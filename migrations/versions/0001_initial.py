"""initial schema: rubric, rubric_score, run_log

Revision ID: 0001_initial
Revises:
Create Date: 2026-04-29
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0001_initial"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "rubric",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("rubric_id", sa.String(length=128), nullable=False),
        sa.Column("scope", sa.String(length=32), nullable=False),
        sa.Column("name", sa.String(length=256), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("definition", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.UniqueConstraint("rubric_id", "version", name="uq_rubric_id_version"),
    )
    op.create_index("ix_rubric_rubric_id", "rubric", ["rubric_id"])
    op.create_index("ix_rubric_scope", "rubric", ["scope"])

    op.create_table(
        "run_log",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("chain_id", sa.String(length=64), nullable=False),
        sa.Column("inputs_hash", sa.String(length=64), nullable=False),
        sa.Column("started_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("finished_at", sa.DateTime(), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="running"),
        sa.Column("inputs", sa.JSON(), nullable=False),
        sa.Column("outputs", sa.JSON(), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
    )
    op.create_index("ix_run_log_chain_id", "run_log", ["chain_id"])
    op.create_index("ix_run_log_started_at", "run_log", ["started_at"])
    op.create_index("ix_run_log_status", "run_log", ["status"])

    op.create_table(
        "rubric_score",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("rubric_db_id", sa.Uuid(), sa.ForeignKey("rubric.id"), nullable=False),
        sa.Column("target_id", sa.String(length=256), nullable=False),
        sa.Column("target_kind", sa.String(length=32), nullable=False),
        sa.Column("iteration", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("weighted_total", sa.Float(), nullable=False),
        sa.Column("normalized_pct", sa.Float(), nullable=False),
        sa.Column("passed", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("detail", sa.JSON(), nullable=False),
        sa.Column("run_log_id", sa.Uuid(), sa.ForeignKey("run_log.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
    )
    op.create_index("ix_rubric_score_rubric_db_id", "rubric_score", ["rubric_db_id"])
    op.create_index("ix_rubric_score_target_id", "rubric_score", ["target_id"])
    op.create_index("ix_rubric_score_target_kind", "rubric_score", ["target_kind"])
    op.create_index("ix_rubric_score_created_at", "rubric_score", ["created_at"])


def downgrade() -> None:
    op.drop_table("rubric_score")
    op.drop_table("run_log")
    op.drop_table("rubric")
