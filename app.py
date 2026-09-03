from __future__ import annotations

import html
import json
import sys
from dataclasses import asdict
from functools import cache
from pathlib import Path
from typing import Any, Literal

import yaml
from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel, Field

ROOT = Path(__file__).resolve().parent
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from strata import registry
from strata.maturity import CompetencyAssessor, MaturityAssessor, plan_90_days
from strata.maturity.assessor import AssessmentResult
from strata.schema import CharacteristicScore
from strata.orchestrator.chains import all_chains
from strata.orchestrator.director import Director

app = FastAPI(title="Strata", version="0.7.0")


class AssessmentRequest(BaseModel):
    yaml_text: str = Field(min_length=1)
    axis: Literal["function", "competency", "both"] = "both"


class DeliverRequest(BaseModel):
    chain_id: str = Field(min_length=1)
    inputs: dict[str, Any] = Field(default_factory=dict)
    use_llm: bool = False


def _load_sample_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _load_sample_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _rubric_ids_for_axis(axis: str) -> tuple[str, ...]:
    if axis == "function":
        return tuple(MaturityAssessor().rubric_ids)
    if axis == "competency":
        return tuple(CompetencyAssessor().rubric_ids)
    return tuple(MaturityAssessor().rubric_ids) + tuple(CompetencyAssessor().rubric_ids)


def _parse_scores(raw: dict[str, Any], axis: str) -> tuple[str, dict[str, list[CharacteristicScore]]]:
    target_id = raw.get("target_id")
    if not isinstance(target_id, str) or not target_id.strip():
        raise ValueError("missing target_id")

    scores_by_rubric: dict[str, list[CharacteristicScore]] = {}
    for rubric_id in _rubric_ids_for_axis(axis):
        rubric_scores = raw.get(rubric_id)
        if not isinstance(rubric_scores, dict):
            raise ValueError(f"missing scores for '{rubric_id}'")
        scores_by_rubric[rubric_id] = [
            CharacteristicScore.model_validate(
                {
                    "characteristic_id": characteristic_id,
                    "score": score,
                    "rationale": "self-reported",
                }
            )
            for characteristic_id, score in rubric_scores.items()
        ]
    return target_id, scores_by_rubric


def _assessment_payload(result: AssessmentResult, axis: str) -> dict[str, Any]:
    return {
        "axis": axis,
        "target_id": result.target_id,
        "overall_pct": result.overall_pct,
        "heatmap": [
            {"name": name, "score_pct": score_pct}
            for name, score_pct in result.heatmap()
        ],
        "capabilities": [
            {
                "rubric_id": snapshot.rubric.rubric_id,
                "name": snapshot.rubric.name,
                "score_pct": snapshot.score_pct,
                "passed": snapshot.report.passed,
                "report": snapshot.report.model_dump(mode="json"),
            }
            for snapshot in result.capabilities
        ],
    }


def _roadmap_payload(result: Any) -> dict[str, Any]:
    return asdict(result)


def _deliver_payload(run: Any) -> dict[str, Any]:
    factory_result = run.factory_result
    return {
        "run_id": run.run_id,
        "chain_id": run.chain_id,
        "target_id": factory_result.target_id,
        "rubric_id": factory_result.rubric_id,
        "iterations": factory_result.iterations,
        "passed": factory_result.passed,
        "final_draft": factory_result.final_draft,
        "final_report": {
            "report": factory_result.final_report.report.model_dump(mode="json"),
            "raw_response": factory_result.final_report.raw_response,
        },
        "history": [
            {
                "report": item.report.model_dump(mode="json"),
                "raw_response": item.raw_response,
            }
            for item in factory_result.history
        ],
    }


@cache
def _meta_payload() -> dict[str, Any]:
    rubrics = sorted(
        (
            {
                "rubric_id": rubric.rubric_id,
                "scope": rubric.scope,
                "name": rubric.name,
                "version": rubric.version,
            }
            for rubric in registry.load_all().values()
        ),
        key=lambda item: item["rubric_id"],
    )
    chains = [
        {
            "chain_id": chain.chain_id,
            "rubric_id": chain.rubric_id,
            "steps": [step.description for step in chain.steps],
        }
        for chain in all_chains()
    ]
    return {
        "rubrics": rubrics,
        "chains": chains,
        "function_rubrics": len(MaturityAssessor().rubric_ids),
        "competency_rubrics": len(CompetencyAssessor().rubric_ids),
    }


