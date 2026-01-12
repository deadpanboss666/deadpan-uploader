# main.py — Monday
# Pipeline completa:
# 1) Genera script Deadpan Files
# 2) Crea voce TTS con gTTS
# 3) Genera automaticamente un background video 9:16 procedurale
# 4) Combina background + voce in uno short MP4
# 5) Applica sottotitoli burn-in
# 6) Carica su YouTube via OAuth

from __future__ import annotations

import subprocess
from pathlib import Path

from uploader import generate_script, synth_voice, upload_video
from subtitles import add_burned_in_subtitles
from backgrounds import get_media_duration, generate_procedural_background


# Cartelle principali
BASE_DIR = Path(__file__).resolve().parent
ROOT_DIR = BASE_DIR.parent
ASSETS_DIR = ROOT_DIR / "assets"
BUILD_DIR = ROOT_DIR / "build"
VIDEOS_DIR = ROOT_DIR / "videos_to_upload"

# Background statico opzionale (fallback, se la generazione procedurale fallisce)
BACKGROUND_IMAGE = ASSETS_DIR / "background.jpg"


def _ensure_dirs() -> None:
    """Crea le cartelle build/ e videos_to_upload/ se non esistono."""
    BUILD_DIR.mkdir(parents=True, exist_ok=True)
    VIDEOS_DIR.mkdir(parents=True, exist_ok=True)


def _render_video(script_text: str) -> Path:
    """Genera:
    - audio WAV con gTTS
    - background video 9:16 procedurale (durata = durata voce)
    - video MP4 con background + voce

    Ritorna il percorso del video base (senza sottotitoli bruciati).
    """
    _ensure_dirs()

    # 1) Sintesi vocale
    audio_wav = BUILD_DIR / "voice.wav"
    print(f"[Monday] Sintesi vocale in: {audio_wav}")
    synth_voice(script_text, audio_wav)

    # 2) Calcola durata della voce per sincronizzare il background
    voice_duration = get_media_duration(audio_wav)

    # 3) Genera background procedurale 9:16
    background_video = BUILD_DIR / "background_auto.mp4"
    background_path_str = generate_procedural_background(
        duration_seconds=voice_duration,
        output_path=background_video,
    )

    # 4) Se qualcosa è andato storto, eventuale fallback su immagine statica
    background_is_video = True
    if not background_path_str:
        if BACKGROUND_IMAGE.exists():
            print(
                "[Monday] Impossibile generare background procedurale. "
                "Uso fallback statico."
            )
            background_path_str = str(BACKGROUND_IMAGE)
            background_is_video = False
        else:
            raise RuntimeError(
                "[Monday] Nessun background valido disponibile "
                "(procedurale fallito e nessun background.jpg trovato)."
            )

    raw_video = VIDEOS_DIR / "video.mp4"

    if background_is_video:
        # Background già video 9:16
        cmd = [
            "ffmpeg",
            "-y",
            "-i",
            background_path_str,  # video procedurale
            "-i",
            str(audio_wav),       # audio voce
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
    else:
        # Fallback: immagine statica come prima
        cmd = [
            "ffmpeg",
            "-y",
            "-loop",
            "1",
            "-i",
            background_path_str,  # immagine di sfondo
            "-i",
            str(audio_wav),       # audio voce
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

    print("[Monday] Genero video base (background + voce) con ffmpeg...")
    print("[Monday] Comando:", " ".join(cmd))
    subprocess.run(cmd, check=True)

    return raw_video


def main() -> None:
    print("[Monday] Avvio upload automatico...")

    # 1) Script Deadpan Files + metadati YouTube
    # generate_script deve restituire: script_text, title, description, tags
    script_text, title, description, tags = generate_script()
    print("[Monday] Script generato (preview):", script_text[:120], "...")
    print("[Monday] Titolo scelto:", title)

    # 2) Audio + 3) background auto + 4) video base
    raw_video = _render_video(script_text)

    # 5) Sottotitoli bruciati (subtitles.txt viene generato in automatico da synth_voice)
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
