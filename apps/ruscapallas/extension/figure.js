// figure.js — RuscaPallas 1.99.3 — GPL-3.0-or-later
//
// Il disegno di Pallasio con Cairo: un manul antropomorfo, panciuto, con
// giacca color crema, camicia, cravatta rossa, occhialini tondi e un tomo
// sempre in mano. Le forme sono scritte come percorsi SVG (quelle
// dell'anteprima approvata, con ombre, luci e trama del pelo) e si disegnano
// su un riquadro di 130 × 150 unità; chi chiama sceglie la scala.
//
// Il modulo non sa niente di GNOME Shell: riceve un contesto Cairo e il
// modello `m` calcolato da motion.js (trasformazioni, percorsi che
// cambiano, opacità). Così si prova anche con gjs da solo.

import Cairo from 'cairo';

export const BOX_W = 130;
export const BOX_H = 150;
export const FEET_Y = 146;          // dove poggiano i piedi, in unità del riquadro

const OUTLINE = '#2e261e';
const LINE_CAP_BUTT = 0, LINE_CAP_ROUND = 1, LINE_JOIN_ROUND = 1;

// ── percorsi SVG → comandi assoluti ──────────────────────────────────────
const _cache = new Map();

export function parsePath(d) {
    let hit = _cache.get(d);
    if (hit)
        return hit;
    const tok = d.match(/[MmLlHhVvQqTtCcZz]|-?(?:\d+\.?\d*|\.\d+)(?:e[-+]?\d+)?/g) || [];
    const ops = [];
    let i = 0, cmd = '', x = 0, y = 0, sx = 0, sy = 0, qx = null, qy = null;
    const num = () => parseFloat(tok[i++]);
    const quad = (x1, y1, ex, ey) => {
        ops.push(['C', x + 2 / 3 * (x1 - x), y + 2 / 3 * (y1 - y),
            ex + 2 / 3 * (x1 - ex), ey + 2 / 3 * (y1 - ey), ex, ey]);
        qx = x1; qy = y1; x = ex; y = ey;
    };
    while (i < tok.length) {
        if (/[A-Za-z]/.test(tok[i]))
            cmd = tok[i++];
        const rel = cmd === cmd.toLowerCase();
        const ox = rel ? x : 0, oy = rel ? y : 0;
        switch (cmd.toUpperCase()) {
        case 'M':
            x = ox + num(); y = oy + num(); sx = x; sy = y;
            ops.push(['M', x, y]);
            cmd = rel ? 'l' : 'L';          // le coppie dopo M sono linee
            qx = null;
            break;
        case 'L': x = ox + num(); y = oy + num(); ops.push(['L', x, y]); qx = null; break;
        case 'H': x = (rel ? x : 0) + num(); ops.push(['L', x, y]); qx = null; break;
        case 'V': y = (rel ? y : 0) + num(); ops.push(['L', x, y]); qx = null; break;
        case 'Q': {
            const x1 = ox + num(), y1 = oy + num(), ex = ox + num(), ey = oy + num();
            quad(x1, y1, ex, ey);
            break;
        }
        case 'T': {
            const x1 = qx === null ? x : 2 * x - qx, y1 = qy === null ? y : 2 * y - qy;
            const ex = ox + num(), ey = oy + num();
            quad(x1, y1, ex, ey);
            break;
        }
        case 'C': {
            const a = [ox + num(), oy + num(), ox + num(), oy + num(), ox + num(), oy + num()];
            ops.push(['C', ...a]);
            x = a[4]; y = a[5]; qx = null;
            break;
        }
        case 'Z':
            ops.push(['Z']); x = sx; y = sy; qx = null;
            break;
        default:
            i++;                             // simbolo sconosciuto: si salta
        }
    }
    if (_cache.size > 400)
        _cache.clear();
    _cache.set(d, ops);
    return ops;
}

function path(cr, d) {
    cr.newPath();
    for (const o of parsePath(d)) {
        if (o[0] === 'M') cr.moveTo(o[1], o[2]);
        else if (o[0] === 'L') cr.lineTo(o[1], o[2]);
        else if (o[0] === 'C') cr.curveTo(o[1], o[2], o[3], o[4], o[5], o[6]);
        else cr.closePath();
    }
}

// ── colori e trasformazioni ───────────────────────────────────────────────
function rgba(c, a = 1) {
    if (c.startsWith('rgba')) {
        const v = c.slice(5, -1).split(',').map(Number);
        return [v[0] / 255, v[1] / 255, v[2] / 255, v[3] * a];
    }
    const n = parseInt(c.slice(1), 16);
    return [(n >> 16 & 255) / 255, (n >> 8 & 255) / 255, (n & 255) / 255, a];
}

/** Colore ('#rrggbb', 'rgba(...)') o gradiente:
 *  ['lin', x0, y0, x1, y1, [[offset, colore, alfa?], ...]]
 *  ['rad', cx0, cy0, r0, cx1, cy1, r1, [[offset, colore, alfa?], ...]] */
function src(cr, c, a = 1) {
    if (Array.isArray(c)) {
        const pat = c[0] === 'lin'
            ? new Cairo.LinearGradient(c[1], c[2], c[3], c[4])
            : new Cairo.RadialGradient(c[1], c[2], c[3], c[4], c[5], c[6]);
        for (const [o, color, alpha = 1] of c[c.length - 1]) {
            const v = rgba(color, alpha * a);
            pat.addColorStopRGBA(o, v[0], v[1], v[2], v[3]);
        }
        cr.setSource(pat);
        return;
    }
    const v = rgba(c, a);
    cr.setSourceRGBA(v[0], v[1], v[2], v[3]);
}

/** Applica una trasformazione scritta come in SVG:
 *  "translate(x y) rotate(a cx cy) scale(sx sy)". */
export function transform(cr, t) {
    if (!t)
        return;
    for (const m of t.matchAll(/(translate|rotate|scale)\(([^)]*)\)/g)) {
        const v = m[2].trim().split(/[\s,]+/).map(Number);
        if (m[1] === 'translate') {
            cr.translate(v[0], v[1] || 0);
        } else if (m[1] === 'scale') {
            cr.scale(v[0], v.length > 1 ? v[1] : v[0]);
        } else {
            const a = v[0] * Math.PI / 180;
            if (v.length >= 3) {
                cr.translate(v[1], v[2]);
                cr.rotate(a);
                cr.translate(-v[1], -v[2]);
            } else {
                cr.rotate(a);
            }
        }
    }
}

// ── forme ────────────────────────────────────────────────────────────────
// fill/stroke: colore o null; o: contorno standard (1,1 unità, scuro)
function shape(cr, d, fill, {o = false, stroke = null, w = 1, cap = LINE_CAP_BUTT, a = 1} = {}) {
    path(cr, d);
    paint(cr, fill, o ? OUTLINE : stroke, o ? 1.1 : w, cap, a);
}

