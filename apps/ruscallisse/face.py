# -*- coding: utf-8 -*-
# face.py — RuscaLinux OS Apps 1.99.3 — GPL-3.0-or-later
#
# Il volto di Ellittica, disegnato con Cairo (specifiche, sezione 1.7.8).
# Personaggio originale: caschetto prugna con la frangia di lato, la ciocca
# destra dietro l'orecchio (e lì la matita), occhiali ovali sottili,
# l'orbita intorno alla testa. Illustrazione vettoriale: chiaroscuri morbidi
# fatti di sfumature, nessuna immagine esterna. All'avvio si materializza:
# scie di luce si raccolgono nella sua sagoma, il volto compare dal basso
# dietro una linea di luce, l'orbita si disegna.
#
#   FaceModel  stato e animazione, senza GTK (si prova da solo)
#   draw()     disegna su un contesto Cairo, senza GTK
#   FaceView   il Gtk.DrawingArea della finestra
import math
import random

STATES = ("idle", "listening", "thinking", "speaking", "paused")

# Forma della bocca per visema: (larghezza, apertura, arrotondamento), da 0 a 1.
MOUTH = {"A": (.70, 1.0, 0.0), "E": (.86, .52, 0.0), "I": (.92, .30, 0.0),
         "O": (.50, .78, .75), "U": (.36, .46, 1.0), "M": (.62, 0.0, 0.0),
         "F": (.74, .16, 0.0), "C": (.66, .34, 0.0), "": (.64, 0.0, 0.0)}
# Espressioni: (sopracciglia, occhi socchiusi, sorriso)
EMOTION = {"sorride": (.3, .35, 1.0), "pensierosa": (.6, .1, .2), "commossa": (1.0, .25, .5),
           "divertita": (.5, .45, 1.3), "perplessa": (.8, 0, 0), "seria": (0, 0, 0)}

APPEAR_TIME = 2.8          # secondi della materializzazione


def _approach(cur, target, k, dt):
    return cur + (target - cur) * min(1.0, k * dt * 60)


class FaceModel:
    """Stato del volto, aggiornato a ogni fotogramma con step()."""

    def __init__(self, reduce_motion=False, seed=None):
        self.state = "idle"
        self.reduce_motion = reduce_motion
        self.t = 0.0
        self.level = 0.0                 # microfono
        self.speech = (0.0, "")          # (ampiezza, visema) dell'audio che suona
        self.emotion = None
        self.emotion_until = 0.0
        self.blink = 0.0
        self.next_blink = 1.8
        self.mouth_w, self.mouth_h, self.mouth_round = .64, 0.0, 0.0
        self.tilt = self.brow = self.squint = self.smile = 0.0
        self.sway = 0.0
        self.gaze = (0.0, 0.0)
        self.saccade = (0.0, 0.0)        # piccoli scatti dello sguardo
        self.next_saccade = 1.0
        self.orbit = 0.0
        self.amp = 0.0
        self.appear = 1.0                # 1: già comparsa
        self._rnd = random.Random(seed)

    def set_state(self, state):
        if state in STATES:
            self.state = state

    def start_appear(self):
        """Fa materializzare il volto dal nulla (con «Animazioni ridotte»
        compare subito)."""
        self.appear = 1.0 if self.reduce_motion else 0.0

    @property
    def orbit_sweep(self):
        if self.appear >= 1:
            return 1.0
        x = min(1.0, max(0.0, (self.appear - .55) / .4))
        return x * x * (3 - 2 * x)

    def set_emotion(self, emotion, seconds=4.0):
        if emotion in EMOTION:
            self.emotion = emotion
            self.emotion_until = self.t + seconds

    def step(self, dt):
        self.t += dt
        if self.appear < 1:
            self.appear = 1.0 if self.reduce_motion else min(1.0, self.appear + dt / APPEAR_TIME)
        t, s, rm = self.t, self.state, self.reduce_motion
        if self.emotion and t > self.emotion_until:
            self.emotion = None
        # sguardo: una direzione per stato, più piccoli scatti come negli occhi veri
        self.next_saccade -= dt
        if self.next_saccade <= 0:
            r = self._rnd
            self.saccade = (0.0, 0.0) if rm else (r.uniform(-1.6, 1.6), r.uniform(-.8, .8))
            self.next_saccade = r.uniform(.6, 2.2)
        if s == "thinking":
            gaze = (3.0 if rm else math.sin(t * .6) * 4 + 3, -5.5)
        elif s == "listening":
            gaze = (0.0, .5)
        elif s == "paused":
            gaze = (0.0, 4.0)
        else:
            gaze = (self.saccade[0], self.saccade[1])
        self.gaze = (_approach(self.gaze[0], gaze[0], .35, dt), _approach(self.gaze[1], gaze[1], .35, dt))
        # testa, sopracciglia, occhi, sorriso
        tilt = {"listening": -.08, "thinking": .045}.get(s, 0.0)
        # a riposo e mentre parla la testa ondeggia appena (uno spostamento,
        # non una rotazione: costa molto meno da disegnare)
        sway = 0.0 if rm or s not in ("idle", "speaking") else math.sin(t * .41) * 1.2 + math.sin(t * 1.13) * .5
        self.sway = _approach(self.sway, sway, .1, dt)
        brow = {"listening": 1.0, "thinking": .6, "speaking": .35 + self.amp * .45}.get(s, .25)
        squint = {"listening": .16, "idle": .05}.get(s, 0.0)
        smile = {"listening": .75, "idle": .55, "speaking": .45}.get(s, .3)
        if self.emotion:
            brow, squint, smile = EMOTION[self.emotion]
        self.tilt = _approach(self.tilt, 0.0 if rm else tilt, .06, dt)
        self.brow = _approach(self.brow, brow, .1, dt)
        self.squint = _approach(self.squint, squint, .08, dt)
        self.smile = _approach(self.smile, smile, .08, dt)
        # palpebre
        self.next_blink -= dt
        if self.next_blink <= 0:
            self.blink = 1.0
            self.next_blink = 2.3 + self._rnd.random() * 2.7
        if self.blink > 0:
            self.blink = max(0.0, self.blink - dt / .16)
        # bocca: visema e ampiezza dell'audio
        amp, vis = self.speech if s == "speaking" else (0.0, "")
        self.amp = _approach(self.amp, min(1.0, amp * 8), .3, dt)
        w, h, rnd = MOUTH.get(vis, MOUTH["C"])
        if s == "speaking" and vis not in ("", "M"):
            h *= max(.4, min(1.15, self.amp * 1.3))
        self.mouth_w = _approach(self.mouth_w, w, .35, dt)
        self.mouth_h = _approach(self.mouth_h, h, .35, dt)
        self.mouth_round = _approach(self.mouth_round, rnd, .3, dt)
        # orbita
        speed = {"thinking": 2.2, "paused": 0.0}.get(s, .45)
        if not rm:
            self.orbit += speed * dt

    @property
    def lid(self):
        b = math.sin(self.blink * math.pi) if self.blink > 0 else 0.0
        return max(b, self.squint)

    @property
    def ring(self):
        if self.state == "listening":
            return .3 + self.level
        if self.state == "speaking":
            return self.amp * .8
        return 0.0


