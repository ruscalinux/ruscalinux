// extension.js — RuscaPallas 1.99.3 — GPL-3.0-or-later
//
// Estensione di GNOME Shell: porta Pallasio sul desktop. Il disegno è in
// figure.js, i movimenti in motion.js e world.js, il resto in pallasio.js.
//
// Copyright (C) 2026 Nunzio Curcuruto — https://www.ruscalinux.org

import {Extension} from 'resource:///org/gnome/shell/extensions/extension.js';

import {Pallasio} from './pallasio.js';

export default class RuscaPallasExtension extends Extension {
    enable() {
        this._pallasio = new Pallasio(this);
    }

    disable() {
        this._pallasio?.destroy();
        this._pallasio = null;
    }
}
