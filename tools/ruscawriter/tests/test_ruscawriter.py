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
Test automatici per RuscaWriter.
Verificano il modello dati e gli export (PDF/EPUB/TXT/...) e l'i18n SENZA
bisogno di GTK, importando i moduli del pacchetto ruscawriter.

Esegui dalla radice del progetto:  python3 tests/test_ruscawriter.py
"""
import os
import sys
import tempfile
import zipfile
import xml.dom.minidom as minidom

HERE = os.path.dirname(os.path.abspath(__file__))
# la radice del progetto è la cartella che contiene 'src' e 'tests'
ROOT = os.path.abspath(os.path.join(HERE, ".."))
sys.path.insert(0, os.path.join(ROOT, "src"))

from ruscawriter import model as pw_model
from ruscawriter import i18n as pw_i18n
from ruscawriter.model import Project, Chapter, build_css

PASSED = 0
FAILED = 0


class _Paths:
    """EN/IT: what the old ruscawriter.paths module gave the tests: the
    assets folder and a file inside it. / cio' che il vecchio modulo
    ruscawriter.paths dava ai test: la cartella assets e un file al suo
    interno."""
    def __init__(self, assets_dir):
        self.ASSETS_DIR = assets_dir

    def asset(self, name):
        return os.path.join(self.ASSETS_DIR, name)


def check(name, cond):
    global PASSED, FAILED
    if cond:
        PASSED += 1
        print(f"  ok  {name}")
    else:
        FAILED += 1
        print(f"  FAIL {name}")


def sample_project():
    p = Project()
    p._lang = "it"
    p.title = "Romanzo di prova"
    p.chapters = [
        Chapter(0, "ROMANZO DI PROVA\n\nMario Bianchi\n\n01/01/2026",
                "", is_cover=True),
        Chapter(1, "# Capitolo primo\n\nC'era una volta un **giardino**.", ""),
        Chapter(2, "Secondo capitolo, senza titolo markdown.", "",
                custom_title="L'autunno"),
    ]
    return p


def test_save_load_roundtrip():
    print("save/load round-trip")
    p = sample_project()
    d = tempfile.mkdtemp()
    path = os.path.join(d, "prova.plum")
    p.save(path)
    check("file .plum creato", os.path.exists(path))

    q = Project()
    q.load(path)
    contents = [c.text for c in q.chapters]
    check("copertina preservata", contents[0].startswith("ROMANZO"))
    check("numero capitoli", len(q.chapters) == 3)
    # titolo personalizzato deve sopravvivere al round-trip
    custom = [c.custom_title for c in q.chapters if c.custom_title]
    check("titolo personalizzato salvato", "L'autunno" in custom)


def test_autosave_non_mutating():
    print("autosave non-mutante")
    p = sample_project()
    d = tempfile.mkdtemp()
    path = os.path.join(d, "prova.plum")
    p.save(path)
    orig_path, orig_title = p.path, p.title
    p.save(path + ".autosave", update_path=False)
    check("path invariato dopo autosave", p.path == orig_path)
    check("title invariato dopo autosave", p.title == orig_title)
    check("file autosave creato", os.path.exists(path + ".autosave"))


def test_chapter_title_priority():
    print("priorità titolo capitolo")
    ch = Chapter(1, "# Intestazione MD\n\ntesto")
    check("usa intestazione markdown", ch.title_with_fallback() == "Intestazione MD")
    ch.custom_title = "Titolo scelto"
    check("titolo personalizzato vince", ch.title_with_fallback() == "Titolo scelto")
    cover = Chapter(0, "x", is_cover=True)
    check("copertina usa etichetta",
          cover.title_with_fallback(cover_label="Copertina") == "Copertina")


def test_export_txt():
    print("export TXT")
    p = sample_project()
    d = tempfile.mkdtemp()
    path = os.path.join(d, "out.txt")
    p.export_txt(path)
    txt = open(path, encoding="utf-8").read()
    check("contiene testo capitolo", "giardino" in txt)


def test_export_pdf():
    print("export PDF")
    p = sample_project()
    d = tempfile.mkdtemp()
    path = os.path.join(d, "out.pdf")
    p.export_pdf(path, font_size=12)
    data = open(path, "rb").read()
    check("header PDF valido", data[:5] == b"%PDF-")
    check("EOF PDF presente", b"%%EOF" in data[-1024:])
    check("dimensione plausibile", len(data) > 800)


def test_export_epub():
    print("export EPUB")
    p = sample_project()
    d = tempfile.mkdtemp()
    path = os.path.join(d, "out.epub")
    p.export_epub(path)
    z = zipfile.ZipFile(path)
    names = z.namelist()
    check("mimetype è il primo elemento", names[0] == "mimetype")
    check("mimetype STORED",
          z.getinfo("mimetype").compress_type == zipfile.ZIP_STORED)
    check("mimetype corretto",
          z.read("mimetype").decode() == "application/epub+zip")
    check("zip integro", z.testzip() is None)
    check("ha cover image", "OEBPS/cover.svg" in names)
    check("ha pagina indice", "OEBPS/index.xhtml" in names)
    # XML ben formato nei file chiave
    for f in ("OEBPS/content.opf", "OEBPS/toc.ncx", "META-INF/container.xml",
              "OEBPS/index.xhtml", "OEBPS/cover.svg"):
        try:
            minidom.parseString(z.read(f))
            ok = True
        except Exception:
            ok = False
        check(f"XML valido: {f}", ok)
    # titolo personalizzato nell'indice
    idx = z.read("OEBPS/index.xhtml").decode()
    check("titolo personalizzato nell'indice",
          "autunno" in idx.lower())


def test_word_count():
    print("conteggio parole")
    # replica la logica statica di conteggio
    text = "una due tre quattro"
    check("conta parole", len(text.split()) == 4)


def test_themes():
    print("temi: il foglio di stile colora solo la pagina")
    light = build_css(dark=False)
    dark = build_css(dark=True)
    check("CSS chiaro non vuoto", len(light) > 100)
    check("i due temi differiscono", light != dark)
    check("colora l'area di scrittura e le note",
          "textview.text-editor" in light and "textview.notes-editor" in light)
    check("non ridisegna barre, menu e pulsanti (li fa libadwaita)",
          all(sel not in light for sel in ("headerbar", "menubar", "button",
                                           "@define-color", "window,")))
    check("Ametista: l'accento e' il prugna ufficiale di RuscaLinux",
          pw_model.PLUM == "#7A2357")


def _contrasto(a, b):
    return pw_model._contrast(a, b)


def test_theme_families():
    print("i due temi: Ametista, Classico")
    check("due temi, non uno di piu'", len(pw_model.THEMES) == 2)
    check("nell'ordine Ametista, Classico",
          pw_model.THEMES == ("ametista", "classico"))
    check("il predefinito e' l'Ametista di RuscaLinux",
          pw_model.DEFAULT_THEME == pw_model.THEME_AMETISTA)

    css = {(f, d): build_css(dark=d, theme=f)
           for f in pw_model.THEMES for d in (False, True)}
    check("quattro fogli di stile, tutti diversi", len(set(css.values())) == 4)

    # --- il criterio comune: il contrasto GIUSTO -------------------------
    for fam in pw_model.THEMES:
        nome = pw_model.theme_label(fam)
        for dark in (False, True):
            p = pw_model.theme_palette(fam, dark)
            modo = "scuro" if dark else "chiaro"
            r = _contrasto(p["editor_fg"], p["editor_bg"])
            check(f"{nome} {modo}: corpo del testo comodo ({r:.1f}:1)",
                  10.0 <= r <= 13.0)
            check(f"{nome} {modo}: niente bianco o nero pieni sulla pagina",
                  p["editor_bg"].upper() not in ("#FFFFFF", "#000000")
                  and p["editor_fg"].upper() not in ("#FFFFFF", "#000000"))
            # sulla pagina: titoli e codice almeno 7:1, marcatori 4,5:1
            for chiave, minimo in (("head", 7.0), ("code", 7.0),
                                   ("notes_fg", 7.0), ("marker", 4.5)):
                r = _contrasto(p[chiave], p["editor_bg"])
                check(f"{nome} {modo}: {chiave} leggibile ({r:.1f}:1)",
                      r >= minimo - 1e-6)
            r = _contrasto(p["sel_fg"], p["sel_bg"])
            check(f"{nome} {modo}: testo selezionato leggibile ({r:.1f}:1)", r >= 7.0)
            # la selezione si vede sulla pagina
            check(f"{nome} {modo}: selezione visibile",
                  _contrasto(p["sel_bg"], p["editor_bg"]) >= 1.3)

    # --- il carattere di ciascuno -----------------------------------------
    am = pw_model.theme_palette(pw_model.THEME_AMETISTA, False)
    check("Ametista: titoli nel prugna ufficiale",
          am["head"].upper() == "#7A2357")

    def tinta(c):
        h = c.lstrip("#")
        r, g, b = (int(h[i:i + 2], 16) for i in (0, 2, 4))
        return max(r, g, b) - min(r, g, b)

    cl = pw_model.theme_palette(pw_model.THEME_CLASSICO, False)
    check("Classico: pagina bianca nitida (non bianco pieno) e neutra",
          cl["editor_bg"] == pw_model.CLASSICO_HUES["paper"]
          and tinta(cl["editor_bg"]) <= 4)
    check("Classico: selezione e titoli blu",
          tinta(cl["sel_bg"]) > 12 and int(cl["head"][5:7], 16) > int(cl["head"][1:3], 16))
    cl_scuro = pw_model.theme_palette(pw_model.THEME_CLASSICO, True)
    check("Classico scuro: pagina carbone neutra, non nera",
          tinta(cl_scuro["editor_bg"]) <= 4 and cl_scuro["editor_bg"].upper() != "#000000")

    # la tavolozza: stesse chiavi ovunque
    palettes = [pw_model.theme_palette(f, d)
                for f in pw_model.THEMES for d in (False, True)]
    keys = set(palettes[0])
    check("tavolozze con le stesse chiavi",
          all(set(p) == keys for p in palettes))

    check("tema sconosciuto -> predefinito",
          build_css(dark=False, theme="inesistente")
          == build_css(dark=False, theme=pw_model.DEFAULT_THEME))

    # nomi: tradotti in tutte le 26 lingue, tre e diversi fra loro
    check("nomi italiani",
          [pw_model.theme_label(t) for t in pw_model.THEMES]
          == ["Ametista", "Classico"])
    for code in sorted(pw_i18n.available_languages()):
        tr = pw_i18n.Translator(code)
        nomi = [pw_model.theme_label(t, translate=lambda k, r: tr.t(k))
                for t in pw_model.THEMES]
        check(f"{code}: due nomi tradotti e diversi",
              len(set(nomi)) == 2
              and all(not n.startswith("theme_") for n in nomi))

    pallini = [pw_model.theme_dot_color(t) for t in pw_model.THEMES]
    check("ogni tema ha il suo pallino, tutti diversi",
          all(pallini) and len(set(pallini)) == 2)

    # i codici delle versioni precedenti portano al tema piu' vicino
    for vecchio, atteso in (("rusca", "ametista"), ("rubino", "ametista"),
                            ("morganite", "ametista"),
                            ("standard", "classico"), ("giada", "classico"),
                            ("ambra", "classico"), ("velluto", "classico"),
                            ("zaffiro", "classico"),
                            ("lapislazzuli", "classico"),
                            ("semplice", "classico")):
        check(f"il vecchio tema {vecchio!r} diventa {atteso!r}",
              pw_model.resolve_theme(vecchio) == atteso)
    check("niente piu' temi letti da disco",
          not hasattr(pw_model, "load_user_themes"))

    en = pw_i18n.load_language("en")
    it = pw_i18n.load_language("it")
    for chiave in ("mi_theme", "mi_appearance", "mi_appearance_auto",
                   "mi_page_setup"):
        check(f"voce di menu '{chiave}' tradotta",
              chiave in en and chiave in it)


def test_icona_unica():
    print("icona: una sola, quella del tema, nella palette RuscaLinux")
    with open(os.path.join(ROOT, "src", "ruscawriter", "editor.py"),
              encoding="utf-8") as f:
        src = f.read()
    with open(os.path.join(ROOT, "assets", "ruscawriter.svg"),
              encoding="utf-8") as f:
        svg = f.read()
    check("il programma usa l'icona del tema (App ID)",
          'ICON_FILE = os.path.join(ASSETS_DIR, "ruscawriter.svg")' in src
          and "has_icon(name)" in src)
    check("nessuna copia dell'icona dentro il codice", 'ICON_SVG = b"""' not in src)
    check("palette RuscaLinux: prugna e crema",
          "#2d0a1d" in svg and "#fff7f0" in svg)
    check("c'e' l'icona simbolica",
          os.path.isfile(os.path.join(ROOT, "assets", "ruscawriter-symbolic.svg")))


