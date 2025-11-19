# -----------------------------------------
# main.py — Monday
# Script principale di upload automatico
# -----------------------------------------

import os
from uploader import upload_video
import os

def main():
    print("[Monday] Avvio upload automatico...")

<<<<<<< HEAD
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

=======
    # Percorso del video nella cartella videos_to_upload/
    video_path = "videos_to_upload/video.mp4"

    # Titolo e descrizione del video
    title = "Video di test caricato automaticamente"
    description = "Questo video è stato caricato da GitHub Actions tramite Monday Bot."

    # Esegui upload
>>>>>>> b346b83fc1aee058902f631daec8f865d8fa85c3
    upload_video(video_path, title, description)

if __name__ == "__main__":
    main()
