#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
RuscaPallas 1.99.3 — richiama Pallasio sul desktop.

    ruscapallas            lo richiama (attiva l'estensione, se serve)
    ruscapallas --hide     lo rimanda nello sgabuzzino
    ruscapallas --quit     spegne il servizio di dialogo e libera la memoria
    ruscapallas --version

Pallasio vive in un'estensione di GNOME Shell (ruscapallas@ruscalinux.org):
questo comando non apre finestre, parla con GNOME Shell su D-Bus e avvisa
con una notifica quando c'è qualcosa da sapere.

Copyright (C) 2026 Nunzio Curcuruto — https://www.ruscalinux.org
Licenza: GNU GPL 3.0 o successiva.
"""
import json
import os
import sys

import gi
gi.require_version("Gio", "2.0")
from gi.repository import Gio, GLib  # noqa: E402

APP_ID = "org.ruscalinux.RuscaPallas"
APP_VERSION = "1.99.3"
UUID = "ruscapallas@ruscalinux.org"
BASE_DIR = os.path.dirname(os.path.realpath(__file__))
LANG_DIR = os.path.join(BASE_DIR, "lang")
EXT_STATE_ENABLED = 1          # ExtensionState.ACTIVE di GNOME Shell (48)


def strings():
    def read(code):
        try:
            with open(os.path.join(LANG_DIR, f"{code}.json"), encoding="utf-8") as f:
                return json.load(f)
        except (OSError, ValueError):
            return None
    out = read("en") or {}
    for name in GLib.get_language_names():
        found = read(name.split(".")[0].split("@")[0]) or read(name.split("_")[0].split(".")[0])
        if found:
            out.update(found)
            break
    return out


_S = strings()


def _(key):
    return _S.get(key, key)


def call(bus, name, path, iface, method, args=None, reply="()"):
    return bus.call_sync(name, path, iface, method, args, GLib.VariantType(reply),
                         Gio.DBusCallFlags.NONE, 5000, None)


def notify(bus, body):
    try:
        call(bus, "org.freedesktop.Notifications", "/org/freedesktop/Notifications",
             "org.freedesktop.Notifications", "Notify",
             GLib.Variant("(susssasa{sv}i)", (_("name"), 0, APP_ID, _("name"), body, [],
                                               {"desktop-entry": GLib.Variant("s", APP_ID)}, -1)),
             "(u)")
    except GLib.Error:
        print(body, file=sys.stderr)


def extension_state(bus):
    """Stato dell'estensione secondo GNOME Shell, o None se non la conosce
    (installata dopo l'accesso: su Wayland si vede al prossimo accesso)."""
    info = call(bus, "org.gnome.Shell", "/org/gnome/Shell", "org.gnome.Shell.Extensions",
                "GetExtensionInfo", GLib.Variant("(s)", (UUID,)), "(a{sv})").unpack()[0]
    return int(info["state"]) if info and "state" in info else None


def show(bus):
    try:
        state = extension_state(bus)
    except GLib.Error:
        notify(bus, _("no_shell"))
        return 1
    if state is None:
        notify(bus, _("relogin"))
        return 1
    if state != EXT_STATE_ENABLED:
        call(bus, "org.gnome.Shell", "/org/gnome/Shell", "org.gnome.Shell.Extensions",
             "EnableExtension", GLib.Variant("(s)", (UUID,)), "(b)")
        notify(bus, _("shown"))
        return 0
    try:
        call(bus, f"{APP_ID}.Shell", "/org/ruscalinux/RuscaPallas/Shell",
             f"{APP_ID}.Shell", "Show")
    except GLib.Error as e:
        print("ruscapallas:", e.message, file=sys.stderr)
        return 1
    return 0


def main(argv):
    if "--version" in argv:
        print(f"RuscaPallas {APP_VERSION}")
        return 0
    if "--help" in argv or "-h" in argv:
        print(__doc__.strip().split("\n\n")[1])
        return 0
    bus = Gio.bus_get_sync(Gio.BusType.SESSION, None)
    if "--hide" in argv:
        try:
            call(bus, f"{APP_ID}.Shell", "/org/ruscalinux/RuscaPallas/Shell", f"{APP_ID}.Shell", "Hide")
        except GLib.Error:
            pass
        return 0
    if "--quit" in argv:
        try:
            call(bus, APP_ID, "/org/ruscalinux/RuscaPallas", APP_ID, "Quit")
        except GLib.Error:
            pass                    # non era acceso
        return 0
    return show(bus)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