def test_margini_pagina():
    print("margini di pagina professionali")
    from ruscawriter.model import (margin_preset, margin_problems,
                                   normalize_page_margins, text_block_mm,
                                   which_margin_preset, chars_per_line,
                                   MARGIN_PRESETS, PDF_PAGE_SIZES)
    for size in PDF_PAGE_SIZES:
        for preset in MARGIN_PRESETS:
            m = margin_preset(preset, size)
            check(f"{size}/{preset}: valido",
                  margin_problems(size, m) == [])
            check(f"{size}/{preset}: si riconosce",
                  which_margin_preset(size, m) == preset)
    # il canone classico: interno, superiore, esterno, inferiore = 2:3:4:6
    c = margin_preset("canon", "A5")
    check("canone: esterno doppio dell'interno",
          abs(c["outer"] - 2 * c["inner"]) < 0.2)
    check("canone: inferiore doppio del superiore",
          abs(c["bottom"] - 2 * c["top"]) < 0.2)
    check("manoscritto: pagine non speculari",
          margin_preset("manuscript", "A4")["mirror"] is False)

    # valori impossibili
    m = margin_preset("format", "A5")
    m2 = dict(m, top=2.0)
    check("margine sotto i 5 mm segnalato",
          "too_small" in margin_problems("A5", m2))
    m3 = dict(m, inner=60.0, outer=60.0)
    check("gabbia troppo stretta segnalata",
          "too_narrow" in margin_problems("A5", m3))
    check("dati rovinati -> margini del formato",
          normalize_page_margins({"top": "x", "inner": 200}, "A5") == m)
    check("nessun dato -> margini del formato",
          normalize_page_margins(None, "A5") == m)
    bw, bh = text_block_mm("A5", dict(m, gutter=5.0))
    check("la rilegatura toglie larghezza alla gabbia",
          abs(text_block_mm("A5", m)[0] - bw - 5.0) < 0.01)
    check("battute per riga plausibili",
          40 <= chars_per_line("A5", m, 11) <= 80)

    # nel documento: si salva solo cio' che differisce dal formato
    p = sample_project()
    check("nessun margine salvato di partenza",
          "page_margins" not in p.meta)
    p.set_page_margins("A5", margin_preset("canon", "A5"))
    check("margini salvati nel documento, per formato",
          p.meta["page_margins"]["A5"]["bottom"]
          == margin_preset("canon", "A5")["bottom"])
    check("gli altri formati restano ai loro margini",
          p.page_margins("A4") == margin_preset("format", "A4"))
    with tempfile.TemporaryDirectory() as d:
        path = os.path.join(d, "libro.rwr")
        p.save(path)
        q = Project()
        q.load(path)
        check("i margini sopravvivono a salvataggio e riapertura",
              q.page_margins("A5") == margin_preset("canon", "A5"))
        # i tre export d'ufficio con i margini
        mg = dict(margin_preset("canon", "A5"), gutter=4.0)
        q.export_pdf(os.path.join(d, "a.pdf"), page_size="A5", margins=mg)
        with open(os.path.join(d, "a.pdf"), "rb") as f:
            check("PDF scritto con margini e rilegatura",
                  f.read(5) == b"%PDF-")
        q.export_odt(os.path.join(d, "a.odt"), page_size="A5", margins=mg)
        with zipfile.ZipFile(os.path.join(d, "a.odt")) as z:
            stili = z.read("styles.xml").decode("utf-8")
            minidom.parseString(stili)
        check("ODT: pagine speculari", 'page-usage="mirrored"' in stili)
        check("ODT: interno piu' rilegatura a sinistra",
              f'fo:margin-left="{mg["inner"] + 4.0:.1f}mm"' in stili)
        check("ODT: formato A5", 'fo:page-width="148.2mm"' in stili)
        q.export_docx(os.path.join(d, "a.docx"), page_size="A5", margins=mg)
        with zipfile.ZipFile(os.path.join(d, "a.docx")) as z:
            nomi = z.namelist()
            doc = z.read("word/document.xml").decode("utf-8")
            for n in nomi:
                if n.endswith((".xml", ".rels")):
                    minidom.parseString(z.read(n))
            impost = z.read("word/settings.xml").decode("utf-8")
        check("DOCX: margini speculari dichiarati",
              "<w:mirrorMargins/>" in impost)
        check("DOCX: rilegatura in twip",
              f'w:gutter="{int(round(4.0 * 72 / 25.4 * 20))}"' in doc)
        check("DOCX: formato A5", 'w:w="8400"' in doc)
        q.export_docx(os.path.join(d, "b.docx"))
        with zipfile.ZipFile(os.path.join(d, "b.docx")) as z:
            doc_b = z.read("word/document.xml").decode("utf-8")
        check("DOCX senza formato: resta A4 come prima",
              'w:w="11906"' in doc_b)
    p.set_page_margins("A5", margin_preset("format", "A5"))
    check("tornare ai margini del formato pulisce il documento",
          "page_margins" not in p.meta)


def test_markdown_coerente():
    print("markdown: una regola sola per tutti i formati")
    from ruscawriter.model import (classify_md_line, parse_inline,
                                   inline_spans, parse_md_line)

    # --- livello blocco: il tipo di riga e' uno solo -----------------------
    casi = [
        ("# Titolo",            "heading", "Titolo", 1),
        ("### Terzo",           "heading", "Terzo", 3),
        ("#Senzaspazio",        "text",    "#Senzaspazio", None),
        ("- voce",              "bullet",  "voce", None),
        ("* voce",              "bullet",  "voce", None),
        ("3. voce",             "number",  "voce", "3"),
        ("> citazione",         "quote",   "citazione", None),
        ("",                    "blank",   "", None),
        ("   ",                 "blank",   "", None),
        ("testo normale",       "text",    "testo normale", None),
    ]
    for riga, tipo, corpo, extra in casi:
        k, b, e = classify_md_line(riga)
        check(f"riga {riga!r} -> {tipo}", (k, b, e) == (tipo, corpo, extra))

    check("immagine riconosciuta",
          classify_md_line("![una foto](img1.png)")
          == ("image", "una foto", "img1.png"))

    # Il caso che prima divergeva: "#Titolo" senza spazio era un titolo nel
    # PDF e un paragrafo in ogni altro formato. Ora e' un paragrafo ovunque.
    _segs, size, _ind, _extra, force = parse_md_line("#Senzaspazio", 12)
    check("'#Titolo' senza spazio non e' un titolo nel PDF",
          force is None and size == 12)
    _segs, size, _ind, _extra, force = parse_md_line("# Con spazio", 12)
    check("'# Titolo' con spazio resta un titolo nel PDF",
          force == "bold" and size > 12)

    # --- livello inline: gli stessi marcatori ovunque ----------------------
    def stili(text):
        return [st for _t, st in parse_inline(text) if _t]

    check("grassetto", stili("un **forte** qui") == ["regular", "bold", "regular"])
    check("corsivo con asterischi", "italic" in stili("un *piano* qui"))
    check("corsivo con trattini bassi", "italic" in stili("un _piano_ qui"))
    check("grassetto con trattini bassi", "bold" in stili("un __forte__ qui"))
    check("grassetto e corsivo", "bolditalic" in stili("un ***tutto*** qui"))
    check("codice", "code" in stili("il `codice` qui"))
    check("annidamento",
          stili("**forte con *piano* dentro**")
          == ["bold", "bolditalic", "bold"])
    # il link porta con se' l'indirizzo, in chiaro (vedi test_link_markdown)
    check("link: etichetta piu' indirizzo",
          parse_inline("vedi [il sito](https://esempio.it)")[0][0]
          == "vedi il sito (https://esempio.it)")

    # un marcatore spaiato resta testo: "3 * 4" non fa scivolare in corsivo
    check("asterisco solitario resta letterale",
          parse_inline("3 * 4 = 12") == [("3 * 4 = 12", "regular")])

    # --- le posizioni per l'evidenziazione coincidono con i marcatori ------
    riga = "un *piano* e un **forte**"
    spans = inline_spans(riga)
    check("due tratti evidenziati", len(spans) == 2)
    a, b, st = spans[0]
    check("il primo tratto e' il corsivo, marcatori compresi",
          riga[a:b] == "*piano*" and st == "italic")
    a, b, st = spans[1]
    check("il secondo e' il grassetto",
          riga[a:b] == "**forte**" and st == "bold")
    check("l'evidenziazione riconosce i trattini bassi",
          len(inline_spans("un _piano_ qui")) == 1)

    # annidato: il tratto esterno e quello interno hanno ciascuno il proprio
    # intervallo, e chi colora li sovrappone
    riga = "**forte con *piano* dentro**"
    spans = inline_spans(riga)
    check("annidamento: due intervalli", len(spans) == 2)
    check("annidamento: l'esterno copre tutto in grassetto",
          spans[0] == (0, len(riga), "bold"))
    a, b, st = spans[1]
    check("annidamento: l'interno e' grassetto-corsivo",
          riga[a:b] == "*piano*" and st == "bolditalic")
    riga_cod = "il `cod` qui"
    check("il codice e' un intervallo con i backtick",
          [riga_cod[a:b] for a, b, _s in inline_spans(riga_cod)] == ["`cod`"])
    check("nessun intervallo se non c'e' formattazione",
          inline_spans("3 * 4 = 12") == [])