# ── disegno ────────────────────────────────────────────────────────────────
# Spazio di disegno: 400 × 400, scalato sulla finestra. La luce viene da
# sinistra, in alto: ombre a destra e sotto, riflessi rosa dell'orbita sul
# bordo destro dei capelli. Nessun testo è disegnato sul volto.
import cairo  # noqa: E402  (python3-cairo, dipendenza di python3-gi-cairo)

P = {   # palette del volto: RuscaLinux (sezione 4.1) e toni derivati
    "hair": (0x7a, 0x23, 0x57), "hair_dark": (0x4a, 0x12, 0x33), "hair_deep": (0x33, 0x0b, 0x23),
    "hair_hi": (0xb0, 0x52, 0x8a), "hair_shine": (0xe6, 0x9c, 0xc4),
    "skin": (0xfd, 0xf0, 0xf4), "skin_mid": (0xf6, 0xdd, 0xe7), "skin_shade": (0xec, 0xc8, 0xd8),
    "skin_deep": (0xd9, 0xa8, 0xc0), "skin_line": (0xb8, 0x7a, 0x9a),
    "blush": (0xf2, 0x9a, 0xc0), "lip": (0xc9, 0x4f, 0x88), "lip_dark": (0x8e, 0x2a, 0x5e),
    "lip_hi": (0xf0, 0xa6, 0xc8), "mouth": (0x3a, 0x0c, 0x26), "mouth_deep": (0x22, 0x05, 0x16),
    "teeth": (0xff, 0xf9, 0xf6), "teeth_sh": (0xe9, 0xd6, 0xe0), "tongue": (0xd4, 0x62, 0x92),
    "line": (0x2d, 0x0a, 0x1d), "brow": (0x55, 0x16, 0x3d),
    "iris_hi": (0xd9, 0x7f, 0xb0), "iris": (0x8a, 0x2b, 0x5f), "iris_dark": (0x45, 0x0f, 0x2f),
    "white": (0xff, 0xfc, 0xfd), "white_sh": (0xec, 0xd9, 0xe4),
    "cream": (0xff, 0xf7, 0xf0), "cream_sh": (0xee, 0xdc, 0xd8),
    "sweater": (0x8a, 0x2b, 0x5f), "sweater_hi": (0xa0, 0x3a, 0x72), "sweater_dark": (0x5e, 0x1a, 0x41),
    "orbit": (0xf2, 0xa7, 0xc8), "glow": (0xf8, 0xd7, 0xe6), "spark": (0xff, 0xff, 0xff),
    "frame": (0x3a, 0x10, 0x28), "frame_hi": (0x9a, 0x4a, 0x78),
    "wood": (0xec, 0xb5, 0x50), "wood_mid": (0xdb, 0x9c, 0x38), "wood_dark": (0xb8, 0x7c, 0x26),
    "eraser": (0xf5, 0xb8, 0xd3), "ferrule": (0xc9, 0xb8, 0xc2), "lead": (0x3a, 0x10, 0x28),
}
CX, CY = 200.0, 196.0           # centro del volto


def _c(name, a=1.0):
    r, g, b = P[name]
    return (r / 255, g / 255, b / 255, a)


def _src(cr, name, a=1.0):
    cr.set_source_rgba(*_c(name, a))


def _ell(cr, x, y, rx, ry, rot=0.0):
    cr.save()
    cr.translate(x, y)
    cr.rotate(rot)
    cr.scale(max(rx, .1), max(ry, .1))
    cr.new_sub_path()
    cr.arc(0, 0, 1, 0, 2 * math.pi)
    cr.restore()


def _radial(x, y, r0, r1, *stops, fx=None, fy=None):
    g = cairo.RadialGradient(x if fx is None else fx, y if fy is None else fy, r0, x, y, r1)
    if len(stops) == 2 and len(stops[0]) == 4:
        stops = ((0, stops[0]), (1, stops[1]))
    for pos, col in stops:
        g.add_color_stop_rgba(pos, *col)
    return g


def _linear(x0, y0, x1, y1, *stops):
    g = cairo.LinearGradient(x0, y0, x1, y1)
    for pos, col in stops:
        g.add_color_stop_rgba(pos, *col)
    return g


def _smooth(x):
    x = min(1.0, max(0.0, x))
    return x * x * (3 - 2 * x)


def _soft_fill(cr, path, name, alpha, spread, steps=14, dx=0.0, dy=0.0):
    """Ombra morbida: la stessa sagoma ripetuta, spostata e sempre più
    trasparente (Cairo non ha la sfocatura)."""
    for i in range(steps, 0, -1):
        k = i / steps
        cr.save()
        cr.translate(dx * k, dy * k)
        path()
        cr.set_line_width(spread * k * 2)
        _src(cr, name, alpha / steps * 1.3)
        cr.fill_preserve()
        cr.stroke()
        cr.restore()


# ── sagome ────────────────────────────────────────────────────────────────
def _face_path(cr, hy):
    cr.new_path()
    cr.move_to(CX, hy - 104)
    cr.curve_to(CX + 60, hy - 104, CX + 84, hy - 60, CX + 84, hy - 4)
    cr.curve_to(CX + 84, hy + 34, CX + 74, hy + 62, CX + 52, hy + 86)
    cr.curve_to(CX + 34, hy + 104, CX + 16, hy + 110, CX, hy + 110)
    cr.curve_to(CX - 16, hy + 110, CX - 34, hy + 104, CX - 52, hy + 86)
    cr.curve_to(CX - 74, hy + 62, CX - 84, hy + 34, CX - 84, hy - 4)
    cr.curve_to(CX - 84, hy - 60, CX - 60, hy - 104, CX, hy - 104)
    cr.close_path()


def _hair_back_path(cr, hy):
    """Il caschetto dietro la testa: arriva al mento, gonfio sui lati, con
    le punte che girano verso l'interno; il fondo resta dietro il collo."""
    cr.new_path()
    cr.move_to(CX - 108, hy + 76)
    cr.curve_to(CX - 130, hy + 10, CX - 124, hy - 142, CX, hy - 142)
    cr.curve_to(CX + 124, hy - 142, CX + 128, hy - 10, CX + 110, hy + 60)
    cr.curve_to(CX + 104, hy + 84, CX + 88, hy + 96, CX + 66, hy + 94)
    cr.curve_to(CX + 30, hy + 112, CX - 30, hy + 112, CX - 66, hy + 98)
    cr.curve_to(CX - 88, hy + 100, CX - 104, hy + 92, CX - 108, hy + 76)
    cr.close_path()


def _lock_left_path(cr, hy):
    """Ciocca sinistra, davanti al viso: scende fino alla mascella."""
    cr.new_path()
    cr.move_to(CX - 66, hy - 92)
    cr.curve_to(CX - 112, hy - 70, CX - 116, hy + 10, CX - 108, hy + 62)
    cr.curve_to(CX - 104, hy + 86, CX - 92, hy + 102, CX - 70, hy + 104)
    cr.curve_to(CX - 80, hy + 92, CX - 82, hy + 78, CX - 80, hy + 62)
    cr.curve_to(CX - 86, hy + 30, CX - 88, hy - 20, CX - 78, hy - 52)
    cr.close_path()


