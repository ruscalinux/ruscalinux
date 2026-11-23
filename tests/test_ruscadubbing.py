"""RuscaLinux OS Apps — test di RuscaDubbing — 1.99.3 — GPL-3.0

rusca_dubbing.py porta un video dalla lingua originale a quella doppiata:
whisper-cli trascrive, llama-server traduce, llama-tts doppia, FFmpeg
missa e scrive il video. Qui si controllano le battute, il prompt e la
lettura delle traduzioni, e l'intera catena con tre programmi finti al posto
dei motori (non servono né i motori né i modelli). FFmpeg invece è quello
vero, e crea anche il video di prova: senza, quei test si saltano.
Dalla radice del repository:
    python3 -m unittest tests/test_ruscadubbing.py
"""

import ast
import json
import os
import re
import shutil
import stat
import subprocess
import sys
import tempfile
import unittest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
APP = os.path.join(REPO, "apps", "ruscadubbing")
sys.path.insert(0, APP)

try:
    from gi.repository import GLib
    import rusca_dubbing as rd
except (ImportError, ValueError):
    rd = None

FFMPEG = shutil.which("ffmpeg")

# whisper-cli finto: tre segmenti, i primi due sono una frase sola.
FAKE_WHISPER = r'''#!/usr/bin/env python3
import json, os, sys
args = sys.argv[1:]
opt = lambda name: args[args.index(name) + 1]
assert os.path.isfile(opt("-f"))
if os.environ.get("FAKE_WHISPER_LOG"):
    open(os.environ["FAKE_WHISPER_LOG"], "a").write("whisper\n")
segs = [(500, 1800, " Good morning"), (1900, 3000, " to everybody."),
        (3600, 5200, " Today we talk about RuscaLinux.")]
json.dump({"result": {"language": "en"}, "transcription": [
    {"offsets": {"from": a, "to": b}, "text": t} for a, b, t in segs]},
    open(opt("-of") + ".json", "w"))
'''

# llama-server finto: /health, e /v1/chat/completions che risponde
# `N|IT <testo>` per ogni riga `N|MAX|testo`; controlla la chiave.
FAKE_SERVER = r'''#!/usr/bin/env python3
import http.server, json, os, re, sys
args = sys.argv[1:]
opt = lambda name: args[args.index(name) + 1]
key = open(opt("--api-key-file")).read().strip()
with open(os.environ["FAKE_ARGS"], "a") as f:
    f.write(json.dumps(args) + "\n")
class H(http.server.BaseHTTPRequestHandler):
    def log_message(self, *a): pass
    def send(self, code, body):
        data = json.dumps(body).encode()
        self.send_response(code); self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data))); self.end_headers()
        self.wfile.write(data)
    def do_GET(self):
        self.send(200, {"status": "ok"})
    def do_POST(self):
        if self.headers.get("Authorization") != "Bearer " + key:
            return self.send(401, {"error": "key"})
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        content = body["messages"][-1]["content"]
        short = "too long to be spoken" in content
        user = content.split("Lines to translate:\n")[-1]
        out = []
        for line in user.splitlines():
            m = re.match(r"(\d+)\|(\d+)\|(.*)", line)
            if m:
                text = "IT " + m.group(3)
                if short:                       # versione breve: al massimo MAX
                    text = text[:int(m.group(2))].rstrip()
                out.append(f"{m.group(1)}|{text}")
        self.send(200, {"choices": [{"message": {"content": "\n".join(out)}}]})
http.server.HTTPServer(("127.0.0.1", int(opt("--port"))), H).serve_forever()
'''

# llama-tts finto: 24 kHz; 40 ms di tono per carattere fra due silenzi brevi.
FAKE_TTS = r'''#!/usr/bin/env python3
import json, math, os, struct, sys, wave
args = sys.argv[1:]
if args == ["--list-devices"]:
    print("Available devices:"); sys.exit(0)
opt = lambda name: args[args.index(name) + 1]
text, out = opt("-p"), opt("-o")
with open(os.environ["FAKE_TTS_ARGS"], "a") as f:
    f.write(json.dumps(args) + "\n")
rate = 24000
w = wave.open(out, "wb"); w.setnchannels(1); w.setsampwidth(2); w.setframerate(rate)
w.writeframes(b"\0\0" * (rate // 10))
n = rate * 40 * len(text) // 1000
w.writeframes(b"".join(struct.pack("<h", int(9000 * math.sin(2 * math.pi * 300 * i / rate)))
                       for i in range(n)))
w.writeframes(b"\0\0" * (rate // 10))
w.close()
'''


