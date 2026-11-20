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
EN — RuscaWriter internationalization (i18n).
Translations are NOT written in the code: they live in JSON files inside
the 'lang/' folder (one per language, e.g. it.json, en.json, ...). This
keeps the program modular and translatable without touching the Python
sources: to add or complete a language, just edit its JSON file.
- LANGUAGES lists the languages of the RuscaLinux OS Apps (code and native
  name), as defined in the specs, section 9.
- load_language(code) loads a language dictionary, automatically falling
  back to English (and then to the key itself) for any missing entry.
- A language without its file shows the English interface: no placeholder
  files are written (they ended up in the packages as copies of English).
- COMPLETE_LANGUAGES is COMPUTED from the JSON files, not written by hand:
  a language is "complete" when its file is a real translation, while the
  skeletons (copies of English) score zero. The menu therefore follows the
  files, and no second list has to be kept in sync.

IT — Internazionalizzazione (i18n) di RuscaWriter.
Le traduzioni NON sono scritte nel codice: vivono in file JSON nella
cartella 'lang/' (uno per lingua, es. it.json, en.json, ...). Questo rende
il programma modulare e traducibile senza toccare il Python: per aggiungere
o completare una lingua basta editare il suo file JSON.
- LANGUAGES elenca le lingue delle RuscaLinux OS Apps (codice e nome
  nativo), come definite nelle specifiche, sezione 9.
- load_language(code) carica il dizionario di una lingua, con fallback
  automatico all'inglese (e poi alla chiave stessa) per le voci mancanti.
