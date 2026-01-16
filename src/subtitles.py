from __future__ import annotations

import re
import shlex
import subprocess
from pathlib import Path
from typing import List


def _run(cmd: List[str]) -> None:
    p = subprocess.run(cmd, capture_output=True, text=True)
    if p.returncode != 0:
        raise RuntimeError(
            "FFmpeg failed:\n"
            f"CMD: {' '.join(shlex.quote(c) for c in cmd)}\n"
            f"STDOUT: {p.stdout}\n"
            f"STDERR: {p.stderr}"
        )


# ---------------------------------------------------------------------------
# COMPAT: questa funzione è importata da uploader.py
# (anche se oggi usiamo ASS, la teniamo per non rompere nulla)
# ---------------------------------------------------------------------------
def generate_subtitles_txt_from_text(raw_text: str, subtitles_txt_path: str | Path) -> Path:
    subtitles_txt_path = Path(subtitles_txt_path)
    subtitles_txt_path.parent.mkdir(parents=True, exist_ok=True)

    text = re.sub(r"\s+", " ", (raw_text or "").strip())
    if not text:
        text = "..."

    subtitles_txt_path.write_text(text, encoding="utf-8")
    return subtitles_txt_path


# ---------------------------------------------------------------------------
# BURN ASS DEFINITIVO (sottotitoli BRUCIATI nel video, non CC)
# ---------------------------------------------------------------------------
def _ass_filter_path(p: Path) -> str:
    """
    FFmpeg filter ass=... vuole un path "safe".
    - Su Linux: /home/... ok
    - Su Windows: C:\... va convertito e ':' va escapato
    """
    s = p.resolve().as_posix()
    # Escape del ":" del drive (C:) solo se presente
    if len(s) >= 2 and s[1] == ":":
        s = s.replace(":", r"\:")
    return s


def add_burned_in_subtitles(
    video_path: str | Path,
    subtitles_path: str | Path | None = None,
    subtitles_txt_path: str | Path | None = None,
    subtitles_ass_path: str | Path | None = None,
    output_dir: str | Path = "videos_to_upload",
    output_name: str = "video_final.mp4",
) -> Path:
    """
    Brucia sottotitoli ASS nel video e forza output 9:16 1080x1920.

    Retro-compat:
    - main vecchi chiamano subtitles_txt_path=
    - main nuovi chiamano subtitles_path=
    - alcuni possono chiamare subtitles_ass_path=
    """
    video_path = Path(video_path)

    # Scegliamo quale path usare (priorità: ASS esplicito -> subtitles_path -> subtitles_txt_path)
    chosen = subtitles_ass_path or subtitles_path or subtitles_txt_path
    if not chosen:
        raise ValueError("Missing subtitles path (use subtitles_path= or subtitles_txt_path= or subtitles_ass_path=)")

    subtitles_file = Path(chosen)

    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    out = output_dir / output_name

    ass_path = _escape_ass_path_for_filter(subtitles_file)

    vf = (
        "scale=1080:1920:force_original_aspect_ratio=decrease,"
        "pad=1080:1920:(ow-iw)/2:(oh-ih)/2,"
        "setsar=1,"
        f"ass='{ass_path}'"
    )

    cmd = [
        "ffmpeg", "-y",
        "-i", str(video_path),
        "-vf", vf,
        "-c:v", "libx264",
        "-preset", "veryfast",
        "-crf", "18",
        "-c:a", "aac",
        "-b:a", "128k",
        "-pix_fmt", "yuv420p",
        str(out),
    ]
    print("[Monday] ffmpeg burn subtitles:", " ".join(cmd))
    _run(cmd)
    return out
