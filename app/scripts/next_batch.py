"""List sessions that still need a note, newest first.

Usage:
    python app/scripts/next_batch.py 8
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

APP_ROOT = Path(__file__).resolve().parents[1]
PROJECT_ROOT = APP_ROOT.parent
STREAMS = PROJECT_ROOT / "streams"

limit = int(sys.argv[1]) if len(sys.argv) > 1 else 8
sessions = json.loads((STREAMS / "_sessions.json").read_text(encoding="utf-8"))

pending = []
for session in sessions:
    if not any(p["has_transcript"] for p in session["parts"]):
        continue
    if list(STREAMS.glob(f"{session['session_id']}_*.md")):
        continue
    if not all(p["has_transcript"] for p in session["parts"]):
        continue  # partial transcripts wait for a manual decision
    pending.append(session)

pending.sort(key=lambda s: s["start_utc"], reverse=True)
print(f"pending: {len(pending)}")
for session in pending[:limit]:
    print(
        f"{session['session_id']}\t{session['date']}\t{session['start_msk'][11:16]}\t"
        f"{len(session['parts'])}p\t{session['title'][:60]}"
    )
