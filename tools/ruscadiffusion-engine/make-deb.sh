#!/bin/bash
# ---------------------------------------------------------------------------
# RuscaLinux — costruisce il pacchetto ruscadiffusion-engine.
#
#   ./make-deb.sh
#
# ruscadiffusion-engine e' il motore di generazione delle immagini di
# RuscaLLama. E' stable-diffusion.cpp, SOFTWARE ESTERNO (licenza MIT,
# https://github.com/leejet/stable-diffusion.cpp), compilato dal sorgente con
# il backend Vulkan: un solo binario per NVIDIA, AMD e Intel, che ripiega
# sulla CPU quando non trova una scheda. E' fatto come ruscawhisper-engine
# (whisper.cpp): stesse regole, stessi controlli.
#
# Regole delle specifiche dei RuscaLinux OS Tools:
#   * versione del pacchetto = versione di RuscaLinux (release.conf);
#     la versione di stable-diffusion.cpp e' scritta nella descrizione e
#     nella documentazione del pacchetto;
#   * un solo .deb in build-deb/, con suffisso -ruscalinux e SHA256SUMS;
#   * architettura amd64: e' codice compilato, non Python.
#
# Quale stable-diffusion.cpp: l'ultima release pubblicata su GitHub (tag
# master-<numero>-<commit>), trovata da ultima-versione.sh.
#
# Il sorgente sono DUE archivi: stable-diffusion.cpp usa una propria copia di
# ggml (github.com/leejet/ggml) come sottomodulo git, e gli archivi di GitHub
# non contengono i sottomoduli. Il commit di ggml non si sceglie qui: e'
# quello registrato nel sorgente di stable-diffusion.cpp per quel tag.
# Controlli:
#   * il commit scritto in ciascun archivio deve essere quello atteso: il
#     commit del tag per stable-diffusion.cpp, il commit del sottomodulo per
#     ggml;
#   * le impronte SHA-256 dei due archivi (e il commit di ggml) vengono
#     registrate in checksums/ la prima volta che una versione viene
#     costruita, e le build successive della stessa versione devono trovare
#     gli stessi archivi. Il file nuovo in checksums/ va aggiunto al
#     repository (git add).
# Dopo la compilazione si controlla che sd-cli accetti tutte le opzioni
# usate da RuscaLLama (OPZIONI_USATE, qui sotto), che il binario non abbia
# codice di rete e che parta davvero (versione ed elenco delle schede).
#
# Si impacchetta solo sd-cli: un programma che legge un modello e scrive
# un'immagine. Niente sd-server: RuscaLLama non apre porte per le immagini,
# nemmeno su 127.0.0.1.
#
# Il risultato della compilazione viene tenuto in una cache
# (~/.cache/ruscalinux/ruscadiffusion-engine) e riusato finche' non cambiano
# versione, backend o opzioni: le build successive della ISO rifanno solo
# il pacchetto, in pochi secondi.
#
# Variabili utili (facoltative):
#   RUSCADIFFUSION_SD_VERSION=master-1104-5dcfa79   (o solo 1104)
#                               costruisce quella versione invece dell'ultima
#   GITHUB_TOKEN=<token>        alza il limite di richieste all'API di GitHub
#   RUSCADIFFUSION_BACKEND=cpu  compila senza Vulkan (prove, macchine senza GPU)
#   RUSCADIFFUSION_CACHE=<dir>  cartella della cache
#   RUSCADIFFUSION_JOBS=<n>     processi di compilazione (default: nproc)
#
# Dipendenze di compilazione (le stesse di ruscallama-engine):
#   sudo apt install build-essential cmake pkg-config dpkg-dev wget git \
#                    libvulkan-dev glslc spirv-headers
# ---------------------------------------------------------------------------
set -euo pipefail
cd "$(dirname "$0")"
SRC_DIR="$(pwd)"

# ── Versioni ────────────────────────────────────────────────────────────────
VER="1.99.3"                       # = VERSION in release.conf
# La versione di stable-diffusion.cpp non e' scritta qui: e' l'ultima
# release, o quella di RUSCADIFFUSION_SD_VERSION (vedi ultima-versione.sh).

# stable-diffusion.cpp pubblica una release a ogni modifica: una release piu'
# giovane di cosi' viene costruita lo stesso, ma con un avviso. Prima di
# pubblicare la ISO, prova la generazione delle immagini di RuscaLLama.
GIORNI_MINIMI=14

# Opzioni di sd-cli usate da RuscaLLama (rusca_diffusion.py). Se una release
# non ne riconosce una, il motore non partirebbe: la build si ferma.
# Aggiornare l'elenco quando il programma comincia a usare un'opzione nuova.
OPZIONI_USATE="-m --diffusion-model --vae --clip_l --clip_g --t5xxl --llm
  --prompt-file --negative-prompt-file -W -H --steps --cfg-scale
  --sampling-method -s -b -t -o --backend --list-devices --vae-tiling
  --offload-to-cpu --disable-image-metadata --preview --preview-path
  --preview-interval --llm_vision --tokenizer --embeddings-connectors
  --uncond-diffusion-model --flow-shift --sigmas --rng --model-args"

# File di thirdparty/ compilati in sd-cli. Sono tutti di altri autori e sono
# dichiarati nel file copyright qui sotto. Se una release aggiunge un file o
# una cartella che non e' in elenco, la build si ferma: va dichiarato nel
# file copyright e nelle specifiche (sezione 6), poi aggiunto qui.
#   httplib.h          solo per sd-server, che non si compila
#   cutlass libwebm libwebp   sottomoduli: non sono negli archivi e restano
#                      spenti (niente CUDA, niente WebP, niente video WebM)
TERZI_DICHIARATI="CMakeLists.txt README.md LICENSE.darts_clone.txt darts.h
  json.hpp miniz.h zip.c zip.h stb_image.h stb_image_resize.h
  stb_image_write.h httplib.h oniguruma utf8proc cutlass libwebm libwebp"

