#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# RuscaWriter — three-column writing editor for non-fiction
# Copyright (C) 2026  Nunzio Curcuruto
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.

"""
EN: GUI tests for formatting: the "Format" button, its menu, the
    right-click menu, the shortcuts (Ctrl+B, Ctrl+I, Ctrl+2...), undo in one
    step, and renaming a chapter whose title is written in the text. They
    open the real window.
IT: Test dell'interfaccia per la formattazione: il pulsante «Formato», il
    suo menu, il menu del tasto destro, le scorciatoie (Ctrl+B, Ctrl+I,
    Ctrl+2...), l'annullamento in un passo solo, e il cambio di nome di un
    capitolo che ha il titolo scritto nel testo. Aprono la finestra vera.

Serve GTK 4 e uno schermo. Senza schermo si usa Xvfb:
    xvfb-run -a python3 tests/test_format_gui.py
"""
import os
import sys
import json
import shutil
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, ".."))
sys.path.insert(0, os.path.join(ROOT, "src"))

# configurazione e dati in una cartella usa e getta: il test non deve
# toccare le impostazioni di chi lo esegue
TMP = tempfile.mkdtemp(prefix="rw-format-")
os.environ["XDG_CONFIG_HOME"] = os.path.join(TMP, "config")
os.environ["XDG_DATA_HOME"] = os.path.join(TMP, "data")
os.environ["XDG_CACHE_HOME"] = os.path.join(TMP, "cache")
os.environ.setdefault("GSETTINGS_BACKEND", "memory")
for _var in ("LC_ALL", "LC_MESSAGES", "LANG", "LANGUAGE"):
    os.environ[_var] = "it_IT.UTF-8" if _var != "LANGUAGE" else "it"
os.makedirs(os.path.join(TMP, "config", "ruscawriter"))
with open(os.path.join(TMP, "config", "ruscawriter", "settings.json"),
          "w", encoding="utf-8") as f:
    json.dump({"ui_lang": "it", "theme": "light"}, f)

try:
    import gi
    gi.require_version("Gtk", "4.0")
    from gi.repository import Gtk, GLib
except Exception as exc:                      # pragma: no cover
    print(f"GTK 4 non disponibile, test saltati: {exc}")
    sys.exit(0)

from ruscawriter import editor as rw_editor
from ruscawriter.model import Chapter

PASSED = 0
FAILED = 0


def check(name, cond):
    global PASSED, FAILED
    if cond:
        PASSED += 1
        print(f"  ok  {name}")
    else:
        FAILED += 1
        print(f"  FAIL {name}")


def pump(ms=150):
    """Lascia lavorare GTK per un momento."""
    ctx = GLib.MainContext.default()
    fine = GLib.get_monotonic_time() + ms * 1000
    while GLib.get_monotonic_time() < fine:
        ctx.iteration(False)


def text_of(win):
    buf = win.text_buffer
    return buf.get_text(buf.get_start_iter(), buf.get_end_iter(), True)


def select(win, a, b):
    buf = win.text_buffer
    buf.select_range(buf.get_iter_at_offset(a), buf.get_iter_at_offset(b))


def selected(win):
    buf = win.text_buffer
    if not buf.get_has_selection():
        return ""
    s, e = buf.get_selection_bounds()
    return buf.get_text(s, e, True)


def menu_actions(model):
    """Tutte le azioni di un Gio.MenuModel, sottomenu e sezioni compresi."""
    out = []
    for i in range(model.get_n_items()):
        act = model.get_item_attribute_value(i, "action", None)
        if act is not None:
            out.append(act.get_string())
        for link in ("section", "submenu"):
            sub = model.get_item_link(i, link)
            if sub is not None:
                out.extend(menu_actions(sub))
    return out


def run(win, name):
    """Attiva un'azione della finestra come fanno menu e tasti."""
    win.lookup_action(name).activate(None)
    pump(30)


def open_chapter(win, text, custom_title=""):
    p = win.project
    p.chapters = [p.chapters[0] if p.chapters and p.chapters[0].is_cover
                  else Chapter(0, "COPERTINA", is_cover=True),
                  Chapter(1, text, "", custom_title=custom_title)]
    p._renumber()
    win.current = None
    win._refresh_chapter_list(1)
    pump()
    return p.chapters[1]


