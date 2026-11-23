// pallasio.js — RuscaPallas 1.99.3 — GPL-3.0-or-later
//
// Pallasio dentro GNOME Shell: un attore disegnato con Cairo sopra le
// finestre (top chrome), che cammina, salta sulle finestre e parla.
//
//   clic sinistro    gli si parla (se sta parlando o ascoltando, tace)
//   trascinamento    lo si sposta; lasciato andare, cade
//   clic destro      menu: «Zitto», «Torna nello sgabuzzino»
//
// La conversazione la fa il servizio org.ruscalinux.RuscaPallas.Dialog (Python,
// avviato da D-Bus al primo clic): ascolta con Vosk, pensa con
// ruscallama-engine, parla con Piper. Qui arrivano solo lo stato, le
// emozioni e il volume della voce, per muovere la bocca.
//
// Sul bus di sessione l'estensione offre org.ruscalinux.RuscaPallas.Shell
// (Show, Hide): lo usa il comando `ruscapallas` per richiamarlo.

import Clutter from 'gi://Clutter';
import Gio from 'gi://Gio';
import GLib from 'gi://GLib';
import Meta from 'gi://Meta';
import St from 'gi://St';

import * as Main from 'resource:///org/gnome/shell/ui/main.js';
import * as PopupMenu from 'resource:///org/gnome/shell/ui/popupMenu.js';

import {draw, drawBubble, BOX_W, BOX_H, FEET_Y, BUBBLE_W, BUBBLE_H} from './figure.js';
import {Animator} from './motion.js';
import {World} from './world.js';

// Impostazioni scritte dalla finestra di RuscaPallas: si rileggono quando
// cambiano, senza riavviare niente.
const SETTINGS_FILE = GLib.build_filenamev([GLib.get_user_config_dir(), 'ruscapallas', 'settings.json']);
const SIZES = {small: 1.0, normal: 1.3, large: 1.6};      // unità del disegno → pixel logici
const JUMPS = {never: null, sometimes: [25, 70], often: [8, 22]};
const DRAG_THRESHOLD = 8;             // px prima che un clic diventi un trascinamento
const ANSWER_TIMEOUT = 20;            // s: dopo un clic il servizio deve farsi vivo

const SERVICE_NAME = 'org.ruscalinux.RuscaPallas.Dialog';
const SERVICE_PATH = '/org/ruscalinux/RuscaPallas/Dialog';
const SERVICE_XML = `<node>
  <interface name="org.ruscalinux.RuscaPallas.Dialog">
    <method name="Talk"/>
    <method name="Stop"/>
    <method name="Quit"/>
    <method name="GetState"><arg type="s" direction="out"/></method>
    <signal name="State"><arg type="s"/></signal>
    <signal name="Emotion"><arg type="s"/></signal>
    <signal name="Mouth"><arg type="d"/></signal>
    <signal name="Error"><arg type="s"/><arg type="s"/></signal>
  </interface>
</node>`;
const ServiceProxy = Gio.DBusProxy.makeProxyWrapper(SERVICE_XML);

const SHELL_NAME = 'org.ruscalinux.RuscaPallas.Shell';
const SHELL_PATH = '/org/ruscalinux/RuscaPallas/Shell';
const SHELL_XML = `<node>
  <interface name="org.ruscalinux.RuscaPallas.Shell">
    <method name="Show"/>
    <method name="Hide"/>
    <property name="Visible" type="b" access="read"/>
  </interface>
</node>`;

// stato del servizio → posa e simbolo nel fumetto (mai parole)
const STATES = {
    waking: {mode: 'wake', icon: 'hourglass'},
    listening: {mode: 'listen', icon: 'ear'},
    thinking: {mode: 'think', icon: 'dots'},
    speaking: {mode: 'speak', icon: 'waves'},
};
const DIALOG = ['wake', 'listen', 'think', 'speak'];

function loadStrings(dir) {
    const read = code => {
        try {
            const [, bytes] = GLib.file_get_contents(GLib.build_filenamev([dir, 'lang', `${code}.json`]));
            return JSON.parse(new TextDecoder().decode(bytes));
        } catch {
            return null;
        }
    };
    const en = read('en') || {};
    for (const name of GLib.get_language_names()) {
        const code = name.split(/[._@]/)[0];
        const found = read(name.split(/[.@]/)[0]) || read(code);
        if (found)
            return Object.assign({}, en, found);
    }
    return en;
}

