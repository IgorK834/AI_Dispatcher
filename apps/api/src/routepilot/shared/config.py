"""Settings shared by the application composition root."""

from decimal import Decimal
from typing import Literal, Self

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_env: Literal["local", "test", "demo", "production"] = "local"
    database_url: str = "sqlite:///./data/routepilot.db"
    agents_db_path: str = "./data/agents.db"
    cors_allowed_origins: str = "http://localhost:3000"
    secret_key: str = Field(default="", repr=False)
    turnstile_site_key: str = "1x00000000000000000000AA"
    turnstile_secret_key: str = Field(default="1x0000000000000000000000000000000AA", repr=False)
    admin_email: str = "admin@example.invalid"
    admin_password: str = Field(default="local-admin-password", repr=False)
    demo_email: str = "demo@example.invalid"
    demo_password: str = Field(default="local-demo-password", repr=False)
    google_api_key: str = Field(default="", repr=False)
    anthropic_api_key: str = Field(default="", repr=False)
    openai_api_key: str = Field(default="", repr=False)
    agent_model_policy: str = ""
    ors_api_key: str = Field(default="", repr=False)
    mock_seed: int = 42
    mock_reference_date: str = ""
    session_ttl_hours: int = Field(default=12, ge=1)
    login_rate_limit_per_ip: str = "10/minute"
    login_rate_limit_per_account: str = "5/minute"
    password_min_length: int = Field(default=12, ge=1)
    ors_base_url: str = "https://api.openrouteservice.org"
    routing_matrix_path: str = "data/mock/routing-matrix.json"
    worker_poll_interval_ms: int = Field(default=500, ge=1)
    job_heartbeat_stale_s: int = Field(default=60, ge=1)
    van_speed_factor: Decimal = Field(default=Decimal("1.08"), gt=0)
    agent_recursion_limit: int = Field(default=25, ge=1)
    agent_max_tool_calls: int = Field(default=6, ge=1)
    agent_run_timeout_s: float = Field(default=120, gt=0)
    agent_run_token_budget: int = Field(default=60000, ge=1)
    agent_daily_token_budget: int = Field(default=500000, ge=1)
    agent_daily_token_budget_demo: int = Field(default=100000, ge=1)
    approval_ttl_min: int = Field(default=30, ge=1)

    @property
    def origins(self) -> list[str]:
        return [
            part.strip().rstrip("/")
            for part in self.cors_allowed_origins.split(",")
            if part.strip()
        ]

    @model_validator(mode="after")
    def validate_settings(self) -> Self:
        if any("*" in origin for origin in self.origins):
            raise ValueError("CORS wildcard origins are forbidden")
        if not self.origins and self.app_env != "test":
            raise ValueError("CORS allowlist must not be empty")
        if self.app_env in ("demo", "production"):
            if (
                not self.secret_key
                or self.admin_password == type(self).model_fields["admin_password"].default
                or self.demo_password == type(self).model_fields["demo_password"].default
            ):
                raise ValueError("demo/production requires a SECRET_KEY and own account passwords")
            if self.turnstile_site_key.startswith(
                ("1x", "2x", "3x")
            ) or self.turnstile_secret_key.startswith(("1x", "2x", "3x")):
                raise ValueError("demo/production forbids Turnstile test keys")
        return self
