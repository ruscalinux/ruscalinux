#!/bin/bash
# ---------------------------------------------------------------------------
# RuscaLinux — costruisce il pacchetto ruscapiper-engine.
#
#   ./make-deb.sh
#
# ruscapiper-engine e' il motore di sintesi vocale di RuscaLLisse. E' Piper
# (piper1-gpl), SOFTWARE ESTERNO con licenza GPL-3.0
# (https://github.com/OHF-Voice/piper1-gpl), compilato dal sorgente insieme a
# espeak-ng (GPL-3.0), che Piper usa per trasformare il testo in fonemi.
# E' fatto come gli altri motori (ruscallama-engine, ruscawhisper-engine,
# ruscadiffusion-engine): stesse regole, stessi controlli.
#
# Regole delle specifiche delle RuscaLinux OS Apps (sezioni 1.8 e 7):
#   * versione del pacchetto = versione di RuscaLinux (release.conf); la
#     versione di Piper e il commit di espeak-ng sono scritti nella
#     descrizione e nella documentazione del pacchetto;
#   * un solo .deb in build-deb/, con suffisso -ruscalinux e SHA256SUMS;
#   * architettura amd64: e' codice compilato.
#
# Sorgente: DUE archivi, come per stable-diffusion.cpp con la sua copia di ggml.
#   1. piper1-gpl all'ultima release stabile (ultima-versione.sh);
#   2. espeak-ng alla revisione che quella release di Piper fissa nella sua
#      build (GIT_TAG in libpiper/CMakeLists.txt): Piper usa una funzione
#      (espeak_TextToPhonemesWithTerminator) che non c'e' nella release 1.52
#      di espeak-ng, quella di Debian trixie, quindi non si puo' usare la
#      libreria di Debian.
# Ogni archivio si controlla in due modi: il commit scritto nell'archivio
# deve essere quello atteso, e l'impronta SHA-256 si registra in checksums/
# alla prima build e si confronta nelle successive (i file nuovi in
# checksums/ vanno aggiunti al repository).
#
# Compilazione: si compilano gli stessi file sorgente di Piper, invariati,
# con CMakeLists.txt di questa cartella invece di quello di Piper, che durante
# la configurazione scaricherebbe espeak-ng (git) e forse ONNX Runtime.
# ONNX Runtime e' quello di Debian (libonnxruntime-dev). Tutto gira senza
# rete (unshare -rn): se qualcosa provasse a scaricare, la build fallirebbe.
#
# Si impacchettano libpiper.so, ruscapiper-stream (programma di RuscaLinux,
# GPL-3.0: legge frasi dallo stdin e scrive audio sullo stdout, la voce resta
# caricata) e i dati di espeak-ng. Niente server HTTP di Piper, niente Python.
#
# Variabili utili (facoltative):
#   RUSCAPIPER_PIPER_VERSION=1.8.0   costruisce quella versione di Piper
#   GITHUB_TOKEN=<token>             alza il limite di richieste all'API di GitHub
#   RUSCAPIPER_CACHE=<dir>           cartella della cache
#   RUSCAPIPER_JOBS=<n>              processi di compilazione (default: nproc)
#
# Dipendenze di compilazione:
#   sudo apt install build-essential cmake pkg-config dpkg-dev wget git \
#                    python3 libonnxruntime-dev libsonic-dev
# (libsonic-dev non finisce nel motore: senza, la configurazione di
# espeak-ng proverebbe a scaricare sonic da GitHub.)
# ---------------------------------------------------------------------------
set -euo pipefail
cd "$(dirname "$0")"
SRC_DIR="$(pwd)"

# ── Versioni ────────────────────────────────────────────────────────────────
VER="1.99.3"                       # = VERSION in release.conf
GIORNI_MINIMI=14                   # release piu' giovani: costruite, con avviso

# Funzioni di libpiper usate da ruscapiper-stream: la libreria compilata le
# deve esportare.
SIMBOLI_PIPER="piper_create piper_free piper_default_synthesize_options
  piper_synthesize_start piper_synthesize_next piper_version"

PKG="ruscapiper-engine"
ARCH="amd64"
MAINT="Nunzio Curcuruto <info@ruscalinux.org>"
HOMEPAGE="https://www.ruscalinux.org/"
UPSTREAM="https://github.com/OHF-Voice/piper1-gpl"
ESPEAK_UPSTREAM="https://github.com/espeak-ng/espeak-ng"
JOBS="${RUSCAPIPER_JOBS:-$(nproc)}"
CACHE="${RUSCAPIPER_CACHE:-${XDG_CACHE_HOME:-$HOME/.cache}/ruscalinux/ruscapiper-engine}"
SOURCE_DATE_EPOCH="${SOURCE_DATE_EPOCH:-$(date +%s)}"

LIBDIR="usr/lib/${PKG}"            # programma, libreria e dati di espeak-ng
PROFILE="usr.lib.ruscapiper-engine.ruscapiper-stream"
KEEP="ruscapiper-stream libpiper.so"

die() { echo "ERRORE: $*" >&2; exit 1; }
say() { echo "==> $*"; }
avviso() { echo "ATTENZIONE: $*" >&2; }