def _lock_right_path(cr, hy):
    """Ciocca destra: portata dietro l'orecchio, più corta davanti."""
    cr.new_path()
    cr.move_to(CX + 60, hy - 96)
    cr.curve_to(CX + 104, hy - 82, CX + 112, hy - 30, CX + 106, hy + 6)
    cr.curve_to(CX + 100, hy - 6, CX + 94, hy - 22, CX + 86, hy - 34)
    cr.curve_to(CX + 84, hy - 52, CX + 76, hy - 72, CX + 60, hy - 96)
    cr.close_path()


# Frangia di lato: dalla riga, a sinistra in alto, le ciocche scendono verso
# destra. Ogni ciocca: (punta, incavo dopo la punta).
FRINGE = (((-34, -44), (-24, -49)), ((4, -36), (14, -42)), ((42, -28), (52, -33)), ((74, -20), (82, -25)))


def _fringe_path(cr, hy):
    cr.new_path()
    cr.move_to(CX - 92, hy - 22)
    cr.curve_to(CX - 90, hy - 40, CX - 78, hy - 54, CX - 62, hy - 56)       # riga
    prev = (CX - 62, hy - 56)
    for (tx, ty), (nx, ny) in FRINGE:
        tip, notch = (CX + tx, hy + ty), (CX + nx, hy + ny)
        cr.curve_to(prev[0] + 12, prev[1] + 2, tip[0] - 14, tip[1] - 1, tip[0], tip[1])
        cr.curve_to(tip[0] + 4, tip[1] + .5, notch[0] - 3, notch[1] + 4, notch[0], notch[1])
        prev = notch
    end = (CX + 94, hy - 8)
    cr.curve_to(prev[0] + 6, prev[1] + 6, end[0] - 4, end[1] - 6, end[0], end[1])
    cr.curve_to(CX + 108, hy - 72, CX + 70, hy - 130, CX + 4, hy - 130)
    cr.curve_to(CX - 62, hy - 130, CX - 104, hy - 92, CX - 92, hy - 22)
    cr.close_path()


def _eye_path(cr, x, y, s, open_):
    """Mandorla dell'occhio; s = -1 sinistro, 1 destro; open_ da 0 a 1."""
    top, bot = 17 * open_, 10 * open_
    cr.new_path()
    cr.move_to(x - s * 21, y + 2)
    cr.curve_to(x - s * 15, y - top * .9, x + s * 9, y - top - 1.5, x + s * 22, y - 3 * open_)
    cr.curve_to(x + s * 15, y + bot, x - s * 9, y + bot + 1.5, x - s * 21, y + 2)
    cr.close_path()


# ── parti ─────────────────────────────────────────────────────────────────
def _orbit(cr, m, hy, front):
    """L'orbita: metà dietro la testa, metà davanti."""
    ring = m.ring
    sweep = m.orbit_sweep
    cr.save()
    cr.translate(CX, hy - 8)
    cr.rotate(-.26)
    cr.save()
    cr.scale(158, 44)
    if sweep < 1:
        if not front or sweep <= 0:
            cr.restore()
            cr.restore()
            return
        cr.new_sub_path()
        cr.arc(0, 0, 1, -math.pi / 2, -math.pi / 2 + sweep * 2 * math.pi)
    else:
        cr.new_sub_path()
        cr.arc(0, 0, 1, *((0.0, math.pi) if front else (math.pi, 2 * math.pi)))
    cr.restore()
    # alone e linea
    cr.set_source_rgba(*_c("orbit", (.14 if front else .10) + ring * .2))
    cr.set_line_width(5 + ring * 6)
    cr.stroke_preserve()
    cr.set_source_rgba(*_c("orbit", .95 if front else .55))
    cr.set_line_width(1.3 + ring * 2.4)
    cr.stroke()
    a = m.orbit
    ox, oy = math.cos(a) * 158, math.sin(a) * 44
    dot_front = math.sin(a) > 0
    if dot_front == front and m.state != "paused" and sweep >= 1:
        r = 4.5 + ring * 2
        cr.set_source(_radial(ox, oy, 0, r * 3.6, _c("glow", .6), _c("glow", 0)))
        _ell(cr, ox, oy, r * 3.6, r * 3.6)
        cr.fill()
        _ell(cr, ox, oy, r, r)
        cr.set_source(_radial(ox - r * .3, oy - r * .3, 0, r, _c("hair_hi"), _c("hair_dark")))
        cr.fill_preserve()
        _src(cr, "cream")
        cr.set_line_width(1.4)
        cr.stroke()
    cr.restore()


def _body(cr, hy):
    # collo, con l'ombra della testa
    cr.new_path()
    cr.move_to(CX - 25, hy + 80)
    cr.curve_to(CX - 25, hy + 108, CX - 28, hy + 124, CX - 42, hy + 132)
    cr.curve_to(CX - 14, hy + 156, CX + 14, hy + 156, CX + 42, hy + 132)
    cr.curve_to(CX + 28, hy + 124, CX + 25, hy + 108, CX + 25, hy + 80)
    cr.close_path()
    cr.set_source(_linear(CX - 30, 0, CX + 30, 0, (0, _c("skin_mid")), (.6, _c("skin_shade")), (1, _c("skin_deep"))))
    cr.fill()
    # maglione: spalle morbide, scollo tondo
    cr.new_path()
    cr.move_to(CX - 176, 400)
    cr.curve_to(CX - 170, 352, CX - 120, 332, CX - 50, 326)
    cr.curve_to(CX - 30, 352, CX + 30, 352, CX + 50, 326)
    cr.curve_to(CX + 120, 332, CX + 170, 352, CX + 176, 400)
    cr.close_path()
    cr.set_source(_linear(CX - 170, 330, CX + 170, 400, (0, _c("sweater_hi")), (.5, _c("sweater")), (1, _c("sweater_dark"))))
    cr.fill()
    # trama a coste, appena accennata
    cr.save()
    cr.new_path()
    cr.move_to(CX - 176, 400)
    cr.curve_to(CX - 170, 352, CX - 120, 332, CX - 50, 326)
    cr.curve_to(CX - 30, 352, CX + 30, 352, CX + 50, 326)
    cr.curve_to(CX + 120, 332, CX + 170, 352, CX + 176, 400)
    cr.close_path()
    cr.clip()
    for i in range(-16, 17):
        x = CX + i * 11
        cr.move_to(x, 330)
        cr.curve_to(x + i * .8, 360, x + i * 1.6, 380, x + i * 2.2, 402)
    _src(cr, "sweater_dark", .22)
    cr.set_line_width(1.2)
    cr.stroke()
    # piega delle spalle
    for s in (-1, 1):
        cr.move_to(CX + s * 118, 338)
        cr.curve_to(CX + s * 128, 356, CX + s * 132, 378, CX + s * 130, 400)
        _src(cr, "sweater_dark", .35)
        cr.set_line_width(2)
        cr.stroke()
    cr.restore()
    # bordo dello scollo e camicetta
    cr.move_to(CX - 52, 325)
    cr.curve_to(CX - 30, 356, CX + 30, 356, CX + 52, 325)
    _src(cr, "sweater_dark")
    cr.set_line_width(5)
    cr.stroke()
    for s in (-1, 1):
        cr.new_path()
        cr.move_to(CX + s * 40, 328)
        cr.curve_to(CX + s * 30, 340, CX + s * 14, 346, CX + s * 2, 352)
        cr.line_to(CX + s * 24, 356)
        cr.curve_to(CX + s * 34, 350, CX + s * 44, 340, CX + s * 48, 330)
        cr.close_path()
        cr.set_source(_linear(CX, 326, CX, 356, (0, _c("cream")), (1, _c("cream_sh"))))
        cr.fill()
    # ciondolo: una piccola orbita su una catenina sottile
    cr.move_to(CX - 24, 330)
    cr.curve_to(CX - 14, 350, CX + 14, 350, CX + 24, 330)
    _src(cr, "cream", .55)
    cr.set_line_width(.7)
    cr.stroke()
    _ell(cr, CX, 350, 7, 3, -.26)
    _src(cr, "orbit")
    cr.set_line_width(1.2)
    cr.stroke()
    _ell(cr, CX + 5, 348.5, 1.9, 1.9)
    _src(cr, "hair")
    cr.fill()


