"""FEAT-001 authentication semantics on SQLite with an injected captcha transport."""

import secrets
from datetime import UTC, datetime, timedelta

import pytest
from alembic import command
from sqlalchemy import select
from sqlalchemy.orm import Session

from routepilot.identity.ports import CaptchaResult
from routepilot.identity.repository.models import AuditEvent, User, UserSession
from routepilot.identity.service import IdentityService
from routepilot.shared.clock import FixedClock
from routepilot.shared.config import Settings
from routepilot.shared.db.engine import make_engine, migration_config
from routepilot.shared.errors import DomainError


class Captcha:
    def __init__(self, ok: bool = True) -> None:
        self.ok = ok

    def verify(self, token: str, remote_ip: str | None) -> CaptchaResult:
        return CaptchaResult(self.ok, [])


@pytest.fixture
def identity(tmp_path):
    url = f"sqlite:///{tmp_path / 'identity.db'}"
    command.upgrade(migration_config(url), "head")
    engine = make_engine(url)
    settings = Settings(_env_file=None, app_env="test", secret_key=secrets.token_hex(32))
    clock = FixedClock(datetime(2026, 11, 16, tzinfo=UTC))
    service = IdentityService(engine, settings, clock, Captcha())
    service.seed_accounts()
    yield service, engine, settings, clock
    engine.dispose()


@pytest.mark.ac("AC-FEAT-001-20", "AC-FEAT-001-25", "AC-FEAT-001-29", "AC-FEAT-001-31")
def test_login_stores_only_session_hash_and_logout_invalidates(identity) -> None:
    service, engine, settings, _ = identity
    service.seed_accounts()
    result = service.login(settings.demo_email, settings.demo_password, "pass", "127.0.0.1", "test")
    principal = service.resolve_session(result.token)
    assert principal is not None and principal.role == "demo"
    assert service.csrf_token(principal) == result.csrf_token
    with Session(engine) as session:
        assert len(session.scalars(select(User)).all()) == 2
        row = session.scalar(select(UserSession))
        assert row is not None and row.token_hash != result.token
        user = session.get(User, principal.id)
        assert user is not None and user.password_hash.startswith("$argon2id$")
    service.logout(result.token)
    assert service.resolve_session(result.token) is None


@pytest.mark.ac("AC-FEAT-001-21", "AC-FEAT-001-22", "AC-FEAT-001-30")
def test_credentials_are_generic_and_captcha_precedes_password(identity) -> None:
    service, engine, settings, _ = identity
    for email in (settings.demo_email, "missing@example.invalid"):
        with pytest.raises(DomainError, match="INVALID_CREDENTIALS"):
            service.login(email, "wrong", "pass", "127.0.0.1", "test")
    service.captcha = Captcha(False)
    with pytest.raises(DomainError, match="CAPTCHA_FAILED"):
        service.login(settings.demo_email, settings.demo_password, "fail", "127.0.0.1", "test")
    with Session(engine) as session:
        diffs = [row.diff for row in session.scalars(select(AuditEvent))]
        assert len(diffs) == 3
        assert all("password" not in str(diff) and "token" not in str(diff) for diff in diffs)


@pytest.mark.ac("AC-FEAT-001-23", "AC-FEAT-001-26", "AC-FEAT-001-28")
def test_csrf_expiry_and_login_limit(identity) -> None:
    service, _, settings, clock = identity
    result = service.login(settings.demo_email, settings.demo_password, "pass", "1", "test")
    principal = service.resolve_session(result.token)
    assert principal is not None
    service.validate_csrf(principal, result.csrf_token, result.csrf_token)
    with pytest.raises(DomainError, match="CSRF_FAILED"):
        service.validate_csrf(principal, result.csrf_token, "wrong")
    service.clock = FixedClock(clock.now() + timedelta(hours=12, seconds=1))
    assert service.resolve_session(result.token) is None
    service.clock = clock
    for _ in range(4):
        with pytest.raises(DomainError, match="INVALID_CREDENTIALS"):
            service.login(settings.demo_email, "wrong", "pass", "1", "test")
    with pytest.raises(DomainError, match="RATE_LIMITED"):
        service.login(settings.demo_email, "wrong", "pass", "1", "test")
