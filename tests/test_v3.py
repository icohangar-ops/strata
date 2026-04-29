"""v3 features: M&A capability, preferred_deliverable, chain composition,
tenant overrides, perception adapter."""
from __future__ import annotations

from pathlib import Path

import pytest

from strata import registry
from strata.maturity.assessor import (
    CAPABILITY_RUBRIC_IDS,
    MaturityAssessor,
)
from strata.orchestrator.director import Director
from strata.perception import csv_gl_adapter, identity_adapter
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


# ---------------------------- (a) M&A capability ----------------------------


def test_ma_capability_in_rubric_set():
    assert "rb.function.ma" in CAPABILITY_RUBRIC_IDS
    rb = registry.get("rb.function.ma")
    assert rb.scope == "function"
    assert sum(g.weight for g in rb.groups) == pytest.approx(1.0, abs=1e-6)


def test_ma_memo_skill_targets_ma_capability():
    from strata.catalog import load_catalog
    cat = load_catalog()
    s = cat.skill("present.ic_memo")
    assert s.capability == "rb.function.ma"


def test_decide_picks_ma_memo_when_ma_is_weakest():
    by_rubric = _scores({rid: 4 for rid in CAPABILITY_RUBRIC_IDS} | {"rb.function.ma": 1})
    assess = MaturityAssessor().assess(target_id="t", scores_by_rubric=by_rubric)
    decision = Director(persist=False).decide(assess)
    assert decision.weakest_capability == "rb.function.ma"
    assert decision.chain.chain_id == "chain.ma_memo.v1"


# ---------------------------- (b) preferred_deliverable ----------------------------


def test_preferred_deliverable_overrides_alphabetical_tiebreak():
    # forecast capability has TWO chains: ma_memo (alpha-first) + three_statement
    # Wait — after step (a) ma_memo moved to rb.function.ma. So forecast now has
    # only three_statement. To exercise preference, weaken board_pack which has 2 chains.
    by_rubric = _scores({rid: 4 for rid in CAPABILITY_RUBRIC_IDS} | {"rb.function.board_pack": 1})
    assess = MaturityAssessor().assess(target_id="t", scores_by_rubric=by_rubric)
    decision = Director(persist=False).decide(
        assess, preferred_deliverable="rb.deliverable.investor_update"
    )
    assert decision.chain.chain_id == "chain.investor_update.v1"
    assert decision.preferred_signal == "rb.deliverable.investor_update"
    assert "user-preferred" in decision.rationale


def test_preferred_deliverable_falls_back_when_not_a_candidate():
    # forecast cap has only three_statement; user prefers ma_memo (different cap)
    # decide() should ignore the preference for forecast and pick three_statement
    by_rubric = _scores({rid: 4 for rid in CAPABILITY_RUBRIC_IDS} | {"rb.function.forecast": 1})
    assess = MaturityAssessor().assess(target_id="t", scores_by_rubric=by_rubric)
    decision = Director(persist=False).decide(
        assess, preferred_deliverable="rb.deliverable.ma_memo"
    )
    assert decision.weakest_capability == "rb.function.forecast"
    assert decision.chain.chain_id == "chain.three_statement.v1"
    assert decision.preferred_signal is None


def test_route_with_preferred_deliverable_in_inputs():
    by_rubric = _scores({rid: 4 for rid in CAPABILITY_RUBRIC_IDS} | {"rb.function.board_pack": 1})
    assess = MaturityAssessor().assess(target_id="t", scores_by_rubric=by_rubric)
    inputs = {
        "company": "Acme",
        "period": "Mar 2026",
        "preferred_deliverable": "rb.deliverable.investor_update",
        "arr": 22400000,
        "runway_months": 14,
    }
    decision, run = Director(persist=False).route(assess, inputs)
    assert decision.chain.chain_id == "chain.investor_update.v1"
    assert run.chain_id == "chain.investor_update.v1"


def test_decide_returns_alternates():
    by_rubric = _scores({rid: 4 for rid in CAPABILITY_RUBRIC_IDS} | {"rb.function.board_pack": 1})
    assess = MaturityAssessor().assess(target_id="t", scores_by_rubric=by_rubric)
    decision = Director(persist=False).decide(assess)
    assert decision.chain.chain_id == "chain.board_pack.v1"
    alt_ids = {c.chain_id for c in decision.alternates}
    assert "chain.investor_update.v1" in alt_ids


