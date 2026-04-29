"""v4: competency-axis assessor + CFO value-creation dashboard."""
from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml
from typer.testing import CliRunner

from strata import registry
from strata.catalog import load_catalog
from strata.cli import app
from strata.deliverable.persona import get_persona
from strata.maturity import (
    CAPABILITY_RUBRIC_IDS,
    COMPETENCY_RUBRIC_IDS,
    CompetencyAssessor,
    MaturityAssessor,
)
from strata.orchestrator import all_chains, chain_for_deliverable
from strata.orchestrator.director import Director
from strata.schema import CharacteristicScore

SAMPLES = Path(__file__).resolve().parents[1] / "samples"
runner = CliRunner()


# ---------------------------- 5 competency rubrics ----------------------------


def test_all_competency_rubrics_load():
    rs = registry.load_all()
    for rid in COMPETENCY_RUBRIC_IDS:
        assert rid in rs, f"missing competency rubric '{rid}'"


def test_competency_rubric_count():
    assert len(COMPETENCY_RUBRIC_IDS) == 5


@pytest.mark.parametrize("rid", COMPETENCY_RUBRIC_IDS)
def test_competency_rubric_well_formed(rid):
    rb = registry.get(rid)
    assert sum(g.weight for g in rb.groups) == pytest.approx(1.0, abs=1e-6)
    for g in rb.groups:
        assert sum(c.weight for c in g.characteristics) == pytest.approx(1.0, abs=1e-6)
    # Each pillar should have 4 sub-competencies (handbook structure)
    assert len(rb.groups) == 4


# ---------------------------- CompetencyAssessor ----------------------------


def _full_competency_scores(score: int) -> dict[str, list[CharacteristicScore]]:
    out: dict[str, list[CharacteristicScore]] = {}
    for rid in COMPETENCY_RUBRIC_IDS:
        rb = registry.get(rid)
        out[rid] = [
            CharacteristicScore(characteristic_id=c.id, score=score, rationale="t")
            for g in rb.groups
            for c in g.characteristics
        ]
    return out


def test_competency_assessor_uniform_floor():
    res = CompetencyAssessor().assess(target_id="t", scores_by_rubric=_full_competency_scores(1))
    assert res.overall_pct == pytest.approx(25.0, abs=1e-6)


def test_competency_assessor_uniform_ceiling():
    res = CompetencyAssessor().assess(target_id="t", scores_by_rubric=_full_competency_scores(4))
    assert res.overall_pct == pytest.approx(100.0, abs=1e-6)


def test_function_and_competency_axes_are_independent():
    f_assessor = MaturityAssessor()
    c_assessor = CompetencyAssessor()
    assert f_assessor.rubric_ids == CAPABILITY_RUBRIC_IDS
    assert c_assessor.rubric_ids == COMPETENCY_RUBRIC_IDS
    # No rubric appears on both axes
    assert set(CAPABILITY_RUBRIC_IDS).isdisjoint(set(COMPETENCY_RUBRIC_IDS))


def test_sample_self_assessment_loads_on_competency_axis():
    raw = yaml.safe_load((SAMPLES / "maturity_self_assessment.yaml").read_text(encoding="utf-8"))
    target_id = raw.pop("target_id")
    by_rubric = {
        rid: [
            CharacteristicScore(characteristic_id=cid, score=int(s), rationale="t")
            for cid, s in raw[rid].items()
        ]
        for rid in COMPETENCY_RUBRIC_IDS
    }
    res = CompetencyAssessor().assess(target_id=target_id, scores_by_rubric=by_rubric)
    # Sample is mid-range; expect 30-65% overall
    assert 30.0 <= res.overall_pct <= 65.0


# ---------------------------- CFO value-creation dashboard ----------------------------


def test_cfo_dashboard_rubric_loads():
    rb = registry.get("rb.deliverable.cfo_dashboard")
    assert rb.scope == "deliverable"
    assert sum(g.weight for g in rb.groups) == pytest.approx(1.0, abs=1e-6)


