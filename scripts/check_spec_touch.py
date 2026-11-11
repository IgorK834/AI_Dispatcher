"""Check contract/spec coupling and canonical coding-agent instructions."""

import argparse
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GUARDED = (
    "contracts/",
    "apps/api/migrations/",
    "apps/api/src/routepilot/agents/prompts/",
    "apps/api/src/routepilot/agents/tools/",
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--base", default="origin/main")
    parser.add_argument("--head", default="HEAD")
    parser.add_argument("--agent-docs", action="store_true")
    args = parser.parse_args()
    if args.agent_docs:
        agents = (args.root / "AGENTS.md").read_text()
        claude = (args.root / "CLAUDE.md").read_text()
        errors = []
        if not claude.startswith("@AGENTS.md\n"):
            errors.append("CLAUDE.md must start with @AGENTS.md")
        if agents.count("\n") > 150:
            errors.append("AGENTS.md exceeds 150 lines")
        if "context.md" not in agents or "context.md" not in claude:
            errors.append("Both instruction files must reference context.md")
        for line in agents.splitlines():
            if "✅" in line:
                for name in re.findall(r"([A-Za-z][\w./-]*(?:\.md|/))\s*✅", line):
                    if not (args.root / name).exists():
                        errors.append(f"AGENTS.md marks missing path as existing: {name}")
    else:
        # S603/S607: fixed git executable, separate argument list, no shell;
        # refs are resolved to commit IDs before being used in a diff.
        refs = [
            subprocess.run(
                [
                    "git",
                    "-C",
                    str(args.root),
                    "rev-parse",
                    "--verify",
                    f"{ref}^{{commit}}",
                ],
                check=True,
                text=True,
                capture_output=True,
            ).stdout.strip()
            for ref in [args.base, args.head]
        ]
        changed = subprocess.run(
            ["git", "-C", str(args.root), "diff", "--name-only", *refs, "--"],
            check=True,
            capture_output=True,
            text=True,
        ).stdout.splitlines()
        errors = (
            ["Guarded files changed without a specs/ change"]
            if any(path.startswith(GUARDED) for path in changed)
            and not any(path.startswith("specs/") for path in changed)
            else []
        )
    for error in errors:
        print(error)
    return int(bool(errors))


if __name__ == "__main__":
    raise SystemExit(main())
