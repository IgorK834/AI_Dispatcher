"""Stable domain error codes at the API boundary."""

from pydantic import JsonValue


class DomainError(Exception):
    def __init__(
        self,
        code: str,
        status: int = 409,
        *,
        headers: dict[str, str] | None = None,
        errors: list[dict[str, JsonValue]] | None = None,
    ) -> None:
        self.code = code
        self.status = status
        self.headers = headers or {}
        self.errors = errors or []
        super().__init__(code)
