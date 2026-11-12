"""A deterministic port double; production uses the composition-root SQL adapter."""

from copy import deepcopy
from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

from routepilot.agents.ports import RecordKind
from routepilot.agents.schemas import TraceStep


class MemoryStore:
    def __init__(self) -> None:
        self.rows: dict[RecordKind, dict[UUID, dict[str, Any]]] = {}
        self.journal: dict[UUID, list[dict[str, Any]]] = {}

    def create(self, kind: RecordKind, values: dict[str, Any]) -> dict[str, Any]:
        row = {"id": uuid4(), **deepcopy(values)}
        self.rows.setdefault(kind, {})[UUID(str(row["id"]))] = row
        return deepcopy(row)

    def get(self, kind: RecordKind, id: UUID) -> dict[str, Any] | None:
        return deepcopy(self.rows.get(kind, {}).get(id))

    def find(self, kind: RecordKind, **filters: Any) -> list[dict[str, Any]]:
        return [
            deepcopy(row)
            for row in self.rows.get(kind, {}).values()
            if all(str(row.get(key)) == str(value) for key, value in filters.items())
        ]

    def update(self, kind: RecordKind, id: UUID, values: dict[str, Any]) -> None:
        self.rows[kind][id].update(deepcopy(values))

    def decide(self, id: UUID, actor: UUID, decision: str, at: datetime) -> bool:
        row = self.rows["approval_requests"][id]
        if row["status"] != "pending":
            return False
        row.update(status=decision, decided_by=actor, decided_at=at)
        return True

    def emit(self, run_id: UUID, event: str, payload: dict[str, Any]) -> int:
        events = self.journal.setdefault(run_id, [])
        id = len(events) + 1
        events.append({"id": id, "event": event, "data": deepcopy(payload)})
        return id

    def events(self, run_id: UUID, after: int = 0) -> list[dict[str, Any]]:
        return deepcopy([event for event in self.journal.get(run_id, []) if event["id"] > after])

    def start_step(self, run_id: UUID, step: TraceStep) -> UUID:
        step.seq = len(self.find("agent_steps", run_id=run_id)) + 1
        row = self.create("agent_steps", {"run_id": run_id, **step.model_dump()})
        self.emit(
            run_id,
            "step_started",
            step.model_dump(include={"seq", "agent", "type", "toolName", "inputSummary"}),
        )
        return UUID(str(row["id"]))

    def finish_step(self, id: UUID, step: TraceStep) -> None:
        row = self.rows["agent_steps"][id]
        self.update("agent_steps", id, step.model_dump())
        self.emit(row["run_id"], "step_finished", step.model_dump(exclude={"inputSummary"}))

    def daily_usage(self, user_id: UUID, day: str) -> int:
        threads = {row["id"] for row in self.find("agent_threads", user_id=user_id)}
        return sum(
            row["tokens_in"] + row["tokens_out"]
            for row in self.find("agent_runs")
            if row["thread_id"] in threads and row["created_at"].isoformat().startswith(day)
        )
