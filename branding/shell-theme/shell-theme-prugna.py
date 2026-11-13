#!/usr/bin/env python3
# RuscaLinux — shell-theme-prugna.py — GPL-3.0
"""Genera il tema di GNOME Shell «Adwaita-Prugna» dai sorgenti di GNOME Shell.

Il tema NON sostituisce il foglio di stile di GNOME Shell: e' uno strato di
soli colori che la Shell carica sopra il proprio (estensione ufficiale User
Themes). Forme, misure, caratteri e animazioni restano quelli di GNOME.

Cambia solo i colori neutri della Shell (specifiche, sezione 4.1):
    barra in alto                      Prugna 900  #2d0a1d
    menu, calendario, notifiche        Prugna 800  #3a1028
    Attivita' e riquadri a schermo     Prugna 850  #230716 (schiarito da GNOME)
    testo                              Crema       #fff7f0
L'accento (interruttori, cursori, selezione) resta quello di sistema, e i
colori di errore, avviso e successo restano quelli di GNOME.

Va rigenerato a ogni nuova versione maggiore di GNOME (per Debian Stable:
a ogni nuova Debian). Se GNOME ha rinominato una delle variabili, lo script
si ferma e dice quale.

Uso (serve sassc):
    apt source gnome-shell
    ./shell-theme-prugna.py gnome-shell-*/data/theme

Scrive, accanto a questo script:
    Adwaita-Prugna/gnome-shell/gnome-shell.css
    GNOME_SHELL_VERSION            la versione maggiore per cui e' generato
"""

import colorsys
import os
import re
import shutil
import subprocess
import sys
import tempfile

PRUGNA_900 = "#2d0a1d"
PRUGNA_850 = "#230716"
PRUGNA_800 = "#3a1028"
CREMA = "#fff7f0"

# (file, riga originale, riga nuova). Ogni riga originale deve esistere una
# volta sola: se una versione futura di GNOME la cambia, lo script si ferma.
PATCHES = [
    ("gnome-shell-sass/_default-colors.scss",
     "$_base_color_dark: #222226;",
     "$_base_color_dark: %s;" % PRUGNA_850),
    ("gnome-shell-sass/_default-colors.scss",
     "$_base_color_light: #fafafb;",
     "$_base_color_light: %s;" % CREMA),
    ("gnome-shell-sass/_colors.scss",
     "$bg_color: if($variant == 'light', $_base_color_light, #36363a);",
     "$bg_color: if($variant == 'light', $_base_color_light, %s);" % PRUGNA_800),
    ("gnome-shell-sass/_colors.scss",
     "$fg_color: if($variant == 'light', $_base_color_dark, $light_1);",
     "$fg_color: if($variant == 'light', $_base_color_dark, %s);" % CREMA),
    # $osd_fg_color (riquadri a schermo, cattura schermata) resta bianco:
    # GNOME lo scurisce per alcuni stati, e il crema scurito diventa arancione.
    ("gnome-shell-sass/_colors.scss",
     "$panel_bg_color: if($variant == 'light', $_base_color_light, $dark_5);",
     "$panel_bg_color: if($variant == 'light', $_base_color_light, %s);" % PRUGNA_900),
    ("gnome-shell-sass/_colors.scss",
     "$panel_fg_color: if($variant == 'light', $_base_color_dark, $light_1);",
     "$panel_fg_color: if($variant == 'light', $_base_color_dark, %s);" % CREMA),
]

HEADER = """/* RuscaLinux — Adwaita-Prugna, tema di GNOME Shell {version}
 *
 * FILE GENERATO da branding/shell-theme/shell-theme-prugna.py: non
 * modificarlo a mano. E' uno strato di soli colori sopra il foglio di stile
 * di GNOME Shell: contiene le dichiarazioni di colore del tema scuro di
 * GNOME Shell {version}, ricompilate con i colori neutri di RuscaLinux.
 *
 * Opera derivata da GNOME Shell (data/theme/gnome-shell-sass) —
 * Copyright (C) The GNOME Project e i contributori di GNOME Shell.
 * Licenza: GNU General Public License, versione 2 o successiva
 * (GPL-2.0-or-later). Su Debian: /usr/share/common-licenses/GPL-2
 */
"""


def fail(message):
    print("ERRORE:", message)
    sys.exit(1)


def compile_scss(theme_dir):
    result = subprocess.run(
        ["sassc", "-a", os.path.join(theme_dir, "gnome-shell-dark.scss")],
        capture_output=True, text=True)
    if result.returncode != 0:
        fail("sassc non ha compilato il tema:\n" + result.stderr)
    return result.stdout


def split_declarations(body):
    """Divide «a: b; c: d» sui punti e virgola fuori dalle parentesi."""
    parts, depth, current = [], 0, ""
    for char in body:
        if char == "(":
            depth += 1
        elif char == ")":
            depth -= 1
        if char == ";" and depth == 0:
            parts.append(current)
            current = ""
        else:
            current += char
    parts.append(current)
    decls = []
    for part in parts:
        if ":" in part:
            prop, value = part.split(":", 1)
            decls.append((prop.strip(), " ".join(value.split())))
    return decls


