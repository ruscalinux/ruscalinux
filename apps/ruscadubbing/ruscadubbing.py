#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
RuscaDubbing 1.99.3 — la sala di doppiaggio di RuscaLinux.

Da un video nella sua lingua a un video doppiato: i sottotitoli nelle due
lingue, l'audio doppiato e il video con le due tracce audio e le due tracce
di sottotitoli. Trascrive con ruscawhisper-engine (whisper.cpp), traduce e
doppia con ruscallama-engine (llama.cpp: llama-server e llama-tts), missa e
scrive il video con FFmpeg. Software esterni con licenza MIT. Tutto resta sul
computer.

Copyright (C) 2026 Nunzio Curcuruto — https://www.ruscalinux.org
Licenza: GNU GPL 3.0 o successiva.

Requisiti: Python 3.10+, PyGObject, GTK 4.18+, libadwaita 1.7+,
ruscawhisper-engine, ruscallama-engine (con llama-tts), ffmpeg.
"""

import json
import os
import re
import sys
import threading
import time

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gdk, Gio, GLib, GObject, Gtk  # noqa: E402

BASE_DIR = os.path.dirname(os.path.realpath(__file__))
sys.path.insert(0, BASE_DIR)

import rusca_dubbing as dub  # noqa: E402
import rusca_voicematch as match  # noqa: E402

tts, whisper, engine = dub.tts, dub.whisper, dub.engine

APP_ID = dub.APP_ID
APP_NAME = "RuscaDubbing"
APP_VERSION = "1.99.3"
STYLE_SRC = os.path.join(BASE_DIR, "style.css")
ICON_SRC = os.path.join(BASE_DIR, "ruscadubbing.svg")
LANG_DIR = os.path.join(BASE_DIR, "lang")
DOC_DIRS = (os.path.join(BASE_DIR, "docs"), "/usr/share/doc/ruscadubbing")
CONFIG_DIR = os.path.join(GLib.get_user_config_dir(), "ruscadubbing")
CONFIG_FILE = os.path.join(CONFIG_DIR, "settings.json")

COMPONENTS = (
    ("whisper.cpp (whisper-cli)", "MIT — The ggml authors", "https://github.com/ggml-org/whisper.cpp"),
    ("llama.cpp (llama-server, llama-tts)", "MIT — The ggml authors",
     "https://github.com/ggml-org/llama.cpp"),
    ("FFmpeg", "LGPL 2.1 / GPL — The FFmpeg developers", "https://ffmpeg.org/"),
)
VIDEO_PATTERNS = ("mp4", "mkv", "webm", "mov", "avi", "m4v", "mpg", "mpeg", "ts", "ogv", "wmv",
                  "flv", "3gp")
SOURCE_CODES = ["auto"] + dub.CODES + sorted(dub.EXTRA_SOURCE)
DUCKING = ("light", "medium", "strong")
THEMES = ("system", "light", "dark")
GENDERS = ("auto", "male", "female")
# Una scheda grafica per passo: la trascrizione, la traduzione, la voce.
DEVICE_KEYS = ("whisper_device", "llm_device", "tts_device")
DEFAULTS = {
    "whisper_model": "", "llm_model": "", "voice_model": "", "speaker_file": "",
    "voice_name": "", "src": "auto", "tgt": "", "out_srt": True, "out_audio": False,
    "out_video": True, "fmt": "mkv", "ducking": "medium", "folder": "", "max_speed": 1.3,
    "seed": 42, "context": 8192, "gpu": True,
    "whisper_device": "", "llm_device": "", "tts_device": "",
    "threads": tts.physical_cores(), "width": 760, "height": 720, "maximized": False,
    "theme": "system", "speaker_gender": "auto",
}


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


# Le scelte già fatte nelle altre app: alla prima apertura RuscaDubbing usa
# gli stessi modelli, la stessa voce di riferimento e lo stesso seme, invece
# del primo file in ordine alfabetico (che può essere il modello piccolo).
SIBLINGS = (
    ("ruscatranscriber", {"model": "whisper_model", "gpu_device": "whisper_device"}),
    ("ruscatranslator", {"model": "llm_model", "gpu_device": "llm_device"}),
    ("ruscanarrator", {"model": "voice_model", "speaker_file": "speaker_file",
                       "voice_name": "voice_name", "seed": "seed", "max_speed": "max_speed",
                       "gpu_device": "tts_device"}),
)


def sibling_settings(config_dir=None):
    """{chiave di RuscaDubbing: valore} dalle impostazioni delle altre app."""
    config_dir = config_dir or GLib.get_user_config_dir()
    out = {}
    for app, keys in SIBLINGS:
        try:
            with open(os.path.join(config_dir, app, "settings.json"),
                      encoding="utf-8") as f:
                data = json.load(f)
        except (OSError, ValueError):
            continue
        if not isinstance(data, dict):
            continue
        for theirs, ours in keys.items():
            value = data.get(theirs)
            if value not in (None, "") and (isinstance(value, type(DEFAULTS[ours])) or (
                    isinstance(DEFAULTS[ours], float) and isinstance(value, int))):
                out[ours] = type(DEFAULTS[ours])(value)
    return out


def load_settings():
    cfg = dict(DEFAULTS)
    if not os.path.exists(CONFIG_FILE):
        cfg.update(sibling_settings())
    try:
        with open(CONFIG_FILE, encoding="utf-8") as f:
            data = json.load(f)
        for k, v in data.items():
            if k in cfg and (isinstance(v, type(cfg[k])) or
                             (isinstance(cfg[k], float) and isinstance(v, int))):
                cfg[k] = type(cfg[k])(v)
        # Fino alla prima 1.99.3 c'era una sola scheda per tutti i passi.
        old = data.get("gpu_device") if isinstance(data, dict) else None
        if isinstance(old, str) and old and not any(k in data for k in DEVICE_KEYS):
            for k in DEVICE_KEYS:
                cfg[k] = old
    except (OSError, ValueError, AttributeError, TypeError):
        pass
    if cfg["tgt"] not in dub.CODES:
        # Primo avvio: si doppia nella lingua dell'interfaccia, se la voce la conosce.
        base = LANG.split("_")[0]
        cfg["tgt"] = base if base in dub.CODES else "en"
    if cfg["src"] not in SOURCE_CODES:
        cfg["src"] = "auto"
    if cfg["fmt"] not in dub.VIDEO_FORMATS:
        cfg["fmt"] = "mkv"
    if cfg["speaker_gender"] not in GENDERS:
        cfg["speaker_gender"] = "auto"
    if cfg["ducking"] not in DUCKING:
        cfg["ducking"] = "medium"
    cfg["threads"] = max(1, min(cfg["threads"], os.cpu_count() or 1))
    cfg["max_speed"] = min(2.0, max(1.0, cfg["max_speed"]))
    cfg["context"] = min(131072, max(2048, cfg["context"]))
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


def pick(saved, paths):
    """Il file salvato se c'è ancora, altrimenti il primo (il più grande)."""
    return saved if saved in paths else (paths[0] if paths else "")


def language_name(code):
    if code == "auto":
        return _("lang_auto")
    if code in dub.NATIVE:
        return dub.NATIVE[code]
    return dub.english_name(code)


def duration_text(ms):
    s = max(0, int(round(ms / 1000)))
    return f"{s // 3600}:{s // 60 % 60:02d}:{s % 60:02d}" if s >= 3600 else f"{s // 60}:{s % 60:02d}"


