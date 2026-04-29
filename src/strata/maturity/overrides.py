"""Per-tenant rubric overrides applied at decide time.

Reads from the rubric_override DB table; produces an in-memory transformed
Rubric (still validated by the L5 schema) plus a transformed score list.

Override semantics:
  - `weight`: replaces the characteristic weight; the parent group's sibling
    weights are scaled proportionally so the group still sums to 1.0.
  - `score_floor` / `score_ceiling`: clamp the self-reported score in-range.
  - `disabled`: drop the characteristic from the rubric and the scores entirely;
    siblings are scaled to fill the freed weight.
"""
from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import select

from strata.db import session_scope
from strata.models import RubricOverride
from strata.schema import (
    Characteristic,
    CharacteristicScore,
    Group,
    Rubric,
)


@dataclass(frozen=True)
class CharOverride:
    weight: float | None
    score_floor: int | None
    score_ceiling: int | None
    disabled: bool


def load_overrides(tenant_id: str, rubric_id: str) -> dict[str, CharOverride]:
    """Returns characteristic_id -> CharOverride for a given tenant + rubric."""
    out: dict[str, CharOverride] = {}
    with session_scope() as s:
        rows = s.execute(
            select(RubricOverride).where(
                RubricOverride.tenant_id == tenant_id,
                RubricOverride.rubric_id == rubric_id,
            )
        ).scalars().all()
        for r in rows:
            out[r.characteristic_id] = CharOverride(
                weight=r.weight,
                score_floor=r.score_floor,
                score_ceiling=r.score_ceiling,
                disabled=r.disabled,
            )
    return out


def apply_overrides(
    rubric: Rubric,
    scores: list[CharacteristicScore],
    overrides: dict[str, CharOverride],
) -> tuple[Rubric, list[CharacteristicScore]]:
    """Returns a new (Rubric, scores) pair with overrides applied. Originals untouched."""
    if not overrides:
        return rubric, scores

    new_groups: list[Group] = []
    for group in rubric.groups:
        kept_chars = [c for c in group.characteristics if not overrides.get(c.id, _NULL).disabled]
        if not kept_chars:
            raise ValueError(
                f"override would disable every characteristic in group '{group.id}'"
            )

        # Within a group:
        #   - characteristics with weight overrides take their exact override weight
        #   - the remainder (1 - sum-of-overrides) is distributed proportionally to
        #     siblings whose weights were NOT overridden, using their original ratios
        ov_for = {c.id: overrides.get(c.id, _NULL) for c in kept_chars}
        overridden_total = sum(
            ov.weight for ov in ov_for.values() if ov.weight is not None
        )
        free_orig_total = sum(
            c.weight for c in kept_chars if ov_for[c.id].weight is None
        )

        if overridden_total > 1.0 + WEIGHT_TOL_LOCAL:
            raise ValueError(
                f"group '{group.id}': overridden weights sum to {overridden_total:.4f} > 1.0"
            )

        new_chars: list[Characteristic] = []
        for c in kept_chars:
            ov_w = ov_for[c.id].weight
            if ov_w is not None:
                new_w = ov_w
            else:
                if free_orig_total <= 0:
                    raise ValueError(
                        f"group '{group.id}': no free weight to distribute to '{c.id}'"
                    )
                remainder = 1.0 - overridden_total
                if remainder <= 0:
                    raise ValueError(
                        f"group '{group.id}': overrides leave no room for non-overridden char '{c.id}'"
                    )
                new_w = c.weight * (remainder / free_orig_total)
            new_chars.append(
                Characteristic(
                    id=c.id,
                    name=c.name,
                    weight=round(new_w, 6),
                    attributes=c.attributes,
                )
            )
        # Final sum may drift by 1e-6 due to rounding; fix by absorbing the
        # delta into the largest-weight characteristic so the group sums to 1.0.
        s = sum(c.weight for c in new_chars)
        if s != 1.0:
            biggest = max(range(len(new_chars)), key=lambda i: new_chars[i].weight)
            adjusted = new_chars[biggest]
            new_chars[biggest] = Characteristic(
                id=adjusted.id,
                name=adjusted.name,
                weight=round(adjusted.weight + (1.0 - s), 6),
                attributes=adjusted.attributes,
            )
        new_groups.append(
            Group(
                id=group.id,
                name=group.name,
                weight=group.weight,
                characteristics=tuple(new_chars),
            )
        )
    new_rubric = Rubric(
        rubric_id=rubric.rubric_id,
        scope=rubric.scope,
        name=rubric.name,
        version=rubric.version,
        description=rubric.description,
        groups=tuple(new_groups),
    )

    kept_ids = {c.id for g in new_rubric.groups for c in g.characteristics}
    new_scores: list[CharacteristicScore] = []
    for s in scores:
        if s.characteristic_id not in kept_ids:
            continue
        ov = overrides.get(s.characteristic_id, _NULL)
        score = s.score
        if ov.score_floor is not None:
            score = max(score, ov.score_floor)
        if ov.score_ceiling is not None:
            score = min(score, ov.score_ceiling)
        new_scores.append(
            CharacteristicScore(
                characteristic_id=s.characteristic_id,
                score=score,
                rationale=s.rationale,
            )
        )
    return new_rubric, new_scores


_NULL = CharOverride(weight=None, score_floor=None, score_ceiling=None, disabled=False)
WEIGHT_TOL_LOCAL = 1e-6
