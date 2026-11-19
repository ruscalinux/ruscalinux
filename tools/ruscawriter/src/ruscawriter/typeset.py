# -*- coding: utf-8 -*-
# RuscaWriter — PDF tipografico con LuaLaTeX
# Copyright (C) 2026  Nunzio Curcuruto — GPL-3.0-or-later
"""
PDF tipografico: il libro composto da LuaLaTeX (TeX Live, pacchetti Debian
texlive-luatex e texlive-latex-recommended), con:

  * a capo sull'intero paragrafo (Knuth–Plass) e microtipografia (microtype:
    sporgenza della punteggiatura ed espansione dei caratteri);
  * crenatura, legature e tutte le scritture tramite luaotfload/HarfBuzz;
  * capitoli su pagina dispari, testatine, indice con i numeri di pagina,
    frontespizio e colophon, niente righe vedove e orfane.

Come il PDF «veloce» (model.write_pdf) parte dai blocchi del motore comune
(model.book_blocks): stesso Markdown, stesse regole del libro. La sillabazione
la decide Pyphen con i dizionari hyphen-* di Debian, come nel PDF veloce: i
punti di divisione arrivano a TeX come \\- e i suoi pattern restano spenti,
così non servono i pacchetti texlive-lang-* (circa 700 MB).

Sicurezza. Il testo del libro non diventa mai codice TeX: ogni carattere
speciale (\\ { } $ & % # _ ^ ~) è sostituito dal comando che lo stampa, quindi
dal documento non può nascere nessun comando (né \\input, né \\directlua). Il
preambolo è scritto solo da questo modulo. lualatex gira senza shell
(-no-shell-escape), senza poter scrivere né leggere fuori dalla cartella
temporanea (openout_any/openin_any = p), con un tempo massimo; i caratteri e
le immagini vengono copiati o collegati lì dentro con nomi scelti qui.
Nessun accesso alla rete: TeX Live non ne fa.
"""

import os
import re
import shutil
import subprocess
import tempfile

from . import model as _m
from .i18n import ASSETS_DIR

# ---------------------------------------------------------------------------
# Disponibilità
# ---------------------------------------------------------------------------
LUALATEX_CANDIDATES = ("/usr/bin/lualatex",)
TIMEOUT_S = 300            # per ogni passaggio di lualatex
DEPENDENCIES = "texlive-luatex texlive-latex-recommended"


def lualatex_path():
    """Il programma lualatex installato, o None. Solo percorsi assoluti
    (specifiche, sezione 11: niente programmi cercati nel PATH dell'utente)."""
    for p in LUALATEX_CANDIDATES:
        if os.path.isfile(p) and os.access(p, os.X_OK):
            return p
    return None


def available():
    return lualatex_path() is not None


class TypesetError(Exception):
    """Errore di composizione, con il messaggio di TeX già ripulito."""


# ---------------------------------------------------------------------------
# Lingue: babel e caratteri per le scritture non latine
# ---------------------------------------------------------------------------
# Codice della lingua del libro (quello del controllo ortografico) → nome
# babel. Le 26 lingue dei RuscaLinux OS Tools (specifiche, sezione 9).
BABEL_NAMES = {
    "it": "italian", "en": "english", "en_GB": "british", "en_US": "american",
    "de": "german", "fr": "french", "es": "spanish", "pt": "portuguese",
    "pt_BR": "brazilian", "pt_PT": "portuguese", "ru": "russian",
    "uk": "ukrainian", "pl": "polish", "cs": "czech", "nl": "dutch",
    "sv": "swedish", "fi": "finnish", "hu": "hungarian", "ro": "romanian",
    "el": "greek", "tr": "turkish", "id": "indonesian", "vi": "vietnamese",
    "ar": "arabic", "hi": "hindi", "ja": "japanese", "ko": "korean",
    "zh": "chinese-simplified", "zh_CN": "chinese-simplified",
    "zh_TW": "chinese-traditional",
}
RTL_LANGS = {"ar"}
CJK_LANGS = {"ja", "zh", "zh_CN", "zh_TW"}
NOTO = "/usr/share/fonts/truetype/noto/"
NOTO_CJK = "/usr/share/fonts/opentype/noto/"
# Caratteri per le scritture che EB Garamond non ha (fonts-noto-core e
# fonts-noto-cjk, già in RuscaLinux): (file del tondo, del neretto, indice
# nella raccolta .ttc).
SCRIPT_FONTS = {
    "ar": (NOTO + "NotoNaskhArabic-Regular.ttf", NOTO + "NotoNaskhArabic-Bold.ttf", None),
    "hi": (NOTO + "NotoSerifDevanagari-Regular.ttf", NOTO + "NotoSerifDevanagari-Bold.ttf", None),
    "ja": (NOTO_CJK + "NotoSerifCJK-Regular.ttc", NOTO_CJK + "NotoSerifCJK-Bold.ttc", 0),
    "ko": (NOTO_CJK + "NotoSerifCJK-Regular.ttc", NOTO_CJK + "NotoSerifCJK-Bold.ttc", 1),
    "zh_CN": (NOTO_CJK + "NotoSerifCJK-Regular.ttc", NOTO_CJK + "NotoSerifCJK-Bold.ttc", 2),
    "zh_TW": (NOTO_CJK + "NotoSerifCJK-Regular.ttc", NOTO_CJK + "NotoSerifCJK-Bold.ttc", 3),
}
# Ripieghi per i glifi che il carattere del libro non ha (simboli delle
# formule, frecce, caselle ☐ ☑…), nell'ordine.
FALLBACK_FONTS = (
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    NOTO + "NotoSansMath-Regular.ttf",
    NOTO + "NotoSansSymbols2-Regular.ttf",
    NOTO + "NotoSansSymbols-Regular.ttf",
)
MONO_FONTS = ("/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf",
              "/usr/share/fonts/truetype/dejavu/DejaVuSansMono-Bold.ttf")


