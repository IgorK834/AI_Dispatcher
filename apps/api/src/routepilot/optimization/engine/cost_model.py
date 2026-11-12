"""Public plan-timeline adapter for the shared FEAT-003 cost model."""

from dataclasses import dataclass
from datetime import datetime

from routepilot.optimization.engine.costs import CostModel as _CostModel
from routepilot.optimization.engine.costs import CostResult as CostBreakdown
from routepilot.optimization.engine.models import (
    CostProfile as CostProfileSpec,
)
from routepilot.optimization.engine.models import (
    DriverSnapshot,
    OfferSnapshot,
    PlanActivity,
    PlanLeg,
)
from routepilot.optimization.engine.models import (
    VehicleSnapshot as VehicleSpec,
)


@dataclass(frozen=True)
class Timeline:
    driver: DriverSnapshot
    offers: tuple[OfferSnapshot, ...]
    legs: tuple[PlanLeg, ...]
    activities: tuple[PlanActivity, ...]
    departure_at: datetime
    finish_at: datetime


class CostModel(_CostModel):
    """Expose the task brief's timeline-oriented cost interface."""

    def breakdown(
        self,
        plan_timeline: Timeline,
        profile: CostProfileSpec,
        vehicle: VehicleSpec,
    ) -> CostBreakdown:
        driver = plan_timeline.driver.model_copy(
            update={"cost_profile": profile, "vehicle": vehicle}
        )
        return self.calculate(
            driver,
            list(plan_timeline.offers),
            list(plan_timeline.legs),
            list(plan_timeline.activities),
            plan_timeline.departure_at,
            plan_timeline.finish_at,
        )


__all__ = [
    "CostBreakdown",
    "CostModel",
    "CostProfileSpec",
    "Timeline",
    "VehicleSpec",
]
