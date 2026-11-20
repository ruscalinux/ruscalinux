#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
RuscaNarrator 1.99.3 — dal testo alla voce, per RuscaLinux.

Legge ad alta voce un documento Markdown, o un file di sottotitoli SRT
rispettandone i tempi, con un modello di sintesi vocale in GGUF che gira su
questo computer, tramite llama-tts di ruscallama-engine (llama.cpp, software
esterno con licenza MIT). L'audio si monta e si converte con FFmpeg e si
salva in WAV, FLAC, Opus o MP3. Tutto resta sul computer.

Copyright (C) 2026 Nunzio Curcuruto — https://www.ruscalinux.org
Licenza: GNU GPL 3.0 o successiva.

Requisiti: Python 3.10+, PyGObject, GTK 4.18+, libadwaita 1.7+,
ruscallama-engine (con llama-tts), ffmpeg, python3-markdown-it.
"""
import json
import os
import random
import re
import sys
import threading
import time

import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gdk, Gio, GLib, Gtk, Pango  # noqa: E402

BASE_DIR = os.path.dirname(os.path.realpath(__file__))
sys.path.insert(0, BASE_DIR)
import rusca_tts as tts  # noqa: E402

APP_ID = "org.ruscalinux.RuscaNarrator"
APP_NAME = "RuscaNarrator"
APP_VERSION = "1.99.3"
STYLE_SRC = os.path.join(BASE_DIR, "style.css")
ICON_SRC = os.path.join(BASE_DIR, "ruscanarrator.svg")
LANG_DIR = os.path.join(BASE_DIR, "lang")
DOC_DIRS = (os.path.join(BASE_DIR, "docs"), "/usr/share/doc/ruscanarrator")
CONFIG_DIR = os.path.join(GLib.get_user_config_dir(), "ruscanarrator")
CONFIG_FILE = os.path.join(CONFIG_DIR, "settings.json")
COMPONENTS = (
    ("llama.cpp (llama-tts)", "MIT — The ggml authors", "https://github.com/ggml-org/llama.cpp"),
    # Regola dell'evidenziato ==testo==, nel file a sé markdown_it_mark.py
    ("markdown-it-mark", "MIT — Vitaly Puzrin, Alex Kocharin; ExecutableBookProject",
     "https://github.com/markdown-it/markdown-it-mark"),
)
CODES = [c for c, _n in tts.LANGUAGES]
SOURCE_PATTERNS = ("md", "markdown", "txt", "srt")
FORMATS = ("wav", "flac", "opus", "mp3")
DEFAULTS = {
    "model": "", "speaker_file": "", "voice_name": "", "language": "",
    "read_code": False, "read_notes": False, "seed": 42, "normalize": True,
    "max_speed": 1.3, "gpu": True, "gpu_device": "", "threads": tts.physical_cores(),
    "font_size": 0, "width": 860, "height": 660, "maximized": False, "theme": "system",
}
THEMES = ("system", "light", "dark")         # ordine delle voci nel menu

def apply_color_scheme(theme):
    """Tema chiaro/scuro: segue GNOME (predefinito) o è scelto dall'utente."""
    Adw.StyleManager.get_default().set_color_scheme({
        "light": Adw.ColorScheme.FORCE_LIGHT,
        "dark": Adw.ColorScheme.FORCE_DARK,
    }.get(theme, Adw.ColorScheme.DEFAULT))



# ── Traduzioni dell'interfaccia (lang/xx.json, ripiego en.json) ──────────────
# Ripieghi fra lingue vicine (specifiche, sezione 9.2): Hong Kong e Macao
# usano il cinese tradizionale, Singapore il semplificato; il portoghese
# senza variante legge il brasiliano, lo slovacco il ceco.
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




# Durante lo sviluppo della 1.99.3 il programma si chiamava RuscaSpeaking:
# alla prima apertura modelli, voci e impostazioni passano al nome nuovo.
OLD_NAME = "ruscaspeaking"


def migrate_old_name():
    """Sposta ~/.local/share/ruscaspeaking e ~/.config/ruscaspeaking.

    I modelli possono pesare gigabyte: la cartella si rinomina, non si copia.
    Nelle impostazioni i percorsi che puntavano alla cartella vecchia (modello,
    voce di riferimento) si correggono. Se la cartella nuova esiste gia', non
    si tocca niente."""
    old_data = os.path.join(GLib.get_user_data_dir(), OLD_NAME)
    new_data = os.path.dirname(tts.USER_MODEL_DIR)
    if os.path.isdir(old_data) and not os.path.lexists(new_data):
        try:
            os.rename(old_data, new_data)
        except OSError:
            pass
    old_cfg = os.path.join(GLib.get_user_config_dir(), OLD_NAME, "settings.json")
    if os.path.exists(CONFIG_FILE) or not os.path.isfile(old_cfg):
        return
    try:
        with open(old_cfg, encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, dict):
            return
        prefix = old_data + os.sep
        for key in ("model", "speaker_file"):
            value = data.get(key)
            if isinstance(value, str) and value.startswith(prefix):
                data[key] = os.path.join(new_data, value[len(prefix):])
        save_settings(data)
    except (OSError, ValueError):
        pass


