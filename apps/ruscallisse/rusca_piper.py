# -*- coding: utf-8 -*-
# rusca_piper.py — RuscaLinux OS Apps 1.99.3 — GPL-3.0-or-later
#
# La voce: Piper (piper1-gpl, software esterno, licenza GPL-3.0, con
# espeak-ng) caricato una volta sola, e pw-play (PipeWire, pacchetto Debian
# pipewire-bin) sempre aperto per la riproduzione. Le frasi arrivano in una
# coda e si dicono una dopo l'altra, mentre il modello scrive ancora.
#
# Per il volto si tiene una linea del tempo: per ogni blocco di 20 ms
# d'audio, quando suonerà, quanto è forte e quale visema si vede.
#
# VERSIONE DI PROVA: Piper e ONNX Runtime vengono dai pacchetti ufficiali
# già compilati, in /usr/lib/ruscallisse/prova/python. Nella versione
# definitiva qui ci sarà ruscapiper-stream di ruscapiper-engine
# (specifiche, sezione 1.7.7).
import array
import collections
import json
import math
import os
import queue
import shutil
import subprocess
import sys
import threading
import time

from gi.repository import GLib

try:
    from . import speech_text as st
except ImportError:
    import speech_text as st

VENDOR_DIR = os.environ.get("RUSCALLISSE_PROVA_DIR", "/usr/lib/ruscallisse/prova/python")
PW_PLAY = "/usr/bin/pw-play"
USER_VOICE_DIR = os.path.join(GLib.get_user_data_dir(), "ruscapiper", "voices")
VOICE_DIRS = ("/usr/share/ruscapiper/voices", USER_VOICE_DIR)
# Ritardo fra la scrittura dell'audio e il suono: il volto si sposta di
# tanto (pw-play usa 100 ms se non si dice altro).
PLAY_LATENCY = float(os.environ.get("RUSCALLISSE_LATENCY", "0.10"))
BLOCK = 0.02                                   # s: un blocco del volto


def find_voices():
    """File .onnx che hanno accanto il loro .onnx.json."""
    out = []
    for d in VOICE_DIRS:
        if not os.path.isdir(d):
            continue
        for root, _dirs, files in os.walk(d):
            for name in sorted(files):
                p = os.path.join(root, name)
                if name.endswith(".onnx") and os.path.isfile(p + ".json") and p not in out:
                    out.append(p)
    return out


def voice_info(path):
    """Nome, lingua (codice) e licenza della voce, dal .onnx.json e dal
    MODEL_CARD, se ci sono."""
    info = {"name": os.path.basename(path)[:-5], "lang": "", "licence": "", "dataset": ""}
    try:
        with open(path + ".json", encoding="utf-8") as f:
            cfg = json.load(f)
        lang = cfg.get("language") or {}
        info["lang"] = (lang.get("family") or lang.get("code") or "").split("_")[0]
        info["dataset"] = cfg.get("dataset") or ""
    except (OSError, ValueError, AttributeError):
        pass
    base = path[:-5]
    for card in (base + ".MODEL_CARD", os.path.join(os.path.dirname(path), "MODEL_CARD")):
        try:
            with open(card, encoding="utf-8") as f:
                for line in f:
                    low = line.lower()
                    if "license" in low or "licenza" in low:
                        value = line.split(":", 1)[-1].strip(" *-\t\n")
                        if value and not info["licence"]:
                            info["licence"] = value
                    if low.strip().startswith("* url") and not info["dataset"]:
                        info["dataset"] = line.split(":", 1)[-1].strip()
            break
        except OSError:
            continue
    return info


def import_voice(onnx):
    """Copia .onnx, .onnx.json e l'eventuale MODEL_CARD. Restituisce il
    percorso nuovo; solleva FileNotFoundError se manca il .onnx.json."""
    if not os.path.isfile(onnx + ".json"):
        raise FileNotFoundError(onnx + ".json")
    os.makedirs(USER_VOICE_DIR, exist_ok=True)
    dest = os.path.join(USER_VOICE_DIR, os.path.basename(onnx))
    if os.path.abspath(dest) != os.path.abspath(onnx):
        shutil.copyfile(onnx, dest)
        shutil.copyfile(onnx + ".json", dest + ".json")
        card = os.path.join(os.path.dirname(onnx), "MODEL_CARD")
        if os.path.isfile(card):
            shutil.copyfile(card, dest[:-5] + ".MODEL_CARD")
    return dest


def _import_piper():
    if os.path.isdir(VENDOR_DIR) and VENDOR_DIR not in sys.path:
        sys.path.insert(0, VENDOR_DIR)
    from piper import PiperVoice, SynthesisConfig   # noqa: E402
    return PiperVoice, SynthesisConfig


def _rms(samples):
    if not samples:
        return 0.0
    return math.sqrt(sum(s * s for s in samples) / len(samples)) / 32768.0


