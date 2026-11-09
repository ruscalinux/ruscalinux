#!/bin/bash
# ---------------------------------------------------------------------------
# RuscaLinux — costruisce il pacchetto ruscallama (RuscaLLama).
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

VER="1.99.2"
PKG="ruscallama"
NAME="RuscaLLama"
APP_ID="org.ruscalinux.RuscaLLama"
ARCH="all"
MAINT="Nunzio Curcuruto <info@ruscalinux.org>"
HOMEPAGE="https://www.ruscalinux.org/"
# Le lingue sono i file di lang/ (specifiche, sezione 9.1): per aggiungerne
# una basta aggiungere il suo file. en.json e it.json sono obbligatori; l'inglese va per primo (testi
# predefiniti di menu e metainfo).
LANGS="en $(cd lang && ls -1 -- *.json | sed 's/\.json$//' | grep -vx en | sort | tr '\n' ' ')"
SOURCE_DATE_EPOCH="${SOURCE_DATE_EPOCH:-$(date +%s)}"
FILES="ruscallama.py rusca_engine.py rusca_markdown.py"

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
GenericName=AI Chat
Exec=$PKG
Icon=$APP_ID
Terminal=false
Categories=GNOME;GTK;Utility;
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
$PKG \\- chat with local language models
.SH SYNOPSIS
.B $PKG

.SH DESCRIPTION
RuscaLLama is a GNOME chat application for language models in GGUF format that run on this computer through ruscallama-engine (llama.cpp). The engine listens only on 127.0.0.1 with a temporary access key; nothing is sent over the internet. Models are searched in /usr/share/ruscallama/models and ~/.local/share/ruscallama/models.
.SH SEE ALSO
/usr/share/doc/$PKG/MANUAL_en.md.gz
.SH AUTHOR
Nunzio Curcuruto <info@ruscalinux.org>
MANPAGE

cat > "$DOC/copyright" <<'COPYRIGHT'
Format: https://www.debian.org/doc/packaging-manuals/copyright-format/1.0/
Upstream-Name: RuscaLLama
Upstream-Contact: Nunzio Curcuruto <info@ruscalinux.org>
Source: https://www.ruscalinux.org/

Files: *
Copyright: 2026 Nunzio Curcuruto
License: GPL-3+
Comment: Design, specifications and testing by the author; code written
 with the assistance of AI tools. See NOTA-IA.md in the RuscaLinux repository.
 The language model engine is llama.cpp (MIT), packaged separately as
 ruscallama-engine.

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
COPYRIGHT

cat <<CHANGELOG | gzip -9n > "$DOC/changelog.gz"
$PKG ($VER) unstable; urgency=medium

  * Interfaccia riscritta con libadwaita e il tema comune RuscaLinux:
    chat al centro, impostazioni in un pannello laterale richiudibile.
  * Motore avviato al primo messaggio, su una porta libera e con una
    chiave temporanea (rusca_engine.py, comune con RuscaTranslator).
  * Ragionamento attivabile senza riavviare il motore; stili di risposta
    nominati per scopo; istruzioni per il modello modificabili.
  * Interfaccia in 15 lingue; icona e icona simbolica nuove.

 -- $MAINT  $(LC_ALL=C date -Ru -d "@$SOURCE_DATE_EPOCH")
CHANGELOG

cat > "$ROOT/DEBIAN/control" <<CONTROL
Package: $PKG
Version: $VER
Section: utils
Priority: optional
Architecture: $ARCH
Depends: python3 (>= 3.10), python3-gi, gir1.2-gtk-4.0 (>= 4.18), gir1.2-adw-1 (>= 1.7), gir1.2-gtksource-5, python3-markdown-it (>= 3.0), python3-mdit-py-plugins (>= 0.4), python3-linkify-it (>= 2.0), ruscallama-engine (>= $VER)
Maintainer: $MAINT
Homepage: $HOMEPAGE
Installed-Size: $(du -sk "$ROOT/usr" | cut -f1)
Description: chat with local language models
 RuscaLLama is a GNOME application to chat with language models (GGUF)
 that run entirely on this computer through ruscallama-engine (llama.cpp).
 Answers stream as they are generated, with optional reasoning, image
 input for vision models, code blocks with highlighting, and saving to
 Markdown or HTML. Nothing you write leaves the machine.
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
