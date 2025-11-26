from pathlib import Path
import subprocess


def run_ffmpeg(cmd: list[str]) -> None:
    """Esegue ffmpeg e alza errore se qualcosa va storto."""
    print("Eseguo ffmpeg:", " ".join(cmd))
    completed = subprocess.run(cmd, check=False)
    if completed.returncode != 0:
        raise RuntimeError(f"ffmpeg error (exit code {completed.returncode})")


def apply_quality_pipeline(
    raw_audio: Path,
    background_path: Path,
    final_video: Path,
    duration_limit: int = 60,
) -> None:
    """
    Pipeline super-semplice e sicura per YouTube:

    1. Taglia/normalizza l'audio a max `duration_limit` secondi (WAV 48k mono).
    2. Crea un MP4 verticale 1080x1920 con:
       - immagine fissa come sfondo
       - codec video H.264
       - audio AAC 128k
       - pix_fmt yuv420p
    """

    raw_audio = Path(raw_audio)
    background_path = Path(background_path)
    final_video = Path(final_video)

    if not raw_audio.exists():
        raise FileNotFoundError(f"Audio file not found: {raw_audio}")
    if not background_path.exists():
        raise FileNotFoundError(f"Background image not found: {background_path}")

    final_video.parent.mkdir(parents=True, exist_ok=True)

    # 1) Taglia e normalizza l'audio in un WAV 48k mono
    trimmed_audio = final_video.with_name("audio_trimmed.wav")

    cmd_trim = [
        "ffmpeg",
        "-y",
        "-i",
        str(raw_audio),
        "-t",
        str(duration_limit),
        "-ac",
        "1",          # mono
        "-ar",
        "48000",      # 48 kHz
        "-c:a",
        "pcm_s16le",  # WAV 16 bit
        str(trimmed_audio),
    ]
    run_ffmpeg(cmd_trim)

    # 2) Crea il video verticale 1080x1920, H.264 + AAC
    #    -loop 1: usa l'immagine come frame ripetuto
    #    scale=1080:1920: adattiamo l'immagine al formato verticale
    cmd_video = [
        "ffmpeg",
        "-y",
        "-loop",
        "1",
        "-i",
        str(background_path),
        "-i",
        str(trimmed_audio),
        "-vf",
        "scale=1080:1920",
        "-c:v",
        "libx264",
        "-preset",
        "veryfast",
        "-tune",
        "stillimage",
        "-pix_fmt",
        "yuv420p",
        "-c:a",
        "aac",
        "-b:a",
        "128k",
        "-shortest",
        "-movflags",
        "+faststart",
        str(final_video),
    ]
    run_ffmpeg(cmd_video)

    print(f"Video finale creato in: {final_video}")
