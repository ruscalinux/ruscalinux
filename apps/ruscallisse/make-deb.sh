#!/bin/bash
# ---------------------------------------------------------------------------
# RuscaLinux — costruisce il pacchetto ruscallisse (RuscaLLisse).
#
#   ./prova/prepara-motori.sh     # una volta: i motori precompilati di prova
#   ./make-deb.sh
#
# VERSIONE DI PROVA. Le regole delle specifiche valgono tutte (un solo .deb
# in build-deb/ con suffisso -ruscalinux e SHA256SUMS accanto, versione =
# VERSION di release.conf), con una differenza dichiarata: invece di
# dipendere da ruscavosk-engine e ruscapiper-engine, il pacchetto porta i
# motori precompilati di prova/motori/ in /usr/lib/ruscallisse/prova/.
# Per questo l'architettura è amd64 e la versione ha il suffisso ~prova.
# ---------------------------------------------------------------------------
set -euo pipefail
cd "$(dirname "$0")"

VER="1.99.3"
PROVA="10"
PKG="ruscallisse"
NAME="RuscaLLisse"
APP_ID="org.ruscalinux.RuscaLLisse"
ARCH="amd64"
DEBVER="${VER}~prova${PROVA}"
MAINT="Nunzio Curcuruto <info@ruscalinux.org>"
HOMEPAGE="https://www.ruscalinux.org/"
LANGS="en $(cd lang && ls -1 -- *.json | sed 's/\.json$//' | grep -vx en | sort | tr '\n' ' ')"
FILES="ruscallisse.py conversation.py entity.py face.py speech_text.py rusca_vosk.py rusca_piper.py rusca_engine.py rusca_markdown.py markdown_it_mark.py"
MOTORI="prova/motori"

die() { echo "ERRORE: $*" >&2; exit 1; }
for l in en it; do [ -f "lang/$l.json" ] || die "manca lang/$l.json"; done
for f in $FILES style.css "$PKG.svg" "$PKG-symbolic.svg" pronunce.tsv entities/ellittica.md \
         docs/MANUAL_it.md docs/MANUAL_en.md; do
    [ -e "$f" ] || die "manca $f"
done
[ -f "$MOTORI/libvosk.so" ] && [ -d "$MOTORI/python/piper" ] \
    || die "mancano i motori di prova: lancia prima ./prova/prepara-motori.sh"
grep -q "^APP_VERSION = \"$VER\"" "$PKG.py" || die "APP_VERSION in $PKG.py diversa da $VER"
if [ -f ../../release.conf ]; then
    grep -q "^VERSION=\"\?$VER\"\?" ../../release.conf || die "VER diversa da VERSION di release.conf"
fi
for f in rusca_engine.py rusca_markdown.py markdown_it_mark.py style.css; do
    cmp -s "$f" "../ruscallama/$f" || die "$f non è identico a quello di RuscaLLama"
done
command -v dpkg-deb >/dev/null || die "serve dpkg-deb (pacchetto dpkg)"
python3 -m py_compile $FILES || die "errore di sintassi Python"

OUT="build-deb"
rm -rf "$OUT"
mkdir -p "$OUT"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"; find . -name __pycache__ -type d -prune -exec rm -rf {} +' EXIT
ROOT="$TMP/root"
SHARE="$ROOT/usr/share/$PKG"
LIBD="$ROOT/usr/lib/$PKG/prova"
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
    data = load(code)
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
mkdir -p "$ROOT/DEBIAN" "$ROOT/usr/bin" "$SHARE/lang" "$SHARE/entities" "$DOC" "$LIBD" \
         "$ROOT/usr/share/applications" "$ROOT/usr/share/metainfo" \
         "$ROOT/usr/share/icons/hicolor/scalable/apps" \
         "$ROOT/usr/share/icons/hicolor/symbolic/apps"
