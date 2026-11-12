"""Composition-root SQL adapter; agent modules depend only on AgentStore.

The existing app_meta JSON keyspace holds each run's durable SSE journal. This
keeps event IDs independent from trace sequence numbers without a schema change.
Only the composition root instantiates this adapter or accesses its tables.
"""

import json
from datetime import UTC, datetime
from threading import RLock
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import MetaData, Table, func, select
from sqlalchemy.engine import Engine

from routepilot.agents.ports import RecordKind
from routepilot.agents.schemas import TraceStep
from routepilot.shared.clock import Clock


def _json(value: Any) -> Any:
    return json.loads(json.dumps(value, default=str))


def _row(value: Any) -> dict[str, Any]:
    return {
        key: (
            item.replace(tzinfo=UTC) if isinstance(item, datetime) and item.tzinfo is None else item
        )
        for key, item in dict(value).items()
    }


class SqlAgentStore:
    def __init__(self, engine: Engine, clock: Clock) -> None:
        self.engine, self.clock = engine, clock
        self.metadata = MetaData()
        self._tables: dict[str, Table] = {}
        self._lock = RLock()

    def _table(self, name: str) -> Table:
        with self._lock:
            if name not in self._tables:
                self._tables[name] = Table(name, self.metadata, autoload_with=self.engine)
            return self._tables[name]

    @staticmethod
    def _values(values: dict[str, Any]) -> dict[str, Any]:
        return {
            key: str(value) if isinstance(value, UUID) else value for key, value in values.items()
        }

    def create(self, kind: RecordKind, values: dict[str, Any]) -> dict[str, Any]:
        row = self._values({"id": uuid4(), **values})
        with self.engine.begin() as connection:
            connection.execute(self._table(kind).insert().values(**row))
        return row

    def get(self, kind: RecordKind, id: UUID) -> dict[str, Any] | None:
        rows = self.find(kind, id=id)
        return rows[0] if rows else None

    def find(self, kind: RecordKind, **filters: Any) -> list[dict[str, Any]]:
        table = self._table(kind)
        statement = select(table).where(
            *(table.c[key] == value for key, value in self._values(filters).items())
        )
        if "created_at" in table.c:
            statement = statement.order_by(table.c.created_at, table.c.id)
        elif "seq" in table.c:
            statement = statement.order_by(table.c.seq)
        with self.engine.connect() as connection:
            return [_row(row) for row in connection.execute(statement).mappings()]

    def update(self, kind: RecordKind, id: UUID, values: dict[str, Any]) -> None:
        table = self._table(kind)
        with self.engine.begin() as connection:
            connection.execute(
                table.update().where(table.c.id == str(id)).values(**self._values(values))
            )

    def decide(self, id: UUID, actor: UUID, decision: str, at: datetime) -> bool:
        table = self._table("approval_requests")
        with self.engine.begin() as connection:
            result = connection.execute(
                table.update()
                .where(table.c.id == str(id), table.c.status == "pending")
                .values(status=decision, decided_by=str(actor), decided_at=at)
            )
            return result.rowcount == 1

    def emit(self, run_id: UUID, event: str, payload: dict[str, Any]) -> int:
        table = self._table("app_meta")
        key = f"agent.events.{run_id}"
        with self._lock, self.engine.begin() as connection:
            events = connection.execute(
                select(table.c.value).where(table.c.key == key)
            ).scalar_one_or_none()
            existing = events is not None
            events = list(events or [])
            id = len(events) + 1
            events.append({"id": id, "event": event, "data": _json(payload)})
            if existing:
                connection.execute(
                    table.update()
                    .where(table.c.key == key)
                    .values(value=events, updated_at=self.clock.now())
                )
            else:
                connection.execute(
                    table.insert().values(key=key, value=events, updated_at=self.clock.now())
                )
            return id

    def events(self, run_id: UUID, after: int = 0) -> list[dict[str, Any]]:
        table = self._table("app_meta")
        with self.engine.connect() as connection:
            events = connection.execute(
                select(table.c.value).where(table.c.key == f"agent.events.{run_id}")
            ).scalar_one_or_none()
        return [event for event in events or [] if event["id"] > after]

    def start_step(self, run_id: UUID, step: TraceStep) -> UUID:
        with self._lock:
            step.seq = len(self.find("agent_steps", run_id=run_id)) + 1
            row = self.create(
                "agent_steps",
                {
                    "run_id": run_id,
                    "seq": step.seq,
                    "agent": step.agent,
                    "type": step.type,
                    "tool_name": step.toolName,
                    "input_summary": step.inputSummary,
                    "output_summary": None,
                    "status": "ok",
                },
            )
            self.emit(
                run_id,
                "step_started",
                step.model_dump(include={"seq", "agent", "type", "toolName", "inputSummary"}),
            )
            return UUID(str(row["id"]))

    def finish_step(self, id: UUID, step: TraceStep) -> None:
        row = self.get("agent_steps", id)
        if row is None:
            raise ValueError("Unknown trace step")
        self.update(
            "agent_steps",
            id,
            {
                "output_summary": step.outputSummary,
                "tokens": step.tokens,
                "duration_ms": step.durationMs,
                "status": step.status,
            },
        )
        self.emit(UUID(row["run_id"]), "step_finished", step.model_dump(exclude={"inputSummary"}))

    def daily_usage(self, user_id: UUID, day: str) -> int:
        threads, runs = self._table("agent_threads"), self._table("agent_runs")
        statement = (
            select(func.coalesce(func.sum(runs.c.tokens_in + runs.c.tokens_out), 0))
            .join(threads, runs.c.thread_id == threads.c.id)
            .where(threads.c.user_id == str(user_id), func.date(runs.c.created_at) == day)
        )
        with self.engine.connect() as connection:
            return int(connection.execute(statement).scalar_one())
