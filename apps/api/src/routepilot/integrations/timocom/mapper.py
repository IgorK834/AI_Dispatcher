"""Tolerant, offline mapping from the recorded TIMOCOM v3 subset."""

from datetime import UTC, datetime, time, timedelta
from decimal import ROUND_CEILING, ROUND_HALF_UP, Decimal
from typing import Literal, cast
from zoneinfo import ZoneInfo

from pydantic import ValidationError

from routepilot.freight.domain.models import (
    MappingFailure,
    NormalizedOffer,
    RawOfferRecord,
    Revenue,
    StopView,
)
from routepilot.freight.geocoding import geocode, timezone_for_country
from routepilot.freight.normalization import completeness
from routepilot.integrations.timocom.schemas import FreightOffer


class TimocomV3Mapper:
    source = "mock_timocom_v3"

    def to_domain(self, record: RawOfferRecord) -> NormalizedOffer | MappingFailure:
        try:
            return self._map(record)
        except (ValidationError, ValueError, ArithmeticError) as exc:
            return MappingFailure(code="INVALID_PROVIDER_RECORD", detail=str(exc))

    def _map(self, record: RawOfferRecord) -> NormalizedOffer:
        raw = FreightOffer.model_validate(record.payload)
        if (
            len(raw.loadingPlaces) < 2
            or raw.loadingPlaces[0].loadingType != "LOADING"
            or raw.loadingPlaces[-1].loadingType != "UNLOADING"
        ):
            raise ValueError("At least two stops, first LOADING and last UNLOADING, are required")
        flags: list[str] = []
        if "creationDateTime " in record.payload:
            flags.append("KEY_WHITESPACE_TOLERATED")
        stops: list[StopView] = []
        enrichment = record.enrichment
        for index, place in enumerate(raw.loadingPlaces):
            if place.loadingType not in ("LOADING", "UNLOADING"):
                raise ValueError("Unknown loadingType")
            address = place.address
            timezone = timezone_for_country(address.country)
            if timezone == "UTC":
                flags.append("TIMEZONE_DEFAULTED")
            lat = address.geoCoordinate.latitude if address.geoCoordinate else None
            lon = address.geoCoordinate.longitude if address.geoCoordinate else None
            coordinate_provenance = "source"
            if lat is None:
                coordinates = geocode(address.city, address.country)
                if coordinates:
                    lat, lon = coordinates
                    coordinate_provenance = "derived"
                else:
                    flags.append("MISSING_COORDINATES")
            start, end = time(0), time(23, 59)
            for name, value in (("start", place.startTime), ("end", place.endTime)):
                if value is not None:
                    parsed = time.fromisoformat(value.rstrip("Z"))
                    parsed = parsed.replace(second=0, microsecond=0)
                    if len(value) != 5:
                        flags.append("TIME_FORMAT_TOLERATED")
                    if name == "start":
                        start = parsed
                    else:
                        end = parsed
                else:
                    flags.append("TIME_WINDOW_DAY_ONLY")
            service = enrichment.get("service_minutes")
            if isinstance(service, list):
                service = service[index]
            if service is None:
                service = 30
                flags.append("SERVICE_TIME_DEFAULTED")
            provenance = {
                key: "source"
                for key in (
                    "stop_type",
                    "city",
                    "postal_code",
                    "country_code",
                    "window_start",
                    "window_end",
                )
            }
            provenance.update(
                lat=coordinate_provenance,
                lon=coordinate_provenance,
                timezone="inferred",
                service_minutes="generated_mock" if "service_minutes" in enrichment else "default",
            )
            stops.append(
                StopView(
                    sequence=index,
                    stop_type=cast(Literal["LOADING", "UNLOADING"], place.loadingType),
                    city=address.city,
                    postal_code=address.postalCode,
                    country_code=address.country,
                    lat=lat,
                    lon=lon,
                    timezone=timezone,
                    window_start=datetime.combine(
                        place.earliestLoadingDate, start, ZoneInfo(timezone)
                    ).astimezone(UTC),
                    window_end=datetime.combine(
                        place.latestLoadingDate, end, ZoneInfo(timezone)
                    ).astimezone(UTC),
                    service_minutes=service,
                    provenance=provenance,
                )
            )
        pallets = enrichment.get("pallet_count")
        pallet_provenance = "generated_mock"
        if pallets is None:
            if raw.length_m is not None:
                pallets = int(
                    (raw.length_m * Decimal("2.4")).to_integral_value(rounding=ROUND_CEILING)
                )
                flags.append("PALLETS_DERIVED")
                pallet_provenance = "derived"
            else:
                flags.append("MISSING_CAPACITY_DATA")
        fields = {
            key: "source"
            for key in (
                "source_offer_id",
                "description",
                "public_remark",
                "revenue",
                "weight_kg",
                "loading_length_m",
                "required_body_types",
                "required_vehicle_types",
                "required_equipment",
                "stops",
            )
        }
        fields.update(
            pallet_count=pallet_provenance,
            pallet_type="generated_mock" if "pallet_type" in enrichment else "default",
            loading_length_meaning="inferred",
        )
        weight_kg = (
            int((raw.weight_t * 1000).quantize(Decimal("1"), rounding=ROUND_HALF_UP))
            if raw.weight_t is not None
            else None
        )
        if weight_kg == 0:  # FEAT-002 §8: the engine treats it as missing capacity data
            flags.append("ZERO_WEIGHT")
        revenue = (
            Revenue(
                amount_minor=int(
                    (raw.price.amount * 100).quantize(Decimal("1"), rounding=ROUND_HALF_UP)
                ),
                currency=raw.price.currency,
            )
            if raw.price
            else None
        )
        retention = max(stop.window_end for stop in stops) + timedelta(days=1)
        return completeness(
            NormalizedOffer(
                source_offer_id=raw.id,
                description=raw.freightDescription,
                public_remark=raw.publicRemark,
                revenue=revenue,
                weight_kg=weight_kg,
                loading_length_m=raw.length_m,
                pallet_count=pallets,
                pallet_type=enrichment.get("pallet_type", "UNKNOWN"),
                required_body_types=raw.vehicleProperties.body,
                required_vehicle_types=raw.vehicleProperties.type,
                required_equipment=raw.vehicleProperties.equipment,
                quality_flags=flags,
                field_provenance=fields,
                stops=stops,
                retention_until=retention,
            )
        )
