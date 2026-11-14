#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
RuscaDubbing 1.99.3 — dal parlato al testo, per RuscaLinux.

Trascrive un video o un file audio con un modello Whisper che gira su questo
computer, tramite ruscawhisper-engine (whisper.cpp, software esterno con
licenza MIT), e salva il testo in Markdown e i sottotitoli in SRT. L'audio
viene estratto con FFmpeg. Tutto resta sul computer.

Copyright (C) 2026 Nunzio Curcuruto — https://www.ruscalinux.org
Licenza: GNU GPL 3.0 o successiva.

Requisiti: Python 3.10+, PyGObject, GTK 4.18+, libadwaita 1.7+,
ruscawhisper-engine, ffmpeg.
"""
import json
import os
import re
import sys

import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gdk, Gio, GLib, Gtk, Pango  # noqa: E402

BASE_DIR = os.path.dirname(os.path.realpath(__file__))
sys.path.insert(0, BASE_DIR)
import rusca_whisper as whisper  # noqa: E402

APP_ID = "org.ruscalinux.RuscaDubbing"
APP_NAME = "RuscaDubbing"
APP_VERSION = "1.99.3"
STYLE_SRC = os.path.join(BASE_DIR, "style.css")
ICON_SRC = os.path.join(BASE_DIR, "ruscadubbing.svg")
LANG_DIR = os.path.join(BASE_DIR, "lang")
DOC_DIRS = (os.path.join(BASE_DIR, "docs"), "/usr/share/doc/ruscadubbing")
CONFIG_DIR = os.path.join(GLib.get_user_config_dir(), "ruscadubbing")
CONFIG_FILE = os.path.join(CONFIG_DIR, "settings.json")
COMPONENTS = (
    ("whisper.cpp", "MIT — The ggml authors", "https://github.com/ggml-org/whisper.cpp"),
)

# Lingue del parlato: quelle dei RuscaLinux OS Tools (specifiche, sezione 9)
# con i codici di Whisper, che ha un solo cinese e un solo portoghese.
# Codice e nome nella lingua stessa. Per le altre lingue che Whisper
# conosce si usa «Rileva la lingua».
LANGUAGES = (
    ("en", "English"), ("zh", "中文"), ("es", "Español"), ("hi", "हिन्दी"),
    ("ar", "العربية"), ("pt", "Português"), ("ru", "Русский"), ("ja", "日本語"),
    ("de", "Deutsch"), ("fr", "Français"), ("it", "Italiano"), ("ko", "한국어"),
    ("id", "Bahasa Indonesia"), ("tr", "Türkçe"), ("pl", "Polski"),
    ("nl", "Nederlands"), ("uk", "Українська"), ("cs", "Čeština"),
    ("vi", "Tiếng Việt"), ("sv", "Svenska"), ("ro", "Română"), ("hu", "Magyar"),
    ("el", "Ελληνικά"), ("fi", "Suomi"),
)
CODES = [c for c, _n in LANGUAGES]
# Video e audio che FFmpeg legge; il filtro «Tutti i file» resta disponibile.
MEDIA_PATTERNS = ("mp4", "mkv", "webm", "mov", "avi", "m4v", "mpg", "mpeg", "ogv", "ts",
                  "wmv", "flv", "3gp", "mp3", "wav", "flac", "ogg", "oga", "opus",
                  "m4a", "aac", "wma", "aiff", "mka", "amr")
DEFAULTS = {
    "model": "", "gpu": False, "threads": whisper.physical_cores(),
    "language": "", "font_size": 0, "width": 760, "height": 620,
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


def load_settings():
    cfg = dict(DEFAULTS)
    try:
        with open(CONFIG_FILE, encoding="utf-8") as f:
            data = json.load(f)
        for k, v in data.items():
            if k in cfg and isinstance(v, type(cfg[k])):
                cfg[k] = v
    except (OSError, ValueError, AttributeError):
        pass
    if cfg["language"] not in CODES and cfg["language"] != "auto":
        # Primo avvio: la lingua dell'interfaccia, se Whisper la conosce.
        base = LANG.split("_")[0]
        cfg["language"] = base if base in CODES else "auto"
    cfg["threads"] = max(1, min(cfg["threads"], os.cpu_count() or 1))
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


def pick_model(saved, models):
    """Il modello salvato se c'è ancora, altrimenti il più grande trovato."""
    if saved and os.path.isfile(saved):
        return saved
    return models[0] if models else ""


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