@unittest.skipIf(rd is None, "PyGObject (GLib) non disponibile")
class Cues(unittest.TestCase):
    def seg(self, a, b, t):
        return rd.whisper.Segment(a, b, t)

    def test_join(self):
        cues = rd.cues_from_segments([self.seg(0, 1000, " Ciao"), self.seg(1200, 2000, "a tutti."),
                                      self.seg(2100, 3000, "Oggi"), self.seg(5000, 6000, "piove.")])
        self.assertEqual(cues, [rd.Cue(0, 2000, "Ciao a tutti."), rd.Cue(2100, 3000, "Oggi"),
                                rd.Cue(5000, 6000, "piove.")])

    def test_srt(self):
        cues = [rd.Cue(0, 1000, "Hello."), rd.Cue(1500, 2500, "Bye.")]
        self.assertEqual(rd.to_srt(cues, ["Ciao.", "Addio."]),
                         "1\n00:00:00,000 --> 00:00:01,000\nCiao.\n\n"
                         "2\n00:00:01,500 --> 00:00:02,500\nAddio.\n")
        both = rd.bilingual_srt(cues, ["Ciao.", "Addio."])
        self.assertIn("Hello.\nCiao.", both)
        again = rd.cues_from_srt(rd.to_srt(cues))
        self.assertEqual([c.text for c in again], ["Hello.", "Bye."])

    def test_budget(self):
        cues = [rd.Cue(0, 1000, "a"), rd.Cue(2000, 2600, "b")]
        self.assertEqual(rd.slot_ms(cues, 0), 2000)          # fino alla battuta dopo
        self.assertEqual(rd.slot_ms(cues, 1), 600)           # l'ultima: la sua durata
        self.assertGreater(rd.budget_chars(cues, 0, "it", 1.3), rd.budget_chars(cues, 1, "it", 1.3))
        self.assertGreater(rd.budget_chars(cues, 0, "it", 2.0), rd.budget_chars(cues, 0, "it", 1.0))

    def test_sentences(self):
        """Le battute si dividono alle fini di frase interne e si
        raggruppano in frasi intere."""
        C = rd.Cue
        cues = [C(0, 4000, "Il corso non deve"), C(4000, 8000, "essere lungo. Il tempo conta."),
                C(8000, 12000, "Ecco il secondo"), C(12000, 14000, "principio."),
                C(20000, 21000, "Grazie!")]
        parts = rd.cue_parts(cues)
        self.assertEqual([(p.cue, p.text) for p in parts],
                         [(0, "Il corso non deve"), (1, "essere lungo."), (1, "Il tempo conta."),
                          (2, "Ecco il secondo"), (3, "principio."), (4, "Grazie!")])
        self.assertEqual(parts[1].start, 4000)
        self.assertEqual(parts[2].end, 8000)
        self.assertLess(parts[1].end, parts[2].end)
        blocks = rd.group_blocks(parts)
        units = rd.block_cues(parts, blocks)
        self.assertTrue(all(u.text.endswith(rd.SENTENCE_END) for u in units))
        self.assertEqual([u.text for u in units],
                         ["Il corso non deve essere lungo. Il tempo conta.",
                          "Ecco il secondo principio.", "Grazie!"])
        # Una frase troppo lunga si chiude a una virgola, o al limite.
        long = [C(i * 5000, i * 5000 + 4900, f"parte {i},") for i in range(10)]
        for u in rd.block_cues(long, rd.group_blocks(long)):
            self.assertLessEqual(u.end - u.start, rd.BLOCK_MAX_MS)

    def test_split(self):
        split = rd.split_translation
        self.assertEqual(split("uno due tre", [1]), ["uno due tre"])
        self.assertEqual(split("uno", [1, 1, 1]), ["uno", "", ""])
        parts = split("Grazie a tutti voi. Cercherò di farvi piacere con cose nuove. Grazie!",
                      [30, 60])
        self.assertEqual(parts, ["Grazie a tutti voi.",
                                 "Cercherò di farvi piacere con cose nuove. Grazie!"])
        words = "a b c d e f g h i l".split()
        parts = split(" ".join(words), [1, 1, 1, 1, 1])
        self.assertEqual(len(parts), 5)
        self.assertTrue(all(parts))
        self.assertEqual(" ".join(parts).split(), words)

    def test_per_cue(self):
        C = rd.Cue
        cues = [C(0, 4000, "Il corso non deve"), C(4000, 8000, "essere lungo. Il tempo conta.")]
        parts = rd.cue_parts(cues)
        blocks = rd.group_blocks(parts)
        per = rd.translations_per_cue(cues, parts, blocks,
                                      ["The course must not be long. Time matters."])
        self.assertEqual(" ".join(per), "The course must not be long. Time matters.")
        self.assertTrue(all(per))

    def test_clean(self):
        clean = rd.clean_translation
        self.assertEqual(clean("Нам требуется найти", "Dobbiamo trovare..."), "Dobbiamo trovare")
        self.assertEqual(clean("Спасибо.", "Grazie…"), "Grazie.")
        self.assertEqual(clean("Ну...", "Beh..."), "Beh...")
        self.assertEqual(clean("и", "…e poi"), "e poi")

    def test_context(self):
        self.assertEqual(rd.parse_glossary("Polyglot = Poliglotta; RuscaLinux\nDmitry=Dmitrij"),
                         [("Polyglot", "Poliglotta"), ("RuscaLinux", "RuscaLinux"),
                          ("Dmitry", "Dmitrij")])
        self.assertEqual(rd.guess_gender(120), "male?")
        self.assertEqual(rd.guess_gender(210), "female?")
        self.assertEqual(rd.guess_gender(170), "")
        self.assertIn("masculine", rd.speaker_note("male", "it"))
        self.assertIn("feminine", rd.speaker_note("female?", "it"))
        self.assertEqual(rd.speaker_note("", "it"), "")
        notes = rd.make_notes("Topic: languages.", rd.speaker_note("male", "it"),
                              [("Polyglot", "Poliglotta")])
        prompt = rd.build_prompt("ru", "it", notes)
        self.assertIn("Topic: languages.", prompt)
        self.assertIn("Polyglot = Poliglotta", prompt)
        self.assertNotIn("Notes about", rd.build_prompt("ru", "it"))
        body = rd.brief_request([rd.Cue(0, 1, "a" * 20000)], "ru", "it")
        self.assertLess(len(body["messages"][0]["content"]), rd.BRIEF_CHARS + 2000)
        self.assertNotEqual(rd._memory_key("ru", "it", "", "male|"), rd._memory_key("ru", "it", ""))

    def test_speech_text(self):
        import rusca_speech as sp
        if sp.numbers_available():
            self.assertEqual(sp.spell_numbers("Dura 16 ore, il 50% nel 2023; 3,5 punti.", "it"),
                             "Dura sedici ore, il cinquanta per cento nel duemilaventitré; "
                             "tre virgola cinque punti.")
            self.assertEqual(sp.spell_numbers("Alle 10:30 del 12/03, A23, il 3° corso.", "it"),
                             "Alle 10:30 del 12/03, A23, il 3° corso.")
            self.assertEqual(sp.spell_numbers("1,500 people", "en"), "one thousand, five hundred people")
        self.assertEqual(sp.spell_numbers("16", "zh"), "16")
        lex = sp.load_lexicon(os.path.join(APP, "pronunce-it.tsv"))
        self.assertEqual(sp.apply_lexicon("Tienila, poi ascoltane un'altra.", lex),
                         "Tiènila, poi ascóltane un'altra.")
        orig = "Questi sono i principi del metodo, e ancora non basta."
        self.assertTrue(sp.needs_stress(orig, "it"))
        self.assertFalse(sp.needs_stress("Buongiorno a tutti.", "it"))
        self.assertFalse(sp.needs_stress(orig, "en"))
        good = "Questi sono i princìpi del metodo, e ancóra non basta."
        self.assertEqual(sp.apply_stress(orig, good, "it"), good)
        # Il modello cambia altro: quelle parole restano com'erano.
        self.assertEqual(sp.apply_stress(orig, "Queste sono i princìpi del metodò, e ancóra non basta.",
                                         "it"), good)
        self.assertEqual(sp.apply_stress(orig, "Una frase diversa.", "it"), orig)
        self.assertEqual(sp.speech_text("Il 16 sono i principi.", "it", {}, "Il 16 sono i princìpi."),
                         ("Il sedici sono i princìpi." if sp.numbers_available()
                          else "Il 16 sono i princìpi."))

    def test_wrap(self):
        wrap = rd.wrap_lines
        self.assertEqual(wrap("Breve."), "Breve.")
        text = "Per la mia lunga esperienza con persone e pubblici molto diversi,"
        top, bottom = wrap(text).split("\n")
        self.assertLessEqual(len(top), 42)
        self.assertLessEqual(len(bottom), 42)
        self.assertLessEqual(len(top), len(bottom))          # piramide
        self.assertFalse(top.split()[-1] in ("e", "la", "di", "con"))
        self.assertEqual(wrap("Sì, ho capito. Ma adesso dobbiamo andare via di qui."),
                         "Sì, ho capito.\nMa adesso dobbiamo andare via di qui.")

    def test_segment(self):
        C = rd.Cue
        units = [C(0, 20000, "x"), C(21000, 22000, "y")]
        texts = ["Per la mia lunga esperienza con persone e pubblici molto diversi, questo è "
                 "il formato compatto ottimale: permette, senza stancarsi troppo, di acquisire "
                 "una quantità davvero efficace di conoscenze.", "Grazie!"]
        subs, fast = rd.segment_subtitles(units, texts, "it")
        self.assertEqual(fast, 0)
        self.assertEqual(subs[-1].text, "Grazie!")
        self.assertEqual(" ".join(" ".join(s.text.split("\n")) for s in subs),
                         texts[0] + " " + texts[1])
        for s in subs:
            lines = s.text.split("\n")
            self.assertLessEqual(len(lines), 2)
            self.assertTrue(all(len(line) <= 42 for line in lines), s.text)
            self.assertGreaterEqual(s.end - s.start, rd.SUB_MIN_MS)
            self.assertLessEqual(s.end - s.start, rd.SUB_MAX_MS + 500)
        for a, b in zip(subs, subs[1:]):
            self.assertGreaterEqual(b.start - a.end, rd.SUB_GAP_MS - 1)
        # Un sottotitolo troppo veloce resta un po' dopo la voce, se c'è spazio.
        subs, fast = rd.segment_subtitles([C(0, 1000, "x")],
                                          ["Una frase decisamente troppo lunga per un secondo."], "it")
        self.assertGreater(subs[0].end, 1000)
        self.assertLessEqual(subs[0].end, 1000 + rd.SUB_MAX_EXTEND_MS)
        self.assertEqual(fast, 1)
        # Cinese: righe più corte.
        subs, _ = rd.segment_subtitles([C(0, 8000, "x")], ["早上好。" * 10], "zh")
        self.assertTrue(all(len(line) <= 16 for s in subs for line in s.text.split("\n")))

    def test_parse(self):
        got = rd.parse_translations("Ecco:\n1|Ciao.\n2| 40 |Addio.\n[3] Fine\n```\nniente\n4|\n")
        self.assertEqual(got, {1: "Ciao.", 2: "Addio.", 3: "Fine"})

    def test_translate(self):
        cues = [rd.Cue(i * 2000, i * 2000 + 1500, f"Line {i}.") for i in range(5)]
        calls = []

        def chat(body):
            user = body["messages"][-1]["content"]
            calls.append(user)
            lines = [line for line in user.split("Lines to translate:\n")[-1].splitlines() if line]
            out = []
            for line in lines:
                n, _max, text = line.split("|", 2)
                if text == "Line 3." and len(lines) > 1:
                    continue                        # nel gruppo il modello la salta
                if text == "Line 4.":
                    continue                        # questa non torna mai
                out.append(f"{n}|Riga {text[5]}.")
            return "\n".join(out)
        texts, stats = rd.translate_cues(chat, cues, "en", "it", batch=3)
        self.assertEqual(texts, ["Riga 0.", "Riga 1.", "Riga 2.", "Riga 3.", "Line 4."])
        self.assertEqual(stats, {"retried": 2, "shortened": 0, "kept": 1, "reused": 0})
        # Il secondo gruppo ha come contesto le battute già tradotte.
        self.assertIn("Line 2. => Riga 2.", calls[1])
        self.assertIn("4|", calls[1])
        self.assertTrue(rd.build_prompt("en", "it").count("Italian") >= 2)
        # Con la memoria: solo le frasi che mancano.
        calls.clear()
        texts, stats = rd.translate_cues(chat, cues, "en", "it", batch=3,
                                         known=["Riga 0.", "", "Riga 2.", "Riga 3.", "x"])
        self.assertEqual(texts[:4], ["Riga 0.", "Riga 1.", "Riga 2.", "Riga 3."])
        self.assertEqual(stats["reused"], 4)
        self.assertEqual(len(calls), 1)
        self.assertNotIn("3|", calls[0].split("Lines to translate:")[-1])
        # Primo gruppo più piccolo (voce in parallelo): 1 frase, poi 3 e 1.
        batches = []
        texts, stats = rd.translate_cues(chat, cues, "en", "it", batch=3, first=1,
                                         on_batch=lambda idx, r: batches.append(list(idx)))
        self.assertEqual(batches, [[0], [1, 2, 3], [4]])
        self.assertEqual(texts[:4], ["Riga 0.", "Riga 1.", "Riga 2.", "Riga 3."])

    def test_shorten(self):
        cues = [rd.Cue(0, 800, "Yes.")]

        def chat(body):
            user = body["messages"][-1]["content"]
            if "too long" in user:
                return "1|Sì."
            return "1|" + "Certamente, sono assolutamente d'accordo con te." * 2
        texts, stats = rd.translate_cues(chat, cues, "en", "it")
        self.assertEqual(texts, ["Sì."])
        self.assertEqual(stats["shortened"], 1)

    def test_stop(self):
        import threading
        ev = threading.Event()
        ev.set()
        with self.assertRaises(rd._Stopped):
            rd.translate_cues(lambda b: "", [rd.Cue(0, 1, "a")], "en", "it", ev)

    def test_paths(self):
        with tempfile.TemporaryDirectory() as t:
            media = os.path.join(t, "film.mp4")
            open(media, "w").close()
            p = rd.output_paths(media, "", "en", "it", "mkv")
            self.assertEqual(p["video"], os.path.join(t, "film.it.mkv"))
            open(p["video"], "w").close()
            self.assertEqual(rd.output_paths(media, "", "en", "it", "mkv")["video"],
                             os.path.join(t, "film.it (2).mkv"))

    def test_mux_command(self):
        cmd = rd.mux_command("/usr/bin/ffmpeg", "in.mp4", "mix.wav", "a.srt", "b.srt", "o.mkv",
                             "mkv", "en", "it", True, ("Original", "Italiano"))
        self.assertEqual(cmd[cmd.index("-protocol_whitelist") + 1], "file")
        self.assertIn("language=eng", cmd)
        self.assertIn("language=ita", cmd)
        self.assertEqual(cmd[cmd.index("-c:v") + 1], "copy")
        self.assertEqual(cmd[cmd.index("-disposition:a:1") + 1], "default")


