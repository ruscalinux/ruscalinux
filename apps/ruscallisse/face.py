# -*- coding: utf-8 -*-
# face.py — RuscaLinux OS Apps 1.99.3 — GPL-3.0-or-later
#
# Il volto di Ellittica, disegnato con Cairo: solo forme, quasi tutte
# ellissi (specifiche, sezione 1.7.8). Personaggio originale: capelli corti,
# occhiali ovali, una matita dietro l'orecchio, l'orbita intorno alla testa.
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

    def set_state(self, state):
        if state in STATES:
            self.state = state

    def set_emotion(self, emotion, seconds=4.0):
        if emotion in EMOTION:
            self.emotion = emotion
            self.emotion_until = self.t + seconds

    def step(self, dt):
        self.t += dt
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
        squint = {"listening": .35, "idle": .15}.get(s, 0.0)
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
def _rgb(cr, name, alpha=1.0):
    r, g, b = C[name]
    cr.set_source_rgba(r / 255, g / 255, b / 255, alpha)


def _ellipse(cr, x, y, rx, ry, rot=0.0):
    cr.save()
    cr.translate(x, y)
    cr.rotate(rot)
    cr.scale(max(rx, .1), max(ry, .1))
    cr.new_sub_path()
    cr.arc(0, 0, 1, 0, 2 * math.pi)
    cr.restore()


def _fill_ellipse(cr, x, y, rx, ry, color, rot=0.0, alpha=1.0):
    _ellipse(cr, x, y, rx, ry, rot)
    _rgb(cr, color, alpha)
    cr.fill()


def _stroke(cr, color, width, alpha=1.0):
    _rgb(cr, color, alpha)
    cr.set_line_width(width)
    cr.stroke()


