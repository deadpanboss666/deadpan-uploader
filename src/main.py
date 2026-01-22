from __future__ import annotations

import hashlib
import inspect
import os
import random
import subprocess
from datetime import datetime, timezone
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parent.parent
SRC_DIR = ROOT_DIR / "src"
BUILD_DIR = ROOT_DIR / "build"
VIDEOS_DIR = ROOT_DIR / "videos_to_upload"


def _run_capture(cmd: list[str]) -> str:
    p = subprocess.run(cmd, capture_output=True, text=True)
    if p.returncode != 0:
        raise RuntimeError(
            f"Command failed: {' '.join(cmd)}\n"
            f"STDOUT:\n{p.stdout}\n"
            f"STDERR:\n{p.stderr}"
        )
    return p.stdout.strip()


def _ffprobe_duration_seconds(path: Path) -> float:
    out = _run_capture([
        "ffprobe", "-v", "error",
        "-show_entries", "format=duration",
        "-of", "default=nw=1:nk=1",
        str(path),
    ])
    try:
        return float(out)
    except Exception:
        return 0.0


def _pick_sub_style_70_30() -> str:
    # Rispetta SUB_STYLE se già impostata
    existing = (os.getenv("SUB_STYLE") or "").strip()
    if existing:
        return existing

    now = datetime.now(timezone.utc).strftime("%Y%m%d%H")
    run_id = os.getenv("GITHUB_RUN_ID", "")
    sha = os.getenv("GITHUB_SHA", "")
    seed_str = f"{now}|{run_id}|{sha}"

    h = hashlib.sha256(seed_str.encode("utf-8")).hexdigest()
    seed_int = int(h[:16], 16)
    rng = random.Random(seed_int)

    style = "aggressive" if rng.random() < 0.70 else "cinematic"
    os.environ["SUB_STYLE"] = style
    return style


def _find_audio() -> Path:
    BUILD_DIR.mkdir(parents=True, exist_ok=True)

    candidates = [
        BUILD_DIR / "voice.mp3",
        BUILD_DIR / "voice.wav",
        BUILD_DIR / "audio.wav",
        BUILD_DIR / "tts.wav",
        BUILD_DIR / "audio_trimmed.wav",
        ROOT_DIR / "audio.wav",
        ROOT_DIR / "audio.mp3",
    ]
    for p in candidates:
        if p.exists() and p.stat().st_size > 0:
            return p

    # fallback: cerca un audio qualsiasi in build
    for ext in (".mp3", ".wav", ".m4a", ".aac", ".flac", ".ogg"):
        items = sorted(BUILD_DIR.glob(f"*{ext}"), key=lambda x: x.stat().st_mtime, reverse=True)
        if items:
            return items[0]

    raise FileNotFoundError("Audio non trovato in build/ (voice.mp3, audio.wav, ecc.).")