@unittest.skipIf(rd is None, "PyGObject (GLib) non disponibile")
class Source(unittest.TestCase):
    def test_no_network(self):
        """Solo rusca_engine.py parla (con llama-server, su 127.0.0.1)."""
        net = {"socket", "urllib", "requests", "http", "ftplib", "smtplib", "ssl"}
        for name in ("rusca_dubbing.py", "ruscadubbing.py", "rusca_whisper.py", "rusca_tts.py",
                     "rusca_voicematch.py", "rusca_speech.py"):
            path = os.path.join(APP, name)
            if not os.path.isfile(path):
                continue
            tree = ast.parse(open(path, encoding="utf-8").read())
            for node in ast.walk(tree):
                mods = []
                if isinstance(node, ast.Import):
                    mods = [a.name for a in node.names]
                elif isinstance(node, ast.ImportFrom) and node.module:
                    mods = [node.module]
                for m in mods:
                    self.assertNotIn(m.split(".")[0], net, f"{name}: {m}")

    def test_shared_copies(self):
        """I moduli comuni sono copie identiche di quelli delle altre app."""
        for f, other in (("rusca_whisper.py", "ruscatranscriber"), ("rusca_tts.py", "ruscanarrator"),
                         ("rusca_engine.py", "ruscatranslator"),
                         ("rusca_markdown.py", "ruscanarrator"),
                         ("markdown_it_mark.py", "ruscanarrator"), ("style.css", "ruscanarrator")):
            a = open(os.path.join(APP, f), "rb").read()
            b = open(os.path.join(APP, "..", other, f), "rb").read()
            self.assertEqual(a, b, f)

    def test_work_dirs(self):
        self.assertTrue(rd.whisper.WORK_DIR.startswith(rd.WORK_DIR))
        self.assertTrue(rd.tts.WORK_DIR.startswith(rd.WORK_DIR))

    def test_lang_keys(self):
        """Le due lingue hanno le stesse chiavi, e ci sono tutte quelle usate."""
        it = json.load(open(os.path.join(APP, "lang", "it.json"), encoding="utf-8"))
        en = json.load(open(os.path.join(APP, "lang", "en.json"), encoding="utf-8"))
        self.assertEqual(set(it), set(en))
        used = set()
        for name in ("rusca_dubbing.py", "ruscadubbing.py", "rusca_whisper.py", "rusca_tts.py",
                     "rusca_engine.py", "rusca_voicematch.py"):
            src = open(os.path.join(APP, name), encoding="utf-8").read()
            if name.startswith("rusca_"):           # nei moduli comuni, solo gli errori
                pattern = (r'(?:DubbingError|WhisperError|TTSError|EngineError|MatchError)'
                           r'\("([a-z][a-z0-9_]+)"')
            else:
                pattern = r'\b_\("([a-z][a-z0-9_]+)"'
            used |= set(re.findall(pattern, src))
        used |= {"err_no_llm_engine", "err_mux", "app_summary", "desktop_keywords"}
        for stage in rd.STAGES:
            used |= {f"stage_{stage}", f"stage_{stage}_sub"}
        used |= {f"ducking_{d}" for d in rd.DUCKING} | {f"fmt_{f}" for f in rd.VIDEO_FORMATS}
        used |= {f"file_{k}" for k in ("video", "audio", "srt_tgt", "srt_src", "srt_both")}
        used |= {f"{k}_sub" for k in ("out_srt", "out_audio", "out_video")}
        used |= {f"theme_{t}" for t in ("system", "light", "dark")}
        used |= {f"diff_{k}" for k in ("higher", "lower", "brighter", "darker", "livelier",
                                       "flatter")}
        self.assertEqual(sorted(used - set(en)), [])


