#!/bin/bash
# ---------------------------------------------------------------------------
# RuscaLinux — costruisce il pacchetto ruscapallas (RuscaPallas).
#
#   ./make-deb.sh
#
# Regole delle specifiche: un solo .deb in build-deb/ con suffisso
# -ruscalinux e SHA256SUMS accanto, versione = VERSION di release.conf,
# Architecture: all.
#
# Il pacchetto ha tre parti:
#   * l'estensione di GNOME Shell ruscapallas@ruscalinux.org (Pallasio sul
#     desktop: disegno, movimenti, fumetto);
#   * il servizio di dialogo org.ruscalinux.RuscaPallas, avviato da D-Bus
#     al primo clic: è il ciclo di conversazione di RuscaLLisse, con i suoi
#     moduli copiati identici (qui si controlla);
#   * il comando ruscapallas, che richiama Pallasio dalla griglia delle
#     applicazioni.
# I motori sono i pacchetti ruscavosk-engine, ruscallama-engine e
# ruscapiper-engine, compilati dal sorgente.
# ---------------------------------------------------------------------------
set -euo pipefail
cd "$(dirname "$0")"

VER="1.99.3"
PKG="ruscapallas"
NAME="RuscaPallas"
APP_ID="org.ruscalinux.RuscaPallas"
UUID="ruscapallas@ruscalinux.org"
ARCH="all"
DEBVER="${VER}"
MAINT="Nunzio Curcuruto <info@ruscalinux.org>"
HOMEPAGE="https://www.ruscalinux.org/"
LANGS="en $(cd lang && ls -1 -- *.json | sed 's/\.json$//' | grep -vx en | sort | tr '\n' ' ')"
SHARED="conversation.py entity.py speech_text.py rusca_vosk.py rusca_piper.py rusca_engine.py rusca_markdown.py markdown_it_mark.py"
FILES="ruscapallas.py ruscapallas-service.py $SHARED"
EXT_FILES="metadata.json extension.js pallasio.js figure.js motion.js world.js"

die() { echo "ERRORE: $*" >&2; exit 1; }
for l in en it; do [ -f "lang/$l.json" ] || die "manca lang/$l.json"; done
for f in $FILES pronunce.tsv "$PKG.svg" "$PKG-symbolic.svg" entities/pallasio.md \
         docs/MANUAL_it.md docs/MANUAL_en.md; do
    [ -e "$f" ] || die "manca $f"
done
for f in $EXT_FILES; do [ -e "extension/$f" ] || die "manca extension/$f"; done
for f in ruscapallas.py ruscapallas-service.py; do
    grep -q "^APP_VERSION = \"$VER\"" "$f" || die "APP_VERSION in $f diversa da $VER"
done
grep -q "\"version-name\": \"$VER\"" extension/metadata.json || die "version-name in metadata.json diversa da $VER"
grep -q "\"uuid\": \"$UUID\"" extension/metadata.json || die "uuid in metadata.json diverso da $UUID"
if [ -f ../../release.conf ]; then
    grep -q "^VERSION=\"\?$VER\"\?" ../../release.conf || die "VER diversa da VERSION di release.conf"
fi
# Il cervello di Pallasio è quello di Ellittica: una correzione fatta in
# RuscaLLisse non deve restare indietro qui.
for f in $SHARED pronunce.tsv; do
    cmp -s "$f" "../ruscallisse/$f" || die "$f non è identico a quello di RuscaLLisse (copialo da ../ruscallisse/)"
done
command -v dpkg-deb >/dev/null || die "serve dpkg-deb (pacchetto dpkg)"
python3 -m py_compile $FILES || die "errore di sintassi Python"
python3 -m json.tool extension/metadata.json >/dev/null || die "metadata.json non è JSON valido"
if command -v gjs >/dev/null; then       # controllo di sintassi dei moduli dell'estensione
    for f in figure.js motion.js world.js; do
        gjs -m "extension/$f" >/dev/null 2>&1 || die "errore in extension/$f (prova: gjs -m extension/$f)"
    done
fi

OUT="build-deb"
rm -rf "$OUT"
mkdir -p "$OUT"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"; find . -name __pycache__ -type d -prune -exec rm -rf {} +' EXIT
ROOT="$TMP/root"
SHARE="$ROOT/usr/share/$PKG"
EXT="$ROOT/usr/share/gnome-shell/extensions/$UUID"
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
mkdir -p "$ROOT/DEBIAN" "$ROOT/usr/bin" "$SHARE/lang" "$SHARE/entities" "$EXT/lang" "$DOC" \
         "$ROOT/usr/share/applications" "$ROOT/usr/share/metainfo" \
         "$ROOT/usr/share/dbus-1/services" \
         "$ROOT/usr/share/icons/hicolor/scalable/apps" \
         "$ROOT/usr/share/icons/hicolor/symbolic/apps"
