"""L5: validate every YAML rubric loads, weights sum to 1.0, and scoring math is correct."""
from __future__ import annotations

import pytest

from strata import registry
from strata.schema import (
    Attribute,
    Characteristic,
    CharacteristicScore,
    Group,
    Rubric,
    RubricScoreReport,
)


def _attrs() -> tuple[Attribute, ...]:
    return (
        Attribute(level="Mature",     score=4, anchor="exemplary"),
        Attribute(level="Developing", score=3, anchor="solid"),
        Attribute(level="Emerging",   score=2, anchor="patchy"),
        Attribute(level="Absent",     score=1, anchor="missing"),
    )


def _good_rubric() -> Rubric:
    chars = (
        Characteristic(id="c1", name="C1", weight=0.50, attributes=_attrs()),
        Characteristic(id="c2", name="C2", weight=0.50, attributes=_attrs()),
    )
    g1 = Group(id="g1", name="G1", weight=0.50, characteristics=chars)
    g2 = Group(id="g2", name="G2", weight=0.50, characteristics=chars)
    return Rubric(
        rubric_id="rb.deliverable.test",
        scope="deliverable",
        name="Test",
        version=1,
        groups=(g1, g2),
    )


def test_group_weights_must_sum_to_one():
    chars = (
        Characteristic(id="c1", name="C1", weight=0.50, attributes=_attrs()),
        Characteristic(id="c2", name="C2", weight=0.50, attributes=_attrs()),
    )
    g1 = Group(id="g1", name="G1", weight=0.50, characteristics=chars)
    g2 = Group(id="g2", name="G2", weight=0.40, characteristics=chars)
    with pytest.raises(ValueError, match="group weights"):
        Rubric(
            rubric_id="rb.deliverable.bad",
            scope="deliverable",
            name="Bad",
            version=1,
            groups=(g1, g2),
        )


def test_characteristic_weights_must_sum_to_one():
    bad_chars = (
        Characteristic(id="c1", name="C1", weight=0.30, attributes=_attrs()),
        Characteristic(id="c2", name="C2", weight=0.30, attributes=_attrs()),
    )
    with pytest.raises(ValueError, match="characteristic weights"):
        Group(id="g1", name="G1", weight=0.50, characteristics=bad_chars)


def test_attribute_scores_unique():
    bad = (
        Attribute(level="A", score=4, anchor="aaaa"),
        Attribute(level="B", score=4, anchor="bbbb"),
    )
    with pytest.raises(ValueError, match="unique"):
        Characteristic(id="c", name="C", weight=0.50, attributes=bad)


def test_compute_normalized_score_perfect():
    rb = _good_rubric()
    perfect = [
        CharacteristicScore(characteristic_id=c.id, score=4, rationale="x")
        for g in rb.groups
        for c in g.characteristics
    ]
    rep = RubricScoreReport.compute(rubric=rb, target_id="t", scores=perfect, pass_threshold_pct=70)
    assert rep.normalized_pct == pytest.approx(100.0)
    assert rep.passed is True


def test_compute_normalized_score_floor():
    rb = _good_rubric()
    floor = [
        CharacteristicScore(characteristic_id=c.id, score=1, rationale="x")
        for g in rb.groups
        for c in g.characteristics
    ]
    rep = RubricScoreReport.compute(rubric=rb, target_id="t", scores=floor, pass_threshold_pct=70)
    # floor score = 1, max = 4 -> 25%
    assert rep.normalized_pct == pytest.approx(25.0)
    assert rep.passed is False


def test_all_yaml_rubrics_load():
    rs = registry.load_all()
    expected = {
        "rb.deliverable.board_pack",
        "rb.function.close",
        "rb.function.reconcile",
        "rb.function.board_pack",
        "rb.function.bva",
        "rb.function.forecast",
    }
    assert expected.issubset(rs.keys())


def test_yaml_rubrics_have_well_formed_weights():
    for rb in registry.load_all().values():
        assert sum(g.weight for g in rb.groups) == pytest.approx(1.0, abs=1e-6)
        for g in rb.groups:
            assert sum(c.weight for c in g.characteristics) == pytest.approx(1.0, abs=1e-6)
