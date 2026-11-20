# -*- coding: utf-8 -*-
# face.py — RuscaLinux OS Apps 1.99.3 — GPL-3.0-or-later
#
# Il volto di Ellittica, disegnato con Cairo: solo forme e sfumature leggere
# (specifiche, sezione 1.7.8). Personaggio originale: capelli corti,
# occhiali ovali, una matita dietro l'orecchio, l'orbita intorno alla testa.
# All'avvio si materializza: scie di luce si raccolgono nella sua sagoma, il
# volto compare dal basso dietro una linea di luce, l'orbita si disegna.
#
#   FaceModel  stato e animazione, senza GTK (si prova da solo)
#   draw()     disegna su un contesto Cairo, senza GTK
#   FaceView   il Gtk.DrawingArea della finestra
import math
import random

STATES = ("idle", "listening", "thinking", "speaking", "paused")

C = {
    "p900": (0x2d, 0x0a, 0x1d), "p800": (0x3a, 0x10, 0x28), "p600": (0x7a, 0x23, 0x57),
    "p500": (0x8a, 0x2b, 0x5f), "r300": (0xf2, 0xa7, 0xc8), "r250": (0xf5, 0xb8, 0xd3),
    "r200": (0xf8, 0xd7, 0xe6), "r100": (0xf6, 0xe4, 0xec), "cream": (0xff, 0xf7, 0xf0),
    "wood": (0xe8, 0xb0, 0x4a), "lead": (0x3a, 0x10, 0x28),
}
# Forma della bocca per visema: (larghezza, apertura), da 0 a 1.
MOUTH = {"A": (.62, 1.0), "E": (.8, .55), "I": (.9, .3), "O": (.45, .8), "U": (.35, .5),
         "M": (.6, .04), "F": (.7, .2), "C": (.62, .32), "": (.6, .05)}
# Espressioni: (sopracciglia, occhi socchiusi, sorriso)
EMOTION = {"sorride": (.3, .35, 1.0), "pensierosa": (.6, .1, .2), "commossa": (1.0, .25, .5),
           "divertita": (.5, .45, 1.3), "perplessa": (.8, 0, 0), "seria": (0, 0, 0)}


APPEAR_TIME = 2.8          # secondi della materializzazione


def _approach(cur, target, k, dt):
    return cur + (target - cur) * min(1.0, k * dt * 60)


class FaceModel:
    """Stato del volto, aggiornato a ogni fotogramma con step()."""

    def __init__(self, reduce_motion=False):
        self.state = "idle"
        self.reduce_motion = reduce_motion
        self.t = 0.0
        self.level = 0.0                 # microfono
        self.speech = (0.0, "")          # (ampiezza, visema) dell'audio che suona
        self.emotion = None
        self.emotion_until = 0.0
        self.blink = 0.0
        self.next_blink = 1.8
        self.mouth_w, self.mouth_h = .6, .05
        self.tilt = self.brow = self.squint = self.smile = 0.0
        self.gaze = (0.0, 0.0)
        self.orbit = 0.0
        self.amp = 0.0
        self.appear = 1.0                # 1: già comparsa

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
        # sguardo
        if s == "thinking":
            gaze = (3.0 if rm else math.sin(t * .6) * 4 + 2, -5.0)
        elif s == "listening":
            gaze = (0.0, 1.0)
        elif s == "paused":
            gaze = (0.0, 4.0)
        else:
            gaze = (0.0, 0.0) if rm else (math.sin(t * .33) * 2.5, math.sin(t * .47) * 1.2)
        self.gaze = (_approach(self.gaze[0], gaze[0], .15, dt), _approach(self.gaze[1], gaze[1], .15, dt))
        # testa, sopracciglia, occhi, sorriso
        tilt = {"listening": -.09, "thinking": .04}.get(s, 0.0)
        brow = {"listening": 1.0, "thinking": .6, "speaking": .4 + self.amp * .4}.get(s, .25)
        squint = {"listening": .18, "idle": .06}.get(s, 0.0)
        smile = {"listening": .7, "idle": .5, "speaking": .5}.get(s, .3)
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
            self.next_blink = 2.3 + random.random() * 2.7
        if self.blink > 0:
            self.blink = max(0.0, self.blink - dt / .15)
        # bocca: visema e ampiezza dell'audio
        amp, vis = self.speech if s == "speaking" else (0.0, "")
        self.amp = _approach(self.amp, min(1.0, amp * 8), .3, dt)
        w, h = MOUTH.get(vis, MOUTH["C"])
        if s == "speaking" and vis not in ("", "M"):
            h *= max(.35, min(1.2, self.amp * 1.3))
        self.mouth_w = _approach(self.mouth_w, w, .35, dt)
        self.mouth_h = _approach(self.mouth_h, h, .35, dt)
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
# Spazio di disegno: 400 × 400, scalato sulla finestra. Ombre e luci sono
# sfumature leggere dello stesso colore: il volto resta piatto e pulito, ma
# più definito. Nessun testo è disegnato sul volto.
import cairo  # noqa: E402  (python3-cairo, dipendenza di python3-gi-cairo)

