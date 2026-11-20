#!/bin/sh
set -e

# COPIA DEI PACCHETTI DA LOCAL PER ESSERE INSTALLATI DURANTE LA FASE DI BUILD
# adwaita-prugna, ruscalinux-backgrounds-it, ruscalinux-fonts, ruscalinux-theme,
# ruscalinux-shell-theme e le utility di
# apps/ (ruscacleaner, ruscahub, ruscamark, ruscawriter, ruscallama-engine, ruscallama,
# ruscatranslator, ruscawhisper-engine, ruscatranscriber, ruscanarrator,
# ruscadiffusion-engine, ruscapinball, ruscavosk-engine, ruscapiper-engine,
# ruscallisse)
cp local/extra_debs/*.deb .work/config/packages.chroot/

# IMPOSTAZIONE splash.png BINARY
mkdir -p .work/config/includes.binary/boot/grub/
mkdir -p .work/config/includes.binary/isolinux/
cp local/grub/splash.png .work/config/includes.binary/boot/grub/
cp local/isolinux/splash.png .work/config/includes.binary/isolinux/
# Colori e posizioni del menu BIOS (generati con il tema GRUB): l'hook
# binario qui sotto li mette al posto dello stdmenu.cfg di live-build.
cp local/isolinux/stdmenu.cfg .work/config/includes.binary/isolinux/ruscalinux-stdmenu.cfg

# TEMA GRUB RUSCALINUX (ISO e sistema installato)
# Generato da branding/generators/ruscalinux-grub-theme.py in
# local/grub/ruscalinux/. Nella ISO va in boot/grub/themes/ruscalinux;
# l'hook binario qui sotto lo attiva. boot/grub/splash.png (da
# local/grub/splash.png, lo stesso fondo del tema) non si vede, ma resta:
# theme.cfg di live-build attiva il tema solo se quel file esiste.
TEMA_GRUB=local/grub/ruscalinux
for dest in .work/config/includes.binary/boot/grub/themes/ruscalinux \
            .work/config/includes.chroot_after_packages/boot/grub/themes/ruscalinux; do
    mkdir -p "$dest"
    cp "$TEMA_GRUB"/* "$dest"/
    sed -i "s|{{VERSION}}|@VERSION@|" "$dest/theme.txt"
done

# Hook binario: gira quando live-build ha gia' scritto i file di GRUB.
#  - theme.cfg: carica i font del tema e attiva il tema RuscaLinux al posto
#    di live-theme;
#  - config.cfg: live-build chiede 800x600 (come la netinst Debian), troppo
#    poco per il menu; si chiede 1920x1080, poi 1280x720, poi la modalita'
#    preferita dallo schermo.
mkdir -p .work/config/hooks/normal/
cat <<'EOF' > .work/config/hooks/normal/9010-ruscalinux-grub-theme.hook.binary
#!/bin/sh
set -e
[ -d binary ] && cd binary

TEMA=/boot/grub/themes/ruscalinux
if [ ! -f ".$TEMA/theme.txt" ]; then
    echo "ATTENZIONE: tema GRUB RuscaLinux mancante in .$TEMA" >&2
    exit 0
fi

if grep -q "set theme=" boot/grub/theme.cfg; then
    awk -v tema="$TEMA" -v font="$(ls ".$TEMA"/*.pf2 | sed 's|^\.||' | tr '\n' ' ')" '
        /set theme=/ {
            match($0, /^[ \t]*/); rientro = substr($0, 1, RLENGTH)
            n = split(font, f, " ")
            for (i = 1; i <= n; i++) print rientro "loadfont " f[i]
            print rientro "set theme=" tema "/theme.txt"
            next
        }
        { print }
    ' boot/grub/theme.cfg > boot/grub/theme.cfg.nuovo
    mv boot/grub/theme.cfg.nuovo boot/grub/theme.cfg
    echo "Tema GRUB RuscaLinux attivato in boot/grub/theme.cfg"
else
    echo "ATTENZIONE: in boot/grub/theme.cfg non c'e' 'set theme=': tema non attivato" >&2
fi

# Menu BIOS (isolinux): stdmenu.cfg di RuscaLinux al posto di quello di
# live-build. Lo includono il menu principale e tutti i sottomenu.
if [ -f isolinux/ruscalinux-stdmenu.cfg ] && [ -f isolinux/stdmenu.cfg ]; then
    mv isolinux/ruscalinux-stdmenu.cfg isolinux/stdmenu.cfg
    echo "Menu isolinux RuscaLinux attivato in isolinux/stdmenu.cfg"
else
    echo "ATTENZIONE: menu isolinux RuscaLinux non attivato" >&2
fi

if grep -q "set gfxmode=800x600" boot/grub/config.cfg; then
    sed -i "s|set gfxmode=800x600|set gfxmode=1920x1080,1280x720,auto|" boot/grub/config.cfg
    echo "Risoluzione GRUB: 1920x1080, poi 1280x720, poi automatica"
else
    echo "ATTENZIONE: in boot/grub/config.cfg non c'e' 'set gfxmode=800x600'" >&2
fi
EOF
chmod +x .work/config/hooks/normal/9010-ruscalinux-grub-theme.hook.binary

# NOME E VERSIONE DEL SISTEMA OPERATIVO
# Un solo file, /usr/lib/os-release, come in Debian: /etc/os-release e' il
# collegamento di base-files che punta a lui (lo controlla l'hook
# 9989-ruscalinux-diversions, che registra anche la sostituzione presso dpkg).
# Lo leggono GDM, gnome-shell, gnome-initial-setup, fastfetch, lsb_release.
mkdir -p .work/config/includes.chroot_after_packages/usr/lib/
cat <<EOF > .work/config/includes.chroot_after_packages/usr/lib/os-release
PRETTY_NAME="RuscaLinux @VERSION@"
NAME="RuscaLinux"
VERSION_ID="@VERSION@"
VERSION="@VERSION@"
VERSION_CODENAME=trixie
ID=ruscalinux
ID_LIKE=debian
LOGO="ruscalinux-logo"
HOME_URL="https://www.ruscalinux.org/"
SUPPORT_URL="https://www.ruscalinux.org/support"
BUG_REPORT_URL="https://bugs.ruscalinux.org/"
EOF

# ---------------------------------------------------------------------------
# FIX: NOME UTENTE E PASSWORD NELLA SCHERMATA DI LOGIN
mkdir -p .work/config/includes.chroot_after_packages/etc/live/config.conf.d/
echo 'LIVE_USER_FULLNAME="RuscaLinux Live user"
LIVE_USER_DEFAULT_PASSWORD="live"' > .work/config/includes.chroot_after_packages/etc/live/config.conf.d/99-ruscalinux-user.conf

# Sovrascrive i banner testuali di sistema usati da GDM come fallback
echo "RuscaLinux @VERSION@  \n \l" > .work/config/includes.chroot_after_packages/etc/issue
echo "RuscaLinux @VERSION@ " > .work/config/includes.chroot_after_packages/etc/issue.net

# COPIA DEL LOGO PER GNOME-INITIAL-SETUP E PANNELLO INFO
mkdir -p .work/config/includes.chroot_after_packages/usr/share/icons/hicolor/scalable/apps/
cp local/ruscalinux-logo.svg .work/config/includes.chroot_after_packages/usr/share/icons/hicolor/scalable/apps/ruscalinux-logo.svg

# Fallback PNG (usa quello di plymouth)
mkdir -p .work/config/includes.chroot_after_packages/usr/share/icons/hicolor/256x256/apps/
cp local/ruscalinux-logo.png .work/config/includes.chroot_after_packages/usr/share/icons/hicolor/256x256/apps/ruscalinux-logo.png

# FASTFETCH CON L'EMBLEMA DI RUSCALINUX
# Fastfetch sceglie il logo da ID di os-release; "ruscalinux" non lo conosce
# e ripiega su ID_LIKE=debian. Le impostazioni di sistema
# (/etc/xdg/fastfetch/config.jsonc) gli danno l'emblema, disegnato a
# caratteri in local/fastfetch/ruscalinux.txt. Il file di un utente
# (~/.config/fastfetch/config.jsonc) ha la precedenza.
mkdir -p .work/config/includes.chroot_after_packages/usr/share/ruscalinux/fastfetch/
cp local/fastfetch/ruscalinux.txt .work/config/includes.chroot_after_packages/usr/share/ruscalinux/fastfetch/ruscalinux.txt
mkdir -p .work/config/includes.chroot_after_packages/etc/xdg/fastfetch/
cp local/fastfetch/config.jsonc .work/config/includes.chroot_after_packages/etc/xdg/fastfetch/config.jsonc

# IMPOSTA SFONDI PREDEFINITI DI GNOME E PERSONALIZZAZIONI
# Accento, tema GTK 3 e icone NON si impostano qui: li imposta il pacchetto
# ruscalinux-theme (branding/theme/90_ruscalinux-theme.gschema.override).
# Il tema della Shell lo imposta ruscalinux-shell-theme (branding/shell-theme/).
# Disabilita anche le notifiche di aggiornamento di gnome-software (sessione live e installata)
mkdir -p .work/config/includes.chroot_after_packages/usr/share/glib-2.0/schemas
cat <<EOF > .work/config/includes.chroot_after_packages/usr/share/glib-2.0/schemas/99_ruscalinux-backgrounds-it.gschema.override
[org.gnome.desktop.background]
picture-uri='file:///usr/share/backgrounds/ruscalinux-backgrounds/ruscalinux-wallpaper-mid.png'
picture-uri-dark='file:///usr/share/backgrounds/ruscalinux-backgrounds/ruscalinux-wallpaper-dark.png'

[org.gnome.desktop.screensaver]
picture-uri='file:///usr/share/backgrounds/ruscalinux-backgrounds/ruscalinux-wallpaper-dark.png'

[org.gnome.software]
allow-updates=false
download-updates=false
download-updates-notify=false

[org.gnome.shell]
disable-user-extensions=false
# Pannello (dash): Firefox, Thunderbird, Terminale, File, Editor di testo,
# Calcolatrice. Il terminale e' GNOME Terminale (gnome-terminal, la prima
# scelta di gnome-core in Debian 13). Senza questa chiave vale l'elenco di
# GNOME, che finisce con Aiuto (yelp), nascosto piu' sotto. E' un valore
# predefinito: vale per gli utenti nuovi e per chi non ha mai cambiato i
# preferiti.
favorite-apps=['firefox-esr.desktop', 'thunderbird.desktop', 'org.gnome.Terminal.desktop', 'org.gnome.Nautilus.desktop', 'org.gnome.TextEditor.desktop', 'org.gnome.Calculator.desktop']
# Tour di benvenuto (gnome-tour, il pallone aerostatico): gnome-shell lo
# lancia al primo accesso di ogni utente se questa chiave e' vuota. Con un
# valore predefinito non parte mai, ne' nella live ne' sul sistema
# installato; l'utente puo' sempre aprirlo a mano.
welcome-dialog-last-shown-version='9999.0'

# PRIVACY E SICUREZZA
# Valori predefiniti; l'utente puo' cambiarli da Impostazioni.
#  • la cronologia file resta SPENTA: e' l'elenco dei documenti aperti di
#    recente, condiviso fra le applicazioni.
#  • la durata resta "per sempre" (-1): e' irrilevante finche' la cronologia
#    e' spenta, ma se l'utente la riaccende non si trova una scadenza
#    imposta da noi.
#  • il cestino NON si svuota da solo: cancellare file dell'utente senza
#    che l'abbia chiesto e' una sorpresa sgradevole.
#  • i file temporanei SI', dopo 1 giorno: non sono roba dell'utente.
[org.gnome.desktop.privacy]
remember-recent-files=false
recent-files-max-age=-1
remove-old-trash-files=false
remove-old-temp-files=true
old-files-age=uint32 1

EOF

mkdir -p .work/config/hooks/normal/
cat <<EOF > .work/config/hooks/normal/9999-compile-schemas.hook.chroot
#!/bin/sh
glib-compile-schemas /usr/share/glib-2.0/schemas/
EOF

# ---------------------------------------------------------------------------
# CARTELLA "RuscaLinux Apps" NELLA GRIGLIA DELLE APPLICAZIONI
#
# Tutte le RuscaLinux OS Apps stanno in una cartella. GNOME Shell 48 crea le
# sue cartelle (Sistema, Utilita') al primo accesso di ogni utente, ma solo
# se l'elenco delle cartelle e' vuoto (js/ui/appDisplay.js,
# _ensureDefaultFolders): un elenco predefinito messo con dconf gli
# impedirebbe di crearle. Per questo, come per nvidia-settings
# (steps/40-nvidia.sh), uno script avviato all'accesso aggiunge la cartella
# DOPO che GNOME ha creato le sue, una volta sola per utente: se l'utente la
# rinomina, la svuota o la elimina, la sua scelta resta.
#
# La cartella raccoglie le applicazioni per categoria: ogni tool ha
# X-RuscaLinux-Apps fra le Categories del suo .desktop (scritto dal suo
# make-deb.sh), quindi un tool nuovo ci entra da solo, senza toccare questo
# script. Per sicurezza si elencano anche i .desktop org.ruscalinux.* gia'
# installati.
mkdir -p .work/config/includes.chroot_after_packages/usr/lib/ruscalinux \
         .work/config/includes.chroot_after_packages/etc/xdg/autostart
cat <<'EOF' > .work/config/includes.chroot_after_packages/usr/lib/ruscalinux/ruscalinux-apps-folder
#!/bin/sh
# RuscaLinux — mette le RuscaLinux OS Apps nella cartella "RuscaLinux Apps"
# della griglia delle applicazioni di GNOME, una volta per utente. Scritto da
# steps/30-custom.sh; avviato da
# /etc/xdg/autostart/ruscalinux-apps-folder.desktop.

# ID e' il nome della cartella per dconf (niente spazi); NOME e' quello che
# si vede nella griglia.
ID=RuscaLinux-Apps
NOME="RuscaLinux Apps"
CARTELLE=org.gnome.desktop.app-folders
CARTELLA="org.gnome.desktop.app-folders.folder:/org/gnome/desktop/app-folders/folders/$ID/"
FATTO="${XDG_CONFIG_HOME:-$HOME/.config}/ruscalinux/ruscalinux-apps-folder.fatto"

[ -e "$FATTO" ] && exit 0
[ "$(id -u)" -ge 1000 ] || exit 0                         # utenti di sistema (GDM, g-i-s)
command -v gsettings > /dev/null || exit 0

# Al primo accesso GNOME Shell crea le sue cartelle mentre parte: si aspetta
# che l'elenco esista (al massimo un minuto).
i=0
while [ "$(gsettings get "$CARTELLE" folder-children)" = "@as []" ]; do
    i=$((i + 1))
    [ "$i" -gt 60 ] && exit 0                      # si riprova al prossimo accesso
    sleep 1
done

# I tool gia' installati, oltre alla categoria.
APPS=""
for f in /usr/share/applications/org.ruscalinux.*.desktop; do
    [ -e "$f" ] || continue
    APPS="${APPS:+$APPS, }'$(basename "$f")'"
done

gsettings set "$CARTELLA" name "$NOME"
gsettings set "$CARTELLA" translate false
gsettings set "$CARTELLA" categories "['X-RuscaLinux-Apps']"
gsettings set "$CARTELLA" apps "[$APPS]"

FIGLI=$(gsettings get "$CARTELLE" folder-children)
case "$FIGLI" in
    *"'$ID'"*) ;;                                  # c'e' gia'
    *) gsettings set "$CARTELLE" folder-children "${FIGLI%]}, '$ID']" ;;
