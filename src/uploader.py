import os
import json
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

def get_youtube_service():
    # Service account key JSON viene preso dal secret GitHub Actions
    key_content = os.getenv("GOOGLE_SERVICE_ACCOUNT_KEY")

    if not key_content:
        raise Exception("Environment variable GOOGLE_SERVICE_ACCOUNT_KEY is missing.")

    # Carica JSON da stringa
    info = json.loads(key_content)

    # Scope richiesti per YouTube upload
    scopes = ["https://www.googleapis.com/auth/youtube.upload"]

    credentials = service_account.Credentials.from_service_account_info(info, scopes=scopes)

    service = build("youtube", "v3", credentials=credentials)
    return service


def upload_video():
    youtube = get_youtube_service()

    video_path = "videos_to_upload/video.mp4"
    title = "Video caricato automaticamente"
    description = "Upload automatico tramite GitHub Actions"
    tags = ["automation", "github", "bot"]

    request_body = {
        "snippet": {
            "categoryId": "22",
            "title": title,
            "description": description,
            "tags": tags
        },
        "status": {
            "privacyStatus": "unlisted"
        }
    }

    media = MediaFileUpload(video_path, chunksize=-1, resumable=True)

    request = youtube.videos().insert(
        part="snippet,status",
        body=request_body,
        media_body=media
    )

    response = request.execute()
    print("Upload completato. Video ID:", response.get("id"))

    return response.get("id")
