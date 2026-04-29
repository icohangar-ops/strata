"""L1: maturity assessor produces a heatmap and reuses the L5 schema."""
from __future__ import annotations

import yaml

from strata import registry
from strata.maturity.assessor import CAPABILITY_RUBRIC_IDS, MaturityAssessor
from strata.schema import CharacteristicScore


def _scores_at(rid: str, score: int) -> list[CharacteristicScore]:
    rb = registry.get(rid)
    return [
        CharacteristicScore(characteristic_id=c.id, score=score, rationale="t")
        for g in rb.groups
        for c in g.characteristics
    ]


def test_uniform_floor_gives_25_pct():
    import pytest as _pytest
    assessor = MaturityAssessor()
    by_rubric = {rid: _scores_at(rid, score=1) for rid in CAPABILITY_RUBRIC_IDS}
    res = assessor.assess(target_id="acme", scores_by_rubric=by_rubric)
    for cap in res.capabilities:
        assert cap.score_pct == _pytest.approx(25.0, abs=1e-6)
    assert res.overall_pct == _pytest.approx(25.0, abs=1e-6)


def test_uniform_ceiling_gives_100_pct():
    import pytest as _pytest
    assessor = MaturityAssessor()
    by_rubric = {rid: _scores_at(rid, score=4) for rid in CAPABILITY_RUBRIC_IDS}
    res = assessor.assess(target_id="acme", scores_by_rubric=by_rubric)
    assert res.overall_pct == _pytest.approx(100.0, abs=1e-6)


def test_sample_self_assessment_loads_and_scores():
    sample = (
        registry.RUBRICS_DIR.parents[2] / "samples" / "maturity_self_assessment.yaml"
    )
    raw = yaml.safe_load(sample.read_text(encoding="utf-8"))
    raw.pop("target_id")
    by_rubric = {
        rid: [
            CharacteristicScore(characteristic_id=cid, score=int(s), rationale="self")
            for cid, s in raw[rid].items()
        ]
        for rid in CAPABILITY_RUBRIC_IDS
    }
    res = MaturityAssessor().assess(target_id="acme", scores_by_rubric=by_rubric)
    # sample is mid-range; expect 30-65% overall
    assert 30.0 <= res.overall_pct <= 65.0
    # heatmap is sorted ascending
    pcts = [p for _, p in res.heatmap()]
    assert pcts == sorted(pcts)
