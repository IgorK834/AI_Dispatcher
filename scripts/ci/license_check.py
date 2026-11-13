"""Licence gate of FEAT-007 Gate 8b: no GPL or AGPL licence in what runs in production.

Usage: license_check.py REQUIREMENTS_FILE [--pnpm]

REQUIREMENTS_FILE is a pinned `name==version` list (`uv export --no-dev`). The licence of every
pin is read from its PyPI metadata. With `--pnpm` the production dependencies of the web app are
read from `pnpm licenses list --prod --json` as well. LGPL is allowed (a library under it can be
used without making the application a derivative work); GPL and AGPL are not. For a licence given
as `A OR B` it is enough that one alternative is allowed, because the user may choose it.
A licence that cannot be determined is printed as a warning and does not fail the gate; a PyPI
that cannot be reached does fail it (exit 2), because then nothing was checked.
"""

import argparse
import json
import os
import platform
import re
import ssl
import subprocess
import sys
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any

PIN = re.compile(r"^([A-Za-z0-9][A-Za-z0-9._-]*)(?:\[[^\]]*\])?==([^\s;]+)")
COPYLEFT = re.compile(r"\bagpl|\bgpl|gnu (affero )?general public")
WEAK = re.compile(r"\blgpl|lesser|library general")


def denied(licence: str) -> bool:
    """True when the licence text is GPL or AGPL (LGPL excluded, `A OR B` needs one clean side)."""
    text = licence.lower()
    alternatives = [part for part in re.split(r"\s+or\s+", text) if part.strip()]
    return bool(alternatives) and all(
        COPYLEFT.search(part) is not None and WEAK.search(part) is None for part in alternatives
    )


def pins(path: Path) -> list[tuple[str, str]]:
    result = []
    for line in path.read_text().splitlines():
        match = PIN.match(line.strip())
        if match:
            result.append((match.group(1), match.group(2)))
    return result


def tls_context() -> ssl.SSLContext | None:
    """The macOS system certificates for Python builds that ship without any (python.org)."""
    bundle = Path("/etc/ssl/cert.pem")
    if platform.system() == "Darwin" and not os.environ.get("SSL_CERT_FILE") and bundle.exists():
        return ssl.create_default_context(cafile=str(bundle))
    return None


class LookupFailed(Exception):
    """PyPI could not be reached: the licence is unknown because the check could not run."""


def pypi_licence(name: str, version: str) -> str:
    url = f"https://pypi.org/pypi/{name}/{version}/json"
    for attempt in range(4):
        try:
            with urllib.request.urlopen(url, timeout=30, context=tls_context()) as response:
                info: dict[str, Any] = json.load(response)["info"]
            break
        except (urllib.error.URLError, TimeoutError):
            if attempt == 3:
                raise LookupFailed(f"{name}=={version}") from None
            time.sleep(1 + attempt)
    expression = (info.get("license_expression") or "").strip()
    if expression:
        return expression
    classifiers = [c.split("::")[-1].strip() for c in info.get("classifiers", []) if "License" in c]
    if classifiers:
        return " OR ".join(classifiers) if len(classifiers) > 1 else classifiers[0]
    text = (info.get("license") or "").strip()
    return text if 0 < len(text) <= 120 else ""


def pnpm_licences() -> list[tuple[str, str]]:
    output = subprocess.run(  # fixed pnpm command, no user input
        ["pnpm", "licenses", "list", "--prod", "--json"],  # noqa: S607  # reason: pnpm comes from PATH
        check=True,
        capture_output=True,
        text=True,
    ).stdout
    found = []
    for licence, packages in json.loads(output).items():
        for package in packages:
            found.append((f"{package['name']}@{','.join(package.get('versions', []))}", licence))
    return found


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("requirements", type=Path)
    parser.add_argument("--pnpm", action="store_true")
    args = parser.parse_args()

    checked = pins(args.requirements)
    try:
        with ThreadPoolExecutor(max_workers=16) as pool:
            python = list(
                zip(
                    [f"{name}=={version}" for name, version in checked],
                    pool.map(lambda pin: pypi_licence(*pin), checked),
                    strict=True,
                )
            )
    except LookupFailed as error:
        print(f"licence check could not run: PyPI did not answer for {error}", file=sys.stderr)
        return 2
    entries = [("python", name, licence) for name, licence in python]
    if args.pnpm:
        entries += [("node", name, licence) for name, licence in pnpm_licences()]

    unknown = [f"{kind}: {name}" for kind, name, licence in entries if not licence]
    offenders = [(kind, name, licence) for kind, name, licence in entries if denied(licence)]
    print(f"licence check: {len(entries)} runtime packages ({len(checked)} Python)")
    for item in unknown:
        print(f"warning: licence unknown for {item}")
    for kind, name, licence in offenders:
        print(f"DENIED ({kind}): {name} is licensed under {licence}")
    return 1 if offenders else 0


if __name__ == "__main__":
    sys.exit(main())