def load_settings():
    cfg = dict(DEFAULTS)
    migrate_old_name()
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
        # Primo avvio: la lingua dell'interfaccia, se il modello la conosce.
        base = LANG.split("_")[0]
        cfg["language"] = base if base in CODES else "en"
    cfg["threads"] = max(1, min(cfg["threads"], os.cpu_count() or 1))
    cfg["max_speed"] = min(2.0, max(1.0, cfg["max_speed"]))
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


def pick_voice(saved, voices):
    """Il modello salvato se c'è ancora, altrimenti il file più grande (a
    parità di modello, il più preciso: qualità prima della velocità)."""
    for v in voices:
        if v.model == saved:
            return v
    if not voices:
        return None

    def size(v):
        try:
            return os.path.getsize(v.model)
        except OSError:
            return 0
    return max(voices, key=size)


# Lingue che separano i decimali con la virgola.
DECIMAL_COMMA = ("it", "de", "fr", "es", "pt", "nl", "sv", "fi", "pl", "cs", "ro", "hu", "el",
                 "ru", "uk", "tr", "id", "vi")


def decimal(value, digits=1):
    text = f"{value:.{digits}f}"
    return text.replace(".", ",") if LANG.split("_")[0] in DECIMAL_COMMA else text


def duration_text(ms):
    s = max(0, int(round(ms / 1000)))
    return f"{s // 3600}:{s // 60 % 60:02d}:{s % 60:02d}" if s >= 3600 else f"{s // 60}:{s % 60:02d}"


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


