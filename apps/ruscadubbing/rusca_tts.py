# -*- coding: utf-8 -*-
# rusca_tts.py — RuscaLinux OS Apps 1.99.3 — GPL-3.0-or-later
#
# Sintesi vocale di RuscaNarrator: divide il testo in pezzi, li fa leggere a
# llama-tts (pacchetto ruscallama-engine, cioe' llama.cpp: software esterno,
# licenza MIT) e monta l'audio:
#   * documento Markdown: i pezzi uno dopo l'altro, con una pausa che
#     dipende dal blocco (titolo, paragrafo, voce di elenco...);
#   * sottotitoli SRT: ogni sottotitolo all'ora in cui compare. Se la voce e'
#     piu' lunga del sottotitolo, si accelera (senza cambiare il tono) fino
#     alla velocita' massima scelta; se non basta, si sposta in avanti quanto
#     serve, senza mai sovrapporre due voci.
#
# llama-tts legge un pezzo per volta: parte, carica il modello, scrive un
# WAV ed esce. E' piu' lento di un server che tiene il modello in memoria,
# ma non apre nessuna porta, nemmeno su 127.0.0.1.
#
# Privacy e sicurezza (specifiche, sezione 11):
#   * nessun modulo di rete: il motore e FFmpeg sono avviati come programmi,
#     con percorso assoluto e lista di argomenti, mai tramite shell;
#   * FFmpeg lavora solo su file locali (-protocol_whitelist file);
#   * i file di lavoro stanno in ~/.cache/ruscanarrator (permessi 0700) e si
#     cancellano all'avvio, alla chiusura e quando si scarta il risultato.
import collections
import os
import re
import shutil
import signal
import subprocess
import tempfile
import threading
import unicodedata
import wave

from gi.repository import GLib

import rusca_markdown as md

# RUSCANARRATOR_ENGINE_DIR: per provare un motore compilato a mano.
ENGINE_DIRS = tuple(filter(None, (os.environ.get("RUSCANARRATOR_ENGINE_DIR"),
                                  "/usr/lib/ruscallama-engine")))
FFMPEG_PATHS = tuple(filter(None, (os.environ.get("RUSCANARRATOR_FFMPEG"), "/usr/bin/ffmpeg")))
SYSTEM_MODEL_DIR = "/usr/share/ruscanarrator/models"
USER_MODEL_DIR = os.path.join(GLib.get_user_data_dir(), "ruscanarrator", "models")
MODEL_DIRS = (SYSTEM_MODEL_DIR, USER_MODEL_DIR)
WORK_DIR = os.path.join(GLib.get_user_cache_dir(), "ruscanarrator")
# Voci create con «Crea una voce»: file WAV da usare come voce di riferimento.
VOICE_DIR = os.path.join(GLib.get_user_data_dir(), "ruscanarrator", "voices")

# Lingue che llama-tts sa chiedere al modello (--tts-lang): quelle di
# Qwen3-TTS. Altri modelli (Pocket TTS, Soprano) hanno la lingua nei pesi e
# ignorano l'opzione.
LANGUAGES = (("it", "Italiano"), ("en", "English"), ("de", "Deutsch"), ("fr", "Français"),
             ("es", "Español"), ("pt", "Português"), ("ru", "Русский"), ("zh", "中文"),
             ("ja", "日本語"), ("ko", "한국어"))

# Frase con cui si prova una voce nuova: circa dieci secondi di parlato, la
# durata che serve a una buona voce di riferimento.
SAMPLE_TEXT = {
    "it": "Buongiorno. Questa è la voce che leggerà i tuoi documenti: chiara, calma e "
          "naturale. Se ti piace, tienila; altrimenti ascoltane un'altra.",
    "en": "Good morning. This is the voice that will read your documents: clear, calm and "
          "natural. If you like it, keep it; otherwise, listen to another one.",
    "de": "Guten Morgen. Das ist die Stimme, die deine Dokumente vorlesen wird: klar, ruhig "
          "und natürlich. Wenn sie dir gefällt, behalte sie; sonst hör dir eine andere an.",
    "fr": "Bonjour. Voici la voix qui lira vos documents : claire, calme et naturelle. Si "
          "elle vous plaît, gardez-la ; sinon, écoutez-en une autre.",
    "es": "Buenos días. Esta es la voz que leerá tus documentos: clara, tranquila y "
          "natural. Si te gusta, quédatela; si no, escucha otra.",
    "pt": "Bom dia. Esta é a voz que vai ler os seus documentos: clara, calma e natural. "
          "Se gostar, fique com ela; se não, ouça outra.",
    "ru": "Доброе утро. Это голос, который будет читать ваши документы: ясный, спокойный "
          "и естественный. Если он вам нравится, оставьте его; если нет, послушайте другой.",
    "zh": "早上好。这是将为你朗读文档的声音：清晰、平静、自然。如果你喜欢，就留下它；否则，再听听另一个。",
    "ja": "おはようございます。これはあなたの文書を読み上げる声です。はっきりとして、落ち着いた、"
          "自然な声です。気に入ったら残してください。そうでなければ、別の声を聞いてみましょう。",
    "ko": "안녕하세요. 이것은 여러분의 문서를 읽어 줄 목소리입니다. 또렷하고 차분하며 "
          "자연스럽습니다. 마음에 들면 저장하고, 아니면 다른 목소리를 들어 보세요.",
}

