"""Rubric grader. LLM-agnostic protocol with a deterministic mock and an Anthropic backend."""
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Protocol

from strata.config import get_settings
from strata.schema import CharacteristicScore, Rubric, RubricScoreReport


class LLMClient(Protocol):
    def complete(self, system: str, user: str) -> str:
        ...


# ---------------------------- mock backend (offline-safe default) ----------------------------


class MockLLM:
    """Deterministic grader. Pretends to be a strict reviewer.

    Heuristic: longer drafts and drafts containing rubric anchor cue-words score
    higher. This is enough to exercise the iteration loop and the schema in
    tests without burning tokens.
    """

    def __init__(self, base_score: int = 3) -> None:
        self._base = base_score

    def complete(self, system: str, user: str) -> str:
        draft = _extract_block(user, "DRAFT")
        rubric_json = _extract_block(user, "RUBRIC")
        rubric = json.loads(rubric_json)
        scores = []
        for group in rubric["groups"]:
            for char in group["characteristics"]:
                cue = sum(
                    1 for a in char["attributes"]
                    for word in _keywords(a["anchor"])
                    if word in draft.lower()
                )
                score = max(1, min(4, self._base + (1 if cue >= 2 else 0)))
                scores.append(
                    {
                        "characteristic_id": char["id"],
                        "score": score,
                        "rationale": f"mock: cue-word matches={cue}",
                    }
                )
        return json.dumps({"scores": scores})


def _keywords(anchor: str) -> list[str]:
    return [w for w in re.findall(r"[a-z]{5,}", anchor.lower())][:4]


def _extract_block(text: str, tag: str) -> str:
    m = re.search(rf"<{tag}>(.*?)</{tag}>", text, flags=re.DOTALL)
    if not m:
        raise ValueError(f"missing <{tag}> block in grader prompt")
    return m.group(1).strip()


# ---------------------------- Anthropic backend (optional) ----------------------------


class AnthropicLLM:  # pragma: no cover - integration only; covered by live e2e
    def __init__(self, model: str | None = None, api_key: str | None = None) -> None:
        try:
            import anthropic
        except ImportError as e:
            raise ImportError("install with `pip install -e '.[llm]'` to use Anthropic") from e
        s = get_settings()
        self._client = anthropic.Anthropic(api_key=api_key or s.anthropic_api_key)
        self._model = model or s.grader_model

    def complete(self, system: str, user: str) -> str:
        msg = self._client.messages.create(
            model=self._model,
            max_tokens=2048,
            system=system,
            messages=[{"role": "user", "content": user}],
        )
        return "".join(b.text for b in msg.content if hasattr(b, "text"))


class OpenAICompatibleLLM:  # pragma: no cover - integration only; covered by live e2e
    """Works against any OpenAI-compatible /chat/completions endpoint.

    Default config in Strata points at DashScope International (Qwen models).
    Set STRATA_LLM_BASE_URL to switch (OpenAI proper, Together, Groq, etc.)."""

    def __init__(
        self,
        model: str | None = None,
        api_key: str | None = None,
        base_url: str | None = None,
    ) -> None:
        try:
            from openai import OpenAI
        except ImportError as e:
            raise ImportError(
                "install with `pip install -e '.[llm]'` to use the OpenAI-compatible backend"
            ) from e
        s = get_settings()
        key = api_key or s.llm_api_key
        if not key:
            raise RuntimeError(
                "No LLM API key set. Set DASHSCOPE_API_KEY (or OPENAI_API_KEY) "
                "for the openai backend."
            )
        self._client = OpenAI(api_key=key, base_url=base_url or s.llm_base_url)
        self._model = model or s.grader_model

    def complete(self, system: str, user: str) -> str:
        resp = self._client.chat.completions.create(
            model=self._model,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            max_tokens=2048,
            temperature=0,
        )
        return resp.choices[0].message.content or ""


# ---------------------------- grader ----------------------------


GRADER_SYSTEM = """You are a strict, fair rubric grader.
You will be given a draft deliverable and a rubric.
Score every characteristic on its discrete 1..4 scale by selecting the integer
score whose anchor text best matches the draft. Return JSON only:
{"scores": [{"characteristic_id": str, "score": int, "rationale": str}, ...]}
Be terse in rationale (<= 25 words). Do not invent characteristics."""


@dataclass(frozen=True)
class GraderResult:
    report: RubricScoreReport
    raw_response: str


class Grader:
    def __init__(self, llm: LLMClient | None = None, pass_threshold_pct: float = 70.0) -> None:
        self._llm = llm or MockLLM()
        self._pass_pct = pass_threshold_pct

    def grade(self, rubric: Rubric, draft: str, target_id: str) -> GraderResult:
        user = self._build_prompt(rubric, draft)
        raw = self._llm.complete(GRADER_SYSTEM, user)
        scores = _parse_scores(raw)
        report = RubricScoreReport.compute(
            rubric=rubric,
            target_id=target_id,
            scores=scores,
            pass_threshold_pct=self._pass_pct,
        )
        return GraderResult(report=report, raw_response=raw)

    @staticmethod
    def _build_prompt(rubric: Rubric, draft: str) -> str:
        return (
            "<RUBRIC>\n"
            f"{rubric.model_dump_json()}\n"
            "</RUBRIC>\n\n"
            "<DRAFT>\n"
            f"{draft}\n"
            "</DRAFT>"
        )


def _parse_scores(raw: str) -> list[CharacteristicScore]:
    """Tolerant JSON extractor. Handles markdown fences and prose-wrapped JSON."""
    blob = raw.strip()
    fenced = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", blob, flags=re.DOTALL)
    if fenced:
        blob = fenced.group(1)
    else:
        first = blob.find("{")
        last = blob.rfind("}")
        if first != -1 and last != -1:
            blob = blob[first : last + 1]
    data = json.loads(blob)
    return [CharacteristicScore.model_validate(s) for s in data["scores"]]