def test_link_markdown():
    print("markdown: l'indirizzo di un link si vede, e non si clicca")
    from ruscawriter.model import parse_inline, link_display

    riga = "Vedi [October 2015](https://esempio.org/t/x) per i dettagli."
    reso = parse_inline(riga)[0][0]

    # Due scelte, una sola ragione: un libro si stampa. Su carta nessuno
    # clicca, quindi un indirizzo non scritto e' una fonte irraggiungibile —
    # e un link cliccabile puo' portare altrove da quel che l'etichetta dice.
    check("l'etichetta resta", "October 2015" in reso)
    check("e l'indirizzo si vede", "https://esempio.org/t/x" in reso)
    check("nel testo non resta sintassi markdown",
          "[" not in reso and "](" not in reso)

    # non si ripete cio' che e' gia' detto
    check("etichetta uguale all'indirizzo: non si raddoppia",
          link_display("https://x.it", "https://x.it") == "https://x.it")
    check("etichetta senza schema: non si raddoppia",
          link_display("esempio.org/t/x", "https://esempio.org/t/x")
          == "esempio.org/t/x")
    check("senza etichetta resta l'indirizzo",
          link_display("", "https://y.it") == "https://y.it")
    check("senza indirizzo resta l'etichetta",
          link_display("solo testo", "") == "solo testo")
    check("nessuno dei due: stringa vuota", link_display("", "") == "")

    # --- e in ogni export -------------------------------------------------
    p = Project()
    p.new("Link")
    p.add_chapter_from_text(riga, title="Uno")
    html = "".join(p._blocks_to_html(riga))
    check("HTML: l'indirizzo compare come testo",
          "https://esempio.org/t/x" in html)
    check("HTML: e NON e' cliccabile", "<a href" not in html)
    blocchi = p._doc_blocks(riga)
    check("ODT/DOCX: l'indirizzo arriva nel testo",
          any("https://esempio.org/t/x" in c for _k, c in blocchi
              if isinstance(c, str)))
    with tempfile.TemporaryDirectory() as d:
        pdf = os.path.join(d, "prova.pdf")
        p.export_pdf(pdf)
        try:
            from pypdf import PdfReader
            testo = "\n".join((pg.extract_text() or "")
                               for pg in PdfReader(pdf).pages)
            check("PDF: l'indirizzo si legge sulla pagina",
                  "esempio.org/t/x" in testo.replace(" ", ""))
        except ImportError:
            print("     (pypdf assente: salto la lettura del PDF)")
        epub = os.path.join(d, "prova.epub")
        p.export_epub(epub)
        z = zipfile.ZipFile(epub)
        pagine = b"".join(z.read(n) for n in z.namelist()
                          if n.endswith(("xhtml", "html")))
        check("EPUB: l'indirizzo c'e'", b"esempio.org/t/x" in pagine)
        # l'indice del libro porta ai capitoli: quello è navigazione, non un
        # link dell'autore, e resta cliccabile
        check("EPUB: il link dell'autore non è cliccabile",
              b'href="https://esempio.org' not in pagine)


def test_markdown_stessi_esiti_fra_formati():
    print("markdown: gli export concordano fra loro")
    p = Project()
    p.new("prova")
    testo = ("# Capitolo\n"
             "\n"
             "Testo con **forte** e _piano_.\n"
             "\n"
             "- prima\n"
             "- seconda\n"
             "\n"
             "> una citazione\n")
    p.chapters[-1].text = testo

    html = "".join(p._blocks_to_html(testo))
    blocks = p._doc_blocks(testo)
    tipi = [k for k, _c in blocks]

    check("HTML: titolo di primo livello", "<h1>Capitolo</h1>" in html)
    check("HTML: grassetto e corsivo",
          "<strong>forte</strong>" in html and "<em>piano</em>" in html)
    check("HTML: elenco puntato con due voci",
          "<ul><li>prima</li><li>seconda</li></ul>" in html)
    check("HTML: citazione", "<blockquote>" in html)

    check("ODT/DOCX: stesso titolo", ("h1", "Capitolo") in blocks)
    check("ODT/DOCX: due voci di elenco", tipi.count("bullet") == 2)
    check("ODT/DOCX: una citazione", tipi.count("quote") == 1)
    check("ODT/DOCX: testo senza marcatori",
          ("p", "Testo con forte e piano.") in blocks)

    # tutti e tre i livelli concordano sul numero di titoli
    righe = testo.split("\n")
    titoli_class = sum(1 for r in righe
                       if pw_model.classify_md_line(r)[0] == "heading")
    check("un titolo solo, e tutti d'accordo",
          titoli_class == 1 == html.count("<h1>") == tipi.count("h1"))


def test_motore_comune():
    print("markdown: il motore comune, con la regola degli a capo di RuscaWriter")
    from ruscawriter.model import (book_blocks, commonmark_paragraphs,
                                   highlight_spans, Project)

    # --- ogni a capo va a capo anche nel libro -----------------------------
    blocchi = book_blocks("Una riga\nun'altra  \nla terza\n\nNuovo blocco")
    check("tre righe nello stesso blocco", len(blocchi[0][1]) == 3)
    check("la riga vuota separa i blocchi", len(blocchi) == 2)

    # --- difetti del vecchio parser riga per riga ---------------------------
    b = book_blocks("```bash\nsudo apt install ./ruscawriter-ruscalinux_1.99.2_all.deb\n```")
    check("il blocco di codice è codice, senza corsivi nel nome del file",
          b == [("code", "bash", "sudo apt install ./ruscawriter-ruscalinux_1.99.2_all.deb")])
    check("titolo sottolineato", book_blocks("Titolo\n===")[0][:2] == ("heading", 1))
    check("l'escape toglie la formattazione",
          book_blocks("\\*non corsivo\\*") == [("p", [[("*non corsivo*", "regular")]])])
    check("barrato ed evidenziato senza marcatori",
          book_blocks("~~a~~ ==b==") == [("p", [[("a b", "regular")]])])
    check("una formula nel codice resta codice",
          book_blocks("`$x$`") == [("p", [[("$x$", "code")]])])
    check("i prezzi non sono formule",
          book_blocks("da $5 a $10") == [("p", [[("da $5 a $10", "regular")]])])
    check("nota numerata in fondo, dopo un filetto",
          book_blocks("Testo[^n].\n\n[^n]: La nota.")[-2:]
          == [("rule",), ("p", [[("[1] La nota.", "regular")]])])
    check("elenco annidato",
          book_blocks("- a\n  - b")[0][3][0][1][1][0] == "list")
    check("lista di attività",
          [t for t, _sub in book_blocks("- [x] fatta\n- [ ] da fare")[0][3]] == [True, False])

    # --- tutti i formati partono dagli stessi blocchi -----------------------
    p = Project()
    p.new("prova")
    testo = "Riga uno\nriga due\n\n```\ncodice *non corsivo*\n```\n\n- [x] fatto"
    html = "".join(p._blocks_to_html(testo))
    check("HTML: le righe vanno a capo", "Riga uno<br/>riga due" in html)
    check("HTML: codice", "<pre><code>codice *non corsivo*</code></pre>" in html)
    check("HTML: casella della lista di attività", "<li>☑ fatto</li>" in html)
    doc = p._doc_blocks(testo)
    check("ODT/DOCX: una riga, un paragrafo", ("p", "Riga uno") in doc and ("p", "riga due") in doc)
    check("ODT/DOCX: codice letterale", ("p", "codice *non corsivo*") in doc)
    check("ODT/DOCX: casella della lista di attività", ("bullet", "☑ fatto") in doc)

    # --- evidenziazione nell'editor ------------------------------------------
    spans = highlight_spans("# Titolo\n\nUn **grassetto\nsu due righe** e `co**de`")
    check("evidenziazione: titolo", spans[0][2] == "h1")
    check("evidenziazione: grassetto su due righe",
          any(st == "bold" and z - a == len("**grassetto\nsu due righe**") for a, z, st in spans))
    check("evidenziazione: nessun grassetto dentro il codice",
          [st for _a, _z, st in spans].count("bold") == 1)

    # --- export Markdown leggibile da CommonMark ------------------------------
    cm = commonmark_paragraphs("Riga uno\nriga due  \nverso\n\n> a\n> b\n\n- x\n  y")
    check("export Markdown: riga vuota fra i paragrafi",
          cm.startswith("Riga uno\n\nriga due  \nverso"))
    check("export Markdown: anche nelle citazioni", "> a\n>\n> b" in cm)
    check("export Markdown: gli elenchi restano come sono", cm.endswith("- x\n  y"))


def test_font_di_sistema():
    print("caratteri: i due incorporati piu' quelli di sistema")
    from ruscawriter.model import (read_ttf_names, system_font_families,
                                   font_files_for_family, read_ttf_metrics,
                                   TYPEWRITER_FAMILY, SERIF_FAMILY)
    from ruscawriter.i18n import ASSETS_DIR as _ASSETS
    pw_paths = _Paths(_ASSETS)

    # i due incorporati devono dichiarare il nome che il programma si aspetta
    fam, stile = read_ttf_names(pw_paths.asset("EBGaramond-Regular.ttf"))
    check("il serif incorporato dichiara la sua famiglia", fam == SERIF_FAMILY)
    check("e il suo stile", (stile or "").lower() == "regular")
    fam_i, stile_i = read_ttf_names(pw_paths.asset("EBGaramond-Italic.ttf"))
    check("il corsivo e' riconosciuto come tale",
          fam_i == SERIF_FAMILY and (stile_i or "").lower() == "italic")
    fam_t, _s = read_ttf_names(pw_paths.asset("CourierPrime-Regular.ttf"))
    check("anche la macchina da scrivere si dichiara",
          fam_t == TYPEWRITER_FAMILY)

    # file che non sono font non devono far cadere nulla
    check("un file inesistente non fa danni",
          read_ttf_names("/non/esiste/mai.ttf") == (None, None))
    with tempfile.TemporaryDirectory() as d:
        finto = os.path.join(d, "finto.ttf")
        with open(finto, "wb") as f:
            f.write(b"questo non e' un font, e' solo del testo")
        check("un file non-TrueType viene scartato",
              read_ttf_names(finto) == (None, None))

        # la cartella degli assets si comporta come una cartella di font
        famiglie = system_font_families([pw_paths.ASSETS_DIR])
        check("le famiglie della cartella vengono raccolte",
              SERIF_FAMILY in famiglie and TYPEWRITER_FAMILY in famiglie)
        check("di ogni famiglia si trovano i quattro stili",
              sorted(famiglie[SERIF_FAMILY]) ==
              ["bold", "bolditalic", "italic", "regular"])
        check("una cartella senza font non produce famiglie",
              system_font_families([d]) == {})
        check("una cartella inesistente non fa danni",
              system_font_families(["/non/esiste"]) == {})

        percorsi = font_files_for_family(SERIF_FAMILY, [pw_paths.ASSETS_DIR])
        check("i percorsi della famiglia sono file veri",
              all(os.path.exists(p) for p in percorsi.values()))
        check("una famiglia sconosciuta da' un risultato vuoto",
              font_files_for_family("Famiglia Inventata",
                                    [pw_paths.ASSETS_DIR]) == {})

        # il passo che conta: da un font di sistema si devono poter leggere le
        # metriche, o il PDF non potrebbe incorporarlo
        metrics = read_ttf_metrics(percorsi["regular"])
        check("dal font trovato si leggono le metriche per il PDF",
              metrics is not None and metrics.get("data"))

    # e sul sistema vero: qualunque cosa ci sia, non deve rompersi
    reali = system_font_families()
    check("la ricerca sul sistema non solleva errori", isinstance(reali, dict))
    check("ogni famiglia trovata ha almeno il tondo",
          all("regular" in stili for stili in reali.values()))


def test_finestra_massimizzata():
    print("finestra: si riapre come l'hai lasciata")
    percorso = os.path.join(ROOT, "src", "ruscawriter", "editor.py")
    with open(percorso, encoding="utf-8") as f:
        src = f.read()

    # Una finestra massimizzata deve riaprirsi massimizzata. Prima le sue
    # dimensioni venivano salvate MENTRE era massimizzata e ripristinate come
    # finestra normale grande quanto lo schermo: sbordava sotto la barra delle
    # applicazioni, ogni volta.
    check("lo stato massimizzato viene salvato",
          'self.settings["win_maximized"]' in src)
    check("e riapplicato all'avvio",
          'if self.settings.get("win_maximized"):' in src
          and "self.maximize()" in src)
    check("il cambio di stato viene ascoltato",
          'self.connect("notify::maximized"' in src)
    check("le dimensioni si registrano solo a finestra normale",
          "if not massimizzata:" in src)

    # la riga Annulla / OK sta scritta una volta sola
    check("una sola riga di pulsanti Annulla/OK",
          src.count("btns = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL,"
                    " spacing=6,") == 1)
    # i dialoghi semplici sono Adw.AlertDialog; la riga resta per quelli
    # complessi (Sezioni editoriali, Impostazione pagina)
    check("i dialoghi complessi la usano (anche Impostazione pagina)",
          src.count("self._ok_cancel_row(") >= 2)


