#!/bin/bash
# ---------------------------------------------------------------------------
# RuscaLinux — costruisce il pacchetto ruscavosk-engine.
#
#   ./make-deb.sh
#
# ruscavosk-engine e' il motore di riconoscimento vocale di RuscaLLisse: la
# libreria libvosk.so di Vosk (vosk-api), SOFTWARE ESTERNO con licenza
# Apache-2.0 (https://github.com/alphacep/vosk-api), compilata dal sorgente
# insieme a Kaldi e OpenFst nelle versioni che Vosk usa (rami di Alpha Cephei,
# licenza Apache-2.0). RuscaLLisse la carica con ctypes: niente modulo Python
# vosk, niente server.
# E' fatto come gli altri motori: stesse regole, stessi controlli.
#
# Regole delle specifiche delle RuscaLinux OS Apps (sezioni 1.8 e 7):
#   * versione del pacchetto = versione di RuscaLinux (release.conf); le
#     versioni dei componenti sono scritte nella descrizione e nella
#     documentazione del pacchetto;
#   * un solo .deb in build-deb/, con suffisso -ruscalinux e SHA256SUMS;
#   * architettura amd64: e' codice compilato.
#
# Sorgente: TRE archivi, a versioni fissate qui sotto. Vosk non fissa la
# revisione di Kaldi (la sua ricetta usa la cima del ramo "vosk"), quindi la
# fissa RuscaLinux: si cambia a mano, provando RuscaLLisse.
#   1. vosk-api al tag della release;
#   2. Kaldi, ramo "vosk" di alphacep/kaldi, al commit KALDI_COMMIT;
#   3. OpenFst, alphacep/openfst (OpenFst 1.8.0 con piccole correzioni, fra
#      cui una piu' veloce ricerca di raggiungibilita' usata nella
#      decodifica), al commit OPENFST_COMMIT.
# Ogni archivio si controlla in due modi: il commit scritto nell'archivio
# deve essere quello atteso, e l'impronta SHA-256 si registra in checksums/
# alla prima build e si confronta nelle successive (i file nuovi in
# checksums/ vanno aggiunti al repository).
#
# Calcolo numerico: OpenBLAS di Debian, variante senza thread
# (libopenblas-serial-dev, come Vosk che compila OpenBLAS con USE_THREAD=0);
# delle intestazioni LAPACK serve solo lapacke.h (liblapacke-dev). Kaldi
# chiama le funzioni LAPACK in stile Fortran: con LAPACK >= 3.9 si applica
# patches/kaldi-lapack.patch (lunghezze nascoste degli argomenti stringa).
#
# Tutto gira senza rete (unshare -rn): se qualcosa provasse a scaricare, la
# build fallirebbe.
#
# Variabili utili (facoltative):
#   RUSCAVOSK_CACHE=<dir>    cartella della cache
#   RUSCAVOSK_JOBS=<n>       processi di compilazione (default: il minore
#                            fra i processori e la RAM in GB divisa per 2)
#   RUSCAVOSK_MODEL=<dir>    modello Vosk per la prova vera (facoltativa)
#
# Dipendenze di compilazione:
#   sudo apt install build-essential dpkg-dev wget git python3 \
#                    autoconf automake libtool zlib1g-dev \
#                    libopenblas-serial-dev liblapacke-dev
# ---------------------------------------------------------------------------
set -euo pipefail
cd "$(dirname "$0")"
SRC_DIR="$(pwd)"

# ── Versioni ────────────────────────────────────────────────────────────────
VER="1.99.3"                       # = VERSION in release.conf
VOSK_TAG="v0.3.50"
VOSK_COMMIT="a7bf6a51e299152a8fb496b928a21eb79a1d7bea"
KALDI_COMMIT="bc5baf14231660bd50b7d05788865b4ac6c34481"     # ramo vosk, 2024-08-23
OPENFST_COMMIT="18e94e63870ebcf79ebb42b7035cd3cb626ec090"   # master, 2024-08-23

# Funzioni dell'API di Vosk usate da RuscaLLisse (rusca_vosk.py, SIMBOLI_VOSK):
# la libreria compilata le deve esportare.
SIMBOLI_VOSK="vosk_set_log_level vosk_model_new vosk_model_free
  vosk_recognizer_new vosk_recognizer_free vosk_recognizer_set_words
  vosk_recognizer_accept_waveform vosk_recognizer_result
  vosk_recognizer_final_result vosk_recognizer_reset
  vosk_recognizer_partial_result"

