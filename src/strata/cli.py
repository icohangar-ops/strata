"""Strata CLI."""
from __future__ import annotations

import json
from pathlib import Path

import typer
import yaml
from rich.console import Console
from rich.table import Table

from strata import registry
from strata.maturity import (
    CAPABILITY_RUBRIC_IDS,
    COMPETENCY_RUBRIC_IDS,
    AssessmentResult,
    CompetencyAssessor,
    MaturityAssessor,
)
from strata.orchestrator.chains import all_chains
from strata.orchestrator.director import Director
from strata.schema import CharacteristicScore

app = typer.Typer(no_args_is_help=True, add_completion=False)
console = Console()


def _scores_from_yaml(raw: dict, rubric_ids: tuple[str, ...], path: Path) -> dict[str, list[CharacteristicScore]]:
    by_rubric: dict[str, list[CharacteristicScore]] = {}
    for rid in rubric_ids:
        if rid not in raw:
            raise typer.BadParameter(f"missing scores for rubric '{rid}' in {path}")
        by_rubric[rid] = [
            CharacteristicScore(characteristic_id=cid, score=int(s), rationale="self-assessed")
            for cid, s in raw[rid].items()
        ]
    return by_rubric


def _load_assessment(path: Path, axis: str = "function") -> AssessmentResult:
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    target_id = raw.get("target_id", "unnamed")
    if axis == "function":
        by_rubric = _scores_from_yaml(raw, CAPABILITY_RUBRIC_IDS, path)
        return MaturityAssessor().assess(target_id=target_id, scores_by_rubric=by_rubric)
    if axis == "competency":
        by_rubric = _scores_from_yaml(raw, COMPETENCY_RUBRIC_IDS, path)
        return CompetencyAssessor().assess(target_id=target_id, scores_by_rubric=by_rubric)
    raise typer.BadParameter(f"axis must be 'function' or 'competency', got '{axis}'")


def _print_heatmap(result: AssessmentResult, label: str) -> None:
    console.rule(f"[bold]{label} — {result.target_id}")
    t = Table("capability", "score_%", "verdict")
    for name, pct in result.heatmap():
        verdict = "weak" if pct < 50 else "developing" if pct < 70 else "mature"
        t.add_row(name, f"{pct:.1f}", verdict)
    console.print(t)
    console.print(f"[bold]overall:[/bold] {result.overall_pct:.1f}%")


def _print_factory_result(r) -> None:
    console.rule(f"[bold]{r.rubric_id} — {r.target_id}")
    console.print(f"iterations: {r.iterations}    passed: {r.passed}")
    console.print(f"final score: {r.final_report.report.normalized_pct:.1f}%")
    t = Table("iter", "weighted", "normalized_%", "passed")
    for i, gr in enumerate(r.history, start=1):
        t.add_row(str(i), f"{gr.report.weighted_total:.2f}",
                  f"{gr.report.normalized_pct:.1f}",
                  "yes" if gr.report.passed else "no")
    console.print(t)


@app.command("board-pack")
def board_pack(
    inputs: Path = typer.Option(..., exists=True, readable=True, help="JSON inputs file"),
    persist: bool = typer.Option(False, help="Persist run to Postgres (requires DB)"),
    use_llm: bool = typer.Option(False, "--use-llm", help="Use Anthropic LLM for author + grader"),
) -> None:
    """L3 + L4: run the board-pack chain end-to-end."""
    payload = json.loads(inputs.read_text(encoding="utf-8"))
    director = Director(persist=persist, use_llm=use_llm)
    run = director.run_board_pack(payload)
    _print_factory_result(run.factory_result)
    console.rule("Final draft")
    console.print(run.factory_result.final_draft)


@app.command("assess")
def assess(
    self_assessment: Path = typer.Option(..., exists=True, readable=True),
    axis: str = typer.Option(
        "function",
        "--axis",
        help="Which axis to score: 'function' (process maturity), 'competency' (CFO pillars), or 'both'",
    ),
) -> None:
    """L1: run the maturity assessor against a self-assessment YAML."""
    if axis == "both":
        f = _load_assessment(self_assessment, axis="function")
        c = _load_assessment(self_assessment, axis="competency")
        _print_heatmap(f, "Function-axis heatmap")
        _print_heatmap(c, "Competency-axis heatmap (CFO Handbook pillars)")
        return
    result = _load_assessment(self_assessment, axis=axis)
    label = "Maturity heatmap" if axis == "function" else "Competency heatmap (CFO Handbook pillars)"
    _print_heatmap(result, label)


@app.command("run")
def run(
    self_assessment: Path = typer.Option(..., exists=True, readable=True,
                                         help="Self-assessment YAML (drives routing)"),
    inputs: Path = typer.Option(..., exists=True, readable=True,
                                help="JSON inputs for whichever chain is picked"),
    persist: bool = typer.Option(False, help="Persist run"),
    use_llm: bool = typer.Option(False, "--use-llm"),
    axis: str = typer.Option(
        "function",
        "--axis",
        help="Which axis to route on: 'function' or 'competency'",
    ),
) -> None:
    """L3 v2: dynamic routing. Picks the chain that targets the weakest capability."""
    assessment = _load_assessment(self_assessment, axis=axis)
    payload = json.loads(inputs.read_text(encoding="utf-8"))
    director = Director(persist=persist, use_llm=use_llm)
    decision, run = director.route(assessment, payload)
    console.rule("[bold]Routing decision")
    console.print(f"axis:                {axis}")
    console.print(f"chain picked:        [cyan]{decision.chain.chain_id}[/cyan]")
    console.print(f"deliverable rubric:  {decision.chain.rubric_id}")
    console.print(f"weakest capability:  {decision.weakest_capability} ({decision.weakest_pct:.1f}%)")
    console.print(f"rationale:           {decision.rationale}")
    _print_factory_result(run.factory_result)
    console.rule("Final draft")
    console.print(run.factory_result.final_draft)