esac

# Qualche secondo dopo, quando GNOME ha applicato tutto, si azzerano le
# posizioni salvate: GNOME ridispone le icone in ordine alfabetico, senza
# buchi dove stavano i tool. Succede solo qui, al primo accesso dell'utente:
# non c'e' ancora una disposizione personale da perdere.
sleep 5
gsettings reset org.gnome.shell app-picker-layout

mkdir -p "$(dirname "$FATTO")"
touch "$FATTO"
EOF
chmod +x .work/config/includes.chroot_after_packages/usr/lib/ruscalinux/ruscalinux-apps-folder

cat <<'EOF' > .work/config/includes.chroot_after_packages/etc/xdg/autostart/ruscalinux-apps-folder.desktop
[Desktop Entry]
Type=Application
Name=RuscaLinux Apps folder
Comment=Puts the RuscaLinux OS Apps in their folder of the app grid, once per user
Exec=/usr/lib/ruscalinux/ruscalinux-apps-folder
OnlyShowIn=GNOME;
NoDisplay=true
X-GNOME-Autostart-enabled=true
EOF

# ---------------------------------------------------------------------------
# GRIGLIA DELLE APPLICAZIONI SENZA BUCHI
#
# GNOME Shell tiene la posizione di ogni icona e non la ricompatta: quando
# delle applicazioni spariscono da una pagina (le RuscaLinux OS Apps che al
# primo accesso entrano nella cartella RuscaLinux Apps, o applicazioni tolte
# o rinominate da un aggiornamento) restano dei posti vuoti e la pagina dopo
# non scala (pagina 2 con quattro posti vuoti, pagina 3 con quattro icone).
# Azzerare la disposizione salvata non basta: GNOME ha gia' le icone in
# memoria e non le ridispone. Lo script, a ogni accesso (25 e 90 secondi
# dopo, quando gli script delle cartelle hanno finito), scrive una
# disposizione completa e compatta: le voci salvate nel loro ordine, poi le
# altre in ordine alfabetico, a pagine da 24. Scrive solo se cambia qualcosa.
# ---------------------------------------------------------------------------
cat <<'EOF' > .work/config/includes.chroot_after_packages/usr/lib/ruscalinux/ruscalinux-app-grid
#!/usr/bin/python3 -I
# RuscaLinux — toglie i buchi dalla griglia delle applicazioni di GNOME.
# Scritto da steps/30-custom.sh; avviato a ogni accesso da
# /etc/xdg/autostart/ruscalinux-app-grid.desktop.
#
# GNOME Shell tiene la posizione di ogni icona (org.gnome.shell
# app-picker-layout) e non la ricompatta. Quando delle applicazioni spariscono
# da una pagina (tolte, rinominate o spostate in una cartella, come le
# RuscaLinux OS Apps che entrano nella cartella RuscaLinux Apps al primo
# accesso) restano dei posti vuoti, e la pagina dopo non scala: pagina 2 con
# quattro posti vuoti, pagina 3 con quattro icone. Succede anche quando la
# disposizione salvata e' vuota (azzerata al primo accesso): GNOME ha gia'
# messo le icone in memoria e non le ridispone.
#
# Qui si scrive una disposizione completa e compatta: le voci della
# disposizione salvata, nel loro ordine, senza quelle che non ci sono piu' o
# che stanno in una cartella; poi le altre in ordine alfabetico, come le
# metterebbe GNOME. Le pagine sono da 24 icone: tutte le griglie di GNOME
# Shell 48 (8 × 3, 6 × 4, 4 × 6, 3 × 8, js/ui/appDisplay.js) ne tengono 24.
# Si scrive solo se cambia qualcosa; GNOME Shell rilegge la disposizione da
# solo. Lo script gira due volte, dopo gli script delle cartelle del primo
# accesso.
import locale
import os
import sys
import time

import gi
gi.require_version("Gio", "2.0")
from gi.repository import Gio, GLib  # noqa: E402

FOLDERS = "org.gnome.desktop.app-folders"
FOLDER = "org.gnome.desktop.app-folders.folder"
SHELL = "org.gnome.shell"
PER_PAGE = 24
PASSES = (25, 90)                      # secondi dall'accesso


def folder_name(settings):
    """Nome della cartella come lo mostra GNOME (tradotto, se translate)."""
    name = settings.get_string("name")
    if settings.get_boolean("translate") and name.endswith(".directory"):
        for d in [GLib.get_user_data_dir()] + list(GLib.get_system_data_dirs()):
            kf = GLib.KeyFile()
            try:
                kf.load_from_file(os.path.join(d, "desktop-directories", name),
                                  GLib.KeyFileFlags.NONE)
                return kf.get_locale_string("Desktop Entry", "Name", None)
            except GLib.Error:
                continue
    return name


def grid_items():
    """{id: nome} delle voci della griglia: le applicazioni visibili che non
    sono nel dash e non stanno in una cartella, e le cartelle."""
    favorites = set(Gio.Settings.new(SHELL).get_strv("favorite-apps"))
    apps = {a.get_id(): a for a in Gio.AppInfo.get_all()
            if isinstance(a, Gio.DesktopAppInfo) and a.should_show()}
    items, inside = {}, set()
    for fid in Gio.Settings.new(FOLDERS).get_strv("folder-children"):
        s = Gio.Settings.new_with_path(FOLDER, f"/org/gnome/desktop/app-folders/folders/{fid}/")
        excluded = set(s.get_strv("excluded-apps"))
        cats = set(s.get_strv("categories"))
        members = {a for a in s.get_strv("apps") if a in apps}
        for app in apps.values():
            if cats & set(filter(None, (app.get_categories() or "").split(";"))):
                members.add(app.get_id())
        members -= excluded | favorites
        if members:                    # GNOME non mostra le cartelle vuote
            items[fid] = folder_name(s)
        inside |= members
    for app_id, app in apps.items():
        if app_id not in inside and app_id not in favorites:
            items[app_id] = app.get_name()
    return items


def compact(pages, items):
    """Disposizione completa e senza buchi: prima le voci gia' salvate, nel
    loro ordine, poi le nuove in ordine alfabetico, a pagine di PER_PAGE."""
    order = []
    for n, page in enumerate(pages):
        for app_id, data in page.items():
            pos = int(data.get("position", 0)) if isinstance(data, dict) else 0
            order.append((n, pos, app_id))
    order.sort()
    ids = [app_id for _n, _p, app_id in order if app_id in items]
    seen = set(ids)
    ids += sorted((i for i in items if i not in seen),
                  key=lambda i: (locale.strxfrm(items[i].casefold()), i))
    return [{app_id: {"position": i} for i, app_id in enumerate(ids[k:k + PER_PAGE])}
            for k in range(0, len(ids), PER_PAGE)]


def to_variant(pages):
    return GLib.Variant("aa{sv}", [
        {app_id: GLib.Variant("a{sv}", {"position": GLib.Variant("i", d["position"])})
         for app_id, d in page.items()} for page in pages])


def fix_once():
    shell = Gio.Settings.new(SHELL)
    pages = shell.get_value("app-picker-layout").unpack()
    old = [{k: {"position": int(v.get("position", 0))} for k, v in p.items()} for p in pages]
    new = compact(pages, grid_items())
    if new and new != old:
        shell.set_value("app-picker-layout", to_variant(new))
        Gio.Settings.sync()


def main():
    try:
        locale.setlocale(locale.LC_ALL, "")
    except locale.Error:
        pass
    if not Gio.SettingsSchemaSource.get_default().lookup(SHELL, True):
        return 0
    passes = [float(a) for a in sys.argv[1:]] or PASSES
    start = time.monotonic()
    for at in passes:
        time.sleep(max(0.0, at - (time.monotonic() - start)))
        fix_once()
    return 0


if __name__ == "__main__":
    sys.exit(main())
EOF
chmod +x .work/config/includes.chroot_after_packages/usr/lib/ruscalinux/ruscalinux-app-grid

cat <<'EOF' > .work/config/includes.chroot_after_packages/etc/xdg/autostart/ruscalinux-app-grid.desktop
[Desktop Entry]
Type=Application
Name=RuscaLinux app grid
Comment=Removes the empty places left in the app grid by updates
Exec=/usr/lib/ruscalinux/ruscalinux-app-grid
OnlyShowIn=GNOME;
NoDisplay=true
X-GNOME-Autostart-enabled=true
EOF

# ---------------------------------------------------------------------------
# APPLICAZIONI PREDEFINITE
#
# Va in /etc/xdg/gnome-mimeapps.list (e, uguale, in /etc/xdg/mimeapps.list
# per le sessioni non GNOME). Non basta /usr/share/applications/mimeapps.list:
# nella stessa cartella vince /usr/share/applications/gnome-mimeapps.list di
# gnome-session-common, che sceglie Loupe per le immagini e Totem per i
# video. /etc/xdg viene prima di /usr/share e non appartiene a nessun
# pacchetto; ~/.config/mimeapps.list vince ancora, quindi la scelta
# dell'utente nel pannello Impostazioni resta libera.
#
# Immagini: Eye of GNOME (eog), nascosto nel menu ma predefinito per aprire
# le immagini. Video: SMPlayer.
#
# I sei tipi che il pannello "Applicazioni predefinite" di GNOME interroga per
# decidere cosa mostrare in ciascuna riga sono, nell'ordine: x-scheme-handler/http,
# x-scheme-handler/mailto, text/calendar, audio/x-vorbis+ogg, video/x-ogm+ogg,
# image/jpeg. Se mancassero quelli, le associazioni funzionerebbero comunque ma
# il pannello mostrerebbe righe vuote: sono i primi di ogni gruppo qui sotto.
# ---------------------------------------------------------------------------
mkdir -p .work/config/includes.chroot_after_packages/etc/xdg
cat <<'MIMEAPPS' > .work/config/includes.chroot_after_packages/etc/xdg/gnome-mimeapps.list
[Default Applications]
# Web — Firefox ESR
x-scheme-handler/http=firefox-esr.desktop
x-scheme-handler/https=firefox-esr.desktop
x-scheme-handler/about=firefox-esr.desktop
x-scheme-handler/unknown=firefox-esr.desktop
text/html=firefox-esr.desktop
application/xhtml+xml=firefox-esr.desktop

# Email — Thunderbird
x-scheme-handler/mailto=thunderbird.desktop
x-scheme-handler/mid=thunderbird.desktop
message/rfc822=thunderbird.desktop
application/x-extension-eml=thunderbird.desktop

# Calendario — GNOME Calendar
text/calendar=org.gnome.Calendar.desktop
application/x-extension-ics=org.gnome.Calendar.desktop

# Musica — Audacious
audio/x-vorbis+ogg=audacious.desktop
audio/mpeg=audacious.desktop
audio/flac=audacious.desktop
audio/ogg=audacious.desktop
audio/opus=audacious.desktop
audio/mp4=audacious.desktop
audio/x-m4a=audacious.desktop
audio/aac=audacious.desktop
audio/x-wav=audacious.desktop
audio/x-aiff=audacious.desktop
audio/x-ms-wma=audacious.desktop
audio/midi=audacious.desktop
audio/x-mpegurl=audacious.desktop
audio/x-scpls=audacious.desktop

# Video — SMPlayer
video/x-ogm+ogg=smplayer.desktop
video/mp4=smplayer.desktop
video/mpeg=smplayer.desktop
video/x-matroska=smplayer.desktop
video/webm=smplayer.desktop
video/quicktime=smplayer.desktop
video/x-msvideo=smplayer.desktop
video/x-ms-wmv=smplayer.desktop
video/x-flv=smplayer.desktop
video/ogg=smplayer.desktop
video/3gpp=smplayer.desktop
video/3gpp2=smplayer.desktop
video/x-theora+ogg=smplayer.desktop
video/vnd.avi=smplayer.desktop
video/x-avi=smplayer.desktop
video/dv=smplayer.desktop
video/mp2t=smplayer.desktop
video/x-mpeg2=smplayer.desktop
video/x-m4v=smplayer.desktop
video/x-ms-asf=smplayer.desktop
video/x-ogm=smplayer.desktop
application/vnd.rn-realmedia=smplayer.desktop

# Fotografie — Eye of GNOME
image/jpeg=org.gnome.eog.desktop
image/png=org.gnome.eog.desktop
image/gif=org.gnome.eog.desktop
image/bmp=org.gnome.eog.desktop
image/tiff=org.gnome.eog.desktop
image/webp=org.gnome.eog.desktop
image/avif=org.gnome.eog.desktop
image/x-icon=org.gnome.eog.desktop
image/svg+xml=org.gnome.eog.desktop
image/heic=org.gnome.eog.desktop
image/x-portable-pixmap=org.gnome.eog.desktop
image/x-tga=org.gnome.eog.desktop
MIMEAPPS
cp .work/config/includes.chroot_after_packages/etc/xdg/gnome-mimeapps.list \
   .work/config/includes.chroot_after_packages/etc/xdg/mimeapps.list

# ---------------------------------------------------------------------------
# GNOME INITIAL SETUP — MODALITÀ LIVE (v@VERSION@, rev. 5 — systemd user unit)
# ---------------------------------------------------------------------------
# Requisito 1: nella sessione LIVE, gnome-initial-setup deve avviarsi
# permettendo di scegliere SOLO lingua, tastiera e fuso orario.
#
# Fatti verificati nel sorgente di g-i-s 48 (quello di trixie):
#   • La pagina "timezone" è hardcoded new_user_only: con --existing-user
#     NON viene MAI mostrata. Quindi in live g-i-s va lanciato in modalità
#     new-user (default, senza flag).
#   • In new-user mode le pagine elencate nella chiave vendor.conf
#     [pages] existing_user_only= vengono saltate: è così che si saltano
#     account e password senza toccare il codice.
#   • La pagina "summary" NON va saltata: è l'unica a fornire il pulsante
#     finale (l'assistant nasconde i pulsanti di navigazione sull'ultima
#     pagina); "welcome" si nasconde da sola quando "language" è attiva.
#   • Il binario è /usr/libexec/gnome-initial-setup (NON è nel PATH).
#   • vendor.conf viene letto da /etc/gnome-initial-setup/vendor.conf.
#
# Meccanismo: uno script live-config (/usr/lib/live/config/2000-*) che
# GIRA SOLO al boot live (live-config non viene mai eseguito sul sistema
# installato) scrive nella overlay di sessione:
#   - vendor.conf "live" (salta tutto tranne language/keyboard/timezone
#     + summary finale)
#   - il launcher e l'autostart .desktop per la sessione GNOME live
#   - una regola polkit che consente all'utente live "user" di impostare
#     locale/tastiera/fuso senza richiesta di password
# Le modifiche avvengono nella overlay tmpfs: il sistema INSTALLATO (che
# copia la squashfs pristina) non le eredita, quindi il primo avvio
# installato conserva il flusso g-i-s completo (creazione account inclusa)
# esattamente come in 1.99.
# ---------------------------------------------------------------------------
mkdir -p .work/config/includes.chroot_after_packages/usr/lib/live/config/
cat <<'EOF' > .work/config/includes.chroot_after_packages/usr/lib/live/config/2000-ruscalinux-gis
#!/bin/sh
# RuscaLinux — configura gnome-initial-setup per la sessione live.
# Eseguito da live-config al boot (solo con boot=live), come root,
# nella overlay di sessione: nulla di tutto ciò finisce nel sistema
# installato.