def lang_key(lang):
    """«it_IT» → «it», «pt_BR» → «pt_BR», «zh-TW» → «zh_TW»: la chiave più
    precisa che BABEL_NAMES conosce."""
    code = (lang or "it").replace("-", "_").split(".")[0]
    if code in BABEL_NAMES:
        return code
    base = code.split("_")[0]
    return base if base in BABEL_NAMES else "en"


# ---------------------------------------------------------------------------
# Testo → TeX
# ---------------------------------------------------------------------------
_SPECIAL = {
    "\\": r"\textbackslash{}", "{": r"\{", "}": r"\}", "$": r"\$", "&": r"\&",
    "%": r"\%", "#": r"\#", "_": r"\_", "^": r"\textasciicircum{}",
    "~": r"\textasciitilde{}",
}
# controlli, area privata e caratteri non validi: non si stampano
_DROP = re.compile("[\x00-\x08\x0b-\x1f\x7f\u2028\u2029\ue000-\uf8ff\ufffe\uffff]")
_WS = re.compile(r"[\t\n\r\f\v]")
_URL = re.compile(r"(?:https?://|www\.)\S+|\S+@\S+\.\w+")
_WORD = re.compile(r"\w+")


def escape(text):
    """Testo qualsiasi → TeX che lo stampa tale e quale. Nessuna sequenza del
    risultato può formare un comando che non sia uno di quelli qui sotto."""
    text = _WS.sub(" ", _DROP.sub("", text or ""))
    return "".join(_SPECIAL.get(c, c) for c in text)


class Hyphenator:
    """Punti di sillabazione di Pyphen come \\- (nessuno se manca Pyphen o
    il dizionario della lingua). Almeno 2 lettere prima e 3 dopo la
    divisione, come nei libri; parole corte, sigle e numeri restano intere."""

    def __init__(self, lang, enabled=True):
        self.dic = _m.get_hyphenator(lang) if enabled else None

    def word(self, w):
        if self.dic is None or len(w) < 5 or not w.isalpha() or w.isupper():
            return escape(w)
        try:
            pos = [p for p in self.dic.positions(w) if 2 <= p <= len(w) - 3]
        except Exception:
            pos = []
        out, last = [], 0
        for p in pos:
            out.append(escape(w[last:p]))
            last = p
        out.append(escape(w[last:]))
        return r"\-".join(out)


def _url_tex(url):
    """Un indirizzo: mai sillabato, ma può andare a capo dopo / . - e simili."""
    out = []
    for c in url:
        out.append(escape(c))
        if c in "/.-?&=#_":
            out.append(r"\allowbreak{}")
    return "".join(out)


def text_tex(text, hy=None):
    """Testo del libro → TeX, con i punti di sillabazione se hy è dato."""
    text = _WS.sub(" ", _DROP.sub("", text or ""))
    out, pos = [], 0
    for m in _URL.finditer(text):
        out.append(_words_tex(text[pos:m.start()], hy))
        out.append(_url_tex(m.group(0)))
        pos = m.end()
    out.append(_words_tex(text[pos:], hy))
    return "".join(out)