PKG="ruscadiffusion-engine"
ARCH="amd64"
MAINT="Nunzio Curcuruto <info@ruscalinux.org>"
HOMEPAGE="https://www.ruscalinux.org/"
UPSTREAM="https://github.com/leejet/stable-diffusion.cpp"
BACKEND="${RUSCADIFFUSION_BACKEND:-vulkan}"
JOBS="${RUSCADIFFUSION_JOBS:-$(nproc)}"
CACHE="${RUSCADIFFUSION_CACHE:-${XDG_CACHE_HOME:-$HOME/.cache}/ruscalinux/ruscadiffusion-engine}"
SOURCE_DATE_EPOCH="${SOURCE_DATE_EPOCH:-$(date +%s)}"

LIBDIR="usr/lib/${PKG}"            # binario (e librerie private, se ce ne sono)
PROFILE="usr.lib.ruscadiffusion-engine.sd-cli"

# Solo questo finisce nel pacchetto: sd-cli per RuscaLLama (e per il terminale).
KEEP_BINARIES="sd-cli"

die() { echo "ERRORE: $*" >&2; exit 1; }
say() { echo "==> $*"; }

avviso() { echo "ATTENZIONE: $*" >&2; }

case "$BACKEND" in vulkan|cpu) ;; *) die "RUSCADIFFUSION_BACKEND deve essere vulkan o cpu";; esac
[ -f ultima-versione.sh ] || die "manca ultima-versione.sh"
[ -f "apparmor/$PROFILE" ] || die "manca il profilo apparmor/$PROFILE"

# ── Controllo delle dipendenze, prima di scaricare o compilare ──────────────
MANCA=""
for c in dpkg-deb dpkg-shlibdeps cmake g++ make pkg-config strip nm; do
    command -v "$c" >/dev/null || MANCA="$MANCA $c"
done
command -v wget >/dev/null || command -v curl >/dev/null || MANCA="$MANCA wget"
# git serve a leggere il commit dentro gli archivi, quello del tag e quello
# del sottomodulo ggml.
command -v git >/dev/null || MANCA="$MANCA git"
if [ "$BACKEND" = vulkan ]; then
    pkg-config --exists vulkan 2>/dev/null || MANCA="$MANCA libvulkan-dev"
    command -v glslc >/dev/null || MANCA="$MANCA glslc"
    find /usr -name 'SPIRV-HeadersConfig.cmake' -print -quit 2>/dev/null | grep -q . \
        || MANCA="$MANCA spirv-headers"
fi
if [ -n "$MANCA" ]; then
    echo "ERRORE: mancano strumenti per compilare stable-diffusion.cpp:$MANCA" >&2
    echo "  sudo apt install build-essential cmake pkg-config dpkg-dev wget git \\" >&2
    echo "                   libvulkan-dev glslc spirv-headers" >&2
    exit 1
fi

mkdir -p "$CACHE/src" "$SRC_DIR/checksums"
OUT_DIR="$SRC_DIR/build-deb"
rm -rf "$OUT_DIR"
mkdir -p "$OUT_DIR"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

scarica() {                        # scarica  URL  FILE
    if command -v wget >/dev/null; then
        wget -q -O "$2" "$1"
    else
        curl -sfL -o "$2" "$1"
    fi
}

# ── Quale versione ───────────────────────────────────────────────────────────
PUBBLICATA=""
if RIGA=$(bash ./ultima-versione.sh); then
    TAG="${RIGA%% *}"
    [ "$RIGA" != "$TAG" ] && PUBBLICATA="${RIGA#* }"
else
    [ $? -eq 2 ] && die "versione di stable-diffusion.cpp non valida (RUSCADIFFUSION_SD_VERSION)"
    # Niente rete: si usa la versione piu' recente gia' scaricata e
    # registrata, cosi' una build senza connessione resta possibile.
    TAG=$(ls "$CACHE/src" 2>/dev/null \
          | sed -n 's/^stable-diffusion\.cpp-\(master-[0-9]*-[0-9a-f]*\)\.tar\.gz$/\1/p' \
          | while read -r t; do [ -f "checksums/stable-diffusion.cpp-$t.sha256" ] && echo "$t"; done \
          | sort -t- -k2,2n | tail -1) || true
    [ -n "$TAG" ] || die "non so quale stable-diffusion.cpp costruire: niente rete e niente in cache"
    avviso "non riesco a sapere quale sia l'ultima release di stable-diffusion.cpp:
            uso $TAG, gia' scaricata. Potrebbe non essere l'ultima."
fi
SD_NUMBER=$(printf '%s' "$TAG" | cut -d- -f2)
ARCHIVE="stable-diffusion.cpp-${TAG}.tar.gz"
URL="https://codeload.github.com/leejet/stable-diffusion.cpp/tar.gz/refs/tags/${TAG}"
GIT_URL="https://github.com/leejet/stable-diffusion.cpp.git"
GGML_REPO="https://github.com/leejet/ggml"
# Un solo file per versione: le due impronte e, nel nome del secondo
# archivio, il commit di ggml.
PIN="$SRC_DIR/checksums/stable-diffusion.cpp-${TAG}.sha256"
say "stable-diffusion.cpp $TAG"

# ── Sorgente di stable-diffusion.cpp: cache locale o download ────────────────
CACHED="$CACHE/src/$ARCHIVE"
if [ ! -f "$CACHED" ]; then
    say "Scarico stable-diffusion.cpp $TAG"
    scarica "$URL" "$TMP/$ARCHIVE" || die "download non riuscito ($URL)"
    mv "$TMP/$ARCHIVE" "$CACHED"
fi

