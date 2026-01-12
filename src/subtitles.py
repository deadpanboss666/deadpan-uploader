# subtitles.py — Monday
# Generazione SRT con frasi principali e timing proporzionale alla voce

from __future__ import annotations

import math
import re
import subprocess
from pathlib import Path
from textwrap import wrap


# ---------------------------------------------------------------------------
# Utilità di base
# ---------------------------------------------------------------------------


def _run_ffprobe_duration(video_path: Path) -> float:
    """Usa ffprobe per la durata del video in secondi.
    Se fallisce, usa 25s di fallback.
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
        print(f"[Monday/subtitles] Durata video rilevata: {duration:.2f}s")
        return duration
    except Exception as e:  # noqa: BLE001
        print(f"[Monday/subtitles] Impossibile leggere la durata con ffprobe: {e}")
        print("[Monday/subtitles] Uso durata di fallback: 25s.")
        return 25.0


def _format_ts(seconds: float) -> str:
    """Converte secondi in formato SRT (HH:MM:SS,mmm)."""
    if seconds < 0:
        seconds = 0.0
    ms = int(round((seconds - int(seconds)) * 1000))
    s = int(seconds) % 60
    m = (int(seconds) // 60) % 60
    h = int(seconds) // 3600
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


# ---------------------------------------------------------------------------
# Preparazione frasi per i sottotitoli
# ---------------------------------------------------------------------------


def _split_into_caption_units(raw_text: str, max_chars_per_caption: int = 80) -> list[str]:
    """
    Prende il testo completo e lo taglia in frasi "forti" per i sottotitoli.

    Regole:
    - normalizza spazi
    - spezza su ., ?, !
    - unisce frasi molto corte finché non superano max_chars_per_caption
    - se una frase è troppo lunga, la spezza
    """
    text = re.sub(r"\s+", " ", (raw_text or "").strip())
    if not text:
        return []

    # split su fine frase
    sentences = re.split(r"(?<=[.!?])\s+", text)
    sentences = [s.strip() for s in sentences if s.strip()]

    units: list[str] = []
    buffer = ""

    for sent in sentences:
        # Proviamo ad aggiungere la frase al buffer corrente
        candidate = f"{buffer} {sent}".strip() if buffer else sent

        if len(candidate) <= max_chars_per_caption:
            buffer = candidate
        else:
            # Il buffer è pieno, lo salviamo
            if buffer:
                units.append(buffer)
                buffer = ""

            # Se la frase da sola è troppo lunga, spezzala
            if len(sent) <= max_chars_per_caption:
                buffer = sent
            else:
                chunks = wrap(sent, max_chars_per_caption)
                # tutte le parti tranne l'ultima vanno direttamente
                for c in chunks[:-1]:
                    units.append(c.strip())
                buffer = chunks[-1].strip()

    if buffer:
        units.append(buffer)

    return units


def generate_subtitles_txt_from_text(raw_text: str, subtitles_txt_path: str | Path) -> None:
    """
    Prende lo script completo e genera un file di testo con
    le frasi principali, una per riga. Sarà poi usato per creare l'SRT.
    """
    subtitles_txt_path = Path(subtitles_txt_path)
    subtitles_txt_path.parent.mkdir(parents=True, exist_ok=True)

    units = _split_into_caption_units(raw_text, max_chars_per_caption=80)
    if not units:
        print("[Monday/subtitles] Nessun testo per sottotitoli; file vuoto.")
        subtitles_txt_path.write_text("", encoding="utf-8")
        return

    # Salviamo ogni "caption unit" su una riga
    subtitles_txt_path.write_text("\n".join(units), encoding="utf-8")
    print(f"[Monday/subtitles] File subtitles.txt generato: {subtitles_txt_path}")


# ---------------------------------------------------------------------------
# Costruzione SRT con timing proporzionale alla lunghezza delle frasi
# ---------------------------------------------------------------------------


def _build_srt_from_lines(
    lines: list[str],
    video_duration: float,
    max_chars_per_line: int = 36,
) -> str:
    """
    Costruisce il contenuto SRT:

    - pulisce le righe vuote
    - per ogni riga crea un blocco con max 2 righe a schermo
    - assegna la durata di ogni blocco in modo proporzionale
      alla lunghezza del testo (più testo = più tempo)
    """
    # Pulizia e rimozione righe vuote
    captions: list[dict] = []
    for raw in lines:
        text = raw.strip()
        if not text:
            continue
        no_newline = re.sub(r"\s+", " ", text)
        if not no_newline:
            continue

        # Wrapping a 2 righe massimo per leggibilità
        wrapped_lines = wrap(no_newline, max_chars_per_line)
        if not wrapped_lines:
            continue

        display_text = "\n".join(wrapped_lines[:2])
        weight = max(len(no_newline), 10)  # almeno un peso minimo

        captions.append(
            {
                "raw": no_newline,
                "text": display_text,
                "weight": weight,
            }
        )

    if not captions:
        return ""

    total_weight = sum(c["weight"] for c in captions)
    if total_weight <= 0 or not math.isfinite(total_weight):
        total_weight = len(captions)

    # Primo pass: durate proporzionali alla lunghezza
    min_duration = 1.2  # secondi minimi per caption
    durations = []
    for c in captions:
        frac = c["weight"] / total_weight
        ideal = video_duration * frac
        dur = max(min_duration, ideal)
        durations.append(dur)

    # Normalizziamo per far tornare la somma alla durata del video
    sum_dur = sum(durations)
    if sum_dur <= 0 or not math.isfinite(sum_dur):
        # fallback: divisione uniforme
        slot = max(video_duration / len(captions), min_duration)
        durations = [slot] * len(captions)
        sum_dur = slot * len(captions)

    scale = video_duration / sum_dur
    durations = [d * scale for d in durations]

    # Costruzione blocchi SRT
    srt_lines: list[str] = []
    current_time = 0.0

    for idx, (cap, dur) in enumerate(zip(captions, durations), start=1):
        start_t = current_time
        end_t = start_t + dur

        # leggero margine finale per evitare sforamento
        if end_t > video_duration:
            end_t = video_duration

        srt_lines.append(str(idx))
        srt_lines.append(f"{_format_ts(start_t)} --> {_format_ts(end_t)}")
        srt_lines.append(cap["text"])
        srt_lines.append("")  # riga vuota separatrice

        current_time = end_t

    return "\n".join(srt_lines).strip() + "\n"


# ---------------------------------------------------------------------------
# ffmpeg: burn-in sottotitoli
# ---------------------------------------------------------------------------


def add_burned_in_subtitles(
    video_path: str | Path,
    subtitles_txt_path: str | Path,
    output_dir: str | Path | None = None,
) -> str:
    """
    Crea un nuovo video con sottotitoli bruciati.
    Se qualcosa va storto, restituisce il path del video originale.
    """
    video_path = Path(video_path)
    subtitles_txt_path = Path(subtitles_txt_path)

    if output_dir is None:
        output_dir = video_path.parent  # es: videos_to_upload
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

    # Durata video
    duration = _run_ffprobe_duration(video_path)

    # Costruzione SRT
    srt_content = _build_srt_from_lines(raw_lines, duration)
    if not srt_content.strip():
        print("[Monday/subtitles] Impossibile costruire SRT. Uso video originale.")
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
