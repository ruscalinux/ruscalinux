"""RuscaLinux OS Tools — test del Markdown di RuscaTranslator — 1.99.2 — GPL-3.0

split_markdown divide il documento da tradurre in pezzi per il modello, solo
fra un blocco Markdown e l'altro (rusca_markdown.block_ranges). Si lanciano
dalla radice del repository:
    python3 -m unittest tests/test_ruscatranslator_markdown.py

ruscatranslator.py importa GTK 4 e libadwaita: senza, i test si saltano.
"""

import importlib.util
import os
import re
import sys
import unittest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TOOL = os.path.join(REPO, "tools", "ruscatranslator")

try:
    sys.path.insert(0, TOOL)
    _spec = importlib.util.spec_from_file_location(
        "ruscatranslator_under_test", os.path.join(TOOL, "ruscatranslator.py"))
    rt = importlib.util.module_from_spec(_spec)
    _spec.loader.exec_module(rt)
except (ImportError, ValueError):
    rt = None

TRICKY = ("# Guida\n\n- uno\n\n- due\n\n- tre\n\n~~~bash\nls\n\n# commento\n```\n\npwd\n~~~\n\n"
          "````md\n```js\nx\n\ny\n```\n````\n\n| a | b |\n|-|-|\n| 1 | 2 |\n\n"
          "Fine. [link][r]\n\n[r]: https://x.it\n")


@unittest.skipIf(rt is None, "GTK 4 o libadwaita non disponibili")
class SplitMarkdown(unittest.TestCase):
    def test_nothing_lost(self):
        chunks = rt.split_markdown(TRICKY, 60)
        self.assertEqual(re.sub(r"\s+", "", "".join(chunks)), re.sub(r"\s+", "", TRICKY))

    def test_blocks_stay_whole(self):
        chunks = rt.split_markdown(TRICKY, 60)
        self.assertEqual(len(chunks), 4)
        self.assertTrue(chunks[0].endswith("- tre"))                    # elenco intero
        self.assertTrue(chunks[1].startswith("~~~bash") and chunks[1].endswith("~~~"))
        self.assertIn("````md", chunks[2])                             # codice annidato intero
        self.assertIn("| 1 | 2 |", chunks[2])
        self.assertIn("[r]: https://x.it", chunks[3])                   # definizione con il link

    def test_one_chunk_when_it_fits(self):
        self.assertEqual(rt.split_markdown(TRICKY), [TRICKY.strip("\n")])


if __name__ == "__main__":
    unittest.main()
