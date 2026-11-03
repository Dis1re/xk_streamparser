"""Session inventory for planning the note rebuild."""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

APP_ROOT = Path(__file__).resolve().parents[1]
PROJECT_ROOT = APP_ROOT.parent
sessions = json.loads(
    (PROJECT_ROOT / "streams" / "_sessions.json").read_text(encoding="utf-8")
)

ready = [s for s in sessions if any(p["has_transcript"] for p in s["parts"])]
partial = [
    s
    for s in ready
    if not all(p["has_transcript"] for p in s["parts"])
]
no_transcript = [s for s in sessions if not any(p["has_transcript"] for p in s["parts"])]

print(f"sessions total: {len(sessions)}")
print(f"with transcript: {len(ready)}")
print(f"  partially: {len(partial)}")
print(f"without transcript: {len(no_transcript)}")

words = []
for session in ready:
    text = (PROJECT_ROOT / session["transcript"]).read_text(encoding="utf-8")
    words.append(len(text.split()))
print(f"total words: {sum(words):,}")
print(f"max words: {max(words):,}")
print(f"median words: {sorted(words)[len(words) // 2]:,}")

types = Counter()
for session in sessions:
    types[len(session["parts"])] += 1
print("parts distribution:", dict(sorted(types.items())))

if partial:
    print("partial transcript sessions:")
    for session in partial:
        print("  ", session["session_id"], [p["label"] for p in session["parts"] if not p["has_transcript"]])
