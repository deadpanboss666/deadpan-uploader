from uploader import upload_video
import os

# ============================================
# Monday - Main Script Automatico
# ============================================
# QUESTO FILE ESEGUE AUTOMATICAMENTE L'UPLOAD
# DI UN VIDEO SU YOUTUBE UTILIZZANDO uploader.py
# ============================================


def main():
    # Percorso del video da caricare
    video_path = "src/video.mp4"  # Sostituisci con il tuo file

    if not os.path.exists(video_path):
        print("[Monday] ERRORE: Il file del video non esiste:", video_path)
        return

    # Impostazioni YouTube
    title = "Titolo di esempio"
    description = "Descrizione automatica generata da Monday."
    tags = ["automation", "monday", "upload"]
    privacy = "unlisted"  # public / private / unlisted

    print("[Monday] Avvio upload automatico...")

    video_id = upload_video(
        file_path=video_path,
        title=title,
        description=description,
        tags=tags,
        privacy=privacy,
        thumbnail_path=None,  # Puoi aggiungerlo dopo
    )

    print(f"[Monday] Video caricato con successo! ID: {video_id}")


if __name__ == "__main__":
    main()
