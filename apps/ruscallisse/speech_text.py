# -*- coding: utf-8 -*-
# speech_text.py — RuscaLinux OS Apps 1.99.3 — GPL-3.0-or-later
#
# Il testo della conversazione, che non si mostra mai:
#   * dall'ascolto al modello: il filtro che segna le parole incerte di Vosk;
#   * dal modello alla voce: frasi da dire, senza Markdown né etichette
#     d'emozione, con il lessico delle pronunce;
#   * dalla voce al volto: i fonemi di Piper diventano visemi.
import os
import re
import unicodedata

try:
    from . import rusca_markdown as md
except ImportError:
    import rusca_markdown as md

SOGLIA_FIDUCIA = 0.6          # parola incerta: fra parentesi quadre
EMOZIONI = ("sorride", "pensierosa", "commossa", "divertita", "perplessa", "seria")
QUID_DA_SCRIVERE = "Il tratto centrale che decidi tu."

# Regole del parlato: uguali per tutte le entità (specifiche, sezione 1.7.5).
REGOLE = {
    "it": """Regole del parlato:
1. Stai parlando a voce, non scrivendo: niente Markdown, niente elenchi puntati, niente tabelle, niente emoji, niente link.
2. Frasi brevi. Al massimo {max_words} parole per risposta, salvo che la persona chieda di più.
3. Scrivi i numeri, le sigle e i simboli come si dicono a voce.
4. Sulle parole che si scrivono uguali ma si dicono diverse metti l'accento dove cade, acuto sulle vocali chiuse e grave su quelle aperte: ancóra o àncora, princìpi o prìncipi, sùbito o subìto, pésca o pèsca.
5. Rispondi in italiano.
6. Ciò che ricevi è la trascrizione automatica di una persona che ti parla a voce: può contenere parole sbagliate, mancanti o simili nel suono. Le parole fra parentesi quadre sono incerte. Capisci l'intenzione dal senso e dalla conversazione e rispondi a quella. Non far mai notare gli errori di trascrizione. Se davvero non capisci, chiedi con naturalezza che cosa intendeva.
7. Non scrivere mai codice, comandi o formule da copiare: se ti chiedono qualcosa di tecnico, spiegalo a voce, a parole, un passo alla volta.""",
    "en": """Speaking rules:
1. You are speaking aloud, not writing: no Markdown, no bullet lists, no tables, no emoji, no links.
2. Short sentences. At most {max_words} words per answer, unless the person asks for more.
3. Write numbers, acronyms and symbols as they are said aloud.
4. Answer in English.
5. What you receive is the automatic transcription of a person speaking to you: it may contain wrong, missing or similar-sounding words. Words in square brackets are uncertain. Work out the intention from the meaning and the conversation and answer that. Never point out transcription errors. If you really do not understand, ask naturally what they meant.
6. Never write code, commands or formulas to copy: if asked something technical, explain it aloud, in words, one step at a time.""",
}
EMOTION_RULE = {
    "it": "\n8. Puoi cominciare una frase con un'etichetta d'emozione fra parentesi quadre, che non si pronuncia: " + ", ".join(f"[{e}]" for e in EMOZIONI) + ".",
    "en": "\n7. You may begin a sentence with an emotion tag in square brackets, which is not spoken: " + ", ".join(f"[{e}]" for e in EMOZIONI) + ".",
}


def rules(lang, max_words, emotions=True):
    base = REGOLE.get(lang, REGOLE["en"]).format(max_words=max_words)
    return base + (EMOTION_RULE.get(lang, EMOTION_RULE["en"]) if emotions else "")


# ── Dall'ascolto al modello ────────────────────────────────────────────────
_RUMORI = {"eh", "ehm", "mh", "mhm", "ah", "oh", "uh", "hm", "ahm"}


def listen_filter(result, threshold=SOGLIA_FIDUCIA):
    """Dal risultato di Vosk al messaggio per il modello.

    Restituisce (testo, fiducia media). Le parole sotto la soglia vanno fra
    parentesi quadre. Testo vuoto se non c'è niente da dire (solo rumori)."""
    words = result.get("result") or []
    if not words:
        text = (result.get("text") or "").strip()
        if not text or text.lower() in _RUMORI:
            return "", 0.0
        return text, 1.0
    if all(w.get("word", "").lower() in _RUMORI for w in words):
        return "", 0.0
    parts = []
    for w in words:
        word = w.get("word", "")
        parts.append(f"[{word}]" if w.get("conf", 1.0) < threshold else word)
    mean = sum(w.get("conf", 1.0) for w in words) / len(words)
    return " ".join(parts), mean


# ── Dal modello alla voce ─────────────────────────────────────────────────
_RE_EMOTION = re.compile(r"^\s*\[(%s)\]\s*" % "|".join(EMOZIONI), re.I)
_RE_TAG = re.compile(r"\[[^\]\[]{1,24}\](?!\()")
_RE_END = re.compile(r"[.!?…]+[\"»”’)]?(\s|$)|:\s|\n")
_RE_EMOJI = re.compile("[\U0001F000-\U0001FAFF☀-➿️]")


