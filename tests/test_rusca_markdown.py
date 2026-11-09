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
          "ruscawriter/src/ruscawriter/rusca_markdown.py",
          "ruscatranslator/rusca_markdown.py"]
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
    def test_external_component_identical(self):
        digests = set()
        for p in COPIES:
            with open(os.path.join(TOOLS, os.path.dirname(p), "markdown_it_mark.py"), "rb") as f:
                digests.add(hashlib.sha256(f.read()).hexdigest())
        self.assertEqual(len(digests), 1, "le copie di markdown_it_mark.py sono diverse")

    def test_no_external_code_in_engine(self):
        # Specifiche, sezione 6, regola 6: il codice esterno sta in file a sé.
        with open(os.path.join(TOOLS, COPIES[0]), encoding="utf-8") as f:
            engine = f.read()
        self.assertNotIn("Permission is hereby granted", engine)
        self.assertNotIn("Copyright (c)", engine)
        self.assertEqual(md.mark_plugin.__module__.rsplit(".", 1)[-1], "markdown_it_mark")

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

    def _failed(self, p):
        return [e["example"] for e in self.examples
                if _normalize(p.render(e["markdown"])) != _normalize(e["html"])]

    def test_spec_examples(self):
        # La configurazione dei programmi, con l'HTML grezzo attivo solo qui
        # e senza link automatici: nessuna estensione (formule, tabelle, note,
        # liste di attività, evidenziato) cambia il comportamento di CommonMark.
        p = md._make_parser()
        p.options["html"] = True
        p.disable("linkify")
        failed = self._failed(p)
        self.assertEqual(failed, [], f"esempi CommonMark non superati: {failed}")

    def test_autolink_extension_changes_only_bare_urls(self):
        # I link automatici di GFM cambiano di proposito solo gli esempi in cui
        # CommonMark lascia come testo un indirizzo scritto senza < >.
        p = md._make_parser()
        p.options["html"] = True
        self.assertEqual(self._failed(p), [601, 607, 610, 611])

    def test_parse_source_same_tokens(self):
        # La resa live vede esattamente quello che vedono anteprima ed export.
        def shape(tokens):
            return [(t.type, t.content, t.markup,
                     [(c.type, c.content, c.markup) for c in t.children or []])
                    for t in tokens]
        different = [e["example"] for e in self.examples
                     if shape(md.parser().parse(e["markdown"]))
                     != shape(md.parse_source(e["markdown"]))]
        self.assertEqual(different, [])

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

    def test_mark(self):
        self.check("a ==b **c**== d",
                   [("text", 'a <span background="#f2a7c8" foreground="#2d0a1d">b <b>c</b></span> d')])
        self.check("== no ==", [("text", "== no ==")])
        self.check("===x===",
                   [("text", '=<span background="#f2a7c8" foreground="#2d0a1d">x</span>=')])

    def test_gfm_autolinks(self):
        def hrefs(src):
            return [t.attrs.get("href") for t in md.parser().parseInline(src)[0].children
                    if t.type == "link_open"]
        self.assertEqual(hrefs("vedi https://x.org/a."), ["https://x.org/a"])
        self.assertEqual(hrefs("vedi www.debian.org."), ["http://www.debian.org"])
        self.assertEqual(hrefs("scrivi a info@ruscalinux.org"), ["mailto:info@ruscalinux.org"])
        # Senza www. né protocollo non è un link: .sh, .py e .md sono domini
        for src in ("build.sh", "raglin.py", "NOTA-IA.md", "debian.org",
                    "ftp://x.org", "//x.org/a", "`https://x.org`"):
            self.assertEqual(hrefs(src), [], src)

    def test_hr(self):
        self.check("a\n\n***\n\nb", [("text", "a"), ("hr",), ("text", "b")])