def _strands(cr, pts, name, alpha, width):
    for (x0, y0, x1, y1, x2, y2, x3, y3) in pts:
        cr.move_to(x0, y0)
        cr.curve_to(x1, y1, x2, y2, x3, y3)
    _src(cr, name, alpha)
    cr.set_line_width(width)
    cr.stroke()


def _pencil(cr, hy):
    cr.save()
    cr.translate(CX + 96, hy - 8)
    cr.rotate(-.98)
    # corpo esagonale: tre facce
    for x0, x1, col in ((-4.5, -1.5, "wood"), (-1.5, 1.5, "wood_mid"), (1.5, 4.5, "wood_dark")):
        cr.rectangle(x0, -40, x1 - x0, 70)
        _src(cr, col)
        cr.fill()
    # gommino e ghiera
    cr.rectangle(-4.5, -49, 9, 9)
    cr.set_source(_linear(-4.5, 0, 4.5, 0, (0, _c("eraser")), (1, _c("blush"))))
    cr.fill()
    cr.rectangle(-4.7, -41, 9.4, 4)
    cr.set_source(_linear(-4.7, 0, 4.7, 0, (0, _c("spark")), (.5, _c("ferrule")), (1, _c("skin_line"))))
    cr.fill()
    # punta temperata
    cr.move_to(-4.5, 30)
    cr.line_to(4.5, 30)
    cr.line_to(0, 44)
    cr.close_path()
    cr.set_source(_linear(-4.5, 0, 4.5, 0, (0, _c("cream")), (1, _c("skin_deep"))))
    cr.fill()
    cr.move_to(-1.7, 39)
    cr.line_to(1.7, 39)
    cr.line_to(0, 44)
    cr.close_path()
    _src(cr, "lead")
    cr.fill()
    cr.restore()


def _ear(cr, hy):
    x, y = CX + 82, hy + 12
    cr.new_path()
    cr.move_to(x - 2, y - 16)
    cr.curve_to(x + 10, y - 22, x + 16, y - 6, x + 12, y + 6)
    cr.curve_to(x + 9, y + 16, x + 4, y + 22, x - 2, y + 18)
    cr.close_path()
    cr.set_source(_linear(x - 2, 0, x + 14, 0, (0, _c("skin_deep")), (.4, _c("skin_mid")), (1, _c("skin_shade"))))
    cr.fill()
    cr.move_to(x + 1, y - 10)
    cr.curve_to(x + 9, y - 12, x + 10, y + 2, x + 5, y + 8)
    _src(cr, "skin_line", .55)
    cr.set_line_width(1.2)
    cr.stroke()
    # piccolo orecchino
    _ell(cr, x + 2, y + 21, 1.8, 1.8)
    _src(cr, "orbit")
    cr.fill()


def _head_base(cr, hy):
    """Le parti della testa che non si muovono: si disegnano una volta."""
    # capelli dietro
    _hair_back_path(cr, hy)
    cr.set_source(_linear(0, hy - 142, 0, hy + 100, (0, _c("hair")), (.55, _c("hair_dark")), (1, _c("hair_deep"))))
    cr.fill()
    # ombra della testa sul collo
    _ell(cr, CX, hy + 98, 36, 14)
    _src(cr, "skin_deep", .6)
    cr.fill()
    # orecchio destro (la ciocca è portata dietro) e matita
    _ear(cr, hy)
    _pencil(cr, hy)
    # volto: base, poi chiaroscuro
    _face_path(cr, hy)
    cr.set_source(_radial(CX - 18, hy - 14, 16, 132, (0, _c("skin")), (.62, _c("skin_mid")), (1, _c("skin_shade"))))
    cr.fill()
    cr.save()
    _face_path(cr, hy)
    cr.clip()
    # ombra laterale destra (luce da sinistra) e della mascella
    cr.set_source(_linear(CX + 20, 0, CX + 86, 0, (0, _c("skin_shade", 0)), (1, _c("skin_deep", .55))))
    cr.paint()
    cr.set_source(_linear(0, hy + 70, 0, hy + 112, (0, _c("skin_shade", 0)), (1, _c("skin_shade", .7))))
    cr.paint()
    # ombra della frangia sulla fronte
    _soft_fill(cr, lambda: _fringe_path(cr, hy), "skin_deep", .45, 3.5, dx=3, dy=7)
    # ombre delle ciocche sulle tempie
    _soft_fill(cr, lambda: _lock_left_path(cr, hy), "skin_deep", .4, 3, dx=6, dy=4)
    _soft_fill(cr, lambda: _lock_right_path(cr, hy), "skin_deep", .35, 3, dx=-5, dy=4)
    # luce sulla fronte, sugli zigomi e sul mento
    cr.set_source(_radial(CX - 26, hy - 50, 0, 46, _c("spark", .35), _c("spark", 0)))
    cr.paint()
    for s, a in ((-1, .45), (1, .22)):
        cr.set_source(_radial(CX + s * 46, hy + 18, 0, 22, _c("spark", a), _c("spark", 0)))
        cr.paint()
    cr.set_source(_radial(CX - 6, hy + 96, 0, 14, _c("spark", .35), _c("spark", 0)))
    cr.paint()
    # guance
    for s, a in ((-1, .5), (1, .42)):
        cr.save()
        cr.translate(CX + s * 50, hy + 36)
        cr.scale(1.0, .64)
        cr.set_source(_radial(0, 0, 0, 28, (0, _c("blush", a)), (.6, _c("blush", a * .45)), (1, _c("blush", 0))))
        cr.paint()
        cr.restore()
    cr.restore()
    _nose(cr, hy)


def _head_live(cr, m, hy):
    """Le parti che cambiano a ogni fotogramma."""
    gx, gy = m.gaze
    _eyes(cr, m, hy, gx, gy)
    _glasses(cr, hy)
    _mouth(cr, m, hy)