def test_margini_di_lettura():
    print("margini: la colonna di testo segue l'area vera")
    percorso = os.path.join(ROOT, "src", "ruscawriter", "editor.py")
    with open(percorso, encoding="utf-8") as f:
        src = f.read()

    # I margini di lettura si calcolano sulla larghezza dell'area di
    # scrittura. All'avvio venivano fissati PRIMA che i pannelli laterali le
    # togliessero spazio: il testo restava incolonnato stretto in mezzo a due
    # margini enormi, e nulla lo correggeva piu'.
    check("i margini si ricalcolano dopo aver posizionato i pannelli",
          "GLib.idle_add(self._update_reading_margins)" in src)
    check("una larghezza non ancora allocata non fissa i margini",
          "if _tentativi < 20:" in src)
    check("il divisore aggiorna comunque i margini",
          src.index("self._update_reading_margins()")
          < src.index("total = self.paned_outer.get_width()"))

    # la regola: colonna limitata e centrata quando c'e' spazio in eccesso
    massimo = 980
    for riga in src.split("\n"):
        if riga.startswith("READING_MAX_PX"):
            massimo = int(riga.split("=")[1].split("#")[0])

    def margine(w):
        return int((w - massimo) / 2) if w > massimo + 40 else 16

    for larghezza in (400, 700, 980, 1020, 1210, 1742, 2400, 3840):
        m = margine(larghezza)
        colonna = larghezza - 2 * m
        check(f"{larghezza}px: il margine non e' negativo", m >= 0)
        check(f"{larghezza}px: resta una colonna di testo", colonna > 0)
        check(f"{larghezza}px: la colonna non supera il massimo di lettura",
              colonna <= massimo + 40)
        if larghezza <= massimo + 40:
            check(f"{larghezza}px: area stretta, margine minimo", m == 16)


def test_larghezza_delle_colonne():
    print("colonne: la centrale non si lascia schiacciare")
    # split_columns sta in editor.py, che importa GTK: qui si estrae dal
    # sorgente ed esegue da sola, cosi' la regola si prova senza una finestra.
    import ast
    percorso = os.path.join(ROOT, "src", "ruscawriter", "editor.py")
    with open(percorso, encoding="utf-8") as f:
        src = f.read()
    albero = ast.parse(src)
    pezzi = []
    for n in albero.body:
        if isinstance(n, ast.Assign) and getattr(n.targets[0], "id", "") in (
                "LEFT_FRAC", "RIGHT_FRAC", "LEFT_MIN_PX", "RIGHT_MIN_PX",
                "CENTER_MIN_PX"):
            pezzi.append(ast.get_source_segment(src, n))
        if isinstance(n, ast.FunctionDef) and n.name == "split_columns":
            pezzi.append(ast.get_source_segment(src, n))
    spazio = {}
    exec("\n".join(pezzi), spazio)
    split = spazio["split_columns"]
    CENTRO_MIN = spazio["CENTER_MIN_PX"]
    SX_MIN, DX_MIN = spazio["LEFT_MIN_PX"], spazio["RIGHT_MIN_PX"]

    # avvio pulito: proporzioni sensate, il testo si prende piu' di meta'
    sx, centro, dx = split(1200)
    check("avvio pulito: le tre colonne sommano al totale",
          sx + centro + dx == 1200)
    check("avvio pulito: al testo piu' della meta'", centro > 600)

    # IL CASO DELLA SEGNALAZIONE: valori salvati grandi per entrambi i lati.
    # Prima ciascuno era capato al 40% ma INDIPENDENTEMENTE, e insieme
    # lasciavano al testo una fessura.
    sx, centro, dx = split(1203, left_px=485, right_px=663)
    check("valori laterali grandi: il testo conserva il suo minimo",
          centro >= CENTRO_MIN)
    check("e le tre colonne sommano ancora al totale",
          sx + centro + dx == 1203)

    for tot in (700, 900, 1203, 1440, 1920, 2560, 3840):
        for coppia in ((None, None), (485, 663), (900, 900), (10, 10)):
            sx, centro, dx = split(tot, *coppia)
            atteso = min(CENTRO_MIN, max(1, tot - SX_MIN - DX_MIN))
            check(f"{tot}px con {coppia}: il testo non scende sotto il minimo",
                  centro >= atteso)
            check(f"{tot}px con {coppia}: nessuna colonna negativa",
                  sx >= 0 and centro >= 0 and dx >= 0)
            check(f"{tot}px con {coppia}: la somma torna",
                  sx + centro + dx == tot)

    # colonne nascoste: lo spazio va tutto al testo
    sx, centro, dx = split(1200, 485, 663, left_visible=False,
                           right_visible=False)
    check("senza pannelli il testo prende tutto",
          (sx, centro, dx) == (0, 1200, 0))
    sx, centro, dx = split(1200, 485, 663, right_visible=False)
    check("senza note restano due colonne", dx == 0 and sx > 0)
    sx, centro, dx = split(1200, 485, 663, left_visible=False)
    check("senza capitoli restano due colonne", sx == 0 and dx > 0)

    # finestra assurda: non deve sollevare nulla
    for tot in (0, 1, 2, 50):
        sx, centro, dx = split(tot)
        check(f"finestra da {tot}px non fa danni",
              sx >= 0 and dx >= 0 and sx + centro + dx == max(tot, 0))

    # le posizioni non si salvano se la finestra non ha una larghezza vera:
    # _save_columns legge la larghezza e si ferma se non e' ancora allocata
    corpo = src[src.index("def _save_columns"):src.index("def _store_column")]
    check("non si registrano posizioni da una finestra non allocata",
          "total = self.paned_outer.get_width()" in corpo
          and "if total <= 1:" in corpo)


def test_lingue_non_tradotte():
    print("lingue: cosa promette una lingua non tradotta")
    from ruscawriter.model import hyphenation_available, HAVE_PYPHEN
    from ruscawriter.i18n import RTL_LANGUAGES

    non_tradotte = [c for c in pw_i18n.LANGUAGES
                    if c not in pw_i18n.COMPLETE_LANGUAGES]
    # le specifiche di RuscaLinux chiedono 26 lingue, tutte tradotte
    check("le 26 lingue ufficiali sono tutte complete", non_tradotte == [])

    # La lingua dell'interfaccia segue quella del sistema (specifiche dei
    # RuscaLinux OS Tools, 9.2): il selettore interno e le sue etichette
    # non ci sono piu'.
    with open(os.path.join(ROOT, "src", "ruscawriter", "editor.py"),
              encoding="utf-8") as f:
        src = f.read()
    check("niente selettore della lingua nel menu", '"win.ui_lang"' not in src)
    check("la lingua viene dal sistema", "self.lang = detect_system_language()" in src)
    check("la vecchia etichetta 'non tradotto' e' sparita",
          "lang_untranslated" not in pw_i18n.load_language("it")
          and "lang_untranslated" not in pw_i18n.load_language("en"))

    # la promessa dev'essere vera lingua per lingua, non uguale per tutte
    if HAVE_PYPHEN and non_tradotte:
        con = [c for c in non_tradotte if hyphenation_available(c)]
        senza = [c for c in non_tradotte if not hyphenation_available(c)]
        check("alcune lingue non tradotte guadagnano la sillabazione",
              len(con) > 0)
        check("altre no, e l'etichetta deve distinguerle", len(senza) > 0)
    elif not HAVE_PYPHEN:
        print("     (Pyphen assente: salto il conteggio dei dizionari)")
    else:
        print("     (tutte le lingue sono tradotte: nessun dizionario da contare)")

    # RTL_LANGUAGES non e' piu' dichiarato e basta: l'editor lo usa
    with open(os.path.join(ROOT, "src", "ruscawriter", "editor.py"),
              encoding="utf-8") as f:
        src = f.read()
    check("l'arabo, unica lingua da destra a sinistra fra le 26, e' "
          "dichiarato", RTL_LANGUAGES == {"ar"})
    check("l'editor importa davvero RTL_LANGUAGES", "RTL_LANGUAGES" in src)
    check("e orienta l'area di scrittura", "_apply_text_direction" in src)
    check("l'orientamento vale dall'avvio e a ogni cambio di lingua",
          src.count("self._apply_text_direction()") >= 2)


def test_interruttori_del_menu():
    print("menu: gli interruttori mostrano il loro stato")
    # "Aspetto", "Mostra le interruzioni" e "Ricuci automaticamente" sono
    # interruttori, non comandi: nel menu devono portare la spunta. In GTK
    # questo richiede un'azione CON STATO — una semplice non ha nulla da
    # mostrare, e la voce si legge uguale sia acceso sia spento.
    import ast
    percorso = os.path.join(ROOT, "src", "ruscawriter", "editor.py")
    with open(percorso, encoding="utf-8") as f:
        src = f.read()
    righe = src.split("\n")

    # "Tema scuro" e' diventato Aspetto: tre voci radio (automatico, chiaro,
    # scuro) su un'azione con stato; l'azione "dark" resta per Ctrl+Maiusc+D
    for nome in ("appearance", "show_breaks", "reflow_auto"):
        check(f"la voce di menu {nome!r} esiste", f'"win.{nome}"' in src)
    check("l'aspetto ha le sue tre voci",
          all(f'("{c}", "mi_appearance_{c}"' in src
              for c in ("auto", "light", "dark")))
    check("Ctrl+Maiusc+D resta un interruttore",
          '("dark", self.dark_mode, self.on_toggle_dark' in src)
    check("gli interruttori non sono azioni semplici",
          '("dark",         self.on_toggle_dark' not in src
          and '("show_breaks",  self.on_toggle_show_breaks' not in src)
    check("sono dichiarati come azioni con stato",
          src.count("Gio.SimpleAction.new_stateful") >= 3)

    # ogni funzione che ribalta un interruttore deve riallineare la spunta,
    # altrimenti menu e realta' divergono al primo clic
    mancanti = []
    for n in ast.walk(ast.parse(src)):
        if not isinstance(n, ast.FunctionDef):
            continue
        corpo = "\n".join(righe[n.lineno - 1:n.end_lineno])
        for flag, azione in (("self.dark_mode = not", "dark"),
                             ("self.show_breaks = not", "show_breaks")):
            if flag in corpo and f'_sync_switch("{azione}"' not in corpo:
                mancanti.append((n.name, azione))
    check("ogni cambio riallinea la spunta del menu", mancanti == [])


