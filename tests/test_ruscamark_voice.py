"""RuscaLinux OS Apps — test della voce di RuscaMark — 1.99.3 — GPL-3.0

rusca_voice.py (apps/ruscamark/) detta nel documento con Vosk o Whisper,
trascrive un file audio in Markdown e legge ad alta voce con Piper. Qui si
controllano il testo dettato (comandi a voce, spazi, maiuscole, protezione
del Markdown), le frasi da leggere e i percorsi completi con programmi finti
al posto di pw-record, whisper-cli, ffmpeg, ruscapiper-stream e pw-play, e
con una libvosk.so finta compilata al momento (serve gcc, altrimenti quei
test si saltano): non servono né i motori né i modelli. Si lanciano dalla
radice del repository:
    python3 -m unittest tests/test_ruscamark_voice.py

rusca_voice.py usa GLib (PyGObject) e il motore Markdown comune: senza, i
test si saltano.
"""

import ast
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import unittest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
APP = os.path.join(REPO, "apps", "ruscamark")
sys.path.insert(0, APP)

try:
    from gi.repository import GLib
    import rusca_whisper
    # rusca_voice.py sposta la cartella di lavoro del modulo comune, come
    # RuscaDubbing: nello stesso processo dei test degli altri tool si rimette
    # quella che c'era (i test qui sotto usano comunque cartelle proprie).
    _work_dir = rusca_whisper.WORK_DIR
    import rusca_voice as rv
    rusca_whisper.WORK_DIR = _work_dir
except (ImportError, ValueError):
    rv = None

NEED = unittest.skipIf(rv is None, "servono PyGObject e markdown-it")


def write_exe(path, text):
    with open(path, "w", encoding="utf-8") as f:
        f.write(text.replace("#!/usr/bin/env python3", "#!" + sys.executable, 1))
    os.chmod(path, 0o755)
    return path


def run_loop(until, timeout=15.0):
    """Gira il ciclo di GLib (le callback arrivano con idle_add) finché
    until() è vero o scade il tempo."""
    ctx = GLib.MainContext.default()
    end = time.monotonic() + timeout
    while time.monotonic() < end and not until():
        while ctx.pending():
            ctx.iteration(False)
        time.sleep(0.01)
    while ctx.pending():
        ctx.iteration(False)
    return until()


# Microfono finto: 0,4 s di silenzio, 1 s di «voce» (onda quadra), 1 s di
# silenzio, poi aspetta di essere fermato. Formato di pw-record: s16, 16 kHz.
FAKE_RECORD = r"""#!/usr/bin/env python3
import struct, sys, time
if "--help" in sys.argv:
    print("  --raw   RAW mode"); sys.exit(0)
out = sys.stdout.buffer
def frames(n, amp):
    for i in range(n):
        out.write(struct.pack("<320h", *([amp, -amp] * 160)))
frames(20, 0); frames(50, 6000); frames(50, 0); out.flush()
time.sleep(30)
"""

# whisper-cli finto: scrive il JSON come quello vero e i tempi sullo
# standard error; salva argomenti e variabili per il test.
FAKE_WHISPER = r"""#!/usr/bin/env python3
import json, os, sys
a = sys.argv[1:]
log = os.environ["FAKE_LOG"]
with open(log, "a") as f:
    f.write(json.dumps({"args": a, "vk": os.environ.get("VK_DRIVER_FILES", ""),
                        "dev": os.environ.get("GGML_VK_VISIBLE_DEVICES", ""),
                        "wav": os.path.getsize(a[a.index("-f") + 1])}) + "\n")
prefix = a[a.index("-of") + 1]
text = os.environ.get("FAKE_TEXT", "Ciao a tutti.")
json.dump({"result": {"language": "it"},
           "transcription": [{"offsets": {"from": 0, "to": 1000}, "text": " " + text},
                             {"offsets": {"from": 3000, "to": 4000}, "text": " Seconda frase."}]},
          open(prefix + ".json", "w"))
sys.stderr.write("whisper_print_timings:    total time =   10.00 ms\n")
"""

