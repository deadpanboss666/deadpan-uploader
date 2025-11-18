import os
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]
TOKEN_PATH = "src/token.json"
CLIENT_SECRET = "src/client_secret.json"


def get_youtube_service():
    creds = None
    if os.path.exists(TOKEN_PATH):
        from google.oauth2.credentials import Credentials
        creds = Credentials.from_authorized_user_file(TOKEN_PATH, SCOPES)
    else:
        flow = InstalledAppFlow.from_client_secrets_file(CLIENT_SECRET, SCOPES)
        creds = flow.run_local_server(port=8080)
        with open(TOKEN_PATH, "w") as token:
            token.write(creds.to_json())

    return build("youtube", "v3", credentials=creds)


def upload_video(file_path: str, title: str, description: str = "", tags=None, privacy="unlisted", thumbnail_path=None):
    if tags is None:
        tags = []

    youtube = get_youtube_service()

    request_body = {
        "snippet": {
            "title": title,
            "description": description,
            "tags": tags
        },
        "status": {
            "privacyStatus": privacy
        }
    }

    media = MediaFileUpload(file_path, chunksize=-1, resumable=True)

    request = youtube.videos().insert(
        part="snippet,status",
        body=request_body,
        media_body=media
    )

    print(f"\n[Monday] Inizio upload del video: {file_path}")

    response = None
    while response is None:
        status, response = request.next_chunk()
        if status:
            print(f"Caricamento: {int(status.progress() * 100)}%")

    print("\n[Monday] Upload completato!")
    video_id = response.get("id")
    print(f"Video ID: {video_id}")

    if thumbnail_path:
        set_thumbnail(youtube, video_id, thumbnail_path)

    return video_id


def set_thumbnail(youtube, video_id: str, thumbnail_path: str):
    print("[Monday] Carico la thumbnail...")
    youtube.thumbnails().set(
        videoId=video_id,
        media_body=MediaFileUpload(thumbnail_path)
    ).execute()
    print("[Monday] Thumbnail caricata!")
