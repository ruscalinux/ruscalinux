#!/usr/bin/env bash
# make-deb.sh — pacchetto .deb di RuscaMark conforme alle specifiche
# dei RuscaLinux OS Tools (SPECIFICHE-RUSCALINUX-OS-TOOLS.md).
#
# Uso: bash make-deb.sh
#   (dalla cartella con ruscamark.py, lang/, docs/, ruscamark.svg)
#   i18n integrato in ruscamark.py: il vecchio i18n.py non serve più.
#
# Conformità alle specifiche:
#   * script dedicato make-deb.sh;
#   * deb, staging e SHA256SUMS nella sotto-cartella build-deb/,
#     separata dai sorgenti;
#   * nome del pacchetto Debian: ruscamark; il suffisso -ruscalinux
#     compare solo nel nome del file .deb (ruscamark-ruscalinux_*.deb);
#   * versione identica a RuscaLinux (1.99.3);
#   * le lingue dei RuscaLinux OS Tools (file lang/*.json), fallback en.json;
#   * Python >= 3.10, GTK >= 4.18, libadwaita >= 1.7, dipendenze minime;
#   * tema comune RuscaLinux (style.css), icona simbolica, metainfo
#     e voce del menu con testi tradotti presi da lang/;
#   * Recommends: hunspell-en-gb (ortografia en_GB, controllo presente);
#   * GPL-3.0, nota IA nel file copyright (specifiche, sez. 12.2),
#     elaborazione solo locale (no telemetria).
#
# Ortografia  : libspelling (gir1.2-spelling-1) o GSpell 2; il binding
#               python3-enchant NON è usato né raccomandato.
# Traduzione  : ASSENTE per scelta (nessun motore LLM, nessun servizio).
#
# NOTA 1: DEBIAN/control è costruito con righe `echo` (non heredoc) per
#         evitare errori di delimitazione della descrizione.
# NOTA 2: ARCH=all perché il pacchetto contiene solo Python e risorse;
#         gli esempi delle specifiche mostrano amd64, ma Debian Policy
#         impone "all" per i pacchetti indipendenti dall'architettura.
set -euo pipefail

APP="ruscamark"                    # nome applicazione: binario, icone, dati
PKG="ruscamark"                    # nome del pacchetto Debian (apt, dpkg)
SUFFIX="ruscalinux"                # suffisso obbligatorio, solo nel nome del file
VER="1.99.3"                       # identica alla versione di RuscaLinux
ARCH="all"
MAINT="Nunzio Curcuruto <info@ruscalinux.org>"
HOMEPAGE="https://www.ruscalinux.org/"

APP_ID="org.ruscalinux.RuscaMark"   # = APP_ID in ruscamark.py
OLD_APP_ID="org.ruscalinux.ruscamark" # fino alla 1.99.1
DESKTOP_ID="${APP_ID}.desktop"       # GNOME associa la finestra a questo file

OUT="build-deb"
# Struttura di lavoro temporanea dentro build-deb/: viene cancellata alla
# fine (anche in caso di errore), così restano solo il .deb e SHA256SUMS.
STAGE="${OUT}/.staging"
ROOT="${STAGE}/${PKG}_${VER}_${ARCH}"
DEB_NAME="${PKG}-${SUFFIX}_${VER}_${ARCH}.deb"

# ---- controlli preliminari ---------------------------------------------------
[ -f ruscamark.py ]  || { echo "ERRORE: ruscamark.py non trovato."; exit 1; }
[ -f ruscamark.svg ] || { echo "ERRORE: ruscamark.svg non trovato."; exit 1; }
[ -f ruscamark-symbolic.svg ] || { echo "ERRORE: ruscamark-symbolic.svg non trovato."; exit 1; }
[ -f style.css ] || { echo "ERRORE: style.css (tema RuscaLinux) non trovato."; exit 1; }
grep -q "^APP_VERSION = \"${VER}\"" ruscamark.py || { echo "ERRORE: APP_VERSION diversa da ${VER}."; exit 1; }
# Privacy e sicurezza sono documentate nei manuali docs/Manual_{it,en}.md.

