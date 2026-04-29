"""Targeted tests for previously-uncovered real-logic branches.

These exist to prove behavior on error paths, helper functions, and
optional-input branches that the happy-path tests never hit.
"""
from __future__ import annotations

import pytest

from strata import registry
from strata.catalog import load_catalog
from strata.db import session_scope
from strata.deliverable.board_pack import build_author_prompt, mock_author
from strata.deliverable.factory import DeliverableFactory
from strata.deliverable.grader import (
    GRADER_SYSTEM,
    Grader,
    MockLLM,
    _extract_block,
    _keywords,
    _parse_scores,
)
from strata.deliverable.persona import get_persona
from strata.maturity.assessor import CAPABILITY_RUBRIC_IDS, MaturityAssessor
from strata.orchestrator.director import Director
from strata.schema import (
    Attribute,
    Characteristic,
    CharacteristicScore,
    Group,
    Rubric,
    RubricScoreReport,
)


# ---------------------------- grader internals ----------------------------


def test_keywords_returns_only_long_lowercase_tokens():
    out = _keywords("Numbers tie to ledger to the dollar")
    assert "numbers" in out
    assert "ledger" in out
    assert all(len(w) >= 5 for w in out)
    assert len(out) <= 4


def test_extract_block_raises_when_missing():
    with pytest.raises(ValueError, match="missing <DRAFT>"):
        _extract_block("no tags here", "DRAFT")


def test_parse_scores_handles_markdown_fenced_json():
    fenced = """Here is the result:
    ```json
    {"scores": [{"characteristic_id": "c1", "score": 3, "rationale": "ok"}]}
    ```
    """
    out = _parse_scores(fenced)
    assert out[0].characteristic_id == "c1"
    assert out[0].score == 3


def test_parse_scores_handles_prose_wrapped_json():
    raw = 'Sure! {"scores": [{"characteristic_id":"x","score":2,"rationale":"y"}]} done'
    out = _parse_scores(raw)
    assert out[0].score == 2


def test_grader_system_prompt_is_nonempty():
    assert "rubric grader" in GRADER_SYSTEM.lower()


def test_mock_llm_returns_valid_json_for_real_rubric():
    rb = registry.get("rb.deliverable.board_pack")
    g = Grader(llm=MockLLM(base_score=2), pass_threshold_pct=70.0)
    result = g.grade(rb, draft="numbers tie to ledger; variance attributed to driver", target_id="t")
    assert len(result.report.scores) == sum(len(g.characteristics) for g in rb.groups)


# ---------------------------- author prompt feedback branch ----------------------------


def test_build_author_prompt_includes_feedback_when_history_present():
    rb = registry.get("rb.deliverable.board_pack")
    persona = get_persona(rb.rubric_id)
    factory = DeliverableFactory(
        rubric=rb,
        author=mock_author,
        grader=Grader(llm=MockLLM(base_score=1), pass_threshold_pct=99.0),
        max_iterations=1,
    )
    res = factory.run(target_id="t", inputs={"company": "X", "period": "p"})
    prompt = build_author_prompt(persona, rb, {"company": "X"}, list(res.history))
    assert "PRIOR-DRAFT FEEDBACK" in prompt
    assert "PRIOR NORMALIZED SCORE" in prompt


def test_build_author_prompt_omits_feedback_when_history_empty():
    rb = registry.get("rb.deliverable.board_pack")
    persona = get_persona(rb.rubric_id)
    prompt = build_author_prompt(persona, rb, {"company": "X", "period": "p"}, history=[])
    assert "PRIOR-DRAFT FEEDBACK" not in prompt


# ---------------------------- persona ----------------------------


def test_persona_unknown_rubric_raises():
    with pytest.raises(KeyError, match="no persona registered"):
        get_persona("rb.deliverable.does_not_exist")


# ---------------------------- assessor ----------------------------


def test_assess_missing_scores_raises():
    assessor = MaturityAssessor()
    with pytest.raises(ValueError, match="missing scores"):
        assessor.assess(target_id="t", scores_by_rubric={})


def test_baseline_scores_emits_one_per_characteristic():
    rb = registry.get("rb.function.close")
    out = MaturityAssessor.baseline_scores(rb, score=2)
    expected = sum(len(g.characteristics) for g in rb.groups)
    assert len(out) == expected
    assert all(s.score == 2 and s.rationale == "baseline" for s in out)


