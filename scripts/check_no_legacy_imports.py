#!/usr/bin/env python3
"""Enforce the legacy boundary.

Modules under ``src/fvsc/`` (except ``src/fvsc/legacy/``) must NOT import from
``src.fvsc.legacy`` or any ``legacy`` submodule. The quarantine keeps the new
architecture independent of superseded code; removal of legacy is a separate step.

Exit code 0 = clean, 1 = violations found. Intended to run in CI.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent / "src" / "fvsc"
LEGACY_SEGMENT = "legacy"
# Match `from <pkg>.legacy...` / `import <pkg>.legacy...` / `from .legacy...` etc.
IMPORT_RE = re.compile(
    r"^\s*(?:from\s+[\w.]*legacy|import\s+[\w.]*legacy)\b",
    re.MULTILINE,
)


def main() -> int:
    if not ROOT.exists():
        print(f"skip: {ROOT} does not exist yet")
        return 0

    violations = []
    for py in sorted(ROOT.rglob("*.py")):
        rel = py.relative_to(ROOT)
        if rel.parts and rel.parts[0] == LEGACY_SEGMENT:
            continue
        text = py.read_text(encoding="utf-8", errors="ignore")
        for m in IMPORT_RE.finditer(text):
            violations.append(f"{py}: {m.group(0).strip()}")

    if violations:
        print("Legacy-boundary violations (src/fvsc must not import legacy):", file=sys.stderr)
        for v in violations:
            print(f"  {v}", file=sys.stderr)
        return 1

    print("OK: no src/fvsc module imports legacy.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
