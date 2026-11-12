"""Freight CRUD and query use cases, shared by API and runtime tools."""

from datetime import datetime
from decimal import Decimal
from typing import Any
from uuid import UUID, uuid4

from pydantic import ValidationError
from sqlalchemy import delete, select, update
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from routepilot.freight.domain.models import (
    FreightOfferCreate,
    FreightOfferUpdate,
    FreightOfferView,
    NormalizedOffer,
    Revenue,
    StopView,
)
from routepilot.freight.normalization import normalize_manual
from routepilot.freight.repository.models import FreightOffer, FreightStop, RawFreightRecord
from routepilot.shared.audit import AuditWriter
from routepilot.shared.clock import Clock
from routepilot.shared.errors import DomainError
from routepilot.shared.pagination import CursorCodec, Page


def offer_values(offer: NormalizedOffer) -> dict[str, Any]:
    values = offer.model_dump(exclude={"revenue", "stops", "loading_length_m"})
    values["revenue_amount_minor"] = offer.revenue.amount_minor if offer.revenue else None
    values["revenue_currency"] = offer.revenue.currency if offer.revenue else None
    values["loading_length_mm"] = (
        int(offer.loading_length_m * 1000) if offer.loading_length_m is not None else None
    )
    return values


def replace_stops(session: Session, offer_id: UUID, stops: list[StopView]) -> None:
    session.execute(delete(FreightStop).where(FreightStop.offer_id == offer_id))
    for stop in stops:
        session.add(FreightStop(offer_id=offer_id, **stop.model_dump()))
    session.flush()


