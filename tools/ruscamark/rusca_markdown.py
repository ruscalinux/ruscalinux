"""RuscaLinux OS Tools — rusca_markdown.py — 1.99.2 — GPL-3.0

Motore Markdown comune dei RuscaLinux OS Tools.

Il Markdown segue la specifica CommonMark (https://spec.commonmark.org/),
con le estensioni di GitHub Flavored Markdown per tabelle, barrato e liste di
attività, le note a piè di pagina e le formule LaTeX. L'analisi non è scritta
qui: la fa markdown-it-py (pacchetto Debian python3-markdown-it), che
implementa CommonMark, con i plugin di python3-mdit-py-plugins. Questo modulo
configura il parser una volta per tutti i programmi e traduce il suo albero
nei formati che servono all'interfaccia.

Sintassi riconosciuta (parser(), sempre la stessa in tutti i programmi):
    CommonMark completo, senza HTML grezzo (resta testo: più sicuro, e le
    risposte dei modelli non possono inserire markup)
    tabelle e ~~barrato~~ (GFM), liste di attività - [ ] / - [x] (GFM)
    note a piè di pagina [^1]
    formule $…$, $$…$$ (regole di Pandoc: dopo il $ di apertura e prima di
    quello di chiusura non c'è uno spazio, e il $ di chiusura non è seguito
    da una cifra, così «da $5 a $10» resta testo), \\(…\\) e \\[…\\]

Blocchi restituiti da parse_blocks():
    ("text", markup)                         paragrafo, titolo, elenco, citazione
    ("code", lingua, sorgente)               blocco di codice (anche non chiuso)
    ("math", markup)                         formula su riga propria
    ("table", allineamenti, intestazione, righe)   celle già in markup
    ("hr",)                                  linea orizzontale

Le formule LaTeX diventano testo Unicode (², ≈, √, α, ⁄ …) con <sup>/<sub>
di Pango dove Unicode non basta: nessuna dipendenza in più.

Per chi non usa Pango (RuscaWriter: PDF, EPUB, ODT, DOCX, testo):
    latex_to_text(formula)   formula -> testo Unicode senza markup
    math_to_text(markdown)   sostituisce le formule $…$, $$…$$, \\(…\\), \\[…\\]
                             in un testo Markdown, fuori dal codice

Strumenti per riga, usati dagli editor per evidenziare il sorgente:
    table_at(righe, i), display_math_at(righe, i), has_inline_math(riga),
    sub_inline_math(testo, f)
Lavorano sulle singole righe e non sono un parser Markdown: si
sostituiranno con le posizioni dei token di parser() quando RuscaMark e
RuscaWriter useranno questo motore anche per anteprime ed esportazioni.

Modulo puro, senza GTK: si può provare con python3 da solo.
File identico in RuscaLLama, RuscaMark e RuscaWriter: si modifica una volta e
si copia.
"""

import re

from markdown_it import MarkdownIt
from markdown_it.tree import SyntaxTreeNode
from mdit_py_plugins.dollarmath import dollarmath_plugin
from mdit_py_plugins.footnote import footnote_plugin
from mdit_py_plugins.tasklists import tasklists_plugin
from mdit_py_plugins.texmath import texmath_plugin

__all__ = ["parser", "parse_blocks", "inline_to_pango", "latex_to_pango", "escape",
           "plain_text", "latex_to_text", "math_to_text", "table_at", "display_math_at",
           "has_inline_math", "sub_inline_math"]

def escape(s):
    return (s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            .replace('"', "&quot;").replace("'", "&#39;"))


def plain_text(markup):
    """Testo visibile di un markup (per misure e per il ripiego)."""
    s = re.sub(r"<[^>]+>", "", markup)
    return (s.replace("&lt;", "<").replace("&gt;", ">").replace("&quot;", '"')
            .replace("&#39;", "'").replace("&amp;", "&"))


