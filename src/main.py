from __future__ import annotations

import hashlib
import inspect
import os
import random
import re
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
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
        BUILD_DIR / "voice.m4a",
        BUILD_DIR / "audio.wav",
        BUILD_DIR / "tts.wav",
        BUILD_DIR / "audio_trimmed.wav",
    ]
    for p in candidates:
        if p.exists() and p.stat().st_size > 0:
            return p

    for ext in (".mp3", ".wav", ".m4a", ".aac", ".flac", ".ogg"):
        items = sorted(BUILD_DIR.glob(f"*{ext}"), key=lambda x: x.stat().st_mtime, reverse=True)
        if items:
            return items[0]

    raise FileNotFoundError("Audio non trovato in build/ (voice.mp3, voice.wav, ecc.).")


def _wrap_every_n_words(text: str, n: int = 5) -> str:
    if r"\N" in text:
        return text
    words = text.split()
    if len(words) <= n:
        return text
    chunks = [" ".join(words[i:i + n]) for i in range(0, len(words), n)]
    return r"\N".join(chunks)


def _ass_time(t: float) -> str:
    if t < 0:
        t = 0.0
    h = int(t // 3600)
    m = int((t % 3600) // 60)
    s = t % 60
    return f"{h}:{m:02d}:{s:05.2f}"


def _generate_ass_from_audio_whisper(audio_path: Path, ass_out: Path) -> Path:
    try:
        from faster_whisper import WhisperModel
    except Exception as e:
        raise RuntimeError("Dipendenza mancante: faster-whisper (installata nel workflow?).") from e

    model_name = (os.getenv("SUB_MODEL") or "tiny").strip()

    cache_dir = BUILD_DIR / ".whisper_cache"
    cache_dir.mkdir(parents=True, exist_ok=True)
    os.environ.setdefault("HF_HOME", str(cache_dir))
    os.environ.setdefault("XDG_CACHE_HOME", str(cache_dir))

    print(f"[Monday] Whisper model: {model_name}")
    model = WhisperModel(model_name, device="cpu", compute_type="int8")

    segments, _info = model.transcribe(
        str(audio_path),
        beam_size=5,
        vad_filter=True,
        language="en",
    )

    wrap_n = int((os.getenv("SUB_WRAP_WORDS") or "5").strip() or "5")

    # ✅ SAFE-BOTTOM (non più in alto)
    # MarginV 220/240 = zona safe sopra UI Shorts
    header = """[Script Info]
ScriptType: v4.00+
PlayResX: 1080
PlayResY: 1920
WrapStyle: 2
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,DejaVu Sans,64,&H00FFFFFF,&H00000000,&H90000000,1,0,0,0,100,100,0,0,3,10,2,2,110,110,240,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""

    lines = [header]
    count = 0
    for seg in segments:
        txt = (seg.text or "").strip()
        if not txt:
            continue
        start = float(seg.start)
        end = float(seg.end)
        if end <= start:
            end = start + 0.8
        txt = _wrap_every_n_words(txt, wrap_n)
        lines.append(f"Dialogue: 0,{_ass_time(start)},{_ass_time(end)},Default,,0,0,0,,{txt}")
        count += 1

    if count == 0:
        raise RuntimeError("[Monday] Whisper non ha prodotto segmenti (audio vuoto?).")

    ass_out.parent.mkdir(parents=True, exist_ok=True)
    ass_out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"[Monday] ASS generato: {ass_out} (righe: {count})")
    return ass_out


def _ensure_subtitles_ass(audio_path: Path) -> Path:
    subs = BUILD_DIR / "subtitles.ass"
    if subs.exists() and subs.stat().st_size > 0:
        return subs
    print("[Monday] subtitles.ass mancante -> genero da audio (Whisper).")
    return _generate_ass_from_audio_whisper(audio_path, subs)


def _read_first_caption_for_title(ass_path: Path) -> str:
    txt = ass_path.read_text(encoding="utf-8", errors="ignore")
    for line in txt.splitlines():
        if line.startswith("Dialogue:"):
            parts = line.split(",", 9)
            if len(parts) == 10:
                raw = parts[9]
                raw = raw.replace(r"\N", " ")
                raw = re.sub(r"\{.*?\}", "", raw)
                raw = re.sub(r"\s+", " ", raw).strip()
                raw = re.sub(r"[^\w\s'’-]", "", raw)
                if raw:
                    return raw
    return ""


def _unique_suffix_from_subs(subs_ass: Path) -> str:
    # suffisso breve, stabile e diverso per ogni audio/testo
    h = hashlib.sha1(subs_ass.read_bytes()).hexdigest()[:4]
    run = os.getenv("GITHUB_RUN_NUMBER") or os.getenv("GITHUB_RUN_ID") or ""
    if run:
        return f"{run}-{h}"
    # fallback locale
    t = datetime.now(timezone.utc).strftime("%m%d%H%M")
    return f"{t}-{h}"


def _safe_title(subs_ass: Path) -> str:
    # Se build/title.txt è presente lo usa, ma rende comunque unico.
    title_file = BUILD_DIR / "title.txt"
    if title_file.exists():
        t = title_file.read_text(encoding="utf-8", errors="ignore").strip()
        if t:
            base = t[:70].strip()
            return f"{base} #{_unique_suffix_from_subs(subs_ass)} #shorts"[:95]

    base = _read_first_caption_for_title(subs_ass)
    if not base:
        base = "Case file"

    base = base[:70].strip()
    return f"{base} #{_unique_suffix_from_subs(subs_ass)} #shorts"[:95]


def _safe_description(subs_ass: Path) -> str:
    desc_file = BUILD_DIR / "description.txt"
    if desc_file.exists():
        d = desc_file.read_text(encoding="utf-8", errors="ignore").strip()
        if d:
            if "#shorts" not in d.lower():
                d += "\n\n#shorts"
            return d

    txt = subs_ass.read_text(encoding="utf-8", errors="ignore")
    lines = []
    for line in txt.splitlines():
        if line.startswith("Dialogue:"):
            parts = line.split(",", 9)
            if len(parts) == 10:
                raw = parts[9].replace(r"\N", " ")
                raw = re.sub(r"\{.*?\}", "", raw)
                raw = re.sub(r"\s+", " ", raw).strip()
                if raw:
                    lines.append(raw)
        if len(lines) >= 3:
            break

    body = " ".join(lines)[:280].strip()
    if not body:
        body = "Auto-generated short."
    return f"{body}\n\n#shorts"


def _safe_tags() -> list[str]:
    tags = ["shorts", "deadpan", "story", "mystery"]
    tag_file = BUILD_DIR / "tags.txt"
    if tag_file.exists():
        extra = [x.strip() for x in tag_file.read_text(encoding="utf-8", errors="ignore").split(",") if x.strip()]
        tags = list(dict.fromkeys(tags + extra))
    return tags[:20]


def _burn_subs(base_video: Path, subs_ass: Path) -> Path:
    import subtitles  # local module

    fn = getattr(subtitles, "add_burned_in_subtitles", None)
    if fn is None:
        raise RuntimeError("subtitles.add_burned_in_subtitles non trovato")

    sig = inspect.signature(fn)
    params = set(sig.parameters.keys())

    kwargs = {"video_path": base_video}

    if "subtitles_ass_path" in params:
        kwargs["subtitles_ass_path"] = subs_ass
    elif "subtitles_path" in params:
        kwargs["subtitles_path"] = subs_ass
    elif "subtitles_file" in params:
        kwargs["subtitles_file"] = subs_ass
    else:
        raise RuntimeError("Firma add_burned_in_subtitles non compatibile (manca param subs).")

    if "output_dir" in params:
        kwargs["output_dir"] = VIDEOS_DIR
    if "output_name" in params:
        kwargs["output_name"] = "video_final.mp4"

    return fn(**kwargs)  # type: ignore


def _upload(final_video: Path, title: str, description: str, tags: list[str]) -> str:
    import uploader  # local module

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

    # evita bug in-place se input è già audio_trimmed.wav
    if raw_audio.name.lower() == "audio_trimmed.wav":
        safe_in = BUILD_DIR / "voice_input.wav"
        shutil.copyfile(raw_audio, safe_in)
        raw_audio = safe_in

    subs_ass = _ensure_subtitles_ass(raw_audio)

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

    title = _safe_title(subs_ass)
    description = _safe_description(subs_ass)
    tags = _safe_tags()

    print("[Monday] Titolo:", title)
    vid = _upload(final_video=final_video, title=title, description=description, tags=tags)
    print(f"[Monday] Upload completato. Video ID: {vid}")


if __name__ == "__main__":
    main()
