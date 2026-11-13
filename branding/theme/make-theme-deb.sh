#!/bin/bash

# Script per creare il pacchetto .deb del tema del desktop di RuscaLinux
# Uso: ./make-theme-deb.sh [versione]
#
# Come gli script di icone e sfondi, scrive il .deb nella cartella corrente.
# I sorgenti stanno accanto a questo script: nessun archivio da passare.
#
# Contenuto del pacchetto (tutto con meccanismi ufficiali di GNOME/GTK):
#   - tema GTK 3 Adwaita-Prugna (chiaro e scuro) in /usr/share/themes/
#   - valori predefiniti: accento di sistema, tema GTK 3, icone
#   - piccolo aiuto di sessione: GTK 3 segue lo stile chiaro/scuro, e il tema
#     della Shell (pacchetto ruscalinux-shell-theme) cede al contrasto elevato
# Qui GNOME Shell, GDM e le applicazioni libadwaita NON vengono modificati:
# prendono il colore dall'accento di sistema, e per questo il pacchetto
# resta valido con le versioni future di GNOME. I colori della Shell sono
# nel pacchetto separato ruscalinux-shell-theme (branding/shell-theme/).

set -e

# ── Identità RuscaLinux ───────────────────────────────────────────────────────
RL_VENDOR="RuscaLinux"
RL_MAINTAINER="RuscaLinux Project <packager@ruscalinux.org>"
RL_HOMEPAGE="https://www.ruscalinux.org"
RL_VERSION_SUFFIX="~ruscalinux1"
# ─────────────────────────────────────────────────────────────────────────────

PACKAGE_NAME="ruscalinux-theme"
VERSION="${1:-1.0}${RL_VERSION_SUFFIX}"
ARCH="all"

SRC="$(cd "$(dirname "$0")" && pwd)"
ORIGINAL_DIR="$(pwd)"

# I file generati devono esserci: si rigenerano con adwaita-gtk3-prugna.py.
for f in Adwaita-Prugna/index.theme \
         Adwaita-Prugna/gtk-3.0/gtk.css \
         Adwaita-Prugna/gtk-3.0/gtk-dark.css \
         Adwaita-Prugna-dark/index.theme \
         Adwaita-Prugna-dark/gtk-3.0/gtk.css \
         90_ruscalinux-theme.gschema.override \
         ruscalinux-theme-session \
         ruscalinux-theme-session.desktop; do
    if [ ! -f "$SRC/$f" ]; then
        echo "Errore: manca $f in $SRC"
        exit 1
    fi
done

# Ogni immagine citata dal CSS deve esistere, altrimenti GTK scarta la regola.
for css in gtk.css gtk-dark.css; do
    grep -o 'url("assets/[^"]*")' "$SRC/Adwaita-Prugna/gtk-3.0/$css" \
        | sed 's/^url("//; s/")$//' | sort -u | while read -r asset; do
        if [ ! -f "$SRC/Adwaita-Prugna/gtk-3.0/$asset" ]; then
            echo "Errore: $css cita $asset, che non esiste"
            exit 1
        fi
    done
done

echo "==> Vendor: $RL_VENDOR"
echo "==> Pacchetto: $PACKAGE_NAME"
echo "==> Versione: $VERSION"

TEMP_DIR=$(mktemp -d)
trap 'rm -rf "$TEMP_DIR"' EXIT
BUILD_DIR="$TEMP_DIR/${PACKAGE_NAME}_${VERSION}_${ARCH}"

echo "==> Creazione struttura pacchetto..."
mkdir -p "$BUILD_DIR/DEBIAN" \
         "$BUILD_DIR/usr/share/themes" \
         "$BUILD_DIR/usr/share/glib-2.0/schemas" \
         "$BUILD_DIR/usr/libexec/$PACKAGE_NAME" \
         "$BUILD_DIR/etc/xdg/autostart" \
         "$BUILD_DIR/usr/share/doc/$PACKAGE_NAME"

cp -r "$SRC/Adwaita-Prugna" "$SRC/Adwaita-Prugna-dark" "$BUILD_DIR/usr/share/themes/"
cp "$SRC/90_ruscalinux-theme.gschema.override" "$BUILD_DIR/usr/share/glib-2.0/schemas/"
cp "$SRC/ruscalinux-theme-session" "$BUILD_DIR/usr/libexec/$PACKAGE_NAME/"
cp "$SRC/ruscalinux-theme-session.desktop" "$BUILD_DIR/etc/xdg/autostart/"

