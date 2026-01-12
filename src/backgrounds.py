# backgrounds.py — Monday
# Generazione procedurale di sfondi video verticali 1080x1920

from __future__ import annotations

import random
import subprocess
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent
BUILD_DIR = BASE_DIR.parent / "build"


def get_media_duration(path: str | Path) -> float:
    """Legge la durata di un file audio/video in secondi usando ffprobe."""
    path = Path(path)
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
    try:
        result = subprocess.check_output(cmd, stderr=subprocess.STDOUT)
        return float(result.decode().strip())
    except Exception as e:  # noqa: BLE001
        print(f"[Monday/backgrounds] Impossibile leggere durata media: {e}")
        return 30.0


def _random_palette() -> tuple[str, str]:
    """Ritorna una coppia di colori (hex) per gradienti."""
    palettes = [
        ("#020617", "#0f172a"),  # blu notte
        ("#030712", "#111827"),  # grigio scuro
        ("#020617", "#1e293b"),  # blu + slate
        ("#000000", "#1f2933"),  # nero + blu fumo
        ("#02010f", "#170312"),  # viola scuro
    ]
    return random.choice(palettes)


def _hex_to_rgb(hex_color: str) -> tuple[int, int, int]:
    hex_color = hex_color.lstrip("#")
    return tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))  # type: ignore[return-value]


def generate_procedural_background(duration_s: float) -> Path:
    """
    Genera uno sfondo verticale 1080x1920 animato:
    - gradiente verticale di 2 colori
    - leggero noise/grain
    - vignettatura e leggera variazione di contrasto/brightness

    Ritorna il path del video MP4 generato.
    """
    BUILD_DIR.mkdir(parents=True, exist_ok=True)
    output_video = BUILD_DIR / "background.mp4"

    # Colori random
    c1_hex, c2_hex = _random_palette()
    c1 = _hex_to_rgb(c1_hex)
    c2 = _hex_to_rgb(c2_hex)

    print(f"[Monday/backgrounds] Palette scelta: {c1_hex} -> {c2_hex}")

    # Parametri random leggeri per rendere ogni sfondo diverso
    seed = random.randint(0, 999999)
    eq_contrast = round(random.uniform(1.2, 1.6), 2)
    eq_brightness = round(random.uniform(-0.1, 0.1), 2)
    vignette = round(random.uniform(0.4, 0.7), 2)

    # Filtri ffmpeg:
    # 1) gradient: disegna un gradiente verticale 1080x1920
    # 2) noise: aggiunge grana
    # 3) eq: contrasto/luminosità
    # 4) vignette: bordi più scuri
    filter_complex = (
        f"gradient=size=1080x1920:direction=vertical:"
        f"colors={c1[0]}x{c1[1]}x{c1[2]}-{c2[0]}x{c2[1]}x{c2[2]},"
        f"noise=alls=15:allf=t+u:seed={seed},"
        f"format=yuv420p,"
        f"eq=contrast={eq_contrast}:brightness={eq_brightness},"
        f"vignette=PI/4:{vignette}"
    )

    cmd = [
        "ffmpeg",
        "-y",
        "-f",
        "lavfi",
        "-i",
        "color=c=black:s=1080x1920:r=30",  # dummy input, non usato ma comodo
        "-vf",
        filter_complex,
        "-t",
        f"{duration_s:.2f}",
        str(output_video),
    ]

    print("[Monday/backgrounds] Genero sfondo procedurale...")
    print("[Monday/backgrounds] Comando:", " ".join(cmd))

    subprocess.run(cmd, check=True)

    print(f"[Monday/backgrounds] Sfondo creato: {output_video}")
    return output_video
