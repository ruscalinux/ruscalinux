#!/bin/bash
# ---------------------------------------------------------------------------
# RuscaLinux — costruisce il pacchetto ruscatranslator (RuscaTranslator).
#
#   ./make-deb.sh
#
# Regole delle specifiche dei RuscaLinux OS Tools: un solo .deb in
# build-deb/ con suffisso -ruscalinux e SHA256SUMS accanto; Python puro,
# quindi Architecture: all; versione = VERSION di release.conf.
# Il programma usa ruscallama-engine (llama.cpp, componente esterno MIT).
# ---------------------------------------------------------------------------
set -euo pipefail
cd "$(dirname "$0")"

VER="1.99.3"
PKG="ruscatranslator"
NAME="RuscaTranslator"
APP_ID="org.ruscalinux.RuscaTranslator"
ARCH="all"
MAINT="Nunzio Curcuruto <info@ruscalinux.org>"
HOMEPAGE="https://www.ruscalinux.org/"
# Le lingue sono i file di lang/ (specifiche, sezione 9.1): per aggiungerne
# una basta aggiungere il suo file. en.json e it.json sono obbligatori; l'inglese va per primo (testi
# predefiniti di menu e metainfo).
LANGS="en $(cd lang && ls -1 -- *.json | sed 's/\.json$//' | grep -vx en | sort | tr '\n' ' ')"
SOURCE_DATE_EPOCH="${SOURCE_DATE_EPOCH:-$(date +%s)}"
FILES="ruscatranslator.py rusca_engine.py rusca_markdown.py markdown_it_mark.py raglin.py rag"

die() { echo "ERRORE: $*" >&2; exit 1; }
for l in en it; do [ -f "lang/$l.json" ] || die "manca lang/$l.json"; done
for f in $FILES style.css "$PKG.svg" "$PKG-symbolic.svg" docs/MANUAL_it.md docs/MANUAL_en.md; do
    [ -e "$f" ] || die "manca $f"
done
grep -q "^APP_VERSION = \"$VER\"" "$PKG.py" || die "APP_VERSION in $PKG.py diversa da $VER"
command -v dpkg-deb >/dev/null || die "serve dpkg-deb (pacchetto dpkg)"
python3 -m py_compile $(for f in $FILES; do case $f in *.py) echo "$f";; esac; done) \
    || die "errore di sintassi Python"

OUT="build-deb"
rm -rf "$OUT"
mkdir -p "$OUT"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"; find . -name __pycache__ -type d -prune -exec rm -rf {} +' EXIT
ROOT="$TMP/root"
SHARE="$ROOT/usr/share/$PKG"
DOC="$ROOT/usr/share/doc/$PKG"

# ── Traduzioni: stesse chiavi e segnaposto di en.json; testi per .desktop
#    e metainfo presi da lang/ (una sola fonte) ──────────────────────────────
python3 - "$TMP" $LANGS <<'PYCHECK' || die "traduzioni incomplete (vedi sopra)"
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
                 if k in data and fields(data[k]) != fields(ref[k])]
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
mkdir -p "$ROOT/DEBIAN" "$ROOT/usr/bin" "$SHARE/lang" "$DOC" \
         "$ROOT/usr/share/applications" "$ROOT/usr/share/metainfo" \
         "$ROOT/usr/share/man/man1" \
         "$ROOT/usr/share/icons/hicolor/scalable/apps" \
         "$ROOT/usr/share/icons/hicolor/symbolic/apps"
