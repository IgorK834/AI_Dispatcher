"""The local signing key survives application restarts after migration."""

from pathlib import Path

import pytest
from alembic import command
from fastapi.testclient import TestClient
from sqlalchemy import inspect, text

from routepilot.main import create_app
from routepilot.shared.config import Settings
from routepilot.shared.db.engine import make_engine, migration_config


@pytest.mark.ac("AC-FEAT-000-12")
def test_generated_local_secret_is_persisted(tmp_path: Path) -> None:
    url = f"sqlite:///{tmp_path / 'secret.db'}"
    command.upgrade(migration_config(url), "head")
    first = Settings(app_env="local", database_url=url, secret_key="")
    with TestClient(create_app(first)):
        assert first.secret_key
    second = Settings(app_env="local", database_url=url, secret_key="")
    with TestClient(create_app(second)):
        assert first.secret_key == second.secret_key
    engine = make_engine(url)
    with engine.connect() as connection:
        assert (
            connection.execute(
                text("SELECT count(*) FROM app_meta WHERE key = 'secret_key'")
            ).scalar_one()
            == 1
        )
    assert inspect(engine).has_table("app_meta")
    engine.dispose()
