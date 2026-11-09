#!/bin/sh
# LISTA DEI PACCHETTI DA INSTALLARE
cat <<EOF >> .work/config/package-lists/live.list.chroot
# GNOME
gnome-core
gnome-tweaks
gnome-initial-setup

# Internet
gufw
firefox-esr
thunderbird
qbittorrent
yt-dlp

# Ufficio
libreoffice
libreoffice-gnome
libreoffice-style-elementary

# Grafica
gimp
imagemagick
gcolor3
eog

# Ebooks
gnome-epub-thumbnailer
calibre
foliate

# Scrittura
goldendict-ng

# Audio
audacious
audacity
soundconverter
easytag
lame
abcde
mp3splt

# Video
smplayer
ffmpeg
obs-studio
shotcut
handbrake
mkvtoolnix-gui
mediainfo
guvcview

# Giochi
aisleriot
dolphin-emu

# Strumenti
sudo
brasero
qemu-system-x86
adb
unrar-free
live-build
squashfs-tools
fastfetch
pdftk
tree
file-roller

# Dischi e recupero: controllo e riparazione dei filesystem (fsck), stato dei
# dischi (smartctl), copia di dischi danneggiati (ddrescue), recupero di
# partizioni e file cancellati (testdisk, photorec). GNOME Dischi arriva gia'
# con gnome-core. Utili anche dalla sessione live, per riparare il disco di
# sistema senza montarlo.
e2fsprogs
dosfstools
exfatprogs
ntfs-3g
xfsprogs
btrfs-progs
smartmontools
gddrescue
testdisk

# Linux e sviluppo
build-essential
pkg-config
libglvnd-dev
linux-image-amd64
linux-headers-amd64
git
python3-venv
python3-tk

# Costruire RuscaLinux da RuscaLinux (build.sh, make-debs.sh, test.sh).
# live-build, squashfs-tools, sudo, git e build-essential (con dpkg-dev)
# sono gia' sopra.
unzip
python3-fonttools
lintian
qemu-utils
ovmf
# Test dei tool: rilettura dei PDF prodotti da RuscaWriter
python3-pypdf

# Compilare ruscallama-engine (llama.cpp con il backend Vulkan):
# vedi tools/ruscallama-engine/README.md
cmake
wget
libvulkan-dev
glslc
spirv-headers

# ===========================================================================
# LIBS SUPPORT
# ===========================================================================
python3-gi-cairo

# Motore Markdown comune di RuscaLLama, RuscaMark e RuscaWriter
# (tools/*/rusca_markdown.py, CommonMark)
python3-markdown-it
python3-mdit-py-plugins
python3-linkify-it

# RuscaWriter: sillabazione del PDF (Pyphen) e generatore di copertine (Pillow)
python3-pyphen
python3-pil

# Google Chrome - https://www.google.com/
# Nessuna libreria in più: il pacchetto .deb ha già tutto

# Visual Studio Code - https://code.visualstudio.com/
socat

# DaVinci Resolve - https://www.blackmagicdesign.com/products/davinciresolve
libglu1-mesa
libxcb-damage0

# Discord - https://discord.com/
libdee-1.0-4
libunity-protocol-private0
libunity-scopes-json-def-desktop
libunity9

# Obsidian - https://obsidian.md/
libayatana-appindicator3-1
libayatana-ido3-0.4-0
libayatana-indicator3-7

# ===========================================================================
# MULTILINGUAL SUPPORT
# ===========================================================================

# --- Fonts for non-Latin scripts (Noto covers virtually all scripts) ---
# Not the "fonts-noto" metapackage: it also pulls fonts-noto-cjk-extra and
# fonts-noto-ui-extra, about 280 MB of extra weights (Thin, Light, Black...).
# The packages below cover every script in regular and bold. fonts-noto-extra
# stays: LibreOffice asks for it and it covers Urdu.
fonts-noto-core
fonts-noto-ui-core
fonts-noto-mono
fonts-noto-color-emoji
fonts-noto-cjk
fonts-noto-extra

# --- IBus input method framework (required for CJK, Arabic, Indic scripts) ---
ibus
ibus-gtk3
ibus-gtk4
ibus-m17n
m17n-db
ibus-pinyin

# --- English (en_US) ---
task-english
hunspell-en-us
aspell-en
mythes-en-us
hyphen-en-us
# GIMP manual in English only: about 68 MB per language. In the other
# languages GIMP offers to open the online manual.
gimp-help-en

# --- English (en_GB...) ---
libreoffice-l10n-en-gb
hyphen-en-gb
mythes-en-au
hunspell-en-gb
hunspell-en-au
hunspell-en-ca
hunspell-en-za

