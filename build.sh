#!/bin/bash
#
# Costruisce la ISO di RuscaLinux.
#
#   ./build.sh            costruisce tutto
#   ./build.sh --config   si ferma prima della build lunga (per controllare)
#   ./build.sh --clean    cancella il lavoro precedente e basta
#
# "set -e" ferma lo script appena un comando fallisce, invece di proseguire
# e produrre una ISO incompleta.
set -e

# Va sempre nella cartella dello script, anche se lo lanci da altrove.
cd "$(dirname "$0")"
RADICE=$PWD

# Carica VERSION, SUITE, ARCH e le altre impostazioni.
. ./release.conf


# --- Opzioni ---------------------------------------------------------------

SOLO_CONFIG=no

if [ "$1" = "--clean" ]; then
    sudo rm -rf .work .gen
    echo "Cancellati .work e .gen"
    exit 0
fi

if [ "$1" = "--config" ]; then
    SOLO_CONFIG=si
fi

echo "RuscaLinux $VERSION — $SUITE/$ARCH"



# --- 1. Controlli ----------------------------------------------------------

if ! command -v lb > /dev/null; then
    echo "ERRORE: manca live-build.  Installalo con:  sudo apt install live-build"
    exit 1
fi

# Servono a make-debs.sh per costruire i pacchetti di branding/ e tools/.
for comando in dpkg-deb python3; do
    if ! command -v "$comando" > /dev/null; then
        echo "ERRORE: manca $comando.  Installalo con:  sudo apt install $comando"
        exit 1
    fi
done

# Il banner dell'installer si ridisegna a ogni build con la versione di
# release.conf (branding/generators/ruscalinux-banner.py): serve Pillow.
if ! python3 -c "import PIL" 2> /dev/null; then
    echo "ERRORE: manca Pillow per Python.  Installalo con:  sudo apt install python3-pil"
    exit 1
fi

