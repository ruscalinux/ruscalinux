#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# RuscaWriter — three-column writing editor for non-fiction
# Copyright (C) 2026  Nunzio Curcuruto
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.

"""
RuscaWriter — GTK 4 user interface / interfaccia grafica GTK 4
Versione / Version: vedi model.APP_VERSION_SHORT / see model.APP_VERSION_SHORT
Autore / Author: Nunzio Curcuruto

EN — Three-column writing editor built with Python + GTK 4 (PyGObject),
with no extra graphical libraries.

 - Left column   : list of the project's chapters/sections.
 - Center column : writing area for the text (black serif).
 - Right column  : notes attached to the selected chapter.

Project format: an .rwr file = a tar.gz archive containing
    01.md  01n.md    (chapter 01 text + its note)
    02.md  02n.md
    ...
    img_001.png ...  (images attached to the chapters)
    cover.png/jpg/webp, meta.json, frontispiece.json, colophon.json

This module was ported from GTK 3 to GTK 4. Main differences:
  - Gtk.Application / Gtk.ApplicationWindow as the app skeleton.
  - Menus built with Gio.Menu + Gtk.PopoverMenuBar and GAction; shortcuts
    registered with app.set_accels_for_action.
  - Asynchronous dialogs (Dialog.run() no longer exists in GTK 4): themed
    windows with callbacks, and Gtk.FileDialog for open/save.
  - set_child()/append() instead of add()/pack_start().
  - Chapter list with Gtk.ListView + Gtk.StringList + Gtk.SingleSelection.
  - Events via controllers (GestureClick) instead of event signals.

IT — Editor di scrittura a tre colonne scritto in Python + GTK 4
(PyGObject), senza librerie grafiche aggiuntive.

 - Colonna sinistra : elenco dei capitoli/sezioni del progetto.
 - Colonna centrale : area di scrittura del testo (serif nero).
 - Colonna destra   : note relative al capitolo selezionato.

Formato progetto: file .rwr = archivio tar.gz contenente
    01.md  01n.md    (testo capitolo 01 + sua nota)
    02.md  02n.md
    ...
    img_001.png ...  (immagini allegate ai capitoli)
    cover.png/jpg/webp, meta.json, frontispiece.json, colophon.json

Questo modulo e' stato portato da GTK 3 a GTK 4. Differenze principali:
  - Gtk.Application / Gtk.ApplicationWindow come struttura dell'app.
  - Menu costruiti con Gio.Menu + Gtk.PopoverMenuBar e GAction; le scorciatoie
    sono registrate con app.set_accels_for_action.
  - Dialoghi asincroni (Dialog.run() non esiste piu' in GTK 4): finestre con
    il nostro tema e callback, e Gtk.FileDialog per aprire/salvare.
  - set_child()/append() al posto di add()/pack_start().
  - Lista capitoli con Gtk.ListView + Gtk.StringList + Gtk.SingleSelection.
  - Eventi tramite controller (GestureClick) invece dei segnali event.
"""

import os
import re
import sys
import json
import locale
import shutil
import threading

import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gtk, Gdk, Pango, GLib, Gio
try:
    gi.require_version("GdkPixbuf", "2.0")
    from gi.repository import GdkPixbuf
except Exception:
    GdkPixbuf = None

# GtkSourceView 5: serve come vista di scrittura quando si usa libspelling,
# perche' il suo adapter richiede un GtkSource.Buffer. E' opzionale: se manca,
# si usa un normale Gtk.TextView e il controllo ortografico resta inattivo.
try:
    gi.require_version("GtkSource", "5")
    from gi.repository import GtkSource
except Exception:
    GtkSource = None

# Controllo ortografico opzionale.
#
# ATTENZIONE alla versione: con GTK 4 NON si possono usare ne' GtkSpell ne'
# Gspell 1.x, perche' quei binding sono compilati contro GTK 3 (caricarli dopo
# GTK 4 fallisce con "Requiring namespace 'Gtk' version '3.0', but '4.0' is
# already loaded"). Il backend giusto per GTK 4 e' libspelling (namespace
# 'Spelling'), la stessa libreria usata da GNOME Text Editor; in subordine si
# tenta Gspell 2.x (namespace 'Gspell' versione '2'), che e' la prima serie di
# Gspell compatibile con GTK 4.
#
#   Debian/Ubuntu (libspelling): sudo apt install gir1.2-spelling-1 \
#                                 hunspell-it hunspell-en-us
#
# SPELL_BACKEND vale "spelling" | "gspell2" | None.
SPELL_BACKEND = None
Spelling = None
Gspell = None
try:
    gi.require_version("Spelling", "1")
    from gi.repository import Spelling
    SPELL_BACKEND = "spelling"
except Exception:
    Spelling = None
    try:
        # solo Gspell 2.x e' compatibile con GTK 4 (la 1.x e' legata a GTK 3)
        gi.require_version("Gspell", "2")
        from gi.repository import Gspell
        SPELL_BACKEND = "gspell2"
    except Exception:
        Gspell = None
        SPELL_BACKEND = None
HAVE_SPELL = SPELL_BACKEND is not None
HAVE_GTKSPELL = HAVE_SPELL   # nome storico mantenuto per compatibilita'

from . import model as pw_model
from .model import (
    APP_NAME, APP_VERSION, APP_VERSION_SHORT, APP_AUTHOR,
    TYPEWRITER_FAMILY, TYPEWRITER_FILE, TYPEWRITER_FILES,
    SERIF_FILES,
    MIN_FONT_SIZE, MAX_FONT_SIZE,
    PDF_PAGE_SIZES, PDF_DEFAULT_PAGE_SIZE, PDF_PAGE_SIZE_LABELS,
    Project, read_ttf_metrics,
    TYPEWRITER_FAMILY as _TW_FAMILY, SERIF_FAMILY,
    system_font_families, font_files_for_family,
    HAVE_PYPHEN, hyphenation_available,
)
# EN/IT: the two themes (Ametista, Classico), each in a light and
# a dark version. All colours come from theme_palette(): the interface never
# writes a colour of its own.
# I due temi (Ametista, Classico), ciascuno in versione chiara e
# scura. Tutti i colori arrivano da theme_palette(): l'interfaccia non scrive
# mai un colore per conto suo.
from .model import (
    DEFAULT_THEME, theme_palette, build_css, resolve_theme,
    theme_label as model_theme_label,
)
# EN/IT: page margins, in millimetres / margini di pagina, in millimetri
from .model import (
    MARGIN_SIDES, MARGIN_MIN_MM, MARGIN_MAX_MM, GUTTER_MAX_MM,
    MARGIN_PRESETS, MARGIN_PRESET_CUSTOM, CPL_COMFORT,
    margin_preset, margin_problems, text_block_mm, chars_per_line,
    which_margin_preset, page_size_mm, normalize_page_margins,
)
# EN/IT: the Markdown rules, shared with every export: the preview and the
# live highlighting must show what the exports will produce.
# Le regole del Markdown, in comune con tutti gli export: anteprima ed
# evidenziazione devono mostrare cio' che gli export produrranno.
# EN/IT: picture boxes for the preview / riquadri delle immagini nell'anteprima
from . import rusca_liveblocks
from .model import (classify_md_line, book_blocks, highlight_spans, list_lines,
                    plain_runs, wrapped_runs, unwrap_hard_breaks)
from .i18n import apply_toolkit_language
from .i18n import (Translator, LANGUAGES, LOCALE_ALIASES, available_languages,
                   spell_locale_for,
                   RTL_LANGUAGES, COMPLETE_LANGUAGES, ASSETS_DIR)
# EN/IT: the MDict reader. Like model.py it never imports GTK and uses only
# the standard library, so the dictionary works with the machine unplugged
# and adds nothing to install. / Il lettore MDict. Come model.py non importa
# mai GTK e usa solo la libreria standard, così il dizionario funziona a
# macchina scollegata e non aggiunge niente da installare.
from . import mdict as pw_mdict
from .mdict import MdxError

APP_ID = "org.ruscalinux.RuscaWriter"
# RuscaWriter fa parte dei RuscaLinux OS Tools: sito, sorgenti e
# segnalazioni sono quelli di RuscaLinux (non c'e' piu' un progetto separato).
APP_WEBSITE = "https://www.ruscalinux.org/"
APP_SOURCE = "https://github.com/ruscalinux/ruscalinux"
APP_ISSUES = "https://github.com/ruscalinux/ruscalinux/issues"
STYLE_SRC = os.path.join(ASSETS_DIR, "style.css")    # tema comune RuscaLinux
# Componenti esterni inclusi (specifiche, sezioni 3.10 e 6)
COMPONENTS = (
    ("EB Garamond", "SIL Open Font License 1.1",
     "https://github.com/octaviopardo/EBGaramond12"),
    ("Courier Prime", "SIL Open Font License 1.1",
     "https://github.com/quoteunquoteapps/CourierPrime"),
)

# Icona: quella del tema (App ID). Avviando dai sorgenti, ensure_icon() la
# copia nel tema hicolor dell'utente.
ICON_FILE = os.path.join(ASSETS_DIR, "ruscawriter.svg")


def theme_has_icon(name=APP_ID):
    display = Gdk.Display.get_default()
    return display is not None and Gtk.IconTheme.get_for_display(display).has_icon(name)


def ensure_icon():
    dest = os.path.join(GLib.get_user_data_dir(), "icons", "hicolor", "scalable",
                        "apps", f"{APP_ID}.svg")
    if os.path.exists(dest) or not os.path.isfile(ICON_FILE):
        return
    try:
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        shutil.copyfile(ICON_FILE, dest)
    except OSError:
        pass


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


class RuscaDialog(Adw.Dialog):
    """Dialogo GNOME (Adw.Dialog con barra del titolo) che offre i metodi di
    Gtk.Window usati dai dialoghi di RuscaWriter: set_child, present,
    destroy, set_default_size, connect("close-request"). Cosi' i dialoghi
    complessi (sezioni, impaginazione, dizionari, copertina, guida Markdown)
    diventano nativi senza riscriverli."""

    def __init__(self, parent, title="", size=None):
        super().__init__(title=title or "")
        self._parent = parent
        self._view = Adw.ToolbarView()
        self._view.add_top_bar(Adw.HeaderBar())
        Adw.Dialog.set_child(self, self._view)
        self._close_handlers = []
        Adw.Dialog.connect(self, "closed", self._on_closed)
        if size:
            self.set_default_size(*size)

    def set_child(self, widget):
        scroller = Gtk.ScrolledWindow(child=widget, propagate_natural_height=True,
                                      propagate_natural_width=True,
                                      hscrollbar_policy=Gtk.PolicyType.NEVER)
        self._view.set_content(scroller)

    def set_default_size(self, width, height=-1):
        if width and width > 0:
            self.set_content_width(width)
        if height and height > 0:
            self.set_content_height(height)

    def set_resizable(self, _value):
        pass

    def present(self, *_a):
        Adw.Dialog.present(self, self._parent)

    def destroy(self):
        self.force_close()

    def connect(self, signal, callback, *args):
        if signal == "close-request":
            self._close_handlers.append((callback, args))
            return 0
        return Adw.Dialog.connect(self, signal, callback, *args)

    def _on_closed(self, _dialog):
        for callback, args in self._close_handlers:
            callback(self, *args)


DEFAULT_FONT_SIZE = 14


def register_bundled_font():
    """Registra i font .ttf della cartella assets/. True se il Regular c'e'."""
    here = ASSETS_DIR
    try:
        import ctypes
        try:
            fc = ctypes.CDLL("libfontconfig.so.1")
        except OSError:
            fc = ctypes.CDLL("libfontconfig.so")
        fc.FcConfigAppFontAddFile.restype = ctypes.c_int
        fc.FcConfigAppFontAddFile.argtypes = [ctypes.c_void_p, ctypes.c_char_p]
        regular_ok = False
        for style, fname in TYPEWRITER_FILES.items():
            path = os.path.join(here, fname)
            if os.path.exists(path):
                ok = bool(fc.FcConfigAppFontAddFile(None, path.encode("utf-8")))
                if style == "regular":
                    regular_ok = ok
        # registra anche il serif EB Garamond, cosi' eventuali anteprime di
        # EPUB/HTML aperte sullo stesso sistema possono usarlo per nome.
        for fname in SERIF_FILES.values():
            path = os.path.join(here, fname)
            if os.path.exists(path):
                fc.FcConfigAppFontAddFile(None, path.encode("utf-8"))
        return regular_ok
    except Exception:
        return os.path.exists(os.path.join(here, TYPEWRITER_FILE))


LEFT_FRAC   = 0.20
RIGHT_FRAC  = 0.22
LEFT_MIN_PX  = 180
RIGHT_MIN_PX = 200
# EN: the centre column is what the program is for. Left and right were each
#     capped at 40% of the width, but INDEPENDENTLY: together they could take
#     80% and squeeze the writing area into a sliver. This is the floor the
#     text keeps, whatever the side columns ask for.
# IT: la colonna centrale e' il motivo per cui il programma esiste. Sinistra e
#     destra erano capate ciascuna al 40% della larghezza, ma in modo
#     INDIPENDENTE: insieme potevano prendersene l'80% e ridurre l'area di
#     scrittura a una fessura. Questo e' il minimo che il testo conserva,
#     qualunque cosa chiedano le colonne laterali.
CENTER_MIN_PX = 360


def _vista_che_segue_la_larghezza(base):
    """EN — the editor view, which calls back whenever it receives a new
    width. The reading margins depend on the real width of the text area,
    and that changes for many reasons: the window being maximized at start,
    resized, the side columns moved or hidden. Measuring only at start and
    when a divider moves left the margins computed on a provisional width
    (a column much narrower than intended) until the next divider move.
    IT — la vista dell'editor, che avvisa ogni volta che riceve una nuova
    larghezza. I margini di lettura dipendono dalla larghezza vera dell'area
    del testo, e questa cambia per molti motivi: la finestra che si
    massimizza all'avvio, il ridimensionamento, le colonne laterali spostate
    o nascoste. Misurarla solo all'avvio e quando si sposta un divisore
    lasciava i margini calcolati su una larghezza provvisoria (una colonna
    molto piu' stretta del previsto) fino al divisore successivo."""
    class Vista(base):
        def __init__(self, on_width, **kwargs):
            super().__init__(**kwargs)
            self._on_width = on_width
            self._ultima_larghezza = -1

        def do_size_allocate(self, width, height, baseline):
            base.do_size_allocate(self, width, height, baseline)
            if width != self._ultima_larghezza:
                self._ultima_larghezza = width
                # dopo l'allocazione, non durante: cambiare i margini qui
                # dentro chiederebbe un'altra allocazione mentre GTK la fa
                GLib.idle_add(self._on_width)
    return Vista


def split_columns(total, left_px=None, right_px=None,
                  left_visible=True, right_visible=True):
    """Larghezza delle tre colonne, dato lo spazio disponibile.

    Restituisce (sinistra, centro, destra) in pixel. Sta fuori dal widget di
    proposito: cosi' la regola si prova con dei numeri, senza aver bisogno di
    una finestra vera, ed e' li' che si era nascosto l'errore.

    La regola: le colonne laterali chiedono, la centrale decide. Se insieme
    lascerebbero al testo meno di CENTER_MIN_PX, le laterali si restringono in
    proporzione. Su una finestra troppo stretta perche' il minimo stia in
    piedi, si cede anche su quello, ma sempre a partire dai lati.
    """
    if total <= 1:
        return (0, max(0, total), 0)

    left_w = 0
    if left_visible:
        left_w = max(LEFT_MIN_PX,
                     min(left_px or int(total * LEFT_FRAC), int(total * 0.4)))
    right_w = 0
    if right_visible:
        right_w = max(RIGHT_MIN_PX,
                      min(right_px or int(total * RIGHT_FRAC), int(total * 0.4)))

    minimo = min(CENTER_MIN_PX, max(1, total - LEFT_MIN_PX - RIGHT_MIN_PX))
    centro = total - left_w - right_w
    if centro < minimo and (left_w + right_w) > 0:
        da_togliere = minimo - centro
        somma = left_w + right_w
        if left_w:
            left_w = max(LEFT_MIN_PX,
                         left_w - int(da_togliere * left_w / somma) - 1)
        if right_w:
            right_w = max(RIGHT_MIN_PX,
                          right_w - int(da_togliere * right_w / somma) - 1)
        # finestra molto stretta: si cede anche sui minimi laterali
        eccesso = (total - left_w - right_w) - minimo
        if eccesso < 0 and right_w:
            right_w = max(0, right_w + eccesso)
        eccesso = (total - left_w - right_w) - minimo
        if eccesso < 0 and left_w:
            left_w = max(0, left_w + eccesso)
    return (left_w, total - left_w - right_w, right_w)
READING_MAX_PX = 980          # ripiego, se il font non si puo' misurare

# EN — reading comfort. A line of 60–75 characters is the measure that books
#      use: longer lines make the eye lose the start of the next one. The
#      column is measured in CHARACTERS of the chosen font, so it stays right
#      at any size and with any typeface. Line spacing around 1.5 lets the
#      eye travel back without slipping a line.
# IT — comodita' di lettura. Una riga di 60–75 caratteri e' la misura dei
#      libri: righe piu' lunghe fanno perdere all'occhio l'inizio della
#      successiva. La colonna si misura in CARATTERI del font scelto, cosi'
#      resta giusta a ogni corpo e con ogni carattere. Un'interlinea intorno
#      a 1,5 lascia tornare l'occhio a capo senza scivolare di una riga.
READING_MEASURE_CHARS = 68
# EN — the user chooses between two measures, both within the comfortable
#      45–80 range: Normal (the book measure, default) and Wide.
# IT — l'utente sceglie fra due misure, entrambe nella fascia comoda 45–80:
#      Normale (la misura dei libri, predefinita) e Larga.
READING_WIDTHS = {"normal": READING_MEASURE_CHARS, "wide": 80}
READING_LINE_SPACING = 1.5


def _config_path():
    base = os.environ.get("XDG_CONFIG_HOME") or os.path.expanduser("~/.config")
    # Cartella di configurazione dell'applicazione.
    d = os.path.join(base, "ruscawriter")
    try:
        os.makedirs(d, exist_ok=True)
    except Exception:
        pass
    return os.path.join(d, "settings.json")


PT_PER_MM_UI = 72.0 / 25.4   # punti tipografici per millimetro

# EN/IT: the three appearances / i tre aspetti
APPEARANCES = ("auto", "light", "dark")


def _gnome_interface_settings():
    """EN: GNOME's "org.gnome.desktop.interface" settings, or None when the
    schema is not installed (another desktop): asking for a missing schema
    would abort the program, so it is looked up first.
    IT: le impostazioni "org.gnome.desktop.interface" di GNOME, o None se lo
    schema non c'e' (altro desktop): chiedere uno schema assente farebbe
    chiudere il programma, quindi prima lo si cerca."""
    try:
        sorgente = Gio.SettingsSchemaSource.get_default()
        schema = sorgente.lookup("org.gnome.desktop.interface", True) \
            if sorgente else None
        if schema is None or not schema.has_key("color-scheme"):
            return None
        return Gio.Settings.new("org.gnome.desktop.interface")
    except Exception:
        return None


def default_dict_folder():
    """EN: where dictionaries are kept by default.

    Not in the configuration folder: an .mdx is data, often hundreds of
    megabytes, and configuration folders are for small files people back up.
    The XDG data folder is the right place, and the user can point this
    somewhere else — an external disk, a shared folder — from
    View → Dictionaries.

    IT: dove si tengono i dizionari, se non si sceglie altro.

    Non nella cartella di configurazione: un .mdx è un dato, spesso centinaia
    di megabyte, e le cartelle di configurazione sono per file piccoli, di
    quelli che si mettono nei backup. La cartella dati XDG è il posto giusto,
    e l'utente può spostarla altrove — un disco esterno, una cartella
    condivisa — da Visualizza → Dizionari."""
    base = (os.environ.get("XDG_DATA_HOME")
            or os.path.expanduser("~/.local/share"))
    return os.path.join(base, "ruscawriter", "dictionaries")


def load_settings():
    try:
        with open(_config_path(), "r", encoding="utf-8") as f:
            data = json.load(f)
        # EN/IT: a damaged file must not crash the start / un file rovinato
        # non deve bloccare l'avvio
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def save_settings(data):
    """EN/IT: written to a temporary file and renamed: an interruption never
    leaves half a configuration / scritto in un file provvisorio e rinominato:
    un'interruzione non lascia mai mezza configurazione."""
    path = _config_path()
    tmp = path + ".tmp"
    try:
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
        os.replace(tmp, path)
    except Exception:
        try:
            os.remove(tmp)
        except OSError:
            pass


def detect_system_language():
    # Le lingue di sistema nell'ordine di GTK (specifiche, sezione 9.2):
    # prima LANGUAGE, poi LC_ALL, LC_MESSAGES, LANG. Prima si leggevano
    # nell'ordine inverso, e LANGUAGE (la variabile per scegliere la lingua
    # delle applicazioni) veniva ignorata se LANG era impostata.
    candidates = [n for n in GLib.get_language_names() if n not in ("C", "POSIX")]
    try:
        loc = locale.getlocale()[0]
        if not loc and hasattr(locale, "getdefaultlocale"):
            loc = locale.getdefaultlocale()[0]
        if loc:
            candidates.append(loc)
    except Exception:
        pass
    # mappa codice-minuscolo -> chiave reale in LANGUAGES
    # (cosi' "zh_cn" trova "zh_CN" e "pt_br" trova "pt_BR")
    lookup = {k.lower(): k for k in LANGUAGES}
    for c in candidates:
        if not c:
            continue
        base = c.split(".")[0].split("@")[0].lower()   # es. "zh_hk", "pt_br", "it_it"
        lang_only = base.split("_")[0]                  # solo la lingua (it, en, fr...)
        # variante piena (zh_CN), suo ripiego (zh_HK -> zh_TW), lingua,
        # ripiego della lingua (pt -> pt_BR, sk -> cs)
        # solo lingue tradotte davvero (COMPLETE_LANGUAGES, calcolato dai
        # file): come negli altri programmi, se la traduzione manca si prova
        # la candidata successiva
        for cand in (base, LOCALE_ALIASES.get(base), lang_only, LOCALE_ALIASES.get(lang_only)):
            if not cand:
                continue
            code = cand if cand in LANGUAGES else lookup.get(cand.lower())
            if code and code in COMPLETE_LANGUAGES:
                return code
    return "en"

# ---- correzione dell'elisione (italiano, francese) -------------------------
# Perche' serve: il controllo ortografico di GTK 4 (libspelling) usa ICU per
# spezzare il testo in parole, e ICU taglia sull'apostrofo. Cosi' "dell'anima"
# diventa due token, "dell" e "anima", e "dell" da solo non e' nel dizionario:
# viene segnalato come errore. La vecchia versione GTK 3 (Gspell) usava invece
# la segmentazione di Pango, che scartava il frammento di elisione, quindi il
# problema non si vedeva.
#
# Soluzione indipendente dalla libreria: aggiungiamo i frammenti di elisione
# (dell, quell, nell, j, qu, ...) alle "parole personali" di Enchant, che e' il
# motore dei dizionari sotto libspelling. Enchant carica automaticamente il
# file <config>/<locale>.dic (una parola per riga) e lo somma al dizionario.

# Frammenti che restano a sinistra dell'apostrofo, per lingua di base.
_ELISION_FRAGMENTS = {
    # Italiano: articoli e preposizioni articolate elise, pronomi, troncamenti
    # e apocopi piu' comuni.
    "it": [
        "l", "un", "dell", "nell", "all", "dall", "sull", "coll", "pell",
        "quell", "quest", "bell", "sant", "tutt", "anch", "dov", "com",
        "cos", "po", "be", "mo", "ce", "ne", "se", "gliel", "me", "te",
        "buon", "gran", "fin", "senz", "grand", "vent", "cent",
    ],
    # Francese: elisioni obbligatorie dei monosillabi grammaticali.
    "fr": [
        "l", "d", "j", "n", "s", "c", "t", "m", "qu", "jusqu", "lorsqu",
        "puisqu", "quoiqu", "presqu", "quelqu", "aujourd",
    ],
}


def _elision_words_for(base_lang):
    """Restituisce l'insieme dei frammenti di elisione per una lingua base
    (es. 'it'), includendo le varianti con iniziale maiuscola (inizio frase:
    'Dell'', 'L'') e tutto maiuscolo, cosi' non vengono segnalate nemmeno li'."""
    frags = _ELISION_FRAGMENTS.get(base_lang, [])
    out = set()
    for w in frags:
        out.add(w)
        out.add(w.capitalize())
        out.add(w.upper())
    return out


def _enchant_config_dir():
    """Cartella di configurazione di Enchant dove finiscono le liste personali.
    Rispetta ENCHANT_CONFIG_DIR, poi XDG_CONFIG_HOME, infine ~/.config."""
    env = os.environ.get("ENCHANT_CONFIG_DIR")
    if env:
        return env
    base = os.environ.get("XDG_CONFIG_HOME") or os.path.expanduser("~/.config")
    return os.path.join(base, "enchant")


# File "collaterale" in cui teniamo traccia delle parole che ABBIAMO aggiunto
# noi, per poterle gestire in modo idempotente SENZA sporcare il file .dic che
# Enchant legge. Importante: nel file .dic le parole vanno scritte "nude", una
# per riga, perche' Enchant interpreta '#' come commento SOLO a inizio riga: un
# commento a fine riga finirebbe dentro la parola e la renderebbe inutile.
_ELISION_SIDECAR_SUFFIX = ".ruscawriter-added"


def ensure_elision_dictionaries(locales):
    """Per ciascun locale dato (es. 'it_IT', 'fr_FR'), assicura che la lista
    personale di Enchant <config>/<locale>.dic contenga i frammenti di elisione
    di quella lingua, scritti come parole nude (una per riga).

    Idempotente e non distruttiva: le parole aggiunte dall'utente restano; le
    nostre vengono ricalcolate. Per distinguerle senza inquinare il .dic,
    teniamo l'elenco delle nostre parole in un file collaterale
    <locale>.dic.ruscawriter-added accanto.

    Restituisce la lista dei file .dic effettivamente scritti/aggiornati."""
    written = []
    try:
        cfg = _enchant_config_dir()
        os.makedirs(cfg, exist_ok=True)
    except Exception:
        return written

    for loc in locales:
        base = loc.split("_")[0].lower()
        words = _elision_words_for(base)
        if not words:
            continue
        path = os.path.join(cfg, f"{loc}.dic")
        sidecar = path + _ELISION_SIDECAR_SUFFIX

        # parole attualmente nel .dic (tutte, nude)
        current = []
        current_set = set()
        raw_lines = []          # righe grezze sul disco (per capire se "sporco")
        try:
            if os.path.exists(path):
                with open(path, "r", encoding="utf-8") as f:
                    for raw in f:
                        raw_lines.append(raw.rstrip("\n"))
                        line = raw.strip()
                        if not line or line.startswith("#"):
                            continue
                        # MIGRAZIONE da una versione precedente che, per errore,
                        # scriveva un commento a fine riga ("dell  # ...-elision"):
                        # quelle righe sono inutili per Enchant. Le ripuliamo
                        # tenendo solo la parola prima del '#'.
                        if "#" in line:
                            line = line.split("#", 1)[0].strip()
                            if not line:
                                continue
                        # una riga con piu' token non e' valida: prendi la prima
                        parts = line.split()
                        w = parts[0] if parts else ""
                        if w and w not in current_set:
                            current.append(w)
                            current_set.add(w)
        except Exception:
            current, current_set, raw_lines = [], set(), []

        # parole che avevamo aggiunto noi in passato (dal collaterale)
        prev_ours = set()
        try:
            if os.path.exists(sidecar):
                with open(sidecar, "r", encoding="utf-8") as f:
                    for raw in f:
                        w = raw.strip()
                        if w and not w.startswith("#"):
                            prev_ours.add(w)
        except Exception:
            prev_ours = set()

        # parole "dell'utente" = quelle presenti che NON erano nostre
        user_words = [w for w in current if w not in prev_ours]
        user_set = set(user_words)

        # nostre parole da garantire: tutti i frammenti che l'utente non abbia
        # gia' inserito a mano (per non duplicarli)
        our_words = sorted(w for w in words if w not in user_set)

        # contenuto desiderato del .dic = parole utente + nostre
        desired = user_words + [w for w in our_words if w not in user_set]

        # Il file su disco e' gia' "pulito e giusto" solo se le righe grezze
        # coincidono esattamente con le parole desiderate (nessun commento,
        # nessun marcatore, nessun ordine diverso). In caso contrario riscrivi.
        clean_on_disk = (raw_lines == desired)
        if clean_on_disk and prev_ours == set(our_words):
            continue

        try:
            with open(path, "w", encoding="utf-8") as f:
                for w in desired:
                    f.write(w + "\n")
            with open(sidecar, "w", encoding="utf-8") as f:
                f.write("# Parole aggiunte automaticamente da RuscaWriter "
                        "(frammenti di elisione). Non modificare a mano.\n")
                for w in our_words:
                    f.write(w + "\n")
            written.append(path)
        except Exception:
            pass
    return written


