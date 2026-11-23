# -*- coding: utf-8 -*-
# rusca_voicematch.py — RuscaLinux OS Apps 1.99.3 — GPL-3.0-or-later
#
# «Trova una voce simile»: voci nella lingua del doppiaggio che somigliano a
# quella originale, senza clonarla.
#
#   1. Dal video si prende fino a un minuto di parlato (le battute, se ci
#      sono già i sottotitoli originali, altrimenti tre tratti nel mezzo).
#   2. Se ne misurano tre cose: l'altezza media della voce, quanto varia
#      (voce monotona o espressiva) e la brillantezza (voce cupa o chiara).
#   3. Il modello della voce inventa voci nuove, una per seme, nella lingua
#      del doppiaggio e senza voce di riferimento: l'accento è quello della
#      lingua, per costruzione.
#   4. Le stesse misure sulle voci nuove le ordinano per somiglianza.
#
# Il modello della voce non riceve mai l'audio originale: lo legge solo
# questo modulo, per farne tre numeri. Le voci proposte non sono una copia
# della voce originale; ne condividono il registro, non il timbro.
#
# Privacy e sicurezza: nessun modulo di rete; FFmpeg con percorso assoluto,
# lista di argomenti e -protocol_whitelist file; i file di lavoro stanno in
# una cartella 0700 sotto quella di RuscaDubbing e si cancellano.
import array
import collections
import math
import operator
import os
import random
import re
import shutil
import subprocess
import sys
import tempfile
import threading

from gi.repository import GLib

import rusca_tts as tts

RATE = 4000                 # Hz: basta per l'altezza della voce (50–400 Hz)
WINDOW = 160                # campioni: 40 ms
HOP = 160                   # un'analisi ogni 40 ms
MIN_LAG, MAX_LAG = 10, 80   # 400 Hz … 50 Hz
YIN_THRESHOLD = 0.2
REFERENCE_MS = 60000        # parlato originale da misurare, al massimo
CANDIDATES = 8              # voci da generare per volta
SHOWN = 4                   # voci da proporre

# Il testo che dicono le voci nuove: una decina di secondi, frasi comuni,
# niente parole difficili da accentare. Per le altre lingue, la frase di
# prova di RuscaNarrator.
VOICE_TEXT = {
    "it": "Buongiorno a tutti. Oggi parliamo di come si impara una lingua straniera: "
          "con calma, con curiosità e con un po' di pazienza, giorno dopo giorno.",
    "en": "Good morning, everyone. Today we are going to talk about how to learn a "
          "foreign language: calmly, with curiosity, and with a little patience every day.",
}

Profile = collections.namedtuple("Profile", "pitch spread brightness voiced")
# pitch: altezza mediana in semitoni sopra 55 Hz; spread: quanto varia, in
# semitoni (scarto interquartile); brightness: baricentro dello spettro dei
# tratti di voce, in Hz; voiced: secondi di voce misurati.
Candidate = collections.namedtuple("Candidate", "seed path profile distance")


class MatchError(Exception):
    def __init__(self, key, detail=""):
        super().__init__(f"{key}: {detail}" if detail else key)
        self.key = key
        self.detail = detail


def voice_text(language):
    return VOICE_TEXT.get(language) or tts.sample_text(language)


def hz_to_semitones(hz):
    return 12 * math.log2(hz / 55.0)


def semitones_to_hz(st):
    return 55.0 * 2 ** (st / 12)


# ── misure ──────────────────────────────────────────────────────────────────
def _run(cmd, timeout=600):
    return subprocess.run(cmd, stdin=subprocess.DEVNULL, capture_output=True, timeout=timeout)