def _render_home() -> str:
    meta_payload = _meta_payload()
    sample_assessment = html.escape(
        _load_sample_text(ROOT / "samples" / "maturity_self_assessment.yaml")
    )
    sample_inputs = html.escape(
        json.dumps(_load_sample_json(ROOT / "samples" / "board_pack_inputs.json"), indent=2)
    )
    meta = html.escape(json.dumps(meta_payload))
    return f"""<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>Strata</title>
    <style>
      :root {{
        color-scheme: dark;
        --bg: #08111f;
        --panel: rgba(12, 19, 36, 0.88);
        --panel-2: rgba(20, 28, 48, 0.88);
        --line: rgba(145, 173, 255, 0.16);
        --text: #edf2ff;
        --muted: #9fb0d0;
        --accent: #7c9cff;
        --accent-2: #53d2c1;
        --danger: #ff7c91;
      }}
      body {{
        margin: 0;
        font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
        background:
          radial-gradient(circle at top left, rgba(124, 156, 255, 0.2), transparent 32%),
          radial-gradient(circle at top right, rgba(83, 210, 193, 0.15), transparent 26%),
          linear-gradient(180deg, #07101c 0%, #050a13 100%);
        color: var(--text);
      }}
      .wrap {{ max-width: 1280px; margin: 0 auto; padding: 40px 24px 64px; }}
      .hero {{ display: grid; gap: 14px; margin-bottom: 24px; }}
      .eyebrow {{ color: var(--accent-2); text-transform: uppercase; letter-spacing: .16em; font-size: 12px; }}
      h1 {{ margin: 0; font-size: clamp(34px, 5vw, 60px); line-height: .95; letter-spacing: -0.05em; }}
      .sub {{ color: var(--muted); max-width: 72ch; line-height: 1.55; }}
      .meta {{ display: flex; flex-wrap: wrap; gap: 10px; margin-top: 8px; }}
      .pill {{ border: 1px solid var(--line); border-radius: 999px; padding: 8px 12px; background: rgba(255,255,255,.03); color: var(--muted); font-size: 13px; }}
      .grid {{ display: grid; grid-template-columns: repeat(12, minmax(0, 1fr)); gap: 18px; }}
      .card {{ grid-column: span 12; border: 1px solid var(--line); border-radius: 20px; background: linear-gradient(180deg, var(--panel), rgba(6, 10, 18, .88)); box-shadow: 0 24px 60px rgba(0,0,0,.22); overflow: hidden; }}
      .card h2 {{ margin: 0; font-size: 18px; }}
      .card .head {{ display: flex; justify-content: space-between; gap: 12px; align-items: baseline; padding: 18px 18px 0; }}
      .card .body {{ padding: 18px; display: grid; gap: 14px; }}
      textarea, select, button {{ width: 100%; border-radius: 14px; border: 1px solid rgba(160, 178, 255, .18); background: rgba(255,255,255,.03); color: var(--text); }}
      textarea {{ min-height: 250px; padding: 14px; resize: vertical; font: 13px/1.5 ui-monospace, SFMono-Regular, Menlo, Consolas, monospace; }}
      select, button {{ padding: 12px 14px; font: 600 14px/1.2 Inter, system-ui, sans-serif; }}
      button {{ background: linear-gradient(135deg, rgba(124,156,255,.95), rgba(83,210,193,.85)); color: #07101c; cursor: pointer; border: 0; }}
      button.secondary {{ background: rgba(255,255,255,.06); color: var(--text); border: 1px solid rgba(160, 178, 255, .18); }}
      .two {{ display: grid; gap: 18px; grid-template-columns: repeat(2, minmax(0, 1fr)); }}
      .three {{ display: grid; gap: 18px; grid-template-columns: repeat(3, minmax(0, 1fr)); }}
      .result {{ border: 1px solid rgba(160, 178, 255, .14); border-radius: 16px; background: rgba(255,255,255,.03); padding: 14px; min-height: 120px; }}
      .result pre {{ margin: 0; white-space: pre-wrap; word-break: break-word; font: 12px/1.55 ui-monospace, SFMono-Regular, Menlo, Consolas, monospace; color: #dce5ff; }}
      .bars {{ display: grid; gap: 10px; }}
      .bar-row {{ display: grid; gap: 6px; }}
      .bar-label {{ display: flex; justify-content: space-between; gap: 10px; color: var(--muted); font-size: 13px; }}
      .bar-track {{ height: 10px; border-radius: 999px; background: rgba(255,255,255,.05); overflow: hidden; }}
      .bar-fill {{ height: 100%; border-radius: inherit; background: linear-gradient(90deg, var(--accent), var(--accent-2)); }}
      .section {{ margin-top: 18px; }}
      .muted {{ color: var(--muted); font-size: 13px; }}
      .error {{ color: var(--danger); }}
      .steps {{ display: grid; gap: 8px; margin: 0; padding-left: 18px; color: var(--muted); }}
      .footer {{ margin-top: 18px; color: var(--muted); font-size: 12px; }}
      @media (min-width: 980px) {{
        .span-7 {{ grid-column: span 7; }}
        .span-5 {{ grid-column: span 5; }}
      }}
    </style>
  </head>
  <body>
    <div class="wrap">
      <div class="hero">
        <div class="eyebrow">Strata on Vercel</div>
        <h1>Maturity assessment, roadmaping, and deliverable execution in one app.</h1>
        <div class="sub">
          FastAPI front end, JSON APIs, and the same rubric engine the CLI uses. The Vercel build stays pure Python, so no Rust toolchain is needed at runtime.
        </div>
        <div class="meta">
          <div class="pill">{len(meta_payload["rubrics"])} rubrics loaded</div>
          <div class="pill">{len(meta_payload["chains"])} executable chains</div>
          <div class="pill">Function axis: {meta_payload["function_rubrics"]} rubrics</div>
          <div class="pill">Competency axis: {meta_payload["competency_rubrics"]} rubrics</div>
        </div>
      </div>

      <div class="grid">
        <section class="card span-7">
          <div class="head">
            <h2>Assess + roadmap</h2>
            <div class="muted">Paste the shared YAML self-assessment.</div>
          </div>
          <div class="body">
            <div class="three">
              <select id="axis">
                <option value="both">Both axes</option>
                <option value="function">Function only</option>
                <option value="competency">Competency only</option>
              </select>
              <button id="assess-btn">Assess</button>
              <button id="roadmap-btn" class="secondary">Roadmap</button>
            </div>
            <textarea id="assessment-input">{sample_assessment}</textarea>
            <div class="two">
              <div class="result" id="assessment-result"><pre>Assessment output will appear here.</pre></div>
              <div class="result" id="roadmap-result"><pre>Roadmap output will appear here.</pre></div>
            </div>
          </div>
        </section>

        <section class="card span-5">
          <div class="head">
            <h2>Deliver</h2>
            <div class="muted">Run a chain with JSON inputs.</div>
          </div>
          <div class="body">
            <select id="chain-select"></select>
            <button id="deliver-btn">Run chain</button>
            <textarea id="deliver-input">{sample_inputs}</textarea>
            <div class="result" id="deliver-result"><pre>Deliverable output will appear here.</pre></div>
            <div class="result">
              <div class="muted" style="margin-bottom: 8px;">Selected chain steps</div>
              <ul id="chain-steps" class="steps"></ul>
            </div>
          </div>
        </section>

        <section class="card">
          <div class="head">
            <h2>Catalog</h2>
            <div class="muted">Loaded from the same YAML rubrics and chain registry as the CLI.</div>
          </div>
          <div class="body">
            <div class="result" id="catalog-result"><pre>{meta}</pre></div>
          </div>
        </section>
      </div>

      <div class="footer">API endpoints: <code>/api/assess</code>, <code>/api/roadmap</code>, <code>/api/deliver</code>, <code>/api/meta</code>.</div>
    </div>

    <script>
      const CATALOG = JSON.parse(document.getElementById('catalog-result').innerText);

      const chainSelect = document.getElementById('chain-select');
      const chainSteps = document.getElementById('chain-steps');
      for (const chain of CATALOG.chains) {{
        const option = document.createElement('option');
        option.value = chain.chain_id;
        option.textContent = `${{chain.chain_id}} → ${{chain.rubric_id}}`;
        chainSelect.appendChild(option);
      }}

      function selectedChain() {{
        return CATALOG.chains.find((chain) => chain.chain_id === chainSelect.value) || CATALOG.chains[0];
      }}

      function renderChainSteps() {{
        const chain = selectedChain();
        chainSteps.innerHTML = '';
        if (!chain) return;
        for (const step of chain.steps) {{
          const item = document.createElement('li');
          item.textContent = step;
          chainSteps.appendChild(item);
        }}
      }}

      chainSelect.addEventListener('change', renderChainSteps);
      renderChainSteps();

      async function postJSON(url, payload) {{
        const response = await fetch(url, {{
          method: 'POST',
          headers: {{ 'Content-Type': 'application/json' }},
          body: JSON.stringify(payload),
        }});
        const data = await response.json();
        if (!response.ok) {{
          throw new Error(data.detail || 'Request failed');
        }}
        return data;
      }}

      function renderBars(container, items) {{
        if (!items.length) {{
          container.innerHTML = '<pre>No data.</pre>';
          return;
        }}
        const max = Math.max(...items.map((item) => item.score_pct), 1);
        container.innerHTML = '<div class="bars"></div>';
        const wrap = container.querySelector('.bars');
        for (const item of items) {{
          const row = document.createElement('div');
          row.className = 'bar-row';
          row.innerHTML = `
            <div class="bar-label"><span>${{item.name}}</span><span>${{item.score_pct.toFixed(1)}}%</span></div>
            <div class="bar-track"><div class="bar-fill" style="width: ${{Math.max((item.score_pct / max) * 100, 2).toFixed(1)}}%"></div></div>
          `;
          wrap.appendChild(row);
        }}
      }}

      function renderAssessment(container, payload) {{
        if (payload.results) {{
          const parts = Object.entries(payload.results).map(([axis, result]) => `
            <section class="section">
              <div class="muted">${{axis}} axis · ${{result.target_id}}</div>
              <div style="margin: 6px 0 10px; font-size: 22px; font-weight: 700;">${{result.overall_pct.toFixed(1)}}%</div>
              <div class="bars">
                ${{result.heatmap.map((item) => `
                  <div class="bar-row">
                    <div class="bar-label"><span>${{item.name}}</span><span>${{item.score_pct.toFixed(1)}}%</span></div>
                    <div class="bar-track"><div class="bar-fill" style="width: ${{Math.max(item.score_pct, 2).toFixed(1)}}%"></div></div>
                  </div>
                `).join('')}}
              </div>
            </section>
          `).join('');
          container.innerHTML = parts;
          return;
        }}
        container.innerHTML = `
          <div class="muted">${{payload.axis}} axis · ${{payload.target_id}}</div>
          <div style="margin: 6px 0 10px; font-size: 22px; font-weight: 700;">${{payload.overall_pct.toFixed(1)}}%</div>
          <div class="bars">
            ${{payload.heatmap.map((item) => `
              <div class="bar-row">
                <div class="bar-label"><span>${{item.name}}</span><span>${{item.score_pct.toFixed(1)}}%</span></div>
                <div class="bar-track"><div class="bar-fill" style="width: ${{Math.max(item.score_pct, 2).toFixed(1)}}%"></div></div>
              </div>
            `).join('')}}
          </div>
        `;
      }}

      function renderRoadmap(container, payload) {{
        if (payload.results) {{
          const sections = Object.entries(payload.results).map(([axis, result]) => `
            <section class="section">
              <div class="muted">${{axis}} axis · ${{result.target_id}}</div>
              <div style="margin: 6px 0 10px; font-size: 20px; font-weight: 700;">${{result.overall_pct.toFixed(1)}}%</div>
              ${{result.phases.map((phase) => `
                <div style="margin-bottom: 14px;">
                  <div style="font-weight: 700; margin-bottom: 6px;">${{phase.label}} · ${{phase.intent}}</div>
                  <ul class="steps">${{phase.actions.map((action) => `<li>${{action.action}}</li>`).join('')}}</ul>
                </div>
              `).join('')}}
            </section>
          `).join('');
          container.innerHTML = sections;
          return;
        }}
        container.innerHTML = `
          <div class="muted">${{payload.axis}} axis · ${{payload.target_id}}</div>
          <div style="margin: 6px 0 10px; font-size: 20px; font-weight: 700;">${{payload.overall_pct.toFixed(1)}}%</div>
          ${{payload.phases.map((phase) => `
            <div style="margin-bottom: 14px;">
              <div style="font-weight: 700; margin-bottom: 6px;">${{phase.label}} · ${{phase.intent}}</div>
              <ul class="steps">${{phase.actions.map((action) => `<li>${{action.action}}</li>`).join('')}}</ul>
            </div>
          `).join('')}}
        `;
      }}

      function renderDeliver(container, payload) {{
        const report = payload.final_report.report;
        container.innerHTML = `
          <div class="muted">${{payload.chain_id}} · run ${{payload.run_id}}</div>
          <div style="margin: 6px 0 10px; font-size: 20px; font-weight: 700;">${{payload.passed ? 'passed' : 'failed'}} · ${{report.normalized_pct.toFixed(1)}}%</div>
          <pre>${{JSON.stringify({{ iterations: payload.iterations, target_id: payload.target_id, rubric_id: payload.rubric_id, final_report: report }}, null, 2)}}</pre>
        `;
      }}

      function showError(container, error) {{
        container.innerHTML = `<pre class="error">${{error.message}}</pre>`;
      }}

      document.getElementById('assess-btn').addEventListener('click', async () => {{
        const container = document.getElementById('assessment-result');
        container.innerHTML = '<pre>Running...</pre>';
        try {{
          const payload = await postJSON('/api/assess', {{ yaml_text: document.getElementById('assessment-input').value, axis: document.getElementById('axis').value }});
          renderAssessment(container, payload);
        }} catch (error) {{
          showError(container, error);
        }}
      }});

      document.getElementById('roadmap-btn').addEventListener('click', async () => {{
        const container = document.getElementById('roadmap-result');
        container.innerHTML = '<pre>Running...</pre>';
        try {{
          const payload = await postJSON('/api/roadmap', {{ yaml_text: document.getElementById('assessment-input').value, axis: document.getElementById('axis').value }});
          renderRoadmap(container, payload);
        }} catch (error) {{
          showError(container, error);
        }}
      }});

      document.getElementById('deliver-btn').addEventListener('click', async () => {{
        const container = document.getElementById('deliver-result');
        container.innerHTML = '<pre>Running...</pre>';
        try {{
          const payload = await postJSON('/api/deliver', {{
            chain_id: chainSelect.value,
            inputs: JSON.parse(document.getElementById('deliver-input').value),
            use_llm: false,
          }});
          renderDeliver(container, payload);
        }} catch (error) {{
          showError(container, error);
        }}
      }});
    </script>
  </body>
</html>"""


