#!/bin/bash
# ---------------------------------------------------------------------------
# RuscaLinux — costruisce il pacchetto ruscawhisper-engine.
#
#   ./make-deb.sh
#
# ruscawhisper-engine e' il motore di riconoscimento vocale di RuscaDubbing.
# E' whisper.cpp, SOFTWARE ESTERNO (licenza MIT,
# https://github.com/ggml-org/whisper.cpp), compilato dal sorgente con il
# backend Vulkan: un solo binario per NVIDIA, AMD e Intel, che ripiega sulla
# CPU quando non trova una scheda. E' fatto come ruscallama-engine
# (llama.cpp): stesse regole, stessi controlli.
#
# Regole delle specifiche dei RuscaLinux OS Tools:
#   * versione del pacchetto = versione di RuscaLinux (release.conf);
#     la versione di whisper.cpp e' scritta nella descrizione e nella
#     documentazione del pacchetto;
#   * un solo .deb in build-deb/, con suffisso -ruscalinux e SHA256SUMS;
#   * architettura amd64: e' codice compilato, non Python.
#
# Quale whisper.cpp: l'ultima release stabile pubblicata su GitHub, trovata
# da ultima-versione.sh. Il sorgente viene controllato in due modi:
#   * il commit scritto nell'archivio deve essere quello del tag su GitHub;
#   * l'impronta SHA-256 dell'archivio viene registrata in checksums/ la
#     prima volta che una versione viene costruita, e le build successive
#     della stessa versione devono trovare lo stesso archivio. Il file nuovo
#     in checksums/ va aggiunto al repository (git add).
# Dopo la compilazione si controlla che whisper-cli accetti tutte le opzioni
# usate da RuscaDubbing (OPZIONI_USATE, qui sotto), che i binari non abbiano
# codice di rete e che il motore trascriva davvero un audio di prova.
#
# Si impacchetta solo whisper-cli (piu' whisper-bench per misurare): un
# programma che legge un file audio e scrive un file di testo. Niente
# whisper-server: RuscaDubbing non apre porte, nemmeno su 127.0.0.1.
#
# Il risultato della compilazione viene tenuto in una cache
# (~/.cache/ruscalinux/ruscawhisper-engine) e riusato finche' non cambiano
# versione di whisper.cpp, backend o opzioni: le build successive della ISO
# rifanno solo il pacchetto, in pochi secondi.
#
# Variabili utili (facoltative):
#   RUSCAWHISPER_WHISPER_VERSION=1.9.4
#                             costruisce quella versione invece dell'ultima
#   GITHUB_TOKEN=<token>      alza il limite di richieste all'API di GitHub
#   RUSCAWHISPER_BACKEND=cpu  compila senza Vulkan (prove, macchine senza GPU)
#   RUSCAWHISPER_CACHE=<dir>  cartella della cache
#   RUSCAWHISPER_JOBS=<n>     processi di compilazione (default: nproc)
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
# La versione di whisper.cpp non e' scritta qui: e' l'ultima release stabile,
# o quella di RUSCAWHISPER_WHISPER_VERSION (vedi ultima-versione.sh).

# Una release piu' giovane di cosi' viene costruita lo stesso, ma con un
# avviso: le prime correzioni di una release arrivano di solito nei primi
# giorni. Prima di pubblicare la ISO, prova RuscaDubbing.
GIORNI_MINIMI=14

# Opzioni di whisper-cli usate da RuscaDubbing (rusca_whisper.py). Se una
# release non ne riconosce una, il motore non partirebbe: la build si ferma.
# Aggiornare l'elenco quando il programma comincia a usare un'opzione nuova.
OPZIONI_USATE="-m -f -l -t -oj -of -pp -ng"

# File di examples/ (la cartella da cui si compilano whisper-cli e
# whisper-bench). I primi sono di whisper.cpp; i secondi sono librerie di
# altri autori. Se una release aggiunge un file che non e' in nessuno dei
# due elenchi, la build si ferma: se e' una libreria inclusa va dichiarata
# nel file copyright qui sotto e nelle specifiche (sezione 6).
#   miniaudio.h, stb_vorbis.c  compilati in whisper-cli (lettura dell'audio)
#   json.hpp                   usato solo da programmi che non impacchettiamo
SORGENTI_WHISPER="common.cpp common.h common-ggml.cpp common-ggml.h
  common-sdl.cpp common-sdl.h common-whisper.cpp common-whisper.h
  ffmpeg-transcode.cpp grammar-parser.cpp grammar-parser.h"
