"""RuscaLinux OS Tools — rusca_liveblocks.py — 1.99.3 — GPL-3.0

Tabelle e formule mostrate «rese» dentro un Gtk.TextView mentre si scrive,
senza toccare il testo del documento.

Come funziona, per ogni blocco (una tabella, una formula su riga propria, una
riga con formule nella frase) lontano dal cursore:

  1. il sorgente del blocco viene nascosto con un tag invisibile, tranne il
     ritorno a capo dell'ultima riga, che resta come riga vuota visibile;
  2. a quella riga un tag dà uno spazio sopra (pixels-above-lines) alto
     quanto la resa;
  3. la resa (un widget) è un «overlay» del TextView, messo in quello spazio
     e spostato quando l'impaginazione cambia.

Nel buffer ci sono solo tag: il testo salvato, l'annulla, il segno di
modifica e le posizioni restano quelli di sempre. Quando il cursore (o la
selezione) entra nel blocco, il sorgente ricompare e si modifica come prima;
un clic sulla resa porta il cursore all'inizio del blocco.

Oggi RuscaWriter ne usa i riquadri delle immagini (image_widget) per
l'anteprima: gli editor mostrano il Markdown sorgente, perché la resa
sovrapposta mentre si scrive si è rivelata instabile con i clic e le
selezioni.
"""

import gi

gi.require_version("Gtk", "4.0")
from gi.repository import GLib, Gtk, Pango  # noqa: E402

__all__ = ["LiveBlocks", "table_widget", "math_widget", "text_widget", "image_widget"]


def _label(markup, xalign=0.0):
    label = Gtk.Label(wrap=True, wrap_mode=Pango.WrapMode.WORD_CHAR, xalign=xalign,
                      use_markup=True)
    try:
        Pango.parse_markup(markup, -1, "\0")
        label.set_markup(markup)
    except GLib.Error:
        label.set_use_markup(False)
        label.set_text(GLib.markup_escape_text(markup))
    return label


def table_widget(aligns, header, rows):
    """Tabella: griglia con celle che vanno a capo, intestazione in grassetto,
    righe separate come nelle liste di GNOME. Celle già in markup Pango."""
    import re
    grid = Gtk.Grid(hexpand=True)
    xalign = {"right": 1.0, "center": 0.5}
    for r, cells in enumerate([header] + rows):
        for c, cell in enumerate(cells):
            label = _label(f"<b>{cell}</b>" if r == 0 else cell,
                           xalign.get(aligns[c] if c < len(aligns) else "left", 0.0))
            label.set_hexpand(True)
            label.set_valign(Gtk.Align.START)
            label.set_max_width_chars(min(max(len(re.sub(r"<[^>]+>", "", cell)), 4), 50))
            for side in ("start", "end"):
                getattr(label, f"set_margin_{side}")(12)
            label.set_margin_top(6)
            label.set_margin_bottom(6)
            grid.attach(label, c, 2 * r, 1, 1)
        if r < len(rows):
            grid.attach(Gtk.Separator(), 0, 2 * r + 1, len(header), 1)
    card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
    card.add_css_class("card")
    card.append(grid)
    return card


def math_widget(markup):
    """Formula su riga propria: centrata e un po' più grande."""
    label = _label(f'<span size="120%">{markup}</span>', 0.5)
    label.set_justify(Gtk.Justification.CENTER)
    label.set_margin_top(4)
    label.set_margin_bottom(4)
    return label


def image_widget(texture, caption_markup, max_width, missing_markup=None):
    """Immagine: figura centrata, ridotta alla larghezza del testo e mai
    ingrandita, con la didascalia sotto. Se texture è None, un riquadro con
    il messaggio missing_markup (immagine assente o non leggibile)."""
    box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
    box.set_margin_top(6)
    box.set_margin_bottom(6)
    if texture is None:
        box.add_css_class("card")
        icon = Gtk.Image.new_from_icon_name("image-missing-symbolic")
        icon.set_pixel_size(32)
        icon.set_margin_top(12)
        box.append(icon)
        msg = _label(missing_markup or "", 0.5)
        msg.set_justify(Gtk.Justification.CENTER)
        msg.set_margin_start(12)
        msg.set_margin_end(12)
        msg.set_margin_bottom(12)
        box.append(msg)
        return box
    tw, th = texture.get_width(), texture.get_height()
    w = max(1, min(tw, int(max_width)))
    h = max(1, int(th * w / max(1, tw)))
    picture = Gtk.Picture.new_for_paintable(texture)
    picture.set_can_shrink(True)
    picture.set_size_request(w, h)
    picture.set_halign(Gtk.Align.CENTER)
    box.append(picture)
    if caption_markup:
        cap = _label(f"<i>{caption_markup}</i>", 0.5)
        cap.set_justify(Gtk.Justification.CENTER)
        box.append(cap)
    return box


