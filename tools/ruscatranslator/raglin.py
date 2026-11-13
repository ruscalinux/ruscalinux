#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
# raglin.py — RAG linguistico di RuscaTranslator (italiano <-> inglese)
# RuscaLinux OS Tools 1.99.3 — Copyright (C) 2026 Nunzio Curcuruto — GPL-3.0-or-later
#
# Strati:
#   1) base di conoscenza lessicale (idiomi, falsi amici, pragmatica,
#      terminologia, connettivi, hedging, culturemi, metafore, convenzioni,
#      latinismi, stile): retrieval lessicale deterministico;
#   2) glossario di documento, tradotto una volta e tenuto in cache;
#   3) memoria di traduzione (TM) dalle traduzioni salvate;
#   4) blocco di suggerimenti aggiunto al prompt di ogni blocco di testo;
#   5) correzioni deterministiche dopo la generazione (post-fix), SOLO di
#      portata generale e per dominio, mai dentro codice, link o HTML;
#   6) prompt di dominio (USI): generale, saggistica, letteratura, dialoghi;
#   7) spia dei residui di lingua sorgente.
#
# Pulizia 1.99.2: tolte le regole costruite su singole frasi dei testi di
# prova (consiglio di amministrazione, Leopardi, "sa di pesce", ...), che non
# servivano a testi nuovi e potevano peggiorarli; "Who knows." -> "Dunno."
# vale solo nei dialoghi; le virgolette italiane solo in letteratura e
# dialoghi; tolto il "bilanciamento" automatico delle virgolette, che
# aggiungeva caratteri a pollici e codice. Le stesse regole, se ancora
# presenti nei file dell'utente, vengono ignorate (RITIRATE).
#
# Il modulo NON parla col motore: la traduzione del glossario passa da un
# callback fornito dal programma. Tutto resta sul computer.
#
# Riga di comando:
#   python3 raglin.py hints file.md it en
#   python3 raglin.py fix file.md en [uso]
#   python3 raglin.py termini file.md it
#   python3 raglin.py tm src.md dst.md it en
#   python3 raglin.py stats
import os
import re
import json
import math
import hashlib
from collections import Counter

_XDG = lambda var, alt: os.environ.get(var) or os.path.join(os.path.expanduser("~"), alt)
# Voci personali dell'utente (vincono su quelle del pacchetto).
DIR_RAG     = os.path.join(_XDG("XDG_CONFIG_HOME", ".config"), "ruscatranslator", "rag")
# Memoria di traduzione e glossari: dati dell'utente, non configurazione.
DIR_DATI    = os.path.join(_XDG("XDG_DATA_HOME", ".local/share"), "ruscatranslator")
DIR_RAG_PKG = "/usr/share/ruscatranslator/rag"
DIR_RAG_SRC = os.path.join(os.path.dirname(os.path.abspath(__file__)), "rag")
TM_MAX      = 20000
CODA_CONT   = 240               # caratteri di continuita' tra chunk
RE_FENCE    = re.compile(r"```.*?```", re.S)

COPPIE_SUPPORTATE = {("it", "en"), ("en", "it")}

STOP_IT = set("che di il la per non sono come e a da in su con tra fra una uno lo gli le".split())
STOP_EN = set("the of and to in that is with for as was were be been it its this these on at by from".split())
STOP_TUTTI = STOP_IT | STOP_EN

PESI = {"pragmatica": 3, "idioma": 3, "falso_amico": 3, "regola": 3,
        "letteratura": 2, "terminologia": 2, "connettivo": 2, "hedging": 2,
        "culturema": 2, "metafora": 2, "convenzione": 3, "latinismo": 1,
        "stile": 3, "postfix": 0}

REGOLE_QUALITA = (
    " QUALITY RULES: prefer target-language idiomatic equivalents over literal "
    "calques; preserve puns and wordplay creatively where possible; never invent "
    "or guess specifics absent from the source (dates, months, names, numbers): "
    "render them generically (e.g. 'the 3rd of this month'); keep metaphors and "
    "literary images intact; translate interjections and exclamations by their "
    "pragmatic force, never literally; preserve academic and professional titles "
    "(Dr., Prof., Eng.) verbatim, never downgrade them to Mr./Mrs./Ms.")

PROMEMORIA_RESIDUI = (
    " REMINDER: your previous attempt left source-language sentences "
    "untranslated. Translate EVERY sentence inline now, with no exceptions.")