# ── LaTeX -> Unicode / Pango ────────────────────────────────────────────────
_SYMBOLS = {
    # lettere greche
    "alpha": "α", "beta": "β", "gamma": "γ", "delta": "δ", "epsilon": "ε",
    "varepsilon": "ε", "zeta": "ζ", "eta": "η", "theta": "θ", "vartheta": "ϑ",
    "iota": "ι", "kappa": "κ", "lambda": "λ", "mu": "μ", "nu": "ν", "xi": "ξ",
    "pi": "π", "varpi": "ϖ", "rho": "ρ", "varrho": "ϱ", "sigma": "σ",
    "varsigma": "ς", "tau": "τ", "upsilon": "υ", "phi": "φ", "varphi": "φ",
    "chi": "χ", "psi": "ψ", "omega": "ω", "Gamma": "Γ", "Delta": "Δ",
    "Theta": "Θ", "Lambda": "Λ", "Xi": "Ξ", "Pi": "Π", "Sigma": "Σ",
    "Upsilon": "Υ", "Phi": "Φ", "Psi": "Ψ", "Omega": "Ω",
    # operatori e relazioni
    "times": "×", "cdot": "·", "div": "÷", "pm": "±", "mp": "∓", "ast": "∗",
    "approx": "≈", "simeq": "≃", "sim": "∼", "cong": "≅", "equiv": "≡",
    "neq": "≠", "ne": "≠", "leq": "≤", "le": "≤", "geq": "≥", "ge": "≥",
    "ll": "≪", "gg": "≫", "propto": "∝", "infty": "∞", "partial": "∂",
    "nabla": "∇", "sum": "∑", "prod": "∏", "int": "∫", "iint": "∬",
    "oint": "∮", "sqrt": "√", "in": "∈", "notin": "∉", "ni": "∋",
    "subset": "⊂", "subseteq": "⊆", "supset": "⊃", "supseteq": "⊇",
    "cup": "∪", "cap": "∩", "emptyset": "∅", "varnothing": "∅",
    "forall": "∀", "exists": "∃", "neg": "¬", "land": "∧", "lor": "∨",
    "wedge": "∧", "vee": "∨", "oplus": "⊕", "otimes": "⊗", "circ": "∘",
    "bullet": "•", "star": "⋆", "dagger": "†", "perp": "⊥", "parallel": "∥",
    "angle": "∠", "degree": "°", "prime": "′", "hbar": "ħ", "ell": "ℓ",
    "Re": "ℜ", "Im": "ℑ", "aleph": "ℵ",
    # frecce
    "to": "→", "rightarrow": "→", "leftarrow": "←", "gets": "←",
    "leftrightarrow": "↔", "Rightarrow": "⇒", "Leftarrow": "⇐",
    "Leftrightarrow": "⇔", "implies": "⇒", "iff": "⇔", "mapsto": "↦",
    "uparrow": "↑", "downarrow": "↓", "longrightarrow": "⟶",
    # puntini e parentesi
    "ldots": "…", "dots": "…", "cdots": "⋯", "vdots": "⋮", "ddots": "⋱",
    "langle": "⟨", "rangle": "⟩", "lfloor": "⌊", "rfloor": "⌋",
    "lceil": "⌈", "rceil": "⌉", "vert": "|", "Vert": "‖", "mid": "|",
    "lbrace": "{", "rbrace": "}",
    # spazi
    "quad": "\u2003", "qquad": "\u2003\u2003",
}
# Comandi di sola presentazione: si ignorano.
_DROP = {"Large", "large", "LARGE", "huge", "Huge", "small", "normalsize",
         "displaystyle", "textstyle", "scriptstyle", "left", "right", "big",
         "Big", "bigg", "Bigg", "bigl", "bigr", "Bigl", "Bigr", "limits",
         "nolimits", "nonumber", "notag"}
# Comandi con argomento da mostrare come testo.
_TEXTLIKE = {"text", "textrm", "textnormal", "mathrm", "operatorname", "mbox",
             "textit", "mathit", "textsf", "mathsf", "texttt", "mathtt",
             "mathbf", "textbf", "boldsymbol", "bm", "mathcal", "mathscr",
             "mathbb", "mathfrak", "hat", "bar", "vec", "dot", "ddot", "tilde",
             "overline", "underline", "widehat", "widetilde", "overrightarrow"}
_ACCENTS = {"hat": "\u0302", "bar": "\u0304", "overline": "\u0305", "vec": "\u20d7",
            "dot": "\u0307", "ddot": "\u0308", "tilde": "\u0303",
            "widehat": "\u0302", "widetilde": "\u0303", "overrightarrow": "\u20d7"}
