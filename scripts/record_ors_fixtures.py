"""Prepare O-5 recordings for FEAT-004; no network without --record.

Run from the repository root with:
  uv run --project apps/api python scripts/record_ors_fixtures.py
  uv run --project apps/api python scripts/record_ors_fixtures.py --record

Put ORS_API_KEY in apps/api/.env, never in command arguments or chat. One approved
run sends at most two requests: a 3x3 matrix and one fastest driving-car route
through Katowice, Wroclaw and Dresden. It never retries or follows redirects.
Failures require review before another recording run; do not exhaust quotas to
obtain a rate-limit fixture. No rate-limit response is fabricated here.

Output JSON wraps the sanitised provider body in `response`; `_source` records
the endpoint, request, UTC capture time and attribution. Only numeric metrics
and LineString geometry are retained. No headers, account data or raw metadata
are saved. Review the diff and run gitleaks before committing real recordings.
This never changes data/mock/routing-matrix.json (source stays haversine_v1).

Sources verified 2026-11-11:
https://giscience.github.io/openrouteservice/api-reference/endpoints/matrix/
https://giscience.github.io/openrouteservice/api-reference/endpoints/directions/requests-and-return-types
Approval and completion record: https://github.com/IgorK834/AI_Dispatcher/issues/5
"""

import argparse
import json
import math
import shlex
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx

ROOT = Path(__file__).resolve().parents[1]
BASE_URL = "https://api.openrouteservice.org"
# City-centre coordinates from FEAT-002 section 6.1, ordered longitude/latitude.
POINTS = [[19.0238, 50.2649], [17.0385, 51.1079], [13.7373, 51.0504]]
REQUESTS = (
    (
        "matrix",
        "/v2/matrix/driving-car",
        {"locations": POINTS, "metrics": ["distance", "duration"], "units": "m"},
    ),
    (
        "directions",
        "/v2/directions/driving-car/geojson",
        {"coordinates": POINTS, "preference": "fastest", "instructions": False, "units": "m"},
    ),
)


def load_key(env_file: Path) -> str:
    entries = []
    for line in env_file.read_text().splitlines():
        name, separator, value = line.partition("=")
        if separator and name.strip() == "ORS_API_KEY":
            entries.extend(shlex.split(value, comments=True))
    if len(entries) != 1 or not entries[0]:
        raise RuntimeError("Set one nonempty ORS_API_KEY in the local .env before recording.")
    return entries[0]


def is_number(value: object) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def response_subset(kind: str, body: Any) -> dict[str, Any]:
    if not isinstance(body, dict):
        raise RuntimeError("ORS response is not a JSON object.")
    if kind == "matrix":
        result = {name: body.get(name) for name in ("distances", "durations")}
        for rows in result.values():
            if not isinstance(rows, list) or len(rows) != len(POINTS):
                raise RuntimeError("ORS matrix has missing rows.")
            for row in rows:
                if not isinstance(row, list) or len(row) != len(POINTS):
                    raise RuntimeError("ORS matrix has missing columns.")
                if not all(is_number(value) and value >= 0 for value in row):
                    raise RuntimeError("ORS matrix contains invalid or unroutable entries.")
        return result
    features = body.get("features")
    if (
        body.get("type") != "FeatureCollection"
        or not isinstance(features, list)
        or len(features) != 1
    ):
        raise RuntimeError("ORS directions must contain one GeoJSON feature.")
    feature = features[0]
    if not isinstance(feature, dict):
        raise RuntimeError("ORS directions feature is invalid.")
    geometry = feature.get("geometry")
    properties = feature.get("properties")
    if not isinstance(geometry, dict) or not isinstance(properties, dict):
        raise RuntimeError("ORS directions geometry or properties are invalid.")
    summary = properties.get("summary")
    if not isinstance(summary, dict):
        raise RuntimeError("ORS directions summary is invalid.")
    coordinates = geometry.get("coordinates", [])
    if (
        geometry.get("type") != "LineString"
        or not isinstance(coordinates, list)
        or len(coordinates) < 2
    ):
        raise RuntimeError("ORS directions has no LineString geometry.")
    for point in coordinates:
        if not isinstance(point, list) or len(point) != 2 or not all(map(is_number, point)):
            raise RuntimeError("ORS directions coordinates are invalid.")
        if not (-180 <= point[0] <= 180 and -90 <= point[1] <= 90):
            raise RuntimeError("ORS directions coordinates are out of range.")
    metrics = {name: summary.get(name) for name in ("distance", "duration")}
    if not all(is_number(value) and value >= 0 for value in metrics.values()):
        raise RuntimeError("ORS directions summary is invalid.")
    return {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "geometry": {"type": "LineString", "coordinates": coordinates},
                "properties": {"summary": metrics},
            }
        ],
    }


def record(key: str, output: Path, client: httpx.Client) -> None:
    if not key:
        raise RuntimeError("ORS_API_KEY is empty.")
    if any((output / f"{name}.json").exists() for name, _, _ in REQUESTS):
        raise RuntimeError("Existing ORS fixtures will not be overwritten.")
    documents = []
    for name, endpoint, request in REQUESTS:
        response = client.post(BASE_URL + endpoint, json=request, headers={"Authorization": key})
        if response.status_code != 200:
            raise RuntimeError(f"ORS {name} HTTP {response.status_code}; stopped without retry.")
        document = {
            "_source": {
                "url": BASE_URL + endpoint,
                "api_version": "v2",
                "profile": "driving-car",
                "recorded_at": datetime.now(UTC).isoformat(),
                "approval_issue": "https://github.com/IgorK834/AI_Dispatcher/issues/5",
                "request": request,
                "attribution": "© openrouteservice.org by HeiGIT | © OpenStreetMap contributors",
                "sanitisation": "Only distances, durations, route summary and geometry retained.",
                "units": {"distance": "metres", "duration": "seconds"},
            },
            "response": response_subset(name, response.json()),
        }
        content = json.dumps(document, indent=2, allow_nan=False) + "\n"
        if key in content:
            raise RuntimeError("Credential detected in fixture output; nothing written.")
        documents.append((output / f"{name}.json", content))
    output.mkdir(parents=True, exist_ok=True)
    for path, content in documents:
        with path.open("x") as stream:
            stream.write(content)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        "--record", action="store_true", help="Perform the owner-approved two-request run"
    )
    parser.add_argument("--env-file", type=Path, default=ROOT / "apps/api/.env")
    parser.add_argument("--out", type=Path, default=ROOT / "apps/api/tests/fixtures/ors")
    args = parser.parse_args(argv)
    if not args.record:
        print("Preview only: one 3x3 matrix request and one fastest directions request.")
        print("No key read or HTTP calls made. Use --record after adding ORS_API_KEY locally.")
        return 0
    try:
        key = load_key(args.env_file)
        with httpx.Client(timeout=30, follow_redirects=False, trust_env=False) as client:
            record(key, args.out, client)
    except RuntimeError as error:
        print(str(error), file=sys.stderr)
        return 1
    except (httpx.HTTPError, OSError, ValueError):
        print(
            "Recording failed; check the local key, network and response shape. No details logged.",
            file=sys.stderr,
        )
        return 1
    print(
        "Recorded two sanitised ORS responses. Review the diff and scan for secrets before commit."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