TERZI_DICHIARATI="json.hpp miniaudio.h stb_vorbis.c"

PKG="ruscawhisper-engine"
ARCH="amd64"
MAINT="Nunzio Curcuruto <info@ruscalinux.org>"
HOMEPAGE="https://www.ruscalinux.org/"
UPSTREAM="https://github.com/ggml-org/whisper.cpp"
BACKEND="${RUSCAWHISPER_BACKEND:-vulkan}"
JOBS="${RUSCAWHISPER_JOBS:-$(nproc)}"
CACHE="${RUSCAWHISPER_CACHE:-${XDG_CACHE_HOME:-$HOME/.cache}/ruscalinux/ruscawhisper-engine}"
SOURCE_DATE_EPOCH="${SOURCE_DATE_EPOCH:-$(date +%s)}"

LIBDIR="usr/lib/${PKG}"            # binari e librerie private
PROFILE="usr.lib.ruscawhisper-engine.whisper-cli"

# Solo questi finiscono nel pacchetto: whisper-cli per RuscaDubbing (e per
# il terminale), whisper-bench per misurare la velocita' di un modello.
KEEP_BINARIES="whisper-cli whisper-bench"

die() { echo "ERRORE: $*" >&2; exit 1; }
say() { echo "==> $*"; }

avviso() { echo "ATTENZIONE: $*" >&2; }

case "$BACKEND" in vulkan|cpu) ;; *) die "RUSCAWHISPER_BACKEND deve essere vulkan o cpu";; esac
[ -f ultima-versione.sh ] || die "manca ultima-versione.sh"
[ -f "apparmor/$PROFILE" ] || die "manca il profilo apparmor/$PROFILE"

# ── Controllo delle dipendenze, prima di scaricare o compilare ──────────────
MANCA=""
for c in dpkg-deb dpkg-shlibdeps cmake g++ make pkg-config strip nm; do
    command -v "$c" >/dev/null || MANCA="$MANCA $c"
done
command -v wget >/dev/null || command -v curl >/dev/null || MANCA="$MANCA wget"
# git serve a leggere il commit dentro l'archivio e quello del tag su GitHub.
command -v git >/dev/null || MANCA="$MANCA git"
if [ "$BACKEND" = vulkan ]; then
    pkg-config --exists vulkan 2>/dev/null || MANCA="$MANCA libvulkan-dev"
    command -v glslc >/dev/null || MANCA="$MANCA glslc"
    find /usr -name 'SPIRV-HeadersConfig.cmake' -print -quit 2>/dev/null | grep -q . \
        || MANCA="$MANCA spirv-headers"
fi
if [ -n "$MANCA" ]; then
    echo "ERRORE: mancano strumenti per compilare whisper.cpp:$MANCA" >&2
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

# ── Quale versione ───────────────────────────────────────────────────────────
PUBBLICATA=""
if RIGA=$(bash ./ultima-versione.sh); then
    TAG="${RIGA%% *}"
    [ "$RIGA" != "$TAG" ] && PUBBLICATA="${RIGA#* }"
else
    [ $? -eq 2 ] && die "versione di whisper.cpp non valida (RUSCAWHISPER_WHISPER_VERSION)"
    # Niente rete: si usa la versione piu' recente gia' scaricata e
    # registrata, cosi' una build senza connessione resta possibile.
    TAG=$(ls "$CACHE/src" 2>/dev/null \
          | sed -n 's/^whisper\.cpp-\(v[0-9]*\.[0-9]*\.[0-9]*\)\.tar\.gz$/\1/p' \
          | while read -r t; do [ -f "checksums/whisper.cpp-$t.tar.gz.sha256" ] && echo "$t"; done \
          | sort -V | tail -1) || true
    [ -n "$TAG" ] || die "non so quale whisper.cpp costruire: niente rete e niente in cache"
    avviso "non riesco a sapere quale sia l'ultima release di whisper.cpp:
            uso $TAG, gia' scaricata. Potrebbe non essere l'ultima."
fi
WHISPER_CPP_VERSION="${TAG#v}"
ARCHIVE="whisper.cpp-${TAG}.tar.gz"
URL="https://codeload.github.com/ggml-org/whisper.cpp/tar.gz/refs/tags/${TAG}"
GIT_URL="https://github.com/ggml-org/whisper.cpp.git"
PIN="$SRC_DIR/checksums/${ARCHIVE}.sha256"
say "whisper.cpp $TAG"