# Un pezzo piu' lungo di cosi' si divide alle fine delle frasi: i modelli
# leggono meglio frasi brevi, e llama-tts si ferma comunque a 512 frame
# (circa 40 secondi con Qwen3-TTS).
MAX_CHARS = 260
# Pause dopo ogni tipo di blocco, in millisecondi.
PAUSES = {"heading": 900, "text": 650, "item": 400, "quote": 650, "table": 400,
          "math": 650, "note": 500, "break": 1200}
PAUSE_INSIDE = 250            # fra i pezzi di uno stesso blocco
# Silenzio tolto all'inizio e alla fine di ogni pezzo generato: i modelli ne
# aggiungono un po', e nei sottotitoli la voce deve partire all'ora giusta.
TRIM_FILTER = ("silenceremove=start_periods=1:start_threshold=-50dB:start_silence=0.05,"
               "areverse,"
               "silenceremove=start_periods=1:start_threshold=-50dB:start_silence=0.1,"
               "areverse")
# Volume finale: EBU R128, -16 LUFS, picco -1,5 dB (voce parlata).
LOUDNORM = "loudnorm=I=-16:TP=-1.5:LRA=11"
EXPORT_FORMATS = {
    "wav": ["-c:a", "pcm_s16le"],
    "flac": ["-c:a", "flac", "-compression_level", "8"],
    "opus": ["-c:a", "libopus", "-b:a", "160k", "-application", "audio"],
    "mp3": ["-c:a", "libmp3lame", "-q:a", "0"],
}

Piece = collections.namedtuple("Piece", "text pause start end", defaults=(0, None, None))
Voice = collections.namedtuple("Voice", "model mmproj")


class TTSError(Exception):
    """Errore con un messaggio per l'utente: `key` e' la chiave di traduzione."""

    def __init__(self, key, detail=""):
        super().__init__(f"{key}: {detail}" if detail else key)
        self.key = key
        self.detail = detail


# ── che cosa c'e' sul computer ──────────────────────────────────────────────
def _executable(paths):
    for p in paths:
        if p and os.path.isfile(p) and os.access(p, os.X_OK):
            return p
    return None


def find_binary():
    return _executable(os.path.join(d, "llama-tts") for d in ENGINE_DIRS)


def find_ffmpeg():
    return _executable(FFMPEG_PATHS)


def physical_cores():
    base = "/sys/devices/system/cpu"
    first = set()
    try:
        for name in os.listdir(base):
            if name.startswith("cpu") and name[3:].isdigit():
                try:
                    with open(os.path.join(base, name, "topology", "thread_siblings_list")) as f:
                        first.add(f.read().strip().split(",")[0].split("-")[0])
                except OSError:
                    continue
    except OSError:
        pass
    return len(first) or os.cpu_count() or 4


# Precisione nel nome del file: "-Q8_0", "-Q4_K_M", "-bf16", "-f16"...
_PRECISION = re.compile(r"[-_.]((?:I?Q\d[\w]*)|bf16|f16|f32|fp16|fp32)$", re.IGNORECASE)
_RANK = {"f32": 6, "fp32": 6, "bf16": 5, "f16": 4, "fp16": 4, "q8_0": 3}


def _stem(name):
    """Nome del modello senza estensione, senza "mmproj" e senza precisione:
    "mmproj-Qwen3-TTS-1.7B-Base-Q8_0.gguf" -> "qwen3-tts-1.7b-base"."""
    stem = name[:-5] if name.lower().endswith(".gguf") else name
    stem = re.sub(r"^mmproj[-_.]?|[-_.]?mmproj$", "", stem, flags=re.IGNORECASE)
    return _PRECISION.sub("", stem).lower()


def _rank(name):
    m = _PRECISION.search(name[:-5] if name.lower().endswith(".gguf") else name)
    return _RANK.get(m.group(1).lower(), 1) if m else 0


