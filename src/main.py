# main.py — Monday
# Pipeline completa:
# 1) genera script
# 2) gTTS -> audio WAV
# 3) genera background procedurale 9:16
# 4) monta background + voce in MP4
# 5) brucia i sottotitoli
# 6) upload su YouTube

from __future__ import annotations

import subprocess
from pathlib import Path

from uploader import generate_script, synth_voice, upload_video
from subtitles import add_burned_in_subtitles
from backgrounds import get_media_duration, generate_procedural_background

# Cartelle principali
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
    - background video procedurale 9:16
    - video MP4 finale (background + voce)

    Ritorna il percorso del video base (senza sottotitoli bruciati).
    """
    _ensure_dirs()

    # 1) Sintesi vocale
    audio_wav = BUILD_DIR / "voice.wav"
    print(f"[Monday] Sintesi vocale in: {audio_wav}")
    synth_voice(script_text, audio_wav)

    # 2) Durata reale dell'audio (serve per il background)
    duration = get_media_duration(audio_wav)
    print(f"[Monday] Durata audio per il background: {duration:.2f}s")

    # 3) Background procedurale
    bg_video_path = BUILD_DIR / "bg_video.mp4"
    print("[Monday] Generazione background procedurale...")
    bg_result = generate_procedural_background(
        duration_seconds=duration,
        output_path=bg_video_path,
    )

    # Se generate_procedural_background fallisce, facciamo un fallback sicuro
    if not bg_result:
        print("[Monday] Errore background. Fallback su colore statico.")
        cmd_fallback = [
            "ffmpeg",
            "-y",
            "-f",
            "lavfi",
            "-i",
            f"color=c=#05070b:s=1080x1920:d={duration:.3f}",
            "-vf",
            "format=yuv420p",
            "-r",
            "30",
            "-an",
            str(bg_video_path),
        ]
        subprocess.run(cmd_fallback, check=True)

    # 4) Montaggio background + voce in un unico MP4
    raw_video = VIDEOS_DIR / "video.mp4"

    cmd = [
        "ffmpeg",
        "-y",
        "-i",
        str(bg_video_path),  # video di sfondo 9:16
        "-i",
        str(audio_wav),      # traccia voce
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
    print("[Monday] Genero video base (background + voce) con ffmpeg...")
    print("[Monday] Comando:", " ".join(cmd))
    subprocess.run(cmd, check=True)

    return raw_video


def main() -> None:
    print("[Monday] Avvio pipeline Deadpan completamente automatica...")

    # 1) Script + metadati YouTube (già ottimizzati SEO in uploader.py)
    script_text, title, description, tags = generate_script()
    print("[Monday] Script generato (preview):", script_text[:140], "...")
    print("[Monday] Titolo scelto:", title)

    # 2–4) Audio + background + video base
    raw_video = _render_video(script_text)

    # 5) Sottotitoli bruciati (file subtitles.txt creato dentro synth_voice)
    subtitles_txt_path = VIDEOS_DIR / "subtitles.txt"
    print("[Monday] Generazione video con sottotitoli bruciati...")
    final_video_path = add_burned_in_subtitles(
        video_path=raw_video,
        subtitles_txt_path=subtitles_txt_path,
        output_dir=VIDEOS_DIR,
    )

    # 6) Upload su YouTube
    print("[Monday] Preparazione upload...")
    upload_video(
        video_path=final_video_path,
        title=title,
        description=description,
        tags=tags,
    )


if __name__ == "__main__":
    main()