[ -f ultima-versione.sh ] || die "manca ultima-versione.sh"
[ -f CMakeLists.txt ] && [ -f ruscapiper-stream.c ] || die "mancano CMakeLists.txt o ruscapiper-stream.c"
[ -f "apparmor/$PROFILE" ] || die "manca il profilo apparmor/$PROFILE"

# ── Controllo delle dipendenze, prima di scaricare o compilare ──────────────
MANCA=""
for c in dpkg-deb dpkg-shlibdeps cmake g++ gcc make patch pkg-config strip nm readelf python3; do
    command -v "$c" >/dev/null || MANCA="$MANCA $c"
done
command -v wget >/dev/null || command -v curl >/dev/null || MANCA="$MANCA wget"
command -v git >/dev/null || MANCA="$MANCA git"
# Basta una delle posizioni possibili dell'intestazione; se non e' in
# nessuna, si chiede a dpkg dove l'ha messa il pacchetto.
ORT_H=""
for h in /usr/include/onnxruntime/onnxruntime_cxx_api.h \
         /usr/include/onnxruntime/core/session/onnxruntime_cxx_api.h \
         /usr/include/onnxruntime_cxx_api.h; do
    [ -f "$h" ] && { ORT_H="$h"; break; }
done
[ -n "$ORT_H" ] || ORT_H=$(dpkg -L libonnxruntime-dev 2>/dev/null | grep '/onnxruntime_cxx_api\.h$' | head -n1 || true)
[ -n "$ORT_H" ] || MANCA="$MANCA libonnxruntime-dev"
[ -z "$ORT_H" ] || say "ONNX Runtime: $ORT_H"
[ -f /usr/include/sonic.h ] || MANCA="$MANCA libsonic-dev"
if [ -n "$MANCA" ]; then
    echo "ERRORE: mancano strumenti per compilare Piper:$MANCA" >&2
    echo "  sudo apt install build-essential cmake pkg-config dpkg-dev wget git \\" >&2
    echo "                   python3 libonnxruntime-dev libsonic-dev" >&2
    exit 1
fi

mkdir -p "$CACHE/src" "$SRC_DIR/checksums"
OUT_DIR="$SRC_DIR/build-deb"
rm -rf "$OUT_DIR"
mkdir -p "$OUT_DIR"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

scarica() {   # url file
    if command -v wget >/dev/null; then
        wget -q -O "$2" "$1"
    else
        curl -sfL -o "$2" "$1"
    fi
}

# Verifica un archivio: commit atteso e impronta registrata.
verifica() {  # archivio commit_atteso nome
    local file="$1" atteso="$2" nome="$3" pin="$SRC_DIR/checksums/$(basename "$1").sha256"
    local commit
    commit=$(gzip -dc "$file" | git get-tar-commit-id 2>/dev/null || true)
    [ -n "$commit" ] || { rm -f "$file"; die "l'archivio di $nome non contiene il commit: scaricato male?"; }
    if [ -n "$atteso" ] && [ "$commit" != "$atteso" ]; then
        rm -f "$file"
        die "l'archivio di $nome non corrisponde al commit atteso
        commit nell'archivio: $commit
        commit atteso:        $atteso
        Il file e' stato cancellato dalla cache: rilancia per riscaricarlo."
    fi
    local ottenuto
    ottenuto=$(sha256sum "$file" | cut -d' ' -f1)
    if [ -f "$pin" ]; then
        if [ "$(cut -d' ' -f1 < "$pin")" != "$ottenuto" ]; then
            rm -f "$file"
            die "l'archivio di $nome non corrisponde all'impronta registrata in
        checksums/$(basename "$pin"). Il file e' stato cancellato dalla cache:
        rilancia per riscaricarlo. Se si ripete, controlla prima di cancellare
        l'impronta registrata."
        fi
    else
        [ -n "$atteso" ] || die "non riesco a verificare $nome: commit atteso sconosciuto e
        nessuna impronta registrata"
        echo "$ottenuto  $(basename "$file")" > "$pin"
        avviso "$nome e' nuovo: impronta registrata in
            apps/ruscapiper-engine/checksums/$(basename "$pin")
            Aggiungila al repository (git add) insieme alla prossima modifica."
    fi
    echo "$commit $ottenuto"
}

# ── Quale versione di Piper ──────────────────────────────────────────────────
PUBBLICATA=""
if RIGA=$(bash ./ultima-versione.sh); then
    TAG="${RIGA%% *}"
    [ "$RIGA" != "$TAG" ] && PUBBLICATA="${RIGA#* }"
else
    [ $? -eq 2 ] && die "versione di Piper non valida (RUSCAPIPER_PIPER_VERSION)"
    TAG=$(ls "$CACHE/src" 2>/dev/null \
          | sed -n 's/^piper1-gpl-\(v[0-9]*\.[0-9]*\.[0-9]*\)\.tar\.gz$/\1/p' \
          | while read -r t; do [ -f "checksums/piper1-gpl-$t.tar.gz.sha256" ] && echo "$t"; done \
          | sort -V | tail -1) || true
    [ -n "$TAG" ] || die "non so quale Piper costruire: niente rete e niente in cache"
    avviso "non riesco a sapere quale sia l'ultima release di Piper: uso $TAG, gia' scaricata."