- Una lingua senza il suo file mostra l'interfaccia in inglese: non si
  scrivono file segnaposto (finivano nei pacchetti come copie dell'inglese).
- COMPLETE_LANGUAGES e' CALCOLATO dai file JSON, non scritto a mano: una
  lingua e' "completa" quando il suo file e' una traduzione vera, mentre
  gli scheletri (copie dell'inglese) fanno zero. Il menu quindi segue i
  file, e nessun secondo elenco va tenuto sincronizzato.
"""

import os
import json

# ---------------------------------------------------------------------------
# EN/IT: project folders (formerly paths.py) / cartelle del progetto (prima
# in paths.py). Layout / struttura:
#     <root>/src/ruscawriter/   this package / questo pacchetto
#     <root>/lang/              translations / traduzioni .json
#     <root>/assets/            fonts, icons / font, icone
# Installed by the deb, <root> is /usr/share/ruscawriter.
# ---------------------------------------------------------------------------
_HERE = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(_HERE, "..", ".."))
LANG_DIR = os.path.join(PROJECT_ROOT, "lang")
ASSETS_DIR = os.path.join(PROJECT_ROOT, "assets")


def asset(*parts):
    """EN: path of a file inside assets/. IT: percorso di un file in assets/."""
    return os.path.join(ASSETS_DIR, *parts)


def lang_file(code):
    """EN: path of a language file. IT: percorso di un file di lingua."""
    return os.path.join(LANG_DIR, f"{code}.json")

# Le lingue delle RuscaLinux OS Apps (SPECIFICHE-RUSCALINUX-OS-APPS, sezione 9).
# Ogni voce: codice -> (nome nativo, nome inglese). Il nome nativo è ciò che
# vede l'utente nel selettore, così riconosce la propria lingua.
# Codici con variante locale dove richiesto dalle specifiche: zh_CN, zh_TW, pt_BR, pt_PT.
LANGUAGES = {
    "en":    ("English", "English"),
    "zh_CN": ("简体中文", "Chinese (Simplified)"),
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
    "zh_TW": ("繁體中文", "Chinese (Traditional)"),
    "pt_PT": ("Português (Portugal)", "Portuguese (Portugal)"),
}

# Ripieghi fra lingue vicine (specifiche, sezione 9.2): Hong Kong e Macao
# usano il cinese tradizionale, Singapore il semplificato; il portoghese
# senza variante legge il brasiliano, lo slovacco il ceco.
# Chiavi in minuscolo, come le confronta detect_system_language().
LOCALE_ALIASES = {"zh_hk": "zh_TW", "zh_mo": "zh_TW", "zh_sg": "zh_CN", "zh": "zh_CN",
                  "pt": "pt_BR", "sk": "cs"}

# lingue di destra-a-sinistra (per l'orientamento dell'area di scrittura)
RTL_LANGUAGES = {"ar"}

# Locale predefinito del dizionario ortografico (Hunspell) per ciascuna lingua.
# I dizionari NON sono forniti dal programma: vanno installati nel sistema
# (es. su Debian/Ubuntu: "sudo apt install hunspell-fr" per il francese).
# Qui mappiamo solo il codice lingua al nome di locale più comune del dizionario.
SPELL_LOCALES = {
    "en":    "en_US",
    "zh_CN": "zh_CN",
    "es":    "es_ES",
    "hi":    "hi_IN",
    "ar":    "ar",
    "pt_BR": "pt_BR",
    "ru":    "ru_RU",
    "ja":    "ja_JP",
    "de":    "de_DE",
    "fr":    "fr_FR",
    "it":    "it_IT",
    "ko":    "ko_KR",
    "id":    "id_ID",
    "tr":    "tr_TR",
    "pl":    "pl_PL",
    "nl":    "nl_NL",
    "uk":    "uk_UA",
    "cs":    "cs_CZ",
    "vi":    "vi_VN",
    "sv":    "sv_SE",
    "ro":    "ro_RO",
    "hu":    "hu_HU",
    "el":    "el_GR",
    "fi":    "fi_FI",
    "zh_TW": "zh_TW",
    "pt_PT": "pt_PT",
}


def spell_locale_for(code):
    """Restituisce il nome del locale del dizionario per una lingua, o il
    codice stesso se non mappato (Gspell/GtkSpell tenteranno comunque)."""
    return SPELL_LOCALES.get(code, code)


def available_languages():
    """Restituisce la lista (codice, nome_nativo) ordinata per nome nativo,
    con le lingue complete in cima."""
    items = []
    for code, (native, _eng) in LANGUAGES.items():
        items.append((code, native))
    # ordina: prima le complete, poi le altre per nome nativo
    items.sort(key=lambda x: (x[0] not in COMPLETE_LANGUAGES, x[1].lower()))
    return items


def _load_json(code):
    path = os.path.join(LANG_DIR, f"{code}.json")
    if os.path.exists(path):
        try:
            with open(path, encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}


# ---------------------------------------------------------------------------
# EN: WHICH LANGUAGES ARE REALLY TRANSLATED — computed, not listed.
#     The menu splits languages into "complete" and "interface in English".
#     That split must follow the JSON files: a hand-written list goes stale
#     the day a translation lands (exactly what happened with the eight new
#     languages). A language counts as translated when a handful of probe
#     keys differ from English: a copy of English scores zero, while any
#     real translation scores full marks.
# IT: QUALI LINGUE SONO TRADOTTE DAVVERO — calcolato, non elencato.
#     Il menu divide le lingue fra "complete" e "interfaccia in inglese":
#     quella divisione deve seguire i file JSON, perche' un elenco scritto a
#     mano invecchia il giorno che arriva una traduzione (ed e' esattamente
#     cio' che e' successo con le otto lingue nuove). Una lingua conta come
#     tradotta quando alcune chiavi-sonda differiscono dall'inglese: una
#     copia dell'inglese fa zero, mentre una traduzione vera fa punteggio
#     pieno. make-deb.sh usa lo stesso criterio per rifiutare le copie.
# ---------------------------------------------------------------------------
PROBE_KEYS = ("btn_save", "btn_open", "menu_file",
              "menu_help", "mi_about", "cancel")


def is_complete(code):
    """True se la lingua ha una traduzione reale (non uno scheletro).
    L'inglese e' completo per definizione: e' il fallback di tutte."""
    if code == "en":
        return True
    raw = _load_json(code)
    if not raw:
        return False
    base = _load_json("en")
    diff = sum(1 for k in PROBE_KEYS
               if k in raw and raw.get(k) != base.get(k))
    # basta la maggioranza: una coincidenza isolata (es. "OK") non deve
    # retrocedere una traduzione vera, ma uno scheletro resta a zero
    return diff * 2 > len(PROBE_KEYS)


# calcolato una volta all'importazione: il menu lo legge come una costante
COMPLETE_LANGUAGES = frozenset(c for c in LANGUAGES if is_complete(c))


def load_language(code):
    """Carica il dizionario della lingua richiesta, completato con l'inglese
    per le chiavi mancanti (fallback). Restituisce sempre un dizionario usabile.
    L'ordine di risoluzione di ogni chiave, gestito altrove da Translator, è:
    lingua scelta -> inglese -> la chiave stessa."""
    base = _load_json("en")           # base di fallback
    chosen = _load_json(code) if code != "en" else {}
    merged = dict(base)
    merged.update(chosen)             # le voci tradotte sovrascrivono il fallback
    return merged


class Translator:
    """Piccolo gestore di traduzioni con cambio lingua a runtime.
    Uso tipico:
        tr = Translator("it")
        tr.t("mi_save")          -> "Salva"
        tr.set_language("fr")    -> ricarica il francese
        tr.t("mi_save", x=3)     -> supporta i segnaposto {x} via str.format
    """

    def __init__(self, code="en"):
        self.code = code
        self._strings = load_language(code)

    def set_language(self, code):
        self.code = code
        self._strings = load_language(code)

    def t(self, key, **kwargs):
        s = self._strings.get(key, key)   # fallback finale: la chiave stessa
        if kwargs:
            try:
                return s.format(**kwargs)
            except Exception:
                return s
        return s

    def is_rtl(self):
        return self.code in RTL_LANGUAGES


def apply_toolkit_language(code):
    """EN — make GTK and libspelling speak the interface language too.
    The menus RuscaWriter writes come from lang/*.json; but some come ready
    made from the toolkit: Cut, Copy, Paste, Undo, Select all, Insert emoji in
    the right-click menu, the spell checker's "Languages", the file chooser.
    Those are translated by gettext following the SYSTEM language, so an
    Italian desktop showed them in Italian under an English interface.
    LANGUAGE is the gettext variable that overrides the system language for
    messages only (dates, numbers and sorting keep the system settings).
    A language without a full translation shows the interface in English, so
    the toolkit is set to English too: one language on screen, never two.
    Setting the locale again tells glibc to drop the translations it cached.

    IT — fa parlare anche a GTK e libspelling la lingua dell'interfaccia.
    I menu scritti da RuscaWriter vengono da lang/*.json; alcuni pero' arrivano
    gia' pronti dal toolkit: Taglia, Copia, Incolla, Annulla, Seleziona tutto,
    Inserisci emoji nel menu del tasto destro, le "Lingue" del correttore, la
    finestra di scelta dei file. Quelli li traduce gettext seguendo la lingua
    di SISTEMA, quindi su un desktop italiano restavano in italiano sotto
    un'interfaccia inglese. LANGUAGE e' la variabile di gettext che scavalca la
    lingua di sistema solo per i messaggi (date, numeri e ordinamenti restano
    quelli di sistema). Una lingua non tradotta per intero mostra l'interfaccia
    in inglese, quindi anche il toolkit va in inglese: una lingua sola sullo
    schermo, mai due. Reimpostare il locale dice a glibc di buttare le
    traduzioni che teneva in memoria."""
    if code not in COMPLETE_LANGUAGES:
        code = "en"
    base = code.split("_")[0]
    os.environ["LANGUAGE"] = code if base == code else f"{code}:{base}"
    try:
        import locale
        locale.setlocale(locale.LC_MESSAGES, "")
    except Exception:
        pass        # un locale di sistema strano non deve impedire l'avvio
