"""Small factories for the pure FEAT-003 working-time rules tests."""

from datetime import UTC, datetime
from typing import Any

from routepilot.compliance.state import DriverState

RULES_START = datetime(2026, 11, 16, 7, tzinfo=UTC)


def rules_state(**changes: Any) -> DriverState:
    """Return a deterministic state; individual tests override only relevant counters."""
    return DriverState(t=changes.pop("t", RULES_START), **changes)