# Driver NVIDIA (steps/40-nvidia.sh, docs/NVIDIA.md): openssl crea la chiave
# di firma dei moduli, unsquashfs controlla che la chiave privata non sia
# finita nella ISO.
for coppia in openssl:openssl base64:coreutils unsquashfs:squashfs-tools; do
    comando=${coppia%%:*}
    pacchetto=${coppia#*:}
    if ! command -v "$comando" > /dev/null; then
        echo "ERRORE: manca $comando.  Installalo con:  sudo apt install $pacchetto"
        exit 1
    fi
done

# Chiave del repository NVIDIA, verificata con l'impronta registrata in git.
if [ ! -f local/nvidia/cuda-archive-keyring.gpg ] || [ ! -f local/nvidia/SHA256SUMS ]; then
    echo "ERRORE: manca la chiave del repository NVIDIA in local/nvidia/."
    echo "        Le istruzioni per scaricarla una volta sola sono in docs/NVIDIA.md."
    exit 1
fi
if ! ( cd local/nvidia && sha256sum --quiet -c SHA256SUMS ); then
    echo "ERRORE: la chiave in local/nvidia/ non corrisponde all'impronta registrata."
    exit 1
fi

# Chiave di firma dei moduli NVIDIA (Secure Boot). La chiave privata NON sta
# nel repository e NON finisce nella ISO: serve solo durante la build. Va
# conservata, con una copia di riserva: con una chiave nuova, chi ha gia'
# registrato la vecchia in Secure Boot dovrebbe registrarla di nuovo.
RUSCALINUX_MOK_DIR="${RUSCALINUX_MOK_DIR:-$HOME/.local/share/ruscalinux/mok}"
if [ ! -f "$RUSCALINUX_MOK_DIR/mok.key" ] || [ ! -f "$RUSCALINUX_MOK_DIR/mok.pub" ]; then
    echo "    Creo la chiave di firma dei moduli in $RUSCALINUX_MOK_DIR"
    mkdir -p "$RUSCALINUX_MOK_DIR"
    chmod 700 "$RUSCALINUX_MOK_DIR"
    openssl req -new -x509 -newkey rsa:2048 -nodes -days 36500 \
        -subj "/CN=RuscaLinux module signing key/" \
        -keyout "$RUSCALINUX_MOK_DIR/mok.key" \
        -outform DER -out "$RUSCALINUX_MOK_DIR/mok.pub" 2> /dev/null
    chmod 600 "$RUSCALINUX_MOK_DIR/mok.key"
    echo "    FAI UNA COPIA DI RISERVA di $RUSCALINUX_MOK_DIR: e' la chiave"
    echo "    che gli utenti registrano in Secure Boot."
fi
export RUSCALINUX_MOK_DIR

if [ "$(id -u)" = "0" ]; then
    echo "ERRORE: non lanciare questo script come root. Usa il tuo utente:"
    echo "        lo script chiama sudo da solo dove serve."
    exit 1
fi


# --- 2. Pacchetti .deb -----------------------------------------------------
#
# I .deb non stanno in git: sono prodotti da make-debs.sh a partire da
# branding/ e tools/. Li ricostruisce se la cartella non c'e', oppure se un
# file in branding/ o tools/ e' piu' recente dei pacchetti (le cartelle
# build-deb/ dei tool sono escluse: sono a loro volta risultati).

echo
echo "==> Pacchetti"

if [ ! -d local/extra_debs ]; then
    ./make-debs.sh
elif [ -n "$(find branding tools -name build-deb -prune -o \
             -type f -newer local/extra_debs -print -quit)" ]; then
    echo "    branding/ o tools/ sono cambiati: ricostruisco i pacchetti"
    ./make-debs.sh
fi

# Motore dei modelli: make-deb.sh costruisce l'ultima release stabile di
# llama.cpp. Se ne e' uscita una piu' nuova di quella gia' impacchettata, si
# ricostruisce anche se in tools/ non e' cambiato nulla. Senza rete il
# controllo si salta e resta il pacchetto che c'e'.
MOTORE=$(ls local/extra_debs/ruscallama-engine-*.deb 2> /dev/null | head -n 1)
ULTIMA=$(bash tools/ruscallama-engine/ultima-versione.sh 2> /dev/null | cut -d ' ' -f 1 || true)
if [ -n "$MOTORE" ] && [ -n "$ULTIMA" ] && \
   ! dpkg-deb -f "$MOTORE" Description | grep -qF "llama.cpp $ULTIMA,"; then
    echo "    llama.cpp $ULTIMA e' piu' recente del motore impacchettato: ricostruisco i pacchetti"
    ./make-debs.sh
fi

# Lo stesso per il motore di riconoscimento vocale (whisper.cpp).
MOTORE=$(ls local/extra_debs/ruscawhisper-engine-*.deb 2> /dev/null | head -n 1)
ULTIMA=$(bash tools/ruscawhisper-engine/ultima-versione.sh 2> /dev/null | cut -d ' ' -f 1 || true)
if [ -n "$MOTORE" ] && [ -n "$ULTIMA" ] && \
   ! dpkg-deb -f "$MOTORE" Description | grep -qF "whisper.cpp $ULTIMA,"; then
    echo "    whisper.cpp $ULTIMA e' piu' recente del motore impacchettato: ricostruisco i pacchetti"
    ./make-debs.sh
fi

# Controlla che ci siano davvero. Una ISO senza una utility si costruisce
# lo stesso, e te ne accorgeresti solo dopo l'avvio.
#
# Si guarda il nome del pacchetto scritto DENTRO il .deb, non il nome del
# file: i tool producono <nome>-ruscalinux_<versione>_all.deb.
for cartella in tools/*/; do
    atteso=$(basename "$cartella")
    trovato=""
    for deb in local/extra_debs/*.deb; do
        [ -f "$deb" ] || continue
        if [ "$(dpkg-deb -f "$deb" Package)" = "$atteso" ]; then
            trovato="$deb"
            break
        fi
    done
    if [ -z "$trovato" ]; then
        echo "ERRORE: manca il pacchetto $atteso."
        echo "        Rilancia ./make-debs.sh e leggi cosa dice."
        exit 1
    fi
    echo "    $atteso $(dpkg-deb -f "$trovato" Version)"
done


# --- 3. Scrive la versione negli script ------------------------------------
#
# Gli script in steps/ contengono @VERSION@ al posto del numero. Qui vengono
# copiati in .gen/ con il numero vero. Cosi' la versione e' scritta in un
# posto solo: release.conf.

echo
echo "==> Versione $VERSION"

rm -rf .gen
mkdir .gen

for file in steps/*.sh; do
    sed -e "s|@VERSION@|$VERSION|g" \
        -e "s|@NVIDIA_PIN@|$NVIDIA_PIN|g" \
        -e "s|@NVIDIA_CUDA@|${NVIDIA_CUDA:-si}|g" \
        -e "s|@NVIDIA_REPO@|$NVIDIA_REPO|g" \
        -e "s|@SUITE@|$SUITE|g" \
        -e "s|@ARCH@|$ARCH|g" \
        -e "s|@MIRROR@|$MIRROR|g" \
        "$file" > ".gen/$(basename "$file")"
done

# Banner dell'installer grafico, con questa versione: .gen/banner.png.
# Lo usa steps/30-custom.sh.
python3 branding/generators/ruscalinux-banner.py "$VERSION" .gen/banner.png


# --- 4. Prepara la configurazione di live-build ----------------------------

echo
echo "==> Configurazione"

sudo rm -rf .work

sh .gen/10-config.sh
sh .gen/20-packages.sh
sh .gen/30-custom.sh
sh .gen/40-nvidia.sh

if [ "$SOLO_CONFIG" = "si" ]; then
    echo
    echo "Fermato prima della build (--config)."
    echo "ATTENZIONE: .work/config/hooks/normal/0500-nvidia-driver.hook.chroot"
    echo "            contiene la chiave privata di firma: ./build.sh --clean"
    echo "            la cancella insieme al resto."
    exit 0
fi

# L'hook del driver contiene la chiave privata di firma dei moduli (in
# base64). Nella ISO non entra, ma resterebbe in .work/ dopo la build, o nel
# chroot se la build si ferma a meta'. Si cancella comunque finisca la build.
pulisci_chiave() {
    sudo find "$RADICE/.work" -name '0500-nvidia-driver.hook.chroot' -delete 2> /dev/null || true
    sudo rm -f "$RADICE/.work/chroot/var/lib/dkms/mok.key"
}
trap pulisci_chiave EXIT


# --- 5. Costruisce la ISO --------------------------------------------------

echo
echo "==> Costruzione della ISO (ci vuole parecchio)"

cd .work
sudo lb build
cd ..

# live-build aggiunge da solo "-amd64.hybrid" al nome che gli abbiamo dato.
# La ISO resta ibrida (si scrive tale e quale su una chiavetta), ma nel nome
# ".hybrid" non serve a chi scarica: si toglie.
ISO="ruscalinux-$VERSION-$ARCH.iso"
ISO_LB="ruscalinux-$VERSION-$ARCH.hybrid.iso"

if [ ! -f ".work/$ISO_LB" ]; then
    echo "ERRORE: la ISO non e' stata prodotta. Guarda i messaggi qui sopra."
    exit 1
fi
mv -f ".work/$ISO_LB" ".work/$ISO"

# La chiave privata di firma dei moduli NVIDIA non deve essere nella ISO.
# L'hook la cancella; qui si controlla.
if sudo unsquashfs -l .work/binary/live/filesystem.squashfs \
        | grep -E 'mok\.key|nvidia-driver\.hook' > /dev/null; then
    echo "ERRORE: nella ISO c'e' la chiave privata di firma. ISO eliminata."
    rm -f ".work/$ISO"
    exit 1
fi
echo "    Controllo chiave privata: assente dalla ISO"

# Testo dell'installer (local/installer/S61ruscalinux-dpi): lo script deve
# essere nell'initrd grafico, e S62Xorg di Debian deve ancora contenere la
# riga "Xorg $DPMS", in cui lo script aggiunge -dpi. Se Debian la cambia,
# l'installer funziona lo stesso ma con il testo piccolo: lo si dice, senza
# fermarsi.
INITRD_GTK=$(sudo find .work/binary/install -path '*gtk*' -name 'initrd.gz' 2> /dev/null | head -n 1)
if [ -z "$INITRD_GTK" ]; then
    echo "    ATTENZIONE: initrd dell'installer grafico non trovato: testo non verificato"
else
    ESITO=$(sudo cat "$INITRD_GTK" | python3 -c '
import gzip, re, sys
dati = gzip.decompress(sys.stdin.buffer.read())
file, tipo, i = {}, {}, 0
while True:
    i = dati.find(b"070701", i)          # inizio del prossimo elemento cpio
    if i < 0:
        break
    h = dati[i:i + 110]
    modo = int(h[14:22], 16)
    dim, nome_len = int(h[54:62], 16), int(h[94:102], 16)
    nome = dati[i + 110:i + 110 + nome_len - 1].decode(errors="replace")
    inizio = (i + 110 + nome_len + 3) & ~3
    file[nome] = dati[inizio:inizio + dim]  # gli archivi aggiunti dopo vincono
    tipo[nome] = modo & 0o170000
    i = (inizio + dim + 3) & ~3
def trova(nome):                        # usr/lib (merged-usr) o lib
    for p in ("usr/lib/", "lib/"):
        if p + nome in file:
            return file[p + nome]
    return None
s61 = trova("debian-installer.d/S61ruscalinux-dpi")
s62 = (trova("debian-installer.d/S62Xorg") or b"").decode(errors="replace")
# merged-usr (trixie): lib deve essere un collegamento. Se diventa una
# cartella mentre i file dell installer stanno in usr/lib, non parte nulla.
if tipo.get("lib") == 0o040000 and \
   any(n.startswith("usr/lib/debian-installer") for n in file):
    print("ERRORE: nell initrd c e una cartella lib/ accanto a usr/lib: l installer non parte")
elif not s61:
    print("manca S61ruscalinux-dpi nell initrd")
elif "Xorg $DPMS" not in s62:
    print("in S62Xorg di Debian manca la riga Xorg $DPMS dove aggiungere -dpi")
else:
    print("ok")
' 2>&1 || echo "initrd illeggibile")
    case "$ESITO" in ERRORE*)
        echo "    $ESITO"
        exit 1 ;;
    esac
    if [ "$ESITO" = ok ]; then
        echo "    Testo dell'installer: script presente, Xorg ricevera' -dpi"
    else
        echo "    ATTENZIONE: testo dell'installer non ingrandito ($ESITO)."
        echo "                Vedi local/installer/S61ruscalinux-dpi."
    fi
fi

cd .work
sha256sum "$ISO" > SHA256SUMS
cd ..

PESO=$(du -h ".work/$ISO" | cut -f 1)
SHA=$(cut -d ' ' -f 1 .work/SHA256SUMS)


# --- 6. Documenti del rilascio ---------------------------------------------
#
# RELEASE-NOTES.md e i due file in dist/ contengono @VERSION@, @SHA256@ e
# simili al posto dei valori veri. Qui vengono riempiti con quelli di questa
# ISO. Serve a non ricopiare a mano un checksum di 64 caratteri: se lo sbagli,
# la verifica fallisce a chiunque scarichi e non se ne accorge nessuno.
#
# Il numero di pacchetti lo conta live-build, nel file .packages che scrive
# accanto alla ISO: e' l'unico modo di averlo giusto.

PACCHETTI=$(wc -l < ".work/ruscalinux-$VERSION-$ARCH.packages" 2> /dev/null || echo "?")

# Versione del driver NVIDIA davvero installato nella ISO (senza epoca e
# revisione Debian): finisce nelle note di rilascio, cosi' chi legge un
# bollettino di sicurezza NVIDIA sa se lo riguarda.
NVIDIA=$(awk '{ p = $1; sub(/:.*/, "", p) } p == "nvidia-driver" { print $2; exit }' \
             ".work/ruscalinux-$VERSION-$ARCH.packages" 2> /dev/null \
         | sed -e 's/^[0-9]*://' -e 's/-[^-]*$//')
