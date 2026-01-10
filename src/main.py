# main.py — Monday
# Pipeline completa: script -> voce gTTS -> video con sfondo -> sottotitoli burn-in -> upload

from __future__ import annotations

import subprocess
from pathlib import Path

from uploader import generate_script, synth_voice, upload_video
from subtitles import add_burned_in_subtitles

# Cartelle principali
BASE_DIR = Path(__file__).resolve().parent
ROOT_DIR = BASE_DIR.parent
ASSETS_DIR = ROOT_DIR / "assets"
BUILD_DIR = ROOT_DIR / "build"
VIDEOS_DIR = ROOT_DIR / "videos_to_upload"

# Sfondo del video (adatta il nome se il tuo file è diverso)
BACKGROUND_IMAGE = ASSETS_DIR / "background.jpg"


def _ensure_dirs() -> None:
    """Crea le cartelle build/ e videos_to_upload/ se non esistono."""
    BUILD_DIR.mkdir(parents=True, exist_ok=True)
    VIDEOS_DIR.mkdir(parents=True, exist_ok=True)


def _render_video(script_text: str) -> Path:
    """Genera:
    - audio WAV con gTTS
    - video MP4 con immagine di sfondo + audio

    Ritorna il percorso del video base (senza sottotitoli bruciati).
    """
    _ensure_dirs()

    audio_wav = BUILD_DIR / "voice.wav"
    print(f"[Monday] Sintesi vocale in: {audio_wav}")
    synth_voice(script_text, audio_wav)

    if not BACKGROUND_IMAGE.exists():
        raise FileNotFoundError(f"[Monday] Background non trovato: {BACKGROUND_IMAGE}")

    raw_video = VIDEOS_DIR / "video.mp4"

    cmd = [
        "ffmpeg",
        "-y",
        "-loop",
        "1",
        "-i",
        str(BACKGROUND_IMAGE),  # immagine di sfondo
        "-i",
        str(audio_wav),         # audio voce
        "-c:v",
        "libx264",
        "-tune",
        "stillimage",
        "-c:a",
        "aac",
        "-b:a",
        "128k",
        "-shortest",
        "-pix_fmt",
        "yuv420p",
        str(raw_video),
    ]
    print("[Monday] Genero video base con ffmpeg...")
    print("[Monday] Comando:", " ".join(cmd))
    subprocess.run(cmd, check=True)

    return raw_video


def main() -> None:
    print("[Monday] Avvio upload automatico...")

    # 1) Script Deadpan Files
    script_text, topic = generate_script()
    print("[Monday] Script generato (preview):", script_text[:120], "...")

    # 2) Audio + 3) video base (immagine + voce)
    raw_video = _render_video(script_text)

    # 4) Sottotitoli bruciati
    subtitles_txt_path = VIDEOS_DIR / "subtitles.txt"
    print("[Monday] Generazione video con sottotitoli bruciati...")
    final_video_path = add_burned_in_subtitles(
        video_path=raw_video,
        subtitles_txt_path=subtitles_txt_path,
        output_dir=VIDEOS_DIR,
    )

    # 5) Upload su YouTube
    print("[Monday] Preparazione upload...")
    upload_video(
        video_path=final_video_path,
        title=topic,
        description=script_text,
    )


if __name__ == "__main__":
    main()
