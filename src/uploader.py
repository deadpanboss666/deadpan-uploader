"""
Uploader per YouTube basato SOLO su OAuth (client_secret.json + token.json).

Viene usato sia in locale che su GitHub Actions.
- In locale, se token.json non esiste, apre il flusso OAuth nel browser.
- Su GitHub Actions, token.json esiste già (lo ricostruiamo dai secret) e il codice
  usa solo il refresh token, senza aprire nessun browser.
"""

from __future__ import annotations

from pathlib import Path
from typing import List, Optional

from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow

# Cartella src/
BASE_DIR = Path(__file__).resolve().parent

# File OAuth (quelli che abbiamo anche in Base64 nei secrets GitHub)
CLIENT_SECRET_FILE = BASE_DIR / "client_secret.json"
TOKEN_FILE = BASE_DIR / "token.json"

# Scope necessario per upload su YouTube
SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]


def _get_oauth_credentials() -> Credentials:
    """Carica le credenziali OAuth da token.json, eventualmente le refresh-a.

    - In locale, se token.json non esiste, avvia il flusso OAuth nel browser.
    - Su GitHub Actions ci aspettiamo che token.json esista già.
    """
    creds: Optional[Credentials] = None

    if TOKEN_FILE.exists():
        # Carica il token esistente
        creds = Credentials.from_authorized_user_file(str(TOKEN_FILE), SCOPES)

    # Se non sono valide, prova a fare refresh o avvia il flow
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            # Caso GitHub / locale dopo un po' di tempo:
            # usa il refresh token per ottenere un nuovo access token
            creds.refresh(Request())
        else:
            # SOLO uso locale (su GitHub questo non dovrebbe mai servire)
            flow = InstalledAppFlow.from_client_secrets_file(
                str(CLIENT_SECRET_FILE),
                SCOPES,
            )
            creds = flow.run_local_server(port=0)

        # Salva sempre il token aggiornato
        TOKEN_FILE.write_text(creds.to_json(), encoding="utf-8")

    return creds


def _get_youtube_service():
    """Crea il client YouTube autenticato con OAuth."""
    creds = _get_oauth_credentials()
    return build("youtube", "v3", credentials=creds)


def upload_video(
    video_path: str | Path,
    title: str,
    description: str,
    tags: Optional[List[str]] = None,
    privacy_status: str = "unlisted",
) -> str:
    """Carica un video su YouTube e restituisce l'ID del video."""
    video_path = str(Path(video_path))

    youtube = _get_youtube_service()

    body = {
        "snippet": {
            "title": title,
            "description": description,
            "tags": tags or [],
            "categoryId": "27",  # Education
        },
        "status": {
            "privacyStatus": privacy_status,
        },
    }

    try:
        print("Inizio upload...")
        request = youtube.videos().insert(
            part="snippet,status",
            body=body,
            media_body=video_path,
        )
        response = request.execute()
        video_id = response["id"]
        print(f"✅ Upload completato. ID video: {video_id}")
        return video_id
    except HttpError as e:
        print(f"❌ Errore durante l'upload: {e}")
        raise


if __name__ == "__main__":
    # Test locale manuale (non usato nel workflow GitHub)
    dummy_path = BASE_DIR / "video.mp4"
    if dummy_path.exists():
        upload_video(
            video_path=dummy_path,
            title="Test upload YouTube (OAuth only)",
            description="Upload di test eseguito da uploader.py",
            tags=["test", "automation"],
            privacy_status="unlisted",
        )
    else:
        print(f"Nessun file di test trovato: {dummy_path}")
