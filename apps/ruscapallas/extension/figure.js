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

// ── le parti ─────────────────────────────────────────────────────────────
// Luce dall'alto a sinistra: ogni volume ha un gradiente dal chiaro allo
// scuro, il contorno esterno è più spesso di quelli interni, e il pelo ha
// ciuffi e trama disegnati a tratti sottili.
const FUR = '#b9ad96', FUR_L = '#d8cfbc', FUR_D = '#8f836e', FUR_DD = '#6f6453';
const STRIPE = '#3b3229', CREAM = '#efe6d6';
const JACKET = '#e9dab6', JACKET_L = '#f6eed8', JACKET_D = '#c7b58a';
const lin = (x0, y0, x1, y1, ...stops) => ['lin', x0, y0, x1, y1, stops];
const rad = (cx, cy, r0, r1, ...stops) => ['rad', cx, cy, r0, cx, cy, r1, stops];
const W_OUT = 1.5, W_IN = 0.9;           // contorno esterno e interno

function furStrokes(cr, list, color, w, a = 1) {
    for (const d of list)
        line(cr, d, color, w, LINE_CAP_ROUND, a);
}

function tail(cr, m) {
    line(cr, m.d.tail, OUTLINE, 15.8, LINE_CAP_ROUND);
    line(cr, m.d.tail, FUR, 13, LINE_CAP_ROUND);
    cr.setDash([4, 7], -6);
    line(cr, m.d.tail, STRIPE, 13, LINE_CAP_BUTT);
    cr.setDash([], 0);
    // riflesso lungo il dorso della coda
    cr.save();
    cr.translate(1.6, -1.4);
    line(cr, m.d.tail, FUR_L, 3, LINE_CAP_ROUND, 0.55);
    cr.restore();
    circle(cr, m.tailTip[0], m.tailTip[1], 6.5, rad(m.tailTip[0] - 2, m.tailTip[1] - 2, 0, 7, [0, '#4a4036'], [1, '#221c16']));
}

function leg(cr, x, dark) {
    const base = dark ? FUR_D : FUR;
    rect(cr, x, 116, 14, 25, 7, lin(x, 0, x + 14, 0, [0, dark ? FUR : FUR_L], [1, base]),
        {stroke: OUTLINE, w: W_OUT});
    ellipse(cr, x + 8, 141, 10.5, 5, lin(0, 136, 0, 146, [0, dark ? FUR : FUR_L], [1, base]),
        {stroke: OUTLINE, w: W_OUT});
    line(cr, `M${x + 4} 138.6 v3.2 M${x + 8} 138.3 v3.8 M${x + 12} 138.6 v3.2`, OUTLINE, W_IN, LINE_CAP_ROUND);
    furStrokes(cr, [`M${x + 3} 122 l2 2`, `M${x + 3} 128 l2 2`], FUR_DD, 0.7, 0.7);
}

function beans(cr) {
    ellipse(cr, 78, 141, 5, 3.6, rad(77, 140, 0, 5, [0, '#e0a7a2'], [1, '#bf7f7a']));
    for (const [x, y] of [[72, 137], [76, 135.5], [80, 135.5], [84, 137]])
        circle(cr, x, y, 1.8, '#c98a86');
}

