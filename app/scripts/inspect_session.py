"""Inspect the raw timestamps behind a session for manual review."""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

APP_ROOT = Path(__file__).resolve().parents[1]
PROJECT_ROOT = APP_ROOT.parent
times = json.loads((APP_ROOT / "data" / "_times.json").read_text(encoding="utf-8"))
sessions = json.loads(
    (PROJECT_ROOT / "streams" / "_sessions.json").read_text(encoding="utf-8")
)
wanted = set(sys.argv[1:])

for session in sessions:
    if session["session_id"] not in wanted:
        continue
    print(f"== {session['session_id']} | {session['title']}")
    print(f"   msk={session['start_msk']} london={session['start_london']}")
    for part in session["parts"]:
        info = times.get(part["video_id"], {})
        ts = info.get("timestamp")
        rts = info.get("release_timestamp")
        fmt = lambda v: datetime.fromtimestamp(v, tz=timezone.utc).isoformat() if v else None
        print(
            f"   P{part['index']} {part['video_id']} | dur={info.get('duration')} "
            f"| timestamp={fmt(ts)} | release={fmt(rts)} | upload={info.get('upload_date')}"
        )
