# -----------------------------------------
# uploader.py — Monday
# Gestisce l’upload su YouTube tramite API
# -----------------------------------------

import os
from googleapiclient.discovery import build
from google.oauth2.service_account import Credentials
from googleapiclient.http import MediaFileUpload

def get_youtube_service():
    """
    Carica le credenziali dal file service-account.json
    e inizializza il client YouTube API.
    """
    # Percorso assoluto del file credenziali
    credentials_path = os.path.join(os.path.dirname(__file__), "service-account.json")

    if not os.path.exists(credentials_path):
        raise FileNotFoundError(
            f"[Monday] ERRORE: Non trovo il file delle credenziali: {credentials_path}"
        )

    print("[Monday] Carico credenziali da service-account.json...")

    creds = Credentials.from_service_account_file(
        credentials_path,
        scopes=["https://www.googleapis.com/auth/youtube.upload"]
    )

    print("[Monday] Credenziali caricate. Avvio servizio YouTube...")
    return build("youtube", "v3", credentials=creds)

def upload_video(video_path, title, description):
    """
    Esegue l’upload di un video su YouTube.
    """
    print("[Monday] Connessione al servizio YouTube...")
    youtube = get_youtube_service()

    print(f"[Monday] Upload del video: {video_path}")

    # Prepara il file video per l’upload
    media = MediaFileUpload(video_path, chunksize=-1, resumable=True)

    # Richiesta di upload
    request = youtube.videos().insert(
        part="snippet,status",
        body={
            "snippet": {
                "title": title,
                "description": description,
                "categoryId": "22"
            },
            "status": {
                "privacyStatus": "private"
            }
        },
        media_body=media
    )

    print("[Monday] Invio dati a YouTube...")
    response = request.execute()

    print("[Monday] Upload COMPLETATO!")
    print(response)

    return response
