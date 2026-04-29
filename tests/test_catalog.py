"""L2: catalog loads, references valid capability rubrics, and lookup works."""
from __future__ import annotations

from strata import registry
from strata.catalog import load_catalog


def test_catalog_loads():
    cat = load_catalog()
    assert cat.version == 1
    phase_ids = {p.id for p in cat.phases}
    assert phase_ids == {"ingest", "record", "analyze", "plan", "present"}


def test_catalog_capability_ids_exist_in_registry():
    cat = load_catalog()
    rubric_ids = set(registry.load_all().keys())
    for p in cat.phases:
        for s in p.skills:
            if s.capability:
                assert s.capability in rubric_ids, f"{s.id} -> unknown {s.capability}"
            if s.deliverable_rubric:
                assert s.deliverable_rubric in rubric_ids


def test_catalog_lookup_helpers():
    cat = load_catalog()
    s = cat.skill("present.board_pack")
    assert s.deliverable_rubric == "rb.deliverable.board_pack"
    close_skills = cat.skills_for_capability("rb.function.close")
    assert any(s.id == "ingest.gl_pull" for s in close_skills)