_BB = {"R": "ℝ", "N": "ℕ", "Z": "ℤ", "Q": "ℚ", "C": "ℂ", "P": "ℙ", "H": "ℍ"}
_SUP = dict(zip("0123456789+-=()aeinx", "⁰¹²³⁴⁵⁶⁷⁸⁹⁺⁻⁼⁽⁾ᵃᵉⁱⁿˣ"))
_SUB = dict(zip("0123456789+-=()aehijklmnoprstuvx", "₀₁₂₃₄₅₆₇₈₉₊₋₌₍₎ₐₑₕᵢⱼₖₗₘₙₒₚᵣₛₜᵤᵥₓ"))
_SUP["−"], _SUB["−"] = "⁻", "₋"


class _Latex:
    def __init__(self, src):
        self.s = src
        self.i = 0

    def run(self, stop=None):
        out = []
        s = self.s
        while self.i < len(s):
            ch = s[self.i]
            if stop and ch == stop:
                self.i += 1
                break
            if ch == "\\":
                out.append(self._command())
            elif ch == "{":
                self.i += 1
                out.append(self.run("}"))
            elif ch in "^_":
                self.i += 1
                out.append(self._script(ch))
            elif ch == "~":
                self.i += 1
                out.append("\u00a0")
            elif ch == "&":
                self.i += 1
                out.append(" ")
            elif ch == "'":
                self.i += 1
                out.append("′")
            elif ch == "-":
                self.i += 1
                out.append("−")
            else:
                self.i += 1
                out.append(escape(ch))
        return "".join(out)

    def _group_src(self):
        """Sorgente del prossimo argomento: {gruppo}, \\comando o un carattere."""
        s = self.s
        while self.i < len(s) and s[self.i] == " ":
            self.i += 1
        if self.i >= len(s):
            return ""
        if s[self.i] == "{":
            depth, start = 0, self.i
            while self.i < len(s):
                if s[self.i] == "\\":
                    self.i += 2
                    continue
                if s[self.i] == "{":
                    depth += 1
                elif s[self.i] == "}":
                    depth -= 1
                    if depth == 0:
                        self.i += 1
                        return s[start + 1:self.i - 1]
                self.i += 1
            return s[start + 1:]
        if s[self.i] == "\\":
            m = re.match(r"\\([A-Za-z]+|.)", s[self.i:])
            self.i += m.end() if m else 1
            return m.group(0) if m else ""
        self.i += 1
        return s[self.i - 1]

    def _arg(self):
        return _Latex(self._group_src()).run()

    def _script(self, kind):
        markup = self._arg()
        text = plain_text(markup)
        table = _SUP if kind == "^" else _SUB
        if text and "<" not in markup and all(c in table for c in text):
            return "".join(table[c] for c in text)
        tag = "sup" if kind == "^" else "sub"
        return f"<{tag}>{markup}</{tag}>"

    def _command(self):
        s = self.s
        m = re.match(r"\\([A-Za-z]+)\*?", s[self.i:])
        if not m:                                   # \, \; \{ \\ …
            ch = s[self.i + 1:self.i + 2]
            self.i += 2
            if ch in ",:;>":
                return "\u2009"
            if ch == "!":
                return ""
            if ch == "\\":
                return "\n"
            if ch == " ":
                return " "
            return escape(ch)
        name = m.group(1)
        self.i += m.end()
        if name in _DROP:
            return ""
        if name in ("frac", "dfrac", "tfrac", "cfrac"):
            num, den = self._arg(), self._arg()
            wrap = lambda x: f"({x})" if re.search(r"[\s+−=·×/]", plain_text(x)) else x
            return f"{wrap(num)}⁄{wrap(den)}"
        if name == "sqrt":
            index = ""
            if self.s[self.i:self.i + 1] == "[":
                end = self.s.find("]", self.i)
                if end > 0:
                    index = _Latex(self.s[self.i + 1:end]).run()
                    self.i = end + 1
            body = self._arg()
            pre = "".join(_SUP.get(c, c) for c in plain_text(index)) if index else ""
            return pre + "√" + (body if len(plain_text(body)) <= 1 else f"({body})")
        if name in ("binom", "tbinom", "dbinom"):
            a, b = self._arg(), self._arg()
            return f"C({a}, {b})"
        if name in _TEXTLIKE:
            src = self._group_src()
            if name == "mathbb":
                return "".join(_BB.get(c, escape(c)) for c in src)
            if name in _ACCENTS:
                body = _Latex(src).run()
                return body + _ACCENTS[name] if len(plain_text(body)) == 1 else body
            if name in ("text", "textrm", "textnormal", "mbox", "texttt", "textit"):
                body = escape(src)                  # testo: niente comandi dentro
            else:
                body = _Latex(src).run()
            if name in ("mathbf", "textbf", "boldsymbol", "bm"):
                return f"<b>{body}</b>"
            if name in ("textit", "mathit"):
                return f"<i>{body}</i>"
            if name in ("texttt", "mathtt"):
                return f"<tt>{body}</tt>"
            return body
        if name in ("begin", "end"):
            self._group_src()                       # nome dell'ambiente
            return ""
        if name in _SYMBOLS:
            # Come in LaTeX, lo spazio dopo una lettera greca non conta:
            # \Delta E è «ΔE».
            if name[0].isalpha() and _SYMBOLS[name].isalpha():
                while self.s[self.i:self.i + 1] == " ":
                    self.i += 1
            return _SYMBOLS[name]
        return escape(name)                         # \sin, \log, \max …


