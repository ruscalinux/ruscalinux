#!/bin/bash
# ---------------------------------------------------------------------------
# RuscaLinux — costruisce il pacchetto ruscallama-engine.
#
#   ./make-deb.sh
#
# ruscallama-engine e' il motore che esegue i modelli linguistici per
# RuscaLLama e RuscaTranslator. E' llama.cpp, SOFTWARE ESTERNO (licenza MIT,
# https://github.com/ggml-org/llama.cpp), compilato dal sorgente con il
# backend Vulkan: un solo binario per NVIDIA, AMD e Intel, che ripiega sulla
# CPU quando non trova una scheda.
#
# Regole delle specifiche dei RuscaLinux OS Tools:
#   * versione del pacchetto = versione di RuscaLinux (release.conf);
#     la versione di llama.cpp e' scritta nella descrizione e nella
#     documentazione del pacchetto;
#   * un solo .deb in build-deb/, con suffisso -ruscalinux e SHA256SUMS;
#   * architettura amd64: e' codice compilato, non Python.
#
# Quale llama.cpp: l'ultima release stabile pubblicata su GitHub, trovata da
# ultima-versione.sh. Il sorgente viene controllato in due modi:
#   * il commit scritto nell'archivio deve essere quello del tag su GitHub;
#   * l'impronta SHA-256 dell'archivio viene registrata in checksums/ la
#     prima volta che una versione viene costruita, e le build successive
#     della stessa versione devono trovare lo stesso archivio. Il file nuovo
#     in checksums/ va aggiunto al repository (git add).
# Dopo la compilazione si controlla che llama-server accetti tutte le
# opzioni usate da RuscaLLama e RuscaTranslator (OPZIONI_USATE, qui sotto).
#
# La compilazione e' lunga. Il risultato viene tenuto in una cache
# (~/.cache/ruscalinux/ruscallama-engine) e riusato finche' non cambiano
# versione di llama.cpp, backend o opzioni: le build successive della ISO
# rifanno solo il pacchetto, in pochi secondi.
#
# Variabili utili (facoltative):
#   RUSCALLAMA_LLAMA_VERSION=0.7.0
#                             costruisce quella versione invece dell'ultima
#   GITHUB_TOKEN=<token>      alza il limite di richieste all'API di GitHub
#   RUSCALLAMA_BACKEND=cpu    compila senza Vulkan (prove, macchine senza GPU)
#   RUSCALLAMA_CACHE=<dir>    cartella della cache
#   RUSCALLAMA_JOBS=<n>       processi di compilazione (default: nproc)
#
# Dipendenze di compilazione:
#   sudo apt install build-essential cmake pkg-config dpkg-dev wget git \
#                    libvulkan-dev glslc spirv-headers
# ---------------------------------------------------------------------------
set -euo pipefail
cd "$(dirname "$0")"
SRC_DIR="$(pwd)"

# ── Versioni ────────────────────────────────────────────────────────────────
VER="1.99.3"                       # = VERSION in release.conf
# La versione di llama.cpp non e' scritta qui: e' l'ultima release stabile,
# o quella di RUSCALLAMA_LLAMA_VERSION (vedi ultima-versione.sh).

# Una release piu' giovane di cosi' viene costruita lo stesso, ma con un
# avviso: le prime correzioni di una release arrivano di solito nei primi
# giorni. Prima di pubblicare la ISO, prova RuscaLLama e RuscaTranslator.
GIORNI_MINIMI=14

# Opzioni di llama-server usate da RuscaLLama e RuscaTranslator
# (rusca_engine.py e i due programmi). Se una release non ne riconosce una,
# il motore non partirebbe: la build si ferma. Aggiornare l'elenco quando i
# programmi cominciano a usare un'opzione nuova.
OPZIONI_USATE="-m --host --port --api-key-file --no-webui --jinja -ngl
  --list-devices -t -c -b -ub --parallel --flash-attn --reasoning-format
  --reasoning --mmproj --device --spec-type --spec-draft-n-max --model-draft
  --device-draft -ctk -ctv"

# Librerie incluse da llama.cpp in vendor/ e dichiarate nel file copyright
# qui sotto. Se una release ne aggiunge una, la build si ferma: va aggiunta
# al file copyright (specifiche, sezione 6) e a questo elenco.
VENDOR_DICHIARATI="cpp-httplib hash miniaudio nlohmann sheredom stb"