# ── Prompt di DOMINIO/USO (4 domini, combinabili con l'unico stile) ─────────
USI = {
    "generale": {
        "nome": "Generale / General",
        "prompt": ""},
    "saggistica": {
        "nome": "Saggistica / Essayistic",
        "prompt": (" DOMAIN: essayistic and non-fiction prose. Vary connectives "
                   "(do not repeat moreover/indeed/however in the same paragraph); "
                   "prefer strong verbs over heavy nominalizations; keep the "
                   "source's hedging faithful (it is held that, tends to, by and "
                   "large); render bibliographic abbreviations per target "
                   "conventions (cfr.→cf., segg.→ff., ivi→ibid., trad. it.→trans. "
                   "into Italian); write centuries as 'the sixteenth century' and "
                   "decades as 'the 1980s'; keep ONE consistent rendering for each "
                   "recurring domain term.")},
    "letteratura": {
        "nome": "Letteratura / Literary",
        "prompt": (" DOMAIN: literary prose and poetry. Preserve line breaks, "
                   "stanza structure and images literally; never paraphrase "
                   "verses into prose; keep metaphors intact and never swap an "
                   "image for a near-synonym that changes it; keep tense and point of view "
                   "consistent across chunks; preserve free indirect discourse; "
                   "choose rhythm-aware wording; add no explanatory glosses inside "
                   "quoted verse.")},
    "dialoghi": {
        "nome": "Dialoghi / Dialogue",
        "prompt": (" DOMAIN: dialogue and spoken exchange. Use colloquial, "
                   "idiomatic spoken register; translate interjections by "
                   "pragmatic force (Magari!→I wish!/Like hell!/As if!, "
                   "Figurati!→No way!/Don't mention it!, Boh→Dunno/Beats me); "
                   "allow contractions (don't, can't, I've) and sentence fragments "
                   "where natural; keep turns short and punchy; render youth slang "
                   "with live English equivalents; prefer natural flow over "
                   "literal closeness WITHOUT adding or omitting information.")},
}
USO_ORDER = ("generale", "saggistica", "letteratura", "dialoghi")


def prompt_uso(cod):
    return USI.get(cod, USI["generale"])["prompt"]


