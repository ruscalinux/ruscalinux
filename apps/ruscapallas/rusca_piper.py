# -*- coding: utf-8 -*-
# rusca_piper.py — RuscaLinux OS Apps 1.99.3 — GPL-3.0-or-later
#
# La voce: Piper (piper1-gpl, software esterno, licenza GPL-3.0, con
# espeak-ng) caricato una volta sola, e pw-play (PipeWire, pacchetto Debian
# pipewire-bin) sempre aperto per la riproduzione. Le frasi arrivano in una
# coda e si dicono una dopo l'altra, mentre il modello scrive ancora.
#
# Piper parla con ruscapiper-stream di ruscapiper-engine (compilato dal
# sorgente): la voce resta caricata in un processo a parte, che riceve le
# frasi e restituisce audio e fonemi.
#
# Per il volto si tiene una linea del tempo: per ogni blocco di 20 ms
# d'audio, quando suonerà, quanto è forte e quale visema si vede. I visemi
# seguono la durata vera di ogni fonema quando la voce la dà, altrimenti si
# distribuiscono in parti uguali.
import array
import collections
import json
import math
import os
import queue
import shutil
import struct
import subprocess
import sys
import threading
import time

from gi.repository import GLib

try:
    from . import speech_text as st
except ImportError:
    import speech_text as st

STREAM = os.environ.get("RUSCAPIPER_STREAM", "/usr/lib/ruscapiper-engine/ruscapiper-stream")
PW_PLAY = "/usr/bin/pw-play"
USER_VOICE_DIR = os.path.join(GLib.get_user_data_dir(), "ruscapiper", "voices")
VOICE_DIRS = ("/usr/share/ruscapiper/voices", USER_VOICE_DIR)
# Ritardo fra la scrittura dell'audio e il suono: il volto si sposta di
# tanto (pw-play usa 100 ms se non si dice altro).
PLAY_LATENCY = float(os.environ.get("RUSCALLISSE_LATENCY", "0.10"))
BLOCK = 0.02                                   # s: un blocco del volto
# Silenzio all'apertura della riproduzione: l'uscita audio si sveglia e i
# primi istanti andrebbero persi (si sentirebbe la voce già cominciata).
PREROLL = float(os.environ.get("RUSCALLISSE_PREROLL", "0.4"))


_RAW = {}


def pw_raw_args(binary):
    """Opzioni per dati grezzi con pw-play e pw-record. Da PipeWire 1.6 con
    «-» libsndfile cerca un'intestazione (in ingresso) o scrive il formato AU
    (in uscita): serve --raw. Prima --raw non esisteva e «-» era già grezzo.
    Si chiede a --help una volta sola."""
    if binary not in _RAW:
        try:
            out = subprocess.run([binary, "--help"], capture_output=True, text=True,
                                 timeout=5).stdout
        except (OSError, subprocess.SubprocessError):
            out = ""
        _RAW[binary] = ["--raw"] if "--raw" in out else []
    return _RAW[binary]


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


class PiperError(Exception):
    def __init__(self, key, detail=""):
        super().__init__(f"{key}: {detail}" if detail else key)
        self.key = key


# ── ruscapiper-stream ─────────────────────────────────────────────────────
FLAG_LAST, FLAG_ERROR = 1, 2
_HEADER = struct.Struct("<4s6I")         # "RPSC" id flags frequenza campioni fonemi allineamenti


def _read_exact(f, n):
    data = b""
    while len(data) < n:
        part = f.read(n - len(data))
        if not part:
            raise EOFError("ruscapiper-stream si è fermato")
        data += part
    return data


def read_hello(f):
    magic, version = struct.unpack("<4sI", _read_exact(f, 8))
    if magic != b"RPS1":
        raise ValueError("ruscapiper-stream: risposta inattesa all'avvio")
    return version


