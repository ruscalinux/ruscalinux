"""RuscaLinux OS Tools — test di RuscaDubbing — 1.99.3 — GPL-3.0

rusca_whisper.py avvia ffmpeg e whisper-cli (ruscawhisper-engine) e scrive
la trascrizione in Markdown e in SRT. Qui si controllano i formati di
uscita, la lettura di ciò che scrive whisper-cli e l'intero percorso di una
trascrizione, con due programmi finti al posto di ffmpeg e di whisper-cli:
i test non hanno bisogno né del motore né di un modello. Si lanciano dalla
radice del repository:
    python3 -m unittest tests/test_ruscadubbing.py

rusca_whisper.py usa GLib (PyGObject): senza, i test si saltano. Il test
del Markdown usa il motore comune rusca_markdown.py: senza markdown-it si
salta solo quello.
"""

import json
import os
import stat
import sys
import tempfile
import textwrap
import unittest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TOOL = os.path.join(REPO, "tools", "ruscadubbing")
sys.path.insert(0, TOOL)

try:
    from gi.repository import GLib
    import rusca_whisper as rw
except (ImportError, ValueError):
    rw = None

try:
    sys.path.insert(0, os.path.join(REPO, "tools", "ruscamark"))
    import rusca_markdown as md
except ImportError:
    md = None

S = rw.Segment if rw else None

# Quello che whisper-cli scrive davvero (whisper.cpp 1.9.5, examples/cli).
STDOUT = ("\n"
          "[00:00:00.000 --> 00:00:03.500]   Buongiorno a tutti.\n"
          "[00:00:03.500 --> 00:00:07.250]   Oggi parliamo di \"RuscaLinux\".\n")
STDERR = ("whisper_init_from_file_with_params_no_state: loading model\n"
          "main: processing 'audio.wav' (176000 samples, 11.0 sec), 2 threads\n"
          "whisper_full_with_state: auto-detected language: it (p = 0.970000)\n"
          "whisper_print_progress_callback: progress =  45%\n"
          "whisper_print_progress_callback: progress = 272%\n")
JSON = textwrap.dedent('''\
    {
    \t"result": {
    \t\t"language": "it"
    \t},
    \t"transcription": [
    \t\t{
    \t\t\t"timestamps": {"from": "00:00:00,000", "to": "00:00:03,500"},
    \t\t\t"offsets": {"from": 0, "to": 3500},
    \t\t\t"text": " Buongiorno a tutti."
    \t\t},
    \t\t{
    \t\t\t"timestamps": {"from": "00:00:03,500", "to": "00:00:07,250"},
    \t\t\t"offsets": {"from": 3500, "to": 7250},
    \t\t\t"text": " Oggi parliamo di \\"RuscaLinux\\".\tFine"
    \t\t},
    \t\t{
    \t\t\t"timestamps": {"from": "00:00:07,250", "to": "00:00:07,250"},
    \t\t\t"offsets": {"from": 7250, "to": 7250},
    \t\t\t"text": "  "
    \t\t}
    \t]
    }
    ''')

FAKE_FFMPEG = '''#!/usr/bin/env python3
import sys
args = sys.argv[1:]
src, dst = args[args.index("-i") + 1], args[-1]
assert args[args.index("-protocol_whitelist") + 1] == "file", args
if "senza-audio" in src:
    sys.stderr.write("Stream map '0:a:0' matches no streams.\\n")
    sys.exit(1)
open(dst, "wb").write(b"RIFF" + b"\\0" * 100)
'''

FAKE_WHISPER = '''#!/usr/bin/env python3
import json, os, sys, time
args = sys.argv[1:]
opt = lambda name: args[args.index(name) + 1]
model, wav, prefix = opt("-m"), opt("-f"), opt("-of")
assert os.path.isfile(wav) and "-oj" in args and "-pp" in args, args
json.dump(args, open(os.environ["FAKE_ARGS"], "w"))
if "rotto" in model:
    sys.stderr.write("whisper_init: failed to load model\\n")
    sys.exit(3)
sys.stderr.write(%(stderr)r)
sys.stderr.flush()
if "lento" in model:
    time.sleep(60)
sys.stdout.write(%(stdout)r)
sys.stdout.flush()
open(prefix + ".json", "w", encoding="utf-8").write(%(json)r)
''' % {"stderr": STDERR, "stdout": STDOUT, "json": JSON}


