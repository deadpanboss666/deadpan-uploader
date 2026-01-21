from __future__ import annotations

from pathlib import Path
import subprocess


def run_ffmpeg(cmd: list[str]) -> None:
    """Run ffmpeg and raise if it fails."""
    print("Eseguo ffmpeg:", " ".join(cmd))
    completed = subprocess.run(cmd, check=False)
    if completed.returncode != 0:
        raise RuntimeError(f"ffmpeg error (exit code {completed.returncode})")


def _is_video_file(p: Path) -> bool:
    return p.suffix.lower() in {".mp4", ".mov", ".mkv", ".webm", ".m4v", ".avi"}


def apply_quality_pipeline(
    raw_audio: Path,
    background_path: Path,
    final_video: Path,
    duration_limit: int = 60,
    width: int = 1080,
    height: int = 1920,
    fps: int = 30,
) -> None:
    """
    Pipeline robusta per Shorts verticali 9:16:

    1) Taglia/normalizza audio a max `duration_limit` secondi (WAV 48k mono).
       Evita "in-place edit": se input e output coincidono, usa un nome alternativo.
    2) Crea MP4 verticale 1080x1920 con background:
       - se background_path è IMMAGINE: loop immagine
       - se background_path è VIDEO: loop video (stream_loop)
       Look "cinematic": crop/scale corretto + vignette + grain + eq.
    """

    raw_audio = Path(raw_audio)
    background_path = Path(background_path)
    final_video = Path(final_video)

    if not raw_audio.exists():
        raise FileNotFoundError(f"Audio file not found: {raw_audio}")
    if not background_path.exists():
        raise FileNotFoundError(f"Background file not found: {background_path}")

    final_video.parent.mkdir(parents=True, exist_ok=True)

    # 1) Trim + normalize audio into WAV 48k mono
    # Default output name near final_video
    trimmed_audio = final_video.with_name("audio_trimmed.wav")

    # If raw_audio is already audio_trimmed.wav in the same folder -> avoid in-place
    try:
        same_file = raw_audio.resolve() == trimmed_audio.resolve()
    except Exception:
        same_file = (str(raw_audio) == str(trimmed_audio))

    if same_file:
        trimmed_audio = final_video.with_name("audio_trimmed2.wav")

    cmd_trim = [
        "ffmpeg",
        "-y",
        "-i", str(raw_audio),
        "-t", str(duration_limit),
        "-ac", "1",
        "-ar", "48000",
        "-c:a", "pcm_s16le",
        str(trimmed_audio),
    ]
    run_ffmpeg(cmd_trim)

    # 2) Build cinematic background -> final vertical mp4
    vf = (
        f"scale={width}:{height}:force_original_aspect_ratio=increase,"
        f"crop={width}:{height},"
        f"eq=contrast=1.18:brightness=0.03:saturation=1.20,"
        f"vignette,"
        f"noise=alls=10:allf=t+u,"
        f"fps={fps},"
        f"format=yuv420p"
    )

    if _is_video_file(background_path):
        cmd_video = [
            "ffmpeg",
            "-y",
            "-stream_loop", "-1",
            "-i", str(background_path),
            "-i", str(trimmed_audio),
            "-vf", vf,
            "-c:v", "libx264",
            "-preset", "veryfast",
            "-crf", "18",
            "-pix_fmt", "yuv420p",
            "-r", str(fps),
            "-c:a", "aac",
            "-b:a", "128k",
            "-shortest",
            "-movflags", "+faststart",
            str(final_video),
        ]
    else:
        cmd_video = [
            "ffmpeg",
            "-y",
            "-loop", "1",
            "-i", str(background_path),
            "-i", str(trimmed_audio),
            "-vf", vf,
            "-c:v", "libx264",
            "-preset", "veryfast",
            "-tune", "stillimage",
            "-crf", "18",
            "-pix_fmt", "yuv420p",
            "-r", str(fps),
            "-c:a", "aac",
            "-b:a", "128k",
            "-shortest",
            "-movflags", "+faststart",
            str(final_video),
        ]

    run_ffmpeg(cmd_video)
    print(f"Video finale creato in: {final_video}")
