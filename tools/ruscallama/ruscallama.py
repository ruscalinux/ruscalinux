#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
RuscaLLama 1.99.2 — chat con modelli linguistici locali per RuscaLinux.

Usa ruscallama-engine (llama.cpp, software esterno con licenza MIT) per
eseguire modelli GGUF sul computer dell'utente. Nessun dato lascia la
macchina: il motore ascolta solo su 127.0.0.1 con una chiave temporanea.

Copyright (C) 2026 Nunzio Curcuruto — https://www.ruscalinux.org
Licenza: GNU GPL 3.0 o successiva.

Requisiti: Python 3.10+, PyGObject, GTK 4.18+, libadwaita 1.7+,
GtkSourceView 5, ruscallama-engine.
"""
import base64
import html
import json
import os
import re
import sys
import threading
import time

import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gdk, Gio, GLib, GObject, Gtk, Pango  # noqa: E402
try:                      # evidenziazione del codice; senza, testo semplice
    gi.require_version("GtkSource", "5")
    from gi.repository import GtkSource
except (ValueError, ImportError):
    GtkSource = None

BASE_DIR = os.path.dirname(os.path.realpath(__file__))
sys.path.insert(0, BASE_DIR)
import rusca_engine as engine  # noqa: E402
import rusca_markdown as md  # noqa: E402

_RE_LINK_TAG = re.compile(r"</?a\b[^>]*>")

APP_ID = "org.ruscalinux.RuscaLLama"
APP_NAME = "RuscaLLama"
APP_VERSION = "1.99.2"
STYLE_SRC = os.path.join(BASE_DIR, "style.css")
ICON_SRC = os.path.join(BASE_DIR, "ruscallama.svg")
LANG_DIR = os.path.join(BASE_DIR, "lang")
CONFIG_DIR = os.path.join(GLib.get_user_config_dir(), "ruscallama")
CONFIG_FILE = os.path.join(CONFIG_DIR, "settings.json")
USER_MODELS = os.path.join(GLib.get_user_data_dir(), "ruscallama", "models")
COMPONENTS = (("llama.cpp", "MIT — The ggml authors",
               "https://github.com/ggml-org/llama.cpp"),)

MAX_TOKENS = 4096
MAX_TEXT_ATTACHMENT = 512 * 1024         # 512 KB di testo per allegato
MAX_IMAGE_ATTACHMENT = 8 * 1024 * 1024   # 8 MB per immagine
TEXT_TYPES = (".md", ".markdown", ".txt", ".py", ".sh", ".json", ".csv",
              ".html", ".css", ".js", ".c", ".h", ".cpp", ".rs", ".go")
IMAGE_TYPES = {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
               ".webp": "image/webp", ".gif": "image/gif", ".bmp": "image/bmp"}
CODE_EXT = {"python": ".py", "py": ".py", "bash": ".sh", "sh": ".sh",
            "shell": ".sh", "markdown": ".md", "md": ".md", "c": ".c",
            "cpp": ".cpp", "c++": ".cpp", "javascript": ".js", "js": ".js",
            "html": ".html", "css": ".css", "json": ".json", "sql": ".sql",
            "rust": ".rs", "go": ".go", "yaml": ".yaml", "toml": ".toml"}

# Stili di risposta: valori di campionamento collaudati, nominati per lo
# scopo invece che per un modello preciso. "custom" sblocca i parametri.
PRESETS = {
    "precise":  dict(temperature=0.2, top_p=0.92, top_k=40, min_p=0.08,
                     presence_penalty=0.0, repeat_penalty=1.08),
    "balanced": dict(temperature=0.7, top_p=0.80, top_k=20, min_p=0.0,
                     presence_penalty=0.0, repeat_penalty=1.0),
    "thinking": dict(temperature=1.0, top_p=0.95, top_k=20, min_p=0.0,
                     presence_penalty=0.0, repeat_penalty=1.0),
    "creative": dict(temperature=0.9, top_p=0.95, top_k=40, min_p=0.05,
                     presence_penalty=0.3, repeat_penalty=1.05),
    "custom": None,
}
PRESET_ORDER = ("precise", "balanced", "thinking", "creative", "custom")
CONTEXTS = (4096, 8192, 16384, 32768, 65536, 131072)
KV_MODES = ("f16", "q8_0", "q4_0")
FLASH_MODES = ("auto", "on", "off")
EFFORTS = ("low", "medium", "high")
DEFAULTS = {
    "model": "", "gpu": True, "gpu_device": "", "threads": engine.physical_cores(),
    "context": 8192, "kv": "q8_0", "flash": "auto", "vision": True,
    "speculative": False, "reasoning": False, "effort": "low",
    "preset": "balanced", "sampling": dict(PRESETS["balanced"]), "seed": -1,
    "system": "", "font_size": 0, "width": 1100, "height": 780, "maximized": False,
    "sidebar": True, "theme": "system",
}
THEMES = ("system", "light", "dark")         # ordine delle voci nel menu


def apply_color_scheme(theme):
    """Tema chiaro/scuro: segue GNOME (predefinito) o è scelto dall'utente."""
    Adw.StyleManager.get_default().set_color_scheme({
        "light": Adw.ColorScheme.FORCE_LIGHT,
        "dark": Adw.ColorScheme.FORCE_DARK,
    }.get(theme, Adw.ColorScheme.DEFAULT))


# ── Traduzioni (lang/xx.json, ripiego en.json, specifiche sezione 9) ─────────
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
    """Avvio dai sorgenti: copia l'icona nel tema hicolor dell'utente."""
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
    cfg = json.loads(json.dumps(DEFAULTS))
    try:
        with open(CONFIG_FILE, encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, dict):
            for k, v in data.items():
                if k in cfg and isinstance(v, type(cfg[k])):
                    cfg[k] = v
    except (OSError, ValueError):
        pass
    if cfg["preset"] not in PRESETS:
        cfg["preset"] = "balanced"
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


def split_code(text):
    """Divide una risposta in parti di testo e blocchi ```lingua ... ```."""
    parts = []
    for chunk in re.split(r"(```[^\n`]*\n.*?```)", text, flags=re.S):
        if chunk.startswith("```") and chunk.endswith("```"):
            first, _sep, rest = chunk[3:-3].partition("\n")
            parts.append(("code", first.strip().lower(), rest.rstrip("\n")))
        elif chunk.strip():
            parts.append(("text", "", chunk.strip("\n")))
    return parts


def strip_think(text):
    """Toglie i blocchi <think> dei modelli che non usano reasoning_content."""
    think = "\n".join(m.strip() for m in re.findall(r"<think>(.*?)</think>", text, re.S))
    text = re.sub(r"<think>.*?</think>", "", text, flags=re.S)
    text = re.sub(r"<think>.*\Z", "", text, flags=re.S)
    return text.strip(), think


def text_of(content):
    if isinstance(content, str):
        return content
    return "\n".join(p.get("text", "") if p.get("type") == "text"
                     else f"[{p.get('name', 'image')}]" for p in content)


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


# ── Dimensione del testo (conversazione o documenti) ─────────────────────────
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


def set_source_scheme(buf):
    scheme = GtkSource.StyleSchemeManager.get_default().get_scheme(
        "Adwaita-dark" if Adw.StyleManager.get_default().get_dark() else "Adwaita")
    if scheme:
        buf.set_style_scheme(scheme)