# --- Spanish (es) ---
task-spanish
manpages-es
hunspell-es
aspell-es
mythes-es
hyphen-es
libreoffice-l10n-es
firefox-esr-l10n-es-es
thunderbird-l10n-es-es

# --- French (fr) ---
task-french
manpages-fr
hunspell-fr
aspell-fr
mythes-fr
hyphen-fr
libreoffice-l10n-fr
firefox-esr-l10n-fr
thunderbird-l10n-fr

# --- German (de) ---
task-german
manpages-de
hunspell-de-de
aspell-de
mythes-de
hyphen-de
libreoffice-l10n-de
firefox-esr-l10n-de
thunderbird-l10n-de

# --- Portuguese Brazil (pt_BR) ---
task-brazilian-portuguese
manpages-pt-br
hunspell-pt-br
aspell-pt-br
mythes-pt-br
hyphen-pt-br
libreoffice-l10n-pt-br
firefox-esr-l10n-pt-br
thunderbird-l10n-pt-br

# --- Russian (ru) ---
task-russian
manpages-ru
hunspell-ru
aspell-ru
mythes-ru
hyphen-ru
libreoffice-l10n-ru
firefox-esr-l10n-ru
thunderbird-l10n-ru

# --- Arabic (ar) ---
task-arabic
hunspell-ar
aspell-ar
libreoffice-l10n-ar
firefox-esr-l10n-ar
thunderbird-l10n-ar

# --- Chinese Simplified (zh_CN) ---
task-chinese-s
libreoffice-l10n-zh-cn
firefox-esr-l10n-zh-cn
thunderbird-l10n-zh-cn

# --- Hindi (hi) ---
task-hindi
libreoffice-l10n-hi
firefox-esr-l10n-hi-in

# --- Bengali (bn) ---
task-bengali
libreoffice-l10n-bn
firefox-esr-l10n-bn

# --- Indonesian (id) ---
hunspell-id
libreoffice-l10n-id
firefox-esr-l10n-id
thunderbird-l10n-id

# --- Urdu (ur) ---
# (no task-urdu, libreoffice-l10n-ur or hunspell-ur in Debian trixie;
# fonts-noto-extra covers the script)
firefox-esr-l10n-ur

# --- Italian (it) ---
task-italian
manpages-it
hunspell-it
aspell-it
mythes-it
hyphen-it
libreoffice-l10n-it
libreoffice-help-it
firefox-esr-l10n-it
thunderbird-l10n-it

# --- Japanese (ja) ---
task-japanese
ibus-mozc
libreoffice-l10n-ja
firefox-esr-l10n-ja
thunderbird-l10n-ja

# Supporto legacy AppImages
libfuse2t64

# ===========================================================================
# SUPPORTO MULTILINGUA ESTESO — LINGUE EUROPEE
# ===========================================================================

# --- Polacco (pl) ---
task-polish
hunspell-pl
aspell-pl
hyphen-pl
libreoffice-l10n-pl
firefox-esr-l10n-pl
thunderbird-l10n-pl

# --- Olandese (nl) ---
task-dutch
hunspell-nl
aspell-nl
hyphen-nl
libreoffice-l10n-nl
firefox-esr-l10n-nl
thunderbird-l10n-nl

# --- Ceco (cs) ---
task-czech
hunspell-cs
aspell-cs
hyphen-cs
libreoffice-l10n-cs
firefox-esr-l10n-cs
thunderbird-l10n-cs

# --- Slovacco (sk) ---
task-slovak
hunspell-sk
aspell-sk
hyphen-sk
libreoffice-l10n-sk
firefox-esr-l10n-sk
thunderbird-l10n-sk

# --- Rumeno (ro) ---
task-romanian
hunspell-ro
aspell-ro
hyphen-ro
libreoffice-l10n-ro
firefox-esr-l10n-ro
thunderbird-l10n-ro

# --- Ungherese (hu) ---
task-hungarian
hunspell-hu
aspell-hu
hyphen-hu
libreoffice-l10n-hu
firefox-esr-l10n-hu
thunderbird-l10n-hu

# --- Svedese (sv) ---
task-swedish
hunspell-sv
aspell-sv
hyphen-sv
libreoffice-l10n-sv
firefox-esr-l10n-sv-se
thunderbird-l10n-sv-se

# --- Norvegese Bokmål (nb) ---
task-norwegian
hunspell-no
aspell-no
libreoffice-l10n-nb
firefox-esr-l10n-nb-no
thunderbird-l10n-nb-no

# --- Danese (da) ---
task-danish
hunspell-da
aspell-da
libreoffice-l10n-da
firefox-esr-l10n-da
thunderbird-l10n-da

