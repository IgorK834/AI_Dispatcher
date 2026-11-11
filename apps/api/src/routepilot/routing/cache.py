"""Persistent immutable ORS response cache (FEAT-004 FR-3)."""

import hashlib
import json
from collections.abc import Sequence
from datetime import datetime
from decimal import ROUND_HALF_UP, Decimal
from typing import Any

from sqlalchemy import JSON, Text, select
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Mapped, Session, mapped_column

from routepilot.routing.domain import GeoPoint
from routepilot.shared.clock import Clock
from routepilot.shared.db.base import Base, IdMixin
from routepilot.shared.db.types import UtcDateTime


def request_key(kind: str, points: Sequence[GeoPoint], options: dict[str, Any]) -> str:
    rounded = [
        [
            str(Decimal(str(p.lon)).quantize(Decimal("0.00001"), rounding=ROUND_HALF_UP)),
            str(Decimal(str(p.lat)).quantize(Decimal("0.00001"), rounding=ROUND_HALF_UP)),
        ]
        for p in points
    ]
    value = {
        "provider": "ors_driving_car_v1",
        "profile": "driving-car",
        "kind": kind,
        "options": options,
        "points": rounded,
    }
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


class RoutingCacheRow(IdMixin, Base):
    __tablename__ = "routing_cache"
    key: Mapped[str] = mapped_column(Text, unique=True)
    kind: Mapped[str] = mapped_column(Text)
    payload: Mapped[dict[str, Any]] = mapped_column(JSON)
    provider_version: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(UtcDateTime())


class RoutingCache:
    def __init__(self, engine: Engine, clock: Clock) -> None:
        self.engine = engine
        self.clock = clock

    def get(self, key: str) -> dict[str, Any] | None:
        with Session(self.engine) as session:
            row = session.scalar(select(RoutingCacheRow).where(RoutingCacheRow.key == key))
            return row.payload if row is not None else None

    def put(self, key: str, kind: str, payload: dict[str, Any]) -> None:
        with Session(self.engine) as session, session.begin():
            if session.scalar(select(RoutingCacheRow.id).where(RoutingCacheRow.key == key)) is None:
                session.add(
                    RoutingCacheRow(
                        key=key,
                        kind=kind,
                        payload=payload,
                        provider_version="ors_driving_car_v1",
                        created_at=self.clock.now(),
                    )
                )