def _words_tex(text, hy):
    if hy is None or hy.dic is None:
        return escape(text)
    out, pos = [], 0
    for m in _WORD.finditer(text):
        out.append(escape(text[pos:m.start()]))
        out.append(hy.word(m.group(0)))
        pos = m.end()
    out.append(escape(text[pos:]))
    return "".join(out)


def runs_tex(runs, hy=None):
    """Tratti (testo, stile) di book_blocks → TeX."""
    out = []
    for text, style in runs:
        if not text:
            continue
        if style == "code":
            out.append(r"\texttt{" + text_tex(text) + "}")
            continue
        body = text_tex(text, hy)
        if style == "bold":
            body = r"\textbf{" + body + "}"
        elif style == "italic":
            body = r"\textit{" + body + "}"
        elif style == "bolditalic":
            body = r"\textbf{\textit{" + body + "}}"
        out.append(body)
    return "".join(out)


def code_line_tex(line):
    """Una riga di codice: spazi conservati (quelli iniziali non si
    spezzano), nessuna sillabazione."""
    line = line.replace("\t", "    ")
    lead = len(line) - len(line.lstrip(" "))
    body = escape(line[lead:]).replace(" ", r"\ ")
    return "~" * lead + body if (lead or body) else r"\mbox{}"


# ---------------------------------------------------------------------------
# Blocchi del libro → TeX
# ---------------------------------------------------------------------------
MAX_NEST = 4               # LaTeX ammette al più 6 elenchi/citazioni annidati


