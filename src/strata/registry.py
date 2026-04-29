"""Loads YAML rubrics from src/strata/rubrics/** and validates them against L5 schema."""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path

import yaml

from strata.schema import Rubric

RUBRICS_DIR = Path(__file__).resolve().parent / "rubrics"


def load_rubric_file(path: Path) -> Rubric:
    with path.open("r", encoding="utf-8") as f:
        raw = yaml.safe_load(f)
    return Rubric.model_validate(raw)


@lru_cache(maxsize=None)
def load_all() -> dict[str, Rubric]:
    rubrics: dict[str, Rubric] = {}
    for path in RUBRICS_DIR.rglob("*.yaml"):
        rb = load_rubric_file(path)
        if rb.rubric_id in rubrics:
            raise ValueError(f"duplicate rubric_id '{rb.rubric_id}' at {path}")
        rubrics[rb.rubric_id] = rb
    return rubrics


def get(rubric_id: str) -> Rubric:
    rubrics = load_all()
    if rubric_id not in rubrics:
        raise KeyError(f"unknown rubric '{rubric_id}'. known: {sorted(rubrics)}")
    return rubrics[rubric_id]


def list_by_scope(scope: str) -> list[Rubric]:
    return [r for r in load_all().values() if r.scope == scope]
