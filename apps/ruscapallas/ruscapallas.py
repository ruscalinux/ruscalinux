#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
RuscaPallas 1.99.3 — la finestra di Pallasio.

Pallasio, il manul cinico con giacca, cravatta e occhialini, vive in
un'estensione di GNOME Shell (ruscapallas@ruscalinux.org) e parla grazie
al servizio org.ruscalinux.RuscaPallas.Dialog. Questa finestra lo richiama sul
desktop e lo configura: dimensione, salti, ascolto, risposte, modelli,
voce, personalità e tema. Le scelte vanno in
~/.config/ruscapallas/settings.json, che leggono anche l'estensione (subito)
e il servizio (alla domanda dopo, o alla conversazione dopo per modelli e
voce).

    ruscapallas            lo richiama dallo sgabuzzino; se è già sul
                           desktop, apre le impostazioni
    ruscapallas --settings apre le impostazioni
    ruscapallas --show     lo richiama, senza finestra
    ruscapallas --hide     lo rimanda nello sgabuzzino
    ruscapallas --quit     spegne il servizio di dialogo e libera la memoria
    ruscapallas --version

Copyright (C) 2026 Nunzio Curcuruto — https://www.ruscalinux.org
Licenza: GNU GPL 3.0 o successiva.

Requisiti: Python 3.10+, PyGObject, GTK 4.18+, libadwaita 1.7+.
"""
import json
import os
import shutil
import sys

import gi
gi.require_version("Gio", "2.0")
from gi.repository import Gio, GLib  # noqa: E402

BASE_DIR = os.path.dirname(os.path.realpath(__file__))
sys.path.insert(0, BASE_DIR)

APP_ID = "org.ruscalinux.RuscaPallas"
APP_NAME = "RuscaPallas"
APP_VERSION = "1.99.3"
UUID = "ruscapallas@ruscalinux.org"
SHELL_NAME, SHELL_PATH = f"{APP_ID}.Shell", "/org/ruscalinux/RuscaPallas/Shell"
# il servizio di dialogo ha un nome suo: l'App ID è della finestra
SERVICE_NAME, SERVICE_PATH = "org.ruscalinux.RuscaPallas.Dialog", "/org/ruscalinux/RuscaPallas/Dialog"
EXT_ACTIVE = 1                 # ExtensionState.ACTIVE di GNOME Shell (48)
STYLE_SRC = os.path.join(BASE_DIR, "style.css")
ICON_SRC = os.path.join(BASE_DIR, "ruscapallas.svg")
LANG_DIR = os.path.join(BASE_DIR, "lang")
CONFIG_DIR = os.path.join(GLib.get_user_config_dir(), "ruscapallas")
CONFIG_FILE = os.path.join(CONFIG_DIR, "settings.json")
DATA_DIR = os.path.join(GLib.get_user_data_dir(), "ruscapallas")
ENTITY_SYSTEM = os.path.join(BASE_DIR, "entities", "pallasio.md")
ENTITY_USER = os.path.join(DATA_DIR, "pallasio.md")
LISSE_DESKTOP = "org.ruscalinux.RuscaLLisse.desktop"
COMPONENTS = (
    ("Vosk (libvosk)", "Apache 2.0 — Alpha Cephei Inc.", "https://github.com/alphacep/vosk-api"),
    ("Piper (piper1-gpl)", "GPL-3.0 — Michael Hansen", "https://github.com/OHF-Voice/piper1-gpl"),
    ("llama.cpp (llama-server)", "MIT — The ggml authors", "https://github.com/ggml-org/llama.cpp"),
    ("markdown-it-mark", "MIT — Vitaly Puzrin, Alex Kocharin; ExecutableBookProject",
     "https://github.com/markdown-it/markdown-it-mark"),
)
# Scelte con un nome, nell'ordine dei menu. Le chiavi sono quelle di
# settings.json; i valori li capiscono l'estensione e il servizio.
SIZES = ("small", "normal", "large")
JUMPS = ("never", "sometimes", "often")
LISTEN = (4, 8, 15)
WORDS = (30, 60, 120)
SPEEDS = (0.0, 0.8, 0.9, 1.0, 1.1, 1.2)        # 0: quella della personalità
THEMES = ("system", "light", "dark")
DEFAULTS = {"size": "normal", "jumps": "sometimes", "idle_reading": True, "listen_window": 8,
            "max_words": 60, "emotions": True, "vosk_model": "", "model": "", "voice": "",
            "speed": 0.0, "gpu": True, "theme": "system", "width": 480, "height": 720}


# ── Traduzioni (lang/xx.json, ripiego en.json) ──────────────────────────────
LANG_ALIASES = {"zh_HK": "zh_TW", "zh_MO": "zh_TW", "zh_SG": "zh_CN", "zh": "zh_CN",
                "pt": "pt_BR", "sk": "cs"}


def _load_strings():
    def read(code):
        try:
            with open(os.path.join(LANG_DIR, f"{code}.json"), encoding="utf-8") as f:
                return json.load(f)
        except (OSError, ValueError):
            return {}
    strings = read("en")
    for name in GLib.get_language_names():
        base = name.split(".")[0].split("@")[0]
        lang = base.split("_")[0]
        for code in (base, LANG_ALIASES.get(base), lang, LANG_ALIASES.get(lang)):
            if not code:
                continue
            if code in ("C", "POSIX", "en"):
                return strings, "en"
            data = read(code)
            if data:
                strings.update(data)
                return strings, code
    return strings, "en"


_STRINGS, LANG = _load_strings()


def _(key, **fields):
    text = _STRINGS.get(key, key)
    try:
        return text.format(**fields) if fields else text
    except (KeyError, IndexError, ValueError):
        return text


# ── Impostazioni: si conservano anche le chiavi che non sono di questa
#    finestra (le scrive a mano l'utente, o una versione futura) ─────────────
def load_settings():
    cfg = dict(DEFAULTS)
    try:
        with open(CONFIG_FILE, encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, dict):
            cfg.update(data)
    except (OSError, ValueError):
        pass
    return cfg


def save_settings(cfg):
    try:
        os.makedirs(CONFIG_DIR, exist_ok=True)
        tmp = CONFIG_FILE + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(cfg, f, ensure_ascii=False, indent=2)
        os.replace(tmp, CONFIG_FILE)       # l'estensione vede un file intero, mai a metà
        return True
    except OSError:
        return False


def ensure_entity():
    if not os.path.exists(ENTITY_USER) and os.path.isfile(ENTITY_SYSTEM):
        os.makedirs(DATA_DIR, exist_ok=True)
        shutil.copyfile(ENTITY_SYSTEM, ENTITY_USER)
    return ENTITY_USER


def lisse_settings():
    try:
        with open(os.path.join(GLib.get_user_config_dir(), "ruscallisse", "settings.json"),
                  encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


# ── GNOME Shell e il servizio, su D-Bus ─────────────────────────────────────
def call(bus, name, path, iface, method, args=None, reply="()", auto_start=True):
    flags = Gio.DBusCallFlags.NONE if auto_start else Gio.DBusCallFlags.NO_AUTO_START
    return bus.call_sync(name, path, iface, method, args, GLib.VariantType(reply), flags, 5000, None)


def extension_state(bus):
    """Stato dell'estensione, o None se GNOME Shell non la conosce
    (installata dopo l'accesso: su Wayland si vede al prossimo accesso)."""
    info = call(bus, "org.gnome.Shell", "/org/gnome/Shell", "org.gnome.Shell.Extensions",
                "GetExtensionInfo", GLib.Variant("(s)", (UUID,)), "(a{sv})").unpack()[0]
    return int(info["state"]) if info and "state" in info else None


def pallasio_visible(bus):
    """True/False se l'estensione è attiva, None se non lo è."""
    try:
        if extension_state(bus) != EXT_ACTIVE:
            return None
        v = call(bus, SHELL_NAME, SHELL_PATH, "org.freedesktop.DBus.Properties", "Get",
                 GLib.Variant("(ss)", (SHELL_NAME, "Visible")), "(v)", auto_start=False)
        return bool(v.unpack()[0])
    except GLib.Error:
        return None


def show(bus):
    """Attiva l'estensione se serve e richiama Pallasio. Restituisce None se
    tutto va bene, altrimenti la chiave del messaggio da mostrare."""
    try:
        state = extension_state(bus)
    except GLib.Error:
        return "no_shell"
    if state is None:
        return "relogin"
    try:
        if state != EXT_ACTIVE:
            call(bus, "org.gnome.Shell", "/org/gnome/Shell", "org.gnome.Shell.Extensions",
                 "EnableExtension", GLib.Variant("(s)", (UUID,)), "(b)")
        else:
            call(bus, SHELL_NAME, SHELL_PATH, SHELL_NAME, "Show", auto_start=False)
    except GLib.Error as e:
        print("ruscapallas:", e.message, file=sys.stderr)
        return "err_generic"
    return None


def hide(bus):
    try:
        call(bus, SHELL_NAME, SHELL_PATH, SHELL_NAME, "Hide", auto_start=False)
    except GLib.Error:
        pass


def quit_service(bus):
    """Spegne il servizio se è acceso: modelli e voce nuovi valgono al clic dopo."""
    try:
        call(bus, SERVICE_NAME, SERVICE_PATH, SERVICE_NAME, "Quit", auto_start=False)
        return True
    except GLib.Error:
        return False


def launch_action(state, visible):
    """Che cosa fa un clic sull'icona: 'show' (Pallasio compare dal nulla,
    nessuna finestra) o 'window' (le impostazioni). Le impostazioni si aprono
    solo se Pallasio è già sul desktop, o se GNOME non conosce ancora
    l'estensione (la finestra spiega che serve un nuovo accesso)."""
    if state is None:
        return "window"
    if state != EXT_ACTIVE or visible is False:
        return "show"
    return "window"


def notify(bus, body):
    try:
        call(bus, "org.freedesktop.Notifications", "/org/freedesktop/Notifications",
             "org.freedesktop.Notifications", "Notify",
             GLib.Variant("(susssasa{sv}i)", (_("name"), 0, APP_ID, _("name"), body, [],
                                               {"desktop-entry": GLib.Variant("s", APP_ID)}, -1)),
             "(u)")
    except GLib.Error:
        print(body, file=sys.stderr)


# ── La finestra ─────────────────────────────────────────────────────────────
def build_app():
    gi.require_version("Gtk", "4.0")
    gi.require_version("Adw", "1")
    from gi.repository import Adw, Gdk, Gtk
    import rusca_engine as eng
    import rusca_piper as piper
    import rusca_vosk as vosk

    def apply_color_scheme(theme):
        Adw.StyleManager.get_default().set_color_scheme({
            "light": Adw.ColorScheme.FORCE_LIGHT,
            "dark": Adw.ColorScheme.FORCE_DARK,
        }.get(theme, Adw.ColorScheme.DEFAULT))

    def theme_has_icon(name=APP_ID):
        display = Gdk.Display.get_default()
        return display is not None and Gtk.IconTheme.get_for_display(display).has_icon(name)

    def show_about_dialog(parent, tr, app_id, app_name, version, description, has_icon,
                          components=()):
        """Finestra «Informazioni» comune alle RuscaLinux OS Apps (specifiche,
        sezioni 3.10 e 12): la stessa di RuscaLLisse."""
        def open_uri(_row, uri):
            def done(launcher, result):
                try:
                    launcher.launch_finish(result)
                except GLib.Error:
                    pass
            Gtk.UriLauncher.new(uri).launch(parent, None, done)

        nav = Adw.NavigationView()
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6,
                      margin_top=12, margin_bottom=24, margin_start=24, margin_end=24)
        icon = Gtk.Image(icon_name=app_id if has_icon else "application-x-executable",
                         pixel_size=128, margin_bottom=12)
        icon.add_css_class("icon-dropshadow")
        box.append(icon)
        for text, css in ((app_name, "title-1"), (version, "dim-label"), (description, "body")):
            label = Gtk.Label(label=text, wrap=True, justify=Gtk.Justification.CENTER)
            label.add_css_class(css)
            box.append(label)
        links = Adw.PreferencesGroup(margin_top=18)
        for title, subtitle, uri in (
                (tr("about_website"), "www.ruscalinux.org", "https://www.ruscalinux.org/"),
                (tr("about_support"), "info@ruscalinux.org", "mailto:info@ruscalinux.org"),
                (tr("about_license"), "GNU GPL 3.0", "https://www.gnu.org/licenses/gpl-3.0.html")):
            row = Adw.ActionRow(title=title, subtitle=subtitle, activatable=True)
            row.add_suffix(Gtk.Image(icon_name="adw-external-link-symbolic"))
            row.connect("activated", open_uri, uri)
            links.add(row)
        note_row = Adw.ActionRow(title=tr("dev_note_title"), activatable=True)
        note_row.add_suffix(Gtk.Image(icon_name="go-next-symbolic"))
        links.add(note_row)
        box.append(links)
        if components:
            ext = Adw.PreferencesGroup(title=tr("about_components"), margin_top=12)
            for name, licence, uri in components:
                row = Adw.ActionRow(title=name, subtitle=licence, activatable=True)
                row.add_suffix(Gtk.Image(icon_name="adw-external-link-symbolic"))
                row.connect("activated", open_uri, uri)
                ext.add(row)
            box.append(ext)
        copyright_label = Gtk.Label(label="© 2026 Nunzio Curcuruto", margin_top=12)
        copyright_label.add_css_class("caption")
        copyright_label.add_css_class("dim-label")
        box.append(copyright_label)
        scroller = Gtk.ScrolledWindow(hscrollbar_policy=Gtk.PolicyType.NEVER,
                                      propagate_natural_height=True, child=box)
        view = Adw.ToolbarView(content=scroller)
        view.add_top_bar(Adw.HeaderBar(show_title=False))
        nav.add(Adw.NavigationPage(title=app_name, child=view))
        note_label = Gtk.Label(label=tr("ai_note"), wrap=True, xalign=0, valign=Gtk.Align.START,
                               margin_top=12, margin_bottom=24, margin_start=24, margin_end=24)
        note_label.add_css_class("body")
        note_view = Adw.ToolbarView(content=note_label)
        note_view.add_top_bar(Adw.HeaderBar())
        note_page = Adw.NavigationPage(title=tr("dev_note_title"), child=note_view)
        note_row.connect("activated", lambda _row: nav.push(note_page))
        Adw.Dialog(title=app_name, content_width=420, child=nav).present(parent)

    class PallasWindow(Adw.ApplicationWindow):
        def __init__(self, app):
            super().__init__(application=app, title=APP_NAME)
            self.cfg = load_settings()
            self.bus = Gio.bus_get_sync(Gio.BusType.SESSION, None)
            self.set_default_size(self.cfg.get("width", 480), self.cfg.get("height", 720))
            self.set_size_request(360, 294)
            self._updating = False

            header = Adw.HeaderBar()
            talk = Gtk.Button(label=_("talk"), action_name="win.talk", tooltip_text=_("talk_tip"))
            talk.add_css_class("suggested-action")
            header.pack_start(talk)
            menu = Gio.Menu()
            sec = Gio.Menu()
            sec.append(_("shortcuts"), "win.shortcuts")
            sec.append(_("about"), "win.about")
            menu.append_section(None, sec)
            header.pack_end(Gtk.MenuButton(icon_name="open-menu-symbolic", menu_model=menu,
                                           primary=True, tooltip_text=_("main_menu")))

            self.banner = Adw.Banner(title=_("relogin_short"))
            self.toasts = Adw.ToastOverlay(child=self._build_page())
            view = Adw.ToolbarView(content=self.toasts)
            view.add_top_bar(header)
            view.add_top_bar(self.banner)
            self.set_content(view)

            for name, cb in (("talk", self.talk), ("shortcuts", self.show_shortcuts),
                             ("about", self.show_about)):
                a = Gio.SimpleAction.new(name, None)
                a.connect("activate", lambda _a, _p, f=cb: f())
                self.add_action(a)
            self.connect("close-request", self._on_close)
            self.refresh_visible()

        # ── costruzione ──────────────────────────────────────────────────
        def _combo(self, title, labels, values, key, subtitle="", after=None):
            row = Adw.ComboRow(title=title, subtitle=subtitle, model=Gtk.StringList.new(labels))
            current = self.cfg.get(key, DEFAULTS.get(key))
            row.set_selected(values.index(current) if current in values else 0)

            def changed(r, _p):
                i = r.get_selected()
                if 0 <= i < len(values) and not self._updating:
                    self.cfg[key] = values[i]
                    self.save()
                    if after:
                        after()
            row.connect("notify::selected", changed)
            return row

        def _switch(self, title, key, subtitle="", after=None):
            row = Adw.SwitchRow(title=title, subtitle=subtitle,
                                active=bool(self.cfg.get(key, DEFAULTS.get(key))))

            def changed(r, _p):
                self.cfg[key] = r.get_active()
                self.save()
                if after:
                    after()
            row.connect("notify::active", changed)
            return row

        def _pieces(self, items, key, inherited):
            """Menu di modelli o voci: prima «Come RuscaLLisse» (il nome del
            file che usa sta nel sottotitolo), poi i file trovati."""
            def short(p):
                name = os.path.basename(p.rstrip("/"))
                return name[:-5] if name.endswith(".onnx") else name
            sub = _("lisse_uses", name=short(inherited)) if inherited else _("pieces_auto")
            return self._combo({"vosk_model": _("piece_listen_title"), "model": _("piece_think_title"),
                                "voice": _("piece_speak_title")}[key],
                               [_("same_as_lisse")] + [short(p) for p in items], [""] + list(items),
                               key, subtitle=sub, after=self.restart_service)

        def _build_page(self):
            page = Adw.PreferencesPage()

            g = Adw.PreferencesGroup(title=_("pref_desktop"))
            self.visible_row = Adw.SwitchRow(title=_("pref_show"), subtitle=_("pref_show_sub"))
            self.visible_row.connect("notify::active", self._on_visible)
            g.add(self.visible_row)
            g.add(self._combo(_("pref_size"), [_(f"size_{s}") for s in SIZES], SIZES, "size"))
            g.add(self._combo(_("pref_jumps"), [_(f"jumps_{j}") for j in JUMPS], JUMPS, "jumps",
                              subtitle=_("pref_jumps_sub")))
            g.add(self._switch(_("pref_idle_reading"), "idle_reading", _("pref_idle_reading_sub")))
            page.add(g)

            g = Adw.PreferencesGroup(title=_("pref_conversation"))
            g.add(self._combo(_("pref_listen"), [_("seconds", n=n) for n in LISTEN], LISTEN,
                              "listen_window", subtitle=_("pref_listen_sub")))
            g.add(self._combo(_("pref_words"), [_(f"words_{w}") for w in WORDS], WORDS, "max_words"))
            g.add(self._switch(_("pref_emotions"), "emotions", _("pref_emotions_sub")))
            page.add(g)

            lisse = lisse_settings()
            g = Adw.PreferencesGroup(title=_("pref_models"), description=_("pref_models_sub"))
            g.add(self._pieces(vosk.find_models(), "vosk_model", lisse.get("vosk_model", "")))
            g.add(self._pieces(eng.find_models(), "model", lisse.get("model", "")))
            g.add(self._pieces(piper.find_voices(), "voice", lisse.get("voice", "")))
            g.add(self._combo(_("pref_speed"),
                              [_("speed_personality")] + [f"{s:.1f}".replace(".", _("decimal_point"))
                                                          for s in SPEEDS[1:]],
                              SPEEDS, "speed", after=self.restart_service))
            g.add(self._switch(_("pref_gpu"), "gpu", after=self.restart_service))
            try:
                app = Gio.DesktopAppInfo.new(LISSE_DESKTOP)
            except TypeError:                 # RuscaLLisse non è installato
                app = None
            if app is not None:
                row = Adw.ActionRow(title=_("open_lisse"), subtitle=_("open_lisse_sub"), activatable=True)
                row.add_suffix(Gtk.Image(icon_name="go-next-symbolic"))
                row.connect("activated", lambda _r: app.launch([], None))
                g.add(row)
            page.add(g)

            g = Adw.PreferencesGroup(title=_("pref_personality"))
            row = Adw.ActionRow(title=_("edit_personality"), subtitle=_("edit_personality_sub"),
                                activatable=True)
            row.add_suffix(Gtk.Image(icon_name="document-edit-symbolic"))
            row.connect("activated", lambda _r: self.edit_personality())
            g.add(row)
            row = Adw.ActionRow(title=_("reset_personality"), activatable=True)
            row.add_suffix(Gtk.Image(icon_name="edit-undo-symbolic"))
            row.connect("activated", lambda _r: self.reset_personality())
            g.add(row)
            page.add(g)

            g = Adw.PreferencesGroup(title=_("pref_look"))
            g.add(self._combo(_("theme"), [_(f"theme_{t}") for t in THEMES], THEMES, "theme",
                              after=lambda: apply_color_scheme(self.cfg["theme"])))
            page.add(g)
            return page

        # ── azioni ───────────────────────────────────────────────────────
        def save(self):
            if not save_settings(self.cfg):
                self.toast(_("err_save"))

        def toast(self, text, timeout=4):
            self.toasts.add_toast(Adw.Toast(title=text, timeout=timeout))

        def refresh_visible(self):
            vis = pallasio_visible(self.bus)
            state = None
            try:
                state = extension_state(self.bus)
            except GLib.Error:
                pass
            self._updating = True
            self.visible_row.set_active(bool(vis))
            self._updating = False
            self.banner.set_revealed(state is None)

        def _on_visible(self, row, _p):
            if self._updating:
                return
            if row.get_active():
                err = show(self.bus)
                if err:
                    self.toast(_(err), 8)
                    GLib.timeout_add(300, lambda: self.refresh_visible() or False)
            else:
                hide(self.bus)

        def talk(self):
            if show(self.bus) in ("relogin", "no_shell"):
                self.toast(_("relogin"), 8)
                return
            self.bus.call(SERVICE_NAME, SERVICE_PATH, SERVICE_NAME, "Talk", None, None,
                          Gio.DBusCallFlags.NONE, 5000, None, None)
            self.refresh_visible()

        def restart_service(self):
            if quit_service(self.bus):
                self.toast(_("applies_next"))

        def edit_personality(self):
            try:
                path = ensure_entity()
            except OSError as e:
                self.toast(str(e))
                return
            Gtk.FileLauncher.new(Gio.File.new_for_path(path)).launch(self, None, None)

        def reset_personality(self):
            dlg = Adw.AlertDialog(heading=_("reset_personality_q"), body=_("reset_personality_body"))
            dlg.add_response("cancel", _("cancel"))
            dlg.add_response("reset", _("reset"))
            dlg.set_response_appearance("reset", Adw.ResponseAppearance.DESTRUCTIVE)
            dlg.set_default_response("cancel")
            dlg.set_close_response("cancel")

            def done(d, result):
                if d.choose_finish(result) != "reset":
                    return
                try:
                    os.makedirs(DATA_DIR, exist_ok=True)
                    shutil.copyfile(ENTITY_SYSTEM, ENTITY_USER)
                    self.toast(_("personality_reset"))
                except OSError as e:
                    self.toast(str(e))
            dlg.choose(self, None, done)

        def show_shortcuts(self):
            group = Adw.PreferencesGroup()
            for title, accel in ((_("talk"), "<Control>t"), (_("shortcuts"), "<Control>question"),
                                 (_("main_menu"), "F10"), (_("sc_close"), "<Control>w"),
                                 (_("sc_quit"), "<Control>q")):
                row = Adw.ActionRow(title=title.rstrip("…"))
                ok, key, mods = Gtk.accelerator_parse(accel)
                keys = Gtk.Label(label=Gtk.accelerator_get_label(key, mods) if ok else accel)
                keys.add_css_class("dim-label")
                row.add_suffix(keys)
                group.add(row)
            page = Adw.PreferencesPage()
            page.add(group)
            view = Adw.ToolbarView(content=page)
            view.add_top_bar(Adw.HeaderBar())
            Adw.Dialog(title=_("shortcuts"), content_width=420, child=view).present(self)

        def show_about(self):
            show_about_dialog(self, _, APP_ID, APP_NAME, APP_VERSION, _("app_description"),
                              theme_has_icon(), COMPONENTS)

        def _on_close(self, *_a):
            if not self.is_maximized():
                w, h = self.get_default_size()
                self.cfg.update(width=w, height=h)
                self.save()
            return False

    class PallasApp(Adw.Application):
        def __init__(self):
            super().__init__(application_id=APP_ID)

        def do_startup(self):
            Adw.Application.do_startup(self)
            if LANG.split("_")[0] in ("ar",):
                Gtk.Widget.set_default_direction(Gtk.TextDirection.RTL)
            if os.path.isfile(STYLE_SRC):
                provider = Gtk.CssProvider()
                provider.load_from_path(STYLE_SRC)
                Gtk.StyleContext.add_provider_for_display(
                    Gdk.Display.get_default(), provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)
            apply_color_scheme(load_settings().get("theme", "system"))
            Adw.StyleManager.get_default().connect("notify::dark", lambda *_a: self.update_theme())
            self.connect("window-added", lambda *_a: self.update_theme())
            quit_action = Gio.SimpleAction.new("quit", None)
            quit_action.connect("activate", lambda *_a: [w.close() for w in self.get_windows()])
            self.add_action(quit_action)
            for action, accels in (("app.quit", ["<Control>q"]), ("window.close", ["<Control>w"]),
                                   ("win.talk", ["<Control>t"]),
                                   ("win.shortcuts", ["<Control>question"])):
                self.set_accels_for_action(action, accels)

        def update_theme(self):
            dark = Adw.StyleManager.get_default().get_dark()
            for window in self.get_windows():
                window.remove_css_class("rusca-light" if dark else "rusca-dark")
                window.add_css_class("rusca-dark" if dark else "rusca-light")

        def do_activate(self):
            (self.props.active_window or PallasWindow(self)).present()

    return PallasApp()


def main(argv):
    if "--version" in argv:
        print(f"{APP_NAME} {APP_VERSION}")
        return 0
    if "--help" in argv or "-h" in argv:
        print(__doc__.strip().split("\n\n")[2])
        return 0
    bus = Gio.bus_get_sync(Gio.BusType.SESSION, None)
    if not argv:                        # clic sull'icona
        try:
            state = extension_state(bus)
        except GLib.Error:
            state = None
        visible = pallasio_visible(bus) if state == EXT_ACTIVE else None
        if launch_action(state, visible) == "show":
            err = show(bus)
            if err:
                notify(bus, _(err))
            return 0
    if any(a in argv for a in ("--show", "--hide", "--quit")):
        if "--hide" in argv:
            hide(bus)
        elif "--quit" in argv:
            quit_service(bus)
        else:
            err = show(bus)
            if err:
                notify(bus, _(err))
                return 1
        return 0
    GLib.set_prgname(APP_ID)
    GLib.set_application_name(APP_NAME)
    return build_app().run([sys.argv[0]])


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
