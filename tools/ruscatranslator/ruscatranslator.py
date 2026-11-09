#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
RuscaTranslator 1.99.2 — traduttore di documenti Markdown per RuscaLinux.

Traduce tra le 26 lingue ufficiali con un modello linguistico locale, eseguito da
ruscallama-engine (llama.cpp, software esterno con licenza MIT). Per la
coppia italiano/inglese usa un RAG linguistico (raglin.py): equivalenti,
falsi amici, glossario del documento, memoria di traduzione e correzioni
finali. Tutto resta sul computer.

Copyright (C) 2026 Nunzio Curcuruto — https://www.ruscalinux.org
Licenza: GNU GPL 3.0 o successiva.

Requisiti: Python 3.10+, PyGObject, GTK 4.18+, libadwaita 1.7+,
GtkSourceView 5, ruscallama-engine.
"""
import json
import os
import re
import sys
import threading

import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gdk, Gio, GLib, Gtk  # noqa: E402
try:                     # evidenziazione Markdown; senza, testo semplice
    gi.require_version("GtkSource", "5")
    from gi.repository import GtkSource
except (ValueError, ImportError):
    GtkSource = None

BASE_DIR = os.path.dirname(os.path.realpath(__file__))
sys.path.insert(0, BASE_DIR)
import rusca_engine as engine  # noqa: E402
import rusca_markdown as md  # noqa: E402
try:
    import raglin
except ImportError:
    raglin = None

APP_ID = "org.ruscalinux.RuscaTranslator"
APP_NAME = "RuscaTranslator"
APP_VERSION = "1.99.2"
STYLE_SRC = os.path.join(BASE_DIR, "style.css")
ICON_SRC = os.path.join(BASE_DIR, "ruscatranslator.svg")
LANG_DIR = os.path.join(BASE_DIR, "lang")
DOC_DIRS = (os.path.join(BASE_DIR, "docs"), "/usr/share/doc/ruscatranslator")
CONFIG_DIR = os.path.join(GLib.get_user_config_dir(), "ruscatranslator")
CONFIG_FILE = os.path.join(CONFIG_DIR, "settings.json")
COMPONENTS = (
    ("llama.cpp", "MIT — The ggml authors", "https://github.com/ggml-org/llama.cpp"),
    # Regola dell'evidenziato ==testo==, nel file a sé markdown_it_mark.py
    ("markdown-it-mark", "MIT — Vitaly Puzrin, Alex Kocharin; ExecutableBookProject",
     "https://github.com/markdown-it/markdown-it-mark"),
)

CHUNK_CHAR = 6000                 # caratteri per blocco di traduzione
MAX_TOKENS = 4096
# Un solo campionamento, scelto dopo le prove: basso e riproducibile.
SAMPLING = dict(temperature=0.2, top_p=0.92, top_k=40, min_p=0.08,
                repeat_penalty=1.08)
# Modelli preferiti per la traduzione, in ordine (parti del nome del file).
PREFERRED_MODELS = ("gemma-4", "gemma4", "26b-a4b", "a4b")

# Lingue dei documenti: le 26 lingue dei RuscaLinux OS Tools (specifiche,
# sezione 9). Codice, nome nella lingua stessa, nome in inglese (per il
# prompt). I codici gia' usati fino alla 1.99.2 ("zh", "pt-BR") restano
# uguali, cosi' le impostazioni salvate continuano a valere; le lingue
# nuove sono in fondo, e le varianti accanto alla lingua sorella.
LANGUAGES = (
    ("en", "English", "English"),
    ("zh", "中文（简体）", "Simplified Chinese"),
    ("zh-TW", "中文（繁體）", "Traditional Chinese"),
    ("es", "Español", "Spanish"), ("hi", "हिन्दी", "Hindi"),
    ("ar", "العربية", "Arabic"),
    ("pt-BR", "Português (Brasil)", "Brazilian Portuguese"),
    ("pt-PT", "Português (Portugal)", "European Portuguese"),
    ("ru", "Русский", "Russian"), ("ja", "日本語", "Japanese"),
    ("de", "Deutsch", "German"), ("fr", "Français", "French"),
    ("it", "Italiano", "Italian"), ("ko", "한국어", "Korean"),
    ("id", "Bahasa Indonesia", "Indonesian"), ("tr", "Türkçe", "Turkish"),
    ("pl", "Polski", "Polish"), ("nl", "Nederlands", "Dutch"),
    ("uk", "Українська", "Ukrainian"), ("cs", "Čeština", "Czech"),
    ("vi", "Tiếng Việt", "Vietnamese"), ("sv", "Svenska", "Swedish"),
    ("ro", "Română", "Romanian"), ("hu", "Magyar", "Hungarian"),
    ("el", "Ελληνικά", "Greek"), ("fi", "Suomi", "Finnish"),
)
CODES = [c for c, _n, _e in LANGUAGES]
NATIVE = {c: n for c, n, _e in LANGUAGES}
ENGLISH = {c: e for c, _n, e in LANGUAGES}
DOMAINS = ("generale", "saggistica", "letteratura", "dialoghi")
CONTEXTS = (4096, 8192, 16384, 32768)
DEFAULTS = {
    "model": "", "gpu": False, "gpu_device": "", "threads": engine.physical_cores(),
    "context": 8192, "rag": True, "domain": "generale", "src": "auto",
    "tgt": "en", "font_size": 0, "width": 1200, "height": 800, "maximized": False,
    "theme": "system",
}
THEMES = ("system", "light", "dark")         # ordine delle voci nel menu


def set_source_scheme(buf):
    """Schema dei colori del testo: Adwaita o Adwaita-dark secondo il tema.
    Senza, GtkSourceView usa «classic», bianco anche in modalità scura."""
    if GtkSource is None or not isinstance(buf, GtkSource.Buffer):
        return
    scheme = GtkSource.StyleSchemeManager.get_default().get_scheme(
        "Adwaita-dark" if Adw.StyleManager.get_default().get_dark() else "Adwaita")
    if scheme:
        buf.set_style_scheme(scheme)


def apply_color_scheme(theme):
    """Tema chiaro/scuro: segue GNOME (predefinito) o è scelto dall'utente."""
    Adw.StyleManager.get_default().set_color_scheme({
        "light": Adw.ColorScheme.FORCE_LIGHT,
        "dark": Adw.ColorScheme.FORCE_DARK,
    }.get(theme, Adw.ColorScheme.DEFAULT))

