# -*- coding: utf-8 -*-
# conversation.py — RuscaLinux OS Apps 1.99.3 — GPL-3.0-or-later
#
# Il turno di conversazione, in un thread di lavoro:
#   ascolto (pw-record → Vosk) → pensa (llama-server, in streaming)
#   → parla (Piper, una frase alla volta) → ascolto.
# Nessun modello si ricarica durante la conversazione e ogni passo comincia
# prima che il precedente finisca (specifiche, sezione 1.7.1).
#
# La conversazione resta solo in memoria: non si mostra e non si salva.
# Con RUSCALLISSE_DEBUG=1 si scrivono sul terminale i tempi di ogni turno;
# con RUSCALLISSE_DEBUG=2 anche ciò che è stato capito e la risposta.
import array
import math
import os
import subprocess
import sys
import threading
import time

from gi.repository import GLib

try:
    from . import speech_text as st
    from .rusca_piper import pw_raw_args
except ImportError:
    import speech_text as st
    from rusca_piper import pw_raw_args

PW_RECORD = "/usr/bin/pw-record"
DEBUG = int(os.environ.get("RUSCALLISSE_DEBUG", "0") or 0)
FRAME = 640                       # 20 ms a 16 kHz, 16 bit
HISTORY_TURNS = 20
# I modelli che ragionano scrivono prima il ragionamento: il limite di token
# deve lasciare spazio anche alla risposta (la sua lunghezza la tiene corta
# il prompt, regola 2).
MAX_TOKENS = 2048
# Fine della frase: Vosk la dichiara da solo solo dopo un silenzio pulito, e
# con un po' di rumore di fondo (una ventola) non lo fa mai. Per questo la
# frase finisce anche quando il testo riconosciuto non cambia per PAUSE
# secondi, come fa una persona che aspetta che l'altro abbia finito.
PAUSE = 0.8
PARTIAL_EVERY = 5                 # testo parziale ogni 5 blocchi (100 ms)


def _log(*args):
    print("ruscallisse:", *args, file=sys.stderr, flush=True)


