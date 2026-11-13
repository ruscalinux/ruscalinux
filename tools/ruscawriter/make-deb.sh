#!/bin/bash
# ---------------------------------------------------------------------------
# RuscaLinux — costruisce il pacchetto ruscawriter (RuscaWriter).
#
#   ./make-deb.sh
#
# Regole delle specifiche dei RuscaLinux OS Tools: un solo .deb in
# build-deb/ con suffisso -ruscalinux e SHA256SUMS accanto; Python puro,
# quindi Architecture: all; versione = VERSION di release.conf, uguale a
# APP_VERSION_SHORT in src/ruscawriter/model.py.
# ---------------------------------------------------------------------------
set -euo pipefail
cd "$(dirname "$0")"

VER="1.99.3"
PKG="ruscawriter"
NAME="RuscaWriter"
APP_ID="org.ruscalinux.RuscaWriter"
OLD_PKG="ruscawriter-ruscalinux"     # nome del pacchetto fino alla 1.99.1
ARCH="all"
MAINT="Nunzio Curcuruto <info@ruscalinux.org>"
HOMEPAGE="https://www.ruscalinux.org/"
# Le lingue sono i file di lang/ (specifiche, sezione 9.1): per aggiungerne
# una basta aggiungere il suo file. en.json e it.json sono obbligatori; l'inglese va per primo (testi
# predefiniti di menu e metainfo).
LANGS="en $(cd lang && ls -1 -- *.json | sed 's/\.json$//' | grep -vx en | sort | tr '\n' ' ')"
SOURCE_DATE_EPOCH="${SOURCE_DATE_EPOCH:-$(date +%s)}"

die() { echo "ERRORE: $*" >&2; exit 1; }
for l in en it; do [ -f "lang/$l.json" ] || die "manca lang/$l.json"; done
for f in ruscawriter.py src/ruscawriter assets/style.css assets/ruscawriter.svg \
         assets/ruscawriter-symbolic.svg docs/Manual_it.md docs/Manual_en.md CHANGELOG.md; do
    [ -e "$f" ] || die "manca $f"
done
grep -q "^APP_VERSION_SHORT = \"$VER\"" src/ruscawriter/model.py \
    || die "APP_VERSION_SHORT in src/ruscawriter/model.py diversa da $VER"
