"""Streamlit UI for Strata.

Run with:
    pip install -e ".[ui]"
    streamlit run streamlit_app.py

Three tabs:
  Assess     - upload a self-assessment YAML and view the dual-axis heatmap
  Roadmap    - 90-day phased plan keyed off the heatmap
  Deliver    - pick a chain, paste inputs JSON, run the factory, view the draft
"""
from __future__ import annotations

import json
import os
from pathlib import Path

import altair as alt
import pandas as pd
import streamlit as st
import yaml

from strata import registry
from strata.maturity import (
    CAPABILITY_RUBRIC_IDS,
    COMPETENCY_RUBRIC_IDS,
    AssessmentResult,
    CompetencyAssessor,
    MaturityAssessor,
    plan_90_days,
)
from strata.orchestrator import all_chains
from strata.orchestrator.director import Director
from strata.schema import CharacteristicScore

PROJECT_ROOT = Path(__file__).resolve().parent
SAMPLES = PROJECT_ROOT / "samples"

st.set_page_config(
    page_title="Strata",
    page_icon="layers",
    layout="wide",
    initial_sidebar_state="expanded",
    menu_items={
        "About": "Strata: maturity-assessed, rubric-graded AI copilot for the CFO/VP Finance function.",
    },
)

# Light cosmetic CSS — tightens up Streamlit's default whitespace without overriding theme.
st.markdown(
    """
    <style>
      .block-container { padding-top: 2rem; padding-bottom: 2rem; }
      h1, h2, h3 { letter-spacing: -0.01em; }
      [data-testid="stMetricValue"] { font-weight: 600; }
      [data-testid="stSidebar"] .block-container { padding-top: 1rem; }
      .stTabs [data-baseweb="tab-list"] { gap: 1.5rem; }
      .stTabs [data-baseweb="tab"] { padding-left: 0; padding-right: 0; }
    </style>
    """,
    unsafe_allow_html=True,
)


# ---------------------------- helpers ----------------------------


def _scores_from_yaml(raw: dict, rubric_ids: tuple[str, ...]) -> dict[str, list[CharacteristicScore]]:
    out: dict[str, list[CharacteristicScore]] = {}
    for rid in rubric_ids:
        if rid not in raw:
            raise ValueError(f"missing scores for rubric '{rid}'")
        out[rid] = [
            CharacteristicScore(characteristic_id=cid, score=int(s), rationale="self")
            for cid, s in raw[rid].items()
        ]
    return out


def _assess(raw: dict, axis: str) -> AssessmentResult:
    target_id = raw.get("target_id", "unnamed")
    if axis == "function":
        return MaturityAssessor().assess(
            target_id=target_id,
            scores_by_rubric=_scores_from_yaml(raw, CAPABILITY_RUBRIC_IDS),
        )
    return CompetencyAssessor().assess(
        target_id=target_id,
        scores_by_rubric=_scores_from_yaml(raw, COMPETENCY_RUBRIC_IDS),
    )


_SAMPLE_FOR_CHAIN: dict[str, str] = {
    "chain.board_pack.v1":             "board_pack_inputs.json",
    "chain.bva_commentary.v1":         "bva_inputs.json",
    "chain.ma_memo.v1":                "ma_memo_inputs.json",
    "chain.investor_update.v1":        "investor_update_inputs.json",
    "chain.three_statement.v1":        "three_statement_inputs.json",
    "chain.cfo_dashboard.v1":          "cfo_dashboard_inputs.json",
    "chain.risk_register.v1":          "risk_register_inputs.json",
    "chain.capex_memo.v1":             "capex_memo_inputs.json",
    "chain.post_investment_review.v1": "post_investment_review_inputs.json",
    "chain.employee_all_hands.v1":     "employee_all_hands_inputs.json",
    "chain.cross_functional_brief.v1": "cross_functional_brief_inputs.json",
    "chain.earnings_script.v1":        "earnings_script_inputs.json",
}


def _sample_path_for_chain(chain_id: str) -> Path | None:
    name = _SAMPLE_FOR_CHAIN.get(chain_id)
    return SAMPLES / name if name else None


def _heatmap_chart(result: AssessmentResult, title: str):
    df = pd.DataFrame(result.heatmap(), columns=["capability", "score_pct"])
    df["verdict"] = pd.cut(
        df["score_pct"],
        bins=[-1, 50, 70, 101],
        labels=["weak", "developing", "mature"],
    )
    chart = (
        alt.Chart(df, title=title)
        .mark_bar()
        .encode(
            x=alt.X("score_pct:Q", title="Score %", scale=alt.Scale(domain=[0, 100])),
            y=alt.Y("capability:N", sort="-x"),
            color=alt.Color(
                "verdict:N",
                scale=alt.Scale(
                    domain=["weak", "developing", "mature"],
                    range=["#d9534f", "#f0ad4e", "#5cb85c"],
                ),
            ),
            tooltip=["capability", "score_pct", "verdict"],
        )
        .properties(height=max(220, 30 * len(df)))
    )
    return chart