function paint(cr, fill, stroke, w, cap = LINE_CAP_BUTT, a = 1) {
    if (fill) {
        src(cr, fill, a);
        if (stroke) cr.fillPreserve(); else cr.fill();
    }
    if (stroke) {
        src(cr, stroke, a);
        cr.setLineWidth(w);
        cr.setLineCap(cap);
        cr.setLineJoin(LINE_JOIN_ROUND);
        cr.stroke();
    }
}

function ellipse(cr, cx, cy, rx, ry, fill, opts = {}) {
    cr.newPath();
    cr.save();
    cr.translate(cx, cy);
    cr.scale(rx, ry);
    cr.arc(0, 0, 1, 0, 2 * Math.PI);
    cr.restore();
    paint(cr, fill, opts.o ? OUTLINE : opts.stroke || null, opts.o ? 1.1 : opts.w || 1, LINE_CAP_BUTT, opts.a ?? 1);
}

const circle = (cr, cx, cy, r, fill, opts) => ellipse(cr, cx, cy, r, r, fill, opts);

function rect(cr, x, y, w, h, rx, fill, opts = {}) {
    const r = Math.min(rx, w / 2, h / 2);
    cr.newPath();
    if (r <= 0) {
        cr.rectangle(x, y, w, h);
    } else {
        cr.arc(x + w - r, y + r, r, -Math.PI / 2, 0);
        cr.arc(x + w - r, y + h - r, r, 0, Math.PI / 2);
        cr.arc(x + r, y + h - r, r, Math.PI / 2, Math.PI);
        cr.arc(x + r, y + r, r, Math.PI, 1.5 * Math.PI);
        cr.closePath();
    }
    paint(cr, fill, opts.o ? OUTLINE : opts.stroke || null, opts.o ? 1.1 : opts.w || 1);
}

const line = (cr, d, color, w, cap = LINE_CAP_BUTT, a = 1) => shape(cr, d, null, {stroke: color, w, cap, a});

function group(cr, t, alpha, fn) {
    if (alpha <= 0.01)
        return;
    cr.save();
    transform(cr, t);
    if (alpha < 0.99) {
        cr.pushGroup();
        fn();
        cr.popGroupToSource();
        cr.paintWithAlpha(alpha);
    } else {
        fn();
    }
    cr.restore();
}

// ── pelo disegnato a mano, ma calcolato una volta sola ───────────────────
// Un generatore pseudo-casuale con il seme fisso: lo stesso pelo a ogni
// fotogramma (niente tremolio) e a ogni avvio.
function seeded(seed) {
    let x = seed >>> 0 || 1;
    return () => (x = Math.imul(x ^ x >>> 15, 0x2c1b3c6d) + 0x9e3779b9 >>> 0) / 4294967296;
}

const deg = a => a * Math.PI / 180;
const r1 = v => Math.round(v * 10) / 10;

/** Un contorno d'ellisse che, fra gli angoli `from` e `to` (gradi, in senso
 *  orario, 0 = destra), diventa una frangia di ciuffi: `len(a)` è la
 *  lunghezza del ciuffo all'angolo a. Fuori da quell'arco è liscio. */
function furEllipse(cx, cy, rx, ry, from, to, n, len, seed) {
    const rnd = seeded(seed);
    const pt = (a, k = 1) => [r1(cx + Math.cos(deg(a)) * rx * k), r1(cy + Math.sin(deg(a)) * ry * k)];
    const span = to - from, step = span / n;
    let d = `M${pt(from).join(' ')}`;
    for (let i = 0; i < n; i++) {
        const a0 = from + i * step, a1 = a0 + step;
        const am = a0 + step * (0.45 + rnd() * 0.25);
        const l = len(am) * (0.75 + rnd() * 0.5);
        const lean = (rnd() - 0.35) * step * 0.5;         // i ciuffi si piegano un po'
        const at = (a, rr) => [r1(cx + Math.cos(deg(a)) * (rx + rr)), r1(cy + Math.sin(deg(a)) * (ry + rr))];
        const w = step * 0.16;                            // punta arrotondata, morbida
        const tipA = at(am + lean - w, l * 0.92), tipB = at(am + lean + w, l * 0.92), top = at(am + lean, l * 1.12);
        const c0 = pt(a0 + step * 0.25, 1 + l / rx * 0.55);
        const c1 = pt(a1 - step * 0.2, 1 + l / rx * 0.4);
        d += ` Q${c0.join(' ')} ${tipA.join(' ')} Q${top.join(' ')} ${tipB.join(' ')} Q${c1.join(' ')} ${pt(a1).join(' ')}`;
    }
    // il resto dell'ellisse, liscio: quattro archi di quadratica
    const rest = 360 - span, k = 1 / Math.cos(deg(rest / 8));
    for (let i = 0; i < 4; i++) {
        const a0 = to + i * rest / 4, a1 = a0 + rest / 4;
        d += ` Q${pt((a0 + a1) / 2, k).join(' ')} ${pt(a1).join(' ')}`;
    }
    return `${d} Z`;
}

/** Tratti di pelo dentro un'ellisse: corti, inclinati verso l'esterno. */
function furHatch(cx, cy, rx, ry, n, seed, {from = 0, to = 360, minR = 0.25, maxR = 0.95, len = 3} = {}) {
    const rnd = seeded(seed), out = [];
    for (let i = 0; i < n; i++) {
        const a = deg(from + rnd() * (to - from)), r = minR + rnd() * (maxR - minR);
        const x = cx + Math.cos(a) * rx * r, y = cy + Math.sin(a) * ry * r;
        const l = len * (0.6 + rnd() * 0.8), b = a + (rnd() - 0.5) * 0.8;
        out.push(`M${r1(x)} ${r1(y)} q${r1(Math.cos(b) * l * 0.6)} ${r1(Math.sin(b) * l * 0.6 - 0.4)} ${r1(Math.cos(b) * l)} ${r1(Math.sin(b) * l)}`);
    }
    return out;
}

// testa: sopra liscia, sotto la gorgiera a ciuffi, più lunghi sulle guance
const HEAD_FUR = furEllipse(66, 48.5, 34, 27, -30, 210, 26,
    a => 2.2 + 3.6 * Math.pow(Math.abs(Math.cos(deg(a))), 0.7) + 1.4 * Math.max(0, Math.sin(deg(a))), 11);
