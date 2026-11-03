# app/ — пайплайн

Скрипты и данные, которые превращают стримы в проверенные заметки и базу знаний.

## Структура

```text
app/
├── scripts/   # сессионизация, проверки, обслуживание
├── prompts/   # инструкции для извлечения и проверки
├── data/      # транскрипты, задания, доказательства, кеш времени
└── .venv/     # окружение Python
```

## Полный цикл

1. **Сессионизация.** `sessionize.py` склеивает части с разрывом меньше трёх
   часов, собирает `streams/_sessions.json` и транскрипты в
   `data/_sessions/<id>/transcript.txt`.
2. **Реальные даты.** `fetch_times.py` забирает даты старта через `yt-dlp` и
   складывает в `data/_times.json`.
3. **Задания.** `make_jobs.py` пишет `data/jobs/<id>.json`; `next_batch.py`
   показывает очередь.
4. **Извлечение.** Агент по `prompts/extract_notes.md` читает полный транскрипт
   и пишет заметку и `data/claims/<id>.json`.
5. **Проверка.** Другой агент по `prompts/verify_notes.md` независимо проверяет
   каждый пункт и пишет `<id>_verdicts.json`.
6. **Применение правок.** `apply_verdicts.py` обновляет доказательства,
   `apply_verdicts_to_note.py` — текст заметки (сопоставление по времени
   ссылки, а не по порядку).
7. **Финальная сверка.** `finalize_session.py` и `check_notes.py`.
8. **База знаний.** `aggregate_claims.py` собирает `data/claims_all.jsonl`,
   `check_knowledge.py` сверяет ссылки в `notes/`.

## Команды

```bash
python scripts/sessionize.py
python scripts/fetch_times.py
python scripts/make_jobs.py
python scripts/next_batch.py 15
python scripts/finalize_session.py 151
python scripts/check_all.py
python scripts/aggregate_claims.py
python scripts/check_knowledge.py
python scripts/session_usage.py <session_id>
```

## Данные

- `data/_sessions/<id>/transcript.txt` — склеенный транскрипт с `## PART`;
- `data/claims/<id>.json` — тезисы с цитатами, временем, scope и условиями;
- `data/claims/<id>_verdicts.json` — вердикты проверяющего;
- `data/claims_all.jsonl` — общая база проверенных тезисов;
- `data/jobs/<id>.json` — задание на сессию;
- `data/_times.json` — кеш реальных дат старта.

Старые папки с `video_id` — наследие первой версии, пайплайном не используются.

## Требования

- Python 3.12 и `.venv`;
- `yt-dlp` для субтитров и метаданных;
- `faster-whisper` для сессий без субтитров;
- прокси для YouTube (в этом окружении — `127.0.0.1:7897`).

## Правила

- сессия — части с разрывом меньше трёх часов; дата — первый старт по Москве;
- каждый тезис подтверждается дословной цитатой из полного транскрипта;
- цитаты не «причёсываются»: опечатки автосубтитров сохраняются;
- имена восстанавливаются только при однозначном оригинале;
- проверка независимая: проверяющий не видит, как писались заметки.
