# RuscaPinball — test — GPL-3.0-or-later
# python3 -m unittest tests/test_ruscapinball.py   (dalla radice del repository)
# Le prove della vista e della partita usano pygame con SDL_VIDEODRIVER=dummy;
# senza pygame si saltano.

import json
import math
import os
import random
import sys
import tempfile
import unittest

ROOT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                    "apps", "ruscapinball")
sys.path.insert(0, ROOT)
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")

try:
    import pygame
except ImportError:
    pygame = None

import rp_table as T  # noqa: E402
from rp_physics import Ball  # noqa: E402

DT = 1 / 120


class Auto:
    """Giocatore automatico imperfetto: a volte sbaglia, così la pallina cade."""

    def __init__(self, miss=0.25):
        self.t, self.miss = {}, miss

    def __call__(self, table, ball):
        for f in (table.left, table.right):
            hold, cool = self.t.get(id(f), (0, 0))
            hold -= DT
            cool -= DT
            dx, dy = ball.x - f.px, ball.y - f.py
            along = dx if f is table.left else -dx
            near = math.hypot(dx, dy) < T.FLIP_LEN + 12 and -35 < dy < 30 and along > 10
            if near and cool <= 0 and hold <= 0 and ball.vy > -30:
                cool = 0.45
                if random.random() > self.miss:
                    hold = 0.18
            f.pressed = hold > 0
            self.t[id(f)] = (hold, cool)


def launch(table, ball, power):
    for _ in range(60):
        table.world.step(ball, DT, 5)
    ball.vy = -(500 + 1700 * power)


class PhysicsTest(unittest.TestCase):
    def test_ball_never_escapes_or_sticks(self):
        drains = 0
        for seed in range(24):
            random.seed(seed)
            table, ball, auto = T.Table(), Ball(*T.BALL_START), Auto()
            launch(table, ball, random.uniform(0.55, 1.0))
            still = 0.0
            for _ in range(int(90 / DT)):
                auto(table, ball)
                table.world.step(ball, DT, 5)
                self.assertFalse(math.isnan(ball.x) or math.isnan(ball.y))
                self.assertTrue(T.LEFT - 2 < ball.x < T.LANE_X1 + 2, (seed, ball.x, ball.y))
                self.assertGreater(ball.y, 0, seed)
                if ball.y > T.DRAIN_Y:
                    drains += 1
                    break
                if ball.speed < 6 and not T.Table.in_lane(ball) \
                        and not (table.left.pressed or table.right.pressed):
                    still += DT
                    self.assertLess(still, 2.5, f"pallina ferma: seed {seed} a {ball.x:.0f},{ball.y:.0f}")
                else:
                    still = 0.0
        self.assertGreater(drains, 6)   # con errori del giocatore la pallina deve cadere

    def test_launch_reaches_playfield(self):
        for power in (0.5, 0.75, 1.0):
            table, ball = T.Table(), Ball(*T.BALL_START)
            launch(table, ball, power)
            for _ in range(int(3 / DT)):
                table.world.step(ball, DT, 5)
                if ball.x < T.LANE_X0 - 20:
                    break
            self.assertLess(ball.x, T.LANE_X0, f"il lancio a {power} non esce dalla corsia")

    def test_gate_blocks_return_to_lane(self):
        table = T.Table()
        ball = Ball(445, 170, 0, 300)    # scende lungo la parete destra
        for _ in range(int(1.5 / DT)):
            table.world.step(ball, DT, 5)
        self.assertFalse(T.Table.in_lane(ball) and ball.y > 300)

    def test_no_flippers_drains(self):
        table, ball = T.Table(), Ball(225, 520, 0, 0)
        for _ in range(int(5 / DT)):
            table.world.step(ball, DT, 5)
            if ball.y > T.DRAIN_Y:
                break
        self.assertGreater(ball.y, T.DRAIN_Y)

    def test_flipper_shoots_ball_up(self):
        table = T.Table()
        ball = Ball(195, 640, 0, 0)       # pallina ferma sul flipper sinistro
        for _ in range(30):
            table.world.step(ball, DT, 5)
        table.left.pressed = True
        best = 0.0
        for _ in range(20):
            table.world.step(ball, DT, 5)
            best = min(best, ball.vy)
        self.assertLess(best, -700)