# ── Sorgente: cache locale o download, poi due controlli ────────────────────
CACHED="$CACHE/src/$ARCHIVE"
if [ ! -f "$CACHED" ]; then
    say "Scarico whisper.cpp $TAG"
    if command -v wget >/dev/null; then
        wget -q -O "$TMP/$ARCHIVE" "$URL" || die "download non riuscito ($URL)"
    else
        curl -sfL -o "$TMP/$ARCHIVE" "$URL" || die "download non riuscito ($URL)"
    fi
    mv "$TMP/$ARCHIVE" "$CACHED"
fi

# 1. Il commit dentro l'archivio (GitHub lo scrive nell'intestazione del tar)
#    deve essere quello a cui punta il tag. I tag di whisper.cpp sono
#    annotati: conta il commit puntato (riga ^{}), non l'oggetto tag.
COMMIT=$(gzip -dc "$CACHED" | git get-tar-commit-id 2>/dev/null || true)
[ -n "$COMMIT" ] || { rm -f "$CACHED"; die "l'archivio di whisper.cpp $TAG non contiene il commit: scaricato male?"; }
REMOTO=$(timeout 60 git ls-remote "$GIT_URL" "refs/tags/$TAG" "refs/tags/$TAG^{}" 2>/dev/null || true)
COMMIT_TAG=$(printf '%s\n' "$REMOTO" | awk '/\^\{\}$/ {print $1}')
[ -n "$COMMIT_TAG" ] || COMMIT_TAG=$(printf '%s\n' "$REMOTO" | awk 'NF {print $1; exit}')
if [ -n "$COMMIT_TAG" ]; then
    if [ "$COMMIT" != "$COMMIT_TAG" ]; then
        rm -f "$CACHED"
        die "l'archivio di whisper.cpp $TAG non corrisponde al tag su GitHub
        commit nell'archivio: $COMMIT
        commit del tag:       $COMMIT_TAG
        Il file e' stato cancellato dalla cache: rilancia per riscaricarlo."
    fi
elif [ ! -f "$PIN" ]; then
    die "non riesco a leggere il tag $TAG su GitHub, e la versione non e' registrata
        in checksums/: non posso verificare il sorgente."
fi

# 2. Impronta: registrata la prima volta, confrontata le volte successive.
OTTENUTO=$(sha256sum "$CACHED" | cut -d' ' -f1)
if [ -f "$PIN" ]; then
    ATTESO=$(cut -d' ' -f1 < "$PIN")
    if [ "$ATTESO" != "$OTTENUTO" ]; then
        rm -f "$CACHED"
        die "l'archivio di whisper.cpp $TAG non corrisponde all'impronta registrata
        atteso:   $ATTESO
        ottenuto: $OTTENUTO
        Il file e' stato cancellato dalla cache: rilancia per riscaricarlo.
        Se si ripete, il tag $TAG e' stato cambiato su GitHub: controlla prima
        di cancellare checksums/$ARCHIVE.sha256."
    fi
else
    echo "$OTTENUTO  $ARCHIVE" > "$PIN"
    avviso "whisper.cpp $TAG e' una versione nuova: impronta registrata in
            tools/ruscawhisper-engine/checksums/$ARCHIVE.sha256
            Aggiungila al repository (git add) insieme alla prossima modifica."
fi
say "Sorgente whisper.cpp $TAG verificato (commit ${COMMIT:0:12})"

# Eta' della release: data di pubblicazione se nota, altrimenti la data del
# commit, che il tar porta in ogni file.
if [ -n "$PUBBLICATA" ]; then
    DATA_RELEASE=$(date -u -d "$PUBBLICATA" +%Y-%m-%d 2>/dev/null || true)
else
    DATA_RELEASE=$(TZ=UTC tar -tvzf "$CACHED" --full-time 2>/dev/null | awk 'NR==1 {print $4}')
fi
if [ -n "$DATA_RELEASE" ]; then
    GIORNI=$(( ( $(date -u +%s) - $(date -u -d "$DATA_RELEASE" +%s) ) / 86400 ))
    say "Release del $DATA_RELEASE ($GIORNI giorni fa)"
    if [ "$GIORNI" -lt "$GIORNI_MINIMI" ]; then
        avviso "whisper.cpp $TAG e' uscita da $GIORNI giorni (meno di $GIORNI_MINIMI).
            Prova RuscaDubbing prima di pubblicare la ISO;
            per costruire la versione precedente:
            RUSCAWHISPER_WHISPER_VERSION=<versione> ./make-deb.sh"
    fi