# Le lingue sono i file di lang/ (specifiche, sezione 9.1): per aggiungerne
# una basta aggiungere il suo file; devono avere le stesse chiavi di en.json.
# Lo stesso passaggio prepara i testi tradotti per il file .desktop e per la
# metainfo (una sola fonte). en.json e it.json sono obbligatori; l'inglese va per primo (testi
# predefiniti di menu e metainfo).
LANGS="en $(cd lang && ls -1 -- *.json | sed 's/\.json$//' | grep -vx en | sort | tr '\n' ' ')"
for l in en it; do [ -f "lang/$l.json" ] || { echo "ERRORE: manca lang/$l.json"; exit 1; }; done
HAVE_I18N=1
TEXTS="$(mktemp -d)"
python3 - "$TEXTS" $LANGS <<'PYCHECK' || { echo "ERRORE: traduzioni incomplete (vedi sopra)."; exit 1; }
import json, re, sys
from xml.sax.saxutils import escape
out, codes = sys.argv[1], sys.argv[2:]
load = lambda c: json.load(open(f"lang/{c}.json", encoding="utf-8"))
ref, problems = load("en"), []
rows = {"desktop": [], "summary": [], "description": []}
fields = lambda v: sorted(re.findall(r"{(\w+)}", v))
for code in codes:
    try:
        data = load(code)
    except (OSError, ValueError) as err:
        problems.append(f"{code}: {err}")
        continue
    problems += [f"{code}: manca {k}" for k in ref if k not in data]
    problems += [f"{code}: chiave sconosciuta {k}" for k in data if k not in ref]
    problems += [f"{code}: segnaposto diversi in {k}" for k in ref
                 if k in data and not k.startswith("__") and fields(data[k]) != fields(ref[k])]
    text = lambda k: data.get(k, ref[k])
    sfx = "" if code == "en" else f"[{code}]"
    lang = "" if code == "en" else f' xml:lang="{code}"'
    rows["desktop"] += [f"Comment{sfx}={text('app_summary')}",
                        f"Keywords{sfx}={text('desktop_keywords')}"]
    rows["summary"].append(f"  <summary{lang}>{escape(text('app_summary'))}</summary>")
    rows["description"].append(f"    <p{lang}>{escape(text('about_desc'))}</p>")
if problems:
    sys.exit("\n".join(problems))
for name, lines in rows.items():
    open(f"{out}/{name}", "w", encoding="utf-8").write("\n".join(lines) + "\n")
PYCHECK
[ -f docs/Manual_it.md ] && [ -f docs/Manual_en.md ] || \
    echo "AVVISO: docs/Manual_it.md o docs/Manual_en.md mancanti: manuali non inclusi."

# Markdown: motore comune rusca_markdown.py, basato su markdown-it-py
# (CommonMark); python3-markdown non serve.
RECOMMENDS="gir1.2-spelling-1, gir1.2-gtksource-5, hunspell-it, hunspell-en-gb"
SUGGESTS="xdg-utils, hunspell-en-us"

rm -rf "$OUT"
trap 'rm -rf "$STAGE" "$TEXTS"' EXIT
mkdir -p "${ROOT}/DEBIAN" \
    "${ROOT}/usr/bin" \
    "${ROOT}/usr/share/${APP}" \
    "${ROOT}/usr/share/applications" \
    "${ROOT}/usr/share/icons/hicolor/scalable/apps" \
    "${ROOT}/usr/share/icons/hicolor/symbolic/apps" \
    "${ROOT}/usr/share/metainfo" \
    "${ROOT}/usr/share/man/man1" \
    "${ROOT}/usr/share/doc/${PKG}"

# ---- programma + lanciatore --------------------------------------------------
install -m 755 ruscamark.py "${ROOT}/usr/share/${APP}/ruscamark.py"
install -m 644 rusca_markdown.py "${ROOT}/usr/share/${APP}/rusca_markdown.py"
install -m 644 markdown_it_mark.py "${ROOT}/usr/share/${APP}/markdown_it_mark.py"   # componente esterno (MIT)
# Tema comune e icona accanto al programma (li cerca in /usr/share/ruscamark).
install -m 644 style.css "${ROOT}/usr/share/${APP}/style.css"
install -m 644 ruscamark.svg "${ROOT}/usr/share/${APP}/ruscamark.svg"
cat > "${ROOT}/usr/bin/${APP}" <<'LAUNCHER'
#!/bin/sh
exec python3 /usr/share/ruscamark/ruscamark.py "$@"
LAUNCHER
chmod 755 "${ROOT}/usr/bin/${APP}"

