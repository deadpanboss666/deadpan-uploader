import os

def upload_files():
    folder = os.path.join(os.getcwd(), 'files_to_upload')
    if not os.path.exists(folder):
        print("? Cartella 'files_to_upload' non trovata.")
        return

    files = os.listdir(folder)
    if not files:
        print("?? Nessun file da caricare.")
        return

    print(f"?? Trovati {len(files)} file:")
    for file in files:
        path = os.path.join(folder, file)
        print(f"?? Caricamento simulato di: {file} -> {path}")