# vendor.conf per la sessione live: in new-user mode le pagine in
# "existing_user_only" vengono saltate → niente account/password.
# Restano: language, keyboard, timezone e la summary finale
# ("welcome" si nasconde da sola perché language è attiva).
mkdir -p /etc/gnome-initial-setup
cat > /etc/gnome-initial-setup/vendor.conf <<'VENDORCONF'
[pages]
skip=network;privacy;software;parental_controls;parent_password
existing_user_only=account;password
VENDORCONF

# Launcher: avvia il wizard, attende il completamento e riavvia la
# sessione. La lingua/tastiera/fuso vengono già salvate da g-i-s alla
# selezione (localed + AccountsService, permesse dalla regola polkit qui
# sotto); il riavvio della sessione serve perché una sessione GNOME in
# corso non può cambiare lingua al volo: al rientro (autologin) GNOME
# riparte nella lingua scelta.
mkdir -p /usr/local/bin
cat > /usr/local/bin/ruscalinux-live-initial-setup <<'LAUNCHER'
#!/bin/sh
# Solo utenti reali: l'autostart con OnlyShowIn=GNOME viene processato
# anche dalla sessione greeter di GDM (XDG_CURRENT_DESKTOP contiene
# "GNOME"), che gira come Debian-gdm. Senza queste guardie il greeter
# "brucia" il wizard prima della sessione utente.
[ "$(id -u)" -ge 1000 ] || exit 0
case "$XDG_CURRENT_DESKTOP" in *Greeter*) exit 0 ;; esac

# Log diagnostico best-effort in ~/.cache
mkdir -p "$HOME/.cache" 2>/dev/null || true
if touch "$HOME/.cache/ruscalinux-gis.log" 2>/dev/null; then
    exec >>"$HOME/.cache/ruscalinux-gis.log" 2>&1
fi

# Lo stamp "done" può essere stato pre-creato dal first-login di serie
# del pacchetto (neutralizzato qui sopra dal componente live-config, ma
# restiamo difensivi): NON va usato come guardia d'ingresso. Lo togliamo,
# così la sua comparsa segnala solo il completamento del NOSTRO wizard.
# La protezione contro il ri-avvio dopo il restart della sessione è la
# guardia STARTED qui sotto, che vive in ~/.cache e sopravvive al re-login.
DONE="$HOME/.config/gnome-initial-setup-done"
rm -f "$DONE" 2>/dev/null || true

# Guardia per-UTENTE e per-boot: la home in live è una overlay tmpfs
# (si azzera a ogni boot) ma sopravvive al riavvio della sessione.
STARTED="$HOME/.cache/ruscalinux-gis.started"
if [ -e "$STARTED" ]; then
    echo "[gis] wizard già avviato in questo boot, esco"
    exit 0
fi
touch "$STARTED" 2>/dev/null || true

echo "[gis] avvio gnome-initial-setup"
/usr/libexec/gnome-initial-setup &
GIS=$!
START_T=$(date +%s)

# g-i-s scrive lo stamp al click sul pulsante finale; se invece il
# processo muore prima (finestra chiusa o crash), usciamo di conseguenza.
while kill -0 "$GIS" 2>/dev/null && [ ! -e "$DONE" ]; do
    sleep 1
done

if [ ! -e "$DONE" ]; then
    # Terminato senza completare. Se è morto subito (crash, sessione
    # abortita) rimuoviamo la guardia: un tentativo successivo riproverà.
    if [ $(( $(date +%s) - START_T )) -lt 10 ]; then
        rm -f "$STARTED"
        echo "[gis] g-i-s terminato subito senza completare: guardia rimossa"
    else
        echo "[gis] wizard chiuso dall'utente senza completare"
    fi
    exit 0
fi

# In live la finestra si nasconde ma il processo resta vivo (manca la
# connessione GDM del flusso new-user): due secondi di grazia per le
# scritture D-Bus asincrone, poi lo chiudiamo noi.
echo "[gis] wizard completato"
sleep 2
kill "$GIS" 2>/dev/null || true

# --- Determinazione della lingua scelta ---
# g-i-s, alla selezione, chiama localed SetLocale(...,persist=TRUE): il
# daemon scrive /etc/locale.conf in modo sincrono. Questa è la fonte più
# affidabile. AccountsService (Language=) è invece aggiornato in modo
# asincrono e può essere ancora indietro qui: le versioni precedenti
# leggevano quello e trovavano il default "en_US". Diamo quindi priorità a
# /etc/locale.conf, con un'attesa attiva finché non riflette una scelta
# reale (fino a ~15s), poi fallback su AccountsService.
NEWLANG=""
i=0
while [ $i -lt 15 ]; do
    L=$(grep -h '^LANG=' /etc/locale.conf 2>/dev/null | head -1 | cut -d= -f2 | tr -d '"')
    AS=$(grep -h '^Language=' "/var/lib/AccountsService/users/$(id -un)" 2>/dev/null | head -1 | cut -d= -f2)
    # Preferisci la fonte che indica una lingua diversa dal default di boot.
    for CAND in "$AS" "$L"; do
        if [ -n "$CAND" ] && [ "${CAND%%.*}" != "en_US" ]; then
            NEWLANG="$CAND"; break
        fi
    done
    [ -n "$NEWLANG" ] && break
    # Se l'utente ha scelto proprio l'inglese, dopo qualche giro accettalo.
    [ $i -ge 3 ] && [ -n "$L" ] && NEWLANG="$L" && break
    i=$((i+1)); sleep 1
done
[ -n "$NEWLANG" ] || NEWLANG=$(grep -h '^LANG=' /etc/default/locale 2>/dev/null | head -1 | cut -d= -f2 | tr -d '"')
echo "[gis] lingua scelta rilevata: ${NEWLANG:-<nessuna>}"

# --- Persistenza per l'autologin della sessione riavviata ---
# L'autologin GDM parte nella lingua dell'account utente (AccountsService),
# non da /etc/locale.conf. Un helper root (via pkexec, senza password
# grazie alla regola polkit) scrive locale.conf, default/locale e
# l'AccountsService dell'utente, così al riavvio la sessione riparte
# davvero nella lingua scelta.
if [ -n "$NEWLANG" ]; then
    pkexec /usr/local/sbin/ruscalinux-apply-lang "$NEWLANG" "$(id -un)" \
        && echo "[gis] lingua applicata a sistema e account" \
        || echo "[gis] ATTENZIONE: helper lingua fallito"
fi

# --- Cartelle utente nella lingua scelta ---
# Osservazione chiave: sul sistema INSTALLATO le cartelle nascono già
# tradotte, perché l'autostart nativo `xdg-user-dirs-update` (fase
# EarlyInitialization, a ogni login) le CREA nel locale corrente quando
# NON esistono ancora né le cartelle né user-dirs.dirs. In live invece le
# cartelle inglesi esistono già (create al primo login autologin, prima
# del wizard), quindi quel meccanismo trova tutto pronto e non traduce.
#
# Soluzione: replichiamo in live la condizione del "primo login pulito".
# Prima del riavvio della sessione azzeriamo lo stato delle user-dirs —
# rimuovendo user-dirs.dirs, user-dirs.locale e le SOLE cartelle standard
# VUOTE — così alla sessione riavviata (ormai in italiano) l'autostart
# nativo le ricrea automaticamente tradotte, senza rinomine manuali e
# senza alcun dialogo. Le cartelle non vuote (contenuto dell'utente) NON
# vengono toccate: rmdir fallisce e le lasciamo com'erano.
if [ -n "$NEWLANG" ]; then
    echo "[gis] azzero stato user-dirs per rigenerazione tradotta a $NEWLANG"
    rm -f "$HOME/.config/user-dirs.dirs" "$HOME/.config/user-dirs.locale"
    for D in Desktop Downloads Templates Public Documents Music Pictures Videos; do
        # rmdir rimuove solo se vuota: nessun dato dell'utente viene perso.
        rmdir "$HOME/$D" 2>/dev/null || true
    done
    echo "[gis] al prossimo avvio le cartelle verranno create in $NEWLANG"
fi

echo "[gis] riavvio la sessione"

# Riavvio della sessione: il restart di GDM ri-innesca l'autologin
# (regola polkit dedicata); il logout con TimedLogin è il ripiego.
systemctl restart display-manager.service 2>/dev/null || \
systemctl restart gdm3.service 2>/dev/null || \
gnome-session-quit --logout --no-prompt
LAUNCHER
chmod 755 /usr/local/bin/ruscalinux-live-initial-setup

# Neutralizza il "first login" di serie di gnome-initial-setup: al primo
# login scriverebbe subito lo stamp gnome-initial-setup-done (da GNOME 40
# in modalità existing-user scrive lo stamp ed esce), facendo credere al
# nostro launcher che il wizard sia già stato completato. Il pacchetto lo
# attiva in DUE modi — autostart XDG e unità utente systemd agganciata a
# gnome-session.target — e vanno disattivati entrambi. Scriviamo solo
# nella overlay live: il sistema installato non è toccato.
cat > /etc/xdg/autostart/gnome-initial-setup-first-login.desktop <<'HIDDEN'
[Desktop Entry]
Type=Application
Name=GNOME Initial Setup First Login (disabilitato nella live RuscaLinux)
Hidden=true
HIDDEN
mkdir -p /etc/systemd/user
ln -sf /dev/null /etc/systemd/user/gnome-initial-setup-first-login.service

# Sopprimi nella LIVE gli autostart di serie che disturbano il flusso:
#  • user-dirs-update-gtk: al re-login in nuova lingua apre il dialogo
#    "Aggiornare cartelle standard?". Lo sopprimiamo perché la migrazione
#    la fa già il nostro launcher, in automatico e senza chiedere nulla.
# Copriamo i nomi noti del file (variano un po' tra versioni) con Hidden.
for AUTO in user-dirs-update-gtk xdg-user-dirs-gtk; do
    cat > "/etc/xdg/autostart/${AUTO}.desktop" <<HIDDEN
[Desktop Entry]
Type=Application
Name=${AUTO} (disabilitato nella live RuscaLinux)
Hidden=true
HIDDEN
done

# NB: il TOUR di benvenuto è disattivato OVUNQUE (live e installato) dalla
# chiave org.gnome.shell welcome-dialog-last-shown-version in
# 99_ruscalinux-backgrounds-it.gschema.override. Qui non serve altro.


# Avvio del launcher: NON via autostart .desktop. Su GNOME/Wayland di
# trixie gli autostart .desktop "legacy" sono inaffidabili (GNOME sta
# migrando gli autostart a unità systemd user); un .desktop qui non
# partiva affatto, ed è la ragione per cui migrazione cartelle e
# soppressioni sembravano ignorate. Usiamo quindi un'unità systemd
# --user agganciata a gnome-session.target, il meccanismo che GNOME
# onora in modo affidabile nella sessione grafica.
mkdir -p /etc/systemd/user
cat > /etc/systemd/user/ruscalinux-live-initial-setup.service <<'UNIT'
[Unit]
Description=RuscaLinux Live Initial Setup (lingua/tastiera/fuso)
After=graphical-session.target
PartOf=graphical-session.target

[Service]
Type=oneshot
ExecStart=/usr/local/bin/ruscalinux-live-initial-setup
# L'ambiente D-Bus/Wayland della sessione è già importato da gnome-session
# nel gestore --user; non serve altro.

[Install]
WantedBy=gnome-session.target
UNIT
# Abilita l'unità per la sessione utente (equivale a systemctl --user enable
# ma scritto direttamente, dato che a build/boot non c'è un manager --user
# a cui parlare): il symlink in gnome-session.target.wants la fa partire.
mkdir -p /etc/systemd/user/gnome-session.target.wants
ln -sf /etc/systemd/user/ruscalinux-live-initial-setup.service \
    /etc/systemd/user/gnome-session.target.wants/ruscalinux-live-initial-setup.service

# Helper root per scrivere i file di sistema (locale + AccountsService):
# il launcher gira come utente non privilegiato e non può scriverli
# direttamente. pkexec lo esegue come root; la regola polkit qui sotto lo
# consente senza password all'utente live.
cat > /usr/local/sbin/ruscalinux-apply-lang <<'HELPER'
#!/bin/sh
# Uso: ruscalinux-apply-lang <LOCALE> <USER>
LOC="$1"; U="$2"
[ -n "$LOC" ] && [ -n "$U" ] || exit 1
printf 'LANG=%s\n' "$LOC" > /etc/locale.conf
printf 'LANG=%s\n' "$LOC" > /etc/default/locale
mkdir -p /var/lib/AccountsService/users
cat > "/var/lib/AccountsService/users/$U" <<ASF
[User]
Language=$LOC
FormatsLocale=$LOC
XSession=gnome
SystemAccount=false
ASF
exit 0
HELPER
chmod 755 /usr/local/sbin/ruscalinux-apply-lang

# Polkit: l'utente live "user" può impostare locale, tastiera e fuso
# orario di sistema senza prompt di password (solo sessione locale attiva).
mkdir -p /etc/polkit-1/rules.d
cat > /etc/polkit-1/rules.d/60-ruscalinux-live.rules <<'POLKIT'
polkit.addRule(function(action, subject) {
    if (subject.user == "user" && subject.local && subject.active &&
        (action.id == "org.freedesktop.locale1.set-locale" ||
         action.id == "org.freedesktop.locale1.set-keyboard" ||
         action.id == "org.freedesktop.timedate1.set-timezone" ||
         action.id.indexOf("org.freedesktop.accounts.") == 0)) {
        return polkit.Result.YES;
    }
});

// Riavvio del display manager al termine del wizard live
// (limitato alle sole unità di GDM).
polkit.addRule(function(action, subject) {
    if (subject.user == "user" && subject.local && subject.active &&
        action.id == "org.freedesktop.systemd1.manage-units" &&
        (action.lookup("unit") == "display-manager.service" ||
         action.lookup("unit") == "gdm.service" ||
         action.lookup("unit") == "gdm3.service")) {
        return polkit.Result.YES;
    }
});

// Esecuzione senza password dell'helper che applica lingua/locale.
polkit.addRule(function(action, subject) {
    if (subject.user == "user" && subject.local && subject.active &&
        action.id == "org.freedesktop.policykit.exec" &&
        action.lookup("program") == "/usr/local/sbin/ruscalinux-apply-lang") {
        return polkit.Result.YES;
    }
});
POLKIT

# TimedLogin come ripiego: se il percorso di logout viene usato al posto
# del restart di GDM, il greeter rientra da solo dopo 5 secondi.
GDMCONF=/etc/gdm3/daemon.conf
mkdir -p /etc/gdm3
[ -f "$GDMCONF" ] || printf '[daemon]\n' > "$GDMCONF"
if ! grep -q '^TimedLoginEnable' "$GDMCONF"; then
    if grep -q '^\[daemon\]' "$GDMCONF"; then
        sed -i '/^\[daemon\]/a TimedLoginEnable=true\nTimedLogin=user\nTimedLoginDelay=5' "$GDMCONF"
    else
        printf '\n[daemon]\nTimedLoginEnable=true\nTimedLogin=user\nTimedLoginDelay=5\n' >> "$GDMCONF"
    fi
fi

exit 0
EOF
chmod +x .work/config/includes.chroot_after_packages/usr/lib/live/config/2000-ruscalinux-gis

