"""Transactional audit adapter; callers supply only non-secret values."""

from typing import Any

from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from routepilot.identity.repository.models import AuditEvent
from routepilot.shared.clock import Clock


class SqlAuditWriter:
    def __init__(self, engine: Engine, clock: Clock) -> None:
        self.engine = engine
        self.clock = clock

    def record(
        self,
        actor: str,
        action: str,
        entity_type: str,
        entity_id: str | None = None,
        diff: dict[str, Any] | None = None,
        transaction: object | None = None,
    ) -> None:
        event = AuditEvent(
            at=self.clock.now(),
            actor=actor,
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            diff=diff or {},
        )
        if isinstance(transaction, Session):
            transaction.add(event)
        else:
            with Session(self.engine) as session, session.begin():
                session.add(event)
