# -----------------------------------------
# main.py — Monday
# Script principale di upload automatico
# -----------------------------------------

import os
from uploader import upload_video
from subtitles import add_burned_in_subtitles


def main():
    print("[Monday] Avvio upload automatico...")

    # Video di input (generato dall'AI)
    original_video_path = "videos_to_upload/video.mp4"

    # File di testo con i sottotitoli (una riga = una “frase” a schermo)
    subtitles_txt_path = "videos_to_upload/subtitles.txt"

    # Titolo e descrizione base (poi li ottimizziamo per CTR)
    title = "Short generato automaticamente"
    description = "Video generato e caricato in automatico da Creator Automatico (Monday)."

    # Controllo esistenza video
    if not os.path.exists(original_video_path):
        print(f"[Monday] ERRORE: Il file video non esiste: {original_video_path}")
        return

    print("[Monday] Generazione video con sottotitoli bruciati...")

    # Prova ad aggiungere i sottotitoli bruciati;
    # se qualcosa va storto, torna il path originale.
    video_path_for_upload = add_burned_in_subtitles(
        original_video_path,
        subtitles_txt_path=subtitles_txt_path,
    )

    print("[Monday] Preparazione upload...")

    # Upload su YouTube
    upload_video(video_path_for_upload, title, description)

    print("[Monday] Fine pipeline.")


if __name__ == "__main__":
    main()
