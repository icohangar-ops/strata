"""SQLAlchemy models for the three persisted tables: rubric, rubric_score, run_log."""
from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID, uuid4

from sqlalchemy import JSON, DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from strata.db import Base


class Rubric(Base):
    """A versioned rubric definition serialized from a YAML / Pydantic Rubric."""

    __tablename__ = "rubric"
    __table_args__ = (UniqueConstraint("rubric_id", "version", name="uq_rubric_id_version"),)

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    rubric_id: Mapped[str] = mapped_column(String(128), index=True)
    scope: Mapped[str] = mapped_column(String(32), index=True)
    name: Mapped[str] = mapped_column(String(256))
    version: Mapped[int] = mapped_column(Integer, default=1)
    definition: Mapped[dict] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))

    scores: Mapped[list[RubricScore]] = relationship(back_populates="rubric")


class RubricScore(Base):
    """One application of a rubric to a target (deliverable draft, capability snapshot, etc)."""

    __tablename__ = "rubric_score"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    rubric_db_id: Mapped[UUID] = mapped_column(ForeignKey("rubric.id"), index=True)
    target_id: Mapped[str] = mapped_column(String(256), index=True)
    target_kind: Mapped[str] = mapped_column(String(32), index=True)
    iteration: Mapped[int] = mapped_column(Integer, default=0)
    weighted_total: Mapped[float] = mapped_column(Float)
    normalized_pct: Mapped[float] = mapped_column(Float)
    passed: Mapped[bool] = mapped_column(default=False)
    detail: Mapped[dict] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc), index=True)

    rubric: Mapped[Rubric] = relationship(back_populates="scores")
    run_log_id: Mapped[UUID | None] = mapped_column(ForeignKey("run_log.id"), nullable=True)


class RunLog(Base):
    """A single end-to-end orchestrator run (e.g. one board-pack generation)."""

    __tablename__ = "run_log"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    chain_id: Mapped[str] = mapped_column(String(64), index=True)
    inputs_hash: Mapped[str] = mapped_column(String(64))
    started_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc), index=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    status: Mapped[str] = mapped_column(String(32), default="running", index=True)
    inputs: Mapped[dict] = mapped_column(JSON)
    outputs: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)


class RubricOverride(Base):
    """Per-tenant override for a single characteristic on a rubric.

    - `weight`: replaces the characteristic weight at decide time. Sibling
      characteristic weights are renormalized to keep group sum-to-1.
    - `score_floor` / `score_ceiling`: clamp self-reported scores within bounds.
    - `disabled`: drop the characteristic from scoring entirely.
    """

    __tablename__ = "rubric_override"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id", "rubric_id", "characteristic_id",
            name="uq_rubric_override_tenant_rubric_char",
        ),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    tenant_id: Mapped[str] = mapped_column(String(128), index=True)
    rubric_id: Mapped[str] = mapped_column(String(128), index=True)
    characteristic_id: Mapped[str] = mapped_column(String(128))
    weight: Mapped[float | None] = mapped_column(Float, nullable=True)
    score_floor: Mapped[int | None] = mapped_column(Integer, nullable=True)
    score_ceiling: Mapped[int | None] = mapped_column(Integer, nullable=True)
    disabled: Mapped[bool] = mapped_column(default=False)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc)
    )