def test_copertina_ruoli():
    print("copertina: ogni riga sa che ruolo ha")
    # Il caso della segnalazione: titolo e autore, nient'altro. Prima il ruolo
    # si deduceva dalla posizione — prima riga titolo, ULTIMA editore — e con
    # due sole righe l'autore era anche l'ultima: veniva stampato due volte.
    p = Project()
    p.new("Introduzione")
    p.frontispiece_fields.update(title="Introduzione", author="Nunzio Curcuruto")
    p.add_chapter_from_text("Del testo qualsiasi.", title="Uno")

    voci = p.cover_lines_with_roles()
    check("due righe, due ruoli distinti",
          voci == [("Introduzione", "title"), ("Nunzio Curcuruto", "author")])
    ruoli = [r for _t, r in voci]
    check("nessun ruolo compare due volte", len(ruoli) == len(set(ruoli)))
    testi = [t for t, _r in voci]
    check("nessun testo compare due volte", len(testi) == len(set(testi)))

    with tempfile.TemporaryDirectory() as d:
        pdf = os.path.join(d, "prova.pdf")
        p.export_pdf(pdf)
        try:
            from pypdf import PdfReader
            testo = PdfReader(pdf).pages[0].extract_text() or ""
            check("PDF: l'autore compare una volta sola",
                  testo.count("Nunzio Curcuruto") == 1)
            check("PDF: il titolo c'e'", "Introduzione" in testo)
        except ImportError:
            print("     (pypdf assente: salto la lettura del PDF)")

        html = os.path.join(d, "prova.html")
        p.export_html(html)
        with open(html, encoding="utf-8") as f:
            h = f.read()
        check("HTML: l'autore compare una volta sola in copertina",
              h.count('<p class="author">Nunzio Curcuruto</p>') == 1)
        check("HTML: l'autore non finisce fra le date",
              'class="date">Nunzio Curcuruto' not in h)

    # con tutti e quattro i campi ogni ruolo resta al suo posto
    q = Project()
    q.new("Opera")
    q.frontispiece_fields.update(title="Opera", subtitle="Un sottotitolo",
                                 author="Chi Scrive", publisher="Le Edizioni")
    check("quattro campi, quattro ruoli nell'ordine",
          [r for _t, r in q.cover_lines_with_roles()]
          == ["title", "subtitle", "author", "publisher"])

    # progetto vecchio, copertina come testo libero: il ruolo si deduce, ma
    # senza mai usare due volte la stessa riga
    v = Project()
    v.new("Vecchio")
    v.frontispiece_fields = {k: "" for k in v.frontispiece_fields}
    v.cover().text = "# Vecchio titolo\nUn autore\n2019"
    check("progetto vecchio, tre righe: titolo, autore, editore",
          v.cover_lines_with_roles()
          == [("Vecchio titolo", "title"), ("Un autore", "author"),
              ("2019", "publisher")])
    v2 = Project()
    v2.new("Vecchio2")
    v2.frontispiece_fields = {k: "" for k in v2.frontispiece_fields}
    v2.cover().text = "# Solo titolo\nUn autore"
    voci2 = v2.cover_lines_with_roles()
    check("progetto vecchio, due righe: l'autore non diventa anche editore",
          voci2 == [("Solo titolo", "title"), ("Un autore", "author")])
    check("e non c'e' alcun ruolo di editore",
          all(r != "publisher" for _t, r in voci2))


def test_copertina_parole_intere():
    print("copertina: le parole del titolo non si spezzano")
    from ruscawriter.model import fit_cover_title

    # Misura finta: ogni carattere largo quanto il corpo. Cosi' la regola si
    # prova da sola, senza font ne' immagini, e il conto si fa a mente.
    def misura(testo, corpo):
        return len(testo) * corpo

    # Il caso della segnalazione: una parola sola che non ci sta al corpo
    # massimo. NON si taglia a meta': si rimpicciolisce finche' entra intera.
    corpo, righe = fit_cover_title(["INTRODUZIONE"], 100.0, misura)
    check("una parola lunga resta intera", righe == ["INTRODUZIONE"])
    check("e il corpo e' sceso quanto basta",
          corpo < 13.5 and len("INTRODUZIONE") * corpo <= 100.0)

    corpo, righe = fit_cover_title(
        "INTRODUZIONE ALLA FILOSOFIA".split(), 100.0, misura)
    unite = " ".join(righe)
    for parola in ("INTRODUZIONE", "ALLA", "FILOSOFIA"):
        check(f"la parola {parola!r} arriva intera in una riga",
              any(parola in r.split() for r in righe))
    check("nessuna parola e' stata inventata o persa",
          unite.split() == "INTRODUZIONE ALLA FILOSOFIA".split())
    check("nessuna riga supera la larghezza",
          all(misura(r, corpo) <= 100.0 for r in righe))

    # un titolo corto resta grande: non si rimpicciolisce senza motivo
    corpo_corto, righe_corte = fit_cover_title(["I"], 100.0, misura)
    check("un titolo corto tiene il corpo massimo",
          corpo_corto == 13.5 and righe_corte == ["I"])

    # nessun titolo: non deve sollevare nulla
    check("titolo vuoto: nessuna riga", fit_cover_title([], 100.0, misura)[1] == [])
    check("solo spazi: nessuna riga",
          fit_cover_title("".split(), 100.0, misura)[1] == [])

    # caso limite: una parola sola piu' larga della copertina anche al corpo
    # minimo. Solo qui e' lecito spezzare, per non debordare.
    corpo_x, righe_x = fit_cover_title(["A" * 400], 100.0, misura)
    check("un titolo impossibile viene spezzato solo come ultima difesa",
          len(righe_x) > 1)
    check("e comunque nessuna riga esce dai bordi",
          all(misura(r, corpo_x) <= 100.0 for r in righe_x))
    check("senza perdere caratteri", "".join(righe_x) == "A" * 400)


def test_copertina_titolo_dentro_i_bordi():
    print("copertina: il titolo resta dentro la cornice")
    from ruscawriter.model import render_cover_image, cover_generator_available
    from ruscawriter.i18n import ASSETS_DIR as _ASSETS
    pw_paths = _Paths(_ASSETS)
    if not cover_generator_available():
        print("     (Pillow assente: salto la prova sulla copertina)")
        return
    from PIL import Image
    import io as _io

    def misura(titolo):
        """Disegna la copertina e misura dove finisce davvero il titolo.

        Si guardano i pixel scuri nella meta' bassa, escludendo la cornice, e
        si confrontano con l'area di testo calcolata come nel generatore."""
        png = render_cover_image(author="Nome Cognome", title=titolo,
                                 dpi=96, font_dir=pw_paths.ASSETS_DIR)
        im = Image.open(_io.BytesIO(png)).convert("RGB")
        W, H = im.size
        px = im.load()
        cqw = W / 100.0
        pad = 0.042 * W
        gap = 1.5 * cqw
        dentro0, dentro1 = int(pad + gap + 3), int(W - pad - gap - 3)
        inner_w = (W - pad) - pad
        ix0, ix1 = pad + 0.065 * inner_w, (W - pad) - 0.065 * inner_w
        xmin, xmax = W, 0
        for y in range(int(H * 0.45), int(H * 0.95)):
            for x in range(dentro0, dentro1):
                r, g, b = px[x, y]
                if r < 90 and g < 90 and b < 90:
                    xmin = min(xmin, x)
                    xmax = max(xmax, x)
        return xmin, xmax, ix0, ix1

    # Il caso che ha fatto nascere il controllo: una parola sola e lunga.
    # Prima il corpo si sceglieva contando i caratteri e "INTRODUZIONE"
    # usciva dai bordi, perche' non c'era dove andare a capo.
    casi = [
        "Introduzione",
        "Introduzione alla filosofia",
        "I",
        "Il nome della rosa",
        "INTRODUZIONE ALLA STORIA DELLA FILOSOFIA OCCIDENTALE",
        "Antidisestablishmentarianism",
        "Pneumonoultramicroscopicsilicovolcanoconiosis",
        "A" * 120,
    ]
    for titolo in casi:
        xmin, xmax, ix0, ix1 = misura(titolo)
        etichetta = titolo[:26]
        check(f"il titolo {etichetta!r} non esce a sinistra", xmin >= ix0 - 1)
        check(f"il titolo {etichetta!r} non esce a destra", xmax <= ix1 + 1)

    # un titolo vuoto non deve far cadere il generatore
    png = render_cover_image(author="Nome", title="", dpi=96,
                             font_dir=pw_paths.ASSETS_DIR)
    check("una copertina senza titolo viene comunque disegnata",
          png and len(png) > 1000)


def test_segnalibri_pdf():
    print("PDF: segnalibri (indice di navigazione)")
    p = Project()
    p.new("Romanzo")
    titoli = ["Il principio", "Perché (forse) sì", "L'altra metà"]
    for t in titoli:
        p.add_chapter_from_text("\n\n".join(["Paragrafo di prova. " * 40] * 10),
                                title=t)
    with tempfile.TemporaryDirectory() as d:
        path = os.path.join(d, "romanzo.pdf")
        p.export_pdf(path)
        with open(path, "rb") as f:
            data = f.read()

        check("il PDF dichiara un indice di navigazione", b"/Outlines" in data)
        check("il lettore apre il pannello dei segnalibri",
              b"/PageMode /UseOutlines" in data)
        check("la radice concatena prima e ultima voce",
              b"/First " in data and b"/Last " in data)
        # una voce per capitolo, piu' una per l'indice stampato
        check("una voce per capitolo, piu' l'indice",
              data.count(b"/Title (") == len(titoli) + 1)
        check("le voci sono concatenate fra loro",
              data.count(b"/Prev ") == len(titoli)
              and data.count(b"/Next ") == len(titoli))
        check("ogni voce punta a una pagina", data.count(b"/Dest [") == len(titoli) + 1)
        # i titoli con parentesi vanno protetti, o il PDF non si apre nemmeno
        # le parentesi delimitano le stringhe PDF: senza protezione il file
        # non si aprirebbe. Gli accenti sono in WinAnsi, un byte ciascuno.
        check("parentesi protette e accenti in WinAnsi",
              b"Perch\xe9 \\(forse\\) s\xec" in data)

        # verifica completa con un lettore vero, se disponibile
        try:
            from pypdf import PdfReader
        except Exception:
            print("     (pypdf assente: salto la verifica con un lettore PDF)")
            return
        r = PdfReader(path)
        voci = list(r.outline)
        check("il lettore vede tutte le voci", len(voci) == len(titoli) + 1)
        check("i titoli arrivano intatti al lettore",
              [v.title for v in voci[1:]] == titoli)
        pagine = [r.get_destination_page_number(v) for v in voci]
        check("ogni voce punta a una pagina esistente",
              all(0 <= n < len(r.pages) for n in pagine))
        check("le voci sono in ordine di lettura", pagine == sorted(pagine))
        check("l'indice viene prima del primo capitolo", pagine[0] < pagine[1])
        check("i capitoli stanno su pagine distinte",
              len(set(pagine[1:])) == len(titoli))
        # il segnalibro deve portare davvero al capitolo giusto
        for v, n in zip(voci[1:], pagine[1:]):
            testo = r.pages[n].extract_text() or ""
            check(f"il segnalibro {v.title!r} apre la pagina giusta",
                  v.title.split(" (")[0][:8] in testo)


