"""RuscaLinux OS Tools — test di RuscaNarrator — 1.99.3 — GPL-3.0

rusca_tts.py divide un documento Markdown o un file SRT in pezzi, li fa
leggere a llama-tts e monta l'audio. Qui si controllano la divisione, la
lettura degli SRT e l'intero percorso con un llama-tts finto, che scrive un
WAV vero (un tono fra due silenzi, lungo in proporzione al testo): non
servono né il motore né un modello. FFmpeg invece è quello vero: senza, i
test che lo usano si saltano. Dalla radice del repository:
    python3 -m unittest tests/test_ruscanarrator.py
"""

import json
import os
import shutil
import stat
import sys
import tempfile
import unittest
import wave

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO, "tools", "ruscanarrator"))

try:
    from gi.repository import GLib
    import rusca_tts as tts
except (ImportError, ValueError):
    tts = None

FFMPEG = shutil.which("ffmpeg")

# llama-tts finto: 24 kHz, 16 bit; 0,2 s di silenzio, poi 60 ms di tono per
# carattere (o la durata scritta nel testo come "[durata 1500]"), poi 0,3 s
# di silenzio. Scrive gli argomenti in FAKE_ARGS (una riga JSON per pezzo).
FAKE_TTS = r'''#!/usr/bin/env python3
import json, math, os, re, struct, sys, time, wave
args = sys.argv[1:]
if args == ["--list-devices"]:
    print("Available devices:")
    print("  Vulkan0: Intel(R) Graphics (RPL-S) (15872 MiB, 14000 MiB free)")
    print("  Vulkan1: NVIDIA GeForce RTX 4060 (8188 MiB, 7900 MiB free)")
    sys.exit(0)
opt = lambda name: args[args.index(name) + 1]
text, out = opt("-p"), opt("-o")
with open(os.environ["FAKE_ARGS"], "a") as f:
    f.write(json.dumps(args + ["ENV", os.environ.get("VK_DRIVER_FILES", "")]) + "\n")
if "rotto" in opt("-m"):
    sys.stderr.write("failed to load model\n"); sys.exit(1)
if "lento" in opt("-m"):
    time.sleep(60)
m = re.search(r"\[durata (\d+)\]", text)
ms = int(m.group(1)) if m else 60 * len(text)
rate = 24000
w = wave.open(out, "wb"); w.setnchannels(1); w.setsampwidth(2); w.setframerate(rate)
w.writeframes(b"\0\0" * (rate // 5))
n = rate * ms // 1000
w.writeframes(b"".join(struct.pack("<h", int(12000 * math.sin(2 * math.pi * 220 * i / rate)))
                       for i in range(n)))
w.writeframes(b"\0\0" * (rate * 3 // 10))
w.close()
sys.stderr.write("generated frames, wrote %s\n" % out)
'''

DOC = """# Capitolo uno

Primo paragrafo. Ha due frasi.

- voce uno
- voce due

```
codice da non leggere
```

---

Ultimo paragrafo[^1].

[^1]: Una nota.
"""

SRT = """﻿1
00:00:01,000 --> 00:00:02,500
<i>Ciao</i> a tutti.

2
00:00:03,000 --> 00:00:04,000
- Troppo lungo,
- ma si accelera.

3
00:00:04,500 --> 00:00:05,000
Lunghissimo.

4
00:00:05,200 --> 00:00:06,000
[MUSICA] ♪ ♪

5
00:00:08,000 --> 00:00:10,000
{\\an8}Fine.
"""


