"""Generic LLM author. The author prompt is built from the persona + rubric +
inputs + history triple, so a single Anthropic-backed author works for every
deliverable type.
"""
from __future__ import annotations

from typing import Any

from strata.config import get_settings
from strata.deliverable.grader import GraderResult
from strata.deliverable.persona import Persona
from strata.schema import Rubric


def build_author_prompt(
    persona: Persona,
    rubric: Rubric,
    inputs: dict[str, Any],
    history: list[GraderResult],
) -> str:
    feedback = ""
    if history:
        last = history[-1]
        weak = sorted(last.report.scores, key=lambda s: s.score)[:5]
        feedback = (
            "\n\nPRIOR-DRAFT FEEDBACK (improve these):\n"
            + "\n".join(f"- {s.characteristic_id}: scored {s.score} — {s.rationale}" for s in weak)
            + f"\n\nPRIOR NORMALIZED SCORE: {last.report.normalized_pct:.1f}%."
        )
    exemplars_block = _format_exemplars(inputs.pop("_exemplars", None))
    standards = "\n  - ".join(persona.standards)
    return (
        f"ROLE: {persona.role}\n"
        f"VOICE: {persona.voice}\n"
        f"STANDARDS:\n  - {standards}\n\n"
        f"DELIVERABLE: {rubric.name}\n"
        f"INPUTS:\n{_dump_inputs(inputs)}\n"
        f"{exemplars_block}"
        f"{feedback}\n\n"
        "Write the deliverable. Be terse, decision-oriented, and tight. "
        "Lead with a one-page synthesis."
    )


def _format_exemplars(exemplars: list[dict] | None) -> str:
    """Splice retrieved past drafts into the author prompt as worked examples.

    Each exemplar contributes a similarity score, target_id, and a truncated
    body so the prompt stays bounded even with multiple high-quality matches.
    """
    if not exemplars:
        return ""
    blocks: list[str] = []
    for i, ex in enumerate(exemplars, start=1):
        body = (ex.get("draft") or "")[:1200]
        sim = ex.get("similarity")
        sim_str = f" (similarity {sim:.2f})" if isinstance(sim, (int, float)) else ""
        blocks.append(
            f"\n--- EXEMPLAR {i}: {ex.get('target_id', 'prior draft')}{sim_str} ---\n{body}"
        )
    return (
        "\n\nPRIOR EXEMPLARS (top-K most similar past drafts of this same chain; "
        "use these to calibrate voice and structure, not to copy verbatim):"
        + "".join(blocks)
        + "\n\nEND OF EXEMPLARS.\n"
    )


def _dump_inputs(inputs: dict[str, Any]) -> str:
    import json
    return json.dumps(inputs, indent=2, default=str)


def anthropic_author_factory(model: str | None = None):  # pragma: no cover - integration only
    """Returns an Author callable backed by Anthropic. Lazy-imports anthropic."""
    s = get_settings()
    try:
        import anthropic
    except ImportError as e:
        raise ImportError("install with `pip install -e '.[llm]'` to use Anthropic") from e
    if not s.anthropic_api_key:
        raise RuntimeError("ANTHROPIC_API_KEY not set; cannot use --use-llm with anthropic backend")
    client = anthropic.Anthropic(api_key=s.anthropic_api_key)
    use_model = model or s.author_model

    def _author(
        persona: Persona,
        rubric: Rubric,
        inputs: dict[str, Any],
        history: list[GraderResult],
    ) -> str:
        prompt = build_author_prompt(persona, rubric, inputs, history)
        msg = client.messages.create(
            model=use_model,
            max_tokens=4096,
            system="You write CFO-grade financial deliverables. Be terse and tie out.",
            messages=[{"role": "user", "content": prompt}],
        )
        return "".join(b.text for b in msg.content if hasattr(b, "text"))

    return _author


def openai_compatible_author_factory(model: str | None = None):  # pragma: no cover - integration only
    """Returns an Author backed by any OpenAI-compatible /chat/completions endpoint.

    Default config in Strata points at DashScope International. Set
    STRATA_LLM_BASE_URL to switch endpoints. Lazy-imports openai SDK."""
    s = get_settings()
    try:
        from openai import OpenAI
    except ImportError as e:
        raise ImportError(
            "install with `pip install -e '.[llm]'` to use the OpenAI-compatible backend"
        ) from e
    if not s.llm_api_key:
        raise RuntimeError(
            "No LLM API key set. Set DASHSCOPE_API_KEY (or OPENAI_API_KEY) for the openai backend."
        )
    client = OpenAI(api_key=s.llm_api_key, base_url=s.llm_base_url)
    use_model = model or s.author_model

    def _author(
        persona: Persona,
        rubric: Rubric,
        inputs: dict[str, Any],
        history: list[GraderResult],
    ) -> str:
        prompt = build_author_prompt(persona, rubric, inputs, history)
        resp = client.chat.completions.create(
            model=use_model,
            messages=[
                {"role": "system", "content": "You write CFO-grade financial deliverables. Be terse and tie out."},
                {"role": "user", "content": prompt},
            ],
            max_tokens=4096,
            temperature=0,
        )
        return resp.choices[0].message.content or ""

    return _author