class SourcePositions(unittest.TestCase):
    def spans(self, src):
        inline = md.parse_source(src)[1]
        return [(c.type, inline.content[slice(*c.meta["src"])])
                for c in inline.children if "src" in c.meta and c.type != "text"]

    def test_positions(self):
        self.assertEqual(self.spans("a **b\nc** `d*e*` [f *g*](h) ~~i~~ ==j== ![k](l)"),
                         [("strong_open", "*"), ("softbreak", "\n"), ("strong_close", "*"),
                          ("code_inline", "`d*e*`"), ("link_open", "[f *g*](h)"),
                          ("em_open", "*"), ("em_close", "*"), ("link_close", "[f *g*](h)"),
                          ("s_open", "~~"), ("s_close", "~~"), ("mark_open", "=="),
                          ("mark_close", "=="), ("image", "![k](l)")])

    def test_link_label_end(self):
        src = "[a [b] `]` c](d)"
        self.assertEqual(src[md.link_label_end(src, 0)], "]")
        self.assertEqual(md.link_label_end(src, 0), 12)
        self.assertEqual(md.link_label_end("[aperta", 0), -1)


class Robustness(unittest.TestCase):
    """Testi trovati con prove casuali che bloccavano o facevano fallire
    l'analisi (plugin di mdit-py-plugins 0.4.2). Anche un modello in
    RuscaLLama, o chi scrive nella resa live di RuscaMark, può produrli."""

    def parse_within(self, src, seconds=3):
        import signal

        def timeout(*_):
            raise TimeoutError(repr(src))
        old = signal.signal(signal.SIGALRM, timeout)
        signal.alarm(seconds)
        try:
            return md.parse_blocks(src), md.parse_source(src)
        finally:
            signal.alarm(0)
            signal.signal(signal.SIGALRM, old)

    def test_texmath_block_never_loops(self):
        self.parse_within(">\\[\n\n\\]")                    # ciclo infinito
        self.assertEqual(md.parse_blocks("\\[\nx^2\n\\]"), [("math", "x²")])
        # Dentro una citazione texmath leggerebbe anche i «>»: resta testo.
        self.assertNotIn("math", [b[0] for b in md.parse_blocks("> \\[\n> x\n> \\]")])

    def test_texmath_block_after_paragraph(self):
        # In markdown-it-py 3.0 la regola dei titoli sottolineati lascia
        # state.parentType a «paragraph» dopo un paragrafo: la protezione
        # non deve fidarsene.
        self.assertEqual(md.parse_blocks("testo\n\n\\[\nq\n\\]"),
                         [("text", "testo"), ("math", "q")])

    def test_nested_footnote_definitions(self):
        self.parse_within("[^1]:- [^1]:")                     # token sbilanciati

    def test_inline_footnotes_are_text(self):
        self.parse_within("^[[^1]]\n[^1]:[^1]")              # KeyError nel plugin
        self.assertEqual(md.parse_blocks("a^[nota] b"), [("text", "a^[nota] b")])


class OtherUses(unittest.TestCase):
    def test_render_html(self):
        self.assertEqual(md.render_html("**a**\nb $x^2$ <i>c</i>"),
                         '<p><strong>a</strong><br />\nb <span class="math">x²</span> '
                         '&lt;i&gt;c&lt;/i&gt;</p>\n')
        self.assertIn('<pre><code class="language-py">print(1)\n</code></pre>',
                      md.render_html("```py\nprint(1)\n```"))
        self.assertIn('<p class="math">a⁄b</p>', md.render_html("$$\n\\frac{a}{b}\n$$"))

    def test_code_blocks(self):
        self.assertEqual(
            md.code_blocks("```PY\na\n```\n\n~~~\nb\n\n~~~\n\n    c\n\n"
                           "````md\n```js\nd\n```\n````\n\n> ```sh\n> e\n> ```"),
            [("py", "a"), ("", "b\n"), ("", "c"), ("md", "```js\nd\n```"), ("sh", "e")])

    def test_block_ranges(self):
        doc = ("# T\n\n- a\n\n- b\n\n````\n```\n\nx\n```\n````\n\n"
               "[r]: https://x.it\n[^1]: nota\n\n> q\n>\n> q2")
        lines = doc.split("\n")
        self.assertEqual([lines[a:b][0] for a, b in md.block_ranges(doc)],
                         ["# T", "- a", "````", "[r]: https://x.it", "> q"])
        # ogni riga non vuota sta in un blocco
        inside = {i for a, b in md.block_ranges(doc) for i in range(a, b)}
        self.assertTrue(all(i in inside for i, ln in enumerate(lines) if ln.strip()))


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
