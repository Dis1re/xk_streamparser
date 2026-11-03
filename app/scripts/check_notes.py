"""Deterministic validation of session notes.

Checks every citation against the session registry, the merged transcript and
the claims evidence file. No LLM involved: only string and time arithmetic.

Usage:
    python app/scripts/check_notes.py 186
    python app/scripts/check_notes.py --all
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime
from pathlib import Path

APP_ROOT = Path(__file__).resolve().parents[1]
PROJECT_ROOT = APP_ROOT.parent
STREAMS_DIR = PROJECT_ROOT / "streams"
CLAIMS_DIR = APP_ROOT / "data" / "claims"
SESSIONS_FILE = STREAMS_DIR / "_sessions.json"

CITATION_RE = re.compile(r"\[(\d{4}-\d{2}-\d{2})\s*·\s*([^\]]+?)\]")
TRANSCRIPT_TS_RE = re.compile(r"^\[(\d{2}):(\d{2}):(\d{2})\]", re.M)
BULLET_RE = re.compile(r"^\s*[-*]\s+", re.M)

# Tolerance when matching a claim to a transcript timestamp, seconds.
TIME_TOLERANCE = 120


def parse_hms(value: str) -> int:
    parts = [int(x) for x in value.split(":")]
    if len(parts) == 3:
        return parts[0] * 3600 + parts[1] * 60 + parts[2]
    raise ValueError(f"time must be HH:MM:SS, got {value!r}")


def parse_duration(value: str) -> int:
    if not value or value == "—":
        return 0
    return sum(int(x) * 60 ** (2 - i) for i, x in enumerate(value.split(":")))


def iso_date(value: str) -> str:
    return datetime.strptime(value, "%d.%m.%Y").strftime("%Y-%m-%d")


def normalize(text: str) -> str:
    text = text.lower().replace("ё", "е")
    text = re.sub(r"[^\w\s]", " ", text)
    return re.sub(r"\s+", " ", text).strip()


class Transcript:
    def __init__(self, path: Path):
        self.text = path.read_text(encoding="utf-8")
        # Blank out markers without changing offsets: otherwise the digits of
        # `[01:02:00]` sit between two halves of a sentence and break matching
        # for any quote that crosses a minute boundary.
        self.clean = re.sub(
            r"\[\d{2}:\d{2}:\d{2}\]|^## PART [^\n]*$",
            lambda m: " " * len(m.group(0)),
            self.text,
            flags=re.M,
        )
        chars: list[str] = []
        mapping: list[int] = []
        previous_space = True
        for index, char in enumerate(self.clean):
            low = char.lower().replace("ё", "е")
            if low.isalnum() or low == "_":
                chars.append(low)
                mapping.append(index)
                previous_space = False
            elif not previous_space:
                chars.append(" ")
                mapping.append(index)
                previous_space = True
        self.normalized = "".join(chars).strip()
        self.mapping = mapping[: len(self.normalized)]
        self.parts: dict[int, list[int]] = {}
        self.offsets: dict[int, int] = {}
        current = 0
        for match in re.finditer(
            r"^## PART (\d+)/\d+[^\n]*duration=([0-9:]+)",
            self.text,
            re.M,
        ):
            current = int(match.group(1))
            self.parts[current] = []
            self.offsets[current] = match.start()
        for match in TRANSCRIPT_TS_RE.finditer(self.text):
            stamp = (
                int(match.group(1)) * 3600
                + int(match.group(2)) * 60
                + int(match.group(3))
            )
            part = 0
            for number, offset in self.offsets.items():
                if offset < match.start():
                    part = number
            if part:
                self.parts[part].append(stamp)

    def has_stamp(self, part: int, seconds: int, tolerance: int = TIME_TOLERANCE) -> bool:
        stamps = self.parts.get(part, [])
        return any(abs(s - seconds) <= tolerance for s in stamps)

    def find_quote(self, quote: str) -> int | None:
        """Return index of the quote in the normalized text, if present."""
        target = normalize(quote)
        if len(target) < 12:
            return None
        index = self.normalized.find(target)
        return index if index >= 0 else None

    def quote_time(self, quote: str) -> tuple[int, int] | None:
        index = self.find_quote(quote)
        if index is None:
            return None
        raw_index = self.mapping[index]
        part = 0
        for number, offset in sorted(self.offsets.items(), key=lambda x: x[1]):
            if offset < raw_index:
                part = number
        before = list(TRANSCRIPT_TS_RE.finditer(self.text, 0, raw_index))
        if not before:
            return None
        last = before[-1]
        seconds = (
            int(last.group(1)) * 3600 + int(last.group(2)) * 60 + int(last.group(3))
        )
        return part, seconds


def _check_session(session: dict) -> dict:
    label = session["label"]
    matches = sorted(STREAMS_DIR.glob(f"{session['session_id']}_*.md"))
    note_path = matches[0] if matches else STREAMS_DIR / session["filename"]
    result = {
        "session": label,
        "note": str(note_path.relative_to(PROJECT_ROOT)),
        "errors": [],
        "warnings": [],
        "citations": 0,
        "claims": 0,
    }

    if not matches:
        result["errors"].append(f"note missing for session {session['session_id']}")
        return result

    note = note_path.read_text(encoding="utf-8")
    transcript_path = PROJECT_ROOT / session["transcript"]
    if not transcript_path.exists():
        result["errors"].append(f"transcript missing: {session['transcript']}")
        return result
    transcript = Transcript(transcript_path)

    expected_date = iso_date(session["date"])
    part_count = len(session["parts"])
    part_durations = {
        p["index"]: parse_duration(p["duration"]) for p in session["parts"]
    }

    header_date = re.search(r"\*\*Дата:\*\*\s*([0-9.]+)", note)
    if not header_date:
        result["errors"].append("header: no date")
    elif iso_date(header_date.group(1)) != expected_date:
        result["errors"].append(
            f"header date {header_date.group(1)} != session date {session['date']}"
        )

    bullets = 0
    for line in note.splitlines():
        stripped = line.strip()
        if re.match(r"^(?:[-*]|\d+\.)\s+", stripped) and CITATION_RE.search(stripped):
            bullets += 1

    citations = CITATION_RE.findall(note)
    result["citations"] = len(citations)
    if not citations:
        result["errors"].append("no citations found")

    for date, payload in citations:
        pieces = payload.split()
        if not pieces:
            result["errors"].append(f"empty citation: [{date} · {payload}]")
            continue
        part = 1
        time_token = pieces[-1]
        if len(pieces) >= 2 and re.fullmatch(r"P\d+", pieces[-2]):
            part = int(pieces[-2][1:])
        label_text = " ".join(pieces[:-2] if re.fullmatch(r"P\d+", pieces[-2]) else pieces[:-1])

        if date != expected_date:
            result["errors"].append(
                f"citation date {date} != {expected_date} in [{date} · {payload}]"
            )
        if label_text.strip() != label:
            result["warnings"].append(
                f"citation label '{label_text}' != '{label}'"
            )
        if part < 1 or part > part_count:
            result["errors"].append(f"citation part P{part} out of range in [{date} · {payload}]")
            continue
        try:
            seconds = parse_hms(time_token)
        except ValueError:
            result["errors"].append(f"bad time '{time_token}' in [{date} · {payload}]")
            continue
        duration = part_durations.get(part, 0)
        if duration and seconds > duration:
            result["errors"].append(
                f"time {time_token} exceeds part {part} duration {session['parts'][part - 1]['duration']}"
            )
        elif not transcript.has_stamp(part, seconds):
            result["errors"].append(
                f"time {time_token} has no transcript line ±{TIME_TOLERANCE}s (P{part})"
            )

    claims_path = CLAIMS_DIR / f"{session['session_id']}.json"
    if not claims_path.exists():
        result["warnings"].append(f"claims file missing: {claims_path.name}")
    else:
        try:
            claims = json.loads(claims_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            result["errors"].append(f"claims json invalid: {exc}")
            claims = []
        result["claims"] = len(claims)
        if len(claims) != bullets:
            result["warnings"].append(
                f"claims {len(claims)} != bullets {bullets}"
            )
        seen = set()
        for claim in claims:
            cid = claim.get("id", "?")
            time_token = claim.get("time", "")
            part = int(claim.get("part", 1))
            try:
                seconds = parse_hms(time_token)
            except ValueError:
                result["errors"].append(f"{cid}: bad time '{time_token}'")
                continue
            quote = claim.get("quote", "")
            found = transcript.quote_time(quote)
            if not found:
                result["errors"].append(f"{cid}: quote not found in transcript")
                continue
            q_part, q_seconds = found
            if q_part != part:
                result["warnings"].append(
                    f"{cid}: quote is in P{q_part}, claim says P{part}"
                )
            if abs(q_seconds - seconds) > TIME_TOLERANCE:
                result["errors"].append(
                    f"{cid}: quote at {q_seconds // 3600:02d}:{q_seconds % 3600 // 60:02d}:{q_seconds % 60:02d}"
                    f" vs claim {time_token}"
                )
            key = normalize(claim.get("claim", ""))
            if key and key in seen:
                result["warnings"].append(f"{cid}: duplicate claim text")
            seen.add(key)

    return result


def check_session(session: dict, verbose: bool = True) -> dict:
    result = _check_session(session)
    if not verbose:
        return result
    status = "OK" if not result["errors"] else "FAIL"
    print(
        f"{status} {result['session']}: {result['citations']} citations, "
        f"{result['claims']} claims, {len(result['errors'])} errors, "
        f"{len(result['warnings'])} warnings"
    )
    for error in result["errors"]:
        print(f"  ERROR {error}")
    for warning in result["warnings"]:
        print(f"  WARN  {warning}")
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("session", nargs="?")
    parser.add_argument("--all", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    sessions = json.loads(SESSIONS_FILE.read_text(encoding="utf-8"))
    if args.all:
        targets = sessions
    elif args.session:
        targets = [s for s in sessions if s["session_id"] == args.session or s["label"] == args.session]
    else:
        parser.error("pass a session id or --all")

    reports = [check_session(s, verbose=not args.json) for s in targets]
    if args.json:
        print(json.dumps(reports, ensure_ascii=False, indent=2))
    failed = sum(1 for r in reports if r["errors"])
    print(f"\nchecked {len(reports)}, failed {failed}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
