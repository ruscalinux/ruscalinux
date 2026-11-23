# -*- coding: utf-8 -*-
# rusca_speech.py — RuscaLinux OS Apps 1.99.3 — GPL-3.0-or-later
#
# Il testo che va alla voce, che non è sempre quello dei sottotitoli:
#
#   * numeri in lettere: «16» detto da solo, senza contesto, la voce lo
#     sbagliava; «sedici» no. Con python3-num2words (LGPL-2.1, pacchetto
#     Debian); senza, i numeri restano cifre;
#   * lessico delle pronunce: parola<TAB>come scriverla per la voce, per le
#     parole che il modello sbaglia sempre allo stesso modo («tienila →
#     tiènila»). Un file di sistema e uno dell'utente, per lingua;
#   * omografi: parole che si scrivono uguali e si dicono diversamente
#     («princìpi» e «prìncipi»): il modello di traduzione, che conosce il
#     senso, ne segna l'accento (stress_request()), e si accetta solo se il
#     resto del testo resta identico (apply_stress()).
#
# I sottotitoli restano scritti normalmente.
import os
import re
import unicodedata

try:
    import num2words as _num2words
except ImportError:          # python3-num2words non installato: cifre
    _num2words = None

# Lingue di num2words per le lingue del doppiaggio (il cinese manca).
NUM_LANG = {"it": "it", "en": "en", "de": "de", "fr": "fr", "es": "es", "pt": "pt",
            "ru": "ru", "ja": "ja", "ko": "ko"}
# Separatore dei decimali: la virgola, tranne in inglese e nelle lingue
# asiatiche.
DECIMAL_POINT = {"en", "ja", "ko", "zh"}
PERCENT = {"it": "per cento", "en": "percent", "de": "Prozent", "fr": "pour cent",
           "es": "por ciento", "pt": "por cento", "ru": "процентов"}


def numbers_available():
    return _num2words is not None


def _number_re(lang):
    if lang in DECIMAL_POINT:
        thousands, decimal = ",", r"\."
    else:
        thousands, decimal = r"[.\u00a0\u202f ]", ","
    return re.compile(
        r"(?<![\w.,:/\-])(\d{1,3}(?:" + thousands + r"\d{3})+|\d+)(?:" + decimal +
        r"(\d+))?(\s?%)?(?![\w:/°ºª]|[.,]\d)")


def spell_numbers(text, lang):
    """I numeri in lettere, nella lingua della voce: interi, decimali,
    migliaia e percentuali. Orari, date con «/», codici e numeri attaccati
    a parole restano come sono."""
    nl = NUM_LANG.get(lang)
    if _num2words is None or not nl:
        return text

    def sub(m):
        whole = re.sub(r"\D", "", m.group(1))
        try:
            if m.group(2):
                words = _num2words.num2words(float(f"{whole}.{m.group(2)}"), lang=nl)
            else:
                words = _num2words.num2words(int(whole), lang=nl)
        except (NotImplementedError, ValueError, OverflowError, TypeError):
            return m.group(0)
        if lang == "it":
            # num2words scrive «ventitre», «duemilaventitre»: in italiano
            # il «tre» finale di un composto vuole l'accento.
            words = re.sub(r"(\w{2,})tre\b", r"\1tré", words)
        if m.group(3):
            words += " " + PERCENT.get(lang, "%")
        return words
    return _number_re(lang).sub(sub, text)


# ── lessico ─────────────────────────────────────────────────────────────────
def load_lexicon(*paths):
    """{parola minuscola: come dirla} dai file (gli ultimi valgono di
    più). Righe «parola<TAB>pronuncia»; «#» comincia un commento."""
    lex = {}
    for path in paths:
        try:
            with open(path, encoding="utf-8") as f:
                for line in f:
                    line = line.rstrip("\n")
                    if not line.strip() or line.lstrip().startswith("#") or "\t" not in line:
                        continue
                    word, say = line.split("\t", 1)
                    word, say = word.strip(), say.strip()
                    if word and say and not say.startswith("[["):
                        lex[unicodedata.normalize("NFC", word.lower())] = say
        except OSError:
            continue
    return lex


