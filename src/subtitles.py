from __future__ import annotations

import os
import re
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
    # Safe per Shorts: molto su + box scuro + outline forte
    return (
        "FontName=DejaVu Sans,"
        "Fontsize=58,"
        "Bold=1,"
        "Outline=7,"
        "Shadow=2,"
        "BorderStyle=3,"
        "BackColour=&H8F000000,"
        "OutlineColour=&H00000000,"
        "PrimaryColour=&H00FFFFFF,"
        "Alignment=2,"
        "WrapStyle=2,"
        "MarginV=520,"
        "MarginL=120,"
        "MarginR=120"
    )


def _force_style_aggressive() -> str:
    # Grande ma safe (no tagli), box presente
    return (
        "FontName=DejaVu Sans,"
        "Fontsize=74,"
        "Bold=1,"
        "Outline=10,"
        "Shadow=2,"
        "BorderStyle=3,"
        "BackColour=&H95000000,"
        "OutlineColour=&H00000000,"
        "PrimaryColour=&H00FFFFFF,"
        "Alignment=2,"
        "WrapStyle=2,"
        "MarginV=560,"
        "MarginL=120,"
        "MarginR=120"
    )


def _get_style_from_env() -> str:
    # SUB_STYLE=aggressive | cinematic
    style = (os.getenv("SUB_STYLE") or "cinematic").strip().lower()
    if style in {"aggressive", "big", "full"}:
        return _force_style_aggressive()
    return _force_style_cinematic()


def _wrap_text_every_n_words(text: str, n: int = 5) -> str:
    """
    Inserisce \N (a capo ASS) ogni n parole SE la riga è più lunga di n parole.
    Se contiene già \N, non tocca.
    Preserva eventuali override tags iniziali tipo: "{\\an8}{\\bord6}..."
    """
    if "\\N" in text:
        return text

    # prendi override tags iniziali (uno o più blocchi {...})
    prefix = ""
    m = re.match(r"^(\{[^}]*\})+", text)
    if m:
        prefix = m.group(0)
        text = text[len(prefix):]

    words = text.split()
    if len(words) <= n:
        return prefix + text

    chunks = [" ".join(words[i:i+n]) for i in range(0, len(words), n)]
    return prefix + r"\N".join(chunks)


def _rewrite_ass_with_wrapping(ass_path: Path, out_path: Path, n_words: int = 5) -> Path:
    """
    Riscrive un .ass facendo wrap ogni n_words sulle righe Dialogue:
    - parse robusto: split sui primi 9 campi (fino a Effect), il resto è Text.
    """
    ass_path = Path(ass_path)
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    lines = ass_path.read_text(encoding="utf-8", errors="ignore").splitlines()
    new_lines: list[str] = []

    for line in lines:
        if not line.startswith("Dialogue:"):
            new_lines.append(line)
            continue

        # Dialogue: Layer,Start,End,Style,Name,MarginL,MarginR,MarginV,Effect,Text
        head = "Dialogue:"
        body = line[len(head):].lstrip()

        # split in 10 pezzi: 9 virgole + il testo finale (resto)
        parts = body.split(",", 9)
        if len(parts) < 10:
            # formato strano, non tocchiamo
            new_lines.append(line)
            continue

        pre = parts[:9]
        txt = parts[9]
        txt_wrapped = _wrap_text_every_n_words(txt, n=n_words)
        rebuilt = head + " " + ",".join(pre + [txt_wrapped])
        new_lines.append(rebuilt)

    out_path.write_text("\n".join(new_lines) + "\n", encoding="utf-8")
    return out_path


def add_burned_in_subtitles(
    video_path: Path,
    subtitles_ass_path: Path | None = None,
    output_dir: Path | None = None,
    output_name: str = "video_final.mp4",
    # compat extra
    subtitles_path: Path | None = None,
    subtitles_file: Path | None = None,
) -> Path:
    """
    Brucia i sottotitoli ASS con libass, e forza wrap ogni 5 parole se la riga è lunga.

    Controlli:
      - SUB_STYLE=cinematic|aggressive
      - SUB_WRAP_WORDS=5 (puoi cambiare il numero se vuoi)
    """
    if output_dir is None:
        output_dir = video_path.parent

    subs_path = subtitles_ass_path or subtitles_path or subtitles_file
    if subs_path is None:
        raise ValueError("Missing subtitles path (subtitles_ass_path / subtitles_path / subtitles_file)")

    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    out_path = output_dir / output_name

    subs_in = Path(subs_path)

    # wrap words (default 5)
    try:
        n_words = int((os.getenv("SUB_WRAP_WORDS") or "5").strip())
    except Exception:
        n_words = 5
    if n_words < 2:
        n_words = 2

    # crea una copia wrap-compat nella stessa cartella output
    wrapped_ass = output_dir / "subtitles_wrapped.ass"
    _rewrite_ass_with_wrapping(subs_in, wrapped_ass, n_words=n_words)

    subs = _ffmpeg_escape_subtitles_path(wrapped_ass)
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