for f in $FILES; do install -m 644 "$f" "$SHARE/$f"; done
chmod 755 "$SHARE/ruscapallas.py" "$SHARE/ruscapallas-service.py"
install -m 644 pronunce.tsv "$PKG.svg" "$SHARE/"
install -m 644 entities/*.md "$SHARE/entities/"
for c in $LANGS; do
    install -m 644 "lang/$c.json" "$SHARE/lang/"
    install -m 644 "lang/$c.json" "$EXT/lang/"      # l'estensione non legge fuori dalla sua cartella
done
for f in $EXT_FILES; do install -m 644 "extension/$f" "$EXT/$f"; done
ln -s "../share/$PKG/ruscapallas.py" "$ROOT/usr/bin/$PKG"
install -m 644 "$PKG.svg" "$ROOT/usr/share/icons/hicolor/scalable/apps/$APP_ID.svg"
install -m 644 "$PKG-symbolic.svg" "$ROOT/usr/share/icons/hicolor/symbolic/apps/$APP_ID-symbolic.svg"
for f in docs/*.md; do gzip -9n -c "$f" > "$DOC/$(basename "$f").gz"; done

# il servizio di dialogo parte da solo al primo clic su Pallasio
cat > "$ROOT/usr/share/dbus-1/services/$APP_ID.service" <<SERVICE
[D-BUS Service]
Name=$APP_ID
Exec=/usr/share/$PKG/ruscapallas-service.py
SERVICE

# Nessuna finestra: il comando richiama Pallasio e avvisa con una notifica.
cat > "$ROOT/usr/share/applications/$APP_ID.desktop" <<DESKTOP
[Desktop Entry]
Type=Application
Name=$NAME
GenericName=Desktop Companion
Exec=$PKG
Icon=$APP_ID
Terminal=false
Categories=GNOME;Utility;X-RuscaLinux-Apps;
StartupNotify=false
StartupWMClass=$APP_ID
$(cat "$TMP/desktop")
DESKTOP
if command -v desktop-file-validate >/dev/null; then
    desktop-file-validate "$ROOT/usr/share/applications/$APP_ID.desktop" || die "file .desktop non valido"
fi

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
    <dbus type="user">$APP_ID</dbus>
  </provides>
  <requires>
    <id>org.gnome.Shell</id>
  </requires>
  <content_rating type="oars-1.1"/>
  <releases>
    <release version="$DEBVER" date="$(date +%Y-%m-%d)"/>
  </releases>
</component>
METAINFO

cat > "$DOC/copyright" <<COPYRIGHT
Format: https://www.debian.org/doc/packaging-manuals/copyright-format/1.0/
Upstream-Name: RuscaPallas
Source: https://github.com/ruscalinux/ruscalinux
Comment: Design, specifications and testing by the author; code written with
 the assistance of AI tools. See NOTA-IA.md in the RuscaLinux repository.
 The speech engines are separate packages (ruscavosk-engine,
 ruscapiper-engine, ruscallama-engine), with their own copyright files.
 Pallasio, his drawing and his personality are original works of the
 RuscaLinux project.

Files: *
Copyright: 2026 Nunzio Curcuruto <info@ruscalinux.org>
License: GPL-3.0-or-later
 On Debian systems the full text is in /usr/share/common-licenses/GPL-3.

Files: usr/share/ruscapallas/markdown_it_mark.py
Copyright: 2014-2015 Vitaly Puzrin, Alex Kocharin; ExecutableBookProject
License: Expat
COPYRIGHT

SIZE=$(du -sk "$ROOT" | cut -f1)
cat > "$ROOT/DEBIAN/control" <<CONTROL
Package: $PKG
Version: $DEBVER
Section: gnome
Priority: optional
Architecture: $ARCH
Installed-Size: $SIZE
Depends: gnome-shell (>= 48), python3 (>= 3.10), python3-gi, gir1.2-glib-2.0, python3-markdown-it (>= 3.0), python3-mdit-py-plugins (>= 0.4), python3-linkify-it (>= 2.0), pipewire-bin, ruscallama-engine, ruscavosk-engine, ruscapiper-engine
Recommends: ruscallisse
Maintainer: $MAINT
Homepage: $HOMEPAGE
Description: Pallasio, a cynical Pallas's cat who walks on the desktop and talks
 Pallasio is an old, learned and embittered Pallas's cat in a cream jacket,
 red tie and small round glasses, with a tome always in hand. A GNOME Shell
 extension lets him walk on the desktop and jump on windows; click him and he
 listens and answers aloud. Listens with Vosk, thinks with ruscallama-engine
 on 127.0.0.1, speaks with Piper: everything stays on the computer and the
 conversation is not saved.
CONTROL

dpkg-deb --root-owner-group -Zxz --build "$ROOT" "$OUT/${PKG}-ruscalinux_${DEBVER}_${ARCH}.deb" >/dev/null
( cd "$OUT" && sha256sum -- *.deb > SHA256SUMS )
ls -la "$OUT"
