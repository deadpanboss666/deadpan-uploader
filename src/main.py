from __future__ import annotations

import hashlib
import os
import subprocess
from pathlib import Path

from uploader import generate_script, upload_video
from backgrounds import get_media_duration, generate_procedural_background
from subtitles import add_burned_in_subtitles
from tts_timestamps import build_voice_and_subs_from_text


BASE_DIR = Path(__file__).resolve().parent
ROOT_DIR = BASE_DIR.parent
BUILD_DIR = ROOT_DIR / "build"
VIDEOS_DIR = ROOT_DIR / "videos_to_upload"


def _ensure_dirs() -> None:
    BUILD_DIR.mkdir(parents=True, exist_ok=True)
    VIDEOS_DIR.mkdir(parents=True, exist_ok=True)


def _truthy_env(name: str, default: str = "0") -> bool:
    raw = os.getenv(name, default)
    v = str(raw).strip().lower()
    return v in {"1", "true", "yes", "y", "on"}


def _merge_bg_and_audio(bg_video: Path, voice_audio: Path, out_path: Path) -> None:
    """
    Merge video + audio con audio più "pro" (voce centrata, volume stabile).
    """
    cmd = [
        "ffmpeg",
        "-y",
        "-i", str(bg_video),
        "-i", str(voice_audio),
        "-filter:a", "loudnorm=I=-16:LRA=11:TP=-1.5",
        "-c:v", "libx264",
        "-preset", "veryfast",
        "-crf", "18",
        "-c:a", "aac",
        "-b:a", "160k",
        "-shortest",
        "-pix_fmt", "yuv420p",
        str(out_path),
    ]
    subprocess.run(cmd, check=True)


def main() -> None:
    print("[Monday] Avvio pipeline Deadpan...")

    _ensure_dirs()

    # Upload toggle (per prove: tienilo a 1, ok)
    do_upload = _truthy_env("UPLOAD_YT", default="0")
    print(f"[Monday] UPLOAD_YT={os.getenv('UPLOAD_YT')} -> do_upload={do_upload}")

    # 1) Story + metadata
    script_text, title, description, tags = generate_script()
    print("[Monday] Titolo:", title)

    # seed deterministico per variazioni forti
    seed = int(hashlib.md5(script_text.encode("utf-8")).hexdigest()[:8], 16)

    # 2) Voce + ASS sync reale
    voice_audio, subtitles_ass, _ = build_voice_and_subs_from_text(
        story_text=script_text,
        work_dir=BUILD_DIR,
        lang="en",
        tld="com",
    )

    # 3) Background dinamico
    duration_s = get_media_duration(voice_audio)
    duration_s = min(max(duration_s, 15.0), 60.0)
    bg_video = generate_procedural_background(duration_s=duration_s, seed=seed)

    # 4) Merge base
    base_video = VIDEOS_DIR / "video_base.mp4"
    _merge_bg_and_audio(bg_video, voice_audio, base_video)

    # 5) Burn subtitles (SAFE DEFINITIVO)
    final_video = add_burned_in_subtitles(
        video_path=base_video,
        subtitles_path=subtitles_ass,
        output_dir=VIDEOS_DIR,
        output_name="video_final.mp4",
    )
    print("[Monday] Video finale:", final_video)

    # 6) Upload (se attivo)
    if do_upload:
        upload_video(
            video_path=final_video,
            title=title,
            description=description,
            tags=tags,
        )
    else:
        print("[Monday] Upload disattivato: generato solo output locale/Actions.")


if __name__ == "__main__":
    main()