def test_assessment_overall_pct_handles_empty_capabilities():
    from strata.maturity.assessor import AssessmentResult

    res = AssessmentResult(target_id="t", capabilities=())
    assert res.overall_pct == 0.0


# ---------------------------- registry ----------------------------


def test_registry_get_unknown_rubric_raises():
    with pytest.raises(KeyError, match="unknown rubric"):
        registry.get("rb.deliverable.does_not_exist")


def test_registry_list_by_scope_returns_function_rubrics():
    out = registry.list_by_scope("function")
    ids = {r.rubric_id for r in out}
    assert "rb.function.close" in ids
    assert all(r.scope == "function" for r in out)


# ---------------------------- catalog ----------------------------


def test_catalog_skill_unknown_raises():
    cat = load_catalog()
    with pytest.raises(KeyError, match="not in catalog"):
        cat.skill("does.not.exist")


# ---------------------------- director error path ----------------------------


def _exploding_author(*_a, **_kw):
    raise RuntimeError("author blew up")


def test_director_error_path_persists_failure(tmp_path, monkeypatch):
    monkeypatch.setenv("STRATA_TEST_DB", f"sqlite:///{tmp_path / 'd.sqlite'}")
    from strata import config, db
    config.get_settings.cache_clear()
    db._engine = None
    db._SessionLocal = None
    from strata.db import Base, get_engine
    from strata import models  # noqa: F401
    Base.metadata.create_all(get_engine())

    # Replace the board-pack chain's mock_author with one that explodes.
    from dataclasses import replace
    import strata.orchestrator.chains as chains_mod
    bad_chain = replace(chains_mod._REGISTRY["rb.deliverable.board_pack"], mock_author=_exploding_author)
    monkeypatch.setitem(chains_mod._REGISTRY, "rb.deliverable.board_pack", bad_chain)

    director = Director(persist=True)
    with pytest.raises(RuntimeError, match="author blew up"):
        director.run_board_pack({"company": "X", "period": "p"})

    # board_pack depends on bva_commentary. The dependency runs first and may
    # log its own RunLog row before the patched chain explodes. Filter to the
    # failed board_pack run.
    from sqlalchemy import select
    from strata.db import session_scope as ss
    from strata.models import RunLog
    with ss() as s:
        row = s.execute(
            select(RunLog).where(
                RunLog.chain_id == "chain.board_pack.v1",
                RunLog.status == "error",
            )
        ).scalar_one()
        assert row.error and "author blew up" in row.error


# ---------------------------- session_scope rollback ----------------------------


def test_session_scope_rolls_back_on_exception(tmp_path, monkeypatch):
    monkeypatch.setenv("STRATA_TEST_DB", f"sqlite:///{tmp_path / 'rb.sqlite'}")
    from strata import config, db
    config.get_settings.cache_clear()
    db._engine = None
    db._SessionLocal = None
    from strata.db import Base, get_engine
    from strata import models  # noqa: F401
    Base.metadata.create_all(get_engine())

    with pytest.raises(RuntimeError, match="boom"):
        with session_scope() as _s:
            raise RuntimeError("boom")


# ---------------------------- schema compute missing-score branch ----------------------------


def test_compute_raises_on_missing_score():
    chars = (
        Characteristic(
            id="c1", name="C1", weight=0.50,
            attributes=(
                Attribute(level="Mature",     score=4, anchor="exemplary"),
                Attribute(level="Developing", score=3, anchor="solid"),
                Attribute(level="Emerging",   score=2, anchor="patchy"),
                Attribute(level="Absent",     score=1, anchor="missing"),
            ),
        ),
        Characteristic(
            id="c2", name="C2", weight=0.50,
            attributes=(
                Attribute(level="Mature",     score=4, anchor="exemplary"),
                Attribute(level="Absent",     score=1, anchor="missing"),
            ),
        ),
    )
    g = Group(id="g", name="G", weight=0.50, characteristics=chars)
    rb = Rubric(
        rubric_id="rb.deliverable.partial",
        scope="deliverable",
        name="Partial",
        version=1,
        groups=(g, g),
    )
    incomplete = [CharacteristicScore(characteristic_id="c1", score=3, rationale="ok")]
    with pytest.raises(ValueError, match="missing score for characteristic"):
        RubricScoreReport.compute(rubric=rb, target_id="t", scores=incomplete)