export class Pallasio {
    constructor(extension) {
        this._strings = loadStrings(extension.path);
        // la preferenza dell'utente (Accessibilità → Animazioni), non quella di
        // St, che le spegne anche con il disegno via software (macchine virtuali)
        this._settings = new Gio.Settings({schema_id: 'org.gnome.desktop.interface'});
        this._anim = new Animator({reduceMotion: !this._settings.get_boolean('enable-animations')});
        this._scale = SIZES.normal;
        this._idleReading = true;
        this._world = new World(this._w, this._h, FEET_Y * this._scale);
        this._model = this._anim.step(0);
        this._visible = true;
        this._busy = false;           // sta conversando (non passeggia)
        this._restUntil = 0;          // seduto a leggere per conto suo fino a…
        this._nextRest = this._now() + 40 + Math.random() * 60;
        this._press = null;
        this._grab = null;
        this._last = 0;

        // ── attori ──
        this.actor = new St.DrawingArea({
            reactive: true, track_hover: true, width: this._w, height: this._h,
            name: 'ruscapallas',
            accessible_name: 'Pallasio',
        });
        this.actor.connect('repaint', area => this._repaint(area));
        this.actor.connect('button-press-event', (a, ev) => this._onPress(ev));
        this.actor.connect('motion-event', (a, ev) => this._onMotion(ev));
        this.actor.connect('button-release-event', (a, ev) => this._onRelease(ev));

        // Il fumetto: un simbolo disegnato (orecchio, puntini, onde, clessidra),
        // mai parole. Non si nasconde con hide(): la visibilità degli attori in
        // top chrome la governa GNOME (schermo intero). Si usa l'opacità.
        this._icon = 'ear';
        this.bubble = new St.DrawingArea({width: BUBBLE_W, height: BUBBLE_H, opacity: 0});
        this.bubble.connect('repaint', area => {
            const cr = area.get_context();
            const [w, h] = area.get_surface_size();
            cr.scale(w / BUBBLE_W, h / BUBBLE_H);
            drawBubble(cr, this._icon, this._anim.dir < 0, this._anim.t);
            cr.$dispose();
        });
        this._bubbleOn = false;
        this._inChrome = false;

        this._menu = new PopupMenu.PopupMenu(this.actor, 0.5, St.Side.BOTTOM);
        this._menu.addAction(this._('menu_stop'), () => this._call('Stop'));
        this._menu.addAction(this._('menu_settings'), () => this._openSettings());
        this._menu.addAction(this._('menu_hide'), () => this.Hide());
        Main.uiGroup.add_child(this._menu.actor);
        this._menu.actor.hide();
        this._menuManager = new PopupMenu.PopupMenuManager(this.actor);
        this._menuManager.addMenu(this._menu);

        this._animId = this._settings.connect('changed::enable-animations', () => {
            this._anim.reduceMotion = !this._settings.get_boolean('enable-animations');
        });

        // ── il servizio di dialogo ──
        this._proxy = null;
        this._signals = [];
        new ServiceProxy(Gio.DBus.session, SERVICE_NAME, SERVICE_PATH, (proxy, error) => {
            if (error) {
                console.warn(`ruscapallas: ${error.message}`);
                return;
            }
            if (!this.actor)              // disattivata nel frattempo
                return;
            this._proxy = proxy;
            this._signals.push(
                proxy.connectSignal('State', (p, s, [state]) => this._onState(state)),
                proxy.connectSignal('Emotion', (p, s, [emotion]) => this._anim.setEmotion(emotion)),
                proxy.connectSignal('Mouth', (p, s, [level]) => this._anim.setMouth(level)),
                proxy.connectSignal('Error', (p, s, [key, detail]) => this._onError(key, detail)));
            this._ownerId = proxy.connect('notify::g-name-owner', () => {
                if (!proxy.g_name_owner)  // il servizio è uscito
                    this._onState('idle');
            });
        }, null, Gio.DBusProxyFlags.DO_NOT_AUTO_START_AT_CONSTRUCTION);

        // ── comando ruscapallas: Show / Hide ──
        this._dbus = Gio.DBusExportedObject.wrapJSObject(SHELL_XML, this);
        this._dbus.export(Gio.DBus.session, SHELL_PATH);
        this._nameId = Gio.bus_own_name(Gio.BusType.SESSION, SHELL_NAME,
            Gio.BusNameOwnerFlags.NONE, null, null, null);

        // ── impostazioni della finestra di RuscaPallas ──
        this._loadOptions();
        try {
            // la cartella deve esistere, o il controllo non vede il file nascere
            GLib.mkdir_with_parents(GLib.path_get_dirname(SETTINGS_FILE), 0o700);
            this._optMonitor = Gio.File.new_for_path(SETTINGS_FILE).monitor_file(Gio.FileMonitorFlags.NONE, null);
            this._optMonitor.connect('changed', () => this._loadOptions());
        } catch (e) {
            console.warn(`ruscapallas: ${e.message}`);
        }

        // ── animazione, legata al ritmo dei fotogrammi dello schermo ──
        this._timeline = new Clutter.Timeline({actor: this.actor, duration: 1000, repeat_count: -1});
        this._timeline.connect('new-frame', () => this._tick());

        // nella panoramica delle attività non c'è
        this._overviewIds = [
            Main.overview.connect('showing', () => this._updateShown()),
            Main.overview.connect('hidden', () => this._updateShown()),
        ];
        this._updateShown();
        this._anim.startMagic('appear');      // compare dal nulla
    }

