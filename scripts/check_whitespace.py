"""Fix trailing whitespace and the final newline in staged text files."""

import sys
from pathlib import Path

changed = False
for name in sys.argv[1:]:
    path = Path(name)
    original = path.read_bytes()
    normalized = (
        b"\n".join(line.rstrip(b" \t\r") for line in original.splitlines()).rstrip(b"\n") + b"\n"
    )
    if original != normalized:
        path.write_bytes(normalized)
        changed = True
raise SystemExit(int(changed))