PKG="ruscavosk-engine"
ARCH="amd64"
MAINT="Nunzio Curcuruto <info@ruscalinux.org>"
HOMEPAGE="https://www.ruscalinux.org/"
UPSTREAM="https://github.com/alphacep/vosk-api"
KALDI_UPSTREAM="https://github.com/alphacep/kaldi"
OPENFST_UPSTREAM="https://github.com/alphacep/openfst"
CACHE="${RUSCAVOSK_CACHE:-${XDG_CACHE_HOME:-$HOME/.cache}/ruscalinux/ruscavosk-engine}"
SOURCE_DATE_EPOCH="${SOURCE_DATE_EPOCH:-$(date +%s)}"
# Kaldi compilato con -O3 vuole circa 2 GB per processo.
RAM_GB=$(awk '/MemTotal/ {print int($2 / 1048576)}' /proc/meminfo)
JOBS_RAM=$(( RAM_GB / 2 )); [ "$JOBS_RAM" -ge 1 ] || JOBS_RAM=1
JOBS="${RUSCAVOSK_JOBS:-$(( $(nproc) < JOBS_RAM ? $(nproc) : JOBS_RAM ))}"

LIBDIR="usr/lib/${PKG}"

die() { echo "ERRORE: $*" >&2; exit 1; }
say() { echo "==> $*"; }
avviso() { echo "ATTENZIONE: $*" >&2; }

[ -f patches/kaldi-lapack.patch ] || die "manca patches/kaldi-lapack.patch"

# ── Controllo delle dipendenze, prima di scaricare o compilare ──────────────
MANCA=""
for c in dpkg-deb dpkg-shlibdeps g++ gcc make patch strip nm readelf python3 autoreconf libtoolize; do
    command -v "$c" >/dev/null || MANCA="$MANCA $c"
done
command -v aclocal >/dev/null || MANCA="$MANCA automake"
command -v wget >/dev/null || command -v curl >/dev/null || MANCA="$MANCA wget"
command -v git >/dev/null || MANCA="$MANCA git"
MULTIARCH=$(gcc -print-multiarch 2>/dev/null || echo x86_64-linux-gnu)
BLAS_INC="/usr/include/$MULTIARCH/openblas-serial"
BLAS_LIB="/usr/lib/$MULTIARCH/openblas-serial"
[ -f "$BLAS_INC/cblas.h" ] && [ -f "$BLAS_LIB/libopenblas.so" ] || MANCA="$MANCA libopenblas-serial-dev"
[ -f /usr/include/lapacke.h ] || MANCA="$MANCA liblapacke-dev"
[ -f /usr/include/zlib.h ] || MANCA="$MANCA zlib1g-dev"
if [ -n "$MANCA" ]; then
    echo "ERRORE: mancano strumenti per compilare Vosk:$MANCA" >&2
    echo "  sudo apt install build-essential dpkg-dev wget git python3 \\" >&2
    echo "                   autoconf automake libtool zlib1g-dev \\" >&2
    echo "                   libopenblas-serial-dev liblapacke-dev" >&2
    exit 1
fi
BLAS_VERSIONE=$(dpkg-query -W -f='${Version}' libopenblas-serial-dev 2>/dev/null || echo "?")
say "OpenBLAS (senza thread): $BLAS_VERSIONE; $JOBS processi di compilazione"

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
    if [ "$commit" != "$atteso" ]; then
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
        echo "$ottenuto  $(basename "$file")" > "$pin"
        avviso "$nome e' nuovo: impronta registrata in
            apps/ruscavosk-engine/checksums/$(basename "$pin")
            Aggiungila al repository (git add) insieme alla prossima modifica."
    fi
    echo "$ottenuto"
}

sorgente() {  # repo(owner/nome) rif commit archivio nome
    local repo="$1" rif="$2" commit="$3" archivio="$4" nome="$5" cached="$CACHE/src/$4"
    if [ ! -f "$cached" ]; then
        say "Scarico $nome" >&2
        scarica "https://codeload.github.com/$repo/tar.gz/$rif" "$TMP/$archivio" \
            || die "download di $nome non riuscito"
        mv "$TMP/$archivio" "$cached"
    fi
    local sha
    sha=$(verifica "$cached" "$commit" "$nome")
    say "Sorgente di $nome verificato (commit ${commit:0:12})" >&2
    tail -n 1 <<< "$sha"
}