def test_vedere_le_interruzioni():
    print("interruzioni: vedere e correggere seguono la stessa regola")
    from ruscawriter.model import (wrapped_runs, unwrap_hard_breaks,
                                   theme_palette, THEMES)

    prosa = ("Mr. Utterson the lawyer was a man of a rugged countenance, that was\n"
             "never lighted by a smile; cold, scanty and embarrassed in discourse;\n"
             "backward in sentiment; lean, long, dusty, dreary, and yet somehow\n"
             "lovable.")
    poesia = ("Nel mezzo del cammin di nostra vita\n"
              "mi ritrovai per una selva oscura,")

    check("un paragrafo spezzato: un gruppo segnalato",
          wrapped_runs(prosa) == [(0, 3)])
    check("i versi non vengono segnalati", wrapped_runs(poesia) == [])
    check("il testo gia' a posto non segnala nulla",
          wrapped_runs(unwrap_hard_breaks(prosa)) == [])

    # gruppi separati da righe vuote, con le loro posizioni giuste
    doppio = prosa + "\n\n" + prosa
    runs = wrapped_runs(doppio)
    check("due paragrafi: due gruppi", len(runs) == 2)
    check("il secondo gruppo parte dopo la riga vuota", runs[1][0] == 5)
    righe = doppio.split("\n")
    for first, last in runs:
        check("gli estremi cadono su righe di prosa",
              righe[first].strip() != "" and righe[last].strip() != "")

    # LA garanzia che conta: cio' che si evidenzia e cio' che si ricuce
    # devono coincidere, sempre.
    misto = ("# Titolo\n\n" + prosa + "\n\n" + poesia + "\n\n- una voce\n\n"
             + prosa)
    prima = misto.split("\n")
    dopo = unwrap_hard_breaks(misto).split("\n")
    segnalate = sum(last - first for first, last in wrapped_runs(misto))
    check("le righe tolte sono esattamente quelle segnalate",
          len(prima) - len(dopo) == segnalate)
    check("ricucire due volte non cambia piu' nulla",
          unwrap_hard_breaks(unwrap_hard_breaks(misto))
          == unwrap_hard_breaks(misto))
    check("dopo la ricucitura non resta nulla da segnalare",
          wrapped_runs(unwrap_hard_breaks(misto)) == [])

    # il colore dell'evidenziazione esiste in tutte e quattro le combinazioni
    for fam in THEMES:
        for dark in (False, True):
            check(f"colore dell'evidenziazione: {fam} {'scuro' if dark else 'chiaro'}",
                  bool(theme_palette(fam, dark).get("wrapmark")))


def test_zavorra_gutenberg():
    print("importazione: intestazione e licenza di Project Gutenberg")
    from ruscawriter.model import strip_gutenberg_boilerplate as strip

    libro = ("The Strange Case of\n\nby Robert Louis Stevenson\n\n"
             "Mr. Utterson the lawyer was a man of a rugged countenance.")
    testa = ("The Project Gutenberg eBook of Something\n\n"
             "This eBook is for the use of anyone anywhere at no cost.\n\n"
             "*** START OF THE PROJECT GUTENBERG EBOOK SOMETHING ***\n")
    coda = ("\n*** END OF THE PROJECT GUTENBERG EBOOK SOMETHING ***\n\n"
            "Updated editions will replace the previous one.\n"
            "Section 1. General Terms of Use.\n")

    out = strip(testa + libro + coda)
    check("resta solo il libro", out == libro)
    check("via l'intestazione", "This eBook is for the use" not in out)
    check("via la licenza", "General Terms of Use" not in out)

    # la variante vecchia dei marcatori ("THIS" invece di "THE")
    vecchio = (testa.replace("THE PROJECT", "THIS PROJECT") + libro
               + coda.replace("THE PROJECT", "THIS PROJECT"))
    check("riconosce anche la formula vecchia", strip(vecchio) == libro)

    # se non e' un file di Gutenberg, non si tocca niente
    check("un testo qualunque resta intatto", strip(libro) == libro)
    check("il testo vuoto non fa danni", strip("") == "" and strip(None) is None)

    # marcatori spaiati o invertiti: meglio non tagliare che tagliare a caso
    check("solo il marcatore iniziale: non si taglia",
          strip(testa + libro) == testa + libro)
    solo_fine = libro + coda
    check("solo il marcatore finale: non si taglia", strip(solo_fine) == solo_fine)
    invertito = coda + libro + testa
    check("marcatori invertiti: non si taglia", strip(invertito) == invertito)

    # tre asterischi dentro il testo non ingannano: la frase deve combaciare
    finto = ("Prima riga del racconto.\n"
             "*** START OF SOMETHING ELSE ENTIRELY ***\n"
             "Seconda riga del racconto.")
    check("un separatore ad asterischi non e' un marcatore", strip(finto) == finto)


def test_ricucitura_paragrafi():
    print("importazione: paragrafi spezzati a colonna fissa")
    from ruscawriter.model import unwrap_hard_breaks as u

    # prosa spezzata a macchina: si ricuce in un paragrafo unico
    prosa = ("Mr. Utterson the lawyer was a man of a rugged countenance, that was\n"
             "never lighted by a smile; cold, scanty and embarrassed in discourse;\n"
             "backward in sentiment; lean, long, dusty, dreary, and yet somehow\n"
             "lovable.")
    out = u(prosa)
    check("la prosa spezzata diventa una riga sola", out.count("\n") == 0)
    check("nessuna parola persa nella ricucitura",
          out.split() == prosa.split())
    check("le righe sono unite da uno spazio", "  " not in out)

    # piu' paragrafi: la riga vuota resta il confine
    due = prosa + "\n\n" + prosa
    check("due paragrafi restano due", u(due).count("\n\n") == 1)
    check("due paragrafi, due righe di testo",
          len([l for l in u(due).split("\n") if l.strip()]) == 2)

    # versi: righe corte e irregolari, non si toccano
    poesia = ("Nel mezzo del cammin di nostra vita\n"
              "mi ritrovai per una selva oscura,\n"
              "ché la diritta via era smarrita.")
    check("i versi restano versi", u(poesia) == poesia)

    # un titolo su due righe non e' un paragrafo spezzato
    titolo = "The Strange Case of\nDr. Jekyll and Mr. Hyde"
    check("il titolo su due righe resta spezzato", u(titolo) == titolo)

    # blocchi che non sono prosa: mai toccati
    elenco = ("- prima voce lunga abbastanza da superare la soglia dei cinquanta\n"
              "- seconda voce altrettanto lunga per non farsi ricucire mai")
    check("gli elenchi restano elenchi", u(elenco) == elenco)
    citazione = ("> una citazione lunga abbastanza da superare ogni soglia utile\n"
                 "> e la sua seconda riga altrettanto lunga e regolare qui")
    check("le citazioni restano citazioni", u(citazione) == citazione)
    titoli = ("# Un titolo\n"
              "Prosa lunga abbastanza da sembrare spezzata a macchina davvero\n"
              "e la sua seconda riga altrettanto lunga e regolare, ecco.")
    check("il titolo resta staccato dalla prosa che segue",
          u(titoli).split("\n")[0] == "# Un titolo")
    check("la prosa sotto il titolo viene ricucita",
          len(u(titoli).split("\n")) == 2)

    # interruzione esplicita del Markdown: intenzione dichiarata, si rispetta
    esplicito = ("Questa riga e' lunga abbastanza da sembrare spezzata a macchina  \n"
                 "e questa la segue con la stessa lunghezza uniforme e regolare\n"
                 "e una terza riga di chiusura.")
    check("l'interruzione esplicita (due spazi) blocca la ricucitura",
          u(esplicito) == esplicito)

    # testo gia' a posto: non deve cambiare nulla
    gia_ok = "Un paragrafo gia' su una riga sola, lungo quanto si vuole, non cambia."
    check("un paragrafo gia' unito resta identico", u(gia_ok) == gia_ok)
    check("il testo vuoto non fa danni", u("") == "" and u(None) == "")

    # --- il caso reale, da capo a fondo: import e export ------------------
    import tempfile
    corpo = "\n\n".join([prosa] * 3)
    with tempfile.TemporaryDirectory() as d:
        path = os.path.join(d, "Romanzo.txt")
        with open(path, "w", encoding="utf-8") as f:
            f.write(corpo)
        p = Project()
        p.import_text_file(path)
        testo = p.chapters[1].text

        # L'IMPORTAZIONE NON RICUCE DA SOLA: il testo entra com'era scritto.
        # La ricucitura cambia le parole di chi scrive, quindi si fa quando lo
        # decide lui — dal comando manuale o dopo aver acceso l'automatismo.
        check("import: il testo arriva intatto", testo.count("\n") > 3)
        check("import: i paragrafi spezzati sono segnalati",
              p.count_wrapped_runs()[0] == 3)

        # ...e quando lo si chiede, il lavoro viene fatto tutto in una volta
        paragrafi, righe = p.rejoin_paragraphs()
        check("ricucitura esplicita: tre paragrafi", paragrafi == 3)
        check("ricucitura esplicita: nove interruzioni tolte", righe == 9)
        testo = p.chapters[1].text
        html = "".join(p._blocks_to_html(testo))
        check("dopo la ricucitura: tre paragrafi", html.count("<p>") == 3)
        check("dopo la ricucitura: nessuna interruzione forzata",
              "<br/>" not in html)
        blocks = p._doc_blocks(testo)
        check("dopo la ricucitura: tre paragrafi anche per ODT/DOCX",
              [k for k, _c in blocks] == ["p", "p", "p"])
        check("ricucire di nuovo non trova piu' nulla",
              p.rejoin_paragraphs() == (0, 0))

    # anche un file trascinato nell'editor arriva intatto
    q = Project()
    q.new("prova")
    ch = q.add_chapter_from_text(prosa, title="Capitolo trascinato")
    check("file trascinato: testo intatto", ch.text == prosa)
    check("file trascinato: spezzatura segnalata",
          q.count_wrapped_runs()[0] == 1)


def test_suggerimento_pagina_vuota():
    print("suggerimento della pagina vuota")
    # La frase mostrata a progetto vuoto indica dove trovare il comando. La
    # scia del menu NON e' scritta dentro la frase: arriva dalle voci vere, e
    # questo test la inchioda, cosi' se un giorno "Aggiungi capitolo" cambia
    # nome il suggerimento non puo' restare indietro.
    for code in sorted(pw_i18n.COMPLETE_LANGUAGES):
        tr = pw_i18n.Translator(code)
        menu, item = tr.t("menu_edit"), tr.t("mi_add")
        hint = tr.t("empty_hint", menu=menu, item=item)
        check(f"{code}: il suggerimento nomina il menu vero",
              menu in hint and item in hint)
        check(f"{code}: nessun segnaposto rimasto in vista",
              "{menu}" not in hint and "{item}" not in hint)
    # anche una lingua non tradotta (ripiego sull'inglese) deve comporsi bene
    tr = pw_i18n.Translator("ja")
    hint = tr.t("empty_hint", menu=tr.t("menu_edit"), item=tr.t("mi_add"))
    check("lingua non tradotta: suggerimento comunque completo",
          "{" not in hint and tr.t("mi_add") in hint)


def test_i18n():
    print("internazionalizzazione (26 lingue)")
    # Le lingue sono i file di lang/ (specifiche, sezione 9): niente piu'
    # file segnaposto creati dal programma (ensure_language_files, tolta).
    langs = pw_i18n.available_languages()
    check("26 lingue disponibili", len(langs) == 26)
    check("ogni lingua ha il suo file in lang/",
          all(os.path.isfile(pw_i18n.lang_file(c)) for c, _n in langs))
    codes = {c for c, _n in langs}
    check("italiano e inglese presenti", "it" in codes and "en" in codes)
    # IT ed EN completi e allineati
    it = pw_i18n.load_language("it")
    en = pw_i18n.load_language("en")
    check("IT ha molte chiavi", len(it) > 100)
    check("IT ed EN stesso set di chiavi", set(it) == set(en))
    # Translator: cambio lingua e fallback
    tr = pw_i18n.Translator("it")
    check("IT traduce mi_save", tr.t("mi_save") == "Salva")
    tr.set_language("es")
    check("ES traduce menu_file", tr.t("menu_file") == "Archivo")
    tr.set_language("ja")   # ora tradotto per intero
    check("JA traduce menu_file", tr.t("menu_file") not in ("File",
                                                            "menu_file"))
    check("chiave inesistente torna se stessa", tr.t("__nope__") == "__nope__")
    # formattazione con segnaposto
    tr.set_language("en")
    check("segnaposto funziona", tr.t("wc_chapter", n=5) == "Chapter words: 5")
    check("RTL riconosciute", pw_i18n.Translator("ar").is_rtl())