# 1. Il commit dentro l'archivio (GitHub lo scrive nell'intestazione del tar)
#    deve essere quello a cui punta il tag. Se il tag e' annotato conta il
#    commit puntato (riga ^{}), non l'oggetto tag.
COMMIT=$(gzip -dc "$CACHED" | git get-tar-commit-id 2>/dev/null || true)
[ -n "$COMMIT" ] || { rm -f "$CACHED"; die "l'archivio di stable-diffusion.cpp $TAG non contiene il commit: scaricato male?"; }
REMOTO=$(timeout 60 git ls-remote "$GIT_URL" "refs/tags/$TAG" "refs/tags/$TAG^{}" 2>/dev/null || true)
COMMIT_TAG=$(printf '%s\n' "$REMOTO" | awk '/\^\{\}$/ {print $1}')
[ -n "$COMMIT_TAG" ] || COMMIT_TAG=$(printf '%s\n' "$REMOTO" | awk 'NF {print $1; exit}')
if [ -n "$COMMIT_TAG" ]; then
    if [ "$COMMIT" != "$COMMIT_TAG" ]; then
        rm -f "$CACHED"
        die "l'archivio di stable-diffusion.cpp $TAG non corrisponde al tag su GitHub
        commit nell'archivio: $COMMIT
        commit del tag:       $COMMIT_TAG
        Il file e' stato cancellato dalla cache: rilancia per riscaricarlo."
    fi
elif [ ! -f "$PIN" ]; then
    die "non riesco a leggere il tag $TAG su GitHub, e la versione non e' registrata
        in checksums/: non posso verificare il sorgente."
fi
# Il nome del tag contiene l'inizio del commit: un'altra prova gratuita.
case "$COMMIT" in
    "${TAG##*-}"*) ;;
    *) rm -f "$CACHED"; die "il commit dell'archivio ($COMMIT) non e' quello del nome del tag $TAG" ;;
esac

# ── Commit di ggml (sottomodulo) ─────────────────────────────────────────────
# Registrato in checksums/ (nome del secondo archivio); la prima volta lo si
# legge dall'albero del tag con git, scaricando solo le cartelle (niente
# file: --filter=blob:none).
GGML_COMMIT=""
if [ -f "$PIN" ]; then
    GGML_COMMIT=$(sed -n 's/.*  ggml-\([0-9a-f]\{40\}\)\.tar\.gz$/\1/p' "$PIN")
    [ -n "$GGML_COMMIT" ] || die "checksums/$(basename "$PIN") non indica il commit di ggml"
else
    say "Leggo il commit di ggml registrato nel tag $TAG"
    G="$TMP/albero"
    git init -q "$G"
    timeout 300 git -C "$G" fetch -q --depth 1 --filter=blob:none "$GIT_URL" "refs/tags/$TAG" \
        || die "non riesco a leggere l'albero di stable-diffusion.cpp $TAG"
    [ "$(git -C "$G" rev-parse 'FETCH_HEAD^{commit}')" = "$COMMIT" ] \
        || die "il tag $TAG su GitHub e' cambiato durante la build"
    GGML_COMMIT=$(git -C "$G" ls-tree FETCH_HEAD ggml | awk '$2 == "commit" {print $3}')
    [[ "$GGML_COMMIT" =~ ^[0-9a-f]{40}$ ]] || die "stable-diffusion.cpp $TAG non ha il sottomodulo ggml"
    GGML_URL_GIT=$(git -C "$G" show FETCH_HEAD:.gitmodules 2>/dev/null \
        | awk '/\[submodule "ggml"\]/ {s=1; next} /^\[/ {s=0} s && $1 == "url" {print $3}')
    [ "${GGML_URL_GIT%.git}" = "$GGML_REPO" ] || die "ggml non arriva piu' da $GGML_REPO ma da: ${GGML_URL_GIT:-?}
        Controlla da dove viene, poi aggiorna GGML_REPO in make-deb.sh."
fi
GGML_ARCHIVE="ggml-${GGML_COMMIT}.tar.gz"
GGML_CACHED="$CACHE/src/$GGML_ARCHIVE"
if [ ! -f "$GGML_CACHED" ]; then
    say "Scarico ggml ${GGML_COMMIT:0:12}"
    scarica "https://codeload.github.com/leejet/ggml/tar.gz/$GGML_COMMIT" "$TMP/$GGML_ARCHIVE" \
        || die "download di ggml non riuscito"
    mv "$TMP/$GGML_ARCHIVE" "$GGML_CACHED"
fi
COMMIT_GGML_TAR=$(gzip -dc "$GGML_CACHED" | git get-tar-commit-id 2>/dev/null || true)
if [ "$COMMIT_GGML_TAR" != "$GGML_COMMIT" ]; then
    rm -f "$GGML_CACHED"
    die "l'archivio di ggml non e' il commit registrato da stable-diffusion.cpp $TAG
        atteso:   $GGML_COMMIT
        ottenuto: ${COMMIT_GGML_TAR:-nessuno}"
fi

# 2. Impronte: registrate la prima volta, confrontate le volte successive.
OTTENUTO=$(sha256sum "$CACHED" | cut -d' ' -f1)
OTTENUTO_GGML=$(sha256sum "$GGML_CACHED" | cut -d' ' -f1)
if [ -f "$PIN" ]; then
    ATTESO=$(awk -v f="$ARCHIVE" '$2 == f {print $1}' "$PIN")
    ATTESO_GGML=$(awk -v f="$GGML_ARCHIVE" '$2 == f {print $1}' "$PIN")
    for coppia in "$ATTESO:$OTTENUTO:$CACHED" "$ATTESO_GGML:$OTTENUTO_GGML:$GGML_CACHED"; do
        IFS=: read -r a o f <<< "$coppia"
        if [ "$a" != "$o" ]; then
            rm -f "$f"
            die "l'archivio $(basename "$f") non corrisponde all'impronta registrata
        atteso:   ${a:-nessuna}
        ottenuto: $o
        Il file e' stato cancellato dalla cache: rilancia per riscaricarlo.
        Se si ripete, il sorgente e' stato cambiato su GitHub: controlla prima
        di cancellare checksums/$(basename "$PIN")."
        fi
    done
