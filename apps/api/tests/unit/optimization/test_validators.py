"""Independent validators reject each specified corruption (FEAT-003 FR-32/33)."""

from datetime import timedelta
from decimal import Decimal

import pytest

from routepilot.optimization.engine import FleetValidator, RouteValidator, optimize
from routepilot.optimization.engine.fleet import fleet_solution
from routepilot.optimization.engine.models import Action

from .factories import T, driver, offer, point, snapshot


@pytest.mark.ac("AC-FEAT-003-25")
def test_validator_mutations_have_specific_errors() -> None:
    a, b = point("A"), point("B", 51.0504, 13.7373, "DE")
    d = driver(a, home_by=T + timedelta(days=2))
    o = offer("X", a, b, revenue=150000, delivery=(T, T + timedelta(days=2)))
    source = snapshot([d], [o])
    plan = optimize(source).per_driver["D"]["profit"][0]
    assert RouteValidator().validate(source, plan).valid
    stops = list(plan.stops)
    pickup = next(i for i, s in enumerate(stops) if s.kind == "PICKUP")
    corrupt_load = list(stops)
    corrupt_load[pickup] = stops[pickup].model_copy(update={"load_kg_after": 2000})
    corrupt_window = list(stops)
    corrupt_window[pickup] = stops[pickup].model_copy(
        update={"service_start_at": T + timedelta(days=1)}
    )
    mutations = [
        (plan.model_copy(update={"stops": corrupt_load}), "CAPACITY_INVALID"),
        (
            plan.model_copy(
                update={
                    "actions": [
                        Action(kind="DELIVERY", offer_id="X"),
                        Action(kind="PICKUP", offer_id="X"),
                    ]
                }
            ),
            "ACTION_ORDER_INVALID",
        ),
        (plan.model_copy(update={"stops": corrupt_window}), "WINDOW_MISSED"),
        (
            plan.model_copy(update={"stops": [s for s in stops if s.kind != "BREAK"]}),
            "BREAK_OR_LIMIT_INVALID",
        ),
        (plan.model_copy(update={"net_profit_minor": plan.net_profit_minor + 1}), "PROFIT_INVALID"),
        (plan.model_copy(update={"co2_kg": plan.co2_kg + Decimal(".01")}), "CO2_INVALID"),
        (
            plan.model_copy(update={"stops": [s for s in stops if s.kind != "END"]}),
            "HOME_END_MISSING",
        ),
        (plan.model_copy(update={"rules_profile": "pl_domestic_employee_v1"}), "WRONG_PROFILE"),
    ]
    for mutated, error in mutations:
        validation = RouteValidator().validate(source, mutated)
        assert not validation.valid
        assert error in validation.errors
    duplicate = plan.model_copy(update={"driver_id": "D2", "plan_ref": "duplicate"})
    d2 = d.model_copy(update={"id": "D2"})
    fleet_source = source.model_copy(update={"drivers": [d, d2]})
    solution = fleet_solution("profit", [plan, duplicate])
    assert (
        "DUPLICATED_ASSIGNMENT"
        in FleetValidator().validate(fleet_source, solution, [plan, duplicate]).errors
    )
