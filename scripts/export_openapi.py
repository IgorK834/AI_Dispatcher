"""Deterministic OpenAPI export (AC-FEAT-000-07)."""

import argparse
import json
from pathlib import Path

from routepilot.main import app

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=ROOT / "contracts/openapi.json")
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    content = json.dumps(app.openapi(), indent=2, sort_keys=True) + "\n"
    if args.check:
        if not args.out.exists() or args.out.read_text() != content:
            print(f"OpenAPI drift: {args.out}")
            return 1
    else:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(content)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
