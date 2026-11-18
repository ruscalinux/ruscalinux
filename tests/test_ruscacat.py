"""RuscaLinux OS Tools — test di RuscaCat — 1.99.3 — GPL-3.0

RuscaCat ascolta dal microfono (rusca_mic.py), trascrive con
rusca_whisper.py, risponde con rusca_engine.py e parla con rusca_tts.py: gli
ultimi tre sono copie dei moduli di RuscaTranscriber, RuscaLLama e
RuscaNarrator, che hanno i loro test. Qui si controllano le copie, il
rilevamento del parlato, l'inviluppo della bocca, la divisione in frasi di
una risposta che arriva a pezzi, le trascrizioni da scartare, il microfono
con un FFmpeg finto e le traduzioni. Non servono né i motori né un modello
né un microfono. Dalla radice del repository:
    python3 -m unittest tests/test_ruscacat.py
"""

import array
import hashlib
import json
import math
import os
import random
import re
import stat
import sys
import tempfile
import unittest
import wave

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TOOLS = os.path.join(REPO, "tools")
TOOL = os.path.join(TOOLS, "ruscacat")
sys.path.insert(0, TOOL)

try:
    from gi.repository import GLib
    import rusca_mic as mic
except (ImportError, ValueError):
    GLib = mic = None

# Moduli comuni: la copia di RuscaCat deve essere identica all'originale.
SHARED = {
    "rusca_engine.py": ("ruscallama", "ruscatranslator"),
    "rusca_whisper.py": ("ruscatranscriber",),
    "rusca_tts.py": ("ruscanarrator",),
    "rusca_markdown.py": ("ruscallama", "ruscanarrator"),
    "markdown_it_mark.py": ("ruscallama", "ruscanarrator"),
    "style.css": ("ruscallama", "ruscanarrator", "ruscatranscriber"),
}

RATE = 16000


