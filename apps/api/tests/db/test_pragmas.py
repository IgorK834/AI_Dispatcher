"""AC-FEAT-001-01: every file connection installs the SQLite PRAGMAs."""

from pathlib import Path

import pytest

from routepilot.shared.db.engine import make_engine


@pytest.mark.ac("AC-FEAT-001-01")
def test_pragmas_on_each_connection(tmp_path: Path) -> None:
    engine = make_engine(f"sqlite:///{tmp_path / 'pragmas.db'}")
    for _ in range(2):
        with engine.connect() as connection:
            assert connection.exec_driver_sql("PRAGMA journal_mode").scalar_one() == "wal"
            assert connection.exec_driver_sql("PRAGMA foreign_keys").scalar_one() == 1
            assert connection.exec_driver_sql("PRAGMA busy_timeout").scalar_one() == 5000
        engine.dispose()
