"""L2 — Catalog loader. Reads catalog.yaml as a frozen dataclass tree."""
from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import yaml

CATALOG_PATH = Path(__file__).resolve().parent / "catalog.yaml"


@dataclass(frozen=True)
class Skill:
    id: str
    name: str
    outputs: tuple[str, ...]
    capability: str | None
    deliverable_rubric: str | None


@dataclass(frozen=True)
class Phase:
    id: str
    name: str
    skills: tuple[Skill, ...]


@dataclass(frozen=True)
class Catalog:
    version: int
    phases: tuple[Phase, ...]

    def skill(self, skill_id: str) -> Skill:
        for p in self.phases:
            for s in p.skills:
                if s.id == skill_id:
                    return s
        raise KeyError(f"skill '{skill_id}' not in catalog")

    def skills_for_capability(self, capability: str) -> list[Skill]:
        return [s for p in self.phases for s in p.skills if s.capability == capability]


@lru_cache(maxsize=1)
def load_catalog(path: Path | None = None) -> Catalog:
    src = path or CATALOG_PATH
    with src.open("r", encoding="utf-8") as f:
        raw = yaml.safe_load(f)
    phases = tuple(
        Phase(
            id=p["id"],
            name=p["name"],
            skills=tuple(
                Skill(
                    id=s["id"],
                    name=s["name"],
                    outputs=tuple(s.get("outputs", ())),
                    capability=s.get("capability"),
                    deliverable_rubric=s.get("deliverable_rubric"),
                )
                for s in p.get("skills", [])
            ),
        )
        for p in raw["phases"]
    )
    return Catalog(version=raw["version"], phases=phases)
