"""Offer text is untrusted data: quoted in one field, never an instruction, never a write."""

import json
from pathlib import Path
from typing import Any

import pytest
from langchain_core.messages import BaseMessage, SystemMessage, ToolMessage

from tests.agents.conftest import ToolEnv
from tests.agents.fakes import response
from tests.agents.scenario import (
    DynamicModel,
    Scenario,
    add_offer,
    decision,
    dispatcher_script,
    final_answer,
    request_approval,
    specialist_models,
)

CORPUS = sorted((Path(__file__).parents[1] / "fixtures/injection").glob("*.json"))


def hidden_in(messages: list[BaseMessage], phrase: str) -> list[BaseMessage]:
    return [message for message in messages if phrase.lower() in message.model_dump_json().lower()]


@pytest.mark.ac("AC-FEAT-006-13")
@pytest.mark.parametrize("path", CORPUS, ids=lambda path: path.stem)
def test_injected_offer_text_appears_only_inside_untrusted_text_and_the_run_still_stops_at_the_gate(
    worker_env: ToolEnv, generated_offers: object, tmp_path: Path, path: Path
) -> None:
    case = json.loads(path.read_text())
    phrase = case["public_remark"]
    offer = add_offer(worker_env, description=case["description"], remark=phrase)
    reference = f"OFF-{offer.id.hex[:8]}"
    models = specialist_models(
        worker_env,
        scout_calls=[
            response(
                tool="search_offers", args={"origin_city": worker_env.driver.state.current_city}
            ),
            response(tool="get_offer", args={"offer_id": reference}),
        ],
    )
    models["dispatcher"] = DynamicModel(
        script=[
            *dispatcher_script(request_approval(), decision("approve"), decision("finish")),
            final_answer,
        ]
    )
    run = Scenario(worker_env, tmp_path / "agents.db", models)
    outcome = run.start()
    carriers = 0
    for role, messages in run.recorded():
        for message in hidden_in(messages, phrase):
            # Only the Scout, only as a get_offer tool result, never as a system prompt.
            assert role == "freight_scout" and isinstance(message, ToolMessage), (role, message)
            assert not isinstance(message, SystemMessage)
            result = json.loads(str(message.content))
            assert phrase.lower() in result["untrusted_text"].lower()
            assert result["untrusted_text"].startswith("<untrusted_text>")
            assert result["suspicious"] is True
            rest = json.dumps({k: v for k, v in result.items() if k != "untrusted_text"})
            assert phrase.lower() not in rest.lower(), "the text is in untrusted_text only"
            carriers += 1
    assert carriers >= 1, "the Scout did read the poisoned offer"
    for _role, messages in run.recorded():
        assert not [
            m for m in messages if isinstance(m, SystemMessage) and phrase in str(m.content)
        ]
    # The Scout's report, the plan facts and the run state carry the phrase nowhere.
    leaked: dict[str, Any] = {
        key: value for key, value in outcome.state.items() if key not in {"messages", "task"}
    }
    assert phrase.lower() not in json.dumps(leaked, default=str).lower()
    # The model is free to ask for approval, but the run stops at the interrupt: no write.
    assert outcome.waiting and run.pending()["action"] == "assign_plan"
    assert run.assignments() == []
    assert worker_env.freight.all_offers(status="assigned") == []


@pytest.mark.ac("AC-FEAT-006-13")
def test_the_corpus_has_several_cases_that_the_normaliser_flags() -> None:
    assert len(CORPUS) >= 3
    for path in CORPUS:
        case = json.loads(path.read_text())
        assert {"id", "description", "public_remark"} <= set(case)