def test_cfo_dashboard_chain_registered():
    ch = chain_for_deliverable("rb.deliverable.cfo_dashboard")
    assert ch.chain_id == "chain.cfo_dashboard.v1"


def test_cfo_dashboard_persona_registered():
    p = get_persona("rb.deliverable.cfo_dashboard")
    assert "value" in p.role.lower() or "dashboard" in p.role.lower()


def test_cfo_dashboard_skill_in_catalog():
    cat = load_catalog()
    s = cat.skill("present.cfo_dashboard")
    assert s.deliverable_rubric == "rb.deliverable.cfo_dashboard"
    assert s.capability == "rb.competency.stakeholder"


def test_cfo_dashboard_chain_runs_end_to_end():
    payload = json.loads((SAMPLES / "cfo_dashboard_inputs.json").read_text(encoding="utf-8"))
    run = Director(persist=False).run_chain("chain.cfo_dashboard.v1", payload)
    assert run.chain_id == "chain.cfo_dashboard.v1"
    assert run.factory_result.iterations >= 1
    assert "Acme Robotics" in run.factory_result.final_draft


# ---------------------------- routing on competency axis ----------------------------


def test_competency_route_picks_dashboard_when_stakeholder_is_weakest():
    # Push every competency high except stakeholder
    raw_scores = {rid: 4 for rid in COMPETENCY_RUBRIC_IDS}
    raw_scores["rb.competency.stakeholder"] = 1
    by_rubric = {
        rid: [
            CharacteristicScore(characteristic_id=c.id, score=raw_scores[rid], rationale="t")
            for g in registry.get(rid).groups
            for c in g.characteristics
        ]
        for rid in COMPETENCY_RUBRIC_IDS
    }
    assess = CompetencyAssessor().assess(target_id="t", scores_by_rubric=by_rubric)
    decision = Director(persist=False).decide(assess)
    assert decision.weakest_capability == "rb.competency.stakeholder"
    assert decision.chain.chain_id == "chain.cfo_dashboard.v1"


# ---------------------------- CLI --axis flag ----------------------------


def test_assess_cli_competency_axis():
    result = runner.invoke(app, [
        "assess",
        "--self-assessment", str(SAMPLES / "maturity_self_assessment.yaml"),
        "--axis", "competency",
    ])
    assert result.exit_code == 0, result.stdout
    assert "Competency heatmap" in result.stdout
    assert "Strategic Financial Leadership" in result.stdout
    assert "Risk Management" in result.stdout


def test_assess_cli_both_axes():
    result = runner.invoke(app, [
        "assess",
        "--self-assessment", str(SAMPLES / "maturity_self_assessment.yaml"),
        "--axis", "both",
    ])
    assert result.exit_code == 0, result.stdout
    assert "Function-axis heatmap" in result.stdout
    assert "Competency-axis heatmap" in result.stdout


def test_assess_cli_invalid_axis():
    result = runner.invoke(app, [
        "assess",
        "--self-assessment", str(SAMPLES / "maturity_self_assessment.yaml"),
        "--axis", "garbage",
    ])
    assert result.exit_code != 0
    combined = (result.stdout + (result.stderr or "")).lower()
    assert "axis must be" in combined


def test_run_cli_competency_axis_routes():
    result = runner.invoke(app, [
        "run",
        "--self-assessment", str(SAMPLES / "maturity_self_assessment.yaml"),
        "--inputs", str(SAMPLES / "cfo_dashboard_inputs.json"),
        "--axis", "competency",
    ])
    assert result.exit_code == 0, result.stdout
    assert "axis:" in result.stdout
    assert "competency" in result.stdout


# ---------------------------- registry growth ----------------------------


def test_chain_registry_includes_cfo_dashboard():
    chain_ids = {c.chain_id for c in all_chains()}
    assert "chain.cfo_dashboard.v1" in chain_ids