class AmethystTableTest(unittest.TestCase):
    def test_trap_catches_slow_ball_and_kicks_it_into_play(self):
        ball = Ball(T.TRAP[0] + 3, T.TRAP[1] + 2, 0, 400)
        self.assertTrue(T.Table.in_trap(ball))
        fast = Ball(*T.TRAP, 0, T.TRAP_MAX_SPEED + 100)
        self.assertFalse(T.Table.in_trap(fast))
        table = T.Table()
        T.Table.kick_from_trap(ball)
        for _ in range(int(1.0 / DT)):
            table.world.step(ball, DT, 5)
        self.assertGreater(ball.x, T.TRAP[0] + 40, "il calcio deve portare la pallina in campo")
        self.assertFalse(T.Table.in_trap(ball))

    def test_trap_is_reachable_but_not_too_easy(self):
        """In gioco la pallina finisce nella trappola ogni tanto, non di continuo."""
        caught, seconds = 0, 0.0
        for seed in range(6):
            random.seed(100 + seed)
            table, ball, auto = T.Table(), Ball(*T.BALL_START), Auto(miss=0.0)
            launch(table, ball, random.uniform(0.6, 1.0))
            cool = 0.0
            for _ in range(int(60 / DT)):
                auto(table, ball)
                table.world.step(ball, DT, 5)
                seconds += DT
                cool = max(0.0, cool - DT)
                if not cool and T.Table.in_trap(ball):
                    caught += 1
                    T.Table.kick_from_trap(ball, random.uniform(-60, 60))
                    cool = 0.6
                if ball.y > T.DRAIN_Y:
                    break
        self.assertGreater(caught, 0)
        self.assertLess(caught / seconds, 1 / 8, "trappola troppo facile")

    def test_bonus_lamps(self):
        self.assertEqual(T.bonus_lamps_on(0), (0, 0))
        self.assertEqual(T.bonus_lamps_on(7), (7, 0))
        self.assertEqual(T.bonus_lamps_on(20), (0, 2))
        self.assertEqual(T.bonus_lamps_on(39), (9, 3))
        self.assertEqual(T.bonus_lamps_on(99), (9, 3))
        self.assertEqual(len(T.BONUS_LAMPS), 9)
        # la lampada 1 è in alto a destra, la 5 in basso al centro
        self.assertGreater(T.BONUS_LAMPS[0][0], T.RING_C[0])
        self.assertLess(T.BONUS_LAMPS[0][1], T.RING_C[1])
        self.assertAlmostEqual(T.BONUS_LAMPS[4][0], T.RING_C[0], delta=1)


@unittest.skipIf(pygame is None, "serve pygame")
class ViewTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        pygame.init()
        pygame.display.set_mode((800, 600))
        import rp_view as V
        cls.V = V

    def test_projection_round_trip(self):
        V = self.V
        for y in (-20, 0, 200, 500, 720):
            sx, sy = V.project(240, y)
            self.assertAlmostEqual(sx, V.CX)
            self.assertAlmostEqual(V.unproject_row(sy), y, places=6)
        # il fondo del tavolo è più stretto del bordo vicino al giocatore
        far = V.project(500, -20)[0] - V.project(-20, -20)[0]
        near = V.project(500, 720)[0] - V.project(-20, 720)[0]
        self.assertAlmostEqual(near / far, V.depth(-20), places=6)
        # il tavolo sta dentro lo schermo, con lo spazio per i punteggi
        self.assertGreater(V.project(-20, -20)[1], 30)
        self.assertLess(V.SB + V.FACE, V.SCREEN_H - 50)

    def test_lit_elements_do_not_spill(self):
        """Il rettangolo di un elemento acceso non deve accendere i vicini."""
        V = self.V
        fonts = {k: V.font(n) for k, n in (("table_title", 34), ("table_small", 13),
                                           ("lamp", 13), ("lamp_small", 11), ("letter", 15))}
        layers = V.StaticLayers(fonts)
        base, lit = pygame.PixelArray(layers.base), pygame.PixelArray(layers.lit)
        keys = list(layers.rects)
        for i, a in enumerate(keys):
            ra = layers.rects[a]
            self.assertTrue(pygame.Rect(0, 0, 800, 600).contains(ra), a)
            changed = any(base[x, y] != lit[x, y] for x in range(ra.left, ra.right)
                          for y in range(ra.top, ra.bottom))
            self.assertTrue(changed, f"{a}: acceso e spento sono uguali")
            for b in keys[i + 1:]:
                clip = ra.clip(layers.rects[b])
                for x in range(clip.left, clip.right):
                    for y in range(clip.top, clip.bottom):
                        self.assertEqual(base[x, y], lit[x, y], f"{a} e {b} si toccano")
        del base, lit

    def test_text_colors_contrast(self):
        """Testi dell'HUD sul bordo dello schermo: almeno 4,5:1 (specifiche, 3.11)."""
        V = self.V
        for col in (V.CREMA, V.ROSA_250, V.ROSA_300, V.ROSA_200, V.AMETISTA_300):
            self.assertGreaterEqual(V.contrast(col, V.BORDER), 4.5, col)
            self.assertGreaterEqual(V.contrast(col, V.PRUGNA_750), 4.5, col)
        # testo scuro sulle lampade accese
        self.assertGreaterEqual(V.contrast(V.PRUGNA_900, V.ROSA_250), 4.5)
        # scritte del tavolo (lettere R-U-S-C-A, sottotitolo) sul campo
        for col in (V.CREMA, V.AMETISTA_300):
            self.assertGreaterEqual(V.contrast(col, V.FIELD), 4.5, col)


