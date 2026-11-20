# -*- coding: utf-8 -*-
"""Test di RuscaLLisse senza motori veri: filtro dell'ascolto, frasi da dire,
lessico, visemi, entità, modelli Vosk, volto e turno di conversazione con un
modello e una voce finti. Senza PyGObject si saltano.

    python3 -m unittest tests/test_ruscallisse.py
"""
import ast
import os
import struct
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
            open(sys_l, "w", encoding="utf-8").write("# commento\nancora\tàncora\nbravo\t[[ brˈaːvo ]]\n")
            open(usr_l, "w", encoding="utf-8").write("ancora\tancóra\n")
            lex = self.st.load_lexicon(sys_l, usr_l)
            # l'utente vince; i fonemi [[ ]] solo con il Piper della prova
            self.assertEqual(self.st.apply_lexicon("Ancora, bravo!", lex), "ancóra, bravo!")
            self.assertEqual(self.st.apply_lexicon("Ancora, bravo!", lex, raw_phonemes=True),
                             "ancóra, [[ brˈaːvo ]]!")

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


@unittest.skipIf(cairo is None, "serve pycairo")
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

    def test_materializzazione(self):
        import face
        m = face.FaceModel()
        self.assertEqual(m.appear, 1.0)                 # senza richiesta è già comparsa
        m.start_appear()
        self.assertEqual(m.appear, 0.0)
        self.assertEqual(m.orbit_sweep, 0.0)
        for _ in range(int(face.APPEAR_TIME * 60) + 5):
            m.step(1 / 60)
        self.assertEqual(m.appear, 1.0)
        self.assertEqual(m.orbit_sweep, 1.0)
        r = face.FaceModel(reduce_motion=True)
        r.start_appear()
        self.assertEqual(r.appear, 1.0)                 # animazioni ridotte: compare subito

    @unittest.skipIf(cairo is None, "serve pycairo")
    def test_disegno_durante_la_comparsa(self):
        import face
        m = face.FaceModel()
        m.start_appear()
        for a in (0.0, .2, .5, .8, .99):
            m.appear = a
            surf = cairo.ImageSurface(cairo.FORMAT_ARGB32, 120, 120)
            face.draw(cairo.Context(surf), 120, 120, m)

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
        self.assertEqual(eng.body["max_tokens"], cv.MAX_TOKENS)
        self.assertEqual(spk.said[0], ("Certo, te lo spiego con calma.", "sorride"))
        self.assertEqual(spk.said[1], ("Prima una cosa, poi l'altra.", None))
        self.assertEqual(states, ["thinking", "speaking"])
        self.assertEqual(c.history[-1]["role"], "assistant")
        c.restart()
        self.assertEqual(c.history, [])

    def test_quit_aspetta_il_thread(self):
        """Il riconoscitore si libera solo a thread fermo (crash di Vosk)."""
        import conversation as cv
        busy = threading.Event()

        class Rec:
            def accept(self, d):
                busy.set(); time.sleep(0.3); return False
            def partial(self): return ""
            def result(self): return {}
            def reset(self): pass

        class Nothing:
            def cancel(self): pass
            def stop(self): pass
            def say(self, *a): pass
            def wait_idle(self, ev=None): return True

        c = cv.Conversation(Rec(), Nothing(), Nothing(), lambda: "", lambda: 10,
                            lambda s: False, lambda l: False, lambda k: False)
        c._start_mic = lambda: setattr(c, "_mic", type("M", (), {
            "poll": lambda self: None,
            "stdout": type("S", (), {"read": lambda self, n: b"\0" * n})(),
            "terminate": lambda self: None, "wait": lambda self, timeout=0: 0})())
        c.start()
        self.assertTrue(busy.wait(3))
        self.assertTrue(c.quit())
        self.assertFalse(c._thread.is_alive())


