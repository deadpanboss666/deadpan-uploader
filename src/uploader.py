<<<<<<< HEAD
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
    cred_path = "service-account.json"

    if not os.path.exists(cred_path):
        raise FileNotFoundError(
            f"[Monday] ERRORE: Non trovo il file delle credenziali: {cred_path}"
        )

    print("[Monday] Carico credenziali da service-account.json...")

    creds = Credentials.from_service_account_file(
        cred_path,
        scopes=["https://www.googleapis.com/auth/youtube.upload"]
    )

    print("[Monday] Credenziali caricate. Avvio servizio YouTube...")
    return build("youtube", "v3", credentials=creds)

def upload_video(video_path, title, description):
    """
    Esegue l’upload di un video su YouTube.
    """
    youtube = get_youtube_service()

    print(f"[Monday] Upload del video: {video_path}")

    media = MediaFileUpload(video_path, chunksize=-1, resumable=True)

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
=======
import os
import json
from googleapiclient.discovery import build
from google.oauth2.service_account import Credentials

def get_youtube_service():
    print("[Monday] Carico credenziali dal file JSON locale...")

    credentials_path = os.path.join(os.path.dirname(__file__), "service-account.json")

    if not os.path.exists(credentials_path):
        raise FileNotFoundError(f"File delle credenziali non trovato: {credentials_path}")

    creds = Credentials.from_service_account_file(
        credentials_path,
        scopes=["https://www.googleapis.com/auth/youtube.upload"]
    )

    print("[Monday] Credenziali caricate correttamente!")
    return build("youtube", "v3", credentials=creds)

def upload_video(video_path, title, description):
    print("[Monday] Connessione al servizio YouTube...")
    youtube = get_youtube_service()

    print("[Monday] Upload del video in corso...")
    request = youtube.videos().insert(
        part="snippet,status",
        body={
            "snippet": {"title": title, "description": description},
            "status": {"privacyStatus": "private"}
        },
        media_body=video_path
>>>>>>> b346b83fc1aee058902f631daec8f865d8fa85c3
    )

    print("[Monday] Invio dati a YouTube...")
    response = request.execute()
<<<<<<< HEAD

    print("[Monday] Upload COMPLETATO!")
    print(response)

=======
    print("[Monday] Upload completato!")
>>>>>>> b346b83fc1aee058902f631daec8f865d8fa85c3
    return response