def latex_to_pango(src):
    """Formula LaTeX -> markup Pango leggibile."""
    try:
        return _Latex(src.strip()).run().strip()
    except Exception:                               # mai far sparire il testo
        return escape(src)


_RE_MATH_CANDIDATE = re.compile(
    r"\$\$([\s\S]+?)\$\$|\\\((.+?)\\\)"
    r"|(?<![\\$\w])\$(?=\S)([^$\n]+?)(?<=\S)\$(?![\d$])")
_RE_WORD = re.compile(r"[^\W\d_]{3,}")


def _looks_like_math(src, dollar):
    """«$5 e $10, poi $x$»: fra due $ può finire della prosa. Tolti i comandi
    LaTeX e il contenuto di \\text{…}, una formula ha variabili di una o due
    lettere: se restano due parole di almeno tre lettere, è prosa."""
    if not dollar:
        return True
    if re.search(r"\\[A-Za-z]", src) and ", " not in src:
        return True                         # comandi LaTeX: è una formula
    bare = re.sub(r"\\(?:text\w*|math\w+|operatorname|mbox)\{[^{}]*\}", " ", src)
    bare = re.sub(r"\\[A-Za-z]+", " ", bare)
    return len(_RE_WORD.findall(bare)) < 2


def sub_inline_math(text, repl):
    """Sostituisce le formule nella frase ($…$, $$…$$, \\(…\\)) con
    repl(sorgente, in_evidenza). Un tratto scartato (vedi _looks_like_math)
    non consuma nulla: la ricerca riprende dal carattere dopo il suo $."""
    out, pos = [], 0
    while True:
        m = _RE_MATH_CANDIDATE.search(text, pos)
        if not m:
            break
        src = m.group(1) or m.group(2) or m.group(3)
        if m.group(3) is not None and not _looks_like_math(src, True):
            out.append(text[pos:m.start() + 1])
            pos = m.start() + 1
            continue
        out.append(text[pos:m.start()])
        out.append(repl(src, m.group(1) is not None))
        pos = m.end()
    out.append(text[pos:])
    return "".join(out)


def latex_to_text(src):
    """Formula LaTeX -> testo Unicode semplice, per i formati senza markup.

    Apici e pedici usano i caratteri Unicode (², ₀) quando esistono per tutti
    i caratteri, altrimenti si scrivono ^(…) e _(…)."""
    markup = latex_to_pango(src)

    def script(m):
        tag, body = m.group(1), plain_text(m.group(2))
        table = _SUP if tag == "sup" else _SUB
        if body and all(c in table for c in body):
            return "".join(table[c] for c in body)
        mark = "^" if tag == "sup" else "_"
        return f"{mark}{body}" if len(body) == 1 else f"{mark}({body})"
    for _ in range(3):                              # apici annidati
        markup = re.sub(r"<(sup|sub)>((?:(?!<(?:sup|sub)>).)*?)</\1>", script, markup)
    # Spazi sottili come spazi normali: non tutti i caratteri tipografici dei
    # libri hanno il glifo, e «299 792 458» resta leggibile.
    text = plain_text(markup).replace("\u2009", " ")
    return re.sub(r"[ \u00a0]{2,}", " ", text).strip()