# ── Seme della base di conoscenza ──────────────────────────────────────────
SEME = [
 {"tipo": "pragmatica", "it": "Magari!", "en": "I wish! / If only!",
  "rx_it": r"\bmagari\s*!", "rx_en": r"\bI\s+wish\s*!|\bIf\s+only\s*!",
  "nota": "desiderativo/deluso",
  "warn": "NON 'Maybe!', NON 'Oh yes!', NON 'Not really!': usa I wish!/If only!"},
 {"tipo": "pragmatica", "it": "Figurati!", "en": "No way! / Don't mention it!",
  "rx_it": r"\bfigurati\s*!", "rx_en": r"\bNo\s+way\s*!|\bDon'?t\s+mention\s+it\s*!",
  "nota": "sarcastico = smentita; in risposta a un grazie = you're welcome"},
 {"tipo": "pragmatica", "it": "Boh", "en": "Dunno / Beats me",
  "rx_it": r"\bboh\b", "rx_en": r"\bDunno\b|\bBeats\s+me\b"},
 {"tipo": "pragmatica", "it": "Vabbè", "en": "Whatever / Oh well",
  "rx_it": r"\bvabbe'??\b", "rx_en": r"\bWhatever\b|\bOh\s+well\b"},
 {"tipo": "pragmatica", "it": "Ma quando mai!", "en": "As if! / No way!",
  "rx_it": r"\bma\s+quando\s+mai\s*!", "rx_en": r"\bAs\s+if\s*!"},
 {"tipo": "idioma", "it": "avere un diavolo per capello", "en": "be in a foul mood",
  "rx_it": r"diavolo\s+per\s+capell[oi]", "rx_en": r"foul\s+mood"},
 {"tipo": "idioma", "it": "svegliarsi con la luna storta", "en": "wake up on the wrong side of the bed",
  "rx_it": r"luna\s+(storta|di\s+traverso)", "rx_en": r"wrong\s+side\s+of\s+the\s+bed"},
 {"tipo": "idioma", "it": "andare a rotoli", "en": "go down the drain",
  "rx_it": r"(andato|andare|va)\s+a\s+rotoli", "rx_en": r"(went|go|goes)\s+down\s+the\s+drain"},
 {"tipo": "idioma", "it": "fare il muso lungo", "en": "pull a long face",
  "rx_it": r"muso\s+lungo", "rx_en": r"(pull|pulled|wear)\s+a\s+long\s+face"},
 {"tipo": "idioma", "it": "non fare il muso lungo", "en": "don't pull a long face",
  "rx_it": r"non\s+fare\s+(il|quel)\s+muso\s+lungo|non\s+fare\s+quella\s+faccia\s+lunga",
  "warn": "GRAVE: preservare SEMPRE la negazione: 'don't pull a long face'; 'pull a long face' da solo ribalta il senso"},
 {"tipo": "idioma", "it": "gettare la spugna", "en": "throw in the towel",
  "rx_it": r"(gettato|gettare|getta)\s+la\s+spugna", "rx_en": r"(thrown|throw|threw)\s+in\s+the\s+towel"},
 {"tipo": "idioma", "it": "dire la sua", "en": "have one's say / say one's piece",
  "rx_it": r"dire\s+la\s+sua", "rx_en": r"(have|had)\s+(her|his|their)\s+say|say\s+(her|his)\s+piece"},
 {"tipo": "idioma", "it": "pescare nelle tasche", "en": "fish in one's pockets (preserve the pun!)",
  "rx_it": r"pesc(ando|are|a)\s+(nelle|in|nelle\s+sue)\s+tasc",
  "rx_en": r"fish(ing)?\s+in\s+(his|her|their)\s+pockets"},
 {"tipo": "idioma", "it": "fra il dire e il fare", "en": "between saying and doing / 'twixt cup and lip",
  "rx_it": r"fra\s+il\s+dire\s+e\s+il\s+fare", "rx_en": r"'twixt\s+cup\s+and\s+lip"},
 {"tipo": "idioma", "it": "se fosse il caso di", "en": "whether it is/was worth …-ing (opportunità, non tempo)",
  "rx_it": r"se\s+fosse\s+il\s+caso\s+di", "rx_en": r"whether\s+it\s+(is|was)\s+worth"},
 {"tipo": "falso_amico", "it": "attuale", "en": "topical / relevant / present-day",
  "rx_it": r"\battual(e|mente|i)\b", "rx_en": r"\btopical\b|\bpresent-day\b",
  "warn": "IT 'attuale' ≠ EN 'current' (current è solo temporale): usa topical/relevant"},
 {"tipo": "falso_amico", "it": "eventualmente", "en": "if necessary / possibly",
  "rx_it": r"\beventualmente\b", "rx_en": r"\bif\s+necessary\b",
  "warn": "≠ 'eventually' (che significa 'alla fine')"},
 {"tipo": "falso_amico", "it": "pretendere", "en": "demand / claim",
  "rx_it": r"\bpretend(e|eva|ono|ere)\b", "rx_en": r"\bdemand(s|ed)?\b|\bclaim(s|ed)?\b",
  "warn": "≠ 'pretend' (che significa 'fingere')"},
 {"tipo": "falso_amico", "it": "libreria", "en": "bookshop / bookstore",
  "rx_it": r"\blibreria\b", "rx_en": r"\bbookshop\b|\bbookstore\b",
  "warn": "≠ 'library' (che significa 'biblioteca')"},
 {"tipo": "falso_amico", "it": "comportare", "en": "to entail / to involve",
  "rx_it": r"\bcomport\w*", "rx_en": r"\bentail(s|ed)?\b|\binvolve(s|d)?\b",
  "warn": "≠ 'to behave'"},
 {"tipo": "regola", "it": "Dott. / Prof. / Ing. (titoli)", "en": "Dr. / Prof. / Eng. — preserve titles verbatim",
  "rx_it": r"\b(Dott|Prof|Ing)\.",
  "warn": "mai degradare titoli accademici/professionali a Mr./Mrs./Ms."},
 {"tipo": "letteratura", "it": "naufragar / naufragio", "en": "shipwreck / to be shipwrecked (Leopardi, L'Infinito)",
  "rx_it": r"\bnaufrag\w*", "rx_en": r"\bshipwreck\w*",
  "warn": "in poesia l'immagine è il naufragio: shipwreck, non sinking/drowning/drifting"},
 {"tipo": "regola", "it": "3 corrente / 3 c.m.", "en": "the 3rd of this month",
  "rx_it": r"\b\d{1,2}\s*(corrente|c\.m\.|del\s+corrente\s+mese)",
  "rx_en": r"the\s+\d{1,2}(st|nd|rd|th)\s+of\s+this\s+month",
  "warn": "non inventare mai il nome del mese se assente nella sorgente"},
 {"tipo": "regola", "it": "smart working", "en": "remote work / working from home / WFH",
  "rx_it": r"\bsmart\s+working\b", "rx_en": r"\bremote\s+work\b|\bworking\s+from\s+home\b|\bWFH\b",
  "warn": "'smart working' è un italianismo inesistente in EN nativo: tradurre SEMPRE"},
 {"tipo": "terminologia", "it": "restauro conservativo", "en": "conservative restoration"},
 {"tipo": "terminologia", "it": "vincolo paesaggistico", "en": "landscape protection order"},
 {"tipo": "terminologia", "it": "Soprintendenza", "en": "Superintendency (heritage office)",
  "nota": "prima occorrenza: apposizione minima"},
 {"tipo": "terminologia", "it": "decreto legislativo", "en": "legislative decree"},
 {"tipo": "terminologia", "it": "liceo classico", "en": "classical lyceum (upper-secondary school)"},
 {"tipo": "terminologia", "it": "medico legale", "en": "forensic pathologist"},
 {"tipo": "terminologia", "it": "osso ioide", "en": "hyoid bone"},
 {"tipo": "terminologia", "it": "petecchie subcongiuntivali", "en": "subconjunctival petechiae"},
 {"tipo": "terminologia", "it": "asfissia meccanica", "en": "mechanical asphyxia"},
]

