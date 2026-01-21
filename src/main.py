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
        raise RuntimeError(f"Command failed: {' '.join(cmd)}\nSTDOUT:\n{p.stdout}\nSTDERR:\n{p.stderr}")
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
    """
    70% aggressive / 30% cinematic.
    Deterministico per run: usa (UTC hour + GITHUB_RUN_ID + SHA) come seed.
    Se SUB_STYLE è già settata, NON cambia nulla.
    """
    existing = (os.getenv("SUB_STYLE") or "").strip()
    if existing:
        return existing

    now = datetime.now(timezone.utc).strftime("%Y%m%d%H")
    run_id = os.getenv("GITHUB_RUN_ID", "")
    sha = os.getenv("GITHUB_SHA", "")
    seed_str = f"{now}|{run_id}|{sha}"

    h = hashlib.sha256(seed_str.encode("utf-8")).hexdigest()
    seed_int = int(h[:16], 16)  # sufficiente
    rng = random.Random(seed_int)

    style = "aggressive" if rng.random() < 0.70 else "cinematic"
    os.environ["SUB_STYLE"] = style
    return style


def _find_first_existing(paths: list[Path]) -> Path | None:
    for p in paths:
        if p.exists():
            return p
    return None


def _find_latest_by_glob(folder: Path, pattern: str) -> Path | None:
    items = sorted(folder.glob(pattern), key=lambda p: p.stat().st_mtime, reverse=True)
    return items[0] if items else None


def _get_audio_path() -> Path:
    BUILD_DIR.mkdir(parents=True, exist_ok=True)

    candidates = [
        BUILD_DIR / "audio.wav",
        BUILD_DIR / "audio_trimmed.wav",
        BUILD_DIR / "tts.wav",
        BUILD_DIR / "raw_audio.wav",
        ROOT_DIR / "audio.wav",
        ROOT_DIR / "audio.mp3",
    ]
    p = _find_first_existing(candidates)
    if p:
        return p

    # fallback: cerca un audio in build
    for ext in (".wav", ".mp3", ".m4a", ".aac", ".flac", ".ogg"):
        found = _find_latest_by_glob(BUILD_DIR, f"*{ext}")
        if found:
            return found

    raise FileNotFoundError("Non trovo nessun file audio (build/audio.wav, build/tts.wav, ecc.).")


def _get_subtitles_path() -> Path | None:
    BUILD_DIR.mkdir(parents=True, exist_ok=True)

    candidates = [
        BUILD_DIR / "subtitles.ass",
        BUILD_DIR / "subs.ass",
        BUILD_DIR / "subtitles.srt",
        BUILD_DIR / "subs.srt",
        ROOT_DIR / "subtitles.ass",
        ROOT_DIR / "subtitles.srt",
    ]
    p = _find_first_existing(candidates)
    if p:
        return p

    # fallback: cerca un .ass o .srt in build
    found = _find_latest_by_glob(BUILD_DIR, "*.ass")
    if found:
        return found
    found = _find_latest_by_glob(BUILD_DIR, "*.srt")
    if found:
        return found

    return None


def _safe_title_from_files() -> str:
    # Se hai un titolo generato da altri moduli, lo prende da build/title.txt
    title_file = BUILD_DIR / "title.txt"
    if title_file.exists():
        t = title_file.read_text(encoding="utf-8", errors="ignore").strip()
        if t:
            return t[:95]
    return "Deadpan Auto Short"


def _safe_description() -> str:
    # descrizione minima, puoi arricchirla dopo
    base = (BUILD_DIR / "description.txt")
    if base.exists():
        d = base.read_text(encoding="utf-8", errors="ignore").strip()
        if d:
            if "#shorts" not in d.lower():
                d += "\n\n#shorts"
            return d
    return "Auto-generated short. #shorts"


def _safe_tags() -> list[str]:
    # tags minimi + shorts
    tags = ["shorts", "deadpan", "story"]
    tag_file = BUILD_DIR / "tags.txt"
    if tag_file.exists():
        extra = [x.strip() for x in tag_file.read_text(encoding="utf-8", errors="ignore").split(",") if x.strip()]
        tags = list(dict.fromkeys(tags + extra))
    return tags[:20]