# ---------------------------- sidebar ----------------------------


st.sidebar.title("Strata")
st.sidebar.caption("Maturity-assessed, rubric-graded AI copilot for the CFO / VP Finance function.")

with st.sidebar.expander("Backend status", expanded=False):
    backend = os.getenv("STRATA_LLM_BACKEND", "openai")
    has_key = bool(
        os.getenv("DASHSCOPE_API_KEY")
        or os.getenv("OPENAI_API_KEY")
        or os.getenv("ANTHROPIC_API_KEY")
    )
    base_url = os.getenv("STRATA_LLM_BASE_URL", "(SDK default)")
    grader_model = os.getenv("STRATA_GRADER_MODEL", "(default)")
    st.write(f"**Backend:** `{backend}`")
    st.write(f"**Key:** {'set' if has_key else '_unset_ — using mock'}")
    st.write(f"**Base URL:** `{base_url}`")
    st.write(f"**Grader model:** `{grader_model}`")

uploaded = st.sidebar.file_uploader(
    "Upload self-assessment YAML",
    type=["yaml", "yml"],
    help="Same format as samples/maturity_self_assessment.yaml",
)
default_path = SAMPLES / "maturity_self_assessment.yaml"
use_default = st.sidebar.checkbox(
    "Use sample (Acme Robotics)",
    value=uploaded is None,
)

if uploaded is not None:
    raw = yaml.safe_load(uploaded.read())
elif use_default and default_path.exists():
    raw = yaml.safe_load(default_path.read_text(encoding="utf-8"))
else:
    raw = None


# ---------------------------- tabs ----------------------------


tab_assess, tab_roadmap, tab_deliver = st.tabs(["Assess", "Roadmap", "Deliver"])


with tab_assess:
    st.header("Dual-axis maturity")
    if raw is None:
        st.info("Upload a self-assessment YAML to begin.")
    else:
        try:
            f_res = _assess(raw, "function")
            c_res = _assess(raw, "competency")
        except Exception as e:
            st.error(f"Assessment failed: {e}")
        else:
            cols = st.columns(2)
            with cols[0]:
                st.metric("Function-axis overall", f"{f_res.overall_pct:.1f}%")
                st.altair_chart(
                    _heatmap_chart(f_res, "Function (process maturity)"),
                    use_container_width=True,
                )
            with cols[1]:
                st.metric("Competency-axis overall", f"{c_res.overall_pct:.1f}%")
                st.altair_chart(
                    _heatmap_chart(c_res, "Competency (CFO Handbook pillars)"),
                    use_container_width=True,
                )


with tab_roadmap:
    st.header("90-day roadmap")
    if raw is None:
        st.info("Upload a self-assessment YAML to begin.")
    else:
        axis = st.radio("Axis", ["function", "competency"], horizontal=True)
        try:
            assessment = _assess(raw, axis)
        except Exception as e:
            st.error(f"Assessment failed: {e}")
        else:
            rmap = plan_90_days(assessment, axis=axis)
            st.caption(f"Baseline overall: {rmap.overall_pct:.1f}%")
            for phase in rmap.phases:
                with st.expander(f"{phase.label} - {phase.intent}", expanded=True):
                    rows = [
                        {
                            "capability": a.capability_name,
                            "score_%": round(a.score_pct, 1),
                            "action": a.action,
                            "chain": a.chain_id or "-",
                        }
                        for a in phase.actions
                    ]
                    if rows:
                        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
                    else:
                        st.write("(no actions for this phase)")


