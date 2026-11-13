#!/usr/bin/env python3
# =============================================================================
# RuscaLinux — generatore del tema GRUB
#
#   python3 branding/generators/ruscalinux-grub-theme.py [cartella-di-uscita]
#
# Crea anche il menu BIOS della ISO (isolinux): local/isolinux/splash.png e
# local/isolinux/stdmenu.cfg, nello stesso stile; e local/grub/splash.png,
# che nella ISO serve solo perche' theme.cfg di live-build attivi il tema.
#
# Crea il tema completo in local/grub/ruscalinux/ (o nella cartella
# indicata): immagine di fondo, fondo neutro per l'editor e la riga di
# comando (console.png), forme della voce selezionata, della barra del conto
# alla rovescia e della barra di scorrimento, font in formato GRUB (.pf2) e
# theme.txt. L'anteprima del menu (preview.png) va nella cartella superiore:
# serve solo per controllo e non deve finire nella ISO.
#
# In theme.txt la versione e' il segnaposto {{VERSION}}: lo sostituisce
# steps/30-custom.sh quando copia il tema nella build.
#
# Serve: python3-pil, librsvg2-bin (rsvg-convert), grub-common (grub-mkfont).
# Font: Syne e DM Sans da branding/fonts/DM_Sans,Syne.zip (OFL).
#
# Idea grafica: a sinistra, su fondo prugna scuro e uniforme, logo e menu, per
# la massima leggibilita'; a destra, la scena degli aeroplanini di carta del
# marchio, in volo verso l'alto. Il fondo scuro e' una scelta di leggibilita':
# GRUB non ha antialiasing sui bordi delle finestre e un fondo chiaro
# metterebbe in evidenza ogni imperfezione dei font bitmap.
#
# Il tema e' disegnato su 1920x1080 ma usa posizioni in percentuale: con
# GRUB_GFXMODE=1920x1080,auto la resa e' quella dell'anteprima sulla maggior
# parte degli schermi; a risoluzioni minori il menu resta proporzionato.
# =============================================================================
import os
import subprocess
import sys
import tempfile
import zipfile

from PIL import Image, ImageDraw, ImageFilter, ImageFont

QUI = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(QUI, "..", ".."))
USCITA = os.path.abspath(sys.argv[1]) if len(sys.argv) > 1 else \
    os.path.join(REPO, "local", "grub", "ruscalinux")

W, H = 1920, 1080

# --- Palette (specifiche, sezione 4.1) --------------------------------------
PRUGNA_950 = "#1a0510"   # bordi del fondo
PRUGNA_900 = "#2d0a1d"   # fondo della zona del menu, testo sulla selezione
PRUGNA_500 = "#8a2b5f"   # onde del marchio
ROSA_300 = "#f2a7c8"     # voce selezionata, barra del conto alla rovescia
ROSA_250 = "#f5b8d3"     # frase sotto il nome
CREMA = "#fff7f0"        # nome e voci del menu
VOCE = "#ecdbe4"         # voci non selezionate (crema appena attenuato)
TENUE = "#b994a9"        # conto alla rovescia, aiuto in basso
TRACCIA = "#4a1834"      # binario della barra di scorrimento

# Zona del menu: sinistra, larga meno di meta' schermo, cosi' le voci lunghe
# ("Live system (amd64) with NVIDIA driver") stanno su una riga.
# GRUB accetta solo percentuali intere: niente decimali qui sotto.
MENU = dict(left=0.08, top=0.28, width=0.46, height=0.54)
# Voce: GRUB disegna la barra della selezione FUORI dall'altezza della voce,
# con i bordi delle forme (SEL_BX ai lati, SEL_BY sopra e sotto). Passo fra
# una voce e l'altra: VOCE_ALTEZZA + VOCE_SPAZIO = 68 px; la barra selezionata
# e' alta VOCE_ALTEZZA + 2*SEL_BY = 60 px, quindi non tocca le voci vicine.
VOCE_ALTEZZA, VOCE_SPAZIO, VOCE_RIENTRO = 36, 32, 0
SEL_BX, SEL_BY, SEL_RAGGIO = 22, 12, 12
FONT_VOCE, FONT_TESTO = 28, 21


