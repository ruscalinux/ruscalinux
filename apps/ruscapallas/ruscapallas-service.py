#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
RuscaPallas 1.99.3 — il servizio di dialogo di Pallasio.

Pallasio è un manul cinico e incattivito, con giacca color crema, cravatta
rossa e occhialini, che cammina sul desktop (estensione di GNOME Shell) e
parla a voce. Questo programma è la sua testa: ascolta con Vosk, pensa con
ruscallama-engine (llama.cpp, su 127.0.0.1), parla con Piper. Tutto resta
sul computer, e la conversazione non si scrive né si salva.

Il ciclo di conversazione è quello di RuscaLLisse: i moduli conversation,
entity, rusca_engine, rusca_piper, rusca_vosk, speech_text e il motore
Markdown sono copie identiche dei suoi (make-deb.sh lo controlla). Cambia
solo il modo di ascoltare: Pallasio ascolta dopo un clic, resta in ascolto
qualche secondo per il seguito, poi torna a passeggiare.

Lo avvia D-Bus al primo clic (org.ruscalinux.RuscaPallas) ed esce da solo
dopo un quarto d'ora senza conversare, per liberare la memoria del modello.

Copyright (C) 2026 Nunzio Curcuruto — https://www.ruscalinux.org
Licenza: GNU GPL 3.0 o successiva.
"""
import json
import os
import shutil
import signal
import sys
import threading
import time

import gi
gi.require_version("Gio", "2.0")
from gi.repository import Gio, GLib  # noqa: E402

BASE_DIR = os.path.dirname(os.path.realpath(__file__))
sys.path.insert(0, BASE_DIR)
import conversation as conv_mod  # noqa: E402
import entity  # noqa: E402
import rusca_engine as eng  # noqa: E402
import rusca_piper as piper  # noqa: E402
import rusca_vosk as vosk  # noqa: E402
import speech_text as st  # noqa: E402

APP_ID = "org.ruscalinux.RuscaPallas"
APP_VERSION = "1.99.3"
BUS_NAME = APP_ID
OBJECT_PATH = "/org/ruscalinux/RuscaPallas"
INTERFACE = "org.ruscalinux.RuscaPallas"
INTERFACE_XML = """<node>
  <interface name="org.ruscalinux.RuscaPallas">
    <method name="Talk"/>
    <method name="Stop"/>
    <method name="Quit"/>
    <method name="GetState"><arg type="s" direction="out"/></method>
    <signal name="State"><arg type="s"/></signal>
    <signal name="Emotion"><arg type="s"/></signal>
    <signal name="Mouth"><arg type="d"/></signal>
    <signal name="Error"><arg type="s"/><arg type="s"/></signal>
  </interface>
