#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
RuscaLLisse 1.99.3 — una conversazione a voce con un'entità digitale.

La prima entità è Ellittica, una donna digitale intellettuale, dolce e
sensibile, che spiega le cose in modo semplice. Si parla a voce, come nella
vita: sullo schermo c'è solo il suo volto, niente viene scritto e la
conversazione non si salva.

Ascolta con Vosk, pensa con ruscallama-engine (llama.cpp, su 127.0.0.1),
parla con Piper. Tutto resta sul computer.

Copyright (C) 2026 Nunzio Curcuruto — https://www.ruscalinux.org
Licenza: GNU GPL 3.0 o successiva.

Requisiti: Python 3.10+, PyGObject (con Cairo), GTK 4.18+, libadwaita 1.7+,
ruscallama-engine, pipewire-bin, python3-markdown-it.
"""
import json
import os
import shutil
import sys
import threading

import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gdk, Gio, GLib, Gtk  # noqa: E402

BASE_DIR = os.path.dirname(os.path.realpath(__file__))
sys.path.insert(0, BASE_DIR)
import conversation as conv_mod  # noqa: E402
import entity  # noqa: E402
import face as face_mod  # noqa: E402
import rusca_engine as eng  # noqa: E402
import rusca_piper as piper  # noqa: E402
import rusca_vosk as vosk  # noqa: E402
import speech_text as st  # noqa: E402

APP_ID = "org.ruscalinux.RuscaLLisse"
APP_NAME = "RuscaLLisse"
APP_VERSION = "1.99.3"
PROVA = "prova 2"            # versione di prova: motori precompilati
STYLE_SRC = os.path.join(BASE_DIR, "style.css")
ICON_SRC = os.path.join(BASE_DIR, "ruscallisse.svg")
LANG_DIR = os.path.join(BASE_DIR, "lang")
CONFIG_DIR = os.path.join(GLib.get_user_config_dir(), "ruscallisse")
CONFIG_FILE = os.path.join(CONFIG_DIR, "settings.json")
DATA_DIR = os.path.join(GLib.get_user_data_dir(), "ruscallisse")
LEXICON_SYSTEM = os.path.join(BASE_DIR, "pronunce.tsv")
LEXICON_USER = os.path.join(DATA_DIR, "pronunce.tsv")
COMPONENTS = (
    ("Vosk (libvosk)", "Apache 2.0 — Alpha Cephei Inc.", "https://github.com/alphacep/vosk-api"),
    ("Piper (piper1-gpl)", "GPL-3.0 — Michael Hansen", "https://github.com/OHF-Voice/piper1-gpl"),
    ("espeak-ng", "GPL-3.0", "https://github.com/espeak-ng/espeak-ng"),
    ("ONNX Runtime", "MIT — Microsoft", "https://github.com/microsoft/onnxruntime"),
    ("NumPy", "BSD-3-Clause", "https://numpy.org"),
    ("llama.cpp (llama-server)", "MIT — The ggml authors", "https://github.com/ggml-org/llama.cpp"),
    ("markdown-it-mark", "MIT — Vitaly Puzrin, Alex Kocharin; ExecutableBookProject",
     "https://github.com/markdown-it/markdown-it-mark"),
)
GUIDE = (
    ("guide_vosk", "https://alphacephei.com/vosk/models"),
    ("guide_voice", "https://huggingface.co/rhasspy/piper-voices/tree/main/it/it_IT"),
    ("guide_model", "https://huggingface.co/models?library=gguf"),
)
DEFAULTS = {
    "entity": "ellittica.md", "vosk_model": "", "model": "", "voice": "", "speed": 0.0,
    "max_words": 80, "emotions": True, "gpu": True, "theme": "system",
    "width": 520, "height": 640, "maximized": False,
}
THEMES = ("system", "light", "dark")
GREETING = {"it": "Ciao, sono {name}. Di che cosa vuoi parlare?",
            "en": "Hello, I'm {name}. What would you like to talk about?"}


def apply_color_scheme(theme):
    """Tema chiaro/scuro: segue GNOME (predefinito) o è scelto dall'utente."""
    Adw.StyleManager.get_default().set_color_scheme({
        "light": Adw.ColorScheme.FORCE_LIGHT,
        "dark": Adw.ColorScheme.FORCE_DARK,
    }.get(theme, Adw.ColorScheme.DEFAULT))


