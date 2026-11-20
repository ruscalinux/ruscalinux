# RuscaPinball — rp_sound.py — 1.99.3 — GPL-3.0-or-later
# Copyright (C) 2026 Nunzio Curcuruto <info@ruscalinux.org>
#
# Effetti sonori sintetizzati all'avvio, in stile "beeper" degli anni '80:
# onde quadre e rumore, nessun file audio. Se l'audio non è disponibile il
# gioco resta muto e non si ferma.

import array
import math
import random

import pygame

RATE = 22050


def _square(f, t):
    return 1.0 if math.sin(2 * math.pi * f * t) >= 0 else -1.0


def _tri(f, t):
    p = (f * t) % 1.0
    return 4 * p - 1 if p < 0.5 else 3 - 4 * p


class Sounds:
    def __init__(self, enabled=True):
        self.enabled = enabled
        self.ok = False
        self.bank = {}
        try:
            if not pygame.mixer.get_init():
                pygame.mixer.init(RATE, -16, 1, 512)
            freq, size, channels = pygame.mixer.get_init()
            if size != -16:
                return
            self.rate, self.channels = freq, channels
            pygame.mixer.set_num_channels(12)
            self._build()
            self.ok = True
        except (pygame.error, TypeError, ValueError):
            self.ok = False

    def _make(self, dur, gen, vol=0.35):
        n = int(self.rate * dur)
        buf = array.array("h")
        for i in range(n):
            t = i / self.rate
            v = gen(t, t / dur) * vol
            v = max(-1.0, min(1.0, v))
            s = int(v * 32000)
            for _ in range(self.channels):
                buf.append(s)
        return pygame.mixer.Sound(buffer=buf.tobytes())

    def _build(self):
        rnd = random.Random(1989)
        noise = [rnd.uniform(-1, 1) for _ in range(4096)]

        def nz(t, f=1.0):
            return noise[int(t * self.rate * f) % 4096]

        def env(p, k=3.0):
            return (1.0 - p) ** k

        def sweep(f0, f1, dur):
            # fase integrata, così la frequenza scivola senza scatti
            k = math.log(f1 / f0)
            c = 2 * math.pi * f0 * dur / k
            return lambda t, p: (1.0 if math.sin(c * (math.exp(k * p) - 1)) >= 0
                                 else -1.0) * env(p, 1.5)

        def seq(notes, wave=_square):
            step = 1.0 / len(notes)
            return lambda t, p: wave(notes[min(int(p / step), len(notes) - 1)], t) * \
                env((p % step) / step, 0.8)

        mk = self._make
        self.bank = {
            "bumper": mk(0.09, sweep(900, 450, 0.09), 0.30),
            "sling": mk(0.06, lambda t, p: _square(330, t) * env(p), 0.28),
            "flipper": mk(0.04, lambda t, p: nz(t, 0.5) * env(p, 2), 0.25),
            "drop": mk(0.08, lambda t, p: _tri(990, t) * env(p), 0.45),
            "rusca": mk(0.16, seq([880, 1320]), 0.25),
            "lane": mk(0.05, lambda t, p: _square(1250, t) * env(p), 0.18),
            "launch": mk(0.28, lambda t, p: nz(t, 0.3 + p) * env(p, 1.2), 0.30),
            "drain": mk(0.7, sweep(440, 90, 0.7), 0.25),
            "tick": mk(0.025, lambda t, p: _square(1500, t) * env(p), 0.15),
            "complete": mk(0.36, seq([523, 659, 784, 1047, 1319, 1568]), 0.22),
            "extra": mk(0.6, seq([784, 988, 1175, 1568, 1175, 1568]), 0.22),
            "tilt": mk(0.6, lambda t, p: _square(110, t) * env(p, 0.6), 0.25),
            "warn": mk(0.15, lambda t, p: _square(180, t) * env(p, 0.6), 0.25),
            "start": mk(0.5, seq([392, 523, 659, 784]), 0.22),
            "save": mk(0.3, seq([659, 523, 659]), 0.22),
            # trappola del bonus: la pallina cade nella buca, poi il calcio
            "trap": mk(0.32, seq([784, 659, 523, 392], _tri), 0.40),
            "kick": mk(0.12, lambda t, p: nz(t, 0.6) * env(p, 1.5) * 0.7
                       + _square(140, t) * env(p, 2) * 0.5, 0.35),
        }

    def play(self, name):
        if self.ok and self.enabled and name in self.bank:
            self.bank[name].play()
