"""Report session dates that changed compared to the archived per-video notes."""

from __future__ import annotations

import json
import re
from pathlib import Path

APP_ROOT = Path(__file__).resolve().parents[1]
PROJECT_ROOT = APP_ROOT.parent
sessions = json.loads(
    (PROJECT_ROOT / "streams" / "_sessions.json").read_text(encoding="utf-8")
)

shifts = []
for session in sessions:
    first = PROJECT_ROOT / session["parts"][0]["old_path"]
    head = first.read_text(encoding="utf-8")[:2000]
    match = re.search(r"\*\*Дата:\*\*\s*([0-9.]+)", head)
    if not match or match.group(1) == "—":
        continue
    day, month, year = match.group(1).split(".")
    old = f"{year}-{month}-{day}"
    if old != session["date_iso"]:
        shifts.append(
            (
                session["session_id"],
                old,
                session["date_iso"],
                session["start_msk"][11:16],
                session["start_london"][11:16],
            )
        )

print(f"date shifts: {len(shifts)} of {len(sessions)}")
for row in shifts:
    print("  ", " | ".join(row))