# ── Parser ──────────────────────────────────────────────────────────────────
def _make_parser():
    return (MarkdownIt("commonmark", {"html": False})
            .enable(["table", "strikethrough"])
            .use(dollarmath_plugin, allow_space=False, allow_digits=False,
                 double_inline=True)
            .use(texmath_plugin, delimiters="brackets")
            .use(tasklists_plugin)
            .use(footnote_plugin))


_PARSER = _make_parser()


def parser():
    """Il parser markdown-it configurato come sopra, uguale in tutti i
    programmi. parser().parse(testo) dà i token (con token.map, le righe del
    sorgente); parser().render(testo) dà l'HTML."""
    return _PARSER


# ── Testo in linea -> Pango ─────────────────────────────────────────────────
# Pango apre i link con il gestore di sistema: solo indirizzi web e posta.
_SAFE_LINK = ("http://", "https://", "mailto:")
_HEADING_SIZE = ("xx-large", "x-large", "large", "large", "medium", "medium")


def _link(href, body):
    if href.lower().startswith(_SAFE_LINK):
        return f'<a href="{escape(href)}">{body}</a>'
    return body


def _inline(nodes):
    out = []
    for n in nodes:
        t = n.type
        if t == "text":
            out.append(escape(n.content))
        elif t in ("softbreak", "hardbreak"):
            # CommonMark lascia al programma la resa dell'a capo morbido:
            # nella chat e nelle anteprime si va a capo come nel sorgente.
            out.append("\n")
        elif t == "code_inline":
            out.append(f"<tt>{escape(n.content)}</tt>")
        elif t in ("math_inline", "math_inline_double"):
            out.append(latex_to_pango(n.content))
        elif t == "strong":
            out.append(f"<b>{_inline(n.children)}</b>")
        elif t == "em":
            out.append(f"<i>{_inline(n.children)}</i>")
        elif t == "s":
            out.append(f"<s>{_inline(n.children)}</s>")
        elif t == "link":
            out.append(_link(n.attrs.get("href", ""), _inline(n.children)))
        elif t == "image":
            src = str(n.attrs.get("src", ""))
            out.append(_link(src, escape(n.content or src)))
        elif t == "footnote_ref":
            out.append(f"<sup>[{n.meta['id'] + 1}]</sup>")
        elif t in ("html_inline", "footnote_anchor"):
            pass            # casella delle liste di attività; ritorno dalla nota
        elif n.children:
            out.append(_inline(n.children))
        else:
            out.append(escape(n.content))
    return "".join(out)


def inline_to_pango(text):
    """Testo in linea (una riga, una cella) -> markup Pango."""
    tokens = _PARSER.parseInline(text.strip())
    if not tokens:
        return ""
    return _inline(SyntaxTreeNode(tokens).children[0].children)


# ── Blocchi ─────────────────────────────────────────────────────────────────
def _prefix(markup, first, rest):
    """Mette first davanti alla prima riga del markup e rest davanti alle
    altre (rientri di elenchi e citazioni)."""
    lines = markup.split("\n")
    return "\n".join([first + lines[0]] + [rest + line for line in lines[1:]])


def _strip_newline(src):
    return src[:-1] if src.endswith("\n") else src


def _table(node):
    aligns, header, rows = [], [], []
    for section in node.children:                  # thead, tbody
        for tr in section.children:
            cells = []
            for cell in tr.children:
                cells.append(_inline(cell.children[0].children) if cell.children else "")
                if section.type == "thead":
                    style = str(cell.attrs.get("style", ""))
                    aligns.append(style.split(":", 1)[1] if ":" in style else "left")
            if section.type == "thead":
                header = cells
            else:
                rows.append(cells)
    return ("table", aligns, header, rows)


def _paragraph(node):
    inline = node.children[0].children if node.children else []
    real = [c for c in inline if not (c.type == "text" and not c.content.strip())]
    if len(real) == 1 and real[0].type == "math_inline_double":
        return ("math", latex_to_pango(real[0].content))   # $$…$$ da sola
    return ("text", _inline(inline))


