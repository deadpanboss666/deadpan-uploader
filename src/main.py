from __future__ import annotations

import os
import re
import shlex
import subprocess
import inspect
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

# Local modules
import backgrounds
import subtitles

ROOT = Path(__file__).resolve().parent.parent
VIDEOS_DIR = ROOT / "videos_to_upload"
BUILD_DIR = ROOT / "build"

DEFAULT_W = 1080
DEFAULT_H = 1920
DEFAULT_FPS = 30


def _run(cmd: list[str]) -> str:
    """Run a command and return stdout, raise with nice error on failure."""
    p = subprocess.run(cmd, capture_output=True, text=True)
    if p.returncode != 0:
        raise RuntimeError(
            "[Monday] Command failed\n"
            f"CMD: {' '.join(shlex.quote(c) for c in cmd)}\n"
            f"STDOUT:\n{p.stdout}\n"
            f"STDERR:\n{p.stderr}\n"
        )
    return p.stdout.strip()


def _ffprobe_duration(path: Path) -> float:
    out = _run([
        "ffprobe", "-v", "error",
        "-show_entries", "format=duration",
        "-of", "default=nw=1:nk=1",
        str(path),
    ])
    try:
        return float(out)
    except Exception:
        raise RuntimeError(f"[Monday] ffprobe duration parse failed for {path}: {out!r}")


def _ffprobe_has_audio(path: Path) -> bool:
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-select_streams", "a", "-show_entries", "stream=codec_type",
         "-of", "default=nw=1:nk=1", str(path)],
        capture_output=True, text=True
    )
    return out.returncode == 0 and "audio" in (out.stdout or "").lower()


def _sanitize_title(s: str) -> str:
    s = re.sub(r"\s+", " ", s).strip()
    # Remove weird control chars
    s = "".join(ch for ch in s if ch.isprintable())
    return s


def _pick_audio_file() -> Path:
    """
    Prefer an explicit voice file (fully automatic pipeline should create this).
    Fallback: try to extract from a video in videos_to_upload.
    """
    candidates = [
        VIDEOS_DIR / "voice.mp3",
        VIDEOS_DIR / "voice.wav",
        VIDEOS_DIR / "audio.mp3",
        VIDEOS_DIR / "audio.wav",
    ]
    for c in candidates:
        if c.exists() and c.stat().st_size > 0:
            return c

    # fallback: extract from a video file if present
    for vname in ["video.mp4", "input.mp4", "source.mp4"]:
        v = VIDEOS_DIR / vname
        if v.exists() and v.stat().st_size > 0 and _ffprobe_has_audio(v):
            BUILD_DIR.mkdir(parents=True, exist_ok=True)
            out_wav = BUILD_DIR / "voice_extracted.wav"
            _run([
                "ffmpeg", "-y",
                "-i", str(v),
                "-vn",
                "-ac", "1",
                "-ar", "48000",
                "-c:a", "pcm_s16le",
                str(out_wav),
            ])
            return out_wav

    raise FileNotFoundError(
        "[Monday] Audio non trovato.\n"
        "Metti un file qui: videos_to_upload/voice.mp3 (consigliato) oppure voice.wav.\n"
        "In alternativa, videos_to_upload/video.mp4 deve contenere una traccia audio valida."
    )


def _read_video_info() -> tuple[str, str]:
    """
    Optional: videos_to_upload/video-info.txt
    First line = title, remaining = description.
    """
    p = VIDEOS_DIR / "video-info.txt"
    if not p.exists():
        return ("", "")
    txt = p.read_text(encoding="utf-8", errors="ignore").strip()
    if not txt:
        return ("", "")
    lines = [l.strip() for l in txt.splitlines() if l.strip()]
    if not lines:
        return ("", "")
    title = lines[0]
    desc = "\n".join(lines[1:]).strip()
    return (title, desc)


def _wrap_every_n_words(text: str, n: int) -> str:
    """
    Insert newline every n words (for better fitting inside 9:16).
    """
    words = [w for w in re.split(r"\s+", text.strip()) if w]
    if not words:
        return ""
    if n <= 0:
        return " ".join(words)
    lines = []
    for i in range(0, len(words), n):
        lines.append(" ".join(words[i:i + n]))
    return "\\N".join(lines)  # ASS newline


@dataclass
class AssLine:
    start: float
    end: float
    text: str