# ── Un messaggio della conversazione ─────────────────────────────────────────
class Message(Gtk.Box):
    """Il testo è formattato mentre arriva: ogni 120 ms si ricompongono solo i
    blocchi cambiati (di solito l'ultimo paragrafo). Paragrafi, codice
    evidenziato, tabelle, formule e linee: vedi rusca_markdown.py."""

    RENDER_MS = 120

    def __init__(self, window, role):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        self.window = window
        self.role = role
        self.text = ""
        self.reasoning = ""
        self.images = []                     # (data_url, nome)
        self.add_css_class("ruscallama-message")
        head = Gtk.Box(spacing=6)
        who = Gtk.Label(label=_("you") if role == "user" else APP_NAME, xalign=0,
                        hexpand=True)
        who.add_css_class("heading")
        head.append(who)
        if role == "assistant":
            self.actions = Gtk.Box(spacing=2, visible=False)
            copy = Gtk.Button(icon_name="edit-copy-symbolic",
                              tooltip_text=_("copy_answer"))
            copy.add_css_class("flat")
            copy.connect("clicked", lambda _b: self.window.copy_text(self.text))
            more = Gtk.MenuButton(icon_name="view-more-symbolic",
                                  tooltip_text=_("more_actions"))
            more.add_css_class("flat")
            menu = Gio.Menu()
            menu.append(_("save_answer_md"), "win.save-answer")
            menu.append(_("save_code_blocks"), "win.save-code")
            more.set_menu_model(menu)
            more.connect("notify::active", self._on_menu)
            for b in (copy, more):
                self.actions.append(b)
            head.append(self.actions)
        self.append(head)
        self.think_expander = None
        self.body = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        self.append(self.body)
        self._shown = []                     # [(blocco, widget)] già visibili
        self._render_id = 0

    def _on_menu(self, button, _pspec):
        if button.get_active():
            self.window.selected_message = self

    @staticmethod
    def _label(text="", markup=True):
        """Testo della conversazione: etichetta selezionabile che va a capo
        (sfondo trasparente, al contrario di un TextView)."""
        label = Gtk.Label(xalign=0, wrap=True, wrap_mode=Pango.WrapMode.WORD_CHAR,
                          selectable=True, use_markup=markup)
        Message._set_label(label, text, markup)
        return label

    @staticmethod
    def _set_label(label, text, markup=True):
        """Markup non valido (tag accavallati, testo a metà durante lo
        streaming) farebbe sparire l'intera etichetta: si mostra il testo.
        I link <a href> li gestisce Gtk.Label e Pango non li conosce: si
        tolgono solo per il controllo."""
        if markup:
            try:
                Pango.parse_markup(_RE_LINK_TAG.sub("", text), -1, "\0")
                label.set_markup(text)
                return
            except GLib.Error:
                text = md.plain_text(text)
        label.set_use_markup(False)
        label.set_text(text)

    def add_stream(self, text):
        self.text += text
        if not self._render_id:
            self._render_id = GLib.timeout_add(self.RENDER_MS, self._render_tick)

    def _render_tick(self):
        self._render_id = 0
        self._render(md.parse_blocks(strip_think(self.text)[0]))
        return False

    def _render(self, blocks):
        """Ricompone solo dal primo blocco cambiato in poi."""
        k = 0
        while k < min(len(blocks), len(self._shown)) and blocks[k] == self._shown[k][0]:
            k += 1
        # Il primo blocco cambiato, se è dello stesso tipo, si aggiorna sul
        # posto invece di ricrearlo: un paragrafo cambia il testo
        # dell'etichetta, un blocco di codice riceve solo il testo nuovo in
        # coda (ricrearlo a ogni aggiornamento lo faceva lampeggiare).
        if k < len(self._shown) and k < len(blocks) and self._update_in_place(k, blocks[k]):
            k += 1
        for _block, widget in self._shown[k:]:
            self.body.remove(widget)
        del self._shown[k:]
        for block in blocks[k:]:
            widget = self._block_widget(block)
            self.body.append(widget)
            self._shown.append((block, widget))

    def _update_in_place(self, k, new):
        old, widget = self._shown[k]
        if new[0] == "text" == old[0]:
            self._set_label(widget, new[1])
        elif new[0] == "code" == old[0] and new[1] == old[1] \
                and getattr(widget, "code_buffer", None) is not None:
            buf = widget.code_buffer
            before, after = old[2].rstrip("\n"), new[2].rstrip("\n")
            if after.startswith(before):
                buf.insert(buf.get_end_iter(), after[len(before):])
            else:
                buf.set_text(after)
        else:
            return False
        self._shown[k] = (new, widget)
        return True

    def _block_widget(self, block):
        kind = block[0]
        if kind == "code":
            return self._code_block(block[1], block[2].rstrip("\n"))
        if kind == "table":
            return self._table(*block[1:])
        if kind == "hr":
            return Gtk.Separator(margin_top=6, margin_bottom=6)
        if kind == "math":
            label = self._label(f'<span size="large">{block[1]}</span>')
            label.set_xalign(0.5)
            label.set_justify(Gtk.Justification.CENTER)
            return label
        return self._label(block[1])

    def _table(self, aligns, header, rows):
        """Tabella vera: celle che vanno a capo, intestazione in grassetto,
        righe separate come nelle liste di GNOME."""
        grid = Gtk.Grid(hexpand=True)
        xalign = {"left": 0.0, "center": 0.5, "right": 1.0}
        for r, cells in enumerate([header] + rows):
            for c, cell in enumerate(cells):
                label = self._label(f"<b>{cell}</b>" if r == 0 else cell)
                label.set_xalign(xalign.get(aligns[c], 0.0))
                label.set_valign(Gtk.Align.START)
                label.set_hexpand(True)
                # larghezza naturale = contenuto (al massimo 50 caratteri):
                # le colonne si dividono lo spazio in proporzione al testo
                label.set_max_width_chars(min(max(len(md.plain_text(cell)), 4), 50))
                label.set_margin_start(12)
                label.set_margin_end(12)
                label.set_margin_top(8)
                label.set_margin_bottom(8)
                grid.attach(label, c, 2 * r, 1, 1)
            if r < len(rows):
                grid.attach(Gtk.Separator(), 0, 2 * r + 1, len(header), 1)
        # Niente ScrolledWindow: misurerebbe l'altezza alla larghezza minima
        # e la tabella diventerebbe altissima. Le celle vanno a capo da sole.
        card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        card.add_css_class("card")
        card.append(grid)
        return card

    def add_reasoning(self, text):
        self.reasoning += text
        if self.think_expander is None:
            self._make_think(expanded=True)
        self.think_label.set_text(self.reasoning)

    def _make_think(self, expanded):
        self.think_label = self._label(markup=False)
        self.think_label.add_css_class("dim-label")
        self.think_label.set_margin_start(12)
        self.think_expander = Gtk.Expander(label=_("reasoning_label"),
                                           expanded=expanded, child=self.think_label)
        self.insert_child_after(self.think_expander, self.get_first_child())

    def add_image(self, data_url, name):
        self.images.append((data_url, name))

    def finish(self):
        """Ultima composizione: testo completo, ragionamento, immagini."""
        if self._render_id:
            GLib.source_remove(self._render_id)
            self._render_id = 0
        self.text, think = strip_think(self.text)
        if think and not self.reasoning:
            self.reasoning = think
            self._make_think(expanded=False)
            self.think_label.set_text(think)
        elif self.think_expander is not None:
            self.think_expander.set_expanded(False)
        self._render(md.parse_blocks(self.text))
        for data_url, name in self.images:
            self.body.append(self._picture(data_url, name))
        if self.role == "assistant":
            self.actions.set_visible(bool(self.text))

    def _code_block(self, lang, code):
        if GtkSource is None:
            buf = Gtk.TextBuffer()
            buf.set_text(code)
            view = Gtk.TextView(buffer=buf, editable=False, monospace=True,
                                top_margin=6, bottom_margin=6, left_margin=8)
            return self._code_frame(lang, code, view)
        buf = GtkSource.Buffer()
        manager = GtkSource.LanguageManager.get_default()
        language = manager.get_language({"py": "python", "md": "markdown",
                                         "sh": "sh", "bash": "sh"}.get(lang, lang)) if lang else None
        if language:
            buf.set_language(language)
        set_source_scheme(buf)
        buf.set_text(code)
        view = GtkSource.View(buffer=buf, editable=False, monospace=True,
                              show_line_numbers=True, wrap_mode=Gtk.WrapMode.NONE,
                              top_margin=6, bottom_margin=6)
        return self._code_frame(lang, code, view)

    def _code_frame(self, lang, code, view):
        scroller = Gtk.ScrolledWindow(child=view, propagate_natural_height=True,
                                      vscrollbar_policy=Gtk.PolicyType.NEVER)
        head = Gtk.Box(spacing=6, margin_start=12, margin_end=6, margin_top=4)
        label = Gtk.Label(label=lang or _("code"), xalign=0, hexpand=True)
        label.add_css_class("caption")
        label.add_css_class("dim-label")
        copy = Gtk.Button(icon_name="edit-copy-symbolic", tooltip_text=_("copy_code"))
        copy.add_css_class("flat")
        buf = view.get_buffer()
        # il testo attuale del blocco: durante lo streaming cresce
        copy.connect("clicked", lambda _b: self.window.copy_text(
            buf.get_text(buf.get_start_iter(), buf.get_end_iter(), False)))
        head.append(label)
        head.append(copy)
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        box.add_css_class("card")
        box.append(head)
        box.append(scroller)
        box.code_buffer = buf
        return box

    @staticmethod
    def _picture(data_url, name):
        try:
            raw = base64.b64decode(data_url.split(",", 1)[1])
            texture = Gdk.Texture.new_from_bytes(GLib.Bytes.new(raw))
            pic = Gtk.Picture(paintable=texture, can_shrink=True,
                              content_fit=Gtk.ContentFit.SCALE_DOWN,
                              halign=Gtk.Align.START, height_request=160,
                              tooltip_text=name)
            pic.add_css_class("card")
            return pic
        except (GLib.Error, ValueError, IndexError):
            label = Gtk.Label(label=name, xalign=0)
            label.add_css_class("dim-label")
            return label


