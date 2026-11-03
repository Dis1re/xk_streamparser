"""Create per-session job files for the extraction and verification agents.

Usage:
    python app/scripts/make_jobs.py            # all sessions with a transcript
    python app/scripts/make_jobs.py 186 167    # only these
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

APP_ROOT = Path(__file__).resolve().parents[1]
PROJECT_ROOT = APP_ROOT.parent
STREAMS = PROJECT_ROOT / "streams"
JOBS = APP_ROOT / "data" / "jobs"
CLAIMS = APP_ROOT / "data" / "claims"


def main() -> int:
    sessions = json.loads((STREAMS / "_sessions.json").read_text(encoding="utf-8"))
    wanted = set(sys.argv[1:])
    if wanted:
        sessions = [s for s in sessions if s["session_id"] in wanted]

    JOBS.mkdir(parents=True, exist_ok=True)
    CLAIMS.mkdir(parents=True, exist_ok=True)
    created = 0
    for session in sessions:
        if not any(p["has_transcript"] for p in session["parts"]):
            continue
        note_path = STREAMS / session["filename"]
        existing = sorted(STREAMS.glob(f"{session['session_id']}_*.md"))
        if existing:
            note_path = existing[0]
        job = {
            "session_id": session["session_id"],
            "label": session["label"],
            "title": session["title"],
            "date_iso": session["date_iso"],
            "date_display": session["date"],
            "start_msk": session["start_msk"],
            "start_london": session["start_london"],
            "duration": " / ".join(p["duration"] for p in session["parts"]),
            "parts": session["parts"],
            "transcript": session["transcript"],
            "note_path": str(note_path.relative_to(PROJECT_ROOT)),
            "claims_path": str(
                (CLAIMS / f"{session['session_id']}.json").relative_to(PROJECT_ROOT)
            ),
            "has_full_transcript": all(p["has_transcript"] for p in session["parts"]),
        }
        (JOBS / f"{session['session_id']}.json").write_text(
            json.dumps(job, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        created += 1
    print(f"jobs written: {created} -> {JOBS.relative_to(PROJECT_ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