# Rilevamento delle lingue in alfabeto latino: parole frequenti e lettere
# tipiche. "pt" e' il portoghese comune; la variante si sceglie dopo
# (_pt_variant). Le parole brevi condivise tra lingue (" a ", " to ",
# " se ", " on ") sono escluse apposta.
STOP_LAT = {
    "it": (" che ", " di ", " il ", " la ", " per ", " non ", " sono ", " come "),
    "en": (" the ", " of ", " and ", " to ", " in ", " that ", " is ", " with "),
    "de": (" der ", " die ", " das ", " und ", " nicht ", " mit ", " für ", " ich "),
    "fr": (" le ", " les ", " des ", " est ", " dans ", " pour ", " une ", " avec "),
    "es": (" el ", " los ", " las ", " que ", " por ", " para ", " muy ", " está "),
    "pt": (" o ", " os ", " as ", " que ", " não ", " para ", " com ", " uma "),
    "pl": (" nie ", " jest ", " i ", " w ", " na ", " z ", " że ", " się "),
    "tr": (" ve ", " bir ", " bu ", " için ", " ile ", " değil ", " olarak ", " çok "),
    "id": (" yang ", " dan ", " ini ", " itu ", " dengan ", " untuk ", " tidak ", " dalam "),
    "nl": (" het ", " een ", " van ", " niet ", " zijn ", " voor ", " ook ", " dat "),
    "sv": (" och ", " att ", " det ", " som ", " inte ", " för ", " med ", " är "),
    "cs": (" je ", " že ", " jsou ", " není ", " také ", " který ", " jako ", " ale "),
    "ro": (" și ", " în ", " este ", " nu ", " cu ", " pentru ", " care ", " sunt "),
    "hu": (" és ", " az ", " hogy ", " nem ", " egy ", " van ", " meg ", " kell "),
    "fi": (" ja ", " että ", " ei ", " oli ", " mutta ", " kun ", " myös ", " ovat "),
    "vi": (" và ", " của ", " là ", " có ", " không ", " những ", " được ", " cho "),
}
BONUS = {
    "pl": ("ł", "ą", "ę", "ś", "ż"),
    "pt": ("ão", "ç"),
    "es": ("¿", "¡"),
    "fr": ("ê", "ç"),           # non "è": e' comunissima in italiano
    "de": ("ß", "ü"),           # non "ä", "ö": anche svedese e finlandese
    "tr": ("ı", "ş", "ğ"),
    "cs": ("ř", "ě", "ů", "č"),
    "ro": ("ș", "ț", "ă", "î", "â"),
    "hu": ("ő", "ű", "gy"),
    "fi": ("ää", "yy"),
    "sv": ("å",),
    "nl": ("ij",),
    "vi": ("ơ", "ư", "đ", "ạ", "ả", "ấ", "ầ", "ế", "ề", "ệ", "ộ", "ờ", "ợ", "ủ", "ứ"),
}

# Varianti. Cinese: caratteri che si scrivono diversamente nelle due forme
# (stesso ordine nelle due stringhe). Ucraino e russo: lettere proprie di
# ciascuno. Portoghese: forme europee e brasiliane frequenti.
HAN_SEMPLIFICATI = "这个们说来时会对后国学体经点样还让开关为与从听见话书车长门问题处应该实际电机发动么过现种东"
HAN_TRADIZIONALI = "這個們說來時會對後國學體經點樣還讓開關為與從聽見話書車長門問題處應該實際電機發動麼過現種東"
PT_PT = (" facto", " equipa", " ecrã", " utilizador", " registo", " connosco",
         " telemóvel", " autocarro", " comboio", " casa de banho", " pequeno-almoço")
PT_BR = (" você", " vocês", " a gente ", " usuário", " tela ", " registro",
         " fato ", " ônibus", " trem ", " celular", " café da manhã")
RE_PT_PT = re.compile(r"\b(?:estou|está|estás|estamos|estão|estava|estavam|continua|anda) a \w+r\b")
RE_PT_BR = re.compile(r"\b(?:estou|está|estamos|estão|estava|estavam|continua|anda) \w+ndo\b")


