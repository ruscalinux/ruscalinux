"""RuscaLinux OS Apps — test del Markdown di RuscaMark — 1.99.3 — GPL-3.0

MarkdownDoc (apps/ruscamark/ruscamark.py) usa l'analisi del motore comune
rusca_markdown.py e la rende in HTML (export), Pango (anteprima) ed elementi
del PDF. Si lanciano dalla radice del repository:
    python3 -m unittest tests/test_ruscamark_markdown.py

Servono, oltre alle librerie del motore comune, python3-gi con GTK 4 e
libadwaita, perché ruscamark.py le importa: senza, i test si saltano.
"""

import importlib.util
import os
import sys
import tempfile
import unittest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RUSCAMARK = os.path.join(REPO, "apps", "ruscamark")

try:
    sys.path.insert(0, RUSCAMARK)
    _spec = importlib.util.spec_from_file_location(
        "ruscamark_under_test", os.path.join(RUSCAMARK, "ruscamark.py"))
    rm = importlib.util.module_from_spec(_spec)
    _spec.loader.exec_module(rm)
except (ImportError, ValueError) as e:            # GTK 4 o libadwaita mancanti
    rm, _missing = None, e


def html(src, **kw):
    return rm.MarkdownDoc(src).to_html(**kw)


@unittest.skipIf(rm is None, "GTK 4 o libadwaita non disponibili")
class Html(unittest.TestCase):
    def test_headings_with_unique_ids(self):
        self.assertEqual(html("# Uno\n\nDue\n---\n\n# Uno"),
                         '<h1 id="uno">Uno</h1>\n<h2 id="due">Due</h2>\n<h1 id="uno-1">Uno</h1>')

    def test_hard_breaks(self):
        # Il vecchio parser toglieva gli spazi a fine riga: «due spazi» non
        # andava mai a capo, anche se il manuale lo promette.
        self.assertEqual(html("uno  \ndue\\\ntre"), "<p>uno<br>\ndue<br>\ntre</p>")

    def test_code_inside_link(self):
        # Il vecchio parser esportava «0» al posto del codice.
        self.assertEqual(html("[`LICENSE`](LICENSE)"),
                         '<p><a href="LICENSE"><code>LICENSE</code></a></p>')

    def test_links(self):
        self.assertEqual(html('[Debian][deb]\n\n[deb]: https://debian.org "Debian"'),
                         '<p><a href="https://debian.org" title="Debian">Debian</a></p>')
        self.assertEqual(html("[vai](#uno)"), '<p><a href="#uno">vai</a></p>')
        self.assertEqual(html("vedi www.debian.org e build.sh"),
                         '<p>vedi <a href="http://www.debian.org">www.debian.org</a> e build.sh</p>')

    def test_images(self):
        self.assertEqual(html('![Grafico](img/g.png "tit")'),
                         '<p><img src="img/g.png" alt="Grafico" title="tit"></p>')
        self.assertEqual(html("![G](img/g.png)", img_src=lambda s: "data:" + s),
                         '<p><img src="data:img/g.png" alt="G"></p>')

    def test_lists(self):
        self.assertEqual(html("- [x] fatto\n- [ ] da fare"),
                         '<ul class="task-list">\n'
                         '<li class="task"><input type="checkbox" disabled checked> fatto</li>\n'
                         '<li class="task"><input type="checkbox" disabled> da fare</li>\n</ul>')
        self.assertEqual(html("3. tre\n4. quattro"),
                         '<ol start="3">\n<li>tre</li>\n<li>quattro</li>\n</ol>')

    def test_footnotes(self):
        self.assertEqual(html("a[^n]\n\n[^n]: **nota**"),
                         '<p>a<sup class="fnref"><a href="#fn-n" id="fnref-n">1</a></sup></p>\n'
                         '<section class="footnotes">\n<hr>\n<ol>\n'
                         '<li id="fn-n"><strong>nota</strong> '
                         '<a href="#fnref-n" class="fnback">↩</a></li>\n</ol>\n</section>')

    def test_math(self):
        self.assertEqual(html("$x^2$ e\n\n$$\n\\frac{a}{b}\n$$"),
                         '<p>x² e</p>\n<p><span style="font-size: 1.2em">a⁄b</span></p>')

    def test_raw_html_and_escapes(self):
        self.assertEqual(html("<b>no</b> & \\*"), "<p>&lt;b&gt;no&lt;/b&gt; &amp; *</p>")

    def test_table(self):
        self.assertEqual(html("| a | b |\n|:-|-:|\n| 1 | 2 |"),
                         '<div class="table-wrap"><table>\n'
                         '<thead><tr><th style="text-align:left">a</th>'
                         '<th style="text-align:right">b</th></tr></thead>\n<tbody>\n'
                         '<tr><td style="text-align:left">1</td>'
                         '<td style="text-align:right">2</td></tr>\n</tbody></table></div>')

    def test_mark(self):
        self.assertEqual(html("==ev=="), "<p><mark>ev</mark></p>")


