# backgrounds.py — Monday
# Generazione automatica di background verticali procedurali con ffmpeg

from __future__ import annotations

import random
import subprocess
from pathlib import Path

# Cartelle principali (stessa logica di main.py)
BASE_DIR = Path(__file__).resolve().parent
ROOT_DIR = BASE_DIR.parent
BUILD_DIR = ROOT_DIR / "build"


# ---------------------------------------------------------------------------
# Lettura durata media con ffprobe
# ---------------------------------------------------------------------------


def get_media_duration(path: str | Path) -> float:
    """
    Ritorna la durata (in secondi) di un file audio/video usando ffprobe.
    Se qualcosa va storto, usa un fallback di 25 secondi.
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
        duration = float(out.decode().strip())
        print(f"[Monday/backgrounds] Durata media rilevata: {duration:.2f}s")
        return duration
    except Exception as e:  # noqa: BLE001
        print(f"[Monday/backgrounds] Impossibile leggere durata con ffprobe: {e}")
        print("[Monday/backgrounds] Uso durata di fallback: 25s.")
        return 25.0


# ---------------------------------------------------------------------------
# Background procedurale
# ---------------------------------------------------------------------------


def _random_background_params() -> dict:
    """
    Genera un set di parametri random per rendere ogni background diverso
    ma sempre coerente con l'estetica dark / horror.
    """
    seed = random.randint(0, 999_999)

    params = {
        "noise_strength": random.randint(10, 18),
        "contrast": round(random.uniform(1.2, 1.6), 2),
        "brightness": round(random.uniform(-0.10, 0.03), 2),
        "saturation": round(random.uniform(0.6, 1.0), 2),
        "vignette": round(random.uniform(0.6, 0.9), 2),
        "seed": seed,
    }

    print(
        "[Monday/backgrounds] Parametri sfondo -> "
        f"noise={params['noise_strength']}, "
        f"contrast={params['contrast']}, "
        f"brightness={params['brightness']}, "
        f"saturation={params['saturation']}, "
        f"vignette={params['vignette']}, "
        f"seed={params['seed']}"
    )
    return params


def generate_procedural_background(
    duration_s: float,
    output_path: str | Path | None = None,
) -> Path:
    """
    Genera un video 1080x1920 vertical, 30 fps, con:
      - base nera
      - noise animato
      - correzione colore (eq)
      - vignetta

    Tutti i parametri principali sono randomizzati ad ogni run per
    ottenere variazioni automatiche tra uno short e l'altro.
    """
    BUILD_DIR.mkdir(parents=True, exist_ok=True)

    if output_path is None:
        output_path = BUILD_DIR / "background.mp4"
    else:
        output_path = Path(output_path)

    params = _random_background_params()

    # Filtro video: formato, noise animato, eq, vignetta
    vf_filter = (
        "format=yuv420p,"
        f"noise=alls={params['noise_strength']}:allf=t+u:seed={params['seed']},"
        f"eq=contrast={params['contrast']}:brightness={params['brightness']}:"
        f"saturation={params['saturation']},"
        f"vignette=PI/4:{params['vignette']}"
    )

    # Input: sorgente lavfi "color" (base nera)
    # NOTA: niente filtro 'gradient' perché non è garantito su tutti i build ffmpeg.
    cmd = [
        "ffmpeg",
        "-y",
        "-f",
        "lavfi",
        "-i",
        "color=c=black:s=1080x1920:r=30",
        "-vf",
        vf_filter,
        "-t",
        f"{duration_s:.2f}",
        str(output_path),
    ]

    print("[Monday/backgrounds] Genero sfondo procedurale...")
    print("[Monday/backgrounds] Comando:", " ".join(cmd))

    try:
        subprocess.run(cmd, check=True)
    except subprocess.CalledProcessError as e:  # noqa: BLE001
        print("[Monday/backgrounds] ERRORE durante la generazione dello sfondo procedurale.")
        print(f"[Monday/backgrounds] Dettagli: {e}")
        raise

    print(f"[Monday/backgrounds] Sfondo generato: {output_path}")
    return output_path
