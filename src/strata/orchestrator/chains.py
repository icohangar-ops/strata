"""Chain registry. One Chain per executable deliverable."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from strata.deliverable.factory import Author


@dataclass(frozen=True)
class ChainStep:
    skill_id: str
    description: str


@dataclass(frozen=True)
class Chain:
    chain_id: str
    rubric_id: str            # the L4 deliverable rubric this chain produces
    steps: tuple[ChainStep, ...]
    mock_author: Author       # used when Director runs in offline / mock mode
    depends_on: tuple[str, ...] = ()  # chain_ids whose final draft this chain consumes
    perception: Any | None = None     # optional callable: (inputs) -> enriched inputs


def _board_pack_chain() -> Chain:
    from strata.deliverable.board_pack import mock_author
    return Chain(
        chain_id="chain.board_pack.v1",
        rubric_id="rb.deliverable.board_pack",
        steps=(
            ChainStep("perception.gather_close_outputs", "Pull close outputs and source numbers"),
            ChainStep("compose.upstream_inputs", "Fold in upstream BvA commentary if present"),
            ChainStep("brain.compose_narrative", "Compose narrative draft per persona"),
            ChainStep("brain.grade", "Grade against board-pack rubric"),
            ChainStep("brain.revise", "Revise until threshold met"),
            ChainStep("action.persist", "Persist final pack and scores"),
        ),
        mock_author=mock_author,
        depends_on=("chain.bva_commentary.v1",),
    )


def _bva_commentary_chain() -> Chain:
    from strata.deliverable.bva_commentary import mock_author
    from strata.perception import csv_gl_adapter
    return Chain(
        chain_id="chain.bva_commentary.v1",
        rubric_id="rb.deliverable.bva_commentary",
        steps=(
            ChainStep("perception.pull_bva", "Pull budget, actuals, and prior-period trends"),
            ChainStep("perception.gl_extract", "Pull GL extract and compute aggregates"),
            ChainStep("brain.decompose_variance", "Decompose variance into volume / price / mix"),
            ChainStep("brain.compose_commentary", "Compose commentary per persona"),
            ChainStep("brain.grade", "Grade against BvA commentary rubric"),
            ChainStep("brain.revise", "Revise until threshold met"),
            ChainStep("action.persist", "Persist final commentary and scores"),
        ),
        mock_author=mock_author,
        perception=csv_gl_adapter(),
    )


def _ma_memo_chain() -> Chain:
    from strata.deliverable.ma_memo import mock_author
    return Chain(
        chain_id="chain.ma_memo.v1",
        rubric_id="rb.deliverable.ma_memo",
        steps=(
            ChainStep("perception.pull_target_financials", "Pull target financials and CIM"),
            ChainStep("perception.pull_market_comps", "Pull peer and transaction comps"),
            ChainStep("brain.qoe_adjust", "Apply QoE adjustments to reported EBITDA"),
            ChainStep("brain.triangulate_valuation", "Triangulate DCF / peer / transaction multiples"),
            ChainStep("brain.compose_memo", "Compose IC memo per persona"),
            ChainStep("brain.grade", "Grade against IC memo rubric"),
            ChainStep("brain.revise", "Revise until threshold met"),
            ChainStep("action.persist", "Persist final memo and scores"),
        ),
        mock_author=mock_author,
    )


def _investor_update_chain() -> Chain:
    from strata.deliverable.investor_update import mock_author
    return Chain(
        chain_id="chain.investor_update.v1",
        rubric_id="rb.deliverable.investor_update",
        steps=(
            ChainStep("perception.pull_kpis", "Pull headline KPIs and prior-period comparators"),
            ChainStep("perception.recall_prior_commitments", "Recall prior-period commitments"),
            ChainStep("brain.compose_letter", "Compose update per persona"),
            ChainStep("brain.segment_asks", "Segment asks by recipient investor"),
            ChainStep("brain.grade", "Grade against investor-update rubric"),
            ChainStep("brain.revise", "Revise until threshold met"),
            ChainStep("action.persist", "Persist final letter and scores"),
        ),
        mock_author=mock_author,
    )


def _three_statement_chain() -> Chain:
    from strata.deliverable.three_statement import mock_author
    return Chain(
        chain_id="chain.three_statement.v1",
        rubric_id="rb.deliverable.three_statement",
        steps=(
            ChainStep("perception.pull_history", "Pull historical financials"),
            ChainStep("brain.build_inputs_sheet", "Build inputs sheet with labeled drivers"),
            ChainStep("brain.link_pl_bs_cf", "Link P&L, balance sheet, and cash-flow statements"),
            ChainStep("brain.scenarios", "Wire scenario toggle and sensitivity tables"),
            ChainStep("brain.validate", "Validate balance-sheet balance and tie-out"),
            ChainStep("brain.grade", "Grade against three-statement rubric"),
            ChainStep("brain.revise", "Revise until threshold met"),
            ChainStep("action.persist", "Persist model spec and scores"),
        ),
        mock_author=mock_author,
    )


def _cfo_dashboard_chain() -> Chain:
    from strata.deliverable.cfo_dashboard import mock_author
    return Chain(
        chain_id="chain.cfo_dashboard.v1",
        rubric_id="rb.deliverable.cfo_dashboard",
        steps=(
            ChainStep("perception.pull_value_metrics", "Pull EVA, ROIC, WACC, FCF inputs"),
            ChainStep("perception.pull_working_capital", "Pull DSO, DPO, DIO from GL"),
            ChainStep("perception.pull_risk_register", "Pull top-5 risks and control status"),
            ChainStep("perception.pull_capital_pipeline", "Pull capital project list with ROI"),
            ChainStep("brain.compose_dashboard", "Assemble one-page dashboard per persona"),
            ChainStep("brain.grade", "Grade against CFO dashboard rubric"),
            ChainStep("brain.revise", "Revise until threshold met"),
            ChainStep("action.persist", "Persist final dashboard and scores"),
        ),
        mock_author=mock_author,
    )


def _risk_register_chain() -> Chain:
    from strata.deliverable.risk_register import mock_author
    return Chain(
        chain_id="chain.risk_register.v1",
        rubric_id="rb.deliverable.risk_register",
        steps=(
            ChainStep("perception.pull_risks", "Pull risks from BU + functional inputs"),
            ChainStep("perception.pull_controls", "Pull existing controls and last-test dates"),
            ChainStep("brain.score_likelihood_impact", "Score likelihood and impact 1-5 with anchors"),
            ChainStep("brain.compute_heat", "Compute heat score and flag > 15"),
            ChainStep("brain.compose_register", "Compose register per persona"),
            ChainStep("brain.grade", "Grade against risk-register rubric"),
            ChainStep("brain.revise", "Revise until threshold met"),
            ChainStep("action.persist", "Persist final register and scores"),
        ),
        mock_author=mock_author,
    )


def _capex_memo_chain() -> Chain:
    from strata.deliverable.capex_memo import mock_author
    return Chain(
        chain_id="chain.capex_memo.v1",
        rubric_id="rb.deliverable.capex_memo",
        steps=(
            ChainStep("perception.pull_project_financials", "Pull project model and assumptions"),
            ChainStep("brain.compute_irr_payback", "Compute IRR and payback vs hurdle/ceiling"),
            ChainStep("brain.build_sensitivity", "Build two-way sensitivity on top drivers"),
            ChainStep("brain.compose_memo", "Compose memo per persona"),
            ChainStep("brain.grade", "Grade against capex-memo rubric"),
            ChainStep("brain.revise", "Revise until threshold met"),
            ChainStep("action.persist", "Persist final memo and scores"),
        ),
        mock_author=mock_author,
    )


def _post_investment_review_chain() -> Chain:
    from strata.deliverable.post_investment_review import mock_author
    return Chain(
        chain_id="chain.post_investment_review.v1",
        rubric_id="rb.deliverable.post_investment_review",
        steps=(
            ChainStep("perception.pull_actuals", "Pull actuals through review window"),
            ChainStep("perception.recall_projections", "Recall projected returns from original memo"),
            ChainStep("brain.decompose_variance", "Decompose variance into volume / price / mix / timing / one-time"),
            ChainStep("brain.compose_review", "Compose review per persona"),
            ChainStep("brain.grade", "Grade against post-investment-review rubric"),
            ChainStep("brain.revise", "Revise until threshold met"),
            ChainStep("action.persist", "Persist review and route to council"),
        ),
        mock_author=mock_author,
    )


def _employee_all_hands_chain() -> Chain:
    from strata.deliverable.employee_all_hands import mock_author
    return Chain(
        chain_id="chain.employee_all_hands.v1",
        rubric_id="rb.deliverable.employee_all_hands",
        steps=(
            ChainStep("perception.pull_business_highlights", "Pull period highlights for the all-hands"),
            ChainStep("brain.translate_to_plain_english", "Translate finance jargon to plain English"),
            ChainStep("brain.compose_segment", "Compose 10-minute segment per persona"),
            ChainStep("brain.draft_qa", "Draft top 5 anticipated employee questions"),
            ChainStep("brain.grade", "Grade against employee-all-hands rubric"),
            ChainStep("brain.revise", "Revise until threshold met"),
            ChainStep("action.persist", "Persist segment and Q&A"),
        ),
        mock_author=mock_author,
    )


def _cross_functional_brief_chain() -> Chain:
    from strata.deliverable.cross_functional_brief import mock_author
    return Chain(
        chain_id="chain.cross_functional_brief.v1",
        rubric_id="rb.deliverable.cross_functional_brief",
        steps=(
            ChainStep("perception.pull_peer_metrics", "Pull peer function's primary metrics"),
            ChainStep("perception.recall_open_decisions", "Recall open decisions and dependencies"),
            ChainStep("brain.compose_agenda", "Compose 30-minute agenda per persona"),
            ChainStep("brain.grade", "Grade against cross-functional-brief rubric"),
            ChainStep("brain.revise", "Revise until threshold met"),
            ChainStep("action.persist", "Persist agenda and route action items"),
        ),
        mock_author=mock_author,
    )


def _earnings_script_chain() -> Chain:
    from strata.deliverable.earnings_script import mock_author
    return Chain(
        chain_id="chain.earnings_script.v1",
        rubric_id="rb.deliverable.earnings_script",
        steps=(
            ChainStep("perception.pull_quarterly_results", "Pull quarterly results and prior guidance"),
            ChainStep("brain.draft_prepared_remarks", "Draft prepared remarks with safe-harbor"),
            ChainStep("brain.draft_guidance_bridge", "Draft guidance change bridge"),
            ChainStep("brain.draft_capital_message", "Draft capital allocation message"),
            ChainStep("brain.draft_qa_prep", "Draft top-10 analyst questions with answers"),
            ChainStep("brain.grade", "Grade against earnings-script rubric"),
            ChainStep("brain.revise", "Revise until threshold met"),
            ChainStep("action.persist", "Persist script and Q&A prep"),
        ),
        mock_author=mock_author,
    )


_REGISTRY: dict[str, Chain] = {
    "rb.deliverable.board_pack": _board_pack_chain(),
    "rb.deliverable.bva_commentary": _bva_commentary_chain(),
    "rb.deliverable.ma_memo": _ma_memo_chain(),
    "rb.deliverable.investor_update": _investor_update_chain(),
    "rb.deliverable.three_statement": _three_statement_chain(),
    "rb.deliverable.cfo_dashboard": _cfo_dashboard_chain(),
    "rb.deliverable.risk_register": _risk_register_chain(),
    "rb.deliverable.capex_memo": _capex_memo_chain(),
    "rb.deliverable.post_investment_review": _post_investment_review_chain(),
    "rb.deliverable.employee_all_hands": _employee_all_hands_chain(),
    "rb.deliverable.cross_functional_brief": _cross_functional_brief_chain(),
    "rb.deliverable.earnings_script": _earnings_script_chain(),
}


def all_chains() -> tuple[Chain, ...]:
    return tuple(_REGISTRY.values())


def chain_for_deliverable(rubric_id: str) -> Chain:
    if rubric_id not in _REGISTRY:
        raise KeyError(
            f"no chain registered for deliverable '{rubric_id}'. "
            f"known: {list(_REGISTRY)}"
        )
    return _REGISTRY[rubric_id]