def read_chunk(f):
    """Un pezzo d'audio di ruscapiper-stream: dizionario con id, flags,
    rate, pcm (bytes a 16 bit), phonemes (codepoint) e alignments."""
    magic, cid, flags, rate, n_s, n_ph, n_al = _HEADER.unpack(_read_exact(f, _HEADER.size))
    if magic != b"RPSC":
        raise ValueError("ruscapiper-stream: pezzo d'audio non valido")
    pcm = _read_exact(f, n_s * 2)
    ph = struct.unpack(f"<{n_ph}I", _read_exact(f, n_ph * 4)) if n_ph else ()
    al = struct.unpack(f"<{n_al}i", _read_exact(f, n_al * 4)) if n_al else ()
    return {"id": cid, "flags": flags, "rate": rate, "pcm": pcm, "phonemes": ph,
            "alignments": al}


def segments(phonemes, alignments):
    """Fonemi e allineamenti di libpiper -> [(visema, campioni)]. I fonemi
    sono gruppi di codepoint ripetuti separati da 0; ogni gruppo di N
    codepoint corrisponde ai prossimi N allineamenti. Se le lunghezze non
    tornano, lista vuota (i visemi si distribuiscono allora in modo uguale)."""
    out, group, k = [], [], 0
    for cp in list(phonemes) + [0]:
        if cp:
            group.append(cp)
            continue
        if not group:
            continue
        n = len(group)
        if k + n > len(alignments):
            return []
        vis = st.visemes([chr(group[0])])
        out.append((vis[0] if vis else "", sum(max(0, a) for a in alignments[k:k + n])))
        k += n
        group = []
    return out


def group_visemes(phonemes):
    """Visemi dai soli fonemi di libpiper, senza durate: un visema per gruppo
    di codepoint. Serve con le voci senza allineamenti (quasi tutte quelle
    pubblicate): il volto li distribuisce in parti uguali sulla frase."""
    out, prev = [], None
    for cp in phonemes:
        if not cp:
            prev = None
            continue
        if cp == prev:
            continue
        prev = cp
        out.extend(st.visemes([chr(cp)]))
    return out


