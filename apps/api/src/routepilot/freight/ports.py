"""Freight import ports; adapters are injected above the domain boundary."""

from collections.abc import Iterator
from typing import Protocol

from routepilot.freight.domain.models import (
    FreightSearchQuery,
    MappingFailure,
    NormalizedOffer,
    RawOfferRecord,
)


class FreightProvider(Protocol):
    name: str

    def search(self, query: FreightSearchQuery) -> Iterator[RawOfferRecord]: ...
    def lookup(self, source_offer_ids: list[str]) -> list[RawOfferRecord]: ...


class OfferMapper(Protocol):
    source: str

    def to_domain(self, record: RawOfferRecord) -> NormalizedOffer | MappingFailure: ...
