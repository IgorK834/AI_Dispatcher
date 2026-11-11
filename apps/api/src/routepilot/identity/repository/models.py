"""Identity records matching the reviewed initial migration."""

from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import JSON, Boolean, ForeignKey, Integer, Text
from sqlalchemy.orm import Mapped, mapped_column

from routepilot.shared.db.base import Base, EditableMixin, IdMixin
from routepilot.shared.db.types import UtcDateTime, UuidText


class User(EditableMixin, Base):
    __tablename__ = "users"
    email: Mapped[str] = mapped_column(Text, unique=True)
    password_hash: Mapped[str] = mapped_column(Text)
    role: Mapped[str] = mapped_column(Text)
    locale: Mapped[str] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(Boolean)
    failed_logins: Mapped[int] = mapped_column(Integer)
    locked_until: Mapped[datetime | None] = mapped_column(UtcDateTime())
    last_login_at: Mapped[datetime | None] = mapped_column(UtcDateTime())


class UserSession(IdMixin, Base):
    __tablename__ = "sessions"
    token_hash: Mapped[str] = mapped_column(Text, unique=True)
    user_id: Mapped[UUID] = mapped_column(UuidText(), ForeignKey("users.id", ondelete="CASCADE"))
    expires_at: Mapped[datetime] = mapped_column(UtcDateTime())
    created_at: Mapped[datetime] = mapped_column(UtcDateTime())
    ip_hash: Mapped[str] = mapped_column(Text)
    ua_hash: Mapped[str] = mapped_column(Text)


class AuditEvent(IdMixin, Base):
    __tablename__ = "audit_events"
    at: Mapped[datetime] = mapped_column(UtcDateTime())
    actor: Mapped[str] = mapped_column(Text)
    action: Mapped[str] = mapped_column(Text)
    entity_type: Mapped[str] = mapped_column(Text)
    entity_id: Mapped[str | None] = mapped_column(Text)
    diff: Mapped[dict[str, Any]] = mapped_column(JSON)