@unittest.skipIf(rw is None, "PyGObject (GLib) non disponibile")
class Formats(unittest.TestCase):
    def test_srt_time(self):
        self.assertEqual(rw.srt_time(0), "00:00:00,000")
        self.assertEqual(rw.srt_time(3723004), "01:02:03,004")
        self.assertEqual(rw.srt_time(-5), "00:00:00,000")
        self.assertEqual(rw.srt_time(100 * 3600000), "100:00:00,000")

    def test_srt(self):
        srt = rw.to_srt([S(0, 3500, " Buongiorno  a tutti. "), S(3500, 3500, "Ciao"),
                         S(4000, 5000, "   ")])
        self.assertEqual(srt, "1\n00:00:00,000 --> 00:00:03,500\nBuongiorno a tutti.\n\n"
                              "2\n00:00:03,500 --> 00:00:03,501\nCiao\n")
        self.assertEqual(rw.to_srt([]), "")

    def test_paragraphs(self):
        segs = [S(0, 1000, "Uno."), S(1000, 2000, "Due."), S(4500, 5000, "Tre.")]
        self.assertEqual(rw.paragraphs(segs), ["Uno. Due.", "Tre."])
        self.assertEqual(rw.plain_text(segs), "Uno. Due.\n\nTre.")
        # Un paragrafo lungo si chiude solo dove finisce una frase.
        long = [S(i * 1000, i * 1000 + 1000, "parola " * 20 + ("fine." if i % 3 == 2 else "e"))
                for i in range(12)]
        paras = rw.paragraphs(long)
        self.assertGreater(len(paras), 1)
        self.assertTrue(all(p.endswith("fine.") for p in paras[:-1]))
        self.assertEqual(" ".join(paras).split(), " ".join(s.text for s in long).split())

    def test_markdown(self):
        text = rw.to_markdown([S(0, 1000, "Uno."), S(5000, 6000, "Due.")], "lezione 1")
        self.assertEqual(text, "# lezione 1\n\nUno.\n\nDue.\n")
        self.assertEqual(rw.to_markdown([S(0, 1000, "Uno.")]), "Uno.\n")

    @unittest.skipIf(md is None, "markdown-it non disponibile")
    def test_markdown_is_plain_text(self):
        """Il parlato non diventa mai formattazione: il motore comune deve
        restituire, per ogni paragrafo, esattamente il testo trascritto."""
        spoken = [
            "# non è un titolo", "- non è un elenco", "+ nemmeno questo", "---",
            "1. non è un elenco numerato", "2) nemmeno", "> non è una citazione",
            "*asterischi* e _trattini_ e `codice` e **forte**", "~~barrato~~ ed ==evidenziato==",
            "[parentesi](quadre) e [^1] e <b>tag</b> e <https://esempio.it>",
            "vai su www.ruscalinux.org o https://www.ruscalinux.org/ oppure HTTP://X.IT",
            "scrivi a info@ruscalinux.org", "costa $5 e $x$ e $$y$$ e \\(z\\) e \\[w\\]",
            "R&D, &copy; e &#35; e una \\ barra", "2026. Un anno", "a | b", "=====", "-5 gradi",
            "#hashtag e C# e 3 > 2 < 4", "[BLANK_AUDIO]", "(musica) *applausi*",
            "[Musica]: forte", "[uno][due] e [tre] [quattro]",
        ]
        parser = md.parser()
        for text in spoken:
            source = rw.escape_markdown(text)
            tokens = parser.parse(source)
            self.assertEqual([t.type for t in tokens],
                             ["paragraph_open", "inline", "paragraph_close"], text)
            kinds = {c.type for c in tokens[1].children}
            self.assertLessEqual(kinds, {"text", "text_special", "entity"}, (text, kinds))
            self.assertEqual("".join(c.content for c in tokens[1].children), text)
        self.assertEqual(rw.escape_markdown("[Musica] e basta"), "[Musica] e basta")
        # Anche come titolo e in un documento intero.
        doc = rw.to_markdown([S(i * 5000, i * 5000 + 1000, t) for i, t in enumerate(spoken)],
                             "*titolo* #1")
        tokens = parser.parse(doc)
        self.assertEqual(tokens[0].tag, "h1")
        self.assertEqual("".join(c.content for c in tokens[1].children), "*titolo* #1")
        self.assertEqual(sum(t.type == "paragraph_open" for t in tokens), len(spoken))