if [ -z "$NVIDIA" ]; then
    echo "ATTENZIONE: versione del driver NVIDIA non trovata nel file .packages"
    NVIDIA="?"
fi
OGGI=$(date +%Y-%m-%d)

riempi() {                        # riempi  MODELLO  DESTINAZIONE
    sed -e "s|@VERSION@|$VERSION|g" \
        -e "s|@SUITE@|$SUITE|g" \
        -e "s|@ARCH@|$ARCH|g" \
        -e "s|@KERNEL@|$KERNEL|g" \
        -e "s|@DESKTOP@|$DESKTOP|g" \
        -e "s|@ISO@|$ISO|g" \
        -e "s|@SHA256@|$SHA|g" \
        -e "s|@SIZE@|$PESO|g" \
        -e "s|@PACCHETTI@|$PACCHETTI|g" \
        -e "s|@NVIDIA@|$NVIDIA|g" \
        -e "s|@DATE@|$OGGI|g" \
        "$1" > "$2"
}

riempi RELEASE-NOTES.md "RELEASE-NOTES-$VERSION.md"
riempi dist/README.md   .work/README.md
riempi dist/INSTALL.md  .work/INSTALL.md


echo
echo "Fatto: RuscaLinux $VERSION"
echo "  file       .work/$ISO"
echo "  peso       $PESO"
echo "  sha256     $SHA"
echo "  pacchetti  $PACCHETTI"
echo "  nvidia     $NVIDIA  (ramo $NVIDIA_PIN: controlla che sia la versione provata)"
echo
echo "Da caricare su SourceForge, tutti in .work/ :"
echo "  $ISO"
echo "  SHA256SUMS"
echo "  ruscalinux-$VERSION-$ARCH.packages"
echo "  README.md   INSTALL.md"
echo
echo "Per la release GitHub:  RELEASE-NOTES-$VERSION.md"
echo
echo "Adesso:  ./test.sh    provala in QEMU"
echo "         poi pubblica a mano — la lista dei passi e' in COME-FUNZIONA.md"