    /** In scena solo se richiamato e fuori dalla panoramica. Gli attori si
     *  tolgono dal top chrome invece di nasconderli: GNOME ne governa la
     *  visibilità per lo schermo intero, e li rimostrerebbe. */
    _updateShown() {
        const shown = this._visible && !Main.overview.visible;
        if (shown === this._inChrome)
            return;
        this._inChrome = shown;
        if (shown) {
            Main.layoutManager.addTopChrome(this.actor, {affectsInputRegion: true, trackFullscreen: true});
            Main.layoutManager.addTopChrome(this.bubble, {affectsInputRegion: false, trackFullscreen: true});
            this._last = 0;
            this._timeline.start();
        } else {
            this._timeline.stop();
            this._menu.close();
            Main.layoutManager.removeChrome(this.bubble);
            Main.layoutManager.removeChrome(this.actor);
        }
    }

    _showBubble(on) {
        this._bubbleOn = on;
        this.bubble.opacity = on ? 255 : 0;
    }

    get _w() {
        return Math.ceil(BOX_W * this._scale);
    }

    get _h() {
        return Math.ceil(BOX_H * this._scale);
    }

    /** Dimensione, salti, letture per conto suo. Un file mancante o rotto
     *  vale come le scelte predefinite. */
    _loadOptions() {
        let opt = {};
        try {
            const [, bytes] = GLib.file_get_contents(SETTINGS_FILE);
            opt = JSON.parse(new TextDecoder().decode(bytes)) || {};
        } catch {
            opt = {};
        }
        const scale = SIZES[opt.size] ?? SIZES.normal;
        if (scale !== this._scale) {
            this._scale = scale;
            this.actor?.set_size(this._w, this._h);
            this._world.resize(this._w, this._h, FEET_Y * scale);
        }
        this._world.jumpEvery = opt.jumps in JUMPS ? JUMPS[opt.jumps] : JUMPS.sometimes;
        this._idleReading = opt.idle_reading !== false;
    }

    _(key) {
        return this._strings[key] ?? key;
    }

    _now() {
        return GLib.get_monotonic_time() / 1e6;
    }

    // ── D-Bus: org.ruscalinux.RuscaPallas.Shell ───────────────────────────
    get Visible() {
        return this._visible;
    }

    Show() {
        if (this._visible)
            return;
        if (this._vanishId) {            // stava sparendo: ci ripensa
            GLib.source_remove(this._vanishId);
            this._vanishId = 0;
        }
        this._visible = true;
        this._world.x = null;          // ricompare in un punto a caso
        this._updateShown();
        this._anim.startMagic('appear');
        this._dbus.emit_property_changed('Visible', GLib.Variant.new_boolean(true));
    }

    Hide() {
        if (!this._visible)
            return;
        this._visible = false;
        this._call('Stop');
        this._showBubble(false);
        this._menu.close();
        // sparisce nel nulla, poi esce di scena
        const seconds = this._inChrome ? this._anim.startMagic('vanish') : 0;
        this._vanishId = GLib.timeout_add(GLib.PRIORITY_DEFAULT, Math.round(seconds * 1000) + 60, () => {
            this._vanishId = 0;
            this._updateShown();
            return GLib.SOURCE_REMOVE;
        });
        this._dbus.emit_property_changed('Visible', GLib.Variant.new_boolean(false));
        Main.notify(this._('name'), this._('hidden_hint'));
    }

