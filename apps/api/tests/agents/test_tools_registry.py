"""The tool registry matches FEAT-006 FR-5/FR-6 and the Agent Tool Specs of section 6.6."""

from typing import cast

import pytest
from pydantic import BaseModel

from routepilot.agents.models import Role
from routepilot.agents.tools import contracts
from tests.agents.conftest import ToolEnv

ALLOWLISTS = {
    "dispatcher": {"request_approval", "explain_plan"},
    "freight_scout": {"search_offers", "get_offer", "offer_quality"},
    "fleet_compliance": {"list_drivers", "driver_state", "driver_availability", "check_plan_rules"},
    "route_planner": {"optimize_driver", "optimize_fleet", "get_plan", "compare_plans"},
    "explainer": set(),
}


def test_allowlists_and_kinds_match_the_specification(tool_env: ToolEnv) -> None:
    definitions = tool_env.registry.definitions
    assert len(definitions) == 14
    for role, names in ALLOWLISTS.items():
        offered = {item["function"]["name"] for item in tool_env.registry.schemas(cast(Role, role))}
        assert offered == names, role
        assert {name for name, item in definitions.items() if role in item.roles} == names, role
    writes = {name for name, item in definitions.items() if item.kind == "write"}
    assert writes == {"assign_plan"}, "assign_plan is the only write tool"
    assert definitions["assign_plan"].roles == (), "only ApprovalGate may run it"
    assert all(definitions[name].kind == "read" for name in set(definitions) - {"assign_plan"}), (
        "optimisation and approval-request tools are read tools (OQ-006-05)"
    )


def test_every_tool_has_strict_input_and_output_models(tool_env: ToolEnv) -> None:
    for name, definition in tool_env.registry.definitions.items():
        for model in (definition.input_schema, definition.output_schema):
            assert issubclass(model, BaseModel)
            assert model.model_config.get("extra") == "forbid", f"{name}: {model.__name__}"
        assert definition.description, f"{name} needs a description for the model"


@pytest.mark.parametrize(
    ("model", "field", "limit"),
    [
        (contracts.SearchOffersOutput, "offers", 20),
        (contracts.OfferQualityOutput, "items", 20),
        (contracts.ListDriversOutput, "drivers", 20),
        (contracts.OfferDetail, "untrusted_text", 300),
        (contracts.OfferDetail, "stops", 2),
        (contracts.PlanDetail, "stops", 30),
        (contracts.ComparePlansOutput, "rows", 6),
    ],
)
def test_output_size_limits_are_part_of_the_output_schema(
    model: type[BaseModel], field: str, limit: int
) -> None:
    constraint = next(
        meta.max_length
        for meta in model.model_fields[field].metadata
        if getattr(meta, "max_length", None) is not None
    )
    assert constraint == limit


def test_write_and_unknown_tools_are_never_executed_for_a_model(tool_env: ToolEnv) -> None:
    for role in ALLOWLISTS:
        for name in ("assign_plan", "no_such_tool"):
            result = tool_env.call(role, name)
            assert result["error"]["code"] == "TOOL_NOT_ALLOWED", (role, name)
    assert tool_env.state["pending_approval"] is None
    assert tool_env.assignments.list_assignments().items == []
