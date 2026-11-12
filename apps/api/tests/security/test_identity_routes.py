"""Session cookies and login-order checks with an injected captcha transport."""

import secrets
from collections.abc import Iterator
from datetime import UTC, datetime

import httpx
import pytest
from alembic import command
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient

from routepilot.identity.api.routes import create_identity_router, require_role
from routepilot.identity.captcha import TurnstileVerifier
from routepilot.identity.ports import CaptchaResult
from routepilot.identity.service import IdentityService
from routepilot.shared.clock import FixedClock
from routepilot.shared.config import Settings
from routepilot.shared.db.engine import make_engine, migration_config
from routepilot.shared.errors import DomainError
from routepilot.shared.problem import problem


class Captcha:
    calls = 0

    def verify(self, token: str, remote_ip: str | None) -> CaptchaResult:
        self.calls += 1
        return CaptchaResult(not token.startswith("reject"), [])


@pytest.fixture
def identity_client(tmp_path) -> Iterator[TestClient]:
    url = f"sqlite:///{tmp_path}/identity-routes.db"
    command.upgrade(migration_config(url), "head")
    engine = make_engine(url)
    settings = Settings(_env_file=None, app_env="test", secret_key=secrets.token_hex(32))
    service = IdentityService(
        engine, settings, FixedClock(datetime(2026, 11, 16, tzinfo=UTC)), Captcha()
    )
    service.seed_accounts()
    app = FastAPI()

    @app.exception_handler(DomainError)
    async def domain_error(request: Request, exc: DomainError):
        return problem(request, exc.status, exc.code, headers=exc.headers)

    app.include_router(create_identity_router(service, settings))
    app.state.identity = service
    with TestClient(app) as client:
        yield client
    engine.dispose()


def login(
    client: TestClient, *, captcha: str = "accepted", password: str | None = None
) -> httpx.Response:
    settings = client.app.state.identity.settings
    return client.post(
        "/api/v1/auth/login",
        json={
            "email": settings.demo_email,
            "password": password or settings.demo_password,
            "captchaToken": captcha,
        },
        headers={"Origin": settings.origins[0]},
    )


@pytest.mark.ac("AC-FEAT-001-20", "AC-FEAT-001-24", "AC-FEAT-001-25", "AC-FEAT-001-27")
def test_login_cookies_me_logout_and_permissions(identity_client: TestClient) -> None:
    client = identity_client
    assert client.get("/api/v1/auth/captcha-config").json()["provider"] == "turnstile"
    assert client.get("/api/v1/auth/me").status_code == 401
    result = login(client)
    assert result.status_code == 200
    session_cookie = next(
        value for value in result.headers.get_list("set-cookie") if value.startswith("rp_session=")
    )
    assert "HttpOnly" in session_cookie and "SameSite=lax" in session_cookie
    assert client.cookies["rp_csrf"] == result.json()["csrfToken"]
    assert client.get("/api/v1/auth/me").json()["user"]["role"] == "demo"
    with pytest.raises(DomainError, match="FORBIDDEN"):
        request = Request(
            {
                "type": "http",
                "headers": [(b"cookie", f"rp_session={client.cookies['rp_session']}".encode())],
            }
        )
        require_role(client.app.state.identity, "admin")(request)
    assert client.post("/api/v1/auth/logout").status_code == 204
    assert not client.cookies
    assert client.get("/api/v1/auth/me").status_code == 401


@pytest.mark.ac("AC-FEAT-001-21", "AC-FEAT-001-22", "AC-FEAT-001-28")
def test_rejected_origin_captcha_and_rate(identity_client: TestClient) -> None:
    client = identity_client
    service = client.app.state.identity
    before = service.captcha.calls
    assert (
        client.post(
            "/api/v1/auth/login", json={}, headers={"Origin": "https://invalid.example"}
        ).status_code
        == 403
    )
    assert service.captcha.calls == before
    assert login(client, captcha="reject-test").status_code == 400
    invalid = secrets.token_hex(16)
    for _ in range(4):
        assert login(client, password=invalid).status_code == 401
    response = login(client)
    assert response.status_code == 429 and int(response.headers["Retry-After"]) >= 1


@pytest.mark.ac("AC-FEAT-001-22")
def test_turnstile_actual_transport_payload_and_fail_closed() -> None:
    secret = secrets.token_hex(32)
    requests = []

    def verify(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(200, json={"success": True})

    with httpx.Client(transport=httpx.MockTransport(verify)) as client:
        result = TurnstileVerifier(secret, client).verify("captcha-answer", "127.0.0.1")
        assert result.ok and len(requests) == 1
        assert requests[0].url.host == "challenges.cloudflare.com"
        assert (
            b"response=captcha-answer" in requests[0].content
            and b"remoteip=127.0.0.1" in requests[0].content
        )
    for response in (
        httpx.Response(500),
        httpx.Response(200, content="invalid-json"),
        httpx.Response(200, json={"success": False, "error-codes": ["invalid-input-response"]}),
    ):
        with httpx.Client(
            transport=httpx.MockTransport(lambda request, response=response: response)
        ) as client:
            assert not TurnstileVerifier(secret, client).verify("captcha-answer", None).ok