else
    printf '%s  %s\n%s  %s\n' "$OTTENUTO" "$ARCHIVE" "$OTTENUTO_GGML" "$GGML_ARCHIVE" > "$PIN"
    avviso "stable-diffusion.cpp $TAG e' una versione nuova: impronte registrate in
            tools/ruscadiffusion-engine/checksums/$(basename "$PIN")
            Aggiungile al repository (git add) insieme alla prossima modifica."
fi
say "Sorgente verificato (stable-diffusion.cpp ${COMMIT:0:12}, ggml ${GGML_COMMIT:0:12})"

# Eta' della release: data di pubblicazione se nota, altrimenti la data del
# commit, che il tar porta in ogni file.
if [ -n "$PUBBLICATA" ]; then
    DATA_RELEASE=$(date -u -d "$PUBBLICATA" +%Y-%m-%d 2>/dev/null || true)
else
    DATA_RELEASE=$(TZ=UTC tar -tvzf "$CACHED" --full-time 2>/dev/null | awk 'NR==1 {print $4}')
fi
if [ -n "$DATA_RELEASE" ]; then
    GIORNI=$(( ( $(date -u +%s) - $(date -u -d "$DATA_RELEASE" +%s) ) / 86400 ))
    case "$GIORNI" in
        0) FA="oggi"; DA="uscita oggi" ;;
        1) FA="1 giorno fa"; DA="uscita da 1 giorno" ;;
        *) FA="$GIORNI giorni fa"; DA="uscita da $GIORNI giorni" ;;
    esac
    say "Release del $DATA_RELEASE ($FA)"
    if [ "$GIORNI" -lt "$GIORNI_MINIMI" ]; then
        avviso "stable-diffusion.cpp $TAG e' $DA (meno di $GIORNI_MINIMI giorni).
            Prova la generazione delle immagini di RuscaLLama prima di
            pubblicare la ISO; per costruire una versione precedente:
            RUSCADIFFUSION_SD_VERSION=<numero> ./make-deb.sh"
    fi
fi

# ── Compilazione (o riuso della cache) ───────────────────────────────────────
# GGML_NATIVE=OFF: il binario deve girare su qualunque x86-64 recente, non
#   solo sulla macchina che costruisce la ISO.
# Niente rete (specifiche, privacy): i modelli arrivano solo dai file
#   copiati dall'utente. sd-cli non scarica nulla; per non portare dentro
#   codice di rete da altre parti:
#   SD_RPC=OFF                    niente backend RPC (--rpc-servers);
#   SD_SERVER_BUILD_FRONTEND=OFF  niente interfaccia web (si compila solo
#                                 sd-cli, non sd-server: cpp-httplib resta
#                                 fuori);
#   SD_WEBP=OFF, SD_WEBM=OFF      niente libwebp e libwebm (sottomoduli non
#                                 inclusi): le immagini sono PNG.
#   Dopo la compilazione si controlla che il binario non usi socket.
# BUILD_SHARED_LIBS=OFF: ggml e stable-diffusion sono compilati dentro sd-cli,
#   un solo file senza librerie private.
# La compilazione gira senza rete quando il sistema lo permette (unshare):
#   se una release nuova provasse a scaricare qualcosa, la build fallirebbe
#   invece di includerlo di nascosto.
# Flag di hardening di Debian da dpkg-buildflags.
CFLAGS_DEB="$(dpkg-buildflags --get CFLAGS)"
CXXFLAGS_DEB="$(dpkg-buildflags --get CXXFLAGS)"
LDFLAGS_DEB="$(dpkg-buildflags --get LDFLAGS)"
CPPFLAGS_DEB="$(dpkg-buildflags --get CPPFLAGS)"
VULKAN_FLAG=$([ "$BACKEND" = vulkan ] && echo ON || echo OFF)
# La firma della cache non dipende dalla cartella in cui si lavora
# (dpkg-buildflags aggiunge -ffile-prefix-map=<cartella corrente>=.).
FLAGS_FIRMA=$(printf '%s %s' "$CFLAGS_DEB" "$LDFLAGS_DEB" | sed 's/-ffile-prefix-map=[^ ]*//g')
OPZIONI="v=2 tag=$TAG commit=$COMMIT ggml=$GGML_COMMIT backend=$BACKEND native=OFF rpc=OFF web=OFF webp=OFF webm=OFF shared=OFF bins=$KEEP_BINARIES flags=$FLAGS_FIRMA"
FIRMA=$(printf '%s' "$OPZIONI" | sha256sum | cut -c1-16)
STAGE_CACHE="$CACHE/stage-${SD_NUMBER}-${BACKEND}-${FIRMA}"

if [ -f "$STAGE_CACHE/.completo" ]; then
    say "Uso la compilazione in cache ($BACKEND)"
else
    say "Compilo stable-diffusion.cpp $TAG ($BACKEND, $JOBS processi): ci vuole qualche minuto"
    BUILD="$CACHE/build-${SD_NUMBER}-${BACKEND}-${FIRMA}"
    rm -rf "$BUILD" "$STAGE_CACHE"
    mkdir -p "$BUILD"
    tar -xzf "$CACHED" -C "$BUILD"
    SORG=$(find "$BUILD" -maxdepth 2 -name CMakeLists.txt -printf '%h\n' | head -1)
    [ -n "$SORG" ] || die "CMakeLists.txt non trovato nell'archivio"
    # ggml al suo posto (la cartella del sottomodulo e' vuota nell'archivio).
    rm -rf "$SORG/ggml"
    mkdir -p "$SORG/ggml"
    tar -xzf "$GGML_CACHED" -C "$SORG/ggml" --strip-components=1
    [ -f "$SORG/ggml/CMakeLists.txt" ] || die "ggml non e' completo"

    # Librerie incluse: devono essere tutte dichiarate nel file copyright.
    for f in $(find "$SORG/thirdparty" -mindepth 1 -maxdepth 1 ! -name ".*" -printf '%f\n' | sort); do
        case " $(echo $TERZI_DICHIARATI) " in
            *" $f "*) ;;
            *) die "stable-diffusion.cpp $TAG ha un file nuovo: thirdparty/$f
        Se e' una libreria di altri autori va dichiarata nel file copyright in
        make-deb.sh e nelle specifiche (sezione 6), poi aggiunta a
        TERZI_DICHIARATI. Poi rilancia." ;;
        esac
    done

    # Versione e commit nel binario (sd-cli --version). CMake li chiede a
    # git, ma l'archivio non e' un repository: al posto di git gli si da'
    # uno script che risponde con il tag e il commit gia' verificati.
    cat > "$BUILD/git-versione" <<GITV