def draw(cr, width, height, m):
    """Disegna il volto al centro di width × height (fondo trasparente)."""
    size = min(width, height)
    cr.save()
    cr.translate((width - size) / 2, (height - size) / 2)
    cr.scale(size / 380, size / 380)
    cr.set_line_cap(1)          # ROUND
    cr.set_line_join(1)
    t = m.t
    br = 0.0 if m.reduce_motion else math.sin(t * 1.5) * 1.6
    cx, cy = 190.0, 182.0
    gx, gy = m.gaze

    # spalle e collo
    _fill_ellipse(cr, cx, cy + 200, 110, 40, "p500")
    _fill_ellipse(cr, cx, cy + 190, 40, 14, "cream")
    _fill_ellipse(cr, cx, cy + 146, 30, 40, "r200")

    cr.save()
    cr.translate(cx, cy + 146)
    cr.rotate(m.tilt)
    cr.translate(-cx, -(cy + 146))
    hy = cy + br * .4

    # orbita, metà dietro
    a = m.orbit
    ring = m.ring
    ox, oy = math.cos(a) * 150, math.sin(a) * 42
    front = math.sin(a) > 0
    cr.save()
    cr.translate(cx, hy - 6)
    cr.rotate(-.26)
    if not front and m.state != "paused":
        _fill_ellipse(cr, ox, oy, 3.5, 3.5, "r300")
    cr.restore()

    # capelli (dietro), testa, orecchio, matita
    _fill_ellipse(cr, cx, hy - 26, 104, 94, "p600")
    _fill_ellipse(cr, cx - 92, hy + 22, 20, 44, "p600", .08)
    _fill_ellipse(cr, cx + 92, hy + 22, 20, 44, "p600", -.08)
    _fill_ellipse(cr, cx, hy, 88, 110, "r100")
    _fill_ellipse(cr, cx + 86, hy + 16, 9, 15, "r100")
    _ellipse(cr, cx + 86, hy + 16, 9, 15)
    _stroke(cr, "r250", 1)
    cr.save()
    cr.translate(cx + 92, hy - 6)
    cr.rotate(-.95)
    _rgb(cr, "wood"); cr.rectangle(-4, -40, 8, 70); cr.fill()
    _rgb(cr, "r250"); cr.rectangle(-4, -46, 8, 8); cr.fill()
    cr.move_to(-4, 30); cr.line_to(4, 30); cr.line_to(0, 42); cr.close_path()
    _rgb(cr, "r200"); cr.fill()
    cr.move_to(-1.6, 37); cr.line_to(1.6, 37); cr.line_to(0, 42); cr.close_path()
    _rgb(cr, "lead"); cr.fill()
    cr.restore()

    # frangia
    cr.move_to(cx - 94, hy + 4)
    cr.curve_to(cx - 96, hy - 60, cx - 60, hy - 112, cx + 6, hy - 112)
    cr.curve_to(cx + 70, hy - 112, cx + 96, hy - 60, cx + 94, hy + 2)
    cr.curve_to(cx + 84, hy - 40, cx + 64, hy - 70, cx + 30, hy - 74)
    cr.curve_to(cx + 4, hy - 56, cx - 30, hy - 46, cx - 62, hy - 44)
    cr.curve_to(cx - 76, hy - 36, cx - 88, hy - 18, cx - 94, hy + 4)
    cr.close_path()
    _rgb(cr, "p600")
    cr.fill()
    cr.move_to(cx - 40, hy - 92)
    cr.curve_to(cx - 10, hy - 98, cx + 30, hy - 96, cx + 56, hy - 80)
    _stroke(cr, "p500", 2)

    # orbita
    cr.save()
    cr.translate(cx, hy - 6)
    cr.rotate(-.26)
    _ellipse(cr, 0, 0, 150, 42)
    _stroke(cr, "r300", 1.2 + ring * 2.5)
    cr.restore()

    # occhi
    ex, ey = 34, hy + 2
    lid = m.lid
    for s in (-1, 1):
        x = cx + s * ex
        ry = 13 * (1 - lid * .85) + .5
        _fill_ellipse(cr, x, ey, 17, ry, "cream")
        if lid < .85:
            cr.save()
            _ellipse(cr, x, ey, 17, ry)
            cr.clip()
            _fill_ellipse(cr, x + gx, ey + gy, 9, 10, "p500")
            _fill_ellipse(cr, x + gx, ey + gy, 4.6, 5.2, "p900")
            _fill_ellipse(cr, x + gx + 3, ey + gy - 3.5, 2.4, 2.4, "cream")
            _fill_ellipse(cr, x + gx - 2.5, ey + gy + 3, 1.1, 1.1, "cream")
            cr.restore()
        cr.save()
        cr.translate(x, ey)
        cr.scale(17, ry)
        cr.arc(0, 0, 1, math.pi * 1.05, math.pi * 1.95)
        cr.restore()
        _stroke(cr, "p900", 2)
        cr.move_to(x + s * 15, ey - ry * .6)
        cr.line_to(x + s * 20, ey - ry * .9 - 2)
        _stroke(cr, "p900", 1.4)
        by = ey - 26 - m.brow * 3
        cr.move_to(x - s * 14, by + 3 - m.brow * 2.5)
        cr.curve_to(x - s * 6, by - 3, x + s * 6, by - 4, x + s * 16, by + 2)
        _stroke(cr, "p800", 2.6)

    # occhiali
    for s in (-1, 1):
        x = cx + s * ex
        _fill_ellipse(cr, x, ey + 1, 27, 21, "cream", alpha=.18)
        _ellipse(cr, x, ey + 1, 27, 21)
        _stroke(cr, "p900", 2.2)
        cr.move_to(x - s * 10 + 6, ey - 12)
        cr.line_to(x - s * 10 - 2, ey - 4)
        _stroke(cr, "cream", 2, .8)
        cr.move_to(x + s * 27, ey - 2)
        cr.line_to(x + s * 58, ey - 6)
        _stroke(cr, "p900", 2)
    cr.move_to(cx - 8, ey - 2)
    cr.curve_to(cx - 4, ey - 7, cx + 4, ey - 7, cx + 8, ey - 2)
    _stroke(cr, "p900", 2)

    # guance e naso
    _fill_ellipse(cr, cx - 56, hy + 34, 15, 8, "r300", alpha=.6)
    _fill_ellipse(cr, cx + 56, hy + 34, 15, 8, "r300", alpha=.6)
    cr.move_to(cx + 2, hy + 14)
    cr.curve_to(cx - 4, hy + 26, cx - 5, hy + 34, cx + 3, hy + 37)
    _stroke(cr, "p500", 1.3)

    # bocca
    mw, mh, my = 24 * m.mouth_w, max(13 * m.mouth_h, 1.2), hy + 62
    if m.state != "speaking" or mh < 2:
        sm = 3 + m.smile * 5
        cr.move_to(cx - mw, my - 3)
        cr.curve_to(cx - mw / 2, my - 3 + sm, cx + mw / 2, my - 3 + sm, cx + mw, my - 3)
        _stroke(cr, "p600", 2.4)
        cr.move_to(cx - mw - 3, my - 4); cr.line_to(cx - mw + 1, my - 2)
        cr.move_to(cx + mw + 3, my - 4); cr.line_to(cx + mw - 1, my - 2)
        _stroke(cr, "p600", 1.4)
    else:
        _fill_ellipse(cr, cx, my, mw, mh, "p800")
        _ellipse(cr, cx, my, mw, mh)
        _stroke(cr, "p600", 2.2)
        if mh > 5:
            _fill_ellipse(cr, cx, my + mh * .45, mw * .55, mh * .33, "p500")

    # orbita, punto davanti
    if front and m.state != "paused":
        cr.save()
        cr.translate(cx, hy - 6)
        cr.rotate(-.26)
        _fill_ellipse(cr, ox, oy, 4.5 + ring * 2, 4.5 + ring * 2, "p600")
        _ellipse(cr, ox, oy, 4.5 + ring * 2, 4.5 + ring * 2)
        _stroke(cr, "cream", 1.5)
        cr.restore()

    cr.restore()            # inclinazione
    cr.restore()            # scala


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