// guance e mento chiari, con la frangia verso l'alto
const CHEEK_FUR = furEllipse(66, 62, 27, 12.5, 188, 352, 16, () => 2, 23);
const HEAD_HATCH_D = furHatch(66, 46, 31, 24, 46, 5, {from: 190, to: 350, len: 2.6});
const HEAD_HATCH_L = furHatch(66, 50, 32, 25, 34, 9, {from: 200, to: 340, len: 2.2});
const RUFF_HATCH = furHatch(66, 50, 34, 27, 40, 17, {from: -15, to: 195, minR: 0.8, maxR: 1.15, len: 3.4});
const SPOTS = (() => {                      // macchie della fronte, irregolari
    const rnd = seeded(31), out = [];
    for (const [x, y, s] of [[56, 29, 1.7], [61.5, 26.6, 1.9], [67, 26, 1.9], [72.5, 27, 1.7], [77, 29.5, 1.6],
        [58.5, 33, 1.3], [64, 31.4, 1.5], [69.5, 31.6, 1.4], [74.5, 33.5, 1.2], [52, 32.5, 1.2], [81, 33, 1.1],
        [61, 36.6, 0.9], [71, 36.4, 0.9], [48.5, 30, 0.8], [84.5, 30.5, 0.8]])
        out.push([x, y, s * (0.85 + rnd() * 0.3), s * (0.6 + rnd() * 0.3), (rnd() - 0.5) * 70]);
    return out;
})();

// ── le parti ─────────────────────────────────────────────────────────────
// Luce dall'alto a sinistra: ogni volume ha un gradiente dal chiaro allo
// scuro, il contorno esterno è più spesso di quelli interni, il pelo ha
// frange di ciuffi e tratti sottili. I colori del manul vengono
// dall'illustrazione di Pallasio: grigio caldo, guance chiare, bande nere.
const FUR = '#aea594', FUR_L = '#dcd6ca', FUR_D = '#857c6d', FUR_DD = '#625a4f';
const STRIPE = '#2b2621', CREAM = '#ece6de', BELLY = '#ddd0cc';
const JACKET = '#e9dab6', JACKET_L = '#f6eed8', JACKET_D = '#c7b58a';
const lin = (x0, y0, x1, y1, ...stops) => ['lin', x0, y0, x1, y1, stops];
const rad = (cx, cy, r0, r1, ...stops) => ['rad', cx, cy, r0, cx, cy, r1, stops];
const W_OUT = 1.5, W_IN = 0.9;           // contorno esterno e interno

function furStrokes(cr, list, color, w, a = 1) {
    for (const d of list)
        line(cr, d, color, w, LINE_CAP_ROUND, a);
}

function spot(cr, x, y, rx, ry, rot, color) {
    cr.save();
    cr.translate(x, y);
    cr.rotate(deg(rot));
    ellipse(cr, 0, 0, rx, ry, color);
    cr.restore();
}

// la coda: folta, ad anelli, con i ciuffi ai lati e la punta nera
function tail(cr, m) {
    const ops = parsePath(m.d.tail);
    const [, x0, y0] = ops[0], [, c1x, c1y, c2x, c2y, x1, y1] = ops[1];
    const at = t => {
        const u = 1 - t;
        return [u * u * u * x0 + 3 * u * u * t * c1x + 3 * u * t * t * c2x + t * t * t * x1,
            u * u * u * y0 + 3 * u * u * t * c1y + 3 * u * t * t * c2y + t * t * t * y1];
    };
    const tufts = [];
    let s = 0, prev = at(0);
    for (let i = 1; i <= 16; i++) {
        const t = i / 17, p = at(t), q = at(t + 0.01);
        s += Math.hypot(p[0] - prev[0], p[1] - prev[1]);
        prev = p;
        const tx = q[0] - p[0], ty = q[1] - p[1], n = Math.hypot(tx, ty) || 1;
        const nx = -ty / n, ny = tx / n, side = i % 2 ? 1 : -1;
        const dark = ((s + 6) % 11 + 11) % 11 < 4;           // come i trattini degli anelli
        tufts.push({p, nx: nx * side, ny: ny * side, ux: tx / n, uy: ty / n, dark});
    }
    const tuft = (k, color) => {
        for (const f of tufts) {
            const bx2 = f.p[0] + f.nx * 4.6, by2 = f.p[1] + f.ny * 4.6;
            shape(cr, `M${bx2 - f.ux * 3 * k} ${by2 - f.uy * 3 * k} Q${bx2 + f.nx * 3.4 * k} ${by2 + f.ny * 3.4 * k} ${bx2 + f.nx * 2.6 * k + f.ux * 2.6} ${by2 + f.ny * 2.6 * k + f.uy * 2.6} Q${bx2 + f.nx * 0.8} ${by2 + f.ny * 0.8} ${bx2 + f.ux * 3 * k} ${by2 + f.uy * 3 * k}Z`,
                color ?? (f.dark ? STRIPE : FUR));
        }
    };
    tuft(1.25, OUTLINE);
    line(cr, m.d.tail, OUTLINE, 15.8, LINE_CAP_ROUND);
    tuft(1);
    line(cr, m.d.tail, FUR, 13, LINE_CAP_ROUND);
    cr.setDash([4, 7], -6);
    line(cr, m.d.tail, STRIPE, 13, LINE_CAP_BUTT);
    cr.setDash([], 0);
    cr.save();
    cr.translate(1.6, -1.4);
    line(cr, m.d.tail, FUR_L, 2.6, LINE_CAP_ROUND, 0.5);
    cr.restore();
    circle(cr, m.tailTip[0], m.tailTip[1], 6.6, rad(m.tailTip[0] - 2, m.tailTip[1] - 2, 0, 7, [0, '#4a4036'], [1, '#1d1814']));
}

function leg(cr, x, dark) {
    const base = dark ? FUR_D : FUR;
    rect(cr, x, 116, 14, 25, 7, lin(x, 0, x + 14, 0, [0, dark ? FUR : FUR_L], [1, base]),
        {stroke: OUTLINE, w: W_OUT});
    ellipse(cr, x + 8, 141, 10.5, 5, lin(0, 136, 0, 146, [0, dark ? FUR : FUR_L], [1, base]),
        {stroke: OUTLINE, w: W_OUT});
    line(cr, `M${x + 4} 138.6 v3.2 M${x + 8} 138.3 v3.8 M${x + 12} 138.6 v3.2`, OUTLINE, W_IN, LINE_CAP_ROUND);
    furStrokes(cr, [`M${x + 2.5} 121 l2.4 2`, `M${x + 3} 127 l2.4 2`, `M${x + 10} 124 l2 1.6`, `M${x + 11} 130 l1.6 1.6`],
        FUR_DD, 0.7, 0.7);
}

function beans(cr) {
    ellipse(cr, 78, 141, 5.2, 3.8, rad(77, 140, 0, 5, [0, '#e6aaa8'], [1, '#c07f7d']));
    for (const [x, y] of [[71.8, 137], [75.9, 135.3], [80.1, 135.3], [84.2, 137]])
        ellipse(cr, x, y, 1.9, 1.7, '#cc8c89');
}