function body(cr) {
    // pelo del corpo (si vede ai lati e sotto la giacca)
    shape(cr, 'M63 66 C 30 66 22 92 26 110 C 29 126 44 134 63 134 C 84 134 99 126 101 110 C 104 92 96 66 63 66 Z',
        rad(52, 88, 6, 62, [0, FUR_L], [0.6, FUR], [1, FUR_D]), {stroke: OUTLINE, w: W_OUT});
    // giacca, con la luce da sinistra
    shape(cr, 'M63 68 C 32 68 25 92 28 110 C 30 122 40 128 50 129 L66 126 L82 129 C 92 128 99 122 100 110 C 103 92 95 68 63 68 Z',
        lin(30, 72, 100, 124, [0, JACKET_L], [0.45, JACKET], [1, JACKET_D]), {stroke: OUTLINE, w: W_OUT});
    // ombra del pancione e pieghe della stoffa
    shape(cr, 'M31 108 C 33 121 41 127 50 128 L58 127 C 46 122 38 113 35 97 Z', JACKET_D, {a: 0.55});
    shape(cr, 'M97 100 C 99 112 94 122 84 127 L82 128 C 90 120 93 111 92 100 Z', JACKET_D, {a: 0.6});
    line(cr, 'M36 84 q3 8 1 15 M93 85 q-2 7 0 13 M44 120 q6 3 12 3', JACKET_D, W_IN, LINE_CAP_ROUND, 0.9);
    // tasca con la patta
    shape(cr, 'M79 109.5 L93 107.5 L93.6 111.6 L79.6 113.6Z', lin(0, 108, 0, 114, [0, JACKET], [1, JACKET_D]),
        {stroke: OUTLINE, w: W_IN});
    // pancia che spunta sotto il bottone
    shape(cr, 'M60 112 L66 107.5 L72 112 L71 127.5 L66 126 L61 127.5Z', lin(60, 110, 72, 128, [0, CREAM], [1, '#d9cdb8']),
        {stroke: OUTLINE, w: W_IN});
    furStrokes(cr, ['M63 116 q1.4 1.6 0 3.2', 'M69 116 q1.4 1.6 0 3.2', 'M66 121 q1.4 1.6 0 3.2'], '#c3b6a0', 0.8);
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
    // la giacca tira sul bottone
    line(cr, 'M57.5 104 l4.6 2.2 M74.5 104 l-4.6 2.2 M56.5 109.5 l4.2 -1.2 M75.5 109.5 l-4.2 -1.2', '#b19f72', 0.8, LINE_CAP_ROUND);
    circle(cr, 66, 106.6, 2.1, rad(65.3, 105.9, 0, 2.2, [0, '#a07a52'], [1, '#5f4127']), {stroke: OUTLINE, w: W_IN});
    circle(cr, 65.4, 106, 0.55, '#e7cfa9');
}

// il tomo chiuso: si vede la copertina, in pelle con fregi dorati
function bookClosed(cr) {
    rect(cr, -13, -16.5, 26, 33, 1.6, lin(-13, -16, 13, 16, [0, '#8a4b29'], [0.6, '#6b371b'], [1, '#4a2410']),
        {stroke: OUTLINE, w: W_OUT});
    rect(cr, -13, -16.5, 5, 33, 0, lin(-13, 0, -8, 0, [0, '#3f1f0d'], [1, '#5a2e16']));
    line(cr, 'M-12.6 -11 h4.2 M-12.6 -6 h4.2 M-12.6 6 h4.2 M-12.6 11 h4.2', '#d1ac58', 0.9);
    rect(cr, 13, -15.2, 2.2, 30.4, 0, lin(13, 0, 15, 0, [0, '#f3e8cb'], [1, '#d2c4a0']), {stroke: OUTLINE, w: W_IN});
    rect(cr, -6, -13.5, 17, 27, 0, null, {stroke: '#c9a24a', w: 0.8});
    rect(cr, -4.5, -12, 14, 24, 0, null, {stroke: '#c9a24a', w: 0.45});
    rect(cr, -2, -6.5, 9, 6, 0.8, lin(0, -6.5, 0, -0.5, [0, '#e2c06a'], [1, '#a9832f']), {stroke: '#7c5c1c', w: 0.5});
    line(cr, 'M-0.5 -4.6 h6 M-0.5 -2.6 h4', '#5a3e12', 0.6);
    for (const [x, y] of [[10.6, -14], [10.6, 14]])          // cantonali di ottone
        shape(cr, `M${x - 2.4} ${y} L${x + 2.4} ${y} L${x + 2.4} ${y + (y < 0 ? 2.4 : -2.4)}Z`, '#c9a24a');
    line(cr, 'M-7 -15.8 L11 -15.8', '#a76a42', 0.7, LINE_CAP_BUTT, 0.7);   // luce sul bordo
}

