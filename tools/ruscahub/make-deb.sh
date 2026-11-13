#!/usr/bin/env bash
# make-deb.sh — Crea il pacchetto .deb di RuscaHub con SHA256SUMS
# Uso: ./make-deb.sh          (dalla radice del progetto)
# Output: build-deb/ruscahub-ruscalinux_<VER>_all.deb + build-deb/SHA256SUMS
set -euo pipefail

PKG="ruscahub"
VER="1.99.3"
ARCH="all"                     # solo Python: indipendente dall'architettura
SUFFIX="ruscalinux"            # suffisso obbligatorio (specifiche RuscaLinux)
MAINT="Nunzio Curcuruto <info@ruscalinux.org>"
HOMEPAGE="https://www.ruscalinux.org/"

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
OUT="$ROOT_DIR/build-deb"
STAGE="$OUT/.staging/${PKG}_${VER}_${ARCH}"

echo "== RuscaHub $VER — creazione pacchetto .deb =="

# ------------------------------------------------------------------ sorgenti
find_file() { local c; for c in "$@"; do [ -f "$ROOT_DIR/$c" ] && { echo "$ROOT_DIR/$c"; return 0; }; done; return 1; }
find_dir()  { local c; for c in "$@"; do [ -d "$ROOT_DIR/$c" ] && { echo "$ROOT_DIR/$c"; return 0; }; done; return 1; }

PY="$(find_file ruscahub/ruscahub.py ruscahub.py)"                || { echo "ERRORE: ruscahub.py non trovato"; exit 1; }
SVG="$(find_file ruscahub.svg data/ruscahub.svg ruscahub/ruscahub.svg org.ruscalinux.RuscaHub.svg)" || { echo "ERRORE: icona SVG non trovata"; exit 1; }
SYM="$(find_file ruscahub-symbolic.svg)"                           || { echo "ERRORE: icona simbolica non trovata"; exit 1; }
CSS="$(find_file style.css)"                                       || { echo "ERRORE: style.css (tema RuscaLinux) non trovato"; exit 1; }
LANG_DIR="$(find_dir lang ruscahub/lang)"                         || { echo "ERRORE: cartella lang/ non trovata"; exit 1; }
[ -f "$LANG_DIR/en.json" ] || { echo "ERRORE: lang/en.json (fallback) mancante"; exit 1; }
[ -f "$LANG_DIR/it.json" ] || { echo "ERRORE: lang/it.json mancante"; exit 1; }
MAN_IT="$(find_file docs/MANUAL_it.md MANUAL_it.md)"             || MAN_IT=""
MAN_EN="$(find_file docs/MANUAL_en.md MANUAL_en.md)"             || MAN_EN=""

grep -qx "APP_VERSION = \"$VER\"" "$PY" || { echo "ERRORE: APP_VERSION in ruscahub.py diversa da $VER"; exit 1; }

# Traduzioni: JSON valido, stesse chiavi e stessi segnaposto di en.json.
# Lo stesso passaggio prepara i testi tradotti per .desktop e metainfo.
TEXTS_DIR="$(mktemp -d)"
trap 'rm -rf "$OUT/.staging" "$TEXTS_DIR"' EXIT
python3 - "$LANG_DIR" "$TEXTS_DIR" <<'PYCHECK' || { echo "ERRORE: traduzioni incomplete (vedi sopra)"; exit 1; }
import json, sys
from xml.sax.saxutils import escape
folder, out = sys.argv[1], sys.argv[2]
# Le lingue sono i file di lang/ (specifiche, sezione 9.1): per aggiungerne
# una basta aggiungere il suo file. en.json e it.json sono obbligatori; l'inglese va per primo (testi
# predefiniti di menu e metainfo).
import os
codes = ["en"] + sorted(f[:-5] for f in os.listdir(folder) if f.endswith(".json") and f != "en.json")
load = lambda c: json.load(open(f"{folder}/{c}.json", encoding="utf-8"))
ref, problems, keywords, summaries, descriptions, names = load("en"), [], [], [], [], []
for code in codes:
    try:
        data = load(code)
    except (OSError, ValueError) as err:
        problems.append(f"{code}: {err}")
        continue
    problems += [f"{code}: manca {k}" for k in ref if k not in data]
    problems += [f"{code}: chiave sconosciuta {k}" for k in data if k not in ref]
    problems += [f"{code}: segnaposto diversi in {k}" for k in ref
                 if k in data and data[k].count("%s") != ref[k].count("%s")]
    text = lambda k: data.get(k, ref[k])
    sfx = "" if code == "en" else f"[{code}]"
    lang = "" if code == "en" else f' xml:lang="{code}"'
    names.append(f"GenericName{sfx}={text('desktop_generic_name')}")
    names.append(f"Comment{sfx}={text('desktop_comment')}")
    keywords.append(f"Keywords{sfx}={text('desktop_keywords')}")
    summaries.append(f"  <summary{lang}>{escape(text('app_summary'))}</summary>")
    descriptions.append(f"    <p{lang}>{escape(text('app_description'))}</p>")