fi
PIPER_VERSION="${TAG#v}"
ARCHIVE="piper1-gpl-${TAG}.tar.gz"
say "Piper $TAG"

# ── Sorgente di Piper ────────────────────────────────────────────────────────
CACHED="$CACHE/src/$ARCHIVE"
if [ ! -f "$CACHED" ]; then
    say "Scarico Piper $TAG"
    scarica "https://codeload.github.com/OHF-Voice/piper1-gpl/tar.gz/refs/tags/${TAG}" "$TMP/$ARCHIVE" \
        || die "download di Piper non riuscito"
    mv "$TMP/$ARCHIVE" "$CACHED"
fi
REMOTO=$(timeout 60 git ls-remote "$UPSTREAM.git" "refs/tags/$TAG" "refs/tags/$TAG^{}" 2>/dev/null || true)
COMMIT_TAG=$(printf '%s\n' "$REMOTO" | awk '/\^\{\}$/ {print $1}')
[ -n "$COMMIT_TAG" ] || COMMIT_TAG=$(printf '%s\n' "$REMOTO" | awk 'NF {print $1; exit}')
# (in una variabile e non con < <(...): se la verifica fallisce lo script si ferma)
RIS=$(verifica "$CACHED" "$COMMIT_TAG" "Piper $TAG")
read -r COMMIT SHA_PIPER <<< "$(tail -n 1 <<< "$RIS")"
say "Sorgente di Piper $TAG verificato (commit ${COMMIT:0:12})"

# ── Quale espeak-ng: la revisione che questa release di Piper fissa ─────────
ESPEAK_COMMIT=$(tar -xzOf "$CACHED" --wildcards '*/libpiper/CMakeLists.txt' 2>/dev/null \
    | awk '/espeak_ng_external/ {in_ep=1} in_ep && /GIT_TAG/ {print $2; exit}')
[[ "$ESPEAK_COMMIT" =~ ^[0-9a-f]{40}$ ]] \
    || die "non trovo in libpiper/CMakeLists.txt di Piper $TAG la revisione di espeak-ng (GIT_TAG)"
ESPEAK_ARCHIVE="espeak-ng-${ESPEAK_COMMIT}.tar.gz"
ESPEAK_CACHED="$CACHE/src/$ESPEAK_ARCHIVE"
if [ ! -f "$ESPEAK_CACHED" ]; then
    say "Scarico espeak-ng ${ESPEAK_COMMIT:0:12}"
    scarica "https://codeload.github.com/espeak-ng/espeak-ng/tar.gz/${ESPEAK_COMMIT}" "$TMP/$ESPEAK_ARCHIVE" \
        || die "download di espeak-ng non riuscito"
    mv "$TMP/$ESPEAK_ARCHIVE" "$ESPEAK_CACHED"
fi
RIS=$(verifica "$ESPEAK_CACHED" "$ESPEAK_COMMIT" "espeak-ng ${ESPEAK_COMMIT:0:12}")
read -r _ SHA_ESPEAK <<< "$(tail -n 1 <<< "$RIS")"
say "Sorgente di espeak-ng ${ESPEAK_COMMIT:0:12} verificato"

# Eta' della release
if [ -n "$PUBBLICATA" ]; then
    DATA_RELEASE=$(date -u -d "$PUBBLICATA" +%Y-%m-%d 2>/dev/null || true)
else
    DATA_RELEASE=$(TZ=UTC tar -tvzf "$CACHED" --full-time 2>/dev/null | awk 'NR==1 {print $4}')
fi
if [ -n "${DATA_RELEASE:-}" ]; then
    GIORNI=$(( ( $(date -u +%s) - $(date -u -d "$DATA_RELEASE" +%s) ) / 86400 ))
    say "Release del $DATA_RELEASE ($GIORNI giorni fa)"
    [ "$GIORNI" -ge "$GIORNI_MINIMI" ] || avviso "Piper $TAG e' uscita da $GIORNI giorni (meno di $GIORNI_MINIMI).
            Prova RuscaLLisse prima di pubblicare la ISO; per la precedente:
            RUSCAPIPER_PIPER_VERSION=<versione> ./make-deb.sh"
fi

# ── Compilazione (o riuso della cache) ───────────────────────────────────────
CFLAGS_DEB="$(dpkg-buildflags --get CFLAGS) $(dpkg-buildflags --get CPPFLAGS)"
CXXFLAGS_DEB="$(dpkg-buildflags --get CXXFLAGS) $(dpkg-buildflags --get CPPFLAGS)"
LDFLAGS_DEB="$(dpkg-buildflags --get LDFLAGS)"
ORT_VERSIONE=$(dpkg-query -W -f='${Version}' libonnxruntime-dev 2>/dev/null || echo "?")
# Piper e' scritto per ONNX Runtime 1.22: con un ONNX Runtime che non ha
# Session::GetOutputNames() (Debian 13 ha la 1.21) si applica
# patches/onnxruntime-1.21.patch, che usa le funzioni della 1.21.
# Si prova a compilare una chiamata a Session::GetOutputNames(): cercare il
# nome nelle intestazioni non basta, compare anche altrove. Se la prova non
# compila per altri motivi la patch si applica lo stesso: e' innocua anche
# con la 1.22, dove GetOutputCount() e GetOutputNameAllocated() ci sono.
PATCH_ORT=""
if ! printf '#include <onnxruntime_cxx_api.h>\nvoid f(Ort::Session &s) { (void)s.GetOutputNames(); }\n' \
        | g++ -std=c++17 -fsyntax-only -I "$(dirname "$ORT_H")" -x c++ - >/dev/null 2>&1; then
    PATCH_ORT="$SRC_DIR/patches/onnxruntime-1.21.patch"