@app.command("roadmap")
def roadmap(
    self_assessment: Path = typer.Option(..., exists=True, readable=True),
    axis: str = typer.Option(
        "function", "--axis",
        help="Which axis to plan against: 'function' or 'competency'",
    ),
) -> None:
    """Generate a 90-day roadmap from a self-assessment YAML."""
    from strata.maturity import plan_90_days

    assessment = _load_assessment(self_assessment, axis=axis)
    rmap = plan_90_days(assessment, axis=axis)
    console.rule(f"[bold]90-day roadmap — {rmap.target_id} ({rmap.axis} axis, "
                 f"baseline {rmap.overall_pct:.1f}%)")
    for phase in rmap.phases:
        console.rule(f"[bold cyan]{phase.label} — {phase.intent}")
        t = Table("capability", "score_%", "action", "chain")
        for a in phase.actions:
            t.add_row(
                a.capability_name,
                f"{a.score_pct:.1f}",
                a.action,
                a.chain_id or "-",
            )
        console.print(t)


exemplars_app = typer.Typer(no_args_is_help=True, help="Manage the vector exemplar store (Astra DB)")
app.add_typer(exemplars_app, name="exemplars")


@exemplars_app.command("ingest")
def exemplars_ingest(
    chain_id: str = typer.Argument(..., help="e.g. chain.bva_commentary.v1"),
    draft_file: Path = typer.Argument(..., exists=True, readable=True),
    target_id: str = typer.Option(
        ...,
        "--target-id",
        help="Stable identifier for this draft (e.g. 'acme::march_2026')",
    ),
    score_pct: float | None = typer.Option(None, "--score-pct"),
) -> None:
    """Add a past deliverable draft to the exemplar store."""
    from strata.vector import Exemplar, get_default_store, NullExemplarStore
    from strata.vector.exemplars import make_exemplar_id

    store = get_default_store()
    if isinstance(store, NullExemplarStore):
        raise typer.BadParameter(
            "Astra DB not configured. Set ASTRA_DB_API_ENDPOINT and ASTRA_DB_APPLICATION_TOKEN."
        )
    ex = Exemplar(
        id=make_exemplar_id(chain_id, target_id),
        chain_id=chain_id,
        target_id=target_id,
        draft=draft_file.read_text(encoding="utf-8"),
        score_pct=score_pct,
    )
    store.upsert(ex)
    console.print(f"[green]Ingested[/green] exemplar id={ex.id} for chain={chain_id}")


@exemplars_app.command("search")
def exemplars_search(
    chain_id: str = typer.Argument(..., help="e.g. chain.bva_commentary.v1"),
    query: str = typer.Option(..., "--query", "-q"),
    top_k: int = typer.Option(3, "--top-k", "-k"),
) -> None:
    """Show top-K most similar past drafts for a chain."""
    from strata.vector import get_default_store, NullExemplarStore

    store = get_default_store()
    if isinstance(store, NullExemplarStore):
        raise typer.BadParameter(
            "Astra DB not configured. Set ASTRA_DB_API_ENDPOINT and ASTRA_DB_APPLICATION_TOKEN."
        )
    hits = store.search(chain_id=chain_id, query=query, top_k=top_k)
    if not hits:
        console.print("[yellow]No exemplars found for this chain.[/yellow]")
        return
    t = Table("rank", "similarity", "target_id", "score_%", "draft (first 80 chars)")
    for i, h in enumerate(hits, 1):
        t.add_row(
            str(i),
            f"{h.similarity:.3f}",
            h.exemplar.target_id,
            f"{h.exemplar.score_pct:.1f}" if h.exemplar.score_pct is not None else "-",
            (h.exemplar.draft[:80] + "...") if len(h.exemplar.draft) > 80 else h.exemplar.draft,
        )
    console.print(t)


@exemplars_app.command("count")
def exemplars_count(
    chain_id: str | None = typer.Option(None, "--chain-id"),
) -> None:
    """Count exemplars in the store, optionally filtered by chain."""
    from strata.vector import get_default_store

    store = get_default_store()
    n = store.count(chain_id=chain_id)
    scope = chain_id or "all chains"
    console.print(f"Exemplars in store ({scope}): [bold]{n}[/bold]")


@app.command("rubrics")
def list_rubrics() -> None:
    """List loaded rubrics."""
    rs = registry.load_all()
    t = Table("rubric_id", "scope", "name", "groups", "max_score")
    for rb in sorted(rs.values(), key=lambda r: r.rubric_id):
        t.add_row(rb.rubric_id, rb.scope, rb.name, str(len(rb.groups)), str(rb.max_score))
    console.print(t)


@app.command("chains")
def list_chains() -> None:
    """List registered chains."""
    t = Table("chain_id", "deliverable_rubric", "steps")
    for c in all_chains():
        t.add_row(c.chain_id, c.rubric_id, str(len(c.steps)))
    console.print(t)


if __name__ == "__main__":  # pragma: no cover
    app()
