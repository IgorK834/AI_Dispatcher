"""Fleet usage port implemented by the assignment service."""

from typing import Literal, Protocol
from uuid import UUID


class DriverUsageChecker(Protocol):
    def assignment_usage(self, driver_id: UUID) -> Literal["none", "historical", "active"]: ...