# ── Traduzioni dell'interfaccia (lang/xx.json, ripiego en.json) ──────────────
LANG_ALIASES = {"zh_HK": "zh_TW", "zh_MO": "zh_TW", "zh_SG": "zh_CN", "zh": "zh_CN",
                "pt": "pt_BR", "sk": "cs"}


def _load_strings():
    def read(code):
        try:
            with open(os.path.join(LANG_DIR, f"{code}.json"), encoding="utf-8") as f:
                return json.load(f)
        except (OSError, ValueError):
            return {}
    strings = read("en")
    for name in GLib.get_language_names():
        base = name.split(".")[0].split("@")[0]
        lang = base.split("_")[0]
        for code in (base, LANG_ALIASES.get(base), lang, LANG_ALIASES.get(lang)):
            if not code:
                continue
            if code in ("C", "POSIX", "en"):
                return strings, "en"
            data = read(code)
            if data:
                strings.update(data)
                return strings, code
    return strings, "en"


_STRINGS, LANG = _load_strings()


def _(key, **fields):
    text = _STRINGS.get(key, key)
    try:
        return text.format(**fields) if fields else text
    except (KeyError, IndexError, ValueError):
        return text


def theme_has_icon(name=APP_ID):
    display = Gdk.Display.get_default()
    return display is not None and Gtk.IconTheme.get_for_display(display).has_icon(name)


def ensure_icon():
    dest = os.path.join(GLib.get_user_data_dir(), "icons", "hicolor", "scalable",
                        "apps", f"{APP_ID}.svg")
    if os.path.exists(dest) or not os.path.isfile(ICON_SRC):
        return
    try:
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        with open(ICON_SRC, "rb") as s, open(dest, "wb") as d:
            d.write(s.read())
    except OSError:
        pass


def load_settings():
    cfg = dict(DEFAULTS)
    try:
        with open(CONFIG_FILE, encoding="utf-8") as f:
            data = json.load(f)
        for k, v in data.items():
            if k in cfg and (isinstance(v, type(cfg[k])) or
                             (isinstance(cfg[k], float) and isinstance(v, int))):
                cfg[k] = type(cfg[k])(v)
    except (OSError, ValueError, AttributeError, TypeError):
        pass
    cfg["max_words"] = max(20, min(300, cfg["max_words"]))
    return cfg


def save_settings(cfg):
    try:
        os.makedirs(CONFIG_DIR, exist_ok=True)
        tmp = CONFIG_FILE + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(cfg, f, ensure_ascii=False, indent=2)
        os.replace(tmp, CONFIG_FILE)
    except OSError:
        pass


