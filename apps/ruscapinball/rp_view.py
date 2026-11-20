# RuscaPinball — rp_view.py — 1.99.3 — GPL-3.0-or-later
# Copyright (C) 2026 Nunzio Curcuruto <info@ruscalinux.org>
#
# Vista del tavolo «Amethyst» in prospettiva, come nei flipper per home
# computer degli anni '80: il tavolo inclinato visto dal giocatore, con il
# bordo della cassa, il frontale e i pezzi in rilievo.
#
# La fisica resta in 2D sul piano del tavolo (rp_physics, rp_table); qui c'è
# solo il disegno:
#   - project() porta un punto del piano (x, y, altezza z) sullo schermo;
#   - il fondo del tavolo si disegna una volta in 2D e si deforma in
#     prospettiva riga per riga (warp), in due versioni: tutto spento (base)
#     e tutto acceso (lit). Ogni lampada, lettera o bersaglio acceso si copia
#     dalla versione accesa con un solo blit del suo rettangolo;
#   - bumper, flipper, pallina e pistone si disegnano a ogni fotogramma, in
#     rilievo.

import math

import pygame

import rp_table as T

# ── Palette: RuscaLinux (specifiche, sezione 4.1) più tre toni di ametista ──
PRUGNA_900 = (0x2D, 0x0A, 0x1D)
PRUGNA_850 = (0x23, 0x07, 0x16)
PRUGNA_800 = (0x3A, 0x10, 0x28)
PRUGNA_750 = (0x40, 0x13, 0x2C)
PRUGNA_600 = (0x7A, 0x23, 0x57)
PRUGNA_500 = (0x8A, 0x2B, 0x5F)
ROSA_300 = (0xF2, 0xA7, 0xC8)
ROSA_250 = (0xF5, 0xB8, 0xD3)
ROSA_200 = (0xF8, 0xD7, 0xE6)
CREMA = (0xFF, 0xF7, 0xF0)
ARGENTO = (0xD9, 0xD2, 0xD6)
AMETISTA_700 = (0x4E, 0x23, 0x6B)    # ombre del legno, frontale
AMETISTA_500 = (0x8E, 0x55, 0xB8)    # cassa del flipper
AMETISTA_300 = (0xCB, 0xA6, 0xEC)    # spigoli in luce, testo sul fondo scuro

BORDER = PRUGNA_900                  # il «bordo» dello schermo, come sullo Spectrum
FIELD = PRUGNA_850
FRAME = AMETISTA_500

SCREEN_W, SCREEN_H = 800, 600

# ── Proiezione ─────────────────────────────────────────────────────────────
# Piano del tavolo: x da -20 a 500, y da -20 a 720 (bordo della cassa
# compreso). La riga y = 720 (in basso, vicino al giocatore) va a SB sullo
# schermo, larga SX volte il vero; la riga in fondo è più stretta di 1 + C.
CX, SB = 400.0, 500.0
SX, SY, SZ = 1.0, 0.78, 0.9
C = 0.3
H = float(T.HEIGHT)
MID_X = 240.0
CANVAS = (-20, -20, 500, 720)        # x0, y0, x1, y1 del fondo disegnato
FACE = 26                            # altezza del frontale della cassa in px
RAIL_Z = 9                           # altezza delle sponde
POST_Z = 12


def depth(y):
    """Fattore di distanza: 1 in basso, 1 + C in fondo al tavolo."""
    return 1.0 + C * (H - y) / H


def project(x, y, z=0.0):
    """Punto del piano (z = altezza sopra il piano) → punto dello schermo."""
    w = depth(y)
    return (CX + (x - MID_X) * SX / w, SB - (SY * (H - y) + SZ * z) / w)


def scale_at(y):
    """Scala orizzontale e verticale sullo schermo vicino alla riga y."""
    w = depth(y)
    return SX / w, SY / (w * w)


def unproject_row(sy):
    """Riga dello schermo → riga y del piano (inversa di project con z = 0)."""
    v = SB - sy
    u = v / (SY - C * v / H)
    return H - u


