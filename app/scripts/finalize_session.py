"""Finalize one session: sync times, apply verdicts, run the checker.

Usage:
    python app/scripts/finalize_session.py 186
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

APP_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = APP_ROOT / "scripts"
PYTHON = sys.executable


def run(script: str, *args: str) -> int:
    return subprocess.run(
        [PYTHON, str(SCRIPTS / script), *args], cwd=APP_ROOT
    ).returncode


def main() -> int:
    if len(sys.argv) != 2:
        print("usage: finalize_session.py <session_id>")
        return 2
    sid = sys.argv[1]
    run("apply_verdicts.py", sid)
    run("apply_verdicts_to_note.py", sid)
    return run("check_notes.py", sid)


if __name__ == "__main__":
    raise SystemExit(main())