def show_about_dialog(parent, tr, app_id, app_name, version, description, has_icon,
                      components=()):
    """Finestra «Informazioni» comune alle RuscaLinux OS Apps (sezioni 3.10 e 12)."""
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

    note_label = Gtk.Label(label=tr("ai_note"), wrap=True, xalign=0, valign=Gtk.Align.START,
                           margin_top=12, margin_bottom=24, margin_start=24, margin_end=24)
    note_label.add_css_class("body")
    note_view = Adw.ToolbarView(content=note_label)
    note_view.add_top_bar(Adw.HeaderBar())
    note_page = Adw.NavigationPage(title=tr("dev_note_title"), child=note_view)
    note_row.connect("activated", lambda _row: nav.push(note_page))

    Adw.Dialog(title=app_name, content_width=420, child=nav).present(parent)


# ── Finestra principale ──────────────────────────────────────────────────────
class DubbingWindow(Adw.ApplicationWindow):
    def __init__(self, app):
        super().__init__(application=app, title=APP_NAME)
        self.cfg = load_settings()
        self.set_default_size(self.cfg["width"], self.cfg["height"])
        self.set_size_request(360, 294)
        if self.cfg["maximized"]:
            self.maximize()
        self.media = None                # video scelto
        self.info = None                 # probe(): durata e flussi
        self.source_srt = ""             # sottotitoli originali scelti a mano
        self.files = {}                  # file dell'ultimo doppiaggio
        self.log_lines = []
        self.devices = []
        self._devices_loading = False
        self._row_devices = []
        self._updating = False
        self._force_close = False
        self._started = 0.0
        self._clock = 0
        self.whisper_models, self.llm_models, self.voices = [], [], []
        self.pref_rows = {}
        self.dubbing = dub.Dubbing(self._on_stage, self._on_log, self._on_done)
        self.finder = None               # finestra «Trova una voce simile» aperta
        self._build_actions()
        self._build_ui()
        dub.clean_work_dir()
        self._refresh_models()
        self.connect("close-request", self._on_close)

    # ── azioni ────────────────────────────────────────────────────────────
    def _build_actions(self):
        for name, cb in (("open", self.open_file), ("dub", self.start),
                         ("preview", lambda: self.start(preview=True)),
                         ("stop", self.stop), ("new", self.new_dubbing),
                         ("open-result", self.open_result), ("open-folder", self.open_folder),
                         ("preferences", self.show_preferences), ("show-log", self.show_log),
                         ("guide", self.show_guide), ("shortcuts", self.show_shortcuts),
                         ("about", self.show_about)):
            action = Gio.SimpleAction.new(name, None)
            action.connect("activate", lambda _a, _p, f=cb: f())
            self.add_action(action)

    # ── interfaccia ───────────────────────────────────────────────────────
    def _build_ui(self):
        header = Adw.HeaderBar()
        header.set_title_widget(Adw.WindowTitle(title=APP_NAME))
        self.open_btn = Gtk.Button(icon_name="document-open-symbolic", action_name="win.open",
                                   tooltip_text=_("open"))
        self.open_btn.update_property([Gtk.AccessibleProperty.LABEL], [_("open")])
        header.pack_start(self.open_btn)
        menu = Gio.Menu()
        tool = Gio.Menu()
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
        self.banner.connect("button-clicked", lambda _b: self.show_preferences())

        self.stack = Gtk.Stack(transition_type=Gtk.StackTransitionType.CROSSFADE)
        self.stack.add_named(self._empty_page(), "empty")
        self.stack.add_named(self._setup_page(), "setup")
        self.stack.add_named(self._work_page(), "work")
        self.stack.add_named(self._done_page(), "done")
        drop = Gtk.DropTarget.new(Gio.File, Gdk.DragAction.COPY)
        drop.connect("drop", lambda _t, f, _x, _y: self._dropped(f))
        self.stack.add_controller(drop)
        self.toasts = Adw.ToastOverlay(child=self.stack)

        view = Adw.ToolbarView(content=self.toasts)
        view.add_top_bar(header)
        view.add_top_bar(self.banner)
        self.set_content(view)

    def _scrolled(self, child):
        clamp = Adw.Clamp(maximum_size=640, child=child, margin_top=18, margin_bottom=24,
                          margin_start=12, margin_end=12)
        return Gtk.ScrolledWindow(child=clamp, hscrollbar_policy=Gtk.PolicyType.NEVER,
                                  vexpand=True)

    def _empty_page(self):
        page = Adw.StatusPage(
            icon_name=APP_ID if theme_has_icon() else "camera-video-symbolic",
            title=_("empty_title"), description=_("empty_desc"))
        choose = Gtk.Button(label=_("choose_video"), action_name="win.open",
                            halign=Gtk.Align.CENTER)
        choose.add_css_class("suggested-action")
        choose.add_css_class("pill")
        page.set_child(choose)
        return page

    def _setup_page(self):
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=24)

        video = Adw.PreferencesGroup(title=_("group_video"))
        self.video_row = Adw.ActionRow(title="", subtitle="", title_lines=2)
        self.video_row.add_prefix(Gtk.Image(icon_name="video-x-generic-symbolic"))
        change = Gtk.Button(icon_name="document-open-symbolic", valign=Gtk.Align.CENTER,
                            tooltip_text=_("change_video"), action_name="win.open")
        change.add_css_class("flat")
        change.update_property([Gtk.AccessibleProperty.LABEL], [_("change_video")])
        self.video_row.add_suffix(change)
        video.add(self.video_row)
        # Lavoro già fatto per questo video: trascrizione e traduzioni
        # salvate, che si riusano (si rifanno solo voce e missaggio).
        self.saved_row = Adw.ActionRow(title=_("saved_work"), visible=False)
        self.saved_row.add_prefix(Gtk.Image(icon_name="document-save-symbolic"))
        forget = Gtk.Button(label=_("saved_forget"), valign=Gtk.Align.CENTER,
                            tooltip_text=_("saved_forget_tip"))
        forget.add_css_class("flat")
        forget.connect("clicked", lambda _b: self._forget())
        self.saved_row.add_suffix(forget)
        video.add(self.saved_row)
        box.append(video)

        langs = Adw.PreferencesGroup(title=_("group_languages"))
        self.src_row = Adw.ComboRow(title=_("source_language"), subtitle=_("source_language_sub"),
                                    model=Gtk.StringList.new([language_name(c) for c in SOURCE_CODES]))
        self.src_row.set_selected(SOURCE_CODES.index(self.cfg["src"]))
        self.src_row.connect("notify::selected", lambda r, _p: self._set(
            "src", SOURCE_CODES[r.get_selected()]))
        langs.add(self.src_row)
        self.tgt_row = Adw.ComboRow(title=_("target_language"), subtitle=_("target_language_sub"),
                                    model=Gtk.StringList.new([dub.NATIVE[c] for c in dub.CODES]))
        self.tgt_row.set_selected(dub.CODES.index(self.cfg["tgt"]))
        self.tgt_row.connect("notify::selected", lambda r, _p: self._set(
            "tgt", dub.CODES[r.get_selected()]))
        langs.add(self.tgt_row)
        # Sottotitoli originali: trascritti dal video, o un file SRT (per
        # esempio corretto a mano, o quelli del film).
        self.srt_row = Adw.ActionRow(title=_("source_subtitles"))
        self.srt_clear = Gtk.Button(icon_name="edit-clear-symbolic", valign=Gtk.Align.CENTER,
                                    tooltip_text=_("srt_clear"), visible=False)
        self.srt_clear.add_css_class("flat")
        self.srt_clear.update_property([Gtk.AccessibleProperty.LABEL], [_("srt_clear")])
        self.srt_clear.connect("clicked", lambda _b: self._set_source_srt(""))
        self.srt_row.add_suffix(self.srt_clear)
        srt_choose = Gtk.Button(icon_name="document-open-symbolic", valign=Gtk.Align.CENTER,
                                tooltip_text=_("srt_choose"))
        srt_choose.add_css_class("flat")
        srt_choose.update_property([Gtk.AccessibleProperty.LABEL], [_("srt_choose")])
        srt_choose.connect("clicked", lambda _b: self._choose_srt())
        self.srt_row.add_suffix(srt_choose)
        langs.add(self.srt_row)
        # Chi parla: serve all'accordo in prima persona («sono stato/a»).
        self.gender_row = Adw.ComboRow(title=_("speaker_gender"), subtitle=_("speaker_gender_sub"),
                                       model=Gtk.StringList.new([_(f"gender_{g}") for g in GENDERS]))
        self.gender_row.set_selected(GENDERS.index(self.cfg["speaker_gender"]))
        self.gender_row.connect("notify::selected", lambda r, _p: self._set(
            "speaker_gender", GENDERS[r.get_selected()]))
        langs.add(self.gender_row)
        # Glossario di questo video: nomi e termini da tradurre sempre allo
        # stesso modo, o da non tradurre.
        self.glossary_row = Adw.EntryRow(title=_("glossary"), show_apply_button=True)
        self.glossary_row.set_tooltip_text(_("glossary_tip"))
        self.glossary_row.connect("apply", lambda r: self._save_glossary(r.get_text()))
        self.glossary_row.connect("changed", lambda r: self._save_glossary(r.get_text(), quiet=True))
        langs.add(self.glossary_row)
        box.append(langs)

        # La voce del doppiaggio: quella di riferimento, e la ricerca di una
        # voce che somigli all'originale.
        voice_group = Adw.PreferencesGroup(title=_("group_dub_voice"))
        self.voice_row = Adw.ActionRow(title=_("speaker_file"), activatable=True)
        self.voice_row.connect("activated", lambda _r: self.show_preferences())
        self.find_btn = Gtk.Button(label=_("find_voice"), valign=Gtk.Align.CENTER,
                                   tooltip_text=_("find_voice_tip"))
        self.find_btn.connect("clicked", lambda _b: self.find_voice())
        self.voice_row.add_suffix(self.find_btn)
        voice_group.add(self.voice_row)
        box.append(voice_group)

        out = Adw.PreferencesGroup(title=_("group_output"))
        self.out_rows = {}
        for key in ("out_srt", "out_audio", "out_video"):
            row = Adw.SwitchRow(title=_(key), subtitle=_(f"{key}_sub"), active=self.cfg[key])
            row.connect("notify::active", lambda r, _p, k=key: (self._set(k, r.get_active()),
                                                               self._refresh_actions()))
            self.out_rows[key] = row
            out.add(row)
        self.fmt_row = Adw.ComboRow(title=_("video_format"), model=Gtk.StringList.new(
            [_(f"fmt_{f}") for f in dub.VIDEO_FORMATS]))
        self.fmt_row.set_selected(dub.VIDEO_FORMATS.index(self.cfg["fmt"]))
        self.fmt_row.connect("notify::selected", lambda r, _p: self._set(
            "fmt", dub.VIDEO_FORMATS[r.get_selected()]))
        self.out_rows["out_video"].bind_property("active", self.fmt_row, "sensitive",
                                                 GObject.BindingFlags.SYNC_CREATE)
        out.add(self.fmt_row)
        self.duck_row = Adw.ComboRow(title=_("ducking"), subtitle=_("ducking_sub"),
                                     model=Gtk.StringList.new([_(f"ducking_{d}") for d in DUCKING]))
        self.duck_row.set_selected(DUCKING.index(self.cfg["ducking"]))
        self.duck_row.connect("notify::selected", lambda r, _p: self._set(
            "ducking", DUCKING[r.get_selected()]))
        out.add(self.duck_row)
        self.folder_row = Adw.ActionRow(title=_("output_folder"))
        self.folder_reset = Gtk.Button(icon_name="edit-clear-symbolic", valign=Gtk.Align.CENTER,
                                       tooltip_text=_("folder_reset"))
        self.folder_reset.add_css_class("flat")
        self.folder_reset.update_property([Gtk.AccessibleProperty.LABEL], [_("folder_reset")])
        self.folder_reset.connect("clicked", lambda _b: (self._set("folder", ""),
                                                         self._refresh_folder()))
        self.folder_row.add_suffix(self.folder_reset)
        folder_choose = Gtk.Button(icon_name="folder-open-symbolic", valign=Gtk.Align.CENTER,
                                   tooltip_text=_("folder_choose"))
        folder_choose.add_css_class("flat")
        folder_choose.update_property([Gtk.AccessibleProperty.LABEL], [_("folder_choose")])
        folder_choose.connect("clicked", lambda _b: self._choose_folder())
        self.folder_row.add_suffix(folder_choose)
        out.add(self.folder_row)
        box.append(out)

        buttons = Gtk.Box(spacing=12, halign=Gtk.Align.CENTER)
        preview = Gtk.Button(label=_("preview"), action_name="win.preview",
                             tooltip_text=_("preview_tip"))
        preview.add_css_class("pill")
        self.dub_btn = Gtk.Button(label=_("dub"), action_name="win.dub")
        self.dub_btn.add_css_class("suggested-action")
        self.dub_btn.add_css_class("pill")
        buttons.append(preview)
        buttons.append(self.dub_btn)
        box.append(buttons)
        narrow = Adw.Breakpoint.new(Adw.BreakpointCondition.parse("max-width: 420sp"))
        narrow.add_setter(buttons, "orientation", Gtk.Orientation.VERTICAL)
        self.add_breakpoint(narrow)
        return self._scrolled(box)

    def _work_page(self):
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=24)
        self.work_title = Gtk.Label(wrap=True, justify=Gtk.Justification.CENTER)
        self.work_title.add_css_class("title-2")
        box.append(self.work_title)
        group = Adw.PreferencesGroup()
        self.stage_rows = {}
        for stage in dub.STAGES:
            row = Adw.ActionRow(title=_(f"stage_{stage}"), subtitle=_(f"stage_{stage}_sub"))
            icon = Gtk.Image(icon_name="content-loading-symbolic")
            icon.add_css_class("dim-label")
            # Adw.Spinner c'è da libadwaita 1.6; prima, quello di GTK.
            spinner = (Adw.Spinner(visible=False) if hasattr(Adw, "Spinner")
                       else Gtk.Spinner(spinning=True, visible=False))
            row.add_prefix(icon)
            row.add_prefix(spinner)
            self.stage_rows[stage] = (row, icon, spinner)
            group.add(row)
        box.append(group)
        self.progress = Gtk.ProgressBar(show_text=True)
        box.append(self.progress)
        self.clock_label = Gtk.Label()
        self.clock_label.add_css_class("dim-label")
        self.clock_label.add_css_class("numeric")
        box.append(self.clock_label)
        stop = Gtk.Button(label=_("stop"), action_name="win.stop", halign=Gtk.Align.CENTER)
        stop.add_css_class("destructive-action")
        stop.add_css_class("pill")
        box.append(stop)
        return self._scrolled(box)

    def _done_page(self):
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=24)
        self.done_status = Adw.StatusPage(icon_name="emblem-ok-symbolic", title=_("done_title"))
        self.done_status.add_css_class("compact")
        box.append(self.done_status)
        self.files_group = Adw.PreferencesGroup(title=_("group_files"))
        self._file_rows = []
        box.append(self.files_group)
        buttons = Gtk.Box(spacing=12, halign=Gtk.Align.CENTER)
        self.play_btn = Gtk.Button(label=_("open_result"), action_name="win.open-result")
        self.play_btn.add_css_class("suggested-action")
        self.play_btn.add_css_class("pill")
        folder = Gtk.Button(label=_("open_folder"), action_name="win.open-folder")
        folder.add_css_class("pill")
        again = Gtk.Button(label=_("new_dubbing"), action_name="win.new")
        again.add_css_class("pill")
        for b in (self.play_btn, folder, again):
            buttons.append(b)
        box.append(buttons)
        narrow = Adw.Breakpoint.new(Adw.BreakpointCondition.parse("max-width: 500sp"))
        narrow.add_setter(buttons, "orientation", Gtk.Orientation.VERTICAL)
        self.add_breakpoint(narrow)
        return self._scrolled(box)

    # ── stato ─────────────────────────────────────────────────────────────
    def _set(self, key, value):
        self.cfg[key] = value
        save_settings(self.cfg)

    def _toast(self, text, timeout=5):
        self.toasts.add_toast(Adw.Toast(title=GLib.markup_escape_text(text), timeout=timeout))

    def _outputs(self):
        return {k[4:] for k in ("out_srt", "out_audio", "out_video") if self.cfg[k]}

    def _missing(self):
        """Il primo problema che impedisce il doppiaggio: (chiave, apre le
        Preferenze?) oppure None."""
        outs = self._outputs()
        if not tts.find_ffmpeg():
            return "err_no_ffmpeg", False
        if not engine.find_binary() or (outs - {"srt"} and not tts.find_binary()):
            return "banner_no_llm_engine", False
        if not self.source_srt and not whisper.find_binary():
            return "banner_no_whisper_engine", False
        if not self.source_srt and not self.cfg["whisper_model"]:
            return "banner_no_whisper_model", True
        if not self.cfg["llm_model"]:
            return "banner_no_llm_model", True
        if outs - {"srt"} and not self._voice():
            return "banner_no_voice_model", True
        return None

    def _voice(self):
        for v in self.voices:
            if v.model == self.cfg["voice_model"]:
                return v
        return None

    def _refresh_banner(self):
        missing = self._missing()
        b = self.banner
        if missing:
            key, prefs = missing
            b.set_title(_(key))
            b.set_button_label(_("preferences").rstrip("…") if prefs else None)
            b.set_revealed(True)
        else:
            b.set_revealed(False)
        self._refresh_actions()

    def _refresh_saved_row(self):
        transcript, langs = dub.project_summary(self.media) if self.media else (False, [])
        if not transcript and not langs:
            self.saved_row.set_visible(False)
            return
        parts = []
        if transcript:
            parts.append(_("saved_transcript"))
        if langs:
            parts.append(_("saved_translations", langs=", ".join(language_name(c) for c in langs)))
        self.saved_row.set_subtitle(GLib.markup_escape_text("; ".join(parts)))
        self.saved_row.set_visible(True)

    def _save_glossary(self, text, quiet=False):
        if self.media is None or self._updating:
            return
        project = dub.load_project(self.media)
        if (project.get("glossary") or "") == text:
            return
        project["glossary"] = text
        dub.save_project(self.media, project)
        if not quiet:
            self._toast(_("glossary_saved"))

    def _forget(self):
        if self.media:
            glossary = self.glossary_row.get_text()
            dub.forget_project(self.media)
            if glossary:
                # Il glossario è una scelta dell'utente: resta.
                dub.save_project(self.media, {"glossary": glossary})
            self._refresh_saved_row()
            self._toast(_("saved_forgotten"))

    def _refresh_voice_row(self):
        path = self.cfg["speaker_file"]
        if path and os.path.isfile(path):
            name = os.path.splitext(os.path.basename(path))[0]
        else:
            name = _("speaker_none")
        self.voice_row.set_subtitle(GLib.markup_escape_text(name))

    def _refresh_actions(self):
        self._refresh_voice_row()
        busy = self.finder is not None
        self.find_btn.set_sensitive(self.media is not None and not self.dubbing.running
                                    and not busy and self._voice() is not None
                                    and bool(self.info and self.info["audio"]))
        running = self.dubbing.running or busy
        ready = self.media is not None and self._missing() is None and bool(self._outputs())
        self.lookup_action("dub").set_enabled(ready and not running)
        self.lookup_action("preview").set_enabled(ready and not running
                                                  and bool(self._outputs() - {"srt"}))
        self.lookup_action("stop").set_enabled(self.dubbing.running)
        self.lookup_action("open").set_enabled(not running)
        self.lookup_action("new").set_enabled(not running)
        self.lookup_action("open-result").set_enabled(bool(self.files) and not running)
        self.lookup_action("open-folder").set_enabled(bool(self.files) and not running)

    # ── modelli ───────────────────────────────────────────────────────────
    def _refresh_models(self):
        self.whisper_models = whisper.find_models()
        self.llm_models = engine.find_models()
        self.voices = tts.find_voices()
        siblings = sibling_settings()
        for key, paths in (("whisper_model", self.whisper_models),
                           ("llm_model", self.llm_models),
                           ("voice_model", [v.model for v in self.voices])):
            # Il file salvato; se non c'è più, quello scelto nell'altra app.
            chosen = pick(self.cfg[key] if self.cfg[key] in paths else siblings.get(key, ""),
                          paths)
            if chosen != self.cfg[key]:
                self._set(key, chosen)
        if not self.cfg["speaker_file"]:
            # Una voce uguale per tutte le battute: quella scelta in
            # RuscaNarrator, o la prima creata con RuscaNarrator.
            theirs = siblings.get("speaker_file", "")
            saved = tts.find_voice_files()
            if theirs and os.path.isfile(theirs):
                self._set("speaker_file", theirs)
            elif saved:
                self._set("speaker_file", saved[0][1])
        self._refresh_banner()

    # ── video ─────────────────────────────────────────────────────────────
    def open_file(self):
        if self.dubbing.running:
            return
        dialog = Gtk.FileDialog(title=_("choose_video"), modal=True)
        filters = Gio.ListStore.new(Gtk.FileFilter)
        videos = Gtk.FileFilter(name=_("filter_video"))
        videos.add_mime_type("video/*")
        for ext in VIDEO_PATTERNS:
            videos.add_suffix(ext)
        filters.append(videos)
        everything = Gtk.FileFilter(name=_("filter_all"))
        everything.add_pattern("*")
        filters.append(everything)
        dialog.set_filters(filters)
        dialog.set_default_filter(videos)

        def done(d, result):
            try:
                f = d.open_finish(result)
            except GLib.Error:
                return
            if f and f.get_path():
                self.open_path(f.get_path())
        dialog.open(self, None, done)

    def _dropped(self, f):
        if f.get_path() and not self.dubbing.running:
            self.open_path(f.get_path())
            return True
        return False

    def open_path(self, path):
        if self.dubbing.running:
            return
        if path.lower().endswith(".srt"):
            if self.media is None:
                self._toast(_("srt_needs_video"))
            else:
                self._set_source_srt(path)
            return
        try:
            info = dub.probe(path)
        except dub.DubbingError as e:
            self._show_error(_("open_error"), e.detail or _(e.key))
            return
        if not info["video"]:
            self._show_error(_("err_not_video"), os.path.basename(path))
            return
        self.media, self.info = path, info
        self.files = {}
        self._set_source_srt("")
        name = os.path.basename(path)
        self.video_row.set_title(GLib.markup_escape_text(name))
        parts = [duration_text(info["duration_ms"])]
        parts.append(_("audio_tracks", n=info["audio"]) if info["audio"] else _("no_audio"))
        if info["subtitle"]:
            parts.append(_("subtitle_tracks", n=info["subtitle"]))
        self.video_row.set_subtitle(" · ".join(parts))
        self._refresh_folder()
        self._refresh_saved_row()
        self._updating = True
        self.glossary_row.set_text(dub.load_project(path).get("glossary") or "")
        self._updating = False
        self.stack.set_visible_child_name("setup")
        self._refresh_banner()

    def _set_source_srt(self, path):
        self.source_srt = path
        self.srt_row.set_subtitle(GLib.markup_escape_text(os.path.basename(path)) if path
                                  else _("source_subtitles_auto"))
        self.srt_clear.set_visible(bool(path))
        self.src_row.set_subtitle(_("source_language_srt") if path else _("source_language_sub"))
        self._refresh_banner()

    def _choose_srt(self):
        dialog = Gtk.FileDialog(title=_("srt_choose"), modal=True)
        filters = Gio.ListStore.new(Gtk.FileFilter)
        srt = Gtk.FileFilter(name=_("filter_srt"))
        srt.add_suffix("srt")
        srt.add_mime_type("application/x-subrip")
        filters.append(srt)
        dialog.set_filters(filters)
        if self.media:
            dialog.set_initial_folder(Gio.File.new_for_path(os.path.dirname(self.media)))

        def done(d, result):
            try:
                f = d.open_finish(result)
            except GLib.Error:
                return
            if f and f.get_path():
                self._set_source_srt(f.get_path())
        dialog.open(self, None, done)

    def _refresh_folder(self):
        folder = self.cfg["folder"]
        if folder and not os.path.isdir(folder):
            folder = ""
            self._set("folder", "")
        self.folder_row.set_subtitle(GLib.markup_escape_text(folder) if folder
                                     else _("folder_next_to_video"))
        self.folder_reset.set_visible(bool(folder))

    def _choose_folder(self):
        dialog = Gtk.FileDialog(title=_("folder_choose"), modal=True)

        def done(d, result):
            try:
                f = d.select_folder_finish(result)
            except GLib.Error:
                return
            if f and f.get_path():
                self._set("folder", f.get_path())
                self._refresh_folder()
        dialog.select_folder(self, None, done)

    # ── doppiaggio ────────────────────────────────────────────────────────
    def start(self, preview=False):
        if self.media is None or self.dubbing.running:
            return
        cfg = self.cfg
        src = cfg["src"]
        if not self.info["audio"] and not self.source_srt:
            self._show_error(_("err_no_audio_srt"), _("err_no_audio_srt_body"))
            return
        if self.source_srt and src == "auto":
            self._show_error(_("err_srt_language"), _("err_srt_language_body"))
            return
        if src == cfg["tgt"] and not self.source_srt:
            # Ridoppiare nella stessa lingua si può (voce nuova), ma è raro.
            self._toast(_("same_language"))
        voice = self._voice()
        o = dub.Options(
            media=self.media, folder=cfg["folder"], src=src, tgt=cfg["tgt"],
            whisper_model=cfg["whisper_model"], llm_model=cfg["llm_model"], voice=voice,
            speaker_file=cfg["speaker_file"] if os.path.isfile(cfg["speaker_file"]) else "",
            voice_name=cfg["voice_name"], gpu=cfg["gpu"], whisper_device=cfg["whisper_device"],
            llm_device=cfg["llm_device"], tts_device=cfg["tts_device"],
            threads=cfg["threads"], context=cfg["context"], max_speed=cfg["max_speed"],
            seed=cfg["seed"], ducking=cfg["ducking"], outputs=self._outputs(), fmt=cfg["fmt"],
            titles=(language_name(src) if src != "auto" else "", dub.NATIVE[cfg["tgt"]]),
            source_srt=self.source_srt, reuse=True, preview=preview,
            gender=cfg["speaker_gender"], glossary=self.glossary_row.get_text())
        self.log_lines.clear()
        self.files = {}
        for stage in dub.STAGES:
            self._stage_state(stage, "pending")
        if not (self._outputs() - {"srt"}):
            for stage in ("dub", "mix"):
                self._stage_state(stage, "skip")
        self.work_title.set_label(_("working_preview" if preview else "working_title",
                                    name=os.path.basename(self.media)))
        self.progress.set_fraction(0)
        self.progress.set_text("")
        try:
            self.dubbing.start(o)
        except dub.DubbingError as e:
            self._show_error(_(e.key), e.detail)
            return
        if not self.dubbing.running:            # finito subito (errore già mostrato)
            return
        self._started = time.monotonic()
        self._clock = GLib.timeout_add_seconds(1, self._tick)
        self._tick()
        self.stack.set_visible_child_name("work")
        self._refresh_actions()

    def stop(self):
        if self.dubbing.running:
            self.dubbing.cancel()

    def _tick(self):
        self.clock_label.set_label(_("elapsed", time=duration_text(
            (time.monotonic() - self._started) * 1000)))
        return True

    def _stage_state(self, stage, state, detail=""):
        row, icon, spinner = self.stage_rows[stage]
        spinner.set_visible(state == "running")
        icon.set_visible(state != "running")
        icon.set_from_icon_name({"done": "object-select-symbolic",
                                 "skip": "action-unavailable-symbolic",
                                 "error": "dialog-error-symbolic"}.get(state,
                                                                       "content-loading-symbolic"))
        if state in ("done", "running"):
            icon.remove_css_class("dim-label")
        else:
            icon.add_css_class("dim-label")
        row.set_subtitle(GLib.markup_escape_text(detail) if detail else _(f"stage_{stage}_sub"))
        row.set_sensitive(state != "skip")
        self.stage_rows[stage] = (row, icon, spinner)
        row._state = state

    def _on_stage(self, stage, fraction=0.0, detail=""):
        if not self.dubbing.running:
            return
        order = dub.STAGES.index(stage)
        for earlier in dub.STAGES[:order]:
            if getattr(self.stage_rows[earlier][0], "_state", "") in ("pending", "running"):
                self._stage_state(earlier, "done")
        text = ""
        if stage == "transcribe" and fraction >= 1.0 and detail:
            text = _("detected_language", language=language_name(detail))
        elif stage == "translate" and detail == "brief":
            text = _("stage_brief")
        elif stage == "transcribe" and detail == "preview":
            text = _("stage_preview")
        elif stage == "transcribe" and detail == "audio":
            text = _("stage_audio")
        elif stage == "transcribe" and detail == "model":
            text = _("stage_model")
        elif stage in ("translate", "dub") and "/" in detail:
            i, n = detail.split("/")
            text = _("cue_progress", i=i, n=n)
        elif stage == "dub" and detail == "refit":
            text = _("stage_refit")
        elif stage == "dub" and detail == "normalize":
            text = _("stage_normalize")
        elif stage == "dub" and detail == "assemble":
            text = _("stage_assemble")
        self._stage_state(stage, "running", text)
        # Avanzamento complessivo: i passi pesano diversamente.
        weights = {"transcribe": .25, "translate": .2, "dub": .45, "mix": .1}
        if not (self._outputs() - {"srt"}):
            weights = {"transcribe": .55, "translate": .45, "dub": 0, "mix": 0}
        done = sum(weights[s] for s in dub.STAGES[:order])
        total = done + weights[stage] * max(0.0, min(1.0, fraction))
        self.progress.set_fraction(total)
        self.progress.set_text(f"{int(total * 100)} %")

    def _on_log(self, line):
        self.log_lines.append(line)
        if len(self.log_lines) > 4000:
            del self.log_lines[:1000]

    def _on_done(self, error, files, stats):
        if self._clock:
            GLib.source_remove(self._clock)
            self._clock = 0
        self.files = files
        self._refresh_actions()
        if error == "cancelled":
            self.stack.set_visible_child_name("setup")
            self._toast(_("stopped"))
            self._refresh_banner()
            return
        if error is not None:
            for stage in dub.STAGES:
                if getattr(self.stage_rows[stage][0], "_state", "") == "running":
                    self._stage_state(stage, "error")
            self.stack.set_visible_child_name("setup")
            self._refresh_banner()
            body = _(error.key)
            if error.detail:
                body += "\n\n" + error.detail
            if files:
                body += "\n\n" + _("partial_files", n=len(files))
            self._show_error(_("dub_failed"), body, log=True)
            return
        self._show_result(files, stats)

    def _show_result(self, files, stats):
        self._refresh_saved_row()
        elapsed = duration_text((time.monotonic() - self._started) * 1000)
        lines = [_("done_desc", n=stats.get("cues", 0), time=elapsed)]
        if stats.get("faster") or stats.get("late"):
            lines.append(_("done_timing", faster=stats.get("faster", 0),
                           late=stats.get("late", 0)))
        if stats.get("refit"):
            lines.append(_("done_refit", n=stats["refit"]))
        if stats.get("kept"):
            lines.append(_("done_kept", n=stats["kept"]))
        if stats.get("reused_transcript") and stats.get("reused") == stats.get("blocks"):
            lines.append(_("done_reused_all"))
        elif stats.get("reused_transcript") or stats.get("reused"):
            lines.append(_("done_reused_some"))
        if stats.get("fast_subtitles"):
            lines.append(_("done_fast", n=stats["fast_subtitles"]))
        self.done_status.set_description("\n".join(lines))
        for row in self._file_rows:
            self.files_group.remove(row)
        self._file_rows = []
        for key in ("video", "audio", "srt_tgt", "srt_src", "srt_both"):
            path = files.get(key)
            if not path:
                continue
            row = Adw.ActionRow(title=GLib.markup_escape_text(os.path.basename(path)),
                                subtitle=_(f"file_{key}"), activatable=True)
            row.add_suffix(Gtk.Image(icon_name="adw-external-link-symbolic"))
            row.connect("activated", lambda _r, p=path: self._launch(p))
            self.files_group.add(row)
            self._file_rows.append(row)
        self.play_btn.set_visible(bool(files.get("video") or files.get("audio")))
        self.stack.set_visible_child_name("done")

    def _launch(self, path):
        Gtk.FileLauncher.new(Gio.File.new_for_path(path)).launch(self, None, None)

    def open_result(self):
        path = self.files.get("video") or self.files.get("audio")
        if path:
            self._launch(path)

    def open_folder(self):
        path = next(iter(self.files.values()), None)
        if path:
            Gtk.FileLauncher.new(Gio.File.new_for_path(path)).open_containing_folder(
                self, None, None)

    def new_dubbing(self):
        if self.dubbing.running:
            return
        self.files = {}
        self.stack.set_visible_child_name("setup" if self.media else "empty")
        self._refresh_actions()

    # ── voce simile ───────────────────────────────────────────────────────
    def find_voice(self):
        if self.media is None or self.dubbing.running or self.finder is not None:
            return
        voice = self._voice()
        if voice is None:
            self.show_preferences()
            return
        cues = []
        if self.source_srt:
            try:
                with open(self.source_srt, encoding="utf-8-sig", errors="replace") as f:
                    cues = dub.cues_from_srt(f.read())
            except OSError:
                cues = []
        elif self.dubbing.cues and self.dubbing.o and self.dubbing.o.media == self.media:
            cues = list(self.dubbing.cues)        # le battute dell'ultimo doppiaggio
        self.finder = VoiceFinder(self, voice, cues)
        self.finder.connect("closed", self._finder_closed)
        self._refresh_actions()
        self.finder.present(self)
        self.finder.begin()

    def _finder_closed(self, finder):
        finder.shutdown()
        self.finder = None
        self._refresh_actions()

    def use_voice(self, path):
        """La voce trovata diventa quella di riferimento."""
        self._set("speaker_file", path)
        self._refresh_actions()
        self._toast(_("voice_saved", name=os.path.splitext(os.path.basename(path))[0]))

    # ── preferenze ────────────────────────────────────────────────────────
    def show_preferences(self):
        self._refresh_models()
        page = Adw.PreferencesPage()
        look = Adw.PreferencesGroup(title=_("group_look"))
        theme_row = Adw.ComboRow(title=_("theme"), model=Gtk.StringList.new(
            [_(f"theme_{t}") for t in THEMES]))
        theme = self.cfg.get("theme", "system")
        theme_row.set_selected(THEMES.index(theme) if theme in THEMES else 0)
        theme_row.connect("notify::selected", self._on_theme)
        look.add(theme_row)
        page.add(look)

        models = Adw.PreferencesGroup(title=_("group_models"), description=_("models_hint"))
        for key, paths, folder in (
                ("whisper_model", self.whisper_models, whisper.USER_MODEL_DIR),
                ("llm_model", self.llm_models, engine.MODEL_DIRS[-1]),
                ("voice_model", [v.model for v in self.voices], tts.USER_MODEL_DIR)):
            row = Adw.ComboRow(title=_(key))
            row.set_model(Gtk.StringList.new([os.path.basename(p) for p in paths]
                                             or [_("no_model")]))
            row.set_sensitive(bool(paths))
            if self.cfg[key] in paths:
                row.set_selected(paths.index(self.cfg[key]))
            row.set_subtitle(GLib.markup_escape_text(folder))
            row.connect("notify::selected", lambda r, _p, k=key, ps=list(paths): (
                0 <= r.get_selected() < len(ps) and self._set(k, ps[r.get_selected()]),
                self._refresh_banner()))
            open_dir = Gtk.Button(icon_name="folder-open-symbolic", valign=Gtk.Align.CENTER,
                                  tooltip_text=_("open_models_folder"))
            open_dir.add_css_class("flat")
            open_dir.update_property([Gtk.AccessibleProperty.LABEL], [_("open_models_folder")])
            open_dir.connect("clicked", lambda _b, d=folder: self._open_dir(d))
            row.add_suffix(open_dir)
            models.add(row)
        page.add(models)

        voice = Adw.PreferencesGroup(title=_("group_voice"), description=_("voice_hint"))
        names, paths = [_("speaker_none")], [""]
        for name, path in tts.find_voice_files():
            names.append(name)
            paths.append(path)
        saved = self.cfg["speaker_file"]
        if saved and saved not in paths:
            names.append(os.path.basename(saved))
            paths.append(saved)
        speaker = Adw.ComboRow(title=_("speaker_file"), model=Gtk.StringList.new(names))
        speaker.set_selected(paths.index(saved) if saved in paths else 0)
        speaker.connect("notify::selected", lambda r, _p: self._set(
            "speaker_file", paths[r.get_selected()]))
        choose = Gtk.Button(icon_name="document-open-symbolic", valign=Gtk.Align.CENTER,
                            tooltip_text=_("speaker_choose"))
        choose.add_css_class("flat")
        choose.update_property([Gtk.AccessibleProperty.LABEL], [_("speaker_choose")])
        choose.connect("clicked", lambda _b: self._choose_speaker(speaker, names, paths))
        speaker.add_suffix(choose)
        voice.add(speaker)
        name = Adw.EntryRow(title=_("voice_name"), text=self.cfg["voice_name"])
        name.connect("changed", lambda r: self._set("voice_name", r.get_text()))
        voice.add(name)
        speed = Adw.SpinRow.new_with_range(1.0, 2.0, 0.05)
        speed.set_digits(2)
        speed.set_title(_("max_speed"))
        speed.set_subtitle(_("max_speed_sub"))
        speed.set_value(self.cfg["max_speed"])
        speed.connect("notify::value", lambda r, _p: self._set("max_speed", round(r.get_value(), 2)))
        voice.add(speed)
        seed = Adw.SpinRow.new_with_range(0, 2 ** 31 - 1, 1)
        seed.set_title(_("seed"))
        seed.set_subtitle(_("seed_sub"))
        seed.set_value(self.cfg["seed"])
        seed.connect("notify::value", lambda r, _p: self._set("seed", int(r.get_value())))
        voice.add(seed)
        page.add(voice)

        eng = Adw.PreferencesGroup(title=_("group_engine"))
        gpu = Adw.SwitchRow(title=_("gpu"), subtitle=_("gpu_sub"), active=self.cfg["gpu"])
        eng.add(gpu)
        # Una scheda per passo: i modelli lavorano uno dopo l'altro, ma su
        # due schede il modello linguistico grande e la voce trovano ognuno
        # tutta la memoria della sua.
        self.device_rows = {}
        for key in DEVICE_KEYS:
            row = Adw.ComboRow(title=_(key), subtitle=_(f"{key}_sub"), sensitive=self.cfg["gpu"])
            row.connect("notify::selected", self._on_device, key)
            self.device_rows[key] = row
            eng.add(row)
        gpu.connect("notify::active", self._on_gpu)
        self._fill_device_row()
        self._load_devices()
        threads = Adw.SpinRow.new_with_range(1, max(1, os.cpu_count() or 1), 1)
        threads.set_title(_("threads"))
        threads.set_subtitle(_("threads_sub", n=tts.physical_cores()))
        threads.set_value(min(self.cfg["threads"], os.cpu_count() or 1))
        threads.connect("notify::value", lambda r, _p: self._set("threads", int(r.get_value())))
        eng.add(threads)
        context = Adw.SpinRow.new_with_range(2048, 131072, 1024)
        context.set_title(_("context"))
        context.set_subtitle(_("context_sub"))
        context.set_value(self.cfg["context"])
        context.connect("notify::value", lambda r, _p: self._set("context", int(r.get_value())))
        eng.add(context)
        page.add(eng)

        dialog = Adw.PreferencesDialog(title=_("preferences").rstrip("…"))
        dialog.add(page)
        dialog.connect("closed", lambda _d: (setattr(self, "device_rows", None),
                                             self._refresh_banner()))
        dialog.present(self)

    def _open_dir(self, folder):
        try:
            os.makedirs(folder, exist_ok=True)
        except OSError as e:
            self._show_error(_("open_error"), str(e))
            return
        Gtk.FileLauncher.new(Gio.File.new_for_path(folder)).launch(self, None, None)

    def _choose_speaker(self, row, names, paths):
        dialog = Gtk.FileDialog(title=_("speaker_choose"), modal=True)
        filters = Gio.ListStore.new(Gtk.FileFilter)
        wav = Gtk.FileFilter(name="WAV")
        wav.add_suffix("wav")
        filters.append(wav)
        dialog.set_filters(filters)

        def done(d, result):
            try:
                f = d.open_finish(result)
            except GLib.Error:
                return
            path = f.get_path() if f else None
            if not path:
                return
            if path not in paths:
                names.append(os.path.basename(path))
                paths.append(path)
                row.set_model(Gtk.StringList.new(names))
            row.set_selected(paths.index(path))
        dialog.open(self, None, done)

    def _on_theme(self, row, _pspec):
        self._set("theme", THEMES[row.get_selected()])
        apply_color_scheme(self.cfg["theme"])

    def _load_devices(self):
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

    def _on_gpu(self, row, _pspec):
        self._set("gpu", row.get_active())
        for r in (getattr(self, "device_rows", None) or {}).values():
            r.set_sensitive(row.get_active())

    def _fill_device_row(self):
        rows = getattr(self, "device_rows", None)
        if not rows:
            return
        labels = [desc for _n, desc, _mib in self.devices]
        items = [_("gpu_device_auto")] + [f"{desc} ({max(1, round(mib / 1024))} GB)"
                                          for _n, desc, mib in self.devices]
        # Una scheda salvata che ora non si vede (spenta, driver) resta nella
        # lista, per non perdere la scelta.
        for key in DEVICE_KEYS:
            saved = self.cfg[key]
            if saved and saved not in labels:
                labels.append(saved)
                items.append(saved)
        self._row_devices = labels
        self._updating = True
        for key, row in rows.items():
            saved = self.cfg[key]
            row.set_model(Gtk.StringList.new(items))
            row.set_selected(labels.index(saved) + 1 if saved in labels else 0)
        self._updating = False

    def _on_device(self, row, _pspec, key):
        if self._updating:
            return
        i = row.get_selected()
        self._set(key, self._row_devices[i - 1] if 0 < i <= len(self._row_devices) else "")

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
                    self._launch(path)
                    return
        self._show_error(_("guide_missing"))

    def show_shortcuts(self):
        group = Adw.PreferencesGroup()
        for title, accel in ((_("open"), "<Control>o"), (_("dub"), "<Control>Return"),
                             (_("stop"), "Escape"), (_("preferences"), "<Control>comma"),
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

    def _show_error(self, heading, detail="", log=False):
        dialog = Adw.AlertDialog(heading=heading, body=detail)
        if log:
            dialog.add_response("log", _("engine_log"))
        dialog.add_response("close", _("close"))
        dialog.set_default_response("close")
        dialog.set_close_response("close")
        dialog.connect("response", lambda _d, r: r == "log" and self.show_log())
        dialog.present(self)

    def _on_close(self, *_a):
        if self.finder is not None:
            self.finder.shutdown()
        if self.dubbing.running and not self._force_close:
            dialog = Adw.AlertDialog(heading=_("discard_title"), body=_("discard_body"))
            dialog.add_response("cancel", _("cancel"))
            dialog.add_response("discard", _("discard"))
            dialog.set_response_appearance("discard", Adw.ResponseAppearance.DESTRUCTIVE)
            dialog.set_default_response("cancel")
            dialog.set_close_response("cancel")

            def answered(_d, response):
                if response == "discard":
                    self._force_close = True
                    self.close()
            dialog.connect("response", answered)
            dialog.present(self)
            return True
        self.dubbing.shutdown()
        w, h = self.get_default_size()
        self.cfg.update(width=w, height=h, maximized=self.is_maximized())
        save_settings(self.cfg)
        return False


class VoiceFinder(Adw.Dialog):
    """«Trova una voce simile»: ascolta la voce originale, inventa voci
    nella lingua del doppiaggio e le propone dalla più simile. Si ascoltano,
    si confrontano con l'originale, e una si tiene come voce di riferimento."""

    def __init__(self, win, voice, cues):
        super().__init__(title=_("finder_title"), content_width=520, content_height=600)
        self.win = win
        self.voice = voice
        self.cues = cues
        self.media_file = None           # Gtk.MediaFile in riproduzione
        self.playing_btn = None
        self.rows = []
        self.search = match.VoiceSearch(os.path.join(dub.WORK_DIR, "voci"), self._on_stage,
                                        win._on_log, self._on_done)

        self.stack = Gtk.Stack(transition_type=Gtk.StackTransitionType.CROSSFADE)
        # Lavoro in corso
        work = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=18, valign=Gtk.Align.CENTER,
                       margin_start=24, margin_end=24, margin_top=24, margin_bottom=24)
        spinner = (Adw.Spinner() if hasattr(Adw, "Spinner") else Gtk.Spinner(spinning=True))
        spinner.set_size_request(48, 48)
        spinner.set_halign(Gtk.Align.CENTER)
        work.append(spinner)
        self.work_label = Gtk.Label(wrap=True, justify=Gtk.Justification.CENTER)
        self.work_label.add_css_class("title-4")
        work.append(self.work_label)
        self.work_bar = Gtk.ProgressBar()
        work.append(self.work_bar)
        hint = Gtk.Label(label=_("finder_hint"), wrap=True, justify=Gtk.Justification.CENTER)
        hint.add_css_class("dim-label")
        work.append(hint)
        stop = Gtk.Button(label=_("stop"), halign=Gtk.Align.CENTER)
        stop.add_css_class("pill")
        stop.connect("clicked", lambda _b: self.search.cancel())
        work.append(stop)
        self.stack.add_named(work, "work")

        # Risultati
        page = Adw.PreferencesPage()
        self.orig_group = Adw.PreferencesGroup(title=_("finder_original"))
        self.orig_row = Adw.ActionRow(title=_("finder_original_row"))
        self.orig_row.add_prefix(self._play_button(lambda: self.search.reference
                                                   and self.search.reference[0]))
        self.orig_group.add(self.orig_row)
        page.add(self.orig_group)
        self.list_group = Adw.PreferencesGroup(title=_("finder_voices"),
                                               description=_("finder_voices_desc"))
        page.add(self.list_group)
        more_group = Adw.PreferencesGroup()
        more = Gtk.Button(label=_("finder_more"), halign=Gtk.Align.CENTER)
        more.add_css_class("pill")
        more.connect("clicked", lambda _b: self._more())
        more_group.add(more)
        page.add(more_group)
        self.stack.add_named(page, "list")

        view = Adw.ToolbarView(content=self.stack)
        view.add_top_bar(Adw.HeaderBar())
        self.toasts = Adw.ToastOverlay(child=view)
        self.set_child(self.toasts)

    # ── ricerca ───────────────────────────────────────────────────────────
    def begin(self):
        w = self.win
        cfg = w.cfg
        self.work_label.set_label(_("finder_listen"))
        self.work_bar.set_fraction(0)
        self.stack.set_visible_child_name("work")
        try:
            self.search.start(w.media, w.info["duration_ms"], self.cues, self.voice, cfg["tgt"],
                              cfg["gpu"], cfg["tts_device"], cfg["threads"])
        except match.MatchError as e:
            self._fail(e)

    def _more(self):
        self._stop_playing()
        self.work_label.set_label(_("finder_voice", i=1, n=match.CANDIDATES))
        self.work_bar.set_fraction(0)
        self.stack.set_visible_child_name("work")
        try:
            self.search.more()
        except match.MatchError as e:
            self._fail(e)

    def _on_stage(self, stage, i=0, n=0):
        if stage == "listen":
            self.work_label.set_label(_("finder_listen"))
            self.work_bar.pulse()
        elif stage == "voice":
            self.work_label.set_label(_("finder_voice", i=i, n=n))
            self.work_bar.set_fraction((i - 1) / max(1, n))

    def _on_done(self, error, reference, candidates):
        if error == "cancelled":
            self.close()
            return
        if error is not None:
            self._fail(error)
            return
        self._show(reference, candidates)

    def _fail(self, error):
        body = _(error.key)
        if error.detail:
            body += "\n\n" + error.detail
        dialog = Adw.AlertDialog(heading=_("finder_failed"), body=body)
        dialog.add_response("close", _("close"))
        dialog.connect("response", lambda *_a: self.close())
        dialog.present(self)

    def _show(self, reference, candidates):
        _wav, ref = reference
        self.orig_row.set_subtitle(self._portrait(ref))
        for row in self.rows:
            self.list_group.remove(row)
        self.rows = []
        for n, cand in enumerate(candidates[:match.SHOWN], 1):
            row = Adw.ActionRow(title=_("finder_voice_row", n=n,
                                         percent=match.similarity(cand.distance)),
                                subtitle=self._difference(ref, cand.profile))
            row.add_prefix(self._play_button(lambda p=cand.path: p))
            use = Gtk.Button(label=_("finder_use"), valign=Gtk.Align.CENTER)
            use.add_css_class("suggested-action" if n == 1 else "flat")
            use.connect("clicked", lambda _b, c=cand: self._use(c))
            row.add_suffix(use)
            self.list_group.add(row)
            self.rows.append(row)
        self.stack.set_visible_child_name("list")

    def _portrait(self, p):
        hz = match.semitones_to_hz(p.pitch)
        register = (_("reg_very_low") if hz < 100 else _("reg_low") if hz < 140 else
                    _("reg_mid") if hz < 185 else _("reg_high") if hz < 240 else _("reg_very_high"))
        expressive = _("expr_flat") if p.spread < 2.0 else (
            _("expr_lively") if p.spread > 4.5 else _("expr_normal"))
        return _("finder_portrait", register=register, hz=int(round(hz)), expressive=expressive)

    def _difference(self, ref, other):
        parts = [_(f"diff_{k}") for k in match.describe(ref, other) if k]
        return ", ".join(parts) if parts else _("diff_none")

    # ── ascolto ───────────────────────────────────────────────────────────
    def _play_button(self, path_getter):
        btn = Gtk.Button(icon_name="media-playback-start-symbolic", valign=Gtk.Align.CENTER,
                         tooltip_text=_("finder_play"))
        btn.add_css_class("circular")
        btn.update_property([Gtk.AccessibleProperty.LABEL], [_("finder_play")])
        btn.connect("clicked", lambda b: self._toggle(b, path_getter()))
        return btn

    def _toggle(self, btn, path):
        was = self.playing_btn
        self._stop_playing()
        if was is btn or not path or not os.path.isfile(path):
            return
        self.media_file = Gtk.MediaFile.new_for_filename(path)
        self.media_file.connect("notify::ended", lambda m, _p: m.get_ended() and self._stop_playing())
        self.media_file.play()
        self.playing_btn = btn
        btn.set_icon_name("media-playback-stop-symbolic")
        btn.set_tooltip_text(_("finder_stop_play"))

    def _stop_playing(self):
        if self.media_file is not None:
            self.media_file.pause()
            self.media_file = None
        if self.playing_btn is not None:
            self.playing_btn.set_icon_name("media-playback-start-symbolic")
            self.playing_btn.set_tooltip_text(_("finder_play"))
            self.playing_btn = None
        return False

    # ── scelta ────────────────────────────────────────────────────────────
    def _use(self, cand):
        self._stop_playing()
        stem = os.path.splitext(os.path.basename(self.win.media))[0]
        entry = Gtk.Entry(text=_("finder_default_name", video=stem[:40].strip()),
                          activates_default=True)
        dialog = Adw.AlertDialog(heading=_("finder_name_title"), body=_("finder_name_body"),
                                 extra_child=entry)
        dialog.add_response("cancel", _("cancel"))
        dialog.add_response("save", _("finder_use"))
        dialog.set_response_appearance("save", Adw.ResponseAppearance.SUGGESTED)
        dialog.set_default_response("save")
        dialog.set_close_response("cancel")

        def answered(_d, response):
            if response != "save":
                return
            try:
                path = tts.save_voice(cand.path, entry.get_text().strip() or "Voce")
            except OSError as e:
                self.toasts.add_toast(Adw.Toast(title=GLib.markup_escape_text(str(e))))
                return
            self.win.use_voice(path)
            self.close()
        dialog.connect("response", answered)
        dialog.present(self)

    def shutdown(self):
        """Ferma la ricerca e cancella l'audio originale e le voci di prova
        (quella tenuta è già stata copiata fra le voci)."""
        self._stop_playing()
        self.search.discard()


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
                               ("win.open", ["<Control>o"]), ("win.dub", ["<Control>Return"]),
                               ("win.stop", ["Escape"]),
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
        if files and files[0].get_path():
            self.props.active_window.open_path(files[0].get_path())


def main():
    GLib.set_prgname(APP_ID)
    GLib.set_application_name(APP_NAME)
    return DubbingApp().run(sys.argv)


if __name__ == "__main__":
    sys.exit(main())