P = {   # palette del volto: RuscaLinux (sezione 4.1) e toni derivati
    "hair": (0x7a, 0x23, 0x57), "hair_dark": (0x55, 0x16, 0x3d), "hair_hi": (0xa8, 0x4a, 0x82),
    "skin": (0xfb, 0xec, 0xf2), "skin_shade": (0xef, 0xcf, 0xdd), "skin_deep": (0xe3, 0xb8, 0xcb),
    "blush": (0xf2, 0xa7, 0xc8), "lip": (0xc5, 0x4f, 0x86), "lip_dark": (0x8a, 0x2b, 0x5f),
    "lip_hi": (0xe8, 0x8d, 0xb5), "mouth": (0x3a, 0x10, 0x28), "teeth": (0xff, 0xf7, 0xf0),
    "tongue": (0xd8, 0x6f, 0x9a), "line": (0x2d, 0x0a, 0x1d), "brow": (0x55, 0x16, 0x3d),
    "iris": (0x8a, 0x2b, 0x5f), "iris_dark": (0x4e, 0x12, 0x35), "white": (0xff, 0xfb, 0xfd),
    "cream": (0xff, 0xf7, 0xf0), "sweater": (0x8a, 0x2b, 0x5f), "sweater_dark": (0x6a, 0x1e, 0x48),
    "orbit": (0xf2, 0xa7, 0xc8), "glow": (0xf8, 0xd7, 0xe6), "spark": (0xff, 0xff, 0xff),
    "wood": (0xe8, 0xb0, 0x4a), "wood_dark": (0xc8, 0x8e, 0x2e), "eraser": (0xf5, 0xb8, 0xd3),
    "lead": (0x3a, 0x10, 0x28),
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


def _radial(x, y, r0, r1, inner, outer):
    g = cairo.RadialGradient(x, y, r0, x, y, r1)
    g.add_color_stop_rgba(0, *inner)
    g.add_color_stop_rgba(1, *outer)
    return g


def _linear(x0, y0, x1, y1, *stops):
    g = cairo.LinearGradient(x0, y0, x1, y1)
    for pos, col in stops:
        g.add_color_stop_rgba(pos, *col)
    return g


def _smooth(x):
    x = min(1.0, max(0.0, x))
    return x * x * (3 - 2 * x)


# ── sagome ────────────────────────────────────────────────────────────────
def _face_path(cr, hy):
    cr.new_path()
    cr.move_to(CX, hy - 102)
    cr.curve_to(CX + 62, hy - 102, CX + 86, hy - 56, CX + 84, hy + 6)
    cr.curve_to(CX + 82, hy + 54, CX + 52, hy + 98, CX, hy + 106)
    cr.curve_to(CX - 52, hy + 98, CX - 82, hy + 54, CX - 84, hy + 6)
    cr.curve_to(CX - 86, hy - 56, CX - 62, hy - 102, CX, hy - 102)
    cr.close_path()


def _hair_back_path(cr, hy):
    cr.new_path()
    cr.move_to(CX - 106, hy + 64)
    cr.curve_to(CX - 124, hy - 40, CX - 92, hy - 136, CX, hy - 136)
    cr.curve_to(CX + 92, hy - 136, CX + 124, hy - 40, CX + 106, hy + 64)
    cr.curve_to(CX + 100, hy + 84, CX + 82, hy + 84, CX + 74, hy + 66)
    cr.line_to(CX - 74, hy + 66)
    cr.curve_to(CX - 82, hy + 84, CX - 100, hy + 84, CX - 106, hy + 64)
    cr.close_path()


def _fringe_path(cr, hy):
    cr.new_path()
    cr.move_to(CX - 92, hy + 10)
    cr.curve_to(CX - 100, hy - 84, CX - 52, hy - 122, CX + 8, hy - 122)
    cr.curve_to(CX + 74, hy - 122, CX + 100, hy - 76, CX + 92, hy + 4)
    cr.curve_to(CX + 84, hy - 40, CX + 66, hy - 66, CX + 34, hy - 72)
    cr.curve_to(CX + 14, hy - 52, CX - 26, hy - 40, CX - 58, hy - 42)
    cr.curve_to(CX - 74, hy - 30, CX - 86, hy - 12, CX - 92, hy + 10)
    cr.close_path()


def _eye_path(cr, x, y, s, open_):
    """Mandorla dell'occhio; s = -1 sinistro, 1 destro; open_ da 0 a 1."""
    top, bot = 15.5 * open_, 9.5 * open_
    cr.new_path()
    cr.move_to(x - s * 20, y + 1)
    cr.curve_to(x - s * 13, y - top, x + s * 11, y - top - 1, x + s * 21, y - 2 * open_)
    cr.curve_to(x + s * 13, y + bot, x - s * 11, y + bot + 1, x - s * 20, y + 1)
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
    cr.scale(156, 44)
    if sweep < 1:
        # durante la materializzazione l'orbita si disegna da sola, tutta davanti
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
    cr.set_source_rgba(*_c("orbit", .95 if front else .55))
    cr.set_line_width(1.4 + ring * 2.6)
    cr.stroke()
    a = m.orbit
    ox, oy = math.cos(a) * 156, math.sin(a) * 44
    dot_front = math.sin(a) > 0
    if dot_front == front and m.state != "paused" and sweep >= 1:
        r = 4.5 + ring * 2
        cr.set_source(_radial(ox, oy, 0, r * 3.2, _c("glow", .55), _c("glow", 0)))
        _ell(cr, ox, oy, r * 3.2, r * 3.2)
        cr.fill()
        _ell(cr, ox, oy, r, r)
        _src(cr, "hair")
        cr.fill_preserve()
        _src(cr, "cream")
        cr.set_line_width(1.5)
        cr.stroke()
    cr.restore()


def _body(cr):
    # spalle e maglione
    cr.new_path()
    cr.move_to(CX - 168, 400)
    cr.curve_to(CX - 160, 350, CX - 110, 330, CX - 46, 322)
    cr.line_to(CX + 46, 322)
    cr.curve_to(CX + 110, 330, CX + 160, 350, CX + 168, 400)
    cr.close_path()
    cr.set_source(_linear(0, 320, 0, 400, (0, _c("sweater")), (1, _c("sweater_dark"))))
    cr.fill()
    # camicetta a V
    cr.new_path()
    cr.move_to(CX - 40, 322)
    cr.line_to(CX, 372)
    cr.line_to(CX + 40, 322)
    cr.close_path()
    _src(cr, "cream")
    cr.fill()
    # collo
    cr.new_path()
    cr.move_to(CX - 24, 276)
    cr.curve_to(CX - 24, 300, CX - 28, 318, CX - 40, 324)
    cr.curve_to(CX - 14, 350, CX + 14, 350, CX + 40, 324)
    cr.curve_to(CX + 28, 318, CX + 24, 300, CX + 24, 276)
    cr.close_path()
    _src(cr, "skin")
    cr.fill()
    # ciondolo: una piccola orbita
    _ell(cr, CX, 356, 7, 3, -.26)
    _src(cr, "orbit")
    cr.set_line_width(1.2)
    cr.stroke()
    _ell(cr, CX + 5, 354.5, 1.8, 1.8)
    _src(cr, "hair")
    cr.fill()
    cr.move_to(CX - 18, 330)
    cr.curve_to(CX - 10, 346, CX + 10, 346, CX + 18, 330)
    _src(cr, "hair", .5)
    cr.set_line_width(.8)
    cr.stroke()


def _head(cr, m, hy):
    gx, gy = m.gaze
    # capelli dietro
    _hair_back_path(cr, hy)
    cr.set_source(_linear(0, hy - 136, 0, hy + 84, (0, _c("hair")), (1, _c("hair_dark"))))
    cr.fill()
    # ombra sotto il mento, sul collo
    _ell(cr, CX, hy + 96, 34, 12)
    _src(cr, "skin_deep", .55)
    cr.fill()
    # volto
    _face_path(cr, hy)
    cr.set_source(_radial(CX - 14, hy - 10, 20, 120, _c("skin"), _c("skin_shade")))
    cr.fill()
    # orecchio destro e matita
    _ell(cr, CX + 84, hy + 16, 9, 15, .1)
    _src(cr, "skin_shade")
    cr.fill()
    cr.save()
    cr.translate(CX + 92, hy - 4)
    cr.rotate(-.95)
    cr.rectangle(-4, -40, 8, 70)
    cr.set_source(_linear(-4, 0, 4, 0, (0, _c("wood")), (.6, _c("wood")), (1, _c("wood_dark"))))
    cr.fill()
    cr.rectangle(-4, -47, 8, 8)
    _src(cr, "eraser")
    cr.fill()
    cr.rectangle(-4.3, -40, 8.6, 2.5)
    _src(cr, "hair_hi")
    cr.fill()
    cr.move_to(-4, 30); cr.line_to(4, 30); cr.line_to(0, 42); cr.close_path()
    _src(cr, "skin_shade")
    cr.fill()
    cr.move_to(-1.6, 37); cr.line_to(1.6, 37); cr.line_to(0, 42); cr.close_path()
    _src(cr, "lead")
    cr.fill()
    cr.restore()
    # frangia, con due ciocche di luce
    _fringe_path(cr, hy)
    cr.set_source(_linear(CX - 90, hy - 122, CX + 60, hy, (0, _c("hair_hi")), (.45, _c("hair")), (1, _c("hair_dark"))))
    cr.fill()
    for dx, w in ((-20, 2.2), (14, 1.6)):
        cr.move_to(CX - 70 + dx, hy - 70)
        cr.curve_to(CX - 40 + dx, hy - 108, CX + 10 + dx, hy - 114, CX + 54 + dx, hy - 92)
        _src(cr, "hair_hi", .45)
        cr.set_line_width(w)
        cr.stroke()
    # guance
    for s in (-1, 1):
        cr.set_source(_radial(CX + s * 52, hy + 34, 0, 22, _c("blush", .55), _c("blush", 0)))
        _ell(cr, CX + s * 52, hy + 34, 22, 14)
        cr.fill()
    # occhi
    lid = m.lid
    open_ = max(.06, 1 - lid * .92)
    ey = hy + 4
    for s in (-1, 1):
        x = CX + s * 36
        _eye_path(cr, x, ey, s, open_)
        _src(cr, "white")
        cr.fill_preserve()
        cr.save()
        cr.clip()
        ix, iy = x + gx, ey + gy + 1
        cr.set_source(_radial(ix - 2, iy - 2, 1, 11, _c("iris"), _c("iris_dark")))
        _ell(cr, ix, iy, 10, 10.5)
        cr.fill()
        _ell(cr, ix, iy, 4.6, 5)
        _src(cr, "line")
        cr.fill()
        _ell(cr, ix + 3.4, iy - 4, 2.7, 2.7)
        _src(cr, "spark")
        cr.fill()
        _ell(cr, ix - 2.8, iy + 3.2, 1.1, 1.1)
        _src(cr, "spark", .8)
        cr.fill()
        # ombra della palpebra
        cr.rectangle(x - 22, ey - 16, 44, 7 + (1 - open_) * 14)
        _src(cr, "skin_deep", .35)
        cr.fill()
        cr.restore()
        # palpebra superiore e ciglia
        top = 15.5 * open_
        cr.move_to(x - s * 21, ey + 1.5)
        cr.curve_to(x - s * 13, ey - top, x + s * 11, ey - top - 1, x + s * 22, ey - 2 * open_)
        _src(cr, "line")
        cr.set_line_width(2.8)
        cr.stroke()
        # due ciglia morbide all'angolo esterno
        for k, (dx, dy, cx_, cy_, lx, ly) in enumerate(((20, -2.5, 24, -4, 26, -8), (16, -7, 19, -10, 20, -14))):
            cr.move_to(x + s * dx, ey + dy * open_)
            cr.curve_to(x + s * cx_, ey + cy_ * open_, x + s * lx, ey + ly * open_, x + s * (lx + 1), ey + (ly - 1) * open_)
            cr.set_line_width(1.8 - k * .4)
            cr.stroke()
        # palpebra inferiore
        cr.move_to(x - s * 14, ey + 6 * open_)
        cr.curve_to(x - s * 6, ey + 9 * open_, x + s * 8, ey + 9 * open_, x + s * 16, ey + 2)
        _src(cr, "skin_deep", .9)
        cr.set_line_width(1.1)
        cr.stroke()
        # sopracciglio, più alto all'interno quando ascolta
        by = ey - 27 - m.brow * 3
        cr.move_to(x - s * 15, by + 4 - m.brow * 3)
        cr.curve_to(x - s * 6, by - 3, x + s * 8, by - 5, x + s * 18, by + 2)
        _src(cr, "brow")
        cr.set_line_width(3.2)
        cr.stroke()
    # naso
    cr.move_to(CX + 3, hy + 16)
    cr.curve_to(CX - 1, hy + 28, CX - 6, hy + 36, CX - 3, hy + 41)
    cr.curve_to(CX, hy + 43, CX + 5, hy + 43, CX + 8, hy + 40)
    _src(cr, "lip_dark", .55)
    cr.set_line_width(1.5)
    cr.stroke()
    _ell(cr, CX + 1, hy + 44, 9, 2.5)
    _src(cr, "skin_deep", .35)
    cr.fill()
    # occhiali
    for s in (-1, 1):
        x = CX + s * 36
        _ell(cr, x, ey + 1, 26, 20)
        _src(cr, "cream", .12)
        cr.fill_preserve()
        _src(cr, "line")
        cr.set_line_width(2)
        cr.stroke()
        cr.save()
        cr.translate(x, ey + 1)
        cr.scale(21, 15)
        cr.arc(0, 0, 1, math.pi * 1.12, math.pi * 1.38)
        cr.restore()
        _src(cr, "spark", .75)
        cr.set_line_width(2.2)
        cr.stroke()
        cr.move_to(x + s * 26, ey - 1)
        cr.curve_to(x + s * 40, ey - 4, x + s * 50, ey - 6, x + s * 56, ey - 4)
        _src(cr, "line")
        cr.set_line_width(1.8)
        cr.stroke()
    cr.move_to(CX - 10, ey - 1)
    cr.curve_to(CX - 5, ey - 7, CX + 5, ey - 7, CX + 10, ey - 1)
    _src(cr, "line")
    cr.set_line_width(1.8)
    cr.stroke()
    _mouth(cr, m, hy)


def _mouth(cr, m, hy):
    my = hy + 64
    mw = 15 + 9 * m.mouth_w
    mh = max(13 * m.mouth_h, 0.0)
    smile = 2 + m.smile * 5
    if m.state != "speaking" or mh < 2:
        # labbra chiuse: labbro inferiore, linea del sorriso, arco di Cupido
        cr.move_to(CX - mw, my - 1)
        cr.curve_to(CX - mw * .5, my + 8 + smile * .4, CX + mw * .5, my + 8 + smile * .4, CX + mw, my - 1)
        cr.curve_to(CX + mw * .5, my + smile * .55, CX - mw * .5, my + smile * .55, CX - mw, my - 1)
        cr.close_path()
        cr.set_source(_linear(0, my, 0, my + 9, (0, _c("lip")), (1, _c("lip_dark"))))
        cr.fill()
        cr.move_to(CX - mw * .9, my - 1.5)
        cr.curve_to(CX - mw * .55, my - 6, CX - 3, my - 6, CX, my - 3.5)
        cr.curve_to(CX + 3, my - 6, CX + mw * .55, my - 6, CX + mw * .9, my - 1.5)
        cr.curve_to(CX + mw * .5, my + smile * .55 - .5, CX - mw * .5, my + smile * .55 - .5, CX - mw * .9, my - 1.5)
        cr.close_path()
        _src(cr, "lip")
        cr.fill()
        cr.move_to(CX - mw - 1, my - 2)
        cr.curve_to(CX - mw * .5, my + smile * .6, CX + mw * .5, my + smile * .6, CX + mw + 1, my - 2)
        _src(cr, "lip_dark")
        cr.set_line_width(1.3)
        cr.stroke()
        _ell(cr, CX + 3, my + 4.2 + smile * .35, 4, 1.2)
        _src(cr, "lip_hi", .8)
        cr.fill()
    else:
        _ell(cr, CX, my + mh * .3, mw, mh * .5 + 2.5)
        _src(cr, "mouth")
        cr.fill_preserve()
        cr.save()
        cr.clip()
        cr.rectangle(CX - mw, my + mh * .3 - mh * .5 - 3, mw * 2, 3 + mh * .12)
        _src(cr, "teeth")
        cr.fill()
        _ell(cr, CX, my + mh * .3 + mh * .5 + 1, mw * .6, mh * .32 + 1)
        _src(cr, "tongue")
        cr.fill()
        cr.restore()
        _ell(cr, CX, my + mh * .3, mw + 1.2, mh * .5 + 3.6)
        _src(cr, "lip")
        cr.set_line_width(3.2)
        cr.stroke()


# ── la materializzazione ──────────────────────────────────────────────────
def _targets():
    """Punti della sagoma verso cui volano le scie: contorno dei capelli e
    del volto, occhi, occhiali, bocca, spalle."""
    pts = []
    hy = CY
    for i in range(60):
        a = 2 * math.pi * i / 60
        pts.append((CX + math.cos(a) * 108, hy - 30 + math.sin(a) * 104))
    for i in range(36):
        a = 2 * math.pi * i / 36
        pts.append((CX + math.cos(a) * 84, hy + 4 + math.sin(a) * 104))
    for s in (-1, 1):
        for i in range(14):
            a = 2 * math.pi * i / 14
            pts.append((CX + s * 36 + math.cos(a) * 26, hy + 5 + math.sin(a) * 20))
    for i in range(10):
        pts.append((CX - 18 + i * 4, hy + 64 + math.sin(i / 9 * math.pi) * 4))
    for i in range(24):
        t = i / 23
        pts.append((CX - 160 + t * 320, 390 - math.sin(t * math.pi) * 60))
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
            # un po' di spirale: arrivano girando
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


def draw(cr, width, height, m):
    """Disegna il volto al centro di width × height (fondo trasparente)."""
    size = min(width, height)
    cr.save()
    cr.translate((width - size) / 2, (height - size) / 2)
    cr.scale(size / 400, size / 400)
    cr.set_line_cap(cairo.LINE_CAP_ROUND)
    cr.set_line_join(cairo.LINE_JOIN_ROUND)
    a = m.appear
    br = 0.0 if m.reduce_motion else math.sin(m.t * 1.5) * 1.6
    hy = CY + br * .4
    reveal = _smooth((a - .3) / .55) if a < 1 else 1.0

    if reveal > 0:
        cr.push_group()
        _body(cr)
        cr.save()
        cr.translate(CX, 300)
        cr.rotate(m.tilt)
        cr.translate(-CX, -300)
        _orbit(cr, m, hy, front=False)
        _head(cr, m, hy)
        _orbit(cr, m, hy, front=True)
        cr.restore()
        group = cr.pop_group()
        if reveal >= 1:
            cr.set_source(group)
            cr.paint()
        else:
            # il volto compare dal basso, dietro una linea di luce
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
