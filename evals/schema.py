"""Strict scenario contracts from FEAT-006 AC-40/41."""

from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, model_validator

TOOLS = frozenset(
    {
        "search_offers",
        "get_offer",
        "offer_quality",
        "list_drivers",
        "driver_state",
        "driver_availability",
        "check_plan_rules",
        "optimize_driver",
        "optimize_fleet",
        "get_plan",
        "compare_plans",
        "request_approval",
        "explain_plan",
    }
)


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class KeyFact(StrictModel):
    kind: Literal[
        "tool_called",
        "offer_observed",
        "suspicious_offer",
        "plans_valid",
        "no_assignment",
        "answer_grounded",
        "approval_required",
        "quality_flag",
        "driver_observed",
    ]
    value: str | None = None


class Scenario(StrictModel):
    version: Literal[1]
    id: str = Field(pattern=r"^[a-z0-9][a-z0-9_-]+$")
    question: str = Field(min_length=5, max_length=2000)
    locale: Literal["en", "pl"]
    fleet_fixture: str
    offer_fixture: str
    expected_tools: list[str] = Field(min_length=1)
    expected_approval: bool
    key_facts: list[KeyFact] = Field(min_length=1)
    injection: str | None = Field(default=None, max_length=300)
    smoke: bool = False

    @model_validator(mode="after")
    def tool_names(self) -> "Scenario":
        if not set(self.expected_tools) <= TOOLS:
            raise ValueError("unknown expected tool")
        if self.injection and self.expected_approval:
            raise ValueError("injection scenarios never authorise an assignment")
        return self


def load_scenarios(root: Path, *, smoke: bool = False) -> list[Scenario]:
    result = []
    for path in sorted([*root.glob("agents/*.yaml"), *root.glob("injection/*.yaml")]):
        scenario = Scenario.model_validate(yaml.safe_load(path.read_text()))
        if path.parent.name == "injection" and not scenario.injection:
            raise ValueError(f"injection text required: {path.name}")
        for relative in (scenario.fleet_fixture, scenario.offer_fixture):
            resolved = (root / relative).resolve()
            if not resolved.is_relative_to((root / "fixtures").resolve()) or not resolved.is_file():
                raise ValueError(f"fixture must be a local evaluation fixture: {relative}")
        if not smoke or scenario.smoke:
            result.append(scenario)
    if len({s.id for s in result}) != len(result):
        raise ValueError("duplicate scenario id")
    return result


def load_fixture(root: Path, relative: str) -> dict[str, Any]:
    path = (root / relative).resolve()
    if not path.is_relative_to((root / "fixtures").resolve()):
        raise ValueError("fixture outside evaluation directory")
    value = yaml.safe_load(path.read_text())
    if not isinstance(value, dict):
        raise ValueError("fixture must be an object")
    return value