# ffmpeg finto: per Whisper scrive un WAV, per Vosk l'audio grezzo sullo
# standard output; la durata sullo standard error, come quello vero.
FAKE_FFMPEG = r"""#!/usr/bin/env python3
import struct, sys, wave
a = sys.argv[1:]
sys.stderr.write("  Duration: 00:00:02.00, start: 0.000000, bitrate: 256 kb/s\n")
pcm = struct.pack("<32000h", *([3000, -3000] * 16000))
if a[-1] == "-":
    sys.stdout.buffer.write(pcm)
else:
    w = wave.open(a[-1], "wb"); w.setnchannels(1); w.setsampwidth(2); w.setframerate(16000)
    w.writeframes(pcm); w.close()
"""

# libvosk.so finta: stessa API in C. Una frase finisce ogni 10 blocchi da
# 100 ms (dettatura) o a ogni secondo d'audio (file). Con -DNEVER non finisce
# mai da sola e il testo parziale conta i blocchi ricevuti: serve a vedere
# che nessun pezzo d'audio si perde.
FAKE_VOSK_C = r"""
#include <stdio.h>
#include <stdlib.h>
static int calls = 0;
static char partial[64];
void vosk_set_log_level(int l) {}
void *vosk_model_new(const char *p) { return malloc(1); }
void vosk_model_free(void *m) { free(m); }
void *vosk_recognizer_new(void *m, float r) { return malloc(1); }
void vosk_recognizer_free(void *r) { free(r); }
void vosk_recognizer_set_words(void *r, int w) {}
int vosk_recognizer_accept_waveform(void *r, const char *d, int n) {
#ifdef NEVER
  calls += n / 3200; return 0;
#else
  return ++calls % 10 == 0 || n >= 32000;
#endif
}
const char *vosk_recognizer_result(void *r) {
  return "{\"text\": \"ciao virgola come stai punto interrogativo\", \"result\": "
         "[{\"word\": \"ciao\", \"start\": 0.5, \"end\": 0.9, \"conf\": 1.0}]}"; }
const char *vosk_recognizer_final_result(void *r) { return "{\"text\": \"\"}"; }
void vosk_recognizer_reset(void *r) { calls = 0; }
const char *vosk_recognizer_partial_result(void *r) {
#ifdef NEVER
  snprintf(partial, sizeof partial, "{\"partial\": \"blocchi %d\"}", calls); return partial;
#else
  return "{\"partial\": \"ciao\"}";
#endif
}
"""


@NEED
class TestCopie(unittest.TestCase):
    def test_moduli_comuni_identici(self):
        for name, other in (("rusca_vosk.py", "ruscallisse"), ("rusca_piper.py", "ruscallisse"),
                            ("speech_text.py", "ruscallisse"), ("pronunce.tsv", "ruscallisse"),
                            ("rusca_whisper.py", "ruscatranscriber")):
            a = open(os.path.join(APP, name), "rb").read()
            b = open(os.path.join(REPO, "apps", other, name), "rb").read()
            self.assertEqual(a, b, name)

    def test_niente_moduli_di_rete(self):
        net = {"socket", "http", "urllib", "requests", "ssl", "ftplib", "smtplib", "asyncio"}
        for name in ("rusca_voice.py", "rusca_vosk.py", "rusca_whisper.py", "rusca_piper.py",
                     "speech_text.py"):
            tree = ast.parse(open(os.path.join(APP, name), encoding="utf-8").read())
            for node in ast.walk(tree):
                mods = []
                if isinstance(node, ast.Import):
                    mods = [a.name for a in node.names]
                elif isinstance(node, ast.ImportFrom) and node.module:
                    mods = [node.module]
                for m in mods:
                    self.assertNotIn(m.split(".")[0], net, f"{name}: {m}")

    def test_cartelle_di_lavoro_proprie(self):
        # Si guarda il sorgente e non rusca_whisper.WORK_DIR: nello stesso
        # processo un altro test (RuscaDubbing) può averlo spostato.
        src = open(os.path.join(APP, "rusca_voice.py"), encoding="utf-8").read()
        self.assertIn('whisper.WORK_DIR = os.path.join(GLib.get_user_cache_dir(), "ruscamark", '
                      '"trascrizione")', src)
        self.assertTrue(rv.LIVE_DIR.endswith("ruscamark"))


