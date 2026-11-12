"""Password, session, captcha and audit orchestration."""

import hashlib
import hmac
import math
import secrets
import time
from datetime import timedelta
from uuid import UUID

from argon2 import PasswordHasher
from argon2.exceptions import VerificationError
from limits import parse
from slowapi import Limiter
from sqlalchemy import delete, select
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from routepilot.identity.captcha import TurnstileVerifier
from routepilot.identity.domain.models import LoginResult, UserView
from routepilot.identity.ports import CaptchaVerifier
from routepilot.identity.repository.audit import SqlAuditWriter
from routepilot.identity.repository.models import User, UserSession
from routepilot.shared.auth import Principal
from routepilot.shared.clock import Clock
from routepilot.shared.config import Settings
from routepilot.shared.errors import DomainError


class IdentityService:
    def __init__(
        self,
        engine: Engine,
        settings: Settings,
        clock: Clock,
        captcha: CaptchaVerifier | None = None,
    ) -> None:
        self.engine, self.settings, self.clock = engine, settings, clock
        self.captcha = captcha or TurnstileVerifier(settings.turnstile_secret_key)
        self.password_hasher = PasswordHasher()
        self.dummy_hash = self.password_hasher.hash("unused-account-password")
        self.audit = SqlAuditWriter(engine, clock)
        self.limiter = Limiter(key_func=lambda: "login")

    def close(self) -> None:
        if isinstance(self.captcha, TurnstileVerifier):
            self.captcha.close()

    def seed_accounts(self) -> None:
        with Session(self.engine) as session, session.begin():
            if session.scalar(select(User.id).limit(1)) is not None:
                return
            now = self.clock.now()
            for email, password, role in (
                (self.settings.admin_email, self.settings.admin_password, "admin"),
                (self.settings.demo_email, self.settings.demo_password, "demo"),
            ):
                session.add(
                    User(
                        email=email.strip().casefold(),
                        password_hash=self.password_hasher.hash(password),
                        role=role,
                        locale="en",
                        is_active=True,
                        failed_logins=0,
                        created_at=now,
                        updated_at=now,
                    )
                )

    def check_login_rate(self, email: str, remote_ip: str | None) -> None:
        for scope, key, setting in (
            ("login-ip", remote_ip or "unknown", self.settings.login_rate_limit_per_ip),
            ("login-account", email.strip().casefold(), self.settings.login_rate_limit_per_account),
        ):
            limit = parse(setting)
            if not self.limiter.limiter.hit(limit, scope, key):
                reset, _ = self.limiter.limiter.get_window_stats(limit, scope, key)
                raise DomainError(
                    "RATE_LIMITED",
                    429,
                    headers={"Retry-After": str(max(1, math.ceil(reset - time.time())))},
                )

    def login(
        self,
        email: str,
        password: str,
        captcha_token: str,
        remote_ip: str | None,
        user_agent: str,
        *,
        rate_checked: bool = False,
    ) -> LoginResult:
        email = email.strip().casefold()
        if not rate_checked:
            self.check_login_rate(email, remote_ip)
        if not self.captcha.verify(captcha_token, remote_ip).ok:
            self.audit.record("anonymous", "auth.login_failed", "user", diff={"reason": "captcha"})
            raise DomainError("CAPTCHA_FAILED", 400)
        with Session(self.engine) as session, session.begin():
            user = session.scalar(select(User).where(User.email == email, User.is_active.is_(True)))
            try:
                valid: bool = self.password_hasher.verify(
                    user.password_hash if user else self.dummy_hash, password
                )
            except VerificationError:
                valid = False
            if not valid or user is None:
                self.audit.record(
                    "anonymous",
                    "auth.login_failed",
                    "user",
                    diff={"reason": "credentials"},
                    transaction=session,
                )
                invalid = True
            else:
                invalid = False
                now = self.clock.now()
                token = secrets.token_urlsafe(32)
                row = UserSession(
                    token_hash=hashlib.sha256(token.encode()).hexdigest(),
                    user_id=user.id,
                    created_at=now,
                    expires_at=now + timedelta(hours=self.settings.session_ttl_hours),
                    ip_hash=hashlib.sha256((remote_ip or "").encode()).hexdigest(),
                    ua_hash=hashlib.sha256(user_agent.encode()).hexdigest(),
                )
                session.add(row)
                session.flush()
                user.last_login_at = now
                user.updated_at = now
                principal = Principal.model_validate(
                    {"id": user.id, "role": user.role, "locale": user.locale, "session_id": row.id}
                )
                self.audit.record(
                    str(user.id), "auth.login", "user", str(user.id), transaction=session
                )
                result = LoginResult(principal, self._view(user), token, self.csrf_token(principal))
        if invalid:
            raise DomainError("INVALID_CREDENTIALS", 401)
        return result

    def resolve_session(self, token: str | None) -> Principal | None:
        if not token:
            return None
        with Session(self.engine) as session, session.begin():
            row = session.scalar(
                select(UserSession).where(
                    UserSession.token_hash == hashlib.sha256(token.encode()).hexdigest()
                )
            )
            if row is None:
                return None
            user = session.get(User, row.user_id)
            if row.expires_at <= self.clock.now() or user is None or not user.is_active:
                session.delete(row)
                return None
            return Principal.model_validate(
                {"id": user.id, "role": user.role, "locale": user.locale, "session_id": row.id}
            )

    def require_user(self, token: str | None) -> Principal:
        principal = self.resolve_session(token)
        if principal is None:
            raise DomainError("UNAUTHENTICATED", 401)
        return principal

    def csrf_token(self, principal: Principal) -> str:
        return hmac.new(
            self.settings.secret_key.encode(), str(principal.session_id).encode(), hashlib.sha256
        ).hexdigest()

    def validate_csrf(self, principal: Principal, cookie: str | None, header: str | None) -> None:
        expected = self.csrf_token(principal)
        if (
            not cookie
            or not header
            or not hmac.compare_digest(cookie, header)
            or not hmac.compare_digest(expected, header)
        ):
            raise DomainError("CSRF_FAILED", 403)

    def public_user(self, user_id: UUID) -> UserView:
        with Session(self.engine) as session:
            user = session.get(User, user_id)
            if user is None:
                raise DomainError("NOT_FOUND", 404)
            return self._view(user)

    def logout(self, token: str) -> None:
        principal = self.require_user(token)
        with Session(self.engine) as session, session.begin():
            session.execute(delete(UserSession).where(UserSession.id == principal.session_id))
            self.audit.record(
                str(principal.id),
                "auth.logout",
                "session",
                str(principal.session_id),
                transaction=session,
            )

    def change_password(self, user_id: UUID, password: str) -> None:
        if len(password) < self.settings.password_min_length:
            raise DomainError("VALIDATION_ERROR", 422)
        with Session(self.engine) as session, session.begin():
            user = session.get(User, user_id)
            if user is None:
                raise DomainError("NOT_FOUND", 404)
            user.password_hash = self.password_hasher.hash(password)
            user.updated_at = self.clock.now()
            session.execute(delete(UserSession).where(UserSession.user_id == user_id))

    @staticmethod
    def _view(user: User) -> UserView:
        return UserView.model_validate(
            {"id": user.id, "email": user.email, "role": user.role, "locale": user.locale}
        )
