"""Print speech-density windows from a subtitle file to choose test excerpts."""

from __future__ import annotations

import argparse
from pathlib import Path

from vtt import (
    bucket_by_window,
    cyrillic_ratio,
    dedupe_cues,
    format_timestamp,
    parse_vtt,
    to_text,
    word_count,
)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("vtt", type=Path)
    parser.add_argument("--window", type=float, default=300, help="seconds per window")
    parser.add_argument("--top", type=int, default=12)
    args = parser.parse_args()

    cues = parse_vtt(args.vtt)
    clean = dedupe_cues(cues)
    buckets = bucket_by_window(clean, args.window)

    rows = []
    for index, bucket in buckets.items():
        text = to_text(bucket)
        words = word_count(text)
        rows.append(
            (
                index * args.window,
                words,
                cyrillic_ratio(text),
                text,
            )
        )

    print(f"cues={len(cues)} clean_cues={len(clean)} windows={len(rows)}")
    print(f"\nTop {args.top} by word count:")
    for start, words, cyr, text in sorted(rows, key=lambda row: row[1], reverse=True)[: args.top]:
        print(
            f"{format_timestamp(start)}  words={words:4d}  ru={cyr:0.2f}  "
            f"{text[:180]}"
        )


if __name__ == "__main__":
    main()