def digest(path):
    with open(path, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


def tone(ms, amp=6000, freq=200):
    n = RATE * ms // 1000
    return array.array("h", [int(amp * math.sin(2 * math.pi * freq * i / RATE))
                             for i in range(n)]).tobytes()


def noise(ms, sigma=50, seed=1):
    rnd = random.Random(seed)
    return array.array("h", [int(rnd.gauss(0, sigma)) for _ in range(RATE * ms // 1000)]).tobytes()


def feed_all(detector, pcm):
    """Restituisce le frasi trovate, come durate in millisecondi."""
    out = []
    step = mic.FRAME_BYTES
    for i in range(0, len(pcm) - step + 1, step):
        _level, utt = detector.feed(pcm[i:i + step])
        if utt:
            out.append(len(utt) // 2 * 1000 // RATE)
    return out


class Copies(unittest.TestCase):
    def test_shared_modules_identical(self):
        for name, owners in SHARED.items():
            mine = digest(os.path.join(TOOL, name))
            for owner in owners:
                self.assertEqual(mine, digest(os.path.join(TOOLS, owner, name)),
                                 f"{name} di RuscaCat è diverso da quello di {owner}")

    def test_no_network_in_own_modules(self):
        # Specifiche, sezione 11: la rete (solo 127.0.0.1) passa da
        # rusca_engine.py; i moduli propri di RuscaCat non la usano.
        for name in ("ruscacat.py", "cat_view.py", "rusca_mic.py"):
            with open(os.path.join(TOOL, name), encoding="utf-8") as f:
                src = f.read()
            for bad in (r"^\s*import (socket|http|urllib|requests)", r"^\s*from (socket|http|urllib)",
                        r"Gio\.Socket", r"shell=True", r"os\.system"):
                self.assertIsNone(re.search(bad, src, re.M), f"{name}: {bad}")

    def test_version(self):
        with open(os.path.join(REPO, "release.conf"), encoding="utf-8") as f:
            version = re.search(r'^VERSION="?([^"\n]+)"?', f.read(), re.M).group(1)
        with open(os.path.join(TOOL, "ruscacat.py"), encoding="utf-8") as f:
            self.assertIn(f'APP_VERSION = "{version}"', f.read())
        with open(os.path.join(TOOL, "make-deb.sh"), encoding="utf-8") as f:
            self.assertIn(f'VER="{version}"', f.read())


class Translations(unittest.TestCase):
    def load(self, code):
        with open(os.path.join(TOOL, "lang", f"{code}.json"), encoding="utf-8") as f:
            return json.load(f)

    def test_same_keys_and_fields(self):
        en = self.load("en")
        fields = lambda v: sorted(re.findall(r"{(\w+)}", v))
        for name in os.listdir(os.path.join(TOOL, "lang")):
            data = self.load(name[:-5])
            self.assertEqual(set(data), set(en), name)
            for k in en:
                self.assertEqual(fields(data[k]), fields(en[k]), f"{name}: {k}")

    def test_persona(self):
        for code in ("it", "en"):
            persona = self.load(code)["persona"]
            self.assertIn("{name}", persona)
            self.assertIn("{language}", persona)
            self.assertIn("heidegger", persona.lower())

    def test_ai_note(self):
        self.assertEqual(self.load("it")["ai_note"], "Progettazione, specifiche e verifica "
                         "dell’autore; codice scritto con l’assistenza di strumenti di "
                         "intelligenza artificiale.")
        self.assertEqual(self.load("en")["ai_note"], "Design, specifications and testing by the "
                         "author; code written with the assistance of AI tools.")


@unittest.skipIf(mic is None, "serve PyGObject")
class Detector(unittest.TestCase):
    def test_silence(self):
        self.assertEqual(mic.frame_db(b"\0\0" * 480), -100.0)
        self.assertEqual(feed_all(mic.SpeechDetector(), noise(5000)), [])

    def test_one_sentence_with_margins(self):
        # 1 s di rumore, 1,5 s di voce, una pausa breve, 0,6 s di voce, 2 s
        # di rumore: una sola frase, con 300 ms prima e circa 200 ms dopo.
        pcm = noise(1000) + tone(1500) + noise(300, seed=2) + tone(600) + noise(2000, seed=3)
        found = feed_all(mic.SpeechDetector(5, 900), pcm)
        self.assertEqual(len(found), 1)
        self.assertGreater(found[0], 1500 + 300 + 600 + 250)
        self.assertLess(found[0], 1500 + 300 + 600 + 300 + 300)

    def test_two_sentences(self):
        pcm = noise(1000) + tone(800) + noise(1500, seed=2) + tone(800) + noise(1500, seed=3)
        self.assertEqual(len(feed_all(mic.SpeechDetector(5, 900), pcm)), 2)

    def test_short_pause_setting(self):
        pcm = noise(1000) + tone(800) + noise(700, seed=2) + tone(800) + noise(1500, seed=3)
        self.assertEqual(len(feed_all(mic.SpeechDetector(5, 900), pcm)), 1)
        self.assertEqual(len(feed_all(mic.SpeechDetector(5, 500), pcm)), 2)

    def test_click_is_not_speech(self):
        pcm = noise(1000) + tone(150, amp=9000) + noise(2000, seed=2)
        self.assertEqual(feed_all(mic.SpeechDetector(), pcm), [])

    def test_quiet_voice_and_sensitivity(self):
        pcm = noise(1000) + tone(1000, amp=500) + noise(2000, seed=2)
        self.assertEqual(feed_all(mic.SpeechDetector(1), pcm), [])
        self.assertEqual(len(feed_all(mic.SpeechDetector(10), pcm)), 1)

    def test_long_sentence_closes(self):
        found = feed_all(mic.SpeechDetector(5, 900, max_ms=3000), noise(500) + tone(7000))
        self.assertEqual(len(found), 2)
        self.assertTrue(all(ms <= 3000 for ms in found))

    def test_noisy_room(self):
        # Il rumore di fondo si misura: in una stanza rumorosa il rumore da
        # solo non è parlato, la voce sì.
        loud = lambda ms, seed=1: noise(ms, sigma=900, seed=seed)
        self.assertEqual(feed_all(mic.SpeechDetector(), loud(4000)), [])
        found = feed_all(mic.SpeechDetector(), loud(2000) + tone(1200, amp=12000) + loud(2000, 2))
        self.assertEqual(len(found), 1)

    def test_level(self):
        d = mic.SpeechDetector()
        for i in range(20):
            quiet, _ = d.feed(noise(30, seed=i))
        loud, _ = d.feed(tone(30, amp=12000))
        self.assertLess(quiet, 0.2)
        self.assertGreater(loud, 0.8)


@unittest.skipIf(mic is None, "serve PyGObject")
class Envelope(unittest.TestCase):
    def test_envelope(self):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "voce.wav")
            mic.write_wav(path, b"\0\0" * (RATE // 2) + tone(500, amp=10000) + b"\0\0" * (RATE // 2))
            env = mic.envelope(path)
            self.assertEqual(len(env), 75)
            self.assertEqual(mic.envelope_at(env, 100), 0.0)
            self.assertGreater(mic.envelope_at(env, 750), 0.9)
            self.assertEqual(mic.envelope_at(env, 5000), 0.0)
            self.assertEqual(mic.envelope(os.path.join(d, "manca.wav")), [])
            with wave.open(path, "rb") as w:
                self.assertEqual((w.getframerate(), w.getnchannels(), w.getsampwidth()), (RATE, 1, 2))


@unittest.skipIf(mic is None, "serve PyGObject")
class Sentences(unittest.TestCase):
    def run_stream(self, text, size=5, **kw):
        s = mic.SentenceSplitter(**kw)
        out = []
        for i in range(0, len(text), size):
            out += s.feed(text[i:i + size])
        return out, s.flush()

    def test_first_sentence_leaves_at_once(self):
        out, rest = self.run_stream("Mah. Ancora tu? Che cosa vuoi, l'Essere in una ciotola? "
                                    "Non ho tempo per il si impersonale.")
        self.assertEqual(out[0], "Mah.")
        self.assertEqual(out[1], "Ancora tu? Che cosa vuoi, l'Essere in una ciotola?")
        self.assertEqual(rest, "Non ho tempo per il si impersonale.")

    def test_numbers_are_not_sentence_ends(self):
        out, rest = self.run_stream("Dormo 3.5 ore al giorno, il resto è Cura.", size=1)
        self.assertEqual(out, [])
        self.assertEqual(rest, "Dormo 3.5 ore al giorno, il resto è Cura.")

    def test_long_first_sentence_breaks_at_a_comma(self):
        text = ("Quando l'umano apre il frigorifero alle tre di notte, cercando qualcosa che non "
                "sa nominare, sta vivendo l'angoscia")
        out, _rest = self.run_stream(text)
        self.assertTrue(out[0].endswith(","))
        self.assertLess(len(out[0]), 100)

    def test_no_punctuation(self):
        out, rest = self.run_stream("parola " * 80, max_chars=120)
        self.assertTrue(out)
        self.assertTrue(all(len(p) <= 120 for p in out))
        self.assertEqual(" ".join(out + [rest]).split(), ["parola"] * 80)

    def test_nothing_lost(self):
        text = ("Uno. Due, tre: quattro! Cinque? Sei… Sette «otto». Nove; dieci. " * 4).strip()
        out, rest = self.run_stream(text, size=3)
        self.assertEqual(" ".join(out + [rest]).split(), text.split())


@unittest.skipIf(mic is None, "serve PyGObject")
class Noise(unittest.TestCase):
    def test_noise(self):
        for text in ("", "  ", "[Musica]", "(applausi) ...", "♪", "Sottotitoli creati dalla "
                     "comunità Amara.org", "Thanks for watching!", "you"):
            self.assertTrue(mic.is_noise(text), text)
        for text in ("Ciao Martino", "Grazie", "Che cos'è il Dasein?", "Thank you"):
            self.assertFalse(mic.is_noise(text), text)


# FFmpeg finto: con "-f pulse" scrive 0,8 s di rumore, 1,2 s di voce e 1,5 s
# di rumore ed esce; scrive i propri argomenti in FAKE_ARGS.
FAKE_FFMPEG = r'''#!/usr/bin/env python3
import array, json, math, os, random, sys
with open(os.environ["FAKE_ARGS"], "w") as f:
    json.dump(sys.argv[1:], f)
R = 16000
rnd = random.Random(4)
noise = lambda ms: array.array("h", [int(rnd.gauss(0, 50)) for _ in range(R * ms // 1000)]).tobytes()
tone = lambda ms: array.array("h", [int(6000 * math.sin(2 * math.pi * 200 * i / R)) for i in range(R * ms // 1000)]).tobytes()
sys.stdout.buffer.write(noise(800) + tone(1200) + noise(1500))
sys.stdout.buffer.flush()
if "rotto" in os.environ.get("FAKE_MODE", ""):
    sys.stderr.write("Connection refused\n"); sys.exit(1)
'''


@unittest.skipIf(mic is None, "serve PyGObject")
class Microphone(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.fake = os.path.join(self.tmp.name, "ffmpeg")
        with open(self.fake, "w") as f:
            f.write(FAKE_FFMPEG)
        os.chmod(self.fake, os.stat(self.fake).st_mode | stat.S_IEXEC)
        os.environ["FAKE_ARGS"] = os.path.join(self.tmp.name, "args.json")
        self.saved = mic.FFMPEG_PATHS
        mic.FFMPEG_PATHS = (self.fake,)

    def tearDown(self):
        mic.FFMPEG_PATHS = self.saved
        os.environ.pop("FAKE_MODE", None)
        self.tmp.cleanup()

    def listen(self):
        loop = GLib.MainLoop()
        got = {"utterances": [], "levels": 0, "stopped": []}

        def stopped(error):
            got["stopped"].append(error)
            loop.quit()
        m = mic.Microphone(on_level=lambda _l: got.__setitem__("levels", got["levels"] + 1),
                           on_utterance=lambda pcm: got["utterances"].append(len(pcm)),
                           on_stopped=stopped)
        m.start(5, 900)
        GLib.timeout_add_seconds(20, loop.quit)
        loop.run()
        return got

    def test_utterance_and_command(self):
        got = self.listen()
        self.assertEqual(len(got["utterances"]), 1)
        self.assertGreater(got["levels"], 50)
        # Il flusso finito da solo è un errore: il microfono non si chiude
        # da sé.
        self.assertIsInstance(got["stopped"][0], mic.MicError)
        with open(os.environ["FAKE_ARGS"]) as f:
            args = json.load(f)
        self.assertEqual(args[args.index("-f") + 1], "pulse")
        self.assertIn("-protocol_whitelist", args)
        self.assertEqual(args[args.index("-protocol_whitelist") + 1], "file")
        self.assertEqual(args[args.index("-ar") + 1], "16000")
        self.assertEqual(args[-1], "-")

    def test_error_message(self):
        os.environ["FAKE_MODE"] = "rotto"
        got = self.listen()
        self.assertIn("Connection refused", got["stopped"][0].detail)

    def test_stop(self):
        loop = GLib.MainLoop()
        stopped = []

        def on_stopped(error):
            stopped.append(error)
            loop.quit()
        with open(self.fake, "a") as f:
            f.write("import time\ntime.sleep(30)\n")
        m = mic.Microphone(on_stopped=on_stopped)
        m.start()
        GLib.timeout_add(500, lambda: m.stop() and False)
        GLib.timeout_add_seconds(10, loop.quit)
        loop.run()
        self.assertEqual(stopped, [None])
        self.assertFalse(m.running)

    def test_no_ffmpeg(self):
        mic.FFMPEG_PATHS = (os.path.join(self.tmp.name, "manca"),)
        with self.assertRaises(mic.MicError) as cm:
            mic.Microphone().start()
        self.assertEqual(cm.exception.key, "err_no_ffmpeg")


try:
    import gi
    gi.require_version("Gtk", "4.0")
    gi.require_version("Adw", "1")
    import ruscacat
except (ImportError, ValueError):
    ruscacat = None


@unittest.skipIf(ruscacat is None, "servono GTK 4 e libadwaita")
class Program(unittest.TestCase):
    def test_work_dirs_are_private_to_ruscacat(self):
        root = ruscacat.WORK_ROOT
        self.assertTrue(root.endswith(os.path.join(".cache", "ruscacat")) or "ruscacat" in root)
        for d in (ruscacat.whisper.WORK_DIR, ruscacat.tts.WORK_DIR, ruscacat.MIC_DIR,
                  ruscacat.PLAY_DIR):
            self.assertTrue(d.startswith(root + os.sep), d)

    def test_speech_text(self):
        self.assertEqual(ruscacat.speech_text("*Sbadiglio.* L'**Essere** non è un `ente`."),
                         "Sbadiglio. L'Essere non è un ente.")
        self.assertEqual(ruscacat.speech_text(""), "")

    def test_conversation_markdown(self):
        md = ruscacat.conversation_markdown(
            [{"role": "user", "content": "Che cos'è *davvero* www.essere.it?"},
             {"role": "assistant", "content": "# Niente.\nSolo [Cura](x)."}], "Martino")
        self.assertTrue(md.startswith("# "))
        self.assertIn("\\*davvero\\*", md)
        self.assertIn("www\\.essere.it", md)
        self.assertIn("**Martino:** \\# Niente. Solo [Cura\\](x).", md)
        self.assertEqual(md.count("\n\n"), 2)          # titolo e due battute


if __name__ == "__main__":
    unittest.main()