@unittest.skipIf(rm is None, "GTK 4 o libadwaita non disponibili")
class PreviewAndPrint(unittest.TestCase):
    def test_preview(self):
        items = rm.MarkdownDoc("![Grafico](<img/grafico è.png>)\n\nuno  \ndue\n\n- [x] fatto"
                               ).to_preview(rm.PREVIEW_GUIDE)
        self.assertEqual(items[0], ("img", "img/grafico è.png", "Grafico", ""))
        self.assertIn(("m", "uno", False), items)          # a capo forzato:
        self.assertIn(("m", "due", False), items)          # due righe
        self.assertTrue(any("☑" in it[1] and "strikethrough" in it[1]
                            for it in items if it[0] == "m"))

    def test_preview_footnotes(self):
        items = rm.MarkdownDoc("n[^a]\n\n[^a]: nota").to_preview(rm.PREVIEW_GUIDE)
        self.assertTrue(items[-1][1].endswith("</span> nota"))

    def test_print_lone_image(self):
        self.assertEqual(rm.MarkdownDoc("![Grafico](img/g.png)").to_print(rm.PRINT_COLORS),
                         [("img", "img/g.png", "Grafico", 0.0, 0.0)])

    def test_plain_title(self):
        self.assertEqual(rm.MarkdownDoc("").plain("Titolo **con** `codice` e [link](x)"),
                         "Titolo con codice e link")


