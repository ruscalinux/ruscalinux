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
EN — RuscaWriter data model and document generation.

This module is INDEPENDENT from the graphical interface (it never imports
GTK): it holds the project structure (Chapter, Project), the native PDF
writer (write_pdf) and every export (TXT, Markdown, PDF, EPUB, ODT, DOCX,
HTML, AZW3), plus the helpers for the images attached to chapters
(PNG/JPEG/WebP). Being separate from the GUI, it can be tested on its own
and reused by other tools (scripts, batch conversions, etc.).

IT — Modello dati e generazione documenti di RuscaWriter.

Questo modulo è INDIPENDENTE dall'interfaccia grafica (non importa mai GTK):
contiene la struttura del progetto (Chapter, Project), il generatore PDF
nativo (write_pdf) e tutti gli export (TXT, Markdown, PDF, EPUB, ODT, DOCX,
HTML, AZW3), oltre agli helper per le immagini allegate ai capitoli
(PNG/JPEG/WebP). Essendo separato dalla GUI, può essere testato da solo ed
essere riusato da altri strumenti (script, conversioni batch, ecc.).
"""
import os
import io
import re
import json
import struct
import shutil
import tarfile
import tempfile

# EN: the common Markdown engine of the RuscaLinux OS Tools (CommonMark,
#     specifications section 1.2), identical in RuscaLLama, RuscaMark and
#     RuscaWriter.
# IT: il motore Markdown comune dei RuscaLinux OS Tools (CommonMark,
#     specifiche sezione 1.2), identico in RuscaLLama, RuscaMark e RuscaWriter.
from markdown_it.tree import SyntaxTreeNode
from .rusca_markdown import (parser as md_parser, parse_source, inline_mapper,
                             latex_to_text, math_to_text as render_math, table_at)

# EN: optional hyphenation support via Pyphen. Two things are needed and both
#     are OPTIONAL: (1) the Pyphen library (Debian "python3-pyphen") and (2) a
#     hyphenation DICTIONARY for the language. The Debian package of Pyphen
#     ships WITHOUT dictionaries and pulls them from the system "hyphen-*"
#     packages (e.g. "hyphen-it", "hyphen-en-us") under /usr/share/hyphen/;
#     the PyPI/pip package instead bundles its own. So on Debian/Ubuntu the
#     user typically needs BOTH python3-pyphen AND a hyphen-<lang> package.
#     When either is missing the PDF export still works: the "hyphenate"
#     option is simply unavailable (the GUI disables it, see editor.py) and we
#     never crash.
# IT: supporto opzionale alla sillabazione tramite Pyphen. Servono due cose,
#     entrambe OPZIONALI: (1) la libreria Pyphen (pacchetto Debian
#     "python3-pyphen") e (2) un DIZIONARIO di sillabazione per la lingua. Il
#     pacchetto Debian di Pyphen NON include i dizionari e li prende dai
#     pacchetti di sistema "hyphen-*" (es. "hyphen-it", "hyphen-en-us") sotto
#     /usr/share/hyphen/; il pacchetto PyPI/pip include invece i propri. Quindi
#     su Debian/Ubuntu di norma servono SIA python3-pyphen SIA un pacchetto
#     hyphen-<lingua>. Se manca l'uno o l'altro l'export PDF funziona lo
#     stesso: l'opzione "sillaba" e' semplicemente non disponibile (la GUI la
#     disattiva, vedi editor.py) e non falliamo mai.
try:
    import pyphen as _pyphen
    HAVE_PYPHEN = True
except Exception:
    _pyphen = None
    HAVE_PYPHEN = False

# cache dei dizionari di sillabazione gia' creati, per lingua (crearli e' caro)
_HYPHEN_DICTS = {}


def get_hyphenator(lang="it"):
    """EN: Return a cached Pyphen hyphenator for 'lang' (e.g. "it", "en_US"),
    or None if Pyphen is missing OR no dictionary exists for the language (for
    instance python3-pyphen installed without any hyphen-<lang> package).
    Pyphen accepts both "it" and "it_IT"; we try progressively broader codes.
    IT: Restituisce un sillabatore Pyphen (in cache) per 'lang' (es. "it",
    "en_US"), oppure None se Pyphen manca OPPURE non esiste un dizionario per
    quella lingua (per esempio python3-pyphen installato senza alcun pacchetto
    hyphen-<lingua>). Pyphen accetta sia "it" sia "it_IT"; proviamo codici via
    via piu' generici."""
    if not HAVE_PYPHEN:
        return None
    key = lang or "it"
    if key in _HYPHEN_DICTS:
        return _HYPHEN_DICTS[key]
    dic = None
    for cand in (key, key.split("_")[0], key.split("-")[0]):
        try:
            dic = _pyphen.Pyphen(lang=cand)
            break
        except Exception:
            dic = None
    _HYPHEN_DICTS[key] = dic
    return dic


def hyphenation_available(lang="it"):
    """EN: True only if hyphenation can actually be performed for 'lang' — i.e.
    Pyphen is importable AND a dictionary for the language is present. This is
    what the GUI should check to enable the "hyphenate" option, because having
    python3-pyphen without a hyphen-<lang> dictionary is not enough.
    IT: True solo se la sillabazione e' davvero eseguibile per 'lang' — cioe'
    Pyphen e' importabile E c'e' un dizionario per la lingua. E' cio' che la
    GUI deve controllare per abilitare l'opzione "sillaba", perche' avere
    python3-pyphen senza un dizionario hyphen-<lingua> non basta."""
    return get_hyphenator(lang) is not None


# --- costanti applicative condivise -----------------------------------------
APP_NAME = "RuscaWriter"

# ---------------------------------------------------------------------------
# UNICA FONTE della versione / SINGLE SOURCE of the version.
# IT: la versione e' quella di RuscaLinux (specifiche dei RuscaLinux OS Tools,
#     sezione 8). Titolo, finestra Informazioni e pacchetto ne derivano.
# EN: the version is RuscaLinux's. Title, About window and package derive
#     from it.
# ---------------------------------------------------------------------------
APP_VERSION_SHORT = "1.99.2"
APP_VERSION = APP_VERSION_SHORT
APP_AUTHOR = "Nunzio Curcuruto"

# Campi strutturati del frontespizio e del colophon. L'ordine e' anche l'ordine
# di impaginazione. Tutti i campi sono opzionali: quelli vuoti non compaiono.
FRONT_FIELDS = ["title", "subtitle", "author", "publisher", "place_year"]
COLO_FIELDS = ["copyright", "publisher", "isbn", "edition", "notes", "license"]

# Formati pagina disponibili per l'esportazione PDF. Dimensioni in punti
# tipografici (1/72 di pollice), come richiede il formato PDF. 1 cm ~= 28,35 pt;
# 1 pollice = 72 pt.
#   A5            = 148 x 210 mm  -> 420   x 595   pt  (narrativa/saggistica EU)
#   6x9 pollici   = 152 x 229 mm  -> 432   x 648   pt  (standard internaz./POD)
#   17x24 cm      = 170 x 240 mm  -> 482   x 680   pt  (saggistica densa/accademica)
#   A4            = 210 x 297 mm  -> 595   x 842   pt  (manuali, documenti, bozze)
#   5x8 pollici   = 127 x 203 mm  -> 360   x 576   pt  (tascabile narrativa)
#
# Ogni formato porta i propri margini, distinti tra:
#   inner  : margine INTERNO, lato rilegatura (piu' largo, cosi' il testo non
#            sparisce nella piega di una copertina incollata o cucita);
#   outer  : margine ESTERNO, lato del taglio (piu' stretto);
#   margin : margine verticale (alto/basso), uniforme.
# Sulle pagine recto (dispari) l'interno e' a sinistra, sul verso (pari) a
# destra: l'export se ne occupa da solo spostando il blocco di testo.
PDF_PAGE_SIZES = {
    "A5":    {"w": 420.0, "h": 595.0,
              "inner": 60.0, "outer": 42.0, "margin": 54.0},
    "6x9":   {"w": 432.0, "h": 648.0,
              "inner": 64.0, "outer": 45.0, "margin": 58.0},
    "17x24": {"w": 482.0, "h": 680.0,
              "inner": 70.0, "outer": 50.0, "margin": 62.0},
    "A4":    {"w": 595.0, "h": 842.0,
              "inner": 85.0, "outer": 65.0, "margin": 72.0},
    "5x8":   {"w": 360.0, "h": 576.0,
              "inner": 54.0, "outer": 38.0, "margin": 50.0},
}
PDF_DEFAULT_PAGE_SIZE = "A5"

# Etichette leggibili dei formati, per il menu di scelta nell'interfaccia.
PDF_PAGE_SIZE_LABELS = {
    "A5":    "A5 (14,8 \u00d7 21 cm)",
    "6x9":   "6\u00d79\" (15,2 \u00d7 22,9 cm)",
    "17x24": "17 \u00d7 24 cm",
    "A4":    "A4 (21 \u00d7 29,7 cm)",
    "5x8":   "5\u00d78\" (12,7 \u00d7 20,3 cm)",
}

# ---------------------------------------------------------------------------
# EN: PAGE MARGINS. Every margin a professional layout program offers:
#     top, bottom, inner (binding side), outer (fore-edge), an extra gutter
#     for the binding, and mirrored pages (inner on the left of a recto, on
#     the right of a verso) or plain left/right margins. Values are in
#     MILLIMETRES everywhere outside the PDF writer, so what is saved in the
#     document is readable by a person; they turn into points only at the
#     moment of writing the page.
# IT: MARGINI DI PAGINA. Tutti i margini di un programma di impaginazione
#     professionale: superiore, inferiore, interno (lato rilegatura), esterno
#     (lato taglio), una rilegatura aggiuntiva e le pagine speculari (interno
#     a sinistra sul recto, a destra sul verso) oppure semplici margini
#     sinistro/destro. I valori sono in MILLIMETRI ovunque fuori dallo
#     scrittore PDF, cosi' cio' che si salva nel documento e' leggibile da una
#     persona; diventano punti solo al momento di scrivere la pagina.
# ---------------------------------------------------------------------------
PT_PER_MM = 72.0 / 25.4
MARGIN_SIDES = ("top", "bottom", "inner", "outer")
MARGIN_MIN_MM = 5.0          # sotto i 5 mm molte stampanti tagliano il testo
MARGIN_MAX_MM = 80.0
GUTTER_MAX_MM = 25.0
# la gabbia del testo non deve ridursi a una striscia: almeno il 40% della
# larghezza e il 45% dell'altezza della pagina
TEXT_BLOCK_MIN_W_RATIO = 0.40
TEXT_BLOCK_MIN_H_RATIO = 0.45
# righe da leggere comodamente: fra 45 e 75 battute (Bringhurst)
CPL_COMFORT = (45, 75)
# larghezza media di un carattere del corpo, in em: vale per i serif da
# lettura (EB Garamond ~0,45), compresi gli spazi
AVG_CHAR_EM = 0.46

MARGIN_PRESET_FORMAT = "format"         # i margini studiati per il formato
MARGIN_PRESET_CANON = "canon"           # canone classico 2:3:4:6
MARGIN_PRESET_NOTES = "notes"           # esterno ampio per le note a margine
MARGIN_PRESET_MANUSCRIPT = "manuscript"  # 2,54 cm uguali, pagine non speculari
MARGIN_PRESETS = (MARGIN_PRESET_FORMAT, MARGIN_PRESET_CANON,
                  MARGIN_PRESET_NOTES, MARGIN_PRESET_MANUSCRIPT)
MARGIN_PRESET_CUSTOM = "custom"


def _pt_to_mm(v):
    return round(float(v) / PT_PER_MM, 1)


def page_size_mm(page_size):
    """EN/IT: (width, height) of a page format in mm / (larghezza, altezza)
    di un formato in mm."""
    spec = PDF_PAGE_SIZES.get(page_size, PDF_PAGE_SIZES[PDF_DEFAULT_PAGE_SIZE])
    return spec["w"] / PT_PER_MM, spec["h"] / PT_PER_MM


def margin_preset(preset, page_size):
    """EN/IT: the margins of a preset for a page format, in mm / i margini di
    un modello per un formato di pagina, in mm."""
    spec = PDF_PAGE_SIZES.get(page_size, PDF_PAGE_SIZES[PDF_DEFAULT_PAGE_SIZE])
    w, h = page_size_mm(page_size)
    if preset == MARGIN_PRESET_CANON:
        # il canone di Van de Graaf e Tschichold: interno, superiore, esterno
        # e inferiore stanno come 2:3:4:6 e la gabbia occupa 2/3 della pagina
        return {"top": round(h / 9, 1), "bottom": round(2 * h / 9, 1),
                "inner": round(w / 9, 1), "outer": round(2 * w / 9, 1),
                "gutter": 0.0, "mirror": True}
    if preset == MARGIN_PRESET_NOTES:
        base = margin_preset(MARGIN_PRESET_FORMAT, page_size)
        base["outer"] = round(max(base["outer"] * 2.0, 25.0), 1)
        return base
    if preset == MARGIN_PRESET_MANUSCRIPT:
        return {"top": 25.4, "bottom": 25.4, "inner": 25.4, "outer": 25.4,
                "gutter": 0.0, "mirror": False}
    return {"top": _pt_to_mm(spec["margin"]),
            "bottom": _pt_to_mm(spec["margin"]),
            "inner": _pt_to_mm(spec.get("inner", spec["margin"])),
            "outer": _pt_to_mm(spec.get("outer", spec["margin"])),
            "gutter": 0.0, "mirror": True}


def default_page_margins(page_size):
    return margin_preset(MARGIN_PRESET_FORMAT, page_size)


def text_block_mm(page_size, margins):
    """EN/IT: (width, height) of the text block in mm / (larghezza, altezza)
    della gabbia del testo in mm."""
    w, h = page_size_mm(page_size)
    return (w - margins["inner"] - margins["outer"] - margins["gutter"],
            h - margins["top"] - margins["bottom"])


def chars_per_line(page_size, margins, font_size):
    """EN/IT: the approximate number of characters in a full line / numero
    approssimativo di battute in una riga piena."""
    bw, _bh = text_block_mm(page_size, margins)
    if font_size <= 0:
        return 0
    return int(round(bw * PT_PER_MM / (font_size * AVG_CHAR_EM)))


def margin_problems(page_size, margins):
    """EN: what is wrong with a set of margins, as short codes; an empty list
    means they can be used.
    IT: cosa non va in un insieme di margini, come codici brevi; una lista
    vuota vuol dire che si possono usare.
      "too_small"  un margine sotto il minimo stampabile
      "too_large"  un margine o la rilegatura oltre il massimo
      "too_narrow" la gabbia e' troppo stretta
      "too_short"  la gabbia e' troppo bassa"""
    problemi = []
    for k in MARGIN_SIDES:
        if margins[k] < MARGIN_MIN_MM - 1e-6:
            problemi.append("too_small")
            break
    if (any(margins[k] > MARGIN_MAX_MM + 1e-6 for k in MARGIN_SIDES)
            or margins["gutter"] > GUTTER_MAX_MM + 1e-6
            or margins["gutter"] < -1e-6):
        problemi.append("too_large")
    w, h = page_size_mm(page_size)
    bw, bh = text_block_mm(page_size, margins)
    if bw < w * TEXT_BLOCK_MIN_W_RATIO:
        problemi.append("too_narrow")
    if bh < h * TEXT_BLOCK_MIN_H_RATIO:
        problemi.append("too_short")
    return problemi


def normalize_page_margins(data, page_size):
    """EN: turn whatever was saved (possibly old, partial or hand-edited)
    into a complete, usable set of margins in mm. Anything unusable falls
    back to the format's own margins, never to a broken page.
    IT: trasforma cio' che e' stato salvato (magari vecchio, parziale o
    modificato a mano) in un insieme di margini completo e utilizzabile, in
    mm. Cio' che non si puo' usare ripiega sui margini del formato, mai su
    una pagina rotta."""
    base = default_page_margins(page_size)
    if not isinstance(data, dict):
        return base
    out = dict(base)
    for k in MARGIN_SIDES + ("gutter",):
        v = data.get(k)
        if isinstance(v, (int, float)) and not isinstance(v, bool):
            out[k] = round(float(v), 1)
    if isinstance(data.get("mirror"), bool):
        out["mirror"] = data["mirror"]
    return base if margin_problems(page_size, out) else out


def margins_to_pdf_args(margins):
    """EN/IT: the write_pdf() keyword arguments for a set of margins in mm /
    gli argomenti di write_pdf() per un insieme di margini in mm."""
    return {"margin": margins["top"] * PT_PER_MM,
            "margin_top": margins["top"] * PT_PER_MM,
            "margin_bottom": margins["bottom"] * PT_PER_MM,
            "margin_inner": margins["inner"] * PT_PER_MM,
            "margin_outer": margins["outer"] * PT_PER_MM,
            "gutter": margins["gutter"] * PT_PER_MM,
            "mirror": bool(margins["mirror"])}


def which_margin_preset(page_size, margins):
    """EN/IT: the preset these margins match, or "custom" / il modello a cui
    corrispondono questi margini, o "custom"."""
    for preset in MARGIN_PRESETS:
        ref = margin_preset(preset, page_size)
        if (ref["mirror"] == margins.get("mirror")
                and all(abs(ref[k] - margins.get(k, -1)) < 0.05
                        for k in MARGIN_SIDES + ("gutter",))):
            return preset
    return MARGIN_PRESET_CUSTOM

TYPEWRITER_FAMILY = "Courier Prime"
TYPEWRITER_FILE = "CourierPrime-Regular.ttf"
# varianti per il rendering di grassetto/corsivo nel PDF
TYPEWRITER_FILES = {
    "regular":    "CourierPrime-Regular.ttf",
    "bold":       "CourierPrime-Bold.ttf",
    "italic":     "CourierPrime-Italic.ttf",
    "bolditalic": "CourierPrime-BoldItalic.ttf",
}

# Font serif da lettura per i documenti ESPORTATI (PDF in primis): EB Garamond,
# un Garamond libero (licenza SIL Open Font License 1.1), molto più adatto a un
# libro/romanzo del monospace Courier Prime usato nell'editor. È proporzionale,
# quindi l'export PDF usa le larghezze reali dei glifi (widths_by_code).
SERIF_FAMILY = "EB Garamond"
SERIF_FILE = "EBGaramond-Regular.ttf"
SERIF_FILES = {
    "regular":    "EBGaramond-Regular.ttf",
    "bold":       "EBGaramond-Bold.ttf",
    "italic":     "EBGaramond-Italic.ttf",
    "bolditalic": "EBGaramond-BoldItalic.ttf",
}
DEFAULT_FONT_SIZE = 14
MIN_FONT_SIZE = 8
MAX_FONT_SIZE = 48

_TIMES_WIDTHS = {
    ' ': 250, '!': 333, '"': 408, '#': 500, '$': 500, '%': 833, '&': 778,
    "'": 180, '(': 333, ')': 333, '*': 500, '+': 564, ',': 250, '-': 333,
    '.': 250, '/': 278, '0': 500, '1': 500, '2': 500, '3': 500, '4': 500,
    '5': 500, '6': 500, '7': 500, '8': 500, '9': 500, ':': 278, ';': 278,
    '<': 564, '=': 564, '>': 564, '?': 444, '@': 921, 'A': 722, 'B': 667,
    'C': 667, 'D': 722, 'E': 611, 'F': 556, 'G': 722, 'H': 722, 'I': 333,
    'J': 389, 'K': 722, 'L': 611, 'M': 889, 'N': 722, 'O': 722, 'P': 556,
    'Q': 722, 'R': 667, 'S': 556, 'T': 611, 'U': 722, 'V': 722, 'W': 944,
    'X': 722, 'Y': 722, 'Z': 611, '[': 333, '\\': 278, ']': 333, '^': 469,
    '_': 500, '`': 333, 'a': 444, 'b': 500, 'c': 444, 'd': 500, 'e': 444,
    'f': 333, 'g': 500, 'h': 500, 'i': 278, 'j': 278, 'k': 500, 'l': 278,
    'm': 778, 'n': 500, 'o': 500, 'p': 500, 'q': 500, 'r': 333, 's': 389,
    't': 278, 'u': 500, 'v': 500, 'w': 722, 'x': 500, 'y': 500, 'z': 444,
    '{': 480, '|': 200, '}': 480, '~': 541,
}
_TIMES_DEFAULT_WIDTH = 500


def _char_width(ch, font_size):
    return _TIMES_WIDTHS.get(ch, _TIMES_DEFAULT_WIDTH) / 1000.0 * font_size


def _text_width(s, font_size, advance1000=None, widths_by_code=None):
    """Larghezza del testo in punti.

    - widths_by_code: dict {codice WinAnsi -> larghezza in 1/1000 em} per i font
      proporzionali incorporati (es. EB Garamond): usa la larghezza reale di
      ogni carattere. È il caso più preciso e ha la precedenza.
    - advance1000: larghezza fissa per glifo (font monospace, es. Courier).
    - altrimenti: metriche Times di ripiego."""
    if widths_by_code is not None:
        total = 0.0
        default = advance1000 if advance1000 is not None else 500
        for ch in s:
            # chiavi = codepoint Unicode (uni_widths) o, per le mappe WinAnsi,
            # gli stessi codepoint nell'intervallo Latin-1
            total += widths_by_code.get(ord(ch), default)
        return total / 1000.0 * font_size
    if advance1000 is not None:
        return len(s) * advance1000 / 1000.0 * font_size
    return sum(_char_width(c, font_size) for c in s)


def _parse_cmap_unicode(data, cmap_off):
    """Estrae una mappa {codepoint Unicode -> glyph id} da una tabella cmap.
    Supporta i formati 4 (BMP) e 12 (full Unicode), i piu' comuni. Restituisce
    un dict, eventualmente vuoto se nessuna sottotabella e' utilizzabile."""
    mapping = {}
    try:
        ntab = struct.unpack(">H", data[cmap_off+2:cmap_off+4])[0]
        best = None   # (preferenza, offset_sottotabella)
        for i in range(ntab):
            rec = cmap_off + 4 + i*8
            plat, enc = struct.unpack(">HH", data[rec:rec+4])
            sub_off = struct.unpack(">I", data[rec+4:rec+8])[0]
            # preferenza: Windows BMP/UCS4 (3,1)/(3,10) e Unicode (0,*)
            pref = {(3,10):4, (0,6):4, (3,1):3, (0,4):3, (0,3):3}.get(
                (plat, enc), 1 if plat == 0 else 0)
            if best is None or pref > best[0]:
                best = (pref, cmap_off + sub_off)
        if best is None:
            return mapping
        off = best[1]
        fmt = struct.unpack(">H", data[off:off+2])[0]
        if fmt == 4:
            segx2 = struct.unpack(">H", data[off+6:off+8])[0]
            segc = segx2 // 2
            p = off + 14
            ends = struct.unpack(">%dH" % segc, data[p:p+segx2]); p += segx2 + 2
            starts = struct.unpack(">%dH" % segc, data[p:p+segx2]); p += segx2
            deltas = struct.unpack(">%dh" % segc, data[p:p+segx2]); p += segx2
            range_off_pos = p
            ranges = struct.unpack(">%dH" % segc, data[p:p+segx2])
            for s in range(segc):
                start, end, delta, ro = starts[s], ends[s], deltas[s], ranges[s]
                if start == 0xFFFF:
                    continue
                for c in range(start, end+1):
                    if ro == 0:
                        g = (c + delta) & 0xFFFF
                    else:
                        gi = range_off_pos + s*2 + ro + (c - start)*2
                        if gi+2 > len(data):
                            continue
                        g = struct.unpack(">H", data[gi:gi+2])[0]
                        if g != 0:
                            g = (g + delta) & 0xFFFF
                    if g != 0:
                        mapping[c] = g
        elif fmt == 12:
            ngroups = struct.unpack(">I", data[off+12:off+16])[0]
            p = off + 16
            for _ in range(ngroups):
                sc, ec, sg = struct.unpack(">III", data[p:p+12]); p += 12
                for c in range(sc, ec+1):
                    mapping[c] = sg + (c - sc)
    except Exception:
        return {}
    return mapping


# ---------------------------------------------------------------------------
# EN: SYSTEM FONTS.
#     RuscaWriter ships two fonts — a typewriter one for the writing area and a
#     reading serif for the exports — and they stay the default. But a person
#     writing a book may well own the face they want, so the fonts installed on
#     the machine are offered too.
#
#     Only TrueType (.ttf) families are listed: the PDF writer embeds glyph
#     outlines as TrueType, so an OpenType/CFF face could be shown on screen
#     but not put inside the PDF — better not to offer what cannot be honoured.
#
# IT: FONT DI SISTEMA.
#     RuscaWriter porta con se' due font — uno da macchina da scrivere per
#     l'area di scrittura e un serif da lettura per gli export — e restano i
#     predefiniti. Ma chi scrive un libro puo' benissimo avere gia' il
#     carattere che vuole, quindi si offrono anche i font installati sulla
#     macchina.
#
#     Si elencano SOLO le famiglie TrueType (.ttf): l'impaginatore PDF
#     incorpora i contorni dei glifi in formato TrueType, quindi un font
#     OpenType/CFF si vedrebbe a schermo ma non finirebbe nel PDF. Meglio non
#     offrire cio' che non si puo' mantenere.
# ---------------------------------------------------------------------------

# Cartelle in cui i sistemi tipo Unix tengono i font.
SYSTEM_FONT_DIRS = (
    "/usr/share/fonts",
    "/usr/local/share/fonts",
    os.path.expanduser("~/.local/share/fonts"),
    os.path.expanduser("~/.fonts"),
)

# Come si chiamano i quattro stili nella tabella 'name' di un TTF.
_TTF_SUBFAMILY_TO_STYLE = {
    "regular": "regular", "book": "regular", "roman": "regular",
    "bold": "bold",
    "italic": "italic", "oblique": "italic",
    "bold italic": "bolditalic", "bolditalic": "bolditalic",
    "bold oblique": "bolditalic",
}


def read_ttf_names(path):
    """Nome della famiglia e dello stile di un file TTF, o (None, None).

    Legge SOLO l'intestazione e la tabella dei nomi, con due letture mirate:
    scorrere centinaia di font di sistema caricandoli interi sarebbe lento
    senza motivo."""
    try:
        with open(path, "rb") as f:
            testa = f.read(12)
            if len(testa) < 12 or testa[:4] not in (b"\x00\x01\x00\x00", b"true"):
                return (None, None)     # non e' un TrueType (potrebbe essere CFF)
            n_tab = struct.unpack(">H", testa[4:6])[0]
            elenco = f.read(16 * n_tab)
            offset = lunghezza = None
            for i in range(n_tab):
                voce = elenco[i * 16:(i + 1) * 16]
                if voce[:4] == b"name":
                    offset, lunghezza = struct.unpack(">II", voce[8:16])
                    break
            if offset is None:
                return (None, None)
            f.seek(offset)
            tabella = f.read(lunghezza)

        conteggio, area = struct.unpack(">HH", tabella[2:6])
        famiglia = stile = None
        for i in range(conteggio):
            rec = tabella[6 + i * 12:18 + i * 12]
            if len(rec) < 12:
                break
            plat, enc, _lang, nome_id, lung, off = struct.unpack(">HHHHHH", rec)
            if nome_id not in (1, 2):
                continue
            grezzo = tabella[area + off:area + off + lung]
            try:
                if plat == 3 or (plat == 0):        # Windows/Unicode: UTF-16BE
                    testo = grezzo.decode("utf-16-be", "ignore")
                else:                                # Macintosh: latin-1
                    testo = grezzo.decode("latin-1", "ignore")
            except Exception:
                continue
            testo = testo.strip()
            if not testo:
                continue
            if nome_id == 1 and famiglia is None:
                famiglia = testo
            elif nome_id == 2 and stile is None:
                stile = testo
        return (famiglia, stile)
    except Exception:
        return (None, None)


def system_font_families(dirs=None):
    """Famiglie TrueType installate sulla macchina.

    Restituisce {nome_famiglia: {stile: percorso}}, con stile fra 'regular',
    'bold', 'italic' e 'bolditalic'. Sono incluse solo le famiglie che hanno
    almeno il tondo: senza quello non si puo' impaginare niente.
    """
    trovate = {}
    for cartella in (dirs if dirs is not None else SYSTEM_FONT_DIRS):
        if not os.path.isdir(cartella):
            continue
        for radice, _sub, files in os.walk(cartella):
            for nome_file in files:
                if not nome_file.lower().endswith(".ttf"):
                    continue
                percorso = os.path.join(radice, nome_file)
                famiglia, sottofamiglia = read_ttf_names(percorso)
                if not famiglia:
                    continue
                stile = _TTF_SUBFAMILY_TO_STYLE.get(
                    (sottofamiglia or "regular").strip().lower())
                if stile is None:
                    continue
                trovate.setdefault(famiglia, {}).setdefault(stile, percorso)
    return {fam: stili for fam, stili in trovate.items() if "regular" in stili}


def font_files_for_family(famiglia, dirs=None):
    """Percorsi dei file di una famiglia di sistema, per stile. Dizionario
    vuoto se la famiglia non c'e' o non ha il tondo."""
    return system_font_families(dirs).get(famiglia, {})


def read_ttf_metrics(path):
    """Legge le metriche essenziali di un TTF (solo libreria standard).
    Restituisce un dict con i dati per incorporarlo in un PDF, oppure None.

    Per i font proporzionali (es. EB Garamond) estrae anche la larghezza di
    ogni carattere nell'intervallo WinAnsi 32..255, in 'widths_by_code', cosi'
    l'impaginazione del PDF e l'array /Widths usano la larghezza reale di ogni
    glifo invece di una larghezza fissa (che andrebbe bene solo per i
    monospace). 'advance1000' resta come ripiego."""
    try:
        with open(path, "rb") as f:
            data = f.read()
    except Exception:
        return None
    try:
        num_tables = struct.unpack(">H", data[4:6])[0]
        tables = {}
        off = 12
        for _ in range(num_tables):
            tag = data[off:off+4]
            t_off, t_len = struct.unpack(">II", data[off+8:off+16])
            tables[tag] = (t_off, t_len)
            off += 16

        def tbl(tag):
            o, l = tables[tag]
            return data[o:o+l]

        head = tbl(b"head")
        units_per_em = struct.unpack(">H", head[18:20])[0]
        x_min, y_min, x_max, y_max = struct.unpack(">hhhh", head[36:44])

        hhea = tbl(b"hhea")
        ascent, descent = struct.unpack(">hh", hhea[4:8])
        num_hmetrics = struct.unpack(">H", hhea[34:36])[0]

        hmtx = tbl(b"hmtx")
        # advance del primo glifo (per monospace e' la larghezza comune)
        adv0 = struct.unpack(">H", hmtx[0:2])[0]

        scale = 1000.0 / units_per_em

        # advance per ciascun glyph id: i primi num_hmetrics hanno valore
        # esplicito, gli altri ripetono l'ultimo (regola TrueType).
        def glyph_advance(gid):
            if gid < num_hmetrics:
                pos = gid * 4
            else:
                pos = (num_hmetrics - 1) * 4
            if pos + 2 > len(hmtx):
                return adv0
            return struct.unpack(">H", hmtx[pos:pos+2])[0]

        # larghezze per codice WinAnsi 32..255 tramite cmap (se disponibile)
        widths_by_code = None
        try:
            if b"cmap" in tables:
                cmap_off = tables[b"cmap"][0]
                uni2gid = _parse_cmap_unicode(data, cmap_off)
                if uni2gid:
                    wbc = {}
                    for code in range(32, 256):
                        # mappa il codice WinAnsi al suo codepoint Unicode
                        cp = _winansi_to_unicode(code)
                        gid = uni2gid.get(cp, 0)
                        adv = glyph_advance(gid) if gid else adv0
                        wbc[code] = int(round(adv * scale))
                    widths_by_code = wbc
        except Exception:
            widths_by_code = None

        # EN: Unicode metrics for the Type0 (Identity-H) PDF fonts: every
        #     character the font has, so Greek, Cyrillic and formula symbols
        #     are no longer turned into "?" by the single-byte WinAnsi.
        # IT: metriche Unicode per i font PDF Type0 (Identity-H): ogni
        #     carattere presente nel font, cosi' greco, cirillico e simboli
        #     delle formule non diventano piu' "?" come con WinAnsi a un byte.
        uni2gid = {}
        try:
            if b"cmap" in tables:
                uni2gid = _parse_cmap_unicode(data, tables[b"cmap"][0]) or {}
        except Exception:
            uni2gid = {}
        uni_widths = {cp: int(round(glyph_advance(g) * scale))
                      for cp, g in uni2gid.items() if g}

        result = {
            "data": data,
            "units_per_em": units_per_em,
            "bbox": [int(x_min*scale), int(y_min*scale),
                     int(x_max*scale), int(y_max*scale)],
            "ascent": int(ascent*scale),
            "descent": int(descent*scale),
            "advance1000": int(round(adv0*scale)),
        }
        if widths_by_code is not None:
            result["widths_by_code"] = widths_by_code
        if uni2gid:
            result["uni2gid"] = {cp: g for cp, g in uni2gid.items() if g}
            result["uni_widths"] = uni_widths
        return result
    except Exception:
        return None


def _wrap_line(line, font_size, max_width, advance1000=None, widths_by_code=None):
    """Spezza una riga in più righe che entrano in max_width (in punti)."""
    if not line.strip():
        return [""]
    def tw(s):
        return _text_width(s, font_size, advance1000, widths_by_code)
    words = line.split(" ")
    out, cur = [], ""
    for w in words:
        candidate = w if not cur else cur + " " + w
        if tw(candidate) <= max_width or not cur:
            # se una singola parola e' piu' larga della pagina, spezzala a forza
            if not cur and tw(w) > max_width:
                piece = ""
                for ch in w:
                    if tw(piece + ch) <= max_width or not piece:
                        piece += ch
                    else:
                        out.append(piece)
                        piece = ch
                cur = piece
            else:
                cur = candidate
        else:
            out.append(cur)
            cur = w
    if cur:
        out.append(cur)
    return out


def _pdf_escape(s):
    return s.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def _pdf_escape_bytes(b):
    return (b.replace(b"\\", b"\\\\")
             .replace(b"(", b"\\(")
             .replace(b")", b"\\)"))


def _to_winansi(s):
    """Codifica una stringa in byte per WinAnsiEncoding (cp1252).
    I caratteri non rappresentabili vengono sostituiti con '?'."""
    return s.encode("cp1252", "replace")


