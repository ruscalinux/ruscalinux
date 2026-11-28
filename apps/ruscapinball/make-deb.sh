#!/bin/bash
# RuscaPinball — make-deb.sh — GPL-3.0-or-later
# Crea build-deb/ruscapinball-ruscalinux_<VER>_all.deb e SHA256SUMS.
# Si lancia dalla cartella del tool, senza argomenti.
set -euo pipefail

VER="1.99.3"
PKG="ruscapinball"
APP_ID="org.ruscalinux.RuscaPinball"
APP_NAME="RuscaPinball"

cd "$(dirname "$(readlink -f "$0")")"

for f in lang/it.json lang/en.json; do
    [ -f "$f" ] || { echo "Errore: manca $f (italiano e inglese sono obbligatori)" >&2; exit 1; }
done
grep -q "^APP_VERSION = \"$VER\"" ruscapinball.py \
    || { echo "Errore: APP_VERSION di ruscapinball.py diverso da $VER" >&2; exit 1; }

echo "== Test"
# I test stanno in tests/ nella radice del repository (specifiche, sezione 1.2)
TEST="../../tests/test_ruscapinball.py"
if [ -f "$TEST" ]; then
    ( cd ../.. && python3 -m unittest tests/test_ruscapinball.py 2>&1 | tail -3 )
else
    echo "ATTENZIONE: non trovo $TEST, test saltati"
fi

OUT="build-deb"
PKGDIR="$OUT/pkgroot"
rm -rf "$OUT"
SHARE="$PKGDIR/usr/share"
install -d "$PKGDIR/DEBIAN" "$PKGDIR/usr/games" "$SHARE/$PKG/lang" \
    "$SHARE/applications" "$SHARE/metainfo" \
    "$SHARE/icons/hicolor/scalable/apps" "$SHARE/icons/hicolor/symbolic/apps" \
    "$SHARE/doc/$PKG" "$SHARE/man/man6"

