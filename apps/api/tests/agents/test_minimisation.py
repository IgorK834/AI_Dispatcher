"""Data minimisation (FR-28): no private data and no internal id in any model input."""

import json
import re
from pathlib import Path

import pytest
from langchain_core.messages import BaseMessage

from tests.agents.conftest import ToolEnv
from tests.agents.scenario import QUESTION, decision
from tests.agents.test_graph_flow import demo_scenario

UUID_TEXT = re.compile(
    r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}"
)


def model_text(message: BaseMessage) -> str:
    """What the model reads: the content and the arguments of tool calls. LangChain's own
    random message ids are bookkeeping of the framework and never reach the provider as data."""
    calls = json.dumps(getattr(message, "tool_calls", []), default=str)
    return f"{message.type}\n{message.content}\n{calls}"


@pytest.mark.ac("AC-FEAT-006-20")
def test_no_model_input_of_a_full_run_contains_names_phones_emails_or_internal_ids(
    worker_env: ToolEnv, generated_offers: object, tmp_path: Path
) -> None:
    drivers = worker_env.fleet.list_active()
    assert len(drivers) == 5
    secrets = [driver.name for driver in drivers] + [driver.phone for driver in drivers]
    secrets += ["tools@example.test", "private@example.test", str(worker_env.user)]
    secrets += [str(driver.id) for driver in drivers]
    first = drivers[0]
    # The user's own message names a driver and gives a phone number, an address and an id.
    question = (
        f"{QUESTION} Driver {first.name}, phone {first.phone}, mail private@example.test, "
        f"id {first.id}."
    )
    run = demo_scenario(worker_env, tmp_path)
    assert run.start(question).waiting
    outcome = run.decide("approve")
    assert not outcome.waiting and outcome.state["assigned"] is True
    inputs = run.recorded()
    assert len(inputs) >= 12, "specialists, Dispatcher and final answer were all recorded"
    texts = [model_text(message) for _role, messages in inputs for message in messages]
    assert any("[email]" in text and "[contact]" in text for text in texts), (
        "the question was redacted"
    )
    seen_refs: set[str] = set()
    for role, messages in inputs:
        text = "\n".join(model_text(message) for message in messages)
        for secret in secrets:
            assert secret and secret not in text, f"{role} input contains private data: {secret!r}"
        assert not UUID_TEXT.search(text), f"{role} input contains an internal UUID"
        seen_refs.update(re.findall(r"\bD\d+\b", text))
    assert seen_refs and seen_refs <= {f"D{n}" for n in range(1, 6)}, seen_refs
    # The driver's display name exists only for the approval card shown to the human.
    payload = run.store.find("approval_requests", run_id=run.run_id)[0]["payload"]
    assert {row["driverLabel"] for row in payload["plans"]} <= {driver.name for driver in drivers}
    assert all(row["driverRef"].startswith("D") for row in payload["plans"])


@pytest.mark.ac("AC-FEAT-006-20")
def test_the_dispatcher_decision_helper_is_a_plain_structured_route() -> None:
    assert decision("finish").tool_calls[0]["args"]["next"] == "finish"