# ── POST-FIX: catena completa e ordinata (il fix finale vive qui) ──────────
# L'ordine e' quello di applicazione: prima lo sfoltimento del sintagma,
# poi la riscrittura dell'inversione sul testo gia' normalizzato.
POSTFIX_SEME = [
 # Ogni voce vale per tutti i domini, salvo "usi" (lista di domini).
 # --- EN: italianismi --------------------------------------------------------
 {"tipo": "postfix", "rx_en": r"\bsmart\s+working\b", "fix_en": "remote work",
  "nota": "italianismo aziendale: in inglese si dice remote work"},
 {"tipo": "postfix", "rx_en": r"\bWho knows\.", "fix_en": "Dunno.",
  "usi": ["dialoghi"],
  "nota": "registro parlato: 'Boh.' = 'Dunno.' (solo nei dialoghi)"},
 # --- EN: tipografia (caporali -> virgolette) --------------------------------
 {"tipo": "postfix", "rx_en": r"«\"", "fix_en": "\"",
  "nota": "caporale doppio prima di una virgoletta: rimuovere"},
 {"tipo": "postfix", "rx_en": r"\"»", "fix_en": "\"",
  "nota": "caporale doppio dopo una virgoletta: rimuovere"},
 {"tipo": "postfix", "rx_en": r"«\s?", "fix_en": "\"",
  "nota": "in inglese non si usano i caporali: virgolette aperte"},
 {"tipo": "postfix", "rx_en": r"\s?»", "fix_en": "\"",
  "nota": "in inglese non si usano i caporali: virgolette chiuse"},
 # --- IT: calchi e titoli -----------------------------------------------------
 {"tipo": "postfix", "rx_it": r"\bTu desideri\s*!", "fix_it": "Magari!",
  "nota": "'You wish!' non è 'Tu desideri!', è 'Magari!'"},
 {"tipo": "postfix", "rx_it": r"\bIo desidero\s*!", "fix_it": "Magari!",
  "nota": "variante in prima persona dello stesso calco"},
 {"tipo": "postfix", "rx_it": r"\bDr\.(?= [A-ZÀ-Ý])", "fix_it": "Dott.",
  "nota": "in italiano il titolo davanti al nome è Dott."},
 # --- IT: tipografia (solo testi letterari e dialoghi) -----------------------
 {"tipo": "postfix", "rx_it": r"\"([^\"\n]{1,300})\"", "fix_it": r"«\1»",
  "usi": ["letteratura", "dialoghi"],
  "nota": "convenzione editoriale italiana: dialoghi e citazioni in caporali"},
]

# Regole tolte nella 1.99.2: costruite su singole frasi dei testi di prova o
# troppo larghe. Se sono ancora nei file dell'utente (vecchio
# seed_linguistico.json) vengono ignorate.
RITIRATE = {
    r"(worth|worthwhile) making (her|his|their) own contribution",
    r"As if!(?= Don't make me laugh)",
    r"in a direction contrary to",
    r"Should the board of directors have decided contrary",
    r"Had the board of directors decided contrary",
    r"\bshipwrecking\b(?= is sweet)",
    r"\b(sinking|drowning|drifting)\b(?= is sweet)",
    r"\bsmell(s|ed|ing)?\b(?= (?:like|of) (?:fish|soap|nothing))",
    r"«", r"»",
    "Translate:\\s*«",
}

