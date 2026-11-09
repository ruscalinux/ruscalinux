"""RuscaLinux OS Tools — test di rusca_markdown.py — 1.99.2 — GPL-3.0

Si lanciano dalla radice del repository:
    python3 -m unittest tests/test_rusca_markdown.py

Servono python3-markdown-it e python3-mdit-py-plugins; con gir1.2-pango-1.0
si controlla anche che il markup prodotto sia accettato da Pango.
"""

import hashlib
import json
import os
import re
import sys
import unittest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TOOLS = os.path.join(REPO, "tools")
COPIES = ["ruscallama/rusca_markdown.py", "ruscamark/rusca_markdown.py",
          "ruscawriter/src/ruscawriter/rusca_markdown.py"]
sys.path.insert(0, os.path.join(TOOLS, "ruscallama"))
import rusca_markdown as md  # noqa: E402

try:
    import gi
    gi.require_version("Pango", "1.0")
    from gi.repository import Pango
except (ImportError, ValueError):
    Pango = None


def _normalize(html):
    # Come il programma ufficiale di verifica CommonMark: un elemento vuoto
    # con o senza a capo all'interno è lo stesso HTML.
    return re.sub(r"<(\w+)>\n</\1>", r"<\1></\1>", html)


class Copies(unittest.TestCase):
    def test_identical(self):
        digests = set()
        for p in COPIES:
            with open(os.path.join(TOOLS, p), "rb") as f:
                digests.add(hashlib.sha256(f.read()).hexdigest())
        self.assertEqual(len(digests), 1, "le copie di rusca_markdown.py sono diverse")


class CommonMark(unittest.TestCase):
    """Conformità agli esempi ufficiali della specifica CommonMark 0.30."""

    @classmethod
    def setUpClass(cls):
        path = os.path.join(REPO, "tests", "data", "commonmark-0.30-spec.json")
        with open(path, encoding="utf-8") as f:
            cls.examples = json.load(f)

    def test_spec_examples(self):
        # La configurazione dei programmi, con l'HTML grezzo attivo solo qui:
        # verifica che nessuna estensione (formule, tabelle, note, liste di
        # attività) cambi il comportamento di CommonMark.
        p = md._make_parser()
        p.options["html"] = True
        failed = [e["example"] for e in self.examples
                  if _normalize(p.render(e["markdown"])) != _normalize(e["html"])]
        self.assertEqual(failed, [], f"esempi CommonMark non superati: {failed}")

    def test_raw_html_is_text(self):
        self.assertFalse(md.parser().options["html"])
        self.assertEqual(md.parse_blocks("a <b>b</b>"), [("text", "a &lt;b&gt;b&lt;/b&gt;")])


class Blocks(unittest.TestCase):
    def check(self, src, expected):
        self.assertEqual(md.parse_blocks(src), expected)

    def test_paragraph_and_inline(self):
        self.check("**a** *b* ~~c~~ `d` &copy;",
                   [("text", "<b>a</b> <i>b</i> <s>c</s> <tt>d</tt> ©")])

    def test_headings(self):
        self.check("# Uno", [("text", '<span size="xx-large" weight="bold">Uno</span>')])
        self.check("Due\n---", [("text", '<span size="x-large" weight="bold">Due</span>')])

    def test_code(self):
        self.check("```Python\nx = 1\n```", [("code", "python", "x = 1")])
        self.check("    rientrato", [("code", "", "rientrato")])
        # streaming: un blocco non chiuso arriva fino alla fine
        self.check("```sh\nls", [("code", "sh", "ls")])

    def test_tight_list_is_one_block(self):
        self.check("1. uno\n   - [x] fatto\n   - [ ] da fare\n2. due",
                   [("text", "1.  uno\n    ☑  fatto\n    ☐  da fare\n2.  due")])

    def test_loose_list(self):
        self.check("- uno\n\n  segue\n- due",
                   [("text", "•  uno"), ("text", "    segue"), ("text", "•  due")])

    def test_ordered_start(self):
        self.check("3) tre\n4) quattro", [("text", "3.  tre\n4.  quattro")])

    def test_quote(self):
        self.check("> a\n> b", [("text", "┃ <i>a\n┃ b</i>")])
        self.check("> - voce", [("text", "┃ <i>•  voce</i>")])

    def test_links(self):
        self.check('[a](https://x.org "t") <https://y.org> [b][r]\n\n[r]: mailto:i@x.org',
                   [("text", '<a href="https://x.org">a</a> '
                             '<a href="https://y.org">https://y.org</a> '
                             '<a href="mailto:i@x.org">b</a>')])
        # markdown-it rifiuta javascript: e file:, e qui non si apre altro
        self.check("[x](javascript:alert(1))", [("text", "[x](javascript:alert(1))")])
        self.check("[x](ftp://h/f)", [("text", "x")])

    def test_table(self):
        self.check("| a | **b** |\n|:-:|-:|\n| 1 | `2\\|3` |",
                   [("table", ["center", "right"], ["a", "<b>b</b>"],
                     [["1", "<tt>2|3</tt>"]])])

    def test_footnotes(self):
        self.check("testo[^n]\n\n[^n]: nota",
                   [("text", "testo<sup>[1]</sup>"), ("hr",),
                    ("text", "<sup>[1]</sup> nota")])

    def test_hr(self):
        self.check("a\n\n***\n\nb", [("text", "a"), ("hr",), ("text", "b")])


class Math(unittest.TestCase):
    def test_pandoc_dollar_rules(self):
        self.assertEqual(md.parse_blocks("da $5 a $10"), [("text", "da $5 a $10")])
        self.assertEqual(md.parse_blocks("da $5 a $x$ euro"), [("text", "da $5 a x euro")])
        self.assertEqual(md.parse_blocks("`$x$`"), [("text", "<tt>$x$</tt>")])

    def test_inline_and_display(self):
        self.assertEqual(md.parse_blocks("$E=mc^2$ e \\(\\alpha\\)"), [("text", "E=mc² e α")])
        self.assertEqual(md.parse_blocks("$$\n\\frac{a}{b}\n$$"), [("math", "a⁄b")])
        self.assertEqual(md.parse_blocks("\\[x^2\\]"), [("math", "x²")])
        self.assertEqual(md.parse_blocks("$$x$$"), [("math", "x")])

    def test_unclosed_display_math_stays_text(self):
        self.assertEqual(md.parse_blocks("$$\n\\frac"), [("text", "$$\n\\frac")])

    def test_latex_to_text(self):
        self.assertEqual(md.latex_to_text("\\sqrt{x^{a+b}}"), "√(x^(a+b))")


@unittest.skipIf(Pango is None, "Pango non disponibile")
class PangoMarkup(unittest.TestCase):
    SAMPLES = [
        "## T `x`\n\n**a *b* c** [l](https://x.org) ~~s~~",
        "- [x] *a*\n\n  > b `c`\n- d[^1]\n\n[^1]: **n** $x^2$",
        "1) uno\n2) **due\nlinea**\n\n| *a* | b |\n|---|---|\n| `<` | & |",
        "> > annidata\n>\n> **fine",
    ]

    def test_markup_is_valid(self):
        for src in self.SAMPLES:
            for block in md.parse_blocks(src):
                cells = []
                if block[0] in ("text", "math"):
                    cells = [block[1]]
                elif block[0] == "table":
                    cells = block[2] + [c for row in block[3] for c in row]
                for markup in cells:
                    # <a href> è di Gtk.Label, non di Pango
                    Pango.parse_markup(re.sub(r"</?a\b[^>]*>", "", markup), -1, "\0")


if __name__ == "__main__":
    unittest.main()
