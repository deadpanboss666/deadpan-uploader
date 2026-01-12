# backgrounds.py — Monday
# Utility per durate media e generazione background procedurale 9:16

from __future__ import annotations

import random
import subprocess
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
ROOT_DIR = BASE_DIR.parent
ASSETS_DIR = ROOT_DIR / "assets"


def get_media_duration(path: str | Path) -> float:
    """Restituisce la durata di un file audio/video in secondi usando ffprobe.

    In caso di problemi ritorna 30.0s così la pipeline non esplode.
    """
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
        out = subprocess.check_output(cmd, stderr=subprocess.STDOUT)
        duration_str = out.decode().strip()
        duration = float(duration_str)
        print(f"[Monday][bg] Durata media rilevata: {duration:.2f}s")
        return duration
    except Exception as e:  # noqa: BLE001
        print(f"[Monday][bg] Impossibile leggere durata con ffprobe ({path}): {e}")
        print("[Monday][bg] Uso durata di fallback: 30s.")
        return 30.0


def _pick_background_image() -> Path | None:
    """Cerca un'immagine di sfondo in assets/ (background*.jpg/png ecc.).

    Ritorna il Path oppure None se non trova nulla.
    """
    if not ASSETS_DIR.exists():
        return None

    candidates = list(ASSETS_DIR.glob("*.jpg")) + list(
        ASSETS_DIR.glob("*.jpeg")
    ) + list(ASSETS_DIR.glob("*.png"))

    if not candidates:
        return None

    # Scelta casuale per dare un po' di varietà
    img = random.choice(candidates)
    print(f"[Monday][bg] Uso immagine di sfondo: {img}")
    return img


def generate_procedural_background(
    duration_seconds: float,
    output_path: str | Path,
    width: int = 1080,
    height: int = 1920,
    fps: int = 30,
) -> str | None:
    """Genera un background video 9:16 con una leggera animazione di zoom/pan.

    - Se trova una o più immagini in assets/, usa una di quelle con effetto Ken Burns.
    - Se non trova nulla, genera un semplice background colorato.

    Ritorna la stringa del percorso del video generato, oppure None se fallisce.
    """
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Durata minima di sicurezza
    if duration_seconds <= 0:
        duration_seconds = 30.0

    bg_image = _pick_background_image()

    try:
        if bg_image is not None:
            # Effetto Ken Burns (zoom lento) sull'immagine scelta
            zoom_filter = (
                "zoompan="
                "z='min(zoom+0.0015,1.25)':"
                "x='iw/2-(iw/zoom/2)':"
                "y='ih/2-(ih/zoom/2)',"
                f"scale={width}:{height},"
                "format=yuv420p"
            )

            cmd = [
                "ffmpeg",
                "-y",
                "-loop",
                "1",
                "-i",
                str(bg_image),
                "-vf",
                zoom_filter,
                "-t",
                f"{duration_seconds:.3f}",
                "-r",
                str(fps),
                "-an",
                str(output_path),
            ]
            print("[Monday][bg] Genero background procedurale da immagine...")
        else:
            # Sorgente sintetica: semplice colore (garantito che funzioni ovunque)
            color = random.choice(
                ["#05070b", "#080017", "#101820", "#111111", "#1a0b24"]
            )
            cmd = [
                "ffmpeg",
                "-y",
                "-f",
                "lavfi",
                "-i",
                f"color=c={color}:s={width}x{height}:d={duration_seconds:.3f}",
                "-vf",
                "format=yuv420p",
                "-r",
                str(fps),
                "-an",
                str(output_path),
            ]
            print(f"[Monday][bg] Genero background procedurale di colore {color}...")

        print("[Monday][bg] Comando background:", " ".join(cmd))
        subprocess.run(cmd, check=True)
        print(f"[Monday][bg] Background generato: {output_path}")
        return str(output_path)
    except subprocess.CalledProcessError as e:  # noqa: BLE001
        print("[Monday][bg] ERRORE durante la generazione del background.")
        print(f"[Monday][bg] Dettagli: {e}")
        return None