# ── Spia anti-residui: marcatori DISTINTIVI della sorgente ─────────────────
RESIDUI_MARK = {
    "it":    (" perché ", " anche ", " nella ", " sulla ", " ovvero ", " dunque "),
    "en":    (" because ", " whether ", " though ", " indeed ", " however "),
    "de":    (" weil ", " auch ", " oder ", " nicht ", " sondern "),
    "fr":    (" parce ", " aussi ", " avec ", " donc ", " mais "),
    "es":    (" porque ", " también ", " ahora ", " luego ", " pero "),
    "pt-BR": (" porque ", " também ", " agora ", " então ", " mas "),
    "pl":    (" ponieważ ", " także ", " teraz ", " więc ", " ale "),
}
RESIDUI_SCRIPT = {
    "ru": re.compile("[\u0400-\u04ff]"),
    "zh": re.compile("[\u4e00-\u9fff]"),
    "ja": re.compile("[\u3040-\u30ff]"),
}
GRUPPO_SCRIPT = {"ru": "cir", "zh": "cjk", "ja": "cjk"}
SOGLIA_MARK = 4

_KB = None
_RX_CACHE = {}
_FIX_CACHE = {}


def attivo(src, tgt):
    return (src, tgt) in COPPIE_SUPPORTATE


# ------------------------------------------------------------------ KB
def _ensure_user_dir():
    """Crea la cartella delle voci personali con un file vuoto da riempire.
    Il seme resta nel programma: copiarlo nella cartella utente (come fino
    alla 1.99.1) congelava la base di conoscenza alla prima installazione."""
    try:
        os.makedirs(DIR_RAG, exist_ok=True)
        p = os.path.join(DIR_RAG, "personale.json")
        if not os.path.isfile(p):
            with open(p, "w", encoding="utf-8") as f:
                f.write("[]\n")
    except OSError:
        pass


def _ritirata(e):
    return any(e.get(k) in RITIRATE for k in ("rx_en", "rx_it"))


def carica_kb():
    """Voci dell'utente, poi file del pacchetto, poi il seme interno. A parità
    di (tipo, it, en) vince la prima trovata."""
    global _KB
    if _KB is not None:
        return _KB
    _ensure_user_dir()
    entries, visti = [], set()

    def aggiungi(lista):
        for e in lista:
            if not isinstance(e, dict) or _ritirata(e):
                continue
            k = (e.get("tipo"), e.get("it"), e.get("en"))
            if k not in visti:
                visti.add(k)
                entries.append(e)

    for d in (DIR_RAG, DIR_RAG_PKG, DIR_RAG_SRC):
        if not os.path.isdir(d):
            continue
        for nome in sorted(os.listdir(d)):
            if not nome.endswith(".json") or nome.startswith("glossario_"):
                continue
            try:
                with open(os.path.join(d, nome), encoding="utf-8") as f:
                    dati = json.load(f)
            except (OSError, ValueError):
                continue
            if isinstance(dati, list):
                aggiungi(dati)
    aggiungi(SEME)
    _KB = entries
    return _KB


def ricarica_kb():
    """Da chiamare dopo modifiche manuali ai JSON senza riavviare."""
    global _KB, _FIX_CACHE
    _KB = None
    _FIX_CACHE = {}
    return carica_kb()


def _rx(e, lato):
    chiave = (e.get("tipo"), e.get(lato, ""), e.get("rx_" + lato, ""))
    if chiave in _RX_CACHE:
        return _RX_CACHE[chiave]
    pat = e.get("rx_" + lato)
    if not pat and e.get(lato):
        pat = r"(?<!\w)" + re.escape(e[lato]) + r"(?!\w)"
    rx = None
    if pat:
        try:
            rx = re.compile(pat, re.I)
        except re.error:
            rx = None
    _RX_CACHE[chiave] = rx
    return rx


# ------------------------------------------------------------------ retrieval
def suggerimenti(testo, src, tgt, max_hint=14):
    if not attivo(src, tgt):
        return []
    corpo = RE_FENCE.sub(" ", testo)[:12000]
    trovati = []
    for e in carica_kb():
        if e.get("tipo") == "postfix":
            continue
        rx = _rx(e, src)
        if rx is None:
            continue
        m = rx.search(corpo)
        if m:
            trovati.append((PESI.get(e.get("tipo"), 1), -m.start(), e, m.group(0)))
    trovati.sort(key=lambda t: (-t[0], -t[1]))
    res, visti = [], set()
    for _p, _s, e, match in trovati:
        k = (e.get("it"), e.get("en"))
        if k in visti:
            continue
        visti.add(k)
        res.append((e, match))
        if len(res) >= max_hint:
            break
    return res