def _call_burn_subs(video_path: Path, subs_path: Path, out_dir: Path, out_name: str) -> Path:
    import subtitles  # local module

    # Compat totale: chiama subtitles.add_burned_in_subtitles anche se cambia firma.
    fn = getattr(subtitles, "add_burned_in_subtitles", None)
    if fn is None:
        raise RuntimeError("subtitles.add_burned_in_subtitles non trovato")

    sig = inspect.signature(fn)
    params = set(sig.parameters.keys())

    kwargs = {}
    if "video_path" in params:
        kwargs["video_path"] = video_path
    if "subtitles_ass_path" in params:
        kwargs["subtitles_ass_path"] = subs_path
    # compat alias
    if "subtitles_path" in params and "subtitles_ass_path" not in kwargs:
        kwargs["subtitles_path"] = subs_path
    if "subtitles_file" in params and "subtitles_ass_path" not in kwargs and "subtitles_path" not in kwargs:
        kwargs["subtitles_file"] = subs_path

    if "output_dir" in params:
        kwargs["output_dir"] = out_dir
    if "output_name" in params:
        kwargs["output_name"] = out_name

    return fn(**kwargs)


def _call_upload(final_video: Path, title: str, description: str, tags: list[str]) -> str:
    import uploader  # local module

    fn = getattr(uploader, "upload_video", None)
    if fn is None:
        raise RuntimeError("uploader.upload_video non trovato")

    sig = inspect.signature(fn)
    params = set(sig.parameters.keys())

    kwargs = {}
    # prova a passare i nomi più comuni senza rompere la firma
    if "video_path" in params:
        kwargs["video_path"] = str(final_video)
    elif "path" in params:
        kwargs["path"] = str(final_video)
    else:
        # fallback: primo argomento posizionale
        return fn(str(final_video))  # type: ignore

    if "title" in params:
        kwargs["title"] = title
    if "description" in params:
        kwargs["description"] = description
    if "tags" in params:
        kwargs["tags"] = tags

    # Non forziamo privacy qui: lo gestisci in uploader.py
    return fn(**kwargs)  # type: ignore


def main() -> None:
    # 70/30 automatico (se SUB_STYLE non è già settato)
    chosen = _pick_sub_style_70_30()
    print(f"[Monday] SUB_STYLE scelto: {chosen}")

    upload_flag = (os.getenv("UPLOAD_YT") or "1").strip()
    do_upload = upload_flag != "0"

    # Paths
    VIDEOS_DIR.mkdir(parents=True, exist_ok=True)
    BUILD_DIR.mkdir(parents=True, exist_ok=True)

    raw_audio = _get_audio_path()
    subs_path = _get_subtitles_path()

    duration = _ffprobe_duration_seconds(raw_audio)
    if duration <= 0:
        duration = 45.0
    duration_limit = 60

    # Background (procedural video)
    from backgrounds import generate_procedural_background
    bg = generate_procedural_background(duration_s=min(duration, float(duration_limit)))

    # Render base video (bg + audio) -> build/video_raw.mp4
    from quality import apply_quality_pipeline
    raw_video = BUILD_DIR / "video_raw.mp4"
    apply_quality_pipeline(
        raw_audio=raw_audio,
        background_path=bg,
        final_video=raw_video,
        duration_limit=duration_limit,
    )

    # Burn subtitles -> videos_to_upload/video_final.mp4
    final_video = VIDEOS_DIR / "video_final.mp4"
    if subs_path and subs_path.exists():
        final_video = _call_burn_subs(
            video_path=raw_video,
            subs_path=subs_path,
            out_dir=VIDEOS_DIR,
            out_name="video_final.mp4",
        )
    else:
        # Se non ci sono sottotitoli, copia il raw video come finale
        final_video = VIDEOS_DIR / "video_final.mp4"
        final_video.write_bytes(raw_video.read_bytes())

    size = final_video.stat().st_size if final_video.exists() else 0
    print(f"[Monday] Video per upload: {final_video} (dimensione: {size} byte)")

    if not do_upload:
        print("[Monday] UPLOAD_YT=0 -> salto upload.")
        return

    title = _safe_title_from_files()
    description = _safe_description()
    tags = _safe_tags()

    vid = _call_upload(final_video=final_video, title=title, description=description, tags=tags)
    print(f"[Monday] Upload completato. Video ID: {vid}")


if __name__ == "__main__":
    main()