@unittest.skipIf(rd is None or FFMPEG is None, "PyGObject o FFmpeg non disponibili")
class Chain(unittest.TestCase):
    """Tutta la catena: video vero, motori finti, FFmpeg vero."""

    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        t = cls.tmp.name
        cls.video = os.path.join(t, "prova.mp4")
        subprocess.run([FFMPEG, "-nostdin", "-loglevel", "error", "-f", "lavfi", "-i",
                        "testsrc=size=160x120:rate=10:duration=6", "-f", "lavfi", "-i",
                        "sine=frequency=500:duration=6", "-c:v", "libx264", "-preset",
                        "ultrafast", "-pix_fmt", "yuv420p", "-c:a", "aac", "-shortest",
                        "-y", cls.video], check=True)
        cls.mute = os.path.join(t, "muto.mp4")
        subprocess.run([FFMPEG, "-nostdin", "-loglevel", "error", "-i", cls.video, "-an",
                        "-c:v", "copy", "-y", cls.mute], check=True)

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        t = self.dir.name
        bins = os.path.join(t, "bin")
        os.makedirs(bins)
        for name, code in (("whisper-cli", FAKE_WHISPER), ("llama-server", FAKE_SERVER),
                           ("llama-tts", FAKE_TTS)):
            p = os.path.join(bins, name)
            with open(p, "w", encoding="utf-8") as f:
                f.write(code)
            os.chmod(p, os.stat(p).st_mode | stat.S_IXUSR)
        self.saved = (rd.whisper.ENGINE_DIRS, rd.whisper.FFMPEG_PATHS, rd.engine.ENGINE_DIRS,
                      rd.tts.ENGINE_DIRS, rd.tts.FFMPEG_PATHS, rd.WORK_DIR, rd.whisper.WORK_DIR,
                      rd.tts.WORK_DIR)
        rd.whisper.ENGINE_DIRS = rd.engine.ENGINE_DIRS = rd.tts.ENGINE_DIRS = (bins,)
        rd.whisper.FFMPEG_PATHS = rd.tts.FFMPEG_PATHS = (FFMPEG,)
        rd.WORK_DIR = os.path.join(t, "lavoro")
        self.saved_project_dir = rd.PROJECT_DIR
        rd.PROJECT_DIR = os.path.join(t, "progetti")
        rd.whisper.WORK_DIR = os.path.join(rd.WORK_DIR, "whisper")
        rd.tts.WORK_DIR = os.path.join(rd.WORK_DIR, "voce")
        os.environ["FAKE_ARGS"] = os.path.join(t, "server.jsonl")
        os.environ["FAKE_TTS_ARGS"] = os.path.join(t, "tts.jsonl")
        os.environ["FAKE_WHISPER_LOG"] = os.path.join(t, "whisper.log")
        self.out = os.path.join(t, "uscita")
        os.makedirs(self.out)
        self.models = {}
        for name in ("whisper.bin", "llm.gguf", "voce.gguf", "mmproj-voce.gguf"):
            self.models[name] = os.path.join(t, name)
            open(self.models[name], "w").close()

    def tearDown(self):
        (rd.whisper.ENGINE_DIRS, rd.whisper.FFMPEG_PATHS, rd.engine.ENGINE_DIRS,
         rd.tts.ENGINE_DIRS, rd.tts.FFMPEG_PATHS, rd.WORK_DIR, rd.whisper.WORK_DIR,
         rd.tts.WORK_DIR) = self.saved
        rd.PROJECT_DIR = self.saved_project_dir
        self.dir.cleanup()

    def options(self, **kw):
        o = dict(media=self.video, folder=self.out, src="auto", tgt="it",
                 whisper_model=self.models["whisper.bin"], llm_model=self.models["llm.gguf"],
                 voice=rd.tts.Voice(self.models["voce.gguf"], self.models["mmproj-voce.gguf"]),
                 speaker_file="", voice_name="", gpu=False, whisper_device="", llm_device="", tts_device="", threads=2,
                 context=4096, max_speed=1.3, seed=42, ducking="medium",
                 outputs={"srt", "audio", "video"}, fmt="mkv", titles=("English", "Italiano"),
                 source_srt="")
        o.update(kw)
        return rd.Options(**o)

    def run_chain(self, options, cancel_after=None):
        loop = GLib.MainLoop()
        seen = {"stages": [], "done": None}

        def done(error, files, stats):
            seen["done"] = (error, files, stats)
            loop.quit()
        d = rd.Dubbing(lambda s, f=0.0, x="": (seen["stages"].append(s),
                                               seen.setdefault("details", []).append(x)),
                       lambda line: None, done)
        d.start(options)
        if cancel_after:
            GLib.timeout_add(cancel_after, lambda: d.cancel() and False)
        GLib.timeout_add_seconds(90, loop.quit)
        loop.run()
        self.assertIsNotNone(seen["done"], "il doppiaggio non è finito")
        d.engine.stop(wait=True)
        return seen

    def streams(self, path):
        r = subprocess.run([FFMPEG, "-hide_banner", "-i", path], capture_output=True, text=True)
        return [line.strip() for line in r.stderr.splitlines() if "Stream #" in line]

    def test_mkv(self):
        seen = self.run_chain(self.options())
        error, files, stats = seen["done"]
        self.assertIsNone(error, error)
        self.assertEqual(set(files), {"srt_src", "srt_tgt", "srt_both", "audio", "video"})
        self.assertEqual(stats["cues"], 2)                   # due segmenti uniti
        for stage in rd.STAGES:
            self.assertIn(stage, seen["stages"])
        tgt = open(files["srt_tgt"], encoding="utf-8").read()
        self.assertIn("IT Good morning to everybody.", tgt)
        self.assertTrue(files["srt_src"].endswith("prova.en.srt"))
        streams = self.streams(files["video"])
        kinds = [s.split(": ")[1] for s in streams]
        self.assertEqual(kinds, ["Video", "Audio", "Audio", "Subtitle", "Subtitle"], streams)
        self.assertIn("(eng)", streams[1])
        self.assertIn("(ita)", streams[2])
        self.assertIn("(default)", streams[2])
        self.assertNotIn("(default)", streams[1])
        self.assertIn("h264", streams[0])                    # immagine copiata
        # Volume finale della traccia doppiata vicino a −16 LUFS.
        r = subprocess.run([FFMPEG, "-hide_banner", "-nostdin", "-i", files["video"], "-map", "0:a:1",
                            "-af", "ebur128", "-f", "null", "-"], capture_output=True, text=True)
        lufs = float(re.findall(r"I:\s+(-?[\d.]+) LUFS", r.stderr)[-1])
        self.assertAlmostEqual(lufs, -16, delta=2.5)
        info = rd.probe(files["video"])
        self.assertGreaterEqual(info["duration_ms"], 5500)
        # Niente file di lavoro rimasti, niente server acceso.
        left = [os.path.join(r, f) for r, _d, fs in os.walk(rd.WORK_DIR) for f in fs]
        self.assertEqual(left, [])
        server = json.load(open(os.environ["FAKE_ARGS"]))
        self.assertIn("127.0.0.1", server)

    def count(self, name):
        path = os.environ[name]
        return len(open(path).read().splitlines()) if os.path.exists(path) else 0

    def test_saved_work(self):
        """Il secondo doppiaggio dello stesso video non rifà trascrizione e
        traduzione; «Rifai tutto» (reuse=False) sì."""
        self.assertIsNone(self.run_chain(self.options(outputs={"srt"}, voice=None))["done"][0])
        self.assertEqual((self.count("FAKE_WHISPER_LOG"), self.count("FAKE_ARGS")), (1, 1))
        self.assertEqual(rd.project_summary(self.video), (True, ["it"]))
        self.assertEqual(oct(os.stat(rd.project_path(self.video)).st_mode & 0o777), "0o600")
        seen = self.run_chain(self.options())
        error, files, stats = seen["done"]
        self.assertIsNone(error, error)
        self.assertEqual((self.count("FAKE_WHISPER_LOG"), self.count("FAKE_ARGS")), (1, 1))
        self.assertTrue(stats.get("reused_transcript"))
        self.assertTrue(stats.get("reused"))
        self.assertIn("IT Good morning", open(files["srt_tgt"], encoding="utf-8").read())
        self.run_chain(self.options(outputs={"srt"}, voice=None, reuse=False))
        self.assertEqual((self.count("FAKE_WHISPER_LOG"), self.count("FAKE_ARGS")), (2, 2))
        rd.forget_project(self.video)
        self.assertEqual(rd.project_summary(self.video), (False, []))

    def test_brief_and_gender(self):
        """La scheda del discorso si fa una volta e si salva; scegliere chi
        parla (o un glossario) rifà la traduzione."""
        self.assertIsNone(self.run_chain(self.options(outputs={"srt"}, voice=None))["done"][0])
        project = rd.load_project(self.video)
        self.assertEqual(len(project["briefs"]), 1)
        self.assertEqual(self.count("FAKE_ARGS"), 1)
        self.run_chain(self.options(outputs={"srt"}, voice=None))
        self.assertEqual(self.count("FAKE_ARGS"), 1)              # tutto dalla memoria
        self.run_chain(self.options(outputs={"srt"}, voice=None, gender="female",
                                    glossary="RuscaLinux"))
        self.assertEqual(self.count("FAKE_ARGS"), 2)
        briefs = rd.load_project(self.video)["briefs"]
        self.assertEqual(len(briefs), 2)
        self.assertTrue(any("feminine" in b and "RuscaLinux = RuscaLinux" in b
                            for b in briefs.values()))

    def test_refit(self):
        """Una frase che, detta, non sta nel suo tempo si fa accorciare e
        si ridice; l'altra si riusa."""
        srt = os.path.join(self.dir.name, "lunga.srt")
        with open(srt, "w", encoding="utf-8") as f:
            f.write("1\n00:00:00,000 --> 00:00:01,000\n"
                    "Hello there, this is a rather long sentence that cannot be said in one "
                    "second at all.\n\n2\n00:00:01,800 --> 00:00:03,000\nBye.\n")
        seen = self.run_chain(self.options(source_srt=srt, src="en", outputs={"srt", "video"}))
        error, files, stats = seen["done"]
        self.assertIsNone(error, error)
        self.assertEqual(stats.get("refit"), 1)
        self.assertEqual(self.count("FAKE_ARGS"), 2)           # tradurre, poi accorciare
        self.assertEqual(self.count("FAKE_TTS_ARGS"), 3)       # 2 frasi + 1 ridetta
        tgt = open(files["srt_tgt"], encoding="utf-8").read()
        self.assertNotIn("at all.", tgt)                        # la versione breve
        memory = rd.load_project(self.video)["memory"]
        self.assertTrue(any("at all" not in t for m in memory.values() for t in m.values()))
        self.assertEqual(sorted(os.listdir(os.path.join(self.dir.name, "uscita"))),
                         sorted(os.path.basename(p) for p in files.values()))

    def test_parallel(self):
        """Con due schede diverse la voce dice le frasi mentre il modello
        traduce le successive; il passaggio finale le riusa tutte."""
        srt = os.path.join(self.dir.name, "tante.srt")
        with open(srt, "w", encoding="utf-8") as f:
            for i in range(12):
                a, b = i * 3000, i * 3000 + 1500
                f.write(f"{i + 1}\n00:00:{a // 1000:02d},{a % 1000:03d} --> "
                        f"00:00:{b // 1000:02d},{b % 1000:03d}\nSentence number {i}.\n\n")
        video = os.path.join(self.dir.name, "lungo.mkv")
        subprocess.run([FFMPEG, "-nostdin", "-loglevel", "error", "-f", "lavfi", "-i",
                        "testsrc=size=64x48:rate=5:duration=38", "-f", "lavfi", "-i",
                        "sine=frequency=500:duration=38", "-c:v", "libx264", "-preset",
                        "ultrafast", "-c:a", "aac", "-shortest", "-y", video], check=True)
        seen = self.run_chain(self.options(media=video, source_srt=srt, src="en", gpu=True,
                                           llm_device="Scheda A", tts_device="Scheda B",
                                           outputs={"video"}))
        error, files, stats = seen["done"]
        self.assertIsNone(error, error)
        self.assertEqual(stats.get("parallel"), 12)
        calls = [json.loads(line) for line in open(os.environ["FAKE_TTS_ARGS"])]
        said = [c for c in calls if c != ["--list-devices"] and "-p" in c]
        self.assertEqual(len(said), 12)                # nessuna frase detta due volte
        # La riga del doppiaggio mostra la voce in parallelo già durante la
        # traduzione (prima che la traduzione sia finita).
        details = seen["details"]
        first_said = next(i for i, x in enumerate(details) if x.startswith("parallel:"))
        last_translate = max(i for i, s in enumerate(seen["stages"]) if s == "translate")
        self.assertLess(first_said, last_translate)
        self.assertIn("parallel:12/12", details)

    def test_burn(self):
        """Sottotitoli impressi: l'immagine si ricodifica in H.264 e cambia
        dove c'è un sottotitolo."""
        seen = self.run_chain(self.options(outputs={"video"}, burn=True))
        error, files, _stats = seen["done"]
        self.assertIsNone(error, error)
        streams = self.streams(files["video"])
        self.assertIn("h264", streams[0])
        frame = os.path.join(self.dir.name, "f.png")
        plain = os.path.join(self.dir.name, "g.png")
        for src, out in ((files["video"], frame), (self.video, plain)):
            subprocess.run([FFMPEG, "-nostdin", "-loglevel", "error", "-ss", "1.2", "-i", src,
                            "-frames:v", "1", "-y", out], check=True)
        self.assertNotEqual(open(frame, "rb").read(), open(plain, "rb").read())

    def test_too_long(self):
        P = rd.tts.Piece
        pieces = [P("a" * 50, 0, 0, 1000), P("b" * 10, 0, 2000, 3000), P("c", 0, 4000, 4100)]
        out = rd.too_long(pieces, [4000, 900, 9000], 1.3)
        self.assertEqual([i for i, _ in out], [0])               # l'ultima non conta
        self.assertLess(out[0][1], 50)
        self.assertGreater(out[0][1], 20)

    def test_preview(self):
        """La prova: solo il primo tratto, file «.prova», niente salvato
        della trascrizione parziale."""
        saved = rd.PREVIEW_MS
        rd.PREVIEW_MS = 3000
        try:
            seen = self.run_chain(self.options(preview=True))
        finally:
            rd.PREVIEW_MS = saved
        error, files, stats = seen["done"]
        self.assertIsNone(error, error)
        self.assertTrue(files["video"].endswith("prova.it.prova.mkv") or
                        files["video"].endswith(".prova.it.mkv"), files["video"])
        self.assertLess(rd.probe(files["video"])["duration_ms"], 4500)
        self.assertEqual(rd.project_summary(self.video)[0], False)

    def test_mp4_and_mute_video(self):
        seen = self.run_chain(self.options(media=self.mute, fmt="mp4", outputs={"video"},
                                           source_srt=self._srt(), src="en"))
        error, files, _stats = seen["done"]
        self.assertIsNone(error, error)
        self.assertEqual(set(files), {"video"})
        kinds = [s.split(": ")[1] for s in self.streams(files["video"])]
        self.assertEqual(kinds, ["Video", "Audio", "Subtitle", "Subtitle"])

    def test_subtitles_only(self):
        seen = self.run_chain(self.options(outputs={"srt"}, voice=None))
        error, files, _stats = seen["done"]
        self.assertIsNone(error, error)
        self.assertEqual(set(files), {"srt_src", "srt_tgt", "srt_both"})
        self.assertFalse(os.path.exists(os.environ["FAKE_TTS_ARGS"]))

    def test_cancel(self):
        seen = self.run_chain(self.options(), cancel_after=300)
        self.assertEqual(seen["done"][0], "cancelled")
        self.assertFalse(os.path.exists(os.path.join(self.out, "prova.it.mkv")))

    def test_missing_model(self):
        with self.assertRaises(rd.DubbingError) as cm:
            rd.Dubbing().start(self.options(llm_model=""))
        self.assertEqual(cm.exception.key, "err_no_llm_model")

    def _srt(self):
        p = os.path.join(self.dir.name, "orig.srt")
        with open(p, "w", encoding="utf-8") as f:
            f.write("1\n00:00:00,500 --> 00:00:02,000\nHello there.\n\n"
                    "2\n00:00:03,000 --> 00:00:05,000\nSee you.\n")
        return p


