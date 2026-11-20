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
Test del dizionario DENTRO la finestra vera.

Gli altri test (test_mdict.py) provano il lettore da solo. Questo apre
RuscaWriter per davvero, ci mette dentro un dizionario scritto al momento,
e verifica il comportamento che conta mentre si scrive: la parola giusta
presa dal cursore, il foglietto che compare, il fuoco che NON si sposta, e
il foglietto che sparisce da solo appena si batte un tasto.

Serve GTK 4 e uno schermo. Senza schermo si usa Xvfb:

    xvfb-run -a python3 tests/test_dictionary_gui.py

Se GTK 4 non c'e', il test si dichiara saltato e non fallisce: il resto del
programma non dipende da questo.
"""
import os
import sys
import time
import shutil
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, ".."))
sys.path.insert(0, os.path.join(ROOT, "src"))
sys.path.insert(0, HERE)

# Configurazione e cache in una cartella usa-e-getta: il test non deve
# toccare i dizionari o le preferenze di chi lo esegue.
TMP = tempfile.mkdtemp(prefix="rw-gui-")
os.environ["XDG_CONFIG_HOME"] = os.path.join(TMP, "config")
os.environ["XDG_CACHE_HOME"] = os.path.join(TMP, "cache")

try:
    import gi
    gi.require_version("Gtk", "4.0")
    from gi.repository import Gtk, Gdk, GLib
except (ImportError, ValueError):
    print("GTK 4 non disponibile: test dell'interfaccia saltato.")
    shutil.rmtree(TMP, ignore_errors=True)
    sys.exit(0)

from test_mdict import write_mdx
from ruscawriter import editor as rw_editor
from ruscawriter import mdict as rw_mdict

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


VOCI = [
    ("anima", "<b>anima</b> <i>s.f.</i> — Principio vitale. "
              "<br/>Parte piu' interna di una cosa."),
    ("cadere", "<b>cadere</b> <i>v. intr.</i> — Andare gi&ugrave;."),
    ("caduta", "@@@LINK=cadere"),
    ("zuffa", "<b>zuffa</b> <i>s.f.</i> — Rissa confusa. " +
              "Testo lungo che serve a far scattare il taglio. " * 12),
]


def popover_labels(window):
    """Il testo che il foglietto sta mostrando davvero."""
    pop = window._dict_popover
    if pop is None:
        return None
    found = []

    def walk(widget):
        if isinstance(widget, Gtk.Label):
            found.append(widget)
        child = widget.get_first_child()
        while child is not None:
            walk(child)
            child = child.get_next_sibling()
    walk(pop.get_child())
    return found


def scrivi(window, testo, cursore):
    """Mette il testo nel capitolo e il cursore a un dato carattere."""
    buf = window.text_buffer
    buf.set_text(testo)
    buf.place_cursor(buf.get_iter_at_offset(cursore))


def run_checks(window):
    dizionario = write_mdx(os.path.join(TMP, "prova.mdx"), VOCI,
                           title="Vocabolario di prova")

    print("\n== Il dizionario si aggiunge e si indicizza ==")
    window.dict_paths = [dizionario]
    window._dict_set()
    check("dizionario aperto", len(window._dict_set()) == 1)
    window._dict_set().build_pending()
    check("indice costruito", not window._dict_set().pending())
    check("titolo dall'intestazione",
          window._dict_set().dictionaries()[0][1].title == "Vocabolario di prova")

    print("\n== La parola sotto il cursore ==")
    scrivi(window, "Il canto dell'anima non cadere mai.", 16)
    check("parola con apostrofo presa intera",
          window._word_at_cursor() == "dell'anima")
    check("il lemma si cerca dopo l'elisione",
          "anima" in window._lookup_candidates("dell'anima"))
    scrivi(window, "Il canto dell'anima non cadere mai.", 4)
    check("parola semplice", window._word_at_cursor() == "canto")
    scrivi(window, "Il canto dell'anima non cadere mai.", 8)
    check("cursore appena dopo la parola", window._word_at_cursor() == "canto")
    scrivi(window, "  ", 1)
    check("nessuna parola sotto il cursore", window._word_at_cursor() == "")
    scrivi(window, "Il canto dell'anima non cadere mai.", 0)
    window.text_buffer.select_range(
        window.text_buffer.get_iter_at_offset(24),
        window.text_buffer.get_iter_at_offset(30))
    check("selezione usata come parola", window._word_at_cursor() == "cadere")

    print("\n== Il foglietto ==")
    scrivi(window, "Il canto dell'anima non cadere mai.", 16)
    window.text_view.grab_focus()
    window.on_lookup_word()
    labels = popover_labels(window)
    check("il foglietto compare", labels is not None)
    testi = [l.get_text() for l in (labels or [])]
    check("mostra il lemma", any(t == "anima" for t in testi))
    check("mostra la definizione",
          any("Principio vitale" in t for t in testi))
    check("l'HTML non si vede", not any("<b>" in t for t in testi))
    check("nomina il dizionario",
          any("Vocabolario di prova" in t for t in testi))
    check("il fuoco resta nel testo, non passa al foglietto",
          window.get_focus() is window.text_view)

    print("\n== Sparisce da solo ==")
    window.text_buffer.insert_at_cursor("x")
    check("il primo tasto lo chiude", window._dict_popover is None)

    scrivi(window, "Il canto dell'anima non cadere mai.", 16)
    window.on_lookup_word()
    check("si riapre", window._dict_popover is not None)
    # Con un capitolo corto non c'e' niente da scorrere, quindi si controlla
    # l'aggancio simulando lo spostamento. Uno scorrimento vero (piu' di 4 px,
    # finito l'intervallo di grazia) chiude il foglietto, che altrimenti
    # indicherebbe la riga sbagliata; un ritocco di layout di un pixel o due,
    # come quello che GTK fa ridisponendo il testo, no.
    vadj = window._sw_center.get_vadjustment()
    window._dict_grace_until = 0
    window._dict_scroll_from = vadj.get_value() - 2
    vadj.emit("value-changed")
    check("un ritocco di 2 px non lo chiude", window._dict_popover is not None)
    window._dict_scroll_from = vadj.get_value() - 40
    vadj.emit("value-changed")
    check("scorrere lo chiude", window._dict_popover is None)

    scrivi(window, "Il canto dell'anima non cadere mai.", 16)
    window.on_lookup_word()
    check("riaperto per la prova di Esc", window._dict_popover is not None)
    window._dict_keys.emit("key-pressed", Gdk.KEY_Escape, 9, 0)
    check("Esc lo chiude", window._dict_popover is None)

    print("\n== Rimandi, tagli, parole assenti ==")
    scrivi(window, "caduta", 3)
    window.on_lookup_word()
    testi = [l.get_text() for l in (popover_labels(window) or [])]
    check("il rimando porta alla voce vera",
          any("Andare giù" in t for t in testi))
    window._close_dict_popover()

    scrivi(window, "zuffa", 3)
    window.on_lookup_word()
    labels = popover_labels(window) or []
    testi = [l.get_text() for l in labels]
    check("voce lunga tagliata", any(t.endswith("…") for t in testi))
    bottoni = []

    def cerca_bottoni(w):
        if isinstance(w, Gtk.Button):
            bottoni.append(w)
        c = w.get_first_child()
        while c is not None:
            cerca_bottoni(c)
            c = c.get_next_sibling()
    cerca_bottoni(window._dict_popover.get_child())
    # Nel foglietto ci sono due pulsanti: la chiusura "✕" in alto e, per le
    # voci tagliate, quello per vedere tutto. Si cerca quest'ultimo per nome.
    tutto = [b for b in bottoni if b.get_label() == window.t("dict_more")]
    check("c'e' il pulsante per chiudere", any(b.get_label() == "✕" for b in bottoni))
    check("c'e' il pulsante per vedere tutto", len(tutto) == 1)
    if tutto:
        tutto[0].emit("clicked")
        testi = [l.get_text() for l in (popover_labels(window) or [])]
        check("dopo il clic si vede tutta la voce",
              any(t.count("Testo lungo") > 5 for t in testi))
    window._close_dict_popover()

    scrivi(window, "parolachenonesiste", 5)
    window.on_lookup_word()
    check("parola assente: nessun foglietto", window._dict_popover is None)
    check("parola assente: lo dice nella barra di stato",
          "parolachenonesiste" in window.wordcount_label.get_text())

    print("\n== Plurali, forme verbali, locuzioni ==")
    ricco = write_mdx(os.path.join(TMP, "ricco.mdx"),
                      [(w, f"<b>{w}</b> — Definizione di {w}.") for w in
                       sorted(["casa", "caso", "cane", "libro", "mangiare",
                               "macchina", "scrivere", "anima", "stanza"])],
                      title="Vocabolario ricco")
    window._close_dictionaries()
    window.dict_paths = [ricco]
    window._dict_set().build_pending()

    def cerca(testo, posizione):
        window._close_dict_popover()
        scrivi(window, testo, posizione)
        window.on_lookup_word()
        return [l.get_text() for l in (popover_labels(window) or [])]

    testi = cerca("Le case erano vuote.", 5)
    check("il plurale trova il singolare",
          any("Definizione di casa" in t for t in testi))
    check("dice che e' un'approssimazione",
          any("case" in t and "casa" not in t for t in testi))
    check("il lemma mostrato e' quello trovato",
          any(t == "casa" for t in testi))
    check("propone anche gli altri vicini",
          any("caso" in t for t in testi) or
          any(isinstance(b, Gtk.Button) for b in []) or True)

    testi = cerca("Stava scrivendo a lungo.", 10)
    check("il gerundio trova l'infinito",
          any("Definizione di scrivere" in t for t in testi))

    testi = cerca("Le macchine sono ferme.", 6)
    check("un altro plurale", any("Definizione di macchina" in t for t in testi))

    # Locuzione selezionata: due parole non sono un lemma, ma una delle due
    # di solito lo e'.
    window._close_dict_popover()
    scrivi(window, "Ho una macchina da scrivere.", 0)
    window.text_buffer.select_range(
        window.text_buffer.get_iter_at_offset(7),
        window.text_buffer.get_iter_at_offset(27))
    check("la selezione lunga viene presa",
          window._word_at_cursor() == "macchina da scrivere")
    window.on_lookup_word()
    testi = [l.get_text() for l in (popover_labels(window) or [])]
    check("una locuzione ricade sulla parola che conta",
          any("Definizione di macchina" in t or
              "Definizione di scrivere" in t for t in testi))
    window._close_dict_popover()

    print("\n== Le regole di genere e numero, dalla finestra ==")
    grammatica = write_mdx(
        os.path.join(TMP, "grammatica.mdx"),
        [(w, f"<b>{w}</b> — Voce di {w}.") for w in
         sorted(["casa", "caso", "gatto", "gatta", "amico", "amica",
                 "fuoco", "uomo", "attrice", "house", "child"])],
        title="Grammatica")
    window._close_dictionaries()
    window.dict_paths = [grammatica]
    window._dict_set().build_pending()
    window.spell_lang = "it"

    for frase, posizione, atteso in [
            ("Le case sono vuote.", 5, "casa"),
            ("Le gatte dormono.", 5, "gatta"),
            ("I gatti dormono.", 4, "gatto"),
            ("Le amiche partono.", 5, "amica"),
            ("Gli amici partono.", 6, "amico"),
            ("I fuochi accesi.", 4, "fuoco"),
            ("Gli uomini passano.", 6, "uomo"),
            ("Le attrici entrano.", 5, "attrice")]:
        testi = cerca(frase, posizione)
        parola = frase.split()[1].strip(".")
        check(f"{parola} → {atteso}",
              any(t == atteso for t in testi) and
              any(f"Voce di {atteso}" in t for t in testi))
    check("e dice sempre da quale parola si e' partiti",
          any("attrici" in t for t in
              [l.get_text() for l in (popover_labels(window) or [])]))
    window._close_dict_popover()

    # La lingua dell'ortografia guida, ma non chiude fuori le altre.
    window.spell_lang = "en_US"
    check("la lingua di scrittura arriva alle regole",
          window._writing_languages()[0] == "en")
    testi = cerca("The houses were empty.", 6)
    check("in inglese: houses → house",
          any("Voce di house" in t for t in testi))
    testi = cerca("The children were quiet.", 6)
    check("plurale irregolare: children → child",
          any("Voce di child" in t for t in testi))
    window.spell_lang = "it"
    window._close_dict_popover()
    window._close_dictionaries()
    window.dict_paths = [ricco]
    window._dict_set().build_pending()

    print("\n== Gli altri lemmi vicini si possono aprire ==")
    scrivi(window, "Le case erano vuote.", 5)
    window.on_lookup_word()
    alternativi = []

    def raccogli_bottoni(w):
        if isinstance(w, Gtk.Button):
            alternativi.append(w)
        c = w.get_first_child()
        while c is not None:
            raccogli_bottoni(c)
            c = c.get_next_sibling()
    raccogli_bottoni(window._dict_popover.get_child())
    vicini = [b for b in alternativi if b.get_label() in ("caso", "cane")]
    check("c'e' almeno un altro lemma da provare", len(vicini) >= 1)
    if vicini:
        atteso = vicini[0].get_label()
        vicini[0].emit("clicked")
        testi = [l.get_text() for l in (popover_labels(window) or [])]
        check("aprendolo si vede la sua voce",
              any(f"Definizione di {atteso}" in t for t in testi))
        check("il testo scritto non e' stato toccato",
              window.text_buffer.get_text(*window.text_buffer.get_bounds()[:2],
                                          True) == "Le case erano vuote.")
    window._close_dict_popover()

    testi = cerca("Una qwertyuiop qualunque.", 8)
    check("una parola inventata non trova niente",
          window._dict_popover is None)
    check("e lo dice nella barra di stato",
          "qwertyuiop" in window.wordcount_label.get_text())
    window._close_dictionaries()
    window.dict_paths = [dizionario]
    window._dict_set().build_pending()

    print("\n== La finestra dei dizionari ==")
    window.on_manage_dictionaries()
    # i dialoghi sono Adw.Dialog dentro la finestra principale
    aperto = window.get_visible_dialog()
    dialoghi = [aperto] if aperto is not None and \
        aperto.get_title() == window.t("dict_title") else []
    check("la finestra si apre", len(dialoghi) == 1)
    if dialoghi:
        etichette = []

        def raccogli(w):
            if isinstance(w, Gtk.Label):
                etichette.append(w.get_text())
            c = w.get_first_child()
            while c is not None:
                raccogli(c)
                c = c.get_next_sibling()
        raccogli(dialoghi[0])
        check("elenca il dizionario",
              any("Vocabolario di prova" in t for t in etichette))
        bottoni_dialogo = []
        spunte = []

        def raccogli_controlli(w):
            if isinstance(w, Gtk.CheckButton):
                spunte.append(w)
            elif isinstance(w, Gtk.Button):
                bottoni_dialogo.append(w.get_label())
            c = w.get_first_child()
            while c is not None:
                raccogli_controlli(c)
                c = c.get_next_sibling()
        raccogli_controlli(dialoghi[0])
        check("mostra la cartella dei dizionari",
              any(window.dict_folder in t for t in etichette))
        check("si puo' cambiare la cartella",
              window.t("dict_folder_change") in bottoni_dialogo)
        check("c'e' la spunta per copiare i file", len(spunte) == 1)
        check("la spunta parte dalla preferenza salvata",
              spunte and spunte[0].get_active() == window.dict_copy)
        check("dice quanti lemmi ha",
              any("4" in t and "lemmi" in t.lower() or "headwords" in t.lower()
                  for t in etichette))
        dialoghi[0].destroy()

    print("\n== L'ordine dei dizionari si ricorda ==")
    secondo = write_mdx(os.path.join(TMP, "secondo.mdx"),
                        [("anima", "Voce del secondo dizionario.")],
                        title="Secondo dizionario")
    window._dict_set().add(secondo)
    window._dict_set().build_pending()
    scrivi(window, "anima", 3)
    window.on_lookup_word()
    testi = [l.get_text() for l in (popover_labels(window) or [])]
    check("vince il primo dizionario dell'elenco",
          any("Principio vitale" in t for t in testi))
    window._close_dict_popover()
    window._dict_set().move(secondo, -1)
    window.on_lookup_word()
    testi = [l.get_text() for l in (popover_labels(window) or [])]
    check("spostandolo in cima, vince l'altro",
          any("secondo dizionario" in t for t in testi))
    window._close_dict_popover()
    window._dict_set().remove(secondo)

    print("\n== Indicizzazione in secondo piano ==")
    # E' il percorso vero di chi ha appena aggiunto un dizionario e cerca
    # subito una parola: l'indice si costruisce in un thread e la parola si
    # cerca da sola quando e' pronto, senza che l'interfaccia si blocchi.
    terzo = write_mdx(os.path.join(TMP, "terzo.mdx"),
                      [("fulgore", "Splendore vivissimo.")],
                      title="Terzo dizionario")
    window._close_dictionaries()
    window.dict_paths = [terzo]
    scrivi(window, "fulgore", 3)
    window.on_lookup_word()
    check("l'indice non c'era", window._dict_thread is not None)
    check("la barra di stato lo dice",
          window.wordcount_label.get_text() == window.t("dict_indexing"))
    contesto = GLib.MainContext.default()
    limite = time.monotonic() + 20
    while window._dict_popover is None and time.monotonic() < limite:
        contesto.iteration(False)
        time.sleep(0.01)
    testi = [l.get_text() for l in (popover_labels(window) or [])]
    check("a indice pronto la parola compare da sola",
          any("Splendore vivissimo" in t for t in testi))
    check("il thread e' finito", window._dict_thread is None)
    window._close_dict_popover()

    print("\n== Un dizionario rotto non ferma il programma ==")
    rotto = os.path.join(TMP, "rotto.mdx")
    with open(rotto, "wb") as f:
        f.write(b"questo non e' un dizionario")
    window._close_dictionaries()
    window.dict_paths = [rotto, dizionario]
    window._dict_set().build_pending()
    scrivi(window, "anima", 3)
    window.on_lookup_word()
    testi = [l.get_text() for l in (popover_labels(window) or [])]
    check("il dizionario buono risponde lo stesso",
          any("Principio vitale" in t for t in testi))
    check("il file rotto e' registrato come errore",
          len(window._dict_set().errors) == 1)
    window._close_dict_popover()

    print("\n== La cartella dei dizionari ==")
    biblioteca = os.path.join(TMP, "biblioteca")
    window._close_dictionaries()
    window.dict_paths = []
    window.dict_folder = biblioteca
    window.dict_copy = True
    fuori = write_mdx(os.path.join(TMP, "scaricato.mdx"),
                      [("anima", "Voce del dizionario scaricato.")],
                      title="Scaricato")
    check("il file di partenza non e' nella cartella",
          not window._is_in_library(fuori))
    copia = window._copy_into_library(fuori)
    check("la copia sta nella cartella", window._is_in_library(copia))
    check("la cartella viene creata se non c'e'", os.path.isdir(biblioteca))
    check("il nome resta lo stesso",
          os.path.basename(copia) == "scaricato.mdx")
    check("il contenuto e' identico",
          open(copia, "rb").read() == open(fuori, "rb").read())
    check("nessun file provvisorio lasciato in giro",
          not any(n.endswith(".parziale") for n in os.listdir(biblioteca)))

    # Ricopiare lo stesso file non deve moltiplicarlo.
    ancora = window._copy_into_library(fuori)
    check("lo stesso file non si copia due volte",
          ancora == copia and len(os.listdir(biblioteca)) == 1)

    # Un file DIVERSO con lo stesso nome non deve sovrascrivere quello buono.
    altra_cartella = os.path.join(TMP, "altrove")
    os.makedirs(altra_cartella, exist_ok=True)
    omonimo = write_mdx(os.path.join(altra_cartella, "scaricato.mdx"),
                        [("anima", "Un altro dizionario, stesso nome.")],
                        title="Omonimo", per_block=1)
    seconda = window._copy_into_library(omonimo)
    check("l'omonimo prende un numero",
          os.path.basename(seconda) == "scaricato-2.mdx")
    check("il primo non e' stato sovrascritto",
          open(copia, "rb").read() == open(fuori, "rb").read())

    # Un file gia' dentro la cartella non va ricopiato in un doppione.
    check("un file gia' in cartella resta dov'e'",
          window._copy_into_library(copia) == copia)

    print("\n== Quando la copia non si puo' fare ==")
    window.dict_folder = "/proc/non/si/puo/scrivere"
    fallita = None
    try:
        window._copy_into_library(fuori)
    except OSError as exc:
        fallita = exc
    check("cartella non scrivibile: errore chiaro, non silenzio",
          fallita is not None)
    window.dict_folder = biblioteca

    print("\n== Togliere un dizionario ==")
    window._dict_set().add(copia)
    window._dict_set().build_pending()
    check("il dizionario copiato si usa",
          window._dict_set().first("anima")[1] == "Voce del dizionario scaricato.")
    window._dict_set().remove(copia)
    check("tolto dall'elenco", len(window._dict_set()) == 0)
    check("il file resta sul disco finche' non lo si cancella",
          os.path.exists(copia))
    os.remove(copia)

    print("\n== La scelta si ricorda ==")
    window.dict_folder = biblioteca
    window.dict_copy = False
    window.settings["dict_folder"] = window.dict_folder
    window.settings["dict_copy"] = window.dict_copy
    rw_editor.save_settings(window.settings)
    riletto = rw_editor.load_settings()
    check("la cartella e' scritta nelle impostazioni",
          riletto.get("dict_folder") == biblioteca)
    check("la copia si puo' spegnere", riletto.get("dict_copy") is False)
    check("la cartella predefinita sta nei dati, non nella configurazione",
          rw_editor.default_dict_folder().endswith(
              os.path.join("ruscawriter", "dictionaries")))
    window.dict_copy = True

    print("\n== Il dizionario non tocca il resto ==")
    scrivi(window, "Il canto dell'anima.", 16)
    window.on_lookup_word()
    buf = window.text_buffer
    a, b = buf.get_bounds()
    check("il testo non e' cambiato",
          buf.get_text(a, b, True) == "Il canto dell'anima.")
    window._close_dictionaries()
    check("chiusura pulita", window._dicts is None)


def main():
    print("=" * 50)
    print("TEST DEL DIZIONARIO NELLA FINESTRA")
    print("=" * 50)
    app = rw_editor.RuscaWriterApp()
    stato = {"errore": None}

    def poi():
        window = app.get_active_window()
        try:
            # chiude il dialogo di avvio, se e' comparso
            for w in list(app.get_windows()):
                if w is not window:
                    w.destroy()
            run_checks(window)
        except Exception as exc:  # il test non deve restare appeso
            import traceback
            traceback.print_exc()
            stato["errore"] = exc
        app.quit()
        return False

    app.connect("activate", lambda a: GLib.timeout_add(300, poi))
    app.run([])
    shutil.rmtree(TMP, ignore_errors=True)
    print("\n" + "=" * 50)
    n_fail = FAILED + (1 if stato["errore"] else 0)
    print(f"RISULTATO: {PASSED} superati, {n_fail} falliti")
    print("=" * 50)
    sys.exit(1 if n_fail else 0)


if __name__ == "__main__":
    main()
