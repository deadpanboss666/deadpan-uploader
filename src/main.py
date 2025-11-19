# -----------------------------------------
# main.py — Monday
# Script principale di upload automatico
# -----------------------------------------

import os
from uploader import upload_video

def main():
    print("[Monday] Avvio upload automatico...")

    # Percorso del video da caricare in automatico
    video_path = "videos_to_upload/video.mp4"

    # Titolo e descrizione del video
    title = "Video Caricato Automaticamente"
    description = "Upload automatico tramite GitHub Actions"

    # Controllo esistenza file
    if not os.path.exists(video_path):
        print(f"[Monday] ERRORE: Il file video non esiste: {video_path}")
        return

    print("[Monday] Preparazione upload...")

    upload_video(video_path, title, description)

if __name__ == "__main__":
    main()
