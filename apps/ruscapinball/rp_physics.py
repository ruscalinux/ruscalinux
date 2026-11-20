# RuscaPinball — rp_physics.py — 1.99.3 — GPL-3.0-or-later
# Copyright (C) 2026 Nunzio Curcuruto <info@ruscalinux.org>
#
# Fisica 2D del flipper: pallina, pareti (segmenti con spessore), bumper
# (cerchi), flipper (capsule rastremate che ruotano attorno al perno).
# Modulo puro, senza pygame: si prova da solo (tests/test_physics.py).

import math

GRAVITY = 1150.0      # px/s², gravità lungo il piano inclinato
BALL_R = 9.0          # raggio della pallina in px
MAX_SPEED = 2300.0    # velocità massima, evita che la pallina "salti" le pareti
DAMPING = 0.05        # attrito di rotolamento, frazione persa al secondo
KICK_MIN = 40.0       # velocità d'urto minima perché bumper e slingshot scattino
EVENT_MIN = 25.0      # velocità d'urto minima per segnalare un colpo


class Ball:
    __slots__ = ("x", "y", "vx", "vy", "r")

    def __init__(self, x, y, vx=0.0, vy=0.0, r=BALL_R):
        self.x, self.y, self.vx, self.vy, self.r = x, y, vx, vy, r

    @property
    def speed(self):
        return math.hypot(self.vx, self.vy)


def _resolve(ball, nx, ny, vn, e, kick, friction):
    """Rimbalzo su una superficie ferma con normale (nx, ny); vn < 0."""
    tx, ty = ball.vx - vn * nx, ball.vy - vn * ny
    out = -vn * e
    if kick > 0.0 and -vn > KICK_MIN:
        out = max(out, kick)
    k = 1.0 - friction
    ball.vx = tx * k + nx * out
    ball.vy = ty * k + ny * out


class Segment:
    """Parete: segmento da a a b con spessore e, se serve, un solo verso.

    one_way è la normale del lato da cui la parete blocca; dall'altro lato
    la pallina passa (cancelletto della corsia di lancio)."""

    __slots__ = ("ax", "ay", "bx", "by", "dx", "dy", "len2", "thick", "e",
                 "kick", "friction", "tag", "active", "one_way", "box")

    def __init__(self, a, b, thick=2.0, e=0.45, kick=0.0, tag=None,
                 one_way=None, friction=0.01):
        self.thick, self.e, self.kick, self.tag = thick, e, kick, tag
        self.friction, self.active = friction, True
        self.one_way = None
        if one_way is not None:
            n = math.hypot(*one_way)
            self.one_way = (one_way[0] / n, one_way[1] / n)
        self.move(a, b)

    def move(self, a, b):
        self.ax, self.ay = float(a[0]), float(a[1])
        self.bx, self.by = float(b[0]), float(b[1])
        self.dx, self.dy = self.bx - self.ax, self.by - self.ay
        self.len2 = max(self.dx * self.dx + self.dy * self.dy, 1e-9)
        m = self.thick + BALL_R + 2.0
        self.box = (min(self.ax, self.bx) - m, min(self.ay, self.by) - m,
                    max(self.ax, self.bx) + m, max(self.ay, self.by) + m)

    def collide(self, ball, events):
        if not self.active:
            return
        x0, y0, x1, y1 = self.box
        if ball.x < x0 or ball.x > x1 or ball.y < y0 or ball.y > y1:
            return
        if self.one_way is not None:
            wx, wy = self.one_way
            if (ball.x - self.ax) * wx + (ball.y - self.ay) * wy < 0.0:
                return
        t = ((ball.x - self.ax) * self.dx + (ball.y - self.ay) * self.dy) / self.len2
        t = 0.0 if t < 0.0 else 1.0 if t > 1.0 else t
        ox = ball.x - (self.ax + self.dx * t)
        oy = ball.y - (self.ay + self.dy * t)
        rr = ball.r + self.thick
        d2 = ox * ox + oy * oy
        if d2 >= rr * rr:
            return
        d = math.sqrt(d2)
        if d < 1e-6:
            if self.one_way is not None:
                nx, ny = self.one_way
            else:
                ln = math.sqrt(self.len2)
                nx, ny = -self.dy / ln, self.dx / ln
        else:
            nx, ny = ox / d, oy / d
        pen = rr - d
        ball.x += nx * pen
        ball.y += ny * pen
        vn = ball.vx * nx + ball.vy * ny
        if vn < 0.0:
            _resolve(ball, nx, ny, vn, self.e, self.kick, self.friction)
            if self.tag is not None and -vn > EVENT_MIN:
                events.append((self.tag, -vn))


