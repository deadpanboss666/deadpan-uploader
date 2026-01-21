from __future__ import annotations

import os
import subprocess
from pathlib import Path


def _run(cmd: list[str]) -> None:
    p = subprocess.run(cmd, capture_output=True, text=True)
    if p.returncode != 0:
        raise RuntimeError(
            "FFmpeg failed:\n"
            f"CMD: {' '.join(cmd)}\n"
            f"STDOUT:\n{p.stdout}\n"
            f"STDERR:\n{p.stderr}\n"
        )


def generate_subtitles_txt_from_text(text: str, out_path: Path) -> Path:
    """
    Compat: alcune parti del progetto importano questa funzione.
    """
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(text.strip() + "\n", encoding="utf-8")
    return out_path


def _ffmpeg_escape_subtitles_path(p: Path) -> str:
    """
    IMPORTANTISSIMO per Windows:
    - usa forward slashes
    - escape della ':' del drive -> C:/... diventa C\\:/...
    - escape di eventuali apostrofi
    """
    s = p.resolve().as_posix()
    if len(s) >= 2 and s[1] == ":":
        s = s[0] + r"\:" + s[2:]
    s = s.replace("'", r"\'")
    return s


def _force_style_cinematic() -> str:
    # Off-white + box semi trasparente + outline più spesso + safe margins
    return (
        "FontName=DejaVu Sans,"
        "Fontsize=74,"
        "Bold=1,"
        "Outline=5,"
        "Shadow=2,"
        "BorderStyle=3,"
        "BackColour=&H7A000000,"
        "OutlineColour=&H00000000,"
        "PrimaryColour=&H00F2F2F2,"
        "Alignment=2,"
        "WrapStyle=2,"
        "MarginV=300,"
        "MarginL=80,"
        "MarginR=80"
    )


def _force_style_aggressive() -> str:
    # Stile “a tutta pagina” ma pulito:
    # - font gigante
    # - box più presente
    # - outline forte per leggibilità
    # - margini più stretti per occupare più area
    return (
        "FontName=DejaVu Sans,"
        "Fontsize=82,"
        "Bold=1,"
        "Outline=8,"
        "Shadow=2,"
        "BorderStyle=3,"
        "BackColour=&H8F000000,"   # box più scuro
        "OutlineColour=&H00000000,"
        "PrimaryColour=&H00FFFFFF,"
        "Alignment=2,"
        "WrapStyle=2,"
        "MarginV=260,"             # un po’ più su (safe area)
        "MarginL=55,"
        "MarginR=55"
    )


def _get_style_from_env() -> str:
    # SUB_STYLE=aggressive | cinematic
    style = (os.getenv("SUB_STYLE") or "cinematic").strip().lower()
    if style in {"aggressive", "big", "full"}:
        return _force_style_aggressive()
    return _force_style_cinematic()


def add_burned_in_subtitles(
    video_path: Path,
    subtitles_ass_path: Path | None = None,
    output_dir: Path | None = None,
    output_name: str = "video_final.mp4",
    # compat extra: alcuni pezzi potrebbero chiamarlo così
    subtitles_path: Path | None = None,
    subtitles_file: Path | None = None,
) -> Path:
    """
    Brucia i sottotitoli ASS con libass.

    Stile controllato da env:
      - SUB_STYLE=cinematic   (default)
      - SUB_STYLE=aggressive  (testo gigante “a tutta pagina”)
    """
    if output_dir is None:
        output_dir = video_path.parent

    subs_path = subtitles_ass_path or subtitles_path or subtitles_file
    if subs_path is None:
        raise ValueError("Missing subtitles path (subtitles_ass_path / subtitles_path / subtitles_file)")

    output_dir.mkdir(parents=True, exist_ok=True)
    out_path = output_dir / output_name

    subs = _ffmpeg_escape_subtitles_path(Path(subs_path))
    force_style = _get_style_from_env()

    vf = f"subtitles='{subs}':force_style='{force_style}'"

    _run([
        "ffmpeg", "-y",
        "-i", str(video_path),
        "-vf", vf,
        "-c:v", "libx264",
        "-preset", "veryfast",
        "-crf", "18",
        "-pix_fmt", "yuv420p",
        "-c:a", "aac",
        "-b:a", "128k",
        "-movflags", "+faststart",
        str(out_path),
    ])

    return out_path