# =============================================================================
# Utilita'
# =============================================================================
def esadecimale(c, alfa=255):
    c = c.lstrip("#")
    return tuple(int(c[i:i + 2], 16) for i in (0, 2, 4)) + (alfa,)


def luminanza(c):
    def canale(v):
        v /= 255
        return v / 12.92 if v <= 0.03928 else ((v + 0.055) / 1.055) ** 2.4
    r, g, b = esadecimale(c)[:3]
    return 0.2126 * canale(r) + 0.7152 * canale(g) + 0.0722 * canale(b)


def contrasto(a, b):
    la, lb = sorted((luminanza(a), luminanza(b)), reverse=True)
    return (la + 0.05) / (lb + 0.05)


def font_marchio():
    """Estrae dallo zip i TTF che servono, in una cartella temporanea."""
    tmp = tempfile.mkdtemp(prefix="ruscalinux-font-")
    servono = {
        "Syne/static/Syne-ExtraBold.ttf": "syne-extrabold",
        "DM_Sans/static/DMSans-Regular.ttf": "dmsans-regular",
        "DM_Sans/static/DMSans-Medium.ttf": "dmsans-medium",
        "DM_Sans/static/DMSans-Bold.ttf": "dmsans-bold",
    }
    percorsi = {}
    with zipfile.ZipFile(os.path.join(REPO, "branding", "fonts", "DM_Sans,Syne.zip")) as z:
        for nome, chiave in servono.items():
            dest = os.path.join(tmp, os.path.basename(nome))
            with open(dest, "wb") as f:
                f.write(z.read(nome))
            percorsi[chiave] = dest
    return percorsi


def rsvg(svg, png, w, h):
    with tempfile.NamedTemporaryFile("w", suffix=".svg", delete=False) as f:
        f.write(svg)
    subprocess.run(["rsvg-convert", "-w", str(w), "-h", str(h), "-o", png, f.name], check=True)
    os.unlink(f.name)


# =============================================================================
# Fondo: la scena degli aeroplanini, a destra
# =============================================================================
# Stessa geometria dell'aeroplanino del generatore di sfondi e del logo: due
# falde, la coda e la piega centrale.
def aeroplanino(x, y, angolo, scala, opacita, sfocatura=0):
    filtro = f' filter="url(#sfoca{sfocatura})"' if sfocatura else ""
    return f'''
<g transform="translate({x:.1f},{y:.1f}) rotate({angolo:.1f}) scale({scala:.3f}) translate(-39,-22)" opacity="{opacita}"{filtro}>
  <polygon points="0,0 78,22 0,44 11,22" fill="{CREMA}" fill-opacity="0.95"/>
  <polygon points="78,22 0,44 11,22" fill="{CREMA}" fill-opacity="0.42"/>
  <polygon points="0,44 11,22 6,33" fill="{CREMA}" fill-opacity="0.7"/>
  <line x1="0" y1="0" x2="11" y2="22" stroke="{CREMA}" stroke-opacity="0.35" stroke-width="1.2"/>
</g>'''


def scia(d, larghezza, opacita):
    return (f'<path d="{d}" fill="none" stroke="url(#scia)" stroke-width="{larghezza}" '
            f'stroke-linecap="round" opacity="{opacita}"/>')


def fondo_svg(w=W, h=H, dx=0):
    """Fondo con la scena degli aeroplanini. w, h: dimensioni; dx sposta la
    scena (onde, puntini, scie, aerei) in orizzontale, per i formati piu'
    stretti come il 4:3 di isolinux."""
    # Le rotte salgono da sinistra in basso verso destra in alto: lo stesso
    # verso del generatore di sfondi. Nessun elemento entra nella zona del
    # menu (x < 0.55 W): li' il fondo resta uniforme.
    rotte = [
        # (curva della scia, posizione e angolo dell'aereo, scala, opacita', sfocatura)
        ("M 1060,840 C 1220,700 1290,520 1400,430", (1420, 418, -34, 1.75, 0.96, 0)),
        ("M 1500,560 C 1580,440 1640,330 1690,270", (1702, 258, -42, 0.95, 0.62, 1)),
        ("M 1240,960 C 1330,860 1390,790 1450,745", (1462, 737, -32, 0.62, 0.38, 2)),
        ("M 1700,520 C 1745,470 1775,430 1805,405", (1814, 398, -36, 0.45, 0.30, 2)),
    ]
    scie = "\n".join(scia(d, 2.2 if i == 0 else 1.6, 0.55 if i == 0 else 0.35)
                     for i, (d, _) in enumerate(rotte))
    aerei = "\n".join(aeroplanino(x, y, a, s, o, b) for _, (x, y, a, s, o, b) in rotte)

    # Puntini di luce: solo a destra, piu' fitti verso il bordo.
    import random
    rnd = random.Random(1992)
    stelle = []
    for _ in range(170):
        x = W * (0.56 + 0.44 * rnd.random() ** 0.7)
        y = H * rnd.random()
        r = rnd.choice([0.7, 0.9, 1.2, 1.6])
        o = round(rnd.uniform(0.10, 0.45) * (x / W), 3)
        stelle.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="{r}" fill="{CREMA}" opacity="{o}"/>')

    return f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}" width="{w}" height="{h}">
