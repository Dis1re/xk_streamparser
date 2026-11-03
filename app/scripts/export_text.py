"""Export a clean, timestamped transcript from WebVTT or Whisper JSONL."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from vtt import (
    Cue,
    bucket_by_window,
    dedupe_cues,
    format_timestamp,
    parse_vtt,
    to_text,
    word_count,
)


def parse_jsonl(path: Path, offset: float = 0.0) -> list[Cue]:
    cues: list[Cue] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        cues.append(
            Cue(
                start=float(row["start"]) + offset,
                end=float(row["end"]) + offset,
                text=row["text"].strip(),
            )
        )
    return cues


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("input", type=Path, help=".vtt or .jsonl")
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument(
        "--window",
        type=float,
        default=60,
        help="seconds per line; 0 = one line per cue",
    )
    parser.add_argument(
        "--offset",
        type=float,
        default=0,
        help="seconds added to timestamps (JSONL only)",
    )
    args = parser.parse_args()

    if args.input.suffix.lower() == ".jsonl":
        cues = parse_jsonl(args.input, args.offset)
    else:
        cues = dedupe_cues(parse_vtt(args.input))

    lines: list[str] = []
    if args.window <= 0:
        for cue in cues:
            if cue.is_noise:
                continue
            lines.append(f"[{format_timestamp(cue.start)}] {cue.text}")
    else:
        for index, bucket in sorted(bucket_by_window(cues, args.window).items()):
            text = to_text(bucket)
            if text:
                lines.append(f"[{format_timestamp(index * args.window)}] {text}")

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"wrote {args.out}: {len(lines)} lines, {word_count(' '.join(lines))} words")


if __name__ == "__main__":
    main()