@unittest.skipIf(rw is None, "PyGObject (GLib) non disponibile")
class Parsing(unittest.TestCase):
    def test_line(self):
        self.assertEqual(rw.parse_line("[00:00:07.960 --> 00:00:10.760]   ask not."),
                         S(7960, 10760, "ask not."))
        self.assertEqual(rw.parse_line("[01:02:03.004 --> 01:02:04.000]  ").text, "")
        self.assertIsNone(rw.parse_line("main: processing"))
        self.assertIsNone(rw.parse_line(""))

    def test_progress_and_language(self):
        self.assertEqual(rw.parse_progress("whisper_print_progress_callback: progress =  45%"), 45)
        self.assertEqual(rw.parse_progress("progress = 272%"), 100)
        self.assertIsNone(rw.parse_progress("load time = 37 ms"))
        self.assertEqual(rw.parse_language(
            "whisper_full_with_state: auto-detected language: it (p = 0.97)"), "it")
        self.assertIsNone(rw.parse_language("lang = auto"))

    def test_json(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "t.json")
            with open(path, "w", encoding="utf-8") as f:
                f.write(JSON)
            language, segments = rw.load_json(path)
            self.assertEqual(language, "it")
            # Il carattere di tabulazione nel testo (JSON non rigoroso) si
            # legge; il segmento vuoto si scarta.
            self.assertEqual(segments, [S(0, 3500, "Buongiorno a tutti."),
                                        S(3500, 7250, 'Oggi parliamo di "RuscaLinux". Fine')])
            with open(path, "wb") as f:
                f.write(b'{"transcription": [{"offsets": {"from": 0, "to": 9}, '
                        b'"text": "caf\xc3"}]}')
            self.assertEqual(rw.load_json(path)[1], [S(0, 9, "caf�")])

    def test_models(self):
        with tempfile.TemporaryDirectory() as tmp:
            for name, size in (("ggml-tiny.bin", 10), ("ggml-large-v3-turbo.bin", 30),
                               ("ggml-silero-v6.2.0.bin", 99), ("leggimi.txt", 99),
                               ("ggml-base-encoder.mlmodelc.bin", 99), ("sub/ggml-small.bin", 20)):
                p = os.path.join(tmp, name)
                os.makedirs(os.path.dirname(p), exist_ok=True)
                with open(p, "wb") as f:
                    f.write(b"x" * size)
            found = [os.path.relpath(p, tmp) for p in rw.find_models((tmp, "/non/esiste"))]
            self.assertEqual(found, ["ggml-large-v3-turbo.bin", "sub/ggml-small.bin",
                                     "ggml-tiny.bin"])


