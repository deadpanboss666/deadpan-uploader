# subtitles.py — Monday
# Generazione SRT e burn-in sottotitoli con ffmpeg

from __future__ import annotations

import re
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


def _build_srt_from_lines(
    lines: list[str],
    video_duration: float,
    max_chars_per_line: int = 32,
) -> str:
    """Costruisce il contenuto SRT a partire dal testo.

    Migliorie:
    - spezza il testo in frasi (., ?, !)
    - crea blocchi brevi (max ~2 righe)
    - assegna la durata in base al numero di parole (più parole -> più tempo)
    """

    # 1) Costruiamo una lista di frasi pulite
    sentence_chunks: list[str] = []

    for raw in lines:
        raw = raw.strip()
        if not raw:
            continue

        # spezza in frasi usando la punteggiatura come separatore
        parts = re.split(r"(?<=[.!?])\s+", raw)
        for part in parts:
            part = part.strip()
            if not part:
                continue
            sentence_chunks.append(part)

    if not sentence_chunks:
        return ""

    # 2) Converte le frasi in blocchi max 2 righe da max_chars_per_line
    chunks: list[str] = []
    word_counts: list[int] = []

    for sent in sentence_chunks:
        wrapped_lines = wrap(sent, max_chars_per_line)
        if not wrapped_lines:
            continue

        # usiamo al massimo 2 righe per sottotitolo
        block_lines = wrapped_lines[:2]
        block_text = "\n".join(block_lines)
        chunks.append(block_text)

        # conteggio parole (per la durata relativa)
        words = len(sent.split())
        word_counts.append(max(words, 1))

    if not chunks:
        return ""

    total_words = sum(word_counts)
    if total_words <= 0:
        total_words = len(chunks)

    # lasciamo un piccolo margine di coda per evitare testo incollato alla fine
    usable_duration = max(1.0, video_duration * 0.96)

    # 3) Costruiamo le entry SRT assegnando il tempo in base alle parole
    srt_lines: list[str] = []
    current_start = 0.0

    for idx, (text, words) in enumerate(zip(chunks, word_counts), start=1):
        share = words / total_words
        # durata proporzionale alle parole, minimo 1.2s
        block_duration = max(1.2, usable_duration * share)

        start_t = current_start
        end_t = start_t + block_duration

        # non superiamo la durata totale
        if end_t > video_duration:
            end_t = video_duration

        # safety: se per qualche motivo siamo oltre la fine, usciamo
        if start_t >= video_duration:
            break

        srt_lines.append(str(idx))
        srt_lines.append(f"{_format_ts(start_t)} --> {_format_ts(end_t)}")
        srt_lines.append(text)
        srt_lines.append("")  # riga vuota

        current_start = end_t

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

    # Stile sottotitoli:
    # - Fontsize 32
    # - Outline e shadow per leggibilità
    # - MarginV per tenerli un po' più alti (utile su mobile)
    subtitle_filter = (
        f"subtitles={srt_path.name}"
        ":force_style='Fontsize=32,"
        "Outline=2,Shadow=1,"
        "PrimaryColour=&H00FFFFFF&,"
        "OutlineColour=&H00000000&,"
        "MarginV=80,"
        "Alignment=2'"
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


def generate_subtitles_txt_from_text(
    raw_text: str,
    subtitles_txt_path: str | Path,
    max_chars_per_line: int = 60,
) -> None:
    """Genera automaticamente un file subtitles.txt a partire dal testo completo
    usato per la voce (gTTS).
    Una riga del file = un “blocco” di sottotitoli.
    """
    subtitles_txt_path = Path(subtitles_txt_path)
    subtitles_txt_path.parent.mkdir(parents=True, exist_ok=True)

    # Spezza il testo in frasi usando punteggiatura come delimitatore
    rough_sentences = re.split(r"[.!?]+", raw_text)
    lines: list[str] = []

    for sent in rough_sentences:
        sent = sent.strip()
        if not sent:
            continue
        # Se la frase è lunghissima, la spezzo in 2 pezzi max
        wrapped = wrap(sent, max_chars_per_line)
        if not wrapped:
            continue
        lines.append(" ".join(wrapped[:2]))

    if not lines:
        print("[Monday] Nessuna frase trovata per i sottotitoli (generate_subtitles_txt_from_text).")
        return

    subtitles_txt_path.write_text("\n".join(lines), encoding="utf-8")
    print(f"[Monday] File sottotitoli generato automaticamente: {subtitles_txt_path}")
