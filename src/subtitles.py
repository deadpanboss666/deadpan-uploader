# subtitles.py — Monday
# Generazione SRT e burn-in sottotitoli con ffmpeg, stile più leggibile

from __future__ import annotations

import math
import subprocess
from pathlib import Path
from textwrap import wrap


def _run_ffprobe_duration(video_path: Path) -> float:
    """Usa ffprobe per recuperare la durata del video in secondi."""
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
        print(f"[Monday/subtitles] Durata video rilevata: {duration:.2f}s")
        return duration
    except Exception as e:  # noqa: BLE001
        print(f"[Monday/subtitles] Attenzione: impossibile leggere durata video con ffprobe: {e}")
        print("[Monday/subtitles] Uso durata di fallback: 30s.")
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


def _build_srt_from_lines(
    lines: list[str],
    video_duration: float,
    max_chars_per_line: int = 32,
) -> str:
    """Costruisce il contenuto SRT a partire dalle righe di testo.

    - spezza il testo in "blocchi" massimo 2 righe
    - cerca di distribuire il tempo in modo uniforme
    """
    chunks: list[str] = []

    for raw in lines:
        raw = raw.strip()
        if not raw:
            continue
        wrapped = wrap(raw, max_chars_per_line)
        if not wrapped:
            continue
        chunks.append("\n".join(wrapped[:2]))  # max 2 righe

    if not chunks:
        return ""

    n = len(chunks)
    # tempo medio per blocco, ma con minimo 1.2s per non essere troppo veloci
    slot = max(video_duration / n, 1.2)

    srt_lines: list[str] = []
    start_t = 0.5  # piccolo offset iniziale

    for idx, text in enumerate(chunks, start=1):
        end_t = start_t + slot - 0.3
        if end_t <= start_t:
            end_t = start_t + 0.7

        srt_lines.append(str(idx))
        srt_lines.append(f"{_format_ts(start_t)} --> {_format_ts(end_t)}")
        srt_lines.append(text)
        srt_lines.append("")

        start_t = end_t + 0.1

    return "\n".join(srt_lines).strip() + "\n"


def generate_subtitles_txt_from_text(
    raw_text: str,
    subtitles_txt_path: str | Path,
) -> Path:
    """
    Converte lo script intero (una stringa lunga) in un file subtitles.txt
    dove ogni riga è una "frase" (= blocco SRT).
    """
    subtitles_txt_path = Path(subtitles_txt_path)
    subtitles_txt_path.parent.mkdir(parents=True, exist_ok=True)

    # Spezzatura grossolana: punti, punti esclamativi, interrogativi
    temp = raw_text.replace("?", "?.").replace("!", "!.")
    sentences = [s.strip() for s in temp.split(".") if s.strip()]

    # Se è troppo poco, spezza anche per virgole lunghe
    if len(sentences) < 4:
        extra: list[str] = []
        for s in sentences:
            parts = [p.strip() for p in s.split(",") if p.strip()]
            if len(parts) <= 1:
                extra.append(s)
            else:
                extra.extend(parts)
        sentences = extra

    with subtitles_txt_path.open("w", encoding="utf-8") as f:
        for s in sentences:
            f.write(s + "\n")

    print(f"[Monday/subtitles] File subtitles.txt generato: {subtitles_txt_path}")
    return subtitles_txt_path


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
        output_dir = video_path.parent
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    if not subtitles_txt_path.exists():
        print(f"[Monday/subtitles] Nessun file di sottotitoli trovato ({subtitles_txt_path}). Uso video originale.")
        return str(video_path)

    try:
        raw_lines = subtitles_txt_path.read_text(encoding="utf-8").splitlines()
    except UnicodeDecodeError:
        raw_lines = subtitles_txt_path.read_text(encoding="latin-1").splitlines()

    if not any(line.strip() for line in raw_lines):
        print("[Monday/subtitles] File sottotitoli vuoto. Uso video originale.")
        return str(video_path)

    duration = _run_ffprobe_duration(video_path)

    srt_content = _build_srt_from_lines(raw_lines, duration)
    if not srt_content.strip():
        print("[Monday/subtitles] Impossibile costruire SRT dai sottotitoli. Uso video originale.")
        return str(video_path)

    srt_path = output_dir / "subtitles.srt"
    srt_path.write_text(srt_content, encoding="utf-8")

    output_video = output_dir / "video_with_subs.mp4"

    # Stile sottotitoli:
    # - font bianco
    # - bordo nero
    # - box semi-trasparente
    # - centrati in basso ma non troppo
    # NB: per usare "force_style" serve libass (è disponibile su runner GitHub)
    subtitle_filter = (
        f"subtitles={srt_path.name}:"
        "force_style='Fontsize=26,PrimaryColour=&H00FFFFFF&,OutlineColour=&H00000000&,"
        "BorderStyle=3,Outline=2,BackColour=&H80000000&,Alignment=2,MarginV=80'"
    )

    cmd = [
        "ffmpeg",
        "-y",
        "-i",
        str(video_path),
        "-vf",
        subtitle_filter,
        "-c:a",
        "copy",
        str(output_video),
    ]

    print("[Monday/subtitles] Lancio ffmpeg per burn-in sottotitoli...")
    print("[Monday/subtitles] Comando:", " ".join(cmd))

    try:
        subprocess.run(cmd, check=True, cwd=str(output_dir))
        print(f"[Monday/subtitles] Video con sottotitoli generato: {output_video}")
        return str(output_video)
    except subprocess.CalledProcessError as e:  # noqa: BLE001
        print("[Monday/subtitles] Errore ffmpeg durante la creazione del video con sottotitoli.")
        print(f"[Monday/subtitles] Dettagli: {e}")
        print("[Monday/subtitles] Uso il video originale SENZA sottotitoli.")
        return str(video_path)