def run_checks(win, app):
    print("\n== Pulsante e menu «Formato» ==")
    b = getattr(win, "format_button", None)
    check("c'è il pulsante Formato nella barra", isinstance(b, Gtk.MenuButton))
    check("ha un nome leggibile (suggerimento)",
          b is not None and b.get_tooltip_text() == "Formato")
    acts = menu_actions(b.get_menu_model()) if b else []
    for name, _key, _acc in rw_editor.RuscaWriterWindow.FORMAT_ACTIONS:
        check(f"il menu Formato ha {name}", "win." + name in acts)
        check(f"l'azione {name} esiste", win.lookup_action(name) is not None)
    check("il menu Formato offre il titolo del capitolo (Rinomina)",
          "win.rename" in acts)
    check("e l'immagine", "win.insert_image" in acts)
    check("niente barrato né evidenziato: il libro non li stampa",
          not any("strike" in a or "mark" in a or "highlight" in a for a in acts))
    main_acts = menu_actions(win._build_menu_model())
    check("il menu principale ha il sottomenu Formato",
          "win.fmt_bold" in main_acts and "win.fmt_section" in main_acts)

    print("\n== Scorciatoie ==")
    def norm(accs):
        return [Gtk.accelerator_name(*Gtk.accelerator_parse(a)[1:]) for a in accs]

    accels = {name: norm(app.get_accels_for_action("win." + name))
              for name in ("fmt_bold", "fmt_italic", "fmt_section",
                           "fmt_subsection", "fmt_paragraph", "fmt_footnote",
                           "import_chapters")}
    check("Ctrl+B è il grassetto", accels["fmt_bold"] == norm(["<Control>b"]))
    check("Ctrl+I è il corsivo", accels["fmt_italic"] == norm(["<Control>i"]))
    check("Ctrl+2 / Ctrl+3: sezione e sottosezione",
          accels["fmt_section"] == norm(["<Control>2"])
          and accels["fmt_subsection"] == norm(["<Control>3"]))
    check("Ctrl+0 resta la dimensione del testo (specifiche, 3.9)",
          accels["fmt_paragraph"] == []
          and norm(["<Control>0"])[0] in norm(app.get_accels_for_action("win.font_reset")))
    win.on_font_increase()
    win.on_font_increase()
    win.lookup_action("font_reset").activate(None)
    check("Ctrl+0 riporta la dimensione predefinita",
          win.font_size == rw_editor.DEFAULT_FONT_SIZE)
    check("Ctrl+Alt+F è la nota", accels["fmt_footnote"] == norm(["<Control><Alt>f"]))
    check("Importa capitoli lascia Ctrl+I e va su Ctrl+Maiusc+O",
          accels["import_chapters"] == norm(["<Control><Shift>o"]))
    used = {}
    for name in win.list_actions():
        for acc in app.get_accels_for_action("win." + name):
            used.setdefault(acc, []).append(name)
    doppie = {k: v for k, v in used.items() if len(v) > 1}
    check("nessuna scorciatoia assegnata a due comandi", doppie == {})

    print("\n== Grassetto e corsivo ==")
    open_chapter(win, "# Il giardino\n\nC'era una volta un giardino.")
    t = text_of(win)
    a = t.index("giardino.")
    select(win, a, a + len("giardino"))
    run(win, "fmt_bold")
    check("Ctrl+B mette il grassetto", "un **giardino**." in text_of(win))
    check("la selezione resta sulla parola", selected(win) == "giardino")
    check("il capitolo si aggiorna", "**giardino**" in win.current.text)
    run(win, "fmt_bold")
    check("di nuovo Ctrl+B lo toglie", text_of(win).endswith("un giardino."))
    # senza selezione: la parola sotto il cursore
    buf = win.text_buffer
    t = text_of(win)
    buf.place_cursor(buf.get_iter_at_offset(t.index("volta") + 2))
    run(win, "fmt_italic")
    check("Ctrl+I senza selezione: la parola sotto il cursore",
          "una *volta* un" in text_of(win))

    print("\n== Un passo solo per annullare ==")
    before = text_of(win)
    select(win, 0, len(before))
    run(win, "fmt_bullets")
    changed = text_of(win)
    check("elenco puntato su più righe", changed != before and "- " in changed)
    if hasattr(buf, "undo") and buf.get_can_undo():
        buf.undo()
        pump()
        check("Ctrl+Z annulla il comando in un passo solo", text_of(win) == before)
    else:
        print("     (annullamento non disponibile in questo GTK: salto)")

    print("\n== Titoli e blocchi ==")
    open_chapter(win, "Testo\nUna sezione\nAltro testo")
    t = text_of(win)
    buf.place_cursor(buf.get_iter_at_offset(t.index("sezione")))
    run(win, "fmt_section")
    check("Ctrl+2: la riga diventa una sezione (##)",
          "\n## Una sezione\n" in text_of(win))
    run(win, "fmt_section")
    check("di nuovo Ctrl+2: torna testo normale",
          text_of(win) == "Testo\nUna sezione\nAltro testo")
    run(win, "fmt_subsection")
    check("Ctrl+3: sottosezione (###)", "\n### Una sezione\n" in text_of(win))
    run(win, "fmt_paragraph")
    check("Testo normale toglie il titolo", text_of(win) == "Testo\nUna sezione\nAltro testo")

    print("\n== Note e separatori ==")
    open_chapter(win, "Una frase.")
    buf.place_cursor(buf.get_end_iter())
    run(win, "fmt_footnote")
    check("la nota: richiamo e definizione in fondo",
          text_of(win) == "Una frase.[^1]\n\n[^1]: ")
    check("il cursore è pronto per scrivere la nota",
          buf.get_iter_at_mark(buf.get_insert()).get_offset() == len(text_of(win)))
    open_chapter(win, "Prima scena.\nSeconda riga.")
    buf.place_cursor(buf.get_iter_at_offset(3))
    run(win, "fmt_break")
    check("separatore di scena su una riga sua",
          text_of(win) == "Prima scena.\n\n* * *\n\nSeconda riga.")

    print("\n== Rinominare un capitolo ==")
    ch = open_chapter(win, "# Vecchio titolo\n\nTesto.")
    asked = {}

    def fake_ask(title, prompt, initial, on_ok):
        asked["initial"] = initial
        on_ok(asked["answer"])
    win._ask_text = fake_ask
    asked["answer"] = "Nuovo titolo"
    win.on_rename_chapter()
    pump()
    check("il dialogo propone il titolo attuale", asked.get("initial") == "Vecchio titolo")
    check("il titolo scritto nel testo cambia", text_of(win).startswith("# Nuovo titolo\n"))
    check("e il nome nell'indice è lo stesso, senza un secondo titolo",
          ch.custom_title == "" and ch.title_with_fallback() == "Nuovo titolo")
    check("la lista dei capitoli si aggiorna",
          win.list_store.get_string(0) == "Nuovo titolo")
    ch = open_chapter(win, "Testo senza titolo scritto.")
    asked["answer"] = "Un nome"
    win.on_rename_chapter()
    pump()
    check("senza titolo scritto: il nome va nell'indice, il testo non cambia",
          ch.custom_title == "Un nome" and text_of(win) == "Testo senza titolo scritto.")

    print("\n== Anteprima ==")
    open_chapter(win, "# Capitolo\n\n## Sezione\n\ntesto")
    win._toggle_preview(whole=False)
    pump()
    check("in anteprima la formattazione è spenta",
          not win.lookup_action("fmt_bold").get_enabled())
    pv = win.preview_buffer
    shown = pv.get_text(pv.get_start_iter(), pv.get_end_iter(), True)
    check("l'anteprima mostra il titolo una volta sola", shown.count("Capitolo") == 1)
    win._toggle_preview(whole=False)
    pump()
    check("tornando a scrivere si riaccende",
          win.lookup_action("fmt_bold").get_enabled())


def main():
    app = rw_editor.RuscaWriterApp()

    def on_activate(_app):
        def go():
            win = app.win
            for t in Gtk.Window.list_toplevels():
                if t is not win and t.get_visible():
                    t.destroy()            # finestra di benvenuto
            try:
                run_checks(win, app)
            except Exception:
                import traceback
                traceback.print_exc()
                check("nessuna eccezione", False)
            finally:
                win._dirty = False
                app.quit()
            return False
        GLib.timeout_add(800, go)

    app.connect("activate", on_activate)
    app.run(None)
    shutil.rmtree(TMP, ignore_errors=True)
    print("\n" + "=" * 50)
    print(f"RISULTATO: {PASSED} superati, {FAILED} falliti")
    print("=" * 50)
    sys.exit(1 if FAILED else 0)


if __name__ == "__main__":
    main()
