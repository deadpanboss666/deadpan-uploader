from __future__ import annotations

import shlex
import subprocess
from pathlib import Path
from typing import List


def _run(cmd: List[str]) -> None:
    p = subprocess.run(cmd, capture_output=True, text=True)
    if p.returncode != 0:
        raise RuntimeError(
            "ffmpeg failed:\n"
            f"CMD: {' '.join(shlex.quote(c) for c in cmd)}\n"
            f"STDOUT: {p.stdout}\n"
            f"STDERR: {p.stderr}"
        )


def _ffprobe_duration_seconds(video_path: Path) -> float:
    cmd = [
        "ffprobe", "-v", "error",
        "-show_entries", "format=duration",
        "-of", "default=nw=1:nk=1",
        str(video_path),
    ]
    p = subprocess.run(cmd, capture_output=True, text=True)
    if p.returncode != 0:
        raise RuntimeError(p.stderr)
    return float(p.stdout.strip())


def generate_subtitles_txt_from_text(raw_text: str, subtitles_txt_path: Path) -> None:
    """
    Backward-compat: crea un file .txt "grezzo".
    (Non è più usato dalla pipeline nuova, ma lo lasciamo per compatibilità.)
    """
    subtitles_txt_path.parent.mkdir(parents=True, exist_ok=True)
    subtitles_txt_path.write_text(raw_text.strip() + "\n", encoding="utf-8")


def _txt_to_simple_srt(txt_path: Path, srt_path: Path, total_duration: float) -> None:
    """
    Convertitore minimale: divide il testo in righe e spalma sul totale.
    Serve solo se qualcuno passa ancora .txt.
    """
    text = txt_path.read_text(encoding="utf-8").strip()
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    if not lines:
        lines = [text] if text else [""]

    n = len(lines)
    chunk = max(total_duration / max(n, 1), 0.5)

    def srt_ts(sec: float) -> str:
        if sec < 0:
            sec = 0
        h = int(sec // 3600)
        m = int((sec % 3600) // 60)
        s = int(sec % 60)
        ms = int(round((sec - int(sec)) * 1000))
        if ms == 1000:
            ms = 0
            s += 1
        return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"

    out: List[str] = []
    t = 0.0
    for i, ln in enumerate(lines, start=1):
        start = t
        end = min(t + chunk, total_duration)
        out.append(str(i))
        out.append(f"{srt_ts(start)} --> {srt_ts(end)}")
        out.append(ln)
        out.append("")
        t = end

    srt_path.write_text("\n".join(out), encoding="utf-8")


def add_burned_in_subtitles(
    video_path: Path,
    subtitles_path: Path,
    output_dir: Path,
) -> Path:
    """
    Brucia sottotitoli nel video.
    Supporta:
    - .ass (consigliato, stile premium)
    - .srt
    - .txt (fallback -> convertito in .srt semplice)
    """
    output_dir.mkdir(parents=True, exist_ok=True)

    ext = subtitles_path.suffix.lower()
    if ext == ".txt":
        total = _ffprobe_duration_seconds(video_path)
        srt_path = output_dir / "subtitles_autogen.srt"
        _txt_to_simple_srt(subtitles_path, srt_path, total_duration=total)
        subtitles_path = srt_path
        ext = ".srt"

    final_video = output_dir / "video_final.mp4"

    # Filter: usa libass (ASS o SRT)
    # Per ASS: ass=...
    # Per SRT: subtitles=... con force_style (così è leggibile)
    if ext == ".ass":
        vf = f"ass={subtitles_path.as_posix()}"
    else:
        # stile leggibile tipo Shorts anche su SRT
        force_style = (
            "FontName=DejaVu Sans,"
            "FontSize=62,"
            "PrimaryColour=&H00FFFFFF,"
            "OutlineColour=&H00000000,"
            "BackColour=&H90000000,"
            "Bold=1,"
            "Outline=3,"
            "Shadow=1,"
            "MarginV=150,"
            "MarginL=90,"
            "MarginR=90"
        )
        vf = f"subtitles={subtitles_path.as_posix()}:force_style='{force_style}'"

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
        str(final_video),
    ]
    print("[Monday] ffmpeg burn subtitles:", " ".join(cmd))
    _run(cmd)

    return final_video
