# main.py — Monday
# Pipeline completa:
# 1) genera script Deadpan
# 2) genera audio voce gTTS
# 3) genera video di sfondo procedurale (ffmpeg, nessuna immagine)
# 4) monta sfondo + voce in un video verticale
# 5) aggiunge sottotitoli burn-in
# 6) carica su YouTube

from __future__ import annotations

import subprocess
from pathlib import Path

from uploader import generate_script, synth_voice, upload_video
from subtitles import add_burned_in_subtitles
from backgrounds import get_media_duration, generate_procedural_background

# Struttura cartelle
BASE_DIR = Path(__file__).resolve().parent
ROOT_DIR = BASE_DIR.parent
BUILD_DIR = ROOT_DIR / "build"
VIDEOS_DIR = ROOT_DIR / "videos_to_upload"


def _ensure_dirs() -> None:
    """Crea le cartelle build/ e videos_to_upload/ se non esistono."""
    BUILD_DIR.mkdir(parents=True, exist_ok=True)
    VIDEOS_DIR.mkdir(parents=True, exist_ok=True)


def _render_video(script_text: str) -> Path:
    """Genera:
    - audio WAV con gTTS
    - sfondo video procedurale (stessa durata dell'audio)
    - video MP4 finale (sfondo + voce)

    Restituisce il percorso del video base (senza sottotitoli bruciati).
    """
    _ensure_dirs()

    # 1) Audio voce
    audio_wav = BUILD_DIR / "voice.wav"
    print(f"[Monday] Sintesi vocale in: {audio_wav}")
    synth_voice(script_text, audio_wav)

    # 2) Durata audio per dimensionare lo sfondo
    audio_duration = get_media_duration(audio_wav, fallback=30.0)
    background_video = BUILD_DIR / "background.mp4"

    print(f"[Monday] Genero sfondo procedurale per {audio_duration:.2f}s...")
    generate_procedural_background(
        duration=audio_duration + 1.0,  # leggero margine
        output_path=background_video,
    )

    # 3) Montaggio sfondo + voce in verticale 9:16
    raw_video = VIDEOS_DIR / "video.mp4"

    cmd = [
        "ffmpeg",
        "-y",
        "-i",
        str(background_video),
        "-i",
        str(audio_wav),
        "-c:v",
        "libx264",
        "-c:a",
        "aac",
        "-b:a",
        "128k",
        "-shortest",
        "-pix_fmt",
        "yuv420p",
        str(raw_video),
    ]

    print("[Monday] Genero video base (sfondo + voce) con ffmpeg...")
    print("[Monday] Comando:", " ".join(cmd))
    subprocess.run(cmd, check=True)

    return raw_video


def main() -> None:
    print("[Monday] Avvio pipeline Deadpan completamente automatica...")

    # 1) Script Deadpan Files + SEO YouTube
    script_text, title, description, tags = generate_script()
    print("[Monday] Script generato (preview):", script_text[:120], "...")
    print("[Monday] Titolo scelto:", title)

    # 2–3–4) Audio + sfondo procedurale + montaggio video
    raw_video = _render_video(script_text)

    # 5) Sottotitoli bruciati (subtitles.txt è generato da synth_voice)
    subtitles_txt_path = VIDEOS_DIR / "subtitles.txt"
    print("[Monday] Generazione video con sottotitoli bruciati...")
    final_video_path = add_burned_in_subtitles(
        video_path=raw_video,
        subtitles_txt_path=subtitles_txt_path,
        output_dir=VIDEOS_DIR,
    )

    # 6) Upload su YouTube
    print("[Monday] Preparazione upload su YouTube...")
    upload_video(
        video_path=final_video_path,
        title=title,
        description=description,
        tags=tags,
    )


if __name__ == "__main__":
    main()
