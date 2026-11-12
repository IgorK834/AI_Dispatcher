"""Synthetic freight provider; searching is entirely offline."""

from collections.abc import Iterator
from datetime import datetime
from typing import Any

from routepilot.freight.domain.models import FreightSearchQuery, RawOfferRecord
from routepilot.freight.geocoding import geocode
from routepilot.freight.service.queries import haversine_km
from routepilot.integrations.ports import ProviderCapabilities


class MockFreightProvider:
    name = "mock_timocom_v3"

    def __init__(
        self, payload: dict[str, Any], enrichment: dict[str, Any], fetched_at: datetime
    ) -> None:
        self.payload, self.enrichment, self.fetched_at = payload, enrichment, fetched_at

    def capabilities(self) -> ProviderCapabilities:
        return ProviderCapabilities()

    def search(self, query: FreightSearchQuery) -> Iterator[RawOfferRecord]:
        for offer in self.payload["payload"]:
            if query.vehicle_type not in offer.get("vehicleProperties", {}).get("type", []):
                continue
            if (
                query.max_weight_kg is not None
                and float(offer.get("weight_t", 0)) * 1000 > query.max_weight_kg
            ):
                continue
            places = offer.get("loadingPlaces", [])
            if len(places) < 2:
                # Invalid provider records still reach the mapper and the failure counter.
                yield RawOfferRecord(
                    source=self.name,
                    source_offer_id=offer["id"],
                    payload=offer,
                    fetched_at=self.fetched_at,
                    enrichment=self.enrichment.get(offer["id"], {}),
                )
                continue
            first, last = places[0], places[-1]
            if not self._matches(query.origin, query.radius_km, first["address"]):
                continue
            if not self._matches(query.destination, query.radius_km, last["address"]):
                continue
            if (
                query.loading_from
                and first["latestLoadingDate"] < query.loading_from.date().isoformat()
            ):
                continue
            if (
                query.loading_to
                and first["earliestLoadingDate"] > query.loading_to.date().isoformat()
            ):
                continue
            yield RawOfferRecord(
                source=self.name,
                source_offer_id=offer["id"],
                payload=offer,
                fetched_at=self.fetched_at,
                enrichment=self.enrichment.get(offer["id"], {}),
            )

    @staticmethod
    def _matches(area: str | None, radius: object, address: dict[str, Any]) -> bool:
        if area is None:
            return True
        if area.casefold() in (address["city"].casefold(), address["country"].casefold()):
            return True
        if radius is not None:
            target = geocode(area, address["country"])
            coordinate = address.get("geoCoordinate")
            if target and coordinate:
                return haversine_km(
                    target, (coordinate["latitude"], coordinate["longitude"])
                ) <= float(str(radius))
        return False

    def lookup(self, source_offer_ids: list[str]) -> list[RawOfferRecord]:
        return []
