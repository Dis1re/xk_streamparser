"""Compare YouTube auto-captions with a Whisper transcript."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

import jiwer

from vtt import (
    Cue,
    bucket_by_window,
    cyrillic_ratio,
    dedupe_cues,
    format_timestamp,
    parse_vtt,
    to_text,
    word_count,
)


def load_whisper_jsonl(path: Path, offset: float = 0.0) -> list[Cue]:
    cues: list[Cue] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        cues.append(
            Cue(
                start=row["start"] + offset,
                end=row["end"] + offset,
                text=row["text"].strip(),
            )
        )
    return cues


def normalize(text: str) -> str:
    text = text.lower().replace("ё", "е")
    text = re.sub(r"\[[^\]]*\]|\([^)]*\)", " ", text)
    text = re.sub(r"[^\w\s]", " ", text, flags=re.UNICODE)
    return re.sub(r"\s+", " ", text).strip()


def punctuation_per_100(text: str) -> float:
    words = word_count(text)
    if not words:
        return 0.0
    marks = len(re.findall(r"[.,!?;:—…]", text))
    return 100 * marks / words


def uppercase_ratio(text: str) -> float:
    letters = [char for char in text if char.isalpha()]
    if not letters:
        return 0.0
    return sum(1 for char in letters if char.isupper()) / len(letters)


def repeated_ngram_ratio(text: str, n: int = 5) -> float:
    words = normalize(text).split()
    if len(words) < n:
        return 0.0
    grams = [tuple(words[i : i + n]) for i in range(len(words) - n + 1)]
    return 1 - len(set(grams)) / len(grams)


def stats(cues: list[Cue]) -> dict:
    text = to_text(cues)
    words = word_count(text)
    duration = (max(cue.end for cue in cues) - min(cue.start for cue in cues)) if cues else 0
    return {
        "words": words,
        "duration": duration,
        "words_per_min": (60 * words / duration) if duration else 0.0,
        "cyrillic_ratio": cyrillic_ratio(text),
        "punct_per_100": punctuation_per_100(text),
        "uppercase_ratio": uppercase_ratio(text),
        "repeated_5gram": repeated_ngram_ratio(text),
        "text": text,
    }


def fmt(value: float, digits: int = 2) -> str:
    return f"{value:.{digits}f}"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--auto", type=Path, help="YouTube .vtt file")
    parser.add_argument("--whisper", type=Path, required=True, help="Whisper .jsonl file")
    parser.add_argument("--whisper-offset", type=float, default=0.0, help="seconds added to Whisper times")
    parser.add_argument("--window", type=float, default=30.0)
    parser.add_argument("--out", type=Path)
    parser.add_argument("--reference", type=Path, help="plain-text reference for WER/CER")
    parser.add_argument("--max-windows", type=int)
    args = parser.parse_args()

    whisper = load_whisper_jsonl(args.whisper, args.whisper_offset)
    auto = dedupe_cues(parse_vtt(args.auto)) if args.auto else []
    if auto and whisper:
        start = min(cue.start for cue in whisper) - 1.0
        end = max(cue.end for cue in whisper) + 1.0
        auto = [cue for cue in auto if cue.end >= start and cue.start <= end]
    out_path = args.out or args.whisper.parent / "comparison.md"

    auto_stats = stats(auto) if auto else None
    whisper_stats = stats(whisper)

    auto_buckets = bucket_by_window(auto, args.window) if auto else {}
    whisper_buckets = bucket_by_window(whisper, args.window)

    rows = []
    for index in sorted(set(auto_buckets) | set(whisper_buckets)):
        if args.max_windows is not None and len(rows) >= args.max_windows:
            break
        start = index * args.window
        rows.append(
            (
                start,
                to_text(auto_buckets.get(index, [])),
                to_text(whisper_buckets.get(index, [])),
            )
        )

    lines = ["# ASR comparison", ""]
    lines += ["## Summary", "", "| metric | YouTube auto | Whisper |", "|---|---|---|"]
    if auto_stats:
        lines += [
            f"| words | {auto_stats['words']} | {whisper_stats['words']} |",
            f"| words / min | {fmt(auto_stats['words_per_min'], 1)} | {fmt(whisper_stats['words_per_min'], 1)} |",
            f"| cyrillic ratio | {fmt(auto_stats['cyrillic_ratio'])} | {fmt(whisper_stats['cyrillic_ratio'])} |",
            f"| punctuation / 100 words | {fmt(auto_stats['punct_per_100'])} | {fmt(whisper_stats['punct_per_100'])} |",
            f"| uppercase ratio | {fmt(auto_stats['uppercase_ratio'], 3)} | {fmt(whisper_stats['uppercase_ratio'], 3)} |",
            f"| repeated 5-grams | {fmt(auto_stats['repeated_5gram'], 3)} | {fmt(whisper_stats['repeated_5gram'], 3)} |",
        ]
    else:
        lines += [
            f"| words | — | {whisper_stats['words']} |",
            f"| words / min | — | {fmt(whisper_stats['words_per_min'], 1)} |",
            f"| cyrillic ratio | — | {fmt(whisper_stats['cyrillic_ratio'])} |",
            f"| punctuation / 100 words | — | {fmt(whisper_stats['punct_per_100'])} |",
            f"| uppercase ratio | — | {fmt(whisper_stats['uppercase_ratio'], 3)} |",
            f"| repeated 5-grams | — | {fmt(whisper_stats['repeated_5gram'], 3)} |",
        ]

    if auto:
        auto_norm = normalize(to_text(auto))
        whisper_norm = normalize(to_text(whisper))
        if auto_norm and whisper_norm:
            lines += [
                "",
                f"Disagreement (WER auto vs Whisper): **{fmt(jiwer.wer(auto_norm, whisper_norm), 3)}**",
                f"Disagreement (CER auto vs Whisper): **{fmt(jiwer.cer(auto_norm, whisper_norm), 3)}**",
                "",
                "> WER here is not accuracy: it only shows how much the two systems disagree.",
            ]

    if args.reference:
        reference = normalize(args.reference.read_text(encoding="utf-8"))
        lines += ["", "## WER / CER against reference", "", "| system | WER | CER |", "|---|---|---|"]
        for name, cues in (("auto", auto), ("whisper", whisper)):
            if not cues:
                continue
            hypothesis = normalize(to_text(cues))
            lines.append(
                f"| {name} | {fmt(jiwer.wer(reference, hypothesis), 3)} | "
                f"{fmt(jiwer.cer(reference, hypothesis), 3)} |"
            )

    lines += ["", "## Side by side", ""]
    for start, auto_text, whisper_text in rows:
        lines += [
            f"### {format_timestamp(start)} – {format_timestamp(start + args.window)}",
            "",
            f"**auto:** {auto_text or '—'}",
            "",
            f"**whisper:** {whisper_text or '—'}",
            "",
        ]

    out_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    if auto:
        out_path.with_suffix(".auto.txt").write_text(to_text(auto), encoding="utf-8")
    out_path.with_suffix(".whisper.txt").write_text(to_text(whisper), encoding="utf-8")

    print(f"wrote {out_path}")
    if auto_stats:
        print(
            f"auto: {auto_stats['words']} words, "
            f"{auto_stats['words_per_min']:.0f} wpm, "
            f"punct/100={auto_stats['punct_per_100']:.1f}, "
            f"repeat={auto_stats['repeated_5gram']:.3f}"
        )
    print(
        f"whisper: {whisper_stats['words']} words, "
        f"{whisper_stats['words_per_min']:.0f} wpm, "
        f"punct/100={whisper_stats['punct_per_100']:.1f}, "
        f"repeat={whisper_stats['repeated_5gram']:.3f}"
    )


if __name__ == "__main__":
    main()
