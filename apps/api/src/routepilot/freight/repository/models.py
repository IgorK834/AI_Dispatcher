"""Freight tables matching the approved initial migration."""

from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import JSON, Boolean, Float, ForeignKey, Integer, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from routepilot.shared.db.base import Base, EditableMixin, IdMixin
from routepilot.shared.db.types import UtcDateTime, UuidText


class ImportBatch(IdMixin, Base):
    __tablename__ = "import_batches"
    source: Mapped[str] = mapped_column(Text)
    started_at: Mapped[datetime] = mapped_column(UtcDateTime())
    finished_at: Mapped[datetime | None] = mapped_column(UtcDateTime())
    status: Mapped[str] = mapped_column(Text)
    counts: Mapped[dict[str, int]] = mapped_column(JSON)


class RawFreightRecord(IdMixin, Base):
    __tablename__ = "raw_freight_records"
    __table_args__ = (UniqueConstraint("source", "source_offer_id", "payload_sha256"),)
    source: Mapped[str] = mapped_column(Text)
    source_offer_id: Mapped[str] = mapped_column(Text)
    payload: Mapped[dict[str, Any]] = mapped_column(JSON)
    payload_sha256: Mapped[str] = mapped_column(Text)
    fetched_at: Mapped[datetime] = mapped_column(UtcDateTime())
    import_batch_id: Mapped[UUID] = mapped_column(
        UuidText(), ForeignKey("import_batches.id", ondelete="RESTRICT")
    )
    is_synthetic: Mapped[bool] = mapped_column(Boolean)
    retention_until: Mapped[datetime | None] = mapped_column(UtcDateTime())


class FreightOffer(EditableMixin, Base):
    __tablename__ = "freight_offers"
    __table_args__ = (UniqueConstraint("source", "source_offer_id"),)
    source: Mapped[str] = mapped_column(Text)
    source_offer_id: Mapped[str] = mapped_column(Text)
    raw_record_id: Mapped[UUID | None] = mapped_column(
        UuidText(), ForeignKey("raw_freight_records.id", ondelete="SET NULL")
    )
    status: Mapped[str] = mapped_column(Text)
    is_synthetic: Mapped[bool] = mapped_column(Boolean)
    description: Mapped[str | None] = mapped_column(Text)
    public_remark: Mapped[str | None] = mapped_column(Text)
    revenue_amount_minor: Mapped[int | None] = mapped_column(Integer)
    revenue_currency: Mapped[str | None] = mapped_column(Text(3))
    weight_kg: Mapped[int | None] = mapped_column(Integer)
    pallet_count: Mapped[int | None] = mapped_column(Integer)
    pallet_type: Mapped[str | None] = mapped_column(Text)
    loading_length_mm: Mapped[int | None] = mapped_column(Integer)
    required_body_types: Mapped[list[str]] = mapped_column(JSON)
    required_vehicle_types: Mapped[list[str]] = mapped_column(JSON)
    completeness_score: Mapped[float] = mapped_column(Float)
    missing_fields: Mapped[list[str]] = mapped_column(JSON)
    quality_flags: Mapped[list[str]] = mapped_column(JSON)
    field_provenance: Mapped[dict[str, str]] = mapped_column(JSON)
    retention_until: Mapped[datetime | None] = mapped_column(UtcDateTime())


class FreightStop(IdMixin, Base):
    __tablename__ = "freight_stops"
    __table_args__ = (UniqueConstraint("offer_id", "sequence"),)
    offer_id: Mapped[UUID] = mapped_column(
        UuidText(), ForeignKey("freight_offers.id", ondelete="CASCADE")
    )
    sequence: Mapped[int] = mapped_column(Integer)
    stop_type: Mapped[str] = mapped_column(Text)
    city: Mapped[str] = mapped_column(Text)
    postal_code: Mapped[str | None] = mapped_column(Text)
    country_code: Mapped[str] = mapped_column(Text(2))
    lat: Mapped[float | None] = mapped_column(Float)
    lon: Mapped[float | None] = mapped_column(Float)
    timezone: Mapped[str] = mapped_column(Text)
    window_start: Mapped[datetime] = mapped_column(UtcDateTime())
    window_end: Mapped[datetime] = mapped_column(UtcDateTime())
    service_minutes: Mapped[int] = mapped_column(Integer)
    provenance: Mapped[dict[str, str]] = mapped_column(JSON)
