# -----------------------------------------
# main.py — Monday
# Script principale di upload automatico
# -----------------------------------------

import os
from uploader import upload_video
from subtitles import add_burned_in_subtitles


def main():
    print("[Monday] Avvio upload automatico...")

    # Percorso del video da caricare in automatico
    video_path = "videos_to_upload/video.mp4"

    # Titolo e descrizione del video
    title = "Video Caricato Automaticamente"
    description = "Upload automatico tramite GitHub Actions"

    # Per ora usiamo la descrizione come testo dei sottotitoli
    script_text = description

    # Controllo esistenza file
    if not os.path.exists(video_path):
        print(f"[Monday] ERRORE: Il file video non esiste: {video_path}")
        return

    print("[Monday] Generazione video con sottotitoli bruciati...")
    # Crea un nuovo file video con sottotitoli (es: video_subs.mp4)
    video_path = add_burned_in_subtitles(
        video_path=video_path,
        script_text=script_text,
    )

    print("[Monday] Preparazione upload...")

    # Esegui upload del video con sottotitoli
    upload_video(video_path, title, description)


if __name__ == "__main__":
    main()