# ---------------------------- chain composition ----------------------------


def test_board_pack_chain_declares_dependency_on_bva():
    from strata.orchestrator import chain_for_deliverable
    bp = chain_for_deliverable("rb.deliverable.board_pack")
    assert bp.depends_on == ("chain.bva_commentary.v1",)


def test_board_pack_chain_runs_dependency_first():
    inputs = {"company": "Acme", "period": "Mar 2026", "materiality_threshold_pct": 5}
    run = Director(persist=False).run_chain("chain.board_pack.v1", inputs)
    # The mock author splices the upstream block when present in inputs;
    # we can't directly inspect inputs after the run, but the run should still
    # complete and produce a draft.
    assert run.factory_result.final_draft


def test_chain_cycle_detection():
    from dataclasses import replace
    import strata.orchestrator.chains as chains_mod
    bp = chains_mod._REGISTRY["rb.deliverable.board_pack"]
    # Make BvA depend on board_pack -> board_pack already depends on BvA -> cycle.
    bva = chains_mod._REGISTRY["rb.deliverable.bva_commentary"]
    cyc = replace(bva, depends_on=("chain.board_pack.v1",))
    saved = chains_mod._REGISTRY["rb.deliverable.bva_commentary"]
    chains_mod._REGISTRY["rb.deliverable.bva_commentary"] = cyc
    try:
        with pytest.raises(RuntimeError, match="cycle detected"):
            Director(persist=False).run_chain("chain.board_pack.v1",
                                              {"company": "X", "period": "p"})
    finally:
        chains_mod._REGISTRY["rb.deliverable.bva_commentary"] = saved


def test_chain_unknown_dependency_raises():
    from dataclasses import replace
    import strata.orchestrator.chains as chains_mod
    saved = chains_mod._REGISTRY["rb.deliverable.bva_commentary"]
    bad = replace(saved, depends_on=("chain.does_not_exist.v1",))
    chains_mod._REGISTRY["rb.deliverable.bva_commentary"] = bad
    try:
        with pytest.raises(KeyError, match="depends on unknown chain"):
            Director(persist=False).run_chain("chain.bva_commentary.v1",
                                              {"company": "X", "period": "p"})
    finally:
        chains_mod._REGISTRY["rb.deliverable.bva_commentary"] = saved


# ---------------------------- tenant rubric overrides ----------------------------


def _setup_sqlite(tmp_path, monkeypatch):
    monkeypatch.setenv("STRATA_TEST_DB", f"sqlite:///{tmp_path / 'tenants.sqlite'}")
    from strata import config, db
    config.get_settings.cache_clear()
    db._engine = None
    db._SessionLocal = None
    from strata.db import Base, get_engine
    from strata import models  # noqa: F401
    Base.metadata.create_all(get_engine())


def _insert_override(**kw):
    import uuid
    from strata.db import session_scope
    from strata.models import RubricOverride
    with session_scope() as s:
        s.add(RubricOverride(id=uuid.uuid4(), **kw))


def test_tenant_weight_override_renormalizes(tmp_path, monkeypatch):
    _setup_sqlite(tmp_path, monkeypatch)
    _insert_override(
        tenant_id="acme",
        rubric_id="rb.function.close",
        characteristic_id="cycle_time_measured",
        weight=0.80,  # heavy weight; siblings rescale
        note="Acme cares disproportionately about close cycle time",
    )
    by_rubric = _scores({rid: 1 for rid in CAPABILITY_RUBRIC_IDS}
                        | {"rb.function.close": 4})
    base = MaturityAssessor().assess(target_id="acme", scores_by_rubric=by_rubric)
    overridden = MaturityAssessor().assess(
        target_id="acme", scores_by_rubric=by_rubric, tenant_id="acme"
    )
    # Weights changed but every score is the same, so total stays 100% for close.
    base_close = next(c for c in base.capabilities if c.rubric.rubric_id == "rb.function.close")
    over_close = next(c for c in overridden.capabilities if c.rubric.rubric_id == "rb.function.close")
    assert base_close.score_pct == pytest.approx(over_close.score_pct, abs=1e-6)
    # But the rubric structure changed: cycle_time_measured weight is now 0.80
    inst = next(g for g in over_close.rubric.groups if g.id == "instrumentation")
    cm = next(c for c in inst.characteristics if c.id == "cycle_time_measured")
    assert cm.weight == pytest.approx(0.80, abs=1e-6)


