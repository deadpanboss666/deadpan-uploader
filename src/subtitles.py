from __future__ import annotations

import re
import shlex
import subprocess
from pathlib import Path
from typing import List


def _run(cmd: List[str]) -> str:
    p = subprocess.run(cmd, capture_output=True, text=True)
    if p.returncode != 0:
        raise RuntimeError(
            "Command failed:\n"
            f"CMD: {' '.join(shlex.quote(c) for c in cmd)}\n"
            f"STDOUT: {p.stdout}\n"
            f"STDERR: {p.stderr}"
        )
    return p.stdout.strip()


def split_sentences_for_txt(text: str, max_chars: int = 90) -> List[str]:
    """
    Split semplice e robusto per subtitles.txt (fallback/legacy).
    - split su .!? principale
    - se troppo lungo spezza su virgole
    - fallback parole
    """
    t = re.sub(r"\s+", " ", (text or "")).strip()
    if not t:
        return []

    parts = re.split(r"(?<=[\.\!\?])\s+", t)
    parts = [p.strip() for p in parts if p.strip()]

    refined: List[str] = []
    for p in parts:
        if len(p) <= max_chars:
            refined.append(p)
            continue

        chunks = re.split(r"(?<=[,;:])\s+", p)
        buf = ""
        for c in chunks:
            c = c.strip()
            if not c:
                continue
            if not buf:
                buf = c
            elif len(buf) + 1 + len(c) <= max_chars:
                buf = f"{buf} {c}"
            else:
                refined.append(buf)
                buf = c
        if buf:
            refined.append(buf)

    out: List[str] = []
    for p in refined:
        if len(p) <= max_chars:
            out.append(p)
            continue

        words = p.split(" ")
        buf = ""
        for w in words:
            if not buf:
                buf = w
            elif len(buf) + 1 + len(w) <= max_chars:
                buf = f"{buf} {w}"
            else:
                out.append(buf)
                buf = w
        if buf:
            out.append(buf)

    return [x.strip() for x in out if x.strip()]


def generate_subtitles_txt_from_text(raw_text: str, subtitles_txt_path: str | Path) -> Path:
    """
    Legacy: crea un subtitles.txt "a righe" (usato ancora da uploader.py).
    Se ormai usi ASS, questo file può anche esistere solo come debug.
    """
    subtitles_txt_path = Path(subtitles_txt_path)
    subtitles_txt_path.parent.mkdir(parents=True, exist_ok=True)

    lines = split_sentences_for_txt(raw_text, max_chars=90)
    if not lines:
        lines = [(raw_text or "").strip()]

    subtitles_txt_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return subtitles_txt_path


def _escape_ass_path_for_filter(p: Path) -> str:
    """
    Escape path per ffmpeg filter ass='...'
    - usa path POSIX anche su Windows (C:/...)
    - escape ':' perché ffmpeg lo interpreta come separatore nelle opzioni
    - escape apici singoli
    """
    p = Path(p).resolve()
    s = p.as_posix()

    # ffmpeg filter parsing: ':' è speciale -> va escapato
    s = s.replace(":", r"\:")

    # dentro apici singoli in vf: ass='...'
    s = s.replace("'", r"\'")

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

    chosen = subtitles_ass_path or subtitles_path or subtitles_txt_path
    if not chosen:
        raise ValueError(
            "Missing subtitles path (use subtitles_path= or subtitles_txt_path= or subtitles_ass_path=)"
        )

    subtitles_file = Path(chosen)

    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    out = output_dir / output_name

    ass_path = _escape_ass_path_for_filter(subtitles_file)

    # FORCE 9:16 sicuro + burn ASS
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