@unittest.skipIf(tts is None, "PyGObject (GLib) non disponibile")
class Text(unittest.TestCase):
    def test_split(self):
        self.assertEqual(tts.split_text("  Breve.  "), ["Breve."])
        self.assertEqual(tts.split_text(""), [])
        long = " ".join(f"Frase numero {i} abbastanza lunga da riempire." for i in range(20))
        pieces = tts.split_text(long, 120)
        self.assertTrue(all(len(p) <= 120 for p in pieces), pieces)
        self.assertTrue(all(p.endswith(".") for p in pieces))
        self.assertEqual(" ".join(pieces).split(), long.split())
        # Una frase senza punti si divide alle virgole e poi fra le parole.
        words = ", ".join("parola " * 30 for _ in range(4))
        pieces = tts.split_text(words, 100)
        self.assertTrue(all(len(p) <= 100 for p in pieces))
        self.assertEqual(" ".join(pieces).split(), words.split())
        self.assertTrue(all(len(p) <= 50 for p in tts.split_text("x" * 130, 50)))

    def test_markdown(self):
        pieces = tts.markdown_pieces(DOC)
        self.assertEqual([p.text for p in pieces],
                         ["Capitolo uno.", "Primo paragrafo. Ha due frasi.", "voce uno.",
                          "voce due.", "Ultimo paragrafo."])
        self.assertEqual([p.pause for p in pieces], [900, 650, 400, 1200, 650])
        texts = [p.text for p in tts.markdown_pieces(DOC, read_code=True, read_notes=True)]
        self.assertIn("codice da non leggere", texts)
        self.assertEqual(texts[-1], "Una nota.")

    def test_srt(self):
        cues = tts.parse_srt(SRT.replace("\n", "\r\n"))
        self.assertEqual([(c.start, c.end, c.text) for c in cues],
                         [(1000, 2500, "Ciao a tutti."),
                          (3000, 4000, "Troppo lungo, ma si accelera."),
                          (4500, 5000, "Lunghissimo."),
                          (8000, 10000, "Fine.")])
        self.assertEqual(tts.parse_srt("1\n0:00:01.5 --> 0:00:02.25\nx\n")[0][2:], (1500, 2250))
        self.assertEqual(tts.parse_srt("niente"), [])

    def test_srt_sound_descriptions(self):
        self.assertEqual(tts.parse_srt("1\n00:00:00,000 --> 00:00:01,000\n[ride] Va bene\n")[0].text,
                         "Va bene")

    def test_preview(self):
        pieces = tts.markdown_pieces(DOC)
        text, spans = tts.preview_text(pieces)
        self.assertEqual([text[a:b] for a, b in spans], [p.text for p in pieces])
        text, spans = tts.preview_text(tts.parse_srt(SRT), srt=True)
        self.assertTrue(text.startswith("00:00:01  Ciao a tutti."))
        self.assertEqual(text[spans[-1][0]:spans[-1][1]], "Fine.")

    def test_voices(self):
        with tempfile.TemporaryDirectory() as d:
            files = ["Qwen3-TTS-12Hz-1.7B-Base-Q8_0.gguf", "Qwen3-TTS-12Hz-1.7B-Base-Q4_K_M.gguf",
                     "mmproj-Qwen3-TTS-12Hz-1.7B-Base-Q8_0.gguf",
                     "mmproj-Qwen3-TTS-12Hz-1.7B-Base-bf16.gguf",
                     "solo/pocket-tts.gguf", "solo/mmproj-pocket-tts.gguf",
                     "orfano/modello.gguf", "leggimi.txt"]
            for f in files:
                os.makedirs(os.path.dirname(os.path.join(d, f)), exist_ok=True)
                open(os.path.join(d, f), "w").close()
            got = [(os.path.relpath(v.model, d), os.path.basename(v.mmproj))
                   for v in tts.find_voices([d, "/non/esiste"])]
            self.assertEqual(got, [
                ("solo/pocket-tts.gguf", "mmproj-pocket-tts.gguf"),
                ("Qwen3-TTS-12Hz-1.7B-Base-Q4_K_M.gguf", "mmproj-Qwen3-TTS-12Hz-1.7B-Base-bf16.gguf"),
                ("Qwen3-TTS-12Hz-1.7B-Base-Q8_0.gguf", "mmproj-Qwen3-TTS-12Hz-1.7B-Base-bf16.gguf")])

    def test_voices_saved(self):
        """«Crea una voce»: nomi sicuri, mai sovrascrivere, elenco in ordine."""
        with tempfile.TemporaryDirectory() as d:
            src = os.path.join(d, "prova.wav")
            open(src, "w").close()
            folder = os.path.join(d, "voices")
            names = [os.path.basename(tts.save_voice(src, n, folder))
                     for n in ("Anna", "Anna", "  ../La mia/voce: bella?.  ", "...", "x" * 200)]
            self.assertEqual(names[:4], ["Anna.wav", "Anna (2).wav", "La mia voce bella.wav", "Voce.wav"])
            self.assertEqual(len(names[4]), 84)                  # 80 caratteri più ".wav"
            self.assertEqual([n for n, _p in tts.find_voice_files(folder)][:3],
                             ["Anna", "Anna (2)", "La mia voce bella"])
            self.assertEqual(tts.find_voice_files(os.path.join(d, "non-esiste")), [])
            self.assertFalse([f for f in os.listdir(folder) if f.endswith(".part")])

    def test_sample_text(self):
        for code, _name in tts.LANGUAGES:
            text = tts.sample_text(code)
            self.assertTrue(40 <= len(text) <= tts.MAX_CHARS, code)    # un pezzo solo
        self.assertEqual(tts.sample_text("xx"), tts.sample_text("en"))

    def test_atempo(self):
        self.assertEqual(tts._atempo(1.25), "atempo=1.2500")
        self.assertEqual(tts._atempo(3.0), "atempo=2.0,atempo=1.5000")