def apply_lexicon(text, lex):
    """Ogni parola del lessico scritta come va detta, con la maiuscola
    iniziale se l'originale l'aveva."""
    if not lex:
        return text

    def sub(m):
        word = m.group(0)
        say = lex.get(unicodedata.normalize("NFC", word.lower()))
        if not say:
            return word
        return say[:1].upper() + say[1:] if word[:1].isupper() else say
    return re.sub(r"\w+", sub, unicodedata.normalize("NFC", text))


# ── omografi ────────────────────────────────────────────────────────────────
# Parole italiane comuni che cambiano accento (e senso): solo le frasi che
# ne contengono una vanno al modello.
HOMOGRAPHS = {
    "it": {"abitino", "agito", "agiti", "altero", "ambito", "ancora", "auguri", "balia",
           "capitano", "capiti", "capito", "circuito", "compito", "compiti", "condomini",
           "decade", "desideri", "esito", "frustino", "impari", "intimo", "intimi",
           "nettare", "nocciolo", "omero", "pagano", "principi", "regia", "retina",
           "ricordati", "rubino", "seguito", "subito", "tendine", "viola", "volano",
           "leggere", "perdono", "meta", "pero"},
}
_ACCENTS = {"\u0300", "\u0301"}


def strip_stress(text):
    """Il testo senza accenti gravi e acuti (per confrontare)."""
    nfd = unicodedata.normalize("NFD", text)
    return unicodedata.normalize("NFC", "".join(c for c in nfd if c not in _ACCENTS))


def needs_stress(text, lang):
    words = HOMOGRAPHS.get(lang)
    if not words:
        return False
    return any(w.lower() in words for w in re.findall(r"\w+", strip_stress(text)))


def stress_request(lines, lang):
    """Richiesta al modello: segnare l'accento solo sugli omografi.
    lines: [(numero, testo)]."""
    words = ", ".join(sorted(HOMOGRAPHS.get(lang, ())))
    system = (
        "You prepare Italian text for a text-to-speech voice. Some Italian words are "
        "written the same but stressed differently depending on the meaning (prìncipi / "
        "princìpi, àncora / ancóra, sùbito / subìto, capitàno / càpitano, càpiti / capìti, "
        "ricòrdati / ricordàti). In each line, add a written accent on the stressed vowel "
        "ONLY of such ambiguous words, according to their meaning in context: grave accent "
        "(à è ì ò ù) on open vowels and on i and u, acute accent (é ó) on closed e and o. "
        f"Ambiguous words to consider: {words}. Change nothing else: same words, same order, "
        "same punctuation, no other accents. Answer with exactly one line per input line, "
        "in the format `N|text`, nothing else.")
    user = "\n".join(f"{n}|{t}" for n, t in lines)
    return {"messages": [{"role": "system", "content": system},
                         {"role": "user", "content": user}],
            "temperature": 0.1, "max_tokens": 2048, "reasoning_effort": "none"}


def apply_stress(original, marked, lang):
    """La versione con gli accenti, accettata parola per parola: una parola
    può cambiare solo se è un omografo e cambia solo per un accento. Se il
    modello ha cambiato altro, quella parola resta com'era."""
    words = HOMOGRAPHS.get(lang, set())
    orig_tokens = re.findall(r"\w+|\W+", original)
    new_tokens = re.findall(r"\w+|\W+", unicodedata.normalize("NFC", marked or ""))
    if len(orig_tokens) != len(new_tokens):
        return original
    out = []
    for a, b in zip(orig_tokens, new_tokens):
        if a != b and strip_stress(a).lower() in words and strip_stress(b) == strip_stress(a):
            out.append(b)
        else:
            out.append(a)
    return "".join(out)


def speech_text(text, lang, lexicon=None, stressed=None):
    """Il testo da dare alla voce: omografi segnati (se c'è la versione
    con gli accenti), lessico, numeri in lettere."""
    if stressed:
        text = apply_stress(text, stressed, lang)
    text = apply_lexicon(text, lexicon or {})
    return spell_numbers(text, lang)


def lexicon_paths(base_dir, user_dir, lang):
    """File del lessico per una lingua: quello di sistema (accanto al
    programma) e quello dell'utente, che vale di più."""
    name = f"pronunce-{lang}.tsv"
    return [os.path.join(base_dir, name), os.path.join(user_dir, name)]