@unittest.skipIf(rd is None, "PyGObject (GLib) non disponibile")
class Siblings(unittest.TestCase):
    """Alla prima apertura si usano le scelte di RuscaNarrator & co."""

    def test_sibling_settings(self):
        try:
            import gi
            gi.require_version("Gtk", "4.0")
            gi.require_version("Adw", "1")
            import ruscadubbing as ui
        except (ImportError, ValueError):
            self.skipTest("GTK non disponibile")
        with tempfile.TemporaryDirectory() as t:
            for app, data in (("ruscanarrator", {"model": "/m/1.7B.gguf", "seed": 7,
                                                 "speaker_file": "/v/a.wav", "max_speed": 1}),
                              ("ruscatranslator", {"model": "/m/gemma.gguf",
                                                   "gpu_device": "AMD Radeon RX 7900"}),
                              ("ruscatranscriber", "non json")):
                os.makedirs(os.path.join(t, app))
                with open(os.path.join(t, app, "settings.json"), "w") as f:
                    f.write(json.dumps(data) if isinstance(data, dict) else data)
            got = ui.sibling_settings(t)
        self.assertEqual(got, {"voice_model": "/m/1.7B.gguf", "seed": 7, "speaker_file": "/v/a.wav",
                               "max_speed": 1.0, "llm_model": "/m/gemma.gguf",
                               "llm_device": "AMD Radeon RX 7900"})


