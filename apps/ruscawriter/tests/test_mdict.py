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
Test automatici del lettore di dizionari MDict.

Non serve un dizionario vero: il test ne SCRIVE uno, con la stessa
struttura binaria che il lettore si aspetta di trovare in un .mdx, e poi
lo rilegge. Se il lettore sbaglia a interpretare il formato, il file
scritto qui non torna indietro uguale.

Esegui dalla radice del progetto:  python3 tests/test_mdict.py
"""
import os
import sys
import zlib
import struct
import shutil
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, ".."))
sys.path.insert(0, os.path.join(ROOT, "src"))

from ruscawriter import mdict
from ruscawriter.mdict import (MdxDictionary, DictionarySet, MdxError,
                               MdxUnsupported, ripemd128, to_pango_markup,
                               to_plain_text, shorten, inflections)

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


# ---------------------------------------------------------------------------
# Un .mdx sintetico / a synthetic .mdx
# ---------------------------------------------------------------------------

def _block(payload, compress=True):
    """Blocco nel formato MDict: tipo, adler32, dati."""
    if compress:
        return b"\x02\x00\x00\x00" + struct.pack(
            ">I", zlib.adler32(payload) & 0xFFFFFFFF) + zlib.compress(payload)
    return b"\x00\x00\x00\x00" + struct.pack(
        ">I", zlib.adler32(payload) & 0xFFFFFFFF) + payload


def write_mdx(path, entries, version=2.0, encoding="UTF-8",
              compress=True, per_block=2, title="Dizionario di prova",
              description="Scritto dal test.", strip_key="No", encrypted="No"):
    """Scrive un .mdx leggibile. entries: lista di (lemma, testo)."""
    enc = "utf-16-le" if encoding.upper().startswith("UTF-16") else encoding.lower()
    term = b"\x00\x00" if enc == "utf-16-le" else b"\x00"
    wide = 2 if enc == "utf-16-le" else 1
    if version >= 2.0:
        num, tfmt, tw, tterm = ">Q", ">H", 2, 1
    else:
        num, tfmt, tw, tterm = ">I", ">B", 1, 0

    # 1. record: ogni definizione termina con un NUL, e la chiave punta
    #    all'inizio del suo testo nello spazio decompresso complessivo.
    offsets = []
    payloads = []
    pos = 0
    for word, text in entries:
        blob = text.encode(enc) + term
        offsets.append(pos)
        payloads.append(blob)
        pos += len(blob)

    rec_blocks = []
    i = 0
    while i < len(payloads):
        chunk = b"".join(payloads[i:i + per_block])
        rec_blocks.append((_block(chunk, compress), len(chunk)))
        i += per_block

    # 2. blocchi delle chiavi
    key_blocks = []
    i = 0
    while i < len(entries):
        group = entries[i:i + per_block]
        raw = b"".join(
            struct.pack(num, offsets[i + k]) + w.encode(enc) + term
            for k, (w, _) in enumerate(group))
        key_blocks.append((_block(raw, compress), len(raw), group))
        i += per_block

    info = b""
    for blob, raw_len, group in key_blocks:
        head = group[0][0].encode(enc)
        tail = group[-1][0].encode(enc)
        info += struct.pack(num, len(group))
        info += struct.pack(tfmt, len(head) // wide) + head + term[:tterm * wide]
        info += struct.pack(tfmt, len(tail) // wide) + tail + term[:tterm * wide]
        info += struct.pack(num, len(blob)) + struct.pack(num, raw_len)

    if version >= 2.0:
        info_stored = _block(info, True)
    else:
        info_stored = info

    header = (
        '<Dictionary GeneratedByEngineVersion="%s" RequiredEngineVersion="%s" '
        'Encrypted="%s" Encoding="%s" Format="Html" Compact="No" '
        'KeyCaseSensitive="No" StripKey="%s" Title="%s" Description="%s"/>'
        % (version, version, encrypted, encoding, strip_key, title, description))
    hb = header.encode("utf-16-le") + b"\x00\x00"

    key_blocks_size = sum(len(b) for b, _, _ in key_blocks)
    if version >= 2.0:
        kh = struct.pack(">5Q", len(key_blocks), len(entries), len(info),
                         len(info_stored), key_blocks_size)
        kh += struct.pack(">I", zlib.adler32(kh) & 0xFFFFFFFF)
    else:
        kh = struct.pack(">4I", len(key_blocks), len(entries),
                         len(info_stored), key_blocks_size)

    rec_info = b"".join(struct.pack(num, len(b)) + struct.pack(num, n)
                        for b, n in rec_blocks)
    rec_head = struct.pack(">4Q" if version >= 2.0 else ">4I",
                           len(rec_blocks), len(entries), len(rec_info),
                           sum(len(b) for b, _ in rec_blocks))

    with open(path, "wb") as f:
        f.write(struct.pack(">I", len(hb)))
        f.write(hb)
        f.write(struct.pack("<I", zlib.adler32(hb) & 0xFFFFFFFF))
        f.write(kh)
        f.write(info_stored)
        for blob, _, _ in key_blocks:
            f.write(blob)
        f.write(rec_head)
        f.write(rec_info)
        for blob, _ in rec_blocks:
            f.write(blob)
    return path


SAMPLE = [
    ("abaco", "<b>abaco</b> s.m. — Tavoletta per contare."),
    ("bagatella", "<b>bagatella</b> s.f. — Cosa di poco conto."),
    ("cadere", "<b>cadere</b> v.intr. — Andare giù."),
    ("caduta", "@@@LINK=cadere"),
    ("perché", "<b>perché</b> — Per quale motivo."),
    ("zuffa", "<b>zuffa</b> s.f. — Rissa confusa."),
]


# ---------------------------------------------------------------------------
# Test
# ---------------------------------------------------------------------------

def test_ripemd128():
    print("\n== RIPEMD-128 ==")
    vectors = [
        (b"", "cdf26213a150dc3ecb610f18f6b38b46"),
        (b"a", "86be7afa339d0fc7cfc785e72f578d33"),
        (b"abc", "c14a12199c66e4ba84636b0f69144c77"),
        (b"message digest", "9e327b3d6e523062afc1132d7df9d1b8"),
        (b"abcdefghijklmnopqrstuvwxyz", "fd2aa607f71dc8f510714922b371834e"),
        (b"1234567890" * 8, "3f45ef194732c2dbb2c4a2c769795fa3"),
    ]
    for data, expected in vectors:
        check(f"digest di {data[:14]!r}", ripemd128(data).hex() == expected)


def test_lettura_base(tmp):
    print("\n== Lettura di un .mdx v2 ==")
    path = write_mdx(os.path.join(tmp, "prova.mdx"), SAMPLE)
    with MdxDictionary(path, cache_folder=os.path.join(tmp, "cache")) as d:
        check("titolo dall'intestazione", d.title == "Dizionario di prova")
        check("descrizione", d.description == "Scritto dal test.")
        check("versione", d.version == 2.0)
        check("codifica", d.encoding == "utf-8")
        d.build_index()
        check("numero di lemmi", d.entry_count == len(SAMPLE))
        check("prima voce", d.lookup("abaco").endswith("Tavoletta per contare."))
        check("voce a metà", "poco conto" in d.lookup("bagatella"))
        check("ultima voce", "Rissa confusa" in d.lookup("zuffa"))
        check("lemma accentato", "Per quale motivo" in d.lookup("perché"))
        check("parola assente", d.lookup("inesistente") is None)
        check("operatore in", "cadere" in d and "inesistente" not in d)


def test_rimandi(tmp):
    print("\n== Rimandi interni (@@@LINK=) ==")
    path = write_mdx(os.path.join(tmp, "link.mdx"), SAMPLE)
    with MdxDictionary(path, cache_folder=os.path.join(tmp, "cache")) as d:
        text = d.lookup("caduta")
        check("il rimando è seguito", text is not None and "Andare giù" in text)
        check("il rimando non resta grezzo",
              text is not None and "@@@LINK" not in text)


def test_maiuscole_e_prefisso(tmp):
    print("\n== Maiuscole, spazi, prefisso ==")
    voci = SAMPLE + [("Buona Sera", "Saluto della sera."),
                     ("cadenza", "Ritmo della voce.")]
    path = write_mdx(os.path.join(tmp, "case.mdx"), voci, strip_key="Yes")
    with MdxDictionary(path, cache_folder=os.path.join(tmp, "cache")) as d:
        check("ricerca senza maiuscole", d.lookup("ABACO") is not None)
        check("ricerca con spazi diversi", d.lookup("buonasera") is not None)
        check("spazi e trattini ignorati", d.lookup("Buona-Sera") is not None)
        sugg = d.prefix("cad")
        check("suggerimenti per prefisso",
              "cadere" in sugg and "cadenza" in sugg and "abaco" not in sugg)
        check("prefisso limitato", len(d.prefix("c", limit=1)) == 1)
        check("prefisso vuoto", d.prefix("") == [])


def test_versione_1(tmp):
    print("\n== Formato v1.2 (numeri a 4 byte) ==")
    path = write_mdx(os.path.join(tmp, "vecchio.mdx"), SAMPLE, version=1.2)
    with MdxDictionary(path, cache_folder=os.path.join(tmp, "cache")) as d:
        d.build_index()
        check("versione riconosciuta", d.version == 1.2)
        check("lemmi letti", d.entry_count == len(SAMPLE))
        check("definizione letta", "Andare giù" in d.lookup("cadere"))


def test_senza_compressione(tmp):
    print("\n== Blocchi non compressi ==")
    path = write_mdx(os.path.join(tmp, "piano.mdx"), SAMPLE, compress=False)
    with MdxDictionary(path, cache_folder=os.path.join(tmp, "cache")) as d:
        check("definizione letta", "Rissa confusa" in d.lookup("zuffa"))


def test_utf16(tmp):
    print("\n== Dizionario in UTF-16 ==")
    path = write_mdx(os.path.join(tmp, "utf16.mdx"), SAMPLE, encoding="UTF-16")
    with MdxDictionary(path, cache_folder=os.path.join(tmp, "cache")) as d:
        check("codifica riconosciuta", d.encoding == "utf-16-le")
        check("lemma accentato", "Per quale motivo" in d.lookup("perché"))
        check("ultima voce", "Rissa confusa" in d.lookup("zuffa"))


def test_blocchi_grandi(tmp):
    print("\n== Molte voci, molti blocchi ==")
    voci = [(f"parola{i:05d}", f"Definizione numero {i}." * 3)
            for i in range(2000)]
    path = write_mdx(os.path.join(tmp, "grande.mdx"), voci, per_block=64)
    with MdxDictionary(path, cache_folder=os.path.join(tmp, "cache")) as d:
        d.build_index()
        check("tutte le voci indicizzate", d.entry_count == 2000)
        check("prima voce", "numero 0." in d.lookup("parola00000"))
        check("voce a metà", "numero 999." in d.lookup("parola00999"))
        check("ultima voce", "numero 1999." in d.lookup("parola01999"))
        # EN/IT: la cache dei blocchi non deve crescere senza limite
        for i in range(0, 2000, 37):
            d.lookup(f"parola{i:05d}")
        check("cache dei blocchi limitata",
              len(d._blocks) <= mdict.CACHE_BLOCKS)


def test_avanzamento(tmp):
    print("\n== Avanzamento della costruzione dell'indice ==")
    voci = [(f"voce{i:04d}", f"Testo {i}.") for i in range(500)]
    path = write_mdx(os.path.join(tmp, "prog.mdx"), voci, per_block=8)
    visti = []
    with MdxDictionary(path, cache_folder=os.path.join(tmp, "cache")) as d:
        d.build_index(progress=visti.append)
    check("la callback viene chiamata", len(visti) > 1)
    check("valori fra 0 e 1", all(0.0 <= v <= 1.0 for v in visti))
    check("valori non decrescenti",
          all(b >= a for a, b in zip(visti, visti[1:])))
    check("finisce a 1.0", visti[-1] == 1.0)


def test_cache(tmp):
    print("\n== Cache dell'indice ==")
    cache = os.path.join(tmp, "cache2")
    path = os.path.join(tmp, "cache.mdx")
    write_mdx(path, SAMPLE)
    with MdxDictionary(path, cache_folder=cache) as d:
        check("primo avvio: indice da costruire", not d.indexed)
        d.build_index()
    with MdxDictionary(path, cache_folder=cache) as d:
        check("secondo avvio: indice già pronto", d.indexed)
        check("legge senza ricostruire", "Andare giù" in d.lookup("cadere"))
    # EN/IT: se il file cambia, la cache va ignorata e non usata a sproposito
    write_mdx(path, SAMPLE + [("nuova", "Voce aggiunta dopo.")])
    os.utime(path, (0, 0))
    with MdxDictionary(path, cache_folder=cache) as d:
        check("file cambiato: cache scartata", not d.indexed)
        check("nuova voce trovata", "aggiunta dopo" in d.lookup("nuova"))
    # EN/IT: senza cartella scrivibile si lavora in memoria, senza morire
    with MdxDictionary(path, cache_folder="/proc/non/scrivibile") as d:
        check("cache non scrivibile: funziona lo stesso",
              "Andare giù" in d.lookup("cadere"))


def test_file_rovinati(tmp):
    print("\n== File rovinati o non .mdx ==")
    good = os.path.join(tmp, "buono.mdx")
    write_mdx(good, SAMPLE)
    raw = open(good, "rb").read()

    def apre(blob, nome, parola=None):
        p = os.path.join(tmp, nome)
        with open(p, "wb") as f:
            f.write(blob)
        try:
            d = MdxDictionary(p, cache_folder=os.path.join(tmp, "cache3"))
            d.build_index()
            if parola is not None:
                d.lookup(parola)
            return None
        except MdxError as exc:
            return exc

    check("file vuoto", isinstance(apre(b"", "vuoto.mdx"), MdxError))
    check("non è un .mdx",
          isinstance(apre(b"Questo e' un testo qualunque.\n" * 10,
                          "testo.mdx"), MdxError))
    check("intestazione enorme",
          isinstance(apre(b"\xff\xff\xff\xff" + raw[4:], "enorme.mdx"), MdxError))
    check("intestazione manomessa",
          isinstance(apre(raw[:20] + b"\x00\x00" + raw[22:], "testa.mdx"),
                     MdxError))
    check("file troncato a metà",
          isinstance(apre(raw[:len(raw) // 2], "mezzo.mdx"), MdxError))
    # EN/IT: un record rovinato si scopre solo quando lo si legge: l'indice
    # si costruisce lo stesso, ma la voce deve dare errore, non spazzatura.
    check("record manomesso: errore alla lettura",
          isinstance(apre(raw[:-6] + b"\x01\x02\x03\x04\x05\x06", "coda.mdx",
                          parola="zuffa"), MdxError))
    check("record manomesso: le altre voci restano leggibili",
          apre(raw[:-6] + b"\x01\x02\x03\x04\x05\x06", "coda2.mdx",
               parola="abaco") is None)


def test_non_supportati(tmp):
    print("\n== Rifiuti espliciti ==")
    path = os.path.join(tmp, "registrato.mdx")
    write_mdx(path, SAMPLE, encrypted="Yes")
    try:
        MdxDictionary(path, cache_folder=os.path.join(tmp, "cache4"))
        esito = None
    except MdxUnsupported as exc:
        esito = exc
    check("dizionario registrato rifiutato", esito is not None)
    check("il messaggio lo dice", "registrato" in str(esito).lower())

    # EN/IT: LZO: blocco valido, compressione che non implementiamo
    lzo = os.path.join(tmp, "lzo.mdx")
    write_mdx(lzo, SAMPLE, compress=False)
    raw = bytearray(open(lzo, "rb").read())
    i = raw.rfind(b"\x00\x00\x00\x00")
    raw[i:i + 4] = b"\x01\x00\x00\x00"
    with open(lzo, "wb") as f:
        f.write(raw)
    try:
        d = MdxDictionary(lzo, cache_folder=os.path.join(tmp, "cache5"))
        d.build_index()
        d.lookup("zuffa")
        esito = None
    except MdxUnsupported as exc:
        esito = exc
    except MdxError as exc:
        esito = exc
    check("LZO segnalato, non ignorato", esito is not None)



def test_html_in_pango():
    print("\n== Da HTML della voce a testo leggibile ==")
    voce = ('<link rel="stylesheet" href="stile.css"/>'
            '<div class="entry"><h3>cadere</h3>'
            '<span class="pos"><i>v. intr.</i></span> &mdash; Andare '
            'gi&ugrave; <b>per terra</b>.<br/>'
            '<ul><li>cadere dal letto</li><li>cadere in errore</li></ul>'
            '</div>')
    m = to_pango_markup(voce)
    check("il grassetto diventa grassetto", "<b>per terra</b>" in m)
    check("il corsivo diventa corsivo", "<i>v. intr.</i>" in m)
    check("il foglio di stile sparisce", "stile.css" not in m)
    check("le entita' si sciolgono", "giù" in m and "&ugrave;" not in m)
    check("gli elenchi hanno il punto", "• cadere dal letto" in m)
    check("il titolo va a capo", m.startswith("<b>cadere</b>\n"))

    check("script e style non arrivano allo schermo",
          to_pango_markup("<style>p{color:red}</style>"
                          "<script>rubaTutto()</script>Resta solo questo.")
          == "Resta solo questo.")
    check("il testo senza tag resta com'e'",
          to_pango_markup("Una voce in solo testo.") == "Una voce in solo testo.")
    check("i caratteri speciali sono protetti",
          to_pango_markup("acqua & fuoco < aria") ==
          "acqua &amp; fuoco &lt; aria")
    check("senza formattazione si legge lo stesso",
          to_plain_text(voce).startswith("cadere\nv. intr."))

    # Un dizionario scritto male non deve produrre markup che GTK rifiuta:
    # i tag si chiudono da soli, sempre.
    storto = to_pango_markup("<b>aperto <i>incrociato</b> chiuso</i> fine")
    check("i tag incrociati vengono raddrizzati",
          storto.count("<b>") == storto.count("</b>") and
          storto.count("<i>") == storto.count("</i>"))
    check("un tag mai chiuso viene chiuso",
          to_pango_markup("<b>senza fine").endswith("</b>"))


def test_taglio_della_voce():
    print("\n== Il taglio dell'inizio della voce ==")
    m = to_pango_markup("<b>zuffa</b> " + "parola " * 200)
    corto, tagliato = shorten(m, max_lines=4, max_chars=120)
    check("taglia le voci lunghe", tagliato and len(corto) < len(m))
    check("il taglio si vede", corto.endswith("…"))
    check("il grassetto resta chiuso",
          corto.count("<b>") == corto.count("</b>"))
    lungo = to_pango_markup("<i>riga uno</i><br/>riga due<br/>riga tre<br/>"
                            "riga quattro<br/>riga cinque")
    corto, tagliato = shorten(lungo, max_lines=2, max_chars=999)
    check("taglia anche a numero di righe", corto.count("\n") == 1)
    intero, tagliato = shorten(to_pango_markup("Voce corta."), 4, 320)
    check("una voce corta non si tocca",
          intero == "Voce corta." and not tagliato)
    # il taglio non deve mai spezzare un'entita' a meta'
    for n in range(1, 60):
        pezzo, _ = shorten(to_pango_markup("a & b < c > d " * 5), 4, n)
        check_silenzioso = pezzo.count("&") == pezzo.count(";")
        if not check_silenzioso:
            break
    check("mai un'entita' spezzata a meta'", check_silenzioso)


def test_piu_dizionari(tmp):
    print("\n== Piu' dizionari, consultati in ordine ==")
    uno = write_mdx(os.path.join(tmp, "uno.mdx"),
                    [("anima", "Voce del primo."), ("solo1", "Solo nel primo.")],
                    title="Primo")
    due = write_mdx(os.path.join(tmp, "due.mdx"),
                    [("anima", "Voce del secondo."), ("solo2", "Solo nel secondo.")],
                    title="Secondo")
    ds = DictionarySet([uno, due], cache_folder=os.path.join(tmp, "cacheN"))
    check("due dizionari aperti", len(ds) == 2)
    check("indici da costruire", len(ds.pending()) == 2)
    ds.build_pending()
    check("nessuno resta da costruire", ds.pending() == [])
    d, testo = ds.first("anima")
    check("vince il primo dell'elenco", d.title == "Primo" and "primo" in testo)
    check("trova anche cio' che ha solo il secondo",
          ds.first("solo2")[1] == "Solo nel secondo.")
    check("le voci di entrambi si vedono tutte",
          [x[0].title for x in ds.lookup("anima")] == ["Primo", "Secondo"])
    ds.move(due, -1)
    check("cambiando ordine cambia chi vince",
          ds.first("anima")[0].title == "Secondo")
    check("i suggerimenti pescano da tutti",
          set(ds.prefix("solo")) == {"solo1", "solo2"})
    ds.remove(due)
    check("togliere un dizionario", len(ds) == 1 and ds.first("solo2") is None)
    check("parola assente ovunque", ds.first("inesistente") is None)

    # un file rotto in mezzo non deve impedire l'avvio del programma
    rotto = os.path.join(tmp, "rotto.mdx")
    with open(rotto, "wb") as f:
        f.write(b"non sono un dizionario")
    ds2 = DictionarySet(cache_folder=os.path.join(tmp, "cacheM"))
    ds2.add_quiet(rotto)
    ds2.add_quiet(uno)
    ds2.build_pending()
    check("il file rotto e' segnalato", len(ds2.errors) == 1)
    check("gli altri funzionano lo stesso",
          ds2.first("anima")[1] == "Voce del primo.")
    ds.close()
    ds2.close()



LEMMI_VICINI = [
    "anima", "animale", "bambino", "bello", "cadere", "caduta", "cane",
    "casa", "casale", "caso", "città", "fiore", "fiorire", "house", "libro",
    "libreria", "macchina", "mangiare", "mouse", "porta", "portare", "run",
    "scrivere", "stanza", "stare", "tavola", "tavolo",
]


def test_parola_piu_vicina(tmp):
    print("\n== Quando la parola esatta non c'e' ==")
    path = write_mdx(os.path.join(tmp, "vicini.mdx"),
                     [(w, f"Definizione di {w}.") for w in sorted(LEMMI_VICINI)])
    d = MdxDictionary(path, cache_folder=os.path.join(tmp, "cacheV"))
    d.build_index()

    def primo(parola):
        v = d.near(parola)
        return v[0][0] if v else None

    print("  -- plurali")
    for plurale, singolare in [("case", "casa"), ("libri", "libro"),
                               ("bambini", "bambino"), ("cani", "cane"),
                               ("anime", "anima"), ("stanze", "stanza"),
                               ("macchine", "macchina"), ("fiori", "fiore"),
                               ("houses", "house")]:
        check(f"{plurale} → {singolare}",
              singolare in [w for w, _ in d.near(plurale)])

    print("  -- forme verbali")
    for forma, lemma in [("mangiando", "mangiare"), ("scrivendo", "scrivere"),
                         ("portava", "portare"), ("cadendo", "cadere"),
                         ("runs", "run")]:
        check(f"{forma} → {lemma}", lemma in [w for w, _ in d.near(forma)])

    print("  -- accenti")
    check("citta → città", primo("citta") == "città")

    print("  -- quello che NON deve succedere")
    check("una parola senza rapporto non trova niente", d.near("xyzzy") == [])
    check("nemmeno una lunga e inventata",
          d.near("qwertyuiop") == [])
    check("una parola troppo corta non tira a indovinare",
          d.near("il") == [] and d.near("a") == [])
    check("l'inizio deve combaciare: 'gatto' non diventa 'tavolo'",
          "tavolo" not in [w for w, _ in d.near("gatto")])
    check("la parola esatta non compare fra i vicini",
          "casa" not in [w for w, _ in d.near("casa")])

    print("  -- ordine e forma della risposta")
    vicini = d.near("bambini")
    check("il migliore per primo",
          vicini and vicini[0][1] == max(s for _w, s in vicini))
    check("punteggi fra 0 e 1", all(0 < s <= 1 for _w, s in vicini))
    check("il numero di risposte si limita", len(d.near("case", limit=1)) == 1)
    check("alzando la soglia si restringe",
          len(d.near("case", min_ratio=0.95)) < len(d.near("case")))
    check("le voci vicine si leggono davvero",
          "Definizione di casa" in d.lookup(primo("case")))
    d.close()


def test_vicini_fra_piu_dizionari(tmp):
    print("\n== La parola più vicina fra più dizionari ==")
    uno = write_mdx(os.path.join(tmp, "v1.mdx"),
                    [("casa", "Casa del primo."), ("cane", "Cane del primo.")],
                    title="Primo")
    due = write_mdx(os.path.join(tmp, "v2.mdx"),
                    [("casa", "Casa del secondo."), ("gatto", "Gatto del secondo.")],
                    title="Secondo")
    ds = DictionarySet([uno, due], cache_folder=os.path.join(tmp, "cacheW"))
    ds.build_pending()
    trovato = ds.first_near("case")
    check("trova la voce vicina", trovato is not None)
    if trovato:
        source, lemma, testo, score = trovato
        check("dice quale lemma ha trovato", lemma == "casa")
        check("dice da quale dizionario viene", source.title == "Primo")
        check("restituisce il testo della voce", "Casa del primo." in testo)
        check("dice quanto e' vicino", 0 < score < 1)
    check("cerca in tutti i dizionari",
          "gatto" in [w for _d, w, _s in ds.near("gatti")])
    check("niente di simile: nessuna risposta", ds.first_near("xyzzy") is None)
    ds.close()



# Lemmi come li registra un dizionario: maschile singolare, o la forma
# base della lingua. Le prove qui sotto partono dalla forma flessa.
LEMMI_REGOLE = [
    # italiano
    "casa", "caso", "cane", "libro", "amico", "amica", "fuoco", "lago",
    "uomo", "mano", "dito", "bello", "attore", "attrice", "professore",
    "studio", "gatto", "gatta", "poeta", "braccio",
    # inglese
    "house", "city", "knife", "child", "box", "woman", "mouse", "church",
    "wolf", "day",
    # spagnolo, francese, portoghese, tedesco, russo
    "luz", "profesor", "maestro", "journal", "chanteur", "grand", "cheval",
    "coração", "animal", "pão", "Buch", "Stadt", "Lehrer", "Kind",
    "книга", "стол", "дом",
]

# (forma flessa, lingua di chi scrive, lemma atteso)
PROVE_REGOLE = [
    ("case", "it", "casa"), ("libri", "it", "libro"),
    ("amiche", "it", "amica"), ("amici", "it", "amico"),
    ("fuochi", "it", "fuoco"), ("laghi", "it", "lago"),
    ("gatte", "it", "gatta"), ("gatti", "it", "gatto"),
    ("poeti", "it", "poeta"),
    ("braccia", "it", "braccio"), ("belle", "it", "bello"),
    ("bella", "it", "bello"), ("attrici", "it", "attrice"),
    ("professoresse", "it", "professore"), ("studi", "it", "studio"),
    ("uomini", "it", "uomo"), ("mani", "it", "mano"), ("dita", "it", "dito"),
    ("houses", "en", "house"), ("cities", "en", "city"),
    ("knives", "en", "knife"), ("churches", "en", "church"),
    ("wolves", "en", "wolf"), ("days", "en", "day"),
    ("boxes", "en", "box"), ("children", "en", "child"),
    ("women", "en", "woman"), ("mice", "en", "mouse"),
    ("luces", "es", "luz"), ("profesora", "es", "profesor"),
    ("maestras", "es", "maestro"),
    ("journaux", "fr", "journal"), ("chanteuse", "fr", "chanteur"),
    ("grande", "fr", "grand"), ("chevaux", "fr", "cheval"),
    ("corações", "pt", "coração"), ("animais", "pt", "animal"),
    ("pães", "pt", "pão"),
    ("Bücher", "de", "Buch"), ("Städte", "de", "Stadt"),
    ("Lehrerin", "de", "Lehrer"), ("Kinder", "de", "Kind"),
    ("книги", "ru", "книга"), ("столы", "ru", "стол"),
    ("домов", "ru", "дом"),
]


def test_genere_e_numero(tmp):
    print("\n== Genere e numero, per regola ==")
    path = write_mdx(os.path.join(tmp, "regole.mdx"),
                     [(w, f"Voce: {w}.") for w in sorted(LEMMI_REGOLE)])
    ds = DictionarySet([path], cache_folder=os.path.join(tmp, "cacheR"))
    ds.build_pending()
    per_lingua = {}
    for flessa, lingua, lemma in PROVE_REGOLE:
        trovato = ds.first_form(flessa, (lingua,))
        ok = trovato is not None and trovato[1] == lemma
        per_lingua.setdefault(lingua, []).append((flessa, lemma, ok,
                                                  trovato[1] if trovato else None))
    for lingua, righe in per_lingua.items():
        giuste = sum(1 for _f, _l, ok, _t in righe if ok)
        check(f"{lingua}: {giuste}/{len(righe)} forme flesse risolte",
              giuste == len(righe))
        for flessa, lemma, ok, ottenuto in righe:
            if not ok:
                print(f"       {flessa} → {ottenuto} invece di {lemma}")

    print("  -- quello che le regole NON devono fare")
    check("una parola che non e' flessa non viene stravolta",
          ds.first_form("casa", ("it",)) is None or
          ds.first_form("casa", ("it",))[1] != "casa")
    check("una parola inventata non trova niente",
          ds.first_form("qwertyuiop", ("it",)) is None)
    check("le parole corte si lasciano stare", inflections("il") == [])
    check("il lemma restituito e' scritto come nel dizionario",
          ds.first_form("Bücher", ("de",))[1] == "Buch")
    check("la voce si legge davvero",
          "Voce: casa." in ds.first_form("case", ("it",))[2])

    print("  -- la lingua di chi scrive decide, ma non chiude le porte")
    check("con l'italiano davanti, 'case' resta 'casa'",
          ds.first_form("case", ("it",))[1] == "casa")
    check("senza dire la lingua, funziona lo stesso",
          ds.first_form("libri")[1] == "libro")
    check("una lingua sbagliata non impedisce di trovare",
          ds.first_form("houses", ("it",))[1] == "house")
    check("le regole cirilliche non si applicano all'alfabeto latino",
          all(not any(0x400 <= ord(c) <= 0x4FF for c in f)
              for f in inflections("case", ("it",))))
    ds.close()


def main():
    print("=" * 50)
    print("TEST DEL LETTORE MDICT")
    print("=" * 50)
    tmp = tempfile.mkdtemp(prefix="rw-mdict-")
    try:
        test_ripemd128()
        test_html_in_pango()
        test_taglio_della_voce()
        for fn in (test_lettura_base, test_rimandi, test_maiuscole_e_prefisso,
                   test_versione_1, test_senza_compressione, test_utf16,
                   test_blocchi_grandi, test_avanzamento, test_cache,
                   test_file_rovinati, test_non_supportati,
                   test_piu_dizionari, test_genere_e_numero,
                   test_parola_piu_vicina,
                   test_vicini_fra_piu_dizionari):
            fn(tmp)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    print("\n" + "=" * 50)
    print(f"RISULTATO: {PASSED} superati, {FAILED} falliti")
    print("=" * 50)
    sys.exit(1 if FAILED else 0)


if __name__ == "__main__":
    main()