def text_widget(markup):
    """Riga di testo con formule nella frase, già in markup Pango."""
    return _label(markup)


class LiveBlocks:
    """Gestisce i blocchi resi di un TextView. make_widget(tipo, dati) crea
    la resa; il programma la costruisce con i propri colori e caratteri."""

    def __init__(self, view, make_widget, relayout):
        """relayout(): chiede al programma di ricalcolare i blocchi (e quindi
        di chiamare update) quando la larghezza del testo cambia."""
        self.view = view
        self.buf = view.get_buffer()
        self.make_widget = make_widget
        self.relayout = relayout
        self._hadj = None
        self.hide_tag = self.buf.create_tag(None, invisible=True)
        self._shown = {}        # chiave -> [contenitore, tag dello spazio, altezza, blocco]
        # GTK non sa staccare un figlio «overlay» da un TextView (remove()
        # lo lascia al suo posto): i contenitori si creano una volta sola, si
        # riusano cambiandone il contenuto e si nascondono quando non servono.
        self._free = []
        # EN/IT: overlay coordinates. GTK 4.20 moves overlay children with the
        # scrolling (buffer coordinates, as documented); GTK 4.14 leaves them
        # where they are (window coordinates). The first scroll measures
        # which one this GTK does; until then, a guess by version.
        # Coordinate degli overlay: GTK 4.20 li sposta con lo scorrimento
        # (coordinate del buffer, come da documentazione); GTK 4.14 li lascia
        # fermi (coordinate della finestra). Il primo scorrimento misura
        # come si comporta questo GTK; fino ad allora, ipotesi per versione.
        self._window_coords = (Gtk.get_major_version(), Gtk.get_minor_version()) < (4, 16)
        self._mode_known = False
        self._probe = None      # (widget, y reale, scorrimento) dopo l'ultima posa
        self._vadj = None
        self._place_id = 0
        self._width = 0
        view.connect("notify::left-margin", self._on_geometry)
        view.connect("notify::right-margin", self._on_geometry)

    # --- dati ---------------------------------------------------------------
    def text_width(self):
        v = self.view
        return max(120, v.get_width() - v.get_left_margin() - v.get_right_margin() - 2)

    def _on_geometry(self, *_a):
        if self._shown and abs(self.text_width() - self._width) > 2:
            self.relayout()

    def clear(self):
        b, e = self.buf.get_bounds()
        self.buf.remove_tag(self.hide_tag, b, e)
        for key in list(self._shown):
            self._drop(key)

    def _drop(self, key):
        holder, space, _h, _blk = self._shown.pop(key)
        b, e = self.buf.get_bounds()
        self.buf.remove_tag(space, b, e)
        self.buf.get_tag_table().remove(space)
        child = holder.get_first_child()
        if child is not None:
            holder.remove(child)
        holder.set_visible(False)
        self._free.append(holder)

    def _holder(self):
        if self._free:
            holder = self._free.pop()
        else:
            holder = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
            self.view.add_overlay(holder, 0, 0)
        holder.set_visible(True)
        return holder

    # --- aggiornamento --------------------------------------------------------
    def update(self, blocks, cursor, selection=None):
        """blocks: lista di (inizio, fine, ultima_riga, tipo, dati), con
        inizio = offset del primo carattere, fine = offset della fine
        dell'ultima riga (prima del suo a capo), ultima_riga = offset
        dell'inizio dell'ultima riga. I blocchi che contengono il cursore o
        toccano la selezione restano sorgente."""
        buf = self.buf
        hadj = self.view.get_hadjustment()
        if hadj is not None and hadj is not self._hadj:
            self._hadj = hadj               # la finestra cambia larghezza
            hadj.connect("notify::page-size", self._on_geometry)
            hadj.connect("value-changed", self._on_scroll)
        vadj = self.view.get_vadjustment()
        if vadj is not None and vadj is not self._vadj:
            self._vadj = vadj
            vadj.connect("value-changed", self._on_scroll)
        b, e = buf.get_bounds()
        buf.remove_tag(self.hide_tag, b, e)
        if self.view.get_width() < 50:          # vista non ancora disposta
            for key in list(self._shown):
                self._drop(key)
            GLib.timeout_add(100, lambda: (self.relayout(), False)[1])
            return
        width = self.text_width()
        if abs(width - self._width) > 2:
            for key in list(self._shown):
                self._drop(key)
            self._width = width
        keep = set()
        for start, end, last, kind, data in blocks:
            if start <= cursor <= end:
                continue
            if selection and not (selection[1] < start or selection[0] > end):
                continue
            key = (kind, repr(data), start, end)
            keep.add(key)
            if key not in self._shown:
                for old in [k for k in self._shown if k[2] == start or k[3] == end]:
                    self._drop(old)
                widget = self.make_widget(kind, data)
                widget.set_size_request(width, -1)
                click = Gtk.GestureClick()
                click.connect("released", self._on_click, key)
                widget.add_controller(click)
                widget.set_cursor_from_name("text")
                # prima si aggancia, poi si misura: così la resa eredita il
                # carattere dell'editor e l'altezza è quella vera
                holder = self._holder()
                holder.append(widget)
                _m, nat, _b1, _b2 = widget.measure(Gtk.Orientation.VERTICAL, width)
                space = buf.create_tag(None, pixels_above_lines=max(1, nat))
                self._shown[key] = [holder, space, nat, (start, end, last)]
            _holder, space, nat, _blk = self._shown[key]
            if end > start:
                buf.apply_tag(self.hide_tag, buf.get_iter_at_offset(start),
                              buf.get_iter_at_offset(end))
            last_it = buf.get_iter_at_offset(last)
            end_it = buf.get_iter_at_offset(end)
            end_it.forward_char()
            buf.apply_tag(space, last_it, end_it)
        for key in [k for k in self._shown if k not in keep]:
            self._drop(key)
        self._schedule_place()

    def _on_click(self, _gesture, _n, _x, _y, key):
        item = self._shown.get(key)
        if item is None:
            return
        self.buf.place_cursor(self.buf.get_iter_at_offset(item[3][0]))
        self.view.grab_focus()

    # --- scorrimento ----------------------------------------------------------
    def _offsets(self):
        h = self._hadj.get_value() if self._hadj is not None else 0.0
        v = self._vadj.get_value() if self._vadj is not None else 0.0
        return h, v

    def _on_scroll(self, *_a):
        if not self._shown:
            return
        if self._mode_known:
            if self._window_coords:
                self._schedule_place()
            return
        # misura dopo che GTK ha ridisposto i figli
        GLib.timeout_add(40, self._measure_mode)

    def _measure_mode(self):
        if self._mode_known or self._probe is None:
            return False
        widget, y0, v0 = self._probe
        if widget.get_parent() is None or not widget.get_visible():
            return False
        _h, v1 = self._offsets()
        if abs(v1 - v0) < 3:
            return False
        point = widget.translate_coordinates(self.view, 0, 0)
        y1 = point[-1]
        moved = y1 - y0
        if abs(moved + (v1 - v0)) <= 3:          # segue lo scorrimento
            self._window_coords, self._mode_known = False, True
        elif abs(moved) <= 3:                    # resta fermo
            self._window_coords, self._mode_known = True, True
            self._schedule_place()
        return False

    # --- posizione ------------------------------------------------------------
    def _schedule_place(self):
        if not self._place_id:
            # dopo l'impaginazione del TextView (priorità più bassa)
            self._place_id = GLib.timeout_add(30, self._place)

    def _place(self):
        self._place_id = 0
        again = False
        last_holder = None
        for key, item in self._shown.items():
            holder, space, nat, (start, _end, last) = item
            it = self.buf.get_iter_at_offset(last)
            y, h = self.view.get_line_yrange(it)
            # la riga vuota visibile ha una sua altezza: lo spazio sopra si
            # riduce di quella, così resa e riga occupano insieme 'nat'
            line_h = h - space.props.pixels_above_lines
            want = max(1, nat - max(0, line_h))
            if line_h > 0 and abs(space.props.pixels_above_lines - want) > 1:
                space.props.pixels_above_lines = want
                again = True
                continue
            hoff, voff = self._offsets() if self._window_coords else (0.0, 0.0)
            self.view.move_overlay(holder, int(self.view.get_left_margin() - hoff), int(y - voff))
            last_holder = holder
        if again:
            self._schedule_place()
        elif last_holder is not None and not self._mode_known:
            # campione per il primo scorrimento (vedi _measure_mode)
            GLib.timeout_add(40, self._take_probe, last_holder)
        return False

    def _take_probe(self, holder):
        if holder.get_parent() is not None and holder.get_visible():
            point = holder.translate_coordinates(self.view, 0, 0)
            self._probe = (holder, point[-1], self._offsets()[1])
        return False
