"""Builders for the full application with a logged-in session, and payloads for fleet tests."""

import secrets
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

from alembic import command
from fastapi.testclient import TestClient
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from routepilot.identity.ports import CaptchaResult
from routepilot.identity.repository.models import User
from routepilot.main import create_app
from routepilot.shared.config import Settings
from routepilot.shared.db.engine import make_engine, migration_config

ORIGIN = "http://localhost:3000"


class PassCaptcha:
    def verify(self, token: str, remote_ip: str | None) -> CaptchaResult:
        return CaptchaResult(True, [])


def login(client: TestClient, role: str = "admin") -> str:
    """Log in with a seeded account (a dispatcher account is created on demand).

    Returns the CSRF token.
    """
    identity = client.app.state.services.identity
    settings = identity.settings
    if role == "dispatcher":
        email, password = "dispatcher@example.invalid", "dispatcher-test-password"
        with Session(identity.engine) as session, session.begin():
            if session.scalar(select(User.id).where(User.email == email)) is None:
                now = identity.clock.now()
                session.add(
                    User(
                        email=email,
                        password_hash=identity.password_hasher.hash(password),
                        role="dispatcher",
                        locale="en",
                        is_active=True,
                        failed_logins=0,
                        created_at=now,
                        updated_at=now,
                    )
                )
    elif role == "admin":
        email, password = settings.admin_email, settings.admin_password
    else:
        email, password = settings.demo_email, settings.demo_password
    response = client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": password, "captchaToken": "pass"},
        headers={"Origin": ORIGIN},
    )
    response.raise_for_status()
    token: str = response.json()["csrfToken"]
    return token


@contextmanager
def api_client(
    tmp_path: Path, role: str = "admin", *, seeded: bool = False
) -> Iterator[TestClient]:
    """The real application on a migrated temporary database, logged in with Origin and CSRF.

    Unless `seeded`, the first-start demo data is marked as done, so the fleet starts empty.
    """
    url = f"sqlite:///{tmp_path / 'api.db'}"
    command.upgrade(migration_config(url), "head")
    if not seeded:
        engine = make_engine(url)
        with engine.begin() as connection:
            connection.execute(
                text("INSERT INTO app_meta (key, value, updated_at) VALUES (:k, :v, :t)"),
                {"k": "seed_version", "v": '{"version": 1}', "t": "2026-11-16T00:00:00+00:00"},
            )
        engine.dispose()
    settings = Settings(
        _env_file=None,
        app_env="test",
        database_url=url,
        agents_db_path=str(tmp_path / "agents.db"),
        secret_key=secrets.token_hex(32),
    )
    with TestClient(create_app(settings, captcha=PassCaptcha())) as client:
        token = login(client, role)
        client.headers.update({"Origin": ORIGIN, "X-CSRF-Token": token})
        yield client


def cost_profile(name: str = "Factory costs") -> dict[str, Any]:
    return {
        "name": name,
        "currency": "EUR",
        "fuelPriceMinorPerL": 181,
        "driverCostMinorPerHour": 1400,
        "vehicleCostMinorPerKm": 12,
        "accommodationMinor": 5500,
        "perDiem": {"PL": 1059},
        "tolls": {"perKm": {"DE": 0}, "annualVignettes": []},
        "fxRates": {"PLN": "4.25"},
        "minProfitMinor": 0,
        "minMarginPct": "0",
    }


def vehicle(profile_id: str, label: str = "FACTORY-BUS") -> dict[str, Any]:
    return {
        "label": label,
        "vehicleType": "VEHICLE_UP_TO_3_5_T",
        "bodyType": "CURTAIN_SIDER",
        "innerLengthM": "4.85",
        "innerWidthM": "2.10",
        "innerHeightM": "2.10",
        "palletPlaces": 10,
        "layoutTemplate": "EUR_MIXED_6X4",
        "sideAccess": "BOTH",
        "payloadKg": 1085,
        "gvwKg": 3500,
        "sleeperCab": False,
        "fuel": {
            "lPer100kmEmptyAt90": "11.0",
            "lPer100kmFullAt90": "13.5",
            "speedCurve": "VAN_DEFAULT_V1",
        },
        "costProfileId": profile_id,
    }


def driver(index: int = 0, **extra: Any) -> dict[str, Any]:
    return {
        "name": f"Fictional Driver {index}",
        "homeCity": "Katowice" if index % 2 else "Wrocław",
        "homeCountry": "PL",
        "homeLat": 50.2649,
        "homeLon": 19.0238,
        **extra,
    }


def driver_state(latitude: float = 50.0, **extra: Any) -> dict[str, Any]:
    counters = dict.fromkeys(
        (
            "workTodayMin",
            "driveTodayMin",
            "workSinceBreakMin",
            "driveSinceBreakMin",
            "workWeekMin",
            "driveWeekMin",
            "drivePrevWeekMin",
        ),
        0,
    )
    return {
        "currentCity": "Katowice",
        "currentLat": latitude,
        "currentLon": 19.0,
        "availableFrom": "2026-11-16T08:00:00Z",
        **counters,
        **extra,
    }


def offer(**extra: Any) -> dict[str, Any]:
    return {
        "description": "Pallets Katowice to Berlin",
        "revenue": {"amountMinor": 15000, "currency": "EUR"},
        "weightKg": 500,
        "palletCount": 3,
        "palletType": "EUR_1200x800",
        "requiredBodyTypes": ["CURTAIN_SIDER"],
        "stops": [
            {
                "stopType": "LOADING",
                "city": "Katowice",
                "countryCode": "PL",
                "windowStart": "2026-11-16T08:00:00Z",
                "windowEnd": "2026-11-16T12:00:00Z",
            },
            {
                "stopType": "UNLOADING",
                "city": "Berlin",
                "countryCode": "DE",
                "windowStart": "2026-11-17T08:00:00Z",
                "windowEnd": "2026-11-17T12:00:00Z",
            },
        ],
        **extra,
    }
