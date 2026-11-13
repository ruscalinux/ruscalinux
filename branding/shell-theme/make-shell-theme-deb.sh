#!/bin/bash

# Script per creare il pacchetto .deb del tema di GNOME Shell di RuscaLinux
# Uso: ./make-shell-theme-deb.sh [versione]
#
# Come gli altri script di branding/, scrive il .deb nella cartella corrente.
#
# Il tema e' uno strato di soli colori sopra il foglio di stile di GNOME
# Shell, caricato dall'estensione ufficiale User Themes: barra in alto, menu,
# notifiche e Attivita' in prugna, testo crema. Non sostituisce nessun file
# di GNOME Shell e non tocca la schermata di accesso (GDM).
#
# E' generato per UNA versione maggiore di GNOME Shell (file
# GNOME_SHELL_VERSION): il pacchetto dipende da quella versione, cosi' un
# passaggio a una nuova Debian lo rimuove invece di lasciare un tema vecchio
# su una Shell nuova. Per la nuova versione: shell-theme-prugna.py.

set -e

# ── Identità RuscaLinux ───────────────────────────────────────────────────────
RL_VENDOR="RuscaLinux"
RL_MAINTAINER="RuscaLinux Project <packager@ruscalinux.org>"
RL_HOMEPAGE="https://www.ruscalinux.org"
RL_VERSION_SUFFIX="~ruscalinux1"
# ─────────────────────────────────────────────────────────────────────────────

PACKAGE_NAME="ruscalinux-shell-theme"
VERSION="${1:-1.0}${RL_VERSION_SUFFIX}"
ARCH="all"

SRC="$(cd "$(dirname "$0")" && pwd)"
ORIGINAL_DIR="$(pwd)"
CSS="$SRC/Adwaita-Prugna/gnome-shell/gnome-shell.css"

for f in "$CSS" "$SRC/GNOME_SHELL_VERSION" "$SRC/91_ruscalinux-shell-theme.gschema.override"; do
    if [ ! -f "$f" ]; then
        echo "Errore: manca $f"
        echo "Il tema si genera con shell-theme-prugna.py (vedi README.md)."
        exit 1
    fi
done

SHELL_VER=$(tr -d '[:space:]' < "$SRC/GNOME_SHELL_VERSION")
case "$SHELL_VER" in
    ''|*[!0-9]*) echo "Errore: GNOME_SHELL_VERSION non e' un numero: '$SHELL_VER'"; exit 1 ;;
esac
SHELL_NEXT=$((SHELL_VER + 1))

# Controlli minimi sul CSS generato: e' per la versione dichiarata e le
# parentesi graffe sono bilanciate.
if ! grep -q "tema di GNOME Shell $SHELL_VER\$" "$CSS"; then
    echo "Errore: gnome-shell.css non e' generato per GNOME Shell $SHELL_VER"
    exit 1
fi
if [ "$(tr -cd '{' < "$CSS" | wc -c)" -ne "$(tr -cd '}' < "$CSS" | wc -c)" ]; then
    echo "Errore: gnome-shell.css ha parentesi graffe non bilanciate"
    exit 1
fi

echo "==> Vendor: $RL_VENDOR"
echo "==> Pacchetto: $PACKAGE_NAME"
echo "==> Versione: $VERSION (per GNOME Shell $SHELL_VER)"

TEMP_DIR=$(mktemp -d)
trap 'rm -rf "$TEMP_DIR"' EXIT
BUILD_DIR="$TEMP_DIR/${PACKAGE_NAME}_${VERSION}_${ARCH}"

echo "==> Creazione struttura pacchetto..."
mkdir -p "$BUILD_DIR/DEBIAN" \
         "$BUILD_DIR/usr/share/themes/Adwaita-Prugna/gnome-shell" \
         "$BUILD_DIR/usr/share/glib-2.0/schemas" \
         "$BUILD_DIR/usr/share/doc/$PACKAGE_NAME"

cp "$CSS" "$BUILD_DIR/usr/share/themes/Adwaita-Prugna/gnome-shell/"
cp "$SRC/91_ruscalinux-shell-theme.gschema.override" "$BUILD_DIR/usr/share/glib-2.0/schemas/"

cat > "$BUILD_DIR/usr/share/doc/$PACKAGE_NAME/copyright" << EOF
Format: https://www.debian.org/doc/packaging-manuals/copyright-format/1.0/
Upstream-Name: $PACKAGE_NAME
Upstream-Contact: RuscaLinux <info@ruscalinux.org>
Source: https://github.com/ruscalinux/ruscalinux
Comment: Design, specifications and testing by the author; code written with
 the assistance of AI tools. See NOTA-IA.md in the RuscaLinux repository.