function body(cr) {
    // pelo del corpo (si vede ai lati e sotto la giacca)
    shape(cr, 'M63 66 C 30 66 22 92 26 110 C 29 126 44 134 63 134 C 84 134 99 126 101 110 C 104 92 96 66 63 66 Z',
        rad(52, 88, 6, 62, [0, FUR_L], [0.6, FUR], [1, FUR_D]), {stroke: OUTLINE, w: W_OUT});
    // giacca, con la luce da sinistra
    shape(cr, 'M63 68 C 32 68 25 92 28 110 C 30 122 40 128 50 129 L66 126 L82 129 C 92 128 99 122 100 110 C 103 92 95 68 63 68 Z',
        lin(30, 72, 100, 124, [0, JACKET_L], [0.45, JACKET], [1, JACKET_D]), {stroke: OUTLINE, w: W_OUT});
    shape(cr, 'M31 108 C 33 121 41 127 50 128 L58 127 C 46 122 38 113 35 97 Z', JACKET_D, {a: 0.55});
    shape(cr, 'M97 100 C 99 112 94 122 84 127 L82 128 C 90 120 93 111 92 100 Z', JACKET_D, {a: 0.6});
    line(cr, 'M36 84 q3 8 1 15 M93 85 q-2 7 0 13 M44 120 q6 3 12 3', JACKET_D, W_IN, LINE_CAP_ROUND, 0.9);
    shape(cr, 'M79 109.5 L93 107.5 L93.6 111.6 L79.6 113.6Z', lin(0, 108, 0, 114, [0, JACKET], [1, JACKET_D]),
        {stroke: OUTLINE, w: W_IN});
    // la pancia, rosata come nell'illustrazione, spunta sotto il bottone
    shape(cr, 'M60 112 L66 107.5 L72 112 L71 127.5 L66 126 L61 127.5Z', lin(60, 110, 72, 128, [0, '#efe6e3'], [1, BELLY]),
        {stroke: OUTLINE, w: W_IN});
    furStrokes(cr, ['M63 116 q1.4 1.6 0 3.2', 'M69 116 q1.4 1.6 0 3.2', 'M66 121 q1.4 1.6 0 3.2', 'M63.5 124 l1 1.6'], '#bfaeaa', 0.8);
    // camicia, revers, colletto
    shape(cr, 'M55 74 L77 74 L70 102 L66 106 L62 102Z', lin(55, 74, 77, 104, [0, '#ffffff'], [1, '#e7e2d8']),
        {stroke: OUTLINE, w: W_IN});
    shape(cr, 'M55 74 L62 102 L57 98 L47 82 L53 79Z', lin(47, 78, 62, 100, [0, '#e6d7b1'], [1, '#cdbb90']),
        {stroke: OUTLINE, w: W_IN});
    shape(cr, 'M77 74 L70 102 L75 98 L85 82 L79 79Z', lin(85, 78, 70, 100, [0, '#d7c69c'], [1, '#bfac80']),
        {stroke: OUTLINE, w: W_IN});
    line(cr, 'M54 80 l5 15 M78 80 l-5 15', '#bba977', 0.6, LINE_CAP_ROUND, 0.8);
    shape(cr, 'M56.5 76 L66 82 L60 87Z M75.5 76 L66 82 L72 87Z', '#fbfaf6', {stroke: OUTLINE, w: W_IN});
    // cravatta di seta, con riflesso
    shape(cr, 'M64.4 86 L67.6 86 L69.8 99 L66 103.8 L62.2 99Z', lin(62, 86, 70, 100, [0, '#cf3a3f'], [0.55, '#ac2329'], [1, '#7f171c']),
        {stroke: OUTLINE, w: W_IN});
    line(cr, 'M65 89 l3 2.5 M64.4 93 l4.4 3.6 M63.6 97 l4.8 3.6', '#6f1418', 0.7);
    line(cr, 'M64.6 88 l-0.9 10', '#f08a8c', 0.7, LINE_CAP_ROUND, 0.6);
    shape(cr, 'M63.4 81 L68.6 81 L67.7 86.2 L64.3 86.2Z', lin(63, 81, 69, 86, [0, '#d8474c'], [1, '#9e1f25']),
        {stroke: OUTLINE, w: W_IN});
    line(cr, 'M57.5 104 l4.6 2.2 M74.5 104 l-4.6 2.2 M56.5 109.5 l4.2 -1.2 M75.5 109.5 l-4.2 -1.2', '#b19f72', 0.8, LINE_CAP_ROUND);
    circle(cr, 66, 106.6, 2.1, rad(65.3, 105.9, 0, 2.2, [0, '#a07a52'], [1, '#5f4127']), {stroke: OUTLINE, w: W_IN});
    circle(cr, 65.4, 106, 0.55, '#e7cfa9');
}

// copertina vecchia e consunta: pelle scolorita, angoli rovinati, macchie
const LEATHER = ['#8b5a34', '#6e4224', '#4d2c16'];
function wear(cr, spots) {
    for (const [x, y, rx, ry, a] of spots)
        ellipse(cr, x, y, rx, ry, '#c8a27a', {a});
}

// il tomo chiuso: si vede la copertina
function bookClosed(cr) {
    rect(cr, -13, -16.5, 26, 33, 1.6, lin(-13, -16, 13, 16, [0, LEATHER[0]], [0.6, LEATHER[1]], [1, LEATHER[2]]),
        {stroke: OUTLINE, w: W_OUT});
    rect(cr, -13, -16.5, 5, 33, 0, lin(-13, 0, -8, 0, [0, '#3f2410'], [1, '#5a3418']));
    line(cr, 'M-12.6 -11 h4.2 M-12.6 -6 h4.2 M-12.6 6 h4.2 M-12.6 11 h4.2', '#b8964e', 0.9);
    rect(cr, 13, -15.2, 2.2, 30.4, 0, lin(13, 0, 15, 0, [0, '#efe1bf'], [1, '#c9b78e']), {stroke: OUTLINE, w: W_IN});
    line(cr, 'M14 -12 v2 M14 -6 v3 M14 3 v2 M14 9 v3', '#a9966e', 0.4);              // pagine ingiallite
    wear(cr, [[3, 8, 5, 3, 0.28], [-4, -10, 3, 2, 0.22], [8, -12, 2.5, 1.6, 0.25], [9, 13, 3, 1.8, 0.3]]);
    rect(cr, -6, -13.5, 17, 27, 0, null, {stroke: '#b8964e', w: 0.8});
    rect(cr, -4.5, -12, 14, 24, 0, null, {stroke: '#b8964e', w: 0.45});
    rect(cr, -2, -6.5, 9, 6, 0.8, lin(0, -6.5, 0, -0.5, [0, '#d7b866'], [1, '#9c7a30']), {stroke: '#6f521a', w: 0.5});
    line(cr, 'M-0.5 -4.6 h6 M-0.5 -2.6 h4', '#4e3510', 0.6);
    shape(cr, 'M13 13 L9.6 16.5 L13 16.5Z M13 -13.4 L10 -16.5 L13 -16.5Z', '#d9c39a', {stroke: OUTLINE, w: 0.6}); // angoli consumati
    line(cr, 'M-7 -15.8 L10 -15.8', '#b27b4d', 0.7, LINE_CAP_BUTT, 0.7);
}