def _hair_front(cr, hy):
    # ciocca sinistra
    _lock_left_path(cr, hy)
    cr.set_source(_linear(CX - 116, 0, CX - 78, 0, (0, _c("hair_dark")), (.55, _c("hair")), (1, _c("hair_hi"))))
    cr.fill()
    _strands(cr, ((CX - 92, hy - 60, CX - 104, hy - 10, CX - 104, hy + 40, CX - 92, hy + 92),
                  (CX - 84, hy - 50, CX - 92, hy, CX - 94, hy + 50, CX - 82, hy + 96)), "hair_deep", .5, 1.1)
    _strands(cr, ((CX - 88, hy - 66, CX - 98, hy - 20, CX - 98, hy + 20, CX - 94, hy + 50),), "hair_shine", .35, 1.4)
    # ciocca destra
    _lock_right_path(cr, hy)
    cr.set_source(_linear(CX + 64, 0, CX + 110, 0, (0, _c("hair_hi")), (.45, _c("hair")), (1, _c("hair_dark"))))
    cr.fill()
    _strands(cr, ((CX + 74, hy - 80, CX + 96, hy - 60, CX + 104, hy - 30, CX + 102, hy - 4),), "hair_deep", .5, 1.1)
    # frangia
    _fringe_path(cr, hy)
    cr.set_source(_linear(CX - 96, hy - 128, CX + 70, hy - 20,
                          (0, _c("hair_hi")), (.4, _c("hair")), (.85, _c("hair_dark")), (1, _c("hair_deep"))))
    cr.fill()
    cr.save()
    _fringe_path(cr, hy)
    cr.clip()
    # ciocche: una linea scura che sale da ogni incavo, fili di luce sulle ciocche
    for (tx, ty), (nx, ny) in FRINGE:
        cr.move_to(CX + nx, hy + ny)
        cr.curve_to(CX + nx - 14, hy + ny - 24, CX + nx * .4 - 30, hy - 104, CX + nx * .3 - 52, hy - 122)
        _src(cr, "hair_deep", .6)
        cr.set_line_width(1.4)
        cr.stroke()
        cr.move_to(CX + tx - 4, hy + ty - 6)
        cr.curve_to(CX + tx - 20, hy + ty - 26, CX + tx * .5 - 36, hy - 100, CX + tx * .3 - 60, hy - 120)
        _src(cr, "hair_shine", .3)
        cr.set_line_width(1.3)
        cr.stroke()
    for dx in (-14, 30, 70):                         # fili più sottili
        cr.move_to(CX + dx, hy - 40 - dx * .2)
        cr.curve_to(CX + dx - 16, hy - 70, CX + dx * .4 - 40, hy - 106, CX + dx * .3 - 62, hy - 124)
    _src(cr, "hair_deep", .3)
    cr.set_line_width(.9)
    cr.stroke()
    # anello di luce sulla testa
    cr.new_path()
    cr.save()
    cr.translate(CX - 8, hy - 96)
    cr.rotate(-.12)
    cr.scale(78, 18)
    cr.arc(0, 0, 1, math.pi * 1.08, math.pi * 1.92)
    cr.restore()
    for w, a in ((14, .10), (9, .14), (4, .18)):
        _src(cr, "hair_shine", a)
        cr.set_line_width(w)
        cr.stroke_preserve()
    cr.new_path()
    cr.restore()


def _rim(cr, m, hy):
    """Riflesso rosa dell'orbita sul bordo destro dei capelli."""
    cr.save()
    cr.rectangle(CX + 70, hy - 150, 70, 220)
    cr.clip()
    _hair_back_path(cr, hy)
    cr.clip_preserve()
    cr.set_source(_linear(CX + 80, 0, CX + 128, 0, (0, _c("orbit", 0)), (1, _c("orbit", .5 + m.ring * .2))))
    cr.set_line_width(6)
    cr.stroke()
    cr.restore()


def _eyes(cr, m, hy, gx, gy):
    lid = m.lid
    open_ = max(.05, 1 - lid * .93)
    ey = hy + 6
    for s in (-1, 1):
        x = CX + s * 37
        # piega della palpebra
        cr.move_to(x - s * 18, ey - 10 - 5 * open_)
        cr.curve_to(x - s * 9, ey - 18 - 7 * open_, x + s * 10, ey - 19 - 7 * open_, x + s * 20, ey - 9 - 4 * open_)
        _src(cr, "skin_line", .45)
        cr.set_line_width(1.1)
        cr.stroke()
        # ombra sopra l'occhio
        cr.set_source(_radial(x, ey - 6, 4, 26, _c("skin_deep", .35), _c("skin_deep", 0)))
        _ell(cr, x, ey - 6, 26, 16)
        cr.fill()
        # bianco dell'occhio, più scuro in alto sotto la palpebra
        _eye_path(cr, x, ey, s, open_)
        cr.set_source(_linear(0, ey - 17, 0, ey + 10, (0, _c("white_sh")), (.45, _c("white")), (1, _c("white"))))
        cr.fill_preserve()
        cr.save()
        cr.clip()
        ix, iy = x + gx, ey + gy + 1
        # iride: chiara in basso, scura in alto, anello scuro sul bordo
        cr.set_source(_radial(ix, iy, 0, 12.5, (0, _c("iris")), (.55, _c("iris")), (.8, _c("iris_hi")), (1, _c("iris_dark")),
                              fx=ix, fy=iy + 4))
        _ell(cr, ix, iy, 12.5, 13)
        cr.fill()
        for k in range(14):                      # fibre dell'iride
            a = k / 14 * 2 * math.pi
            cr.move_to(ix + math.cos(a) * 5.5, iy + math.sin(a) * 5.8)
            cr.line_to(ix + math.cos(a + .08) * 11, iy + math.sin(a + .08) * 11.5)
        _src(cr, "iris_dark", .35)
        cr.set_line_width(.7)
        cr.stroke()
        _ell(cr, ix, iy, 12.5, 13)
        _src(cr, "iris_dark")
        cr.set_line_width(1.6)
        cr.stroke()
        _ell(cr, ix, iy, 5.2, 5.6)                  # pupilla
        _src(cr, "line")
        cr.fill()
        # ombra della palpebra sull'iride
        cr.rectangle(x - 24, ey - 20, 48, 9 + (1 - open_) * 14)
        cr.set_source(_linear(0, ey - 20, 0, ey - 6 + (1 - open_) * 14, (0, _c("iris_dark", .55)), (1, _c("iris_dark", 0))))
        cr.fill()
        # riflessi
        _ell(cr, ix + 4.2, iy - 4.8, 3.1, 3.4)
        _src(cr, "spark")
        cr.fill()
        _ell(cr, ix - 3.4, iy + 4.4, 1.3, 1.3)
        _src(cr, "spark", .85)
        cr.fill()
        cr.restore()
        # palpebra che scende quando sbatte gli occhi
        if open_ < .9:
            cr.save()
            _eye_path(cr, x, ey, s, 1.0)
            cr.clip()
            top = 17 * open_
            cr.new_path()
            cr.move_to(x - s * 23, ey + 2)
            cr.curve_to(x - s * 15, ey - top * .9, x + s * 9, ey - top - 1.5, x + s * 23, ey - 3 * open_)
            cr.line_to(x + s * 23, ey - 22)
            cr.line_to(x - s * 23, ey - 22)
            cr.close_path()
            cr.set_source(_linear(0, ey - 22, 0, ey, (0, _c("skin_mid")), (1, _c("skin_shade"))))
            cr.fill()
            cr.restore()
        # rima ciliare: più spessa verso l'esterno
        top = 17 * open_
        cr.new_path()
        cr.move_to(x - s * 22, ey + 2)
        cr.curve_to(x - s * 15, ey - top * .9, x + s * 9, ey - top - 1.5, x + s * 23, ey - 3 * open_)
        cr.curve_to(x + s * 25, ey - 4 * open_ - 2.5, x + s * 25, ey - 5 * open_ - 2.5, x + s * 24, ey - 6 * open_ - 3)
        cr.curve_to(x + s * 10, ey - top - 4.6, x - s * 15, ey - top * .9 - 2.4, x - s * 22, ey + 2)
        cr.close_path()
        _src(cr, "line")
        cr.fill()
        # ciglia all'angolo esterno
        for k, (bx, by, cx_, cy_, lx, ly) in enumerate(((22, -4, 27, -6, 31, -12), (18, -9, 22, -12, 25, -18),
                                                         (13, -12, 15, -16, 16, -21))):
            cr.move_to(x + s * bx, ey + by * open_ - 1)
            cr.curve_to(x + s * cx_, ey + cy_ * open_ - 1, x + s * (lx - 2), ey + ly * open_, x + s * lx, ey + (ly - 1) * open_)
            cr.set_line_width(1.7 - k * .35)
            cr.stroke()
        # palpebra inferiore, con due ciglia leggere
        cr.move_to(x - s * 15, ey + 7 * open_)
        cr.curve_to(x - s * 6, ey + 11 * open_, x + s * 9, ey + 10 * open_, x + s * 19, ey + 2)
        _src(cr, "skin_line", .7)
        cr.set_line_width(1.0)
        cr.stroke()
        for dx in (12, 16):
            cr.move_to(x + s * dx, ey + 7.5 * open_)
            cr.line_to(x + s * (dx + 1.5), ey + 10.5 * open_)
        _src(cr, "line", .45)
        cr.set_line_width(.8)
        cr.stroke()
        # sopracciglio: pieno, più spesso all'interno, con la coda sottile
        by = ey - 30 - m.brow * 3.2
        lift = m.brow * 3.4
        cr.new_path()
        cr.move_to(x - s * 17, by + 5 - lift)
        cr.curve_to(x - s * 8, by - 4 - lift * .4, x + s * 8, by - 6, x + s * 21, by + 1)
        cr.curve_to(x + s * 9, by - 2.2, x - s * 7, by + 1.6 - lift * .4, x - s * 16, by + 9 - lift)
        cr.close_path()
        cr.set_source(_linear(x - s * 17, 0, x + s * 21, 0, (0, _c("brow", .85)), (.5, _c("brow")), (1, _c("hair_dark"))))
        cr.fill()


