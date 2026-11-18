#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
RuscaCat 1.99.3 — il gatto filosofo di RuscaLinux.

Un gatto animato con cui si parla a voce. Ascolta dal microfono, capisce
con un modello Whisper (ruscawhisper-engine, cioe' whisper.cpp), risponde
con un modello linguistico (ruscallama-engine, cioe' llama.cpp) e parla con
llama-tts dello stesso motore. Il gatto e' un filosofo heideggeriano,
scontroso e cinico, ma in fondo buono. Tutto resta sul computer.

Copyright (C) 2026 Nunzio Curcuruto — https://www.ruscalinux.org
Licenza: GNU GPL 3.0 o successiva.

Requisiti: Python 3.10+, PyGObject, GTK 4.18+, libadwaita 1.7+,
ruscallama-engine (llama-server e llama-tts), ruscawhisper-engine, ffmpeg,
libgtk-4-media-gstreamer, python3-markdown-it.
"""
import itertools
import json
import os
import re
import shutil
import sys
import threading

import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gdk, Gio, GLib, Gtk, Pango  # noqa: E402

BASE_DIR = os.path.dirname(os.path.realpath(__file__))
sys.path.insert(0, BASE_DIR)
import rusca_engine as engine  # noqa: E402
import rusca_mic as mic  # noqa: E402
import rusca_tts as tts  # noqa: E402
import rusca_whisper as whisper  # noqa: E402
from cat_view import CatView  # noqa: E402

APP_ID = "org.ruscalinux.RuscaCat"
APP_NAME = "RuscaCat"
APP_VERSION = "1.99.3"
STYLE_SRC = os.path.join(BASE_DIR, "style.css")
ICON_SRC = os.path.join(BASE_DIR, "ruscacat.svg")
LANG_DIR = os.path.join(BASE_DIR, "lang")
DOC_DIRS = (os.path.join(BASE_DIR, "docs"), "/usr/share/doc/ruscacat")
CONFIG_DIR = os.path.join(GLib.get_user_config_dir(), "ruscacat")
CONFIG_FILE = os.path.join(CONFIG_DIR, "settings.json")
COMPONENTS = (
    ("llama.cpp (llama-server, llama-tts)", "MIT — The ggml authors",
     "https://github.com/ggml-org/llama.cpp"),
    ("whisper.cpp (whisper-cli)", "MIT — The ggml authors", "https://github.com/ggml-org/whisper.cpp"),
    # Regola dell'evidenziato ==testo==, nel file a sé markdown_it_mark.py
    ("markdown-it-mark", "MIT — Vitaly Puzrin, Alex Kocharin; ExecutableBookProject",
     "https://github.com/markdown-it/markdown-it-mark"),
)

# I modelli sono quelli degli altri strumenti, nelle loro cartelle: chi ha
# gia' RuscaLLama, RuscaTranscriber e RuscaNarrator non copia nulla due volte.
LLM_USER_DIR = engine.MODEL_DIRS[-1]                # ~/.local/share/ruscallama/models
STT_USER_DIR = whisper.USER_MODEL_DIR               # ~/.local/share/ruscawhisper/models
TTS_USER_DIR = tts.USER_MODEL_DIR                   # ~/.local/share/ruscanarrator/models

# File di lavoro: tutto sotto ~/.cache/ruscacat (permessi 0700). I moduli
# comuni scrivono nella cartella indicata da WORK_DIR, che qui e' la nostra:
# RuscaTranscriber e RuscaNarrator aperti insieme non si toccano i file.
WORK_ROOT = os.path.join(GLib.get_user_cache_dir(), "ruscacat")
whisper.WORK_DIR = os.path.join(WORK_ROOT, "ears")
tts.WORK_DIR = os.path.join(WORK_ROOT, "voice")
MIC_DIR = os.path.join(WORK_ROOT, "mic")
PLAY_DIR = os.path.join(WORK_ROOT, "play")

CODES = [c for c, _n in tts.LANGUAGES]            # lingue della conversazione
CONTEXTS = (4096, 8192, 16384, 32768)
MAX_TOKENS = 400                                  # parla, non scrive saggi
HISTORY_TURNS = 24                                # scambi ricordati
DEFAULTS = {
    "llm_model": "", "stt_model": "", "tts_model": "", "speaker_file": "", "voice_name": "",
    "language": "", "speak": True, "auto_listen": True, "sensitivity": 5, "pause_ms": 900,
    "temperature": 0.8, "context": 8192, "seed": 42, "gpu": True, "gpu_device": "",
    "threads": engine.physical_cores(), "font_size": 0, "width": 900, "height": 640,
    "maximized": False, "theme": "system",
}
THEMES = ("system", "light", "dark")         # ordine delle voci nel menu


def apply_color_scheme(theme):
    """Tema chiaro/scuro: segue GNOME (predefinito) o è scelto dall'utente."""
    Adw.StyleManager.get_default().set_color_scheme({
        "light": Adw.ColorScheme.FORCE_LIGHT,
        "dark": Adw.ColorScheme.FORCE_DARK,
    }.get(theme, Adw.ColorScheme.DEFAULT))


# ── Traduzioni dell'interfaccia (lang/xx.json, ripiego en.json) ──────────────
# Ripieghi fra lingue vicine (specifiche, sezione 9.2).
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
    if cfg["language"] not in CODES:
        # Primo avvio: la lingua dell'interfaccia, se la voce la conosce.
        base = LANG.split("_")[0]
        cfg["language"] = base if base in CODES else "en"
    cfg["threads"] = max(1, min(cfg["threads"], os.cpu_count() or 1))
    cfg["sensitivity"] = min(mic.SENSITIVITY[1], max(mic.SENSITIVITY[0], cfg["sensitivity"]))
    cfg["pause_ms"] = min(mic.PAUSE_MS[1], max(mic.PAUSE_MS[0], cfg["pause_ms"]))
    cfg["temperature"] = min(1.5, max(0.0, cfg["temperature"]))
    if cfg["context"] not in CONTEXTS:
        cfg["context"] = 8192
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


def pick(saved, items, key=lambda x: x):
    """L'elemento salvato se c'è ancora, altrimenti il primo (gli elenchi dei
    modelli sono già in ordine, dal più grande)."""
    for item in items:
        if key(item) == saved:
            return item
    return items[0] if items else None


def prepare_work_dirs():
    """Cartella di lavoro privata (0700): conterrà la voce dell'utente."""
    os.makedirs(WORK_ROOT, mode=0o700, exist_ok=True)
    os.chmod(WORK_ROOT, 0o700)
    for d in (MIC_DIR, PLAY_DIR):
        os.makedirs(d, mode=0o700, exist_ok=True)


def clean_work_dirs():
    """Cancella tutto l'audio rimasto: voce dell'utente e voce del gatto."""
    whisper.clean_work_dir()
    tts.clean_work_dir()
    for d in (MIC_DIR, PLAY_DIR):
        shutil.rmtree(d, ignore_errors=True)


def speech_text(text):
    """Il testo da leggere ad alta voce: niente marcatori Markdown, come in
    RuscaNarrator (motore comune, speech_blocks)."""
    return " ".join(p.text for p in tts.markdown_pieces(text)).strip()


def conversation_markdown(history, cat_name):
    """La conversazione come documento Markdown. I testi sono protetti: ciò
    che si è detto resta testo, anche se contiene asterischi o indirizzi."""
    parts = [f"# {whisper.escape_markdown(_('conversation_title', name=cat_name))}"]
    for m in history:
        who = _("you") if m["role"] == "user" else cat_name
        text = " ".join(m["content"].split())          # un paragrafo per battuta
        parts.append(f"**{whisper.escape_markdown(who)}:** {whisper.escape_markdown(text)}")
    return "\n\n".join(parts) + "\n"


def show_about_dialog(parent, tr, app_id, app_name, version, description, has_icon,
                      components=()):
    """Finestra «Informazioni» comune ai RuscaLinux OS Tools.

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


# ── Dimensione del testo (conversazione) ─────────────────────────────────────
FONT_MIN, FONT_MAX = 6, 48


def system_font_size():
    """Dimensione del carattere di GNOME (Impostazioni → Accessibilità)."""
    settings = Gtk.Settings.get_default()
    name = settings.get_property("gtk-font-name") if settings else ""
    m = re.search(r"(\d+(?:\.\d+)?)\s*$", name or "")
    return float(m.group(1)) if m else 11.0


class FontSizeMixin:
    """Ctrl++ / Ctrl+− / Ctrl+0 e impostazione «Dimensione del testo». Vale
    per i widget con la classe rusca-content; 0 = dimensione di sistema."""

    def _init_font_size(self):
        self._font_provider = Gtk.CssProvider()
        Gtk.StyleContext.add_provider_for_display(
            Gdk.Display.get_default(), self._font_provider,
            Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION + 1)
        self._font_rows = []
        for name, step in (("zoom-in", 1), ("zoom-out", -1), ("zoom-reset", 0)):
            action = Gio.SimpleAction.new(name, None)
            action.connect("activate", lambda _a, _p, s=step: self.zoom(s))
            self.add_action(action)
        self._apply_font_size()

    def font_size(self):
        return self.cfg.get("font_size") or system_font_size()

    def _apply_font_size(self):
        size = self.font_size()
        self._font_provider.load_from_string(
            f".rusca-content, .rusca-content .monospace, .rusca-content.monospace "
            f"{{ font-size: {size:g}pt; }}")
        for row in self._font_rows:
            if abs(row.get_value() - size) > 0.01:
                row.set_value(size)

    def zoom(self, step):
        if step == 0:
            self.cfg["font_size"] = 0
        else:
            self.cfg["font_size"] = int(min(FONT_MAX, max(FONT_MIN, round(self.font_size()) + step)))
        save_settings(self.cfg)
        self._apply_font_size()

    def font_size_row(self):
        """Riga per le impostazioni, sincronizzata con le scorciatoie."""
        row = Adw.SpinRow.new_with_range(FONT_MIN, FONT_MAX, 1)
        row.set_title(_("font_size"))
        row.set_subtitle(_("font_size_sub"))
        row.set_value(self.font_size())

        def changed(r, _p):
            if abs(r.get_value() - self.font_size()) > 0.01:
                self.cfg["font_size"] = int(r.get_value())
                save_settings(self.cfg)
                self._apply_font_size()
        row.connect("notify::value", changed)
        row.connect("destroy", lambda r: r in self._font_rows and self._font_rows.remove(r))
        self._font_rows.append(row)
        return row


# ── Finestra principale ──────────────────────────────────────────────────────
class CatWindow(FontSizeMixin, Adw.ApplicationWindow):
    """Il dialogo è una catena di passi, uno per volta:
        listening  il microfono è aperto e aspetta una frase
        hearing    whisper-cli trascrive la frase (il microfono è chiuso)
        thinking   il modello risponde; le frasi pronte vanno alla voce
        speaking   il gatto parla; le frasi dopo si preparano intanto
        idle       nessun passo in corso
    Il microfono resta chiuso mentre il gatto pensa e parla, così non sente
    se stesso; con «Ascolta di nuovo» si riapre alla fine della risposta."""

    def __init__(self, app):
        super().__init__(application=app, title=APP_NAME)
        self.cfg = load_settings()
        self.set_default_size(self.cfg["width"], self.cfg["height"])
        self.set_size_request(360, 294)
        if self.cfg["maximized"]:
            self.maximize()
        self.cat_name = _("cat_name")
        self.phase = "idle"
        self.listening = False          # l'utente ha acceso l'ascolto
        self.history = []               # [{"role", "content"}], solo in memoria
        self.log_lines = []
        self.llm_models, self.stt_models, self.voices = [], [], []
        self.devices = []
        self._devices_loading = False
        self._row_items = {}
        self._rows = {}
        self._updating = False
        self._monitors = []
        self._models_timer = 0
        self._force_close = False
        # Una risposta: le callback di una risposta interrotta si scartano.
        self.reply_id = 0
        self.reply_done = True
        self.reply_label = None
        self.reply_text = ""
        self.stop_event = threading.Event()
        self.splitter = None
        self.say_queue = []             # frasi da far leggere alla voce
        self.play_queue = []            # WAV pronti da ascoltare
        self.speaker = None             # llama-tts in corso
        self.media = None               # WAV in ascolto
        self.media_clip = None
        self.envelope = []
        self.voice_failed = False
        self.clip_count = itertools.count(1)
        self.mic = None
        self.mic_id = 0
        self._heard_file = None
        self.transcriber = whisper.Transcriber(on_log=self._on_log, on_done=self._on_heard)
        self.engine = engine.Engine(APP_ID, on_log=self._on_log, on_state=self._on_engine_state)
        self._build_actions()
        self._init_font_size()
        self._build_ui()
        try:
            clean_work_dirs()
            prepare_work_dirs()
        except OSError:
            pass
        self._watch_models()
        self._refresh_models()
        self._set_phase("idle")
        self.connect("close-request", self._on_close)
        GLib.idle_add(self._first_start)

    # ── azioni ────────────────────────────────────────────────────────────
    def _build_actions(self):
        for name, cb in (("listen", self.toggle_listening), ("hush", self.hush),
                         ("new", self.new_conversation), ("save", self.save_conversation),
                         ("preferences", self.show_preferences), ("show-log", self.show_log),
                         ("restart-engine", self.restart_engine),
                         ("guide", self.show_guide), ("shortcuts", self.show_shortcuts),
                         ("about", self.show_about)):
            action = Gio.SimpleAction.new(name, None)
            action.connect("activate", lambda _a, _p, f=cb: f())
            self.add_action(action)

    # ── interfaccia ───────────────────────────────────────────────────────
    def _build_ui(self):
        header = Adw.HeaderBar()
        self.title = Adw.WindowTitle(title=APP_NAME)
        header.set_title_widget(self.title)
        new_btn = Gtk.Button(icon_name="list-add-symbolic", action_name="win.new",
                             tooltip_text=_("new_conversation"))
        new_btn.update_property([Gtk.AccessibleProperty.LABEL], [_("new_conversation")])
        header.pack_start(new_btn)
        menu = Gio.Menu()
        tool = Gio.Menu()
        tool.append(_("save_conversation"), "win.save")
        tool.append(_("restart_engine"), "win.restart-engine")
        tool.append(_("engine_log"), "win.show-log")
        menu.append_section(None, tool)
        app_menu = Gio.Menu()
        app_menu.append(_("preferences"), "win.preferences")
        app_menu.append(_("guide"), "win.guide")
        app_menu.append(_("shortcuts"), "win.shortcuts")
        app_menu.append(_("about"), "win.about")
        menu.append_section(None, app_menu)
        header.pack_end(Gtk.MenuButton(icon_name="open-menu-symbolic", menu_model=menu,
                                       primary=True, tooltip_text=_("main_menu")))

        self.banner = Adw.Banner()
        self.banner.connect("button-clicked", lambda _b: self._banner_action())
        self._banner_folder = None

        # Il gatto, con lo stato scritto sotto (non si affida al disegno).
        self.cat = CatView()
        self.cat.mouth_source = self._mouth
        self.status = Gtk.Label(wrap=True, justify=Gtk.Justification.CENTER,
                                margin_start=12, margin_end=12)
        self.status.add_css_class("heading")
        cat_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6,
                          margin_top=12, margin_bottom=12, margin_start=12, margin_end=12)
        cat_box.append(self.cat)
        cat_box.append(self.status)

        # La conversazione.
        empty = Adw.StatusPage(title=_("empty_title", name=self.cat_name),
                               description=_("empty_desc", name=self.cat_name), vexpand=True)
        self.messages = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12,
                                margin_top=12, margin_bottom=12, margin_start=12, margin_end=12)
        self.messages.update_property([Gtk.AccessibleProperty.LABEL], [_("conversation")])
        self.scroll = Gtk.ScrolledWindow(child=self.messages, vexpand=True, hexpand=True,
                                         hscrollbar_policy=Gtk.PolicyType.NEVER)
        self.chat_stack = Gtk.Stack(vexpand=True, hexpand=True)
        self.chat_stack.add_named(empty, "empty")
        self.chat_stack.add_named(self.scroll, "chat")
        chat_frame = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, hexpand=True, vexpand=True,
                             margin_top=12, margin_bottom=12, margin_end=12)
        chat_frame.add_css_class("card")
        chat_frame.append(self.chat_stack)
        self.chat_frame = chat_frame

        self.split = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, homogeneous=True)
        self.split.append(cat_box)
        self.split.append(chat_frame)
        self.toasts = Adw.ToastOverlay(child=self.split)

        # In basso: scrivere, ascoltare, zittire.
        self.entry = Gtk.Entry(hexpand=True, placeholder_text=_("write_to", name=self.cat_name))
        self.entry.update_property([Gtk.AccessibleProperty.LABEL], [_("write_to", name=self.cat_name)])
        self.entry.connect("activate", lambda _e: self.send_typed())
        self.entry.connect("changed", lambda _e: self._refresh_actions())
        self.send_btn = Gtk.Button(icon_name="go-up-symbolic", tooltip_text=_("send"))
        self.send_btn.update_property([Gtk.AccessibleProperty.LABEL], [_("send")])
        self.send_btn.connect("clicked", lambda _b: self.send_typed())
        self.hush_btn = Gtk.Button(label=_("hush"), action_name="win.hush", visible=False)
        self.hush_btn.add_css_class("destructive-action")
        self.listen_btn = Gtk.Button(action_name="win.listen")
        self.listen_btn.add_css_class("pill")
        self.listen_content = Adw.ButtonContent(icon_name="audio-input-microphone-symbolic")
        self.listen_btn.set_child(self.listen_content)
        bottom = Gtk.Box(spacing=6, margin_start=12, margin_end=12, margin_top=6, margin_bottom=12)
        bottom.append(self.entry)
        bottom.append(self.send_btn)
        bottom.append(self.hush_btn)
        bottom.append(self.listen_btn)

        view = Adw.ToolbarView(content=self.toasts)
        view.add_top_bar(header)
        view.add_top_bar(self.banner)
        view.add_bottom_bar(bottom)
        self.set_content(view)

        # Finestra stretta: il gatto sopra la conversazione; bassa: gatto piccolo.
        narrow = Adw.Breakpoint.new(Adw.BreakpointCondition.parse("max-width: 640sp"))
        narrow.add_setter(self.split, "orientation", Gtk.Orientation.VERTICAL)
        narrow.add_setter(self.split, "homogeneous", False)
        narrow.add_setter(chat_frame, "margin-start", 12)
        narrow.add_setter(chat_frame, "margin-top", 0)
        narrow.add_setter(self.cat, "height-request", 150)
        narrow.add_setter(self.cat, "vexpand", False)
        self.add_breakpoint(narrow)
        short = Adw.Breakpoint.new(Adw.BreakpointCondition.parse("max-height: 480sp"))
        short.add_setter(self.cat, "height-request", 90)
        short.add_setter(self.cat, "width-request", 90)
        short.add_setter(self.status, "visible", False)
        self.add_breakpoint(short)

        style = Adw.StyleManager.get_default()
        style.connect("notify::dark", lambda *_a: self._update_cat_colors())
        style.connect("notify::high-contrast", lambda *_a: self._update_cat_colors())
        self._update_cat_colors()

    def _update_cat_colors(self):
        style = Adw.StyleManager.get_default()
        self.cat.set_colors(style.get_dark(), style.get_high_contrast())

    # ── stato ─────────────────────────────────────────────────────────────
    def _llm(self):
        return self.cfg["llm_model"] if self.cfg["llm_model"] in self.llm_models else None

    def _stt(self):
        return self.cfg["stt_model"] if self.cfg["stt_model"] in self.stt_models else None

    def _voice(self):
        return pick(self.cfg["tts_model"], self.voices, key=lambda v: v.model) \
            if self.cfg["tts_model"] else None

    def _can_listen(self):
        return bool(self._stt()) and bool(whisper.find_binary()) and bool(mic.find_ffmpeg())

    def _can_speak(self):
        return (self.cfg["speak"] and bool(self._voice()) and bool(tts.find_binary())
                and bool(tts.find_ffmpeg()) and not self.voice_failed)

    def _busy(self):
        return self.phase in ("hearing", "thinking", "speaking")

    def _set_phase(self, phase):
        self.phase = phase
        name = self.cat_name
        if phase == "idle" and self.engine.state != "ready":
            cat, text = "sleep", (_("status_waking", name=name) if self.engine.state == "starting"
                                  else _("status_asleep", name=name))
        else:
            cat, text = {
                "idle": ("idle", _("status_idle", name=name)),
                "listening": ("listen", _("status_listening", name=name)),
                "hearing": ("hear", _("status_hearing", name=name)),
                "thinking": ("think", _("status_thinking", name=name)),
                "speaking": ("speak", _("status_speaking", name=name)),
            }[phase]
        self.status.set_label(text)
        self.cat.set_state(cat, text)
        self._refresh_actions()

    def _refresh_actions(self):
        busy = self._busy()
        self.lookup_action("hush").set_enabled(busy)
        self.hush_btn.set_visible(self.phase in ("thinking", "speaking"))
        self.lookup_action("listen").set_enabled(self._can_listen() or self.listening)
        self.lookup_action("save").set_enabled(bool(self.history))
        self.lookup_action("new").set_enabled(bool(self.history) or busy)
        self.lookup_action("restart-engine").set_enabled(bool(self._llm()))
        self.send_btn.set_sensitive(bool(self.entry.get_text().strip()) and bool(self._llm()))
        if self.listening:
            self.listen_content.set_label(_("stop_listening"))
            self.listen_btn.remove_css_class("suggested-action")
        else:
            self.listen_content.set_label(_("listen"))
            self.listen_btn.add_css_class("suggested-action")
        self.listen_btn.set_tooltip_text(_("listen_tip"))

    def _refresh_banner(self):
        b, folder, label = self.banner, None, None
        if not engine.find_binary():
            title = _("banner_no_engine")
        elif not self._llm():
            title, folder = _("banner_no_llm", name=self.cat_name), LLM_USER_DIR
        elif not whisper.find_binary():
            title = _("banner_no_whisper")
        elif not mic.find_ffmpeg():
            title = _("err_no_ffmpeg")
        elif not self._stt():
            title, folder = _("banner_no_stt", name=self.cat_name), STT_USER_DIR
        elif self.cfg["speak"] and not self._voice():
            title, folder = _("banner_no_voice", name=self.cat_name), TTS_USER_DIR
        else:
            title = None
        if folder:
            label = _("open_models_folder")
        self._banner_folder = folder
        b.set_button_label(label)
        if title:
            b.set_title(title)
        b.set_revealed(bool(title))
        self._refresh_actions()

    def _banner_action(self):
        if self._banner_folder:
            self.open_folder(self._banner_folder)

    def _set(self, key, value):
        self.cfg[key] = value
        save_settings(self.cfg)

    def _toast(self, text, timeout=5):
        self.toasts.add_toast(Adw.Toast(title=GLib.markup_escape_text(text), timeout=timeout))

    def _on_log(self, line):
        self.log_lines.append(line)
        del self.log_lines[:-3000]

    # ── modelli ───────────────────────────────────────────────────────────
    def _watch_models(self):
        """Tiene d'occhio le cartelle dei modelli: un modello copiato
        compare senza riavviare il programma."""
        for d in (LLM_USER_DIR, STT_USER_DIR, TTS_USER_DIR):
            try:
                os.makedirs(d, exist_ok=True)
            except OSError:
                pass
        dirs = set(engine.MODEL_DIRS) | set(whisper.MODEL_DIRS) | set(tts.MODEL_DIRS)
        for d in sorted(dirs):
            if not os.path.isdir(d):
                continue
            try:
                monitor = Gio.File.new_for_path(d).monitor_directory(
                    Gio.FileMonitorFlags.WATCH_MOVES, None)
            except GLib.Error:
                continue
            monitor.connect("changed", self._on_models_changed)
            self._monitors.append(monitor)

    def _on_models_changed(self, *_a):
        # Una copia di qualche GB manda molti eventi: si aspetta che finisca.
        if self._models_timer:
            GLib.source_remove(self._models_timer)
        self._models_timer = GLib.timeout_add(1500, self._models_timeout)

    def _models_timeout(self):
        self._models_timer = 0
        old = self._llm()
        self._refresh_models()
        if self._llm() and self._llm() != old:
            self.restart_engine()
        return False

    def _refresh_models(self):
        self.llm_models = engine.find_models()
        self.stt_models = whisper.find_models()
        self.voices = tts.find_voices()
        # Il modello salvato, o il più grande. Per la voce: il più grande.
        for key, items, get in (("llm_model", self.llm_models, lambda x: x),
                                ("stt_model", self.stt_models, lambda x: x),
                                ("tts_model", self.voices, lambda v: v.model)):
            chosen = pick(self.cfg[key], items, get)
            value = get(chosen) if chosen is not None else ""
            if value != self.cfg[key]:
                self._set(key, value)
        self._fill_model_rows()
        self._refresh_banner()

    def open_folder(self, folder):
        try:
            os.makedirs(folder, exist_ok=True)
        except OSError as e:
            self._show_error(_("open_error"), str(e))
            return
        Gtk.FileLauncher.new(Gio.File.new_for_path(folder)).launch(self, None, None)

    # ── motore ────────────────────────────────────────────────────────────
    def _first_start(self):
        self.start_engine()
        return False

    def _engine_args(self):
        cfg = self.cfg
        args = ["-t", cfg["threads"], "-c", cfg["context"], "-b", 2048,
                "--reasoning-format", "deepseek"]
        if cfg["gpu"] and cfg["gpu_device"]:
            device = engine.device_name(cfg["gpu_device"], self.devices or engine.list_devices())
            if device:
                args += ["--device", device]
        return args

    def start_engine(self):
        if self.engine.running or not self._llm() or not engine.find_binary():
            self._set_phase(self.phase)
            return
        try:
            self.engine.start(self._llm(), self._engine_args(), self.cfg["gpu"])
        except engine.EngineError as e:
            self._show_error(_(e.key), e.detail)
        self._set_phase(self.phase)

    def restart_engine(self):
        self.hush()
        self.engine.stop(wait=True)
        self.start_engine()

    def _on_engine_state(self, state, detail=""):
        if state == "error" and detail:
            self.toasts.add_toast(Adw.Toast(title=_("engine_died"), timeout=8,
                                            button_label=_("engine_log"),
                                            action_name="win.show-log"))
        model = os.path.basename(self.engine.model or "") if state == "ready" else ""
        self.title.set_subtitle(model)
        if not self._busy():
            self._set_phase("listening" if self.phase == "listening" else "idle")
        return False

    # ── ascolto ───────────────────────────────────────────────────────────
    def toggle_listening(self):
        if self.listening:
            self.listening = False
            self._close_mic()
            if self.phase == "listening":
                self._set_phase("idle")
            else:
                self._refresh_actions()
            return
        if not self._can_listen():
            self._refresh_banner()
            return
        self.listening = True
        if not self._busy():
            self._open_mic()
        else:
            self._refresh_actions()

    def _open_mic(self):
        self._close_mic()
        self.mic_id += 1
        mid = self.mic_id
        self.mic = mic.Microphone(
            on_level=lambda level: mid == self.mic_id and self.cat.set_level(level),
            on_utterance=lambda pcm: mid == self.mic_id and self._on_utterance(pcm),
            on_stopped=lambda error: mid == self.mic_id and self._on_mic_stopped(error),
            on_log=self._on_log)
        try:
            self.mic.start(self.cfg["sensitivity"], self.cfg["pause_ms"])
        except mic.MicError as e:
            self.listening = False
            self._set_phase("idle")
            self._show_error(_(e.key), e.detail)
            return
        self._set_phase("listening")

    def _close_mic(self):
        if self.mic is not None:
            self.mic_id += 1             # le sue ultime callback si scartano
            self.mic.stop()
            self.mic = None

    def _on_mic_stopped(self, error):
        self.mic = None
        if error is not None:
            self.listening = False
            if self.phase == "listening":
                self._set_phase("idle")
            self._show_error(_("err_mic"), error.detail)

    def _on_utterance(self, pcm):
        # Mentre trascrive, pensa e parla il gatto non ascolta: non deve
        # sentire se stesso.
        self._close_mic()
        if not self._stt():
            self._set_phase("idle")
            return
        path = os.path.join(MIC_DIR, f"frase-{next(self.clip_count)}.wav")
        if self.transcriber.running:
            # Una trascrizione appena interrotta si sta chiudendo: start()
            # non partirebbe.
            self.transcriber.cancel()
            self.transcriber.wait(3)
        try:
            prepare_work_dirs()
            mic.write_wav(path, pcm)
            self.transcriber.start(path, self._stt(), self.cfg["language"], self.cfg["threads"],
                                   self.cfg["gpu"], self.cfg["gpu_device"])
        except (OSError, whisper.WhisperError) as e:
            self._remove(path)
            self._show_error(_(getattr(e, "key", "err_engine")), getattr(e, "detail", str(e)))
            self._resume()
            return
        self._heard_file = path
        self._set_phase("hearing")

    def _on_heard(self, error, _language, segments):
        self._remove(getattr(self, "_heard_file", None))
        if self.phase != "hearing":            # zittito nel frattempo
            return
        if error == "cancelled":
            self._resume()
            return
        if error is not None:
            self._show_error(_(error.key), error.detail)
            self._resume()
            return
        text = whisper.plain_text(segments).replace("\n\n", " ").strip()
        if mic.is_noise(text):
            self._resume()
            return
        self.send_message(text)

    def _resume(self):
        """Fine di un passo: si torna ad ascoltare, se l'ascolto è acceso."""
        if self.listening and self._can_listen():
            self._open_mic()
        else:
            self._set_phase("idle")

    # ── conversazione ─────────────────────────────────────────────────────
    def send_typed(self):
        text = self.entry.get_text().strip()
        if not text or not self._llm():
            return
        self.entry.set_text("")
        self.send_message(text)

    def _add_bubble(self, who, text, mine):
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=3,
                      halign=Gtk.Align.END if mine else Gtk.Align.START)
        name = Gtk.Label(label=who, xalign=0)
        name.add_css_class("heading")
        body = Gtk.Label(label=text, wrap=True, xalign=0, selectable=True,
                         wrap_mode=Pango.WrapMode.WORD_CHAR, max_width_chars=60)
        body.add_css_class("rusca-content")
        box.append(name)
        box.append(body)
        self.messages.append(box)
        # Un'etichetta selezionabile nasce con tutto il testo selezionato.
        GLib.idle_add(lambda: body.select_region(0, 0) and False)
        self.chat_stack.set_visible_child_name("chat")
        GLib.idle_add(self._scroll_end)
        return body

    def _scroll_end(self):
        adj = self.scroll.get_vadjustment()
        adj.set_value(adj.get_upper())
        return False

    def send_message(self, text):
        if self._busy():
            self.hush(resume=False)
        self._close_mic()
        self.history.append({"role": "user", "content": text})
        self._add_bubble(_("you"), text, True)
        self.entry.grab_focus()
        if not self.engine.running:
            self.start_engine()
        self.reply_id += 1
        rid = self.reply_id
        self.reply_done = False
        self.reply_text = ""
        self.reply_label = None
        self.voice_failed = False
        self.splitter = mic.SentenceSplitter()
        self.stop_event = threading.Event()
        self._set_phase("thinking")
        body = self._request_body()
        threading.Thread(target=self._generate, args=(rid, body, self.stop_event),
                         daemon=True).start()

    def _request_body(self):
        language = dict(tts.LANGUAGES).get(self.cfg["language"], "English")
        messages = [{"role": "system",
                     "content": _("persona", name=self.cat_name, language=language)}]
        messages += self.history[-2 * HISTORY_TURNS:]
        return dict(messages=messages, max_tokens=MAX_TOKENS, reasoning_effort="none",
                    temperature=self.cfg["temperature"], top_p=0.95)

    def _generate(self, rid, body, stop_event):
        error = None
        try:
            if not self.engine.wait_ready(stop_event):
                if not stop_event.is_set():
                    error = _("engine_not_ready")
            else:
                for text, _reasoning in self.engine.chat_stream(body, stop_event):
                    if text:
                        GLib.idle_add(self._on_delta, rid, text)
        except (engine.EngineError, OSError) as e:
            error = _("connection_error", error=str(e))
        GLib.idle_add(self._on_reply_done, rid, error)

    def _on_delta(self, rid, text):
        if rid != self.reply_id:
            return False
        if not self.reply_text:
            text = text.lstrip()
            if not text:
                return False
        self.reply_text += text
        if self.reply_label is None:
            self.reply_label = self._add_bubble(self.cat_name, "", False)
        # Si mostra il testo come lo dice la voce: senza marcatori Markdown,
        # che i modelli usano anche quando si chiede di non farlo.
        self.reply_label.set_label(speech_text(self.reply_text) or self.reply_text.strip())
        GLib.idle_add(self._scroll_end)
        if self._can_speak():
            for sentence in self.splitter.feed(text):
                self._say(sentence)
        return False

    def _on_reply_done(self, rid, error):
        if rid != self.reply_id:
            return False
        self.reply_done = True
        if self.reply_text.strip():
            self.history.append({"role": "assistant", "content": self.reply_text.strip()})
            if self._can_speak():
                self._say(self.splitter.flush())
        elif error:
            self._add_bubble(self.cat_name, error, False)
        self._maybe_finished()
        return False

    # ── voce ──────────────────────────────────────────────────────────────
    def _say(self, text):
        text = speech_text(text or "")
        if text:
            self.say_queue.append(text)
            self._pump_voice()

    def _pump_voice(self):
        """Una frase alla volta a llama-tts; mentre il gatto ne dice una, si
        prepara la successiva."""
        if self.speaker is not None or not self.say_queue or not self._can_speak():
            return
        text = self.say_queue.pop(0)
        rid = self.reply_id
        speaker = tts.Speaker(on_log=self._on_log,
                              on_done=lambda e, p, _s: self._on_voice_ready(rid, speaker, e, p))
        c = self.cfg
        try:
            speaker.start([tts.Piece(text)], self._voice(), language=c["language"],
                          speaker_file=c["speaker_file"] if os.path.isfile(c["speaker_file"] or "")
                          else "", voice_name=c["voice_name"].strip(), gpu=c["gpu"],
                          gpu_device=c["gpu_device"], threads=c["threads"], seed=c["seed"],
                          normalize=True)
        except tts.TTSError as e:
            self._voice_error(e)
            return
        self.speaker = speaker

    def _on_voice_ready(self, rid, speaker, error, path):
        if speaker is self.speaker:
            self.speaker = None
        if rid != self.reply_id:
            speaker.discard()
            return
        if error is None and path:
            clip = os.path.join(PLAY_DIR, f"voce-{next(self.clip_count)}.wav")
            try:
                prepare_work_dirs()
                os.replace(path, clip)
                self.play_queue.append(clip)
            except OSError:
                pass
        elif error != "cancelled":
            self._voice_error(error)
        speaker.discard()
        self._pump_play()
        self._pump_voice()
        self._maybe_finished()

    def _voice_error(self, error):
        """La voce non funziona: il gatto continua per iscritto."""
        self.voice_failed = True
        self.say_queue.clear()
        self.toasts.add_toast(Adw.Toast(title=_("voice_failed", name=self.cat_name), timeout=8,
                                        button_label=_("engine_log"), action_name="win.show-log"))
        self._on_log(f"ruscacat: {getattr(error, 'key', error)} {getattr(error, 'detail', '')}")

    def _pump_play(self):
        if self.media is not None or not self.play_queue:
            return
        clip = self.play_queue.pop(0)
        self.envelope = mic.envelope(clip)
        media = Gtk.MediaFile.new_for_filename(clip)
        media.connect("notify::ended", lambda m, _p: m.get_ended() and self._on_clip_end(m, clip))
        media.connect("notify::error", lambda m, _p: m.get_error() and self._on_clip_end(m, clip))
        self.media = media
        self.media_clip = clip
        self._set_phase("speaking")
        media.play()

    def _on_clip_end(self, media, clip):
        if media is not self.media:
            return
        if media.get_error() is not None:
            # Di solito manca libgtk-4-media-gstreamer: il gatto scrive soltanto.
            self._voice_error(tts.TTSError("err_play", media.get_error().message))
        self.media = None
        self.media_clip = None
        self.envelope = []
        self._remove(clip)
        self._pump_play()
        self._maybe_finished()

    def _mouth(self):
        media = self.media
        if media is None or not media.get_playing():
            return 0.0
        return mic.envelope_at(self.envelope, media.get_timestamp() / 1000)

    def _maybe_finished(self):
        """La risposta è finita quando il testo è arrivato e la voce ha
        detto tutto."""
        # Fra una frase e l'altra resta nello stato «parla», a bocca chiusa.
        if not self.reply_done:
            return
        if self.say_queue and self._can_speak() or self.speaker or self.play_queue or self.media:
            return
        if self.phase in ("thinking", "speaking"):
            if self.listening and self.cfg["auto_listen"]:
                self._resume()
            else:
                self.listening = False
                self._set_phase("idle")

    def hush(self, resume=True):
        """Ferma tutto: risposta, voce, trascrizione. Quello che il gatto ha
        già scritto resta nella conversazione. Con `resume` si torna ad
        ascoltare, se l'ascolto è acceso."""
        if not self._busy():
            return
        self.reply_id += 1
        self.stop_event.set()
        self.engine.cancel()
        if self.transcriber.running:
            self.transcriber.cancel()
        if self.speaker is not None:
            self.speaker.cancel()
            self.speaker = None
        self.say_queue.clear()
        if self.media is not None:
            media, self.media = self.media, None
            media.set_playing(False)
            self._remove(self.media_clip)
            self.media_clip = None
        for clip in self.play_queue:
            self._remove(clip)
        self.play_queue.clear()
        if not self.reply_done and self.reply_text.strip():
            self.history.append({"role": "assistant", "content": self.reply_text.strip()})
        self.reply_done = True
        self.phase = "idle"
        if resume:
            self._resume()

    def new_conversation(self):
        self.hush()
        self.history.clear()
        child = self.messages.get_first_child()
        while child is not None:
            nxt = child.get_next_sibling()
            self.messages.remove(child)
            child = nxt
        self.chat_stack.set_visible_child_name("empty")
        self._refresh_actions()

    def save_conversation(self):
        if not self.history:
            return
        filt = Gtk.FileFilter()
        filt.set_name(_("markdown_files"))
        filt.add_suffix("md")
        store = Gio.ListStore.new(Gtk.FileFilter)
        store.append(filt)
        dialog = Gtk.FileDialog(title=_("save_conversation").rstrip("…"), filters=store,
                                initial_name=_("conversation_file", name=self.cat_name) + ".md")
        text = conversation_markdown(self.history, self.cat_name)

        def done(d, result):
            try:
                path = d.save_finish(result).get_path()
            except GLib.Error:
                return
            try:
                tmp = path + ".part"
                with open(tmp, "w", encoding="utf-8") as f:
                    f.write(text)
                os.replace(tmp, path)
                self._toast(_("saved", name=os.path.basename(path)))
            except OSError as e:
                self._show_error(_("save_error"), str(e))
        dialog.save(self, None, done)

    @staticmethod
    def _remove(path):
        if path:
            try:
                os.unlink(path)
            except OSError:
                pass

    # ── preferenze ────────────────────────────────────────────────────────
    def show_preferences(self):
        page = Adw.PreferencesPage()
        look = Adw.PreferencesGroup(title=_("group_look"))
        theme_row = Adw.ComboRow(title=_("theme"), model=Gtk.StringList.new(
            [_(f"theme_{t}") for t in THEMES]))
        theme = self.cfg.get("theme", "system")
        theme_row.set_selected(THEMES.index(theme) if theme in THEMES else 0)
        theme_row.connect("notify::selected", self._on_theme)
        look.add(theme_row)
        look.add(self.font_size_row())
        page.add(look)

        talk = Adw.PreferencesGroup(title=_("group_conversation"))
        lang = Adw.ComboRow(title=_("language"), subtitle=_("language_sub"),
                            model=Gtk.StringList.new([n for _c, n in tts.LANGUAGES]))
        lang.set_selected(CODES.index(self.cfg["language"]))
        lang.connect("notify::selected",
                     lambda r, _p: self._set("language", CODES[r.get_selected()]))
        talk.add(lang)
        for key in ("speak", "auto_listen"):
            row = Adw.SwitchRow(title=_(key), subtitle=_(f"{key}_sub", name=self.cat_name),
                                active=self.cfg[key])
            row.connect("notify::active", lambda r, _p, k=key: (
                self._set(k, r.get_active()), self._refresh_banner()))
            talk.add(row)
        temp = Adw.SpinRow.new_with_range(0.0, 1.5, 0.05)
        temp.set_digits(2)
        temp.set_title(_("temperature"))
        temp.set_subtitle(_("temperature_sub"))
        temp.set_value(self.cfg["temperature"])
        temp.connect("notify::value", lambda r, _p: self._set("temperature", round(r.get_value(), 2)))
        talk.add(temp)
        page.add(talk)

        brain = Adw.PreferencesGroup(title=_("group_brain"), description=_("llm_hint"))
        self._rows["llm_model"] = Adw.ComboRow(title=_("model"))
        brain.add(self._rows["llm_model"])
        ctx = Adw.ComboRow(title=_("context"), subtitle=_("context_sub"),
                           model=Gtk.StringList.new([f"{c:,}".replace(",", ".") for c in CONTEXTS]))
        ctx.set_selected(CONTEXTS.index(self.cfg["context"]))
        ctx.connect("notify::selected", lambda r, _p: self._set_engine("context",
                                                                       CONTEXTS[r.get_selected()]))
        brain.add(ctx)
        brain.add(self._folder_row(LLM_USER_DIR))
        page.add(brain)

        ears = Adw.PreferencesGroup(title=_("group_ears"), description=_("stt_hint"))
        self._rows["stt_model"] = Adw.ComboRow(title=_("model"))
        ears.add(self._rows["stt_model"])
        sens = Adw.SpinRow.new_with_range(*mic.SENSITIVITY, 1)
        sens.set_title(_("sensitivity"))
        sens.set_subtitle(_("sensitivity_sub"))
        sens.set_value(self.cfg["sensitivity"])
        sens.connect("notify::value", lambda r, _p: self._set_listen("sensitivity",
                                                                     int(r.get_value())))
        ears.add(sens)
        pause = Adw.SpinRow.new_with_range(mic.PAUSE_MS[0] / 1000, mic.PAUSE_MS[1] / 1000, 0.1)
        pause.set_digits(1)
        pause.set_title(_("pause"))
        pause.set_subtitle(_("pause_sub"))
        pause.set_value(self.cfg["pause_ms"] / 1000)
        pause.connect("notify::value", lambda r, _p: self._set_listen(
            "pause_ms", int(round(r.get_value() * 1000))))
        ears.add(pause)
        ears.add(self._folder_row(STT_USER_DIR))
        page.add(ears)

        voice = Adw.PreferencesGroup(title=_("group_voice"), description=_("tts_hint"))
        self._rows["tts_model"] = Adw.ComboRow(title=_("model"))
        voice.add(self._rows["tts_model"])
        self._rows["speaker_file"] = Adw.ComboRow(title=_("speaker_file"),
                                                  subtitle=_("speaker_file_sub"))
        voice.add(self._rows["speaker_file"])
        name = Adw.EntryRow(title=_("voice_name"), text=self.cfg["voice_name"])
        name.connect("changed", lambda r: self._set("voice_name", r.get_text()))
        voice.add(name)
        seed = Adw.SpinRow.new_with_range(0, 2 ** 31 - 1, 1)
        seed.set_title(_("seed"))
        seed.set_subtitle(_("seed_sub"))
        seed.set_value(self.cfg["seed"])
        seed.connect("notify::value", lambda r, _p: self._set("seed", int(r.get_value())))
        voice.add(seed)
        voice.add(self._folder_row(TTS_USER_DIR))
        page.add(voice)
        for key, row in self._rows.items():
            row.connect("notify::selected", self._on_model_row, key)
        self._fill_model_rows()

        eng = Adw.PreferencesGroup(title=_("group_engine"))
        gpu = Adw.SwitchRow(title=_("gpu"), subtitle=_("gpu_sub"), active=self.cfg["gpu"])
        gpu.connect("notify::active", self._on_gpu)
        eng.add(gpu)
        self.device_row = Adw.ComboRow(title=_("gpu_device"), use_subtitle=True,
                                       sensitive=self.cfg["gpu"])
        self._fill_device_row()
        self.device_row.connect("notify::selected", self._on_device)
        eng.add(self.device_row)
        self._load_devices()
        threads = Adw.SpinRow.new_with_range(1, max(1, os.cpu_count() or 1), 1)
        threads.set_title(_("threads"))
        threads.set_subtitle(_("threads_sub", n=engine.physical_cores()))
        threads.set_value(min(self.cfg["threads"], os.cpu_count() or 1))
        threads.connect("notify::value", lambda r, _p: self._set_engine("threads",
                                                                        int(r.get_value())))
        eng.add(threads)
        page.add(eng)

        dialog = Adw.PreferencesDialog(title=_("preferences").rstrip("…"))
        dialog.add(page)
        dialog.connect("closed", self._on_preferences_closed)
        dialog.present(self)

    def _folder_row(self, folder):
        row = Adw.ActionRow(title=_("open_models_folder"), subtitle=folder, activatable=True)
        row.add_suffix(Gtk.Image(icon_name="folder-open-symbolic"))
        row.connect("activated", lambda _r: self.open_folder(folder))
        return row

    def _on_preferences_closed(self, _dialog):
        self._rows = {}
        self._row_items = {}
        self.device_row = None
        if self._engine_dirty:
            self._engine_dirty = False
            self.restart_engine()

    _engine_dirty = False

    def _set_engine(self, key, value):
        """Opzioni del motore: valgono al prossimo avvio, cioè alla chiusura
        delle preferenze."""
        if self.cfg.get(key) != value:
            self._set(key, value)
            self._engine_dirty = True

    def _set_listen(self, key, value):
        self._set(key, value)
        if self.phase == "listening":
            self._open_mic()

    def _fill_model_rows(self):
        """Elenchi dei tre modelli e delle voci di riferimento."""
        sources = {
            "llm_model": [(os.path.basename(p), p) for p in self.llm_models],
            "stt_model": [(os.path.basename(p), p) for p in self.stt_models],
            "tts_model": [(os.path.basename(v.model), v.model) for v in self.voices],
            "speaker_file": [(_("speaker_none"), "")] + tts.find_voice_files(),
        }
        self._updating = True
        for key, row in self._rows.items():
            items = sources[key]
            saved = self.cfg[key]
            if key == "speaker_file" and saved and saved not in [p for _n, p in items]:
                items.append((os.path.basename(saved), saved))
            self._row_items[key] = [p for _n, p in items]
            row.set_model(Gtk.StringList.new([n for n, _p in items] or [_("no_model")]))
            row.set_sensitive(bool(items))
            paths = self._row_items[key]
            row.set_selected(paths.index(saved) if saved in paths else 0)
        self._updating = False

    def _on_model_row(self, row, _pspec, key):
        if self._updating:
            return
        items = self._row_items.get(key, [])
        i = row.get_selected()
        if 0 <= i < len(items) and items[i] != self.cfg[key]:
            if key == "llm_model":
                self._set_engine(key, items[i])
            else:
                self._set(key, items[i])
            self.voice_failed = False
            self._refresh_banner()

    def _on_theme(self, row, _pspec):
        self._set("theme", THEMES[row.get_selected()])
        apply_color_scheme(self.cfg["theme"])

    # ── schede grafiche ───────────────────────────────────────────────────
    def _on_gpu(self, row, _pspec):
        self._set_engine("gpu", row.get_active())
        if self.device_row is not None:
            self.device_row.set_sensitive(row.get_active())

    def _load_devices(self):
        """Il motore interroga Vulkan: un thread, e la riga si riempie dopo."""
        if self._devices_loading:
            return
        self._devices_loading = True

        def work():
            devices = engine.list_devices()
            GLib.idle_add(self._devices_loaded, devices)
        threading.Thread(target=work, daemon=True).start()

    def _devices_loaded(self, devices):
        self._devices_loading = False
        self.devices = devices
        self._fill_device_row()
        return False

    device_row = None
    _row_devices = ()

    def _fill_device_row(self):
        row = self.device_row
        if row is None:
            return
        labels = [desc for _n, desc, _mib in self.devices]
        items = [_("gpu_device_auto")] + [f"{desc} ({max(1, round(mib / 1024))} GB)"
                                          for _n, desc, mib in self.devices]
        saved = self.cfg["gpu_device"]
        if saved and saved not in labels:
            labels.append(saved)
            items.append(saved)
        self._row_devices = labels
        self._updating = True
        row.set_model(Gtk.StringList.new(items))
        row.set_selected(labels.index(saved) + 1 if saved in labels else 0)
        self._updating = False

    def _on_device(self, row, _pspec):
        if self._updating:
            return
        i = row.get_selected()
        self._set_engine("gpu_device",
                         self._row_devices[i - 1] if 0 < i <= len(self._row_devices) else "")

    # ── altre finestre ────────────────────────────────────────────────────
    def show_log(self):
        view = Gtk.TextView(editable=False, cursor_visible=False, monospace=True,
                            wrap_mode=Gtk.WrapMode.WORD_CHAR, top_margin=12,
                            bottom_margin=12, left_margin=12, right_margin=12)
        view.get_buffer().set_text("\n".join(self.log_lines) or _("log_empty"))
        toolbar = Adw.ToolbarView(content=Gtk.ScrolledWindow(child=view, vexpand=True))
        toolbar.add_top_bar(Adw.HeaderBar())
        Adw.Dialog(title=_("engine_log"), content_width=720, content_height=480,
                   child=toolbar).present(self)

    def show_guide(self):
        code = "it" if LANG.startswith("it") else "en"
        for d in DOC_DIRS:
            for name in (f"MANUAL_{code}.md", f"MANUAL_{code}.md.gz"):
                path = os.path.join(d, name)
                if os.path.isfile(path):
                    Gtk.FileLauncher.new(Gio.File.new_for_path(path)).launch(self, None, None)
                    return
        self._show_error(_("guide_missing"))

    def show_shortcuts(self):
        group = Adw.PreferencesGroup()
        for title, accel in ((_("listen_shortcut"), "<Control>l"), (_("hush"), "Escape"),
                             (_("new_conversation"), "<Control>n"),
                             (_("save_conversation"), "<Control>s"),
                             (_("preferences"), "<Control>comma"),
                             (_("zoom_in"), "<Control>plus"), (_("zoom_out"), "<Control>minus"),
                             (_("zoom_reset"), "<Control>0"),
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
        show_about_dialog(self, _, APP_ID, APP_NAME, APP_VERSION, _("app_description"),
                          theme_has_icon(), COMPONENTS)

    def _show_error(self, heading, detail=""):
        dialog = Adw.AlertDialog(heading=heading, body=detail)
        dialog.add_response("close", _("close"))
        dialog.present(self)

    def _on_close(self, *_a):
        self.listening = False
        self._close_mic()
        self.hush(resume=False)
        self.transcriber.cancel()
        self.transcriber.wait(3)
        self.engine.stop(wait=True)
        clean_work_dirs()
        w, h = self.get_default_size()
        self.cfg.update(width=w, height=h, maximized=self.is_maximized())
        save_settings(self.cfg)
        return False


class CatApp(Adw.Application):
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
                               ("win.listen", ["<Control>l"]), ("win.hush", ["Escape"]),
                               ("win.new", ["<Control>n"]), ("win.save", ["<Control>s"]),
                               ("win.zoom-in", ["<Control>plus", "<Control>equal", "<Control>KP_Add"]),
                               ("win.zoom-out", ["<Control>minus", "<Control>KP_Subtract"]),
                               ("win.zoom-reset", ["<Control>0", "<Control>KP_0"]),
                               ("win.preferences", ["<Control>comma"]),
                               ("win.shortcuts", ["<Control>question"])):
            self.set_accels_for_action(action, accels)

    def update_theme(self):
        dark = Adw.StyleManager.get_default().get_dark()
        for window in self.get_windows():
            window.remove_css_class("rusca-light" if dark else "rusca-dark")
            window.add_css_class("rusca-dark" if dark else "rusca-light")

    def do_activate(self):
        (self.props.active_window or CatWindow(self)).present()


def main():
    GLib.set_prgname(APP_ID)
    GLib.set_application_name(APP_NAME)
    return CatApp().run(sys.argv)


if __name__ == "__main__":
    sys.exit(main())
