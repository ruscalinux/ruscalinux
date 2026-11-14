#!/usr/bin/env python3
# =============================================================================
# RuscaLinux — banner dell'installer grafico, con la versione
#
#   python3 branding/generators/ruscalinux-banner.py VERSIONE [file-di-uscita]
#
# Lo lancia build.sh a ogni build, con VERSION di release.conf: il banner
# (800x75, in alto nelle schermate dell'installer) porta sempre la versione
# della ISO che si sta costruendo. Senza file di uscita scrive .gen/banner.png.
#
# Parte da local/banner-base.png, che e' il banner senza versione: fondo,
# emblema, nome e frase. Qui si aggiungono la targhetta con la versione, a
# destra, e la linea sotto il nome, che si ferma prima della targhetta.
#
# Il disegno e' quello di ruscalinux-banner-generator.html (stesse misure e
# stessi colori). Se cambia il disegno, banner-base.png si rifa' da li':
# esporta il PNG lasciando vuoto il campo della versione e togliendo la linea
# sotto il nome (<line x1="92" ...>), che qui viene ridisegnata.
#
# Serve: python3-pil. Font: Syne Bold da branding/fonts/DM_Sans,Syne.zip (OFL).
# =============================================================================
import io
import os
import sys
import zipfile

from PIL import Image, ImageDraw, ImageFilter, ImageFont

QUI = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(QUI, "..", ".."))
BASE = os.path.join(REPO, "local", "banner-base.png")
FONT_ZIP = os.path.join(REPO, "branding", "fonts", "DM_Sans,Syne.zip")

W, H = 800, 75
K = 4                     # si disegna 4 volte piu' grande, poi si riduce

# Misure e colori del generatore HTML (gruppo "version-group").
MARGINE_DESTRO = 792      # bordo destro della targhetta
TARGA_Y, TARGA_H, TARGA_RAGGIO = 19, 29, 6
TARGA_RIENTRO = 14        # spazio fra il bordo della targhetta e il testo
TARGA_COLORE = (0x4a, 0x10, 0x30, round(255 * 0.88))
TESTO_COLORE = (0xf5, 0xc2, 0xda, 255)
TESTO_CORPO = 17
OMBRA = dict(sfocatura=1.5, dy=1, opacita=0.28)
LINEA = dict(x1=92, y=46.5, spessore=0.6, opacita=0.18, distanza=8)


def main():
    if len(sys.argv) < 2 or not sys.argv[1].strip():
        sys.exit("uso: ruscalinux-banner.py VERSIONE [file-di-uscita]")
    etichetta = "v" + sys.argv[1].strip()
    uscita = sys.argv[2] if len(sys.argv) > 2 else os.path.join(REPO, ".gen", "banner.png")

    base = Image.open(BASE).convert("RGBA")
    if base.size != (W, H):
        sys.exit(f"ERRORE: {BASE} e' {base.size[0]}x{base.size[1]}, deve essere {W}x{H}")

    with zipfile.ZipFile(FONT_ZIP) as z:
        font = ImageFont.truetype(io.BytesIO(z.read("Syne/static/Syne-Bold.ttf")), TESTO_CORPO * K)

    # Larghezza della targhetta dal testo, come nel generatore.
    larghezza_testo = font.getlength(etichetta) / K
    targa_w = int(-(-(larghezza_testo + 2 * TARGA_RIENTRO) // 1))
    targa_x = MARGINE_DESTRO - targa_w
    if targa_x < 560:
        sys.exit(f"ERRORE: la versione '{etichetta}' e' troppo lunga per il banner")

    forme = Image.new("RGBA", (W * K, H * K), (0, 0, 0, 0))
    d = ImageDraw.Draw(forme)

    # Linea sotto il nome, fino a poco prima della targhetta.
    y = LINEA["y"] * K
    d.line([(LINEA["x1"] * K, y), ((targa_x - LINEA["distanza"]) * K, y)],
           fill=(255, 255, 255, round(255 * LINEA["opacita"])),
           width=max(1, round(LINEA["spessore"] * K)))

    # Targhetta.
    d.rounded_rectangle([targa_x * K, TARGA_Y * K,
                         (targa_x + targa_w) * K - 1, (TARGA_Y + TARGA_H) * K - 1],
                        radius=TARGA_RAGGIO * K, fill=TARGA_COLORE)

    # Testo, allineato a destra e centrato in altezza sulla targhetta.
    testo = Image.new("RGBA", forme.size, (0, 0, 0, 0))
    dt = ImageDraw.Draw(testo)
    dt.text(((MARGINE_DESTRO - TARGA_RIENTRO) * K, (TARGA_Y + TARGA_H / 2) * K),
            etichetta, font=font, fill=TESTO_COLORE, anchor="rm")

    # Ombra del testo: la sua sagoma, sfocata e spostata in basso.
    alfa = testo.getchannel("A").filter(ImageFilter.GaussianBlur(OMBRA["sfocatura"] * K))
    alfa = alfa.point(lambda v: round(v * OMBRA["opacita"]))
    ombra = Image.new("RGBA", forme.size, (0, 0, 0, 0))
    ombra.paste(Image.new("RGBA", forme.size, (0, 0, 0, 255)), (0, OMBRA["dy"] * K), alfa)

    for strato in (ombra, testo):
        forme = Image.alpha_composite(forme, strato)
    banner = Image.alpha_composite(base, forme.resize((W, H), Image.LANCZOS))

    os.makedirs(os.path.dirname(os.path.abspath(uscita)), exist_ok=True)
    banner.save(uscita, optimize=True)
    print(f"    Banner dell'installer: {etichetta} -> {os.path.relpath(uscita, REPO)}")


if __name__ == "__main__":
    main()
