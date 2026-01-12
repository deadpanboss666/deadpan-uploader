# backgrounds.py — Monday
# Sfondi procedurali automatici:
# - tenta prima uno sfondo animato (zoom lento + blur)
# - se ffmpeg fallisce, usa uno sfondo statico sicuro

from __future__ import annotations

import random
import subprocess
from pathlib import Path

DEFAULT_FPS = 30
DEFAULT_RESOLUTION = "1080x1920"  # verticale per Shorts


# --------------------------------------------------------------------
# Durata media (serve per agganciare la lunghezza della voce)
# --------------------------------------------------------------------
def _run_ffprobe_duration(path: Path) -> float:
    cmd = [
        "ffprobe",
        "-v",
        "error",
        "-show_entries",
        "format=duration",
        "-of",
        "default=nokey=1:noprint_wrappers=1",
        str(path),
    ]
    result = subprocess.check_output(cmd, stderr=subprocess.STDOUT)
    return float(result.decode().strip())


def get_media_duration(media_path: str | Path, fallback: float = 30.0) -> float:
    media_path = Path(media_path)

    try:
        duration = _run_ffprobe_duration(media_path)
        print(f"[Monday/backgrounds] Durata media rilevata: {duration:.2f}s")
        return duration
    except Exception as e:  # noqa: BLE001
        print(
            "[Monday/backgrounds] Impossibile leggere la durata con ffprobe "
            f"({e}). Uso fallback {fallback}s."
        )
        return fallback


# --------------------------------------------------------------------
# Sfondo procedurale
# --------------------------------------------------------------------
def _choose_dark_color() -> str:
    """Palette di colori scuri in stile horror / true crime."""
    dark_palette = [
        "#050314",
        "#020617",
        "#0b1120",
        "#111827",
        "#1f2933",
        "#17141f",
        "#140b0b",
        "#101318",
    ]
    color = random.choice(dark_palette)
    print(f"[Monday/backgrounds] Colore scelto per lo sfondo: {color}")
    return color


def _generate_animated_background(
    duration: float,
    output_path: Path,
    fps: int,
    resolution: str,
    color: str,
) -> None:
    """Prova a creare uno sfondo ANIMATO (zoom lento + blur).
    Se qualcosa va storto, solleva CalledProcessError e il chiamante
    farà il fallback allo sfondo statico.
    """
    # zoompan: zoom lento verso il centro
    vf_expr = (
        f"zoompan=z='min(1.2,zoom+0.0004)':"
        f"x='iw/2-(iw/zoom)/2':"
        f"y='ih/2-(ih/zoom)/2':"
        f"d=1:fps={fps},"
        "boxblur=2:2,"
        "format=yuv420p"
    )

    cmd = [
        "ffmpeg",
        "-y",
        "-f",
        "lavfi",
        "-i",
        f"color=c={color}:s={resolution}:r={fps}",
        "-vf",
        vf_expr,
        "-t",
        f"{duration:.2f}",
        str(output_path),
    ]

    print("[Monday/backgrounds] Provo sfondo ANIMATO...")
    print("[Monday/backgrounds] Comando:", " ".join(cmd))
    subprocess.run(cmd, check=True)
    print("[Monday/backgrounds] Sfondo animato creato con successo.")


def _generate_static_background(
    duration: float,
    output_path: Path,
    fps: int,
    resolution: str,
    color: str,
) -> None:
    """Versione di fallback: colore piatto, ma sicuro al 100%."""
    cmd = [
        "ffmpeg",
        "-y",
        "-f",
        "lavfi",
        "-i",
        f"color=c={color}:s={resolution}:r={fps}",
        "-vf",
        "format=yuv420p",
        "-t",
        f"{duration:.2f}",
        str(output_path),
    ]

    print("[Monday/backgrounds] Uso sfondo STATICO di fallback...")
    print("[Monday/backgrounds] Comando:", " ".join(cmd))
    subprocess.run(cmd, check=True)
    print("[Monday/backgrounds] Sfondo statico creato.")


def generate_procedural_background(
    duration: float,
    output_path: str | Path,
    fps: int = DEFAULT_FPS,
    resolution: str = DEFAULT_RESOLUTION,
) -> Path:
    """Genera automaticamente uno sfondo:
    - colore diverso ad ogni short
    - prima prova animato
    - se fallisce, fallback statico
    """
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Clamp durata (3–60s)
    duration = max(3.0, min(duration, 60.0))

    color = _choose_dark_color()

    try:
        _generate_animated_background(duration, output_path, fps, resolution, color)
    except subprocess.CalledProcessError as e:
        print("[Monday/backgrounds] Errore sfondo animato:", e)
        print("[Monday/backgrounds] Faccio fallback allo sfondo statico...")
        _generate_static_background(duration, output_path, fps, resolution, color)

    return output_path
