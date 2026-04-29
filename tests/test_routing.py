"""L3 v2: dynamic Director.route() picks chain based on weakest capability."""
from __future__ import annotations

from pathlib import Path

import pytest
import yaml
from typer.testing import CliRunner

from strata import registry
from strata.cli import app
from strata.maturity.assessor import CAPABILITY_RUBRIC_IDS, MaturityAssessor
from strata.orchestrator import all_chains, chain_for_deliverable
from strata.orchestrator.director import Director
from strata.schema import CharacteristicScore

SAMPLES = Path(__file__).resolve().parents[1] / "samples"
runner = CliRunner()


def _scores_at_per_rubric(score_map: dict[str, int]) -> dict[str, list[CharacteristicScore]]:
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


def test_chain_registry_has_two_chains():
    chains = {c.chain_id for c in all_chains()}
    assert "chain.board_pack.v1" in chains
    assert "chain.bva_commentary.v1" in chains


def test_chain_for_deliverable_lookup():
    ch = chain_for_deliverable("rb.deliverable.bva_commentary")
    assert ch.rubric_id == "rb.deliverable.bva_commentary"


def test_chain_for_deliverable_unknown_raises():
    with pytest.raises(KeyError, match="no chain registered"):
        chain_for_deliverable("rb.deliverable.does_not_exist")


def test_route_picks_bva_when_bva_is_weakest_with_chain():
    # BvA is weakest among capabilities that have chains.
    by_rubric = _scores_at_per_rubric({
        "rb.function.close":      4,
        "rb.function.reconcile":  4,
        "rb.function.board_pack": 4,
        "rb.function.bva":        2,   # weakest with chain
        "rb.function.forecast":   4,
    })
    assess = MaturityAssessor().assess(target_id="acme", scores_by_rubric=by_rubric)
    director = Director(persist=False)
    decision = director.decide(assess)
    assert decision.chain.rubric_id == "rb.deliverable.bva_commentary"
    assert decision.weakest_capability == "rb.function.bva"


def test_route_picks_board_pack_when_board_pack_is_weakest():
    by_rubric = _scores_at_per_rubric({
        "rb.function.close":      4,
        "rb.function.reconcile":  4,
        "rb.function.board_pack": 1,   # weakest with chain
        "rb.function.bva":        4,
        "rb.function.forecast":   4,
    })
    assess = MaturityAssessor().assess(target_id="acme", scores_by_rubric=by_rubric)
    decision = Director(persist=False).decide(assess)
    assert decision.chain.rubric_id == "rb.deliverable.board_pack"


def test_route_raises_when_no_capability_has_chain(monkeypatch):
    # Drop all chains -> assessor result has no capability that maps to a chain.
    import strata.orchestrator.chains as chains_mod
    monkeypatch.setattr(chains_mod, "_REGISTRY", {})

    by_rubric = _scores_at_per_rubric({rid: 2 for rid in CAPABILITY_RUBRIC_IDS})
    assess = MaturityAssessor().assess(target_id="t", scores_by_rubric=by_rubric)
    with pytest.raises(RuntimeError, match="no capability"):
        Director(persist=False).decide(assess)


def test_route_runs_chain_end_to_end():
    by_rubric = _scores_at_per_rubric({
        "rb.function.bva":        2,
        "rb.function.forecast":   4,
        "rb.function.close":      4,
        "rb.function.reconcile":  4,
        "rb.function.board_pack": 4,
    })
    assess = MaturityAssessor().assess(target_id="acme", scores_by_rubric=by_rubric)
    inputs = {"company": "Acme", "period": "Mar 2026", "materiality_threshold_pct": 5}
    decision, run = Director(persist=False).route(assess, inputs)
    assert decision.chain.rubric_id == "rb.deliverable.bva_commentary"
    assert run.chain_id == "chain.bva_commentary.v1"
    assert run.factory_result.iterations >= 1


def test_run_chain_by_id_unknown_raises():
    with pytest.raises(KeyError, match="unknown chain"):
        Director(persist=False).run_chain("chain.does_not_exist", {})


def test_run_chain_by_id_executes_bva():
    inputs = {"company": "Acme", "period": "Mar 2026", "materiality_threshold_pct": 5}
    run = Director(persist=False).run_chain("chain.bva_commentary.v1", inputs)
    assert run.chain_id == "chain.bva_commentary.v1"


# ---------------------------- CLI smoke ----------------------------


def test_chains_cli_lists_both():
    result = runner.invoke(app, ["chains"])
    assert result.exit_code == 0
    assert "chain.board_pack.v1" in result.stdout
    assert "chain.bva_commentary.v1" in result.stdout


def test_run_cli_routes_dynamically(tmp_path):
    # Self-assessment that makes BvA weakest among capabilities with a chain.
    sa = tmp_path / "sa.yaml"
    payload: dict = {"target_id": "Acme"}
    for rid in CAPABILITY_RUBRIC_IDS:
        rb = registry.get(rid)
        score = 2 if rid == "rb.function.bva" else 4
        payload[rid] = {c.id: score for g in rb.groups for c in g.characteristics}
    sa.write_text(yaml.safe_dump(payload), encoding="utf-8")

    result = runner.invoke(app, [
        "run",
        "--self-assessment", str(sa),
        "--inputs", str(SAMPLES / "bva_inputs.json"),
    ])
    assert result.exit_code == 0, result.stdout
    assert "chain.bva_commentary.v1" in result.stdout
    assert "Routing decision" in result.stdout
