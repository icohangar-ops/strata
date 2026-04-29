"""Coverage for the three new chains (M&A memo, investor update, 3-statement model)
and for the multi-chain-per-capability tiebreaker.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from strata import registry
from strata.deliverable.persona import get_persona
from strata.maturity.assessor import CAPABILITY_RUBRIC_IDS, MaturityAssessor
from strata.orchestrator import all_chains, chain_for_deliverable
from strata.orchestrator.director import Director
from strata.schema import CharacteristicScore

SAMPLES = Path(__file__).resolve().parents[1] / "samples"


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


# ---------------------------- registration ----------------------------


@pytest.mark.parametrize(
    "deliverable_id,chain_id",
    [
        ("rb.deliverable.ma_memo",         "chain.ma_memo.v1"),
        ("rb.deliverable.investor_update", "chain.investor_update.v1"),
        ("rb.deliverable.three_statement", "chain.three_statement.v1"),
    ],
)
def test_new_chains_are_registered(deliverable_id, chain_id):
    ch = chain_for_deliverable(deliverable_id)
    assert ch.chain_id == chain_id


def test_registry_loads_all_deliverable_rubrics():
    delivs = {r.rubric_id for r in registry.list_by_scope("deliverable")}
    assert delivs == {
        "rb.deliverable.board_pack",
        "rb.deliverable.bva_commentary",
        "rb.deliverable.ma_memo",
        "rb.deliverable.investor_update",
        "rb.deliverable.three_statement",
        "rb.deliverable.cfo_dashboard",
        "rb.deliverable.risk_register",
        "rb.deliverable.capex_memo",
        "rb.deliverable.post_investment_review",
        "rb.deliverable.employee_all_hands",
        "rb.deliverable.cross_functional_brief",
        "rb.deliverable.earnings_script",
    }


@pytest.mark.parametrize(
    "rubric_id",
    [
        "rb.deliverable.ma_memo",
        "rb.deliverable.investor_update",
        "rb.deliverable.three_statement",
    ],
)
def test_personas_registered(rubric_id):
    p = get_persona(rubric_id)
    assert p.role
    assert len(p.standards) >= 3


# ---------------------------- end-to-end run ----------------------------


@pytest.mark.parametrize(
    "chain_id,inputs_file",
    [
        ("chain.ma_memo.v1",         "ma_memo_inputs.json"),
        ("chain.investor_update.v1", "investor_update_inputs.json"),
        ("chain.three_statement.v1", "three_statement_inputs.json"),
    ],
)
def test_each_new_chain_runs_to_completion(chain_id, inputs_file):
    payload = json.loads((SAMPLES / inputs_file).read_text(encoding="utf-8"))
    run = Director(persist=False).run_chain(chain_id, payload)
    assert run.chain_id == chain_id
    assert run.factory_result.iterations >= 1
    assert run.factory_result.final_draft  # produced something


# ---------------------------- multi-chain-per-capability tiebreaker ----------------------------


def test_chains_for_forecast_capability_returns_three_statement_only():
    # After v3, M&A IC memo moved to its own capability (rb.function.ma).
    # Forecast now has only the three-statement chain.
    out = Director(persist=False).chains_for_capability("rb.function.forecast")
    chain_ids = [c.chain_id for c in out]
    assert chain_ids == ["chain.three_statement.v1"]


def test_chains_for_board_pack_capability_returns_two_sorted():
    out = Director(persist=False).chains_for_capability("rb.function.board_pack")
    chain_ids = [c.chain_id for c in out]
    assert "chain.board_pack.v1" in chain_ids
    assert "chain.investor_update.v1" in chain_ids
    assert chain_ids == sorted(chain_ids)


def test_decide_picks_alphabetically_first_chain_when_capability_has_multiple():
    # board_pack now has TWO chains: board_pack + investor_update.
    # Tiebreaker: chain.board_pack.v1 < chain.investor_update.v1 alphabetically.
    by_rubric = _scores({rid: 4 for rid in CAPABILITY_RUBRIC_IDS}
                        | {"rb.function.board_pack": 1})
    assess = MaturityAssessor().assess(target_id="t", scores_by_rubric=by_rubric)
    decision = Director(persist=False).decide(assess)
    assert decision.weakest_capability == "rb.function.board_pack"
    assert decision.chain.chain_id == "chain.board_pack.v1"
    assert "2 candidates" in decision.rationale


def test_decide_single_candidate_omits_tiebreak_note():
    # BvA weakest; only one chain targets it.
    by_rubric = _scores({
        "rb.function.close":      4,
        "rb.function.reconcile":  4,
        "rb.function.board_pack": 4,
        "rb.function.bva":        1,
        "rb.function.forecast":   4,
    })
    assess = MaturityAssessor().assess(target_id="t", scores_by_rubric=by_rubric)
    decision = Director(persist=False).decide(assess)
    assert decision.chain.chain_id == "chain.bva_commentary.v1"
    assert "candidates" not in decision.rationale
