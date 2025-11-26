from __future__ import annotations

import re
import subprocess
from pathlib import Path


def _split_sentences(text: str) -> list[str]:
    """Spezza il testo in frasi usando la punteggiatura."""
    clean = re.sub(r"\s+", " ", text).strip()
    if not clean:
        return []

    parts = re.split(r"(?<=[.!?])\s+", clean)
    sentences = [p.strip() for p in parts if p.strip()]

    if not sentences:
        sentences = [clean]

    return sentences


def _format_timestamp(seconds: float) -> str:
    """Converte secondi float in formato SRT hh:mm:ss,mmm."""
    total_ms = int(round(seconds * 1000))
    hours, rem = divmod(total_ms, 3600_000)
    minutes, rem = divmod(rem, 60_000)
    secs, ms = divmod(rem, 1000)
    return f"{hours:02}:{minutes:02}:{secs:02},{ms:03}"


def _build_srt_content(sentences: list[str], total_duration: float) -> str:
    """
    Crea il contenuto SRT distribuendo le frasi in modo uniforme
    lungo tutta la durata del video.
    """
    if not sentences or total_duration <= 0:
        return ""

    n = len(sentences)
    segment = total_duration / n

    blocks: list[str] = []
    start = 0.0

    for idx, sentence in enumerate(sentences, start=1):
        end = segment * idx
        if idx == n:
            end = total_duration

        start_ts = _format_timestamp(start)
        end_ts = _format_timestamp(end)

        blocks.append(str(idx))
        blocks.append(f"{start_ts} --> {end_ts}")
        blocks.append(sentence)
        blocks.append("")

        start = end

    return "\n".join(blocks).strip() + "\n"


def _get_video_duration(video_path: Path) -> float:
    """
    Legge la durata del video.
    1) prova con ffprobe
    2) se fallisce, prova con moviepy
    3) se fallisce ancora, usa 30s di fallback (caso limite)
    """
    # 1) tentativo con ffprobe
    cmd = [
        "ffprobe",
        "-v", "error",
        "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1",
        str(video_path),
    ]
    result = subprocess.run(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        check=True,
    )
    output = result.stdout.strip()

    try:
        return float(output)
    except ValueError:
        print(f"[Monday] Durata non valida da ffprobe ('{output}'), provo con moviepy...")

    # 2) tentativo con moviepy
    try:
        from moviepy.editor import VideoFileClip

        with VideoFileClip(str(video_path)) as clip:
            return float(clip.duration)
    except Exception as e:
        print(f"[Monday] Errore anche con moviepy: {e}")
        print("[Monday] Uso 30s di durata di fallback.")
        return 30.0



def add_burned_in_subtitles(video_path: str | Path, script_text: str) -> str:
    """
    Crea i sottotitoli dal testo e li brucia nel video con ffmpeg.
    Ritorna il path del nuovo video con i sottotitoli.
    """
    video_path = Path(video_path).resolve()
    if not video_path.exists():
        raise FileNotFoundError(f"Video non trovato: {video_path}")

    workdir = video_path.parent

    # 1) Durata video
    duration = _get_video_duration(video_path)

    # 2) Frasi dal testo
    sentences = _split_sentences(script_text)
    if not sentences:
        # niente testo => niente modifiche
        return str(video_path)

    # 3) Genera SRT
    srt_content = _build_srt_content(sentences, duration)
    srt_path = workdir / f"{video_path.stem}.srt"
    srt_path.write_text(srt_content, encoding="utf-8")

    # 4) ffmpeg: brucia i sottotitoli
    output_name = f"{video_path.stem}_subs.mp4"
    output_path = workdir / output_name

    cmd = [
        "ffmpeg",
        "-y",
        "-i", video_path.name,
        "-vf", f"subtitles={srt_path.name}",
        "-c:a", "copy",
        output_name,
    ]
    subprocess.run(cmd, check=True, cwd=workdir)

    return str(output_path)