#!/bin/sh
case "\$1" in
    describe) echo "$TAG" ;;
    rev-parse) echo "${COMMIT:0:7}" ;;
    *) exit 1 ;;
esac
GITV
    chmod 755 "$BUILD/git-versione"

    SENZA_RETE=()
    if unshare -rn true 2>/dev/null; then
        SENZA_RETE=(unshare -rn)
    else
        avviso "unshare non disponibile: compilo senza isolare la rete"
    fi
    CFLAGS="$CFLAGS_DEB $CPPFLAGS_DEB" CXXFLAGS="$CXXFLAGS_DEB $CPPFLAGS_DEB" \
    LDFLAGS="$LDFLAGS_DEB" "${SENZA_RETE[@]}" cmake -S "$SORG" -B "$SORG/build" \
        -DCMAKE_BUILD_TYPE=Release \
        -DGIT_EXE="$BUILD/git-versione" \
        -DSD_VULKAN="$VULKAN_FLAG" \
        -DGGML_VULKAN="$VULKAN_FLAG" \
        -DGGML_NATIVE=OFF \
        -DBUILD_SHARED_LIBS=OFF \
        -DSD_BUILD_SHARED_LIBS=OFF \
        -DSD_BUILD_EXAMPLES=ON \
        -DSD_RPC=OFF \
        -DGGML_RPC=OFF \
        -DSD_WEBP=OFF \
        -DSD_WEBM=OFF \
        -DSD_SERVER_BUILD_FRONTEND=OFF
    # shellcheck disable=SC2086
    "${SENZA_RETE[@]}" cmake --build "$SORG/build" --config Release -j"$JOBS" --target $KEEP_BINARIES

    BIN=$(find "$SORG/build" -type f -name sd-cli -printf '%h\n' | head -1)
    [ -n "$BIN" ] || die "sd-cli non trovato dopo la compilazione"
    mkdir -p "$STAGE_CACHE/bin"
    for b in $KEEP_BINARIES; do
        install -m 755 "$BIN/$b" "$STAGE_CACHE/bin/"
    done
    mkdir -p "$STAGE_CACHE/licenses"
    cp "$SORG/LICENSE" "$STAGE_CACHE/licenses/LICENSE.stable-diffusion.cpp"
    cp "$SORG/ggml/LICENSE" "$STAGE_CACHE/licenses/LICENSE.ggml"
    cp "$SORG/thirdparty/LICENSE.darts_clone.txt" "$STAGE_CACHE/licenses/LICENSE.darts_clone"
    cp "$SORG/thirdparty/oniguruma/COPYING" "$STAGE_CACHE/licenses/LICENSE.oniguruma"
    cp "$SORG/thirdparty/utf8proc/LICENSE.md" "$STAGE_CACHE/licenses/LICENSE.utf8proc"
    touch "$STAGE_CACHE/.completo"
    rm -rf "$BUILD"
fi
[ -f "$STAGE_CACHE/bin/sd-cli" ] || die "sd-cli mancante nella compilazione"

# Niente rete nel binario: nessuna libreria TLS o HTTP, e nessuna funzione
# per aprire connessioni (socket, connect, ...) tra i simboli richiesti.
RETE=$(cd "$STAGE_CACHE/bin" && for f in *; do [ -L "$f" ] && continue
    LD_LIBRARY_PATH=. ldd "./$f" 2>/dev/null; done \
    | grep -oE 'lib(ssl|crypto|curl)[^ ]*' | sort -u || true)
[ -z "$RETE" ] || die "il motore e' collegato a librerie di rete: $RETE"
SOCKET=$(cd "$STAGE_CACHE/bin" && for f in *; do [ -L "$f" ] && continue
    nm -D --undefined-only "./$f" 2>/dev/null | awk -v f="$f" \
        '{ sub(/@.*/, "", $NF) }
         $NF ~ /^(socket|connect|bind|listen|accept|accept4|getaddrinfo|gethostbyname|sendto|recvfrom)$/ \
             { print f ":" $NF }'
    done | sort -u | tr '\n' ' ' || true)
[ -z "$SOCKET" ] || die "il motore contiene codice di rete: $SOCKET"
say "Nessun codice di rete nel binario"

# Prova vera: il motore parte, dice la sua versione ed elenca le schede.
# Sulla CPU (driver Vulkan nascosti), cosi' la prova non dipende dalla
# scheda grafica della macchina di build. Il sorgente non contiene un
# modello di prova: la generazione si prova con RuscaLLama.
SENZA_VK=(env VK_ICD_FILENAMES=/dev/null VK_DRIVER_FILES=/dev/null)
"${SENZA_VK[@]}" timeout 60 "$STAGE_CACHE/bin/sd-cli" --version >"$TMP/versione.log" 2>&1 \
    || { cat "$TMP/versione.log" >&2; die "sd-cli --version non funziona"; }
