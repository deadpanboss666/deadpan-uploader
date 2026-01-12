# main.py — Monday
# Pipeline completa: script -> voce gTTS (per-frase) -> sfondo procedurale -> sottotitoli ASS -> upload

from __future__ import annotations

import subprocess
from pathlib import Path

from uploader import generate_script, upload_video
from subtitles import add_burned_in_subtitles
from backgrounds import get_media_duration, generate_procedural_background
from tts_timestamps import build_voice_and_subs_from_text


# Cartelle principali
BASE_DIR = Path(__file__).resolve().parent
ROOT_DIR = BASE_DIR.parent
BUILD_DIR = ROOT_DIR / "build"
VIDEOS_DIR = ROOT_DIR / "videos_to_upload"


def _ensure_dirs() -> None:
    """Crea le cartelle build/ e videos_to_upload/ se non esistono."""
    BUILD_DIR.mkdir(parents=True, exist_ok=True)
    VIDEOS_DIR.mkdir(parents=True, exist_ok=True)


def _render_video(background_video: Path, voice_audio: Path) -> Path:
    """
    Merge voce + sfondo (manteniamo 1080x1920, formato short verticale).
    Ritorna il percorso del video base (senza sottotitoli bruciati).
    """
    _ensure_dirs()

    raw_video = VIDEOS_DIR / "video_base.mp4"

    cmd = [
        "ffmpeg",
        "-y",
        "-i",
        str(background_video),
        "-i",
        str(voice_audio),
        "-c:v",
        "libx264",
        "-preset",
        "veryfast",
        "-crf",
        "18",
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
    print("[Monday] Avvio pipeline Deadpan completamente automatica...")

    # 1) Script Deadpan Files + metadati YouTube
    script_text, title, description, tags = generate_script()
    print("[Monday] Script generato (preview):", script_text[:140], "...")
    print("[Monday] Titolo scelto:", title)

    _ensure_dirs()

    # 2) Voce + sottotitoli ASS con sync reale (per-frase)
    print("[Monday] Genero voice.mp3 + subtitles.ass (sync reale)...")
    voice_audio, subtitles_ass, _segments = build_voice_and_subs_from_text(
        story_text=script_text,
        work_dir=BUILD_DIR,
        lang="en",
        tld="com",
    )
    print(f"[Monday] Voice: {voice_audio}")
    print(f"[Monday] Subtitles: {subtitles_ass}")

    # 3) Durata audio → durata sfondo
    duration_s = get_media_duration(voice_audio)
    duration_s = min(max(duration_s, 15.0), 45.0)

    # 4) Sfondo procedurale
    print("[Monday] Genero background procedurale...")
    bg_video = generate_procedural_background(duration_s)

    # 5) Video base (sfondo + voce)
    raw_video = _render_video(bg_video, voice_audio)

    # 6) Sottotitoli bruciati (ASS)
    print("[Monday] Brucio sottotitoli (ASS) nel video finale...")
    final_video_path = add_burned_in_subtitles(
        video_path=raw_video,
        subtitles_path=subtitles_ass,
        output_dir=VIDEOS_DIR,
    )

    # 7) Upload su YouTube
    print("[Monday] Preparazione upload...")
    upload_video(
        video_path=final_video_path,
        title=title,
        description=description,
        tags=tags,
    )


if __name__ == "__main__":
    main()