def project_rect(x0, y0, x1, y1, z=0.0, pad=1):
    """Rettangolo dello schermo che contiene il rettangolo del piano."""
    pts = [project(x, y, zz) for x in (x0, x1) for y in (y0, y1) for zz in (0.0, z)]
    xs, ys = [p[0] for p in pts], [p[1] for p in pts]
    left, top = math.floor(min(xs)) - pad, math.floor(min(ys)) - pad
    return pygame.Rect(left, top, math.ceil(max(xs)) + pad - left,
                       math.ceil(max(ys)) + pad - top)


def ellipse_rect(x, y, r, z=0.0):
    """Ellisse dello schermo di un cerchio di raggio r sul piano (o a quota z)."""
    cx, cy = project(x, y, z)
    kx, ky = scale_at(y)
    return pygame.Rect(round(cx - r * kx), round(cy - r * ky),
                       max(1, round(2 * r * kx)), max(1, round(2 * r * ky)))


# ── Caratteri ──────────────────────────────────────────────────────────────
def font(size, bold=True, mono=True):
    names = "dejavusansmono,liberationmono,freemono" if mono else \
        "dejavusans,liberationsans,freesans"
    try:
        return pygame.font.SysFont(names, size, bold=bold)
    except (pygame.error, OSError):
        return pygame.font.Font(None, size + 6)


def blit_text(surf, fnt, s, color, aa=False, **anchor):
    img = fnt.render(s, aa, color)
    rect = img.get_rect(**anchor)
    surf.blit(img, rect)
    return rect


# ── Fondo del tavolo in 2D ─────────────────────────────────────────────────
def _c(p):
    """Coordinate del piano → coordinate nella tela (che parte da -20, -20)."""
    return (round(p[0] - CANVAS[0]), round(p[1] - CANVAS[1]))


def _circle(s, col, p, r, width=0):
    pygame.draw.circle(s, col, _c(p), r, width)


def _poly(s, col, pts, width=0):
    pygame.draw.polygon(s, col, [_c(p) for p in pts], width)


