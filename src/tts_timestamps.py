from __future__ import annotations

import re
import shlex
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import List, Tuple


@dataclass
class Segment:
    idx: int
    text: str
    start: float
    end: float


def _run(cmd: List[str]) -> str:
    p = subprocess.run(cmd, capture_output=True, text=True)
    if p.returncode != 0:
        raise RuntimeError(
            "Command failed:\n"
            f"CMD: {' '.join(shlex.quote(c) for c in cmd)}\n"
            f"STDOUT: {p.stdout}\n"
            f"STDERR: {p.stderr}"
        )
    return p.stdout.strip()


def split_sentences(text: str, max_chars: int = 78) -> List[str]:
    """
    Split "Shorts-ready":
    - frasi più corte (max_chars basso)
    - evita righe lunghe che YouTube taglia/impasta
    """
    t = re.sub(r"\s+", " ", text).strip()
    if not t:
        return []

    parts = re.split(r"(?<=[\.\!\?])\s+", t)
    parts = [p.strip() for p in parts if p.strip()]

    refined: List[str] = []
    for p in parts:
        if len(p) <= max_chars:
            refined.append(p)
            continue

        chunks = re.split(r"(?<=[,;:])\s+", p)
        buf = ""
        for c in chunks:
            c = c.strip()
            if not c:
                continue
            if not buf:
                buf = c
            elif len(buf) + 1 + len(c) <= max_chars:
                buf = f"{buf} {c}"
            else:
                refined.append(buf)
                buf = c
        if buf:
            refined.append(buf)

    out: List[str] = []
    for p in refined:
        if len(p) <= max_chars:
            out.append(p)
            continue

        words = p.split(" ")
        buf = ""
        for w in words:
            if not buf:
                buf = w
            elif len(buf) + 1 + len(w) <= max_chars:
                buf = f"{buf} {w}"
            else:
                out.append(buf)
                buf = w
        if buf:
            out.append(buf)

    return [x.strip() for x in out if x.strip()]


def ffprobe_duration_seconds(media_path: Path) -> float:
    out = _run([
        "ffprobe", "-v", "error",
        "-show_entries", "format=duration",
        "-of", "default=nw=1:nk=1",
        str(media_path),
    ])
    return float(out)


def concat_audio_mp3(inputs: List[Path], output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    lst = output.parent / "concat_list.txt"

    with lst.open("w", encoding="utf-8") as f:
        for p in inputs:
            f.write(f"file '{p.as_posix()}'\n")

    _run([
        "ffmpeg", "-y",
        "-f", "concat", "-safe", "0",
        "-i", str(lst),
        "-c", "copy",
        str(output),
    ])

    try:
        lst.unlink(missing_ok=True)
    except Exception:
        pass


def build_segments_from_phrase_audio(
    phrases: List[str],
    phrase_audio_paths: List[Path],
    gap_seconds: float = 0.06
) -> List[Segment]:
    if len(phrases) != len(phrase_audio_paths):
        raise ValueError("phrases and phrase_audio_paths must have same length")

    t = 0.0
    segs: List[Segment] = []
    for i, (txt, ap) in enumerate(zip(phrases, phrase_audio_paths)):
        d = ffprobe_duration_seconds(ap)
        start = t
        end = t + d
        segs.append(Segment(idx=i, text=txt, start=start, end=end))
        t = end + gap_seconds
    return segs


def escape_ass(text: str) -> str:
    t = text.replace("{", r"\{").replace("}", r"\}")
    t = re.sub(r"\s+", " ", t).strip()
    return t


def write_ass_subtitles(
    segments: List[Segment],
    out_path: Path,
    width: int = 1080,
    height: int = 1920,
    font_name: str = "DejaVu Sans",
    font_size: int = 54,
) -> None:
    """
    ASS Shorts "pro":
    - posizionamento FORZATO in lower-third safe (non taglia mai con UI YouTube)
    - box semi-trasparente + outline nero
    - max 2 righe bilanciate
    """
    out_path.parent.mkdir(parents=True, exist_ok=True)

    # posizione safe: centro X, Y nel lower-third ma sopra la UI
    pos_x = width // 2
    pos_y = 1500  # <<< QUI è il punto chiave: alza tutto, sempre visibile

    def ts(sec: float) -> str:
        if sec < 0:
            sec = 0
        h = int(sec // 3600)
        m = int((sec % 3600) // 60)
        s = int(sec % 60)
        cs = int(round((sec - int(sec)) * 100))
        if cs == 100:
            cs = 0
            s += 1
        return f"{h}:{m:02d}:{s:02d}.{cs:02d}"

    primary = "&H00FFFFFF"   # bianco
    outline = "&H00000000"   # nero
    back = "&H90000000"      # box nero semi-trasparente

    header = f"""[Script Info]
ScriptType: v4.00+
PlayResX: {width}
PlayResY: {height}
ScaledBorderAndShadow: yes
WrapStyle: 2

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,{font_name},{font_size},{primary},{primary},{outline},{back},1,0,0,0,100,100,0,0,3,3.2,1.2,5,10,10,10,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""

    lines = [header]

    for seg in segments:
        start = ts(seg.start)
        end = ts(seg.end)

        txt = escape_ass(seg.text)

        # 2 righe bilanciate
        if len(txt) > 52 and " " in txt:
            words = txt.split(" ")
            mid = len(words) // 2
            best_i = mid
            best_score = 10**9
            for i in range(max(1, mid - 5), min(len(words) - 1, mid + 6)):
                a = " ".join(words[:i])
                b = " ".join(words[i:])
                score = abs(len(a) - len(b))
                if score < best_score:
                    best_score = score
                    best_i = i
            txt = " ".join(words[:best_i]) + r"\N" + " ".join(words[best_i:])

        # FORZA posizione + fade + micro-pop
        # \an5 = anchor center, \pos(x,y) = posizione fissa
        effect = (
            fr"{{\an5\pos({pos_x},{pos_y})\fad(120,120)\fscx112\fscy112\t(0,140,\fscx100\fscy100)}}"
            + txt
        )
        lines.append(f"Dialogue: 0,{start},{end},Default,,0,0,0,,{effect}\n")

    out_path.write_text("".join(lines), encoding="utf-8")


def generate_gtts_phrase_audio(
    phrases: List[str],
    out_dir: Path,
    lang: str = "en",
    tld: str = "com",
) -> List[Path]:
    from gtts import gTTS

    out_dir.mkdir(parents=True, exist_ok=True)
    paths: List[Path] = []
    for i, txt in enumerate(phrases):
        p = out_dir / f"phrase_{i:03d}.mp3"
        gTTS(text=txt, lang=lang, tld=tld, slow=False).save(str(p))
        paths.append(p)
    return paths


def build_voice_and_subs_from_text(
    story_text: str,
    work_dir: Path,
    lang: str = "en",
    tld: str = "com",
) -> Tuple[Path, Path, List[Segment]]:
    phrases = split_sentences(story_text)
    phrase_dir = work_dir / "phrases"
    voice_path = work_dir / "voice.mp3"
    subs_path = work_dir / "subtitles.ass"

    phrase_audio = generate_gtts_phrase_audio(phrases, phrase_dir, lang=lang, tld=tld)
    concat_audio_mp3(phrase_audio, voice_path)
    segments = build_segments_from_phrase_audio(phrases, phrase_audio, gap_seconds=0.06)
    write_ass_subtitles(segments, subs_path)

    return voice_path, subs_path, segments
