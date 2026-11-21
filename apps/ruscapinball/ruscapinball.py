#!/usr/bin/env python3
# RuscaPinball — ruscapinball.py — 1.99.3 — GPL-3.0-or-later
# Copyright (C) 2026 Nunzio Curcuruto <info@ruscalinux.org>
#
# Flipper in stile anni '80 per RuscaLinux. Tavolo, grafica e suoni originali.
#
# This program is free software: you can redistribute it and/or modify it
# under the terms of the GNU General Public License as published by the Free
# Software Foundation, either version 3 of the License, or (at your option)
# any later version. See <https://www.gnu.org/licenses/gpl-3.0.html>.

import json
import math
import os
import random
import sys

APP_ID = "org.ruscalinux.RuscaPinball"
APP_NAME = "RuscaPinball"
APP_VERSION = "1.99.3"
BASE_DIR = os.path.dirname(os.path.realpath(__file__))   # /usr/share/ruscapinball
LANG_DIR = os.path.join(BASE_DIR, "lang")
sys.path.insert(0, BASE_DIR)

# Nome della finestra uguale all'App ID, perché GNOME la associ all'icona.
for _var in ("SDL_VIDEO_X11_WMCLASS", "SDL_VIDEO_WAYLAND_WMCLASS", "SDL_APP_ID"):
    os.environ.setdefault(_var, APP_ID)
os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")

import pygame  # noqa: E402

import rp_table as T  # noqa: E402
from rp_physics import Ball  # noqa: E402
from rp_sound import Sounds  # noqa: E402

import rp_view as V  # noqa: E402
from rp_view import (AMETISTA_300, AMETISTA_500, BORDER,  # noqa: E402
                     CREMA, PRUGNA_600, PRUGNA_750, PRUGNA_900, ROSA_200,
                     ROSA_250, ROSA_300)

SCREEN_W, SCREEN_H = V.SCREEN_W, V.SCREEN_H
FPS = 60
STEP = 1.0 / 120.0          # passo fisso della fisica
SUBSTEPS = 5

BALLS_PER_GAME = 3
BALL_SAVE_SECONDS = 6.0
MAX_EXTRA_BALLS = 2
BONUS_UNIT = 1000            # valore di ogni lampada dell'anello del bonus
SPECIAL_POINTS = 25000
ATTRACT_CYCLE, ATTRACT_PANEL = 15.0, 9.0   # secondi: ciclo e pannello nella vetrina
LAUNCH_MIN, LAUNCH_RANGE = 500.0, 1700.0

KEYS_LEFT = (pygame.K_z, pygame.K_LSHIFT, pygame.K_LCTRL, pygame.K_LEFT)
KEYS_RIGHT = (pygame.K_m, pygame.K_RSHIFT, pygame.K_RCTRL, pygame.K_RIGHT)
KEYS_PLUNGER = (pygame.K_SPACE, pygame.K_DOWN)
KEYS_NUDGE = (pygame.K_n,)
# pulsanti dei gamepad più comuni (disposizione Xbox con SDL)
JOY_LEFT, JOY_RIGHT, JOY_PLUNGER, JOY_NUDGE, JOY_START = (4,), (5,), (0, 1), (3,), (7, 9)


# ── Lingue (specifiche, sezione 9) ─────────────────────────────────────────
LANG_ALIASES = {"zh_HK": "zh_TW", "zh_MO": "zh_TW", "zh_SG": "zh_CN", "zh": "zh_CN",
                "pt": "pt_BR", "sk": "cs"}


def system_languages():
    """Lingue di sistema nello stesso ordine di GLib/GTK."""
    names = []
    if os.environ.get("LANGUAGE"):
        names.extend(os.environ["LANGUAGE"].split(":"))
    for var in ("LC_ALL", "LC_MESSAGES", "LANG"):
        if os.environ.get(var):
            names.append(os.environ[var])
            break
    return [n for n in names if n and n not in ("C", "POSIX")]


def pick_language(available):
    for name in system_languages():
        base = name.split(".")[0].split("@")[0]
        lang = base.split("_")[0]
        for code in (base, LANG_ALIASES.get(base), lang, LANG_ALIASES.get(lang)):
            if code in available:
                return code
    return "en"


class I18n:
    def __init__(self):
        available = set()
        if os.path.isdir(LANG_DIR):
            available = {f[:-5] for f in os.listdir(LANG_DIR) if f.endswith(".json")}
        self.code = pick_language(available)
        self.fallback = self._load("en")
        self.strings = self._load(self.code) if self.code != "en" else self.fallback

    @staticmethod
    def _load(code):
        try:
            with open(os.path.join(LANG_DIR, code + ".json"), encoding="utf-8") as fh:
                return json.load(fh)
        except (OSError, ValueError):
            return {}

    def __call__(self, key, **kw):
        text = self.strings.get(key) or self.fallback.get(key) or key
        try:
            return text.format(**kw) if kw else text
        except (KeyError, IndexError, ValueError):
            return text


# ── Dati e impostazioni dell'utente ────────────────────────────────────────
def _xdg(var, default):
    base = os.environ.get(var) or os.path.join(os.path.expanduser("~"), default)
    return os.path.join(base, "ruscapinball")


DATA_DIR = _xdg("XDG_DATA_HOME", ".local/share")
CONFIG_DIR = _xdg("XDG_CONFIG_HOME", ".config")


def _read_json(path, default):
    try:
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return default


def _write_json(path, value):
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        tmp = path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump(value, fh, ensure_ascii=False, indent=1)
        os.replace(tmp, path)
    except OSError as err:
        print(f"{APP_NAME}: impossibile salvare {path}: {err}", file=sys.stderr)


