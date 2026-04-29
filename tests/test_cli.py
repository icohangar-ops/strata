"""End-to-end CLI smoke tests using Typer's runner."""
from __future__ import annotations

from pathlib import Path

from typer.testing import CliRunner

from strata.cli import app

runner = CliRunner()
SAMPLES = Path(__file__).resolve().parents[1] / "samples"


def test_rubrics_command_lists_all_rubrics():
    result = runner.invoke(app, ["rubrics"])
    assert result.exit_code == 0
    # Rich may truncate long ids in the rendered table — check by name + scope.
    assert "Monthly Board Pack" in result.stdout
    assert "Monthly Close" in result.stdout
    assert "Forecasting" in result.stdout


def test_assess_command_produces_heatmap():
    result = runner.invoke(app, ["assess", "--self-assessment", str(SAMPLES / "maturity_self_assessment.yaml")])
    assert result.exit_code == 0
    assert "Maturity heatmap" in result.stdout
    assert "overall:" in result.stdout
    assert "Forecasting" in result.stdout


def test_board_pack_command_runs_chain():
    result = runner.invoke(app, ["board-pack", "--inputs", str(SAMPLES / "board_pack_inputs.json")])
    assert result.exit_code == 0
    assert "Board Pack" in result.stdout
    assert "iterations:" in result.stdout
    assert "Acme Robotics" in result.stdout


def test_assess_command_errors_when_required_rubric_missing(tmp_path):
    """If the self-assessment YAML omits a capability the assessor expects,
    the CLI must exit non-zero with a BadParameter naming the missing rubric."""
    incomplete = tmp_path / "partial.yaml"
    incomplete.write_text(
        # has rb.function.close but is missing the other four capability rubrics
        "target_id: Test Co\n"
        "rb.function.close:\n"
        "  team_understands_close_target: 3\n"
        "  stakeholders_know_calendar: 3\n"
        "  written_close_runbook: 2\n"
        "  review_evidence_trail: 2\n"
        "  cycle_time_measured: 2\n"
        "  error_rate_tracked: 1\n"
        "  bus_follow_calendar: 3\n"
        "  cross_functional_handoffs: 2\n"
        "  recurring_entries_automated: 2\n"
        "  tie_outs_machine_checked: 1\n",
        encoding="utf-8",
    )
    result = runner.invoke(app, ["assess", "--self-assessment", str(incomplete)])
    assert result.exit_code != 0
    combined = (result.stdout + (result.stderr or "")).lower()
    assert "missing scores" in combined
    assert "rb.function.reconcile" in combined
