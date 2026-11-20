#!/bin/bash
# ---------------------------------------------------------------------------
# RuscaLinux — RuscaLLisse, VERSIONE DI PROVA: prepara i motori precompilati.
#
#   ./prova/prepara-motori.sh
#
# Le specifiche (sezioni 1.8 e 7) vogliono ruscavosk-engine e
# ruscapiper-engine compilati dal sorgente. Prima di fare quel lavoro (Kaldi
# è lungo da compilare) si prova RuscaLLisse con i motori già compilati dei
# pacchetti ufficiali:
#   * vosk        — solo libvosk.so (Apache 2.0); il modulo Python di Vosk
#                   NON si usa: importa librerie di rete;
#   * piper-tts   — Piper con espeak-ng (GPL-3.0);
#   * onnxruntime — il motore delle voci di Piper (MIT): Debian trixie non ha
#                   il modulo Python;
#   * numpy       — richiesto da onnxruntime e Piper (BSD-3-Clause).
# Versioni bloccate e impronte SHA-256 registrate in motori.sha256 alla prima
# preparazione (il file va aggiunto al repository) e confrontate dopo.
# Il risultato va in prova/motori/, che NON si aggiunge al repository.
#
# Serve la rete solo qui, e Python 3.13 come quello di trixie.
# ---------------------------------------------------------------------------
set -euo pipefail
cd "$(dirname "$0")"

VOSK_VER="0.3.45"
PIPER_VER="1.8.0"
ORT_VER="1.32.0"
NUMPY_VER="2.5.5"
PYVER="3.13"
OUT="motori"
SUMS="motori.sha256"

die() { echo "ERRORE: $*" >&2; exit 1; }
command -v python3 >/dev/null || die "serve python3"
python3 -c "import sys; sys.exit(0 if sys.version_info[:2] == (3, 13) else 1)" \
    || die "serve Python $PYVER (quello di Debian trixie)"

TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT
python3 -m venv "$TMP/venv" || die "serve python3-venv"
"$TMP/venv/bin/pip" download -q --no-deps --only-binary=:all: \
    --python-version "$PYVER" --implementation cp --abi cp313 --abi abi3 --abi none \
    --platform manylinux_2_28_x86_64 --platform manylinux_2_27_x86_64 \
    --platform manylinux_2_17_x86_64 --platform manylinux2014_x86_64 \
    --platform manylinux2010_x86_64 --platform linux_x86_64 \
    -d "$TMP/wheels" \
    "vosk==$VOSK_VER" "piper-tts==$PIPER_VER" "onnxruntime==$ORT_VER" "numpy==$NUMPY_VER" \
    || die "download non riuscito"

( cd "$TMP/wheels" && sha256sum -- *.whl ) > "$TMP/sums"
if [ -f "$SUMS" ]; then
    diff -u "$SUMS" "$TMP/sums" || die "le impronte sono cambiate rispetto a $SUMS"
    echo "Impronte uguali a $SUMS."
else
    cp "$TMP/sums" "$SUMS"
    echo "Impronte registrate in $SUMS: aggiungi il file al repository."
fi

rm -rf "$OUT"
mkdir -p "$OUT/python" "$OUT/licenze" "$TMP/x"
for w in "$TMP"/wheels/*.whl; do
    python3 -m zipfile -e "$w" "$TMP/x/"
done
X="$TMP/x"
install -m 644 "$X/vosk/libvosk.so" "$OUT/libvosk.so"
cp -r "$X/piper" "$X/onnxruntime" "$X/numpy" "$OUT/python/"
[ -d "$X/numpy.libs" ] && cp -r "$X/numpy.libs" "$OUT/python/"
# Parti che RuscaLLisse non usa: addestramento, server web, ebraico, cinese;
# strumenti e conversioni di onnxruntime.
rm -rf "$OUT/python/piper/train" "$OUT/python/piper/hebrew" \
       "$OUT/python/piper/http_server.py" "$OUT/python/piper/g2pw_onnx.py" \
       "$OUT/python/onnxruntime/tools" "$OUT/python/onnxruntime/transformers" \
       "$OUT/python/onnxruntime/quantization"
find "$OUT" -name __pycache__ -type d -prune -exec rm -rf {} +
# Licenze
mkdir -p "$OUT/licenze/piper" "$OUT/licenze/onnxruntime" "$OUT/licenze/numpy"
cp -r "$X"/piper_tts-*.dist-info/licenses/. "$OUT/licenze/piper/"
cp "$X/onnxruntime/ThirdPartyNotices.txt" "$OUT/licenze/onnxruntime/" 2>/dev/null || true
find "$X"/onnxruntime-*.dist-info -iname "LICENSE*" -exec cp {} "$OUT/licenze/onnxruntime/" \; || true
cp -r "$X"/numpy-*.dist-info/licenses/. "$OUT/licenze/numpy/" 2>/dev/null || true
cat > "$OUT/VERSIONI" <<EOF
vosk $VOSK_VER (solo libvosk.so)
piper-tts $PIPER_VER
onnxruntime $ORT_VER
numpy $NUMPY_VER
EOF

# Controlli: nessun modulo di rete caricato, funzioni di Vosk presenti.
python3 -I -S - "$OUT" <<'PY' || die "controllo dei motori non riuscito"
import ctypes, os, sys
out = sys.argv[1]
sys.path.insert(0, os.path.join(out, "python"))
from piper import PiperVoice, SynthesisConfig  # noqa: F401
rete = [m for m in sys.modules if m.split(".")[0] in
        ("socket", "http", "urllib3", "requests", "flask", "websockets")]
if rete:
    sys.exit("moduli di rete caricati: %s" % rete)
lib = ctypes.CDLL(os.path.join(out, "libvosk.so"))
for s in ("vosk_set_log_level", "vosk_model_new", "vosk_model_free",
          "vosk_recognizer_new", "vosk_recognizer_free", "vosk_recognizer_set_words",
          "vosk_recognizer_accept_waveform", "vosk_recognizer_result",
          "vosk_recognizer_final_result", "vosk_recognizer_reset"):
    getattr(lib, s)
lib.vosk_set_log_level(-1)
lib.vosk_model_new.restype = ctypes.c_void_p
assert not lib.vosk_model_new(b"/nonexistent"), "vosk_model_new su una cartella vuota"
print("Motori pronti.")
PY
du -sh "$OUT"