def parse_css(css):
    """[(selettore, [(proprieta', valore), …]), …] — il CSS della Shell non
    ha blocchi annidati: lo si controlla."""
    css = re.sub(r"/\*.*?\*/", "", css, flags=re.S)
    rules = []
    for selector, body in re.findall(r"([^{}]+)\{([^{}]*)\}", css):
        selector = " ".join(selector.split())
        if selector.startswith("@"):
            fail("blocco %s non previsto nel CSS della Shell" % selector)
        rules.append((selector, split_declarations(body)))
    if css.count("{") != len(rules):
        fail("il CSS della Shell contiene blocchi annidati: lo script va aggiornato")
    return rules


def soften_darkened_cream(value, stock_colors):
    """Sass scurisce il crema abbassandone solo la luminosita': ne esce un
    arancione. Qui lo si riporta a un crema piu' scuro (tutti i canali in
    proporzione), come GNOME fa con il bianco che diventa grigio."""
    def repl(match):
        text = match.group(0).lower()
        if text in stock_colors:
            return match.group(0)          # arancioni veri di GNOME: restano
        r, g, b = (int(text[i:i + 2], 16) / 255 for i in (1, 3, 5))
        h, l, sat = colorsys.rgb_to_hls(r, g, b)
        if not (15 <= h * 360 <= 40 and sat > 0.8 and l > 0.5) or text == CREMA:
            return match.group(0)
        cream = [int(CREMA[i:i + 2], 16) for i in (1, 3, 5)]
        factor = l / colorsys.rgb_to_hls(*(c / 255 for c in cream))[1]
        return "#%02x%02x%02x" % tuple(round(c * factor) for c in cream)
    return re.sub(r"#[0-9a-fA-F]{6}\b", repl, value)


def family(prop):
    """Le proprieta' abbreviate e le loro parti vanno tenute insieme: il tema
    ha la precedenza su tutto il foglio di GNOME, quindi deve contenere tutte
    le dichiarazioni delle proprieta' che tocca, anche quelle invariate."""
    if prop.startswith("border") and not prop.startswith(("border-radius", "border-image")):
        return "border"
    if prop.startswith("background"):
        return "background"
    return prop


def shell_version(theme_dir):
    meson = os.path.join(theme_dir, "..", "..", "meson.build")
    try:
        with open(meson, encoding="utf-8") as handle:
            match = re.search(r"version\s*:\s*'(\d+)[.\w]*'", handle.read())
        if match:
            return match.group(1)
    except OSError:
        pass
    fail("non trovo la versione di GNOME Shell in " + os.path.normpath(meson))


def main():
    if len(sys.argv) != 2 or not os.path.isfile(
            os.path.join(sys.argv[1], "gnome-shell-dark.scss")):
        print(__doc__)
        return 1
    if not shutil.which("sassc"):
        fail("manca sassc (sudo apt install sassc)")
    source = os.path.abspath(sys.argv[1])
    here = os.path.dirname(os.path.realpath(__file__))
    version = shell_version(source)

    stock = parse_css(compile_scss(source))

    with tempfile.TemporaryDirectory() as tmp:
        work = os.path.join(tmp, "theme")
        shutil.copytree(source, work)
        for name, old, new in PATCHES:
            path = os.path.join(work, name)
            with open(path, encoding="utf-8") as handle:
                text = handle.read()
            if text.count(old) != 1:
                fail("in %s non trovo (una volta sola) la riga:\n    %s\n"
                     "GNOME Shell %s ha cambiato i suoi colori: aggiorna PATCHES."
                     % (name, old, version))
            with open(path, "w", encoding="utf-8") as handle:
                handle.write(text.replace(old, new))
        prugna = parse_css(compile_scss(work))

    stock_colors = {c.lower() for _s, decls in stock for _p, v in decls
                    for c in re.findall(r"#[0-9a-fA-F]{6}\b", v)}
    prugna = [(sel, [(p, soften_darkened_cream(v, stock_colors)) for p, v in decls])
              for sel, decls in prugna]

    if [r[0] for r in stock] != [r[0] for r in prugna]:
        fail("i due CSS compilati non hanno le stesse regole")

    changed = set()
    for (_s, before), (_s2, after) in zip(stock, prugna):
        if [p for p, _v in before] != [p for p, _v in after]:
            fail("i due CSS compilati non hanno le stesse dichiarazioni")
        changed.update(family(p) for (p, v), (_p, w) in zip(before, after) if v != w)

    out, kept = [], 0
    for selector, decls in prugna:
        mine = [(p, v) for p, v in decls if family(p) in changed]
        if mine:
            kept += len(mine)
            out.append("%s {\n%s\n}\n" % (
                selector, "\n".join("  %s: %s;" % d for d in mine)))

    target = os.path.join(here, "Adwaita-Prugna", "gnome-shell")
    os.makedirs(target, exist_ok=True)
    with open(os.path.join(target, "gnome-shell.css"), "w", encoding="utf-8") as handle:
        handle.write(HEADER.format(version=version) + "\n" + "\n".join(out))
    with open(os.path.join(here, "GNOME_SHELL_VERSION"), "w", encoding="utf-8") as handle:
        handle.write(version + "\n")
    print("GNOME Shell %s: %d regole, %d dichiarazioni di colore (%s)"
          % (version, len(out), kept, ", ".join(sorted(changed))))
    return 0


if __name__ == "__main__":
    sys.exit(main())