# File copyright: il tema GTK 3 deriva da GTK e conserva la sua licenza.
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

Files: usr/share/themes/Adwaita-Prugna/gtk-3.0/*
Copyright: The GTK Team and the GTK contributors
           2026 Nunzio Curcuruto (colour conversion)
License: LGPL-2+
Comment: The Adwaita theme of GTK 3 (gtk/theme/Adwaita), with the blue
 accent converted to the RuscaLinux palette by adwaita-gtk3-prugna.py.

License: GPL-3
 This package is free software: you can redistribute it and/or modify it
 under the terms of the GNU General Public License, version 3, as published
 by the Free Software Foundation.
 .
 On Debian systems, the complete text of the GNU General Public License
 version 3 can be found in /usr/share/common-licenses/GPL-3.

License: LGPL-2+
 This library is free software; you can redistribute it and/or modify it
 under the terms of the GNU Library General Public License as published by
 the Free Software Foundation; either version 2 of the License, or (at your
 option) any later version.
 .
 On Debian systems, the complete text of the GNU Library General Public
 License version 2 can be found in /usr/share/common-licenses/LGPL-2.
EOF

echo "==> Creazione file control..."
cat > "$BUILD_DIR/DEBIAN/control" << EOF
Package: $PACKAGE_NAME
Version: $VERSION
Section: x11
Priority: optional
Architecture: $ARCH
Vendor: $RL_VENDOR
Depends: gsettings-desktop-schemas (>= 47), libglib2.0-bin
Recommends: ruscalinux-adwaita-prugna, ruscalinux-backgrounds
Maintainer: $RL_MAINTAINER
Homepage: $RL_HOMEPAGE
Description: Desktop theme for $RL_VENDOR (plum and pink)
 Gives the GNOME desktop the $RL_VENDOR colours using only supported
 mechanisms, so that it keeps working with future GNOME releases:
 .
  * the system accent colour, followed by GNOME Shell, the login screen
    and every libadwaita application;
  * Adwaita-Prugna, the Adwaita theme of GTK 3 with the plum and pink
    accent, in light and dark variants, for GTK 3 applications;
  * a small session helper: GTK 3 applications follow the light or dark
    style chosen in Settings, and the GNOME Shell theme of
    ruscalinux-shell-theme steps aside when high contrast is on.
 .
 These are defaults: every user can change them in Settings or Tweaks.
 .
 Built for $RL_VENDOR — $RL_HOMEPAGE
EOF

# Il file in /etc e' un file di configurazione: dpkg ne conserva le modifiche.
echo "/etc/xdg/autostart/ruscalinux-theme-session.desktop" > "$BUILD_DIR/DEBIAN/conffiles"

# I valori predefiniti (gschema override) vanno compilati. Lo fa gia' il
# trigger di libglib2.0-0 sulla cartella degli schemi; qui lo si ripete per
# i sistemi dove il trigger non parte.
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
find "$BUILD_DIR/usr" "$BUILD_DIR/etc" -type d -exec chmod 755 {} \;
find "$BUILD_DIR/usr" "$BUILD_DIR/etc" -type f -exec chmod 644 {} \;
chmod 755 "$BUILD_DIR/usr/libexec/$PACKAGE_NAME/ruscalinux-theme-session"

INSTALLED_SIZE=$(du -sk "$BUILD_DIR/usr" | cut -f1)
echo "Installed-Size: $INSTALLED_SIZE" >> "$BUILD_DIR/DEBIAN/control"

echo "==> Costruzione pacchetto .deb..."
DEB_FILE="${PACKAGE_NAME}_${VERSION}_${ARCH}.deb"
dpkg-deb --build --root-owner-group "$BUILD_DIR" "$ORIGINAL_DIR/$DEB_FILE" > /dev/null

echo ""
echo "✅ Pacchetto creato con successo: $DEB_FILE"
echo ""
echo "Per installare:"
echo "  sudo apt install ./$DEB_FILE"
echo ""
echo "Chi ha gia' cambiato tema, icone o accento conserva le proprie scelte."
echo "Per tornare ai valori predefiniti di RuscaLinux:"
echo "  gsettings reset org.gnome.desktop.interface accent-color"
echo "  gsettings reset org.gnome.desktop.interface gtk-theme"
echo "  gsettings reset org.gnome.desktop.interface icon-theme"
