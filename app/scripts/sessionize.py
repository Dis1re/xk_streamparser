"""Build stream sessions from the archived per-video notes plus real timestamps.

A session is a contiguous run of videos: a new session starts when the gap
between the end of the previous video and the start of the next one exceeds
three hours. This merges crashed/restarted streams, multipart uploads and
several numbered videos published during one long stream.

Dates:
- grouping is done on absolute UTC time, so timezone does not matter;
- the session date shown to readers is the Moscow date (GMT+3) of the first
  start, as requested.

Old notes are used ONLY as an index (label, video id, source, placeholder
flag). Their text is never read for content.

Writes streams/_sessions.json and app/data/_sessions/<id>/transcript.txt.
"""

from __future__ import annotations

import json
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path

from tz import to_london, to_moscow

APP_ROOT = Path(__file__).resolve().parents[1]
PROJECT_ROOT = APP_ROOT.parent
OLD_NOTES = PROJECT_ROOT / "archive" / "streams_v1"
OUT_NOTES = PROJECT_ROOT / "streams"
SESSIONS_DIR = APP_ROOT / "data" / "_sessions"
TIMES_FILE = APP_ROOT / "data" / "_times.json"

GAP = timedelta(hours=3)


def parse_note(path: Path) -> dict:
    text = path.read_text(encoding="utf-8")
    head = text[:4000]
    title = re.search(r"^#\s+(.+?)\s+—\s+«(.+?)»", head, re.M)
    date = re.search(r"\*\*Дата:\*\*\s*([0-9.]+)", head)
    duration = re.search(r"\*\*Длительность:\*\*\s*([0-9:]+)", head)
    vod = re.search(r"\*\*VOD:\*\*\s*(\S+)", head)
    source = re.search(r"\*\*Источник:\*\*\s*(.+)", head)
    name = path.stem
    m = re.match(r"bonus_(\d+)", name)
    if m:
        label = f"({int(m.group(1))})"
    else:
        m = re.match(r"(\d+)_(\d+)_", name)
        if m:
            label = f"{m.group(1)}/{m.group(2)}"
        else:
            m = re.match(r"(\d+)_", name)
            label = m.group(1) if m else name
    video_id = ""
    if vod:
        video_id = vod.group(1).split("v=")[-1].split("&")[0]
    if video_id in ("-", "—", "–", "none", "None"):
        video_id = ""
    return {
        "label": label,
        "title": title.group(2).strip() if title else path.stem,
        "date": date.group(1) if date else "—",
        "duration": duration.group(1) if duration else "—",
        "video_id": video_id,
        "source": source.group(1).strip() if source else "—",
        "old_path": str(path.relative_to(PROJECT_ROOT)),
        "is_placeholder": len(text) < 2000,
    }


def base_number(label: str) -> str | None:
    m = re.match(r"(\d+)(?:/\d+)?$", label)
    return m.group(1) if m else None


def group_label(items: list[dict]) -> str:
    labels = [x["label"] for x in items]
    numbers = [base_number(x) for x in labels]
    if all(numbers):
        unique = sorted({int(x) for x in numbers})
        if len(unique) == 1:
            return str(unique[0])
        return f"{unique[0]}–{unique[-1]}"
    stripped = [x.strip("()") for x in labels]
    if all(x.isdigit() for x in stripped):
        unique = sorted({int(x) for x in stripped})
        if len(unique) == 1:
            return f"({unique[0]})"
        return f"({unique[0]}–{unique[-1]})"
    if len(labels) == 1:
        return labels[0]
    return labels[0]


def slugify(text: str, limit: int = 60) -> str:
    text = re.sub(r"\(![^)]*\)", "", text)
    text = re.sub(r"№\s*\d+.*$", "", text)
    text = re.sub(r"[^\w\s-]", "", text, flags=re.UNICODE)
    text = re.sub(r"\s+", "_", text.strip())
    return text[:limit].rstrip("_") or "stream"


def parse_duration(value: str) -> int:
    if not value or value == "—":
        return 0
    parts = [int(x) for x in value.split(":")]
    return sum(int(x) * 60 ** (2 - i) for i, x in enumerate(parts))


def fmt_duration(seconds: int) -> str:
    return f"{seconds // 3600}:{seconds % 3600 // 60:02d}:{seconds % 60:02d}"


def start_of(item: dict) -> datetime:
    real = item.get("real") or {}
    stamp = real.get("release_timestamp") or real.get("timestamp")
    if stamp:
        return datetime.fromtimestamp(stamp, tz=timezone.utc)
    fallback = item["date"]
    if fallback and fallback != "—":
        day = datetime.strptime(fallback, "%d.%m.%Y").replace(tzinfo=timezone.utc)
        return day + timedelta(hours=18)
    return datetime(1970, 1, 1, tzinfo=timezone.utc)


def build_groups(items: list[dict]) -> list[list[dict]]:
    items = sorted(items, key=lambda x: x["start"])
    groups: list[list[dict]] = []
    current: list[dict] = []
    current_end: datetime | None = None
    for item in items:
        if current and current_end and item["start"] - current_end > GAP:
            groups.append(current)
            current = []
            current_end = None
        current.append(item)
        end = item["start"] + timedelta(seconds=item.get("seconds") or 0)
        current_end = max(current_end, end) if current_end else end
    if current:
        groups.append(current)
    return groups