def _list(node, out):
    ordered = node.type == "ordered_list"
    number = int(node.attrs.get("start", 1)) if ordered else 1
    items = []
    tight = True
    for item in node.children:
        sub = []
        _walk(item.children, sub)
        tight = tight and all(c.hidden for c in item.children if c.type == "paragraph")
        if "task-list-item" in str(item.attrs.get("class", "")):
            first = item.children[0] if item.children else None
            box = first.children[0].children[0] if first and first.children and \
                first.children[0].children else None
            mark = "☑" if box is not None and "checked" in box.content else "☐"
        else:
            mark = f"{number}." if ordered else "•"
        number += 1
        if not sub or sub[0][0] != "text":
            sub.insert(0, ("text", ""))
        head = sub[0][1].lstrip(" ")
        sub[0] = ("text", _prefix(head, f"{mark}  ", "    "))
        sub[1:] = [("text", _prefix(b[1], "    ", "    ")) if b[0] == "text" else b
                   for b in sub[1:]]
        items.extend(sub)
    # Elenco «stretto» (voci senza righe vuote fra loro): un solo blocco,
    # come nel sorgente; elenco «largo»: un blocco per paragrafo.
    merged = []
    for block in items:
        if tight and block[0] == "text" and merged and merged[-1][0] == "text":
            merged[-1] = ("text", merged[-1][1] + "\n" + block[1])
        else:
            merged.append(block)
    out.extend(merged)

def _walk(nodes, out):
    for n in nodes:
        t = n.type
        if t == "paragraph":
            out.append(_paragraph(n))
        elif t == "heading":
            size = _HEADING_SIZE[int(n.tag[1]) - 1]
            body = _inline(n.children[0].children) if n.children else ""
            out.append(("text", f'<span size="{size}" weight="bold">{body}</span>'))
        elif t == "fence":
            lang = n.info.split()[0].lower() if n.info.strip() else ""
            out.append(("code", lang, _strip_newline(n.content)))
        elif t == "code_block":
            out.append(("code", "", _strip_newline(n.content)))
        elif t.startswith("math_block"):
            out.append(("math", latex_to_pango(n.content)))
        elif t == "table":
            out.append(_table(n))
        elif t == "hr":
            out.append(("hr",))
        elif t in ("bullet_list", "ordered_list"):
            _list(n, out)
        elif t == "blockquote":
            sub = []
            _walk(n.children, sub)
            # «┃ » davanti a ogni riga, testo in corsivo.
            out.extend(("text", "┃ <i>" + _prefix(b[1], "", "┃ ") + "</i>")
                       if b[0] == "text" else b for b in sub)
        elif t == "footnote_block":
            out.append(("hr",))
            for note in n.children:
                sub = []
                _walk(note.children, sub)
                if not sub or sub[0][0] != "text":
                    sub.insert(0, ("text", ""))
                label = f"<sup>[{note.meta['id'] + 1}]</sup> "
                sub[0] = ("text", _prefix(sub[0][1], label, ""))
                out.extend(sub)
        elif n.children:
            _walk(n.children, out)


def parse_blocks(text):
    """Divide il testo in blocchi (vedi l'intestazione del modulo).

    Funziona anche su testo incompleto, durante lo streaming: per CommonMark
    un blocco di codice non chiuso arriva fino alla fine, e una formula $$
    non chiusa resta testo finché non si chiude."""
    tree = SyntaxTreeNode(_PARSER.parse(text.replace("\r\n", "\n")))
    blocks = []
    _walk(tree.children, blocks)
    return blocks


# ── Strumenti per riga (editor) ─────────────────────────────────────────────
# Usati da math_to_text, table_at, display_math_at e has_inline_math.
_RE_CODE_SPAN = re.compile(r"(`+)(.+?)\1")
_RE_TABLE_SEP = re.compile(r"^\s*\|?\s*:?-+:?\s*(\|\s*:?-+:?\s*)*\|?\s*$")

_RE_FENCE_LINE = re.compile(r"^\s{0,3}(`{3,}|~{3,})")

