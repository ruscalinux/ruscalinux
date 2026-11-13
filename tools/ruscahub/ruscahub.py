#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
RuscaHub — Gestore di AppImage per RuscaLinux
Suite: RuscaTools | Sito: https://www.ruscalinux.org/
Autore: Nunzio Curcuruto (ruscalinux-dev) — © 2026 — GPL-3.0

Funzioni:
  * Apertura/importazione di AppImage (pulsante o drag & drop sulla finestra)
  * Copia automatica in ~/.ruscahub/apps/ (cartella nascosta nella Home)
  * Installazione (voce nel menu GNOME via file .desktop) e disinstallazione
  * Eliminazione: rimuove voce, file .desktop, icona e il file AppImage
  * Estrazione icone robusta: legge la chiave Icon= del .desktop interno,
    segue i collegamenti simbolici (.DirIcon), cerca in usr/share/icons e
    usr/share/pixmaps; usa unsquashfs (senza eseguire l'AppImage) e ripiega
    sul runtime --appimage-extract. Riparazione automatica delle voci già
    importate senza icona.
  * Interfaccia GNOME (libadwaita) con il tema comune RuscaLinux (style.css),
    modalità chiara/scura automatica, scorciatoie da tastiera
  * Eliminazione con conferma: il file AppImage va nel cestino
  * Internazionalizzazione: 26 lingue in lang/*.json, fallback en.json
    (override con variabile d'ambiente RUSCAHUB_LANG)

Requisiti: Python 3.10+, PyGObject, GTK 4.18+, libadwaita 1.7+
(Debian: python3-gi gir1.2-gtk-4.0 gir1.2-adw-1).
"""

import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gtk, Gdk, Gio, GLib

import os
import json
import gzip
import shutil
import struct
import subprocess
import threading
import uuid
import configparser
import tempfile
import re
from pathlib import Path

# ------------------------------------------------------------------ costanti
APP_ID      = "org.ruscalinux.RuscaHub"
APP_NAME    = "RuscaHub"
APP_VERSION = "1.99.3"
AUTHOR      = "Nunzio Curcuruto"
SITE_URI    = "https://www.ruscalinux.org/"
SITE_LABEL  = "ruscalinux.org"

BASE_DIR    = Path.home() / ".ruscahub"
APPS_DIR    = BASE_DIR / "apps"
ICONS_DIR   = BASE_DIR / "icons"
DB_FILE     = BASE_DIR / "ruscahub.json"
DESKTOP_DIR = Path(GLib.get_user_data_dir()) / "applications"   # ~/.local/share/applications
CONFIG_DIR  = Path(GLib.get_user_config_dir()) / "ruscahub"     # stato della finestra
WINDOW_STATE = CONFIG_DIR / "window.json"
DEFAULT_SIZE = (720, 560)

ICON_SCAN_VERSION = 2       # incrementare quando cambia la logica di estrazione icone

# ------------------------------------------------------------------ i18n
SCRIPT_DIR = Path(__file__).resolve().parent
STYLE_SRC  = SCRIPT_DIR / "style.css"          # tema comune RuscaLinux
ICON_SRC   = SCRIPT_DIR / "ruscahub.svg"
LANG_DIRS  = (SCRIPT_DIR / "lang", Path("/usr/share/ruscahub/lang"))
for _alt in (Path("/usr/share/ruscahub/style.css"),):
    if not STYLE_SRC.is_file() and _alt.is_file():
        STYLE_SRC = _alt

def _available_langs():
    """Le lingue sono i file di lang/ (en.json, it.json, zh_TW.json...): per
    aggiungerne una basta aggiungere il suo file (specifiche, sezione 9.1)."""
    for folder in LANG_DIRS:
        if folder.is_dir():
            found = {p.stem for p in folder.glob("*.json")}
            if found:
                return frozenset(found | {"en"})
    return frozenset({"en"})


SUPPORTED_LANGS = _available_langs()
# Ripieghi fra lingue vicine (specifiche, sezione 9.2): Hong Kong e Macao
# usano il cinese tradizionale, Singapore il semplificato; il portoghese
# senza variante legge il brasiliano, lo slovacco il ceco.
LANG_ALIASES = {"zh_HK": "zh_TW", "zh_MO": "zh_TW", "zh_SG": "zh_CN", "zh": "zh_CN",
                "pt": "pt_BR", "sk": "cs"}
RTL_LANGS = ("ar",)

# Copia interna di en.json: ultima rete di sicurezza se la cartella lang/ manca.
BUILTIN_EN = {
    "app_description": "AppImage manager with drag & drop import, storage in a hidden folder of the Home, and installation and uninstallation from the GNOME menu.",
    "ai_note": "Design, specifications and testing by the author; code written with the assistance of AI tools.",
    "add_appimage": "Add AppImage",
    "about_title": "About %s",
    "empty_title": "No AppImage archived",
    "empty_hint": "Drag an .AppImage file here or press “Add AppImage”.",
    "state_installed": "Installed",
    "state_archived": "Archived",
    "run_tooltip": "Run the AppImage",
    "install_tooltip": "Create or remove the entry in the GNOME menu",
    "remove_tooltip": "Delete: removes the menu entry and icon, moves the AppImage to the trash",
    "chooser_title": "Select one or more AppImage files",
    "cancel": "Cancel",
    "desktop_comment_default": "AppImage managed by RuscaHub",
    "shortcuts": "Keyboard Shortcuts",
    "main_menu": "Main Menu",
    "sc_close": "Close Window",
    "sc_quit": "Quit",
    "app_summary": "Manage AppImage applications",
    "desktop_keywords": "AppImage;applications;install;manager;launcher;",
    "list_title": "Your AppImages",
    "list_hint": "Drag more .AppImage files onto the window to add them.",
    "delete_heading": "Delete %s?",
    "delete_body": "The menu entry and the icon will be removed, and the AppImage file will be moved to the trash.",
    "delete": "Delete",
    "toast_added": "%s added",
    "toast_installed": "%s added to the applications menu",
    "toast_uninstalled": "%s removed from the applications menu",
    "toast_deleted": "%s moved to the trash",
    "toast_delete_failed": "Could not move %s to the trash",
    "toast_import_failed": "Could not import %s",
    "toast_not_appimage": "%s is not an AppImage file",
    "toast_launch_failed": "Could not start %s",
    "about_website": "Website",
    "about_support": "Support",
    "about_license": "License",
    "dev_note_title": "Development Note",
}



def _match_lang(raw):
    """Converte un nome di locale (it_IT.UTF-8, pt-BR, zh_TW…) in una lingua supportata."""
    n = raw.split(".")[0].split("@")[0].replace("-", "_").strip()
    base = n.split("_")[0]
    for code in (n, LANG_ALIASES.get(n), base, LANG_ALIASES.get(base)):
        if code in SUPPORTED_LANGS:
            return code
    return None


def _detect_lang():
    env = os.environ.get("RUSCAHUB_LANG", "").strip()
    if env:
        found = _match_lang(env)
        if found:
            return found
    try:
        names = GLib.get_language_names()
    except Exception:
        names = []
    for raw in names:
        found = _match_lang(raw)
        if found:
            return found
    return "en"


def _load_lang_file(code):
    for d in LANG_DIRS:
        f = d / f"{code}.json"
        if f.is_file():
            try:
                data = json.loads(f.read_text(encoding="utf-8"))
                if isinstance(data, dict):
                    return {str(k): str(v) for k, v in data.items()}
            except (OSError, ValueError):
                pass
    return {}


LANG = _detect_lang()
TR_EN = _load_lang_file("en")
TR = TR_EN if LANG == "en" else _load_lang_file(LANG)


def _(key):
    """Traduzione: lingua attiva → en.json → copia interna → chiave grezza (mai crash)."""
    return TR.get(key) or TR_EN.get(key) or BUILTIN_EN.get(key) or key


def _f(key, value):
    """Traduzione con un segnaposto %s; tollera traduzioni senza segnaposto."""
    return _(key).replace("%s", str(value), 1)

# ------------------------------------------------------------------ icone e stato finestra
def theme_has_icon(name=APP_ID):
    display = Gdk.Display.get_default()
    return display is not None and Gtk.IconTheme.get_for_display(display).has_icon(name)


def ensure_icon():
    """Avvio dai sorgenti: se il tema non conosce l'icona, la copia nel tema
    hicolor dell'utente. Se non riesce, si resta senza icona."""
    dest = Path(GLib.get_user_data_dir()) / "icons" / "hicolor" / "scalable" / "apps" / f"{APP_ID}.svg"
    if dest.exists() or not ICON_SRC.is_file():
        return
    try:
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ICON_SRC, dest)
    except OSError:
        pass


def app_icon_widget(path, size=32):
    """Icona di un'AppImage (PNG o SVG); ripiega sull'icona generica del tema."""
    if path and Path(path).is_file():
        try:
            tex = Gdk.Texture.new_from_filename(str(path))
            img = Gtk.Image.new_from_paintable(tex)
            img.set_pixel_size(size)
            img.add_css_class("lowres-icon")
            return img
        except GLib.Error:
            pass
    img = Gtk.Image.new_from_icon_name("application-x-executable")
    img.set_pixel_size(size)
    return img


def load_window_state():
    """Dimensione e stato massimizzato dell'ultima chiusura, o i predefiniti."""
    try:
        data = json.loads(WINDOW_STATE.read_text(encoding="utf-8"))
        w, h = int(data["width"]), int(data["height"])
        if 360 <= w <= 10000 and 294 <= h <= 10000:
            return w, h, bool(data.get("maximized", False))
    except (OSError, ValueError, KeyError, TypeError):
        pass
    return DEFAULT_SIZE[0], DEFAULT_SIZE[1], False


def save_window_state(width, height, maximized):
    try:
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        tmp = WINDOW_STATE.with_suffix(".tmp")
        tmp.write_text(json.dumps({"width": width, "height": height,
                                   "maximized": maximized}), encoding="utf-8")
        os.replace(tmp, WINDOW_STATE)
    except OSError:
        pass

# ------------------------------------------------------------------ meta AppImage
PNG_MAGIC = b"\x89PNG\r\n\x1a\n"
ICON_EXTS = (".png", ".svg", ".svgz", ".xpm")


def _squashfs_offset(path):
    """Offset del filesystem squashfs dentro un'AppImage di tipo 2 (fine dell'ELF)."""
    try:
        with open(path, "rb") as f:
            h = f.read(64)
            if len(h) < 52 or h[:4] != b"\x7fELF":
                return None
            end = "<" if h[5] == 1 else ">"
            if h[4] == 2:                                   # ELF64
                shoff = struct.unpack_from(end + "Q", h, 0x28)[0]
                shentsize, shnum = struct.unpack_from(end + "HH", h, 0x3A)
            elif h[4] == 1:                                 # ELF32
                shoff = struct.unpack_from(end + "I", h, 0x20)[0]
                shentsize, shnum = struct.unpack_from(end + "HH", h, 0x2E)
            else:
                return None
            off = shoff + shentsize * shnum
            f.seek(off)
            return off if f.read(4) == b"hsqs" else None
    except (OSError, struct.error):
        return None


class _Extractor:
    """Estrae singoli percorsi dall'AppImage in <tmp>/squashfs-root.

    method = "unsquashfs": legge il filesystem senza eseguire l'AppImage;
    method = "runtime"   : usa --appimage-extract del runtime dell'AppImage.
    """

    def __init__(self, app_path, tmp, method, offset=None):
        self.app = Path(app_path).resolve()
        self.tmp = Path(tmp)
        self.root = self.tmp / "squashfs-root"
        self.method = method
        self.offset = offset

    def extract(self, pattern):
        if self.method == "unsquashfs":
            cmd = ["unsquashfs", "-no-progress", "-no-xattrs", "-f",
                   "-o", str(self.offset), "-d", str(self.root),
                   str(self.app), pattern]
        else:
            cmd = [str(self.app), "--appimage-extract", pattern]
        try:
            subprocess.run(cmd, cwd=str(self.tmp), stdin=subprocess.DEVNULL,
                           capture_output=True, timeout=120)
        except (OSError, subprocess.SubprocessError):
            pass

    def resolve(self, rel):
        """File reale per `rel`; se è un symlink estrae e segue il bersaglio."""
        p = self.root / rel
        for _i in range(10):
            if p.is_symlink():
                target = os.readlink(p)
                if os.path.isabs(target):
                    nxt = self.root / target.lstrip("/")
                else:
                    nxt = p.parent / target
                nxt = Path(os.path.normpath(str(nxt)))
                try:
                    rel_next = nxt.relative_to(self.root)
                except ValueError:                          # fuori dall'AppImage
                    return None
                if not (nxt.exists() or nxt.is_symlink()):
                    self.extract(str(rel_next))
                p = nxt
                continue
            return p if p.is_file() else None
        return None


def _probe_icon(path):
    """(tipo, punteggio): SVG preferito, poi il PNG più grande."""
    try:
        with open(path, "rb") as f:
            head = f.read(4096)
    except OSError:
        return None, 0
    if head.startswith(PNG_MAGIC) and len(head) >= 24:
        return "png", struct.unpack(">I", head[16:20])[0]
    if head[:2] == b"\x1f\x8b":
        return "svgz", 100000
    if b"<svg" in head.lower():
        return "svg", 100000
    return None, 0


def _store_icon(src, kind, entry_id):
    for ext in (".png", ".svg"):                            # vecchie icone della voce
        (ICONS_DIR / f"{entry_id}{ext}").unlink(missing_ok=True)
    if kind == "png":
        dest = ICONS_DIR / f"{entry_id}.png"
        shutil.copyfile(src, dest)
        return dest
    data = Path(src).read_bytes()
    if kind == "svgz":
        data = gzip.decompress(data)
        if b"<svg" not in data[:4096].lower():
            return None
    dest = ICONS_DIR / f"{entry_id}.svg"
    dest.write_bytes(data)
    return dest


def _extract_with(ex, entry_id):
    """Un tentativo di estrazione con un metodo. None se non si è trovato nulla."""
    shutil.rmtree(ex.root, ignore_errors=True)
    found = {"name": "", "comment": "", "wmclass": "", "icon": None}

    # 1) .desktop interno (spesso è un symlink a usr/share/applications/…)
    icon_key = ""
    ex.extract("*.desktop")
    desk = None
    if ex.root.is_dir():
        for cand in sorted(ex.root.glob("*.desktop")):
            desk = ex.resolve(cand.name)
            if desk:
                break
    if desk:
        cp = configparser.ConfigParser(strict=False, interpolation=None)
        try:
            cp.read_string(desk.read_text(encoding="utf-8", errors="ignore"))
            if cp.has_section("Desktop Entry"):
                g = lambda k: cp.get("Desktop Entry", k, fallback="").strip()
                found["name"] = g("Name")
                found["comment"] = g("Comment")
                found["wmclass"] = g("StartupWMClass")
                icon_key = g("Icon")
        except configparser.Error:
            pass

    # 2) candidati icona: .DirIcon (seguendo i symlink) + nome dalla chiave Icon=
    cands = []
    ex.extract(".DirIcon")
    p = ex.resolve(".DirIcon")
    if p:
        cands.append(p)

    stem = Path(icon_key).name if icon_key else ""
    for ext in ICON_EXTS:
        if stem.lower().endswith(ext):
            stem = stem[: -len(ext)]
            break
    if stem and not any(ch in stem for ch in "*?[]\\"):
        patterns = (f"{stem}.*",
                    f"usr/share/icons/*/*/*/{stem}.*",
                    f"usr/share/pixmaps/{stem}.*")
        for pat in patterns:
            ex.extract(pat)
        if ex.root.is_dir():
            for pat in patterns:
                for c in sorted(ex.root.glob(pat)):
                    real = ex.resolve(str(c.relative_to(ex.root)))
                    if real and real not in cands:
                        cands.append(real)

    best, best_kind, best_score = None, None, -1
    for c in cands:
        kind, score = _probe_icon(c)
        if kind and score > best_score:
            best, best_kind, best_score = c, kind, score
    if best is not None:
        try:
            dest = _store_icon(best, best_kind, entry_id)
            found["icon"] = str(dest) if dest else None
        except (OSError, EOFError, ValueError):
            pass

    if not desk and not found["icon"]:
        return None
    return found


def extract_meta(app_path: Path, entry_id: str):
    """Estrae nome, commento, StartupWMClass e icona dall'AppImage."""
    default_name = re.sub(r"(?i)\.appimage$", "", Path(app_path).name)
    meta = {"name": default_name, "comment": "", "icon": None,
            "wmclass": "", "from_desktop": False}
    ICONS_DIR.mkdir(parents=True, exist_ok=True)
    tmp = Path(tempfile.mkdtemp(prefix="ruscahub-"))
    try:
        methods = []
        off = _squashfs_offset(app_path)
        if off is not None and shutil.which("unsquashfs"):
            methods.append(_Extractor(app_path, tmp, "unsquashfs", off))
        methods.append(_Extractor(app_path, tmp, "runtime"))
        for ex in methods:
            found = _extract_with(ex, entry_id)
            if not found:
                continue
            if found["name"] and not meta["from_desktop"]:
                meta["name"] = found["name"]
                meta["from_desktop"] = True
            meta["comment"] = meta["comment"] or found["comment"]
            meta["wmclass"] = meta["wmclass"] or found["wmclass"]
            if found["icon"]:
                meta["icon"] = found["icon"]
                break
    except Exception:
        pass
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    return meta

# ------------------------------------------------------------------ finestra Informazioni
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


# ------------------------------------------------------------------ finestra principale
class RuscaHubWindow(Adw.ApplicationWindow):

    def __init__(self, app):
        super().__init__(application=app, title=APP_NAME)
        self.app = app
        width, height, maximized = load_window_state()
        self.set_default_size(width, height)
        self.set_size_request(360, 294)
        if maximized:
            self.maximize()
        self.entries = {}          # id -> dict
        self._pending = 0

        for d in (BASE_DIR, APPS_DIR, ICONS_DIR, DESKTOP_DIR):
            d.mkdir(parents=True, exist_ok=True)

        # ---------- azioni della finestra
        for name, callback in (("add", lambda *_a: self.open_chooser()),
                               ("shortcuts", lambda *_a: self.show_shortcuts()),
                               ("about", lambda *_a: self.show_about())):
            action = Gio.SimpleAction.new(name, None)
            action.connect("activate", callback)
            self.add_action(action)

        # ---------- barra del titolo: azione principale a sinistra, menu a destra
        hb = Adw.HeaderBar()
        btn_add = Gtk.Button(icon_name="list-add-symbolic", action_name="win.add",
                             tooltip_text=_("add_appimage"))
        btn_add.update_property([Gtk.AccessibleProperty.LABEL], [_("add_appimage")])
        hb.pack_start(btn_add)
        menu = Gio.Menu()
        menu.append(_("shortcuts"), "win.shortcuts")
        menu.append(_f("about_title", APP_NAME), "win.about")
        hb.pack_end(Gtk.MenuButton(icon_name="open-menu-symbolic", menu_model=menu,
                                   primary=True, tooltip_text=_("main_menu")))
        self.spinner = Adw.Spinner(visible=False)
        hb.pack_end(self.spinner)

        # ---------- corpo: pagina vuota oppure elenco
        self.stack = Gtk.Stack(transition_type=Gtk.StackTransitionType.CROSSFADE)

        empty = Adw.StatusPage(title=_("empty_title"), description=_("empty_hint"))
        if theme_has_icon():
            empty.set_icon_name(APP_ID)
        else:
            empty.set_icon_name("application-x-executable-symbolic")
        empty_btn = Gtk.Button(label=_("add_appimage"), action_name="win.add",
                               halign=Gtk.Align.CENTER)
        empty_btn.add_css_class("pill")
        empty_btn.add_css_class("suggested-action")
        empty.set_child(empty_btn)
        self.stack.add_named(empty, "empty")

        page = Adw.PreferencesPage()
        self.group = Adw.PreferencesGroup(title=_("list_title"),
                                          description=_("list_hint"))
        page.add(self.group)
        self.stack.add_named(page, "list")
        self._rows = []

        view = Adw.ToolbarView(content=self.stack)
        view.add_top_bar(hb)
        self.toasts = Adw.ToastOverlay(child=view)
        self.set_content(self.toasts)

        # ---------- drag & drop
        drop = Gtk.DropTarget.new(Gdk.FileList, Gdk.DragAction.COPY)
        drop.connect("drop", self._on_drop)
        self.add_controller(drop)

        self.connect("close-request", self._on_close_request)

        self.load_db()
        self.refresh()
        self._repair_icons()

    # -------------------------------------------------- utilità UI
    def toast(self, text):
        self.toasts.add_toast(Adw.Toast(title=GLib.markup_escape_text(text)))

    def _set_pending(self, delta):
        self._pending = max(0, self._pending + delta)
        self.spinner.set_visible(self._pending > 0)

    def _on_close_request(self, *_a):
        width, height = self.get_default_size()
        save_window_state(width, height, self.is_maximized())
        return False

    def show_about(self):
        show_about_dialog(self, _, APP_ID, APP_NAME, APP_VERSION,
                          _("app_description"), theme_has_icon())

    def show_shortcuts(self):
        """Adw.ShortcutsDialog arriva con libadwaita 1.8: su trixie si usa un
        Adw.Dialog con righe normali."""
        group = Adw.PreferencesGroup()
        for title, accel in ((_("add_appimage"), "<Control>o"),
                             (_("shortcuts"), "<Control>question"),
                             (_("main_menu"), "F10"),
                             (_("sc_close"), "<Control>w"),
                             (_("sc_quit"), "<Control>q")):
            row = Adw.ActionRow(title=title)
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

    def confirm_delete(self, e):
        dialog = Adw.AlertDialog(heading=_f("delete_heading", e["name"]),
                                 body=_("delete_body"))
        dialog.add_response("cancel", _("cancel"))
        dialog.add_response("delete", _("delete"))
        dialog.set_response_appearance("delete", Adw.ResponseAppearance.DESTRUCTIVE)
        dialog.set_default_response("cancel")
        dialog.set_close_response("cancel")

        def on_response(_d, response):
            if response != "delete":
                return
            name = e["name"]
            if self.delete_entry(e):
                self.save_db()
                self.refresh()
                self.toast(_f("toast_deleted", name))
            else:
                self.toast(_f("toast_delete_failed", name))
        dialog.connect("response", on_response)
        dialog.present(self)

    def _on_toggle_menu(self, switch, _pspec, e):
        want = switch.get_active()
        if want == bool(e["installed"]):
            return
        if want:
            self.install(e)
            self.toast(_f("toast_installed", e["name"]))
        else:
            self._remove_desktop(e)
            if shutil.which("update-desktop-database"):
                subprocess.run(["update-desktop-database", str(DESKTOP_DIR)],
                               capture_output=True)
            self.toast(_f("toast_uninstalled", e["name"]))
        self.save_db()
        GLib.idle_add(self.refresh)

    # -------------------------------------------------- persistenza
    def load_db(self):
        if DB_FILE.is_file():
            try:
                data = json.loads(DB_FILE.read_text(encoding="utf-8"))
                for e in data:
                    if Path(e["path"]).is_file():
                        self.entries[e["id"]] = e
                    else:  # file sparito: pulizia silenziosa
                        self._remove_desktop(e)
            except Exception:
                self.entries = {}

    def save_db(self):
        DB_FILE.write_text(json.dumps(list(self.entries.values()), indent=2,
                                      ensure_ascii=False), encoding="utf-8")

    # -------------------------------------------------- importazione
    def open_chooser(self):
        filt = Gtk.FileFilter()
        filt.set_name("AppImage")
        filt.add_pattern("*.AppImage")
        filt.add_pattern("*.appimage")
        dlg = Gtk.FileDialog()                  # GTK 4.10+, usa il portale
        dlg.set_title(_("chooser_title"))
        store = Gio.ListStore.new(Gtk.FileFilter)
        store.append(filt)
        dlg.set_filters(store)
        dlg.open_multiple(self, None, self._on_files_chosen, None)

    def _on_files_chosen(self, dlg, res, _ud=None):
        try:
            model = dlg.open_multiple_finish(res)
            files = [model.get_item(i) for i in range(model.get_n_items())]
            self.import_files(files)
        except GLib.Error:
            pass

    def _on_drop(self, _t, value, _x, _y):
        if isinstance(value, Gdk.FileList):
            files = value.get_files()
        elif isinstance(value, Gio.File):
            files = [value]
        else:
            return False
        self.import_files(files)
        return True

    def import_files(self, gfiles):
        for gf in gfiles:
            p = gf.get_path()
            if p and Path(p).is_file() and p.lower().endswith(".appimage"):
                self._set_pending(+1)
                threading.Thread(target=self._import_worker,
                                 args=(Path(p),), daemon=True).start()
            else:
                self.toast(_f("toast_not_appimage", gf.get_basename() or "?"))

    def _import_worker(self, src: Path):
        try:
            eid = uuid.uuid4().hex[:8]
            dest = APPS_DIR / src.name
            if dest.exists():
                dest = APPS_DIR / f"{eid}-{src.name}"
            shutil.copy2(src, dest)
            os.chmod(dest, 0o755)
            meta = extract_meta(dest, eid)
            entry = {
                "id": eid,
                "name": meta["name"],
                "comment": meta["comment"],
                "filename": dest.name,
                "path": str(dest),
                "icon": meta["icon"],
                "wmclass": meta["wmclass"],
                "icon_scan": ICON_SCAN_VERSION,
                "installed": False,
                "desktop": None,
            }
            GLib.idle_add(self._finish_import, entry, src.name)
        except Exception:
            GLib.idle_add(self._finish_import, None, src.name)

    def _finish_import(self, entry, src_name):
        self._set_pending(-1)
        if entry:
            self.entries[entry["id"]] = entry
            self.save_db()
            self.refresh()
            self.toast(_f("toast_added", entry["name"]))
        else:
            self.toast(_f("toast_import_failed", src_name))
        return False

    # -------------------------------------------------- riparazione icone
    def _repair_icons(self):
        """Rianalizza (una sola volta) le voci senza icona importate con versioni precedenti."""
        todo = [dict(e) for e in self.entries.values()
                if e.get("icon_scan") != ICON_SCAN_VERSION
                and not (e.get("icon") and Path(e["icon"]).is_file())]
        if not todo:
            return
        self._set_pending(+1)
        threading.Thread(target=self._repair_worker, args=(todo,), daemon=True).start()

    def _repair_worker(self, todo):
        results = []
        for e in todo:
            try:
                results.append((e["id"], extract_meta(Path(e["path"]), e["id"])))
            except Exception:
                results.append((e["id"], None))
        GLib.idle_add(self._finish_repair, results)

    def _finish_repair(self, results):
        self._set_pending(-1)
        for eid, meta in results:
            e = self.entries.get(eid)
            if e is None:                       # eliminata nel frattempo
                continue
            e["icon_scan"] = ICON_SCAN_VERSION
            if not meta:
                continue
            if meta.get("icon"):
                e["icon"] = meta["icon"]
            if meta.get("wmclass"):
                e["wmclass"] = meta["wmclass"]
            default = re.sub(r"(?i)\.appimage$", "", e.get("filename", ""))
            if meta.get("from_desktop") and e.get("name") in ("", default):
                e["name"] = meta["name"]
            if not e.get("comment") and meta.get("comment"):
                e["comment"] = meta["comment"]
            if e.get("installed"):
                self.install(e)                 # riscrive il .desktop con Icon=
        self.save_db()
        self.refresh()
        return False

    # -------------------------------------------------- installa / disinstalla / elimina
    def _desktop_path(self, eid):
        return DESKTOP_DIR / f"ruscahub-{eid}.desktop"

    def install(self, e):
        def clean(v):
            return " ".join(str(v or "").split())          # niente a capo nel .desktop
        dp = self._desktop_path(e["id"])
        lines = [
            "[Desktop Entry]",
            "Type=Application",
            f"Name={clean(e['name'])}",
            f"Comment={clean(e.get('comment')) or _('desktop_comment_default')}",
            f'Exec="{e["path"]}" %U',
            "Terminal=false",
            "Categories=Utility;",
            "X-RuscaHub=true",
        ]
        if e.get("icon") and Path(e["icon"]).is_file():
            lines.insert(4, f"Icon={e['icon']}")
        if e.get("wmclass"):
            # associa la finestra in esecuzione alla voce (icona corretta nella dash)
            lines.append(f"StartupWMClass={clean(e['wmclass'])}")
        dp.write_text("\n".join(lines) + "\n", encoding="utf-8")
        os.chmod(dp, 0o644)
        e["installed"] = True
        e["desktop"] = str(dp)
        if shutil.which("update-desktop-database"):
            subprocess.run(["update-desktop-database", str(DESKTOP_DIR)],
                           capture_output=True)

    def _remove_desktop(self, e):
        dp = Path(e.get("desktop") or self._desktop_path(e["id"]))
        if dp.is_file():
            dp.unlink()
        e["installed"] = False
        e["desktop"] = None

    def delete_entry(self, e):
        """Sposta l'AppImage nel cestino, poi rimuove voce e icona.
        Se il cestino non è disponibile non cancella nulla: False."""
        app_file = Path(e["path"])
        if app_file.exists():
            try:
                Gio.File.new_for_path(str(app_file)).trash(None)
            except GLib.Error:
                return False
        self._remove_desktop(e)
        if e.get("icon") and Path(e["icon"]).is_file():
            try:
                Path(e["icon"]).unlink()
            except OSError:
                pass
        self.entries.pop(e["id"], None)
        if shutil.which("update-desktop-database"):
            subprocess.run(["update-desktop-database", str(DESKTOP_DIR)],
                           capture_output=True)
        return True

    def launch(self, e):
        try:
            os.chmod(e["path"], 0o755)
        except OSError:
            pass
        try:
            subprocess.Popen([e["path"]], start_new_session=True,
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except OSError:  # fallback senza FUSE
            try:
                subprocess.Popen([e["path"], "--appimage-extract-and-run"],
                                 start_new_session=True,
                                 stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            except OSError:
                self.toast(_f("toast_launch_failed", e["name"]))

    # -------------------------------------------------- UI
    def refresh(self):
        for row in self._rows:
            self.group.remove(row)
        self._rows = []

        if not self.entries:
            self.stack.set_visible_child_name("empty")
            return False
        self.stack.set_visible_child_name("list")

        for e in sorted(self.entries.values(), key=lambda x: x["name"].lower()):
            state = _("state_installed") if e["installed"] else _("state_archived")
            row = Adw.ActionRow(title=e["name"], subtitle=f"{state} · {e['filename']}",
                                use_markup=False, title_lines=1, subtitle_lines=1)
            row.set_tooltip_text(e["path"])
            row.add_prefix(app_icon_widget(e.get("icon"), 32))

            run = Gtk.Button(icon_name="media-playback-start-symbolic",
                             tooltip_text=_("run_tooltip"), valign=Gtk.Align.CENTER)
            run.add_css_class("flat")
            run.update_property([Gtk.AccessibleProperty.LABEL],
                                [f"{_('run_tooltip')}: {e['name']}"])
            run.connect("clicked", lambda _b, e=e: self.launch(e))
            row.add_suffix(run)

            switch = Gtk.Switch(active=bool(e["installed"]), valign=Gtk.Align.CENTER,
                                tooltip_text=_("install_tooltip"))
            switch.update_property([Gtk.AccessibleProperty.LABEL],
                                   [f"{_('install_tooltip')}: {e['name']}"])
            switch.connect("notify::active", self._on_toggle_menu, e)
            row.add_suffix(switch)

            trash = Gtk.Button(icon_name="user-trash-symbolic",
                               tooltip_text=_("remove_tooltip"), valign=Gtk.Align.CENTER)
            trash.add_css_class("flat")
            trash.update_property([Gtk.AccessibleProperty.LABEL],
                                  [f"{_('remove_tooltip')}: {e['name']}"])
            trash.connect("clicked", lambda _b, e=e: self.confirm_delete(e))
            row.add_suffix(trash)

            self.group.add(row)
            self._rows.append(row)
        return False

# ------------------------------------------------------------------ applicazione
class RuscaHubApp(Adw.Application):
    def __init__(self):
        super().__init__(application_id=APP_ID,
                         flags=Gio.ApplicationFlags.DEFAULT_FLAGS)

    def do_startup(self):
        Adw.Application.do_startup(self)
        if LANG in RTL_LANGS:
            Gtk.Widget.set_default_direction(Gtk.TextDirection.RTL)
        if not theme_has_icon():
            ensure_icon()
        # Tema comune RuscaLinux; se manca restano i colori di GNOME.
        if STYLE_SRC.is_file():
            provider = Gtk.CssProvider()
            provider.load_from_path(str(STYLE_SRC))
            Gtk.StyleContext.add_provider_for_display(
                Gdk.Display.get_default(), provider,
                Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)
        style = Adw.StyleManager.get_default()
        style.connect("notify::dark", lambda *_a: self.update_theme())
        self.connect("window-added", lambda *_a: self.update_theme())

        quit_action = Gio.SimpleAction.new("quit", None)
        quit_action.connect("activate", lambda *_a: [w.close() for w in self.get_windows()])
        self.add_action(quit_action)
        for action, accels in (("app.quit", ["<Control>q"]),
                               ("window.close", ["<Control>w"]),
                               ("win.add", ["<Control>o"]),
                               ("win.shortcuts", ["<Control>question"])):
            self.set_accels_for_action(action, accels)

    def update_theme(self):
        dark = Adw.StyleManager.get_default().get_dark()
        for window in self.get_windows():
            window.remove_css_class("rusca-light" if dark else "rusca-dark")
            window.add_css_class("rusca-dark" if dark else "rusca-light")

    def do_activate(self):
        # Una sola finestra: un secondo avvio la riporta in primo piano.
        win = self.props.active_window or RuscaHubWindow(self)
        win.present()


if __name__ == "__main__":
    RuscaHubApp().run(None)