# llama-tts finto per la ricerca di voci: un tono armonico la cui altezza
# dipende dal seme, così la voce «giusta» è nota.
FAKE_TTS_PITCH = r"""#!/usr/bin/env python3
import math, struct, sys, wave
args = sys.argv[1:]
if args == ["--list-devices"]:
    print("Available devices:"); sys.exit(0)
opt = lambda name: args[args.index(name) + 1]
seed, out = int(opt("-s")), opt("-o")
assert "--tts-speaker-file" not in args          # mai la voce originale
f0 = 90 + seed % 160
rate = 24000
w = wave.open(out, "wb"); w.setnchannels(1); w.setsampwidth(2); w.setframerate(rate)
frames = bytearray()
for i in range(rate * 5):
    t = i / rate
    v = 0.4 * math.sin(2 * math.pi * f0 * t) + 0.25 * math.sin(4 * math.pi * f0 * t) \
        + 0.15 * math.sin(6 * math.pi * f0 * t)
    frames += struct.pack("<h", int(12000 * v * (0.6 + 0.4 * math.sin(2 * math.pi * 3 * t))))
w.writeframes(bytes(frames)); w.close()
"""


@unittest.skipIf(rd is None or FFMPEG is None, "PyGObject o FFmpeg non disponibili")
class VoiceMatch(unittest.TestCase):
    """Misure della voce e ricerca di voci simili."""

    @classmethod
    def setUpClass(cls):
        import rusca_voicematch
        cls.vm = rusca_voicematch
        cls.tmp = tempfile.TemporaryDirectory()

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def tone(self, name, f0, seconds=8, extra=()):
        path = os.path.join(self.tmp.name, name)
        expr = (f"(0.4*sin(2*PI*{f0}*t)+0.25*sin(4*PI*{f0}*t)+0.15*sin(6*PI*{f0}*t))"
                f"*(0.6+0.4*sin(2*PI*3*t))")
        subprocess.run([FFMPEG, "-nostdin", "-loglevel", "error", "-f", "lavfi", "-i",
                        f"aevalsrc='{expr}':s=24000:d={seconds}"] + list(extra) + ["-y", path],
                       check=True)
        return path

    def test_pitch(self):
        for f0 in (100, 160, 240):
            p = self.vm.measure(FFMPEG, self.tone(f"t{f0}.wav", f0))
            self.assertAlmostEqual(self.vm.semitones_to_hz(p.pitch), f0, delta=f0 * 0.02)
            self.assertLess(p.spread, 0.5)
            self.assertGreater(p.voiced, 6)

    def test_no_voice(self):
        silent = os.path.join(self.tmp.name, "muto.wav")
        subprocess.run([FFMPEG, "-nostdin", "-loglevel", "error", "-f", "lavfi", "-i",
                        "anullsrc=r=16000:cl=mono", "-t", "5", "-y", silent], check=True)
        with self.assertRaises(self.vm.MatchError) as cm:
            self.vm.measure(FFMPEG, silent)
        self.assertEqual(cm.exception.key, "err_no_voice")

    def test_distance(self):
        P = self.vm.Profile
        ref = P(20.0, 3.0, 500.0, 30)
        self.assertEqual(self.vm.distance(ref, ref), 0)
        self.assertEqual(self.vm.similarity(0), 100)
        near, far = P(21.0, 3.0, 520.0, 10), P(30.0, 3.0, 500.0, 10)
        self.assertLess(self.vm.distance(ref, near), self.vm.distance(ref, far))
        self.assertEqual(self.vm.describe(ref, far), ("higher", "", ""))
        self.assertEqual(self.vm.describe(ref, P(15.0, 6.0, 1000.0, 9)),
                         ("lower", "brighter", "livelier"))
        self.assertEqual(self.vm.describe(ref, near), ("", "", ""))

    def test_windows(self):
        Cue = rd.Cue
        cues = [Cue(0, 500, "a"), Cue(1000, 41000, "b"), Cue(50000, 80000, "c"), Cue(90000, 95000, "d")]
        self.assertEqual(self.vm.speech_windows(100000, cues), [(1000, 41000), (50000, 80000)])
        self.assertEqual(self.vm.speech_windows(30000), [(0, 30000)])
        w = self.vm.speech_windows(600000)
        self.assertEqual(len(w), 3)
        self.assertEqual(sum(b - a for a, b in w), 60000)

    def test_search(self):
        """Video con una voce a 130 Hz; llama-tts finto con l'altezza dal
        seme: le voci tornano ordinate e la prima è la più vicina."""
        video = self.tone("video.mkv", 130, 12, ["-f", "lavfi", "-i",
                                                 "testsrc=size=64x48:rate=5:duration=12",
                                                 "-c:v", "libx264", "-preset", "ultrafast",
                                                 "-c:a", "aac", "-shortest"])
        bins = os.path.join(self.tmp.name, "bin")
        os.makedirs(bins, exist_ok=True)
        fake = os.path.join(bins, "llama-tts")
        with open(fake, "w") as f:
            f.write(FAKE_TTS_PITCH)
        os.chmod(fake, 0o755)
        model = os.path.join(self.tmp.name, "voce.gguf")
        proj = os.path.join(self.tmp.name, "mmproj-voce.gguf")
        for p in (model, proj):
            open(p, "w").close()
        saved = (rd.tts.ENGINE_DIRS, rd.tts.FFMPEG_PATHS, rd.tts.WORK_DIR)
        rd.tts.ENGINE_DIRS, rd.tts.FFMPEG_PATHS = (bins,), (FFMPEG,)
        rd.tts.WORK_DIR = os.path.join(self.tmp.name, "tts")
        work = os.path.join(self.tmp.name, "voci")
        loop = GLib.MainLoop()
        seen = {"stages": [], "done": None}

        def done(error, reference, candidates):
            seen["done"] = (error, reference, candidates)
            loop.quit()
        try:
            search = self.vm.VoiceSearch(work, lambda s, i=0, n=0: seen["stages"].append((s, i, n)),
                                         None, done)
            search.start(video, 12000, [], rd.tts.Voice(model, proj), "it", gpu=False, count=4)
            GLib.timeout_add_seconds(120, loop.quit)
            loop.run()
            error, reference, cands = seen["done"]
            self.assertIsNone(error, error)
            self.assertAlmostEqual(self.vm.semitones_to_hz(reference[1].pitch), 130, delta=3)
            self.assertEqual(len(cands), 4)
            self.assertEqual(cands, sorted(cands, key=lambda c: c.distance))
            for c in cands:
                self.assertAlmostEqual(self.vm.semitones_to_hz(c.profile.pitch),
                                       90 + c.seed % 160, delta=4)
            self.assertIn(("voice", 4, 4), seen["stages"])
            # Altre voci: si aggiungono, con semi nuovi.
            seen["done"] = None
            search.more(count=2)
            loop = GLib.MainLoop()
            GLib.timeout_add_seconds(120, loop.quit)
            loop.run()
            self.assertEqual(len(seen["done"][2]), 6)
            self.assertEqual(len({c.seed for c in seen["done"][2]}), 6)
            search.discard()
            left = [f for _r, _d, fs in os.walk(work) for f in fs]
            self.assertEqual(left, [])
        finally:
            rd.tts.ENGINE_DIRS, rd.tts.FFMPEG_PATHS, rd.tts.WORK_DIR = saved


    def test_one_card_becomes_three(self):
        """Le impostazioni con una sola scheda la danno a tutti e tre i passi."""
        try:
            import gi
            gi.require_version("Gtk", "4.0")
            gi.require_version("Adw", "1")
            import ruscadubbing as ui
        except (ImportError, ValueError):
            self.skipTest("GTK non disponibile")
        with tempfile.TemporaryDirectory() as t:
            path = os.path.join(t, "settings.json")
            saved = ui.CONFIG_FILE
            ui.CONFIG_FILE = path
            try:
                with open(path, "w") as f:
                    json.dump({"gpu_device": "NVIDIA GeForce RTX 3060"}, f)
                cfg = ui.load_settings()
                self.assertEqual({k: cfg[k] for k in ui.DEVICE_KEYS},
                                 dict.fromkeys(ui.DEVICE_KEYS, "NVIDIA GeForce RTX 3060"))
                with open(path, "w") as f:
                    json.dump({"gpu_device": "vecchia", "llm_device": "A", "tts_device": "B"}, f)
                cfg = ui.load_settings()
                self.assertEqual((cfg["whisper_device"], cfg["llm_device"], cfg["tts_device"]),
                                 ("", "A", "B"))
            finally:
                ui.CONFIG_FILE = saved


if __name__ == "__main__":
    unittest.main()