// il tomo aperto visto da chi guarda: le due copertine e il dorso, sopra il
// taglio delle pagine; le pagine scritte le vede solo Pallasio
function bookOpen(cr) {
    shape(cr, 'M-24 -10.5 L0 -14.5 L24 -10.5 L22 -7.5 L0 -10.8 L-22 -7.5Z', lin(0, -14, 0, -8, [0, '#f4e7c6'], [1, '#cdb98d']),
        {stroke: OUTLINE, w: W_IN});
    line(cr, 'M-20 -9.6 L0 -12.6 L20 -9.6 M-16 -9.2 L0 -11.6', '#b8a578', 0.45);
    shape(cr, 'M-25 -9 L-2.2 -11.2 L-2.2 17 L-25 14.6Z', lin(-25, -9, -2, 17, [0, LEATHER[0]], [1, LEATHER[2]]),
        {stroke: OUTLINE, w: W_OUT});
    shape(cr, 'M25 -9 L2.2 -11.2 L2.2 17 L25 14.6Z', lin(25, -9, 2, 17, [0, '#7c4e2c'], [1, '#43260f']),
        {stroke: OUTLINE, w: W_OUT});
    wear(cr, [[-15, 8, 5, 3, 0.25], [-20, -4, 2.4, 1.6, 0.2], [15, 9, 4, 2.4, 0.22], [19, -5, 2.6, 1.6, 0.25]]);
    shape(cr, 'M-2.6 -11.6 L2.6 -11.6 L2.6 17.6 L-2.6 17.6Z', lin(-2.6, 0, 2.6, 0, [0, '#3f2410'], [0.5, '#6e4224'], [1, '#3f2410']),
        {stroke: OUTLINE, w: W_IN});
    line(cr, 'M-2.4 -6 h4.8 M-2.4 -1 h4.8 M-2.4 9 h4.8 M-2.4 14 h4.8', '#b8964e', 0.8);
    shape(cr, 'M-22.5 -6.8 L-5 -8.6 L-5 13.8 L-22.5 12Z', null, {stroke: '#b8964e', w: 0.7});
    shape(cr, 'M22.5 -6.8 L5 -8.6 L5 13.8 L22.5 12Z', null, {stroke: '#b8964e', w: 0.7});
    shape(cr, 'M9 -1 L18.5 -1.9 L18.5 4.4 L9 5.3Z', lin(0, -2, 0, 5, [0, '#d7b866'], [1, '#9c7a30']), {stroke: '#6f521a', w: 0.5});
    line(cr, 'M10.5 1 l6 -0.6 M10.5 3 l4 -0.4', '#4e3510', 0.55);
    shape(cr, 'M-25 14.6 L-22 14.9 L-25 11.6Z M25 14.6 L22 14.9 L25 11.6Z', '#d9c39a', {stroke: OUTLINE, w: 0.6});
}

// zampa pelosa, con le unghie chiare come nell'illustrazione
function paw(cr, p, color) {
    const [x, y] = p;
    shape(cr, `M${x - 5.6} ${y} Q${x - 6.6} ${y - 3.2} ${x - 4.4} ${y - 4.6} L${x - 3.8} ${y - 6.6} L${x - 2.4} ${y - 5.2} Q${x} ${y - 6.4} ${x + 2.4} ${y - 5.2} L${x + 3.8} ${y - 6.6} L${x + 4.4} ${y - 4.6} Q${x + 6.6} ${y - 3.2} ${x + 5.6} ${y} Q${x + 5.6} ${y + 5.8} ${x} ${y + 5.8} Q${x - 5.6} ${y + 5.8} ${x - 5.6} ${y}Z`,
        rad(x - 1.6, y - 1.8, 0.5, 6.6, [0, FUR_L], [0.7, color], [1, FUR_D]), {stroke: OUTLINE, w: W_OUT});
    line(cr, `M${x - 2.6} ${y + 1.4} v2.4 M${x} ${y + 2} v2.6 M${x + 2.6} ${y + 1.4} v2.4`, OUTLINE, 0.7, LINE_CAP_ROUND);
    line(cr, `M${x - 3.2} ${y + 5} q0.3 0.8 0.9 1 M${x - 0.4} ${y + 5.5} q0.3 0.8 0.9 1 M${x + 2.4} ${y + 5} q0.3 0.8 0.9 1`,
        '#e9e2d4', 0.7, LINE_CAP_ROUND, 0.9);
}

function arm(cr, d, crease, light, shade, p, pawColor) {
    line(cr, d, OUTLINE, 12.8, LINE_CAP_ROUND);
    line(cr, d, light, 10, LINE_CAP_ROUND);
    cr.save();
    cr.translate(1.2, 1.4);
    line(cr, d, shade, 2.6, LINE_CAP_ROUND, 0.35);
    cr.restore();
    line(cr, crease, shade, 1.6);
    paw(cr, p, pawColor);
}

