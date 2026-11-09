#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
RuscaMark 1.99.2 — Editor professionale Markdown in Python + GTK4 + libadwaita
Autore : Nunzio Curcuruto
Sito   : https://www.ruscalinux.org
Licenza: GPL-3.0 — https://www.gnu.org/licenses/gpl-3.0.html

Resa live della formattazione, pagina centrata che segue la larghezza
della finestra, controllo ortografico live (libspelling / GSpell 2) con
elisioni it/fr, motore Markdown integrato (tabelle, immagini, liste di
attività, note a piè di pagina, link a riferimento, evidenziato), export
HTML e PDF nello stile delle guide RuscaLinux, interfaccia nelle 26 lingue
ufficiali RuscaLinux tramite la cartella lang/ (i18n integrato in questo
file: niente più i18n.py).

Privacy: tutta l'elaborazione è locale. L'anteprima non scarica mai
immagini remote e l'export HTML non contatta alcun server.
"""
import os
import re
import sys
import json
import html
import signal
import shutil
import base64
import mimetypes
import unicodedata
import urllib.parse
import gi
gi.require_version('Gtk', '4.0')
gi.require_version('Gdk', '4.0')
gi.require_version('Adw', '1')
from gi.repository import Adw, Gtk, Gdk, Gio, GLib, Pango, GdkPixbuf

# Motore Markdown comune dei RuscaLinux OS Tools (CommonMark, specifiche
# sezione 1.2), identico in RuscaLLama, RuscaMark e RuscaWriter: si modifica
# una volta e si copia. Formule LaTeX -> simboli Unicode (E = mc², ≈, √…).
from markdown_it.tree import SyntaxTreeNode
from rusca_markdown import parser as md_parser, latex_to_pango, plain_text as _pango_plain
from rusca_markdown import parse_source, link_label_end, inline_mapper
# Export PDF: GtkPrintOperation + PangoCairo (pacchetto python3-gi-cairo).
try:
    gi.require_foreign("cairo")
    gi.require_version("PangoCairo", "1.0")
    from gi.repository import PangoCairo
    import cairo
    HAVE_PDF = True
except Exception:
    PangoCairo = None
    cairo = None
    HAVE_PDF = False
try:
    gi.require_version('GtkSource', '5')
    from gi.repository import GtkSource
    HAS_GSV = True
except Exception:
    HAS_GSV = False
# ----------------------------------------------------------------------------
# Controllo ortografico live per GTK 4 (metodo RuscaWriter)
# ----------------------------------------------------------------------------
SPELL_BACKEND = None
Spelling = None
Gspell = None
try:
    gi.require_version("Spelling", "1")
    from gi.repository import Spelling
    SPELL_BACKEND = "spelling"
except Exception:
    Spelling = None
if SPELL_BACKEND is None:
    try:
        gi.require_version("Gspell", "2")
        from gi.repository import Gspell
        SPELL_BACKEND = "gspell2"
    except Exception:
        Gspell = None
HAVE_SPELL = SPELL_BACKEND is not None
HAS_FILEDIALOG = hasattr(Gtk, "FileDialog")
# ----------------------------------------------------------------------------
# i18n integrato (ex i18n.py): le lingue dei RuscaLinux OS Tools (specifiche,
# sezione 9). LANGUAGES da' il nome di ciascuna; e' tradotta se c'e' il suo
# file lang/<codice>.json (language_available).
# Regole (SPECIFICHE-RUSCALINUX-OS-TOOLS.md):
#   - le traduzioni stanno in lang/<codice>.json (UTF-8);
#   - fallback: inglese; se una chiave manca anche in inglese si mostra la
#     chiave grezza, senza mai andare in crash;
#   - inglese e italiano sono sempre presenti: oltre ai JSON sono incorporati
#     qui sotto, così il programma funziona anche senza cartella lang/;
#   - nessun en_GB.json per l'interfaccia (en_GB serve solo all'ortografia).
# Ordine di ricerca dei JSON: ~/.config/ruscamark/lang (personalizzazioni),
# <cartella del programma>/lang, /usr/share/ruscamark/lang.
# ----------------------------------------------------------------------------
LANGUAGES = {
    "en":    ("English", "English"),
    "zh_CN": ("中文（简体）", "Simplified Chinese"),
    "es":    ("Español", "Spanish"),
    "hi":    ("हिन्दी", "Hindi"),
    "ar":    ("العربية", "Arabic"),
    "pt_BR": ("Português (Brasil)", "Brazilian Portuguese"),
    "ru":    ("Русский", "Russian"),
    "ja":    ("日本語", "Japanese"),
    "de":    ("Deutsch", "German"),
    "fr":    ("Français", "French"),
    "it":    ("Italiano", "Italian"),
    "ko":    ("한국어", "Korean"),
    "id":    ("Bahasa Indonesia", "Indonesian"),
    "tr":    ("Türkçe", "Turkish"),
    "pl":    ("Polski", "Polish"),
    "nl":    ("Nederlands", "Dutch"),
    "uk":    ("Українська", "Ukrainian"),
    "cs":    ("Čeština", "Czech"),
    "vi":    ("Tiếng Việt", "Vietnamese"),
    "sv":    ("Svenska", "Swedish"),
    "ro":    ("Română", "Romanian"),
    "hu":    ("Magyar", "Hungarian"),
    "el":    ("Ελληνικά", "Greek"),
    "fi":    ("Suomi", "Finnish"),
    "zh_TW": ("中文（繁體）", "Traditional Chinese"),
    "pt_PT": ("Português (Portugal)", "Portuguese (Portugal)"),
}
RTL_LANGUAGES = {"ar"}
# Ripieghi fra lingue vicine (specifiche, sezione 9.2): Hong Kong e Macao
# usano il cinese tradizionale, Singapore il semplificato; il portoghese
# senza variante legge il brasiliano, lo slovacco il ceco.
_LOCALE_ALIASES = {"zh_HK": "zh_TW", "zh_MO": "zh_TW", "zh_SG": "zh_CN", "zh": "zh_CN",
                   "pt": "pt_BR", "sk": "cs"}
_PROGRAM_DIR = os.path.dirname(os.path.abspath(__file__))
LANG_DIRS = (
    os.path.join(os.environ.get("XDG_CONFIG_HOME") or os.path.expanduser("~/.config"),
                 "ruscamark", "lang"),
    os.path.join(_PROGRAM_DIR, "lang"),
    "/usr/share/ruscamark/lang",
)

_BUILTIN_STRINGS = {
    'en': {
        '__lang__': 'en',
        '__name__': 'English',
        'mi_new': 'New',
        'mi_open': 'Open/Import Markdown…',
        'mi_save': 'Save/Export Markdown',
        'mi_save_as': 'Save As…',
        'mi_export_html': 'Export HTML…',
        'mi_export_pdf': 'Export PDF…',
        'mi_live': 'Live rendering',
        'mi_preview': 'Preview',
        'mi_fullscreen': 'Full screen',
        'mi_preferences': 'Preferences…',
        'mi_goal': 'Word goal…',
        'mi_spell': 'Spell checking',
        'mi_find': 'Find…',
        'mi_replace': 'Find and replace…',
        'mi_about': 'About RuscaMark',
        'mi_quit': 'Quit',
        'tip_new': 'New',
        'tip_open': 'Open/Import Markdown',
        'tip_save': 'Save/Export Markdown',
        'tip_preview': 'Preview (Ctrl+P)',
        'tip_spell_on': 'Spell checking on (F7 to turn off)',
        'tip_spell_off': 'Spell checking off (F7 to turn on)',
        'st_counts': 'Words: {w} · Characters: {c} · Lines: {l}',
        'st_cursor': 'Ln {ln}, Col {col}',
        'goal_tip': 'Set a word goal',
        'goal_label': '🎯 {w}/{g}',
        'goal_missing': '{n} words to go',
        'goal_done': '✅ Goal reached!',
        'goal_idle': '🎯 Goal',
        'goal_pop_title': 'Word goal (0 = disabled)',
        'btn_apply': 'Set',
        'find_placeholder': 'Find…',
        'replace_placeholder': 'Replace with…',
        'tip_case': 'Match case',
        'tip_prev': 'Previous',
        'tip_next': 'Next (Enter)',
        'btn_replace': 'Replace',
        'btn_replace_all': 'All',
        'tip_replace_all': 'Replace all',
        'tip_close': 'Close (Esc)',
        'st_results': '{n} matches',
        'st_no_results': 'No matches',
        'st_replaced': 'Replaced {n} occurrences',
        'spell_title': 'Spell checking',
        'spell_on': 'Spelling on',
        'spell_off': 'Spelling off',
        'spell_toggle_tip': 'Turns live spell underlining on or off',
        'spell_hide_tip': 'Hide the bar (state unchanged)',
        'spell_live': 'Live spelling on ({backend}, {loc}): underlining as you type, right-click for suggestions.',
        'spell_disabled': 'Spell checking off: turn it back on from the button or F7.',
        'spell_no_backend': 'Spell checking unavailable: {e} — install gir1.2-spelling-1.',
        'spell_inactive': 'Live checking not active: {e}',
        'pref_live': 'Live rendering of formatting',
        'pref_center': 'Centred page',
        'pref_width': 'Page width (characters)',
        'pref_spacing': 'Line spacing',
        'spacing_compact': 'Compact',
        'spacing_normal': 'Normal',
        'spacing_airy': 'Airy',
        'pref_font': 'System font',
        'pref_size': 'Size',
        'btn_cancel': 'Cancel',
        'btn_ok': 'OK',
        'btn_close': 'Close',
        'unsaved_title': 'Unsaved changes',
        'unsaved_open': 'Save the changes to "{name}" before continuing?',
        'unsaved_close': 'Save the changes before quitting?',
        'btn_nosave': "Don't save",
        'btn_save': 'Save',
        'btn_save_exit': 'Save and quit',
        'err_open': 'Cannot open the file:\n{e}',
        'err_save': 'Cannot save the file:\n{e}',
        'err_export': 'Export error:\n{e}',
        'export_footer': '{title} - page {page} / {pages}',
        'title_untitled': 'Untitled',
        'about_desc': 'Professional Markdown editor with live rendering of formatting, centred writing page, live spell checking with suggestions and word goal.',
        'about_license': 'License',
        'mi_bold': 'Bold',
        'mi_italic': 'Italic',
        'mi_link': 'Insert link…',
        'mi_image': 'Insert image…',
        'mi_table': 'Insert/align table',
        'mi_heading': 'Heading',
        'mi_heading_n': 'Heading {n}',
        'mi_paragraph': 'Normal text',
        'filter_markdown': 'Markdown files',
        'filter_images': 'Images',
        'filter_all': 'All files',
        'default_name': 'document',
        'html_default_title': 'Markdown document',
        'pref_embed': 'Embed images in HTML export',
        'tbl_col': 'Column {n}',
        'link_text': 'link text',
        'img_remote': 'Remote image not loaded: {alt}',
        'img_missing': 'Image not found: {src}',
        'fn_title': 'Notes',
        'spell_err_nobackend': 'no live backend compatible with GTK 4 (install gir1.2-spelling-1)',
        'spell_err_needs_gsv': 'libspelling requires GtkSourceView 5 (install gir1.2-gtksource-5)',
        'spell_err_dict': "dictionary '{loc}' not found",
        'spell_err_checker': 'cannot create the libspelling checker',
        'sample_title': 'Welcome to RuscaMark',
        'sample_tagline': 'Markdown editor with *live rendering*',
        'sample_h_live': 'Writing with instant rendering',
        'sample_l1': 'Formatting is applied **as you type**',
        'sample_l2': 'Markers disappear: *italic*, ~~strikethrough~~, `inline code`, ==highlight==',
        'sample_l3': 'Move the cursor onto an element and its syntax reappears for editing',
        'sample_l4': 'The page stays **centred**, even on wide screens',
        'sample_l5': 'Spelling is **live**: underlined as you type, right-click for suggestions',
        'sample_quote': 'Live rendering (**Ctrl+L**) and the classic preview (**Ctrl+P**) are mutually exclusive: turning one on turns the other off.',
        'sample_h_table': 'Tables, tasks and notes',
        'sample_tc1': 'Shortcut',
        'sample_tc2': 'Action',
        'sample_t_table': 'Insert or align a table',
        'sample_task1': 'Write the first draft',
        'sample_task2': 'Check the spelling',
        'sample_fn': 'Press F7 to turn spell checking on or off.',
        'sample_h_code': 'Code block',
        'sample_code': 'Hello from RuscaMark!',
        'sample_s1': 'Open a file with **Ctrl+O**',
        'sample_s2': 'Save with **Ctrl+S**',
        'sample_s3': 'Updates on [ruscalinux.org](https://ruscalinux.org)',
        'shortcuts': 'Keyboard Shortcuts',
        'main_menu': 'Main Menu',
        'sc_close': 'Close Window',
        'about_website': 'Website',
        'about_support': 'Support',
        'dev_note_title': 'Development Note',
        'ai_note': 'Design, specifications and testing by the author; code written with the assistance of AI tools.',
        'mi_format': 'Format',
        'pref_group_look': 'Appearance',
        'pref_group_writing': 'Writing',
        'pref_group_export': 'Export',
        'pref_style': 'Style',
        'style_system': 'Follow System',
        'style_light': 'Light',
        'style_dark': 'Dark',
        'toast_html_done': 'HTML exported',
        'toast_pdf_done': 'PDF exported',
        'btn_open_file': 'Open',
        'sc_group_file': 'File',
        'sc_group_edit': 'Editing',
        'sc_group_view': 'View',
        'app_summary': 'Write Markdown with live formatting',
        'desktop_keywords': 'Markdown;editor;text;writing;notes;',
    },
    'it': {
        '__lang__': 'it',
        '__name__': 'Italiano',
        'mi_new': 'Nuovo',
        'mi_open': 'Apri/Importa Markdown…',
        'mi_save': 'Salva/Esporta Markdown',
        'mi_save_as': 'Salva con nome…',
        'mi_export_html': 'Esporta HTML…',
        'mi_export_pdf': 'Esporta PDF…',
        'mi_live': 'Resa live',
        'mi_preview': 'Anteprima',
        'mi_fullscreen': 'Schermo intero',
        'mi_preferences': 'Preferenze…',
        'mi_goal': 'Obiettivo parole…',
        'mi_spell': 'Controllo ortografico',
        'mi_find': 'Trova…',
        'mi_replace': 'Trova e sostituisci…',
        'mi_about': 'Informazioni su RuscaMark',
        'mi_quit': 'Esci',
        'tip_new': 'Nuovo',
        'tip_open': 'Apri/Importa Markdown',
        'tip_save': 'Salva/Esporta Markdown',
        'tip_preview': 'Anteprima (Ctrl+P)',
        'tip_spell_on': 'Controllo ortografico attivo (F7 per spegnere)',
        'tip_spell_off': 'Controllo ortografico spento (F7 per accendere)',
        'st_counts': 'Parole: {w} · Caratteri: {c} · Righe: {l}',
        'st_cursor': 'Ln {ln}, Col {col}',
        'goal_tip': 'Imposta un obiettivo di parole',
        'goal_label': '🎯 {w}/{g}',
        'goal_missing': 'mancano {n} parole',
        'goal_done': '✅ Obiettivo raggiunto!',
        'goal_idle': '🎯 Obiettivo',
        'goal_pop_title': 'Obiettivo parole (0 = disattivato)',
        'btn_apply': 'Imposta',
        'find_placeholder': 'Trova…',
        'replace_placeholder': 'Sostituisci con…',
        'tip_case': 'Rispetta maiuscole/minuscole',
        'tip_prev': 'Precedente',
        'tip_next': 'Successivo (Invio)',
        'btn_replace': 'Sostituisci',
        'btn_replace_all': 'Tutti',
        'tip_replace_all': 'Sostituisci tutto',
        'tip_close': 'Chiudi (Esc)',
        'st_results': '{n} risultati',
        'st_no_results': 'Nessun risultato',
        'st_replaced': 'Sostituite {n} occorrenze',
        'spell_title': 'Controllo ortografico',
        'spell_on': 'Ortografia attiva',
        'spell_off': 'Ortografia spenta',
        'spell_toggle_tip': 'Accende o spegne la sottolineatura ortografica live',
        'spell_hide_tip': 'Nascondi la barra (lo stato non cambia)',
        'spell_live': 'Ortografia live attiva ({backend}, {loc}): sottolineatura durante la scrittura, tasto destro per i suggerimenti.',
        'spell_disabled': 'Controllo ortografico disattivato: riaccendilo dal pulsante o con F7.',
        'spell_no_backend': 'Controllo ortografico non disponibile: {e} — installa gir1.2-spelling-1.',
        'spell_inactive': 'Controllo live non attivo: {e}',
        'pref_live': 'Resa live della formattazione',
        'pref_center': 'Pagina centrata',
        'pref_width': 'Larghezza pagina (caratteri)',
        'pref_spacing': 'Interlinea',
        'spacing_compact': 'Compatta',
        'spacing_normal': 'Normale',
        'spacing_airy': 'Ariosa',
        'pref_font': 'Font di sistema',
        'pref_size': 'Dimensione',
        'btn_cancel': 'Annulla',
        'btn_ok': 'OK',
        'btn_close': 'Chiudi',
        'unsaved_title': 'Modifiche non salvate',
        'unsaved_open': 'Vuoi salvare le modifiche a "{name}" prima di continuare?',
        'unsaved_close': 'Vuoi salvare le modifiche prima di uscire?',
        'btn_nosave': 'Non salvare',
        'btn_save': 'Salva',
        'btn_save_exit': 'Salva ed esci',
        'err_open': 'Impossibile aprire il file:\n{e}',
        'err_save': 'Impossibile salvare il file:\n{e}',
        'err_export': "Errore nell'esportazione:\n{e}",
        'export_footer': '{title} - pag. {page} / {pages}',
        'title_untitled': 'Senza titolo',
        'about_desc': 'Editor professionale Markdown con resa live della formattazione, pagina centrata per la scrittura, controllo ortografico live con suggerimenti e obiettivo parole.',
        'about_license': 'Licenza',
        'mi_bold': 'Grassetto',
        'mi_italic': 'Corsivo',
        'mi_link': 'Inserisci link…',
        'mi_image': 'Inserisci immagine…',
        'mi_table': 'Inserisci/allinea tabella',
        'mi_heading': 'Titolo',
        'mi_heading_n': 'Titolo {n}',
        'mi_paragraph': 'Testo normale',
        'filter_markdown': 'File Markdown',
        'filter_images': 'Immagini',
        'filter_all': 'Tutti i file',
        'default_name': 'documento',
        'html_default_title': 'Documento Markdown',
        'pref_embed': "Incorpora le immagini nell'export HTML",
        'tbl_col': 'Colonna {n}',
        'link_text': 'testo del link',
        'img_remote': 'Immagine remota non caricata: {alt}',
        'img_missing': 'Immagine non trovata: {src}',
        'fn_title': 'Note',
        'spell_err_nobackend': 'nessun backend live compatibile con GTK 4 (installa gir1.2-spelling-1)',
        'spell_err_needs_gsv': 'libspelling richiede GtkSourceView 5 (installa gir1.2-gtksource-5)',
        'spell_err_dict': "dizionario '{loc}' non trovato",
        'spell_err_checker': 'impossibile creare il checker libspelling',
        'sample_title': 'Benvenuto in RuscaMark',
        'sample_tagline': 'Editor Markdown con *resa live*',
        'sample_h_live': 'Scrittura con resa immediata',
        'sample_l1': 'Mentre scrivi, la formattazione si applica **da sola**',
        'sample_l2': 'I marcatori spariscono: *corsivo*, ~~barrato~~, `codice inline`, ==evidenziato==',
        'sample_l3': 'Porta il cursore su un elemento: la sintassi riappare per modificarla',
        'sample_l4': 'La pagina resta **centrata**, anche sugli schermi larghi',
        'sample_l5': "L'ortografia è **live**: sottolineatura mentre scrivi, tasto destro per i suggerimenti",
        'sample_quote': "La resa live (**Ctrl+L**) e l'anteprima classica (**Ctrl+P**) si escludono a vicenda: accendendone una, l'altra si spegne.",
        'sample_h_table': 'Tabelle, attività e note',
        'sample_tc1': 'Scorciatoia',
        'sample_tc2': 'Azione',
        'sample_t_table': 'Inserisci o allinea una tabella',
        'sample_task1': 'Scrivere la prima bozza',
        'sample_task2': "Controllare l'ortografia",
        'sample_fn': 'Premi F7 per accendere o spegnere il controllo ortografico.',
        'sample_h_code': 'Blocco di codice',
        'sample_code': 'Ciao da RuscaMark!',
        'sample_s1': 'Apri un file con **Ctrl+O**',
        'sample_s2': 'Salva con **Ctrl+S**',
        'sample_s3': 'Aggiornamenti su [ruscalinux.org](https://ruscalinux.org)',
        'shortcuts': 'Scorciatoie da tastiera',
        'main_menu': 'Menu principale',
        'sc_close': 'Chiudi finestra',
        'about_website': 'Sito web',
        'about_support': 'Supporto',
        'dev_note_title': 'Nota di sviluppo',
        'ai_note': 'Progettazione, specifiche e verifica dell’autore; codice scritto con l’assistenza di strumenti di intelligenza artificiale.',
        'mi_format': 'Formato',
        'pref_group_look': 'Aspetto',
        'pref_group_writing': 'Scrittura',
        'pref_group_export': 'Esportazione',
        'pref_style': 'Stile',
        'style_system': 'Segui il sistema',
        'style_light': 'Chiaro',
        'style_dark': 'Scuro',
        'toast_html_done': 'HTML esportato',
        'toast_pdf_done': 'PDF esportato',
        'btn_open_file': 'Apri',
        'sc_group_file': 'File',
        'sc_group_edit': 'Modifica',
        'sc_group_view': 'Visualizza',
        'app_summary': 'Scrivi in Markdown con la formattazione dal vivo',
        'desktop_keywords': 'Markdown;editor;testo;scrittura;note;',
    },
}



_lang_cache = {}


def _read_lang_json(path):
    """Legge un catalogo; {} se mancante, corrotto o scheletro ('__comment__')."""
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
    except Exception:
        return {}
    if not isinstance(data, dict) or "__comment__" in data:
        return {}
    return {k: v for k, v in data.items()
            if isinstance(k, str) and isinstance(v, str) and not k.startswith("__")}


def _lang_json(code):
    if code not in _lang_cache:
        data = {}
        for d in LANG_DIRS:
            p = os.path.join(d, f"{code}.json")
            if os.path.isfile(p):
                data = _read_lang_json(p)
                if data:
                    break
        _lang_cache[code] = data
    return _lang_cache[code]


def load_language(code):
    """Cascata: en incorporato → en.json → lingua incorporata → <lingua>.json."""
    data = dict(_BUILTIN_STRINGS["en"])
    data.update(_lang_json("en"))
    if code != "en":
        data.update(_BUILTIN_STRINGS.get(code, {}))
        data.update(_lang_json(code))
    return data


def language_available(code):
    return code in _BUILTIN_STRINGS or bool(_lang_json(code))


def available_languages():
    """[(codice, nome nativo, tradotta?)] — prima le lingue tradotte."""
    items = [(c, n[0], language_available(c)) for c, n in LANGUAGES.items()]
    items.sort(key=lambda x: (not x[2], x[1].lower()))
    return items


def detect_system_language():
    # Le lingue di sistema nell'ordine di GTK (specifiche, sezione 9.2):
    # prima LANGUAGE, poi LC_ALL, LC_MESSAGES, LANG. Prima si leggevano
    # nell'ordine inverso, e LANGUAGE (la variabile per scegliere la lingua
    # delle applicazioni) veniva ignorata se LANG era impostata.
    for nome in GLib.get_language_names():
        cand = nome.split(".")[0].split("@")[0]
        if not cand or cand in ("C", "POSIX"):
            continue
        base = cand.split("_")[0].lower()
        # solo lingue tradotte davvero: come negli altri programmi, se la
        # traduzione manca si prova la candidata successiva
        for code in (cand, _LOCALE_ALIASES.get(cand), base, _LOCALE_ALIASES.get(base)):
            if code in LANGUAGES and language_available(code):
                return code
    return "en"


class Translator:
    def __init__(self, code="en"):
        self.set_language(code)

    def set_language(self, code):
        self.code = code if code in LANGUAGES else "en"
        self._strings = load_language(self.code)

    def t(self, key, **kwargs):
        s = self._strings.get(key, key)
        if kwargs:
            try:
                return s.format(**kwargs)
            except Exception:
                return s
        return s

    def is_rtl(self):
        return self.code in RTL_LANGUAGES
# ----------------------------------------------------------------------------
APP_NAME    = "RuscaMark"
APP_VERSION = "1.99.2"
APP_AUTHOR  = "Nunzio Curcuruto"
APP_WEBSITE = "https://www.ruscalinux.org"
APP_ID      = "org.ruscalinux.RuscaMark"
STYLE_SRC   = next((p for p in (os.path.join(_PROGRAM_DIR, "style.css"),
                                "/usr/share/ruscamark/style.css") if os.path.isfile(p)), None)
ICON_SRC    = next((p for p in (os.path.join(_PROGRAM_DIR, "ruscamark.svg"),
                                "/usr/share/ruscamark/ruscamark.svg") if os.path.isfile(p)), None)
CONFIG_DIR  = os.path.join(GLib.get_user_config_dir(), "ruscamark")
STYLES_DIR  = os.path.join(GLib.get_user_data_dir(), "gtksourceview-5", "styles")
CONFIG_FILE = os.path.join(CONFIG_DIR, "config.json")
OLD_CONFIG_FILE = os.path.join(GLib.get_user_config_dir(), "ruscaeditor", "config.json")
DEFAULT_CONFIG = {
    # Stile: "system" segue GNOME, "light"/"dark" lo forzano.
    "style": "system", "font": "Sans", "font_size": 13,
    "goal": 0, "lang": "it_IT", "show_preview": False,
    "live": True, "center_page": True, "page_chars": 80,
    "line_spacing": "normal",      # interlinea dell'editor: compact | normal | airy
    "html_embed_images": False,    # export HTML autonomo (immagini in base64)
    "spell_on": True,              # persiste lo stato del controllo ortografico
    "spell_panel_hidden": True,    # primo avvio: pannello nascosto
    "win_w": 1240, "win_h": 800, "paned": 620,
}
# ----------------------------------------------------------------------------
# Colori di editor e anteprima, dalla palette ufficiale RuscaLinux
# (specifiche, sezione 4.1). Ogni coppia testo/sfondo ha contrasto >= 4,5:1.
LIGHT = {
    "bg": "#FBF4F7", "editor_bg": "#FFFFFF", "preview_bg": "#FBF4F7",
    "panel": "#F6E4EC", "header": "#F6E4EC", "fg": "#2D0A1D",
    "accent": "#7A2357", "accent_fg": "#FFFFFF", "accent2": "#8A2B5F",
    "subtle": "#85607A", "border": "#E6CBD8", "selection": "#F8D7E6",
    "sel_fg": "#2D0A1D", "hover": "#F6E4EC", "code_bg": "#F6E4EC",
    "code_fg": "#7A2357", "heading": "#7A2357", "link": "#7A2357",
    "quote": "#6B4A5C", "trough": "#F6E4EC", "error": "#C01C28",
}
DARK = {
    "bg": "#2D0A1D", "editor_bg": "#230716", "preview_bg": "#2D0A1D",
    "panel": "#3A1028", "header": "#3A1028", "fg": "#FFF7F0",
    "accent": "#F2A7C8", "accent_fg": "#2D0A1D", "accent2": "#F5B8D3",
    "subtle": "#C9A5B8", "border": "#5C1A40", "selection": "#7A2357",
    "sel_fg": "#FFF7F0", "hover": "#40132C", "code_bg": "#40132C",
    "code_fg": "#F5B8D3", "heading": "#F5B8D3", "link": "#F2A7C8",
    "quote": "#D8BFCB", "trough": "#40132C", "error": "#FF7B8A",
}
# Interlinea dell'editor e dell'anteprima (multipli del corpo, come in CSS).
LINE_SPACING = {"compact": 1.25, "normal": 1.5, "airy": 1.75}
# Unico CSS proprio di RuscaMark: carattere del testo e colori della pagina
# di anteprima. Barre, pulsanti, menu e dialoghi sono quelli di libadwaita,
# colorati dal tema comune style.css.
CSS_TEMPLATE = """
textview.ruscamark-editor, textview.preview { font-family: "__FONT__"; font-size: __SIZE__pt; }
textview.preview, textview.preview text { background-color: @preview_bg; color: @fg; }
"""
# Schemi colore di GtkSourceView, dalla stessa palette.
SCHEME_LIGHT = """<?xml version="1.0" encoding="UTF-8"?>
<style-scheme id="ruscamark-light" name="RuscaMark Chiaro" version="1.0">
  <author>Nunzio Curcuruto</author>
  <description>Palette RuscaLinux, chiara</description>
  <style name="text" foreground="#2D0A1D" background="#FFFFFF"/>
  <style name="selection" foreground="#2D0A1D" background="#F8D7E6"/>
  <style name="cursor" foreground="#7A2357"/>
  <style name="secondary-cursor" foreground="#8A2B5F"/>
  <style name="line-numbers" foreground="#85607A" background="#FBF4F7"/>
  <style name="right-margin" foreground="#E6CBD8" background="#FFFFFF"/>
  <style name="search-match" background="#F8D7E6"/>
  <style name="bracket-match" foreground="#7A2357" bold="true"/>
  <style name="markdown:header" foreground="#7A2357" bold="true"/>
  <style name="markdown:strong-emphasis" bold="true"/>
  <style name="markdown:emphasis" italic="true"/>
  <style name="markdown:code-span" foreground="#7A2357" background="#F6E4EC"/>
  <style name="markdown:code-block" foreground="#7A2357" background="#F6E4EC"/>
  <style name="markdown:blockquote-marker" foreground="#6B4A5C" bold="true"/>
  <style name="markdown:list-marker" foreground="#7A2357" bold="true"/>
  <style name="markdown:horizontal-rule" foreground="#85607A"/>
  <style name="markdown:url" foreground="#7A2357" underline="true"/>
  <style name="markdown:link-text" foreground="#7A2357" underline="true"/>
  <style name="markdown:image-marker" foreground="#7A2357"/>
  <style name="markdown:label" foreground="#7A2357"/>
  <style name="markdown:attribute-value" foreground="#7A2357"/>
  <style name="markdown:backslash-escape" foreground="#85607A"/>
  <style name="markdown:line-break" background="#F6E4EC"/>