# ---------------------------------------------------------------------------
# I FILE DI DEBIAN SOSTITUITI DA RUSCALINUX, REGISTRATI PRESSO DPKG
# ---------------------------------------------------------------------------
# Alcuni file che gli includes mettono nel sistema (os-release, l'emblema del
# distributore...) prendono il posto di file di pacchetti Debian. dpkg non lo
# sa: reinstallando o aggiornando il pacchetto rimetterebbe il file Debian, e
# dpkg --verify li segnala come modificati. Questo hook li registra con
# dpkg-divert --no-rename: il file resta quello di RuscaLinux e, se il
# pacchetto arrivasse di nuovo, il suo file andrebbe in
# /usr/lib/ruscalinux/debian-originali/ invece di sovrascriverlo.
#
# L'elenco dei file degli includes lo scrive build.sh dopo tutti i passi
# (anche 40-nvidia.sh aggiunge includes) in
# /usr/share/ruscalinux/includes.list. Si registrano solo i file che
# appartengono davvero a un pacchetto. Restano fuori i conffile (/etc/issue,
# /etc/issue.net...): dpkg protegge gia' le loro modifiche, e una diversione
# su un conffile confonderebbe i suoi controlli.
#
# Gira prima di 9991 e 9993, che sostituiscono i loghi con dpkg-divert per
# conto proprio.
# ---------------------------------------------------------------------------
cat <<'EOF' > .work/config/hooks/normal/9989-ruscalinux-diversions.hook.chroot
#!/bin/sh
set -e
ELENCO=/usr/share/ruscalinux/includes.list
ORIGINALI=/usr/lib/ruscalinux/debian-originali

if [ ! -f "$ELENCO" ]; then
    echo "ATTENZIONE: manca $ELENCO, nessuna diversione registrata" >&2
    exit 0
fi

# /etc/os-release resta il collegamento di base-files verso
# ../usr/lib/os-release, che e' il file di RuscaLinux.
if [ ! -L /etc/os-release ]; then
    ln -sf ../usr/lib/os-release /etc/os-release
    echo "/etc/os-release: di nuovo collegamento a /usr/lib/os-release"
fi

while read -r F; do
    [ -f "$F" ] && [ ! -L "$F" ] || continue
    [ -z "$(dpkg-divert --listpackage "$F")" ] || continue    # gia' registrato
    PKG=$(dpkg-query -S "$F" 2> /dev/null | sed -n '1s/: .*//p') || true
    [ -n "$PKG" ] || continue                                    # e' solo nostro
    case "$PKG" in *,*) PKG=${PKG%%,*} ;; esac
    if dpkg-query -W -f '${Conffiles}\n' "$PKG" 2> /dev/null | awk '{ print $1 }' | grep -qxF "$F"; then
        echo "conffile di $PKG, lasciato a dpkg: $F"
        continue
    fi
    mkdir -p "$(dirname "$ORIGINALI$F")"
    dpkg-divert --local --no-rename --divert "$ORIGINALI$F" --add "$F" > /dev/null
    echo "file di $PKG sostituito da RuscaLinux: $F"
done < "$ELENCO"
exit 0
EOF
chmod +x .work/config/hooks/normal/9989-ruscalinux-diversions.hook.chroot

# ---------------------------------------------------------------------------
# RIMOZIONE AVATAR DEBIAN DA /etc/skel (v@VERSION@)
# ---------------------------------------------------------------------------
# Requisito 3: niente icone Debian nella home. In trixie il pacchetto
# desktop-base installa /etc/skel/.face e /etc/skel/.face.icon (lo swirl
# Debian): vengono copiati nella home di OGNI utente creato (utente live,
# utente oem del d-i, utente creato da g-i-s al primo avvio). Togliendoli
# dallo skel a build-time spariscono ovunque. Si tolgono con dpkg-divert
# --rename (vanno in /usr/lib/ruscalinux/debian-originali/), cosi' una
# reinstallazione di desktop-base non li rimette nello skel.
# ---------------------------------------------------------------------------
cat <<'EOF' > .work/config/hooks/normal/9992-remove-skel-face.hook.chroot
#!/bin/sh
set -e
for F in /etc/skel/.face /etc/skel/.face.icon; do
    [ -e "$F" ] || [ -L "$F" ] || continue
    if [ -z "$(dpkg-divert --listpackage "$F")" ] && dpkg-query -S "$F" > /dev/null 2>&1; then
        mkdir -p "/usr/lib/ruscalinux/debian-originali/etc/skel"
        dpkg-divert --local --rename --divert "/usr/lib/ruscalinux/debian-originali$F" --add "$F" > /dev/null
        echo "avatar Debian tolto dallo skel: $F"
    else
        rm -f "$F"
    fi
done
EOF
chmod +x .work/config/hooks/normal/9992-remove-skel-face.hook.chroot

# ---------------------------------------------------------------------------
# APPLICAZIONI NASCOSTE NEL MENU DI GNOME (v@VERSION@)
# ---------------------------------------------------------------------------
# Restano installate ma non compaiono nella griglia delle applicazioni ne'
# nella ricerca:
#  • per pacchetto: Totem (Video) ed Eye of GNOME (eog), che resta il
#    visualizzatore predefinito delle immagini (vedi APPLICAZIONI
#    PREDEFINITE) e si apre con un doppio clic; la Guida di riferimento
#    Debian, se la rimozione in 9993-remove-debian-artwork non e' riuscita.
#    I file si trovano con dpkg -L, non per nome: cosi' funziona anche se
#    Debian li rinomina, e comprende tutte le lingue della guida.
#  • per file: la GUI "display" di ImageMagick (una finestra Motif degli anni
#    Novanta; i nomi variano: display-im6.q16, display-im7...), TeXdoctk se
#    c'e' texlive, Snapshot, Estensioni, mpv, "Mozc Setup" (chi scrive in
#    giapponese lo apre dalle preferenze della sorgente di input; il
#    pacchetto ha gia' ibus-setup-mozc-jp.desktop, nascosto, per quell'uso)
#    e "Aiuto" (yelp): Yelp resta installato, F1 e le voci "Aiuto" dei
#    programmi continuano ad aprire i manuali.
#
# Non si modificano i file .desktop in /usr/share/applications: il prossimo
# aggiornamento del pacchetto li riscriverebbe. Se ne mette invece una copia
# con NoDisplay=true in /usr/local/share/applications, che nella precedenza
# XDG viene prima di /usr/share e sopravvive agli aggiornamenti. La copia
# conserva Exec e MimeType: "Apri con" continua a funzionare (NoDisplay
# nasconde l'icona, non l'associazione ai tipi di file).
# ---------------------------------------------------------------------------
cat <<'EOF' > .work/config/hooks/normal/9994-hide-apps.hook.chroot
#!/bin/sh
set -e
DEST=/usr/local/share/applications
mkdir -p "$DEST"

nascondi() {                      # nascondi FILE.desktop [PACCHETTO]
    [ -f "$1" ] || return 0
    # Copia con NoDisplay=true subito dopo la prima intestazione
    # [Desktop Entry] (non dentro una [Desktop Action ...] in fondo al file),
    # senza un eventuale NoDisplay gia' presente.
    grep -v '^NoDisplay=' "$1" | sed '0,/^\[Desktop Entry\]/s//[Desktop Entry]\nNoDisplay=true/' \
        > "$DEST/$(basename "$1")"
    echo "nascosto nel menu: $(basename "$1")${2:+ ($2)}"
}

for PKG in totem eog $(dpkg-query -W -f '${Package}\n' 'debian-reference*' 2>/dev/null); do
    dpkg -L "$PKG" 2>/dev/null | grep '^/usr/share/applications/.*\.desktop$' |
    while read -r F; do
        nascondi "$F" "$PKG"
    done
done

for F in /usr/share/applications/display-im*.desktop \
         /usr/share/applications/texdoctk.desktop \
         /usr/share/applications/org.gnome.Snapshot.desktop \
         /usr/share/applications/org.gnome.Extensions.desktop \
         /usr/share/applications/yelp.desktop \
         /usr/share/applications/mpv.desktop \
         /usr/share/applications/setup-mozc.desktop; do
    nascondi "$F"
done

command -v update-desktop-database >/dev/null && update-desktop-database -q "$DEST" || true
exit 0
EOF
chmod +x .work/config/hooks/normal/9994-hide-apps.hook.chroot

# ---------------------------------------------------------------------------
# PULIZIA DI CIO' CHE E' DI DEBIAN E NON SERVE (v@VERSION@)
# ---------------------------------------------------------------------------
# RuscaLinux ha i propri sfondi, il proprio tema Plymouth, il proprio tema
# GRUB e il proprio logo: la grafica di Debian resterebbe sul disco senza
# che niente la usi. Questo hook la toglie, in quattro passi.
#
#  1. Pacchetti: la guida di riferimento Debian e gli strumenti che parlano
#     con i servizi di Debian (segnalazione di bug, statistiche d'uso), che
#     su RuscaLinux non servono. Ogni rimozione e' prima simulata: se apt
#     volesse togliere anche un pacchetto fuori da questo elenco, non si
#     rimuove niente e la build lo scrive.
#  2. Grafica di desktop-base: i temi (Ceratopsian, Emerald, Homeworld...),
#     con i loro sfondi, schermate di blocco, temi Plymouth e sfondi GRUB,
#     e le voci che li mettono in Impostazioni -> Sfondo. I file si trovano
#     con dpkg -L, non per nome: i temi cambiano a ogni versione di Debian.
#     Il pacchetto desktop-base resta installato, perche' altri pacchetti lo
#     richiedono, e resta la cartella dei loghi (debian-logos), che GDM
#     legge per la schermata di accesso: 9991-replace-debian-logos ci ha
#     gia' messo il logo RuscaLinux.
#  3. Alternative: desktop-base registra i propri file con
#     update-alternatives (sfondo, tema, sfondo GRUB...). Le scelte rimaste
#     senza file si tolgono, cosi' non restano collegamenti verso il nulla.
#  4. Logo: lo swirl che resta nelle icone (emblem-debian, debian-swirl,
#     distributor-logo) e in Plymouth (debian-logo.png) si sostituisce con
#     il logo RuscaLinux. Si sostituisce e non si cancella: lo script di
#     Plymouth per l'initramfs e le alternative delle icone cercano quei file.
#     La sostituzione passa da dpkg-divert (funzione sostituisci, come in
#     9991): i nomi restano quelli di Debian, ma dpkg sa che il contenuto e'
#     di RuscaLinux, e una reinstallazione dei pacchetti non lo rimette.
#
# I temi Plymouth di Debian si tolgono solo se quello attivo e' "ruscalinux"
# (lo imposta 9990-set-plymouth-theme): se non lo fosse, si lasciano e la
# build lo scrive, perche' il sistema deve comunque avviarsi.
#
# Gira dopo 9990 e 9991 e prima di 9994-hide-apps.
# ---------------------------------------------------------------------------
cat <<'EOF' > .work/config/hooks/normal/9993-remove-debian-artwork.hook.chroot
#!/bin/sh
set -e

LOGO_SVG=/usr/share/icons/hicolor/scalable/apps/ruscalinux-logo.svg
LOGO_PNG=/usr/share/icons/hicolor/256x256/apps/ruscalinux-logo.png

# Mette un file RuscaLinux al posto di uno di un pacchetto Debian con
# dpkg-divert: l'originale va in /usr/lib/ruscalinux/debian-originali/
# (fuori dalle cartelle delle icone e dei temi, dove nessuno lo cerca) e
# dpkg sa che il file e' stato sostituito, quindi un'eventuale
# reinstallazione del pacchetto non rimette il logo Debian. Un file che non
# appartiene a nessun pacchetto si sovrascrive e basta.
#   sostituisci FILE_NUOVO DESTINAZIONE      (FILE_NUOVO resta dov'e')
sostituisci() {
    NUOVO=$1 F=$2
    if [ -z "$(dpkg-divert --listpackage "$F")" ] && dpkg-query -S "$F" > /dev/null 2>&1; then
        ORIGINALE="/usr/lib/ruscalinux/debian-originali$F"
        mkdir -p "$(dirname "$ORIGINALE")"
        dpkg-divert --local --rename --divert "$ORIGINALE" --add "$F" > /dev/null
    fi
    cp "$NUOVO" "$F"
}

# --- 1. Pacchetti -----------------------------------------------------------
# L'ordine conta: prima chi dipende, poi le sue librerie.
ELENCO="$(dpkg-query -W -f '${Package}\n' 'debian-reference*' 2>/dev/null || true)
debian-faq
doc-debian
reportbug
python3-reportbug
installation-report
popularity-contest"

for PKG in $ELENCO; do
    dpkg-query -W -f '${db:Status-Status}' "$PKG" 2>/dev/null | grep -qx installed || continue
    VIA=$(apt-get -s -o APT::Get::AutomaticRemove=false purge "$PKG" 2>/dev/null \
            | awk '$1 == "Purg" || $1 == "Remv" { print $2 }')
    if [ -z "$VIA" ]; then
        echo "ATTENZIONE: $PKG: simulazione della rimozione fallita, resta installato" >&2
        continue
    fi
    ALTRI=""
    for P in $VIA; do
        echo "$ELENCO" | grep -qxF "$P" || ALTRI="$ALTRI $P"
    done
    if [ -n "$ALTRI" ]; then
        echo "ATTENZIONE: $PKG resta installato: toglierlo rimuoverebbe anche$ALTRI" >&2
        continue
    fi
    if apt-get purge --assume-yes -o APT::Get::AutomaticRemove=false "$PKG" > /dev/null; then
        echo "pacchetto rimosso: $PKG"
    else
        echo "ATTENZIONE: rimozione di $PKG fallita" >&2
    fi
done

# --- 2. Grafica di desktop-base --------------------------------------------
FILE_DB=$(dpkg -L desktop-base 2>/dev/null || true)
if [ -z "$FILE_DB" ]; then
    echo "desktop-base non installato: nessuna grafica Debian da togliere"
fi

# Temi Plymouth: solo se quello attivo e' il nostro.
ATTIVO=$(plymouth-set-default-theme 2>/dev/null || true)
if [ "$ATTIVO" = "ruscalinux" ]; then
    echo "$FILE_DB" | grep -E '^/usr/share/plymouth/themes/[^/]+$' | while read -r T; do
        [ -e "$T" ] || [ -L "$T" ] || continue
        # Mai il nostro tema ne' i due di ripiego di Plymouth.
        case "$(basename "$T")" in ruscalinux|details|text) continue ;; esac
        rm -rf "$T"
        echo "tema Plymouth Debian rimosso: $(basename "$T")"
    done
else
    echo "ATTENZIONE: il tema Plymouth attivo e' '${ATTIVO:-nessuno}', non 'ruscalinux':" \
         "i temi Plymouth di Debian restano" >&2
fi

# Voci di Impostazioni -> Sfondo e sfondi per KDE.
echo "$FILE_DB" | grep -E '^/usr/share/(gnome-background-properties|wallpapers)/[^/]+$' | while read -r F; do
    [ -e "$F" ] || [ -L "$F" ] || continue
    rm -rf "$F"
    echo "sfondo Debian tolto dal selettore: $(basename "$F")"
done

# Le cartelle dei temi: sfondi, blocco schermo, accesso, GRUB, Plymouth.
# Se i temi Plymouth sono rimasti (vedi sopra), resta la loro cartella.
echo "$FILE_DB" | grep -E '^/usr/share/desktop-base/[^/]+-theme$' | while read -r D; do
    [ -e "$D" ] || [ -L "$D" ] || continue
    if [ "$ATTIVO" = "ruscalinux" ] || [ -L "$D" ]; then
        rm -rf "$D"
    else
        find "$D" -mindepth 1 -maxdepth 1 ! -name plymouth -exec rm -rf {} +
    fi
    echo "tema Debian rimosso: $(basename "$D")"