function head(cr, m) {
    for (const [side, t, flip] of [[-1, m.tr.earL, 1], [1, m.tr.earR, -1]]) {
        group(cr, t, 1, () => {
            const x = side < 0 ? 30 : 102;
            shape(cr, side < 0 ? 'M30 42 Q27 31 42 31.5 Q40.5 40 30 42Z' : 'M102 42 Q105 31 90 31.5 Q91.5 40 102 42Z',
                lin(x, 31, x + 12 * flip, 42, [0, FUR], [1, FUR_DD]), {stroke: OUTLINE, w: W_OUT});
            shape(cr, side < 0 ? 'M33 39.4 Q32 34 39.5 34 Q37.5 38 33 39.4Z' : 'M99 39.4 Q100 34 92.5 34 Q94.5 38 99 39.4Z',
                lin(x, 34, x + 7 * flip, 39, [0, '#d9b8ae'], [1, '#a98479']));
            line(cr, side < 0 ? 'M33.6 37.6 l2.8 -2 M35 38.4 l3 -1.4' : 'M98.4 37.6 l-2.8 -2 M97 38.4 l-3 -1.4', '#f6f1e8', 0.6, LINE_CAP_ROUND);
        });
    }
    // testa: gradiente caldo, frangia di ciuffi, trama del pelo
    shape(cr, HEAD_FUR, rad(58, 34, 4, 50, [0, '#dcd6ca'], [0.55, '#b8ae9d'], [1, '#8a8072']), {stroke: OUTLINE, w: 1.25});
    furStrokes(cr, HEAD_HATCH_D, FUR_DD, 0.55, 0.45);
    furStrokes(cr, HEAD_HATCH_L, '#f2ede4', 0.5, 0.5);
    furStrokes(cr, RUFF_HATCH, '#efe9de', 0.6, 0.7);
    // guance e mento chiari
    shape(cr, CHEEK_FUR, lin(0, 50, 0, 76, [0, '#f3eee6'], [1, '#d8d0c3']));
    for (const [x, y, rx, ry, rot] of SPOTS)
        spot(cr, x, y, rx, ry, rot, '#2f2924');
    line(cr, 'M61.5 39.5 q4.5 2.6 9 0 M62.6 42 q3.4 1.8 6.8 0', '#6c6356', 0.8, LINE_CAP_ROUND);   // fronte corrugata
    // le bande nere delle guance, spesse, con le punte sfrangiate
    shape(cr, 'M33.6 49.5 q8 8.6 17 8.6 l-0.8 3.2 q-10 -0.6 -17.2 -7.8 l-2 0.6Z M32.6 57 q8.4 8.4 17.6 8.2 l-0.8 3.4 q-10.6 -0.8 -17.8 -7.6 l-1.8 0.4Z M98.4 49.5 q-8 8.6 -17 8.6 l0.8 3.2 q10 -0.6 17.2 -7.8 l2 0.6Z M99.4 57 q-8.4 8.4 -17.6 8.2 l0.8 3.4 q10.6 -0.8 17.8 -7.6 l1.8 0.4Z',
        STRIPE);
    furStrokes(cr, ['M37 55.6 l-1.2 2.4', 'M42 59.2 l-1 2.4', 'M37 62.4 l-1.2 2.4', 'M45 65.6 l-0.8 2',
        'M95 55.6 l1.2 2.4', 'M90 59.2 l1 2.4', 'M95 62.4 l1.2 2.4', 'M87 65.6 l0.8 2'], STRIPE, 0.8);
    // muso
    shape(cr, 'M66 54 C 56 54 52 60 53 64 C 54 69 60 71 66 71 C 72 71 78 69 79 64 C 80 60 76 54 66 54 Z',
        rad(63, 58, 1, 15, [0, '#ffffff'], [0.7, '#f1ebe1'], [1, '#d8cebf']), {stroke: OUTLINE, w: W_IN});
    for (const [x, y] of [[58, 61], [60, 63.5], [57.5, 64.5], [59.6, 59.4], [74, 61], [72, 63.5], [74.5, 64.5], [72.4, 59.4]])
        circle(cr, x, y, 0.45, '#7d7364');
    // occhi: pelle chiara attorno, borse sotto, iride gialla
    for (const cx of [55, 77]) {
        ellipse(cr, cx, 48.4, 7.6, 6.2, '#e9e3d8', {a: 0.85});
        circle(cr, cx, 47, 5.1, '#fbf6e6', {stroke: OUTLINE, w: W_IN});
        circle(cr, cx, 47, 4.4, rad(cx - 0.8, 46, 0.5, 4.6, [0, '#eee07a'], [0.6, '#d7bc3c'], [1, '#97741c']));
    }
    group(cr, m.tr.pup, 1, () => {
        for (const cx of [55, 77]) {
            ellipse(cr, cx, 47, 1.2, 3.1, '#110e0a');
            circle(cr, cx + 1.4, 45.4, 0.8, '#ffffff');
            circle(cr, cx - 1.2, 48.6, 0.35, '#ffffff', {a: 0.8});
        }
    });
    shape(cr, m.d.lid1, lin(49, 41, 49, 48, [0, '#cfc8b9'], [1, '#aca394']), {stroke: OUTLINE, w: W_IN});
    shape(cr, m.d.lid2, lin(71, 41, 71, 48, [0, '#c6bfb0'], [1, '#a1988a']), {stroke: OUTLINE, w: W_IN});
    line(cr, 'M50.6 52.3 q4.4 1.6 8.8 0 M72.6 52.3 q4.4 1.6 8.8 0 M51.6 54 q3.4 1 6.8 0 M73.6 54 q3.4 1 6.8 0',
        '#857a6b', 0.55, LINE_CAP_ROUND);
    line(cr, m.d.brows, '#231c15', 2.9, LINE_CAP_ROUND);
    // occhialini tondi: lenti con il riflesso, montatura con la luce
    for (const cx of [55, 77]) {
        circle(cr, cx, 47.5, 7.4, rad(cx - 2.5, 45, 0, 8, [0, 'rgba(255,255,255,0.34)'], [0.6, 'rgba(225,238,246,0.12)'], [1, 'rgba(200,220,235,0.24)']),
            {stroke: '#1b1712', w: 1.8});
        line(cr, `M${cx - 5.4} ${45.2} q1.6 -3 5 -3.6`, '#ffffff', 1, LINE_CAP_ROUND, 0.9);
        line(cr, `M${cx + 3.5} ${51.5} q1.6 -1 2.4 -2.8`, '#ffffff', 0.7, LINE_CAP_ROUND, 0.5);
        cr.newPath();
        cr.arc(cx, 47.5, 7.4, Math.PI * 1.08, Math.PI * 1.42);
        src(cr, '#8a7e6c');
        cr.setLineWidth(0.6);
        cr.stroke();
    }
    line(cr, 'M62.4 46.6 q3.6 -2.6 7.2 0 M47.6 46.4 l-11 -4 M84.4 46.4 l11 -4', '#1b1712', 1.4, LINE_CAP_ROUND);
    // naso rosa, più grande, con le narici
    shape(cr, 'M61.6 56.2 q4.4 -2 8.8 0 q-0.6 2.6 -4.4 4.8 q-3.8 -2.2 -4.4 -4.8z',
        lin(62, 54, 66, 61, [0, '#e2a4a6'], [1, '#b26e72']), {stroke: OUTLINE, w: W_IN});
    line(cr, 'M63.6 57.6 q0.8 0.6 1.4 0.1 M68.4 57.6 q-0.8 0.6 -1.4 0.1', '#6d3b3d', 0.6, LINE_CAP_ROUND);
    circle(cr, 64.4, 56.4, 0.6, '#f7dcdc');
    if (m.op.snarl > 0.01)
        line(cr, 'M58 58 q2 -2 4 -1 M70 57 q2 -1 4 1 M60 59.6 q1.5 -1 3 -0.6', '#7d725f', 0.9, LINE_CAP_ROUND, m.op.snarl);
    line(cr, 'M66 61 v2', OUTLINE, W_IN);
    // bocca: ringhiando mostra la fila di dentini, come nell'illustrazione
    if (m.mouthFill) {
        const o = m.mouthOpen ?? 0, depth = 66 + o * 2.2;
        shape(cr, m.d.mouth, lin(0, 62, 0, depth, [0, '#7a3436'], [1, '#3c1617']), {stroke: OUTLINE, w: 1.1});
        cr.save();
        path(cr, m.d.mouth);
        cr.clip();
        if (o > 0.6)
            ellipse(cr, 66, depth - 0.8, 4.2, Math.min(2.4, o * 0.5), '#c56a74');          // lingua
        for (let x = 59.2; x <= 72.9; x += 1.55) {
            const fang = Math.abs(x - 60.75) < 0.5 || Math.abs(x - 71.6) < 0.6;
            const l = fang ? 2.8 : 1.3;
            shape(cr, `M${x - 0.7} 62.6 L${x} ${63.2 + l} L${x + 0.7} 62.6Z`, '#fbf7ee', {stroke: OUTLINE, w: 0.3});
        }
        if (o > 1.2) {
            const base = y => y;
            for (let x = 60.4; x <= 71.8; x += 1.6) {
                const k = (x - 66) / 8, y = base(64 + (depth - 64) * 0.5 * (1 - k * k) + 0.6);
                shape(cr, `M${x - 0.6} ${y} L${x} ${y - 1.1} L${x + 0.6} ${y}Z`, '#f3ede0', {stroke: OUTLINE, w: 0.3});
            }
        }
        cr.restore();
    } else {
        shape(cr, m.d.mouth, null, {stroke: OUTLINE, w: 1.1});
        shape(cr, 'M61.6 64.6 l1.3 3.4 l1.2 -3', '#ffffff', {stroke: OUTLINE, w: 0.5});
        if (m.op.fangR > 0.01)
            shape(cr, 'M68 64.4 l1.2 3 l1.3 -3.4', '#ffffff', {stroke: OUTLINE, w: 0.5, a: m.op.fangR});
    }
    line(cr, 'M78 61 l21 -3.4 M78 64 l22 0.8 M78 67 l19 4.4 M54 61 l-21 -3.4 M54 64 l-22 0.8 M54 67 l-19 4.4', '#f7f3ea', 0.55, LINE_CAP_ROUND, 0.9);
    if (m.op.tear > 0.01)          // commosso: una lacrima che non ammetterà mai
        ellipse(cr, 49.5, 53, 1.1, 1.6, rad(49.2, 52.5, 0, 1.6, [0, '#ffffff'], [1, '#9fcbe6']), {a: m.op.tear});
}