fi

# ── Compilazione (o riuso della cache) ───────────────────────────────────────
# GGML_NATIVE=OFF: il binario deve girare su qualunque x86-64 recente, non
#   solo sulla macchina che costruisce la ISO.
# Niente rete (specifiche, privacy): i modelli arrivano solo dai file
#   copiati dall'utente. whisper-cli non ha codice di rete; per non
#   portarne dentro da altre parti:
#   WHISPER_BUILD_SERVER=OFF  niente whisper-server (cpp-httplib);
#   WHISPER_CURL=OFF          niente libcurl;
#   WHISPER_SDL2=OFF          niente microfono: si trascrivono solo file;
#   WHISPER_COMMON_FFMPEG=OFF video e altri formati li converte RuscaDubbing
#                             con il comando ffmpeg di Debian, senza
#                             collegare il motore alle librerie di FFmpeg.
#   Dopo la compilazione si controlla che i binari non usino socket.
# WHISPER_BUILD_IS_DEV=OFF e WHISPER_BUILD_COMMIT: l'archivio non e' un
#   repository git, e senza queste whisper-cli --version direbbe "X.Y.Z-dev".
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
OPZIONI="tag=$TAG commit=$COMMIT backend=$BACKEND native=OFF server=OFF curl=OFF sdl=OFF ffmpeg=OFF shared=ON flags=$FLAGS_FIRMA"
FIRMA=$(printf '%s' "$OPZIONI" | sha256sum | cut -c1-16)
STAGE_CACHE="$CACHE/stage-${WHISPER_CPP_VERSION}-${BACKEND}-${FIRMA}"

if [ -f "$STAGE_CACHE/.completo" ]; then
    say "Uso la compilazione in cache ($BACKEND)"
