"""v7: vector exemplar store + factory integration.

Offline unit tests use the InMemoryExemplarStore. The live_astra marker covers
real Astra DB integration; it is skipped without ASTRA_DB_API_ENDPOINT and
ASTRA_DB_APPLICATION_TOKEN."""
from __future__ import annotations

import os

import pytest

from strata import registry
from strata.deliverable.author import build_author_prompt, _format_exemplars
from strata.deliverable.board_pack import mock_author
from strata.deliverable.factory import DeliverableFactory
from strata.deliverable.grader import Grader, MockLLM
from strata.deliverable.persona import get_persona
from strata.vector import (
    Exemplar,
    InMemoryExemplarStore,
    NullExemplarStore,
    get_default_store,
)
from strata.vector.exemplars import _cosine, _trigram_vec, make_exemplar_id


# ---------------------------- public types ----------------------------


def test_exemplar_id_is_stable():
    a = make_exemplar_id("chain.x.v1", "acme::march_2026")
    b = make_exemplar_id("chain.x.v1", "acme::march_2026")
    assert a == b
    assert len(a) == 24
    assert a != make_exemplar_id("chain.x.v1", "acme::april_2026")


def test_null_store_always_empty():
    s = NullExemplarStore()
    s.upsert(Exemplar(id="x", chain_id="c", target_id="t", draft="hello"))
    assert s.search("c", "anything", top_k=3) == []
    assert s.count() == 0


# ---------------------------- in-memory store ----------------------------


def test_in_memory_store_round_trips():
    s = InMemoryExemplarStore()
    s.upsert(Exemplar(id="e1", chain_id="c1", target_id="t1", draft="board pack March 2026 revenue"))
    s.upsert(Exemplar(id="e2", chain_id="c1", target_id="t2", draft="bva commentary volume price mix"))
    assert s.count() == 2
    assert s.count(chain_id="c1") == 2
    assert s.count(chain_id="c2") == 0


def test_in_memory_store_filters_by_chain():
    s = InMemoryExemplarStore()
    s.upsert(Exemplar(id="e1", chain_id="c1", target_id="t1", draft="board pack content"))
    s.upsert(Exemplar(id="e2", chain_id="c2", target_id="t2", draft="board pack content"))
    hits = s.search("c1", "board pack", top_k=5)
    assert len(hits) == 1
    assert hits[0].exemplar.chain_id == "c1"


def test_in_memory_store_returns_top_k_sorted_by_similarity():
    s = InMemoryExemplarStore()
    s.upsert(Exemplar(id="e1", chain_id="c", target_id="alpha", draft="alpha content"))
    s.upsert(Exemplar(id="e2", chain_id="c", target_id="beta", draft="beta content"))
    s.upsert(Exemplar(id="e3", chain_id="c", target_id="gamma", draft="gamma content"))
    hits = s.search("c", "alpha content", top_k=2)
    assert len(hits) == 2
    sims = [h.similarity for h in hits]
    assert sims == sorted(sims, reverse=True)
    assert hits[0].exemplar.target_id == "alpha"


def test_cosine_handles_empty_inputs():
    assert _cosine({}, {"a": 1}) == 0.0
    assert _cosine({"a": 1}, {}) == 0.0


def test_trigram_vec_returns_chargrams():
    v = _trigram_vec("hello")
    # "hel", "ell", "llo"
    assert v == {"hel": 1, "ell": 1, "llo": 1}


# ---------------------------- get_default_store selector ----------------------------


def test_get_default_store_returns_null_when_astra_unset(monkeypatch):
    monkeypatch.delenv("ASTRA_DB_API_ENDPOINT", raising=False)
    monkeypatch.delenv("ASTRA_DB_APPLICATION_TOKEN", raising=False)
    from strata import config
    config.get_settings.cache_clear()
    assert isinstance(get_default_store(), NullExemplarStore)


# ---------------------------- author-prompt splice ----------------------------


def test_format_exemplars_returns_empty_when_none():
    assert _format_exemplars(None) == ""
    assert _format_exemplars([]) == ""


def test_format_exemplars_includes_target_id_and_similarity():
    exs = [
        {"target_id": "acme::feb_2026", "draft": "lorem ipsum", "similarity": 0.872},
        {"target_id": "acme::jan_2026", "draft": "dolor sit",   "similarity": 0.701},
    ]
    out = _format_exemplars(exs)
    assert "PRIOR EXEMPLARS" in out
    assert "acme::feb_2026" in out
    assert "0.87" in out
    assert "lorem ipsum" in out
    assert "dolor sit" in out
    assert "END OF EXEMPLARS" in out


