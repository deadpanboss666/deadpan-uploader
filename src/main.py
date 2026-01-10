# -----------------------------------------
# main.py — Monday
# Script principale di upload automatico
# -----------------------------------------

import os
from uploader import upload_video
from subtitles import add_burned_in_subtitles


def main():
    print("[Monday] Avvio upload automatico...")

    # Percorso del video di input (generato dall'AI)
    video_path = "videos_to_upload/video.mp4"

    # File opzionale con il testo dei sottotitoli
    subtitles_text_path = "videos_to_upload/subtitles.txt"

    # Titolo e descrizione del video (per ora fissi)
    title = "Video Caricato Automaticamente"
    description = "Upload automatico tramite GitHub Actions"

    # Testo per i sottotitoli:
    # se esiste subtitles.txt lo usiamo, altrimenti usiamo la description
    if os.path.exists(subtitles_text_path):
        print("[Monday] Trovato subtitles.txt, uso quello per i sottotitoli...")
        with open(subtitles_text_path, "r", encoding="utf-8") as f:
            script_text = f.read().strip()
    else:
        print("[Monday] Nessun subtitles.txt trovato, uso la description come sottotitolo...")
        script_text = description

    # Controllo esistenza file video
    if not os.path.exists(video_path):
        print(f"[Monday] ERRORE: Il file video non esiste: {video_path}")
        return

    print("[Monday] Generazione video con sottotitoli bruciati...")
    # Crea un nuovo file video con sottotitoli (es: video_subs.mp4)
    video_path = add_burned_in_subtitles(
        video_path=video_path,
        script_text=script_text,
    )

    print("[Monday] Preparazione upload...")

    # Esegui upload del video (con o senza sottotitoli, a seconda di ffmpeg)
    upload_video(video_path, title, description)


if __name__ == "__main__":
    main()