@unittest.skipIf(rm is None, "GTK 4 o libadwaita non disponibili")
class Live(unittest.TestCase):
    """Resa live: stili e marcatori nascosti, dal motore comune."""

    def styled(self, text):
        out = []
        for _a, _z, styles, hides in rm.live_elements(text):
            out += [(name, text[x:y]) for name, x, y in styles if name != "block"]
            out += [(h[2] if len(h) > 2 else "hide", text[h[0]:h[1]]) for h in hides]
        return out

    def test_inline_like_the_preview(self):
        got = self.styled("Un **grassetto\nsu due** e ***entrambi***, snake_case_name, "
                          "`co**de`, \\*no\\*.")
        self.assertIn(("bold", "grassetto\nsu due"), got)      # anche su due righe
        self.assertIn(("italic", "**entrambi**"), got)
        self.assertIn(("bold", "entrambi"), got)
        self.assertIn(("code", "co**de"), got)
        self.assertNotIn("italic", [n for n, t in got if "case" in t])
        self.assertEqual([n for n, _ in got].count("bold"), 2)

    def test_links(self):
        got = self.styled("[`LICENSE`](LICENSE) <https://x.org> www.debian.org a@b.it build.sh "
                          "[rif][r]\n\n[r]: https://y.org")
        links = [t for n, t in got if n == "link"]
        self.assertEqual(links, ["`LICENSE`", "https://x.org", "www.debian.org", "a@b.it", "rif"])
        self.assertIn(("fndef", "[r]: https://y.org"), got)

    def test_headings(self):
        got = self.styled("## Titolo ##\n\nSotto\n---")
        self.assertIn(("h2", "## Titolo ##"), got)
        self.assertIn(("hide", "## "), got)
        self.assertIn(("hide", " ##"), got)
        self.assertIn(("h2", "Sotto"), got)
        self.assertIn(("setext", "---"), got)

    def test_blocks(self):
        got = self.styled("````md\n```python\nprint()\n```\n````\n\n    rientrato\n\n"
                          "> - [x] fatta *bene*\n\n1. uno")
        # Il blocco interno è testo del blocco esterno: si nascondono solo i ````.
        self.assertEqual([t for n, t in got if n == "hide"][:2], ["````md", "````"])
        self.assertIn(("code", "```python"), got)
        self.assertIn(("code", "    rientrato"), got)
        self.assertIn(("task_done", "fatta *bene*"), got)
        self.assertIn(("italic", "bene"), got)
        self.assertIn(("bullet", "1."), got)

    def test_footnotes(self):
        got = self.styled("Testo[^n].\n\n[^n]: La **nota**.")
        self.assertIn(("fnref", "[^n]"), got)
        self.assertIn(("fndef", "[^n]: La **nota**."), got)
        self.assertIn(("bold", "nota"), got)

    def conditional(self, text):
        """Marcatori nascosti e stili che valgono col cursore lontano."""
        out = []
        for _a, _z, _styles, hides in rm.live_elements(text):
            out += [(h[2] if len(h) > 2 else "hide", text[h[0]:h[1]]) for h in hides]
        return out

    def test_math(self):
        got = self.styled("$E=mc^2$, $x_{i+1}$, \\(a^b\\) e $5 e $10.")
        self.assertIn(("math", "E=mc^2"), got)
        self.assertNotIn("math", [n for n, t in got if "5" in t])   # prezzi, non formule
        cond = self.conditional("$E=mc^2$ e $x_{i+1}$")
        self.assertIn(("hide", "$"), cond)
        self.assertIn(("hide", "^"), cond)
        self.assertIn(("sup", "2"), cond)
        self.assertIn(("hide", "_{"), cond)
        self.assertIn(("sub", "i+1"), cond)

    def test_display_math(self):
        cond = self.conditional("$$\n\\frac{a}{b}\n$$\n\n$$ y $$ (1)")
        self.assertEqual([t for n, t in cond if n == "hide"], ["$$", "$$", "$$", "$$"])
        got = self.styled("$$\nx\n$$")
        self.assertIn(("math_block", "x\n"), got)

    def test_backslashes(self):
        cond = self.conditional("\\*non corsivo\\* e a capo\\\nqui")
        self.assertEqual(cond, [("hide", "\\"), ("hide", "\\"), ("hide", "\\")])

    def test_horizontal_rule(self):
        self.assertIn(("hr_bar", "***\n"), self.conditional("a\n\n***\n\nb"))

    def test_table_keeps_markers(self):
        got = self.styled("| a | *b* |\n|---|---|\n| 1 | 2 |")
        self.assertIn(("table_head", "| a | *b* |"), got)
        self.assertNotIn("italic", [n for n, _ in got])       # colonne allineate


try:
    import cairo
    import gi
    gi.require_version("PangoCairo", "1.0")
    from gi.repository import PangoCairo
    from pypdf import PdfReader
except (ImportError, ValueError):
    PdfReader = None


class _PrintContext:
    """Quello che PdfExporter usa di Gtk.PrintContext, su una pagina A4 di
    cairo.PDFSurface: si prova l'impaginazione vera senza GTK in esecuzione."""
    W, H = 595.28, 841.89

    def __init__(self, cr):
        self.cr = cr

    def get_width(self):
        return self.W

    def get_height(self):
        return self.H

    def create_pango_layout(self):
        return PangoCairo.create_layout(self.cr)

    def get_cairo_context(self):
        return self.cr


class _Op:
    def set_n_pages(self, n):
        self.n = n


@unittest.skipIf(rm is None or PdfReader is None,
                 "GTK 4, libadwaita, pycairo o pypdf non disponibili")
