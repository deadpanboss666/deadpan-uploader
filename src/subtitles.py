from __future__ import annotations

import shlex
import subprocess
from pathlib import Path
from typing import List, Optional


def _run(cmd: List[str]) -> None:
    p = subprocess.run(cmd, capture_output=True, text=True)
    if p.returncode != 0:
        raise RuntimeError(
            "FFmpeg failed:\n"
            f"CMD: {' '.join(shlex.quote(c) for c in cmd)}\n"
            f"STDOUT: {p.stdout}\n"
            f"STDERR: {p.stderr}"
        )


def add_burned_in_subtitles(
    video_path: str | Path,
    subtitles_path: str | Path,
    output_dir: str | Path,
    output_name: str = "video_final.mp4",
) -> Path:
    """
    Brucia sottotitoli ASS nel video in modo *definitivo*:
    - force_style impone posizione/size/outline in SAFE AREA
    - evita tagli della UI Shorts (like/comment/share)
    """
    video_path = Path(video_path)
    subtitles_path = Path(subtitles_path)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    if not video_path.exists():
        raise FileNotFoundError(f"Video non trovato: {video_path}")
    if not subtitles_path.exists():
        raise FileNotFoundError(f"Sottotitoli non trovati: {subtitles_path}")

    out_path = output_dir / output_name

    # SAFE STYLE (Shorts):
    # Alignment=2 = bottom-center
    # MarginV alto = sposta su (safe area)
    # Fontsize moderato = niente tagli laterali/verticali
    # Outline/Shadow/BackColour = leggibilità pro
    force_style = (
        "FontName=DejaVu Sans,"
        "FontSize=52,"
        "PrimaryColour=&H00FFFFFF,"
        "OutlineColour=&H00000000,"
        "BackColour=&H90000000,"
        "Bold=1,"
        "BorderStyle=3,"
        "Outline=4,"
        "Shadow=1,"
        "Alignment=2,"
        "MarginL=90,"
        "MarginR=90,"
        "MarginV=520"
    )

    # IMPORTANTISSIMO:
    # usiamo subtitles= con force_style -> così anche se l'ASS è diverso,
    # la posizione rimane sempre corretta.
    vf = f"subtitles={subtitles_path.as_posix()}:force_style='{force_style}'"

    cmd = [
        "ffmpeg",
        "-y",
        "-i",
        str(video_path),
        "-vf",
        vf,
        "-c:v",
        "libx264",
        "-preset",
        "veryfast",
        "-crf",
        "18",
        "-c:a",
        "aac",
        "-b:a",
        "160k",
        "-pix_fmt",
        "yuv420p",
        str(out_path),
    ]
    _run(cmd)
    return out_path