def test_build_author_prompt_includes_exemplars_when_present():
    rb = registry.get("rb.deliverable.board_pack")
    persona = get_persona(rb.rubric_id)
    inputs = {
        "company": "Acme",
        "period": "Mar 2026",
        "_exemplars": [{"target_id": "acme::feb_2026", "draft": "prior draft body", "similarity": 0.9}],
    }
    prompt = build_author_prompt(persona, rb, inputs, history=[])
    assert "PRIOR EXEMPLARS" in prompt
    assert "acme::feb_2026" in prompt
    assert "prior draft body" in prompt


def test_build_author_prompt_without_exemplars_unchanged():
    rb = registry.get("rb.deliverable.board_pack")
    persona = get_persona(rb.rubric_id)
    prompt = build_author_prompt(persona, rb, {"company": "Acme", "period": "p"}, history=[])
    assert "PRIOR EXEMPLARS" not in prompt


# ---------------------------- factory integration ----------------------------


def test_factory_with_no_chain_id_skips_exemplar_lookup():
    rb = registry.get("rb.deliverable.board_pack")
    store = InMemoryExemplarStore()
    store.upsert(Exemplar(id="e1", chain_id="chain.board_pack.v1", target_id="t", draft="x"))
    factory = DeliverableFactory(
        rubric=rb,
        author=mock_author,
        grader=Grader(llm=MockLLM(), pass_threshold_pct=70.0),
        max_iterations=1,
        exemplar_store=store,
        chain_id=None,  # disabled
    )
    res = factory.run(target_id="t", inputs={"company": "X", "period": "p"})
    assert res.iterations == 1


def test_factory_with_chain_id_pulls_exemplars_into_inputs():
    """Verify the factory queries the store and passes exemplars to the author."""
    rb = registry.get("rb.deliverable.board_pack")
    store = InMemoryExemplarStore()
    store.upsert(Exemplar(
        id="e1",
        chain_id="chain.board_pack.v1",
        target_id="acme::feb_2026",
        draft="board pack period feb 2026 acme robotics revenue ledger",
    ))

    captured: dict[str, list[dict] | None] = {"exemplars": None}

    def spy_author(persona, rubric, inputs, history):
        captured["exemplars"] = inputs.get("_exemplars")
        return mock_author(persona, rubric, inputs, history)

    factory = DeliverableFactory(
        rubric=rb,
        author=spy_author,
        grader=Grader(llm=MockLLM(base_score=4), pass_threshold_pct=70.0),
        max_iterations=1,
        exemplar_store=store,
        chain_id="chain.board_pack.v1",
    )
    factory.run(
        target_id="acme::march_2026",
        inputs={"company": "Acme Robotics", "period": "March 2026"},
    )
    assert captured["exemplars"] is not None
    assert len(captured["exemplars"]) >= 1
    assert captured["exemplars"][0]["target_id"] == "acme::feb_2026"


def test_factory_falls_back_silently_on_exemplar_lookup_failure():
    """A vector lookup error must never break a run."""
    rb = registry.get("rb.deliverable.board_pack")

    class ExplodingStore:
        def search(self, **kw):
            raise RuntimeError("vector backend offline")

        def count(self, **kw):
            return 0

        def upsert(self, ex):
            return None

    factory = DeliverableFactory(
        rubric=rb,
        author=mock_author,
        grader=Grader(llm=MockLLM(base_score=4), pass_threshold_pct=70.0),
        max_iterations=1,
        exemplar_store=ExplodingStore(),
        chain_id="chain.board_pack.v1",
    )
    res = factory.run(target_id="t", inputs={"company": "X", "period": "p"})
    assert res.passed is True


# ---------------------------- live Astra (opt-in) ----------------------------


_HAS_ASTRA = bool(os.getenv("ASTRA_DB_API_ENDPOINT") and os.getenv("ASTRA_DB_APPLICATION_TOKEN"))


@pytest.mark.live_astra
@pytest.mark.skipif(
    not _HAS_ASTRA,
    reason="ASTRA_DB_API_ENDPOINT + ASTRA_DB_APPLICATION_TOKEN not set; skipping live Astra test",
)
def test_astra_round_trip():
    """Live integration: insert a synthetic exemplar, search for it, verify retrieval, clean up."""
    from strata.vector.exemplars import AstraExemplarStore

    store = AstraExemplarStore()
    test_id = make_exemplar_id("chain.live_test.v1", "smoke_test")
    ex = Exemplar(
        id=test_id,
        chain_id="chain.live_test.v1",
        target_id="smoke_test",
        draft="This is a synthetic exemplar inserted by the v7 live Astra smoke test.",
        score_pct=99.9,
        metadata={"smoke_test": True},
    )
    store.upsert(ex)
    hits = store.search(
        chain_id="chain.live_test.v1",
        query="synthetic exemplar smoke test",
        top_k=1,
    )
    assert hits, "live Astra returned no hits"
    assert hits[0].exemplar.id == test_id
