"""v6: full Tool 3 deliverable parity + 90-day roadmap generator."""
from __future__ import annotations

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from strata import registry
from strata.catalog import load_catalog
from strata.cli import app
from strata.deliverable.persona import get_persona
from strata.maturity import (
    CAPABILITY_RUBRIC_IDS,
    MaturityAssessor,
    Roadmap,
    plan_90_days,
)
from strata.orchestrator import all_chains, chain_for_deliverable
from strata.orchestrator.director import Director
from strata.schema import CharacteristicScore

SAMPLES = Path(__file__).resolve().parents[1] / "samples"
runner = CliRunner()


_NEW_DELIVERABLES = (
    "rb.deliverable.employee_all_hands",
    "rb.deliverable.cross_functional_brief",
    "rb.deliverable.earnings_script",
)
_NEW_CHAINS = (
    "chain.employee_all_hands.v1",
    "chain.cross_functional_brief.v1",
    "chain.earnings_script.v1",
)


# ---------------------------- new deliverables ----------------------------


@pytest.mark.parametrize("rid", _NEW_DELIVERABLES)
def test_new_deliverable_rubric_loads(rid):
    rb = registry.get(rid)
    assert rb.scope == "deliverable"
    assert sum(g.weight for g in rb.groups) == pytest.approx(1.0, abs=1e-6)


@pytest.mark.parametrize("rid", _NEW_DELIVERABLES)
def test_persona_registered(rid):
    p = get_persona(rid)
    assert p.role and len(p.standards) >= 3


@pytest.mark.parametrize(
    "deliverable_id,chain_id",
    list(zip(_NEW_DELIVERABLES, _NEW_CHAINS, strict=True)),
)
def test_chain_registered(deliverable_id, chain_id):
    assert chain_for_deliverable(deliverable_id).chain_id == chain_id


def test_chain_registry_has_twelve_chains():
    chain_ids = {c.chain_id for c in all_chains()}
    for cid in _NEW_CHAINS:
        assert cid in chain_ids
    assert len(chain_ids) == 12


@pytest.mark.parametrize(
    "skill_id,deliverable",
    [
        ("present.employee_all_hands",     "rb.deliverable.employee_all_hands"),
        ("present.cross_functional_brief", "rb.deliverable.cross_functional_brief"),
        ("present.earnings_script",        "rb.deliverable.earnings_script"),
    ],
)
def test_catalog_skill_wired(skill_id, deliverable):
    cat = load_catalog()
    s = cat.skill(skill_id)
    assert s.deliverable_rubric == deliverable
    assert s.capability == "rb.competency.stakeholder"


@pytest.mark.parametrize(
    "chain_id,inputs_file,expected_token",
    [
        ("chain.employee_all_hands.v1",     "employee_all_hands_inputs.json",     "All-Hands Finance Segment"),
        ("chain.cross_functional_brief.v1", "cross_functional_brief_inputs.json", "Bi-Weekly Brief"),
        ("chain.earnings_script.v1",        "earnings_script_inputs.json",        "Earnings Call Script"),
    ],
)
def test_chain_runs_end_to_end(chain_id, inputs_file, expected_token):
    payload = json.loads((SAMPLES / inputs_file).read_text(encoding="utf-8"))
    run = Director(persist=False).run_chain(chain_id, payload)
    assert run.chain_id == chain_id
    assert expected_token in run.factory_result.final_draft


# ---------------------------- 90-day roadmap ----------------------------


def _scores_at_pct(low_pct_capabilities: dict[str, int]) -> dict[str, list[CharacteristicScore]]:
    """Build scores where listed capabilities are weak, rest are strong."""
    out: dict[str, list[CharacteristicScore]] = {}
    for rid in CAPABILITY_RUBRIC_IDS:
        rb = registry.get(rid)
        score = low_pct_capabilities.get(rid, 4)
        out[rid] = [
            CharacteristicScore(characteristic_id=c.id, score=score, rationale="t")
            for g in rb.groups
            for c in g.characteristics
        ]
    return out


def test_plan_90_days_returns_three_phases():
    scores = _scores_at_pct({"rb.function.risk": 1, "rb.function.bva": 1})
    assess = MaturityAssessor().assess(target_id="t", scores_by_rubric=scores)
    rmap = plan_90_days(assess)
    assert isinstance(rmap, Roadmap)
    assert len(rmap.phases) == 3
    labels = [p.label for p in rmap.phases]
    assert labels == ["Days 1-30", "Days 31-60", "Days 61-90"]


def test_plan_90_days_phase1_pilots_weakest_with_chain():
    scores = _scores_at_pct({"rb.function.risk": 1})
    assess = MaturityAssessor().assess(target_id="t", scores_by_rubric=scores)
    rmap = plan_90_days(assess)
    pilot = rmap.phases[0].actions[-1]  # last phase-1 action is the pilot
    assert pilot.chain_id == "chain.risk_register.v1"
    assert pilot.capability_id == "rb.function.risk"


def test_plan_90_days_phase2_scales_next_weakest():
    scores = _scores_at_pct({
        "rb.function.risk": 1,
        "rb.function.bva":  1,
        "rb.function.capital_allocation": 1,
    })
    assess = MaturityAssessor().assess(target_id="t", scores_by_rubric=scores)
    rmap = plan_90_days(assess)
    phase2_chains = {a.chain_id for a in rmap.phases[1].actions if a.chain_id}
    # All three are tied at 25%; alphabetical tiebreak makes bva the pilot.
    # Phase 2 should include the next two: capital_allocation (capex_memo) + risk.
    assert "chain.capex_memo.v1" in phase2_chains
    assert "chain.risk_register.v1" in phase2_chains
    # The pilot's own chain is NOT in phase 2.
    assert "chain.bva_commentary.v1" not in phase2_chains


def test_plan_90_days_phase3_includes_capital_council_review():
    scores = _scores_at_pct({"rb.function.risk": 1})
    assess = MaturityAssessor().assess(target_id="t", scores_by_rubric=scores)
    rmap = plan_90_days(assess)
    phase3_actions = [a.action for a in rmap.phases[2].actions]
    assert any("capital council" in a.lower() for a in phase3_actions)


def test_director_exposes_plan_90_days():
    scores = _scores_at_pct({"rb.function.risk": 1})
    assess = MaturityAssessor().assess(target_id="t", scores_by_rubric=scores)
    rmap = Director(persist=False).plan_90_days(assess)
    assert isinstance(rmap, Roadmap)


# ---------------------------- CLI ----------------------------


def test_roadmap_cli_renders_three_phases():
    result = runner.invoke(app, [
        "roadmap",
        "--self-assessment", str(SAMPLES / "maturity_self_assessment.yaml"),
    ])
    assert result.exit_code == 0, result.stdout
    assert "Days 1-30" in result.stdout
    assert "Days 31-60" in result.stdout
    assert "Days 61-90" in result.stdout
    assert "Baseline & Quick Wins" in result.stdout


def test_roadmap_cli_competency_axis():
    result = runner.invoke(app, [
        "roadmap",
        "--self-assessment", str(SAMPLES / "maturity_self_assessment.yaml"),
        "--axis", "competency",
    ])
    assert result.exit_code == 0, result.stdout
    assert "Days 1-30" in result.stdout