done

# --- 3. Alternative rimaste senza file --------------------------------------
# update-alternatives scarta da solo le scelte il cui file non c'e' piu':
# se al gruppo ne restano altre si lascia scegliere a lui, altrimenti il
# gruppo si toglie.
update-alternatives --get-selections 2>/dev/null | while read -r NOME STATO SCELTA; do
    case "$SCELTA" in
        /usr/share/desktop-base/*|/usr/share/plymouth/themes/*) ;;
        *) continue ;;
    esac
    [ -e "$SCELTA" ] && continue
    if update-alternatives --query "$NOME" 2>/dev/null | grep -q '^Alternative: '; then
        update-alternatives --quiet --auto "$NOME" 2>/dev/null || true
        echo "alternativa aggiornata: $NOME"
    else
        update-alternatives --quiet --remove-all "$NOME" 2>/dev/null || true
        echo "alternativa tolta: $NOME"
    fi
done
# Collegamenti del pacchetto che ora non portano piu' a niente.
for DIR in /usr/share/images/desktop-base /usr/share/desktop-base; do
    [ -d "$DIR" ] || continue
    find "$DIR" -maxdepth 1 -xtype l -print -delete | sed 's/^/collegamento rimosso: /'
done

# --- 4. Lo swirl che resta ---------------------------------------------------
if [ -f "$LOGO_SVG" ] && [ -f "$LOGO_PNG" ]; then
    for DIR in /usr/share/icons /usr/share/pixmaps /usr/share/plymouth; do
        [ -d "$DIR" ] || continue
        find "$DIR" -type f \( -name 'emblem-debian*' -o -name 'debian-swirl*' \
                -o -name 'debian-logo*' -o -name 'distributor-logo*' \) | while read -r F; do
            case "$F" in
                *.svg)
                    sostituisci "$LOGO_SVG" "$F" ;;
                *.png)
                    # Nelle icone la misura sta nel percorso (.../64x64/...).
                    LATO=$(echo "$F" | sed -n 's|.*/\([0-9][0-9]*\)x[0-9][0-9]*/.*|\1|p')
                    RIDOTTO=$(mktemp --suffix=.png)
                    if [ -n "$LATO" ] && command -v convert > /dev/null 2>&1 \
                       && convert "$LOGO_PNG" -resize "${LATO}x${LATO}" "$RIDOTTO" 2>/dev/null; then
                        sostituisci "$RIDOTTO" "$F"
                    else
                        sostituisci "$LOGO_PNG" "$F"
                    fi
                    rm -f "$RIDOTTO" ;;
                *) continue ;;
            esac
            chmod 644 "$F"
            echo "logo sostituito: $F"
        done
    done
else
    echo "ATTENZIONE: logo RuscaLinux non trovato, lo swirl Debian resta" >&2
fi

exit 0
EOF
chmod +x .work/config/hooks/normal/9993-remove-debian-artwork.hook.chroot



# ---------------------------------------------------------------------------
# FIX B — dconf dedicato per GDM (sovrascrive desktop-base)
# La gschema override vale per utenti normali, ma GDM usa il proprio
# profilo dconf: serve un file in /etc/dconf/db/gdm.d/ compilato
# con `dconf update` per forzare il logo nella schermata di login
# ---------------------------------------------------------------------------
mkdir -p .work/config/includes.chroot_after_packages/etc/dconf/profile/
cat <<'EOF' > .work/config/includes.chroot_after_packages/etc/dconf/profile/gdm
user-db:user
system-db:gdm
file-db:/usr/share/gdm/greeter-dconf-defaults
EOF

# ---------------------------------------------------------------------------
# FIX C — Hook post-schema: aggiorna cache icone e compila dconf
# Deve girare DOPO 9999-compile-schemas, da cui il suffisso -zz
# - gtk-update-icon-cache: permette a gnome-initial-setup di trovare
#   l'icona "ruscalinux-logo" (letta tramite LOGO= in os-release)
# - dconf update: compila i file in /etc/dconf/db/gdm.d/ nel database
#   binario usato da GDM a runtime
# ---------------------------------------------------------------------------
cat <<'EOF' > .work/config/hooks/normal/9999-zz-branding-finalize.hook.chroot
#!/bin/sh
set -e

# Forza i permessi in modo che l'utente limitato "gdm" possa leggere il logo
chmod 644 /usr/share/icons/hicolor/scalable/apps/ruscalinux-logo.svg || true
chmod 644 /usr/share/icons/hicolor/256x256/apps/ruscalinux-logo.png || true

# Rigenera le cache delle icone dopo tutte le sostituzioni (9991, 9993):
# hicolor (logo RuscaLinux) e vendor (emblema del distributore).
gtk-update-icon-cache -f -t /usr/share/icons/hicolor 2>/dev/null || true
gtk-update-icon-cache -f -t /usr/share/icons/vendor 2>/dev/null || true

# Compila il database dconf per GDM (fix logo schermata di login)
dconf update 2>/dev/null || true
EOF
chmod +x .work/config/hooks/normal/9999-zz-branding-finalize.hook.chroot

# ---------------------------------------------------------------------------
# FIX 1 — GRUB BACKGROUND TRAMITE DROP-IN (evita il conflitto conffile)
# ---------------------------------------------------------------------------
# Tema RuscaLinux (copiato all'inizio di questo passo in /boot/grub/themes):
# Debian carica da solo i font .pf2 della cartella del tema. Il fondo neutro
# console.png serve all'editor e alla riga di comando di GRUB.
mkdir -p .work/config/includes.chroot_after_packages/etc/default/grub.d/
cat > .work/config/includes.chroot_after_packages/etc/default/grub.d/99-ruscalinux.cfg <<'GRUBCFG'
GRUB_THEME=/boot/grub/themes/ruscalinux/theme.txt
GRUB_BACKGROUND=/boot/grub/themes/ruscalinux/console.png
GRUB_GFXMODE=1920x1080,1280x720,auto
# CRITICO: senza "splash" nel cmdline del kernel, Plymouth non mostra mai il
# tema grafico anche se l'initramfs lo contiene. Vale per il sistema
# installato (la live ha la sua riga di avvio in 10-config.sh).
GRUB_CMDLINE_LINUX_DEFAULT="quiet splash"
GRUBCFG

# ---------------------------------------------------------------------------
# FIX 3 — LOCALE, KEYBOARD AND TIMEZONE: English only
#           The system is in English (en_US.UTF-8, US keyboard, UTC timezone).
#           Both in the live environment and the installed system.
# ---------------------------------------------------------------------------
cat <<'EOF' > .work/config/hooks/normal/0010-locale-multi.hook.chroot
#!/bin/sh
set -e

# 1) Enable all supported locales in locale.gen (49, one per line)
LOCALES="
en_US.UTF-8 UTF-8
es_ES.UTF-8 UTF-8
fr_FR.UTF-8 UTF-8
de_DE.UTF-8 UTF-8
pt_BR.UTF-8 UTF-8
ru_RU.UTF-8 UTF-8
ar_SA.UTF-8 UTF-8
zh_CN.UTF-8 UTF-8
hi_IN.UTF-8 UTF-8
bn_BD.UTF-8 UTF-8
id_ID.UTF-8 UTF-8
ur_PK.UTF-8 UTF-8
it_IT.UTF-8 UTF-8
ja_JP.UTF-8 UTF-8
pl_PL.UTF-8 UTF-8
nl_NL.UTF-8 UTF-8
cs_CZ.UTF-8 UTF-8
sk_SK.UTF-8 UTF-8
ro_RO.UTF-8 UTF-8
hu_HU.UTF-8 UTF-8
sv_SE.UTF-8 UTF-8
nb_NO.UTF-8 UTF-8
da_DK.UTF-8 UTF-8
fi_FI.UTF-8 UTF-8
el_GR.UTF-8 UTF-8
bg_BG.UTF-8 UTF-8
uk_UA.UTF-8 UTF-8
hr_HR.UTF-8 UTF-8
sr_RS.UTF-8 UTF-8
tr_TR.UTF-8 UTF-8
ca_ES.UTF-8 UTF-8
lt_LT.UTF-8 UTF-8
lv_LV.UTF-8 UTF-8
et_EE.UTF-8 UTF-8
sl_SI.UTF-8 UTF-8
pt_PT.UTF-8 UTF-8
gl_ES.UTF-8 UTF-8
eu_ES.UTF-8 UTF-8
ko_KR.UTF-8 UTF-8
zh_TW.UTF-8 UTF-8
vi_VN.UTF-8 UTF-8
th_TH.UTF-8 UTF-8
fa_IR.UTF-8 UTF-8
ta_IN.UTF-8 UTF-8
te_IN.UTF-8 UTF-8
mr_IN.UTF-8 UTF-8
pa_IN.UTF-8 UTF-8
ms_MY.UTF-8 UTF-8
sw_KE.UTF-8 UTF-8
"

# Comment out any currently active locales
sed -i 's/^\([^#].*\)/# \1/' /etc/locale.gen || true

# Uncomment or append each locale.
# NB (v@VERSION@): il vecchio ciclo `for X in $(echo ...)` iterava per PAROLE,
# non per righe: ogni "UTF-8" spaiato aggiungeva una riga spuria
# "UTF-8 UTF-8" a locale.gen, e locale-gen tentava di generare un locale
# inesistente chiamato "UTF-8" (errore "cannot open locale definition
# file 'UTF-8'" ripetuto ~49 volte). Con read -r si itera per riga.
echo "$LOCALES" | grep -v '^[[:space:]]*$' | while read -r LOCALE CHARSET; do
    [ -n "$LOCALE" ] || continue
    CHARSET="${CHARSET:-UTF-8}"
    if grep -q "^# *${LOCALE}[[:space:]]" /etc/locale.gen; then
        sed -i "s|^# *${LOCALE}[[:space:]].*|${LOCALE} ${CHARSET}|" /etc/locale.gen
    elif ! grep -q "^${LOCALE}[[:space:]]" /etc/locale.gen; then
        echo "${LOCALE} ${CHARSET}" >> /etc/locale.gen
    fi
done
locale-gen

# 2) Set en_US.UTF-8 as system default locale
cat > /etc/default/locale <<LOC
LANG=en_US.UTF-8
LOC
update-locale LANG=en_US.UTF-8 || true

# 3) US keyboard
cat > /etc/default/keyboard <<KBD
XKBMODEL="pc105"
XKBLAYOUT="us"
XKBVARIANT=""
XKBOPTIONS=""
BACKSPACE="guess"
KBD

# 4) UTC timezone
echo "UTC" > /etc/timezone
ln -sf /usr/share/zoneinfo/UTC /etc/localtime
EOF
chmod +x .work/config/hooks/normal/0010-locale-multi.hook.chroot

# ===========================================================================
# FIX 3-BIS — FORCE ENGLISH FOR GDM AND GNOME-INITIAL-SETUP
# ===========================================================================

# 1) /etc/locale.conf — read by systemd at boot, propagated to services
cat > .work/config/includes.chroot_after_packages/etc/locale.conf <<EOF
LANG=en_US.UTF-8
EOF

# 2) /etc/default/locale — read by Debian and pam_env: lo scrive l'hook
#    0010-locale-multi (con update-locale), che gira dopo gli includes.

# 3) /etc/environment — NON impostare LANG qui: pam_env lo propagherebbe a
#    TUTTE le sessioni PAM sovrascrivendo la lingua scelta dall'utente in
#    gnome-initial-setup. Il default di sistema è già in /etc/default/locale.

# 4) Drop-in gdm.service rimosso: forzare LANG nel processo GDM impedirebbe
#    a gnome-initial-setup di avviarsi nella lingua scelta dall'utente.
#    Il default di sistema (en_US.UTF-8 via /etc/default/locale) è sufficiente.

# 5) AccountsService pre-populated for Debian-gdm and gnome-initial-setup
mkdir -p .work/config/includes.chroot_after_packages/var/lib/AccountsService/users/

cat > .work/config/includes.chroot_after_packages/var/lib/AccountsService/users/Debian-gdm <<EOF
[User]
Language=en_US.UTF-8
FormatsLocale=en_US.UTF-8
XSession=gnome
SystemAccount=true
EOF

cat > .work/config/includes.chroot_after_packages/var/lib/AccountsService/users/gnome-initial-setup <<EOF
[User]
XSession=gnome
SystemAccount=true
EOF

# 6) (rimosso) l'hook 0011-force-english-locale ripeteva cio' che fa gia'
#    0010-locale-multi: en_US.UTF-8 e' sempre nell'elenco dei locali, e
#    update-locale e' gia' stato lanciato; localectl nel chroot non gira mai.

# 7) (rimosso) l'override org.gnome.system.locale region='en_US.UTF-8' è stato
# eliminato: in gnome-control-center la sezione "Regione e lingua" legge questo
# valore e, se forzato a sistema, può impedire all'utente di cambiare i formati
# data/ora/numero. Il file 98_ruscalinux-locale.gschema.override non viene più
# creato; la lingua di sistema rimane quella impostata nel Debian Installer
# (o en_US.UTF-8 di fallback), che l'utente può sovrascrivere liberamente.

# ---------------------------------------------------------------------------
# TEMA PLYMOUTH PERSONALIZZATO RUSCALINUX
# ---------------------------------------------------------------------------
PLYMOUTH_THEME_DIR=".work/config/includes.chroot_after_packages/usr/share/plymouth/themes/ruscalinux"
mkdir -p "$PLYMOUTH_THEME_DIR"

cp local/ruscalinux-logo.png "$PLYMOUTH_THEME_DIR/logo.png"

cat <<'EOF' > "$PLYMOUTH_THEME_DIR/ruscalinux.plymouth"
[Plymouth Theme]
Name=RuscaLinux 
Description=Schermata di avvio ufficiale di RuscaLinux 
ModuleName=script

[script]
ImageDir=/usr/share/plymouth/themes/ruscalinux
ScriptFile=/usr/share/plymouth/themes/ruscalinux/ruscalinux.script
EOF

cat <<'EOF' > "$PLYMOUTH_THEME_DIR/ruscalinux.script"
# ── Colori brand RuscaLinux ──────────────────────────────────────────────
BG_R = 0.05;   BG_G = 0.01;   BG_B = 0.03;   # ~#0D0208
BAR_R = 0.545; BAR_G = 0.082; BAR_B = 0.220;  # #8B1538

# ── Sfondo pieno ─────────────────────────────────────────────────────────
Window.SetBackgroundTopColor(BG_R, BG_G, BG_B);
Window.SetBackgroundBottomColor(BG_R, BG_G, BG_B);

# ── Logo ─────────────────────────────────────────────────────────────────
logo.image  = Image("logo.png");
logo.width  = logo.image.GetWidth();
logo.height = logo.image.GetHeight();
logo.x      = Window.GetWidth()  / 2 - logo.width  / 2;
logo.y      = Window.GetHeight() / 2 - logo.height / 2 - 40;

logo.sprite = Sprite();
logo.sprite.SetImage(logo.image);
logo.sprite.SetX(logo.x);
logo.sprite.SetY(logo.y);
logo.sprite.SetZ(10);

# ── Barra di avanzamento ──────────────────────────────────────────────────
BAR_FULL_W = Math.Int(Window.GetWidth() * 0.45);
BAR_H      = 4;
BAR_X      = Math.Int((Window.GetWidth() - BAR_FULL_W) / 2);
BAR_Y      = Window.GetHeight() - 55;