class _Writer:
    def __init__(self, hy, images, text_w, text_h, font_size=11.0):
        self.font_size = font_size
        self.hy = hy
        self.images = images           # nome nel libro → (file, larghezza, altezza)
        self.text_w = text_w
        self.text_h = text_h
        self.out = []
        self.noindent = True

    def para(self, tex):
        self.out.append((r"\noindent " if self.noindent else "") + tex + r"\par")
        self.noindent = False

    def display(self, lines):
        self.out.extend(lines)
        self.noindent = True

    def blocks(self, blocks, nest=0):
        for b in blocks:
            kind = b[0]
            prev, self.last = getattr(self, "last", None), kind
            if kind == "heading":
                cmd = {1: "section", 2: "subsection"}.get(b[1], "subsubsection")
                title = escape(_m.plain_runs(b[2]).strip())
                if title:
                    self.out.append(f"\\{cmd}*{{{title}}}")
                    self.noindent = True
            elif kind == "p":
                # come nel PDF normale: ogni a capo è un capoverso con il
                # rientro; la riga vuota fra due blocchi lascia mezzo rigo e
                # il blocco che segue non rientra
                if prev == "p":
                    self.out.append(r"\vspace{.5\baselineskip}")
                    self.noindent = True
                for line in b[1]:
                    if _m.plain_runs(line).strip():
                        self.para(runs_tex(line, self.hy))
            elif kind == "image":
                self.image(b[1], b[2])
            elif kind == "list":
                self.list_(b, nest)
            elif kind == "quote":
                if nest >= MAX_NEST:
                    self.blocks(b[1], nest)
                    continue
                self.out.append(r"\begin{quote}\small")
                self.noindent = True
                self.blocks(b[1], nest + 1)
                self.display([r"\end{quote}"])
            elif kind == "table":
                self.table(b[1], b[2], b[3], nest)
            elif kind == "rule":
                self.display([r"\begin{center}\rule{.25\linewidth}{.4pt}\end{center}"])
            elif kind == "code":
                body = [code_line_tex(ln) + r"\par" for ln in b[2].split("\n")]
                self.display([r"\begin{rwcode}"] + body + [r"\end{rwcode}"])
            elif kind == "math":
                self.display([r"\begin{center}" + text_tex(b[1]) + r"\end{center}"])

    def image(self, caption, name):
        cap = text_tex((caption or "").strip(), self.hy)
        if name not in self.images:
            if cap:
                self.display([r"\begin{center}\textit{" + cap + r"}\end{center}"])
            return
        fname, iw, ih = self.images[name]
        # come il PDF veloce: mai ingrandita, al più larga quanto il testo e
        # alta il 60% della gabbia (i pixel contano come punti)
        scale = min(self.text_w / iw, self.text_h * 0.6 / ih, 1.0)
        lines = [r"\begin{center}",
                 f"\\includegraphics[width={iw * scale:.2f}bp,height={ih * scale:.2f}bp]{{{fname}}}"]
        if cap:
            lines.append(r"\par\nopagebreak\smallskip{\small\textit{" + cap + "}}")
        lines.append(r"\end{center}")
        self.display(lines)

    def list_(self, block, nest):
        _k, ordered, start, items = block
        if nest >= MAX_NEST:           # troppo annidato per LaTeX: rientro semplice
            for task, sub in items:
                self.blocks(sub, nest)
            return
        env = "enumerate" if ordered else "itemize"
        self.out.append(f"\\begin{{{env}}}\\setlength{{\\itemsep}}{{1pt}}\\setlength{{\\parsep}}{{0pt}}")
        if ordered and start != 1:
            counter = ("enumi", "enumii", "enumiii", "enumiv")[min(self._enum_depth(), 3)]
            self.out.append(f"\\setcounter{{{counter}}}{{{int(start) - 1}}}")
        self._enum_stack.append(ordered)
        for task, sub in items:
            if task is not None:
                self.out.append(r"\item[" + ("☑" if task else "☐") + "] ")
            else:
                self.out.append(r"\item{} ")
            self.noindent = True
            self.blocks(sub, nest + 1)
        self._enum_stack.pop()
        self.display([f"\\end{{{env}}}"])

    _enum_stack = None

    def _enum_depth(self):
        return sum(1 for o in self._enum_stack if o)

    def table(self, aligns, header, rows, nest):
        ncol = len(header)
        if not ncol:
            return
        grid = [header] + rows
        # Larghezze come nel PDF veloce: se tutto il testo sta su una riga le
        # colonne si allargano in proporzione fino a riempire la gabbia;
        # altrimenti le colonne corte restano alla loro misura e le lunghe si
        # dividono il resto, mai più strette della loro parola più lunga.
        cw = self.font_size * 0.9 * 0.5          # larghezza media di un carattere (\small)
        pad = 12.0                               # 2 × \tabcolsep
        avail = self.text_w - pad * ncol
        cells = [[_m.plain_runs(r[c]) if c < len(r) else "" for r in grid] for c in range(ncol)]
        nat = [max(len(t) for t in col) * cw + cw for col in cells]
        least = [max((len(w) for t in col for w in t.split()), default=1) * cw + cw for col in cells]
        if sum(nat) <= avail:
            tot = sum(nat) or 1.0
            widths = [n * avail / tot for n in nat]
        else:
            base = [min(n, max(lw, avail / ncol)) for n, lw in zip(nat, least)]
            flex = [max(n - b_, 0.0) for n, b_ in zip(nat, base)]
            rest = max(avail - sum(base), 0.0)
            tot = sum(flex) or 1.0
            widths = [b_ + rest * f_ / tot for b_, f_ in zip(base, flex)]
            scale = min(1.0, avail / (sum(widths) or 1.0))
            widths = [w_ * scale for w_ in widths]
        cols = []
        for c in range(ncol):
            al = aligns[c] if c < len(aligns) else "left"
            ragged = {"right": r"\RaggedLeft", "center": r"\Centering"}.get(al, r"\RaggedRight")
            cols.append(f">{{{ragged}\\arraybackslash}}p{{{widths[c]:.2f}bp}}")
        spec = "".join(cols)

        def row_tex(cells, bold=False):
            vals = []
            for c in range(ncol):
                cell = runs_tex(cells[c], self.hy) if c < len(cells) else ""
                vals.append(r"\textbf{" + cell + "}" if bold and cell else cell)
            return " & ".join(vals) + r" \\"

        body = [row_tex(r) for r in rows]
        if nest:                       # dentro un elenco: tabella che non si spezza
            lines = [r"\par\smallskip{\small\begin{tabular}{" + spec + "}", r"\toprule",
                     row_tex(header, True), r"\midrule"] + body + [r"\bottomrule\end{tabular}}\par\smallskip"]
        else:
            lines = [r"{\small\begin{longtable}{" + spec + "}", r"\toprule", row_tex(header, True),
                     r"\midrule\endhead", r"\bottomrule\endfoot"] + body + [r"\end{longtable}}"]
        self.display(lines)


