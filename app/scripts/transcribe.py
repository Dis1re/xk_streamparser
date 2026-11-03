"""Transcribe an audio file with faster-whisper and write JSONL/TXT/VTT."""

from __future__ import annotations

import argparse
import json
import os
import site
import sys
import time
from pathlib import Path

APP_ROOT = Path(__file__).resolve().parents[1]
PROJECT_ROOT = APP_ROOT.parent

_DLL_DIRS = []


def _add_cuda_dll_dirs() -> None:
    """Make pip-installed cuBLAS/cuDNN DLLs visible to CTranslate2 on Windows."""
    for root in site.getsitepackages():
        nvidia = Path(root) / "nvidia"
        for relative in ("cublas/bin", "cudnn/bin", "cuda_nvrtc/bin"):
            folder = nvidia / relative
            if folder.is_dir():
                _DLL_DIRS.append(os.add_dll_directory(str(folder)))
                os.environ["PATH"] = str(folder) + os.pathsep + os.environ.get("PATH", "")


_add_cuda_dll_dirs()

from faster_whisper import WhisperModel  # noqa: E402

from vtt import format_timestamp  # noqa: E402


def audio_duration(path: Path) -> float:
    import av

    with av.open(str(path)) as container:
        if container.duration is None:
            return 0.0
        return float(container.duration / av.time_base)


def load_model(
    name: str,
    device: str,
    compute_type: str,
    download_root: Path,
    cpu_threads: int,
) -> tuple[WhisperModel, str, str]:
    if device == "auto":
        try:
            compute = compute_type if compute_type != "auto" else "int8_float16"
            model = WhisperModel(
                name,
                device="cuda",
                compute_type=compute,
                download_root=str(download_root),
            )
            return model, "cuda", compute
        except Exception as exc:  # noqa: BLE001 - CUDA can fail for many reasons
            print(f"[warn] CUDA load failed, falling back to CPU: {exc}", file=sys.stderr)

    if device in ("auto", "cpu"):
        compute = compute_type if compute_type not in ("auto", "int8_float16", "float16") else "int8"
        model = WhisperModel(
            name,
            device="cpu",
            compute_type=compute,
            download_root=str(download_root),
            cpu_threads=cpu_threads,
        )
        return model, "cpu", compute

    compute = compute_type if compute_type != "auto" else "float16"
    model = WhisperModel(
        name,
        device=device,
        compute_type=compute,
        download_root=str(download_root),
    )
    return model, device, compute


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("audio", type=Path)
    parser.add_argument("--model", default="large-v3-turbo")
    parser.add_argument("--device", default="auto", choices=["auto", "cuda", "cpu"])
    parser.add_argument("--compute-type", default="auto")
    parser.add_argument("--language", default="ru")
    parser.add_argument("--beam-size", type=int, default=5)
    parser.add_argument("--no-vad", action="store_true")
    parser.add_argument("--condition-on-previous-text", action="store_true")
    parser.add_argument("--out-dir", type=Path)
    parser.add_argument("--models-dir", type=Path, default=APP_ROOT / "models")
    parser.add_argument("--cpu-threads", type=int, default=max(1, (os.cpu_count() or 4) - 1))
    parser.add_argument("--initial-prompt", default=None)
    parser.add_argument("--initial-prompt-file", type=Path)
    args = parser.parse_args()

    if args.initial_prompt_file:
        args.initial_prompt = args.initial_prompt_file.read_text(encoding="utf-8").strip()

    args.out_dir = args.out_dir or args.audio.parent / "whisper"
    args.out_dir.mkdir(parents=True, exist_ok=True)
    stem = args.audio.stem
    jsonl_path = args.out_dir / f"{stem}.jsonl"
    txt_path = args.out_dir / f"{stem}.txt"
    vtt_path = args.out_dir / f"{stem}.vtt"
    meta_path = args.out_dir / f"{stem}.meta.json"

    duration = audio_duration(args.audio)
    print(f"audio: {args.audio} ({format_timestamp(duration)})")
    load_start = time.perf_counter()
    model, device, compute = load_model(
        args.model, args.device, args.compute_type, args.models_dir, args.cpu_threads
    )
    print(
        f"model: {args.model} device={device} compute={compute} "
        f"load={time.perf_counter() - load_start:.1f}s"
    )

    started = time.perf_counter()
    segments, info = model.transcribe(
        str(args.audio),
        language=None if args.language == "auto" else args.language,
        task="transcribe",
        beam_size=args.beam_size,
        vad_filter=not args.no_vad,
        vad_parameters={"min_silence_duration_ms": 500},
        condition_on_previous_text=args.condition_on_previous_text,
        initial_prompt=args.initial_prompt,
        word_timestamps=False,
    )

    rows: list[dict] = []
    with jsonl_path.open("w", encoding="utf-8") as handle:
        for index, segment in enumerate(segments, 1):
            text = segment.text.strip()
            if not text:
                continue
            row = {
                "start": round(segment.start, 3),
                "end": round(segment.end, 3),
                "text": text,
            }
            rows.append(row)
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")
            if index % 25 == 0:
                handle.flush()
                elapsed = time.perf_counter() - started
                print(
                    f"  {format_timestamp(segment.end)}  segments={index}  "
                    f"elapsed={elapsed:.0f}s",
                    flush=True,
                )

    elapsed = time.perf_counter() - started
    txt_path.write_text(
        "\n".join(f"[{format_timestamp(row['start'])}] {row['text']}" for row in rows) + "\n",
        encoding="utf-8",
    )
    with vtt_path.open("w", encoding="utf-8") as handle:
        handle.write("WEBVTT\n\n")
        for row in rows:
            handle.write(
                f"{format_timestamp(row['start'], vtt=True)} --> "
                f"{format_timestamp(row['end'], vtt=True)}\n{row['text']}\n\n"
            )

    meta = {
        "audio": str(args.audio),
        "model": args.model,
        "device": device,
        "compute_type": compute,
        "language": info.language,
        "language_probability": round(info.language_probability, 4),
        "duration": round(duration, 3),
        "duration_after_vad": round(info.duration_after_vad, 3),
        "elapsed": round(elapsed, 1),
        "realtime_factor": round(elapsed / duration, 3) if duration else None,
        "segments": len(rows),
        "beam_size": args.beam_size,
        "vad": not args.no_vad,
        "condition_on_previous_text": args.condition_on_previous_text,
        "initial_prompt": args.initial_prompt,
    }
    meta_path.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"\nsegments: {len(rows)}")
    print(f"elapsed: {elapsed:.1f}s  RTF: {meta['realtime_factor']}x")
    print(f"language: {info.language} ({info.language_probability:.3f})")
    print(f"out: {args.out_dir}")


if __name__ == "__main__":
    main()