# ── Sorgenti ────────────────────────────────────────────────────────────────
VOSK_ARCHIVE="vosk-api-${VOSK_TAG}.tar.gz"
KALDI_ARCHIVE="kaldi-${KALDI_COMMIT}.tar.gz"
OPENFST_ARCHIVE="openfst-${OPENFST_COMMIT}.tar.gz"
SHA_VOSK=$(sorgente alphacep/vosk-api "refs/tags/$VOSK_TAG" "$VOSK_COMMIT" "$VOSK_ARCHIVE" "Vosk $VOSK_TAG")
SHA_KALDI=$(sorgente alphacep/kaldi "$KALDI_COMMIT" "$KALDI_COMMIT" "$KALDI_ARCHIVE" "Kaldi ${KALDI_COMMIT:0:12}")
SHA_OPENFST=$(sorgente alphacep/openfst "$OPENFST_COMMIT" "$OPENFST_COMMIT" "$OPENFST_ARCHIVE" "OpenFst ${OPENFST_COMMIT:0:12}")
VOSK_VERSION="${VOSK_TAG#v}"

# ── Compilazione (o riuso della cache) ───────────────────────────────────────
CXXFLAGS_DEB="$(dpkg-buildflags --get CXXFLAGS) $(dpkg-buildflags --get CPPFLAGS)"
LDFLAGS_DEB="$(dpkg-buildflags --get LDFLAGS)"
FLAGS_FIRMA=$(printf '%s %s' "$CXXFLAGS_DEB" "$LDFLAGS_DEB" | sed 's/-ffile-prefix-map=[^ ]*//g')
OPZIONI="vosk=$VOSK_COMMIT kaldi=$KALDI_COMMIT openfst=$OPENFST_COMMIT blas=$BLAS_VERSIONE lapack=$(sha256sum patches/kaldi-lapack.patch | cut -c1-16) flags=$FLAGS_FIRMA"
FIRMA=$(printf '%s' "$OPZIONI" | sha256sum | cut -c1-16)
STAGE_CACHE="$CACHE/stage-${VOSK_VERSION}-${FIRMA}"

SENZA_RETE=()
if unshare -rn true 2>/dev/null; then
    SENZA_RETE=(unshare -rn)
else
    avviso "unshare non disponibile: compilo senza isolare la rete"
fi

if [ -f "$STAGE_CACHE/.completo" ]; then
    say "Uso la compilazione in cache"