def chapter_tex(title, text, hy, images, text_w, text_h, font_size=11.0):
    """Un capitolo: \\chapter con il suo titolo e i blocchi del testo. Se il
    testo comincia con un titolo uguale a quello del capitolo (il caso
    normale: il titolo viene dal «# Titolo» del testo), non si ripete."""
    blocks = _m.book_blocks(text)
    if blocks and blocks[0][0] == "heading" \
            and _m.plain_runs(blocks[0][2]).strip() == (title or "").strip():
        blocks = blocks[1:]
    w = _Writer(hy, images, text_w, text_h, font_size)
    w._enum_stack = []
    w.out.append(r"\chapter{" + escape(title) + "}")
    w.blocks(blocks)
    return "\n".join(w.out)


# ---------------------------------------------------------------------------
# Documento
# ---------------------------------------------------------------------------
PREAMBLE_TAIL = r"""
\usepackage{microtype}
\usepackage{graphicx}
\usepackage{array,longtable,booktabs}
\usepackage{ragged2e}
\usepackage[headsepline=false]{scrlayer-scrpage}
\usepackage[hidelinks,bookmarks=true,bookmarksopen=false]{hyperref}
\setcounter{secnumdepth}{-1}
\setcounter{tocdepth}{0}
\setlength{\parskip}{0pt plus .5pt}
\clubpenalty=10000
\widowpenalty=10000
\displaywidowpenalty=10000
\brokenpenalty=5000
\tolerance=1000
\emergencystretch=1.5em
\setkomafont{disposition}{\normalfont}
\setkomafont{chapter}{\normalfont\huge}
\setkomafont{section}{\normalfont\Large\itshape}
\setkomafont{subsection}{\normalfont\large\bfseries}
\setkomafont{subsubsection}{\normalfont\normalsize\bfseries}
\setkomafont{chapterentry}{\normalfont}
\setkomafont{chapterentrypagenumber}{\normalfont}
\renewcommand*{\raggedchapter}{\centering}
\RedeclareSectionCommand[beforeskip=.18\textheight,afterskip=2.5\baselineskip]{chapter}
\setkomafont{pagehead}{\normalfont\small\itshape}
\setkomafont{pagenumber}{\normalfont\small}
\newenvironment{rwcode}{\par\smallskip\begingroup\footnotesize\ttfamily
  \setlength{\parindent}{0pt}\RaggedRight\hyphenpenalty=10000\exhyphenpenalty=10000
  \setlength{\leftskip}{1em}}{\par\endgroup\smallskip}
"""


def _pt(v):
    """Punti PDF (1/72 di pollice): in TeX sono «bp», non «pt» (1/72,27)."""
    return f"{float(v):.2f}bp"


