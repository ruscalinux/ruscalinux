# -*- coding: utf-8 -*-
# rusca_dubbing.py — RuscaLinux OS Apps 1.99.3 — GPL-3.0-or-later
#
# La catena di RuscaDubbing: dal video originale al video doppiato.
#
#   1. trascrizione  ruscawhisper-engine (whisper-cli) scrive i sottotitoli
#                    nella lingua originale (rusca_whisper.py, lo stesso
#                    modulo di RuscaTranscriber);
#   2. traduzione    llama-server di ruscallama-engine traduce i sottotitoli
#                    a gruppi, sapendo quanto tempo ha ogni battuta
#                    (rusca_engine.py, lo stesso modulo di RuscaTranslator);
#   3. doppiaggio    llama-tts di ruscallama-engine dice ogni battuta
#                    tradotta al suo tempo (rusca_tts.py, lo stesso modulo
#                    di RuscaNarrator);
#   4. missaggio     FFmpeg abbassa l'audio originale mentre parla la voce
#                    doppiata e scrive il video: immagine copiata, audio
#                    originale e doppiato, sottotitoli nelle due lingue.
#
# Un passo per volta, perché i modelli non stanno insieme nella memoria
# della scheda grafica: il modello di traduzione si chiude prima che parta
# quello della voce.
#
# Privacy e sicurezza (specifiche, sezione 11):
#   * nessun modulo di rete in questo file: la sola connessione è quella di
#     rusca_engine.py a llama-server su 127.0.0.1, con la chiave;
#   * i programmi sono avviati con percorso assoluto e lista di argomenti,
#     mai tramite shell; FFmpeg legge solo file locali
#     (-protocol_whitelist file);
#   * i file di lavoro stanno in ~/.cache/ruscadubbing (permessi 0700) e si
#     cancellano alla fine, all'avvio e alla chiusura.
import collections
import hashlib
import json
import os
import re
import shutil
import subprocess
import tempfile
import threading

from gi.repository import GLib

import rusca_engine as engine
import rusca_speech as speech
import rusca_tts as tts
import rusca_whisper as whisper

APP_ID = "org.ruscalinux.RuscaDubbing"
WORK_DIR = os.path.join(GLib.get_user_cache_dir(), "ruscadubbing")
# I moduli comuni lavorano in sottocartelle di quella di RuscaDubbing, non in
# quelle di RuscaTranscriber e RuscaNarrator.
whisper.WORK_DIR = os.path.join(WORK_DIR, "whisper")
# Lavoro salvato: trascrizione e traduzioni di ogni video, per rifare solo
# voce e missaggio. Testo dell'utente: cartella 0700, file 0600, si
# cancella dalla finestra («Dimentica»).
PROJECT_DIR = os.path.join(GLib.get_user_data_dir(), "ruscadubbing", "progetti")
# Lessico delle pronunce: quello del programma e quello dell'utente.
LEXICON_DIRS = (os.path.dirname(os.path.abspath(__file__)),
                os.path.join(GLib.get_user_data_dir(), "ruscadubbing"))
PREVIEW_MS = 60000          # «Prova su un minuto»
PROMPT_VERSION = 3          # cambia quando cambia il modo di tradurre
BRIEF_CHARS = 12000         # trascrizione data al modello per la scheda
tts.WORK_DIR = os.path.join(WORK_DIR, "voce")

# Lingue del doppiaggio: quelle che il modello della voce sa dire (Qwen3-TTS).
# Codice, nome nella lingua stessa, nome in inglese (per il prompt), codice
# ISO 639-2 (per le tracce del video).
LANGUAGES = (
    ("it", "Italiano", "Italian", "ita"), ("en", "English", "English", "eng"),
    ("de", "Deutsch", "German", "deu"), ("fr", "Français", "French", "fra"),
    ("es", "Español", "Spanish", "spa"), ("pt", "Português", "Portuguese", "por"),
    ("ru", "Русский", "Russian", "rus"), ("zh", "中文", "Chinese", "zho"),
    ("ja", "日本語", "Japanese", "jpn"), ("ko", "한국어", "Korean", "kor"),
)
CODES = [c for c, _n, _e, _i in LANGUAGES]
NATIVE = {c: n for c, n, _e, _i in LANGUAGES}
ENGLISH = {c: e for c, _n, e, _i in LANGUAGES}
ISO3 = {c: i for c, _n, _e, i in LANGUAGES}
# Lingue che Whisper riconosce oltre a queste: per il prompt e per le tracce.
EXTRA_SOURCE = {"nl": ("Dutch", "nld"), "pl": ("Polish", "pol"), "tr": ("Turkish", "tur"),
                "uk": ("Ukrainian", "ukr"), "cs": ("Czech", "ces"), "sv": ("Swedish", "swe"),
                "ro": ("Romanian", "ron"), "hu": ("Hungarian", "hun"), "el": ("Greek", "ell"),
                "fi": ("Finnish", "fin"), "ar": ("Arabic", "ara"), "hi": ("Hindi", "hin"),
                "id": ("Indonesian", "ind"), "vi": ("Vietnamese", "vie"), "ca": ("Catalan", "cat")}

# Velocità della voce, in caratteri al secondo: serve a dire al modello
# quanto può essere lunga ogni battuta tradotta. Valori prudenti per una
# voce chiara; il doppiaggio può poi accelerare fino a max_speed.
CHARS_PER_SECOND = {"it": 14.0, "en": 15.0, "de": 13.5, "fr": 14.5, "es": 15.0,
                    "pt": 14.5, "ru": 13.0, "zh": 5.0, "ja": 7.5, "ko": 7.0}
BATCH = 8                       # frasi per richiesta di traduzione
PARALLEL_FIRST = 2              # con la voce in parallelo: primo gruppo piccolo
CONTEXT_LINES = 3               # frasi già tradotte date come contesto
# Frasi: battute consecutive che formano una frase si traducono e si dicono
# insieme. Una frase si chiude dopo una battuta che finisce con un segno di
# fine frase, dopo una pausa lunga, o quando diventa troppo lunga; superata
# BLOCK_SOFT_MS si chiude anche a una virgola.
BLOCK_MAX_MS = 30000
BLOCK_SOFT_MS = 15000
BLOCK_MAX_CHARS = 420
BLOCK_GAP_MS = 1500
BLOCK_MIN_MS = 8000         # sotto, una frase finita si unisce alla successiva
BLOCK_JOIN_GAP_MS = 700     # … se fra le due la pausa è breve
CLAUSE_END = (",", ";", ":", "—", "–", "，", "、", "；", "：")
MAX_TOKENS = 2048
SAMPLING = dict(temperature=0.2, top_p=0.92, top_k=40, min_p=0.08, repeat_penalty=1.05)
# Battute che Whisper spezza: si uniscono se la pausa è breve e la frase non
# è finita, finché la battuta resta di una lunghezza ragionevole.
JOIN_GAP_MS = 600
JOIN_MAX_MS = 7000
JOIN_MAX_CHARS = 140
SENTENCE_END = (".", "?", "!", "…", "。", "？", "！", "\"", "”", "»")

# Missaggio: mentre parla la voce doppiata, l'audio originale scende. ratio
# alto = originale più basso sotto la voce.
DUCKING = {"light": "threshold=0.03:ratio=4:attack=30:release=500",
           "medium": "threshold=0.02:ratio=8:attack=20:release=450",
           "strong": "threshold=0.015:ratio=16:attack=15:release=400"}
VIDEO_FORMATS = ("mkv", "mp4")
# Volume finale della traccia doppiata: −16 LUFS integrati, picchi a
# −1,5 dBTP (valori comuni per il video sul web), uguale da un video
# all'altro. loudnorm lavora a 192 kHz: si torna a 48 kHz.
FINAL_LOUDNESS = "loudnorm=I=-16:TP=-1.5:LRA=11,aresample=48000"

Cue = collections.namedtuple("Cue", "start end text")       # tempi in ms


class DubbingError(Exception):
    """Errore con una chiave di lang/ e un dettaglio da mostrare."""

    def __init__(self, key, detail=""):
        super().__init__(f"{key}: {detail}" if detail else key)
        self.key = key
        self.detail = detail


def english_name(code):
    return ENGLISH.get(code) or EXTRA_SOURCE.get(code, (code,))[0]


def iso3(code):
    return ISO3.get(code) or EXTRA_SOURCE.get(code, ("", "und"))[1]


def clean_work_dir():
    """Cancella i file di lavoro rimasti: audio e testi dell'utente."""
    try:
        for name in os.listdir(WORK_DIR):
            p = os.path.join(WORK_DIR, name)
            if os.path.isdir(p) and not os.path.islink(p):
                shutil.rmtree(p, ignore_errors=True)
            else:
                try:
                    os.unlink(p)
                except OSError:
                    pass
    except OSError:
        pass


# ── sottotitoli ─────────────────────────────────────────────────────────────
def cues_from_segments(segments):
    """Battute dai segmenti di Whisper: si uniscono i pezzi di una stessa
    frase separati da una pausa breve, perché la voce li dica di seguito."""
    cues = []
    for seg in segments:
        text = " ".join(seg.text.split())
        if not text:
            continue
        start, end = seg.start, max(seg.end, seg.start + 1)
        if cues:
            last = cues[-1]
            if (not last.text.endswith(SENTENCE_END) and start - last.end <= JOIN_GAP_MS
                    and end - last.start <= JOIN_MAX_MS
                    and len(last.text) + len(text) < JOIN_MAX_CHARS):
                cues[-1] = Cue(last.start, end, last.text + " " + text)
                continue
        cues.append(Cue(start, end, text))
    return cues


def cues_from_srt(text):
    """Battute da un file SRT (per esempio uno corretto a mano)."""
    return [Cue(p.start, max(p.end, p.start + 1), p.text) for p in tts.parse_srt(text)]