@unittest.skipUnless(HAVE_GI, "serve PyGObject")
class TestVoce(unittest.TestCase):
    """Speaker con un Piper finto e un pw-play finto che salva ciò che riceve."""

    def _speaker(self, d, fail=False):
        import rusca_piper as rp

        class Chunk:
            def __init__(self, n):
                self.audio_int16_bytes = b"\x10\x00" * n
                self.phonemes = list("tʃˈao")

        class Voice:
            class config:
                sample_rate = 16000
            @classmethod
            def load(cls, path):
                return cls()
            def synthesize(self, text, syn_config=None):
                if fail:
                    raise RuntimeError("voce rotta")
                yield Chunk(1600)

        class Cfg:
            def __init__(self, length_scale=1.0):
                self.length_scale = length_scale

        out = os.path.join(d, "audio.raw")
        fake = os.path.join(d, "pw-play")
        with open(fake, "w") as f:
            f.write("#!/bin/sh\n[ \"$1\" = --help ] && { echo '  -a | --raw   RAW mode'; exit 0; }\n"
                    "echo \"$@\" > '%s.args'\ncat > '%s'\n" % (out, out))
        os.chmod(fake, 0o755)
        self._old = (rp._import_piper, rp.PW_PLAY)
        rp._import_piper = lambda: (Voice, Cfg)
        rp.PW_PLAY = fake
        return rp.Speaker("x.onnx", 1.0), out

    def tearDown(self):
        import rusca_piper as rp
        if hasattr(self, "_old"):
            rp._import_piper, rp.PW_PLAY = self._old

    def test_silenzio_iniziale_e_frase(self):
        import rusca_piper as rp
        with tempfile.TemporaryDirectory() as d:
            spk, out = self._speaker(d)
            spk.say("Ciao.")
            self.assertTrue(spk.busy)
            deadline = time.monotonic() + 5
            while spk.busy and time.monotonic() < deadline:
                time.sleep(0.02)
            spk.close()
            time.sleep(0.2)
            data = open(out, "rb").read()
            pre = int(16000 * rp.PREROLL) * 2
            self.assertEqual(data[:pre], b"\0" * pre)          # silenzio iniziale
            self.assertIn(b"\x10\x00" * 1600, data)             # la frase
            args = open(out + ".args").read().split()
            self.assertEqual(args[0], "--raw")              # PipeWire recente: dati grezzi
            self.assertEqual(args[-1], "-")

    def test_raw_solo_se_esiste(self):
        import rusca_piper as rp
        with tempfile.TemporaryDirectory() as d:
            new, old = os.path.join(d, "nuovo"), os.path.join(d, "vecchio")
            open(new, "w").write("#!/bin/sh\necho '  -a | --raw  RAW mode'\n")
            open(old, "w").write("#!/bin/sh\necho '  --format=VALUE'\n")
            for f in (new, old):
                os.chmod(f, 0o755)
            self.assertEqual(rp.pw_raw_args(new), ["--raw"])
            self.assertEqual(rp.pw_raw_args(old), [])

    def test_errore_segnalato(self):
        with tempfile.TemporaryDirectory() as d:
            spk, _out = self._speaker(d, fail=True)
            errors = []
            spk.on_error = lambda key: errors.append(key)
            spk.say("Ciao.")
            ctx = GLib.MainContext.default()
            deadline = time.monotonic() + 3
            while not errors and time.monotonic() < deadline:
                ctx.iteration(False)
                time.sleep(0.01)
            spk.close()
            self.assertEqual(errors, ["err_voice"])


@unittest.skipUnless(HAVE_GI, "serve PyGObject")
class TestFineFrase(unittest.TestCase):
    """Con il rumore di fondo Vosk non chiude mai la frase: la chiude la pausa."""

    def test_pausa_chiude_la_frase(self):
        import conversation as cv
        asked = []

        class Rec:
            calls = 0
            def accept(self, d): return False          # Vosk non dichiara mai la fine
            def partial(self):
                Rec.calls += 1
                return "spiegami la seconda" if Rec.calls < 3 else "spiegami la seconda guerra mondiale"
            def final_result(self):
                return {"result": [{"word": w, "conf": 0.95} for w in
                                   "spiegami la seconda guerra mondiale".split()]}
            def result(self): return {}
            def reset(self): pass

        class Engine:
            def cancel(self): pass
            def chat_stream(self, body, stop, timeout=0):
                asked.append(body["messages"][-1]["content"])
                yield "Certo.", ""

        class Speaker:
            first_audio = None
            def say(self, *a): pass
            def wait_idle(self, ev=None): return True
            def stop(self): pass

        c = cv.Conversation(Rec(), Speaker(), Engine(), lambda: "", lambda: 10,
                            lambda s: False, lambda l: False, lambda k: False, pause=0.2)
        c._start_mic = lambda: setattr(c, "_mic", type("M", (), {
            "poll": lambda self: None,
            "stdout": type("S", (), {"read": lambda self, n: (time.sleep(0.02), b"\0" * n)[1]})(),
            "terminate": lambda self: None, "wait": lambda self, timeout=0: 0})())
        c._drain_mic = lambda: None
        c.start()
        deadline = time.monotonic() + 5
        while not asked and time.monotonic() < deadline:
            time.sleep(0.05)
        c.quit()
        self.assertEqual(asked[:1], ["spiegami la seconda guerra mondiale"])

    def test_finale_vuoto_usa_il_parziale(self):
        """Il modello italiano grande può dare un risultato finale vuoto."""
        import conversation as cv
        asked = []

        class Rec:
            def accept(self, d): return False
            def partial(self): return "spiegami la seconda guerra mondiale"
            def final_result(self): return {"text": ""}
            def result(self): return {}
            def reset(self): pass

        class Engine:
            def cancel(self): pass
            def chat_stream(self, body, stop, timeout=0):
                asked.append(body["messages"][-1]["content"])
                yield "Certo.", ""

        class Speaker:
            first_audio = None
            def say(self, *a): pass
            def wait_idle(self, ev=None): return True
            def stop(self): pass

        c = cv.Conversation(Rec(), Speaker(), Engine(), lambda: "", lambda: 10,
                            lambda s: False, lambda l: False, lambda k: False, pause=0.2)
        c._start_mic = lambda: setattr(c, "_mic", type("M", (), {
            "poll": lambda self: None,
            "stdout": type("S", (), {"read": lambda self, n: (time.sleep(0.02), b"\0" * n)[1]})(),
            "terminate": lambda self: None, "wait": lambda self, timeout=0: 0})())
        c._drain_mic = lambda: None
        c.start()
        deadline = time.monotonic() + 5
        while not asked and time.monotonic() < deadline:
            time.sleep(0.05)
        c.quit()
        self.assertEqual(asked[:1], ["spiegami la seconda guerra mondiale"])