class RuscaWriterWindow(Adw.ApplicationWindow):
    def __init__(self, app):
        super().__init__(application=app, title=APP_NAME)
        self.app = app
        self.settings = load_settings()
        w = self.settings.get("win_w", 1200)
        h = self.settings.get("win_h", 760)
        self.set_default_size(w, h)
        # EN: a maximised window must come back maximised. Without this, its
        #     size was saved WHILE maximised and restored as an ordinary window
        #     of screen size — spilling under the taskbar, with the window
        #     buttons off the edge. See _on_size_changed: the size is now only
        #     recorded when the window is not maximised, so the value kept is
        #     the one to return to.
        # IT: una finestra massimizzata deve riaprirsi massimizzata. Senza
        #     questo, le sue dimensioni venivano salvate MENTRE era
        #     massimizzata e ripristinate come finestra normale grande quanto
        #     lo schermo: sbordava sotto la barra delle applicazioni e i
        #     pulsanti finivano fuori. Vedi _on_size_changed: le dimensioni si
        #     registrano solo quando NON e' massimizzata, così il valore
        #     conservato e' quello a cui tornare.
        if self.settings.get("win_maximized"):
            self.maximize()
        self.set_size_request(360, 294)
        # La lingua dell'interfaccia segue quella del sistema (specifiche,
        # sezione 9.2): niente selettore interno.
        self.lang = detect_system_language()
        if self.lang not in LANGUAGES:
            self.lang = "en"
        self.translator = Translator(self.lang)
        self.project = Project()
        self.project._lang = self.lang
        self.current = None
        self._loading = False
        self.left_visible = self.settings.get("left_visible", True)
        self.right_visible = self.settings.get("right_visible", True)
        self._restoring = True

        self.font_available = register_bundled_font()
        self.font_size = int(self.settings.get("font_size", DEFAULT_FONT_SIZE))
        self.reading_width = self.settings.get("reading_width", "normal")
        if self.reading_width not in READING_WIDTHS:
            self.reading_width = "normal"
        self.font_size = max(MIN_FONT_SIZE, min(self.font_size, MAX_FONT_SIZE))
        # Carattere dei documenti ESPORTATI. Vuoto = comportamento predefinito
        # (il serif da lettura incorporato). Puo' essere il nome di una
        # famiglia installata sulla macchina.
        self.doc_font = self.settings.get("doc_font", "")
        self.font_family = self.settings.get(
            "font_family",
            TYPEWRITER_FAMILY if self.font_available else "Monospace")
        if self.font_family in ("Special Elite",) and self.font_available:
            self.font_family = TYPEWRITER_FAMILY

        self.spell_lang = self.settings.get("spell_lang", self.lang)
        self.spell_checker = None
        self.spell_error = None

        self._dirty = False
        self.word_goal = int(self.settings.get("word_goal", 0))

        # Aspetto: "auto" segue il sistema (e lo segue dal vivo, vedi
        # _watch_system_appearance), "light" e "dark" lo fissano.
        self.theme_pref = self.settings.get("theme", "auto")
        if self.theme_pref not in APPEARANCES:
            self.theme_pref = "auto"
        # Chiaro/scuro: lo decide Adw.StyleManager (sistema, o forzato).
        self._style_manager = Adw.StyleManager.get_default()
        self._apply_color_scheme()
        self.dark_mode = self._style_manager.get_dark()
        # Tema della pagina: Ametista o Classico. E'
        # indipendente da chiaro/scuro: ogni tema ha entrambe le versioni.
        # resolve_theme traduce anche i codici dei temi vecchi (Giada, Ambra,
        # Zaffiro...), cosi' chi ne aveva uno si ritrova sul piu' vicino dei
        # tre e non rimbalza sul predefinito senza spiegazione.
        self.theme_family = resolve_theme(
            self.settings.get("theme_family", DEFAULT_THEME))
        # Vista "Mostra le interruzioni": tinge i paragrafi spezzati a colonna
        # fissa. Non modifica il testo, si limita a farlo vedere.
        self.show_breaks = bool(self.settings.get("show_breaks", False))
        # Ricucitura automatica all'importazione: SPENTA di partenza. Modifica
        # il testo di chi scrive, quindi non si accende da sola: si attiva dal
        # menu, e da quel momento RuscaWriter ricuce i file importati senza
        # chiedere altro. Chi non la accende puo' sempre usare il comando
        # manuale su un capitolo alla volta.
        self.reflow_on_import = bool(self.settings.get("reflow_on_import", False))
        self._is_fullscreen = False

        # Dizionari MDict. Si aprono alla prima consultazione, non all'avvio:
        # aprire e' immediato, ma un dizionario mai indicizzato costerebbe
        # qualche secondo, e l'avvio del programma non e' il momento per
        # farglielo pagare. La lista e' un ordine di consultazione: si cerca
        # nel primo, poi nel secondo, e ci si ferma al primo che ha la parola.
        self.dict_paths = [p for p in self.settings.get("dictionaries", [])
                           if isinstance(p, str)]
        # Cartella dei dizionari: dove i file .mdx vengono copiati quando li
        # aggiungi, cosi' restano tutti in un posto solo e il programma non
        # dipende da dove li avevi scaricati. Si cambia da Visualizza →
        # Dizionari; chi preferisce tenerli dove sono spegne la copia.
        folder = self.settings.get("dict_folder")
        self.dict_folder = folder if isinstance(folder, str) and folder \
            else default_dict_folder()
        self.dict_copy = bool(self.settings.get("dict_copy", True))
        self._dicts = None
        self._dict_popover = None
        self._dict_grace_until = 0
        self._dict_scroll_from = 0.0
        self._dict_thread = None

        # ultimo formato pagina PDF usato (ricordato tra le sessioni); se il
        # valore salvato non e' tra quelli validi, ripiega sul predefinito.
        saved_size = self.settings.get("pdf_page_size", PDF_DEFAULT_PAGE_SIZE)
        self._pdf_page_size = (saved_size if saved_size in PDF_PAGE_SIZES
                               else PDF_DEFAULT_PAGE_SIZE)

        # preferenze di impaginazione PDF ricordate tra le sessioni:
        # giustificazione del testo e sillabazione. La sillabazione richiede il
        # pacchetto opzionale Pyphen E un dizionario per la lingua (su Debian
        # un pacchetto hyphen-<lingua>): se manca l'uno o l'altro la teniamo
        # sempre a False, a prescindere da cio' che e' salvato.
        self._pdf_justify = bool(self.settings.get("pdf_justify", False))
        self._pdf_hyphenate = bool(
            self.settings.get("pdf_hyphenate", False)) and hyphenation_available(
                getattr(self, "lang", "it"))

        # Evita che gli entry/spinbutton selezionino tutto il testo quando
        # ricevono il focus (in GTK 4 e' il comportamento predefinito): senza
        # questo, lo SpinButton del font mostrerebbe "14" tutto evidenziato.
        try:
            gtk_settings = Gtk.Settings.get_default()
            if gtk_settings is not None:
                gtk_settings.set_property("gtk-entry-select-on-focus", False)
        except Exception:
            pass

        self._apply_css()
        self._build_actions()
        self._build_ui()
        self._apply_editor_font()
        # orienta l'area di scrittura fin dall'avvio, non solo al cambio lingua
        self._apply_text_direction()
        # prepara le liste di elisione di Enchant PRIMA di creare il checker,
        # cosi' libspelling le trova gia' pronte (vedi ensure_elision_dictionaries)
        self._ensure_elision_for_spell()
        self._setup_spell()
        self._retranslate()

        self.connect("close-request", self.on_close_request)
        self.connect("notify::default-width", self._on_size_changed)
        self.connect("notify::default-height", self._on_size_changed)
        self.connect("notify::maximized", self._on_size_changed)
        self.connect("notify::fullscreened", self._on_fullscreen_changed)

        GLib.idle_add(self._apply_layout)
        GLib.idle_add(self._finish_restore)
        GLib.idle_add(self._startup_dialog)
        # All'apertura, dai il focus all'area di scrittura: senza questo il
        # primo widget focusabile (lo SpinButton del font) riceverebbe il focus
        # e mostrerebbe il numero "14" tutto selezionato/evidenziato.
        GLib.idle_add(self._focus_editor)
        # in "automatico" il tema segue il desktop anche mentre si scrive
        self._watch_system_appearance()
        self._autosave_id = GLib.timeout_add_seconds(60, self._autosave_tick)

    def _focus_editor(self):
        try:
            self.text_view.grab_focus()
        except Exception:
            pass
        return False

    def _raise_dialog(self, dialog):
        """Riporta un dialogo in primo piano: utile quando la finestra
        principale è a schermo intero e il window manager lo metterebbe dietro."""
        try:
            if dialog.get_visible():
                dialog.present()
        except Exception:
            pass
        return False

    def _finish_restore(self):
        self._restoring = False
        return False

    # ---- salvataggio sicuro -------------------------------------------------
    def _mark_dirty(self):
        if not self._dirty:
            self._dirty = True
            self._update_window_title()

    def _mark_clean(self):
        self._dirty = False
        self._update_window_title()

    def _update_window_title(self):
        proj = getattr(self.project, "title", "") or ""
        if proj:
            shown = self.t("title_dirty", t=proj) if self._dirty else proj
            self.set_title(f"{shown} — {APP_NAME}")
        else:
            self.set_title(APP_NAME)
        if getattr(self, "window_title", None) is not None:
            self.window_title.set_title(proj or APP_NAME)
            subtitle = APP_NAME if proj else ""
            if getattr(self, "_preview_mode", False):
                whole = getattr(self, "_preview_whole", False)
                subtitle = self.t("mi_preview_all" if whole else "mi_preview")
            self.window_title.set_subtitle(subtitle)

    def _autosave_path(self):
        if self.project.path:
            return self.project.path + ".autosave"
        return None

    def _autosave_tick(self):
        try:
            if self._dirty and self.project.path:
                self._commit_current()
                self.project.meta["font_size"] = self.font_size
                self.project.meta["font_family"] = self.font_family
                self.project.meta["spell_lang"] = self.spell_lang
                self.project.save(self._autosave_path(), update_path=False)
        except Exception:
            pass
        return True

    def on_close_request(self, *_):
        if not self._dirty:
            self._persist_layout()
            return False

        def on_choice(idx):
            if idx == 0:          # scarta
                self._cleanup_autosave()
                self._persist_layout()
                self._force_close()
            elif idx == 2:        # salva (senza popup) e poi chiudi
                def after_save():
                    self._cleanup_autosave()
                    self._persist_layout()
                    self._force_close()
                self.on_save(announce=False, then=after_save)
            # idx == 1 (annulla) o chiusura: resta aperto

        self._confirm(self.t("unsaved_title"), self.t("unsaved_body"),
                      [self.t("btn_discard"), self.t("btn_cancel"),
                       self.t("btn_save_changes")],
                      default_idx=2, cancel_idx=1, on_choice=on_choice)
        return True   # blocca questa chiusura; decidiamo nel callback

    def _close_dictionaries(self):
        """EN: close the dictionary files on the way out. IT: chiude i file
        dei dizionari all'uscita."""
        self._close_dict_popover()
        if self._dicts is not None:
            self._dicts.close()
            self._dicts = None

    def _force_close(self):
        self._dirty = False
        self._close_dictionaries()
        self.destroy()

    def _cleanup_autosave(self):
        p = self._autosave_path()
        try:
            if p and os.path.exists(p):
                os.remove(p)
        except Exception:
            pass

    # ---- traduzione ---------------------------------------------------------
    def t(self, key, **kw):
        return self.translator.t(key, **kw)

    def _t_or(self, key, default, **kw):
        """Come t(), ma se la chiave non e' presente nei file di lingua
        (t() ripiegherebbe sulla chiave grezza) usa il testo 'default'.
        Serve per voci nuove non ancora tradotte: l'interfaccia mostra
        comunque un testo sensato, e quando il JSON conterra' la chiave
        verra' usata la traduzione."""
        val = self.translator.t(key, **kw)
        if val == key:
            return default.format(**kw) if kw else default
        return val

    # ---- stile --------------------------------------------------------------
    def _apply_color_scheme(self):
        self._style_manager.set_color_scheme({
            "light": Adw.ColorScheme.FORCE_LIGHT,
            "dark": Adw.ColorScheme.FORCE_DARK,
        }.get(self.theme_pref, Adw.ColorScheme.DEFAULT))

    def _watch_system_appearance(self):
        """Ogni cambio di chiaro/scuro (del sistema o scelto qui) arriva da
        Adw.StyleManager:dark: si ridipingono pagina e Markdown."""
        self._style_manager.connect("notify::dark",
                                    lambda *_a: self._on_system_appearance())

    def _on_system_appearance(self):
        scuro = self._style_manager.get_dark()
        if scuro != self.dark_mode:
            self.dark_mode = scuro
            self._sync_switch("dark", self.dark_mode)
            self._apply_css()
            self._update_tag_colors()

    def palette(self):
        """Tavolozza corrente: famiglia di tema + chiaro/scuro.

        Unico punto da cui l'interfaccia prende i colori (compresi quelli dei
        titoli Markdown nell'editor), così le quattro combinazioni restano
        coerenti fra loro."""
        return theme_palette(getattr(self, "theme_family", DEFAULT_THEME),
                             getattr(self, "dark_mode", False))

    def theme_label(self, code):
        """Nome da mostrare nel menu, tradotto.

        Davanti al nome va il pallino del colore, dove c'e'. Le etichette dei
        menu GTK sono testo semplice — non si possono colorare voce per voce —
        quindi il colore entra come carattere, non come tinta dell'etichetta."""
        nome = model_theme_label(code, translate=self._t_or)
        pallino = pw_model.theme_dot(code)
        return f"{pallino}  {nome}" if pallino else nome

    # ---- voci del sottomenu Tema, con il pallino dipinto ----------------------
    # EN: GTK menu labels are plain text: the "use-markup" attribute is ignored
    #     by the menus built from a Gio.Menu, so a coloured dot cannot be
    #     written into the label. Each theme entry is therefore a small custom
    #     widget (the "custom" attribute + add_child): a radio button bound to
    #     the same win.theme_family action, with a dot painted in the theme's
    #     exact colour and a thin outline, so even the palest pink shows on a
    #     white menu.
    # IT: le etichette dei menu GTK sono testo semplice: l'attributo
    #     "use-markup" viene ignorato dai menu costruiti da un Gio.Menu, quindi
    #     un pallino colorato non si puo' scrivere nell'etichetta. Ogni voce di
    #     tema e' allora un piccolo widget su misura (attributo "custom" +
    #     add_child): un pulsante radio legato alla stessa azione
    #     win.theme_family, con un pallino dipinto nel colore esatto del tema e
    #     un contorno sottile, così anche il rosa piu' pallido si vede su un
    #     menu bianco.
    THEME_ITEM_CSS = """
    .rusca-theme-item { padding: 4px 12px 4px 8px; border-radius: 6px; }
    .rusca-theme-item:hover { background-color: alpha(currentColor, 0.08); }
    """

    THEME_CUSTOM_ID = "rusca-themes"

    def _theme_dot_widget(self, code, size=14):
        color = pw_model.theme_dot_color(code)
        area = Gtk.DrawingArea()
        area.set_content_width(size)
        area.set_content_height(size)
        area.set_valign(Gtk.Align.CENTER)
        if not color:
            return area
        r, g, b = (int(color[i:i + 2], 16) / 255 for i in (1, 3, 5))

        def draw(_area, cr, w, h):
            radius = min(w, h) / 2 - 1
            cr.arc(w / 2, h / 2, radius, 0, 6.283185307)
            cr.set_source_rgb(r, g, b)
            cr.fill_preserve()
            cr.set_source_rgba(0, 0, 0, 0.22)   # contorno: si vede su bianco
            cr.set_line_width(1)
            cr.stroke()
        area.set_draw_func(draw)
        return area

    def _theme_list_widget(self):
        """EN/IT: the three themes as radio rows: button, painted
        dot, translated name. / i temi come righe radio: pulsante, pallino
        dipinto, nome tradotto."""
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        first = None
        for code in pw_model.THEMES:
            btn = Gtk.CheckButton()
            btn.add_css_class("rusca-theme-item")
            btn.set_action_name("win.theme_family")
            btn.set_action_target_value(GLib.Variant("s", code))
            row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
            row.append(self._theme_dot_widget(code))
            row.append(Gtk.Label(
                label=model_theme_label(code, translate=self._t_or), xalign=0))
            try:
                btn.set_child(row)              # GTK >= 4.8
            except Exception:
                btn.set_label(self.theme_label(code))
            if first is None:
                first = btn
            else:
                btn.set_group(first)            # disegnati come radio

            def on_toggled(b):
                # un clic chiude il menu; un cambio a menu chiuso no
                if not (b.get_active() and b.get_mapped()):
                    return
                w = b.get_ancestor(Gtk.Popover)
                while w is not None:
                    w.popdown()
                    parent = w.get_parent()
                    w = parent.get_ancestor(Gtk.Popover) if parent else None
            btn.connect("toggled", on_toggled)
            box.append(btn)
        return box

    def _attach_theme_items(self, container):
        """EN/IT: put the theme list into a menubar or popover menu built with
        custom_themes=True. Returns False if GTK did not take it, so the
        caller can fall back to the plain submenu. / mette l'elenco dei temi
        in una barra o in un menu costruiti con custom_themes=True.
        Restituisce False se GTK non l'ha accettato, cosi' chi chiama puo'
        ripiegare sul sottomenu semplice."""
        if container is None:
            return False
        if not getattr(self, "_theme_item_css", None):
            self._theme_item_css = Gtk.CssProvider()
            try:
                self._theme_item_css.load_from_data(
                    self.THEME_ITEM_CSS.encode("utf-8"))
                display = Gdk.Display.get_default()
                if display is not None:
                    Gtk.StyleContext.add_provider_for_display(
                        display, self._theme_item_css,
                        Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)
            except Exception:
                pass
        try:
            return bool(container.add_child(self._theme_list_widget(),
                                            self.THEME_CUSTOM_ID))
        except Exception:
            return False

    def _set_menu_with_themes(self, container):
        """EN/IT: give a menubar or popover menu its model and its theme list;
        fall back to the emoji submenu if the custom widget is refused.
        / da' a una barra o a un menu il suo modello e l'elenco dei temi;
        ripiega sul sottomenu con le emoji se il widget viene rifiutato."""
        container.set_menu_model(self._build_menu_model(custom_themes=True))
        if not self._attach_theme_items(container):
            container.set_menu_model(
                self._build_menu_model(custom_themes=False))

    def _sync_switch(self, nome, attivo):
        """Riallinea la spunta di un interruttore nel menu al suo valore
        vero. Va chiamata a ogni cambio, o la spunta e la realta' divergono."""
        act = getattr(self, "_switch_actions", {}).get(nome)
        if act is not None:
            act.set_state(GLib.Variant.new_boolean(bool(attivo)))

    def on_toggle_dark(self, *_):
        """Ctrl+Maiusc+D: passa da chiaro a scuro e viceversa, fissando la
        scelta (smette di seguire il sistema finche' non si sceglie di nuovo
        Aspetto -> Automatico)."""
        self.on_appearance("light" if self.dark_mode else "dark")

    def on_appearance(self, pref):
        """Aspetto: "auto" (segue il sistema), "light" o "dark"."""
        if pref not in APPEARANCES:
            return
        self.theme_pref = pref
        self.settings["theme"] = pref
        save_settings(self.settings)
        self._apply_color_scheme()
        self.dark_mode = self._style_manager.get_dark()
        self._sync_switch("dark", self.dark_mode)
        act = getattr(self, "_appearance_action", None)
        if act is not None:
            act.set_state(GLib.Variant("s", pref))
        self._apply_css()
        self._update_tag_colors()

    def on_reading_width(self, code):
        """Larghezza della colonna di scrittura: "normal" o "wide"."""
        if code not in READING_WIDTHS:
            return
        self.reading_width = code
        self.settings["reading_width"] = code
        save_settings(self.settings)
        act = getattr(self, "_reading_width_action", None)
        if act is not None:
            act.set_state(GLib.Variant("s", code))
        self._last_side = None                      # la colonna va rimisurata
        self._update_reading_margins()

    def on_theme_family(self, code):
        """Cambia tema (Ametista / Classico) senza toccare la
        preferenza chiaro-scuro, che resta com'era."""
        if (code not in pw_model.THEMES
                or code == getattr(self, "theme_family", None)):
            return
        self.theme_family = code
        self.settings["theme_family"] = code
        save_settings(self.settings)
        self._apply_css()
        self._update_tag_colors()

    def _apply_css(self):
        if not hasattr(self, "_theme_provider"):
            self._theme_provider = Gtk.CssProvider()
            display = Gdk.Display.get_default()
            if display is not None:
                Gtk.StyleContext.add_provider_for_display(
                    display, self._theme_provider,
                    Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)
        css = build_css(dark=getattr(self, "dark_mode", False),
                        theme=getattr(self, "theme_family", DEFAULT_THEME))
        try:
            self._theme_provider.load_from_data(css.encode("utf-8"))
        except Exception:
            try:
                self._theme_provider.load_from_data(css, -1)
            except Exception:
                pass

    # ---- layout -------------------------------------------------------------
    def _content_width(self):
        w = self.paned_outer.get_allocated_width()
        return w if w > 1 else self.settings.get("win_w", 1200)

    def _apply_editor_font(self):
        if not hasattr(self, "_font_css_provider"):
            self._font_css_provider = Gtk.CssProvider()
            display = Gdk.Display.get_default()
            if display is not None:
                Gtk.StyleContext.add_provider_for_display(
                    display, self._font_css_provider,
                    Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION + 1)
        css = ('textview.text-editor, textview.text-editor text '
               '{{ font-family: "{fam}"; font-size: {sz}pt; }}').format(
                   fam=self.font_family, sz=self.font_size)
        try:
            self._font_css_provider.load_from_data(css.encode("utf-8"))
        except Exception:
            try:
                self._font_css_provider.load_from_data(css, -1)
            except Exception:
                pass
        if hasattr(self, "font_size_spin"):
            self.font_size_spin.set_value(self.font_size)
        # corpo o carattere cambiati: interlinea e colonna si adeguano
        self._apply_reading_rhythm()

    # ---- controllo ortografico ---------------------------------------------
    def _setup_spell(self):
        """Collega il controllo ortografico al TextView. Usa libspelling
        (backend 'spelling') o, in subordine, Gspell 2.x ('gspell2'). Salva
        l'oggetto attivo in self.spell_checker e, per libspelling, l'adapter
        in self._spell_adapter (serve per cambiare lingua e abilitare/menu)."""
        self.spell_error = None
        self.spell_checker = None
        self._spell_adapter = None
        if SPELL_BACKEND is None:
            self.spell_error = ("nessun backend di controllo ortografico "
                                "compatibile con GTK 4 (installa "
                                "gir1.2-spelling-1)")
            return
        loc = self._spell_locale()
        try:
            if SPELL_BACKEND == "spelling":
                # libspelling vuole un GtkSource.Buffer: se GtkSourceView non
                # e' disponibile la vista e' un Gtk.TextView normale e l'adapter
                # rifiuterebbe il buffer. Segnaliamo il motivo invece di fallire.
                if GtkSource is None or not isinstance(self.text_buffer,
                                                       GtkSource.Buffer):
                    raise RuntimeError(
                        "libspelling richiede GtkSourceView 5 "
                        "(installa gir1.2-gtksource-5)")
                self._setup_spell_libspelling(loc)
            else:  # gspell2
                self._setup_spell_gspell2(loc)
        except Exception as exc:
            self.spell_checker = None
            self._spell_adapter = None
            self.spell_error = str(exc) or repr(exc)

    def _make_spelling_checker(self, loc):
        """Crea un Spelling.Checker per il locale dato, con vari ripieghi a
        seconda della versione dell'API di libspelling disponibile."""
        provider = None
        try:
            provider = Spelling.Provider.get_default()
        except Exception:
            provider = None
        # tentativo 1: Checker.new(provider, code)
        if provider is not None:
            try:
                ck = Spelling.Checker.new(provider, loc)
                if ck is not None:
                    return ck
            except Exception:
                pass
            # tentativo 2: anche solo con la sigla lingua (es. 'it')
            try:
                ck = Spelling.Checker.new(provider, loc.split("_")[0])
                if ck is not None:
                    return ck
            except Exception:
                pass
        # ripiego finale: checker predefinito (lingua di sistema)
        return Spelling.Checker.get_default()

    def _setup_spell_libspelling(self, loc):
        checker = self._make_spelling_checker(loc)
        if checker is None:
            raise RuntimeError("impossibile creare il checker libspelling")
        adapter = Spelling.TextBufferAdapter.new(
            self.text_view.get_buffer(), checker)
        # menu contestuale dei suggerimenti + gruppo di azioni 'spelling'
        try:
            self._apply_extra_menu(adapter.get_menu_model())
        except Exception:
            pass
        try:
            self.text_view.insert_action_group("spelling", adapter)
        except Exception:
            pass
        adapter.set_enabled(True)
        self.spell_checker = checker
        self._spell_adapter = adapter

    def _setup_spell_gspell2(self, loc):
        lang = Gspell.Language.lookup(loc)
        if lang is None:
            raise RuntimeError("dizionario '%s' non trovato" % loc)
        checker = Gspell.Checker.new(lang)
        buf = Gspell.TextBuffer.get_from_gtk_text_buffer(
            self.text_view.get_buffer())
        buf.set_spell_checker(checker)
        gview = Gspell.TextView.get_from_gtk_text_view(self.text_view)
        gview.set_inline_spell_checking(True)
        gview.set_enable_language_menu(True)
        self.spell_checker = checker

    def _populate_spell_combo(self):
        self._spell_combo_loading = True
        self.spell_combo.remove_all()
        langs = self._available_spell_langs()
        for code in langs:
            self.spell_combo.append(code, LANGUAGES[code][0])
        if self.spell_lang in langs:
            self.spell_combo.set_active_id(self.spell_lang)
        elif langs:
            self.spell_lang = langs[0]
            self.spell_combo.set_active_id(langs[0])
        self._spell_combo_loading = False

    def _spell_locale(self):
        return spell_locale_for(self.spell_lang)

    def _ensure_elision_for_spell(self):
        """Genera/aggiorna le liste personali di Enchant con i frammenti di
        elisione per la lingua ortografica corrente (e per le altre lingue con
        elisione, cosi' il passaggio di lingua e' gia' coperto). Va chiamata
        prima di creare/ricreare il checker."""
        try:
            locales = set()
            # lingua attiva
            locales.add(self._spell_locale())
            # tutte le lingue con elisione note, cosi' funziona anche dopo un
            # cambio lingua senza dover rigenerare nulla
            for base in _ELISION_FRAGMENTS:
                locales.add(spell_locale_for(base))
            ensure_elision_dictionaries(locales)
        except Exception:
            pass   # il controllo ortografico non deve mai bloccare l'avvio

    def _available_spell_langs(self):
        available = []
        if SPELL_BACKEND == "gspell2" and Gspell is not None:
            try:
                installed = {l.get_code() for l in Gspell.Language.get_available()}
                for code in LANGUAGES:
                    loc = spell_locale_for(code)
                    if loc in installed or loc.split("_")[0] in installed or any(
                            ic.split("_")[0] == loc.split("_")[0] for ic in installed):
                        available.append(code)
            except Exception:
                available = []
        elif SPELL_BACKEND == "spelling" and Spelling is not None:
            # libspelling espone le lingue tramite il provider predefinito; i
            # nomi dei metodi variano tra le versioni, quindi proviamo i piu'
            # comuni e, se nulla funziona, ripieghiamo sull'elenco completo.
            try:
                provider = Spelling.Provider.get_default()
                codes = set()
                langs = None
                for meth in ("list_languages", "get_languages", "dup_languages"):
                    fn = getattr(provider, meth, None)
                    if fn is not None:
                        try:
                            langs = fn()
                            break
                        except Exception:
                            langs = None
                if langs is not None:
                    for lg in langs:
                        code = None
                        for attr in ("get_code", "get_language", "get_id"):
                            getter = getattr(lg, attr, None)
                            if getter is not None:
                                try:
                                    code = getter()
                                    break
                                except Exception:
                                    code = None
                        if isinstance(lg, str):
                            code = lg
                        if code:
                            codes.add(code)
                if codes:
                    for code in LANGUAGES:
                        loc = spell_locale_for(code)
                        if loc in codes or loc.split("_")[0] in {
                                c.split("_")[0] for c in codes}:
                            available.append(code)
            except Exception:
                available = []
        if not available:
            available = [c for c in LANGUAGES]
        available = sorted(set(available),
                           key=lambda c: (c != self.lang, LANGUAGES[c][0].lower()))
        return available

    def _set_spell_lang(self, lang):
        self.spell_lang = lang
        self.settings["spell_lang"] = lang
        if not self._restoring:
            save_settings(self.settings)
        # assicura i frammenti di elisione per la nuova lingua prima del checker
        self._ensure_elision_for_spell()
        if self.spell_checker is not None:
            try:
                loc = self._spell_locale()
                if SPELL_BACKEND == "spelling":
                    # crea un nuovo checker per la lingua e applicalo all'adapter
                    new_checker = self._make_spelling_checker(loc)
                    applied = False
                    if self._spell_adapter is not None:
                        for meth in ("set_checker", "set_spell_checker"):
                            fn = getattr(self._spell_adapter, meth, None)
                            if fn is not None and new_checker is not None:
                                try:
                                    fn(new_checker)
                                    applied = True
                                    break
                                except Exception:
                                    applied = False
                    if applied and new_checker is not None:
                        self.spell_checker = new_checker
                    else:
                        # ripiego: ricollega tutto da capo con la nuova lingua
                        self._setup_spell()
                else:  # gspell2
                    glang = Gspell.Language.lookup(loc)
                    if glang is None:
                        raise RuntimeError("dizionario non trovato")
                    self.spell_checker.set_language(glang)
            except Exception as exc:
                self.spell_error = str(exc)
                self._setup_spell()
        elif HAVE_SPELL:
            # il checker non era partito: riprova con la nuova lingua
            self._setup_spell()
        if self.project is not None:
            self.project.meta["spell_lang"] = lang

    def on_spell_lang_changed(self, combo):
        if getattr(self, "_spell_combo_loading", False):
            return
        lang = combo.get_active_id()
        if lang and lang != self.spell_lang:
            self._set_spell_lang(lang)
            if self.spell_checker is None and self.spell_error:
                self._info(self.t("spell_unavailable", e=self.spell_error))

    def _set_font_size(self, size):
        size = max(MIN_FONT_SIZE, min(int(size), MAX_FONT_SIZE))
        if size == self.font_size:
            return
        self.font_size = size
        self._apply_editor_font()
        self.settings["font_size"] = size
        if not self._restoring:
            save_settings(self.settings)

    def on_font_size_changed(self, spin):
        self._set_font_size(spin.get_value_as_int())
        # togli l'eventuale selezione del numero (sicurezza in piu' oltre a
        # gtk-entry-select-on-focus): porta il cursore in fondo senza selezione
        try:
            spin.select_region(0, 0)
        except Exception:
            pass

    def on_font_increase(self, *_):
        self._set_font_size(self.font_size + 1)
        return True

    def on_font_decrease(self, *_):
        self._set_font_size(self.font_size - 1)
        return True

    def _apply_layout(self, _retries=0):
        # La visibilita' dei pannelli va impostata SEMPRE, anche se la larghezza
        # non e' ancora nota (durante le transizioni fullscreen puo' essere <=1):
        # altrimenti, uscendo dalla modalita' concentrazione, i pannelli non
        # riapparirebbero.
        self.left_panel.set_visible(self.left_visible)
        self.right_panel.set_visible(self.right_visible)
        # EN: only move the dividers once the window really has a width. At
        #     startup this runs before the first allocation, and positioning an
        #     unallocated GtkPaned makes GTK complain that it is being asked to
        #     draw a part that has no size yet. Retry on the next idle turn
        #     instead of guessing; after a while, fall back to the saved width
        #     so a window that never gets allocated still opens usably.
        # IT: sposta i separatori solo quando la finestra ha davvero una
        #     larghezza. All'avvio questo metodo parte prima della prima
        #     allocazione, e posizionare un GtkPaned non ancora allocato fa
        #     protestare GTK, che si trova a disegnare una parte senza misure.
        #     Invece di indovinare si riprova al giro successivo; dopo un po'
        #     si ripiega sulla larghezza salvata, così una finestra che non
        #     venisse mai allocata si aprirebbe comunque in modo utilizzabile.
        allocated = self.paned_outer.get_allocated_width()
        if allocated <= 1:
            if _retries < 20:
                GLib.idle_add(self._apply_layout, _retries + 1)
                return False
            total = self._content_width()
        else:
            total = allocated
        if total <= 1:
            return False
        left_w, _centro, right_w = split_columns(
            total,
            self.settings.get("left_px"), self.settings.get("right_px"),
            self.left_visible, self.right_visible)

        # Ripristino in due tempi. Prima il divisore dei capitoli; quello
        # delle note al giro successivo, quando il pannello interno ha la sua
        # larghezza vera. Calcolarla a tavolino (totale meno capitoli) mentre
        # il pannello interno non era ancora allocato faceva correggere la
        # posizione a GTK: la colonna delle note ripartiva larga il doppio.
        self._restoring_columns = True
        self.paned_outer.set_position(left_w)
        GLib.idle_add(self._apply_inner_layout, right_w)
        return False

    def _apply_inner_layout(self, right_w, _retries=0):
        inner_w = self.paned_inner.get_width()
        if inner_w <= 1 and _retries < 20:
            GLib.idle_add(self._apply_inner_layout, right_w, _retries + 1)
            return False
        if inner_w > 1:
            self.paned_inner.set_position(max(0, inner_w - right_w))
        # I margini di lettura dipendono dalla larghezza dell'AREA DI
        # SCRITTURA, che cambia proprio adesso: si ricalcolano al giro
        # successivo, quando GTK ha applicato le posizioni appena chieste.
        # Senza questo restavano quelli calcolati prima che i pannelli
        # togliessero spazio al centro, e il testo usciva incolonnato
        # stretto in mezzo a due margini enormi.
        GLib.idle_add(self._update_reading_margins)
        GLib.idle_add(self._remember_columns_total)
        return False

    def _remember_columns_total(self):
        """Dopo il ripristino delle colonne: e' questa la larghezza della
        finestra rispetto a cui uno spostamento dei divisori e' dell'utente."""
        self._columns_total = self.paned_outer.get_width()
        self._restoring_columns = False
        return False

    def _block_file_drops_on_editor(self):
        """Installa sull'area di scrittura un gestore di trascinamento: quando si
        rilascia uno o piu' file .txt/.md, ciascun file viene aggiunto come UN
        nuovo capitolo in fondo al progetto (un file = un capitolo). Il testo non
        viene inserito dentro il capitolo corrente, per non mescolare contenuti.

        (Il nome del metodo resta per compatibilita' con il punto di chiamata.)"""
        try:
            drop = Gtk.DropTarget.new(Gdk.FileList, Gdk.DragAction.COPY)
            try:
                drop.set_gtypes([Gdk.FileList, Gio.File])
            except Exception:
                pass
            drop.connect("drop", self._on_editor_file_drop)
            self.text_view.add_controller(drop)
        except Exception:
            pass

    def _on_editor_file_drop(self, _target, value, _x, _y):
        """Gestisce il rilascio di file sull'area di scrittura importando ogni
        file di testo come nuovo capitolo. Restituisce True se ha gestito il
        rilascio. Rifiuta i tipi non-file (cosi' il testo trascinato non viene
        inserito alla rinfusa nel capitolo)."""
        files = []
        try:
            if isinstance(value, Gdk.FileList):
                files = list(value.get_files())
            elif isinstance(value, Gio.File):
                files = [value]
        except Exception:
            files = []
        if not files:
            return False
        paths = []
        for gf in files:
            try:
                p = gf.get_path()
            except Exception:
                p = None
            if p:
                paths.append(p)
        if not paths:
            return False
        added = self._import_files_as_chapters(paths)
        return bool(added)

    def _import_files_as_chapters(self, paths):
        """Importa una lista di file .txt/.md, ciascuno come nuovo capitolo in
        fondo al progetto. Salta i file non testuali. Restituisce il numero di
        capitoli aggiunti e seleziona l'ultimo importato."""
        self._commit_current()
        accepted = (".txt", ".md", ".markdown")
        added = 0
        last_ch = None
        skipped = []
        for path in paths:
            if not path.lower().endswith(accepted):
                skipped.append(os.path.basename(path))
                continue
            try:
                with open(path, "r", encoding="utf-8", errors="replace") as f:
                    raw = f.read()
            except Exception as exc:
                self._error(self.t("err_open", e=exc))
                continue
            title = os.path.splitext(os.path.basename(path))[0]
            if path.lower().endswith((".md", ".markdown")):
                # le immagini accanto al file entrano nel progetto
                raw = self.project.import_md_images(
                    raw, os.path.dirname(os.path.abspath(path)))
            last_ch = self.project.add_chapter_from_text(raw, title=title)
            added += 1
        if added and self.reflow_on_import:
            # la preferenza e' accesa: ricuci i capitoli appena importati
            self.project.rejoin_paragraphs()
        if added:
            # seleziona l'ultimo capitolo importato
            idx = self.project.chapters.index(last_ch) if last_ch else 0
            self._refresh_chapter_list(idx)
            self._mark_dirty()
            self._info(self.t("imported_n", n=added))
        if skipped:
            self._error(self.t("import_skipped", files=", ".join(skipped)))
        return added

    def _reading_max_px(self):
        """EN/IT: the width of READING_MEASURE_CHARS characters of the editor
        font, in pixels / la larghezza di READING_MEASURE_CHARS caratteri del
        font dell'editor, in pixel."""
        try:
            desc = Pango.FontDescription.from_string(
                f"{self.font_family} {self.font_size}")
            metrics = self.text_view.get_pango_context().get_metrics(desc, None)
            char_w = metrics.get_approximate_char_width() / Pango.SCALE
            if char_w > 0:
                return int(char_w * READING_WIDTHS.get(self.reading_width,
                                                       READING_MEASURE_CHARS))
        except Exception:
            pass
        return READING_MAX_PX

    def _apply_reading_rhythm(self):
        """EN/IT: line spacing, paragraph spacing and air above the headings,
        all proportional to the font size. / interlinea, spazio tra i
        paragrafi e aria sopra i titoli, tutto in proporzione al corpo."""
        tv = getattr(self, "text_view", None)
        if tv is None:
            return
        px = self.font_size * 96 / 72               # corpo in pixel
        # una riga "naturale" e' gia' circa 1,2 volte il corpo
        extra = max(2, int(round(px * (READING_LINE_SPACING - 1.2))))
        tv.set_pixels_inside_wrap(extra)            # dentro il paragrafo
        tv.set_pixels_below_lines(extra)            # tra una riga e l'altra
        for nome, aria in (("h1", 1.1), ("h2", 0.9), ("h3", 0.7)):
            tag = getattr(self, "_md_tags", {}).get(nome)
            if tag is not None:
                tag.set_property("pixels-above-lines", int(px * aria))
                tag.set_property("pixels-below-lines", int(px * 0.35))
        self._last_side = None                      # la colonna va rimisurata
        self._update_reading_margins()

    def _update_reading_margins(self, _tentativi=0):
        w = self.text_view.get_allocated_width()
        if w <= 1:
            # non ancora allocata: si riprova, invece di fissare un margine
            # su una misura che non esiste
            if _tentativi < 20:
                GLib.idle_add(self._update_reading_margins, _tentativi + 1)
            return False
        # limita la larghezza della colonna di scrittura per comodita' di lettura
        # e la centra quando l'area e' molto piu' larga del massimo di lettura
        massimo = self._reading_max_px()
        if w > massimo + 40:
            side = int((w - massimo) / 2)
        else:
            side = 16
        if getattr(self, "_last_side", None) != side:
            self._last_side = side
            self.text_view.set_left_margin(side)
            self.text_view.set_right_margin(side)
        return False

    def on_divider_moved(self, _paned, _param):
        if self._restoring:
            return
        # I margini seguono subito il divisore. Il salvataggio delle colonne
        # laterali invece si fa dopo, quando GTK ha finito di sistemare la
        # finestra: leggere le posizioni durante un ridimensionamento (un
        # divisore gia' spostato, l'altro non ancora) dava larghezze assurde,
        # per esempio una colonna delle note di 1300 px, che al riavvio
        # lasciavano al testo una fessura.
        self._update_reading_margins()
        if not getattr(self, "_columns_save_pending", False):
            self._columns_save_pending = True
            GLib.idle_add(self._save_columns)

    def _save_columns(self):
        """Registra la larghezza delle colonne laterali, ma solo quando a
        spostare un divisore e' stato l'utente. Se nel frattempo e' cambiata
        la larghezza della finestra, i divisori si sono mossi per quello e la
        scelta dell'utente resta quella di prima."""
        self._columns_save_pending = False
        if getattr(self, "_restoring_columns", False):
            return False                   # ripristino in corso, non e' l'utente
        total = self.paned_outer.get_width()
        if total <= 1:
            return False
        if total != getattr(self, "_columns_total", None):
            self._columns_total = total
            return False
        left_w = self.left_panel.get_width()
        right_w = self.right_panel.get_width()
        if self.left_visible and left_w > 0:
            self._store_column("left_px", left_w)
        if self.right_visible and right_w > 0:
            self._store_column("right_px", right_w)
        return False

    def _store_column(self, key, width):
        """Le differenze di un paio di pixel (lo spessore del divisore fra
        come la colonna si ripristina e come si rimisura) non sono una
        scelta dell'utente: registrarle faceva perdere un pixel a ogni
        riavvio."""
        vecchio = self.settings.get(key)
        if not isinstance(vecchio, int) or abs(vecchio - width) > 2:
            self.settings[key] = width

    def _on_size_changed(self, *_):
        if not self._restoring:
            massimizzata = self.is_maximized()
            self.settings["win_maximized"] = bool(massimizzata)
            # Le dimensioni si registrano solo a finestra normale: quelle di
            # una massimizzata non sono una misura a cui tornare, sono lo
            # schermo.
            if not massimizzata:
                # La dimensione predefinita, non get_width(): e' la stessa
                # misura che set_default_size() ripristina all'avvio.
                # get_width() non comprende il bordo della finestra, e la
                # finestra si restringeva di qualche pixel a ogni riavvio.
                w, h = self.get_default_size()
                if w > 1:
                    self.settings["win_w"] = w
                if h > 1:
                    self.settings["win_h"] = h
        self._update_reading_margins()

    def _persist_layout(self):
        self.settings["left_visible"] = self.left_visible
        self.settings["right_visible"] = self.right_visible
        save_settings(self.settings)

    def on_toggle_left(self, *_):
        self.left_visible = not self.left_visible
        self._apply_layout()
        self._persist_layout()

    def on_toggle_right(self, *_):
        self.right_visible = not self.right_visible
        self._apply_layout()
        self._persist_layout()

    def _on_fullscreen_changed(self, *_):
        self._is_fullscreen = bool(self.is_fullscreen())
        self._sync_menu_chrome()

    def _sync_menu_chrome(self):
        """A schermo intero restano barra del titolo e menu: tutto resta
        raggiungibile (F11 per uscire)."""
        return

    def on_toggle_fullscreen(self, *_):
        if self.is_fullscreen():
            self.unfullscreen()
        else:
            self.fullscreen()
        return True

    def on_quit(self, *_):
        self.close()
        return True

    # ---- azioni e scorciatoie ----------------------------------------------
    def _build_actions(self):
        simple = [
            ("new",          self.on_new,            ["<Control>n"]),
            ("open",         self.on_open,           ["<Control>o"]),
            ("save",         self.on_save,           ["<Control>s"]),
            ("import_chapters", self.on_import_chapters, ["<Control>i"]),
            ("sections",     self.on_edit_sections,  []),
            ("export_txt",   self.on_export,         []),
            ("export_md",    self.on_export_markdown, []),
            ("export_pdf",   self.on_export_pdf,     []),
            ("page_setup",   self.on_page_setup,     ["<Control><Shift>p"]),
            ("export_epub",  self.on_export_epub,    []),
            ("export_azw3",  self.on_export_azw3,    []),
            ("export_odt",   self.on_export_odt,     []),
            ("export_docx",  self.on_export_docx,    []),
            ("export_html",  self.on_export_html,    []),
            ("quit",         self.on_quit,           ["<Control>q"]),
            ("add",          self.on_add_chapter,    ["<Control><Shift>n"]),
            ("del",          self.on_delete_chapter, []),
            ("rename",       self.on_rename_chapter, ["F2"]),
            ("up",           self.on_move_up,        ["<Control><Shift>Up"]),
            ("down",         self.on_move_down,      ["<Control><Shift>Down"]),
            ("find",         self.on_find_replace,   ["<Control>f"]),
            # EN/IT: dictionary lookup of the word under the cursor, and the
            # place where the .mdx files are added and put in order.
            ("lookup",       self.on_lookup_word,    ["<Control>d"]),
            ("dictionaries", self.on_manage_dictionaries, []),
            # EN/IT: manual paragraph re-flow, and the view that shows where
            # the hard-wrapped paragraphs are.
            ("reflow",       self.on_reflow_paragraphs, []),
            ("choose_font",  self.on_choose_font,     []),
            # EN: attach an image (PNG/JPEG/WebP) into the current chapter
            # IT: allega un'immagine (PNG/JPEG/WebP) nel capitolo corrente
            ("insert_image", self.on_insert_image,   ["<Control><Shift>i"]),
            ("toggle_left",  self.on_toggle_left,    ["<Control>l"]),
            ("toggle_right", self.on_toggle_right,   ["<Control>r"]),
            ("fullscreen",   self.on_toggle_fullscreen, ["F11"]),
            ("font_inc",     self.on_font_increase,
             ["<Control>plus", "<Control>equal", "<Control>KP_Add"]),
            ("font_dec",     self.on_font_decrease,
             ["<Control>minus", "<Control>KP_Subtract"]),
            ("preview",      self.on_toggle_preview, ["<Control>e"]),
            ("preview_all",  self.on_toggle_preview_whole, ["<Control><Shift>e"]),
            ("goal",         self.on_set_goal,       []),
            ("about",        self.on_info,           []),
            ("shortcuts",    self.show_shortcuts,    ["<Control>question"]),
            ("md_help",      self.on_md_help,        ["<Shift>F1"]),
        ]
        self._switch_actions = {}
        for name, handler, accels in simple:
            act = Gio.SimpleAction.new(name, None)
            act.connect("activate", lambda a, p, h=handler: h())
            self.add_action(act)
            if accels:
                self.app.set_accels_for_action("win." + name, accels)

        # EN/IT: switches, not commands. A stateful boolean action makes GTK
        # draw a tick beside the entry, so the menu says whether the dark theme
        # is on instead of always reading the same. A plain action cannot: it
        # has no state to show.
        # Interruttori, non comandi. Un'azione booleana "con stato" fa
        # disegnare a GTK la spunta accanto alla voce, così il menu dice se il
        # tema scuro e' acceso invece di leggersi sempre uguale. Un'azione
        # semplice non puo': non ha uno stato da mostrare.
        for nome, attivo, gestore, accels in (
                ("dark", self.dark_mode, self.on_toggle_dark,
                 ["<Control><Shift>d"]),
                ("show_breaks", self.show_breaks, self.on_toggle_show_breaks,
                 ["<Control><Shift>b"])):
            act = Gio.SimpleAction.new_stateful(
                nome, None, GLib.Variant.new_boolean(bool(attivo)))
            act.connect("activate", lambda a, p, h=gestore: h())
            self.add_action(act)
            self.app.set_accels_for_action("win." + nome, accels)
            self._switch_actions[nome] = act


        # Aspetto (automatico / chiaro / scuro): azione con stato, cosi' il
        # menu mostra quale dei tre e' attivo.
        app_act = Gio.SimpleAction.new_stateful(
            "appearance", GLib.VariantType.new("s"),
            GLib.Variant("s", self.theme_pref))
        app_act.connect("activate",
                        lambda _a, prm: self.on_appearance(prm.get_string()))
        self.add_action(app_act)
        self._appearance_action = app_act

        # Larghezza della colonna (normale / larga): azione con
        # stato, come l'aspetto, cosi' il menu mostra quale e' attiva.
        width_act = Gio.SimpleAction.new_stateful(
            "reading_width", GLib.VariantType.new("s"),
            GLib.Variant("s", self.reading_width))
        width_act.connect("activate",
                          lambda _a, prm: self.on_reading_width(prm.get_string()))
        self.add_action(width_act)
        self._reading_width_action = width_act

        # Famiglia di tema: azione "con stato", come la lingua, cosi' il menu
        # mostra il pallino accanto alla voce attiva.
        theme_act = Gio.SimpleAction.new_stateful(
            "theme_family", GLib.VariantType.new("s"),
            GLib.Variant("s", self.theme_family))
        theme_act.connect("activate", self._on_theme_family_action)
        self.add_action(theme_act)
        self._theme_action = theme_act

        # Ricucitura automatica: azione booleana, cosi' il menu mostra la
        # spunta e si vede a colpo d'occhio se e' attiva.
        reflow_act = Gio.SimpleAction.new_stateful(
            "reflow_auto", None,
            GLib.Variant.new_boolean(self.reflow_on_import))
        reflow_act.connect("activate", self._on_reflow_auto_action)
        self.add_action(reflow_act)
        self._reflow_action = reflow_act

    def _on_reflow_auto_action(self, action, _param):
        self.reflow_on_import = not self.reflow_on_import
        action.set_state(GLib.Variant.new_boolean(self.reflow_on_import))
        self.settings["reflow_on_import"] = self.reflow_on_import
        save_settings(self.settings)
        self._info(self.t("reflow_auto_on") if self.reflow_on_import
                   else self.t("reflow_auto_off"))

    def _on_theme_family_action(self, action, param):
        code = param.get_string()
        action.set_state(param)
        self.on_theme_family(code)

    def _build_menu_model(self, custom_themes=False):
        """Menu principale (in alto a destra), nello stile GNOME: le voci di
        uso frequente in alto, poi sottomenu per capitoli, esportazione,
        vista e aspetto, infine guida, scorciatoie e informazioni."""
        menu = Gio.Menu()
        files = Gio.Menu()
        files.append(self.t("mi_new"), "win.new")
        files.append(self.t("mi_open"), "win.open")
        files.append(self.t("mi_import_chapters"), "win.import_chapters")
        m_export = Gio.Menu()
        for key, action in (("mi_export_pdf", "export_pdf"), ("mi_export_epub", "export_epub"),
                            ("mi_export_azw3", "export_azw3"), ("mi_export_odt", "export_odt"),
                            ("mi_export_docx", "export_docx"), ("mi_export_html", "export_html"),
                            ("mi_export_md", "export_md"), ("mi_export_txt", "export_txt")):
            m_export.append(self.t(key), "win." + action)
        files.append_submenu(self.t("mi_export_sub"), m_export)
        menu.append_section(None, files)

        book = Gio.Menu()
        m_chapter = Gio.Menu()
        c1 = Gio.Menu()
        c1.append(self.t("mi_add"), "win.add")
        c1.append(self.t("mi_rename"), "win.rename")
        c1.append(self.t("mi_del"), "win.del")
        m_chapter.append_section(None, c1)
        c2 = Gio.Menu()
        c2.append(self.t("mi_up"), "win.up")
        c2.append(self.t("mi_down"), "win.down")
        m_chapter.append_section(None, c2)
        c3 = Gio.Menu()
        c3.append(self.t("mi_insert_image"), "win.insert_image")
        m_chapter.append_section(None, c3)
        book.append_submenu(self.t("menu_edit"), m_chapter)
        book.append(self.t("mi_sections"), "win.sections")
        book.append(self._t_or("mi_page_setup", "Impostazione pagina\u2026"), "win.page_setup")
        book.append(self.t("mi_goal"), "win.goal")
        menu.append_section(None, book)

        tools = Gio.Menu()
        tools.append(self.t("mi_find"), "win.find")
        tools.append(self.t("mi_lookup"), "win.lookup")
        tools.append(self.t("mi_dictionaries"), "win.dictionaries")
        m_reflow = Gio.Menu()
        m_reflow.append(self._t_or("mi_reflow", "Ricuci i paragrafi"), "win.reflow")
        m_reflow.append(self._t_or("mi_reflow_auto",
                                   "Ricuci automaticamente i testi importati"),
                        "win.reflow_auto")
        m_reflow.append(self._t_or("mi_show_breaks", "Mostra le interruzioni"),
                        "win.show_breaks")
        tools.append_section(None, m_reflow)
        menu.append_section(None, tools)

        view = Gio.Menu()
        m_view = Gio.Menu()
        v1 = Gio.Menu()
        v1.append(self.t("mi_preview"), "win.preview")
        v1.append(self.t("mi_preview_all"), "win.preview_all")
        m_view.append_section(None, v1)
        v2 = Gio.Menu()
        v2.append(self.t("mi_toggle_left"), "win.toggle_left")
        v2.append(self.t("mi_toggle_right"), "win.toggle_right")
        v2.append(self.t("mi_fullscreen"), "win.fullscreen")
        m_view.append_section(None, v2)
        v3 = Gio.Menu()
        v3.append(self.t("mi_font_inc"), "win.font_inc")
        v3.append(self.t("mi_font_dec"), "win.font_dec")
        v3.append(self._t_or("mi_font", "Caratteri…"), "win.choose_font")
        m_view.append_section(None, v3)
        widths = Gio.Menu()
        for codice, chiave, ripiego in (
                ("normal", "mi_width_normal", "Normale"),
                ("wide", "mi_width_wide", "Larga")):
            it = Gio.MenuItem.new(self._t_or(chiave, ripiego), None)
            it.set_action_and_target_value("win.reading_width", GLib.Variant("s", codice))
            widths.append_item(it)
        m_view.append_section(self._t_or("mi_width", "Larghezza della colonna"), widths)
        view.append_submenu(self.t("menu_view"), m_view)
        m_look = Gio.Menu()
        style = Gio.Menu()
        for codice, chiave, ripiego in (
                ("auto", "mi_appearance_auto", "Automatico (come il sistema)"),
                ("light", "mi_appearance_light", "Chiaro"),
                ("dark", "mi_appearance_dark", "Scuro")):
            it = Gio.MenuItem.new(self._t_or(chiave, ripiego), None)
            it.set_action_and_target_value("win.appearance", GLib.Variant("s", codice))
            style.append_item(it)
        m_look.append_section(None, style)
        themes = Gio.Menu()
        for code in pw_model.THEMES:
            it = Gio.MenuItem.new(model_theme_label(code, translate=self._t_or), None)
            it.set_action_and_target_value("win.theme_family", GLib.Variant("s", code))
            themes.append_item(it)
        m_look.append_section(self._t_or("mi_theme", "Tema"), themes)
        view.append_submenu(self._t_or("mi_appearance", "Aspetto"), m_look)
        menu.append_section(None, view)

        app = Gio.Menu()
        app.append(self._t_or("mi_md_help", "Guida ai comandi Markdown"), "win.md_help")
        app.append(self.t("shortcuts"), "win.shortcuts")
        app.append(self.t("mi_about"), "win.about")
        menu.append_section(None, app)
        return menu

    def _rebuild_menubar(self):
        if getattr(self, "menu_button", None) is not None:
            self.menu_button.set_menu_model(self._build_menu_model())
            self.menu_button.set_tooltip_text(self.t("main_menu"))

    # ---- interfaccia --------------------------------------------------------
    def _build_ui(self):
        # Barra del titolo GNOME: a sinistra pannello dei capitoli e nuovo
        # capitolo; al centro il titolo del progetto; a destra menu
        # principale, Salva, anteprima e pannello delle note.
        header = Adw.HeaderBar()
        self.window_title = Adw.WindowTitle(title=APP_NAME)
        header.set_title_widget(self.window_title)
        self._header_buttons = []
        for icon, action, key in (
                ("sidebar-show-symbolic", "win.toggle_left", "mi_toggle_left"),
                ("list-add-symbolic", "win.add", "mi_add"),
                ("open-menu-symbolic", None, "main_menu"),
                ("document-save-symbolic", "win.save", "mi_save"),
                ("view-reveal-symbolic", "win.preview", "mi_preview"),
                ("sidebar-show-right-symbolic", "win.toggle_right", "mi_toggle_right")):
            if action is None:
                # pack_end va da destra verso sinistra: il menu all'estremo
                self.menu_button = Gtk.MenuButton(icon_name=icon, primary=True)
                header.pack_end(self.menu_button)
                continue
            if action == "win.preview":
                # EN: a toggle: pressed while the preview is shown, so the
                #     mode is always visible (same icon, as in GNOME).
                # IT: un interruttore: premuto mentre è mostrata l'anteprima,
                #     così la modalità si vede sempre (stessa icona, come in
                #     GNOME).
                b = Gtk.ToggleButton(icon_name=icon)
                b.connect("toggled", self._on_preview_button)
                self.preview_button = b
                header.pack_end(b)
                continue
            b = Gtk.Button(icon_name=icon, action_name=action)
            self._header_buttons.append((b, key))
            if action in ("win.toggle_left", "win.add"):
                header.pack_start(b)
            else:
                header.pack_end(b)

        # Dimensione del testo e lingua del correttore: nella barra in basso.
        adj = Gtk.Adjustment(value=self.font_size, lower=MIN_FONT_SIZE,
                             upper=MAX_FONT_SIZE, step_increment=1, page_increment=2)
        self.font_size_spin = Gtk.SpinButton()
        self.font_size_spin.set_adjustment(adj)
        self.font_size_spin.set_numeric(True)
        self.font_size_spin.set_valign(Gtk.Align.CENTER)
        self.font_size_spin.connect("value-changed", self.on_font_size_changed)
        self.spell_combo = Gtk.ComboBoxText()
        self.spell_combo.set_valign(Gtk.Align.CENTER)
        self._populate_spell_combo()
        self.spell_combo.connect("changed", self.on_spell_lang_changed)

        paned_outer = Gtk.Paned(orientation=Gtk.Orientation.HORIZONTAL)
        paned_inner = Gtk.Paned(orientation=Gtk.Orientation.HORIZONTAL)
        paned_outer.set_vexpand(True)
        paned_outer.set_hexpand(True)

        # colonna sinistra
        left = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self.lbl_left = Gtk.Label(label="", xalign=0, margin_start=12,
                                  margin_top=8, margin_bottom=6)
        self.lbl_left.add_css_class("heading")
        left.append(self.lbl_left)

        self.list_store = Gtk.StringList()
        self.list_selection = Gtk.SingleSelection(model=self.list_store)
        self.list_selection.set_autoselect(False)
        self.list_selection.set_can_unselect(True)
        self.list_selection.connect("selection-changed", self.on_select_chapter)
        factory = Gtk.SignalListItemFactory()
        factory.connect("setup", self._chapter_item_setup)
        factory.connect("bind", self._chapter_item_bind)
        self.tree = Gtk.ListView(model=self.list_selection, factory=factory)
        self.tree.add_css_class("chapter-list")
        self.tree.add_css_class("navigation-sidebar")
        click = Gtk.GestureClick()
        click.set_button(1)
        click.connect("pressed", self.on_list_click)
        self.tree.add_controller(click)
        sw_left = Gtk.ScrolledWindow()
        sw_left.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        sw_left.set_vexpand(True)
        sw_left.set_child(self.tree)
        left.append(sw_left)

        movebar = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6,
                          homogeneous=True, margin_start=6, margin_end=6,
                          margin_top=6, margin_bottom=6)
        self.btn_up = Gtk.Button(icon_name="go-up-symbolic")
        self.btn_down = Gtk.Button(icon_name="go-down-symbolic")
        for b in (self.btn_up, self.btn_down):
            b.add_css_class("flat")
        self.btn_up.connect("clicked", self.on_move_up)
        self.btn_down.connect("clicked", self.on_move_down)
        movebar.append(self.btn_up)
        movebar.append(self.btn_down)
        left.append(movebar)

        # colonna centrale
        center = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self._center_box = center
        self._find_bar = None
        self.center_title = Gtk.Label(label="Testo", xalign=0, margin_start=12,
                                      margin_top=8, margin_bottom=6,
                                      ellipsize=Pango.EllipsizeMode.END)
        self.center_title.add_css_class("heading")
        center.append(self.center_title)

        # Area di scrittura. libspelling (Spelling.TextBufferAdapter) richiede
        # un GtkSource.Buffer, non un Gtk.TextBuffer normale: quindi, se
        # GtkSourceView 5 e' disponibile, costruiamo un GtkSource.View con il
        # suo GtkSource.Buffer (entrambi sottoclassi di Gtk.TextView/TextBuffer,
        # percio' tutto il resto del codice resta invariato). Disattiviamo
        # l'evidenziazione di sintassi di GtkSourceView per non interferire con
        # i nostri tag markdown. Se GtkSourceView manca, ripieghiamo su un
        # normale Gtk.TextView (e il controllo ortografico restera' inattivo).
        if GtkSource is not None:
            self.text_buffer = GtkSource.Buffer()
            try:
                self.text_buffer.set_highlight_syntax(False)
                self.text_buffer.set_highlight_matching_brackets(False)
            except Exception:
                pass
            self.text_view = _vista_che_segue_la_larghezza(GtkSource.View)(
                self._update_reading_margins, buffer=self.text_buffer)
        else:
            self.text_view = _vista_che_segue_la_larghezza(Gtk.TextView)(
                self._update_reading_margins)
            self.text_buffer = self.text_view.get_buffer()
        self.text_view.set_wrap_mode(Gtk.WrapMode.WORD)
        self.text_view.add_css_class("text-editor")
        self.text_view.set_top_margin(16)
        self.text_view.set_bottom_margin(16)
        pal = self.palette()
        head_color = pal["head"]
        self._md_tags = {
            "h1": self.text_buffer.create_tag("h1", weight=Pango.Weight.BOLD,
                                              scale=1.6, foreground=head_color),
            "h2": self.text_buffer.create_tag("h2", weight=Pango.Weight.BOLD,
                                              scale=1.35, foreground=head_color),
            "h3": self.text_buffer.create_tag("h3", weight=Pango.Weight.BOLD,
                                              scale=1.18, foreground=head_color),
            "bold": self.text_buffer.create_tag("bold", weight=Pango.Weight.BOLD),
            "italic": self.text_buffer.create_tag("italic", style=Pango.Style.ITALIC),
            "bolditalic": self.text_buffer.create_tag(
                "bolditalic", weight=Pango.Weight.BOLD, style=Pango.Style.ITALIC),
            "code": self.text_buffer.create_tag(
                "code", family="monospace", foreground=pal["code"]),
            "marker": self.text_buffer.create_tag("marker",
                                                  foreground=pal["marker"]),
            # Tinge le righe che il comando "Ricuci i paragrafi" unirebbe.
            # paragraph-background colora la riga per tutta la sua larghezza,
            # cosi' la spezzatura si vede anche dove il testo finisce prima.
            "wrapmark": self.text_buffer.create_tag(
                "wrapmark", paragraph_background=pal["wrapmark"]),
        }
        self.text_buffer.connect("changed", self.on_text_changed)
        self._install_dict_mouse()
        self._block_file_drops_on_editor()
        self._autocap_busy = False
        self.text_buffer.connect("insert-text", self.on_insert_autocap)
        sw_center = Gtk.ScrolledWindow()
        sw_center.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        sw_center.set_vexpand(True)
        sw_center.set_child(self.text_view)
        self._sw_center = sw_center

        self.preview_view = Gtk.TextView()
        self.preview_view.set_editable(False)
        self.preview_view.set_cursor_visible(False)
        self.preview_view.set_wrap_mode(Gtk.WrapMode.WORD)
        self.preview_view.set_left_margin(24)
        self.preview_view.set_right_margin(24)
        self.preview_view.set_top_margin(12)
        self.preview_view.add_css_class("text-editor")
        self.preview_buffer = self.preview_view.get_buffer()
        head_color = self.palette()["head"]
        self._pv_tags = {
            "h1": self.preview_buffer.create_tag("h1", weight=Pango.Weight.BOLD,
                                                 scale=1.7, foreground=head_color),
            "h2": self.preview_buffer.create_tag("h2", weight=Pango.Weight.BOLD,
                                                 scale=1.4, foreground=head_color),
            "h3": self.preview_buffer.create_tag("h3", weight=Pango.Weight.BOLD,
                                                 scale=1.2, foreground=head_color),
            "bold": self.preview_buffer.create_tag("bold", weight=Pango.Weight.BOLD),
            "italic": self.preview_buffer.create_tag("italic", style=Pango.Style.ITALIC),
            "bolditalic": self.preview_buffer.create_tag(
                "bolditalic", weight=Pango.Weight.BOLD, style=Pango.Style.ITALIC),
            "code": self.preview_buffer.create_tag("code", family="monospace"),
            "quote": self.preview_buffer.create_tag(
                "quote", style=Pango.Style.ITALIC, left_margin=40, foreground=head_color),
            "sep": self.preview_buffer.create_tag(
                "sep", justification=Gtk.Justification.CENTER, foreground=head_color),
        }
        sw_preview = Gtk.ScrolledWindow()
        sw_preview.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        sw_preview.set_vexpand(True)
        sw_preview.set_child(self.preview_view)
        # EN: preview tables are as wide as the page: when the width changes,
        #     the preview is laid out again (once, when resizing settles).
        # IT: le tabelle dell'anteprima sono larghe quanto la pagina: se la
        #     larghezza cambia, l'anteprima si ricompone (una volta, a
        #     ridimensionamento finito).
        self._pv_has_table = False
        self._pv_width = 0
        self._pv_relayout_id = 0
        sw_preview.get_hadjustment().connect("notify::page-size", self._on_preview_width)

        self.center_stack = Gtk.Stack()
        self.center_stack.add_named(sw_center, "editor")
        self.center_stack.add_named(sw_preview, "preview")
        self.center_stack.set_visible_child_name("editor")
        self.center_stack.set_vexpand(True)
        self._preview_mode = False
        center.append(self.center_stack)

        # colonna destra
        right = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self.lbl_right = Gtk.Label(label="", xalign=0, margin_start=12,
                                   margin_top=8, margin_bottom=6)
        self.lbl_right.add_css_class("heading")
        right.append(self.lbl_right)
        self.note_view = Gtk.TextView(top_margin=12, bottom_margin=12,
                                      left_margin=12, right_margin=12)
        self.note_view.set_wrap_mode(Gtk.WrapMode.WORD)
        self.note_view.add_css_class("notes-editor")
        self.note_buffer = self.note_view.get_buffer()
        self.note_buffer.connect("changed", self.on_note_changed)
        sw_right = Gtk.ScrolledWindow()
        sw_right.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        sw_right.set_vexpand(True)
        sw_right.set_child(self.note_view)
        right.append(sw_right)

        self.paned_outer = paned_outer
        self.paned_inner = paned_inner
        self.left_panel = left
        self.right_panel = right

        paned_inner.set_start_child(center)
        paned_inner.set_resize_start_child(True)
        paned_inner.set_shrink_start_child(False)
        paned_inner.set_end_child(right)
        paned_inner.set_resize_end_child(False)
        paned_inner.set_shrink_end_child(False)
        paned_outer.set_start_child(left)
        paned_outer.set_resize_start_child(False)
        paned_outer.set_shrink_start_child(False)
        paned_outer.set_end_child(paned_inner)
        paned_outer.set_resize_end_child(True)
        paned_outer.set_shrink_end_child(False)
        paned_outer.connect("notify::position", self.on_divider_moved)
        paned_inner.connect("notify::position", self.on_divider_moved)

        statusbar = Gtk.CenterBox(margin_start=12, margin_end=6,
                                  margin_top=3, margin_bottom=3)
        self.wordcount_label = Gtk.Label(label="Parole: 0", xalign=0,
                                         ellipsize=Pango.EllipsizeMode.END)
        statusbar.set_start_widget(self.wordcount_label)
        self.detail_label = Gtk.Label(label="", xalign=0.5,
                                      ellipsize=Pango.EllipsizeMode.END)
        statusbar.set_center_widget(self.detail_label)
        self.totalcount_label = Gtk.Label(label="Totale progetto: 0", xalign=1)
        end = Gtk.Box(spacing=6)
        end.append(self.totalcount_label)
        end.append(self.spell_combo)
        end.append(self.font_size_spin)
        statusbar.set_end_widget(end)
        for lbl in (self.wordcount_label, self.detail_label, self.totalcount_label):
            lbl.add_css_class("dim-label")
            lbl.add_css_class("numeric")

        self.toasts = Adw.ToastOverlay(child=paned_outer)
        self.toolbar = Adw.ToolbarView(content=self.toasts)
        self.toolbar.add_top_bar(header)
        self.toolbar.add_bottom_bar(statusbar)
        self.set_content(self.toolbar)

        # stato iniziale corretto di barra menu / pulsante hamburger
        self._sync_menu_chrome()
        GLib.idle_add(self._update_reading_margins)

    def _chapter_item_setup(self, factory, list_item):
        label = Gtk.Label(xalign=0)
        label.set_ellipsize(Pango.EllipsizeMode.END)
        label.add_css_class("chapter-list")
        list_item.set_child(label)

    def _chapter_item_bind(self, factory, list_item):
        label = list_item.get_child()
        item = list_item.get_item()
        label.set_text(item.get_string())

    def _update_tag_colors(self):
        """Riallinea i colori del testo Markdown alla tavolozza corrente.
        Chiamata a ogni cambio di famiglia di tema e di chiaro/scuro."""
        pal = self.palette()
        head_color = pal["head"]
        for name in ("h1", "h2", "h3"):
            try:
                self._md_tags[name].set_property("foreground", head_color)
                self._pv_tags[name].set_property("foreground", head_color)
            except Exception:
                pass
        try:
            self._md_tags["code"].set_property("foreground", pal["code"])
            self._md_tags["marker"].set_property("foreground", pal["marker"])
            self._md_tags["wrapmark"].set_property("paragraph-background",
                                                  pal["wrapmark"])
            self._pv_tags["quote"].set_property("foreground", head_color)
            self._pv_tags["sep"].set_property("foreground", head_color)
        except Exception:
            pass

    @staticmethod
    def _count_words(text):
        return len(text.split())

    @staticmethod
    def _count_chars(text):
        return sum(len(line) for line in text.splitlines())

    def _update_wordcount(self):
        if self.current is not None and not self.current.is_cover:
            chapter_words = self._count_words(self.current.text)
        else:
            chapter_words = 0
        total = sum(self._count_words(c.text)
                    for c in self.project.chapters if not c.is_cover)
        total_chars = sum(self._count_chars(c.text)
                          for c in self.project.chapters if not c.is_cover)
        self.wordcount_label.set_text(self.t("wc_chapter", n=chapter_words))
        self.totalcount_label.set_text(self.t("wc_total", n=total))
        pages = max(1, round(total / 250)) if total else 0
        detail = (self.t("wc_chars", n=total_chars) + "    "
                  + self.t("wc_pages", n=pages))
        if getattr(self, "word_goal", 0) > 0:
            pct = min(100, round(total * 100 / self.word_goal))
            detail += "    " + self.t("goal_status",
                                      c=total, g=self.word_goal, p=pct)
        self.detail_label.set_text(detail)

    def _chapter_title(self, ch):
        return ch.title_with_fallback(self.t("chapter_n"), self.t("cover_label"))

    def on_ui_lang_changed(self, code):
        if code == self.lang:
            return
        self.lang = code
        apply_toolkit_language(code)
        self.translator.set_language(code)
        self.project._lang = code
        self.settings["ui_lang"] = code
        save_settings(self.settings)
        self._retranslate()
        self._refresh_chapter_list(max(0, self._current_index()))
        if hasattr(self, "spell_combo"):
            self._populate_spell_combo()

    def _apply_text_direction(self):
        """Orienta le aree di scrittura secondo la lingua dell'interfaccia.

        Arabo, urdu, persiano ed ebraico si scrivono da destra a sinistra.
        RTL_LANGUAGES lo dichiarava gia', ma nessuno lo leggeva: si potevano
        scegliere quelle quattro lingue e ritrovarsi il cursore a sinistra e il
        testo che partiva dal lato sbagliato.

        NB: questo orienta l'AREA DI SCRITTURA. L'impaginatore PDF compone
        ancora da sinistra a destra: per quelle lingue l'export non e' ancora
        corretto, ed e' un lavoro a se'."""
        verso = (Gtk.TextDirection.RTL if self.lang in RTL_LANGUAGES
                 else Gtk.TextDirection.LTR)
        for widget in (getattr(self, "text_view", None),
                       getattr(self, "note_view", None),
                       getattr(self, "preview_view", None)):
            if widget is not None:
                try:
                    widget.set_direction(verso)
                except Exception:
                    pass   # l'orientamento non deve mai impedire di scrivere

    def _retranslate(self):
        self._apply_text_direction()
        self._rebuild_menubar()
        # EN/IT: setting the extra menu again makes GTK rebuild the whole
        # right-click menu, its own items included, in the new language.
        # / reimpostare il menu aggiuntivo fa ricostruire a GTK tutto il menu
        # del tasto destro, comprese le sue voci, nella lingua nuova.
        if getattr(self, "text_view", None) is not None:
            self._apply_extra_menu()
        self.btn_up.set_tooltip_text(self.t("mi_up"))
        self.btn_down.set_tooltip_text(self.t("mi_down"))
        for b, key in getattr(self, "_header_buttons", ()):
            b.set_tooltip_text(self.t(key))
            b.update_property([Gtk.AccessibleProperty.LABEL], [self.t(key)])
        if getattr(self, "preview_button", None) is not None:
            self._sync_preview_button()
        for b, key in ((self.btn_up, "mi_up"), (self.btn_down, "mi_down")):
            b.update_property([Gtk.AccessibleProperty.LABEL], [self.t(key)])
        self.font_size_spin.set_tooltip_text(self.t("tip_font_size"))
        self.spell_combo.set_tooltip_text(self.t("tip_spell_lang"))
        self.lbl_left.set_text(self.t("col_chapters"))
        self.lbl_right.set_text(self.t("col_notes"))
        if self.current is not None:
            self.center_title.set_text(self._chapter_title(self.current))
        else:
            self.center_title.set_text(self.t("col_text"))
        self._update_wordcount()

    # ---- modello visuale ---------------------------------------------------
    def _cover_offset(self):
        """1 se il primo capitolo e' la copertina (nascosta dalla lista), 0 se no.
        La copertina resta nel progetto ma non compare piu' come voce di lista:
        il suo contenuto ora viene dai campi del frontespizio."""
        chs = self.project.chapters
        return 1 if (chs and chs[0].is_cover) else 0

    def _row_to_index(self, row):
        """Riga visibile della lista -> indice reale in project.chapters."""
        return row + self._cover_offset()

    def _index_to_row(self, index):
        """Indice in project.chapters -> riga visibile (>=0)."""
        return max(0, index - self._cover_offset())

    def _refresh_chapter_list(self, select_index=0):
        # select_index e' un INDICE in project.chapters (come passato dai chiamanti)
        self._loading = True
        n = self.list_store.get_n_items()
        if n:
            self.list_store.splice(0, n, [])
        off = self._cover_offset()
        for ch in self.project.chapters[off:]:   # salta la copertina
            self.list_store.append(self._chapter_title(ch))
        self._loading = False
        if self.list_store.get_n_items():
            self._set_editing_enabled(True)
            self._select_row(self._index_to_row(select_index))
        else:
            # nessun capitolo: stato neutro, aree di testo vuote e non
            # modificabili finche' l'utente non crea un capitolo
            self._show_empty_state()
        self._update_window_title()
        self._update_wordcount()
        self._update_window_title()

    def _show_empty_state(self):
        """Progetto senza capitoli: svuota i buffer, disabilita la scrittura e
        mostra un suggerimento al centro. Evita che il testo digitato finisca
        nel nulla (current e' None) o che restino i contenuti del progetto
        precedente."""
        self.current = None
        self._loading = True
        self.text_buffer.set_text("")
        self.note_buffer.set_text("")
        self._loading = False
        # La scia del menu ("Capitolo -> Aggiungi capitolo") non e' scritta a
        # mano nella frase: arriva dalle voci di menu vere. Cosi' se un giorno
        # una voce cambia nome, o viene tradotta, il suggerimento la segue e
        # non puo' piu' indicare un comando che non esiste.
        self.center_title.set_text(self.t("empty_hint",
                                          menu=self.t("main_menu"),
                                          item=self.t("mi_add")))
        self._set_editing_enabled(False)

    def _set_editing_enabled(self, enabled):
        self.text_view.set_editable(enabled)
        self.text_view.set_cursor_visible(enabled)
        self.note_view.set_editable(enabled)
        self.note_view.set_cursor_visible(enabled)

    def _select_row(self, row):
        if 0 <= row < self.list_store.get_n_items():
            self.list_selection.set_selected(row)
            self._load_row(row)

    def _commit_current(self):
        if self.current is None:
            return
        s, e = self.text_buffer.get_bounds()
        self.current.text = self.text_buffer.get_text(s, e, True)
        s, e = self.note_buffer.get_bounds()
        self.current.note = self.note_buffer.get_text(s, e, True)

    def on_list_click(self, gesture, n_press, x, y):
        if n_press != 1:
            return
        row_index = self._row_at_y(y)
        if row_index is None:
            return
        if self.list_selection.get_selected() == row_index:
            self._commit_current()
            self.current = None
            self.list_selection.unselect_all()
            self._loading = True
            self.text_buffer.set_text("")
            self.note_buffer.set_text("")
            self.center_title.set_text(self.t("col_text"))
            self._loading = False
            self._update_wordcount()
            gesture.set_state(Gtk.EventSequenceState.CLAIMED)

    def _row_at_y(self, y):
        n = self.list_store.get_n_items()
        if n == 0:
            return None
        child = self.tree.get_first_child()
        row_h = 0
        while child is not None:
            h = child.get_allocated_height()
            if h > 0:
                row_h = h
                break
            child = child.get_next_sibling()
        if row_h <= 0:
            return None
        idx = int(y // row_h)
        if 0 <= idx < n:
            return idx
        return None

    # firma imposta dal segnale "selection-changed": i tre parametri
    # arrivano da GTK e non servono, la selezione si rilegge dal modello
    def on_select_chapter(self, _selection=None, _position=None,
                          _n_items=None):
        if self._loading:
            return
        sel = self.list_selection.get_selected()
        if sel == Gtk.INVALID_LIST_POSITION:
            self._commit_current()
            self.current = None
            self._loading = True
            self.text_buffer.set_text("")
            self.note_buffer.set_text("")
            self.center_title.set_text(self.t("col_text"))
            self._loading = False
            self._update_wordcount()
            return
        self._load_row(sel)

    def _load_row(self, row):
        self._close_dict_popover()
        index = self._row_to_index(row)
        if not (0 <= index < len(self.project.chapters)):
            return
        if self.current is self.project.chapters[index]:
            return
        self._commit_current()
        self.current = self.project.chapters[index]
        self._loading = True
        self.text_buffer.set_text(self.current.text)
        self.note_buffer.set_text(self.current.note)
        self.center_title.set_text(self._chapter_title(self.current))
        self._loading = False
        self._highlight_markdown()
        self._update_wordcount()
        if getattr(self, "_preview_mode", False):
            self._render_preview()

    def on_insert_autocap(self, buf, location, text, length):
        if self._loading or self._autocap_busy:
            return
        if length != 1 or not text.isalpha() or not text.islower():
            return
        it_prev = location.copy()
        if not it_prev.backward_char():
            self._do_autocap(buf, location, text)
            return
        prev = it_prev.get_char()
        if prev not in (" ", "\n", "\t"):
            return
        scan = it_prev.copy()
        ch = prev
        while ch in (" ", "\t"):
            if not scan.backward_char():
                self._do_autocap(buf, location, text)
                return
            ch = scan.get_char()
        if ch in (".", "!", "?", "\n"):
            self._do_autocap(buf, location, text)

    def _do_autocap(self, buf, location, text):
        self._autocap_busy = True
        buf.stop_emission_by_name("insert-text")
        buf.insert(location, text.upper(), -1)
        self._autocap_busy = False

    def on_text_changed(self, buf):
        # EN/IT: the dictionary sheet goes away by itself as soon as you
        # write: it is a glance, not a window to manage.
        self._close_dict_popover()
        if self._loading or self.current is None:
            return
        s, e = buf.get_bounds()
        self.current.text = buf.get_text(s, e, True)
        self._mark_dirty()
        row = self._current_row()
        if row >= 0:
            title = self._chapter_title(self.current)
            if self.list_store.get_string(row) != title:
                self._loading = True
                self.list_store.splice(row, 1, [title])
                self.list_selection.set_selected(row)
                self._loading = False
            self.center_title.set_text(title)
        self._highlight_markdown()
        self._update_wordcount()

    # ---- immagini: figura vera, o riquadro per collegarla ------------------
    def _image_texture(self, name):
        """Texture di un'immagine del progetto (None se manca o non si legge)."""
        data = self.project.images.get(name)
        if not data:
            return None
        cache = self.__dict__.setdefault("_img_textures", {})
        key = (name, len(data), hash(data[:4096]))
        if key not in cache:
            try:
                cache[key] = Gdk.Texture.new_from_bytes(GLib.Bytes.new(data))
            except GLib.Error:
                cache[key] = None
            if len(cache) > 64:
                cache.clear()
                return self._image_texture(name)
        return cache[key]

    def _image_widget(self, src, caption, width, fg, subtle):
        """Immagine del capitolo per anteprima ed editor. Se il file non è nel
        progetto (es. un ![…](italia.jpg) incollato o importato senza il
        file), un riquadro lo dice e offre di sceglierlo."""
        tex = self._image_texture(src)
        cap = (f'<span foreground="{subtle}">{GLib.markup_escape_text(caption)}</span>'
               if caption else "")
        if tex is not None:
            return rusca_liveblocks.image_widget(tex, cap, width)
        msg = self._t_or("img_not_in_project",
                         "Immagine non presente nel progetto: {src}", src=src)
        box = rusca_liveblocks.image_widget(
            None, "", width,
            f'<span foreground="{fg}">{GLib.markup_escape_text(msg)}</span>')
        box.set_size_request(int(width), -1)
        button = Gtk.Button(label=self._t_or("img_choose", "Scegli l'immagine…"),
                            halign=Gtk.Align.CENTER, margin_bottom=12)
        button.add_css_class("suggested-action")
        button.connect("clicked", lambda *_a: self._relink_image(src))
        box.append(button)
        return box

    def _relink_image(self, src):
        """Sceglie il file di un'immagine citata ma assente: lo copia nel
        progetto e aggiorna i riferimenti ](src) del capitolo corrente."""
        row = self._current_index()
        if row < 0 or self.project.chapters[row].is_cover:
            self._error(self.t("img_only_chapter"))
            return

        def on_path(path):
            try:
                with open(path, "rb") as f:
                    name = self.project.add_image(f.read())
            except ValueError:
                self._error(self.t("err_img_format"))
                return
            except Exception as exc:
                self._error(self.t("err_open", e=exc))
                return
            buf = self.text_buffer
            needle = f"]({src})"
            buf.begin_user_action()
            it = buf.get_start_iter()
            while True:
                found = it.forward_search(needle, Gtk.TextSearchFlags.TEXT_ONLY, None)
                if not found:
                    break
                a, b = found
                buf.delete(a, b)
                buf.insert(a, f"]({name})")
                it = a
            buf.end_user_action()
            self._commit_current()
            self._mark_dirty()
            if self._preview_mode:
                self._render_preview()

        self._open_file_dialog(self.t("mi_insert_image"),
                               ["*.png", "*.jpg", "*.jpeg", "*.webp"],
                               self.t("filter_image"), on_path)

    def _highlight_markdown(self):
        """Colora il Markdown mentre si scrive. Usa lo stesso motore degli
        export (model.highlight_spans): ciò che qui appare in grassetto
        uscirà in grassetto anche nel PDF."""
        buf = self.text_buffer
        start, end = buf.get_bounds()
        for tag in self._md_tags.values():
            buf.remove_tag(tag, start, end)
        text = buf.get_text(start, end, True)

        def apply(tag_name, a, b):
            tag = self._md_tags.get(tag_name)
            if tag is None:
                return
            buf.apply_tag(tag, buf.get_iter_at_offset(a),
                          buf.get_iter_at_offset(b))

        lines = text.split("\n")
        offset = 0
        starts = []
        for line in lines:
            starts.append(offset)
            offset += len(line) + 1
        try:
            for a, b, style in highlight_spans(text):
                apply(style, a, b)
        except Exception as err:            # mai bloccare la scrittura
            print(f"[ruscawriter] evidenziazione: {err}", file=sys.stderr)

        # Vista "Mostra le interruzioni": tinge i gruppi di righe che il
        # comando di ricucitura unirebbe. Sono decisi da model.wrapped_runs,
        # la stessa funzione che poi esegue l'unione: cio' che si vede
        # evidenziato e' esattamente cio' che verrebbe toccato.
        if getattr(self, "show_breaks", False):
            for first, last in wrapped_runs(text):
                apply("wrapmark", starts[first],
                      starts[last] + len(lines[last]))

    def on_note_changed(self, buf):
        if self._loading or self.current is None:
            return
        s, e = buf.get_bounds()
        self.current.note = buf.get_text(s, e, True)
        self._mark_dirty()

    # ---- helper dialoghi asincroni -----------------------------------------
    def _dialog_shell(self, title, size=None, spacing=12, margin=20):
        """Dialogo GNOME (RuscaDialog) e il suo contenitore. Restituisce
        (dialogo, contenitore): il chiamante riempie il contenitore e chiude
        con _dialog_present()."""
        dialog = RuscaDialog(self, title, size)
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=spacing)
        box.set_margin_top(margin); box.set_margin_bottom(margin)
        box.set_margin_start(margin); box.set_margin_end(margin)
        return dialog, box

    def _ok_cancel_row(self, box, on_ok, on_cancel=None, ok_label=None,
                       with_cancel=False):
        """Coppia Annulla / OK in fondo a un dialogo complesso."""
        btns = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6,
                       halign=Gtk.Align.END, margin_top=6)
        b_cancel = Gtk.Button(label=self.t("cancel"))
        b_ok = Gtk.Button(label=ok_label or self.t("ok"))
        b_ok.add_css_class("suggested-action")
        btns.append(b_cancel)
        btns.append(b_ok)
        box.append(btns)
        b_cancel.connect("clicked", on_cancel or (lambda *_a: None))
        b_ok.connect("clicked", on_ok)
        return (b_ok, b_cancel) if with_cancel else b_ok

    def _dialog_present(self, dialog, box, default_widget=None):
        dialog.set_child(box)
        if default_widget is not None:
            dialog.set_default_widget(default_widget)
        dialog.present()
        if default_widget is not None:
            default_widget.grab_focus()

    def _alert(self, heading, body, responses, default_id, close_id, on_response,
               extra=None, destructive=()):
        dialog = Adw.AlertDialog(heading=heading or "", body=body or "")
        for rid, label in responses:
            dialog.add_response(rid, label)
            if rid in destructive:
                dialog.set_response_appearance(rid, Adw.ResponseAppearance.DESTRUCTIVE)
        if default_id is not None:
            dialog.set_default_response(default_id)
            if default_id not in destructive and default_id != close_id:
                dialog.set_response_appearance(default_id, Adw.ResponseAppearance.SUGGESTED)
        if close_id is not None:
            dialog.set_close_response(close_id)
        if extra is not None:
            dialog.set_extra_child(extra)
        dialog.connect("response", lambda _d, rid: on_response(rid))
        dialog.present(self)
        return dialog

    def _message_dialog(self, title, body):
        self._alert(title, str(body), (("ok", self.t("ok")),), "ok", "ok",
                    lambda _rid: None)

    def toast(self, msg):
        self.toasts.add_toast(Adw.Toast(title=GLib.markup_escape_text(str(msg))))

    def _info(self, msg):
        # Conferme brevi: notifica in basso, senza un dialogo da chiudere.
        text = str(msg)
        if len(text) <= 120 and "\n" not in text:
            self.toast(text)
        else:
            self._message_dialog(None, text)

    def _error(self, msg):
        self._message_dialog(self.t("error_title"), msg)

    def _ask_text(self, title, prompt, initial, on_ok):
        entry = Gtk.Entry(text=initial or "", activates_default=True)
        self._alert(title, prompt, (("cancel", self.t("cancel")), ("ok", self.t("ok"))),
                    "ok", "cancel",
                    lambda rid: rid == "ok" and on_ok(entry.get_text()), extra=entry)
        entry.grab_focus()
        # il testo proposto e' selezionato: si sostituisce scrivendo
        entry.select_region(0, -1)

    def _ask_number(self, title, prompt, initial, lower, upper, step, on_ok):
        adj = Gtk.Adjustment(value=initial, lower=lower, upper=upper,
                             step_increment=step, page_increment=step * 10)
        spin = Gtk.SpinButton(adjustment=adj, numeric=True, activates_default=True,
                              halign=Gtk.Align.CENTER)
        self._alert(title, prompt, (("cancel", self.t("cancel")), ("ok", self.t("ok"))),
                    "ok", "cancel",
                    lambda rid: rid == "ok" and on_ok(int(spin.get_value())), extra=spin)
        spin.grab_focus()

    def _confirm(self, title, body, buttons, default_idx, cancel_idx, on_choice):
        """Conferma con N pulsanti; on_choice(indice) viene chiamato una
        volta, fuori dai segnali del dialogo. La chiusura vale cancel_idx."""
        responses = tuple((str(i), label) for i, label in enumerate(buttons))
        close_id = str(cancel_idx) if cancel_idx is not None else None
        # Con tre scelte (Salva / Non salvare / Annulla) quella che non e'
        # ne' la predefinita ne' l'annullamento e' la distruttiva.
        discard = tuple(str(i) for i in range(len(buttons))
                        if len(buttons) > 2 and i not in (default_idx, cancel_idx))

        def done(rid):
            idx = int(rid) if rid is not None and rid.lstrip("-").isdigit() else \
                (cancel_idx if cancel_idx is not None else -1)
            GLib.idle_add(lambda: (on_choice(idx), False)[1])
        self._alert(title, body,
                    responses, str(default_idx) if default_idx is not None else None,
                    close_id, done, destructive=discard)

    def _file_dialog(self, title, patterns, filter_name,
                     suggested_name=None, multiple=False, on_result=None):
        """Selettore di file: unico punto in cui si costruisce un Gtk.FileDialog.

        I tre casi — salva, apri, apri piu' file — differiscono solo per il
        metodo da chiamare e per quello che restituiscono; il titolo, il filtro
        e la gestione dell'annullamento sono identici e stanno qui una volta
        sola. La richiamata riceve un percorso, o una lista di percorsi se
        multiple=True. Se l'utente annulla, non viene chiamata."""
        dialog = Gtk.FileDialog()
        dialog.set_title(title)
        if suggested_name is not None:
            dialog.set_initial_name(suggested_name)
        if patterns:
            flt = Gtk.FileFilter()
            flt.set_name(filter_name)
            for pattern in patterns:
                flt.add_pattern(pattern)
            filters = Gio.ListStore.new(Gtk.FileFilter)
            filters.append(flt)
            dialog.set_filters(filters)
            dialog.set_default_filter(flt)

        def done(d, result):
            try:
                answer = finish(d, result)
            except GLib.Error:
                return          # l'utente ha annullato: nulla da fare
            if multiple:
                paths = []
                for i in range(answer.get_n_items()):
                    try:
                        path = answer.get_item(i).get_path()
                    except Exception:
                        path = None
                    if path:
                        paths.append(path)
                if paths:
                    on_result(paths)
            elif answer is not None:
                on_result(answer.get_path())

        if suggested_name is not None:
            finish = Gtk.FileDialog.save_finish
            dialog.save(self, None, done)
        elif multiple:
            finish = Gtk.FileDialog.open_multiple_finish
            dialog.open_multiple(self, None, done)
        else:
            finish = Gtk.FileDialog.open_finish
            dialog.open(self, None, done)

    def _save_file_dialog(self, title, suggested_name, patterns, filter_name, on_path):
        self._file_dialog(title, patterns, filter_name,
                          suggested_name=suggested_name or "", on_result=on_path)

    def _open_file_dialog(self, title, patterns, filter_name, on_path):
        self._file_dialog(title, patterns, filter_name, on_result=on_path)

    def _open_files_dialog(self, title, patterns, filter_name, on_paths):
        """Come _open_file_dialog ma permette di selezionare piu' file insieme;
        chiama on_paths(lista_di_percorsi)."""
        self._file_dialog(title, patterns, filter_name,
                          multiple=True, on_result=on_paths)

    def on_import_chapters(self, *_):
        """File -> Importa come capitoli: ogni file .txt/.md scelto diventa un
        nuovo capitolo in fondo al progetto (il progetto resta, non viene
        sostituito)."""
        self._open_files_dialog(self.t("dlg_import_title"),
                                ["*.txt", "*.md", "*.markdown"],
                                self.t("filter_text"),
                                self._import_files_as_chapters)

    # ---- File: nuovo / apri / salva ----------------------------------------
    def on_new(self, *_):
        def proceed():
            self._ask_text(self.t("dlg_new_title"), self.t("dlg_new_prompt"),
                           self.t("default_project"), self._do_new)
        self._guard_discard(proceed)

    def _do_new(self, title):
        title = (title or "").strip() or self.t("default_project")
        self.current = None
        self.project.new(title)
        self.project._lang = self.lang
        self._refresh_chapter_list(0)
        self._mark_clean()

    def on_open(self, *_):
        def proceed():
            self._open_file_dialog(self.t("dlg_open_title"), ["*.rwr"],
                                   self.t("filter_project"), self._do_open)
        self._guard_discard(proceed)

    def _do_open(self, path):
        recovered = self._maybe_recover(path, self._do_open_finish)
        if recovered == "pending":
            return
        self._do_open_finish(path, recovered)

    def _do_open_finish(self, path, recovered):
        try:
            self.current = None
            if recovered is not None:
                self.project.load(recovered)
                self.project._lang = self.lang
            fs = self.project.meta.get("font_size")
            ff = self.project.meta.get("font_family")
            if isinstance(fs, int):
                self.font_size = max(MIN_FONT_SIZE, min(fs, MAX_FONT_SIZE))
            if ff and ff not in ("Special Elite",):
                self.font_family = ff
            elif ff in ("Special Elite",) and self.font_available:
                self.font_family = TYPEWRITER_FAMILY
            self._apply_editor_font()
            sl = self.project.meta.get("spell_lang")
            if sl in ("it", "en"):
                if hasattr(self, "spell_combo"):
                    self.spell_combo.set_active_id(sl)
                # applica la lingua ortografica del documento tramite il
                # percorso unico (gestisce libspelling e gspell2)
                self._set_spell_lang(sl)
            self._refresh_chapter_list(0)
            self._mark_clean()
        except Exception as exc:
            self._error(self.t("err_open", e=exc))

    def _maybe_recover(self, path, finish_cb):
        auto = path + ".autosave"
        try:
            if (os.path.exists(auto)
                    and os.path.getmtime(auto) > os.path.getmtime(path)):
                yes = self.translator._strings.get("yes", "Sì")
                no = self.translator._strings.get("no", "No")

                def choice(idx):
                    if idx == 0:
                        try:
                            self.project.load(auto)
                            self.project.path = path
                        except Exception as exc:
                            self._error(self.t("err_open", e=exc))
                            return
                        finish_cb(path, None)
                    else:
                        finish_cb(path, path)

                self._confirm(self.t("recover_title"), self.t("recover_body"),
                              [yes, no], default_idx=0, cancel_idx=1,
                              on_choice=choice)
                return "pending"
        except Exception:
            pass
        return path

    def on_save(self, *_, announce=True, then=None):
        self._commit_current()
        if not self.project.path:
            self._save_file_dialog(self.t("dlg_save_title"),
                                   f"{self.project.title}.rwr", ["*.rwr"],
                                   self.t("filter_project"),
                                   lambda p: self._do_save_as(p, announce=announce,
                                                              then=then))
            return
        self._do_save(None, announce=announce, then=then)

    def _do_save_as(self, path, announce=True, then=None):
        if not path.endswith(".rwr"):
            path += ".rwr"
        self._do_save(path, announce=announce, then=then)

    def _do_save(self, path, announce=True, then=None):
        try:
            self.project.meta["font_size"] = self.font_size
            self.project.meta["font_family"] = self.font_family
            self.project.meta["spell_lang"] = self.spell_lang
            self.project.save(path)
            self._refresh_chapter_list(max(0, self._current_index()))
            self._mark_clean()
            self._cleanup_autosave()
            if announce:
                self._info(self.t("saved"))
            if then is not None:
                then()
        except Exception as exc:
            self._error(self.t("err_save", e=exc))

    def _guard_discard(self, proceed):
        if not self._dirty:
            proceed()
            return

        def choice(idx):
            if idx == 0:
                proceed()
            elif idx == 2:
                # salva (senza popup) e, se riuscito, prosegui con l'azione
                self.on_save(announce=False, then=proceed)

        self._confirm(self.t("unsaved_title"), self.t("unsaved_body"),
                      [self.t("btn_discard"), self.t("btn_cancel"),
                       self.t("btn_save_changes")],
                      default_idx=2, cancel_idx=1, on_choice=choice)

    # ---- capitoli -----------------------------------------------------------
    def on_add_chapter(self, *_):
        self._commit_current()
        self.project.add_chapter()
        self._refresh_chapter_list(len(self.project.chapters) - 1)
        self._mark_dirty()

    def on_delete_chapter(self, *_):
        if not self.project.chapters:
            return
        row = self._current_index()
        if row < 0:
            return
        ch = self.project.chapters[row]
        if ch.is_cover:
            self._error(self.t("del_cover"))
            return
        # (e' consentito eliminare anche l'ultimo capitolo: un progetto senza
        # capitoli e' uno stato legittimo, gestito dallo stato vuoto)

        def choice(idx):
            if idx != 0:
                return
            self.current = None
            self.project.delete_chapter(row)
            new_sel = min(row, len(self.project.chapters) - 1)
            self._refresh_chapter_list(new_sel)
            self._mark_dirty()

        self._confirm(self.t("del_title"),
                      self.t("del_body", t=self._chapter_title(ch)),
                      [self.t("ok"), self.t("cancel")],
                      default_idx=0, cancel_idx=1, on_choice=choice)

    def on_move_up(self, *_):
        self._move(-1)

    def on_move_down(self, *_):
        self._move(+1)

    def on_insert_image(self, *_):
        """EN: Attach an image (PNG/JPEG/WebP) to the current chapter: the
        file is copied INTO the project (it travels inside the .rwr archive)
        and a Markdown line ![caption](img_NNN.ext) is inserted at the
        cursor. The exports render it as a real picture.
        IT: Allega un'immagine (PNG/JPEG/WebP) al capitolo corrente: il file
        viene copiato DENTRO il progetto (viaggia nell'archivio .rwr) e una
        riga Markdown ![didascalia](img_NNN.ext) viene inserita al cursore.
        Gli export la rendono come immagine vera e propria."""
        row = self._current_index()
        if row < 0 or self.project.chapters[row].is_cover:
            # EN/IT: images belong to content chapters, not to the cover
            # (the cover has its own image in File -> Editorial sections).
            self._error(self.t("img_only_chapter"))
            return

        def on_path(path):
            try:
                with open(path, "rb") as f:
                    data = f.read()
                name = self.project.add_image(data)
            except ValueError:
                self._error(self.t("err_img_format"))
                return
            except Exception as exc:
                self._error(self.t("err_open", e=exc))
                return
            # EN: default caption = the original file name (editable text).
            # IT: didascalia predefinita = nome del file originale
            #     (testo modificabile).
            caption = os.path.splitext(os.path.basename(path))[0]
            snippet = f"\n![{caption}]({name})\n"
            self.text_buffer.insert_at_cursor(snippet)
            self._commit_current()
            self._mark_dirty()

        self._open_file_dialog(self.t("mi_insert_image"),
                               ["*.png", "*.jpg", "*.jpeg", "*.webp"],
                               self.t("filter_image"), on_path)

    def _move(self, direction):
        row = self._current_index()
        if row < 0:
            return
        self._commit_current()
        new_row = self.project.move_chapter(row, direction)
        if new_row != row:
            self._refresh_chapter_list(new_row)
            self._mark_dirty()

    def on_rename_chapter(self, *_):
        row = self._current_index()
        if row < 0:
            return
        ch = self.project.chapters[row]
        if ch.is_cover:
            self._error(self.t("rename_cover"))
            return

        def on_ok(new_title):
            ch.custom_title = (new_title or "").strip()
            self._refresh_chapter_list(row)
            if self.current is ch:
                self.center_title.set_text(self._chapter_title(ch))
            self._mark_dirty()

        self._ask_text(self.t("rename_title"), self.t("rename_prompt"),
                       ch.custom_title, on_ok)

    def on_set_goal(self, *_):
        def on_ok(val):
            self.word_goal = max(0, int(val))
            self.settings["word_goal"] = self.word_goal
            save_settings(self.settings)
            self._update_wordcount()

        self._ask_number(self.t("goal_title"), self.t("goal_prompt"),
                         self.word_goal, 0, 10_000_000, 500, on_ok)

    # ---- ricerca / sostituzione --------------------------------------------
    def on_find_replace(self, *_):
        if getattr(self, "_find_bar", None) is not None:
            self._find_entry.grab_focus()
            return
        bar = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
        bar.add_css_class("rusca-findbar")
        bar.set_margin_top(4); bar.set_margin_bottom(4)
        bar.set_margin_start(4); bar.set_margin_end(4)

        self._find_entry = Gtk.SearchEntry()
        self._find_entry.set_placeholder_text(self.t("find_label"))
        self._find_entry.set_hexpand(True)
        self._replace_entry = Gtk.Entry()
        self._replace_entry.set_placeholder_text(self.t("replace_label"))
        self._replace_entry.set_hexpand(True)

        btn_prev = Gtk.Button(label=self.t("find_prev"))
        btn_next = Gtk.Button(label=self.t("find_next"))
        btn_one = Gtk.Button(label=self.t("replace_one"))
        btn_all = Gtk.Button(label=self.t("replace_all"))
        btn_close = Gtk.Button(label="✕")

        btn_next.connect("clicked", lambda *_: self._find_step(+1))
        btn_prev.connect("clicked", lambda *_: self._find_step(-1))
        btn_one.connect("clicked", self._replace_one)
        btn_all.connect("clicked", self._replace_all)
        btn_close.connect("clicked", lambda *_: self._close_find_bar())
        self._find_entry.connect("activate", lambda *_: self._find_step(+1))
        self._find_entry.connect("stop-search", lambda *_: self._close_find_bar())

        for w in (self._find_entry, btn_prev, btn_next,
                  self._replace_entry, btn_one, btn_all, btn_close):
            bar.append(w)

        self._center_box.prepend(bar)
        self._find_bar = bar
        self._find_entry.grab_focus()

    def _close_find_bar(self):
        if getattr(self, "_find_bar", None) is not None:
            self._center_box.remove(self._find_bar)
            self._find_bar = None
            self.text_view.grab_focus()

    def _find_step(self, direction):
        if getattr(self, "_find_bar", None) is None:
            return
        needle = self._find_entry.get_text()
        if not needle:
            return
        buf = self.text_buffer
        text = buf.get_text(*buf.get_bounds(), True)
        hay = text.lower()
        ndl = needle.lower()
        if buf.get_has_selection():
            sa, sb = buf.get_selection_bounds()
            start_fwd = sb.get_offset()
            start_bwd = sa.get_offset()
        else:
            ins = buf.get_iter_at_mark(buf.get_insert()).get_offset()
            start_fwd = start_bwd = ins
        if direction > 0:
            idx = hay.find(ndl, start_fwd)
            if idx < 0:
                idx = hay.find(ndl, 0)
        else:
            idx = hay.rfind(ndl, 0, max(0, start_bwd))
            if idx < 0:
                idx = hay.rfind(ndl)
        if idx < 0:
            self._flash_status(self.t("find_none"))
            return
        a = buf.get_iter_at_offset(idx)
        b = buf.get_iter_at_offset(idx + len(needle))
        buf.select_range(b, a)
        self.text_view.scroll_to_iter(a, 0.1, False, 0, 0)

    def _replace_one(self, *_):
        if getattr(self, "_find_bar", None) is None:
            return
        buf = self.text_buffer
        needle = self._find_entry.get_text()
        if not needle:
            return
        if buf.get_has_selection():
            a, b = buf.get_selection_bounds()
            sel = buf.get_text(a, b, True)
            if sel.lower() == needle.lower():
                rep = self._replace_entry.get_text()
                buf.delete(a, b)
                buf.insert(a, rep)
        self._find_step(+1)

    def _replace_all(self, *_):
        if getattr(self, "_find_bar", None) is None:
            return
        needle = self._find_entry.get_text()
        if not needle:
            return
        rep = self._replace_entry.get_text()
        buf = self.text_buffer
        text = buf.get_text(*buf.get_bounds(), True)
        import re
        count = len(re.findall(re.escape(needle), text, flags=re.IGNORECASE))
        if count:
            new_text = re.sub(re.escape(needle), lambda m: rep,
                              text, flags=re.IGNORECASE)
            self._loading = True
            buf.set_text(new_text)
            self._loading = False
            if self.current is not None:
                self.current.text = new_text
            self._highlight_markdown()
            self._update_wordcount()
            self._mark_dirty()
        self._flash_status(self.t("replaced_n", n=count))

    def _flash_status(self, msg):
        self.wordcount_label.set_text(msg)
        GLib.timeout_add_seconds(2, lambda: (self._update_wordcount(), False)[1])

    # ---- dizionario ---------------------------------------------------------
    # EN: consulting a dictionary must not become a second program open
    # inside this one. So: no panel that stays open beside the notes, no
    # modal window to dismiss. A small sheet appears next to the word, the
    # cursor never leaves the text, and the first key you type puts it away.
    # IT: consultare un dizionario non deve diventare un secondo programma
    # aperto dentro questo. Quindi: nessun pannello che resta aperto accanto
    # alle note, nessuna finestra modale da chiudere. Un foglietto compare
    # accanto alla parola, il cursore non lascia mai il testo, e il primo
    # tasto che batti lo fa sparire.

    WORD_CHARS = "-'’\u2010"

    def _word_at_cursor(self):
        """EN: the selected text, or the word the cursor sits in.

        GTK's own word boundaries split on the apostrophe, which in Italian
        and French cuts "dell'anima" in two. So the line is scanned by hand,
        keeping apostrophes and hyphens inside the word, exactly as the
        spell checker already does with its elision lists.

        IT: il testo selezionato, o la parola in cui sta il cursore.

        I confini di parola di GTK spezzano sull'apostrofo, che in italiano
        e in francese taglia in due "dell'anima". Quindi la riga si esamina
        a mano, tenendo apostrofi e trattini dentro la parola, come già fa
        il correttore ortografico con le sue liste di elisione."""
        buf = self.text_buffer
        if buf.get_has_selection():
            a, b = buf.get_selection_bounds()
            sel = buf.get_text(a, b, False).strip()
            # EN/IT: a whole paragraph is not a headword: refuse politely.
            if sel and len(sel) <= 80 and "\n" not in sel:
                return sel
            if sel:
                return ""
        it = buf.get_iter_at_mark(buf.get_insert())
        start = it.copy()
        start.set_line_offset(0)
        end = it.copy()
        if not end.ends_line():
            end.forward_to_line_end()
        line = buf.get_text(start, end, False)
        pos = it.get_line_offset()
        if not line:
            return ""
        ok = lambda c: c.isalnum() or c in self.WORD_CHARS
        i = min(pos, len(line))
        # EN/IT: standing just after a word counts as being in it.
        if i >= len(line) or not ok(line[i]):
            if i > 0 and ok(line[i - 1]):
                i -= 1
            else:
                return ""
        a = i
        while a > 0 and ok(line[a - 1]):
            a -= 1
        b = i
        while b < len(line) and ok(line[b]):
            b += 1
        return line[a:b].strip("-'’\u2010")

    def _lookup_candidates(self, word):
        """EN: what to try, in order. An elided article is not part of the
        headword: "dell'anima" is filed under "anima". And a selection of
        several words is not a headword either — a dictionary may well have
        the phrase, but if it does not, the words themselves are worth
        trying, the longest first, because that is usually the one carrying
        the meaning.
        IT: cosa provare, in ordine. L'articolo eliso non fa parte del lemma:
        "dell'anima" sta sotto "anima". E una selezione di più parole non è
        un lemma: il dizionario può benissimo avere la locuzione, ma se non
        ce l'ha vale la pena provare le parole, la più lunga per prima, che
        di solito è quella che porta il significato."""
        out = [word]
        for sep in ("'", "’", "\u2010", "-"):
            if sep in word:
                head, _, tail = word.rpartition(sep)
                if tail:
                    out.append(tail)
                if head:
                    out.append(head)
                out.append(word.replace(sep, ""))
        parts = [p for p in word.split() if len(p) > 2]
        if len(parts) > 1:
            for part in sorted(parts, key=len, reverse=True):
                out.append(part)
                if "'" in part or "’" in part:
                    out.append(part.rpartition("'")[2] or
                               part.rpartition("’")[2])
        low = word.lower()
        if low != word:
            out.append(low)
        seen, uniq = set(), []
        for w in out:
            w = w.strip()
            if w and w not in seen:
                seen.add(w)
                uniq.append(w)
        return uniq

    # ---- la cartella dei dizionari ------------------------------------------
    def _is_in_library(self, path):
        """EN: is this file already inside the dictionary folder?
        IT: questo file sta già dentro la cartella dei dizionari?"""
        try:
            folder = os.path.abspath(self.dict_folder)
            path = os.path.abspath(path)
            return os.path.commonpath([folder, path]) == folder
        except (ValueError, OSError):
            return False

    def _library_destination(self, path):
        """EN: the name the copy will take. A dictionary already there, same
        name and same size, is reused instead of copied a second time; a
        different file with the same name gets a number, so nothing is ever
        silently overwritten.
        IT: il nome che prenderà la copia. Un dizionario già presente, stesso
        nome e stessa dimensione, viene riusato invece di ricopiarlo; un file
        diverso con lo stesso nome prende un numero, così non si sovrascrive
        mai niente senza dirlo."""
        base = os.path.basename(path)
        stem, ext = os.path.splitext(base)
        dest = os.path.join(self.dict_folder, base)
        try:
            source_size = os.path.getsize(path)
        except OSError:
            source_size = -1
        n = 2
        while os.path.exists(dest):
            try:
                if os.path.samefile(dest, path):
                    return dest, True
            except OSError:
                pass
            try:
                if os.path.getsize(dest) == source_size:
                    return dest, True       # e' gia' li': si riusa
            except OSError:
                pass
            dest = os.path.join(self.dict_folder, f"{stem}-{n}{ext}")
            n += 1
        return dest, False

    # EN/IT: an MDict dictionary is a family of files sharing one name.
    # / un dizionario MDict e' una famiglia di file con lo stesso nome.
    DICT_COMPANION_EXTS = (".mdd", ".MDD", ".png", ".PNG", ".jpg", ".jpeg",
                           ".css", ".CSS", ".js")
    # EN/IT: written inside a folder copied by RuscaWriter; it lists the
    # copied files, so removing the dictionary deletes exactly those and
    # nothing else. / scritto dentro una cartella copiata da RuscaWriter;
    # elenca i file copiati, cosi' togliendo il dizionario si cancellano
    # esattamente quelli e nient'altro.
    DICT_MANIFEST = ".ruscawriter-copy"

    def _dict_companions(self, mdx_path):
        """EN/IT: the files next to an .mdx that belong to it, as suffixes:
        ".mdd", ".1.mdd", ".png", ".css" ... / i file accanto a un .mdx che
        gli appartengono, come suffissi."""
        stem = os.path.splitext(mdx_path)[0]
        found = [ext for ext in self.DICT_COMPANION_EXTS
                 if os.path.isfile(stem + ext)]
        for n in range(1, 100):
            if not os.path.isfile(f"{stem}.{n}.mdd"):
                break
            found.append(f".{n}.mdd")
        return found

    def _copy_file_safely(self, src, dest):
        """EN/IT: copy through a temporary name; an identical file already
        there is kept. / copia passando da un nome provvisorio; un file
        identico gia' presente si tiene."""
        try:
            if os.path.getsize(dest) == os.path.getsize(src):
                return
        except OSError:
            pass
        tmp = dest + ".parziale"
        try:
            shutil.copyfile(src, tmp)
            os.replace(tmp, dest)
        except OSError:
            try:
                os.remove(tmp)
            except OSError:
                pass
            raise

    def _copy_into_library(self, path):
        """EN: copy an .mdx, and the files that belong with it (.mdd, icon,
        style sheet), into the dictionary folder; return the new .mdx path.
        Every file goes through a temporary name, so an interrupted copy never
        leaves a half dictionary that looks finished. Raises OSError.
        IT: copia un .mdx, e i file che gli appartengono (.mdd, icona, foglio
        di stile), nella cartella dei dizionari; restituisce il nuovo
        percorso del .mdx. Ogni file passa da un nome provvisorio, cosi' una
        copia interrotta non lascia mai un mezzo dizionario dall'aria
        completa. Solleva OSError."""
        os.makedirs(self.dict_folder, exist_ok=True)
        dest, already = self._library_destination(path)
        if not already:
            self._copy_file_safely(path, dest)
        src_stem = os.path.splitext(path)[0]
        dest_stem = os.path.splitext(dest)[0]
        for suffix in self._dict_companions(path):
            self._copy_file_safely(src_stem + suffix, dest_stem + suffix)
        return dest

    def _walk_folder(self, folder, max_depth=4, max_files=5000):
        """EN/IT: regular files under *folder*, relative paths. Symbolic links
        are never followed, so a link cannot pull in files from elsewhere.
        / i file regolari sotto *folder*, con percorso relativo. I link
        simbolici non si seguono mai, cosi' un link non puo' trascinare
        dentro file da altre parti."""
        out = []
        base_depth = folder.rstrip(os.sep).count(os.sep)
        for root, dirs, files in os.walk(folder, followlinks=False):
            if root.count(os.sep) - base_depth >= max_depth:
                dirs[:] = []
            dirs[:] = [d for d in dirs
                       if not os.path.islink(os.path.join(root, d))]
            for name in files:
                full = os.path.join(root, name)
                if os.path.islink(full) or not os.path.isfile(full):
                    continue
                if name == self.DICT_MANIFEST or name.endswith(".parziale"):
                    continue
                out.append(os.path.relpath(full, folder))
                if len(out) > max_files:
                    raise OSError(0, f"troppi file / too many files: {folder}")
        return sorted(out)

    def _copy_folder_into_library(self, folder):
        """EN/IT: copy a whole dictionary folder into the library, as a
        subfolder with the same name; return its path. / copia un'intera
        cartella di dizionario nella libreria, come sottocartella con lo
        stesso nome; ne restituisce il percorso."""
        folder = os.path.abspath(folder)
        os.makedirs(self.dict_folder, exist_ok=True)
        files = self._walk_folder(folder)
        name = os.path.basename(folder.rstrip(os.sep)) or "dizionario"
        dest = os.path.join(self.dict_folder, name)
        n = 2
        while os.path.exists(dest):
            same = all(
                os.path.isfile(os.path.join(dest, rel)) and
                os.path.getsize(os.path.join(dest, rel)) ==
                os.path.getsize(os.path.join(folder, rel)) for rel in files)
            if same:
                return dest             # e' gia' li': si riusa
            dest = os.path.join(self.dict_folder, f"{name}-{n}")
            n += 1
        tmp = dest + ".parziale"
        try:
            for rel in files:
                target = os.path.join(tmp, rel)
                os.makedirs(os.path.dirname(target), exist_ok=True)
                shutil.copyfile(os.path.join(folder, rel), target)
            with open(os.path.join(tmp, self.DICT_MANIFEST), "w",
                      encoding="utf-8") as f:
                f.write("\n".join(files) + "\n")
            os.replace(tmp, dest)
        except OSError:
            shutil.rmtree(tmp, ignore_errors=True)
            raise
        return dest

    def _find_mdx(self, folder):
        """EN/IT: the .mdx files inside a folder, in name order."""
        try:
            files = self._walk_folder(folder)
        except OSError:
            return []
        return [os.path.join(folder, rel) for rel in files
                if rel.lower().endswith(".mdx")]

    def _delete_dictionary_files(self, mdx_path):
        """EN/IT: delete a dictionary from the library: the .mdx and its
        companions, or, for a folder RuscaWriter copied, exactly the files
        its manifest lists. Never anything outside the library.
        / cancella un dizionario dalla libreria: il .mdx e i suoi file
        compagni oppure, per una cartella copiata da RuscaWriter,
        esattamente i file elencati nel suo manifesto. Mai niente fuori
        dalla libreria."""
        if not self._is_in_library(mdx_path):
            return
        library = os.path.abspath(self.dict_folder)
        parent = os.path.dirname(os.path.abspath(mdx_path))
        # EN/IT: the copied folder may hold the .mdx in a subfolder: look up
        # for the manifest, but never above the library. / la cartella
        # copiata puo' avere il .mdx in una sottocartella: si cerca il
        # manifesto risalendo, mai oltre la libreria.
        probe = parent
        while probe != library and os.path.commonpath([probe, library]) == library:
            if os.path.isfile(os.path.join(probe, self.DICT_MANIFEST)):
                parent = probe
                break
            probe = os.path.dirname(probe)
        manifest = os.path.join(parent, self.DICT_MANIFEST)
        others = [p for p in self._dict_set().paths
                  if os.path.commonpath([os.path.abspath(p), parent]) == parent]
        if os.path.isfile(manifest) and not others:
            with open(manifest, encoding="utf-8") as f:
                listed = [line.strip() for line in f if line.strip()]
            for rel in listed:
                full = os.path.abspath(os.path.join(parent, rel))
                if os.path.commonpath([full, parent]) != parent:
                    continue            # un manifesto alterato non esce mai
                try:
                    os.remove(full)
                except OSError:
                    pass
            try:
                os.remove(manifest)
            except OSError:
                pass
            for root, _dirs, _files in sorted(os.walk(parent, topdown=False),
                                              key=lambda t: -len(t[0])):
                try:
                    os.rmdir(root)       # solo se vuota
                except OSError:
                    pass
            return
        stem = os.path.splitext(mdx_path)[0]
        for suffix in [""] + self._dict_companions(mdx_path):
            target = mdx_path if not suffix else stem + suffix
            try:
                os.remove(target)
            except OSError:
                pass

    def _open_folder_dialog(self, title, on_path, initial=None):
        """EN: pick a folder. IT: sceglie una cartella."""
        dialog = Gtk.FileDialog()
        dialog.set_title(title)
        try:
            current = Gio.File.new_for_path(initial or self.dict_folder)
            dialog.set_initial_folder(current)
        except Exception:
            pass

        def done(d, result):
            try:
                answer = Gtk.FileDialog.select_folder_finish(d, result)
            except GLib.Error:
                return          # annullato
            if answer is not None and answer.get_path():
                on_path(answer.get_path())
        dialog.select_folder(self, None, done)

    def _dict_set(self):
        """EN: the open dictionaries, built on first use.
        IT: i dizionari aperti, costruiti al primo uso."""
        if self._dicts is None:
            self._dicts = pw_mdict.DictionarySet()
            for path in self.dict_paths:
                self._dicts.add_quiet(path)
        return self._dicts

    def on_lookup_word(self, *_):
        word = self._word_at_cursor()
        if not word:
            self._flash_status(self.t("dict_no_word"))
            return
        if not self.dict_paths:
            # EN/IT: nothing installed yet: say so once, and open the place
            # where it is fixed, instead of flashing a message every time.
            self.on_manage_dictionaries()
            return
        dicts = self._dict_set()
        if not any(d is not None for _, d in dicts.dictionaries()):
            # EN/IT: every installed dictionary failed to open. Saying "not
            # found" would blame the word for the file's problem.
            self.on_manage_dictionaries()
            return
        if dicts.pending():
            # EN/IT: an index still to build would freeze the writing for
            # seconds. It is done in the background, and the word is looked
            # up when it is ready.
            self._flash_status(self.t("dict_indexing"))
            self._dict_index_async(then=lambda: self._dict_do_lookup(word))
            return
        self._dict_do_lookup(word)
        if dicts.needs_work():
            # EN/IT: the words are ready, the pictures of the .mdd are not
            # yet: they are indexed quietly in the background, and "Show all"
            # finds them from then on. / le parole sono pronte, le immagini
            # del .mdd non ancora: si indicizzano in silenzio in background, e
            # da quel momento "Mostra tutto" le trova.
            self._dict_index_async()

    def _writing_languages(self):
        """EN: the languages whose grammar rules to try first. The spelling
        language is the better guess — it is set per document and follows
        what is actually being written — with the interface language behind
        it. Rules for other languages still get their turn afterwards, and
        cost nothing when they invent a word no dictionary has.
        IT: le lingue le cui regole grammaticali vanno provate per prime.
        Quella dell'ortografia è l'ipotesi migliore — si imposta per
        documento e segue quello che si sta scrivendo davvero — con dietro
        quella dell'interfaccia. Le regole delle altre lingue vengono
        comunque dopo, e non costano niente quando inventano una parola che
        nessun dizionario ha."""
        out = []
        for code in (getattr(self, "spell_lang", ""), getattr(self, "lang", "")):
            base = str(code or "").replace("-", "_").split("_")[0].lower()
            if base and base not in out:
                out.append(base)
        return out

    def _dict_do_lookup(self, word):
        dicts = self._dict_set()
        candidates = self._lookup_candidates(word)
        for candidate in candidates:
            try:
                found = dicts.first(candidate)
            except MdxError as exc:
                self._flash_status(str(exc))
                return
            if found is not None:
                source, entry = found
                self._show_dict_popover(candidate, source, entry)
                return
        # EN: nothing matched letter for letter. First undo gender and number
        # by rule — "case" is "casa", and about that there is nothing to
        # guess. Only when the rules find nothing does similarity get a turn:
        # a rule gives one answer, a resemblance gives a best guess, and the
        # one that is certain should be asked first.
        # IT: niente ha corrisposto lettera per lettera. Prima si disfano
        # genere e numero per regola — "case" è "casa", e su questo non c'è
        # niente da indovinare. Solo quando le regole non trovano nulla tocca
        # alla somiglianza: una regola dà una risposta, un'assonanza dà
        # un'ipotesi, e va chiesto prima a chi è sicuro.
        prefer = self._writing_languages()
        for candidate in candidates:
            try:
                byrule = dicts.first_form(candidate, prefer)
            except MdxError as exc:
                self._flash_status(str(exc))
                return
            if byrule is not None:
                source, headword, entry = byrule
                others = [w for _d, w, _s in dicts.near(candidate)
                          if w.casefold() != headword.casefold()]
                self._show_dict_popover(headword, source, entry,
                                        asked=candidate, others=others[:3])
                return
        # EN/IT: no rule fitted. The closest headword is shown instead —
        # labelled as such, never passed off as the word that was asked for.
        for candidate in candidates:
            try:
                near = dicts.first_near(candidate)
            except MdxError as exc:
                self._flash_status(str(exc))
                return
            if near is not None:
                source, headword, entry, _score = near
                others = [w for _d, w, _s in dicts.near(candidate)
                          if w != headword]
                self._show_dict_popover(headword, source, entry,
                                        asked=candidate, others=others[:3])
                return
        self._flash_status(self.t("dict_not_found", word=word))

    def _dict_show_headword(self, headword, asked):
        """EN: switch the sheet to one of the other close headwords, without
        touching the text or the cursor.
        IT: porta il foglietto su un altro dei lemmi vicini, senza toccare il
        testo né il cursore."""
        dicts = self._dict_set()
        found = dicts.first(headword)
        if found is None:
            return
        source, entry = found
        others = [w for _d, w, _s in dicts.near(asked) if w != headword]
        self._show_dict_popover(headword, source, entry,
                                asked=asked, others=others[:3])

    def _dict_index_async(self, then=None, on_progress=None):
        """EN: build the missing indexes in a worker thread. The interface
        stays alive: GTK is only touched from the main loop, via idle_add.
        IT: costruisce gli indici mancanti in un thread di lavoro.
        L'interfaccia resta viva: GTK si tocca solo dal ciclo principale,
        tramite idle_add."""
        if self._dict_thread is not None and self._dict_thread.is_alive():
            return
        dicts = self._dict_set()

        def report(d, fraction):
            if on_progress is not None:
                GLib.idle_add(on_progress, d, fraction)

        def work():
            # EN/IT: any exception, not only MdxError: a thread that dies in
            # silence leaves "indexing..." on screen forever, which is exactly
            # how a dictionary looks "accepted but not working".
            # / qualunque eccezione, non solo MdxError: un thread che muore
            # in silenzio lascia "indicizzazione..." per sempre, ed e'
            # proprio cosi' che un dizionario sembra "accettato ma non
            # funzionante".
            try:
                error = dicts.build_pending(report)
            except Exception as exc:          # noqa: BLE001
                error = f"{type(exc).__name__}: {exc}"
            GLib.idle_add(done, error)

        def done(error):
            self._dict_thread = None
            usable = any(d is not None and d.indexed
                         for _p, d in dicts.dictionaries())
            if error and not usable:
                # EN/IT: nothing can answer: say why, in a window that stays.
                # (il messaggio di mdict e' gia' bilingue IT/EN)
                self._error(error)
                return False
            if error:
                self._flash_status(error)
            if then is not None:
                then()
            return False

        self._dict_thread = threading.Thread(target=work, daemon=True)
        self._dict_thread.start()

    def _cursor_rectangle(self, word):
        """EN: where to point the sheet: the start of the word, in widget
        coordinates.
        IT: dove puntare il foglietto: l'inizio della parola, in coordinate
        del widget."""
        buf = self.text_buffer
        it = buf.get_iter_at_mark(buf.get_insert())
        if buf.get_has_selection():
            it = buf.get_selection_bounds()[0]
        else:
            back = max(0, it.get_line_offset() - len(word))
            it = it.copy()
            it.set_line_offset(back)
        loc = self.text_view.get_iter_location(it)
        x, y = self.text_view.buffer_to_window_coords(
            Gtk.TextWindowType.WIDGET, loc.x, loc.y)
        rect = Gdk.Rectangle()
        rect.x, rect.y = x, y
        rect.width, rect.height = max(1, loc.width), max(1, loc.height)
        return rect

    # EN/IT: the sheet never grows past this: a long entry scrolls inside it
    # instead of pushing the popover off the screen (which made "Show all"
    # look dead). / il foglietto non cresce oltre questo: una voce lunga
    # scorre al suo interno invece di spingere il popover fuori dallo schermo
    # (ed e' per questo che "Mostra tutto" sembrava non fare niente).
    DICT_SHEET_WIDTH = 440
    DICT_SHEET_MAX_HEIGHT = 380
    DICT_MAX_IMAGES = 6

    def _dict_texture(self, data):
        """EN/IT: a picture from an .mdd as a texture, or None. Only image
        bytes are decoded: anything else (sound, css) is skipped. / un'immagine
        di un .mdd come texture, o None. Si decodificano solo byte di
        immagini: il resto (suoni, css) si salta."""
        if not data or len(data) > 8 * 1024 * 1024:
            return None
        if not (data[:8] == b"\x89PNG\r\n\x1a\n" or data[:3] == b"\xff\xd8\xff"
                or data[:6] in (b"GIF87a", b"GIF89a")
                or (data[:4] == b"RIFF" and data[8:12] == b"WEBP")):
            return None
        try:
            return Gdk.Texture.new_from_bytes(GLib.Bytes.new(data))
        except Exception:
            pass
        if GdkPixbuf is None:
            return None
        try:
            loader = GdkPixbuf.PixbufLoader()
            loader.write(data)
            loader.close()
            pix = loader.get_pixbuf()
            return Gdk.Texture.new_for_pixbuf(pix) if pix is not None else None
        except Exception:
            return None

    def _dict_icon(self, source, size=16):
        """EN/IT: the dictionary's own icon (name.png beside the .mdx) / l'icona
        del dizionario (nome.png accanto al .mdx)."""
        path = getattr(source, "icon_path", None)
        if not path:
            return None
        try:
            if os.path.getsize(path) > 2 * 1024 * 1024:
                return None
            tex = Gdk.Texture.new_from_filename(path)
        except Exception:
            return None
        img = Gtk.Image.new_from_paintable(tex)
        img.set_pixel_size(size)
        return img

    def _show_dict_popover(self, word, source, entry, asked=None, others=()):
        self._close_dict_popover()
        markup = pw_mdict.to_pango_markup(entry)
        short, cut = pw_mdict.shorten(markup)
        images = pw_mdict.entry_images(entry)

        pop = Gtk.Popover()
        pop.add_css_class("rusca-dictpop")
        # EN: the sheet does not take the focus. You keep typing with it
        # open, which is the whole point of it not being a dialog.
        # IT: il foglietto non prende il fuoco. Si continua a battere con
        # quello aperto, che e' esattamente il motivo per cui non e' un
        # dialogo.
        pop.set_autohide(False)
        pop.set_has_arrow(True)
        pop.set_position(Gtk.PositionType.BOTTOM)
        pop.set_parent(self.text_view)
        pop.set_pointing_to(self._cursor_rectangle(asked or word))

        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        box.set_margin_top(10); box.set_margin_bottom(10)
        box.set_margin_start(12); box.set_margin_end(12)
        box.set_size_request(self.DICT_SHEET_WIDTH, -1)

        # EN/IT: headword and a close button: one click puts the sheet away.
        # / lemma e pulsante di chiusura: un clic mette via il foglietto.
        top = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        head = Gtk.Label(label=word, xalign=0)
        head.add_css_class("rusca-dictpop-word")
        head.set_hexpand(True)
        top.append(head)
        close = Gtk.Button(label="✕")
        close.add_css_class("flat")
        close.set_valign(Gtk.Align.START)
        close.set_tooltip_text(self._t_or("dict_close", "Close"))
        close.connect("clicked", lambda *_a: (self._close_dict_popover(),
                                              self._focus_editor()))
        top.append(close)
        box.append(top)

        if asked is not None and asked.casefold() != word.casefold():
            # EN/IT: say plainly that this is not the word that was asked
            # for. A dictionary that quietly answers something else is worse
            # than one that answers nothing.
            note = Gtk.Label(label=self.t("dict_near", word=asked), xalign=0)
            note.add_css_class("rusca-dictpop-source")
            note.set_wrap(True)
            box.append(note)

        body = Gtk.Label(xalign=0)
        body.add_css_class("rusca-dictpop-body")
        body.set_wrap(True)
        body.set_wrap_mode(Pango.WrapMode.WORD_CHAR)
        body.set_max_width_chars(50)
        self._set_markup_safely(body, short)

        inner = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        inner.append(body)
        scroller = Gtk.ScrolledWindow()
        scroller.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        scroller.set_propagate_natural_height(True)
        scroller.set_max_content_height(self.DICT_SHEET_MAX_HEIGHT)
        scroller.set_child(inner)
        box.append(scroller)

        if others:
            row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
            label = Gtk.Label(label=self.t("dict_also"))
            label.add_css_class("rusca-dictpop-source")
            row.append(label)
            for other in others:
                btn = Gtk.Button(label=other)
                btn.add_css_class("flat")
                btn.connect("clicked",
                            lambda _b, w=other: self._dict_show_headword(
                                w, asked or word))
                row.append(btn)
            box.append(row)

        foot = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        icon = self._dict_icon(source)
        if icon is not None:
            foot.append(icon)
        src = Gtk.Label(label=source.title, xalign=0)
        src.add_css_class("rusca-dictpop-source")
        src.set_hexpand(True)
        src.set_ellipsize(Pango.EllipsizeMode.END)
        foot.append(src)

        def add_images():
            # EN/IT: the pictures of the entry, from the dictionary's .mdd.
            # Never from the network: http(s) sources are skipped.
            # / le immagini della voce, dal .mdd del dizionario. Mai dalla
            # rete: le sorgenti http(s) si saltano.
            shown = 0
            for name in images:
                if shown >= self.DICT_MAX_IMAGES:
                    break
                try:
                    tex = self._dict_texture(source.resource(name))
                except Exception:
                    tex = None
                if tex is None:
                    continue
                pic = Gtk.Picture.new_for_paintable(tex)
                pic.set_can_shrink(True)
                pic.set_content_fit(Gtk.ContentFit.SCALE_DOWN)
                pic.set_halign(Gtk.Align.START)
                pic.set_size_request(-1, min(220, max(16, tex.get_height())))
                inner.append(pic)
                shown += 1

        if cut or images:
            more = Gtk.Button(label=self.t("dict_more"))
            more.add_css_class("flat")

            def expand(*_a):
                # EN/IT: growing the sheet makes GTK lay out the text view
                # again, which nudges its scroll position: for a moment that
                # must not count as "you scrolled, close the sheet". That
                # nudge used to close the sheet at the very click.
                # / far crescere il foglietto fa ridisporre il testo, che
                # sposta di poco lo scorrimento: per un attimo non deve valere
                # come "hai scorso, chiudi". Era quel ritocco a chiudere il
                # foglietto proprio al clic.
                self._dict_grace_until = GLib.get_monotonic_time() + 600_000
                self._set_markup_safely(body, markup)
                add_images()
                foot.remove(more)
                self._focus_editor()
            more.connect("clicked", expand)
            foot.append(more)
        box.append(foot)
        pop.set_child(box)

        # EN/IT: Escape closes it, like the find bar. The controller sits on
        # the text view because the sheet has no focus of its own.
        keys = Gtk.EventControllerKey()

        def on_key(_c, keyval, _code, _state):
            if keyval == Gdk.KEY_Escape:
                self._close_dict_popover()
                return True
            return False
        keys.connect("key-pressed", on_key)
        self.text_view.add_controller(keys)
        self._dict_keys = keys

        # EN/IT: a real scroll closes the sheet (it would point at the wrong
        # line); a layout nudge of a pixel or two does not.
        # / uno scorrimento vero chiude il foglietto (punterebbe alla riga
        # sbagliata); un ritocco di layout di un pixel o due no.
        vadj = self._sw_center.get_vadjustment()
        self._dict_scroll_from = vadj.get_value()
        self._dict_grace_until = GLib.get_monotonic_time() + 400_000

        def on_scroll(adj):
            if GLib.get_monotonic_time() < self._dict_grace_until:
                self._dict_scroll_from = adj.get_value()
                return
            if abs(adj.get_value() - self._dict_scroll_from) > 4:
                self._close_dict_popover()
        self._dict_scroll_id = vadj.connect("value-changed", on_scroll)
        self._dict_vadj = vadj

        self._dict_popover = pop
        pop.popup()
        # EN/IT: the cursor never left the text, but make sure of it.
        self._focus_editor()

    # ---- il dizionario con il mouse -----------------------------------------
    def _install_dict_mouse(self):
        """EN — the mouse can do what Ctrl+D does: Ctrl+click on a word looks
        it up, the right-click menu has the same entry, and a click in the
        text puts the sheet away, as does its ✕.
        IT — il mouse puo' fare quello che fa Ctrl+D: Ctrl+clic su una parola
        la cerca, il menu del tasto destro ha la stessa voce, e un clic nel
        testo mette via il foglietto, come la sua ✕."""
        click = Gtk.GestureClick()
        click.set_button(1)
        click.set_propagation_phase(Gtk.PropagationPhase.CAPTURE)
        click.connect("pressed", self._on_text_click)
        self.text_view.add_controller(click)
        self._apply_extra_menu()

    def _on_text_click(self, gesture, n_press, x, y):
        pop = self._dict_popover
        if pop is not None:
            # EN/IT: a click inside the sheet belongs to the sheet; its
            # events arrive on its own surface. / un clic dentro il foglietto
            # e' del foglietto: i suoi eventi arrivano sulla sua superficie.
            try:
                ev = gesture.get_current_event()
                if ev is not None and ev.get_surface() == pop.get_surface():
                    return
            except Exception:
                pass
            self._close_dict_popover()
        state = gesture.get_current_event_state()
        if n_press != 1 or not (state & Gdk.ModifierType.CONTROL_MASK):
            return
        bx, by = self.text_view.window_to_buffer_coords(
            Gtk.TextWindowType.WIDGET, int(x), int(y))
        found = self.text_view.get_iter_at_location(bx, by)
        it = found[1] if isinstance(found, tuple) else found
        if it is None:
            return
        gesture.set_state(Gtk.EventSequenceState.CLAIMED)
        self.text_buffer.place_cursor(it)
        GLib.idle_add(lambda: (self.on_lookup_word(), False)[1])

    def _apply_extra_menu(self, spell_menu=None):
        """EN/IT: the right-click menu of the text: "Look up" first, then the
        spelling suggestions when the spell checker is on. / il menu del
        tasto destro: prima "Cerca nel dizionario", poi i suggerimenti
        ortografici se il correttore e' attivo."""
        if spell_menu is not None:
            self._spell_menu_model = spell_menu
        spell_menu = getattr(self, "_spell_menu_model", None)
        menu = Gio.Menu()
        section = Gio.Menu()
        section.append(self.t("mi_lookup"), "win.lookup")
        menu.append_section(None, section)
        if spell_menu is not None:
            menu.append_section(None, spell_menu)
        try:
            self.text_view.set_extra_menu(menu)
        except Exception:
            pass

    def _set_markup_safely(self, label, markup):
        """EN: a dictionary written badly must not break the label: if the
        markup is refused, show the same text without formatting.
        IT: un dizionario scritto male non deve rompere l'etichetta: se il
        markup viene rifiutato, si mostra lo stesso testo senza formato."""
        try:
            label.set_markup(markup)
        except Exception:
            label.set_text(pw_mdict.to_plain_text(markup))

    def _close_dict_popover(self, *_):
        if getattr(self, "_dict_popover", None) is None:
            return
        pop = self._dict_popover
        self._dict_popover = None
        keys = getattr(self, "_dict_keys", None)
        if keys is not None:
            try:
                self.text_view.remove_controller(keys)
            except Exception:
                pass
            self._dict_keys = None
        vadj = getattr(self, "_dict_vadj", None)
        if vadj is not None and getattr(self, "_dict_scroll_id", 0):
            try:
                vadj.disconnect(self._dict_scroll_id)
            except Exception:
                pass
            self._dict_scroll_id = 0
            self._dict_vadj = None
        try:
            pop.popdown()
            pop.unparent()
        except Exception:
            pass

    # ---- gestione dei dizionari ---------------------------------------------
    def on_manage_dictionaries(self, *_):
        """EN: where .mdx files are added, ordered and removed. Opened once
        and then forgotten: the lookup itself never asks anything.
        IT: dove i file .mdx si aggiungono, si ordinano e si tolgono. Si apre
        una volta e poi si dimentica: la consultazione non chiede mai
        niente."""
        dialog, box = self._dialog_shell(self.t("dict_title"), size=(560, 380))

        intro = Gtk.Label(label=self.t("dict_intro"), xalign=0)
        intro.add_css_class("rusca-dialog-text")
        intro.set_wrap(True)
        intro.set_max_width_chars(56)
        box.append(intro)

        # Riga della cartella: dove finiscono i file quando li aggiungi. Sta
        # in alto perche' e' la decisione che riguarda tutti i dizionari, non
        # uno solo, e si prende una volta.
        folder_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        folder_lbl = Gtk.Label(xalign=0)
        folder_lbl.add_css_class("rusca-dictpop-source")
        folder_lbl.set_hexpand(True)
        folder_lbl.set_ellipsize(Pango.EllipsizeMode.MIDDLE)
        b_folder = Gtk.Button(label=self.t("dict_folder_change"))
        folder_row.append(folder_lbl)
        folder_row.append(b_folder)
        box.append(folder_row)

        copy_check = Gtk.CheckButton(label=self.t("dict_copy_here"))
        copy_check.set_active(self.dict_copy)
        copy_check.add_css_class("rusca-dialog-text")
        box.append(copy_check)

        def show_folder():
            folder_lbl.set_text(
                self.t("dict_folder_is", folder=self.dict_folder))
            folder_lbl.set_tooltip_text(self.dict_folder)
            copy_check.set_active(self.dict_copy)

        listbox = Gtk.ListBox()
        listbox.set_selection_mode(Gtk.SelectionMode.SINGLE)
        sw = Gtk.ScrolledWindow()
        sw.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        sw.set_vexpand(True)
        sw.set_child(listbox)
        box.append(sw)

        progress = Gtk.ProgressBar()
        progress.set_show_text(True)
        progress.set_visible(False)
        box.append(progress)

        def selected_path():
            row = listbox.get_selected_row()
            return getattr(row, "_path", None) if row is not None else None

        def refresh():
            child = listbox.get_first_child()
            while child is not None:
                nxt = child.get_next_sibling()
                listbox.remove(child)
                child = nxt
            dicts = self._dict_set()
            if not dicts.paths:
                empty = Gtk.Label(label=self.t("dict_none"))
                empty.add_css_class("rusca-dialog-text")
                empty.set_wrap(True)
                empty.set_margin_top(16); empty.set_margin_bottom(16)
                row = Gtk.ListBoxRow()
                row.set_selectable(False)
                row.set_child(empty)
                listbox.append(row)
                return
            for path, d in dicts.dictionaries():
                row = Gtk.ListBoxRow()
                row._path = path
                line = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
                line.set_margin_top(6); line.set_margin_bottom(6)
                line.set_margin_start(8); line.set_margin_end(8)
                name = Gtk.Label(xalign=0)
                name.add_css_class("rusca-dialog-text")
                title = d.title if d is not None else os.path.basename(path)
                name.set_markup(f"<b>{GLib.markup_escape_text(title)}</b>")
                name.set_hexpand(True)
                head_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL,
                                   spacing=8)
                icon = self._dict_icon(d, 20) if d is not None else None
                if icon is not None:
                    head_row.append(icon)
                head_row.append(name)
                if d is not None and d.companions():
                    extra = Gtk.Label(label=" + ".join(
                        os.path.basename(c) for c in d.companions()))
                    extra.add_css_class("rusca-dictpop-source")
                    extra.set_ellipsize(Pango.EllipsizeMode.MIDDLE)
                    head_row.append(extra)
                line.append(head_row)
                err = self._dicts.errors.get(os.path.abspath(path), "")
                if d is None or err:
                    note = "⚠ " + err
                elif not d.indexed:
                    note = self.t("dict_state_new")
                else:
                    note = self.t("dict_state_ready", n=d.entry_count)
                info = Gtk.Label(label=f"{note}  ·  {path}", xalign=0)
                info.add_css_class("rusca-dictpop-source")
                info.set_ellipsize(Pango.EllipsizeMode.MIDDLE)
                line.append(info)
                row.set_child(line)
                listbox.append(row)

        def save_order():
            self.dict_paths = list(self._dict_set().paths)
            self.settings["dictionaries"] = self.dict_paths
            self.settings["dict_folder"] = self.dict_folder
            self.settings["dict_copy"] = self.dict_copy
            save_settings(self.settings)

        def index_all():
            progress.set_visible(True)
            progress.set_fraction(0.0)

            def on_progress(d, fraction):
                progress.set_fraction(fraction)
                progress.set_text(self.t("dict_indexing_one", name=d.title))
                return False

            def finished():
                progress.set_visible(False)
                refresh()
            self._dict_index_async(then=finished, on_progress=on_progress)

        def use(paths):
            """Aggiunge all'elenco uno o piu' file gia' al loro posto
            definitivo, poi indicizza tutto in una volta sola."""
            if isinstance(paths, str):
                paths = [paths]
            errors = []
            for path in paths:
                try:
                    self._dict_set().add(path)
                except MdxError as exc:
                    errors.append(f"{os.path.basename(path)}: {exc}")
            save_order()
            refresh()
            index_all()
            if errors:
                self._error("\n".join(errors))

        def run_copy(label, job, then):
            """La copia puo' durare (un .mdd arriva a gigabyte): va in un
            thread, con la barra che pulsa."""
            progress.set_visible(True)
            progress.set_text(self.t("dict_copying", name=label))
            progress.pulse()
            pulse = GLib.timeout_add(120, lambda: (progress.pulse(), True)[1])

            def work():
                try:
                    result, error = job(), None
                except OSError as exc:
                    result, error = None, exc
                GLib.idle_add(done, result, error)

            def done(result, error):
                GLib.source_remove(pulse)
                progress.set_visible(False)
                progress.set_text(None)
                if error is not None:
                    # Non si aggiunge l'originale di nascosto: chi ha chiesto
                    # la copia deve sapere che non c'e' stata.
                    self._error(self.t("dict_copy_failed",
                                       folder=self.dict_folder,
                                       error=error.strerror or str(error)))
                else:
                    then(result)
                return False
            threading.Thread(target=work, daemon=True).start()

        def do_add_folder(folder):
            # EN/IT: a whole dictionary folder: every .mdx inside it, with
            # its .mdd, icon and style sheets. / un'intera cartella di
            # dizionario: ogni .mdx che contiene, con .mdd, icona e stili.
            if not self._find_mdx(folder):
                self._error(self._t_or(
                    "dict_folder_empty",
                    "No .mdx file in this folder: {folder}", folder=folder))
                return
            if not self.dict_copy or self._is_in_library(folder):
                use(self._find_mdx(folder))
                return
            run_copy(os.path.basename(folder.rstrip(os.sep)),
                     lambda: self._copy_folder_into_library(folder),
                     lambda dest: use(self._find_mdx(dest)))

        def do_add(path):
            # EN/IT: an MDict dictionary is often a family of files (.mdx,
            # .mdd, .css, .png). Whichever one was picked, the words are in
            # the .mdx with the same name. / un dizionario MDict e' spesso una
            # famiglia di file (.mdx, .mdd, .css, .png). Qualunque si sia
            # scelto, le parole stanno nel .mdx con lo stesso nome.
            stem, ext = os.path.splitext(path)
            if ext.lower() != ".mdx":
                for cand in (stem + ".mdx", stem + ".MDX"):
                    if os.path.isfile(cand):
                        path = cand
                        break
            if not self.dict_copy or self._is_in_library(path):
                use(path)
                return
            run_copy(os.path.basename(path),
                     lambda: self._copy_into_library(path), use)

        def on_add(*_a):
            self._open_file_dialog(
                self.t("dict_add"),
                ["*.mdx", "*.MDX", "*.mdd", "*.MDD", "*.png", "*.PNG"],
                self.t("dict_filter"), do_add)

        def on_add_folder(*_a):
            self._open_folder_dialog(
                self._t_or("dict_add_folder", "Add folder…"), do_add_folder,
                initial=os.path.expanduser("~"))

        def on_change_folder(*_a):
            def chosen(folder):
                self.dict_folder = folder
                self.dict_copy = True
                # I dizionari gia' aggiunti restano dove sono: spostarli
                # butterebbe via i loro indici e non e' quello che si chiede
                # cambiando una cartella. La nuova vale da adesso in poi.
                save_order()
                show_folder()
            self._open_folder_dialog(self.t("dict_folder_choose"), chosen)

        def on_copy_toggled(check):
            self.dict_copy = check.get_active()
            save_order()

        def on_remove(*_a):
            path = selected_path()
            if path is None:
                return

            def forget(delete_file):
                self._dict_set().remove(path)
                if delete_file:
                    # EN/IT: the .mdx with its .mdd, icon and styles; for a
                    # copied folder, the whole copy. / il .mdx con .mdd, icona
                    # e stili; per una cartella copiata, l'intera copia.
                    self._delete_dictionary_files(path)
                save_order()
                refresh()

            if self._is_in_library(path) and os.path.exists(path):
                # Il file sta nella cartella dei dizionari, quindi con ogni
                # probabilita' ce l'ha messo questo programma: chiedere e'
                # meglio sia che lasciarlo li' orfano sia che cancellarlo
                # senza dirlo.
                self._confirm(
                    self.t("dict_remove"),
                    self.t("dict_remove_ask", name=os.path.basename(path)),
                    [self.t("cancel"), self.t("dict_remove_list"),
                     self.t("dict_remove_file")],
                    1, 0,
                    lambda idx: forget(idx == 2) if idx else None)
            else:
                forget(False)

        def on_move(delta):
            path = selected_path()
            if path is None:
                return
            self._dict_set().move(path, delta)
            save_order()
            refresh()

        bar = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        b_add = Gtk.Button(label=self.t("dict_add"))
        b_add_folder = Gtk.Button(
            label=self._t_or("dict_add_folder", "Add folder…"))
        b_add_folder.set_tooltip_text(self._t_or(
            "dict_add_folder_tip",
            "A dictionary folder: .mdx, .mdd, icon and style sheets"))
        b_add_folder.connect("clicked", on_add_folder)
        b_del = Gtk.Button(label=self.t("dict_remove"))
        b_up = Gtk.Button(label="↑")
        b_down = Gtk.Button(label="↓")
        b_add.connect("clicked", on_add)
        b_del.connect("clicked", on_remove)
        b_folder.connect("clicked", on_change_folder)
        copy_check.connect("toggled", on_copy_toggled)
        b_up.connect("clicked", lambda *_a: on_move(-1))
        b_down.connect("clicked", lambda *_a: on_move(+1))
        for w in (b_add, b_add_folder, b_del, b_up, b_down):
            bar.append(w)
        spacer = Gtk.Box()
        spacer.set_hexpand(True)
        bar.append(spacer)
        b_close = Gtk.Button(label=self.t("ok"))
        b_close.add_css_class("suggested-action")
        b_close.connect("clicked", lambda *_a: dialog.destroy())
        bar.append(b_close)
        box.append(bar)

        refresh()
        show_folder()
        if self._dict_set().pending():
            index_all()
        self._dialog_present(dialog, box, b_close)

    # ---- anteprima ----------------------------------------------------------
    def on_toggle_preview(self, *_):
        self._toggle_preview(whole=False)

    def on_toggle_preview_whole(self, *_):
        self._toggle_preview(whole=True)

    # ---- carattere ---------------------------------------------------------
    def _font_choices(self):
        """Elenco dei caratteri offerti: prima i due incorporati, poi le
        famiglie TrueType installate. Ogni voce e' (etichetta, famiglia)."""
        incorporato = self._t_or("font_builtin", "incorporato")
        voci = [(f"{_TW_FAMILY} ({incorporato})", _TW_FAMILY),
                (f"{SERIF_FAMILY} ({incorporato})", SERIF_FAMILY)]
        interne = {_TW_FAMILY, SERIF_FAMILY}
        voci += [(fam, fam) for fam in sorted(system_font_families())
                 if fam not in interne]
        return voci

    def on_choose_font(self, *_):
        """Sceglie DUE caratteri, separati: quello con cui si scrive e legge a
        schermo, e quello con cui escono i documenti esportati.

        Sono mestieri diversi. A schermo si sta ore su un testo in lavorazione,
        e c'e' chi ci vuole una macchina da scrivere; il PDF e' il libro, e li'
        di solito si vuole un serif da lettura. Percio' due tendine, non una,
        con i predefiniti storici gia' selezionati."""
        voci = self._font_choices()
        etichette = [v[0] for v in voci]

        def indice_di(famiglia, ripiego):
            for i, (_lbl, fam) in enumerate(voci):
                if fam == famiglia:
                    return i
            for i, (_lbl, fam) in enumerate(voci):
                if fam == ripiego:
                    return i
            return 0

        dialog, box = self._dialog_shell(
            self._t_or("dlg_font_title", "Caratteri"), size=(460, -1))

        def riga(chiave, ripiego_testo, selezione):
            lbl = Gtk.Label(label=self._t_or(chiave, ripiego_testo), xalign=0)
            lbl.add_css_class("rusca-dialog-text")
            box.append(lbl)
            tendina = Gtk.DropDown.new_from_strings(etichette)
            tendina.set_selected(selezione)
            box.append(tendina)
            return tendina

        t_schermo = riga("font_screen_label",
                         "Scrittura e lettura a schermo",
                         indice_di(getattr(self, "font_family", _TW_FAMILY),
                                   _TW_FAMILY))
        t_export = riga("font_export_label",
                        "Documenti esportati (PDF)",
                        indice_di(getattr(self, "doc_font", "") or SERIF_FAMILY,
                                  SERIF_FAMILY))

        nota = Gtk.Label(
            label=self._t_or("font_ttf_note",
                             "Sono elencate le famiglie TrueType: sono le sole "
                             "che si possono incorporare nel PDF."),
            xalign=0)
        nota.set_wrap(True)
        nota.add_css_class("rusca-dialog-text")
        box.append(nota)

        def conferma(*_a):
            self.font_family = voci[t_schermo.get_selected()][1]
            self.doc_font = voci[t_export.get_selected()][1]
            self.settings["font_family"] = self.font_family
            self.settings["doc_font"] = self.doc_font
            save_settings(self.settings)
            self._apply_editor_font()
            dialog.destroy()
            self._info(self.t("font_chosen", s=self.font_family,
                              e=self.doc_font))

        ok = self._ok_cancel_row(box, conferma,
                                 lambda *_a: dialog.destroy())
        self._dialog_present(dialog, box, ok)

    # ---- interruzioni di riga ----------------------------------------------
    def on_toggle_show_breaks(self, *_):
        """Accende o spegne l'evidenziazione dei paragrafi spezzati. Non tocca
        il testo: serve a vedere se e dove c'e' qualcosa da ricucire."""
        self.show_breaks = not self.show_breaks
        self.settings["show_breaks"] = self.show_breaks
        save_settings(self.settings)
        self._sync_switch("show_breaks", self.show_breaks)
        self._highlight_markdown()
        if self.show_breaks:
            n = len(wrapped_runs(self._chapter_text()))
            self._info(self.t("breaks_found", n=n) if n
                       else self.t("breaks_none"))

    def _chapter_text(self):
        """Testo del capitolo aperto, così com'e' nell'area di scrittura."""
        s, e = self.text_buffer.get_bounds()
        return self.text_buffer.get_text(s, e, True)

    def on_reflow_paragraphs(self, *_):
        """Ricuce a mano i paragrafi spezzati del capitolo aperto.

        E' la versione manuale di cio' che l'importazione fa da sola: serve
        quando il testo e' arrivato per altre strade — incollato, o importato
        con una versione precedente."""
        if self.current is None:
            return
        text = self._chapter_text()
        runs = wrapped_runs(text)
        if not runs:
            self._info(self.t("breaks_none"))
            return
        righe = sum(last - first for first, last in runs)
        new_text = unwrap_hard_breaks(text)
        if new_text == text:
            self._info(self.t("breaks_none"))
            return
        self.text_buffer.set_text(new_text)
        self._commit_current()
        self._highlight_markdown()
        self._mark_dirty()
        self._update_wordcount()
        self._info(self.t("reflow_done", n=len(runs), lines=righe))

    def _toggle_preview(self, whole):
        if self._preview_mode and bool(getattr(self, "_preview_whole", False)) == whole:
            self._preview_mode = False
            self.center_stack.set_visible_child_name("editor")
        else:
            self._preview_mode = True
            self._preview_whole = whole
            self._commit_current()
            self._render_preview()
            self.center_stack.set_visible_child_name("preview")
        self._sync_preview_button()

    def _on_preview_button(self, button):
        if getattr(self, "_syncing_preview", False):
            return
        if button.get_active() != self._preview_mode:
            self._toggle_preview(whole=False)

    def _sync_preview_button(self):
        """EN: The preview button shows the mode: released eye = writing,
        pressed eye = preview; the tooltip says what a click does and the
        subtitle says "Preview" too.
        IT: Il pulsante dell'anteprima mostra la modalità: occhio normale =
        scrittura, occhio premuto = anteprima; il suggerimento dice cosa fa
        il clic e anche il sottotitolo dice «Anteprima»."""
        b = getattr(self, "preview_button", None)
        if b is None:
            return
        on = bool(self._preview_mode)
        self._syncing_preview = True
        b.set_active(on)
        self._syncing_preview = False
        tip = self.t("mi_edit_mode") if on else self.t("mi_preview")
        b.set_tooltip_text(tip)
        b.update_property([Gtk.AccessibleProperty.LABEL], [tip])
        self._update_window_title()

    def _render_preview(self):
        buf = self.preview_buffer
        buf.set_text("")
        self._pv_has_table = False
        if getattr(self, "_preview_whole", False):
            chapters = self.project._ordered_chapters()
            for i, (ch_title, text) in enumerate(chapters):
                if i > 0:
                    buf.insert(buf.get_end_iter(), "\n")
                    buf.insert_with_tags(buf.get_end_iter(),
                                         "* * *\n\n", self._pv_tags["sep"])
                first = text.lstrip().split("\n", 1)[0] if text.strip() else ""
                if classify_md_line(first)[0] != "heading":
                    buf.insert_with_tags(buf.get_end_iter(),
                                         ch_title + "\n", self._pv_tags["h1"])
                self._render_markdown_into(text)
        else:
            text = self.current.text if self.current is not None else ""
            self._render_markdown_into(text)

    def _preview_text_width(self):
        return max(200, self.preview_view.get_width()
                   - self.preview_view.get_left_margin()
                   - self.preview_view.get_right_margin() - 4)

    def _on_preview_width(self, *_a):
        if (not getattr(self, "_preview_mode", False) or not self._pv_has_table
                or self._pv_relayout_id
                or abs(self._preview_text_width() - self._pv_width) <= 4):
            return

        def relayout():
            self._pv_relayout_id = 0
            if self._preview_mode:
                self._render_preview()
            return False
        self._pv_relayout_id = GLib.timeout_add(150, relayout)

    def _preview_table(self, aligns, header, rows):
        """EN: A Markdown table in the preview: a real grid as wide as the
        page, cells that wrap, bold header, rows separated like GNOME lists.
        IT: Una tabella Markdown nell'anteprima: griglia vera larga quanto la
        pagina, celle che vanno a capo, intestazione in grassetto, righe
        separate come nelle liste di GNOME."""
        wrap = {"bold": ("<b>", "</b>"), "italic": ("<i>", "</i>"),
                "bolditalic": ("<b><i>", "</i></b>"), "code": ("<tt>", "</tt>"),
                "regular": ("", "")}

        def markup(runs, head):
            m = "".join(f"{wrap[st][0]}{GLib.markup_escape_text(t)}{wrap[st][1]}"
                        for t, st in runs)
            return f"<b>{m}</b>" if head else m
        grid = Gtk.Grid(hexpand=True)
        xalign = {"right": 1.0, "center": 0.5}
        for r, cells in enumerate([header] + rows):
            for c, cell in enumerate(cells):
                label = Gtk.Label(wrap=True, wrap_mode=Pango.WrapMode.WORD_CHAR,
                                  selectable=True, hexpand=True, valign=Gtk.Align.START,
                                  margin_start=12, margin_end=12,
                                  margin_top=8, margin_bottom=8,
                                  xalign=xalign.get(aligns[c], 0.0))
                # larghezza naturale = contenuto (al massimo 50 caratteri):
                # le colonne si dividono lo spazio in proporzione al testo
                label.set_max_width_chars(min(max(len(plain_runs(cell)), 4), 50))
                label.set_markup(markup(cell, r == 0))
                grid.attach(label, c, 2 * r, 1, 1)
            if r < len(rows):
                grid.attach(Gtk.Separator(), 0, 2 * r + 1, len(header), 1)
        card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        card.add_css_class("card")
        card.append(grid)
        # un figlio del TextView prende la sua larghezza naturale: si fissa qui
        card.set_size_request(self._preview_text_width(), -1)
        return card

    def _render_markdown_into(self, text):
        """Riversa il Markdown nel buffer dell'anteprima, dai blocchi del
        libro (model.book_blocks): l'anteprima mostra esattamente ciò che
        finirà negli export. Formule in simboli Unicode, tabelle come griglia
        vera, immagini come figure."""
        buf = self.preview_buffer
        self._pv_width = self._preview_text_width()
        end = buf.get_end_iter

        def insert_runs(runs, base_tags=()):
            for seg, style in runs:
                tag = self._pv_tags.get(style)
                tags = ([tag] if tag is not None else []) + list(base_tags)
                buf.insert_with_tags(end(), seg, *tags)

        def widget(child):
            anchor = buf.create_child_anchor(end())
            self.preview_view.add_child_at_anchor(child, anchor)
            buf.insert(end(), "\n")
            self._pv_has_table = True        # segue la larghezza della finestra

        def rule():
            # separatore: filetto corto e centrato, come nei libri
            width = self._preview_text_width()
            row = Gtk.Box(halign=Gtk.Align.START)
            row.set_size_request(width, 24)
            row.append(Gtk.Separator(hexpand=True, valign=Gtk.Align.CENTER,
                                     margin_start=int(width * 0.35),
                                     margin_end=int(width * 0.35)))
            widget(row)

        def blocks_into(blocks, base_tags=()):
            for b in blocks:
                kind = b[0]
                if kind == "heading":
                    buf.insert_with_tags(end(), plain_runs(b[2]) + "\n",
                                         self._pv_tags[f"h{min(3, b[1])}"])
                elif kind == "p":
                    for line in b[1]:
                        insert_runs(line, base_tags)
                        buf.insert(end(), "\n")
                elif kind == "list":
                    for depth, mark, line, inner in list_lines(b):
                        if inner is not None:
                            blocks_into([inner], base_tags)
                            continue
                        pad = "    " * depth
                        buf.insert(end(), f"{pad}  {mark}  " if mark else f"{pad}       ")
                        insert_runs(line, base_tags)
                        buf.insert(end(), "\n")
                elif kind == "quote":
                    blocks_into(b[1], tuple(base_tags) + (self._pv_tags["quote"],))
                elif kind == "image":
                    # figura vera con la didascalia; se il file non è nel
                    # progetto, un riquadro offre di sceglierlo
                    pal = self.palette()
                    widget(self._image_widget(b[2], b[1], self._preview_text_width(),
                                              pal["editor_fg"], pal["marker"]))
                elif kind == "table":
                    widget(self._preview_table(b[1], b[2], b[3]))
                elif kind == "rule":
                    rule()
                elif kind == "code":
                    for code_line in b[2].split("\n"):
                        buf.insert_with_tags(end(), code_line + "\n", self._pv_tags["code"])
                elif kind == "math":
                    buf.insert_with_tags(end(), b[1] + "\n", self._pv_tags["sep"])

        # una riga vuota fra i blocchi, come nel testo
        for i, block in enumerate(book_blocks(text)):
            if i:
                buf.insert(end(), "\n")
            blocks_into([block])

    # ---- informazioni -------------------------------------------------------
    def _cover_generator_dialog(self, on_done, parent=None):
        """EN: Cover generator: composes a typographic cover (colour ground,
        double rule frame, author, optional picture, title, publisher) with a
        live preview, and hands the resulting PNG bytes to 'on_done'. It is an
        ALTERNATIVE to attaching a ready-made image, never a replacement: the
        caller keeps its Attach/Remove buttons untouched.
        IT: Generatore di copertine: compone una copertina tipografica (fondo
        colorato, cornice a doppio filetto, autore, immagine facoltativa,
        titolo, editore) con anteprima dal vivo, e passa i byte PNG ottenuti a
        'on_done'. E' un'ALTERNATIVA all'allegare un'immagine gia' pronta, mai
        un sostituto: i pulsanti Allega/Rimuovi del chiamante restano intatti."""
        # EN: initial values taken from the frontispiece metadata the user has
        #     already filled in (title/author/publisher), so the generator
        #     opens with the book's own data instead of placeholders.
        # IT: valori iniziali presi dai dati del frontespizio gia' compilati
        #     dall'utente (titolo/autore/editore), cosi' il generatore si apre
        #     con i dati del libro invece che con segnaposto.
        front = getattr(self.project, "frontispiece_fields", {}) or {}
        st = {
            "fmt": getattr(self, "_pdf_page_size", pw_model.COVER_DEFAULT_FORMAT),
            "bg": pw_model.COVER_DEFAULT_COLOR,
            "txt": "#111111",
            "author": (front.get("author") or "").strip(),
            "title": (front.get("title") or self.project.title or "").strip(),
            "publisher": (front.get("publisher") or "").strip(),
            "image": None,
        }
        if st["fmt"] not in pw_model.COVER_FORMATS:
            st["fmt"] = pw_model.COVER_DEFAULT_FORMAT

        dialog = RuscaDialog(parent if isinstance(parent, Gtk.Widget) and not
                             isinstance(parent, RuscaDialog) else self)
        dialog.add_css_class("rusca-dialog")
        dialog.set_title(self._t_or("cover_gen_title", "Genera copertina"))
        dialog.set_default_size(760, 640)

        outer = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=14)
        outer.set_margin_top(16); outer.set_margin_bottom(16)
        outer.set_margin_start(18); outer.set_margin_end(18)
        outer.add_css_class("rusca-bg")

        # ---- colonna sinistra: controlli (scorrevole) ----
        ctrl_scroll = Gtk.ScrolledWindow()
        ctrl_scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        ctrl_scroll.set_vexpand(True)
        ctrl_scroll.set_size_request(320, -1)
        ctrl = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        ctrl_scroll.set_child(ctrl)
        outer.append(ctrl_scroll)

        # ---- colonna destra: anteprima ----
        prev_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        prev_box.set_hexpand(True)
        preview = Gtk.Picture()
        preview.set_can_shrink(True)
        preview.set_vexpand(True)
        prev_box.append(preview)
        outer.append(prev_box)

        def _label(text, bold=False):
            l = Gtk.Label(xalign=0)
            if bold:
                l.set_markup(f"<b>{GLib.markup_escape_text(text)}</b>")
            else:
                l.set_text(text)
            l.add_css_class("rusca-dialog-text")
            return l

        # --- anteprima: ridisegnata a ogni modifica ---
        def refresh():
            data = pw_model.render_cover_image(
                fmt_key=st["fmt"], dpi=pw_model.COVER_PREVIEW_DPI,
                bg_color=st["bg"], text_color=st["txt"],
                author=st["author"], title=st["title"],
                publisher=st["publisher"], image_bytes=st["image"],
                out_format="png", font_dir=ASSETS_DIR)
            if not data or GdkPixbuf is None:
                preview.set_paintable(None)
                return
            try:
                loader = GdkPixbuf.PixbufLoader()
                loader.write(data); loader.close()
                preview.set_pixbuf(loader.get_pixbuf())
            except Exception:
                preview.set_paintable(None)

        # --- campi di testo ---
        ctrl.append(_label(self._t_or("cover_gen_texts", "Testi"), bold=True))

        def text_field(label_key, default_label, key):
            ctrl.append(_label(self._t_or(label_key, default_label)))
            e = Gtk.Entry()
            e.add_css_class("rusca-dialog")
            e.set_text(st[key] or "")

            def changed(entry):
                st[key] = entry.get_text()
                refresh()
            e.connect("changed", changed)
            ctrl.append(e)
            return e

        text_field("cover_gen_author", "Autore", "author")
        text_field("cover_gen_book_title", "Titolo", "title")
        text_field("cover_gen_publisher", "Casa editrice", "publisher")

        # --- immagine facoltativa ---
        ctrl.append(_label(self._t_or("cover_gen_image", "Immagine"), bold=True))
        img_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        b_pick = Gtk.Button(label=self._t_or("cover_gen_pick", "Scegli…"))
        b_clear = Gtk.Button(label=self._t_or("cover_gen_clear", "Togli"))

        def pick_image():
            def on_path(path):
                try:
                    with open(path, "rb") as f:
                        data = f.read()
                    if pw_model.image_format(data) is None:
                        self._error(self.t("err_img_format"))
                        return
                    st["image"] = data
                    refresh()
                except Exception as exc:
                    self._error(self.t("err_open", e=exc))
            self._open_file_dialog(self._t_or("cover_gen_pick", "Scegli…"),
                                   ["*.png", "*.jpg", "*.jpeg", "*.webp"],
                                   self.t("filter_image"), on_path)

        b_pick.connect("clicked", lambda *_: pick_image())

        def clear_image(*_):
            st["image"] = None
            refresh()
        b_clear.connect("clicked", clear_image)
        img_row.append(b_pick); img_row.append(b_clear)
        ctrl.append(img_row)

        # --- formato pagina ---
        ctrl.append(_label(self._t_or("cover_gen_format", "Formato"), bold=True))
        fmt_keys = list(pw_model.COVER_FORMATS.keys())
        fmt_combo = Gtk.ComboBoxText()
        for k in fmt_keys:
            # le etichette gia' contengono le misure in centimetri
            fmt_combo.append_text(PDF_PAGE_SIZE_LABELS.get(k, k))
        fmt_combo.set_active(fmt_keys.index(st["fmt"]))

        def fmt_changed(cb):
            i = cb.get_active()
            if 0 <= i < len(fmt_keys):
                st["fmt"] = fmt_keys[i]
                refresh()
        fmt_combo.connect("changed", fmt_changed)
        ctrl.append(fmt_combo)

        # --- colore del fondo: tavolozza + scelta libera ---
        ctrl.append(_label(self._t_or("cover_gen_color", "Colore"), bold=True))
        grid = Gtk.Grid()
        grid.set_row_spacing(6); grid.set_column_spacing(6)
        for i, hexcol in enumerate(pw_model.COVER_COLORS):
            sw = Gtk.Button()
            sw.set_size_request(34, 26)
            # pastiglia colorata come contenuto del pulsante
            css = Gtk.CssProvider()
            css.load_from_data(
                f"button {{ background-image:none; background-color:{hexcol}; }}"
                .encode("utf-8"))
            sw.get_style_context().add_provider(
                css, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)
            sw.set_tooltip_text(hexcol)

            def pick(_b, c=hexcol):
                st["bg"] = c
                refresh()
            sw.connect("clicked", pick)
            grid.attach(sw, i % 6, i // 6, 1, 1)
        ctrl.append(grid)

        free_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        free_row.append(_label(self._t_or("cover_gen_custom", "Personalizzato")))
        color_btn = Gtk.ColorButton()
        try:
            rgba = Gdk.RGBA(); rgba.parse(st["bg"])
            color_btn.set_rgba(rgba)
        except Exception:
            pass

        def color_set(btn):
            c = btn.get_rgba()
            st["bg"] = "#%02x%02x%02x" % (int(c.red * 255 + .5),
                                          int(c.green * 255 + .5),
                                          int(c.blue * 255 + .5))
            refresh()
        color_btn.connect("color-set", color_set)
        free_row.append(color_btn)
        ctrl.append(free_row)

        # --- colore del testo ---
        ctrl.append(_label(self._t_or("cover_gen_text_color", "Testo"), bold=True))
        txt_combo = Gtk.ComboBoxText()
        txt_combo.append_text(self._t_or("cover_gen_text_dark", "Testo nero"))
        txt_combo.append_text(self._t_or("cover_gen_text_light", "Testo bianco"))
        txt_combo.set_active(0)

        def txt_changed(cb):
            st["txt"] = "#ffffff" if cb.get_active() == 1 else "#111111"
            refresh()
        txt_combo.connect("changed", txt_changed)
        ctrl.append(txt_combo)

        # ---- pulsanti finali ----
        actions = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        actions.set_halign(Gtk.Align.END)
        b_cancel = Gtk.Button(label=self.t("btn_cancel"))
        b_use = Gtk.Button(label=self._t_or("cover_gen_use", "Usa come copertina"))
        b_use.add_css_class("suggested-action")
        actions.append(b_cancel); actions.append(b_use)
        prev_box.append(actions)

        def close(*_):
            dialog.destroy()
        b_cancel.connect("clicked", close)

        def confirm(*_):
            # immagine finale a piena risoluzione (300 DPI), non l'anteprima
            data = pw_model.render_cover_image(
                fmt_key=st["fmt"], dpi=pw_model.COVER_EXPORT_DPI,
                bg_color=st["bg"], text_color=st["txt"],
                author=st["author"], title=st["title"],
                publisher=st["publisher"], image_bytes=st["image"],
                out_format="png", font_dir=ASSETS_DIR)
            dialog.destroy()
            if data:
                on_done(data)
            else:
                self._error(self._t_or(
                    "cover_gen_failed",
                    "Non è stato possibile generare la copertina."))
        b_use.connect("clicked", confirm)

        dialog.set_child(outer)
        dialog.set_default_widget(b_use)
        refresh()
        dialog.present()
        GLib.idle_add(self._raise_dialog, dialog)

    def on_edit_sections(self, *_):
        """Dialogo per gestire le tre sezioni editoriali: immagine di copertina,
        frontespizio e colophon. Le modifiche vengono applicate al progetto solo
        quando si preme Salva."""
        dialog, outer = self._dialog_shell(self.t("sections_title"),
                                           size=(560, 640), margin=18)

        scroller = Gtk.ScrolledWindow()
        scroller.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        scroller.set_vexpand(True)
        body = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=14)
        scroller.set_child(body)
        outer.append(scroller)

        # stato locale modificabile prima del salvataggio
        pending = {"image": self.project.cover_image,
                   "fmt": self.project.cover_image_fmt}

        # --- sezione COPERTINA (immagine) ---
        cov_head = Gtk.Label(xalign=0)
        cov_head.set_markup(f"<b>{GLib.markup_escape_text(self.t('sec_cover'))}</b>")
        cov_head.add_css_class("rusca-dialog-text")
        body.append(cov_head)

        cov_hint = Gtk.Label(label=self.t("sec_cover_hint"), xalign=0)
        cov_hint.add_css_class("rusca-dialog-text")
        cov_hint.set_wrap(True)
        body.append(cov_hint)

        preview = Gtk.Picture()
        preview.set_size_request(-1, 200)
        preview.set_can_shrink(True)

        def refresh_preview():
            data = pending["image"]
            if data and GdkPixbuf is not None:
                try:
                    loader = GdkPixbuf.PixbufLoader()
                    loader.write(data); loader.close()
                    preview.set_pixbuf(loader.get_pixbuf())
                    preview.set_visible(True)
                except Exception:
                    preview.set_visible(False)
            else:
                preview.set_visible(False)
            status_lbl.set_text(self.t("sec_cover_set") if pending["image"]
                                else self.t("sec_cover_none"))

        status_lbl = Gtk.Label(xalign=0)
        status_lbl.add_css_class("rusca-dialog-text")
        body.append(preview)
        body.append(status_lbl)

        btnrow = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        b_attach = Gtk.Button(label=self.t("sec_cover_attach"))
        b_generate = Gtk.Button(
            label=self._t_or("sec_cover_generate", "Genera…"))
        b_remove = Gtk.Button(label=self.t("sec_cover_remove"))

        def do_attach():
            def on_path(path):
                try:
                    with open(path, "rb") as f:
                        data = f.read()
                    # EN: format detected from the CONTENT (magic bytes),
                    #     so a wrong extension cannot fool the export.
                    # IT: formato riconosciuto dal CONTENUTO (byte iniziali),
                    #     cosi' un'estensione sbagliata non inganna l'export.
                    fmt = pw_model.image_format(data)
                    if fmt is None:
                        self._error(self.t("err_img_format"))
                        return
                    pending["image"] = data
                    pending["fmt"] = fmt
                    refresh_preview()
                except Exception as exc:
                    self._error(self.t("err_open", e=exc))
            self._open_file_dialog(self.t("sec_cover_attach"),
                                   ["*.png", "*.jpg", "*.jpeg", "*.webp"],
                                   self.t("filter_image"), on_path)

        def do_remove():
            pending["image"] = None
            pending["fmt"] = None
            refresh_preview()

        def do_generate():
            # EN: the generator returns PNG bytes; they enter the very same
            #     pending slot used by an attached image, so saving, preview
            #     and every export treat both origins identically.
            # IT: il generatore restituisce byte PNG; entrano nello stesso
            #     spazio "pending" di un'immagine allegata, cosi' salvataggio,
            #     anteprima ed export trattano le due origini allo stesso modo.
            def on_done(data):
                if not data:
                    return
                pending["image"] = data
                pending["fmt"] = pw_model.image_format(data) or "png"
                refresh_preview()
            self._cover_generator_dialog(on_done, parent=dialog)

        b_attach.connect("clicked", lambda *_: do_attach())
        b_generate.connect("clicked", lambda *_: do_generate())
        b_remove.connect("clicked", lambda *_: do_remove())
        btnrow.append(b_attach)
        btnrow.append(b_generate)
        btnrow.append(b_remove)
        body.append(btnrow)

        # senza Pillow non si puo' disegnare il testo della copertina: il
        # generatore resta visibile ma disattivato, con una spiegazione.
        if not pw_model.cover_generator_available():
            b_generate.set_sensitive(False)
            b_generate.set_tooltip_text(self._t_or(
                "sec_cover_generate_needs_pil",
                "Per generare una copertina serve Pillow: "
                "sudo apt install python3-pil"))

        # helper per creare una riga "etichetta + campo"
        def field_row(label_text, value=""):
            lbl = Gtk.Label(xalign=0, label=label_text)
            lbl.add_css_class("rusca-dialog-text")
            entry = Gtk.Entry()
            entry.add_css_class("rusca-dialog")
            entry.set_hexpand(True)
            entry.set_text(value or "")
            body.append(lbl)
            body.append(entry)
            return entry

        def group_head(text):
            h = Gtk.Label(xalign=0)
            h.set_markup(f"<b>{GLib.markup_escape_text(text)}</b>")
            h.add_css_class("rusca-dialog-text")
            body.append(h)

        fr = self.project.frontispiece_fields
        co = self.project.colophon_fields

        hint = Gtk.Label(xalign=0, label=self.t("sec_fields_hint"))
        hint.add_css_class("rusca-dialog-text"); hint.set_wrap(True)
        body.append(hint)

        # --- DATI DELL'OPERA: titolo (precompilato), sottotitolo, autore ---
        group_head(self.t("grp_work"))
        e_title = field_row(self.t("fld_title"),
                            fr.get("title", "") or self.project.title)
        e_subtitle = field_row(self.t("fld_subtitle"), fr.get("subtitle", ""))
        e_author = field_row(self.t("fld_author"), fr.get("author", ""))

        # --- PUBBLICAZIONE: editore (unico), luogo/anno, edizione, ISBN ----
        group_head(self.t("grp_pub"))
        e_publisher = field_row(self.t("fld_publisher"),
                                fr.get("publisher", "") or co.get("publisher", ""))
        e_place = field_row(self.t("fld_place_year"), fr.get("place_year", ""))
        e_edition = field_row(self.t("fld_edition"), co.get("edition", ""))
        e_isbn = field_row(self.t("fld_isbn"), co.get("isbn", ""))

        # --- COLOPHON: copyright (auto se vuoto), licenza, note ------------
        group_head(self.t("sec_colophon"))
        e_copyright = field_row(self.t("fld_copyright"), co.get("copyright", ""))
        e_license = field_row(self.t("fld_license"), co.get("license", ""))
        lbl_notes = Gtk.Label(xalign=0, label=self.t("fld_notes"))
        lbl_notes.add_css_class("rusca-dialog-text")
        body.append(lbl_notes)
        co_notes_view = Gtk.TextView()
        co_notes_view.set_wrap_mode(Gtk.WrapMode.WORD)
        co_notes_view.add_css_class("rusca-dialog")
        co_notes_view.get_buffer().set_text(co.get("notes", ""))
        nf = Gtk.ScrolledWindow()
        nf.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        nf.set_child(co_notes_view)
        nf.set_size_request(-1, 70)
        body.append(nf)

        # --- pulsanti finali ---
        actions = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8,
                          halign=Gtk.Align.END)
        b_cancel = Gtk.Button(label=self.t("cancel"))
        b_save = Gtk.Button(label=self.t("save"))
        b_save.add_css_class("suggested-action")

        def do_save():
            self.project.cover_image = pending["image"]
            self.project.cover_image_fmt = pending["fmt"]
            fr["title"] = e_title.get_text().strip()
            fr["subtitle"] = e_subtitle.get_text().strip()
            fr["author"] = e_author.get_text().strip()
            fr["place_year"] = e_place.get_text().strip()
            # l'editore si inserisce UNA volta e vale per frontespizio e colophon
            pub = e_publisher.get_text().strip()
            fr["publisher"] = pub
            co["publisher"] = pub
            co["edition"] = e_edition.get_text().strip()
            co["isbn"] = e_isbn.get_text().strip()
            co["license"] = e_license.get_text().strip()
            b = co_notes_view.get_buffer()
            co["notes"] = b.get_text(b.get_start_iter(), b.get_end_iter(),
                                     False).strip()
            # copyright: se lasciato vuoto ma c'e' l'autore, lo generiamo noi
            cpy = e_copyright.get_text().strip()
            if not cpy and fr["author"]:
                import datetime
                cpy = "© %d %s" % (datetime.date.today().year, fr["author"])
            co["copyright"] = cpy
            self._mark_dirty()
            dialog.destroy()

        b_cancel.connect("clicked", lambda *_: dialog.destroy())
        b_save.connect("clicked", lambda *_: do_save())
        actions.append(b_cancel)
        actions.append(b_save)
        outer.append(actions)

        dialog.set_child(outer)
        refresh_preview()
        dialog.present()
        GLib.idle_add(self._raise_dialog, dialog)

    def on_info(self, *_):
        show_about_dialog(self, self.t, APP_ID, APP_NAME, APP_VERSION_SHORT,
                          self.t("app_description"), theme_has_icon(), COMPONENTS)

    def show_shortcuts(self, *_):
        """Adw.ShortcutsDialog arriva con libadwaita 1.8: su trixie un
        Adw.Dialog con righe normali, in tre gruppi."""
        t = self.t
        groups = (
            (t("menu_file"), (("mi_new", "<Control>n"), ("mi_open", "<Control>o"),
                              ("mi_save", "<Control>s"), ("mi_import_chapters", "<Control>i"),
                              ("mi_page_setup", "<Control><Shift>p"))),
            (t("menu_edit"), (("mi_add", "<Control><Shift>n"), ("mi_rename", "F2"),
                              ("mi_up", "<Control><Shift>Up"), ("mi_down", "<Control><Shift>Down"),
                              ("mi_insert_image", "<Control><Shift>i"), ("mi_find", "<Control>f"),
                              ("mi_lookup", "<Control>d"), ("mi_show_breaks", "<Control><Shift>b"))),
            (t("menu_view"), (("mi_preview", "<Control>e"), ("mi_preview_all", "<Control><Shift>e"),
                              ("mi_toggle_left", "<Control>l"), ("mi_toggle_right", "<Control>r"),
                              ("mi_fullscreen", "F11"), ("mi_font_inc", "<Control>plus"),
                              ("mi_font_dec", "<Control>minus"),
                              ("mi_appearance_dark", "<Control><Shift>d"),
                              ("mi_md_help", "<Shift>F1"), ("shortcuts", "<Control>question"),
                              ("main_menu", "F10"), ("sc_close", "<Control>w"),
                              ("mi_quit", "<Control>q"))),
        )
        page = Adw.PreferencesPage()
        for title, rows in groups:
            group = Adw.PreferencesGroup(title=title)
            for key, accel in rows:
                row = Adw.ActionRow(title=self._t_or(key, key).rstrip("…").rstrip("\u2026"),
                                    use_markup=False)
                ok, keyval, mods = Gtk.accelerator_parse(accel)
                lbl = Gtk.Label(label=Gtk.accelerator_get_label(keyval, mods) if ok else accel)
                lbl.add_css_class("dim-label")
                row.add_suffix(lbl)
                group.add(row)
            page.add(group)
        view = Adw.ToolbarView(content=page)
        view.add_top_bar(Adw.HeaderBar())
        Adw.Dialog(title=t("shortcuts"), content_width=460, content_height=560,
                   child=view).present(self)

    def on_md_help(self, *_):
        """Finestra 'Guida ai comandi Markdown': elenca in breve la sintassi
        Markdown che l'editor riconosce e impagina negli export (specialmente
        nel PDF). E' costruita come una griglia a due colonne: a sinistra
        l'esempio di sintassi (in monospazio), a destra l'effetto. I testi
        vengono dai file di lingua con ripiego in italiano, cosi' la guida e'
        traducibile senza toccare il codice."""
        # ogni voce: (chiave_traduzione, esempio_sintassi, descrizione_fallback)
        rows = [
            ("md_h1",     "# Titolo",          "Titolo di primo livello"),
            ("md_h2",     "## Sottotitolo",    "Titoli minori (fino a ######)"),
            ("md_bold",   "**grassetto**",     "Testo in grassetto"),
            ("md_italic", "*corsivo*",         "Testo in corsivo"),
            ("md_both",   "***entrambi***",    "Grassetto e corsivo insieme"),
            ("md_code",   "`codice`",          "Testo a spaziatura fissa"),
            ("md_quote",  "> citazione",       "Citazione (resa in corsivo)"),
            ("md_ul",     "- elenco",          "Elenco puntato (anche * o +)"),
            ("md_ol",     "1. elenco",         "Elenco numerato"),
            ("md_link",   "[testo](url)",      "Collegamento (resta il testo)"),
            ("md_img",    "![didascalia](img)", "Immagine allegata con didascalia"),
            ("md_para",   "riga vuota",        "Una riga vuota separa i paragrafi"),
        ]

        dialog, box = self._dialog_shell(
            self._t_or("mi_md_help", "Guida ai comandi Markdown"),
            size=(480, 540), margin=22)

        title = Gtk.Label()
        title.set_markup("<span size='large' weight='bold'>%s</span>"
                         % GLib.markup_escape_text(
                             self._t_or("mi_md_help",
                                        "Guida ai comandi Markdown")))
        title.set_xalign(0.5)
        title.add_css_class("column-title")
        box.append(title)

        intro = Gtk.Label(label=self._t_or(
            "md_help_intro",
            "L'editor usa Markdown. Scrivi normalmente e usa questi simboli "
            "per la formattazione: verranno resi negli export (PDF, EPUB, "
            "ODT, DOCX, HTML)."))
        intro.add_css_class("rusca-dialog-text")
        intro.set_wrap(True)
        intro.set_justify(Gtk.Justification.CENTER)
        intro.set_xalign(0.5); intro.set_max_width_chars(48)
        box.append(intro)

        grid = Gtk.Grid()
        grid.set_row_spacing(8)
        grid.set_column_spacing(18)
        grid.set_margin_start(4); grid.set_margin_end(4)
        for i, (key, syntax, fallback) in enumerate(rows):
            code = Gtk.Label()
            # esempio in monospazio, cosi' i simboli si distinguono bene
            code.set_markup("<tt>%s</tt>" % GLib.markup_escape_text(syntax))
            code.set_xalign(0.0)
            code.add_css_class("rusca-dialog-text")
            code.set_selectable(True)
            desc = Gtk.Label(label=self._t_or(key, fallback))
            desc.set_xalign(0.0)
            desc.set_wrap(True)
            desc.set_max_width_chars(30)
            desc.add_css_class("rusca-dialog-text")
            grid.attach(code, 0, i, 1, 1)
            grid.attach(desc, 1, i, 1, 1)

        scroller = Gtk.ScrolledWindow()
        scroller.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        scroller.set_vexpand(True)
        scroller.set_child(grid)
        box.append(scroller)

        btn = Gtk.Button(label=self.t("ok"))
        btn.add_css_class("suggested-action")
        btn.set_halign(Gtk.Align.CENTER)
        btn.connect("clicked", lambda *_: dialog.destroy())
        box.append(btn)

        self._dialog_present(dialog, box, btn)

    # ---- export -------------------------------------------------------------
    def on_export(self, *_):
        self._export_simple("txt", None, self.project.export_txt,
                            title_key="dlg_export_title")

    def on_export_pdf(self, *_):
        """Esporta in PDF: prima l'impostazione della pagina (formato,
        margini, giustificazione), poi la scelta del file."""
        self._commit_current()
        self._page_setup_dialog(for_export=True)

    def on_page_setup(self, *_):
        """File -> Impostazione pagina: formato e margini del libro, senza
        esportare. Valgono per PDF, ODT e DOCX."""
        self._commit_current()
        self._page_setup_dialog(for_export=False)

    # unita' di misura del dialogo: (codice, mm per unita', cifre, passo)
    PAGE_UNITS = (("mm", 1.0, 1, 0.5), ("cm", 10.0, 2, 0.05),
                  ("in", 25.4, 3, 0.01))

    def _page_setup_dialog(self, for_export=False):
        """EN: the page set-up dialog. Format, a margin preset, mirrored
        pages, the five margins (top, bottom, inner, outer, gutter) in mm, cm
        or inches, and a live preview of the spread with the text block, the
        size of the block and the characters per line. For the PDF export it
        also holds justification and hyphenation, and ends in the file
        chooser.
        IT: il dialogo di impostazione della pagina. Formato, un modello di
        margini, le pagine speculari, i cinque margini (superiore, inferiore,
        interno, esterno, rilegatura) in mm, cm o pollici, e un'anteprima dal
        vivo della doppia pagina con la gabbia del testo, la sua misura e le
        battute per riga. Per l'export PDF contiene anche giustificazione e
        sillabazione, e termina nella scelta del file."""
        sizes = list(PDF_PAGE_SIZES.keys())
        cur = getattr(self, "_pdf_page_size", PDF_DEFAULT_PAGE_SIZE)
        if cur not in PDF_PAGE_SIZES:
            cur = PDF_DEFAULT_PAGE_SIZE
        # copia di lavoro: un insieme di margini per ogni formato visitato
        work = {}
        st = {"size": cur, "busy": False, "done": False,
              "unit": self.settings.get("page_unit", "mm")}
        if st["unit"] not in [u[0] for u in self.PAGE_UNITS]:
            st["unit"] = "mm"

        def margins():
            if st["size"] not in work:
                work[st["size"]] = dict(self.project.page_margins(st["size"]))
            return work[st["size"]]

        def unit_info():
            for u in self.PAGE_UNITS:
                if u[0] == st["unit"]:
                    return u
            return self.PAGE_UNITS[0]

        title = self._t_or("ps_title", "Impostazione pagina")
        dialog, box = self._dialog_shell(title, spacing=12, margin=18)
        head = Gtk.Label()
        head.set_markup("<b>%s</b>" % GLib.markup_escape_text(title))
        head.add_css_class("rusca-dialog-text")
        head.set_xalign(0)
        box.append(head)

        body = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=24)
        box.append(body)
        left = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        body.append(left)

        def lab(text, xalign=1.0):
            w = Gtk.Label(label=text)
            w.add_css_class("rusca-dialog-text")
            w.set_xalign(xalign)
            return w

        grid = Gtk.Grid(column_spacing=10, row_spacing=8)
        left.append(grid)
        # formato
        dd_size = Gtk.DropDown.new_from_strings(
            [PDF_PAGE_SIZE_LABELS.get(k, k) for k in sizes])
        dd_size.set_selected(sizes.index(cur))
        grid.attach(lab(self._t_or("ps_format", "Formato")), 0, 0, 1, 1)
        grid.attach(dd_size, 1, 0, 3, 1)
        # modello di margini
        preset_codes = list(MARGIN_PRESETS) + [MARGIN_PRESET_CUSTOM]
        preset_names = {
            "format": self._t_or("ps_preset_format", "Margini del formato"),
            "canon": self._t_or("ps_preset_canon", "Canone classico (2:3:4:6)"),
            "notes": self._t_or("ps_preset_notes",
                                "Esterno ampio per le note"),
            "manuscript": self._t_or("ps_preset_manuscript",
                                     "Manoscritto (2,54 cm)"),
            MARGIN_PRESET_CUSTOM: self._t_or("ps_preset_custom",
                                             "Personalizzati"),
        }
        dd_preset = Gtk.DropDown.new_from_strings(
            [preset_names[c] for c in preset_codes])
        grid.attach(lab(self._t_or("ps_preset", "Modello")), 0, 1, 1, 1)
        grid.attach(dd_preset, 1, 1, 3, 1)
        # pagine speculari
        chk_mirror = Gtk.CheckButton(label=self._t_or(
            "ps_mirror", "Pagine affiancate (margini speculari)"))
        chk_mirror.add_css_class("rusca-dialog-text")
        grid.attach(chk_mirror, 1, 2, 3, 1)

        sep = Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL)
        sep.set_margin_top(2); sep.set_margin_bottom(2)
        grid.attach(sep, 0, 3, 4, 1)
        mh = Gtk.Label()
        mh.set_markup("<b>%s</b>" % GLib.markup_escape_text(
            self._t_or("ps_margins", "Margini")))
        mh.add_css_class("rusca-dialog-text")
        mh.set_xalign(0)
        grid.attach(mh, 0, 4, 2, 1)
        # unita' di misura
        unit_codes = [u[0] for u in self.PAGE_UNITS]
        dd_unit = Gtk.DropDown.new_from_strings([
            self._t_or("ps_unit_mm", "mm"), self._t_or("ps_unit_cm", "cm"),
            self._t_or("ps_unit_in", "pollici")])
        dd_unit.set_selected(unit_codes.index(st["unit"]))
        unit_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6,
                           halign=Gtk.Align.END)
        unit_row.append(lab(self._t_or("ps_unit", "Unita'")))
        unit_row.append(dd_unit)
        grid.attach(unit_row, 2, 4, 2, 1)

        # i cinque margini, in due colonne come nei programmi di
        # impaginazione: verticali a sinistra, orizzontali a destra
        spins, side_labels = {}, {}
        posti = (("top", 5, 0), ("bottom", 6, 0), ("inner", 5, 2),
                 ("outer", 6, 2), ("gutter", 7, 2))
        for chiave, riga, col in posti:
            l = lab("")
            side_labels[chiave] = l
            sp = Gtk.SpinButton()
            sp.set_numeric(True)
            sp.set_width_chars(7)
            sp.set_hexpand(False)
            spins[chiave] = sp
            grid.attach(l, col, riga, 1, 1)
            grid.attach(sp, col + 1, riga, 1, 1)

        # opzioni tipografiche, solo per l'export PDF
        opts = {"justify": None, "hyphenate": None}
        if for_export:
            sep2 = Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL)
            left.append(sep2)
            cur_lang = getattr(self, "lang", "it")
            hyph_ok = hyphenation_available(cur_lang)
            chk_justify = Gtk.CheckButton(
                label=self._t_or("dlg_pdf_justify", "Giustifica il testo"))
            chk_justify.add_css_class("rusca-dialog-text")
            chk_justify.set_active(getattr(self, "_pdf_justify", False))
            left.append(chk_justify)
            chk_hyphen = Gtk.CheckButton(label=self._t_or(
                "dlg_pdf_hyphenate", "Sillaba le parole a fine riga"))
            chk_hyphen.add_css_class("rusca-dialog-text")
            chk_hyphen.set_active(
                hyph_ok and getattr(self, "_pdf_hyphenate", False))
            left.append(chk_hyphen)
            opts["justify"], opts["hyphenate"] = chk_justify, chk_hyphen

            def _sync_hyphen(*_):
                can = chk_justify.get_active() and hyph_ok
                chk_hyphen.set_sensitive(can)
                if not can:
                    chk_hyphen.set_active(False)
            chk_justify.connect("toggled", _sync_hyphen)
            _sync_hyphen()
            if not hyph_ok:
                if not HAVE_PYPHEN:
                    hint_text = self._t_or(
                        "dlg_pdf_hyphenate_hint",
                        "Per sillabare installa Pyphen e un dizionario:\n"
                        "sudo apt install python3-pyphen hyphen-it")
                else:
                    hint_text = self._t_or(
                        "dlg_pdf_hyphenate_hint_dict",
                        "Per sillabare in questa lingua installa il "
                        "dizionario:\nsudo apt install hyphen-<lingua>")
                hyp_hint = lab(hint_text, 0.0)
                hyp_hint.set_wrap(True)
                hyp_hint.set_max_width_chars(46)
                hyp_hint.set_opacity(0.8)
                left.append(hyp_hint)

        # --- colonna destra: anteprima e misure ------------------------------
        right = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        body.append(right)
        area = Gtk.DrawingArea()
        area.set_content_width(340)
        area.set_content_height(250)
        right.append(area)
        info = lab("", 0.0)
        info.set_wrap(True)
        info.set_max_width_chars(46)
        right.append(info)
        warn = lab("", 0.0)
        warn.set_wrap(True)
        warn.set_max_width_chars(46)
        warn.set_use_markup(True)
        right.append(warn)
        note = lab(self._t_or(
            "ps_hint", "I margini si salvano nel documento, uno per ogni "
            "formato. Valgono per PDF, ODT e DOCX."), 0.0)
        note.set_wrap(True)
        note.set_max_width_chars(46)
        note.set_opacity(0.8)
        right.append(note)

        def rgb(hex_color):
            h = hex_color.lstrip("#")
            return tuple(int(h[i:i + 2], 16) / 255 for i in (0, 2, 4))

        def draw(_a, cr, w, h, *_):
            pal = self.palette()
            m = margins()
            pw, ph = page_size_mm(st["size"])
            n = 2 if m["mirror"] else 1
            gap, pad = 4.0, 8.0
            k = min((w - 2 * pad - gap * (n - 1)) / (n * pw),
                    (h - 2 * pad) / ph)
            tot_w = n * pw * k + gap * (n - 1)
            x0 = (w - tot_w) / 2.0
            y0 = (h - ph * k) / 2.0
            # la carta stampata, smorzata nel tema scuro per non abbagliare
            carta = rgb("#FBFAF7") if not self.dark_mode else rgb("#CFCBC4")
            bordo = rgb(pal["dialog_fg"])
            acc = rgb(pal["accent"] if not self.dark_mode else pal["head"])
            inchiostro = rgb("#555555")
            interlinea = max(1.5, (self.font_size * 1.45 / PT_PER_MM_UI) * k)
            for i in range(n):
                px = x0 + i * (pw * k + gap)
                # verso a sinistra (interno a destra), recto a destra
                verso = m["mirror"] and i == 0
                interno = m["inner"] + m["gutter"]
                sx = m["outer"] if verso else interno
                # pagina con un'ombra leggera
                cr.set_source_rgba(0, 0, 0, 0.18)
                cr.rectangle(px + 2, y0 + 2, pw * k, ph * k)
                cr.fill()
                cr.set_source_rgb(*carta)
                cr.rectangle(px, y0, pw * k, ph * k)
                cr.fill()
                cr.set_source_rgba(*bordo, 0.55)
                cr.set_line_width(1)
                cr.rectangle(px + 0.5, y0 + 0.5, pw * k - 1, ph * k - 1)
                cr.stroke()
                # rilegatura: fascia tratteggiata dal lato della piega
                if m["gutter"] > 0:
                    gx = px + (pw - m["gutter"]) * k if verso else px
                    cr.set_source_rgba(*acc, 0.14)
                    cr.rectangle(gx, y0, m["gutter"] * k, ph * k)
                    cr.fill()
                # gabbia del testo
                bx = px + sx * k
                by = y0 + m["top"] * k
                bw = (pw - m["inner"] - m["outer"] - m["gutter"]) * k
                bh = (ph - m["top"] - m["bottom"]) * k
                cr.set_source_rgba(*acc, 0.07)
                cr.rectangle(bx, by, bw, bh)
                cr.fill()
                # righe di testo simulate: paragrafi con l'ultima riga corta
                cr.set_source_rgba(*inchiostro, 0.55)
                yy = by + interlinea
                riga = 0
                while yy < by + bh - 1 and bw > 4:
                    fine = ((riga + i * 3) % 7 == 6)
                    lw = bw * (0.55 if fine else 1.0)
                    rientro = interlinea * 1.2 if (riga + i * 3) % 7 == 0 else 0
                    cr.rectangle(bx + rientro, yy - 0.6,
                                 max(0.0, lw - rientro), 1.2)
                    riga += 1
                    yy += interlinea
                cr.fill()
                # contorno della gabbia e numero di pagina
                cr.set_source_rgba(*acc, 0.9)
                cr.set_line_width(1)
                cr.rectangle(bx + 0.5, by + 0.5, max(0, bw - 1),
                             max(0, bh - 1))
                cr.stroke()
                ny = y0 + (ph - m["bottom"] / 2.0) * k
                cr.arc(bx + bw / 2.0, ny, 1.6, 0, 6.2832)
                cr.fill()
            # piega centrale della doppia pagina
            if n == 2:
                cx = x0 + pw * k + gap / 2.0
                cr.set_source_rgba(*bordo, 0.35)
                cr.move_to(cx, y0 - 3)
                cr.line_to(cx, y0 + ph * k + 3)
                cr.stroke()

        area.set_draw_func(draw)

        def fmt(v_mm):
            _c, per, cifre, _p = unit_info()
            testo = f"{v_mm / per:.{cifre}f}"
            return testo.replace(".", ",") if self.lang in (
                "it", "de", "fr", "es", "pt_BR", "ru", "pl", "tr", "id") \
                else testo

        def refresh_labels():
            speculari = margins()["mirror"]
            nomi = {
                "top": self._t_or("ps_top", "Superiore"),
                "bottom": self._t_or("ps_bottom", "Inferiore"),
                "inner": self._t_or("ps_inner", "Interno") if speculari
                else self._t_or("ps_left", "Sinistro"),
                "outer": self._t_or("ps_outer", "Esterno") if speculari
                else self._t_or("ps_right", "Destro"),
                "gutter": self._t_or("ps_gutter", "Rilegatura"),
            }
            for k2, l in side_labels.items():
                l.set_label(nomi[k2])

        def load_spins():
            """Riporta nei campi i margini correnti, nell'unita' scelta."""
            st["busy"] = True
            _c, per, cifre, passo = unit_info()
            m = margins()
            for k2, sp in spins.items():
                lo = 0.0 if k2 == "gutter" else MARGIN_MIN_MM
                hi = GUTTER_MAX_MM if k2 == "gutter" else MARGIN_MAX_MM
                sp.set_digits(cifre)
                sp.set_range(lo / per, hi / per)
                sp.set_increments(passo, passo * 10)
                sp.set_value(m[k2] / per)
            chk_mirror.set_active(bool(m["mirror"]))
            dd_preset.set_selected(preset_codes.index(
                which_margin_preset(st["size"], m)))
            st["busy"] = False

        def refresh():
            m = margins()
            refresh_labels()
            area.queue_draw()
            u = st["unit"]
            simbolo = {"mm": "mm", "cm": "cm", "in": "in"}[u]
            bw, bh = text_block_mm(st["size"], m)
            cpl = chars_per_line(st["size"], m, self.font_size)
            info.set_label(self._t_or(
                "ps_block", "Gabbia del testo: {w} \u00d7 {h} {u} \u00b7 "
                "circa {c} battute per riga").format(
                    w=fmt(bw), h=fmt(bh), u=simbolo, c=cpl))
            problemi = margin_problems(st["size"], m)
            righe = []
            msg = {
                "too_small": self._t_or(
                    "ps_err_too_small", "Un margine e' sotto i {n} mm: "
                    "molte stampanti lo taglierebbero.").format(
                        n=int(MARGIN_MIN_MM)),
                "too_large": self._t_or(
                    "ps_err_too_large",
                    "Un margine supera il massimo consentito."),
                "too_narrow": self._t_or(
                    "ps_err_too_narrow", "La gabbia del testo e' troppo "
                    "stretta: riduci i margini laterali."),
                "too_short": self._t_or(
                    "ps_err_too_short", "La gabbia del testo e' troppo "
                    "bassa: riduci i margini superiore e inferiore."),
            }
            for codice in problemi:
                righe.append("\u26a0 " + msg[codice])
            if not problemi:
                lo, hi = CPL_COMFORT
                if cpl > hi:
                    righe.append("\u2139 " + self._t_or(
                        "ps_cpl_long", "Righe lunghe: oltre {n} battute "
                        "l'occhio fatica a ritrovare l'inizio della riga "
                        "successiva.").format(n=hi))
                elif cpl < lo:
                    righe.append("\u2139 " + self._t_or(
                        "ps_cpl_short", "Righe corte: sotto {n} battute il "
                        "testo si spezzetta e la giustificazione allarga gli "
                        "spazi.").format(n=lo))
            warn.set_markup(GLib.markup_escape_text("\n".join(righe)))
            warn.set_visible(bool(righe))
            b_ok.set_sensitive(not problemi)

        def on_spin(sp, chiave):
            if st["busy"]:
                return
            _c, per, _cf, _p = unit_info()
            margins()[chiave] = round(sp.get_value() * per, 2)
            st["busy"] = True
            dd_preset.set_selected(preset_codes.index(
                which_margin_preset(st["size"], margins())))
            st["busy"] = False
            refresh()

        for chiave, sp in spins.items():
            sp.connect("value-changed", on_spin, chiave)

        def on_mirror(btn):
            if st["busy"]:
                return
            margins()["mirror"] = btn.get_active()
            st["busy"] = True
            dd_preset.set_selected(preset_codes.index(
                which_margin_preset(st["size"], margins())))
            st["busy"] = False
            refresh()
        chk_mirror.connect("toggled", on_mirror)

        def on_preset(dd, _p):
            if st["busy"]:
                return
            codice = preset_codes[dd.get_selected()]
            if codice == MARGIN_PRESET_CUSTOM:
                return          # "personalizzati" si ottiene modificando
            work[st["size"]] = margin_preset(codice, st["size"])
            load_spins()
            refresh()
        dd_preset.connect("notify::selected", on_preset)

        def on_size(dd, _p):
            st["size"] = sizes[dd.get_selected()]
            load_spins()
            refresh()
        dd_size.connect("notify::selected", on_size)

        def on_unit(dd, _p):
            st["unit"] = unit_codes[dd.get_selected()]
            load_spins()
            refresh()
        dd_unit.connect("notify::selected", on_unit)

        # --- pulsanti ---------------------------------------------------------
        b_ok, b_cancel = self._ok_cancel_row(
            box, lambda *_a: finish(True), lambda *_a: finish(False),
            ok_label=self._t_or("ps_export", "Esporta PDF\u2026")
            if for_export else self._t_or("ps_apply", "Applica"),
            with_cancel=True)

        def commit():
            """Salva formato e margini: il formato nelle impostazioni del
            programma, i margini nel documento."""
            cambiati = False
            for size_key, m in work.items():
                prima = self.project.page_margins(size_key)
                dopo = self.project.set_page_margins(size_key, m)
                if prima != dopo:
                    cambiati = True
            if cambiati:
                self._mark_dirty()
            self._pdf_page_size = st["size"]
            self.settings["pdf_page_size"] = st["size"]
            self.settings["page_unit"] = st["unit"]
            if for_export:
                self._pdf_justify = bool(opts["justify"].get_active())
                self._pdf_hyphenate = bool(
                    opts["hyphenate"].get_active()) and hyphenation_available(
                        getattr(self, "lang", "it"))
                self.settings["pdf_justify"] = self._pdf_justify
                self.settings["pdf_hyphenate"] = self._pdf_hyphenate
            try:
                save_settings(self.settings)
            except Exception:
                pass

        def finish(ok):
            if st["done"]:
                return
            st["done"] = True
            if ok:
                commit()
            dialog.destroy()
            if ok and for_export:
                GLib.idle_add(lambda: (self._save_file_dialog(
                    self.t("dlg_export_pdf_title"),
                    f"{self.project.title}.pdf", ["*.pdf"],
                    self.t("filter_pdf"), self._do_export_pdf), False)[1])

        def on_close_req(*_):
            finish(False)
            return False
        dialog.connect("close-request", on_close_req)

        load_spins()
        refresh()
        # riferimenti per i test automatici dell'interfaccia
        self._page_setup_widgets = {
            "dialog": dialog, "size": dd_size, "preset": dd_preset,
            "mirror": chk_mirror, "unit": dd_unit, "spins": spins,
            "labels": side_labels, "info": info, "warn": warn, "ok": b_ok,
            "cancel": b_cancel, "area": area, "work": work}
        self._dialog_present(dialog, box, b_ok)

    def _do_export_pdf(self, path):
        if not path.endswith(".pdf"):
            path += ".pdf"
        try:
            # Per i documenti esportati usiamo un serif da lettura (EB Garamond),
            # piu' adatto di un monospace come il Courier Prime dell'editor.
            here = ASSETS_DIR
            embed_fonts = {}
            fname = None
            # 1) carattere scelto da chi scrive, se e' una famiglia di sistema
            scelto = getattr(self, "doc_font", "")
            # i due caratteri incorporati si riconoscono per nome e si
            # prendono dalla cartella assets, senza cercarli nel sistema
            incorporati = {SERIF_FAMILY: SERIF_FILES,
                           _TW_FAMILY: TYPEWRITER_FILES}
            if scelto in incorporati:
                for style, ffile in incorporati[scelto].items():
                    metrics = read_ttf_metrics(os.path.join(here, ffile))
                    if metrics:
                        embed_fonts[style] = metrics
                if "regular" in embed_fonts:
                    fname = scelto.replace(" ", "")
                else:
                    embed_fonts = {}
            elif scelto:
                for style, ffile in font_files_for_family(scelto).items():
                    metrics = read_ttf_metrics(ffile)
                    if metrics:
                        embed_fonts[style] = metrics
                if "regular" in embed_fonts:
                    # il nome dentro il PDF non ammette spazi
                    fname = scelto.replace(" ", "")
                else:
                    embed_fonts = {}
            # 2) altrimenti il serif da lettura incorporato
            if not embed_fonts:
                for style, ffile in SERIF_FILES.items():
                    metrics = read_ttf_metrics(os.path.join(here, ffile))
                    if metrics:
                        embed_fonts[style] = metrics
                if "regular" in embed_fonts:
                    fname = "EBGaramond"
            if "regular" not in embed_fonts:
                # ripiego: se i .ttf del serif non ci sono, prova il Courier Prime
                embed_fonts = {}
                for style, ffile in TYPEWRITER_FILES.items():
                    metrics = read_ttf_metrics(os.path.join(here, ffile))
                    if metrics:
                        embed_fonts[style] = metrics
                fname = "CourierPrime"
                if "regular" not in embed_fonts:
                    embed_fonts = None
            self.project.export_pdf(path, font_size=self.font_size,
                                    embed_fonts=embed_fonts, embed_font_name=fname,
                                    page_size=getattr(self, "_pdf_page_size",
                                                      PDF_DEFAULT_PAGE_SIZE),
                                    justify=getattr(self, "_pdf_justify", False),
                                    hyphenate=getattr(self, "_pdf_hyphenate", False),
                                    hyphen_lang=getattr(self, "lang", "it"),
                                    margins=self.project.page_margins(
                                        getattr(self, "_pdf_page_size",
                                                PDF_DEFAULT_PAGE_SIZE)))
            self._info(self.t("exported", p=path))
        except Exception as exc:
            self._error(self.t("err_export", e=exc))

    def on_export_epub(self, *_):
        self._export_simple("epub", "filter_epub", self.project.export_epub,
                            title_key="dlg_export_epub_title")

    def _export_simple(self, ext, filter_key, method, title_key="export"):
        """Esporta in un formato che non chiede altre scelte all'utente.

        Sette export su otto seguono la stessa sequenza: chiedi dove salvare,
        aggiungi l'estensione se manca, esporta, avvisa dell'esito. Sta qui una
        volta sola; PDF e HTML, che prima del salvataggio fanno domande in piu',
        restano a parte."""
        self._commit_current()

        def on_path(path):
            if not path.endswith("." + ext):
                path += "." + ext
            try:
                method(path)
                self._info(self.t("exported", p=path))
            except Exception as exc:
                self._error(self.t("err_export", e=exc))

        self._save_file_dialog(self.t(title_key),
                               f"{self.project.title}.{ext}",
                               [f"*.{ext}"] if filter_key else None,
                               self.t(filter_key) if filter_key else None,
                               on_path)

    def on_export_markdown(self, *_):
        self._export_simple("md", "filter_md", self.project.export_markdown)

    def _page_size_now(self):
        size = getattr(self, "_pdf_page_size", PDF_DEFAULT_PAGE_SIZE)
        return size if size in PDF_PAGE_SIZES else PDF_DEFAULT_PAGE_SIZE

    # ODT e DOCX portano lo stesso formato e gli stessi margini del PDF, cosi'
    # il libro si apre in LibreOffice o in Word gia' impaginato
    def on_export_odt(self, *_):
        self._export_simple("odt", "filter_odt", lambda path:
                            self.project.export_odt(
                                path, page_size=self._page_size_now()))

    def on_export_docx(self, *_):
        self._export_simple("docx", "filter_docx", lambda path:
                            self.project.export_docx(
                                path, page_size=self._page_size_now()))

    def on_export_azw3(self, *_):
        self._export_simple("azw3", "filter_azw3", self.project.export_azw3)

    def on_export_html(self, *_):
        self._commit_current()

        def choice(idx):
            # 0 = singolo, 1 = multi, 2 = annulla
            if idx == 2 or idx < 0:
                return
            multifile = (idx == 1)

            def on_path(path):
                if not multifile and not path.endswith(".html"):
                    path += ".html"
                try:
                    out = self.project.export_html(path, multifile=multifile)
                    self._info(self.t("exported", p=out))
                except Exception as exc:
                    self._error(self.t("err_export", e=exc))

            if multifile:
                self._save_file_dialog(self.t("export"), self.project.title,
                                       None, None, on_path)
            else:
                self._save_file_dialog(self.t("export"),
                                       f"{self.project.title}.html", ["*.html"],
                                       self.t("filter_html"), on_path)

        self._confirm(self.t("html_mode_title"), self.t("html_mode_body"),
                      [self.t("html_single"), self.t("html_multi"),
                       self.t("cancel")],
                      default_idx=0, cancel_idx=2, on_choice=choice)

    # ---- avvio --------------------------------------------------------------
    def _startup_dialog(self):
        if getattr(self, "_opened_from_file", False):
            return False

        def chosen(rid):
            if rid == "open":
                self.on_open()
            elif rid == "new":
                self.on_new()
        self._alert(APP_NAME, self.t("startup_secondary"),
                    (("open", self.t("startup_open")), ("new", self.t("startup_new"))),
                    "new", None, chosen)
        return False

    # ---- utilita' -----------------------------------------------------------
    def _current_row(self):
        sel = self.list_selection.get_selected()
        if sel == Gtk.INVALID_LIST_POSITION:
            return -1
        return sel

    def _current_index(self):
        """Indice in project.chapters del capitolo selezionato (-1 se nessuno)."""
        row = self._current_row()
        if row < 0:
            return -1
        return self._row_to_index(row)