echo "== File del programma"
install -m 0755 ruscapinball.py "$SHARE/$PKG/ruscapinball.py"
install -m 0644 rp_physics.py rp_table.py rp_view.py rp_sound.py ruscapinball.svg "$SHARE/$PKG/"
install -m 0644 lang/*.json "$SHARE/$PKG/lang/"
ln -s "../share/$PKG/ruscapinball.py" "$PKGDIR/usr/games/$PKG"   # Debian Policy 11.11: i giochi in /usr/games
install -m 0644 ruscapinball.svg "$SHARE/icons/hicolor/scalable/apps/$APP_ID.svg"
install -m 0644 ruscapinball-symbolic.svg "$SHARE/icons/hicolor/symbolic/apps/$APP_ID-symbolic.svg"

echo "== .desktop e metainfo dai file di lang/"
python3 -I - "$SHARE" "$APP_ID" "$APP_NAME" "$PKG" "$VER" "$(pwd)/lang" <<'PY'
import glob, json, os, sys, datetime
from xml.sax.saxutils import escape
share, app_id, name, pkg, ver, lang_dir = sys.argv[1:]
langs = {}
for path in sorted(glob.glob(os.path.join(lang_dir, "*.json"))):
    with open(path, encoding="utf-8") as fh:
        langs[os.path.basename(path)[:-5]] = json.load(fh)
en = langs["en"]
d = ["[Desktop Entry]", "Type=Application", f"Name={name}",
     f"Comment={en['app_description']}"]
for code, s in langs.items():
    if code != "en" and s.get("app_description"):
        d.append(f"Comment[{code}]={s['app_description']}")
d += [f"Exec=/usr/games/{pkg}", f"Icon={app_id}", "Terminal=false",
      "Categories=Game;ArcadeGame;X-RuscaLinux-Apps;", f"Keywords={en['keywords']}"]
for code, s in langs.items():
    if code != "en" and s.get("keywords"):
        d.append(f"Keywords[{code}]={s['keywords']}")
d += ["StartupNotify=true", f"StartupWMClass={app_id}", "PrefersNonDefaultGPU=false"]
with open(os.path.join(share, "applications", app_id + ".desktop"), "w", encoding="utf-8") as fh:
    fh.write("\n".join(d) + "\n")

def tr(tag, key, indent="  "):
    out = [f"{indent}<{tag}>{escape(en[key])}</{tag}>"]
    for code, s in langs.items():
        if code != "en" and s.get(key):
            out.append(f'{indent}<{tag} xml:lang="{code}">{escape(s[key])}</{tag}>')
    return "\n".join(out)

desc = [f"    <p>{escape(en['app_long'])}</p>"]
for code, s in langs.items():
    if code != "en" and s.get("app_long"):
        desc.append(f'    <p xml:lang="{code}">{escape(s["app_long"])}</p>')
today = datetime.date.today().isoformat()
meta = f'''<?xml version="1.0" encoding="UTF-8"?>
<component type="desktop-application">
  <id>{app_id}</id>
  <name>{name}</name>
{tr("summary", "app_description")}
  <metadata_license>CC0-1.0</metadata_license>
  <project_license>GPL-3.0-or-later</project_license>
  <developer id="org.ruscalinux">
    <name>Nunzio Curcuruto</name>
  </developer>
  <description>
{chr(10).join(desc)}
  </description>
  <launchable type="desktop-id">{app_id}.desktop</launchable>
  <url type="homepage">https://www.ruscalinux.org</url>
  <categories>
    <category>Game</category>
    <category>ArcadeGame</category>
  </categories>
  <supports>
    <control>keyboard</control>
    <control>gamepad</control>
  </supports>
  <content_rating type="oars-1.1"/>
  <releases>
    <release version="{ver}" date="{today}"/>
  </releases>
</component>
'''
with open(os.path.join(share, "metainfo", app_id + ".metainfo.xml"), "w", encoding="utf-8") as fh:
    fh.write(meta)
PY

echo "== Documentazione"
cat > "$SHARE/doc/$PKG/copyright" <<EOF
Format: https://www.debian.org/doc/packaging-manuals/copyright-format/1.0/
Upstream-Name: $APP_NAME
Upstream-Contact: Nunzio Curcuruto <info@ruscalinux.org>
Source: https://github.com/ruscalinux/ruscalinux
Comment: Design, specifications and testing by the author; code written with
 the assistance of AI tools. See NOTA-IA.md in the RuscaLinux repository.
 .
 Original table, graphics and sounds: no code or data from other games.

Files: *
Copyright: 2026 Nunzio Curcuruto <info@ruscalinux.org>
License: GPL-3.0-or-later
 This program is free software: you can redistribute it and/or modify
 it under the terms of the GNU General Public License as published by
 the Free Software Foundation, either version 3 of the License, or
 (at your option) any later version.
 .
 On Debian systems, the complete text of the GNU General Public License
 version 3 can be found in "/usr/share/common-licenses/GPL-3".
EOF
for m in docs/MANUAL_it.md docs/MANUAL_en.md; do
    [ -f "$m" ] && gzip -9n -c "$m" > "$SHARE/doc/$PKG/$(basename "$m").gz"
done
DATE="$(date -R)"
printf '%s (%s) unstable; urgency=medium\n\n  * Prima versione di RuscaPinball, con il tavolo Amethyst.\n\n -- Nunzio Curcuruto <info@ruscalinux.org>  %s\n' \
    "$PKG" "$VER" "$DATE" | gzip -9n > "$SHARE/doc/$PKG/changelog.gz"
cat > "$OUT/$PKG.6" <<EOF
.TH RUSCAPINBALL 6 "$(date +%Y-%m-%d)" "$VER" "RuscaLinux"
.SH NAME
ruscapinball \- 1980s-style pinball for RuscaLinux
.SH SYNOPSIS
.B ruscapinball
[\-\-fullscreen] [\-\-version]
.SH DESCRIPTION
Pinball game with an original table, "Amethyst", seen in perspective.
Z / Left Shift: left flipper;
M / Right Shift: right flipper; hold Space: launch; N: nudge;
P: pause; F2: TV effect; F3: sound; F11: fullscreen; Esc: quit.
.SH FILES
~/.local/share/ruscapinball/scores.json, ~/.config/ruscapinball/settings.json
EOF
gzip -9n -c "$OUT/$PKG.6" > "$SHARE/man/man6/$PKG.6.gz"
rm "$OUT/$PKG.6"

echo "== control"
SIZE="$(du -sk --exclude=DEBIAN "$PKGDIR" | cut -f1)"
cat > "$PKGDIR/DEBIAN/control" <<EOF
Package: $PKG
Version: $VER
Section: games
Priority: optional
Architecture: all
Depends: python3 (>= 3.10), python3-pygame (>= 2.1)
Recommends: fonts-dejavu-core, fonts-noto-core, fonts-noto-cjk, python3-arabic-reshaper, python3-bidi
Installed-Size: $SIZE
Maintainer: Nunzio Curcuruto <info@ruscalinux.org>
Homepage: https://www.ruscalinux.org
Description: 1980s-style pinball for RuscaLinux
 RuscaPinball is a pinball game with realistic physics and an original
 table, "Amethyst", seen in perspective in the style of 1980s home
 computer pinball games: three bumpers, slingshots, drop targets, the
 R-U-S-C-A letters, the bonus trap, the ring of bonus lamps with the
 SPECIAL, multiplier, ball save and tilt. Original graphics and sounds;
 playable with keyboard or gamepad.
EOF

find "$PKGDIR" -type d -exec chmod 0755 {} +
( cd "$PKGDIR" && find usr -type f -exec md5sum {} + | sort -k2 > DEBIAN/md5sums )
command -v desktop-file-validate >/dev/null && desktop-file-validate "$SHARE/applications/$APP_ID.desktop"
command -v appstreamcli >/dev/null && appstreamcli validate --no-net "$SHARE/metainfo/$APP_ID.metainfo.xml" || true

DEB="$OUT/$PKG-ruscalinux_${VER}_all.deb"
dpkg-deb --root-owner-group --build "$PKGDIR" "$DEB"
rm -rf "$PKGDIR"
( cd "$OUT" && sha256sum *.deb > SHA256SUMS )
echo "== Fatto: $DEB"
