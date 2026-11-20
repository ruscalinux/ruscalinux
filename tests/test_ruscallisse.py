# -*- coding: utf-8 -*-
"""Test di RuscaLLisse senza motori veri: filtro dell'ascolto, frasi da dire,
lessico, visemi, entità, modelli Vosk, volto e turno di conversazione con un
modello e una voce finti. Senza PyGObject si saltano.

    python3 -m unittest tests/test_ruscallisse.py
"""
import ast
import os
import sys
import tempfile
import threading
import time
import unittest

APP = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "apps", "ruscallisse")
sys.path.insert(0, APP)

try:
    import gi  # noqa: F401
    from gi.repository import GLib  # noqa: F401
    HAVE_GI = True
except ImportError:
    HAVE_GI = False
try:
    import cairo
except ImportError:
    cairo = None

NET = {"socket", "http", "urllib", "urllib3", "requests", "ssl"}


@unittest.skipUnless(HAVE_GI, "serve PyGObject")
class TestTesto(unittest.TestCase):
    def setUp(self):
        import speech_text
        self.st = speech_text

    def test_filtro_parole_incerte(self):
        r = {"result": [{"word": "come", "conf": 0.98}, {"word": "funziona", "conf": 0.9},
                        {"word": "fotone", "conf": 0.41}], "text": "come funziona fotone"}
        text, conf = self.st.listen_filter(r)
        self.assertEqual(text, "come funziona [fotone]")
        self.assertAlmostEqual(conf, (0.98 + 0.9 + 0.41) / 3)

    def test_filtro_rumori(self):
        self.assertEqual(self.st.listen_filter({"text": ""})[0], "")
        self.assertEqual(self.st.listen_filter({"result": [{"word": "ehm", "conf": 1}]})[0], "")

    def test_frasi_in_streaming(self):
        s = self.st.Sentences()
        out = []
        for piece in ["[sorride] Ciao, che bello ", "sentirti oggi, davvero. Ti spiego ",
                      "una cosa: prima la luce", ", poi il colore. Va bene?"]:
            out += s.feed(piece)
        out += s.flush()
        self.assertEqual(out[0], "[sorride] Ciao, che bello sentirti oggi,")
        self.assertIn("Va bene?", out[-1])
        self.assertEqual("".join(out).replace(" ", ""),
                         "[sorride]Ciao,chebellosentirtioggi,davvero.Tispiegounacosa:primalaluce,poiilcolore.Vabene?")

    def test_frasi_think(self):
        s = self.st.Sentences()
        out = s.feed("<think>ragiono a lungo.</think>Ecco. ") + s.feed("Fine.") + s.flush()
        self.assertEqual(out, ["Ecco.", "Fine."])

    def test_pulizia(self):
        self.assertEqual(self.st.clean("[commossa] Che **bella** domanda!"), ("Che bella domanda!", "commossa"))
        self.assertEqual(self.st.clean("Vedi [qui](https://x.org) 😀")[0], "Vedi qui")
        self.assertEqual(self.st.clean("```python")[0], "")

    def test_lessico(self):
        with tempfile.TemporaryDirectory() as d:
            sys_l, usr_l = os.path.join(d, "a.tsv"), os.path.join(d, "b.tsv")
            open(sys_l, "w", encoding="utf-8").write("# commento\nancora\taŋkˈoːra\nbravo\tbrˈaːvo\n")
            open(usr_l, "w", encoding="utf-8").write("ancora\tˈaŋkora\n")
            lex = self.st.load_lexicon(sys_l, usr_l)
            self.assertEqual(self.st.apply_lexicon("Ancora, bravo!", lex),
                             "[[ ˈaŋkora ]], [[ brˈaːvo ]]!")

    def test_visemi(self):
        ph = ['t', 'ʃ', 'ˈ', 'a', 'o', ',', ' ', 'm', 'i', 'f', 'u', 'ɛ']
        self.assertEqual(self.st.visemes(ph), ["C", "C", "A", "O", "", "", "M", "I", "F", "U", "E"])

    def test_regole(self):
        r = self.st.rules("it", 80)
        self.assertIn("80 parole", r)
        self.assertIn("trascrizione automatica", r)
        self.assertIn("[sorride]", r)
        self.assertNotIn("[sorride]", self.st.rules("it", 80, emotions=False))


@unittest.skipUnless(HAVE_GI, "serve PyGObject")
class TestEntita(unittest.TestCase):
    def test_file_predefinito(self):
        import entity
        e = entity.load(os.path.join(APP, "entities", "ellittica.md"))
        self.assertEqual(e["name"], "Ellittica")
        self.assertTrue(entity.quid_missing(e))
        self.assertAlmostEqual(e["speed"], 0.95)
        self.assertIn("Chiaro e semplice", e["speech"])
        p = entity.system_prompt(e, "it", 80)
        self.assertTrue(p.startswith("Sei Ellittica."))
        self.assertNotIn("decidi tu", p)

    def test_quid_per_primo(self):
        import entity
        e = entity.parse("# Nora\n\n## Carattere\nCuriosa.\n\n## Quid\nAma i treni.\n\n## Voce\nvoce: it_IT-x\nvelocità: 2\n")
        self.assertFalse(entity.quid_missing(e))
        self.assertEqual((e["voice_name"], e["speed"]), ("it_IT-x", 1.3))
        p = entity.system_prompt(e, "it", 50)
        self.assertLess(p.index("Ama i treni"), p.index("Curiosa"))