@NEED
class TestTestoDettato(unittest.TestCase):
    def test_comandi_a_voce(self):
        t = rv.dictation_text("ciao virgola come stai punto interrogativo bene grazie punto",
                              "", "it")
        self.assertEqual(t, "Ciao, come stai? Bene grazie.")
        self.assertEqual(rv.dictation_text("hello comma world full stop", "", "en"),
                         "Hello, world.")

    def test_a_capo_e_paragrafo(self):
        self.assertEqual(rv.dictation_text("nuovo paragrafo secondo punto", "Fine.", "it"),
                         "\n\nSecondo.")
        # dopo un a capo si ricomincia con la maiuscola
        self.assertEqual(rv.dictation_text("uno a capo due", "", "it"), "Uno\nDue")

    def test_spazi_dopo_il_testo(self):
        self.assertEqual(rv.dictation_text("e poi", "Parola", "it"), " e poi")
        self.assertEqual(rv.dictation_text("e poi", "Parola ", "it"), "e poi")
        self.assertEqual(rv.dictation_text("virgola e poi", "Parola", "it"), ", e poi")
        self.assertEqual(rv.dictation_text("apri parentesi nota chiudi parentesi", "Testo", "it"),
                         " (nota)")

    def test_comandi_markdown(self):
        it = lambda t, b="": rv.dictation_text(t, b, "it")
        self.assertEqual(it("titolo due introduzione", "Testo."), "\n\n## Introduzione\n\n")
        self.assertEqual(it("questo è il testo", "## Introduzione\n\n"), "Questo è il testo")
        self.assertEqual(it("elenco latte", "Lista:"), "\n- Latte")
        self.assertEqual(it("elenco pane", "Lista:\n- Latte"), "\n- Pane")
        self.assertEqual(it("poi si continua", "- Latte\n- Pane\n"), "\nPoi si continua")
        self.assertEqual(it("elenco numerato secondo", "1. Primo\n"), "2. Secondo")
        self.assertEqual(it("citazione essere o non essere"), "> Essere o non essere")
        self.assertEqual(it("è inizio grassetto molto fine grassetto importante", "Questo"),
                         " è **molto** importante")
        self.assertEqual(it("inizio corsivo nota fine corsivo e basta"), "*Nota* e basta")
        self.assertEqual(rv.dictation_text("heading one my notes", "", "en"), "# My notes\n\n")
        # in mezzo a una frase «titolo» è una parola
        self.assertEqual(it("il titolo del libro", "Leggo"), " il titolo del libro")

    def test_comandi_markdown_con_whisper(self):
        # Whisper aggiunge maiuscole e punti: i comandi si riconoscono lo
        # stesso, la punteggiatura detta a parole no.
        self.assertEqual(rv.dictation_text("Titolo due. Introduzione.", "Testo.\n", "it",
                                           commands=False, markdown=True),
                         "\n## Introduzione\n\n")
        self.assertEqual(rv.dictation_text("Il punto è questo.", "", "it",
                                           commands=False, markdown=True),
                         "Il punto è questo.")

    def test_finale_o_parziale(self):
        self.assertEqual(rv.longer("", "ciao a tutti"), "ciao a tutti")
        self.assertEqual(rv.longer("ciao", "ciao a tutti"), "ciao a tutti")
        self.assertEqual(rv.longer("ciao a tutte", "ciao a tutti"), "ciao a tutte")

    def test_aiuto_dei_comandi(self):
        groups = dict(rv.command_help("it"))
        self.assertIn(("virgola", ","), groups["punct"])
        self.assertIn(("titolo due", "##"), groups["blocks"])
        self.assertIn(("nuovo paragrafo", "¶"), groups["lines"])
        self.assertEqual(rv.command_help("de"), rv.command_help("en"))

    def test_senza_comandi_whisper(self):
        # Whisper scrive già la punteggiatura: «punto» resta una parola.
        self.assertEqual(rv.dictation_text("Il punto è questo.", "", "it", commands=False),
                         "Il punto è questo.")

    def test_il_parlato_non_diventa_markdown(self):
        self.assertEqual(rv.dictation_text("1. Primo, *bello*", "", commands=False),
                         "1\\. Primo, \\*bello\\*")
        # A metà riga «#» e «1.» non formattano: restano come sono.
        self.assertEqual(rv.dictation_text("# tre e 5 $", "Prezzo:", commands=False),
                         " # tre e 5 \\$")
        # niente link automatici verso indirizzi detti a voce
        self.assertIn("www\\.", rv.dictation_text("vai su www.esempio.it", "", commands=False))

    def test_frasi_da_leggere(self):
        doc = ("# Titolo\n\nUn **paragrafo** con [link](http://x). Seconda frase!\n\n"
               "- voce uno\n- voce due\n\n```\ncodice\n```\n\nTesto[^1].\n\n[^1]: Nota.\n")
        self.assertEqual(rv.reading_sentences(doc),
                         ["Titolo.", "Un paragrafo con link.", "Seconda frase!",
                          "voce uno.", "voce due.", "Testo."])
        self.assertIn("codice", " ".join(rv.reading_sentences(doc, skip_code=False)))
        self.assertEqual(rv.reading_sentences("ancora qui", lexicon={"ancora": "ancóra"}),
                         ["ancóra qui"])

    def test_scelta_dei_modelli(self):
        # Una copia nuova di rusca_vosk.model_language: nello stesso processo
        # un altro test (RuscaPallas) può averla sostituita.
        import importlib.util
        spec = importlib.util.spec_from_file_location("vosk_fresco", os.path.join(APP, "rusca_vosk.py"))
        fresh = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(fresh)
        saved, rv.vosk.model_language = rv.vosk.model_language, fresh.model_language
        self.addCleanup(setattr, rv.vosk, "model_language", saved)
        models = ["/m/vosk-model-en-us-0.22", "/m/vosk-model-it-0.22", "/m/vosk-model-small-it-0.22"]
        self.assertEqual(rv.pick_vosk_model(models, "", "it"), "/m/vosk-model-it-0.22")
        self.assertEqual(rv.pick_vosk_model(models, "/m/vosk-model-small-it-0.22", "it"),
                         "/m/vosk-model-small-it-0.22")
        self.assertEqual(rv.pick_vosk_model(models, "/sparito", "fr"), models[0])
        self.assertEqual(rv.pick_vosk_model([], "", "it"), "")
        self.assertEqual(rv.model_label("/x/ggml-large-v3-turbo.bin"), "ggml-large-v3-turbo")
        self.assertEqual(rv.base_language("pt_BR"), "pt")


