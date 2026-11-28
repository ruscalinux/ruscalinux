# -*- coding: utf-8 -*-
# rusca_vosk.py — RuscaLinux OS Apps 1.99.3 — GPL-3.0-or-later
#
# Riconoscimento vocale in tempo reale con Vosk (libvosk.so: software esterno,
# licenza Apache 2.0, copyright Alpha Cephei Inc.), usato direttamente con
# ctypes attraverso la sua API in C. Niente modulo Python «vosk»: quello
# importa librerie di rete (requests) appena lo si carica.
#
# La libreria lavora dentro il processo, sull'audio che riceve in memoria:
# nessun processo in più, nessuna porta, niente file.
import ctypes
import json
import os
import re

from gi.repository import GLib

# RUSCAVOSK_ENGINE_DIR: per provare una libreria compilata a mano.
LIB_DIRS = tuple(filter(None, (os.environ.get("RUSCAVOSK_ENGINE_DIR"),
                               "/usr/lib/ruscavosk-engine")))
USER_MODEL_DIR = os.path.join(GLib.get_user_data_dir(), "ruscavosk", "models")
MODEL_DIRS = ("/usr/share/ruscavosk/models", USER_MODEL_DIR)

# Le funzioni dell'API usate da RuscaLLisse (la build del motore controlla
# che la libreria le esporti).
SIMBOLI_VOSK = (
    "vosk_set_log_level", "vosk_model_new", "vosk_model_free",
    "vosk_recognizer_new", "vosk_recognizer_free", "vosk_recognizer_set_words",
    "vosk_recognizer_accept_waveform", "vosk_recognizer_result",
    "vosk_recognizer_final_result", "vosk_recognizer_reset",
    "vosk_recognizer_partial_result",
)

_lib = None


class VoskError(Exception):
    def __init__(self, key, detail=""):
        super().__init__(f"{key}: {detail}" if detail else key)
        self.key = key
        self.detail = detail


def find_library():
    for d in LIB_DIRS:
        p = os.path.join(d, "libvosk.so")
        if os.path.isfile(p):
            return p
    return None


def _load():
    global _lib
    if _lib is not None:
        return _lib
    path = find_library()
    if not path:
        raise VoskError("err_no_vosk")
    # ruscavosk-engine usa l'OpenBLAS di Debian: se la variante scelta dal
    # sistema e' quella con i thread, Vosk ne userebbe tanti quanti i
    # processori per matrici piccole (la ricetta di Vosk compila OpenBLAS
    # senza thread). OpenBLAS legge la variabile quando viene caricato.
    os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")
    try:
        lib = ctypes.CDLL(path)
    except OSError as e:
        raise VoskError("err_no_vosk", str(e)) from e
    vp, cp, ci = ctypes.c_void_p, ctypes.c_char_p, ctypes.c_int
    sig = {
        "vosk_set_log_level": ([ci], None),
        "vosk_model_new": ([cp], vp),
        "vosk_model_free": ([vp], None),
        "vosk_recognizer_new": ([vp, ctypes.c_float], vp),
        "vosk_recognizer_free": ([vp], None),
        "vosk_recognizer_set_words": ([vp, ci], None),
        "vosk_recognizer_accept_waveform": ([vp, cp, ci], ci),
        "vosk_recognizer_result": ([vp], cp),
        "vosk_recognizer_final_result": ([vp], cp),
        "vosk_recognizer_reset": ([vp], None),
        "vosk_recognizer_partial_result": ([vp], cp),
    }
    for name, (args, res) in sig.items():
        fn = getattr(lib, name)
        fn.argtypes = args
        fn.restype = res
    lib.vosk_set_log_level(-1)
    _lib = lib
    return lib


def is_model(path):
    """Una cartella è un modello Vosk se ha am/final.mdl e conf/."""
    return (os.path.isfile(os.path.join(path, "am", "final.mdl"))
            and os.path.isdir(os.path.join(path, "conf")))


def _size(path):
    total = 0
    for root, _dirs, files in os.walk(path):
        for f in files:
            try:
                total += os.path.getsize(os.path.join(root, f))
            except OSError:
                pass
    return total


def find_models():
    """Cartelle dei modelli, dalla più grande. Si guarda la cartella dei
    modelli e un livello sotto (uno zip scompattato in una cartella omonima)."""
    found = []
    for d in MODEL_DIRS:
        if not os.path.isdir(d):
            continue
        for name in sorted(os.listdir(d)):
            p = os.path.join(d, name)
            if not os.path.isdir(p):
                continue
            if is_model(p):
                found.append(p)
                continue
            try:
                for sub in sorted(os.listdir(p)):
                    q = os.path.join(p, sub)
                    if os.path.isdir(q) and is_model(q):
                        found.append(q)
            except OSError:
                pass
    sizes = {p: _size(p) for p in found}
    found.sort(key=lambda p: sizes[p], reverse=True)
    return found


def model_language(path):
    """Lingua dal nome ufficiale: vosk-model-it-0.22, vosk-model-small-it-0.22."""
    m = re.search(r"vosk-model-(?:small-)?([a-z]{2,3})(?:[-_]|$)", os.path.basename(path))
    return m.group(1) if m else ""


class Recognizer:
    """Un modello e un riconoscitore a 16 kHz, mono, 16 bit."""

    RATE = 16000

    def __init__(self, model_path):
        lib = _load()
        self._lib = lib
        self._model = lib.vosk_model_new(os.fsencode(model_path))
        if not self._model:
            raise VoskError("err_vosk_model", model_path)
        self._rec = lib.vosk_recognizer_new(self._model, float(self.RATE))
        if not self._rec:
            lib.vosk_model_free(self._model)
            raise VoskError("err_vosk_model", model_path)
        lib.vosk_recognizer_set_words(self._rec, 1)

    def accept(self, data):
        """True quando una frase è finita (si legge con result())."""
        return self._lib.vosk_recognizer_accept_waveform(self._rec, data, len(data)) == 1

    def _json(self, raw):
        try:
            return json.loads(raw.decode("utf-8", "replace")) if raw else {}
        except ValueError:
            return {}

    def result(self):
        return self._json(self._lib.vosk_recognizer_result(self._rec))

    def final_result(self):
        return self._json(self._lib.vosk_recognizer_final_result(self._rec))

    def partial(self):
        """Testo della frase in corso (per il terminale, in modalità debug)."""
        return self._json(self._lib.vosk_recognizer_partial_result(self._rec)).get("partial", "")

    def reset(self):
        self._lib.vosk_recognizer_reset(self._rec)

    def close(self):
        if self._rec:
            self._lib.vosk_recognizer_free(self._rec)
            self._rec = None
        if self._model:
            self._lib.vosk_model_free(self._model)
            self._model = None