def to_srt(cues, texts=None):
    """Sottotitoli SubRip. texts: i testi da scrivere al posto di quelli
    delle battute (la traduzione), una stringa o più righe per battuta."""
    blocks = []
    for i, cue in enumerate(cues):
        text = cue.text if texts is None else texts[i]
        text = "\n".join(" ".join(line.split()) for line in text.split("\n") if line.strip())
        if not text:
            continue
        blocks.append(f"{len(blocks) + 1}\n{whisper.srt_time(cue.start)} --> "
                      f"{whisper.srt_time(max(cue.end, cue.start + 1))}\n{text}\n")
    return "\n".join(blocks)


# ── sottotitoli professionali ───────────────────────────────────────────────
# Le regole comuni dei sottotitoli (per esempio le guide Netflix per molte
# lingue europee): al massimo 2 righe da 42 caratteri, di solito una riga
# sola; a capo dopo la punteggiatura, a piramide (riga in alto più corta),
# mai una o due parole sole in alto; fino a 17 caratteri al secondo per un
# pubblico adulto; almeno 5/6 di secondo per sottotitolo; 2 fotogrammi fra
# un sottotitolo e il successivo. Per cinese, giapponese e coreano, righe
# più corte e lettura più lenta.
LINE_CHARS = {"zh": 16, "ja": 13, "ko": 16}
READING_CPS = {"zh": 9, "ja": 4, "ko": 12}
SUB_LINE = 42
SUB_CPS = 17.0
SUB_MIN_MS = 834
SUB_MAX_MS = 7000
SUB_GAP_MS = 83
SUB_MAX_EXTEND_MS = 1000       # un sottotitolo veloce può restare dopo la voce


def _line_limit(lang):
    return LINE_CHARS.get((lang or "").split("_")[0].split("-")[0], SUB_LINE)


def _cps_limit(lang):
    return READING_CPS.get((lang or "").split("_")[0].split("-")[0], SUB_CPS)


def _end_score(word):
    """Quanto costa tagliare dopo questa parola: niente alla fine di una
    frase, poco dopo una virgola, di più a metà frase, molto dopo una
    parolina che lega alla successiva (articoli, preposizioni,
    congiunzioni: «la», «di», «e», «the», «of»)."""
    if word.endswith(_STRONG) or word.endswith(("»", "”", "\"")):
        return 0.0
    if word.endswith(CLAUSE_END):
        return 1.0
    if len(word) <= 3 and word.isalpha() and word.islower():
        return 5.0
    return 3.0


def _best_wrap(words, limit, sep=" "):
    """(posizione dell'a capo, costo) per le parole di un sottotitolo, o
    (None, None) se non stanno in due righe di limit caratteri."""
    text = sep.join(words)
    if len(text) <= limit:
        return 0, 0.0
    best, best_score = None, None
    top = -len(sep)
    for j in range(1, len(words)):
        top += len(words[j - 1]) + len(sep)
        bottom = len(text) - top - len(sep)
        if top > limit or bottom > limit:
            continue
        score = _end_score(words[j - 1]) * 2
        if top > bottom:
            score += (top - bottom) / 6                    # piramide
        if j <= 2 and len(words) > 4:
            score += 6                                     # parole sole in alto
        score += abs(top - bottom) / 20
        if best_score is None or score < best_score:
            best, best_score = j, score
    return best, best_score


def _tokens(text, lang):
    """Le «parole» di un testo: per cinese e giapponese, che non separano
    le parole con gli spazi, i singoli caratteri."""
    if (lang or "").split("_")[0] in ("zh", "ja"):
        return [c for c in text if not c.isspace()], ""
    return text.split(), " "