def build_document(book, workdir):
    """Scrive in workdir il sorgente book.tex e i file che usa (caratteri,
    immagini). book è un dizionario (vedi Project.typeset_data()):
      title, author, lang, font_size, page_w, page_h, margins (in pt:
      inner, outer, top, bottom, gutter, mirror), justify, hyphenate,
      fonts {stile: percorso}, cover_image (byte) | None, cover_lines
      [(testo, ruolo)], blank_cover, front_lines, colophon_lines,
      chapters [(titolo, markdown)], images {nome: byte}.
    Restituisce il percorso di book.tex."""
    os.makedirs(os.path.join(workdir, "fonts"), exist_ok=True)
    os.makedirs(os.path.join(workdir, "img"), exist_ok=True)
    key = lang_key(book.get("lang"))
    babel = BABEL_NAMES[key]
    script = SCRIPT_FONTS.get(key) or SCRIPT_FONTS.get(key.split("_")[0])
    hy = Hyphenator(book.get("lang") or key, book.get("hyphenate", True))
    m = book["margins"]
    mirror = bool(m.get("mirror", True))
    fs = max(8.0, min(16.0, float(book.get("font_size") or 11)))
    pw, ph = float(book["page_w"]), float(book["page_h"])
    text_w = pw - m["inner"] - m["outer"] - m.get("gutter", 0.0)
    text_h = ph - m["top"] - m["bottom"]

    def link(src, name):
        """Collega (o copia) un file nella cartella di lavoro con un nome
        scelto qui: TeX non vede mai i percorsi dell'utente."""
        dst = os.path.join(workdir, "fonts", name)
        try:
            os.symlink(os.path.abspath(src), dst)
        except OSError:
            shutil.copyfile(src, dst)
        return name

    # --- caratteri del libro
    fonts = {k: v for k, v in (book.get("fonts") or {}).items() if v and os.path.isfile(v)}
    if "regular" not in fonts:
        fonts = {s: os.path.join(ASSETS_DIR, f) for s, f in _m.SERIF_FILES.items()}
    names = {s: link(p, f"book-{s}{os.path.splitext(p)[1].lower()}") for s, p in fonts.items()}
    fallbacks = [link(p, f"fb{i}{os.path.splitext(p)[1].lower()}")
                 for i, p in enumerate(FALLBACK_FONTS) if os.path.isfile(p)]
    harf = key in RTL_LANGS or key == "hi"

    def font_opts(nm, extra=""):
        opts = [f"Path=./fonts/", "Ligatures={Common,TeXOff}"]
        for style, opt in (("bold", "BoldFont"), ("italic", "ItalicFont"),
                           ("bolditalic", "BoldItalicFont")):
            if style in nm:
                opts.append(f"{opt}={nm[style]}")
        if fallbacks:
            opts.append("RawFeature={fallback=rwfallback}")
        if extra:
            opts.append(extra)
        return ",".join(opts)

    lua_fb = ",".join(f'"[fonts/{f}]:mode={"harf" if harf else "node"};"' for f in fallbacks)
    twoside = "twoside,openright" if mirror else "oneside,openany"
    geo_side = (f"inner={_pt(m['inner'])},outer={_pt(m['outer'])},bindingoffset={_pt(m.get('gutter', 0))}"
                if mirror else
                f"left={_pt(m['inner'] + m.get('gutter', 0))},right={_pt(m['outer'])}")
    pre = [
        f"\\documentclass[fontsize={fs:g}pt,paper={pw:.2f}bp:{ph:.2f}bp,{twoside},"
        "headings=normal,toc=chapterentrywithdots,cleardoublepage=empty,"
        "chapterprefix=false,numbers=noenddot]{scrbook}",
        f"\\usepackage[paperwidth={pw:.2f}bp,paperheight={ph:.2f}bp,{geo_side},"
        f"top={_pt(m['top'])},bottom={_pt(m['bottom'])},"
        f"headheight={fs * 1.3:.1f}pt,headsep={_pt(max(8.0, m['top'] * 0.3))},"
        f"footskip={_pt(max(16.0, m['bottom'] * 0.5))}]{{geometry}}",
        r"\usepackage{fontspec}",
    ]
    if fallbacks:
        pre.append(f"\\directlua{{luaotfload.add_fallback(\"rwfallback\",{{{lua_fb}}})}}")
    pre.append(f"\\setmainfont{{{names['regular']}}}[{font_opts(names)}]")
    mono = [p for p in MONO_FONTS if os.path.isfile(p)]
    if mono:
        mnames = {"regular": link(mono[0], "mono-regular.ttf")}
        if len(mono) > 1:
            mnames["bold"] = link(mono[1], "mono-bold.ttf")
        pre.append(f"\\setmonofont{{{mnames['regular']}}}[{font_opts(mnames, 'Scale=MatchLowercase')}]")
    pre.append(f"\\usepackage[{'bidi=basic,' if key in RTL_LANGS else ''}provide=*]{{babel}}")
    # i pattern di TeX restano spenti: la sillabazione è quella di Pyphen.
    # Cinese e giapponese vanno a capo fra gli ideogrammi con le regole di
    # babel, che valgono solo con le loro «regole di divisione» (nil).
    cjk = key in CJK_LANGS
    rules = "" if cjk else ",hyphenrules=nohyphenation"
    pre.append(f"\\babelprovide[import,main{rules}]{{{babel}}}")
    if script and os.path.isfile(script[0]):
        sreg = link(script[0], "script-regular" + os.path.splitext(script[0])[1])
        sopts = ["Path=./fonts/"]
        if script[1] and os.path.isfile(script[1]):
            sopts.append("BoldFont=" + link(script[1], "script-bold" + os.path.splitext(script[1])[1]))
        if script[2] is not None:
            sopts.append(f"FontIndex={script[2]}")
        if harf:
            sopts.append("Renderer=HarfBuzz")
        if fallbacks:
            sopts.append("RawFeature={fallback=rwfallback}")
        pre.append(f"\\babelfont{{rm}}[{','.join(sopts)}]{{{sreg}}}")
    body_pre = PREAMBLE_TAIL
    if harf or cjk or key == "ko":
        # microtype non conosce queste scritture: solo la sporgenza
        body_pre = body_pre.replace(r"\usepackage{microtype}",
                                    r"\usepackage[expansion=false]{microtype}")
    pre.append(body_pre)
    title = book.get("title") or ""
    author = book.get("author") or ""
    pre.append(r"\hypersetup{pdftitle={" + escape(title) + "},pdfauthor={" + escape(author)
               + "},pdfcreator={RuscaWriter}}")
    if not book.get("justify", True):
        pre.append(r"\AtBeginDocument{\RaggedRight}")
    pre.append(r"\clearpairofpagestyles")
    pre.append(r"\automark[chapter]{chapter}")
    if mirror:
        pre += [r"\ohead{\pagemark}", r"\cehead{" + escape(title) + "}", r"\cohead{\leftmark}"]
    else:
        pre += [r"\ohead{\pagemark}", r"\chead{\leftmark}"]
    pre.append(r"\cfoot[\pagemark]{}")

    # --- immagini dei capitoli
    images = {}
    for i, (name, data) in enumerate(sorted((book.get("images") or {}).items())):
        fmt = _m.image_format(data)
        if fmt in ("png", "jpeg"):
            dims = _m.image_dimensions(data, fmt)
            payload = data
        else:
            conv = _m._image_to_jpeg(data, fmt)
            if not conv:
                continue
            payload, dims, fmt = conv[0], (conv[1], conv[2]), "jpeg"
        if not dims or not dims[0] or not dims[1]:
            continue
        fname = f"img/i{i}.{'png' if fmt == 'png' else 'jpg'}"
        with open(os.path.join(workdir, fname), "wb") as f:
            f.write(payload)
        images[name] = (fname, float(dims[0]), float(dims[1]))

    doc = [r"\begin{document}", r"\frontmatter", r"\pagestyle{empty}",
           r"\renewcommand*{\chapterpagestyle}{empty}"]
    doc += _cover_tex(book, workdir, pw, ph)
    doc += _front_tex(book.get("front_lines") or [], book.get("colophon_lines") or [])
    chapters = book.get("chapters") or []
    if chapters:
        doc += [r"\tableofcontents", r"\cleardoublepage"]
    doc += [r"\mainmatter", r"\pagestyle{scrheadings}",
            r"\renewcommand*{\chapterpagestyle}{plain.scrheadings}"]
    for t, text in chapters:
        doc.append(chapter_tex(t, text, hy, images, text_w, text_h, fs))
    doc.append(r"\end{document}")
    src = "\n".join(pre + doc) + "\n"
    path = os.path.join(workdir, "book.tex")
    with open(path, "w", encoding="utf-8") as f:
        f.write(src)
    return path


