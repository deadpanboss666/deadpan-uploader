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
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(text.strip() + "\n", encoding="utf-8")
    return out_path


def _ffmpeg_escape_subtitles_path(p: Path) -> str:
    s = p.resolve().as_posix()
    if len(s) >= 2 and s[1] == ":":
        s = s[0] + r"\:" + s[2:]
    s = s.replace("'", r"\'")
    return s


def _force_style_cinematic() -> str:
    # Safe Shorts (molto leggibile) — ma ricordati: in ASS i Margin* possono essere per-dialogue.
    return (
        "FontName=DejaVu Sans,"
        "Fontsize=56,"
        "Bold=1,"
        "Outline=8,"
        "Shadow=2,"
        "BorderStyle=3,"
        "BackColour=&H90000000,"
        "OutlineColour=&H00000000,"
        "PrimaryColour=&H00FFFFFF,"
        "Alignment=2,"
        "WrapStyle=2,"
        "MarginV=720,"
        "MarginL=120,"
        "MarginR=120"
    )


def _force_style_aggressive() -> str:
    return (
        "FontName=DejaVu Sans,"
        "Fontsize=70,"
        "Bold=1,"
        "Outline=10,"
        "Shadow=2,"
        "BorderStyle=3,"
        "BackColour=&H95000000,"
        "OutlineColour=&H00000000,"
        "PrimaryColour=&H00FFFFFF,"
        "Alignment=2,"
        "WrapStyle=2,"
        "MarginV=760,"
        "MarginL=120,"
        "MarginR=120"
    )


def _get_style_from_env() -> str:
    style = (os.getenv("SUB_STYLE") or "cinematic").strip().lower()
    if style in {"aggressive", "big", "full"}:
        return _force_style_aggressive()
    return _force_style_cinematic()


def _wrap_text_every_n_words(text: str, n: int = 5) -> str:
    """
    Inserisce \\N ogni n parole se la riga è lunga.
    Se già contiene \\N, non tocca.
    Preserva override tags iniziali tipo "{\\an8}{\\bord6}".
    """
    if "\\N" in text:
        return text

    prefix = ""
    m = re.match(r"^(\{[^}]*\})+", text)
    if m:
        prefix = m.group(0)
        text = text[len(prefix):]

    words = text.split()
    if len(words) <= n:
        return prefix + text

    chunks = [" ".join(words[i:i + n]) for i in range(0, len(words), n)]
    return prefix + r"\N".join(chunks)


def _rewrite_ass(
    ass_path: Path,
    out_path: Path,
    n_words: int = 5,
    margin_l: int = 120,
    margin_r: int = 120,
    margin_v: int = 760,
) -> Path:
    """
    Riscrive il .ass:
    - wrap testo ogni n_words sulle righe Dialogue:
    - FORZA MarginL/MarginR/MarginV sulle righe Dialogue (anti-taglio definitivo)
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

        head = "Dialogue:"
        body = line[len(head):].lstrip()

        # Dialogue: Layer,Start,End,Style,Name,MarginL,MarginR,MarginV,Effect,Text
        parts = body.split(",", 9)
        if len(parts) < 10:
            new_lines.append(line)
            continue

        # campi pre: 0..8, testo: 9
        pre = parts[:9]
        txt = parts[9]

        # forza margini: indexes 5,6,7
        # pre = [Layer,Start,End,Style,Name,MarginL,MarginR,MarginV,Effect]
        if len(pre) >= 8:
            pre[5] = str(margin_l)
            pre[6] = str(margin_r)
            pre[7] = str(margin_v)

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
    subtitles_path: Path | None = None,
    subtitles_file: Path | None = None,
) -> Path:
    """
    Burn-in sottotitoli ASS con:
    - wrap ogni N parole (default 5)
    - margini Dialogue forzati (anti taglio)
    - stile forzato (force_style)
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

    try:
        n_words = int((os.getenv("SUB_WRAP_WORDS") or "5").strip())
    except Exception:
        n_words = 5
    if n_words < 2:
        n_words = 2

    # margini safe extra (Shorts UI)
    # puoi anche cambiare via env senza toccare codice
    def _env_int(name: str, default: int) -> int:
        try:
            return int((os.getenv(name) or str(default)).strip())
        except Exception:
            return default

    margin_l = _env_int("SUB_MARGIN_L", 140)
    margin_r = _env_int("SUB_MARGIN_R", 140)
    margin_v = _env_int("SUB_MARGIN_V", 860)  # molto alto -> più su

    wrapped_ass = output_dir / "subtitles_wrapped.ass"
    _rewrite_ass(
        subs_in,
        wrapped_ass,
        n_words=n_words,
        margin_l=margin_l,
        margin_r=margin_r,
        margin_v=margin_v,
    )

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