class _StreamVoice:
    """La voce dentro ruscapiper-stream, sempre caricata."""

    def __init__(self, onnx):
        self.rate = 22050
        try:
            with open(onnx + ".json", encoding="utf-8") as f:
                self.rate = int(json.load(f)["audio"]["sample_rate"])
        except (OSError, ValueError, KeyError, TypeError):
            pass
        self.proc = subprocess.Popen([STREAM, "--voice", onnx], stdin=subprocess.PIPE,
                                     stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        # Lo standard error va letto sempre, in un thread: l'ONNX Runtime di
        # Debian vi scrive centinaia di righe "Schema error" a ogni voce
        # (bug Debian #1092898). Senza lettura il tubo si riempie,
        # ruscapiper-stream si ferma e RuscaLLisse resta ad aspettare RPS1.
        self._last_err = collections.deque(maxlen=5)
        threading.Thread(target=self._drain_stderr, daemon=True).start()
        try:
            read_hello(self.proc.stdout)
        except (EOFError, ValueError) as e:
            self.proc.kill()
            self.proc.wait()
            time.sleep(0.05)       # le ultime righe dal thread
            raise RuntimeError("\n".join(self._last_err) or str(e)) from e
        self._id = 0

    def _drain_stderr(self):
        for raw in self.proc.stderr:
            line = raw.decode("utf-8", "replace").rstrip()
            if not line or line.startswith("Schema error"):
                continue
            self._last_err.append(line)
            print(f"ruscapiper-stream: {line}" if not line.startswith("ruscapiper-stream")
                  else line, file=sys.stderr, flush=True)

    def synthesize(self, text, length_scale):
        """Genera (pcm, segmenti) per una frase. Legge sempre fino all'ultimo
        pezzo, così il flusso resta allineato anche se la frase si scarta."""
        self._id += 1
        clean = " ".join(text.replace("\t", " ").split())
        self.proc.stdin.write(f"{self._id}\t{length_scale:.3f}\t{clean}\n".encode("utf-8"))
        self.proc.stdin.flush()
        while True:
            c = read_chunk(self.proc.stdout)
            if c["flags"] & FLAG_ERROR:
                raise RuntimeError("ruscapiper-stream non ha potuto dire la frase")
            if c["rate"]:
                self.rate = c["rate"]
            if c["pcm"]:
                vis = segments(c["phonemes"], c["alignments"]) if c["alignments"] else []
                yield c["pcm"], vis or group_visemes(c["phonemes"])
            if c["flags"] & FLAG_LAST:
                return

    def close(self):
        try:
            self.proc.stdin.close()
            self.proc.wait(timeout=2)
        except (OSError, subprocess.TimeoutExpired):
            self.proc.kill()


def available():
    """C'è ruscapiper-engine?"""
    return os.access(STREAM, os.X_OK)


def _rms(samples):
    if not samples:
        return 0.0
    return math.sqrt(sum(s * s for s in samples) / len(samples)) / 32768.0


class Speaker:
    """Voce caricata e riproduzione. say() mette una frase in coda;
    stop() fa tacere subito; busy dice se sta ancora parlando."""

    def __init__(self, onnx, speed=1.0, debug=False):
        if not available():
            raise PiperError("err_no_piper", STREAM)
        self.voice = _StreamVoice(onnx)
        self.rate = int(self.voice.rate)
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
        self.on_error = None            # callback(chiave, dettaglio): sempre segnalato
        self._error_said = False
        threading.Thread(target=self._work, daemon=True).start()
        self._player()                  # si apre subito, con il silenzio iniziale

    def set_speed(self, speed):
        speed = min(1.3, max(0.7, speed or 1.0))
        self.length_scale = 1.0 / speed

    # ── riproduzione ─────────────────────────────────────────────────────
    def _report(self, key, detail=""):
        print(f"ruscallisse: {key}: {detail}", file=sys.stderr, flush=True)
        if self.on_error and not self._error_said:
            self._error_said = True
            GLib.idle_add(self.on_error, key)

    def _player(self):
        if self._play is None or self._play.poll() is not None:
            if self._play is not None:
                why = ""
                try:
                    why = self._play.stderr.read().decode("utf-8", "replace").strip()
                except (OSError, ValueError, AttributeError):
                    pass
                self._report("err_play", f"pw-play è uscito con il codice "
                                         f"{self._play.returncode}: {why}")
            try:
                self._play = subprocess.Popen(
                    [PW_PLAY, *pw_raw_args(PW_PLAY), "--rate", str(self.rate),
                     "--channels", "1", "--format", "s16", "-"],
                    stdin=subprocess.PIPE, stdout=subprocess.DEVNULL,
                    stderr=subprocess.PIPE)
            except OSError as e:
                self._play = None
                self._report("err_play", str(e))
                raise
            with self._lock:
                self._end = time.monotonic() + PREROLL
            try:
                self._play.stdin.write(b"\0\0" * int(self.rate * PREROLL))
                self._play.stdin.flush()
            except (BrokenPipeError, OSError) as e:
                self._report("err_play", str(e))
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
        timed = bool(visemes) and isinstance(visemes[0], tuple)
        if timed:     # (visema, campioni): la durata vera di ogni fonema
            bounds, acc = [], 0
            for v, count in visemes:
                acc += count
                bounds.append((acc, v))
        for b in range(blocks):
            chunk = samples[b * step:(b + 1) * step]
            if timed:
                mid = b * step + step // 2
                v = next((vv for end, vv in bounds if mid < end), "")
            else:
                v = visemes[min(len(visemes) - 1, b * len(visemes) // blocks)] if visemes else ""
            self.timeline.append((start + PLAY_LATENCY + b * BLOCK, _rms(chunk), v))
        if gen != self._gen:
            return
        try:
            play.stdin.write(data)
            play.stdin.flush()
        except (BrokenPipeError, OSError) as e:
            self._report("err_play", str(e))
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
                for pcm, vis in self.voice.synthesize(text, self.length_scale):
                    if gen != self._gen:
                        continue          # si legge fino in fondo, ma non si suona
                    if self.first_audio is None:
                        self.first_audio = time.monotonic()
                    self._write(pcm, vis, gen)
                if gen == self._gen:
                    self._silence(0.35 if text.rstrip().endswith("?") else 0.2, gen)
            except Exception as e:                       # noqa: BLE001
                self._report("err_voice", f"{type(e).__name__}: {e}")
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
        self.voice.close()