@app.get("/", response_class=HTMLResponse)
def home() -> HTMLResponse:
    return HTMLResponse(_render_home())


@app.get("/api/meta")
def meta() -> JSONResponse:
    return JSONResponse(_meta_payload())


@app.post("/api/assess")
def assess(request: AssessmentRequest) -> JSONResponse:
    try:
        raw = yaml.safe_load(request.yaml_text)
        if not isinstance(raw, dict):
            raise ValueError("assessment YAML must parse to a mapping")
        target_id, scores_by_rubric = _parse_scores(raw, request.axis)
        payload: dict[str, Any]
        if request.axis == "both":
            payload = {
                "axis": "both",
                "results": {
                    "function": _assessment_payload(
                        MaturityAssessor().assess(target_id=target_id, scores_by_rubric=scores_by_rubric),
                        "function",
                    ),
                    "competency": _assessment_payload(
                        CompetencyAssessor().assess(target_id=target_id, scores_by_rubric=scores_by_rubric),
                        "competency",
                    ),
                },
            }
        elif request.axis == "function":
            payload = _assessment_payload(
                MaturityAssessor().assess(target_id=target_id, scores_by_rubric=scores_by_rubric),
                "function",
            )
        else:
            payload = _assessment_payload(
                CompetencyAssessor().assess(target_id=target_id, scores_by_rubric=scores_by_rubric),
                "competency",
            )
        return JSONResponse(payload)
    except (ValueError, KeyError, yaml.YAMLError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/roadmap")
def roadmap(request: AssessmentRequest) -> JSONResponse:
    try:
        raw = yaml.safe_load(request.yaml_text)
        if not isinstance(raw, dict):
            raise ValueError("assessment YAML must parse to a mapping")
        target_id, scores_by_rubric = _parse_scores(raw, request.axis)
        if request.axis == "both":
            function_assessment = MaturityAssessor().assess(
                target_id=target_id, scores_by_rubric=scores_by_rubric
            )
            competency_assessment = CompetencyAssessor().assess(
                target_id=target_id, scores_by_rubric=scores_by_rubric
            )
            payload = {
                "axis": "both",
                "results": {
                    "function": _roadmap_payload(plan_90_days(function_assessment, axis="function")),
                    "competency": _roadmap_payload(plan_90_days(competency_assessment, axis="competency")),
                },
            }
        elif request.axis == "function":
            assessment = MaturityAssessor().assess(target_id=target_id, scores_by_rubric=scores_by_rubric)
            payload = _roadmap_payload(plan_90_days(assessment, axis="function"))
        else:
            assessment = CompetencyAssessor().assess(target_id=target_id, scores_by_rubric=scores_by_rubric)
            payload = _roadmap_payload(plan_90_days(assessment, axis="competency"))
        return JSONResponse(payload)
    except (ValueError, KeyError, yaml.YAMLError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/deliver")
def deliver(request: DeliverRequest) -> JSONResponse:
    try:
        run = Director(persist=False, use_llm=request.use_llm).run_chain(request.chain_id, request.inputs)
        return JSONResponse(_deliver_payload(run))
    except (KeyError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/healthz")
def healthz() -> JSONResponse:
    return JSONResponse({"ok": True})
