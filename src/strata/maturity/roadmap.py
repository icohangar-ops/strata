"""90-day roadmap generator.

Converts an AssessmentResult into a phased plan modeled on the Modern CFO
Handbook's three phases:

  Days  1-30 (Baseline & Quick Wins): assessment + dashboard + 1 pilot on the
                                      single weakest capability with a chain
  Days 31-60 (Scale & Pilot)        : address the next 2-3 weakest capabilities
                                      with chain-driven deliverables
  Days 61-90 (Embed & Measure)      : embed automation, formalize ERM if weak,
                                      run first capital council review

This is *analytic*, not graded — the roadmap is an action list, not a
deliverable. It can be combined with a deliverable factory by feeding
roadmap actions as inputs.preferred_deliverable to Director.route().
"""
from __future__ import annotations

from dataclasses import dataclass

from strata.maturity.assessor import AssessmentResult, CapabilitySnapshot


@dataclass(frozen=True)
class RoadmapAction:
    capability_id: str
    capability_name: str
    score_pct: float
    action: str
    chain_id: str | None = None  # if a chain can drive this action
    deliverable_rubric_id: str | None = None


@dataclass(frozen=True)
class RoadmapPhase:
    label: str            # e.g. "Days 1-30"
    intent: str           # e.g. "Baseline & Quick Wins"
    actions: tuple[RoadmapAction, ...]


@dataclass(frozen=True)
class Roadmap:
    target_id: str
    axis: str             # "function" | "competency"
    overall_pct: float
    phases: tuple[RoadmapPhase, ...]


_BASELINE_ACTIONS = (
    "Run dual-axis assessment (function + competency)",
    "Build the one-page CFO value-creation dashboard",
    "Identify top 3 capability gaps and confirm with peer execs",
)


_EMBED_ACTIONS_GENERIC = (
    "Tighten leading indicators: forecast accuracy, close cycle days, decision speed",
    "Tighten lagging indicators: ROIC vs WACC spread, EVA, stakeholder eNPS",
    "Schedule next quarterly competency review",
)


def plan_90_days(assessment: AssessmentResult, axis: str = "function") -> Roadmap:
    """Produces a 90-day roadmap from an assessment.

    - Phase 1 (1-30): always includes the three handbook 'baseline' actions, plus
      a single pilot on the *weakest* capability for which a chain exists.
    - Phase 2 (31-60): one chain-driven action per capability for the
      next-weakest 2-3 capabilities below the 70% mature threshold.
    - Phase 3 (61-90): embed/measure actions, plus run a first review on the
      strongest scale-ready capability if any.
    """
    # Lazy import to break circular dep: orchestrator.director -> maturity.assessor
    # -> maturity.__init__ -> roadmap -> Director would deadlock.
    from strata.orchestrator.director import Director

    director = Director(persist=False)
    cap_to_chains = director._capability_chain_index()  # noqa: SLF001 — clean adapter

    # Sort capabilities weakest-first
    ranked: list[CapabilitySnapshot] = sorted(
        assessment.capabilities, key=lambda c: (c.score_pct, c.rubric.rubric_id)
    )

    # Phase 1
    phase1: list[RoadmapAction] = [
        RoadmapAction(
            capability_id="meta",
            capability_name="Strata baseline",
            score_pct=assessment.overall_pct,
            action=a,
        )
        for a in _BASELINE_ACTIONS
    ]
    pilot = _first_with_chain(ranked, cap_to_chains)
    if pilot is not None:
        snap, chain = pilot
        phase1.append(
            RoadmapAction(
                capability_id=snap.rubric.rubric_id,
                capability_name=snap.rubric.name,
                score_pct=snap.score_pct,
                action=f"Pilot one chain-driven deliverable: {chain.chain_id}",
                chain_id=chain.chain_id,
                deliverable_rubric_id=chain.rubric_id,
            )
        )

    # Phase 2: next 2-3 weakest with chains, skipping the pilot
    pilot_id = pilot[0].rubric.rubric_id if pilot else None
    phase2: list[RoadmapAction] = []
    for snap in ranked:
        if snap.rubric.rubric_id == pilot_id:
            continue
        if snap.score_pct >= 70.0:
            continue
        if snap.rubric.rubric_id not in cap_to_chains:
            continue
        chain = cap_to_chains[snap.rubric.rubric_id][0]
        phase2.append(
            RoadmapAction(
                capability_id=snap.rubric.rubric_id,
                capability_name=snap.rubric.name,
                score_pct=snap.score_pct,
                action=f"Scale chain-driven deliverable: {chain.chain_id}",
                chain_id=chain.chain_id,
                deliverable_rubric_id=chain.rubric_id,
            )
        )
        if len(phase2) >= 3:
            break

    # Phase 3: embed/measure
    phase3: list[RoadmapAction] = [
        RoadmapAction(
            capability_id="meta",
            capability_name="Embed & Measure",
            score_pct=assessment.overall_pct,
            action=a,
        )
        for a in _EMBED_ACTIONS_GENERIC
    ]
    if "rb.function.capital_allocation" in {c.rubric.rubric_id for c in ranked}:
        phase3.append(
            RoadmapAction(
                capability_id="rb.function.capital_allocation",
                capability_name="Capital Allocation Discipline",
                score_pct=next(
                    c.score_pct for c in ranked
                    if c.rubric.rubric_id == "rb.function.capital_allocation"
                ),
                action="Run first capital council review of in-flight investments",
            )
        )

    return Roadmap(
        target_id=assessment.target_id,
        axis=axis,
        overall_pct=assessment.overall_pct,
        phases=(
            RoadmapPhase(label="Days 1-30",  intent="Baseline & Quick Wins", actions=tuple(phase1)),
            RoadmapPhase(label="Days 31-60", intent="Scale & Pilot",         actions=tuple(phase2)),
            RoadmapPhase(label="Days 61-90", intent="Embed & Measure",       actions=tuple(phase3)),
        ),
    )


def _first_with_chain(ranked, cap_to_chains):
    for snap in ranked:
        if snap.rubric.rubric_id in cap_to_chains:
            return snap, cap_to_chains[snap.rubric.rubric_id][0]
    return None