@unittest.skipUnless(HAVE_GI, "serve PyGObject")
class TestTurniAlternati(unittest.TestCase):
    """Il chat template di Mistral rifiuta un assistente prima della prima
    domanda e due turni dello stesso ruolo (errore 500 di llama-server)."""

    def check(self, msgs):
        self.assertEqual(msgs[0]["role"], "system")
        roles = [m["role"] for m in msgs[1:]]
        self.assertEqual(roles[0], "user")
        for a, b in zip(roles, roles[1:]):
            self.assertNotEqual(a, b)

    def test_saluto_nel_sistema(self):
        import conversation as cv
        h = [{"role": "assistant", "content": "Ciao, sono Ellittica."},
             {"role": "user", "content": "spiegami la seconda guerra mondiale"}]
        msgs = cv.alternate("SISTEMA", h)
        self.check(msgs)
        self.assertIn("Ciao, sono Ellittica.", msgs[0]["content"])
        self.assertEqual(len(msgs), 2)

    def test_due_domande_di_fila(self):
        import conversation as cv
        h = [{"role": "user", "content": "uno"}, {"role": "assistant", "content": "a"},
             {"role": "user", "content": "due"}, {"role": "user", "content": "tre"}]
        msgs = cv.alternate("S", h)
        self.check(msgs)
        self.assertEqual(msgs[-1]["content"], "due\ntre")

    def test_turno_dopo_il_saluto(self):
        import conversation as cv

        class Engine:
            def __init__(self): self.body = None
            def cancel(self): pass
            def chat_stream(self, body, stop, timeout=0):
                self.body = body
                yield "Certo.", ""

        class Speaker:
            first_audio = None
            def say(self, *a): pass
            def wait_idle(self, ev=None): return True
            def stop(self): pass

        eng = Engine()
        c = cv.Conversation(None, Speaker(), eng, lambda: "S", lambda: 10,
                            lambda s: False, lambda l: False, lambda k: False)
        c._set_state = lambda st: None
        c.history.append({"role": "assistant", "content": "Ciao, sono Ellittica."})
        c._turn("come stai", 1.0, time.monotonic())
        self.check(eng.body["messages"])


FAKE_STREAM = r"""#!/usr/bin/env python3
import struct, sys
out = sys.stdout.buffer
args = sys.argv[1:]
if "--voice" not in args or args[args.index("--voice") + 1].endswith("rotta.onnx"):
    sys.stderr.write("non riesco ad aprire la voce\n"); sys.exit(1)
if args[args.index("--voice") + 1].endswith("chiacchierona.onnx"):
    # come l'ONNX Runtime di Debian: centinaia di righe prima di essere pronto
    for i in range(3000):
        sys.stderr.write(f"Schema error: Trying to register schema with name Op{i} (domain:  version: 1), but it is already registered\n\n")
    sys.stderr.flush()
out.write(b"RPS1" + struct.pack("<I", 1)); out.flush()
for line in sys.stdin.buffer:
    cid, scale, text = line.decode().rstrip("\n").split("\t", 2)
    cid = int(cid)
    if text == "ERRORE":
        out.write(struct.pack("<4s6I", b"RPSC", cid, 3, 0, 0, 0, 0)); out.flush(); continue
    n = 1600
    pcm = struct.pack(f"<{n}h", *([4000] * n))
    ph = [ord("a"), ord("a"), 0, ord("m"), ord("m"), 0, ord("o"), ord("o")]
    al = [400, 0, 400, 0, 800, 0]
    out.write(struct.pack("<4s6I", b"RPSC", cid, 1, 16000, n, len(ph), len(al)))
    out.write(pcm + struct.pack(f"<{len(ph)}I", *ph) + struct.pack(f"<{len(al)}i", *al))
    out.flush()
"""