# Chatterbox (Resemble AI) in llama.cpp: llama-tts passa il testo al modello
# così com'è, mentre il programma originale lo prepara prima. Senza questa
# preparazione le lettere accentate non sono quelle viste in addestramento
# (scomposte in NFKD: «à» = «a» + accento) e la voce sbaglia l'accento
# delle parole («quantìta» per «quantità»), e certi segni («...», «:»)
# finiscono letti o detti male.
_CHATTERBOX_PUNCT = (("...", ", "), ("…", ", "), (":", ","), (" - ", ", "), (";", ", "),
                     ("—", "-"), ("–", "-"), (" ,", ","), ("“", '"'), ("”", '"'),
                     ("‘", "'"), ("’", "'"), ("«", '"'), ("»", '"'))
_CHATTERBOX_ENDS = (".", "!", "?", "-", ",", "、", "，", "。", "？", "！")
_kind_cache = {}


def is_chatterbox(model):
    """Vero se il file GGUF è un modello Chatterbox (dal nome o
    dall'architettura scritta all'inizio del file)."""
    if not model:
        return False
    if "chatterbox" in os.path.basename(model).lower():
        return True
    if model not in _kind_cache:
        try:
            with open(model, "rb") as f:
                _kind_cache[model] = b"chatterbox" in f.read(1 << 18).lower()
        except OSError:
            _kind_cache[model] = False
    return _kind_cache[model]


def prepare_text(text, model):
    """Il testo come lo prepara il programma originale del modello: per
    Chatterbox punteggiatura semplificata, prima lettera maiuscola, segno
    finale, e (modello multilingue) lettere scomposte in NFKD. Per gli
    altri modelli il testo resta com'è."""
    if not is_chatterbox(model):
        return text
    text = " ".join(text.split())
    if not text:
        return text
    text = text[0].upper() + text[1:]
    for old, new in _CHATTERBOX_PUNCT:
        text = text.replace(old, new)
    text = " ".join(text.split())
    if not text.endswith(_CHATTERBOX_ENDS):
        text += "."
    if "turbo" not in os.path.basename(model).lower():
        text = unicodedata.normalize("NFKD", text)
    return text


def find_voices(dirs=None):
    """Modelli di sintesi vocale: ogni modello GGUF con il suo mmproj, nella
    stessa cartella. Il mmproj e' quello con lo stesso nome (a parte
    "mmproj" e la precisione), o l'unico della cartella; fra piu' mmproj
    adatti si sceglie il piu' preciso (bf16 prima di Q8_0), per la qualita'.
    Un modello senza mmproj non si puo' usare e non compare."""
    voices = []
    for d in (MODEL_DIRS if dirs is None else dirs):
        if not d or not os.path.isdir(d):
            continue
        for root, _dirs, files in os.walk(d):
            ggufs = sorted(f for f in files if f.lower().endswith(".gguf") and not f.startswith("."))
            projs = [f for f in ggufs if "mmproj" in f.lower()]
            for f in ggufs:
                if f in projs:
                    continue
                same = [p for p in projs if _stem(p) == _stem(f)]
                pick = same or (projs if len(projs) == 1 else [])
                if pick:
                    best = max(pick, key=lambda p: (_rank(p), p))
                    voices.append(Voice(os.path.join(root, f), os.path.join(root, best)))
    voices.sort(key=lambda v: os.path.basename(v.model).lower())
    return voices


def ensure_user_model_dir():
    os.makedirs(USER_MODEL_DIR, exist_ok=True)
    return USER_MODEL_DIR


def clean_work_dir():
    """Cancella i file di lavoro rimasti: e' audio dell'utente."""
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


# ── voci salvate ────────────────────────────────────────────────────────────
def sample_text(language):
    return SAMPLE_TEXT.get(language, SAMPLE_TEXT["en"])


def find_voice_files(folder=None):
    """Voci salvate: [(nome, percorso)], in ordine di nome."""
    folder = folder or VOICE_DIR
    try:
        names = os.listdir(folder)
    except OSError:
        return []
    voices = [(n[:-4], os.path.join(folder, n)) for n in names
              if n.lower().endswith(".wav") and not n.startswith(".")]
    return sorted(voices, key=lambda v: v[0].lower())


def _safe_name(name):
    """Nome di file sicuro: niente barre, niente punto iniziale, niente
    caratteri di controllo; al massimo 80 caratteri."""
    name = "".join(c if c.isprintable() and c not in '/\\:*?"<>|' else " " for c in name)
    name = " ".join(name.split()).strip(" .")
    return name[:80].strip(" .")


def save_voice(src, name, folder=None):
    """Copia una voce di prova fra le voci salvate e ne restituisce il
    percorso. Un nome gia' usato prende un numero: «Voce (2)». Non si
    sovrascrive mai una voce."""
    folder = folder or VOICE_DIR
    os.makedirs(folder, exist_ok=True)
    base = _safe_name(name) or "Voce"
    path, n = os.path.join(folder, base + ".wav"), 1
    while os.path.exists(path):
        n += 1
        path = os.path.join(folder, f"{base} ({n}).wav")
    tmp = path + ".part"
    shutil.copyfile(src, tmp)
    os.replace(tmp, path)
    return path


