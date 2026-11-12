"""Small, PII-free freight projections used by the approved runtime tools."""

import math
from datetime import datetime
from decimal import ROUND_CEILING, Decimal
from typing import Any

from routepilot.freight.domain.models import FreightOfferView
from routepilot.freight.service.offers import FreightService
from routepilot.shared.errors import DomainError


def pallet_equivalents(offer: FreightOfferView) -> Decimal | None:
    count = offer.pallet_count
    derived = (
        int((offer.loading_length_m * Decimal("2.4")).to_integral_value(rounding=ROUND_CEILING))
        if offer.loading_length_m is not None
        else None
    )
    if count is None or offer.field_provenance.get("pallet_count") == "ai":
        if derived is None:
            return None
        count = max(count or 0, derived)
    factor = {
        "EUR_1200x800": Decimal("1"),
        "IND_1200x1000": Decimal("1.5"),
        "HALF_800x600": Decimal("0.5"),
    }.get(offer.pallet_type, Decimal("1"))
    return Decimal(count) * factor


def haversine_km(first: tuple[float, float], second: tuple[float, float]) -> float:
    lat1, lon1, lat2, lon2 = map(math.radians, (*first, *second))
    value = (
        math.sin((lat2 - lat1) / 2) ** 2
        + math.cos(lat1) * math.cos(lat2) * math.sin((lon2 - lon1) / 2) ** 2
    )
    return 6371 * 2 * math.asin(min(1, math.sqrt(value)))


class OfferQueryService:
    def __init__(self, freight: FreightService, fx_rates: dict[str, Decimal] | None = None) -> None:
        self.freight = freight
        self.fx_rates = {"EUR": Decimal("1"), **(fx_rates or {})}

    def _price(self, offer: FreightOfferView) -> Decimal | None:
        if offer.revenue is None:
            return None
        rate = self.fx_rates.get(offer.revenue.currency)
        return Decimal(offer.revenue.amount_minor) / 100 / rate if rate and rate > 0 else None

    def _reason(self, offer: FreightOfferView) -> str | None:
        if self._price(offer) is None:
            return "MISSING_REVENUE"
        if any(stop.lat is None or stop.lon is None for stop in offer.stops):
            return "MISSING_COORDINATES"
        if pallet_equivalents(offer) is None:
            return "MISSING_CAPACITY_DATA"
        return None

    def search(
        self,
        *,
        origin_city: str | None = None,
        origin_country: str | None = None,
        destination_city: str | None = None,
        destination_country: str | None = None,
        near_coordinates: tuple[float, float] | None = None,
        radius_km: int | None = None,
        pickup_from: datetime | None = None,
        pickup_to: datetime | None = None,
        max_weight_kg: int | None = None,
        max_pallet_eq: Decimal | None = None,
        only_complete: bool = False,
        limit: int = 20,
    ) -> dict[str, Any]:
        if any(
            value is not None and value.utcoffset() is None for value in (pickup_from, pickup_to)
        ):
            raise DomainError("VALIDATION_ERROR", 422)
        if not 1 <= limit <= 20 or (radius_km is not None and not 0 <= radius_km <= 500):
            raise DomainError("VALIDATION_ERROR", 422)
        if pickup_from and pickup_to and pickup_from > pickup_to:
            raise DomainError("VALIDATION_ERROR", 422)
        items = self.freight.all_offers(status="open")
        selected = []
        for item in items:
            first, last = item.stops[0], item.stops[-1]
            if origin_country is not None and first.country_code != origin_country:
                continue
            if destination_country is not None and last.country_code != destination_country:
                continue
            if origin_city is not None and first.city.casefold() != origin_city.casefold():
                continue
            if destination_city is not None and last.city.casefold() != destination_city.casefold():
                continue
            if (pickup_from is not None and first.window_end < pickup_from) or (
                pickup_to is not None and first.window_start > pickup_to
            ):
                continue
            if max_weight_kg is not None and (
                item.weight_kg is None or item.weight_kg > max_weight_kg
            ):
                continue
            equivalents = pallet_equivalents(item)
            if max_pallet_eq is not None and (equivalents is None or equivalents > max_pallet_eq):
                continue
            if near_coordinates is not None and radius_km is not None:
                if (
                    first.lat is None
                    or first.lon is None
                    or haversine_km(near_coordinates, (first.lat, first.lon)) > radius_km
                ):
                    continue
            if only_complete and item.completeness_score < 1:
                continue
            selected.append(
                {
                    "offer_id": item.source_offer_id,
                    "origin": {"city": first.city, "country": first.country_code},
                    "destination": {"city": last.city, "country": last.country_code},
                    "pickup_window": {
                        "start": first.window_start.isoformat(),
                        "end": first.window_end.isoformat(),
                    },
                    "delivery_window": {
                        "start": last.window_start.isoformat(),
                        "end": last.window_end.isoformat(),
                    },
                    "weight_kg": item.weight_kg,
                    "pallet_eq": str(equivalents) if equivalents is not None else None,
                    "price_eur": str(self._price(item)) if self._price(item) is not None else None,
                    "completeness": item.completeness_score,
                    "flags": item.quality_flags,
                    "suspicious": "SUSPICIOUS_TEXT" in item.quality_flags,
                }
            )
        return {
            "offers": selected[:limit],
            "total_matching": len(selected),
            "truncated": len(selected) > limit,
        }

    def get(self, offer_id: str) -> dict[str, Any]:
        item = self.freight.get_by_source_id(offer_id)
        equivalents = pallet_equivalents(item)
        price = self._price(item)
        return {
            "offer_id": item.source_offer_id,
            "source": item.source,
            "status": item.status,
            "stops": [
                {
                    "type": stop.stop_type,
                    "city": stop.city,
                    "country": stop.country_code,
                    "window_start": stop.window_start.isoformat(),
                    "window_end": stop.window_end.isoformat(),
                    "service_min": stop.service_minutes,
                }
                for stop in item.stops
            ],
            "weight_kg": item.weight_kg,
            "pallet_count": item.pallet_count,
            "pallet_type": item.pallet_type,
            "pallet_eq": str(equivalents) if equivalents is not None else None,
            "loading_length_m": str(item.loading_length_m)
            if item.loading_length_m is not None
            else None,
            "price_eur": str(price) if price is not None else None,
            "required_body_types": item.required_body_types,
            "missing_fields": item.missing_fields,
            "flags": item.quality_flags,
            "provenance": item.field_provenance,
            "suspicious": "SUSPICIOUS_TEXT" in item.quality_flags,
            "untrusted_text": "\n".join(
                text for text in (item.description, item.public_remark) if text
            )[:300],
        }

    def quality(self, offer_ids: list[str]) -> dict[str, Any]:
        if len(offer_ids) > 20:
            raise DomainError("VALIDATION_ERROR", 422)
        items: list[dict[str, Any]] = []
        for offer_id in offer_ids:
            try:
                offer = self.freight.get_by_source_id(offer_id)
            except DomainError as exc:
                if exc.code != "NOT_FOUND":
                    raise
                items.append(
                    {
                        "offer_id": offer_id,
                        "completeness": None,
                        "missing_fields": [],
                        "flags": [],
                        "usable_by_engine": False,
                        "reason_code": "NOT_FOUND",
                    }
                )
                continue
            reason = self._reason(offer)
            items.append(
                {
                    "offer_id": offer_id,
                    "completeness": offer.completeness_score,
                    "missing_fields": offer.missing_fields,
                    "flags": offer.quality_flags,
                    "usable_by_engine": reason is None,
                    "reason_code": reason,
                }
            )
        return {"items": items}
