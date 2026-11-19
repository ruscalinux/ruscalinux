# -*- coding: utf-8 -*-
# diffusion_view.py — RuscaLinux OS Tools 1.99.3 — GPL-3.0-or-later
#
# La vista «Immagini» di RuscaLLama: una descrizione in basso, il pulsante
# Genera, le immagini create al centro. Le impostazioni (modello, qualità,
# motore) stanno nel pannello laterale, come quelle della chat.
#
# Il lavoro vero lo fa rusca_diffusion.py, che avvia ruscadiffusion-engine
# (sd-cli, cioe' stable-diffusion.cpp: software esterno, licenza MIT) una
# volta per ogni generazione. Questo modulo e' solo interfaccia.
import os
import threading
import time

import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gdk, Gio, GLib, Gtk  # noqa: E402

import rusca_diffusion as rd  # noqa: E402

QUALITIES = ("fast", "normal", "detailed")
ASPECT_ORDER = ("square", "landscape", "portrait")
SIDES = (0, 512, 768, 1024, 1280)
TILE = 220                                   # lato delle miniature (px)


class _Item:
    """Un'immagine creata in questa sessione."""
    _next = 0

    def __init__(self, path, job, index, model_name):
        _Item._next += 1
        self.id = str(_Item._next)
        self.path = path
        self.prompt = job.prompt
        self.width, self.height, self.steps = job.width, job.height, job.steps
        self.seed = job.seed + index           # sd-cli: seme + posizione nel gruppo
        self.model = model_name
        self.saved = False
        self.child = None                      # Gtk.FlowBoxChild nella galleria