// il tomo aperto visto da chi guarda: le due copertine a libro e il dorso,
// sopra il taglio delle pagine; le pagine scritte le vede solo Pallasio
function bookOpen(cr) {
    shape(cr, 'M-24 -10.5 L0 -14.5 L24 -10.5 L22 -7.5 L0 -10.8 L-22 -7.5Z', lin(0, -14, 0, -8, [0, '#fbf3dc'], [1, '#d9caa3']),
        {stroke: OUTLINE, w: W_IN});
    line(cr, 'M-20 -9.6 L0 -12.6 L20 -9.6', '#c8b88f', 0.5);
    shape(cr, 'M-25 -9 L-2.2 -11.2 L-2.2 17 L-25 14.6Z', lin(-25, -9, -2, 17, [0, '#8a4b29'], [1, '#55290f']),
        {stroke: OUTLINE, w: W_OUT});
    shape(cr, 'M25 -9 L2.2 -11.2 L2.2 17 L25 14.6Z', lin(25, -9, 2, 17, [0, '#7a3f20'], [1, '#4a2410']),
        {stroke: OUTLINE, w: W_OUT});
    shape(cr, 'M-2.6 -11.6 L2.6 -11.6 L2.6 17.6 L-2.6 17.6Z', lin(-2.6, 0, 2.6, 0, [0, '#3f1f0d'], [0.5, '#6a3519'], [1, '#3f1f0d']),
        {stroke: OUTLINE, w: W_IN});
    line(cr, 'M-2.4 -6 h4.8 M-2.4 -1 h4.8 M-2.4 9 h4.8 M-2.4 14 h4.8', '#d1ac58', 0.8);
    shape(cr, 'M-22.5 -6.8 L-5 -8.6 L-5 13.8 L-22.5 12Z', null, {stroke: '#c9a24a', w: 0.7});
    shape(cr, 'M22.5 -6.8 L5 -8.6 L5 13.8 L22.5 12Z', null, {stroke: '#c9a24a', w: 0.7});
    shape(cr, 'M9 -1 L18.5 -1.9 L18.5 4.4 L9 5.3Z', lin(0, -2, 0, 5, [0, '#e2c06a'], [1, '#a9832f']), {stroke: '#7c5c1c', w: 0.5});
    line(cr, 'M10.5 1 l6 -0.6 M10.5 3 l4 -0.4', '#5a3e12', 0.55);
}

function arm(cr, d, crease, light, shade, paw, pawColor) {
    line(cr, d, OUTLINE, 12.8, LINE_CAP_ROUND);
    line(cr, d, light, 10, LINE_CAP_ROUND);
    cr.save();
    cr.translate(1.2, 1.4);                  // ombra lungo la manica
    line(cr, d, shade, 2.6, LINE_CAP_ROUND, 0.35);
    cr.restore();
    line(cr, crease, shade, 1.6);            // polsino
    circle(cr, paw[0], paw[1], 5.7, rad(paw[0] - 1.6, paw[1] - 1.8, 0.5, 6.4, [0, FUR_L], [0.7, pawColor], [1, FUR_D]),
        {stroke: OUTLINE, w: W_OUT});
    line(cr, `M${paw[0] - 2.6} ${paw[1] + 1.4} v2.2 M${paw[0]} ${paw[1] + 2.2} v2.4 M${paw[0] + 2.6} ${paw[1] + 1.4} v2.2`,
        OUTLINE, 0.7, LINE_CAP_ROUND);
}

const HEAD = 'M66 22 C 44 22 32 34 32 48 L26 52 L32 55 L27 61 L34 62 L31 68 L40 67 L39 73 L48 70 L50 77 L57 72 L62 79 L66 73 L70 79 L75 72 L82 77 L84 70 L93 73 L92 67 L101 68 L98 62 L105 61 L100 55 L106 52 L100 48 C 100 34 88 22 66 22 Z';
// trama del pelo: ciuffi sulla gorgiera, sulla fronte e sulle guance
const FUR_TUFTS = ['M29 53 l4 1', 'M30 60 l5 0', 'M34 66 l5 -1', 'M42 71 l4 -2', 'M51 75 l3 -3', 'M60 77 l2 -4',
    'M103 53 l-4 1', 'M102 60 l-5 0', 'M98 66 l-5 -1', 'M90 71 l-4 -2', 'M81 75 l-3 -3', 'M72 77 l-2 -4'];
const FUR_FINE = ['M44 32 q2 -2 4 -2', 'M84 32 q-2 -2 -4 -2', 'M40 40 q1 -3 3 -4', 'M92 40 q-1 -3 -3 -4',
    'M58 24 q2 -1 4 -1', 'M70 23 q2 0 4 1', 'M38 50 l-3 2', 'M94 50 l3 2'];

