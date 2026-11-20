# RuscaPinball — rp_table.py — 1.99.3 — GPL-3.0-or-later
# Copyright (C) 2026 Nunzio Curcuruto <info@ruscalinux.org>
#
# Il tavolo «Amethyst»: tutte le coordinate in px, sul piano del tavolo visto
# dall'alto (480 × 720). La vista in prospettiva sta in rp_view.py.
# Disposizione ispirata ai flipper per home computer degli anni '80: quattro
# corsie in alto, tre bumper, la trappola del bonus a sinistra, l'anello delle
# lampade del bonus al centro. Tavolo originale di RuscaLinux; modulo puro,
# senza pygame.

import math

from rp_physics import BALL_R, Circle, Flipper, Segment, World

WIDTH, HEIGHT = 480, 720          # piano del tavolo
LEFT, RIGHT = 20, 430             # pareti del campo (la corsia è a destra)
LANE_X0, LANE_X1 = 430, 465       # corsia di lancio
LANE_FLOOR = 700                  # piano del pistone a riposo
PLUNGER_TRAVEL = 28               # corsa del pistone in px
BALL_START = ((LANE_X0 + LANE_X1) / 2, LANE_FLOOR - BALL_R - 1)
DRAIN_Y = HEIGHT + 15

ARC_C = ((LEFT + LANE_X1) / 2, 200.0)   # arco superiore (mezza ellisse)
ARC_R = ((LANE_X1 - LEFT) / 2, 180.0)

# ── elementi attivi ─────────────────────────────────────────────────────────
BUMPERS = [(160, 238), (300, 238), (230, 318)]
BUMPER_R = 24
LANE_POSTS = [120, 170, 220, 270, 320]   # paletti delle quattro corsie in alto
TOP_LANES = [145, 195, 245, 295]         # centri delle corsie
TOP_LANE_Y = (72, 112)
LANE_LAMP_Y = 135
DROP_TARGETS = [(300, 325), (332, 357), (364, 389)]   # banco a sinistra
DROP_X = 27
RUSCA = "RUSCA"
RUSCA_X = 423
RUSCA_Y = [280 + i * 30 for i in range(5)]
RUSCA_LEN = 22

# Trappola del bonus: una buca in alto a sinistra. La pallina che ci passa
# sopra abbastanza piano resta presa, poi viene ributtata verso i bumper.
TRAP = (44, 250)
TRAP_R = 11                      # raggio di cattura
TRAP_MAX_SPEED = 650.0           # oltre questa velocità la pallina salta la buca
TRAP_HOLD = 1.2                  # secondi di attesa prima del calcio
TRAP_KICK = (430.0, -160.0)      # velocità del calcio, verso i bumper
TRAP_ARROW = (80, 284)           # freccia che indica la trappola

# Anello del bonus: nove lampade (1-9) attorno alle decine (10, 20, 30) e
# alla lampada SPECIAL, come nei tavoli elettromeccanici.
RING_C = (225, 485)
RING_R = (84, 58)
LAMP_R = 12
BONUS_LAMPS = [(RING_C[0] + RING_R[0] * math.cos(math.radians(a)),
                RING_C[1] + RING_R[1] * math.sin(math.radians(a)))
               for a in range(-70, 290, 40)]            # 1 in alto a destra, poi in senso orario
TENS_LAMPS = [(187, 470), (225, 470), (263, 470)]       # 10, 20, 30
SPECIAL_LAMP = (225, 503, 70, 18)                       # centro, larghezza, altezza
BONUS_MAX = 39
SAVE_LAMP = (225, 600)
TITLE_Y = 380

SLING_L = [(60, 455), (60, 535), (122, 578)]
SLING_R = [(2 * 225 - x, y) for x, y in SLING_L]

FLIP_L = (150, 640)
FLIP_R = (300, 640)
FLIP_LEN = 66
FLIP_REST = math.radians(30)
FLIP_UP = math.radians(-30)


def arc_points(n=48):
    cx, cy = ARC_C
    rx, ry = ARC_R
    return [(cx + rx * math.cos(math.pi + math.pi * i / n),
             cy + ry * math.sin(math.pi + math.pi * i / n)) for i in range(n + 1)]


def guide_end(x0, pivot, r0=11.0, thick=2.0):
    """Fine della guida: il punto del perno tangente alla guida, dal lato del campo."""
    dx, dy = pivot[0] - x0, pivot[1] - 540
    ln = math.hypot(dx, dy)
    nx, ny = dy / ln, -dx / ln            # normale verso l'alto
    if ny > 0:
        nx, ny = -nx, -ny
    return (pivot[0] + nx * (r0 - thick), pivot[1] + ny * (r0 - thick))


def bonus_lamps_on(bonus):
    """Lampade accese per un bonus da 0 a BONUS_MAX: (unità 1-9, decine 1-3)."""
    bonus = max(0, min(BONUS_MAX, bonus))
    return bonus % 10, bonus // 10