def main() -> None:
    times = json.loads(TIMES_FILE.read_text(encoding="utf-8")) if TIMES_FILE.exists() else {}
    items: list[dict] = []
    for path in sorted(OLD_NOTES.glob("*.md")):
        if path.name in ("README.md", "_template.md"):
            continue
        note = parse_note(path)
        # Files like "104_отсутствует.md" mark gaps in the channel numbering.
        # They have no video and no date, so they are not sessions.
        if not note["video_id"] and note["date"] == "—":
            continue
        real = times.get(note["video_id"], {})
        note["real"] = real
        note["seconds"] = real.get("duration") or parse_duration(note["duration"])
        if note["seconds"] and note["duration"] == "—":
            note["duration"] = fmt_duration(note["seconds"])
        note["start"] = start_of(note)
        items.append(note)

    SESSIONS_DIR.mkdir(parents=True, exist_ok=True)
    sessions = []
    used_ids: set[str] = set()
    for group in build_groups(items):
        label = group_label(group)
        first = group[0]
        start_utc = first["start"]
        start_msk = to_moscow(start_utc)
        start_london = to_london(start_utc)
        sid = label.replace("–", "-").replace("(", "").replace(")", "")
        sid = re.sub(r"[^\w-]", "_", sid, flags=re.UNICODE)
        if label.startswith("("):
            sid = f"bonus_{sid}"
        candidate = sid
        suffix = 2
        while candidate in used_ids:
            candidate = f"{sid}_{suffix}"
            suffix += 1
        sid = candidate
        used_ids.add(sid)

        session_dir = SESSIONS_DIR / sid
        session_dir.mkdir(parents=True, exist_ok=True)
        transcript_lines = [
            f"# SESSION {label} | date={start_msk:%d.%m.%Y} | parts={len(group)}",
            f"# start_utc={start_utc.isoformat()} | start_london={start_london.isoformat()} | start_msk={start_msk.isoformat()}",
            "",
        ]
        offset = 0
        parts = []
        for index, item in enumerate(group, 1):
            transcript_lines.append(
                f"## PART {index}/{len(group)} | label={item['label']} | id={item['video_id']} "
                f"| duration={item['duration']} | offset={offset} | start_utc={item['start'].isoformat()}"
            )
            transcript_path = None
            if item["video_id"]:
                candidate_path = APP_ROOT / "data" / item["video_id"] / "auto_minutes.txt"
                if candidate_path.exists():
                    transcript_path = candidate_path
            if transcript_path:
                transcript_lines.append(transcript_path.read_text(encoding="utf-8").strip())
            else:
                transcript_lines.append("[NO TRANSCRIPT]")
            transcript_lines.append("")
            parts.append(
                {
                    "index": index,
                    "label": item["label"],
                    "video_id": item["video_id"],
                    "duration": item["duration"],
                    "start_utc": item["start"].isoformat(),
                    "start_msk": to_moscow(item["start"]).isoformat(),
                    "offset": offset,
                    "source": item["source"],
                    "old_path": item["old_path"],
                    "has_transcript": bool(transcript_path),
                    "placeholder": item["is_placeholder"],
                    "date_verified": item["video_id"] in times
                    and bool(
                        times[item["video_id"]].get("release_timestamp")
                        or times[item["video_id"]].get("timestamp")
                    ),
                }
            )
            offset += item["seconds"]

        merged = session_dir / "transcript.txt"
        merged.write_text("\n".join(transcript_lines), encoding="utf-8")
        title = first["title"]
        sessions.append(
            {
                "session_id": sid,
                "label": label,
                "date": start_msk.strftime("%d.%m.%Y"),
                "date_iso": start_msk.strftime("%Y-%m-%d"),
                "date_group_london": start_london.strftime("%Y-%m-%d"),
                "start_utc": start_utc.isoformat(),
                "start_london": start_london.isoformat(),
                "start_msk": start_msk.isoformat(),
                "date_verified": all(p["date_verified"] for p in parts),
                "title": title,
                "filename": f"{sid}_{slugify(title)}.md",
                "parts": parts,
                "transcript": str(merged.relative_to(PROJECT_ROOT)),
                "old_note": first["old_path"],
                "full_notes": sum(1 for x in group if not x["is_placeholder"]),
                "placeholders": sum(1 for x in group if x["is_placeholder"]),
            }
        )

    sessions.sort(key=lambda x: x["start_utc"])
    (OUT_NOTES / "_sessions.json").write_text(
        json.dumps(sessions, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"sessions: {len(sessions)}")
    print(f"parts: {sum(len(s['parts']) for s in sessions)}")
    print(f"full notes: {sum(s['full_notes'] for s in sessions)}")
    print(f"placeholders: {sum(s['placeholders'] for s in sessions)}")
    print(f"unverified dates: {sum(1 for s in sessions if not s['date_verified'])}")


if __name__ == "__main__":
    main()