"${SENZA_VK[@]}" timeout 60 "$STAGE_CACHE/bin/sd-cli" --list-devices >"$TMP/schede.log" 2>&1 \
    || { cat "$TMP/schede.log" >&2; die "sd-cli --list-devices non funziona"; }
grep -qP '^\S+\t' "$TMP/schede.log" \
    || { cat "$TMP/schede.log" >&2; die "sd-cli --list-devices non scrive \"nome<TAB>descrizione\""; }
grep -qF "$TAG" "$TMP/versione.log" \
    || { cat "$TMP/versione.log" >&2; die "sd-cli --version non dice la versione $TAG"; }
say "sd-cli parte ($(head -1 "$TMP/versione.log" | cut -c1-80))"

# Le opzioni che RuscaLLama passa a sd-cli devono esistere.
AIUTO=$("${SENZA_VK[@]}" timeout 60 "$STAGE_CACHE/bin/sd-cli" --help 2>&1 || true)
MANCANO=""
for o in $OPZIONI_USATE; do
    # Here-string e non "printf | grep -q": con pipefail, grep -q che esce
    # alla prima riga trovata fa fallire printf (SIGPIPE) e l'opzione
    # risulterebbe mancante a caso.
    grep -qE -- "(^|[ ,])$o([ ,=]|\$)" <<< "$AIUTO" || MANCANO="$MANCANO $o"
done
[ -z "$MANCANO" ] || die "sd-cli di stable-diffusion.cpp $TAG non riconosce opzioni usate
        da RuscaLLama:$MANCANO
        Adatta rusca_diffusion.py, oppure costruisci una versione precedente:
        RUSCADIFFUSION_SD_VERSION=<numero> ./make-deb.sh"