<defs>
  <linearGradient id="base" x1="0" y1="0" x2="1" y2="0">
    <stop offset="0%" stop-color="{PRUGNA_900}"/>
    <stop offset="52%" stop-color="{PRUGNA_900}"/>
    <stop offset="100%" stop-color="#3a0d26"/>
  </linearGradient>
  <radialGradient id="luce" cx="78%" cy="58%" r="48%">
    <stop offset="0%" stop-color="#b2477f" stop-opacity="0.55"/>
    <stop offset="100%" stop-color="#b2477f" stop-opacity="0"/>
  </radialGradient>
  <radialGradient id="vignetta" cx="40%" cy="45%" r="85%">
    <stop offset="60%" stop-color="{PRUGNA_950}" stop-opacity="0"/>
    <stop offset="100%" stop-color="{PRUGNA_950}" stop-opacity="0.85"/>
  </radialGradient>
  <linearGradient id="onda" gradientUnits="userSpaceOnUse" x1="1000" y1="1000" x2="1920" y2="150">
    <stop offset="0%" stop-color="{PRUGNA_500}" stop-opacity="0"/>
    <stop offset="40%" stop-color="#c4568c" stop-opacity="0.9"/>
    <stop offset="100%" stop-color="{PRUGNA_500}" stop-opacity="0"/>
  </linearGradient>
  <linearGradient id="scia" gradientUnits="userSpaceOnUse" x1="1050" y1="960" x2="1820" y2="380">
    <stop offset="0%" stop-color="{CREMA}" stop-opacity="0"/>
    <stop offset="100%" stop-color="{CREMA}" stop-opacity="0.85"/>
  </linearGradient>
  <filter id="nebbia" x="-50%" y="-50%" width="200%" height="200%"><feGaussianBlur stdDeviation="46"/></filter>
  <filter id="sfoca1" x="-40%" y="-40%" width="180%" height="180%"><feGaussianBlur stdDeviation="0.8"/></filter>
  <filter id="sfoca2" x="-40%" y="-40%" width="180%" height="180%"><feGaussianBlur stdDeviation="1.6"/></filter>
</defs>
<rect width="{w}" height="{h}" fill="url(#base)"/>
<rect width="{w}" height="{h}" fill="url(#luce)"/>
<g transform="translate({dx},0)">
<g filter="url(#nebbia)" opacity="0.55">
  <path d="M 980,1140 C 1260,900 1500,620 2040,240" fill="none" stroke="url(#onda)" stroke-width="210" stroke-linecap="round"/>
  <path d="M 1180,1160 C 1420,980 1640,760 2060,520" fill="none" stroke="url(#onda)" stroke-width="120" stroke-linecap="round"/>