# ── schede grafiche ─────────────────────────────────────────────────────────
# Una riga di `llama-tts --list-devices` (come per RuscaLLama):
#   "  Vulkan1: NVIDIA GeForce RTX 3060 Laptop GPU (6144 MiB, 5794 MiB free)"
_DEVICE_RE = re.compile(r"^\s+(\S+):\s+(.*\S)\s+\((\d+) MiB, \d+ MiB free\)\s*$")


def list_devices():
    """Schede viste dal motore: [(nome, descrizione, MiB)]. Il motore
    inizializza Vulkan: va chiamata fuori dal thread dell'interfaccia."""
    binary = find_binary()
    if not binary:
        return []
    try:
        r = subprocess.run([binary, "--list-devices"], stdin=subprocess.DEVNULL,
                           capture_output=True, text=True, timeout=30)
    except (OSError, subprocess.SubprocessError):
        return []
    devices = []
    for line in (r.stdout + "\n" + r.stderr).splitlines():
        m = _DEVICE_RE.match(line)
        if m:
            devices.append((m.group(1), m.group(2), int(m.group(3))))
    return devices


def device_name(description, devices):
    """Nome di oggi (Vulkan0, Vulkan1...) della scheda salvata per
    descrizione, o None (scelta automatica, o scheda non piu' presente)."""
    for name, desc, _mib in devices:
        if description and desc == description:
            return name
    return None


# ── dal testo ai pezzi ──────────────────────────────────────────────────────
_SENTENCE_END = re.compile(r"(?<=[.!?…。！？])[\"'»”)\]]*\s+")
_CLAUSE_END = re.compile(r"(?<=[,;:，；：])\s+")
_FINAL = (".", "!", "?", "…", ":", ";", "。", "！", "？")


def _finish(text):
    """Un titolo o una voce di elenco senza punto finale si legge come una
    frase sospesa: il punto chiude l'intonazione."""
    text = text.strip()
    return text if not text or text.endswith(_FINAL) else text + "."


def split_text(text, limit=MAX_CHARS):
    """Divide un blocco in pezzi di al massimo `limit` caratteri, alle fine
    delle frasi; una frase troppo lunga si divide alle virgole e, se non
    basta, fra le parole. I pezzi corti vicini si riuniscono."""
    text = " ".join(text.split())
    if len(text) <= limit:
        return [text] if text else []
    parts = []
    for sentence in _SENTENCE_END.split(text):
        if len(sentence) <= limit:
            parts.append(sentence)
            continue
        for clause in _CLAUSE_END.split(sentence):
            while len(clause) > limit:
                cut = clause.rfind(" ", 0, limit)
                cut = cut if cut > limit // 3 else limit
                parts.append(clause[:cut])
                clause = clause[cut:].lstrip()
            parts.append(clause)
    pieces = []
    for part in (p.strip() for p in parts):
        if not part:
            continue
        if pieces and len(pieces[-1]) + 1 + len(part) <= limit:
            pieces[-1] += " " + part
        else:
            pieces.append(part)
    return pieces


def markdown_pieces(text, read_code=False, read_notes=False):
    """Pezzi da leggere di un documento Markdown, con la pausa dopo ognuno.
    L'analisi e' quella del motore comune (rusca_markdown.speech_blocks)."""
    pieces = []
    for kind, body in md.speech_blocks(text):
        if kind == "break":
            if pieces:
                last = pieces[-1]
                pieces[-1] = last._replace(pause=max(last.pause, PAUSES["break"]))
            continue
        if (kind == "code" and not read_code) or (kind == "note" and not read_notes):
            continue
        if kind == "code":
            body = " ".join(body.split())
        if kind in ("heading", "item", "table", "math"):
            body = _finish(body)
        chunks = split_text(body)
        for i, chunk in enumerate(chunks):
            last = i == len(chunks) - 1
            pieces.append(Piece(chunk, PAUSES.get(kind, 650) if last else PAUSE_INSIDE))
    return pieces


# Una riga di tempi SRT: "00:01:02,345 --> 00:01:04,000" (anche con il punto
# al posto della virgola, ore di una cifra e coordinate dopo i tempi).
_SRT_TIME = re.compile(r"(\d+):(\d{1,2}):(\d{1,2})[,.](\d{1,3})\s*-->\s*"
                       r"(\d+):(\d{1,2}):(\d{1,2})[,.](\d{1,3})")
