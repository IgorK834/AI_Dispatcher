"""Real-service tool allowlists, data minimization and approved write boundary.

The `tools` fixture lives in `tests/agents/conftest.py`.
"""

import json

import pytest


@pytest.mark.ac("AC-FEAT-006-02", "AC-FEAT-006-20", "AC-FEAT-006-29")
def test_allowlists_strict_inputs_and_stable_private_aliases(tools):
    registry, state, driver, _offer = tools
    assert len(registry.definitions) == 14
    assert {item["function"]["name"] for item in registry.schemas("dispatcher")} == {
        "explain_plan",
        "request_approval",
    }
    assert all(
        item["function"]["name"] != "assign_plan"
        for role in (
            "dispatcher",
            "freight_scout",
            "fleet_compliance",
            "route_planner",
            "explainer",
        )
        for item in registry.schemas(role)
    )
    assert (
        registry.execute("freight_scout", "assign_plan", {}, state)["error"]["code"]
        == "TOOL_NOT_ALLOWED"
    )
    assert (
        registry.execute("fleet_compliance", "list_drivers", {"extra": True}, state)["error"][
            "code"
        ]
        == "VALIDATION_ERROR"
    )
    registry.prepare(state)
    assert driver.name not in state["messages"][0].content and driver.name not in state["task"]
    assert driver.phone not in state["messages"][0].content
    assert state["plan_facts"] == {}
    first = registry.execute("fleet_compliance", "list_drivers", {}, state)
    again = registry.execute("fleet_compliance", "list_drivers", {}, state)
    assert first == again and first["count"] == 5
    serialized = json.dumps(first)
    assert (
        driver.name not in serialized
        and driver.phone not in serialized
        and str(driver.id) not in serialized
    )