class FreightService:
    def __init__(
        self,
        engine: Engine,
        clock: Clock,
        audit: AuditWriter | None = None,
        cursor_secret: str | bytes | None = None,
    ) -> None:
        self.engine, self.clock, self.audit = engine, clock, audit
        self.cursors = CursorCodec(cursor_secret)

    def _audit(
        self,
        session: Session,
        actor: str,
        action: str,
        offer_id: UUID,
        diff: dict[str, Any] | None = None,
    ) -> None:
        if self.audit:
            self.audit.record(
                actor, action, "freight_offer", str(offer_id), diff, transaction=session
            )

    @staticmethod
    def _row(session: Session, offer_id: UUID) -> FreightOffer:
        row = session.get(FreightOffer, offer_id)
        if row is None:
            raise DomainError("NOT_FOUND", 404)
        return row

    @staticmethod
    def _view(session: Session, row: FreightOffer) -> FreightOfferView:
        values = {column.name: getattr(row, column.name) for column in row.__table__.columns}
        raw_id = values.pop("raw_record_id")
        raw = session.get(RawFreightRecord, raw_id) if raw_id else None
        values["required_equipment"] = (
            raw.payload.get("vehicleProperties", {}).get("equipment", []) if raw else []
        )
        amount, currency = values.pop("revenue_amount_minor"), values.pop("revenue_currency")
        values["revenue"] = (
            Revenue(amount_minor=amount, currency=currency)
            if amount is not None and currency
            else None
        )
        length_mm = values.pop("loading_length_mm")
        values["loading_length_m"] = Decimal(length_mm) / 1000 if length_mm is not None else None
        values["pallet_type"] = values["pallet_type"] or "UNKNOWN"
        values["stops"] = [
            StopView.model_validate(
                {
                    column.name: getattr(stop, column.name)
                    for column in stop.__table__.columns
                    if column.name not in ("id", "offer_id")
                }
            )
            for stop in session.scalars(
                select(FreightStop)
                .where(FreightStop.offer_id == row.id)
                .order_by(FreightStop.sequence)
            )
        ]
        return FreightOfferView.model_validate(values)

    def get_offer(self, offer_id: UUID) -> FreightOfferView:
        with Session(self.engine) as session:
            return self._view(session, self._row(session, offer_id))

    def get_by_source_id(self, source_offer_id: str) -> FreightOfferView:
        with Session(self.engine) as session:
            row = session.scalar(
                select(FreightOffer)
                .where(FreightOffer.source_offer_id == source_offer_id)
                .order_by(FreightOffer.id)
            )
            if row is None:
                raise DomainError("NOT_FOUND", 404)
            return self._view(session, row)

    def all_offers(self, *, status: str | None = None) -> list[FreightOfferView]:
        with Session(self.engine) as session:
            query = select(FreightOffer).order_by(FreightOffer.id)
            if status is not None:
                query = query.where(FreightOffer.status == status)
            return [self._view(session, row) for row in session.scalars(query)]

    def list_offers(
        self,
        limit: int = 50,
        cursor: str | None = None,
        source: str | None = None,
        status: str | None = None,
        origin_country: str | None = None,
        destination_country: str | None = None,
        origin_city: str | None = None,
        destination_city: str | None = None,
        pickup_from: datetime | None = None,
        pickup_to: datetime | None = None,
        max_weight_kg: int | None = None,
        max_pallets: int | None = None,
        min_completeness: float | None = None,
        has_price: bool | None = None,
    ) -> Page[FreightOfferView]:
        if not 1 <= limit <= 100:
            raise DomainError("VALIDATION_ERROR", 422)
        filters = {
            key: value for key, value in locals().items() if key not in ("self", "limit", "cursor")
        }
        filters["resource"] = "freight_offers"
        items = self.all_offers(status=status)
        selected = []
        for item in items:
            first, last = item.stops[0], item.stops[-1]
            if source is not None and item.source != source:
                continue
            if origin_country is not None and first.country_code != origin_country:
                continue
            if destination_country is not None and last.country_code != destination_country:
                continue
            if origin_city is not None and first.city.casefold() != origin_city.casefold():
                continue
            if destination_city is not None and last.city.casefold() != destination_city.casefold():
                continue
            if pickup_from is not None and first.window_end < pickup_from:
                continue
            if pickup_to is not None and first.window_start > pickup_to:
                continue
            if max_weight_kg is not None and (
                item.weight_kg is None or item.weight_kg > max_weight_kg
            ):
                continue
            if max_pallets is not None and (
                item.pallet_count is None or item.pallet_count > max_pallets
            ):
                continue
            if min_completeness is not None and item.completeness_score < min_completeness:
                continue
            if has_price is not None and (item.revenue is not None) != has_price:
                continue
            selected.append(item)
        marker = self.cursors.decode(cursor, filters)
        if marker:
            matches = [index for index, item in enumerate(selected) if str(item.id) == marker]
            if not matches:
                raise DomainError("VALIDATION_ERROR", 422)
            selected = selected[matches[0] + 1 :]
        page = selected[:limit]
        return Page(
            items=page,
            nextCursor=self.cursors.encode(str(page[-1].id), filters)
            if len(selected) > limit
            else None,
        )

    def create_offer(self, body: FreightOfferCreate, actor: str) -> FreightOfferView:
        with Session(self.engine) as session, session.begin():
            now = self.clock.now()
            offer = normalize_manual(body, "MAN-" + uuid4().hex[:8])
            row = FreightOffer(
                **offer_values(offer),
                source="manual",
                status="open",
                is_synthetic=False,
                created_at=now,
                updated_at=now,
            )
            session.add(row)
            session.flush()
            replace_stops(session, row.id, offer.stops)
            self._audit(
                session, actor, "freight_offer.created", row.id, body.model_dump(mode="json")
            )
            return self._view(session, row)

    def update_offer(
        self, offer_id: UUID, body: FreightOfferUpdate, actor: str
    ) -> FreightOfferView:
        try:
            with Session(self.engine) as session, session.begin():
                row = self._row(session, offer_id)
                if row.source != "manual":
                    raise DomainError("PROVIDER_OFFER_READ_ONLY", 409)
                original = self._view(session, row)
                values = body.model_dump(exclude_unset=True, exclude={"version"})
                current = original.model_dump(
                    include=set(FreightOfferCreate.model_fields), exclude={"stops"}
                )
                current["stops"] = [
                    stop.model_dump(exclude={"sequence", "timezone", "provenance"})
                    for stop in original.stops
                ]
                validated = FreightOfferCreate.model_validate({**current, **values})
                normalized = normalize_manual(validated, row.source_offer_id)
                changed = session.execute(
                    update(FreightOffer)
                    .where(FreightOffer.id == offer_id, FreightOffer.version == body.version)
                    .returning(FreightOffer.id)
                    .values(
                        **offer_values(normalized),
                        version=body.version + 1,
                        updated_at=self.clock.now(),
                    )
                )
                if changed.scalar_one_or_none() is None:
                    raise DomainError("VERSION_CONFLICT", 409)
                replace_stops(session, offer_id, normalized.stops)
                session.refresh(row)
                self._audit(
                    session,
                    actor,
                    "freight_offer.updated",
                    row.id,
                    body.model_dump(mode="json", exclude_unset=True),
                )
                return self._view(session, row)
        except ValidationError:
            raise DomainError("VALIDATION_ERROR", 422) from None

    def delete_offer(self, offer_id: UUID, actor: str) -> None:
        with Session(self.engine) as session, session.begin():
            row = self._row(session, offer_id)
            if row.source != "manual":
                raise DomainError("PROVIDER_OFFER_READ_ONLY", 409)
            row.status = "withdrawn"
            row.version += 1
            row.updated_at = self.clock.now()
            self._audit(session, actor, "freight_offer.deleted", row.id)