def _line(s, col, a, b, width):
    pygame.draw.line(s, col, _c(a), _c(b), width)
    r = max(1, width // 2)
    pygame.draw.circle(s, col, _c(a), r)
    pygame.draw.circle(s, col, _c(b), r)


def _text(s, fnt, txt, col, center):
    img = fnt.render(txt, False, col)
    s.blit(img, img.get_rect(center=_c(center)))


def _lamp(s, fnt, p, on, label="", r=T.LAMP_R):
    _circle(s, ROSA_250 if on else PRUGNA_750, p, r)
    _circle(s, CREMA if on else PRUGNA_600, p, r, 3)
    if label:
        _text(s, fnt, label, PRUGNA_900 if on else ROSA_300, p)


def _arrow(s, col, tip, direction, size=14):
    ang = math.atan2(direction[1], direction[0])
    back = (tip[0] - math.cos(ang) * size, tip[1] - math.sin(ang) * size)
    side = (-math.sin(ang) * size * 0.6, math.cos(ang) * size * 0.6)
    _poly(s, col, [tip, (back[0] + side[0], back[1] + side[1]),
                   (back[0] - side[0], back[1] - side[1])])


def draw_canvas(fonts, lit):
    """Il fondo del tavolo visto dall'alto: lit = True con tutto acceso."""
    x0, y0, x1, y1 = CANVAS
    s = pygame.Surface((x1 - x0, y1 - y0))
    s.fill(FRAME)
    # campo di gioco
    arc = T.arc_points()
    _poly(s, FIELD, arc + [(T.LANE_X1, T.HEIGHT), (T.LEFT, T.HEIGHT)])
    for y in range(36, T.HEIGHT, 24):            # trama a puntini, serigrafata
        for x in range(32, T.RIGHT, 24):
            if s.get_at(_c((x, y)))[:3] == FIELD:
                _circle(s, PRUGNA_800, (x, y), 2)
    # corsia di lancio
    pygame.draw.rect(s, PRUGNA_800, (*_c((T.LANE_X0, 232)), T.LANE_X1 - T.LANE_X0, T.HEIGHT - 232))
    for y in range(260, T.LANE_FLOOR - 30, 34):
        _poly(s, PRUGNA_600, [(447, y), (440, y + 10), (454, y + 10)])
    # nome del tavolo, serigrafato al centro come nei tavoli dell'epoca
    title = fonts["table_title"].render("AMETHYST", False, AMETISTA_500)
    s.blit(title, title.get_rect(center=_c((225, T.TITLE_Y))))
    # trappola del bonus: una buca con l'orlo
    _circle(s, PRUGNA_600, T.TRAP, T.TRAP_R + 5)
    _circle(s, BORDER, T.TRAP, T.TRAP_R)
    _circle(s, AMETISTA_300, T.TRAP, T.TRAP_R + 5, 2)
    _arrow(s, ROSA_250 if lit else PRUGNA_600, T.TRAP_ARROW,
           (T.TRAP[0] - T.TRAP_ARROW[0], T.TRAP[1] - T.TRAP_ARROW[1]), 16)
    # lampade delle corsie in alto
    for x in T.TOP_LANES:
        _lamp(s, fonts["lamp"], (x, T.LANE_LAMP_Y), lit, r=9)
    # anello del bonus
    for p in T.BONUS_LAMPS + T.TENS_LAMPS:
        _lamp(s, fonts["lamp"], p, lit)
    cx, cy, w, h = T.SPECIAL_LAMP
    box = pygame.Rect(0, 0, w, h)
    box.center = _c((cx, cy))
    pygame.draw.rect(s, ROSA_250 if lit else PRUGNA_750, box, border_radius=6)
    pygame.draw.rect(s, CREMA if lit else PRUGNA_600, box, 3, border_radius=6)
    # salvataggio della pallina
    _lamp(s, fonts["lamp"], T.SAVE_LAMP, lit, r=7)
    # frecce delle corsie interne
    for x, y, d in ((70, 585, 1), (380, 585, -1)):
        _poly(s, PRUGNA_600, [(x, y), (x + 14 * d, y + 12), (x, y + 24)])
    # slingshot: accesi quando scattano
    for pts in (T.SLING_L, T.SLING_R):
        _poly(s, PRUGNA_500 if lit else AMETISTA_700, pts)
        _poly(s, AMETISTA_300, pts, 3)
        _line(s, CREMA if lit else ROSA_200, pts[0], pts[2], 7)
    # bersagli abbattibili: nella versione accesa sono giù
    for y0_, y1_ in T.DROP_TARGETS:
        if lit:
            _line(s, PRUGNA_600, (T.LEFT + 3, y0_), (T.LEFT + 3, y1_), 3)
        else:
            pygame.draw.rect(s, ROSA_200, (*_c((T.LEFT + 1, y0_)), 12, y1_ - y0_), border_radius=2)
            pygame.draw.rect(s, PRUGNA_600, (*_c((T.LEFT + 1, y0_)), 12, y1_ - y0_), 2,
                             border_radius=2)
    # bersagli R-U-S-C-A con la loro lettera
    for i, y in enumerate(T.RUSCA_Y):
        col = ROSA_250 if lit else PRUGNA_750
        pygame.draw.rect(s, col, (*_c((T.RUSCA_X - 5, y)), 10, T.RUSCA_LEN), border_radius=2)
        pygame.draw.rect(s, PRUGNA_600, (*_c((T.RUSCA_X - 5, y)), 10, T.RUSCA_LEN), 2,
                         border_radius=2)
    return s


def draw_labels(surf, fonts, lit):
    """Numeri e lettere delle lampade, diritti sullo schermo: in prospettiva
    le cifre piccole si schiaccerebbero fino a confondersi (9 e 0)."""
    def label(fnt, txt, col, p):
        img = fnt.render(txt, False, col)
        surf.blit(img, img.get_rect(center=(round(p[0]), round(p[1]))))

    on, off = PRUGNA_900, ROSA_300
    label(fonts["table_small"], "RUSCALINUX · 2026", AMETISTA_300, project(225, T.TITLE_Y + 26))
    label(fonts["lamp_small"], "BONUS", AMETISTA_300, project(225, 449))
    for n, p in enumerate(T.BONUS_LAMPS, 1):
        label(fonts["lamp"], str(n), on if lit else off, project(*p))
    for k, p in enumerate(T.TENS_LAMPS, 1):
        label(fonts["lamp_small"], str(10 * k), on if lit else off, project(*p))
    label(fonts["lamp_small"], "SPECIAL", on if lit else off, project(*T.SPECIAL_LAMP[:2]))
    for i, y in enumerate(T.RUSCA_Y):
        label(fonts["letter"], T.RUSCA[i], CREMA if lit else AMETISTA_300,
              project(T.RUSCA_X - 20, y + T.RUSCA_LEN / 2))


def warp(canvas, dest):
    """Deforma la tela in prospettiva sulla superficie dello schermo."""
    x0, y0, x1, y1 = CANVAS
    top = math.floor(project(MID_X, y0)[1])
    for sy in range(top, int(SB)):
        y = unproject_row(sy + 0.5)
        r = int(y - y0)
        if r < 0 or r >= y1 - y0:
            continue
        left, right = project(x0, y)[0], project(x1, y)[0]
        width = round(right) - round(left)
        row = canvas.subsurface((0, r, x1 - x0, 1))
        dest.blit(pygame.transform.scale(row, (width, 1)), (round(left), sy))


def _dither(surf, rect, col_a, col_b, poly):
    """Riempie un poligono con un retino a scacchi 2 × 2, come sullo Spectrum."""
    pat = pygame.Surface(rect.size)
    pat.fill(col_a)
    for yy in range(0, rect.h, 2):
        for xx in range((yy // 2 % 2) * 2, rect.w, 4):
            pat.fill(col_b, (xx, yy, 2, 2))
    mask = pygame.Surface(rect.size, pygame.SRCALPHA)
    pygame.draw.polygon(mask, (255, 255, 255, 255), [(x - rect.x, y - rect.y) for x, y in poly])
    out = pygame.Surface(rect.size, pygame.SRCALPHA)
    out.blit(pat, (0, 0))
    out.blit(mask, (0, 0), special_flags=pygame.BLEND_RGBA_MIN)
    surf.blit(out, rect)


def _rail(surf, a, b, z, side, top, width=3):
    """Sponda in rilievo dal punto a al punto b del piano."""
    pa, pb = project(*a), project(*b)
    qa, qb = project(*a, z), project(*b, z)
    pygame.draw.polygon(surf, side, [pa, pb, qb, qa])
    pygame.draw.line(surf, top, qa, qb, width)


def draw_cabinet(surf):
    """Frontale e spigoli della cassa, sopra il fondo deformato."""
    x0, y0, x1, y1 = CANVAS
    bl, br = project(x0, y1), project(x1, y1)
    tl, tr = project(x0, y0), project(x1, y0)
    face = [bl, br, (br[0], br[1] + FACE), (bl[0], bl[1] + FACE)]
    rect = pygame.Rect(math.floor(bl[0]), math.floor(bl[1]),
                       math.ceil(br[0] - bl[0]) + 1, FACE + 1)
    _dither(surf, rect, AMETISTA_700, AMETISTA_500, face)
    pygame.draw.line(surf, AMETISTA_300, bl, br, 2)
    for a, b in ((tl, tr), (tl, bl), (tr, br)):
        pygame.draw.line(surf, AMETISTA_300, a, b, 2)
    pygame.draw.line(surf, AMETISTA_700, (bl[0], bl[1] + FACE), (br[0], br[1] + FACE), 2)


def draw_rails(surf):
    """Sponde, paletti delle corsie e cancelletto, in rilievo."""
    walls = T.wall_list()
    # dal fondo verso il giocatore, così le sponde davanti coprono quelle dietro
    walls.sort(key=lambda w: min(w[0][1], w[1][1]))
    for a, b in walls:
        _rail(surf, a, b, RAIL_Z, AMETISTA_700, AMETISTA_300)
    _rail(surf, (T.LANE_X0, 232), (T.LANE_X1, 200), RAIL_Z / 2, PRUGNA_600, ROSA_300, 2)
    for x in T.LANE_POSTS:
        _rail(surf, (x, T.TOP_LANE_Y[0]), (x, T.TOP_LANE_Y[1]), POST_Z, AMETISTA_700, CREMA, 4)
    # paletti tondi in cima alle guide
    for p in ((T.LEFT, 540), (T.RIGHT, 540)):
        pygame.draw.ellipse(surf, AMETISTA_300, ellipse_rect(*p, 5, RAIL_Z))


class StaticLayers:
    """Fondo dello schermo spento e acceso, e i rettangoli di ciascun elemento."""

    def __init__(self, fonts):
        self.base = self._layer(fonts, False)
        self.lit = self._layer(fonts, True)
        self.rects = element_rects()

    @staticmethod
    def _layer(fonts, lit):
        surf = pygame.Surface((SCREEN_W, SCREEN_H))
        surf.fill(BORDER)
        warp(draw_canvas(fonts, lit), surf)
        draw_cabinet(surf)
        draw_rails(surf)
        draw_labels(surf, fonts, lit)
        return surf

    def blit_on(self, surf, key, offset=(0, 0)):
        rect = self.rects[key]
        surf.blit(self.lit, rect.move(offset), rect)


def element_rects():
    """Rettangolo dello schermo di ogni elemento che si accende."""
    r = T.LAMP_R + 1
    rects = {}
    for i, x in enumerate(T.TOP_LANES):
        rects[("lane", i)] = project_rect(x - 12, T.LANE_LAMP_Y - 12, x + 12, T.LANE_LAMP_Y + 12)
    for n, (x, y) in enumerate(T.BONUS_LAMPS, 1):
        rects[("bonus", n)] = project_rect(x - r, y - r, x + r, y + r)
    for k, (x, y) in enumerate(T.TENS_LAMPS, 1):
        rects[("tens", k)] = project_rect(x - r, y - r, x + r, y + r)
    cx, cy, w, h = T.SPECIAL_LAMP
    rects["special"] = project_rect(cx - w / 2 - 2, cy - h / 2 - 2, cx + w / 2 + 2, cy + h / 2 + 2)
    x, y = T.SAVE_LAMP
    rects["save"] = project_rect(x - 10, y - 10, x + 10, y + 10)
    x, y = T.TRAP_ARROW
    rects["arrow"] = project_rect(x - 14, y - 14, x + 14, y + 14)
    for i, (y0, y1) in enumerate(T.DROP_TARGETS):
        rects[("drop", i)] = project_rect(T.LEFT + 1, y0 - 2, T.LEFT + 14, y1 + 2)
    for i, y in enumerate(T.RUSCA_Y):
        rects[("rusca", i)] = project_rect(T.RUSCA_X - 30, y - 3, T.RUSCA_X + 6, y + T.RUSCA_LEN + 3)
    for i, pts in enumerate((T.SLING_L, T.SLING_R)):
        xs, ys = [p[0] for p in pts], [p[1] for p in pts]
        rects[("sling", i)] = project_rect(min(xs) - 4, min(ys) - 4, max(xs) + 4, max(ys) + 4)
    return rects


# ── Pezzi che si muovono, in rilievo ───────────────────────────────────────
def draw_bumper(surf, x, y, hot, label):
    """Bumper a fungo: base, gambo e cappello, con il valore sopra."""
    r = T.BUMPER_R
    pygame.draw.ellipse(surf, AMETISTA_700, ellipse_rect(x, y, r + 3))
    stem_lo, stem_hi = ellipse_rect(x, y, r * 0.55), ellipse_rect(x, y, r * 0.55, 12)
    pygame.draw.rect(surf, PRUGNA_600, stem_hi.union(stem_lo).inflate(0, -stem_lo.h // 2))
    pygame.draw.ellipse(surf, PRUGNA_600, stem_lo)
    cap_side = ellipse_rect(x, y, r, 12)
    cap_top = ellipse_rect(x, y, r, 20)
    body = CREMA if hot else ROSA_300
    pygame.draw.rect(surf, PRUGNA_500 if not hot else ROSA_250,
                     cap_top.union(cap_side).inflate(0, -cap_side.h))
    pygame.draw.ellipse(surf, PRUGNA_500 if not hot else ROSA_250, cap_side)
    pygame.draw.ellipse(surf, body, cap_top)
    pygame.draw.ellipse(surf, CREMA, cap_top, 2)
    inner = cap_top.inflate(-round(cap_top.w * 0.22), -round(cap_top.h * 0.36))
    pygame.draw.ellipse(surf, PRUGNA_600 if not hot else ROSA_300, inner)
    surf.blit(label, label.get_rect(center=inner.center))


def draw_flipper(surf, fl):
    base = [project(x, y) for x, y in fl.outline()]
    top = [project(x, y, 8) for x, y in fl.outline()]
    n = len(base)
    for i in range(n):
        j = (i + 1) % n
        pygame.draw.polygon(surf, AMETISTA_700, [base[i], base[j], top[j], top[i]])
    pygame.draw.polygon(surf, CREMA, top)
    pygame.draw.polygon(surf, ROSA_300, top, 2)
    pygame.draw.ellipse(surf, PRUGNA_600, ellipse_rect(fl.px, fl.py, 4, 8))


def draw_ball(surf, ball, sunk=False):
    """Pallina d'acciaio: ombra sul piano e sfera; sunk = dentro la trappola."""
    r = ball.r
    if not sunk:
        sh = ellipse_rect(ball.x + 2, ball.y + 2, r)
        pygame.draw.ellipse(surf, PRUGNA_900, sh)
    cx, cy = project(ball.x, ball.y, 0 if sunk else r)
    rad = r * scale_at(ball.y)[0]
    pygame.draw.circle(surf, ARGENTO, (round(cx), round(cy)), round(rad))
    pygame.draw.circle(surf, AMETISTA_300, (round(cx), round(cy)), round(rad), 1)
    pygame.draw.circle(surf, CREMA, (round(cx - rad / 3), round(cy - rad / 3)), max(1, round(rad / 3)))


def draw_plunger(surf, pull):
    y = T.LANE_FLOOR + T.PLUNGER_TRAVEL * pull
    x0, x1 = T.LANE_X0 + 5, T.LANE_X1 - 5
    head = [project(x0, y, 4), project(x1, y, 4), project(x1, y + 6, 4), project(x0, y + 6, 4)]
    pts = []
    for i in range(9):
        yy = y + 6 + (T.HEIGHT - y - 6) * i / 8
        pts.append(project(x0 + 4 if i % 2 else x1 - 4, yy, 3))
    pygame.draw.lines(surf, PRUGNA_500, False, pts, 2)
    pygame.draw.polygon(surf, ROSA_300, head)
    pygame.draw.polygon(surf, CREMA, head, 1)


def contrast(c1, c2):
    """Rapporto di contrasto WCAG fra due colori RGB."""
    def lum(c):
        def ch(v):
            v /= 255
            return v / 12.92 if v <= 0.03928 else ((v + 0.055) / 1.055) ** 2.4
        r, g, b = (ch(v) for v in c)
        return 0.2126 * r + 0.7152 * g + 0.0722 * b
    a, b = sorted((lum(c1), lum(c2)), reverse=True)
    return (a + 0.05) / (b + 0.05)