with tab_deliver:
    st.header("Run a deliverable chain")
    chain_options = {c.chain_id: c for c in all_chains()}
    chain_id = st.selectbox(
        "Chain",
        options=sorted(chain_options.keys()),
        index=0,
    )
    chain = chain_options[chain_id]
    rb = registry.get(chain.rubric_id)
    st.caption(f"Rubric: {rb.name} ({rb.rubric_id})")

    sample_path = _sample_path_for_chain(chain_id)
    sample_text = sample_path.read_text(encoding="utf-8") if sample_path and sample_path.exists() else "{}"
    inputs_text = st.text_area("Inputs JSON", value=sample_text, height=240)

    # Optional GL extract upload — only meaningful for chains with a perception adapter.
    has_perception = chain.perception is not None
    gl_csv_path: Path | None = None
    if has_perception:
        st.markdown("**Source-system perception**")
        st.caption(
            "This chain has a perception adapter wired in. Upload a GL extract CSV "
            "(columns: period, account, account_type, amount). Aggregates will be "
            "merged into inputs before authoring."
        )
        uploaded_gl = st.file_uploader(
            "GL extract CSV (optional)",
            type=["csv"],
            key="gl_extract",
        )
        if uploaded_gl is not None:
            gl_tmp = PROJECT_ROOT / ".streamlit_uploads"
            gl_tmp.mkdir(exist_ok=True)
            gl_csv_path = gl_tmp / uploaded_gl.name
            gl_csv_path.write_bytes(uploaded_gl.read())
            st.success(f"Saved upload to {gl_csv_path.name}")

    backend_label = (
        f"Use LLM (backend: {os.getenv('STRATA_LLM_BACKEND', 'openai')}; "
        f"key: {'set' if (os.getenv('DASHSCOPE_API_KEY') or os.getenv('OPENAI_API_KEY') or os.getenv('ANTHROPIC_API_KEY')) else 'missing'})"
    )
    use_llm = st.checkbox(backend_label, value=False)

    # Vector exemplars panel — only shown when Astra is configured.
    astra_configured = bool(os.getenv("ASTRA_DB_API_ENDPOINT") and os.getenv("ASTRA_DB_APPLICATION_TOKEN"))
    if astra_configured:
        with st.expander("Similar prior drafts (Astra DB)", expanded=False):
            st.caption(
                "Top-K most similar past drafts of this same chain, retrieved by "
                "vector search. These will be spliced into the author prompt at "
                "draft time when 'Use LLM' is enabled."
            )
            try:
                from strata.vector import get_default_store
                exemplar_query = st.text_input(
                    "Query (defaults to inputs.company + inputs.period at run time)",
                    value="",
                    key=f"exemplar_query_{chain_id}",
                )
                if exemplar_query:
                    hits = get_default_store().search(
                        chain_id=chain_id, query=exemplar_query, top_k=3
                    )
                    if not hits:
                        st.info("No exemplars indexed yet for this chain.")
                    else:
                        for i, h in enumerate(hits, 1):
                            st.markdown(
                                f"**{i}. {h.exemplar.target_id}** — similarity {h.similarity:.3f}"
                                + (f" · score {h.exemplar.score_pct:.1f}%" if h.exemplar.score_pct else "")
                            )
                            st.code(
                                h.exemplar.draft[:600] + ("..." if len(h.exemplar.draft) > 600 else ""),
                                language="markdown",
                            )
                else:
                    n = get_default_store().count(chain_id=chain_id)
                    st.write(f"Indexed exemplars for `{chain_id}`: **{n}**")
            except Exception as e:
                st.warning(f"Astra lookup failed: {type(e).__name__}: {e}")
    else:
        st.caption(
            "_Vector exemplar store inactive (set `ASTRA_DB_API_ENDPOINT` + "
            "`ASTRA_DB_APPLICATION_TOKEN` to enable similar-prior-draft retrieval)._"
        )
    if st.button("Run chain", type="primary"):
        try:
            inputs = json.loads(inputs_text)
        except json.JSONDecodeError as e:
            st.error(f"Inputs JSON invalid: {e}")
        else:
            if gl_csv_path is not None:
                inputs["gl_extract_path"] = str(gl_csv_path)
            with st.spinner(f"Running {chain_id}..."):
                try:
                    run = Director(persist=False, use_llm=use_llm).run_chain(chain_id, inputs)
                except Exception as e:
                    st.error(f"Run failed: {type(e).__name__}: {e}")
                else:
                    r = run.factory_result
                    st.success(
                        f"iterations={r.iterations}  ·  "
                        f"final={r.final_report.report.normalized_pct:.1f}%  ·  "
                        f"passed={r.passed}"
                    )
                    history = pd.DataFrame(
                        [
                            {
                                "iter": i + 1,
                                "weighted": gr.report.weighted_total,
                                "normalized_%": round(gr.report.normalized_pct, 1),
                                "passed": gr.report.passed,
                            }
                            for i, gr in enumerate(r.history)
                        ]
                    )
                    st.dataframe(history, use_container_width=True, hide_index=True)
                    st.markdown("### Draft")
                    st.markdown(r.final_draft)
                    st.download_button(
                        "Download draft as Markdown",
                        data=r.final_draft,
                        file_name=f"{chain_id.replace('.', '_')}-{r.target_id}.md",
                        mime="text/markdown",
                    )


# ---------------------------- footer ----------------------------

st.divider()
_v_col1, _v_col2 = st.columns([3, 1])
with _v_col1:
    st.caption(
        "Strata · 12 chains · 2 axes (function + competency) · "
        "see [NOTICE](./NOTICE) for upstream attribution."
    )
with _v_col2:
    try:
        from strata import __version__ as _v
        st.caption(f"v{_v}")
    except Exception:
        pass