def _pt_variant(low):
    """Portoghese europeo o brasiliano; nel dubbio brasiliano, come prima."""
    pt = sum(low.count(m) for m in PT_PT) + 2 * len(RE_PT_PT.findall(low))
    br = sum(low.count(m) for m in PT_BR) + 2 * len(RE_PT_BR.findall(low))
    return "pt-PT" if pt > br else "pt-BR"



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
        # Impostazioni della 1.99.1 (chiavi italiane)
        for old, new in (("modello", "model"), ("thread", "threads"), ("ctx", "context")):
            if old in data and new not in data and isinstance(data[old], type(cfg[new])):
                cfg[new] = data[old]
    except (OSError, ValueError, AttributeError):
        pass
    if cfg["src"] != "auto" and cfg["src"] not in CODES:
        cfg["src"] = "auto"
    if cfg["tgt"] not in CODES:
        cfg["tgt"] = "en"
    if cfg["domain"] not in DOMAINS:
        cfg["domain"] = "generale"
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


def detect_language(text):
    """Rilevamento leggero: alfabeto per le lingue con scrittura propria,
    parole frequenti per quelle in alfabeto latino."""
    t = text[:6000]
    for pattern, code in (("[\u3040-\u30ff]", "ja"),       # kana prima degli ideogrammi
                          ("[\uac00-\ud7af]", "ko"),       # hangul
                          ("[\u4e00-\u9fff]", "zh"),
                          ("[\u0600-\u06ff]", "ar"),
                          ("[\u0900-\u097f]", "hi"),       # devanagari
                          ("[\u0370-\u03ff\u1f00-\u1fff]", "el"),
                          ("[\u0400-\u04ff]", "ru")):
        if re.search(pattern, t):
            if code == "zh":
                trad = sum(t.count(c) for c in HAN_TRADIZIONALI)
                simp = sum(t.count(c) for c in HAN_SEMPLIFICATI)
                return "zh-TW" if trad > simp else "zh"
            if code == "ru":
                low = t.lower()
                uk = sum(low.count(c) for c in "іїєґ")
                ru = sum(low.count(c) for c in "ыэъё")
                return "uk" if uk > ru else "ru"
            return code
    low = " " + t.lower().replace("\n", " ") + " "
    scores = {}
    for code, marks in STOP_LAT.items():
        score = sum(low.count(m) for m in marks)
        score += sum(3 * low.count(b) for b in BONUS.get(code, ()))
        scores[code] = score
    best = max(scores, key=scores.get)
    return _pt_variant(low) if best == "pt" else best


def build_prompt(src, tgt, domain):
    s, g = ENGLISH[src], ENGLISH[tgt]
    prompt = (
        f"You are a professional translator from {s} to {g} of technical, "
        f"humanistic and literary texts. Translate the following Markdown chunk "
        f"completely and faithfully into idiomatic {g}. Preserve all Markdown "
        f"formatting exactly (headings, lists, tables, code fences, links, "
        f"emphasis, footnote markers). Never add notes, comments or explanations. "
        f"Every line of the chunk is content to translate, including quoted "
        f"dialogue, imperatives, interjections and exclamations: render them in "
        f"{g}, never leave them in {s}. When the force of an expression is "
        f"uncertain, choose the most plausible {g} equivalent for the context. "
        f"Output only the translated Markdown.")
    if raglin is not None:
        prompt += raglin.REGOLE_QUALITA + raglin.prompt_uso(domain)
    return prompt


def split_markdown(text, max_chars=CHUNK_CHAR):
    """Blocchi di al massimo max_chars caratteri, tagliati solo fra un blocco
    Markdown e l'altro: un elenco, una tabella, una citazione o un blocco di
    codice non si spezzano mai, anche se contengono righe vuote (righe dei
    blocchi dal motore comune, rusca_markdown.block_ranges). Un blocco più
    lungo di max_chars resta intero. Dentro ogni pezzo il testo è quello
    originale, righe vuote comprese."""
    lines = text.split("\n")
    chunks, first, last, size = [], None, None, 0
    for a, b in md.block_ranges(text):
        length = sum(len(line) + 1 for line in lines[a:b])
        if first is not None and size + length > max_chars:
            chunks.append("\n".join(lines[first:last]).strip("\n"))
            first, size = None, 0
        if first is None:
            first = a
        last, size = b, size + length
    if first is not None:
        chunks.append("\n".join(lines[first:last]).strip("\n"))
    return [c for c in chunks if c.strip()]


def pick_model(saved):
    """Il modello salvato, altrimenti il primo che corrisponde ai preferiti,
    altrimenti il più grande trovato."""
    if saved and os.path.isfile(saved):
        return saved
    found = engine.find_models()
    for pattern in PREFERRED_MODELS:
        for p in found:
            if pattern in os.path.basename(p).lower():
                return p
    return found[0] if found else ""


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