</style-scheme>
"""
SCHEME_DARK = """<?xml version="1.0" encoding="UTF-8"?>
<style-scheme id="ruscamark-dark" name="RuscaMark Scuro" version="1.0">
  <author>Nunzio Curcuruto</author>
  <description>Palette RuscaLinux, scura</description>
  <style name="text" foreground="#FFF7F0" background="#230716"/>
  <style name="selection" foreground="#FFF7F0" background="#7A2357"/>
  <style name="cursor" foreground="#F2A7C8"/>
  <style name="secondary-cursor" foreground="#F5B8D3"/>
  <style name="line-numbers" foreground="#C9A5B8" background="#2D0A1D"/>
  <style name="right-margin" foreground="#5C1A40" background="#230716"/>
  <style name="search-match" background="#7A2357"/>
  <style name="bracket-match" foreground="#F2A7C8" bold="true"/>
  <style name="markdown:header" foreground="#F5B8D3" bold="true"/>
  <style name="markdown:strong-emphasis" bold="true"/>
  <style name="markdown:emphasis" italic="true"/>
  <style name="markdown:code-span" foreground="#F5B8D3" background="#40132C"/>
  <style name="markdown:code-block" foreground="#F5B8D3" background="#40132C"/>
  <style name="markdown:blockquote-marker" foreground="#D8BFCB" bold="true"/>
  <style name="markdown:list-marker" foreground="#F2A7C8" bold="true"/>
  <style name="markdown:horizontal-rule" foreground="#C9A5B8"/>
  <style name="markdown:url" foreground="#F2A7C8" underline="true"/>
  <style name="markdown:link-text" foreground="#F2A7C8" underline="true"/>
  <style name="markdown:image-marker" foreground="#F2A7C8"/>
  <style name="markdown:label" foreground="#F2A7C8"/>
  <style name="markdown:attribute-value" foreground="#F2A7C8"/>
  <style name="markdown:backslash-escape" foreground="#C9A5B8"/>
  <style name="markdown:line-break" background="#40132C"/>
