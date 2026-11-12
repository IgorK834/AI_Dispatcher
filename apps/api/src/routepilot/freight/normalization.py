"""Pure normalization shared by manual input and provider adapters."""

import re
from typing import Any

from routepilot.freight.domain.models import FreightOfferCreate, NormalizedOffer, StopView
from routepilot.freight.geocoding import geocode, timezone_for_country


def suspicious_text(*values: str | None) -> bool:
    return any(
        re.search(r"ignore\s+previous|system\s*:|assign\s+this|you\s+must", text, re.I)
        for text in values
        if text
    )


def completeness(offer: NormalizedOffer) -> NormalizedOffer:
    present = {
        "revenue": offer.revenue is not None,
        "weightKg": offer.weight_kg is not None,
        "palletCount": offer.pallet_count is not None,
    }
    for index, stop in enumerate(offer.stops[:2]):
        present[f"stops[{index}].coordinates"] = stop.lat is not None and stop.lon is not None
        present[f"stops[{index}].window"] = (
            stop.window_start is not None and stop.window_end is not None
        )
    offer.missing_fields = sorted(key for key, value in present.items() if not value)
    offer.completeness_score = sum(present.values()) / 7
    if offer.pallet_type == "UNKNOWN":
        offer.quality_flags.append("PALLET_TYPE_UNKNOWN")
    if suspicious_text(offer.description, offer.public_remark):
        offer.quality_flags.append("SUSPICIOUS_TEXT")
    offer.quality_flags = sorted(set(offer.quality_flags))
    return offer


def normalize_manual(body: FreightOfferCreate, source_offer_id: str) -> NormalizedOffer:
    stops, flags = [], []
    for index, stop in enumerate(body.stops):
        data: dict[str, Any] = stop.model_dump()
        provenance = {key: "user" for key in type(stop).model_fields}
        if stop.lat is None:
            coordinates = geocode(stop.city, stop.country_code)
            if coordinates:
                data["lat"], data["lon"] = coordinates
                provenance.update(lat="derived", lon="derived")
            else:
                flags.append("MISSING_COORDINATES")
        if stop.service_minutes is None:
            data["service_minutes"] = 30
            provenance["service_minutes"] = "default"
            flags.append("SERVICE_TIME_DEFAULTED")
        stops.append(
            StopView(
                **data,
                sequence=index,
                timezone=timezone_for_country(stop.country_code),
                provenance={**provenance, "timezone": "inferred"},
            )
        )
    return completeness(
        NormalizedOffer(
            **body.model_dump(exclude={"stops"}),
            source_offer_id=source_offer_id,
            stops=stops,
            required_vehicle_types=["VEHICLE_UP_TO_3_5_T"],
            field_provenance={key: "user" for key in type(body).model_fields},
            quality_flags=flags,
        )
    )