@unittest.skipIf(rw is None, "PyGObject (GLib) non disponibile")
class Transcription(unittest.TestCase):
    """Tutto il percorso, con ffmpeg e whisper-cli finti."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        t = self.tmp.name
        for name, code in (("ffmpeg", FAKE_FFMPEG), ("whisper-cli", FAKE_WHISPER)):
            p = os.path.join(t, name)
            with open(p, "w", encoding="utf-8") as f:
                f.write(code)
            os.chmod(p, os.stat(p).st_mode | stat.S_IXUSR)
        self.saved = (rw.ENGINE_DIRS, rw.FFMPEG_PATHS, rw.WORK_DIR)
        rw.ENGINE_DIRS = (t,)
        rw.FFMPEG_PATHS = (os.path.join(t, "ffmpeg"),)
        rw.WORK_DIR = os.path.join(t, "lavoro")
        self.args = os.environ["FAKE_ARGS"] = os.path.join(t, "args.json")
        self.files = {}
        for name in ("video.mkv", "senza-audio.mkv", "ggml-base.bin", "ggml-rotto.bin",
                     "ggml-lento.bin"):
            self.files[name] = os.path.join(t, name)
            with open(self.files[name], "wb") as f:
                f.write(b"x")

    def tearDown(self):
        rw.ENGINE_DIRS, rw.FFMPEG_PATHS, rw.WORK_DIR = self.saved
        self.tmp.cleanup()

    def run_one(self, media, model, cancel_after=None, **options):
        loop = GLib.MainLoop()
        seen = {"stages": [], "segments": [], "log": [], "done": None}

        def done(error, language, segments):
            seen["done"] = (error, language, segments)
            loop.quit()
        t = rw.Transcriber(lambda stage, percent=0: seen["stages"].append((stage, percent)),
                           seen["segments"].append, seen["log"].append, done)
        t.start(self.files[media], self.files[model], **options)
        if cancel_after is not None:
            GLib.timeout_add(cancel_after, lambda: t.cancel() and False)
        GLib.timeout_add_seconds(30, loop.quit)
        loop.run()
        t.wait(5)
        self.assertIsNotNone(seen["done"], "la trascrizione non è finita")
        return seen

    def test_transcription(self):
        seen = self.run_one("video.mkv", "ggml-base.bin", language="auto", threads=3)
        error, language, segments = seen["done"]
        self.assertIsNone(error)
        self.assertEqual(language, "it")
        self.assertEqual([s.text for s in segments],
                         ["Buongiorno a tutti.", 'Oggi parliamo di "RuscaLinux". Fine'])
        self.assertEqual([s.text for s in seen["segments"]],
                         ["Buongiorno a tutti.", 'Oggi parliamo di "RuscaLinux".'])
        self.assertEqual(seen["stages"],
                         [("audio", 0), ("model", 0), ("speech", 0), ("speech", 45),
                          ("speech", 100)])
        with open(self.args, encoding="utf-8") as f:
            args = f.read()
        args = json.loads(args)
        self.assertEqual(args[args.index("-l") + 1], "auto")
        self.assertEqual(args[args.index("-t") + 1], "3")
        self.assertIn("-ng", args)                       # scheda grafica spenta
        # I file di lavoro (l'audio dell'utente) non restano sul disco.
        self.assertEqual(os.listdir(rw.WORK_DIR), [])
        self.assertEqual(stat.S_IMODE(os.stat(rw.WORK_DIR).st_mode), 0o700)

    def test_language_and_gpu(self):
        seen = self.run_one("video.mkv", "ggml-base.bin", language="de", gpu=True)
        self.assertEqual(seen["done"][1], "de")
        with open(self.args, encoding="utf-8") as f:
            args = json.load(f)
        self.assertEqual(args[args.index("-l") + 1], "de")
        self.assertNotIn("-ng", args)

    def test_no_audio(self):
        error = self.run_one("senza-audio.mkv", "ggml-base.bin")["done"][0]
        self.assertEqual(error.key, "err_audio")
        self.assertIn("matches no streams", error.detail)
        self.assertEqual(os.listdir(rw.WORK_DIR), [])

    def test_engine_error(self):
        error = self.run_one("video.mkv", "ggml-rotto.bin")["done"][0]
        self.assertEqual(error.key, "err_engine")
        self.assertIn("failed to load model", error.detail)

    def test_cancel(self):
        seen = self.run_one("video.mkv", "ggml-lento.bin", cancel_after=1500)
        self.assertEqual(seen["done"], ("cancelled", "", []))
        self.assertEqual(os.listdir(rw.WORK_DIR), [])

    def test_missing_pieces(self):
        t = rw.Transcriber()
        with self.assertRaises(rw.WhisperError) as e:
            t.start(self.files["video.mkv"], "/non/esiste.bin")
        self.assertEqual(e.exception.key, "err_no_model")
        with self.assertRaises(rw.WhisperError) as e:
            t.start("/non/esiste.mkv", self.files["ggml-base.bin"])
        self.assertEqual(e.exception.key, "open_error")
        rw.FFMPEG_PATHS = ("/non/esiste/ffmpeg",)
        with self.assertRaises(rw.WhisperError) as e:
            t.start(self.files["video.mkv"], self.files["ggml-base.bin"])
        self.assertEqual(e.exception.key, "err_no_ffmpeg")
        rw.ENGINE_DIRS = ("/non/esiste",)
        with self.assertRaises(rw.WhisperError) as e:
            t.start(self.files["video.mkv"], self.files["ggml-base.bin"])
        self.assertEqual(e.exception.key, "err_no_engine")


if __name__ == "__main__":
    unittest.main()
