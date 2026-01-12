# backgrounds.py — Monday (safe color-only version)
# Generazione automatica di sfondi video procedurali (solo color lavfi)

from __future__ import annotations

import random
import subprocess
from pathlib import Path

DEFAULT_FPS = 30
DEFAULT_RESOLUTION = "1080x1920"  # verticale per Shorts


def _run_ffprobe_duration(path: Path) -> float:
    """Usa ffprobe per leggere la durata di un media in secondi."""
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
    """Restituisce la durata del media, con fallback in caso di errore."""
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


def generate_procedural_background(
    duration: float,
    output_path: str | Path,
    fps: int = DEFAULT_FPS,
    resolution: str = DEFAULT_RESOLUTION,
) -> Path:
    """Genera un video di sfondo usando solo la sorgente 'color' di ffmpeg.

    Niente filtri complessi: massima compatibilità su GitHub Actions.
    Il colore viene scelto in modo pseudo-random da una palette dark.
    """
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Clamp durata (min 3s, max 60s)
    duration = max(3.0, min(duration, 60.0))

    # Palette di colori scuri (in stile horror / noir)
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

    # Sorgente lavfi: color
    # Usiamo solo 'format=yuv420p' per compatibilità con i player.
    filter_chain = "format=yuv420p"

    cmd = [
        "ffmpeg",
        "-y",
        "-f",
        "lavfi",
        "-i",
        f"color=c={color}:s={resolution}:r={fps}",
        "-vf",
        filter_chain,
        "-t",
        f"{duration:.2f}",
        str(output_path),
    ]

    print("[Monday/backgrounds] Genero sfondo procedurale (solo color)...")
    print("[Monday/backgrounds] Comando:", " ".join(cmd))
    subprocess.run(cmd, check=True)
    print(f"[Monday/backgrounds] Sfondo creato: {output_path}")

    return output_path
