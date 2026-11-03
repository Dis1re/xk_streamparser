"""Bring all timestamps in a note and its claims file to HH:MM:SS.

Accepts the legacy hybrid form (HH:MM for times under an hour, HH:MM:SS above)
and rewrites it to a single unambiguous format.

Usage:
    python app/scripts/normalize_times.py 186
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

APP_ROOT = Path(__file__).resolve().parents[1]
PROJECT_ROOT = APP_ROOT.parent
STREAMS_DIR = PROJECT_ROOT / "streams"
CLAIMS_DIR = APP_ROOT / "data" / "claims"

SHORT_RE = re.compile(r"\[(\d{4}-\d{2}-\d{2}\s*·\s*[^\]]+?)\s+(\d{1,2}:\d{2})\]")
LONG_RE = re.compile(r"\[(\d{4}-\d{2}-\d{2}\s*·\s*[^\]]+?)\s+(\d{1,2}:\d{2}:\d{2})\]")
BOLD_RE = re.compile(r"\*\*(\d{1,2}:\d{2})\*\*")


def to_hms(value: str) -> str:
    parts = [int(x) for x in value.split(":")]
    if len(parts) == 2:
        hours, minutes = parts
        return f"{hours:02d}:{minutes:02d}:00"
    hours, minutes, seconds = parts
    return f"{hours:02d}:{minutes:02d}:{seconds:02d}"


def fix_note(text: str) -> tuple[str, int]:
    count = 0

    def long_sub(match: re.Match[str]) -> str:
        nonlocal count
        count += 1
        return f"[{match.group(1)} {to_hms(match.group(2))}]"

    def short_sub(match: re.Match[str]) -> str:
        nonlocal count
        count += 1
        return f"[{match.group(1)} {to_hms(match.group(2))}]"

    text = LONG_RE.sub(long_sub, text)
    text = SHORT_RE.sub(short_sub, text)

    def bold_sub(match: re.Match[str]) -> str:
        nonlocal count
        count += 1
        return f"**{to_hms(match.group(1))}**"

    text = BOLD_RE.sub(bold_sub, text)
    return text, count


def main() -> int:
    if len(sys.argv) != 2:
        print("usage: normalize_times.py <session_id>")
        return 2
    session_id = sys.argv[1]

    notes = sorted(STREAMS_DIR.glob(f"{session_id}_*.md"))
    if not notes:
        print(f"note not found for {session_id}")
        return 1
    note_path = notes[0]
    text, count = fix_note(note_path.read_text(encoding="utf-8"))
    note_path.write_text(text, encoding="utf-8")
    print(f"{note_path.name}: {count} citations normalized")

    claims_path = CLAIMS_DIR / f"{session_id}.json"
    if claims_path.exists():
        claims = json.loads(claims_path.read_text(encoding="utf-8"))
        for claim in claims:
            if claim.get("time"):
                claim["time"] = to_hms(claim["time"])
        claims_path.write_text(
            json.dumps(claims, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        print(f"{claims_path.name}: {len(claims)} claims normalized")
    return 0


if __name__ == "__main__":
    sys.exit(main())
