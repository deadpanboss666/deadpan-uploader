import os
import json
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload


def get_youtube_service():
    """
    Restituisce un client YouTube autenticato usando
    il service account caricato come secret GitHub.
    """

    # Carichiamo il JSON dal secret GCP_SERVICE_ACCOUNT_JSON
    info = json.loads(os.environ["GCP_SERVICE_ACCOUNT_JSON"])

    # Creiamo le credenziali dal JSON
    creds = service_account.Credentials.from_service_account_info(
        info,
        scopes=["https://www.googleapis.com/auth/youtube.upload"]
    )

    # Costruiamo il client YouTube
    return build("youtube", "v3", credentials=creds)


def upload_video():
    """
    Carica automaticamente il video presente nella cartella:
    src/video.mp4
    """

    video_path = "src/video.mp4"

    if not os.path.exists(video_path):
        print("[Monday] ERRORE: Il file del video non esiste:", video_path)
        return None

    youtube = get_youtube_service()

    # Metadata del video
    request_body = {
        "snippet": {
            "title": "Video caricato automaticamente",
            "description": "Upload automatico tramite GitHub Actions",
            "tags": ["auto-upload", "github-actions"],
            "categoryId": "22"  # People & Blogs (default)
        },
        "status": {
            "privacyStatus": "public"
        }
    }

    media = MediaFileUpload(video_path, chunksize=-1, resumable=True)

    print("[Monday] Upload del video iniziato...")

    request = youtube.videos().insert(
        part="snippet,status",
        body=request_body,
        media_body=media
    )

    response = request.execute()

    print("[Monday] Upload completato!")
    print("[Monday] Video ID:", response.get("id"))

    return response.get("id")


if __name__ == "__main__":
    print("[Monday] Avvio upload automatico...")
    upload_video()