if problems:
    sys.exit("\n".join(problems))
for name, rows in (("names", names), ("keywords", keywords), ("summary", summaries), ("description", descriptions)):
    open(f"{out}/{name}", "w", encoding="utf-8").write("\n".join(rows) + "\n")
PYCHECK

# ------------------------------------------------------------------ struttura
rm -rf "$OUT/.staging"
mkdir -p "$STAGE/DEBIAN" \
         "$STAGE/usr/bin" \
         "$STAGE/usr/share/ruscahub/lang" \
         "$STAGE/usr/share/applications" \
         "$STAGE/usr/share/icons/hicolor/scalable/apps" \
         "$STAGE/usr/share/icons/hicolor/symbolic/apps" \
         "$STAGE/usr/share/metainfo" \
         "$STAGE/usr/share/man/man1" \
         "$STAGE/usr/share/doc/ruscahub"

cp "$PY"  "$STAGE/usr/share/ruscahub/ruscahub.py"
cp "$LANG_DIR"/*.json "$STAGE/usr/share/ruscahub/lang/"
cp "$CSS" "$STAGE/usr/share/ruscahub/style.css"
cp "$SVG" "$STAGE/usr/share/ruscahub/ruscahub.svg"
cp "$SVG" "$STAGE/usr/share/icons/hicolor/scalable/apps/org.ruscalinux.RuscaHub.svg"
cp "$SYM" "$STAGE/usr/share/icons/hicolor/symbolic/apps/org.ruscalinux.RuscaHub-symbolic.svg"
[ -n "$MAN_IT" ] && cp "$MAN_IT" "$STAGE/usr/share/doc/ruscahub/MANUAL_it.md"
[ -n "$MAN_EN" ] && cp "$MAN_EN" "$STAGE/usr/share/doc/ruscahub/MANUAL_en.md"

# ------------------------------------------------------------------ launcher
cat > "$STAGE/usr/bin/ruscahub" <<'EOF'
#!/bin/sh
exec python3 /usr/share/ruscahub/ruscahub.py "$@"
EOF
chmod 755 "$STAGE/usr/bin/ruscahub"

# ------------------------------------------------------------------ desktop
# Nome generico, descrizione e parole chiave tradotti vengono da lang/.
{
cat <<'EOF'
[Desktop Entry]
Type=Application
Name=RuscaHub
Exec=ruscahub
Icon=org.ruscalinux.RuscaHub
Terminal=false
Categories=GTK;GNOME;Utility;
StartupNotify=true
StartupWMClass=org.ruscalinux.RuscaHub
EOF
cat "$TEXTS_DIR/names"
cat "$TEXTS_DIR/keywords"
} > "$STAGE/usr/share/applications/org.ruscalinux.RuscaHub.desktop"

# ------------------------------------------------------------------ metainfo AppStream
cat > "$STAGE/usr/share/metainfo/org.ruscalinux.RuscaHub.metainfo.xml" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<component type="desktop-application">
  <id>org.ruscalinux.RuscaHub</id>
  <name>RuscaHub</name>
$(cat "$TEXTS_DIR/summary")
  <metadata_license>CC0-1.0</metadata_license>
  <project_license>GPL-3.0-or-later</project_license>
  <developer id="org.ruscalinux">
    <name>Nunzio Curcuruto</name>
  </developer>
  <description>
$(cat "$TEXTS_DIR/description")
  </description>
  <launchable type="desktop-id">org.ruscalinux.RuscaHub.desktop</launchable>
  <provides>
    <binary>ruscahub</binary>
  </provides>
  <url type="homepage">$HOMEPAGE</url>
  <url type="bugtracker">https://github.com/ruscalinux/ruscalinux/issues</url>
  <branding>
    <color type="primary" scheme_preference="light">#f8d7e6</color>
    <color type="primary" scheme_preference="dark">#2d0a1d</color>
  </branding>
  <requires>
    <display_length compare="ge">360</display_length>
  </requires>
  <content_rating type="oars-1.1"/>
  <releases>
    <release version="$VER" date="$(date -u +%Y-%m-%d)"/>
  </releases>
</component>
EOF

# ------------------------------------------------------------------ pagina di manuale
cat <<EOF | gzip -9n > "$STAGE/usr/share/man/man1/ruscahub.1.gz"
.TH RUSCAHUB 1 "$(LC_ALL=C date -u '+%B %Y')" "RuscaHub $VER" "RuscaLinux OS Tools"
.SH NAME
ruscahub \\- manage AppImage applications
.SH SYNOPSIS
.B ruscahub
.SH DESCRIPTION
RuscaHub imports AppImage files into ~/.ruscahub/apps, reads their name and
icon without running them when squashfs-tools is installed, adds or removes
their entry in the GNOME applications menu, runs them and moves them to the
trash when deleted. It opens a GNOME window and takes no options.
.SH FILES
.TP
.I ~/.ruscahub/
Archived AppImages, extracted icons and the list of entries.
.TP
.I ~/.local/share/applications/ruscahub-*.desktop
Menu entries created by RuscaHub.
.SH SEE ALSO
/usr/share/doc/ruscahub/MANUAL_en.md
.SH AUTHOR
Nunzio Curcuruto <info@ruscalinux.org>
EOF

# ------------------------------------------------------------------ copyright e changelog
cat > "$STAGE/usr/share/doc/ruscahub/copyright" <<'EOF'
Format: https://www.debian.org/doc/packaging-manuals/copyright-format/1.0/
Upstream-Name: RuscaHub
Upstream-Contact: Nunzio Curcuruto <info@ruscalinux.org>
Source: https://www.ruscalinux.org/

Files: *
Copyright: 2026 Nunzio Curcuruto
License: GPL-3+
Comment: Design, specifications and testing by the author; code written
 with the assistance of AI tools. See NOTA-IA.md in the RuscaLinux repository.

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
EOF

cat <<EOF | gzip -9n > "$STAGE/usr/share/doc/ruscahub/changelog.gz"
ruscahub ($VER) unstable; urgency=medium

  * Interfaccia riscritta con libadwaita secondo le linee guida GNOME e il
    tema comune RuscaLinux (style.css), con modalità chiara/scura automatica.
  * Menu principale con Scorciatoie da tastiera e Informazioni;
    Ctrl+O aggiunge, Ctrl+W chiude, Ctrl+Q esce.
  * Elenco con interruttore per il menu delle applicazioni; notifiche per
    importazione, installazione ed eliminazione.
  * Eliminazione con conferma: il file AppImage viene spostato nel cestino.
  * Una sola finestra; la finestra ricorda la sua dimensione.
  * Icona simbolica, metainfo AppStream, pagina di manuale.
  * Rimossa la dipendenza da python3-cairo; richiede libadwaita 1.7.

 -- $MAINT  $(LC_ALL=C date -Ru)
EOF

# Cache delle icone e database dei lanciatori si aggiornano con i trigger di
# dpkg dichiarati da hicolor-icon-theme e desktop-file-utils: niente postinst.

# ------------------------------------------------------------------ permessi
find "$STAGE" -type d -exec chmod 755 {} +
find "$STAGE/usr/share" -type f -exec chmod 644 {} +

# ------------------------------------------------------------------ control + md5sums
INSTALLED_SIZE="$(du -sk --exclude=DEBIAN "$STAGE" | cut -f1)"
cat > "$STAGE/DEBIAN/control" <<EOF
Package: $PKG
Version: $VER
Section: utils
Priority: optional
Architecture: $ARCH
Installed-Size: $INSTALLED_SIZE
Depends: python3 (>= 3.10), python3-gi, gir1.2-gtk-4.0 (>= 4.18), gir1.2-adw-1 (>= 1.7), librsvg2-common
Recommends: squashfs-tools, libfuse2t64 | libfuse2
Suggests: fonts-noto-core, fonts-noto-cjk
Maintainer: $MAINT
Homepage: $HOMEPAGE
Description: AppImage manager for RuscaLinux (RuscaTools suite)
 RuscaHub imports AppImage files by drag and drop or file chooser, stores
 them in a hidden folder of the user home and integrates them into the
 GNOME menu through .desktop entries, with the original application icon.
 Install, uninstall, run and delete AppImages from a single GNOME
 (libadwaita) interface in the RuscaLinux colours, available in many languages.
 Deleted AppImages are moved to the trash.
EOF
chmod 644 "$STAGE/DEBIAN/control"
( cd "$STAGE" && find usr -type f -print0 | sort -z | xargs -0 md5sum ) > "$STAGE/DEBIAN/md5sums"
chmod 644 "$STAGE/DEBIAN/md5sums"

# ------------------------------------------------------------------ build
mkdir -p "$OUT"
DEB_NAME="${PKG}-${SUFFIX}_${VER}_${ARCH}.deb"
rm -f "$OUT/$DEB_NAME" "$OUT/SHA256SUMS"
dpkg-deb --build --root-owner-group "$STAGE" "$OUT/$DEB_NAME"

# ------------------------------------------------------------------ SHA256SUMS
( cd "$OUT" && sha256sum *.deb > SHA256SUMS )

echo
echo "== Completato =="
echo "Pacchetto : $OUT/$DEB_NAME"
echo "Checksum  : $OUT/SHA256SUMS"
cat "$OUT/SHA256SUMS"
echo
echo "Verifica  : cd build-deb && sha256sum -c SHA256SUMS"
if command -v desktop-file-validate >/dev/null 2>&1; then
    desktop-file-validate "$STAGE/usr/share/applications/org.ruscalinux.RuscaHub.desktop" 2>/dev/null || true
fi
echo "Install   : sudo apt install ./build-deb/$DEB_NAME"
