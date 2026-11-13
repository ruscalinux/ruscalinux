#!/usr/bin/env python3
# RuscaLinux — adwaita-gtk3-prugna.py — GPL-3.0
"""Genera il tema GTK 3 «Adwaita-Prugna» a partire dal tema Adwaita di GTK 3.

Il tema e' Adwaita cosi' com'e', con una sola differenza: il blu dell'accento
diventa il prugna/rosa di RuscaLinux (specifiche, sezione 4.1). Forme, grigi,
spaziature e colori semantici (errore, avviso, successo) non si toccano.

GTK 3 e' in sola manutenzione: il suo Adwaita non cambia piu', quindi il tema
generato resta valido con le versioni future di GNOME. Si rigenera solo se si
cambia la palette.

Uso:
    apt source gtk+3.0          # oppure i sorgenti di GTK 3.24 da gnome.org
    ./adwaita-gtk3-prugna.py gtk+3.0-*/gtk/theme/Adwaita

Scrive, accanto a questo script:
    Adwaita-Prugna/gtk-3.0/gtk.css         tema chiaro
    Adwaita-Prugna/gtk-3.0/gtk-dark.css    tema scuro
    Adwaita-Prugna/gtk-3.0/assets/         immagini (cursori dei regolatori,
                                           maniglie di selezione del testo)

I file generati derivano da GTK (LGPL-2.0-or-later): portano in testa la
provenienza e la licenza, e il file copyright del pacchetto li dichiara.
"""

import colorsys
import os
import re
import shutil
import sys

# --- Palette (specifiche, sezione 4.1) --------------------------------------
PRUGNA_600 = "#7a2357"   # accento su fondo chiaro; testo bianco sopra: 9,5:1
ROSA_300 = "#f2a7c8"     # tinta chiara verso cui tendono i toni piu' chiari
ROSA_250 = "#f5b8d3"     # testo d'accento (link) su fondo scuro

# Il blu d'accento di Adwaita in GTK 3 e' #3584e4 (chiaro) e #15539e (scuro):
# sono i due colori che diventano esattamente Prugna 600.

# Proprieta' che colorano testo: su fondo scuro devono restare chiare.
TEXT_PROPS = {"color", "caret-color", "-gtk-secondary-caret-color",
              "text-decoration-color"}

HEADER = """/* RuscaLinux — Adwaita-Prugna, tema GTK 3 ({variant})
 *
 * FILE GENERATO da branding/theme/adwaita-gtk3-prugna.py: non modificarlo
 * a mano. E' il tema Adwaita di GTK {gtk} (gtk/theme/Adwaita/{source})
 * con il blu dell'accento sostituito dal prugna/rosa di RuscaLinux.
 *
 * Opera derivata da GTK — Copyright (C) The GTK Team e i contributori di GTK.
 * Licenza: GNU Library General Public License, versione 2 o successiva
 * (LGPL-2.0-or-later). Su Debian: /usr/share/common-licenses/LGPL-2
 */
"""


def hex_to_rgb(text):
    text = text.lstrip("#")
    if len(text) == 3:
        text = "".join(ch * 2 for ch in text)
    return tuple(int(text[i:i + 2], 16) for i in (0, 2, 4))


def hls(rgb):
    return colorsys.rgb_to_hls(*(v / 255 for v in rgb))


P_H, P_L, P_S = hls(hex_to_rgb(PRUGNA_600))
R_H, R_L, R_S = hls(hex_to_rgb(ROSA_300))
ROSA_250_L = hls(hex_to_rgb(ROSA_250))[1]
ADW_ACCENT_L_LIGHT = hls(hex_to_rgb("#3584e4"))[1]
ADW_ACCENT_L_DARK = hls(hex_to_rgb("#15539e"))[1]


def is_accent_blue(rgb):
    """Vero per il blu dell'accento di Adwaita e le sue sfumature."""
    h, _l, s = hls(rgb)
    return 200 <= h * 360 <= 225 and s >= 0.2


def convert(rgb, dark, text=False):
    """Blu di Adwaita -> prugna/rosa, conservando i rapporti di luminosita'.

    Il blu d'accento diventa esattamente Prugna 600; i toni piu' scuri
    scendono in proporzione, quelli piu' chiari salgono verso Rosa 300.
    """
    _h, l, s = hls(rgb)
    anchor = ADW_ACCENT_L_DARK if dark else ADW_ACCENT_L_LIGHT
    if l <= anchor:
        new_l = l * P_L / anchor
    else:
        new_l = P_L + (l - anchor) / (1 - anchor) * (1 - P_L)
    if dark and text and new_l < 0.75:
        new_l = ROSA_250_L          # link e simili leggibili sul fondo scuro
    # Da Prugna 600 a Rosa 300 tinta e saturazione cambiano gradualmente.
    t = min(max((new_l - P_L) / (R_L - P_L), 0.0), 1.0)
    new_h = P_H + (R_H - P_H) * t
    new_s = P_S + (R_S - P_S) * t
    # Le sfumature gia' mescolate al grigio restano meno sature.
    new_s *= min(s / 0.76, 1.0)
    r, g, b = colorsys.hls_to_rgb(new_h, new_l, new_s)
    return tuple(round(v * 255) for v in (r, g, b))


