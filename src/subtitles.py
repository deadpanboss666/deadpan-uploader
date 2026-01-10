from __future__ import annotations

import re
import subprocess
from pathlib import Path


def _split_sentences(text: str) -> list[str]:
    """Spezza il testo in frasi usando la punteggiatura."""
    clean = re.sub(r"\s+", " ", text).strip()
    if not clean:
        return []

    # Spezza su . ! ? seguiti da spazio
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


def _build_srt_content(sentences: list[str], durations: list[float]) -> str:
    """
    Crea il contenuto SRT usando una durata specifica per ogni frase.
    Le durate sono in secondi e vengono accumulate in sequenza.
    """
    if not sentences or not durations or len(sentences) != len(durations):
        return ""

    blocks: list[str] = []
    current_time = 0.0

    for idx, (sentence, dur) in enumerate(zip(sentences, durations), start=1):
        start_ts = _format_timestamp(current_time)
        end_ts = _format_timestamp(current_time + dur)

        blocks.append(str(idx))
        blocks.append(f"{start_ts} --> {end_ts}")
        blocks.append(sentence)
        blocks.append("")

        current_time += dur

    return "\n".join(blocks).strip() + "\n"


def add_burned_in_subtitles(video_path: str | Path, script_text: str) -> str:
    """
    Crea i sottotitoli dal testo e li brucia nel video con ffmpeg.

    - Il testo viene spezzato in frasi.
    - Ogni frase ha una durata stimata in base al numero di parole (~0.33s per parola),
      con minimo 1s e massimo 4s.
    - Se ffmpeg fallisce, ritorna il video originale SENZA sottotitoli.
    """
    video_path = Path(video_path).resolve()
    if not video_path.exists():
        raise FileNotFoundError(f"Video non trovato: {video_path}")

    workdir = video_path.parent

    # 1) Frasi dal testo
    sentences = _split_sentences(script_text)
    if not sentences:
        print("[Monday] Nessun testo per i sottotitoli, uso video originale.")
        return str(video_path)

    # 2) Durata per frase basata sul numero di parole
    #    ~0.33s per parola, con minimo 1s e massimo 4s per frase
    durations: list[float] = []
    for sentence in sentences:
        word_count = len(sentence.split())
        estimated = word_count * 0.33  # circa 3 parole al secondo
        clamped = max(1.0, min(4.0, estimated))
        durations.append(clamped)

    # 3) Genera SRT
    srt_content = _build_srt_content(sentences, durations)
    srt_path = workdir / f"{video_path.stem}.srt"
    srt_path.write_text(srt_content, encoding="utf-8")

    # 4) ffmpeg: brucia i sottotitoli
    output_name = f"{video_path.stem}_subs.mp4"
    output_path = workdir / output_name

    cmd = [
        "ffmpeg",
        "-y",
        "-i",
        video_path.name,
        "-vf",
        f"subtitles={srt_path.name}",
        "-c:a",
        "copy",
        output_name,
    ]

    try:
        subprocess.run(cmd, check=True, cwd=workdir)
    except FileNotFoundError as e:
        print(f"[Monday] ffmpeg non trovato: {e}. Uso video originale senza sottotitoli.")
        return str(video_path)
    except subprocess.CalledProcessError as e:
        print(f"[Monday] Errore ffmpeg durante la creazione del video con sottotitoli: {e}")
        print("[Monday] Uso il video originale SENZA sottotitoli.")
        return str(video_path)

    return str(output_path)