class Scores:
    PATH = os.path.join(DATA_DIR, "scores.json")
    DEFAULT = [["RUSCA", 50000], ["LINUX", 40000], ["DEBIAN", 30000],
               ["GNOME", 20000], ["TUX", 10000]]

    def __init__(self):
        data = _read_json(self.PATH, None)
        try:
            self.table = sorted(([str(n)[:10], int(s)] for n, s in data),
                                key=lambda e: -e[1])[:5]
        except (TypeError, ValueError):
            self.table = []
        if not self.table:
            self.table = [list(e) for e in self.DEFAULT]

    def qualifies(self, score):
        return score > 0 and (len(self.table) < 5 or score > self.table[-1][1])

    def add(self, name, score):
        self.table.append([name[:10] or "?", score])
        self.table.sort(key=lambda e: -e[1])
        del self.table[5:]
        _write_json(self.PATH, self.table)


class Settings:
    PATH = os.path.join(CONFIG_DIR, "settings.json")

    def __init__(self):
        data = _read_json(self.PATH, {})
        self.sound = bool(data.get("sound", True)) if isinstance(data, dict) else True
        self.scanlines = bool(data.get("scanlines", False)) if isinstance(data, dict) else False

    def save(self):
        _write_json(self.PATH, {"sound": self.sound, "scanlines": self.scanlines})


# ── Disegno ────────────────────────────────────────────────────────────────
def text(surf, fnt, s, color, aa=True, **anchor):
    img = fnt.render(s, aa, color)
    rect = img.get_rect(**anchor)
    surf.blit(img, rect)
    return rect


def fit(fonts, keys, s, width):
    """Il carattere più grande fra keys in cui s sta in width (lingue lunghe)."""
    for k in keys:
        if fonts[k].size(s)[0] <= width:
            return fonts[k]
    return fonts[keys[-1]]


def make_icon(size=64):
    """Icona della finestra, disegnata (stessa idea dell'SVG)."""
    s = pygame.Surface((size, size), pygame.SRCALPHA)
    k = size / 64
    pygame.draw.rect(s, AMETISTA_500, (2 * k, 2 * k, 60 * k, 60 * k), border_radius=int(14 * k))
    pygame.draw.rect(s, PRUGNA_900, (8 * k, 14 * k, 48 * k, 44 * k), border_radius=int(8 * k))
    pygame.draw.line(s, CREMA, (14 * k, 44 * k), (28 * k, 51 * k), int(6 * k))
    pygame.draw.line(s, CREMA, (50 * k, 44 * k), (36 * k, 51 * k), int(6 * k))
    pygame.draw.circle(s, ROSA_300, (32 * k, 27 * k), 7 * k)
    pygame.draw.circle(s, CREMA, (30 * k, 25 * k), 2.5 * k)
    return s


def make_scanlines():
    s = pygame.Surface((SCREEN_W, SCREEN_H), pygame.SRCALPHA)
    for y in range(0, SCREEN_H, 3):
        pygame.draw.line(s, (0, 0, 0, 70), (0, y), (SCREEN_W, y))
    return s


# ── Gioco ──────────────────────────────────────────────────────────────────
class AutoPlayer:
    """Gioca da solo nella modalità dimostrativa."""

    def __init__(self):
        self.timers = {}

    def update(self, table, ball, dt):
        for f in (table.left, table.right):
            hold, cool = self.timers.get(id(f), (0.0, 0.0))
            hold -= dt
            cool -= dt
            dx, dy = ball.x - f.px, ball.y - f.py
            along = dx if f is table.left else -dx
            near = (math.hypot(dx, dy) < T.FLIP_LEN + 12 and -35 < dy < 30
                    and along > random.uniform(10, 50))
            if near and cool <= 0 and hold <= 0 and ball.vy > -30 and random.random() > 0.08:
                hold, cool = 0.18, 0.45
            f.pressed = hold > 0
            self.timers[id(f)] = (hold, cool)