def math_to_text(text):
    """Sostituisce le formule di un testo Markdown con testo Unicode.

    Una formula su riga propria ($$…$$ o \\[…\\], anche su più righe) diventa
    una riga a sé; quelle nella frase restano nella frase. Blocchi e frammenti
    di codice restano intatti."""
    lines = text.split("\n")
    out, i, fence = [], 0, None
    while i < len(lines):
        line = lines[i]
        f = _RE_FENCE_LINE.match(line)
        if fence:
            out.append(line)
            if f and f.group(1)[0] == fence[0] and len(f.group(1)) >= len(fence):
                fence = None
            i += 1
            continue
        if f:
            fence = f.group(1)
            out.append(line)
            i += 1
            continue
        block = _display_math(lines, i)
        if block:
            indent = line[:len(line) - len(line.lstrip())]
            out.append(indent + latex_to_text(block[0]))
            i = block[1]
            continue
        # Il codice in linea si mette da parte prima: un $ dentro `…` non
        # deve aprire una formula.
        keep = []

        def stash(m):
            keep.append(m.group(0))
            return f"\x00{len(keep) - 1}\x00"
        line = _RE_CODE_SPAN.sub(stash, line)
        line = sub_inline_math(line, lambda src, _big: latex_to_text(src))
        out.append(re.sub(r"\x00(\d+)\x00", lambda m: keep[int(m.group(1))], line))
        i += 1
    return "\n".join(out)


def table_at(lines, i):
    """Tabella Markdown che comincia alla riga i: (allineamenti, intestazione,
    righe, indice della riga dopo la tabella), celle come testo Markdown.
    None se lì non comincia una tabella."""
    if not _is_table(lines, i):
        return None
    header = _split_row(lines[i])
    ncol = len(header)
    aligns = (_aligns(lines[i + 1]) + ["left"] * ncol)[:ncol]
    rows, j = [], i + 2
    while j < len(lines) and lines[j].strip() and "|" in lines[j]:
        rows.append((_split_row(lines[j]) + [""] * ncol)[:ncol])
        j += 1
    return aligns, header, rows, j


def display_math_at(lines, i):
    """Formula su riga propria ($$…$$ o \\[…\\], anche su più righe) che
    comincia alla riga i: (sorgente LaTeX, indice della riga dopo), o None."""
    return _display_math(lines, i)


def has_inline_math(line):
    """True se la riga contiene una formula $…$, $$…$$ o \\(…\\) fuori dal
    codice in linea."""
    found = []
    sub_inline_math(_RE_CODE_SPAN.sub("", line), lambda src, _big: found.append(src) or "")
    return bool(found)

def _split_row(line):
    s = line.strip()
    if s.startswith("|"):
        s = s[1:]
    if s.endswith("|") and not s.endswith("\\|"):
        s = s[:-1]
    cells, cur, in_code, i = [], [], False, 0
    while i < len(s):
        ch = s[i]
        if ch == "\\" and s[i + 1:i + 2] == "|":
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


def _is_table(lines, i):
    if i + 1 >= len(lines) or "|" not in lines[i]:
        return False
    sep = lines[i + 1]
    if "-" not in sep or not _RE_TABLE_SEP.match(sep):
        return False
    return len(_split_row(lines[i])) == len(_split_row(sep))


def _aligns(sep):
    out = []
    for c in _split_row(sep):
        left, right = c.startswith(":"), c.endswith(":")
        out.append("center" if left and right else "right" if right else "left")
    return out


def _display_math(lines, i):
    """Formula su riga propria ($$…$$ o \\[…\\], anche su più righe):
    (sorgente, indice della riga dopo) oppure None se non c'è o non è chiusa."""
    stripped = lines[i].strip()
    for opener, closer in (("$$", "$$"), ("\\[", "\\]")):
        if not stripped.startswith(opener):
            continue
        rest = stripped[len(opener):]
        if rest.rstrip().endswith(closer):
            src = rest.rstrip()[:-len(closer)]
            return (src, i + 1) if src.strip() else None
        if closer in rest:
            return None                             # $$a$$ seguito da testo
        for j in range(i + 1, len(lines)):
            if closer in lines[j]:
                tail = lines[j][:lines[j].find(closer)]
                return " ".join([rest] + lines[i + 1:j] + [tail]), j + 1
        return None
    return None