function puff(cr) {
    circle(cr, 100, 62, 3, rad(99, 61, 0, 3, [0, '#f4f1ea'], [1, '#c9c4b8']));
    circle(cr, 106, 59, 2.2, rad(105.4, 58.4, 0, 2.2, [0, '#f4f1ea'], [1, '#c9c4b8']));
    circle(cr, 111, 57, 1.5, '#d8d4cc');
}

function figure(cr, m) {
    tail(cr, m);
    group(cr, m.tr.legL, 1, () => leg(cr, 46, true));
    group(cr, m.tr.legR, 1, () => {
        leg(cr, 70, false);
        if (m.op.beans > 0.01)
            beans(cr);
    });
    body(cr);
    group(cr, m.tr.book, 1 - m.op.open, () => bookClosed(cr));
    group(cr, m.tr.bookOpen, m.op.open, () => bookOpen(cr));
    arm(cr, m.d.armL, m.d.creaseL, JACKET_L, JACKET_D, m.pawL, FUR);
    if (m.op.finger > 0.01) {      // l'indice alzato, sopra la zampa
        line(cr, m.d.finger, OUTLINE, 4.6, LINE_CAP_ROUND, m.op.finger);
        line(cr, m.d.finger, FUR_L, 2.4, LINE_CAP_ROUND, m.op.finger);
    }
    arm(cr, m.d.armR, m.d.creaseR, JACKET, '#b6a275', m.pawR, FUR_D);
    group(cr, m.tr.head, 1, () => head(cr, m));
    group(cr, m.tr.puff, m.op.puff, () => puff(cr));
}

// ── la magia: apparire dal nulla, sparire nel nulla ──────────────────────
// Scintille dorate e rosa che girano a spirale, un lampo, un anello di fumo
// color ametista. Tutto dentro il riquadro di 130 × 150 unità.
const MAGIC_C = [65, 98];                      // il centro della magia: la pancia
const SPARK_GOLD = '#ffd979', SPARK_PINK = '#f5b8d3', SMOKE = '#cba6ec';
const ease = t => t < 0 ? 0 : t > 1 ? 1 : t * t * (3 - 2 * t);
const backOut = t => {
    const c = 1.9;
    return 1 + (c + 1) * Math.pow(t - 1, 3) + c * Math.pow(t - 1, 2);
};
const phase = (p, a, b) => Math.max(0, Math.min(1, (p - a) / (b - a)));

function sparkle(cr, x, y, s, color, a) {
    if (a <= 0.01 || s <= 0.05)
        return;
    circle(cr, x, y, s * 2.2, rad(x, y, 0, s * 2.2, [0, color, 0.55 * a], [1, color, 0]));
    shape(cr, `M${x} ${y - s * 1.6} Q${x} ${y} ${x + s * 1.6} ${y} Q${x} ${y} ${x} ${y + s * 1.6} Q${x} ${y} ${x - s * 1.6} ${y} Q${x} ${y} ${x} ${y - s * 1.6}Z`,
        color, {a});
    circle(cr, x, y, s * 0.4, '#ffffff', {a});
}

function sparks(cr, p, inward, t, n = 14) {
    const [cx, cy] = MAGIC_C;
    for (let i = 0; i < n; i++) {
        const k = (i * 0.618) % 1;                          // sfasate, mai in fila
        const q = Math.max(0, Math.min(1, p * 1.25 - k * 0.25));
        const r = inward ? 58 * (1 - q) + 4 : 6 + 58 * q;
        const a = (i / n) * Math.PI * 2 + (inward ? q * 3.2 : -q * 2.4) + k;
        const x = cx + Math.cos(a) * r * 0.95, y = cy + Math.sin(a) * r * 0.8;
        const tw = 0.7 + 0.3 * Math.sin(t * 0.5 + i * 1.7);
        const alpha = inward ? Math.min(1, q * 3) * (1 - phase(q, 0.85, 1)) : (1 - q);
        sparkle(cr, x, y, (2 + 2.2 * k) * tw, i % 3 ? SPARK_GOLD : SPARK_PINK, alpha);
    }
}