def _rms(data):
    a = array.array("h")
    a.frombytes(data[: len(data) // 2 * 2])
    if not a:
        return 0.0
    return math.sqrt(sum(s * s for s in a) / len(a)) / 32768.0


class Conversation:
    """Callback (sempre nel thread dell'interfaccia):
      on_state(stato)   "listening" | "thinking" | "speaking" | "paused" | "error"
      on_level(livello) livello del microfono, da 0 a 1
      on_error(chiave)
    `get_prompt()` restituisce il prompt di sistema aggiornato (l'entità si
    rilegge a ogni turno, così le modifiche valgono subito)."""

    def __init__(self, recognizer, speaker, engine, get_prompt, max_tokens,
                 on_state, on_level, on_error, greeting="", on_notice=None,
                 pause=PAUSE):
        self.rec = recognizer
        self.speaker = speaker
        self.engine = engine
        self.get_prompt = get_prompt
        self.max_tokens = max_tokens
        self.on_state = on_state
        self.on_level = on_level
        self.on_error = on_error
        self.greeting = greeting
        self.on_notice = on_notice or (lambda key: False)
        self._reasoning_said = False
        self._partial = ""
        self._partial_since = 0.0
        self._frames = 0
        self.pause = pause
        self.history = []
        self.state = None
        self._paused = threading.Event()
        self._quit = threading.Event()
        self._interrupt = threading.Event()
        self._mic = None
        self._thread = None
        self._last_level = 0.0
        self._mic_failures = 0

    # ── comandi dall'interfaccia ─────────────────────────────────────────
    def start(self):
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def set_paused(self, paused):
        if paused:
            self._paused.set()
            self.interrupt()
            self._stop_mic()
        else:
            self._paused.clear()

    @property
    def paused(self):
        return self._paused.is_set()

    def interrupt(self):
        """Esc: tace subito e torna ad ascoltare."""
        self._interrupt.set()
        self.engine.cancel()
        self.speaker.stop()

    def restart(self):
        """Ricomincia: dimentica la conversazione."""
        self.interrupt()
        self.history = []

    def quit(self, timeout=5.0):
        """Ferma il thread e lo aspetta: il riconoscitore si può liberare solo
        dopo (liberarlo mentre il thread lo usa fa cadere Vosk). Restituisce
        False se il thread non si è fermato in tempo."""
        self._quit.set()
        self.interrupt()
        self._stop_mic()
        if self._thread is not None and self._thread is not threading.current_thread():
            self._thread.join(timeout)
            return not self._thread.is_alive()
        return True

    # ── interni ──────────────────────────────────────────────────────────
    def _set_state(self, state):
        if state != self.state:
            self.state = state
            GLib.idle_add(self.on_state, state)

    def _start_mic(self):
        self._mic = subprocess.Popen(
            [PW_RECORD, *pw_raw_args(PW_RECORD), "--rate", "16000", "--channels", "1",
             "--format", "s16", "-"],
            stdout=subprocess.PIPE, stdin=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    def _stop_mic(self):
        mic, self._mic = self._mic, None
        if mic is not None:
            try:
                mic.terminate()
                mic.wait(timeout=2)
            except (OSError, subprocess.TimeoutExpired):
                try:
                    mic.kill()
                except OSError:
                    pass

    def _drain_mic(self):
        """Butta l'audio arrivato mentre l'entità parlava (niente eco)."""
        mic = self._mic
        if mic is None:
            return
        fd = mic.stdout.fileno()
        os.set_blocking(fd, False)
        try:
            while True:
                try:
                    data = os.read(fd, 65536)
                except BlockingIOError:
                    break
                if not data:
                    break
        finally:
            os.set_blocking(fd, True)

    def _say_greeting(self):
        if self.greeting:
            self._set_state("speaking")
            self.speaker.say(self.greeting, "sorride")
            self.history.append({"role": "assistant", "content": self.greeting})
            self.speaker.wait_idle(self._interrupt)

    def _run(self):
        """Il ciclo non deve mai morire in silenzio: un errore si segnala e
        si torna ad ascoltare."""
        while not self._quit.is_set():
            try:
                self._loop()
                return
            except Exception as e:                   # noqa: BLE001
                _log("errore:", f"{type(e).__name__}: {e}")
                GLib.idle_add(self.on_error, "err_internal")
                self._stop_mic()
                time.sleep(0.5)

    def _loop(self):
        try:
            self._say_greeting()
        except Exception as e:                       # noqa: BLE001
            if DEBUG:
                _log("saluto:", e)
        self._interrupt.clear()
        while not self._quit.is_set():
            if self._paused.is_set():
                self._set_state("paused")
                time.sleep(0.1)
                continue
            if self._mic is None or self._mic.poll() is not None:
                try:
                    self._start_mic()
                    self.rec.reset()
                except OSError as e:
                    _log("microfono:", e)
                    GLib.idle_add(self.on_error, "err_mic")
                    self._paused.set()
                    continue
            self._set_state("listening")
            data = self._mic.stdout.read(FRAME)
            if not data:
                code = self._mic.poll()
                if not self._paused.is_set() and not self._quit.is_set():
                    _log("microfono: pw-record si è fermato", code)
                    self._mic_failures += 1
                    if self._mic_failures >= 3:
                        GLib.idle_add(self.on_error, "err_mic")
                        self._paused.set()
                    time.sleep(0.5)
                self._mic = None
                continue
            self._mic_failures = 0
            level = min(1.0, _rms(data) * 6.0)
            if abs(level - self._last_level) > 0.02:
                self._last_level = level
                GLib.idle_add(self.on_level, level)
            if self._quit.is_set():
                break
            if self.rec.accept(data):
                raw = self.rec.result()
                ended_by = "vosk"
            else:
                self._frames += 1
                if self._frames % PARTIAL_EVERY:
                    continue
                now = time.monotonic()
                p = self.rec.partial()
                if p != self._partial:
                    self._partial, self._partial_since = p, now
                    if DEBUG >= 2 and p:
                        _log("sento:", p)
                    continue
                if not p or now - self._partial_since < self.pause:
                    continue
                raw = self.rec.final_result()      # la frase è finita: si chiude
                ended_by = "pausa"
            self._partial = ""
            t_end = time.monotonic()
            if DEBUG >= 2:
                _log(f"fine della frase ({ended_by})")
            text, conf = st.listen_filter(raw)
            if not text:
                if DEBUG >= 2 and raw.get("text"):
                    _log("ignorato (solo rumore):", raw.get("text"))
                continue
            self._turn(text, conf, t_end)
            if self._quit.is_set():
                break
            self._drain_mic()
            self.rec.reset()
            GLib.idle_add(self.on_level, 0.0)
        self._stop_mic()

    def _turn(self, text, conf, t_end):
        self._interrupt.clear()
        if DEBUG >= 2:
            _log(f"capito (fiducia {conf:.2f}): {text}")
        self._set_state("thinking")
        self.history.append({"role": "user", "content": text})
        messages = [{"role": "system", "content": self.get_prompt()}] + self.history[-HISTORY_TURNS:]
        body = {"messages": messages, "max_tokens": MAX_TOKENS, "temperature": 0.7,
                "cache_prompt": True, "reasoning_effort": "none",
                "chat_template_kwargs": {"enable_thinking": False}}
        sentences = st.Sentences()
        answer = ""
        t_token = t_first = None
        reasoning = 0
        self.speaker.first_audio = None
        try:
            for piece, thought in self.engine.chat_stream(body, self._interrupt, timeout=300):
                if thought:
                    reasoning += len(thought)
                    if not self._reasoning_said:
                        self._reasoning_said = True
                        GLib.idle_add(self.on_notice, "notice_reasoning")
                if not piece:
                    continue
                if t_token is None:
                    t_token = time.monotonic()
                answer += piece
                for s in sentences.feed(piece):
                    t = self._speak(s)
                    t_first = t_first or t
            for s in sentences.flush():
                t = self._speak(s)
                t_first = t_first or t
        except Exception as e:                       # noqa: BLE001
            if not self._interrupt.is_set():
                _log("modello:", e)
                GLib.idle_add(self.on_error, "err_engine")
        if answer.strip():
            self.history.append({"role": "assistant", "content": answer.strip()})
        else:
            self.history.pop()
        if DEBUG >= 2:
            if reasoning:
                _log(f"ragionamento: {reasoning} caratteri, non detti")
            _log("risposta:", answer.strip() or "(vuota)")
        self.speaker.wait_idle(self._interrupt)
        if DEBUG:
            def ms(t):
                return f"{(t - t_end) * 1000:6.0f} ms" if t else "     —   "
            _log(f"tempi dalla fine della frase: primo token {ms(t_token)} · "
                 f"prima frase {ms(t_first)} · prima sillaba {ms(self.speaker.first_audio)}")
        self._interrupt.clear()

    def _speak(self, sentence):
        text, emotion = st.clean(sentence)
        if not text or self._interrupt.is_set():
            return None
        self._set_state("speaking")
        self.speaker.say(self.lexicon_apply(text), emotion)
        return time.monotonic()

    lexicon_apply = staticmethod(lambda text: text)