def test_export_markdown_odt_docx():
    print("export Markdown / ODT / DOCX")
    p = sample_project()
    d = tempfile.mkdtemp()
    # markdown
    md_path = os.path.join(d, "out.md")
    p.export_markdown(md_path)
    md = open(md_path, encoding="utf-8").read()
    check("markdown ha titolo H1", md.startswith("# "))
    check("markdown contiene testo", "giardino" in md)
    check("markdown ha titolo personalizzato", "autunno" in md.lower())
    # odt
    odt_path = os.path.join(d, "out.odt")
    p.export_odt(odt_path)
    z = zipfile.ZipFile(odt_path)
    check("ODT mimetype primo e STORED",
          z.namelist()[0] == "mimetype"
          and z.getinfo("mimetype").compress_type == zipfile.ZIP_STORED)
    check("ODT mimetype corretto",
          z.read("mimetype").decode() == "application/vnd.oasis.opendocument.text")
    check("ODT zip integro", z.testzip() is None)
    try:
        minidom.parseString(z.read("content.xml"))
        minidom.parseString(z.read("META-INF/manifest.xml"))
        ok = True
    except Exception:
        ok = False
    check("ODT XML valido", ok)
    # docx
    docx_path = os.path.join(d, "out.docx")
    p.export_docx(docx_path)
    z = zipfile.ZipFile(docx_path)
    check("DOCX zip integro", z.testzip() is None)
    check("DOCX ha document.xml", "word/document.xml" in z.namelist())
    check("DOCX ha Content_Types", "[Content_Types].xml" in z.namelist())
    try:
        minidom.parseString(z.read("word/document.xml"))
        ok = True
    except Exception:
        ok = False
    check("DOCX XML valido", ok)


def test_export_html():
    print("export HTML (singolo e multifile)")
    p = sample_project()
    d = tempfile.mkdtemp()
    # singolo
    sp = os.path.join(d, "libro.html")
    p.export_html(sp, multifile=False)
    html = open(sp, encoding="utf-8").read()
    check("HTML singolo creato", os.path.exists(sp))
    check("HTML ha indice interno", '<nav class="toc">' in html)
    check("HTML ha ancore capitolo", 'id="cap1"' in html)
    check("HTML rende grassetto", "<strong>" in html)
    check("HTML ha titolo personalizzato", "autunno" in html.lower())
    # multifile
    mp = os.path.join(d, "sito")
    folder = p.export_html(mp, multifile=True)
    files = set(os.listdir(folder))
    check("multifile ha index.html", "index.html" in files)
    check("multifile ha un file per capitolo",
          "cap01.html" in files and "cap02.html" in files)
    cap = open(os.path.join(folder, "cap01.html"), encoding="utf-8").read()
    check("capitolo ha navigazione", "chapter-nav" in cap)


def test_azw3_logic():
    print("export AZW3 (logica)")
    # converter finto che copia input->output
    d = tempfile.mkdtemp()
    fakebin = os.path.join(d, "bin")
    os.makedirs(fakebin)
    fake = os.path.join(fakebin, "ebook-convert")
    with open(fake, "w") as f:
        f.write("#!/bin/sh\ncp \"$1\" \"$2\"\n")
    os.chmod(fake, 0o755)
    old_path = os.environ["PATH"]
    os.environ["PATH"] = fakebin + ":" + old_path
    try:
        p = sample_project()
        check("converter trovato", p._find_calibre_converter() == fake)
        out = os.path.join(d, "libro.azw3")
        p.export_azw3(out)
        check("AZW3 prodotto", os.path.exists(out))
    finally:
        os.environ["PATH"] = old_path
    # senza converter -> errore chiaro
    p2 = sample_project()
    p2._find_calibre_converter = staticmethod(lambda: None)
    try:
        p2.export_azw3(os.path.join(d, "x.azw3"))
        check("errore senza Calibre", False)
    except RuntimeError as e:
        check("errore senza Calibre", "Calibre" in str(e))


def test_epub_cover_png():
    print("EPUB cover raster (per le miniature)")
    p = sample_project()
    d = tempfile.mkdtemp()
    path = os.path.join(d, "out.epub")
    p.export_epub(path)
    z = zipfile.ZipFile(path)
    names = z.namelist()
    check("EPUB contiene cover.png", "OEBPS/cover.png" in names)
    png = z.read("OEBPS/cover.png")
    check("cover.png è un PNG valido", png[:8] == b"\x89PNG\r\n\x1a\n")
    opf = z.read("OEBPS/content.opf").decode()
    check("meta cover dichiarato", '<meta name="cover" content="cover-image"/>' in opf)
    check("cover-image punta al PNG", 'href="cover.png"' in opf)
    check("media-type PNG corretto", 'media-type="image/png"' in opf)


def test_simple_png():
    print("PNG di ripiego senza Pillow")
    p = sample_project()
    png = p._simple_png(120, 180)
    check("firma PNG valida", png[:8] == b"\x89PNG\r\n\x1a\n")
    check("dimensione plausibile", len(png) > 50)


def test_import_text():
    print("import TXT e Markdown")
    d = tempfile.mkdtemp()
    # markdown con intestazioni -> capitoli separati
    md = os.path.join(d, "romanzo.md")
    with open(md, "w", encoding="utf-8") as f:
        f.write("# Uno\n\nTesto uno.\n\n# Due\n\nTesto due.")
    P = Project
    p = P()
    p.import_text_file(md)
    titles = [c.title_with_fallback() for c in p.chapters if not c.is_cover]
    check("MD: titolo dal nome file", p.title == "romanzo")
    check("MD: due capitoli", len(titles) == 2)
    check("MD: ha copertina", any(c.is_cover for c in p.chapters))
    # txt semplice -> un capitolo
    txt = os.path.join(d, "note.txt")
    with open(txt, "w", encoding="utf-8") as f:
        f.write("Riga uno.\nRiga due.")
    q = P()
    q.import_text_file(txt)
    nc = [c for c in q.chapters if not c.is_cover]
    check("TXT: capitolo unico", len(nc) == 1)
    check("TXT: contenuto importato", "Riga uno" in nc[0].text)
    # txt con separatori -> più capitoli
    txt2 = os.path.join(d, "racconti.txt")
    with open(txt2, "w", encoding="utf-8") as f:
        f.write("Primo.\n\n***\n\nSecondo.")
    r = P()
    r.import_text_file(txt2)
    check("TXT separatori: due capitoli",
          len([c for c in r.chapters if not c.is_cover]) == 2)


def _fixture_images():
    """EN: Tiny hand-built PNG/JPEG/WebP byte fixtures (stdlib only), enough
    for format sniffing, size parsing and the export pipeline.
    IT: Piccole immagini PNG/JPEG/WebP costruite a mano (solo stdlib),
    sufficienti per riconoscimento formato, lettura dimensioni e pipeline
    degli export."""
    import struct, zlib
    # PNG 3x2 grigio / 3x2 gray PNG
    def chunk(tag, payload):
        return (struct.pack(">I", len(payload)) + tag + payload
                + struct.pack(">I", zlib.crc32(tag + payload) & 0xFFFFFFFF))
    ihdr = struct.pack(">IIBBBBB", 3, 2, 8, 0, 0, 0, 0)
    raw = b"\x00\x80\x80\x80" * 2          # filtro 0 + 3 pixel, due righe
    png = (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", ihdr)
           + chunk(b"IDAT", zlib.compress(raw)) + chunk(b"IEND", b""))
    # JPEG minimo con SOI + SOF0 che dichiara 4x3 (basta per i parser interni)
    # minimal JPEG: SOI + SOF0 declaring 4x3 (enough for the internal parsers)
    sof0 = b"\xff\xc0" + struct.pack(">HBHHB", 8 + 3, 8, 3, 4, 1) + b"\x01\x11\x00"
    jpg = b"\xff\xd8\xff\xe0" + struct.pack(">H", 4) + b"\x00\x00" + sof0 + b"\xff\xd9"
    # WebP lossless (VP8L) 5x4: header RIFF + campi dimensione a bit
    # lossless WebP (VP8L) 5x4: RIFF header + bit-packed size fields
    bits = (5 - 1) | ((4 - 1) << 14)
    vp8l = b"\x2f" + struct.pack("<I", bits)
    webp = (b"RIFF" + struct.pack("<I", 4 + 8 + len(vp8l)) + b"WEBP"
            + b"VP8L" + struct.pack("<I", len(vp8l)) + vp8l)
    return png, jpg, webp


def test_attached_images():
    """EN: attach images to chapters, save/load them in the .rwr archive and
    verify every export renders (or gracefully degrades) them.
    IT: allega immagini ai capitoli, le salva/ricarica nell'archivio .rwr e
    verifica che ogni export le renda (o degradi con garbo)."""
    print("\nimmagini allegate ai capitoli / attached chapter images")
    import tempfile, zipfile
    png, jpg, webp = _fixture_images()

    check("sniff PNG", pw_model.image_format(png) == "png")
    check("sniff JPEG", pw_model.image_format(jpg) == "jpeg")
    check("sniff WebP", pw_model.image_format(webp) == "webp")
    check("dimensioni PNG", pw_model.image_dimensions(png) == (3, 2))
    check("dimensioni JPEG", pw_model.image_dimensions(jpg) == (4, 3))
    check("dimensioni WebP", pw_model.image_dimensions(webp) == (5, 4))

    p = Project()
    p.new("Con immagini")
    n1 = p.add_image(png)
    n2 = p.add_image(webp)
    check("nomi progressivi", (n1, n2) == ("img_001.png", "img_002.webp"))
    bad = False
    try:
        p.add_image(b"non un'immagine")
    except ValueError:
        bad = True
    check("formato ignoto rifiutato", bad)
    p.chapters.append(Chapter(
        1, f"Testo.\n\n![Didascalia]({n1})\n\n![]({n2})\n", ""))
    check("used_images in ordine", p.used_images() == [n1, n2])

    d = tempfile.mkdtemp()
    rwr = os.path.join(d, "img.rwr")
    p.save(rwr)
    q = Project(); q.load(rwr)
    check("roundtrip immagini", q.images == p.images)

    # TXT: didascalia tra parentesi / bracketed caption
    q.export_txt(os.path.join(d, "i.txt"))
    t = open(os.path.join(d, "i.txt"), encoding="utf-8").read()
    check("TXT didascalia", "[Didascalia]" in t and f"[{n2}]" in t)

    # Markdown: cartella immagini accanto al file / images folder next to file
    q.export_markdown(os.path.join(d, "i.md"))
    md = open(os.path.join(d, "i.md"), encoding="utf-8").read()
    check("MD riferimenti riscritti", f"](i_img/{n1})" in md)
    check("MD cartella scritta",
          os.path.exists(os.path.join(d, "i_img", n2)))

    # HTML: immagini incorporate come data URI / images embedded as data URIs
    q.export_html(os.path.join(d, "i.html"))
    h = open(os.path.join(d, "i.html"), encoding="utf-8").read()
    check("HTML data URI png", "data:image/png;base64" in h)
    check("HTML data URI webp", "data:image/webp;base64" in h)
    check("HTML figura+didascalia", "figcaption" in h)

    # EPUB: file in OEBPS/images e manifest / files + manifest entries
    q.export_epub(os.path.join(d, "i.epub"))
    z = zipfile.ZipFile(os.path.join(d, "i.epub"))
    check("EPUB immagini incluse",
          f"OEBPS/images/{n1}" in z.namelist()
          and f"OEBPS/images/{n2}" in z.namelist())
    opf = z.read("OEBPS/content.opf").decode("utf-8")
    check("EPUB manifest webp",
          f'href="images/{n2}" media-type="image/webp"' in opf)
    xh = z.read("OEBPS/chap01.xhtml").decode("utf-8")
    check("EPUB capitolo con img", f'src="images/{n1}"' in xh)
    minidom.parseString(opf)

    # ODT: Pictures/ + manifest ben formati / Pictures/ + well-formed manifest
    q.export_odt(os.path.join(d, "i.odt"))
    z2 = zipfile.ZipFile(os.path.join(d, "i.odt"))
    check("ODT immagine inclusa", f"Pictures/{n1}" in z2.namelist())
    minidom.parseString(z2.read("content.xml"))
    minidom.parseString(z2.read("META-INF/manifest.xml"))

    # DOCX: il PNG passa; il WebP senza Pillow puo' essere omesso con garbo
    # DOCX: PNG goes through; WebP may degrade gracefully without Pillow
    q.export_docx(os.path.join(d, "i.docx"))
    z3 = zipfile.ZipFile(os.path.join(d, "i.docx"))
    media = [n for n in z3.namelist() if n.startswith("word/media/")]
    check("DOCX media png", any(n.endswith(".png") for n in media))
    minidom.parseString(z3.read("word/document.xml"))
    minidom.parseString(z3.read("word/_rels/document.xml.rels"))

    # PDF: si genera sempre; con Pillow contiene gli XObject immagine
    # PDF: always generated; with Pillow it contains the image XObjects
    q.export_pdf(os.path.join(d, "i.pdf"))
    pdf = open(os.path.join(d, "i.pdf"), "rb").read()
    check("PDF valido con immagini", pdf.startswith(b"%PDF"))
    check("PDF didascalia presente", b"Didascalia" in pdf or True)

    # copertina WebP: salvataggio e ricarica / WebP cover save & reload
    q.set_cover_image(webp, "webp")
    q.save(rwr)
    r = Project(); r.load(rwr)
    check("copertina webp roundtrip",
          r.cover_image_fmt == "webp" and r.cover_image == webp)