function head(cr, m) {
    group(cr, m.tr.earL, 1, () => {
        shape(cr, 'M30 42 Q28 32 42 32 Q40 40 30 42Z', lin(28, 32, 42, 42, [0, FUR], [1, FUR_D]), {stroke: OUTLINE, w: W_OUT});
        shape(cr, 'M33 39 Q32 34 39 34 Q37 38 33 39Z', lin(32, 34, 39, 39, [0, '#e4c4b8'], [1, '#c49c91']));
        line(cr, 'M33 37 l3 -1', '#f3ece0', 0.6);
    });
    group(cr, m.tr.earR, 1, () => {
        shape(cr, 'M102 42 Q104 32 90 32 Q92 40 102 42Z', lin(104, 32, 90, 42, [0, FUR_D], [1, FUR_DD]), {stroke: OUTLINE, w: W_OUT});
        shape(cr, 'M99 39 Q100 34 93 34 Q95 38 99 39Z', lin(100, 34, 93, 39, [0, '#d9b6aa'], [1, '#b38c82']));
        line(cr, 'M99 37 l-3 -1', '#f3ece0', 0.6);
    });
    // testa larga con la gorgiera a punte
    shape(cr, HEAD, rad(58, 36, 4, 48, [0, '#ddd4c2'], [0.55, '#c5baa5'], [1, '#9c907b']), {stroke: OUTLINE, w: W_OUT});
    shape(cr, 'M38 60 L34 66 L42 66 L44 72 L52 68 L58 76 L66 70 L74 76 L80 68 L88 72 L90 66 L98 66 L94 60 Q80 72 66 70 Q52 72 38 60Z',
        lin(0, 60, 0, 76, [0, '#f2ebdd'], [1, '#d9cfbd']));
    furStrokes(cr, FUR_TUFTS, '#f4eee2', 0.8, 0.85);
    furStrokes(cr, FUR_FINE, FUR_D, 0.7, 0.8);
    for (const [x, y, r] of [[56, 29, 1.6], [62, 26.5, 1.8], [70, 26.5, 1.8], [76, 29, 1.6], [59, 33, 1.3],
        [66, 31, 1.5], [73, 33, 1.3], [52, 33, 1.1], [80, 33, 1.1], [48, 30.5, 0.8], [84, 30.5, 0.8]])
        ellipse(cr, x, y, r, r * 0.85, '#3d342b');
    line(cr, 'M62 36 q4 3 8 0 M63 39 q3 2 6 0', '#7d725f', 0.9, LINE_CAP_ROUND);
    // le bande scure delle guance, con i bordi sfrangiati
    shape(cr, 'M34 50 q8 8 16 8 l-1 3 q-9 -1 -16 -7Z M33 57 q8 8 17 8 l-1 3 q-10 -1 -17 -7Z M98 50 q-8 8 -16 8 l1 3 q9 -1 16 -7Z M99 57 q-8 8 -17 8 l1 3 q10 -1 17 -7Z',
        STRIPE);
    furStrokes(cr, ['M37 55 l-1 2', 'M42 59 l-1 2', 'M37 62 l-1 2', 'M95 55 l1 2', 'M90 59 l1 2', 'M95 62 l1 2'], STRIPE, 0.8);
    // muso
    shape(cr, 'M66 54 C 56 54 52 60 53 64 C 54 69 60 71 66 71 C 72 71 78 69 79 64 C 80 60 76 54 66 54 Z',
        rad(63, 58, 1, 15, [0, '#ffffff'], [0.7, '#f3ede2'], [1, '#dcd2c1']), {stroke: OUTLINE, w: W_IN});
    for (const [x, y] of [[58, 61], [60, 63.5], [57.5, 64.5], [74, 61], [72, 63.5], [74.5, 64.5]])
        circle(cr, x, y, 0.45, '#8f836e');       // attaccature dei baffi
    // occhi
    for (const cx of [55, 77]) {
        circle(cr, cx, 47, 5.1, '#fbf6e6', {stroke: OUTLINE, w: W_IN});
        circle(cr, cx, 47, 4.4, rad(cx - 0.8, 46, 0.5, 4.6, [0, '#f6dd6e'], [0.65, '#e0b53a'], [1, '#a9791c']));
    }
    group(cr, m.tr.pup, 1, () => {
        for (const cx of [55, 77]) {
            ellipse(cr, cx, 47, 1.25, 3.1, '#120f0b');
            circle(cr, cx + 1.4, 45.4, 0.8, '#ffffff');
            circle(cr, cx - 1.2, 48.6, 0.35, '#ffffff', {a: 0.8});
        }
    });
    shape(cr, m.d.lid1, lin(49, 41, 49, 48, [0, '#cdc3ae'], [1, '#b2a68f']), {stroke: OUTLINE, w: W_IN});
    shape(cr, m.d.lid2, lin(71, 41, 71, 48, [0, '#c4b9a3'], [1, '#a99d86']), {stroke: OUTLINE, w: W_IN});
    line(cr, 'M51 52.3 q4 1.4 8 0 M73 52.3 q4 1.4 8 0', '#8f836e', 0.6, LINE_CAP_ROUND);
    line(cr, m.d.brows, '#241d16', 2.9, LINE_CAP_ROUND);
    // occhialini tondi: lenti con il riflesso, montatura con la luce
    for (const cx of [55, 77]) {
        circle(cr, cx, 47.5, 7.4, rad(cx - 2.5, 45, 0, 8, [0, 'rgba(255,255,255,0.32)'], [0.6, 'rgba(225,238,246,0.12)'], [1, 'rgba(200,220,235,0.22)']),
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
    // naso, bocca, zanne, baffi
    shape(cr, 'M62.5 56.5 q3.5 -1.5 7 0 l-3.5 4z', lin(62, 55, 66, 61, [0, '#dba19c'], [1, '#b0716d']), {stroke: OUTLINE, w: W_IN});
    circle(cr, 64.6, 56.7, 0.6, '#f6d7d3');
    if (m.op.snarl > 0.01)
        line(cr, 'M58 58 q2 -2 4 -1 M70 57 q2 -1 4 1 M60 59.6 q1.5 -1 3 -0.6', '#7d725f', 0.9, LINE_CAP_ROUND, m.op.snarl);
    line(cr, 'M66 60.5 v2.5', OUTLINE, W_IN);
    shape(cr, m.d.mouth, m.mouthFill ? lin(0, 62, 0, 72, [0, '#6e3232'], [1, '#3f1a1a']) : null, {stroke: OUTLINE, w: 1.1});
    shape(cr, 'M61.6 64.6 l1.3 3.4 l1.2 -3', '#ffffff', {stroke: OUTLINE, w: 0.5});
    if (m.op.fangR > 0.01)
        shape(cr, 'M68 64.4 l1.2 3 l1.3 -3.4', '#ffffff', {stroke: OUTLINE, w: 0.5, a: m.op.fangR});
    line(cr, 'M78 61 l20 -3 M78 64 l21 1 M78 67 l18 4 M54 61 l-20 -3 M54 64 l-21 1 M54 67 l-18 4', '#f7f3ea', 0.6, LINE_CAP_ROUND, 0.9);
    if (m.op.tear > 0.01)          // commosso: una lacrima che non ammetterà mai
        ellipse(cr, 49.5, 53, 1.1, 1.6, rad(49.2, 52.5, 0, 1.6, [0, '#ffffff'], [1, '#9fcbe6']), {a: m.op.tear});
}

function puff(cr) {
    circle(cr, 100, 62, 3, rad(99, 61, 0, 3, [0, '#f4f1ea'], [1, '#c9c4b8']));
    circle(cr, 106, 59, 2.2, rad(105.4, 58.4, 0, 2.2, [0, '#f4f1ea'], [1, '#c9c4b8']));
    circle(cr, 111, 57, 1.5, '#d8d4cc');
}

/** Disegna Pallasio. Il contesto è già scalato: 1 unità = 1/130 della
 *  larghezza del riquadro. */
export function draw(cr, m) {
    cr.save();
    if (m.flip) {
        cr.translate(BOX_W, 0);
        cr.scale(-1, 1);
    }
    ellipse(cr, 65, 146, m.shadowRx, 3.8, ['rad', 65, 146, 0, 65, 146, m.shadowRx,
        [[0, '#000000', 0.38], [0.7, '#000000', 0.18], [1, '#000000', 0]]], {});
    group(cr, m.tr.all, 1, () => {
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
    });
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
