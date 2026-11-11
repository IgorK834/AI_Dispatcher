"""SQLite text types with explicit UUID and UTC semantics."""

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import DateTime, Text
from sqlalchemy.engine import Dialect
from sqlalchemy.types import TypeDecorator, TypeEngine


class UuidText(TypeDecorator[UUID]):
    impl = Text
    cache_ok = True

    def process_bind_param(self, value: UUID | None, dialect: Dialect) -> str | None:
        return str(value) if value is not None else None

    def process_result_value(self, value: object, dialect: Dialect) -> UUID | None:
        return UUID(str(value)) if value is not None else None


class UtcDateTime(TypeDecorator[datetime]):
    impl = Text
    cache_ok = True

    def load_dialect_impl(self, dialect: Dialect) -> TypeEngine[str] | TypeEngine[datetime]:
        if dialect.name == "postgresql":
            return dialect.type_descriptor(DateTime(timezone=True))
        return dialect.type_descriptor(Text())

    def process_bind_param(self, value: datetime | None, dialect: Dialect) -> str | datetime | None:
        if value is None:
            return None
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("UtcDateTime requires an aware datetime")
        utc = value.astimezone(UTC)
        return utc if dialect.name == "postgresql" else utc.isoformat(timespec="microseconds")

    def process_result_value(self, value: object, dialect: Dialect) -> datetime | None:
        if value is None:
            return None
        result = value if isinstance(value, datetime) else datetime.fromisoformat(str(value))
        return result.replace(tzinfo=UTC) if result.tzinfo is None else result.astimezone(UTC)