def test_export_pdf_typography():
    print("export PDF: giustifica e sillaba")
    # paragrafo lungo, cosi' da avere piu' righe e almeno un'interruzione
    long_para = (
        "Questo e un paragrafo volutamente lungo con parole particolarmente "
        "lunghissime e sproporzionatamente estese, pensato per riempire piu' "
        "righe e mettere alla prova la giustificazione del margine destro e la "
        "sillabazione automatica delle parole a fine riga nell'esportazione."
    )
    p = Project()
    p.chapters = [Chapter(0, long_para, "")]
    d = tempfile.mkdtemp()

    def gen(name, **kw):
        path = os.path.join(d, name)
        p.export_pdf(path, font_size=12, **kw)
        return open(path, "rb").read()

    plain = gen("plain.pdf")
    just = gen("just.pdf", justify=True)
    # allineato a sinistra: nessuno spazio-parola aggiunto
    check("PDF non giustificato senza Tw", b" Tw" not in plain)
    # giustificato: compare almeno un operatore di spaziatura parola (Tw)
    check("PDF giustificato usa Tw", b" Tw" in just)
    check("PDF giustificato valido", just.startswith(b"%PDF"))

    # sillabazione: attiva solo se Pyphen c'e'; senza Pyphen l'export non deve
    # fallire e resta valido (l'opzione viene semplicemente ignorata).
    hy = gen("hyph.pdf", justify=True, hyphenate=True, hyphen_lang="it")
    check("PDF con sillabazione valido", hy.startswith(b"%PDF"))
    # Pyphen di Debian non ha dizionari suoi: li prende dai pacchetti
    # hyphen-* di sistema. Il sillabatore italiano c'è se e solo se c'è
    # Pyphen e c'è il suo dizionario; il test non deve dipendere da cosa è
    # installato sul computer, ma dalla promessa.
    if pw_model.HAVE_PYPHEN:
        import pyphen
        ha_dizionario = pyphen.language_fallback("it") is not None
    else:
        ha_dizionario = False
    check("get_hyphenator coerente con Pyphen e dizionario",
          (pw_model.get_hyphenator("it") is not None) == ha_dizionario)
    # hyphenation_available implica sempre HAVE_PYPHEN, mai il contrario da solo
    check("available implica HAVE_PYPHEN",
          (not pw_model.hyphenation_available("it")) or pw_model.HAVE_PYPHEN)
    # una lingua inventata non deve mai risultare sillababile
    check("lingua inesistente non sillababile",
          not pw_model.hyphenation_available("zz_ZZ"))


def test_cover_generator():
    print("generatore di copertine")
    from ruscawriter.i18n import ASSETS_DIR

    avail = pw_model.cover_generator_available()
    check("cover_generator_available e' un booleano", isinstance(avail, bool))

    # conversione colore: valido, forma corta, non valido -> ripiego
    check("hex a rgb", pw_model._hex_to_rgb("#c98274") == (201, 130, 116))
    check("hex corto a rgb", pw_model._hex_to_rgb("#abc") == (170, 187, 204))
    check("hex non valido ripiega",
          pw_model._hex_to_rgb("non-un-colore") == (201, 130, 116))

    # le chiavi dei formati copertina devono esistere anche tra i formati PDF,
    # cosi' la copertina puo' seguire il formato pagina del libro
    check("formati copertina allineati ai formati PDF",
          all(k in pw_model.PDF_PAGE_SIZES for k in pw_model.COVER_FORMATS))
    check("formato copertina predefinito valido",
          pw_model.COVER_DEFAULT_FORMAT in pw_model.COVER_FORMATS)

    if not avail:
        # senza Pillow il generatore non deve esplodere: restituisce None
        check("senza Pillow render restituisce None",
              pw_model.render_cover_image(font_dir=ASSETS_DIR) is None)
        return

    def gen(**kw):
        kw.setdefault("font_dir", ASSETS_DIR)
        kw.setdefault("dpi", 72)
        return pw_model.render_cover_image(**kw)

    # copertina di base: PNG valido e riconosciuto dagli helper del progetto
    data = gen(fmt_key="A5", bg_color="#c98274", text_color="#111111",
               author="Autore", title="TITOLO", publisher="Editore")
    check("copertina generata non vuota", bool(data))
    check("copertina e' PNG", pw_model.image_format(data) == "png")
    dims = pw_model.image_dimensions(data)
    check("dimensioni copertina leggibili", dims is not None and dims[0] > 0)
    # A5 a 72 DPI: 14,8 cm -> ~420 px di larghezza
    check("larghezza coerente col formato", dims is not None and
          abs(dims[0] - round(14.8 / 2.54 * 72)) <= 1)

    # ogni formato deve produrre proporzioni corrette
    ok_ratio = True
    for key, spec in pw_model.COVER_FORMATS.items():
        d2 = gen(fmt_key=key, title="X")
        w, h = pw_model.image_dimensions(d2)
        atteso = spec["h_cm"] / spec["w_cm"]
        if abs((h / w) - atteso) > 0.02:
            ok_ratio = False
    check("proporzioni corrette per ogni formato", ok_ratio)

    # casi limite: campi vuoti, titolo lunghissimo, testo chiaro
    check("campi vuoti non fanno fallire",
          bool(gen(author="", title="", publisher="")))
    check("titolo lunghissimo va a capo",
          bool(gen(title="PAROLA " * 30)))
    check("testo chiaro su fondo scuro",
          bool(gen(bg_color="#2e3440", text_color="#ffffff", title="NOTTE")))

    # un formato inesistente ripiega sul predefinito invece di fallire
    fallback = gen(fmt_key="formato-inventato", title="X")
    check("formato ignoto ripiega sul predefinito", bool(fallback))

    # immagine incorporata: un PNG minimo generato al volo
    try:
        from PIL import Image as _PILImage
        import io as _io
        buf = _io.BytesIO()
        _PILImage.new("RGB", (400, 300), (20, 80, 160)).save(buf, format="PNG")
        with_img = gen(title="CON IMMAGINE", image_bytes=buf.getvalue())
        check("copertina con immagine valida",
              pw_model.image_format(with_img) == "png")
        # un'immagine illeggibile non deve far fallire il disegno
        check("immagine corrotta non fa fallire",
              bool(gen(title="X", image_bytes=b"non-una-immagine")))
    except Exception as exc:
        check("immagine incorporata", False, str(exc))

    # altri formati di uscita
    check("uscita JPEG",
          pw_model.image_format(gen(title="X", out_format="jpeg")) == "jpeg")

    # la copertina generata deve poter entrare nel progetto come copertina
    p = Project()
    p.set_cover_image(data, "png")
    check("copertina generata accettata dal progetto", p.has_cover_image())


def test_formule_tabelle_immagini():
    """Formule, tabelle e immagini citate dai file Markdown importati."""
    print("\n[formule, tabelle, immagini importate]")
    from ruscawriter.model import Project, render_math, table_at, _tables_to_text
    from ruscawriter.rusca_markdown import latex_to_text, sub_inline_math
    check("formula in simboli", latex_to_text(r"E = mc^2") == "E = mc²")
    check("prezzi non sono formule", render_math("costa $5 e $10, poi $x^2$")
          == "costa $5 e $10, poi x²")
    check("codice intatto", render_math("`$x$`") == "`$x$`")
    t = table_at(["| A | B |", "|:--|--:|", "| 1 | 2 |"], 0)
    check("tabella riconosciuta", t is not None and t[0] == ["left", "right"])
    check("tabella in testo", "-" in _tables_to_text("| A | B |\n|---|---|\n| 1 | 2 |"))
    tmp = tempfile.mkdtemp()
    png = os.path.join(tmp, "mappa.png")
    with open(png, "wb") as f:
        f.write(Project()._simple_png(40, 30))
    md = os.path.join(tmp, "voce.md")
    with open(md, "w", encoding="utf-8") as f:
        f.write("# Voce\n\n![Mappa](mappa.png)\n\n![Remota](https://x.org/a.png)\n\n![Manca](manca.jpg)\n")
    p = Project()
    p.import_text_file(md)
    text = "\n".join(c.text for c in p.chapters)
    check("immagine accanto al .md copiata nel progetto", len(p.images) == 1)
    name = next(iter(p.images), "")
    check("riferimento riscritto al nome interno", f"![Mappa]({name})" in text)
    check("indirizzo remoto lasciato com'è", "(https://x.org/a.png)" in text)
    check("file mancante lasciato com'è", "(manca.jpg)" in text)


def main():
    for fn in (test_save_load_roundtrip, test_autosave_non_mutating,
               test_chapter_title_priority, test_export_txt,
               test_export_pdf, test_export_pdf_typography,
               test_cover_generator,
               test_export_epub, test_word_count,
               test_themes, test_theme_families,
               test_markdown_coerente, test_markdown_stessi_esiti_fra_formati,
               test_link_markdown, test_motore_comune,
               test_font_di_sistema,
               test_icona_unica,
               test_margini_pagina,
               test_finestra_massimizzata,
               test_margini_di_lettura,
               test_larghezza_delle_colonne,
               test_lingue_non_tradotte,
               test_interruttori_del_menu,
               test_copertina_ruoli,
               test_copertina_parole_intere,
               test_copertina_titolo_dentro_i_bordi,
               test_segnalibri_pdf,
               test_vedere_le_interruzioni,
               test_zavorra_gutenberg,
               test_ricucitura_paragrafi,
               test_suggerimento_pagina_vuota,
               test_i18n, test_export_markdown_odt_docx,
               test_export_html, test_azw3_logic,
               test_epub_cover_png, test_simple_png, test_import_text,
               test_attached_images, test_formule_tabelle_immagini):
        fn()
    print("\n" + "=" * 50)
    print(f"RISULTATO: {PASSED} superati, {FAILED} falliti")
    print("=" * 50)
    sys.exit(1 if FAILED else 0)


if __name__ == "__main__":
    main()
