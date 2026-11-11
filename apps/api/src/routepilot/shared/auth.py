"""User context passed by composition without exposing identity internals."""

from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class Principal(BaseModel):
    model_config = ConfigDict(frozen=True)
    id: UUID
    role: Literal["admin", "dispatcher", "demo"]
    locale: Literal["en", "pl"]
    session_id: UUID