</style-scheme>
"""
HEADING_SIZES = {1: "xx-large", 2: "x-large", 3: "large", 4: "large", 5: "medium", 6: "medium"}
# ----------------------------------------------------------------------------
def load_config():
    cfg = dict(DEFAULT_CONFIG)
    try:
        if not os.path.exists(CONFIG_FILE) and os.path.exists(OLD_CONFIG_FILE):
            shutil.copyfile(OLD_CONFIG_FILE, CONFIG_FILE)
    except Exception:
        pass
    try:
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            cfg.update(json.load(f))
    except Exception:
        pass
    cfg["lang"] = str(cfg.get("lang", "it_IT")).replace("-", "_")
    # Fino alla 1.99.1 "theme" valeva "light" per tutti (predefinito) o "dark"
    # se scelto: chi aveva scelto lo scuro lo conserva, gli altri seguono GNOME.
    if "theme" in cfg:
        if cfg.pop("theme") == "dark" and cfg.get("style", "system") == "system":
            cfg["style"] = "dark"
    cfg.pop("ui_lang", None)          # la lingua segue sempre il sistema
    if cfg.get("style") not in ("system", "light", "dark"):
        cfg["style"] = "system"
    return cfg

def save_config(cfg):
    try:
        os.makedirs(CONFIG_DIR, exist_ok=True)
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(cfg, f, indent=2, ensure_ascii=False)
    except Exception:
        pass

def ensure_style_schemes():
    try:
        os.makedirs(STYLES_DIR, exist_ok=True)
        for name, content in (("ruscamark-light.xml", SCHEME_LIGHT), ("ruscamark-dark.xml", SCHEME_DARK)):
            with open(os.path.join(STYLES_DIR, name), "w", encoding="utf-8") as f:
                f.write(content)
    except Exception:
        pass

def system_font_families():
    """Elenco font di sistema, compatibile con Pango nuovo e vecchio."""
    fm = None
    try:
        fm = Pango.font_map_get_default()
    except Exception:
        try:
            fm = Pango.FontMap.get_default()
        except Exception:
            fm = None
    if fm is None:
        return ["Sans", "Serif", "Monospace"]
    try:
        return sorted({f.get_name() for f in fm.list_families()})
    except Exception:
        return ["Sans", "Serif", "Monospace"]
# ----------------------------------------------------------------------------
# Markdown: analisi del motore comune (rusca_markdown.parser(), CommonMark
# con le estensioni delle specifiche, sezione 1.2). MarkdownDoc trasforma il
# suo albero nell'HTML dell'export, nell'anteprima (Pango) e negli elementi
# del PDF.
#
# Le espressioni regolari qui sotto NON analizzano il documento: servono
# all'editor per colorare il sorgente riga per riga (resa live) e ai comandi
# sulle tabelle (Ctrl+Maiusc+T). Specifiche, sezione 1.2, regola 1.
# ----------------------------------------------------------------------------
_RE_FENCE = re.compile(r"^( {0,3})(`{3,}|~{3,})[ \t]*([^`\s]*)[^`]*$")
_RE_ATX = re.compile(r"^ {0,3}(#{1,6})(?:[ \t]+(.*?))?(?:[ \t]+#+)?[ \t]*$")
_RE_HR = re.compile(r"^ {0,3}([-*_])(?:[ \t]*\1){2,}[ \t]*$")
_RE_SETEXT = re.compile(r"^ {0,3}(=+|-+)[ \t]*$")
_RE_QUOTE = re.compile(r"^ {0,3}> ?(.*)$")
_RE_LIST = re.compile(r"^( {0,3})([-*+]|\d{1,9}[.)])([ \t]+|$)(.*)$")
_RE_TABLE_SEP = re.compile(r"^ {0,3}\|?[ \t]*:?-+:?[ \t]*(\|[ \t]*:?-+:?[ \t]*)*\|?[ \t]*$")
_RE_FNDEF = re.compile(r"^ {0,3}\[\^([^\]\s]+)\]:[ \t]*(.*)$")
_RE_REFDEF = re.compile(r'^ {0,3}\[([^\]^][^\]]*)\]:[ \t]*<?([^\s>]+)>?(?:[ \t]+["\'(](.+)["\')])?[ \t]*$')
_IMG_EXT = (".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg", ".bmp", ".tif", ".tiff", ".avif")


def _display_width(s):
    """Larghezza in colonne monospazio (CJK = 2, combinanti = 0)."""
    w = 0
    for ch in s:
        if unicodedata.combining(ch):
            continue
        w += 2 if unicodedata.east_asian_width(ch) in ("W", "F") else 1
    return w


def _split_table_row(line):
    """Divide una riga di tabella in celle (rispetta \\| e i `code span`)."""
    s = line.strip()
    if s.startswith("|"):
        s = s[1:]
    if s.endswith("|") and not s.endswith("\\|"):
        s = s[:-1]
    cells, cur, in_code, i = [], [], False, 0
    while i < len(s):
        ch = s[i]
        if ch == "\\" and i + 1 < len(s) and s[i + 1] == "|":
            cur.append("|")
            i += 2
            continue
        if ch == "`":
            in_code = not in_code
        if ch == "|" and not in_code:
            cells.append("".join(cur).strip())
            cur = []
        else:
            cur.append(ch)
        i += 1
    cells.append("".join(cur).strip())
    return cells


def _is_table_start(lines, i):
    if i + 1 >= len(lines):
        return False
    head, sep = lines[i], lines[i + 1]
    if "|" not in head or "|" not in sep or not _RE_TABLE_SEP.match(sep):
        return False
    return len(_split_table_row(head)) == len(_split_table_row(sep))


def _table_aligns(sep_line):
    out = []
    for s in _split_table_row(sep_line):
        s = s.strip()
        left, right = s.startswith(":"), s.endswith(":")
        out.append("center" if left and right else "right" if right
                   else "left" if left else None)
    return out


def find_table_blocks(lines):
    """Intervalli (inizio, fine) inclusi delle tabelle, fuori dai blocchi codice."""
    out, i, n, fence = [], 0, len(lines), None
    while i < n:
        m = _RE_FENCE.match(lines[i])
        if fence:
            cl = lines[i].strip()
            if cl and set(cl) == {fence[0]} and len(cl) >= len(fence):
                fence = None
            i += 1
            continue
        if m:
            fence = m.group(2)
            i += 1
            continue
        if _is_table_start(lines, i):
            j = i + 2
            while j < n and lines[j].strip() and "|" in lines[j]:
                j += 1
            out.append((i, j - 1))
            i = j
            continue
        i += 1
    return out


def align_table_lines(lines):
    """Riallinea le colonne di una tabella Markdown (larghezza visuale)."""
    header = _split_table_row(lines[0])
    ncol = len(header)
    aligns = (_table_aligns(lines[1]) + [None] * ncol)[:ncol]
    rows = [header] + [(_split_table_row(l) + [""] * ncol)[:ncol] for l in lines[2:]]
    rows = [[c.replace("|", "\\|") for c in r] for r in rows]
    widths = [max(3, *(_display_width(r[c]) for r in rows)) for c in range(ncol)]

    def pad(text, w, al):
        gap = w - _display_width(text)
        if al == "right":
            return " " * gap + text
        if al == "center":
            return " " * (gap // 2) + text + " " * (gap - gap // 2)
        return text + " " * gap

    def sep(w, al):
        if al == "center":
            return ":" + "-" * (w - 2) + ":"
        if al == "right":
            return "-" * (w - 1) + ":"
        if al == "left":
            return ":" + "-" * (w - 1)
        return "-" * w
    out = ["| " + " | ".join(pad(r[c], widths[c], aligns[c]) for c in range(ncol)) + " |"
           for r in rows]
    out.insert(1, "| " + " | ".join(sep(widths[c], aligns[c]) for c in range(ncol)) + " |")
    return out


# ----------------------------------------------------------------------------
# Resa live: dove applicare stili e dove nascondere i marcatori.
# La struttura viene dal motore comune (parse_source: gli stessi token
# dell'anteprima e degli export, con le posizioni nel sorgente), così la resa
# live riconosce la formattazione esattamente come l'anteprima.
# ----------------------------------------------------------------------------
_RE_QUOTE_MARKS = re.compile(r"^[ \t]*(?:>[ \t]?)+")
_RE_REF_LINE = re.compile(r"^ {0,3}\[[^\]]+\]:")


_RE_TEX_SCRIPT = re.compile(r"([\^_])(\{([^{}]*)\}|\\[A-Za-z]+|[^\s{}\\])")


def _live_math(a, z, to_doc, src, out):
    """Formula fra a e z (delimitatori esclusi): stile da formula; ^ e _
    diventano esponenti e pedici (x^2, x_{i+1}), come in TeX."""
    styles = [("math", to_doc(a), to_doc(z))]
    marks = []
    for m in _RE_TEX_SCRIPT.finditer(src, a, z):
        tag = "sup" if m.group(1) == "^" else "sub"
        if m.group(3) is not None:                       # ^{…}
            body_a, body_z = m.start(3), m.end(3)
            marks += [(to_doc(m.start()), to_doc(body_a)), (to_doc(body_z), to_doc(m.end()))]
        else:                                            # ^2, ^\alpha
            body_a, body_z = m.start(2), m.end(2)
            marks.append((to_doc(m.start()), to_doc(body_a)))
        marks.append((to_doc(body_a), to_doc(body_z), tag))
    return styles, marks


def _live_inline(token, to_doc, out):
    """Elementi in linea di un paragrafo o titolo."""
    content = token.meta.get("src_content", token.content)
    for a, z in token.meta.get("escapes", []):          # \* \_ …: via la barra
        out.append((to_doc(a), to_doc(z), [], [(to_doc(a), to_doc(a + 1))]))
    stack, last = [], 0
    kinds = {"strong": "bold", "em": "italic", "s": "strike", "mark": "mark"}
    children = token.children or []
    for idx, c in enumerate(children):
        src = c.meta.get("src")
        t = c.type
        if t.endswith("_open") and t[:-5] in kinds:
            stack.append(c)
            continue
        if t.endswith("_close") and t[:-6] in kinds:
            if not stack:
                continue
            o = stack.pop()
            if "src" not in o.meta or src is None:
                continue
            n = len(c.markup)
            oa, ca = o.meta["src"][1] - n, src[0]
            a, z = to_doc(oa), to_doc(ca + n)
            out.append((a, z, [(kinds[t[:-6]], to_doc(oa + n), to_doc(ca))],
                        [(a, to_doc(oa + n)), (to_doc(ca), z)]))
            last = max(last, ca + n)
            continue
        if t == "link_open":
            if src is not None and c.markup == "autolink":            # <https://…>
                a, z = src
                out.append((to_doc(a), to_doc(z), [("link", to_doc(a + 1), to_doc(z - 1))],
                            [(to_doc(a), to_doc(a + 1)), (to_doc(z - 1), to_doc(z))]))
            elif src is not None and c.markup == "linkify":             # https://… nudo
                out.append((to_doc(src[0]), to_doc(src[1]),
                            [("link", to_doc(src[0]), to_doc(src[1]))], []))
            elif src is not None:                                       # [testo](indirizzo)
                a, z = src
                end = link_label_end(content, a)
                if end > a:
                    out.append((to_doc(a), to_doc(z), [("link", to_doc(a + 1), to_doc(end))],
                                [(to_doc(a), to_doc(a + 1)), (to_doc(end), to_doc(z))]))
            else:
                # Link automatico riconosciuto dopo l'analisi (www., email):
                # il suo testo, dopo l'ultimo elemento già trovato.
                text = children[idx + 1].content if idx + 1 < len(children) else ""
                at = content.find(text, last) if text else -1
                if at >= 0:
                    out.append((to_doc(at), to_doc(at + len(text)),
                                [("link", to_doc(at), to_doc(at + len(text)))], []))
                    last = at + len(text)
            if src is not None:
                last = max(last, src[1])
            continue
        if src is None:
            continue
        a, z = src
        if t == "image":
            end = link_label_end(content, a + 1)
            if end > a:
                out.append((to_doc(a), to_doc(z), [("img", to_doc(a + 2), to_doc(end))],
                            [(to_doc(a), to_doc(a + 2)), (to_doc(end), to_doc(z))]))
        elif t == "code_inline":
            n = len(c.markup)
            out.append((to_doc(a), to_doc(z), [("code", to_doc(a + n), to_doc(z - n))],
                        [(to_doc(a), to_doc(a + n)), (to_doc(z - n), to_doc(z))]))
        elif t == "footnote_ref":
            out.append((to_doc(a), to_doc(z), [("fnref", to_doc(a), to_doc(z))], []))
        elif t in ("math_inline", "math_inline_double"):          # $…$ $$…$$ \(…\)
            n = len(c.markup) if c.markup else 1
            styles, marks = _live_math(a + n, z - n, to_doc, content, out)
            out.append((to_doc(a), to_doc(z), styles,
                        [(to_doc(a), to_doc(a + n)), (to_doc(z - n), to_doc(z))] + marks))
        elif t == "hardbreak" and content[a:a + 1] == "\\":    # a capo con «\»
            out.append((to_doc(a), to_doc(z), [], [(to_doc(a), to_doc(a + 1))]))
        last = max(last, z)


def live_elements(text):
    """Elementi della resa live: (inizio, fine, stili, da_nascondere), con
    stili = [(nome, a, z)] e da_nascondere = [(a, z)] o [(a, z, nome)], in
    offset di carattere (come Gtk.TextBuffer). Gli stili valgono sempre; i
    marcatori si nascondono (o prendono lo stile «nome», come esponenti e
    linea orizzontale) solo quando il cursore o la selezione non toccano
    (inizio, fine): lì riappare il sorgente da modificare."""
    lines = text.split("\n")
    starts, o = [], 0
    for line in lines:
        starts.append(o)
        o += len(line) + 1

    def span(i):                                 # riga i, a capo compreso
        return starts[i], min(starts[i] + len(lines[i]) + 1, len(text))

    out, covered, quoted, table_depth = [], set(), set(), 0
    tokens = parse_source(text)
    heading = None
    for k, tok in enumerate(tokens):
        t = tok.type
        if tok.map and tok.level == 0:
            covered.update(range(*tok.map))
        if not tok.map and t not in ("table_close", "heading_close"):
            continue                    # senza righe non si sa dove applicarlo
        if t == "table_open":
            table_depth += 1
            l0, l1 = tok.map
            for i in range(l0, l1):
                a, z = span(i)
                role = "table_head" if i == l0 else "table_sep" if i == l0 + 1 else "table"
                styles = [("block", a, z), ("table", a, starts[i] + len(lines[i])),
                          (role, a, starts[i] + len(lines[i]))]
                if i != l0 + 1:
                    styles += [("table_sep", a + m.start(), a + m.end())
                               for m in re.finditer(r"\|", lines[i])]
                out.append((a, z, styles, []))
        elif t == "table_close":
            table_depth -= 1
        elif t == "heading_open":
            heading = tok
        elif t == "heading_close":
            heading = None
        elif t == "inline" and table_depth == 0:
            to_doc = inline_mapper(lines, starts, tok)
            if to_doc is None:
                continue
            if heading is not None:
                lvl = f"h{heading.tag[1]}"
                l0, l1 = heading.map
                if heading.markup.startswith("#"):                 # # Titolo
                    line, a0 = lines[l0], starts[l0]
                    c0 = to_doc(0) - a0
                    c1 = to_doc(len(tok.meta.get("src_content", tok.content))) - a0
                    ms = line.rfind(heading.markup, 0, c0)         # i # prima del testo
                    if ms < 0:
                        ms = c0
                    out.append((a0 + ms, a0 + len(line), [(lvl, a0 + ms, a0 + len(line))], []))
                    out.append((a0 + ms, a0 + c0, [], [(a0 + ms, a0 + c0)]))
                    tail = line[c1:]
                    if tail.strip().strip("#") == "" and "#" in tail:   # # di chiusura
                        out.append((a0 + c1, a0 + len(line), [], [(a0 + c1, a0 + len(line))]))
                else:                                               # sottolineato === ---
                    for i in range(l0, l1 - 1):
                        out.append((starts[i], starts[i] + len(lines[i]),
                                    [(lvl, starts[i], starts[i] + len(lines[i]))], []))
                    u = l1 - 1
                    out.append((starts[u], starts[u] + len(lines[u]),
                                [("setext", starts[u], starts[u] + len(lines[u]))], []))
            _live_inline(tok, to_doc, out)
        elif t.startswith("math_block"):                       # $$ … $$
            l0, l1 = tok.map
            l1 = min(l1, len(lines))
            A, Z = starts[l0], starts[l1 - 1] + len(lines[l1 - 1])
            styles, marks = [], []
            for i in range(l0, l1):
                styles.append(("math_block", *span(i)))
            if l1 - l0 == 1:                                     # $$ x $$ (1)
                line, a0 = lines[l0], starts[l0]
                open_ = line.index("$$") + 2 if "$$" in line else 0
                close = line.rindex("$$") if line.count("$$") >= 2 else len(line)
                # Solo i $$: il numero dell'equazione, $$ … $$ (1), resta.
                marks += [(a0, a0 + open_), (a0 + close, a0 + min(close + 2, len(line)))]
                body = [(a0 + open_, a0 + close)]
            else:
                marks += [(starts[l0], starts[l0] + len(lines[l0])),
                          (starts[l1 - 1], starts[l1 - 1] + len(lines[l1 - 1]))]
                body = [(starts[i], starts[i] + len(lines[i])) for i in range(l0 + 1, l1 - 1)]
            for a, z in body:
                st, mk = _live_math(0, z - a, lambda p, a=a: a + p, text[a:z], out)
                styles += st
                marks += mk
            out.append((A, Z, styles, marks))
        elif t in ("fence", "code_block"):
            l0, l1 = tok.map
            l1 = min(l1, len(lines))
            A, Z = starts[l0], starts[l1 - 1] + len(lines[l1 - 1])
            styles, hides = [], []
            for i in range(l0, l1):
                a, z = span(i)
                styles += [("block", a, z), ("code", a, starts[i] + len(lines[i]))]
            if t == "fence":
                fences = [l0]
                last = lines[l1 - 1].strip()
                if l1 - 1 > l0 and last and set(last.lstrip(">").strip()) == {tok.markup[0]} \
                        and len(last.lstrip(">").strip()) >= len(tok.markup):
                    fences.append(l1 - 1)
                hides = [(starts[i], starts[i] + len(lines[i])) for i in fences]
            out.append((A, Z, styles, hides))
        elif t == "hr":
            i = tok.map[0]
            out.append((starts[i], starts[i] + len(lines[i]),
                        [("hr", starts[i], starts[i] + len(lines[i]))],
                        [(*span(i), "hr_bar")]))
        elif t == "blockquote_open":
            for i in range(*tok.map):
                if i >= len(lines) or i in quoted:
                    continue                     # citazioni annidate: una volta
                quoted.add(i)
                a, line = starts[i], lines[i]
                m = _RE_QUOTE_MARKS.match(line)
                out.append((a, a + len(line), [("quote", a, a + len(line))], []))
                if m and ">" in m.group(0):
                    ms = a + line.index(">")
                    out.append((ms, a + m.end(), [], [(ms, a + m.end())]))
        elif t == "list_item_open":
            i = tok.map[0]
            a, line = starts[i], lines[i]
            marker = (tok.info + tok.markup) if tok.info else tok.markup
            m = re.search(r"(?:^|(?<=[\s>]))" + re.escape(marker) + r"(?=[ \t]|$)", line)
            if not m:
                continue
            ms, me = a + m.start(), a + m.end()
            out.append((ms, me, [("bullet", ms, me)], []))
            if "task-list-item" in str(tok.attrs.get("class", "")):
                mt = re.match(r"[ \t]+(\[[ xX]\])[ \t]*", line[m.end():])
                if mt:
                    ta, tz = me + mt.start(1), me + mt.end(1)
                    styles = [("task", ta, tz)]
                    if mt.group(1)[1] in "xX":
                        styles.append(("task_done", me + mt.end(), a + len(line)))
                    out.append((ta, tz, styles, []))
    # Definizioni di riferimento ([etichetta]: indirizzo) e di nota
    # ([^etichetta]: testo): markdown-it usa le prime senza produrre token e
    # sposta le seconde in fondo al documento, quindi sono le righe che nessun
    # blocco copre. Il testo delle note ha già avuto i suoi stili in linea.
    for i, line in enumerate(lines):
        if i in covered:
            continue
        m = _RE_REF_LINE.match(line)
        if m:
            styles = [("fndef", starts[i], starts[i] + len(line))]
            if line.lstrip().startswith("[^"):
                styles.append(("fnref", starts[i] + line.index("["), starts[i] + m.end() - 1))
            out.append((starts[i], starts[i] + len(line), styles, []))
    return out


def _safe_url(url):
    u = url.strip()
    if re.match(r"^\s*(javascript|vbscript|data:text/html)", u, re.I):
        return "#"
    return u


class _MathNode:
    """Formula su riga propria ($$…$$, \\[…\\]) vista come un paragrafo con
    una sola formula in evidenza: i renderer la trattano come $$…$$."""
    type = "math_inline_double"
    children = ()

    def __init__(self, content):
        self.content = content


class MarkdownDoc:
    """Albero di blocchi Markdown con resa HTML, Pango (anteprima) e testo.

    L'analisi è quella del motore comune (rusca_markdown.parser()). Qui il suo
    albero diventa una lista di blocchi; il testo in linea resta come nodi
    dell'albero di markdown-it e lo rende _inline():
      ("heading", livello, nodi, id)    ("para", nodi)    ("code", lingua, testo)
      ("hr",)    ("quote", blocchi)    ("table", allineamenti, intestazione, righe)
      ("list", numerato, inizio, largo, [(attività, blocchi), …])
    attività vale None (voce normale), True (fatta) o False (da fare). Le note
    sono in self.footnotes (etichetta -> blocchi)."""

    def __init__(self, text):
        self.footnotes = {}
        self._ids = {}
        self._fn_num = {}
        self._img_src = None
        self._colors = LIGHT
        self._t = lambda k, **kw: k
        self._collect = None          # indirizzi dei link, per il PDF
        text = text.replace("\r\n", "\n").replace("\r", "\n")
        self.blocks = self._blocks(SyntaxTreeNode(md_parser().parse(text)).children)

    # ------------------------------------------------------------ albero
    def _make_id(self, nodes):
        base = re.sub(r"[^\w\- ]", "", self.plain(nodes).lower(), flags=re.U).strip()
        base = re.sub(r"\s+", "-", base) or "section"
        n = self._ids.get(base, 0)
        self._ids[base] = n + 1
        return base if n == 0 else f"{base}-{n}"

    @staticmethod
    def _inline_nodes(node):
        """Nodi in linea di un paragrafo, titolo o cella."""
        return list(node.children[0].children) if node.children else []

    def _blocks(self, nodes):
        out = []
        for n in nodes:
            t = n.type
            if t == "paragraph":
                out.append(("para", self._inline_nodes(n)))
            elif t == "heading":
                inline = self._inline_nodes(n)
                out.append(("heading", int(n.tag[1]), inline, self._make_id(inline)))
            elif t in ("fence", "code_block"):
                lang = n.info.split()[0] if t == "fence" and n.info.strip() else ""
                body = n.content[:-1] if n.content.endswith("\n") else n.content
                out.append(("code", lang, body))
            elif t.startswith("math_block"):
                out.append(("para", [_MathNode(n.content.strip())]))
            elif t == "hr":
                out.append(("hr",))
            elif t == "blockquote":
                out.append(("quote", self._blocks(n.children)))
            elif t in ("bullet_list", "ordered_list"):
                out.append(self._list(n))
            elif t == "table":
                out.append(self._table(n))
            elif t == "footnote_block":
                for note in n.children:
                    self.footnotes[note.meta["label"]] = self._blocks(note.children)
            elif n.children:
                out.extend(self._blocks(n.children))
        return out

    def _list(self, node):
        ordered = node.type == "ordered_list"
        start = int(node.attrs.get("start", 1)) if ordered else 1
        # markdown-it nasconde i paragrafi degli elenchi «stretti».
        loose = any(not c.hidden for item in node.children
                    for c in item.children if c.type == "paragraph")
        items = []
        for item in node.children:
            task = None
            if "task-list-item" in str(item.attrs.get("class", "")):
                first = item.children[0] if item.children else None
                box = next((x for x in self._inline_nodes(first) if x.type == "html_inline"),
                           None) if first is not None and first.type == "paragraph" else None
                task = box is not None and "checked" in box.content
            items.append((task, self._blocks(item.children)))
        return ("list", ordered, start, loose, items)

    def _table(self, node):
        aligns, header, rows = [], [], []
        for section in node.children:                  # thead, tbody
            for tr in section.children:
                cells = [self._inline_nodes(cell) for cell in tr.children]
                if section.type == "thead":
                    header = cells
                    for cell in tr.children:
                        style = str(cell.attrs.get("style", ""))
                        aligns.append(style.split(":", 1)[1] if ":" in style else None)
                else:
                    rows.append(cells)
        return ("table", aligns, header, rows)

    @staticmethod
    def _split_hardbreaks(nodes):
        """Righe di un paragrafo divise agli a capo forzati."""
        pieces = [[]]
        for n in nodes:
            if n.type == "hardbreak":
                pieces.append([])
            else:
                pieces[-1].append(n)
        return pieces

    def _lone_image(self, nodes):
        """(percorso, descrizione) se il paragrafo è una sola immagine."""
        real = [n for n in nodes if not (n.type == "text" and not n.content.strip())]
        if len(real) == 1 and real[0].type == "image":
            img = real[0]
            return (md_parser().normalizeLinkText(str(img.attrs.get("src", ""))),
                    self._inline(img.children, "plain"))
        return None

    # ------------------------------------------------------------ inline
    def plain(self, text):
        return self._inline(text, "plain")

    def _inline(self, nodes, mode):
        """Nodi in linea (o testo Markdown) -> HTML, markup Pango o testo."""
        if isinstance(nodes, str):
            tokens = md_parser().parseInline(nodes)
            nodes = SyntaxTreeNode(tokens).children[0].children if tokens else []
        c = self._colors
        esc = (lambda s: s) if mode == "plain" else html.escape
        tags = {
            "html": {"b": ("<strong>", "</strong>"), "i": ("<em>", "</em>"),
                     "s": ("<del>", "</del>"), "m": ("<mark>", "</mark>")},
            "pango": {"b": ("<b>", "</b>"),
                      "i": ((f'<span style="italic" foreground="{c["em"]}">', "</span>")
                            if c.get("em") else ("<i>", "</i>")),
                      "s": ("<s>", "</s>"),
                      "m": (f'<span background="{c["selection"]}">', "</span>")},
            "plain": {k: ("", "") for k in ("b", "i", "s", "m")},
        }[mode]
        kinds = {"strong": "b", "em": "i", "s": "s", "mark": "m"}
        out, after_box = [], False
        for n in nodes:
            t = n.type
            if t == "text":
                out.append(esc(n.content.lstrip(" ") if after_box else n.content))
            elif t == "softbreak":
                out.append("\n" if mode == "html" else " ")
            elif t == "hardbreak":
                out.append("<br>\n" if mode == "html" else "\n")
            elif t == "code_inline":
                out.append(self._code_span(n.content, mode))
            elif t in ("math_inline", "math_inline_double"):
                out.append(self._math(n.content, t == "math_inline_double", mode))
            elif t in kinds:
                a, z = tags[kinds[t]]
                out.append(a + self._inline(n.children, mode) + z)
            elif t == "link":
                out.append(self._link(self._inline(n.children, mode), n.attrs.get("href", ""),
                                      n.attrs.get("title"), mode))
            elif t == "image":
                src = md_parser().normalizeLinkText(str(n.attrs.get("src", "")))
                out.append(self._image(self._inline(n.children, "plain"), src,
                                       n.attrs.get("title"), mode))
            elif t == "footnote_ref":
                out.append(self._fnref(n.meta, mode))
            elif t in ("html_inline", "footnote_anchor"):
                pass                # casella delle liste di attività; ritorno dalla nota
            elif n.children:
                out.append(self._inline(n.children, mode))
            else:
                out.append(esc(n.content))
            after_box = t == "html_inline"
        return "".join(out)

    def _code_span(self, body, mode):
        c = self._colors
        if mode == "html":
            return f"<code>{html.escape(body)}</code>"
        if mode == "pango" and c.get("guide"):
            # Export PDF: «pillola» rosa come nelle guide RuscaLinux
            # (gli spazi sottili fanno da margine interno dello sfondo).
            return (f'<span font_family="{c["mono"]}" size="smaller" '
                    f'background="{c["code_bg"]}" foreground="{c["code_fg"]}">'
                    f'\u2009{html.escape(body)}\u2009</span>')
        if mode == "pango":
            return (f'<span font_family="monospace" background="{c["code_bg"]}" '
                    f'foreground="{c["code_fg"]}">{html.escape(body)}</span>')
        return body

    @staticmethod
    def _math(src, big, mode):
        markup = latex_to_pango(src)
        if mode == "plain":
            return _pango_plain(markup)
        if big:                                     # $$…$$: formula in evidenza
            return (f'<span size="large">{markup}</span>' if mode == "pango"
                    else f'<span style="font-size: 1.2em">{markup}</span>')
        return markup

    def _link(self, label_markup, url, title, mode):
        c = self._colors
        url = _safe_url(url)
        if mode == "html":
            t = f' title="{html.escape(title)}"' if title else ""
            return f'<a href="{html.escape(url)}"{t}>{label_markup}</a>'
        if mode == "pango":
            if self._collect is not None:
                # PDF: l'esportatore trova i link come tratti sottolineati,
                # nell'ordine del testo. Un link senza testo non ha tratto.
                if not label_markup:
                    return ""
                self._collect.append(url)
            uc = f' underline_color="{c["link_line"]}"' if c.get("link_line") else ""
            return f'<span underline="single"{uc} foreground="{c["link"]}">{label_markup}</span>'
        return label_markup

    def _image(self, alt, src, title, mode):
        c = self._colors
        if mode == "html":
            real = self._img_src(src) if self._img_src else src
            t = f' title="{html.escape(title)}"' if title else ""
            return f'<img src="{html.escape(_safe_url(real))}" alt="{html.escape(alt)}"{t}>'
        if mode == "pango":
            return f'<span foreground="{c["accent"]}">🖼 {html.escape(alt or src)}</span>'
        return alt

    def _fnref(self, meta, mode):
        """Numero della nota: l'ordine in cui le note compaiono nel testo."""
        c = self._colors
        label = meta.get("label") or str(meta["id"])
        num = meta["id"] + 1
        self._fn_num[label] = num
        sid = re.sub(r"[^\w-]", "-", label)
        if mode == "html":
            return f'<sup class="fnref"><a href="#fn-{sid}" id="fnref-{sid}">{num}</a></sup>'
        if mode == "pango":
            return f'<span rise="5000" size="smaller" foreground="{c["accent"]}">{num}</span>'
        return f"[{num}]"

    # ------------------------------------------------------------ HTML
    def to_html(self, img_src=None, t=None):
        self._img_src = img_src
        self._fn_num = {}
        if t:
            self._t = t
        body = self._html_blocks(self.blocks)
        if self._fn_num:
            parts = ['<section class="footnotes">', "<hr>", "<ol>"]
            for fid, _num in sorted(self._fn_num.items(), key=lambda kv: kv[1]):
                sid = re.sub(r"[^\w-]", "-", fid)
                inner = self._html_blocks(self.footnotes.get(fid, []), tight=True)
                parts.append(f'<li id="fn-{sid}">{inner} '
                             f'<a href="#fnref-{sid}" class="fnback">↩</a></li>')
            parts += ["</ol>", "</section>"]
            body += "\n" + "\n".join(parts)
        return body

    def _html_blocks(self, blocks, tight=False):
        out = []
        for b in blocks:
            k = b[0]
            if k == "heading":
                out.append(f'<h{b[1]} id="{html.escape(b[3])}">{self._inline(b[2], "html")}</h{b[1]}>')
            elif k == "para":
                inner = self._inline(b[1], "html")
                out.append(inner if tight else f"<p>{inner}</p>")
            elif k == "code":
                cls = f' class="language-{html.escape(b[1])}"' if b[1] else ""
                out.append(f"<pre><code{cls}>{html.escape(b[2])}</code></pre>")
            elif k == "hr":
                out.append("<hr>")
            elif k == "quote":
                out.append("<blockquote>\n" + self._html_blocks(b[1]) + "\n</blockquote>")
            elif k == "list":
                _, ordered, start, loose, items = b
                has_task = any(task is not None for task, _ in items)
                cls = ' class="task-list"' if has_task else ""
                if ordered:
                    st = f' start="{start}"' if start != 1 else ""
                    out.append(f"<ol{st}{cls}>")
                else:
                    out.append(f"<ul{cls}>")
                for task, sub in items:
                    inner = self._html_blocks(sub, tight=not loose)
                    if task is not None:
                        chk = " checked" if task else ""
                        out.append(f'<li class="task"><input type="checkbox" disabled{chk}> {inner}</li>')
                    else:
                        out.append(f"<li>{inner}</li>")
                out.append("</ol>" if ordered else "</ul>")
            elif k == "table":
                _, aligns, header, rows = b

                def st(i):
                    al = aligns[i] if i < len(aligns) else None
                    return f' style="text-align:{al}"' if al else ""
                out.append('<div class="table-wrap"><table>')
                out.append("<thead><tr>" + "".join(
                    f"<th{st(i)}>{self._inline(h, 'html')}</th>" for i, h in enumerate(header))
                    + "</tr></thead>")
                out.append("<tbody>")
                for r in rows:
                    out.append("<tr>" + "".join(
                        f"<td{st(i)}>{self._inline(cell, 'html')}</td>" for i, cell in enumerate(r))
                        + "</tr>")
                out.append("</tbody></table></div>")
        return "\n".join(out)

    # ------------------------------------------------------------ anteprima
    def to_preview(self, colors, t=None):
        """Elementi per l'anteprima: ("m", markup, nowrap), ("img", src, alt, prefisso)
        o ("table", allineamenti, intestazione, righe) con celle in markup.
        L'export PDF usa invece to_print(), con elementi semantici."""
        self._colors = colors
        self._fn_num = {}
        if t:
            self._t = t
        items = self._pv_blocks(self.blocks, depth=0)
        if self._fn_num:
            c = colors
            items.append(("m", "", False))
            items.append(("m", f'<span foreground="{c["subtle"]}">{"─" * 24}</span>  '
                               f'<span weight="bold" foreground="{c["subtle"]}">'
                               f'{html.escape(self._t("fn_title"))}</span>', False))
            for fid, num in sorted(self._fn_num.items(), key=lambda kv: kv[1]):
                sub = self._pv_blocks(self.footnotes.get(fid, []), depth=1, tight=True)
                pre = f'<span rise="5000" size="smaller" foreground="{c["accent"]}">{num}</span> '
                items += self._prefix(sub, pre, "   ")
        return items

    def _prefix(self, items, first, rest):
        out = []
        for idx, it in enumerate(items):
            p = first if idx == 0 else rest
            if it[0] == "m":
                out.append(("m", p + it[1] if (it[1] or idx == 0) else it[1], it[2]))
            elif it[0] == "img":
                out.append(("img", it[1], it[2], p + it[3]))
            else:
                out.append(it)
        return out

    def _pv_blocks(self, blocks, depth, tight=False):
        c = self._colors
        out = []
        sizes = {1: "xx-large", 2: "x-large", 3: "large", 4: "large", 5: "medium", 6: "medium"}
        for bi, b in enumerate(blocks):
            if bi > 0 and not tight:
                out.append(("m", "", False))
            k = b[0]
            if k == "heading":
                hc = c.get("heading3", c["heading"]) if b[1] >= 3 else c["heading"]
                out.append(("m", f'<span size="{sizes[b[1]]}" weight="bold" foreground="{hc}">'
                                 f'{self._inline(b[2], "pango")}</span>', False))
            elif k == "para":
                img = self._lone_image(b[1])
                if img:
                    out.append(("img", img[0], img[1], ""))
                    continue
                for piece in self._split_hardbreaks(b[1]):
                    out.append(("m", self._inline(piece, "pango").replace("\n", " "), False))
            elif k == "code":
                lines = b[2].split("\n") or [""]
                w = max(_display_width(l) for l in lines) + 2
                for l in lines:
                    pad = " " * (w - _display_width(l))
                    out.append(("m", f'<span font_family="monospace" '
                                     f'background="{c.get("pre_bg", c["code_bg"])}" '
                                     f'foreground="{c.get("pre_fg", c["code_fg"])}"> '
                                     f'{html.escape(l)}{pad}</span>', True))
            elif k == "hr":
                out.append(("m", f'<span foreground="{c["subtle"]}">{"─" * 40}</span>', False))
            elif k == "quote":
                inner = self._pv_blocks(b[1], depth)
                bar = f'<span foreground="{c.get("quote_bar", c["accent"])}" weight="bold">┃ </span>'
                for it in inner:
                    if it[0] == "m":
                        out.append(("m", bar + f'<span style="italic" foreground="{c["quote"]}">'
                                    + it[1] + "</span>", it[2]))
                    elif it[0] == "img":
                        out.append(("img", it[1], it[2], bar + it[3]))
                    else:
                        out.append(it)
            elif k == "list":
                _, ordered, start, loose, items = b
                bullets = "•◦▪"
                for idx, (task, sub) in enumerate(items):
                    if task is not None:
                        mark = "☑" if task else "☐"
                    elif ordered:
                        mark = f"{start + idx}."
                    else:
                        mark = bullets[depth % 3]
                    inner = self._pv_blocks(sub, depth + 1, tight=not loose)
                    if task:
                        inner = [("m", f'<span strikethrough="true" foreground="{c["subtle"]}">'
                                       f'{it[1]}</span>', it[2]) if it[0] == "m" and it[1] else it
                                 for it in inner]
                    first = f'<span foreground="{c["accent"]}" weight="bold">{mark}</span> '
                    rest = " " * (_display_width(mark) + 1)
                    out += self._prefix(inner or [("m", "", False)], first, rest)
                    if loose and idx < len(items) - 1:
                        out.append(("m", "", False))
            elif k == "table":
                # Tabella vera (Gtk.Grid nell'anteprima): le celle vanno a capo.
                _, aligns, header, rows = b
                out.append(("table", aligns, [self._inline(h, "pango") for h in header],
                            [[self._inline(cell, "pango").replace("\n", " ") for cell in r]
                             for r in rows]))
        return out

    _PR_BEFORE = {"h1": 22.0, "h2": 22.0, "h3": 14.0, "h4": 12.0, "h5": 11.0, "h6": 11.0,
                  "hr": 17.0}
    _PR_AFTER = {"h1": 18.0, "h2": 12.0, "h3": 7.0, "h4": 6.0, "h5": 6.0, "h6": 6.0,
                 "hr": 17.0, "para": 9.0, "code": 10.0, "quote": 10.0, "list": 9.0,
                 "table": 10.0, "img": 9.0}
    _PR_LIST_INDENT = 27.0      # rientro del contenuto di un elemento d'elenco (pt)
    _PR_QUOTE_LEFT = 16.0       # barra (4) + margine interno (12) della citazione
    _PR_QUOTE_RIGHT = 12.0

    def to_print(self, colors, t=None):
        """Elementi semantici per l'export PDF in stile «guida RuscaLinux».
        Ogni elemento porta i propri rientri sinistro/destro (l, r) in punti:
          ("gap", pt)                         spazio verticale
          ("h", livello, markup, l, r, link, id)   titolo (livello 1 = banner)
          ("p", markup, l, r, marker, stile, link) paragrafo; marker = (markup, x_destra)
          ("code", testo, l, r)               blocco di codice scuro
          ("qopen", l, r) / ("qclose",)       riquadro di citazione
          ("hr", l, r)                        linea di separazione
          ("img", src, alt, l, r)             immagine centrata
          ("table", allin., intest., righe, l, r, link)
        link: indirizzi dei link del markup, nell'ordine del testo (per le
        tabelle, una lista per cella, riga per riga a partire
        dall'intestazione). id: l'ancora del titolo, per i link interni."""
        self._colors = colors
        self._fn_num = {}
        if t:
            self._t = t
        items = self._pr_blocks(self.blocks, 0.0, 0.0)
        if self._fn_num:
            items += [("gap", 18.0), ("hr", 0.0, 0.0), ("gap", 8.0),
                      ("p", f'<b>{html.escape(self._t("fn_title"))}</b>', 0.0, 0.0, None, "small", ()),
                      ("gap", 3.0)]
            for fid, num in sorted(self._fn_num.items(), key=lambda kv: kv[1]):
                sub = self._pr_blocks(self.footnotes.get(fid, []), 18.0, 0.0, tight=True, style="small")
                items += self._pr_marker(sub, f"{num}.", 18.0, "small")
                items.append(("gap", 2.0))
        return items

    def _pr_inline(self, nodes):
        """Markup Pango per il PDF e indirizzi dei suoi link."""
        self._collect = []
        try:
            markup = self._inline(nodes, "pango")
            return markup, tuple(self._collect)
        finally:
            self._collect = None

    @staticmethod
    def _pr_marker(items, marker, l, style):
        """Aggancia il segno d'elenco al primo paragrafo, allineato a destra
        nello spazio di rientro (come i numeri degli elenchi nelle guide)."""
        items = list(items)
        for idx, it in enumerate(items):
            if it[0] == "gap":
                continue
            if it[0] == "p" and it[4] is None:
                items[idx] = it[:4] + ((marker, l - 6.0),) + it[5:]
                return items
            break
        items.insert(0, ("p", "", l, 0.0, (marker, l - 6.0), style, ()))
        return items

    def _pr_blocks(self, blocks, l, r, tight=False, style="body", depth=0):
        c = self._colors
        out = []
        prev = None
        for b in blocks:
            k = b[0]
            kind = f"h{b[1]}" if k == "heading" else k
            if prev is not None:
                if tight:
                    out.append(("gap", 2.0))
                else:
                    out.append(("gap", max(self._PR_AFTER.get(prev, 7.0),
                                           self._PR_BEFORE.get(kind, 0.0))))
            if k == "heading":
                markup, links = self._pr_inline(b[2])
                out.append(("h", b[1], markup, l, r, links, b[3]))
            elif k == "para":
                img = self._lone_image(b[1])
                if img:
                    out.append(("img", img[0], img[1], l, r))
                    kind = "img"
                else:
                    st = "lead" if (prev == "h1" and depth == 0 and l == 0.0 and style == "body") else style
                    markup, links = self._pr_inline(b[1])
                    out.append(("p", markup, l, r, None, st, links))
            elif k == "code":
                out.append(("code", b[2], l, r))
            elif k == "hr":
                out.append(("hr", l, r))
            elif k == "quote":
                out.append(("qopen", l, r))
                out += self._pr_blocks(b[1], l + self._PR_QUOTE_LEFT, r + self._PR_QUOTE_RIGHT,
                                       style=style, depth=depth)
                out.append(("qclose",))
            elif k == "list":
                _, ordered, start, loose, items = b
                bullets = "•◦▪"
                ind = l + self._PR_LIST_INDENT
                for idx, (task, sub) in enumerate(items):
                    if idx:
                        out.append(("gap", 6.0 if loose else 0.5))
                    if task is not None:
                        mark = f'<span foreground="{c["accent"]}">{"☑" if task else "☐"}</span>'
                    elif ordered:
                        mark = f"{start + idx}."
                    else:
                        mark = bullets[depth % 3]
                    inner = self._pr_blocks(sub, ind, r, tight=not loose, style=style, depth=depth + 1)
                    if task:
                        inner = [(it[0], f'<span strikethrough="true" foreground="{c["subtle"]}">'
                                         f'{it[1]}</span>') + it[2:]
                                 if it[0] == "p" and it[1] else it for it in inner]
                    out += self._pr_marker(inner, mark, ind, style)
            elif k == "table":
                _, aligns, header, rows = b
                grid = [[self._pr_inline(cell) for cell in row] for row in [header] + rows]
                out.append(("table", aligns, [m for m, _ in grid[0]],
                            [[m for m, _ in row] for row in grid[1:]], l, r,
                            [[links for _, links in row] for row in grid]))
            prev = kind
        return out
# ----------------------------------------------------------------------------
# Tema degli export (HTML e PDF): lo stile delle guide di riferimento dei
# RuscaLinux OS Tools. Banner del titolo con sfumatura rosa → prugna,
# titoli prugna con filetto rosa, codice su fondo prugna scuro con barra
# rosa, citazioni su rosa chiaro, tabelle con intestazione prugna e righe
# alternate, DejaVu Sans / DejaVu Sans Mono (fonts-dejavu-core su Debian).
# I colori sono fissi: l'export non dipende dal tema chiaro/scuro dell'editor.
# ----------------------------------------------------------------------------
GUIDE = {
    "page": "#FFFFFF", "fg": "#2B1027", "title": "#4A1238", "h3": "#6B2252",
    "lead": "#4A1238", "accent": "#B0598C", "rule_h2": "#D98BB4", "rule": "#ECC7DA",
    "code_bg": "#FBEEF4", "code_fg": "#4A1238",
    "pre_bg": "#2E0F26", "pre_fg": "#FDF2E9", "pre_bar": "#D98BB4",
    "quote_bg": "#FBEEF4", "quote_bar": "#B0598C",
    "th_bg": "#6B2252", "th_fg": "#FFFFFF", "stripe": "#FDF4F8",
    "footer": "#5A2A4A", "em": "#6B2252", "link": "#6B2252", "mark": "#F6C6DC",
    "banner_fg": "#FFFFFF",
    # sfumatura del banner: 135°, rosa 0 % → malva 45 % → prugna 100 %
    # (con punto medio al 50 %: il prugna arriva presto, come nelle guide)
    "grad": ("#F6C6DC", "#B0598C", "#4A1238"),
}
GUIDE_FONT = "DejaVu Sans"
GUIDE_MONO = "DejaVu Sans Mono"
# Anteprima classica con il tema chiaro: i colori degli export, così quello
# che si vede accanto all'editor è quello che uscirà in PDF e in HTML.
# Con il tema scuro l'anteprima resta prugna, per non affiancare un pannello
# bianco all'editor scuro.
PREVIEW_GUIDE = dict(LIGHT)
PREVIEW_GUIDE.update({
    "preview_bg": GUIDE["page"], "fg": GUIDE["fg"], "heading": GUIDE["title"],
    "heading3": GUIDE["h3"], "accent": GUIDE["accent"], "subtle": GUIDE["footer"],
    "code_bg": GUIDE["code_bg"], "code_fg": GUIDE["code_fg"],
    "pre_bg": GUIDE["pre_bg"], "pre_fg": GUIDE["pre_fg"], "quote": GUIDE["footer"],
    "quote_bar": GUIDE["quote_bar"], "link": GUIDE["link"], "selection": GUIDE["mark"],
})

HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="{lang}"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="color-scheme" content="light">
<title>{title}</title><style>
@page {{
  size: A4; margin: 2cm 2cm 2cm 2cm;
  @bottom-center {{ content: {footer}; font-family: {font}; font-size: 8pt; color: {c[footer]}; }}
}}
* {{ -webkit-print-color-adjust: exact; print-color-adjust: exact; box-sizing: border-box; }}
html {{ background: {c[stripe]}; }}
body {{ background: {c[page]}; color: {c[fg]}; font-family: {font};
        font-size: 15px; line-height: 1.5; max-width: 860px; margin: 2rem auto;
        padding: 2.6rem 3rem 3rem; border-radius: 10px;
        box-shadow: 0 2px 18px rgba(74,18,56,.10); overflow-wrap: break-word; }}
h1 {{ color: {c[banner_fg]}; font-size: 2.1em; line-height: 1.45; margin: 1.2em 0 .7em;
      padding: .8em .75em; border-radius: 6px;
      background: {c[grad][2]} linear-gradient(135deg, {c[grad][0]} 0%, {c[grad][1]} 45%, 50%, {c[grad][2]} 100%); }}
body > h1:first-child {{ margin-top: 0; }}
h1 code {{ color: {c[code_fg]}; }}
h1 + p {{ font-size: 1.1em; color: {c[lead]}; }}
h2 {{ color: {c[title]}; font-size: 1.4em; line-height: 1.3; margin: 1.45em 0 .7em;
      padding-bottom: .3em; border-bottom: 2px solid {c[rule_h2]}; }}
