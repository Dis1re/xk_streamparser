"""Fetch real stream timestamps for every video in the session registry.

`upload_date` is a date without timezone and cannot be used to group sessions.
YouTube gives `release_timestamp` (when the stream started) and `timestamp`
(when it was published). Both are Unix UTC seconds.

Results are cached in app/data/_times.json so the network is hit only once.

Usage:
    python app/scripts/fetch_times.py
    python app/scripts/fetch_times.py --force
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

APP_ROOT = Path(__file__).resolve().parents[1]
PROJECT_ROOT = APP_ROOT.parent
SESSIONS_FILE = PROJECT_ROOT / "streams" / "_sessions.json"
CACHE_FILE = APP_ROOT / "data" / "_times.json"
PROXY = "http://127.0.0.1:7897"

PRINT_FIELDS = "|".join(
    [
        "%(id)s",
        "%(timestamp)s",
        "%(release_timestamp)s",
        "%(duration)s",
        "%(upload_date)s",
        "%(title)s",
    ]
)


def load_cache() -> dict:
    cache: dict[str, dict] = {}
    if CACHE_FILE.exists():
        cache = json.loads(CACHE_FILE.read_text(encoding="utf-8"))
    # Adopt timestamps that already sit in per-video meta.json.
    for meta_path in (APP_ROOT / "data").glob("*/meta.json"):
        try:
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            continue
        vid = meta.get("id")
        if not vid:
            continue
        if meta.get("timestamp") or meta.get("release_timestamp"):
            cache.setdefault(
                vid,
                {
                    "timestamp": meta.get("timestamp"),
                    "release_timestamp": meta.get("release_timestamp"),
                    "duration": meta.get("duration"),
                    "upload_date": meta.get("upload_date"),
                    "title": meta.get("title"),
                },
            )
    return cache


def write_meta(vid: str, info: dict) -> None:
    """Persist timestamps next to the downloaded subtitles, not only in cache."""
    meta_path = APP_ROOT / "data" / vid / "meta.json"
    if not meta_path.exists():
        return
    try:
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return
    changed = False
    for key in ("timestamp", "release_timestamp"):
        if meta.get(key) != info.get(key):
            meta[key] = info.get(key)
            changed = True
    if changed:
        meta_path.write_text(
            json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8"
        )


def video_ids() -> list[str]:
    sessions = json.loads(SESSIONS_FILE.read_text(encoding="utf-8"))
    ids: list[str] = []
    seen: set[str] = set()
    for session in sessions:
        for part in session["parts"]:
            vid = part.get("video_id")
            if vid and vid not in seen:
                seen.add(vid)
                ids.append(vid)
    return ids


def fetch(ids: list[str]) -> dict:
    urls = [f"https://www.youtube.com/watch?v={vid}" for vid in ids]
    if not urls:
        return {}
    command = [
        sys.executable,
        "-m",
        "yt_dlp",
        "--no-warnings",
        "--ignore-errors",
        "--skip-download",
        "--proxy",
        PROXY,
        "--print",
        PRINT_FIELDS,
        *urls,
    ]
    completed = subprocess.run(
        command, capture_output=True, text=True, encoding="utf-8", errors="replace"
    )
    result: dict[str, dict] = {}
    for line in completed.stdout.splitlines():
        pieces = line.split("|")
        if len(pieces) < 6 or not pieces[0]:
            continue
        vid = pieces[0]
        try:
            result[vid] = {
                "timestamp": int(pieces[1]) if pieces[1] not in ("NA", "") else None,
                "release_timestamp": int(pieces[2]) if pieces[2] not in ("NA", "") else None,
                "duration": int(float(pieces[3])) if pieces[3] not in ("NA", "") else None,
                "upload_date": pieces[4],
                "title": "|".join(pieces[5:]),
            }
        except ValueError:
            continue
    if completed.returncode != 0:
        print("yt-dlp stderr:", completed.stderr.strip()[:2000], file=sys.stderr)
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()

    cache = {} if args.force else load_cache()
    ids = [vid for vid in video_ids() if vid not in cache]
    print(f"videos: {len(video_ids())}, cached: {len(cache)}, to fetch: {len(ids)}")
    if ids:
        fetched: dict[str, dict] = {}
        for start in range(0, len(ids), 25):
            batch = ids[start : start + 25]
            part = fetch(batch)
            fetched.update(part)
            cache.update(part)
            CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
            CACHE_FILE.write_text(
                json.dumps(cache, ensure_ascii=False, indent=2, sort_keys=True),
                encoding="utf-8",
            )
            for vid, info in part.items():
                write_meta(vid, info)
            print(f"fetched {len(fetched)}/{len(ids)}")
        print(f"fetched total: {len(fetched)}")
    missing = [vid for vid in video_ids() if vid not in cache]
    print(f"missing: {len(missing)}")
    for vid in missing[:20]:
        print("  ", vid)
    return 0


if __name__ == "__main__":
    sys.exit(main())
