from __future__ import annotations

import random
import shlex
import subprocess
from pathlib import Path
from typing import List, Optional, Tuple


# Percorsi
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
    """Durata media (audio o video) via ffprobe."""
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


def _hex_color(rgb: Tuple[int, int, int]) -> str:
    return "#{:02X}{:02X}{:02X}".format(*rgb)


def generate_procedural_background(
    duration_s: float,
    seed: Optional[int] = None,
    width: int = 1080,
    height: int = 1920,
    fps: int = 30,
) -> Path:
    """
    Genera uno sfondo verticale "premium" SEMPRE diverso:
    - palette casuale (seed deterministico opzionale)
    - grain/noise + blur soft
    - vignetta
    - movimento lento (zoom/pan)

    Restituisce un file mp4 in build/.
    """
    BUILD_DIR.mkdir(parents=True, exist_ok=True)

    # Se seed non fornito, usa random "vero"
    if seed is None:
        seed = random.randint(0, 2_000_000_000)

    rng = random.Random(seed)

    out_path = BUILD_DIR / f"bg_{seed:08x}.mp4"
    if out_path.exists():
        return out_path

    palettes: List[Tuple[Tuple[int, int, int], Tuple[int, int, int]]] = [
        ((10, 10, 14), (40, 10, 60)),     # dark purple
        ((6, 18, 24), (10, 60, 70)),      # teal noir
        ((12, 12, 12), (60, 20, 20)),     # dark crimson
        ((8, 10, 22), (30, 40, 90)),      # night blue
        ((14, 8, 10), (80, 40, 20)),      # ember
        ((10, 12, 14), (40, 50, 55)),     # steel
        ((6, 6, 8), (25, 25, 35)),        # graphite
        ((5, 10, 8), (20, 55, 35)),       # moss noir
    ]
    c1, c2 = rng.choice(palettes)
    col1 = _hex_color(c1)
    col2 = _hex_color(c2)

    noise_strength = rng.randint(10, 26)
    blur_sigma = rng.uniform(6.0, 14.0)
    sat = rng.uniform(0.85, 1.25)
    con = rng.uniform(1.03, 1.18)
    bri = rng.uniform(-0.05, 0.03)
    hue_shift = rng.randint(-8, 8)

    zoom_max = rng.uniform(1.06, 1.14)
    wobble_x = rng.uniform(10.0, 35.0)
    wobble_y = rng.uniform(10.0, 45.0)
    wobble_fx = rng.uniform(28.0, 55.0)
    wobble_fy = rng.uniform(32.0, 65.0)

    box_alpha = rng.uniform(0.06, 0.14)
    box_count = rng.randint(2, 5)

    drawboxes = []
    for _ in range(box_count):
        bw = rng.randint(int(width * 0.25), int(width * 0.70))
        bh = rng.randint(int(height * 0.12), int(height * 0.35))
        bx = rng.randint(-int(width * 0.10), int(width * 0.40))
        by = rng.randint(-int(height * 0.05), int(height * 0.60))
        drawboxes.append(
            f"drawbox=x={bx}:y={by}:w={bw}:h={bh}:color={col2}@{box_alpha:.3f}:t=fill"
        )
    drawbox_chain = ",".join(drawboxes) if drawboxes else "null"

    vf = (
        f"format=rgba,"
        f"noise=alls={noise_strength}:allf=t+u,"
        f"gblur=sigma={blur_sigma:.2f},"
        f"{drawbox_chain},"
        f"eq=contrast={con:.3f}:brightness={bri:.3f}:saturation={sat:.3f},"
        f"hue=h={hue_shift},"
        f"vignette,"
        f"zoompan="
        f"z='min({zoom_max:.3f},1.0+0.0009*on)':"
        f"x='iw/2-(iw/zoom/2)+sin(on/{wobble_fx:.2f})*{wobble_x:.2f}':"
        f"y='ih/2-(ih/zoom/2)+cos(on/{wobble_fy:.2f})*{wobble_y:.2f}':"
        f"d=1:s={width}x{height}:fps={fps},"
        f"format=yuv420p"
    )

    cmd = [
        "ffmpeg", "-y",
        "-f", "lavfi", "-i", f"color=c={col1}:s={width}x{height}:r={fps}:d={duration_s}",
        "-f", "lavfi", "-i", f"color=c={col2}:s={width}x{height}:r={fps}:d={duration_s}",
        "-filter_complex",
        f"[0:v][1:v]blend=all_mode=overlay:all_opacity=0.35, {vf}",
        "-c:v", "libx264",
        "-preset", "veryfast",
        "-crf", "20",
        "-pix_fmt", "yuv420p",
        str(out_path),
    ]

    print(f"[Monday] Background seed={seed} palette={col1}/{col2}")
    _run(cmd)

    return out_path
