"""Live LLM smoke tests across all registered chains.

Skipped by default. Run with:
    # OpenAI-compatible (DashScope International default)
    STRATA_LLM_BACKEND=openai DASHSCOPE_API_KEY=sk-... pytest -m live_llm

    # Anthropic
    STRATA_LLM_BACKEND=anthropic ANTHROPIC_API_KEY=sk-... pytest -m live_llm

Each test exercises the real iteration loop end to end:
- the configured LLM grader actually grades
- the configured author actually authors
- the rubric pass-threshold actually constrains iteration count

These tests cost real tokens. Pick a cheap model:
    STRATA_GRADER_MODEL=qwen-plus
    STRATA_AUTHOR_MODEL=qwen-plus
"""
from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from strata.orchestrator import all_chains
from strata.orchestrator.director import Director

SAMPLES = Path(__file__).resolve().parents[1] / "samples"

# Map chain_id -> sample inputs file (None = synthetic)
_CHAIN_INPUTS: dict[str, str | None] = {
    "chain.board_pack.v1":              "board_pack_inputs.json",
    "chain.bva_commentary.v1":          "bva_inputs.json",
    "chain.ma_memo.v1":                 "ma_memo_inputs.json",
    "chain.investor_update.v1":         "investor_update_inputs.json",
    "chain.three_statement.v1":         "three_statement_inputs.json",
    "chain.cfo_dashboard.v1":           "cfo_dashboard_inputs.json",
    "chain.risk_register.v1":           "risk_register_inputs.json",
    "chain.capex_memo.v1":              "capex_memo_inputs.json",
    "chain.post_investment_review.v1":  "post_investment_review_inputs.json",
    "chain.employee_all_hands.v1":      "employee_all_hands_inputs.json",
    "chain.cross_functional_brief.v1":  "cross_functional_brief_inputs.json",
    "chain.earnings_script.v1":         "earnings_script_inputs.json",
}


def _load_inputs(chain_id: str) -> dict:
    name = _CHAIN_INPUTS.get(chain_id)
    if not name:
        return {"company": "Acme Robotics", "period": "Mar 2026"}
    return json.loads((SAMPLES / name).read_text(encoding="utf-8"))


def _all_chain_ids() -> list[str]:
    return [c.chain_id for c in all_chains()]


def _has_live_llm_key() -> bool:
    return bool(
        os.getenv("DASHSCOPE_API_KEY")
        or os.getenv("OPENAI_API_KEY")
        or os.getenv("STRATA_LLM_API_KEY")
        or os.getenv("ANTHROPIC_API_KEY")
    )


@pytest.mark.live_llm
@pytest.mark.skipif(
    not _has_live_llm_key(),
    reason="No LLM API key set (DASHSCOPE_API_KEY / OPENAI_API_KEY / ANTHROPIC_API_KEY); skipping",
)
@pytest.mark.parametrize("chain_id", _all_chain_ids())
def test_chain_runs_against_real_llm(chain_id: str):
    inputs = _load_inputs(chain_id)
    run = Director(persist=False, use_llm=True).run_chain(chain_id, inputs)
    r = run.factory_result
    assert r.iterations >= 1
    assert r.iterations <= 5
    assert len(r.final_draft) > 200, "real LLM should produce a substantive draft"