class PdfLinks(unittest.TestCase):
    def export(self, text, theme=None):
        colors = rm.print_colors(theme) if theme else rm.PRINT_COLORS
        items = rm.MarkdownDoc(text).to_print(colors, t=lambda k, **kw: k)
        path = os.path.join(tempfile.mkdtemp(), "prova.pdf")
        surface = cairo.PDFSurface(path, _PrintContext.W, _PrintContext.H)
        cr = cairo.Context(surface)
        ctx, op = _PrintContext(cr), _Op()
        exporter = rm.PdfExporter(items, load_image=lambda src: None, title="Prova",
                                  t=lambda k, **kw: k, theme=theme)
        exporter._begin(op, ctx)
        for page in range(op.n):
            exporter._draw(op, ctx, page)
            cr.show_page()
        surface.finish()                 # qui cairo rifiuta i tag non validi
        return PdfReader(path)

    @staticmethod
    def annots(reader):
        out = []
        for page in reader.pages:
            for a in page.get("/Annots", []):
                a = a.get_object()
                action = a.get("/A", {})
                out.append((str(action.get("/URI") or "interno"), [float(v) for v in a["/Rect"]]))
        return out

    def test_links_are_clickable(self):
        found = self.annots(self.export(
            "# Perché\n\nVedi [il sito](https://www.ruscalinux.org), info@ruscalinux.org, "
            "www.debian.org e [torna su](#perché).\n\n| a |\n|--:|\n| [b](https://x.org) |"))
        self.assertEqual([u for u, _ in found],
                         ["https://www.ruscalinux.org", "mailto:info@ruscalinux.org",
                          "http://www.debian.org", "interno", "https://x.org"])
        margin = 56.7                    # 2 cm: le aree cadono sul testo, non sul bordo
        for _url, (x0, y0, x1, y1) in found:
            self.assertGreaterEqual(x0, margin - 0.5)
            self.assertLessEqual(y1, _PrintContext.H - margin + 0.5)

    def test_only_reachable_links(self):
        # Un link interno a un titolo che non c'è renderebbe non valido tutto
        # il PDF; percorsi relativi e altri protocolli non portano da nessuna parte.
        found = self.annots(self.export(
            "# Uno\n\n[manca](#nessuno), [file](altro.md), [ftp](ftp://x.org) e [ok](#uno)."))
        self.assertEqual([u for u, _ in found], ["interno"])

    def test_link_split_over_two_lines(self):
        found = self.annots(self.export("[" + "parola " * 40 + "](https://x.org)"))
        self.assertGreaterEqual(len(found), 2)
        self.assertTrue(all(u == "https://x.org" for u, _ in found))

    def test_every_theme_exports(self):
        # Ogni tema incluso impagina lo stesso documento con link validi:
        # banner o titolo come testo, fascia in cima, piè di pagina diviso.
        text = ("# Titolo\n\nVedi [il sito](https://www.ruscalinux.org) e [su](#titolo).\n\n"
                "```\ncodice\n```\n\n> citazione\n\n| a | b |\n|---|---|\n| 1 | 2 |\n\n"
                + "Testo lungo. " * 400)
        for tid, theme in rm.load_export_themes().items():
            with self.subTest(theme=tid):
                reader = self.export(text, theme)
                self.assertGreaterEqual(len(reader.pages), 2)
                self.assertEqual([u for u, _ in self.annots(reader)],
                                 ["https://www.ruscalinux.org", "interno"])
                footer = reader.pages[0].extract_text()
                self.assertIn("1 / ", footer)


