from pathlib import Path
import random

from PIL import Image, ImageDraw, ImageFilter


def _hex_to_rgb(h: str) -> tuple[int, int, int]:
    h = h.lstrip("#")
    return tuple(int(h[i:i+2], 16) for i in (0, 2, 4))


def _choose_palette(text: str) -> tuple[tuple[int, int, int], tuple[int, int, int]]:
    """
    Sceglie una coppia di colori (alto -> basso) in base alle parole chiave del testo.
    """
    t = text.lower()

    if any(w in t for w in ["blood", "murder", "kill", "knife", "stab"]):
        # rosso sangue + nero
        return _hex_to_rgb("#220000"), _hex_to_rgb("#640000")

    if any(w in t for w in ["missing", "disappeared", "vanished", "lost"]):
        # blu freddo / caso irrisolto
        return _hex_to_rgb("#020b1f"), _hex_to_rgb("#12324f")

    if any(w in t for w in ["hospital", "asylum", "clinic"]):
        # verde malato
        return _hex_to_rgb("#02110b"), _hex_to_rgb("#0b3b2b")

    if any(w in t for w in ["police", "case file", "detective", "evidence"]):
        # blu/grigio investigativo
        return _hex_to_rgb("#050712"), _hex_to_rgb("#1c2538")

    if any(w in t for w in ["ghost", "haunted", "spirit", "curse"]):
        # viola spettrale
        return _hex_to_rgb("#0a0210"), _hex_to_rgb("#35123b")

    # fallback: palette oscura casuale tra alcune opzioni
    palettes = [
        ("#050505", "#262626"),  # grigio cemento
        ("#020308", "#1a1022"),  # blu/viola notturno
        ("#060102", "#3b1212"),  # rosso scuro
    ]
    top_hex, bottom_hex = random.choice(palettes)
    return _hex_to_rgb(top_hex), _hex_to_rgb(bottom_hex)


def _make_gradient(width: int, height: int, top_color, bottom_color) -> Image.Image:
    """
    Crea un semplice gradiente verticale scuro.
    """
    img = Image.new("RGB", (width, height), top_color)
    draw = ImageDraw.Draw(img)

    for y in range(height):
        ratio = y / max(1, height - 1)
        r = int(top_color[0] * (1 - ratio) + bottom_color[0] * ratio)
        g = int(top_color[1] * (1 - ratio) + bottom_color[1] * ratio)
        b = int(top_color[2] * (1 - ratio) + bottom_color[2] * ratio)
        draw.line([(0, y), (width, y)], fill=(r, g, b))

    return img


def _add_vignette(img: Image.Image) -> Image.Image:
    """
    Aggiunge una vignettatura scura ai bordi per effetto più cinematografico.
    """
    width, height = img.size
    vignette = Image.new("L", (width, height), 0)
    draw = ImageDraw.Draw(vignette)

    # ellisse centrale chiara, bordi scuri
    draw.ellipse(
        [
            (int(width * 0.05), int(height * 0.05)),
            (int(width * 0.95), int(height * 0.95)),
        ],
        fill=255,
    )

    vignette = vignette.filter(ImageFilter.GaussianBlur(radius=80))
    img = img.convert("RGB")
    dark_layer = Image.new("RGB", (width, height), (0, 0, 0))
    img = Image.composite(img, dark_layer, vignette.point(lambda v: 255 - v))

    return img


def _add_noise(img: Image.Image, intensity: int = 12) -> Image.Image:
    """
    Aggiunge una leggera grana per evitare fondo troppo piatto.
    """
    import random as rnd

    width, height = img.size
    pixels = img.load()
    for _ in range(width * height // 40):
        x = rnd.randrange(0, width)
        y = rnd.randrange(0, height)
        r, g, b = pixels[x, y]
        delta = rnd.randint(-intensity, intensity)
        nr = max(0, min(255, r + delta))
        ng = max(0, min(255, g + delta))
        nb = max(0, min(255, b + delta))
        pixels[x, y] = (nr, ng, nb)

    return img


def generate_background(text: str, output_path: Path) -> Path:
    """
    Genera uno sfondo 1536x1024 in locale, dark, basato sul testo del caso.
    Nessuna chiamata API, nessun costo.
    """
    width, height = 1536, 1024

    top_color, bottom_color = _choose_palette(text)
    img = _make_gradient(width, height, top_color, bottom_color)
    img = _add_vignette(img)
    img = _add_noise(img, intensity=16)

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    img.save(output_path, format="JPEG", quality=90)
    print(f"Sfondo generato localmente in {output_path}")
    return output_path
