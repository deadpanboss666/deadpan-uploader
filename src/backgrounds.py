from __future__ import annotations

import os
import shlex
import subprocess
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parent.parent
BUILD_DIR = ROOT_DIR / "build"


def _run(cmd: list[str]) -> str:
    p = subprocess.run(cmd, capture_output=True, text=True)
    if p.returncode != 0:
        raise RuntimeError(
            "FFmpeg failed:\n"
            f"CMD: {' '.join(shlex.quote(c) for c in cmd)}\n"
            f"STDOUT:\n{p.stdout}\n"
            f"STDERR:\n{p.stderr}\n"
        )
    return p.stdout.strip()


def get_media_duration(path: Path) -> float:
    out = _run([
        "ffprobe", "-v", "error",
        "-show_entries", "format=duration",
        "-of", "default=nw=1:nk=1",
        str(path),
    ])
    return float(out)


def _rand_hex_color(seed: int) -> str:
    # Dark cinematic colors, but NOT pure black.
    r = (seed * 1103515245 + 12345) & 0xFFFFFFFF
    a = (r >> 16) & 255
    b = (r >> 8) & 255
    c = (r >> 0) & 255

    rr = 35 + (a % 90)  # 35..124 (a bit brighter than before)
    gg = 35 + (b % 90)
    bb = 35 + (c % 90)

    return f"#{rr:02x}{gg:02x}{bb:02x}"


def generate_procedural_background(
    duration_s: float,
    seed: int | None = None,
    width: int = 1080,
    height: int = 1920,
    fps: int = 30,
) -> Path:
    """
    Procedural cinematic background video (MP4):
    - non-black base color
    - texture (noise) + blur
    - gentle contrast/sat + tiny brightness
    - vignette + slow motion (zoompan)
    """
    BUILD_DIR.mkdir(parents=True, exist_ok=True)

    if seed is None:
        seed = int.from_bytes(os.urandom(4), "little")

    out_path = BUILD_DIR / f"bg_{seed}.mp4"
    base = _rand_hex_color(seed)

    vf = (
        "noise=alls=18:allf=t+u,"
        "gblur=sigma=8,"
        "eq=contrast=1.20:brightness=0.03:saturation=1.30,"
        f"hue=h={(seed % 40) - 20},"
        "vignette,"
        "zoompan=z='min(1.14,1.0+0.0012*on)':"
        "x='iw/2-(iw/zoom/2)+sin(on/29)*24':"
        "y='ih/2-(ih/zoom/2)+cos(on/37)*20':"
        f"d=1:s={width}x{height}:fps={fps},"
        "format=yuv420p"
    )

    _run([
        "ffmpeg", "-y",
        "-f", "lavfi",
        "-i", f"color=c={base}:s={width}x{height}:r={fps}:d={duration_s}",
        "-vf", vf,
        "-c:v", "libx264",
        "-preset", "veryfast",
        "-crf", "18",
        "-pix_fmt", "yuv420p",
        str(out_path),
    ])

    return out_path


def extract_background_frame(
    background_video: Path,
    out_png: Path | None = None,
    t: float = 0.5,
) -> Path:
    """
    Optional helper:
    Extract a PNG frame from a generated background video.
    Useful if some pipeline step expects an image.
    """
    background_video = Path(background_video)
    if out_png is None:
        out_png = background_video.with_suffix(".png")

    _run([
        "ffmpeg", "-y",
        "-ss", str(t),
        "-i", str(background_video),
        "-frames:v", "1",
        "-vf", "format=rgb24",
        str(out_png),
    ])
    return out_png