# ---------------------------------------------------------------------------
# EN: fallback fonts for the PDF. The book font (EB Garamond, Courier Prime)
#     has no emoji and few symbols: for each character it lacks, fontconfig
#     finds a system font that has it, as typesetting programs do. Only
#     TrueType fonts with real outlines can be embedded (colour bitmap emoji
#     fonts cannot); a character no font can draw is left out rather than
#     printed as "?". Invisible emoji helpers (variation selectors, joiners,
#     skin tones) are never printed.
# IT: font di riserva per il PDF. Il font del libro (EB Garamond, Courier
#     Prime) non ha emoji e ha pochi simboli: per ogni carattere che manca,
#     fontconfig trova un font del sistema che lo contiene, come fanno i
#     programmi di impaginazione. Si incorporano solo font TrueType con
#     contorni veri (non i font di emoji a colori bitmap); un carattere che
#     nessun font sa disegnare viene omesso invece di stampare "?". I
#     caratteri invisibili delle emoji (selettori di variante, unioni,
#     tonalita' della pelle) non si stampano mai.
# ---------------------------------------------------------------------------
_FALLBACK_CACHE = {}          # percorso -> metriche (o None se inutilizzabile)
_FALLBACK_MAX_FONTS = 6


# EN/IT: a Markdown thematic break (---, ***, ___) / linea di separazione
_HR_RE = re.compile(r"^\s{0,3}([-*_])(?:[ \t]*\1){2,}[ \t]*$")


def _is_invisible_mark(cp):
    # anche le lettere delle bandiere (🇮🇹 = I + T regionali): una bandiera
    # esiste solo nei font a colori, in bianco e nero sarebbero due lettere
    # in un riquadro
    return (cp in (0x200B, 0x200C, 0x200D, 0x2060, 0xFE0E, 0xFE0F, 0x20E3)
            or 0x1F3FB <= cp <= 0x1F3FF or 0xE0020 <= cp <= 0xE007F
            or 0x1F1E6 <= cp <= 0x1F1FF)


def _outline_font_metrics(path):
    """Metriche di un font TrueType con contorni, o None (CFF, emoji a colori
    in bitmap, collezioni .ttc, file illeggibili)."""
    if path in _FALLBACK_CACHE:
        return _FALLBACK_CACHE[path]
    metrics = None
    try:
        if path.lower().endswith((".ttf", ".otf")):
            with open(path, "rb") as f:
                head = f.read(12)
                num = struct.unpack(">H", head[4:6])[0]
                tags = {f.read(16)[:4] for _ in range(num)}
            if b"glyf" in tags and not tags & {b"CBDT", b"sbix", b"SVG ", b"COLR"}:
                metrics = read_ttf_metrics(path)
                if metrics and not metrics.get("uni2gid"):
                    metrics = None
    except (OSError, struct.error, ValueError):
        metrics = None
    _FALLBACK_CACHE[path] = metrics
    return metrics


def _fontconfig_files(cp):
    """File dei font del sistema che contengono il carattere cp (fontconfig)."""
    import shutil
    import subprocess
    exe = shutil.which("fc-list")
    if not exe:
        return []
    try:
        out = subprocess.run([exe, "--format", "%{file}\n", f":charset={cp:x}"],
                             capture_output=True, text=True, timeout=10).stdout
    except (OSError, subprocess.SubprocessError):
        return []
    # Unifont e LastResort disegnano riquadri o pixel: meglio omettere
    files = [ln.strip() for ln in out.splitlines()
             if ln.strip() and not re.search(r"unifont|lastresort", ln, re.I)]
    # prima i font «normali» (Regular/Book), poi gli altri
    files.sort(key=lambda f: (not re.search(r"(Regular|Book|-R)\.", f), len(f)))
    return files


def pdf_fallback_fonts(primary, texts):
    """EN/IT: (char -> index of the fallback font, list of fallback metrics,
    set of invisible or undrawable chars). primary = metrics of the book
    font; texts = all the strings the PDF will print."""
    have = primary.get("uni2gid", {})
    chars = {ch for t in texts for ch in t if ord(ch) >= 32}
    # i segni invisibili e le lettere delle bandiere si omettono anche se il
    # font del libro li ha (EB Garamond ha le lettere regionali in riquadro)
    drop = {ch for ch in chars if _is_invisible_mark(ord(ch))}
    missing = sorted(ch for ch in chars - drop if ord(ch) not in have)
    use, fonts = {}, []
    for ch in missing:
        cp = ord(ch)
        idx = next((i for i, m in enumerate(fonts) if cp in m["uni2gid"]), None)
        if idx is None and len(fonts) < _FALLBACK_MAX_FONTS:
            for path in _fontconfig_files(cp):
                m = _outline_font_metrics(path)
                if m and cp in m["uni2gid"]:
                    fonts.append(m)
                    idx = len(fonts) - 1
                    break
        if idx is None:
            drop.add(ch)
        else:
            use[ch] = idx
    return use, fonts, drop


def _tables_to_text(text):
    """EN: Markdown tables -> columns aligned with spaces, for plain text.
    IT: Tabelle Markdown -> colonne allineate con spazi, per il testo
    semplice."""
    lines = text.split("\n")
    out, i = [], 0
    while i < len(lines):
        tbl = table_at(lines, i)
        if not tbl:
            out.append(lines[i])
            i += 1
            continue
        aligns, header, rows, i = tbl
        grid = [[_strip_inline_md(c) for c in r] for r in [header] + rows]
        widths = [max(len(r[c]) for r in grid) for c in range(len(header))]

        def fmt(r):
            cells = [v.rjust(w) if a == "right" else v.center(w) if a == "center"
                     else v.ljust(w) for v, w, a in zip(r, widths, aligns)]
            return "  ".join(cells).rstrip()
        out.append(fmt(grid[0]))
        out.append("  ".join("-" * w for w in widths))
        out.extend(fmt(r) for r in grid[1:])
    return "\n".join(out)


def _pdf_text_string(s):
    """Stringa di testo PDF (titoli dell'indice di navigazione): in WinAnsi
    quando basta, come prima, altrimenti UTF-16 con BOM, che ogni lettore
    capisce (greco, cirillico, cinese, simboli)."""
    try:
        return b"(" + _pdf_escape_bytes(s.encode("cp1252")) + b")"
    except UnicodeEncodeError:
        return b"<FEFF" + s.encode("utf-16-be").hex().upper().encode("ascii") + b">"


def _winansi_to_unicode(code):
    """Converte un valore di byte WinAnsi (cp1252), 0..255, nel suo codepoint
    Unicode. Serve per mappare i codici dell'array /Widths del PDF ai glifi del
    font tramite la cmap Unicode. Per i codici non assegnati ripiega sul codice
    stesso."""
    try:
        return ord(bytes([code]).decode("cp1252"))
    except Exception:
        return code


# ---------------------------------------------------------------------------
# EN: THE MARKDOWN RULES, IN ONE PLACE.
#     Markdown is read by the common engine (rusca_markdown: CommonMark with
#     the extensions of the specifications, section 1.2). book_blocks() turns
#     a chapter into the blocks of the book, and every part of the program
#     that shows a chapter — the PDF typesetter, the HTML and EPUB exports,
#     the ODT and DOCX exports, the on-screen preview — starts from there;
#     the live highlighting asks highlight_spans(), from the same engine.
#     One rule is RuscaWriter's own: every line break in the text is a line
#     break in the book (lines written one under the other are not merged
#     into one paragraph, as CommonMark would do).
#
# IT: LE REGOLE DEL MARKDOWN, IN UN POSTO SOLO.
#     Il Markdown lo legge il motore comune (rusca_markdown: CommonMark con le
#     estensioni delle specifiche, sezione 1.2). book_blocks() trasforma un
#     capitolo nei blocchi del libro, e ogni parte del programma che mostra
#     un capitolo — l'impaginatore PDF, gli export HTML ed EPUB, quelli ODT e
#     DOCX, l'anteprima — parte da lì; l'evidenziazione dal vivo chiede
#     highlight_spans(), dallo stesso motore. Una regola è solo di
#     RuscaWriter: ogni a capo del testo va a capo anche nel libro (le righe
#     scritte una sotto l'altra non si fondono in un paragrafo, come farebbe
#     CommonMark).
# ---------------------------------------------------------------------------

# Stili dei tratti di testo. 'code' e' un caso a se': dentro i backtick il
# testo resta letterale, senza altra formattazione.
INLINE_STYLES = ("regular", "bold", "italic", "bolditalic", "code")

# Interruzioni dentro un paragrafo del motore: due «stili» speciali che i
# tratti usano solo per dividere il testo in righe (vedi book_blocks).
_SOFT, _HARD = "\x00soft", "\x00hard"


def _style_name(bold, italic):
    if bold and italic:
        return "bolditalic"
    if bold:
        return "bold"
    if italic:
        return "italic"
    return "regular"


def link_display(etichetta, indirizzo):
    """Come si scrive un link in un libro: l'etichetta, poi l'indirizzo fra
    parentesi.

    NIENTE LINK CLICCABILI, e l'indirizzo SEMPRE IN CHIARO. Sono due facce
    della stessa scelta. Un link cliccabile puo' portare altrove da quel che
    l'etichetta promette, e in un documento che gira non e' un rischio da
    regalare a chi legge. Ma soprattutto: un libro si stampa, e su una pagina
    di carta nessuno clicca — se l'indirizzo non e' scritto, la fonte citata
    non e' raggiungibile. Prima veniva buttato via in silenzio.

    Se etichetta e indirizzo dicono gia' la stessa cosa non si ripete nulla.
    """
    etichetta = (etichetta or "").strip()
    indirizzo = (indirizzo or "").strip()
    if not indirizzo:
        return etichetta
    if not etichetta:
        return indirizzo
    # "vedi https://x.it" o "[https://x.it](https://x.it)": non raddoppiare
    nudo = indirizzo.split("://", 1)[-1].rstrip("/")
    if etichetta.rstrip("/").endswith(nudo) or nudo.endswith(etichetta.rstrip("/")):
        return etichetta
    return f"{etichetta} ({indirizzo})"


def _plain(nodes):
    """Testo semplice di nodi in linea (etichette di link e immagini)."""
    return "".join(t for t, st in _runs(nodes) if st not in (_SOFT, _HARD, "image")) \
        if nodes else ""


def _runs(nodes, bold=False, italic=False, out=None):
    """Nodi in linea del motore -> tratti (testo, stile). Le formule diventano
    simboli Unicode, i link «testo (indirizzo)» (vedi link_display), i
    riferimenti alle note «[1]». Barrato ed evidenziato non hanno uno stile
    proprio nei formati del libro: resta il testo, senza marcatori. Un'immagine
    diventa il tratto speciale ((didascalia, nome), "image")."""
    if out is None:
        out = []
    style = _style_name(bold, italic)
    after_box = False
    for n in nodes:
        t = n.type
        if t == "text":
            out.append((n.content.lstrip(" ") if after_box else n.content, style))
        elif t == "softbreak":
            out.append(("", _SOFT))
        elif t == "hardbreak":
            out.append(("", _HARD))
        elif t == "code_inline":
            out.append((n.content, "code"))
        elif t == "strong":
            _runs(n.children, True, italic, out)
        elif t == "em":
            _runs(n.children, bold, True, out)
        elif t in ("math_inline", "math_inline_double"):
            out.append((latex_to_text(n.content), style))
        elif t == "link":
            label = _plain(n.children)
            shown = link_display(label, str(n.attrs.get("href", "")))
            if shown.startswith(label):
                _runs(n.children, bold, italic, out)
                if shown != label:
                    out.append((shown[len(label):], style))
            else:
                out.append((shown, style))
        elif t == "image":
            out.append(((_plain(n.children),
                         md_parser().normalizeLinkText(str(n.attrs.get("src", "")))), "image"))
        elif t == "footnote_ref":
            out.append((f"[{n.meta['id'] + 1}]", style))
        elif t in ("html_inline", "footnote_anchor"):
            pass                      # casella delle liste di attività; ritorno dalla nota
        elif n.children:
            _runs(n.children, bold, italic, out)
        else:
            out.append((n.content, style))
        after_box = t == "html_inline"
    return out


def _merge(runs):
    """Tratti consecutivi dello stesso stile in uno solo; via quelli vuoti."""
    out = []
    for text, style in runs:
        if style == "image":
            out.append((text, style))
        elif not text:
            continue
        elif out and out[-1][1] == style:
            out[-1] = (out[-1][0] + text, style)
        else:
            out.append((text, style))
    return out


def _inline_nodes(text):
    """Nodi in linea di un testo di una riga (cella, titolo, didascalia)."""
    tokens = md_parser().parseInline(text)
    return SyntaxTreeNode(tokens).children[0].children if tokens else []


def parse_inline(text):
    """Spezza il testo in segmenti (testo, stile), stile in INLINE_STYLES.

    L'analisi e' quella del motore comune (CommonMark). I link
    [testo](indirizzo) diventano "testo (indirizzo)": vedi link_display.
    Restituisce sempre almeno un segmento, così chi impagina non deve
    gestire la lista vuota."""
    runs = []
    for t, st in _runs(_inline_nodes(text)):
        if st == "image":
            runs.append((t[0], "regular"))
        elif st in (_SOFT, _HARD):
            runs.append((" " if st == _SOFT else "\n", "regular"))
        else:
            runs.append((t, st))
    segments = _merge(runs)
    return segments or [("", "regular")]


def _emphasis_spans(token, to_doc):
    """Tratti di grassetto, corsivo e codice di un token «inline» di
    parse_source(), marcatori compresi: (inizio, fine, stile), il tratto
    esterno prima di quello interno. Lo stile tiene conto di quelli che lo
    contengono: un corsivo dentro un grassetto e' «bolditalic»."""
    spans, stack = [], []
    for c in token.children or []:
        src = c.meta.get("src")
        if c.type in ("strong_open", "em_open"):
            stack.append(c)
        elif c.type in ("strong_close", "em_close") and stack:
            o = stack.pop()
            if "src" not in o.meta or src is None:
                continue
            n = len(c.markup)
            kinds = {x.type for x in stack} | {o.type}
            spans.append((to_doc(o.meta["src"][1] - n), to_doc(src[0] + n),
                          _style_name("strong_open" in kinds, "em_open" in kinds)))
        elif c.type == "code_inline" and src is not None:
            spans.append((to_doc(src[0]), to_doc(src[1]), "code"))
    return sorted(spans, key=lambda x: (x[0], -x[1]))


def inline_spans(text, base=0):
    """Posizioni dei tratti formattati nella riga così com'è scritta, marcatori
    compresi: (inizio, fine, stile). Un tratto annidato produce una voce
    propria, con lo stile combinato: chi colora sovrappone le due e ottiene,
    ad esempio, grassetto-corsivo."""
    tokens = parse_source(text)
    lines = text.split("\n")
    starts, o = [], 0
    for line in lines:
        starts.append(o)
        o += len(line) + 1
    out = []
    for tok in tokens:
        if tok.type == "inline":
            to_doc = inline_mapper(lines, starts, tok)
            if to_doc is not None:
                out += [(base + a, base + z, st) for a, z, st in _emphasis_spans(tok, to_doc)]
    return out


def highlight_spans(text):
    """Cosa colorare nell'editor, per tutto il capitolo: i titoli per intero
    (h1, h2, h3) e i tratti di inline_spans. Viene dal motore comune, come gli
    export: ciò che qui appare in grassetto uscirà in grassetto."""
    tokens = parse_source(text)
    lines = text.split("\n")
    starts, o = [], 0
    for line in lines:
        starts.append(o)
        o += len(line) + 1
    out, heading = [], None
    for tok in tokens:
        if tok.type == "heading_open" and tok.map:
            heading = tok
            for i in range(tok.map[0], min(tok.map[1], len(lines))):
                out.append((starts[i], starts[i] + len(lines[i]), f"h{min(3, int(tok.tag[1]))}"))
        elif tok.type == "heading_close":
            heading = None
        elif tok.type == "inline" and heading is None:
            to_doc = inline_mapper(lines, starts, tok)
            if to_doc is not None:
                out += _emphasis_spans(tok, to_doc)
    return out


def _parse_inline_md(text):
    """Come parse_inline, ma il codice viene reso in tondo: l'impaginatore PDF
    conosce solo tondo, grassetto, corsivo e grassetto-corsivo."""
    return [(t, "regular" if st == "code" else st) for t, st in parse_inline(text)]


def _strip_inline_md(text):
    """Restituisce il solo testo senza i marcatori inline markdown."""
    return "".join(seg for seg, _ in parse_inline(text))


def classify_md_line(raw_line):
    """Riconosce il tipo di una riga di Markdown, presa da sola.

    Restituisce (tipo, corpo, extra):

        ("blank",   "",          None)      riga vuota
        ("image",   didascalia,  nome)      ![didascalia](nome)
        ("heading", testo,       livello)   # ... ###### (lo spazio e' d'obbligo)
        ("bullet",  testo,       None)      - * +
        ("number",  testo,       "3")       3. testo  oppure  3) testo
        ("quote",   testo,       None)      > testo
        ("rule",    riga,        None)      --- *** ___
        ("text",    testo,       None)      tutto il resto

    Il riconoscimento e' quello del motore comune: "#3 note" non e' un
    titolo, come vuole CommonMark. Serve a chi ragiona riga per riga (la
    ricucitura dei paragrafi spezzati); gli export usano book_blocks."""
    s = raw_line.strip()
    if not s:
        return ("blank", "", None)
    tokens = parse_source(s)
    first = tokens[0].type if tokens else ""
    inline = next((t for t in tokens if t.type == "inline"), None)
    body = inline.meta.get("src_content", inline.content) if inline is not None else s
    if first == "heading_open":
        return ("heading", body, int(tokens[0].tag[1]))
    if first == "hr":
        return ("rule", s, None)
    if first == "bullet_list_open":
        return ("bullet", body, None)
    if first == "ordered_list_open":
        item = tokens[1]
        return ("number", body, item.info or str(tokens[0].attrs.get("start", 1)))
    if first == "blockquote_open":
        return ("quote", body, None)
    if first == "paragraph_open" and inline is not None:
        kids = [c for c in inline.children if not (c.type == "text" and not c.content.strip())]
        if len(kids) == 1 and kids[0].type == "image":
            img = kids[0]
            return ("image", img.content,
                    md_parser().normalizeLinkText(str(img.attrs.get("src", ""))))
    return ("text", s, None)


# ---------------------------------------------------------------------------
# I blocchi del libro
# ---------------------------------------------------------------------------
def _lines(runs):
    """Tratti di un paragrafo del motore -> righe. In RuscaWriter ogni a capo
    va a capo anche nel libro (specifiche, sezione 1.2): le righe scritte una
    sotto l'altra non si fondono in un paragrafo solo, come in CommonMark."""
    lines = [[]]
    for text, style in runs:
        if style in (_SOFT, _HARD):
            lines.append([])
        else:
            lines[-1].append((text, style))
    return [_merge(line) for line in lines]


def _is_image_line(line):
    real = [r for r in line if not (r[1] != "image" and not r[0].strip())]
    return len(real) == 1 and real[0][1] == "image"


def _text_runs(line):
    """Una riga di tratti senza immagini: un'immagine dentro il testo diventa
    la sua didascalia."""
    return _merge([(t[0], "regular") if st == "image" else (t, st) for t, st in line])


def _book_paragraph(node, out):
    """Un paragrafo del motore: righe di testo e figure (una riga che è solo
    un'immagine)."""
    inline = node.children[0].children if node.children else []
    lines = []
    for line in _lines(_runs(inline)):
        if _is_image_line(line):
            if lines:
                out.append(("p", lines))
                lines = []
            caption, name = next(r[0] for r in line if r[1] == "image")
            out.append(("image", caption, name))
        else:
            lines.append(_text_runs(line))
    if lines:
        out.append(("p", lines))


def _book_list(node):
    ordered = node.type == "ordered_list"
    start = int(node.attrs.get("start", 1)) if ordered else 1
    items = []
    for item in node.children:
        task = None
        if "task-list-item" in str(item.attrs.get("class", "")):
            first = item.children[0] if item.children else None
            inline = first.children[0].children if first is not None and first.children else []
            box = next((x for x in inline if x.type == "html_inline"), None)
            task = box is not None and "checked" in box.content
        items.append((task, _book_blocks(item.children)))
    return ("list", ordered, start, items)


def _book_blocks(nodes):
    out = []
    for n in nodes:
        t = n.type
        if t == "paragraph":
            _book_paragraph(n, out)
        elif t == "heading":
            inline = n.children[0].children if n.children else []
            runs = [r for line in _lines(_runs(inline)) for r in _text_runs(line)]
            out.append(("heading", int(n.tag[1]), _merge(runs)))
        elif t in ("bullet_list", "ordered_list"):
            out.append(_book_list(n))
        elif t == "blockquote":
            out.append(("quote", _book_blocks(n.children)))
        elif t == "table":
            aligns, header, rows = [], [], []
            for section in n.children:
                for tr in section.children:
                    cells = []
                    for cell in tr.children:
                        inline = cell.children[0].children if cell.children else []
                        cells.append(_text_runs([r for line in _lines(_runs(inline)) for r in line]))
                        if section.type == "thead":
                            style = str(cell.attrs.get("style", ""))
                            aligns.append(style.split(":", 1)[1] if ":" in style else "left")
                    if section.type == "thead":
                        header = cells
                    else:
                        rows.append(cells)
            out.append(("table", aligns, header, rows))
        elif t == "hr":
            out.append(("rule",))
        elif t in ("fence", "code_block"):
            lang = n.info.split()[0] if t == "fence" and n.info.strip() else ""
            body = n.content[:-1] if n.content.endswith("\n") else n.content
            out.append(("code", lang, body))
        elif t.startswith("math_block"):
            out.append(("math", latex_to_text(n.content.strip())))
        elif t == "footnote_block":
            out.append(("rule",))
            for note in n.children:
                sub = _book_blocks(note.children)
                label = f"[{note.meta['id'] + 1}] "
                if sub and sub[0][0] == "p":
                    first = sub[0][1]
                    sub[0] = ("p", [_merge([(label, "regular")] + first[0])] + first[1:])
                else:
                    sub.insert(0, ("p", [[(label, "regular")]]))
                out.extend(sub)
        elif n.children:
            out.extend(_book_blocks(n.children))
    return out


def book_blocks(text):
    """Il Markdown di un capitolo come blocchi del libro, dal motore comune
    (CommonMark con le estensioni delle specifiche, sezione 1.2). Tutti gli
    export e l'anteprima partono da qui, quindi mostrano la stessa cosa.

        ("heading", livello, tratti)
        ("p", righe)                       righe = [tratti, ...]: ogni a capo
                                           del testo va a capo anche nel libro
        ("image", didascalia, nome)        una riga che è solo un'immagine
        ("list", numerato, inizio, voci)   voci = [(attività, blocchi), ...];
                                           attività None, True (fatta), False
        ("quote", blocchi)
        ("table", allineamenti, intestazione, righe)   celle = tratti
        ("rule",)
        ("code", lingua, testo)
        ("math", testo)                    formula su righe proprie, in simboli

    tratti = [(testo, stile)], stile in INLINE_STYLES. Le note a piè di
    pagina del Markdown ([^1]) finiscono in fondo, dopo un filetto."""
    tree = SyntaxTreeNode(md_parser().parse((text or "").replace("\r\n", "\n")))
    return _book_blocks(tree.children)


def list_lines(block, depth=0):
    """Le voci di un elenco come righe da impaginare una sotto l'altra:
    (profondità, segno, tratti, blocco) dove segno è «•», «3.», «☐» o «☑»
    sulla prima riga di ogni voce e "" sulle righe che la continuano; blocco
    è None per le righe di testo, o un blocco non testuale (immagine,
    tabella, codice…) dentro la voce."""
    _kind, ordered, start, items = block
    for k, (task, blocks) in enumerate(items):
        mark = ("☑" if task else "☐") if task is not None else (f"{start + k}." if ordered else "•")
        first = True
        for b in blocks:
            if b[0] == "p":
                for line in b[1]:
                    yield depth, mark if first else "", line, None
                    first = False
            elif b[0] == "list":
                yield from list_lines(b, depth + 1)
            else:
                yield depth, mark if first else "", [], b
                first = False
        if first:
            yield depth, mark, [], None


def plain_runs(runs):
    """Testo semplice di una riga di tratti."""
    return "".join(t for t, _st in runs)


def block_images(blocks):
    """Nomi delle immagini (righe ![didascalia](nome)) nei blocchi, in ordine."""
    for b in blocks:
        if b[0] == "image":
            yield b[2]
        elif b[0] == "quote":
            yield from block_images(b[1])
        elif b[0] == "list":
            for _task, sub in b[3]:
                yield from block_images(sub)


_RE_QUOTE_PREFIX = re.compile(r"^[ \t]*(?:>[ \t]?)+")


def commonmark_paragraphs(text):
    """Il testo di un capitolo scritto per CommonMark: una riga vuota fra le
    righe che in RuscaWriter vanno a capo e per CommonMark sarebbero un
    paragrafo solo (non dopo un a capo forzato, che CommonMark conosce già).
    Serve all'export Markdown: chi apre il file con RuscaMark, o su GitHub,
    vede gli stessi paragrafi del libro. Le righe dentro gli elenchi restano
    come sono: lì una riga vuota cambierebbe l'elenco."""
    lines = text.split("\n")
    insert = {}                            # riga -> riga vuota (con i «>») dopo
    in_list = 0
    for tok in parse_source(text):
        if tok.type in ("bullet_list_open", "ordered_list_open"):
            in_list += 1
        elif tok.type in ("bullet_list_close", "ordered_list_close"):
            in_list -= 1
        elif tok.type == "paragraph_open" and tok.map and not in_list:
            l0, l1 = tok.map
            m = _RE_QUOTE_PREFIX.match(lines[l0])
            prefix = m.group(0).rstrip() if m else ""
            for i in range(l0, min(l1, len(lines)) - 1):
                if lines[i].endswith("  ") or lines[i].rstrip().endswith("\\"):
                    continue
                insert[i] = prefix
    out = []
    for i, line in enumerate(lines):
        if i - 1 in insert and insert[i - 1] and not line.lstrip().startswith(">"):
            line = insert[i - 1] + " " + line.lstrip()      # riga «pigra» di citazione
        out.append(line)
        if i in insert:
            out.append(insert[i])
    return "\n".join(out)


# EN/IT: the two machine-written lines Project Gutenberg wraps every book in.
# They are generated, not written, so matching them exactly is safe: no book
# opens a paragraph with three asterisks and that sentence.
# Le due righe scritte a macchina con cui Project Gutenberg avvolge ogni libro.
# Sono generate, non scritte: riconoscerle alla lettera e' sicuro, nessun libro
# comincia un paragrafo con tre asterischi e quella frase.
_PG_START_RE = re.compile(
    r"^\*\*\*\s*START OF (?:THE|THIS) PROJECT GUTENBERG EBOOK\b.*$", re.I)
_PG_END_RE = re.compile(
    r"^\*\*\*\s*END OF (?:THE|THIS) PROJECT GUTENBERG EBOOK\b.*$", re.I)


def strip_gutenberg_boilerplate(text):
    """Toglie l'intestazione e la licenza che Project Gutenberg aggiunge a ogni
    libro, lasciando solo l'opera.

    In un file tipico sono un'intestazione di una ventina di righe e una
    licenza finale di trecento: circa un decimo delle parole, che altrimenti
    finirebbero nel manoscritto e da li' nel PDF e nell'EPUB.

    Si taglia solo fra i due marcatori, e solo se ci sono entrambi e
    nell'ordine giusto: se il file non e' di Gutenberg, o e' stato modificato,
    il testo torna indietro intatto. Meglio non tagliare che tagliare a
    sproposito.
    """
    lines = (text or "").split("\n")
    start = end = None
    for i, line in enumerate(lines):
        if start is None and _PG_START_RE.match(line.strip()):
            start = i
        elif start is not None and _PG_END_RE.match(line.strip()):
            end = i
            break
    if start is None or end is None or end <= start + 1:
        return text
    return "\n".join(lines[start + 1:end]).strip("\n")


# ---------------------------------------------------------------------------
# EN: RE-JOINING HARD-WRAPPED PARAGRAPHS ON IMPORT.
#     Most literary .txt files — Project Gutenberg's above all — are wrapped by
#     hand at a fixed column, with a blank line between paragraphs. Taken
#     literally, every one of those newlines is a line break, so the text comes
#     out of the PDF unjustified and refuses to reflow on an e-reader.
#     The file is not at fault: that layout is the norm, and the importer has
#     to recognise it.
#
#     The decision is made one paragraph at a time, never on the whole file,
#     because a book can hold both prose and verse. A run of lines that are all
#     nearly as long as the longest was wrapped by a machine and gets rejoined;
#     a run of short, uneven lines is poetry and is left exactly as it is.
#
# IT: RICUCIRE I PARAGRAFI SPEZZATI ALL'IMPORTAZIONE.
#     Quasi tutti i .txt letterari — quelli di Project Gutenberg per primi —
#     hanno le righe spezzate a mano a una colonna fissa e i paragrafi separati
#     da una riga vuota. Presi alla lettera, quei ritorni a capo sono
#     interruzioni di riga: il testo esce dal PDF non giustificato e su un
#     e-reader non si riadatta. Non e' colpa del file: quel formato e' la
#     norma, ed e' l'importatore che deve saperlo leggere.
#
#     La decisione si prende un paragrafo per volta, mai sul file intero,
#     perche' un libro puo' contenere prosa e versi insieme. Un gruppo di righe
#     lunghe quasi quanto la piu' lunga e' stato spezzato a macchina e viene
#     ricucito; un gruppo di righe corte e irregolari e' poesia e resta com'e'.
# ---------------------------------------------------------------------------

# Sotto questa larghezza non si parla di spezzatura automatica: nessuno manda
# a capo a colonna 30. I .txt in circolazione vanno dalle 60 alle 80 colonne.
_WRAP_MIN_WIDTH = 50
# Quanto devono essere uniformi le righe: la piu' corta almeno il 60% della
# piu' lunga. La prosa spezzata a macchina sta ampiamente sopra; i versi no.
_WRAP_MIN_RATIO = 0.6


def _looks_machine_wrapped(lengths):
    """Vero se queste lunghezze di riga sembrano prodotte da una spezzatura
    automatica a colonna fissa, non da scelte di chi scrive."""
    if not lengths:
        return False
    width = max(lengths)
    if width < _WRAP_MIN_WIDTH:
        return False
    return min(lengths) >= width * _WRAP_MIN_RATIO


def wrapped_runs(text):
    """Trova i paragrafi spezzati a colonna fissa, senza modificare niente.

    Restituisce una lista di coppie (prima_riga, ultima_riga), indici a base
    zero ed estremi inclusi: sono esattamente i gruppi di righe che
    unwrap_hard_breaks ricucirebbe.

    Esiste perche' vedere e correggere devono seguire la STESSA regola:
    l'editor evidenzia queste righe e il comando "Ricuci i paragrafi" unisce
    queste righe. Se la regola cambia, cambiano insieme.
    """
    lines = (text or "").split("\n")
    runs = []
    start = None
    explicit = False
    for i, raw in enumerate(lines):
        if classify_md_line(raw)[0] == "text":
            if start is None:
                start, explicit = i, False
            stripped = raw.rstrip("\n")
            if stripped.endswith("  ") or stripped.rstrip().endswith("\\"):
                explicit = True
        else:
            if start is not None:
                runs.append((start, i - 1, explicit))
            start = None
    if start is not None:
        runs.append((start, len(lines) - 1, explicit))

    out = []
    for a, b, has_explicit in runs:
        if b <= a or has_explicit:
            continue
        # si guardano tutte le righe tranne l'ultima: e' l'unica che puo'
        # essere piu' corta senza che questo dica niente sulla spezzatura
        if _looks_machine_wrapped([len(lines[i].rstrip()) for i in range(a, b)]):
            out.append((a, b))
    return out


def unwrap_hard_breaks(text):
    """Ricuce i paragrafi spezzati a colonna fissa, lasciando intatto il resto.

    Non tocca mai: righe vuote, titoli, elenchi, citazioni, immagini (li
    riconosce con classify_md_line), i gruppi di righe corte o irregolari, e i
    paragrafi in cui compare un'interruzione esplicita del Markdown (riga che
    finisce con due spazi o con una barra rovesciata) — li' l'intenzione di chi
    scrive e' dichiarata e va rispettata.

    Quali paragrafi ricucire lo decide wrapped_runs: la stessa funzione che
    l'editor usa per evidenziarli.
    """
    lines = (text or "").split("\n")
    fino_a = dict(wrapped_runs(text))       # prima riga -> ultima riga
    out = []
    i = 0
    while i < len(lines):
        if i in fino_a:
            ultima = fino_a[i]
            out.append(" ".join(ln.strip() for ln in lines[i:ultima + 1]))
            i = ultima + 1
        else:
            out.append(lines[i])
            i += 1
    return "\n".join(out)


_HEADING_SCALE = {1: 1.6, 2: 1.4, 3: 1.25, 4: 1.15, 5: 1.07, 6: 1.0}


def parse_md_line(raw_line, base_size):
    """Interpreta una riga markdown per il PDF. Restituisce
    (segments, dimensione_font, rientro_punti, spazio_extra_sotto, force_style)
    dove segments e' una lista di (testo, stile).

    Il riconoscimento della riga arriva da classify_md_line: qui restano solo
    le scelte tipografiche, che sono l'unica cosa specifica del PDF."""
    kind, body, extra = classify_md_line(raw_line)
    if kind == "blank":
        return ([("", "regular")], base_size, 0.0, 0.0, None)
    if kind == "heading":
        return ([(_strip_inline_md(body), "bold")],
                base_size * _HEADING_SCALE[extra], 0.0, base_size * 0.4, "bold")
    if kind == "bullet":
        segs = [("\u2022 ", "regular")] + _parse_inline_md(body)
        return (segs, base_size, base_size * 1.2, 0.0, None)
    if kind == "number":
        segs = [(f"{extra}. ", "regular")] + _parse_inline_md(body)
        return (segs, base_size, base_size * 1.2, 0.0, None)
    if kind == "quote":
        segs = [(seg, "italic" if st == "regular" else st)
                for seg, st in _parse_inline_md(body)]
        return (segs, base_size, base_size * 1.2, 0.0, None)
    # riga normale (comprese le righe immagine, che l'impaginatore intercetta
    # prima di arrivare qui): si conserva il rientro originale
    return (_parse_inline_md(raw_line), base_size, 0.0, 0.0, None)