def _cover_tex(book, workdir, pw, ph):
    """Copertina: l'immagine a pagina piena (ritagliata alle proporzioni
    della pagina se c'è Pillow), altrimenti titolo, sottotitolo, autore ed
    editore composti; bianca se il libro non ne ha."""
    data = book.get("cover_image")
    if data:
        fmt = _m.image_format(data)
        payload, ext = None, None
        try:
            from PIL import Image, ImageOps
            import io as _io
            img = Image.open(_io.BytesIO(data)).convert("RGB")
            target = (max(1, round(pw / 72 * 300)), max(1, round(ph / 72 * 300)))
            if img.width < target[0]:          # non si ingrandisce per niente
                target = (img.width, max(1, round(img.width * ph / pw)))
            img = ImageOps.fit(img, target, Image.LANCZOS)
            buf = _io.BytesIO()
            img.save(buf, format="JPEG", quality=92)
            payload, ext = buf.getvalue(), "jpg"
        except Exception:
            if fmt in ("png", "jpeg"):
                payload, ext = data, ("png" if fmt == "png" else "jpg")
        if payload:
            with open(os.path.join(workdir, "img", "cover." + ext), "wb") as f:
                f.write(payload)
            return [r"\AddToHookNext{shipout/background}{\put(0pt,-\paperheight){"
                    r"\includegraphics[width=\paperwidth,height=\paperheight,keepaspectratio]"
                    "{img/cover." + ext + "}}}",
                    r"\null\thispagestyle{empty}\cleardoublepage"]
    lines = book.get("cover_lines") or []
    if book.get("blank_cover") or not lines:
        return [r"\null\thispagestyle{empty}\cleardoublepage"]
    out = [r"\begin{titlepage}\centering", r"\vspace*{.22\textheight}"]
    out += _role_lines(lines, {"title": r"{\Huge ", "subtitle": r"{\Large\itshape ",
                               "author": r"{\Large\scshape ", "publisher": None})
    pub = [t for t, r in lines if r == "publisher"]
    out.append(r"\vfill")
    out += [r"{\large " + escape(t) + r"\par}" for t in pub]
    out += [r"\end{titlepage}", r"\cleardoublepage"]
    return out