def show_about_dialog(parent, tr, app_id, app_name, version, description, has_icon,
                      components=()):
    """Finestra «Informazioni» comune alle RuscaLinux OS Apps.

    Pagina principale: icona, nome, versione, descrizione (sempre visibile:
    in Adw.AboutDialog finirebbe in una sottopagina) e collegamenti. La nota
    di sviluppo e' una riga dell'elenco, come la licenza: con un clic apre la
    sua pagina nella stessa finestra (specifiche, sezioni 3.10 e 12).
    `tr` restituisce il testo tradotto di una chiave di lang/.
    `components`: componenti esterni (nome, licenza, indirizzo), mostrati in
    un gruppo «Componenti esterni» (specifiche, sezioni 3.10 e 6)."""
    def open_uri(_row, uri):
        def done(launcher, result):
            try:
                launcher.launch_finish(result)
            except GLib.Error:
                pass
        Gtk.UriLauncher.new(uri).launch(parent, None, done)

    nav = Adw.NavigationView()

    box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6,
                  margin_top=12, margin_bottom=24, margin_start=24, margin_end=24)
    icon = Gtk.Image(icon_name=app_id if has_icon else "application-x-executable",
                     pixel_size=128, margin_bottom=12)
    icon.add_css_class("icon-dropshadow")
    box.append(icon)
    for text, css in ((app_name, "title-1"), (version, "dim-label"),
                      (description, "body")):
        label = Gtk.Label(label=text, wrap=True, justify=Gtk.Justification.CENTER)
        label.add_css_class(css)
        box.append(label)

    links = Adw.PreferencesGroup(margin_top=18)
    for title, subtitle, uri in (
            (tr("about_website"), "www.ruscalinux.org", "https://www.ruscalinux.org/"),
            (tr("about_support"), "info@ruscalinux.org", "mailto:info@ruscalinux.org"),
            (tr("about_license"), "GNU GPL 3.0", "https://www.gnu.org/licenses/gpl-3.0.html")):
        row = Adw.ActionRow(title=title, subtitle=subtitle, activatable=True)
        row.add_suffix(Gtk.Image(icon_name="adw-external-link-symbolic"))
        row.connect("activated", open_uri, uri)
        links.add(row)
    # Nota di sviluppo: una riga come le altre, che apre la sua pagina.
    note_row = Adw.ActionRow(title=tr("dev_note_title"), activatable=True)
    note_row.add_suffix(Gtk.Image(icon_name="go-next-symbolic"))
    links.add(note_row)
    box.append(links)

    if components:
        ext = Adw.PreferencesGroup(title=tr("about_components"), margin_top=12)
        for name, licence, uri in components:
            row = Adw.ActionRow(title=name, subtitle=licence, activatable=True)
            row.add_suffix(Gtk.Image(icon_name="adw-external-link-symbolic"))
            row.connect("activated", open_uri, uri)
            ext.add(row)
        box.append(ext)

    copyright_label = Gtk.Label(label="© 2026 Nunzio Curcuruto", margin_top=12)
    copyright_label.add_css_class("caption")
    copyright_label.add_css_class("dim-label")
    box.append(copyright_label)

    scroller = Gtk.ScrolledWindow(hscrollbar_policy=Gtk.PolicyType.NEVER,
                                  propagate_natural_height=True, child=box)
    view = Adw.ToolbarView(content=scroller)
    view.add_top_bar(Adw.HeaderBar(show_title=False))
    nav.add(Adw.NavigationPage(title=app_name, child=view))

    # Pagina della nota: testo a colore pieno (contrasto >= 4,5:1), pulsante
    # indietro nella barra in alto, tradotto da libadwaita.
    note_label = Gtk.Label(label=tr("ai_note"), wrap=True, xalign=0, valign=Gtk.Align.START,
                           margin_top=12, margin_bottom=24, margin_start=24, margin_end=24)
    note_label.add_css_class("body")
    note_view = Adw.ToolbarView(content=note_label)
    note_view.add_top_bar(Adw.HeaderBar())
    note_page = Adw.NavigationPage(title=tr("dev_note_title"), child=note_view)
    note_row.connect("activated", lambda _row: nav.push(note_page))

    Adw.Dialog(title=app_name, content_width=420, child=nav).present(parent)


def open_folder(parent, path):
    os.makedirs(path, exist_ok=True)
    Gtk.FileLauncher.new(Gio.File.new_for_path(path)).launch(parent, None, None)


def open_uri(parent, uri):
    Gtk.UriLauncher.new(uri).launch(parent, None, None)


