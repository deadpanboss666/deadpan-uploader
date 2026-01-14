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


def get_media_duration(path: Path) -> float:
    cmd = [
        "ffprobe", "-v", "error",
        "-show_entries", "format=duration",
        "-of", "default=nw=1:nk=1",
        str(path),
    ]
    p = subprocess.run(cmd, capture_output=True, text=True)
    if p.returncode != 0:
        raise RuntimeError(p.stderr)
    return float(p.stdout.strip())


def generate_procedural_background(
    duration_s: float,
    seed: Optional[int] = None,
    width: int = 1080,
    height: int = 1920,
    fps: int = 30,
) -> Path:
    """
    Sfondo shorts "premium" e SEMPRE diverso.
    4 stili random deterministici col seed:
      0) Mandelbrot fractal cinematic
      1) Cellular automata + grade
      2) Gradient + light leaks overlay
      3) Plasma + motion
    In tutti i casi: movimento (zoom/pan), grain, vignette.
    """
    BUILD_DIR.mkdir(parents=True, exist_ok=True)

    if seed is None:
        seed = random.randint(0, 2_000_000_000)
    rng = random.Random(seed)

    out_path = BUILD_DIR / f"bg_{seed:08x}.mp4"
    if out_path.exists():
        return out_path

    style = seed % 4

    crf = rng.choice([18, 19, 20])
    zoom_max = rng.uniform(1.12, 1.28)
    blur = rng.uniform(4.0, 10.0)
    grain = rng.randint(10, 22)

    # grading random (ma coerente)
    hue = rng.randint(-18, 18)
    sat = rng.uniform(1.05, 1.45)
    con = rng.uniform(1.08, 1.28)
    bri = rng.uniform(-0.06, 0.03)

    # motion (micro camera)
    motion_x = rng.randint(14, 30)
    motion_y = rng.randint(18, 36)

    def common_tail() -> str:
        return (
            f"noise=alls={grain}:allf=t+u,"
            f"gblur=sigma={blur:.2f},"
            f"eq=contrast={con:.3f}:brightness={bri:.3f}:saturation={sat:.3f},"
            f"hue=h={hue},"
            f"vignette,"
            f"zoompan="
            f"z='min({zoom_max:.3f},1.0+0.0011*on)':"
            f"x='iw/2-(iw/zoom/2)+sin(on/33)*{motion_x}':"
            f"y='ih/2-(ih/zoom/2)+cos(on/47)*{motion_y}':"
            f"d=1:s={width}x{height}:fps={fps},"
            f"format=yuv420p"
        )

    if style == 0:
        start = rng.uniform(0.25, 0.95)
        end = start * rng.uniform(0.20, 0.55)
        src = f"mandelbrot=s={width}x{height}:r={fps}:start_scale={start:.5f}:end_scale={end:.5f}:d={duration_s}"
        vf = common_tail()
        cmd = ["ffmpeg", "-y", "-f", "lavfi", "-i", src, "-vf", vf,
               "-c:v", "libx264", "-preset", "veryfast", "-crf", str(crf),
               "-pix_fmt", "yuv420p", str(out_path)]
        _run(cmd)
        return out_path

    if style == 1:
        rule = rng.randint(20, 230)
        src = f"cellauto=s={width}x{height}:r={fps}:rule={rule}:d={duration_s}"
        vf = common_tail()
        cmd = ["ffmpeg", "-y", "-f", "lavfi", "-i", src, "-vf", vf,
               "-c:v", "libx264", "-preset", "veryfast", "-crf", str(crf),
               "-pix_fmt", "yuv420p", str(out_path)]
        _run(cmd)
        return out_path

    if style == 2:
        col_a = rng.choice(["#070b10", "#09070f", "#071012", "#0b0b12"])
        col_b = rng.choice(["#2b0a3d", "#0a3d44", "#3d0a0a", "#1a2f5a", "#3a2a0a"])
        base = f"color=c={col_a}:s={width}x{height}:r={fps}:d={duration_s}"
        leak = f"color=c={col_b}:s={width}x{height}:r={fps}:d={duration_s}"

        # overlay + tail
        fc = f"[0:v][1:v]blend=all_mode=overlay:all_opacity=0.30,{common_tail()}"
        cmd = ["ffmpeg", "-y",
               "-f", "lavfi", "-i", base,
               "-f", "lavfi", "-i", leak,
               "-filter_complex", fc,
               "-c:v", "libx264", "-preset", "veryfast", "-crf", str(crf),
               "-pix_fmt", "yuv420p", str(out_path)]
        _run(cmd)
        return out_path

    # style 3: plasma
    src = f"plasma=s={width}x{height}:r={fps}:d={duration_s}"
    vf = common_tail()
    cmd = ["ffmpeg", "-y", "-f", "lavfi", "-i", src, "-vf", vf,
           "-c:v", "libx264", "-preset", "veryfast", "-crf", str(crf),
           "-pix_fmt", "yuv420p", str(out_path)]
    _run(cmd)
    return out_path
