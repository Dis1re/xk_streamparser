"""Parsing and normalisation helpers for WebVTT subtitles.

YouTube auto-captions are "rolling": every cue usually repeats the tail of the
previous cue and appends a few new words.  ``parse_vtt`` keeps the raw cues,
``dedupe_cues`` removes the overlapping prefix and returns only new text.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Sequence

TIMESTAMP_RE = re.compile(r"(\d{1,2}):(\d{2}):(\d{2})[.,](\d{3})")
TAG_RE = re.compile(r"<[^>]*>")
ENTITY_RE = re.compile(r"&(amp|lt|gt|quot|#39|nbsp);")
ENTITY_MAP = {"amp": "&", "lt": "<", "gt": ">", "quot": '"', "#39": "'", "nbsp": " "}


@dataclass
class Cue:
    start: float
    end: float
    text: str
    source: str = ""

    @property
    def duration(self) -> float:
        return max(0.0, self.end - self.start)

    @property
    def is_noise(self) -> bool:
        stripped = self.text.strip()
        return bool(re.fullmatch(r"[\[(].*[\])]", stripped))


def parse_timestamp(value: str) -> float:
    match = TIMESTAMP_RE.search(value)
    if not match:
        raise ValueError(f"bad timestamp: {value!r}")
    hours, minutes, seconds, millis = (int(x) for x in match.groups())
    return hours * 3600 + minutes * 60 + seconds + millis / 1000


def format_timestamp(seconds: float, *, vtt: bool = False) -> str:
    seconds = max(0.0, seconds)
    hours, rest = divmod(int(seconds), 3600)
    minutes, secs = divmod(rest, 60)
    millis = int(round((seconds - int(seconds)) * 1000))
    if vtt:
        return f"{hours:02d}:{minutes:02d}:{secs:02d}.{millis:03d}"
    return f"{hours:02d}:{minutes:02d}:{secs:02d}"


def clean_text(text: str) -> str:
    text = TAG_RE.sub("", text)
    text = ENTITY_RE.sub(lambda m: ENTITY_MAP[m.group(1)], text)
    text = text.replace("\u200b", "")
    return re.sub(r"\s+", " ", text).strip()


def parse_vtt(path: str | Path) -> list[Cue]:
    raw = Path(path).read_text(encoding="utf-8-sig").replace("\r\n", "\n")
    cues: list[Cue] = []
    for block in re.split(r"\n\s*\n", raw):
        lines = block.strip("\n").split("\n")
        if not lines:
            continue
        time_index = next((i for i, line in enumerate(lines) if "-->" in line), None)
        if time_index is None:
            continue
        left, right = lines[time_index].split("-->", 1)
        try:
            start = parse_timestamp(left)
            end = parse_timestamp(right.strip().split()[0])
        except ValueError:
            continue
        text = clean_text(" ".join(lines[time_index + 1 :]))
        if text:
            cues.append(Cue(start=start, end=end, text=text))
    return cues


def _token_parts(text: str) -> tuple[list[str], list[str]]:
    tokens = text.split()
    normalised = [re.sub(r"^[^\w]+|[^\w]+$", "", token.lower()) for token in tokens]
    return normalised, tokens


def _overlap(previous: Sequence[str], current: Sequence[str]) -> int:
    limit = min(len(previous), len(current))
    for size in range(limit, 0, -1):
        if list(previous[-size:]) == list(current[:size]):
            return size
    return 0


def dedupe_cues(cues: Iterable[Cue]) -> list[Cue]:
    """Drop the part of each cue that repeats the previous cue."""
    result: list[Cue] = []
    previous: list[str] = []
    for cue in cues:
        normalised, tokens = _token_parts(cue.text)
        if not tokens:
            continue
        overlap = _overlap(previous, normalised)
        new_tokens = tokens[overlap:]
        if new_tokens:
            result.append(Cue(cue.start, cue.end, " ".join(new_tokens), cue.source))
        previous = normalised
    return result


def to_text(cues: Iterable[Cue], *, skip_noise: bool = True) -> str:
    parts = [
        cue.text
        for cue in cues
        if not (skip_noise and cue.is_noise)
    ]
    return " ".join(parts)


def bucket_by_window(cues: Iterable[Cue], window: float) -> dict[int, list[Cue]]:
    buckets: dict[int, list[Cue]] = {}
    for cue in cues:
        index = int(cue.start // window)
        buckets.setdefault(index, []).append(cue)
    return buckets


def word_count(text: str) -> int:
    return len(re.findall(r"\w+", text, flags=re.UNICODE))


def cyrillic_ratio(text: str) -> float:
    words = re.findall(r"\w+", text, flags=re.UNICODE)
    if not words:
        return 0.0
    cyrillic = sum(1 for word in words if re.search(r"[А-Яа-яЁё]", word))
    return cyrillic / len(words)