</g>
{"".join(stelle)}
{scie}
{aerei}
</g>
<rect width="{w}" height="{h}" fill="url(#vignetta)"/>
</svg>'''


def fondo(font, png):
    rsvg(fondo_svg(), png, W, H)
    img = Image.open(png).convert("RGBA")

    # Testata in alto a sinistra: emblema bianco, nome, frase.
    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
        emblema_png = f.name
    subprocess.run(["rsvg-convert", "-h", "96",
                    os.path.join(REPO, "branding", "logos", "emblem-ruscalinux-white.svg"),
                    "-o", emblema_png], check=True)
    emblema = Image.open(emblema_png).convert("RGBA")
    os.unlink(emblema_png)
    x0 = round(W * MENU["left"])
    y0 = 92
    img.alpha_composite(emblema, (x0 - 10, y0))

    d = ImageDraw.Draw(img)
    nome = ImageFont.truetype(font["syne-extrabold"], 62)
    frase = ImageFont.truetype(font["dmsans-regular"], 24)
    xt = x0 - 10 + emblema.width + 22
    d.text((xt, y0 + 6), "ruscalinux", font=nome, fill=esadecimale(CREMA))
    d.text((xt + 2, y0 + 78), "Free, complete, and ready to go.", font=frase,
           fill=esadecimale(ROSA_250))

    # Filo sottile che separa testata e menu: un dettaglio "da strumento".
    yf = round(H * MENU["top"]) - 30
    d.line([(x0, yf), (x0 + round(W * MENU["width"]), yf)],
           fill=esadecimale(ROSA_300, 70), width=2)
    img.convert("RGB").save(png, optimize=True)


# =============================================================================
# isolinux (avvio BIOS della ISO): stesso disegno, a 640x480
# =============================================================================
# vesamenu scrive con un font fisso di 8x16 pixel: lo schermo e' una griglia
# di 80 colonne x 30 righe. Testata e filo sono allineati a quella griglia,
# e il menu parte dalla colonna ISO_COLONNA come il menu GRUB parte dall'8%.
ISO_W, ISO_H = 640, 480
ISO_COLONNA = 4          # menu hshift: 4 colonne = 32 px
ISO_RIGA_FILO = 7        # il filo sta sotto la riga 7 (y = 128 px)


def isolinux_splash(font, png):
    k = 1080 / ISO_H                       # si disegna a 1440x1080 e si riduce
    gw, gh = round(ISO_W * k), 1080
    rsvg(fondo_svg(gw, gh, dx=-300), png, gw, gh)
    img = Image.open(png).convert("RGBA")

    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
        emblema_png = f.name
    subprocess.run(["rsvg-convert", "-h", str(round(40 * k)),
                    os.path.join(REPO, "branding", "logos", "emblem-ruscalinux-white.svg"),
                    "-o", emblema_png], check=True)
    emblema = Image.open(emblema_png).convert("RGBA")
    os.unlink(emblema_png)
    # La barra di selezione parte dalla colonna ISO_COLONNA + 1 (dopo il
    # bordo invisibile): filo e testata si allineano a quella.
    x0 = round((ISO_COLONNA + 1) * 8 * k)
    y0 = round(40 * k)
    img.alpha_composite(emblema, (x0 - round(4 * k), y0))
    d = ImageDraw.Draw(img)
    nome = ImageFont.truetype(font["syne-extrabold"], round(26 * k))
    frase = ImageFont.truetype(font["dmsans-regular"], round(11 * k))
    xt = x0 - round(4 * k) + emblema.width + round(10 * k)
    d.text((xt, y0 + round(2 * k)), "ruscalinux", font=nome, fill=esadecimale(CREMA))
    d.text((xt + round(1 * k), y0 + round(31 * k)), "Free, complete, and ready to go.",
           font=frase, fill=esadecimale(ROSA_250))
    yf = round((ISO_RIGA_FILO + 1) * 16 * k) - round(6 * k)
    d.line([(x0, yf), (x0 + round(46 * 8 * k) - 1, yf)], fill=esadecimale(ROSA_300, 70),
           width=round(1 * k))
    img.convert("RGB").resize((ISO_W, ISO_H), Image.LANCZOS).save(png, optimize=True)


def argb(c, alfa="ff"):
    return "#" + alfa + c.lstrip("#").lower()


def isolinux_stdmenu():
    """stdmenu.cfg per vesamenu: lo includono il menu principale e tutti i
    sottomenu, quindi vale ovunque. Sostituisce quello di live-build."""
    trasp = "#00000000"
    return f"""# RuscaLinux — menu isolinux (avvio BIOS della ISO)
# Generato da branding/generators/ruscalinux-grub-theme.py: non modificare
# qui, rigenera. Lo installa l'hook 9010-ruscalinux-grub-theme.hook.binary.
menu background splash.png
menu color screen      * {trasp} {trasp} none
menu color border      * {trasp} {trasp} none
menu color title       * {trasp} {trasp} none
menu color unsel       * {argb(VOCE)} {trasp} none
menu color hotkey      * {argb(ROSA_250)} {trasp} none
menu color sel         * {argb(PRUGNA_900)} {argb(ROSA_300)} none
menu color hotsel      * {argb(PRUGNA_900)} {argb(ROSA_300)} none
menu color disabled    * {argb(TENUE)} {trasp} none
menu color scrollbar   * {argb(ROSA_300)} {argb(TRACCIA)} none
menu color tabmsg      * {argb(TENUE)} {trasp} none
menu color cmdmark     * {argb(ROSA_300)} {trasp} none
menu color cmdline     * {argb(VOCE)} {trasp} none
menu color timeout_msg * {argb(TENUE)} {trasp} none
menu color timeout     * {argb(ROSA_300)} {trasp} none
menu color help        * {argb(VOCE)} {trasp} none
menu width 48
menu margin 0
menu hshift {ISO_COLONNA - 1}
menu vshift {ISO_RIGA_FILO - 1}
menu rows 14
menu helpmsgrow 24
menu helpmsgendrow 25
menu cmdlinerow 25
menu timeoutrow 25
menu tabmsgrow 26
menu tabmsg Enter: start    Tab: edit the entry
"""


# =============================================================================
# Forme a nove pezzi (GRUB "styled box"): angoli arrotondati senza scaletta
# =============================================================================
def nove_pezzi(cartella, prefisso, colore, raggio, bx=None, by=None, trasparente=False):
    """Forma a nove pezzi per GRUB: angoli fissi, lati e centro stirati.

    GRUB disegna i pezzi del bordo FUORI dall'area del contenuto: bx e by
    sono quindi lo spazio che la forma aggiunge a sinistra/destra e
    sopra/sotto (per la voce selezionata: il rientro del testo e il margine
    verticale della barra). Il raggio non puo' superare by, altrimenti l'arco
    finirebbe nei lati, che GRUB stira.

    La forma si disegna 4 volte piu' grande e poi si riduce: cosi' gli
    angoli hanno l'antialiasing."""
    bx = raggio if bx is None else bx
    by = raggio if by is None else by
    assert raggio <= min(bx, by)
    k = 4
    lw, lh = bx * 2 + 1, by * 2 + 1
    grande = Image.new("RGBA", (lw * k, lh * k), (0, 0, 0, 0))
    ImageDraw.Draw(grande).rounded_rectangle([0, 0, lw * k - 1, lh * k - 1],
                                            radius=raggio * k,
                                            fill=esadecimale(colore, 0 if trasparente else 255))
    img = grande.resize((lw, lh), Image.LANCZOS)
    pezzi = {
        "nw": (0, 0, bx, by), "n": (bx, 0, bx + 1, by), "ne": (bx + 1, 0, lw, by),
        "w": (0, by, bx, by + 1), "c": (bx, by, bx + 1, by + 1), "e": (bx + 1, by, lw, by + 1),
        "sw": (0, by + 1, bx, lh), "s": (bx, by + 1, bx + 1, lh), "se": (bx + 1, by + 1, lw, lh),
    }
    for nome, box in pezzi.items():
        img.crop(box).save(os.path.join(cartella, f"{prefisso}_{nome}.png"))


# =============================================================================
# Font GRUB
# =============================================================================
# Latino di base ed esteso, trattini e puntini, frecce.
INTERVALLI = "0x20-0x7E,0xA0-0x17F,0x2010-0x2027,0x2190-0x2193"


def font_grub(ttf, dimensione, file_pf2):
    subprocess.run(["grub-mkfont", "-s", str(dimensione), "-r", INTERVALLI,
                    "-o", file_pf2, ttf], check=True)
    # Il nome con cui theme.txt richiama il font sta nella sezione NAME.
    dati = open(file_pf2, "rb").read()
    i = dati.index(b"NAME") + 8
    return dati[i:dati.index(b"\0", i)].decode()


# =============================================================================
# theme.txt
# =============================================================================
def theme_txt(f_voce, f_scelta, f_testo):
    m = MENU
    return f'''# RuscaLinux — tema GRUB