class Speaker:
    """Voce caricata e riproduzione. say() mette una frase in coda;
    stop() fa tacere subito; busy dice se sta ancora parlando."""

    def __init__(self, onnx, speed=1.0, debug=False):
        PiperVoice, SynthesisConfig = _import_piper()
        self.voice = PiperVoice.load(onnx)
        self.rate = int(self.voice.config.sample_rate)
        self._cfg_cls = SynthesisConfig
        self.set_speed(speed)
        self.debug = debug
        self._q = queue.Queue()
        self._play = None
        self._lock = threading.Lock()
        self._end = 0.0                 # quando finirà l'audio scritto
        self._gen = 0                   # cambia a ogni stop(): scarta il lavoro vecchio
        self._pending = 0
        self.first_audio = None
        self.timeline = collections.deque(maxlen=6000)   # (t, ampiezza, visema)
        self.on_sentence = None         # callback(emozione) quando una frase comincia
        threading.Thread(target=self._work, daemon=True).start()

    def set_speed(self, speed):
        speed = min(1.3, max(0.7, speed or 1.0))
        self.cfg = self._cfg_cls(length_scale=1.0 / speed)

    # ── riproduzione ─────────────────────────────────────────────────────
    def _player(self):
        if self._play is None or self._play.poll() is not None:
            self._play = subprocess.Popen(
                [PW_PLAY, "--rate", str(self.rate), "--channels", "1",
                 "--format", "s16", "-"],
                stdin=subprocess.PIPE, stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL)
            self._end = 0.0
        return self._play

    def _write(self, data, visemes, gen):
        if gen != self._gen:
            return
        play = self._player()
        n = len(data) // 2
        dur = n / self.rate
        now = time.monotonic()
        with self._lock:
            start = max(now, self._end)
            self._end = start + dur
        # linea del tempo per il volto: un punto ogni 20 ms
        samples = array.array("h")
        samples.frombytes(data[: n * 2])
        step = max(1, int(self.rate * BLOCK))
        blocks = max(1, n // step)
        for b in range(blocks):
            chunk = samples[b * step:(b + 1) * step]
            v = visemes[min(len(visemes) - 1, b * len(visemes) // blocks)] if visemes else ""
            self.timeline.append((start + PLAY_LATENCY + b * BLOCK, _rms(chunk), v))
        if gen != self._gen:
            return
        try:
            play.stdin.write(data)
            play.stdin.flush()
        except (BrokenPipeError, OSError):
            self._play = None

    def _silence(self, seconds, gen):
        self._write(b"\0\0" * int(self.rate * seconds), [""], gen)

    def _work(self):
        while True:
            gen, text, emotion = self._q.get()
            try:
                if gen != self._gen:
                    continue
                if self.on_sentence:
                    GLib.idle_add(self.on_sentence, emotion)
                for chunk in self.voice.synthesize(text, syn_config=self.cfg):
                    if gen != self._gen:
                        break
                    if self.first_audio is None:
                        self.first_audio = time.monotonic()
                    vis = st.visemes(getattr(chunk, "phonemes", []) or [])
                    self._write(chunk.audio_int16_bytes, vis, gen)
                if gen == self._gen:
                    self._silence(0.35 if text.rstrip().endswith("?") else 0.2, gen)
            except Exception as e:                       # noqa: BLE001
                if self.debug:
                    print("ruscallisse: voce:", e, file=sys.stderr)
            finally:
                with self._lock:
                    self._pending -= 1

    # ── interfaccia ──────────────────────────────────────────────────────
    def say(self, text, emotion=None):
        if not text:
            return
        with self._lock:
            self._pending += 1
        self._q.put((self._gen, text, emotion))

    @property
    def busy(self):
        with self._lock:
            return self._pending > 0 or time.monotonic() < self._end + PLAY_LATENCY

    def wait_idle(self, stop_event=None):
        while self.busy:
            if stop_event is not None and stop_event.is_set():
                return False
            time.sleep(0.02)
        return True

    def stop(self):
        """Tace subito: scarta la coda e chiude la riproduzione."""
        self._gen += 1
        try:
            while True:
                self._q.get_nowait()
                with self._lock:
                    self._pending -= 1
        except queue.Empty:
            pass
        play, self._play = self._play, None
        if play is not None:
            try:
                play.kill()
            except OSError:
                pass
        with self._lock:
            self._end = 0.0
        self.timeline.clear()

    def level_at(self, t):
        """(ampiezza, visema) da mostrare all'istante t."""
        tl = self.timeline
        while len(tl) > 1 and tl[1][0] <= t:
            tl.popleft()
        if tl and tl[0][0] <= t < tl[0][0] + BLOCK * 1.5:
            return tl[0][1], tl[0][2]
        return 0.0, ""

    def close(self):
        self.stop()
