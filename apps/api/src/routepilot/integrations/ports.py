"""Public integration port names from the approved adapter contract."""

from pydantic import BaseModel

from routepilot.freight.domain.models import (
    FreightSearchQuery,
    MappingFailure,
    NormalizedOffer,
    RawOfferRecord,
)
from routepilot.freight.ports import FreightProvider, OfferMapper


class ProviderCapabilities(BaseModel):
    search: bool = True
    lookup: bool = False


__all__ = [
    "FreightProvider",
    "FreightSearchQuery",
    "MappingFailure",
    "NormalizedOffer",
    "OfferMapper",
    "ProviderCapabilities",
    "RawOfferRecord",
]
