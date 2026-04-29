"""L4: deliverable factory iterates and grades against the board-pack rubric."""
from __future__ import annotations

from strata import registry
from strata.deliverable.board_pack import mock_author
from strata.deliverable.factory import DeliverableFactory
from strata.deliverable.grader import Grader, MockLLM


def test_factory_runs_loop_and_returns_history():
    rb = registry.get("rb.deliverable.board_pack")
    factory = DeliverableFactory(
        rubric=rb,
        author=mock_author,
        grader=Grader(llm=MockLLM(base_score=2), pass_threshold_pct=60.0),
        max_iterations=3,
    )
    inputs = {"company": "Acme", "period": "Mar 2026", "revenue_actual": 100, "revenue_budget": 110}
    res = factory.run(target_id="acme::mar2026", inputs=inputs)
    assert res.iterations >= 1
    assert res.iterations <= 3
    assert len(res.history) == res.iterations
    assert res.final_draft.startswith("# Acme")


def test_factory_passes_at_high_base_score():
    rb = registry.get("rb.deliverable.board_pack")
    factory = DeliverableFactory(
        rubric=rb,
        author=mock_author,
        grader=Grader(llm=MockLLM(base_score=4), pass_threshold_pct=60.0),
        max_iterations=2,
    )
    res = factory.run(target_id="t", inputs={"company": "X", "period": "p"})
    assert res.passed is True


def test_factory_fails_at_low_base_score_within_max_iter():
    rb = registry.get("rb.deliverable.board_pack")
    factory = DeliverableFactory(
        rubric=rb,
        author=mock_author,
        grader=Grader(llm=MockLLM(base_score=1), pass_threshold_pct=95.0),
        max_iterations=2,
    )
    res = factory.run(target_id="t", inputs={"company": "X", "period": "p"})
    assert res.passed is False
    assert res.iterations == 2
