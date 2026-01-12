# main.py — Monday
# Pipeline completa: script -> voce gTTS -> sfondo procedurale -> sottotitoli -> upload

from __future__ import annotations

import subprocess
from pathlib import Path

from uploader import generate_script, synth_voice, upload_video
from subtitles import add_burned_in_subtitles, generate_subtitles_txt_from_text
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
    - sfondo video procedurale verticale
    - video MP4 finale (voce + sfondo)

    Ritorna il percorso del video base (senza sottotitoli bruciati).
    """
    _ensure_dirs()

    # 1) Audio voce
    audio_wav = BUILD_DIR / "voice.wav"
    print(f"[Monday] Sintesi vocale in: {audio_wav}")
    synth_voice(script_text, audio_wav)

    # 2) Durata audio → durata sfondo
    duration_s = get_media_duration(audio_wav)
    # Limita la durata per sicurezza (evita file enormi)
    duration_s = min(max(duration_s, 15.0), 45.0)

    # 3) Sfondo procedurale
    bg_video = generate_procedural_background(duration_s)

    # 4) Merge voce + sfondo (manteniamo 1080x1920, formato short verticale)
    raw_video = VIDEOS_DIR / "video.mp4"

    cmd = [
        "ffmpeg",
        "-y",
        "-i",
        str(bg_video),
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

    # 2) Genera file subtitles.txt dal testo completo
    subtitles_txt_path = VIDEOS_DIR / "subtitles.txt"
    generate_subtitles_txt_from_text(
        raw_text=script_text,
        subtitles_txt_path=subtitles_txt_path,
    )

    # 3) Audio + video base (sfondo procedurale + voce)
    raw_video = _render_video(script_text)

    # 4) Sottotitoli bruciati
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
        title=title,
        description=description,
        tags=tags,
    )


if __name__ == "__main__":
    main()