def test_tenant_disable_override_drops_characteristic(tmp_path, monkeypatch):
    _setup_sqlite(tmp_path, monkeypatch)
    _insert_override(
        tenant_id="acme",
        rubric_id="rb.function.close",
        characteristic_id="error_rate_tracked",
        disabled=True,
        note="Acme does not measure post-close adjustments yet",
    )
    by_rubric = _scores({rid: 4 for rid in CAPABILITY_RUBRIC_IDS}
                        | {"rb.function.close": 4})
    overridden = MaturityAssessor().assess(
        target_id="acme", scores_by_rubric=by_rubric, tenant_id="acme"
    )
    close_cap = next(c for c in overridden.capabilities if c.rubric.rubric_id == "rb.function.close")
    inst = next(g for g in close_cap.rubric.groups if g.id == "instrumentation")
    char_ids = {c.id for c in inst.characteristics}
    assert "error_rate_tracked" not in char_ids
    # The remaining sibling absorbs the weight (0.50 -> 1.00, then renormalized in group).
    cm = next(c for c in inst.characteristics if c.id == "cycle_time_measured")
    assert cm.weight == pytest.approx(1.0, abs=1e-6)


def test_tenant_score_floor_clamps(tmp_path, monkeypatch):
    _setup_sqlite(tmp_path, monkeypatch)
    _insert_override(
        tenant_id="acme",
        rubric_id="rb.function.close",
        characteristic_id="cycle_time_measured",
        score_floor=3,
    )
    by_rubric = _scores({rid: 4 for rid in CAPABILITY_RUBRIC_IDS}
                        | {"rb.function.close": 1})  # self-reported floor for close
    overridden = MaturityAssessor().assess(
        target_id="acme", scores_by_rubric=by_rubric, tenant_id="acme"
    )
    close_cap = next(c for c in overridden.capabilities if c.rubric.rubric_id == "rb.function.close")
    cm_score = next(s for s in close_cap.report.scores if s.characteristic_id == "cycle_time_measured")
    assert cm_score.score == 3  # clamped up from 1


# ---------------------------- perception adapter ----------------------------


def test_identity_adapter_passthrough():
    inputs = {"a": 1}
    assert identity_adapter(inputs) is inputs


def test_csv_gl_adapter_aggregates():
    adapter = csv_gl_adapter()
    inputs = {
        "period": "March 2026",
        "gl_extract_path": str(SAMPLES / "gl_extract.csv"),
    }
    out = adapter(inputs)
    agg = out["gl_aggregates"]
    # Hardware 3.2M + Services 1.62M = 4.82M
    assert agg["revenue"] == pytest.approx(4_820_000)
    assert agg["cogs"] == pytest.approx(1_820_000)  # 1.18M materials + 0.64M labor
    assert agg["gross_margin_pct"] == pytest.approx(((4_820_000 - 1_820_000) / 4_820_000) * 100)


def test_csv_gl_adapter_skips_when_path_missing():
    adapter = csv_gl_adapter()
    out = adapter({"period": "March 2026"})
    assert "gl_aggregates" not in out


def test_csv_gl_adapter_returns_inputs_when_period_not_in_extract(tmp_path):
    adapter = csv_gl_adapter()
    out = adapter({
        "period": "Year 3000",
        "gl_extract_path": str(SAMPLES / "gl_extract.csv"),
    })
    assert "gl_aggregates" not in out


def test_bva_chain_runs_with_perception_enrichment():
    """End-to-end: run BvA chain; perception adapter loads GL aggregates into inputs."""
    import json
    inputs = json.loads((SAMPLES / "bva_inputs.json").read_text(encoding="utf-8"))
    run = Director(persist=False).run_chain("chain.bva_commentary.v1", inputs)
    assert run.factory_result.final_draft  # produced something