@unittest.skipIf(pygame is None, "serve pygame")
class GameTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        os.environ["XDG_DATA_HOME"] = os.environ["XDG_CONFIG_HOME"] = self.tmp.name
        import importlib
        import ruscapinball as R
        self.R = importlib.reload(R)
        pygame.init()
        screen = pygame.display.set_mode((R.SCREEN_W, R.SCREEN_H))
        self.g = R.Game(screen, R.I18n(), R.Sounds(False), R.Scores(), R.Settings())
        self.g.start_game()

    def tearDown(self):
        self.tmp.cleanup()

    def test_special_at_the_trap_gives_extra_ball(self):
        g = self.g
        g.advance_bonus(50)
        self.assertEqual(g.bonus, T.BONUS_MAX)
        self.assertTrue(g.special)
        g.ball.x, g.ball.y, g.ball.vx, g.ball.vy = T.TRAP[0], T.TRAP[1], 0, 200
        g.tick(1 / 120)
        self.assertGreater(g.trapped, 0)
        self.assertFalse(g.special)
        self.assertEqual(g.balls_total, self.R.BALLS_PER_GAME + 1)
        self.assertTrue(g.extra_pending())
        self.assertGreaterEqual(g.score, self.R.SPECIAL_POINTS)
        for _ in range(int((T.TRAP_HOLD + 0.1) * 120)):
            g.tick(1 / 120)
        self.assertEqual(g.trapped, 0)
        self.assertGreater(g.ball.vx, 0, "dopo l'attesa la trappola ributta la pallina")

    def test_bonus_counts_down_lamp_by_lamp(self):
        g = self.g
        g.launched = True
        g.advance_bonus(12)
        g.mult = 2
        start = g.score
        g.ball.y = T.DRAIN_Y + 1
        g.tick(1 / 120)
        self.assertIsNotNone(g.counting)
        seen = set()
        for _ in range(120 * 6):
            g.tick(1 / 120)
            seen.add(g.bonus)
            if g.counting is None:
                break
        self.assertEqual(g.score - start, 12 * self.R.BONUS_UNIT * 2)
        self.assertTrue({11, 6, 1, 0} <= seen)
        self.assertEqual(g.ball_num, 2)

    def test_tilt_loses_the_bonus(self):
        g = self.g
        g.advance_bonus(10)
        g.ball.x, g.ball.y = 200, 400
        for _ in range(3):
            g.nudge()
        self.assertTrue(g.tilt)
        self.assertEqual(g.bonus, 0)

    def test_draw_every_state(self):
        g = self.g
        for state in ("attract", "play", "entry", "gameover"):
            g.state = state
            g.gameover_until = g.clock_t + 5
            g.draw()
        g.paused = True
        g.draw()


class DataTest(unittest.TestCase):
    def test_no_network_modules(self):
        """Il gioco non usa la rete (specifiche, sezione 11)."""
        import ast
        banned = {"socket", "http", "urllib", "requests", "ssl", "ftplib", "smtplib"}
        for name in os.listdir(ROOT):
            if not name.endswith(".py"):
                continue
            with open(os.path.join(ROOT, name), encoding="utf-8") as fh:
                tree = ast.parse(fh.read())
            for node in ast.walk(tree):
                mods = []
                if isinstance(node, ast.Import):
                    mods = [a.name for a in node.names]
                elif isinstance(node, ast.ImportFrom) and node.module:
                    mods = [node.module]
                for m in mods:
                    self.assertNotIn(m.split(".")[0], banned, f"{name} importa {m}")

    def test_translations_complete(self):
        def load(code):
            with open(os.path.join(ROOT, "lang", code + ".json"), encoding="utf-8") as fh:
                return json.load(fh)
        it, en = load("it"), load("en")
        self.assertEqual(set(it), set(en))
        self.assertEqual(en["ai_note"], "Design, specifications and testing by the author; "
                         "code written with the assistance of AI tools.")
        self.assertEqual(it["ai_note"], "Progettazione, specifiche e verifica dell’autore; "
                         "codice scritto con l’assistenza di strumenti di intelligenza artificiale.")

    @unittest.skipIf(pygame is None, "serve pygame")
    def test_scores_and_language(self):
        with tempfile.TemporaryDirectory() as tmp:
            os.environ["XDG_DATA_HOME"] = tmp
            os.environ["SDL_VIDEODRIVER"] = "dummy"
            import importlib
            import ruscapinball as R
            R = importlib.reload(R)
            s = R.Scores()
            self.assertTrue(s.qualifies(10001))
            self.assertFalse(s.qualifies(10))
            s.add("ZX", 60000)
            self.assertEqual(R.Scores().table[0], ["ZX", 60000])
            os.environ["LANGUAGE"] = "it_IT:en"
            self.assertEqual(R.I18n().code, "it")
            os.environ["LANGUAGE"] = "de_DE"
            os.environ["LANG"] = "de_DE.UTF-8"
            self.assertEqual(R.I18n().code, "en")
            self.assertEqual(R.I18n()("chiave_inesistente"), "chiave_inesistente")


if __name__ == "__main__":
    unittest.main()