for f in $FILES; do
    if [ -d "$f" ]; then
        mkdir -p "$SHARE/$f"
        install -m 644 "$f"/*.json "$SHARE/$f/"
    else
        install -m 644 "$f" "$SHARE/$f"
    fi
done
chmod 755 "$SHARE/$PKG.py"
install -m 644 style.css "$PKG.svg" "$SHARE/"
for c in $LANGS; do install -m 644 "lang/$c.json" "$SHARE/lang/"; done
# Il comando e' un collegamento: il programma trova lang/, style.css e i
# moduli accanto a se' con os.path.realpath(__file__).
ln -s "../share/$PKG/$PKG.py" "$ROOT/usr/bin/$PKG"
install -m 644 "$PKG.svg" "$ROOT/usr/share/icons/hicolor/scalable/apps/$APP_ID.svg"
install -m 644 "$PKG-symbolic.svg" "$ROOT/usr/share/icons/hicolor/symbolic/apps/$APP_ID-symbolic.svg"
for f in docs/*.md; do gzip -9n -c "$f" > "$DOC/$(basename "$f").gz"; done

{
cat <<DESKTOP
[Desktop Entry]
Type=Application
Name=$NAME
GenericName=Translator
Exec=$PKG %F
Icon=$APP_ID
Terminal=false
Categories=GNOME;GTK;Office;
MimeType=text/markdown;
StartupNotify=true
StartupWMClass=$APP_ID
DESKTOP
cat "$TMP/desktop"
} > "$ROOT/usr/share/applications/$APP_ID.desktop"
sed -i '/^$/d' "$ROOT/usr/share/applications/$APP_ID.desktop"

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
.TH $(echo "$PKG" | tr a-z A-Z) 1 "$(LC_ALL=C date -u -d "@$SOURCE_DATE_EPOCH" '+%B %Y')" "$NAME $VER" "RuscaLinux OS Tools"
.SH NAME
$PKG \\- translate Markdown documents with a local language model
.SH SYNOPSIS
.B $PKG
[\\fIFILE\\fR]
.SH DESCRIPTION
RuscaTranslator translates Markdown documents between twenty-six languages with a language model that runs on this computer through ruscallama-engine (llama.cpp). For Italian and English it adds a linguistic knowledge base, a document glossary, a translation memory and final corrections. If FILE is given, it is opened at start. Nothing is sent over the internet.
.SH SEE ALSO
/usr/share/doc/$PKG/MANUAL_en.md.gz
.SH AUTHOR
Nunzio Curcuruto <info@ruscalinux.org>
MANPAGE

cat > "$DOC/copyright" <<'COPYRIGHT'
Format: https://www.debian.org/doc/packaging-manuals/copyright-format/1.0/
Upstream-Name: RuscaTranslator
Upstream-Contact: Nunzio Curcuruto <info@ruscalinux.org>
Source: https://www.ruscalinux.org/

Files: *
Copyright: 2026 Nunzio Curcuruto
License: GPL-3+
Comment: Design, specifications and testing by the author; code written
 with the assistance of AI tools. See NOTA-IA.md in the RuscaLinux repository.
 The language model engine is llama.cpp (MIT), packaged separately as
 ruscallama-engine.

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

cat <<CHANGELOG | gzip -9n > "$DOC/changelog.gz"
$PKG ($VER) unstable; urgency=medium

  * Interfaccia riscritta con libadwaita e il tema comune RuscaLinux.
  * Motore su porta libera con chiave temporanea (rusca_engine.py).
  * RAG ripulito dalle regole costruite sui testi di prova; correzioni
    per dominio, mai dentro codice, link o HTML.
  * Memoria di traduzione e glossari in ~/.local/share/ruscatranslator.
  * raglin.py in /usr/share/ruscatranslator (prima in /usr/bin).
  * Interfaccia in 15 lingue; icona e icona simbolica nuove.
  * Traduzione tra tutte le 26 lingue dei RuscaLinux OS Tools (prima 15):
    aggiunti cinese tradizionale, portoghese europeo, olandese, ucraino,
    ceco, vietnamita, svedese, rumeno, ungherese, greco e finlandese, con
    rilevamento automatico anche delle varianti.

 -- $MAINT  $(LC_ALL=C date -Ru -d "@$SOURCE_DATE_EPOCH")
CHANGELOG

cat > "$ROOT/DEBIAN/control" <<CONTROL
Package: $PKG
Version: $VER
Section: text
Priority: optional
Architecture: $ARCH
Depends: python3 (>= 3.10), python3-gi, gir1.2-gtk-4.0 (>= 4.18), gir1.2-adw-1 (>= 1.7), gir1.2-gtksource-5, python3-markdown-it (>= 3.0), python3-mdit-py-plugins (>= 0.4), python3-linkify-it (>= 2.0), ruscallama-engine (>= $VER)
Maintainer: $MAINT
Homepage: $HOMEPAGE
Installed-Size: $(du -sk "$ROOT/usr" | cut -f1)
Description: translate Markdown documents with a local language model
 RuscaTranslator translates Markdown documents between twenty-six
 languages with a language model that runs on this computer through
 ruscallama-engine (llama.cpp), keeping headings, lists, tables, code and
 links intact. Between Italian and English it adds a linguistic knowledge
 base, a document glossary, a translation memory and final corrections.
 Nothing leaves the machine.
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