class ImagesPage(Adw.Bin):
    """Contenuto della vista. `window` e' la finestra di RuscaLLama: da lei
    prende le impostazioni (window.cfg, window._set), le notifiche
    (window.toasts) e gli allegati della chat (window.attach_image)."""

    def __init__(self, window, tr):
        super().__init__()
        self.window = window
        self._ = tr
        self.cfg = window.cfg
        self.models = []
        self.model = None
        self.devices = []
        self.items = []
        self.log_lines = []
        self._updating = False
        self._job = None
        self._t_start = None
        self._pulsing = True
        self._monitors = []
        self._models_timer = 0
        self.misplaced = []
        self._banner_action = None
        self.generator = rd.Generator(self._on_progress, self._on_preview,
                                      self._on_log, self._on_done)
        rd.clean_work_dir()                    # resti di una sessione interrotta
        self._build_actions()
        self.set_child(self._build_view())
        self.settings_page = self._build_settings()
        self.scan_models()
        if rd.find_binary():
            threading.Thread(target=self._load_devices, daemon=True).start()
        self.refresh()

    # ── azioni sulle immagini (gruppo "img", parametro: id dell'immagine) ──
    def _build_actions(self):
        group = Gio.SimpleActionGroup()
        for name, cb in (("save", self.save), ("copy", self.copy), ("to-chat", self.to_chat),
                         ("reuse", self.reuse), ("remove", self.remove),
                         ("open", self.open_viewer)):
            action = Gio.SimpleAction.new(name, GLib.VariantType.new("s"))
            action.connect("activate", lambda _a, p, f=cb: self._with_item(p.get_string(), f))
            group.add_action(action)
        self.insert_action_group("img", group)
        self._actions = group

    def _with_item(self, item_id, callback):
        for item in self.items:
            if item.id == item_id:
                callback(item)
                return

    def _item_menu(self, item):
        menu = Gio.Menu()
        for label, name in ((self._("img_save"), "save"), (self._("img_copy"), "copy"),
                            (self._("img_to_chat"), "to-chat"),
                            (self._("img_reuse"), "reuse")):
            menu.append(label, f"img.{name}::{item.id}")
        last = Gio.Menu()
        last.append(self._("img_remove"), f"img.remove::{item.id}")
        menu.append_section(None, last)
        return menu

    # ── interfaccia ───────────────────────────────────────────────────────
    def _build_view(self):
        _ = self._
        self.banner = Adw.Banner()
        self.banner.connect("button-clicked", self._on_banner)

        self.empty = Adw.StatusPage(icon_name="image-x-generic-symbolic",
                                    title=_("img_empty_title"),
                                    description=_("img_empty_desc"))

        # Senza un modello: che cosa serve e dove va, con i pulsanti per
        # farlo (specifiche, sezione 3.8: gli stati vuoti hanno un'azione).
        guide = Gtk.Button(label=_("img_guide_button"), halign=Gtk.Align.CENTER)
        guide.add_css_class("suggested-action")
        guide.add_css_class("pill")
        guide.connect("clicked", lambda _b: self.show_guide())
        open_dir = Gtk.Button(label=_("img_open_models_folder"), halign=Gtk.Align.CENTER)
        open_dir.add_css_class("pill")
        open_dir.connect("clicked", lambda _b: self.open_models_folder())
        add_dir = Gtk.Button(label=_("img_add_folder"), halign=Gtk.Align.CENTER)
        add_dir.add_css_class("pill")
        add_dir.connect("clicked", lambda _b: self.add_folder())
        buttons = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12,
                          halign=Gtk.Align.CENTER)
        for w in (guide, open_dir, add_dir):
            buttons.append(w)
        path = Gtk.Label(label=self._shown_path(rd.USER_MODEL_DIR), selectable=True, wrap=True,
                         justify=Gtk.Justification.CENTER)
        path.add_css_class("monospace")
        path.add_css_class("dim-label")
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=18)
        box.append(path)
        box.append(buttons)
        self.setup = Adw.StatusPage(icon_name="folder-download-symbolic",
                                    title=_("img_setup_title"),
                                    description=_("img_setup_desc"), child=box)

        # Generazione in corso: anteprima, passo, barra, Ferma.
        self.preview = Gtk.Picture(can_shrink=True, content_fit=Gtk.ContentFit.CONTAIN,
                                   width_request=160, height_request=160)
        self.preview.update_property([Gtk.AccessibleProperty.LABEL], [_("img_working")])
        self.progress_title = Gtk.Label(label=_("img_working"), xalign=0, wrap=True)
        self.progress_title.add_css_class("heading")
        self.progress_detail = Gtk.Label(xalign=0, wrap=True)
        self.progress_detail.add_css_class("dim-label")
        self.progress_detail.add_css_class("numeric")
        self.progress_bar = Gtk.ProgressBar(hexpand=True)
        stop = Gtk.Button(label=_("stop"), halign=Gtk.Align.START)
        stop.add_css_class("destructive-action")
        stop.add_css_class("pill")
        stop.connect("clicked", lambda _b: self.stop())
        info = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6,
                       valign=Gtk.Align.CENTER, hexpand=True)
        for w in (self.progress_title, self.progress_detail, self.progress_bar, stop):
            info.append(w)
        self.progress_card = Gtk.Box(spacing=18, visible=False, margin_bottom=6)
        self.progress_card.add_css_class("card")
        inner = Gtk.Box(spacing=18, margin_top=12, margin_bottom=12, margin_start=12,
                        margin_end=18, hexpand=True)
        inner.append(self.preview)
        inner.append(info)
        self.progress_card.append(inner)

        self.flow = Gtk.FlowBox(selection_mode=Gtk.SelectionMode.NONE, homogeneous=True,
                                min_children_per_line=1, max_children_per_line=6,
                                row_spacing=12, column_spacing=12,
                                activate_on_single_click=True, valign=Gtk.Align.START)
        self.flow.connect("child-activated", lambda _f, child: self.open_viewer(child.item))
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12, margin_top=18,
                      margin_bottom=18, margin_start=12, margin_end=12)
        box.append(self.progress_card)
        box.append(self.flow)
        self.gallery = Gtk.ScrolledWindow(child=Adw.Clamp(child=box, maximum_size=1200),
                                          vexpand=True,
                                          hscrollbar_policy=Gtk.PolicyType.NEVER)
        self.stack = Gtk.Stack(transition_type=Gtk.StackTransitionType.CROSSFADE)
        self.stack.add_named(self.empty, "empty")
        self.stack.add_named(self.setup, "setup")
        self.stack.add_named(self.gallery, "gallery")

        view = Adw.ToolbarView(content=self.stack)
        view.add_top_bar(self.banner)
        view.add_bottom_bar(self._build_input())
        return view

    def _build_input(self):
        _ = self._
        outer = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6, margin_top=6,
                        margin_bottom=6, margin_start=12, margin_end=12)
        outer.append(self._build_aspect())
        row = Gtk.Box(spacing=6)
        self.input_buf = Gtk.TextBuffer()
        self.input = Gtk.TextView(buffer=self.input_buf, wrap_mode=Gtk.WrapMode.WORD_CHAR,
                                  top_margin=8, bottom_margin=8, left_margin=10,
                                  right_margin=10, accepts_tab=False)
        self.input.update_property([Gtk.AccessibleProperty.LABEL], [_("img_input_label")])
        self.input.add_css_class("rusca-content")
        keys = Gtk.EventControllerKey()
        keys.connect("key-pressed", self._on_key)
        self.input.add_controller(keys)
        self.input_buf.connect("changed", lambda *_a: self.refresh())
        scroller = Gtk.ScrolledWindow(child=self.input, hexpand=True,
                                      propagate_natural_height=True, max_content_height=160,
                                      hscrollbar_policy=Gtk.PolicyType.NEVER)
        scroller.add_css_class("card")
        self.placeholder = Gtk.Label(label=_("img_placeholder"), xalign=0, can_target=False,
                                     margin_start=12)
        self.placeholder.add_css_class("dim-label")
        self.placeholder.add_css_class("rusca-content")
        overlay = Gtk.Overlay(child=scroller, hexpand=True)
        overlay.add_overlay(self.placeholder)
        self.generate_btn = Gtk.Button(label=_("img_generate"), valign=Gtk.Align.END)
        self.generate_btn.add_css_class("suggested-action")
        self.generate_btn.add_css_class("pill")
        self.generate_btn.connect("clicked", lambda _b: self.generate())
        self.stop_btn = Gtk.Button(icon_name="media-playback-stop-symbolic",
                                   tooltip_text=_("stop"), valign=Gtk.Align.END, visible=False)
        self.stop_btn.add_css_class("circular")
        self.stop_btn.add_css_class("destructive-action")
        self.stop_btn.update_property([Gtk.AccessibleProperty.LABEL], [_("stop")])
        self.stop_btn.connect("clicked", lambda _b: self.stop())
        for w in (overlay, self.generate_btn, self.stop_btn):
            row.append(w)
        outer.append(row)
        return Adw.Clamp(child=outer, maximum_size=820)

    def _build_aspect(self):
        """Formato dell'immagine: tre scelte esclusive sopra la descrizione."""
        _ = self._
        current = self.cfg.get("img_aspect", "square")
        if hasattr(Adw, "ToggleGroup"):                    # libadwaita >= 1.7
            group = Adw.ToggleGroup(halign=Gtk.Align.START)
            group.add_css_class("round")
            for name in ASPECT_ORDER:
                group.add(Adw.Toggle(name=name, label=_(f"img_aspect_{name}")))
            group.set_active_name(current if current in ASPECT_ORDER else "square")
            group.connect("notify::active-name",
                          lambda g, _p: self.window._set("img_aspect", g.get_active_name()))
            return group
        box = Gtk.Box(halign=Gtk.Align.START)              # ripiego: bottoni collegati
        box.add_css_class("linked")
        first = None
        for name in ASPECT_ORDER:
            b = Gtk.ToggleButton(label=_(f"img_aspect_{name}"))
            if first:
                b.set_group(first)
            first = first or b
            b.set_active(name == current)
            b.connect("toggled", lambda b, n=name: b.get_active()
                      and self.window._set("img_aspect", n))
            box.append(b)
        return box

    def _build_settings(self):
        """Pagina del pannello laterale quando si vede questa vista."""
        _ = self._
        cfg = self.cfg
        page = Adw.PreferencesPage()

        group = Adw.PreferencesGroup(title=_("img_group_model"))
        self.model_row = Adw.ComboRow(title=_("model"), use_subtitle=False)
        self.model_row.connect("notify::selected", self._on_model_selected)
        group.add(self.model_row)
        add = Adw.ActionRow(title=_("img_add_folder"), subtitle=_("img_add_folder_sub"),
                            activatable=True)
        add.add_suffix(Gtk.Image(icon_name="folder-new-symbolic"))
        add.connect("activated", lambda _r: self.add_folder())
        group.add(add)
        guide = Adw.ActionRow(title=_("img_guide_button"), activatable=True)
        guide.add_suffix(Gtk.Image(icon_name="help-about-symbolic"))
        guide.connect("activated", lambda _r: self.show_guide())
        group.add(guide)
        # Il percorso si vede: la cartella dei modelli per immagini non e'
        # quella dei modelli della chat (~/.local/share/ruscallama/models).
        folder = Adw.ActionRow(title=_("img_open_models_folder"),
                               subtitle=self._shown_path(rd.USER_MODEL_DIR),
                               tooltip_text=_("img_models_folder_hint"), activatable=True)
        folder.add_css_class("property")
        folder.add_suffix(Gtk.Image(icon_name="folder-open-symbolic"))
        folder.connect("activated", lambda _r: self.open_models_folder())
        group.add(folder)
        self.remove_folder_row = Adw.ActionRow(title=_("img_remove_folder"),
                                               subtitle=_("img_remove_folder_sub"),
                                               activatable=True, visible=False)
        self.remove_folder_row.add_suffix(Gtk.Image(icon_name="list-remove-symbolic"))
        self.remove_folder_row.connect("activated", lambda _r: self.remove_folder())
        group.add(self.remove_folder_row)
        page.add(group)

        group = Adw.PreferencesGroup(title=_("img_group_image"))
        quality = Adw.ComboRow(title=_("img_quality"), subtitle=_("img_quality_sub"),
                               model=Gtk.StringList.new([_(f"img_quality_{q}") for q in QUALITIES]))
        quality.set_selected(QUALITIES.index(cfg["img_quality"])
                             if cfg["img_quality"] in QUALITIES else 1)
        quality.connect("notify::selected",
                        lambda r, _p: (self.window._set("img_quality", QUALITIES[r.get_selected()]),
                                       self._show_recommended()))
        group.add(quality)
        count = Adw.SpinRow.new_with_range(1, rd.MAX_COUNT, 1)
        count.set_title(_("img_count"))
        count.set_value(cfg["img_count"])
        count.connect("notify::value", lambda r, _p: self.window._set("img_count",
                                                                      int(r.get_value())))
        group.add(count)
        negative = Adw.EntryRow(title=_("img_negative"), text=cfg["img_negative"])
        negative.connect("changed", lambda r: self.window._set("img_negative", r.get_text()))
        group.add(negative)
        metadata = Adw.SwitchRow(title=_("img_metadata"), subtitle=_("img_metadata_sub"),
                                 active=cfg["img_metadata"])
        metadata.connect("notify::active",
                         lambda r, _p: self.window._set("img_metadata", r.get_active()))
        group.add(metadata)

        advanced = Adw.ExpanderRow(title=_("img_advanced"), subtitle=_("img_advanced_sub"))
        self.steps_row = Adw.SpinRow.new_with_range(0, 150, 1)
        self.steps_row.set_title(_("img_steps"))
        self.steps_row.set_value(cfg["img_steps"])
        self.steps_row.connect("notify::value", lambda r, _p: self._set_advanced(
            "img_steps", int(r.get_value())))
        advanced.add_row(self.steps_row)
        self.cfg_row = Adw.SpinRow.new_with_range(0, 30, 0.5)
        self.cfg_row.set_digits(1)
        self.cfg_row.set_title(_("img_cfg"))
        self.cfg_row.set_subtitle(_("img_cfg_sub"))
        self.cfg_row.set_value(cfg["img_cfg"])
        self.cfg_row.connect("notify::value", lambda r, _p: self._set_advanced(
            "img_cfg", float(r.get_value())))
        advanced.add_row(self.cfg_row)
        self.side_row = Adw.ComboRow(title=_("img_side"), model=Gtk.StringList.new(
            [_("img_auto")] + [f"{s} × {s}" for s in SIDES[1:]]))
        self.side_row.set_selected(SIDES.index(cfg["img_side"]) if cfg["img_side"] in SIDES else 0)
        self.side_row.connect("notify::selected", lambda r, _p: self._set_advanced(
            "img_side", SIDES[r.get_selected()]))
        advanced.add_row(self.side_row)
        samplers = ("",) + rd.SAMPLERS
        sampler = Adw.ComboRow(title=_("img_sampler"), model=Gtk.StringList.new(
            [_("img_auto")] + list(rd.SAMPLERS)))
        sampler.set_selected(samplers.index(cfg["img_sampler"])
                             if cfg["img_sampler"] in samplers else 0)
        sampler.connect("notify::selected", lambda r, _p: self.window._set(
            "img_sampler", samplers[r.get_selected()]))
        advanced.add_row(sampler)
        # Il seme ha fino a 10 cifre: uno Adw.SpinRow si allargherebbe fino
        # a schiacciare il sottotitolo, qui la casella e' larga 8 caratteri.
        seed = Adw.ActionRow(title=_("p_seed"), subtitle=_("img_seed_sub"))
        self.seed_row = Gtk.SpinButton.new_with_range(-1, 2 ** 31 - 1, 1)
        self.seed_row.set_width_chars(8)
        self.seed_row.set_valign(Gtk.Align.CENTER)
        self.seed_row.set_value(cfg["img_seed"])
        self.seed_row.update_property([Gtk.AccessibleProperty.LABEL], [_("p_seed")])
        self.seed_row.connect("value-changed", lambda r: self.window._set(
            "img_seed", int(r.get_value())))
        seed.add_suffix(self.seed_row)
        seed.set_activatable_widget(self.seed_row)
        advanced.add_row(seed)
        group.add(advanced)
        page.add(group)

        group = Adw.PreferencesGroup(title=_("img_group_engine"), description=_("img_engine_desc"))
        gpu = Adw.SwitchRow(title=_("gpu"), subtitle=_("gpu_sub"), active=cfg["img_gpu"])
        group.add(gpu)
        self.device_row = Adw.ComboRow(title=_("gpu_device"), sensitive=cfg["img_gpu"])
        self._fill_devices()
        self.device_row.connect("notify::selected", self._on_device)
        gpu.connect("notify::active", lambda r, _p: (
            self.window._set("img_gpu", r.get_active()),
            self.device_row.set_sensitive(r.get_active())))
        group.add(self.device_row)
        # Il codificatore di testo su un'altra scheda o sul processore: la
        # scheda principale resta libera per il modello di diffusione.
        self.te_row = Adw.ComboRow(title=_("img_te_device"), subtitle=_("img_te_device_sub"),
                                   sensitive=cfg["img_gpu"])
        self._fill_te_devices()
        self.te_row.connect("notify::selected", self._on_te_device)
        gpu.connect("notify::active", lambda r, _p: self.te_row.set_sensitive(r.get_active()))
        group.add(self.te_row)
        threads = Adw.SpinRow.new_with_range(1, max(1, os.cpu_count() or 1), 1)
        threads.set_title(_("threads"))
        threads.set_subtitle(_("threads_sub", n=rd.physical_cores()))
        threads.set_value(min(cfg["img_threads"], os.cpu_count() or 1))
        threads.connect("notify::value", lambda r, _p: self.window._set(
            "img_threads", int(r.get_value())))
        group.add(threads)
        low = Adw.SwitchRow(title=_("img_low_memory"), subtitle=_("img_low_memory_sub"),
                            active=cfg["img_low_memory"])
        low.connect("notify::active", lambda r, _p: self.window._set(
            "img_low_memory", r.get_active()))
        group.add(low)
        page.add(group)
        return page

    def _set_advanced(self, key, value):
        if not self._updating:
            self.window._set(key, value)
        self._show_recommended()

    def _show_recommended(self):
        """Sottotitoli delle impostazioni avanzate: il valore che si usa con
        «0» o «Automatico», per il modello scelto."""
        rec = rd.recommended(self.model) if self.model else None
        if rec is None:
            self.steps_row.set_subtitle(self._("img_auto_sub"))
            return
        steps = rd.recommended_steps(rec, self.cfg["img_quality"])
        self.steps_row.set_subtitle(self._("img_recommended", value=steps))
        self.cfg_row.set_subtitle(self._("img_auto_sub") if rec["cfg"] is None
                                  else self._("img_recommended", value=f"{rec['cfg']:g}"))
        self.side_row.set_subtitle(self._("img_recommended",
                                          value=f"{rec['side']} × {rec['side']}"))

    # ── modelli ───────────────────────────────────────────────────────────
    def _folders(self):
        return [f for f in self.cfg.get("img_folders", []) if isinstance(f, str)]

    # Le cartelle dei modelli si guardano con Gio.FileMonitor, come in
    # RuscaTranscriber e RuscaNarrator: un modello copiato mentre RuscaLLama
    # e' aperto compare da solo. Un modello in piu' file e' una
    # sottocartella, quindi si guardano anche le sottocartelle (un livello:
    # i monitor si rifanno a ogni nuova lettura).
    def _watch_models(self):
        for m in self._monitors:
            m.cancel()
        self._monitors = []
        try:
            rd.ensure_user_model_dir()
        except OSError:
            pass
        dirs = []
        for d in tuple(rd.MODEL_DIRS) + tuple(self._folders()) + rd.CHAT_MODEL_DIRS:
            if not os.path.isdir(d):
                continue
            dirs.append(d)
            if d in rd.CHAT_MODEL_DIRS:
                continue
            try:
                dirs += [e.path for e in os.scandir(d)
                         if e.is_dir() and not e.name.startswith(".")]
            except OSError:
                pass
        for d in dirs:
            try:
                monitor = Gio.File.new_for_path(d).monitor_directory(
                    Gio.FileMonitorFlags.WATCH_MOVES, None)
            except GLib.Error:
                continue
            monitor.connect("changed", self._on_models_changed)
            self._monitors.append(monitor)

    def _on_models_changed(self, _monitor, _file, _other, event):
        # Durante una copia arrivano molti eventi: si rilegge una volta sola,
        # quando la cartella si e' calmata.
        if event in (Gio.FileMonitorEvent.ATTRIBUTE_CHANGED,):
            return
        if self._models_timer:
            GLib.source_remove(self._models_timer)
        self._models_timer = GLib.timeout_add(1500, self._models_timeout)

    def _models_timeout(self):
        self._models_timer = 0
        if not self.generator.running:
            self.scan_models()
        else:                          # a generazione finita
            self._models_timer = GLib.timeout_add(1500, self._models_timeout)
        return False

    def scan_models(self, select=None):
        self.misplaced = rd.misplaced_files()
        self.models = rd.find_models(self._folders())
        self._watch_models()
        keys = [m.key for m in self.models]
        wanted = select or self.cfg["img_model"]
        self._updating = True
        self.model_row.set_model(Gtk.StringList.new(
            [m.name for m in self.models] or [self._("no_model")]))
        self.model_row.set_sensitive(bool(self.models))
        if self.models:
            self.model_row.set_selected(keys.index(wanted) if wanted in keys else 0)
        self._updating = False
        self._on_model_selected(self.model_row, None)

    def _on_model_selected(self, row, _pspec):
        if self._updating:
            return
        i = row.get_selected()
        self.model = self.models[i] if 0 <= i < len(self.models) else None
        key = self.model.key if self.model else ""
        if key != self.cfg["img_model"]:
            self.window._set("img_model", key)
        if self.model is None:
            row.set_subtitle(self._("img_no_model_sub"))
        elif self.model.missing():
            row.set_subtitle(self._("img_incomplete", parts=self._parts(self.model.missing())))
        elif self.model.parts:
            row.set_subtitle(self._("img_kind_parts", n=len(self.model.parts) + 1))
        else:
            row.set_subtitle(self._("img_kind_full"))
        row.set_tooltip_text(self.model.folder or self.model.main if self.model else None)
        self.remove_folder_row.set_visible(self._added_folder() is not None)
        self._show_recommended()
        self.refresh()

    def _added_folder(self):
        """La cartella aggiunta dall'utente che contiene il modello scelto."""
        if self.model is None:
            return None
        for f in self._folders():
            root = os.path.join(os.path.realpath(f), "")
            if os.path.realpath(self.model.main).startswith(root):
                return f
        return None

    def add_folder(self):
        dialog = Gtk.FileDialog(title=self._("img_add_folder_title"))

        def done(d, result):
            try:
                path = d.select_folder_finish(result).get_path()
            except GLib.Error:
                return
            if not path:
                return
            found = rd.scan_folder(path)
            if not found:
                self.window.toasts.add_toast(Adw.Toast(title=GLib.markup_escape_text(
                    self._("img_no_model_in_folder", name=os.path.basename(path)))))
                return
            folders = self._folders()
            if path not in folders:
                folders.append(path)
                self.window._set("img_folders", folders)
            self.scan_models(select=found[0].key)
        dialog.select_folder(self.window, None, done)

    def remove_folder(self):
        folder = self._added_folder()
        if folder is None:
            return
        self.window._set("img_folders", [f for f in self._folders() if f != folder])
        self.scan_models()

    def open_models_folder(self):
        path = rd.ensure_user_model_dir()
        Gtk.FileLauncher.new(Gio.File.new_for_path(path)).launch(self.window, None, None)

    # ── schede grafiche ───────────────────────────────────────────────────
    def _load_devices(self):
        devices = rd.list_devices()
        GLib.idle_add(self._devices_loaded, devices)

    def _devices_loaded(self, devices):
        self.devices = devices
        self._fill_devices()
        self._fill_te_devices()
        return False

    def _fill_te_devices(self):
        """Sulla stessa scheda, sul processore, o su una delle schede."""
        labels = [d["label"] for d in self.devices]
        self._te_choices = ["", "cpu"] + labels
        self._updating = True
        self.te_row.set_model(Gtk.StringList.new(
            [self._("img_te_same"), self._("img_te_cpu")] + labels))
        current = self.cfg["img_te_device"]
        self.te_row.set_selected(self._te_choices.index(current)
                                 if current in self._te_choices else 0)
        self._updating = False

    def _on_te_device(self, row, _pspec):
        if self._updating:
            return
        i = row.get_selected()
        if 0 <= i < len(self._te_choices):
            self.window._set("img_te_device", self._te_choices[i])

    def _fill_devices(self):
        labels = [d["label"] for d in self.devices]
        self._updating = True
        self.device_row.set_model(Gtk.StringList.new([self._("gpu_device_auto")] + labels))
        self.device_row.set_selected(labels.index(self.cfg["img_device"]) + 1
                                     if self.cfg["img_device"] in labels else 0)
        self._updating = False

    def _on_device(self, row, _pspec):
        if self._updating:
            return
        i = row.get_selected()
        self.window._set("img_device",
                         self.devices[i - 1]["label"] if 0 < i <= len(self.devices) else "")

    # ── stato ─────────────────────────────────────────────────────────────
    def _prompt(self):
        return self.input_buf.get_text(self.input_buf.get_start_iter(),
                                       self.input_buf.get_end_iter(), False).strip()

    def refresh(self):
        running = self.generator.running
        self.placeholder.set_visible(self.input_buf.get_char_count() == 0)
        self.generate_btn.set_visible(not running)
        self.stop_btn.set_visible(running)
        missing = self.model.missing() if self.model else []
        self.generate_btn.set_sensitive(bool(self._prompt()) and self.model is not None
                                        and not missing and rd.find_binary() is not None)
        b = self.banner
        self._banner_action = None
        if not rd.find_binary():
            b.set_title(self._("img_banner_no_engine"))
            b.set_button_label(None)
            b.set_revealed(True)
        elif self.misplaced:
            b.set_title(self._("img_misplaced", name=os.path.basename(self.misplaced[0])))
            b.set_button_label(self._("img_open_models_folder"))
            self._banner_action = self.open_models_folder
            b.set_revealed(True)
        elif missing:
            b.set_title(self._("img_banner_incomplete", name=self.model.name,
                               parts=self._parts(missing)))
            b.set_button_label(self._("img_guide_button"))
            self._banner_action = self.show_guide
            b.set_revealed(True)
        else:
            b.set_revealed(False)
        if self.items or running:
            self.stack.set_visible_child_name("gallery")
        else:
            self.stack.set_visible_child_name("setup" if self.model is None else "empty")

    def _on_banner(self, _banner):
        if self._banner_action:
            self._banner_action()

    @staticmethod
    def _shown_path(path):
        home = os.path.expanduser("~")
        return "~" + path[len(home):] if path.startswith(home + os.sep) else path

    def _parts(self, roles):
        names = {"vae": "VAE", "llm": self._("img_part_te"), "t5xxl": "T5-XXL",
                 "clip_l": "CLIP-L", "clip_g": "CLIP-G"}
        return ", ".join(names.get(r, r) for r in roles)

    # ── guida: quali file scaricare e dove ────────────────────────────────
    def show_guide(self):
        _ = self._
        page = Adw.PreferencesPage(description=_("img_guide_intro"))
        intro = Adw.PreferencesGroup(description=_("img_guide_versions"))
        page.add(intro)
        labels = {"model": _("img_part_model"), "llm": _("img_part_te"), "vae": "VAE"}
        for entry in rd.GUIDE:
            group = Adw.PreferencesGroup(title=entry["name"], description=_(entry["desc"]))
            for role, hint, url in entry["files"]:
                row = Adw.ActionRow(title=labels[role], subtitle=hint, activatable=True,
                                    tooltip_text=url)
                row.add_css_class("property")
                row.add_suffix(Gtk.Image(icon_name="web-browser-symbolic",
                                         tooltip_text=_("img_open_link")))
                row.connect("activated", lambda _r, u=url: Gtk.UriLauncher.new(u).launch(
                    self.window, None, None))
                group.add(row)
            target = os.path.join(rd.USER_MODEL_DIR, entry["name"])
            row = Adw.ActionRow(title=_("img_create_folder"), subtitle=self._shown_path(target),
                                activatable=True)
            row.add_suffix(Gtk.Image(icon_name="folder-new-symbolic"))
            row.connect("activated", lambda _r, t=target: self._create_model_folder(t))
            group.add(row)
            page.add(group)
        view = Adw.ToolbarView(content=page)
        view.add_top_bar(Adw.HeaderBar())
        Adw.Dialog(title=_("img_guide_title"), content_width=620, content_height=720,
                   child=view).present(self.window)

    def _create_model_folder(self, path):
        """Crea la cartella del modello con il nome giusto e la apre: li'
        dentro vanno i tre file."""
        try:
            os.makedirs(path, exist_ok=True)
        except OSError as e:
            self.window._show_error(self._("save_error"), str(e))
            return
        Gtk.FileLauncher.new(Gio.File.new_for_path(path)).launch(self.window, None, None)

    def _on_key(self, _ctrl, keyval, _code, state):
        if keyval in (Gdk.KEY_Return, Gdk.KEY_KP_Enter) and \
                not state & Gdk.ModifierType.SHIFT_MASK:
            self.generate()
            return True
        return False

    def set_prompt(self, text):
        self.input_buf.set_text(text.strip())
        self.input.grab_focus()

    def focus(self):
        self.input.grab_focus()

    # ── generazione ───────────────────────────────────────────────────────
    def generate(self):
        if self.generator.running or not self.generate_btn.get_sensitive():
            return
        job = rd.make_job(self.model, self._prompt(), self.cfg)
        try:
            self.generator.start(self.model, job, threads=self.cfg["img_threads"],
                                 gpu=self.cfg["img_gpu"], gpu_device=self.cfg["img_device"],
                                 low_memory=self.cfg["img_low_memory"],
                                 metadata=self.cfg["img_metadata"],
                                 devices=self.devices or None,
                                 te_device=self.cfg["img_te_device"])
        except rd.DiffusionError as e:
            self.window._show_error(self._(e.key), e.detail)
            return
        self._job = job
        self._t_start = time.monotonic()
        self._pulsing = True
        self.log_lines.clear()
        self.preview.set_paintable(None)
        self.progress_title.set_label(self._("img_working"))
        self.progress_detail.set_label(self._("img_loading"))
        self.progress_bar.set_fraction(0)
        self.progress_card.set_visible(True)
        GLib.timeout_add(150, self._pulse)
        self.refresh()
        self.gallery.get_vadjustment().set_value(0)

    def _pulse(self):
        """Barra che si muove finche' non si conoscono i passi."""
        if not self.generator.running:
            return False
        if self._pulsing:
            self.progress_bar.pulse()
        return True

    def stop(self):
        if self.generator.running:
            self.generator.cancel()

    def _on_progress(self, stage, step, steps):
        if stage == "sample" and steps:
            self._pulsing = False
            self.progress_detail.set_label(self._("img_step", n=step, total=steps))
            self.progress_bar.set_fraction(min(1.0, step / steps))
        elif stage == "decode":
            self._pulsing = True
            self.progress_detail.set_label(self._("img_decoding"))
        else:
            self._pulsing = True
            self.progress_detail.set_label(self._("img_loading"))

    def _on_preview(self, data):
        try:
            self.preview.set_paintable(Gdk.Texture.new_from_bytes(GLib.Bytes.new(data)))
        except GLib.Error:
            pass

    def _on_log(self, line):
        self.log_lines.append(line)
        del self.log_lines[:-2000]

    def _on_done(self, error, images, job):
        self._pulsing = True
        self.progress_card.set_visible(False)
        name = self.model.name if self.model else ""
        if error == "cancelled":
            pass
        elif error is not None:
            toast = Adw.Toast(title=GLib.markup_escape_text(self._(error.key)), timeout=8,
                              button_label=self._("img_log"), action_name="win.show-image-log")
            self.window.toasts.add_toast(toast)
        else:
            for i, path in enumerate(images):
                self._add_item(_Item(path, job, i, name))
        self.refresh()
        self.input.grab_focus()

    # ── galleria ──────────────────────────────────────────────────────────
    def _add_item(self, item, position=0):
        pic = Gtk.Picture(can_shrink=True, content_fit=Gtk.ContentFit.COVER,
                          width_request=TILE, height_request=TILE)
        try:
            pic.set_paintable(Gdk.Texture.new_from_filename(item.path))
        except GLib.Error:
            return
        pic.update_property([Gtk.AccessibleProperty.LABEL], [item.prompt])
        frame = Gtk.Box(overflow=Gtk.Overflow.HIDDEN, tooltip_text=item.prompt)
        frame.add_css_class("card")
        frame.append(pic)
        more = Gtk.MenuButton(icon_name="view-more-symbolic", menu_model=self._item_menu(item),
                              tooltip_text=self._("more_actions"), halign=Gtk.Align.END,
                              valign=Gtk.Align.START, margin_top=6, margin_end=6)
        more.add_css_class("osd")
        more.add_css_class("circular")
        more.update_property([Gtk.AccessibleProperty.LABEL], [self._("more_actions")])
        # La miniatura resta quadrata anche quando la colonna e' piu' larga.
        overlay = Gtk.Overlay(child=frame, halign=Gtk.Align.CENTER, valign=Gtk.Align.START)
        overlay.add_overlay(more)
        child = Gtk.FlowBoxChild(child=overlay)
        child.item = item
        item.child = child
        self.flow.insert(child, position)
        if item not in self.items:
            self.items.insert(position, item)

    def open_viewer(self, item):
        _ = self._
        pic = Gtk.Picture(can_shrink=True, content_fit=Gtk.ContentFit.CONTAIN, vexpand=True)
        try:
            pic.set_paintable(Gdk.Texture.new_from_filename(item.path))
        except GLib.Error:
            return
        pic.update_property([Gtk.AccessibleProperty.LABEL], [item.prompt])
        prompt = Gtk.Label(label=item.prompt, wrap=True, xalign=0, selectable=True)
        info = Gtk.Label(label=_("img_info", w=item.width, h=item.height, steps=item.steps,
                                 seed=item.seed) + (f" · {item.model}" if item.model else ""),
                         wrap=True, xalign=0)
        info.add_css_class("dim-label")
        info.add_css_class("caption")
        info.add_css_class("numeric")
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12, margin_top=6,
                      margin_bottom=18, margin_start=18, margin_end=18)
        for w in (pic, prompt, info):
            box.append(w)
        header = Adw.HeaderBar()
        save = Gtk.Button(label=_("img_save"), action_name="img.save",
                          action_target=GLib.Variant.new_string(item.id))
        save.add_css_class("suggested-action")
        header.pack_start(save)
        header.pack_end(Gtk.MenuButton(icon_name="view-more-symbolic",
                                       menu_model=self._item_menu(item),
                                       tooltip_text=_("more_actions")))
        view = Adw.ToolbarView(content=box)
        view.add_top_bar(header)
        dialog = Adw.Dialog(title=_("img_viewer_title"), content_width=900,
                            content_height=760, child=view)
        dialog.insert_action_group("img", self._actions)
        self._dialog = dialog
        dialog.connect("closed", lambda _d: setattr(self, "_dialog", None))
        dialog.present(self.window)

    def _close_viewer(self):
        dialog = getattr(self, "_dialog", None)
        if dialog is not None:
            dialog.close()

    def save(self, item):
        stamp = time.strftime("%Y-%m-%d-%H%M")
        dialog = Gtk.FileDialog(title=self._("save_title"),
                                initial_name=f"ruscallama-{stamp}-{item.seed}.png")
        filt = Gtk.FileFilter()
        filt.set_name(self._("img_png_files"))
        filt.add_mime_type("image/png")
        store = Gio.ListStore.new(Gtk.FileFilter)
        store.append(filt)
        dialog.set_filters(store)
        pictures = GLib.get_user_special_dir(GLib.UserDirectory.DIRECTORY_PICTURES)
        if pictures and os.path.isdir(pictures):
            dialog.set_initial_folder(Gio.File.new_for_path(pictures))

        def done(d, result):
            try:
                path = d.save_finish(result).get_path()
            except GLib.Error:
                return
            try:
                with open(item.path, "rb") as src, open(path, "wb") as dst:
                    dst.write(src.read())
            except OSError as e:
                self.window._show_error(self._("save_error"), str(e))
                return
            item.saved = True
            self.window.toasts.add_toast(Adw.Toast(title=GLib.markup_escape_text(
                self._("saved", name=os.path.basename(path)))))
        dialog.save(self.window, None, done)

    def copy(self, item):
        try:
            texture = Gdk.Texture.new_from_filename(item.path)
        except GLib.Error:
            return
        self.window.get_clipboard().set(texture)
        self.window.toasts.add_toast(Adw.Toast(title=self._("copied"), timeout=2))

    def to_chat(self, item):
        self._close_viewer()
        self.window.attach_image(item.path)

    def reuse(self, item):
        """Stesso seme e stessa descrizione: cambiando poco la descrizione,
        l'immagine nuova somiglia a questa."""
        self._close_viewer()
        self.seed_row.set_value(item.seed)
        self.set_prompt(item.prompt)
        self.window.toasts.add_toast(Adw.Toast(title=self._("img_seed_set", seed=item.seed)))

    def remove(self, item):
        self._close_viewer()
        if item not in self.items:
            return
        position = self.items.index(item)
        self.items.remove(item)
        self.flow.remove(item.child)
        self.refresh()
        toast = Adw.Toast(title=self._("img_removed"), button_label=self._("undo"))
        undone = []

        def undo(_t):
            undone.append(True)
            self._add_item(item, min(position, len(self.items)))
            self.refresh()

        def dismissed(_t):
            if not undone:
                try:
                    os.unlink(item.path)
                except OSError:
                    pass
        toast.connect("button-clicked", undo)
        toast.connect("dismissed", dismissed)
        self.window.toasts.add_toast(toast)

    # ── chiusura ──────────────────────────────────────────────────────────
    def unsaved(self):
        return [i for i in self.items if not i.saved]

    def shutdown(self):
        """Ferma il motore e cancella prompt e immagini dalla cache."""
        for m in self._monitors:
            m.cancel()
        self._monitors = []
        self.generator.cancel()
        self.generator.wait(10)
        rd.clean_work_dir()