PKG="ruscallama-engine"
ARCH="amd64"
MAINT="Nunzio Curcuruto <info@ruscalinux.org>"
HOMEPAGE="https://www.ruscalinux.org/"
UPSTREAM="https://github.com/ggml-org/llama.cpp"
BACKEND="${RUSCALLAMA_BACKEND:-vulkan}"
JOBS="${RUSCALLAMA_JOBS:-$(nproc)}"
CACHE="${RUSCALLAMA_CACHE:-${XDG_CACHE_HOME:-$HOME/.cache}/ruscalinux/ruscallama-engine}"
SOURCE_DATE_EPOCH="${SOURCE_DATE_EPOCH:-$(date +%s)}"

LIBDIR="usr/lib/${PKG}"            # binari e librerie private
PROFILE="usr.lib.ruscallama-engine.llama-server"

# Solo questi finiscono nel pacchetto: llama-server per i programmi,
# llama-cli e llama-bench per diagnosticare e misurare dal terminale.
KEEP_BINARIES="llama-server llama-cli llama-bench"

die() { echo "ERRORE: $*" >&2; exit 1; }
say() { echo "==> $*"; }

avviso() { echo "ATTENZIONE: $*" >&2; }

case "$BACKEND" in vulkan|cpu) ;; *) die "RUSCALLAMA_BACKEND deve essere vulkan o cpu";; esac
[ -x ultima-versione.sh ] || [ -f ultima-versione.sh ] || die "manca ultima-versione.sh"
[ -f "apparmor/$PROFILE" ] || die "manca il profilo apparmor/$PROFILE"

# ── Controllo delle dipendenze, prima di scaricare o compilare ──────────────
MANCA=""
for c in dpkg-deb dpkg-shlibdeps cmake g++ make pkg-config strip; do
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
    echo "ERRORE: mancano strumenti per compilare llama.cpp:$MANCA" >&2
    echo "  sudo apt install build-essential cmake pkg-config dpkg-dev wget git \\" >&2
    echo "                   libvulkan-dev glslc spirv-headers" >&2
    exit 1
fi

mkdir -p "$CACHE/src"
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
    [ $? -eq 2 ] && die "versione di llama.cpp non valida (RUSCALLAMA_LLAMA_VERSION)"
    # Niente rete: si usa la versione piu' recente gia' scaricata e
    # registrata, cosi' una build senza connessione resta possibile.
    TAG=$(ls "$CACHE/src" 2>/dev/null \
          | sed -n 's/^llama\.cpp-\(v[0-9]*\.[0-9]*\.[0-9]*\)\.tar\.gz$/\1/p' \
          | while read -r t; do [ -f "checksums/llama.cpp-$t.tar.gz.sha256" ] && echo "$t"; done \
          | sort -V | tail -1) || true
    [ -n "$TAG" ] || die "non so quale llama.cpp costruire: niente rete e niente in cache"
    avviso "non riesco a sapere quale sia l'ultima release di llama.cpp:
            uso $TAG, gia' scaricata. Potrebbe non essere l'ultima."
fi
LLAMA_CPP_VERSION="${TAG#v}"
ARCHIVE="llama.cpp-${TAG}.tar.gz"
URL="https://codeload.github.com/ggml-org/llama.cpp/tar.gz/refs/tags/${TAG}"
GIT_URL="https://github.com/ggml-org/llama.cpp.git"
PIN="$SRC_DIR/checksums/${ARCHIVE}.sha256"
say "llama.cpp $TAG"

# ── Sorgente: cache locale o download, poi due controlli ────────────────────
CACHED="$CACHE/src/$ARCHIVE"
if [ ! -f "$CACHED" ]; then
    say "Scarico llama.cpp $TAG"
    if command -v wget >/dev/null; then
        wget -q -O "$TMP/$ARCHIVE" "$URL" || die "download non riuscito ($URL)"
    else
        curl -sfL -o "$TMP/$ARCHIVE" "$URL" || die "download non riuscito ($URL)"
    fi
    mv "$TMP/$ARCHIVE" "$CACHED"
fi