# ---- internazionalizzazione --------------------------------------------------
install -d "${ROOT}/usr/share/${APP}/lang"
for f in lang/*.json; do
    [ -e "$f" ] || continue
    install -m 644 "$f" "${ROOT}/usr/share/${APP}/lang/"
done

# ---- icona -------------------------------------------------------------------
install -m 644 ruscamark.svg "${ROOT}/usr/share/icons/hicolor/scalable/apps/${APP_ID}.svg"
install -m 644 ruscamark-symbolic.svg \
        "${ROOT}/usr/share/icons/hicolor/symbolic/apps/${APP_ID}-symbolic.svg"

# ---- voce .desktop -----------------------------------------------------------
# Il nome del file coincide con l'identificativo dell'applicazione: su
# Wayland GTK 4 annuncia l'app_id org.ruscalinux.RuscaMark e GNOME cerca
# org.ruscalinux.RuscaMark.desktop per mostrare l'icona nel pannello.
# Il vecchio org.ruscalinux.ruscamark.desktop sparisce con l'aggiornamento.
{
cat <<DESKTOP
[Desktop Entry]
Type=Application
Name=RuscaMark
GenericName=Markdown Editor
Exec=ruscamark %F
Icon=${APP_ID}
Terminal=false
Categories=GNOME;GTK;Utility;TextEditor;
MimeType=text/markdown;text/x-markdown;
StartupWMClass=${APP_ID}
StartupNotify=true
DESKTOP
cat "${TEXTS}/desktop"
} > "${ROOT}/usr/share/applications/${DESKTOP_ID}"

# ---- metainfo AppStream ------------------------------------------------------
cat > "${ROOT}/usr/share/metainfo/${APP_ID}.metainfo.xml" <<METAINFO
<?xml version="1.0" encoding="UTF-8"?>
<component type="desktop-application">
  <id>${APP_ID}</id>
  <metadata_license>CC0-1.0</metadata_license>
  <project_license>GPL-3.0-or-later</project_license>
  <name>RuscaMark</name>
$(cat "${TEXTS}/summary")
  <developer id="org.ruscalinux">
    <name>Nunzio Curcuruto</name>
  </developer>
  <description>
$(cat "${TEXTS}/description")
  </description>
  <launchable type="desktop-id">${DESKTOP_ID}</launchable>
  <replaces>
    <id>${OLD_APP_ID}</id>
  </replaces>
  <url type="homepage">${HOMEPAGE}</url>
  <url type="bugtracker">https://github.com/ruscalinux/ruscalinux/issues</url>
  <provides>
    <binary>ruscamark</binary>
    <mediatype>text/markdown</mediatype>
  </provides>
  <branding>
    <color type="primary" scheme_preference="light">#f8d7e6</color>
    <color type="primary" scheme_preference="dark">#2d0a1d</color>
  </branding>
  <requires>
    <display_length compare="ge">360</display_length>
  </requires>
  <content_rating type="oars-1.1"/>
  <releases>
    <release version="${VER}" date="$(date -u +%Y-%m-%d)"/>
  </releases>
</component>
METAINFO

# ---- pagina di manuale -------------------------------------------------------
cat <<MANPAGE | gzip -9n > "${ROOT}/usr/share/man/man1/${APP}.1.gz"
.TH RUSCAMARK 1 "$(LC_ALL=C date -u '+%B %Y')" "RuscaMark ${VER}" "RuscaLinux OS Tools"
.SH NAME
ruscamark \\- Markdown editor with live formatting
.SH SYNOPSIS
.B ruscamark
[\\fIFILE\\fR]
.SH DESCRIPTION
RuscaMark is a GNOME Markdown editor. Formatting is applied while you type,
the page stays centred, spelling is checked live with local dictionaries,
and documents can be exported to HTML and PDF. Everything is processed
locally. If FILE is given, it is opened at start.
.SH FILES
.TP
.I ~/.config/ruscamark/config.json
Preferences and window size.
.SH SEE ALSO
/usr/share/doc/ruscamark/Manual_en.md
.SH AUTHOR
Nunzio Curcuruto <info@ruscalinux.org>
MANPAGE

# ---- documentazione ----------------------------------------------------------
# I manuali includono anche le note di privacy e sicurezza (sezione 15).
for doc in docs/Manual_it.md docs/Manual_en.md; do
    if [ -f "$doc" ]; then
        install -m 644 "$doc" "${ROOT}/usr/share/doc/${PKG}/"
    fi
done

cat > "${ROOT}/usr/share/doc/${PKG}/copyright" <<'COPYRIGHT'
Format: https://www.debian.org/doc/packaging-manuals/copyright-format/1.0/
Upstream-Name: RuscaMark
Upstream-Contact: Nunzio Curcuruto <info@ruscalinux.org>
Source: https://www.ruscalinux.org/

Files: *
Copyright: 2026 Nunzio Curcuruto
License: GPL-3+
Comment: Design, specifications and testing by the author; code written
 with the assistance of AI tools. See NOTA-IA.md in the RuscaLinux repository.

Files: markdown_it_mark.py
Copyright: 2014-2015 Vitaly Puzrin, Alex Kocharin (markdown-it-mark)
 2020 ExecutableBookProject (markdown-it-py)
License: Expat
Comment: External component: the ==highlight== rule of the common Markdown
 engine, a Python port of the markdown-it-mark plugin following the
 strikethrough rule of markdown-it-py.

License: GPL-3+
 This program is free software: you can redistribute it and/or modify it
 under the terms of the GNU General Public License as published by the Free
 Software Foundation, either version 3 of the License, or (at your option)
 any later version.
 .
 This program is distributed in the hope that it will be useful, but WITHOUT
 ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or
 FITNESS FOR A PARTICULAR PURPOSE. See the GNU General Public License for
 more details.
 .
 On Debian systems, the complete text of the GNU General Public License
 version 3 can be found in "/usr/share/common-licenses/GPL-3".

License: Expat
 Permission is hereby granted, free of charge, to any person obtaining a copy
 of this software and associated documentation files (the "Software"), to
 deal in the Software without restriction, including without limitation the
 rights to use, copy, modify, merge, publish, distribute, sublicense, and/or
 sell copies of the Software, and to permit persons to whom the Software is
 furnished to do so, subject to the following conditions:
 .
 The above copyright notice and this permission notice shall be included in
 all copies or substantial portions of the Software.
 .
 THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
 IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
 FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
 AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
 LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING
 FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS
 IN THE SOFTWARE.
COPYRIGHT

# ---- changelog (pacchetto nativo: changelog.gz, gzip -9n) --------------------------------------
cat > "${ROOT}/usr/share/doc/${PKG}/changelog" <<CHANGELOG
${PKG} (${VER}) unstable; urgency=medium

  * Interfaccia portata su libadwaita secondo le linee guida GNOME e il
    tema comune RuscaLinux (style.css); colori di editor e anteprima dalla
    palette ufficiale, stile chiaro/scuro che segue il sistema.
  * Barra del titolo semplificata (Nuovo, Apri, anteprima, Salva, menu);
    ortografia e schermo intero nel menu (F7, F11).
  * Preferenze con applicazione immediata; la lingua dell'interfaccia
    segue sempre quella del sistema.
  * Finestra Informazioni e Scorciatoie da tastiera comuni ai
    RuscaLinux OS Tools; notifiche con «Apri» dopo gli export.
  * Identificativo org.ruscalinux.RuscaMark (prima ...ruscamark); icona
    simbolica, metainfo tradotta, pagina di manuale.
  * Export PDF diretto (Ctrl+Maiusc+P): solo il contenuto del documento,
    senza intestazioni, piè di pagina o riferimenti al programma. Anche
    l'export HTML non aggiunge più piè di pagina né meta "generator".
  * Icona corretta nel pannello GNOME: file .desktop rinominato in
    org.ruscalinux.ruscamark.desktop, uguale all'identificativo
    dell'applicazione (app_id su Wayland, WM_CLASS su X11).
  * make-deb.sh non lascia più la cartella di lavoro dentro build-deb/.
  * Il pacchetto si chiama di nuovo "ruscamark"; il suffisso -ruscalinux
    resta solo nel nome del file .deb. Sostituisce il pacchetto
    "ruscamark-ruscalinux" delle build precedenti.
  * Motore Markdown integrato (nessuna dipendenza): tabelle con
    allineamento, immagini mostrate in anteprima, liste di attività, note
    a piè di pagina, link a riferimento, evidenziato, titoli setext.
  * Comandi di scrittura: grassetto (Ctrl+B), corsivo (Ctrl+I), link
    (Ctrl+K), immagine (Ctrl+Maiusc+I), tabella/allinea (Ctrl+Maiusc+T),
    titoli (Ctrl+1…6, Ctrl+0).
  * Export HTML: percorsi immagine corretti, opzione immagini incorporate,
    stile di stampa per PDF dal browser.
  * Pagina centrata anche dopo ridimensionamento e massimizzazione.
  * i18n integrato in ruscamark.py; 15 lingue tradotte; arabo RTL.
  * Versione allineata a RuscaLinux ${VER}: resa live della formattazione,
    pagina centrata, ortografia live (libspelling/GSpell 2) con elisioni
    it/fr, obiettivo parole, Trova/Sostituisci ed export HTML.
  * Corretta la persistenza del controllo ortografico: la scelta
    attivo/disattivo ora viene salvata in config.json e rispettata al
    riavvio.
  * Corretto "Trova e sostituisci": la ricerca usa Gtk.TextIter
    (GTK 4 non espone più forward_search su Gtk.TextBuffer); la
    sostituzione singola ora raggiunge l'occorrenza anche senza
    selezione preventiva.
  * Conformità alle specifiche RuscaLinux OS Tools: script make-deb.sh,
    cartella build-deb/, suffisso -ruscalinux nel nome del file,
    SHA256SUMS, 15 lingue ufficiali (varianti zh_CN e pt_BR), fallback
    inglese, Python >= 3.10,
    Recommends hunspell-en-gb.

 -- ${MAINT}  $(LC_ALL=C date -Ru)
CHANGELOG
gzip -9n "${ROOT}/usr/share/doc/${PKG}/changelog"

# ---- permessi ----------------------------------------------------------------
find "${ROOT}/usr" -type d -exec chmod 755 {} +
find "${ROOT}/usr" -type f -exec chmod 644 {} +
chmod 755 "${ROOT}/usr/bin/${APP}" "${ROOT}/usr/share/${APP}/ruscamark.py"

# ---- dimensione installata ---------------------------------------------------
SIZE_KB=$(du -sk "${ROOT}/usr" | cut -f1)

# ---- DEBIAN/control (costruito a righe, non heredoc) -------------------------
{
    echo "Package: ${PKG}"
    echo "Version: ${VER}"
    echo "Architecture: ${ARCH}"
    echo "Maintainer: ${MAINT}"
    echo "Depends: python3 (>= 3.10), python3-gi, python3-gi-cairo, gir1.2-gtk-4.0 (>= 4.18), gir1.2-adw-1 (>= 1.7), librsvg2-common, fonts-dejavu-core, python3-markdown-it (>= 3.0), python3-mdit-py-plugins (>= 0.4), python3-linkify-it (>= 2.0)"
    echo "Recommends: ${RECOMMENDS}"
    echo "Suggests: ${SUGGESTS}"
    # Le build precedenti si chiamavano "ruscamark-ruscalinux" e installavano
    # gli stessi file: Replaces+Conflicts rende pulito l'aggiornamento.
    # (Un pacchetto non può dichiarare conflitto con il proprio nome.)
    echo "Replaces: ${PKG}-${SUFFIX}"
    echo "Conflicts: ${PKG}-${SUFFIX}"
    echo "Section: editors"
    echo "Priority: optional"
    echo "Homepage: ${HOMEPAGE}"
    echo "Installed-Size: ${SIZE_KB}"
    echo "Description: Editor Markdown con resa live per la scrittura"
    echo " RuscaMark applica la formattazione Markdown durante la digitazione e"
    echo " centra la pagina come un foglio di scrittura. Tabelle, immagini, liste"
    echo " di attività e note a piè di pagina. Interfaccia GNOME nei colori di"
    echo " RuscaLinux, controllo ortografico live con suggerimenti nel menu"
    echo " contestuale (libspelling / GSpell 2), interfaccia in $(echo $LANGS | wc -w) lingue"
    echo " ufficiali di RuscaLinux, obiettivo parole, Trova/Sostituisci, export"
    echo " HTML e PDF. Tutta l'elaborazione avviene in locale."
} > "${ROOT}/DEBIAN/control"

# ---- validazioni opzionali (non bloccanti) -----------------------------------
command -v desktop-file-validate >/dev/null 2>&1 && \
    desktop-file-validate "${ROOT}/usr/share/applications/${DESKTOP_ID}" || true
command -v appstreamcli >/dev/null 2>&1 && \
    appstreamcli validate --no-net "${ROOT}/usr/share/metainfo/${APP_ID}.metainfo.xml" || true

# ---- costruzione e impronta --------------------------------------------------
dpkg-deb --build --root-owner-group -Zxz -z9 "${ROOT}" "${OUT}/${DEB_NAME}"
( cd "${OUT}" && sha256sum *.deb > SHA256SUMS )
rm -rf "$STAGE"

# ---- riepilogo ---------------------------------------------------------------
echo
echo "Pacchetto creato : ${OUT}/${DEB_NAME}"
echo "Dimensione       : $(du -h "${OUT}/${DEB_NAME}" | cut -f1)"
echo "i18n             : $([ "$HAVE_I18N" -eq 1 ] && echo "$(echo $LANGS | wc -w) lingue (fallback en)" || echo 'lingue parziali (fallback en/it incorporati)')"
echo "Traduzione       : assente (scelta progettuale)"
echo
cat "${OUT}/SHA256SUMS"
echo
echo "Installa :  sudo apt install ./${OUT}/${DEB_NAME}"
echo "Verifica :  sha256sum -c ${OUT}/SHA256SUMS"
echo "Audit    :  lintian ${OUT}/${DEB_NAME}   (se installato)"
echo "Rimuovi  :  sudo apt remove ${PKG}"