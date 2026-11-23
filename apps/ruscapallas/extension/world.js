// world.js — RuscaPallas 1.99.3 — GPL-3.0-or-later
//
// Dove va Pallasio: cammina lungo il bordo basso dell'area di lavoro,
// ogni tanto salta sul bordo superiore di una finestra aperta, ci passeggia
// sopra, si sporge a guardare fuori, e poi torna giù. Se la finestra si
// chiude, si riduce a icona o si sposta da sotto i suoi piedi, cade.
//
// Tutto in pixel logici dello schermo. Il modulo riceve l'area di lavoro e
// le finestre come semplici rettangoli: non conosce GNOME Shell, e si prova
// anche con gjs da solo.

export const SPEED = 42;            // px/s, passo pesante
export const GRAVITY = 1370;        // px/s²
const RUN = 78;                     // px/s quando va verso una finestra
const PEEK_TIME = 2.6;              // s affacciato sul bordo

const clamp = (v, a, b) => Math.max(a, Math.min(b, v));

export class World {
    /** w, h: dimensioni del riquadro; feet: distanza dei piedi dall'alto. */
    constructor(w, h, feet, {random = Math.random} = {}) {
        this.w = w;
        this.h = h;
        this.feet = feet;
        this.random = random;
        this.x = null;              // bordo sinistro del riquadro
        this.feetY = null;          // dove poggiano i piedi
        this.vy = 0;
        this.dir = 1;
        this.platform = null;       // id della finestra sotto i piedi, o null
        this.target = null;         // {id, x}: finestra su cui vuole saltare
        this.aim = null;            // id della finestra su cui sta saltando
        this.nextJump = 12 + this.random() * 20;
        this.peek = 0;              // secondi ancora affacciato
        this.events = [];           // 'landed', 'peek', 'fell'
    }

    get airborne() {
        return this.vy !== 0;
    }

    get top() {
        return Math.round(this.feetY - this.feet);
    }

    /** Il punto da cui si guarda: centro dei piedi. */
    get center() {
        return this.x + this.w / 2;
    }

    _floor(area) {
        return area.y + area.height;
    }

    /** Finestre su cui può salire: abbastanza larghe, sotto la barra in
     *  alto con spazio per lui, e più in alto di dove si trova ora. */
    candidates(area, windows) {
        return windows.filter(win => win.width >= this.w * 1.2 &&
            win.y - this.h - 8 >= area.y &&
            win.y < this._floor(area) - 60 &&
            win.x + win.width > area.x + this.w / 2 &&
            win.x < area.x + area.width - this.w / 2);
    }

    /** Lo porta a terra in un punto (per esempio dopo un trascinamento). */
    place(x, area) {
        this.x = clamp(x, area.x, area.x + area.width - this.w);
        this.feetY = this._floor(area);
        this.vy = 0;
        this.platform = this.target = this.aim = null;
    }

    /** Lo si trascina col mouse: segue il puntatore. */
    drag(x, feetY) {
        this.x = x;
        this.feetY = feetY;
        this.vy = 0;
        this.platform = this.target = this.aim = null;
        this.peek = 0;
    }

    /** Lasciato andare: cade sulla finestra che ha sotto, o a terra. */
    drop(area, windows) {
        const c = this.center;
        const below = this.candidates(area, windows)
            .filter(win => c >= win.x && c <= win.x + win.width && win.y >= this.feetY - 2)
            .sort((a, b) => a.y - b.y);
        this.aim = below.length ? below[0].id : null;
        this.x = clamp(this.x, area.x, area.x + area.width - this.w);
        this.vy = 1;
    }

    _byId(windows, id) {
        return windows.find(win => win.id === id) || null;
    }

    _jumpTo(win) {
        const rise = this.feetY - win.y;
        this.vy = -Math.sqrt(2 * GRAVITY * (Math.max(0, rise) + 22));
        this.aim = win.id;
        this.platform = null;
        this.target = null;
    }