# ── Finestra principale ──────────────────────────────────────────────────────
class RuscaLLamaWindow(FontSizeMixin, Adw.ApplicationWindow):
    def __init__(self, app):
        super().__init__(application=app, title=APP_NAME)
        self.cfg = load_settings()
        self.set_default_size(self.cfg["width"], self.cfg["height"])
        self.set_size_request(360, 294)
        if self.cfg["maximized"]:
            self.maximize()
        self.engine = engine.Engine("ruscallama", self._on_engine_log,
                                    self._on_engine_state)
        self.devices = []                    # schede viste dal motore
        self._device_updating = False
        threading.Thread(target=self._load_devices, daemon=True).start()
        self.log_lines = []
        self.history = []                    # messaggi in formato OpenAI
        self.attachments = []                # (tipo, nome, dato)
        self.models = []
        self.mmproj = self.draft = None
        self.generating = False
        self.stop_event = threading.Event()
        self.current = None                  # Message in streaming
        self.selected_message = None
        self.needs_restart = False
        self._updating = False
        self._tokens = 0
        self._t_first = self._t_send = None

        self._build_actions()
        self._init_font_size()
        self._build_ui()
        self._scan_models()
        self._refresh_engine_ui()
        self.connect("close-request", self._on_close)

    # ── azioni e scorciatoie ──────────────────────────────────────────────
    def _build_actions(self):
        for name, cb in (("new-chat", self.new_chat), ("attach", self.attach),
                         ("save-md", lambda: self.save_conversation("md")),
                         ("save-html", lambda: self.save_conversation("html")),
                         ("save-answer", self.save_answer),
                         ("save-code", self.save_code),
                         ("engine-start", self.start_engine),
                         ("engine-stop", self.stop_engine),
                         ("engine-restart", self.restart_engine),
                         ("show-log", self.show_log),
                         ("stop", self.stop_generation),
                         ("toggle-sidebar", self.toggle_sidebar),
                         ("shortcuts", self.show_shortcuts),
                         ("about", self.show_about)):
            action = Gio.SimpleAction.new(name, None)
            action.connect("activate", lambda _a, _p, f=cb: f())
            self.add_action(action)

    # ── interfaccia ───────────────────────────────────────────────────────
    def _build_ui(self):
        header = Adw.HeaderBar()
        self.title = Adw.WindowTitle(title=APP_NAME)
        header.set_title_widget(self.title)
        new = Gtk.Button(icon_name="list-add-symbolic", action_name="win.new-chat",
                         tooltip_text=_("new_chat"))
        header.pack_start(new)
        menu = Gio.Menu()
        save = Gio.Menu()
        save.append(_("save_md"), "win.save-md")
        save.append(_("save_html"), "win.save-html")
        menu.append_section(None, save)
        eng = Gio.Menu()
        eng.append(_("engine_restart"), "win.engine-restart")
        eng.append(_("engine_stop"), "win.engine-stop")
        eng.append(_("engine_log"), "win.show-log")
        menu.append_section(None, eng)
        app_menu = Gio.Menu()
        app_menu.append(_("shortcuts"), "win.shortcuts")
        app_menu.append(_("about"), "win.about")
        menu.append_section(None, app_menu)
        header.pack_end(Gtk.MenuButton(icon_name="open-menu-symbolic", menu_model=menu,
                                       primary=True, tooltip_text=_("main_menu")))
        self.sidebar_btn = Gtk.ToggleButton(icon_name="sidebar-show-right-symbolic",
                                            tooltip_text=_("settings_toggle"))
        self.sidebar_btn.update_property([Gtk.AccessibleProperty.LABEL],
                                         [_("settings_toggle")])
        header.pack_end(self.sidebar_btn)

        self.banner = Adw.Banner()
        self.banner.connect("button-clicked", self._on_banner)

        # Conversazione
        self.empty = Adw.StatusPage(title=_("empty_title"),
                                    description=_("empty_desc"))
        if theme_has_icon():
            self.empty.set_icon_name(APP_ID)
        self.chat_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=18,
                                margin_top=18, margin_bottom=18,
                                margin_start=12, margin_end=12)
        self.chat_box.add_css_class("rusca-content")
        clamp = Adw.Clamp(child=self.chat_box, maximum_size=820)
        self.chat_scroll = Gtk.ScrolledWindow(child=clamp, vexpand=True,
                                              hscrollbar_policy=Gtk.PolicyType.NEVER)
        self.stack = Gtk.Stack(transition_type=Gtk.StackTransitionType.CROSSFADE)
        self.stack.add_named(self.empty, "empty")
        self.stack.add_named(self.chat_scroll, "chat")
        self.toasts = Adw.ToastOverlay(child=self.stack)

        view = Adw.ToolbarView(content=self.toasts)
        view.add_top_bar(header)
        view.add_top_bar(self.banner)
        view.add_bottom_bar(self._build_input())

        # Il pannello ha la sua barra del titolo: con il pannello aperto a
        # destra, sono i suoi i pulsanti della finestra (chiudi, riduci...).
        sidebar = Adw.ToolbarView(content=self._build_sidebar())
        sidebar.add_top_bar(Adw.HeaderBar(show_title=False))
        self.split = Adw.OverlaySplitView(content=view, sidebar=sidebar,
                                          sidebar_position=Gtk.PackType.END,
                                          max_sidebar_width=380, min_sidebar_width=300)
        self.split.bind_property("show-sidebar", self.sidebar_btn, "active",
                                 GObject.BindingFlags.BIDIRECTIONAL
                                 | GObject.BindingFlags.SYNC_CREATE)
        self.split.set_show_sidebar(self.cfg["sidebar"])
        breakpoint_ = Adw.Breakpoint.new(Adw.BreakpointCondition.parse("max-width: 760sp"))
        breakpoint_.add_setter(self.split, "collapsed", True)
        self.add_breakpoint(breakpoint_)
        self.set_content(self.split)

    def _build_input(self):
        outer = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6,
                        margin_top=6, margin_bottom=6, margin_start=12, margin_end=12)
        self.attach_box = Gtk.FlowBox(selection_mode=Gtk.SelectionMode.NONE,
                                      max_children_per_line=8, visible=False)
        outer.append(self.attach_box)
        row = Gtk.Box(spacing=6)
        attach = Gtk.Button(icon_name="mail-attachment-symbolic", action_name="win.attach",
                            tooltip_text=_("attach"), valign=Gtk.Align.END)
        attach.add_css_class("flat")
        attach.update_property([Gtk.AccessibleProperty.LABEL], [_("attach")])
        self.input_buf = Gtk.TextBuffer()
        self.input = Gtk.TextView(buffer=self.input_buf, wrap_mode=Gtk.WrapMode.WORD_CHAR,
                                  top_margin=8, bottom_margin=8, left_margin=10,
                                  right_margin=10, accepts_tab=False)
        self.input.update_property([Gtk.AccessibleProperty.LABEL], [_("input_label")])
        self.input.add_css_class("rusca-content")
        keys = Gtk.EventControllerKey()
        keys.connect("key-pressed", self._on_key)
        self.input.add_controller(keys)
        self.input_buf.connect("changed", lambda *_a: self._refresh_send())
        scroller = Gtk.ScrolledWindow(child=self.input, hexpand=True,
                                      propagate_natural_height=True,
                                      max_content_height=200,
                                      hscrollbar_policy=Gtk.PolicyType.NEVER)
        scroller.add_css_class("card")
        self.placeholder = Gtk.Label(label=_("input_placeholder"), xalign=0,
                                     can_target=False, margin_start=12)
        self.placeholder.add_css_class("dim-label")
        self.placeholder.add_css_class("rusca-content")
        overlay = Gtk.Overlay(child=scroller, hexpand=True)
        overlay.add_overlay(self.placeholder)
        self.send_btn = Gtk.Button(icon_name="go-up-symbolic", tooltip_text=_("send"),
                                   valign=Gtk.Align.END)
        self.send_btn.add_css_class("circular")
        self.send_btn.add_css_class("suggested-action")
        self.send_btn.update_property([Gtk.AccessibleProperty.LABEL], [_("send")])
        self.send_btn.connect("clicked", lambda _b: self.send())
        self.stop_btn = Gtk.Button(icon_name="media-playback-stop-symbolic",
                                   tooltip_text=_("stop"), valign=Gtk.Align.END,
                                   action_name="win.stop", visible=False)
        self.stop_btn.add_css_class("circular")
        self.stop_btn.add_css_class("destructive-action")
        self.stop_btn.update_property([Gtk.AccessibleProperty.LABEL], [_("stop")])
        for w in (attach, overlay, self.send_btn, self.stop_btn):
            row.append(w)
        outer.append(row)
        self.stats = Gtk.Label(xalign=1, visible=False)
        self.stats.add_css_class("caption")
        self.stats.add_css_class("dim-label")
        self.stats.add_css_class("numeric")
        outer.append(self.stats)
        clamp = Adw.Clamp(child=outer, maximum_size=820)
        return clamp

    def _build_sidebar(self):
        page = Adw.PreferencesPage()
        cfg = self.cfg

        # Modello
        look = Adw.PreferencesGroup(title=_("group_look"))
        theme_row = Adw.ComboRow(title=_("theme"), model=Gtk.StringList.new(
            [_(f"theme_{t}") for t in THEMES]))
        theme_row.set_selected(THEMES.index(cfg.get("theme", "system"))
                               if cfg.get("theme") in THEMES else 0)
        theme_row.connect("notify::selected", self._on_theme)
        look.add(theme_row)
        look.add(self.font_size_row())
        page.add(look)

        model_group = Adw.PreferencesGroup(title=_("group_model"))
        self.model_row = Adw.ComboRow(title=_("model"), use_subtitle=True)
        self.model_row.connect("notify::selected", self._on_model_selected)
        model_group.add(self.model_row)
        choose = Adw.ActionRow(title=_("choose_file"), activatable=True)
        choose.add_suffix(Gtk.Image(icon_name="document-open-symbolic"))
        choose.connect("activated", lambda _r: self.choose_model())
        model_group.add(choose)
        folder = Adw.ActionRow(title=_("open_models_folder"), subtitle=_("models_folder_hint"),
                               activatable=True)
        folder.add_suffix(Gtk.Image(icon_name="folder-open-symbolic"))
        folder.connect("activated", lambda _r: self.open_models_folder())
        model_group.add(folder)
        page.add(model_group)

        # Risposte
        answers = Adw.PreferencesGroup(title=_("group_answers"))
        self.preset_row = Adw.ComboRow(title=_("style"), model=Gtk.StringList.new(
            [_(f"preset_{p}") for p in PRESET_ORDER]))
        self.preset_row.set_selected(PRESET_ORDER.index(cfg["preset"]))
        self.preset_row.connect("notify::selected", self._on_preset)
        answers.add(self.preset_row)
        self.reasoning_row = Adw.SwitchRow(title=_("reasoning"),
                                           subtitle=_("reasoning_sub"),
                                           active=cfg["reasoning"])
        self.reasoning_row.connect("notify::active", self._on_reasoning)
        answers.add(self.reasoning_row)
        self.effort_row = Adw.ComboRow(title=_("effort"), model=Gtk.StringList.new(
            [_(f"effort_{e}") for e in EFFORTS]), sensitive=cfg["reasoning"])
        self.effort_row.set_selected(EFFORTS.index(cfg["effort"])
                                     if cfg["effort"] in EFFORTS else 0)
        self.effort_row.connect("notify::selected", lambda r, _p: self._set(
            "effort", EFFORTS[r.get_selected()]))
        answers.add(self.effort_row)
        self.system_row = Adw.EntryRow(title=_("system_prompt"),
                                       text=cfg["system"] or _("system_default"))
        # Si salva solo un testo diverso da quello predefinito, che resta
        # così nella lingua dell'interfaccia anche se questa cambia.
        self.system_row.connect("changed", lambda r: self._set(
            "system", "" if r.get_text() == _("system_default") else r.get_text()))
        answers.add(self.system_row)
        self.sampling = Adw.ExpanderRow(title=_("sampling"), subtitle=_("sampling_sub"))
        self.spins = {}
        for key, lo, hi, step, digits in (("temperature", 0, 2, 0.05, 2),
                                          ("top_p", 0, 1, 0.01, 2),
                                          ("top_k", 0, 200, 1, 0),
                                          ("min_p", 0, 1, 0.01, 2),
                                          ("presence_penalty", -2, 2, 0.1, 2),
                                          ("repeat_penalty", 0.5, 2, 0.01, 2)):
            row = Adw.SpinRow.new_with_range(lo, hi, step)
            row.set_digits(digits)
            row.set_title(_(f"p_{key}"))
            row.set_subtitle(_(f"p_{key}_sub"))
            row.set_value(cfg["sampling"].get(key, PRESETS["balanced"][key]))
            row.connect("notify::value", self._on_spin, key)
            self.sampling.add_row(row)
            self.spins[key] = row
        seed = Adw.SpinRow.new_with_range(-1, 2**31 - 1, 1)
        seed.set_title(_("p_seed"))
        seed.set_subtitle(_("p_seed_sub"))
        seed.set_value(cfg["seed"])
        seed.connect("notify::value", lambda r, _p: self._set("seed", int(r.get_value())))
        self.sampling.add_row(seed)
        answers.add(self.sampling)
        page.add(answers)

        # Motore
        eng = Adw.PreferencesGroup(title=_("group_engine"), description=_("engine_desc"))
        self.gpu_row = Adw.SwitchRow(title=_("gpu"), subtitle=_("gpu_sub"), active=cfg["gpu"])
        self.gpu_row.connect("notify::active", lambda r, _p: (
            self._set_engine("gpu", r.get_active()), self.device_row.set_sensitive(r.get_active())))
        eng.add(self.gpu_row)
        self.device_row = Adw.ComboRow(title=_("gpu_device"), use_subtitle=True,
                                       sensitive=cfg["gpu"])
        self._fill_device_row()
        self.device_row.connect("notify::selected", self._on_device)
        eng.add(self.device_row)
        threads = Adw.SpinRow.new_with_range(1, max(1, os.cpu_count() or 1), 1)
        threads.set_title(_("threads"))
        threads.set_subtitle(_("threads_sub", n=engine.physical_cores()))
        threads.set_value(min(cfg["threads"], os.cpu_count() or 1))
        threads.connect("notify::value", lambda r, _p: self._set_engine("threads", int(r.get_value())))
        eng.add(threads)
        ctx = Adw.ComboRow(title=_("context"), subtitle=_("context_sub"),
                           model=Gtk.StringList.new([f"{c:,}".replace(",", " ") for c in CONTEXTS]))
        ctx.set_selected(CONTEXTS.index(cfg["context"]) if cfg["context"] in CONTEXTS else 1)
        ctx.connect("notify::selected", lambda r, _p: self._set_engine("context", CONTEXTS[r.get_selected()]))
        eng.add(ctx)
        kv = Adw.ComboRow(title=_("kv_cache"), subtitle=_("kv_cache_sub"),
                          model=Gtk.StringList.new([_(f"kv_{k}") for k in KV_MODES]))
        kv.set_selected(KV_MODES.index(cfg["kv"]) if cfg["kv"] in KV_MODES else 1)
        kv.connect("notify::selected", lambda r, _p: self._set_engine("kv", KV_MODES[r.get_selected()]))
        eng.add(kv)
        flash = Adw.ComboRow(title=_("flash"), subtitle=_("flash_sub"),
                             model=Gtk.StringList.new([_(f"flash_{f}") for f in FLASH_MODES]))
        flash.set_selected(FLASH_MODES.index(cfg["flash"]) if cfg["flash"] in FLASH_MODES else 0)
        flash.connect("notify::selected", lambda r, _p: self._set_engine("flash", FLASH_MODES[r.get_selected()]))
        eng.add(flash)
        self.vision_row = Adw.SwitchRow(title=_("vision"), active=cfg["vision"])
        self.vision_row.connect("notify::active", lambda r, _p: self._set_engine("vision", r.get_active()))
        eng.add(self.vision_row)
        self.spec_row = Adw.SwitchRow(title=_("speculative"), active=cfg["speculative"])
        self.spec_row.connect("notify::active", lambda r, _p: self._set_engine("speculative", r.get_active()))
        eng.add(self.spec_row)
        page.add(eng)
        return page

    # ── impostazioni ──────────────────────────────────────────────────────
    def _on_theme(self, row, _pspec):
        self._set("theme", THEMES[row.get_selected()])
        apply_color_scheme(self.cfg["theme"])

    def _set(self, key, value):
        self.cfg[key] = value
        save_settings(self.cfg)

    # ── schede grafiche ───────────────────────────────────────────────────
    # L'elenco si chiede al motore in background all'avvio del programma
    # (Vulkan impiega un attimo a inizializzarsi). Si salva la descrizione
    # della scheda, non il nome VulkanN, che puo' cambiare.
    def _load_devices(self):
        devices = engine.list_devices()
        GLib.idle_add(self._devices_loaded, devices)

    def _devices_loaded(self, devices):
        self.devices = devices
        self._fill_device_row()
        return False

    def _devices_now(self):
        if not self.devices and self.cfg["gpu_device"]:
            self.devices = engine.list_devices()
        return self.devices

    def _fill_device_row(self):
        row = getattr(self, "device_row", None)
        if row is None:
            return
        voci = [_("gpu_device_auto")] + [
            f"{desc} ({max(1, round(mib / 1024))} GB)" for _n, desc, mib in self.devices]
        descrizioni = [d[1] for d in self.devices]
        self._device_updating = True
        row.set_model(Gtk.StringList.new(voci))
        row.set_selected(descrizioni.index(self.cfg["gpu_device"]) + 1
                         if self.cfg["gpu_device"] in descrizioni else 0)
        self._device_updating = False

    def _on_device(self, row, _pspec):
        if self._device_updating:
            return
        i = row.get_selected()
        self._set_engine("gpu_device", self.devices[i - 1][1] if 0 < i <= len(self.devices) else "")

    def _set_engine(self, key, value):
        """Opzioni che valgono solo all'avvio del motore."""
        self._set(key, value)
        if self.engine.running and not self.needs_restart:
            self.needs_restart = True
            self._refresh_engine_ui()

    def _on_preset(self, row, _pspec):
        if self._updating:
            return
        name = PRESET_ORDER[row.get_selected()]
        self._set("preset", name)
        values = PRESETS[name]
        if values:
            self._updating = True
            for key, spin in self.spins.items():
                spin.set_value(values[key])
            self._updating = False
            self._set("sampling", dict(values))

    def _on_spin(self, row, _pspec, key):
        self.cfg["sampling"][key] = row.get_value()
        if not self._updating and self.cfg["preset"] != "custom":
            self._updating = True
            self.preset_row.set_selected(PRESET_ORDER.index("custom"))
            self.cfg["preset"] = "custom"
            self._updating = False
        save_settings(self.cfg)

    def _on_reasoning(self, row, _pspec):
        on = row.get_active()
        self._set("reasoning", on)
        self.effort_row.set_sensitive(on)
        # Il ragionamento vuole i valori "thinking"; senza, quelli bilanciati.
        if self.cfg["preset"] in ("balanced", "thinking"):
            self.preset_row.set_selected(PRESET_ORDER.index("thinking" if on else "balanced"))

    # ── modelli ───────────────────────────────────────────────────────────
    def _scan_models(self):
        found = engine.find_models()
        if self.cfg["model"] and os.path.isfile(self.cfg["model"]) \
                and self.cfg["model"] not in found:
            found.insert(0, self.cfg["model"])
        self.models = found
        names = [os.path.basename(p) for p in found] or [_("no_model")]
        self._updating = True
        self.model_row.set_model(Gtk.StringList.new(names))
        self.model_row.set_sensitive(bool(found))
        if found:
            self.model_row.set_selected(found.index(self.cfg["model"])
                                        if self.cfg["model"] in found else 0)
        self._updating = False
        self._on_model_selected(self.model_row, None)

    def _on_model_selected(self, row, _pspec):
        if self._updating:
            return
        i = row.get_selected()
        model = self.models[i] if 0 <= i < len(self.models) else ""
        if model != self.cfg["model"]:
            self._set_engine("model", model)
        self.mmproj, self.draft = engine.companions(model) if model else (None, None)
        has_mtp = bool(self.draft) or "mtp" in os.path.basename(model).lower()
        self.vision_row.set_sensitive(bool(self.mmproj))
        self.vision_row.set_subtitle(_("vision_sub") if self.mmproj else _("vision_none"))
        self.spec_row.set_sensitive(has_mtp)
        self.spec_row.set_subtitle(_("speculative_sub") if has_mtp else _("speculative_none"))
        row.set_tooltip_text(model or _("no_model_sub"))
        self._refresh_engine_ui()

    def choose_model(self):
        dialog = Gtk.FileDialog(title=_("choose_model_title"))
        filt = Gtk.FileFilter()
        filt.set_name(_("gguf_files"))
        filt.add_pattern("*.gguf")
        store = Gio.ListStore.new(Gtk.FileFilter)
        store.append(filt)
        dialog.set_filters(store)

        def done(d, result):
            try:
                path = d.open_finish(result).get_path()
            except GLib.Error:
                return
            if path:
                self.cfg["model"] = path
                self._scan_models()
        dialog.open(self, None, done)

    def open_models_folder(self):
        os.makedirs(USER_MODELS, exist_ok=True)
        Gtk.FileLauncher.new(Gio.File.new_for_path(USER_MODELS)).launch(self, None, None)

    # ── motore ────────────────────────────────────────────────────────────
    def _engine_args(self):
        cfg = self.cfg
        args = ["-t", cfg["threads"], "-c", cfg["context"], "-b", 2048,
                "--flash-attn", cfg["flash"], "--reasoning-format", "deepseek"]
        if cfg["kv"] != "f16":
            args += ["-ctk", cfg["kv"], "-ctv", cfg["kv"]]
        if cfg["vision"] and self.mmproj:
            args += ["--mmproj", self.mmproj]
        device = engine.device_name(cfg["gpu_device"], self._devices_now()) if cfg["gpu"] else None
        if device:
            args += ["--device", device]
        if cfg["speculative"]:
            if self.draft:
                args += ["--spec-type", "draft-mtp", "--spec-draft-n-max", 4,
                         "--model-draft", self.draft]
                if cfg["gpu"]:
                    args += ["-ngld", 99]
                    if device:
                        args += ["--device-draft", device]
            elif "mtp" in os.path.basename(cfg["model"]).lower():
                args += ["--spec-type", "draft-mtp", "--spec-draft-n-max", 4]
        return args

    def start_engine(self):
        if self.engine.running:
            return True
        try:
            self.log_lines.clear()
            self.engine.start(self.cfg["model"], self._engine_args(), self.cfg["gpu"])
        except engine.EngineError as e:
            self._show_error(_(e.key), e.detail)
            return False
        self.needs_restart = False
        self._refresh_engine_ui()
        return True

    def stop_engine(self):
        self.stop_generation()
        self.engine.stop()
        self.needs_restart = False
        self._refresh_engine_ui()

    def restart_engine(self):
        self.stop_generation()
        self.engine.stop(wait=True)
        self.start_engine()

    def _on_engine_log(self, line):
        self.log_lines.append(line)
        del self.log_lines[:-2000]

    def _on_engine_state(self, state, detail=""):
        if state == "error" and detail:
            self.toasts.add_toast(Adw.Toast(title=_("engine_died"), timeout=8,
                                            button_label=_("engine_log"),
                                            action_name="win.show-log"))
        self._refresh_engine_ui()

    def _refresh_engine_ui(self):
        state = self.engine.state
        if not self.engine.running and state in ("ready", "starting"):
            state = "stopped"
        model = os.path.basename(self.cfg["model"]) if self.cfg["model"] else _("no_model")
        self.title.set_subtitle({"ready": model, "starting": _("state_starting")}
                                .get(state, _("state_stopped")))
        b = self.banner
        if not engine.find_binary():
            b.set_title(_("banner_no_engine"))
            b.set_button_label(None)
            b.set_revealed(True)
        elif not self.cfg["model"]:
            b.set_title(_("banner_no_model"))
            b.set_button_label(_("choose_file"))
            b.set_revealed(True)
        elif state == "starting":
            b.set_title(_("banner_starting", model=model))
            b.set_button_label(None)
            b.set_revealed(True)
        elif self.needs_restart:
            b.set_title(_("banner_restart"))
            b.set_button_label(_("engine_restart"))
            b.set_revealed(True)
        else:
            b.set_revealed(False)
        self._refresh_send()

    def _on_banner(self, banner):
        if not self.cfg["model"]:
            self.choose_model()
        elif self.needs_restart:
            self.restart_engine()

    # ── invio e generazione ───────────────────────────────────────────────
    def _input_text(self):
        return self.input_buf.get_text(self.input_buf.get_start_iter(),
                                       self.input_buf.get_end_iter(), False).strip()

    def _refresh_send(self):
        has_text = bool(self._input_text()) or bool(self.attachments)
        self.placeholder.set_visible(self.input_buf.get_char_count() == 0)
        self.send_btn.set_visible(not self.generating)
        self.stop_btn.set_visible(self.generating)
        self.send_btn.set_sensitive(has_text and bool(self.cfg["model"])
                                    and engine.find_binary() is not None)

    def _on_key(self, _ctrl, keyval, _code, state):
        if keyval in (Gdk.KEY_Return, Gdk.KEY_KP_Enter) and \
                not state & Gdk.ModifierType.SHIFT_MASK:
            self.send()
            return True
        return False

    def send(self):
        if self.generating or not self.send_btn.get_sensitive():
            return
        text = self._input_text()
        images = [(n, d) for k, n, d in self.attachments if k == "image"]
        if images and not (self.cfg["vision"] and self.mmproj):
            self.toasts.add_toast(Adw.Toast(title=_("needs_vision")))
            return
        for kind, name, data in self.attachments:
            if kind == "text":
                text += f"\n\n```\n# {name}\n{data}\n```"
        content = text.strip()
        if images:
            content = ([{"type": "text", "text": content}] if content else []) + [
                {"type": "image_url", "image_url": {"url": d}, "name": n} for n, d in images]
        self.input_buf.set_text("")
        self._clear_attachments()
        self.history.append({"role": "user", "content": content})
        user = Message(self, "user")
        user.add_stream(text_of(content) if isinstance(content, list) else content)
        for n, d in images:
            user.add_image(d, n)
        user.finish()
        self.chat_box.append(user)
        self.stack.set_visible_child_name("chat")
        self.current = Message(self, "assistant")
        self.chat_box.append(self.current)
        self.generating = True
        self.stop_event.clear()
        self._tokens = 0
        self._t_first = None
        self._t_send = time.monotonic()
        self.stats.set_visible(True)
        GLib.timeout_add(500, self._update_stats)
        self._refresh_send()
        self._scroll_end()
        if not self.engine.running and not self.start_engine():
            self._finish_generation()
            return
        threading.Thread(target=self._generate, args=(self.current,), daemon=True).start()

    def _request_body(self):
        cfg = self.cfg
        messages = [{"role": "system", "content": cfg["system"] or _("system_default")}]
        messages += [{"role": m["role"], "content": m["content"]} for m in self.history]
        body = dict(messages=messages, max_tokens=MAX_TOKENS,
                    reasoning_effort=cfg["effort"] if cfg["reasoning"] else "none")
        body.update({k: (int(v) if k == "top_k" else v) for k, v in cfg["sampling"].items()})
        if cfg["seed"] >= 0:
            body["seed"] = cfg["seed"]
        return body

    def _generate(self, message):
        try:
            if not self.engine.wait_ready(self.stop_event):
                if not self.stop_event.is_set():
                    GLib.idle_add(message.add_stream, _("engine_not_ready"))
            else:
                for text, reasoning in self.engine.chat_stream(self._request_body(),
                                                               self.stop_event):
                    if reasoning:
                        GLib.idle_add(message.add_reasoning, reasoning)
                    if text:
                        self._tokens += 1
                        self._t_first = self._t_first or time.monotonic()
                        GLib.idle_add(message.add_stream, text)
                        GLib.idle_add(self._scroll_end)
        except (engine.EngineError, OSError) as e:
            GLib.idle_add(message.add_stream, "\n\n" + _("connection_error", error=str(e)))
        GLib.idle_add(self._finish_generation)

    def _finish_generation(self):
        message, self.current = self.current, None
        self.generating = False
        if message is not None:
            message.finish()
            if message.text or message.reasoning:
                self.history.append({"role": "assistant", "content": message.text})
        self._update_stats(final=True)
        self._refresh_send()
        self.input.grab_focus()

    def stop_generation(self):
        if self.generating:
            self.stop_event.set()
            self.engine.cancel()

    def _update_stats(self, final=False):
        now = time.monotonic()
        if self._t_first and self._tokens > 1:
            rate = (self._tokens - 1) / max(now - self._t_first, 1e-3)
            self.stats.set_label(_("stats", rate=f"{rate:.1f}", n=self._tokens))
        elif self._t_send:
            self.stats.set_label(_("stats_wait", s=int(now - self._t_send)))
        return self.generating and not final

    def _scroll_end(self):
        adj = self.chat_scroll.get_vadjustment()
        GLib.idle_add(lambda: adj.set_value(adj.get_upper()) and False)
        return False

    def new_chat(self):
        self.stop_generation()
        self.history.clear()
        while (child := self.chat_box.get_first_child()) is not None:
            self.chat_box.remove(child)
        self.stack.set_visible_child_name("empty")
        self.stats.set_visible(False)
        self.input.grab_focus()

    # ── allegati ──────────────────────────────────────────────────────────
    def attach(self):
        dialog = Gtk.FileDialog(title=_("attach_title"))
        filt = Gtk.FileFilter()
        filt.set_name(_("attach_filter"))
        for ext in TEXT_TYPES + tuple(IMAGE_TYPES):
            filt.add_suffix(ext.lstrip("."))
        store = Gio.ListStore.new(Gtk.FileFilter)
        store.append(filt)
        dialog.set_filters(store)

        def done(d, result):
            try:
                files = d.open_multiple_finish(result)
            except GLib.Error:
                return
            for i in range(files.get_n_items()):
                self._add_attachment(files.get_item(i).get_path())
        dialog.open_multiple(self, None, done)

    def _add_attachment(self, path):
        if not path:
            return
        name = os.path.basename(path)
        ext = os.path.splitext(name)[1].lower()
        try:
            size = os.path.getsize(path)
            if ext in IMAGE_TYPES:
                if size > MAX_IMAGE_ATTACHMENT:
                    raise ValueError(_("too_big", name=name))
                with open(path, "rb") as f:
                    data = f"data:{IMAGE_TYPES[ext]};base64," + base64.b64encode(f.read()).decode()
                self.attachments.append(("image", name, data))
            else:
                if size > MAX_TEXT_ATTACHMENT:
                    raise ValueError(_("too_big", name=name))
                with open(path, encoding="utf-8", errors="replace") as f:
                    self.attachments.append(("text", name, f.read()))
        except (OSError, ValueError) as e:
            self.toasts.add_toast(Adw.Toast(title=GLib.markup_escape_text(str(e))))
            return
        self._refresh_attachments()

    def _refresh_attachments(self):
        self.attach_box.remove_all()
        for item in list(self.attachments):
            chip = Adw.ButtonContent(icon_name="image-x-generic-symbolic" if item[0] == "image"
                                     else "text-x-generic-symbolic", label=item[1])
            button = Gtk.Button(child=chip, tooltip_text=_("remove_attachment"))
            button.add_css_class("pill")
            button.add_css_class("small")
            button.connect("clicked", lambda _b, it=item: (self.attachments.remove(it),
                                                            self._refresh_attachments()))
            self.attach_box.append(button)
        self.attach_box.set_visible(bool(self.attachments))
        self._refresh_send()

    def _clear_attachments(self):
        self.attachments.clear()
        self._refresh_attachments()

    # ── salvataggi ────────────────────────────────────────────────────────
    def _conversation(self, fmt):
        rows = []
        for m in self.history:
            who = _("you") if m["role"] == "user" else APP_NAME
            text = text_of(m["content"])
            if fmt == "md":
                rows.append(f"**{who}:**\n\n{text}\n")
            else:
                body = []
                for kind, lang, part in split_code(text):
                    esc = html.escape(part)
                    body.append(f"<pre><code class=\"language-{html.escape(lang)}\">{esc}</code></pre>"
                                if kind == "code" else
                                "".join(f"<p>{p.replace(chr(10), '<br>')}</p>"
                                        for p in esc.split("\n\n")))
                rows.append(f"<section class=\"{m['role']}\"><h2>{html.escape(who)}</h2>"
                            + "".join(body) + "</section>")
        title = _("conversation_title")
        if fmt == "md":
            return f"# {APP_NAME} — {title}\n\n" + "\n".join(rows)
        return (f"<!DOCTYPE html>\n<html lang=\"{LANG.split('_')[0]}\"><head><meta charset=\"utf-8\">"
                f"<title>{APP_NAME} — {html.escape(title)}</title><style>"
                "body{font-family:sans-serif;max-width:46em;margin:2em auto;padding:0 1em;"
                "line-height:1.5;color:#2d0a1d;background:#fbf4f7}"
                "h2{font-size:1em;color:#7a2357}section{margin-bottom:1.5em}"
                "pre{background:#fff;border:1px solid #e6cbd8;border-radius:6px;"
                "padding:.75em;overflow:auto}</style></head><body>"
                f"<h1>{APP_NAME} — {html.escape(title)}</h1>" + "".join(rows)
                + "</body></html>\n")

    def _save_dialog(self, name, content):
        dialog = Gtk.FileDialog(title=_("save_title"), initial_name=name)

        def done(d, result):
            try:
                path = d.save_finish(result).get_path()
                with open(path, "w", encoding="utf-8") as f:
                    f.write(content)
            except GLib.Error:
                return
            except OSError as e:
                self._show_error(_("save_error"), str(e))
                return
            self.toasts.add_toast(Adw.Toast(title=GLib.markup_escape_text(
                _("saved", name=os.path.basename(path)))))
        dialog.save(self, None, done)

    def save_conversation(self, fmt):
        if not self.history:
            self.toasts.add_toast(Adw.Toast(title=_("nothing_to_save")))
            return
        stamp = time.strftime("%Y-%m-%d-%H%M")
        self._save_dialog(f"ruscallama-{stamp}.{fmt}", self._conversation(fmt))

    def _target_message(self):
        msg = self.selected_message
        if msg is None:
            answers = [m for m in self._messages() if m.role == "assistant" and m.text]
            msg = answers[-1] if answers else None
        return msg

    def _messages(self):
        child = self.chat_box.get_first_child()
        while child is not None:
            yield child
            child = child.get_next_sibling()

    def save_answer(self):
        msg = self._target_message()
        if msg is None or not msg.text:
            self.toasts.add_toast(Adw.Toast(title=_("nothing_to_save")))
            return
        self._save_dialog(f"ruscallama-{time.strftime('%Y-%m-%d-%H%M')}.md", msg.text + "\n")

    def save_code(self):
        msg = self._target_message()
        blocks = [(lang, body) for kind, lang, body in split_code(msg.text if msg else "")
                  if kind == "code"]
        if not blocks:
            self.toasts.add_toast(Adw.Toast(title=_("no_code")))
            return
        dialog = Gtk.FileDialog(title=_("save_code_title"))

        def done(d, result):
            try:
                folder = d.select_folder_finish(result).get_path()
            except GLib.Error:
                return
            written = 0
            for i, (lang, body) in enumerate(blocks, 1):
                base = os.path.join(folder, f"ruscallama-{i:02d}")
                ext = CODE_EXT.get(lang, ".txt")
                path, n = base + ext, 1
                while os.path.exists(path):            # mai sovrascrivere
                    n += 1
                    path = f"{base}-{n}{ext}"
                try:
                    with open(path, "w", encoding="utf-8") as f:
                        f.write(body + "\n")
                    written += 1
                except OSError as e:
                    self._show_error(_("save_error"), str(e))
                    return
            self.toasts.add_toast(Adw.Toast(title=_("code_saved", n=written)))
        dialog.select_folder(self, None, done)

    def copy_text(self, text):
        self.get_clipboard().set(text)
        self.toasts.add_toast(Adw.Toast(title=_("copied"), timeout=2))

    # ── finestre secondarie ───────────────────────────────────────────────
    def toggle_sidebar(self):
        self.split.set_show_sidebar(not self.split.get_show_sidebar())

    def show_log(self):
        view = Gtk.TextView(editable=False, cursor_visible=False, monospace=True,
                            wrap_mode=Gtk.WrapMode.WORD_CHAR, top_margin=12,
                            bottom_margin=12, left_margin=12, right_margin=12)
        view.get_buffer().set_text("\n".join(self.log_lines) or _("log_empty"))
        toolbar = Adw.ToolbarView(content=Gtk.ScrolledWindow(child=view, vexpand=True))
        toolbar.add_top_bar(Adw.HeaderBar())
        Adw.Dialog(title=_("engine_log"), content_width=720, content_height=480,
                   child=toolbar).present(self)

    def show_shortcuts(self):
        group = Adw.PreferencesGroup()
        for title, accel in ((_("send"), "Return"), (_("newline"), "<Shift>Return"),
                             (_("stop"), "Escape"), (_("new_chat"), "<Control>n"),
                             (_("attach"), "<Control>o"), (_("save_md"), "<Control>s"),
                             (_("settings_toggle"), "F9"),
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
        self.stop_generation()
        self.engine.stop(wait=True)
        w, h = self.get_default_size()
        self.cfg.update(width=w, height=h, maximized=self.is_maximized(),
                        sidebar=self.split.get_show_sidebar())
        save_settings(self.cfg)
        return False


# ── Applicazione ─────────────────────────────────────────────────────────────
class RuscaLLamaApp(Adw.Application):
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
        # Tema scelto nel pannello (predefinito: segue il sistema), applicato
        # prima della finestra per non mostrarla nel tema sbagliato.
        apply_color_scheme(load_settings().get("theme", "system"))
        Adw.StyleManager.get_default().connect("notify::dark", lambda *_a: self.update_theme())
        self.connect("window-added", lambda *_a: self.update_theme())
        quit_action = Gio.SimpleAction.new("quit", None)
        quit_action.connect("activate", lambda *_a: [w.close() for w in self.get_windows()])
        self.add_action(quit_action)
        for action, accels in (("app.quit", ["<Control>q"]), ("window.close", ["<Control>w"]),
                               ("win.new-chat", ["<Control>n"]), ("win.attach", ["<Control>o"]),
                               ("win.save-md", ["<Control>s"]), ("win.stop", ["Escape"]),
                               ("win.toggle-sidebar", ["F9"]),
                               ("win.zoom-in", ["<Control>plus", "<Control>equal", "<Control>KP_Add"]),
                               ("win.zoom-out", ["<Control>minus", "<Control>KP_Subtract"]),
                               ("win.zoom-reset", ["<Control>0", "<Control>KP_0"]),
                               ("win.shortcuts", ["<Control>question"])):
            self.set_accels_for_action(action, accels)

    def update_theme(self):
        dark = Adw.StyleManager.get_default().get_dark()
        for window in self.get_windows():
            window.remove_css_class("rusca-light" if dark else "rusca-dark")
            window.add_css_class("rusca-dark" if dark else "rusca-light")
        if GtkSource is not None:                # blocchi di codice già mostrati
            for window in self.get_windows():
                stack = [window]
                while stack:
                    widget = stack.pop()
                    if isinstance(widget, GtkSource.View):
                        set_source_scheme(widget.get_buffer())
                    child = widget.get_first_child()
                    while child is not None:
                        stack.append(child)
                        child = child.get_next_sibling()

    def do_activate(self):
        (self.props.active_window or RuscaLLamaWindow(self)).present()


def main():
    GLib.set_prgname(APP_ID)
    GLib.set_application_name(APP_NAME)
    return RuscaLLamaApp().run(sys.argv)


if __name__ == "__main__":
    sys.exit(main())