else
    say "ONNX Runtime $ORT_VERSIONE ha GetOutputNames(): Piper senza modifiche"
fi
FLAGS_FIRMA=$(printf '%s %s' "$CFLAGS_DEB" "$LDFLAGS_DEB" | sed 's/-ffile-prefix-map=[^ ]*//g')
OPZIONI="piper=$COMMIT espeak=$ESPEAK_COMMIT ort=$ORT_VERSIONE cmake=$(sha256sum CMakeLists.txt | cut -c1-16) stream=$(sha256sum ruscapiper-stream.c | cut -c1-16) patch=$([ -z "$PATCH_ORT" ] || sha256sum "$PATCH_ORT" | cut -c1-16) fonemi=$(sha256sum patches/fonemi.patch | cut -c1-16) flags=$FLAGS_FIRMA"
FIRMA=$(printf '%s' "$OPZIONI" | sha256sum | cut -c1-16)
STAGE_CACHE="$CACHE/stage-${PIPER_VERSION}-${FIRMA}"

SENZA_RETE=()
if unshare -rn true 2>/dev/null; then
    SENZA_RETE=(unshare -rn)
else
    avviso "unshare non disponibile: compilo senza isolare la rete"
fi

if [ -f "$STAGE_CACHE/.completo" ]; then
    say "Uso la compilazione in cache"
