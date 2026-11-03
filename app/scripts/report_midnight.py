"""List sessions where the Moscow calendar date differs from the London one."""

from __future__ import annotations

import json
from pathlib import Path

APP_ROOT = Path(__file__).resolve().parents[1]
PROJECT_ROOT = APP_ROOT.parent
sessions = json.loads(
    (PROJECT_ROOT / "streams" / "_sessions.json").read_text(encoding="utf-8")
)
rows = [s for s in sessions if s["date_iso"] != s["date_group_london"]]
print(f"moscow/london date mismatch: {len(rows)}")
for s in rows:
    print(
        f"  {s['session_id']:>16} | msk {s['start_msk']} | london {s['start_london']}"
    )
