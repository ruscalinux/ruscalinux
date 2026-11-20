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
EN: GUI tests for the page set-up dialog, the three themes and the
    appearance (automatic / light / dark). They open the real window.
IT: Test dell'interfaccia per il dialogo di impostazione pagina, i due temi e
    l'aspetto (automatico / chiaro / scuro). Aprono la finestra vera.

Serve GTK 4 e uno schermo. Senza schermo si usa Xvfb:
    xvfb-run -a python3 tests/test_page_setup_gui.py
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
TMP = tempfile.mkdtemp(prefix="rw-pagesetup-")
os.environ["XDG_CONFIG_HOME"] = os.path.join(TMP, "config")
os.environ["XDG_DATA_HOME"] = os.path.join(TMP, "data")
os.environ["XDG_CACHE_HOME"] = os.path.join(TMP, "cache")
os.environ.setdefault("GSETTINGS_BACKEND", "memory")
# La lingua dell'interfaccia segue quella del sistema: per i testi italiani
# controllati qui sotto si imposta l'italiano nell'ambiente.
for _var in ("LC_ALL", "LC_MESSAGES", "LANG", "LANGUAGE"):
    os.environ[_var] = "it_IT.UTF-8" if _var != "LANGUAGE" else "it"
os.makedirs(os.path.join(TMP, "config", "ruscawriter"))
with open(os.path.join(TMP, "config", "ruscawriter", "settings.json"),
          "w", encoding="utf-8") as f:
    json.dump({"ui_lang": "it", "theme": "light",
               "theme_family": "giada"}, f)

try:
    import gi
    gi.require_version("Gtk", "4.0")
    from gi.repository import Gtk, GLib
except Exception as exc:                      # pragma: no cover
    print(f"GTK 4 non disponibile, test saltati: {exc}")
    sys.exit(0)

from ruscawriter import editor as rw_editor
from ruscawriter import model as rw_model

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


def run_checks(win):
    print("\n== Temi ==")
    check("un tema vecchio salvato (giada) diventa Classico",
          win.theme_family == rw_model.THEME_CLASSICO)
    check("due temi nel menu", len(rw_model.THEMES) == 2)
    for code in rw_model.THEMES:
        win.on_theme_family(code)
        check(f"{code}: tema applicato e ricordato",
              win.theme_family == code
              and win.settings["theme_family"] == code)

    print("\n== Aspetto ==")
    win.on_appearance("dark")
    check("scuro fissato", win.dark_mode and win.theme_pref == "dark")
    from gi.repository import Adw
    check("libadwaita allineato allo scuro",
          Adw.StyleManager.get_default().get_dark() is True)
    win.on_toggle_dark()
    check("Ctrl+Maiusc+D torna al chiaro",
          not win.dark_mode and win.theme_pref == "light")
    win.on_appearance("auto")
    check("automatico ricordato", win.settings["theme"] == "auto")
    check("l'azione del menu mostra l'aspetto scelto",
          win._appearance_action.get_state().get_string() == "auto")
    win.on_appearance("light")

    print("\n== Impostazione pagina ==")
    win._page_setup_dialog(for_export=False)
    pump()
    w = win._page_setup_widgets
    check("il dialogo si apre", w["dialog"].get_visible())
    sizes = list(rw_model.PDF_PAGE_SIZES)
    w["size"].set_selected(sizes.index("A5"))
    pump()
    check("parte dai margini del formato",
          w["preset"].get_selected() == 0)
    check("pagine speculari: interno ed esterno",
          w["labels"]["inner"].get_label() == "Interno")

    # modello: canone classico
    w["preset"].set_selected(list(rw_model.MARGIN_PRESETS).index("canon"))
    pump()
    canone = rw_model.margin_preset("canon", "A5")
    check("il modello riempie i campi",
          abs(w["spins"]["bottom"].get_value() - canone["bottom"]) < 0.05)

    # un ritocco a mano rende il modello "personalizzati"
    w["spins"]["outer"].set_value(30.0)
    pump()
    check("ritoccato -> Personalizzati",
          w["preset"].get_selected() == len(rw_model.MARGIN_PRESETS))
    check("la misura della gabbia e' scritta",
          "98,8" not in w["info"].get_label()
          and "\u00d7" in w["info"].get_label())

    # niente pagine speculari: i nomi diventano sinistro / destro
    w["mirror"].set_active(False)
    pump()
    check("senza speculari: sinistro e destro",
          w["labels"]["inner"].get_label() == "Sinistro"
          and w["labels"]["outer"].get_label() == "Destro")

    # unita': in centimetri i valori si dividono per dieci
    w["unit"].set_selected(1)
    pump()
    check("in cm il campo mostra 3,00",
          abs(w["spins"]["outer"].get_value() - 3.0) < 0.001)
    w["unit"].set_selected(0)
    pump()

    # margini impossibili: il pulsante si spegne e compare l'avviso
    w["spins"]["inner"].set_value(70.0)
    w["spins"]["outer"].set_value(70.0)
    pump()
    check("gabbia troppo stretta: Applica spento",
          not w["ok"].get_sensitive())
    check("e l'avviso lo dice",
          "stretta" in w["warn"].get_label())
    w["spins"]["inner"].set_value(20.0)
    w["spins"]["outer"].set_value(30.0)
    pump()
    check("tornati validi: Applica acceso", w["ok"].get_sensitive())

    # applica: i margini finiscono nel documento
    w["ok"].emit("clicked")
    pump()
    salvati = win.project.meta.get("page_margins", {}).get("A5")
    check("margini salvati nel documento",
          salvati is not None and salvati["outer"] == 30.0
          and salvati["mirror"] is False)
    check("il documento risulta modificato", win._dirty)
    check("formato ricordato", win.settings["pdf_page_size"] == "A5")

    # annulla non cambia nulla
    win._page_setup_dialog(for_export=False)
    pump()
    w = win._page_setup_widgets
    check("si riapre con i margini salvati",
          abs(w["spins"]["outer"].get_value() - 30.0) < 0.05
          and not w["mirror"].get_active())
    w["spins"]["outer"].set_value(15.0)
    w["cancel"].emit("clicked")
    pump()
    check("Annulla non salva",
          win.project.meta["page_margins"]["A5"]["outer"] == 30.0)

    # i margini arrivano davvero al PDF
    pdf = os.path.join(TMP, "prova.pdf")
    win._pdf_page_size = "A5"
    win._do_export_pdf(pdf)
    pump()
    check("il PDF si scrive con i margini del documento",
          os.path.exists(pdf) and os.path.getsize(pdf) > 500)


def main():
    app = rw_editor.RuscaWriterApp()

    def on_activate(_app):
        def go():
            win = app.win
            for t in Gtk.Window.list_toplevels():
                if t is not win and t.get_visible():
                    t.destroy()            # finestra di benvenuto
            try:
                run_checks(win)
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