else
    BUILD="$CACHE/build-${PIPER_VERSION}-${FIRMA}"
    rm -rf "$BUILD" "$STAGE_CACHE"
    mkdir -p "$BUILD/piper" "$BUILD/espeak"
    tar -xzf "$CACHED" -C "$BUILD/piper" --strip-components=1
    tar -xzf "$ESPEAK_CACHED" -C "$BUILD/espeak" --strip-components=1
    # Correzioni a libpiper 1.8.0 (sempre): chiavi di piu' codepoint nella
    # mappa dei fonemi (accento straniero con le voci recenti) e fonemi che
    # non ripartivano da capo a ogni frase.
    say "Applico patches/fonemi.patch"
    patch -d "$BUILD/piper" -p1 --forward --no-backup-if-mismatch -s < "$SRC_DIR/patches/fonemi.patch" \
        || die "patches/fonemi.patch non si applica a Piper $TAG: va aggiornata (o non serve piu')"
    if [ -n "$PATCH_ORT" ]; then
        say "ONNX Runtime $ORT_VERSIONE senza GetOutputNames(): applico patches/onnxruntime-1.21.patch"
        patch -d "$BUILD/piper" -p1 --forward --no-backup-if-mismatch -s < "$PATCH_ORT" \
            || die "patches/onnxruntime-1.21.patch non si applica a Piper $TAG: va aggiornata"
    fi

    # 1. espeak-ng statico, con le stesse opzioni dell'ExternalProject di
    #    Piper (niente audio, niente mbrola, niente sonic; dizionari estesi
    #    per cinese e russo).
    say "Compilo espeak-ng (${ESPEAK_COMMIT:0:12})"
    UCD_INC="$BUILD/espeak/src/ucd-tools/src/include"
    CFLAGS="$CFLAGS_DEB -D_FILE_OFFSET_BITS=64 -I$UCD_INC" \
    CXXFLAGS="$CXXFLAGS_DEB -D_FILE_OFFSET_BITS=64 -I$UCD_INC" LDFLAGS="$LDFLAGS_DEB" \
    "${SENZA_RETE[@]}" cmake -S "$BUILD/espeak" -B "$BUILD/espeak-build" \
        -DCMAKE_BUILD_TYPE=Release \
        -DCMAKE_INSTALL_PREFIX="$BUILD/espeak-install" \
        -DBUILD_SHARED_LIBS=OFF -DCMAKE_POSITION_INDEPENDENT_CODE=ON \
        -DUSE_ASYNC=OFF -DUSE_MBROLA=OFF -DUSE_LIBSONIC=OFF -DUSE_LIBPCAUDIO=OFF \
        -DUSE_KLATT=OFF -DUSE_SPEECHPLAYER=OFF -DEXTRA_cmn=ON -DEXTRA_ru=ON \
        > "$BUILD/espeak-cmake.log" 2>&1 \
        || { tail -n 30 "$BUILD/espeak-cmake.log" >&2; die "configurazione di espeak-ng non riuscita"; }
    "${SENZA_RETE[@]}" cmake --build "$BUILD/espeak-build" -j"$JOBS" > "$BUILD/espeak-build.log" 2>&1 \
        || { tail -n 30 "$BUILD/espeak-build.log" >&2; die "compilazione di espeak-ng non riuscita"; }
    "${SENZA_RETE[@]}" cmake --install "$BUILD/espeak-build" > /dev/null
    UCD_LIB=$(find "$BUILD/espeak-build" -name libucd.a | head -1)
    [ -n "$UCD_LIB" ] && [ -f "$BUILD/espeak-install/lib/libespeak-ng.a" ] \
        || die "espeak-ng compilato senza libespeak-ng.a o libucd.a"
    [ -d "$BUILD/espeak-install/share/espeak-ng-data" ] || die "mancano i dati di espeak-ng"

    # 2. libpiper e ruscapiper-stream, con CMakeLists.txt di questa cartella.
    say "Compilo libpiper e ruscapiper-stream"
    CFLAGS="$CFLAGS_DEB" CXXFLAGS="$CXXFLAGS_DEB" LDFLAGS="$LDFLAGS_DEB" \
    "${SENZA_RETE[@]}" cmake -S "$SRC_DIR" -B "$BUILD/piper-build" \
        -DCMAKE_BUILD_TYPE=Release \
        -DPIPER_SRC="$BUILD/piper" \
        -DESPEAK_INSTALL="$BUILD/espeak-install" \
        -DUCD_LIB="$UCD_LIB" \
        -DCMAKE_INCLUDE_PATH="$(dirname "$ORT_H")" \
        -DPIPER_VERSION="$PIPER_VERSION" \
        -DRUSCAPIPER_VERSION="$VER" \
        -DRUSCAPIPER_ESPEAK_DATA="/$LIBDIR/espeak-ng-data" \
        -DCMAKE_BUILD_WITH_INSTALL_RPATH=ON \
        -DCMAKE_INSTALL_RPATH="/$LIBDIR" \
        > "$BUILD/piper-cmake.log" 2>&1 \
        || { tail -n 30 "$BUILD/piper-cmake.log" >&2; die "configurazione di libpiper non riuscita"; }
    "${SENZA_RETE[@]}" cmake --build "$BUILD/piper-build" -j"$JOBS" > "$BUILD/piper-build.log" 2>&1 \
        || { grep -E "error|Error" "$BUILD/piper-build.log" | head -n 30 >&2; die "compilazione di libpiper non riuscita (log: $BUILD/piper-build.log)"; }

    mkdir -p "$STAGE_CACHE/bin" "$STAGE_CACHE/licenses"
    install -m 755 "$BUILD/piper-build/ruscapiper-stream" "$STAGE_CACHE/bin/"
    install -m 644 "$BUILD/piper-build/libpiper.so" "$STAGE_CACHE/bin/"
    cp -a "$BUILD/espeak-install/share/espeak-ng-data" "$STAGE_CACHE/bin/espeak-ng-data"
    cp "$BUILD/piper/COPYING" "$STAGE_CACHE/licenses/COPYING.piper"
    cp "$BUILD/espeak/COPYING" "$STAGE_CACHE/licenses/COPYING.espeak-ng"
    for f in COPYING.APACHE COPYING.BSD2 COPYING.UCD; do
        [ -f "$BUILD/espeak/$f" ] && cp "$BUILD/espeak/$f" "$STAGE_CACHE/licenses/$f.espeak-ng"
    done
    # La voce di prova del sorgente di Piper, per la prova qui sotto.
    if [ -f "$BUILD/piper/tests/test_voice.onnx" ]; then
        mkdir -p "$STAGE_CACHE/prova"
        cp "$BUILD/piper/tests/test_voice.onnx" "$BUILD/piper/tests/test_voice.onnx.json" "$STAGE_CACHE/prova/"
    fi
    touch "$STAGE_CACHE/.completo"
    rm -rf "$BUILD"
fi
BIN="$STAGE_CACHE/bin"
for f in $KEEP; do [ -f "$BIN/$f" ] || die "$f mancante nella compilazione"; done

# ── Controlli ────────────────────────────────────────────────────────────────
# Funzioni esportate da libpiper.
MANCANO=""
for s in $SIMBOLI_PIPER; do
    nm -D --defined-only "$BIN/libpiper.so" | awk '{print $NF}' | grep -qx "$s" || MANCANO="$MANCANO $s"
done
[ -z "$MANCANO" ] || die "libpiper di Piper $TAG non esporta:$MANCANO
        Adatta ruscapiper-stream.c, oppure costruisci la versione precedente:
        RUSCAPIPER_PIPER_VERSION=<versione> ./make-deb.sh"
say "libpiper esporta tutte le funzioni usate da ruscapiper-stream"

# Niente rete: nessuna libreria TLS o HTTP, nessuna funzione per connessioni.
RETE=$(for f in $KEEP; do LD_LIBRARY_PATH="$BIN" ldd "$BIN/$f" 2>/dev/null; done \
    | grep -oE 'lib(ssl|crypto|curl)[^ ]*' | sort -u || true)