# --- Finlandese (fi) ---
task-finnish
voikko-fi
libreoffice-voikko
libreoffice-l10n-fi
firefox-esr-l10n-fi
thunderbird-l10n-fi

# --- Greco (el) ---
task-greek
hunspell-el
aspell-el
libreoffice-l10n-el
firefox-esr-l10n-el
thunderbird-l10n-el

# --- Bulgaro (bg) ---
task-bulgarian
hunspell-bg
aspell-bg
libreoffice-l10n-bg
firefox-esr-l10n-bg
thunderbird-l10n-bg

# --- Ucraino (uk) ---
task-ukrainian
hunspell-uk
aspell-uk
libreoffice-l10n-uk
firefox-esr-l10n-uk
thunderbird-l10n-uk

# --- Croato (hr) ---
task-croatian
hunspell-hr
libreoffice-l10n-hr
firefox-esr-l10n-hr
thunderbird-l10n-hr

# --- Serbo (sr) ---
task-serbian
hunspell-sr
libreoffice-l10n-sr
firefox-esr-l10n-sr
thunderbird-l10n-sr

# --- Turco (tr) ---
task-turkish
hunspell-tr
libreoffice-l10n-tr
firefox-esr-l10n-tr
thunderbird-l10n-tr

# --- Catalano (ca) ---
task-catalan
hunspell-ca
aspell-ca
hyphen-ca
libreoffice-l10n-ca
firefox-esr-l10n-ca
thunderbird-l10n-ca

# --- Lituano (lt) ---
task-lithuanian
hunspell-lt
aspell-lt
libreoffice-l10n-lt
firefox-esr-l10n-lt
thunderbird-l10n-lt

# --- Lettone (lv) ---
task-latvian
hunspell-lv
aspell-lv
libreoffice-l10n-lv
firefox-esr-l10n-lv
thunderbird-l10n-lv

# --- Estone (et) ---
task-estonian
hunspell-et
aspell-et
libreoffice-l10n-et
firefox-esr-l10n-et
thunderbird-l10n-et

# --- Sloveno (sl) ---
task-slovenian
hunspell-sl
libreoffice-l10n-sl
firefox-esr-l10n-sl
thunderbird-l10n-sl

# --- Portoghese Europeo (pt_PT) ---
task-portuguese
hunspell-pt-pt
aspell-pt
mythes-pt-pt
hyphen-pt-pt
libreoffice-l10n-pt
firefox-esr-l10n-pt-pt
thunderbird-l10n-pt-pt

# --- Galiziano (gl) ---
task-galician
hunspell-gl
hyphen-gl
mythes-gl
libreoffice-l10n-gl
firefox-esr-l10n-gl
thunderbird-l10n-gl

# --- Basco (eu) ---
task-basque
hunspell-eu
aspell-eu
libreoffice-l10n-eu
firefox-esr-l10n-eu
thunderbird-l10n-eu

# ===========================================================================
# SUPPORTO MULTILINGUA ESTESO — LINGUE MONDIALI
# ===========================================================================

# --- Coreano (ko) ---
task-korean
ibus-hangul
hunspell-ko
libreoffice-l10n-ko
firefox-esr-l10n-ko
thunderbird-l10n-ko

# --- Cinese Tradizionale (zh_TW) ---
task-chinese-t
# Metodo di input Zhuyin (Bopomofo), quello usato di solito a Taiwan
ibus-chewing
libreoffice-l10n-zh-tw
firefox-esr-l10n-zh-tw
thunderbird-l10n-zh-tw

# --- Vietnamita (vi) ---
hunspell-vi
libreoffice-l10n-vi
firefox-esr-l10n-vi
thunderbird-l10n-vi

# --- Thai (th) ---
task-thai
fonts-thai-tlwg
libreoffice-l10n-th
firefox-esr-l10n-th
thunderbird-l10n-th

# --- Persiano / Farsi (fa) ---
task-persian
myspell-fa
libreoffice-l10n-fa
firefox-esr-l10n-fa

# --- Tamil (ta) ---
task-tamil
libreoffice-l10n-ta
firefox-esr-l10n-ta

# --- Telugu (te) ---
task-telugu
libreoffice-l10n-te
firefox-esr-l10n-te

# --- Marathi (mr) ---
task-marathi
libreoffice-l10n-mr
firefox-esr-l10n-mr

# --- Punjabi (pa) ---
task-punjabi
libreoffice-l10n-pa-in
firefox-esr-l10n-pa-in
thunderbird-l10n-pa-in

# --- Malese (ms) ---
firefox-esr-l10n-ms
thunderbird-l10n-ms

# --- Swahili (sw) ---
# (no libreoffice-l10n-sw or firefox-esr-l10n-sw in Debian trixie)
hunspell-sw
EOF