def wrap_lines(text, limit=SUB_LINE, lang=""):
    """Il testo di un sottotitolo su una riga, o su due a piramide: a capo
    dopo la punteggiatura se possibile, riga in alto non più lunga di
    quella in basso, mai una o due parole sole in alto."""
    words, sep = _tokens(text, lang)
    if len(sep.join(words)) <= limit:
        return sep.join(words)
    best, _score = _best_wrap(words, limit, sep)
    if best is None:
        # Non sta in due righe (una parola lunghissima): a capo a metà.
        best = max(1, len(words) // 2)
    return sep.join(words[:best]) + "\n" + sep.join(words[best:])


def segment_subtitles(units, texts, lang):
    """Sottotitoli divisi sul testo tradotto, non sulle battute originali:
    per ogni frase (unit: tempi della frase; text: la sua traduzione) i
    sottotitoli che servono, ognuno di al massimo due righe, tagliati dopo
    la punteggiatura dove si può, con tempi proporzionali al testo.
    Restituisce (lista di Cue con il testo già a capo, sottotitoli più
    veloci del limite di lettura)."""
    limit = _line_limit(lang)
    max_chars = 2 * limit
    cps = _cps_limit(lang)
    out = []
    for unit, text in zip(units, texts):
        words, sep = _tokens(text or "", lang)
        if not words:
            continue
        span = max(1, unit.end - unit.start)
        total = len(sep.join(words))
        per_char = span / total
        # Divisione migliore in sottotitoli (programmazione dinamica): ogni
        # pezzo sta in due righe; si preferiscono tagli dopo la
        # punteggiatura, pezzi non troppo corti, pochi pezzi, durate entro
        # SUB_MAX_MS.
        n = len(words)
        lengths = [len(w) + len(sep) for w in words]
        best = [0.0] + [None] * n
        back = [0] * (n + 1)
        for j in range(1, n + 1):
            chars = -len(sep)
            for i in range(j - 1, -1, -1):
                chars += lengths[i]
                if chars > max_chars and i < j - 1:
                    break
                if best[i] is None:
                    continue
                wrap, wrap_cost = _best_wrap(words[i:j], limit, sep)
                if wrap is None and j - i > 1:
                    continue                               # non sta in due righe
                cost = 1.0 + (_end_score(words[j - 1]) if j < n else 0.0) + (wrap_cost or 0.0) / 4
                duration = chars * per_char
                if chars < 18 and n > 3:
                    cost += 3.0
                if duration < SUB_MIN_MS and n > 1:
                    cost += 10.0 * (SUB_MIN_MS - duration) / SUB_MIN_MS
                if duration > SUB_MAX_MS:
                    cost += 2.0 * (duration - SUB_MAX_MS) / 1000
                if wrap is None:
                    cost += 50.0                           # una parola lunghissima
                total_cost = best[i] + cost
                if best[j] is None or total_cost < best[j]:
                    best[j], back[j] = total_cost, i
        cuts, j = [], n
        while j > 0:
            cuts.append((back[j], j))
            j = back[j]
        cuts.reverse()
        done_chars = 0
        for a, b in cuts:
            piece = sep.join(words[a:b])
            start = unit.start + int(done_chars * per_char)
            done_chars += len(piece) + len(sep)
            end = unit.start + min(span, int(done_chars * per_char))
            out.append(Cue(start, end, wrap_lines(piece, limit, lang)))
    # Tempi: 2 fotogrammi fra un sottotitolo e l'altro, durata minima, e
    # per un sottotitolo troppo veloce un po' di tempo in più, se dopo c'è
    # spazio.
    fast = 0
    for k, cue in enumerate(out):
        nxt = out[k + 1].start if k + 1 < len(out) else None
        room = (nxt - SUB_GAP_MS) if nxt is not None else cue.end + SUB_MAX_EXTEND_MS
        chars = len(cue.text.replace("\n", " "))
        need = max(SUB_MIN_MS, int(chars / cps * 1000))
        end = cue.end
        if end - cue.start < need:
            end = min(cue.start + need, cue.end + SUB_MAX_EXTEND_MS, room)
        end = min(end, room) if nxt is not None else end
        end = max(end, cue.start + 1)
        if chars / max(0.001, (end - cue.start) / 1000) > cps + 0.5:
            fast += 1
        out[k] = Cue(cue.start, end, cue.text)
    return out, fast


def bilingual_srt(cues, translated):
    """Un solo file con le due lingue: sopra l'originale, sotto la traduzione."""
    return to_srt(cues, [f"{c.text}\n{t}" for c, t in zip(cues, translated)])


def slot_ms(cues, i):
    """Tempo che ha la battuta i: fino all'inizio della successiva, o fino
    alla sua fine se è l'ultima (lo stesso spazio che usa il doppiaggio)."""
    cue = cues[i]
    limit = cues[i + 1].start if i + 1 < len(cues) else cue.end
    return max(400, limit - cue.start)


def budget_chars(cues, i, tgt, max_speed=1.3):
    """Caratteri al massimo per la battuta i tradotta: quelli che la voce
    dice nel suo tempo, con una parte dell'accelerazione permessa."""
    cps = CHARS_PER_SECOND.get(tgt, 14.0)
    allowed = 1.0 + (max(1.0, max_speed) - 1.0) * 0.5
    return max(8, int(slot_ms(cues, i) / 1000 * cps * allowed))


# ── frasi ───────────────────────────────────────────────────────────────────
Part = collections.namedtuple("Part", "cue start end text")
# cue: indice della battuta da cui viene; start, end: tempi stimati (ms).

_SENTENCE_SPLIT = re.compile(r"(?<=[.!?…。？！])\s+(?=\S)")


def cue_parts(cues):
    """Le battute divise anche dove una frase finisce in mezzo a una
    battuta («…до автоматизма. Еще один важный принцип. Очень…»): così una
    frase si traduce e si dice intera anche quando le battute la tagliano
    altrove. I tempi dei pezzi sono stimati in proporzione ai caratteri.
    I sottotitoli restano sulle battute originali."""
    parts = []
    for i, cue in enumerate(cues):
        pieces = [p for p in _SENTENCE_SPLIT.split(cue.text) if p.strip()]
        # Un pezzo cortissimo («Ну.») resta attaccato al precedente.
        merged = []
        for p in pieces:
            if merged and len(p) < 4:
                merged[-1] += " " + p
            else:
                merged.append(p)
        pieces = merged or [cue.text]
        total = sum(len(p) for p in pieces) or 1
        span = cue.end - cue.start
        acc = 0
        for p in pieces:
            a = cue.start + span * acc // total
            acc += len(p)
            parts.append(Part(i, a, cue.start + span * acc // total, p))
    return parts


def group_blocks(cues):
    """Le battute raggruppate in frasi: liste di indici consecutivi.

    Tradurre battuta per battuta costringeva il modello a far tornare i
    pezzi di una frase spezzata (il russo e l'italiano mettono le parole in
    ordine diverso): chiudeva le frasi in anticipo, spostava parole,
    aggiungeva «…». Una frase intera si traduce bene e la voce la dice con
    l'intonazione giusta."""
    blocks, current = [], []

    def fits(block, j):
        """La battuta j si può aggiungere alla frase block?"""
        first, last = cues[block[0]], cues[block[-1]]
        chars = sum(len(cues[k].text) + 1 for k in block) + len(cues[j].text)
        return (cues[j].start - last.end <= BLOCK_GAP_MS
                and cues[j].end - first.start <= BLOCK_MAX_MS and chars <= BLOCK_MAX_CHARS)

    for i, cue in enumerate(cues):
        if current and not fits(current, i):
            blocks.append(current)
            current = []
        current.append(i)
        text = cue.text.rstrip()
        if text.endswith(SENTENCE_END):
            # Una frase breve si unisce alla successiva, se anche quella è
            # una frase intera, ci sta e segue senza una vera pausa.
            nxt = i + 1
            short = cue.end - cues[current[0]].start < BLOCK_MIN_MS
            if not (short and nxt < len(cues) and fits(current, nxt)
                    and cues[nxt].start - cue.end <= BLOCK_JOIN_GAP_MS
                    and cues[nxt].text.rstrip().endswith(SENTENCE_END)):
                blocks.append(current)
                current = []
        elif text.endswith(CLAUSE_END) and cue.end - cues[current[0]].start >= BLOCK_SOFT_MS:
            # Frase già lunga: si chiude alla virgola, a meno che la battuta
            # dopo finisca la frase e ci stia ancora.
            nxt = i + 1
            if not (nxt < len(cues) and fits(current, nxt)
                    and cues[nxt].text.rstrip().endswith(SENTENCE_END)):
                blocks.append(current)
                current = []
    if current:
        blocks.append(current)
    return blocks


def block_cues(cues, blocks):
    """Una Cue per frase: dall'inizio della prima battuta alla fine
    dell'ultima, con i testi uniti."""
    return [Cue(cues[b[0]].start, cues[b[-1]].end, " ".join(cues[i].text for i in b))
            for b in blocks]


_STRONG = (".", "?", "!", "…", ";", ":", "。", "？", "！")


def split_translation(text, weights):
    """Divide la traduzione di una frase fra le sue battute, in parti
    proporzionali al peso di ognuna (la lunghezza del testo originale),
    tagliando fra le parole e preferendo i segni di punteggiatura vicini.
    Ogni battuta riceve almeno una parola, se ce ne sono abbastanza."""
    n_parts = len(weights)
    words = text.split()
    if n_parts <= 1 or not words:
        return [" ".join(words)] + [""] * (n_parts - 1)
    if len(words) < n_parts:
        return words + [""] * (n_parts - len(words))
    pos = [0]                                   # caratteri prima della parola j
    for w in words:
        pos.append(pos[-1] + len(w) + 1)
    total = pos[-1]
    wsum = float(sum(weights)) or 1.0
    cuts, prev, acc = [], 0, 0.0
    for k in range(1, n_parts):
        acc += weights[k - 1]
        target = total * acc / wsum
        part = total / n_parts
        best, best_score = None, None
        for j in range(prev + 1, len(words) - (n_parts - k) + 1):
            score = abs(pos[j] - target)
            end = words[j - 1]
            if end.endswith(_STRONG):
                score -= 0.45 * part
            elif end.endswith(CLAUSE_END):
                score -= 0.3 * part
            if best_score is None or score < best_score:
                best, best_score = j, score
        cuts.append(best)
        prev = best
    bounds = [0] + cuts + [len(words)]
    return [" ".join(words[a:b]) for a, b in zip(bounds, bounds[1:])]


def translations_per_cue(cues, parts, blocks, block_texts):
    """I sottotitoli tradotti, uno per battuta originale: ogni frase
    tradotta si ridivide sui suoi pezzi in proporzione al testo originale,
    e i pezzi di una stessa battuta si riuniscono."""
    per_part = [""] * len(parts)
    for block, text in zip(blocks, block_texts):
        pieces = split_translation(text, [max(1, len(parts[k].text)) for k in block])
        for k, piece in zip(block, pieces):
            per_part[k] = piece
    out = [[] for _ in cues]
    for part, text in zip(parts, per_part):
        if text:
            out[part.cue].append(text)
    return [" ".join(t) for t in out]


_ELLIPSIS_END = re.compile(r"\s*(?:\.\.\.|…)+\s*$")
_ELLIPSIS_START = re.compile(r"^\s*(?:\.\.\.|…)+\s*")


def clean_translation(source, text):
    """Toglie i puntini di sospensione che il modello aggiunge ai capi di
    una frase e che nell'originale non ci sono: nei sottotitoli sono
    brutti e la voce li legge come una frase sospesa."""
    text = " ".join(text.split())
    if not _ELLIPSIS_END.search(source):
        stripped = _ELLIPSIS_END.sub("", text)
        if stripped:
            # «…» al posto di un punto: se l'originale finisce la frase, il
            # punto resta.
            text = stripped + ("." if source.rstrip().endswith((".", "。")) else "")
    if not _ELLIPSIS_START.search(source):
        text = _ELLIPSIS_START.sub("", text) or text
    return text


# ── traduzione ──────────────────────────────────────────────────────────────
def build_prompt(src, tgt, notes=""):
    s, g = english_name(src), english_name(tgt)
    extra = f"\n\nNotes about this talk, from the whole transcript:\n{notes.strip()}" if notes.strip() else ""
    return (
        f"You are a professional dubbing adapter translating a spoken talk from {s} to "
        f"{g}. You receive numbered passages in the format `N|MAX|text`: each passage is "
        f"what the speaker says in one stretch, usually one or more complete sentences, "
        f"and MAX is the maximum number of characters the {g} passage may have, so that it "
        f"can be spoken in the time of the original. Translate each passage into natural, "
        f"fluent, idiomatic spoken {g}, faithful to the meaning and tone, as one coherent "
        f"text. When a faithful translation would be longer than MAX, condense it as a "
        f"professional adapter would, keeping the meaning. Translate every part of the "
        f"passage, in its order. If a passage stops in the middle of a sentence, stop the "
        f"translation at the corresponding point, without adding a period. Never add "
        f"ellipses (... or …) that are not in the original. Answer with exactly one line per "
        f"passage, in the format `N|translation`, same numbers, same order, nothing else: "
        f"no notes, no explanations, no blank translations.{extra}")


# ── contesto del discorso ───────────────────────────────────────────────────
def parse_glossary(text):
    """[(termine, traduzione)] da «termine = traduzione», separati da «;»
    o da a capo. Un termine senza «=» si lascia com'è (non si traduce)."""
    out = []
    for item in re.split(r"[;\n]+", text or ""):
        item = item.strip()
        if not item:
            continue
        if "=" in item:
            a, b = item.split("=", 1)
            if a.strip():
                out.append((a.strip(), b.strip() or a.strip()))
        else:
            out.append((item, item))
    return out


def speaker_note(gender, tgt):
    """Indicazione sul genere di chi parla, per l'accordo delle forme in
    prima persona («sono stato» o «sono stata»)."""
    g = english_name(tgt)
    if gender == "male":
        return (f"The speaker is a man: in {g}, use masculine agreement for everything the "
                f"speaker says about himself.")
    if gender == "female":
        return (f"The speaker is a woman: in {g}, use feminine agreement for everything the "
                f"speaker says about herself.")
    if gender == "male?":
        return ("The speaker's voice is low, probably a man's: use masculine agreement for "
                "first-person forms, unless the transcript clearly shows otherwise.")
    if gender == "female?":
        return ("The speaker's voice is high, probably a woman's: use feminine agreement for "
                "first-person forms, unless the transcript clearly shows otherwise.")
    return ""


def guess_gender(hz):
    """Dall'altezza mediana della voce: "male?", "female?" o "" (incerto).
    È solo un indizio, che il modello mette dopo la grammatica del testo."""
    if not hz:
        return ""
    return "male?" if hz < 160 else "female?" if hz > 180 else ""


def brief_request(units, src, tgt):
    """La richiesta della scheda del discorso: argomento, registro, genere
    di chi parla dalla grammatica, termini ricorrenti con la traduzione da
    usare sempre. Al modello va la trascrizione (inizio e fine, se è
    lunga)."""
    text = " ".join(u.text for u in units)
    if len(text) > BRIEF_CHARS:
        head = text[:BRIEF_CHARS * 2 // 3]
        tail = text[-BRIEF_CHARS // 3:]
        text = head + " […] " + tail
    s, g = english_name(src), english_name(tgt)
    user = (f"Here is the transcript of a talk in {s}. Write short notes, in English, for the "
            f"person who will translate it into {g} for dubbing. At most 150 words, in this "
            f"form:\n"
            f"Topic: one or two sentences.\n"
            f"Register: formal or informal, and how the speaker addresses the audience (in "
            f"{g}, which form of address to use).\n"
            f"Speaker: man, woman or unknown, only if the grammar of the transcript shows it "
            f"(for example past-tense endings); otherwise unknown.\n"
            f"Terms: up to 10 recurring key terms, names or concepts, each as "
            f"`term = {g} translation`, to be used consistently.\n\n"
            f"Transcript:\n{text}")
    return dict(SAMPLING, messages=[{"role": "user", "content": user}], max_tokens=600,
                reasoning_effort="none")


def make_notes(brief, gender_note, glossary):
    parts = []
    if brief.strip():
        parts.append(brief.strip())
    if gender_note:
        parts.append(gender_note)
    if glossary:
        parts.append("Glossary (always use these translations; a term mapped to itself stays "
                     "untranslated):\n" + "\n".join(f"{a} = {b}" for a, b in glossary))
    return "\n".join(parts)


_LINE = re.compile(r"^\s*(?:\[(\d+)\]\s*[|:.)\-]?|(\d+)\s*[|:.)\-])\s*(.*?)\s*$")


def parse_translations(text):
    """{numero: traduzione} dalle righe `N|testo` della risposta. Ignora le
    righe che non hanno questa forma (preamboli, blocchi di codice)."""
    out = {}
    for line in (text or "").splitlines():
        m = _LINE.match(line)
        if not m:
            continue
        number, body = int(m.group(1) or m.group(2)), m.group(3).strip()
        # Il modello a volte ripete il limite: `N|MAX|testo`.
        mm = re.match(r"^(\d+)\s*\|\s*(.*)$", body)
        if mm:
            body = mm.group(2).strip()
        body = body.strip("`").strip()
        if body:
            out[number] = body
    return out


def translate_cues(chat, cues, src, tgt, stop_event=None, on_progress=None, max_speed=1.3,
                   batch=BATCH, known=None, notes="", on_batch=None, first=None):
    """Traduce le frasi a gruppi. chat(body) -> testo è la funzione del
    motore (engine.Engine.chat). known: traduzioni già pronte (memoria del
    lavoro salvato), None o "" per quelle da fare. Restituisce
    (traduzioni, statistiche): statistiche = {"retried", "shortened",
    "kept", "reused"}. Una frase che non torna tradotta si chiede di nuovo
    da sola; se il modello non la restituisce ancora, resta l'originale
    ("kept"). first: grandezza del primo gruppo, se diversa (con la voce
    in parallelo un primo gruppo piccolo fa partire prima la voce)."""
    result = [t or None for t in (known or [None] * len(cues))]
    todo = [i for i in range(len(cues)) if not result[i]]
    stats = {"retried": 0, "shortened": 0, "kept": 0, "reused": len(cues) - len(todo)}
    system = build_prompt(src, tgt, notes)

    def ask(lines, context):
        user = ""
        if context:
            user += ("Previous passages, already translated (context only, do not output):\n"
                     + "\n".join(context) + "\n\n")
        user += "Lines to translate:\n" + "\n".join(lines)
        body = dict(SAMPLING, messages=[{"role": "system", "content": system},
                                        {"role": "user", "content": user}],
                    max_tokens=MAX_TOKENS, reasoning_effort="none")
        return parse_translations(chat(body))

    def line(i):
        return f"{i + 1}|{budget_chars(cues, i, tgt, max_speed)}|{cues[i].text}"

    known_idx = [i for i in range(len(cues)) if result[i]]
    if on_batch and known_idx:
        on_batch(known_idx, result)
    head = first if first and first < batch else 0
    groups = ([todo[:head]] if head and todo[:head] else []) + \
        [todo[s:s + batch] for s in range(head, len(todo), batch)]
    start = 0
    for idx in groups:
        if stop_event is not None and stop_event.is_set():
            raise _Stopped()
        if on_progress:
            on_progress(start, len(todo))
        start += len(idx)
        context = [f"{cues[j].text} => {result[j]}"
                   for j in range(max(0, idx[0] - CONTEXT_LINES), idx[0]) if result[j]]
        got = ask([line(i) for i in idx], context)
        for i in idx:
            if got.get(i + 1):
                result[i] = got[i + 1]
        for i in [i for i in idx if not result[i]]:            # una per volta
            if stop_event is not None and stop_event.is_set():
                raise _Stopped()
            stats["retried"] += 1
            got = ask([line(i)], context)
            if got.get(i + 1):
                result[i] = got[i + 1]
            else:
                result[i] = cues[i].text
                stats["kept"] += 1
        # Frasi molto più lunghe del loro tempo: si chiede una versione breve.
        long_ones = [i for i in idx
                     if len(result[i]) > budget_chars(cues, i, tgt, max_speed) * 1.25]
        if long_ones:
            if stop_event is not None and stop_event.is_set():
                raise _Stopped()
            got = ask([line(i) for i in long_ones],
                      [f"(too long, shorten to MAX) {result[i]}" for i in long_ones])
            for i in long_ones:
                short = got.get(i + 1)
                if short and len(short) < len(result[i]):
                    result[i] = short
                    stats["shortened"] += 1
        if on_batch:
            on_batch(idx, result)
    if on_progress:
        on_progress(len(todo), len(todo))
    return result, stats


# Verifica dopo la voce: una frase detta che non sta nel suo tempo nemmeno
# alla velocità massima si fa riscrivere più corta e si ridice (una volta).
REFIT_TOLERANCE_MS = 150
REFIT_MARGIN = 0.9


def too_long(pieces, durations, max_speed):
    """[(indice, caratteri massimi)] delle frasi dette che non stanno nel
    loro tempo (fino all'inizio della successiva) nemmeno accelerate a
    max_speed. Il massimo si ricava dalla velocità reale della voce su
    quella frase. L'ultima frase non ha limite: può finire dopo."""
    out = []
    for i, (piece, ms) in enumerate(zip(pieces, durations)):
        if i + 1 >= len(pieces) or ms <= 0:
            continue
        slot = max(1, pieces[i + 1].start - piece.start)
        if ms / max(1.0, max_speed) > slot + REFIT_TOLERANCE_MS:
            chars = len(piece.text)
            target = int(chars * slot * max(1.0, max_speed) * REFIT_MARGIN / ms)
            out.append((i, max(8, min(target, chars - 1))))
    return out


def shorten_translations(chat, originals, texts, targets, src, tgt, stop_event=None,
                         batch=BATCH, notes=""):
    """Versioni più corte delle traduzioni troppo lunghe da dire.
    targets: {indice: caratteri massimi}. Restituisce {indice: testo}
    solo per quelle davvero più corte."""
    system = build_prompt(src, tgt, notes)
    order = sorted(targets)
    out = {}
    for start in range(0, len(order), batch):
        if stop_event is not None and stop_event.is_set():
            raise _Stopped()
        idx = order[start:start + batch]
        user = ("These translations are too long to be spoken in the time of the original. "
                "Rewrite each one in at most MAX characters, as a professional dubbing "
                "adapter would: same meaning, natural spoken language, nothing important "
                "lost.\n" + "\n".join(f"{i + 1}: {texts[i]}" for i in idx)
                + "\n\nLines to translate:\n"
                + "\n".join(f"{i + 1}|{targets[i]}|{originals[i]}" for i in idx))
        body = dict(SAMPLING, messages=[{"role": "system", "content": system},
                                        {"role": "user", "content": user}],
                    max_tokens=MAX_TOKENS, reasoning_effort="none")
        got = parse_translations(chat(body))
        for i in idx:
            new = got.get(i + 1)
            if new and len(new) < len(texts[i]):
                out[i] = new
    return out


class _Stopped(Exception):
    pass


# ── video ───────────────────────────────────────────────────────────────────
_DURATION = re.compile(r"Duration:\s*(\d+):(\d+):(\d+)(?:\.(\d+))?")
_STREAM = re.compile(r"Stream #\d+:\d+(?:\[[^\]]*\])?(?:\((\w+)\))?: (Video|Audio|Subtitle):")


def probe(path, ffmpeg=None):
    """{"duration_ms", "video", "audio", "subtitle"}: durata e numero di
    flussi, letti da ciò che FFmpeg scrive aprendo il file (senza ffprobe)."""
    ffmpeg = ffmpeg or tts.find_ffmpeg()
    if not ffmpeg:
        raise DubbingError("err_no_ffmpeg")
    r = subprocess.run([ffmpeg, "-hide_banner", "-nostdin", "-protocol_whitelist", "file",
                        "-i", path], stdin=subprocess.DEVNULL, capture_output=True, text=True,
                       errors="replace")
    info = {"duration_ms": 0, "video": 0, "audio": 0, "subtitle": 0}
    m = _DURATION.search(r.stderr)
    if m:
        h, mi, s, frac = m.groups()
        info["duration_ms"] = ((int(h) * 60 + int(mi)) * 60 + int(s)) * 1000 + \
            int((frac or "0").ljust(3, "0")[:3])
    for m in _STREAM.finditer(r.stderr):
        info[m.group(2).lower()] += 1
    if not info["video"] and not info["audio"]:
        raise DubbingError("err_not_video", r.stderr.strip().splitlines()[-1] if r.stderr.strip() else path)
    return info


def mix_command(ffmpeg, media, dub_wav, out_wav, has_audio, ducking="medium"):
    """La traccia doppiata: originale abbassato sotto la voce, più la voce.
    Senza audio originale, la sola voce. Stereo, 48 kHz."""
    cmd = [ffmpeg, "-nostdin", "-hide_banner", "-loglevel", "error",
           "-protocol_whitelist", "file"]
    if has_audio:
        cmd += ["-i", media, "-i", dub_wav, "-filter_complex",
                "[0:a:0]aresample=48000,aformat=channel_layouts=stereo[orig];"
                "[1:a]aresample=48000,aformat=channel_layouts=stereo,asplit=2[voice][key];"
                f"[orig][key]sidechaincompress={DUCKING.get(ducking, DUCKING['medium'])}[duck];"
                "[duck][voice]amix=inputs=2:duration=longest:dropout_transition=0:normalize=0,"
                f"alimiter=limit=0.95,{FINAL_LOUDNESS}[out]",
                "-map", "[out]"]
    else:
        cmd += ["-i", dub_wav, "-af",
                f"aresample=48000,aformat=channel_layouts=stereo,{FINAL_LOUDNESS}"]
    return cmd + ["-c:a", "pcm_s16le", "-f", "wav", "-y", out_wav]


# Sottotitoli impressi nell'immagine: libass (filtro subtitles di FFmpeg),
# carattere senza grazie con il bordo, in basso. L'immagine si ricodifica in
# H.264 (CRF 20, preset veryfast: buona qualità senza far aspettare).
BURN_STYLE = ("FontName=Cantarell,FontSize=20,PrimaryColour=&H00FFFFFF,"
              "OutlineColour=&H00000000,BorderStyle=1,Outline=1.6,Shadow=0,MarginV=22")
BURN_FILE = "impressi.srt"


def mux_command(ffmpeg, media, mix_wav, srt_src, srt_tgt, out, fmt, src, tgt, has_audio,
                titles=("", ""), max_ms=0, burn=False):
    """… burn: imprime i sottotitoli tradotti nell'immagine (il comando va
    lanciato nella cartella in cui c'è BURN_FILE)."""
    """Il video doppiato: immagine copiata (niente ricodifica), audio
    originale (se c'è), audio doppiato come traccia predefinita, sottotitoli
    nelle due lingue. titles: (nome della traccia originale, del doppiaggio)."""
    cmd = [ffmpeg, "-nostdin", "-hide_banner", "-loglevel", "error",
           "-protocol_whitelist", "file",
           "-i", media, "-i", mix_wav, "-i", srt_src, "-i", srt_tgt,
           "-map", "0:v?", "-map_chapters", "0"]
    audio = 0
    if has_audio:
        cmd += ["-map", "0:a:0"]
        audio = 1
    cmd += ["-map", "1:a:0", "-map", "2:s:0", "-map", "3:s:0"]
    if burn:
        cmd += ["-vf", f"subtitles={BURN_FILE}:charenc=UTF-8:force_style='{BURN_STYLE}'",
                "-c:v", "libx264", "-crf", "20", "-preset", "veryfast", "-pix_fmt", "yuv420p"]
    else:
        cmd += ["-c:v", "copy"]
    dub = audio                                  # indice della traccia doppiata
    if fmt == "mp4":
        cmd += ["-c:a", "aac", "-b:a", "192k", "-c:s", "mov_text", "-movflags", "+faststart"]
    else:
        if has_audio:
            cmd += ["-c:a:0", "copy"]
        cmd += [f"-c:a:{dub}", "libopus", f"-b:a:{dub}", "160k", "-c:s", "srt"]
    if has_audio:
        cmd += ["-metadata:s:a:0", f"language={iso3(src)}", "-metadata:s:a:0",
                f"title={titles[0]}", "-disposition:a:0", "0"]
    cmd += [f"-metadata:s:a:{dub}", f"language={iso3(tgt)}", f"-metadata:s:a:{dub}",
            f"title={titles[1]}", f"-disposition:a:{dub}", "default",
            "-metadata:s:s:0", f"language={iso3(src)}", "-metadata:s:s:1",
            f"language={iso3(tgt)}", "-disposition:s:0", "0", "-disposition:s:1", "0",
            "-f", "mp4" if fmt == "mp4" else "matroska"]
    if max_ms:
        # La prova finisce con lo spezzone, anche se la voce va oltre.
        cmd += ["-t", f"{max_ms / 1000:.3f}"]
    return cmd + ["-y", out]


def unique_path(path):
    """path, o «nome (2).est» se esiste già: non si sovrascrive mai niente."""
    if not os.path.exists(path):
        return path
    root, ext = os.path.splitext(path)
    if root.endswith(f".{ext[1:]}"):
        root = root[:-len(ext)]
    n = 2
    while os.path.exists(f"{root} ({n}){ext}"):
        n += 1
    return f"{root} ({n}){ext}"


def output_paths(media, folder, src, tgt, fmt, suffix=""):
    """Nomi dei file in uscita, accanto al video o nella cartella scelta.
    suffix: ".prova" per la prova su un minuto."""
    stem = os.path.splitext(os.path.basename(media))[0] + suffix
    base = os.path.join(folder or os.path.dirname(os.path.abspath(media)), stem)
    return {
        "srt_src": unique_path(f"{base}.{src}.srt"),
        "srt_tgt": unique_path(f"{base}.{tgt}.srt"),
        "srt_both": unique_path(f"{base}.{src}-{tgt}.srt"),
        "audio": unique_path(f"{base}.{tgt}.opus"),
        "video": unique_path(f"{base}.{tgt}.{fmt}"),
    }


# ── lavoro salvato ──────────────────────────────────────────────────────────
def _file_id(path):
    st = os.stat(path)
    return f"{os.path.realpath(path)}|{st.st_size}|{st.st_mtime_ns}"


def model_id(path):
    """Un modello si riconosce da nome e dimensione (non dal percorso: lo
    stesso file copiato altrove è lo stesso modello)."""
    try:
        return f"{os.path.basename(path)}|{os.path.getsize(path)}"
    except OSError:
        return os.path.basename(path or "")


def project_path(media):
    key = hashlib.sha256(_file_id(media).encode("utf-8")).hexdigest()[:24]
    return os.path.join(PROJECT_DIR, key + ".json")


def load_project(media):
    """Il lavoro salvato per questo video (lo stesso file: percorso,
    dimensione e data di modifica), o {}."""
    try:
        with open(project_path(media), encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) and data.get("version") == 1 else {}
    except (OSError, ValueError):
        return {}


def save_project(media, data):
    try:
        os.makedirs(PROJECT_DIR, mode=0o700, exist_ok=True)
        os.chmod(PROJECT_DIR, 0o700)
        path = project_path(media)
        data = dict(data, version=1, media=os.path.basename(media))
        fd = os.open(path + ".tmp", os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False)
        os.replace(path + ".tmp", path)
    except OSError:
        pass


def forget_project(media):
    try:
        os.unlink(project_path(media))
    except OSError:
        pass


def project_summary(media):
    """(c'è una trascrizione salvata, lingue in cui ci sono traduzioni)."""
    data = load_project(media) if media and os.path.isfile(media) else {}
    langs = set()
    for key, memory in (data.get("memory") or {}).items():
        if memory:
            langs.add(key.split("|")[1])
    return bool(data.get("transcripts")), sorted(langs)


def _transcript_key(o):
    return f"{model_id(o.whisper_model)}|{o.src}"


def _memory_key(src, tgt, llm_model, extra=""):
    """Chiave della memoria: lingue, modello, versione del modo di
    tradurre, e un'impronta di genere e glossario (se cambiano, le
    traduzioni vecchie non valgono più)."""
    tag = hashlib.sha256(extra.encode("utf-8")).hexdigest()[:8] if extra else "-"
    return f"{src}|{tgt}|{model_id(llm_model)}|v{PROMPT_VERSION}|{tag}"


def trim_cues(cues, limit_ms):
    """Le battute che cominciano prima di limit_ms, tagliate a limit_ms."""
    return [Cue(c.start, min(c.end, limit_ms), c.text) for c in cues
            if c.start < limit_ms - 300]


# ── la catena ───────────────────────────────────────────────────────────────
STAGES = ("transcribe", "translate", "dub", "mix")
Options = collections.namedtuple("Options", [
    "media", "folder", "src", "tgt", "whisper_model", "llm_model", "voice", "speaker_file",
    "voice_name", "gpu", "whisper_device", "llm_device", "tts_device", "threads", "context", "max_speed", "seed", "ducking",
    "outputs", "fmt", "titles", "source_srt", "reuse", "preview", "gender", "glossary",
    "burn"],
    defaults=(True, False, "auto", "", False))
# whisper_device, llm_device, tts_device: la scheda grafica di ogni passo
# (descrizione di list_devices(), "" = scelta del motore).
# outputs: insieme di "srt", "audio", "video". source_srt: file SRT della
# lingua originale da usare al posto della trascrizione ("" = trascrivere).
# reuse: usare la trascrizione e le traduzioni salvate per questo video.
# preview: doppiare solo il primo minuto (file «.prova»).
# gender: "auto" (dall'altezza della voce e dalla grammatica), "male",
# "female". glossary: «termine = traduzione; …» (facoltativo).
# burn: sottotitoli tradotti impressi nell'immagine (si ricodifica).


class Dubbing:
    """Un doppiaggio per volta. Le callback arrivano nel thread
    dell'interfaccia (GLib.idle_add):
        on_stage(stage, fraction, detail)  stage: uno di STAGES; fraction 0–1
        on_log(line)                       righe dei programmi
        on_done(error, files, stats)       error: None, "cancelled" o
                                           DubbingError; files: {tipo: percorso}
    """

    def __init__(self, on_stage=None, on_log=None, on_done=None):
        self.on_stage = on_stage or (lambda stage, fraction=0.0, detail="": None)
        self.on_log = on_log or (lambda line: None)
        self.on_done = on_done or (lambda error, files, stats: None)
        self.engine = engine.Engine(APP_ID, on_log=self._log_main)
        self.transcriber = None
        self.speaker = None
        self.stop_event = threading.Event()
        self.running = False
        self.o = None
        self.cues = []
        self.translated = []
        self.stats = {}
        self.run_dir = None
        self.files = {}
        self._proc = None
        self._lock = threading.Lock()

    # ── comandi dall'interfaccia ──────────────────────────────────────────
    def start(self, o):
        if self.running:
            return
        for find, key in ((whisper.find_ffmpeg, "err_no_ffmpeg"),
                          (engine.find_binary, "err_no_llm_engine"),
                          (tts.find_binary, "err_no_llm_engine")):
            if not find():
                raise DubbingError(key)
        if not o.source_srt and not whisper.find_binary():
            raise DubbingError("err_no_whisper_engine")
        if not os.path.isfile(o.media):
            raise DubbingError("open_error", o.media)
        if not o.source_srt and (not o.whisper_model or not os.path.isfile(o.whisper_model)):
            raise DubbingError("err_no_whisper_model")
        if not o.llm_model or not os.path.isfile(o.llm_model):
            raise DubbingError("err_no_llm_model")
        if "audio" in o.outputs or "video" in o.outputs:
            if not o.voice or not os.path.isfile(o.voice.model):
                raise DubbingError("err_no_voice_model")
        if o.tgt not in CODES:
            raise DubbingError("err_language", o.tgt)
        folder = o.folder or os.path.dirname(os.path.abspath(o.media))
        if not os.access(folder, os.W_OK):
            raise DubbingError("err_folder", folder)
        self.o = o
        self.stop_event.clear()
        self.running = True
        self.files, self.stats = {}, {}
        self.cues, self.translated = [], []
        self.paths = None
        self.units = None
        self.refit_done = False
        self.lexicon = None
        self.pre_queue, self.pregen, self.pre_count = [], {}, 0
        self.pre_speaker = None
        self.waiting_dub = False
        os.makedirs(WORK_DIR, mode=0o700, exist_ok=True)
        os.chmod(WORK_DIR, 0o700)
        self.run_dir = tempfile.mkdtemp(prefix="run-", dir=WORK_DIR)
        self.media_work = o.media
        # Il lavoro salvato si carica sempre (per aggiungervi), ma si usa
        # solo con reuse: «Rifai tutto» rifà e sovrascrive.
        self.project = load_project(o.media)
        threading.Thread(target=self._prepare_work, daemon=True).start()

    def _prepare_work(self):
        """Fuori dall'interfaccia: lo spezzone della prova e la lettura del
        video."""
        o = self.o
        error = None
        try:
            if o.preview:
                self.on_stage_safe("transcribe", 0.0, "preview")
                clip = os.path.join(self.run_dir, "prova.mkv")
                code, tail = self._run([
                    tts.find_ffmpeg(), "-nostdin", "-hide_banner", "-loglevel", "error",
                    "-protocol_whitelist", "file", "-i", o.media, "-map", "0", "-t",
                    f"{PREVIEW_MS / 1000:.3f}", "-c", "copy", "-y", clip])
                if code != 0 or not os.path.isfile(clip):
                    raise DubbingError("err_mux", tail)
                self.media_work = clip
            self.info = probe(self.media_work)
        except _Stopped:
            error = "cancelled"
        except DubbingError as e:
            error = e
        except OSError as e:
            error = DubbingError("open_error", str(e))
        if error:
            self._emit(self._finish, error)
        else:
            self._emit(self._after_prepare)

    def on_stage_safe(self, *args):
        self._emit(self.on_stage, *args)

    def _after_prepare(self):
        o = self.o
        if o.source_srt:
            self._use_source_srt()
            return
        saved = (self.project.get("transcripts") or {}).get(_transcript_key(o))
        if o.reuse and saved and saved.get("cues"):
            # Trascrizione già fatta per questo video, con questo modello.
            cues = [Cue(int(a), int(b), str(t)) for a, b, t in saved["cues"]]
            if o.preview:
                cues = trim_cues(cues, PREVIEW_MS)
            self.stats["reused_transcript"] = True
            self.on_log("ruscadubbing: trascrizione salvata, non si rifà")
            self._transcribed(None, saved.get("language", ""), None, cues=cues)
            return
        self._transcribe()

    def cancel(self):
        if not self.running:
            return
        self.stop_event.set()
        if self.transcriber is not None:
            self.transcriber.cancel()
        if self.speaker is not None:
            self.speaker.cancel()
        if getattr(self, "pre_speaker", None) is not None:
            self.pre_speaker.cancel()
        # Chiudere il server interrompe anche una richiesta di traduzione in corso.
        self.engine.stop()
        with self._lock:
            proc = self._proc
        if proc is not None and proc.poll() is None:
            try:
                proc.terminate()
            except OSError:
                pass

    def shutdown(self):
        """Alla chiusura del programma: ferma tutto e cancella i file di lavoro."""
        self.cancel()
        self.engine.stop()
        clean_work_dir()

    # ── passi ─────────────────────────────────────────────────────────────
    def _log_main(self, line):
        self.on_log(line)

    def _emit(self, callback, *args):
        GLib.idle_add(lambda: callback(*args) and False)

    def _use_source_srt(self):
        try:
            with open(self.o.source_srt, encoding="utf-8-sig", errors="replace") as f:
                self.cues = cues_from_srt(f.read())
        except OSError as e:
            self._finish(DubbingError("open_error", str(e)))
            return
        if self.o.preview:
            self.cues = trim_cues(self.cues, PREVIEW_MS)
        if not self.cues:
            self._finish(DubbingError("err_no_speech"))
            return
        self.src = self.o.src if self.o.src != "auto" else "en"
        self.on_stage("transcribe", 1.0, "")
        self._translate()

    def _transcribe(self):
        self.on_stage("transcribe", 0.0, "")
        self.transcriber = whisper.Transcriber(
            on_stage=lambda stage, percent=0: self.on_stage(
                "transcribe", (percent / 100) if stage == "speech" else 0.0, stage),
            on_log=self.on_log, on_done=self._transcribed)
        try:
            self.transcriber.start(self.media_work, self.o.whisper_model, self.o.src,
                                   self.o.threads, self.o.gpu, self.o.whisper_device)
        except whisper.WhisperError as e:
            self._finish(DubbingError(e.key, e.detail))

    def _transcribed(self, error, language, segments, cues=None):
        self.transcriber = None
        if error:
            self._finish(error if error == "cancelled" else DubbingError(error.key, error.detail))
            return
        self.cues = cues if cues is not None else cues_from_segments(segments)
        if self.o.preview:
            self.cues = trim_cues(self.cues, PREVIEW_MS)
        if cues is None and not self.o.preview and self.cues:
            # Si salva solo la trascrizione del video intero.
            self.project.setdefault("transcripts", {})[_transcript_key(self.o)] = {
                "language": language or "",
                "cues": [[c.start, c.end, c.text] for c in self.cues]}
            save_project(self.o.media, self.project)
        if not self.cues:
            self._finish(DubbingError("err_no_speech"))
            return
        self.src = language or (self.o.src if self.o.src != "auto" else "en")
        self.on_stage("transcribe", 1.0, self.src)
        self._translate()

    def _translate(self):
        o = self.o
        self.on_stage("translate", 0.0, "")
        self.parts = cue_parts(self.cues)
        self.blocks = group_blocks(self.parts)
        self.stats["blocks"] = len(self.blocks)
        if self.src == o.tgt:
            # Stessa lingua: niente traduzione, il doppiaggio rilegge il testo.
            self.block_texts = [c.text for c in block_cues(self.parts, self.blocks)]
            self.translated = [c.text for c in self.cues]
            self._after_translation()
            return
        # Memoria delle traduzioni di questo video: una frase già tradotta
        # (stessa lingua, stesso modello) non si ritraduce.
        self.units = block_cues(self.parts, self.blocks)
        self.glossary = parse_glossary(o.glossary)
        extra = o.gender + "|" + "; ".join(f"{a}={b}" for a, b in self.glossary)
        self.memory_key = _memory_key(self.src, o.tgt, o.llm_model,
                                      "" if extra == "auto|" else extra)
        self.notes = (self.project.get("briefs") or {}).get(self.memory_key, "")
        memory = (self.project.get("memory") or {}).get(self.memory_key) or {}
        self.known = [memory.get(u.text, "") if o.reuse else "" for u in self.units]
        if all(self.known):
            self.on_log("ruscadubbing: traduzione salvata, non si rifà")
            self.stats["reused"] = len(self.units)
            self._set_translations(self.known)
            self._after_translation()
            return
        threading.Thread(target=self._translate_work, daemon=True).start()

    def _set_translations(self, texts):
        self.block_texts = [clean_translation(u.text, t) for u, t in zip(self.units, texts)]
        self.translated = translations_per_cue(self.cues, self.parts, self.blocks,
                                               self.block_texts)

    def _translate_work(self):
        o = self.o
        error = None
        try:
            if not self.notes:
                gender = o.gender
                if gender == "auto":
                    gender = guess_gender(self._speaker_pitch())
                self._start_llm()
                self._emit(self.on_stage, "translate", 0.0, "brief")
                try:
                    brief = self.engine.chat(brief_request(self.units, self.src, o.tgt)) or ""
                except engine.EngineError:
                    raise
                except Exception as e:      # noqa: BLE001 — la scheda è un aiuto
                    if self.stop_event.is_set():
                        raise _Stopped() from e
                    brief = ""
                self.notes = make_notes(brief, speaker_note(gender, o.tgt), self.glossary)
                self.project.setdefault("briefs", {})[self.memory_key] = self.notes
                self._emit(self.on_log, "ruscadubbing: scheda del discorso:\n" + self.notes)
            else:
                self._start_llm()
            on_batch = None
            first = None
            if self._parallel():
                # Due schede: la voce comincia a dire ogni gruppo di frasi
                # appena è tradotto, mentre il modello traduce i successivi.
                self._emit(self.on_log, "ruscadubbing: traduzione e voce in parallelo")

                def on_batch(idx, result):
                    texts = {k: clean_translation(self.units[k].text, result[k])
                             for k in idx if result[k]}
                    self._mark_stress_texts(texts)
                    self._emit(self._pregen_add, texts)
                first = PARALLEL_FIRST
            texts, tstats = translate_cues(
                self.engine.chat, self.units, self.src, self.o.tgt, self.stop_event,
                lambda i, n: self._emit(self.on_stage, "translate", i / max(1, n), f"{i}/{n}"),
                self.o.max_speed, known=self.known, notes=self.notes, on_batch=on_batch,
                first=first)
            self.stats.update(tstats)
            self._set_translations(texts)
            if self.o.tgt in speech.HOMOGRAPHS:
                self._emit(self.on_stage, "translate", 1.0, "stress")
                self._mark_stress(range(len(self.block_texts)))
            memory = self.project.setdefault("memory", {}).setdefault(self.memory_key, {})
            for u, t, k in zip(self.units, self.block_texts, self.known):
                # Le frasi lasciate nell'originale non si ricordano.
                if t and not k and t != u.text:
                    memory[u.text] = t
            save_project(self.o.media, self.project)
        except _Stopped:
            error = "cancelled"
        except engine.EngineError as e:
            error = "cancelled" if self.stop_event.is_set() else DubbingError(e.key, e.detail)
        except Exception as e:      # noqa: BLE001 — connessione persa, risposta rotta
            error = "cancelled" if self.stop_event.is_set() else DubbingError("connection_error", str(e))
        # Il modello di traduzione si chiude: la scheda grafica serve alla voce.
        self.engine.stop(wait=True)
        if error:
            self._emit(self._finish, error)
        else:
            self._emit(self._after_translation)

    def _after_translation(self):
        o = self.o
        self.on_stage("translate", 1.0, "")
        try:
            self._write_subtitles()
        except OSError as e:
            self._finish(DubbingError("save_error", str(e)))
            return
        if "audio" not in o.outputs and "video" not in o.outputs:
            self._finish(None)
            return
        if self.pre_speaker is not None or self.pre_queue:
            # La voce sta ancora dicendo le frasi già tradotte: si aspetta.
            self.waiting_dub = True
            self.on_stage("dub", 0.0, "")
            self._pregen_progress(0)
            return
        self._dub()

    def _write_subtitles(self):
        o = self.o
        if not self.paths:
            self.paths = output_paths(o.media, o.folder, self.src, o.tgt, o.fmt,
                                      ".prova" if o.preview else "")
        self.work_srt_src = os.path.join(self.run_dir, "originale.srt")
        self.work_srt_tgt = os.path.join(self.run_dir, "tradotto.srt")
        # Sottotitoli divisi con le regole professionali: gli originali
        # battuta per battuta, quelli tradotti frase per frase sul testo
        # tradotto (non sui tagli dell'originale).
        src_subs, _fast = segment_subtitles(self.cues, [c.text for c in self.cues], self.src)
        if getattr(self, "blocks", None) and getattr(self, "block_texts", None):
            units = block_cues(self.parts, self.blocks)
            tgt_subs, fast = segment_subtitles(units, self.block_texts, o.tgt)
        else:
            tgt_subs, fast = segment_subtitles(self.cues, self.translated, o.tgt)
        if o.preview:
            # Nella prova nessun sottotitolo va oltre lo spezzone.
            limit = self.info["duration_ms"] or PREVIEW_MS
            src_subs = [Cue(c.start, min(c.end, limit), c.text) for c in src_subs if c.start < limit]
            tgt_subs = [Cue(c.start, min(c.end, limit), c.text) for c in tgt_subs if c.start < limit]
        self.stats["fast_subtitles"] = fast
        self.stats["subtitles"] = len(tgt_subs)
        for path, text in ((self.work_srt_src, to_srt(src_subs)),
                           (self.work_srt_tgt, to_srt(tgt_subs))):
            with open(path, "w", encoding="utf-8") as f:
                f.write(text)
        if "srt" in o.outputs:
            for key, src_path in (("srt_src", self.work_srt_src), ("srt_tgt", self.work_srt_tgt)):
                shutil.copyfile(src_path, self.paths[key])
                self.files[key] = self.paths[key]
            with open(self.paths["srt_both"], "w", encoding="utf-8") as f:
                f.write(bilingual_srt(self.cues, self.translated))
            self.files["srt_both"] = self.paths["srt_both"]

    def _dub(self, reuse=None):
        o = self.o
        self.on_stage("dub", 0.0, "")
        # La voce dice ogni frase intera, dall'inizio della prima battuta.
        units = block_cues(self.parts, self.blocks)
        self.piece_units = [k for k, t in enumerate(self.block_texts) if t.strip()]
        pieces = [tts.Piece(self._speech_text(self.block_texts[k]), 0, units[k].start,
                            units[k].end)
                  for k in self.piece_units]
        if reuse is None and self.pregen:
            # Frasi già dette in parallelo alla traduzione, se il testo è lo
            # stesso.
            reuse = {}
            for i, k in enumerate(self.piece_units):
                said = self.pregen.get(k)
                if said and said[0] == pieces[i].text and os.path.isfile(said[1]):
                    reuse[i] = said[1]
            self.stats["parallel"] = len(reuse)
        self.pieces = pieces
        self.keep_dir = os.path.join(self.run_dir, "frasi")
        os.makedirs(self.keep_dir, exist_ok=True)
        self.speaker = tts.Speaker(
            on_progress=lambda i, n: self.on_stage("dub", i / max(1, n), f"{i + 1}/{n}"),
            on_stage=lambda stage: self.on_stage("dub", 1.0, stage),
            on_log=self.on_log, on_done=self._dubbed)
        try:
            self.speaker.start(pieces, o.voice, srt=True, language=o.tgt,
                               speaker_file=o.speaker_file, voice_name=o.voice_name,
                               gpu=o.gpu, gpu_device=o.tts_device, threads=o.threads,
                               seed=o.seed, max_speed=o.max_speed, normalize=True,
                               keep_dir=self.keep_dir, reuse=reuse)
        except tts.TTSError as e:
            self._finish(DubbingError(e.key, e.detail))

    def _dubbed(self, error, path, stats):
        speaker, self.speaker = self.speaker, None
        if error:
            if speaker is not None:
                speaker.discard()
            self._finish(error if error == "cancelled" else DubbingError(error.key, error.detail))
            return
        durations = stats.pop("durations", [])
        self.stats.update(stats)
        # Verifica: le frasi che, dette, non stanno nel loro tempo si fanno
        # accorciare e si ridicono; le altre si riusano. Una volta sola, e
        # solo se c'è stata una traduzione (un testo da riscrivere).
        if not self.refit_done and getattr(self, "units", None) and self.src != self.o.tgt:
            long_ones = too_long(self.pieces, durations, self.o.max_speed)
            if long_ones:
                self.refit_done = True
                speaker.discard()
                self.on_log(f"ruscadubbing: {len(long_ones)} frasi troppo lunghe da dire, "
                            "si accorciano")
                self.on_stage("dub", 1.0, "refit")
                targets = {self.piece_units[i]: chars for i, chars in long_ones}
                threading.Thread(target=self._refit_work, args=(targets,), daemon=True).start()
                return
        self.on_stage("dub", 1.0, "")
        self.on_stage("mix", 0.0, "")
        threading.Thread(target=self._mix_work, args=(path, speaker), daemon=True).start()

    def _speaker_pitch(self):
        """Altezza mediana della voce originale in Hz (0 se non si misura):
        un minuto delle battute più lunghe, come «Trova una voce simile»."""
        if not self.info.get("audio"):
            return 0
        try:
            import rusca_voicematch as match
            ffmpeg = tts.find_ffmpeg()
            wav = os.path.join(self.run_dir, "voce-originale.wav")
            match.extract_reference(ffmpeg, self.media_work,
                                    match.speech_windows(self.info["duration_ms"], self.cues), wav)
            hz = match.semitones_to_hz(match.measure(ffmpeg, wav).pitch)
            os.unlink(wav)
            self._emit(self.on_log, f"ruscadubbing: voce originale a circa {hz:.0f} Hz")
            return hz
        except Exception as e:      # noqa: BLE001 — è solo un indizio
            self._emit(self.on_log, f"ruscadubbing: altezza della voce non misurata ({e})")
            return 0

    def _speech_text(self, text):
        """Il testo da dare alla voce: omografi segnati, lessico, numeri in
        lettere."""
        lang = self.o.tgt
        if self.lexicon is None:
            self.lexicon = speech.load_lexicon(*[os.path.join(d, f"pronunce-{lang}.tsv")
                                                 for d in LEXICON_DIRS])
        stress = ((self.project.get("stress") or {}).get(getattr(self, "memory_key", ""))
                  or {})
        return speech.speech_text(text, lang, self.lexicon, stress.get(text))

    def _parallel(self):
        o = self.o
        return bool(o.gpu and o.llm_device and o.tts_device and o.llm_device != o.tts_device
                    and ("audio" in o.outputs or "video" in o.outputs))

    # ── voce in parallelo alla traduzione (due schede) ────────────────────
    def _pregen_add(self, texts):
        if texts:
            self.pre_queue.append(texts)
        self._pregen_next()
        return False

    def _pregen_next(self):
        if self.pre_speaker is not None or self.stop_event.is_set():
            return
        if not self.pre_queue:
            if self.waiting_dub:
                self.waiting_dub = False
                self._dub()
            return
        texts = self.pre_queue.pop(0)
        o = self.o
        keys = sorted(texts)
        said = [self._speech_text(texts[k]) for k in keys]
        self.pre_count += 1
        folder = os.path.join(self.run_dir, "prima", str(self.pre_count))
        os.makedirs(folder, exist_ok=True)
        pieces = [tts.Piece(t, 0, self.units[k].start, self.units[k].end)
                  for k, t in zip(keys, said)]
        self._pregen_progress(0)
        self.pre_speaker = tts.Speaker(
            on_progress=lambda i, n: self._pregen_progress(i),
            on_log=self.on_log,
            on_done=lambda e, p, s: self._pregen_done(e, keys, said, folder))
        try:
            self.pre_speaker.start(pieces, o.voice, srt=False, language=o.tgt,
                                   speaker_file=o.speaker_file, voice_name=o.voice_name,
                                   gpu=o.gpu, gpu_device=o.tts_device, threads=o.threads,
                                   seed=o.seed, normalize=False, keep_dir=folder)
        except tts.TTSError as e:
            # Non è grave: le frasi si diranno dopo, nel passaggio normale.
            self.on_log(f"ruscadubbing: voce in parallelo non partita ({e})")
            self.pre_speaker = None
            self.pre_queue.clear()
            self._pregen_next()

    def _pregen_progress(self, i):
        """Mostra sulla riga del doppiaggio quante frasi la voce ha già
        detto in parallelo alla traduzione."""
        if self.running:
            self.on_stage("dub", 0.0, f"parallel:{len(self.pregen) + i}/{len(self.units)}")

    def _pregen_done(self, error, keys, said, folder):
        speaker, self.pre_speaker = self.pre_speaker, None
        if error is None:
            for j, (k, text) in enumerate(zip(keys, said)):
                self.pregen[k] = (text, os.path.join(folder, f"{j:05d}.wav"))
            self._pregen_progress(0)
        elif error != "cancelled":
            self.on_log(f"ruscadubbing: voce in parallelo non riuscita ({error}): "
                        "quelle frasi si diranno dopo")
        if speaker is not None:
            speaker.discard()
        if self.running:
            self._pregen_next()

    def _mark_stress(self, indices):
        """Con il modello acceso: gli omografi delle frasi indicate, segnati
        con l'accento secondo il senso (solo per la voce), nella memoria."""
        self._mark_stress_texts({k: self.block_texts[k] for k in indices})

    def _mark_stress_texts(self, texts):
        """Come _mark_stress(), per i testi dati ({frase: testo})."""
        lang = self.o.tgt
        if lang not in speech.HOMOGRAPHS:
            return
        memory = self.project.setdefault("stress", {}).setdefault(self.memory_key, {})
        todo = [k for k in sorted(texts) if speech.needs_stress(texts[k], lang)
                and texts[k] not in memory]
        for start in range(0, len(todo), BATCH):
            if self.stop_event.is_set():
                raise _Stopped()
            idx = todo[start:start + BATCH]
            try:
                got = parse_translations(self.engine.chat(speech.stress_request(
                    [(k + 1, texts[k]) for k in idx], lang)))
            except engine.EngineError:
                raise
            except Exception:      # noqa: BLE001 — gli accenti sono un aiuto
                if self.stop_event.is_set():
                    raise _Stopped()
                continue
            for k in idx:
                memory[texts[k]] = speech.apply_stress(texts[k], got.get(k + 1, ""), lang)
        if todo:
            self.stats["stressed"] = self.stats.get("stressed", 0) + sum(
                1 for k in todo if memory.get(texts[k]) != texts[k])

    def _start_llm(self):
        """Avvia llama-server con il modello di traduzione (nel thread di
        lavoro) e aspetta che sia pronto."""
        o = self.o
        args = ["-t", o.threads, "-c", o.context, "-b", 2048, "-ub", 1024, "--parallel", 1,
                "--flash-attn", "on", "--reasoning", "off"]
        if o.gpu and o.llm_device:
            # list_devices apre un processo: qui, fuori dall'interfaccia.
            device = engine.device_name(o.llm_device, engine.list_devices())
            if device:
                args += ["--device", device]
        self.engine.start(o.llm_model, args, o.gpu)
        if not self.engine.wait_ready(self.stop_event):
            if self.stop_event.is_set():
                raise _Stopped()
            raise engine.EngineError("engine_not_ready")

    def _refit_work(self, targets):
        """Accorcia le frasi troppo lunghe (targets: {frase: caratteri})."""
        error, changed = None, {}
        try:
            self._start_llm()
            changed = shorten_translations(
                self.engine.chat, [u.text for u in self.units], self.block_texts, targets,
                self.src, self.o.tgt, self.stop_event, notes=getattr(self, "notes", ""))
            if changed and self.o.tgt in speech.HOMOGRAPHS:
                saved = {k: self.block_texts[k] for k in changed}
                for k, text in changed.items():
                    self.block_texts[k] = clean_translation(self.units[k].text, text)
                self._mark_stress(list(changed))
                for k, text in saved.items():
                    self.block_texts[k] = text
        except _Stopped:
            error = "cancelled"
        except engine.EngineError as e:
            error = "cancelled" if self.stop_event.is_set() else DubbingError(e.key, e.detail)
        except Exception as e:      # noqa: BLE001 — connessione persa, risposta rotta
            error = "cancelled" if self.stop_event.is_set() else DubbingError("connection_error", str(e))
        self.engine.stop(wait=True)
        if error:
            self._emit(self._finish, error)
        else:
            self._emit(self._refitted, changed)

    def _refitted(self, changed):
        """Le frasi accorciate entrano nella traduzione, nei sottotitoli e
        nella memoria; la voce ridice solo quelle."""
        self.stats["refit"] = len(changed)
        for k, text in changed.items():
            self.block_texts[k] = clean_translation(self.units[k].text, text)
        if changed:
            self.translated = translations_per_cue(self.cues, self.parts, self.blocks,
                                                   self.block_texts)
            memory = self.project.setdefault("memory", {}).setdefault(self.memory_key, {})
            for k in changed:
                memory[self.units[k].text] = self.block_texts[k]
            save_project(self.o.media, self.project)
            try:
                self._write_subtitles()
            except OSError as e:
                self._finish(DubbingError("save_error", str(e)))
                return
        reuse = {}
        for i, k in enumerate(self.piece_units):
            if k not in changed:
                reuse[i] = os.path.join(self.keep_dir, f"{i:05d}.wav")
        # Se il numero dei pezzi resta lo stesso (sempre: nessuna frase
        # diventa vuota), gli indici coincidono.
        self._dub(reuse=reuse)
        return False

    def _run(self, cmd, cwd=None):
        self._emit(self.on_log, "$ " + " ".join(cmd))
        proc = subprocess.Popen(cmd, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                                stderr=subprocess.STDOUT, start_new_session=True, cwd=cwd)
        with self._lock:
            self._proc = proc
        out = proc.communicate()[0].decode("utf-8", "replace")
        with self._lock:
            self._proc = None
        for line in out.splitlines()[-20:]:
            self._emit(self.on_log, line)
        if self.stop_event.is_set():
            raise _Stopped()
        return proc.returncode, "\n".join(out.strip().splitlines()[-8:])

    def _mix_work(self, voice_wav, speaker):
        o = self.o
        error = None
        ffmpeg = tts.find_ffmpeg()
        try:
            has_audio = self.info["audio"] > 0
            mix = os.path.join(self.run_dir, "doppiaggio.wav")
            code, tail = self._run(mix_command(ffmpeg, self.media_work, voice_wav, mix, has_audio,
                                               o.ducking))
            if code != 0 or not os.path.isfile(mix):
                raise DubbingError("err_mix", tail)
            self._emit(self.on_stage, "mix", 0.4, "")
            if "audio" in o.outputs:
                tmp = self.paths["audio"] + ".part"
                code, tail = self._run([ffmpeg, "-nostdin", "-hide_banner", "-loglevel", "error",
                                        "-protocol_whitelist", "file", "-i", mix,
                                        "-c:a", "libopus", "-b:a", "160k", "-f", "ogg", "-y", tmp])
                if code != 0 or not os.path.isfile(tmp):
                    raise DubbingError("err_mix", tail)
                os.replace(tmp, self.paths["audio"])
                self.files["audio"] = self.paths["audio"]
            self._emit(self.on_stage, "mix", 0.6, "")
            if "video" in o.outputs:
                tmp = self.paths["video"] + ".part"
                if o.burn and self.info["video"]:
                    # libass legge il file dalla cartella di lavoro: niente
                    # percorsi da proteggere nel filtro.
                    shutil.copyfile(self.work_srt_tgt, os.path.join(self.run_dir, BURN_FILE))
                    self._emit(self.on_stage, "mix", 0.65, "burn")
                code, tail = self._run(mux_command(
                    ffmpeg, self.media_work, mix, self.work_srt_src, self.work_srt_tgt, tmp, o.fmt,
                    self.src, o.tgt, has_audio, o.titles,
                    self.info["duration_ms"] if o.preview else 0,
                    burn=bool(o.burn and self.info["video"])), cwd=self.run_dir)
                if code != 0 or not os.path.isfile(tmp):
                    try:
                        os.unlink(tmp)
                    except OSError:
                        pass
                    raise DubbingError("err_mux_mp4" if o.fmt == "mp4" else "err_mux", tail)
                os.replace(tmp, self.paths["video"])
                self.files["video"] = self.paths["video"]
        except _Stopped:
            error = "cancelled"
        except DubbingError as e:
            error = e
        except OSError as e:
            error = DubbingError("save_error", str(e))
        finally:
            if speaker is not None:
                speaker.discard()
        self._emit(self._finish, error)

    def _finish(self, error):
        self.running = False
        self.transcriber = self.speaker = None
        if self.engine.running:
            self.engine.stop()
        if self.run_dir:
            shutil.rmtree(self.run_dir, ignore_errors=True)
            self.run_dir = None
        files = dict(self.files)        # anche dopo un errore: i file già scritti restano
        self.stats["cues"] = len(self.cues)
        self.on_done(error, files, dict(self.stats))
        return False