[ -z "$RETE" ] || die "il motore e' collegato a librerie di rete: $RETE"
SOCKET=$(for f in $KEEP; do
    nm -D --undefined-only "$BIN/$f" 2>/dev/null | awk -v f="$f" \
        '{ sub(/@.*/, "", $NF) }
         $NF ~ /^(socket|connect|bind|listen|accept|accept4|getaddrinfo|gethostbyname|sendto|recvfrom)$/ \
             { print f ":" $NF }'
    done | sort -u | tr '\n' ' ' || true)
[ -z "$SOCKET" ] || die "il motore contiene codice di rete: $SOCKET"
say "Nessun codice di rete nei binari"

# Le librerie si cercano solo nella cartella privata del pacchetto.
for f in $KEEP; do
    RP=$(readelf -d "$BIN/$f" 2>/dev/null | sed -n 's/.*R\(UN\)\?PATH.*\[\(.*\)\]/\2/p')
    [ -z "$RP" ] || [ "$RP" = "/$LIBDIR" ] || die "RUNPATH inatteso in $f: $RP"
done

# Prova vera: ruscapiper-stream dice una frase con la voce di prova del
# sorgente di Piper (e i dati di espeak-ng appena compilati). Si controllano
# l'avvio, l'audio, i fonemi e la fine della frase.
"$BIN/ruscapiper-stream" --version >/dev/null 2>&1 \
    || LD_LIBRARY_PATH="$BIN" "$BIN/ruscapiper-stream" --version >/dev/null \
    || die "ruscapiper-stream non parte"
if [ -f "$STAGE_CACHE/prova/test_voice.onnx" ]; then
    printf '1\t0\tHello, this is a test.\n2\t0\tERRORE\n' | LD_LIBRARY_PATH="$BIN" timeout 120 \
        "$BIN/ruscapiper-stream" --voice "$STAGE_CACHE/prova/test_voice.onnx" \
        --espeak-data "$BIN/espeak-ng-data" > "$TMP/prova.bin" 2> "$TMP/prova.log" \
        || { cat "$TMP/prova.log" >&2; die "ruscapiper-stream non riesce a usare la voce di prova"; }
    python3 - "$TMP/prova.bin" <<'PY' || die "ruscapiper-stream ha scritto un audio non valido"
import struct, sys
d = open(sys.argv[1], "rb").read()
assert d[:4] == b"RPS1", "manca RPS1"
p, ids, campioni, fonemi = 8, set(), 0, 0
while p < len(d):
    magic, cid, flags, rate, ns, nph, nal = struct.unpack_from("<4s6I", d, p)
    assert magic == b"RPSC", "pezzo non valido"
    p += 28 + ns * 2 + nph * 4 + nal * 4
    if cid == 1:
        assert rate > 0 or ns == 0
        campioni += ns
        fonemi += nph
    if flags & 1:
        ids.add(cid)
assert p == len(d), "lunghezza sbagliata"
assert {1, 2} <= ids, "frasi non concluse"
assert campioni > 0 and fonemi > 0, "niente audio o niente fonemi"
print(f"==> Voce di prova: {campioni} campioni, {fonemi} fonemi")
open(sys.argv[1] + ".fonemi", "w").write(str(fonemi))
PY
    # Prova delle chiavi di piu' caratteri (patches/fonemi.patch): con la
    # chiave "aɪ" aggiunta alla mappa, i fonemi devono restare quelli di prima.
    python3 - "$STAGE_CACHE/prova/test_voice.onnx.json" "$TMP/gruppi.onnx.json" <<'PY'
import json, sys
c = json.load(open(sys.argv[1], encoding="utf-8"))
c["phoneme_id_map"]["aɪ"] = c["phoneme_id_map"]["ɪ"]
json.dump(c, open(sys.argv[2], "w", encoding="utf-8"), ensure_ascii=False)
PY
    printf '1\t0\tHello, this is a test.\n' | LD_LIBRARY_PATH="$BIN" timeout 120 \
        "$BIN/ruscapiper-stream" --voice "$STAGE_CACHE/prova/test_voice.onnx" \
        --config "$TMP/gruppi.onnx.json" --espeak-data "$BIN/espeak-ng-data" \
        > "$TMP/gruppi.bin" 2> /dev/null || die "ruscapiper-stream non usa la voce con la chiave aɪ"
    python3 - "$TMP/gruppi.bin" "$(cat "$TMP/prova.bin.fonemi")" <<'PY' \
        || die "con la chiave aɪ i fonemi cambiano: patches/fonemi.patch non funziona"
import struct, sys
d = open(sys.argv[1], "rb").read()
p, fonemi = 8, 0
while p < len(d):
    _m, _cid, _fl, _r, ns, nph, nal = struct.unpack_from("<4s6I", d, p)
    p += 28 + ns * 2 + nph * 4 + nal * 4
    fonemi += nph
assert fonemi == int(sys.argv[2]), f"{fonemi} fonemi invece di {sys.argv[2]}"
print("==> Chiavi di piu' caratteri nella mappa dei fonemi: ignorate")
PY
else
    avviso "voce di prova non trovata nel sorgente di Piper: prova saltata"
fi

