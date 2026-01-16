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
    subtitles_txt_path: str | Path,   # lo lasciamo per compat firma, ma usiamo ASS se è .ass
    output_dir: str | Path,
    output_name: str = "video_final.mp4",
) -> Path:
    """
    Se subtitles_txt_path punta a .ass -> burn con ass=
    Se punta a .txt/.srt -> prova comunque con subtitles= (fallback)
    In ogni caso FORZIAMO 1080x1920 + setsar=1 (Shorts)
    """
    video_path = Path(video_path)
    subs_path = Path(subtitles_txt_path)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    out = output_dir / output_name

    # Forza formato verticale sempre
    base = (
        "scale=1080:1920:force_original_aspect_ratio=decrease,"
        "pad=1080:1920:(ow-iw)/2:(oh-ih)/2,"
        "setsar=1"
    )

    if subs_path.suffix.lower() == ".ass":
        subs_filter = f"ass='{_ass_filter_path(subs_path)}'"
    else:
        # fallback (non ideale, ma non deve mai crashare)
        subs_filter = f"subtitles='{_ass_filter_path(subs_path)}'"

    vf = f"{base},{subs_filter}"

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