bar_bg.image = Image(BAR_FULL_W, BAR_H);
bar_bg.image.Fill(0.15, 0.05, 0.08, 0.5);
bar_bg.sprite = Sprite();
bar_bg.sprite.SetImage(bar_bg.image);
bar_bg.sprite.SetX(BAR_X);
bar_bg.sprite.SetY(BAR_Y);
bar_bg.sprite.SetZ(9);

bar.sprite = Sprite();
bar.sprite.SetX(BAR_X);
bar.sprite.SetY(BAR_Y);
bar.sprite.SetZ(10);

fun plymouth_boot_progress_callback(time, progress) {
    fill_w = Math.Int(BAR_FULL_W * progress);
    if (fill_w < 2) fill_w = 2;
    bar.image = Image(fill_w, BAR_H);
    bar.image.Fill(BAR_R, BAR_G, BAR_B, 1.0);
    bar.sprite.SetImage(bar.image);
}
Plymouth.SetBootProgressFunction(plymouth_boot_progress_callback);

fun plymouth_quit_callback() {
    logo.sprite.SetOpacity(0);
    bar.sprite.SetOpacity(0);
    bar_bg.sprite.SetOpacity(0);
}
Plymouth.SetQuitFunction(plymouth_quit_callback);

# ── Animazione pulsazione logo (luminosità) ───────────────────────────────
# refresh_callback è chiamata ~50 volte al secondo dal Plymouth.
# Usiamo un contatore che incrementa di 1 per frame; con 50fps e 200 frame
# totali il ciclo completo dura 4 secondi (salita 2s, discesa 2s).
# L'opacità oscilla tra 0.35 (scuro) e 1.0 (piena luce).
anim_frame     = 0;
anim_direction = 1;     # +1 = sale, -1 = scende
ANIM_STEPS     = 100;   # passi per metà ciclo (salita O discesa)
ANIM_LOW       = 0.35;
ANIM_HIGH      = 1.0;
ANIM_RANGE     = ANIM_HIGH - ANIM_LOW;   # 0.65

fun refresh_callback() {
    anim_frame = anim_frame + anim_direction;
    if (anim_frame >= ANIM_STEPS) {
        anim_frame     = ANIM_STEPS;
        anim_direction = -1;
    } else if (anim_frame <= 0) {
        anim_frame     = 0;
        anim_direction = 1;
    }
    # t in [0 .. 1]: quanto siamo avanzati nel semi-ciclo corrente
    t = anim_frame / ANIM_STEPS;
    # Curva smooth (ease-in/out): 3t² − 2t³  →  più naturale di una rampa lineare
    smooth = t * t * (3.0 - 2.0 * t);
    logo.sprite.SetOpacity(ANIM_LOW + smooth * ANIM_RANGE);
}
Plymouth.SetRefreshFunction(refresh_callback);
EOF

cat <<'EOF' > .work/config/hooks/normal/9990-set-plymouth-theme.hook.chroot
#!/bin/sh
set -e

if ! dpkg -l plymouth 2>/dev/null | grep -q '^ii'; then
    echo "AVVISO: plymouth non installato nel chroot, skip." >&2
    exit 0
fi

update-alternatives --install \
    /usr/share/plymouth/themes/default.plymouth \
    default.plymouth \
    /usr/share/plymouth/themes/ruscalinux/ruscalinux.plymouth \
    200 || true

plymouth-set-default-theme -R ruscalinux

exit 0
EOF
chmod +x .work/config/hooks/normal/9990-set-plymouth-theme.hook.chroot

echo "plymouth"        >> .work/config/package-lists/ruscalinux.list.chroot
echo "plymouth-themes" >> .work/config/package-lists/ruscalinux.list.chroot

# SOSTITUZIONE PROFONDA DEL LOGO DEBIAN E DEL PIEDONE GNOME CON QUELLO DI RUSCALINUX
mkdir -p .work/config/includes.chroot_after_packages/usr/share/icons/vendor/scalable/emblems/
# Stesso logo di ruscalinux-logo.svg, con il nome che Debian usa per
# l'emblema del distributore: sostituisce il logo Debian anche li'.
cp local/ruscalinux-logo.svg .work/config/includes.chroot_after_packages/usr/share/icons/vendor/scalable/emblems/emblem-vendor.svg

mkdir -p .work/config/hooks/normal/
cat <<'EOF' > .work/config/hooks/normal/9991-replace-debian-logos.hook.chroot
#!/bin/sh
set -e

# Mette un file RuscaLinux al posto di uno di un pacchetto Debian con
# dpkg-divert: l'originale va in /usr/lib/ruscalinux/debian-originali/
# (fuori dalle cartelle delle icone e dei temi, dove nessuno lo cerca) e
# dpkg sa che il file e' stato sostituito, quindi un'eventuale
# reinstallazione del pacchetto non rimette il logo Debian. Un file che non
# appartiene a nessun pacchetto si sovrascrive e basta.
#   sostituisci FILE_NUOVO DESTINAZIONE      (FILE_NUOVO resta dov'e')
sostituisci() {
    NUOVO=$1 F=$2
    if [ -z "$(dpkg-divert --listpackage "$F")" ] && dpkg-query -S "$F" > /dev/null 2>&1; then
        ORIGINALE="/usr/lib/ruscalinux/debian-originali$F"
        mkdir -p "$(dirname "$ORIGINALE")"
        dpkg-divert --local --rename --divert "$ORIGINALE" --add "$F" > /dev/null
    fi
    cp "$NUOVO" "$F"
}

# Le cache delle icone si rigenerano una volta sola, alla fine, in
# 9999-zz-branding-finalize.

# 1. Sostituisce brutalmente tutti i loghi, intercettando ogni SVG/PNG nelle cartelle login di Debian
if [ -d /usr/share/desktop-base ]; then
    find -L /usr/share/desktop-base -type f \( -name "*logo*.svg" -o -name "*logo*.png" -o -path "*/login/*.svg" -o -path "*/login/*.png" \) | while read -r f; do
        if echo "$f" | grep -q "\.svg$"; then
            sostituisci /usr/share/icons/hicolor/scalable/apps/ruscalinux-logo.svg "$f" 2>/dev/null || true
        elif echo "$f" | grep -q "\.png$"; then
            sostituisci /usr/share/plymouth/themes/ruscalinux/logo.png "$f" 2>/dev/null || true
        fi
    done
fi

# 2. Sostituisce il "piedone" di GNOME (start-here e gnome-logo) in tutti i temi di icone
if [ -d /usr/share/icons ]; then
    find -L /usr/share/icons -type f \( -name "start-here*.svg" -o -name "start-here*.png" -o -name "gnome-logo*.svg" -o -name "gnome-logo*.png" \) | while read -r f; do
        if echo "$f" | grep -q "\.svg$"; then
            sostituisci /usr/share/icons/hicolor/scalable/apps/ruscalinux-logo.svg "$f" 2>/dev/null || true
        elif echo "$f" | grep -q "\.png$"; then
            sostituisci /usr/share/plymouth/themes/ruscalinux/logo.png "$f" 2>/dev/null || true
        fi
    done
fi
EOF
chmod +x .work/config/hooks/normal/9991-replace-debian-logos.hook.chroot

# ---------------------------------------------------------------------------
# FIX 4 — BANNER GRAFICO INSTALLER GTK (vinaccia, "RuscaLinux @VERSION@")
# ---------------------------------------------------------------------------
# Il banner con la versione lo disegna build.sh a ogni build
# (branding/generators/ruscalinux-banner.py), in .gen/banner.png.
BANNER_SRC=".gen/banner.png"

if [ ! -f "$BANNER_SRC" ]; then
    echo "ERRORE: $BANNER_SRC non trovato: lo crea build.sh con"
    echo "        branding/generators/ruscalinux-banner.py"
    exit 1
fi

# Percorso primario trixie
mkdir -p .work/config/includes.installer/usr/share/desktop-base/trixie-theme/installer/
cp "$BANNER_SRC" .work/config/includes.installer/usr/share/desktop-base/trixie-theme/installer/banner.png

# Percorso fallback emerald
mkdir -p .work/config/includes.installer/usr/share/desktop-base/emerald-theme/installer/
cp "$BANNER_SRC" .work/config/includes.installer/usr/share/desktop-base/emerald-theme/installer/banner.png

# Percorso fallback homeworld
mkdir -p .work/config/includes.installer/usr/share/desktop-base/homeworld-theme/installer/
cp "$BANNER_SRC" .work/config/includes.installer/usr/share/desktop-base/homeworld-theme/installer/banner.png

# Copia anche sul CD in modo che l'early_command possa usarla
cp "$BANNER_SRC" .work/config/includes.binary/banner_ruscalinux.png

# Hook installer — sostituisce banner.png via symlink attivo a runtime
mkdir -p .work/config/hooks/installer/
cat <<'EOF' > .work/config/hooks/installer/9001-banner.hook.installer
#!/bin/sh
set -e
BANNER_SRC="/cdrom/banner_ruscalinux.png"
[ -f "$BANNER_SRC" ] || exit 0
# Sovrascrive tutti i banner.png nell'albero desktop-base, symlink inclusi
find -L /usr/share/desktop-base -name "banner.png" -path "*/installer/*" 2>/dev/null | \
    while read -r f; do
        cp "$BANNER_SRC" "$f" 2>/dev/null || true
    done
exit 0
EOF
chmod +x .work/config/hooks/installer/9001-banner.hook.installer

# ---------------------------------------------------------------------------
# FIX — TESTO DELL'INSTALLER GRAFICO PIU' GRANDE
# ---------------------------------------------------------------------------
# L'installer usa DejaVu Sans 9 pt con Xorg a 96 DPI: sugli schermi Full HD
# e piu' grandi il testo e' minuscolo. Lo script fa partire Xorg con una
# risoluzione proporzionale allo schermo (spiegazione nel file). Va
# nell'initrd dell'installer, come il banner, perche' deve agire prima
# della prima schermata: il preseed arriva troppo tardi.
#
# Percorso: usr/lib/..., NON lib/... L'installer di trixie e' merged-usr:
# /lib e' un collegamento a usr/lib. Una cartella lib/ in includes.installer
# prende il posto del collegamento e l'installer non parte piu' (kernel
# panic "Attempted to kill init! exitcode=0x00000200").
if [ ! -f local/installer/S61ruscalinux-dpi ]; then
    echo "ERRORE: manca local/installer/S61ruscalinux-dpi"
    exit 1
fi
mkdir -p .work/config/includes.installer/usr/lib/debian-installer.d/
install -m 755 local/installer/S61ruscalinux-dpi \
    .work/config/includes.installer/usr/lib/debian-installer.d/S61ruscalinux-dpi

# Controllo per tutto includes.installer: niente cartelle che nell'initrd
# merged-usr sono collegamenti.
for d in bin sbin lib lib32 lib64 libx32; do
    if [ -e ".work/config/includes.installer/$d" ]; then
        echo "ERRORE: .work/config/includes.installer/$d esiste."
        echo "        Nell'installer di trixie /$d e' un collegamento a /usr/$d:"
        echo "        metti i file in includes.installer/usr/$d/."
        exit 1
    fi
done

# ===========================================================================
# FIX — HOSTNAME DAL MODELLO DELLA MACCHINA (DMI / SMBIOS)
# ===========================================================================
# Il debian-installer usa "debian" come hostname predefinito perche' la rete
# e' disabilitata. Lo script legge il modello dal firmware (per esempio
# "Latitude 5420" -> latitude-5420, "ThinkPad X1 Carbon Gen 9" ->
# thinkpad-x1-carbon-gen-9) e lo da' a netcfg; se il firmware non dice
# niente di utile, il nome e' "ruscalinux". La domanda non compare: come il
# resto dell'installazione, il nome si sceglie da solo, e si cambia dopo in
# Impostazioni -> Sistema -> Informazioni.
#
# Perche' nelle prime versioni non funzionava: ruscalinux-postinstall.sh
# scriveva comunque "ruscalinux" in /etc/hostname a fine installazione,
# cancellando il nome scelto qui. Ora lo fa solo se netcfg ha lasciato un
# nome di ripiego (debian, localhost...).
#
# Gira nell'installer (busybox): niente classi di caratteri in tr, solo
# intervalli. DMI=cartella permette di provarlo su file finti.
# ---------------------------------------------------------------------------
cat > .work/config/includes.binary/set-hostname.sh <<'EOF'
#!/bin/sh
# Chiamato da preseed/early_command. Legge il modello da DMI/SMBIOS e
# imposta netcfg/get_hostname e netcfg/hostname con debconf-set-selections.
DMI=${DMI:-/sys/class/dmi/id}

leggi() {
    [ -r "$DMI/$1" ] || return 0
    head -n 1 "$DMI/$1" 2> /dev/null | tr -d '\r\n'
}

# Valori segnaposto dei produttori: non descrivono la macchina.
inutile() {
    case "$(printf '%s' "$1" | tr 'A-Z' 'a-z' | tr -s ' ')" in
        ""|" "|"to be filled by o.e.m."|"to be filled by oem"|"system product name"|\
        "system version"|"system manufacturer"|"default string"|"not specified"|\
        "not applicable"|"none"|"unknown"|"oem"|"o.e.m."|"invalid"|"type1productconfigid"|\
        "type2 - board product name1"|"0123456789"|"123456789"|"x.x"|"1.0"|"none none")
            return 0 ;;
    esac
    return 1
}

# Lenovo scrive il nome commerciale in product_version (in product_name c'e'
# il codice del modello, come 20XW00K1IX); gli altri in product_name.
case "$(leggi sys_vendor | tr 'a-z' 'A-Z')" in
    LENOVO*) CAMPI="product_version product_family product_name board_name" ;;
    *)       CAMPI="product_name product_family product_version board_name" ;;
esac

MODELLO=""
for campo in $CAMPI; do
    valore=$(leggi "$campo")
    inutile "$valore" && continue
    MODELLO=$valore
    break
done

# Nome valido (RFC 1123): minuscole, cifre e trattini, non all'inizio ne'
# alla fine; spazi e simboli diventano un trattino. Al massimo 30
# caratteri, tagliati fra due parole e non a meta' di una.
HOST=$(printf '%s' "$MODELLO" | tr 'A-Z' 'a-z' | tr -c 'a-z0-9' '-' | tr -s '-' \
       | sed -e 's/^-*//' -e 's/-*$//')
if [ "${#HOST}" -gt 30 ]; then
    HOST=$(printf '%s' "$HOST" | cut -c 1-31 | sed 's/-[^-]*$//' | cut -c 1-30)
fi
case "$HOST" in
    [0-9]*) HOST="pc-$HOST" ;;          # un nome fatto di sole cifre confonde
esac
[ -n "$HOST" ] || HOST=ruscalinux

echo "RuscaLinux: hostname $HOST (modello: ${MODELLO:-sconosciuto})"
# Anche per il post-install, nel caso netcfg (con la rete disattivata) non
# scrivesse /etc/hostname sul disco: il late_command lo copia in /target/tmp.
printf '%s\n' "$HOST" > /tmp/ruscalinux-hostname
debconf-set-selections <<SEL
d-i netcfg/get_hostname string $HOST
d-i netcfg/hostname string $HOST
d-i netcfg/get_domain string
SEL
EOF
chmod +x .work/config/includes.binary/set-hostname.sh

# ---------------------------------------------------------------------------
# INSTALLER GRAFICO DEBIAN — CONFIGURAZIONE OFFLINE SEMI-AUTOMATICA
# ---------------------------------------------------------------------------
mkdir -p .work/config/includes.binary/