def fit_cover_title(parole, max_w, misura, start=13.5, floor=2.0,
                    max_lines=4, step=0.94):
    """Sceglie il corpo del titolo di copertina e la sua andata a capo.

    LE PAROLE NON SI SPEZZANO. Se una parola non ci sta, non la si taglia a
    meta': si rimpicciolisce il corpo finche' entra intera. Spezzare
    "INTRODUZIONE" in "INTRODUZ / IONE" e' un errore tipografico, non un
    ripiego accettabile.

    parole : le parole del titolo, gia' in maiuscolo
    max_w  : larghezza disponibile
    misura : funzione (testo, corpo) -> larghezza, spaziatura fra le lettere
             compresa. Passandola da fuori questa funzione non ha bisogno di
             font ne' di immagini, e si puo' verificare da sola.

    Restituisce (corpo, righe). Solo per un titolo assurdo — una parola sola
    piu' larga della copertina anche al corpo minimo — si arriva a spezzare,
    come ultima difesa perche' nulla esca dai bordi.
    """
    parole = [p for p in parole if p]
    if not parole:
        return (start, [])

    def manda_a_capo(corpo, spezza):
        righe, cur = [], ""
        for parola in parole:
            prova = (cur + " " + parola).strip()
            if misura(prova, corpo) <= max_w:
                cur = prova
                continue
            if cur:
                righe.append(cur)
                cur = ""
            if not spezza or misura(parola, corpo) <= max_w:
                cur = parola
                continue
            pezzo = ""
            for ch in parola:
                if not pezzo or misura(pezzo + ch, corpo) <= max_w:
                    pezzo += ch
                else:
                    righe.append(pezzo)
                    pezzo = ch
            cur = pezzo
        if cur:
            righe.append(cur)
        return righe

    corpo = start
    while True:
        intere = all(misura(p, corpo) <= max_w for p in parole)
        righe = manda_a_capo(corpo, spezza=False)
        if (intere and len(righe) <= max_lines) or corpo <= floor:
            break
        corpo *= step
    if not intere:
        # titolo impossibile: solo qui si spezza, per non debordare
        righe = manda_a_capo(corpo, spezza=True)
    return (corpo, righe)


def _cover_graphics_ops(page_w, page_h):
    """Operatori grafici vettoriali per una copertina sobria e seria.
    Disegna soltanto:
      - una cornice esterna a filetto singolo, sottile, color prugna scuro;
      - due brevi filetti orizzontali centrati, che incorniciano il blocco
        del titolo (uno appena sopra, uno appena sotto).
    Nessun ornamento dorato, nessun emblema. Restituisce una lista di byte
    (comandi del content stream) da anteporre al testo. Solo PDF nativo.
    """
    P = []

    plum_d = b"0.361 0.165 0.333"   # #5C2A55  unico colore, prugna scuro

    def rect_stroke(x, y, w, h, lw, col):
        P.append(col + b" RG")
        P.append(f"{lw:.2f} w".encode("latin-1"))
        P.append(f"{x:.2f} {y:.2f} {w:.2f} {h:.2f} re S".encode("latin-1"))

    def line(x1, y1, x2, y2, lw, col):
        P.append(col + b" RG")
        P.append(f"{lw:.2f} w".encode("latin-1"))
        P.append(f"{x1:.2f} {y1:.2f} m {x2:.2f} {y2:.2f} l S".encode("latin-1"))

    # --- cornice esterna sottile ----------------------------------------
    m_out = 40.0
    rect_stroke(m_out, m_out, page_w - 2 * m_out, page_h - 2 * m_out,
                0.8, plum_d)

    # --- due brevi filetti centrati attorno al titolo -------------------
    cx = page_w / 2.0
    half = page_w * 0.16        # mezza lunghezza del filetto (corto, centrato)
    y_top = page_h * 0.560      # appena sopra il blocco del titolo
    y_bot = page_h * 0.400      # appena sotto (sopra autore/data)
    line(cx - half, y_top, cx + half, y_top, 0.7, plum_d)
    line(cx - half, y_bot, cx + half, y_bot, 0.7, plum_d)

    return P


# --- Immagini / Images ------------------------------------------------------
# EN: Shared helpers for the "common image formats" the app accepts (PNG,
#     JPEG, WebP): format sniffing from magic bytes, pixel size reading
#     without external libraries, and conversion to JPEG for the PDF export
#     (PDF embeds JPEG natively via DCTDecode).
# IT: Helper condivisi per i "formati immagine comuni" accettati (PNG, JPEG,
#     WebP): riconoscimento del formato dai byte iniziali, lettura delle
#     dimensioni in pixel senza librerie esterne, e conversione in JPEG per
#     l'export PDF (il PDF incorpora i JPEG nativamente via DCTDecode).

# EN: canonical format name -> (file extension, MIME type)
# IT: nome canonico del formato -> (estensione file, tipo MIME)
# EN/IT: limits for reading a .rwr project, which may come from anyone.
# Generous for a book (even with many images), small for an attack.
# / limiti per leggere un progetto .rwr, che può venire da chiunque.
# Larghi per un libro (anche con molte immagini), stretti per un attacco.
MAX_PROJECT_MEMBERS = 20_000
MAX_PROJECT_BYTES = 1024 * 1024 * 1024     # 1 GB decompresso / uncompressed

IMAGE_FORMATS = {
    "png":  ("png",  "image/png"),
    "jpeg": ("jpg",  "image/jpeg"),
    "webp": ("webp", "image/webp"),
}


# --- generatore di copertine ------------------------------------------------
# EN: Formats offered by the cover generator, in centimetres. The keys match
#     PDF_PAGE_SIZES so a generated cover can follow the book's page size.
# IT: Formati offerti dal generatore di copertine, in centimetri. Le chiavi
#     coincidono con PDF_PAGE_SIZES cosi' la copertina generata puo' seguire
#     il formato pagina del libro.
COVER_FORMATS = {
    "A5":    {"w_cm": 14.8, "h_cm": 21.0},
    "6x9":   {"w_cm": 15.2, "h_cm": 22.9},
    "17x24": {"w_cm": 17.0, "h_cm": 24.0},
    "A4":    {"w_cm": 21.0, "h_cm": 29.7},
    "5x8":   {"w_cm": 12.7, "h_cm": 20.3},
}
COVER_DEFAULT_FORMAT = "A5"

# EN/IT: palette proposta dal generatore / palette offered by the generator
COVER_COLORS = [
    "#c98274", "#8d9e7e", "#7d8ba3", "#c4a94f", "#a2705f", "#6f6f78",
    "#d9c9a8", "#3f4a3c", "#8e5b6e", "#2e3440", "#e0ded6", "#b3462f",
]
COVER_DEFAULT_COLOR = "#c98274"
COVER_TEXT_COLORS = ["#111111", "#ffffff"]

# EN: preview vs final resolution (dots per inch). The preview stays small so
#     the GUI redraws instantly; the final image is print-quality.
# IT: risoluzione di anteprima e finale (punti per pollice). L'anteprima resta
#     piccola cosi' la GUI si ridisegna all'istante; l'immagine finale e' di
#     qualita' di stampa.
COVER_PREVIEW_DPI = 96
COVER_EXPORT_DPI = 300


def cover_generator_available():
    """EN: True if a cover can be generated. Drawing the text requires Pillow,
    so without it the generator is offered as unavailable (attaching a
    ready-made image keeps working).
    IT: True se e' possibile generare una copertina. Disegnare il testo
    richiede Pillow, quindi senza di esso il generatore risulta non disponibile
    (allegare un'immagine gia' pronta continua a funzionare)."""
    try:
        from PIL import Image, ImageDraw, ImageFont  # noqa: F401
        return True
    except Exception:
        return False


def _hex_to_rgb(value, fallback=(201, 130, 116)):
    """EN/IT: '#rrggbb' (o '#rgb') -> (r, g, b); fallback se non valido."""
    s = (value or "").strip().lstrip("#")
    if len(s) == 3:
        s = "".join(c * 2 for c in s)
    if len(s) != 6:
        return fallback
    try:
        return (int(s[0:2], 16), int(s[2:4], 16), int(s[4:6], 16))
    except Exception:
        return fallback