def _pcm(ffmpeg, path):
    """Il file come campioni mono a 4 kHz, senza i bassi e gli acuti che non
    servono all'altezza della voce."""
    r = _run([ffmpeg, "-nostdin", "-hide_banner", "-loglevel", "error",
              "-protocol_whitelist", "file", "-i", path, "-vn", "-ac", "1",
              "-af", "highpass=f=50,lowpass=f=900", "-ar", str(RATE),
              "-f", "s16le", "-"])
    if r.returncode != 0:
        raise MatchError("err_audio", r.stderr.decode("utf-8", "replace").strip()[-300:])
    samples = array.array("h")
    samples.frombytes(r.stdout[:len(r.stdout) // 2 * 2])
    if sys.byteorder != "little":
        samples.byteswap()
    return samples


def pitch_track(samples):
    """Altezza di ogni tratto di voce, in Hz (YIN). I tratti senza voce
    (silenzio, rumore, consonanti) non ci sono."""
    n = len(samples)
    if n < WINDOW + MAX_LAG:
        return []
    x = [float(s) for s in samples]
    # Soglia di energia: un tratto più debole di un decimo dei tratti forti
    # è silenzio o fondo.
    energies = []
    for start in range(0, n - WINDOW - MAX_LAG, HOP):
        seg = x[start:start + WINDOW]
        energies.append(sum(map(operator.mul, seg, seg)))
    if not energies:
        return []
    loud = sorted(energies)[int(len(energies) * 0.9)]
    gate = loud * 0.03
    out = []
    mul = operator.mul
    for k, start in enumerate(range(0, n - WINDOW - MAX_LAG, HOP)):
        if energies[k] < gate or energies[k] <= 0:
            continue
        frame = x[start:start + WINDOW + MAX_LAG]
        head = frame[:WINDOW]
        e0 = energies[k]
        # Energia della finestra spostata di tau, aggiornata a ogni passo.
        et = e0
        diffs = [0.0] * (MAX_LAG + 1)
        for tau in range(1, MAX_LAG + 1):
            et += frame[tau + WINDOW - 1] ** 2 - frame[tau - 1] ** 2
            r = sum(map(mul, head, frame[tau:tau + WINDOW]))
            diffs[tau] = e0 + et - 2 * r
        # Differenza normalizzata cumulata (CMNDF).
        running, cmnd = 0.0, [1.0] * (MAX_LAG + 1)
        for tau in range(1, MAX_LAG + 1):
            running += diffs[tau]
            cmnd[tau] = diffs[tau] * tau / running if running > 0 else 1.0
        best = None
        tau = MIN_LAG
        while tau <= MAX_LAG:
            if cmnd[tau] < YIN_THRESHOLD:
                while tau + 1 <= MAX_LAG and cmnd[tau + 1] < cmnd[tau]:
                    tau += 1
                best = tau
                break
            tau += 1
        if best is None or best >= MAX_LAG:
            continue
        # Interpolazione parabolica fra i tre punti intorno al minimo.
        a, b, c = cmnd[best - 1], cmnd[best], cmnd[best + 1]
        den = a - 2 * b + c
        shift = 0.5 * (a - c) / den if den else 0.0
        lag = best + max(-0.5, min(0.5, shift))
        out.append(RATE / lag)
    return out


_CENTROID = re.compile(rb"centroid=([0-9.]+)")
_FLATNESS = re.compile(rb"flatness=([0-9.eE+-]+)")


def brightness(ffmpeg, path):
    """Baricentro mediano dello spettro nei tratti di voce (poco piatti),
    in Hz: più alto per una voce chiara, più basso per una cupa."""
    r = _run([ffmpeg, "-nostdin", "-hide_banner", "-loglevel", "error",
              "-protocol_whitelist", "file", "-i", path, "-vn", "-ac", "1",
              "-af", "aresample=16000,highpass=f=80,"
                     "aspectralstats=measure=centroid+flatness,ametadata=mode=print:file=-",
              "-f", "null", "-"])
    if r.returncode != 0:
        return 0.0
    cents = _CENTROID.findall(r.stdout)
    flats = _FLATNESS.findall(r.stdout)
    values = [float(c) for c, f in zip(cents, flats) if float(f) < 0.25 and float(c) > 0]
    if not values:
        return 0.0
    values.sort()
    return values[len(values) // 2]


def _quantile(values, q):
    values = sorted(values)
    return values[min(len(values) - 1, max(0, int(round(q * (len(values) - 1)))))]


def measure(ffmpeg, path):
    """Profile della voce nel file. MatchError("err_no_voice") se non c'è
    abbastanza voce da misurare (meno di tre secondi)."""
    track = pitch_track(_pcm(ffmpeg, path))
    if len(track) * HOP / RATE < 3.0:
        raise MatchError("err_no_voice")
    st = [hz_to_semitones(f) for f in track]
    # Si tolgono gli errori d'ottava più evidenti: tratti a più di un'ottava
    # dalla mediana.
    med = _quantile(st, 0.5)
    st = [s for s in st if abs(s - med) <= 12]
    return Profile(pitch=_quantile(st, 0.5), spread=_quantile(st, 0.75) - _quantile(st, 0.25),
                   brightness=brightness(ffmpeg, path), voiced=len(st) * HOP / RATE)


def distance(ref, other):
    """Quanto sono diverse due voci, in «semitoni equivalenti»: l'altezza
    pesa di più (è quella che si sente subito), poi la brillantezza (un
    raddoppio vale quattro semitoni), poi la variazione."""
    d = abs(ref.pitch - other.pitch)
    if ref.brightness > 0 and other.brightness > 0:
        d += 0.33 * abs(12 * math.log2(other.brightness / ref.brightness))
    d += 0.5 * abs(ref.spread - other.spread)
    return d


def similarity(d):
    """Percentuale da mostrare: 100 per la stessa voce, 50 a circa cinque
    semitoni di differenza."""
    return max(0, min(100, int(round(100 * math.exp(-d / 7.0)))))


def describe(ref, other):
    """Differenze principali, come chiavi di lang/: ("lower"|"higher"|"",
    "darker"|"brighter"|"", "flatter"|"livelier"|"")."""
    pitch = ("" if abs(other.pitch - ref.pitch) < 1.5 else
             "higher" if other.pitch > ref.pitch else "lower")
    bright = ""
    if ref.brightness > 0 and other.brightness > 0:
        ratio = other.brightness / ref.brightness
        bright = "" if 0.85 <= ratio <= 1.18 else ("brighter" if ratio > 1 else "darker")
    spread = ("" if abs(other.spread - ref.spread) < 1.5 else
              "livelier" if other.spread > ref.spread else "flatter")
    return pitch, bright, spread


# ── parlato originale ───────────────────────────────────────────────────────
def speech_windows(duration_ms, cues=(), total_ms=REFERENCE_MS):
    """Tratti del video da misurare, in ms: le battute (le più lunghe,
    tenute in ordine) fino a total_ms, o senza battute tre tratti di
    venti secondi al 20, 50 e 80 % del video."""
    if cues:
        chosen, total = [], 0
        for cue in sorted(cues, key=lambda c: c.end - c.start, reverse=True):
            length = cue.end - cue.start
            if length < 800:
                continue
            chosen.append((cue.start, cue.end))
            total += length
            if total >= total_ms:
                break
        if chosen:
            return sorted(chosen)
    if duration_ms <= total_ms:
        return [(0, duration_ms)]
    third = total_ms // 3
    return [(max(0, int(duration_ms * f) - third // 2),
             min(duration_ms, int(duration_ms * f) + third // 2)) for f in (0.2, 0.5, 0.8)]


def extract_reference(ffmpeg, media, windows, out_wav):
    """I tratti scelti, uno dopo l'altro, in un WAV mono a 16 kHz: il file
    che si misura e che si può ascoltare per confronto."""
    expr = "+".join(f"between(t,{a / 1000:.3f},{b / 1000:.3f})" for a, b in windows)
    r = _run([ffmpeg, "-nostdin", "-hide_banner", "-loglevel", "error",
              "-protocol_whitelist", "file", "-i", media, "-vn", "-map", "0:a:0",
              "-af", f"aselect='{expr}',asetpts=N/SR/TB", "-ac", "1", "-ar", "16000",
              "-c:a", "pcm_s16le", "-y", out_wav])
    if r.returncode != 0 or not os.path.isfile(out_wav) or os.path.getsize(out_wav) <= 44:
        raise MatchError("err_audio", r.stderr.decode("utf-8", "replace").strip()[-300:])


# ── la ricerca ──────────────────────────────────────────────────────────────
class VoiceSearch:
    """Una ricerca per volta. Callback nel thread dell'interfaccia:
        on_stage(stage, i, n)     stage: "listen" | "voice" (i di n) | "compare"
        on_log(line)
        on_done(error, reference, candidates)
            error: None, "cancelled" o MatchError; reference: (wav, Profile);
            candidates: lista di Candidate dalla più simile (tutte quelle
            generate finora, anche dopo una ricerca «altre voci»).
    """

    def __init__(self, work_dir, on_stage=None, on_log=None, on_done=None):
        self.work_dir = work_dir
        self.on_stage = on_stage or (lambda stage, i=0, n=0: None)
        self.on_log = on_log or (lambda line: None)
        self.on_done = on_done or (lambda error, reference, candidates: None)
        self.running = False
        self.run_dir = None
        self.reference = None
        self.candidates = []
        self._speaker = None
        self._stop = threading.Event()
        self._o = None
        self._seeds = []

    def _emit(self, callback, *args):
        GLib.idle_add(lambda: callback(*args) and False)

    def start(self, media, duration_ms, cues, voice, language, gpu=True, gpu_device="",
              threads=None, count=CANDIDATES):
        """Ascolta la voce originale (una volta sola) e genera count voci."""
        if self.running:
            return
        ffmpeg = tts.find_ffmpeg()
        if not ffmpeg:
            raise MatchError("err_no_ffmpeg")
        if not tts.find_binary():
            raise MatchError("err_no_llm_engine")
        if not voice or not os.path.isfile(voice.model):
            raise MatchError("err_no_voice_model")
        if self.run_dir is None:
            os.makedirs(self.work_dir, mode=0o700, exist_ok=True)
            os.chmod(self.work_dir, 0o700)
            self.run_dir = tempfile.mkdtemp(prefix="voci-", dir=self.work_dir)
        self._o = dict(media=media, duration_ms=duration_ms, cues=list(cues), voice=voice,
                       language=language, gpu=gpu, gpu_device=gpu_device, threads=threads)
        used = {c.seed for c in self.candidates}
        rng = random.SystemRandom()
        self._seeds = []
        while len(self._seeds) < count:
            seed = rng.randrange(1, 2 ** 31 - 1)
            if seed not in used:
                used.add(seed)
                self._seeds.append(seed)
        self._total = count
        self._stop.clear()
        self.running = True
        if self.reference is None:
            self.on_stage("listen", 0, 0)
            threading.Thread(target=self._listen_work, daemon=True).start()
        else:
            self._next_voice()

    def more(self, count=CANDIDATES):
        """Altre voci per lo stesso video."""
        o = self._o
        self.start(o["media"], o["duration_ms"], o["cues"], o["voice"], o["language"],
                   o["gpu"], o["gpu_device"], o["threads"], count)

    def cancel(self):
        self._stop.set()
        if self._speaker is not None:
            self._speaker.cancel()

    def discard(self):
        """Cancella tutto: audio originale e voci di prova."""
        self.cancel()
        if self.run_dir:
            shutil.rmtree(self.run_dir, ignore_errors=True)
        self.run_dir = None
        self.reference = None
        self.candidates = []

    # ── passi ─────────────────────────────────────────────────────────────
    def _listen_work(self):
        o = self._o
        error = None
        try:
            ffmpeg = tts.find_ffmpeg()
            wav = os.path.join(self.run_dir, "originale.wav")
            extract_reference(ffmpeg, o["media"], speech_windows(o["duration_ms"], o["cues"]), wav)
            profile = measure(ffmpeg, wav)
            self.reference = (wav, profile)
            self._emit(self.on_log, "ruscadubbing: voce originale "
                                    f"{semitones_to_hz(profile.pitch):.0f} Hz, "
                                    f"variazione {profile.spread:.1f} st, "
                                    f"brillantezza {profile.brightness:.0f} Hz, "
                                    f"{profile.voiced:.0f} s di voce")
        except MatchError as e:
            error = e
        except (OSError, subprocess.SubprocessError) as e:
            error = MatchError("err_audio", str(e))
        if self._stop.is_set():
            error = "cancelled"
        if error:
            self._emit(self._finish, error)
        else:
            self._emit(self._next_voice)

    def _next_voice(self):
        if self._stop.is_set():
            self._finish("cancelled")
            return False
        if not self._seeds:
            self._finish(None)
            return False
        o = self._o
        seed = self._seeds.pop(0)
        self.on_stage("voice", self._total - len(self._seeds), self._total)
        self._speaker = tts.Speaker(on_log=self.on_log,
                                    on_done=lambda e, p, s, seed=seed: self._voice_done(seed, e, p))
        try:
            self._speaker.start([tts.Piece(voice_text(o["language"]), 0, 0, 0)], o["voice"],
                                language=o["language"], gpu=o["gpu"],
                                gpu_device=o["gpu_device"], threads=o["threads"], seed=seed,
                                normalize=True)
        except tts.TTSError as e:
            self._finish(MatchError(e.key, e.detail))
        return False

    def _voice_done(self, seed, error, path):
        speaker, self._speaker = self._speaker, None
        if error:
            if speaker is not None:
                speaker.discard()
            self._finish("cancelled" if error == "cancelled" or self._stop.is_set()
                         else MatchError(error.key, error.detail))
            return
        dest = os.path.join(self.run_dir, f"voce-{seed}.wav")
        try:
            shutil.copyfile(path, dest)
        except OSError as e:
            speaker.discard()
            self._finish(MatchError("save_error", str(e)))
            return
        speaker.discard()
        threading.Thread(target=self._compare_work, args=(seed, dest), daemon=True).start()

    def _compare_work(self, seed, path):
        try:
            profile = measure(tts.find_ffmpeg(), path)
        except (MatchError, OSError, subprocess.SubprocessError) as e:
            # Una voce che non si riesce a misurare (quasi muta) si scarta.
            self._emit(self.on_log, f"ruscadubbing: voce {seed} scartata ({e})")
            try:
                os.unlink(path)
            except OSError:
                pass
            self._emit(self._next_voice)
            return
        d = distance(self.reference[1], profile)
        self.candidates.append(Candidate(seed, path, profile, d))
        self.candidates.sort(key=lambda c: c.distance)
        self._emit(self.on_log, f"ruscadubbing: voce {seed}: "
                                f"{semitones_to_hz(profile.pitch):.0f} Hz, distanza {d:.1f}")
        self._emit(self._next_voice)

    def _finish(self, error):
        self.running = False
        self._speaker = None
        if error == "cancelled" and self.candidates:
            error = None            # le voci già pronte si possono scegliere
        self.on_stage("compare", 0, 0)
        self.on_done(error, self.reference, list(self.candidates))
        return False
