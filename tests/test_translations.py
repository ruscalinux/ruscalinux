# RuscaLinux OS Apps — test delle traduzioni — GPL-3.0-or-later
# python3 -m unittest tests/test_translations.py   (dalla radice del repository)
#
# Specifiche, sezione 9: ogni tool con un'interfaccia è tradotto nelle 26
# lingue. Per ogni cartella apps/*/lang/ si controlla che ci siano tutte e
# sole le 26 lingue, che ogni file abbia le stesse chiavi di en.json, con gli
# stessi segnaposto e nessun testo vuoto, e che la nota IA in italiano e in
# inglese sia esattamente quella della sezione 12.

import glob
import json
import os
import re
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LANGS = ("en it zh_CN zh_TW es hi ar pt_BR pt_PT ru ja de fr ko id tr pl nl uk "
         "cs vi sv ro hu el fi").split()
AI_NOTE = {
    "it": "Progettazione, specifiche e verifica dell’autore; codice scritto con "
          "l’assistenza di strumenti di intelligenza artificiale.",
    "en": "Design, specifications and testing by the author; code written with "
          "the assistance of AI tools.",
}
PLACEHOLDER = re.compile(r"\{[a-z_0-9]*\}")


def _load(path):
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def _lang_dirs():
    return sorted(d for d in glob.glob(os.path.join(ROOT, "apps", "*", "lang"))
                  if os.path.isfile(os.path.join(d, "en.json")))


class TranslationsTest(unittest.TestCase):
    def test_there_are_apps(self):
        self.assertGreaterEqual(len(_lang_dirs()), 12)

    def test_26_languages_everywhere(self):
        for d in _lang_dirs():
            app = os.path.basename(os.path.dirname(d))
            files = {f[:-5] for f in os.listdir(d) if f.endswith(".json")}
            with self.subTest(app=app):
                self.assertEqual(sorted(files), sorted(LANGS))
                self.assertEqual(len(LANGS), 26)

    def test_same_keys_and_placeholders(self):
        for d in _lang_dirs():
            app = os.path.basename(os.path.dirname(d))
            en = _load(os.path.join(d, "en.json"))
            for code in LANGS:
                path = os.path.join(d, code + ".json")
                if not os.path.isfile(path):
                    continue   # lo dice test_26_languages_everywhere
                data = _load(path)
                with self.subTest(app=app, lang=code):
                    self.assertEqual(sorted(set(data) - set(en)), [], "chiavi in più")
                    self.assertEqual(sorted(set(en) - set(data)), [], "chiavi mancanti")
                    for key, value in en.items():
                        if not isinstance(value, str):
                            continue
                        text = data[key]
                        self.assertIsInstance(text, str, key)
                        self.assertEqual(sorted(PLACEHOLDER.findall(text)),
                                         sorted(PLACEHOLDER.findall(value)), key)
                        if value.strip():
                            self.assertTrue(text.strip(), f"{key} vuota")

    def test_ai_note(self):
        for d in _lang_dirs():
            app = os.path.basename(os.path.dirname(d))
            for code, note in AI_NOTE.items():
                data = _load(os.path.join(d, code + ".json"))
                if "ai_note" in data:
                    with self.subTest(app=app, lang=code):
                        self.assertEqual(data["ai_note"], note)


if __name__ == "__main__":
    unittest.main()
