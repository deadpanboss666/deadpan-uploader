# main.py — Monday
# Pipeline completa: script -> voce gTTS (per-frase) -> sfondo procedurale -> audio mix + loudnorm -> sottotitoli ASS -> upload

from __future__ import annotations

import hashlib
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
    BUILD_DIR.mkdir(parents=True, exist_ok=True)
    VIDEOS_DIR.mkdir(parents=True, exist_ok=True)


def _render_video(background_video: Path, voice_audio: Path, duration_s: float, seed: int) -> Path:
    """
    Merge voce + sfondo e migliora audio:
    - ambience horror generato (anoisesrc) sempre diverso (seed)
    - mix voce + ambience a basso volume
    - loudnorm per volume stabile (più pro)
    """
    _ensure_dirs()

    raw_video = VIDEOS_DIR / "video_base.mp4"

    # ambience procedurale: scegli "pink" o "brown" in modo deterministico
    ambience_color = "pink" if (seed % 2 == 0) else "brown"

    # Nota: anoisesrc è un generatore audio interno di ffmpeg (nessun file esterno/copyright)
    # Facciamo un’ambience leggera + echo minimo + filtri + volume basso.
    filter_complex = (
        # voce: un po' di compressione soft + loudnorm
        "[1:a]"
        "highpass=f=90,"
        "lowpass=f=8000,"
        "acompressor=threshold=-18dB:ratio=3:attack=15:release=140,"
        "alimiter=limit=0.95,"
        "volume=1.0"
        "[voice];"

        # ambience: noise -> filtri -> echo -> volume basso
        f"anoisesrc=d={duration_s:.3f}:c={ambience_color}:seed={seed}:r=48000,"
        "highpass=f=120,"
        "lowpass=f=1600,"
        "aecho=0.8:0.85:40:0.20,"
        "volume=0.055"
        "[amb];"

        # mix + loudnorm finale
        "[voice][amb]amix=inputs=2:duration=shortest:dropout_transition=0,"
        "loudnorm=I=-16:LRA=11:TP=-1.5"
        "[aout]"
    )

    cmd = [
        "ffmpeg",
        "-y",
        "-i", str(background_video),
        "-i", str(voice_audio),
        "-filter_complex", filter_complex,
        "-map", "0:v:0",
        "-map", "[aout]",
        "-c:v", "libx264",
        "-preset", "veryfast",
        "-crf", "18",
        "-c:a", "aac",
        "-b:a", "160k",
        "-shortest",
        "-pix_fmt", "yuv420p",
        str(raw_video),
    ]

    print("[Monday] Genero video base + audio mix (ambience + loudnorm)...")
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

    # Seed unico basato sul testo: aiuta a rendere il look/audio coerente ma diverso per ogni storia
    seed = int(hashlib.md5(script_text.encode("utf-8")).hexdigest()[:8], 16)
    print(f"[Monday] Seed stile video: {seed}")

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

    # 4) Sfondo procedurale (già variabile col seed)
    print("[Monday] Genero background procedurale...")
    bg_video = generate_procedural_background(duration_s, seed=seed)

    # 5) Video base (sfondo + voce + ambience + loudnorm)
    raw_video = _render_video(bg_video, voice_audio, duration_s=duration_s, seed=seed)

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
