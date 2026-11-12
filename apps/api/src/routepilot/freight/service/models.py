"""Service-layer view of the freight models, so the HTTP layer never imports the domain package."""

from routepilot.freight.domain.models import (
    FreightOfferCreate as FreightOfferCreate,
)
from routepilot.freight.domain.models import (
    FreightOfferUpdate as FreightOfferUpdate,
)
from routepilot.freight.domain.models import (
    FreightOfferView as FreightOfferView,
)

__all__ = [
    "FreightOfferCreate",
    "FreightOfferUpdate",
    "FreightOfferView",
]
