# backgrounds.py — Monday (safe version)
# Generazione automatica di sfondi video procedurali (nessuna immagine fissa)

from __future__ import annotations

import random
import subprocess
from pathlib import Path

DEFAULT_FPS = 30
DEFAULT_RESOLUTION = "1080x1920"  # 9:16 verticale per Shorts


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
    duration_str = result.decode().strip()
    return float(duration_str)


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
    """Genera un video di sfondo procedurale (noise / grain noir).

    Versione compatibile con ffmpeg su GitHub Actions:
    - sorgente: color nero
    - filtro: noise animato + eq (contrasto) desaturato
    """
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Clamp della durata (min 3s, max 60s)
    duration = max(3.0, min(duration, 60.0))

    # Parametri random per variare il look
    seed = random.randint(0, 999_999)
    grain_strength = random.choice([15, 20, 25])
    contrast = round(random.uniform(1.15, 1.55), 2)
    brightness = round(random.uniform(-0.08, 0.03), 2)

    # Catena di filtri ffmpeg semplificata:
    # - noise: grana in movimento con seed random
    # - format: yuv420p per compatibilità
    # - eq: contrasto + leggera variazione di luminosità, desaturato
    filter_chain = (
        f"noise=alls={grain_strength}:allf=t:seed={seed},"
        "format=yuv420p,"
        f"eq=contrast={contrast}:brightness={brightness}:saturation=0.0"
    )

    cmd = [
        "ffmpeg",
        "-y",
        "-f",
        "lavfi",
        "-i",
        f"color=c=black:s={resolution}:r={fps}",
        "-vf",
        filter_chain,
        "-t",
        f"{duration:.2f}",
        str(output_path),
    ]

    print("[Monday/backgrounds] Genero sfondo procedurale...")
    print("[Monday/backgrounds] Comando:", " ".join(cmd))
    subprocess.run(cmd, check=True)
    print(f"[Monday/backgrounds] Sfondo creato: {output_path}")

    return output_path
