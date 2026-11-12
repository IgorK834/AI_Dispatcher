"""Generate data/mock/routing-matrix.json from data/mock/cities.json (FEAT-004 FR-6).

Run from apps/api:
  uv run python ../../scripts/generate_routing_matrix.py --source haversine \
      --out ../../data/mock/routing-matrix.json

Only the haversine variant is offered (OQ-004-02). It needs no key and no network, and it
reproduces the committed file byte for byte. An ORS-sourced file would need one matrix request
with the owner's key and approval and is not generated here.
"""

import argparse
import json
import sys
from pathlib import Path

from routepilot.routing.matrix_file import build_matrix_document

ROOT = Path(__file__).resolve().parents[1]
GENERATED_AT = "2026-11-11T00:00:00Z"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", choices=["haversine"], required=True)
    parser.add_argument("--cities", type=Path, default=ROOT / "data/mock/cities.json")
    parser.add_argument("--out", type=Path, default=ROOT / "data/mock/routing-matrix.json")
    parser.add_argument("--generated-at", default=GENERATED_AT)
    args = parser.parse_args(argv)
    try:
        cities = json.loads(args.cities.read_text())["cities"]
    except (OSError, KeyError, ValueError) as error:
        print(f"Cannot read the city table: {error}", file=sys.stderr)
        return 1
    document = build_matrix_document(cities, generated_at=args.generated_at)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(document, indent=2, ensure_ascii=False) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