# Generato da branding/generators/ruscalinux-grub-theme.py: non modificare
# qui, rigenera. {{{{VERSION}}}} viene sostituito durante la build.

title-text: ""
desktop-image: "background.png"
desktop-image-scale-method: "crop"
desktop-color: "{PRUGNA_900}"
message-font: "{f_testo}"
message-color: "{VOCE}"

+ boot_menu {{
    left = {m["left"]*100:g}%
    top = {m["top"]*100:g}%
    width = {m["width"]*100:g}%
    height = {m["height"]*100:g}%
    item_font = "{f_voce}"
    selected_item_font = "{f_scelta}"
    item_color = "{VOCE}"
    selected_item_color = "{PRUGNA_900}"
    item_height = {VOCE_ALTEZZA}
    item_spacing = {VOCE_SPAZIO}
    item_padding = {VOCE_RIENTRO}
    icon_width = 0
    icon_height = 0
    item_icon_space = 0
    item_pixmap_style = "item_*.png"
    selected_item_pixmap_style = "select_*.png"
    scrollbar = true
    scrollbar_width = 6
    scrollbar_frame = "scrollbar_frame_*.png"
    scrollbar_thumb = "scrollbar_thumb_*.png"
}}

# Conto alla rovescia sotto il menu: GRUB lo mostra solo quando c'e' un
# tempo di attesa. Niente barra: GRUB le impone un'altezza minima di circa
# 28 px, troppo pesante per questo disegno.
+ label {{
    id = "__timeout__"
    left = {m["left"]*100:g}%
    top = 84%
    width = 40%
    height = 30
    font = "{f_testo}"
    color = "{TENUE}"
    text = "Starting the selected entry in %d s"
}}