    /** La finestra di RuscaPallas, aperta sulle impostazioni. */
    _openSettings() {
        try {
            const app = Gio.DesktopAppInfo.new('org.ruscalinux.RuscaPallas.desktop');
            if (app) {
                app.launch_action('settings', global.create_app_launch_context(0, -1));
                return;
            }
        } catch (e) {
            console.warn(`ruscapallas: ${e.message}`);
        }
        try {
            GLib.spawn_command_line_async('ruscapallas --settings');
        } catch (e) {
            console.warn(`ruscapallas: ${e.message}`);
        }
    }

    // ── servizio di dialogo ───────────────────────────────────────────────
    _call(method) {
        if (!this._proxy)
            return;
        this._proxy[`${method}Remote`]((result, error) => {
            if (error && method === 'Talk') {
                console.warn(`ruscapallas: ${error.message}`);
                this._onState('idle');
                this._onError('err_service', '');
            }
        });
    }

    _onState(state) {
        if (this._answerId) {               // il servizio ha risposto
            GLib.source_remove(this._answerId);
            this._answerId = 0;
        }
        const s = STATES[state];
        this._busy = Boolean(s);
        if (s) {
            this._anim.setMode(s.mode);
            this._icon = s.icon;
            this._showBubble(true);
        } else {                        // idle, error, missing: torna a passeggiare
            const was = this._anim.mode;
            this._anim.setMode('walk');
            this._showBubble(false);
            if (DIALOG.includes(was))
                this._anim.puff();
        }
    }

    _onError(key, detail) {
        // err_missing elenca i pezzi mancanti come chiavi da tradurre
        const names = key === 'err_missing'
            ? (detail || '').split(',').filter(Boolean).map(k => this._(k)).join(', ')
            : detail || '';
        const body = this._(key in this._strings ? key : 'err_generic').replace('{names}', names);
        Main.notify(this._('name'), body);
    }

    _talk() {
        const mode = this._anim.mode;
        if (mode === 'speak' || mode === 'listen') {   // basta così
            this._call('Stop');
            return;
        }
        if (DIALOG.includes(mode))
            return;
        if (!this._proxy) {
            this._onError('err_service', '');
            return;
        }
        this._restUntil = 0;
        this._onState('listening');       // drizza le orecchie subito
        this._call('Talk');
        // se il servizio non dice niente, non resta in ascolto per sempre
        this._answerId = GLib.timeout_add_seconds(GLib.PRIORITY_DEFAULT, ANSWER_TIMEOUT, () => {
            this._answerId = 0;
            this._onState('idle');
            this._onError('err_service', '');
            return GLib.SOURCE_REMOVE;
        });
    }

    // ── mouse ─────────────────────────────────────────────────────────────
    _onPress(ev) {
        const button = ev.get_button();
        if (button === Clutter.BUTTON_SECONDARY) {
            this._menu.toggle();
            return Clutter.EVENT_STOP;
        }
        if (button !== Clutter.BUTTON_PRIMARY)
            return Clutter.EVENT_PROPAGATE;
        if (this._anim.inMagic)          // mentre appare o sparisce non si tocca
            return Clutter.EVENT_STOP;
        const [x, y] = ev.get_coords();
        this._press = {x, y, dx: x - this.actor.x, dy: y - this.actor.y, dragging: false};
        this._grab = global.stage.grab(this.actor);
        return Clutter.EVENT_STOP;
    }

    _onMotion(ev) {
        const p = this._press;
        if (!p)
            return Clutter.EVENT_PROPAGATE;
        const [x, y] = ev.get_coords();
        if (!p.dragging && Math.hypot(x - p.x, y - p.y) < DRAG_THRESHOLD)
            return Clutter.EVENT_STOP;
        p.dragging = true;
        this._world.drag(x - p.dx, y - p.dy + FEET_Y * this._scale);
        return Clutter.EVENT_STOP;
    }

    _onRelease(ev) {
        const p = this._press;
        this._press = null;
        if (this._grab) {
            this._grab.dismiss();
            this._grab = null;
        }
        if (!p || ev.get_button() !== Clutter.BUTTON_PRIMARY)
            return Clutter.EVENT_PROPAGATE;
        if (p.dragging)
            this._world.drop(this._area(), this._windows());
        else
            this._talk();
        return Clutter.EVENT_STOP;
    }

