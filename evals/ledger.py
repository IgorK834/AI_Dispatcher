"""Durable pre-generation reservations; an interrupted call consumes its whole cap."""

import fcntl
import json
import os
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Literal
from uuid import uuid4

from routepilot.agents.guards import BudgetExceeded, Reservation, TokenBudget

Phase = Literal["smoke", "evals"]
# Owner decision 2026-11-12: a first campaign of 500 000 tokens (80 000 smoke, 420 000 evals);
# 484 835 of them were used by the first live batch (issue #7), which ran 18 of 40 scenarios.
# Owner decision 2026-11-13: one new campaign of 1 000 000 tokens for a complete AC-40/41 batch,
# 80 000 for the smoke check and 920 000 for the evals phase. It needs a new ledger file: the
# budget of an existing ledger is immutable.
PHASE_LIMITS: dict[Phase, int] = {"smoke": 80000, "evals": 920000}
CAMPAIGN_LIMIT = 1000000


class CampaignLedger:
    def __init__(self, path: Path, limit: int = CAMPAIGN_LIMIT) -> None:
        if not 0 < limit <= CAMPAIGN_LIMIT:
            raise ValueError("campaign budget must be within approved 1000000 tokens")
        self.path, self.limit = path, limit
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.lock_path = path.with_suffix(path.suffix + ".lock")
        with self.transaction() as state:
            if state["limit"] != limit:
                raise ValueError("existing ledger has another immutable budget")

    @contextmanager
    def transaction(self) -> Iterator[dict[str, Any]]:
        with self.lock_path.open("a+") as lock:
            fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
            try:
                state = (
                    json.loads(self.path.read_text())
                    if self.path.exists()
                    else dict(version=1, limit=self.limit, closed=False, phases={}, calls={})
                )
                yield state
                temporary = self.path.with_name(self.path.name + ".tmp")
                with temporary.open("w") as output:
                    json.dump(state, output, sort_keys=True, indent=2)
                    output.write("\n")
                    output.flush()
                    os.fsync(output.fileno())
                temporary.replace(self.path)
            finally:
                fcntl.flock(lock.fileno(), fcntl.LOCK_UN)

    @staticmethod
    def usage(state: dict[str, Any], phase: Phase | None = None) -> tuple[int, int]:
        calls = [c for c in state["calls"].values() if phase is None or c["phase"] == phase]
        return sum(c["tokens_in"] for c in calls), sum(c["tokens_out"] for c in calls)

    def snapshot(self) -> dict[str, Any]:
        with self.transaction() as state:
            return json.loads(json.dumps(state))

    def start_phase(
        self, phase: Phase, scenario_ids: list[str], fingerprint: str, *, retry: bool = False
    ) -> None:
        with self.transaction() as state:
            previous = state["phases"].get(phase)
            if previous is not None and not retry:
                raise ValueError("phase already attempted; automatic reruns are forbidden")
            attempts = (previous or {}).get("attempts", [])
            if previous is not None:
                attempts = [
                    *attempts,
                    dict(status=previous["status"], fingerprint=previous["fingerprint"]),
                ]
            # A retry is an explicit owner decision; the phase and campaign caps still count
            # every earlier call, so it can never extend the approved allowance.
            state["phases"][phase] = dict(
                status="started", scenarios=scenario_ids, fingerprint=fingerprint, attempts=attempts
            )

    def reconcile(self, entry: str, tokens_in: int, tokens_out: int, source: str) -> None:
        """Replace an orphaned full reservation by usage that the run itself recorded.

        Only an entry still in `reserved` state can be reconciled, never upward, and the
        original reservation is kept in the entry for audit.
        """
        with self.transaction() as state:
            call = state["calls"][entry]
            if call["status"] != "reserved":
                raise ValueError("only an unsettled reservation can be reconciled")
            if min(tokens_in, tokens_out) < 0 or tokens_in + tokens_out > (
                call["tokens_in"] + call["tokens_out"]
            ):
                raise ValueError("reconciled usage can never exceed the reservation")
            call.update(
                status="reconciled",
                tokens_in=tokens_in,
                tokens_out=tokens_out,
                reconciled=dict(
                    source=source,
                    reserved_input=call["reserved_input"],
                    reserved_output=call["reserved_output"],
                ),
            )

    def reopen(self, reason: str) -> None:
        """Re-open a campaign closed by an accounting failure; an explicit, recorded owner act."""
        with self.transaction() as state:
            if not state["closed"]:
                raise ValueError("campaign is not closed")
            state["closed"] = False
            state.setdefault("reopened", []).append(reason)

    def finish_phase(self, phase: Phase, status: str) -> None:
        with self.transaction() as state:
            state["phases"][phase]["status"] = status


class DurableBudget(TokenBudget):
    """One reservation entry accounts global and phase caps together, exactly once."""

    def __init__(
        self, ledger: CampaignLedger, phase: Phase, phase_limit: int | None = None
    ) -> None:
        self.ledger, self.phase = ledger, phase
        state = ledger.snapshot()
        tokens_in, tokens_out = ledger.usage(state, phase)
        # An owner-approved campaign may need a phase cap above the default; never above the
        # campaign limit of the ledger, which is checked at every reservation anyway.
        super().__init__(
            min(phase_limit or PHASE_LIMITS[phase], ledger.limit), tokens_in + tokens_out
        )
        self.tokens_in, self.tokens_out = tokens_in, tokens_out
        self.closed = state["closed"]
        self.entries: dict[int, str] = {}

    def reserve(self, input_tokens: int, max_output_tokens: int) -> Reservation:
        ticket = super().reserve(input_tokens, max_output_tokens)
        entry = str(uuid4())
        try:
            with self.ledger.transaction() as state:
                global_in, global_out = self.ledger.usage(state)
                phase_in, phase_out = self.ledger.usage(state, self.phase)
                amount = input_tokens + max_output_tokens
                if (
                    state["closed"]
                    or global_in + global_out + amount > self.ledger.limit
                    or phase_in + phase_out + amount > self.limit
                ):
                    raise BudgetExceeded("CAMPAIGN_TOKEN_BUDGET")
                state["calls"][entry] = dict(
                    phase=self.phase,
                    status="reserved",
                    tokens_in=input_tokens,
                    tokens_out=max_output_tokens,
                    reserved_input=input_tokens,
                    reserved_output=max_output_tokens,
                )
            self.entries[ticket.id] = entry
            return ticket
        except Exception:
            super().settle(ticket, 0, 0)
            raise

    def settle(self, ticket: Reservation, input_tokens: int, output_tokens: int) -> None:
        entry = self.entries.pop(ticket.id)
        try:
            super().settle(ticket, input_tokens, output_tokens)
        finally:
            with self.ledger.transaction() as state:
                state["calls"][entry].update(
                    status="settled", tokens_in=input_tokens, tokens_out=output_tokens
                )
                state["closed"] |= self.closed

    def unknown(self, ticket: Reservation) -> None:
        entry = self.entries.pop(ticket.id)
        super().unknown(ticket)
        # Owner decision 2026-11-12: an unknown outcome (for example a provider 504) is charged at
        # its full reservation but does not close the campaign, so the configured fallback can
        # still run. Only usage that exceeds its reservation (settle) closes it.
        with self.ledger.transaction() as state:
            state["calls"][entry]["status"] = "unknown"
