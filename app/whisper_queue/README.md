# Очередь для Whisper

Здесь лежит аудио всех стримов, у которых не было auto-субтитров.
Все пути ниже — от папки `app`.

- **74 файла**, формат `.m4a`, mono 16 kHz, AAC ~64 kbps.
- Имена: `<номер>_<название>.m4a` для нумерованных выпусков и
  `(<бонусный номер>)_<название>.m4a` для стримов без номера.
- `manifest.json` — соответствие «номер → видео → файл».
- `failures.json` появляется только если что-то не скачалось.

## Как прогнать на сервере

```bash
# пример для faster-whisper
python -m faster_whisper whisper_queue/176_*.m4a \
  --model large-v3 \
  --language ru \
  --output_format vtt \
  --output_dir whisper_out
```

После распознавания положите VTT в `data/<video_id>/subs/` и соберите
`auto_minutes.txt` тем же `scripts/export_text.py`, что и для auto-субтитров.
Затем замените заглушку `streams/<номер>_без_субтитров.md` полноценной
заметкой и поменяйте источник в `streams/README.md` на `Whisper`.