say "sd-cli accetta tutte le opzioni usate da RuscaLLama"
if command -v readelf >/dev/null; then
    for f in "$STAGE_CACHE"/bin/*; do
        [ -L "$f" ] && continue
        RP=$(readelf -d "$f" 2>/dev/null | sed -n 's/.*R\(UN\)\?PATH.*\[\(.*\)\]/\2/p')
        [ -z "$RP" ] || [ "$RP" = "/$LIBDIR" ] || die "RUNPATH inatteso in $(basename "$f"): $RP"
    done
fi

# ── Albero del pacchetto ─────────────────────────────────────────────────────
ROOT="$TMP/${PKG}_${VER}_${ARCH}"
DOC="$ROOT/usr/share/doc/$PKG"
mkdir -p "$ROOT/DEBIAN" "$ROOT/$LIBDIR" "$DOC" \
         "$ROOT/etc/apparmor.d/force-complain" "$ROOT/usr/share/ruscadiffusion/models"
cp -a "$STAGE_CACHE/bin/." "$ROOT/$LIBDIR/"
# Simboli di debug fuori dal pacchetto.
find "$ROOT/$LIBDIR" -type f -exec \
    strip --strip-unneeded --remove-section=.comment --remove-section=.note {} \;

# Controllo delle librerie: se ne manca una il motore non parte e
# RuscaLLama vede solo "terminato (codice 127)". Meglio scoprirlo qui.
MANCANTI=$(cd "$ROOT/$LIBDIR" && for f in $KEEP_BINARIES; do
    [ -f "$f" ] && LD_LIBRARY_PATH=. ldd "./$f" 2>/dev/null; done \
    | grep 'not found' | awk '{print $1}' | sort -u || true)
[ -z "$MANCANTI" ] || die "librerie non risolte: $MANCANTI"

# Profilo AppArmor, in modalita' complain (vedi il commento nel profilo).
install -m 644 "apparmor/$PROFILE" "$ROOT/etc/apparmor.d/$PROFILE"
ln -s "../$PROFILE" "$ROOT/etc/apparmor.d/force-complain/$PROFILE"
if command -v apparmor_parser >/dev/null 2>&1; then
    apparmor_parser -Q -K "apparmor/$PROFILE" >/dev/null \
        || die "il profilo AppArmor non e' valido"
fi

# ── Documentazione ───────────────────────────────────────────────────────────
cat > "$DOC/README.md" <<README
# ruscadiffusion-engine $VER

Motore di generazione delle immagini del RuscaLinux OS Tool RuscaLLama.

**Componente esterno:** stable-diffusion.cpp $TAG — $UPSTREAM — licenza
MIT, copyright leejet; con la sua copia di ggml ($GGML_REPO, licenza MIT,
copyright The ggml authors). RuscaLinux lo compila dal sorgente senza
modifiche al codice.

| Voce | Valore |
|---|---|
| Versione di stable-diffusion.cpp | $TAG (ultima release al momento della build) |
| Data della release | ${DATA_RELEASE:-non nota} |
| Commit | $COMMIT |
| Commit di ggml | $GGML_COMMIT |
| SHA-256 dell'archivio sorgente | $OTTENUTO |
| SHA-256 dell'archivio di ggml | $OTTENUTO_GGML |
| Backend | $BACKEND |
| Ottimizzazioni per CPU specifica | no (GGML_NATIVE=OFF) |
| Rete | nessuna: niente server, niente RPC, nessun socket nel binario |
| Percorso | /$LIBDIR |
| Programmi | $KEEP_BINARIES |
| Modelli | ~/.local/share/ruscadiffusion/models/ e /usr/share/ruscadiffusion/models/ |

I modelli non fanno parte del pacchetto: sono file .safetensors, .gguf o
.ckpt (un file solo, come Stable Diffusion 1.5 e SDXL), oppure una cartella
con il modello di diffusione, il VAE e i codificatori di testo (come FLUX,
Stable Diffusion 3.5, Z-Image, Qwen-Image). Ogni modello ha la propria
licenza.

Il profilo AppArmor /etc/apparmor.d/$PROFILE e' in modalita' complain.

Per provare il motore dal terminale:

    /$LIBDIR/sd-cli --version
    /$LIBDIR/sd-cli --list-devices
    /$LIBDIR/sd-cli -m modello.safetensors -p "un gatto su un tetto" -o gatto.png
README
gzip -9n "$DOC/README.md"

cat > "$DOC/copyright" <<'COPYRIGHT'
Format: https://www.debian.org/doc/packaging-manuals/copyright-format/1.0/
Upstream-Name: stable-diffusion.cpp
Upstream-Contact: https://github.com/leejet/stable-diffusion.cpp/issues
Source: https://github.com/leejet/stable-diffusion.cpp
 https://github.com/leejet/ggml
Comment: ruscadiffusion-engine is stable-diffusion.cpp, an external component,
 built from unmodified source for RuscaLinux, with the copy of ggml that
 stable-diffusion.cpp records as its git submodule. Only the packaging
 (build script and AppArmor profile) is part of RuscaLinux. This file lists
 the code compiled into the packaged program (sd-cli). The full license
 texts of darts-clone, Oniguruma and utf8proc, as shipped with the source,
 are in LICENSE.darts_clone, LICENSE.oniguruma and LICENSE.utf8proc.

Files: *
Copyright: 2023-2026 leejet
License: MIT

Files: ggml/*
Copyright: 2023-2026 The ggml authors
License: MIT

Files: ggml/src/ggml-cpu/llamafile/*
Copyright: 2024 Mozilla Foundation
License: MIT

Files: ggml/src/ggml-cpu/ops.cpp
Copyright: 2023-2026 The ggml authors
 2023 Jeffrey Quesnelle and Bowen Peng (YaRN rotary embedding)
License: MIT

Files: thirdparty/json.hpp
Copyright: 2013-2022 Niels Lohmann
License: MIT

Files: thirdparty/zip.c thirdparty/zip.h
Copyright: Kuba Podgórski
License: Unlicense

Files: thirdparty/miniz.h
Copyright: 2013-2014 RAD Game Tools and Valve Software
 2010-2014 Rich Geldreich and Tenacious Software LLC
License: MIT

Files: thirdparty/darts.h
Copyright: 2008-2011 Susumu Yata
License: BSD-3-clause
Comment: darts-clone, from sentencepiece. Full text in LICENSE.darts_clone.

Files: thirdparty/stb_image.h thirdparty/stb_image_resize.h
 thirdparty/stb_image_write.h
Copyright: 2017 Sean Barrett
License: MIT
Comment: stb is offered as a choice of public domain (Unlicense) or MIT.

Files: thirdparty/oniguruma/*
Copyright: 2002-2021 K.Kosako
License: BSD-2-clause
Comment: Full text in LICENSE.oniguruma.

Files: thirdparty/utf8proc/*
Copyright: 2014-2021 Steven G. Johnson, Jiahao Chen, Tony Kelman,
 Jonas Fonseca and other contributors
 2009, 2013 Public Software Group e. V., Berlin, Germany
 1991-2007 Unicode, Inc. (Unicode data)
License: MIT and Unicode-DFS
Comment: Full text, with the Unicode data license, in LICENSE.utf8proc.

Files: debian/* etc/apparmor.d/*
Copyright: 2026 Nunzio Curcuruto
License: GPL-3+
Comment: Design, specifications and testing by the author; code written
 with the assistance of AI tools. See NOTA-IA.md in the RuscaLinux repository.

License: MIT
 Permission is hereby granted, free of charge, to any person obtaining a copy
 of this software and associated documentation files (the "Software"), to deal
 in the Software without restriction, including without limitation the rights
 to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
 copies of the Software, and to permit persons to whom the Software is
 furnished to do so, subject to the following conditions:
 .
 The above copyright notice and this permission notice shall be included in
 all copies or substantial portions of the Software.
 .
 THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
 IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
 FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
 AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
 LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
 OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
 SOFTWARE.

License: Unlicense
 This is free and unencumbered software released into the public domain.
 .
 Anyone is free to copy, modify, publish, use, compile, sell, or distribute
 this software, either in source code form or as a compiled binary, for any
 purpose, commercial or non-commercial, and by any means.
 .
 In jurisdictions that recognize copyright laws, the author or authors of
 this software dedicate any and all copyright interest in the software to the
 public domain. We make this dedication for the benefit of the public at
 large and to the detriment of our heirs and successors. We intend this
 dedication to be an overt act of relinquishment in perpetuity of all present
 and future rights to this software under copyright law.
 .
 THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
 IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
 FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
 AUTHORS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN
 ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION
 WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.

License: BSD-2-clause
 Redistribution and use in source and binary forms, with or without
 modification, are permitted provided that the following conditions are met:
 .
 1. Redistributions of source code must retain the above copyright notice,
    this list of conditions and the following disclaimer.
 2. Redistributions in binary form must reproduce the above copyright notice,
    this list of conditions and the following disclaimer in the documentation
    and/or other materials provided with the distribution.
 .
 THIS SOFTWARE IS PROVIDED BY THE AUTHOR AND CONTRIBUTORS "AS IS" AND ANY
 EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED
 WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
 DISCLAIMED. IN NO EVENT SHALL THE AUTHOR OR CONTRIBUTORS BE LIABLE FOR ANY
 DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES
 (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES;
 LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND
 ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
 (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS
 SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.

License: BSD-3-clause
 Redistribution and use in source and binary forms, with or without
 modification, are permitted provided that the following conditions are met:
 .
 - Redistributions of source code must retain the above copyright notice,
   this list of conditions and the following disclaimer.
 - Redistributions in binary form must reproduce the above copyright notice,
   this list of conditions and the following disclaimer in the documentation
   and/or other materials provided with the distribution.
 - Neither the name of the <ORGANIZATION> nor the names of its contributors
   may be used to endorse or promote products derived from this software
   without specific prior written permission.
 .
 THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
 AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
 IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE
 ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT OWNER OR CONTRIBUTORS BE
 LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR
 CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF
 SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS
 INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN
 CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE)
 ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE
 POSSIBILITY OF SUCH DAMAGE.

License: MIT and Unicode-DFS
 See LICENSE.utf8proc in this directory: the utf8proc code is under the MIT
 license above, its Unicode data tables under the Unicode data license
 reproduced in that file.

License: GPL-3+
 This program is free software: you can redistribute it and/or modify it
 under the terms of the GNU General Public License as published by the Free
 Software Foundation, either version 3 of the License, or (at your option)
 any later version.
 .
 On Debian systems, the complete text of the GNU General Public License
 version 3 can be found in "/usr/share/common-licenses/GPL-3".
COPYRIGHT
for l in "$STAGE_CACHE"/licenses/LICENSE.*; do
    install -m 644 "$l" "$DOC/$(basename "$l")"
done

cat <<CHANGELOG | gzip -9n > "$DOC/changelog.gz"
$PKG ($VER) unstable; urgency=medium

  * Primo pacchetto: stable-diffusion.cpp $TAG (commit ${COMMIT:0:12}, ggml
    ${GGML_COMMIT:0:12}) compilato dal sorgente (backend $BACKEND), con le
    stesse regole di ruscawhisper-engine.
  * Solo sd-cli: niente server, niente RPC, nessun socket nel binario
    (controllato dalla build).
  * Controllo che sd-cli accetti le opzioni usate da RuscaLLama e che parta.
  * Binario in /$LIBDIR; profilo AppArmor in complain.

 -- $MAINT  $(LC_ALL=C date -Ru -d "@$SOURCE_DATE_EPOCH")
CHANGELOG

# ── Dipendenze calcolate dal binario ─────────────────────────────────────────
mkdir -p "$TMP/shlib/debian"
printf 'Source: %s\n\nPackage: %s\nArchitecture: %s\n' "$PKG" "$PKG" "$ARCH" \
    > "$TMP/shlib/debian/control"
SHLIBS=$(cd "$TMP/shlib" && dpkg-shlibdeps -O -l"$ROOT/$LIBDIR" \
    $(for b in $KEEP_BINARIES; do printf ' -e%s' "$ROOT/$LIBDIR/$b"; done) 2>/dev/null \
    | sed -n 's/^shlibs:Depends=//p')
[ -n "$SHLIBS" ] || die "dpkg-shlibdeps non ha calcolato le dipendenze"
RECOMMENDS="apparmor"
[ "$BACKEND" = vulkan ] && RECOMMENDS="mesa-vulkan-drivers, $RECOMMENDS"

cat > "$ROOT/DEBIAN/control" <<CONTROL
Package: $PKG
Version: $VER
Section: graphics
Priority: optional
Architecture: $ARCH
Depends: $SHLIBS
Recommends: $RECOMMENDS
Maintainer: $MAINT
Homepage: $HOMEPAGE
Installed-Size: $(du -sk --exclude=DEBIAN "$ROOT" | cut -f1)
Description: image generation engine for RuscaLLama
 Runs local image generation models (Stable Diffusion, SDXL, FLUX, SD 3.5,
 Z-Image, Qwen-Image and others, as .safetensors or .gguf files) for the
 RuscaLinux OS Tool RuscaLLama. Contains sd-cli.
 .
 This is stable-diffusion.cpp $TAG, an external component (MIT license,
 $UPSTREAM), built from unmodified source with the
 $BACKEND backend. It has no network code: no server, no RPC and no
 downloads, models are files copied by the user. Vulkan covers NVIDIA, AMD
 and Intel graphics with one binary and falls back to the CPU.
CONTROL

cat > "$ROOT/DEBIAN/conffiles" <<CONFFILES
/etc/apparmor.d/$PROFILE
CONFFILES

cat > "$ROOT/DEBIAN/postinst" <<POSTINST
#!/bin/sh
set -e
if [ "\$1" = "configure" ] && command -v apparmor_parser >/dev/null 2>&1 \\
        && aa-enabled --quiet 2>/dev/null; then
    apparmor_parser -r -T -W /etc/apparmor.d/$PROFILE || true
fi
POSTINST
cat > "$ROOT/DEBIAN/postrm" <<POSTRM
#!/bin/sh
set -e
if [ "\$1" = "remove" ] && command -v apparmor_parser >/dev/null 2>&1; then
    apparmor_parser -R /etc/apparmor.d/$PROFILE 2>/dev/null || true
fi
POSTRM
chmod 755 "$ROOT/DEBIAN/postinst" "$ROOT/DEBIAN/postrm"
find "$ROOT" -type d -exec chmod 755 {} +

# ── Costruzione ──────────────────────────────────────────────────────────────
DEB_FILE="${PKG}-ruscalinux_${VER}_${ARCH}.deb"
dpkg-deb --root-owner-group -Zxz --build "$ROOT" "$OUT_DIR/$DEB_FILE" >/dev/null
( cd "$OUT_DIR" && sha256sum "$DEB_FILE" > SHA256SUMS )
say "Pronto: build-deb/$DEB_FILE ($(du -h "$OUT_DIR/$DEB_FILE" | cut -f1)), stable-diffusion.cpp $TAG, $BACKEND"

# Cache: restano solo sorgente e compilazione della versione appena usata.
find "$CACHE/src" -maxdepth 1 -name 'stable-diffusion.cpp-master-*.tar.gz' ! -name "$ARCHIVE" -delete 2>/dev/null || true
find "$CACHE/src" -maxdepth 1 -name 'ggml-*.tar.gz' ! -name "$GGML_ARCHIVE" -delete 2>/dev/null || true
find "$CACHE" -maxdepth 1 -type d \( -name 'stage-*' -o -name 'build-*' \) \
     ! -name "stage-${SD_NUMBER}-*" -exec rm -rf {} + 2>/dev/null || true
if command -v lintian >/dev/null 2>&1; then
    lintian "$OUT_DIR/$DEB_FILE" || true
fi