function smokeRing(cr, q) {
    if (q <= 0 || q >= 1)
        return;
    const [cx, cy] = MAGIC_C, r = 10 + q * 48, a = (1 - q) * 0.85;
    for (let i = 0; i < 9; i++) {
        const ang = i / 9 * Math.PI * 2 + q;
        const x = cx + Math.cos(ang) * r, y = cy + Math.sin(ang) * r * 0.62;
        circle(cr, x, y, 5 + q * 7, rad(x, y, 0, 5 + q * 7, [0, SMOKE, a], [1, SMOKE, 0]));
    }
}

function flash(cr, q) {
    if (q <= 0 || q >= 1)
        return;
    const [cx, cy] = MAGIC_C, s = Math.sin(q * Math.PI);
    circle(cr, cx, cy, 6 + 26 * s, rad(cx, cy, 0, 6 + 26 * s, [0, '#ffffff', 0.9 * s], [0.35, SPARK_GOLD, 0.5 * s], [1, SPARK_PINK, 0]));
    sparkle(cr, cx, cy, 5 * s, '#fff4d6', s);
}

/** Disegna Pallasio. Il contesto è già scalato: 1 unità = 1/130 della
 *  larghezza del riquadro. */
export function draw(cr, m) {
    cr.save();
    if (m.flip) {
        cr.translate(BOX_W, 0);
        cr.scale(-1, 1);
    }
    const mg = m.magic;
    let alpha = 1, scale = 1, spin = 0;
    if (mg) {
        const p = mg.p;
        if (mg.plain) {                                    // animazioni ridotte: solo dissolvenza
            alpha = mg.kind === 'appear' ? p : 1 - p;
        } else if (mg.kind === 'appear') {
            const q = phase(p, 0.3, 0.78);
            scale = q > 0 ? Math.max(0.02, backOut(q)) : 0;
            alpha = Math.min(1, q * 1.8);
        } else {
            const q = phase(p, 0, 0.58);
            scale = 1 - ease(q) * 0.98;
            spin = ease(q) * 28;
            alpha = q < 0.98 ? 1 - q * 0.6 : 0;
        }
    }
    if (alpha > 0.01 && scale > 0.01) {
        ellipse(cr, 65, 146, m.shadowRx * Math.min(1, scale), 3.8, ['rad', 65, 146, 0, 65, 146, m.shadowRx,
            [[0, '#000000', 0.38 * alpha], [0.7, '#000000', 0.18 * alpha], [1, '#000000', 0]]], {});
        cr.save();
        if (scale !== 1 || spin) {
            cr.translate(MAGIC_C[0], MAGIC_C[1]);
            cr.rotate(deg(spin));
            cr.scale(scale, scale);
            cr.translate(-MAGIC_C[0], -MAGIC_C[1]);
        }
        group(cr, m.tr.all, alpha, () => figure(cr, m));
        cr.restore();
    }
    if (mg && !mg.plain) {
        const p = mg.p;
        if (mg.kind === 'appear') {
            sparks(cr, phase(p, 0, 0.45), true, mg.t);
            flash(cr, phase(p, 0.22, 0.5));
            smokeRing(cr, phase(p, 0.35, 0.95));
            sparks(cr, phase(p, 0.55, 1), false, mg.t, 10);
        } else {
            sparks(cr, phase(p, 0, 0.55), true, mg.t);
            flash(cr, phase(p, 0.45, 0.72));
            smokeRing(cr, phase(p, 0.55, 1));
            sparks(cr, phase(p, 0.58, 1), false, mg.t, 12);
        }
    }
    cr.restore();
}

// ── il fumetto: un simbolo, mai parole ───────────────────────────────────
export const BUBBLE_W = 46;
export const BUBBLE_H = 40;
const INK = '#2b2440';

/** icon: 'ear' (ascolta), 'dots' (pensa), 'waves' (parla), 'hourglass'
 *  (si sveglia). left: il fumetto sta a sinistra della testa, quindi la
 *  punta va a destra. t: tempo in fotogrammi, per i puntini che pulsano.
 *  Colori fissi, scuro su chiaro: leggibile con ogni tema. */
export function drawBubble(cr, icon, left, t = 0) {
    const tip = left ? 'M34 29 L40 37 L28 29Z' : 'M12 29 L6 37 L18 29Z';
    rect(cr, 2, 2, 42, 28, 12, '#fbf8f1', {stroke: '#6f6758', w: 1.2});
    shape(cr, tip, '#fbf8f1', {stroke: '#6f6758', w: 1.2});
    shape(cr, left ? 'M29 28.4 L33 28.4' : 'M13 28.4 L17 28.4', null, {stroke: '#fbf8f1', w: 2});
    if (icon === 'ear') {
        line(cr, 'M20 23 c-2 0 -3.5 -1.6 -3.5 -3.8 c0 -5.6 3.2 -10 8.4 -10 c4.2 0 7.1 3 7.1 6.8 c0 3.2 -2.4 4.4 -3.5 6.4 c-1 1.9 -1.2 4.6 -4.5 4.6', INK, 2.1, LINE_CAP_ROUND);
        line(cr, 'M21.6 16 c0 -2.2 1.6 -3.4 3.3 -3.4 c1.8 0 3.1 1.2 3.1 3', INK, 1.7, LINE_CAP_ROUND);
    } else if (icon === 'dots') {
        for (let i = 0; i < 3; i++) {
            const a = 0.35 + 0.65 * Math.max(0, Math.sin(t * 0.12 - i * 0.9));
            circle(cr, 14 + i * 9, 16, 2.6, INK, {a});
        }
    } else if (icon === 'waves') {
        shape(cr, 'M11 13 h4 l5.5 -4.5 v15 l-5.5 -4.5 h-4z', INK);
        cr.setLineCap(LINE_CAP_ROUND);
        for (const r of [5.5, 10]) {
            cr.newPath();
            cr.arc(21, 16, r, -0.75, 0.75);
            src(cr, INK);
            cr.setLineWidth(2);
            cr.stroke();
        }
    } else {
        line(cr, 'M17 8 h12 M17 24 h12', INK, 2, LINE_CAP_ROUND);
        line(cr, 'M18.5 8 c0 5 4.5 5.8 4.5 8 c0 2.2 -4.5 3 -4.5 8 M27.5 8 c0 5 -4.5 5.8 -4.5 8 c0 2.2 4.5 3 4.5 8', INK, 1.6, LINE_CAP_ROUND);
        shape(cr, 'M19.6 23 c0.8 -2.6 2.6 -3.4 3.4 -4 c0.8 0.6 2.6 1.4 3.4 4z', INK);
    }
}
