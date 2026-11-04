import json
import shutil
from pathlib import Path

APP = Path(__file__).resolve().parents[1]
PROJECT = APP.parent
sessions = json.loads((PROJECT / "streams" / "_sessions.json").read_text(encoding="utf-8"))
entry = next(s for s in sessions if s["session_id"] == "144")
print("144:", entry["date_iso"], [p["has_transcript"] for p in entry["parts"]], entry["duration"] if "duration" in entry else "")
print("transcript:", entry["transcript"])

backup = APP / "data" / "_audit_v2"
for sid in ("101", "bonus_69"):
    target = backup / sid
    target.mkdir(parents=True, exist_ok=True)
    note = next((PROJECT / "streams").glob(f"{sid}_*.md"))
    shutil.copy2(note, target / note.name)
    for name in (f"{sid}.json", f"{sid}_verdicts.json"):
        src = APP / "data" / "claims" / name
        if src.exists():
            shutil.copy2(src, target / name)
    print("backed up", sid)
