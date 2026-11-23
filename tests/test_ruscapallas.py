# -*- coding: utf-8 -*-
"""Test di RuscaPallas senza motori veri e senza GNOME Shell: moduli condivisi
con RuscaLLisse, personalità di Pallasio, impostazioni, servizio di dialogo
(stati, ascolto a tempo, bocca, errori) con una conversazione e una voce
finte. Con gjs si provano anche il disegno, l'animazione e i salti
dell'estensione. Senza PyGObject si saltano.

    python3 -m unittest tests/test_ruscapallas.py
"""
import filecmp
import importlib.util
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import unittest

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
APP = os.path.join(ROOT, "apps", "ruscapallas")
LISSE = os.path.join(ROOT, "apps", "ruscallisse")
SHARED = ("conversation.py", "entity.py", "rusca_engine.py", "rusca_piper.py", "rusca_vosk.py",
          "speech_text.py", "rusca_markdown.py", "markdown_it_mark.py", "pronunce.tsv")

try:
    import gi  # noqa: F401
    from gi.repository import GLib  # noqa: F401
    HAVE_GI = True
except ImportError:
    HAVE_GI = False


def _read(path):
    with open(path, encoding="utf-8") as f:
        return f.read()


def _json(path, data=None):
    if data is None:
        return json.loads(_read(path))
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f)


