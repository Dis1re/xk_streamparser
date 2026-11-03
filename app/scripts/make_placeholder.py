"""Create a placeholder note for a missing stream or a stream without subtitles."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path


APP_ROOT = Path(__file__).resolve().parents[1]
PROJECT_ROOT = APP_ROOT.parent


def format_duration(seconds: int) -> str:
    hours, rest = divmod(int(seconds), 3600)
    minutes, secs = divmod(rest, 60)
    return f"{hours}:{minutes:02d}:{secs:02d}"


def clean_title(title: str) -> str:
    return re.sub(r"\s*\(![^)]*\)\s*$", "", title).strip()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--number", required=True)
    parser.add_argument("--display", default=None, help="label used in the heading")
    parser.add_argument("--status", choices=["no_subs", "missing"], required=True)
    parser.add_argument("--meta", type=Path)
    parser.add_argument("--title", default=None)
    parser.add_argument("--reason", default=None)
    parser.add_argument("--extra-note", default=None)
    parser.add_argument("--notes-dir", type=Path, default=PROJECT_ROOT / "streams")
    args = parser.parse_args()

    title = "Неизвестный выпуск"
    url = "—"
    date = "—"
    duration = "—"
    if args.meta:
        data = json.loads(args.meta.read_text(encoding="utf-8"))
        title = clean_title(data.get("title") or title)
        url = data.get("webpage_url") or url
        upload = data.get("upload_date") or ""
        if len(upload) == 8:
            date = f"{upload[6:8]}.{upload[4:6]}.{upload[0:4]}"
        if data.get("duration"):
            duration = format_duration(data["duration"])
    if args.title:
        title = args.title

    if args.status == "no_subs":
        filename = f"{args.number}_без_субтитров.md"
        status = "без auto-субтитров"
        body = (
            "У видео нет auto-субтитров (`ru-orig`, `ru`, `en`). По текущему правилу "
            "Whisper не запускаем — стрим пропущен.\n\n"
            "Чтобы сделать заметку, нужно скачать аудио и распознать его локально "
            "через Whisper, как это делали для #179 и #183."
        )
    else:
        filename = f"{args.number}_отсутствует.md"
        status = "отсутствует"
        body = args.reason or (
            f"Выпуск с номером {args.number} отсутствует в нумерации канала: "
            "видео с этим номером не найдено. Возможно, стрим не состоялся "
            "или был удалён."
        )

    lines = [
        f"# {args.display or args.number} — «{title}»",
        "",
        f"**VOD:** {url}  ",
        f"**Дата:** {date}  ",
        f"**Длительность:** {duration}  ",
        "**Канал:** xk  ",
        "**Источник:** —  ",
        f"**Статус:** {status}",
        "",
        body,
    ]
    if args.extra_note:
        lines += ["", args.extra_note]
    lines.append("")

    path = args.notes_dir / filename
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")
    print(path)


if __name__ == "__main__":
    main()
