// motion.js — RuscaPallas 1.99.3 — GPL-3.0-or-later
//
// Come si muove Pallasio: dallo stato (passeggia, ascolta, pensa, parla,
// legge) e dal tempo trascorso calcola il modello da disegnare con
// figure.js. Non sa dove si trova sullo schermo: lo spostamento lo decide
// pallasio.js, che qui dice solo se sta camminando o è in volo.
//
// Le pose delle braccia e del tomo non scattano: ogni gomito, ogni zampa e
// il libro scivolano verso la posa nuova in circa mezzo secondo.

// Il tempo interno si conta in «fotogrammi a 60 Hz», come nell'anteprima.
const FPS = 60;

export const MODES = ['walk', 'listen', 'think', 'speak', 'sit', 'wake'];
export const EMOTIONS = ['sorride', 'pensierosa', 'commossa', 'divertita', 'perplessa', 'seria'];

const SHOULDER_L = [37, 80], SHOULDER_R = [92, 80];

// Posa delle braccia (gomito e zampa, a sinistra e a destra) e del tomo.
export const POSES = {
    // tomo stretto al fianco sotto il braccio destro
    walk: {le: [30, 96], lh: [34, 110], re: [101, 96], rh: [86, 104], bx: 80, by: 101, br: -7, open: 0, finger: 0},
    // il tomo resta stretto, l'altra zampa alza l'indice
    speak: {le: [23, 90], lh: [27, 74], re: [101, 96], rh: [86, 104], bx: 80, by: 101, br: -7, open: 0, finger: 1},
    // braccia conserte, abbraccia il tomo
    listen: {le: [29, 97], lh: [74, 96], re: [103, 97], rh: [58, 99], bx: 66, by: 97, br: 0, open: 0, finger: 0},
    // seduto, il tomo aperto con tutte e due le zampe
    read: {le: [31, 103], lh: [44, 106], re: [101, 103], rh: [88, 106], bx: 66, by: 104, br: 0, open: 1, finger: 0},
};

const BROWS = {
    normal: 'M46 37 L62 44.5 M86 37 L70 44.5',
    skeptic: 'M46 38 L62 45 M86 33 L71 39',      // un sopracciglio alzato
    roll: 'M46 35 L62 41 M86 35 L70 41',
    serious: 'M46 38 L62 46.5 M86 38 L70 46.5',
    soft: 'M47 40 L62 42 M85 40 L70 42',          // commosso, per un attimo
};

const lerp = (a, b, k) => a + (b - a) * k;
const clone = p => JSON.parse(JSON.stringify(p));

function lids(h, slant) {
    const b = 41 + h, s = slant ? 2.5 : 0;
    return [`M49 41 H61 V${b + s} L49 ${b - s}Z`, `M71 41 H83 V${b - s} L71 ${b + s}Z`];
}

function armPath(s, e, h) {
    const mx = (e[0] + h[0]) / 2, my = (e[1] + h[1]) / 2;
    return `M${s[0]} ${s[1]} Q${e[0]} ${e[1]} ${mx} ${my} T${h[0]} ${h[1]}`;
}

function crease(e, h) {
    const cx = lerp(e[0], h[0], 0.78), cy = lerp(e[1], h[1], 0.78);
    const a = Math.atan2(h[1] - e[1], h[0] - e[0]);
    const nx = -Math.sin(a) * 4.4, ny = Math.cos(a) * 4.4;
    return `M${cx - nx} ${cy - ny} L${cx + nx} ${cy + ny}`;
}

export class Animator {
    constructor({reduceMotion = false, random = Math.random} = {}) {
        this.reduceMotion = reduceMotion;
        this.random = random;
        this.mode = 'walk';
        this.moving = false;        // cammina (lo dice chi lo sposta)
        this.airborne = false;      // sta saltando o cadendo
        this.dir = 1;               // 1 guarda a destra, -1 a sinistra
        this.t = 0;
        this.pose = clone(POSES.walk);
        this.mouthTarget = 0;
        this.mouth = 0;
        this.emotion = null;
        this.emotionLeft = 0;
        this.rollLeft = 0;          // occhi al cielo
        this.puffLeft = 0;          // sbuffo
        this.blinkIn = 3 * FPS;
        this.blink = 0;
    }

    setMode(mode) {
        if (MODES.includes(mode) && mode !== this.mode) {
            this.mode = mode;
            if (mode !== 'speak')
                this.mouthTarget = 0;
        }
    }