class LisseWindow(Adw.ApplicationWindow):
    def __init__(self, app):
        super().__init__(application=app, title=APP_NAME)
        self.cfg = load_settings()
        self.set_default_size(self.cfg["width"], self.cfg["height"])
        if self.cfg["maximized"]:
            self.maximize()
        entity.ensure_default()
        self.engine = eng.Engine(APP_ID, on_state=self._on_engine_state)
        self.recognizer = None
        self.speaker = None
        self.conv = None
        self.ent = None
        self.lang = "it"
        self.lexicon = {}
        self._loading = False
        self._monitors = []

        # ── barra del titolo ──
        header = Adw.HeaderBar()
        self.mic_button = Gtk.ToggleButton(icon_name="audio-input-microphone-symbolic",
                                           tooltip_text=_("mic_pause"), action_name="win.mic")
        self.mic_button.update_property([Gtk.AccessibleProperty.LABEL], [_("mic_pause")])
        header.pack_start(self.mic_button)
        self.title = Adw.WindowTitle(title=APP_NAME, subtitle="")
        header.set_title_widget(self.title)
        menu = Gio.Menu()
        sec = Gio.Menu()
        sec.append(_("restart"), "win.restart")
        menu.append_section(None, sec)
        sec = Gio.Menu()
        sec.append(_("edit_personality"), "win.edit-personality")
        sec.append(_("import_voice"), "win.import-voice")
        sec.append(_("open_vosk_folder"), "win.open-vosk")
        sec.append(_("open_voice_folder"), "win.open-voices")
        sec.append(_("guide"), "win.guide")
        menu.append_section(None, sec)
        sec = Gio.Menu()
        sec.append(_("preferences"), "win.preferences")
        sec.append(_("shortcuts"), "win.shortcuts")
        sec.append(_("about"), "win.about")
        menu.append_section(None, sec)
        header.pack_end(Gtk.MenuButton(icon_name="open-menu-symbolic", menu_model=menu,
                                       primary=True, tooltip_text=_("main_menu")))

        self.banner = Adw.Banner(title=_("quid_missing"), button_label=_("write_quid"))
        self.banner.connect("button-clicked", lambda _b: self.edit_personality())

        # ── contenuto ──
        self.face = face_mod.FaceView(self._state_label)
        self.welcome = self._build_welcome()
        self.stack = Gtk.Stack(transition_type=Gtk.StackTransitionType.CROSSFADE)
        self.stack.add_named(self.welcome, "welcome")
        self.stack.add_named(self.face, "face")
        self.toasts = Adw.ToastOverlay(child=self.stack)
        view = Adw.ToolbarView(content=self.toasts)
        view.add_top_bar(header)
        view.add_top_bar(self.banner)
        self.set_content(view)

        for name, cb in (("restart", self.restart), ("stop", self.stop_speaking),
                         ("edit-personality", self.edit_personality),
                         ("import-voice", self.import_voice),
                         ("open-vosk", lambda: open_folder(self, vosk.USER_MODEL_DIR)),
                         ("open-voices", lambda: open_folder(self, piper.USER_VOICE_DIR)),
                         ("open-models", lambda: open_folder(self, eng.MODEL_DIRS[1])),
                         ("guide", self.show_guide), ("preferences", self.show_preferences),
                         ("shortcuts", self.show_shortcuts), ("about", self.show_about)):
            a = Gio.SimpleAction.new(name, None)
            a.connect("activate", lambda _a, _p, f=cb: f())
            self.add_action(a)
        mic = Gio.SimpleAction.new_stateful("mic", None, GLib.Variant.new_boolean(False))
        mic.connect("activate", self._toggle_mic)
        self.add_action(mic)

        self.connect("close-request", self._on_close)
        self._watch_folders()
        self.refresh()

    # ── stato ────────────────────────────────────────────────────────────
    def _state_label(self, state):
        name = self.ent["name"] if self.ent else "Ellittica"
        return _(f"state_{state}", name=name)

    def _set_subtitle(self, key):
        self.title.set_subtitle(_(key))

    def _on_state(self, state):
        self.face.set_state(state)
        self._set_subtitle(f"sub_{state}")
        return False

    def _on_level(self, level):
        self.face.set_level(level)
        return False

    def _on_error(self, key):
        self.toasts.add_toast(Adw.Toast(title=_(key), timeout=5))
        if key == "err_mic":
            self._set_mic_paused(True)
        return False

    def _on_engine_state(self, state, detail=""):
        if state == "error" and self.conv is not None:
            self.toasts.add_toast(Adw.Toast(title=_("err_engine"), timeout=5))
        return False

    # ── i tre pezzi ──────────────────────────────────────────────────────
    def _entity_path(self):
        p = os.path.join(entity.USER_DIR, self.cfg["entity"])
        if not os.path.isfile(p):
            found = entity.list_entities()
            p = found[0] if found else p
        return p

    def _pieces(self):
        """Percorsi scelti (o None) di modello Vosk, modello linguistico, voce."""
        models = vosk.find_models()
        vm = self.cfg["vosk_model"] if self.cfg["vosk_model"] in models else (models[0] if models else None)
        ggufs = eng.find_models()
        gm = self.cfg["model"] if self.cfg["model"] in ggufs else (ggufs[0] if ggufs else None)
        voices = piper.find_voices()
        wanted = (self.ent or {}).get("voice_name") or ""
        vc = next((v for v in voices if os.path.basename(v)[:-5] == wanted), None)
        if vc is None:
            vc = self.cfg["voice"] if self.cfg["voice"] in voices else None
        if vc is None and voices:
            lang = vosk.model_language(vm) if vm else ""
            same = [v for v in voices if piper.voice_info(v)["lang"] == lang]
            vc = (same or voices)[0]
        return vm, gm, vc

    def _build_welcome(self):
        page = Adw.StatusPage(icon_name=APP_ID if theme_has_icon() else "audio-input-microphone-symbolic",
                              title=_("welcome_title"), description=_("welcome_desc"))
        group = Adw.PreferencesGroup()
        self.row_vosk = Adw.ActionRow(title=_("piece_listen"))
        self.row_model = Adw.ActionRow(title=_("piece_think"))
        self.row_voice = Adw.ActionRow(title=_("piece_speak"))
        for row, action, label in ((self.row_vosk, "win.open-vosk", _("open_folder")),
                                   (self.row_model, "win.open-models", _("open_folder")),
                                   (self.row_voice, "win.import-voice", _("import_voice"))):
            row.add_suffix(Gtk.Button(label=label, action_name=action, valign=Gtk.Align.CENTER))
            group.add(row)
        guide = Gtk.Button(label=_("guide"), action_name="win.guide",
                           halign=Gtk.Align.CENTER, margin_top=12)
        guide.add_css_class("pill")
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        box.append(group)
        box.append(guide)
        page.set_child(Adw.Clamp(maximum_size=560, child=box))
        self.welcome_page = page
        return Gtk.ScrolledWindow(child=page)

    def _watch_folders(self):
        for d in (vosk.USER_MODEL_DIR, piper.USER_VOICE_DIR, eng.MODEL_DIRS[1], entity.USER_DIR):
            try:
                os.makedirs(d, exist_ok=True)
                mon = Gio.File.new_for_path(d).monitor_directory(Gio.FileMonitorFlags.NONE, None)
                mon.connect("changed", lambda *_a: self._schedule_refresh())
                self._monitors.append(mon)
            except (OSError, GLib.Error):
                pass
        self._refresh_id = 0

    def _schedule_refresh(self):
        if self._refresh_id:
            GLib.source_remove(self._refresh_id)
        self._refresh_id = GLib.timeout_add(1500, self._refresh_timeout)

    def _refresh_timeout(self):
        self._refresh_id = 0
        self.refresh()
        return False

    def refresh(self):
        """Rilegge l'entità; se tutto c'è e la conversazione non è partita,
        la fa partire; altrimenti mostra la pagina di benvenuto."""
        self.ent = entity.load(self._entity_path())
        self.banner.set_revealed(entity.quid_missing(self.ent))
        self.title.set_title(self.ent["name"])
        if self.conv is not None or self._loading:
            return
        vm, gm, vc = self._pieces()
        missing = []
        for row, value, key in ((self.row_vosk, vm, "piece_listen"),
                                (self.row_model, gm, "piece_think"),
                                (self.row_voice, vc, "piece_speak")):
            row.set_subtitle(os.path.basename(value) if value else _("missing"))
            if not value:
                missing.append(key)
        engines = []
        if not vosk.find_library():
            engines.append("libvosk")
        if not eng.find_binary():
            engines.append("ruscallama-engine")
        if not os.path.exists(conv_mod.PW_RECORD):
            engines.append("pipewire-bin")
        if engines:
            self.welcome_page.set_description(_("err_engines", names=", ".join(engines)))
        if missing or engines:
            self.stack.set_visible_child_name("welcome")
            self._set_subtitle("sub_missing")
            return
        self.stack.set_visible_child_name("face")
        self._start_session(vm, gm, vc)

    def _start_session(self, vm, gm, vc):
        self._loading = True
        self.face.set_state("paused")
        self._set_subtitle("sub_waking")
        self.lang = vosk.model_language(vm) or LANG.split("_")[0]
        if self.lang not in st.REGOLE:
            self.lang = "en"
        speed = self.ent.get("speed") or self.cfg["speed"] or 1.0
        try:
            self.engine.start(gm, ["-c", "4096", "-t", str(eng.physical_cores())],
                              gpu=self.cfg["gpu"])
        except eng.EngineError as e:
            self._loading = False
            self._on_error(e.key if e.key in _STRINGS else "err_engine")
            return

        def work():
            try:
                rec = vosk.Recognizer(vm)
                spk = piper.Speaker(vc, speed, debug=bool(conv_mod.DEBUG))
            except Exception as e:                       # noqa: BLE001
                GLib.idle_add(self._session_failed, getattr(e, "key", "err_load"), str(e))
                return
            if not self.engine.wait_ready():
                GLib.idle_add(self._session_failed, "err_engine", "")
                return
            try:   # il prompt dell'entità entra nella cache del motore
                self.engine.chat({"messages": [{"role": "system", "content": self._prompt()},
                                               {"role": "user", "content": "Ciao"}],
                                  "max_tokens": 1, "cache_prompt": True}, timeout=600)
            except Exception:                            # noqa: BLE001
                pass
            GLib.idle_add(self._session_ready, rec, spk)
        threading.Thread(target=work, daemon=True).start()

    def _session_failed(self, key, detail):
        self._loading = False
        print("ruscallisse:", key, detail, file=sys.stderr)
        self._on_error(key if key in _STRINGS else "err_load")
        self.engine.stop()
        self._set_subtitle("sub_error")
        return False

    def _prompt(self):
        self.ent = entity.load(self._entity_path())
        return entity.system_prompt(self.ent, self.lang, self.cfg["max_words"], self.cfg["emotions"])

    def _session_ready(self, rec, spk):
        self._loading = False
        self.recognizer, self.speaker = rec, spk
        self.lexicon = st.load_lexicon(LEXICON_SYSTEM, LEXICON_USER)
        spk.on_sentence = lambda emo: (self.face.set_emotion(emo) if emo else None) or False
        spk.on_error = self._on_error
        self.face.speech_source = spk.level_at
        self.conv = conv_mod.Conversation(
            rec, spk, self.engine, self._prompt, lambda: self.cfg["max_words"] * 2,
            self._on_state, self._on_level, self._on_error,
            greeting=GREETING.get(self.lang, GREETING["en"]).format(name=self.ent["name"]))
        self.conv.lexicon_apply = lambda text: st.apply_lexicon(text, self.lexicon)
        self.conv.start()
        return False

    def _stop_session(self):
        if self.conv is not None:
            self.conv.quit()
            self.conv = None
        if self.speaker is not None:
            self.speaker.close()
            self.speaker = None
        if self.recognizer is not None:
            self.recognizer.close()
            self.recognizer = None
        self.face.speech_source = None
        self.engine.stop(wait=True)

    # ── comandi ──────────────────────────────────────────────────────────
    def _toggle_mic(self, action, _param):
        self._set_mic_paused(not action.get_state().get_boolean())

    def _set_mic_paused(self, paused):
        self.lookup_action("mic").set_state(GLib.Variant.new_boolean(paused))
        self.mic_button.set_icon_name("microphone-disabled-symbolic" if paused
                                      else "audio-input-microphone-symbolic")
        label = _("mic_resume") if paused else _("mic_pause")
        self.mic_button.set_tooltip_text(label)
        self.mic_button.update_property([Gtk.AccessibleProperty.LABEL], [label])
        if self.conv is not None:
            self.conv.set_paused(paused)

    def stop_speaking(self):
        if self.conv is not None:
            self.conv.interrupt()

    def restart(self):
        if self.conv is not None:
            self.conv.restart()
            self.toasts.add_toast(Adw.Toast(title=_("restarted", name=self.ent["name"]), timeout=3))

    def edit_personality(self):
        path = self._entity_path()
        if not os.path.isfile(path):
            entity.ensure_default()
        Gtk.FileLauncher.new(Gio.File.new_for_path(path)).launch(self, None, None)

    def import_voice(self):
        dialog = Gtk.FileDialog(title=_("import_voice"))
        filt = Gtk.FileFilter()
        filt.set_name(_("voice_files"))
        filt.add_pattern("*.onnx")
        store = Gio.ListStore.new(Gtk.FileFilter)
        store.append(filt)
        dialog.set_filters(store)

        def done(dlg, result):
            try:
                f = dlg.open_finish(result)
            except GLib.Error:
                return
            try:
                dest = piper.import_voice(f.get_path())
            except FileNotFoundError:
                self.toasts.add_toast(Adw.Toast(
                    title=_("err_voice_json", name=os.path.basename(f.get_path()) + ".json"), timeout=6))
                return
            except OSError as e:
                self.toasts.add_toast(Adw.Toast(title=str(e), timeout=6))
                return
            self.cfg["voice"] = dest
            save_settings(self.cfg)
            self.toasts.add_toast(Adw.Toast(title=_("voice_imported"), timeout=3))
            self.refresh()
        dialog.open(self, None, done)

    def show_guide(self):
        group = Adw.PreferencesGroup(description=_("guide_desc"))
        for key, uri in GUIDE:
            row = Adw.ActionRow(title=_(key), subtitle=_(key + "_sub"), activatable=True,
                                subtitle_lines=0)
            row.add_suffix(Gtk.Image(icon_name="adw-external-link-symbolic"))
            row.connect("activated", lambda _r, u=uri: open_uri(self, u))
            group.add(row)
        page = Adw.PreferencesPage()
        page.add(group)
        view = Adw.ToolbarView(content=page)
        view.add_top_bar(Adw.HeaderBar())
        Adw.Dialog(title=_("guide"), content_width=480, child=view).present(self)

    def show_preferences(self):
        cfg = self.cfg
        dlg = Adw.PreferencesDialog()
        page = Adw.PreferencesPage()
        dlg.add(page)

        def combo(title, items, current, key, subtitle=""):
            names = [os.path.basename(p) for p in items] or [_("missing")]
            row = Adw.ComboRow(title=title, subtitle=subtitle, model=Gtk.StringList.new(names))
            if current in items:
                row.set_selected(items.index(current))

            def changed(r, _p):
                i = r.get_selected()
                if 0 <= i < len(items):
                    cfg[key] = items[i]
                    save_settings(cfg)
                    self._restart_session()
            row.connect("notify::selected", changed)
            return row

        vm, gm, vc = self._pieces()
        g = Adw.PreferencesGroup(title=_("pref_conversation"))
        words = Adw.SpinRow.new_with_range(20, 300, 10)
        words.set_title(_("pref_max_words"))
        words.set_subtitle(_("pref_max_words_sub"))
        words.set_value(cfg["max_words"])
        words.connect("notify::value", lambda r, _p: (cfg.__setitem__("max_words", int(r.get_value())),
                                                      save_settings(cfg)))
        g.add(words)
        emo = Adw.SwitchRow(title=_("pref_emotions"), subtitle=_("pref_emotions_sub"),
                            active=cfg["emotions"])
        emo.connect("notify::active", lambda r, _p: (cfg.__setitem__("emotions", r.get_active()),
                                                     save_settings(cfg)))
        g.add(emo)
        page.add(g)

        g = Adw.PreferencesGroup(title=_("pref_listen"))
        g.add(combo(_("piece_listen"), vosk.find_models(), vm, "vosk_model"))
        page.add(g)

        g = Adw.PreferencesGroup(title=_("pref_voice"))
        voices = piper.find_voices()
        g.add(combo(_("piece_speak"), voices, vc, "voice"))
        speed = Adw.SpinRow.new_with_range(0.7, 1.3, 0.05)
        speed.set_title(_("pref_speed"))
        speed.set_digits(2)
        speed.set_value(self.ent.get("speed") or cfg["speed"] or 1.0)
        speed.set_subtitle(_("pref_speed_sub"))

        def set_speed(r, _p):
            cfg["speed"] = round(r.get_value(), 2)
            save_settings(cfg)
            if self.speaker is not None:
                self.speaker.set_speed(cfg["speed"])
        speed.connect("notify::value", set_speed)
        g.add(speed)
        if vc:
            info = piper.voice_info(vc)
            lic = Adw.ActionRow(title=_("pref_voice_licence"),
                                subtitle=info["licence"] or _("licence_unknown"), subtitle_lines=0)
            g.add(lic)
        page.add(g)

        g = Adw.PreferencesGroup(title=_("pref_model"))
        g.add(combo(_("piece_think"), eng.find_models(), gm, "model"))
        gpu = Adw.SwitchRow(title=_("pref_gpu"), active=cfg["gpu"])

        def set_gpu(r, _p):
            cfg["gpu"] = r.get_active()
            save_settings(cfg)
            self._restart_session()
        gpu.connect("notify::active", set_gpu)
        g.add(gpu)
        page.add(g)

        g = Adw.PreferencesGroup(title=_("pref_look"))
        theme = Adw.ComboRow(title=_("theme"), model=Gtk.StringList.new(
            [_(f"theme_{t}") for t in THEMES]))
        theme.set_selected(THEMES.index(cfg["theme"]) if cfg["theme"] in THEMES else 0)

        def set_theme(r, _p):
            cfg["theme"] = THEMES[r.get_selected()]
            save_settings(cfg)
            apply_color_scheme(cfg["theme"])
        theme.connect("notify::selected", set_theme)
        g.add(theme)
        page.add(g)
        dlg.present(self)

    def _restart_session(self):
        self._stop_session()
        self._loading = False
        self.refresh()

    def show_shortcuts(self):
        group = Adw.PreferencesGroup()
        for title, accel in ((_("mic_pause"), "space"), (_("sc_stop"), "Escape"),
                             (_("restart"), "<Control>n"),
                             (_("preferences"), "<Control>comma"),
                             (_("shortcuts"), "<Control>question"), (_("main_menu"), "F10"),
                             (_("sc_close"), "<Control>w"), (_("sc_quit"), "<Control>q")):
            row = Adw.ActionRow(title=title.rstrip("…"))
            ok, key, mods = Gtk.accelerator_parse(accel)
            keys = Gtk.Label(label=Gtk.accelerator_get_label(key, mods) if ok else accel)
            keys.add_css_class("dim-label")
            row.add_suffix(keys)
            group.add(row)
        page = Adw.PreferencesPage()
        page.add(group)
        view = Adw.ToolbarView(content=page)
        view.add_top_bar(Adw.HeaderBar())
        Adw.Dialog(title=_("shortcuts"), content_width=420, child=view).present(self)

    def show_about(self):
        show_about_dialog(self, _, APP_ID, APP_NAME, f"{APP_VERSION} ({PROVA})",
                          _("app_description"), theme_has_icon(), COMPONENTS)

    def _on_close(self, *_a):
        if not self.is_maximized():
            w, h = self.get_default_size()
            self.cfg.update(width=w, height=h)
        self.cfg["maximized"] = self.is_maximized()
        save_settings(self.cfg)
        self._stop_session()
        return False


