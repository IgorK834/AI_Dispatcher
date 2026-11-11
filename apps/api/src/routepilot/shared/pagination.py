"""Opaque cursors bound to a resource/filter set and signed by the server."""

import base64
import hashlib
import hmac
import json
import secrets
from typing import Any, Generic, TypeVar

from pydantic import BaseModel, ConfigDict, Field

from routepilot.shared.errors import DomainError

T = TypeVar("T")


class Page(BaseModel, Generic[T]):
    model_config = ConfigDict(populate_by_name=True)
    items: list[T]
    next_cursor: str | None = Field(default=None, alias="nextCursor")


class CursorCodec:
    def __init__(self, secret: str | bytes | None = None) -> None:
        self.secret = (
            secret.encode() if isinstance(secret, str) else secret or secrets.token_bytes(32)
        )

    @staticmethod
    def _filter_hash(filters: dict[str, Any]) -> str:
        value = json.dumps(filters, sort_keys=True, separators=(",", ":"), default=str)
        return hashlib.sha256(value.encode()).hexdigest()

    def encode(self, last_id: str, filters: dict[str, Any]) -> str:
        payload = json.dumps(
            {"last": last_id, "filters": self._filter_hash(filters)},
            sort_keys=True,
            separators=(",", ":"),
        ).encode()
        encoded = base64.urlsafe_b64encode(payload).decode().rstrip("=")
        signature = hmac.new(self.secret, encoded.encode(), hashlib.sha256).hexdigest()
        return encoded + "." + signature

    def decode(self, cursor: str | None, filters: dict[str, Any]) -> str | None:
        if cursor is None:
            return None
        try:
            encoded, signature = cursor.rsplit(".", 1)
            expected = hmac.new(self.secret, encoded.encode(), hashlib.sha256).hexdigest()
            if not hmac.compare_digest(signature, expected):
                raise ValueError("signature")
            payload = json.loads(base64.urlsafe_b64decode(encoded + "=" * (-len(encoded) % 4)))
            if payload["filters"] != self._filter_hash(filters) or not isinstance(
                payload["last"], str
            ):
                raise ValueError("filters")
            return str(payload["last"])
        except (ValueError, KeyError, TypeError):
            raise DomainError("VALIDATION_ERROR", 422) from None