def render_cover_image(fmt_key=COVER_DEFAULT_FORMAT, dpi=COVER_EXPORT_DPI,
                       bg_color=COVER_DEFAULT_COLOR, text_color="#111111",
                       author="", title="", publisher="",
                       image_bytes=None, out_format="png", font_dir=None):
    """EN: Draw a book cover and return the image bytes (PNG by default).

    The layout follows a classic typographic scheme: a coloured ground, a
    double rule frame, the author in tracked capitals at the top, a picture
    box in the middle (cropped like CSS 'object-fit: cover'), the title in
    large capitals and the publisher at the foot under a short ornamental
    rule. Every measure is proportional to the cover width, so the result is
    identical at preview resolution and at print resolution.

    font_dir : folder holding the bundled EB Garamond .ttf files (the caller
    passes assets/, so this module keeps needing no path logic of its own).

    Returns None if Pillow is missing (see cover_generator_available()).

    IT: Disegna una copertina e restituisce i byte dell'immagine (PNG per
    impostazione predefinita).

    L'impaginazione segue uno schema tipografico classico: fondo colorato,
    cornice a doppio filetto, autore in maiuscoletto spaziato in alto,
    riquadro per l'immagine al centro (ritagliata come 'object-fit: cover'
    del CSS), titolo in maiuscole grandi ed editore in basso sotto un breve
    filetto ornamentale. Ogni misura e' proporzionale alla larghezza, cosi' il
    risultato e' identico in anteprima e in stampa.

    Restituisce None se Pillow non c'e' (vedi cover_generator_available())."""
    try:
        from PIL import Image, ImageDraw, ImageFont
    except Exception:
        return None

    spec = COVER_FORMATS.get(fmt_key) or COVER_FORMATS[COVER_DEFAULT_FORMAT]
    W = max(1, int(round(spec["w_cm"] / 2.54 * dpi)))
    H = max(1, int(round(spec["h_cm"] / 2.54 * dpi)))

    bg_rgb = _hex_to_rgb(bg_color)
    txt_rgb = _hex_to_rgb(text_color, (17, 17, 17))
    # filetti dello stesso colore del testo (bianchi su fondo scuro)
    rule_rgb = (255, 255, 255) if sum(txt_rgb) > 380 else (0, 0, 0)

    img = Image.new("RGB", (W, H), bg_rgb)
    d = ImageDraw.Draw(img)

    # unita' proporzionale: 1% della larghezza (il "cqw" dei CSS container)
    cqw = W / 100.0

    def _font(filename, size_px):
        """Carica un font del progetto; ripiega sul font di sistema."""
        try:
            path = os.path.join(font_dir, filename) if font_dir else filename
            return ImageFont.truetype(path, max(1, int(round(size_px))))
        except Exception:
            try:
                return ImageFont.load_default(max(1, int(round(size_px))))
            except Exception:
                return ImageFont.load_default()

    def _tracked(text_s, y, fnt, tracking, cx, fill):
        """Testo centrato con spaziatura tra le lettere (letter-spacing)."""
        if not text_s:
            return
        widths = [d.textlength(ch, font=fnt) for ch in text_s]
        total = sum(widths) + tracking * max(0, len(text_s) - 1)
        x = cx - total / 2.0
        for ch, w in zip(text_s, widths):
            d.text((x, y), ch, font=fnt, fill=fill)
            x += w + tracking

    # --- cornice a doppio filetto ---
    pad = 0.042 * W
    thick = max(1, int(round(0.42 * cqw)))
    thin = max(1, int(round(0.16 * cqw)))
    gap = 1.5 * cqw
    fx0, fy0, fx1, fy1 = pad, pad, W - pad, H - pad
    d.rectangle([fx0, fy0, fx1, fy1], outline=rule_rgb, width=thick)
    d.rectangle([fx0 + gap, fy0 + gap, fx1 - gap, fy1 - gap],
                outline=rule_rgb, width=thin)

    # --- area di testo interna ---
    inner_w = fx1 - fx0
    ix0 = fx0 + 0.065 * inner_w
    ix1 = fx1 - 0.065 * inner_w
    iy0 = fy0 + 0.060 * inner_w
    iy1 = fy1 - 0.055 * inner_w
    cx = (ix0 + ix1) / 2.0
    inner_h = iy1 - iy0

    # --- autore, in alto ---
    a_size = 4.0 * cqw
    fa = _font("EBGaramond-Regular.ttf", a_size)
    _tracked((author or "").upper(), iy0, fa, 0.18 * a_size, cx, txt_rgb)
    a_asc, a_desc = fa.getmetrics()
    author_bottom = iy0 + (a_asc + a_desc) * 1.2

    # --- editore, in basso, con filetto ornamentale ---
    e_size = 3.0 * cqw
    fe = _font("EBGaramond-Regular.ttf", e_size)
    e_asc, e_desc = fe.getmetrics()
    e_y = iy1 - (e_asc + e_desc) * 1.2
    _tracked((publisher or "").upper(), e_y, fe, 0.22 * e_size, cx, txt_rgb)
    rule_y = e_y - 0.035 * inner_h
    rule_half = 0.07 * (ix1 - ix0)
    if publisher:
        d.line([cx - rule_half, rule_y, cx + rule_half, rule_y],
               fill=rule_rgb, width=thin)

    # --- titolo: il corpo si MISURA, non si indovina --------------------------
    # Prima il corpo si sceglieva contando i caratteri: una parola sola e lunga
    # usciva dai bordi. La decisione sta ora in fit_cover_title, che scende di
    # corpo finche' ogni parola ci sta INTERA — le parole non si spezzano.
    t_text = (title or "").upper()
    max_w = ix1 - ix0

    def _misura(testo, corpo):
        """Larghezza reale del testo come lo disegna _tracked: la spaziatura
        fra le lettere va contata, o la misura mente."""
        if not testo:
            return 0.0
        fnt = _font("EBGaramond-Bold.ttf", corpo * cqw)
        tracking = 0.03 * corpo * cqw
        return (sum(d.textlength(ch, font=fnt) for ch in testo)
                + tracking * max(0, len(testo) - 1))

    corpo, lines = fit_cover_title(t_text.split(), max_w, _misura)
    t_size = corpo * cqw
    ft = _font("EBGaramond-Bold.ttf", t_size)

    line_h = t_size * 1.02
    title_top = rule_y - 0.025 * inner_h - line_h * len(lines)
    for i, ln in enumerate(lines):
        _tracked(ln, title_top + i * line_h, ft, 0.03 * t_size, cx, txt_rgb)

    # --- riquadro dell'immagine, tra autore e titolo ---
    box_top = int(round(author_bottom + 0.045 * inner_h))
    box_bottom = int(round(title_top - 0.045 * inner_h))
    bx0, bx1 = int(round(ix0)), int(round(ix1))
    if box_bottom > box_top and bx1 > bx0:
        bw, bh = bx1 - bx0, box_bottom - box_top
        placed = False
        if image_bytes:
            try:
                src = Image.open(io.BytesIO(image_bytes))
                if src.mode != "RGB":
                    src = src.convert("RGB")
                # ritaglio "cover": riempie il riquadro senza deformare
                src_ratio = src.width / max(1, src.height)
                box_ratio = bw / max(1, bh)
                if src_ratio > box_ratio:
                    nw = int(src.height * box_ratio)
                    left = max(0, (src.width - nw) // 2)
                    src = src.crop((left, 0, left + nw, src.height))
                else:
                    nh = int(src.width / max(0.0001, box_ratio))
                    top = max(0, (src.height - nh) // 2)
                    src = src.crop((0, top, src.width, top + nh))
                src = src.resize((bw, bh), Image.LANCZOS)
                img.paste(src, (bx0, box_top))
                placed = True
            except Exception:
                placed = False
        if not placed:
            # velo chiaro come segnaposto (CSS rgba(255,255,255,.22))
            base = img.crop((bx0, box_top, bx1, box_bottom))
            veil = Image.new("RGB", (bw, bh), (255, 255, 255))
            img.paste(Image.blend(base, veil, 0.22), (bx0, box_top))

    out = io.BytesIO()
    fmt = (out_format or "png").lower()
    if fmt in ("jpg", "jpeg"):
        img.save(out, format="JPEG", quality=95)
    elif fmt == "webp":
        img.save(out, format="WEBP", quality=95)
    else:
        img.save(out, format="PNG")
    return out.getvalue()


def image_format(data):
    """EN: Detect the image format from the magic bytes at the start of the
    file. Returns 'png', 'jpeg', 'webp' or None if unsupported. Sniffing the
    content (instead of trusting the file extension) makes attach robust.
    IT: Riconosce il formato dai byte iniziali del file. Restituisce 'png',
    'jpeg', 'webp' o None se non supportato. Annusare il contenuto (invece di
    fidarsi dell'estensione) rende l'allegato robusto."""
    if not data or len(data) < 12:
        return None
    if data[:8] == b"\x89PNG\r\n\x1a\n":
        return "png"
    if data[:3] == b"\xff\xd8\xff":
        return "jpeg"
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "webp"
    return None


def _png_dimensions(data):
    """EN: Read (width, height) from the PNG IHDR chunk (always first, big
    endian, at fixed offsets 16 and 20).
    IT: Legge (larghezza, altezza) dal chunk IHDR del PNG (sempre il primo,
    big endian, agli offset fissi 16 e 20)."""
    try:
        w, h = struct.unpack(">II", data[16:24])
        return (w, h) if w and h else None
    except Exception:
        return None


def _webp_dimensions(data):
    """EN: Read (width, height) from a WebP file. WebP is a RIFF container;
    the size lives in the first chunk, whose layout depends on the variant:
    VP8 (lossy), VP8L (lossless) or VP8X (extended).
    IT: Legge (larghezza, altezza) da un WebP. Il WebP e' un contenitore
    RIFF; la dimensione sta nel primo chunk, il cui formato dipende dalla
    variante: VP8 (lossy), VP8L (lossless) o VP8X (esteso)."""
    try:
        tag = data[12:16]
        if tag == b"VP8X":
            # EN: 24-bit little-endian fields store size minus one.
            # IT: campi a 24 bit little-endian con dimensione meno uno.
            w = int.from_bytes(data[24:27], "little") + 1
            h = int.from_bytes(data[27:30], "little") + 1
            return (w, h)
        if tag == b"VP8L":
            bits = int.from_bytes(data[21:25], "little")
            w = (bits & 0x3FFF) + 1
            h = ((bits >> 14) & 0x3FFF) + 1
            return (w, h)
        if tag == b"VP8 ":
            # EN: lossy frame header: size at offset 26, 14 bits each.
            # IT: header del frame lossy: dimensioni all'offset 26, 14 bit.
            w = int.from_bytes(data[26:28], "little") & 0x3FFF
            h = int.from_bytes(data[28:30], "little") & 0x3FFF
            return (w, h) if w and h else None
        return None
    except Exception:
        return None


def image_dimensions(data, fmt=None):
    """EN: (width, height) in pixels for PNG/JPEG/WebP data, or None. Used to
    scale images in the exports without requiring Pillow.
    IT: (larghezza, altezza) in pixel per dati PNG/JPEG/WebP, o None. Usata
    per scalare le immagini negli export senza richiedere Pillow."""
    fmt = fmt or image_format(data)
    if fmt == "png":
        return _png_dimensions(data)
    if fmt == "jpeg":
        return _jpeg_dimensions(data)
    if fmt == "webp":
        return _webp_dimensions(data)
    return None


def _jpeg_dimensions(data):
    """Estrae (larghezza, altezza) da un JPEG leggendo i marker SOF (stdlib)."""
    try:
        i = 2; n = len(data)
        while i + 9 < n:
            if data[i] != 0xFF:
                i += 1; continue
            marker = data[i + 1]
            if marker in (0xC0,0xC1,0xC2,0xC3,0xC5,0xC6,0xC7,0xC9,0xCA,0xCB,0xCD,0xCE,0xCF):
                h = (data[i+5] << 8) | data[i+6]
                w = (data[i+7] << 8) | data[i+8]
                return (w, h)
            seg_len = (data[i+2] << 8) | data[i+3]
            i += 2 + seg_len
        return None
    except Exception:
        return None


def _image_to_jpeg(data, fmt=None):
    """EN: Prepare an image (cover or chapter attachment) for embedding in
    the PDF. PDF embeds JPEG natively (DCTDecode) but not PNG/WebP. With
    Pillow any image is converted to RGB JPEG; without Pillow a JPEG passes
    through untouched; anything else returns None (the caller falls back).
    Returns (jpeg_bytes, width, height) or None.
    IT: Prepara un'immagine (copertina o allegato di capitolo) per
    l'incorporamento nel PDF. Il PDF incorpora i JPEG nativamente
    (DCTDecode) ma non PNG/WebP. Con Pillow ogni immagine viene convertita
    in JPEG RGB; senza Pillow un JPEG passa cosi' com'e'; altrimenti None
    (il chiamante ripiega). Ritorna (jpeg_bytes, width, height) o None."""
    if not data:
        return None
    fmt = fmt or image_format(data)
    try:
        from PIL import Image
        import io as _io
        img = Image.open(_io.BytesIO(data))
        if img.mode != "RGB":
            img = img.convert("RGB")
        w, h = img.size
        buf = _io.BytesIO(); img.save(buf, format="JPEG", quality=90)
        return buf.getvalue(), w, h
    except Exception:
        pass
    if fmt == "jpeg":
        dims = _jpeg_dimensions(data)
        if dims:
            return data, dims[0], dims[1]
    return None


# EN: A chapter line that is ONLY a Markdown image, e.g. ![caption](img_001.png)
# IT: Riga di capitolo che e' SOLO un'immagine Markdown, es. ![didascalia](img_001.png)
_IMG_LINE_RE = re.compile(r"^!\[(?P<alt>.*?)\]\((?P<src>[^)\s]+)\)\s*$")


def write_pdf(path, chapters, title="",
              cover_paragraphs=None, cover_roles=None,
              chapter_titles=None, toc_label="Indice",
              font_size=12, leading=16,
              page_w=595.0, page_h=842.0,   # A4 in punti
              margin=72.0,                  # ~2.54 cm (margine uniforme di base)
              margin_inner=None,            # margine interno (lato rilegatura)
              margin_outer=None,            # margine esterno (lato taglio)
              margin_top=None,              # margine superiore ('margin' se None)
              margin_bottom=None,           # margine inferiore ('margin' se None)
              gutter=0.0,                   # rilegatura aggiunta al lato interno
              mirror=True,                  # pagine speculari (recto/verso)
              page_break_per_chapter=True,
              embed_fonts=None, embed_font_name="CourierPrime",
              cover_image=None,
              chapter_images=None,
              frontispiece_paragraphs=None,
              colophon_paragraphs=None,
              blank_cover=False,
              justify=False,
              hyphenate=False,
              hyphen_lang="it"):
    """
    EN: Write a PDF using only the standard library, with basic Markdown.
      chapters : list of chapters; each chapter = list of paragraphs (str).
      cover_paragraphs : opening cover page (unnumbered).
      embed_fonts : dict {style: metrics} for regular/bold/italic/bolditalic
                    (from read_ttf_metrics). When present, the text uses the
                    embedded font and renders bold/italic.
      chapter_images : dict {internal_name: (jpeg_bytes, width, height)} of
                    the attached chapter images, already converted to JPEG;
                    a text line like ![caption](name) places the image.
      justify   : when True, body paragraphs are justified to the text width
                    (extra space is spread evenly between words); the LAST
                    line of each paragraph, headings and centered material stay
                    flush-left / centered as before.
      hyphenate : when True AND Pyphen is available, over-long words are broken
                    with a hyphen at a valid syllable point so justification
                    looks tidier and fewer words are stretched. Silently
                    ignored if Pyphen is missing.
      hyphen_lang : language code for the hyphenation dictionary (e.g. "it",
                    "en_US"); ignored when hyphenate is False.
    IT: Scrive un PDF usando solo la libreria standard, con markdown di base.
      chapters : lista di capitoli; ogni capitolo = lista di paragrafi (str).
      cover_paragraphs : pagina copertina iniziale (senza numero).
      embed_fonts : dict {stile: metrics} per stile in regular/bold/italic/
                    bolditalic (da read_ttf_metrics). Se presente, il testo usa
                    il font incorporato e rende grassetto/corsivo.
      chapter_images : dict {nome_interno: (jpeg_bytes, larg, alt)} delle
                    immagini allegate ai capitoli, gia' convertite in JPEG;
                    una riga di testo ![didascalia](nome) colloca l'immagine.
    """
    embed_fonts = embed_fonts or {}
    chapter_images = chapter_images or {}
    reg = embed_fonts.get("regular")
    # advance per glifo (monospace -> uguale per tutti gli stili)
    adv = reg["advance1000"] if reg else None
    # mappa larghezze per carattere (font proporzionali, es. EB Garamond):
    # se presente, l'impaginazione usa la larghezza reale di ogni glifo.
    widths_map = (reg.get("uni_widths") or reg.get("widths_by_code")) if reg else None
    # EN/IT: fallback fonts for characters the book font lacks (see
    #        pdf_fallback_fonts) / font di riserva per i caratteri che il
    #        font del libro non ha
    fb_use, fb_fonts, fb_drop = {}, [], set()
    if reg and reg.get("uni2gid"):
        # i segni degli elenchi non sono nel sorgente (lì c'è «- [x]»)
        texts = [title or "", "•☐☑"] + [t for t in (chapter_titles or []) if isinstance(t, str)]
        for ch_paras in chapters:
            for para in ch_paras:
                if isinstance(para, str):
                    texts.append(para)
        fb_use, fb_fonts, fb_drop = pdf_fallback_fonts(reg, texts)
        if fb_use or fb_drop:
            widths_map = dict(widths_map)
            for ch in fb_drop:
                widths_map[ord(ch)] = 0
            for ch, i in fb_use.items():
                m = fb_fonts[i]
                widths_map[ord(ch)] = m["uni_widths"].get(ord(ch), m.get("advance1000", 1000))
    # mappa stile -> chiave font PDF (/F1=regular, /F2=bold, ...)
    style_to_fid = {"regular": "F1", "bold": "F2",
                    "italic": "F3", "bolditalic": "F4"}

    def seg_w(s, size):
        return _text_width(s, size, adv, widths_map)

    # --- sillabazione (opzionale) ------------------------------------------
    # EN: the hyphenator is created only if requested AND Pyphen is present;
    #     otherwise it stays None and no word is ever broken with a hyphen.
    # IT: il sillabatore si crea solo se richiesto E Pyphen c'e'; altrimenti
    #     resta None e nessuna parola viene mai spezzata con un trattino.
    hyphenator = get_hyphenator(hyphen_lang) if hyphenate else None

    def _hyphenate_token(tok, style, size, first_max, next_max):
        """EN: Try to split an over-long word so its first piece fits in
        'first_max' points; the remainder is returned to be re-wrapped. Returns
        a list of (text, style) pieces where every piece but the last ends in a
        soft hyphen "-". If no valid split fits, returns [(tok, style)] intact.
        IT: Prova a spezzare una parola troppo lunga cosi' che il primo pezzo
        entri in 'first_max' punti; il resto viene restituito per essere
        re-impaginato. Restituisce una lista di pezzi (testo, stile) dove ogni
        pezzo tranne l'ultimo finisce con un trattino "-". Se nessuna divisione
        valida entra, restituisce [(tok, style)] intatto."""
        if hyphenator is None or len(tok) < 5:
            return [(tok, style)]
        # Pyphen.positions() da' gli indici di sillaba validi (crescenti).
        try:
            positions = hyphenator.positions(tok)
        except Exception:
            positions = []
        if not positions:
            return [(tok, style)]
        pieces = []
        rest = tok
        offset = 0
        avail = first_max
        while True:
            # posizioni valide relative a 'rest'
            rel = [p - offset for p in positions if 0 < p - offset < len(rest)]
            chosen = None
            for cut in reversed(rel):        # dal taglio piu' lungo che entra
                head = rest[:cut] + "-"
                if seg_w(head, size) <= avail:
                    chosen = cut
                    break
            if chosen is None:
                pieces.append((rest, style))
                break
            pieces.append((rest[:chosen] + "-", style))
            rest = rest[chosen:]
            offset += chosen
            avail = next_max
            if seg_w(rest, size) <= avail:
                pieces.append((rest, style))
                break
        return pieces

    # --- margini: interno (rilegatura) ed esterno (taglio) -----------------
    # Se non specificati, ripiegano sul margine uniforme 'margin', cosi' il
    # comportamento storico resta invariato. Quando differiscono, le pagine
    # dispari (recto) hanno il margine interno a SINISTRA e quelle pari (verso)
    # a DESTRA: il testo viene impaginato con un margine sinistro di base pari
    # al margine ESTERNO, e all'emissione viene traslato a destra della
    # differenza interno - esterno ('shift_inner') sulle pagine recto. Cosi'
    # i calcoli X esistenti restano validi e basta spostare in blocco
    # l'intera pagina.
    # EN: 'gutter' (the binding allowance) is added to the inner margin.
    #     With mirror=False the inner margin is simply the LEFT one on every
    #     page, as in a word processor without facing pages.
    # IT: la 'rilegatura' si aggiunge al margine interno. Con mirror=False il
    #     margine interno e' semplicemente quello SINISTRO su ogni pagina, come
    #     in un elaboratore di testi senza pagine affiancate.
    m_inner = (margin if margin_inner is None else margin_inner) + (gutter or 0.0)
    m_outer = margin if margin_outer is None else margin_outer
    m_top = margin if margin_top is None else margin_top
    m_bottom = margin if margin_bottom is None else margin_bottom
    shift_inner = m_inner - m_outer     # spostamento del blocco verso l'esterno
    left_margin = m_outer               # margine sinistro di impaginazione (base)

    usable_w = page_w - (m_inner + m_outer)
    top_y = page_h - m_top
    bottom_y = m_bottom
    header_gap = leading * 1.6
    content_top_y = top_y - header_gap

    # ogni riga di pagina: (x, y, runs, size) dove runs = [(testo, stile), ...]
    pages = []
    cur_lines = []
    y = content_top_y

    def flush_page(kind=None):
        # kind: "cover" (grafica copertina), "plain" (senza numero),
        #       "toc" (indice: senza numero, ma con la gabbia del testo),
        #       None (pagina di contenuto, numerata)
        nonlocal cur_lines, y
        pages.append((cur_lines, kind))
        cur_lines = []
        y = content_top_y

    def wrap_segments(segments, size, maxw):
        """Manda a capo una sequenza di run (testo,stile) entro maxw.
        Restituisce una lista di righe, ciascuna lista di run.

        Se il sillabatore e' attivo, una parola che non entra nello spazio
        rimasto sulla riga corrente viene spezzata con un trattino nel punto
        di sillaba piu' conveniente, invece di essere mandata tutta a capo:
        cosi' le righe si riempiono meglio e la giustificazione risulta piu'
        uniforme (meno spazi dilatati)."""
        lines = []
        cur = []
        cur_w = 0.0
        for seg_text, style in segments:
            # spezza il run in parole conservando gli spazi
            tokens = re.split(r"(\s+)", seg_text)
            for tok in tokens:
                if tok == "":
                    continue
                w = seg_w(tok, size)
                if cur_w + w > maxw and cur:
                    if tok.strip() == "":
                        # lo spazio finisce la riga: a capo, senza riportarlo
                        lines.append(cur)
                        cur = []
                        cur_w = 0.0
                        continue
                    # la parola non entra nello spazio rimasto: prova a
                    # sillabarla in modo che un pezzo stia su questa riga.
                    if hyphenator is not None:
                        pieces = _hyphenate_token(
                            tok, style, size, maxw - cur_w, maxw)
                        if len(pieces) > 1:
                            head = pieces[0]
                            cur.append(head)
                            lines.append(cur)
                            cur = []
                            cur_w = 0.0
                            # i pezzi restanti (l'ultimo senza trattino) vanno
                            # sulle righe successive, ricontrollando la
                            # larghezza uno per uno
                            for pc_text, pc_style in pieces[1:]:
                                pw = seg_w(pc_text, size)
                                if cur_w + pw > maxw and cur:
                                    lines.append(cur)
                                    cur = []
                                    cur_w = 0.0
                                cur.append((pc_text, pc_style))
                                cur_w += pw
                            continue
                    # niente sillabazione: mando la parola intera a capo
                    lines.append(cur)
                    cur = []
                    cur_w = 0.0
                cur.append((tok, style))
                cur_w += w
        if cur:
            lines.append(cur)
        return lines or [[("", "regular")]]

    def _wrap_centered(text, size):
        """Spezza 'text' in righe centrabili che stanno in usable_w."""
        words = text.split()
        if not words:
            return [""]
        rows, cur = [], words[0]
        for w in words[1:]:
            if seg_w(cur + " " + w, size) <= usable_w:
                cur += " " + w
            else:
                rows.append(cur); cur = w
        rows.append(cur)
        return rows

    def _emit_centered(rows, size, style, yy, line_lead):
        for row in rows:
            lw = seg_w(row, size)
            cur_lines.append(((page_w - lw) / 2.0, yy, [(row, style)], size))
            yy -= line_lead
        return yy

    def add_front_page(styled_lines):
        """Frontespizio professionale: titolo grande nella parte alta-centrale,
        sottotitolo sotto, autore piu' in basso, e in fondo alla pagina i dati
        editoriali (editore, luogo/anno). styled_lines: lista (testo, ruolo)."""
        if not styled_lines:
            return
        title_sz = font_size * 2.1
        sub_sz = font_size * 1.25
        author_sz = font_size * 1.15
        meta_sz = font_size * 0.95
        # blocco principale (titolo/sottotitolo/autore) centrato verticalmente
        # nella meta' superiore; i meta vanno in fondo pagina.
        top = [(t, r) for (t, r) in styled_lines if r != "meta"]
        meta = [(t, r) for (t, r) in styled_lines if r == "meta"]

        # calcola altezza del blocco principale
        def size_of(role):
            return {"title": title_sz, "subtitle": sub_sz,
                    "author": author_sz}.get(role, font_size)
        block_h = 0
        for t, r in top:
            rows = _wrap_centered(t, size_of(r))
            lead = size_of(r) * 1.4
            block_h += lead * len(rows)
            if r == "title":
                block_h += font_size * 0.6   # spazio dopo il titolo
            if r == "author":
                block_h += font_size * 0.8   # spazio prima dell'autore
        # parti un po' sopra il centro, per un'aria piu' "da libro"
        yy = page_h * 0.66 + block_h / 2.0
        for t, r in top:
            sz = size_of(r)
            if r == "author":
                yy -= font_size * 0.8
            style = "bold" if r == "title" else ("italic" if r == "subtitle" else "regular")
            rows = _wrap_centered(t, sz)
            yy = _emit_centered(rows, sz, style, yy, sz * 1.4)
            if r == "title":
                yy -= font_size * 0.6
        # meta in fondo pagina
        if meta:
            my = m_bottom + meta_sz * 1.6 * len(meta)
            for t, r in meta:
                rows = _wrap_centered(t, meta_sz)
                my = _emit_centered(rows, meta_sz, "regular", my, meta_sz * 1.4)
        flush_page("plain")

    def add_colophon_page(styled_lines):
        """Colophon professionale: blocco compatto e piccolo, centrato, nella
        parte bassa della pagina. styled_lines: lista (testo, ruolo)."""
        if not styled_lines:
            return
        copy_sz = font_size * 1.0
        small_sz = font_size * 0.85
        line_lead = small_sz * 1.5
        # altezza totale per posizionare il blocco nella meta' inferiore
        total = 0
        for t, r in styled_lines:
            sz = copy_sz if r == "copyright" else small_sz
            total += line_lead * len(_wrap_centered(t, sz))
        yy = page_h * 0.40 + total / 2.0
        for t, r in styled_lines:
            sz = copy_sz if r == "copyright" else small_sz
            rows = _wrap_centered(t, sz)
            yy = _emit_centered(rows, sz, "regular", yy, line_lead)
        flush_page("plain")

    # 0) copertina-immagine a piena pagina (precede ed esclude la grafica)
    if cover_image is not None:
        jpeg_bytes, img_w, img_h = cover_image
        pages.append(([], ("image", jpeg_bytes, img_w, img_h)))

    # 0-bis) copertina BIANCA e VUOTA: nessuna immagine e campi editoriali
    # vuoti. Si emette comunque una pagina (presente nel PDF) ma senza alcuna
    # grafica vettoriale e senza testo: pagina completamente bianca, senza
    # numero. Esclude la copertina stilizzata sottostante.
    blank_cover_now = blank_cover and cover_image is None
    if blank_cover_now:
        flush_page("plain")   # pagina vuota, senza cornice e senza numero

    # 1) pagina copertina stilizzata (grafica + testo) solo senza immagine
    if cover_paragraphs is not None and cover_image is None and not blank_cover_now:
        # raccoglie le righe non vuote della copertina conservando l'ordine.
        # convenzione del progetto: 1a riga = TITOLO, ultima = data,
        # le righe intermedie = autore (ed eventuale sottotitolo).
        raw_lines = []
        for para in cover_paragraphs:
            for raw_line in para.split("\n"):
                clean = _strip_inline_md(raw_line.lstrip("#").strip()
                                         if raw_line.strip().startswith("#")
                                         else raw_line)
                if clean.strip():
                    raw_lines.append(clean.strip())

        title_size  = font_size * 2.1
        author_size = font_size * 1.25
        date_size   = font_size * 0.95
        title_lead  = leading * 2.1
        author_lead = leading * 1.4

        def put_centered(text, size, cy_pos, style):
            lw = seg_w(text, size)
            cx = (page_w - lw) / 2.0
            cur_lines.append((cx, cy_pos, [(text, style)], size))

        def wrap_centered(text, size):
            """Spezza un testo troppo largo in piu' righe centrabili."""
            maxw = usable_w
            words = text.split()
            if not words:
                return [""]
            out, cur = [], words[0]
            for w in words[1:]:
                if seg_w(cur + " " + w, size) <= maxw:
                    cur += " " + w
                else:
                    out.append(cur); cur = w
            out.append(cur)
            return out

        # I ruoli arrivano dal progetto (cover_lines_with_roles): titolo,
        # sottotitolo, autore, editore. Non si deducono dalla posizione, o con
        # due sole righe la stessa finirebbe stampata due volte.
        if cover_roles and len(cover_roles) == len(raw_lines):
            title_line = next((t for t, r in zip(raw_lines, cover_roles)
                               if r == "title"), "")
            middle = [t for t, r in zip(raw_lines, cover_roles)
                      if r in ("subtitle", "author")]
            date_line = next((t for t, r in zip(raw_lines, cover_roles)
                              if r == "publisher"), "")
            raw_lines = [x for x in ([title_line] + middle + [date_line]) if x]
        elif raw_lines:
            # ripiego per chi chiama write_pdf senza ruoli
            title_line = raw_lines[0]
            date_line = raw_lines[-1] if len(raw_lines) > 2 else ""
            middle = raw_lines[1:-1] if len(raw_lines) > 2 else raw_lines[1:]

        if raw_lines:

            # TITOLO: centrato nella fascia tra i due filetti (0.585 e 0.375),
            # quindi attorno a ~0.48 dell'altezza pagina.
            band_mid = page_h * 0.48
            title_rows = wrap_centered(title_line, title_size)
            n_mid = len(middle)
            block_h = len(title_rows) * title_lead + n_mid * author_lead
            ty = band_mid + block_h / 2.0 - title_size * 0.30
            for trow in title_rows:
                put_centered(trow, title_size, ty, "bold")
                ty -= title_lead

            # AUTORE / sottotitolo: appena sotto il titolo
            ay = ty - (title_lead * 0.15)
            for line_txt in middle:
                put_centered(line_txt, author_size, ay, "regular")
                ay -= author_lead

            # DATA: ancorata appena sotto il filetto inferiore (0.400)
            if date_line:
                dy = page_h * 0.400 - date_size * 2.2
                put_centered(date_line, date_size, dy, "italic")

        flush_page("cover")

    # 1a) frontespizio (dopo la copertina, prima dell'indice)
    if frontispiece_paragraphs:
        add_front_page(frontispiece_paragraphs)

    # Per avere nell'indice i NUMERI DI PAGINA reali (non gli ordinali dei
    # capitoli) impaginiamo prima i capitoli in un elenco di pagine separato,
    # registrando la pagina di inizio di ciascun capitolo, e SOLO DOPO
    # costruiamo l'indice. I numeri di pagina visibili partono da 1 e contano
    # solo le pagine di contenuto (le pagine "plain" come copertina, indice e
    # colophon non sono numerate), quindi l'indice non altera la numerazione.
    pages_before_chapters = list(pages)   # cover + frontespizio
    def layout_table(aligns, header, rows):
        """EN: Lay out a Markdown table in book style (booktabs): a thick
        rule above and below, a thin one under the header, no vertical
        lines. The table spans the text width; columns share it in
        proportion to their content and cells wrap. Returns how many pages
        were started.
        IT: Impagina una tabella Markdown in stile libro (booktabs): filetto
        spesso sopra e sotto, sottile sotto l'intestazione, niente linee
        verticali. La tabella occupa la larghezza del testo; le colonne se
        la dividono in proporzione al contenuto e le celle vanno a capo.
        Restituisce quante pagine nuove sono state aperte."""
        nonlocal y
        new_pages = 0
        sz = font_size * 0.9
        lead = leading * 0.9
        pad = sz * 0.5
        ncol = len(header)

        def segs_of(text, head):
            # celle già analizzate (book_blocks) o testo Markdown
            segs = (_parse_inline_md(text) if isinstance(text, str) else
                    [(t, "regular" if st == "code" else st) for t, st in text] or [("", "regular")])
            if head:
                segs = [(t, "bolditalic" if "italic" in st else "bold") for t, st in segs]
            return segs
        table = ([[segs_of(c, True) for c in header]]
                 + [[segs_of(c, False) for c in r] for r in rows])
        nat, least = [0.0] * ncol, [0.0] * ncol
        for r in table:
            for c, segs in enumerate(r):
                nat[c] = max(nat[c], sum(seg_w(t, sz) for t, _ in segs))
                words = [seg_w(w, sz) for t, _ in segs for w in t.split()]
                least[c] = max(least[c], max(words, default=0.0))
        avail = usable_w - 2 * pad * ncol
        if sum(nat) <= avail:
            total = sum(nat) or 1.0
            widths = [n + (avail - sum(nat)) * n / total for n in nat]
        else:
            base = [min(m, avail / ncol) for m in least]
            flex = [max(n - b, 0.0) for n, b in zip(nat, base)]
            total = sum(flex) or 1.0
            widths = [b + (avail - sum(base)) * f / total for b, f in zip(base, flex)]
        col_x, x = [], left_margin
        for w in widths:
            col_x.append(x)
            x += w + 2 * pad
        x1, x2 = left_margin, left_margin + usable_w
        first_on_page = True
        bottom = y
        for ri, r in enumerate(table):
            wrapped = [wrap_segments(segs, sz, widths[c]) for c, segs in enumerate(r)]
            n = max(len(w) for w in wrapped)
            if y - n * lead < bottom_y and cur_lines:
                if not first_on_page:
                    cur_lines.append(("rule", x1, bottom, x2, 0.8))
                flush_page()
                new_pages += 1
                first_on_page = True
            if first_on_page:
                cur_lines.append(("rule", x1, y + lead * 0.8, x2, 0.8))
                first_on_page = False
            for c, lines_c in enumerate(wrapped):
                for k, run_line in enumerate(lines_c):
                    lw = sum(seg_w(t, sz) for t, _ in run_line)
                    shift = {"right": 1.0, "center": 0.5}.get(aligns[c], 0.0)
                    cur_lines.append((col_x[c] + pad + (widths[c] - lw) * shift,
                                      y - k * lead, run_line, sz))
            bottom = y - (n - 1) * lead - lead * 0.45
            if ri == 0:
                cur_lines.append(("rule", x1, bottom, x2, 0.4))
            y = bottom - lead * 0.85
        cur_lines.append(("rule", x1, bottom, x2, 0.8))
        y = bottom - leading
        return new_pages

    pages = []                            # qui finiranno SOLO le pagine capitoli

    chapter_start_page = []   # numero di pagina visibile d'inizio per capitolo
    pages_so_far = 0          # pagine di contenuto gia' completate

    # 2) capitoli di contenuto (markdown)
    for ci, paragraphs in enumerate(chapters):
        if page_break_per_chapter and ci > 0:
            flush_page()
            pages_so_far += 1
        # all'inizio del capitolo, la sua prima pagina e' (pagine_finora + 1)
        chapter_start_page.append(pages_so_far + 1)
        def pdf_runs(runs, force=None):
            """Tratti -> segmenti del PDF: il codice in tondo, perché
            l'impaginatore conosce solo tondo, grassetto, corsivo e
            grassetto-corsivo; force impone uno stile (titoli, citazioni)."""
            segs = []
            for t, st in runs:
                st = "regular" if st == "code" else st
                if force == "italic":
                    st = "italic" if st == "regular" else st
                elif force:
                    st = force
                segs.append((t, st))
            return segs or [("", "regular")]

        def text_line(segments, sz, indent, extra=0.0, force=None, centered=False):
            """Una riga del testo, che va a capo nella gabbia. L'ULTIMA riga
            spezzata non si giustifica mai (apparirebbe dilatata), e nemmeno
            i titoli (force == "bold")."""
            nonlocal y, pages_so_far
            line_leading = leading * (sz / font_size)
            avail = usable_w - indent
            wrapped = wrap_segments(segments, sz, avail)
            can_justify = justify and force != "bold" and not centered
            for li, run_line in enumerate(wrapped):
                if y < bottom_y:
                    flush_page()
                    pages_so_far += 1
                is_last = (li == len(wrapped) - 1)
                jw = avail if (can_justify and not is_last) else None
                x = left_margin + indent
                if centered:
                    x = left_margin + (usable_w - sum(seg_w(t, sz) for t, _s in run_line)) / 2.0
                cur_lines.append((x, y, run_line, sz, jw))
                y -= line_leading
            if extra:
                y -= extra

        def rule_line():
            """Un filetto corto e centrato, come nei libri."""
            nonlocal y, pages_so_far
            if y - leading < bottom_y and cur_lines:
                flush_page()
                pages_so_far += 1
            mid = left_margin + usable_w / 2.0
            cur_lines.append(("rule", mid - usable_w * 0.15, y + leading * 0.3,
                              mid + usable_w * 0.15, 0.5))
            y -= leading

        def image_block(caption, name):
            """Una riga che è solo ![didascalia](nome) colloca l'immagine
            allegata, centrata e scalata alla larghezza del testo (mai
            ingrandita), seguita dalla didascalia in corsivo. Se non entra
            nello spazio rimasto, passa prima a una pagina nuova. Un'immagine
            che non è nel progetto lascia la sola didascalia."""
            nonlocal y, pages_so_far
            if name not in chapter_images:
                text_line(pdf_runs([(caption, "italic")]), font_size, 0.0)
                return
            _jpg, iw, ih = chapter_images[name]
            max_h = (content_top_y - bottom_y) * 0.60
            scale = min(usable_w / iw, max_h / ih, 1.0)
            draw_w, draw_h = iw * scale, ih * scale
            if y - draw_h < bottom_y and cur_lines:
                flush_page()
                pages_so_far += 1
            ix = left_margin + (usable_w - draw_w) / 2.0
            # voce speciale, gestita al momento dell'emissione pagina
            cur_lines.append(("img", name, ix, y - draw_h, draw_w, draw_h))
            y -= draw_h + leading * 0.5
            alt = caption.strip()
            if alt:
                cap_sz = font_size * 0.85
                for row in _wrap_centered(alt, cap_sz):
                    if y < bottom_y:
                        flush_page()
                        pages_so_far += 1
                    lw = seg_w(row, cap_sz)
                    # centrata sulla gabbia, non sulla pagina: il blocco
                    # viene poi spostato per la rilegatura
                    cur_lines.append((left_margin + (usable_w - lw) / 2.0,
                                      y, [(row, "italic")], cap_sz))
                    y -= cap_sz * 1.4
                y -= leading * 0.3

        def blocks_out(blocks, indent=0.0, quote=False):
            nonlocal pages_so_far
            force = "italic" if quote else None
            for b in blocks:
                kind = b[0]
                if kind == "heading":
                    lvl = b[1]
                    sz = font_size * _HEADING_SCALE[lvl]
                    text_line([(plain_runs(b[2]), "bold")], sz, indent, font_size * 0.4, "bold")
                elif kind == "p":
                    for line in b[1]:
                        text_line(pdf_runs(line, force), font_size, indent, force=force)
                elif kind == "list":
                    for depth, mark, line, inner in list_lines(b):
                        ind = indent + font_size * 1.2 * (depth + 1)
                        if inner is not None:
                            blocks_out([inner], ind, quote)
                            continue
                        if reg is None:     # caratteri standard del PDF: solo Latin-1
                            mark = {"☑": "[x]", "☐": "[ ]"}.get(mark, mark)
                        segs = ([(mark + " ", "regular")] if mark else []) + pdf_runs(line, force)
                        text_line(segs, font_size, ind, force=force)
                elif kind == "quote":
                    blocks_out(b[1], indent + font_size * 1.2, True)
                elif kind == "image":
                    image_block(b[1], b[2])
                elif kind == "table":
                    pages_so_far += layout_table(b[1], b[2], b[3])
                elif kind == "rule":
                    rule_line()
                elif kind == "code":
                    for code_line in b[2].split("\n"):
                        text_line([(code_line, "regular")], font_size, indent + font_size * 1.2)
                elif kind == "math":
                    text_line([(b[1], "regular")], font_size, indent, centered=True)

        # Il capitolo arriva come paragrafi separati da righe vuote; il
        # motore lo legge tutto insieme (book_blocks) e dopo ogni blocco
        # resta mezza interlinea, come fra i paragrafi di prima.
        for block in book_blocks("\n\n".join(paragraphs)):
            blocks_out([block])
            y -= leading * 0.5
    flush_page()
    pages_so_far += 1

    chapter_pages = pages        # le pagine dei capitoli appena impaginate
    pages = pages_before_chapters
    # Posizione in cui finira' l'indice stampato, da segnare ORA: 'pages' e
    # 'pages_before_chapters' sono da qui in poi la stessa lista, quindi
    # misurarla dopo aver impaginato l'indice restituirebbe la pagina
    # sbagliata.
    toc_page_index = len(pages)

    # Intestazione di pagina (running header): ogni pagina di capitolo mostra il
    # TITOLO DEL CAPITOLO a cui appartiene, non il titolo del progetto. La pagina
    # di capitolo in posizione j (0-based) ha numero visibile j+1; il suo
    # capitolo e' l'ultimo il cui chapter_start_page <= j+1.
    chapter_page_header = []
    for j in range(len(chapter_pages)):
        vis = j + 1
        title_for_page = title   # ripiego: titolo progetto
        for ci2, start in enumerate(chapter_start_page):
            if start <= vis and ci2 < len(chapter_titles):
                title_for_page = chapter_titles[ci2]
            else:
                break
        chapter_page_header.append(title_for_page)

    # 1b) pagina indice (sommario), senza numero, con i NUMERI DI PAGINA reali
    if chapter_titles:
        # titolo "Indice" centrato in alto
        tl_size = font_size * 1.7
        tw = seg_w(toc_label, tl_size)
        cur_lines.append((left_margin + (usable_w - tw) / 2.0, content_top_y,
                          [(toc_label, "bold")], tl_size))
        yy = content_top_y - leading * 2.4
        for idx_i, ct in enumerate(chapter_titles):
            page_no = (chapter_start_page[idx_i]
                       if idx_i < len(chapter_start_page) else idx_i + 1)
            left = f"{ct}"
            right = str(page_no)
            # titolo a sinistra, numero di pagina a destra, puntini di guida
            lw = seg_w(left, font_size)
            rw = seg_w(right, font_size)
            avail = usable_w - lw - rw - seg_w("  ", font_size)
            dots = ""
            dot_w = seg_w(".", font_size)
            if avail > dot_w and dot_w > 0:
                dots = "." * int(avail / dot_w)
            cur_lines.append((left_margin, yy, [(left + " ", "regular")], font_size))
            if dots:
                cur_lines.append((left_margin + lw + seg_w(" ", font_size), yy,
                                  [(dots, "regular")], font_size))
            # il numero si allinea al bordo destro della GABBIA (prima stava
            # al bordo della pagina meno l'esterno, e sporgeva della
            # rilegatura oltre i puntini)
            cur_lines.append((left_margin + usable_w - rw, yy,
                              [(right, "regular")], font_size))
            yy -= leading * 1.4
            if yy < bottom_y:
                flush_page("toc")
                yy = content_top_y
        flush_page("toc")

    # EN: bookmarks (the PDF outline) need the ABSOLUTE position of each
    #     chapter's first page inside the final page list — not the visible
    #     page number, which skips cover, index and colophon. We record it here,
    #     the one moment when both halves of the list are known.
    # IT: i segnalibri (l'indice di navigazione del PDF) vogliono la posizione
    #     ASSOLUTA della prima pagina di ogni capitolo nell'elenco finale, non
    #     il numero di pagina visibile, che salta copertina, indice e colophon.
    #     La registriamo qui, l'unico momento in cui si conoscono entrambe le
    #     meta' dell'elenco.
    outline_entries = []           # (titolo, indice assoluto di pagina)
    if chapter_titles:
        # la pagina dell'indice stampato e' la prima dopo copertina e
        # frontespizio: ci si mette un segnalibro, e' li' che si torna
        outline_entries.append((toc_label, toc_page_index))
    chapter_pages_offset = len(pages)
    for ci3, ct in enumerate(chapter_titles or []):
        if ci3 < len(chapter_start_page):
            outline_entries.append(
                (ct, chapter_pages_offset + chapter_start_page[ci3] - 1))

    # ora accodiamo le pagine dei capitoli (gia' impaginate sopra)
    pages.extend(chapter_pages)

    # 3) colophon (ultima pagina, senza numero)
    if colophon_paragraphs:
        add_colophon_page(colophon_paragraphs)

    if not pages:
        pages = [([], None)]

    total = len(pages)

    # costruisci gli oggetti PDF (come byte)
    objects = []

    def add_obj(body_bytes):
        objects.append(body_bytes)
        return len(objects)

    # mappa "F1".."F4" -> id oggetto font (per le Resources)
    font_ids = {}

    # EN: fonts with Unicode metrics are written as Type0 / Identity-H: the
    #     text is a sequence of glyph ids, so any character the font has can
    #     appear (formulas, Greek, Cyrillic…). Their /W widths and ToUnicode
    #     map list only the glyphs actually used, so they are filled in after
    #     the pages: here we reserve the object slots.
    # IT: i font con metriche Unicode si scrivono come Type0 / Identity-H: il
    #     testo e' una sequenza di id di glifo, quindi puo' comparire ogni
    #     carattere presente nel font (formule, greco, cirillico…). Larghezze
    #     /W e mappa ToUnicode elencano solo i glifi usati, quindi si
    #     compilano dopo le pagine: qui si prenotano gli oggetti.
    unicode_fonts = {}            # fid -> dati del font Type0

    def make_embedded_font(metrics, psname, italic, fid=None):
        ttf = metrics["data"]
        fontfile_id = add_obj(
            (f"<< /Length {len(ttf)} /Length1 {len(ttf)} >>\nstream\n").encode("latin-1")
            + ttf + b"\nendstream")
        bbox = metrics["bbox"]
        wbc = metrics.get("widths_by_code")
        # Flag del descrittore di font (PDF spec):
        #   1 = FixedPitch (solo monospace), 2 = Serif, 32 = Nonsymbolic, 64 = Italic
        # Per un font proporzionale (con widths_by_code) NON impostiamo FixedPitch,
        # altrimenti i visualizzatori assumono larghezza fissa.
        if wbc is not None:
            flags = 2 + 32 + (64 if italic else 0)      # Serif, Nonsymbolic
        else:
            flags = 1 + 32 + (64 if italic else 0)      # FixedPitch, Nonsymbolic
        ital_angle = -12 if italic else 0
        descriptor_id = add_obj(
            (f"<< /Type /FontDescriptor /FontName /{psname} /Flags {flags} "
             f"/FontBBox [{bbox[0]} {bbox[1]} {bbox[2]} {bbox[3]}] "
             f"/ItalicAngle {ital_angle} /Ascent {metrics['ascent']} "
             f"/Descent {metrics['descent']} /CapHeight {metrics['ascent']} "
             f"/StemV 80 /FontFile2 {fontfile_id} 0 R >>").encode("latin-1"))
        if metrics.get("uni2gid") and fid is not None:
            cid_id = add_obj(None)
            tounicode_id = add_obj(None)
            unicode_fonts[fid] = {"metrics": metrics, "used": {}, "ps": psname,
                                  "cid": cid_id, "tounicode": tounicode_id,
                                  "descriptor": descriptor_id}
            return add_obj(
                (f"<< /Type /Font /Subtype /Type0 /BaseFont /{psname} "
                 f"/Encoding /Identity-H /DescendantFonts [{cid_id} 0 R] "
                 f"/ToUnicode {tounicode_id} 0 R >>").encode("latin-1"))
        # Array /Widths: larghezza reale per ogni carattere se disponibile
        # (font proporzionale), altrimenti larghezza fissa (monospace).
        if wbc is not None:
            default = metrics.get("advance1000", 500)
            widths = " ".join(str(wbc.get(code, default))
                              for code in range(32, 256))
        else:
            widths = " ".join(str(metrics["advance1000"]) for _ in range(32, 256))
        return add_obj(
            (f"<< /Type /Font /Subtype /TrueType /BaseFont /{psname} "
             f"/FirstChar 32 /LastChar 255 /Widths [{widths}] "
             f"/FontDescriptor {descriptor_id} 0 R "
             f"/Encoding /WinAnsiEncoding >>").encode("latin-1"))

    if reg:
        defs = [("F1", "regular", False), ("F2", "bold", False),
                ("F3", "italic", True), ("F4", "bolditalic", True)]
        for fid, style, italic in defs:
            metrics = embed_fonts.get(style) or reg   # ripiego sul regular
            psname = f"{embed_font_name}-{style}"
            font_ids[fid] = make_embedded_font(metrics, psname, italic, fid)
        for i, m in enumerate(fb_fonts):
            font_ids[f"FB{i + 1}"] = make_embedded_font(m, f"Fallback{i + 1}", False,
                                                        f"FB{i + 1}")
    else:
        # font core (fallback senza incorporamento)
        font_ids["F1"] = add_obj(
            b"<< /Type /Font /Subtype /Type1 /BaseFont /Times-Roman "
            b"/Encoding /WinAnsiEncoding >>")
        font_ids["F2"] = add_obj(
            b"<< /Type /Font /Subtype /Type1 /BaseFont /Times-Bold "
            b"/Encoding /WinAnsiEncoding >>")
        font_ids["F3"] = add_obj(
            b"<< /Type /Font /Subtype /Type1 /BaseFont /Times-Italic "
            b"/Encoding /WinAnsiEncoding >>")
        font_ids["F4"] = add_obj(
            b"<< /Type /Font /Subtype /Type1 /BaseFont /Times-BoldItalic "
            b"/Encoding /WinAnsiEncoding >>")

    def encode_run(fid, text, adj):
        """Testo in un solo font Type0: id di glifo a due byte; con adj, uno
        spostamento dopo ogni spazio (giustificazione)."""
        info = unicode_fonts[fid]
        u2g = info["metrics"]["uni2gid"]
        used = info["used"]
        q_gid = u2g.get(ord("?"), 0)
        chunks, cur = [], []
        for ch in text:
            gid = u2g.get(ord(ch))
            if gid is None:
                gid, ch = q_gid, "?"
            used.setdefault(gid, ch)
            cur.append(f"{gid:04X}")
            if adj and ch == " ":
                chunks.append("<" + "".join(cur) + ">")
                chunks.append(f"{adj:.2f}")
                cur = []
        if cur:
            chunks.append("<" + "".join(cur) + ">")
        if adj:
            return "[" + " ".join(chunks) + "] TJ"
        return "".join(chunks) + " Tj"

    def show_text(fid, text, tw=0.0, size=None):
        """Operatori che mostrano 'text' con il font 'fid'. Font Type0: id di
        glifo a due byte. I caratteri che il font non ha passano ai font di
        riserva (cambio di font solo per quei caratteri), quelli invisibili o
        che nessun font disegna vengono omessi. Lo spazio-parola Tw non vale
        per le codifiche a due byte: con la giustificazione ogni spazio
        riceve un aggiustamento esplicito in TJ."""
        if fid not in unicode_fonts:
            return b"(" + _pdf_escape_bytes(_to_winansi(text)) + b") Tj"
        size = size or 10
        adj = -tw * 1000.0 / size if tw else 0.0
        out, run, run_font = [], [], fid
        for ch in text:
            if ch in fb_drop:
                continue
            font = f"FB{fb_use[ch] + 1}" if ch in fb_use else fid
            if font != run_font and run:
                out.append((run_font, "".join(run)))
                run = []
            run_font = font
            run.append(ch)
        if run:
            out.append((run_font, "".join(run)))
        ops = []
        for font, chunk in out:
            if font == fid:
                ops.append(encode_run(fid, chunk, adj))
            else:
                ops.append(f"/{font} {size:.1f} Tf {encode_run(font, chunk, 0.0)} "
                           f"/{fid} {size:.1f} Tf")
        return " ".join(ops).encode("latin-1") if ops else b""

    pages_obj_id = len(objects) + 1
    objects.append(None)

    # risorse font condivise (riferite da ogni pagina)
    font_res = " ".join(f"/{fid} {oid} 0 R" for fid, oid in font_ids.items())

    page_obj_ids = []
    visible_number = 0
    # EN: each distinct attached image becomes ONE shared PDF XObject, reused
    #     by every page that shows it: name -> object id.
    # IT: ogni immagine allegata distinta diventa UN solo XObject PDF,
    #     riutilizzato da ogni pagina che la mostra: nome -> id oggetto.
    image_obj_ids = {}
    for i, (lines, kind) in enumerate(pages):
        parts = []
        # pagina copertina-immagine: kind = ("image", jpeg_bytes, w, h)
        if isinstance(kind, tuple) and kind and kind[0] == "image":
            _, jpeg_bytes, img_w, img_h = kind
            img_stream = (f"<< /Type /XObject /Subtype /Image /Width {img_w} "
                          f"/Height {img_h} /ColorSpace /DeviceRGB "
                          f"/BitsPerComponent 8 /Filter /DCTDecode "
                          f"/Length {len(jpeg_bytes)} >>\nstream\n").encode("latin-1") \
                         + jpeg_bytes + b"\nendstream"
            img_id = add_obj(img_stream)
            scale = min(page_w / img_w, page_h / img_h)
            draw_w = img_w * scale; draw_h = img_h * scale
            off_x = (page_w - draw_w) / 2.0; off_y = (page_h - draw_h) / 2.0
            parts.append(b"q")
            parts.append(f"{draw_w:.2f} 0 0 {draw_h:.2f} {off_x:.2f} {off_y:.2f} cm".encode("latin-1"))
            parts.append(b"/Im0 Do")
            parts.append(b"Q")
            stream = b"\n".join(parts)
            body = (f"<< /Length {len(stream)} >>\nstream\n".encode("latin-1")
                    + stream + b"\nendstream")
            cid = add_obj(body)
            pid = add_obj(
                (f"<< /Type /Page /Parent {pages_obj_id} 0 R "
                 f"/MediaBox [0 0 {page_w:.0f} {page_h:.0f}] "
                 f"/Resources << /Font << {font_res} >> "
                 f"/XObject << /Im0 {img_id} 0 R >> >> "
                 f"/Contents {cid} 0 R >>").encode("latin-1"))
            page_obj_ids.append(pid)
            continue
        if kind == "cover":
            # grafica vettoriale della copertina prima del testo
            parts.extend(_cover_graphics_ops(page_w, page_h))
        # spostamento orizzontale per la rilegatura: sulle pagine di contenuto
        # numerate, il recto (pagina fisica dispari) ha il margine interno a
        # sinistra, quindi il blocco di testo si sposta a destra della
        # differenza fra interno ed esterno; il verso (pagina pari) resta al
        # margine esterno. Testatina e numero di pagina seguono la gabbia.
        # Le pagine dell'indice ("toc") seguono la stessa gabbia del testo.
        # Senza pagine speculari l'interno e' sempre a sinistra.
        page_shift = 0.0
        if kind in (None, "toc") and shift_inner:
            physical_page = i + 1           # 1 = prima pagina fisica (recto)
            if not mirror or physical_page % 2 == 1:
                page_shift = shift_inner
        # EN: attached chapter images: drawn BEFORE the text block (outside
        #     BT/ET, as required by the PDF graphics model). Each entry is
        #     ("img", name, x, y, w, h); the XObject is created once and its
        #     id is referenced by this page's /XObject resources.
        # IT: immagini allegate ai capitoli: disegnate PRIMA del blocco di
        #     testo (fuori da BT/ET, come richiede il modello grafico PDF).
        #     Ogni voce e' ("img", nome, x, y, w, h); l'XObject viene creato
        #     una sola volta e il suo id e' citato nelle risorse /XObject
        #     della pagina.
        page_xobjects = {}
        text_lines = []
        for entry in lines:
            if entry and entry[0] == "rule":
                # EN/IT: table rule / filetto di tabella: (x1, y, x2, spessore)
                _tag, rx1, ry, rx2, rw = entry
                parts.append(f"q {rw:.2f} w 0.2 0.2 0.2 RG {rx1 + page_shift:.2f} "
                             f"{ry:.2f} m {rx2 + page_shift:.2f} {ry:.2f} l S Q"
                             .encode("latin-1"))
                continue
            if entry and entry[0] == "img":
                _tag, iname, ix, iy, dw, dh = entry
                oid = image_obj_ids.get(iname)
                if oid is None:
                    jpeg_b, iw, ih = chapter_images[iname]
                    oid = add_obj(
                        (f"<< /Type /XObject /Subtype /Image /Width {iw} "
                         f"/Height {ih} /ColorSpace /DeviceRGB "
                         f"/BitsPerComponent 8 /Filter /DCTDecode "
                         f"/Length {len(jpeg_b)} >>\nstream\n").encode("latin-1")
                        + jpeg_b + b"\nendstream")
                    image_obj_ids[iname] = oid
                res_name = f"ImA{oid}"
                page_xobjects[res_name] = oid
                parts.append(b"q")
                parts.append(f"{dw:.2f} 0 0 {dh:.2f} "
                             f"{ix + page_shift:.2f} {iy:.2f} cm"
                             .encode("latin-1"))
                parts.append(f"/{res_name} Do".encode("latin-1"))
                parts.append(b"Q")
            else:
                text_lines.append(entry)
        parts.append(b"BT")
        cur_fid = None
        cur_size = None
        cur_tw = 0.0   # word-spacing (Tw) attivo; 0 = normale (allineato a sx)
        for entry in text_lines:
            # EN: body lines may carry a 5th item, the justify target width
            #     (float) or None. Older 4-item lines (headings, centered,
            #     covers) are left flush as before.
            # IT: le righe di corpo possono portare un 5° elemento, la
            #     larghezza-obiettivo per la giustificazione (float) o None. Le
            #     righe a 4 elementi (intestazioni, centrate, copertine)
            #     restano allineate come prima.
            if len(entry) >= 5:
                x, ly, runs, sz, jw = entry[0], entry[1], entry[2], entry[3], entry[4]
            else:
                x, ly, runs, sz = entry
                jw = None
            # EN: compute word-spacing so the line reaches the target width:
            #     extra = target - natural, spread over the space characters.
            # IT: calcola lo spazio-parola perche' la riga raggiunga la
            #     larghezza-obiettivo: extra = obiettivo - naturale, diviso tra
            #     i caratteri di spazio.
            tw = 0.0
            if jw:
                natural = sum(seg_w(t, sz) for (t, _s) in runs if t)
                n_spaces = sum(t.count(" ") for (t, _s) in runs if t)
                if n_spaces > 0 and natural < jw:
                    extra = jw - natural
                    tw = extra / n_spaces
                    # non dilatare oltre misura: se servisse piu' di ~1 en per
                    # spazio la riga e' troppo corta (parole lunghissime),
                    # meglio lasciarla allineata a sinistra.
                    if tw > sz * 0.9:
                        tw = 0.0
            if tw != cur_tw:
                parts.append(f"{tw:.3f} Tw".encode("latin-1"))
                cur_tw = tw
            parts.append(f"1 0 0 1 {x + page_shift:.2f} {ly:.2f} Tm".encode("latin-1"))
            for (text, style) in runs:
                if text == "":
                    continue
                fid = style_to_fid.get(style, "F1")
                if fid != cur_fid or sz != cur_size:
                    parts.append(f"/{fid} {sz:.1f} Tf".encode("latin-1"))
                    cur_fid, cur_size = fid, sz
                parts.append(show_text(fid, text, tw, sz))
        # ripristina lo spazio-parola normale prima di intestazione/numero
        if cur_tw != 0.0:
            parts.append(b"0 Tw")
            cur_tw = 0.0
        if kind is None:
            visible_number += 1
            head_txt = title
            if 0 <= visible_number - 1 < len(chapter_page_header):
                head_txt = chapter_page_header[visible_number - 1]
            if head_txt:
                hw = seg_w(head_txt, 10)
                # testatina centrata sulla gabbia del testo (che sul recto e'
                # spostata dalla rilegatura), come nei libri ben composti
                hx = left_margin + page_shift + (usable_w - hw) / 2.0
                hy = page_h - m_top + leading * 0.4
                parts.append(b"ET BT")
                parts.append(b"/F1 10 Tf")
                parts.append(f"1 0 0 1 {hx:.2f} {hy:.2f} Tm".encode("latin-1"))
                parts.append(show_text("F1", head_txt, 0.0, 10))
                cur_fid = cur_size = None
            label = str(visible_number)
            lw = seg_w(label, 10)
            nx = left_margin + page_shift + (usable_w - lw) / 2.0
            ny = m_bottom / 2.0
            parts.append(b"ET BT")
            parts.append(b"/F1 10 Tf")
            parts.append(f"1 0 0 1 {nx:.2f} {ny:.2f} Tm".encode("latin-1"))
            parts.append(show_text("F1", label, 0.0, 10))
        parts.append(b"ET")
        stream = b"\n".join(parts)
        body = (f"<< /Length {len(stream)} >>\nstream\n".encode("latin-1")
                + stream + b"\nendstream")
        cid = add_obj(body)
        # EN: page resources: shared fonts plus this page's image XObjects.
        # IT: risorse di pagina: font condivisi piu' gli XObject immagine
        #     di questa pagina.
        xres = ""
        if page_xobjects:
            xrefs = " ".join(f"/{n} {oid} 0 R"
                             for n, oid in page_xobjects.items())
            xres = f"/XObject << {xrefs} >> "
        pid = add_obj(
            (f"<< /Type /Page /Parent {pages_obj_id} 0 R "
             f"/MediaBox [0 0 {page_w:.0f} {page_h:.0f}] "
             f"/Resources << /Font << {font_res} >> {xres}>> "
             f"/Contents {cid} 0 R >>").encode("latin-1"))
        page_obj_ids.append(pid)

    kids = " ".join(f"{pid} 0 R" for pid in page_obj_ids)
    objects[pages_obj_id - 1] = (
        f"<< /Type /Pages /Count {total} /Kids [{kids}] >>".encode("latin-1"))

    # EN: the outline — the clickable chapter tree in the reader's sidebar.
    #     Each item is an object pointing at a page; the items form a doubly
    #     linked list (/Prev, /Next) hanging off a single /Outlines root.
    #     Object ids must be known before the bodies are written, so we reserve
    #     empty slots first and fill them in afterwards.
    # IT: l'indice di navigazione: l'albero dei capitoli su cui si fa clic
    #     nella barra laterale del lettore. Ogni voce e' un oggetto che punta a
    #     una pagina; le voci formano una lista doppiamente concatenata
    #     (/Prev, /Next) appesa a un'unica radice /Outlines. Gli id degli
    #     oggetti servono prima dei contenuti, quindi si prenotano le caselle
    #     vuote e si riempiono dopo.
    voci = [(t, i) for t, i in outline_entries if 0 <= i < len(page_obj_ids)]
    outlines_id = None
    if voci:
        outlines_id = add_obj(None)
        voce_ids = [add_obj(None) for _ in voci]
        for k, (titolo, page_index) in enumerate(voci):
            pid = page_obj_ids[page_index]
            prev = f"/Prev {voce_ids[k - 1]} 0 R " if k > 0 else ""
            nxt = f"/Next {voce_ids[k + 1]} 0 R " if k < len(voci) - 1 else ""
            # /XYZ 0 altezza 0 = apri la pagina in cima, senza cambiare lo zoom
            objects[voce_ids[k] - 1] = (
                b"<< /Title " + _pdf_text_string(titolo)
                + f" /Parent {outlines_id} 0 R {prev}{nxt}"
                  f"/Dest [{pid} 0 R /XYZ 0 {page_h:.0f} 0] >>".encode("latin-1"))
        objects[outlines_id - 1] = (
            f"<< /Type /Outlines /First {voce_ids[0]} 0 R "
            f"/Last {voce_ids[-1]} 0 R /Count {len(voce_ids)} >>").encode("latin-1")

    # /PageMode /UseOutlines chiede al lettore di aprire subito il pannello dei
    # segnalibri: senza, molti visualizzatori li tengono nascosti e sembra che
    # non ci siano.
    extra_cat = (f"/Outlines {outlines_id} 0 R /PageMode /UseOutlines "
                 if outlines_id else "")
    catalog_id = add_obj(
        (f"<< /Type /Catalog /Pages {pages_obj_id} 0 R "
         f"{extra_cat}>>").encode("latin-1"))

    # EN: Type0 fonts: widths and ToUnicode map of the glyphs used.
    # IT: font Type0: larghezze e mappa ToUnicode dei glifi usati.
    for info in unicode_fonts.values():
        m = info["metrics"]
        dw = m.get("advance1000", 500)
        used = sorted(info["used"].items())
        w_arr = " ".join(f"{gid} [{m['uni_widths'].get(ord(ch), dw)}]"
                         for gid, ch in used)
        objects[info["cid"] - 1] = (
            f"<< /Type /Font /Subtype /CIDFontType2 /BaseFont /{info['ps']} "
            f"/CIDSystemInfo << /Registry (Adobe) /Ordering (Identity) "
            f"/Supplement 0 >> /FontDescriptor {info['descriptor']} 0 R "
            f"/DW {dw} /W [{w_arr}] /CIDToGIDMap /Identity >>").encode("latin-1")
        lines_tu = []
        for k in range(0, len(used), 100):
            part = used[k:k + 100]
            lines_tu.append(f"{len(part)} beginbfchar")
            lines_tu += [f"<{gid:04X}> <{ch.encode('utf-16-be').hex().upper()}>"
                         for gid, ch in part]
            lines_tu.append("endbfchar")
        cmap = ("/CIDInit /ProcSet findresource begin\n12 dict begin\nbegincmap\n"
                "/CIDSystemInfo << /Registry (Adobe) /Ordering (UCS) /Supplement 0 >> def\n"
                "/CMapName /Adobe-Identity-UCS def\n/CMapType 2 def\n"
                "1 begincodespacerange\n<0000> <FFFF>\nendcodespacerange\n"
                + "\n".join(lines_tu)
                + "\nendcmap\nCMapName currentdict /CMap defineresource pop\nend\nend")
        cmap_b = cmap.encode("latin-1")
        objects[info["tounicode"] - 1] = (
            f"<< /Length {len(cmap_b)} >>\nstream\n".encode("latin-1")
            + cmap_b + b"\nendstream")

    # 3) serializza con tabella xref
    out = bytearray()
    out += b"%PDF-1.4\n"
    offsets = [0] * (len(objects) + 1)
    for num, body in enumerate(objects, start=1):
        offsets[num] = len(out)
        out += f"{num} 0 obj\n".encode("latin-1")
        out += body
        out += b"\nendobj\n"
    xref_pos = len(out)
    n_obj = len(objects) + 1
    out += f"xref\n0 {n_obj}\n".encode("latin-1")
    out += b"0000000000 65535 f \n"
    for num in range(1, n_obj):
        out += f"{offsets[num]:010d} 00000 n \n".encode("latin-1")
    out += (f"trailer\n<< /Size {n_obj} /Root {catalog_id} 0 R >>\n"
            f"startxref\n{xref_pos}\n%%EOF").encode("latin-1")

    with open(path, "wb") as f:
        f.write(out)


# ---- Colori: i due temi -----------------------------------------------------
# EN: RuscaWriter has TWO page themes, each with a light and a dark version
#     (four combinations). They colour only the writing page, the preview and
#     the notes: bars, menus and dialogs follow the common RuscaLinux theme.
#
#       "ametista" — the RuscaLinux identity: the official plum and pink
#                    palette. The default theme.
#       "classico" — the look of a professional writing studio: a crisp white
#                    page, near-black ink, cool neutral greys and clear blue
#                    accents; in dark mode a charcoal page with a muted blue.
#
#     The criterion is the same for both: the RIGHT contrast, not the
#     maximum. Pure black on pure white (21:1) glares; white on black makes
#     letters bloom. Body text sits around 11:1 on its page, headings and
#     code at 7:1 or more, Markdown marks at 4.5:1 or more.
# IT: RuscaWriter ha DUE temi della pagina, ciascuno in versione chiara e
#     scura (quattro combinazioni). Colorano solo la pagina di scrittura,
#     l'anteprima e le note: barre, menu e dialoghi seguono il tema comune
#     di RuscaLinux.
#
#       "ametista" — l'identita' di RuscaLinux: la palette ufficiale prugna e
#                    rosa. E' il tema predefinito.
#       "classico" — l'aspetto di uno studio di scrittura professionale:
#                    pagina bianca nitida, inchiostro quasi nero, grigi
#                    freddi neutri e accenti blu decisi; nello scuro pagina
#                    carbone e blu smorzato.
#
#     Il criterio e' lo stesso per entrambi: il contrasto GIUSTO, non il
#     massimo. Nero pieno su bianco pieno (21:1) abbaglia; bianco su nero fa
#     sbavare le lettere. Il corpo del testo sta intorno a 11:1 sulla sua
#     pagina, titoli e codice ad almeno 7:1, i segni del Markdown ad almeno
#     4,5:1.
#
# NB: "PLUM" qui e' il COLORE prugna ("plum" in inglese), il tema cromatico
# storico dell'applicazione: non un residuo del vecchio nome del programma.

# Palette ufficiale RuscaLinux (specifiche dei RuscaLinux OS Tools, 4.1)
PLUM        = "#7A2357"   # prugna 600: accento nel chiaro
PLUM_DARK   = "#5C1A40"   # prugna scuro
PLUM_LIGHT  = "#F8D7E6"   # rosa chiaro
WHITE       = "#FFFFFF"

# Valori di ripiego per le chiavi neutre: li usa _standard_palette() se una
# tavolozza non le indica. I tre temi le indicano tutte.
PAPER_WHITE = "#FAF8F4"   # carta: avorio appena accennato, non bianco pieno
CREAM_PANEL = "#F0ECE4"   # pannelli
INK         = "#2B2A28"   # inchiostro: grafite, mai nero pieno
NIGHT_WARM  = "#1B1D1C"   # fondo scuro
NIGHT_PANEL = "#23262A"   # pannelli nel tema scuro
NIGHT_INK   = "#171918"   # area di scrittura scura
PARCHMENT   = "#D6D3CC"   # testo su fondo scuro

# --- "Ametista": dal rosa chiaro al prugna scuro -----------------------------
# EN: the colours of RuscaLinux. The identity lives in the frames: the bars
#     run from light pink to mauve in the light version, from plum to dark
#     plum in the dark one, always with text that reads on both ends of the
#     gradient (plum-black on pink, cream on plum). The page, where the eyes
#     rest for hours, keeps only a breath of pink.
# IT: i colori di RuscaLinux. L'identita' sta nelle cornici: le barre vanno
#     dal rosa chiaro al malva nella versione chiara, dal prugna al prugna
#     scuro in quella scura, sempre con un testo che si legge su entrambi i
#     capi della sfumatura (prugna-nero sul rosa, crema sul prugna). La
#     pagina, dove lo sguardo resta per ore, tiene solo un soffio di rosa.
AMETISTA_HUES = {
    # Pagina e testo: la palette ufficiale RuscaLinux (specifiche, 4.1).
    "paper":        "#FFFCFD",   # bianco con un soffio di rosa
    "panel":        "#FBF4F7",   # rosa 50
    "ink":          "#2D0A1D",   # prugna 900, ammorbidito a 11:1 sulla pagina
    "night":        "#2D0A1D",   # prugna 900
    "night_panel":  "#3A1028",   # prugna 800
    "night_ink":    "#230716",   # prugna 850: la pagina scura (poi schiarita)
    "parchment":    "#FFF7F0",   # crema
    "accent":       PLUM,
    "dark":         PLUM_DARK,
    "light":        PLUM_LIGHT,
    "glow":         "#F5B8D3",   # rosa 250: titoli e codice nello scuro
    "code":         "#7A2357",
    "wrap_light":   "#FBEFF4",
    "wrap_dark":    "#4A1634",
    "text":         "#7A2357",   # titoli e nomi dei capitoli
    # selezione: rosa chiaro con testo prugna nel chiaro, prugna con testo
    # crema nello scuro
    "sel":          "#F4C7DB", "on_sel":       "#2D0A1D",
    "night_sel":    "#7A2357", "night_on_sel": "#FFF7F0",
    # cornici (usate solo dalla tavolozza: la finestra segue il tema comune)
    "window_top":   "#FBF4F7",
    "chrome_a":     "#FBF4F7", "chrome_b":     "#F6E4EC",
    "menubar_a":    "#FBF4F7", "menubar_b":    "#F6E4EC",
    "on_chrome":    "#2D0A1D",
    "night_chrome_a":  "#3A1028", "night_chrome_b":  "#2D0A1D",
    "night_menubar_a": "#3A1028", "night_menubar_b": "#2D0A1D",
    "night_on_chrome": "#FFF7F0",
}

# --- "Classico": studio di scrittura -----------------------------------------
# EN: a crisp white page, near-black ink, cool neutral greys for the panels
#     and a clear blue for headings, code and selection, like the writing
#     programs of the Mac world. Dark: a charcoal page (not black) with soft
#     light-grey text and a muted blue selection.
# IT: pagina bianca nitida, inchiostro quasi nero, grigi freddi neutri per i
#     pannelli e un blu deciso per titoli, codice e selezione, come i
#     programmi di scrittura del mondo Mac. Scuro: pagina carbone (non nera)
#     con testo grigio chiaro e selezione blu smorzato.
CLASSICO_HUES = {
    "paper":        "#FDFDFC",   # bianco carta, appena sotto il bianco pieno
    "panel":        "#F2F3F5",   # grigio freddo del raccoglitore
    "ink":          "#1D1D1F",   # quasi nero
    "night":        "#1E1E1E",   # carbone
    "night_panel":  "#2A2A2C",
    "night_ink":    "#1E1E1E",   # la pagina scura (poi schiarita)
    "parchment":    "#E6E6E6",   # testo grigio chiaro sul carbone
    "accent":       "#2F6FBA",   # blu deciso: pulsanti e pallino
    "dark":         "#1F4F8A",
    "light":        "#DCE8F7",
    "glow":         "#8FB8EC",   # blu luminoso per titoli e codice nello scuro
    "code":         "#1F4F8A",
    "wrap_light":   "#EEF4FC",
    "wrap_dark":    "#24303F",
    "text":         "#1F4E79",   # titoli: blu profondo
    "sel":          "#B7D4FB", "on_sel":       "#101418",
    "night_sel":    "#2C4D77", "night_on_sel": "#F5F8FC",
    # cornici (usate solo dalla tavolozza: la finestra segue il tema comune)
    "window_top":   "#ECEDEF",
    "chrome_a":     "#F2F3F5", "chrome_b":     "#E6E8EB",
    "menubar_a":    "#F6F7F8", "menubar_b":    "#ECEDEF",
    "on_chrome":    "#1D1D1F",
    "night_chrome_a":  "#323234", "night_chrome_b":  "#28282A",
    "night_menubar_a": "#2E2E30", "night_menubar_b": "#262628",
    "night_on_chrome": "#E6E6E6",
}


# Codici dei temi. Il valore salvato nelle impostazioni ("theme_family") e'
# una di queste stringhe: qualunque altro valore passa da THEME_ALIASES o
# ripiega sul predefinito.
THEME_AMETISTA = "ametista"
THEME_CLASSICO = "classico"
BUILTIN_THEMES = (THEME_AMETISTA, THEME_CLASSICO)
THEMES = BUILTIN_THEMES
DEFAULT_THEME = THEME_AMETISTA
# nomi storici, tenuti perche' il codice esterno continui a funzionare
THEME_RUSCA, THEME_STANDARD = THEME_AMETISTA, THEME_CLASSICO

# EN/IT: themes that no longer exist. Whoever had one saved lands on the
# closest of the two, not on the default without explanation.
# / temi che non esistono piu'. Chi ne aveva uno salvato atterra sul piu'
# vicino dei due, non sul predefinito senza spiegazione.
THEME_ALIASES = {
    "rusca":         THEME_AMETISTA,
    "rubino":        THEME_AMETISTA,   # rosso profondo -> la famiglia calda
    "morganite":     THEME_AMETISTA,   # rosa chiarissimo -> il rosa
    "standard":      THEME_CLASSICO,
    "standard_blue": THEME_CLASSICO,
    "standard_red":  THEME_CLASSICO,
    "giada":         THEME_CLASSICO,
    "ambra":         THEME_CLASSICO,
    "velluto":       THEME_CLASSICO,
    "zaffiro":       THEME_CLASSICO,
    "lapislazzuli":  THEME_CLASSICO,
    "semplice":      THEME_CLASSICO,   # tolto nella 1.99.2: neutro -> Classico
}

THEME_HUES = {
    THEME_AMETISTA: AMETISTA_HUES,
    THEME_CLASSICO: CLASSICO_HUES,
}
STANDARD_HUES = THEME_HUES      # nome storico

THEME_LABEL_KEYS = {
    THEME_AMETISTA: "theme_ametista",
    THEME_CLASSICO: "theme_classico",
}

# EN/IT: a coloured dot beside each name in the menu, painted with the
# theme's own colour. / un pallino colorato accanto a ogni nome nel menu,
# dipinto con il colore del tema.
THEME_DOT_COLORS = {
    THEME_AMETISTA: "#7A2357",   # prugna RuscaLinux
    THEME_CLASSICO: "#2F6FBA",   # blu
}
THEME_DOT = "\u25CF"             # ● pallino pieno


def theme_hues(theme):
    """Colori di partenza di un tema, None se il codice non esiste."""
    return THEME_HUES.get(theme)


def theme_dot_color(theme):
    """EN/IT: the dot colour of a theme (#RRGGBB), or None. / il colore del
    pallino di un tema (#RRGGBB), o None."""
    color = THEME_DOT_COLORS.get(theme)
    if isinstance(color, str) and re.fullmatch(r"#[0-9A-Fa-f]{6}", color):
        return color
    return None


# EN/IT: only for the fallback submenu, used if GTK refuses the painted dots.
# / solo per il sottomenu di ripiego, se GTK rifiuta i pallini dipinti.
THEME_EMOJI = {
    THEME_AMETISTA: "\U0001F7E3",   # 🟣
    THEME_CLASSICO: "\U0001F535",   # 🔵
}


def theme_emoji(theme):
    return THEME_EMOJI.get(theme, "")


def theme_dot(theme):
    """Pallino del tema come testo semplice (senza colore), stringa vuota se
    il tema non ha un colore. Il menu usa theme_dot_color() e il markup."""
    return THEME_DOT if theme_dot_color(theme) else ""


THEME_LABEL_FALLBACK = {
    THEME_AMETISTA: "Ametista",
    THEME_CLASSICO: "Classico",
}


def theme_label(theme, translate=None):
    """Nome da mostrare nel menu, passando dalle traduzioni se possibile."""
    chiave = THEME_LABEL_KEYS.get(theme)
    ripiego = THEME_LABEL_FALLBACK.get(theme, theme)
    if translate and chiave:
        return translate(chiave, ripiego)
    return ripiego


def resolve_theme(code):
    """Traduce un codice di tema salvato nelle impostazioni in uno valido,
    tenendo conto dei nomi vecchi. Ripiega sul predefinito se non esiste."""
    code = THEME_ALIASES.get(code, code)
    return code if code in THEMES else DEFAULT_THEME


def _rgba(hex_color, alpha):
    """Da #RRGGBB alla forma rgba() del CSS, per le superfici traslucide."""
    h = hex_color.lstrip("#")
    r, g, b = (int(h[i:i + 2], 16) for i in (0, 2, 4))
    return f"rgba({r},{g},{b},{alpha:.2f})"


def _mix_hex(a, b, t):
    """EN/IT: colour a moved towards b by t (0..1) / il colore a spostato
    verso b di t (0..1)."""
    ca = [int(a.lstrip("#")[i:i + 2], 16) for i in (0, 2, 4)]
    cb = [int(b.lstrip("#")[i:i + 2], 16) for i in (0, 2, 4)]
    return "#" + "".join(f"{round(x + (y - x) * t):02X}" for x, y in zip(ca, cb))


# EN — the writing text is not printed at full strength: around 11:1 on its
#      page is far above every readability guideline (AAA asks 7:1) and no
#      longer glares.
# IT — il testo da scrivere non si stampa a piena forza: intorno a 11:1 sulla
#      sua pagina resta molto sopra ogni norma (AAA chiede 7:1) e non abbaglia.
EDITOR_INK_SOFTEN = 0.09


def _standard_palette(hues, dark):
    """Costruisce la tavolozza di un tema dai suoi colori di partenza.

    Restituisce un dizionario di RUOLI (sfondo dell'editor, testo dei titoli,
    fasce...), non di colori: build_css() e i colori del Markdown nell'editor
    leggono tutti da qui.
    """
    accent, accent_dark = hues["accent"], hues["dark"]
    accent_light, glow = hues["light"], hues["glow"]
    on_accent = hues.get("on_accent", WHITE)
    testo = hues.get("text", accent_dark)
    carta = hues.get("paper", PAPER_WHITE)
    pannelli = hues.get("panel", CREAM_PANEL)
    inchiostro = hues.get("ink", INK)
    notte = hues.get("night", NIGHT_WARM)
    notte_pann = hues.get("night_panel", NIGHT_PANEL)
    notte_ink = hues.get("night_ink", NIGHT_INK)
    chiaro_su_scuro = hues.get("parchment", PARCHMENT)
    if dark:
        accent = hues.get("night_accent", accent)
        accent_dark = hues.get("night_accent_dark", accent_dark)
        chrome_a = hues.get("night_chrome_a", accent_dark)
        chrome_b = hues.get("night_chrome_b", notte)
        menubar_a = hues.get("night_menubar_a", accent)
        menubar_b = hues.get("night_menubar_b", accent_dark)
        on_chrome = hues.get("night_on_chrome",
                             hues.get("on_accent_dark", WHITE))
        return dict(
            accent=accent, accent_dark=accent_dark, accent_light=accent_light,
            on_accent=hues.get("on_accent_dark", WHITE),
            sel_bg=hues.get("night_sel", accent),
            sel_fg=hues.get("night_on_sel", hues.get("on_accent_dark", WHITE)),
            menubar_a=menubar_a, menubar_b=menubar_b, on_chrome=on_chrome,
            bg_top=notte, bg_bottom=notte_pann,
            header_a=chrome_a, header_b=chrome_b,
            panel_bg=notte_pann,
            list_text=glow,
            editor_bg=notte_ink, editor_fg=chiaro_su_scuro,
            notes_fg=chiaro_su_scuro,
            title_fg=glow,
            status_a=accent_dark, status_b=notte,
            status_fg=glow,
            findbar_bg="rgba(20,22,26,0.95)",
            dialog_fg=chiaro_su_scuro,
            entry_bg=notte_ink, entry_fg=chiaro_su_scuro,
            head=glow, code=glow, marker=accent,
            wrapmark=hues["wrap_dark"],
            text_contrast=hues.get("dark_contrast", DARK_TEXT_CONTRAST),
        )
    return dict(
        accent=accent, accent_dark=accent_dark, accent_light=accent_light,
        on_accent=on_accent,
        sel_bg=hues.get("sel", accent),
        sel_fg=hues.get("on_sel", on_accent),
        menubar_a=hues.get("menubar_a", accent),
        menubar_b=hues.get("menubar_b", accent_dark),
        on_chrome=hues.get("on_chrome", on_accent),
        bg_top=hues.get("window_top", accent_light), bg_bottom=carta,
        header_a=hues.get("chrome_a", accent),
        header_b=hues.get("chrome_b", accent_light),
        panel_bg=_rgba(pannelli, 0.90),
        list_text=testo,
        editor_bg=carta,
        editor_fg=_mix_hex(inchiostro, carta, EDITOR_INK_SOFTEN),
        notes_fg=testo,
        title_fg=testo,
        status_a=accent_light, status_b=carta,
        status_fg=testo,
        findbar_bg=_rgba(carta, 0.92),
        dialog_fg=inchiostro,
        entry_bg=carta, entry_fg=inchiostro,
        head=testo, code=hues["code"], marker=accent_light,
        wrapmark=hues["wrap_light"],
        text_contrast=hues.get("light_contrast", LIGHT_TEXT_CONTRAST),
    )


def theme_palette(theme=DEFAULT_THEME, dark=False):
    """Restituisce la tavolozza completa di una combinazione tema + luminosita'.

    E' l'UNICO posto in cui si decide quale colore svolge quale ruolo. Il
    foglio di stile (build_css) e i colori del testo Markdown nell'editor
    leggono entrambi da qui, così le sei combinazioni restano coerenti.
    """
    theme = resolve_theme(theme)
    p = _standard_palette(theme_hues(theme), dark)
    _comfort(p, dark)
    return p


# ---------------------------------------------------------------------------
# EN — EYE COMFORT. One pass applied to every theme, built-in or written by
#      the user, so no palette has to get these numbers right by hand:
#        * dark mode: no surface near pure black. Very dark grounds make light
#          letters "bloom" (halation) and the pupil works harder; screens and
#          reading apps keep the darkest surface around 12–15 % grey. The
#          writing area is lifted to that, panels a step above it.
#        * dark mode: text at about 11:1, not 15:1. Off-white on dark grey
#          reads as clearly and glares less.
#        * buttons: a quiet tint of the accent, not a solid block. The eye is
#          drawn to the most saturated thing on screen, and that should be
#          the text, not a "+" button.
#        * the status bar in dark mode: a muted band, not the accent.
# IT — RIPOSO DEGLI OCCHI. Un passaggio applicato a ogni tema, incorporato o
#      scritto dall'utente, cosi' nessuna tavolozza deve azzeccare a mano
#      questi numeri:
#        * scuro: nessuna superficie vicina al nero pieno. Su fondi molto scuri
#          le lettere chiare "sbavano" (alone) e la pupilla lavora di piu';
#          la superficie piu' scura resta intorno al 12–15 % di grigio. L'area
#          di scrittura sale a quel livello, i pannelli un gradino sopra.
#        * scuro: testo a circa 11:1, non 15:1. Il bianco sporco su grigio
#          scuro si legge altrettanto bene e abbaglia meno.
#        * pulsanti: una tinta tenue dell'accento, non un blocco pieno.
#          L'occhio va sulla cosa piu' satura dello schermo, e quella deve
#          essere il testo, non un pulsante "+".
#        * barra di stato nel tema scuro: una fascia smorzata, non l'accento.
# ---------------------------------------------------------------------------
DARK_EDITOR_LUM = 0.018        # area di scrittura scura (~ #252525)
DARK_PANEL_LUM = 0.024         # pannelli e fasce, un gradino sopra
DARK_TEXT_CONTRAST = 11.0      # testo su fondo scuro
LIGHT_TEXT_CONTRAST = 11.0     # testo sulla pagina chiara (tetto, non minimo)
UI_TEXT_MIN_CONTRAST = 7.0     # minimo per ogni scritta dell'interfaccia (AAA)


def _lum(c):
    h = c.lstrip("#")
    v = [int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)]
    v = [x / 12.92 if x <= 0.03928 else ((x + 0.055) / 1.055) ** 2.4
         for x in v]
    return 0.2126 * v[0] + 0.7152 * v[1] + 0.0722 * v[2]


def _contrast(a, b):
    la, lb = sorted((_lum(a), _lum(b)), reverse=True)
    return (la + 0.05) / (lb + 0.05)


def _is_hex(c):
    return isinstance(c, str) and re.fullmatch(r"#[0-9A-Fa-f]{6}", c) is not None


def _lift(c, target):
    """EN/IT: raise a dark colour to a luminance, keeping its tint / alza un
    colore scuro fino a una luminanza, tenendo la sua tinta."""
    if not _is_hex(c) or _lum(c) >= target:
        return c
    lo, hi = 0.0, 1.0
    for _ in range(20):
        mid = (lo + hi) / 2
        if _lum(_mix_hex(c, "#FFFFFF", mid)) < target:
            lo = mid
        else:
            hi = mid
    return _mix_hex(c, "#FFFFFF", hi)


def _ease_text(fg, bg, target):
    """EN/IT: move a text colour towards its ground until the contrast is
    about *target* (never below) / avvicina un colore di testo al suo fondo
    finche' il contrasto e' circa *target* (mai sotto)."""
    if not (_is_hex(fg) and _is_hex(bg)) or _contrast(fg, bg) <= target:
        return fg
    lo, hi = 0.0, 1.0
    for _ in range(20):
        mid = (lo + hi) / 2
        if _contrast(_mix_hex(fg, bg, mid), bg) > target:
            lo = mid
        else:
            hi = mid
    return _mix_hex(fg, bg, lo)


def _readable(fg, bg, minimum=UI_TEXT_MIN_CONTRAST):
    """EN/IT: push a text colour away from its ground until it reaches the
    minimum contrast / allontana un colore di testo dal suo fondo finche'
    raggiunge il contrasto minimo."""
    if not (_is_hex(fg) and _is_hex(bg)) or _contrast(fg, bg) >= minimum:
        return fg
    verso = "#000000" if _lum(bg) > 0.18 else "#FFFFFF"
    for step in range(1, 21):
        cand = _mix_hex(fg, verso, step / 20)
        if _contrast(cand, bg) >= minimum:
            return cand
    return verso


def _readable_on(p, fg, *bgs, minimum=None):
    """EN/IT: make p[fg] readable on every ground listed (the two ends of a
    gradient, for instance) / rende p[fg] leggibile su ogni fondo indicato
    (per esempio i due capi di una sfumatura)."""
    minimo = UI_TEXT_MIN_CONTRAST if minimum is None else minimum
    for bg in bgs:
        if _is_hex(p.get(bg)) and _is_hex(p.get(fg)):
            p[fg] = _readable(p[fg], p[bg], minimo)


def _comfort(p, dark):
    accent, accent_dark = p["accent"], p["accent_dark"]
    target = p.pop("text_contrast", DARK_TEXT_CONTRAST if dark
                   else LIGHT_TEXT_CONTRAST)
    if dark:
        for key in ("editor_bg", "entry_bg"):
            p[key] = _lift(p[key], DARK_EDITOR_LUM)
        for key in ("bg_top", "status_b", "header_b"):
            p[key] = _lift(p[key], DARK_EDITOR_LUM)
        for key in ("bg_bottom", "header_a", "menubar_a", "menubar_b"):
            p[key] = _lift(p[key], DARK_PANEL_LUM)
        if _is_hex(p["bg_bottom"]):
            p["panel_bg"] = p["bg_bottom"]
        for key in ("editor_fg", "notes_fg", "dialog_fg", "entry_fg"):
            p[key] = _ease_text(p[key], p["editor_bg"], target)
        p["status_a"] = _mix_hex(accent_dark, p["editor_bg"], 0.55) \
            if _is_hex(accent_dark) and _is_hex(p["editor_bg"]) \
            else p["status_a"]
        ground = p["editor_bg"]
        # pulsanti: l'accento smorzato verso il fondo, testo chiaro
        btn_a = _mix_hex(accent, ground, 0.45)
        btn_b = _mix_hex(accent, ground, 0.55)
        btn_fg = p.get("title_fg", "#FFFFFF")
    else:
        ground = p["editor_bg"]
        # il testo da scrivere intorno al contrasto scelto dal tema
        p["editor_fg"] = _ease_text(p["editor_fg"], ground, target)
        # pulsanti: una tinta chiara dell'accento, testo nel suo scuro
        btn_a = _mix_hex(accent, ground, 0.82)
        btn_b = _mix_hex(accent, ground, 0.74)
        btn_fg = accent_dark
    p["btn_a"], p["btn_b"], p["btn_fg"] = btn_a, btn_b, btn_fg
    p["btn_hover_a"] = _mix_hex(btn_a, accent, 0.12)
    p["btn_hover_b"] = _mix_hex(btn_b, accent, 0.12)
    # ogni scritta resta leggibile sul suo fondo (su entrambi i capi delle
    # sfumature), dopo tutti i ritocchi: almeno 7:1, il livello AAA
    _readable_on(p, "btn_fg", "btn_a", "btn_b", "btn_hover_a", "btn_hover_b")
    _readable_on(p, "list_text", "editor_bg")
    _readable_on(p, "title_fg", "editor_bg")
    _readable_on(p, "head", "editor_bg")
    _readable_on(p, "status_fg", "status_a", "status_b")
    _readable_on(p, "on_chrome", "header_a", "header_b",
                 "menubar_a", "menubar_b")
    _readable_on(p, "dialog_fg", "bg_top", "bg_bottom")
    _readable_on(p, "sel_fg", "sel_bg")
    _readable_on(p, "entry_fg", "entry_bg")
    # il testo del corpo: mai sotto 7:1, anche dopo l'ammorbidimento
    _readable_on(p, "editor_fg", "editor_bg")
    _readable_on(p, "notes_fg", "editor_bg")
    # sulla pagina anche codice (7:1) e marcatori del Markdown (4,5:1, il
    # minimo per il testo): smorzati, ma mai illeggibili. Il testo resta
    # leggibile anche sulle righe evidenziate da "Ricuci i paragrafi".
    _readable_on(p, "code", "editor_bg")
    _readable_on(p, "marker", "editor_bg", minimum=4.5)
    _readable_on(p, "editor_fg", "wrapmark")
    # EN: the accent GTK itself uses (check boxes, the main button of a
    #     dialog, focus rings, switches): without this they stay Adwaita blue
    #     in every theme. White on it at 7:1 or more.
    # IT: l'accento che usa GTK stesso (caselle di spunta, pulsante
    #     principale dei dialoghi, contorni del fuoco): senza questo restano
    #     del blu di Adwaita in ogni tema. Bianco sopra almeno a 7:1.
    if dark:
        p["gtk_accent_bg"], p["gtk_accent_fg"] = p["sel_bg"], p["sel_fg"]
    else:
        fondo = accent
        for passo in range(0, 21):
            fondo = _mix_hex(accent, accent_dark, passo / 10) if passo <= 10 \
                else _mix_hex(accent_dark, "#000000", (passo - 10) / 20)
            if _contrast("#FFFFFF", fondo) >= UI_TEXT_MIN_CONTRAST:
                break
        p["gtk_accent_bg"], p["gtk_accent_fg"] = fondo, "#FFFFFF"
    p["gtk_accent"] = p["head"]


def build_css(dark=False, theme=DEFAULT_THEME):
    """Foglio di stile della PAGINA: area di scrittura, anteprima e note.

    Barre, menu, pulsanti e dialoghi sono quelli di libadwaita, colorati dal
    tema comune dei RuscaLinux OS Tools (style.css): il tema di RuscaWriter
    (Ametista, Classico) colora solo la carta su cui si scrive.
    """
    p = theme_palette(theme, dark)
    return f"""
textview.text-editor, textview.text-editor text,
textview.notes-editor, textview.notes-editor text {{
    background-color: {p["editor_bg"]};
}}
textview.text-editor, textview.text-editor text {{
    color: {p["editor_fg"]};
    caret-color: {p["head"]};
}}
textview.notes-editor, textview.notes-editor text {{
    color: {p["notes_fg"]};
    caret-color: {p["head"]};
}}
textview.text-editor text selection, textview.notes-editor text selection {{
    background-color: {p["sel_bg"]};
    color: {p["sel_fg"]};
}}
"""


CSS = build_css(dark=False, theme=DEFAULT_THEME)


class Chapter:
    """Un capitolo: testo + nota. Indice 1-based -> 01.txt / 01n.txt.
    La copertina (is_cover) usa indice 0 -> 00.txt e non e' spostabile/cancellabile."""
    def __init__(self, index, text="", note="", is_cover=False, custom_title=""):
        self.index = index
        self.text = text
        self.note = note
        self.is_cover = is_cover
        self.custom_title = custom_title or ""   # titolo scelto dall'utente

    @property
    def base(self):
        return f"{self.index:02d}"

    @property
    def text_name(self):
        return f"{self.base}.md"

    @property
    def note_name(self):
        return f"{self.base}n.md"

    def title_with_fallback(self, fallback_template="Capitolo {n}", cover_label="Copertina"):
        """Titolo del capitolo. Priorita': titolo personalizzato dell'utente,
        poi intestazione markdown (# Titolo), poi prima riga tutta in MAIUSCOLO;
        altrimenti il fallback. La copertina mostra sempre l'etichetta dedicata."""
        if self.is_cover:
            return cover_label
        if self.custom_title.strip():
            return self.custom_title.strip()
        for line in self.text.splitlines():
            stripped = line.strip()
            if not stripped:
                continue
            # intestazione markdown: # Titolo, ## Titolo, ...
            if stripped.startswith("#"):
                heading = stripped.lstrip("#").strip()
                if heading:
                    return heading
            # prima riga interamente maiuscola
            if stripped == stripped.upper() and any(c.isalpha() for c in stripped):
                return stripped
            # se la prima riga non vuota non e' un titolo, fermati comunque
            break
        return fallback_template.format(n=self.index)

    @property
    def title(self):
        return self.title_with_fallback()


class Project:
    def __init__(self):
        self.path = None          # percorso del file .rwr
        self.chapters = []        # lista di Chapter
        self.title = "Senza titolo"
        self.meta = {}            # preferenze salvate nel documento (es. font)
        self._lang = "it"         # lingua per le etichette degli export
        # --- sezioni editoriali opzionali -----------------------------------
        self.cover_image = None
        self.cover_image_fmt = None      # "png" | "jpeg" | "webp"
        # EN: images attached inside chapters: name -> raw bytes. Names are
        #     img_001.png, img_002.webp, ... and are referenced from the text
        #     with standard Markdown: ![caption](img_001.png)
        # IT: immagini allegate nei capitoli: nome -> byte grezzi. I nomi sono
        #     img_001.png, img_002.webp, ... e sono richiamati dal testo con
        #     Markdown standard: ![didascalia](img_001.png)
        self.images = {}
        # frontespizio e colophon come CAMPI strutturati (formattazione
        # professionale decisa dal programma). Vedi FRONT_FIELDS / COLO_FIELDS.
        self.frontispiece_fields = {k: "" for k in FRONT_FIELDS}
        self.colophon_fields = {k: "" for k in COLO_FIELDS}

    # ---- margini di pagina / page margins --------------------------------
    # EN: margins belong to the BOOK, not to the program: they are saved in
    #     the document (meta.json), one set per page format, so a book
    #     reopened next year prints exactly as before, and switching format
    #     does not drag the margins of another format along.
    # IT: i margini appartengono al LIBRO, non al programma: si salvano nel
    #     documento (meta.json), un insieme per ogni formato di pagina, cosi'
    #     un libro riaperto fra un anno si stampa esattamente come prima, e
    #     cambiare formato non si porta dietro i margini di un altro.
    def page_margins(self, page_size):
        saved = (self.meta.get("page_margins") or {}).get(page_size)
        return normalize_page_margins(saved, page_size)

    def set_page_margins(self, page_size, margins):
        """Salva i margini di un formato. Se coincidono con quelli del formato
        non si scrive nulla: il documento resta pulito e seguira' eventuali
        miglioramenti futuri dei valori predefiniti."""
        tutti = dict(self.meta.get("page_margins") or {})
        pulito = normalize_page_margins(margins, page_size)
        if which_margin_preset(page_size, pulito) == MARGIN_PRESET_FORMAT:
            tutti.pop(page_size, None)
        else:
            tutti[page_size] = pulito
        if tutti:
            self.meta["page_margins"] = tutti
        else:
            self.meta.pop("page_margins", None)
        return pulito

    def set_cover_image(self, data, fmt):
        """EN: Set the cover image. fmt: 'png', 'jpeg' or 'webp'.
        IT: Imposta l'immagine di copertina. fmt: 'png', 'jpeg' o 'webp'."""
        self.cover_image = data
        self.cover_image_fmt = fmt

    def clear_cover_image(self):
        self.cover_image = None
        self.cover_image_fmt = None

    def has_cover_image(self):
        return bool(self.cover_image)

    # ---- immagini nei capitoli / chapter images ----------------------------
    def add_image(self, data):
        """EN: Store an attached image (PNG/JPEG/WebP, detected from the
        content) and return its internal name (e.g. 'img_001.png'), ready to
        be referenced from the text as ![caption](img_001.png).
        Raises ValueError for unsupported formats.
        IT: Registra un'immagine allegata (PNG/JPEG/WebP, riconosciuta dal
        contenuto) e restituisce il suo nome interno (es. 'img_001.png'),
        pronto per essere richiamato dal testo come ![didascalia](img_001.png).
        Solleva ValueError per i formati non supportati."""
        fmt = image_format(data)
        if fmt is None:
            raise ValueError("Formato immagine non supportato "
                             "(usa PNG, JPEG o WebP). / Unsupported image "
                             "format (use PNG, JPEG or WebP).")
        ext = IMAGE_FORMATS[fmt][0]
        # EN: first free progressive number, so deleting one image never
        #     breaks the names of the others.
        # IT: primo numero progressivo libero, cosi' eliminare un'immagine
        #     non rompe mai i nomi delle altre.
        n = 1
        while any(name.startswith(f"img_{n:03d}.") for name in self.images):
            n += 1
        name = f"img_{n:03d}.{ext}"
        self.images[name] = data
        return name

    # EN/IT: largest picture copied in from a Markdown file / immagine piu'
    #        grande copiata da un file Markdown
    IMPORT_IMAGE_MAX_BYTES = 30 * 1024 * 1024

    def import_md_images(self, text, base_dir):
        """EN: Markdown imported from a file may point to pictures next to it
        (![Map](italia.jpg)). Each local picture that exists and is PNG, JPEG
        or WebP is copied INTO the project and the line is rewritten to its
        internal name, so the preview, the editor and every export show it.
        Remote addresses and missing files are left as they are.
        IT: Il Markdown importato da un file puo' citare immagini accanto al
        file (![Mappa](italia.jpg)). Ogni immagine locale che esiste ed e'
        PNG, JPEG o WebP viene copiata DENTRO il progetto e la riga viene
        riscritta con il suo nome interno, cosi' anteprima, editor ed export
        la mostrano. Indirizzi remoti e file mancanti restano come sono."""
        done = {}

        def repl(line):
            m = _IMG_LINE_RE.match(line.strip())
            if not m:
                return line
            src = m.group("src")
            if src in self.images or re.match(r"^[a-z][\w+.-]*://", src, re.I):
                return line
            if src not in done:
                done[src] = None
                path = os.path.expanduser(src)
                if not os.path.isabs(path):
                    path = os.path.join(base_dir or ".", path)
                try:
                    if os.path.isfile(path) and \
                            os.path.getsize(path) <= self.IMPORT_IMAGE_MAX_BYTES:
                        with open(path, "rb") as f:
                            done[src] = self.add_image(f.read())
                except (OSError, ValueError):
                    done[src] = None
            if not done[src]:
                return line
            return line.replace(f"]({src})", f"]({done[src]})", 1)
        return "\n".join(repl(ln) for ln in text.split("\n"))

    def image_mime(self, name):
        """EN: MIME type of an attached image (from its content).
        IT: Tipo MIME di un'immagine allegata (dal suo contenuto)."""
        fmt = image_format(self.images.get(name, b""))
        return IMAGE_FORMATS[fmt][1] if fmt else "application/octet-stream"

    def _image_data_uri(self, name):
        """EN: base64 data URI of an attached image (single-file HTML export).
        IT: data URI base64 di un'immagine allegata (export HTML a file unico)."""
        data = self.images.get(name)
        if not data:
            return None
        import base64
        b64 = base64.b64encode(data).decode("ascii")
        return f"data:{self.image_mime(name)};base64,{b64}"

    def used_images(self):
        """EN: Names of the attached images actually referenced by at least
        one chapter, in first-appearance order (exports only ship these).
        IT: Nomi delle immagini allegate effettivamente richiamate da almeno
        un capitolo, in ordine di prima apparizione (gli export includono
        solo queste)."""
        seen = []
        for ch in self.chapters:
            for name in block_images(book_blocks(ch.text)):
                if name in self.images and name not in seen:
                    seen.append(name)
        return seen

    # ---- creazione / caricamento -------------------------------------------
    def _make_cover_text(self, title):
        """Testo predefinito della copertina interna: solo NOME OPERA e DATA.
        L'autore NON viene inserito qui: l'autore dell'opera e' quello indicato
        nei campi del frontespizio (File -> Sezioni editoriali), non lo
        sviluppatore dell'applicazione."""
        import datetime
        oggi = datetime.date.today().strftime("%d/%m/%Y")
        return f"{title.upper()}\n\n{oggi}"

    def new(self, title="Nuovo progetto"):
        self.title = title
        self.path = None
        self.cover_image = None
        self.cover_image_fmt = None
        self.images = {}
        self.frontispiece_fields = {k: "" for k in FRONT_FIELDS}
        self.colophon_fields = {k: "" for k in COLO_FIELDS}
        cover = Chapter(0, self._make_cover_text(title), "", is_cover=True)
        # Nessun capitolo creato in automatico: il progetto parte vuoto e
        # l'utente aggiunge i capitoli che vuole (Capitolo -> Aggiungi capitolo).
        self.chapters = [cover]

    def import_text_file(self, path):
        """Crea un nuovo progetto importando un file di testo (.txt) o
        Markdown (.md). Il titolo dell'opera viene dal nome del file. Per il
        Markdown, il documento viene suddiviso in capitoli usando le
        intestazioni di primo o secondo livello (# / ##) come punti di taglio;
        per il TXT, se ci sono righe di separazione tipo capitolo le usa,
        altrimenti tiene tutto in un unico capitolo."""
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            raw = f.read()
        raw = raw.replace("\r\n", "\n").replace("\r", "\n")
        # Via l'intestazione e la licenza di Project Gutenberg, se ci sono:
        # sono righe generate a macchina, riconosciute alla lettera.
        # I paragrafi spezzati a colonna fissa, invece, NON si toccano qui:
        # e' una scelta di chi scrive, e la fa dal menu quando vuole
        # (vedi wrapped_runs e rejoin_paragraphs).
        raw = strip_gutenberg_boilerplate(raw)

        title = os.path.splitext(os.path.basename(path))[0]
        is_md = path.lower().endswith((".md", ".markdown"))

        self.title = title
        self.path = None        # importato: nessun .rwr associato finché non si salva
        self.meta = {}
        self.cover_image = None
        self.cover_image_fmt = None
        self.images = {}
        self.frontispiece_fields = {k: "" for k in FRONT_FIELDS}
        self.colophon_fields = {k: "" for k in COLO_FIELDS}
        cover = Chapter(0, self._make_cover_text(title), "", is_cover=True)
        self.chapters = [cover]
        if is_md:
            # EN/IT: pictures next to the file come into the project too /
            #        le immagini accanto al file entrano nel progetto
            raw = self.import_md_images(raw, os.path.dirname(os.path.abspath(path)))

        # suddivisione in capitoli
        chunks = []   # lista di (titolo_opzionale, testo)
        if is_md:
            # taglia ad ogni intestazione di livello 1 o 2 mantenendola nel testo
            lines = raw.split("\n")
            current = []
            current_title = ""
            def flush():
                if current and any(l.strip() for l in current):
                    chunks.append((current_title, "\n".join(current).strip("\n")))
            for line in lines:
                m = re.match(r"^(#{1,2})\s+(.*)$", line.strip())
                if m:
                    # nuova sezione: salva la precedente e inizia
                    flush()
                    current = [line]
                    current_title = m.group(2).strip()
                else:
                    current.append(line)
            flush()
        if not chunks:
            # TXT, o MD senza intestazioni: prova a spezzare su separatori tipici
            # (righe con soli '***', '---' o '* * *'); altrimenti capitolo unico
            parts = re.split(r"\n\s*(?:\*\s*\*\s*\*|-{3,}|\*{3,})\s*\n", raw)
            parts = [p.strip("\n") for p in parts if p.strip()]
            if len(parts) > 1:
                chunks = [("", p) for p in parts]
            else:
                chunks = [("", raw.strip("\n"))]

        idx = 1
        for _ttl, body in chunks:
            self.chapters.append(Chapter(idx, body, ""))
            idx += 1
        self._renumber()

    def load(self, path):
        self.path = path
        self.title = os.path.splitext(os.path.basename(path))[0]
        self.chapters = []
        self.meta = {}
        contents = {}        # nome file -> bytes
        # EN: a .rwr is read into memory and NEVER extracted to disk, so a
        #     crafted path ("../../.bashrc") cannot write anywhere. The limits
        #     stop a tiny archive that inflates to gigabytes (a "tar bomb").
        # IT: un .rwr si legge in memoria e non si estrae MAI su disco, così
        #     un percorso costruito ad arte ("../../.bashrc") non può
        #     scrivere da nessuna parte. I limiti fermano un archivio minuscolo
        #     che si gonfia fino a gigabyte (una "bomba tar").
        total = 0
        with tarfile.open(path, "r:gz") as tar:
            for count, member in enumerate(tar):
                if count >= MAX_PROJECT_MEMBERS:
                    raise ValueError("Progetto non valido: troppi file "
                                     "nell'archivio / too many entries.")
                if not member.isfile():
                    continue
                total += member.size
                if member.size > MAX_PROJECT_BYTES or total > MAX_PROJECT_BYTES:
                    raise ValueError("Progetto non valido: archivio troppo "
                                     "grande / archive too large.")
                name = os.path.basename(member.name)
                f = tar.extractfile(member)
                if f is not None:
                    contents[name] = f.read(member.size)
        names = set(contents)
        if "meta.json" in names:
            try:
                self.meta = json.loads(contents["meta.json"].decode("utf-8"))
            except Exception:
                self.meta = {}
        # riconosce i file dei capitoli sia .md sia (per progetti vecchi) .txt
        def chapter_index(fname):
            for ext in (".md", ".txt"):
                if fname.endswith(ext) and not fname.endswith("n" + ext):
                    stem = fname[:-len(ext)]
                    if stem.isdigit():
                        return int(stem)
            return None

        idx_to_files = {}    # idx -> (text_name, note_name)
        for n in names:
            idx = chapter_index(n)
            if idx is not None:
                ext = ".md" if n.endswith(".md") else ".txt"
                # EN/IT: the real names, not rebuilt ones: "1.md" written by
                # hand must not become a KeyError on "01.md".
                stem = n[:-len(ext)]
                idx_to_files[idx] = (n, f"{stem}n{ext}")

        for idx in sorted(idx_to_files):
            text_name, note_name = idx_to_files[idx]
            ch = Chapter(idx, is_cover=(idx == 0))
            ch.text = contents[text_name].decode("utf-8", errors="replace")
            if note_name in names:
                ch.note = contents[note_name].decode("utf-8", errors="replace")
            self.chapters.append(ch)
        # titoli personalizzati salvati nei metadati (mappa indice->titolo)
        titles = self.meta.get("titles") or {}
        if isinstance(titles, dict):
            for ch in self.chapters:
                ct = titles.get(str(ch.index))
                if ct:
                    ch.custom_title = ct
        # garantisci la presenza della copertina come primo elemento
        if not self.chapters or not self.chapters[0].is_cover:
            cover = Chapter(0, self._make_cover_text(self.title), "", is_cover=True)
            self.chapters.insert(0, cover)
        # NB: nessun capitolo creato in automatico se il progetto e' vuoto:
        # un progetto senza capitoli e' uno stato legittimo.
        self._renumber()

        # --- sezioni editoriali opzionali ----------------------------------
        self.frontispiece_fields = {k: "" for k in FRONT_FIELDS}
        self.colophon_fields = {k: "" for k in COLO_FIELDS}
        self.cover_image = None
        self.cover_image_fmt = None
        # EN: attached chapter images travel inside the archive as img_*.<ext>
        # IT: le immagini allegate viaggiano nell'archivio come img_*.<ext>
        self.images = {n: b for n, b in contents.items()
                       if re.match(r"^img_\d+\.(png|jpe?g|webp)$", n)}
        # nuovo formato: campi strutturati in JSON
        if "frontispiece.json" in names:
            try:
                d = json.loads(contents["frontispiece.json"].decode("utf-8"))
                for k in FRONT_FIELDS:
                    self.frontispiece_fields[k] = str(d.get(k, "") or "")
            except Exception:
                pass
        elif "frontispiece.md" in names:
            # vecchio formato a testo libero: lo conserviamo nel sottotitolo,
            # cosi' non si perde nulla nella transizione
            try:
                old = contents["frontispiece.md"].decode("utf-8").strip()
                if old:
                    self.frontispiece_fields["subtitle"] = old
            except Exception:
                pass
        if "colophon.json" in names:
            try:
                d = json.loads(contents["colophon.json"].decode("utf-8"))
                for k in COLO_FIELDS:
                    self.colophon_fields[k] = str(d.get(k, "") or "")
            except Exception:
                pass
        elif "colophon.md" in names:
            try:
                old = contents["colophon.md"].decode("utf-8").strip()
                if old:
                    self.colophon_fields["notes"] = old
            except Exception:
                pass
        # EN: cover image, in any of the accepted formats.
        # IT: immagine di copertina, in uno qualsiasi dei formati accettati.
        for cname, cfmt in (("cover.jpg", "jpeg"), ("cover.jpeg", "jpeg"),
                            ("cover.png", "png"), ("cover.webp", "webp")):
            if cname in names:
                self.cover_image = contents[cname]
                self.cover_image_fmt = cfmt
                break

    def _renumber(self):
        """Copertina = 0, capitoli di contenuto = 1,2,3..."""
        n = 1
        for ch in self.chapters:
            if ch.is_cover:
                ch.index = 0
            else:
                ch.index = n
                n += 1

    def save(self, path=None, update_path=True):
        """Scrive il progetto. Se update_path è False, salva nel percorso dato
        (es. autosave) senza modificare self.path/self.title del progetto."""
        if path and update_path:
            self.path = path
            self.title = os.path.splitext(os.path.basename(path))[0]
        dest = path if (path and not update_path) else self.path
        if not dest:
            raise ValueError("Nessun percorso di salvataggio impostato.")
        self._renumber()
        # registra i titoli personalizzati nei metadati prima di scrivere
        titles = {str(ch.index): ch.custom_title
                  for ch in self.chapters if ch.custom_title.strip()}
        if titles:
            self.meta["titles"] = titles
        elif "titles" in self.meta:
            del self.meta["titles"]
        # EN/IT: the temporary file sits next to the destination, so the final
        # step is an atomic rename on the same disk: a crash leaves either
        # the old project or the new one, never half of one.
        # / il file provvisorio sta accanto alla destinazione, così l'ultimo
        # passo è una rinomina atomica sullo stesso disco: un crash lascia il
        # progetto vecchio o quello nuovo, mai una metà.
        fd, tmp = tempfile.mkstemp(
            suffix=".rwr.tmp",
            dir=os.path.dirname(os.path.abspath(dest)) or None)
        os.close(fd)
        try:
            with tarfile.open(tmp, "w:gz") as tar:
                def add(name, data_bytes):
                    info = tarfile.TarInfo(name=name)
                    info.size = len(data_bytes)
                    tar.addfile(info, io.BytesIO(data_bytes))
                if self.meta:
                    add("meta.json",
                        json.dumps(self.meta, ensure_ascii=False, indent=2)
                        .encode("utf-8"))
                for ch in self.chapters:
                    add(ch.text_name, ch.text.encode("utf-8"))
                    add(ch.note_name, ch.note.encode("utf-8"))
                if any(v.strip() for v in self.frontispiece_fields.values()):
                    add("frontispiece.json",
                        json.dumps(self.frontispiece_fields,
                                   ensure_ascii=False, indent=2).encode("utf-8"))
                if any(v.strip() for v in self.colophon_fields.values()):
                    add("colophon.json",
                        json.dumps(self.colophon_fields,
                                   ensure_ascii=False, indent=2).encode("utf-8"))
                # EN: attached chapter images, each as its own archive entry.
                # IT: immagini allegate ai capitoli, una voce d'archivio ciascuna.
                for iname, idata in self.images.items():
                    add(iname, idata)
                if self.cover_image and self.cover_image_fmt:
                    ext = IMAGE_FORMATS.get(self.cover_image_fmt,
                                            ("png",))[0]
                    add(f"cover.{ext}", self.cover_image)
            os.replace(tmp, dest)
        finally:
            if os.path.exists(tmp):
                os.remove(tmp)

    def export_txt(self, path):
        """Concatena i capitoli in un unico file ordinato. La testata iniziale
        (titolo, autore, editore) viene dai CAMPI del frontespizio, non dal
        capitolo-copertina interno; seguono frontespizio, capitoli e colophon.
        L'immagine di copertina non ha senso nel testo semplice ed e' omessa."""
        with open(path, "w", encoding="utf-8") as out:
            wrote = False

            def sep():
                nonlocal wrote
                if wrote:
                    out.write("\n\n")
                wrote = True

            cov = self._cover_lines()
            if cov:
                sep()
                out.write("\n".join(cov))
                out.write("\n")
            front = self._front_paragraphs()
            if front:
                sep()
                out.write("\n".join(front))
                out.write("\n")
            for ch in self.chapters:
                if ch.is_cover:
                    continue
                sep()
                # EN: plain text cannot embed pictures: each attached image
                #     becomes a bracketed line with its caption (or name).
                # IT: il testo semplice non incorpora figure: ogni immagine
                #     allegata diventa una riga tra parentesi con la sua
                #     didascalia (o il nome).
                body = "\n".join(
                    f"[{(m.group('alt') or m.group('src')).strip()}]"
                    if (m := _IMG_LINE_RE.match(ln.strip())) else ln
                    for ln in _tables_to_text(render_math(ch.text)).split("\n"))
                out.write(body.rstrip("\n"))
                out.write("\n")
            colo = self._colophon_paragraphs()
            if colo:
                sep()
                out.write("\n".join(colo))
                out.write("\n")

    # --- helper comuni agli export documentali ----------------------------
    def cover_lines_with_roles(self):
        """Righe della copertina grafica con il loro RUOLO tipografico.

        Restituisce una lista di (testo, ruolo) con ruolo fra "title",
        "subtitle", "author" e "publisher".

        Il ruolo si dichiara, non si indovina. Prima gli export lo deducevano
        dalla posizione — prima riga il titolo, ultima l'editore, il resto
        l'autore — e con DUE sole righe gli intervalli si sovrapponevano: lo
        stesso nome finiva stampato due volte, una come autore e una in coda.
        I campi del frontespizio sanno gia' cos'e' cosa: basta chiederglielo.
        """
        f = getattr(self, "frontispiece_fields", {}) or {}
        voci = []
        for campo, ruolo in (("title", "title"), ("subtitle", "subtitle"),
                             ("author", "author"), ("publisher", "publisher")):
            valore = (f.get(campo) or "").strip()
            if valore:
                voci.append((valore, ruolo))
        if voci:
            return voci

        # Ripiego per i progetti vecchi, dove la copertina era testo libero in
        # un capitolo: li' il ruolo si puo' solo dedurre dalla posizione, ma
        # senza mai usare due volte la stessa riga.
        righe = []
        cover = self.cover()
        if cover is not None:
            for ln in cover.text.splitlines():
                s = _strip_inline_md(ln.lstrip("#").strip()
                                     if ln.strip().startswith("#") else ln).strip()
                if s:
                    righe.append(s)
        if not righe and self.title:
            righe.append(self.title)
        if not righe:
            return []
        voci = [(righe[0], "title")]
        if len(righe) > 2:
            voci += [(r, "author") for r in righe[1:-1]]
            voci.append((righe[-1], "publisher"))
        elif len(righe) == 2:
            voci.append((righe[1], "author"))
        return voci

    def _cover_lines(self):
        """Solo i testi della copertina, nell'ordine. Per chi non ha bisogno
        dei ruoli; chi li vuole usa cover_lines_with_roles()."""
        return [testo for testo, _ruolo in self.cover_lines_with_roles()]

    def _ordered_chapters(self):
        """Capitoli di contenuto (esclusa la copertina) con titolo risolto."""
        out = []
        n = 0
        for ch in self.chapters:
            if ch.is_cover:
                continue
            n += 1
            title = ch.title_with_fallback(
                fallback_template="Capitolo {n}".replace("{n}", str(n)))
            out.append((title, ch.text))
        return out

    # --- sezioni editoriali: helper condivisi dagli export ----------------
    def has_frontispiece(self):
        return any(v.strip() for v in self.frontispiece_fields.values())

    def cover_is_blank(self):
        """True se la copertina esportata deve risultare BIANCA e VUOTA:
        nessuna immagine di copertina E tutti i campi delle Sezioni editoriali
        del frontespizio (titolo, sottotitolo, autore, editore) vuoti.
        In questo caso l'export non disegna la grafica della copertina ne'
        ripiega sul titolo del progetto: la pagina resta completamente bianca."""
        if self.has_cover_image():
            return False
        f = getattr(self, "frontispiece_fields", {}) or {}
        return not any(str(v).strip() for v in f.values())

    def has_colophon(self):
        return any(v.strip() for v in self.colophon_fields.values())

    def _front_lines(self):
        """Frontespizio come lista di righe con stile: (testo, ruolo).
        Ruoli: 'title', 'subtitle', 'author', 'meta'. La formattazione vera
        (font, dimensioni, spaziatura) la decide ogni export in base al ruolo.
        Lista vuota se non c'e' nessun campo."""
        f = self.frontispiece_fields
        lines = []
        if f.get("title", "").strip():
            lines.append((f["title"].strip(), "title"))
        if f.get("subtitle", "").strip():
            # il sottotitolo puo' contenere piu' righe (es. vecchio testo libero)
            for i, ln in enumerate(f["subtitle"].strip().split("\n")):
                if ln.strip():
                    lines.append((ln.strip(), "subtitle"))
        if f.get("author", "").strip():
            lines.append((f["author"].strip(), "author"))
        if f.get("publisher", "").strip():
            lines.append((f["publisher"].strip(), "meta"))
        if f.get("place_year", "").strip():
            lines.append((f["place_year"].strip(), "meta"))
        return lines

    def _colophon_lines(self):
        """Colophon come lista di righe con stile: (testo, ruolo).
        Ruoli: 'copyright', 'small'. Lista vuota se non c'e' nessun campo."""
        c = self.colophon_fields
        lines = []
        if c.get("copyright", "").strip():
            lines.append((c["copyright"].strip(), "copyright"))
        if c.get("publisher", "").strip():
            lines.append((c["publisher"].strip(), "small"))
        if c.get("isbn", "").strip():
            lines.append(("ISBN " + c["isbn"].strip(), "small"))
        if c.get("edition", "").strip():
            lines.append((c["edition"].strip(), "small"))
        if c.get("notes", "").strip():
            for ln in c["notes"].strip().split("\n"):
                if ln.strip():
                    lines.append((ln.strip(), "small"))
        if c.get("license", "").strip():
            lines.append((c["license"].strip(), "small"))
        return lines

    # compatibilita': vecchi nomi usati altrove, ora derivati dai campi
    def _front_paragraphs(self):
        return [t for (t, _r) in self._front_lines()]

    def _colophon_paragraphs(self):
        return [t for (t, _r) in self._colophon_lines()]

    def _cover_image_mime(self):
        """EN: MIME type of the cover image ('image/png' fallback).
        IT: Tipo MIME dell'immagine di copertina (ripiego 'image/png')."""
        return IMAGE_FORMATS.get(self.cover_image_fmt,
                                 (None, "image/png"))[1]

    def _cover_image_data_uri(self):
        """Data URI base64 dell'immagine di copertina, per incorporarla inline
        nell'HTML a file unico. None se non c'e' immagine."""
        if not self.cover_image:
            return None
        import base64
        b64 = base64.b64encode(self.cover_image).decode("ascii")
        return f"data:{self._cover_image_mime()};base64,{b64}"

    def export_markdown(self, path):
        """EN: Export the whole project to a single Markdown file. Title as
        H1, cover as the opening block, each chapter with its own H2 heading
        (unless the text already starts with one). Attached images are copied
        to a sibling '<name>_img/' folder and the ![..](..) references are
        rewritten to point there, so the exported file works anywhere.
        IT: Esporta tutto il progetto in un unico file Markdown. Titolo come
        H1, copertina come blocco iniziale, ogni capitolo con la propria
        intestazione H2 (se il testo non ne ha già una). Le immagini allegate
        vengono copiate in una cartella affiancata '<nome>_img/' e i
        riferimenti ![..](..) riscritti verso di essa, così il file esportato
        funziona ovunque."""
        cover_lines = self._cover_lines()
        title = cover_lines[0] if cover_lines else self.title

        # EN/IT: images folder next to the .md / cartella immagini accanto al .md
        used = self.used_images()
        img_dir_name = os.path.splitext(os.path.basename(path))[0] + "_img"
        if used:
            img_dir = os.path.join(os.path.dirname(path) or ".", img_dir_name)
            os.makedirs(img_dir, exist_ok=True)
            for n in used:
                with open(os.path.join(img_dir, n), "wb") as imgf:
                    imgf.write(self.images[n])

        def rewrite_refs(text):
            # EN: only the internal names get the folder prefix; any other
            #     Markdown image the author wrote is left untouched.
            # IT: solo i nomi interni ricevono il prefisso cartella; ogni
            #     altra immagine Markdown scritta dall'autore resta intatta.
            return "\n".join(
                f"![{m.group('alt')}]({img_dir_name}/{m.group('src')})"
                if (m := _IMG_LINE_RE.match(ln.strip()))
                and m.group("src") in self.images else ln
                for ln in text.split("\n"))

        with open(path, "w", encoding="utf-8") as out:
            out.write(f"# {title}\n\n")
            # autore e data della copertina, in corsivo
            for extra in cover_lines[1:]:
                out.write(f"*{extra}*\n\n")
            out.write("---\n\n")
            # frontespizio (dopo la copertina), se presente
            front = self._front_paragraphs()
            if front:
                for j, ln in enumerate(front):
                    if j == 0:
                        out.write(f"## {ln}\n\n")
                    else:
                        out.write(f"*{ln}*\n\n")
                out.write("---\n\n")
            for ch_title, text in self._ordered_chapters():
                # ogni a capo di RuscaWriter è un paragrafo anche per CommonMark
                body = rewrite_refs(commonmark_paragraphs(text.rstrip("\n")))
                # EN: if the text already opens with a Markdown heading we do
                #     not add a duplicate title.
                # IT: se il testo inizia già con un'intestazione markdown, non
                #     aggiungiamo un titolo doppio.
                first = body.lstrip().split("\n", 1)[0] if body else ""
                if not first.startswith("#"):
                    out.write(f"## {ch_title}\n\n")
                out.write(body)
                out.write("\n\n")
            # colophon in fondo, se presente
            colo = self._colophon_paragraphs()
            if colo:
                out.write("---\n\n")
                for ln in colo:
                    out.write(f"*{ln}*\n\n")

    # EN: table styles for the ODT export, book style like the PDF: thick
    #     rule above the header and below the last row, thin under the header.
    # IT: stili delle tabelle dell'export ODT, in stile libro come il PDF:
    #     filetto spesso sopra l'intestazione e sotto l'ultima riga, sottile
    #     sotto l'intestazione.
    _ODT_TABLE_STYLES = (
        '<style:style style:name="RwTable" style:family="table">'
        '<style:table-properties table:align="margins" table:border-model="collapsing" '
        'fo:margin-top="0.3cm" '
        'fo:margin-bottom="0.3cm"/></style:style>\n'
        '<style:style style:name="RwCellHead" style:family="table-cell">'
        '<style:table-cell-properties fo:padding="0.1cm" '
        'fo:border-top="0.05cm solid #333333" fo:border-bottom="0.02cm solid #333333" '
        'fo:border-left="none" fo:border-right="none"/></style:style>\n'
        '<style:style style:name="RwCell" style:family="table-cell">'
        '<style:table-cell-properties fo:padding="0.1cm" fo:border="none"/></style:style>\n'
        '<style:style style:name="RwCellLast" style:family="table-cell">'
        '<style:table-cell-properties fo:padding="0.1cm" fo:border-top="none" '
        'fo:border-bottom="0.05cm solid #333333" fo:border-left="none" '
        'fo:border-right="none"/></style:style>\n'
        + "".join(
            f'<style:style style:name="RwP{k}{a[0].upper()}" style:family="paragraph">'
            f'<style:paragraph-properties fo:text-align="{ {"left": "start", "right": "end"}.get(a, a)}"/>'
            + ('<style:text-properties fo:font-weight="bold"/>' if k == "H" else "")
            + '</style:style>\n'
            for k in ("H", "B") for a in ("left", "center", "right")))

    def _odt_table(self, content, n):
        """EN: A Markdown table as a native ODT table (editable in Writer).
        IT: Una tabella Markdown come tabella ODT nativa (modificabile in
        Writer)."""
        from xml.sax.saxutils import escape
        aligns, header, rows = content
        ncol = len(header)

        def row(values, cell_style, kind):
            cells = "".join(
                f'<table:table-cell table:style-name="{cell_style}" office:value-type="string">'
                f'<text:p text:style-name="RwP{kind}{a[0].upper()}">{escape(v)}</text:p>'
                '</table:table-cell>' for a, v in zip(aligns, values))
            return f"<table:table-row>{cells}</table:table-row>"
        body_rows = "".join(row(r, "RwCellLast" if k == len(rows) - 1 else "RwCell", "B")
                            for k, r in enumerate(rows))
        return (f'<table:table table:name="Tabella{n}" table:style-name="RwTable">'
                f'<table:table-column table:number-columns-repeated="{ncol}"/>'
                f'<table:table-header-rows>{row(header, "RwCellHead", "H")}'
                f'</table:table-header-rows>{body_rows}</table:table>')

    def _doc_blocks(self, text):
        """EN: Turn a chapter's Markdown into a list of (kind, content)
        blocks shared by the ODT and DOCX exports, from book_blocks. Kinds:
        h1/h2/h3, bullet, quote, p, rule, image (content = (caption,
        internal_name)) and table (content = (alignments, header, rows)).
        Inline formatting is stripped (plain text) to stay simple and robust.
        IT: Trasforma il markdown di un capitolo in una lista di blocchi
        (tipo, contenuto) usata sia da ODT sia da DOCX, a partire da
        book_blocks. Tipi: h1/h2/h3, bullet, quote, p, rule, image
        (contenuto = (didascalia, nome_interno)) e table (contenuto =
        (allineamenti, intestazione, righe)). La formattazione inline viene
        rimossa (testo piano) per restare semplice e robusta."""
        out = []

        def walk(blocks, quote=False):
            para = "quote" if quote else "p"
            for b in blocks:
                kind = b[0]
                if kind == "heading":
                    out.append((f"h{min(3, b[1])}", plain_runs(b[2])))
                elif kind == "p":
                    out.extend((para, plain_runs(line)) for line in b[1])
                elif kind == "list":
                    for _depth, mark, line, inner in list_lines(b):
                        if inner is not None:
                            walk([inner], quote)
                        elif mark:
                            prefix = "" if mark in ("•",) or mark[0].isdigit() else mark + " "
                            out.append(("bullet", prefix + plain_runs(line)))
                        else:
                            out.append((para, plain_runs(line)))
                elif kind == "quote":
                    walk(b[1], True)
                elif kind == "image":
                    # un riferimento rotto (immagine non piu' nel progetto)
                    # non e' una figura: resta un paragrafo con la didascalia
                    if b[2] in self.images:
                        out.append(("image", (b[1], b[2])))
                    else:
                        out.append(("p", b[1]))
                elif kind == "table":
                    out.append(("table", (b[1], [plain_runs(c) for c in b[2]],
                                          [[plain_runs(c) for c in r] for r in b[3]])))
                elif kind == "rule":
                    out.append(("rule", None))
                elif kind == "code":
                    out.extend((para, ln) for ln in b[2].split("\n"))
                elif kind == "math":
                    out.append((para, b[1]))
        walk(book_blocks(text))
        return out

    def _blocks_to_html(self, text, image_html=None):
        """EN: Convert a chapter's Markdown to HTML (list of strings),
        recognizing headings, lists, quotes, attached images and inline
        formatting (bold, italic, code). Used by the HTML and EPUB exports.
        image_html(caption, name) returns the markup for an attached image
        (or None to skip it); the default emits a <figure> whose <img>
        embeds the bytes as a base64 data URI (self-contained single file).
        IT: Converte il markdown di un capitolo in HTML (lista di stringhe),
        riconoscendo titoli, elenchi, citazioni, immagini allegate e
        formattazione inline (grassetto, corsivo, codice). Usato dagli
        export HTML ed EPUB. image_html(didascalia, nome) restituisce il
        markup per un'immagine allegata (o None per ometterla); il default
        emette un <figure> il cui <img> incorpora i byte come data URI
        base64 (file unico autosufficiente)."""
        from xml.sax.saxutils import escape as esc

        def default_image_html(alt, name):
            # EN: one image per <figure>, caption below when present.
            # IT: un'immagine per <figure>, didascalia sotto se presente.
            src = self._image_data_uri(name)
            if not src:
                return None
            cap = f"<figcaption>{esc(alt)}</figcaption>" if alt.strip() else ""
            return (f'<figure class="attached"><img src="{esc(src)}" '
                    f'alt="{esc(alt)}"/>{cap}</figure>')

        figure = image_html or default_image_html

        # marcatura HTML di ogni stile inline riconosciuto dal parser comune
        _WRAP = {
            "bold": ("<strong>", "</strong>"),
            "italic": ("<em>", "</em>"),
            "bolditalic": ("<strong><em>", "</em></strong>"),
            "code": ("<code>", "</code>"),
            "regular": ("", ""),
        }

        def inline(runs):
            return "".join(f"{_WRAP[st][0]}{esc(seg)}{_WRAP[st][1]}" for seg, st in runs)

        def table_html(aligns, header, rows):
            def cells(tag, values):
                out_c = []
                for a, v in zip(aligns, values):
                    style = "" if a == "left" else f' style="text-align:{a}"'
                    out_c.append(f"<{tag}{style}>{inline(v)}</{tag}>")
                return "".join(out_c)
            body_rows = "".join(f"<tr>{cells('td', r)}</tr>" for r in rows)
            return (f"<table><thead><tr>{cells('th', header)}</tr></thead>"
                    f"<tbody>{body_rows}</tbody></table>")

        def lines_html(lines):
            # ogni a capo del testo va a capo anche qui, come nel PDF
            return "<br/>".join(inline(line) for line in lines)

        def blocks_html(blocks, tight=False):
            out = []
            for b in blocks:
                kind = b[0]
                if kind == "heading":
                    out.append(f"<h{b[1]}>{inline(b[2])}</h{b[1]}>")
                elif kind == "p":
                    out.append(lines_html(b[1]) if tight else f"<p>{lines_html(b[1])}</p>")
                elif kind == "list":
                    _k, ordered, start, items = b
                    tag = "ol" if ordered else "ul"
                    attr = f' start="{start}"' if ordered and start != 1 else ""
                    lis = []
                    for task, sub in items:
                        box = ("☑ " if task else "☐ ") if task is not None else ""
                        lis.append(f"<li>{box}{''.join(blocks_html(sub, tight=True))}</li>")
                    out.append(f"<{tag}{attr}>" + "".join(lis) + f"</{tag}>")
                elif kind == "quote":
                    out.append("<blockquote>" + "".join(blocks_html(b[1])) + "</blockquote>")
                elif kind == "image":
                    # immagine allegata; se il riferimento e' rotto (immagine
                    # assente dal progetto) ripiega sulla sola didascalia
                    fig = figure(b[1], b[2]) if b[2] in self.images else None
                    out.append(fig if fig else f"<p><em>{esc(b[1])}</em></p>")
                elif kind == "table":
                    out.append(table_html(b[1], b[2], b[3]))
                elif kind == "rule":
                    out.append("<hr/>")
                elif kind == "code":
                    out.append(f"<pre><code>{esc(b[2])}</code></pre>")
                elif kind == "math":
                    out.append(f'<p class="math">{esc(b[1])}</p>')
            return out

        return blocks_html(book_blocks(text))

    # foglio di stile condiviso dalle pagine HTML esportate
    _HTML_CSS = (
        "body{font-family:'EB Garamond',Georgia,'Times New Roman',serif;line-height:1.6;"
        "max-width:42em;margin:2em auto;padding:0 1em;color:#222;}"
        "h1,h2,h3{font-family:'Helvetica Neue',Arial,sans-serif;color:#5C2A55;}"
        "h1.title{text-align:center;border-bottom:2px solid #8E4585;"
        "padding-bottom:0.3em;}"
        ".cover{text-align:center;margin:3em 0;}"
        ".cover .author{font-size:1.1em;color:#555;}"
        ".cover .date{font-style:italic;color:#777;}"
        ".cover-image{text-align:center;margin:0 0 2em 0;}"
        ".cover-image img{max-width:100%;height:auto;}"
        # EN/IT: attached chapter images / immagini allegate ai capitoli
        "figure.attached{text-align:center;margin:2em 0;}"
        "figure.attached img{max-width:100%;height:auto;}"
        "figure.attached figcaption{font-style:italic;color:#666;"
        "font-size:0.9em;margin-top:0.5em;}"
        ".frontispiece{text-align:center;margin:3em 0;}"
        ".frontispiece .ftitle{font-size:1.6em;font-weight:bold;color:#5C2A55;}"
        ".colophon{margin-top:3em;border-top:1px solid #d9b8d4;padding-top:1em;"
        "font-size:0.9em;color:#555;text-align:center;}"
        "blockquote{border-left:3px solid #8E4585;margin-left:0;padding-left:1em;"
        "font-style:italic;color:#444;}"
        "nav.toc{background:#f6eef4;border:1px solid #d9b8d4;border-radius:6px;"
        "padding:1em 1.5em;}"
        "nav.toc a{color:#5C2A55;text-decoration:none;}"
        "nav.toc a:hover{text-decoration:underline;}"
        "code{background:#f0e6ee;padding:0 0.2em;border-radius:3px;}"
        # EN/IT: tables in book style / tabelle in stile libro
        "table{border-collapse:collapse;width:100%;margin:1.5em 0;font-size:0.95em;"
        "border-top:2px solid #333;border-bottom:2px solid #333;}"
        "th,td{padding:0.35em 0.6em;text-align:left;vertical-align:top;}"
        "thead th{border-bottom:1px solid #333;}"
        "hr{border:none;border-top:1px solid #888;width:30%;margin:1.5em auto;}"
        ".chapter-nav{margin-top:3em;border-top:1px solid #d9b8d4;"
        "padding-top:1em;font-size:0.9em;}"
    )

    def export_html(self, path, multifile=False):
        """Esporta in HTML.

        - multifile=False: un unico file .html con copertina, indice interno
          (link agli #ancore) e tutti i capitoli in sequenza.
        - multifile=True: crea una cartella accanto a 'path' con un index.html
          (copertina + indice) e un file per ogni capitolo, collegati tra loro.
        """
        from xml.sax.saxutils import escape as esc

        cover_lines = self._cover_lines()
        title = cover_lines[0] if cover_lines else self.title
        chapters = self._ordered_chapters()

        def page(title_txt, body_html):
            return (
                "<!DOCTYPE html>\n<html lang=\"it\">\n<head>\n"
                "<meta charset=\"utf-8\"/>\n"
                "<meta name=\"viewport\" content=\"width=device-width, "
                "initial-scale=1\"/>\n"
                f"<title>{esc(title_txt)}</title>\n"
                f"<style>{self._HTML_CSS}</style>\n</head>\n<body>\n"
                + body_html +
                "\n</body>\n</html>\n")

        def cover_html(image_src=None):
            h = ['<div class="cover">']
            if image_src:
                # con immagine di copertina: mostra l'immagine a piena larghezza
                h.append(f'<div class="cover-image"><img src="{esc(image_src)}" '
                         f'alt="{esc(title)}"/></div>')
            elif self.cover_is_blank():
                # campi Sezioni editoriali vuoti e nessuna immagine:
                # copertina bianca e vuota
                pass
            else:
                # ogni riga sa gia' che ruolo ha: nessuna deduzione
                h.append(f'<h1 class="title">{esc(title)}</h1>')
                for testo, ruolo in self.cover_lines_with_roles():
                    if ruolo in ("subtitle", "author"):
                        h.append(f'<p class="author">{esc(testo)}</p>')
                    elif ruolo == "publisher":
                        h.append(f'<p class="date">{esc(testo)}</p>')
            h.append('</div>')
            return "\n".join(h)

        def frontispiece_html():
            front = self._front_paragraphs()
            if not front:
                return ""
            h = ['<div class="frontispiece">']
            for j, ln in enumerate(front):
                cls = "ftitle" if j == 0 else "fline"
                h.append(f'<p class="{cls}">{esc(ln)}</p>')
            h.append('</div>')
            return "\n".join(h)

        def colophon_html():
            colo = self._colophon_paragraphs()
            if not colo:
                return ""
            h = ['<div class="colophon">']
            for ln in colo:
                h.append(f'<p>{esc(ln)}</p>')
            h.append('</div>')
            return "\n".join(h)

        if not multifile:
            # ---- file unico ----
            data_uri = self._cover_image_data_uri()
            parts = [cover_html(data_uri)]
            fr = frontispiece_html()
            if fr:
                parts.append(fr)
            # indice con ancore interne
            toc = ['<nav class="toc"><h2>' + esc(self.t_index_label())
                   + '</h2><ol>']
            for n, (ct, _t) in enumerate(chapters, 1):
                toc.append(f'<li><a href="#cap{n}">{esc(ct)}</a></li>')
            toc.append('</ol></nav>')
            parts.append("\n".join(toc))
            # capitoli
            for n, (ct, text) in enumerate(chapters, 1):
                parts.append(f'<section id="cap{n}">')
                blocks = self._blocks_to_html(text)
                starts_h = bool(blocks) and blocks[0].startswith("<h")
                if not starts_h:
                    parts.append(f"<h2>{esc(ct)}</h2>")
                parts.extend(blocks)
                parts.append('</section>')
            colo = colophon_html()
            if colo:
                parts.append(colo)
            with open(path, "w", encoding="utf-8") as f:
                f.write(page(title, "\n".join(parts)))
            return path

        # ---- multifile: una cartella con index + un file per capitolo ----
        base = os.path.splitext(path)[0]            # toglie .html se presente
        folder = base                                # la cartella di output
        os.makedirs(folder, exist_ok=True)

        filenames = [f"cap{n:02d}.html" for n in range(1, len(chapters) + 1)]

        # salva l'immagine di copertina come file nella cartella, se presente
        cover_src = None
        if self.cover_image:
            ext = IMAGE_FORMATS.get(self.cover_image_fmt, ("png",))[0]
            cover_name = f"cover.{ext}"
            with open(os.path.join(folder, cover_name), "wb") as imgf:
                imgf.write(self.cover_image)
            cover_src = cover_name

        # index.html: copertina + frontespizio + indice con link ai file
        idx = [cover_html(cover_src)]
        fr = frontispiece_html()
        if fr:
            idx.append(fr)
        idx.append('<nav class="toc"><h2>'
                   + esc(self.t_index_label()) + '</h2><ol>')
        for fn, (ct, _t) in zip(filenames, chapters):
            idx.append(f'<li><a href="{fn}">{esc(ct)}</a></li>')
        idx.append('</ol></nav>')
        colo = colophon_html()
        if colo:
            idx.append(colo)
        with open(os.path.join(folder, "index.html"), "w", encoding="utf-8") as f:
            f.write(page(title, "\n".join(idx)))

        # un file per capitolo, con navigazione avanti/indietro
        for i, (fn, (ct, text)) in enumerate(zip(filenames, chapters)):
            body = []
            blocks = self._blocks_to_html(text)
            starts_h = bool(blocks) and blocks[0].startswith("<h")
            if not starts_h:
                body.append(f"<h2>{esc(ct)}</h2>")
            body.extend(blocks)
            # barra di navigazione tra capitoli
            nav = ['<div class="chapter-nav">']
            if i > 0:
                nav.append(f'<a href="{filenames[i-1]}">&larr; precedente</a> · ')
            nav.append('<a href="index.html">indice</a>')
            if i < len(filenames) - 1:
                nav.append(f' · <a href="{filenames[i+1]}">successivo &rarr;</a>')
            nav.append('</div>')
            body.append("\n".join(nav))
            with open(os.path.join(folder, fn), "w", encoding="utf-8") as f:
                f.write(page(ct, "\n".join(body)))
        return folder

    def _page_setup_mm(self, page_size, margins):
        """EN/IT: (width, height, margins) in mm for the office exports, or
        None when no page format was asked for / (larghezza, altezza,
        margini) in mm per gli export d'ufficio, o None se non e' stato
        chiesto un formato."""
        if page_size is None:
            return None
        if page_size not in PDF_PAGE_SIZES:
            page_size = PDF_DEFAULT_PAGE_SIZE
        w, h = page_size_mm(page_size)
        m = (self.page_margins(page_size) if margins is None
             else normalize_page_margins(margins, page_size))
        return w, h, m

    @staticmethod
    def _fit_cm(w_cm, h_cm, setup):
        """EN/IT: shrink an image (cm) so it fits the text block of the page
        setup, keeping its proportions / riduce un'immagine (cm) perche'
        entri nella gabbia del formato scelto, mantenendo le proporzioni."""
        if not setup or w_cm <= 0 or h_cm <= 0:
            return w_cm, h_cm
        pw, ph, m = setup
        bw = (pw - m["inner"] - m["outer"] - m["gutter"]) / 10.0
        bh = (ph - m["top"] - m["bottom"]) / 10.0 * 0.9   # spazio per la didascalia
        k = min(1.0, bw / w_cm, bh / h_cm)
        return w_cm * k, h_cm * k

    def export_odt(self, path, page_size=None, margins=None):
        """Esporta in OpenDocument Text (.odt) usando solo la libreria standard.
        Un .odt è un archivio ZIP con dentro dei file XML; lo costruiamo a mano,
        come facciamo per l'EPUB.

        page_size/margins: se indicati, il documento porta il formato e i
        margini di pagina (pagine speculari comprese), cosi' LibreOffice lo
        apre gia' impaginato come il PDF."""
        import zipfile
        from xml.sax.saxutils import escape

        cover_lines = self._cover_lines()
        title = cover_lines[0] if cover_lines else self.title
        setup = self._page_setup_mm(page_size, margins)

        # corpo del documento in formato Open Document
        body = []
        # EN: every picture shipped in the archive: (zip path, MIME, bytes).
        #     Holds the cover (if any) plus the attached chapter images.
        # IT: tutte le immagini incluse nell'archivio: (percorso zip, MIME,
        #     byte). Contiene la copertina (se c'e') e le immagini allegate.
        img_entries = []
        # immagine di copertina (se presente) come frame a piena larghezza
        if self.cover_image:
            ext = IMAGE_FORMATS.get(self.cover_image_fmt, ("png",))[0]
            img_path = f"Pictures/cover.{ext}"
            img_entries.append((img_path, self._cover_image_mime(),
                                self.cover_image))
            # dimensioni in cm: stima per stare nella pagina (~16cm larghezza)
            from_w, from_h = 16.0, 22.0
            try:
                from PIL import Image as _PILImage
                import io as _io
                _im = _PILImage.open(_io.BytesIO(self.cover_image))
                iw, ih = _im.size
                from_h = min(24.0, 16.0 * ih / iw)
            except Exception:
                pass
            from_w, from_h = self._fit_cm(from_w, from_h, setup)
            body.append(
                '<text:p text:style-name="Author">'
                f'<draw:frame draw:name="cover" text:anchor-type="paragraph" '
                f'svg:width="{from_w:.2f}cm" svg:height="{from_h:.2f}cm" '
                f'draw:z-index="0">'
                f'<draw:image xlink:href="{img_path}" '
                f'xlink:type="simple" xlink:show="embed" '
                f'xlink:actuate="onLoad"/></draw:frame></text:p>')
        else:
            # copertina testuale: titolo grande e dati centrati
            body.append(f'<text:h text:style-name="Title" '
                        f'text:outline-level="1">{escape(title)}</text:h>')
            for extra in cover_lines[1:]:
                body.append(f'<text:p text:style-name="Author">{escape(extra)}</text:p>')
        # frontespizio (dopo la copertina)
        for j, ln in enumerate(self._front_paragraphs()):
            style = "Title" if j == 0 else "Author"
            body.append(f'<text:p text:style-name="{style}">{escape(ln)}</text:p>')
        for ch_title, text in self._ordered_chapters():
            body_blocks = self._doc_blocks(text)
            # se il capitolo inizia gia' con un'intestazione, non duplicare
            starts_with_heading = bool(body_blocks) and body_blocks[0][0].startswith("h")
            if not starts_with_heading:
                body.append(f'<text:h text:style-name="Heading_20_1" '
                            f'text:outline-level="1">{escape(ch_title)}</text:h>')
            for kind, content in body_blocks:
                if kind == "image":
                    # EN: attached image as a centered frame + italic caption.
                    #     Width fits the page (max 14 cm), height keeps the
                    #     aspect ratio read from the file itself.
                    # IT: immagine allegata come cornice centrata + didascalia
                    #     in corsivo. Larghezza entro la pagina (max 14 cm),
                    #     altezza con le proporzioni lette dal file stesso.
                    alt, iname = content
                    data = self.images[iname]
                    dims = image_dimensions(data) or (1400, 1000)
                    w_cm = 14.0
                    h_cm = min(20.0, w_cm * dims[1] / dims[0])
                    w_cm, h_cm = self._fit_cm(w_cm, h_cm, setup)
                    ipath = f"Pictures/{iname}"
                    img_entries.append((ipath, self.image_mime(iname), data))
                    body.append(
                        '<text:p text:style-name="Author">'
                        f'<draw:frame draw:name="{iname}" '
                        'text:anchor-type="as-char" '
                        f'svg:width="{w_cm:.2f}cm" svg:height="{h_cm:.2f}cm" '
                        'draw:z-index="0">'
                        f'<draw:image xlink:href="{ipath}" '
                        'xlink:type="simple" xlink:show="embed" '
                        'xlink:actuate="onLoad"/></draw:frame></text:p>')
                    if alt.strip():
                        body.append(f'<text:p text:style-name="Caption">'
                                    f'{escape(alt)}</text:p>')
                    continue
                if kind == "table":
                    body.append(self._odt_table(content, len(body)))
                    continue
                if kind == "rule":
                    body.append('<text:p text:style-name="RwPBC">*   *   *</text:p>')
                    continue
                c = escape(content)
                if kind.startswith("h"):
                    lvl = kind[1]
                    body.append(f'<text:h text:style-name="Heading_20_{lvl}" '
                                f'text:outline-level="{lvl}">{c}</text:h>')
                elif kind == "bullet":
                    body.append('<text:list text:style-name="L1"><text:list-item>'
                                f'<text:p text:style-name="Standard">{c}</text:p>'
                                '</text:list-item></text:list>')
                elif kind == "quote":
                    body.append(f'<text:p text:style-name="Quote">{c}</text:p>')
                else:
                    body.append(f'<text:p text:style-name="Standard">{c}</text:p>')

        # colophon in fondo, se presente
        for ln in self._colophon_paragraphs():
            body.append(f'<text:p text:style-name="Author">{escape(ln)}</text:p>')

        content_xml = (
            '<?xml version="1.0" encoding="UTF-8"?>\n'
            '<office:document-content '
            'xmlns:office="urn:oasis:names:tc:opendocument:xmlns:office:1.0" '
            'xmlns:text="urn:oasis:names:tc:opendocument:xmlns:text:1.0" '
            'xmlns:style="urn:oasis:names:tc:opendocument:xmlns:style:1.0" '
            'xmlns:fo="urn:oasis:names:tc:opendocument:xmlns:xsl-fo-compatible:1.0" '
            'xmlns:draw="urn:oasis:names:tc:opendocument:xmlns:drawing:1.0" '
            'xmlns:svg="urn:oasis:names:tc:opendocument:xmlns:svg-compatible:1.0" '
            'xmlns:xlink="http://www.w3.org/1999/xlink" '
            'xmlns:table="urn:oasis:names:tc:opendocument:xmlns:table:1.0" '
            'office:version="1.2">\n'
            '<office:automatic-styles>\n'
            + self._ODT_TABLE_STYLES +
            '<style:style style:name="Title" style:family="paragraph">'
            '<style:paragraph-properties fo:text-align="center"/>'
            '<style:text-properties fo:font-size="24pt" fo:font-weight="bold" '
            'fo:color="#5C2A55"/></style:style>\n'
            '<style:style style:name="Author" style:family="paragraph">'
            '<style:paragraph-properties fo:text-align="center"/>'
            '<style:text-properties fo:font-size="13pt"/></style:style>\n'
            '<style:style style:name="Quote" style:family="paragraph">'
            '<style:paragraph-properties fo:margin-left="1cm"/>'
            '<style:text-properties fo:font-style="italic"/></style:style>\n'
            '<style:style style:name="Caption" style:family="paragraph">'
            '<style:paragraph-properties fo:text-align="center"/>'
            '<style:text-properties fo:font-size="10pt" fo:font-style="italic"/></style:style>\n'
            '</office:automatic-styles>\n'
            '<office:body><office:text>\n'
            + "\n".join(body) +
            '\n</office:text></office:body>\n'
            '</office:document-content>\n')

        # EN/IT: page format and margins / formato e margini di pagina.
        # ODF names the margins left/right; with page-usage "mirrored" the
        # left one is the INNER one on right-hand pages, as in a book.
        odt_page = ""
        if setup:
            pw, ph, m = setup
            uso = "mirrored" if m["mirror"] else "all"
            odt_page = (
                '<office:automatic-styles>'
                f'<style:page-layout style:name="pm1" style:page-usage="{uso}">'
                f'<style:page-layout-properties fo:page-width="{pw:.1f}mm" '
                f'fo:page-height="{ph:.1f}mm" '
                f'fo:margin-top="{m["top"]:.1f}mm" '
                f'fo:margin-bottom="{m["bottom"]:.1f}mm" '
                f'fo:margin-left="{m["inner"] + m["gutter"]:.1f}mm" '
                f'fo:margin-right="{m["outer"]:.1f}mm" '
                'style:print-orientation="portrait"/>'
                '</style:page-layout></office:automatic-styles>'
                '<office:master-styles>'
                '<style:master-page style:name="Standard" '
                'style:page-layout-name="pm1"/>'
                '</office:master-styles>')
        styles_xml = (
            '<?xml version="1.0" encoding="UTF-8"?>\n'
            '<office:document-styles '
            'xmlns:office="urn:oasis:names:tc:opendocument:xmlns:office:1.0" '
            'xmlns:style="urn:oasis:names:tc:opendocument:xmlns:style:1.0" '
            'xmlns:fo="urn:oasis:names:tc:opendocument:xmlns:xsl-fo-compatible:1.0" '
            'office:version="1.2"><office:styles>\n'
            '<style:style style:name="Standard" style:family="paragraph"/>\n'
            '<style:style style:name="Heading_20_1" style:family="paragraph" '
            'style:display-name="Heading 1">'
            '<style:text-properties fo:font-size="18pt" fo:font-weight="bold" '
            'fo:color="#5C2A55"/></style:style>\n'
            '<style:style style:name="Heading_20_2" style:family="paragraph" '
            'style:display-name="Heading 2">'
            '<style:text-properties fo:font-size="15pt" fo:font-weight="bold"/>'
            '</style:style>\n'
            '<style:style style:name="Heading_20_3" style:family="paragraph" '
            'style:display-name="Heading 3">'
            '<style:text-properties fo:font-size="13pt" fo:font-weight="bold"/>'
            '</style:style>\n'
            '</office:styles>' + odt_page + '</office:document-styles>\n')

        # EN/IT: one manifest entry per picture / una voce per immagine
        img_manifest = "".join(
            f'<manifest:file-entry manifest:full-path="{ipath}" '
            f'manifest:media-type="{imime}"/>\n'
            for (ipath, imime, _d) in img_entries)
        manifest = (
            '<?xml version="1.0" encoding="UTF-8"?>\n'
            '<manifest:manifest '
            'xmlns:manifest="urn:oasis:names:tc:opendocument:xmlns:manifest:1.0" '
            'manifest:version="1.2">\n'
            '<manifest:file-entry manifest:full-path="/" '
            'manifest:media-type="application/vnd.oasis.opendocument.text"/>\n'
            '<manifest:file-entry manifest:full-path="content.xml" '
            'manifest:media-type="text/xml"/>\n'
            '<manifest:file-entry manifest:full-path="styles.xml" '
            'manifest:media-type="text/xml"/>\n'
            + img_manifest +
            '</manifest:manifest>\n')

        with zipfile.ZipFile(path, "w") as z:
            # come per l'EPUB, il mimetype va per primo e non compresso
            z.writestr("mimetype", "application/vnd.oasis.opendocument.text",
                       compress_type=zipfile.ZIP_STORED)
            z.writestr("content.xml", content_xml, zipfile.ZIP_DEFLATED)
            z.writestr("styles.xml", styles_xml, zipfile.ZIP_DEFLATED)
            z.writestr("META-INF/manifest.xml", manifest, zipfile.ZIP_DEFLATED)
            for (ipath, _m, idata) in img_entries:
                z.writestr(ipath, idata, zipfile.ZIP_STORED)

    def export_docx(self, path, page_size=None, margins=None):
        """Esporta in Word (.docx) usando solo la libreria standard.
        Anche il .docx è un archivio ZIP con XML (Office Open XML).

        page_size/margins: se indicati, il documento porta formato, margini,
        rilegatura e pagine speculari; altrimenti resta A4 con 2,54 cm."""
        import zipfile
        from xml.sax.saxutils import escape

        setup = self._page_setup_mm(page_size, margins)
        cover_lines = self._cover_lines()
        title = cover_lines[0] if cover_lines else self.title

        def para(text, style=None, bold=False, size=None, align=None,
                 color=None):
            ppr = []
            if style:
                ppr.append(f'<w:pStyle w:val="{style}"/>')
            if align:
                ppr.append(f'<w:jc w:val="{align}"/>')
            ppr_xml = f'<w:pPr>{"".join(ppr)}</w:pPr>' if ppr else ""
            rpr = []
            if bold:
                rpr.append('<w:b/>')
            if size:
                rpr.append(f'<w:sz w:val="{size*2}"/>')  # half-points
            if color:
                rpr.append(f'<w:color w:val="{color}"/>')
            rpr_xml = f'<w:rPr>{"".join(rpr)}</w:rPr>' if rpr else ""
            return (f'<w:p>{ppr_xml}<w:r>{rpr_xml}'
                    f'<w:t xml:space="preserve">{escape(text)}</w:t></w:r></w:p>')

        def docx_table(content):
            """EN: A Markdown table as a native Word table, book style:
            thick rules above and below, thin under the header row (which
            repeats on every page).
            IT: Una tabella Markdown come tabella Word nativa, in stile
            libro: filetti spessi sopra e sotto, sottile sotto la riga di
            intestazione (che si ripete a ogni pagina)."""
            aligns, header, rows = content
            ncol = len(header)
            rule = '<w:{0} w:val="single" w:sz="{1}" w:space="0" w:color="333333"/>'

            def cell(text, align, bold, bottom=None):
                tcpr = (f'<w:tcPr><w:tcBorders>{rule.format("bottom", bottom)}'
                        '</w:tcBorders></w:tcPr>' if bottom else "")
                rpr = "<w:rPr><w:b/></w:rPr>" if bold else ""
                return (f'<w:tc>{tcpr}<w:p><w:pPr><w:jc w:val="{align}"/></w:pPr>'
                        f'<w:r>{rpr}<w:t xml:space="preserve">{escape(text)}</w:t></w:r>'
                        '</w:p></w:tc>')
            head = ('<w:tr><w:trPr><w:tblHeader/></w:trPr>'
                    + "".join(cell(v, a, True, 6) for a, v in zip(aligns, header))
                    + "</w:tr>")
            body_rows = "".join(
                "<w:tr>" + "".join(cell(v, a, False) for a, v in zip(aligns, r)) + "</w:tr>"
                for r in rows)
            grid = "".join(f'<w:gridCol w:w="{9000 // ncol}"/>' for _ in range(ncol))
            return ('<w:tbl><w:tblPr><w:tblW w:w="5000" w:type="pct"/>'
                    f'<w:tblBorders>{rule.format("top", 12)}{rule.format("bottom", 12)}'
                    '</w:tblBorders><w:tblCellMar><w:top w:w="40" w:type="dxa"/>'
                    '<w:left w:w="100" w:type="dxa"/><w:bottom w:w="40" w:type="dxa"/>'
                    '<w:right w:w="100" w:type="dxa"/></w:tblCellMar></w:tblPr>'
                    f'<w:tblGrid>{grid}</w:tblGrid>{head}{body_rows}</w:tbl>'
                    + para(""))

        # EN: pictures shipped inside word/media/: (relationship id,
        #     file name, bytes). Word cannot display WebP, so WebP data is
        #     converted to JPEG with Pillow when possible; if the conversion
        #     is unavailable the image is skipped (caption only).
        # IT: immagini incluse in word/media/: (id relazione, nome file,
        #     byte). Word non visualizza il WebP, quindi i dati WebP vengono
        #     convertiti in JPEG con Pillow quando possibile; se la
        #     conversione non e' disponibile l'immagine viene omessa (resta
        #     la didascalia).
        media = []
        CM = 360000       # EN/IT: 1 cm in EMU / 1 cm in EMU (unita' di Word)

        def docx_ready(data, fmt):
            """EN: (bytes, ext, w_px, h_px) suitable for Word, or None.
            IT: (byte, estensione, larg_px, alt_px) adatti a Word, o None."""
            fmt = fmt or image_format(data)
            if fmt in ("png", "jpeg"):
                dims = image_dimensions(data, fmt) or (1600, 1000)
                return data, IMAGE_FORMATS[fmt][0], dims[0], dims[1]
            jpg = _image_to_jpeg(data, fmt)     # WebP -> JPEG (con Pillow)
            if jpg:
                return jpg[0], "jpg", jpg[1], jpg[2]
            return None

        def drawing(rid, name, w_emu, h_emu, num):
            """EN: minimal Office Open XML inline picture block.
            IT: blocco minimo Office Open XML per un'immagine inline."""
            return (
                '<w:p><w:pPr><w:jc w:val="center"/></w:pPr><w:r><w:drawing>'
                f'<wp:inline distT="0" distB="0" distL="0" distR="0">'
                f'<wp:extent cx="{w_emu}" cy="{h_emu}"/>'
                f'<wp:docPr id="{num}" name="{name}"/>'
                '<a:graphic xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main">'
                '<a:graphicData uri="http://schemas.openxmlformats.org/drawingml/2006/picture">'
                '<pic:pic xmlns:pic="http://schemas.openxmlformats.org/drawingml/2006/picture">'
                f'<pic:nvPicPr><pic:cNvPr id="{num}" name="{name}"/><pic:cNvPicPr/></pic:nvPicPr>'
                f'<pic:blipFill><a:blip r:embed="{rid}" '
                'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"/>'
                '<a:stretch><a:fillRect/></a:stretch></pic:blipFill>'
                '<pic:spPr><a:xfrm><a:off x="0" y="0"/>'
                f'<a:ext cx="{w_emu}" cy="{h_emu}"/></a:xfrm>'
                '<a:prstGeom prst="rect"><a:avLst/></a:prstGeom></pic:spPr>'
                '</pic:pic></a:graphicData></a:graphic></wp:inline></w:drawing></w:r></w:p>')

        def add_picture(data, fmt, base_name, max_w_cm=16.0, max_h_cm=24.0):
            """EN: register a picture and return its <w:drawing> paragraph,
            or None when the image cannot be embedded.
            IT: registra un'immagine e restituisce il suo paragrafo
            <w:drawing>, o None quando non puo' essere incorporata."""
            ready = docx_ready(data, fmt)
            if not ready:
                return None
            bts, ext, iw, ih = ready
            num = len(media) + 1
            rid = f"rIdImg{num}"
            fname = f"{base_name}.{ext}"
            media.append((rid, fname, bts))
            w_cm = max_w_cm
            h_cm = min(max_h_cm, w_cm * ih / iw)
            w_cm, h_cm = self._fit_cm(w_cm, h_cm, setup)
            return drawing(rid, base_name, int(w_cm * CM), int(h_cm * CM), num)

        # immagine di copertina (se presente) come primo paragrafo
        cover_drawing = None
        if self.cover_image:
            cover_drawing = add_picture(self.cover_image,
                                        self.cover_image_fmt, "cover")

        paras = []
        # copertina: immagine se presente, altrimenti testo
        if cover_drawing:
            paras.append(cover_drawing)
        else:
            paras.append(para(title, bold=True, size=24, align="center",
                              color="5C2A55"))
            for extra in cover_lines[1:]:
                paras.append(para(extra, size=13, align="center"))
        paras.append(para(""))   # spazio
        # frontespizio (dopo la copertina)
        front = self._front_paragraphs()
        for j, ln in enumerate(front):
            if j == 0:
                paras.append(para(ln, bold=True, size=20, align="center",
                                  color="5C2A55"))
            else:
                paras.append(para(ln, size=13, align="center"))
        if front:
            paras.append(para(""))
        # capitoli
        for ch_title, text in self._ordered_chapters():
            body_blocks = self._doc_blocks(text)
            starts_with_heading = bool(body_blocks) and body_blocks[0][0].startswith("h")
            if not starts_with_heading:
                paras.append(para(ch_title, bold=True, size=18, color="5C2A55"))
            for kind, content in body_blocks:
                if kind == "image":
                    # EN: attached image + optional italic caption below.
                    # IT: immagine allegata + eventuale didascalia in corsivo.
                    alt, iname = content
                    d = add_picture(self.images[iname], None,
                                    os.path.splitext(iname)[0],
                                    max_w_cm=14.0, max_h_cm=20.0)
                    if d:
                        paras.append(d)
                    if alt.strip():
                        paras.append(para(alt, size=10, align="center",
                                          color="666666"))
                    continue
                if kind == "table":
                    paras.append(docx_table(content))
                    continue
                if kind == "rule":
                    paras.append(para("*   *   *", align="center"))
                    continue
                if kind == "h1":
                    paras.append(para(content, bold=True, size=18, color="5C2A55"))
                elif kind == "h2":
                    paras.append(para(content, bold=True, size=15))
                elif kind == "h3":
                    paras.append(para(content, bold=True, size=13))
                elif kind == "bullet":
                    paras.append(para("• " + content))
                elif kind == "quote":
                    paras.append(para(content, style="Quote"))
                else:
                    paras.append(para(content))

        # colophon in fondo, se presente
        colo = self._colophon_paragraphs()
        if colo:
            paras.append(para(""))
            for ln in colo:
                paras.append(para(ln, size=11, align="center", color="555555"))

        # EN/IT: page format and margins, in twentieths of a point (twips).
        # With <w:mirrorMargins/> Word reads left/right as inside/outside,
        # and w:gutter is added on the binding side.
        # / formato e margini, in ventesimi di punto (twip). Con
        # <w:mirrorMargins/> Word legge sinistro/destro come interno/esterno,
        # e w:gutter si aggiunge dal lato della rilegatura.
        mirror_docx = False
        if setup:
            pw, ph, m = setup

            def tw(mm):
                return int(round(mm * PT_PER_MM * 20))
            mirror_docx = bool(m["mirror"])
            sect_pr = (
                f'<w:sectPr><w:pgSz w:w="{tw(pw)}" w:h="{tw(ph)}"/>'
                f'<w:pgMar w:top="{tw(m["top"])}" w:right="{tw(m["outer"])}" '
                f'w:bottom="{tw(m["bottom"])}" w:left="{tw(m["inner"])}" '
                f'w:header="{tw(min(12.5, m["top"] / 2))}" '
                f'w:footer="{tw(min(12.5, m["bottom"] / 2))}" '
                f'w:gutter="{tw(m["gutter"])}"/></w:sectPr>')
        else:
            sect_pr = ('<w:sectPr><w:pgSz w:w="11906" w:h="16838"/>'
                       '<w:pgMar w:top="1440" w:right="1440" w:bottom="1440" '
                       'w:left="1440"/></w:sectPr>')
        settings_xml = (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
            '<w:settings xmlns:w="http://schemas.openxmlformats.org/'
            'wordprocessingml/2006/main"><w:mirrorMargins/></w:settings>'
        ) if mirror_docx else None

        document = (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
            '<w:document '
            'xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main" '
            'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships" '
            'xmlns:wp="http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing">'
            '<w:body>'
            + "".join(paras) + sect_pr +
            '</w:body></w:document>')

        # EN: declare the MIME type once per extension actually used.
        # IT: dichiara il tipo MIME una volta per estensione davvero usata.
        exts = {fname.rsplit(".", 1)[1] for (_r, fname, _b) in media}
        img_ct = ""
        if "jpg" in exts:
            img_ct += ('<Default Extension="jpg" ContentType="image/jpeg"/>'
                       '<Default Extension="jpeg" ContentType="image/jpeg"/>')
        if "png" in exts:
            img_ct += '<Default Extension="png" ContentType="image/png"/>'
        content_types = (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
            '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
            '<Default Extension="rels" '
            'ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
            '<Default Extension="xml" ContentType="application/xml"/>'
            + img_ct +
            '<Override PartName="/word/document.xml" '
            'ContentType="application/vnd.openxmlformats-officedocument.'
            'wordprocessingml.document.main+xml"/>'
            + ('<Override PartName="/word/settings.xml" '
               'ContentType="application/vnd.openxmlformats-officedocument.'
               'wordprocessingml.settings+xml"/>' if settings_xml else '') +
            '</Types>')

        rels = (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
            '<Relationships '
            'xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            '<Relationship Id="rId1" '
            'Type="http://schemas.openxmlformats.org/officeDocument/2006/'
            'relationships/officeDocument" Target="word/document.xml"/>'
            '</Relationships>')

        # EN: document relationships: one entry per embedded picture.
        # IT: relazioni del documento: una voce per ogni immagine incorporata.
        doc_rels = None
        if media or settings_xml:
            rel_items = "".join(
                f'<Relationship Id="{rid}" '
                'Type="http://schemas.openxmlformats.org/officeDocument/2006/'
                f'relationships/image" Target="media/{fname}"/>'
                for (rid, fname, _b) in media)
            if settings_xml:
                rel_items += (
                    '<Relationship Id="rIdSettings" '
                    'Type="http://schemas.openxmlformats.org/officeDocument/'
                    '2006/relationships/settings" Target="settings.xml"/>')
            doc_rels = (
                '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
                '<Relationships '
                'xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
                + rel_items + '</Relationships>')

        with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
            z.writestr("[Content_Types].xml", content_types)
            z.writestr("_rels/.rels", rels)
            z.writestr("word/document.xml", document)
            if doc_rels:
                z.writestr("word/_rels/document.xml.rels", doc_rels)
            if settings_xml:
                z.writestr("word/settings.xml", settings_xml)
            if media:
                for (_rid, fname, bts) in media:
                    z.writestr(f"word/media/{fname}", bts)


    def export_pdf(self, path, font_size=12, embed_fonts=None,
                   embed_font_name="CourierPrime", page_size="A4",
                   justify=False, hyphenate=False, hyphen_lang="it",
                   margins=None):
        """Salva in PDF con markdown di base. Se embed_fonts e' fornito (dict
        stile->metrics), il testo usa il font del documento incorporato e rende
        grassetto/corsivo. La copertina e' una pagina senza numero; la
        numerazione parte da 1 dalla pagina successiva.

        page_size sceglie il formato pagina: "A4" (predefinito) o "A5". Le
        dimensioni e il margine vengono presi da PDF_PAGE_SIZES; un valore non
        riconosciuto ripiega su A4.

        justify   : se True, i paragrafi del corpo sono giustificati alla
                    larghezza del testo (l'ultima riga resta allineata a
                    sinistra; le intestazioni non si giustificano).
        hyphenate : se True e Pyphen e' disponibile, le parole lunghe vengono
                    sillabate con un trattino per una giustificazione piu'
                    ordinata; ignorato se Pyphen manca.
        hyphen_lang : codice lingua del dizionario di sillabazione (es. "it").
        margins   : margini in mm (vedi normalize_page_margins); se None si
                    usano quelli salvati nel documento per questo formato."""
        cover_paragraphs = None
        cover_roles = None
        chapters_paragraphs = []
        chapter_titles = []
        n = 0
        for ch in self.chapters:
            text = render_math(ch.text).rstrip("\n")
            # le bandiere non si stampano (vedi _is_invisible_mark): via anche
            # lo spazio che le segue, per non lasciare un rientro
            text = re.sub("[\U0001F1E6-\U0001F1FF]{2}[ \t]?", "", text)
            paras = list(text.split("\n\n")) if text else [""]
            if ch.is_cover:
                # la copertina grafica ora si costruisce dai CAMPI del
                # frontespizio (titolo, autore, editore), non dal testo del
                # vecchio capitolo-copertina. _cover_lines() gestisce anche il
                # ripiego per i progetti vecchi.
                voci_cop = self.cover_lines_with_roles()
                cover_paragraphs = [t for t, _r in voci_cop] or paras
                cover_roles = [r for _t, r in voci_cop] or None
            else:
                n += 1
                chapters_paragraphs.append(paras)
                chapter_titles.append(ch.title_with_fallback(
                    fallback_template="Capitolo {n}".replace("{n}", str(n))))
        leading = int(round(font_size * 1.45))
        cover_img = None
        if self.cover_image:
            cover_img = _image_to_jpeg(self.cover_image, self.cover_image_fmt)
        # EN: attached chapter images, converted to JPEG for embedding (the
        #     PDF stream uses DCTDecode). Images that cannot be converted
        #     (e.g. WebP without Pillow) are skipped: their caption remains.
        # IT: immagini allegate ai capitoli, convertite in JPEG per
        #     l'incorporamento (lo stream PDF usa DCTDecode). Le immagini non
        #     convertibili (es. WebP senza Pillow) vengono omesse: resta la
        #     loro didascalia.
        chapter_images = {}
        for iname in self.used_images():
            prepared = _image_to_jpeg(self.images[iname])
            if prepared:
                chapter_images[iname] = prepared
        # copertina bianca e vuota se non c'e' immagine e i campi delle
        # Sezioni editoriali del frontespizio sono tutti vuoti
        blank_cover = self.cover_is_blank()
        # frontespizio/colophon come righe con stile (testo, ruolo)
        front = self._front_lines() or None
        colo = self._colophon_lines() or None
        # dimensioni e margini del formato pagina scelto (ripiego su default)
        if page_size not in PDF_PAGE_SIZES:
            page_size = PDF_DEFAULT_PAGE_SIZE
        spec = PDF_PAGE_SIZES[page_size]
        if margins is None:
            margins = self.page_margins(page_size)
        else:
            margins = normalize_page_margins(margins, page_size)
        write_pdf(path, chapters_paragraphs, title=self.title,
                  cover_paragraphs=cover_paragraphs,
                  cover_roles=cover_roles,
                  chapter_titles=chapter_titles,
                  toc_label=self.t_index_label(),
                  font_size=font_size, leading=leading,
                  page_w=spec["w"], page_h=spec["h"],
                  **margins_to_pdf_args(margins),
                  page_break_per_chapter=True,
                  embed_fonts=embed_fonts, embed_font_name=embed_font_name,
                  cover_image=cover_img,
                  chapter_images=chapter_images,
                  frontispiece_paragraphs=front,
                  colophon_paragraphs=colo,
                  blank_cover=blank_cover,
                  justify=justify, hyphenate=hyphenate, hyphen_lang=hyphen_lang)

    def _make_cover_png(self, cover_lines, width=600, height=900):
        """Genera i byte di un'immagine PNG di copertina (raster), necessaria
        perché i generatori di miniature come gnome-epub-thumbnailer mostrino
        l'anteprima: questi strumenti vogliono un'immagine raster (PNG/JPEG),
        non un SVG. Se Pillow è disponibile, disegna anche titolo e autore;
        altrimenti produce con la sola libreria standard un PNG con sfondo,
        cornice e filetti (senza testo), comunque valido come anteprima."""
        voci = self.cover_lines_with_roles()
        title = next((t for t, r in voci if r == "title"),
                     cover_lines[0] if cover_lines else self.title)
        middle = [t for t, r in voci if r in ("subtitle", "author")]
        date = next((t for t, r in voci if r == "publisher"), "")

        # --- tentativo con Pillow (testo nitido) --------------------------
        try:
            from PIL import Image, ImageDraw, ImageFont
            import io as _io

            img = Image.new("RGB", (width, height), "#FFFFFF")
            d = ImageDraw.Draw(img)
            plum = (92, 42, 85)
            # cornice
            d.rectangle([4, 4, width - 5, height - 5], outline=plum, width=3)

            def font(sz, bold=False):
                # prova alcuni font di sistema comuni; ripiego sul font interno
                for n in (["DejaVuSerif-Bold.ttf"] if bold else
                          ["DejaVuSerif.ttf", "DejaVuSerif-Bold.ttf"]):
                    try:
                        return ImageFont.truetype(n, sz)
                    except Exception:
                        pass
                try:
                    return ImageFont.truetype(
                        "/usr/share/fonts/truetype/dejavu/DejaVuSerif.ttf", sz)
                except Exception:
                    return ImageFont.load_default()

            def text_width(text, f):
                try:
                    bbox = d.textbbox((0, 0), text, font=f)
                    return bbox[2] - bbox[0]
                except Exception:
                    return len(text) * 20

            def centered(text, y, sz, bold=False, fill=(58, 18, 48)):
                f = font(sz, bold)
                tw = text_width(text, f)
                d.text(((width - tw) / 2, y), text, font=f, fill=fill)

            def wrap(text, f, maxw):
                words = text.split()
                if not words:
                    return [""]
                rows, cur = [], words[0]
                for w in words[1:]:
                    if text_width(cur + " " + w, f) <= maxw:
                        cur += " " + w
                    else:
                        rows.append(cur); cur = w
                rows.append(cur)
                return rows

            # filetti sopra/sotto il titolo
            d.line([180, 330, 420, 330], fill=plum, width=2)
            # titolo: riduci il corpo finché non sta, poi vai a capo se serve
            maxw = width - 120
            tsize = 40
            tfont = font(tsize, True)
            while tsize > 22 and text_width(title, tfont) > maxw:
                tsize -= 2
                tfont = font(tsize, True)
            rows = wrap(title, tfont, maxw)
            ty = 400 - (len(rows) - 1) * (tsize + 6) // 2
            for r in rows:
                tw = text_width(r, tfont)
                d.text(((width - tw) / 2, ty), r, font=tfont, fill=(58, 18, 48))
                ty += tsize + 6
            yy = 470
            for m in middle:
                centered(m, yy, 24)
                yy += 40
            d.line([180, 560, 420, 560], fill=plum, width=2)
            if date:
                centered(date, 600, 18, fill=(110, 110, 110))

            buf = _io.BytesIO()
            img.save(buf, format="PNG")
            return buf.getvalue()
        except Exception:
            pass

        # --- ripiego senza dipendenze: PNG di sola grafica (stdlib) -------
        return self._simple_png(width, height)

    @staticmethod
    def _simple_png(width, height):
        """Crea un PNG (sfondo bianco + cornice prugna + due filetti) usando
        solo zlib e struct. Serve come anteprima quando Pillow non c'è."""
        import zlib, struct

        # immagine RGB: lista di righe, ogni pixel 3 byte
        white = (255, 255, 255)
        plum = (92, 42, 85)

        # buffer pixel
        raw = bytearray()
        # disegniamo: cornice spessa 3px e due filetti orizzontali
        def px(x, y):
            # bordo cornice
            if x < 4 or x >= width - 4 or y < 4 or y >= height - 4:
                if x < 7 or x >= width - 7 or y < 7 or y >= height - 7:
                    return plum
            # filetti a y=330 e y=560, da x=180 a x=420
            if (330 <= y <= 332 or 560 <= y <= 562) and 180 <= x <= 420:
                return plum
            return white

        for y in range(height):
            raw.append(0)  # filtro 'None' a inizio riga
            for x in range(width):
                r, g, b = px(x, y)
                raw += bytes((r, g, b))

        def chunk(typ, data):
            c = struct.pack(">I", len(data)) + typ + data
            c += struct.pack(">I", zlib.crc32(typ + data) & 0xffffffff)
            return c

        sig = b"\x89PNG\r\n\x1a\n"
        ihdr = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)  # 8-bit RGB
        idat = zlib.compress(bytes(raw), 9)
        return (sig + chunk(b"IHDR", ihdr)
                + chunk(b"IDAT", idat) + chunk(b"IEND", b""))

    @staticmethod
    def _make_blank_cover_png(width=600, height=900):
        """Crea un PNG completamente BIANCO (nessuna cornice, nessun filetto,
        nessun testo), usando solo zlib e struct. Usato come copertina
        e-book quando i campi delle Sezioni editoriali sono vuoti e non c'e'
        un'immagine di copertina: il risultato e' una copertina bianca e vuota."""
        import zlib, struct

        # ogni riga: 1 byte di filtro 'None' + width pixel RGB bianchi
        white_row = b"\x00" + (b"\xff\xff\xff" * width)
        raw = white_row * height

        def chunk(typ, data):
            c = struct.pack(">I", len(data)) + typ + data
            c += struct.pack(">I", zlib.crc32(typ + data) & 0xffffffff)
            return c

        sig = b"\x89PNG\r\n\x1a\n"
        ihdr = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)  # 8-bit RGB
        idat = zlib.compress(raw, 9)
        return (sig + chunk(b"IHDR", ihdr)
                + chunk(b"IDAT", idat) + chunk(b"IEND", b""))

    def export_epub(self, path, author=None):
        """Esporta il progetto in un file EPUB 2 valido usando solo la
        libreria standard. La copertina diventa la prima sezione; ogni
        capitolo una sezione XHTML separata. Il markdown di base
        (intestazioni, grassetto, corsivo, liste, citazioni) viene reso in
        HTML semplice. Titolo e autore provengono dal progetto/copertina."""
        import zipfile, html, uuid, datetime

        # --- titolo e autore: prima di tutto dai CAMPI del frontespizio ----
        # (File -> Sezioni editoriali). _cover_lines() usa i campi e ripiega
        # sul vecchio capitolo-copertina solo per i progetti datati.
        title = self.title or "Senza titolo"
        cover_lines = self._cover_lines()
        if cover_lines:
            title = cover_lines[0]
        if author is None:
            author = (self.frontispiece_fields.get("author", "") or "").strip()
        author = author or ""

        book_id = "urn:uuid:" + str(uuid.uuid4())

        def esc(s):
            return html.escape(s, quote=False)

        # EN: attached images referenced by the chapters: they are shipped in
        #     OEBPS/images/ and listed in the manifest with their MIME type.
        # IT: immagini allegate richiamate dai capitoli: vengono incluse in
        #     OEBPS/images/ ed elencate nel manifest con il loro tipo MIME.
        used_imgs = self.used_images()

        def epub_image_html(alt, name):
            # EN: XHTML 1.1 has no <figure>: a plain <div> + caption <p>.
            # IT: XHTML 1.1 non ha <figure>: un semplice <div> + <p> didascalia.
            cap = (f'<p style="text-align:center;font-style:italic;">'
                   f'{esc(alt)}</p>' if alt.strip() else "")
            return (f'<div style="text-align:center;">'
                    f'<img src="images/{name}" alt="{esc(alt)}" '
                    f'style="max-width:100%;"/></div>{cap}')

        def md_to_html(text):
            """EN: chapter Markdown -> XHTML body, via the shared converter.
            IT: markdown del capitolo -> corpo XHTML, tramite il convertitore
            condiviso."""
            out = self._blocks_to_html(text, image_html=epub_image_html)
            return "\n".join(out) if out else "<p></p>"

        XHTML = ('<?xml version="1.0" encoding="utf-8"?>\n'
                 '<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.1//EN" '
                 '"http://www.w3.org/TR/xhtml11/DTD/xhtml11.dtd">\n'
                 '<html xmlns="http://www.w3.org/1999/xhtml">\n'
                 '<head><meta http-equiv="Content-Type" '
                 'content="text/html; charset=utf-8"/>\n'
                 '<title>{t}</title>\n'
                 '<link rel="stylesheet" type="text/css" href="style.css"/>\n'
                 '</head>\n<body>\n{body}\n</body>\n</html>\n')

        CSS = ("body{font-family:'EB Garamond',Georgia,serif;line-height:1.5;margin:5%;}"
               "h1,h2,h3{font-family:sans-serif;color:#5C2A55;}"
               "blockquote{font-style:italic;border-left:3px solid #8E4585;"
               "padding-left:1em;color:#444;}"
               ".cover{text-align:center;margin-top:30%;}"
               ".cover .title{font-size:2em;font-weight:bold;color:#5C2A55;}"
               ".cover .author{font-size:1.2em;margin-top:1em;}"
               ".cover .date{font-style:italic;margin-top:2em;color:#666;}"
               "nav.toc ol{list-style:none;padding-left:0;}"
               "nav.toc li{margin:0.4em 0;}"
               "nav.toc a{color:#5C2A55;text-decoration:none;}"
               "code{font-family:monospace;}"
               # EN/IT: tables in book style / tabelle in stile libro
               "table{border-collapse:collapse;width:100%;margin:1.5em 0;font-size:0.95em;"
               "border-top:2px solid #333;border-bottom:2px solid #333;}"
               "th,td{padding:0.35em 0.6em;text-align:left;vertical-align:top;}"
               "thead th{border-bottom:1px solid #333;}"
               "hr{border:none;border-top:1px solid #888;width:30%;margin:1.5em auto;}")

        # --- immagine di copertina (SVG, sobria come il PDF) --------------
        cl = cover_lines or [title]
        ctitle = esc(cl[0])
        cmiddle = [esc(x) for x in cl[1:-1]] if len(cl) > 2 else (
            [esc(cl[1])] if len(cl) == 2 else [])
        cdate = esc(cl[-1]) if len(cl) > 1 else ""

        def svg_text(y, size, weight, txt, style=""):
            return (f'<text x="300" y="{y}" text-anchor="middle" '
                    f'font-family="serif" font-size="{size}" '
                    f'font-weight="{weight}" {style} fill="#3A1230">{txt}</text>')

        svg_lines = [
            '<rect x="2" y="2" width="596" height="896" fill="#FFFFFF" '
            'stroke="#5C2A55" stroke-width="2"/>',
            '<line x1="180" y1="330" x2="420" y2="330" stroke="#5C2A55" '
            'stroke-width="1.2"/>',
            svg_text(420, 38, "bold", ctitle),
        ]
        yy = 470
        for mid in cmiddle:
            svg_lines.append(svg_text(yy, 24, "normal", mid))
            yy += 40
        svg_lines.append('<line x1="180" y1="560" x2="420" y2="560" '
                         'stroke="#5C2A55" stroke-width="1.2"/>')
        if cdate:
            svg_lines.append(svg_text(610, 18, "normal", cdate,
                                      'font-style="italic"'))
        cover_svg = ('<?xml version="1.0" encoding="utf-8"?>\n'
                     '<svg xmlns="http://www.w3.org/2000/svg" '
                     'width="600" height="900" viewBox="0 0 600 900">\n'
                     + "\n".join(svg_lines) + '\n</svg>\n')

        # immagine di copertina RASTER: se l'utente ne ha caricata una usiamo
        # quella, altrimenti generiamo il PNG sobrio. I generatori di miniature
        # (gnome-epub-thumbnailer, Calibre) richiedono un raster.
        if self.cover_image:
            cover_img_bytes = self.cover_image
            cover_ext = IMAGE_FORMATS.get(self.cover_image_fmt, ("png",))[0]
            cover_img_name = f"cover.{cover_ext}"
            cover_img_mime = self._cover_image_mime()
        elif self.cover_is_blank():
            # campi Sezioni editoriali vuoti e nessuna immagine: copertina
            # bianca e vuota (PNG completamente bianco, senza testo ne' grafica)
            cover_img_bytes = self._make_blank_cover_png()
            cover_img_name = "cover.png"
            cover_img_mime = "image/png"
        else:
            cover_img_bytes = self._make_cover_png(cl)
            cover_img_name = "cover.png"
            cover_img_mime = "image/png"

        # --- costruisci le sezioni XHTML ----------------------------------
        sections = []   # (id, filename, title, xhtml_body, in_toc)

        # pagina copertina che mostra l'immagine raster
        cover_page = ('<div style="text-align:center;margin:0;padding:0;">'
                      '<img src="%s" alt="%s" '
                      'style="max-width:100%%;height:auto;"/></div>'
                      % (cover_img_name, ctitle))
        sections.append(("coverpage", "cover.xhtml", title, cover_page, False))

        # frontespizio (dopo la copertina), se presente
        front = self._front_paragraphs()
        if front:
            fr_html = ['<div class="frontispiece">']
            for j, ln in enumerate(front):
                if j == 0:
                    fr_html.append(f'<h1 style="text-align:center">{esc(ln)}</h1>')
                else:
                    fr_html.append(f'<p style="text-align:center">{esc(ln)}</p>')
            fr_html.append('</div>')
            sections.append(("frontispiece", "frontispiece.xhtml",
                             "Frontispiece", "\n".join(fr_html), False))

        # capitoli
        chap_entries = []   # (filename, titolo) per l'indice
        n = 0
        for ch in self.chapters:
            if ch.is_cover:
                continue
            n += 1
            ch_title = ch.title_with_fallback(
                fallback_template="Capitolo {n}".replace("{n}", str(n)))
            fname = f"chap{n:02d}.xhtml"
            sections.append((f"chap{n:02d}", fname, ch_title,
                             md_to_html(ch.text), True))
            chap_entries.append((fname, ch_title))

        # colophon (ultima sezione), se presente
        colo = self._colophon_paragraphs()
        if colo:
            co_html = ['<div class="colophon">']
            for ln in colo:
                co_html.append(f'<p style="text-align:center">{esc(ln)}</p>')
            co_html.append('</div>')
            sections.append(("colophon", "colophon.xhtml",
                             "Colophon", "\n".join(co_html), False))

        # pagina indice (sommario navigabile)
        toc_items = "".join(
            f'<li><a href="{fn}">{esc(tt)}</a></li>' for fn, tt in chap_entries)
        toc_body = (f'<h1>{esc(self.t_index_label())}</h1>'
                    f'<nav class="toc"><ol>{toc_items}</ol></nav>')
        # inserisci l'indice subito dopo la copertina
        sections.insert(1, ("nav", "index.xhtml",
                            self.t_index_label(), toc_body, False))

        # --- file di struttura --------------------------------------------
        manifest, spine, navpoints = [], [], []
        play = 1
        for (iid, fname, sec_title, _body, in_toc) in sections:
            manifest.append(f'<item id="{iid}" href="{fname}" '
                            f'media-type="application/xhtml+xml"/>')
            spine.append(f'<itemref idref="{iid}"/>')
            if in_toc:
                navpoints.append(
                    f'<navPoint id="np{play}" playOrder="{play}">'
                    f'<navLabel><text>{esc(sec_title)}</text></navLabel>'
                    f'<content src="{fname}"/></navPoint>')
                play += 1

        opf = ('<?xml version="1.0" encoding="utf-8"?>\n'
               '<package xmlns="http://www.idpf.org/2007/opf" '
               'unique-identifier="bookid" version="2.0">\n'
               '<metadata xmlns:dc="http://purl.org/dc/elements/1.1/" '
               'xmlns:opf="http://www.idpf.org/2007/opf">\n'
               f'<dc:title>{esc(title)}</dc:title>\n'
               + (f'<dc:creator opf:role="aut">{esc(author)}</dc:creator>\n'
                  if author else '') +
               '<dc:language>it</dc:language>\n'
               f'<dc:identifier id="bookid">{book_id}</dc:identifier>\n'
               f'<dc:date>{datetime.date.today().isoformat()}</dc:date>\n'
               '<meta name="cover" content="cover-image"/>\n'
               '</metadata>\n<manifest>\n'
               '<item id="ncx" href="toc.ncx" '
               'media-type="application/x-dtbncx+xml"/>\n'
               '<item id="css" href="style.css" media-type="text/css"/>\n'
               f'<item id="cover-image" href="{cover_img_name}" '
               f'media-type="{cover_img_mime}"/>\n'
               '<item id="cover-svg" href="cover.svg" '
               'media-type="image/svg+xml"/>\n'
               + "".join(f'<item id="att{k}" href="images/{n}" '
                         f'media-type="{self.image_mime(n)}"/>\n'
                         for k, n in enumerate(used_imgs, 1))
               + "\n".join(manifest) +
               '\n</manifest>\n<spine toc="ncx">\n'
               + "\n".join(spine) +
               '\n</spine>\n<guide>\n'
               '<reference type="cover" title="Copertina" href="cover.xhtml"/>\n'
               '<reference type="toc" title="Indice" href="index.xhtml"/>\n'
               '</guide>\n</package>\n')

        ncx = ('<?xml version="1.0" encoding="utf-8"?>\n'
               '<ncx xmlns="http://www.daisy.org/z3986/2005/ncx/" version="2005-1">\n'
               f'<head><meta name="dtb:uid" content="{book_id}"/>'
               '<meta name="dtb:depth" content="1"/>'
               '<meta name="dtb:totalPageCount" content="0"/>'
               '<meta name="dtb:maxPageNumber" content="0"/></head>\n'
               f'<docTitle><text>{esc(title)}</text></docTitle>\n'
               '<navMap>\n' + "\n".join(navpoints) + '\n</navMap>\n</ncx>\n')

        container = ('<?xml version="1.0" encoding="UTF-8"?>\n'
                     '<container version="1.0" '
                     'xmlns="urn:oasis:names:tc:opendocument:xmlns:container">\n'
                     '<rootfiles><rootfile full-path="OEBPS/content.opf" '
                     'media-type="application/oebps-package+xml"/></rootfiles>\n'
                     '</container>\n')

        # --- scrivi lo ZIP EPUB (mimetype non compresso, per primo) -------
        with zipfile.ZipFile(path, "w") as z:
            z.writestr("mimetype", "application/epub+zip",
                       compress_type=zipfile.ZIP_STORED)
            z.writestr("META-INF/container.xml", container,
                       compress_type=zipfile.ZIP_DEFLATED)
            z.writestr("OEBPS/content.opf", opf, zipfile.ZIP_DEFLATED)
            z.writestr("OEBPS/toc.ncx", ncx, zipfile.ZIP_DEFLATED)
            z.writestr("OEBPS/style.css", CSS, zipfile.ZIP_DEFLATED)
            z.writestr("OEBPS/" + cover_img_name, cover_img_bytes,
                       zipfile.ZIP_DEFLATED)
            z.writestr("OEBPS/cover.svg", cover_svg, zipfile.ZIP_DEFLATED)
            # EN: attached chapter images (only the ones actually used).
            # IT: immagini allegate ai capitoli (solo quelle davvero usate).
            for n in used_imgs:
                z.writestr("OEBPS/images/" + n, self.images[n],
                           zipfile.ZIP_STORED)
            for (iid, fname, sec_title, body, in_toc) in sections:
                z.writestr("OEBPS/" + fname,
                           XHTML.format(t=esc(sec_title), body=body),
                           zipfile.ZIP_DEFLATED)

    def t_index_label(self):
        """Etichetta 'Indice' nella lingua del progetto (fallback IT/EN)."""
        return "Indice" if getattr(self, "_lang", "it") == "it" else "Contents"

    @staticmethod
    def _find_calibre_converter():
        """Cerca l'eseguibile 'ebook-convert' di Calibre nel sistema.
        Restituisce il percorso o None se Calibre non è installato."""
        # nel PATH
        exe = shutil.which("ebook-convert")
        if exe:
            return exe
        # percorsi tipici (Linux, macOS, Windows)
        candidates = [
            "/usr/bin/ebook-convert",
            "/opt/calibre/ebook-convert",
            "/Applications/calibre.app/Contents/MacOS/ebook-convert",
            r"C:\Program Files\Calibre2\ebook-convert.exe",
            r"C:\Program Files (x86)\Calibre2\ebook-convert.exe",
        ]
        for c in candidates:
            if os.path.exists(c):
                return c
        return None

    def export_azw3(self, path, author=None):
        """Esporta in AZW3 (Kindle). L'AZW3 è un formato proprietario Amazon:
        per ottenere un file affidabile generiamo prima un EPUB (che sappiamo
        produrre bene) e lo convertiamo con Calibre ('ebook-convert'), se
        installato. Se Calibre non c'è, solleviamo un errore esplicativo.

        Restituisce il percorso prodotto. Solleva RuntimeError con istruzioni
        se la conversione non è possibile."""
        import subprocess

        converter = self._find_calibre_converter()
        if not converter:
            raise RuntimeError(
                "Per esportare in AZW3 serve Calibre (comando 'ebook-convert').\n"
                "Installa Calibre da https://calibre-ebook.com/ e riprova.\n"
                "In alternativa esporta in EPUB e converti con Calibre o "
                "'Invia a Kindle' di Amazon.")

        # 1) genera un EPUB temporaneo accanto alla destinazione
        tmpdir = tempfile.mkdtemp()
        epub_tmp = os.path.join(tmpdir, "book.epub")
        self.export_epub(epub_tmp, author=author)

        # 2) converti EPUB -> AZW3 con Calibre, passando i metadati principali
        cover_lines = self._cover_lines()
        book_title = cover_lines[0] if cover_lines else self.title
        book_author = author or (self.frontispiece_fields.get("author", "") or "").strip()
        cmd = [converter, epub_tmp, path,
               "--title", book_title]
        if book_author:
            cmd += ["--authors", book_author]
        try:
            result = subprocess.run(
                cmd, capture_output=True, text=True, timeout=300)
        except subprocess.TimeoutExpired:
            raise RuntimeError("La conversione AZW3 ha impiegato troppo tempo.")
        except FileNotFoundError:
            raise RuntimeError(
                "Calibre non trovato. Installa Calibre da "
                "https://calibre-ebook.com/ e riprova.")
        finally:
            # pulizia del file temporaneo
            try:
                os.remove(epub_tmp)
                os.rmdir(tmpdir)
            except OSError:
                pass

        if result.returncode != 0 or not os.path.exists(path):
            msg = (result.stderr or result.stdout or "").strip()
            raise RuntimeError("Calibre non è riuscito a creare l'AZW3.\n" + msg[:500])
        return path

    def add_chapter(self):
        idx = (max((c.index for c in self.chapters if not c.is_cover), default=0)) + 1
        ch = Chapter(idx, "", "")
        self.chapters.append(ch)
        self._renumber()
        return ch

    def add_chapter_from_text(self, text, title=""):
        """Aggiunge UN nuovo capitolo in fondo al progetto con il contenuto
        passato (es. importato da un file .txt/.md). Il progetto e gli altri
        capitoli restano invariati. Se 'title' e' dato, diventa il titolo
        personalizzato del capitolo. Restituisce il Chapter creato."""
        idx = (max((c.index for c in self.chapters if not c.is_cover), default=0)) + 1
        body = (text or "").replace("\r\n", "\n").replace("\r", "\n").strip("\n")
        ch = Chapter(idx, body, "", custom_title=(title or "").strip())
        self.chapters.append(ch)
        self._renumber()
        return ch

    def count_wrapped_runs(self):
        """Quanti paragrafi spezzati a colonna fissa ci sono in tutto il
        progetto, e su quante righe. Serve a CHIEDERE, non a decidere."""
        paragrafi = righe = 0
        for ch in self.chapters:
            for first, last in wrapped_runs(ch.text):
                paragrafi += 1
                righe += last - first
        return paragrafi, righe

    def rejoin_paragraphs(self):
        """Ricuce i paragrafi spezzati di TUTTI i capitoli. Restituisce
        (paragrafi, righe) effettivamente sistemati. Da chiamare solo dopo un
        assenso esplicito: la ricucitura cambia il testo di chi scrive."""
        paragrafi = righe = 0
        for ch in self.chapters:
            runs = wrapped_runs(ch.text)
            if not runs:
                continue
            paragrafi += len(runs)
            righe += sum(last - first for first, last in runs)
            ch.text = unwrap_hard_breaks(ch.text)
        return paragrafi, righe

    def delete_chapter(self, row):
        """Rimuove il capitolo alla posizione 'row'. La copertina e' protetta."""
        if 0 <= row < len(self.chapters) and not self.chapters[row].is_cover:
            del self.chapters[row]
            self._renumber()

    def move_chapter(self, row, direction):
        """Sposta il capitolo su (-1) o giu (+1). La copertina resta in cima
        e nessun capitolo puo' finire prima della copertina."""
        if not (0 <= row < len(self.chapters)):
            return row
        ch = self.chapters[row]
        if ch.is_cover:
            return row                      # la copertina non si sposta
        target = row + direction
        # non oltre i limiti e non sopra la copertina (posizione 0)
        if target < 1 or target >= len(self.chapters):
            return row
        if self.chapters[target].is_cover:
            return row
        self.chapters[row], self.chapters[target] = \
            self.chapters[target], self.chapters[row]
        self._renumber()
        return target

    def cover(self):
        """Restituisce il capitolo copertina, o None."""
        for ch in self.chapters:
            if ch.is_cover:
                return ch
        return None


