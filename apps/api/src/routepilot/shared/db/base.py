"""Shared declarative base; services supply timestamps from their Clock."""

from datetime import datetime
from uuid import UUID

from sqlalchemy import Integer
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from routepilot.shared.db.types import UtcDateTime, UuidText
from routepilot.shared.ids import new_id


class Base(DeclarativeBase):
    pass


class IdMixin:
    id: Mapped[UUID] = mapped_column(UuidText(), primary_key=True, default=new_id)


class EditableMixin(IdMixin):
    version: Mapped[int] = mapped_column(Integer, default=1, server_default="1", nullable=False)
    created_at: Mapped[datetime] = mapped_column(UtcDateTime(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(UtcDateTime(), nullable=False)