# ── Albero del pacchetto ─────────────────────────────────────────────────────
ROOT="$TMP/${PKG}_${VER}_${ARCH}"
DOC="$ROOT/usr/share/doc/$PKG"
mkdir -p "$ROOT/DEBIAN" "$ROOT/$LIBDIR" "$DOC" \
         "$ROOT/etc/apparmor.d/force-complain" "$ROOT/usr/share/ruscapiper/voices"
install -m 755 "$BIN/ruscapiper-stream" "$ROOT/$LIBDIR/"
install -m 644 "$BIN/libpiper.so" "$ROOT/$LIBDIR/"
cp -a "$BIN/espeak-ng-data" "$ROOT/$LIBDIR/espeak-ng-data"
find "$ROOT/$LIBDIR/espeak-ng-data" -type d -exec chmod 755 {} +
find "$ROOT/$LIBDIR/espeak-ng-data" -type f -exec chmod 644 {} +
strip --strip-unneeded --remove-section=.comment --remove-section=.note \
    "$ROOT/$LIBDIR/ruscapiper-stream" "$ROOT/$LIBDIR/libpiper.so"

MANCANTI=$(LD_LIBRARY_PATH="$ROOT/$LIBDIR" ldd "$ROOT/$LIBDIR/ruscapiper-stream" 2>/dev/null \
    | grep 'not found' | awk '{print $1}' | sort -u || true)
[ -z "$MANCANTI" ] || die "librerie non risolte: $MANCANTI"

install -m 644 "apparmor/$PROFILE" "$ROOT/etc/apparmor.d/$PROFILE"
ln -s "../$PROFILE" "$ROOT/etc/apparmor.d/force-complain/$PROFILE"
if command -v apparmor_parser >/dev/null 2>&1; then
    apparmor_parser -Q -K "apparmor/$PROFILE" >/dev/null || die "il profilo AppArmor non e' valido"
fi