# 1. Il commit dentro l'archivio (GitHub lo scrive nell'intestazione del tar)
#    deve essere quello a cui punta il tag. Per un tag annotato conta il
#    commit puntato (riga ^{}), non l'oggetto tag.
COMMIT=$(gzip -dc "$CACHED" | git get-tar-commit-id 2>/dev/null || true)
[ -n "$COMMIT" ] || { rm -f "$CACHED"; die "l'archivio di llama.cpp $TAG non contiene il commit: scaricato male?"; }
REMOTO=$(timeout 60 git ls-remote "$GIT_URL" "refs/tags/$TAG" "refs/tags/$TAG^{}" 2>/dev/null || true)
COMMIT_TAG=$(printf '%s\n' "$REMOTO" | awk '/\^\{\}$/ {print $1}')
[ -n "$COMMIT_TAG" ] || COMMIT_TAG=$(printf '%s\n' "$REMOTO" | awk 'NF {print $1; exit}')
if [ -n "$COMMIT_TAG" ]; then
    if [ "$COMMIT" != "$COMMIT_TAG" ]; then
        rm -f "$CACHED"
        die "l'archivio di llama.cpp $TAG non corrisponde al tag su GitHub
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
        die "l'archivio di llama.cpp $TAG non corrisponde all'impronta registrata
        atteso:   $ATTESO
        ottenuto: $OTTENUTO
        Il file e' stato cancellato dalla cache: rilancia per riscaricarlo.
        Se si ripete, il tag $TAG e' stato cambiato su GitHub: controlla prima
        di cancellare checksums/$ARCHIVE.sha256."
    fi
else
    echo "$OTTENUTO  $ARCHIVE" > "$PIN"
    avviso "llama.cpp $TAG e' una versione nuova: impronta registrata in
            tools/ruscallama-engine/checksums/$ARCHIVE.sha256
            Aggiungila al repository (git add) insieme alla prossima modifica."
fi
say "Sorgente llama.cpp $TAG verificato (commit ${COMMIT:0:12})"

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
        avviso "llama.cpp $TAG e' uscita da $GIORNI giorni (meno di $GIORNI_MINIMI).
            Prova RuscaLLama e RuscaTranslator prima di pubblicare la ISO;
            per costruire la versione precedente:
            RUSCALLAMA_LLAMA_VERSION=<versione> ./make-deb.sh"
    fi
fi

# ── Compilazione (o riuso della cache) ───────────────────────────────────────
# GGML_NATIVE=OFF: il binario deve girare su qualunque x86-64, non solo sulla
#   macchina che costruisce la ISO.
# Niente download (specifiche, privacy): i modelli arrivano solo dai file
#   scelti dall'utente. Da quando llama.cpp ha abbandonato libcurl
#   (LLAMA_CURL non fa piu' nulla) i download passano da cpp-httplib con
#   OpenSSL, attivo per default se libssl-dev e' installata. Quindi:
#   LLAMA_OPENSSL=OFF        niente HTTPS: il motore non puo' scaricare da
#                            Hugging Face ne' da altri siti HTTPS;
#   LLAMA_USE_PREBUILT_UI=OFF e LLAMA_BUILD_UI=OFF
#                            la compilazione non scarica l'interfaccia web
#                            (i programmi usano --no-webui);
#   LLAMA_CONNECT=OFF        niente strumento che scarica binari.
#   Dopo la compilazione si controlla che i binari non usino OpenSSL o curl.
# LLAMA_BUILD_IS_DEV=OFF e LLAMA_BUILD_COMMIT: l'archivio non e' un
#   repository git, e senza queste llama-server --version direbbe
#   "X.Y.Z-dev" e "commit unknown" (upstream chiede IS_DEV=OFF per i tag).
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
OPZIONI="tag=$TAG commit=$COMMIT backend=$BACKEND native=OFF openssl=OFF ui=OFF shared=ON flags=$FLAGS_FIRMA"
FIRMA=$(printf '%s' "$OPZIONI" | sha256sum | cut -c1-16)
STAGE_CACHE="$CACHE/stage-${LLAMA_CPP_VERSION}-${BACKEND}-${FIRMA}"

if [ -f "$STAGE_CACHE/.completo" ]; then
    say "Uso la compilazione in cache ($BACKEND)"