# ── Dimensione del testo (trascrizione) ─────────────────────────
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
class DubbingWindow(FontSizeMixin, Adw.ApplicationWindow):
    def __init__(self, app):
        super().__init__(application=app, title=APP_NAME)
        self.cfg = load_settings()
        self.set_default_size(self.cfg["width"], self.cfg["height"])
        self.set_size_request(360, 294)
        if self.cfg["maximized"]:
            self.maximize()
        self.transcriber = None
        self.run_id = 0                 # le callback di una corsa vecchia si scartano
        self.running = False
        self.media = None               # percorso del video o dell'audio
        self.segments = []
        self.unsaved = False
        self.live_text = False
        self.log_lines = []
        self.models = []
        self.model_row = None
        self._row_models = []
        self._model_updating = False
        self._models_timer = 0
        self._pulse_timer = 0
        self._force_close = False
        self._monitors = []
        self._build_actions()
        self._init_font_size()
        self._build_ui()
        whisper.clean_work_dir()
        self._watch_models()
        self._refresh_models()
        self.connect("close-request", self._on_close)

    # ── azioni ────────────────────────────────────────────────────────────
    def _build_actions(self):
        for name, cb in (("open", self.open_file), ("transcribe", self.transcribe),
                         ("stop", self.stop), ("save-md", self.save_md),
                         ("save-srt", self.save_srt),
                         ("models-folder", self.open_models_folder),
                         ("preferences", self.show_preferences),
                         ("show-log", self.show_log), ("guide", self.show_guide),
                         ("shortcuts", self.show_shortcuts), ("about", self.show_about)):
            action = Gio.SimpleAction.new(name, None)
            action.connect("activate", lambda _a, _p, f=cb: f())
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
        save_menu.append(_("save_md"), "win.save-md")
        save_menu.append(_("save_srt"), "win.save-srt")
        self.save_btn = Gtk.MenuButton(icon_name="document-save-symbolic", menu_model=save_menu,
                                       tooltip_text=_("save"), sensitive=False)
        self.save_btn.update_property([Gtk.AccessibleProperty.LABEL], [_("save")])
        header.pack_start(self.save_btn)
        menu = Gio.Menu()
        tool = Gio.Menu()
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

        # Barra della trascrizione: lingua parlata e pulsante. Compare quando
        # c'è un file.
        self.lang_drop = Gtk.DropDown.new_from_strings(
            [_("auto_detect")] + [name for _code, name in LANGUAGES])
        self.lang_drop.set_tooltip_text(_("spoken_language"))
        self.lang_drop.update_property([Gtk.AccessibleProperty.LABEL], [_("spoken_language")])
        language = self.cfg["language"]
        self.lang_drop.set_selected(CODES.index(language) + 1 if language in CODES else 0)
        self.lang_drop.connect("notify::selected", self._on_language)
        lang_label = Gtk.Label(label=_("spoken_language"), xalign=0, wrap=True)
        self.transcribe_btn = Gtk.Button(label=_("transcribe"), action_name="win.transcribe")
        self.transcribe_btn.add_css_class("suggested-action")
        self.transcribe_btn.add_css_class("pill")
        langs = Gtk.Box(spacing=12, hexpand=True)
        langs.append(lang_label)
        langs.append(self.lang_drop)
        self.bar = Gtk.Box(spacing=12, margin_start=12, margin_end=12, margin_top=6,
                           margin_bottom=6, visible=False)
        self.bar.append(langs)
        self.bar.append(self.transcribe_btn)

        self.banner = Adw.Banner()
        self.banner.connect("button-clicked", lambda _b: self.open_models_folder())

        # Tre stati: nessun file, file pronto, testo.
        empty = Adw.StatusPage(
            icon_name=APP_ID if theme_has_icon() else "audio-x-generic-symbolic",
            title=_("empty_title"), description=_("empty_desc"))
        choose = Gtk.Button(label=_("choose_media"), action_name="win.open",
                            halign=Gtk.Align.CENTER)
        choose.add_css_class("suggested-action")
        choose.add_css_class("pill")
        empty.set_child(choose)

        self.media_icon = Gtk.Image(icon_name="audio-x-generic-symbolic", pixel_size=64)
        self.media_icon.add_css_class("dim-label")
        self.media_label = Gtk.Label(wrap=True, wrap_mode=Pango.WrapMode.WORD_CHAR,
                                     justify=Gtk.Justification.CENTER)
        self.media_label.add_css_class("title-2")
        self.model_label = Gtk.Label(wrap=True, wrap_mode=Pango.WrapMode.WORD_CHAR,
                                     justify=Gtk.Justification.CENTER)
        self.model_label.add_css_class("dim-label")
        ready = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12,
                        valign=Gtk.Align.CENTER, margin_start=24, margin_end=24,
                        margin_top=24, margin_bottom=24)
        for w in (self.media_icon, self.media_label, self.model_label):
            ready.append(w)

        self.buf = Gtk.TextBuffer()
        self.view = Gtk.TextView(buffer=self.buf, editable=False, cursor_visible=False,
                                 wrap_mode=Gtk.WrapMode.WORD_CHAR, top_margin=12,
                                 bottom_margin=12, left_margin=12, right_margin=12)
        self.view.add_css_class("rusca-content")
        self.view.update_property([Gtk.AccessibleProperty.LABEL], [_("transcript")])
        self.scroll = Gtk.ScrolledWindow(child=self.view, vexpand=True, hexpand=True,
                                         hscrollbar_policy=Gtk.PolicyType.NEVER,
                                         margin_start=12, margin_end=12, margin_top=6,
                                         margin_bottom=12)
        self.scroll.add_css_class("card")

        self.stack = Gtk.Stack()
        self.stack.add_named(empty, "empty")
        self.stack.add_named(ready, "ready")
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

        view = Adw.ToolbarView(content=self.toasts)
        view.add_top_bar(header)
        view.add_top_bar(self.bar)
        view.add_top_bar(self.banner)
        view.add_bottom_bar(self.progress_bar)
        self.set_content(view)
        narrow = Adw.Breakpoint.new(Adw.BreakpointCondition.parse("max-width: 500sp"))
        narrow.add_setter(self.bar, "orientation", Gtk.Orientation.VERTICAL)
        self.add_breakpoint(narrow)

    def _refresh_actions(self):
        ready = bool(self.cfg["model"]) and bool(whisper.find_binary()) \
            and bool(whisper.find_ffmpeg())
        done = bool(self.segments) and not self.running
        self.lookup_action("transcribe").set_enabled(
            bool(self.media) and ready and not self.running)
        self.lookup_action("stop").set_enabled(self.running)
        self.lookup_action("save-md").set_enabled(done)
        self.lookup_action("save-srt").set_enabled(done)
        self.save_btn.set_sensitive(done)
        self.lang_drop.set_sensitive(not self.running)

    def _refresh_banner(self):
        b = self.banner
        if not whisper.find_binary():
            b.set_title(_("banner_no_engine"))
            b.set_button_label(None)
            b.set_revealed(True)
        elif not whisper.find_ffmpeg():
            b.set_title(_("err_no_ffmpeg"))
            b.set_button_label(None)
            b.set_revealed(True)
        elif not self.cfg["model"]:
            b.set_title(_("banner_no_model"))
            b.set_button_label(_("open_models_folder"))
            b.set_revealed(True)
        else:
            b.set_revealed(False)
        model = self.cfg["model"]
        self.model_label.set_label(os.path.basename(model) if model else _("no_model"))
        self._refresh_actions()

    def _on_language(self, drop, _pspec):
        i = drop.get_selected()
        self._set("language", CODES[i - 1] if 0 < i <= len(CODES) else "auto")

    def _set(self, key, value):
        self.cfg[key] = value
        save_settings(self.cfg)

    def _toast(self, text, timeout=5):
        self.toasts.add_toast(Adw.Toast(title=GLib.markup_escape_text(text), timeout=timeout))

    # ── modelli ───────────────────────────────────────────────────────────
    def _watch_models(self):
        """Tiene d'occhio le cartelle dei modelli: quando l'utente ne copia
        uno, compare senza riavviare il programma."""
        try:
            whisper.ensure_user_model_dir()
        except OSError:
            pass
        for d in whisper.MODEL_DIRS:
            if not os.path.isdir(d):
                continue
            try:
                monitor = Gio.File.new_for_path(d).monitor_directory(
                    Gio.FileMonitorFlags.NONE, None)
            except GLib.Error:
                continue
            monitor.connect("changed", self._on_models_changed)
            self._monitors.append(monitor)

    def _on_models_changed(self, *_a):
        if not self._models_timer:
            self._models_timer = GLib.timeout_add(700, self._models_timeout)

    def _models_timeout(self):
        self._models_timer = 0
        self._refresh_models()
        return False

    def _refresh_models(self):
        self.models = whisper.find_models()
        self.cfg["model"] = pick_model(self.cfg["model"], self.models)
        self._fill_model_row()
        self._refresh_banner()

    def _fill_model_row(self):
        row = self.model_row
        if row is None:
            return
        models = list(self.models)
        if self.cfg["model"] and self.cfg["model"] not in models:
            models.insert(0, self.cfg["model"])
        self._row_models = models
        self._model_updating = True
        row.set_model(Gtk.StringList.new([os.path.basename(p) for p in models]
                                         or [_("no_model")]))
        row.set_sensitive(bool(models))
        if self.cfg["model"] in models:
            row.set_selected(models.index(self.cfg["model"]))
        self._model_updating = False

    def _on_model(self, row, _pspec):
        if self._model_updating:
            return
        i = row.get_selected()
        if 0 <= i < len(self._row_models):
            self._set("model", self._row_models[i])
            self._refresh_banner()

    def open_models_folder(self):
        try:
            folder = whisper.ensure_user_model_dir()
        except OSError as e:
            self._show_error(_("open_error"), str(e))
            return
        Gtk.FileLauncher.new(Gio.File.new_for_path(folder)).launch(self, None, None)

    # ── file ──────────────────────────────────────────────────────────────
    def _guard(self, then):
        """Esegue `then` subito, o dopo la conferma se andrebbe persa una
        trascrizione in corso o non salvata."""
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
        """Butta via la trascrizione in corso o non salvata."""
        self.run_id += 1                      # le callback in arrivo si scartano
        if self.transcriber is not None:
            self.transcriber.cancel()
        self._set_running(False)
        self.segments = []
        self.unsaved = False
        self.buf.set_text("")
        self.stack.set_visible_child_name("ready" if self.media else "empty")
        self._refresh_actions()

    def _media_filters(self):
        media = Gtk.FileFilter()
        media.set_name(_("media_files"))
        media.add_mime_type("video/*")
        media.add_mime_type("audio/*")
        for ext in MEDIA_PATTERNS:
            media.add_suffix(ext)
        everything = Gtk.FileFilter()
        everything.set_name(_("all_files"))
        everything.add_pattern("*")
        store = Gio.ListStore.new(Gtk.FileFilter)
        store.append(media)
        store.append(everything)
        return store

    def open_file(self):
        self._guard(self._choose_media)

    def _choose_media(self):
        dialog = Gtk.FileDialog(title=_("choose_media").rstrip("…"),
                                filters=self._media_filters())

        def done(d, result):
            try:
                self.load_media(d.open_finish(result).get_path())
            except GLib.Error:
                pass
        dialog.open(self, None, done)

    def open_path(self, path):
        """File trascinato sulla finestra o passato dalla riga di comando."""
        if path:
            self._guard(lambda: self.load_media(path))

    def load_media(self, path):
        if not path or not os.path.isfile(path):
            self._show_error(_("open_error"), path or "")
            return
        self.media = path
        self.segments = []
        self.unsaved = False
        self.buf.set_text("")
        name = os.path.basename(path)
        kind, _uncertain = Gio.content_type_guess(name, None)
        self.media_icon.set_from_icon_name(
            "video-x-generic-symbolic" if (kind or "").startswith("video/")
            else "audio-x-generic-symbolic")
        self.media_label.set_label(name)
        self.title.set_subtitle(name)
        self.bar.set_visible(True)
        self.stack.set_visible_child_name("ready")
        self._refresh_actions()

    # ── trascrizione ──────────────────────────────────────────────────────
    def transcribe(self):
        if self.media and not self.running:
            self._guard(self._start)

    def _start(self):
        self.run_id += 1
        rid = self.run_id

        def mine(callback):
            return lambda *args: rid == self.run_id and callback(*args)
        self.transcriber = whisper.Transcriber(
            on_stage=mine(self._on_stage), on_segment=mine(self._on_segment),
            on_log=mine(self._on_log), on_done=mine(self._on_done))
        self.log_lines.clear()
        self.segments = []
        self.unsaved = False
        self.live_text = False
        self.buf.set_text("")
        self.stack.set_visible_child_name("ready")
        try:
            self.transcriber.start(self.media, self.cfg["model"], self.cfg["language"],
                                   self.cfg["threads"], self.cfg["gpu"])
        except whisper.WhisperError as e:
            self._show_error(_(e.key), e.detail)
            return
        self._set_running(True)
        self._on_stage("audio", 0)

    def stop(self):
        if self.running and self.transcriber is not None:
            self.transcriber.cancel()

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

    def _on_stage(self, stage, percent=0):
        if not self.running:
            return
        if stage == "speech":
            self._stop_pulse()
            self.progress.set_fraction(min(1.0, max(0, percent) / 100))
            self.progress.set_text(_("transcribing", percent=percent))
            return
        # Estrazione dell'audio e caricamento del modello non dicono a che
        # punto sono: la barra scorre.
        self.progress.set_text(_("extracting" if stage == "audio" else "loading_model"))
        if not self._pulse_timer:
            self._pulse_timer = GLib.timeout_add(150, self._pulse)

    def _on_segment(self, segment):
        if not self.live_text:
            self.live_text = True
            self.stack.set_visible_child_name("text")
        self.buf.insert(self.buf.get_end_iter(), segment.text + " ")
        adj = self.scroll.get_vadjustment()
        adj.set_value(adj.get_upper())

    def _on_log(self, line):
        self.log_lines.append(line)
        del self.log_lines[:-2000]

    def _on_done(self, error, _language, segments):
        self._set_running(False)
        if error is None and segments:
            self.segments = list(segments)
            self.unsaved = True
            self.buf.set_text(whisper.plain_text(self.segments))
            self.stack.set_visible_child_name("text")
            self._refresh_actions()
            self._toast(_("completed"), 6)
            return
        self.buf.set_text("")
        self.stack.set_visible_child_name("ready")
        if error == "cancelled":
            self._toast(_("stopped"))
        elif error is None:
            self._toast(_("no_speech"), 8)
        else:
            self._show_error(_(error.key), error.detail)

    # ── salvataggio ───────────────────────────────────────────────────────
    def save_md(self):
        self._save("md", _("save_md"), _("markdown_files"))

    def save_srt(self):
        self._save("srt", _("save_srt"), _("srt_files"))

    def _save(self, ext, title, filter_name):
        if not self.segments or not self.media:
            return
        base = os.path.splitext(os.path.basename(self.media))[0]
        filt = Gtk.FileFilter()
        filt.set_name(filter_name)
        filt.add_pattern(f"*.{ext}")
        store = Gio.ListStore.new(Gtk.FileFilter)
        store.append(filt)
        # Accanto al video, con lo stesso nome: i lettori caricano da soli
        # i sottotitoli che trovano così.
        dialog = Gtk.FileDialog(title=title.rstrip("…"), initial_name=f"{base}.{ext}",
                                filters=store)
        folder = os.path.dirname(self.media)
        if os.path.isdir(folder):
            dialog.set_initial_folder(Gio.File.new_for_path(folder))
        text = (whisper.to_srt(self.segments) if ext == "srt"
                else whisper.to_markdown(self.segments, base))

        def done(d, result):
            try:
                path = d.save_finish(result).get_path()
            except GLib.Error:
                return
            try:
                with open(path, "w", encoding="utf-8", newline="\n") as f:
                    f.write(text)
            except OSError as e:
                self._show_error(_("save_error"), str(e))
                return
            self.unsaved = False
            self._toast(_("saved", name=os.path.basename(path)))
        dialog.save(self, None, done)

    # ── preferenze e finestre ─────────────────────────────────────────────
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

        group = Adw.PreferencesGroup(title=_("group_model"), description=_("model_hint"))
        self.model_row = Adw.ComboRow(title=_("model"), use_subtitle=True)
        self._fill_model_row()
        self.model_row.connect("notify::selected", self._on_model)
        group.add(self.model_row)
        folder = Adw.ActionRow(title=_("open_models_folder"), subtitle=whisper.USER_MODEL_DIR,
                               activatable=True)
        folder.add_suffix(Gtk.Image(icon_name="folder-open-symbolic"))
        folder.connect("activated", lambda _r: self.open_models_folder())
        group.add(folder)
        page.add(group)

        eng = Adw.PreferencesGroup(title=_("group_engine"))
        gpu = Adw.SwitchRow(title=_("gpu"), subtitle=_("gpu_sub"), active=self.cfg["gpu"])
        gpu.connect("notify::active", lambda r, _p: self._set("gpu", r.get_active()))
        eng.add(gpu)
        threads = Adw.SpinRow.new_with_range(1, max(1, os.cpu_count() or 1), 1)
        threads.set_title(_("threads"))
        threads.set_subtitle(_("threads_sub", n=whisper.physical_cores()))
        threads.set_value(min(self.cfg["threads"], os.cpu_count() or 1))
        threads.connect("notify::value", lambda r, _p: self._set("threads", int(r.get_value())))
        eng.add(threads)
        page.add(eng)

        dialog = Adw.PreferencesDialog(title=_("preferences").rstrip("…"))
        dialog.add(page)
        dialog.connect("closed", lambda _d: setattr(self, "model_row", None))
        dialog.present(self)

    def _on_theme(self, row, _pspec):
        self._set("theme", THEMES[row.get_selected()])
        apply_color_scheme(self.cfg["theme"])

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
        for title, accel in ((_("open"), "<Control>o"),
                             (_("transcribe"), "<Control>Return"), (_("stop"), "Escape"),
                             (_("save_md"), "<Control>s"), (_("save_srt"), "<Control>e"),
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
            return True                       # la finestra resta finché non si conferma
        if self.transcriber is not None:
            self.transcriber.cancel()
            self.transcriber.wait(3)
        whisper.clean_work_dir()
        w, h = self.get_default_size()
        self.cfg.update(width=w, height=h, maximized=self.is_maximized())
        save_settings(self.cfg)
        return False


class DubbingApp(Adw.Application):
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
                               ("win.transcribe", ["<Control>Return"]),
                               ("win.stop", ["Escape"]),
                               ("win.save-md", ["<Control>s"]), ("win.save-srt", ["<Control>e"]),
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
        (self.props.active_window or DubbingWindow(self)).present()

    def do_open(self, files, _n, _hint):
        self.do_activate()
        if files:
            self.props.active_window.open_path(files[0].get_path())


def main():
    GLib.set_prgname(APP_ID)
    GLib.set_application_name(APP_NAME)
    return DubbingApp().run(sys.argv)


if __name__ == "__main__":
    sys.exit(main())