def _nose(cr, hy):
    # ombra del dorso, a destra
    for w, a in ((7, .06), (4, .08), (2, .1)):
        cr.move_to(CX + 6, hy + 12)
        cr.curve_to(CX + 8, hy + 22, CX + 9, hy + 31, CX + 10, hy + 38)
        _src(cr, "skin_deep", a)
        cr.set_line_width(w)
        cr.stroke()
    # punta e narici
    cr.move_to(CX - 7, hy + 41)
    cr.curve_to(CX - 4, hy + 46, CX + 6, hy + 46, CX + 9, hy + 41)
    _src(cr, "skin_line", .8)
    cr.set_line_width(1.4)
    cr.stroke()
    for s in (-1, 1):
        cr.move_to(CX + s * 7 + 1, hy + 40)
        cr.curve_to(CX + s * 10 + 1, hy + 39, CX + s * 10 + 1, hy + 43, CX + s * 6 + 1, hy + 44)
        _src(cr, "skin_line", .55)
        cr.set_line_width(1.1)
        cr.stroke()
    _ell(cr, CX - 1, hy + 36, 3.5, 2.6)
    _src(cr, "spark", .6)
    cr.fill()
    _ell(cr, CX + 1, hy + 48, 10, 2.4)
    _src(cr, "skin_deep", .3)
    cr.fill()


def _glasses(cr, hy):
    ey = hy + 7
    # ombra della montatura sulla pelle
    cr.save()
    _face_path(cr, hy)
    cr.clip()
    for s in (-1, 1):
        _ell(cr, CX + s * 37 + 3, ey + 6, 27, 21)
        _src(cr, "skin_deep", .13)
        cr.set_line_width(4)
        cr.stroke()
    cr.restore()
    for s in (-1, 1):
        x = CX + s * 37
        # lente: appena colorata, con un riflesso obliquo
        _ell(cr, x, ey, 27, 21)
        _src(cr, "glow", .07)
        cr.fill_preserve()
        cr.save()
        cr.clip()
        cr.move_to(x - 30, ey + 6)
        cr.line_to(x - 6, ey - 24)
        cr.line_to(x + 4, ey - 24)
        cr.line_to(x - 20, ey + 6)
        cr.close_path()
        _src(cr, "spark", .16)
        cr.fill()
        cr.move_to(x - 12, ey + 22)
        cr.line_to(x + 12, ey - 8)
        cr.line_to(x + 16, ey - 8)
        cr.line_to(x - 8, ey + 22)
        cr.close_path()
        _src(cr, "spark", .09)
        cr.fill()
        cr.restore()
        # montatura: scura in alto, più chiara in basso
        _ell(cr, x, ey, 27, 21)
        cr.set_source(_linear(0, ey - 21, 0, ey + 21, (0, _c("frame")), (.6, _c("frame")), (1, _c("frame_hi"))))
        cr.set_line_width(2.2)
        cr.stroke()
        cr.save()
        cr.translate(x, ey)
        cr.scale(23, 17)
        cr.arc(0, 0, 1, math.pi * 1.12, math.pi * 1.36)
        cr.restore()
        _src(cr, "spark", .8)
        cr.set_line_width(1.6)
        cr.stroke()
        # stanghetta verso l'orecchio
        cr.move_to(x + s * 27, ey - 3)
        cr.curve_to(x + s * 38, ey - 6, x + s * 48, ey - 8, x + s * 56, ey - 6)
        _src(cr, "frame")
        cr.set_line_width(1.8)
        cr.stroke()
    # ponte
    cr.move_to(CX - 10, ey - 2)
    cr.curve_to(CX - 5, ey - 8, CX + 5, ey - 8, CX + 10, ey - 2)
    _src(cr, "frame")
    cr.set_line_width(1.9)
    cr.stroke()


