"""rubric_override table

Revision ID: 0002_rubric_override
Revises: 0001_initial
Create Date: 2026-04-29
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0002_rubric_override"
down_revision: str | None = "0001_initial"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "rubric_override",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("tenant_id", sa.String(length=128), nullable=False),
        sa.Column("rubric_id", sa.String(length=128), nullable=False),
        sa.Column("characteristic_id", sa.String(length=128), nullable=False),
        sa.Column("weight", sa.Float(), nullable=True),
        sa.Column("score_floor", sa.Integer(), nullable=True),
        sa.Column("score_ceiling", sa.Integer(), nullable=True),
        sa.Column("disabled", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(), nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.UniqueConstraint(
            "tenant_id", "rubric_id", "characteristic_id",
            name="uq_rubric_override_tenant_rubric_char",
        ),
    )
    op.create_index("ix_rubric_override_tenant_id", "rubric_override", ["tenant_id"])
    op.create_index("ix_rubric_override_rubric_id", "rubric_override", ["rubric_id"])


def downgrade() -> None:
    op.drop_table("rubric_override")