def _role_lines(lines, styles):
    out = []
    for text, role in lines:
        st = styles.get(role, r"{\large ")
        if st is None:
            continue
        out.append(st + escape(text) + r"\par}")
        out.append(r"\vspace{1.2em}")
    return out


def _front_tex(front, colophon):
    """Frontespizio (pagina dispari) e colophon sul retro, in basso."""
    out = []
    if front:
        out += [r"\begin{titlepage}\centering", r"\vspace*{.12\textheight}"]
        top = [(t, r) for t, r in front if r != "meta"]
        out += _role_lines(top, {"title": r"{\huge ", "subtitle": r"{\large\itshape ",
                                 "author": r"{\large\scshape "})
        out.append(r"\vfill")
        out += [r"{\normalsize " + escape(t) + r"\par}" for t, r in front if r == "meta"]
        out.append(r"\end{titlepage}")
    if colophon:
        out += [r"\null\vfill", r"{\footnotesize\setlength{\parindent}{0pt}"]
        for text, role in colophon:
            out.append((r"\textbf{" + escape(text) + "}" if role == "copyright" else escape(text))
                       + r"\par\smallskip")
        out += [r"}", r"\clearpage"]
    if front or colophon:
        out.append(r"\cleardoublepage")
    return out


# ---------------------------------------------------------------------------
# Composizione
# ---------------------------------------------------------------------------
def _tex_error(log):
    """Il primo errore del registro di TeX, in una riga leggibile."""
    lines = log.splitlines()
    for i, ln in enumerate(lines):
        if ln.startswith("!") or re.match(r"^\./book\.tex:\d+:", ln):
            msg = re.sub(r"^\./book\.tex:\d+:\s*|^!\s*", "", ln).strip()
            ctx = " ".join(x.strip() for x in lines[i + 1:i + 3] if x.strip().startswith("l."))
            return (msg + (" — " + ctx if ctx else "")).strip()[:400]
    return ""


def run(workdir, passes=2):
    """lualatex su book.tex, senza shell né rete, confinato in workdir.
    Restituisce il percorso del PDF o solleva TypesetError."""
    exe = lualatex_path()
    if exe is None:
        raise TypesetError(f"lualatex non installato ({DEPENDENCIES})")
    env = {k: v for k, v in os.environ.items()
           if k in ("PATH", "HOME", "LANG", "LC_ALL", "LANGUAGE", "XDG_CACHE_HOME", "USER")}
    cache = os.path.join(os.environ.get("XDG_CACHE_HOME") or os.path.expanduser("~/.cache"),
                         "ruscawriter", "texmf-var")
    os.makedirs(cache, exist_ok=True)
    env.update({
        "openout_any": "p", "openin_any": "p", "shell_escape": "f",
        "TEXMFVAR": cache,                    # cache dei caratteri di luaotfload
        "max_print_line": "1000",
    })
    args = [exe, "-interaction=nonstopmode", "-halt-on-error", "-no-shell-escape",
            "-file-line-error", "book.tex"]
    log_path = os.path.join(workdir, "book.log")
    for n in range(passes + 1):
        try:
            subprocess.run(args, cwd=workdir, env=env, stdin=subprocess.DEVNULL,
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                           timeout=TIMEOUT_S, check=False)
        except subprocess.TimeoutExpired:
            raise TypesetError("tempo scaduto")
        try:
            with open(log_path, encoding="utf-8", errors="replace") as f:
                log = f.read()
        except OSError:
            log = ""
        pdf = os.path.join(workdir, "book.pdf")
        if "Fatal error" in log or not os.path.isfile(pdf):
            raise TypesetError(_tex_error(log) or "lualatex non ha prodotto il PDF")
        rerun = re.search(r"Rerun to get|Label\(s\) may have changed|rerunfilecheck", log)
        if n + 1 >= passes and not rerun:
            break
    return pdf


def typeset(book, path, keep_dir=None):
    """Compone il libro in PDF in path. keep_dir: cartella dove lasciare
    sorgente e registro (per la diagnosi); di norma una cartella temporanea
    che si cancella alla fine."""
    workdir = keep_dir or tempfile.mkdtemp(prefix="ruscawriter-tex-")
    try:
        build_document(book, workdir)
        pdf = run(workdir)
        shutil.copyfile(pdf, path)
    finally:
        if keep_dir is None:
            shutil.rmtree(workdir, ignore_errors=True)
    return path