Files: *
Copyright: 2026 Nunzio Curcuruto
License: GPL-3

Files: usr/share/themes/Adwaita-Prugna/gnome-shell/gnome-shell.css
Copyright: The GNOME Project and the GNOME Shell contributors
           2026 Nunzio Curcuruto (colours)
License: GPL-2+
Comment: Colour declarations of the GNOME Shell $SHELL_VER dark theme
 (data/theme/gnome-shell-sass), recompiled with the RuscaLinux neutral
 colours by shell-theme-prugna.py.

License: GPL-3
 This package is free software: you can redistribute it and/or modify it
 under the terms of the GNU General Public License, version 3, as published
 by the Free Software Foundation.
 .
 On Debian systems, the complete text of the GNU General Public License
 version 3 can be found in /usr/share/common-licenses/GPL-3.

License: GPL-2+
 This program is free software; you can redistribute it and/or modify it
 under the terms of the GNU General Public License as published by the Free
 Software Foundation; either version 2 of the License, or (at your option)
 any later version.
 .
 On Debian systems, the complete text of the GNU General Public License
 version 2 can be found in /usr/share/common-licenses/GPL-2.
EOF

echo "==> Creazione file control..."
cat > "$BUILD_DIR/DEBIAN/control" << EOF
Package: $PACKAGE_NAME
Version: $VERSION
Section: gnome
Priority: optional
Architecture: $ARCH
Vendor: $RL_VENDOR
Depends: gnome-shell (>= $SHELL_VER~), gnome-shell (<< $SHELL_NEXT~), gnome-shell-extension-user-theme, ruscalinux-theme
Maintainer: $RL_MAINTAINER
Homepage: $RL_HOMEPAGE
Description: GNOME Shell theme for $RL_VENDOR (plum)
 Gives the top bar, the menus, the notifications and the overview of
 GNOME Shell the $RL_VENDOR plum colours, with cream text.
 .
 The theme is a colour-only layer on top of the stylesheet of GNOME Shell
 $SHELL_VER, loaded by the official User Themes extension: it replaces no file
 of GNOME Shell and leaves the login screen alone. The accent colour and
 the error, warning and success colours stay those of GNOME. With high
 contrast on, the theme steps aside (ruscalinux-theme).
 .
 It is a default: it can be turned off in Extensions or Tweaks.
 .
 Built for $RL_VENDOR — $RL_HOMEPAGE
EOF

cat > "$BUILD_DIR/DEBIAN/postinst" << 'EOF'
#!/bin/sh
set -e
if [ "$1" = "configure" ] && command -v glib-compile-schemas > /dev/null 2>&1; then
    glib-compile-schemas /usr/share/glib-2.0/schemas 2> /dev/null || true
fi
exit 0
EOF
cat > "$BUILD_DIR/DEBIAN/postrm" << 'EOF'
#!/bin/sh
set -e
if [ "$1" = "remove" ] || [ "$1" = "purge" ]; then
    if command -v glib-compile-schemas > /dev/null 2>&1; then
        glib-compile-schemas /usr/share/glib-2.0/schemas 2> /dev/null || true
    fi
fi
exit 0
EOF
chmod 755 "$BUILD_DIR/DEBIAN/postinst" "$BUILD_DIR/DEBIAN/postrm"

echo "==> Correzione permessi..."
find "$BUILD_DIR/usr" -type d -exec chmod 755 {} \;
find "$BUILD_DIR/usr" -type f -exec chmod 644 {} \;

INSTALLED_SIZE=$(du -sk "$BUILD_DIR/usr" | cut -f1)
echo "Installed-Size: $INSTALLED_SIZE" >> "$BUILD_DIR/DEBIAN/control"

echo "==> Costruzione pacchetto .deb..."
DEB_FILE="${PACKAGE_NAME}_${VERSION}_${ARCH}.deb"
dpkg-deb --build --root-owner-group "$BUILD_DIR" "$ORIGINAL_DIR/$DEB_FILE" > /dev/null

echo ""
echo "✅ Pacchetto creato con successo: $DEB_FILE"
echo ""
echo "Per installare (serve anche ruscalinux-theme):"
echo "  sudo apt install ./$DEB_FILE"
echo "Poi uscire e rientrare nella sessione."
echo ""
echo "Per spegnere il tema senza disinstallare:"
echo "  gsettings set org.gnome.shell.extensions.user-theme name \"''\""