class Circle:
    """Bumper o paletto rotondo."""

    __slots__ = ("x", "y", "r", "e", "kick", "tag", "active")

    def __init__(self, x, y, r, e=0.5, kick=0.0, tag=None):
        self.x, self.y, self.r = float(x), float(y), float(r)
        self.e, self.kick, self.tag, self.active = e, kick, tag, True

    def collide(self, ball, events):
        if not self.active:
            return
        ox, oy = ball.x - self.x, ball.y - self.y
        rr = ball.r + self.r
        d2 = ox * ox + oy * oy
        if d2 >= rr * rr:
            return
        d = math.sqrt(d2)
        if d < 1e-6:
            nx, ny = 0.0, -1.0
        else:
            nx, ny = ox / d, oy / d
        ball.x = self.x + nx * rr
        ball.y = self.y + ny * rr
        vn = ball.vx * nx + ball.vy * ny
        if vn < 0.0:
            _resolve(ball, nx, ny, vn, self.e, self.kick, 0.0)
            if self.tag is not None and -vn > EVENT_MIN:
                events.append((self.tag, -vn))


class Flipper:
    """Flipper: capsule rastremata che ruota attorno al perno.

    Gli angoli sono in radianti, con l'asse y verso il basso (come lo
    schermo): 0 punta a destra, pi/2 in basso."""

    UP_SPEED = 26.0     # rad/s quando si preme
    DOWN_SPEED = 15.0   # rad/s quando si rilascia

    def __init__(self, px, py, length, rest, up, r0=11.0, r1=6.0, e=0.3,
                 tag="flipper"):
        self.px, self.py, self.length = float(px), float(py), float(length)
        self.rest, self.up = rest, up
        self.r0, self.r1, self.e, self.tag = r0, r1, e, tag
        self.angle, self.omega, self.pressed = rest, 0.0, False

    def update(self, h):
        target = self.up if self.pressed else self.rest
        speed = self.UP_SPEED if self.pressed else self.DOWN_SPEED
        diff = target - self.angle
        step = speed * h
        new = target if abs(diff) <= step else self.angle + math.copysign(step, diff)
        self.omega = (new - self.angle) / h
        self.angle = new

    def tip(self):
        return (self.px + math.cos(self.angle) * self.length,
                self.py + math.sin(self.angle) * self.length)

    def outline(self, steps=8):
        """Contorno del flipper come poligono, per disegnarlo."""
        a = self.angle
        tx, ty = self.tip()
        pts = []
        for i in range(steps + 1):
            t = a + math.pi / 2 + math.pi * i / steps
            pts.append((self.px + math.cos(t) * self.r0, self.py + math.sin(t) * self.r0))
        for i in range(steps + 1):
            t = a - math.pi / 2 + math.pi * i / steps
            pts.append((tx + math.cos(t) * self.r1, ty + math.sin(t) * self.r1))
        return pts

    def collide(self, ball, events):
        c, s = math.cos(self.angle), math.sin(self.angle)
        rx, ry = ball.x - self.px, ball.y - self.py
        reach = self.length + self.r0 + ball.r
        if rx * rx + ry * ry > reach * reach:
            return
        t = (rx * c + ry * s) / self.length
        t = 0.0 if t < 0.0 else 1.0 if t > 1.0 else t
        qx = self.px + c * self.length * t
        qy = self.py + s * self.length * t
        rad = self.r0 + (self.r1 - self.r0) * t
        ox, oy = ball.x - qx, ball.y - qy
        rr = ball.r + rad
        d2 = ox * ox + oy * oy
        if d2 >= rr * rr:
            return
        d = math.sqrt(d2)
        if d < 1e-6:
            nx, ny = s, -c
        else:
            nx, ny = ox / d, oy / d
        pen = rr - d
        ball.x += nx * pen
        ball.y += ny * pen
        # velocità della superficie del flipper nel punto di contatto
        cx, cy = qx + nx * rad - self.px, qy + ny * rad - self.py
        svx, svy = -self.omega * cy, self.omega * cx
        vn = (ball.vx - svx) * nx + (ball.vy - svy) * ny
        if vn < 0.0:
            j = -(1.0 + self.e) * vn
            ball.vx += j * nx
            ball.vy += j * ny
            if -vn > EVENT_MIN:
                events.append((self.tag, -vn))


class World:
    def __init__(self):
        self.segments, self.circles, self.flippers = [], [], []

    def step(self, ball, dt, substeps=10):
        """Avanza di dt secondi; restituisce i colpi [(tag, velocità)]."""
        events = []
        h = dt / substeps
        damp = 1.0 - DAMPING * h
        for _ in range(substeps):
            for f in self.flippers:
                f.update(h)
            if ball is None:
                continue
            ball.vy += GRAVITY * h
            ball.vx *= damp
            ball.vy *= damp
            sp = ball.vx * ball.vx + ball.vy * ball.vy
            if sp > MAX_SPEED * MAX_SPEED:
                k = MAX_SPEED / math.sqrt(sp)
                ball.vx *= k
                ball.vy *= k
            ball.x += ball.vx * h
            ball.y += ball.vy * h
            for seg in self.segments:
                seg.collide(ball, events)
            for cir in self.circles:
                cir.collide(ball, events)
            for f in self.flippers:
                f.collide(ball, events)
        return events