@unittest.skipUnless(HAVE_GI, "serve PyGObject")
class TestRuscapiperStream(unittest.TestCase):
    """La voce con ruscapiper-stream (qui finto, stesso protocollo)."""

    def setUp(self):
        import rusca_piper as rp
        self.rp = rp
        self.d = tempfile.mkdtemp()
        self.stream = os.path.join(self.d, "ruscapiper-stream")
        open(self.stream, "w").write(FAKE_STREAM.replace("/usr/bin/env python3", sys.executable))
        os.chmod(self.stream, 0o755)
        self.out = os.path.join(self.d, "audio.raw")
        play = os.path.join(self.d, "pw-play")
        open(play, "w").write("#!/bin/sh\n[ \"$1\" = --help ] && exit 0\ncat > '%s'\n" % self.out)
        os.chmod(play, 0o755)
        self.old = (rp.STREAM, rp.PW_PLAY)
        rp.STREAM, rp.PW_PLAY = self.stream, play
        self.voice = os.path.join(self.d, "voce.onnx")
        open(self.voice, "wb").close()
        open(self.voice + ".json", "w").write('{"audio": {"sample_rate": 16000}}')

    def tearDown(self):
        self.rp.STREAM, self.rp.PW_PLAY = self.old
        import shutil
        shutil.rmtree(self.d, ignore_errors=True)

    def test_segmenti(self):
        seg = self.rp.segments([ord("a"), ord("a"), 0, ord("m"), 0, ord("o")], [10, 5, 7, 20])
        self.assertEqual(seg, [("A", 15), ("M", 7), ("O", 20)])
        self.assertEqual(self.rp.segments([ord("a"), ord("a")], [1]), [])   # lunghezze sbagliate

    def test_frase_detta_con_i_visemi_veri(self):
        self.assertEqual(self.rp.backend(), "ruscapiper-engine")
        spk = self.rp.Speaker(self.voice, 1.0)
        self.assertEqual(spk.rate, 16000)
        spk.say("Ciao.")
        deadline = time.monotonic() + 5
        while spk.busy and time.monotonic() < deadline:
            time.sleep(0.02)
        vis = [v for _t, _a, v in spk.timeline]
        spk.close()
        time.sleep(0.2)
        data = open(self.out, "rb").read()
        self.assertIn(struct.pack("<h", 4000) * 1600, data)
        # 1600 campioni a 16 kHz = 5 blocchi da 20 ms: A A? M O O secondo le durate
        self.assertEqual(vis[:5], ["A", "M", "O", "O", "O"])

    def test_stderr_pieno_non_blocca(self):
        """L'ONNX Runtime di Debian scrive oltre 64 KB su stderr prima che la
        voce sia pronta: RuscaLLisse deve leggerlo, o resta ad aspettare."""
        voce = os.path.join(self.d, "chiacchierona.onnx")
        open(voce, "wb").close()
        esito = []
        t = threading.Thread(target=lambda: esito.append(self.rp.Speaker(voce, 1.0)), daemon=True)
        t.start()
        t.join(10)
        self.assertTrue(esito, "Speaker bloccato: stderr di ruscapiper-stream non letto")
        esito[0].close()

    def test_errore_e_voce_rotta(self):
        spk = self.rp.Speaker(self.voice, 1.0)
        errors = []
        spk.on_error = errors.append
        spk.say("ERRORE")
        spk.say("Ciao.")                 # dopo un errore il flusso resta allineato
        ctx = GLib.MainContext.default()
        deadline = time.monotonic() + 5
        while (spk.busy or not errors) and time.monotonic() < deadline:
            ctx.iteration(False)
            time.sleep(0.01)
        self.assertEqual(errors, ["err_voice"])
        self.assertTrue(any(v for _t, _a, v in spk.timeline))
        spk.close()
        with self.assertRaises(RuntimeError):
            self.rp.Speaker(os.path.join(self.d, "rotta.onnx"), 1.0)


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