cat <<'EOF' > .work/config/includes.binary/preseed.cfg
# =============================================================
#  ruscalinux — Preseed for semi-automatic graphical installation
#  Language: English | Mode: Offline
# =============================================================
# NOTE (v@VERSION@): language/keyboard/timezone are chosen by the user in the
#       LIVE GNOME session via gnome-initial-setup, NOT in the Debian
#       Installer. The installer therefore keeps the neutral defaults below
#       (US keyboard, UTC) and does not re-prompt for them. Only
#       partitioning asks the user: disk choice (if multiple disks) and a
#       single write confirmation.

# --- debconf priority HIGH (default GTK installer) ---
d-i debconf/priority select high

# --- Keyboard confirmation (redundant with keymap=us from cmdline) ---
d-i console-setup/ask_detect boolean false
d-i keyboard-configuration/layoutcode string us
d-i keyboard-configuration/variantcode string
d-i keyboard-configuration/xkb-keymap select us
d-i keymap select us

# --- Timezone UTC ---
d-i time/zone string UTC
d-i clock-setup/utc boolean true
d-i clock-setup/ntp boolean false

# --- Rete: disabilitata ---
# Hostname: "ruscalinux" e' solo il ripiego. preseed/early_command lancia
# set-hostname.sh, che lo sostituisce con il nome del modello della macchina.
d-i netcfg/enable boolean false
d-i netcfg/dhcp_options select Do not configure the network at this time
d-i netcfg/get_hostname string ruscalinux
d-i netcfg/hostname string ruscalinux
d-i netcfg/get_domain string

# --- Mirror APT ---
d-i mirror/country string manual
d-i mirror/http/hostname string 127.0.0.1
d-i mirror/http/directory string /
d-i mirror/http/proxy string
d-i apt-setup/use_mirror boolean false
d-i apt-setup/no_mirror boolean true
d-i apt-setup/cdrom/set-first boolean true
d-i apt-setup/services-select multiselect

# --- Partizionamento (v@VERSION@) ---
# Obiettivo: l'utente sceglie SOLO il disco, conferma una volta, e il resto
# (partizionamento e formattazione) avviene da solo con "usa l'intero disco".
#
# Due cose vanno capite del preseed, perche' non sono intuitive:
#
# 1. La schermata "Metodo di partizionamento" e' la domanda
#    partman-auto/init_automatically_partition, ed e' SEPARATA da
#    partman-auto/method. Impostare method="regular" dice a partman COME
#    partizionare, ma non risponde alla domanda: quella continua a comparire
#    con tutte e cinque le voci. Per farla sparire va preseedata lei.
#
# 2. Una chiave preseedata viene marcata "seen" e NON viene piu' chiesta:
#    debconf usa il valore. Quindi preseedare partman/confirm a "false" non
#    mostra il dialog di conferma — risponde "No, non scrivere". Per avere
#    la conferma dell'utente quelle chiavi vanno lasciate NON preseedate.

# Sceglie "Guidato - usa l'intero disco" al posto dell'utente, cosi' il menu
# dei cinque metodi non viene mostrato.
d-i partman-auto/init_automatically_partition select some_device

# Come partizionare, una volta scelto il disco: una sola partizione root
# (piu' la ESP se il sistema e' UEFI, che e' obbligatoria).
d-i partman-auto/method string regular
d-i partman-auto/choose_recipe select atomic
d-i partman/default_filesystem string ext4

# partman-auto/disk NON preseedato: e' l'unica domanda che vogliamo venga
# posta. Con un solo disco l'installer lo sceglie da se' senza chiedere.
#d-i partman-auto/disk string /dev/sda

# Rimuove LVM/RAID preesistenti senza domande accessorie: cosi' l'unico
# prompt che resta e' la conferma finale di scrittura.
d-i partman-lvm/device_remove_lvm boolean true
d-i partman-md/device_remove_md boolean true
d-i partman-lvm/confirm boolean true
d-i partman-lvm/confirm_nooverwrite boolean true
d-i partman/choose_partition select finish

# --- Conferma prima di cancellare i dati ---
# Queste tre chiavi restano deliberatamente COMMENTATE. Preseedarle, con
# qualunque valore, toglie all'utente la possibilita' di rispondere:
#   true  -> scrive subito, nessuna conferma, i dati spariscono in silenzio
#   false -> risponde "No" e l'installer torna indietro senza installare
# Non preseedarle e' l'unico modo per far comparire il dialog riepilogativo
# "Scrivere le modifiche sui dischi?".
#d-i partman/confirm boolean true
#d-i partman/confirm_nooverwrite boolean true
#d-i partman-partitioning/confirm_write_new_label boolean true

# --- Account utente ---
# Disabilita l'account root diretto
d-i passwd/root-login boolean false
# Crea un utente fittizio in background in modo silente
d-i passwd/make-user boolean true
d-i passwd/user-fullname string Temporary User
d-i passwd/username string oem
d-i passwd/user-password password oem1234
d-i passwd/user-password-again password oem1234
d-i passwd/user-default-groups string audio cdrom dip floppy video plugdev netdev sudo

# --- Gestione conffile dpkg + hostname auto da DMI ---
d-i preseed/early_command string \
    mkdir -p /etc/apt/apt.conf.d/ && \
    printf 'Dpkg::Options {"--force-confdef";"--force-confold";};\n' \
    > /etc/apt/apt.conf.d/99force-confold && \
    sh /cdrom/set-hostname.sh

# --- Selezione pacchetti ---
d-i pkgsel/upgrade select none
d-i pkgsel/update-policy select none
d-i pkgsel/include string

# --- Bootloader GRUB ---
d-i grub-installer/only_debian boolean true
d-i grub-installer/with_other_os boolean true
d-i grub-installer/bootdev string default
# UEFI: GRUB anche nel percorso di riserva EFI/BOOT/BOOTX64.EFI. Alcuni
# firmware (per esempio Acer) rimettono in cima una voce vecchia che punta a
# EFI/Boot, come "Linpus lite": cosi' anche quella avvia RuscaLinux.
d-i grub-installer/force-efi-extra-removable boolean true

# --- Branding installer ---
d-i debian-installer/title string RuscaLinux @VERSION@ 

# ---------------------------------------------------------------------------
# late_command
# ---------------------------------------------------------------------------
d-i preseed/late_command string \
    cp /cdrom/ruscalinux-postinstall.sh /target/tmp/ruscalinux-postinstall.sh ; \
    chmod +x /target/tmp/ruscalinux-postinstall.sh ; \
    if grep -qw rusca.driver=nvidia /proc/cmdline ; then touch /target/tmp/ruscalinux-driver-nvidia ; fi ; \
    if [ -f /tmp/ruscalinux-hostname ] ; then cp /tmp/ruscalinux-hostname /target/tmp/ruscalinux-hostname ; fi ; \
    in-target /tmp/ruscalinux-postinstall.sh || true

# --- Fine installazione ---
# finish-install/reboot_in_progress NON preseedato: l'installer GTK
# mostrerà il dialog "Installazione completata" e aspetterà il click
# su Continua prima di spegnere (dà il tempo di rimuovere la USB).
d-i finish-install/keep-consoles boolean false
d-i debian-installer/exit/poweroff boolean true
EOF

# ---------------------------------------------------------------------------
# Script post-installazione (chiamato dal late_command)
# ---------------------------------------------------------------------------
cat <<'POSTINSTALL' > .work/config/includes.binary/ruscalinux-postinstall.sh
#!/bin/sh
set -e

# ---------------------------------------------------------------------------
# TEMA PLYMOUTH — forza la selezione e rigenera l'initramfs nel sistema installato
# Necessario perché il Debian Installer rigenera l'initramfs PRIMA di late_command,
# quindi dobbiamo farlo di nuovo alla fine per avere il tema corretto sul disco.
# ---------------------------------------------------------------------------
if command -v plymouth-set-default-theme >/dev/null 2>&1; then
    update-alternatives --install \
        /usr/share/plymouth/themes/default.plymouth \
        default.plymouth \
        /usr/share/plymouth/themes/ruscalinux/ruscalinux.plymouth \
        200 2>/dev/null || true
    plymouth-set-default-theme ruscalinux
fi

# Rigenera l'initramfs per tutti i kernel installati con il tema corretto
update-initramfs -u -k all || true

# ===========================================================================
# HOSTNAME — quello scelto dall'installer dal modello della macchina (vedi
# set-hostname.sh). Se in /etc/hostname c'e' un nome di ripiego (debian,
# localhost...), si usa quello calcolato da set-hostname.sh, che il
# late_command copia in /tmp; se manca anche quello, "ruscalinux".
# /etc/hosts deve avere lo stesso nome su 127.0.1.1.
# ===========================================================================
ripiego() {
    case "$1" in ""|debian|localhost|localhost.localdomain|unassigned-hostname) return 0 ;; esac
    return 1
}
NOME=$(head -n 1 /etc/hostname 2>/dev/null | tr -d ' \t\r')
if ripiego "$NOME"; then
    NOME=$(head -n 1 /tmp/ruscalinux-hostname 2>/dev/null | tr -d ' \t\r')
    ripiego "$NOME" && NOME=ruscalinux
fi
rm -f /tmp/ruscalinux-hostname
echo "$NOME" > /etc/hostname
if grep -q "^127\.0\.1\.1" /etc/hosts; then
    sed -i "s/^127\.0\.1\.1.*/127.0.1.1\t$NOME/" /etc/hosts
else
    printf '127.0.1.1\t%s\n' "$NOME" >> /etc/hosts
fi
echo ">>> Hostname: $NOME"

# ===========================================================================
# MODALITÀ OEM: FORZA GNOME INITIAL SETUP COMPLETO AL PRIMO AVVIO
# ===========================================================================

# Rileva l'utente creato temporaneamente dal Debian Installer
IUSER=$(ls /home/ 2>/dev/null | grep -v lost+found | head -1)

if [ -n "$IUSER" ]; then
    echo ">>> Eliminazione utente provvisorio $IUSER per forzare GNOME Initial Setup..."
    # Elimina l'utente e la sua home directory
    userdel -r "$IUSER" 2>/dev/null || true
    
    # Elimina SOLO il profilo AccountsService dell'utente provvisorio
    rm -f "/var/lib/AccountsService/users/$IUSER" 2>/dev/null || true
fi

# GDM e GNOME Initial Setup in inglese: i loro file AccountsService
# (Debian-gdm, gnome-initial-setup) sono gia' nel sistema copiato dalla live
# (steps/30-custom.sh, FIX 3-BIS).

# Preserva la lingua scelta dall'utente nel Debian Installer.
# Il Debian Installer ha già scritto LANG in /etc/default/locale;
# la sovrascrittura forzata a en_US.UTF-8 era la causa per cui GNOME
# rimaneva in inglese anche dopo aver impostato un'altra lingua.
# Sincronizziamo solo /etc/locale.conf (richiesto da systemd) con
# il valore scelto dall'installer, o en_US.UTF-8 come fallback sicuro.
INST_LANG=$(grep '^LANG=' /etc/default/locale 2>/dev/null | cut -d= -f2 | head -1)
[ -z "$INST_LANG" ] && INST_LANG="en_US.UTF-8"
printf 'LANG=%s\n' "$INST_LANG" > /etc/locale.conf

# ===========================================================================
# AUTOLOGIN PER IL PRIMO UTENTE REALE
# ===========================================================================
# L'utente viene creato da gnome-initial-setup al primo boot, quindi il suo
# username NON è noto in fase di installazione. Installiamo un servizio
# systemd "oneshot" che, ad ogni boot, controlla se esiste un utente "umano"
# (UID >= 1000) e, in caso affermativo, configura l'autologin in
# /etc/gdm3/daemon.conf. Dopo la prima esecuzione si auto-disabilita.
# ---------------------------------------------------------------------------
mkdir -p /usr/local/sbin
cat > /usr/local/sbin/ruscalinux-setup-autologin <<'AUTOSCRIPT'
#!/bin/sh
set -e

FLAG=/var/lib/ruscalinux/autologin.done
[ -f "$FLAG" ] && exit 0

# Trova il primo utente "umano" (UID >= 1000, < 65000), escluso nobody/gdm
USER=$(getent passwd | awk -F: '$3 >= 1000 && $3 < 65000 && $1 != "nobody" {print $1; exit}')
[ -z "$USER" ] && exit 0

# Configura GDM3
mkdir -p /etc/gdm3
CONF=/etc/gdm3/daemon.conf

if [ ! -f "$CONF" ]; then
    printf '[daemon]\n' > "$CONF"
fi

# Rimuove eventuali righe pregresse e riscrive la sezione [daemon]
sed -i '/^AutomaticLoginEnable\s*=/d; /^AutomaticLogin\s*=/d' "$CONF"
if grep -q '^\[daemon\]' "$CONF"; then
    sed -i "/^\[daemon\]/a AutomaticLoginEnable=true\nAutomaticLogin=$USER" "$CONF"
else
    printf '\n[daemon]\nAutomaticLoginEnable=true\nAutomaticLogin=%s\n' "$USER" >> "$CONF"
fi

# ---------------------------------------------------------------------------
# Propaga la lingua scelta in gnome-initial-setup al locale di sistema.
# g-i-s scrive Language= nell'AccountsService dell'utente al primo boot.
# Questo servizio gira Before=display-manager al secondo boot: aggiornando
# /etc/locale.conf PRIMA che GDM parta, la sessione autologin parte già
# nella lingua scelta dall'utente, senza dipendere dal meccanismo
# AccountsService→sessione di GDM (che con autologin può non attivarsi).
# ---------------------------------------------------------------------------
AS_FILE="/var/lib/AccountsService/users/$USER"
if [ -f "$AS_FILE" ]; then
    USER_LANG=$(grep '^Language=' "$AS_FILE" | cut -d= -f2 | head -1)
    if [ -n "$USER_LANG" ]; then
        printf 'LANG=%s\n' "$USER_LANG" > /etc/locale.conf
        printf 'LANG=%s\n' "$USER_LANG" > /etc/default/locale
        # Forza systemd-localed a rileggere il file aggiornato
        systemctl restart systemd-localed 2>/dev/null || true
    fi
fi

mkdir -p /var/lib/ruscalinux
touch "$FLAG"
# Disabilita il servizio dopo la prima esecuzione riuscita
systemctl disable ruscalinux-autologin.service 2>/dev/null || true
AUTOSCRIPT
chmod +x /usr/local/sbin/ruscalinux-setup-autologin

cat > /etc/systemd/system/ruscalinux-autologin.service <<'AUTOUNIT'
[Unit]
Description=Configura autologin GDM per il primo utente reale (RuscaLinux)
Before=display-manager.service
ConditionPathExists=!/var/lib/ruscalinux/autologin.done

[Service]
Type=oneshot
ExecStart=/usr/local/sbin/ruscalinux-setup-autologin
RemainAfterExit=yes

[Install]
WantedBy=multi-user.target
AUTOUNIT

systemctl enable ruscalinux-autologin.service 2>/dev/null || true

# GRUB: tema e "quiet splash" sono in /etc/default/grub.d/99-ruscalinux.cfg,
# gia' nel sistema copiato dalla live (steps/30-custom.sh, FIX 1).
update-grub || true

