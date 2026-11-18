# -*- coding: utf-8 -*-
# cat_view.py — RuscaCat 1.99.3 — GPL-3.0-or-later
#
# Il gatto, disegnato con Cairo: un gatto nero dal petto bianco, con gli
# occhiali tondi del filosofo e un libro fra le zampe. Nessuna immagine
# esterna: il disegno e' tutto qui, e segue la modalita' chiara o scura.
#
# Stati (CatView.set_state):
#   "sleep"   dorme: occhi chiusi e qualche «z» (il motore non e' pronto)
#   "idle"    seduto, palpebre a meta' e orecchie di traverso: scontroso
#   "listen"  orecchie dritte e occhi aperti; gli archi vicino all'orecchio
#             seguono il volume del microfono (set_level)
#   "hear"    trascrive: guarda di lato, tre puntini
#   "think"   il modello risponde: guarda in alto, tre puntini
#   "speak"   parla: la bocca si apre col volume della voce (mouth_source)
#
# Con «Animazioni ridotte» (Impostazioni → Accessibilita') non si muove
# nulla da solo: niente coda, respiro, battito di ciglia o puntini; mentre
# parla la bocca resta aperta a meta'. Lo stato si legge comunque, senza
# colori: occhi, orecchie e i segni accanto alla testa cambiano forma, e la
# finestra scrive lo stato sotto il disegno.
import math
import random

from gi.repository import Gtk

# Palette RuscaLinux (specifiche, sezione 4.1) e due colori dell'illustrazione
# (occhi e copertina del libro), che non portano testo.
PLUM_900 = (0x2d / 255, 0x0a / 255, 0x1d / 255)
PLUM_600 = (0x7a / 255, 0x23 / 255, 0x57 / 255)
PLUM_DARK_FUR = (0x52 / 255, 0x1f / 255, 0x3d / 255)
ROSE_300 = (0xf2 / 255, 0xa7 / 255, 0xc8 / 255)
ROSE_250 = (0xf5 / 255, 0xb8 / 255, 0xd3 / 255)
CREAM = (0xff / 255, 0xf7 / 255, 0xf0 / 255)
AMBER = (0xe8 / 255, 0xb0 / 255, 0x4a / 255)

WIDTH, HEIGHT = 240.0, 262.0         # spazio del disegno, scalato alla finestra

# Per ogni stato: palpebra superiore (0 aperto, 1 chiuso), orecchie (0 di
# traverso, 1 dritte), direzione dello sguardo, larghezza della pupilla,
# sopracciglia (0 corrucciate, 1 alzate).
LOOK = {
    "sleep":  dict(lid=1.0, ears=0.2, gaze=(0, 0), pupil=3, brow=0.3),
    "idle":   dict(lid=0.48, ears=0.0, gaze=(0, 1), pupil=3, brow=0.0),
    "listen": dict(lid=0.12, ears=1.0, gaze=(0, 0), pupil=7, brow=1.0),
    "hear":   dict(lid=0.25, ears=0.8, gaze=(-4, -3), pupil=5, brow=0.6),
    "think":  dict(lid=0.30, ears=0.5, gaze=(4, -5), pupil=4, brow=0.2),
    "speak":  dict(lid=0.32, ears=0.4, gaze=(0, 0), pupil=4, brow=0.1),
}