_SRT_TAG = re.compile(r"<[^>]*>|\{\\[^}]*\}")
_SRT_SOUND = re.compile(r"\[[^\]]*\]|[♪♫]+")


def _srt_ms(h, m, s, frac):
    return ((int(h) * 60 + int(m)) * 60 + int(s)) * 1000 + int(frac.ljust(3, "0")[:3])


def parse_srt(text):
    """Sottotitoli SRT: [Piece(testo, 0, inizio, fine)] in ordine di tempo,
    tempi in millisecondi. Il testo e' su una riga, senza tag (<i>, {\\an8})
    e senza descrizioni di suoni fra parentesi quadre o note musicali, che
    nei sottotitoli per non udenti non si leggono. I trattini dei dialoghi
    restano, ma all'inizio della riga si tolgono."""
    text = text.replace("﻿", "").replace("\r\n", "\n").replace("\r", "\n")
    cues = []
    for block in re.split(r"\n\s*\n", text):
        lines = [line for line in block.split("\n") if line.strip()]
        for i, line in enumerate(lines):
            m = _SRT_TIME.search(line)
            if not m:
                continue
            g = m.groups()
            start, end = _srt_ms(*g[0:4]), _srt_ms(*g[4:8])
            words = []
            for raw in lines[i + 1:]:
                clean = _SRT_SOUND.sub(" ", _SRT_TAG.sub("", raw))
                clean = re.sub(r"^\s*[-–—]\s*", "", clean)
                if clean.strip():
                    words.append(clean.strip())
            spoken = " ".join(" ".join(words).split())
            if spoken and end >= start:
                cues.append(Piece(spoken, 0, start, end))
            break
    cues.sort(key=lambda c: (c.start, c.end))
    return cues


def preview_text(pieces, srt=False):
    """Il testo come lo mostra la finestra, e per ogni pezzo la sua
    posizione (inizio, fine) nel testo, per evidenziare quello in lettura."""
    out, spans, pos = [], [], 0
    for i, p in enumerate(pieces):
        prefix = ""
        if srt:
            s = p.start // 1000
            prefix = f"{s // 3600:02d}:{s // 60 % 60:02d}:{s % 60:02d}  "
        line = prefix + p.text
        start = pos + len(prefix)
        spans.append((start, start + len(p.text)))
        out.append(line)
        pos += len(line)
        if i < len(pieces) - 1:
            sep = "\n\n" if (srt or p.pause >= PAUSES["text"]) else "\n" if p.pause > PAUSE_INSIDE else " "
            out.append(sep)
            pos += len(sep)
    return "".join(out), spans


# ── audio ───────────────────────────────────────────────────────────────────
def wav_info(path):
    """(frequenza, canali, byte per campione, numero di campioni)."""
    with wave.open(path, "rb") as w:
        return w.getframerate(), w.getnchannels(), w.getsampwidth(), w.getnframes()


class _Timeline:
    """Scrive l'audio finale un pezzo dopo l'altro, senza tenerlo in
    memoria: WAV mono a 16 bit."""

    def __init__(self, path, rate):
        self.rate = rate
        self.w = wave.open(path, "wb")
        self.w.setnchannels(1)
        self.w.setsampwidth(2)
        self.w.setframerate(rate)
        self.frames = 0

    @property
    def ms(self):
        return self.frames * 1000 // self.rate

    def silence(self, ms):
        n = max(0, int(ms * self.rate / 1000))
        block = b"\0\0" * min(n, self.rate)
        while n > 0:
            k = min(n, self.rate)
            self.w.writeframes(block[:2 * k])
            self.frames += k
            n -= k

    def append(self, path):
        with wave.open(path, "rb") as r:
            while True:
                data = r.readframes(self.rate)
                if not data:
                    break
                self.w.writeframes(data)
                self.frames += len(data) // 2

    def close(self):
        self.w.close()