# ── Documentazione ───────────────────────────────────────────────────────────
MODIFICHE="RuscaLinux li compila dal sorgente, con due correzioni a
libpiper/src/piper.cpp (fonemi.patch, in questa cartella): le chiavi di piu'
caratteri della mappa dei fonemi (gruppi vocalici come \"aɪ\") non si
attribuiscono al loro primo carattere, che con le voci recenti dava un accento
straniero; i fonemi di ogni frase ripartono da capo."
cp "$SRC_DIR/patches/fonemi.patch" "$DOC/fonemi.patch"
if [ -n "$PATCH_ORT" ]; then
    MODIFICHE="$MODIFICHE Per l'ONNX Runtime $ORT_VERSIONE di Debian,
inoltre, la chiamata a Session::GetOutputNames() (che esiste dalla 1.22) e'
sostituita da GetOutputCount() e GetOutputNameAllocated(), con lo stesso
risultato (onnxruntime-1.21.patch)."
    cp "$PATCH_ORT" "$DOC/onnxruntime-1.21.patch"
fi
cat > "$DOC/README.md" <<README
# ruscapiper-engine $VER

Motore di sintesi vocale del RuscaLinux OS App RuscaLLisse.

**Componenti esterni:** Piper (piper1-gpl) $TAG — $UPSTREAM — licenza
GPL-3.0; espeak-ng (revisione fissata da Piper) — $ESPEAK_UPSTREAM —
licenza GPL-3.0. $MODIFICHE

| Voce | Valore |
|---|---|
| Versione di Piper | $PIPER_VERSION (ultima release stabile al momento della build) |
| Data della release | ${DATA_RELEASE:-non nota} |
| Commit di Piper | $COMMIT |
| SHA-256 dell'archivio di Piper | $SHA_PIPER |
| Commit di espeak-ng | $ESPEAK_COMMIT |
| SHA-256 dell'archivio di espeak-ng | $SHA_ESPEAK |
| ONNX Runtime | quello di Debian (libonnxruntime-dev $ORT_VERSIONE) |
| Rete | nessuna: niente server, nessun socket nei binari |
| Percorso | /$LIBDIR |
| Voci | ~/.local/share/ruscapiper/voices/ e /usr/share/ruscapiper/voices/ |

Le voci non fanno parte del pacchetto: sono coppie nome.onnx e nome.onnx.json,
da copiare in una delle due cartelle. Ogni voce ha la propria licenza.

ruscapiper-stream tiene la voce caricata: legge una frase per riga dallo
standard input (ID<TAB>LENGTH_SCALE<TAB>TESTO) e scrive l'audio a 16 bit, con
i fonemi e la loro durata, sullo standard output.

Il profilo AppArmor /etc/apparmor.d/$PROFILE e' in modalita' complain.

    /$LIBDIR/ruscapiper-stream --version
README
gzip -9n "$DOC/README.md"

cat > "$DOC/copyright" <<'COPYRIGHT'
Format: https://www.debian.org/doc/packaging-manuals/copyright-format/1.0/
Upstream-Name: piper1-gpl, espeak-ng
Source: https://github.com/OHF-Voice/piper1-gpl
 https://github.com/espeak-ng/espeak-ng
Comment: ruscapiper-engine is Piper (libpiper) and espeak-ng, external
 components, built from source for RuscaLinux. Only the build files
 (make-deb.sh, CMakeLists.txt), ruscapiper-stream, the AppArmor profile and
 the patches in this directory are part of RuscaLinux. fonemi.patch fixes
 two bugs in libpiper/src/piper.cpp: multi-codepoint keys of the phoneme id
 map were assigned to their first codepoint, and phoneme codepoints were not
 reset between sentences. onnxruntime-1.21.patch, applied only when the
 system ONNX Runtime lacks Session::GetOutputNames(), changes one call so
 that Piper builds with ONNX Runtime 1.21.

Files: usr/lib/ruscapiper-engine/libpiper.so
Copyright: 2023-2026 Michael Hansen and the Piper authors
License: GPL-3+
Comment: libpiper embeds espeak-ng (statically) and the header-only
 libraries nlohmann/json (MIT, 2013-2022 Niels Lohmann) and uni-algo
 (public domain or MIT).

Files: usr/lib/ruscapiper-engine/espeak-ng-data/*
Copyright: 1995-2026 Jonathan Duddington, Reece H. Dunn and the espeak-ng authors
License: GPL-3+
Comment: espeak-ng also contains files under the Apache-2.0 and BSD-2-Clause
 licenses and Unicode character data under the Unicode license; their texts
 are in this directory (COPYING.*.espeak-ng).

Files: usr/lib/ruscapiper-engine/ruscapiper-stream etc/apparmor.d/*
 usr/share/doc/ruscapiper-engine/*.patch
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
 On Debian systems, the complete text of the GNU General Public License
 version 3 can be found in "/usr/share/common-licenses/GPL-3".
COPYRIGHT
for f in "$STAGE_CACHE"/licenses/*; do install -m 644 "$f" "$DOC/"; done

cat <<CHANGELOG | gzip -9n > "$DOC/changelog.gz"
$PKG ($VER) unstable; urgency=medium

  * Primo pacchetto: Piper $TAG (commit ${COMMIT:0:12}) ed espeak-ng
    (commit ${ESPEAK_COMMIT:0:12}) compilati dal sorgente, senza rete, con
    l'ONNX Runtime di Debian.
  * ruscapiper-stream: voce sempre caricata, frasi dallo stdin, audio con
    fonemi e durate sullo stdout. Nessun socket nei binari (controllato).
  * Prova con la voce di prova del sorgente di Piper; profilo AppArmor in
    complain.

 -- $MAINT  $(LC_ALL=C date -Ru -d "@$SOURCE_DATE_EPOCH")
CHANGELOG

# ── Dipendenze calcolate dai binari ──────────────────────────────────────────
mkdir -p "$TMP/shlib/debian"
printf 'Source: %s\n\nPackage: %s\nArchitecture: %s\n' "$PKG" "$PKG" "$ARCH" \
    > "$TMP/shlib/debian/control"
SHLIBS=$(cd "$TMP/shlib" && dpkg-shlibdeps -O -l"$ROOT/$LIBDIR" \
    -e"$ROOT/$LIBDIR/ruscapiper-stream" -e"$ROOT/$LIBDIR/libpiper.so" 2>/dev/null \
    | sed -n 's/^shlibs:Depends=//p')
[ -n "$SHLIBS" ] || die "dpkg-shlibdeps non ha calcolato le dipendenze"

cat > "$ROOT/DEBIAN/control" <<CONTROL
Package: $PKG
Version: $VER
Section: sound
Priority: optional
Architecture: $ARCH
Depends: $SHLIBS
Recommends: apparmor
Maintainer: $MAINT
Homepage: $HOMEPAGE
Installed-Size: $(du -sk --exclude=DEBIAN "$ROOT" | cut -f1)
Description: speech synthesis engine for RuscaLLisse
 Runs local Piper voices (ONNX files) for the RuscaLinux OS App RuscaLLisse.
 Contains ruscapiper-stream, which keeps a voice loaded and turns sentences
 read from standard input into audio with phoneme timings.
 .
 This is Piper (piper1-gpl) $TAG and espeak-ng, external components
 (GPL-3.0), built from source with the ONNX Runtime of Debian and two small
 fixes to libpiper (see /usr/share/doc/ruscapiper-engine/).
 It has no network code: no server and no downloads, voices are files
 copied by the user.
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
say "Pronto: build-deb/$DEB_FILE ($(du -h "$OUT_DIR/$DEB_FILE" | cut -f1)), Piper $TAG"

# Cache: restano solo sorgenti e compilazione della versione appena usata.
find "$CACHE/src" -maxdepth 1 -name 'piper1-gpl-v*.tar.gz' ! -name "$ARCHIVE" -delete 2>/dev/null || true
find "$CACHE/src" -maxdepth 1 -name 'espeak-ng-*.tar.gz' ! -name "$ESPEAK_ARCHIVE" -delete 2>/dev/null || true
find "$CACHE" -maxdepth 1 -type d \( -name 'stage-*' -o -name 'build-*' \) \
     ! -name "stage-${PIPER_VERSION}-${FIRMA}" -exec rm -rf {} + 2>/dev/null || true
if command -v lintian >/dev/null 2>&1; then
    lintian "$OUT_DIR/$DEB_FILE" || true
fi