COLOR_RE = re.compile(
    r"#(?P<hex>[0-9a-fA-F]{6}|[0-9a-fA-F]{3})\b"
    r"|(?P<fn>rgba?)\(\s*(?P<r>\d+)\s*,\s*(?P<g>\d+)\s*,\s*(?P<b>\d+)\s*(?P<rest>[^)]*)\)")
DECL_RE = re.compile(r"(?P<prop>[-\w]+)\s*:\s*(?P<value>[^;{}]*)")


def convert_value(value, dark, text):
    def repl(match):
        if match.group("hex"):
            rgb = hex_to_rgb(match.group("hex"))
            if not is_accent_blue(rgb):
                return match.group(0)
            return "#%02x%02x%02x" % convert(rgb, dark, text)
        rgb = tuple(int(match.group(k)) for k in "rgb")
        if not is_accent_blue(rgb):
            return match.group(0)
        return "%s(%d, %d, %d%s)" % ((match.group("fn"),)
                                     + convert(rgb, dark, text)
                                     + (match.group("rest"),))
    return COLOR_RE.sub(repl, value)


def convert_css(css, dark):
    out = []
    for line in css.splitlines():
        if line.startswith("@define-color"):
            # "@define-color nome valore;": qui non ci sono dichiarazioni.
            name = line.split()[1]
            text = dark and name.endswith(("link_color", "fg_color"))
            out.append(convert_value(line, dark, text))
            continue
        brace = line.find("{")
        if brace < 0:
            out.append(line)
            continue
        head, body = line[:brace], line[brace:]
        body = DECL_RE.sub(
            lambda m: "%s: %s" % (m.group("prop"), convert_value(
                m.group("value"), dark, m.group("prop") in TEXT_PROPS)), body)
        out.append(head + body)
    return "\n".join(out) + "\n"


def convert_png(src, dst, dark):
    from PIL import Image
    image = Image.open(src).convert("RGBA")
    pixels = image.load()
    cache = {}
    for y in range(image.height):
        for x in range(image.width):
            r, g, b, a = pixels[x, y]
            if a == 0 or not is_accent_blue((r, g, b)):
                continue
            if (r, g, b) not in cache:
                cache[(r, g, b)] = convert((r, g, b), dark)
            pixels[x, y] = cache[(r, g, b)] + (a,)
    image.save(dst, optimize=True)


def gtk_version(source):
    """Versione di GTK, letta da meson.build nella radice dei sorgenti."""
    meson = os.path.join(source, "..", "..", "..", "meson.build")
    try:
        with open(meson, encoding="utf-8") as handle:
            match = re.search(r"version\s*:\s*'(3\.[\d.]+)'", handle.read())
        return match.group(1) if match else "3.24"
    except OSError:
        return "3.24"


def main():
    if len(sys.argv) != 2 or not os.path.isfile(
            os.path.join(sys.argv[1], "gtk-contained.css")):
        print(__doc__)
        return 1
    source = sys.argv[1]
    here = os.path.dirname(os.path.realpath(__file__))
    target = os.path.join(here, "Adwaita-Prugna", "gtk-3.0")
    assets = os.path.join(target, "assets")
    shutil.rmtree(target, ignore_errors=True)
    os.makedirs(assets)
    version = gtk_version(source)

    for name, out_name, dark in (("gtk-contained.css", "gtk.css", False),
                                 ("gtk-contained-dark.css", "gtk-dark.css", True)):
        with open(os.path.join(source, name), encoding="utf-8") as handle:
            css = handle.read()
        header = HEADER.format(variant="scuro" if dark else "chiaro",
                               gtk=version, source=name)
        with open(os.path.join(target, out_name), "w", encoding="utf-8") as handle:
            handle.write(header + convert_css(css, dark))
        print("scritto", os.path.relpath(os.path.join(target, out_name), here))

    # Solo le immagini che il CSS usa davvero.
    used = set()
    for out_name in ("gtk.css", "gtk-dark.css"):
        with open(os.path.join(target, out_name), encoding="utf-8") as handle:
            used.update(re.findall(r'url\("assets/([^"]+)"\)', handle.read()))
    for name in sorted(used):
        src = os.path.join(source, "assets", name)
        dst = os.path.join(assets, name)
        if name.endswith(".png") and "symbolic" not in name:
            convert_png(src, dst, dark="-dark" in name)
        else:
            shutil.copyfile(src, dst)     # icone simboliche: le colora GTK
    print("scritte %d immagini in %s" % (len(used), os.path.relpath(assets, here)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