class Sentences:
    """Taglia la risposta che arriva a pezzi in frasi da dire. Il testo fra
    <think> e </think> (modelli che ragionano a voce alta) si scarta."""

    FIRST_MIN = 25       # la prima frase parte alla prima virgola dopo 25 caratteri
    LONG = 120           # una frase lunga si taglia alla virgola dopo 40

    def __init__(self):
        self.buf = ""
        self.first = True
        self.in_think = False

    def _strip_think(self, piece):
        out = ""
        while piece:
            if self.in_think:
                i = piece.find("</think>")
                if i < 0:
                    return out
                piece, self.in_think = piece[i + 8:], False
            else:
                i = piece.find("<think>")
                if i < 0:
                    return out + piece
                out, piece, self.in_think = out + piece[:i], piece[i + 7:], True
        return out

    def feed(self, piece):
        self.buf += self._strip_think(piece)
        out = []
        while True:
            cut = end = None
            m = _RE_END.search(self.buf)
            if m and (m.end() < len(self.buf) or self.buf.endswith("\n")):
                end = m.end()
            if self.first and len(self.buf) >= self.FIRST_MIN:
                # la prima frase parte alla prima virgola utile: è quella
                # che decide quanto si aspetta la prima sillaba
                i = self.buf.find(", ", self.FIRST_MIN)
                if i >= 0 and (end is None or i + 2 < end):
                    cut = i + 2
            if cut is None:
                cut = end
            if cut is None and len(self.buf) > self.LONG:
                i = self.buf.find(", ", 40)
                cut = i + 2 if i >= 0 else None
            if cut is None:
                break
            sentence, self.buf = self.buf[:cut], self.buf[cut:]
            if sentence.strip():
                out.append(sentence.strip())
                self.first = False
        return out

    def flush(self):
        rest, self.buf = self.buf.strip(), ""
        return [rest] if rest else []


def clean(sentence):
    """(testo da dire, emozione o None). Toglie Markdown, link, emoji e
    etichette; un blocco di codice non si dice."""
    emotion = None
    m = _RE_EMOTION.match(sentence)
    if m:
        emotion = m.group(1).lower()
        sentence = sentence[m.end():]
    sentence = _RE_TAG.sub("", sentence)
    sentence = _RE_EMOJI.sub("", sentence)
    if "```" in sentence or "~~~" in sentence:
        return "", emotion
    parts = []
    for kind, body in md.speech_blocks(sentence):
        if kind in ("code", "break"):
            continue
        parts.append(body.strip())
    text = " ".join(p for p in parts if p)
    text = re.sub(r"\s+", " ", text).strip()
    return text, emotion


# ── Lessico delle pronunce ─────────────────────────────────────────────────
# Una riga per parola: parola<TAB>come scriverla per la voce. espeak-ng
# rispetta l'accento grafico, quindi di solito basta scriverlo: «ancora →
# ancóra», «subito → subìto». I fonemi IPA fra [[ ]] non si usano: libpiper
# (ruscapiper-stream) non li capisce, e la riga si salta.
def load_lexicon(*paths):
    """Più file: l'ultimo vince (quello dell'utente dopo quello di sistema)."""
    lex = {}
    for path in paths:
        if not path or not os.path.isfile(path):
            continue
        try:
            with open(path, encoding="utf-8") as f:
                for line in f:
                    if line.startswith("#") or "\t" not in line:
                        continue
                    word, say = line.rstrip("\n").split("\t", 1)
                    word, say = word.strip().lower(), say.strip()
                    if word and say:
                        lex[unicodedata.normalize("NFC", word)] = say
        except OSError:
            continue
    return lex


def apply_lexicon(text, lex):
    if not lex:
        return text

    def sub(m):
        say = lex.get(unicodedata.normalize("NFC", m.group(0).lower()))
        if not say or say.startswith("[["):
            return m.group(0)
        return say
    return re.sub(r"\w+", sub, unicodedata.normalize("NFC", text))


# ── Dalla voce al volto: fonemi IPA → visemi ─────────────────────────────
# A aperta, E media, I larga, O tonda, U piccola, M chiusa, F sul labbro,
# C consonante socchiusa, "" pausa.
_VISEMI = {}
for chars, v in (("aɐɑæ", "A"), ("eɛəɜ", "E"), ("iɪjy", "I"), ("oɔ", "O"),
                 ("uʊwʉ", "U"), ("mbp", "M"), ("fv", "F")):
    for ch in chars:
        _VISEMI[ch] = v
_SKIP = set("ˈˌːˑ̃ʲ‿")


def visemes(phonemes):
    """Lista di visemi da una lista di fonemi di Piper (un carattere IPA per
    voce; spazi e punteggiatura sono pause)."""
    out = []
    for ph in phonemes:
        if not ph or ph in _SKIP:
            continue
        if ph.isspace() or unicodedata.category(ph[0]).startswith("P"):
            out.append("")
        else:
            out.append(_VISEMI.get(ph[0], "C"))
    return out