h3 {{ color: {c[h3]}; font-size: 1.15em; margin: 1.3em 0 .5em; }}
h4, h5, h6 {{ color: {c[h3]}; font-size: 1.05em; margin: 1.2em 0 .45em; }}
p {{ margin: 0 0 .75em; }}
a {{ color: {c[link]}; text-decoration-color: {c[rule_h2]}; text-underline-offset: 2px; }}
em {{ color: {c[em]}; }}
strong {{ color: inherit; }}
hr {{ border: none; border-top: 1px solid {c[rule]}; margin: 1.6em 0; }}
code {{ font-family: {mono}; font-size: .88em; background: {c[code_bg]}; color: {c[code_fg]};
        padding: .1em .35em; border-radius: 3px; }}
pre {{ background: {c[pre_bg]}; color: {c[pre_fg]}; border-left: 4px solid {c[pre_bar]};
       border-radius: 6px; padding: .95em 1.2em; margin: 0 0 1em; line-height: 1.75;
       overflow-x: auto; }}
pre code {{ background: none; color: inherit; padding: 0; font-size: .85em; border-radius: 0; }}
blockquote {{ background: {c[quote_bg]}; border-left: 4px solid {c[quote_bar]};
              margin: 0 0 1em; padding: .8em 1.1em; border-radius: 0 4px 4px 0; }}
blockquote > :last-child {{ margin-bottom: 0; }}
ul, ol {{ margin: 0 0 .9em; padding-left: 2.2em; }}
li {{ margin: .1em 0; }}
li > p {{ margin: .2em 0; }}
ul.task-list, ol.task-list {{ list-style: none; padding-left: 1.2em; }}
li.task input {{ margin-right: .45rem; accent-color: {c[accent]}; }}
img {{ max-width: 100%; height: auto; }}
p > img:only-child {{ display: block; margin: 1.2rem auto; }}
.table-wrap {{ overflow-x: auto; margin: 0 0 1.1em; }}
table {{ border-collapse: collapse; width: 100%; font-size: .9em; }}
th, td {{ padding: .6em .7em; text-align: left; vertical-align: top; }}
thead th {{ background: {c[th_bg]}; color: {c[th_fg]}; font-weight: bold;
            border-right: 1px solid {c[page]}; }}
