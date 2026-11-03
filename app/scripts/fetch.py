"""Download a YouTube VOD slice and its subtitles with yt-dlp."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

APP_ROOT = Path(__file__).resolve().parents[1]
PROJECT_ROOT = APP_ROOT.parent


def parse_offset(value: str) -> int:
    value = value.strip()
    if ":" in value:
        parts = [int(part) for part in value.split(":")]
        if len(parts) == 2:
            hours, minutes, seconds = 0, parts[0], parts[1]
        elif len(parts) == 3:
            hours, minutes, seconds = parts
        else:
            raise ValueError(f"bad time: {value!r}")
        return hours * 3600 + minutes * 60 + seconds
    if value.endswith("m"):
        return int(float(value[:-1]) * 60)
    if value.endswith("h"):
        return int(float(value[:-1]) * 3600)
    return int(float(value))


def format_offset(seconds: int) -> str:
    hours, rest = divmod(seconds, 3600)
    minutes, secs = divmod(rest, 60)
    return f"{hours:02d}:{minutes:02d}:{secs:02d}"


def format_label(seconds: int) -> str:
    hours, rest = divmod(seconds, 3600)
    minutes, secs = divmod(rest, 60)
    return f"{hours:02d}{minutes:02d}{secs:02d}"


def run(command: list[str], *, check: bool = True) -> subprocess.CompletedProcess:
    print("+ " + " ".join(command), flush=True)
    return subprocess.run(command, check=check, text=True)


def media_duration(path: Path) -> float:
    import av

    with av.open(str(path)) as container:
        if container.duration is None:
            return 0.0
        return float(container.duration / av.time_base)


def yt_dlp(*args: str) -> list[str]:
    return [sys.executable, "-m", "yt_dlp", *args]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("url")
    parser.add_argument("--start", default="0", help="HH:MM:SS, MM:SS or seconds")
    parser.add_argument("--duration", help="10m, 600, HH:MM:SS; omit for full audio")
    parser.add_argument("--out", type=Path, help="output root (default: data/<video-id>)")
    parser.add_argument("--proxy", help="e.g. http://127.0.0.1:7897")
    parser.add_argument("--cookies-from-browser", help="chrome, firefox, edge ...")
    parser.add_argument("--skip-subs", action="store_true")
    parser.add_argument("--skip-audio", action="store_true")
    parser.add_argument("--sub-langs", default="ru-orig,ru,en")
    parser.add_argument("--audio-quality", default="bestaudio[abr<=64]/bestaudio/best")
    parser.add_argument("--retries", default="10")
    parser.add_argument("--socket-timeout", default="30")
    args = parser.parse_args()

    common: list[str] = [
        "--no-warnings",
        "--retries",
        args.retries,
        "--fragment-retries",
        args.retries,
        "--socket-timeout",
        args.socket_timeout,
    ]
    if args.proxy:
        common += ["--proxy", args.proxy]
    if args.cookies_from_browser:
        common += ["--cookies-from-browser", args.cookies_from_browser]

    meta_cmd = yt_dlp(*common, "--dump-single-json", "--skip-download", args.url)
    result = subprocess.run(meta_cmd, check=True, capture_output=True, text=True, encoding="utf-8")
    info = json.loads(result.stdout)
    video_id = info["id"]
    duration = int(info.get("duration") or 0)

    out_dir = args.out or APP_ROOT / "data" / video_id
    subs_dir = out_dir / "subs"
    audio_dir = out_dir / "audio"
    subs_dir.mkdir(parents=True, exist_ok=True)
    audio_dir.mkdir(parents=True, exist_ok=True)

    meta = {
        "id": video_id,
        "title": info.get("title"),
        "channel": info.get("channel"),
        "channel_id": info.get("channel_id"),
        "duration": duration,
        "upload_date": info.get("upload_date"),
        "live_status": info.get("live_status"),
        "webpage_url": info.get("webpage_url"),
        "description": (info.get("description") or "")[:2000],
    }
    (out_dir / "meta.json").write_text(
        json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"video: {meta['title']} ({format_offset(duration)})")

    if not args.skip_subs:
        auto_cmd = yt_dlp(
            *common,
            "--skip-download",
            "--write-auto-subs",
            "--sub-langs",
            args.sub_langs,
            "--sub-format",
            "vtt",
            "-o",
            str(subs_dir / "%(id)s.%(ext)s"),
            args.url,
        )
        try:
            run(auto_cmd)
        except subprocess.CalledProcessError as exc:
            print(f"[warn] auto subtitles failed: {exc}", file=sys.stderr)

        manual_cmd = yt_dlp(
            *common,
            "--skip-download",
            "--write-subs",
            "--sub-langs",
            "ru,en",
            "--sub-format",
            "vtt",
            "-o",
            str(subs_dir / "%(id)s.%(ext)s"),
            args.url,
        )
        try:
            run(manual_cmd, check=True)
        except subprocess.CalledProcessError:
            print("[info] no manual subtitles", file=sys.stderr)

    if args.skip_audio:
        return

    start = parse_offset(args.start)
    if args.duration:
        requested = parse_offset(args.duration)
        section = f"*{format_offset(start)}-{format_offset(start + requested)}"
        label = format_label(start)
    else:
        requested = None
        section = None
        label = "full"

    expected = requested or duration or 0
    wav_path = audio_dir / f"{video_id}_{label}.wav"
    if wav_path.exists():
        actual = media_duration(wav_path)
        if expected and actual < expected - 2:
            print(
                f"[warn] existing file is incomplete ({actual:.1f}s of {expected}s), "
                "re-downloading",
                file=sys.stderr,
            )
            wav_path.unlink()
        else:
            print(f"[skip] exists: {wav_path}")
            return

    audio_cmd = yt_dlp(
        *common,
        "-f",
        args.audio_quality,
        "-x",
        "--audio-format",
        "wav",
        "--postprocessor-args",
        "ffmpeg:-ar 16000 -ac 1",
        "--http-chunk-size",
        "1M",
        "--downloader-args",
        "ffmpeg:-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5",
    )
    if section:
        audio_cmd += ["--download-sections", section]
    audio_cmd += [
        "-o",
        str(audio_dir / f"%(id)s_{label}.%(ext)s"),
        args.url,
    ]
    run(audio_cmd)

    if not wav_path.exists():
        candidates = list(audio_dir.glob(f"{video_id}_{label}.*"))
        raise SystemExit(f"expected {wav_path}, found: {candidates}")

    actual = media_duration(wav_path)
    if expected and actual < expected - 2:
        raise SystemExit(
            f"incomplete audio: {actual:.1f}s of {expected}s; file kept at {wav_path}"
        )

    print(f"\naudio: {wav_path}")
    print(f"subs:  {subs_dir}")


if __name__ == "__main__":
    main()