class CatView(Gtk.DrawingArea):
    def __init__(self):
        super().__init__(hexpand=True, vexpand=True, accessible_role=Gtk.AccessibleRole.IMG)
        self.set_size_request(150, 160)
        self.set_draw_func(self._draw)
        self.state = "sleep"
        self.level = 0.0
        self.dark = False
        self.high_contrast = False
        self.mouth_source = None          # funzione che restituisce 0–1
        self._t = 0.0
        self._blink_at = 3.0
        self._tick = 0
        settings = Gtk.Settings.get_default()
        self._settings = settings
        if settings is not None:
            settings.connect("notify::gtk-enable-animations", lambda *_a: self._update_tick())
        self.connect("map", lambda *_a: self._update_tick())
        self.connect("unmap", lambda *_a: self._stop_tick())

    # ── stato ─────────────────────────────────────────────────────────────
    @property
    def animated(self):
        s = self._settings
        return s is None or bool(s.get_property("gtk-enable-animations"))

    def set_state(self, state, description=""):
        if state not in LOOK:
            state = "idle"
        self.state = state
        if state != "listen":
            self.level = 0.0
        if description:
            self.update_property([Gtk.AccessibleProperty.LABEL], [description])
        self.queue_draw()

    def set_level(self, level):
        self.level = 0.6 * self.level + 0.4 * min(1.0, max(0.0, level))
        if not self.animated:
            self.queue_draw()

    def set_colors(self, dark, high_contrast=False):
        self.dark, self.high_contrast = dark, high_contrast
        self.queue_draw()

    # ── movimento ─────────────────────────────────────────────────────────
    def _update_tick(self):
        if self.animated and self.get_mapped():
            if not self._tick:
                self._tick = self.add_tick_callback(self._on_tick)
        else:
            self._stop_tick()
        self.queue_draw()

    def _stop_tick(self):
        if self._tick:
            self.remove_tick_callback(self._tick)
            self._tick = 0

    def _on_tick(self, _widget, clock):
        self._t = clock.get_frame_time() / 1_000_000
        if self._t > self._blink_at + 0.16:
            self._blink_at = self._t + random.uniform(2.5, 7.0)
        self.queue_draw()
        return True

    def _mouth(self):
        if self.state != "speak":
            return 0.0
        if not self.animated:
            return 0.5
        try:
            return min(1.0, max(0.0, float(self.mouth_source()))) if self.mouth_source else 0.0
        except (TypeError, ValueError):
            return 0.0

    # ── disegno ───────────────────────────────────────────────────────────
    def _draw(self, _area, cr, width, height):
        scale = min(width / WIDTH, height / HEIGHT) * 0.94
        cr.translate((width - WIDTH * scale) / 2, (height - HEIGHT * scale) / 2)
        cr.scale(scale, scale)
        anim = self.animated
        t = self._t if anim else 0.0
        look = LOOK[self.state]
        fur = PLUM_DARK_FUR if self.dark else PLUM_900
        line = ROSE_250 if self.dark else PLUM_900
        detail = ROSE_250 if self.dark else ROSE_300
        width_line = 3.0 if self.high_contrast else 2.0
        cr.set_line_join(1)                     # ROUND
        cr.set_line_cap(1)

        def fill_stroke(color, outline=True):
            cr.set_source_rgb(*color)
            if outline:
                cr.fill_preserve()
                cr.set_source_rgb(*line)
                cr.set_line_width(width_line)
                cr.stroke()
            else:
                cr.fill()

        def ellipse(cx, cy, rx, ry):
            cr.save()
            cr.translate(cx, cy)
            cr.scale(rx, ry)
            cr.new_sub_path()
            cr.arc(0, 0, 1, 0, 2 * math.pi)
            cr.restore()

        breath = 1.0 + (0.018 * math.sin(t * 1.9) if anim else 0.0)
        if self.state == "sleep" and anim:
            breath = 1.0 + 0.03 * math.sin(t * 1.2)

        # Coda, dietro al corpo: ondeggia piano; nervosa mentre pensa.
        # Ruota verso l'esterno, mai sopra il corpo.
        speed, amount = (3.2, 0.28) if self.state in ("think", "hear") else (1.1, 0.2)
        swing = 0.12 + amount * math.sin(t * speed) if anim and self.state != "sleep" else 0.0
        cr.save()
        cr.translate(168, 232)
        cr.rotate(swing)
        cr.move_to(0, 0)
        cr.curve_to(48, -6, 52, -60, 30, -96)
        cr.curve_to(24, -108, 40, -116, 46, -104)
        cr.restore()
        cr.set_source_rgb(*line)
        cr.set_line_width(17 + 2 * width_line)
        cr.stroke_preserve()
        cr.set_source_rgb(*fur)
        cr.set_line_width(17)
        cr.stroke()

        # Corpo, petto bianco e zampe.
        cr.save()
        cr.translate(120, 245)
        cr.scale(1.0, breath)
        cr.translate(-120, -245)
        ellipse(120, 192, 64, 56)
        fill_stroke(fur)
        ellipse(120, 188, 29, 40)
        fill_stroke(CREAM, outline=self.dark)
        cr.restore()

        # Il libro, aperto davanti alle zampe: copertina prugna, pagine crema.
        cr.move_to(64, 246)
        cr.line_to(120, 252)
        cr.line_to(176, 246)
        cr.line_to(176, 256)
        cr.line_to(120, 261)
        cr.line_to(64, 256)
        cr.close_path()
        fill_stroke(PLUM_600)
        cr.move_to(70, 240)
        cr.curve_to(90, 236, 108, 240, 120, 247)
        cr.curve_to(132, 240, 150, 236, 170, 240)
        cr.line_to(170, 247)
        cr.curve_to(150, 244, 132, 247, 120, 253)
        cr.curve_to(108, 247, 90, 244, 70, 247)
        cr.close_path()
        fill_stroke(CREAM)
        cr.set_source_rgb(*ROSE_300)
        cr.set_line_width(1.2)
        for i in range(3):
            y = 241.5 + i * 2.2
            cr.move_to(78, y)
            cr.curve_to(92, y - 3, 106, y - 1, 116, y + 4)
            cr.move_to(162, y)
            cr.curve_to(148, y - 3, 134, y - 1, 124, y + 4)
        cr.stroke()
        for x in (96, 144):
            ellipse(x, 242, 15, 9)
            fill_stroke(CREAM)

        # Testa.
        head_y = 100 + (1.5 * math.sin(t * 1.9) if anim else 0.0)
        if self.state == "sleep":
            head_y += 6
        cr.save()
        cr.translate(0, head_y - 100)

        # Orecchie: di traverso quando e' scontroso, dritte quando ascolta.
        e = look["ears"]
        if anim and self.state == "listen":
            e = min(1.0, e + 0.04 * math.sin(t * 6))
        for side in (-1, 1):
            base_out = (120 + side * 54, 82)
            base_in = (120 + side * 16, 56)
            tip = (120 + side * (70 - 22 * e), 36 - 22 * e)
            cr.move_to(*base_out)
            cr.line_to(*tip)
            cr.line_to(*base_in)
            cr.close_path()
            fill_stroke(fur)
            cr.move_to(base_out[0] - side * 10, base_out[1] - 6)
            cr.line_to(tip[0] - side * 3, tip[1] + 12)
            cr.line_to(base_in[0] + side * 6, base_in[1] + 4)
            cr.close_path()
            cr.set_source_rgb(*ROSE_300)
            cr.fill()

        ellipse(120, 100, 60, 50)
        fill_stroke(fur)
        # Muso bianco.
        ellipse(108, 130, 17, 13)
        ellipse(132, 130, 17, 13)
        cr.set_source_rgb(*CREAM)
        cr.fill()

        # Occhi, con le palpebre: a meta' per lo sguardo cinico.
        lid = look["lid"]
        if anim and self.state not in ("sleep",) and self._blink_at <= self._t <= self._blink_at + 0.16:
            lid = 1.0
        gx, gy = look["gaze"]
        for side in (-1, 1):
            cx, cy = 120 + side * 22, 100
            rx, ry = 14, 11 if self.state != "listen" else 13
            if lid >= 0.99:
                cr.move_to(cx - rx, cy + 1)
                cr.curve_to(cx - rx / 2, cy + 7, cx + rx / 2, cy + 7, cx + rx, cy + 1)
                cr.set_source_rgb(*detail)
                cr.set_line_width(2.5)
                cr.stroke()
                continue
            ellipse(cx, cy, rx, ry)
            cr.set_source_rgb(*AMBER)
            cr.fill_preserve()
            cr.save()
            cr.clip()
            cr.set_source_rgb(*PLUM_900)
            ellipse(cx + gx, cy + gy, look["pupil"] / 2 + 0.5, ry - 1.5)
            cr.fill()
            ellipse(cx + gx - 2, cy + gy - 4, 1.8, 1.8)
            cr.set_source_rgb(*CREAM)
            cr.fill()
            if lid > 0:
                cr.rectangle(cx - rx - 2, cy - ry - 2, 2 * rx + 4, (2 * ry + 2) * lid + 2)
                cr.set_source_rgb(*fur)
                cr.fill()
            cr.restore()
            if lid > 0:
                y = cy - ry + 2 * ry * lid
                cr.move_to(cx - rx + 2, y + side * 0.5)
                cr.line_to(cx + rx - 2, y - side * 0.5)
                cr.set_source_rgb(*detail)
                cr.set_line_width(2)
                cr.stroke()
            ellipse(cx, cy, rx, ry)
            cr.set_source_rgb(*detail)
            cr.set_line_width(1.5)
            cr.stroke()

        # Sopracciglia: corrucciate verso il centro, o alzate.
        b = look["brow"]
        for side in (-1, 1):
            inner_y = 84 - 4 * b + (4 if b < 0.3 else 0)
            outer_y = 80 - 6 * b
            cr.move_to(120 + side * 10, inner_y)
            cr.line_to(120 + side * 34, outer_y)
            cr.set_source_rgb(*detail)
            cr.set_line_width(3)
            cr.stroke()

        # Occhiali tondi.
        cr.set_source_rgb(*(CREAM if self.dark else ROSE_250))
        cr.set_line_width(2.6)
        for side in (-1, 1):
            cr.new_sub_path()
            cr.arc(120 + side * 22, 101, 17.5, 0, 2 * math.pi)
        cr.stroke()
        cr.move_to(115.5, 99)
        cr.curve_to(118, 96, 122, 96, 124.5, 99)
        cr.move_to(120 - 39.5, 98)
        cr.line_to(120 - 58, 93)
        cr.move_to(120 + 39.5, 98)
        cr.line_to(120 + 58, 93)
        cr.stroke()

        # Naso e bocca.
        cr.move_to(113, 119)
        cr.line_to(127, 119)
        cr.line_to(120, 126)
        cr.close_path()
        cr.set_source_rgb(*ROSE_300)
        cr.fill_preserve()
        cr.set_source_rgb(*PLUM_900)
        cr.set_line_width(1.2)
        cr.stroke()
        m = self._mouth()
        if m > 0.04:
            ellipse(120, 133 + 3 * m, 6 + 5 * m, 2 + 9 * m)
            cr.set_source_rgb(*PLUM_900)
            cr.fill_preserve()
            cr.save()
            cr.clip()
            ellipse(120, 140 + 5 * m, 7 + 3 * m, 4 + 3 * m)
            cr.set_source_rgb(*ROSE_300)
            cr.fill()
            cr.restore()
        else:
            # Chiusa: una «w» che scende ai lati (il broncio).
            cr.move_to(120, 126)
            cr.line_to(120, 130)
            cr.curve_to(117, 135, 111, 135, 107, 133 if self.state == "listen" else 137)
            cr.move_to(120, 130)
            cr.curve_to(123, 135, 129, 135, 133, 133 if self.state == "listen" else 137)
            cr.set_source_rgb(*PLUM_900)
            cr.set_line_width(2)
            cr.stroke()

        # Baffi.
        cr.set_source_rgb(*detail)
        cr.set_line_width(1.4)
        for side in (-1, 1):
            for dy, end in ((-4, -10), (0, 0), (4, 10)):
                x0 = 120 + side * 24
                cr.move_to(x0, 128 + dy)
                cr.curve_to(x0 + side * 20, 126 + dy + end * 0.3, x0 + side * 36,
                            127 + dy + end * 0.6, x0 + side * 50, 128 + dy + end)
        cr.stroke()
        cr.restore()

        # Segni accanto alla testa.
        if self.state == "listen":
            lvl = self.level if anim else max(self.level, 0.35)
            cr.set_source_rgb(*line)
            cr.set_line_width(3)
            for i in range(3):
                if lvl < 0.12 + 0.28 * i:
                    break
                r = 12 + 10 * i
                cr.new_sub_path()
                cr.arc(204, 44, r, -0.9, 0.7)
                cr.stroke()
            cr.new_sub_path()
            cr.arc(204, 44, 3.5, 0, 2 * math.pi)
            cr.fill()
        elif self.state in ("think", "hear"):
            for i, (x, y, r) in enumerate(((180, 52, 4.5), (196, 36, 6.5), (215, 18, 8.5))):
                alpha = 1.0
                if anim:
                    alpha = 0.35 + 0.65 * max(0.0, math.sin(t * 4 - i * 0.9))
                cr.set_source_rgba(*line, alpha)
                cr.new_sub_path()
                cr.arc(x, y, r, 0, 2 * math.pi)
                cr.fill()
        elif self.state == "sleep":
            cr.set_source_rgb(*line)
            cr.select_font_face("sans-serif", 0, 1)
            for i, size in enumerate((16, 21, 26)):
                drift = ((t * 0.6 + i / 3) % 1.0) if anim else i / 3
                cr.set_font_size(size)
                cr.move_to(178 + 14 * i + 6 * drift, 58 - 18 * i - 8 * drift)
                cr.show_text("z")