thead th:last-child {{ border-right: none; }}
td {{ border-bottom: 1px solid {c[rule]}; }}
tbody tr:nth-child(even) td {{ background: {c[stripe]}; }}
mark {{ background: {c[mark]}; color: {c[fg]}; padding: 0 .15rem; border-radius: 3px; }}
del {{ color: {c[footer]}; }}
sup.fnref a {{ text-decoration: none; }}
.footnotes {{ font-size: .85em; color: {c[footer]}; margin-top: 2.5rem; }}
.fnback {{ text-decoration: none; }}
@media (max-width: 640px) {{
  body {{ margin: 0; padding: 1.4rem 1.1rem; border-radius: 0; box-shadow: none; }}
}}
@media print {{
  html {{ background: none; }}
  body {{ background: none; max-width: none; margin: 0; padding: 0; font-size: 10pt;
          border-radius: 0; box-shadow: none; }}
  h1, h2, h3, h4, h5, h6 {{ break-after: avoid; page-break-after: avoid; }}
  img, pre, blockquote, tr {{ break-inside: avoid; page-break-inside: avoid; }}
  pre {{ white-space: pre-wrap; overflow: visible; }}
}}
</style></head><body>
{body}
</body></html>"""


def _css_string(s):
    """Stringa CSS tra virgolette (per la proprietà content)."""
    s = re.sub(r"[\x00-\x1f\x7f]", " ", s)
    s = s.replace("\\", "\\\\").replace('"', '\\"')
    # < e > in forma di escape CSS: il titolo non può chiudere il blocco <style>.
    return '"' + s.replace("<", "\\3C ").replace(">", "\\3E ") + '"'


def _footer_template(t):
    """Modello del piè di pagina («{title} - pag. {page} / {pages}»),
    tradotto; se il catalogo non lo prevede si usa quello inglese."""
    tpl = t("export_footer") if t else ""
    if not tpl or tpl == "export_footer" or "{page}" not in tpl:
        tpl = _BUILTIN_STRINGS["en"]["export_footer"]
    return tpl


def footer_css_content(title, t=None):
    """Il piè di pagina come valore CSS di content, con i contatori di pagina."""
    parts = []
    for piece in re.split(r"(\{title\}|\{page\}|\{pages\})", _footer_template(t)):
        if piece == "{title}":
            parts.append(_css_string(title))
        elif piece == "{page}":
            parts.append("counter(page)")
        elif piece == "{pages}":
            parts.append("counter(pages)")
        elif piece:
            parts.append(_css_string(piece))
    return " ".join(parts) or '""'


def footer_text(title, page, pages, t=None):
    try:
        return _footer_template(t).format(title=title, page=page, pages=pages)
    except Exception:
        return f"{title} - {page} / {pages}"


def markdown_to_html(text, title, lang="en", img_src=None, t=None):
    """Export HTML con il motore integrato, nello stile delle guide RuscaLinux.
    Contiene solo il documento; stampato (o convertito in PDF da un browser)
    mostra in fondo a ogni pagina titolo e numero di pagina, come il PDF."""
    body = MarkdownDoc(text).to_html(img_src=img_src, t=t)
    return HTML_TEMPLATE.format(
        lang=html.escape(lang), title=html.escape(title), body=body, c=GUIDE,
        font=f'"{GUIDE_FONT}", "Verdana", "Bitstream Vera Sans", sans-serif',
        mono=f'"{GUIDE_MONO}", "Bitstream Vera Sans Mono", monospace',
        footer=footer_css_content(title, t))
# ----------------------------------------------------------------------------
# Export PDF nativo (GtkPrintOperation → file PDF, nessun dialogo di stampa)
# nello stile delle guide RuscaLinux: stessi colori, caratteri e riquadri
# dell'export HTML, piè di pagina «titolo - pag. N / totale».
# ----------------------------------------------------------------------------
PRINT_COLORS = dict(LIGHT)
PRINT_COLORS.update({
    "guide": True, "mono": GUIDE_MONO,
    "fg": GUIDE["fg"], "heading": GUIDE["title"], "accent": GUIDE["accent"],
    "accent2": GUIDE["accent"], "subtle": GUIDE["footer"], "quote": GUIDE["fg"],
    "border": GUIDE["rule"], "link": GUIDE["link"], "link_line": GUIDE["rule_h2"],
    "code_bg": GUIDE["code_bg"], "code_fg": GUIDE["code_fg"], "em": GUIDE["em"],
    "selection": GUIDE["mark"], "sel_fg": GUIDE["fg"],
})


def _cairo_str(s):
    """Stringa per gli attributi dei tag di cairo, tra apici singoli."""
    return str(s).replace("\\", "\\\\").replace("'", "\\'")


def _pdf_link_target(url, dests):
    """Attributo di cairo per la destinazione di un link del PDF: un indirizzo
    web o di posta, oppure un titolo del documento (#ancora) fra quelli in
    dests. Un link interno a un titolo che non c'è renderebbe non valido
    l'intero PDF (cairo lo rifiuta alla chiusura): resta testo. Gli altri
    indirizzi (file, percorsi relativi) non diventano link: fuori dalla
    cartella del documento non porterebbero da nessuna parte."""
    url = str(url)
    if url.startswith("#") and len(url) > 1:
        # markdown-it codifica l'ancora (#perch%C3%A9), l'id del titolo no.
        name = urllib.parse.unquote(url[1:])
        return f"dest='{_cairo_str(name)}'" if name in dests else ""
    if re.match(r"^(https?:|mailto:)", url, re.I):
        return f"uri='{_cairo_str(url)}'"
    return ""


class PdfExporter:
    """Impagina gli elementi di MarkdownDoc.to_print() su pagine del formato
    carta predefinito del sistema (A4 o Letter), con margini di 2 cm.
    I paragrafi e i blocchi di codice vanno a capo tra una pagina e l'altra
    riga per riga (i riquadri si spezzano con loro); i titoli non restano
    soli in fondo alla pagina; le tabelle si adattano alla larghezza utile
    e ripetono l'intestazione sulla pagina nuova."""

    MARGIN_PT = 56.7          # 2 cm
    FOOTER_PT = 30.0          # linea di base del piè di pagina dal bordo inferiore
    BODY = 10.0               # corpo del testo (pt)
    LEADING = 1.5             # interlinea del testo
    STYLE = {                 # corpo, colore, grassetto
        "body": (10.0, "fg", False), "lead": (11.0, "lead", False),
        "small": (8.5, "footer", False),
    }
    HEADINGS = {2: (14.0, "title"), 3: (11.5, "h3"), 4: (10.5, "h3"),
                5: (10.0, "h3"), 6: (10.0, "h3")}
    BOXES = {                 # sfondo, barra, raggio, margine verticale
        "code": ("pre_bg", "pre_bar", 5.0, 9.0),
        "quote": ("quote_bg", "quote_bar", 3.0, 9.0),
    }
    BAR_W = 4.0

    def __init__(self, items, load_image, title="", t=None):
        self.items = items
        self.load_image = load_image      # src -> GdkPixbuf.Pixbuf | None
        self.title = title
        self.t = t
        self.pages = [[]]
        self._keep = []

    def export(self, path):
        op = Gtk.PrintOperation()
        op.set_unit(Gtk.Unit.POINTS)
        op.set_use_full_page(True)        # margini e piè di pagina gestiti qui
        setup = Gtk.PageSetup()
        try:
            setup.set_paper_size(Gtk.PaperSize.new(Gtk.PaperSize.get_default()))
        except Exception:
            pass
        for setter in (setup.set_top_margin, setup.set_bottom_margin,
                       setup.set_left_margin, setup.set_right_margin):
            setter(0.0, Gtk.Unit.POINTS)
        op.set_default_page_setup(setup)
        op.set_export_filename(path)
        if self.title:
            op.set_job_name(self.title)
        op.connect("begin-print", self._begin)
        op.connect("draw-page", self._draw)
        return op.run(Gtk.PrintOperationAction.EXPORT, None)

    # --------------------------------------------------------- impaginazione
    def _begin(self, op, ctx):
        M = self.MARGIN_PT
        self.PW, self.PH = ctx.get_width(), ctx.get_height()
        W, H = self.PW - 2 * M, self.PH - 2 * M
        S = Pango.SCALE
        G = GUIDE
        self.pages, self._keep, self._boxes = [[]], [], []
        self._y = 0.0
        # Titoli del documento: le sole destinazioni dei link interni.
        self._dests = {it[6] for it in self.items if it[0] == "h"}
        self._ctx = ctx

        def font(size, bold=False, mono=False):
            fd = Pango.FontDescription.from_string(GUIDE_MONO if mono else GUIDE_FONT)
            fd.set_size(int(size * S))
            if bold:
                fd.set_weight(Pango.Weight.BOLD)
            return fd

        def layout(markup, width, fd, plain=False):
            lay = ctx.create_pango_layout()
            lay.set_font_description(fd)
            if width is not None:
                lay.set_width(int(max(1.0, width) * S))
                lay.set_wrap(Pango.WrapMode.WORD_CHAR)
            if plain:
                lay.set_text(markup, -1)
            else:
                try:
                    lay.set_markup(markup, -1)
                except Exception:
                    lay.set_text(html.unescape(re.sub(r"<[^>]+>", "", markup)), -1)
            self._keep.append(lay)
            return lay

        def size(lay):
            r = lay.get_extents()[1]
            return r.width / S, r.height / S

        def text_height(lay, lh):
            h = 0.0
            li = lay.get_iter()
            while True:
                h += max(li.get_line_extents()[1].height / S, lh)
                if not li.next_line():
                    return h

        def emit(op_):
            self.pages[-1].append(op_)

        # --- link cliccabili. Nel markup del PDF i link sono gli unici tratti
        # sottolineati: si abbinano, nell'ordine, agli indirizzi raccolti da
        # MarkdownDoc. Se i conti non tornano (markup non valido) niente link.
        def link_ranges(lay, links):
            if not links:
                return []
            spans = sorted((a.start_index, a.end_index) for a in lay.get_attributes().get_attributes()
                           if a.klass.type == Pango.AttrType.UNDERLINE and a.end_index > a.start_index)
            if len(spans) != len(links):
                return []
            return [(a, z, url) for (a, z), url in zip(spans, links)
                    if _pdf_link_target(url, self._dests)]

        def emit_links(line, ranges, x, top, h):
            """Rettangoli dei link che cadono in questa riga (x = inizio
            della riga, top = suo bordo superiore, in punti)."""
            ls, le = line.start_index, line.start_index + line.length
            for a, z, url in ranges:
                a, z = max(a, ls), min(z, le)
                if z <= a:
                    continue
                xa, xb = line.index_to_x(a, False) / S, line.index_to_x(z, False) / S
                if xb == xa:
                    continue
                emit(("link", x + min(xa, xb), top, abs(xb - xa), h, url))

        def lay_links(lay, links, x, y):
            """Link di un layout disegnato tutto insieme (celle di tabella)."""
            ranges = link_ranges(lay, links)
            if not ranges:
                return
            li = lay.get_iter()
            while True:
                logical = li.get_line_extents()[1]
                emit_links(li.get_line_readonly(), ranges, x + logical.x / S,
                           y + logical.y / S, logical.height / S)
                if not li.next_line():
                    break

        # --- riquadri (codice, citazioni) che si spezzano tra le pagine.
        # Lo sfondo va disegnato prima del testo: alla chiusura di ogni tratto
        # lo si inserisce nella pagina alla posizione registrata all'apertura.
        def close_chunk(box, y_end):
            h = y_end - box["y0"]
            if h > 0.5:
                self.pages[box["page"]].insert(
                    box["idx"], ("box", box["x"], box["y0"], W - box["x"] - box["r"], h, box["kind"]))

        def new_page():
            for box in reversed(self._boxes):     # prima i riquadri interni
                close_chunk(box, self._y)
            self.pages.append([])
            self._y = 0.0
            for box in self._boxes:               # riaperti, dall'esterno
                box.update(page=len(self.pages) - 1, idx=0, y0=0.0)
            if self._boxes:
                self._y = self.BOXES[self._boxes[-1]["kind"]][3] * 0.6

        def open_box(kind, l, r, need):
            pad = self.BOXES[kind][3]
            if self._y > 0 and self._y + pad + need > H:
                new_page()
            self._boxes.append({"kind": kind, "x": l, "r": r, "page": len(self.pages) - 1,
                                "idx": len(self.pages[-1]), "y0": self._y})
            self._y += pad

        def close_box():
            box = self._boxes.pop()
            self._y += self.BOXES[box["kind"]][3]
            close_chunk(box, self._y)

        def flow(lay, x0, color, line_h, marker=None, break_at=None, links=()):
            """Disegna un layout riga per riga, andando a pagina nuova se serve.
            line_h è l'interlinea in punti (come line-height in CSS): lo spazio
            in più si divide sopra e sotto la riga. break_at forza il salto di
            pagina prima di quella riga (vedove e orfane). links: indirizzi dei
            link del markup, nell'ordine del testo."""
            ranges = link_ranges(lay, links)
            li = lay.get_iter()
            first = True
            idx = 0
            while True:
                if break_at is not None and idx == break_at and self._y > 0:
                    new_page()
                idx += 1
                logical = li.get_line_extents()[1]
                lh0 = logical.height / S
                lh = max(lh0, line_h)
                if self._y + lh > H and (self.pages[-1] or self._boxes):
                    if self._y > 0:
                        new_page()
                top = self._y + (lh - lh0) / 2
                base = top + (li.get_baseline() - logical.y) / S
                emit(("line", li.get_line_readonly(), x0 + logical.x / S, base, color))
                if ranges:
                    emit_links(li.get_line_readonly(), ranges, x0 + logical.x / S, top, lh0)
                if first and marker is not None:
                    mlay, mx = marker
                    mw = size(mlay)[0]
                    emit(("line", mlay.get_line_readonly(0), mx - mw, base, G["fg"]))
                first = False
                self._y += lh
                if not li.next_line():
                    break

        def split_point(lay, line_h, min_lines=2):
            """Come orphans/widows: 2 in CSS. Restituisce la riga prima della
            quale andare a pagina nuova (0 = tutto il paragrafo), o None."""
            hs, li = [], lay.get_iter()
            while True:
                hs.append(max(li.get_line_extents()[1].height / S, line_h))
                if not li.next_line():
                    break
            n, y, fit = len(hs), self._y, 0
            for h in hs:
                if y + h > H:
                    break
                y += h
                fit += 1
            if fit >= n or self._y == 0 or n < 2:
                return None
            if fit < min_lines:
                return 0                       # orfana: tutto sulla pagina nuova
            if n - fit < min_lines:
                fit = n - min_lines            # vedova: si porta giù una riga in più
                return fit if fit >= min_lines else 0
            return fit

        def keep_room(h):
            """Evita titoli e banner orfani in fondo alla pagina."""
            if self._y > 0 and self._y + h > H:
                new_page()

        def table(aligns, header, rows, l, r, links=None):
            pad_x, pad_y = 6.0, 6.5
            TW = W - l - r
            ncol = len(header)
            grid = [header] + rows
            fd_b, fd_h = font(9.0), font(9.0, bold=True)
            natural = [0.0] * ncol
            for ri, row in enumerate(grid):
                for ci in range(ncol):
                    lay = layout(row[ci], None, fd_h if ri == 0 else fd_b)
                    natural[ci] = max(natural[ci], size(lay)[0] + 2 * pad_x)
            if sum(natural) <= TW:
                # Larghezza piena come nelle guide, in proporzione al contenuto.
                tot = sum(natural) or 1.0
                widths = [TW * n / tot for n in natural]
            else:
                # Colonne strette alla misura naturale, il resto diviso fra
                # quelle lunghe in proporzione: il testo va a capo nella cella.
                fixed, flexible = {}, list(range(ncol))
                while flexible:
                    share = (TW - sum(fixed.values())) / len(flexible)
                    small = [ci for ci in flexible if natural[ci] <= share]
                    if not small:
                        break
                    for ci in small:
                        fixed[ci] = natural[ci]
                        flexible.remove(ci)
                rest = TW - sum(fixed.values())
                tot = sum(natural[ci] for ci in flexible) or 1.0
                widths = [fixed[ci] if ci in fixed else max(36.0, rest * natural[ci] / tot)
                          for ci in range(ncol)]
            amap = {"center": Pango.Alignment.CENTER, "right": Pango.Alignment.RIGHT}

            def row_lays(cells, is_head):
                lays = []
                for ci in range(ncol):
                    lay = layout(cells[ci], widths[ci] - 2 * pad_x, fd_h if is_head else fd_b)
                    lay.set_spacing(int(2.0 * S))
                    al = aligns[ci] if ci < len(aligns) else None
                    if al in amap:
                        lay.set_alignment(amap[al])
                    lays.append(lay)
                return lays, max(size(x)[1] for x in lays) + 2 * pad_y

            def place(lays, h, is_head, stripe, cell_links=None):
                x = l
                if is_head:
                    emit(("fill", l, self._y, sum(widths), h, G["th_bg"]))
                elif stripe:
                    emit(("fill", l, self._y, sum(widths), h, G["stripe"]))
                for ci, lay in enumerate(lays):
                    emit(("lay", lay, x + pad_x, self._y + pad_y, G["th_fg"] if is_head else G["fg"]))
                    if cell_links and ci < len(cell_links):
                        lay_links(lay, cell_links[ci], x + pad_x, self._y + pad_y)
                    if is_head and ci < ncol - 1:
                        emit(("fill", x + widths[ci] - 0.4, self._y, 0.8, h, G["page"]))
                    x += widths[ci]
                if not is_head:
                    emit(("fill", l, self._y + h - 0.75, sum(widths), 0.75, G["rule"]))
                self._y += h

            links = links or [[] for _ in range(len(rows) + 1)]
            head_lays, head_h = row_lays(header, True)
            first_h = row_lays(rows[0], False)[1] if rows else 0.0
            keep_room(head_h + first_h)
            place(head_lays, head_h, True, False, links[0])
            for ri, row in enumerate(rows):
                lays, h = row_lays(row, False)
                if self._y + h > H and self._y > 0:
                    new_page()
                    place(*row_lays(header, True), True, False, links[0])   # intestazione ripetuta
                place(lays, h, False, ri % 2 == 1, links[ri + 1])

        def next_heading(i):
            """Il titolo che segue subito (saltando gli spazi), se c'è."""
            for nxt in self.items[i + 1:]:
                if nxt[0] != "gap":
                    return nxt if nxt[0] == "h" and nxt[1] > 1 else None
            return None

        for i, it in enumerate(self.items):
            kind = it[0]
            if kind == "gap":
                if self._y > 0:
                    self._y = min(self._y + it[1], H)
            elif kind == "h" and it[1] == 1:
                _, _lvl, markup, l, r, links, hid = it
                px, py = 15.0, 19.0
                lay = layout(markup, W - l - r - 2 * px, font(21.0, bold=True))
                h = text_height(lay, 21.0 * 1.45) + 2 * py
                keep_room(h + self.BODY * self.LEADING * 2)
                emit(("dest", hid, l, self._y))
                emit(("grad", l, self._y, W - l - r, h))
                self._y += py
                flow(lay, l + px, G["banner_fg"], 21.0 * 1.45, links=links)
                self._y += py
            elif kind == "h":
                _, lvl, markup, l, r, links, hid = it
                fs, col = self.HEADINGS.get(lvl, self.HEADINGS[6])
                lay = layout(markup, W - l - r, font(fs, bold=True))
                need = text_height(lay, fs * 1.3) + 6.0 + self.BODY * self.LEADING * 3
                nh = next_heading(i)
                if nh:          # titolo seguito da un sottotitolo: restano insieme
                    need += self.HEADINGS.get(nh[1], self.HEADINGS[6])[0] * 1.3 + 22.0
                keep_room(need)
                emit(("dest", hid, l, self._y))
                flow(lay, l, G[col], fs * 1.3, links=links)
                if lvl == 2:
                    self._y += 4.0
                    emit(("fill", l, self._y, W - l - r, 1.5, G["rule_h2"]))
                    self._y += 1.5
            elif kind == "p":
                _, markup, l, r, marker, style, links = it
                fs, col, bold = self.STYLE.get(style, self.STYLE["body"])
                fd = font(fs, bold)
                lay = layout(markup or " ", W - l - r, fd)
                mk = (layout(marker[0], None, fd), marker[1]) if marker else None
                flow(lay, l, G[col], fs * self.LEADING, marker=mk,
                     break_at=split_point(lay, fs * self.LEADING), links=links)
            elif kind == "code":
                _, text, l, r = it
                inner = l + self.BAR_W + 12.0
                lay = layout(text.rstrip("\n") or " ", W - inner - r - 12.0,
                             font(8.5, mono=True), plain=True)
                total = text_height(lay, 8.5 * 1.75) + 2 * self.BOXES["code"][3]
                if total <= H / 3:
                    keep_room(total)         # i blocchi brevi non si spezzano
                open_box("code", l, r, 8.5 * 1.75 * min(lay.get_line_count(), 2))
                flow(lay, inner, G["pre_fg"], 8.5 * 1.75)
                close_box()
            elif kind == "qopen":
                open_box("quote", it[1], it[2], self.BODY * self.LEADING * 2)
            elif kind == "qclose":
                if self._boxes:
                    close_box()
            elif kind == "hr":
                _, l, r = it
                emit(("fill", l, self._y, W - l - r, 0.75, G["rule"]))
                self._y += 0.75
            elif kind == "img":
                _, src, alt, l, r = it
                pix = self.load_image(src)
                if pix is None:
                    flow(layout(f'<span style="italic">{html.escape(alt or src)}</span>',
                                W - l - r, font(self.BODY)), l, G["footer"], self.BODY * self.LEADING)
                    continue
                avail = W - l - r
                pw, ph = pix.get_width(), pix.get_height()
                w = min(avail, pw * 0.75)              # 96 dpi → punti
                h = w * ph / pw
                if h > H:
                    w, h = w * H / h, H
                keep_room(h)
                emit(("img", pix, l + (avail - w) / 2, self._y, w, h))
                self._y += h
            elif kind == "table":
                table(*it[1:])
        while self._boxes:
            close_box()
        while len(self.pages) > 1 and not self.pages[-1]:
            self.pages.pop()
        op.set_n_pages(len(self.pages))

    # --------------------------------------------------------- disegno
    @staticmethod
    def _rgb(spec):
        c = Gdk.RGBA()
        c.parse(spec)
        return c.red, c.green, c.blue

    @staticmethod
    def _rounded(cr, x, y, w, h, rad):
        rad = max(0.0, min(rad, w / 2, h / 2))
        cr.new_sub_path()
        cr.arc(x + w - rad, y + rad, rad, -1.5708, 0)
        cr.arc(x + w - rad, y + h - rad, rad, 0, 1.5708)
        cr.arc(x + rad, y + h - rad, rad, 1.5708, 3.1416)
        cr.arc(x + rad, y + rad, rad, 3.1416, 4.7124)
        cr.close_path()

    def _gradient(self, x, y, w, h):
        """Sfumatura CSS linear-gradient(135deg, …) con punto medio al 50 %."""
        L = (w + h) / 2 ** 0.5
        cx, cy, d = x + w / 2, y + h / 2, 0.5 ** 0.5
        pat = cairo.LinearGradient(cx - d * L / 2, cy - d * L / 2, cx + d * L / 2, cy + d * L / 2)
        c0, c1, c2 = (self._rgb(c) for c in GUIDE["grad"])
        pat.add_color_stop_rgb(0.0, *c0)
        pat.add_color_stop_rgb(0.45, *c1)
        # Tra il 45 % e il 100 % il colore segue t^0,289 (punto medio al 50 %).
        for i in range(1, 11):
            t = i / 10
            k = t ** 0.289
            pat.add_color_stop_rgb(0.45 + 0.55 * t, *(a + (b - a) * k for a, b in zip(c1, c2)))
        return pat

    def _draw(self, op, ctx, page_nr):
        cr = ctx.get_cairo_context()
        M = self.MARGIN_PT
        cr.save()
        cr.translate(M, M)
        for item in self.pages[page_nr]:
            kind = item[0]
            if kind == "img":
                _, pix, x, y, w, h = item
                cr.save()
                cr.translate(x, y)
                cr.scale(w / pix.get_width(), h / pix.get_height())
                Gdk.cairo_set_source_pixbuf(cr, pix, 0, 0)
                cr.paint()
                cr.restore()
            elif kind == "fill":
                _, x, y, w, h, color = item
                cr.set_source_rgb(*self._rgb(color))
                cr.rectangle(x, y, w, h)
                cr.fill()
            elif kind == "box":
                _, x, y, w, h, bkind = item
                bg, bar, rad, _pad = self.BOXES[bkind]
                cr.save()
                self._rounded(cr, x, y, w, h, rad)
                cr.clip()
                cr.set_source_rgb(*self._rgb(GUIDE[bg]))
                cr.paint()
                cr.set_source_rgb(*self._rgb(GUIDE[bar]))
                cr.rectangle(x, y, self.BAR_W, h)
                cr.fill()
                cr.restore()
            elif kind == "grad":
                _, x, y, w, h = item
                cr.save()
                self._rounded(cr, x, y, w, h, 6.0)
                cr.set_source(self._gradient(x, y, w, h))
                cr.fill()
                cr.restore()
            elif kind == "line":
                _, line, x, y, color = item
                cr.set_source_rgb(*self._rgb(color))
                cr.move_to(x, y)
                PangoCairo.show_layout_line(cr, line)
            elif kind == "lay":
                _, lay, x, y, color = item
                cr.set_source_rgb(*self._rgb(color))
                cr.move_to(x, y)
                PangoCairo.show_layout(cr, lay)
            elif kind in ("link", "dest") and hasattr(cr, "tag_begin"):
                # Link e destinazioni del PDF (cairo >= 1.16): un'area
                # cliccabile sopra il testo, o un punto d'arrivo per i link
                # interni (#ancora). cairo vuole le coordinate della pagina,
                # senza le trasformazioni del contesto (margini): si
                # convertono con user_to_device.
                try:
                    if kind == "link":
                        _, x, y, w, h, url = item
                        x0, y0 = cr.user_to_device(x, y)
                        x1, y1 = cr.user_to_device(x + w, y + h)
                        rect = (f"rect=[{min(x0, x1):.2f} {min(y0, y1):.2f} "
                                f"{abs(x1 - x0):.2f} {abs(y1 - y0):.2f}] ")
                        cr.tag_begin(cairo.TAG_LINK, rect + _pdf_link_target(url, self._dests))
                        cr.tag_end(cairo.TAG_LINK)
                    else:
                        _, name, x, y = item
                        dx, dy = cr.user_to_device(x, y)
                        cr.tag_begin(cairo.TAG_DEST, f"name='{_cairo_str(name)}' "
                                                     f"x={dx:.2f} y={dy:.2f} internal")
                        cr.tag_end(cairo.TAG_DEST)
                except Exception:
                    pass
        cr.restore()
        # Piè di pagina: «titolo - pag. N / totale», centrato.
        lay = ctx.create_pango_layout()
        fd = Pango.FontDescription.from_string(GUIDE_FONT)
        fd.set_size(int(8 * Pango.SCALE))
        lay.set_font_description(fd)
        lay.set_text(footer_text(self.title, page_nr + 1, len(self.pages), self.t), -1)
        lay.set_width(int((self.PW - 2 * M) * Pango.SCALE))
        lay.set_ellipsize(Pango.EllipsizeMode.MIDDLE)
        lay.set_alignment(Pango.Alignment.CENTER)
        line = lay.get_line_readonly(0)
        x_off = lay.get_iter().get_line_extents()[1].x / Pango.SCALE   # include la centratura
        cr.set_source_rgb(*self._rgb(GUIDE["footer"]))
        cr.move_to(M + x_off, self.PH - self.FOOTER_PT)
        PangoCairo.show_layout_line(cr, line)
# ---- correzione dell'elisione (italiano, francese) -------------------------
_ELISION_FRAGMENTS = {
    "it": [
        "l", "un", "dell", "nell", "all", "dall", "sull", "coll", "pell",
        "quell", "quest", "bell", "sant", "tutt", "anch", "dov", "com",
        "cos", "po", "be", "mo", "ce", "ne", "se", "gliel", "me", "te",
        "buon", "gran", "fin", "senz", "grand", "vent", "cent",
    ],
    "fr": [
        "l", "d", "j", "n", "s", "c", "t", "m", "qu", "jusqu", "lorsqu",
        "puisqu", "quoiqu", "presqu", "quelqu", "aujourd",
    ],
}
_ELISION_LOCALES = {"it": "it_IT", "fr": "fr_FR"}

def _elision_words_for(base_lang):
    out = set()
    for w in _ELISION_FRAGMENTS.get(base_lang, []):
        out.add(w)
        out.add(w.capitalize())
        out.add(w.upper())
    return out

def _enchant_config_dir():
    env = os.environ.get("ENCHANT_CONFIG_DIR")
    if env:
        return env
    base = os.environ.get("XDG_CONFIG_HOME") or os.path.expanduser("~/.config")
    return os.path.join(base, "enchant")

_ELISION_SIDECAR_SUFFIX = ".ruscamark-added"

def ensure_elision_dictionaries(locales):
    """Assicura che <config>/<locale>.dic contenga i frammenti di elisione."""
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
        current, current_set, raw_lines = [], set(), []
        try:
            if os.path.exists(path):
                with open(path, "r", encoding="utf-8") as f:
                    for raw in f:
                        raw_lines.append(raw.rstrip("\n"))
                        line = raw.strip()
                        if not line or line.startswith("#"):
                            continue
                        if "#" in line:
                            line = line.split("#", 1)[0].strip()
                        if not line:
                            continue
                        w = line.split()[0]
                        if w and w not in current_set:
                            current.append(w)
                            current_set.add(w)
        except Exception:
            current, current_set, raw_lines = [], set(), []
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
        user_words = [w for w in current if w not in prev_ours]
        user_set = set(user_words)
        our_words = sorted(w for w in words if w not in user_set)
        desired = user_words + our_words
        if raw_lines == desired and prev_ours == set(our_words):
            continue
        try:
            with open(path, "w", encoding="utf-8") as f:
                for w in desired:
                    f.write(w + "\n")
            with open(sidecar, "w", encoding="utf-8") as f:
                f.write("# Parole aggiunte automaticamente da RuscaMark "
                        "(frammenti di elisione). Non modificare a mano.\n")
                for w in our_words:
                    f.write(w + "\n")
            written.append(path)
        except Exception:
            pass
    return written
# ----------------------------------------------------------------------------
# Icona e finestra «Informazioni» comuni ai RuscaLinux OS Tools
# ----------------------------------------------------------------------------
def theme_has_icon(name=APP_ID):
    display = Gdk.Display.get_default()
    return display is not None and Gtk.IconTheme.get_for_display(display).has_icon(name)


def ensure_icon():
    """Avvio dai sorgenti: se il tema non conosce l'icona, la copia nel tema
    hicolor dell'utente. Se non riesce, si resta senza icona."""
    dest = os.path.join(GLib.get_user_data_dir(), "icons", "hicolor", "scalable",
                        "apps", f"{APP_ID}.svg")
    if ICON_SRC is None or os.path.exists(dest):
        return
    try:
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        shutil.copyfile(ICON_SRC, dest)
    except OSError:
        pass


# Componenti esterni inclusi (specifiche, sezioni 3.10 e 6)
COMPONENTS = (
    # Regola dell'evidenziato ==testo==, nel file a sé markdown_it_mark.py
    ("markdown-it-mark", "MIT — Vitaly Puzrin, Alex Kocharin; ExecutableBookProject",
     "https://github.com/markdown-it/markdown-it-mark"),
)


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

# ----------------------------------------------------------------------------
class WidthAwareScrolledWindow(Gtk.ScrolledWindow):
    """ScrolledWindow che segnala ogni cambio di larghezza.

    In GTK 4 GtkWidget non ha una proprietà "width": il vecchio
    connect("notify::width") non scattava mai, quindi ridimensionando o
    massimizzando la finestra i margini restavano quelli calcolati
    all'avvio e il testo non era più centrato. Qui si intercetta
    size_allocate e si ricentra (in idle, fuori dal ciclo di layout)."""

    def __init__(self, on_width=None):
        super().__init__()
        self._on_width = on_width
        self._last_w = -1
        self._pending = 0

    def do_size_allocate(self, width, height, baseline):
        Gtk.ScrolledWindow.do_size_allocate(self, width, height, baseline)
        if width != self._last_w:
            self._last_w = width
            if self._on_width is not None and not self._pending:
                # Priorità più alta del ridisegno (120): i margini corretti
                # sono già in vigore nel frame successivo, senza sfarfallio.
                self._pending = GLib.idle_add(self._fire, priority=GLib.PRIORITY_HIGH_IDLE)

    def _fire(self):
        self._pending = 0
        if self._on_width is not None:
            self._on_width()
        return False
# ----------------------------------------------------------------------------
class RuscaWindow(Adw.ApplicationWindow):
    NATIVE_NAMES = {
        "af": "Afrikaans", "ar": "العربية", "az": "Azərbaycan",
        "be": "Беларуская", "bg": "Български", "bs": "Bosanski",
        "ca": "Català", "cs": "Čeština", "cy": "Cymraeg", "da": "Dansk",
        "de": "Deutsch", "el": "Ελληνικά", "en": "English", "es": "Español",
        "et": "Eesti", "eu": "Euskara", "fa": "فارسی", "fi": "Suomi",
        "fr": "Français", "ga": "Gaeilge", "gl": "Galego", "he": "עברית",
        "hi": "हिन्दी", "hr": "Hrvatski", "hu": "Magyar", "hy": "Հայերեն",
        "id": "Indonesia", "is": "Íslenska", "it": "Italiano",
        "ja": "日本語", "ka": "ქართული", "kk": "Қазақша", "ko": "한국어",
        "lt": "Lietuvių", "lv": "Latviešu", "mk": "Македонски",
        "mn": "Монгол", "nb": "Norsk bokmål", "nl": "Nederlands",
        "nn": "Norsk nynorsk", "pl": "Polski", "pt": "Português",
        "ro": "Română", "ru": "Русский", "sk": "Slovenčina",
        "sl": "Slovenščina", "sq": "Shqip", "sr": "Српски", "sv": "Svenska",
        "th": "ไทย", "tr": "Türkçe", "uk": "Українська", "vi": "Tiếng Việt",
        "zh": "中文",
    }
    LIVE_MAX_CHARS = 250000

    def __init__(self, app, path=None):
        super().__init__(application=app, title=APP_NAME)
        self.app = app
        self.cfg = load_config()
        if self.cfg.get("live", True) and self.cfg.get("show_preview", False):
            self.cfg["show_preview"] = False
        # La lingua dell'interfaccia segue quella del sistema (specifiche 9.2).
        self.lang = detect_system_language()
        self.tr = Translator(self.lang)
        self.t = self.tr.t
        self._img_cache = {}
        self._apply_default_direction()
        self.current_path = None
        self._refresh_id = 0
        self._live_id = 0
        self._closing = False
        self.word_count = 0
        self.spell_checker = None
        self.spell_error = None
        self._spell_adapter = None
        self._gspell_view = None
        self._spell_on = False
        self._spell_combo_loading = False
        self.set_default_size(self.cfg.get("win_w", 1240), self.cfg.get("win_h", 800))
        self.set_size_request(360, 294)
        self._build_actions()
        self._build_ui()
        self._build_search_bar()
        self._apply_theme()
        self._build_spell_panel()
        # Rispetta la scelta salvata: l'ortografia non si riaccende da sola.
        if self.cfg.get("spell_on", True):
            self._ensure_elision_for_spell()
            self._setup_spell()
        if not self.cfg.get("spell_panel_hidden", True):
            self.spell_revealer.set_reveal_child(True)
        self._sync_spell_ui()
        self._build_statusbar()
        self._setup_accels()
        self._apply_text_direction()
        self.connect("close-request", self._on_close_request)
        self.connect("notify::fullscreened", self._on_fullscreened)
        dt = Gtk.DropTarget.new(Gio.File, Gdk.DragAction.COPY)
        dt.connect("drop", self._on_drop)
        self.add_controller(dt)
        if path:
            self.load_file(path)
        elif not self.cfg.get("sample_shown", False):
            # Il documento dimostrativo solo al primo avvio; poi un documento
            # vuoto, come Testo di GNOME.
            self._load_sample()
            self.cfg["sample_shown"] = True
            save_config(self.cfg)
        else:
            self._reset_doc()
        self._schedule_refresh()
        GLib.timeout_add(120, self._init_paned)
        GLib.idle_add(self._center_page)

    # ------------------------------------------------------------- azioni
    def _build_actions(self):
        def plain(name, cb):
            a = Gio.SimpleAction.new(name)
            a.connect("activate", lambda *_: cb())
            self.add_action(a)

        def stateful(name, state, cb):
            a = Gio.SimpleAction.new_stateful(name, None, GLib.Variant.new_boolean(state))

            def _chg(action, value):
                action.set_state(value)
                cb(value.get_boolean())
            a.connect("change-state", _chg)
            self.add_action(a)
            return a
        plain("new-file", self._action_new)
        plain("open-file", self._action_open)
        plain("save-file", lambda: self.save_file())
        plain("save-as", lambda: self.save_file(as_new=True))
        plain("export-html", self._action_export_html)
        plain("export-pdf", self._action_export_pdf)
        plain("preferences", self._action_preferences)
        plain("goal", self._popup_goal)
        plain("about", self._action_about)
        plain("shortcuts", self._action_shortcuts)
        plain("undo", self._action_undo)
        plain("redo", self._action_redo)
        self.preview_action = stateful("toggle-preview", self.cfg.get("show_preview", False),
                                       self._set_preview)
        self.live_action = stateful("live-render", self.cfg.get("live", True), self._set_live)
        self.spell_action = stateful("spell-toggle", False, self._set_spell_on)
        self.fullscreen_action = stateful("fullscreen", False, self._set_fullscreen)
        plain("search", lambda: self._show_search(False))
        plain("replace", lambda: self._show_search(True))
        plain("fmt-bold", lambda: self._toggle_wrap("**"))
        plain("fmt-italic", lambda: self._toggle_wrap("*"))
        plain("insert-link", self._insert_link)
        plain("insert-image", self._action_insert_image)
        plain("insert-table", self._table_action)
        hd = Gio.SimpleAction.new("heading", GLib.VariantType.new("i"))
        hd.connect("activate", lambda _a, v: self._set_heading(v.get_int32()))
        self.add_action(hd)

    def _setup_accels(self):
        accels = {
            "win.new-file": ["<Primary>n"], "win.open-file": ["<Primary>o"],
            "win.save-file": ["<Primary>s"], "win.save-as": ["<Primary><Shift>s"],
            "win.export-html": ["<Primary><Shift>e"], "win.export-pdf": ["<Primary><Shift>p"], "win.toggle-preview": ["<Primary>p"],
            "win.live-render": ["<Primary>l"],
            "win.fullscreen": ["F11"], "win.spell-toggle": ["F7"],
            "win.undo": ["<Primary>z"], "win.redo": ["<Primary><Shift>z"],
            "win.search": ["<Primary>f"], "win.replace": ["<Primary>h"],
            "win.fmt-bold": ["<Primary>b"], "win.fmt-italic": ["<Primary>i"],
            "win.insert-link": ["<Primary>k"], "win.insert-image": ["<Primary><Shift>i"],
            "win.insert-table": ["<Primary><Shift>t"],
            "app.quit": ["<Primary>q"], "window.close": ["<Primary>w"],
            "win.preferences": ["<Primary>comma"], "win.shortcuts": ["<Primary>question"],
        }
        for n in range(0, 7):
            accels[f"win.heading({n})"] = [f"<Primary>{n}"]
        for act, keys in accels.items():
            self.app.set_accels_for_action(act, keys)

    # ------------------------------------------------------------- UI base
    def _build_ui(self):
        """Barra del titolo GNOME: a sinistra Nuovo e Apri, a destra menu
        principale, Salva e anteprima. Ricerca sopra il testo; pannello
        ortografico e barra di stato sotto. Ortografia e schermo intero
        stanno nel menu (F7, F11)."""
        self.hb = Adw.HeaderBar()
        self._hdr_tips = []
        for icon, act, tip, start in (("document-new-symbolic", "win.new-file", "tip_new", True),
                                      ("document-open-symbolic", "win.open-file", "tip_open", True)):
            b = Gtk.Button.new_from_icon_name(icon)
            b.set_action_name(act)
            self._hdr_tips.append((b, tip))
            self.hb.pack_start(b)
        self.mb = Gtk.MenuButton()
        self.mb.set_icon_name("open-menu-symbolic")
        self.mb.set_primary(True)
        self.mb.set_menu_model(self._build_menu())
        self.hb.pack_end(self.mb)
        save = Gtk.Button.new_from_icon_name("document-save-symbolic")
        save.set_action_name("win.save-file")
        self._hdr_tips.append((save, "tip_save"))
        self.hb.pack_end(save)
        self.preview_btn = Gtk.ToggleButton()
        self.preview_btn.set_icon_name("view-dual-symbolic")
        self.preview_btn.set_active(self.cfg.get("show_preview", False))
        self.preview_btn.connect("toggled", self._on_preview_btn)
        self.hb.pack_end(self.preview_btn)
        self._retranslate_header()
        self.paned = Gtk.Paned(orientation=Gtk.Orientation.HORIZONTAL)
        self.paned.set_wide_handle(True)
        self._build_editor()
        self._build_preview()
        self.editor_sw = WidthAwareScrolledWindow(self._center_page)
        self.editor_sw.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        self.editor_sw.set_child(self.view)
        self.editor_sw.set_vexpand(True)
        self.paned.set_start_child(self.editor_sw)
        self.paned.set_resize_start_child(True)
        self.paned.set_shrink_start_child(False)
        self.toasts = Adw.ToastOverlay(child=self.paned)
        self.toolbar = Adw.ToolbarView(content=self.toasts)
        self.toolbar.add_top_bar(self.hb)
        self.set_content(self.toolbar)

    def _retranslate_header(self):
        for b, key in self._hdr_tips:
            b.set_tooltip_text(self.t(key))
            b.update_property([Gtk.AccessibleProperty.LABEL], [self.t(key)])
        self.preview_btn.set_tooltip_text(self.t("tip_preview"))
        self.preview_btn.update_property([Gtk.AccessibleProperty.LABEL], [self.t("tip_preview")])
        self.mb.set_tooltip_text(self.t("main_menu"))

    def _on_preview_btn(self, btn):
        if btn.get_active() != self.preview_action.get_state().get_boolean():
            self.preview_action.activate()

    def _build_editor(self):
        if HAS_GSV:
            self.buffer = GtkSource.Buffer()
            self.view = GtkSource.View.new_with_buffer(self.buffer)
            self.view.set_show_line_numbers(False)
            self.view.set_highlight_current_line(False)
            self.view.set_auto_indent(True)
            self.view.set_smart_backspace(True)
            # Il gizmo del margine destro esiste solo se la pagina NON è
            # centrata: evita il warning GtkGizmo senza allocation all'avvio.
            self.view.set_right_margin_position(100)
            # === FIX: wrap orizzontale ===
            # Il default di GtkSource.View è WrapMode.NONE: senza questa
            # riga le righe non vanno a capo e la finestra scorre a destra.
            self.view.set_wrap_mode(Gtk.WrapMode.WORD_CHAR)
            # === FIX: margini immediati ===
            # Margini simmetrici già prima che _center_page() li ricalcoli.
            self.view.set_left_margin(16)
            self.view.set_right_margin(16)
            self.view.set_top_margin(14)
            self.view.set_bottom_margin(14)
            try:
                self.view.set_smart_home_end(GtkSource.SmartHomeEndType.ALWAYS)
            except Exception:
                pass
        else:
            self.buffer = Gtk.TextBuffer()
            self.view = Gtk.TextView.new_with_buffer(self.buffer)
            self.view.set_wrap_mode(Gtk.WrapMode.WORD_CHAR)
            self.view.set_left_margin(16); self.view.set_right_margin(16)
            self.view.set_top_margin(14); self.view.set_bottom_margin(14)
        self.buffer.connect("changed", self._schedule_refresh)
        self.buffer.connect("changed", self._schedule_live)
        self.buffer.connect("mark-set", self._on_mark_set)
        self.buffer.connect("modified-changed", self._update_title)
        self.view.add_css_class("ruscamark-editor")
        self.view.connect("realize", lambda *_: (
            GLib.idle_add(self._center_page),
            GLib.timeout_add(250, self._center_page),
        ))
        self._live_sync_language()

    def _build_preview(self):
        self.preview_buffer = Gtk.TextBuffer()
        self.preview_view = Gtk.TextView.new_with_buffer(self.preview_buffer)
        self.preview_view.set_editable(False)
        self.preview_view.set_cursor_visible(False)
        self.preview_view.set_focusable(False)
        self.preview_view.set_wrap_mode(Gtk.WrapMode.WORD_CHAR)
        self.preview_view.set_left_margin(22); self.preview_view.set_right_margin(22)
        self.preview_view.set_top_margin(18); self.preview_view.set_bottom_margin(18)
        self.preview_view.add_css_class("preview")
        # Codice e tabelle a griglia restano compatti: le cornici e gli sfondi
        # delle righe consecutive devono toccarsi.
        self._pv_nowrap = self.preview_buffer.create_tag(
            "pv-nowrap", wrap_mode=Gtk.WrapMode.NONE, pixels_above_lines=0,
            pixels_below_lines=0, pixels_inside_wrap=0)
        self.preview_sw = WidthAwareScrolledWindow(self._center_page)
        self.preview_sw.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        self.preview_sw.set_child(self.preview_view)
        if self.cfg.get("show_preview", False):
            self.paned.set_end_child(self.preview_sw)
            self.paned.set_resize_end_child(True)
            self.paned.set_shrink_end_child(False)

    def _init_paned(self):
        try:
            pos = self.cfg.get("paned", 0) or max(520, self.get_width() * 55 // 100)
            self.paned.set_position(pos)
        except Exception:
            pass
        return False

    def _build_menu(self):
        """Menu principale: file, vista, formato, strumenti, applicazione.
        Apri e Salva sono già nella barra del titolo."""
        menu = Gio.Menu()
        s1 = Gio.Menu()
        s1.append(self.t("mi_save_as"), "win.save-as")
        s1.append(self.t("mi_export_html"), "win.export-html")
        s1.append(self.t("mi_export_pdf"), "win.export-pdf")
        menu.append_section(None, s1)
        s2 = Gio.Menu()
        s2.append(self.t("mi_live"), "win.live-render")
        s2.append(self.t("mi_preview"), "win.toggle-preview")
        s2.append(self.t("mi_spell"), "win.spell-toggle")
        s2.append(self.t("mi_fullscreen"), "win.fullscreen")
        menu.append_section(None, s2)
        fmt = Gio.Menu()
        fmt.append(self.t("mi_bold"), "win.fmt-bold")
        fmt.append(self.t("mi_italic"), "win.fmt-italic")
        heads = Gio.Menu()
        heads.append(self.t("mi_paragraph"), "win.heading(0)")
        for n in range(1, 7):
            heads.append(self.t("mi_heading_n", n=n), f"win.heading({n})")
        fmt.append_submenu(self.t("mi_heading"), heads)
        fmt.append(self.t("mi_link"), "win.insert-link")
        fmt.append(self.t("mi_image"), "win.insert-image")
        fmt.append(self.t("mi_table"), "win.insert-table")
        s3 = Gio.Menu()
        s3.append_submenu(self.t("mi_format"), fmt)
        s3.append(self.t("mi_find"), "win.search")
        s3.append(self.t("mi_replace"), "win.replace")
        s3.append(self.t("mi_goal"), "win.goal")
        menu.append_section(None, s3)
        s4 = Gio.Menu()
        s4.append(self.t("mi_preferences"), "win.preferences")
        s4.append(self.t("shortcuts"), "win.shortcuts")
        s4.append(self.t("mi_about"), "win.about")
        menu.append_section(None, s4)
        return menu

    # ------------------------------------------------------- tema e font
    @staticmethod
    def _is_dark():
        return Adw.StyleManager.get_default().get_dark()

    def _palette(self):
        return DARK if self._is_dark() else LIGHT

    def _preview_palette(self):
        return DARK if self._is_dark() else PREVIEW_GUIDE

    def _apply_spacing(self):
        """Interlinea come line-height in CSS: lo spazio oltre quello naturale
        del font (~1,2 volte il corpo) va metà sopra e metà sotto ogni riga
        del documento, e per intero fra le righe che vanno a capo."""
        factor = LINE_SPACING.get(self.cfg.get("line_spacing", "normal"), LINE_SPACING["normal"])
        px = float(self.cfg.get("font_size", 13)) * 96.0 / 72.0
        extra = max(0, int(round(px * (factor - 1.2))))
        for view in (getattr(self, "view", None), getattr(self, "preview_view", None)):
            if view is None:
                continue
            view.set_pixels_inside_wrap(extra)
            view.set_pixels_above_lines(extra // 2)
            view.set_pixels_below_lines(extra - extra // 2)

    def _apply_theme(self):
        dark = self._is_dark()
        c = self._palette()
        defs = "\n".join(f"@define-color {k} {v};" for k, v in c.items())
        css = defs + "\n" + CSS_TEMPLATE
        css = css.replace("__FONT__", self.cfg.get("font", "Sans"))
        css = css.replace("__SIZE__", str(self.cfg.get("font_size", 13)))
        if not dark:
            css += (f"\n.preview, .preview text {{ background-color: {GUIDE['page']};"
                    f" color: {GUIDE['fg']}; }}\n")
        if getattr(self, "_css_provider", None):
            try:
                Gtk.StyleContext.remove_provider_for_display(
                    Gdk.Display.get_default(), self._css_provider)
            except Exception:
                pass
        provider = Gtk.CssProvider()
        provider.load_from_string(css)
        Gtk.StyleContext.add_provider_for_display(
            Gdk.Display.get_default(), provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)
        self._css_provider = provider
        if HAS_GSV:
            try:
                mgr = GtkSource.StyleSchemeManager.get_default()
                paths = list(mgr.get_search_path() or [])
                if STYLES_DIR not in paths:
                    paths.append(STYLES_DIR)
                mgr.set_search_path(paths)
                scheme = mgr.get_scheme("ruscamark-dark" if dark else "ruscamark-light")
                if scheme is None:
                    scheme = mgr.get_scheme("oblivion" if dark else "classic")
                self.buffer.set_style_scheme(scheme)
            except Exception:
                pass
        try:
            c = self._palette()
            self.search_tag.set_property("background", c["hover"])
            self.search_cur_tag.set_property("background", c["accent"])
            self.search_cur_tag.set_property("foreground", c["accent_fg"])
        except Exception:
            pass
        self._apply_spacing()
        self._live_make_tags()
        self._live_restyle()
        self._center_page()
        # Il nuovo font CSS vale dal prossimo ciclo di stile: si ricentra
        # anche dopo, quando le metriche sono quelle aggiornate.
        GLib.timeout_add(80, self._center_page)
        self._schedule_refresh()

    def _set_style(self, style):
        """Stile chiaro/scuro: segue GNOME o è forzato. Il cambio arriva a
        _apply_theme tramite Adw.StyleManager:dark (vedi RuscaApplication)."""
        self.cfg["style"] = style
        Adw.StyleManager.get_default().set_color_scheme({
            "light": Adw.ColorScheme.FORCE_LIGHT,
            "dark": Adw.ColorScheme.FORCE_DARK,
        }.get(style, Adw.ColorScheme.DEFAULT))
        save_config(self.cfg)

    # ------------------------------------------------------- anteprima/live/pagina
    def _set_preview(self, show):
        show = bool(show)
        if show and self.cfg.get("live", False):
            self.live_action.change_state(GLib.Variant.new_boolean(False))
        self.cfg["show_preview"] = show
        if show:
            self.paned.set_end_child(self.preview_sw)
            self.paned.set_resize_end_child(True)
            GLib.timeout_add(50, self._init_paned)
            self._refresh_preview()
        else:
            try:
                self.paned.set_end_child(None)
            except Exception:
                pass
        self.preview_btn.set_active(show)
        GLib.idle_add(self._center_page)
        save_config(self.cfg)

    def _set_live(self, on):
        on = bool(on)
        if on and self.cfg.get("show_preview", False):
            self.preview_action.change_state(GLib.Variant.new_boolean(False))
        self.cfg["live"] = on
        save_config(self.cfg)
        self._live_sync_language()
        self._live_restyle()

    def _char_width(self):
        """Larghezza media di un carattere del font dell'editor.

        Prima si usava la larghezza della cifra "0", più larga della media
        delle lettere: con i font proporzionali una pagina da 68 "caratteri"
        ne conteneva in realtà ~80. Le metriche Pango danno la media vera."""
        try:
            m = self.view.get_pango_context().get_metrics(None, None)
            w = m.get_approximate_char_width() / Pango.SCALE
            if w > 1:
                return w
        except Exception:
            pass
        try:
            sample = "abcdefghijklmnopqrstuvwxyz ABCDEFGHIJ"
            layout = self.view.create_pango_layout(sample)
            return max(4.0, layout.get_pixel_size().width / len(sample))
        except Exception:
            return 8.0

    @staticmethod
    def _viewport_width(sw):
        """Larghezza visibile: senza scrollbar sovrapposte (es. accessibilità)
        la barra verticale occupa spazio e va sottratta, altrimenti il testo
        risulta spostato a sinistra di metà barra."""
        w = sw.get_width()
        try:
            if not sw.get_overlay_scrolling():
                sb = sw.get_vscrollbar()
                if sb is not None and sb.get_visible():
                    w -= sb.get_width()
        except Exception:
            pass
        return w

    @staticmethod
    def _page_margins(avail, page):
        """Margini in funzione della larghezza disponibile.

        - laterale minimo proporzionale (4% della larghezza, 16..48 px), così
          le finestre strette non incollano il testo ai bordi;
        - con pagina centrata il resto dello spazio va diviso a metà;
        - verticale proporzionale (3%, 14..48 px)."""
        min_side = int(min(48, max(16, avail * 0.04)))
        side = max(min_side, int(avail - page) // 2) if page else min_side
        vert = int(min(48, max(14, avail * 0.03)))
        return side, vert

    @staticmethod
    def _set_margins(view, side, vert):
        # Solo se cambiano: evita relayout inutili ad ogni allocazione.
        if view.get_left_margin() != side:
            view.set_left_margin(side)
        if view.get_right_margin() != side:
            view.set_right_margin(side)
        if view.get_top_margin() != vert:
            view.set_top_margin(vert)
        if view.get_bottom_margin() != vert:
            view.set_bottom_margin(vert)

    def _center_page(self, *_):
        if not getattr(self, "editor_sw", None) or not getattr(self, "preview_sw", None):
            return False
        if not self.view.get_realized():
            return False      # ci pensano realize e la prima allocazione
        centred = self.cfg.get("center_page", True)
        chars = int(self.cfg.get("page_chars", 80))
        page = int(self._char_width() * chars) if centred else 0
        if HAS_GSV:
            # Pagina libera: guida verticale alla larghezza di pagina scelta.
            self.view.set_right_margin_position(chars)
            self.view.set_show_right_margin(not centred)
        for sw, view in ((self.editor_sw, self.view), (self.preview_sw, self.preview_view)):
            avail = self._viewport_width(sw)
            if avail <= 1:
                continue
            side, vert = self._page_margins(avail, page)
            self._set_margins(view, side, vert)
        # Le tabelle dell'anteprima hanno la larghezza della pagina: se questa
        # cambia si ricompone l'anteprima (una volta, a ridimensionamento finito).
        if (getattr(self, "_pv_has_table", False) and self.cfg.get("show_preview", False)
                and abs(self._preview_text_width() - getattr(self, "_pv_width", 0)) > 4
                and not getattr(self, "_pv_rerender_id", 0)):
            self._pv_rerender_id = GLib.timeout_add(150, self._pv_rerender)
        if os.environ.get("RUSCA_DEBUG"):
            print(f"[center] ew={self._viewport_width(self.editor_sw)} page={page} "
                  f"char={self._char_width():.2f} margin={self.view.get_left_margin()}")
        return False

    def _set_fullscreen(self, fs):
        if fs:
            self.fullscreen()
        else:
            self.unfullscreen()

    def _on_fullscreened(self, *_):
        fs = self.is_fullscreen() if hasattr(self, "is_fullscreen") else self.props.fullscreened
        if fs:
            try:
                self.paned.set_end_child(None)
            except Exception:
                pass
            self.statusbar.set_visible(False)
            self.toolbar.set_reveal_top_bars(False)
            self._spell_panel_pre_fs = self.spell_revealer.get_reveal_child()
            self.spell_revealer.set_reveal_child(False)
        else:
            if self.cfg.get("show_preview", False):
                self.paned.set_end_child(self.preview_sw)
                self.paned.set_resize_end_child(True)
                GLib.timeout_add(50, self._init_paned)
            self.statusbar.set_visible(True)
            self.toolbar.set_reveal_top_bars(True)
            self.spell_revealer.set_reveal_child(
                bool(getattr(self, "_spell_panel_pre_fs", False)))
            GLib.idle_add(self._center_page)
        self.fullscreen_action.set_state(GLib.Variant.new_boolean(fs))

    # ------------------------------------------------------- barra di stato
    def _build_statusbar(self):
        bar = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        bar.set_margin_start(12); bar.set_margin_end(6)
        bar.set_margin_top(3); bar.set_margin_bottom(3)
        self.count_label = Gtk.Label(label="")
        self.count_label.add_css_class("dim-label")
        self.count_label.add_css_class("numeric")
        # Su finestre strette il conteggio si accorcia invece di allargarle.
        self.count_label.set_ellipsize(Pango.EllipsizeMode.END)
        self.count_label.set_hexpand(True)
        self.count_label.set_xalign(0)
        bar.append(self.count_label)
        spacer = Gtk.Box(); spacer.set_hexpand(True)
        bar.append(spacer)
        self.cursor_label = Gtk.Label(label="")
        self.cursor_label.add_css_class("dim-label")
        self.cursor_label.add_css_class("numeric")
        bar.append(self.cursor_label)
        self.goal_button = Gtk.Button()
        self.goal_button.add_css_class("flat")
        self.goal_button.connect("clicked", lambda *_: self._popup_goal())
        bar.append(self.goal_button)
        self.goal_progress = Gtk.ProgressBar()
        self.goal_progress.set_size_request(120, -1)
        self.goal_progress.set_valign(Gtk.Align.CENTER)
        self.goal_progress.set_fraction(0.0)
        bar.append(self.goal_progress)
        self.goal_label = Gtk.Label(label="")
        bar.append(self.goal_label)
        self.statusbar = bar
        self.toolbar.add_bottom_bar(bar)
        self._build_goal_popover()
        self._update_goal_widgets(0)

    def _build_goal_popover(self):
        pop = Gtk.Popover()
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        box.set_margin_start(12); box.set_margin_end(12)
        box.set_margin_top(10); box.set_margin_bottom(10)
        self.goal_pop_label = Gtk.Label(label="")
        self.goal_pop_label.set_xalign(0)
        self.goal_spin = Gtk.SpinButton.new_with_range(0, 1000000, 50)
        self.goal_spin.set_digits(0)
        self.goal_spin.set_value(self.cfg.get("goal", 0))
        self.goal_apply_btn = Gtk.Button.new_with_label("")
        self.goal_apply_btn.connect("clicked", self._apply_goal)
        box.append(self.goal_pop_label); box.append(self.goal_spin)
        box.append(self.goal_apply_btn)
        pop.set_child(box)
        pop.set_parent(self.goal_button)
        self.goal_popover = pop
        self.goal_button.set_tooltip_text(self.t("goal_tip"))
        self.goal_pop_label.set_text(self.t("goal_pop_title"))
        self.goal_apply_btn.set_label(self.t("btn_apply"))

    def _popup_goal(self):
        self.goal_spin.set_value(self.cfg.get("goal", 0))
        self.goal_popover.popup()

    def _apply_goal(self, *_):
        self.cfg["goal"] = int(self.goal_spin.get_value())
        save_config(self.cfg)
        self.goal_popover.popdown()
        self._update_counts()

    def _update_goal_widgets(self, words):
        goal = self.cfg.get("goal", 0)
        if goal > 0:
            self.goal_progress.set_fraction(min(1.0, words / goal))
            self.goal_button.set_label(self.t("goal_label", w=words, g=goal))
            if words >= goal:
                self.goal_label.set_markup(
                    f'<span weight="bold">{html.escape(self.t("goal_done"))}</span>')
                self.goal_progress.add_css_class("goal-done")
            else:
                self.goal_label.set_label(self.t("goal_missing", n=goal - words))
                self.goal_progress.remove_css_class("goal-done")
            self.goal_progress.set_visible(True)
            self.goal_label.set_visible(True)
        else:
            self.goal_button.set_label(self.t("goal_idle"))
            self.goal_progress.set_visible(False)
            self.goal_label.set_visible(False)

    # ------------------------------------------------------- ricerca e sostituzione
    def _build_search_bar(self):
        self.search_revealer = Gtk.Revealer()
        self.search_revealer.set_transition_type(Gtk.RevealerTransitionType.SLIDE_DOWN)
        bar = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        bar.set_margin_start(6); bar.set_margin_end(6)
        bar.set_margin_top(6); bar.set_margin_bottom(6)
        self.search_entry = Gtk.SearchEntry()
        self.search_entry.set_hexpand(True)
        self.search_entry.connect("search-changed", lambda *_: self._refresh_search())
        self.search_entry.connect("activate", lambda *_: self._search_next())
        self.search_entry.connect("stop-search", lambda *_: self._hide_search())
        bar.append(self.search_entry)
        self.replace_entry = Gtk.Entry()
        self.replace_entry.set_hexpand(True)
        self.replace_entry.set_visible(False)
        self.replace_entry.connect("activate", lambda *_: self._replace_one())
        bar.append(self.replace_entry)
        self.case_btn = Gtk.ToggleButton(label="Aa")
        self.case_btn.connect("toggled", lambda *_: self._refresh_search())
        bar.append(self.case_btn)
        self._btn_prev = Gtk.Button.new_from_icon_name("go-up-symbolic")
        self._btn_prev.connect("clicked", lambda *_: self._search_prev())
        bar.append(self._btn_prev)
        self._btn_next = Gtk.Button.new_from_icon_name("go-down-symbolic")
        self._btn_next.connect("clicked", lambda *_: self._search_next())
        bar.append(self._btn_next)
        self.replace_btn = Gtk.Button()
        self.replace_btn.set_visible(False)
        self.replace_btn.connect("clicked", lambda *_: self._replace_one())
        bar.append(self.replace_btn)
        self.replace_all_btn = Gtk.Button()
        self.replace_all_btn.set_visible(False)
        self.replace_all_btn.connect("clicked", lambda *_: self._replace_all())
        bar.append(self.replace_all_btn)
        self.search_status = Gtk.Label(label="")
        self.search_status.set_xalign(0)
        self.search_status.set_hexpand(True)
        self.search_status.set_ellipsize(Pango.EllipsizeMode.END)
        bar.append(self.search_status)
        for b in (self.case_btn, self._btn_prev, self._btn_next):
            b.add_css_class("flat")
        self._btn_search_close = Gtk.Button.new_from_icon_name("window-close-symbolic")
        self._btn_search_close.add_css_class("flat")
        self._btn_search_close.connect("clicked", lambda *_: self._hide_search())
        bar.append(self._btn_search_close)
        self.search_revealer.set_child(bar)
        self.toolbar.add_top_bar(self.search_revealer)
        self._search_ctx = None
        self.search_tag = self.buffer.create_tag("search-match", background=LIGHT["hover"])
        self.search_cur_tag = self.buffer.create_tag("search-current",
                                                     background=LIGHT["accent"],
                                                     foreground=LIGHT["accent_fg"])
        self._retranslate_search()

    def _retranslate_search(self):
        self.search_entry.set_placeholder_text(self.t("find_placeholder"))
        self.replace_entry.set_placeholder_text(self.t("replace_placeholder"))
        self.case_btn.set_tooltip_text(self.t("tip_case"))
        self._btn_prev.set_tooltip_text(self.t("tip_prev"))
        self._btn_next.set_tooltip_text(self.t("tip_next"))
        self.replace_btn.set_label(self.t("btn_replace"))
        self.replace_all_btn.set_label(self.t("btn_replace_all"))
        self.replace_all_btn.set_tooltip_text(self.t("tip_replace_all"))
        self._btn_search_close.set_tooltip_text(self.t("tip_close"))

    def _search_flags(self):
        flags = Gtk.TextSearchFlags.VISIBLE_ONLY
        if not self.case_btn.get_active():
            flags |= Gtk.TextSearchFlags.CASE_INSENSITIVE
        return flags

    # --------------------------------------------------------- GTK 4 search helpers
    def _find_next(self, start_iter, needle, flags, wrap=True):
        """GTK 4: la ricerca vive su Gtk.TextIter, non più sul TextBuffer.
        Ritorna (match_start, match_end) oppure None. Con wrap=True, se non
        trova nulla a partire da start_iter, ricomincia dall'inizio."""
        if not needle:
            return None
        res = start_iter.forward_search(needle, flags, None)
        if res or not wrap:
            return res
        if start_iter.is_start():
            return None
        return self.buffer.get_start_iter().forward_search(needle, flags, None)

    def _find_prev(self, start_iter, needle, flags, wrap=True):
        """Come _find_next ma all'indietro (Gtk.TextIter.backward_search)."""
        if not needle:
            return None
        res = start_iter.backward_search(needle, flags, None)
        if res or not wrap:
            return res
        if start_iter.is_end():
            return None
        return self.buffer.get_end_iter().backward_search(needle, flags, None)

    def _show_search(self, with_replace):
        self.search_revealer.set_reveal_child(True)
        for w in (self.replace_entry, self.replace_btn, self.replace_all_btn):
            w.set_visible(with_replace)
        self.search_entry.grab_focus()
        self._refresh_search()

    def _hide_search(self):
        self.search_revealer.set_reveal_child(False)
        if self._search_ctx is not None:
            try:
                self._search_ctx.set_highlight(False)
            except Exception:
                pass
        self._search_ctx = None
        b, e = self.buffer.get_bounds()
        self.buffer.remove_tag(self.search_tag, b, e)
        self.buffer.remove_tag(self.search_cur_tag, b, e)
        self.search_status.set_label("")
        self.view.grab_focus()

    def _refresh_search(self, *_):
        needle = self.search_entry.get_text()
        buf = self.buffer
        b, e = buf.get_bounds()
        buf.remove_tag(self.search_tag, b, e)
        buf.remove_tag(self.search_cur_tag, b, e)
        if self._search_ctx is not None:
            try:
                self._search_ctx.set_highlight(False)
            except Exception:
                pass
            self._search_ctx = None
        count = 0
        if needle:
            if HAS_GSV:
                try:
                    st = GtkSource.SearchSettings()
                    st.set_search_text(needle)
                    st.set_case_sensitive(self.case_btn.get_active())
                    st.set_wrap_around(True)
                    ctx = GtkSource.SearchContext.new(buf, st)
                    ctx.set_highlight(True)
                    ctx.connect("notify::occurrences-count",
                                lambda c, _p: self.search_status.set_label(
                                    self.t("st_results", n=c.get_occurrences_count())))
                    self._search_ctx = ctx
                    count = ctx.get_occurrences_count()
                except Exception:
                    self._search_ctx = None
            if self._search_ctx is None:
                count = self._highlight_fallback(needle)
            self.search_status.set_label(
                self.t("st_results", n=count) if count else self.t("st_no_results"))
        else:
            self.search_status.set_label("")
        return count

    def _highlight_fallback(self, needle):
        """Evidenzia tutte le occorrenze usando TextIter.forward_search (GTK 4)."""
        buf = self.buffer
        start = buf.get_start_iter()
        flags = self._search_flags()
        count = 0
        while count < 500:
            res = start.forward_search(needle, flags, None)
            if not res:
                break
            ms, me = res
            buf.apply_tag(self.search_tag, ms, me)
            start = me
            count += 1
        return count

    def _mark_current(self, ms, me):
        b, e = self.buffer.get_bounds()
        self.buffer.remove_tag(self.search_cur_tag, b, e)
        self.buffer.apply_tag(self.search_cur_tag, ms, me)
        self.buffer.select_range(ms, me)
        self.view.scroll_to_mark(self.buffer.get_insert(), 0.15, True, 0.0, 0.5)

    def _search_next(self):
        needle = self.search_entry.get_text()
        if not needle:
            self.search_entry.grab_focus()
            return
        buf = self.buffer
        it = buf.get_iter_at_mark(buf.get_insert())
        if self._search_ctx is not None:
            try:
                ok, ms, me, _ = self._search_ctx.forward(it)
                if ok:
                    self._mark_current(ms, me)
                else:
                    self.search_status.set_label(self.t("st_no_results"))
            except Exception:
                # Fallback se l'API GtkSource cambia: uso TextIter.
                res = self._find_next(it, needle, self._search_flags())
                if res:
                    self._mark_current(res[0], res[1])
                else:
                    self.search_status.set_label(self.t("st_no_results"))
            return
        res = self._find_next(it, needle, self._search_flags())
        if res:
            self._mark_current(res[0], res[1])
        else:
            self.search_status.set_label(self.t("st_no_results"))

    def _search_prev(self):
        needle = self.search_entry.get_text()
        if not needle:
            self.search_entry.grab_focus()
            return
        buf = self.buffer
        it = buf.get_iter_at_mark(buf.get_insert())
        if self._search_ctx is not None:
            try:
                ok, ms, me, _ = self._search_ctx.backward(it)
                if ok:
                    self._mark_current(ms, me)
                else:
                    self.search_status.set_label(self.t("st_no_results"))
            except Exception:
                res = self._find_prev(it, needle, self._search_flags())
                if res:
                    self._mark_current(res[0], res[1])
                else:
                    self.search_status.set_label(self.t("st_no_results"))
            return
        res = self._find_prev(it, needle, self._search_flags())
        if res:
            self._mark_current(res[0], res[1])
        else:
            self.search_status.set_label(self.t("st_no_results"))

    def _replace_range(self, ms, me):
        """Sostituisce l'intervallo ms..me con il testo della casella
        "Sostituisci con…" e posiziona il cursore dopo l'inserimento.
        Ritorna l'offset finale (subito dopo il testo inserito)."""
        buf = self.buffer
        rep = self.replace_entry.get_text()
        off = ms.get_offset()
        buf.begin_user_action()
        buf.delete(ms, me)
        buf.insert(buf.get_iter_at_offset(off), rep)
        buf.end_user_action()
        end_off = off + len(rep)
        buf.place_cursor(buf.get_iter_at_offset(end_off))
        return end_off

    def _replace_one(self):
        """Sostituisce la selezione se coincide con la ricerca, altrimenti
        trova l'occorrenza successiva (con wrap) e la sostituisce."""
        buf = self.buffer
        needle = self.search_entry.get_text()
        if not needle:
            self.search_entry.grab_focus()
            return
        case = self.case_btn.get_active()

        def same(txt):
            return (txt == needle) if case else (txt.lower() == needle.lower())
        sel = buf.get_selection_bounds()
        if sel and same(sel[0].get_text(sel[1])):
            self._replace_range(sel[0], sel[1])
            self._refresh_search()
            self._search_next()
            return
        it = buf.get_iter_at_mark(buf.get_insert())
        res = self._find_next(it, needle, self._search_flags())
        if not res:
            self.search_status.set_label(self.t("st_no_results"))
            return
        self._replace_range(res[0], res[1])
        self._refresh_search()
        self._search_next()

    def _replace_all(self):
        """Sostituisce tutte le occorrenze in un unico passo di Annulla.
        Usa TextIter.forward_search (GTK 4) e riparte sempre DOPO il testo
        appena inserito, così evita loop se la sostituzione contiene il
        testo cercato."""
        buf = self.buffer
        needle = self.search_entry.get_text()
        if not needle:
            self.search_entry.grab_focus()
            return
        rep = self.replace_entry.get_text()
        flags = self._search_flags()
        start = buf.get_start_iter()
        n = 0
        buf.begin_user_action()
        try:
            while n < 100000:
                res = start.forward_search(needle, flags, None)
                if not res:
                    break
                ms, me = res
                off = ms.get_offset()
                buf.delete(ms, me)
                buf.insert(buf.get_iter_at_offset(off), rep)
                start = buf.get_iter_at_offset(off + len(rep))
                n += 1
        finally:
            buf.end_user_action()
        self._refresh_search()
        if n > 0:
            self.search_status.set_label(self.t("st_replaced", n=n))
        else:
            self.search_status.set_label(self.t("st_no_results"))

    # ------------------------------------------------------- conteggi
    def _schedule_refresh(self, *_):
        if self._refresh_id:
            GLib.source_remove(self._refresh_id)
        self._refresh_id = GLib.timeout_add(250, self._do_refresh)
        return False

    def _do_refresh(self):
        self._refresh_id = 0
        self._update_counts()
        self._refresh_preview()
        return False

    def _get_text(self):
        return self.buffer.get_text(self.buffer.get_start_iter(),
                                    self.buffer.get_end_iter(), True)

    def _set_buffer_text(self, text):
        """Sostituisce tutto il contenuto in modo atomico.
        - Se disponibile (GtkSourceView 5), usa le azioni non-undoable, così
          il caricamento non entra nella cronologia di Annulla.
        - Altrimenti chiama set_text() da solo: è già atomico e, non essendo
          annidato in una user-action esterna, non genera i warning GTK
          'Cannot begin/end irreversible action while in user action'.
        """
        buf = self.buffer
        begin = getattr(buf, "begin_not_undoable_action", None)
        end = getattr(buf, "end_not_undoable_action", None)
        if callable(begin) and callable(end):
            begin()
            buf.set_text(text)
            end()
        else:
            buf.set_text(text)
        buf.place_cursor(buf.get_start_iter())

    def _update_counts(self):
        text = self._get_text()
        words = len([t for t in text.split() if any(ch.isalnum() for ch in t)])
        self.word_count = words
        self.count_label.set_label(self.t("st_counts", w=words, c=len(text),
                                          l=self.buffer.get_line_count()))
        self._update_goal_widgets(words)

    def _refresh_preview(self):
        if not self.cfg.get("show_preview", False):
            return
        pb = self.preview_buffer
        pb.set_text("")
        try:
            items = MarkdownDoc(self._get_text()).to_preview(self._preview_palette(), t=self.t)
        except Exception as e:
            print(f"[ruscamark] anteprima: {e}", file=sys.stderr)
            pb.set_text(self._get_text())
            return
        c = self._preview_palette()
        self._pv_width = self._preview_text_width()
        self._pv_has_table = False
        for idx, it in enumerate(items):
            if idx:
                pb.insert(pb.get_end_iter(), "\n")
            if it[0] == "table":
                anchor = pb.create_child_anchor(pb.get_end_iter())
                self.preview_view.add_child_at_anchor(self._pv_table_widget(*it[1:]), anchor)
                self._pv_has_table = True
                continue
            if it[0] == "m":
                start = pb.get_char_count()
                self._insert_markup(pb, it[1])
                if it[2]:
                    pb.apply_tag(self._pv_nowrap, pb.get_iter_at_offset(start), pb.get_end_iter())
                continue
            _, src, alt, prefix = it
            if prefix:
                self._insert_markup(pb, prefix)
            tex, msg = self._image_texture(src, alt)
            if tex is not None:
                pb.insert_paintable(pb.get_end_iter(), tex)
            else:
                self._insert_markup(pb, f'<span foreground="{c["subtle"]}" style="italic">'
                                        f'🖼 {html.escape(msg)}</span>')

    def _pv_table_widget(self, aligns, header, rows):
        """Tabella dell'anteprima: griglia larga quanto la pagina, celle che
        vanno a capo, intestazione in grassetto, righe separate come nelle
        liste di GNOME. Prima era testo a spaziatura fissa senza a capo:
        con celle lunghe la riga usciva dalla pagina."""
        ncol = len(header)
        grid = Gtk.Grid(hexpand=True)
        xalign = {"right": 1.0, "center": 0.5}
        for r, cells in enumerate([header] + rows):
            for ci, cell in enumerate(cells):
                markup = f"<b>{cell}</b>" if r == 0 else cell
                label = Gtk.Label(wrap=True, wrap_mode=Pango.WrapMode.WORD_CHAR,
                                  selectable=True, hexpand=True, valign=Gtk.Align.START,
                                  margin_start=12, margin_end=12,
                                  margin_top=8, margin_bottom=8)
                # larghezza naturale = contenuto (al massimo 50 caratteri):
                # le colonne si dividono lo spazio in proporzione al testo
                label.set_max_width_chars(
                    min(max(len(re.sub(r"<[^>]+>", "", markup)), 4), 50))
                label.set_xalign(xalign.get(aligns[ci] if ci < len(aligns) else None, 0.0))
                try:
                    Pango.parse_markup(markup, -1, "\0")
                    label.set_markup(markup)
                except GLib.Error:
                    label.set_text(re.sub(r"<[^>]+>", "", markup))
                grid.attach(label, ci, 2 * r, 1, 1)
            if r < len(rows):
                grid.attach(Gtk.Separator(), 0, 2 * r + 1, ncol, 1)
        card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        card.add_css_class("card")
        card.append(grid)
        # Larghezza della pagina: un figlio del TextView prende la sua
        # larghezza naturale, quindi la si fissa qui (si ricalcola quando la
        # pagina cambia larghezza, vedi _center_page).
        card.set_size_request(max(200, self._preview_text_width() - 2), -1)
        return card

    def _pv_rerender(self):
        self._pv_rerender_id = 0
        self._refresh_preview()
        return False

    @staticmethod
    def _insert_markup(buf, markup):
        if not markup:
            return
        try:
            buf.insert_markup(buf.get_end_iter(), markup, -1)
        except Exception:
            try:
                _ok, _attrs, plain, _accel = Pango.parse_markup(markup, -1, "\0")
            except Exception:
                plain = re.sub(r"<[^>]+>", "", markup)
            buf.insert(buf.get_end_iter(), plain)

    # ------------------------------------------------------- immagini
    def _doc_dir(self):
        return os.path.dirname(os.path.abspath(self.current_path)) if self.current_path \
            else os.getcwd()

    def _resolve_image_path(self, src):
        """Percorso locale di un'immagine Markdown (relativo al documento)."""
        s = (src or "").strip()
        if not s or s.lower().startswith("data:"):
            return None
        if s.lower().startswith("file://"):
            s = urllib.parse.urlparse(s).path
        elif re.match(r"^[a-z][\w+.-]*://", s, re.I):
            return None                      # remota: mai scaricata
        s = os.path.expanduser(urllib.parse.unquote(s))
        if not os.path.isabs(s):
            s = os.path.join(self._doc_dir(), s)
        return s if os.path.isfile(s) else None

    def _preview_text_width(self):
        w = self.preview_sw.get_width() - self.preview_view.get_left_margin() \
            - self.preview_view.get_right_margin()
        return w if w > 0 else 640

    def _image_texture(self, src, alt="", maxw=None):
        """Texture ridotta alla larghezza della pagina (mai ingrandita).
        Le immagini remote non vengono caricate: nessun accesso alla rete.
        maxw: larghezza massima; predefinita quella dell'anteprima."""
        if re.match(r"^[a-z][\w+.-]*://", src or "", re.I) and not src.lower().startswith("file://"):
            return None, self.t("img_remote", alt=alt or src)
        path = self._resolve_image_path(src)
        if not path:
            return None, self.t("img_missing", src=src)
        maxw = int(maxw) if maxw else max(160, int(self._preview_text_width()))
        try:
            key = (path, os.path.getmtime(path), maxw)
        except OSError:
            return None, self.t("img_missing", src=src)
        tex = self._img_cache.get(key)
        if tex is not None:
            return tex, ""
        try:
            info = GdkPixbuf.Pixbuf.get_file_info(path)
            width = info[1] if info and info[0] is not None else 0
            if width and width > maxw:
                pix = GdkPixbuf.Pixbuf.new_from_file_at_scale(path, maxw, -1, True)
            else:
                pix = GdkPixbuf.Pixbuf.new_from_file(path)
            tex = Gdk.Texture.new_for_pixbuf(pix)
        except Exception:
            return None, self.t("img_missing", src=src)
        if len(self._img_cache) > 48:
            self._img_cache.clear()
        self._img_cache[key] = tex
        return tex, ""

    def _on_mark_set(self, buf, it, mark):
        if mark is buf.get_insert():
            self.cursor_label.set_label(
                self.t("st_cursor", ln=it.get_line() + 1, col=it.get_line_offset() + 1))
        self._schedule_live()

    def _update_title(self, *_):
        name = os.path.basename(self.current_path) if self.current_path \
            else self.t("title_untitled")
        star = "● " if self.buffer.get_modified() else ""
        self.set_title(f"{star}{name} — {APP_NAME}")

    # ------------------------------------------------------- resa live
    def _live_sync_language(self):
        if not HAS_GSV:
            return
        try:
            if self.cfg.get("live", True):
                self.buffer.set_language(None)
                self.buffer.set_highlight_syntax(False)
            else:
                lm = GtkSource.LanguageManager.get_default()
                self.buffer.set_language(lm.get_language("markdown"))
                self.buffer.set_highlight_syntax(True)
        except Exception:
            pass

    def _live_make_tags(self):
        buf = getattr(self, "buffer", None)
        if buf is None:
            return
        tt = buf.get_tag_table()
        for n in getattr(self, "_live_tag_names", None) or []:
            t = tt.lookup(n)
            if t is not None:
                b, e = buf.get_bounds()
                buf.remove_tag(t, b, e)
                tt.remove(t)
        c = self._palette()
        self.lv = {}

        def mk(name, **props):
            self.lv[name] = buf.create_tag("lv-" + name, **props)
        mk("h1", scale=1.80, weight=Pango.Weight.BOLD, foreground=c["heading"])
        mk("h2", scale=1.55, weight=Pango.Weight.BOLD, foreground=c["heading"])
        mk("h3", scale=1.32, weight=Pango.Weight.BOLD, foreground=c["heading"])
        mk("h4", scale=1.15, weight=Pango.Weight.BOLD, foreground=c["heading"])
        mk("h5", scale=1.05, weight=Pango.Weight.BOLD, foreground=c["heading"])
        mk("h6", scale=1.00, weight=Pango.Weight.BOLD, foreground=c["subtle"])
        mk("bold", weight=Pango.Weight.BOLD)
        mk("italic", style=Pango.Style.ITALIC)
        mk("strike", strikethrough=True, foreground=c["subtle"])
        mk("code", family="Monospace", background=c["code_bg"], foreground=c["code_fg"])
        mk("link", underline=Pango.Underline.SINGLE, foreground=c["link"])
        mk("img", foreground=c["accent"], weight=Pango.Weight.BOLD)
        mk("quote", style=Pango.Style.ITALIC, foreground=c["quote"])
        mk("bullet", foreground=c["accent2"], weight=Pango.Weight.BOLD)
        mk("hr", foreground=c["subtle"])
        mk("table", family="Monospace")
        mk("table_head", weight=Pango.Weight.BOLD, foreground=c["heading"])
        mk("table_sep", foreground=c["subtle"])
        mk("task", foreground=c["accent2"], weight=Pango.Weight.BOLD, family="Monospace")
        mk("task_done", strikethrough=True, foreground=c["subtle"])
        mk("fnref", foreground=c["accent"], rise=4 * Pango.SCALE, scale=0.8)
        mk("fndef", foreground=c["subtle"], scale=0.92)
        mk("mark", background=c["selection"], foreground=c["sel_fg"])
        mk("math", style=Pango.Style.ITALIC, foreground=c["accent2"])
        mk("math_block", justification=Gtk.Justification.CENTER)
        mk("sup", rise=5 * Pango.SCALE, scale=0.75)
        mk("sub", rise=-3 * Pango.SCALE, scale=0.75)
        # Linea orizzontale: riga bassissima colorata da un bordo all'altro;
        # il testo «---» prende lo stesso colore e sparisce. Senza gli spazi
        # dell'interlinea, che lo sfondo di paragrafo colorerebbe: 3 pixel con
        # qualunque interlinea, invece di una fascia di 13-21.
        mk("hr_bar", scale=0.12, foreground=c["border"], paragraph_background=c["border"],
           pixels_above_lines=0, pixels_below_lines=0)
        mk("setext", foreground=c["subtle"])
        mk("hide", invisible=True)
        # Blocchi di codice e tabelle: interlinea minima (righe compatte).
        mk("block", pixels_above_lines=1, pixels_below_lines=1, pixels_inside_wrap=1)
        self._live_tag_names = ["lv-" + n for n in self.lv]

    def _schedule_live(self, *_):
        if not self.cfg.get("live", True):
            return False
        if self._live_id:
            GLib.source_remove(self._live_id)
        self._live_id = GLib.timeout_add(90, self._do_live)
        return False

    def _do_live(self):
        self._live_id = 0
        self._live_restyle()
        return False

    def _live_restyle(self):
        if not getattr(self, "lv", None):
            return
        buf = self.buffer
        b, e = buf.get_bounds()
        for t in self.lv.values():
            buf.remove_tag(t, b, e)
        if not self.cfg.get("live", True):
            return
        text = self._get_text()
        if len(text) > self.LIVE_MAX_CHARS:
            return
        # L'analisi si rifà solo quando il testo cambia: spostando il cursore
        # cambiano soltanto i marcatori da mostrare.
        if getattr(self, "_live_cache", (None,))[0] != text:
            try:
                self._live_cache = (text, live_elements(text))
            except Exception as err:            # mai bloccare l'editor
                print(f"[ruscamark] resa live: {err}", file=sys.stderr)
                self._live_cache = (text, [])
        elements = self._live_cache[1]
        cur = buf.get_iter_at_mark(buf.get_insert()).get_offset()
        selb = buf.get_selection_bounds()
        sa, sb = (selb[0].get_offset(), selb[1].get_offset()) if selb else (None, None)

        def touched(a, z):
            if a <= cur <= z:
                return True
            return sa is not None and not (z < sa or a > sb)

        def apply(name, a, z):
            if z > a:
                buf.apply_tag(self.lv[name], buf.get_iter_at_offset(a), buf.get_iter_at_offset(z))
        for a, z, styles, hides in elements:
            for name, x, y in styles:
                apply(name, x, y)
            if hides and not touched(a, z):
                for h in hides:
                    apply(h[2] if len(h) > 2 else "hide", h[0], h[1])

    # ------------------------------------------------------- comandi di scrittura
    def _toggle_wrap(self, marker):
        """Grassetto/corsivo: avvolge o toglie il marcatore dalla selezione;
        senza selezione inserisce la coppia e mette il cursore in mezzo."""
        buf = self.buffer
        L = len(marker)
        sel = buf.get_selection_bounds()
        buf.begin_user_action()
        try:
            if not sel:
                off = buf.get_iter_at_mark(buf.get_insert()).get_offset()
                buf.insert_at_cursor(marker * 2)
                buf.place_cursor(buf.get_iter_at_offset(off + L))
                return
            so, eo = sel[0].get_offset(), sel[1].get_offset()
            txt = sel[0].get_text(sel[1])

            def wrapped(t):
                if not (len(t) >= 2 * L and t.startswith(marker) and t.endswith(marker)):
                    return False
                # "*" non deve scambiare il grassetto "**x**" per corsivo
                return not (marker == "*" and t.startswith("**") and not t.startswith("***"))
            before = buf.get_text(buf.get_iter_at_offset(max(0, so - L)),
                                  buf.get_iter_at_offset(so), True)
            after = buf.get_text(buf.get_iter_at_offset(eo),
                                 buf.get_iter_at_offset(eo + L), True)
            if wrapped(txt):
                new, a = txt[L:-L], so
                buf.delete(buf.get_iter_at_offset(so), buf.get_iter_at_offset(eo))
            elif before == marker and after == marker and so >= L:
                new, a = txt, so - L
                buf.delete(buf.get_iter_at_offset(so - L), buf.get_iter_at_offset(eo + L))
            else:
                new, a = marker + txt + marker, so
                buf.delete(buf.get_iter_at_offset(so), buf.get_iter_at_offset(eo))
            buf.insert(buf.get_iter_at_offset(a), new)
            buf.select_range(buf.get_iter_at_offset(a), buf.get_iter_at_offset(a + len(new)))
        finally:
            buf.end_user_action()
        self.view.grab_focus()

    def _insert_link(self):
        buf = self.buffer
        sel = buf.get_selection_bounds()
        txt = sel[0].get_text(sel[1]) if sel else ""
        buf.begin_user_action()
        try:
            if sel:
                so = sel[0].get_offset()
                buf.delete(sel[0], sel[1])
            else:
                so = buf.get_iter_at_mark(buf.get_insert()).get_offset()
            if re.match(r"^(https?://|www\.)\S+$", txt.strip()):
                new, a, z = f"[]({txt.strip()})", so + 1, so + 1
            else:
                label = txt or self.t("link_text")
                new = f"[{label}](https://)"
                if txt:
                    a = so + len(label) + 3
                    z = a + len("https://")
                else:
                    a, z = so + 1, so + 1 + len(label)
            buf.insert(buf.get_iter_at_offset(so), new)
            buf.select_range(buf.get_iter_at_offset(a), buf.get_iter_at_offset(z))
        finally:
            buf.end_user_action()
        self.view.grab_focus()

    def _set_heading(self, level):
        """Ctrl+1…6 imposta il livello di titolo della riga, Ctrl+0 lo toglie."""
        buf = self.buffer
        it = buf.get_iter_at_mark(buf.get_insert())
        ln = it.get_line()
        ok, start = buf.get_iter_at_line(ln)
        if not ok:
            return
        end = start.copy()
        if not end.ends_line():
            end.forward_to_line_end()
        line = start.get_text(end)
        body = re.sub(r"^ {0,3}#{1,6}[ \t]*", "", line)
        new = ("#" * level + " " + body) if level > 0 else body
        if new == line:
            return
        buf.begin_user_action()
        off = start.get_offset()
        buf.delete(start, end)
        buf.insert(buf.get_iter_at_offset(off), new)
        buf.place_cursor(buf.get_iter_at_offset(off + len(new)))
        buf.end_user_action()

    def _insert_block(self, block):
        """Inserisce un blocco su righe proprie, con una riga vuota prima."""
        buf = self.buffer
        it = buf.get_iter_at_mark(buf.get_insert())
        if not it.ends_line():
            it.forward_to_line_end()
        off = it.get_offset()
        before = buf.get_text(buf.get_start_iter(), it, True)
        pre = ""
        if before and not before.endswith("\n"):
            pre = "\n\n"
        elif before and not before.endswith("\n\n"):
            pre = "\n"
        buf.begin_user_action()
        buf.insert(buf.get_iter_at_offset(off), pre + block + "\n")
        buf.end_user_action()
        return off + len(pre)

    def _action_insert_image(self):
        f = Gtk.FileFilter()
        f.set_name(self.t("filter_images"))
        f.add_pixbuf_formats()
        for ext in _IMG_EXT:
            f.add_suffix(ext[1:])
        if HAS_FILEDIALOG:
            store = Gio.ListStore.new(Gtk.FileFilter)
            store.append(f)
            fd = Gtk.FileDialog()
            fd.set_title(self.t("mi_image"))
            fd.set_filters(store)
            if self.current_path:
                try:
                    fd.set_initial_folder(Gio.File.new_for_path(self._doc_dir()))
                except Exception:
                    pass

            def done(dlg, res, _u=None):
                try:
                    gf = dlg.open_finish(res)
                except Exception:
                    return
                if gf and gf.get_path():
                    self._insert_image_path(gf.get_path())
            fd.open(self, None, done, None)
        else:
            dlg = Gtk.FileChooserNative.new(self.t("mi_image"), self, Gtk.FileChooserAction.OPEN,
                                            self.t("btn_ok"), self.t("btn_cancel"))
            dlg.add_filter(f)

            def resp(d, r):
                if r == Gtk.ResponseType.ACCEPT and d.get_file():
                    self._insert_image_path(d.get_file().get_path())
                d.destroy()
            dlg.connect("response", resp)
            dlg.show()

    def _insert_image_path(self, path):
        """Percorso relativo al documento se è già salvato, altrimenti assoluto."""
        ref = path
        if self.current_path:
            try:
                ref = os.path.relpath(path, self._doc_dir())
            except ValueError:
                ref = path
        ref = urllib.parse.quote(ref.replace(os.sep, "/"), safe="/:._-~()")
        alt = os.path.splitext(os.path.basename(path))[0].replace("_", " ").replace("-", " ")
        self._insert_block(f"![{alt}]({ref})")
        self._schedule_refresh()
        self.view.grab_focus()

    def _table_action(self):
        """Ctrl+Maiusc+T: dentro una tabella la riallinea, fuori ne inserisce una."""
        buf = self.buffer
        lines = self._get_text().split("\n")
        ln = buf.get_iter_at_mark(buf.get_insert()).get_line()
        for a, b in find_table_blocks(lines):
            if a <= ln <= b:
                new = align_table_lines(lines[a:b + 1])
                ok, s_it = buf.get_iter_at_line(a)
                ok2, e_it = buf.get_iter_at_line(b)
                if not (ok and ok2):
                    return
                if not e_it.ends_line():
                    e_it.forward_to_line_end()
                buf.begin_user_action()
                off = s_it.get_offset()
                buf.delete(s_it, e_it)
                buf.insert(buf.get_iter_at_offset(off), "\n".join(new))
                ok, cur = buf.get_iter_at_line(ln)
                if ok:
                    cur.forward_chars(2)
                    buf.place_cursor(cur)
                buf.end_user_action()
                return
        head = "| " + " | ".join(self.t("tbl_col", n=n) for n in (1, 2, 3)) + " |"
        tmpl = align_table_lines([head, "|---|---|---|", "|  |  |  |", "|  |  |  |"])
        start = self._insert_block("\n".join(tmpl))
        cell = buf.get_iter_at_offset(start + len(tmpl[0]) + len(tmpl[1]) + 4)
        buf.place_cursor(cell)
        self.view.grab_focus()

    # ------------------------------------------------------- file I/O
    def _filters_store(self):
        f = Gtk.FileFilter()
        f.set_name(self.t("filter_markdown"))
        for p in ("*.md", "*.markdown", "*.mdown"):
            f.add_pattern(p)
        f.add_mime_type("text/markdown")
        f2 = Gtk.FileFilter()
        f2.set_name(self.t("filter_all"))
        f2.add_pattern("*")
        if HAS_FILEDIALOG:
            store = Gio.ListStore.new(Gtk.FileFilter)
            store.append(f); store.append(f2)
            return store
        return [f, f2]

    @staticmethod
    def _dismissed(e):
        try:
            return e.matches(Gtk.FileDialogError, Gtk.FileDialogError.DISMISSED)
        except Exception:
            msg = (getattr(e, "message", "") or "").lower()
            return "dismiss" in msg or "cancel" in msg

    def load_file(self, path):
        try:
            with open(path, "r", encoding="utf-8", errors="replace") as f:
                text = f.read()
        except Exception as e:
            self._message(self.t("err_open", e=e))
            return False
        self._set_buffer_text(text)
        self.current_path = path
        self.buffer.set_modified(False)
        self._update_title()
        self._schedule_refresh()
        return True

    def save_file(self, as_new=False):
        if self.current_path and not as_new:
            return self._write_file(self.current_path)
        base = os.path.basename(self.current_path) if self.current_path \
            else self.t("default_name") + ".md"
        if HAS_FILEDIALOG:
            fd = Gtk.FileDialog()
            fd.set_title(self.t("mi_save"))
            fd.set_filters(self._filters_store())
            fd.set_initial_name(base)
            fd.save(self, None, self._on_save_done, None)
        else:
            dlg = Gtk.FileChooserNative.new(
                self.t("mi_save"), self, Gtk.FileChooserAction.SAVE,
                self.t("btn_save"), self.t("btn_cancel"))
            dlg.set_current_name(base)
            dlg.set_modal(True)
            for fl in self._filters_store():
                dlg.add_filter(fl)
            dlg.connect("response", self._on_save_response_old)
            dlg.show()
        return True

    def _on_save_done(self, fd, result, user=None):
        try:
            gf = fd.save_finish(result)
        except GLib.Error as e:
            if not self._dismissed(e):
                self._message(self.t("err_save", e=e.message))
            return
        except Exception as e:
            self._message(self.t("err_save", e=e))
            return
        if gf:
            path = gf.get_path()
            if not re.search(r"\.(md|markdown|mdown|txt)$", path, re.I):
                path += ".md"
            self._write_file(path)

    def _on_save_response_old(self, dlg, response):
        if response == Gtk.ResponseType.ACCEPT:
            gf = dlg.get_file()
            if gf:
                path = gf.get_path()
                if not re.search(r"\.(md|markdown|mdown|txt)$", path, re.I):
                    path += ".md"
                self._write_file(path)
        dlg.destroy()

    def _write_file(self, path):
        try:
            with open(path, "w", encoding="utf-8") as f:
                f.write(self._get_text())
        except Exception as e:
            self._message(self.t("err_save", e=e))
            return False
        self.current_path = path
        self.buffer.set_modified(False)
        self._update_title()
        return True

    # ------------------------------------------------------- azioni varie
    def _action_new(self):
        self._confirm_discard(lambda ok: ok and self._reset_doc())

    def _reset_doc(self):
        self._set_buffer_text("")
        self.current_path = None
        self.buffer.set_modified(False)
        self._update_title(); self._schedule_refresh()

    def _action_open(self):
        def proceed(_ok):
            if HAS_FILEDIALOG:
                fd = Gtk.FileDialog()
                fd.set_title(self.t("mi_open"))
                fd.set_filters(self._filters_store())
                fd.open(self, None, self._on_open_done, None)
            else:
                dlg = Gtk.FileChooserNative.new(
                    self.t("mi_open"), self, Gtk.FileChooserAction.OPEN,
                    self.t("btn_ok"), self.t("btn_cancel"))
                dlg.set_modal(True)
                for fl in self._filters_store():
                    dlg.add_filter(fl)
                dlg.connect("response", self._on_open_response_old)
                dlg.show()
        self._confirm_discard(proceed)

    def _on_open_done(self, fd, result, user=None):
        try:
            gf = fd.open_finish(result)
        except GLib.Error as e:
            if not self._dismissed(e):
                self._message(self.t("err_open", e=e.message))
            return
        except Exception as e:
            self._message(self.t("err_open", e=e))
            return
        if gf:
            self.load_file(gf.get_path())

    def _on_open_response_old(self, dlg, response):
        if response == Gtk.ResponseType.ACCEPT:
            gf = dlg.get_file()
            if gf:
                self.load_file(gf.get_path())
        dlg.destroy()

    def _action_export_html(self):
        base = os.path.basename(self.current_path or self.t("default_name"))
        name = os.path.splitext(base)[0] + ".html"
        if HAS_FILEDIALOG:
            fd = Gtk.FileDialog()
            fd.set_title(self.t("mi_export_html"))
            fd.set_initial_name(name)
            fd.save(self, None, self._on_html_done, None)
        else:
            dlg = Gtk.FileChooserNative.new(
                self.t("mi_export_html"), self, Gtk.FileChooserAction.SAVE,
                self.t("btn_ok"), self.t("btn_cancel"))
            dlg.set_current_name(name)
            dlg.set_modal(True)
            dlg.connect("response", self._on_html_response_old)
            dlg.show()

    def _do_export_html(self, path):
        if not path.lower().endswith(".html"):
            path += ".html"
        text = self._get_text()
        m = re.search(r"^ {0,3}#[ \t]+(.+?)[ \t#]*$", text, re.M)
        title = MarkdownDoc("").plain(m.group(1)) if m else \
            os.path.basename(self.current_path or self.t("html_default_title"))
        out_dir = os.path.dirname(os.path.abspath(path))
        embed = bool(self.cfg.get("html_embed_images", False))
        lang = self._current_lang().split("_")[0] or "en"
        out = markdown_to_html(
            text, title, lang=lang,
            img_src=lambda src: self._html_img_src(src, out_dir, embed), t=self.t)
        try:
            with open(path, "w", encoding="utf-8") as f:
                f.write(out)
            self._toast_file("toast_html_done", path)
        except Exception as e:
            self._message(self.t("err_export", e=e))

    def _action_export_pdf(self):
        base = os.path.basename(self.current_path or self.t("default_name"))
        name = os.path.splitext(base)[0] + ".pdf"
        f = Gtk.FileFilter()
        f.set_name("PDF")
        f.add_suffix("pdf")
        f.add_mime_type("application/pdf")
        if HAS_FILEDIALOG:
            store = Gio.ListStore.new(Gtk.FileFilter)
            store.append(f)
            fd = Gtk.FileDialog()
            fd.set_title(self.t("mi_export_pdf"))
            fd.set_initial_name(name)
            fd.set_filters(store)

            def done(dlg, res, _u=None):
                try:
                    gf = dlg.save_finish(res)
                except GLib.Error as e:
                    if not self._dismissed(e):
                        self._message(self.t("err_export", e=e.message))
                    return
                except Exception as e:
                    self._message(self.t("err_export", e=e))
                    return
                if gf and gf.get_path():
                    self._do_export_pdf(gf.get_path())
            fd.save(self, None, done, None)
        else:
            dlg = Gtk.FileChooserNative.new(self.t("mi_export_pdf"), self, Gtk.FileChooserAction.SAVE,
                                            self.t("btn_ok"), self.t("btn_cancel"))
            dlg.set_current_name(name)
            dlg.set_modal(True)
            dlg.add_filter(f)

            def resp(d, r):
                if r == Gtk.ResponseType.ACCEPT and d.get_file():
                    self._do_export_pdf(d.get_file().get_path())
                d.destroy()
            dlg.connect("response", resp)
            dlg.show()

    def _pdf_image(self, src):
        """Pixbuf per il PDF (max 2400 px di lato); le immagini remote non
        vengono scaricate: al loro posto resta il testo alternativo."""
        path = self._resolve_image_path(src)
        if not path:
            return None
        try:
            info = GdkPixbuf.Pixbuf.get_file_info(path)
            w = info[1] if info and info[0] is not None else 0
            if w > 2400:
                return GdkPixbuf.Pixbuf.new_from_file_at_scale(path, 2400, -1, True)
            return GdkPixbuf.Pixbuf.new_from_file(path)
        except Exception:
            return None

    def _do_export_pdf(self, path):
        if not path.lower().endswith(".pdf"):
            path += ".pdf"
        if not HAVE_PDF:
            self._message(self.t("err_export", e="python3-gi-cairo"))
            return
        text = self._get_text()
        m = re.search(r"^ {0,3}#[ \t]+(.+?)[ \t#]*$", text, re.M)
        title = MarkdownDoc("").plain(m.group(1)) if m else \
            os.path.splitext(os.path.basename(path))[0]
        try:
            items = MarkdownDoc(text).to_print(PRINT_COLORS, t=self.t)
            PdfExporter(items, self._pdf_image, title=title, t=self.t).export(path)
            self._toast_file("toast_pdf_done", path)
        except Exception as e:
            self._message(self.t("err_export", e=getattr(e, "message", None) or e))

    def _html_img_src(self, src, out_dir, embed):
        """Riferimento immagine valido anche se l'HTML è salvato altrove:
        percorso relativo alla cartella dell'HTML oppure, con l'opzione
        «Incorpora le immagini», data URI base64 (file unico e portabile).
        Gli URL remoti restano invariati e non vengono mai scaricati."""
        path = self._resolve_image_path(src)
        if path is None:
            return src
        if embed:
            try:
                if os.path.getsize(path) <= 25 * 1024 * 1024:
                    mime = mimetypes.guess_type(path)[0] or "application/octet-stream"
                    with open(path, "rb") as f:
                        return f"data:{mime};base64," + base64.b64encode(f.read()).decode("ascii")
            except Exception:
                pass
        try:
            rel = os.path.relpath(path, out_dir)
        except ValueError:
            rel = path
        return urllib.parse.quote(rel.replace(os.sep, "/"), safe="/:._-~()")

    def _on_html_done(self, fd, result, user=None):
        try:
            gf = fd.save_finish(result)
        except GLib.Error as e:
            if not self._dismissed(e):
                self._message(self.t("err_export", e=e.message))
            return
        except Exception as e:
            self._message(self.t("err_export", e=e))
            return
        if gf:
            self._do_export_html(gf.get_path())

    def _on_html_response_old(self, dlg, response):
        if response == Gtk.ResponseType.ACCEPT:
            gf = dlg.get_file()
            if gf:
                self._do_export_html(gf.get_path())
        dlg.destroy()

    def _action_undo(self):
        if HAS_GSV and self.buffer.can_undo():
            self.buffer.undo()

    def _action_redo(self):
        if HAS_GSV and self.buffer.can_redo():
            self.buffer.redo()

    # ------------------------------------------------------- Informazioni e scorciatoie
    def _action_about(self):
        show_about_dialog(self, self.t, APP_ID, APP_NAME, APP_VERSION,
                          self.t("about_desc"), theme_has_icon(), COMPONENTS)

    def _action_shortcuts(self):
        """Adw.ShortcutsDialog arriva con libadwaita 1.8: su trixie si usa un
        Adw.Dialog con righe normali."""
        t = self.t
        groups = (
            (t("sc_group_file"), ((t("mi_new"), "<Primary>n"), (t("mi_open"), "<Primary>o"),
                                  (t("mi_save"), "<Primary>s"), (t("mi_save_as"), "<Primary><Shift>s"),
                                  (t("mi_export_html"), "<Primary><Shift>e"),
                                  (t("mi_export_pdf"), "<Primary><Shift>p"))),
            (t("sc_group_edit"), ((t("mi_bold"), "<Primary>b"), (t("mi_italic"), "<Primary>i"),
                                  (t("mi_link"), "<Primary>k"), (t("mi_image"), "<Primary><Shift>i"),
                                  (t("mi_table"), "<Primary><Shift>t"),
                                  (t("mi_heading_n", n="1–6"), "<Primary>1"),
                                  (t("mi_paragraph"), "<Primary>0"),
                                  (t("mi_find"), "<Primary>f"), (t("mi_replace"), "<Primary>h"))),
            (t("sc_group_view"), ((t("mi_preview"), "<Primary>p"), (t("mi_live"), "<Primary>l"),
                                  (t("mi_spell"), "F7"), (t("mi_fullscreen"), "F11"),
                                  (t("mi_preferences"), "<Primary>comma"),
                                  (t("shortcuts"), "<Primary>question"), (t("main_menu"), "F10"),
                                  (t("sc_close"), "<Primary>w"), (t("mi_quit"), "<Primary>q"))),
        )
        page = Adw.PreferencesPage()
        for title, rows in groups:
            group = Adw.PreferencesGroup(title=title)
            for label, accel in rows:
                row = Adw.ActionRow(title=label.rstrip("…"), use_markup=False)
                ok, key, mods = Gtk.accelerator_parse(accel)
                keys = Gtk.Label(label=Gtk.accelerator_get_label(key, mods) if ok else accel)
                keys.add_css_class("dim-label")
                row.add_suffix(keys)
                group.add(row)
            page.add(group)
        view = Adw.ToolbarView(content=page)
        view.add_top_bar(Adw.HeaderBar())
        Adw.Dialog(title=t("shortcuts"), content_width=460, content_height=560,
                   child=view).present(self)

    def _on_drop(self, target, value, x, y):
        try:
            path = value.get_path()
            if path:
                self.load_file(path)
                return True
        except Exception:
            pass
        return False

    # ------------------------------------------------------- preferenze
    def _action_preferences(self):
        """Preferenze nello stile GNOME: ogni modifica vale subito."""
        t = self.t
        page = Adw.PreferencesPage()

        def changed():
            self._apply_theme()
            self._center_page()
            GLib.timeout_add(80, self._center_page)
            save_config(self.cfg)

        look = Adw.PreferencesGroup(title=t("pref_group_look"))
        styles = ["system", "light", "dark"]
        style_row = Adw.ComboRow(title=t("pref_style"),
                                 model=Gtk.StringList.new([t("style_system"), t("style_light"),
                                                           t("style_dark")]))
        style_row.set_selected(styles.index(self.cfg.get("style", "system")))
        style_row.connect("notify::selected",
                          lambda r, _p: self._set_style(styles[r.get_selected()]))
        look.add(style_row)

        names = system_font_families()
        font_row = Adw.ComboRow(title=t("pref_font"), model=Gtk.StringList.new(names),
                                enable_search=True)
        try:
            font_row.set_selected(names.index(self.cfg.get("font", "Sans")))
        except ValueError:
            font_row.set_selected(0)

        def on_font(r, _p):
            i = r.get_selected()
            if 0 <= i < len(names):
                self.cfg["font"] = names[i]
                changed()
        font_row.connect("notify::selected", on_font)
        look.add(font_row)

        size_row = Adw.SpinRow.new_with_range(8, 72, 1)
        size_row.set_title(t("pref_size"))
        size_row.set_value(self.cfg.get("font_size", 13))

        def on_size(r, _p):
            self.cfg["font_size"] = int(r.get_value())
            changed()
        size_row.connect("notify::value", on_size)
        look.add(size_row)

        spacing_keys = ["compact", "normal", "airy"]
        spacing_row = Adw.ComboRow(title=t("pref_spacing"), model=Gtk.StringList.new(
            [t(f"spacing_{k}") for k in spacing_keys]))
        try:
            spacing_row.set_selected(spacing_keys.index(self.cfg.get("line_spacing", "normal")))
        except ValueError:
            spacing_row.set_selected(1)

        def on_spacing(r, _p):
            self.cfg["line_spacing"] = spacing_keys[r.get_selected()]
            changed()
        spacing_row.connect("notify::selected", on_spacing)
        look.add(spacing_row)
        page.add(look)

        writing = Adw.PreferencesGroup(title=t("pref_group_writing"))
        live_row = Adw.SwitchRow(title=t("pref_live"),
                                 active=self.live_action.get_state().get_boolean())
        live_row.connect("notify::active", lambda r, _p: self.live_action.change_state(
            GLib.Variant.new_boolean(r.get_active())))
        writing.add(live_row)
        center_row = Adw.SwitchRow(title=t("pref_center"),
                                   active=bool(self.cfg.get("center_page", True)))
        width_row = Adw.SpinRow.new_with_range(40, 140, 2)
        width_row.set_title(t("pref_width"))
        width_row.set_value(int(self.cfg.get("page_chars", 80)))

        def on_center(r, _p):
            self.cfg["center_page"] = r.get_active()
            changed()
        center_row.connect("notify::active", on_center)

        def on_width(r, _p):
            self.cfg["page_chars"] = int(r.get_value())
            changed()
        width_row.connect("notify::value", on_width)
        writing.add(center_row)
        writing.add(width_row)
        page.add(writing)

        export = Adw.PreferencesGroup(title=t("pref_group_export"))
        embed_row = Adw.SwitchRow(title=t("pref_embed"),
                                  active=bool(self.cfg.get("html_embed_images", False)))

        def on_embed(r, _p):
            self.cfg["html_embed_images"] = r.get_active()
            save_config(self.cfg)
        embed_row.connect("notify::active", on_embed)
        export.add(embed_row)
        page.add(export)

        dialog = Adw.PreferencesDialog(title=t("mi_preferences").rstrip("…"))
        dialog.add(page)
        dialog.present(self)

    def _apply_default_direction(self):
        """Arabo: tutta l'interfaccia da destra a sinistra (non solo il testo)."""
        try:
            Gtk.Widget.set_default_direction(
                Gtk.TextDirection.RTL if self.lang in RTL_LANGUAGES else Gtk.TextDirection.LTR)
        except Exception:
            pass

    def _apply_text_direction(self):
        verso = (Gtk.TextDirection.RTL if self.lang in RTL_LANGUAGES
                 else Gtk.TextDirection.LTR)
        for w in (getattr(self, "view", None), getattr(self, "preview_view", None)):
            if w is not None:
                try:
                    w.set_direction(verso)
                except Exception:
                    pass

    def _retranslate(self):
        """Riallinea tutti i testi già costruiti alla nuova lingua."""
        self._apply_default_direction()
        self._apply_text_direction()
        self.mb.set_menu_model(self._build_menu())
        self._retranslate_header()
        self._retranslate_search()
        self.goal_button.set_tooltip_text(self.t("goal_tip"))
        self.goal_pop_label.set_text(self.t("goal_pop_title"))
        self.goal_apply_btn.set_label(self.t("btn_apply"))
        self.spell_title_label.set_label(self.t('spell_title'))
        self.spell_toggle_btn.set_tooltip_text(self.t("spell_toggle_tip"))
        self._spell_hide_btn.set_tooltip_text(self.t("spell_hide_tip"))
        self._update_counts()
        self._update_title()
        self._sync_spell_ui()
        self._schedule_refresh()

    # ------------------------------------------------------- ortografia live
    def _build_spell_panel(self):
        self.spell_revealer = Gtk.Revealer()
        self.spell_revealer.set_transition_type(Gtk.RevealerTransitionType.SLIDE_UP)
        panel = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        panel.set_margin_start(12); panel.set_margin_end(6)
        panel.set_margin_top(6); panel.set_margin_bottom(6)
        head = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        self.spell_title_label = Gtk.Label()
        self.spell_title_label.set_xalign(0)
        self.spell_title_label.add_css_class("heading")
        head.append(self.spell_title_label)
        self.lang_combo = Gtk.DropDown.new_from_strings(["…"])
        head.append(self.lang_combo)
        self._refresh_spell_langs()
        self.lang_combo.connect("notify::selected", self._on_lang_combo)
        self.spell_status = Gtk.Label(label="")
        self.spell_status.set_hexpand(True)
        self.spell_status.set_xalign(0)
        self.spell_status.set_ellipsize(Pango.EllipsizeMode.END)
        self.spell_status.add_css_class("dim-label")
        head.append(self.spell_status)
        self.spell_toggle_btn = Gtk.ToggleButton(label="")
        self.spell_toggle_btn.set_action_name("win.spell-toggle")
        head.append(self.spell_toggle_btn)
        self._spell_hide_btn = Gtk.Button.new_from_icon_name("window-close-symbolic")
        self._spell_hide_btn.add_css_class("flat")
        self._spell_hide_btn.connect("clicked", self._hide_spell_panel)
        head.append(self._spell_hide_btn)
        panel.append(head)
        self.spell_revealer.set_child(panel)
        self.toolbar.add_bottom_bar(self.spell_revealer)
        self.spell_title_label.set_label(self.t('spell_title'))
        self.spell_toggle_btn.set_tooltip_text(self.t("spell_toggle_tip"))
        self._spell_hide_btn.set_tooltip_text(self.t("spell_hide_tip"))

    def _lang_label(self, code):
        base = code.split("_")[0].lower()
        if base in self.NATIVE_NAMES:
            return f"{self.NATIVE_NAMES[base]} ({code})"
        return code

    def _installed_spell_langs(self):
        found = {}
        if SPELL_BACKEND == "gspell2" and Gspell is not None:
            try:
                installed = {l.get_code() for l in Gspell.Language.get_available()}
                for code in self.NATIVE_NAMES:
                    loc = f"{code}_{code.upper()}" if code not in ("ar", "zh", "ja", "ko",
                                                                   "th", "he", "fa", "ur", "hi", "bn", "mr", "pa", "gu", "ta",
                                                                   "te", "kn", "ml", "id", "ms", "vi", "sw", "el", "uk", "be",
                                                                   "kk", "mn", "hy", "ka", "sq", "is", "cy", "ga") else None
                    loc = loc or {
                        "en": "en_US", "it": "it_IT", "es": "es_ES", "fr": "fr_FR",
                        "de": "de_DE", "pt": "pt_PT", "ru": "ru_RU", "pl": "pl_PL",
                        "nl": "nl_NL", "sv": "sv_SE", "da": "da_DK", "nb": "nb_NO",
                        "fi": "fi_FI", "cs": "cs_CZ", "hu": "hu_HU", "ro": "ro_RO",
                        "el": "el_GR", "uk": "uk_UA", "tr": "tr_TR", "id": "id_ID",
                        "ms": "ms_MY", "vi": "vi_VN", "he": "he_IL", "ar": "ar",
                        "fa": "fa_IR", "ur": "ur_PK", "hi": "hi_IN", "bn": "bn_BD",
                        "mr": "mr_IN", "pa": "pa_IN", "gu": "gu_IN", "ta": "ta_IN",
                        "te": "te_IN", "kn": "kn_IN", "ml": "ml_IN", "th": "th_TH",
                        "zh": "zh_CN", "ja": "ja_JP", "ko": "ko_KR", "sw": "sw_TZ",
                    }.get(code, code)
                    if loc in installed or loc.split("_")[0] in installed or any(
                            ic.split("_")[0] == loc.split("_")[0] for ic in installed):
                        found[code] = None
            except Exception:
                found = {}
        elif SPELL_BACKEND == "spelling" and Spelling is not None:
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
                    base_codes = {c.split("_")[0] for c in codes}
                    for code in self.NATIVE_NAMES:
                        if code in codes or code in base_codes:
                            found[code] = None
            except Exception:
                found = {}
        return found

    def _available_spell_langs(self):
        found = self._installed_spell_langs()
        codes = set(found)
        if not codes:
            codes = {"it_IT", "en_US", "es_ES", "fr_FR", "de_DE", "pt_PT", "ru_RU"}
        prefer = self.cfg.get("lang", "it_IT")
        return sorted(codes, key=lambda c: (c != prefer, self._lang_label(c).lower()))

    def _refresh_spell_langs(self):
        current = self.cfg.get("lang", "it_IT")
        self._spell_langs = self._available_spell_langs()
        labels = [self._lang_label(c) for c in self._spell_langs]
        self._spell_combo_loading = True
        self.lang_combo.set_model(Gtk.StringList.new(labels))
        try:
            sel = self._spell_langs.index(current)
        except ValueError:
            sel = 0
        self.lang_combo.set_selected(sel)
        self._spell_combo_loading = False

    def _on_lang_combo(self, combo, _pspec=None):
        if getattr(self, "_spell_combo_loading", False):
            return
        langs = getattr(self, "_spell_langs", [])
        idx = combo.get_selected()
        if 0 <= idx < len(langs) and langs[idx] != self.cfg.get("lang"):
            self._set_spell_lang(langs[idx])

    def _current_lang(self):
        return self.cfg.get("lang", "it_IT")

    def _spell_locale(self):
        return self._current_lang()

    def _ensure_elision_for_spell(self):
        try:
            locales = {self._spell_locale()} | set(_ELISION_LOCALES.values())
            ensure_elision_dictionaries(locales)
        except Exception:
            pass

    def _make_spelling_checker(self, loc):
        provider = None
        try:
            provider = Spelling.Provider.get_default()
        except Exception:
            provider = None
        if provider is not None:
            try:
                ck = Spelling.Checker.new(provider, loc)
                if ck is not None:
                    return ck
            except Exception:
                pass
            try:
                ck = Spelling.Checker.new(provider, loc.split("_")[0])
                if ck is not None:
                    return ck
            except Exception:
                pass
        return Spelling.Checker.get_default()

    def _setup_spell_libspelling(self, loc):
        checker = self._make_spelling_checker(loc)
        if checker is None:
            raise RuntimeError(self.t("spell_err_checker"))
        adapter = Spelling.TextBufferAdapter.new(self.buffer, checker)
        try:
            self.view.set_extra_menu(adapter.get_menu_model())
        except Exception:
            pass
        try:
            self.view.insert_action_group("spelling", adapter)
        except Exception:
            pass
        adapter.set_enabled(True)
        self.spell_checker = checker
        self._spell_adapter = adapter

    def _setup_spell_gspell2(self, loc):
        lang = Gspell.Language.lookup(loc)
        if lang is None:
            raise RuntimeError(self.t("spell_err_dict", loc=loc))
        checker = Gspell.Checker.new(lang)
        gbuf = Gspell.TextBuffer.get_from_gtk_text_buffer(self.buffer)
        gbuf.set_spell_checker(checker)
        gview = Gspell.TextView.get_from_gtk_text_view(self.view)
        gview.set_inline_spell_checking(True)
        gview.set_enable_language_menu(True)
        self.spell_checker = checker
        self._gspell_view = gview

    def _setup_spell(self):
        if getattr(self, "_spell_adapter", None) is not None:
            try:
                self._spell_adapter.set_enabled(False)
            except Exception:
                pass
        self._spell_adapter = None
        self.spell_error = None
        self.spell_checker = None
        self._spell_on = False
        if SPELL_BACKEND is None:
            self.spell_error = self.t("spell_err_nobackend")
            return
        loc = self._spell_locale()
        try:
            if SPELL_BACKEND == "spelling":
                if not HAS_GSV or not isinstance(self.buffer, GtkSource.Buffer):
                    raise RuntimeError(self.t("spell_err_needs_gsv"))
                self._setup_spell_libspelling(loc)
            else:
                self._setup_spell_gspell2(loc)
        except Exception as exc:
            self.spell_checker = None
            self._spell_adapter = None
            self.spell_error = str(exc) or repr(exc)
        self._spell_on = self.spell_checker is not None

    def _spell_disable(self):
        if SPELL_BACKEND == "spelling" and getattr(self, "_spell_adapter", None) is not None:
            try:
                self._spell_adapter.set_enabled(False)
            except Exception:
                pass
        if SPELL_BACKEND == "gspell2" and getattr(self, "_gspell_view", None) is not None:
            try:
                self._gspell_view.set_inline_spell_checking(False)
            except Exception:
                pass
        self._spell_on = False

    def _hide_spell_panel(self, *_):
        self.cfg["spell_panel_hidden"] = True
        save_config(self.cfg)
        self.spell_revealer.set_reveal_child(False)

    def _set_spell_on(self, on):
        """Unico interruttore dell'ortografia live (header, barra, F7, menu).
        Accendere mostra il pannello e azzera il nascondimento manuale;
        spegnere nasconde il pannello. Lo stato viene salvato in config.json."""
        on = bool(on)
        self.cfg["spell_on"] = on
        if on:
            self.cfg["spell_panel_hidden"] = False
            save_config(self.cfg)
            self._refresh_spell_langs()
            self._ensure_elision_for_spell()
            self._setup_spell()
            self.spell_revealer.set_reveal_child(True)
        else:
            self._spell_disable()
            self.spell_revealer.set_reveal_child(False)
            save_config(self.cfg)
        self._sync_spell_ui()

    def _set_spell_lang(self, lang):
        was_on = getattr(self, "_spell_on", False)
        self.cfg["lang"] = lang
        save_config(self.cfg)
        self._ensure_elision_for_spell()
        if self.spell_checker is not None or was_on or HAVE_SPELL:
            try:
                loc = self._spell_locale()
                if SPELL_BACKEND == "spelling":
                    new_checker = self._make_spelling_checker(loc)
                    applied = False
                    if self._spell_adapter is not None and new_checker is not None:
                        for meth in ("set_checker", "set_spell_checker"):
                            fn = getattr(self._spell_adapter, meth, None)
                            if fn is not None:
                                try:
                                    fn(new_checker)
                                    applied = True
                                    break
                                except Exception:
                                    applied = False
                    if applied:
                        self.spell_checker = new_checker
                    else:
                        self._setup_spell()
                elif SPELL_BACKEND == "gspell2":
                    glang = Gspell.Language.lookup(loc)
                    if glang is None:
                        raise RuntimeError(self.t("spell_err_dict", loc=loc))
                    self.spell_checker.set_language(glang)
            except Exception as exc:
                self.spell_error = str(exc)
                self._setup_spell()
        if not was_on:
            self._spell_disable()
        self._sync_spell_ui()

    def _sync_spell_ui(self):
        on = bool(getattr(self, "_spell_on", False)) and \
            getattr(self, "spell_checker", None) is not None
        try:
            self.spell_action.set_state(GLib.Variant.new_boolean(on))
        except Exception:
            pass
        btn = getattr(self, "spell_toggle_btn", None)
        if btn is not None:
            btn.set_label(self.t("spell_on") if on else self.t("spell_off"))
        hb = getattr(self, "spell_btn", None)
        if hb is not None:
            hb.set_tooltip_text(self.t("tip_spell_on") if on
                                else self.t("tip_spell_off"))
        self._update_spell_status()

    def _update_spell_status(self):
        """Messaggio di stato della barra ortografia: corretto anche quando
        il checker non è stato creato perché l'utente l'ha spento in config."""
        if SPELL_BACKEND is None:
            self.spell_status.set_label(self.t("spell_no_backend",
                                               e=getattr(self, "spell_error", "") or ""))
        elif getattr(self, "_spell_on", False) and \
                getattr(self, "spell_checker", None) is not None:
            nome = "libspelling" if SPELL_BACKEND == "spelling" else "GSpell 2"
            self.spell_status.set_label(self.t("spell_live", backend=nome,
                                               loc=self._spell_locale()))
        elif getattr(self, "spell_error", ""):
            self.spell_status.set_label(self.t("spell_inactive", e=self.spell_error))
        else:
            self.spell_status.set_label(self.t("spell_disabled"))

    # ------------------------------------------------------- dialoghi
    def _message(self, text, secondary=None):
        """Errore o avviso che richiede attenzione."""
        dlg = Adw.AlertDialog(heading=APP_NAME, body=text if not secondary
                              else f"{text}\n\n{secondary}")
        dlg.add_response("ok", self.t("btn_close"))
        dlg.present(self)

    def _toast_file(self, key, path):
        """Esito positivo di un export: notifica con «Apri» invece di un
        dialogo da chiudere."""
        toast = Adw.Toast(title=GLib.markup_escape_text(self.t(key)),
                          button_label=self.t("btn_open_file"), timeout=6)

        def open_file(*_a):
            Gtk.FileLauncher.new(Gio.File.new_for_path(path)).launch(self, None, None)
        toast.connect("button-clicked", open_file)
        self.toasts.add_toast(toast)

    def _ask_unsaved(self, body, save_label, on_save, on_discard):
        dlg = Adw.AlertDialog(heading=self.t("unsaved_title"), body=body)
        dlg.add_response("cancel", self.t("btn_cancel"))
        dlg.add_response("discard", self.t("btn_nosave"))
        dlg.add_response("save", save_label)
        dlg.set_response_appearance("discard", Adw.ResponseAppearance.DESTRUCTIVE)
        dlg.set_response_appearance("save", Adw.ResponseAppearance.SUGGESTED)
        dlg.set_default_response("save")
        dlg.set_close_response("cancel")

        def on_response(_d, rid):
            if rid == "save":
                on_save()
            elif rid == "discard":
                on_discard()
        dlg.connect("response", on_response)
        dlg.present(self)

    def _confirm_discard(self, callback):
        if not self.buffer.get_modified():
            callback(True)
            return
        name = os.path.basename(self.current_path) if self.current_path \
            else self.t("title_untitled")

        def save():
            if self.save_file():
                callback(True)
        self._ask_unsaved(self.t("unsaved_open", name=name), self.t("btn_save"),
                          save, lambda: callback(True))

    def _on_close_request(self, *_):
        if self._closing:
            return False
        if self.buffer.get_modified():
            self._confirm_discard_close()
            return True
        self._finalize()
        return False

    def _confirm_discard_close(self):
        def close():
            self._closing = True
            self.close()

        def save():
            if self.save_file():
                close()
        self._ask_unsaved(self.t("unsaved_close"), self.t("btn_save_exit"), save, close)

    def _finalize(self):
        try:
            self.cfg["win_w"], self.cfg["win_h"] = self.get_width(), self.get_height()
            self.cfg["paned"] = self.paned.get_position()
        except Exception:
            pass
        save_config(self.cfg)

    # ------------------------------------------------------- documento demo
    def _load_sample(self):
        """Documento dimostrativo nella lingua dell'interfaccia."""
        t = self.t
        F = "```"
        table = align_table_lines([
            f"| {t('sample_tc1')} | {t('sample_tc2')} |", "|:---|:---|",
            f"| Ctrl+B | {t('mi_bold')} |",
            f"| Ctrl+K | {t('mi_link').rstrip('…')} |",
            f"| Ctrl+Shift+T | {t('sample_t_table')} |",
        ])
        sample = "\n".join([
            f"# {t('sample_title')}",
            f"**{APP_NAME} {APP_VERSION}** — {t('sample_tagline')}",
            "",
            f"## {t('sample_h_live')}",
            f"- {t('sample_l1')}", f"- {t('sample_l2')}", f"- {t('sample_l3')}",
            f"- {t('sample_l4')}", f"- {t('sample_l5')}",
            "",
            f"> {t('sample_quote')}",
            "",
            f"## {t('sample_h_table')}",
            *table,
            "",
            f"- [x] {t('sample_task1')}",
            f"- [ ] {t('sample_task2')}[^1]",
            "",
            f"[^1]: {t('sample_fn')}",
            "",
            f"### {t('sample_h_code')}",
            f"{F}python", f'print("{t("sample_code")}")', F,
            "",
            "---",
            f"1. {t('sample_s1')}", f"2. {t('sample_s2')}", f"3. {t('sample_s3')}",
            "",
        ])
        self._set_buffer_text(sample)
        self.buffer.set_modified(False)
        self._update_title()
# ----------------------------------------------------------------------------
class RuscaApplication(Adw.Application):
    def __init__(self):
        super().__init__(application_id=APP_ID,
                         flags=Gio.ApplicationFlags.HANDLES_OPEN)
        self.win = None

    def do_startup(self):
        Adw.Application.do_startup(self)
        if not theme_has_icon():
            ensure_icon()
        # Stile chiaro/scuro scelto nelle preferenze (predefinito: sistema).
        style = load_config().get("style", "system")
        manager = Adw.StyleManager.get_default()
        manager.set_color_scheme({"light": Adw.ColorScheme.FORCE_LIGHT,
                                  "dark": Adw.ColorScheme.FORCE_DARK}
                                 .get(style, Adw.ColorScheme.DEFAULT))
        # Tema comune RuscaLinux; se manca restano i colori di GNOME.
        if STYLE_SRC:
            provider = Gtk.CssProvider()
            provider.load_from_path(STYLE_SRC)
            Gtk.StyleContext.add_provider_for_display(
                Gdk.Display.get_default(), provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)
        manager.connect("notify::dark", lambda *_a: self.update_theme())
        self.connect("window-added", lambda *_a: self.update_theme())
        quit_action = Gio.SimpleAction.new("quit", None)
        # Passa da close-request: le modifiche non salvate vengono chieste.
        quit_action.connect("activate", lambda *_a: [w.close() for w in self.get_windows()])
        self.add_action(quit_action)

    def update_theme(self):
        dark = Adw.StyleManager.get_default().get_dark()
        for window in self.get_windows():
            window.remove_css_class("rusca-light" if dark else "rusca-dark")
            window.add_css_class("rusca-dark" if dark else "rusca-light")
            # Una finestra appena creata (window-added arriva durante
            # __init__) applica il tema da sé quando è completa.
            if isinstance(window, RuscaWindow) and hasattr(window, "statusbar"):
                window._apply_theme()

    def do_activate(self):
        self._open_window(None)

    def do_open(self, files, n_files, hint):
        path = files[0].get_path() if files else None
        self._open_window(path)

    def _open_window(self, path):
        if self.win is None:
            self.win = RuscaWindow(self, path)
        elif path:
            self.win.load_file(path)
        self.win.present()

_GIZMO_WARNING = "Trying to snapshot GtkGizmo"

def _install_gtk_warning_filter():
    """Nasconde SOLO il warning cosmetico upstream di GTK4 sul primo
    frame della TextView ('Trying to snapshot GtkGizmo ... without a
    current allocation'); tutti gli altri messaggi restano visibili.
    Nota: log_set_handler(None, ...) intercetterebbe solo i messaggi
    SENZA dominio, quindi registriamo i domini espliciti Gtk/Gdk/GtkSource."""
    def _handler(domain, level, message, *args):
        if message and _GIZMO_WARNING in message:
            return
        print(f"({domain}): {message}", file=sys.stderr)
    for dom in ("Gtk", "Gdk", "GtkSource"):
        try:
            GLib.log_set_handler(dom, GLib.LogLevelFlags.LEVEL_WARNING, _handler)
        except Exception:
            pass


def main():
    GLib.set_application_name(APP_NAME)
    # Identificativo identico al nome del file .desktop
    # (org.ruscalinux.RuscaMark.desktop): GNOME associa così la finestra al
    # suo lanciatore e mostra l'icona di RuscaMark invece di quella generica.
    GLib.set_prgname(APP_ID)
    _install_gtk_warning_filter()
    signal.signal(signal.SIGINT, signal.SIG_DFL)
    os.makedirs(CONFIG_DIR, exist_ok=True)
    ensure_style_schemes()
    app = RuscaApplication()
    return app.run(sys.argv)

if __name__ == "__main__":
    sys.exit(main())