def _mouth(cr, m, hy):
    my = hy + 66
    rnd = m.mouth_round
    mw = (17 + 10 * m.mouth_w) * (1 - .25 * rnd)
    mh = max(15 * m.mouth_h, 0.0)
    smile = (1.5 + m.smile * 4.5) * (1 - rnd * .7)
    cy = my - smile                                   # angoli della bocca
    top_in = my - mh * (.42 + .18 * rnd)              # bordo interno superiore
    bot_in = my + mh * (.58 + .18 * rnd) + smile * .25
    ctl = .5 - .2 * rnd                               # più tondo per O e U

    def opening(path_only=False):
        cr.new_path()
        cr.move_to(CX - mw, cy)
        cr.curve_to(CX - mw * ctl, top_in, CX + mw * ctl, top_in, CX + mw, cy)
        cr.curve_to(CX + mw * ctl, bot_in, CX - mw * ctl, bot_in, CX - mw, cy)
        cr.close_path()

    # ombra sotto il labbro inferiore e fossette agli angoli
    _ell(cr, CX + 2, bot_in + 10, mw * .5, 2.8)
    _src(cr, "skin_deep", .35)
    cr.fill()
    for s in (-1, 1):
        cr.move_to(CX + s * (mw + 1), cy - 1)
        cr.curve_to(CX + s * (mw + 4), cy - 2 - smile * .4, CX + s * (mw + 4), cy + 3, CX + s * (mw + 2), cy + 4)
        _src(cr, "skin_line", .35 + .1 * m.smile)
        cr.set_line_width(1.0)
        cr.stroke()
    # interno della bocca
    if mh > 1.2:
        opening()
        cr.set_source(_linear(0, top_in, 0, bot_in, (0, _c("mouth_deep")), (1, _c("mouth"))))
        cr.fill_preserve()
        cr.save()
        cr.clip()
        tooth = min(5.5, mh * .42)
        cr.new_path()
        cr.move_to(CX - mw, top_in - 2)
        cr.line_to(CX + mw, top_in - 2)
        cr.line_to(CX + mw * .8, top_in + tooth)
        cr.curve_to(CX + mw * .3, top_in + tooth + 1.2, CX - mw * .3, top_in + tooth + 1.2, CX - mw * .8, top_in + tooth)
        cr.close_path()
        cr.set_source(_linear(0, top_in, 0, top_in + tooth, (0, _c("teeth")), (1, _c("teeth_sh"))))
        cr.fill()
        if m.mouth_w > .78 and mh > 4:                # E, I: si vedono anche i denti di sotto
            cr.rectangle(CX - mw * .6, bot_in - 3.5, mw * 1.2, 4)
            _src(cr, "teeth_sh", .9)
            cr.fill()
        elif mh > 6:
            _ell(cr, CX + 1, bot_in + 1, mw * .58, mh * .3 + 1)
            cr.set_source(_linear(0, bot_in - mh * .3, 0, bot_in, (0, _c("tongue")), (1, _c("lip_dark"))))
            cr.fill()
        cr.restore()
    # labbro superiore, con l'arco di Cupido
    cr.new_path()
    cr.move_to(CX - mw - 1.5, cy)
    cr.curve_to(CX - mw * .7, top_in - 5, CX - 8, top_in - 7.5, CX - 4.5, top_in - 7)
    cr.curve_to(CX - 2, top_in - 6.8, CX - 1, top_in - 5.2, CX, top_in - 5.2)
    cr.curve_to(CX + 1, top_in - 5.2, CX + 2, top_in - 6.8, CX + 4.5, top_in - 7)
    cr.curve_to(CX + 8, top_in - 7.5, CX + mw * .7, top_in - 5, CX + mw + 1.5, cy)
    cr.curve_to(CX + mw * ctl, top_in + .5, CX - mw * ctl, top_in + .5, CX - mw - 1.5, cy)
    cr.close_path()
    cr.set_source(_linear(0, top_in - 7, 0, top_in, (0, _c("lip")), (1, _c("lip_dark"))))
    cr.fill()
    # labbro inferiore, più pieno, con il riflesso
    cr.new_path()
    cr.move_to(CX - mw - 1.5, cy)
    cr.curve_to(CX - mw * ctl, bot_in - .5, CX + mw * ctl, bot_in - .5, CX + mw + 1.5, cy)
    cr.curve_to(CX + mw * .7, bot_in + 5.5, CX + 7, bot_in + 7.5, CX, bot_in + 7.5)
    cr.curve_to(CX - 7, bot_in + 7.5, CX - mw * .7, bot_in + 5.5, CX - mw - 1.5, cy)
    cr.close_path()
    cr.set_source(_linear(0, bot_in, 0, bot_in + 7.5, (0, _c("lip_dark")), (.4, _c("lip")), (1, _c("lip"))))
    cr.fill()
    _ell(cr, CX - 3, bot_in + 3.6, mw * .22, 1.2)
    _src(cr, "lip_hi", .75)
    cr.fill()
    # linea fra le labbra quando la bocca è chiusa
    if mh <= 1.2:
        cr.move_to(CX - mw - 1.5, cy)
        cr.curve_to(CX - mw * ctl, top_in + 1.4, CX + mw * ctl, top_in + 1.4, CX + mw + 1.5, cy)
        _src(cr, "mouth", .8)
        cr.set_line_width(1.2)
        cr.stroke()


# ── la materializzazione ──────────────────────────────────────────────────
def _targets():
    """Punti della sagoma verso cui volano le scie: contorno dei capelli e
    del volto, occhi, occhiali, bocca, spalle."""
    pts = []
    hy = CY
    for i in range(60):
        a = 2 * math.pi * i / 60
        pts.append((CX + math.cos(a) * 112, hy - 34 + math.sin(a) * 108))
    for i in range(36):
        a = 2 * math.pi * i / 36
        pts.append((CX + math.cos(a) * 84, hy + 4 + math.sin(a) * 106))
    for s in (-1, 1):
        for i in range(14):
            a = 2 * math.pi * i / 14
            pts.append((CX + s * 37 + math.cos(a) * 27, hy + 7 + math.sin(a) * 21))
    for i in range(10):
        pts.append((CX - 18 + i * 4, hy + 66 + math.sin(i / 9 * math.pi) * 4))
    for i in range(24):
        t = i / 23
        pts.append((CX - 166 + t * 332, 392 - math.sin(t * math.pi) * 62))
    return pts


_PARTICLES = None


def _particles():
    global _PARTICLES
    if _PARTICLES is None:
        rnd = random.Random(7)
        out = []
        for tx, ty in _targets():
            a = rnd.uniform(0, 2 * math.pi)
            d = rnd.uniform(220, 380)
            out.append((CX + math.cos(a) * d, CY + math.sin(a) * d, tx, ty,
                        rnd.uniform(0, .3), rnd.uniform(1.2, 2.6), rnd.uniform(-1.6, 1.6)))
        _PARTICLES = out
    return _PARTICLES


def _materialize(cr, a):
    """Scie di luce che arrivano da ogni parte e si raccolgono nella sagoma."""
    fade = 1 - _smooth((a - .72) / .25)
    if fade <= 0:
        return
    for sx, sy, tx, ty, delay, size, swirl in _particles():
        u = (a - delay) / .5
        if u <= 0:
            continue
        u = min(1.0, u)

        def pos(v):
            e = 1 - (1 - v) ** 3
            ang = swirl * (1 - e)
            dx, dy = (sx - tx) * (1 - e), (sy - ty) * (1 - e)
            return (tx + dx * math.cos(ang) - dy * math.sin(ang),
                    ty + dx * math.sin(ang) + dy * math.cos(ang))
        x, y = pos(u)
        px, py = pos(max(0.0, u - .12))
        alpha = fade * min(1.0, u * 3)
        cr.move_to(px, py)
        cr.line_to(x, y)
        cr.set_source(_linear(px, py, x, y, (0, _c("orbit", 0)), (1, _c("orbit", alpha * .55))))
        cr.set_line_width(size * .6)
        cr.stroke()
        cr.set_source(_radial(x, y, 0, size * 3.4, _c("orbit", alpha), _c("orbit", 0)))
        _ell(cr, x, y, size * 3.4, size * 3.4)
        cr.fill()
        _ell(cr, x, y, size * .7, size * .7)
        _src(cr, "spark", alpha)
        cr.fill()