# Aiuto e versione, in basso.
+ label {{
    left = {m["left"]*100:g}%
    top = 92%
    width = 60%
    height = 30
    font = "{f_testo}"
    color = "{TENUE}"
    text = "↑ ↓  Select      Enter  Start      E  Edit      C  Command line"
}}
+ label {{
    left = 72%
    top = 92%
    width = 20%
    height = 30
    align = "right"
    font = "{f_testo}"
    color = "{TENUE}"
    text = "RuscaLinux {{{{VERSION}}}}"
}}
'''


# =============================================================================
# Anteprima: il menu disegnato come lo disegna GRUB (solo per controllo)
# =============================================================================
VOCI_ANTEPRIMA = [
    "Live system (amd64)",
    "Live system (amd64) with NVIDIA driver",
    "Live system (amd64 fail-safe mode)",
    "Start installer",
    "Start installer with NVIDIA driver",
    "Start installer with speech synthesis",
    "Advanced install options ...",
    "Utilities ...",
]


def anteprima(font, cartella, png):
    """Ridisegna il menu come lo disegna GRUB: la barra della selezione
    sporge di SEL_BY sopra e sotto la voce e il testo rientra di SEL_BX."""
    img = Image.open(os.path.join(cartella, "background.png")).convert("RGBA")
    d = ImageDraw.Draw(img)
    voce = ImageFont.truetype(font["dmsans-medium"], FONT_VOCE)
    scelta = ImageFont.truetype(font["dmsans-bold"], FONT_VOCE)
    testo = ImageFont.truetype(font["dmsans-regular"], FONT_TESTO)
    x = round(W * MENU["left"])
    y = round(H * MENU["top"]) + SEL_BY
    larghezza = round(W * MENU["width"]) - 2 * SEL_BX - 6
    pill = Image.new("RGBA", (larghezza + 2 * SEL_BX, VOCE_ALTEZZA + 2 * SEL_BY), (0, 0, 0, 0))
    ImageDraw.Draw(pill).rounded_rectangle([0, 0, pill.width - 1, pill.height - 1],
                                           radius=SEL_RAGGIO, fill=esadecimale(ROSA_300))
    for i, t in enumerate(VOCI_ANTEPRIMA):
        yy = y + i * (VOCE_ALTEZZA + VOCE_SPAZIO)
        if i == 0:
            img.alpha_composite(pill, (x, yy - SEL_BY))
        f = scelta if i == 0 else voce
        alto = f.getbbox("Ag")
        ty = yy + (VOCE_ALTEZZA - (alto[3] - alto[1])) // 2 - alto[1]
        d.text((x + SEL_BX, ty), t, font=f, fill=esadecimale(PRUGNA_900 if i == 0 else VOCE))
    d.text((x, round(H * 0.84)), "Starting the selected entry in 5 s", font=testo,
           fill=esadecimale(TENUE))
    d.text((x, round(H * 0.92)),
           "↑ ↓  Select      Enter  Start      E  Edit      C  Command line",
           font=testo, fill=esadecimale(TENUE))
    v = "RuscaLinux 1.99.3"
    d.text((round(W * 0.92) - d.textlength(v, font=testo), round(H * 0.92)), v,
           font=testo, fill=esadecimale(TENUE))
    img.convert("RGB").save(png, optimize=True)


# =============================================================================
def main():
    os.makedirs(USCITA, exist_ok=True)
    font = font_marchio()

    print("Contrasti (WCAG, minimo 4,5:1 per il testo):")
    for nome, a, b in [("voci", VOCE, PRUGNA_900), ("voce selezionata", PRUGNA_900, ROSA_300),
                       ("aiuto e conto alla rovescia", TENUE, PRUGNA_900),
                       ("frase sotto il nome", ROSA_250, PRUGNA_900)]:
        print(f"  {nome:30s} {contrasto(a, b):5.1f}:1")

    fondo(font, os.path.join(USCITA, "background.png"))
    nove_pezzi(USCITA, "select", ROSA_300, SEL_RAGGIO, SEL_BX, SEL_BY)
    # Stessi bordi, ma trasparente: GRUB sposta il testo di ogni voce in base
    # ai bordi della sua forma. Con questa le voci non selezionate hanno lo
    # stesso spostamento di quella selezionata, e il testo non "salta".
    nove_pezzi(USCITA, "item", "#000000", SEL_RAGGIO, SEL_BX, SEL_BY, trasparente=True)
    nove_pezzi(USCITA, "scrollbar_frame", TRACCIA, 3)
    nove_pezzi(USCITA, "scrollbar_thumb", ROSA_300, 3)

    f_voce = font_grub(font["dmsans-medium"], FONT_VOCE, os.path.join(USCITA, "dmsans-medium-28.pf2"))
    f_scelta = font_grub(font["dmsans-bold"], FONT_VOCE, os.path.join(USCITA, "dmsans-bold-28.pf2"))
    f_testo = font_grub(font["dmsans-regular"], FONT_TESTO, os.path.join(USCITA, "dmsans-regular-21.pf2"))
    print(f"Font GRUB: {f_voce} / {f_scelta} / {f_testo}")

    testo = theme_txt(f_voce, f_scelta, f_testo)
    import re
    if re.search(r"\d+\.\d+%", testo):
        sys.exit("ERRORE: theme.txt contiene percentuali con decimali, che GRUB rifiuta")
    with open(os.path.join(USCITA, "theme.txt"), "w", encoding="utf-8") as f:
        f.write(testo)

    console = Image.new("RGB", (W, H), esadecimale(PRUGNA_900)[:3])
    console.save(os.path.join(USCITA, "console.png"), optimize=True)

    anteprima(font, USCITA, os.path.join(os.path.dirname(USCITA), "preview.png"))

    # local/grub/splash.png: nella ISO va in boot/grub/splash.png. Non si
    # vede (il menu usa il tema), ma theme.cfg di live-build attiva il tema
    # solo se il file esiste: e' lo stesso fondo del tema, cosi' resta coerente.
    os.makedirs(os.path.join(REPO, "local", "grub"), exist_ok=True)
    Image.open(os.path.join(USCITA, "background.png")).save(
        os.path.join(REPO, "local", "grub", "splash.png"), optimize=True)

    # Menu BIOS (isolinux): immagine e colori, accanto agli altri file
    # d'avvio della ISO.
    iso = os.path.join(REPO, "local", "isolinux")
    os.makedirs(iso, exist_ok=True)
    isolinux_splash(font, os.path.join(iso, "splash.png"))
    with open(os.path.join(iso, "stdmenu.cfg"), "w", encoding="utf-8") as f:
        f.write(isolinux_stdmenu())
    print(f"Menu isolinux scritto in {iso}")
    print(f"Tema scritto in {USCITA}")


if __name__ == "__main__":
    main()
