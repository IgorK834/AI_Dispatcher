"""The stored trace of a finished run (AC-22), read from the real SQL store."""

from uuid import UUID

import pytest

from tests.agents.live_app import scenario, serve

REQUIRED = ("seq", "agent", "type", "status", "duration_ms")


@pytest.mark.ac("AC-FEAT-006-22")
def test_trace_has_one_row_per_step_and_leaks_neither_offer_text_nor_names(tmp_path) -> None:
    chosen = scenario("injection-01")
    assert chosen.injection
    with serve(tmp_path, scenario_id="injection-01") as live:
        live.sign_in_as("dispatcher")
        thread_id, run_id = live.start_run(chosen.question)
        run = live.wait_for(run_id, {"succeeded", "failed"})
        assert run["status"] == "succeeded"

        rows = live.services.store.find("agent_steps", run_id=UUID(run_id))
        assert [row["seq"] for row in rows] == list(range(1, len(rows) + 1))
        for row in rows:
            for column in REQUIRED:
                assert row[column] is not None, f"step {row['seq']} has no {column}"
            assert row["type"] in {"llm", "tool", "guard", "interrupt"}
            assert row["status"] in {"ok", "error", "rejected"}
            assert row["duration_ms"] >= 0

        state = live.services.agents.graph.get_state(
            {"configurable": {"thread_id": thread_id}}
        ).values
        by_type = {kind: [row for row in rows if row["type"] == kind] for kind in ("llm", "tool")}
        assert len(by_type["llm"]) == state["budget"]["steps"]  # one row per model call
        assert len(by_type["tool"]) == len(state["tool_results"])  # one row per tool call
        assert [row for row in rows if row["type"] == "guard"], "guard decisions are traced"
        assert all(row["tool_name"] for row in by_type["tool"])

        names = [driver["name"] for driver in live.http.get("/api/v1/drivers").json()["items"]]
        assert names
        for row in rows:
            for text in (row["input_summary"], row["output_summary"]):
                assert text is None or len(text) <= 500
                assert text is None or chosen.injection not in text
                assert text is None or "untrusted" not in text.lower()
                assert text is None or not any(name in text for name in names)