class _Fakes(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.mkdtemp()
        self.log = os.path.join(self.d, "whisper.log")
        os.environ["FAKE_LOG"] = self.log
        self.record = write_exe(os.path.join(self.d, "pw-record"), FAKE_RECORD)
        eng = os.path.join(self.d, "engine")
        os.mkdir(eng)
        write_exe(os.path.join(eng, "whisper-cli"), FAKE_WHISPER)
        self.ffmpeg = write_exe(os.path.join(self.d, "ffmpeg"), FAKE_FFMPEG)
        self.model = os.path.join(self.d, "ggml-tiny.bin")
        open(self.model, "wb").write(b"x")
        self.saved = (rv.PW_RECORD, rv.LIVE_DIR, rv.whisper.ENGINE_DIRS, rv.whisper.FFMPEG_PATHS,
                      rv.whisper.WORK_DIR, rv.whisper.MODEL_DIRS, rv.vosk.LIB_DIRS, rv.vosk._lib)
        rv.PW_RECORD = self.record
        rv.LIVE_DIR = os.path.join(self.d, "live")
        rv.whisper.ENGINE_DIRS = (eng,)
        rv.whisper.FFMPEG_PATHS = (self.ffmpeg,)
        rv.whisper.WORK_DIR = os.path.join(self.d, "work")
        rv.whisper.MODEL_DIRS = (os.path.join(self.d, "nessuno"),)       # niente VAD

    def tearDown(self):
        (rv.PW_RECORD, rv.LIVE_DIR, rv.whisper.ENGINE_DIRS, rv.whisper.FFMPEG_PATHS,
         rv.whisper.WORK_DIR, rv.whisper.MODEL_DIRS, rv.vosk.LIB_DIRS, rv.vosk._lib) = self.saved
        os.environ.pop("FAKE_TEXT", None)
        shutil.rmtree(self.d, ignore_errors=True)

    def calls(self):
        try:
            return [json.loads(line) for line in open(self.log)]
        except OSError:
            return []

    def fake_vosk(self, *flags):
        if not shutil.which("gcc"):
            self.skipTest("serve gcc per la libvosk.so finta")
        src = os.path.join(self.d, "vosk.c")
        open(src, "w").write(FAKE_VOSK_C)
        lib_dir = os.path.join(self.d, "vosk")
        os.mkdir(lib_dir)
        subprocess.run(["gcc", "-shared", "-fPIC", *flags, "-o",
                        os.path.join(lib_dir, "libvosk.so"), src], check=True)
        rv.vosk.LIB_DIRS = (lib_dir,)
        rv.vosk._lib = None
        model = os.path.join(self.d, "vosk-model-it-0.22")
        os.makedirs(os.path.join(model, "am"))
        os.makedirs(os.path.join(model, "conf"))
        open(os.path.join(model, "am", "final.mdl"), "wb").close()
        return model


@NEED
class TestDettaturaWhisper(_Fakes):
    def dictate(self, **options):
        texts, states, errors = [], [], []
        d = rv.Dictation(on_state=states.append, on_text=texts.append, on_error=errors.append)
        d.prompt = "Testo già scritto."
        opts = {"whisper_model": self.model, "language": "it", "gpu": False}
        opts.update(options)
        d.start("whisper", opts)
        self.assertTrue(run_loop(lambda: texts or errors))
        d.stop()
        self.assertTrue(run_loop(lambda: "stopped" in states))
        self.assertTrue(d.close())
        return texts, states, errors

    def test_una_frase_dopo_la_pausa(self):
        texts, states, errors = self.dictate()
        self.assertEqual(errors, [])
        self.assertEqual(texts, ["Ciao a tutti. Seconda frase."])
        self.assertIn("writing", states)
        call = self.calls()[0]
        a = call["args"]
        self.assertEqual(a[a.index("-l") + 1], "it")
        self.assertIn("-sns", a)
        self.assertIn("-ng", a)                          # processore
        self.assertEqual(call["vk"], "/dev/null")        # driver Vulkan nascosti
        self.assertEqual(a[a.index("--prompt") + 1], "Testo già scritto.")
        # la frase: 0,3 s prima della voce + 1 s di voce + 0,7 s di pausa
        self.assertGreater(call["wav"], 16000 * 2 * 1.5)
        # nessun audio rimasto su disco
        self.assertEqual(os.listdir(rv.LIVE_DIR), [])

    def test_scheda_grafica_scelta(self):
        saved = rv.whisper.list_devices
        rv.whisper.list_devices = lambda timeout=20: [
            {"index": 0, "name": "Radeon", "type": "integrated", "mib": 512, "label": "Radeon"},
            {"index": 1, "name": "RTX 3060", "type": "discrete", "mib": 6144, "label": "RTX 3060"}]
        try:
            texts, _states, errors = self.dictate(gpu=True, gpu_device="RTX 3060")
        finally:
            rv.whisper.list_devices = saved
        self.assertEqual(errors, [])
        call = self.calls()[0]
        self.assertNotIn("-ng", call["args"])
        self.assertEqual(call["dev"], "1")
        self.assertEqual(call["vk"], "")

    def test_senza_motore(self):
        rv.whisper.ENGINE_DIRS = (os.path.join(self.d, "niente"),)
        with self.assertRaises(rv.VoiceError) as e:
            rv.Dictation().start("whisper", {"whisper_model": self.model})
        self.assertEqual(e.exception.key, "err_no_whisper")

    def test_senza_modello(self):
        with self.assertRaises(rv.VoiceError) as e:
            rv.Dictation().start("whisper", {"whisper_model": ""})
        self.assertEqual(e.exception.key, "err_no_whisper_model")


@NEED
class TestDettaturaVosk(_Fakes):
    def test_parole_mentre_si_parla(self):
        model = self.fake_vosk()
        texts, partials, states, errors = [], [], [], []
        d = rv.Dictation(on_state=states.append, on_text=texts.append,
                         on_partial=partials.append, on_error=errors.append)
        d.start("vosk", {"vosk_model": model})
        self.assertTrue(run_loop(lambda: texts or errors))
        self.assertEqual(errors, [])
        self.assertEqual(texts[0], "ciao virgola come stai punto interrogativo")
        self.assertIn("ciao", partials)
        self.assertEqual(states[:2], ["loading", "listening"])
        d.stop()
        self.assertTrue(run_loop(lambda: "stopped" in states))
        # il modello resta caricato e si presta alla trascrizione di un file
        self.assertIsNotNone(d.borrow_recognizer(model))
        self.assertIsNone(d.borrow_recognizer(model + "-altro"))
        self.assertTrue(d.close())
        self.assertIsNone(d.borrow_recognizer(model))

    def test_nessuna_parola_persa(self):
        """L'audio si legge in un thread a parte e dopo «Ferma» si riconosce
        anche quello rimasto: 2,4 s di audio sono 24 blocchi da 100 ms, e il
        testo finale (qui il parziale, perché il finale arriva vuoto) li ha
        visti tutti."""
        model = self.fake_vosk("-DNEVER")
        texts, partials, states = [], [], []
        d = rv.Dictation(on_state=states.append, on_text=texts.append,
                         on_partial=partials.append)
        d.start("vosk", {"vosk_model": model})
        self.assertTrue(run_loop(lambda: "blocchi 24" in partials))
        self.assertEqual(texts, [])           # il parziale cambia: la frase non è finita
        d.stop()
        self.assertTrue(run_loop(lambda: "stopped" in states))
        self.assertEqual(texts, ["blocchi 24"])
        d.close()

    def test_file_audio_con_vosk(self):
        model = self.fake_vosk()
        done = []
        job = rv.FileTranscriber(on_done=lambda e, m: done.append((e, m)))
        job.start(os.path.join(self.d, "intervista.mp3"), "vosk", {"vosk_model": model},
                  title="Intervista")
        self.assertTrue(run_loop(lambda: done))
        error, markdown = done[0]
        self.assertIsNone(error, getattr(error, "detail", error))
        self.assertTrue(markdown.startswith("# Intervista\n\n"), markdown)
        self.assertIn("Ciao virgola come stai punto interrogativo.", markdown)


@NEED
class TestFileWhisper(_Fakes):
    def test_file_audio_in_markdown(self):
        done, stages = [], []
        job = rv.FileTranscriber(on_progress=lambda f, s: stages.append(s),
                                 on_done=lambda e, m: done.append((e, m)))
        media = os.path.join(self.d, "lezione.ogg")
        open(media, "wb").write(b"audio")
        job.start(media, "whisper",
                  {"whisper_model": self.model, "language": "auto", "gpu": False},
                  title="Lezione")
        self.assertTrue(run_loop(lambda: done))
        error, markdown = done[0]
        self.assertIsNone(error)
        # pausa di due secondi fra i segmenti: due paragrafi
        self.assertEqual(markdown, "# Lezione\n\nCiao a tutti.\n\nSeconda frase.\n")
        self.assertIn("audio", stages)
        self.assertEqual(self.calls()[0]["args"][self.calls()[0]["args"].index("-l") + 1], "auto")
        self.assertEqual(os.listdir(rv.whisper.WORK_DIR), [])

    def test_errori_con_i_nomi_di_ruscamark(self):
        rv.whisper.FFMPEG_PATHS = (os.path.join(self.d, "niente"),)
        with self.assertRaises(rv.VoiceError) as e:
            rv.FileTranscriber().start("x.mp3", "whisper", {"whisper_model": self.model})
        self.assertEqual(e.exception.key, "err_no_ffmpeg")


FAKE_STREAM = r"""#!/usr/bin/env python3
import struct, sys
out = sys.stdout.buffer
out.write(b"RPS1" + struct.pack("<I", 1)); out.flush()
with open(sys.argv[-1] + ".said", "a") as log:
    for line in sys.stdin.buffer:
        cid, scale, text = line.decode().rstrip("\n").split("\t", 2)
        log.write(text + "\n"); log.flush()
        n = 800
        out.write(struct.pack("<4s6I", b"RPSC", int(cid), 1, 16000, n, 0, 0))
        out.write(struct.pack(f"<{n}h", *([1000] * n))); out.flush()
"""


@NEED
class TestLettura(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.mkdtemp()
        p = rv.piper
        self.saved = (p.STREAM, p.PW_PLAY)
        p.STREAM = write_exe(os.path.join(self.d, "ruscapiper-stream"), FAKE_STREAM)
        p.PW_PLAY = write_exe(os.path.join(self.d, "pw-play"),
                              "#!/bin/sh\n[ \"$1\" = --help ] && exit 0\ncat > /dev/null\n")
        self.voice = os.path.join(self.d, "it_IT-voce-medium.onnx")
        open(self.voice, "wb").close()
        open(self.voice + ".json", "w").write('{"audio": {"sample_rate": 16000}, '
                                              '"language": {"code": "it_IT"}}')

    def tearDown(self):
        rv.piper.STREAM, rv.piper.PW_PLAY = self.saved
        shutil.rmtree(self.d, ignore_errors=True)

    def test_legge_e_torna_libero(self):
        states, errors = [], []
        r = rv.Reader(on_state=states.append, on_error=errors.append)
        r.read(["Prima frase.", "Seconda frase."], self.voice, 1.0)
        self.assertTrue(run_loop(lambda: "reading" in states and states[-1] == "idle"))
        self.assertEqual(errors, [])
        said = open(self.voice + ".said").read().split("\n")
        self.assertEqual(said[:2], ["Prima frase.", "Seconda frase."])
        r.close()

    def test_voce_scelta_per_lingua(self):
        other = os.path.join(self.d, "en_GB-voice.onnx")
        open(other, "wb").close()
        open(other + ".json", "w").write('{"language": {"code": "en_GB"}}')
        self.assertEqual(rv.pick_voice([other, self.voice], "", "it"), self.voice)
        self.assertEqual(rv.pick_voice([other, self.voice], other, "it"), other)

    def test_senza_ruscapiper(self):
        rv.piper.STREAM = os.path.join(self.d, "niente")
        with self.assertRaises(rv.VoiceError) as e:
            rv.Reader().read(["Ciao."], self.voice)
        self.assertEqual(e.exception.key, "err_no_piper")


if __name__ == "__main__":
    unittest.main()
