"""AC-FEAT-000-12: safe local defaults and production validation."""

from pathlib import Path

import pytest
from pydantic import ValidationError

from routepilot.shared.config import Settings


@pytest.mark.ac("AC-FEAT-000-12")
def test_production_rejects_local_defaults() -> None:
    with pytest.raises(ValidationError, match=r"production|demo"):
        Settings(app_env="production")


@pytest.mark.ac("AC-FEAT-000-12")
def test_origins_are_normalized_and_wildcards_rejected() -> None:
    assert Settings(
        cors_allowed_origins=" http://localhost:3000/ , https://example.test/ "
    ).origins == ["http://localhost:3000", "https://example.test"]
    for value in ["*", "https://*.example.test"]:
        with pytest.raises(ValidationError, match="wildcard"):
            Settings(cors_allowed_origins=value)
    with pytest.raises(ValidationError, match="empty"):
        Settings(app_env="local", cors_allowed_origins="")


@pytest.mark.ac("AC-FEAT-000-12")
def test_env_examples_are_complete_and_optional_keys_empty() -> None:
    root = Path(__file__).resolve().parents[4]
    values = dict(
        line.split("=", 1)
        for line in (root / "apps/api/.env.example").read_text().splitlines()
        if line and not line.startswith("#")
    )
    required = {
        "APP_ENV",
        "DATABASE_URL",
        "AGENTS_DB_PATH",
        "CORS_ALLOWED_ORIGINS",
        "SECRET_KEY",
        "TURNSTILE_SITE_KEY",
        "TURNSTILE_SECRET_KEY",
        "ADMIN_EMAIL",
        "ADMIN_PASSWORD",
        "DEMO_EMAIL",
        "DEMO_PASSWORD",
        "GOOGLE_API_KEY",
        "ANTHROPIC_API_KEY",
        "OPENAI_API_KEY",
        "AGENT_MODEL_POLICY",
        "ORS_API_KEY",
        "MOCK_SEED",
        "MOCK_REFERENCE_DATE",
    }
    assert required <= values.keys()
    for name in [
        "GOOGLE_API_KEY",
        "ANTHROPIC_API_KEY",
        "OPENAI_API_KEY",
        "ORS_API_KEY",
        "SECRET_KEY",
    ]:
        assert values[name] == ""
    assert (
        "NEXT_PUBLIC_API_BASE_URL=http://localhost:8000"
        in (root / "apps/web/.env.example").read_text()
    )
