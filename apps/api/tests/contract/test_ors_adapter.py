"""O-5 recorder safety, recorded-response parsing and ORS failure policy (FEAT-004 AC-04).

Only the two success responses were recorded (O-5); no rate-limit response was provoked or
fabricated, so the retry and fallback tests use a synthetic httpx transport and say so.
"""

import importlib.util
import json
from pathlib import Path
from types import ModuleType

import httpx
import pytest

from routepilot.routing.composite import CompositeRoutingProvider
from routepilot.routing.domain import GeoPoint
from routepilot.routing.ors import OrsRoutingProvider

SCRIPT = Path(__file__).resolve().parents[4] / "scripts/record_ors_fixtures.py"
POINTS = [
    GeoPoint(lat=50.2649, lon=19.0238),
    GeoPoint(lat=51.1079, lon=17.0385),
    GeoPoint(lat=51.0504, lon=13.7373),
]


@pytest.fixture
def recorder() -> ModuleType:
    spec = importlib.util.spec_from_file_location("record_ors_fixtures", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def responses() -> list[dict[str, object]]:
    """Artificial transport data, never represented as recorded ORS fixtures."""
    return [
        {
            "distances": [[0, 10, 20], [10, 0, 30], [20, 30, 0]],
            "durations": [[0, 1, 2], [1, 0, 3], [2, 3, 0]],
        },
        {
            "type": "FeatureCollection",
            "features": [
                {
                    "type": "Feature",
                    "geometry": {
                        "type": "LineString",
                        "coordinates": [[19.0238, 50.2649], [17.0385, 51.1079]],
                    },
                    "properties": {"summary": {"distance": 10, "duration": 1}},
                }
            ],
        },
    ]


def test_recorder_preview_and_missing_key_never_open_http(
    recorder: ModuleType,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    def unexpected_client(**kwargs: object) -> None:
        pytest.fail("HTTP must not start without an explicit recording and a key")

    monkeypatch.setattr(recorder.httpx, "Client", unexpected_client)
    env = tmp_path / ".env"
    assert recorder.main(["--env-file", str(env)]) == 0
    env.write_text("ORS_API_KEY=\n")
    assert recorder.main(["--record", "--env-file", str(env)]) == 1
    assert "ORS_API_KEY" in capsys.readouterr().err


def test_recorder_makes_two_bounded_requests_and_saves_only_numeric_route_data(
    recorder: ModuleType,
    tmp_path: Path,
) -> None:
    key = "offline-transport-credential"
    bodies = responses()
    requests = []

    def reply(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        assert request.url.host == "api.openrouteservice.org"
        assert request.url.scheme == "https" and not request.url.query
        assert request.headers["Authorization"] == key
        body = bodies[len(requests) - 1]
        body["metadata"] = {"api_key": key, "account": "private-account"}
        return httpx.Response(200, json=body, headers={"Authorization": key})

    with httpx.Client(transport=httpx.MockTransport(reply)) as client:
        recorder.record(key, tmp_path, client)
    assert len(requests) == 2
    matrix_request, route_request = [json.loads(r.content) for r in requests]
    assert len(matrix_request["locations"]) == 3
    assert matrix_request["metrics"] == ["distance", "duration"]
    assert route_request["preference"] == "fastest"
    documents = [json.loads(p.read_text()) for p in sorted(tmp_path.glob("*.json"))]
    assert len(documents) == 2
    for document in documents:
        text = json.dumps(document)
        assert key not in text and "Authorization" not in text and "private-account" not in text
        assert document["_source"]["approval_issue"].endswith("/issues/5")
        assert document["_source"]["recorded_at"]
        assert document["_source"]["request"]
    matrix = json.loads((tmp_path / "matrix.json").read_text())["response"]
    route = json.loads((tmp_path / "directions.json").read_text())["response"]
    assert matrix == {k: bodies[0][k] for k in ("distances", "durations")}
    assert route["features"][0]["geometry"] == bodies[1]["features"][0]["geometry"]


@pytest.mark.parametrize("status", [302, 401, 429, 503])
def test_recorder_stops_on_http_errors_without_retry_or_response_leaks(
    recorder: ModuleType,
    tmp_path: Path,
    status: int,
) -> None:
    calls = []
    key = "offline-error-credential"

    def reply(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        return httpx.Response(
            status, json={"error": key}, headers={"Location": "https://example.invalid/"}
        )

    with httpx.Client(transport=httpx.MockTransport(reply)) as client:
        with pytest.raises(RuntimeError, match=f"HTTP {status}") as error:
            recorder.record(key, tmp_path, client)
    assert key not in str(error.value)
    assert len(calls) == 1 and not list(tmp_path.glob("*.json"))


def test_recorder_transport_exceptions_do_not_print_credentials(
    recorder: ModuleType,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    key = "offline-exception-credential"
    env = tmp_path / ".env"
    env.write_text(f"ORS_API_KEY='{key}'\n")

    def fail(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadError(f"Untrusted transport error containing {key}", request=request)

    client = httpx.Client(transport=httpx.MockTransport(fail))
    monkeypatch.setattr(recorder.httpx, "Client", lambda **kwargs: client)
    assert recorder.main(["--record", "--env-file", str(env), "--out", str(tmp_path)]) == 1
    captured = capsys.readouterr()
    assert key not in captured.out + captured.err
    assert "Recording failed" in captured.err
    assert not list(tmp_path.glob("*.json"))


@pytest.mark.parametrize("field", ["geometry", "properties"])
def test_recorder_rejects_null_direction_objects_without_writing(
    recorder: ModuleType,
    tmp_path: Path,
    field: str,
) -> None:
    bodies = responses()
    bodies[1]["features"][0][field] = None
    calls = []

    def reply(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        return httpx.Response(200, json=bodies[len(calls) - 1])

    with httpx.Client(transport=httpx.MockTransport(reply)) as client:
        with pytest.raises(RuntimeError, match="invalid"):
            recorder.record("offline-credential", tmp_path, client)
    assert not list(tmp_path.glob("*.json"))


@pytest.mark.parametrize("case", ["existing", "incomplete_matrix", "invalid_directions"])
def test_recorder_refuses_overwrites_and_incomplete_recordings(
    recorder: ModuleType,
    tmp_path: Path,
    case: str,
) -> None:
    bodies = responses()
    if case == "existing":
        (tmp_path / "matrix.json").write_text("existing fixture\n")
    elif case == "incomplete_matrix":
        bodies[0]["distances"] = [[0, None]]
    else:
        bodies[1]["features"] = []
    calls = []

    def reply(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        return httpx.Response(200, json=bodies[len(calls) - 1])

    with httpx.Client(transport=httpx.MockTransport(reply)) as client:
        with pytest.raises(RuntimeError):
            recorder.record("offline-credential", tmp_path, client)
    if case == "existing":
        assert not calls and (tmp_path / "matrix.json").read_text() == "existing fixture\n"
    else:
        assert not list(tmp_path.glob("*.json"))


@pytest.mark.ac("AC-FEAT-004-04", "AC-FEAT-004-07")
def test_provider_maps_genuine_recorded_success_responses() -> None:
    """Real captured successes; rate-limit behavior is separately synthetic."""
    from decimal import ROUND_CEILING, ROUND_HALF_UP, Decimal

    fixtures = Path(__file__).resolve().parents[1] / "fixtures" / "ors"
    matrix = json.loads((fixtures / "matrix.json").read_text())["response"]
    directions = json.loads((fixtures / "directions.json").read_text())["response"]
    requests = []

    def reply(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        body = matrix if "/matrix/" in request.url.path else directions
        return httpx.Response(200, json=body)

    points = [
        GeoPoint(lat=50.2649, lon=19.0238),
        GeoPoint(lat=51.1079, lon=17.0385),
        GeoPoint(lat=51.0504, lon=13.7373),
    ]
    with httpx.Client(transport=httpx.MockTransport(reply)) as client:
        provider = OrsRoutingProvider(api_key="offline-fixture-credential", client=client)
        composite = CompositeRoutingProvider(ors=provider)
        mapped = composite.matrix(points)
        assert mapped.provider_id == "ors_driving_car_v1"
        for i in range(3):
            for j in range(3):
                assert mapped.distance_km[i][j] == (
                    Decimal(str(matrix["distances"][i][j])) / 1000
                ).quantize(Decimal(".01"), rounding=ROUND_HALF_UP)
                assert mapped.duration_min[i][j] == int(
                    (
                        Decimal(str(matrix["durations"][i][j])) * Decimal("1.08") / 60
                    ).to_integral_value(rounding=ROUND_CEILING)
                )
        route = composite.route(points, variant="FASTEST")
    feature = directions["features"][0]
    assert route.geometry == feature["geometry"]
    assert route.distance_km == (
        Decimal(str(feature["properties"]["summary"]["distance"])) / 1000
    ).quantize(Decimal(".01"), rounding=ROUND_HALF_UP)
    assert route.duration_min == int(
        (
            Decimal(str(feature["properties"]["summary"]["duration"])) * Decimal("1.08") / 60
        ).to_integral_value(rounding=ROUND_CEILING)
    )
    assert not route.approximate and len(requests) == 2


# --- Failure policy through a synthetic transport (not recorded ORS responses) ---


@pytest.mark.ac("AC-FEAT-004-04")
def test_rate_limit_transport_retries_then_falls_back_without_logging_key() -> None:
    # A synthetic transport status exercises policy; it is not a captured ORS response.
    calls = []
    waits = []

    def rate_limit(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        return httpx.Response(429, json={"error": "offline test rate limit"})

    with httpx.Client(transport=httpx.MockTransport(rate_limit)) as client:
        provider = CompositeRoutingProvider(
            ors=OrsRoutingProvider(api_key="offline-test-value", client=client, sleep=waits.append)
        )
        assert provider.matrix(POINTS).fallback
    assert len(calls) == 3
    assert waits == [0.25, 0.5]


@pytest.mark.ac("AC-FEAT-004-04")
def test_unroutable_or_incomplete_matrix_is_a_failure_with_fallback() -> None:
    for body in (
        {"durations": [[0]], "distances": [[0]]},
        {"durations": [[None] * 3] * 3, "distances": [[0] * 3] * 3},
    ):
        with httpx.Client(
            transport=httpx.MockTransport(lambda request, body=body: httpx.Response(200, json=body))
        ) as client:
            result = CompositeRoutingProvider(
                ors=OrsRoutingProvider(api_key="offline-test-value", client=client)
            ).matrix(POINTS)
            assert result.fallback


@pytest.mark.ac("AC-FEAT-004-04", "AC-FEAT-004-06")
@pytest.mark.parametrize(
    "failure", ["transport", "authentication", "list_json", "distance", "duration", "geometry"]
)
def test_ors_failures_fall_back_with_bounded_requests(failure: str) -> None:
    calls = []
    delays = []

    def reply(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        if failure == "transport":
            raise httpx.ReadTimeout("offline timeout", request=request)
        if failure == "authentication":
            return httpx.Response(401)
        if failure == "list_json":
            return httpx.Response(200, json=[])
        if failure == "geometry":
            return httpx.Response(
                200, json={"features": [{"geometry": {"type": "Point", "coordinates": [0, 0]}}]}
            )
        body = {"distances": [[0] * 3 for _ in range(3)], "durations": [[0] * 3 for _ in range(3)]}
        body["distances" if failure == "distance" else "durations"][0][1] = -1
        return httpx.Response(200, json=body)

    with httpx.Client(transport=httpx.MockTransport(reply)) as client:
        composite = CompositeRoutingProvider(
            ors=OrsRoutingProvider(api_key="offline-credential", client=client, sleep=delays.append)
        )
        if failure == "geometry":
            assert composite.route(POINTS, variant="FASTEST").approximate
        else:
            assert composite.matrix(POINTS).fallback
    assert len(calls) == (3 if failure == "transport" else 1)
    assert delays == ([0.25, 0.5] if failure == "transport" else [])


@pytest.mark.ac("AC-FEAT-004-04", "AC-FEAT-004-07")
def test_ors_request_limit_and_matrix_element_limit_are_enforced_locally() -> None:
    from routepilot.routing.domain import RoutingFailure

    class Timer:
        def __init__(self):
            self.seconds = 0.0
            self.waits = []

        def now(self):
            return self.seconds

        def sleep(self, seconds):
            self.waits.append(seconds)
            self.seconds += seconds

    timer = Timer()
    calls = []

    def reply(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        return httpx.Response(200, json={"distances": [[0]], "durations": [[0]]})

    with httpx.Client(transport=httpx.MockTransport(reply)) as client:
        provider = OrsRoutingProvider(
            api_key="offline-credential", client=client, sleep=timer.sleep, monotonic=timer.now
        )
        for _ in range(35):
            provider.matrix(POINTS[:1])
        assert len(calls) == 35 and timer.waits == [60]
        with pytest.raises(RoutingFailure, match="3500"):
            provider.matrix([POINTS[0]] * 60)
        assert len(calls) == 35
        disabled = OrsRoutingProvider(api_key="", client=client)
        with pytest.raises(RoutingFailure, match="disabled"):
            disabled.matrix(POINTS[:1])
        assert len(calls) == 35