else
    say "Compilo whisper.cpp $TAG ($BACKEND, $JOBS processi): ci vuole qualche minuto"
    BUILD="$CACHE/build-${WHISPER_CPP_VERSION}-${BACKEND}-${FIRMA}"
    rm -rf "$BUILD" "$STAGE_CACHE"
    mkdir -p "$BUILD"
    tar -xzf "$CACHED" -C "$BUILD"
    SORG=$(find "$BUILD" -maxdepth 2 -name CMakeLists.txt -printf '%h\n' | head -1)
    [ -n "$SORG" ] || die "CMakeLists.txt non trovato nell'archivio"

    # Librerie incluse: devono essere tutte dichiarate nel file copyright.
    for f in $(find "$SORG/examples" -maxdepth 1 -type f \
                    \( -name '*.c' -o -name '*.cpp' -o -name '*.h' -o -name '*.hpp' \) \
                    -printf '%f\n' | sort); do
        case " $(echo $SORGENTI_WHISPER $TERZI_DICHIARATI) " in
            *" $f "*) ;;
            *) die "whisper.cpp $TAG ha un file nuovo: examples/$f
        Se e' di whisper.cpp aggiungilo a SORGENTI_WHISPER. Se e' una libreria
        di altri autori aggiungila a TERZI_DICHIARATI, al file copyright in
        make-deb.sh e alle specifiche (sezione 6), poi rilancia." ;;
        esac
    done

    SENZA_RETE=()
    if unshare -rn true 2>/dev/null; then
        SENZA_RETE=(unshare -rn)
    else
        avviso "unshare non disponibile: compilo senza isolare la rete"
    fi
    CFLAGS="$CFLAGS_DEB $CPPFLAGS_DEB" CXXFLAGS="$CXXFLAGS_DEB $CPPFLAGS_DEB" \
    LDFLAGS="$LDFLAGS_DEB" "${SENZA_RETE[@]}" cmake -S "$SORG" -B "$SORG/build" \
        -DCMAKE_BUILD_TYPE=Release \
        -DGGML_VULKAN="$VULKAN_FLAG" \
        -DGGML_NATIVE=OFF \
        -DBUILD_SHARED_LIBS=ON \
        -DWHISPER_BUILD_EXAMPLES=ON \
        -DWHISPER_BUILD_SERVER=OFF \
        -DWHISPER_BUILD_TESTS=OFF \
        -DWHISPER_CURL=OFF \
        -DWHISPER_SDL2=OFF \
        -DWHISPER_COMMON_FFMPEG=OFF \
        -DWHISPER_BUILD_IS_DEV=OFF \
        -DWHISPER_BUILD_COMMIT="${COMMIT:0:7}" \
        -DCMAKE_BUILD_WITH_INSTALL_RPATH=ON \
        -DCMAKE_INSTALL_RPATH="/${LIBDIR}"
    # shellcheck disable=SC2086
    "${SENZA_RETE[@]}" cmake --build "$SORG/build" --config Release -j"$JOBS" --target $KEEP_BINARIES

    BIN=$(find "$SORG/build" -type f -name whisper-cli -printf '%h\n' | head -1)
    [ -n "$BIN" ] || die "whisper-cli non trovato dopo la compilazione"
    mkdir -p "$STAGE_CACHE/bin"
    # cp -a conserva i collegamenti simbolici delle librerie (libwhisper.so.1
    # -> libwhisper.so.1.x.y) invece di duplicarle.
    for d in "$BIN" "$SORG/build/src" "$SORG/build/ggml/src" "$SORG/build/lib"; do
        [ -d "$d" ] && cp -a "$d"/*.so* "$STAGE_CACHE/bin/" 2>/dev/null || true
    done
    for b in $KEEP_BINARIES; do
        [ -f "$BIN/$b" ] && install -m 755 "$BIN/$b" "$STAGE_CACHE/bin/"
    done
    mkdir -p "$STAGE_CACHE/licenses"
    cp "$SORG/LICENSE" "$STAGE_CACHE/licenses/LICENSE.whisper.cpp"

    # Prova vera, al posto di quella manuale: il motore appena compilato
    # trascrive l'audio di prova del sorgente con il modello di prova (un
    # modello senza pesi: il testo e' vuoto, ma si percorre tutta la strada,
    # dalla lettura dell'audio alla scrittura del JSON). Sulla CPU, cosi' la
    # prova non dipende dalla scheda grafica della macchina di build.
    if [ -f "$SORG/samples/jfk.wav" ] && [ -f "$SORG/models/for-tests-ggml-tiny.bin" ]; then
        LD_LIBRARY_PATH="$STAGE_CACHE/bin" VK_ICD_FILENAMES=/dev/null VK_DRIVER_FILES=/dev/null \
            timeout 300 "$STAGE_CACHE/bin/whisper-cli" -ng -t 2 -l auto -pp -oj \
            -m "$SORG/models/for-tests-ggml-tiny.bin" -f "$SORG/samples/jfk.wav" \
            -of "$TMP/prova" >"$TMP/prova.log" 2>&1 \
            || { tail -n 20 "$TMP/prova.log" >&2; die "whisper-cli non riesce a trascrivere l'audio di prova"; }
        grep -q '"transcription"' "$TMP/prova.json" 2>/dev/null \
            || die "whisper-cli non ha scritto il JSON della trascrizione di prova"
        say "whisper-cli ha trascritto l'audio di prova"
    else
        avviso "audio o modello di prova non trovati nel sorgente: prova saltata"
    fi
    touch "$STAGE_CACHE/.completo"
    rm -rf "$BUILD"
fi
[ -f "$STAGE_CACHE/bin/whisper-cli" ] || die "whisper-cli mancante nella compilazione"

# Niente rete nei binari: nessuna libreria TLS o HTTP, e nessuna funzione
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
say "Nessun codice di rete nei binari"

# Le opzioni che RuscaDubbing passa a whisper-cli devono esistere.
AIUTO=$(LD_LIBRARY_PATH="$STAGE_CACHE/bin" VK_ICD_FILENAMES=/dev/null \
        VK_DRIVER_FILES=/dev/null timeout 60 "$STAGE_CACHE/bin/whisper-cli" --help 2>&1 || true)
MANCANO=""
for o in $OPZIONI_USATE; do
    # Here-string e non "printf | grep -q": con pipefail, grep -q che esce
    # alla prima riga trovata fa fallire printf (SIGPIPE) e l'opzione
    # risulterebbe mancante a caso.
    grep -qE -- "(^|[ ,])$o([ ,=]|\$)" <<< "$AIUTO" || MANCANO="$MANCANO $o"
done
[ -z "$MANCANO" ] || die "whisper-cli di whisper.cpp $TAG non riconosce opzioni usate
        da RuscaDubbing:$MANCANO
        Adatta il programma, oppure costruisci la versione precedente:
        RUSCAWHISPER_WHISPER_VERSION=<versione> ./make-deb.sh"
say "whisper-cli accetta tutte le opzioni usate da RuscaDubbing"
# Le librerie si cercano solo nella cartella privata del pacchetto: un
# percorso della macchina di build nei binari sarebbe un errore.
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
         "$ROOT/etc/apparmor.d/force-complain" "$ROOT/usr/share/ruscawhisper/models"
cp -a "$STAGE_CACHE/bin/." "$ROOT/$LIBDIR/"
# Simboli di debug fuori dal pacchetto.
find "$ROOT/$LIBDIR" -type f \( -name '*.so*' -o -perm -u+x \) -exec \
    strip --strip-unneeded --remove-section=.comment --remove-section=.note {} \;
find "$ROOT/$LIBDIR" -type f -name '*.so*' -exec chmod 644 {} \;

# Controllo delle librerie: se ne manca una il motore non parte e
# RuscaDubbing vede solo "terminato (codice 127)". Meglio scoprirlo qui.
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
# ruscawhisper-engine $VER

Motore di riconoscimento vocale del RuscaLinux OS Tool RuscaDubbing.

**Componente esterno:** whisper.cpp $TAG — $UPSTREAM — licenza MIT,
copyright The ggml authors. RuscaLinux lo compila dal sorgente senza
modifiche al codice.

| Voce | Valore |
|---|---|
| Versione di whisper.cpp | $WHISPER_CPP_VERSION (ultima release stabile al momento della build) |
| Data della release | ${DATA_RELEASE:-non nota} |
| Commit | $COMMIT |
| SHA-256 dell'archivio sorgente | $OTTENUTO |
| Backend | $BACKEND |
| Ottimizzazioni per CPU specifica | no (GGML_NATIVE=OFF) |
| Rete | nessuna: niente server, niente libcurl, nessun socket nei binari |
| Percorso | /$LIBDIR |
| Programmi | $KEEP_BINARIES |
| Modelli | ~/.local/share/ruscawhisper/models/ e /usr/share/ruscawhisper/models/ |

I modelli non fanno parte del pacchetto: sono file ggml (.bin) come
ggml-large-v3-turbo.bin, da copiare in una delle due cartelle. Ogni modello
ha la propria licenza.

Il profilo AppArmor /etc/apparmor.d/$PROFILE e' in modalita' complain.

Per provare il motore dal terminale (audio WAV, MP3, FLAC o Ogg):

    /$LIBDIR/whisper-cli --version
    /$LIBDIR/whisper-cli -m modello.bin -l it -f audio.wav
    /$LIBDIR/whisper-bench -m modello.bin
README
gzip -9n "$DOC/README.md"

cat > "$DOC/copyright" <<'COPYRIGHT'
Format: https://www.debian.org/doc/packaging-manuals/copyright-format/1.0/
Upstream-Name: whisper.cpp
Upstream-Contact: https://github.com/ggml-org/whisper.cpp/issues
Source: https://github.com/ggml-org/whisper.cpp
Comment: ruscawhisper-engine is whisper.cpp, an external component, built
 from unmodified source for RuscaLinux. Only the packaging (build script and
 AppArmor profile) is part of RuscaLinux. This file lists the code compiled
 into the packaged programs (whisper-cli, whisper-bench and their libraries).

Files: *
Copyright: 2023-2026 The ggml authors
License: MIT

Files: ggml/src/ggml-cpu/llamafile/*
Copyright: 2024 Mozilla Foundation
License: MIT

Files: ggml/src/ggml-cpu/ops.cpp
Copyright: 2023-2026 The ggml authors
 2023 Jeffrey Quesnelle and Bowen Peng (YaRN rotary embedding)
License: MIT

Files: examples/miniaudio.h
Copyright: 2025 David Reid
License: MIT-0
Comment: miniaudio is offered as a choice of public domain (Unlicense) or
 MIT No Attribution.

Files: examples/stb_vorbis.c
Copyright: 2017 Sean Barrett
License: MIT
Comment: stb_vorbis is offered as a choice of public domain (Unlicense) or
 MIT.

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

License: MIT-0
 Permission is hereby granted, free of charge, to any person obtaining a copy
 of this software and associated documentation files (the "Software"), to deal
 in the Software without restriction, including without limitation the rights
 to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
 copies of the Software, and to permit persons to whom the Software is
 furnished to do so.
 .
 THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
 IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
 FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
 AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
 LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
 OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
 SOFTWARE.

License: GPL-3+
 This program is free software: you can redistribute it and/or modify it
 under the terms of the GNU General Public License as published by the Free
 Software Foundation, either version 3 of the License, or (at your option)
 any later version.
 .
 On Debian systems, the complete text of the GNU General Public License
 version 3 can be found in "/usr/share/common-licenses/GPL-3".
COPYRIGHT
install -m 644 "$STAGE_CACHE/licenses/LICENSE.whisper.cpp" "$DOC/LICENSE.whisper.cpp"

cat <<CHANGELOG | gzip -9n > "$DOC/changelog.gz"
$PKG ($VER) unstable; urgency=medium

  * Primo pacchetto: whisper.cpp $TAG (ultima release stabile, commit
    ${COMMIT:0:12}) compilato dal sorgente (backend $BACKEND), con le
    stesse regole di ruscallama-engine.
  * Solo whisper-cli e whisper-bench: niente server, niente libcurl,
    nessun socket nei binari (controllato dalla build).
  * Controllo che whisper-cli accetti le opzioni usate da RuscaDubbing e
    che trascriva l'audio di prova.
  * Binari e librerie in /$LIBDIR; profilo AppArmor in complain.

 -- $MAINT  $(LC_ALL=C date -Ru -d "@$SOURCE_DATE_EPOCH")
CHANGELOG

# ── Dipendenze calcolate dai binari ──────────────────────────────────────────
mkdir -p "$TMP/shlib/debian"
printf 'Source: %s\n\nPackage: %s\nArchitecture: %s\n' "$PKG" "$PKG" "$ARCH" \
    > "$TMP/shlib/debian/control"
SHLIBS=$(cd "$TMP/shlib" && dpkg-shlibdeps -O -l"$ROOT/$LIBDIR" \
    -e"$ROOT/$LIBDIR/whisper-cli" -e"$ROOT/$LIBDIR/whisper-bench" \
    $(find "$ROOT/$LIBDIR" -type f -name '*.so*' -printf ' -e%p') 2>/dev/null \
    | sed -n 's/^shlibs:Depends=//p')
[ -n "$SHLIBS" ] || die "dpkg-shlibdeps non ha calcolato le dipendenze"
RECOMMENDS="apparmor"
[ "$BACKEND" = vulkan ] && RECOMMENDS="mesa-vulkan-drivers, $RECOMMENDS"

cat > "$ROOT/DEBIAN/control" <<CONTROL
Package: $PKG
Version: $VER
Section: sound
Priority: optional
Architecture: $ARCH
Depends: $SHLIBS
Recommends: $RECOMMENDS
Maintainer: $MAINT
Homepage: $HOMEPAGE
Installed-Size: $(du -sk --exclude=DEBIAN "$ROOT" | cut -f1)
Description: speech recognition engine for RuscaDubbing
 Runs local Whisper speech recognition models (ggml files) for the
 RuscaLinux OS Tool RuscaDubbing. Contains whisper-cli, plus whisper-bench
 for measurements.
 .
 This is whisper.cpp $TAG, an external component (MIT license,
 $UPSTREAM), built from unmodified source with the
 $BACKEND backend. It has no network code: no server and no downloads,
 models are files copied by the user. Vulkan covers NVIDIA, AMD and Intel
 graphics with one binary and falls back to the CPU.
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
say "Pronto: build-deb/$DEB_FILE ($(du -h "$OUT_DIR/$DEB_FILE" | cut -f1)), whisper.cpp $TAG, $BACKEND"

# Cache: restano solo sorgente e compilazione della versione appena usata.
find "$CACHE/src" -maxdepth 1 -name 'whisper.cpp-v*.tar.gz' ! -name "$ARCHIVE" -delete 2>/dev/null || true
find "$CACHE" -maxdepth 1 -type d \( -name 'stage-*' -o -name 'build-*' \) \
     ! -name "stage-${WHISPER_CPP_VERSION}-*" -exec rm -rf {} + 2>/dev/null || true
if command -v lintian >/dev/null 2>&1; then
    lintian "$OUT_DIR/$DEB_FILE" || true
fi