    // ── il mondo: area di lavoro e finestre del monitor principale ────────
    _area() {
        return Main.layoutManager.getWorkAreaForMonitor(Main.layoutManager.primaryIndex);
    }

    _windows() {
        const primary = Main.layoutManager.primaryIndex;
        const ws = global.workspace_manager.get_active_workspace();
        return ws.list_windows()
            .filter(w => w.get_window_type() === Meta.WindowType.NORMAL &&
                !w.minimized && !w.is_fullscreen() &&
                w.get_monitor() === primary && w.showing_on_its_workspace())
            .map(w => {
                const r = w.get_frame_rect();
                return {id: w.get_stable_sequence(), x: r.x, y: r.y, width: r.width, height: r.height};
            });
    }

    // ── ogni fotogramma ───────────────────────────────────────────────────
    _tick() {
        const now = this._now();
        const dt = this._last ? Math.min(0.1, now - this._last) : 1 / 60;
        this._last = now;
        const anim = this._anim, world = this._world;

        // per conto suo: ogni tanto si siede a leggere, ogni tanto sbuffa
        if (!this._busy && !this._press) {
            if (anim.mode === 'walk' && this._idleReading && now > this._nextRest &&
                !world.airborne && world.platform === null) {
                this._restUntil = now + 8 + Math.random() * 10;
                this._nextRest = this._restUntil + 40 + Math.random() * 80;
                anim.setMode('sit');
            } else if (anim.mode === 'sit' && now > this._restUntil) {
                anim.setMode('walk');
                anim.roll();
            }
        }

        const canWalk = anim.mode === 'walk' && !anim.reduceMotion && !this._press && !anim.inMagic;
        let moving = false;
        if (!this._press?.dragging)
            moving = world.step(dt, this._area(), this._windows(), canWalk);
        for (const e of world.events) {
            if (e === 'peek')
                anim.roll();
        }
        anim.moving = moving;
        anim.airborne = world.airborne || Boolean(this._press?.dragging);
        anim.dir = world.dir;
        this._model = anim.step(dt);

        const x = Math.round(world.x), y = world.top;
        this.actor.set_position(x, y);
        if (this._bubbleOn) {
            const bx = world.dir > 0 ? x + this._w * 0.74 : x + this._w * 0.26 - BUBBLE_W;
            this.bubble.set_position(Math.round(bx), Math.max(0, y - BUBBLE_H * 0.55));
            this.bubble.queue_repaint();
        }
        this.actor.queue_repaint();
    }

    _repaint(area) {
        const cr = area.get_context();
        const [w, h] = area.get_surface_size();
        cr.save();
        cr.setOperator(0);               // CLEAR: sfondo trasparente
        cr.paint();
        cr.restore();
        cr.scale(w / BOX_W, h / BOX_H);
        try {
            draw(cr, this._model);
        } catch (e) {
            console.error(`ruscapallas: ${e}`);
        }
        cr.$dispose();
    }

    destroy() {
        if (this._vanishId) {
            GLib.source_remove(this._vanishId);
            this._vanishId = 0;
        }
        if (this._answerId) {
            GLib.source_remove(this._answerId);
            this._answerId = 0;
        }
        this._optMonitor?.cancel();
        this._optMonitor = null;
        for (const id of this._overviewIds ?? [])
            Main.overview.disconnect(id);
        this._overviewIds = [];
        this._timeline?.stop();
        this._timeline = null;
        if (this._inChrome) {
            Main.layoutManager.removeChrome(this.bubble);
            Main.layoutManager.removeChrome(this.actor);
            this._inChrome = false;
        }
        if (this._grab) {
            this._grab.dismiss();
            this._grab = null;
        }
        if (this._proxy) {
            for (const id of this._signals)
                this._proxy.disconnectSignal(id);
            if (this._ownerId)
                this._proxy.disconnect(this._ownerId);
            this._proxy = null;
        }
        if (this._nameId) {
            Gio.bus_unown_name(this._nameId);
            this._nameId = 0;
        }
        this._dbus?.unexport();
        this._dbus = null;
        this._settings.disconnect(this._animId);
        this._menu?.destroy();
        this._menu = null;
        this.bubble?.destroy();
        this.bubble = null;
        this.actor?.destroy();
        this.actor = null;
    }
}