def wall_list():
    """Pareti fisse (a, b) da disegnare in rilievo: arco, pareti, guide."""
    pts = arc_points()
    walls = list(zip(pts, pts[1:]))
    walls += [((LEFT, ARC_C[1]), (LEFT, 540)),
              ((LANE_X1, ARC_C[1]), (LANE_X1, HEIGHT)),
              ((LANE_X0, 232), (LANE_X0, HEIGHT)),
              ((LEFT, 540), guide_end(LEFT, FLIP_L)),
              ((RIGHT, 540), guide_end(RIGHT, FLIP_R))]
    return walls


class Table:
    """Il tavolo con il suo mondo fisico e i riferimenti agli elementi attivi."""

    def __init__(self):
        w = self.world = World()
        S = w.segments

        def wall(a, b, **kw):
            seg = Segment(a, b, **kw)
            S.append(seg)
            return seg

        # arco superiore e pareti esterne
        pts = arc_points()
        for a, b in zip(pts, pts[1:]):
            wall(a, b, e=0.4, friction=0.005)
        wall((LEFT, ARC_C[1]), (LEFT, 540))
        wall((LANE_X1, ARC_C[1]), (LANE_X1, HEIGHT + 40))
        # corsia di lancio: parete interna, cancelletto a senso unico, pistone
        wall((LANE_X0, 232), (LANE_X0, LANE_FLOOR + PLUNGER_TRAVEL + 4))
        wall((LANE_X0, 232), (LANE_X1, 200), one_way=(-32, -35), e=0.3)
        self.plunger = wall((LANE_X0, LANE_FLOOR), (LANE_X1, LANE_FLOOR), e=0.1)
        # guide verso i flipper
        # finiscono sulla sommità del perno, così la pallina scivola sul
        # flipper senza fermarsi nell'angolo
        wall((LEFT, 540), guide_end(LEFT, FLIP_L), e=0.3)
        wall((RIGHT, 540), guide_end(RIGHT, FLIP_R), e=0.3)
        # paletti delle corsie in alto
        for x in LANE_POSTS:
            wall((x, TOP_LANE_Y[0]), (x, TOP_LANE_Y[1]), thick=4, e=0.5)
        # slingshot: due lati fermi e il lato che scatta
        self.slings = []
        for (a, b, c), tag in ((SLING_L, ("sling", 0)), (SLING_R, ("sling", 1))):
            wall(a, b, thick=3, e=0.4)
            wall(b, c, thick=3, e=0.4)
            self.slings.append(wall(a, c, thick=3, e=0.5, kick=520, tag=tag))
        # banco di bersagli abbattibili
        self.drops = [wall((DROP_X, y0), (DROP_X, y1), thick=3, e=0.35,
                           tag=("drop", i)) for i, (y0, y1) in enumerate(DROP_TARGETS)]
        # bersagli R-U-S-C-A
        self.rusca = [wall((RUSCA_X, y), (RUSCA_X, y + RUSCA_LEN), thick=3, e=0.4,
                           tag=("rusca", i)) for i, y in enumerate(RUSCA_Y)]
        # bumper
        self.bumpers = [Circle(x, y, BUMPER_R, e=0.4, kick=640, tag=("bumper", i))
                        for i, (x, y) in enumerate(BUMPERS)]
        w.circles.extend(self.bumpers)
        # flipper
        self.left = Flipper(*FLIP_L, FLIP_LEN, FLIP_REST, FLIP_UP, tag="flipper")
        self.right = Flipper(*FLIP_R, FLIP_LEN, math.pi - FLIP_REST,
                             math.pi - FLIP_UP, tag="flipper")
        w.flippers.extend([self.left, self.right])

    def set_plunger(self, pull):
        """pull da 0 (a riposo) a 1 (tutto tirato)."""
        y = LANE_FLOOR + PLUNGER_TRAVEL * pull
        self.plunger.move((LANE_X0, y), (LANE_X1, y))

    @staticmethod
    def in_lane(ball):
        return ball.x > LANE_X0 and ball.y > 225

    @staticmethod
    def on_plunger(ball):
        return ball.x > LANE_X0 and ball.y > LANE_FLOOR - 40

    @staticmethod
    def in_trap(ball):
        """La pallina cade nella trappola del bonus?"""
        return (math.hypot(ball.x - TRAP[0], ball.y - TRAP[1]) < TRAP_R
                and ball.speed < TRAP_MAX_SPEED)

    @staticmethod
    def kick_from_trap(ball, jitter=0.0):
        """Rimette la pallina al centro della buca e la ributta in campo."""
        ball.x, ball.y = float(TRAP[0]), float(TRAP[1])
        ball.vx = TRAP_KICK[0] + jitter
        ball.vy = TRAP_KICK[1] - abs(jitter) * 0.3