else
    say "Compilo llama.cpp $TAG ($BACKEND, $JOBS processi): ci vuole tempo"
    BUILD="$CACHE/build-${LLAMA_CPP_VERSION}-${BACKEND}-${FIRMA}"
    rm -rf "$BUILD" "$STAGE_CACHE"
    mkdir -p "$BUILD"
    tar -xzf "$CACHED" -C "$BUILD"
    SORG=$(find "$BUILD" -maxdepth 2 -name CMakeLists.txt -printf '%h\n' | head -1)
    [ -n "$SORG" ] || die "CMakeLists.txt non trovato nell'archivio"

    # Librerie incluse: devono essere tutte dichiarate nel file copyright.
    if [ -d "$SORG/vendor" ]; then
        for v in $(find "$SORG/vendor" -mindepth 1 -maxdepth 1 -type d -printf '%f\n' | sort); do
            case " $VENDOR_DICHIARATI " in
                *" $v "*) ;;
                *) die "llama.cpp $TAG include una libreria nuova: vendor/$v
        Aggiungila al file copyright in make-deb.sh, alle specifiche
        (sezione 6) e a VENDOR_DICHIARATI, poi rilancia." ;;
            esac
        done
    fi

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
        -DLLAMA_OPENSSL=OFF \
        -DLLAMA_BUILD_UI=OFF \
        -DLLAMA_USE_PREBUILT_UI=OFF \
        -DLLAMA_CONNECT=OFF \
        -DLLAMA_BUILD_TESTS=OFF \
        -DLLAMA_BUILD_EXAMPLES=OFF \
        -DLLAMA_BUILD_IS_DEV=OFF \
        -DLLAMA_BUILD_COMMIT="${COMMIT:0:7}" \
        -DCMAKE_BUILD_WITH_INSTALL_RPATH=ON \
        -DCMAKE_INSTALL_RPATH="/${LIBDIR}"
    # shellcheck disable=SC2086
    "${SENZA_RETE[@]}" cmake --build "$SORG/build" --config Release -j"$JOBS" --target $KEEP_BINARIES

    BIN=$(find "$SORG/build" -type f -name llama-server -printf '%h\n' | head -1)
    [ -n "$BIN" ] || die "llama-server non trovato dopo la compilazione"
    mkdir -p "$STAGE_CACHE/bin"
    # cp -a conserva i collegamenti simbolici delle librerie (libllama.so.0 ->
    # libllama.so.0.x.y) invece di duplicarle.
    for d in "$BIN" "$SORG/build/src" "$SORG/build/lib"; do
        [ -d "$d" ] && cp -a "$d"/*.so* "$STAGE_CACHE/bin/" 2>/dev/null || true
    done
    for b in $KEEP_BINARIES; do
        [ -f "$BIN/$b" ] && install -m 755 "$BIN/$b" "$STAGE_CACHE/bin/"
    done
    mkdir -p "$STAGE_CACHE/licenses"
    cp "$SORG/LICENSE" "$STAGE_CACHE/licenses/LICENSE.llama.cpp"
    touch "$STAGE_CACHE/.completo"
    rm -rf "$BUILD"
fi
[ -f "$STAGE_CACHE/bin/llama-server" ] || die "llama-server mancante nella compilazione"

# Niente OpenSSL ne' curl nei binari: senza, il motore non scarica via HTTPS.
RETE=$(cd "$STAGE_CACHE/bin" && for f in *; do [ -L "$f" ] && continue
    LD_LIBRARY_PATH=. ldd "./$f" 2>/dev/null; done \
    | grep -oE 'lib(ssl|crypto|curl)[^ ]*' | sort -u || true)
[ -z "$RETE" ] || die "il motore e' collegato a librerie di rete: $RETE"

# Le opzioni che i programmi passano a llama-server devono esistere.
AIUTO=$(LD_LIBRARY_PATH="$STAGE_CACHE/bin" VK_ICD_FILENAMES=/dev/null \
        VK_DRIVER_FILES=/dev/null timeout 60 "$STAGE_CACHE/bin/llama-server" --help 2>&1 || true)
MANCANO=""
for o in $OPZIONI_USATE; do
    # Here-string e non "printf | grep -q": con pipefail, grep -q che esce
    # alla prima riga trovata fa fallire printf (SIGPIPE) e l'opzione
    # risulterebbe mancante a caso.
    grep -qE -- "(^|[ ,])$o([ ,=]|\$)" <<< "$AIUTO" || MANCANO="$MANCANO $o"
done
[ -z "$MANCANO" ] || die "llama-server di llama.cpp $TAG non riconosce opzioni usate
        da RuscaLLama o RuscaTranslator:$MANCANO
        Adatta i programmi, oppure costruisci la versione precedente:
        RUSCALLAMA_LLAMA_VERSION=<versione> ./make-deb.sh"
say "llama-server accetta tutte le opzioni usate dai programmi"
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
         "$ROOT/etc/apparmor.d/force-complain"
cp -a "$STAGE_CACHE/bin/." "$ROOT/$LIBDIR/"
# Simboli di debug fuori dal pacchetto: decine di MB in meno nella ISO.
find "$ROOT/$LIBDIR" -type f \( -name '*.so*' -o -perm -u+x \) -exec \
    strip --strip-unneeded --remove-section=.comment --remove-section=.note {} \;
find "$ROOT/$LIBDIR" -type f -name '*.so*' -exec chmod 644 {} \;

# Controllo delle librerie: se ne manca una il motore non parte e i programmi
# vedono solo "terminato (codice 127)". Meglio scoprirlo qui.
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
# ruscallama-engine $VER

Motore di inferenza dei RuscaLinux OS Tools RuscaLLama e RuscaTranslator.

**Componente esterno:** llama.cpp $TAG — $UPSTREAM — licenza MIT,
copyright The ggml authors. RuscaLinux lo compila dal sorgente senza
modifiche al codice.

| Voce | Valore |
|---|---|
| Versione di llama.cpp | $LLAMA_CPP_VERSION (ultima release stabile al momento della build) |
| Data della release | ${DATA_RELEASE:-non nota} |
| Commit | $COMMIT |
| SHA-256 dell'archivio sorgente | $OTTENUTO |
| Backend | $BACKEND |
| Ottimizzazioni per CPU specifica | no (GGML_NATIVE=OFF) |
| HTTPS / download dei modelli | no (LLAMA_OPENSSL=OFF, nessuna libreria TLS) |
| Interfaccia web | no (LLAMA_BUILD_UI=OFF, LLAMA_USE_PREBUILT_UI=OFF) |
| Percorso | /$LIBDIR |
| Programmi | $KEEP_BINARIES |

Il server viene avviato dai programmi solo su 127.0.0.1, con una chiave
di accesso temporanea. Il profilo AppArmor
/etc/apparmor.d/$PROFILE e' in modalita' complain.

Per provare il motore dal terminale:

    /$LIBDIR/llama-cli --version
    /$LIBDIR/llama-bench -m modello.gguf
README
gzip -9n "$DOC/README.md"

cat > "$DOC/copyright" <<'COPYRIGHT'
Format: https://www.debian.org/doc/packaging-manuals/copyright-format/1.0/
Upstream-Name: llama.cpp
Upstream-Contact: https://github.com/ggml-org/llama.cpp/issues
Source: https://github.com/ggml-org/llama.cpp
Comment: ruscallama-engine is llama.cpp, an external component, built from
 unmodified source for RuscaLinux. Only the packaging (build script and
 AppArmor profile) is part of RuscaLinux.

Files: *
Copyright: 2023-2026 The ggml authors
License: MIT

Files: vendor/nlohmann/*
Copyright: 2013-2025 Niels Lohmann
License: MIT

Files: vendor/cpp-httplib/*
Copyright: 2017 yhirose
License: MIT

Files: vendor/hash/rotate-bits/*
Copyright: 2021 William Casarin
License: MIT

Files: vendor/hash/xxhash/*
Copyright: 2012-2021 Yann Collet
License: BSD-2-Clause

Files: vendor/hash/sha1/* vendor/hash/sha256/* vendor/stb/* vendor/sheredom/*
 vendor/miniaudio/*
Copyright: none (public domain)
License: public-domain
 These files are dedicated to the public domain by their authors
 (stb_image and miniaudio also offer MIT/MIT-0 as an alternative).

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

License: BSD-2-Clause
 Redistribution and use in source and binary forms, with or without
 modification, are permitted provided that the following conditions are met:
 .
 1. Redistributions of source code must retain the above copyright notice,
    this list of conditions and the following disclaimer.
 2. Redistributions in binary form must reproduce the above copyright notice,
    this list of conditions and the following disclaimer in the documentation
    and/or other materials provided with the distribution.
 .
 THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
 AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
 IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE
 ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE
 LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR
 CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF
 SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS
 INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN
 CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE)
 ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE
 POSSIBILITY OF SUCH DAMAGE.

License: GPL-3+
 This program is free software: you can redistribute it and/or modify it
 under the terms of the GNU General Public License as published by the Free
 Software Foundation, either version 3 of the License, or (at your option)
 any later version.
 .
 On Debian systems, the complete text of the GNU General Public License
 version 3 can be found in "/usr/share/common-licenses/GPL-3".
COPYRIGHT
install -m 644 "$STAGE_CACHE/licenses/LICENSE.llama.cpp" "$DOC/LICENSE.llama.cpp"

cat <<CHANGELOG | gzip -9n > "$DOC/changelog.gz"
$PKG ($VER) unstable; urgency=medium

  * llama.cpp $TAG (ultima release stabile, commit ${COMMIT:0:12})
    compilato dal sorgente (backend $BACKEND).
  * La versione di llama.cpp non e' piu' fissata: make-deb.sh costruisce
    l'ultima release stabile, verificando il commit del tag e registrando
    l'impronta dell'archivio in checksums/.
  * Compilazione senza OpenSSL e senza interfaccia web: LLAMA_CURL non
    ha piu' effetto e i download ora passano da OpenSSL.
  * Controllo che llama-server accetti le opzioni usate da RuscaLLama e
    RuscaTranslator.
  * Binari e librerie in /$LIBDIR; profilo AppArmor in complain.

 -- $MAINT  $(LC_ALL=C date -Ru -d "@$SOURCE_DATE_EPOCH")
CHANGELOG

# ── Dipendenze calcolate dai binari ──────────────────────────────────────────
mkdir -p "$TMP/shlib/debian"
printf 'Source: %s\n\nPackage: %s\nArchitecture: %s\n' "$PKG" "$PKG" "$ARCH" \
    > "$TMP/shlib/debian/control"
SHLIBS=$(cd "$TMP/shlib" && dpkg-shlibdeps -O -l"$ROOT/$LIBDIR" \
    -e"$ROOT/$LIBDIR/llama-server" -e"$ROOT/$LIBDIR/llama-cli" \
    -e"$ROOT/$LIBDIR/llama-bench" \
    $(find "$ROOT/$LIBDIR" -type f -name '*.so*' -printf ' -e%p') 2>/dev/null \
    | sed -n 's/^shlibs:Depends=//p')
[ -n "$SHLIBS" ] || die "dpkg-shlibdeps non ha calcolato le dipendenze"
RECOMMENDS="apparmor"
[ "$BACKEND" = vulkan ] && RECOMMENDS="mesa-vulkan-drivers, $RECOMMENDS"

cat > "$ROOT/DEBIAN/control" <<CONTROL
Package: $PKG
Version: $VER
Section: science
Priority: optional
Architecture: $ARCH
Depends: $SHLIBS
Recommends: $RECOMMENDS
Maintainer: $MAINT
Homepage: $HOMEPAGE
Installed-Size: $(du -sk --exclude=DEBIAN "$ROOT" | cut -f1)
Description: language model engine for RuscaLLama and RuscaTranslator
 Runs local language models (GGUF files) for the RuscaLinux OS Tools
 RuscaLLama and RuscaTranslator. Contains llama-server, plus llama-cli
 and llama-bench for diagnostics.
 .
 This is llama.cpp $TAG, an external component (MIT license,
 $UPSTREAM), built from unmodified source with the
 $BACKEND backend and without HTTPS support, so it cannot download
 models. Vulkan covers NVIDIA, AMD and Intel graphics with one binary and
 falls back to the CPU.
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
say "Pronto: build-deb/$DEB_FILE ($(du -h "$OUT_DIR/$DEB_FILE" | cut -f1)), llama.cpp $TAG, $BACKEND"

# Cache: restano solo sorgente e compilazione della versione appena usata.
find "$CACHE/src" -maxdepth 1 -name 'llama.cpp-v*.tar.gz' ! -name "$ARCHIVE" -delete 2>/dev/null || true
find "$CACHE" -maxdepth 1 -type d \( -name 'stage-*' -o -name 'build-*' \) \
     ! -name "stage-${LLAMA_CPP_VERSION}-*" -exec rm -rf {} + 2>/dev/null || true
if command -v lintian >/dev/null 2>&1; then
    lintian --suppress-tags dir-or-file-in-opt "$OUT_DIR/$DEB_FILE" || true
fi
