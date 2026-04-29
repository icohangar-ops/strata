"""L3: Director runs the board-pack chain and (optionally) persists to a sqlite DB."""
from __future__ import annotations

from strata.orchestrator.director import Director


def test_director_runs_chain_without_persistence():
    inputs = {
        "company": "Acme",
        "period": "Mar 2026",
        "revenue_actual": 100,
        "revenue_budget": 110,
    }
    run = Director(persist=False).run_board_pack(inputs)
    assert run.chain_id == "chain.board_pack.v1"
    assert run.factory_result.iterations >= 1


def test_director_persists_to_sqlite(tmp_path, monkeypatch):
    monkeypatch.setenv("STRATA_TEST_DB", f"sqlite:///{tmp_path / 'd.sqlite'}")

    # reset cached settings + engine
    from strata import config, db
    config.get_settings.cache_clear()
    db._engine = None
    db._SessionLocal = None

    # create tables on the fresh engine
    from strata.db import Base, get_engine
    from strata import models  # noqa: F401  registers tables
    engine = get_engine()
    Base.metadata.create_all(engine)

    inputs = {"company": "Acme", "period": "Mar 2026"}
    run = Director(persist=True).run_board_pack(inputs)

    from sqlalchemy import select
    from strata.db import session_scope
    from strata.models import RubricScore, RunLog

    with session_scope() as s:
        run_row = s.execute(select(RunLog).where(RunLog.chain_id == "chain.board_pack.v1")).scalar_one()
        assert run_row.status in {"passed", "failed"}
        scores = s.execute(select(RubricScore).where(RubricScore.run_log_id == run_row.id)).scalars().all()
        assert len(scores) == run.factory_result.iterations