@unittest.skipUnless(HAVE_GI, "serve PyGObject")
class TestVosk(unittest.TestCase):
    def test_modelli(self):
        import rusca_vosk as rv
        with tempfile.TemporaryDirectory() as d:
            for name, big in (("vosk-model-small-it-0.22", 10), ("vosk-model-it-0.22", 1000)):
                os.makedirs(os.path.join(d, name, "am"))
                os.makedirs(os.path.join(d, name, "conf"))
                open(os.path.join(d, name, "am", "final.mdl"), "wb").write(b"x" * big)
            os.makedirs(os.path.join(d, "non-un-modello"))
            old = rv.MODEL_DIRS
            rv.MODEL_DIRS = (d,)
            try:
                found = [os.path.basename(p) for p in rv.find_models()]
            finally:
                rv.MODEL_DIRS = old
            self.assertEqual(found, ["vosk-model-it-0.22", "vosk-model-small-it-0.22"])
        self.assertEqual(rv.model_language("/x/vosk-model-small-it-0.22"), "it")
        self.assertEqual(rv.model_language("/x/vosk-model-en-us-0.22"), "en")


class TestVolto(unittest.TestCase):
    def test_stati_e_bocca(self):
        import face
        m = face.FaceModel()
        m.set_state("speaking")
        m.speech = (0.1, "A")
        for _ in range(60):
            m.step(1 / 60)
        self.assertGreater(m.mouth_h, .5)
        m.speech = (0.0, "M")
        for _ in range(60):
            m.step(1 / 60)
        self.assertLess(m.mouth_h, .1)
        m.set_emotion("commossa", 1)
        m.step(.1)
        self.assertEqual(m.emotion, "commossa")
        for _ in range(80):
            m.step(1 / 60)
        self.assertIsNone(m.emotion)

    def test_animazioni_ridotte(self):
        import face
        m = face.FaceModel(reduce_motion=True)
        m.set_state("thinking")
        for _ in range(120):
            m.step(1 / 60)
        self.assertEqual(m.orbit, 0.0)
        self.assertEqual(m.tilt, 0.0)

    @unittest.skipIf(cairo is None, "serve pycairo")
    def test_disegno_ogni_stato(self):
        import face
        for state in face.STATES:
            m = face.FaceModel()
            m.set_state(state)
            m.step(.05)
            surf = cairo.ImageSurface(cairo.FORMAT_ARGB32, 200, 200)
            face.draw(cairo.Context(surf), 200, 200, m)
            data = bytes(surf.get_data())
            self.assertTrue(any(data[3::4]), state)     # qualcosa è stato disegnato


@unittest.skipUnless(HAVE_GI, "serve PyGObject")
class TestTurno(unittest.TestCase):
    """Un turno intero con riconoscitore, modello e voce finti."""

    def test_turno(self):
        import conversation as cv

        class Rec:
            def accept(self, d): return True
            def result(self): return {}
            def reset(self): pass

        class Engine:
            def __init__(self): self.body = None
            def cancel(self): pass
            def chat_stream(self, body, stop, timeout=0):
                self.body = body
                for p in ["[sorride] Certo, te lo spiego ", "con calma. Prima ", "una cosa, poi l'altra."]:
                    yield p, ""

        class Speaker:
            def __init__(self): self.said, self.first_audio = [], None
            def say(self, t, e=None): self.said.append((t, e)); self.first_audio = time.monotonic()
            def wait_idle(self, ev=None): return True
            def stop(self): pass

        states, eng, spk = [], Engine(), Speaker()
        c = cv.Conversation(Rec(), spk, eng, lambda: "SISTEMA", lambda: 160,
                            states.append, lambda l: None, lambda k: None)
        c._set_state = lambda st: states.append(st) if not states or states[-1] != st else None
        c._turn("come [funziona] la luce", 0.7, time.monotonic())
        self.assertEqual(eng.body["messages"][0], {"role": "system", "content": "SISTEMA"})
        self.assertEqual(eng.body["messages"][-1]["content"], "come [funziona] la luce")
        self.assertEqual(eng.body["max_tokens"], 160)
        self.assertEqual(spk.said[0], ("Certo, te lo spiego con calma.", "sorride"))
        self.assertEqual(spk.said[1], ("Prima una cosa, poi l'altra.", None))
        self.assertEqual(states, ["thinking", "speaking"])
        self.assertEqual(c.history[-1]["role"], "assistant")
        c.restart()
        self.assertEqual(c.history, [])


class TestSicurezza(unittest.TestCase):
    def test_niente_moduli_di_rete(self):
        """Solo rusca_engine.py parla con 127.0.0.1 (specifiche, sezione 11)."""
        for name in os.listdir(APP):
            if not name.endswith(".py") or name == "rusca_engine.py":
                continue
            tree = ast.parse(open(os.path.join(APP, name), encoding="utf-8").read())
            for node in ast.walk(tree):
                mods = []
                if isinstance(node, ast.Import):
                    mods = [a.name for a in node.names]
                elif isinstance(node, ast.ImportFrom) and node.module:
                    mods = [node.module]
                for m in mods:
                    self.assertNotIn(m.split(".")[0], NET, f"{name}: {m}")

    def test_copie_identiche(self):
        for f in ("rusca_engine.py", "rusca_markdown.py", "markdown_it_mark.py", "style.css"):
            a = open(os.path.join(APP, f), "rb").read()
            b = open(os.path.join(APP, "..", "ruscallama", f), "rb").read()
            self.assertEqual(a, b, f)

    def test_niente_testo_salvato(self):
        """La conversazione non si scrive su disco: conversation.py non apre file."""
        tree = ast.parse(open(os.path.join(APP, "conversation.py"), encoding="utf-8").read())
        calls = [n.func.id for n in ast.walk(tree)
                 if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)]
        self.assertNotIn("open", calls)


if __name__ == "__main__":
    unittest.main()
