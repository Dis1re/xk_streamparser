"""Download audio for every note marked as missing subtitles.

Files are stored in ``whisper_queue/`` and named by stream number and title,
so a Whisper worker on another machine can process them without extra metadata.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

APP_ROOT = Path(__file__).resolve().parents[1]
PROJECT_ROOT = APP_ROOT.parent
NOTES_DIR = PROJECT_ROOT / "streams"
QUEUE_DIR = APP_ROOT / "whisper_queue"
FORBIDDEN = re.compile(r'[<>:"/\\|?*\x00-\x1f]')


def slugify(title: str, limit: int = 70) -> str:
    slug = re.sub(r"№\s*\d+(?:\s*[ч4][12]?/2)?", "", title)
    slug = re.sub(r"(\d+)/(\d+)", r"\1-\2", slug)
    slug = FORBIDDEN.sub("", slug)
    slug = re.sub(r"[,!]+", " ", slug)
    slug = re.sub(r"\s+", "_", slug.strip())
    slug = re.sub(r"_+", "_", slug)
    slug = slug.strip("._")
    return slug[:limit].rstrip("._") or "stream"


def read_note(path: Path) -> dict[str, str] | None:
    text = path.read_text(encoding="utf-8")
    url = re.search(r"\*\*VOD:\*\*\s*(\S+)", text)
    heading = re.search(r"^#\s+(.+?)\s+—\s+«(.+?)»\s*$", text, re.M)
    if not url or not heading:
        return None
    number, title = heading.group(1).strip(), heading.group(2).strip()
    video_id = url.group(1).split("v=")[-1].split("&")[0]
    return {"number": number, "title": title, "id": video_id, "url": url.group(1)}


def collect() -> list[dict[str, str]]:
    items: list[dict[str, str]] = []
    for path in sorted(NOTES_DIR.glob("*_без_субтитров.md")):
        note = read_note(path)
        if note:
            note["note"] = path.name
            items.append(note)
    return items


def target_path(item: dict[str, str]) -> Path:
    return QUEUE_DIR / f"{item['number']}_{slugify(item['title'])}.m4a"


def download(item: dict[str, str], *, force: bool = False) -> Path:
    target = target_path(item)
    if target.exists() and not force:
        print(f"[skip] {target}")
        return target
    command = [
        sys.executable,
        "-m",
        "yt_dlp",
        "--no-warnings",
        "--retries",
        "10",
        "--fragment-retries",
        "10",
        "--socket-timeout",
        "30",
        "-f",
        "bestaudio[abr<=96]/bestaudio/best",
        "-x",
        "--audio-format",
        "m4a",
        "--postprocessor-args",
        "ffmpeg:-ac 1 -ar 16000 -b:a 64k",
        "-o",
        str(QUEUE_DIR / f"{item['number']}_%(id)s.%(ext)s.tmp"),
        item["url"],
    ]
    print(f"[download] {item['number']} {item['title']}", flush=True)
    subprocess.run(command, check=True)
    produced = list(QUEUE_DIR.glob(f"{item['number']}_{item['id']}*.m4a"))
    if not produced:
        raise SystemExit(f"no audio produced for {item['number']} ({item['id']})")
    produced[0].replace(target)
    for leftover in QUEUE_DIR.glob(f"{item['number']}_{item['id']}*"):
        leftover.unlink(missing_ok=True)
    return target


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")

    parser = argparse.ArgumentParser()
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--limit", type=int, default=0)
    args = parser.parse_args()

    QUEUE_DIR.mkdir(exist_ok=True)
    items = collect()
    if args.limit:
        items = items[: args.limit]
    manifest = []
    failures = []
    for item in items:
        target = target_path(item)
        if args.dry_run:
            print(f"{item['number']}\t{item['id']}\t{target}")
            continue
        try:
            target = download(item, force=args.force)
        except Exception as exc:  # keep the queue moving on a single bad video
            print(f"[error] {item['number']} {item['id']}: {exc}", file=sys.stderr)
            failures.append({**item, "error": str(exc)})
            continue
        manifest.append(
            {
                "number": item["number"],
                "title": item["title"],
                "video_id": item["id"],
                "url": item["url"],
                "audio": str(target),
            }
        )
        (QUEUE_DIR / "manifest.json").write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
        )
    if failures:
        (QUEUE_DIR / "failures.json").write_text(
            json.dumps(failures, ensure_ascii=False, indent=2), encoding="utf-8"
        )
    else:
        (QUEUE_DIR / "failures.json").unlink(missing_ok=True)


if __name__ == "__main__":
    main()