@unittest.skipIf(rm is None, "GTK 4 o libadwaita non disponibili")
class ExportThemes(unittest.TestCase):
    """Temi di PDF, HTML e anteprima: file .css con variabili (themes/)."""

    def write(self, folder, name, text):
        with open(os.path.join(folder, name), "w", encoding="utf-8") as f:
            f.write(text)

    def load_from(self, *folders):
        saved = rm.THEME_DIRS
        rm.THEME_DIRS = folders
        try:
            return rm.load_export_themes()
        finally:
            rm.THEME_DIRS = saved

    def test_builtin_themes(self):
        themes = self.load_from(os.path.join(RUSCAMARK, "themes"))
        self.assertEqual(list(themes), list(rm.BUILTIN_THEMES))
        for tid, th in themes.items():
            with self.subTest(theme=tid):
                self.assertEqual(set(th), set(rm.GUIDE))
                for k in rm._THEME_COLORS:
                    self.assertIsNotNone(rm._theme_color(th[k]), k)
                self.assertNotEqual(rm.theme_label(tid, th, lambda k, **kw: rm._BUILTIN_STRINGS["it"].get(k, k)),
                                    tid)

    def test_ruscalinux_file_matches_builtin(self):
        # Il file del tema predefinito documenta le variabili: deve dare
        # esattamente il tema incorporato nel programma.
        with open(os.path.join(RUSCAMARK, "themes", "ruscalinux.css"), encoding="utf-8") as f:
            raw = rm.parse_theme_css(f.read())
        self.assertEqual(rm.theme_from_vars(raw), rm.GUIDE)
        names = set(raw) - {"name"}
        documented = set(rm._THEME_COLORS) | set(rm._THEME_GRAD) | set(rm._THEME_CHOICES) \
            | set(rm._THEME_WIDTHS) | {"font", "mono"}
        self.assertEqual(names, documented)

    def test_without_theme_folders(self):
        self.assertEqual(list(self.load_from()), [rm.DEFAULT_EXPORT_THEME])

    def test_invalid_values_fall_back(self):
        d = tempfile.mkdtemp()
        self.write(d, "prova.css", """/* --title: #000000; nel commento non conta */
            :root { --base: neutral; --title: #123456; --fg: rossiccio; --h1-style: enorme;
                    --strip: top; --pre-bar-width: 99pt; --font: "Bad</style>", Noto Serif;
                    --name: "Prova"; }""")
        neutral = self.load_from(os.path.join(RUSCAMARK, "themes"))["neutral"]
        th = self.load_from(d, os.path.join(RUSCAMARK, "themes"))["prova"]
        self.assertEqual(th["title"], "#123456")
        self.assertEqual(th["fg"], neutral["fg"])              # colore non valido
        self.assertEqual(th["h1_style"], neutral["h1_style"])  # valore non previsto
        self.assertEqual(th["strip"], "top")
        self.assertEqual(th["pre_bar_width"], 12.0)
        self.assertEqual(th["font"], "Noto Serif")
        self.assertEqual(rm.theme_label("prova", th, lambda k, **kw: k), "Prova")

    def test_user_folder_wins_and_bases_do_not_loop(self):
        user, system = tempfile.mkdtemp(), tempfile.mkdtemp()
        self.write(system, "a.css", ":root { --title: #111111; }")
        self.write(user, "a.css", ":root { --base: b; --title: #222222; }")
        self.write(user, "b.css", ":root { --base: a; --fg: #333333; }")
        self.write(user, "c.css", ":root { --base: manca; }")
        self.write(user, "grande.css", ":root { --fg: #444444; }" + " " * rm._THEME_MAX_BYTES)
        self.write(user, "non tema.txt", ":root { --fg: #555555; }")
        themes = self.load_from(user, system)
        self.assertEqual(list(themes), ["ruscalinux", "a", "b", "c"])
        self.assertEqual(themes["a"]["title"], "#222222")
        self.assertEqual(themes["c"], rm.GUIDE)

    def test_html_follows_theme(self):
        themes = self.load_from(os.path.join(RUSCAMARK, "themes"))
        for tid, th in themes.items():
            with self.subTest(theme=tid):
                out = rm.markdown_to_html("# T\n\n```\nx\n```", "T</style>", theme=th)
                self.assertIn(th["pre_bg"], out)
                self.assertEqual(out.count("</style>"), 1)
                self.assertEqual('<div class="strip"></div>' in out, th["strip"] == "top")
                self.assertEqual("@bottom-right" in out, th["footer_align"] == "split")
        self.assertIn("linear-gradient(135deg", rm.markdown_to_html("# T", "T"))
        self.assertIn("border-left: none", rm.markdown_to_html("```\nx\n```", "T",
                                                               theme=themes["ruscalinux-strip"]))

    def test_preview_follows_theme(self):
        th = self.load_from(os.path.join(RUSCAMARK, "themes"))["sea"]
        self.assertEqual(rm.preview_colors(th)["heading"], th["title"])
        self.assertEqual(rm.preview_colors(), rm.PREVIEW_GUIDE)


if __name__ == "__main__":
    unittest.main()