def blocco_hint(hints, tgt, glossario=None, tm=None, coda=""):
    righe = []
    if hints:
        righe.append("[LINGUISTIC RAG — binding equivalents for this chunk]")
        for e, match in hints:
            val = e.get(tgt) or e.get("en") or e.get("it")
            riga = f"- {e.get('tipo', '?').upper()}: \"{match}\" → \"{val}\""
            if e.get("nota"):
                riga += f" ({e['nota']})"
            if e.get("warn"):
                riga += f" [WARN: {e['warn']}]"
            righe.append(riga)
    if glossario:
        righe.append("[DOCUMENT GLOSSARY — keep consistent across chunks]")
        for k, v in list(glossario.items())[:20]:
            righe.append(f"- {k} → {v}")
    if tm:
        righe.append("[TRANSLATION MEMORY — style/terminology reference, do not copy verbatim]")
        for s, t, sc in tm:
            righe.append(f"- SRC: {s[:180]} | REF: {t[:180]}  (sim {sc})")
    if coda:
        righe.append("[CONTINUITY CONTEXT — tail of the previous translated chunk: "
                     "keep terminology and tone consistent; do NOT repeat or "
                     "include it in the output]")
        righe.append(coda)
    if not righe:
        return ""
    righe.append("Apply the equivalents above; adapt minimally only if the "
                 "context strictly conflicts.")
    return "\n" + "\n".join(righe) + "\n"


# ------------------------------------------------------------------ residui
def contiene_residui(testo, src, tgt, soglia=None):
    """True se nel testo tradotto restano tracce riconoscibili della sorgente."""
    if not attivo(src, tgt):
        return False
    if GRUPPO_SCRIPT.get(src) and GRUPPO_SCRIPT.get(src) == GRUPPO_SCRIPT.get(tgt):
        return False
    corpo = RE_FENCE.sub(" ", testo[:8000])
    rx = RESIDUI_SCRIPT.get(src)
    if rx is not None:
        return bool(rx.search(corpo))
    marks = RESIDUI_MARK.get(src)
    if not marks:
        return False
    lim = SOGLIA_MARK if soglia is None else soglia
    low = " " + corpo.lower().replace("\n", " ") + " "
    return sum(low.count(m) for m in marks) >= lim


# ------------------------------------------------------------------ post-fix
def _fix_entries(tgt, uso="generale"):
    chiave = (tgt, uso)
    if chiave in _FIX_CACHE:
        return _FIX_CACHE[chiave]
    lista, visti = [], set()
    sorgenti = list(POSTFIX_SEME) + [e for e in carica_kb()
                                     if e.get("tipo") == "postfix"]
    for e in sorgenti:
        pat = e.get("rx_" + tgt)
        if not pat or pat in visti or pat in RITIRATE:
            continue
        usi = e.get("usi")
        if usi and uso not in usi:
            continue
        visti.add(pat)
        try:
            rx = re.compile(pat, re.I)
        except re.error:
            continue
        lista.append({"rx": rx, "fix": e.get("fix_" + tgt, ""),
                      "nota": e.get("nota", pat)})
    _FIX_CACHE[chiave] = lista
    return lista


# Parti del Markdown da non toccare mai: blocchi e frammenti di codice,
# indirizzi dei link e delle immagini, tag HTML, URL.
RE_PROTETTO = re.compile(r"```.*?```|`[^`\n]+`|\]\([^)\n]*\)|<[^>\n]+>|https?://\S+", re.S)


def post_process(testo, tgt, uso="generale"):
    """Correzioni deterministiche dopo la generazione, fuori dalle parti
    protette. Ritorna (testo, note delle correzioni applicate)."""
    regole = _fix_entries(tgt, uso)
    if not regole:
        return testo, []
    protetti = []

    def metti_da_parte(m):
        protetti.append(m.group(0))
        return f"\x00{len(protetti) - 1}\x00"
    out = RE_PROTETTO.sub(metti_da_parte, testo)
    applicati = []
    for e in regole:
        nuovo = e["rx"].sub(e["fix"], out)
        if nuovo != out:
            out = nuovo
            applicati.append(e["nota"])
    out = re.sub("\x00(\\d+)\x00", lambda m: protetti[int(m.group(1))], out)
    return out, applicati