class RuscaWriterApp(Adw.Application):
    def __init__(self):
        super().__init__(application_id=APP_ID,
                         flags=Gio.ApplicationFlags.HANDLES_OPEN)
        self.win = None

    def do_startup(self):
        Adw.Application.do_startup(self)
        if not theme_has_icon():
            ensure_icon()
        # Tema comune RuscaLinux; se manca restano i colori di GNOME.
        if os.path.isfile(STYLE_SRC):
            provider = Gtk.CssProvider()
            provider.load_from_path(STYLE_SRC)
            Gtk.StyleContext.add_provider_for_display(
                Gdk.Display.get_default(), provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)
        Adw.StyleManager.get_default().connect("notify::dark", lambda *_a: self.update_theme())
        self.connect("window-added", lambda *_a: self.update_theme())
        self.set_accels_for_action("window.close", ["<Control>w"])

    def update_theme(self):
        dark = Adw.StyleManager.get_default().get_dark()
        for window in self.get_windows():
            window.remove_css_class("rusca-light" if dark else "rusca-dark")
            window.add_css_class("rusca-dark" if dark else "rusca-light")

    def do_activate(self):
        if self.win is None:
            self.win = RuscaWriterWindow(self)
        self.win.present()

    def do_open(self, files, _n, _hint):
        path = files[0].get_path() if files else None
        if self.win is None:
            self.win = RuscaWriterWindow(self)
        if path:
            self.win._opened_from_file = True
            GLib.idle_add(lambda: (self.win._do_open(path), False)[1])
        self.win.present()


def main():
    # Sotto X11 la classe della finestra viene dal nome del programma: uguale
    # all'APP_ID, GNOME abbina la finestra al suo .desktop e alla sua icona.
    GLib.set_prgname(APP_ID)
    # Anche le voci di GTK (Taglia, Copia, Incolla...) nella lingua
    # dell'interfaccia, che e' quella del sistema.
    apply_toolkit_language(detect_system_language())
    app = RuscaWriterApp()
    return app.run(sys.argv)


if __name__ == "__main__":
    main()