class Speaker:
    """Una lettura per volta. Le callback arrivano nel thread
    dell'interfaccia (GLib.idle_add):
        on_progress(index, total)   pezzo in lettura (da 0) e totale
        on_stage(stage)             "assemble" | "normalize"
        on_log(line)                righe dei programmi
        on_done(error, path, stats) error: None, "cancelled" o TTSError;
                                    path: WAV finale; stats per gli SRT:
                                    {"faster": n, "late": n, "max_late_ms": n}
    """

    def __init__(self, on_progress=None, on_stage=None, on_log=None, on_done=None):
        self.on_progress = on_progress or (lambda index, total: None)
        self.on_stage = on_stage or (lambda stage: None)
        self.on_log = on_log or (lambda line: None)
        self.on_done = on_done or (lambda error, path, stats: None)
        self._proc = None
        self._lock = threading.Lock()
        self._cancel = threading.Event()
        self._thread = None
        self.run_dir = None

    @property
    def running(self):
        return self._thread is not None and self._thread.is_alive()

    def start(self, pieces, voice, srt=False, language="it", speaker_file="", voice_name="",
              gpu=True, gpu_device="", threads=None, seed=42, max_speed=1.3, normalize=True,
              keep_dir="", reuse=None, min_speed=1.0):
        """Avvia la lettura in background e ritorna subito. gpu_device e' la
        descrizione di una scheda di list_devices(), o "" per la scelta del
        motore. keep_dir: cartella in cui copiare ogni pezzo detto, prima di
        accelerarlo o spostarlo («00000.wav»…); reuse: {indice: file} dei
        pezzi già detti da riusare invece di rigenerarli. Le durate dei
        pezzi (in ms, prima di accelerarli) arrivano in stats["durations"].
        min_speed < 1 (solo con srt): un pezzo molto più corto del suo
        sottotitolo si rallenta un poco, fino a min_speed, per riempirlo."""
        if self.running:
            return
        if not find_binary():
            raise TTSError("err_no_engine")
        if not find_ffmpeg():
            raise TTSError("err_no_ffmpeg")
        if not voice or not os.path.isfile(voice.model) or not os.path.isfile(voice.mmproj):
            raise TTSError("err_no_model")
        if speaker_file and not os.path.isfile(speaker_file):
            raise TTSError("err_speaker", speaker_file)
        if not pieces:
            raise TTSError("err_empty")
        self._cancel.clear()
        options = dict(srt=srt, language=language, speaker_file=speaker_file,
                       voice_name=voice_name, gpu=gpu, gpu_device=gpu_device,
                       threads=int(threads or physical_cores()), seed=int(seed),
                       max_speed=max(1.0, float(max_speed)), normalize=normalize,
                       keep_dir=keep_dir, reuse=dict(reuse or {}),
                       min_speed=min(1.0, max(0.5, float(min_speed))))
        self._thread = threading.Thread(target=self._work, args=(list(pieces), voice, options),
                                        daemon=True)
        self._thread.start()

    def cancel(self):
        self._cancel.set()
        with self._lock:
            proc = self._proc
        if proc is not None and proc.poll() is None:
            try:
                os.killpg(os.getpgid(proc.pid), signal.SIGTERM)
            except OSError:
                pass

    def wait(self, timeout=None):
        if self._thread is not None:
            self._thread.join(timeout)

    def discard(self):
        """Cancella i file di questa lettura (risultato compreso)."""
        if self.run_dir:
            shutil.rmtree(self.run_dir, ignore_errors=True)
            self.run_dir = None

    # ── lavoro (thread proprio) ───────────────────────────────────────────
    def _emit(self, callback, *args):
        GLib.idle_add(lambda: callback(*args) and False)

    def _run(self, cmd, env=None):
        self._emit(self.on_log, "$ " + " ".join(cmd))
        try:
            proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                    stdin=subprocess.DEVNULL, env=env, start_new_session=True)
        except OSError as e:
            raise TTSError("err_start", str(e)) from e
        with self._lock:
            self._proc = proc
        tail = collections.deque(maxlen=12)
        self._wrote = []                      # file che llama-tts dice di aver scritto
        try:
            for raw in iter(proc.stdout.readline, b""):
                line = raw.decode("utf-8", "replace").rstrip("\r\n")
                tail.append(line)
                self._emit(self.on_log, line)
                m = _WROTE.search(line)
                if m:
                    self._wrote.append(m.group(1).strip())
            code = proc.wait()
        finally:
            if proc.poll() is None:
                try:
                    os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
                except OSError:
                    pass
                proc.wait()
            proc.stdout.close()
            with self._lock:
                self._proc = None
        if self._cancel.is_set():
            raise _Cancelled()
        return code, "\n".join(t for t in tail if t.strip())

    def _ffmpeg(self, src, dst, filters, rate=None):
        cmd = [find_ffmpeg(), "-nostdin", "-hide_banner", "-loglevel", "error",
               "-protocol_whitelist", "file", "-i", src]
        if filters:
            cmd += ["-af", filters]
        cmd += ["-ac", "1"] + (["-ar", str(rate)] if rate else []) + \
               ["-c:a", "pcm_s16le", "-f", "wav", "-y", dst]
        code, tail = self._run(cmd)
        if code != 0 or not os.path.isfile(dst):
            raise TTSError("err_audio", tail)

    def _tts_command(self, text, out, voice, o, device):
        cmd = [find_binary(), "-m", voice.model, "-mm", voice.mmproj,
               "-p", prepare_text(text, voice.model),
               "-o", out, "-s", str(o["seed"]), "-t", str(max(1, o["threads"])),
               "-c", str(TTS_CONTEXT)]
        if o["language"]:
            cmd += ["--tts-lang", o["language"]]
        if o["speaker_file"]:
            cmd += ["--tts-speaker-file", o["speaker_file"]]
        if o["voice_name"]:
            cmd += ["--tts-voice", o["voice_name"]]
        env = os.environ.copy()
        if o["gpu"]:
            cmd += ["-ngl", "99"]
            if device:
                cmd += ["--device", device]
        else:
            # Senza scheda grafica i driver Vulkan si nascondono: alcuni si
            # bloccano anche senza lavorare.
            cmd += ["-ngl", "0", "--device", "none", "--no-mmproj-offload"]
            env["VK_DRIVER_FILES"] = "/dev/null"
            env["VK_ICD_FILENAMES"] = "/dev/null"
        return cmd, env

    def _work(self, pieces, voice, o):
        error, result, stats = None, None, {"faster": 0, "late": 0, "max_late_ms": 0}
        try:
            os.makedirs(WORK_DIR, mode=0o700, exist_ok=True)
            os.chmod(WORK_DIR, 0o700)
            self.run_dir = tempfile.mkdtemp(prefix="run-", dir=WORK_DIR)
            device = None
            if o["gpu"] and o["gpu_device"]:
                device = device_name(o["gpu_device"], list_devices())
                self._emit(self.on_log, f"ruscanarrator: scheda «{o['gpu_device']}» -> "
                                        f"{device or 'non trovata, scelta automatica'}")
            rate = None
            clips = []                     # (file pulito, durata in ms)
            for i, piece in enumerate(pieces):
                self._emit(self.on_progress, i, len(pieces))
                clean = os.path.join(self.run_dir, f"{i:05d}.wav")
                old = o["reuse"].get(i)
                if old and os.path.isfile(old):
                    # Pezzo già detto (per esempio in un passaggio precedente).
                    shutil.copyfile(old, clean)
                    info = wav_info(clean)
                    rate = rate or info[0]
                    clips.append((clean, info[3] * 1000 // info[0]))
                    kept = os.path.join(o["keep_dir"], f"{i:05d}.wav") if o["keep_dir"] else ""
                    if kept and os.path.abspath(kept) != os.path.abspath(old):
                        shutil.copyfile(clean, kept)
                    continue
                raw = os.path.join(self.run_dir, f"{i:05d}-tts.wav")
                cmd, env = self._tts_command(piece.text, raw, voice, o, device)
                code, tail = self._run(cmd, env)
                written = (raw in self._wrote and os.path.isfile(raw)
                           and os.path.getsize(raw) > 44)
                if code != 0 and written:
                    # L'audio è scritto e completo: l'errore è venuto dopo,
                    # alla chiusura (driver Vulkan NVIDIA: «double free or
                    # corruption» mentre il programma libera la scheda).
                    self._emit(self.on_log, "ruscanarrator: llama-tts ha scritto l'audio e poi "
                                            f"si è chiuso con un errore ({exit_description(code)}): "
                                            "l'audio è completo e si tiene")
                elif code != 0 or not os.path.isfile(raw) or os.path.getsize(raw) <= 44:
                    raise TTSError("err_engine", f"{exit_description(code)}\n{tail}".strip()
                                   if code != 0 else tail)
                if rate is None:
                    rate = wav_info(raw)[0]
                self._ffmpeg(raw, clean, TRIM_FILTER, rate)
                os.unlink(raw)
                info = wav_info(clean)
                clips.append((clean, info[3] * 1000 // rate))
                if o["keep_dir"]:
                    shutil.copyfile(clean, os.path.join(o["keep_dir"], f"{i:05d}.wav"))
            stats["durations"] = [ms for _clip, ms in clips]

            self._emit(self.on_stage, "assemble")
            joined = os.path.join(self.run_dir, "joined.wav")
            line = _Timeline(joined, rate)
            try:
                if o["srt"]:
                    self._place_srt(line, pieces, clips, rate, o["max_speed"], stats,
                                    o["min_speed"])
                else:
                    for piece, (clip, _ms) in zip(pieces, clips):
                        line.append(clip)
                        line.silence(piece.pause)
            finally:
                line.close()
            for clip, _ms in clips:
                try:
                    os.unlink(clip)
                except OSError:
                    pass
            result = os.path.join(self.run_dir, "audio.wav")
            if o["normalize"]:
                self._emit(self.on_stage, "normalize")
                self._ffmpeg(joined, result, LOUDNORM, rate)
                os.unlink(joined)
            else:
                os.replace(joined, result)
        except _Cancelled:
            error = "cancelled"
        except TTSError as e:
            error = "cancelled" if self._cancel.is_set() else e
        except (OSError, wave.Error, EOFError) as e:
            error = TTSError("err_engine", str(e))
        if error is not None:
            self.discard()
            result = None
        self._emit(self.on_done, error, result, stats)

    def _place_srt(self, line, cues, clips, rate, max_speed, stats, min_speed=1.0):
        """Ogni voce all'ora del suo sottotitolo. Lo spazio di una voce va
        fino all'inizio del sottotitolo dopo (o alla sua fine, per
        l'ultimo): se non basta si accelera fino a max_speed, poi si
        sposta in avanti. Una voce molto più corta del suo sottotitolo si
        rallenta, al massimo fino a min_speed. Il risultato dura almeno
        fino alla fine dell'ultimo sottotitolo."""
        for i, (cue, (clip, ms)) in enumerate(zip(cues, clips)):
            if self._cancel.is_set():
                raise _Cancelled()
            limit = cues[i + 1].start if i + 1 < len(cues) else max(cue.end, cue.start + ms)
            slot = max(1, limit - cue.start)
            if ms > slot:
                speed = min(max_speed, ms / slot)
                if speed > 1.005:
                    fast = clip[:-4] + "-fast.wav"
                    self._ffmpeg(clip, fast, _atempo(speed), rate)
                    os.replace(fast, clip)
                    ms = wav_info(clip)[3] * 1000 // rate
                    stats["faster"] += 1
            elif min_speed < 1.0:
                # Più corta del sottotitolo (e c'è posto): un poco più lenta,
                # così finisce più vicino a dove finisce l'originale.
                target = min(slot, cue.end - cue.start)
                speed = max(min_speed, ms / max(1, target))
                if speed < 0.97:
                    slow = clip[:-4] + "-slow.wav"
                    self._ffmpeg(clip, slow, _atempo(speed), rate)
                    os.replace(slow, clip)
                    ms = wav_info(clip)[3] * 1000 // rate
                    stats["slower"] = stats.get("slower", 0) + 1
            start = max(cue.start, line.ms)
            late = start - cue.start
            if late > 40:                       # meno di due fotogrammi non conta
                stats["late"] += 1
                stats["max_late_ms"] = max(stats["max_late_ms"], late)
            line.silence(start - line.ms)
            line.append(clip)
        if cues and line.ms < cues[-1].end:
            line.silence(cues[-1].end - line.ms)


# Contesto di llama-tts. Senza -c llama.cpp usa quello di addestramento del
# modello (per Qwen3-TTS decine di migliaia di posizioni), e la cache occupa
# gigabyte della scheda: su una RTX 3060 Laptop da 6 GB la voce non partiva
# (ErrorOutOfDeviceMemory). Un pezzo (al massimo MAX_CHARS caratteri, circa
# mezzo minuto) sta in meno di mille posizioni fra testo e audio.
TTS_CONTEXT = 4096

_WROTE = re.compile(r"\bwrote (/.+?)\s*$")


def exit_description(code):
    """Il codice di uscita di un programma, a parole: "codice 1", o il
    segnale che l'ha fermato ("segnale 6, SIGABRT")."""
    if code is not None and code < 0:
        try:
            return f"segnale {-code}, {signal.Signals(-code).name}"
        except ValueError:
            return f"segnale {-code}"
    return f"codice {code}"


def _atempo(speed):
    """Filtro atempo di FFmpeg: cambia la velocita' senza cambiare il tono.
    Oltre 2x si concatenano piu' filtri."""
    filters = []
    while speed > 2.0:
        filters.append("atempo=2.0")
        speed /= 2.0
    filters.append(f"atempo={speed:.4f}")
    return ",".join(filters)


def export(src, dst, fmt):
    """Salva il WAV finale nel formato scelto (wav, flac, opus, mp3). Da un
    thread: la conversione di un'ora di audio richiede qualche secondo."""
    if fmt not in EXPORT_FORMATS:
        raise TTSError("save_error", fmt)
    if fmt == "wav":
        shutil.copyfile(src, dst)
        return
    ffmpeg = find_ffmpeg()
    if not ffmpeg:
        raise TTSError("err_no_ffmpeg")
    tmp = dst + ".part"
    cmd = [ffmpeg, "-nostdin", "-hide_banner", "-loglevel", "error",
           "-protocol_whitelist", "file", "-i", src] + EXPORT_FORMATS[fmt] + \
          ["-f", {"opus": "ogg", "mp3": "mp3", "flac": "flac"}[fmt], "-y", tmp]
    r = subprocess.run(cmd, stdin=subprocess.DEVNULL, capture_output=True, text=True)
    if r.returncode != 0 or not os.path.isfile(tmp):
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise TTSError("save_error", r.stderr.strip()[-500:])
    os.replace(tmp, dst)


class _Cancelled(Exception):
    pass
