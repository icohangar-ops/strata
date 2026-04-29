"""Exemplar store — vector index of past deliverable drafts.

Postgres remains the relational core (rubric, rubric_score, run_log).
This module is purely additive: at draft time, the deliverable factory
queries this store for top-K similar past drafts of the same chain and
splices them into the persona prompt as exemplars.

Three implementations:

    NullExemplarStore       — always empty; used when Astra is not configured
    InMemoryExemplarStore   — simple cosine-similarity store backed by a dict;
                              used in tests and offline demos
    AstraExemplarStore      — DataStax Astra DB Data API with native vector
                              search; used in production when env vars are set

Selection happens via get_default_store() which inspects Settings.has_astra.
"""
from __future__ import annotations

import hashlib
import math
from dataclasses import dataclass, field
from typing import Any, Protocol

from strata.config import get_settings

# ---------------------------- public types ----------------------------


@dataclass(frozen=True)
class Exemplar:
    """A single past draft retained as a similar-deliverable seed."""

    id: str                       # stable hash of (chain_id, target_id) or user-supplied
    chain_id: str                 # partition key — only same-chain exemplars are retrieved
    target_id: str                # e.g. "acme_robotics::march_2026"
    draft: str                    # the rendered deliverable text
    score_pct: float | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ExemplarHit:
    exemplar: Exemplar
    similarity: float             # 0..1, higher is more similar


# ---------------------------- protocol ----------------------------


class ExemplarStore(Protocol):
    """Three operations cover the whole product surface."""

    def upsert(self, exemplar: Exemplar) -> None: ...
    def search(self, chain_id: str, query: str, top_k: int = 3) -> list[ExemplarHit]: ...
    def count(self, chain_id: str | None = None) -> int: ...


# ---------------------------- null store ----------------------------


class NullExemplarStore:
    """Always-empty store. Default when no Astra credentials are configured."""

    def upsert(self, exemplar: Exemplar) -> None:
        return None

    def search(self, chain_id: str, query: str, top_k: int = 3) -> list[ExemplarHit]:
        return []

    def count(self, chain_id: str | None = None) -> int:
        return 0


# ---------------------------- in-memory store ----------------------------


class InMemoryExemplarStore:
    """Small cosine-similarity store backed by character-trigram embeddings.

    Deterministic and offline. Used in tests so the deliverable factory's
    exemplar-injection path can be exercised without reaching Astra.
    """

    def __init__(self) -> None:
        self._items: dict[tuple[str, str], Exemplar] = {}

    def upsert(self, exemplar: Exemplar) -> None:
        self._items[(exemplar.chain_id, exemplar.id)] = exemplar

    def search(self, chain_id: str, query: str, top_k: int = 3) -> list[ExemplarHit]:
        q = _trigram_vec(query)
        scored: list[ExemplarHit] = []
        for (cid, _), ex in self._items.items():
            if cid != chain_id:
                continue
            sim = _cosine(q, _trigram_vec(ex.draft))
            scored.append(ExemplarHit(exemplar=ex, similarity=sim))
        scored.sort(key=lambda h: h.similarity, reverse=True)
        return scored[:top_k]

    def count(self, chain_id: str | None = None) -> int:
        if chain_id is None:
            return len(self._items)
        return sum(1 for (cid, _) in self._items if cid == chain_id)


def _trigram_vec(text: str) -> dict[str, int]:
    s = text.lower()
    out: dict[str, int] = {}
    for i in range(len(s) - 2):
        tri = s[i : i + 3]
        out[tri] = out.get(tri, 0) + 1
    return out


def _cosine(a: dict[str, int], b: dict[str, int]) -> float:
    if not a or not b:
        return 0.0
    common = set(a) & set(b)
    dot = sum(a[k] * b[k] for k in common)
    na = math.sqrt(sum(v * v for v in a.values()))
    nb = math.sqrt(sum(v * v for v in b.values()))
    return dot / (na * nb) if na and nb else 0.0


# ---------------------------- Astra store ----------------------------


_COLLECTION = "strata_exemplars"
_VECTOR_DIM = 1024  # NV-Embed-v1 default; matches Astra "$vectorize" auto-embed


class AstraExemplarStore:  # pragma: no cover - integration only; covered by live tests
    """DataStax Astra DB Data API store with server-side $vectorize.

    Uses Astra's native auto-embedding ('$vectorize') so the client never has
    to call an embedding API directly — Astra computes the vector from the
    draft text on insert and from the query string on read.
    """

    def __init__(
        self,
        api_endpoint: str | None = None,
        token: str | None = None,
        keyspace: str | None = None,
    ) -> None:
        try:
            from astrapy import DataAPIClient
        except ImportError as e:
            raise ImportError(
                "install with `pip install -e '.[vector]'` to use Astra DB"
            ) from e
        s = get_settings()
        endpoint = api_endpoint or s.astra_api_endpoint
        tok = token or s.astra_token
        ks = keyspace or s.astra_keyspace
        if not (endpoint and tok):
            raise RuntimeError(
                "Astra DB not configured. Set ASTRA_DB_API_ENDPOINT and "
                "ASTRA_DB_APPLICATION_TOKEN."
            )

        client = DataAPIClient(tok)
        self._db = client.get_database(endpoint, keyspace=ks)
        self._collection = self._ensure_collection()

    def _ensure_collection(self):
        try:
            return self._db.get_collection(_COLLECTION)
        except Exception:
            from astrapy.constants import VectorMetric
            return self._db.create_collection(
                _COLLECTION,
                dimension=_VECTOR_DIM,
                metric=VectorMetric.COSINE,
                service={"provider": "nvidia", "modelName": "NV-Embed-QA-4"},
            )

    def upsert(self, exemplar: Exemplar) -> None:
        doc = {
            "_id": exemplar.id,
            "chain_id": exemplar.chain_id,
            "target_id": exemplar.target_id,
            "draft": exemplar.draft,
            "score_pct": exemplar.score_pct,
            "metadata": exemplar.metadata,
            "$vectorize": exemplar.draft,
        }
        self._collection.find_one_and_replace(
            filter={"_id": exemplar.id},
            replacement=doc,
            upsert=True,
        )

    def search(self, chain_id: str, query: str, top_k: int = 3) -> list[ExemplarHit]:
        cursor = self._collection.find(
            filter={"chain_id": chain_id},
            sort={"$vectorize": query},
            limit=top_k,
            include_similarity=True,
        )
        out: list[ExemplarHit] = []
        for doc in cursor:
            ex = Exemplar(
                id=str(doc["_id"]),
                chain_id=doc["chain_id"],
                target_id=doc["target_id"],
                draft=doc["draft"],
                score_pct=doc.get("score_pct"),
                metadata=doc.get("metadata") or {},
            )
            out.append(ExemplarHit(exemplar=ex, similarity=float(doc.get("$similarity", 0.0))))
        return out

    def count(self, chain_id: str | None = None) -> int:
        flt = {"chain_id": chain_id} if chain_id else {}
        return self._collection.count_documents(filter=flt, upper_bound=10_000)


# ---------------------------- selector ----------------------------


def get_default_store() -> ExemplarStore:
    """Returns AstraExemplarStore when configured, else NullExemplarStore."""
    if get_settings().has_astra:
        return AstraExemplarStore()
    return NullExemplarStore()


def make_exemplar_id(chain_id: str, target_id: str) -> str:
    """Stable id derived from chain_id + target_id."""
    return hashlib.sha256(f"{chain_id}::{target_id}".encode()).hexdigest()[:24]