class Game:
    def __init__(self, screen, i18n, sounds, scores, settings):
        self.screen, self.t, self.snd = screen, i18n, sounds
        self.scores, self.settings = scores, settings
        F = V.font
        self.fonts = {
            # fondo del tavolo e HUD: caratteri a blocchi, senza sfumature
            "table_title": F(34), "table_small": F(13), "lamp": F(13),
            "lamp_small": F(11), "letter": F(15),
            "hud_big": F(30), "hud": F(18), "hud_small": F(14), "hud_tiny": F(12),
            "bumper": F(11),
            # pannelli con testo lungo: caratteri normali, leggibili
            "title": F(40, mono=False), "big": F(28, mono=False), "mid": F(19, mono=False),
            "text": F(16, bold=False, mono=False), "small": F(14, bold=False, mono=False),
            "tiny": F(10, mono=False), "score": F(28),
            "row": F(16),
        }
        self.layers = V.StaticLayers(self.fonts)
        self.world_surf = pygame.Surface((SCREEN_W, SCREEN_H))
        self.scan = make_scanlines()
        self.table = T.Table()
        self.auto = AutoPlayer()
        self.bumper_labels = {}
        self.acc = 0.0
        self.clock_t = 0.0
        self.paused = False
        self.info = False
        self.name = ""
        self.keys_left = self.keys_right = self.keys_plunger = False
        self.joy_left = self.joy_right = self.joy_plunger = False
        self.state = "attract"
        self.reset_game_vars()
        self.new_ball()

    # ── stato della partita ──
    def reset_game_vars(self):
        self.score = 0
        self.ball_num = 1
        self.balls_total = BALLS_PER_GAME
        self.letters = [False] * 5
        self.extra_balls = 0     # al massimo MAX_EXTRA_BALLS a partita
        self.messages = []
        self.flash = {}
        self.shake = 0.0

    def new_ball(self):
        self.ball = Ball(*T.BALL_START)
        self.pull = 0.0
        self.table.set_plunger(0.0)
        self.mult = 1
        self.bonus = 0
        self.special = False
        self.bumper_value = 100
        self.lanes = [False] * len(T.TOP_LANES)
        self.lane_cool = [0.0] * len(T.TOP_LANES)
        for seg in self.table.drops:
            seg.active = True
        self.drop_reset = 0.0
        self.letters_reset = 0.0
        self.tilt = False
        self.tilt_meter = 0.0
        self.launched = False
        self.save_until = 0.0
        self.extra_this_ball = False
        self.stuck = 0.0
        self.trapped = 0.0       # secondi che mancano al calcio della trappola
        self.power_until = 0.0   # fulmine: bumper doppi fino a quest'ora
        self.inlanes = [False, False]
        self.inlane_cool = 0.0
        self.rollover_cool = 0.0
        self.trap_cool = 0.0
        self.counting = None     # conteggio del bonus a fine pallina

    def start_game(self):
        self.state = "play"
        self.paused = False
        self.info = False
        self.reset_game_vars()
        self.new_ball()
        self.snd.play("start")
        self.say(self.t("msg_launch"), 3.0)

    def say(self, msg, secs=2.0):
        self.messages.append([msg, self.clock_t + secs])

    def add(self, points):
        if self.state == "play" and not self.tilt:
            self.score += points

    def advance_bonus(self, steps):
        if self.tilt:
            return
        before = self.bonus
        self.bonus = min(T.BONUS_MAX, self.bonus + steps)
        if self.bonus == T.BONUS_MAX and before < T.BONUS_MAX and not self.special:
            self.special = True
            if self.state == "play":
                self.say(self.t("msg_special_lit"), 2.5)
                self.snd.play("complete")

    def extra_pending(self):
        """Palline extra vinte e non ancora giocate (spia EXTRA)."""
        return self.balls_total - max(self.ball_num, BALLS_PER_GAME) > 0

    # ── comandi ──
    def flippers_input(self):
        left = self.keys_left or self.joy_left
        right = self.keys_right or self.joy_right
        if self.state != "play" or self.tilt or self.paused:
            left = right = False
        return left, right

    def on_flipper_press(self, side):
        if self.state != "play" or self.tilt or self.paused:
            return
        self.snd.play("flipper")
        # i flipper spostano la corsia accesa, come nei tavoli veri
        if side == "left":
            self.lanes = self.lanes[1:] + self.lanes[:1]
        else:
            self.lanes = self.lanes[-1:] + self.lanes[:-1]

    def nudge(self):
        if self.state != "play" or self.tilt or self.paused or self.counting or self.trapped:
            return
        if T.Table.in_lane(self.ball):
            return
        self.ball.vx += random.uniform(-90, 90)
        self.ball.vy -= random.uniform(60, 140)
        self.shake = 0.18
        self.tilt_meter += 1.0
        if self.tilt_meter >= 3.0:
            self.tilt = True
            self.bonus = 0
            self.special = False
            self.snd.play("tilt")
            self.say(self.t("msg_tilt"), 3.0)
        else:
            self.snd.play("warn")
            self.say(self.t("msg_warning"), 1.0)

    def release_plunger(self):
        ball = self.ball
        if self.pull > 0.05 and T.Table.on_plunger(ball) and not self.counting:
            ball.y = min(ball.y, T.LANE_FLOOR - ball.r - 1)
            ball.vy = -(LAUNCH_MIN + LAUNCH_RANGE * self.pull)
            ball.vx = 0.0
            self.snd.play("launch")
        self.pull = 0.0
        self.table.set_plunger(0.0)

    def handle(self, ev):
        if ev.type == pygame.KEYDOWN:
            if ev.key == pygame.K_q and ev.mod & pygame.KMOD_CTRL:
                return False
            if self.state == "entry":
                return self.handle_entry(ev)
            if ev.key == pygame.K_F2:
                self.settings.scanlines = not self.settings.scanlines
                self.settings.save()
                self.say(self.t("scan_on" if self.settings.scanlines else "scan_off"), 1.2)
            elif ev.key == pygame.K_F3:
                self.settings.sound = self.snd.enabled = not self.settings.sound
                self.settings.save()
                self.say(self.t("sound_on" if self.settings.sound else "sound_off"), 1.2)
            elif ev.key == pygame.K_F11:
                pygame.display.toggle_fullscreen()
            elif self.state == "attract":
                if self.info:
                    self.info = False
                elif ev.key == pygame.K_ESCAPE:
                    return False
                elif ev.key in (pygame.K_i, pygame.K_F1):
                    self.info = True
                elif ev.key in KEYS_PLUNGER or ev.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
                    self.start_game()
            elif self.state == "play":
                if ev.key == pygame.K_ESCAPE:
                    if self.paused:
                        self.to_attract()
                    else:
                        self.paused = True
                elif ev.key == pygame.K_p:
                    self.paused = not self.paused
                elif self.paused:
                    pass
                elif ev.key in KEYS_LEFT:
                    self.keys_left = True
                    self.on_flipper_press("left")
                elif ev.key in KEYS_RIGHT:
                    self.keys_right = True
                    self.on_flipper_press("right")
                elif ev.key in KEYS_PLUNGER:
                    self.keys_plunger = True
                elif ev.key in KEYS_NUDGE:
                    self.nudge()
            elif self.state == "gameover":
                if ev.key in KEYS_PLUNGER or ev.key in (pygame.K_RETURN, pygame.K_ESCAPE):
                    self.to_attract()
        elif ev.type == pygame.KEYUP:
            if ev.key in KEYS_LEFT:
                self.keys_left = False
            elif ev.key in KEYS_RIGHT:
                self.keys_right = False
            elif ev.key in KEYS_PLUNGER and self.keys_plunger:
                self.keys_plunger = False
                if not self.joy_plunger and self.state == "play":
                    self.release_plunger()
        elif ev.type == pygame.TEXTINPUT and self.state == "entry":
            for ch in ev.text:
                if ch.isprintable() and len(self.name) < 10:
                    self.name += ch.upper()
        elif ev.type == pygame.JOYBUTTONDOWN:
            b = ev.button
            if self.state == "attract" and (b in JOY_START or b in JOY_PLUNGER):
                self.info = False
                self.start_game()
            elif self.state == "gameover" and b in JOY_START + JOY_PLUNGER:
                self.to_attract()
            elif self.state == "play":
                if b in JOY_START:
                    self.paused = not self.paused
                elif b in JOY_LEFT:
                    self.joy_left = True
                    self.on_flipper_press("left")
                elif b in JOY_RIGHT:
                    self.joy_right = True
                    self.on_flipper_press("right")
                elif b in JOY_PLUNGER:
                    self.joy_plunger = True
                elif b in JOY_NUDGE:
                    self.nudge()
        elif ev.type == pygame.JOYBUTTONUP:
            b = ev.button
            if b in JOY_LEFT:
                self.joy_left = False
            elif b in JOY_RIGHT:
                self.joy_right = False
            elif b in JOY_PLUNGER and self.joy_plunger:
                self.joy_plunger = False
                if not self.keys_plunger and self.state == "play":
                    self.release_plunger()
        elif ev.type == pygame.JOYDEVICEADDED:
            try:
                pygame.joystick.Joystick(ev.device_index).init()
            except pygame.error:
                pass
        elif ev.type == pygame.WINDOWFOCUSLOST and self.state == "play":
            self.paused = True
            self.keys_left = self.keys_right = self.keys_plunger = False
        return True

    def handle_entry(self, ev):
        if ev.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
            self.scores.add(self.name.strip() or self.t("default_player"), self.score)
            pygame.key.stop_text_input()
            self.state = "gameover"
            self.gameover_until = self.clock_t + 6.0
        elif ev.key == pygame.K_BACKSPACE:
            self.name = self.name[:-1]
        elif ev.key == pygame.K_ESCAPE:
            self.name = ""
        return True

    def to_attract(self):
        self.state = "attract"
        self.paused = False
        self.reset_game_vars()
        self.new_ball()

    # ── aggiornamento ──
    def update(self, dt):
        self.clock_t += dt
        self.messages = [m for m in self.messages if m[1] > self.clock_t]
        for k in list(self.flash):
            self.flash[k] -= dt
            if self.flash[k] <= 0:
                del self.flash[k]
        self.shake = max(0.0, self.shake - dt)
        if self.paused or self.info and self.state != "attract":
            return
        if self.state in ("entry", "gameover"):
            if self.state == "gameover" and self.clock_t > self.gameover_until:
                self.to_attract()
            self.acc = 0.0
            self.table.left.pressed = self.table.right.pressed = False
            self.table.world.step(None, dt, 2)
            return
        self.acc += dt
        while self.acc >= STEP:
            self.acc -= STEP
            self.tick(STEP)

    def tick(self, dt):
        table, ball = self.table, self.ball
        if self.state == "attract":
            self.auto.update(table, ball, dt)
            if T.Table.on_plunger(ball) and abs(ball.vy) < 5:
                ball.vy = -(LAUNCH_MIN + LAUNCH_RANGE * random.uniform(0.55, 1.0))
        else:
            table.left.pressed, table.right.pressed = self.flippers_input()
            if (self.keys_plunger or self.joy_plunger) and not self.counting:
                self.pull = min(1.0, self.pull + dt * 1.2)
                table.set_plunger(self.pull)
        self.tilt_meter = max(0.0, self.tilt_meter - dt / 3.0)

        if self.counting is not None:
            table.world.step(None, dt, SUBSTEPS)
            self.count_bonus(dt)
            return

        # pallina nella trappola: aspetta e poi la ributta in campo
        if self.trapped:
            table.world.step(None, dt, SUBSTEPS)
            self.trapped = max(0.0, self.trapped - dt)
            if not self.trapped:
                T.Table.kick_from_trap(ball, random.uniform(-60, 60))
                self.trap_cool = 0.6
                self.snd.play("kick")
            return
        self.trap_cool = max(0.0, self.trap_cool - dt)

        for tag, speed in table.world.step(ball, dt, SUBSTEPS):
            self.on_hit(tag)

        if not self.trap_cool and not self.tilt and T.Table.in_trap(ball):
            self.on_trap()
            return

        # pulsante del bonus e corsie interne (a filo del tavolo)
        self.rollover_cool = max(0.0, self.rollover_cool - dt)
        if not self.rollover_cool and T.Table.on_rollover(ball):
            self.rollover_cool = 0.5
            self.on_rollover()
        self.inlane_cool = max(0.0, self.inlane_cool - dt)
        side = T.Table.on_inlane(ball)
        if side is not None and not self.inlane_cool:
            self.inlane_cool = 0.5
            self.on_inlane(side)

        # corsie in alto
        for i, x in enumerate(T.TOP_LANES):
            self.lane_cool[i] = max(0.0, self.lane_cool[i] - dt)
            if abs(ball.x - x) < 18 and 84 < ball.y < 104 and ball.vy > 0 \
                    and self.lane_cool[i] == 0.0:
                self.lane_cool[i] = 0.6
                self.on_lane(i)

        # salvataggio della pallina appena lanciata
        if not self.launched and ball.x < T.LANE_X0 - 4:
            self.launched = True
            self.save_until = self.clock_t + BALL_SAVE_SECONDS

        # bersagli che si rialzano
        if self.drop_reset and self.clock_t > self.drop_reset:
            self.drop_reset = 0.0
            for seg in table.drops:
                seg.active = True
        if self.letters_reset and self.clock_t > self.letters_reset:
            self.letters_reset = 0.0
            self.letters = [False] * 5

        # pallina ferma in un angolo: la si sblocca
        if ball.speed < 6 and not T.Table.in_lane(ball) and not (table.left.pressed or
                                                              table.right.pressed):
            self.stuck += dt
            if self.stuck > 3.0:
                self.stuck = 0.0
                ball.vy = -random.uniform(300, 450)
                ball.vx = random.uniform(-150, 150)
        else:
            self.stuck = 0.0

        if ball.y > T.DRAIN_Y:
            self.on_drain()

    def on_trap(self):
        ball = self.ball
        ball.x, ball.y = float(T.TRAP[0]), float(T.TRAP[1])
        ball.vx = ball.vy = 0.0
        self.trapped = T.TRAP_HOLD
        self.snd.play("trap")
        if self.special:
            self.special = False
            self.add(SPECIAL_POINTS)
            if self.give_extra_ball():
                self.say(self.t("msg_special") + "  " + self.t("msg_extra_ball"), 3.0)
            else:
                self.say(self.t("msg_special") + f"  {SPECIAL_POINTS:,}".replace(",", "."), 2.5)
        else:
            points = 2000 + 1000 * self.mult
            self.add(points)
            self.advance_bonus(3)
            self.say(self.t("msg_trap", points=f"{points:,}".replace(",", ".")), 1.5)

    def give_extra_ball(self):
        if (not self.extra_this_ball and self.extra_balls < MAX_EXTRA_BALLS
                and self.state == "play" and not self.tilt):
            self.extra_this_ball = True
            self.extra_balls += 1
            self.balls_total += 1
            self.snd.play("extra")
            return True
        return False

    def on_hit(self, tag):
        kind, idx = tag if isinstance(tag, tuple) else (tag, 0)
        if kind == "bumper":
            self.add(self.bumper_value * (2 if self.powered() else 1))
            self.flash[("bumper", idx)] = 0.12
            self.snd.play("bumper")
        elif kind == "center":
            self.flash[("center", 0)] = 0.15
            self.add(750)
            self.advance_bonus(1)
            if not self.powered() and self.state == "play" and not self.tilt:
                self.say(self.t("msg_power"), 2.0)
                self.snd.play("complete")
            else:
                self.snd.play("drop")
            if not self.tilt:
                self.power_until = self.clock_t + T.POWER_SECONDS
        elif kind == "dish":
            self.flash[("dish", 0)] = 0.12
            self.add(50)
            self.snd.play("kick")
        elif kind == "sling":
            self.add(10)
            self.flash[("sling", idx)] = 0.10
            self.snd.play("sling")
        elif kind == "drop":
            seg = self.table.drops[idx]
            if seg.active:
                seg.active = False
                self.add(500)
                self.advance_bonus(1)
                self.snd.play("drop")
                if not any(s.active for s in self.table.drops):
                    self.add(2500)
                    if self.mult < 5:
                        self.mult += 1
                    self.say(self.t("msg_bank", n=self.mult))
                    self.snd.play("complete")
                    self.drop_reset = self.clock_t + 1.5
        elif kind == "rusca":
            self.flash[("rusca", idx)] = 0.15
            if self.letters_reset:
                return
            if not self.letters[idx]:
                self.letters[idx] = True
                self.add(1000)
                self.advance_bonus(1)
                self.snd.play("rusca")
                if all(self.letters):
                    self.add(15000)
                    self.letters_reset = self.clock_t + 2.0
                    if self.give_extra_ball():
                        self.say(self.t("msg_rusca") + "  " + self.t("msg_extra_ball"), 3.0)
                    else:
                        self.say(self.t("msg_rusca"), 2.0)
                        self.snd.play("complete")
            else:
                self.add(100)
                self.snd.play("sling")

    def powered(self):
        return self.clock_t < self.power_until

    def on_rollover(self):
        """Pulsante del bonus: un passo di bonus, due con il fulmine."""
        self.flash[("rollover", 0)] = 0.3
        self.add(300)
        self.advance_bonus(2 if self.powered() else 1)
        self.snd.play("lane")

    def on_inlane(self, side):
        """Corsie interne: accese tutte e due, il moltiplicatore sale."""
        if self.inlanes[side]:
            self.add(100)
            return
        self.inlanes[side] = True
        self.add(500)
        self.snd.play("lane")
        if all(self.inlanes):
            self.inlanes = [False, False]
            self.add(2500)
            if self.mult < 5:
                self.mult += 1
            self.say(self.t("msg_inlanes", n=self.mult))
            self.snd.play("complete")

    def on_lane(self, i):
        if not self.lanes[i]:
            self.lanes[i] = True
            self.add(500)
            self.advance_bonus(1)
            self.snd.play("lane")
            if all(self.lanes):
                self.add(5000)
                self.bumper_value = min(500, self.bumper_value + 100)
                self.say(self.t("msg_lanes", value=self.bumper_value))
                self.snd.play("complete")
                self.lanes = [False] * len(T.TOP_LANES)
        else:
            self.add(50)

    def on_drain(self):
        if self.state == "attract":
            self.new_ball()
            return
        if not self.tilt and self.launched and self.clock_t < self.save_until:
            self.say(self.t("msg_ball_saved"))
            self.snd.play("save")
            self.ball = Ball(*T.BALL_START)
            self.launched = False
            return
        self.snd.play("drain")
        if self.tilt:
            self.bonus = 0
        self.counting = {"wait": 0.8, "step": 0.0}
        if self.bonus:
            self.say(self.t("msg_bonus", bonus=f"{self.bonus * BONUS_UNIT:,}".replace(",", "."),
                            mult=self.mult), 2.5)

    def count_bonus(self, dt):
        """Le lampade dell'anello si spengono una alla volta, come nei tavoli veri."""
        c = self.counting
        if c["wait"] > 0:
            c["wait"] -= dt
            return
        if self.bonus > 0:
            c["step"] -= dt
            if c["step"] <= 0:
                c["step"] = 0.07
                self.bonus -= 1
                self.score += BONUS_UNIT * self.mult
                self.snd.play("tick")
            if self.bonus == 0:
                c["wait"] = 0.9
            return
        # bonus finito: prossima pallina o fine partita
        self.counting = None
        if self.ball_num < self.balls_total:
            self.ball_num += 1
            self.new_ball()
            if self.ball_num == self.balls_total:
                self.say(self.t("msg_last_ball"), 2.0)
        else:
            self.game_over()

    def game_over(self):
        self.ball = Ball(-100, -100)
        if self.scores.qualifies(self.score):
            self.state = "entry"
            self.name = ""
            pygame.key.start_text_input()
        else:
            self.state = "gameover"
            self.gameover_until = self.clock_t + 5.0

    # ── disegno ──
    def lit(self, key):
        return key in self.flash

    def lamps_on(self):
        """Chiavi degli elementi accesi in questo fotogramma (vedi rp_view)."""
        on = []
        t = self.clock_t
        blink = int(t * 4) % 2 == 0
        if self.state == "attract":
            # giro di lampade, come i flipper in vetrina
            k = int(t * 8)
            on += [("lane", k % len(T.TOP_LANES))]
            on += [("bonus", 1 + (k + j) % 9) for j in (0, 3, 6)]
            on += [("tens", 1 + (k // 3) % 3), ("rusca", k % 5)]
            on += [("arc", j) for j in range(5) if j <= k % 6]
            on += [("inlane", k % 2)]
            if blink:
                on += ["special", "arrow", "power", "rollover"]
            return on
        on += [("lane", i) for i, v in enumerate(self.lanes) if v]
        units, tens = T.bonus_lamps_on(self.bonus)
        if units:
            on.append(("bonus", units))
        if tens:
            on.append(("tens", tens))
        if self.special and blink:
            on += ["special", "arrow"]
        on += [("arc", j) for j in range(min(5, self.bumper_value // 100))]
        on += [("inlane", i) for i, v in enumerate(self.inlanes) if v]
        if self.powered():
            # il fulmine lampeggia più in fretta negli ultimi 3 secondi
            left = self.power_until - t
            if left > 3 or int(t * 8) % 2 == 0:
                on += ["power", "rollover"]
        elif self.lit(("rollover", 0)):
            on.append("rollover")
        on += [("rusca", i) for i, v in enumerate(self.letters) if v or self.lit(("rusca", i))]
        on += [("drop", i) for i, s in enumerate(self.table.drops) if not s.active]
        on += [("sling", i) for i in (0, 1) if self.lit(("sling", i))]
        saving = self.state == "play" and (not self.launched or self.clock_t < self.save_until)
        if saving and (blink or not self.launched):
            on.append("save")
        return on

    def bumper_label(self):
        value = self.bumper_value * (2 if self.powered() else 1)
        img = self.bumper_labels.get(value)
        if img is None:
            img = self.fonts["bumper"].render(str(value), False, CREMA)
            self.bumper_labels[value] = img
        return img

    def draw(self):
        f = self.world_surf
        L = self.layers
        f.blit(L.base, (0, 0))
        for key in self.lamps_on():
            L.blit_on(f, key)
        if self.state in ("play", "attract"):
            V.draw_plunger(f, self.pull)
        # bumper e pallina in ordine di distanza: ciò che è davanti copre
        ball_visible = self.state in ("play", "attract") and self.counting is None
        items = [(y, "bumper", i) for i, (x, y) in enumerate(T.BUMPERS)]
        items += [(T.CENTER_TARGET[1], "center", 0), (T.DISH[0][1], "dish", 0)]
        if ball_visible:
            items.append((self.ball.y, "ball", 0))
        label = self.bumper_label()
        for _y, kind, i in sorted(items):
            if kind == "bumper":
                x, y = T.BUMPERS[i]
                V.draw_bumper(f, x, y, self.lit(("bumper", i)), label)
            elif kind == "center":
                V.draw_center_target(f, self.lit(("center", 0)), self.powered())
            elif kind == "dish":
                V.draw_dish(f, self.lit(("dish", 0)))
            else:
                V.draw_ball(f, self.ball, sunk=bool(self.trapped))
        for fl in (self.table.left, self.table.right):
            V.draw_flipper(f, fl)

        self.screen.fill(BORDER)
        dx = dy = 0
        if self.shake > 0:
            dx, dy = random.randint(-4, 4), random.randint(-3, 3)
        self.screen.blit(f, (dx, dy))
        self.draw_hud()
        if self.state == "attract":
            self.draw_attract()
        if self.state == "entry":
            self.draw_entry()
        elif self.state == "gameover":
            self.draw_gameover()
        if self.paused:
            self.draw_panel([(self.t("paused"), "big", CREMA),
                             (self.t("pause_hint"), "small", ROSA_250)])
        if self.settings.scanlines:
            self.screen.blit(self.scan, (0, 0))

    def draw_box(self, rect, value, fnt):
        """Riquadro del punteggio, come i contatori dei flipper per Spectrum."""
        s = self.screen
        pygame.draw.rect(s, PRUGNA_750, rect)
        pygame.draw.rect(s, AMETISTA_500, rect, 2)
        img = fnt.render(value, False, CREMA)
        if img.get_width() > rect.w - 8:
            img = self.fonts["hud_small"].render(value, False, CREMA)
        s.blit(img, img.get_rect(midright=(rect.right - 6, rect.centery)))

    def draw_hud(self):
        s, t, F = self.screen, self.t, self.fonts
        # in alto a sinistra: il nome del tavolo
        text(s, F["hud_small"], "PINBALL", AMETISTA_300, False, topleft=(16, 16))
        text(s, F["hud_big"], "AMETHYST", ROSA_250, False, topleft=(14, 32))
        text(s, F["hud_tiny"], "RUSCALINUX", AMETISTA_300, False, topleft=(16, 70))
        # in alto a destra: il record
        best = self.scores.table[0][1] if self.scores.table else 0
        top_label = t("top_label")
        text(s, fit(F, ("hud", "hud_small", "hud_tiny"), top_label, 170), top_label,
             AMETISTA_300, False, topright=(SCREEN_W - 16, 16))
        self.draw_box(pygame.Rect(SCREEN_W - 156, 40, 140, 32),
                      f"{best:,}".replace(",", "."), F["hud"])
        # a destra: punti, moltiplicatore, bonus
        score_label = t("score_label")
        text(s, fit(F, ("hud", "hud_small", "hud_tiny"), score_label, 130), score_label,
             AMETISTA_300, False, topleft=(SCREEN_W - 140, 300))
        self.draw_box(pygame.Rect(SCREEN_W - 140, 324, 128, 38),
                      f"{self.score:,}".replace(",", "."), F["hud"])
        for i, n in enumerate((2, 3, 4, 5)):
            cx, cy = SCREEN_W - 125 + i * 33, 395
            on = self.mult >= n
            pygame.draw.circle(s, ROSA_250 if on else PRUGNA_750, (cx, cy), 14)
            pygame.draw.circle(s, CREMA if on else PRUGNA_600, (cx, cy), 14, 2)
            text(s, F["hud_tiny"], f"{n}×", PRUGNA_900 if on else ROSA_300, False, center=(cx, cy))
        bonus = f"{t('bonus_label')} {self.bonus * BONUS_UNIT:,}".replace(",", ".")
        text(s, fit(F, ("hud_small", "hud_tiny"), bonus, 130), bonus, ROSA_200, False,
             topleft=(SCREEN_W - 140, 420))
        # a sinistra: pallina, tilt, pallina extra
        playing = self.state in ("play", "entry", "gameover")
        ball_label = t("ball_label")
        text(s, fit(F, ("hud", "hud_small", "hud_tiny"), ball_label, 125), ball_label,
             AMETISTA_300, False, topleft=(14, 300))
        if playing:
            value = f"{min(self.ball_num, self.balls_total)}/{self.balls_total}"
            text(s, F["hud_big"], value, CREMA, False, topleft=(14, 322))
        else:
            demo = t("demo")
            text(s, fit(F, ("hud", "hud_small", "hud_tiny"), demo, 125), demo, CREMA, False,
                 topleft=(14, 330))
        text(s, F["hud_tiny"], t("tilt_label"), AMETISTA_300, False, topleft=(14, 372))
        for i in range(3):
            on = playing and (self.tilt or self.tilt_meter > i + 0.01)
            pygame.draw.circle(s, ROSA_300 if on else PRUGNA_750, (22 + i * 18, 398), 6)
            pygame.draw.circle(s, PRUGNA_600, (22 + i * 18, 398), 6, 1)
        extra = t("extra_label")
        text(s, fit(F, ("hud_small", "hud_tiny"), extra, 125), extra, AMETISTA_300, False,
             topleft=(14, 420))
        on = playing and self.extra_pending()
        box = pygame.Rect(14, 440, 34, 24)
        pygame.draw.rect(s, ROSA_250 if on else PRUGNA_750, box)
        pygame.draw.rect(s, CREMA if on else AMETISTA_500, box, 2)
        if on:
            text(s, F["hud_tiny"], "EB", PRUGNA_900, False, center=box.center)
        # in basso: messaggi, oppure la scritta che scorre
        self.draw_messages()

    def draw_messages(self):
        s = self.screen
        y = 565
        if self.state == "attract" and not self.attract_panel():
            if int(self.clock_t * 2) % 2 == 0:
                text(s, self.fonts["hud"], self.t("press_start"), CREMA, False,
                     center=(SCREEN_W // 2, y))
            return
        if self.messages:
            msg = self.messages[-1][0]
            fnt = fit(self.fonts, ("hud", "hud_small", "hud_tiny"), msg, SCREEN_W - 40)
            text(s, fnt, msg, CREMA, False, center=(SCREEN_W // 2, y))
            return
        marquee = "   ·   ".join(("PINBALL AMETHYST", "RUSCALINUX 2026", self.t("marquee"),
                                  "WWW.RUSCALINUX.ORG")) + "   ·   "
        fnt = self.fonts["hud_small"]
        img = fnt.render(marquee, False, ROSA_300)
        w = img.get_width()
        x = -int(self.clock_t * 60) % w
        clip = s.get_clip()
        s.set_clip(pygame.Rect(16, y - 12, SCREEN_W - 32, 24))
        for xx in (x - w, x, x + w):
            s.blit(img, img.get_rect(midleft=(xx, y)))
        s.set_clip(clip)

    def draw_panel(self, lines, y=None, width=460):
        fonts = self.fonts
        hgt = sum(fonts[f].get_linesize() + 6 for _, f, _ in lines) + 24
        y = y if y is not None else (SCREEN_H - hgt) // 2 - 30
        rect = pygame.Rect((SCREEN_W - width) // 2, y, width, hgt)
        panel = pygame.Surface(rect.size, pygame.SRCALPHA)
        panel.fill((*PRUGNA_900, 240))
        self.screen.blit(panel, rect)
        pygame.draw.rect(self.screen, AMETISTA_500, rect, 3)
        pygame.draw.rect(self.screen, AMETISTA_300, rect.inflate(-8, -8), 1)
        yy = rect.y + 12
        for line, fnt, col in lines:
            lh = fonts[fnt].get_linesize() + 6
            if line:
                text(self.screen, fonts[fnt], line, col, center=(SCREEN_W // 2, yy + lh // 2))
            yy += lh
        return rect

    def attract_panel(self):
        return self.info or self.clock_t % ATTRACT_CYCLE < ATTRACT_PANEL

    def draw_attract(self):
        t = self.t
        if self.info:
            self.draw_panel([
                (APP_NAME, "title", ROSA_250),
                (t("version", v=APP_VERSION), "small", ROSA_200),
                *[(line, "text", CREMA) for line in wrap(t("app_description"), self.fonts["text"], 420)],
                ("", "tiny", CREMA),
                (t("about_website") + ": www.ruscalinux.org", "text", CREMA),
                (t("about_support") + ": info@ruscalinux.org", "text", CREMA),
                (t("about_license") + ": GNU GPL 3.0", "text", CREMA),
                ("", "tiny", CREMA),
                (t("dev_note_title"), "mid", ROSA_250),
                *[(line, "small", CREMA) for line in wrap(t("ai_note"), self.fonts["small"], 420)],
                ("", "tiny", CREMA),
                (t("original_note"), "small", ROSA_200),
                ("© 2026 Nunzio Curcuruto", "small", ROSA_200),
                (t("info_close"), "small", ROSA_300),
            ], y=40)
            return
        # come nei flipper in vetrina: il pannello si alterna alla partita
        # dimostrativa, che resta visibile per qualche secondo
        if not self.attract_panel():
            return
        lines = [("PINBALL AMETHYST", "title", ROSA_250),
                 (t("app_description"), "text", CREMA),
                 ("", "tiny", CREMA)]
        if int(self.clock_t * 2) % 2 == 0:
            lines.append((t("press_start"), "mid", CREMA))
        else:
            lines.append(("", "mid", CREMA))
        lines += [("", "tiny", CREMA), (t("high_scores"), "mid", ROSA_250)]
        for name, score in self.scores.table:
            lines.append((f"{name:<10} {score:>9,}".replace(",", "."), "row", CREMA))
        lines += [("", "tiny", CREMA), (t("controls_title"), "mid", ROSA_250)]
        for key in ("ctl_left", "ctl_right", "ctl_plunger", "ctl_nudge", "ctl_misc", "ctl_info"):
            lines.append((t(key), "small", CREMA))
        self.draw_panel(lines, y=24)

    def draw_entry(self):
        cursor = "_" if int(self.clock_t * 3) % 2 == 0 else " "
        self.draw_panel([(self.t("new_record"), "big", ROSA_250),
                         (f"{self.score:,}".replace(",", "."), "score", CREMA),
                         (self.t("enter_name"), "small", ROSA_200),
                         (self.name + cursor, "big", CREMA)])

    def draw_gameover(self):
        self.draw_panel([(self.t("game_over"), "big", ROSA_250),
                         (f"{self.score:,}".replace(",", "."), "score", CREMA),
                         (self.t("press_start"), "small", ROSA_200)])


def wrap(s, fnt, width):
    words, lines, cur = s.split(), [], ""
    for w in words:
        test = (cur + " " + w).strip()
        if fnt.size(test)[0] > width and cur:
            lines.append(cur)
            cur = w
        else:
            cur = test
    if cur:
        lines.append(cur)
    return lines


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    if "--version" in argv:
        print(f"{APP_NAME} {APP_VERSION}")
        return 0
    settings = Settings()
    try:
        pygame.mixer.pre_init(22050, -16, 1, 512)
    except pygame.error:
        pass
    pygame.init()
    i18n = I18n()
    flags = pygame.SCALED | pygame.RESIZABLE
    if "--fullscreen" in argv:
        flags |= pygame.FULLSCREEN
    try:
        screen = pygame.display.set_mode((SCREEN_W, SCREEN_H), flags, vsync=1)
    except pygame.error:
        screen = pygame.display.set_mode((SCREEN_W, SCREEN_H), flags)
    pygame.display.set_caption(APP_NAME)
    try:
        icon = pygame.image.load(os.path.join(BASE_DIR, "ruscapinball.svg"))
    except (pygame.error, FileNotFoundError):
        icon = make_icon()
    pygame.display.set_icon(icon)
    pygame.joystick.init()
    for i in range(pygame.joystick.get_count()):
        try:
            pygame.joystick.Joystick(i).init()
        except pygame.error:
            pass
    sounds = Sounds(settings.sound)
    game = Game(screen, i18n, sounds, Scores(), settings)
    clock = pygame.time.Clock()
    running = True
    while running:
        dt = min(clock.tick(FPS) / 1000.0, 1.0 / 20)
        for ev in pygame.event.get():
            if ev.type == pygame.QUIT:
                running = False
            elif not game.handle(ev):
                running = False
        game.update(dt)
        game.draw()
        pygame.display.flip()
    pygame.quit()
    return 0


if __name__ == "__main__":
    sys.exit(main())
