from uploader import upload_video
import os

def main():
    print("[Monday] Avvio upload automatico...")

    # Percorso del video nella cartella videos_to_upload/
    video_path = "videos_to_upload/video.mp4"

    # Titolo e descrizione del video
    title = "Video di test caricato automaticamente"
    description = "Questo video è stato caricato da GitHub Actions tramite Monday Bot."

    # Esegui upload
    upload_video(video_path, title, description)

if __name__ == "__main__":
    main()