def _device_scale(cr):
    """Pixel veri per pixel logico (schermi ad alta densità: 2)."""
    try:
        return max(1.0, cr.get_target().get_device_scale()[0])
    except (AttributeError, cairo.Error):
        return 1.0


# ── livelli in memoria ────────────────────────────────────────────────────
# Capelli, viso, ombre e maglione non cambiano: si disegnano una volta per
# dimensione della finestra e poi si incollano (il respiro e l'inclinazione
# della testa li spostano soltanto). A ogni fotogramma si ridisegnano solo
# occhi, occhiali, bocca, orbita e riflesso: circa un quinto del lavoro.
_LAYERS = {}
_MAX_LAYERS = 10
TILT_STEP = .004       # l'inclinazione si salva a passi di circa un quarto di grado


def _layer(name, scale, paint, tilt=0.0):
    key = (name, round(scale, 3), tilt)
    surf = _LAYERS.pop(key, None)
    if surf is not None:
        _LAYERS[key] = surf                        # il più recente va in fondo
        return surf
    if surf is None:
        while len(_LAYERS) >= _MAX_LAYERS:
            del _LAYERS[next(iter(_LAYERS))]
        side = int(math.ceil(400 * scale)) + 2
        surf = cairo.ImageSurface(cairo.FORMAT_ARGB32, side, side)
        lc = cairo.Context(surf)
        lc.scale(scale, scale)
        lc.set_line_cap(cairo.LINE_CAP_ROUND)
        lc.set_line_join(cairo.LINE_JOIN_ROUND)
        if tilt:
            lc.translate(CX, 300)
            lc.rotate(tilt)
            lc.translate(-CX, -300)
        paint(lc)
        surf.flush()
        _LAYERS[key] = surf
    return surf


def _blit(cr, surf, scale, dx=0.0, dy=0.0):
    cr.save()
    cr.translate(dx, dy)
    cr.scale(1 / scale, 1 / scale)
    cr.set_source_surface(surf, 0, 0)
    cr.get_source().set_filter(cairo.FILTER_BILINEAR)
    cr.paint()
    cr.restore()


def draw(cr, width, height, m):
    """Disegna il volto al centro di width × height (fondo trasparente)."""
    size = min(width, height)
    cr.save()
    cr.translate((width - size) / 2, (height - size) / 2)
    cr.scale(size / 400, size / 400)
    cr.set_line_cap(cairo.LINE_CAP_ROUND)
    cr.set_line_join(cairo.LINE_JOIN_ROUND)
    a = m.appear
    br = 0.0 if m.reduce_motion else math.sin(m.t * 1.5) * 1.6       # respiro
    hy = CY + br * .4
    reveal = _smooth((a - .3) / .55) if a < 1 else 1.0

    if reveal > 0:
        dev = size / 400 * _device_scale(cr)
        if reveal < 1:
            cr.push_group()        # serve la maschera della linea di luce
        tq = round(m.tilt / TILT_STEP) * TILT_STEP
        tq = 0.0 if abs(tq) < 1e-9 else round(tq, 4)
        sw = m.sway
        _blit(cr, _layer("body", dev, lambda c: _body(c, CY)), dev, 0, br * .25)
        head = _layer("head", dev, lambda c: _head_base(c, CY), tq)
        hair = _layer("hair", dev, lambda c: _hair_front(c, CY), tq)
        cr.save()
        cr.translate(sw, 0)
        cr.save()
        cr.translate(CX, 300)
        cr.rotate(tq)
        cr.translate(-CX, -300)
        _orbit(cr, m, hy, front=False)
        cr.restore()
        _blit(cr, head, dev, 0, hy - CY)
        cr.translate(CX, 300)
        cr.rotate(tq)
        cr.translate(-CX, -300)
        _head_live(cr, m, hy)
        cr.restore()
        cr.save()
        cr.translate(sw, 0)
        _blit(cr, hair, dev, 0, hy - CY)
        cr.translate(CX, 300)
        cr.rotate(tq)
        cr.translate(-CX, -300)
        _rim(cr, m, hy)
        _orbit(cr, m, hy, front=True)
        cr.restore()
        if reveal < 1:
            group = cr.pop_group()
            line = 400 - reveal * 440
            mask = _linear(0, line - 26, 0, line + 6, (0, (0, 0, 0, 0)), (1, (0, 0, 0, 1)))
            cr.set_source(group)
            cr.mask(mask)
            glow = _linear(0, line - 14, 0, line + 14, (0, _c("glow", 0)), (.5, _c("spark", .9)), (1, _c("glow", 0)))
            cr.save()
            cr.rectangle(CX - 170, line - 14, 340, 28)
            cr.clip()
            cr.set_source(glow)
            cr.mask(_radial(CX, line, 10, 170, (0, 0, 0, 1), (0, 0, 0, 0)))
            cr.restore()
    if a < 1:
        _materialize(cr, a)
    cr.restore()


# ── widget ─────────────────────────────────────────────────────────────────
try:
    import gi
    gi.require_version("Gtk", "4.0")
    from gi.repository import Gtk
except (ImportError, ValueError):            # prove senza GTK
    Gtk = None

if Gtk is not None:
    class FaceView(Gtk.DrawingArea):
        """Il volto nella finestra. `speech_source()` restituisce
        (ampiezza, visema) dell'audio che suona in questo momento."""

        def __init__(self, label_for_state):
            super().__init__(hexpand=True, vexpand=True, content_width=240, content_height=240)
            settings = Gtk.Settings.get_default()
            reduce = settings is not None and not settings.props.gtk_enable_animations
            self.model = FaceModel(reduce_motion=reduce)
            self.speech_source = None
            self.label_for_state = label_for_state
            self._last = None
            self.set_draw_func(lambda _w, cr, w, h: draw(cr, w, h, self.model))
            self.add_tick_callback(self._tick)
            if settings is not None:
                settings.connect("notify::gtk-enable-animations",
                                 lambda s, _p: setattr(self.model, "reduce_motion",
                                                       not s.props.gtk_enable_animations))
            self._update_label()

        def set_state(self, state):
            self.model.set_state(state)
            self._update_label()

        def set_level(self, level):
            self.model.level = level

        def set_emotion(self, emotion):
            self.model.set_emotion(emotion)

        def _update_label(self):
            self.update_property([Gtk.AccessibleProperty.LABEL],
                                 [self.label_for_state(self.model.state)])

        def _tick(self, _widget, clock):
            now = clock.get_frame_time() / 1e6
            dt = 0.016 if self._last is None else min(0.1, now - self._last)
            self._last = now
            if self.speech_source is not None:
                import time
                self.model.speech = self.speech_source(time.monotonic())
            self.model.step(dt)
            self.queue_draw()
            return True