@unittest.skipIf(tts is None or FFMPEG is None, "PyGObject o FFmpeg non disponibili")
class Narrator(unittest.TestCase):
    """Tutto il percorso, con llama-tts finto e FFmpeg vero."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        t = self.tmp.name
        p = os.path.join(t, "llama-tts")
        with open(p, "w", encoding="utf-8") as f:
            f.write(FAKE_TTS)
        os.chmod(p, os.stat(p).st_mode | stat.S_IXUSR)
        self.saved = (tts.ENGINE_DIRS, tts.FFMPEG_PATHS, tts.WORK_DIR)
        tts.ENGINE_DIRS = (t,)
        tts.FFMPEG_PATHS = (FFMPEG,)
        tts.WORK_DIR = os.path.join(t, "lavoro")
        self.args = os.environ["FAKE_ARGS"] = os.path.join(t, "args.jsonl")
        self.voices = {}
        for name in ("buono", "rotto", "lento"):
            model = os.path.join(t, f"{name}.gguf")
            mmproj = os.path.join(t, f"mmproj-{name}.gguf")
            for f in (model, mmproj):
                open(f, "w").close()
            self.voices[name] = tts.Voice(model, mmproj)

    def tearDown(self):
        tts.ENGINE_DIRS, tts.FFMPEG_PATHS, tts.WORK_DIR = self.saved
        self.tmp.cleanup()

    def speak(self, pieces, voice="buono", cancel_after=None, **options):
        loop = GLib.MainLoop()
        seen = {"progress": [], "stages": [], "done": None}

        def done(error, path, stats):
            seen["done"] = (error, path, stats)
            loop.quit()
        s = tts.Speaker(lambda i, n: seen["progress"].append((i, n)), seen["stages"].append,
                        lambda line: None, done)
        s.start(pieces, self.voices[voice], **options)
        if cancel_after:
            GLib.timeout_add(cancel_after, lambda: s.cancel() and False)
        GLib.timeout_add_seconds(60, loop.quit)
        loop.run()
        s.wait(5)
        self.assertIsNotNone(seen["done"], "la lettura non è finita")
        seen["speaker"] = s
        return seen

    def calls(self):
        with open(self.args, encoding="utf-8") as f:
            return [json.loads(line) for line in f]

    def duration_ms(self, path):
        rate, _ch, _w, n = tts.wav_info(path)
        return n * 1000 // rate

    def test_markdown(self):
        pieces = [tts.Piece("Uno.", 650), tts.Piece("Due due.", 400)]
        seen = self.speak(pieces, language="it", speaker_file="", normalize=False, seed=7,
                          threads=3, gpu=True)
        error, path, _stats = seen["done"]
        self.assertIsNone(error)
        self.assertEqual(seen["progress"], [(0, 2), (1, 2)])
        self.assertEqual(seen["stages"], ["assemble"])
        # Silenzi del modello tolti (resta un margine di 50 ms prima e 100
        # ms dopo ogni frase, TRIM_FILTER), pause messe.
        margin = 150
        expected = 60 * 4 + margin + 650 + 60 * 8 + margin + 400
        self.assertAlmostEqual(self.duration_ms(path), expected, delta=150)
        self.assertEqual(tts.wav_info(path)[:3], (24000, 1, 2))
        args = self.calls()[0]
        self.assertEqual(args[args.index("--tts-lang") + 1], "it")
        self.assertEqual(args[args.index("-s") + 1], "7")
        self.assertEqual(args[args.index("-t") + 1], "3")
        self.assertEqual(args[args.index("-ngl") + 1], "99")
        self.assertNotIn("--device", args)
        self.assertNotIn("--tts-speaker-file", args)
        self.assertEqual(args[-1], "")                     # driver Vulkan visibili
        # Solo il risultato resta fra i file di lavoro, e si cancella con
        # discard().
        self.assertEqual(os.listdir(os.path.dirname(path)), ["audio.wav"])
        seen["speaker"].discard()
        self.assertEqual(os.listdir(tts.WORK_DIR), [])

    def test_srt_timing(self):
        # Durate con il margine di 150 ms (vedi test_markdown); lo spazio
        # di una voce arriva fino al sottotitolo dopo.
        cues = [tts.Piece("Ciao a tutti.", 0, 1000, 2500),             # 930 in 2000: ci sta
                tts.Piece("[durata 1300]", 0, 3000, 4000),           # 1450 in 1500: ci sta
                tts.Piece("[durata 1600] veloce", 0, 4500, 5000),    # 1750 in 3500: ci sta
                tts.Piece("[durata 1400]", 0, 8000, 8500),           # 1550 in 600: no
                tts.Piece("Fine.", 0, 8600, 10000)]
        seen = self.speak(cues, srt=True, max_speed=1.5, normalize=False)
        error, path, stats = seen["done"]
        self.assertIsNone(error)
        # Il quarto supera lo spazio (fino a 8600): accelerato al massimo
        # (1,5) dura circa 1033 ms, finisce a 9033 e il quinto parte in
        # ritardo di circa 433 ms.
        self.assertEqual(stats["faster"], 1)
        self.assertEqual(stats["late"], 1)
        self.assertAlmostEqual(stats["max_late_ms"], 433, delta=60)
        # Durata: fino alla fine dell'ultimo sottotitolo (10 s), o poco più
        # se l'ultima voce è in ritardo.
        self.assertAlmostEqual(self.duration_ms(path), 10000, delta=120)
        # Ogni voce parte alla sua ora: si guarda dove finisce il silenzio.
        with wave.open(path, "rb") as w:
            data = w.readframes(w.getnframes())
        loud = [i for i in range(0, len(data) // 2, 24)
                if abs(int.from_bytes(data[2 * i:2 * i + 2], "little", signed=True)) > 2000]
        first = loud[0] * 1000 // 24000
        self.assertAlmostEqual(first, 1000, delta=60)

    def test_cpu_and_device(self):
        self.speak([tts.Piece("Uno.")], gpu=False, gpu_device="NVIDIA GeForce RTX 4060",
                   normalize=False)
        args = self.calls()[-1]
        self.assertEqual(args[args.index("-ngl") + 1], "0")
        self.assertEqual(args[args.index("--device") + 1], "none")
        self.assertIn("--no-mmproj-offload", args)
        self.assertEqual(args[-1], "/dev/null")
        self.speak([tts.Piece("Uno.")], gpu=True, gpu_device="NVIDIA GeForce RTX 4060",
                   speaker_file=self.voices["buono"].model, voice_name="giovanni",
                   normalize=False)
        args = self.calls()[-1]
        self.assertEqual(args[args.index("--device") + 1], "Vulkan1")
        self.assertEqual(args[args.index("--tts-speaker-file") + 1], self.voices["buono"].model)
        self.assertEqual(args[args.index("--tts-voice") + 1], "giovanni")
        self.speak([tts.Piece("Uno.")], gpu=True, gpu_device="Scheda tolta", normalize=False)
        self.assertNotIn("--device", self.calls()[-1])

    def test_normalize_and_export(self):
        error, path, _stats = self.speak([tts.Piece("Volume normalizzato.")], normalize=True)["done"]
        self.assertIsNone(error)
        for fmt, magic in (("wav", b"RIFF"), ("flac", b"fLaC"), ("opus", b"OggS"), ("mp3", None)):
            dst = os.path.join(self.tmp.name, f"uscita.{fmt}")
            tts.export(path, dst, fmt)
            with open(dst, "rb") as f:
                head = f.read(4)
            if magic:
                self.assertEqual(head, magic, fmt)
            else:
                self.assertTrue(head.startswith(b"ID3") or head[:2] in (b"\xff\xfb", b"\xff\xf3"),
                                head)
            self.assertFalse(os.path.exists(dst + ".part"))

    def test_engine_error(self):
        error, path, _ = self.speak([tts.Piece("Uno.")], voice="rotto")["done"]
        self.assertEqual(error.key, "err_engine")
        self.assertIn("failed to load model", error.detail)
        self.assertIsNone(path)
        self.assertEqual(os.listdir(tts.WORK_DIR), [])

    def test_cancel(self):
        seen = self.speak([tts.Piece("Uno."), tts.Piece("Due.")], voice="lento", cancel_after=1500)
        self.assertEqual(seen["done"][:2], ("cancelled", None))
        self.assertEqual(os.listdir(tts.WORK_DIR), [])

    def test_missing(self):
        s = tts.Speaker()
        with self.assertRaises(tts.TTSError) as e:
            s.start([], self.voices["buono"])
        self.assertEqual(e.exception.key, "err_empty")
        with self.assertRaises(tts.TTSError) as e:
            s.start([tts.Piece("x")], tts.Voice("/no.gguf", "/no-mmproj.gguf"))
        self.assertEqual(e.exception.key, "err_no_model")
        with self.assertRaises(tts.TTSError) as e:
            s.start([tts.Piece("x")], self.voices["buono"], speaker_file="/non/esiste.wav")
        self.assertEqual(e.exception.key, "err_speaker")
        tts.ENGINE_DIRS = ("/non/esiste",)
        with self.assertRaises(tts.TTSError) as e:
            s.start([tts.Piece("x")], self.voices["buono"])
        self.assertEqual(e.exception.key, "err_no_engine")

    def test_devices(self):
        devices = tts.list_devices()
        self.assertEqual(devices, [("Vulkan0", "Intel(R) Graphics (RPL-S)", 15872),
                                   ("Vulkan1", "NVIDIA GeForce RTX 4060", 8188)])
        self.assertEqual(tts.device_name("NVIDIA GeForce RTX 4060", devices), "Vulkan1")
        self.assertIsNone(tts.device_name("", devices))


if __name__ == "__main__":
    unittest.main()
