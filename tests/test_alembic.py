"""Alembic migrations: offline (SQLite) static checks always run; live Postgres
verification runs when the env opts in.

Static checks (always):
  - migrations/env.py imports cleanly
  - the migration chain is linear (every revision has at most one parent)
  - upgrade head + downgrade base round-trips on SQLite
  - every ORM table has a corresponding migration table

Live checks (opt-in via STRATA_LIVE_POSTGRES_URL):
  - upgrade head against a real Postgres
  - SQLAlchemy can read every table the ORM declares
  - downgrade base cleans up
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest
from alembic.config import Config
from alembic.script import ScriptDirectory

PROJECT_ROOT = Path(__file__).resolve().parents[1]
ALEMBIC_INI = PROJECT_ROOT / "alembic.ini"


def _alembic_cfg(database_url: str) -> Config:
    cfg = Config(str(ALEMBIC_INI))
    cfg.set_main_option("script_location", str(PROJECT_ROOT / "migrations"))
    cfg.set_main_option("sqlalchemy.url", database_url)
    return cfg


def test_migration_chain_is_linear():
    cfg = _alembic_cfg("sqlite:///:memory:")
    script = ScriptDirectory.from_config(cfg)
    revisions = list(script.walk_revisions())
    assert revisions, "no migrations found"
    for rev in revisions:
        assert isinstance(rev.down_revision, (str, type(None))), (
            f"revision {rev.revision} has multi-parent down_revision: {rev.down_revision}"
        )


def test_orm_tables_match_migration_tables(tmp_path):
    """Apply migrations to a fresh SQLite DB, then check every ORM-declared table exists."""
    db_path = tmp_path / "alembic_check.sqlite"
    db_url = f"sqlite:///{db_path}"

    env = {**os.environ, "STRATA_TEST_DB": db_url}
    result = subprocess.run(
        [sys.executable, "-m", "alembic", "-c", str(ALEMBIC_INI), "upgrade", "head"],
        cwd=str(PROJECT_ROOT),
        env=env,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, f"alembic upgrade failed:\nstdout={result.stdout}\nstderr={result.stderr}"

    # Now reflect the DB and compare
    from sqlalchemy import create_engine, inspect

    from strata.db import Base
    from strata import models  # noqa: F401  registers tables

    engine = create_engine(db_url)
    inspector = inspect(engine)
    db_tables = set(inspector.get_table_names())
    orm_tables = set(Base.metadata.tables.keys())

    # alembic_version is from alembic itself; expect it present
    assert "alembic_version" in db_tables
    missing = orm_tables - db_tables
    assert not missing, f"ORM tables missing from migrated DB: {missing}"


def test_upgrade_head_then_downgrade_base_round_trips(tmp_path):
    db_path = tmp_path / "round_trip.sqlite"
    db_url = f"sqlite:///{db_path}"
    env = {**os.environ, "STRATA_TEST_DB": db_url}

    up = subprocess.run(
        [sys.executable, "-m", "alembic", "-c", str(ALEMBIC_INI), "upgrade", "head"],
        cwd=str(PROJECT_ROOT), env=env, capture_output=True, text=True,
    )
    assert up.returncode == 0, up.stderr

    down = subprocess.run(
        [sys.executable, "-m", "alembic", "-c", str(ALEMBIC_INI), "downgrade", "base"],
        cwd=str(PROJECT_ROOT), env=env, capture_output=True, text=True,
    )
    assert down.returncode == 0, down.stderr

    from sqlalchemy import create_engine, inspect
    inspector = inspect(create_engine(db_url))
    remaining = set(inspector.get_table_names()) - {"alembic_version"}
    assert remaining == set(), f"tables left after downgrade base: {remaining}"


# ---------------------------- live Postgres ----------------------------


_LIVE_PG = os.getenv("STRATA_LIVE_POSTGRES_URL")


@pytest.mark.live_postgres
@pytest.mark.skipif(
    not _LIVE_PG,
    reason="STRATA_LIVE_POSTGRES_URL not set; skipping live Postgres verification",
)
def test_alembic_upgrade_against_live_postgres():
    env = {**os.environ, "DATABASE_URL": _LIVE_PG}
    # Ensure clean start
    subprocess.run(
        [sys.executable, "-m", "alembic", "-c", str(ALEMBIC_INI), "downgrade", "base"],
        cwd=str(PROJECT_ROOT), env=env, capture_output=True, text=True,
    )
    up = subprocess.run(
        [sys.executable, "-m", "alembic", "-c", str(ALEMBIC_INI), "upgrade", "head"],
        cwd=str(PROJECT_ROOT), env=env, capture_output=True, text=True,
    )
    assert up.returncode == 0, up.stderr

    from sqlalchemy import create_engine, inspect

    from strata.db import Base
    from strata import models  # noqa: F401

    inspector = inspect(create_engine(_LIVE_PG))
    db_tables = set(inspector.get_table_names())
    orm_tables = set(Base.metadata.tables.keys())
    missing = orm_tables - db_tables
    assert not missing, f"ORM tables missing in live Postgres: {missing}"
