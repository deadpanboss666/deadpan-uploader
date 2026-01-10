# subtitles.py — Monday
# Generazione SRT e burn-in sottotitoli con ffmpeg

from __future__ import annotations

import math
import subprocess
from pathlib import Path
from textwrap import wrap


def _run_ffprobe_duration(video_path: Path) -> float:
    """Usa ffprobe per recuperare la durata del video in secondi.
    Se fallisce, usa un fallback di 30s per non bloccare la pipeline.
    """
    cmd = [
        "ffprobe",
        "-v",
        "error",
        "-show_entries",
        "format=duration",
        "-of",
        "default=nokey=1:noprint_wrappers=1",
        str(video_path),
    ]
    try:
        result = subprocess.check_output(cmd, stderr=subprocess.STDOUT)
        duration_str = result.decode().strip()
        duration = float(duration_str)
        print(f"[Monday] Durata video rilevata: {duration:.2f}s")
        return duration
    except Exception as e:  # noqa: BLE001
        print(f"[Monday] Attenzione: impossibile leggere la durata video con ffprobe: {e}")
        print("[Monday] Uso durata di fallback: 30s.")
        return 30.0


def _format_ts(seconds: float) -> str:
    """Converte i secondi in formato SRT (HH:MM:SS,mmm)."""
    if seconds < 0:
        seconds = 0.0
    ms = int(round((seconds - int(seconds)) * 1000))
    s = int(seconds) % 60
    m = (int(seconds) // 60) % 60
    h = int(seconds) // 3600
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def _build_srt_from_lines(lines: list[str], video_duration: float, max_chars_per_line: int = 40) -> str:
    """Costruisce il contenuto SRT a partire dalle righe di testo."""
    # Pulizia righe
    chunks: list[str] = []
    for raw in lines:
        raw = raw.strip()
        if not raw:
            continue
        # spezza le frasi troppo lunghe in 2 righe massimo (per leggibilità)
        wrapped = wrap(raw, max_chars_per_line)
        if not wrapped:
            continue
        # Limita a 2 righe max per sottotitolo
        chunks.append("\n".join(wrapped[:2]))

    if not chunks:
        return ""

    n = len(chunks)
    slot = video_duration / n
    srt_lines: list[str] = []

    for idx, text in enumerate(chunks, start=1):
        start_t = slot * (idx - 1)
        end_t = slot * idx - 0.2  # piccolo margine per non sovrapporre
        if end_t <= start_t:
            end_t = start_t + 0.5

        srt_lines.append(str(idx))
        srt_lines.append(f"{_format_ts(start_t)} --> {_format_ts(end_t)}")
        srt_lines.append(text)
        srt_lines.append("")  # riga vuota separatrice

    return "\n".join(srt_lines).strip() + "\n"


def add_burned_in_subtitles(
    video_path: str | Path,
    subtitles_txt_path: str | Path,
    output_dir: str | Path | None = None,
) -> str:
    """Crea un nuovo video con sottotitoli bruciati.
    Se qualcosa va storto, restituisce il path del video originale.
    """
    video_path = Path(video_path)
    subtitles_txt_path = Path(subtitles_txt_path)

    if output_dir is None:
        output_dir = video_path.parent.parent / "build"  # es: deadpan-uploader/build
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    # Se non c'è il file di testo, usa direttamente il video originale.
    if not subtitles_txt_path.exists():
        print(f"[Monday] Nessun file di sottotitoli trovato ({subtitles_txt_path}). Uso video originale.")
        return str(video_path)

    try:
        raw_lines = subtitles_txt_path.read_text(encoding="utf-8").splitlines()
    except UnicodeDecodeError:
        raw_lines = subtitles_txt_path.read_text(encoding="latin-1").splitlines()

    if not any(line.strip() for line in raw_lines):
        print("[Monday] File sottotitoli vuoto. Uso video originale.")
        return str(video_path)

    # Calcola durata video
    duration = _run_ffprobe_duration(video_path)

    # Costruisci contenuto SRT
    srt_content = _build_srt_from_lines(raw_lines, duration)
    if not srt_content.strip():
        print("[Monday] Impossibile costruire SRT dai sottotitoli. Uso video originale.")
        return str(video_path)

    srt_path = output_dir / "subtitles.srt"
    srt_path.write_text(srt_content, encoding="utf-8")

    output_video = output_dir / "video_with_subs.mp4"

    cmd = [
        "ffmpeg",
        "-y",
        "-i",
        str(video_path),
        "-vf",
        f"subtitles={srt_path.name}",
        "-c:a",
        "copy",
        str(output_video),
    ]

    print("[Monday] Lancio ffmpeg per burn-in sottotitoli...")
    print("[Monday] Comando:", " ".join(cmd))

    try:
        subprocess.run(cmd, check=True, cwd=str(output_dir))
        print(f"[Monday] Video con sottotitoli generato: {output_video}")
        return str(output_video)
    except subprocess.CalledProcessError as e:  # noqa: BLE001
        print("[Monday] Errore ffmpeg durante la creazione del video con sottotitoli.")
        print(f"[Monday] Dettagli: {e}")
        print("[Monday] Uso il video originale SENZA sottotitoli.")
        return str(video_path)