# ------------------------------------------------------------------ glossario
def estrai_termini(testo, src, max_term=24):
    stop = STOP_IT if src == "it" else (STOP_EN if src == "en" else STOP_TUTTI)
    corpo = RE_FENCE.sub(" ", testo)
    parole = re.findall(r"[A-Za-zÀ-ÖØ-öø-ÿ']+", corpo)
    freq, caps, prev = Counter(), Counter(), None
    for w in parole:
        lw = w.lower()
        if lw in stop or len(lw) < 3:
            prev = None
            continue
        freq[lw] += 1
        if w[:1].isupper() and prev is not None:
            caps[prev + " " + lw] += 1
        prev = lw
    cand = [(t, c) for t, c in caps.items() if c >= 2]
    cand += [(t, c) for t, c in freq.items() if c >= 4]
    cand.sort(key=lambda x: -x[1])
    return [t for t, _ in cand[:max_term]]


def _migra_dati():
    """Fino alla 1.99.1 memoria di traduzione e glossari stavano accanto
    alla configurazione: si spostano una volta nella cartella dei dati."""
    if not os.path.isdir(DIR_RAG):
        return
    for nome in os.listdir(DIR_RAG):
        if (nome.startswith("tm_") and nome.endswith(".jsonl")) or nome.startswith("glossario_"):
            try:
                os.makedirs(DIR_DATI, exist_ok=True)
                dest = os.path.join(DIR_DATI, nome)
                if not os.path.exists(dest):
                    os.replace(os.path.join(DIR_RAG, nome), dest)
            except OSError:
                pass


def _hash_doc(testo, src, tgt):
    return hashlib.sha1((testo[:20000] + src + tgt).encode("utf-8")).hexdigest()[:16]