else
    BUILD="$CACHE/build-${VOSK_VERSION}-${FIRMA}"
    rm -rf "$BUILD" "$STAGE_CACHE"
    mkdir -p "$BUILD/vosk" "$BUILD/kaldi" "$BUILD/openfst-src" "$BUILD/blas"
    tar -xzf "$CACHE/src/$VOSK_ARCHIVE" -C "$BUILD/vosk" --strip-components=1
    tar -xzf "$CACHE/src/$KALDI_ARCHIVE" -C "$BUILD/kaldi" --strip-components=1
    tar -xzf "$CACHE/src/$OPENFST_ARCHIVE" -C "$BUILD/openfst-src" --strip-components=1

    # 1. OpenFst, come nella ricetta di Vosk (travis/Dockerfile.manylinux):
    #    statico e condiviso (la configurazione di Kaldi --shared vuole il
    #    secondo), con le estensioni far, ngram e lookahead, senza programmi.
    say "Compilo OpenFst (${OPENFST_COMMIT:0:12})"
    ( cd "$BUILD/openfst-src" \
      && "${SENZA_RETE[@]}" autoreconf -i \
      && CFLAGS="-O3" CXXFLAGS="-O3" "${SENZA_RETE[@]}" ./configure --prefix="$BUILD/openfst" \
            --enable-static --enable-shared --enable-far --enable-ngram-fsts \
            --enable-lookahead-fsts --with-pic --disable-bin \
      && "${SENZA_RETE[@]}" make -j"$JOBS" && "${SENZA_RETE[@]}" make install ) \
        > "$BUILD/openfst.log" 2>&1 \
        || { tail -n 30 "$BUILD/openfst.log" >&2; die "compilazione di OpenFst non riuscita (log: $BUILD/openfst.log)"; }

    # 2. Kaldi, solo le parti che servono a Vosk (online2 e rnnlm), con
    #    l'OpenBLAS di Debian. La configurazione di Kaldi vuole OpenBLAS in
    #    <radice>/include e <radice>/lib: si fa una radice di collegamenti.
    say "Compilo Kaldi (${KALDI_COMMIT:0:12}): e' la parte lunga"
    patch -d "$BUILD/kaldi" -p1 --forward --no-backup-if-mismatch -s < "$SRC_DIR/patches/kaldi-lapack.patch" \
        || die "patches/kaldi-lapack.patch non si applica a Kaldi ${KALDI_COMMIT:0:12}: va aggiornata"
    ln -s "$BLAS_INC" "$BUILD/blas/include"
    ln -s "$BLAS_LIB" "$BUILD/blas/lib"
    ( cd "$BUILD/kaldi/src" \
      && "${SENZA_RETE[@]}" ./configure --shared --use-cuda=no --mathlib=OPENBLAS \
            --openblas-root="$BUILD/blas" --fst-root="$BUILD/openfst" --fst-version=1.8.0 ) \
        > "$BUILD/kaldi-configure.log" 2>&1 \
        || { tail -n 30 "$BUILD/kaldi-configure.log" >&2; die "configurazione di Kaldi non riuscita"; }
    # Come la ricetta di Vosk: -O3 invece di -O1. In piu': niente -g (la
    # libreria si spoglia comunque), niente -lgfortran (OpenBLAS di Debian
    # non lo chiede) e nessun RPATH verso le cartelle di compilazione.
    sed -i -e 's: -O1 : -O3 :g' -e 's/^\( *\)-g$/\1/' -e 's: -lgfortran::' \
           -e 's: -Wl,-rpath=[^ ]*::g' -e 's:^OPENFSTLDFLAGS = .*:OPENFSTLDFLAGS =:' \
           "$BUILD/kaldi/src/kaldi.mk"
    ( cd "$BUILD/kaldi/src" && "${SENZA_RETE[@]}" make -j"$JOBS" online2 rnnlm ) \
        > "$BUILD/kaldi-make.log" 2>&1 \
        || { grep -E "error|Error" "$BUILD/kaldi-make.log" | head -n 30 >&2; die "compilazione di Kaldi non riuscita (log: $BUILD/kaldi-make.log)"; }

    # 3. libvosk.so: il Makefile di Vosk, con Kaldi e OpenFst statici dentro
    #    la libreria e OpenBLAS di Debian collegato dinamicamente. Dalle
    #    opzioni di Debian si toglie -O2, che verrebbe dopo il -O3 di Vosk.
    say "Compilo libvosk ($VOSK_TAG)"
    ( cd "$BUILD/vosk/src" && "${SENZA_RETE[@]}" make -j"$JOBS" \
        KALDI_ROOT="$BUILD/kaldi" OPENFST_ROOT="$BUILD/openfst" \
        HAVE_OPENBLAS_CLAPACK=0 USE_SHARED=0 \
        EXTRA_CFLAGS="${CXXFLAGS_DEB//-O2/} -I$BLAS_INC" \
        EXTRA_LDFLAGS="$LDFLAGS_DEB -Wl,-soname,libvosk.so -L$BLAS_LIB -lopenblas -lpthread -ldl" ) \
        > "$BUILD/vosk-make.log" 2>&1 \
        || { grep -E "error|Error|undefined" "$BUILD/vosk-make.log" | head -n 30 >&2; die "compilazione di libvosk non riuscita (log: $BUILD/vosk-make.log)"; }

    mkdir -p "$STAGE_CACHE/bin" "$STAGE_CACHE/licenses"
    install -m 644 "$BUILD/vosk/src/libvosk.so" "$STAGE_CACHE/bin/"
    install -m 644 "$BUILD/vosk/src/vosk_api.h" "$STAGE_CACHE/bin/"
    cp "$BUILD/vosk/COPYING" "$STAGE_CACHE/licenses/COPYING.vosk"
    cp "$BUILD/kaldi/COPYING" "$STAGE_CACHE/licenses/COPYING.kaldi"
    cp "$BUILD/openfst-src/COPYING" "$STAGE_CACHE/licenses/COPYING.openfst"
    touch "$STAGE_CACHE/.completo"
    rm -rf "$BUILD"
fi
BIN="$STAGE_CACHE/bin"
[ -f "$BIN/libvosk.so" ] || die "libvosk.so mancante nella compilazione"

