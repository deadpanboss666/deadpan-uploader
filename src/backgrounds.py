from __future__ import annotations

import random
import shlex
import subprocess
from pathlib import Path
from typing import List, Optional


BASE_DIR = Path(__file__).resolve().parent
ROOT_DIR = BASE_DIR.parent
BUILD_DIR = ROOT_DIR / "build"


def _run(cmd: List[str]) -> None:
    p = subprocess.run(cmd, capture_output=True, text=True)
    if p.returncode != 0:
        raise RuntimeError(
            "FFmpeg failed:\n"
            f"CMD: {' '.join(shlex.quote(c) for c in cmd)}\n"
            f"STDOUT: {p.stdout}\n"
            f"STDERR: {p.stderr}"
        )


def get_media_duration(media_path: Path) -> float:
    cmd = [
        "ffprobe", "-v", "error",
        "-show_entries", "format=duration",
        "-of", "default=nw=1:nk=1",
        str(media_path),
    ]
    p = subprocess.run(cmd, capture_output=True, text=True)
    if p.returncode != 0:
        raise RuntimeError(p.stderr)
    return float(p.stdout.strip())


def _style_filter(seed: int) -> str:
    # variazioni
    hue_amp = 6 + (seed % 7)            # 6..12
    sat = 1.25 + ((seed % 35) / 100)    # 1.25..1.60
    con = 1.12 + ((seed % 25) / 100)    # 1.12..1.37
    bri = -0.06 + ((seed % 9) / 100)    # -0.06..+0.02
    noise = 10 + (seed % 14)            # 10..23
    blur = 3.5 + ((seed % 20) / 10)     # 3.5..5.4

    sx = 28 + (seed % 23)
    sy = 31 + (seed % 27)
    z = 1.07 + ((seed % 10) / 100)      # 1.07..1.16

    look = seed % 5

    if look == 0:
        grade = (
            f"eq=contrast={con:.3f}:brightness={bri:.3f}:saturation={sat:.3f},"
            "colorchannelmixer=rr=1.05:rg=0.02:rb=0.02:gr=0.00:gg=0.98:gb=0.02:br=0.00:bg=0.02:bb=0.92"
        )
    elif look == 1:
        grade = (
            f"eq=contrast={con:.3f}:brightness={bri:.3f}:saturation={sat:.3f},"
            "colorchannelmixer=rr=0.90:rg=0.02:rb=0.00:gr=0.00:gg=0.98:gb=0.02:br=0.00:bg=0.05:bb=1.08"
        )
    elif look == 2:
        grade = (
            f"eq=contrast={con:.3f}:brightness={bri:.3f}:saturation={sat:.3f},"
            "colorchannelmixer=rr=1.10:rg=0.02:rb=0.00:gr=0.00:gg=0.96:gb=0.02:br=0.00:bg=0.02:bb=0.90"
        )
    elif look == 3:
        grade = (
            f"eq=contrast={con:.3f}:brightness={bri:.3f}:saturation={sat:.3f},"
            "colorchannelmixer=rr=0.92:rg=0.05:rb=0.00:gr=0.00:gg=1.05:gb=0.00:br=0.00:bg=0.05:bb=0.92"
        )
    else:
        grade = (
            f"eq=contrast={con:.3f}:brightness={bri:.3f}:saturation=1.10,"
            "colorchannelmixer=rr=0.98:rg=0.01:rb=0.01:gr=0.01:gg=0.98:gb=0.01:br=0.01:bg=0.01:bb=0.98"
        )

    hue = f"hue=h='{hue_amp}*sin(2*PI*t/11)'"

    vf = (
        f"noise=alls={noise}:allf=t+u,"
        f"gblur=sigma={blur:.2f},"
        f"{grade},"
        f"{hue},"
        "vignette=PI/5,"
        "unsharp=5:5:0.60:5:5:0.00,"
        f"zoompan=z='min({z:.3f},1.0+0.00075*on)':"
        f"x='iw/2-(iw/zoom/2)+sin(on/{sx})*30':"
        f"y='ih/2-(ih/zoom/2)+cos(on/{sy})*22':"
        "d=1:fps=30,"
        "format=yuv420p"
    )
    return vf


def generate_procedural_background(duration_s: float, seed: Optional[int] = None) -> Path:
    BUILD_DIR.mkdir(parents=True, exist_ok=True)

    if seed is None:
        seed = random.randint(100_000, 999_999)

    out = BUILD_DIR / f"bg_{seed}.mp4"
    vf = _style_filter(seed)

    cmd = [
        "ffmpeg", "-y",
        "-f", "lavfi",
        "-i", f"color=c=black:s=1080x1920:r=30:d={duration_s:.3f}",
        "-vf", vf,
        "-c:v", "libx264",
        "-preset", "veryfast",
        "-crf", "18",
        "-pix_fmt", "yuv420p",
        str(out),
    ]
    _run(cmd)
    print(f"[Monday/backgrounds] Background generato: {out}")
    return out