# Disabilita repository e aggiornamenti automatici
echo "# Repository disabilitate da ruscalinux installer" > /etc/apt/sources.list
rm -f /etc/apt/sources.list.d/*.list
rm -f /etc/apt/sources.list.d/*.sources

systemctl disable apt-daily.timer         2>/dev/null || true
systemctl disable apt-daily-upgrade.timer 2>/dev/null || true
systemctl mask   apt-daily.service        2>/dev/null || true
systemctl mask   apt-daily-upgrade.service 2>/dev/null || true

if [ -f /etc/apt/apt.conf.d/20auto-upgrades ]; then
    printf 'APT::Periodic::Update-Package-Lists "0";\nAPT::Periodic::Unattended-Upgrade "0";\n' \
        > /etc/apt/apt.conf.d/20auto-upgrades
fi

# Rimuovi lo script live-config di g-i-s: sul sistema installato
# live-config non gira mai, il file sarebbe solo un residuo inerte.
rm -f /usr/lib/live/config/2000-ruscalinux-gis

# UEFI: RuscaLinux per prima nell'ordine di avvio del firmware. efibootmgr
# di trixie stampa il percorso dopo il nome, separato da una tabulazione:
# il nome e' il primo campo. Le altre
# voci (per esempio Windows) restano, dopo. Se GRUB e' stato copiato anche
# in EFI/BOOT (preseed force-efi-extra-removable), gli si mette accanto il
# grub.cfg di questa installazione.
if [ -d /sys/firmware/efi ] && command -v efibootmgr > /dev/null; then
    NUM=$(efibootmgr 2> /dev/null \
        | awk -F '\t' 'tolower($1) ~ /^boot[0-9a-f][0-9a-f][0-9a-f][0-9a-f][*]? ruscalinux[ ]*$/ { print substr($1, 5, 4); exit }')
    if [ -n "$NUM" ]; then
        ORDINE=$(efibootmgr 2> /dev/null | sed -n 's/^BootOrder: //p')
        RESTO=$(echo "$ORDINE" | tr ',' '\n' | grep -vix "$NUM" | paste -sd, -)
        efibootmgr -o "$NUM${RESTO:+,$RESTO}" > /dev/null 2>&1 || true
        echo ">>> UEFI: voce Boot$NUM (ruscalinux) prima nell'ordine di avvio"
    else
        echo ">>> UEFI: voce ruscalinux non trovata, ordine di avvio invariato"
    fi
    # Sempre sovrascritto: la partizione EFI puo' sopravvivere a una
    # reinstallazione, e un grub.cfg vecchio cercherebbe il disco
    # dell'installazione precedente (GRUB si fermerebbe alla riga di comando).
    for dir in /boot/efi/EFI/ruscalinux /boot/efi/EFI/debian; do
        if [ -f "$dir/grub.cfg" ] && [ -f /boot/efi/EFI/BOOT/grubx64.efi ]; then
            cp -f "$dir/grub.cfg" /boot/efi/EFI/BOOT/grub.cfg
            echo ">>> UEFI: grub.cfg copiato in EFI/BOOT"
            break
        fi
    done
fi

# Driver: liberi oppure NVIDIA, secondo la voce scelta nel menu
# dell'installer (il late_command lascia /tmp/ruscalinux-driver-nvidia).
# Gira per ultimo perche' aggiunge una voce a GRUB e rilancia update-grub.
if [ -x /usr/lib/ruscalinux/nvidia-postinstall ]; then
    /usr/lib/ruscalinux/nvidia-postinstall || true
fi

echo ">>> Post-installazione ruscalinux  completata."
POSTINSTALL

chmod +x .work/config/includes.binary/ruscalinux-postinstall.sh

# --- Hook installer: forza uso del CD come sorgente APT ---
mkdir -p .work/config/hooks/installer/
cat <<'EOF' > .work/config/hooks/installer/9000-offline-apt.hook.installer
#!/bin/sh
set -e
if [ -f /etc/apt/sources.list ]; then
    grep -v "^deb http" /etc/apt/sources.list > /tmp/sources.list.clean || true
    mv /tmp/sources.list.clean /etc/apt/sources.list
fi
exit 0
EOF
chmod +x .work/config/hooks/installer/9000-offline-apt.hook.installer

# ---------------------------------------------------------------------------
# BANNER INSTALLER DEBIAN (Color Vinaccia + Testo)
# ---------------------------------------------------------------------------
# Creiamo la cartella che live-build inietta nell'installer
mkdir -p .work/config/includes.installer/usr/share/graphics/

# Copiamo il banner sovrascrivendo i loghi di default (chiaro e scuro)
cp "$BANNER_SRC" .work/config/includes.installer/usr/share/graphics/logo_debian.png
cp "$BANNER_SRC" .work/config/includes.installer/usr/share/graphics/logo_debian_dark.png

# ---------------------------------------------------------------------------
# TEMA INSTALLER DEBIAN — ACCENTI PRUGNA (v@VERSION@, rev. 3 — GTK2)
# ---------------------------------------------------------------------------
# Le revisioni precedenti (CSS GTK3) non potevano funzionare: dal sorgente
# di cdebconf (debian/control: Build-Depends libgtk2.0-dev) risulta che il
# frontend grafico del debian-installer è ancora GTK2, e GTK2 non legge
# alcun CSS. Il tema dell'installer è "Clearlooks", caricato da
# /usr/share/themes/Clearlooks/gtk-2.0/gtkrc dentro l'initrd (rootskel-gtk
# imposta gtk-theme-name in /etc/gtk-2.0/gtkrc); barra di avanzamento e
# selezioni prendono il colore dagli slot bg[SELECTED]/base[SELECTED].
#
# Fix (doppio, per robustezza):
#  1) sovrascrittura del gtkrc del tema via includes.installer — lo stesso
#     meccanismo del banner, che sappiamo funzionare;
#  2) override in /root/.gtkrc-2.0 e /.gtkrc-2.0: in GTK2 gli rc "utente"
#     hanno priorità più alta degli stili del tema, quindi coprono anche
#     il tema "dark" (boot theme=dark) o variazioni di percorso.
# ---------------------------------------------------------------------------
mkdir -p .work/config/includes.installer/usr/share/themes/Clearlooks/gtk-2.0/
cat > .work/config/includes.installer/usr/share/themes/Clearlooks/gtk-2.0/gtkrc <<'EOF'
# RuscaLinux — tema Clearlooks dell'installer con accenti prugna (#7d2b59)
style "clearlooks-default"
{
	GtkButton::default_border	= { 0, 0, 0, 0 }
	GtkRange::trough_border		= 0
	GtkPaned::handle_size		= 6
	GtkRange::slider_width		= 15
	GtkRange::stepper_size		= 15
	GtkScrollbar::min_slider_length	= 30
	GtkCheckButton::indicator_size	= 14
	GtkMenuBar::internal-padding	= 0
	GtkTreeView::expander_size	= 14
	GtkExpander::expander_size	= 16
	GtkScale::slider-length		= 27
	GtkButton::child-displacement-x	= 1
	GtkButton::child-displacement-y	= 1

	xthickness = 1
	ythickness = 1

	fg[NORMAL]		= "#000000"
	fg[PRELIGHT]		= "#000000"
	fg[SELECTED]		= "#ffffff"
	fg[ACTIVE]		= "#000000"
	fg[INSENSITIVE]		= "#b5b3ac"

	bg[NORMAL]		= "#ede9e3"
	bg[PRELIGHT]		= "#f9f7f3"
	bg[SELECTED]		= "#7d2b59"
	bg[INSENSITIVE]		= "#efebe5"
	bg[ACTIVE]		= "#dcd4c9"

	base[NORMAL]		= "#ffffff"
	base[PRELIGHT]		= "#9a4a76"
	base[ACTIVE]		= "#632247"
	base[SELECTED]		= "#7d2b59"
	base[INSENSITIVE]	= "#e8e5de"

	text[NORMAL]		= "#000000"
	text[PRELIGHT]		= "#000000"
	text[ACTIVE]		= "#ffffff"
	text[SELECTED]		= "#ffffff"
	text[INSENSITIVE]	= "#b5b3ac"

	engine "clearlooks"
	{
		menubarstyle	= 2
		animation	= FALSE
	}
}

style "clearlooks-wide" = "clearlooks-default"
{
	xthickness = 2
	ythickness = 2
}

style "clearlooks-wider" = "clearlooks-default"
{
	xthickness = 3
	ythickness = 3
}

style "clearlooks-button" = "clearlooks-wider"
{
	bg[NORMAL]	= "#f6f4f1"
	bg[INSENSITIVE]	= "#f2efeb"
	bg[PRELIGHT]	= "#faf9f8"
}

style "clearlooks-notebook" = "clearlooks-wide"
{
	bg[NORMAL]	= "#efebe5"
	bg[INSENSITIVE]	= "#efebe5"
}

style "clearlooks-tasklist" = "clearlooks-default"
{
	xthickness = 5
	ythickness = 3
}

style "clearlooks-menu" = "clearlooks-default"
{
	xthickness = 2
	ythickness = 2
}

style "clearlooks-menubar-item" = "clearlooks-button"
{
	fg[PRELIGHT] = "#000000"
}

style "clearlooks-menu-item" = "clearlooks-default"
{
	xthickness	= 2
	ythickness	= 3
	fg[PRELIGHT]	= "#ffffff"
	text[PRELIGHT]	= "#ffffff"
}

style "clearlooks-tree" = "clearlooks-default"
{
	xthickness = 2
	ythickness = 2
}

style "clearlooks-frame-title" = "clearlooks-default"
{
	fg[NORMAL] = "#404040"
}

style "clearlooks-tooltips" = "clearlooks-default"
{
	xthickness = 4
	ythickness = 4
	bg[NORMAL] = { 1.0,1.0,0.75 }
}

style "clearlooks-progressbar" = "clearlooks-wide"
{
	xthickness	= 1
	ythickness	= 1
	fg[PRELIGHT]	= "#ffffff"
}

style "clearlooks-combo" = "clearlooks-button"
{
}

# widget styles
class "GtkWidget"	style "clearlooks-default"
class "GtkButton"	style "clearlooks-button"
class "GtkScale"	style "clearlooks-button"
class "GtkCombo"	style "clearlooks-button"
class "GtkRange"	style "clearlooks-wide"
class "GtkFrame"	style "clearlooks-wide"
class "GtkMenu"		style "clearlooks-menu"
class "GtkEntry"	style "clearlooks-wider"
class "GtkMenuItem"	style "clearlooks-menu-item"
class "GtkNotebook"	style "clearlooks-notebook"
class "GtkProgressBar"	style "clearlooks-progressbar"

widget_class "*MenuItem.*"			style "clearlooks-menu-item"

# combobox stuff
widget_class "*.GtkComboBox.GtkButton"		style "clearlooks-combo"
widget_class "*.GtkCombo.GtkButton"		style "clearlooks-combo"
# tooltips stuff
widget_class "*.tooltips.*.GtkToggleButton"	style "clearlooks-tasklist"
widget "gtk-tooltips"				style "clearlooks-tooltips"

# treeview stuff
widget_class "*.GtkTreeView.GtkButton"		style "clearlooks-tree"
widget_class "*.GtkCTree.GtkButton"		style "clearlooks-tree"
widget_class "*.GtkList.GtkButton"		style "clearlooks-tree"
widget_class "*.GtkCList.GtkButton"		style "clearlooks-tree"
widget_class "*.GtkFrame.GtkLabel"		style "clearlooks-frame-title"

# notebook stuff
widget_class "*.GtkNotebook.*.GtkEventBox"	style "clearlooks-notebook"
widget_class "*.GtkNotebook.*.GtkViewport"	style "clearlooks-notebook"
EOF

# Fallback: rc utente (priorità superiore al tema in GTK2), copre anche
# il tema dark e HOME=/ o HOME=/root nell'ambiente d-i.
for RCPATH in root/.gtkrc-2.0 .gtkrc-2.0; do
    mkdir -p ".work/config/includes.installer/$(dirname "$RCPATH")" 2>/dev/null || true
    cat > ".work/config/includes.installer/$RCPATH" <<'EOF'
# RuscaLinux — override accenti prugna per l'installer (GTK2)
style "ruscalinux-accent"
{
	bg[SELECTED]	= "#7d2b59"
	base[SELECTED]	= "#7d2b59"
	base[ACTIVE]	= "#632247"
	base[PRELIGHT]	= "#9a4a76"
	fg[SELECTED]	= "#ffffff"
	text[SELECTED]	= "#ffffff"
}
class "GtkWidget" style "ruscalinux-accent"
EOF
done

# ---------------------------------------------------------------------------
# IMPEDISCI L'INSTALLAZIONE DI FORTUNE ED EVENTUALI ALTRI PACCHETTI TRAMITE APT PREFERENCES
# ---------------------------------------------------------------------------
mkdir -p .work/config/includes.chroot_before_packages/etc/apt/preferences.d/
cat <<'EOF' > .work/config/includes.chroot_before_packages/etc/apt/preferences.d/99-exclude-packages
Package: fortune-mod
Pin: release *
Pin-Priority: -1

Explanation: VLC non va installato: il lettore video e' SMPlayer.
Explanation: Si bloccano il programma e la sua interfaccia grafica; le
Explanation: librerie libvlc restano installabili per chi ne dipende.
Package: vlc vlc-bin vlc-plugin-qt vlc-plugin-skins2 vlc-l10n
Pin: release *
Pin-Priority: -1
EOF

# ---------------------------------------------------------------------------
# NOMI STABILI PER GLI SFONDI PREDEFINITI
#
# I file esportati dal generatore hanno il seed nel nome
# (ruscalinux-wallpaper-dark-4526880-3840x2160.png), e il seed cambia a ogni
# nuova composizione. Se le chiavi gsettings puntassero a quel nome, alla
# prossima serie di sfondi il desktop partirebbe senza sfondo — e senza alcun
# errore, perche' una picture-uri che non esiste non produce nessun messaggio.
#
# Questo hook crea i collegamenti dal nome stabile al file reale per gli sfondi
# predefiniti (mid per il tema chiaro, dark per il tema scuro e il blocco
# schermo). Le chiavi puntano ai collegamenti, quindi cambiare gli sfondi non
# richiede piu' di toccare 30-custom.sh. Lo sfondo "magic" non e' predefinito:
# compare solo in Impostazioni -> Aspetto e non ha bisogno del collegamento.
# ---------------------------------------------------------------------------
cat <<'EOF' > .work/config/hooks/normal/9992-wallpaper-aliases.hook.chroot
#!/bin/sh
set -e
DIR=/usr/share/backgrounds/ruscalinux-backgrounds
[ -d "$DIR" ] || exit 0

for variant in mid dark; do
    # Il piu' recente che corrisponde alla variante, qualunque sia il suffisso.
    target=$(ls -1 "$DIR"/ruscalinux-wallpaper-"$variant"-*.png 2>/dev/null | sort | tail -n1)
    if [ -n "$target" ]; then
        ln -sfn "$(basename "$target")" "$DIR/ruscalinux-wallpaper-$variant.png"
        echo "Sfondo $variant -> $(basename "$target")"
    else
        echo "Attenzione: nessuno sfondo trovato per la variante $variant" >&2
    fi
done
EOF

chmod +x .work/config/hooks/normal/9992-wallpaper-aliases.hook.chroot

# ---------------------------------------------------------------------------
# RIMUOVI GNOME-SOFTWARE (inutile: aggiornamenti e repository sono disabilitati)
# ---------------------------------------------------------------------------
cat <<'EOF' > .work/config/hooks/normal/9998-remove-gnome-software.hook.chroot
#!/bin/sh
set -e
apt-get remove --purge --assume-yes gnome-software gnome-software-common 2>/dev/null || true
apt-get autoremove --assume-yes 2>/dev/null || true
EOF
chmod +x .work/config/hooks/normal/9998-remove-gnome-software.hook.chroot
