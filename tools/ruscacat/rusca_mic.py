# -*- coding: utf-8 -*-
# rusca_mic.py — RuscaLinux OS Tools 1.99.3 — GPL-3.0-or-later
#
# L'audio di RuscaCat che non passa dai motori:
#   * il microfono: FFmpeg (pacchetto Debian) legge la sorgente predefinita
#     di GNOME tramite PipeWire (interfaccia PulseAudio) e scrive campioni
#     grezzi, 16 kHz, mono, 16 bit, sul proprio standard output;
#   * il rilevamento del parlato (SpeechDetector): capisce quando l'utente
#     comincia e finisce di parlare, confrontando il volume con il rumore di
#     fondo, che misura da solo;
#   * l'inviluppo di un WAV (envelope), che muove la bocca del gatto;
#   * la divisione in frasi di una risposta che arriva a pezzi
#     (SentenceSplitter), perche' la voce possa partire alla prima frase.
#
# Privacy e sicurezza (specifiche, sezione 11):
#   * nessun modulo di rete; FFmpeg e' avviato con percorso assoluto e lista
#     di argomenti, mai tramite shell, e con -protocol_whitelist file;
#   * il microfono e' aperto solo mentre il gatto ascolta: il processo
#     FFmpeg parte quando l'utente lo chiede e si ferma subito dopo;
#   * l'audio resta in memoria; diventa un file solo la frase da trascrivere,
#     nella cartella di lavoro del programma (permessi 0700), e il chiamante
#     la cancella appena trascritta.
import array
import collections
import math
import os
import re
import signal
import subprocess
import sys
import threading
import wave

from gi.repository import GLib

# RUSCACAT_FFMPEG: per provare un ffmpeg diverso da quello di Debian.
FFMPEG_PATHS = tuple(filter(None, (os.environ.get("RUSCACAT_FFMPEG"), "/usr/bin/ffmpeg")))
# RUSCACAT_MIC_SOURCE: per provare una sorgente diversa da quella scelta in
# Impostazioni → Suono (il nome di una sorgente di `pactl list sources`).
MIC_SOURCE = os.environ.get("RUSCACAT_MIC_SOURCE") or "default"

RATE = 16000                       # Whisper vuole 16 kHz, mono
FRAME_MS = 30
FRAME_SAMPLES = RATE * FRAME_MS // 1000
FRAME_BYTES = FRAME_SAMPLES * 2

PAUSE_MS = (500, 3000)             # limiti della pausa di fine frase
SENSITIVITY = (1, 10)              # limiti della sensibilità


def find_ffmpeg():
    for p in FFMPEG_PATHS:
        if os.path.isfile(p) and os.access(p, os.X_OK):
            return p
    return None