command -v dpkg-deb >/dev/null || die "serve dpkg-deb (pacchetto dpkg)"
python3 -m py_compile ruscawriter.py src/ruscawriter/*.py || die "errore di sintassi Python"

OUT="build-deb"
rm -rf "$OUT"
mkdir -p "$OUT"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"; find . -name __pycache__ -type d -prune -exec rm -rf {} +' EXIT
ROOT="$TMP/root"
SHARE="$ROOT/usr/share/$PKG"
DOC="$ROOT/usr/share/doc/$PKG"

# ── Traduzioni: stesse chiavi e segnaposto di en.json; testi del lanciatore
#    e della metainfo presi da lang/ (una sola fonte) ─────────────────────────
python3 - "$TMP" $LANGS <<'PYCHECK' || die "traduzioni incomplete (vedi sopra)"
import json, re, sys
from xml.sax.saxutils import escape
out, codes = sys.argv[1], sys.argv[2:]
load = lambda c: json.load(open(f"lang/{c}.json", encoding="utf-8"))
ref, problems = load("en"), []
rows = {"desktop": [], "summary": [], "description": []}
fields = lambda v: sorted(re.findall(r"{(\w+)}", v)) if isinstance(v, str) else []
for code in codes:
    try:
        data = load(code)
    except (OSError, ValueError) as err:
        problems.append(f"{code}: {err}")
        continue
    problems += [f"{code}: manca {k}" for k in ref if k not in data and not k.startswith("__")]
    problems += [f"{code}: segnaposto diversi in {k}" for k in ref
                 if k in data and not k.startswith("__") and fields(data[k]) != fields(ref[k])]
    # Una copia dell'inglese non e' una traduzione: stesso criterio di
    # is_complete() in src/ruscawriter/i18n.py (chiavi-sonda).
    probe = ("btn_save", "btn_open", "menu_file", "menu_help", "mi_about", "cancel")
    if code != "en" and sum(data.get(k) != ref.get(k) for k in probe) * 2 <= len(probe):
        problems.append(f"{code}: sembra una copia dell'inglese, non una traduzione")
    t = lambda k: data.get(k, ref[k])
    sfx = "" if code == "en" else f"[{code}]"
    lang = "" if code == "en" else f' xml:lang="{code}"'
    rows["desktop"] += [f"Comment{sfx}={t('app_summary')}", f"Keywords{sfx}={t('desktop_keywords')}"]
    rows["summary"].append(f"  <summary{lang}>{escape(t('app_summary'))}</summary>")
    rows["description"].append(f"    <p{lang}>{escape(t('app_description'))}</p>")
if problems:
    sys.exit("\n".join(problems))
for name, lines in rows.items():
    open(f"{out}/{name}", "w", encoding="utf-8").write("\n".join(lines) + "\n")
PYCHECK

# ── File ─────────────────────────────────────────────────────────────────────
mkdir -p "$ROOT/DEBIAN" "$ROOT/usr/bin" "$SHARE" "$DOC" \
         "$ROOT/usr/share/applications" "$ROOT/usr/share/metainfo" \
         "$ROOT/usr/share/mime/packages" "$ROOT/usr/share/man/man1" \
         "$ROOT/usr/share/icons/hicolor/scalable/apps" \
         "$ROOT/usr/share/icons/hicolor/symbolic/apps"
cp -a ruscawriter.py src lang assets "$SHARE/"
find "$SHARE" -name __pycache__ -type d -prune -exec rm -rf {} +
find "$SHARE" -type d -exec chmod 755 {} +
find "$SHARE" -type f -exec chmod 644 {} +
chmod 755 "$SHARE/ruscawriter.py"
# Il comando e' un collegamento: ruscawriter.py trova src/, lang/ e assets/
# accanto a se' con os.path.realpath(__file__).
ln -s "../share/$PKG/ruscawriter.py" "$ROOT/usr/bin/$PKG"
install -m 644 assets/ruscawriter.svg "$ROOT/usr/share/icons/hicolor/scalable/apps/$APP_ID.svg"
install -m 644 assets/ruscawriter-symbolic.svg \
        "$ROOT/usr/share/icons/hicolor/symbolic/apps/$APP_ID-symbolic.svg"
for f in docs/Manual_it.md docs/Manual_en.md CHANGELOG.md; do
    gzip -9n -c "$f" > "$DOC/$(basename "$f").gz"
done

# Tipo di file dei progetti (.rwr, archivio tar.gz): doppio clic -> RuscaWriter
cat > "$ROOT/usr/share/mime/packages/$APP_ID.xml" <<'MIME'
<?xml version="1.0" encoding="UTF-8"?>
<mime-info xmlns="http://www.freedesktop.org/standards/shared-mime-info">
  <mime-type type="application/x-ruscawriter">
    <comment>RuscaWriter project</comment>
    <comment xml:lang="it">Progetto di RuscaWriter</comment>
    <sub-class-of type="application/gzip"/>
    <glob pattern="*.rwr"/>
  </mime-type>
</mime-info>
MIME

{
cat <<DESKTOP
[Desktop Entry]
Type=Application
Name=$NAME
GenericName=Writing and Typesetting
GenericName[it]=Scrittura e impaginazione
Exec=$PKG %f
Icon=$APP_ID
Terminal=false
Categories=GNOME;GTK;Office;WordProcessor;
MimeType=application/x-ruscawriter;
StartupNotify=true
StartupWMClass=$APP_ID
DESKTOP
cat "$TMP/desktop"
} > "$ROOT/usr/share/applications/$APP_ID.desktop"

cat > "$ROOT/usr/share/metainfo/$APP_ID.metainfo.xml" <<METAINFO
<?xml version="1.0" encoding="UTF-8"?>
<component type="desktop-application">
  <id>$APP_ID</id>
  <metadata_license>CC0-1.0</metadata_license>
  <project_license>GPL-3.0-or-later</project_license>
  <name>$NAME</name>
$(cat "$TMP/summary")
  <developer id="org.ruscalinux">
    <name>Nunzio Curcuruto</name>
  </developer>
  <description>
$(cat "$TMP/description")
  </description>
  <launchable type="desktop-id">$APP_ID.desktop</launchable>
  <url type="homepage">$HOMEPAGE</url>
  <url type="bugtracker">https://github.com/ruscalinux/ruscalinux/issues</url>
  <provides>
    <binary>$PKG</binary>
    <mediatype>application/x-ruscawriter</mediatype>
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
    <release version="$VER" date="$(date -u -d "@$SOURCE_DATE_EPOCH" +%Y-%m-%d)"/>
  </releases>
</component>
METAINFO

cat <<MANPAGE | gzip -9n > "$ROOT/usr/share/man/man1/$PKG.1.gz"
.TH RUSCAWRITER 1 "$(LC_ALL=C date -u -d "@$SOURCE_DATE_EPOCH" '+%B %Y')" "$NAME $VER" "RuscaLinux OS Tools"
.SH NAME
ruscawriter \\- write a book and typeset it, in one program
.SH SYNOPSIS
.B ruscawriter
[\\fIPROJECT.rwr\\fR]
.SH DESCRIPTION
RuscaWriter is a GNOME writing environment for books: chapter list, text and
per-chapter notes side by side. You write in Markdown; the same program
typesets the book and exports it to PDF, EPUB, AZW3, ODT, DOCX, HTML, Markdown
or text. A project is a .rwr file, a tar.gz archive of Markdown files.
If PROJECT.rwr is given, it is opened at start. RuscaWriter never connects
to the network.
.SH FILES
.TP
.I ~/.config/ruscawriter/settings.json
Preferences.
.TP
.I ~/.local/share/ruscawriter/dictionaries/
MDict dictionaries added by the user.
.SH SEE ALSO
/usr/share/doc/ruscawriter/Manual_en.md.gz
.SH AUTHOR
Nunzio Curcuruto <info@ruscalinux.org>
MANPAGE

cat > "$DOC/copyright" <<'COPYRIGHT'
Format: https://www.debian.org/doc/packaging-manuals/copyright-format/1.0/
Upstream-Name: RuscaWriter
Upstream-Contact: Nunzio Curcuruto <info@ruscalinux.org>
Source: https://github.com/ruscalinux/ruscalinux

Files: *
Copyright: 2026 Nunzio Curcuruto
License: GPL-3+
Comment: Design, specifications and testing by the author; code written
 with the assistance of AI tools. See NOTA-IA.md in the RuscaLinux repository.

Files: assets/EBGaramond-*.ttf
Copyright: 2017 The EB Garamond Project Authors
 2025 Deborah Khodanovich (RCS citation glyphs)
License: OFL-1.1
Comment: External component. Full license text in
 /usr/share/ruscawriter/assets/EBGaramond-OFL.txt

Files: assets/CourierPrime-*.ttf
Copyright: 2015 The Courier Prime Project Authors
License: OFL-1.1
Comment: External component. Full license text in
 /usr/share/ruscawriter/assets/CourierPrime-OFL.txt

Files: src/ruscawriter/markdown_it_mark.py
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

License: OFL-1.1
 SIL Open Font License, Version 1.1. The complete text is installed next to
 each font, in /usr/share/ruscawriter/assets/.

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

cat <<CHANGELOG | gzip -9n > "$DOC/changelog.gz"
$PKG ($VER) unstable; urgency=medium

  * RuscaWriter entra nei RuscaLinux OS Tools: interfaccia libadwaita con
    il tema comune, menu principale al posto della barra dei menu, dialoghi
    GNOME, finestra Informazioni comune con i componenti esterni.
  * Temi Ametista (palette ufficiale), Classico e Semplice limitati alla
    pagina di scrittura, con contrasti verificati.
  * Lingua dell'interfaccia dal sistema; versione senza data.
  * Sito, sorgenti e segnalazioni di RuscaLinux; tolti i file del progetto
    separato. Pacchetto ruscawriter (Architecture: all), sostituisce
    ruscawriter-ruscalinux.
  * Icona nuova con versione simbolica; tipo di file per i progetti .rwr.
  * Elenco completo delle modifiche: CHANGELOG.md.gz.

 -- $MAINT  $(LC_ALL=C date -Ru -d "@$SOURCE_DATE_EPOCH")
CHANGELOG

cat > "$ROOT/DEBIAN/control" <<CONTROL
Package: $PKG
Version: $VER
Section: editors
Priority: optional
Architecture: $ARCH
Depends: python3 (>= 3.10), python3-gi, gir1.2-gtk-4.0 (>= 4.18), gir1.2-adw-1 (>= 1.7), librsvg2-common, python3-markdown-it (>= 3.0), python3-mdit-py-plugins (>= 0.4), python3-linkify-it (>= 2.0)
Recommends: gir1.2-gtksource-5, gir1.2-spelling-1, python3-pyphen, hunspell-en-gb, hyphen-en-gb, python3-pil
Suggests: calibre, hyphen-it, hyphen-en-us, hunspell-it, hunspell-en-us
Replaces: $OLD_PKG
Breaks: $OLD_PKG
Maintainer: $MAINT
Homepage: $HOMEPAGE
Installed-Size: $(du -sk "$ROOT/usr" | cut -f1)
Description: write a book and typeset it, in one program
 RuscaWriter is a GNOME writing environment for books: chapter list, text
 and per-chapter notes side by side. You write in Markdown, then the same
 program typesets the result (book page sizes, binding margins, justified
 text, hyphenation, embedded fonts, cover, frontispiece and colophon) and
 exports to PDF, EPUB, AZW3, ODT, DOCX, HTML, Markdown or text.
 .
 A project file is a tar.gz of Markdown files, so the text can be
 recovered with ordinary tools. RuscaWriter never connects to the network.
CONTROL
find "$ROOT" -type d -exec chmod 755 {} +

DEB="${PKG}-ruscalinux_${VER}_${ARCH}.deb"
dpkg-deb --root-owner-group --build "$ROOT" "$OUT/$DEB" >/dev/null
( cd "$OUT" && sha256sum "$DEB" > SHA256SUMS )
echo "Pronto: $OUT/$DEB"
if command -v desktop-file-validate >/dev/null 2>&1; then
    desktop-file-validate "$ROOT/usr/share/applications/$APP_ID.desktop" || true
fi
if command -v appstreamcli >/dev/null 2>&1; then
    appstreamcli validate --no-net "$ROOT/usr/share/metainfo/$APP_ID.metainfo.xml" >/dev/null \
        || appstreamcli validate --no-net "$ROOT/usr/share/metainfo/$APP_ID.metainfo.xml" || true
fi
