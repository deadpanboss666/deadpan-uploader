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
    IMPORTANTISSIMO:
    - usa forward slashes
    - escape della ':' del drive su Windows -> C:/... diventa C\\:/...
    - escape di eventuali apostrofi
    """
    s = p.resolve().as_posix()
    if len(s) >= 2 and s[1] == ":":
        s = s[0] + r"\:" + s[2:]
    s = s.replace("'", r"\'")
    return s


def _force_style_for_env() -> str:
    """
    Stile sottotitoli controllato da env SUB_STYLE:
    - aggressive: grande, centrato, box scuro (più views, “old school” ma premium)
    - cinematic: più sobrio, basso ma safe
    """
    style = (os.getenv("SUB_STYLE") or "cinematic").strip().lower()

    if style == "aggressive":
        # CENTRO schermo (Alignment=5) => niente overlay UI Shorts e zero tagli.
        # Box scuro + outline forte => leggibile su qualsiasi sfondo.
        return (
            "FontName=DejaVu Sans,"
            "Fontsize=82,"
            "Bold=1,"
            "Outline=6,"
            "Shadow=2,"
            "BorderStyle=3,"
            "BackColour=&HC8000000,"   # box scuro (più opaco)
            "OutlineColour=&H00000000,"
            "PrimaryColour=&H00F8F8F8,"  # bianco leggermente soft
            "Alignment=5,"             # middle-center
            "MarginV=0,"
            "MarginL=90,"
            "MarginR=90"
        )

    # cinematic (safe, senza tagli, più “pulito”)
    return (
        "FontName=DejaVu Sans,"
        "Fontsize=62,"
        "Bold=1,"
        "Outline=4,"
        "Shadow=1,"
        "BorderStyle=3,"
        "BackColour=&H90000000,"
        "OutlineColour=&H00000000,"
        "PrimaryColour=&H00FFFFFF,"
        "Alignment=2,"               # bottom-center
        "MarginV=240,"               # alza sopra la UI Shorts
        "MarginL=110,"
        "MarginR=110"
    )


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
    Brucia i sottotitoli ASS con filtro 'subtitles' (libass).
    Supporta SUB_STYLE=aggressive|cinematic.
    """
    if output_dir is None:
        output_dir = video_path.parent

    subs_path = subtitles_ass_path or subtitles_path or subtitles_file
    if subs_path is None:
        raise ValueError("Missing subtitles path (subtitles_ass_path / subtitles_path / subtitles_file)")

    output_dir.mkdir(parents=True, exist_ok=True)
    out_path = output_dir / output_name

    subs = _ffmpeg_escape_subtitles_path(Path(subs_path))
    force_style = _force_style_for_env()

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
        str(out_path),
    ])

    return out_path
