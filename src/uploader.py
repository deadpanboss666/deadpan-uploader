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
    )

    response = request.execute()
    print("[Monday] Upload completato!")
    return response
