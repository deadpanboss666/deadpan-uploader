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
            "Command failed:\n"
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
    Sfondo cinematico, SEMPRE diverso:
    - STYLE 0: Fractal (mandelbrot) + blur + vignette + grain
    - STYLE 1: Cellular automata + color grade + motion
    - STYLE 2: Gradient/noise cinematic + light-leaks + motion
    """
    BUILD_DIR.mkdir(parents=True, exist_ok=True)

    if seed is None:
        seed = random.randint(0, 2_000_000_000)
    rng = random.Random(seed)

    out_path = BUILD_DIR / f"bg_{seed:08x}.mp4"
    if out_path.exists():
        return out_path

    style = seed % 3

    # parametri random (ma deterministici col seed)
    crf = rng.choice([18, 19, 20])
    zoom_max = rng.uniform(1.10, 1.22)
    blur = rng.uniform(6.0, 14.0)
    grain = rng.randint(10, 22)
    hue = rng.randint(-12, 12)
    sat = rng.uniform(0.95, 1.35)
    con = rng.uniform(1.05, 1.22)
    bri = rng.uniform(-0.05, 0.03)

    if style == 0:
        # Mandelbrot animato (fractal), molto più "premium" di un colore fisso
        start = rng.uniform(0.20, 0.90)
        end = start * rng.uniform(0.20, 0.55)

        src = (
            f"mandelbrot=s={width}x{height}:r={fps}:"
            f"start_scale={start:.5f}:end_scale={end:.5f}"
        )

        vf = (
            f"noise=alls={grain}:allf=t+u,"
            f"gblur=sigma={blur:.2f},"
            f"eq=contrast={con:.3f}:brightness={bri:.3f}:saturation={sat:.3f},"
            f"hue=h={hue},"
            f"vignette,"
            f"zoompan="
            f"z='min({zoom_max:.3f},1.0+0.0010*on)':"
            f"x='iw/2-(iw/zoom/2)+sin(on/40)*18':"
            f"y='ih/2-(ih/zoom/2)+cos(on/55)*26':"
            f"d=1:s={width}x{height}:fps={fps},"
            f"format=yuv420p"
        )

        cmd = [
            "ffmpeg", "-y",
            "-f", "lavfi", "-i", f"{src}:d={duration_s}",
            "-vf", vf,
            "-c:v", "libx264",
            "-preset", "veryfast",
            "-crf", str(crf),
            "-pix_fmt", "yuv420p",
            str(out_path),
        ]
        _run(cmd)
        return out_path

    if style == 1:
        # Cellular automata (pattern vivo) -> grade -> motion
        rule = rng.randint(20, 200)
        src = f"cellauto=s={width}x{height}:r={fps}:rule={rule}"

        vf = (
            f"noise=alls={grain}:allf=t+u,"
            f"gblur=sigma={blur:.2f},"
            f"eq=contrast={con:.3f}:brightness={bri:.3f}:saturation={sat:.3f},"
            f"hue=h={hue},"
            f"vignette,"
            f"zoompan="
            f"z='min({zoom_max:.3f},1.0+0.0011*on)':"
            f"x='iw/2-(iw/zoom/2)+sin(on/33)*24':"
            f"y='ih/2-(ih/zoom/2)+cos(on/47)*34':"
            f"d=1:s={width}x{height}:fps={fps},"
            f"format=yuv420p"
        )

        cmd = [
            "ffmpeg", "-y",
            "-f", "lavfi", "-i", f"{src}:d={duration_s}",
            "-vf", vf,
            "-c:v", "libx264",
            "-preset", "veryfast",
            "-crf", str(crf),
            "-pix_fmt", "yuv420p",
            str(out_path),
        ]
        _run(cmd)
        return out_path

    # style 2: gradient + noise + light leak (overlay) + motion
    # due layer: base gradient + overlay "light leak" animato
    col_a = rng.choice(["#0b0b12", "#07131a", "#12070b", "#061011"])
    col_b = rng.choice(["#2b0a3d", "#0a3d44", "#3d0a0a", "#1a2f5a", "#3a2a0a"])

    base = f"color=c={col_a}:s={width}x{height}:r={fps}:d={duration_s}"
    leak = f"color=c={col_b}:s={width}x{height}:r={fps}:d={duration_s}"

    vf = (
        # blend + gradient motion simulato con zoompan, poi grade/grain
        f"[0:v][1:v]blend=all_mode=overlay:all_opacity=0.28,"
        f"noise=alls={grain}:allf=t+u,"
        f"gblur=sigma={blur:.2f},"
        f"eq=contrast={con:.3f}:brightness={bri:.3f}:saturation={sat:.3f},"
        f"hue=h={hue},"
        f"vignette,"
        f"zoompan="
        f"z='min({zoom_max:.3f},1.0+0.0010*on)':"
        f"x='iw/2-(iw/zoom/2)+sin(on/29)*22':"
        f"y='ih/2-(ih/zoom/2)+cos(on/41)*30':"
        f"d=1:s={width}x{height}:fps={fps},"
        f"format=yuv420p"
    )

    cmd = [
        "ffmpeg", "-y",
        "-f", "lavfi", "-i", base,
        "-f", "lavfi", "-i", leak,
        "-filter_complex", vf,
        "-c:v", "libx264",
        "-preset", "veryfast",
        "-crf", str(crf),
        "-pix_fmt", "yuv420p",
        str(out_path),
    ]
    _run(cmd)
    return out_path
