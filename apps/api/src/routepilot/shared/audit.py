"""Audit writer port; transaction is opaque to domain consumers."""

from typing import Any, Protocol


class AuditWriter(Protocol):
    def record(
        self,
        actor: str,
        action: str,
        entity_type: str,
        entity_id: str | None = None,
        diff: dict[str, Any] | None = None,
        transaction: object | None = None,
    ) -> None: ...