# ── Controlli ────────────────────────────────────────────────────────────────
# L'elenco dei simboli si legge una volta: con pipefail, "nm | grep -q"
# puo' fallire anche quando il simbolo c'e' (grep chiude il tubo e nm
# riceve SIGPIPE).
ESPORTATI=$(nm -D --defined-only "$BIN/libvosk.so" | awk '{print $NF}')
MANCANO=""
for s in $SIMBOLI_VOSK; do
    grep -qx "$s" <<< "$ESPORTATI" || MANCANO="$MANCANO $s"
done
[ -z "$MANCANO" ] || die "libvosk di Vosk $VOSK_TAG non esporta:$MANCANO"
say "libvosk esporta tutte le funzioni usate da RuscaLLisse"

# Niente rete: nessuna libreria TLS o HTTP, nessuna funzione per connessioni.
RETE=$(ldd "$BIN/libvosk.so" 2>/dev/null | grep -oE 'lib(ssl|crypto|curl)[^ ]*' | sort -u || true)
[ -z "$RETE" ] || die "il motore e' collegato a librerie di rete: $RETE"
SOCKET=$(nm -D --undefined-only "$BIN/libvosk.so" 2>/dev/null | awk \
    '{ sub(/@.*/, "", $NF) }
     $NF ~ /^(socket|connect|bind|listen|accept|accept4|getaddrinfo|gethostbyname|sendto|recvfrom)$/ { print $NF }' \
    | sort -u | tr '\n' ' ' || true)
[ -z "$SOCKET" ] || die "il motore contiene codice di rete: $SOCKET"
say "Nessun codice di rete nella libreria"

RP=$(readelf -d "$BIN/libvosk.so" 2>/dev/null | sed -n 's/.*R\(UN\)\?PATH.*\[\(.*\)\]/\2/p')
[ -z "$RP" ] || die "RUNPATH inatteso in libvosk.so: $RP"
NON_TROVATE=$(ldd "$BIN/libvosk.so" 2>/dev/null | grep 'not found' | awk '{print $1}' | sort -u || true)
[ -z "$NON_TROVATE" ] || die "librerie non risolte: $NON_TROVATE"

# Prova: la libreria si carica come la carica RuscaLLisse (ctypes), rifiuta
# senza cadere un modello che non esiste e, se c'e' un modello, lo apre e
# riconosce un secondo di silenzio.
MODELLO="${RUSCAVOSK_MODEL:-}"
if [ -z "$MODELLO" ]; then
    MODELLO=$(ls -d "$HOME"/.local/share/ruscavosk/models/*/ /usr/share/ruscavosk/models/*/ 2>/dev/null | head -n1 || true)
fi
OPENBLAS_NUM_THREADS=1 python3 -I - "$BIN/libvosk.so" "${MODELLO%/}" <<'PY' || die "libvosk non funziona"
import ctypes, json, sys
lib = ctypes.CDLL(sys.argv[1])
lib.vosk_set_log_level(-1)
lib.vosk_model_new.restype = ctypes.c_void_p
lib.vosk_model_new.argtypes = [ctypes.c_char_p]
assert not lib.vosk_model_new(b"/modello/che/non/esiste"), "modello inesistente accettato"
modello = sys.argv[2] if len(sys.argv) > 2 else ""
if not modello:
    print("==> libvosk si carica e rifiuta un modello inesistente (nessun modello per la prova vera)")
    sys.exit(0)
lib.vosk_model_free.argtypes = [ctypes.c_void_p]
lib.vosk_recognizer_new.restype = ctypes.c_void_p
lib.vosk_recognizer_new.argtypes = [ctypes.c_void_p, ctypes.c_float]
lib.vosk_recognizer_accept_waveform.argtypes = [ctypes.c_void_p, ctypes.c_char_p, ctypes.c_int]
lib.vosk_recognizer_final_result.restype = ctypes.c_char_p
lib.vosk_recognizer_final_result.argtypes = [ctypes.c_void_p]
lib.vosk_recognizer_free.argtypes = [ctypes.c_void_p]
m = lib.vosk_model_new(modello.encode())
assert m, f"il modello {modello} non si apre"
r = lib.vosk_recognizer_new(m, 16000.0)
assert r, "riconoscitore non creato"
silenzio = b"\0\0" * 16000
lib.vosk_recognizer_accept_waveform(r, silenzio, len(silenzio))
res = json.loads(lib.vosk_recognizer_final_result(r).decode())
assert "text" in res, res
lib.vosk_recognizer_free(r)
lib.vosk_model_free(m)
print(f"==> Prova con il modello {modello}: aperto, un secondo di silenzio riconosciuto ({res['text']!r})")
PY

# ── Albero del pacchetto ─────────────────────────────────────────────────────
ROOT="$TMP/${PKG}_${VER}_${ARCH}"
DOC="$ROOT/usr/share/doc/$PKG"
mkdir -p "$ROOT/DEBIAN" "$ROOT/$LIBDIR" "$DOC" "$ROOT/usr/share/ruscavosk/models"
install -m 644 "$BIN/libvosk.so" "$ROOT/$LIBDIR/"
strip --strip-unneeded --remove-section=.comment --remove-section=.note "$ROOT/$LIBDIR/libvosk.so"

# ── Documentazione ───────────────────────────────────────────────────────────
cat > "$DOC/README.md" <<README
# ruscavosk-engine $VER

Motore di riconoscimento vocale del RuscaLinux OS App RuscaLLisse.

**Componenti esterni:** Vosk (vosk-api) $VOSK_TAG — $UPSTREAM — licenza
Apache-2.0; Kaldi (ramo vosk di Alpha Cephei) — $KALDI_UPSTREAM — licenza
Apache-2.0; OpenFst (versione di Alpha Cephei, OpenFst 1.8.0 con piccole
correzioni) — $OPENFST_UPSTREAM — licenza Apache-2.0. RuscaLinux li compila dal
sorgente; l'unica modifica (kaldi-lapack.patch, in questa cartella) fa passare
le chiamate LAPACK di Kaldi dalle macro di lapack.h, che aggiungono le
lunghezze degli argomenti stringa richieste da LAPACK >= 3.9.

| Voce | Valore |
|---|---|
| Versione di Vosk | $VOSK_VERSION |
| Commit di Vosk | $VOSK_COMMIT |
| SHA-256 dell'archivio di Vosk | $SHA_VOSK |
| Commit di Kaldi | $KALDI_COMMIT |
| SHA-256 dell'archivio di Kaldi | $SHA_KALDI |
| Commit di OpenFst | $OPENFST_COMMIT |
| SHA-256 dell'archivio di OpenFst | $SHA_OPENFST |
| Calcolo numerico | OpenBLAS di Debian ($BLAS_VERSIONE), collegato dinamicamente |
| Rete | nessuna: nessun socket nella libreria |
| Percorso | /$LIBDIR/libvosk.so |
| Modelli | ~/.local/share/ruscavosk/models/ e /usr/share/ruscavosk/models/ |

I modelli non fanno parte del pacchetto: sono cartelle scaricate da
https://alphacephei.com/vosk/models e importate da RuscaLLisse. Ogni modello
ha la propria licenza.

La libreria e' caricata da RuscaLLisse (ctypes) dentro il suo processo:
lavora sull'audio che riceve in memoria, senza file e senza porte.
README
gzip -9n "$DOC/README.md"
cp "$SRC_DIR/patches/kaldi-lapack.patch" "$DOC/kaldi-lapack.patch"

cat > "$DOC/copyright" <<'COPYRIGHT'
Format: https://www.debian.org/doc/packaging-manuals/copyright-format/1.0/
Upstream-Name: vosk-api, kaldi, openfst
Source: https://github.com/alphacep/vosk-api
 https://github.com/alphacep/kaldi
 https://github.com/alphacep/openfst
Comment: ruscavosk-engine is Vosk (libvosk), Kaldi and OpenFst, external
 components, built from source for RuscaLinux. Kaldi and OpenFst are linked
 statically into libvosk.so; OpenBLAS is the Debian library, linked
 dynamically. Only the build file (make-deb.sh) and kaldi-lapack.patch are
 part of RuscaLinux. kaldi-lapack.patch makes Kaldi call the Fortran LAPACK
 functions through the LAPACK_xxx() macros of lapack.h, which pass the hidden
 string length arguments required with LAPACK >= 3.9.

Files: usr/lib/ruscavosk-engine/libvosk.so
Copyright: 2019-2026 Alpha Cephei Inc.
 2009-2026 Johns Hopkins University, Microsoft Corporation and the Kaldi authors
 2005-2026 Google Inc. and the OpenFst authors
License: Apache-2.0
Comment: The license texts and notices are in this directory
 (COPYING.vosk, COPYING.kaldi, COPYING.openfst).

Files: usr/share/doc/ruscavosk-engine/kaldi-lapack.patch
Copyright: 2026 Nunzio Curcuruto
License: Apache-2.0
Comment: Released under the license of the file it changes. Design,
 specifications and testing by the author; code written with the assistance
 of AI tools. See NOTA-IA.md in the RuscaLinux repository.

License: Apache-2.0
 Licensed under the Apache License, Version 2.0 (the "License"); you may not
 use this file except in compliance with the License.
 .
 On Debian systems, the complete text of the Apache License, Version 2.0 can
 be found in "/usr/share/common-licenses/Apache-2.0".
COPYRIGHT
for f in "$STAGE_CACHE"/licenses/*; do install -m 644 "$f" "$DOC/"; done

cat <<CHANGELOG | gzip -9n > "$DOC/changelog.gz"
$PKG ($VER) unstable; urgency=medium

  * Primo pacchetto: Vosk $VOSK_TAG, Kaldi (commit ${KALDI_COMMIT:0:12}) e
    OpenFst (commit ${OPENFST_COMMIT:0:12}) compilati dal sorgente, senza
    rete, con l'OpenBLAS di Debian.
  * Nessun socket nella libreria (controllato); prova di caricamento e, se
    c'e' un modello, di riconoscimento.

 -- $MAINT  $(LC_ALL=C date -Ru -d "@$SOURCE_DATE_EPOCH")
CHANGELOG

# ── Dipendenze calcolate dalla libreria ──────────────────────────────────────
mkdir -p "$TMP/shlib/debian"
printf 'Source: %s\n\nPackage: %s\nArchitecture: %s\n' "$PKG" "$PKG" "$ARCH" \
    > "$TMP/shlib/debian/control"
SHLIBS=$(cd "$TMP/shlib" && dpkg-shlibdeps -O -e"$ROOT/$LIBDIR/libvosk.so" 2>/dev/null \
    | sed -n 's/^shlibs:Depends=//p')
[ -n "$SHLIBS" ] || die "dpkg-shlibdeps non ha calcolato le dipendenze"

cat > "$ROOT/DEBIAN/control" <<CONTROL
Package: $PKG
Version: $VER
Section: sound
Priority: optional
Architecture: $ARCH
Depends: $SHLIBS
Recommends: libopenblas0-serial
Maintainer: $MAINT
Homepage: $HOMEPAGE
Installed-Size: $(du -sk --exclude=DEBIAN "$ROOT" | cut -f1)
Description: speech recognition engine for RuscaLLisse
 Offline speech recognition with Vosk models for the RuscaLinux OS App
 RuscaLLisse: libvosk.so, loaded by the application in its own process.
 .
 This is Vosk $VOSK_TAG with Kaldi and OpenFst, external components
 (Apache-2.0), built from source with the OpenBLAS of Debian. It has no
 network code: models are folders imported by the user.
CONTROL
find "$ROOT" -type d -exec chmod 755 {} +

# ── Costruzione ──────────────────────────────────────────────────────────────
DEB_FILE="${PKG}-ruscalinux_${VER}_${ARCH}.deb"
dpkg-deb --root-owner-group -Zxz --build "$ROOT" "$OUT_DIR/$DEB_FILE" >/dev/null
( cd "$OUT_DIR" && sha256sum "$DEB_FILE" > SHA256SUMS )
say "Pronto: build-deb/$DEB_FILE ($(du -h "$OUT_DIR/$DEB_FILE" | cut -f1)), Vosk $VOSK_TAG"

# Cache: restano solo sorgenti e compilazione della versione appena usata.
find "$CACHE/src" -maxdepth 1 -type f ! -name "$VOSK_ARCHIVE" ! -name "$KALDI_ARCHIVE" \
     ! -name "$OPENFST_ARCHIVE" -delete 2>/dev/null || true
find "$CACHE" -maxdepth 1 -type d \( -name 'stage-*' -o -name 'build-*' \) \
     ! -name "stage-${VOSK_VERSION}-${FIRMA}" -exec rm -rf {} + 2>/dev/null || true
if command -v lintian >/dev/null 2>&1; then
    lintian "$OUT_DIR/$DEB_FILE" || true
fi
