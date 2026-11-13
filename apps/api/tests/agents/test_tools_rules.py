"""check_plan_rules through the real registry, on a stored plan and on a plan made invalid."""

import pytest

from routepilot.agents.tools import contracts
from routepilot.optimization.engine.models import ValidationResult
from routepilot.optimization.jobs.service import PlanService
from tests.agents.conftest import D1_POOL, ToolEnv

FLEET, PLANNER = "fleet_compliance", "route_planner"


class InvalidPlans(PlanService):
    """A PlanService whose validator rejects every stored plan (the spec's fake PlanService)."""

    def validate(self, plan_id: object) -> ValidationResult:
        return ValidationResult(valid=False, errors=["WORK_LIMIT_EXCEEDED", "HOME_BY_MISSED"])


def first_plan_ref(env: ToolEnv) -> str:
    result = env.call(
        PLANNER, "optimize_driver", driver_ref="D1", offer_ids=env.planning_pool(D1_POOL)
    )
    plans = result["plans"]["profit"]
    if not plans:
        pytest.fail("the fixture offers no longer produce a plan; see D1_POOL in conftest.py")
    return str(plans[0]["plan_ref"])


@pytest.mark.ac("AC-FEAT-006-32")
def test_check_plan_rules_reports_a_valid_stored_plan_with_profile_and_counts(
    worker_env: ToolEnv, generated_offers: object
) -> None:
    reference = first_plan_ref(worker_env)
    result = worker_env.call(FLEET, "check_plan_rules", plan_ref=reference)
    assert set(result) == set(contracts.CheckPlanRulesOutput.model_fields)
    assert result["plan_ref"] == reference and "plan_id" not in result
    assert result["valid"] is True and result["violations"] == []
    assert result["rules_profile"] == "pl_domestic_employee_v1"
    # The counts and limits are the service's: this plan needs a break and a daily rest.
    plan_id = worker_env.registry._plan_id(reference, worker_env.state)
    direct = worker_env.plans.check_plan_rules(plan_id)
    assert result["inserted_breaks"] == direct.inserted_breaks >= 1
    assert result["inserted_daily_rests"] == direct.inserted_daily_rests >= 1
    assert result["max_work_day_min"] == direct.max_work_day_min
    assert result["max_drive_day_min"] == direct.max_drive_day_min
    assert result["home_reached"] is direct.home_reached
    assert result["finish_at"].startswith(direct.finish_at.strftime("%Y-%m-%dT%H:%M"))


@pytest.mark.ac("AC-FEAT-006-32")
def test_check_plan_rules_lists_the_violated_invariants_of_an_invalid_plan(
    worker_env: ToolEnv, generated_offers: object
) -> None:
    reference = first_plan_ref(worker_env)
    registry = worker_env.registry
    registry.plans = InvalidPlans(
        worker_env.plans.repository.engine, worker_env.clock, worker_env.plans.routing
    )
    result = worker_env.call(FLEET, "check_plan_rules", plan_ref=reference)
    assert result["valid"] is False
    assert [item["invariant"] for item in result["violations"]] == [
        "WORK_LIMIT_EXCEEDED",
        "HOME_BY_MISSED",
    ]
    assert all(set(item) == {"invariant", "message"} for item in result["violations"])


@pytest.mark.ac("AC-FEAT-006-32")
def test_check_plan_rules_unknown_reference_and_strict_input(worker_env: ToolEnv) -> None:
    assert worker_env.call(FLEET, "check_plan_rules", plan_ref="PLAN-ffffffff")["error"][
        "code"
    ] == ("NOT_FOUND")
    assert worker_env.call(FLEET, "check_plan_rules", plan_ref="PLAN-ffffffff", x=1)["error"][
        "code"
    ] == ("VALIDATION_ERROR")
    # The tool belongs to Fleet & Compliance only.
    assert worker_env.call(PLANNER, "check_plan_rules", plan_ref="PLAN-ffffffff")["error"][
        "code"
    ] == ("TOOL_NOT_ALLOWED")