def glossario_cache_get(testo, src, tgt):
    p = os.path.join(DIR_DATI, f"glossario_{_hash_doc(testo, src, tgt)}.json")
    if os.path.isfile(p):
        try:
            with open(p, encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return None


def glossario_cache_put(testo, src, tgt, glossario):
    os.makedirs(DIR_DATI, exist_ok=True)
    p = os.path.join(DIR_DATI, f"glossario_{_hash_doc(testo, src, tgt)}.json")
    with open(p, "w", encoding="utf-8") as f:
        json.dump(glossario, f, ensure_ascii=False, indent=1)


def parse_glossario(raw):
    m = re.search(r"\{.*\}", raw or "", re.S)
    if not m:
        return {}
    try:
        d = json.loads(m.group(0))
    except Exception:
        return {}
    return {str(k): str(v) for k, v in d.items()
            if isinstance(v, (str, int, float)) and str(v).strip()}


# ------------------------------------------------------------------ memoria TM
def _tm_path(src, tgt):
    _migra_dati()
    return os.path.join(DIR_DATI, f"tm_{src}_{tgt}.jsonl")


def _tok(s):
    return set(re.findall(r"[a-zà-öø-ÿ']{3,}", s.lower())) - STOP_TUTTI


def indica_tm(testo_src, testo_tgt, src, tgt):
    if not attivo(src, tgt):
        return 0
    ss = [s.strip() for s in re.split(r"\n\s*\n", testo_src) if len(s.strip()) > 40]
    tt = [t.strip() for t in re.split(r"\n\s*\n", testo_tgt) if len(t.strip()) > 40]
    # Si allinea per posizione: se il numero di paragrafi non coincide,
    # l'allineamento sarebbe sbagliato e inquinerebbe la memoria.
    if not ss or len(ss) != len(tt):
        return 0
    n = len(ss)
    os.makedirs(DIR_DATI, exist_ok=True)
    with open(_tm_path(src, tgt), "a", encoding="utf-8") as f:
        for i in range(n):
            f.write(json.dumps({"s": ss[i][:1500], "t": tt[i][:1500]},
                               ensure_ascii=False) + "\n")
    try:
        with open(_tm_path(src, tgt), encoding="utf-8") as f:
            righe = f.readlines()
        if len(righe) > TM_MAX:
            with open(_tm_path(src, tgt), "w", encoding="utf-8") as f:
                f.writelines(righe[-TM_MAX:])
    except Exception:
        pass
    return n


def cerca_tm(chunk, src, tgt, k=2, soglia=0.30):
    if not attivo(src, tgt):
        return []
    p = _tm_path(src, tgt)
    if not os.path.isfile(p):
        return []
    qc = _tok(chunk[:4000])
    if not qc:
        return []
    res = []
    with open(p, encoding="utf-8") as f:
        for riga in f:
            try:
                rec = json.loads(riga)
            except Exception:
                continue
            ts = _tok(rec.get("s", ""))
            if not ts:
                continue
            inter = len(qc & ts)
            if not inter:
                continue
            sc = inter / math.sqrt(len(qc) * len(ts))
            if sc >= soglia:
                res.append((sc, rec["s"], rec["t"]))
    res.sort(key=lambda x: -x[0])
    return [(s, t, round(sc, 2)) for sc, s, t in res[:k]]


# ------------------------------------------------------------------ sessione
class SessioneRAG:
    """Stato RAG di una traduzione: glossario, continuita', hint per chunk."""

    def __init__(self, testo, src, tgt, traduci_termini=None, max_hint=14):
        self.src, self.tgt = src, tgt
        self.max_hint = max_hint
        self.glossario = {}
        self._coda = ""
        self.ultimi_hint = 0
        self.ultimi_tm = 0
        if not attivo(src, tgt):
            return
        g = glossario_cache_get(testo, src, tgt)
        if g is None and traduci_termini is not None:
            termini = estrai_termini(testo, src)
            if termini:
                try:
                    g = traduci_termini(termini) or {}
                except Exception:
                    g = {}
                glossario_cache_put(testo, src, tgt, g)
        self.glossario = g or {}

    def hint(self, chunk):
        if not attivo(self.src, self.tgt):
            return ""
        hints = suggerimenti(chunk, self.src, self.tgt, max_hint=self.max_hint)
        tm = cerca_tm(chunk, self.src, self.tgt)
        self.ultimi_hint, self.ultimi_tm = len(hints), len(tm)
        return blocco_hint(hints, self.tgt, self.glossario, tm, self._coda)

    def registra(self, tradotto):
        self._coda = (tradotto or "").strip()[-CODA_CONT:]


def nuova_sessione(testo, src, tgt, traduci_termini=None, max_hint=14):
    return SessioneRAG(testo, src, tgt, traduci_termini, max_hint)


# ------------------------------------------------------------------ utilità/CLI
def stats():
    kb = carica_kb()
    per_tipo = Counter(e.get("tipo", "?") for e in kb)
    out = [f"Voci KB: {len(kb)} — " +
           ", ".join(f"{k}: {v}" for k, v in sorted(per_tipo.items())),
           f"Post-fix generali: {len(_fix_entries('en'))} (en), "
           f"{len(_fix_entries('it'))} (it)",
           f"Usi disponibili: {', '.join(USO_ORDER)}",
           f"Voci personali: {DIR_RAG}", f"Memoria di traduzione: {DIR_DATI}"]
    _migra_dati()
    if os.path.isdir(DIR_DATI):
        for nome in sorted(os.listdir(DIR_DATI)):
            if nome.startswith("tm_") and nome.endswith(".jsonl"):
                with open(os.path.join(DIR_DATI, nome), encoding="utf-8") as f:
                    out.append(f"{nome}: {sum(1 for _ in f)} segmenti")
    return "\n".join(out)


if __name__ == "__main__":
    import sys
    cmd = sys.argv[1] if len(sys.argv) > 1 else "stats"
    if cmd == "hints" and len(sys.argv) >= 5:
        testo = open(sys.argv[2], encoding="utf-8").read()
        h = suggerimenti(testo, sys.argv[3], sys.argv[4], max_hint=50)
        print(blocco_hint(h, sys.argv[4]) or "Nessun suggerimento trovato.")
    elif cmd == "fix" and len(sys.argv) >= 4:
        testo = open(sys.argv[2], encoding="utf-8").read()
        out, appl = post_process(testo, sys.argv[3],
                                 sys.argv[4] if len(sys.argv) > 4 else "generale")
        print(out)
        if appl:
            print("\n[post-fix applicati]: " + "; ".join(appl), file=sys.stderr)
    elif cmd == "termini" and len(sys.argv) >= 4:
        testo = open(sys.argv[2], encoding="utf-8").read()
        print("\n".join(estrai_termini(testo, sys.argv[3])) or "Nessun termine.")
    elif cmd == "tm" and len(sys.argv) >= 6:
        a = open(sys.argv[2], encoding="utf-8").read()
        b = open(sys.argv[3], encoding="utf-8").read()
        print(indica_tm(a, b, sys.argv[4], sys.argv[5]), "segmenti indicizzati")
    else:
        print(stats())