# ── Finestra principale ──────────────────────────────────────────────────────
class TranslatorWindow(FontSizeMixin, Adw.ApplicationWindow):
    def __init__(self, app):
        super().__init__(application=app, title=APP_NAME)
        self.cfg = load_settings()
        self.set_default_size(self.cfg["width"], self.cfg["height"])
        self.set_size_request(360, 294)
        if self.cfg["maximized"]:
            self.maximize()
        self.engine = engine.Engine("ruscatranslator", self._on_engine_log,
                                    self._on_engine_state)
        self.devices = []                    # schede viste dal motore
        self._device_updating = False
        threading.Thread(target=self._load_devices, daemon=True).start()
        self.log_lines = []
        self.models = []
        self.source_path = None
        self.saved_path = None
        self.last_pair = None
        self.last_source = ""
        self.rag_used = False
        self.translating = False
        self.stop_event = threading.Event()
        self.needs_restart = False
        self._build_actions()
        self._init_font_size()
        self._build_ui()
        self.cfg["model"] = pick_model(self.cfg["model"])
        self._refresh_engine_ui()
        self.connect("close-request", self._on_close)

    # ── azioni ────────────────────────────────────────────────────────────
    def _build_actions(self):
        for name, cb in (("open", self.open_file), ("save", self.save),
                         ("save-as", self.save_as), ("translate", self.translate),
                         ("stop", self.stop_translation), ("swap", self.swap_languages),
                         ("preferences", self.show_preferences),
                         ("engine-restart", self.restart_engine),
                         ("engine-stop", self.stop_engine), ("show-log", self.show_log),
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
        for icon, action, tip in (("document-open-symbolic", "win.open", "open"),
                                  ("document-save-symbolic", "win.save", "save")):
            b = Gtk.Button(icon_name=icon, action_name=action, tooltip_text=_(tip))
            b.update_property([Gtk.AccessibleProperty.LABEL], [_(tip)])
            header.pack_start(b)
        menu = Gio.Menu()
        files = Gio.Menu()
        files.append(_("save_as"), "win.save-as")
        menu.append_section(None, files)
        eng = Gio.Menu()
        eng.append(_("preferences"), "win.preferences")
        eng.append(_("engine_restart"), "win.engine-restart")
        eng.append(_("engine_stop"), "win.engine-stop")
        eng.append(_("engine_log"), "win.show-log")
        menu.append_section(None, eng)
        app_menu = Gio.Menu()
        app_menu.append(_("guide"), "win.guide")
        app_menu.append(_("shortcuts"), "win.shortcuts")
        app_menu.append(_("about"), "win.about")
        menu.append_section(None, app_menu)
        header.pack_end(Gtk.MenuButton(icon_name="open-menu-symbolic", menu_model=menu,
                                       primary=True, tooltip_text=_("main_menu")))

        # Barra delle lingue
        names = [NATIVE[c] for c in CODES]
        self.src_drop = Gtk.DropDown.new_from_strings([_("auto_detect")] + names)
        self.src_drop.set_tooltip_text(_("source_language"))
        self.src_drop.set_selected(0 if self.cfg["src"] == "auto" else CODES.index(self.cfg["src"]) + 1)
        self.src_drop.connect("notify::selected", lambda *_a: self._save_choices())
        swap = Gtk.Button(icon_name="media-playlist-repeat-symbolic", action_name="win.swap",
                          tooltip_text=_("swap"))
        swap.add_css_class("flat")
        swap.update_property([Gtk.AccessibleProperty.LABEL], [_("swap")])
        self.tgt_drop = Gtk.DropDown.new_from_strings(names)
        self.tgt_drop.set_tooltip_text(_("target_language"))
        self.tgt_drop.set_selected(CODES.index(self.cfg["tgt"]))
        self.tgt_drop.connect("notify::selected", lambda *_a: self._save_choices())
        self.domain_drop = Gtk.DropDown.new_from_strings([_(f"domain_{d}") for d in DOMAINS])
        self.domain_drop.set_tooltip_text(_("domain_tip"))
        self.domain_drop.set_selected(DOMAINS.index(self.cfg["domain"]))
        self.domain_drop.connect("notify::selected", lambda *_a: self._save_choices())
        for w, key in ((self.src_drop, "source_language"), (self.tgt_drop, "target_language"),
                       (self.domain_drop, "domain")):
            w.update_property([Gtk.AccessibleProperty.LABEL], [_(key)])
        self.translate_btn = Gtk.Button(label=_("translate"), action_name="win.translate")
        self.translate_btn.add_css_class("suggested-action")
        self.translate_btn.add_css_class("pill")
        langs = Gtk.Box(spacing=6)
        for w in (self.src_drop, swap, self.tgt_drop):
            langs.append(w)
        right = Gtk.Box(spacing=6)
        right.append(self.domain_drop)
        right.append(self.translate_btn)
        bar = Gtk.Box(spacing=12, margin_start=12, margin_end=12, margin_top=6, margin_bottom=6)
        langs.set_hexpand(True)
        bar.append(langs)
        bar.append(right)

        self.banner = Adw.Banner()
        self.banner.connect("button-clicked", lambda _b: self._on_banner())

        # Testi: originale e traduzione affiancati (impilati su schermi stretti)
        self.src_buf, src_view = self._editor(editable=True)
        self.dst_buf, dst_view = self._editor(editable=True)
        self.src_buf.connect("changed", lambda *_a: self._update_counts())
        self.dst_buf.connect("changed", lambda *_a: self._update_counts())
        self.src_label = Gtk.Label(xalign=0)
        self.dst_label = Gtk.Label(xalign=0)
        self.dst_scroll = None
        src_pane = self._pane(_("original"), self.src_label, src_view)
        dst_pane = self._pane(_("translation"), self.dst_label, dst_view, keep=True)
        self.paned = Gtk.Paned(orientation=Gtk.Orientation.HORIZONTAL, wide_handle=True,
                               start_child=src_pane, end_child=dst_pane,
                               shrink_start_child=False, shrink_end_child=False,
                               margin_start=12, margin_end=12, margin_bottom=12)
        drop = Gtk.DropTarget.new(Gio.File, Gdk.DragAction.COPY)
        drop.connect("drop", lambda _t, f, _x, _y: self.load_file(f.get_path()) or True)
        src_view.add_controller(drop)
        self.toasts = Adw.ToastOverlay(child=self.paned)

        # Avanzamento
        self.progress = Gtk.ProgressBar(show_text=True, hexpand=True, valign=Gtk.Align.CENTER)
        stop = Gtk.Button(label=_("stop"), action_name="win.stop")
        stop.add_css_class("destructive-action")
        self.progress_bar = Gtk.ActionBar(revealed=False)
        self.progress_bar.pack_start(self.progress)
        self.progress_bar.pack_end(stop)

        view = Adw.ToolbarView(content=self.toasts)
        view.add_top_bar(header)
        view.add_top_bar(bar)
        view.add_top_bar(self.banner)
        view.add_bottom_bar(self.progress_bar)
        self.set_content(view)
        narrow = Adw.Breakpoint.new(Adw.BreakpointCondition.parse("max-width: 700sp"))
        narrow.add_setter(self.paned, "orientation", Gtk.Orientation.VERTICAL)
        narrow.add_setter(bar, "orientation", Gtk.Orientation.VERTICAL)
        self.add_breakpoint(narrow)
        self._update_counts()

    def _editor(self, editable):
        if GtkSource is not None:
            buf = GtkSource.Buffer()
            lang = GtkSource.LanguageManager.get_default().get_language("markdown")
            if lang:
                buf.set_language(lang)
            set_source_scheme(buf)
            view = GtkSource.View(buffer=buf)
        else:
            buf = Gtk.TextBuffer()
            view = Gtk.TextView(buffer=buf)
        view.set_wrap_mode(Gtk.WrapMode.WORD_CHAR)
        view.set_editable(editable)
        view.add_css_class("rusca-content")
        for side in ("top", "bottom", "left", "right"):
            getattr(view, f"set_{side}_margin")(12)
        return buf, view

    def _pane(self, title, counter, view, keep=False):
        head = Gtk.Box(spacing=6, margin_bottom=6, margin_top=6)
        label = Gtk.Label(label=title, xalign=0, hexpand=True)
        label.add_css_class("heading")
        counter.add_css_class("caption")
        counter.add_css_class("dim-label")
        counter.add_css_class("numeric")
        head.append(label)
        head.append(counter)
        scroller = Gtk.ScrolledWindow(child=view, vexpand=True, hexpand=True,
                                      hscrollbar_policy=Gtk.PolicyType.NEVER)
        scroller.add_css_class("card")
        if keep:
            self.dst_scroll = scroller
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, margin_start=3, margin_end=3)
        box.append(head)
        box.append(scroller)
        return box

    # ── stato e scelte ────────────────────────────────────────────────────
    def _text(self, buf):
        return buf.get_text(buf.get_start_iter(), buf.get_end_iter(), False)

    def _update_counts(self):
        for buf, label in ((self.src_buf, self.src_label), (self.dst_buf, self.dst_label)):
            label.set_label(_("chars", n=f"{buf.get_char_count():,}".replace(",", " ")))
        self._refresh_actions()

    def _refresh_actions(self):
        has_src = self.src_buf.get_char_count() > 0
        ready = bool(self.cfg["model"]) and engine.find_binary() is not None
        self.lookup_action("translate").set_enabled(has_src and ready and not self.translating)
        self.lookup_action("save").set_enabled(self.dst_buf.get_char_count() > 0 and not self.translating)
        self.lookup_action("save-as").set_enabled(self.dst_buf.get_char_count() > 0 and not self.translating)
        self.lookup_action("stop").set_enabled(self.translating)

    def _save_choices(self):
        i = self.src_drop.get_selected()
        self.cfg["src"] = "auto" if i == 0 else CODES[i - 1]
        self.cfg["tgt"] = CODES[self.tgt_drop.get_selected()]
        self.cfg["domain"] = DOMAINS[self.domain_drop.get_selected()]
        save_settings(self.cfg)

    def swap_languages(self):
        src = self.cfg["src"]
        if src == "auto":
            src = detect_language(self._text(self.src_buf)) if self.src_buf.get_char_count() else "it"
        tgt = self.cfg["tgt"]
        self.src_drop.set_selected(CODES.index(tgt) + 1)
        self.tgt_drop.set_selected(CODES.index(src))
        if self.dst_buf.get_char_count():
            text = self._text(self.dst_buf)
            self.dst_buf.set_text(self._text(self.src_buf))
            self.src_buf.set_text(text)

    # ── file ──────────────────────────────────────────────────────────────
    def _md_filter(self):
        filt = Gtk.FileFilter()
        filt.set_name(_("markdown_files"))
        for p in ("*.md", "*.markdown", "*.txt"):
            filt.add_pattern(p)
        store = Gio.ListStore.new(Gtk.FileFilter)
        store.append(filt)
        return store

    def open_file(self):
        dialog = Gtk.FileDialog(title=_("open_title"), filters=self._md_filter())

        def done(d, result):
            try:
                self.load_file(d.open_finish(result).get_path())
            except GLib.Error:
                pass
        dialog.open(self, None, done)

    def load_file(self, path):
        if not path:
            return
        try:
            with open(path, encoding="utf-8") as f:
                text = f.read()
        except (OSError, UnicodeDecodeError) as e:
            self._show_error(_("open_error"), str(e))
            return
        self.src_buf.set_text(text)
        self.dst_buf.set_text("")
        self.source_path = path
        self.saved_path = None
        detected = detect_language(text)
        self.toasts.add_toast(Adw.Toast(title=GLib.markup_escape_text(
            _("opened", name=os.path.basename(path), language=NATIVE[detected]))))

    def _default_name(self):
        tgt = self.cfg["tgt"].replace("-", "").lower()
        if self.source_path:
            base = os.path.splitext(os.path.basename(self.source_path))[0]
            for code in CODES:
                suffix = "." + code.replace("-", "").lower()
                if base.endswith(suffix):
                    base = base[:-len(suffix)]
                    break
            return f"{base}.{tgt}.md"
        return f"{_('translation_file')}.{tgt}.md"

    def save(self):
        if self.saved_path and os.path.isdir(os.path.dirname(self.saved_path)):
            self._write(self.saved_path)
        else:
            self.save_as()

    def save_as(self):
        dialog = Gtk.FileDialog(title=_("save_title"), initial_name=self._default_name(),
                                filters=self._md_filter())

        def done(d, result):
            try:
                path = d.save_finish(result).get_path()
            except GLib.Error:
                return
            self._write(path)
        dialog.save(self, None, done)

    def _write(self, path):
        text = self._text(self.dst_buf)
        try:
            with open(path, "w", encoding="utf-8") as f:
                f.write(text if text.endswith("\n") else text + "\n")
        except OSError as e:
            self._show_error(_("save_error"), str(e))
            return
        self.saved_path = path
        # La traduzione salvata, rivista dall'utente, alimenta la memoria.
        if raglin is not None and self.rag_used and self.last_pair and self.last_source:
            src, tgt = self.last_pair
            threading.Thread(target=raglin.indica_tm, args=(self.last_source, text, src, tgt),
                             daemon=True).start()
        self.toasts.add_toast(Adw.Toast(title=GLib.markup_escape_text(
            _("saved", name=os.path.basename(path)))))

    # ── motore ────────────────────────────────────────────────────────────
    def _engine_args(self):
        args = ["-t", self.cfg["threads"], "-c", self.cfg["context"], "-b", 4096,
                "-ub", 2048, "--parallel", 1, "--flash-attn", "on",
                "-ctk", "q8_0", "-ctv", "q8_0", "--reasoning", "off"]
        device = (engine.device_name(self.cfg["gpu_device"], self._devices_now())
                  if self.cfg["gpu"] else None)
        if device:
            args += ["--device", device]
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
        self.stop_translation()
        self.engine.stop()
        self.needs_restart = False
        self._refresh_engine_ui()

    def restart_engine(self):
        self.stop_translation()
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
            b.set_button_label(_("preferences"))
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
        self._refresh_actions()

    def _on_banner(self):
        if not self.cfg["model"]:
            self.show_preferences()
        elif self.needs_restart:
            self.restart_engine()

    # ── traduzione ────────────────────────────────────────────────────────
    def _pair(self, text):
        src = self.cfg["src"]
        if src == "auto":
            src = detect_language(text)
        tgt = self.cfg["tgt"]
        if src == tgt:
            # Rilevamento sulla lingua d'arrivo: si traduce verso l'inglese,
            # o verso l'italiano se il testo è già inglese.
            tgt = "it" if src == "en" else "en"
        return src, tgt

    def translate(self):
        if self.translating:
            return
        text = self._text(self.src_buf)
        if not text.strip():
            return
        src, tgt = self._pair(text)
        self.translating = True
        self.stop_event.clear()
        self.dst_buf.set_text("")
        self.progress.set_fraction(0)
        self.progress.set_text(_("preparing"))
        self.progress_bar.set_revealed(True)
        self._refresh_actions()
        if not self.engine.running and not self.start_engine():
            self._finish(False, 0, 0, 0)
            return
        threading.Thread(target=self._worker, args=(text, src, tgt, self.cfg["domain"]),
                         daemon=True).start()

    def stop_translation(self):
        if self.translating:
            self.stop_event.set()
            self.engine.cancel()

    def _translate_terms(self, terms, src, tgt):
        raw = self.engine.chat({
            "messages": [
                {"role": "system", "content":
                    f"You are a terminology extractor. Translate each term from {ENGLISH[src]} "
                    f"to {ENGLISH[tgt]} as a JSON object {{source_term: target_term}}. "
                    "Output JSON only, no prose."},
                {"role": "user", "content": "\n".join(terms)}],
            "temperature": 0.1, "max_tokens": 1024, "reasoning_effort": "none"})
        return raglin.parse_glossario(raw)

    def _stream(self, system, chunk):
        body = dict(SAMPLING, messages=[{"role": "system", "content": system},
                                        {"role": "user", "content": chunk}],
                    max_tokens=MAX_TOKENS, reasoning_effort="none")
        parts = []
        for text, _reasoning in self.engine.chat_stream(body, self.stop_event):
            if text:
                parts.append(text)
                self._emit(text)
        return "".join(parts)

    def _emit(self, text):
        """Aggiunge testo alla traduzione dal thread di lavoro. La posizione
        si conta qui (non leggendo il buffer, che appartiene all'interfaccia)."""
        self._written += len(text)
        GLib.idle_add(self._append, text)

    def _worker(self, text, src, tgt, domain):
        done = total = residues = 0
        ok = False
        try:
            GLib.idle_add(self.progress.set_text, _("loading_model"))
            if not self.engine.wait_ready(self.stop_event):
                raise engine.EngineError("engine_not_ready")
            system = build_prompt(src, tgt, domain)
            use_rag = raglin is not None and self.cfg["rag"] and raglin.attivo(src, tgt)
            session = None
            if use_rag:
                GLib.idle_add(self.progress.set_text, _("preparing_glossary"))
                session = raglin.nuova_sessione(
                    text, src, tgt, traduci_termini=lambda t: self._translate_terms(t, src, tgt))
            self.last_pair, self.last_source, self.rag_used = (src, tgt), text, use_rag
            chunks = split_markdown(text)
            total = len(chunks)
            self._written = 0
            for i, chunk in enumerate(chunks):
                if self.stop_event.is_set():
                    break
                GLib.idle_add(self._progress, i, total, src, tgt)
                prompt = system + (session.hint(chunk) if session else "")
                mark = self._written
                out = self._stream(prompt, chunk)
                if self.stop_event.is_set():
                    break
                # Spia dei residui: un secondo tentativo se resta testo sorgente.
                if use_rag and out.strip() and raglin.contiene_residui(out, src, tgt):
                    residues += 1
                    GLib.idle_add(self._truncate, mark)
                    self._written = mark
                    out = self._stream(prompt + raglin.PROMEMORIA_RESIDUI, chunk)
                if use_rag and out.strip():
                    fixed, _notes = raglin.post_process(out, tgt, domain)
                    if fixed != out:
                        out = fixed
                        GLib.idle_add(self._truncate, mark)
                        self._written = mark
                        self._emit(fixed)
                if not out.strip():
                    break
                if session:
                    session.registra(out)
                done += 1
                if done < total:
                    self._emit("\n\n")
            ok = done == total and not self.stop_event.is_set()
        except (engine.EngineError, OSError) as e:
            key = e.key if isinstance(e, engine.EngineError) else "connection_error"
            GLib.idle_add(self._show_error, _(key), getattr(e, "detail", "") or str(e))
        GLib.idle_add(self._finish, ok, done, total, residues)

    def _progress(self, i, total, src, tgt):
        self.progress.set_fraction(i / max(total, 1))
        self.progress.set_text(_("progress", src=NATIVE[src], tgt=NATIVE[tgt], i=i + 1, n=total))

    def _append(self, text):
        self.dst_buf.insert(self.dst_buf.get_end_iter(), text)
        if self.dst_scroll:
            adj = self.dst_scroll.get_vadjustment()
            adj.set_value(adj.get_upper())

    def _truncate(self, mark):
        self.dst_buf.delete(self.dst_buf.get_iter_at_offset(mark), self.dst_buf.get_end_iter())

    def _finish(self, ok, done, total, residues=0):
        self.translating = False
        self.progress_bar.set_revealed(False)
        self._refresh_actions()
        if self.stop_event.is_set():
            msg = _("stopped", done=done, n=total)
        elif ok:
            msg = _("completed")
            if residues:
                msg += " " + _("residues_warn", n=residues)
        elif total:
            msg = _("partial", done=done, n=total)
        else:
            return
        self.toasts.add_toast(Adw.Toast(title=GLib.markup_escape_text(msg), timeout=6))

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
        group = Adw.PreferencesGroup(title=_("group_model"))
        self.models = engine.find_models()
        if self.cfg["model"] and self.cfg["model"] not in self.models:
            self.models.insert(0, self.cfg["model"])
        model_row = Adw.ComboRow(title=_("model"), use_subtitle=True, model=Gtk.StringList.new(
            [os.path.basename(p) for p in self.models] or [_("no_model")]),
            sensitive=bool(self.models))
        if self.cfg["model"] in self.models:
            model_row.set_selected(self.models.index(self.cfg["model"]))
        model_row.connect("notify::selected", lambda r, _p: self.models and
                          self._set_engine("model", self.models[r.get_selected()]))
        group.add(model_row)
        choose = Adw.ActionRow(title=_("choose_file"), subtitle=_("model_hint"), activatable=True)
        choose.add_suffix(Gtk.Image(icon_name="document-open-symbolic"))
        group.add(choose)
        page.add(group)

        eng = Adw.PreferencesGroup(title=_("group_engine"), description=_("engine_desc"))
        gpu = Adw.SwitchRow(title=_("gpu"), subtitle=_("gpu_sub"), active=self.cfg["gpu"])
        gpu.connect("notify::active", lambda r, _p: (
            self._set_engine("gpu", r.get_active()), self.device_row.set_sensitive(r.get_active())))
        eng.add(gpu)
        self.device_row = Adw.ComboRow(title=_("gpu_device"), use_subtitle=True,
                                       sensitive=self.cfg["gpu"])
        self._fill_device_row()
        self.device_row.connect("notify::selected", self._on_device)
        eng.add(self.device_row)
        threads = Adw.SpinRow.new_with_range(1, max(1, os.cpu_count() or 1), 1)
        threads.set_title(_("threads"))
        threads.set_subtitle(_("threads_sub", n=engine.physical_cores()))
        threads.set_value(min(self.cfg["threads"], os.cpu_count() or 1))
        threads.connect("notify::value", lambda r, _p: self._set_engine("threads", int(r.get_value())))
        eng.add(threads)
        ctx = Adw.ComboRow(title=_("context"), subtitle=_("context_sub"),
                           model=Gtk.StringList.new([f"{c:,}".replace(",", " ") for c in CONTEXTS]))
        ctx.set_selected(CONTEXTS.index(self.cfg["context"]) if self.cfg["context"] in CONTEXTS else 1)
        ctx.connect("notify::selected", lambda r, _p: self._set_engine("context", CONTEXTS[r.get_selected()]))
        eng.add(ctx)
        page.add(eng)

        quality = Adw.PreferencesGroup(title=_("group_quality"))
        rag = Adw.SwitchRow(title=_("rag"), subtitle=_("rag_sub"),
                            active=self.cfg["rag"] and raglin is not None,
                            sensitive=raglin is not None)
        rag.connect("notify::active", lambda r, _p: self._set("rag", r.get_active()))
        quality.add(rag)
        page.add(quality)

        dialog = Adw.PreferencesDialog(title=_("preferences").rstrip("…"))
        dialog.add(page)

        def choose_file(_row):
            fd = Gtk.FileDialog(title=_("choose_model_title"))
            filt = Gtk.FileFilter()
            filt.set_name(_("gguf_files"))
            filt.add_pattern("*.gguf")
            store = Gio.ListStore.new(Gtk.FileFilter)
            store.append(filt)
            fd.set_filters(store)

            def done(d, result):
                try:
                    path = d.open_finish(result).get_path()
                except GLib.Error:
                    return
                self._set_engine("model", path)
                dialog.close()
                self.show_preferences()
            fd.open(self, None, done)
        choose.connect("activated", choose_file)
        dialog.present(self)

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
        if self.cfg.get(key) == value:
            return
        self._set(key, value)
        if self.engine.running:
            self.needs_restart = True
        self._refresh_engine_ui()

    # ── finestre secondarie ───────────────────────────────────────────────
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
        for title, accel in ((_("open"), "<Control>o"), (_("save"), "<Control>s"),
                             (_("save_as"), "<Control><Shift>s"),
                             (_("translate"), "<Control>Return"), (_("stop"), "Escape"),
                             (_("swap"), "<Control>i"), (_("preferences"), "<Control>comma"),
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
        self.stop_translation()
        self.engine.stop(wait=True)
        w, h = self.get_default_size()
        self.cfg.update(width=w, height=h, maximized=self.is_maximized())
        save_settings(self.cfg)
        return False


# ── Applicazione ─────────────────────────────────────────────────────────────
class TranslatorApp(Adw.Application):
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
        # Tema scelto nelle preferenze (predefinito: segue il sistema), applicato
        # prima della finestra per non mostrarla nel tema sbagliato.
        apply_color_scheme(load_settings().get("theme", "system"))
        Adw.StyleManager.get_default().connect("notify::dark", lambda *_a: self.update_theme())
        self.connect("window-added", lambda *_a: self.update_theme())
        quit_action = Gio.SimpleAction.new("quit", None)
        quit_action.connect("activate", lambda *_a: [w.close() for w in self.get_windows()])
        self.add_action(quit_action)
        for action, accels in (("app.quit", ["<Control>q"]), ("window.close", ["<Control>w"]),
                               ("win.open", ["<Control>o"]), ("win.save", ["<Control>s"]),
                               ("win.save-as", ["<Control><Shift>s"]),
                               ("win.translate", ["<Control>Return"]), ("win.stop", ["Escape"]),
                               ("win.swap", ["<Control>i"]),
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
            for buf in (getattr(window, "src_buf", None), getattr(window, "dst_buf", None)):
                set_source_scheme(buf)

    def do_activate(self):
        (self.props.active_window or TranslatorWindow(self)).present()

    def do_open(self, files, _n, _hint):
        self.do_activate()
        if files:
            self.props.active_window.load_file(files[0].get_path())


def main():
    GLib.set_prgname(APP_ID)
    GLib.set_application_name(APP_NAME)
    return TranslatorApp().run(sys.argv)


if __name__ == "__main__":
    sys.exit(main())
