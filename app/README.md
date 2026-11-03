# xk_streamparser / app

Приложение для скачивания стримов, субтитров, Whisper-расшифровки и сравнения
ASR. Все команды ниже выполняются **из этой папки** (`app`).

## Почему не YouTube Data API v3

Data API даёт метаданные и список дорожек субтитров, но **не отдаёт видео и
чужие субтитры**. `captions.download` работает только для видео, которыми
владеет аккаунт. Поэтому для исследования используется `yt-dlp`.

## Установка

```powershell
uv sync --python 3.12 --extra cuda
```

`--extra cuda` нужен для NVIDIA GPU: ставит cuBLAS/cuDNN, которые CTranslate2
не находит сам на Windows. Без GPU используйте просто `uv sync --python 3.12`.
`ffmpeg` должен быть в PATH. Модели Whisper лежат в `models/` и в git не попадают.

## Быстрый тест

1. Скачать 5 минут аудио (16 кГц, моно) и auto-субтитры:

```powershell
.\.venv\Scripts\python.exe scripts\fetch.py `
  "https://www.youtube.com/watch?v=ggs0f0xxFXI" `
  --start 01:30:00 --duration 5m
```

2. Распознать кусок через Whisper:

```powershell
.\.venv\Scripts\python.exe scripts\transcribe.py `
  "data\ggs0f0xxFXI\audio\ggs0f0xxFXI_013000.wav" `
  --model models\large-v3-turbo-local `
  --device cuda --compute-type int8_float16 `
  --condition-on-previous-text `
  --initial-prompt "Стрим xk. Обсуждаем ИИ, ИИшку, искусственный интеллект, нейрослоп, геймдев, Steam, GTA, Unreal Engine, Unity, геймдизайн, дофамин, анонс, билд, релиз."
```

3. Сравнить с auto-субтитрами:

```powershell
.\.venv\Scripts\python.exe scripts\compare.py `
  --auto "data\ggs0f0xxFXI\subs\ggs0f0xxFXI.ru-orig.vtt" `
  --whisper "data\ggs0f0xxFXI\audio\whisper\ggs0f0xxFXI_013000.jsonl" `
  --whisper-offset 5400 `
  --window 30 `
  --out "data\ggs0f0xxFXI\comparison_013000.md"
```

`--whisper-offset` — начало куска в секундах, потому что Whisper нумерует время
от начала файла, а субтитры YouTube — от начала стрима.

## Что внутри

- `scripts/fetch.py` — метаданные, auto/manual субтитры, аудио-отрезок.
- `scripts/vtt.py` — парсер WebVTT и удаление «бегущих» повторов YouTube.
- `scripts/analyze_subs.py` — ищет в субтитрах участки с высокой плотностью речи.
- `scripts/transcribe.py` — faster-whisper, VAD, JSONL/TXT/VTT.
- `scripts/compare.py` — сводка, WER/CER (если есть эталон), текст рядом по окнам.

## Ограничения

- YouTube auto-captions часто без пунктуации, путают имена, сленг и английские
  вставки. Повторы строк удаляются эвристикой, поэтому на границах кусков
  возможны потери.
- Whisper любит «зацикливаться» на музыке и тишине. Включён VAD и
  `condition_on_previous_text=False`, но проверять повторяющиеся 5-граммы всё
  равно нужно (см. `repeated_5-grams` в отчёте).
- WER между auto и Whisper — это **расхождение**, а не точность. Для настоящей
  оценки нужен вручную выверенный эталон (`--reference`).
- Скачивание чужих VOD через `yt-dlp` нарушает ToS YouTube. Для собственного
  канала используйте YouTube Studio.

## Железо

GTX 1650 4 ГБ тянет `large-v3-turbo` в `int8_float16`. Если не хватит памяти —
`medium` или `small`, либо `--device cpu --compute-type int8`.
