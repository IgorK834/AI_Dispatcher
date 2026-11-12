"""Service-layer view of the fleet models, so the HTTP layer never imports the domain package."""

from routepilot.fleet.domain.models import (
    CostProfileCreate as CostProfileCreate,
)
from routepilot.fleet.domain.models import (
    CostProfileUpdate as CostProfileUpdate,
)
from routepilot.fleet.domain.models import (
    CostProfileView as CostProfileView,
)
from routepilot.fleet.domain.models import (
    DriverCreate as DriverCreate,
)
from routepilot.fleet.domain.models import (
    DriverStateCreate as DriverStateCreate,
)
from routepilot.fleet.domain.models import (
    DriverStateView as DriverStateView,
)
from routepilot.fleet.domain.models import (
    DriverUpdate as DriverUpdate,
)
from routepilot.fleet.domain.models import (
    DriverView as DriverView,
)
from routepilot.fleet.domain.models import (
    VehicleCreate as VehicleCreate,
)
from routepilot.fleet.domain.models import (
    VehicleUpdate as VehicleUpdate,
)
from routepilot.fleet.domain.models import (
    VehicleView as VehicleView,
)

__all__ = [
    "CostProfileCreate",
    "CostProfileUpdate",
    "CostProfileView",
    "DriverCreate",
    "DriverStateCreate",
    "DriverStateView",
    "DriverUpdate",
    "DriverView",
    "VehicleCreate",
    "VehicleUpdate",
    "VehicleView",
]
