import os
import json
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

# ---------------------------------------------
#   CREA IL SERVIZIO YOUTUBE DAL SERVICE ACCOUNT
#   USA LA VARIABILE CORRETTA:
#   GOOGLE_APPLICATION_CREDENTIALS_JSON
# ---------------------------------------------
def get_youtube_service():
    # Carica il contenuto JSON dalle variabili di ambiente
    info = json.loads(os.environ["GOOGLE_APPLICATION_CREDENTIALS_JSON"])

    # Crea le credenziali dal dizionario JSON
    credentials = service_account.Credentials.from_service_account_info(
        info,
        scopes=["https://www.googleapis.com/auth/youtube.upload"]
    )

    # Inizializza il servizio YouTube
    youtube = build("youtube", "v3", credentials=credentials)
    return youtube


# ---------------------------------------------
#   FUNZIONE PER CARICARE IL VIDEO
# ---------------------------------------------
def upload_video(video_path: str, title: str, description: str) -> None:
    print("[Monday] Preparazione upload video...")

    youtube = get_youtube_service()

    # Metadata video
    body = {
        "snippet": {
            "title": title,
            "description": description,
            "tags": ["automation", "deadpan", "bot"]
        },
        "status": {
            "privacyStatus": "public"
        }
    }

    # Carica file
    media = MediaFileUpload(video_path, chunksize=-1, resumable=True)

    print("[Monday] Invio richiesta a YouTube...")
    request = youtube.videos().insert(
        part="snippet,status",
        body=body,
        media_body=media
    )

    response = request.execute()
    print(f"[Monday] ✅ Video caricato! ID: {response['id']}")