    /** Un'etichetta d'emozione del modello: dura qualche secondo. */
    setEmotion(emotion, seconds = 4) {
        if (!EMOTIONS.includes(emotion))
            return;
        this.emotion = emotion;
        this.emotionLeft = seconds * FPS;
    }

    /** Volume della voce, da 0 a 1: apre la bocca. */
    setMouth(level) {
        this.mouthTarget = Math.max(0, Math.min(1, level || 0));
    }

    /** Alza gli occhi al cielo e sbuffa. */
    roll() {
        this.rollLeft = 70;
        this.puffLeft = 60;
    }

    puff() {
        this.puffLeft = 50;
    }

    get seated() {
        return ['think', 'sit', 'wake'].includes(this.mode);
    }

    /** Avanza di dt secondi e restituisce il modello per figure.draw(). */
    step(dt) {
        const f = Math.min(dt, 0.25) * FPS;           // fotogrammi trascorsi
        this.t += f;
        const t = this.t, mode = this.mode, rm = this.reduceMotion;
        const seated = this.seated;
        const walking = this.moving && !this.airborne && !rm;
        if (this.rollLeft > 0) this.rollLeft = Math.max(0, this.rollLeft - f);
        if (this.puffLeft > 0) this.puffLeft = Math.max(0, this.puffLeft - f);
        if (this.emotionLeft > 0) {
            this.emotionLeft -= f;
            if (this.emotionLeft <= 0) this.emotion = null;
        }
        // battito di ciglia ogni 3-5 secondi
        this.blinkIn -= f;
        if (this.blinkIn <= 0) {
            this.blink = 6;
            this.blinkIn = (3 + this.random() * 2) * FPS;
        }
        if (this.blink > 0) this.blink = Math.max(0, this.blink - f);

        // pose che scivolano
        const P = POSES[seated ? 'read' : mode === 'speak' ? 'speak' : mode === 'listen' ? 'listen' : 'walk'];
        const k = rm ? 1 : 1 - Math.pow(1 - 0.12, f);
        const cur = this.pose;
        for (const n of ['le', 'lh', 're', 'rh']) {
            cur[n][0] = lerp(cur[n][0], P[n][0], k);
            cur[n][1] = lerp(cur[n][1], P[n][1], k);
        }
        for (const n of ['bx', 'by', 'br', 'open', 'finger'])
            cur[n] = lerp(cur[n], P[n], k);
        this.mouth = lerp(this.mouth, mode === 'speak' ? this.mouthTarget : 0, 1 - Math.pow(1 - 0.35, f));

        const ph = t * 0.13, sw = walking ? Math.sin(ph) : 0;
        const m = {tr: {}, d: {}, op: {}, flip: this.dir < 0};

        // gambe: seduto le allunga davanti; ascoltando batte il piede
        if (seated) {
            m.tr.legL = 'rotate(-72 53 118) translate(0 -3)';
            m.tr.legR = 'translate(-6 2) rotate(-90 77 118)';
        } else if (mode === 'listen' && !rm) {
            m.tr.legL = '';
            m.tr.legR = `rotate(${-Math.max(0, Math.sin(t * 0.45)) * 14} 77 140)`;
        } else {
            m.tr.legL = `rotate(${sw * 18} 53 118)`;
            m.tr.legR = `rotate(${-sw * 18} 77 118)`;
        }
        m.op.beans = seated ? 1 : 0;

        // braccia: il sinistro dondola camminando e fa «no» con l'indice parlando
        const wag = mode === 'speak' && !rm ? Math.sin(t * 0.28) * 5 : 0;
        const swH = walking ? sw * 6 : 0;
        const le = [cur.le[0] + (walking ? sw * 3 : 0), cur.le[1]];
        const lh = [cur.lh[0] + swH + wag * cur.finger, cur.lh[1] - Math.abs(swH) * 0.3];
        m.d.armL = armPath(SHOULDER_L, le, lh);
        m.d.armR = armPath(SHOULDER_R, cur.re, cur.rh);
        m.d.creaseL = crease(le, lh);
        m.d.creaseR = crease(cur.re, cur.rh);
        m.pawL = lh;
        m.pawR = cur.rh;
        m.d.finger = `M${lh[0] + 1} ${lh[1] - 4} l${wag * 0.15} -6`;
        m.op.finger = cur.finger > 0.5 ? 1 : 0;
        m.tr.book = `translate(${cur.bx} ${cur.by}) rotate(${cur.br})`;
        m.tr.bookOpen = `translate(${cur.bx} ${cur.by})`;
        m.op.open = cur.open;

        // corpo: passo pesante e un po' curvo
        const bob = walking ? Math.abs(sw) * 4 : rm ? 0 : Math.sin(t * 0.05);
        m.tr.all = seated ? 'translate(0 13)'
            : `translate(0 ${-bob + (walking ? 2 : 0)}) rotate(${walking ? sw * 3 : 0} 64 140)`;
        m.shadowRx = this.airborne ? 24 : 34;

        // coda: frusta quando parla, si agita quando pensa
        const tw = rm ? 0 : mode === 'speak' ? Math.sin(t * 0.4) * 10
            : mode === 'think' || mode === 'wake' ? Math.sin(t * 0.25) * 8 : Math.sin(t * 0.1) * 7;
        const ex = 10 + tw;
        m.d.tail = `M36 116 Q${12 + tw / 2} 112 ${ex} 86`;
        m.tailTip = [ex, 86];

        // orecchie appiattite; ascoltando, una scatta infastidita
        const twitch = mode === 'listen' && !rm && (t % 90) < 8 ? -14 : 0;
        m.tr.earL = 'rotate(-16 38 40)';
        m.tr.earR = `rotate(${16 + twitch} 94 40)`;
        m.tr.head = seated
            ? `translate(0 6) rotate(${mode === 'sit' ? 4 : -6 + (rm ? 0 : Math.sin(t * 0.04) * 3)} 66 72)`
            : mode === 'listen' ? 'rotate(-5 66 72) translate(0 1)'
                : walking ? 'translate(3 3) rotate(4 66 72)' : '';

        // occhi a mezz'asta, sopracciglia a V
        const emo = this.emotion, rolling = this.rollLeft > 0;
        let h = this.blink > 0 && !rolling ? 11.6 : rolling ? 2.5
            : mode === 'think' || mode === 'wake' ? 7.5 : mode === 'speak' ? 4.5 : 6;
        let brows = mode === 'listen' ? BROWS.skeptic : rolling ? BROWS.roll : BROWS.normal;
        let pup = rolling ? `translate(${Math.sin(this.rollLeft * 0.09) * 2} -3.2)`
            : seated ? 'translate(0 2.4)' : `translate(${mode === 'listen' ? 2 : 0} 1)`;
        m.op.tear = 0;
        if (emo && !rolling && this.blink <= 0) {
            if (emo === 'perplessa') brows = BROWS.skeptic;
            if (emo === 'seria') { brows = BROWS.serious; h = 6.5; }
            if (emo === 'divertita') h = 7.5;
            if (emo === 'pensierosa') pup = 'translate(-1.5 -2.6)';
            if (emo === 'commossa') { brows = BROWS.soft; h = 3; m.op.tear = 1; }
        }
        [m.d.lid1, m.d.lid2] = lids(h, mode === 'listen' || emo === 'perplessa');
        m.d.brows = brows;
        m.tr.pup = pup;

        // bocca: ringhia parlando, ghigno di traverso con certe emozioni
        const o = this.mouth * 6.4;
        const speaking = mode === 'speak';
        const tender = emo === 'commossa';
        if (speaking) {
            m.d.mouth = tender ? `M60 64 Q66 63 72 64 Q66 ${65 + o * 1.8} 60 64Z`
                : `M58 64 Q61 62 66 63 Q71 62 74 64 Q66 ${66 + o * 2.2} 58 64Z`;
            m.mouthFill = true;
        } else {
            m.d.mouth = emo === 'sorride' || emo === 'divertita' ? 'M59 65.5 Q66 64.5 73 62'
                : tender ? 'M60 65 Q66 64 72 65' : 'M59 66 Q66 62 73 66';
            m.mouthFill = false;
        }
        m.op.fangR = (speaking && !tender && o > 1.4) || (!speaking && emo === 'divertita') ? 1 : 0;
        m.op.snarl = speaking && !tender ? 1 : 0;

        // sbuffo
        m.op.puff = this.puffLeft > 0 ? Math.min(1, this.puffLeft / 20) : 0;
        m.tr.puff = `translate(${(60 - this.puffLeft) * 0.25} ${-(60 - this.puffLeft) * 0.15})`;
        return m;
    }
}