def frame_db(frame):
    """Volume di un blocco di campioni a 16 bit, in dBFS (da -100 a 0)."""
    samples = array.array("h")
    samples.frombytes(frame[:len(frame) // 2 * 2])
    if sys.byteorder != "little":
        samples.byteswap()
    if not samples:
        return -100.0
    power = sum(s * s for s in samples) / len(samples)
    if power <= 0:
        return -100.0
    return max(-100.0, 10 * math.log10(power / (32768.0 * 32768.0)))


# ── rilevamento del parlato ─────────────────────────────────────────────────
class SpeechDetector:
    """Riceve l'audio a blocchi di 30 ms e restituisce le frasi dette.

    Il rumore di fondo si misura da solo: nei primi 450 ms (si prende il
    volume dei blocchi piu' silenziosi, cosi' una parola detta subito non
    conta), poi scende subito quando la stanza si fa piu' silenziosa e sale
    piano, solo fuori dal parlato: una ventola accesa diventa rumore, non
    voce. Il parlato
    comincia quando il volume supera il rumore di un margine (piu'
    sensibilita', meno margine) per 150 ms, e finisce dopo `pause_ms` di
    silenzio. Si tengono 300 ms prima dell'inizio, perche' la prima sillaba
    non si perda, e 200 ms dopo la fine. Una frase piu' corta di 250 ms di
    voce e' un rumore e si scarta; una piu' lunga di `max_ms` si chiude."""

    CALIBRATION = 15               # 450 ms per misurare il rumore
    START_FRAMES = 5               # 150 ms sopra la soglia
    PRE_ROLL = 10                  # 300 ms prima dell'inizio
    TAIL_FRAMES = 7                # 210 ms dopo la fine
    MIN_VOICED = 8                 # 240 ms di voce
    FLOOR_START = -55.0
    FLOOR_LIMITS = (-75.0, -25.0)

    def __init__(self, sensitivity=5, pause_ms=900, max_ms=30000):
        sensitivity = min(SENSITIVITY[1], max(SENSITIVITY[0], int(sensitivity)))
        self.margin = 21.0 - 1.5 * sensitivity        # 5 → 13,5 dB sopra il rumore
        self.pause_frames = max(1, int(pause_ms) // FRAME_MS)
        self.max_frames = max(self.START_FRAMES + 1, int(max_ms) // FRAME_MS)
        self.floor = self.FLOOR_START
        self._calibration = []
        self.reset()

    def reset(self):
        self.speaking = False
        self._recent = collections.deque(maxlen=self.PRE_ROLL)
        self._above = 0
        self._frames = []
        self._silent = 0
        self._voiced = 0

    @property
    def threshold(self):
        return max(self.floor + self.margin, -60.0)

    def level(self, db):
        """Volume da 0 a 1 rispetto al rumore di fondo, per l'indicatore."""
        return min(1.0, max(0.0, (db - self.floor) / 35.0))

    def _track_floor(self, db):
        lo, hi = self.FLOOR_LIMITS
        if db < self.floor:
            self.floor = 0.7 * self.floor + 0.3 * db
        else:
            # Sale piano: circa 3 secondi per raggiungere un rumore nuovo.
            self.floor = 0.99 * self.floor + 0.01 * db
        self.floor = min(hi, max(lo, self.floor))

    def feed(self, frame):
        """Un blocco di 30 ms. Restituisce (volume 0–1, frase o None): la
        frase sono i campioni grezzi, gia' con il margine prima e dopo."""
        db = frame_db(frame)
        if self._calibration is not None:
            self._recent.append(frame)
            self._calibration.append(db)
            if len(self._calibration) >= self.CALIBRATION:
                quiet = sorted(self._calibration)[len(self._calibration) // 5]
                lo, hi = self.FLOOR_LIMITS
                self.floor = min(hi, max(lo, quiet))
                self._calibration = None
            return self.level(db), None
        loud = db >= self.threshold
        if not self.speaking:
            self._recent.append(frame)
            self._above = self._above + 1 if loud else 0
            if self._above >= self.START_FRAMES:
                self.speaking = True
                self._frames = list(self._recent)
                self._voiced = self._above
                self._silent = 0
            else:
                self._track_floor(db)
            return self.level(db), None
        self._frames.append(frame)
        if loud:
            self._silent = 0
            self._voiced += 1
        else:
            self._silent += 1
        if self._silent >= self.pause_frames or len(self._frames) >= self.max_frames:
            keep = len(self._frames) - max(0, self._silent - self.TAIL_FRAMES)
            frames, voiced = self._frames[:keep], self._voiced
            self.reset()
            if voiced >= self.MIN_VOICED:
                return self.level(db), b"".join(frames)
        return self.level(db), None


def write_wav(path, pcm, rate=RATE):
    """Campioni grezzi (16 bit, mono) in un file WAV."""
    with wave.open(path, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(pcm)


# ── microfono ───────────────────────────────────────────────────────────────
class MicError(Exception):
    """Errore con un messaggio per l'utente: `key` e' la chiave di traduzione."""

    def __init__(self, key, detail=""):
        super().__init__(f"{key}: {detail}" if detail else key)
        self.key = key
        self.detail = detail


class Microphone:
    """Ascolto dal microfono. Le callback arrivano nel thread
    dell'interfaccia (GLib.idle_add):
        on_level(volume)        da 0 a 1, circa 30 volte al secondo
        on_utterance(pcm)       una frase finita: campioni a 16 kHz, mono
        on_stopped(error)       None se fermato da stop(), altrimenti MicError
    Dopo una frase l'ascolto continua; il chiamante lo ferma con stop()
    quando il gatto deve pensare o parlare, perche' non senta se stesso."""

    def __init__(self, on_level=None, on_utterance=None, on_stopped=None, on_log=None):
        self.on_level = on_level or (lambda level: None)
        self.on_utterance = on_utterance or (lambda pcm: None)
        self.on_stopped = on_stopped or (lambda error: None)
        self.on_log = on_log or (lambda line: None)
        self._proc = None
        self._lock = threading.Lock()
        self._stop = threading.Event()
        self._thread = None

    @property
    def running(self):
        return self._thread is not None and self._thread.is_alive()

    def command(self):
        return [find_ffmpeg(), "-nostdin", "-hide_banner", "-loglevel", "error",
                "-protocol_whitelist", "file", "-f", "pulse", "-name", "RuscaCat",
                "-fragment_size", str(FRAME_BYTES * 2), "-i", MIC_SOURCE,
                "-ac", "1", "-ar", str(RATE), "-f", "s16le", "-"]

    def start(self, sensitivity=5, pause_ms=900):
        if self.running:
            return
        if not find_ffmpeg():
            raise MicError("err_no_ffmpeg")
        self._stop.clear()
        detector = SpeechDetector(sensitivity, pause_ms)
        self._thread = threading.Thread(target=self._work, args=(detector,), daemon=True)
        self._thread.start()

    def stop(self):
        """Chiude il microfono; on_stopped arriva con None."""
        self._stop.set()
        with self._lock:
            proc = self._proc
        if proc is not None and proc.poll() is None:
            try:
                os.killpg(os.getpgid(proc.pid), signal.SIGTERM)
            except OSError:
                pass

    def wait(self, timeout=None):
        if self._thread is not None:
            self._thread.join(timeout)

    def _emit(self, callback, *args):
        GLib.idle_add(lambda: callback(*args) and False)

    def _work(self, detector):
        cmd = self.command()
        self._emit(self.on_log, "$ " + " ".join(cmd))
        error = None
        tail = collections.deque(maxlen=8)
        try:
            proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                    stdin=subprocess.DEVNULL, start_new_session=True)
        except OSError as e:
            self._emit(self.on_stopped, MicError("err_mic", str(e)))
            return
        with self._lock:
            self._proc = proc

        def read_stderr():
            for raw in iter(proc.stderr.readline, b""):
                line = raw.decode("utf-8", "replace").rstrip()
                tail.append(line)
                self._emit(self.on_log, line)
        reader = threading.Thread(target=read_stderr, daemon=True)
        reader.start()
        try:
            pending = b""
            while not self._stop.is_set():
                data = proc.stdout.read(FRAME_BYTES)
                if not data:
                    break
                pending += data
                while len(pending) >= FRAME_BYTES and not self._stop.is_set():
                    frame, pending = pending[:FRAME_BYTES], pending[FRAME_BYTES:]
                    level, utterance = detector.feed(frame)
                    self._emit(self.on_level, level)
                    if utterance:
                        self._emit(self.on_utterance, utterance)
            code = proc.wait() if self._stop.is_set() else proc.wait(timeout=5)
            if not self._stop.is_set():
                error = MicError("err_mic", "\n".join(t for t in tail if t) or f"ffmpeg: {code}")
        except (OSError, ValueError, subprocess.TimeoutExpired) as e:
            if not self._stop.is_set():
                error = MicError("err_mic", str(e))
        finally:
            if proc.poll() is None:
                try:
                    os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
                except OSError:
                    pass
                proc.wait()
            reader.join(2)
            proc.stdout.close()
            proc.stderr.close()
            with self._lock:
                self._proc = None
        self._emit(self.on_stopped, error)


# ── bocca del gatto ─────────────────────────────────────────────────────────
ENVELOPE_MS = 20


def envelope(path, step_ms=ENVELOPE_MS):
    """Apertura della bocca (da 0 a 1) ogni `step_ms` di un WAV a 16 bit,
    dal volume della voce: il valore piu' alto dell'audio vale 1, il
    silenzio 0. Lista vuota se il file non si legge."""
    try:
        with wave.open(path, "rb") as w:
            if w.getsampwidth() != 2 or w.getnchannels() != 1:
                return []
            rate = w.getframerate()
            step = max(1, rate * step_ms // 1000)
            values = []
            while True:
                data = w.readframes(step)
                if not data:
                    break
                values.append(frame_db(data))
    except (OSError, EOFError, wave.Error):
        return []
    if not values:
        return []
    top = max(values)
    low = max(top - 30.0, -60.0)
    span = max(1.0, top - low)
    return [min(1.0, max(0.0, (v - low) / span)) ** 0.8 for v in values]


def envelope_at(env, ms, step_ms=ENVELOPE_MS):
    if not env:
        return 0.0
    i = int(ms // step_ms)
    return env[i] if 0 <= i < len(env) else 0.0


# ── frasi di una risposta che arriva a pezzi ────────────────────────────────
_SENTENCE = re.compile(r"[.!?…。！？]+[\"'»”)\]*_]*(?:\s+|$)")
_CLAUSE = re.compile(r"[,;:，；：]\s+")


class SentenceSplitter:
    """Riceve il testo della risposta come arriva dal modello e restituisce
    le frasi complete da far leggere alla voce. Ogni pezzo ha almeno
    `min_chars` caratteri (i pezzi corti si uniscono: ogni pezzo e' un
    avvio di llama-tts), tranne il primo, che parte appena c'e' una frase
    o, se la frase e' lunga, una virgola dopo `first_clause` caratteri:
    cosi' il gatto comincia a parlare prima."""

    def __init__(self, min_chars=40, max_chars=240, first_clause=60):
        self.min_chars = min_chars
        self.max_chars = max_chars
        self.first_clause = first_clause
        self.buf = ""
        self.first = True

    def feed(self, text):
        self.buf += text
        out = []
        while True:
            piece = self._next()
            if not piece:
                return out
            out.append(piece)

    def _next(self):
        start = 0
        need = 1 if self.first else self.min_chars
        for m in _SENTENCE.finditer(self.buf):
            if m.end() == len(self.buf) and not self.buf[-1:].isspace():
                break                          # "3." potrebbe essere "3.5"
            if m.end() - start >= need or m.end() >= self.max_chars:
                return self._take(m.end())
        if self.first and len(self.buf) >= self.first_clause:
            for m in _CLAUSE.finditer(self.buf, self.first_clause // 2):
                return self._take(m.end())
        if len(self.buf) >= self.max_chars:
            cut = self.buf.rfind(" ", 0, self.max_chars)
            return self._take(cut if cut > self.max_chars // 3 else self.max_chars)
        return None

    def _take(self, end):
        piece, self.buf = self.buf[:end].strip(), self.buf[end:]
        if piece:
            self.first = False
        return piece

    def flush(self):
        piece, self.buf = self.buf.strip(), ""
        return piece


# ── trascrizioni da scartare ────────────────────────────────────────────────
# Su un rumore o su un silenzio Whisper a volte «sente» frasi viste nei
# sottotitoli con cui e' stato addestrato. Si scartano solo quando sono tutta
# la frase.
_HALLUCINATIONS = (
    "sottotitoli creati dalla comunità amara.org", "sottotitoli a cura di qtss",
    "grazie per la visione", "sottotitoli e revisione a cura di qtss",
    "thank you for watching", "thanks for watching", "subtitles by the amara.org community",
    "you", "untertitel der amazon.de community", "untertitel im auftrag des zdf",
    "sous-titres réalisés par la communauté d'amara.org", "sous-titrage st' 501",
    "subtítulos realizados por la comunidad de amara.org", "gracias por ver el video",
)
_PUNCT = re.compile(r"[.!?…,«»\"“”']")


def _normal(text):
    return " ".join(_PUNCT.sub(" ", text.lower()).split())


_HALLUCINATIONS = frozenset(_normal(t) for t in _HALLUCINATIONS)
_ONLY_SOUNDS = re.compile(r"^(?:\s|\[[^\]]*\]|\([^)]*\)|[♪♫*.…,!?-])*$")


def is_noise(text):
    """Vero se la trascrizione non contiene parole dette: vuota, solo
    descrizioni di suoni ("[Musica]", "(applausi)") o una frase tipica di
    Whisper sul silenzio."""
    if _ONLY_SOUNDS.match(text or ""):
        return True
    return _normal(text) in _HALLUCINATIONS
