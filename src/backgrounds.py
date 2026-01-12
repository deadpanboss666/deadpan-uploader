# backgrounds.py — Monday
# Generazione automatica di background verticali robusti per ffmpeg

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
# Palette e utility
# ---------------------------------------------------------------------------


def _to_ffmpeg_color(hex_color: str) -> str:
    """Converte '#1f2933' in '0x1f2933' per ffmpeg."""
    hex_color = hex_color.strip().lstrip("#")
    return f"0x{hex_color}"


def _random_palette() -> tuple[str, str]:
    """
    Ritorna (base_color, overlay_color) in esadecimale,
    scelti da una piccola palette dark / horror.
    """
    palettes = [
        ("#020617", "#0f172a"),
        ("#020617", "#1e293b"),
        ("#030712", "#111827"),
        ("#020617", "#450a0a"),
        ("#020617", "#1f2933"),
        ("#050816", "#4b1d3f"),
    ]
    base_hex, overlay_hex = random.choice(palettes)
    base = _to_ffmpeg_color(base_hex)
    overlay = _to_ffmpeg_color(overlay_hex)
    print(f"[Monday/backgrounds] Palette scelta: {base_hex} (base) -> {overlay_hex} (overlay)")
    return base, overlay


# ---------------------------------------------------------------------------
# Background procedurale (safe)
# ---------------------------------------------------------------------------


def generate_procedural_background(
    duration_s: float,
    output_path: str | Path | None = None,
) -> Path:
    """
    Genera un video 1080x1920 vertical, 30 fps, con:
      - colore di base scuro
      - fascia centrale semi-trasparente (drawbox) come overlay
    Se il filtro drawbox dovesse fallire sul runner, viene usato
    un fallback a colore pieno, così la pipeline non salta mai.
    """
    BUILD_DIR.mkdir(parents=True, exist_ok=True)

    if output_path is None:
        output_path = BUILD_DIR / "background.mp4"
    else:
        output_path = Path(output_path)

    base_color, overlay_color = _random_palette()

    # Filtro video "ricco": formato + drawbox centrale (per profondità)
    vf_filter = (
        "format=yuv420p,"
        f"drawbox=x=0:y=ih*0.15:w=iw:h=ih*0.7:color={overlay_color}@0.35:t=fill"
    )

    # Comando principale: sorgente lavfi "color"
    cmd_rich = [
        "ffmpeg",
        "-y",
        "-f",
        "lavfi",
        "-i",
        f"color=c={base_color}:s=1080x1920:r=30",
        "-vf",
        vf_filter,
        "-t",
        f"{duration_s:.2f}",
        str(output_path),
    ]

    print("[Monday/backgrounds] Genero sfondo procedurale (rich)...")
    print("[Monday/backgrounds] Comando:", " ".join(cmd_rich))

    try:
        subprocess.run(cmd_rich, check=True)
        print(f"[Monday/backgrounds] Sfondo generato (rich): {output_path}")
        return output_path
    except subprocess.CalledProcessError as e:  # noqa: BLE001
        print("[Monday/backgrounds] ERRORE nel filtro avanzato. Dettagli:")
        print(f"[Monday/backgrounds] {e}")
        print("[Monday/backgrounds] Fallback a colore pieno semplice.")

    # Fallback ultra-semplice: solo colore pieno, nessun filtro extra
    cmd_fallback = [
        "ffmpeg",
        "-y",
        "-f",
        "lavfi",
        "-i",
        f"color=c={base_color}:s=1080x1920:r=30",
        "-t",
        f"{duration_s:.2f}",
        str(output_path),
    ]

    print("[Monday/backgrounds] Comando fallback:", " ".join(cmd_fallback))
    subprocess.run(cmd_fallback, check=True)
    print(f"[Monday/backgrounds] Sfondo generato (fallback): {output_path}")
    return output_path