for f in $FILES; do install -m 644 "$f" "$SHARE/$f"; done
chmod 755 "$SHARE/$PKG.py"
install -m 644 style.css "$PKG.svg" pronunce.tsv "$SHARE/"
install -m 644 entities/*.md "$SHARE/entities/"
for c in $LANGS; do install -m 644 "lang/$c.json" "$SHARE/lang/"; done
ln -s "../share/$PKG/$PKG.py" "$ROOT/usr/bin/$PKG"
install -m 644 "$PKG.svg" "$ROOT/usr/share/icons/hicolor/scalable/apps/$APP_ID.svg"
install -m 644 "$PKG-symbolic.svg" "$ROOT/usr/share/icons/hicolor/symbolic/apps/$APP_ID-symbolic.svg"
for f in docs/*.md; do gzip -9n -c "$f" > "$DOC/$(basename "$f").gz"; done
# Motori di prova
install -m 644 "$MOTORI/libvosk.so" "$LIBD/libvosk.so"
cp -r "$MOTORI/python" "$LIBD/python"
cp -r "$MOTORI/licenze" "$DOC/licenze-motori"
install -m 644 "$MOTORI/VERSIONI" "$DOC/VERSIONI-motori"
find "$LIBD" -type d -exec chmod 755 {} +
find "$LIBD" -type f -exec chmod 644 {} +
find "$LIBD" -name "*.so*" -exec chmod 755 {} +

cat > "$ROOT/usr/share/applications/$APP_ID.desktop" <<DESKTOP
[Desktop Entry]
Type=Application
Name=$NAME
GenericName=Voice Conversation
Exec=$PKG
Icon=$APP_ID
Terminal=false
Categories=GNOME;GTK;Utility;X-RuscaLinux-Apps;
StartupNotify=true
StartupWMClass=$APP_ID
$(cat "$TMP/desktop")
DESKTOP

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
  <content_rating type="oars-1.1"/>
  <releases>
    <release version="$DEBVER" date="$(date +%Y-%m-%d)"/>
  </releases>
</component>
METAINFO

cat > "$DOC/copyright" <<COPYRIGHT
Format: https://www.debian.org/doc/packaging-manuals/copyright-format/1.0/
Upstream-Name: RuscaLLisse
Source: https://github.com/ruscalinux/ruscalinux
Comment: Design, specifications and testing by the author; code written with
 the assistance of AI tools. See NOTA-IA.md in the RuscaLinux repository.
 .
 TEST VERSION: the speech engines in /usr/lib/ruscallisse/prova/ are the
 prebuilt binaries of the official packages (see VERSIONI-motori); their
 licence texts are in licenze-motori/.

Files: *
Copyright: 2026 Nunzio Curcuruto <info@ruscalinux.org>
License: GPL-3.0-or-later
 On Debian systems the full text is in /usr/share/common-licenses/GPL-3.

Files: usr/share/ruscallisse/markdown_it_mark.py
Copyright: 2014-2015 Vitaly Puzrin, Alex Kocharin; ExecutableBookProject
License: Expat

Files: usr/lib/ruscallisse/prova/libvosk.so
Copyright: Alpha Cephei Inc.; Kaldi authors
License: Apache-2.0
 On Debian systems the full text is in /usr/share/common-licenses/Apache-2.0.

Files: usr/lib/ruscallisse/prova/python/piper/*
Copyright: Michael Hansen and the Piper authors; espeak-ng authors
License: GPL-3.0-or-later

Files: usr/lib/ruscallisse/prova/python/onnxruntime/*
Copyright: Microsoft Corporation
License: Expat
 Third-party notices in licenze-motori/onnxruntime/ThirdPartyNotices.txt.

Files: usr/lib/ruscallisse/prova/python/numpy*
Copyright: NumPy Developers
License: BSD-3-Clause
 See licenze-motori/numpy/ (bundled OpenBLAS and runtime libraries included).
COPYRIGHT

SIZE=$(du -sk "$ROOT" | cut -f1)
cat > "$ROOT/DEBIAN/control" <<CONTROL
Package: $PKG
Version: $DEBVER
Section: sound
Priority: optional
Architecture: $ARCH
Installed-Size: $SIZE
Depends: python3 (>= 3.13), python3 (<< 3.14), python3-gi, python3-gi-cairo, gir1.2-gtk-4.0 (>= 4.18), gir1.2-adw-1 (>= 1.7), python3-markdown-it (>= 3.0), python3-mdit-py-plugins (>= 0.4), python3-linkify-it (>= 2.0), pipewire-bin, ruscallama-engine, libstdc++6, libgcc-s1
Maintainer: $MAINT
Homepage: $HOMEPAGE
Description: Voice conversation with a digital entity (test version)
 Talk aloud with Ellittica, an intellectual, gentle and sensitive digital
 woman who explains things simply. Only her face is on screen: nothing is
 written and the conversation is not saved. Listens with Vosk, thinks with
 ruscallama-engine on 127.0.0.1, speaks with Piper. Everything stays on the
 computer.
 .
 TEST VERSION with the prebuilt engines of the official packages.
CONTROL

dpkg-deb --root-owner-group -Zxz --build "$ROOT" "$OUT/${PKG}-ruscalinux_${DEBVER}_${ARCH}.deb" >/dev/null
( cd "$OUT" && sha256sum -- *.deb > SHA256SUMS )
ls -la "$OUT"