def load_service():
    sys.path.insert(0, APP)
    spec = importlib.util.spec_from_file_location("ruscapallas_service",
                                                  os.path.join(APP, "ruscapallas-service.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class TestFile(unittest.TestCase):
    def test_moduli_identici_a_ruscallisse(self):
        for name in SHARED:
            self.assertTrue(filecmp.cmp(os.path.join(APP, name), os.path.join(LISSE, name), shallow=False),
                            f"{name} non è identico a quello di RuscaLLisse")

    def test_traduzioni_stesse_chiavi(self):
        it = _json(os.path.join(APP, "lang", "it.json"))
        en = _json(os.path.join(APP, "lang", "en.json"))
        self.assertEqual(set(it), set(en))
        for key in ("menu_stop", "menu_hide", "err_missing", "err_engines", "err_generic", "relogin"):
            self.assertIn(key, it)

    def test_metadati_estensione(self):
        meta = _json(os.path.join(APP, "extension", "metadata.json"))
        self.assertEqual(meta["uuid"], "ruscapallas@ruscalinux.org")
        self.assertIn("48", meta["shell-version"])
        self.assertEqual(meta["version-name"], "1.99.3")

    def test_fumetto_senza_parole(self):
        """Il fumetto mostra solo simboli: nessuna stringa tradotta lo usa."""
        src = _read(os.path.join(APP, "extension", "pallasio.js"))
        for icon in ("'ear'", "'dots'", "'waves'", "'hourglass'"):
            self.assertIn(icon, src)
        self.assertNotIn("set_text", src)


@unittest.skipUnless(HAVE_GI, "serve PyGObject")
class TestPersonalita(unittest.TestCase):
    def setUp(self):
        sys.path.insert(0, APP)
        import entity
        self.entity = entity
        self.ent = entity.load(os.path.join(APP, "entities", "pallasio.md"))

    def test_campi(self):
        e = self.ent
        self.assertEqual(e["name"], "Pallasio")
        self.assertFalse(self.entity.quid_missing(e))
        self.assertIn("sgabuzzino", e["quid"])
        self.assertIn("zombi", e["character"])         # il sottotitolo resta nel carattere
        self.assertIn("Non insulta", e["never"])
        self.assertEqual(e["voice_name"], "it_IT-riccardo-x_low")
        self.assertAlmostEqual(e["speed"], 0.9)

    def test_prompt(self):
        p = self.entity.system_prompt(self.ent, "it", 60)
        self.assertTrue(p.startswith("Sei Pallasio."))
        self.assertLess(p.index("sgabuzzino"), p.index("Carattere"))   # il quid per primo
        self.assertIn("maiali", p)
        self.assertIn("Regole del parlato", p)


def load_window():
    spec = importlib.util.spec_from_file_location("ruscapallas_window", os.path.join(APP, "ruscapallas.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@unittest.skipUnless(HAVE_GI, "serve PyGObject")
class TestFinestra(unittest.TestCase):
    def setUp(self):
        self.mod = load_window()
        self.tmp = tempfile.mkdtemp()
        self.mod.CONFIG_DIR = self.tmp
        self.mod.CONFIG_FILE = os.path.join(self.tmp, "settings.json")

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_conserva_le_chiavi_altrui(self):
        _json(self.mod.CONFIG_FILE, {"gpu_device": "NVIDIA", "size": "small"})
        cfg = self.mod.load_settings()
        self.assertEqual(cfg["size"], "small")
        self.assertEqual(cfg["jumps"], "sometimes")          # predefinito
        cfg["jumps"] = "often"
        self.assertTrue(self.mod.save_settings(cfg))
        saved = _json(self.mod.CONFIG_FILE)
        self.assertEqual(saved["gpu_device"], "NVIDIA")
        self.assertEqual(saved["jumps"], "often")

    def test_valori_che_capisce_l_estensione(self):
        js = _read(os.path.join(APP, "extension", "pallasio.js"))
        for v in self.mod.SIZES + self.mod.JUMPS:
            self.assertIn(f"{v}:", js)
        self.assertIn("idle_reading", js)

    def test_valori_che_capisce_il_servizio(self):
        svc = _read(os.path.join(APP, "ruscapallas-service.py"))
        for key in ("listen_window", "max_words", "emotions", "vosk_model", "model", "voice", "speed", "gpu"):
            self.assertIn(f'"{key}"', svc)

    def test_stringhe_della_finestra(self):
        src = _read(os.path.join(APP, "ruscapallas.py"))
        it = _json(os.path.join(APP, "lang", "it.json"))
        import re
        keys = set(re.findall(r'_\("([a-z_0-9]+)"', src))
        keys |= {f"size_{v}" for v in self.mod.SIZES} | {f"jumps_{v}" for v in self.mod.JUMPS}
        keys |= {f"words_{v}" for v in self.mod.WORDS} | {f"theme_{v}" for v in self.mod.THEMES}
        self.assertEqual(sorted(k for k in keys if k not in it), [])

    def test_nomi_dbus_separati(self):
        """La finestra (GApplication) prende l'App ID sul bus: il servizio deve
        avere un nome suo, o al clic sull'icona la finestra non si apre."""
        svc = load_service()
        self.assertNotEqual(svc.BUS_NAME, self.mod.APP_ID)
        self.assertEqual(self.mod.SERVICE_NAME, svc.BUS_NAME)
        self.assertEqual(self.mod.SERVICE_PATH, svc.OBJECT_PATH)
        js = _read(os.path.join(APP, "extension", "pallasio.js"))
        self.assertIn(f"const SERVICE_NAME = '{svc.BUS_NAME}';", js)
        self.assertIn(f"const SERVICE_PATH = '{svc.OBJECT_PATH}';", js)
        self.assertIn(f'<interface name="{svc.INTERFACE}">', js)
        self.assertIn('DIALOG="org.ruscalinux.RuscaPallas.Dialog"', _read(os.path.join(APP, "make-deb.sh")))

    def test_version_senza_finestra(self):
        r = subprocess.run([sys.executable, os.path.join(APP, "ruscapallas.py"), "--version"],
                           capture_output=True, text=True, timeout=60)
        self.assertEqual(r.stdout.strip(), "RuscaPallas 1.99.3")


class FakeConv:
    def __init__(self):
        self.state = "listening"
        self.paused = False
        self.calls = []

    def set_paused(self, p):
        self.paused = p
        self.calls.append(p)

    def quit(self, timeout=5.0):
        return True


class FakeSpeaker:
    def level_at(self, t):
        return 0.05, "A"

    def close(self):
        pass


class FakeEngine:
    def __init__(self, *a, **k):
        self.stopped = False

    def stop(self, wait=False):
        self.stopped = True


@unittest.skipUnless(HAVE_GI, "serve PyGObject")
class TestServizio(unittest.TestCase):
    def setUp(self):
        self.mod = load_service()
        self.tmp = tempfile.mkdtemp()
        self.mod.CONFIG_FILE = os.path.join(self.tmp, "pallas.json")
        self.mod.LISSE_CONFIG = os.path.join(self.tmp, "lisse.json")
        self.mod.DATA_DIR = os.path.join(self.tmp, "data")
        self.mod.ENTITY_USER = os.path.join(self.tmp, "data", "pallasio.md")
        self.mod.eng.Engine = FakeEngine
        self.mod._log = lambda *a: None                       # niente messaggi durante i test
        self.sent = []
        self.svc = self.mod.Service(emit=lambda name, sig, *args: self.sent.append((name, args)))

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def signals(self, name):
        return [args for n, args in self.sent if n == name]

    def test_impostazioni_di_ruscallisse_poi_le_sue(self):
        _json(self.mod.LISSE_CONFIG, {"model": "/m/a.gguf", "voice": "/v/paola.onnx", "max_words": 80})
        _json(self.mod.CONFIG_FILE, {"voice": "/v/riccardo.onnx", "model": ""})
        cfg = self.mod.load_settings()
        self.assertEqual(cfg["model"], "/m/a.gguf")          # vuoto nelle sue: vale RuscaLLisse
        self.assertEqual(cfg["voice"], "/v/riccardo.onnx")   # le sue vincono
        self.assertEqual(cfg["max_words"], 80)
        self.assertTrue(cfg["emotions"])

    def test_voce_scelta_qui_vince_sulla_personalita(self):
        mod = self.mod
        mod.vosk.find_models = lambda: ["/vosk/it"]
        mod.vosk.model_language = lambda p: "it"
        mod.eng.find_models = lambda extra_dirs=(): ["/m/a.gguf"]
        mod.piper.find_voices = lambda: ["/v/it_IT-paola-medium.onnx", "/v/it_IT-riccardo-x_low.onnx"]
        ent = {"voice_name": "it_IT-riccardo-x_low"}
        _json(mod.LISSE_CONFIG, {"voice": "/v/it_IT-paola-medium.onnx"})
        self.assertEqual(mod.choose_pieces(mod.load_settings(), ent)[2], "/v/it_IT-riccardo-x_low.onnx")
        _json(mod.CONFIG_FILE, {"voice": "/v/it_IT-paola-medium.onnx", "speed": 1.1})
        cfg = mod.load_settings()
        self.assertEqual(mod.choose_pieces(cfg, ent)[2], "/v/it_IT-paola-medium.onnx")
        self.assertEqual(cfg["own_speed"], 1.1)

    def test_ascolto_dalla_finestra(self):
        _json(self.mod.CONFIG_FILE, {"listen_window": 15})
        self.assertEqual(self.mod.load_settings()["listen_window"], 15)
        _json(self.mod.CONFIG_FILE, {"listen_window": "boh"})
        self.assertEqual(self.mod.load_settings()["listen_window"], self.mod.LISTEN_WINDOW)
        _json(self.mod.CONFIG_FILE, {"listen_window": 999})
        self.assertEqual(self.mod.load_settings()["listen_window"], 60)

    def test_personalita_copiata_una_volta(self):
        path = self.mod.ensure_entity()
        self.assertEqual(path, self.mod.ENTITY_USER)
        with open(path, "a", encoding="utf-8") as f:
            f.write("\nmodifica dell'utente\n")
        self.mod.ensure_entity()
        self.assertIn("modifica dell'utente", _read(path))

    def test_motori_mancanti(self):
        self.mod.missing_engines = lambda: ["ruscavosk-engine", "pipewire-bin"]
        self.svc.talk()
        self.assertEqual(self.signals("Error"), [("err_engines", "ruscavosk-engine, pipewire-bin")])
        self.assertEqual(self.svc.state, "idle")
        self.assertFalse(self.svc.loading)

    def test_pezzi_mancanti(self):
        self.mod.missing_engines = lambda: []
        self.mod.choose_pieces = lambda cfg, ent: ("/vosk", None, None)
        self.svc.talk()
        self.assertEqual(self.signals("Error"), [("err_missing", "piece_think,piece_speak")])

    def test_stati_della_conversazione(self):
        self.svc._on_state("listening")
        self.svc._on_state("thinking")
        self.svc._on_state("paused")
        self.assertEqual(self.signals("State"), [("listening",), ("thinking",), ("idle",)])

    def test_clic_riapre_le_orecchie(self):
        conv = self.svc.conv = FakeConv()
        conv.paused = True
        self.svc.talk()
        self.assertEqual(conv.calls, [False])
        self.assertTrue(self.svc._window_id)

    def test_ascolto_a_tempo(self):
        conv = self.svc.conv = FakeConv()
        self.svc.state = "listening"
        self.svc.last_voice = time.monotonic()
        self.assertTrue(self.svc._check_listening())          # appena cliccato: ascolta
        self.svc._on_level(0.5)                               # la persona parla
        self.svc.last_voice -= self.mod.LISTEN_WINDOW + 1     # poi silenzio troppo lungo
        self.assertFalse(self.svc._check_listening())
        self.assertEqual(conv.calls, [True])
        self.assertEqual(self.signals("State")[-1], ("idle",))

    def test_rumore_non_tiene_aperto(self):
        self.svc.last_voice = 0.0
        self.svc._on_level(self.mod.VOICE_LEVEL / 2)
        self.assertEqual(self.svc.last_voice, 0.0)

    def test_bocca_mentre_parla(self):
        self.svc.speaker = FakeSpeaker()
        self.svc._set_state("speaking")
        self.assertTrue(self.svc._mouth_id)
        self.assertTrue(self.svc._send_mouth())
        self.assertAlmostEqual(self.signals("Mouth")[-1][0], 0.4)
        self.svc._set_state("listening")
        self.assertEqual(self.svc._mouth_id, 0)
        self.assertEqual(self.signals("Mouth")[-1], (0.0,))     # bocca chiusa

    def test_emozioni(self):
        self.svc._on_sentence("divertita")
        self.svc._on_sentence(None)
        self.assertEqual(self.signals("Emotion"), [("divertita",)])

    def test_zitto(self):
        conv = self.svc.conv = FakeConv()
        self.svc.state = "speaking"
        self.svc.stop()
        self.assertEqual(conv.calls, [True])
        self.assertEqual(self.svc.state, "idle")
        self.assertFalse(self.svc.want_listen)

    def test_esce_dopo_inattivita(self):
        quit_called = []
        self.svc.quit = lambda: quit_called.append(True)
        self.svc.last_activity = time.monotonic() - self.mod.IDLE_EXIT - 1
        self.assertFalse(self.svc._check_idle())
        self.assertEqual(quit_called, [True])

    def test_non_esce_mentre_conversa(self):
        self.svc.state = "listening"
        self.svc.last_activity = time.monotonic() - self.mod.IDLE_EXIT - 1
        self.assertTrue(self.svc._check_idle())

    def test_niente_rete(self):
        """Il servizio non apre connessioni da sé: il modello è su 127.0.0.1
        tramite rusca_engine, come in RuscaLLisse."""
        import ast
        tree = ast.parse(_read(os.path.join(APP, "ruscapallas-service.py")))
        names = {a.name.split(".")[0] for n in ast.walk(tree) if isinstance(n, (ast.Import, ast.ImportFrom))
                 for a in n.names}
        mods = {n.module.split(".")[0] for n in ast.walk(tree) if isinstance(n, ast.ImportFrom) and n.module}
        self.assertFalse((names | mods) & {"socket", "http", "urllib", "requests", "ssl"})


GJS_TEST = r"""
import {parsePath, draw, drawBubble, BOX_W, BOX_H, BUBBLE_W, BUBBLE_H} from '%(ext)s/figure.js';
import {Animator, MODES, EMOTIONS, MAGIC_TIME} from '%(ext)s/motion.js';
import {World} from '%(ext)s/world.js';
import Cairo from 'cairo';
const fail = m => { print('FAIL ' + m); imports.system.exit(1); };
// percorsi: relativi, quadratiche e T diventano comandi assoluti
const ops = parsePath('M10 10 l5 0 q5 5 10 0 t10 0 h-3 v4 z');
if (ops[1][1] !== 15 || ops[2][0] !== 'C' || ops[2][5] !== 25 || ops[4][1] !== 32 || ops[5][2] !== 14)
    fail('parsePath ' + JSON.stringify(ops));
// ogni stato e ogni emozione si disegna senza errori
const surf = new Cairo.ImageSurface(Cairo.Format.ARGB32, BOX_W, BOX_H);
const cr = new Cairo.Context(surf);
for (const mode of MODES) for (const emo of [null, ...EMOTIONS]) {
    const a = new Animator({random: () => 0.5});
    a.setMode(mode); if (emo) a.setEmotion(emo); a.setMouth(0.7); a.moving = mode === 'walk'; a.roll();
    for (let i = 0; i < 40; i++) { const m = a.step(1 / 30); draw(cr, m); }
}
for (const icon of ['ear', 'dots', 'waves', 'hourglass']) drawBubble(cr, icon, true, 3);
// la magia: appare dal nulla e finisce, sparisce nel nulla e resta sparito
const mg = new Animator(); mg.startMagic('appear');
for (let i = 0; i < 120; i++) draw(cr, mg.step(1 / 60));
if (mg.magic !== null || mg.inMagic) fail('l\'apparizione non finisce');
const len = mg.startMagic('vanish'); if (len !== MAGIC_TIME) fail('durata della magia');
for (let i = 0; i < 100; i++) draw(cr, mg.step(1 / 60));
if (!mg.gone || mg.inMagic) fail('non sparisce del tutto');
const rm = new Animator({reduceMotion: true}); if (rm.startMagic('appear') >= MAGIC_TIME) fail('magia lunga con le animazioni ridotte');
draw(cr, rm.step(0.1));
// il tomo: chiuso camminando, aperto leggendo
const a = new Animator(); a.setMode('think'); let m; for (let i = 0; i < 120; i++) m = a.step(1 / 60);
if (m.op.open < 0.95) fail('il tomo non si apre: ' + m.op.open);
a.setMode('walk'); for (let i = 0; i < 120; i++) m = a.step(1 / 60);
if (m.op.open > 0.05) fail('il tomo non si chiude');
// animazioni ridotte: niente passi né coda che dondola
const r = new Animator({reduceMotion: true}); r.moving = true;
const m1 = r.step(0.3), m2 = r.step(0.3);
if (m1.tr.legL !== m2.tr.legL || m1.d.tail !== m2.d.tail) fail('si muove con le animazioni ridotte');
// salti: sale su una finestra bassa, la segue, cade quando sparisce
let seed = 7; const rnd = () => (seed = seed * 16807 %% 2147483647) / 2147483647;
const area = {x: 0, y: 32, width: 1920, height: 1048};
let wins = [{id: 3, x: 600, y: 420, width: 700, height: 400}];
const w = new World(169, 195, 190, {random: rnd});
let up = false;
for (let t = 0; t < 300 && !up; t += 1 / 60) { w.step(1 / 60, area, wins); up = w.platform === 3; }
if (!up || w.feetY !== 420) fail('non sale sulla finestra');
wins[0].y = 470; w.step(1 / 60, area, wins); if (w.feetY !== 470) fail('non segue la finestra');
wins = []; for (let i = 0; i < 240; i++) w.step(1 / 60, area, wins);
if (w.platform !== null || w.feetY !== 1080) fail('non cade a terra');
// una finestra troppo in alto non è un posto dove salire
if (new World(169, 195, 190).candidates(area, [{id: 1, x: 0, y: 60, width: 800, height: 300}]).length)
    fail('sale dove non c\'è spazio sopra');
// «mai»: non sceglie finestre
const nv = new World(169, 195, 190, {random: rnd}); nv.jumpEvery = null;
const lw = [{id: 4, x: 600, y: 420, width: 700, height: 400}];
for (let t = 0; t < 200; t += 1 / 30) nv.step(1 / 30, area, lw);
if (nv.platform !== null || nv.target !== null || nv.airborne) fail('salta anche con «mai»');
// più grande o più piccolo: il centro resta dov'è
const rz = new World(169, 195, 190); rz.step(0.1, area, []); const c0 = rz.center;
rz.resize(208, 240, 234); if (Math.abs(rz.center - c0) > 0.01) fail('ridimensionato si sposta');
// fermo se non può camminare
const s = new World(169, 195, 190); s.step(0.1, area, []); const x0 = s.x;
for (let i = 0; i < 30; i++) s.step(0.1, area, [], false);
if (s.x !== x0) fail('cammina quando non dovrebbe');
// trascinato e lasciato sopra una finestra: ci atterra
const d = new World(169, 195, 190); d.step(0.1, area, []);
const win = {id: 9, x: 500, y: 600, width: 600, height: 300};
d.drag(650, 500); d.drop(area, [win]);
for (let i = 0; i < 120; i++) d.step(1 / 60, area, [win], false);
if (d.platform !== 9) fail('lasciato sopra la finestra non ci atterra');
print('ok');
"""


@unittest.skipUnless(shutil.which("gjs"), "serve gjs")
class TestEstensione(unittest.TestCase):
    def test_disegno_animazione_salti(self):
        ext = "file://" + os.path.abspath(os.path.join(APP, "extension"))
        with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False) as f:
            f.write(GJS_TEST % {"ext": ext})
            path = f.name
        try:
            r = subprocess.run(["gjs", "-m", path], capture_output=True, text=True, timeout=120)
        finally:
            os.unlink(path)
        self.assertEqual(r.stdout.strip().splitlines()[-1:], ["ok"], r.stdout + r.stderr)


if __name__ == "__main__":
    unittest.main()
