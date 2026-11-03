"""Run check_notes.py over every finished session and show only failures.

Usage:
    python app/scripts/check_all.py
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

APP_ROOT = Path(__file__).resolve().parents[1]
STREAMS = APP_ROOT.parent / "streams"
CLAIMS = APP_ROOT / "data" / "claims"
PYTHON = sys.executable


def main() -> int:
    ids = sorted(p.stem for p in CLAIMS.glob("*.json") if not p.stem.endswith("_verdicts"))
    failures = 0
    for sid in ids:
        if not list(STREAMS.glob(f"{sid}_*.md")):
            continue
        proc = subprocess.run(
            [PYTHON, str(APP_ROOT / "scripts" / "check_notes.py"), sid],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        if "FAIL" in proc.stdout:
            failures += 1
            print(proc.stdout.strip())
            print()
    print(f"checked {len(ids)}, failures {failures}")
    return 0 if failures == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
