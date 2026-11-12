"""Offline harness checks for the AC-40/41 runner and the hard campaign ledger."""

import asyncio
from pathlib import Path

import pytest
from evals.ledger import CampaignLedger, DurableBudget
from evals.runner import ROOT, run_scenario, summarise
from evals.schema import load_scenarios

from routepilot.agents.guards import BudgetExceeded


@pytest.mark.ac("AC-FEAT-006-40")
@pytest.mark.ac("AC-FEAT-006-41")
def test_scenario_set_meets_minimum_sizes_and_injections_are_detectable() -> None:
    from routepilot.freight.normalization import suspicious_text

    scenarios = load_scenarios(ROOT)
    injections = [s for s in scenarios if s.injection]
    assert len(scenarios) - len(injections) >= 30
    assert len(injections) >= 10
    # AC-41 asks for "reported as suspicious": the deterministic detector must flag each text.
    assert all(suspicious_text(s.injection) for s in injections)
    assert all(not s.expected_approval for s in injections)


@pytest.mark.ac("AC-FEAT-006-40")
@pytest.mark.parametrize(
    "scenario_id", ["approval-driver", "injection-03", "international-profile"]
)
def test_offline_run_uses_real_flow_and_never_assigns(tmp_path: Path, scenario_id: str) -> None:
    scenario = next(s for s in load_scenarios(ROOT) if s.id == scenario_id)
    result = asyncio.run(
        run_scenario(
            scenario, mode="offline", env_file=tmp_path / "none", budget=None, work=tmp_path
        )
    )
    assert result.error is None
    assert result.passed, result.checks
    assert result.write_violation is False
    assert result.status == ("waiting_approval" if scenario.expected_approval else "succeeded")
    summary = summarise([result], None)
    assert summary["write_policy_violations"] == 0
    assert summary["estimated_cost_usd"] is None


@pytest.mark.ac("AC-FEAT-006-40")
def test_campaign_ledger_is_immutable_once_and_hard_capped(tmp_path: Path) -> None:
    path = tmp_path / "ledger.json"
    with pytest.raises(ValueError):
        CampaignLedger(path, 500001)
    ledger = CampaignLedger(path)
    ledger.start_phase("smoke", ["a"], "fingerprint")
    with pytest.raises(ValueError):
        ledger.start_phase("smoke", ["a"], "fingerprint")  # no automatic rerun of a phase
    ledger.start_phase("smoke", ["a"], "fingerprint", retry=True)  # explicit retry only
    assert ledger.snapshot()["phases"]["smoke"]["attempts"][0]["status"] == "started"
    budget = DurableBudget(ledger, "smoke")
    ticket = budget.reserve(1000, 8192)
    budget.settle(ticket, 900, 100)
    assert ledger.usage(ledger.snapshot(), "smoke") == (900, 100)
    with pytest.raises(BudgetExceeded):
        budget.reserve(75000, 8192)  # 1 000 used + 83 192 would pass the 80 000 smoke cap
    assert ledger.usage(ledger.snapshot(), "smoke") == (900, 100)  # a refused call reserves nothing


@pytest.mark.ac("AC-FEAT-006-40")
def test_unknown_provider_outcome_is_charged_in_full_but_keeps_the_campaign_open(
    tmp_path: Path,
) -> None:
    ledger = CampaignLedger(tmp_path / "ledger.json")
    ledger.start_phase("evals", ["a"], "fingerprint")
    budget = DurableBudget(ledger, "evals")
    budget.unknown(budget.reserve(100, 100))
    assert ledger.usage(ledger.snapshot(), "evals") == (100, 100)  # the whole reservation
    assert ledger.snapshot()["closed"] is False
    DurableBudget(ledger, "evals").reserve(1, 1)  # the fallback may still be reserved
    # Usage above its reservation still closes the campaign.
    over = DurableBudget(ledger, "evals")
    ticket = over.reserve(10, 10)
    with pytest.raises(BudgetExceeded):
        over.settle(ticket, 50, 5)
    assert ledger.snapshot()["closed"] is True


@pytest.mark.ac("AC-FEAT-007-09")
def test_ai_evals_workflow_is_manual_secret_gated_and_ledger_bound() -> None:
    import yaml

    text = (ROOT.parent / ".github/workflows/ai-evals.yml").read_text()
    workflow = yaml.safe_load(text)
    assert set(workflow["on"]) == {"workflow_dispatch"}
    assert "secrets.GOOGLE_API_KEY" in text
    assert "--mode live" in text and "--confirm-live" in text and "--ledger" in text
    assert "permissions" in workflow and workflow["permissions"] == {"contents": "read"}
    assert "upload-artifact" in text


@pytest.mark.ac("AC-FEAT-006-40")
def test_reconcile_only_lowers_an_orphaned_reservation(tmp_path: Path) -> None:
    ledger = CampaignLedger(tmp_path / "ledger.json")
    ledger.start_phase("smoke", ["a"], "fingerprint")
    budget = DurableBudget(ledger, "smoke")
    budget.reserve(1000, 8192)  # never settled: an orphan counted at its full cap
    (entry,) = ledger.snapshot()["calls"]
    with pytest.raises(ValueError):
        ledger.reconcile(entry, 5000, 5000, "too high")
    ledger.reconcile(entry, 1317, 100, "run_budget of the failed attempt")
    assert ledger.usage(ledger.snapshot(), "smoke") == (1317, 100)
    assert ledger.snapshot()["calls"][entry]["reconciled"]["reserved_output"] == 8192
    with pytest.raises(ValueError):
        ledger.reconcile(entry, 1, 1, "twice")


@pytest.mark.ac("AC-FEAT-006-40")
def test_phase_caps_sum_to_the_approved_campaign_and_reopen_is_recorded(tmp_path: Path) -> None:
    from evals.ledger import CAMPAIGN_LIMIT, PHASE_LIMITS

    assert sum(PHASE_LIMITS.values()) == CAMPAIGN_LIMIT == 500000
    ledger = CampaignLedger(tmp_path / "ledger.json")
    with pytest.raises(ValueError):
        ledger.reopen("not closed")
    ledger.start_phase("smoke", ["a"], "fingerprint")
    budget = DurableBudget(ledger, "smoke")
    with pytest.raises(BudgetExceeded):
        budget.settle(budget.reserve(10, 10), 50, 5)  # usage above its reservation closes it
    assert ledger.snapshot()["closed"] is True
    ledger.reopen("test reason")
    assert ledger.snapshot()["closed"] is False
    assert ledger.snapshot()["reopened"] == ["test reason"]