# ── Dimensione del testo (testo da leggere) ─────────────────────
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
        # libadwaita dà al codice (.monospace) una dimensione propria: la si
        # allinea, altrimenti il codice resterebbe piccolo.
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
class NarratorWindow(FontSizeMixin, Adw.ApplicationWindow):
    def __init__(self, app):
        super().__init__(application=app, title=APP_NAME)
        self.cfg = load_settings()
        self.set_default_size(self.cfg["width"], self.cfg["height"])
        self.set_size_request(360, 294)
        if self.cfg["maximized"]:
            self.maximize()
        self.speaker = None
        self.run_id = 0                 # le callback di una lettura vecchia si scartano
        self.running = False
        self.source = None              # documento o sottotitoli aperti
        self.source_text = ""
        self.is_srt = False
        self.pieces = []
        self.spans = []
        self.result = None              # WAV generato, nei file di lavoro
        self.unsaved = False
        self.log_lines = []
        self.voices = []
        self.voice = None
        self.devices = []
        self._devices_loading = False
        self.model_row = None
        self.device_row = None
        self.speaker_row = None
        self._row_speakers = []
        self.voice_dialog = None        # «Crea una voce», se aperto
        self.voice_busy = False         # una voce di prova in creazione
        self._row_voices = []
        self._row_devices = []
        self._updating = False
        self._models_timer = 0
        self._pulse_timer = 0
        self._started = 0.0
        self._force_close = False
        self._monitors = []
        self.media = None
        self._build_actions()
        self._init_font_size()
        self._build_ui()
        tts.clean_work_dir()
        self._watch_models()
        self._refresh_models()
        self.connect("close-request", self._on_close)

    # ── azioni ────────────────────────────────────────────────────────────
    def _build_actions(self):
        for name, cb in (("open", self.open_file), ("generate", self.generate),
                         ("stop", self.stop), ("models-folder", self.open_models_folder),
                         ("create-voice", self.show_voice_creator),
                         ("voices-folder", self.open_voices_folder),
                         ("preferences", self.show_preferences), ("show-log", self.show_log),
                         ("guide", self.show_guide), ("shortcuts", self.show_shortcuts),
                         ("about", self.show_about)):
            action = Gio.SimpleAction.new(name, None)
            action.connect("activate", lambda _a, _p, f=cb: f())
            self.add_action(action)
        for fmt in FORMATS:
            action = Gio.SimpleAction.new(f"save-{fmt}", None)
            action.connect("activate", lambda _a, _p, f=fmt: self.save(f))
            self.add_action(action)

    # ── interfaccia ───────────────────────────────────────────────────────
    def _build_ui(self):
        header = Adw.HeaderBar()
        self.title = Adw.WindowTitle(title=APP_NAME)
        header.set_title_widget(self.title)
        open_btn = Gtk.Button(icon_name="document-open-symbolic", action_name="win.open",
                              tooltip_text=_("open"))
        open_btn.update_property([Gtk.AccessibleProperty.LABEL], [_("open")])
        header.pack_start(open_btn)
        save_menu = Gio.Menu()
        for fmt in FORMATS:
            save_menu.append(_(f"save_{fmt}"), f"win.save-{fmt}")
        self.save_btn = Gtk.MenuButton(icon_name="document-save-symbolic", menu_model=save_menu,
                                       tooltip_text=_("save"), sensitive=False)
        self.save_btn.update_property([Gtk.AccessibleProperty.LABEL], [_("save")])
        header.pack_start(self.save_btn)
        menu = Gio.Menu()
        tool = Gio.Menu()
        tool.append(_("create_voice"), "win.create-voice")
        tool.append(_("open_models_folder"), "win.models-folder")
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

        # Barra della lettura: lingua e pulsante. Compare quando c'è un file.
        self.lang_drop = Gtk.DropDown.new_from_strings([n for _c, n in tts.LANGUAGES])
        self.lang_drop.set_tooltip_text(_("speech_language"))
        self.lang_drop.update_property([Gtk.AccessibleProperty.LABEL], [_("speech_language")])
        self.lang_drop.set_selected(CODES.index(self.cfg["language"]))
        self.lang_drop.connect("notify::selected", self._on_language)
        lang_label = Gtk.Label(label=_("speech_language"), xalign=0, wrap=True)
        self.generate_btn = Gtk.Button(label=_("generate"), action_name="win.generate")
        self.generate_btn.add_css_class("suggested-action")
        self.generate_btn.add_css_class("pill")
        langs = Gtk.Box(spacing=12, hexpand=True)
        langs.append(lang_label)
        langs.append(self.lang_drop)
        self.bar = Gtk.Box(spacing=12, margin_start=12, margin_end=12, margin_top=6,
                           margin_bottom=6, visible=False)
        self.bar.append(langs)
        self.bar.append(self.generate_btn)

        self.banner = Adw.Banner()
        self.banner.connect("button-clicked", lambda _b: self.open_models_folder())

        empty = Adw.StatusPage(
            icon_name=APP_ID if theme_has_icon() else "audio-speakers-symbolic",
            title=_("empty_title"), description=_("empty_desc"))
        choose = Gtk.Button(label=_("choose_file"), action_name="win.open",
                            halign=Gtk.Align.CENTER)
        choose.add_css_class("suggested-action")
        choose.add_css_class("pill")
        empty.set_child(choose)

        nothing = Adw.StatusPage(icon_name="dialog-information-symbolic",
                                 title=_("nothing_title"), description=_("nothing_desc"))

        # Il testo da leggere, come lo leggerà il modello. Il pezzo in
        # lettura è in grassetto e sottolineato: si vede senza colori.
        self.buf = Gtk.TextBuffer()
        self.reading_tag = self.buf.create_tag("reading", weight=Pango.Weight.BOLD,
                                               underline=Pango.Underline.SINGLE)
        self.view = Gtk.TextView(buffer=self.buf, editable=False, cursor_visible=False,
                                 wrap_mode=Gtk.WrapMode.WORD_CHAR, top_margin=12,
                                 bottom_margin=12, left_margin=12, right_margin=12)
        self.view.add_css_class("rusca-content")
        self.view.update_property([Gtk.AccessibleProperty.LABEL], [_("text_to_read")])
        self.scroll = Gtk.ScrolledWindow(child=self.view, vexpand=True, hexpand=True,
                                         hscrollbar_policy=Gtk.PolicyType.NEVER,
                                         margin_start=12, margin_end=12, margin_top=6,
                                         margin_bottom=12)
        self.scroll.add_css_class("card")

        self.stack = Gtk.Stack()
        self.stack.add_named(empty, "empty")
        self.stack.add_named(nothing, "nothing")
        self.stack.add_named(self.scroll, "text")
        drop = Gtk.DropTarget.new(Gio.File, Gdk.DragAction.COPY)
        drop.connect("drop", lambda _t, f, _x, _y: self.open_path(f.get_path()) or True)
        self.stack.add_controller(drop)
        self.toasts = Adw.ToastOverlay(child=self.stack)

        # Avanzamento
        self.progress = Gtk.ProgressBar(show_text=True, hexpand=True, valign=Gtk.Align.CENTER)
        stop = Gtk.Button(label=_("stop"), action_name="win.stop")
        stop.add_css_class("destructive-action")
        self.progress_bar = Gtk.ActionBar(revealed=False)
        self.progress_bar.pack_start(self.progress)
        self.progress_bar.pack_end(stop)

        # Ascolto del risultato
        self.controls = Gtk.MediaControls(hexpand=True)
        self.player_label = Gtk.Label(xalign=0)
        self.player_label.add_css_class("dim-label")
        self.player_label.add_css_class("numeric")
        self.player_bar = Gtk.ActionBar(revealed=False)
        self.player_bar.pack_start(self.controls)
        self.player_bar.pack_end(self.player_label)

        view = Adw.ToolbarView(content=self.toasts)
        view.add_top_bar(header)
        view.add_top_bar(self.bar)
        view.add_top_bar(self.banner)
        view.add_bottom_bar(self.player_bar)
        view.add_bottom_bar(self.progress_bar)
        self.set_content(view)
        narrow = Adw.Breakpoint.new(Adw.BreakpointCondition.parse("max-width: 500sp"))
        narrow.add_setter(self.bar, "orientation", Gtk.Orientation.VERTICAL)
        self.add_breakpoint(narrow)

    def _ready(self):
        return bool(self.voice) and bool(tts.find_binary()) and bool(tts.find_ffmpeg())

    def _refresh_actions(self):
        done = bool(self.result) and not self.running
        self.lookup_action("generate").set_enabled(
            bool(self.pieces) and self._ready() and not self.running and not self.voice_busy)
        self.lookup_action("create-voice").set_enabled(self._ready() and not self.running)
        self.lookup_action("stop").set_enabled(self.running)
        for fmt in FORMATS:
            self.lookup_action(f"save-{fmt}").set_enabled(done)
        self.save_btn.set_sensitive(done)
        self.lang_drop.set_sensitive(not self.running)

    def _refresh_banner(self):
        b = self.banner
        b.set_button_label(None)
        if not tts.find_binary():
            b.set_title(_("banner_no_engine"))
            b.set_revealed(True)
        elif not tts.find_ffmpeg():
            b.set_title(_("err_no_ffmpeg"))
            b.set_revealed(True)
        elif not self.voice:
            b.set_title(_("banner_no_model"))
            b.set_button_label(_("open_models_folder"))
            b.set_revealed(True)
        else:
            b.set_revealed(False)
        self._refresh_actions()

    def _on_language(self, drop, _pspec):
        i = drop.get_selected()
        if 0 <= i < len(CODES):
            self._set("language", CODES[i])

    def _set(self, key, value):
        self.cfg[key] = value
        save_settings(self.cfg)

    def _toast(self, text, timeout=5):
        self.toasts.add_toast(Adw.Toast(title=GLib.markup_escape_text(text), timeout=timeout))

    # ── modelli ───────────────────────────────────────────────────────────
    def _watch_models(self):
        """Tiene d'occhio le cartelle dei modelli: un modello copiato
        compare senza riavviare il programma."""
        try:
            tts.ensure_user_model_dir()
        except OSError:
            pass
        for d in tts.MODEL_DIRS:
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
        self._refresh_models()
        return False

    def _refresh_models(self):
        self.voices = tts.find_voices()
        self.voice = pick_voice(self.cfg["model"], self.voices)
        if self.voice and self.voice.model != self.cfg["model"]:
            self._set("model", self.voice.model)
        self._fill_model_row()
        self._refresh_banner()

    def _fill_model_row(self):
        row = self.model_row
        if row is None:
            return
        self._row_voices = list(self.voices)
        self._updating = True
        row.set_model(Gtk.StringList.new([os.path.basename(v.model) for v in self.voices]
                                         or [_("no_model")]))
        row.set_sensitive(bool(self.voices))
        if self.voice in self.voices:
            row.set_selected(self.voices.index(self.voice))
        self._updating = False
        self._update_model_subtitle()

    def _update_model_subtitle(self):
        if self.model_row is not None:
            self.model_row.set_subtitle(
                _("model_with", mmproj=os.path.basename(self.voice.mmproj)) if self.voice
                else _("model_hint"))

    def _on_model(self, row, _pspec):
        if self._updating:
            return
        i = row.get_selected()
        if 0 <= i < len(self._row_voices):
            self.voice = self._row_voices[i]
            self._set("model", self.voice.model)
            self._update_model_subtitle()
            self._refresh_banner()

    def open_models_folder(self):
        try:
            folder = tts.ensure_user_model_dir()
        except OSError as e:
            self._show_error(_("open_error"), str(e))
            return
        Gtk.FileLauncher.new(Gio.File.new_for_path(folder)).launch(self, None, None)

    # ── file ──────────────────────────────────────────────────────────────
    def _guard(self, then):
        """Esegue `then` subito, o dopo la conferma se andrebbe persa una
        lettura in corso o un audio non salvato."""
        if not self.running and not self.unsaved:
            then()
            return
        dialog = Adw.AlertDialog(heading=_("discard_title"), body=_("discard_body"))
        dialog.add_response("cancel", _("cancel"))
        dialog.add_response("discard", _("discard"))
        dialog.set_response_appearance("discard", Adw.ResponseAppearance.DESTRUCTIVE)
        dialog.set_default_response("cancel")
        dialog.set_close_response("cancel")

        def answered(_d, response):
            if response == "discard":
                self._discard()
                then()
        dialog.connect("response", answered)
        dialog.present(self)

    def _discard(self):
        """Butta via la lettura in corso o l'audio non salvato."""
        self.run_id += 1
        if self.speaker is not None:
            self.speaker.cancel()
            self.speaker.discard()
        self._set_running(False)
        self._set_result(None)
        self._highlight(None)

    def _set_result(self, path):
        if self.media is not None:
            self.media.set_playing(False)
            self.media = None
        self.controls.set_media_stream(None)
        self.result = path
        self.unsaved = bool(path)
        if path:
            self.media = Gtk.MediaFile.new_for_filename(path)
            self.controls.set_media_stream(self.media)
            try:
                rate, _ch, _w, n = tts.wav_info(path)
                self.player_label.set_label(duration_text(n * 1000 / rate))
            except (OSError, EOFError, ValueError):
                self.player_label.set_label("")
        self.player_bar.set_revealed(bool(path))
        self._refresh_actions()

    def open_file(self):
        self._guard(self._choose_source)

    def _choose_source(self):
        sources = Gtk.FileFilter()
        sources.set_name(_("source_files"))
        for ext in SOURCE_PATTERNS:
            sources.add_suffix(ext)
        sources.add_mime_type("text/markdown")
        sources.add_mime_type("application/x-subrip")
        everything = Gtk.FileFilter()
        everything.set_name(_("all_files"))
        everything.add_pattern("*")
        store = Gio.ListStore.new(Gtk.FileFilter)
        store.append(sources)
        store.append(everything)
        dialog = Gtk.FileDialog(title=_("choose_file").rstrip("…"), filters=store)

        def done(d, result):
            try:
                self.load_source(d.open_finish(result).get_path())
            except GLib.Error:
                pass
        dialog.open(self, None, done)

    def open_path(self, path):
        """File trascinato sulla finestra o passato dalla riga di comando."""
        if path:
            self._guard(lambda: self.load_source(path))

    def load_source(self, path):
        try:
            with open(path, encoding="utf-8", errors="replace") as f:
                text = f.read()
        except (OSError, TypeError) as e:
            self._show_error(_("open_error"), f"{path or ''}\n{e}")
            return
        self.source = path
        self.source_text = text
        self.is_srt = path.lower().endswith(".srt")
        name = os.path.basename(path)
        self.title.set_subtitle(name)
        self.bar.set_visible(True)
        self._set_result(None)
        self._rebuild_pieces()

    def _rebuild_pieces(self):
        """Pezzi da leggere e anteprima: da rifare quando cambiano le
        opzioni di lettura (codice, note)."""
        if self.source is None or self.running:
            return
        if self.is_srt:
            self.pieces = tts.parse_srt(self.source_text)
        else:
            self.pieces = tts.markdown_pieces(self.source_text, self.cfg["read_code"],
                                              self.cfg["read_notes"])
        text, self.spans = tts.preview_text(self.pieces, srt=self.is_srt)
        self.buf.set_text(text)
        self.stack.set_visible_child_name("text" if self.pieces else "nothing")
        self._refresh_actions()

    def _highlight(self, index):
        self.buf.remove_tag(self.reading_tag, self.buf.get_start_iter(), self.buf.get_end_iter())
        if index is None or not 0 <= index < len(self.spans):
            return
        a, b = self.spans[index]
        start, end = self.buf.get_iter_at_offset(a), self.buf.get_iter_at_offset(b)
        self.buf.apply_tag(self.reading_tag, start, end)
        self.view.scroll_to_iter(start, 0.1, False, 0, 0)

    # ── lettura ───────────────────────────────────────────────────────────
    def generate(self):
        if self.pieces and not self.running:
            self._guard(self._start)

    def _start(self):
        self.run_id += 1
        rid = self.run_id

        def mine(callback):
            return lambda *args: rid == self.run_id and callback(*args)
        self.speaker = tts.Speaker(on_progress=mine(self._on_progress),
                                   on_stage=mine(self._on_stage), on_log=mine(self._on_log),
                                   on_done=mine(self._on_done))
        self.log_lines.clear()
        self._set_result(None)
        c = self.cfg
        try:
            self.speaker.start(self.pieces, self.voice, srt=self.is_srt, language=c["language"],
                               speaker_file=c["speaker_file"], voice_name=c["voice_name"].strip(),
                               gpu=c["gpu"], gpu_device=c["gpu_device"], threads=c["threads"],
                               seed=c["seed"], max_speed=c["max_speed"],
                               normalize=c["normalize"])
        except tts.TTSError as e:
            self._show_error(_(e.key), e.detail)
            return
        self._started = time.monotonic()
        self._set_running(True)
        self._on_progress(0, len(self.pieces))

    def stop(self):
        if self.running and self.speaker is not None:
            self.speaker.cancel()

    def _set_running(self, running):
        self.running = running
        self.progress_bar.set_revealed(running)
        if not running:
            self._stop_pulse()
        self._refresh_actions()

    def _stop_pulse(self):
        if self._pulse_timer:
            GLib.source_remove(self._pulse_timer)
            self._pulse_timer = 0

    def _pulse(self):
        self.progress.pulse()
        return True

    def _on_progress(self, index, total):
        if not self.running:
            return
        self._stop_pulse()
        self.progress.set_fraction(index / max(1, total))
        text = _("reading_piece", n=index + 1, total=total)
        if index > 0:
            # Stima: il tempo medio dei pezzi già letti.
            left = (time.monotonic() - self._started) / index * (total - index)
            text = _("reading_piece_left", n=index + 1, total=total,
                     left=duration_text(left * 1000))
        self.progress.set_text(text)
        self._highlight(index)

    def _on_stage(self, stage):
        if not self.running:
            return
        self._highlight(None)
        self.progress.set_text(_("assembling" if stage == "assemble" else "normalizing"))
        if not self._pulse_timer:
            self._pulse_timer = GLib.timeout_add(150, self._pulse)

    def _on_log(self, line):
        self.log_lines.append(line)
        del self.log_lines[:-3000]

    def _on_done(self, error, path, stats):
        self._set_running(False)
        self._highlight(None)
        if error is None and path:
            self._set_result(path)
            self._toast(_("completed"), 6)
            if self.is_srt and (stats["faster"] or stats["late"]):
                self._toast(_("srt_report", faster=stats["faster"], late=stats["late"],
                              seconds=decimal(stats["max_late_ms"] / 1000)), 10)
        elif error == "cancelled":
            self._toast(_("stopped"))
        elif error is not None:
            self._show_error(_(error.key), error.detail)

    # ── salvataggio ───────────────────────────────────────────────────────
    def save(self, fmt):
        if not self.result or self.running:
            return
        base = os.path.splitext(os.path.basename(self.source or "audio"))[0]
        filt = Gtk.FileFilter()
        filt.set_name(_(f"files_{fmt}"))
        filt.add_suffix(fmt)
        store = Gio.ListStore.new(Gtk.FileFilter)
        store.append(filt)
        dialog = Gtk.FileDialog(title=_(f"save_{fmt}").rstrip("…"),
                                initial_name=f"{base}.{fmt}", filters=store)
        folder = os.path.dirname(self.source or "")
        if os.path.isdir(folder):
            dialog.set_initial_folder(Gio.File.new_for_path(folder))
        src = self.result

        def done(d, result):
            try:
                dest = d.save_finish(result).get_path()
            except GLib.Error:
                return
            self._toast(_("saving"), 2)

            def work():
                try:
                    tts.export(src, dest, fmt)
                    error = None
                except (tts.TTSError, OSError) as e:
                    error = e
                GLib.idle_add(self._saved, dest, error)
            threading.Thread(target=work, daemon=True).start()
        dialog.save(self, None, done)

    def _saved(self, dest, error):
        if error is None:
            self.unsaved = False
            self._toast(_("saved", name=os.path.basename(dest)))
        else:
            self._show_error(_("save_error"), getattr(error, "detail", "") or str(error))
        return False

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

        voice = Adw.PreferencesGroup(title=_("group_voice"), description=_("model_hint"))
        self.model_row = Adw.ComboRow(title=_("model"))
        self._fill_model_row()
        self.model_row.connect("notify::selected", self._on_model)
        voice.add(self.model_row)
        folder = Adw.ActionRow(title=_("open_models_folder"), subtitle=tts.USER_MODEL_DIR,
                               activatable=True)
        folder.add_suffix(Gtk.Image(icon_name="folder-open-symbolic"))
        folder.connect("activated", lambda _r: self.open_models_folder())
        voice.add(folder)
        # Voce di riferimento: nessuna, una delle voci salvate, o un file
        # scelto (il pulsante a destra).
        self.speaker_row = Adw.ComboRow(title=_("speaker_file"))
        choose = Gtk.Button(icon_name="document-open-symbolic", valign=Gtk.Align.CENTER,
                            tooltip_text=_("speaker_choose"))
        choose.add_css_class("flat")
        choose.update_property([Gtk.AccessibleProperty.LABEL], [_("speaker_choose")])
        choose.connect("clicked", lambda _b: self._choose_speaker())
        self.speaker_row.add_suffix(choose)
        self._fill_speaker_row()
        self.speaker_row.connect("notify::selected", self._on_speaker)
        voice.add(self.speaker_row)
        create = Adw.ActionRow(title=_("create_voice").rstrip("…"),
                               subtitle=_("create_voice_sub"), activatable=True)
        create.add_suffix(Gtk.Image(icon_name="go-next-symbolic"))
        create.connect("activated", lambda _r: self.show_voice_creator())
        create.set_sensitive(self._ready())
        voice.add(create)
        voices = Adw.ActionRow(title=_("open_voices_folder"), subtitle=tts.VOICE_DIR,
                               activatable=True)
        voices.add_suffix(Gtk.Image(icon_name="folder-open-symbolic"))
        voices.connect("activated", lambda _r: self.open_voices_folder())
        voice.add(voices)
        name = Adw.EntryRow(title=_("voice_name"), text=self.cfg["voice_name"])
        name.connect("changed", lambda r: self._set("voice_name", r.get_text()))
        voice.add(name)
        page.add(voice)

        reading = Adw.PreferencesGroup(title=_("group_reading"))
        for key in ("read_code", "read_notes"):
            row = Adw.SwitchRow(title=_(key), active=self.cfg[key])
            row.connect("notify::active", lambda r, _p, k=key: (
                self._set(k, r.get_active()), self._rebuild_pieces()))
            reading.add(row)
        speed = Adw.SpinRow.new_with_range(1.0, 2.0, 0.05)
        speed.set_digits(2)
        speed.set_title(_("max_speed"))
        speed.set_subtitle(_("max_speed_sub"))
        speed.set_value(self.cfg["max_speed"])
        speed.connect("notify::value", lambda r, _p: self._set("max_speed", round(r.get_value(), 2)))
        reading.add(speed)
        norm = Adw.SwitchRow(title=_("normalize"), subtitle=_("normalize_sub"),
                             active=self.cfg["normalize"])
        norm.connect("notify::active", lambda r, _p: self._set("normalize", r.get_active()))
        reading.add(norm)
        seed = Adw.SpinRow.new_with_range(0, 2 ** 31 - 1, 1)
        seed.set_title(_("seed"))
        seed.set_subtitle(_("seed_sub"))
        seed.set_value(self.cfg["seed"])
        seed.connect("notify::value", lambda r, _p: self._set("seed", int(r.get_value())))
        reading.add(seed)
        page.add(reading)

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
        threads.set_subtitle(_("threads_sub", n=tts.physical_cores()))
        threads.set_value(min(self.cfg["threads"], os.cpu_count() or 1))
        threads.connect("notify::value", lambda r, _p: self._set("threads", int(r.get_value())))
        eng.add(threads)
        page.add(eng)

        dialog = Adw.PreferencesDialog(title=_("preferences").rstrip("…"))
        dialog.add(page)
        dialog.connect("closed", self._on_preferences_closed)
        dialog.present(self)

    def _on_preferences_closed(self, _dialog):
        self.model_row = None
        self.device_row = None
        self.speaker_row = None
        self._row_speakers = []

    def _fill_speaker_row(self):
        row = self.speaker_row
        if row is None:
            return
        items, paths = [_("speaker_none")], [""]
        for name, path in tts.find_voice_files():
            items.append(name)
            paths.append(path)
        saved = self.cfg["speaker_file"]
        if saved and saved not in paths:
            items.append(os.path.basename(saved))
            paths.append(saved)
        self._row_speakers = paths
        self._updating = True
        row.set_model(Gtk.StringList.new(items))
        row.set_selected(paths.index(saved) if saved in paths else 0)
        self._updating = False

    def _on_speaker(self, row, _pspec):
        if self._updating:
            return
        i = row.get_selected()
        if 0 <= i < len(self._row_speakers):
            self._set("speaker_file", self._row_speakers[i])

    def _choose_speaker(self):
        filt = Gtk.FileFilter()
        filt.set_name(_("audio_files"))
        filt.add_mime_type("audio/*")
        for ext in ("wav", "mp3", "flac", "ogg", "opus", "m4a"):
            filt.add_suffix(ext)
        store = Gio.ListStore.new(Gtk.FileFilter)
        store.append(filt)
        dialog = Gtk.FileDialog(title=_("speaker_choose").rstrip("…"), filters=store)

        def done(d, result):
            try:
                self._set_speaker(d.open_finish(result).get_path())
            except GLib.Error:
                pass
        dialog.open(self, None, done)

    def _set_speaker(self, path):
        self._set("speaker_file", path or "")
        self._fill_speaker_row()

    def open_voices_folder(self):
        try:
            os.makedirs(tts.VOICE_DIR, exist_ok=True)
        except OSError as e:
            self._show_error(_("open_error"), str(e))
            return
        Gtk.FileLauncher.new(Gio.File.new_for_path(tts.VOICE_DIR)).launch(self, None, None)

    # ── «Crea una voce» ───────────────────────────────────────────────────
    def show_voice_creator(self):
        """Prova una voce del modello con un seme a caso; se piace, la si
        tiene: diventa la voce di riferimento, uguale per tutte le frasi."""
        if self.running or not self._ready() or self.voice_dialog is not None:
            return
        state = {"speaker": None, "result": None, "media": None, "id": 0}

        desc = Gtk.Label(label=_("create_voice_desc"), wrap=True, xalign=0)
        self._voice_status = Gtk.Label(wrap=True, xalign=0)
        self._voice_status.add_css_class("dim-label")
        spinner = Adw.Spinner(visible=False)
        status = Gtk.Box(spacing=12)
        status.append(spinner)
        status.append(self._voice_status)
        controls = Gtk.MediaControls(visible=False)
        name_row = Adw.EntryRow(title=_("voice_title"), text=self._next_voice_name())
        names = Gtk.ListBox(selection_mode=Gtk.SelectionMode.NONE)
        names.add_css_class("boxed-list")
        names.append(name_row)
        try_btn = Gtk.Button(label=_("try_voice"), halign=Gtk.Align.CENTER)
        try_btn.add_css_class("pill")
        try_btn.add_css_class("suggested-action")
        keep_btn = Gtk.Button(label=_("keep_voice"), halign=Gtk.Align.CENTER, sensitive=False)
        keep_btn.add_css_class("pill")
        buttons = Gtk.Box(spacing=12, halign=Gtk.Align.CENTER)
        buttons.append(try_btn)
        buttons.append(keep_btn)
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=18, margin_top=12,
                      margin_bottom=24, margin_start=24, margin_end=24)
        for w in (desc, status, controls, names, buttons):
            box.append(w)
        view = Adw.ToolbarView(content=Adw.Clamp(child=box, maximum_size=520))
        view.add_top_bar(Adw.HeaderBar())
        dialog = Adw.Dialog(title=_("create_voice").rstrip("…"), content_width=520, child=view)
        self.voice_dialog = dialog

        def set_busy(busy):
            self.voice_busy = busy
            spinner.set_visible(busy)
            try_btn.set_sensitive(not busy)
            keep_btn.set_sensitive(not busy and bool(state["result"]))
            self._refresh_actions()

        def drop_result():
            if state["media"] is not None:
                state["media"].set_playing(False)
                state["media"] = None
            controls.set_media_stream(None)
            controls.set_visible(False)
            if state["speaker"] is not None:
                state["speaker"].discard()
            state["result"] = None

        def try_voice(_b=None):
            if self.voice_busy or self.running or not self._ready():
                return
            drop_result()
            state["id"] += 1
            run = state["id"]
            seed = random.randrange(1, 2 ** 31 - 1)

            def done(error, path, _stats):
                if run != state["id"] or self.voice_dialog is not dialog:
                    if path:
                        speaker.discard()
                    return
                set_busy(False)
                if error is None and path:
                    state["result"] = path
                    state["media"] = Gtk.MediaFile.new_for_filename(path)
                    controls.set_media_stream(state["media"])
                    controls.set_visible(True)
                    state["media"].play()
                    self._voice_status.set_label(_("voice_ready", seed=seed))
                    try_btn.set_label(_("another_voice"))
                    keep_btn.set_sensitive(True)
                elif error == "cancelled":
                    self._voice_status.set_label("")
                else:
                    self._voice_status.set_label("")
                    self._show_error(_(error.key), error.detail)
            speaker = tts.Speaker(on_log=self._on_log, on_done=done)
            state["speaker"] = speaker
            c = self.cfg
            try:
                speaker.start([tts.Piece(tts.sample_text(c["language"]))], self.voice,
                              language=c["language"], voice_name=c["voice_name"].strip(),
                              gpu=c["gpu"], gpu_device=c["gpu_device"], threads=c["threads"],
                              seed=seed, normalize=True)
            except tts.TTSError as e:
                self._show_error(_(e.key), e.detail)
                return
            self._voice_status.set_label(_("creating_voice"))
            set_busy(True)

        def keep(_b):
            if not state["result"]:
                return
            try:
                path = tts.save_voice(state["result"], name_row.get_text())
            except OSError as e:
                self._show_error(_("save_error"), str(e))
                return
            self._set_speaker(path)
            self._toast(_("voice_saved", name=os.path.splitext(os.path.basename(path))[0]))
            dialog.close()

        def closed(_d):
            state["id"] += 1
            if state["speaker"] is not None:
                state["speaker"].cancel()
            drop_result()
            self.voice_dialog = None
            self.voice_busy = False
            self._refresh_actions()

        try_btn.connect("clicked", try_voice)
        keep_btn.connect("clicked", keep)
        dialog.connect("closed", closed)
        dialog.present(self)
        try_voice()

    def _next_voice_name(self):
        taken = {name for name, _p in tts.find_voice_files()}
        n = 1
        while _("voice_default_name", n=n) in taken:
            n += 1
        return _("voice_default_name", n=n)

    def _on_theme(self, row, _pspec):
        self._set("theme", THEMES[row.get_selected()])
        apply_color_scheme(self.cfg["theme"])

    # ── schede grafiche ───────────────────────────────────────────────────
    def _on_gpu(self, row, _pspec):
        self._set("gpu", row.get_active())
        if self.device_row is not None:
            self.device_row.set_sensitive(row.get_active())

    def _load_devices(self):
        """Il motore interroga Vulkan: un thread, e la riga si riempie dopo."""
        if self._devices_loading:
            return
        self._devices_loading = True

        def work():
            devices = tts.list_devices()
            GLib.idle_add(self._devices_loaded, devices)
        threading.Thread(target=work, daemon=True).start()

    def _devices_loaded(self, devices):
        self._devices_loading = False
        self.devices = devices
        self._fill_device_row()
        return False

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
        self._set("gpu_device", self._row_devices[i - 1] if 0 < i <= len(self._row_devices) else "")

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
        for title, accel in ((_("open"), "<Control>o"), (_("generate"), "<Control>Return"),
                             (_("stop"), "Escape"), (_("save_wav"), "<Control>s"),
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
        if (self.running or self.unsaved) and not self._force_close:
            def close():
                self._force_close = True
                self.close()
            self._guard(close)
            return True
        if self.voice_dialog is not None:
            self.voice_dialog.close()           # ferma la voce di prova
        if self.media is not None:
            self.media.set_playing(False)
        if self.speaker is not None:
            self.speaker.cancel()
            self.speaker.wait(3)
            self.speaker.discard()
        tts.clean_work_dir()
        w, h = self.get_default_size()
        self.cfg.update(width=w, height=h, maximized=self.is_maximized())
        save_settings(self.cfg)
        return False


class NarratorApp(Adw.Application):
    def __init__(self):
        super().__init__(application_id=APP_ID, flags=Gio.ApplicationFlags.HANDLES_OPEN)

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
                               ("win.open", ["<Control>o"]),
                               ("win.generate", ["<Control>Return"]),
                               ("win.stop", ["Escape"]), ("win.save-wav", ["<Control>s"]),
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
        (self.props.active_window or NarratorWindow(self)).present()

    def do_open(self, files, _n, _hint):
        self.do_activate()
        if files:
            self.props.active_window.open_path(files[0].get_path())


def main():
    GLib.set_prgname(APP_ID)
    GLib.set_application_name(APP_NAME)
    return NarratorApp().run(sys.argv)


if __name__ == "__main__":
    sys.exit(main())