    /** Avanza di dt secondi. canWalk: falso se sta ascoltando, parlando,
     *  leggendo o se le animazioni sono ridotte (allora sta fermo, ma se
     *  il pavimento sparisce cade lo stesso). Restituisce true se cammina. */
    step(dt, area, windows, canWalk = true) {
        dt = Math.min(dt, 0.1);
        this.events = [];
        const floor = this._floor(area);
        if (this.x === null)
            this.place(area.x + area.width * (0.15 + this.random() * 0.5), area);

        // la finestra sotto i piedi c'è ancora?
        let win = this.platform !== null ? this._byId(windows, this.platform) : null;
        if (this.platform !== null) {
            const c = this.center;
            if (!win || c < win.x || c > win.x + win.width || win.y - this.h < area.y) {
                this.platform = null;
                this.vy = 1;                // comincia a cadere
                this.events.push('fell');
                win = null;
            } else {
                this.feetY = win.y;         // segue la finestra se si sposta
            }
        }

        // in volo
        if (this.vy !== 0) {
            const before = this.feetY;
            this.vy += GRAVITY * dt;
            this.feetY += this.vy * dt;
            this.x += this.dir * RUN * 0.5 * dt;
            this.x = clamp(this.x, area.x, area.x + area.width - this.w);
            if (this.vy > 0) {
                const aim = this.aim !== null ? this._byId(windows, this.aim) : null;
                const c = this.center;
                if (aim && before <= aim.y && this.feetY >= aim.y && c >= aim.x && c <= aim.x + aim.width) {
                    this.feetY = aim.y;
                    this.vy = 0;
                    this.platform = aim.id;
                    this.aim = null;
                    this.events.push('landed');
                } else if (this.feetY >= floor) {
                    this.feetY = floor;
                    this.vy = 0;
                    this.aim = null;
                    this.events.push('landed');
                }
            }
            return false;
        }

        if (this.platform === null)
            this.feetY = floor;
        if (this.peek > 0) {
            this.peek -= dt;
            return false;
        }
        if (!canWalk)
            return false;

        // vuole salire su una finestra: ci va sotto, poi salta
        if (this.target) {
            const t = this._byId(this.candidates(area, windows), this.target.id);
            if (!t) {
                this.target = null;
            } else {
                const dx = this.target.x - this.x;
                this.dir = dx >= 0 ? 1 : -1;
                if (Math.abs(dx) < 4) {
                    this._jumpTo(t);
                    return false;
                }
                this.x += this.dir * Math.min(Math.abs(dx), RUN * dt);
                return true;
            }
        }

        // passeggia
        let lo, hi;
        if (win) {
            lo = Math.max(area.x, win.x - this.w * 0.3);
            hi = Math.min(area.x + area.width - this.w, win.x + win.width - this.w * 0.7);
        } else {
            lo = area.x;
            hi = area.x + area.width - this.w;
        }
        this.x += this.dir * SPEED * dt;
        if (this.x <= lo || this.x >= hi) {
            this.x = clamp(this.x, lo, hi);
            if (win) {
                const r = this.random();
                if (r < 0.45) {                      // si affaccia e sbuffa
                    this.peek = PEEK_TIME;
                    this.events.push('peek');
                    this.dir = -this.dir;
                } else if (r < 0.8) {                // scende
                    this.platform = null;
                    this.vy = -260;
                    this.x += this.dir * 6;
                } else {
                    this.dir = -this.dir;
                }
            } else {
                this.dir = -this.dir;
            }
        }

        // ogni tanto sceglie una finestra
        if (!win) {
            this.nextJump -= dt;
            if (this.nextJump <= 0) {
                this.nextJump = 25 + this.random() * 45;
                const c = this.candidates(area, windows);
                if (c.length) {
                    const t = c[Math.floor(this.random() * c.length)];
                    const x = clamp(t.x + t.width * (0.2 + this.random() * 0.6) - this.w / 2,
                        area.x, area.x + area.width - this.w);
                    this.target = {id: t.id, x};
                }
            }
        }
        return true;
    }
}
