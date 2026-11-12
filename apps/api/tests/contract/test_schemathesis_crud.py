"""The committed contract lists every path, method and status of FEAT-001 §6.2, and the CRUD
endpoints conform to it when called with an authenticated session (schemathesis 4.33.2)."""

import json
import re
from pathlib import Path
from typing import Any

import pytest
import schemathesis
from hypothesis import HealthCheck, given, settings
from schemathesis.specs.openapi.checks import positive_data_acceptance

from tests.factories import ORIGIN, api_client

ROOT = Path(__file__).resolve().parents[4]
P = "/api/v1"
ID = "{id}"

# FEAT-001 §6.2: success status, the specific errors, plus the universal ones of the intro
# (401 and 403 on every protected endpoint, 422 where the request has parameters or a body).
SECTION_6_2: dict[tuple[str, str], set[str]] = {
    ("GET", f"{P}/auth/captcha-config"): {"200"},
    ("POST", f"{P}/auth/login"): {"200", "400", "401", "403", "422", "429"},
    ("POST", f"{P}/auth/logout"): {"204", "401", "403"},
    ("GET", f"{P}/auth/me"): {"200", "401"},
    ("GET", f"{P}/drivers"): {"200", "401", "422"},
    ("POST", f"{P}/drivers"): {"201", "401", "403", "404", "409", "422"},
    ("GET", f"{P}/drivers/{ID}"): {"200", "401", "404", "422"},
    ("PATCH", f"{P}/drivers/{ID}"): {"200", "401", "403", "404", "409", "422"},
    ("DELETE", f"{P}/drivers/{ID}"): {"204", "401", "403", "404", "409", "422"},
    ("GET", f"{P}/drivers/{ID}/state"): {"200", "401", "404", "422"},
    ("POST", f"{P}/drivers/{ID}/state"): {"201", "401", "403", "404", "422"},
    ("GET", f"{P}/vehicles"): {"200", "401", "422"},
    ("POST", f"{P}/vehicles"): {"201", "401", "403", "404", "409", "422"},
    ("GET", f"{P}/vehicles/{ID}"): {"200", "401", "404", "422"},
    ("PATCH", f"{P}/vehicles/{ID}"): {"200", "401", "403", "404", "409", "422"},
    ("DELETE", f"{P}/vehicles/{ID}"): {"204", "401", "403", "404", "409", "422"},
    ("GET", f"{P}/cost-profiles"): {"200", "401", "422"},
    ("POST", f"{P}/cost-profiles"): {"201", "401", "403", "409", "422"},
    ("GET", f"{P}/cost-profiles/{ID}"): {"200", "401", "404", "422"},
    ("PATCH", f"{P}/cost-profiles/{ID}"): {"200", "401", "403", "404", "409", "422"},
    ("DELETE", f"{P}/cost-profiles/{ID}"): {"204", "401", "403", "404", "409", "422"},
    ("GET", f"{P}/freight-offers"): {"200", "401", "422"},
    ("POST", f"{P}/freight-offers"): {"201", "401", "403", "422"},
    ("GET", f"{P}/freight-offers/{ID}"): {"200", "401", "404", "422"},
    ("PATCH", f"{P}/freight-offers/{ID}"): {"200", "401", "403", "404", "409", "422"},
    ("DELETE", f"{P}/freight-offers/{ID}"): {"204", "401", "403", "404", "409", "422"},
}
CRUD_PREFIXES = (f"{P}/drivers", f"{P}/vehicles", f"{P}/cost-profiles", f"{P}/freight-offers")


def normalise(path: str) -> str:
    return re.sub(r"\{[^}]+\}", ID, path)


def documented(spec: dict[str, Any]) -> dict[tuple[str, str], set[str]]:
    return {
        (method.upper(), normalise(path)): set(operation["responses"])
        for path, item in spec["paths"].items()
        for method, operation in item.items()
        if path.startswith(P)
    }


@pytest.mark.ac("AC-FEAT-001-32")
def test_the_committed_contract_lists_every_path_method_and_status_of_section_6_2(
    tmp_path: Path,
) -> None:
    committed = json.loads((ROOT / "contracts/openapi.json").read_text())
    with api_client(tmp_path) as client:
        live = client.app.openapi()
    for label, spec in (("committed contract", committed), ("running app", live)):
        found = documented(spec)
        missing = {key for key in SECTION_6_2 if key not in found}
        assert not missing, f"{label}: endpoints missing: {sorted(missing)}"
        gaps = {
            f"{method} {path}": sorted(want - found[(method, path)])
            for (method, path), want in SECTION_6_2.items()
            if want - found[(method, path)]
        }
        assert not gaps, f"{label}: status codes of §6.2 not documented: {gaps}"
    assert committed == json.loads(json.dumps(live)), "run `make openapi`: the contract is stale"


@pytest.mark.ac("AC-FEAT-001-32")
def test_crud_endpoints_conform_to_the_contract_with_an_authenticated_session(
    tmp_path: Path,
) -> None:
    with api_client(tmp_path, "admin", seeded=True) as client:
        schema = schemathesis.openapi.from_asgi("/openapi.json", client.app)
        auth = {
            "headers": {"Origin": ORIGIN, "X-CSRF-Token": client.headers["X-CSRF-Token"]},
            "cookies": dict(client.cookies),
        }
        operations = [
            result.ok()
            for result in schema.get_all_operations()
            if result.ok().path.startswith(CRUD_PREFIXES)
        ]
        assert len(operations) == sum(path.startswith(CRUD_PREFIXES) for _, path in SECTION_6_2)
        for operation in operations:

            @settings(
                max_examples=12,
                deadline=None,
                derandomize=True,
                suppress_health_check=list(HealthCheck),
            )
            @given(case=operation.as_strategy())
            def run(case: Any) -> None:
                response = case.call(**auth)
                # Every other check stays on: status codes, content types, headers and response
                # bodies must match the contract, and no server error may occur. ST202 (a
                # schema-valid request must be accepted) is the one exception: some rules cannot
                # be written in JSON Schema (decimal places, the opaque signed `cursor`, unknown
                # references), and the server rightly answers those with a documented 422/404.
                # The acceptance of valid requests is covered by the CRUD tests in tests/api.
                case.validate_response(response, excluded_checks=[positive_data_acceptance])

            run()
