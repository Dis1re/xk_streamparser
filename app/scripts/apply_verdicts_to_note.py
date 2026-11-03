"""Apply verifier corrections to a note automatically.

Bullets and claims are matched by the citation timestamp, not by position:
the extractor does not always keep the note and the claims in the same order.
For every `corrected` verdict the descriptive text of the bullet is replaced by
the verifier's formulation; the bold time and the citation stay untouched.

Usage:
    python app/scripts/apply_verdicts_to_note.py 186 --dry-run
    python app/scripts/apply_verdicts_to_note.py 186
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

APP_ROOT = Path(__file__).resolve().parents[1]
PROJECT_ROOT = APP_ROOT.parent
STREAMS = PROJECT_ROOT / "streams"
CLAIMS = APP_ROOT / "data" / "claims"

BULLET_RE = re.compile(
    r"^(?P<prefix>\s*(?:[-*]|\d+\.)\s+(?:\*\*(?P<time>\d{1,2}:\d{2}(?::\d{2})?)\*\*\s+—\s+)?)"
    r"(?P<text>.*?)"
    r"(?P<cite>\s*`\[\d{4}-\d{2}-\d{2}\s*·[^\]]+?\]`)\s*$"
)
CITE_TIME_RE = re.compile(r"\s(\d{1,2}):(\d{2}):(\d{2})\]")


def parse_hms(value: str) -> int:
    parts = [int(x) for x in value.split(":")]
    if len(parts) == 2:
        return parts[0] * 3600 + parts[1] * 60
    return parts[0] * 3600 + parts[1] * 60 + parts[2]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("session_id")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    sid = args.session_id
    notes = sorted(STREAMS.glob(f"{sid}_*.md"))
    if not notes:
        print(f"note not found: {sid}")
        return 1
    note_path = notes[0]
    verdicts_path = CLAIMS / f"{sid}_verdicts.json"
    if not verdicts_path.exists():
        print(f"verdicts not found: {verdicts_path.name}")
        return 1

    verdicts = json.loads(verdicts_path.read_text(encoding="utf-8"))
    claims = json.loads((CLAIMS / f"{sid}.json").read_text(encoding="utf-8"))
    verdict_by_id = {v["id"]: v for v in verdicts}

    lines = note_path.read_text(encoding="utf-8").splitlines()
    bullets = []
    section = ""
    for i, line in enumerate(lines):
        if line.startswith("## "):
            section = line[3:].strip()
        match = BULLET_RE.match(line)
        if not match:
            continue
        cite_time = CITE_TIME_RE.search(match.group("cite"))
        seconds = (
            int(cite_time.group(1)) * 3600
            + int(cite_time.group(2)) * 60
            + int(cite_time.group(3))
            if cite_time
            else None
        )
        bullets.append({"index": i, "match": match, "section": section, "seconds": seconds})

    if len(bullets) != len(claims):
        print(f"count mismatch: bullets {len(bullets)} != claims {len(claims)}")
        return 2

    # Match bullets to claims by timestamp. Duplicates are matched in order.
    by_time: dict[int, list[dict]] = {}
    for claim in claims:
        by_time.setdefault(parse_hms(claim["time"]), []).append(claim)

    used: set[str] = set()
    pairs: list[tuple[dict, dict]] = []
    unresolved = []
    for bullet in bullets:
        seconds = bullet["seconds"]
        claim = None
        for candidate in by_time.get(seconds, []):
            if candidate["id"] not in used:
                claim = candidate
                break
        if claim is None:
            # Allow a one-minute rounding difference.
            for shift in (-60, 60):
                for candidate in by_time.get((seconds or 0) + shift, []):
                    if candidate["id"] not in used:
                        claim = candidate
                        break
                if claim:
                    break
        if claim is None:
            unresolved.append(bullet)
            continue
        used.add(claim["id"])
        pairs.append((bullet, claim))

    if unresolved:
        print(f"could not match {len(unresolved)} bullets to claims by time, refusing to edit")
        for bullet in unresolved[:5]:
            print("  ", bullet["match"].group("cite"))
        return 3

    changed = 0
    skipped_quotes = 0
    for bullet, claim in pairs:
        verdict = verdict_by_id.get(claim["id"])
        if not verdict or verdict["verdict"] != "corrected":
            continue
        if not verdict.get("corrected_claim"):
            continue
        if bullet["section"] == "Цитаты":
            skipped_quotes += 1
            continue
        new_text = verdict["corrected_claim"].strip()
        match = bullet["match"]
        if new_text == match.group("text").strip():
            continue
        lines[bullet["index"]] = match.group("prefix") + new_text + match.group("cite")
        changed += 1

    if skipped_quotes:
        print(f"manual review needed: {skipped_quotes} corrected quotes")

    if args.dry_run:
        print(f"{note_path.name}: would change {changed} bullets")
        return 0

    note_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"{note_path.name}: changed {changed} bullets")
    return 0


if __name__ == "__main__":
    sys.exit(main())