def _sec_to_ass_time(t: float) -> str:
    if t < 0:
        t = 0
    h = int(t // 3600)
    m = int((t % 3600) // 60)
    s = t % 60
    cs = int(round((s - int(s)) * 100))
    return f"{h:d}:{m:02d}:{int(s):02d}.{cs:02d}"


def _build_ass(lines: list[AssLine], out_path: Path, style: str = "cinematic") -> Path:
    """
    Create a simple ASS file compatible with ffmpeg libass.
    """
    out_path.parent.mkdir(parents=True, exist_ok=True)

    # Safe default: bottom, centered, big, readable.
    # Use large margins so it never gets cut.
    if style == "aggressive":
        font_size = 78
        margin_v = 220
        outline = 5
    else:
        font_size = 62
        margin_v = 210
        outline = 4

    ass = []
    ass.append("[Script Info]")
    ass.append("ScriptType: v4.00+")
    ass.append("PlayResX: 1080")
    ass.append("PlayResY: 1920")
    ass.append("ScaledBorderAndShadow: yes")
    ass.append("")
    ass.append("[V4+ Styles]")
    ass.append("Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, "
               "Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, "
               "Alignment, MarginL, MarginR, MarginV, Encoding")
    # Primary: white, Outline: black, Back: semi-transparent black box
    ass.append(
        "Style: Default,DejaVu Sans,"
        f"{font_size},&H00FFFFFF,&H00000000,&H00000000,&H90000000,"
        "1,0,0,0,100,100,0,0,3,"
        f"{outline},1,"
        "2,90,90,"
        f"{margin_v},1"
    )
    ass.append("")
    ass.append("[Events]")
    ass.append("Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text")

    for ln in lines:
        start = _sec_to_ass_time(ln.start)
        end = _sec_to_ass_time(ln.end)
        text = ln.text
        # Avoid empty lines
        if not text.strip():
            continue
        ass.append(f"Dialogue: 0,{start},{end},Default,,0,0,0,,{text}")

    out_path.write_text("\n".join(ass) + "\n", encoding="utf-8")
    return out_path


def _subtitles_from_txt(subs_txt: Path, duration: float, wrap_words: int, style: str) -> Path:
    """
    Turn subtitles.txt into timed ASS lines spread across duration.
    Each input line becomes a segment.
    """
    raw = subs_txt.read_text(encoding="utf-8", errors="ignore").strip()
    if not raw:
        raise FileNotFoundError(f"[Monday] subtitles.txt vuoto: {subs_txt}")

    # Split lines but keep meaningful ones
    lines_in = [l.strip() for l in raw.splitlines() if l.strip()]
    if not lines_in:
        raise FileNotFoundError(f"[Monday] subtitles.txt senza righe utili: {subs_txt}")

    # Timing: distribute by character weight
    weights = [max(5, len(l)) for l in lines_in]
    total_w = sum(weights)
    t = 0.0
    out_lines: list[AssLine] = []

    for l, w in zip(lines_in, weights):
        seg = (w / total_w) * max(1.0, duration)
        seg = max(0.8, min(seg, 6.0))  # clamp readable
        start = t
        end = min(duration, t + seg)
        t = end

        text = _wrap_every_n_words(l, wrap_words)
        out_lines.append(AssLine(start=start, end=end, text=text))

        if t >= duration:
            break

    # Ensure last line ends at duration
    if out_lines and out_lines[-1].end < duration:
        out_lines[-1].end = duration

    BUILD_DIR.mkdir(parents=True, exist_ok=True)
    return _build_ass(out_lines, BUILD_DIR / "subtitles.ass", style=style)


def _ensure_subtitles_ass(duration: float, style: str) -> Path:
    """
    Priority:
    1) videos_to_upload/subtitles_wrapped.ass (if you already generated it)
    2) videos_to_upload/subtitles.txt -> build/subtitles.ass
    Otherwise: create a minimal subtitle from title.
    """
    wrap_words = int(os.getenv("SUB_WRAP_WORDS", "5") or "5")

    p_ass = VIDEOS_DIR / "subtitles_wrapped.ass"
    if p_ass.exists() and p_ass.stat().st_size > 0:
        return p_ass

    p_txt = VIDEOS_DIR / "subtitles.txt"
    if p_txt.exists() and p_txt.stat().st_size > 0:
        return _subtitles_from_txt(p_txt, duration=duration, wrap_words=wrap_words, style=style)

    # Minimal fallback
    title, _ = _read_video_info()
    if not title:
        title = "Deadpan story"
    out_lines = [AssLine(0.0, max(2.0, min(5.0, duration)), _wrap_every_n_words(title, wrap_words))]
    BUILD_DIR.mkdir(parents=True, exist_ok=True)
    return _build_ass(out_lines, BUILD_DIR / "subtitles.ass", style=style)


def _make_base_video(background_mp4: Path, audio_path: Path) -> Path:
    BUILD_DIR.mkdir(parents=True, exist_ok=True)
    out = BUILD_DIR / "video_base.mp4"

    # Re-encode audio to AAC, keep video (bg already H264), ensure faststart.
    _run([
        "ffmpeg", "-y",
        "-i", str(background_mp4),
        "-i", str(audio_path),
        "-c:v", "copy",
        "-c:a", "aac",
        "-b:a", "128k",
        "-shortest",
        "-movflags", "+faststart",
        str(out),
    ])
    return out


def _unique_suffix() -> str:
    # short unique ID for titles
    return datetime.utcnow().strftime("%y%m%d-%H%M%S")


def _make_title_and_description() -> tuple[str, str, list[str]]:
    base_title, base_desc = _read_video_info()

    if not base_title:
        # use first line of subtitles.txt if available
        st = VIDEOS_DIR / "subtitles.txt"
        if st.exists():
            first = ""
            for l in st.read_text(encoding="utf-8", errors="ignore").splitlines():
                l = l.strip()
                if l:
                    first = l
                    break
            base_title = first or "Deadpan Auto Short"
        else:
            base_title = "Deadpan Auto Short"

    base_title = _sanitize_title(base_title)
    base_desc = (base_desc or "").strip()

    # Ensure #shorts present
    if "#shorts" not in base_title.lower():
        # avoid pushing title over limit
        pass

    # Add suffix to avoid duplicates
    suffix = _unique_suffix()
    title = f"{base_title} [{suffix}]"
    title = title[:95].rstrip()

    desc = base_desc
    if "#shorts" not in desc.lower():
        desc = (desc + "\n\n#shorts").strip()

    tags = ["shorts", "deadpan", "story"]
    return title, desc, tags


def _call_upload(video_path: Path, title: str, description: str, tags: list[str]) -> str:
    """
    Call uploader.upload_video in a compatible way (signature might differ).
    """
    import uploader  # local module

    fn = getattr(uploader, "upload_video", None)
    if fn is None:
        raise RuntimeError("[Monday] uploader.upload_video non trovato in src/uploader.py")

    sig = inspect.signature(fn)
    kwargs = {}

    # Most common params used in your project
    if "video_path" in sig.parameters:
        kwargs["video_path"] = str(video_path)
    else:
        # fallback: assume first arg is path
        pass

    if "title" in sig.parameters:
        kwargs["title"] = title
    if "description" in sig.parameters:
        kwargs["description"] = description
    if "tags" in sig.parameters:
        kwargs["tags"] = tags
    if "privacy_status" in sig.parameters:
        kwargs["privacy_status"] = "public"

    # call safely
    try:
        if kwargs:
            return fn(**kwargs)
        return fn(str(video_path), title, description, tags)
    except TypeError:
        # try minimal
        return fn(str(video_path))


def main() -> None:
    VIDEOS_DIR.mkdir(parents=True, exist_ok=True)
    BUILD_DIR.mkdir(parents=True, exist_ok=True)

    # Sub style (only affects ASS style sizing/margins)
    sub_style = (os.getenv("SUB_STYLE", "cinematic") or "cinematic").strip().lower()
    if sub_style not in ("cinematic", "aggressive"):
        sub_style = "cinematic"
    print(f"[Monday] SUB_STYLE scelto: {sub_style}")

    # Pick audio
    audio_path = _pick_audio_file()
    print(f"[Monday] Audio: {audio_path} (size: {audio_path.stat().st_size} byte)")

    # Duration (cap to 60s for Shorts safety unless you want more)
    duration = _ffprobe_duration(audio_path)
    duration_cap = float(os.getenv("DURATION_LIMIT", "60") or "60")
    duration = min(duration, duration_cap)
    print(f"[Monday] Durata: {duration:.2f}s (cap {duration_cap}s)")

    # Generate background mp4 procedural (already 1080x1920)
    seed = int(datetime.utcnow().timestamp())
    bg = backgrounds.generate_procedural_background(
        duration_s=duration,
        seed=seed,
        width=DEFAULT_W,
        height=DEFAULT_H,
        fps=DEFAULT_FPS,
    )
    print(f"[Monday] Background: {bg} (size: {bg.stat().st_size} byte)")

    # Make base video with audio
    base_video = _make_base_video(bg, audio_path)
    print(f"[Monday] Base video: {base_video} (size: {base_video.stat().st_size} byte)")

    # Ensure subtitles ASS
    subs_ass = _ensure_subtitles_ass(duration=duration, style=sub_style)
    print(f"[Monday] Subtitles ASS: {subs_ass} (size: {subs_ass.stat().st_size} byte)")

    # Burn-in subtitles -> final in videos_to_upload
    final_path = subtitles.add_burned_in_subtitles(
        video_path=base_video,
        subtitles_ass_path=subs_ass,
        output_dir=VIDEOS_DIR,
        output_name="video_final.mp4",
    )
    print(f"[Monday] Video finale: {final_path} (size: {final_path.stat().st_size} byte)")

    # Upload if enabled
    upload = (os.getenv("UPLOAD_YT", "1") or "1").strip()
    if upload == "1":
        title, desc, tags = _make_title_and_description()
        print(f"[Monday] Titolo che inviamo a YouTube: {title!r}")
        vid = _call_upload(final_path, title=title, description=desc, tags=tags)
        print(f"[Monday] Uploaded video id: {vid}")
    else:
        print("[Monday] UPLOAD_YT=0 -> upload saltato.")


if __name__ == "__main__":
    main()
