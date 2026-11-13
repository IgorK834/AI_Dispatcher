"""Live SSE streaming of a real run on scripted models (FEAT-006 AC-15 and AC-16).

The application is served by uvicorn (`tests/agents/live_app.py`), because the ASGI test
transports collect a streaming body before they return and could not show a live stream.
"""

import time
from uuid import UUID

import pytest

from routepilot.agents.api_models import EVENT_SCHEMAS
from tests.agents.live_app import Event, serve


def is_approval(event: Event) -> bool:
    return event.event == "approval_required"


@pytest.mark.ac("AC-FEAT-006-15")
def test_stream_opens_within_two_seconds_and_follows_the_event_contract(tmp_path) -> None:
    with serve(tmp_path, scenario_id="approval-driver") as live:
        live.sign_in_as("dispatcher")
        _, run_id = live.start_run()

        opened = time.monotonic()
        first = live.stream(run_id, until=lambda event: True)
        assert first[0].event == "run_started"
        assert time.monotonic() - opened < 2

        # Up to the approval request, then the decision, then the rest of the run.
        head = live.stream(run_id, until=is_approval)
        approval = live.run(run_id)["pendingApproval"]
        decided = live.http.post(
            f"/api/v1/agent/runs/{run_id}/resume",
            json={"approvalId": approval["approvalId"], "decision": "approve"},
        )
        assert decided.status_code == 202
        tail = live.stream(run_id, after=head[-1].id)
        events = head + tail

        assert [event.id for event in events] == list(range(1, len(events) + 1))
        assert events[0].event == "run_started"
        assert events[-1].event == "run_finished"
        started = [event for event in events if event.event == "step_started"]
        finished = [event for event in events if event.event == "step_finished"]
        assert started and {event.data["seq"] for event in started} == {
            event.data["seq"] for event in finished
        }
        for step in started:  # a step is announced before it is finished
            match = next(e for e in finished if e.data["seq"] == step.data["seq"])
            assert step.id < match.id
        for event in events:
            EVENT_SCHEMAS[event.event].model_validate(event.data)
        assert {"approval_required", "approval_resolved", "final_answer"} <= {
            event.event for event in events
        }


@pytest.mark.ac("AC-FEAT-006-16")
def test_reconnect_with_last_event_id_delivers_every_later_event_exactly_once(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import threading

    gate = threading.Event()
    with serve(tmp_path, scenario_id="approval-driver") as live:
        live.sign_in_as("dispatcher")
        original = live.services.tools.execute

        def held(*args, **kwargs):
            gate.wait(60)  # the first tool call waits, so the run goes on while the client is away
            return original(*args, **kwargs)

        monkeypatch.setattr(live.services.tools, "execute", held)
        try:
            _, run_id = live.start_run()
            head = live.stream(run_id, until=lambda event: event.id >= 4)  # then disconnect
            assert [event.id for event in head] == [1, 2, 3, 4]
            assert live.run(run_id)["status"] in {"queued", "running"}
            before_release = len(live.services.store.events(UUID(run_id)))
        finally:
            gate.set()

        live.wait_for(run_id, {"waiting_approval"})
        tail = live.stream(run_id, after=4, until=is_approval)
        everything = live.stream(run_id, until=is_approval)

        assert [event.id for event in tail] == list(range(5, tail[-1].id + 1))
        assert head + tail == everything  # nothing lost, nothing twice
        assert tail[-1].id > before_release  # some of it was produced while disconnected
