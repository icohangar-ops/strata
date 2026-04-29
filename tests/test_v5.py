"""v5: ERM (rb.function.risk + rb.deliverable.risk_register) and
Capital Allocation (rb.function.capital_allocation + rb.deliverable.capex_memo
+ rb.deliverable.post_investment_review)."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from strata import registry
from strata.catalog import load_catalog
from strata.deliverable.persona import get_persona
from strata.maturity import CAPABILITY_RUBRIC_IDS, MaturityAssessor
from strata.orchestrator import all_chains, chain_for_deliverable
from strata.orchestrator.director import Director
from strata.schema import CharacteristicScore

SAMPLES = Path(__file__).resolve().parents[1] / "samples"


# ---------------------------- new capability rubrics ----------------------------


@pytest.mark.parametrize("rid", ["rb.function.risk", "rb.function.capital_allocation"])
def test_new_function_rubric_loads_and_well_formed(rid):
    rb = registry.get(rid)
    assert rb.scope == "function"
    assert sum(g.weight for g in rb.groups) == pytest.approx(1.0, abs=1e-6)
    for g in rb.groups:
        assert sum(c.weight for c in g.characteristics) == pytest.approx(1.0, abs=1e-6)
    assert len(rb.groups) == 5  # five-lens shape


def test_capability_set_has_eight_function_rubrics():
    assert len(CAPABILITY_RUBRIC_IDS) == 8
    assert "rb.function.risk" in CAPABILITY_RUBRIC_IDS
    assert "rb.function.capital_allocation" in CAPABILITY_RUBRIC_IDS


# ---------------------------- new deliverable rubrics ----------------------------


@pytest.mark.parametrize(
    "rid",
    [
        "rb.deliverable.risk_register",
        "rb.deliverable.capex_memo",
        "rb.deliverable.post_investment_review",
    ],
)
def test_new_deliverable_rubric_loads(rid):
    rb = registry.get(rid)
    assert rb.scope == "deliverable"
    assert sum(g.weight for g in rb.groups) == pytest.approx(1.0, abs=1e-6)


@pytest.mark.parametrize(
    "rubric_id",
    [
        "rb.deliverable.risk_register",
        "rb.deliverable.capex_memo",
        "rb.deliverable.post_investment_review",
    ],
)
def test_persona_registered(rubric_id):
    p = get_persona(rubric_id)
    assert p.role
    assert len(p.standards) >= 3


# ---------------------------- chain registration ----------------------------


@pytest.mark.parametrize(
    "deliverable_id,chain_id",
    [
        ("rb.deliverable.risk_register",          "chain.risk_register.v1"),
        ("rb.deliverable.capex_memo",             "chain.capex_memo.v1"),
        ("rb.deliverable.post_investment_review", "chain.post_investment_review.v1"),
    ],
)
def test_chain_registered(deliverable_id, chain_id):
    ch = chain_for_deliverable(deliverable_id)
    assert ch.chain_id == chain_id


def test_chain_registry_includes_v5_chains():
    chain_ids = {c.chain_id for c in all_chains()}
    for cid in (
        "chain.risk_register.v1",
        "chain.capex_memo.v1",
        "chain.post_investment_review.v1",
    ):
        assert cid in chain_ids


# ---------------------------- catalog wiring ----------------------------


@pytest.mark.parametrize(
    "skill_id,capability,deliverable",
    [
        ("analyze.risk_register",      "rb.function.risk",                "rb.deliverable.risk_register"),
        ("plan.capex_memo",            "rb.function.capital_allocation",  "rb.deliverable.capex_memo"),
        ("plan.post_investment_review","rb.function.capital_allocation",  "rb.deliverable.post_investment_review"),
    ],
)
def test_catalog_skill_wired(skill_id, capability, deliverable):
    cat = load_catalog()
    s = cat.skill(skill_id)
    assert s.capability == capability
    assert s.deliverable_rubric == deliverable


# ---------------------------- end-to-end runs ----------------------------


@pytest.mark.parametrize(
    "chain_id,inputs_file,expected_token",
    [
        ("chain.risk_register.v1",          "risk_register_inputs.json",          "Enterprise Risk Register"),
        ("chain.capex_memo.v1",             "capex_memo_inputs.json",             "Capex Memo"),
        ("chain.post_investment_review.v1", "post_investment_review_inputs.json", "Post-Investment Review"),
    ],
)
def test_chain_runs_end_to_end(chain_id, inputs_file, expected_token):
    payload = json.loads((SAMPLES / inputs_file).read_text(encoding="utf-8"))
    run = Director(persist=False).run_chain(chain_id, payload)
    assert run.chain_id == chain_id
    assert expected_token in run.factory_result.final_draft


# ---------------------------- routing ----------------------------


def _scores(score_map: dict[str, int]) -> dict[str, list[CharacteristicScore]]:
    out: dict[str, list[CharacteristicScore]] = {}
    for rid in CAPABILITY_RUBRIC_IDS:
        rb = registry.get(rid)
        s = score_map.get(rid, 3)
        out[rid] = [
            CharacteristicScore(characteristic_id=c.id, score=s, rationale="t")
            for g in rb.groups
            for c in g.characteristics
        ]
    return out


def test_decide_routes_to_risk_register_when_risk_is_weakest():
    by_rubric = _scores({rid: 4 for rid in CAPABILITY_RUBRIC_IDS} | {"rb.function.risk": 1})
    assess = MaturityAssessor().assess(target_id="t", scores_by_rubric=by_rubric)
    decision = Director(persist=False).decide(assess)
    assert decision.weakest_capability == "rb.function.risk"
    assert decision.chain.rubric_id == "rb.deliverable.risk_register"


def test_decide_routes_to_capex_memo_when_capital_allocation_is_weakest():
    by_rubric = _scores({rid: 4 for rid in CAPABILITY_RUBRIC_IDS}
                        | {"rb.function.capital_allocation": 1})
    assess = MaturityAssessor().assess(target_id="t", scores_by_rubric=by_rubric)
    decision = Director(persist=False).decide(assess)
    assert decision.weakest_capability == "rb.function.capital_allocation"
    # Two chains target capital_allocation: capex_memo + post_investment_review.
    # Tiebreak alphabetical: capex_memo wins.
    assert decision.chain.chain_id == "chain.capex_memo.v1"
    assert "2 candidates" in decision.rationale


def test_preferred_deliverable_overrides_to_post_investment_review():
    by_rubric = _scores({rid: 4 for rid in CAPABILITY_RUBRIC_IDS}
                        | {"rb.function.capital_allocation": 1})
    assess = MaturityAssessor().assess(target_id="t", scores_by_rubric=by_rubric)
    decision = Director(persist=False).decide(
        assess, preferred_deliverable="rb.deliverable.post_investment_review"
    )
    assert decision.chain.chain_id == "chain.post_investment_review.v1"
    assert decision.preferred_signal == "rb.deliverable.post_investment_review"


# ---------------------------- sample self-assessment integration ----------------------------


def test_sample_self_assessment_loads_with_eight_capabilities():
    import yaml
    raw = yaml.safe_load((SAMPLES / "maturity_self_assessment.yaml").read_text(encoding="utf-8"))
    for rid in CAPABILITY_RUBRIC_IDS:
        assert rid in raw, f"sample missing scores for '{rid}'"