</node>"""

CONFIG_DIR = os.path.join(GLib.get_user_config_dir(), "ruscapallas")
CONFIG_FILE = os.path.join(CONFIG_DIR, "settings.json")
LISSE_CONFIG = os.path.join(GLib.get_user_config_dir(), "ruscallisse", "settings.json")
DATA_DIR = os.path.join(GLib.get_user_data_dir(), "ruscapallas")
ENTITY_SYSTEM = os.path.join(BASE_DIR, "entities", "pallasio.md")
ENTITY_USER = os.path.join(DATA_DIR, "pallasio.md")
LEXICON_SYSTEM = os.path.join(BASE_DIR, "pronunce.tsv")
# il lessico delle pronunce è quello di RuscaLLisse: una correzione vale per tutti e due
LEXICON_USER = os.path.join(GLib.get_user_data_dir(), "ruscallisse", "pronunce.tsv")

LISTEN_WINDOW = 8.0          # s di ascolto senza voce, poi torna a passeggiare
VOICE_LEVEL = 0.18           # livello del microfono che conta come voce
IDLE_EXIT = 15 * 60          # s senza conversare, poi il servizio esce
MOUTH_EVERY = 40             # ms fra un volume della voce e il successivo
DEFAULTS = {"vosk_model": "", "model": "", "voice": "", "speed": 0.0, "max_words": 60,
            "emotions": True, "gpu": True, "gpu_device": ""}
GREETING = {"it": "Ancora tu. Che c'è?", "en": "You again. What is it?"}


def _log(*args):
    print("ruscapallas:", *args, file=sys.stderr, flush=True)


def load_settings():
    """Le scelte di RuscaLLisse (modello, voce, scheda grafica) valgono anche
    per Pallasio; quelle di RuscaPallas, se ci sono, vincono."""
    cfg = dict(DEFAULTS)
    for path in (LISSE_CONFIG, CONFIG_FILE):
        try:
            with open(path, encoding="utf-8") as f:
                data = json.load(f)
        except (OSError, ValueError):
            continue
        if isinstance(data, dict):
            cfg.update({k: data[k] for k in DEFAULTS if k in data and data[k] not in ("", None)})
    return cfg


def ensure_entity():
    """La personalità del pacchetto si copia all'utente una volta sola: da
    quel momento è sua e non si sovrascrive."""
    if not os.path.exists(ENTITY_USER) and os.path.isfile(ENTITY_SYSTEM):
        try:
            os.makedirs(DATA_DIR, exist_ok=True)
            shutil.copyfile(ENTITY_SYSTEM, ENTITY_USER)
        except OSError as e:
            _log("personalità:", e)
    return ENTITY_USER if os.path.isfile(ENTITY_USER) else ENTITY_SYSTEM


def choose_pieces(cfg, ent):
    """Percorsi (o None) di modello Vosk, modello linguistico e voce, come
    in RuscaLLisse; la voce scritta nella personalità vince."""
    models = vosk.find_models()
    vm = cfg["vosk_model"] if cfg["vosk_model"] in models else (models[0] if models else None)
    ggufs = eng.find_models()
    gm = cfg["model"] if cfg["model"] in ggufs else (ggufs[0] if ggufs else None)
    voices = piper.find_voices()
    wanted = (ent or {}).get("voice_name") or ""
    vc = next((v for v in voices if os.path.basename(v)[:-5] == wanted), None)
    if vc is None:
        vc = cfg["voice"] if cfg["voice"] in voices else None
    if vc is None and voices:
        lang = vosk.model_language(vm) if vm else ""
        same = [v for v in voices if piper.voice_info(v)["lang"] == lang]
        vc = (same or voices)[0]
    return vm, gm, vc


def missing_engines():
    names = []
    if not vosk.find_library():
        names.append("ruscavosk-engine")
    if not eng.find_binary():
        names.append("ruscallama-engine")
    if not piper.available():
        names.append("ruscapiper-engine")
    if not os.path.exists(conv_mod.PW_RECORD):
        names.append("pipewire-bin")
    return names


class Service:
    """La testa di Pallasio. Gli stati che vede l'estensione:
    idle (passeggia), waking (si sveglia: carica i modelli), listening,
    thinking, speaking."""

    def __init__(self, loop=None, emit=None):
        self.loop = loop
        self.emit = emit or (lambda name, sig, *args: None)
        self.cfg = load_settings()
        self.engine = eng.Engine(APP_ID, on_state=self._on_engine_state)
        self.recognizer = self.speaker = self.conv = None
        self.ent = None
        self.lang = "it"
        self.lexicon = {}
        self.state = "idle"
        self.loading = False
        self.want_listen = False
        self.last_voice = 0.0
        self.last_activity = time.monotonic()
        self._mouth_id = 0
        self._window_id = 0
        self._idle_id = GLib.timeout_add_seconds(30, self._check_idle)

    # ── comandi (da D-Bus) ───────────────────────────────────────────────
    def talk(self):
        """Clic su Pallasio: drizza le orecchie."""
        self.last_activity = time.monotonic()
        if self.conv is None:
            self.want_listen = True
            if not self.loading:
                self.start_session()
            return
        self.last_voice = time.monotonic()
        self.conv.set_paused(False)
        self._watch_listening()

    def stop(self):
        """Zitto: tace e smette di ascoltare."""
        self.last_activity = time.monotonic()
        self.want_listen = False
        if self.conv is not None:
            self.conv.set_paused(True)
        self._set_state("idle")

    def quit(self):
        self.stop_session()
        if self.loop is not None:
            self.loop.quit()

    # ── stato ────────────────────────────────────────────────────────────
    def _set_state(self, state):
        if state == self.state:
            return
        self.state = state
        self.emit("State", "(s)", state)
        if state == "speaking":
            if not self._mouth_id:
                self._mouth_id = GLib.timeout_add(MOUTH_EVERY, self._send_mouth)
        elif self._mouth_id:
            GLib.source_remove(self._mouth_id)
            self._mouth_id = 0
            self.emit("Mouth", "(d)", 0.0)
        if state == "listening":
            self.last_voice = time.monotonic()
        if state in ("listening", "thinking", "speaking"):
            self.last_activity = time.monotonic()

    def _send_mouth(self):
        if self.speaker is None or self.state != "speaking":
            self._mouth_id = 0
            return False
        amp, _vis = self.speaker.level_at(time.monotonic())
        self.emit("Mouth", "(d)", min(1.0, amp * 8))
        return True

    def _error(self, key, detail=""):
        self.emit("Error", "(ss)", key, detail)

    # callback della conversazione (nel thread principale)
    def _on_state(self, state):
        self._set_state("idle" if state in ("paused", "error") else state)
        return False

    def _on_level(self, level):
        if level >= VOICE_LEVEL:
            self.last_voice = time.monotonic()
        return False

    def _on_error(self, key):
        self._error(key)
        return False

    def _on_notice(self, key):
        return False

    def _on_engine_state(self, state, detail=""):
        if state == "error" and self.conv is not None:
            self._error("err_engine")
        return False

    def _on_sentence(self, emotion):
        if emotion:
            self.emit("Emotion", "(s)", emotion)
        return False

    # ── ascolto a tempo: dopo il clic e dopo ogni risposta ───────────────
    def _watch_listening(self):
        if not self._window_id:
            self._window_id = GLib.timeout_add(250, self._check_listening)

    def _check_listening(self):
        conv = self.conv
        if conv is None or conv.paused:
            self._window_id = 0
            return False
        if conv.state == "listening" and time.monotonic() - self.last_voice > LISTEN_WINDOW:
            conv.set_paused(True)
            self._set_state("idle")
            self._window_id = 0
            return False
        return True

    def _check_idle(self):
        if (self.state == "idle" and not self.loading
                and time.monotonic() - self.last_activity > IDLE_EXIT):
            _log("un quarto d'ora senza conversare: esco e libero la memoria")
            self.quit()
            return False
        return True

    # ── la sessione: i tre motori ────────────────────────────────────────
    def prompt(self):
        self.ent = entity.load(ensure_entity())
        return entity.system_prompt(self.ent, self.lang, self.cfg["max_words"], self.cfg["emotions"])

    def start_session(self):
        # subito «waking»: se qualcosa manca, il ritorno a «idle» si vede
        # (l'estensione ha già drizzato le orecchie al clic)
        self._set_state("waking")
        self.cfg = load_settings()
        self.ent = entity.load(ensure_entity())
        engines = missing_engines()
        if engines:
            self._error("err_engines", ", ".join(engines))
            self._set_state("idle")
            return
        vm, gm, vc = choose_pieces(self.cfg, self.ent)
        missing = [name for name, value in (("piece_listen", vm), ("piece_think", gm),
                                            ("piece_speak", vc)) if not value]
        if missing:
            self._error("err_missing", ",".join(missing))
            self._set_state("idle")
            return
        self.loading = True
        self.lang = vosk.model_language(vm) or "it"
        if self.lang not in st.REGOLE:
            self.lang = "en"
        speed = self.ent.get("speed") or self.cfg["speed"] or 1.0
        args = ["-c", "8192", "-t", str(eng.physical_cores()), "--reasoning-format", "deepseek"]
        if self.cfg["gpu"]:
            device = eng.device_name(self.cfg["gpu_device"], eng.list_devices()) if self.cfg["gpu_device"] else ""
            if device:
                args += ["--device", device]
        try:
            self.engine.start(gm, args, gpu=self.cfg["gpu"])
        except eng.EngineError as e:
            self.loading = False
            self._error(e.key or "err_engine", e.detail)
            self._set_state("idle")
            return

        def work():
            try:
                rec = vosk.Recognizer(vm)
                spk = piper.Speaker(vc, speed, debug=bool(conv_mod.DEBUG))
            except Exception as e:                       # noqa: BLE001
                GLib.idle_add(self._session_failed, getattr(e, "key", "err_load"), str(e))
                return
            if not self.engine.wait_ready():
                rec.close()
                spk.close()
                GLib.idle_add(self._session_failed, "err_engine", "")
                return
            try:   # il prompt della personalità entra nella cache del motore
                self.engine.chat({"messages": [{"role": "system", "content": self.prompt()},
                                               {"role": "user", "content": "Ciao"}],
                                  "max_tokens": 1, "cache_prompt": True}, timeout=600)
            except Exception:                            # noqa: BLE001
                pass
            GLib.idle_add(self._session_ready, rec, spk)
        threading.Thread(target=work, daemon=True).start()

    def _session_failed(self, key, detail):
        self.loading = False
        _log(key, detail)
        self._error(key, "")
        self.engine.stop()
        self._set_state("idle")
        return False

    def _session_ready(self, rec, spk):
        self.loading = False
        self.recognizer, self.speaker = rec, spk
        self.lexicon = st.load_lexicon(LEXICON_SYSTEM, LEXICON_USER)
        spk.on_sentence = self._on_sentence
        spk.on_error = self._on_error
        self.conv = conv_mod.Conversation(
            rec, spk, self.engine, self.prompt, lambda: self.cfg["max_words"] * 2,
            self._on_state, self._on_level, self._on_error,
            greeting=GREETING.get(self.lang, GREETING["en"]), on_notice=self._on_notice)
        self.conv.lexicon_apply = lambda text: st.apply_lexicon(text, self.lexicon)
        if not self.want_listen:         # «Zitto» mentre si svegliava
            self.conv.set_paused(True)
        self.conv.start()
        self.last_voice = time.monotonic()
        self._watch_listening()
        return False

    def stop_session(self):
        stopped = True
        if self.conv is not None:
            stopped = self.conv.quit()
            self.conv = None
        if self.speaker is not None:
            self.speaker.close()
            self.speaker = None
        if self.recognizer is not None:
            if stopped:          # mai mentre il thread dell'ascolto lo usa ancora
                self.recognizer.close()
            self.recognizer = None
        self.engine.stop(wait=True)


# ── D-Bus ────────────────────────────────────────────────────────────────
class Bus:
    def __init__(self, loop):
        self.loop = loop
        self.conn = None
        self.service = Service(loop, self.emit)
        self.node = Gio.DBusNodeInfo.new_for_xml(INTERFACE_XML)
        self.owner_id = Gio.bus_own_name(Gio.BusType.SESSION, BUS_NAME, Gio.BusNameOwnerFlags.NONE,
                                         self._on_bus, None, self._on_lost)

    def emit(self, name, signature, *args):
        if self.conn is None:
            return
        try:
            self.conn.emit_signal(None, OBJECT_PATH, INTERFACE, name, GLib.Variant(signature, args))
        except GLib.Error as e:
            _log("D-Bus:", e.message)

    def _on_bus(self, conn, _name):
        self.conn = conn
        conn.register_object(OBJECT_PATH, self.node.interfaces[0], self._on_call, None, None)

    def _on_lost(self, _conn, _name):
        _log("il nome", BUS_NAME, "è già usato o il bus non c'è: esco")
        self.service.quit()
        self.loop.quit()

    def _on_call(self, _conn, _sender, _path, _iface, method, _params, invocation):
        s = self.service
        if method == "GetState":
            invocation.return_value(GLib.Variant("(s)", (s.state,)))
            return
        invocation.return_value(None)
        if method == "Talk":
            s.talk()
        elif method == "Stop":
            s.stop()
        elif method == "Quit":
            GLib.idle_add(lambda: s.quit() or False)


def main():
    if "--version" in sys.argv:
        print(f"RuscaPallas {APP_VERSION}")
        return 0
    loop = GLib.MainLoop()
    bus = Bus(loop)
    for sig in (signal.SIGINT, signal.SIGTERM):
        GLib.unix_signal_add(GLib.PRIORITY_DEFAULT, sig, lambda: bus.service.quit() or False)
    loop.run()
    bus.service.stop_session()
    return 0


if __name__ == "__main__":
    sys.exit(main())