def _make_basic_ass_from_txt(txt_path: Path, ass_out: Path) -> Path:
    """
    Crea un .ass minimale da un .txt (una riga per sottotitolo).
    Timing semplice: ogni riga ~1.25s.
    È un fallback per GitHub Actions quando manca la generazione ASS.
    """
    raw = txt_path.read_text(encoding="utf-8", errors="ignore").splitlines()
    lines = [t.strip() for t in raw if t.strip()]
    if not lines:
        raise FileNotFoundError(f"File sottotitoli txt vuoto: {txt_path}")

    def fmt_time(seconds: float) -> str:
        h = int(seconds // 3600)
        m = int((seconds % 3600) // 60)
        s = seconds % 60
        return f"{h}:{m:02d}:{s:05.2f}"

    header = """[Script Info]
ScriptType: v4.00+
PlayResX: 1080
PlayResY: 1920
WrapStyle: 2
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,DejaVu Sans,64,&H00FFFFFF,&H00000000,&H90000000,1,0,0,0,100,100,0,0,3,10,2,2,140,140,860,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    start = 0.0
    step = 1.25
    dur = 1.25

    out = [header]
    for t in lines:
        t = t.replace("\r", "")
        s = fmt_time(start)
        e = fmt_time(start + dur)
        out.append(f"Dialogue: 0,{s},{e},Default,,0,0,0,,{t}")
        start += step

    ass_out.parent.mkdir(parents=True, exist_ok=True)
    ass_out.write_text("\n".join(out) + "\n", encoding="utf-8")
    return ass_out


def _require_subtitles_ass() -> Path:
    subs = BUILD_DIR / "subtitles.ass"
    if subs.exists() and subs.stat().st_size > 0:
        return subs

    # fallback: se esiste subtitles.txt, generiamo un ass minimale
    txt_candidates = [
        BUILD_DIR / "subtitles.txt",
        VIDEOS_DIR / "subtitles.txt",
        ROOT_DIR / "subtitles.txt",
    ]
    for t in txt_candidates:
        if t.exists() and t.stat().st_size > 0:
            print(f"[Monday] subtitles.ass mancante -> creo fallback da: {t}")
            return _make_basic_ass_from_txt(t, subs)

    raise FileNotFoundError(f"[Monday] Sottotitoli mancanti: {subs} (e nessun subtitles.txt trovato)")


def _safe_title() -> str:
    title_file = BUILD_DIR / "title.txt"
    if title_file.exists():
        t = title_file.read_text(encoding="utf-8", errors="ignore").strip()
        if t:
            return t[:95]
    return "Deadpan Auto Short"


def _safe_description() -> str:
    desc_file = BUILD_DIR / "description.txt"
    if desc_file.exists():
        d = desc_file.read_text(encoding="utf-8", errors="ignore").strip()
        if d:
            if "#shorts" not in d.lower():
                d += "\n\n#shorts"
            return d
    return "Auto-generated short. #shorts"


def _safe_tags() -> list[str]:
    tags = ["shorts", "deadpan", "story"]
    tag_file = BUILD_DIR / "tags.txt"
    if tag_file.exists():
        extra = [x.strip() for x in tag_file.read_text(encoding="utf-8", errors="ignore").split(",") if x.strip()]
        tags = list(dict.fromkeys(tags + extra))
    return tags[:20]


def _burn_subs(base_video: Path, subs_ass: Path) -> Path:
    # Import locale: garantisce che in GitHub Actions carichi src/subtitles.py
    import subtitles  # type: ignore

    fn = getattr(subtitles, "add_burned_in_subtitles", None)
    if fn is None:
        raise RuntimeError("subtitles.add_burned_in_subtitles non trovato")

    sig = inspect.signature(fn)
    params = set(sig.parameters.keys())

    kwargs = {}
    if "video_path" in params:
        kwargs["video_path"] = base_video
    if "subtitles_ass_path" in params:
        kwargs["subtitles_ass_path"] = subs_ass
    if "subtitles_path" in params and "subtitles_ass_path" not in kwargs:
        kwargs["subtitles_path"] = subs_ass
    if "subtitles_file" in params and "subtitles_ass_path" not in kwargs and "subtitles_path" not in kwargs:
        kwargs["subtitles_file"] = subs_ass

    if "output_dir" in params:
        kwargs["output_dir"] = VIDEOS_DIR
    if "output_name" in params:
        kwargs["output_name"] = "video_final.mp4"

    return fn(**kwargs)  # type: ignore


def _upload(final_video: Path, title: str, description: str, tags: list[str]) -> str:
    import uploader  # type: ignore

    fn = getattr(uploader, "upload_video", None)
    if fn is None:
        raise RuntimeError("uploader.upload_video non trovato")

    sig = inspect.signature(fn)
    params = set(sig.parameters.keys())

    kwargs = {}
    if "video_path" in params:
        kwargs["video_path"] = str(final_video)
    elif "path" in params:
        kwargs["path"] = str(final_video)
    else:
        return fn(str(final_video))  # type: ignore

    if "title" in params:
        kwargs["title"] = title
    if "description" in params:
        kwargs["description"] = description
    if "tags" in params:
        kwargs["tags"] = tags

    return fn(**kwargs)  # type: ignore


def main() -> None:
    chosen = _pick_sub_style_70_30()
    print(f"[Monday] SUB_STYLE scelto: {chosen}")

    do_upload = (os.getenv("UPLOAD_YT") or "1").strip() != "0"

    VIDEOS_DIR.mkdir(parents=True, exist_ok=True)
    BUILD_DIR.mkdir(parents=True, exist_ok=True)

    raw_audio = _find_audio()
    subs_ass = _require_subtitles_ass()

    duration = _ffprobe_duration_seconds(raw_audio)
    if duration <= 0:
        duration = 45.0

    from backgrounds import generate_procedural_background
    bg = generate_procedural_background(duration_s=min(duration, 60.0))

    from quality import apply_quality_pipeline
    base_video = BUILD_DIR / "video_base.mp4"
    apply_quality_pipeline(
        raw_audio=raw_audio,
        background_path=bg,
        final_video=base_video,
        duration_limit=60,
    )

    final_video = _burn_subs(base_video=base_video, subs_ass=subs_ass)

    size = final_video.stat().st_size if final_video.exists() else 0
    print(f"[Monday] Video per upload: {final_video} (dimensione: {size} byte)")

    if not do_upload:
        print("[Monday] UPLOAD_YT=0 -> salto upload.")
        return

    title = _safe_title()
    description = _safe_description()
    tags = _safe_tags()

    vid = _upload(final_video=final_video, title=title, description=description, tags=tags)
    print(f"[Monday] Upload completato. Video ID: {vid}")


if __name__ == "__main__":
    main()
