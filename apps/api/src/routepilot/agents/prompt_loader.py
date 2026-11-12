"""Load immutable versioned prompts and retain their content provenance."""

import re
from dataclasses import dataclass
from pathlib import Path

ROLES = ("dispatcher", "freight_scout", "fleet_compliance", "route_planner", "explainer")


@dataclass(frozen=True)
class Prompt:
    version: str
    text: str
    path: str


def load_prompts(directory: Path | None = None) -> dict[str, Prompt]:
    directory = directory or Path(__file__).with_name("prompts")
    result: dict[str, Prompt] = {}
    for role in ROLES:
        candidates = []
        for path in directory.glob(f"{role}.v*.md"):
            match = re.fullmatch(rf"{role}\.v([1-9]\d*)\.md", path.name)
            if match:
                candidates.append((int(match[1]), path))
        if not candidates:
            raise ValueError(f"Missing prompt for {role}")
        version, path = max(candidates)
        result[role] = Prompt(f"v{version}", path.read_text(), str(path))
    return result