class LisseApp(Adw.Application):
    def __init__(self):
        super().__init__(application_id=APP_ID)

    def do_startup(self):
        Adw.Application.do_startup(self)
        if LANG.split("_")[0] in ("ar",):
            Gtk.Widget.set_default_direction(Gtk.TextDirection.RTL)
        if not theme_has_icon():
            ensure_icon()
        if os.path.isfile(STYLE_SRC):
            provider = Gtk.CssProvider()
            provider.load_from_path(STYLE_SRC)
            Gtk.StyleContext.add_provider_for_display(
                Gdk.Display.get_default(), provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)
        apply_color_scheme(load_settings().get("theme", "system"))
        Adw.StyleManager.get_default().connect("notify::dark", lambda *_a: self.update_theme())
        self.connect("window-added", lambda *_a: self.update_theme())
        quit_action = Gio.SimpleAction.new("quit", None)
        quit_action.connect("activate", lambda *_a: [w.close() for w in self.get_windows()])
        self.add_action(quit_action)
        for action, accels in (("app.quit", ["<Control>q"]), ("window.close", ["<Control>w"]),
                               ("win.mic", ["space"]), ("win.stop", ["Escape"]),
                               ("win.restart", ["<Control>n"]),
                               ("win.preferences", ["<Control>comma"]),
                               ("win.shortcuts", ["<Control>question"])):
            self.set_accels_for_action(action, accels)

    def update_theme(self):
        dark = Adw.StyleManager.get_default().get_dark()
        for window in self.get_windows():
            window.remove_css_class("rusca-light" if dark else "rusca-dark")
            window.add_css_class("rusca-dark" if dark else "rusca-light")

    def do_activate(self):
        (self.props.active_window or LisseWindow(self)).present()


def main():
    GLib.set_prgname(APP_ID)
    GLib.set_application_name(APP_NAME)
    return LisseApp().run(sys.argv)


if __name__ == "__main__":
    sys.exit(main())
