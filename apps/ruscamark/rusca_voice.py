# -*- coding: utf-8 -*-
# rusca_voice.py — RuscaMark 1.99.3 — GPL-3.0-or-later
#
# La voce di RuscaMark, con i motori delle RuscaLinux OS Apps:
#   * dettatura: il microfono (pw-record, PipeWire) scrive nel documento,
#     con Vosk (ruscavosk-engine, parola per parola mentre si parla) o con
#     Whisper (ruscawhisper-engine, una frase per volta dopo ogni pausa, più
#     preciso e con la punteggiatura);
#   * trascrizione di un file audio o video in un documento Markdown, con
#     uno dei due motori;
#   * lettura ad alta voce del documento con Piper (ruscapiper-engine).
#
# I moduli comuni (rusca_vosk.py, rusca_whisper.py, rusca_piper.py,
# speech_text.py) sono copie identiche di quelli di RuscaLLisse e
# RuscaTranscriber: qui si usano, non si cambiano.
#
# Privacy (specifiche, sezione 11): nessun modulo di rete, nessuna porta.
# Con Vosk l'audio del microfono passa solo in memoria. Whisper legge un
# file: ogni frase dettata diventa un WAV in una cartella privata (0700)
# della memoria di sessione ($XDG_RUNTIME_DIR, di solito in RAM), cancellato
# appena letto; la trascrizione di un file usa la cartella di lavoro di
# rusca_whisper.py, qui spostata in ~/.cache/ruscamark/trascrizione e
# svuotata alla fine.
import array
import collections
import math
import os
import queue
import re
import shutil
import signal
import subprocess
import sys
import tempfile
import threading
import time
import wave

from gi.repository import GLib

import rusca_markdown as md
import rusca_piper as piper
import rusca_vosk as vosk
import rusca_whisper as whisper
import speech_text as st

PW_RECORD = "/usr/bin/pw-record"
RATE = 16000
FRAME = 640                          # 20 ms a 16 kHz, 16 bit, mono
VOSK_BLOCK = 5                       # Vosk riceve l'audio a blocchi di 100 ms
PARTIAL_EVERY = 2                    # testo parziale ogni 2 blocchi (200 ms d'audio)
# Vosk: la frase finisce quando il testo parziale non cambia per tanto
# audio (con un po' di rumore di fondo Vosk non la chiude da solo, sezione
# 1.7.3). Si conta l'audio e non l'orologio: se Vosk resta indietro rispetto
# al parlato, una frase non si chiude mentre si sta ancora parlando.
VOSK_PAUSE = 1.0
# Dopo «Ferma» il microfono resta aperto ancora un poco: l'ultima parola
# detta arriva da PipeWire con un piccolo ritardo.
STOP_GRACE = 0.4
# Il testo parziale di Vosk costa tanto più quanto è lunga la frase in corso:
# si chiede solo se il riconoscimento è al passo con il parlato (meno di
# tanto audio in coda). Se resta indietro recupera prima, e il testo arriva.
PARTIAL_MAX_BACKLOG = 0.3
# Oltre questo ritardo la barra della voce lo mostra.
SHOW_BACKLOG = 1.0
# RUSCAMARK_VOICE_DEBUG=1: sul terminale, per ogni frase, audio, ritardo e
# tempi; =2 anche il testo riconosciuto. Mai nella finestra né su disco.
DEBUG = int(os.environ.get("RUSCAMARK_VOICE_DEBUG", "0") or 0)


def _log(*args):
    if DEBUG:
        print("ruscamark voce:", *args, file=sys.stderr, flush=True)
# Whisper: una frase è il parlato fra due silenzi di almeno WHISPER_PAUSE.
WHISPER_PAUSE = 0.7
WHISPER_PREROLL = 0.3                # s di audio tenuti prima della voce
WHISPER_MIN_SPEECH = 0.35            # più corto: un rumore, si scarta
WHISPER_MAX = 25.0                   # Whisper lavora su finestre di 30 s
PROMPT_CHARS = 200                   # testo già dettato passato a --prompt

# Cartelle di lavoro: niente audio nelle cartelle degli altri programmi.
LIVE_DIR = os.path.join(GLib.get_user_runtime_dir() or GLib.get_user_cache_dir(),
                        "ruscamark")
whisper.WORK_DIR = os.path.join(GLib.get_user_cache_dir(), "ruscamark", "trascrizione")

ENGINES = ("vosk", "whisper")
# Lingue del parlato: quelle delle RuscaLinux OS Apps con i codici di Whisper
# (un solo cinese e un solo portoghese), sezione 9.
SPEECH_LANGUAGES = ("en", "it", "zh", "es", "hi", "ar", "pt", "ru", "ja", "de", "fr",
                    "ko", "id", "tr", "pl", "nl", "uk", "cs", "vi", "sv", "ro", "hu",
                    "el", "fi")


class VoiceError(Exception):
    """Errore per l'utente: `key` è una chiave di lang/."""

    def __init__(self, key, detail=""):
        super().__init__(f"{key}: {detail}" if detail else key)
        self.key = key
        self.detail = detail


# Le chiavi d'errore di rusca_whisper.py con i nomi di RuscaMark.
_WHISPER_KEYS = {"err_no_engine": "err_no_whisper", "err_no_model": "err_no_whisper_model",
                 "err_start": "err_whisper_start", "err_engine": "err_whisper",
                 "open_error": "err_audio", "err_audio": "err_audio",
                 "err_no_ffmpeg": "err_no_ffmpeg"}


def _from_whisper(error):
    return VoiceError(_WHISPER_KEYS.get(error.key, "err_whisper"), error.detail)


# ── che cosa c'è sul computer ──────────────────────────────────────────────
def mic_available():
    return os.access(PW_RECORD, os.X_OK)


def status():
    """Motori e modelli presenti (per le Preferenze e i messaggi)."""
    return {
        "mic": mic_available(),
        "vosk": bool(vosk.find_library()),
        "vosk_models": vosk.find_models(),
        "whisper": bool(whisper.find_binary()),
        "whisper_models": whisper.find_models(),
        "ffmpeg": bool(whisper.find_ffmpeg()),
        "piper": piper.available(),
        "voices": piper.find_voices(),
    }


def clean_work_dirs():
    """Cancella l'audio rimasto da una dettatura o da una trascrizione
    interrotte (all'avvio di RuscaMark)."""
    whisper.clean_work_dir()
    try:
        for name in os.listdir(LIVE_DIR):
            path = os.path.join(LIVE_DIR, name)
            if os.path.isdir(path) and not os.path.islink(path):
                shutil.rmtree(path, ignore_errors=True)
    except OSError:
        pass


def model_label(path):
    """Il nome breve di un modello: la cartella di Vosk o il file di Whisper
    senza «.bin»."""
    name = os.path.basename(path.rstrip("/"))
    return name[:-4] if name.lower().endswith(".bin") else name


def base_language(code):
    """«it_IT», «pt-BR», «zh_CN» → «it», «pt», «zh»."""
    return (code or "").replace("-", "_").split("_")[0].lower()


def pick_vosk_model(models, saved="", lang=""):
    """Il modello salvato, se c'è ancora; altrimenti il più grande della
    lingua; altrimenti il più grande (find_models() li dà dal più grande)."""
    if saved and saved in models:
        return saved
    for m in models:
        if lang and vosk.model_language(m) == lang:
            return m
    return models[0] if models else ""


def pick_whisper_model(models, saved=""):
    if saved and saved in models:
        return saved
    return models[0] if models else ""


def voice_language(path):
    return base_language(piper.voice_info(path).get("lang", ""))


def pick_voice(voices, saved="", lang=""):
    if saved and saved in voices:
        return saved
    for v in voices:
        if lang and voice_language(v) == lang:
            return v
    return voices[0] if voices else ""


# ── dal parlato al testo ───────────────────────────────────────────────────
# Comandi a voce. Si riconoscono come parole intere, senza maiuscole e senza
# la punteggiatura che Whisper aggiunge; i più lunghi prima («punto e
# virgola» prima di «punto»).
#   punct  – i segni: solo con Vosk, che scrive le parole e non i segni;
#   lines  – a capo e nuovo paragrafo;
#   blocks – Markdown di riga (titoli, elenchi, citazione): valgono solo
#            all'inizio di una frase o dopo un a capo, così «il titolo del
#            libro» detto in mezzo a una frase resta testo;
#   inline – grassetto e corsivo, con un comando per aprire e uno per
#            chiudere (due parole, rare nel parlato).
COMMANDS = {
    "it": {
        "punct": (("punto interrogativo", "?"), ("punto esclamativo", "!"),
                  ("punto e virgola", ";"), ("due punti", ":"), ("virgola", ","),
                  ("punto", "."), ("apri parentesi", "("), ("chiudi parentesi", ")"),
                  ("apri virgolette", "«"), ("chiudi virgolette", "»")),
        "lines": (("nuovo paragrafo", "\n\n"), ("a capo", "\n"), ("accapo", "\n")),
        "blocks": (("titolo uno", "# "), ("titolo due", "## "), ("titolo tre", "### "),
                   ("titolo", "# "), ("sottotitolo", "## "), ("elenco numerato", "1. "),
                   ("elenco", "- "), ("citazione", "> ")),
        "inline": (("inizio grassetto", "**", "open"), ("fine grassetto", "**", "close"),
                   ("inizio corsivo", "*", "open"), ("fine corsivo", "*", "close")),
    },
    "en": {
        "punct": (("question mark", "?"), ("exclamation mark", "!"),
                  ("exclamation point", "!"), ("semicolon", ";"), ("colon", ":"),
                  ("comma", ","), ("full stop", "."), ("period", "."),
                  ("open parenthesis", "("), ("close parenthesis", ")"),
                  ("open quote", "“"), ("close quote", "”")),
        "lines": (("new paragraph", "\n\n"), ("new line", "\n")),
        "blocks": (("heading one", "# "), ("heading two", "## "), ("heading three", "### "),
                   ("heading", "# "), ("subheading", "## "), ("numbered list", "1. "),
                   ("bullet", "- "), ("quote", "> ")),
        "inline": (("start bold", "**", "open"), ("end bold", "**", "close"),
                   ("start italic", "*", "open"), ("end italic", "*", "close")),
    },
}
_ATTACH_LEFT = set(".,;:?!)»”")          # senza spazio prima
_ATTACH_RIGHT = set("(«“")               # senza spazio dopo
_SENTENCE_END = (".", "?", "!", "…")
_STRIP = ".,;:!?…«»“”\"'()"
_BLOCK_LINE = re.compile(r"^(?:#{1,6} |[-*+] |\d{1,9}\. |> )")
_NUMBERED = re.compile(r"^(\d{1,9})\. ")


def command_language(lang):
    """La lingua dei comandi: italiano o inglese (per le altre lingue i
    comandi si dicono in inglese)."""
    return lang if lang in COMMANDS else "en"


def parse_commands(text, lang, punctuation=True, markdown=True):
    """Il parlato riconosciuto come elenco di (tipo, valore): "word" (una
    parola), "punct" (un segno), "nl" (a capo o paragrafo), "block" (il
    marcatore di una riga Markdown), "open" e "close" (grassetto, corsivo).
    Senza tabella dei comandi per la lingua, solo parole."""
    words = text.split()
    table = COMMANDS.get(lang)
    if not table or not (punctuation or markdown):
        return [("word", w) for w in words]
    groups = []
    if markdown:
        groups += [("lines", "nl"), ("blocks", "block"), ("inline", None)]
    if punctuation:
        groups.append(("punct", "punct"))
    norm = [w.strip(_STRIP).lower() for w in words]
    out, i, line_start = [], 0, True
    while i < len(words):
        found = None
        for group, kind in groups:
            if group == "blocks" and not line_start:
                continue
            for entry in table[group]:
                phrase = entry[0].split()
                if norm[i:i + len(phrase)] == phrase:
                    found = (entry[2] if kind is None else kind, entry[1], len(phrase))
                    break
            if found:
                break
        if found:
            out.append(found[:2])
            i += found[2]
            line_start = found[0] == "nl"
        else:
            out.append(("word", words[i]))
            i += 1
            line_start = False
    return out


def apply_commands(text, lang):
    """Compatibilità: i pezzi come testo (parole e segni)."""
    return [v for _k, v in parse_commands(text, lang)]


def _capitalize(word):
    return word[:1].upper() + word[1:] if word else word


def _escape_word(word, line_start):
    """Il parlato è testo e non Markdown (escape_markdown() di
    rusca_whisper.py, come nelle trascrizioni). La regola dell'inizio di
    riga («1.», «#», «-») vale solo per la prima parola di una riga."""
    if line_start:
        return whisper.escape_markdown(word)
    return whisper.escape_markdown("a " + word)[2:]


def render_dictation(items, before, escape=True):
    """Gli elementi di parse_commands() come testo da inserire dopo `before`
    (il testo che precede il cursore): spazi, maiuscole a inizio frase e
    di riga, marcatori Markdown su una riga propria. Un titolo occupa la
    sua frase: dopo, si va a un paragrafo nuovo."""
    out = ""
    heading = False

    def cur():
        return before + out

    def line_of(text):
        return text[text.rfind("\n") + 1:]

    def previous_line(text):
        lines = text.split("\n")
        return lines[-2] if len(lines) >= 2 else ""

    for kind, value in items:
        text = cur()
        if kind == "nl":
            out = out.rstrip(" ") + value
            if (before + out).endswith("\n\n\n"):
                out = out.rstrip("\n") + "\n\n"
            heading = False
        elif kind == "block":
            if line_of(text).strip():
                out = out.rstrip(" ") + "\n"
            if value == "1. ":
                m = _NUMBERED.match(previous_line(cur() if cur().endswith("\n") else cur() + "\n"))
                if m and not line_of(cur()).strip():
                    value = f"{int(m.group(1)) + 1}. "
            if value.startswith("#"):
                prev = previous_line(cur()) if cur().endswith("\n") else ""
                if prev.strip():
                    out += "\n"                      # una riga vuota prima del titolo
                heading = True
            out = out[:len(out) - len(line_of(cur()))] + value if not line_of(cur()).strip() \
                else out + value
        elif kind == "punct":
            if value in _ATTACH_RIGHT:
                sep = "" if not text or text[-1] in " \n\t" or text[-1] in _ATTACH_RIGHT else " "
                out += sep + value
            else:
                out = out.rstrip(" ") + value
        elif kind == "open":
            sep = "" if not text or text[-1] in " \n\t" or text[-1] in _ATTACH_RIGHT else " "
            out += sep + value
        elif kind == "close":
            out = out.rstrip(" ") + value
        else:
            line = line_of(text)
            at_line_start = not line.strip()
            # Testo normale dopo un elenco o una citazione: riga vuota, se
            # no il Markdown lo attacca all'ultima voce.
            if at_line_start and text.endswith("\n") and _BLOCK_LINE.match(previous_line(text)) \
                    and not previous_line(text).startswith("#"):
                out += "\n"
                text = cur()
            # Inizio di frase: testo vuoto, a capo, fine frase, o solo il
            # marcatore di una riga Markdown (anche con un grassetto aperto).
            bare = re.sub(r"\*+$", "", text.rstrip(" "))
            marker_only = re.fullmatch(r"\s*(?:#{1,6}|[-*+]|\d{1,9}\.|>)?\s*\**",
                                       line_of(text))
            starts = (not bare.strip() or bare.endswith("\n") or bare.endswith(_SENTENCE_END)
                      or bool(marker_only))
            word = _capitalize(value) if starts and value[:1].isalpha() else value
            if escape:
                word = _escape_word(word, at_line_start and not _BLOCK_LINE.match(line))
            sep = "" if not text or text[-1] in " \n\t" or text[-1] in _ATTACH_RIGHT \
                or text.endswith("*") and kind_before_open(text) else " "
            out += sep + word
    if heading:
        out = out.rstrip(" ")
        if out.endswith(".") and not out.endswith(".."):
            out = out[:-1]                            # niente punto in fondo a un titolo
        out += "\n\n"
    return out


def kind_before_open(text):
    """Il testo finisce con un marcatore di grassetto o corsivo appena
    aperto (preceduto da uno spazio o da un inizio di riga)?"""
    return bool(re.search(r"(^|[\s(«“])\*{1,2}$", text))


def join_dictation(pieces, before):
    """Compatibilità: parole e segni già separati (senza comandi Markdown)."""
    items = [("punct" if p in _ATTACH_LEFT or p in _ATTACH_RIGHT else
              "nl" if p in ("\n", "\n\n") else "word", p) for p in pieces]
    return render_dictation(items, before, escape=False)


def dictation_text(text, before, lang="", commands=True, escape=True, markdown=None):
    """Il testo riconosciuto, pronto da inserire nel documento dopo `before`.
    commands: i comandi di punteggiatura (Vosk); markdown: i comandi di riga
    e di formattazione (se non indicato, come commands). Il parlato è testo
    e non Markdown: le parole si proteggono, i comandi scrivono i marcatori."""
    if markdown is None:
        markdown = commands
    items = parse_commands(text, lang, punctuation=commands, markdown=markdown)
    return render_dictation(items, before, escape=escape)


def command_help(lang):
    """I comandi della lingua, per l'aiuto della barra della voce:
    [(gruppo, [(parole, segno da mostrare)])]."""
    table = COMMANDS[command_language(lang)]
    shown = {"\n": "↵", "\n\n": "¶"}
    return [(group, [(entry[0], shown.get(entry[1], entry[1].strip() or entry[1]))
                     for entry in table[group]])
            for group in ("punct", "lines", "blocks", "inline")]


def longer(final, partial):
    """Il testo della frase: quello finale di Vosk, se non ha perso parole
    rispetto al parziale. Con il modello grande il risultato chiesto a metà
    può arrivare vuoto o più corto (il rescoring di fine frase), mentre il
    parziale è la frase intera (sezione 1.7.3)."""
    final, partial = (final or "").strip(), (partial or "").strip()
    return final if len(final.split()) >= len(partial.split()) else partial


def _rms(data):
    a = array.array("h")
    a.frombytes(data[: len(data) // 2 * 2])
    if not a:
        return 0.0
    return math.sqrt(sum(s * s for s in a) / len(a)) / 32768.0


def write_wav(path, pcm, rate=RATE):
    with wave.open(path, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(pcm)


def whisper_command(model, wav, prefix, language, threads, gpu, gpu_device="",
                    prompt="", devices=None):
    """Comando e ambiente di whisper-cli per un WAV, con le stesse regole di
    rusca_whisper.py: niente simboli non verbali (-sns), VAD se c'è il
    modello Silero, processore con i driver Vulkan nascosti o la scheda
    scelta (GGML_VK_VISIBLE_DEVICES)."""
    cmd = [whisper.find_binary(), "-m", model, "-f", wav, "-l", language or "auto",
           "-t", str(max(1, int(threads or whisper.physical_cores()))),
           "-oj", "-of", prefix, "-sns"]
    vad = whisper.find_vad_model()
    if vad:
        cmd += ["--vad", "-vm", vad]
    if prompt.strip():
        cmd += ["--prompt", " ".join(prompt.split())[-PROMPT_CHARS:]]
    env = os.environ.copy()
    if not gpu:
        cmd.append("-ng")
        env["VK_DRIVER_FILES"] = "/dev/null"
        env["VK_ICD_FILENAMES"] = "/dev/null"
    elif gpu_device:
        index = whisper.device_index(gpu_device, whisper.list_devices()
                                     if devices is None else devices)
        if index is not None:
            env["GGML_VK_VISIBLE_DEVICES"] = str(index)
    return cmd, env


# ── dettatura ──────────────────────────────────────────────────────────────
class Dictation:
    """Dal microfono al testo, in un thread di lavoro. Le callback arrivano
    sempre nel thread dell'interfaccia:
        on_state(stato)      "loading" | "listening" | "writing" | "stopped"
        on_partial(testo)    la frase in corso (Vosk), "" quando finisce
        on_text(testo)       una frase finita, da inserire
        on_level(livello)    livello del microfono, da 0 a 1
        on_error(VoiceError)
    Con Vosk il modello resta caricato fra una dettatura e l'altra
    (recognizer); si libera con close()."""

    def __init__(self, on_state=None, on_partial=None, on_text=None, on_level=None,
                 on_error=None, on_delay=None):
        self.on_state = on_state or (lambda s: None)
        self.on_partial = on_partial or (lambda t: None)
        self.on_text = on_text or (lambda t: None)
        self.on_level = on_level or (lambda x: None)
        self.on_error = on_error or (lambda e: None)
        self.on_delay = on_delay or (lambda seconds: None)   # audio in coda, in secondi
        self._stop = threading.Event()
        self._pause = threading.Event()
        self._resume = threading.Event()
        self._queue = None
        self._thread = None
        self._mic = None
        self._mic_lock = threading.Lock()
        self._rec = None                 # (percorso del modello, vosk.Recognizer)
        self._proc = None                # whisper-cli in corso
        self.engine = ""
        self._cancelled = False
        self.prompt = ""                 # testo prima del cursore (Whisper --prompt)

    @property
    def running(self):
        return self._thread is not None and self._thread.is_alive()

    def start(self, engine, options):
        """options: vosk_model | whisper_model, language, gpu, gpu_device,
        threads. Ritorna subito; gli errori arrivano con on_error."""
        if self.running:
            return
        if not mic_available():
            raise VoiceError("err_no_mic", PW_RECORD)
        if engine == "vosk":
            if not vosk.find_library():
                raise VoiceError("err_no_vosk")
            if not options.get("vosk_model"):
                raise VoiceError("err_no_vosk_model")
        else:
            if not whisper.find_binary():
                raise VoiceError("err_no_whisper")
            if not options.get("whisper_model") or not os.path.isfile(options["whisper_model"]):
                raise VoiceError("err_no_whisper_model")
        self.engine = engine
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, args=(engine, dict(options)),
                                        daemon=True)
        self._thread.start()

    def stop(self):
        """Smette di ascoltare. Tutto l'audio già registrato si riconosce
        ancora (l'ultima frase non si perde), e con Whisper si scrivono le
        frasi in coda; poi arriva "stopped"."""
        self._stop.set()
        self._resume.set()                       # se era in pausa, esce
        timer = threading.Timer(STOP_GRACE, self._stop_mic)
        timer.daemon = True
        timer.start()

    @property
    def paused(self):
        return self._pause.is_set()

    def pause(self):
        """Chiude il microfono senza fermare la dettatura: la frase in corso
        si finisce di riconoscere e si scrive, il modello resta caricato."""
        if self.running and not self._pause.is_set():
            self._resume.clear()
            self._pause.set()
            timer = threading.Timer(STOP_GRACE, self._stop_mic)
            timer.daemon = True
            timer.start()

    def resume(self):
        """Riapre il microfono dopo pause()."""
        if self._pause.is_set():
            self._pause.clear()
            self._resume.set()

    def backlog(self):
        """Secondi d'audio registrati e non ancora riconosciuti."""
        q = self._queue
        return q.qsize() * FRAME / (RATE * 2) if q is not None else 0.0

    def cancel(self):
        """Smette subito, senza scrivere ciò che resta (chiusura)."""
        self._stop.set()
        self._cancelled = True
        self._resume.set()
        self._stop_mic()
        proc = self._proc
        if proc is not None and proc.poll() is None:
            try:
                os.killpg(os.getpgid(proc.pid), signal.SIGTERM)
            except OSError:
                pass

    def borrow_recognizer(self, path):
        """Il modello di Vosk già caricato, se è quello e la dettatura è
        ferma: la trascrizione di un file lo usa senza caricarlo di nuovo."""
        if not self.running and self._rec is not None and self._rec[0] == path:
            return self._rec[1]
        return None

    def close(self, timeout=5.0):
        """Ferma tutto e libera il modello di Vosk, ma solo dopo che il
        thread si è fermato: liberarlo mentre è in uso fa cadere Vosk."""
        self.cancel()
        if self._thread is not None:
            self._thread.join(timeout)
            if self._thread.is_alive():
                return False
        if self._rec is not None:
            self._rec[1].close()
            self._rec = None
        return True

    # ── interni ──────────────────────────────────────────────────────────
    def _emit(self, fn, *args):
        GLib.idle_add(lambda: fn(*args) and False)

    def _start_mic(self):
        with self._mic_lock:
            self._mic = subprocess.Popen(
                [PW_RECORD, *piper.pw_raw_args(PW_RECORD), "--rate", str(RATE),
                 "--channels", "1", "--format", "s16", "-"],
                stdout=subprocess.PIPE, stdin=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL)
            return self._mic

    def _stop_mic(self):
        with self._mic_lock:
            mic, self._mic = self._mic, None
        if mic is not None:
            try:
                mic.terminate()
                mic.wait(timeout=2)
            except (OSError, subprocess.TimeoutExpired):
                try:
                    mic.kill()
                except OSError:
                    pass

    def _run(self, engine, options):
        self._cancelled = False
        self._pause.clear()
        try:
            if engine == "vosk":
                self._run_vosk(options)
            else:
                self._run_whisper(options)
        except VoiceError as e:
            self._emit(self.on_error, e)
        except Exception as e:                      # noqa: BLE001
            self._emit(self.on_error, VoiceError("err_voice_internal",
                                                 f"{type(e).__name__}: {e}"))
        finally:
            self._stop_mic()
            self._emit(self.on_partial, "")
            self._emit(self.on_state, "stopped")

    def _frames(self, per=1):
        """L'audio del microfono a blocchi di per × 20 ms, finché non si
        ferma. Il microfono si legge in un thread a parte che mette tutto in
        coda: se il riconoscimento resta indietro rispetto al parlato
        recupera dopo, e PipeWire non deve mai scartare l'audio perché il
        tubo è pieno. Dopo lo stop si consuma l'audio rimasto nel tubo.
        In pausa il microfono è chiuso: si restituisce un blocco vuoto (b"")
        perché chi riconosce finisca la frase in corso, poi si aspetta."""
        while True:
            mic = self._start_mic()
            frames = queue.Queue()
            self._queue = frames

            def read(mic=mic, frames=frames):
                n = 0
                try:
                    while True:
                        data = mic.stdout.read(FRAME)
                        if not data:
                            break
                        n += 1
                        if n % 3 == 0:
                            self._emit(self.on_level, min(1.0, _rms(data) * 6.0))
                        frames.put(data)
                except (OSError, ValueError):
                    pass
                finally:
                    frames.put(None)
            threading.Thread(target=read, daemon=True).start()
            block, last_delay = [], 0.0
            while True:
                data = frames.get()
                if data is None:
                    break
                if self._cancelled:
                    continue                    # chiusura: si svuota senza riconoscere
                block.append(data)
                if len(block) >= per:
                    yield b"".join(block)
                    block = []
                    now = time.monotonic()
                    if now - last_delay >= 0.5:
                        last_delay = now
                        self._emit(self.on_delay, self.backlog())
            if block and not self._cancelled:
                yield b"".join(block)
            self._queue = None
            self._emit(self.on_delay, 0.0)
            if self._stop.is_set() or self._cancelled:
                return
            if not self._pause.is_set():
                raise VoiceError("err_mic", f"pw-record: {mic.poll()}")
            yield b""                           # pausa: finire la frase in corso
            self._emit(self.on_level, 0.0)
            self._emit(self.on_state, "paused")
            self._resume.wait()
            if self._stop.is_set() or self._cancelled:
                return
            self._emit(self.on_state, "listening")

    # Vosk: parola per parola mentre si parla.
    def _run_vosk(self, options):
        path = options["vosk_model"]
        if self._rec is None or self._rec[0] != path:
            self._emit(self.on_state, "loading")
            if self._rec is not None:
                self._rec[1].close()
                self._rec = None
            try:
                self._rec = (path, vosk.Recognizer(path))
            except vosk.VoskError as e:
                raise VoiceError(e.key, e.detail) from e
        rec = self._rec[1]
        rec.reset()
        self._emit(self.on_state, "listening")
        partial, quiet, count, heard = "", 0.0, 0, 0.0
        for data in self._frames(VOSK_BLOCK):
            if not data:                                 # pausa
                self._vosk_final(rec, partial, heard)
                partial, quiet, heard = "", 0.0, 0.0
                continue
            seconds = len(data) / (RATE * 2)
            heard += seconds
            if rec.accept(data):
                text = rec.result().get("text", "")
                _log(f"frase chiusa da Vosk: {heard:.1f} s d'audio, ritardo {self.backlog():.1f} s",
                     f"«{text}»" if DEBUG > 1 else "")
                self._final(text)
                partial, quiet, heard = "", 0.0, 0.0
                continue
            quiet += seconds
            count += 1
            if count % PARTIAL_EVERY:
                continue
            if self.backlog() > PARTIAL_MAX_BACKLOG:
                # In ritardo: niente testo parziale, che è la parte costosa;
                # la pausa si misura sul parziale, quindi aspetta anche lei.
                continue
            text = rec.partial()
            if text != partial:
                partial, quiet = text, 0.0
                self._emit(self.on_partial, text)
            elif partial and quiet >= VOSK_PAUSE:
                self._vosk_final(rec, partial, heard)
                partial, quiet, heard = "", 0.0, 0.0
        if not self._cancelled:
            self._vosk_final(rec, partial, heard)

    def _vosk_final(self, rec, partial, heard):
        start = time.monotonic()
        final = rec.final_result().get("text", "")
        text = longer(final, partial)
        _log(f"frase: {heard:.1f} s d'audio, risultato in {time.monotonic() - start:.2f} s, "
             f"ritardo {self.backlog():.1f} s, parole finale/parziale "
             f"{len(final.split())}/{len(partial.split())}",
             f"«{text}»" if DEBUG > 1 else "")
        self._final(text)

    def _final(self, text):
        text = " ".join((text or "").split())
        self._emit(self.on_partial, "")
        if text and text.lower() not in ("eh", "ehm", "mh", "mhm", "ah", "oh", "uh", "hm"):
            self._emit(self.on_text, text)

    # Whisper: una frase alla volta, dopo ogni pausa.
    def _run_whisper(self, options):
        os.makedirs(LIVE_DIR, mode=0o700, exist_ok=True)
        os.chmod(LIVE_DIR, 0o700)
        devices = whisper.list_devices() if options.get("gpu") and options.get("gpu_device") else []
        jobs = queue.Queue()
        worker = threading.Thread(target=self._whisper_worker, args=(jobs, options, devices),
                                  daemon=True)
        worker.start()
        self._emit(self.on_state, "listening")
        try:
            self._listen_whisper(jobs)
        finally:
            # Anche se il microfono si ferma con un errore, il lavoratore
            # finisce le frasi in coda ed esce.
            jobs.put(None)
            worker.join()

    def _listen_whisper(self, jobs):
        cutter = SpeechCutter()
        for data in self._frames():
            segment = cutter.flush() if not data else cutter.feed(data)
            if segment:
                _log(f"frase per Whisper: {len(segment) / (RATE * 2):.1f} s, "
                     f"soglia {cutter.threshold():.3f}")
                jobs.put(segment)
        if not self._cancelled:
            segment = cutter.flush()
            if segment:
                jobs.put(segment)

    def _whisper_worker(self, jobs, options, devices):
        while True:
            pcm = jobs.get()
            if pcm is None or self._cancelled:
                return
            self._emit(self.on_state, "writing")
            try:
                text = self._transcribe(pcm, options, devices)
            except VoiceError as e:
                self._emit(self.on_error, e)
                self._stop.set()
                self._stop_mic()
                return
            if text and not self._cancelled:
                self.prompt = (self.prompt + " " + text)[-PROMPT_CHARS:]
                self._emit(self.on_text, text)
            if not self._stop.is_set():
                self._emit(self.on_state, "paused" if self._pause.is_set() else "listening")

    def _transcribe(self, pcm, options, devices):
        run = tempfile.mkdtemp(prefix="frase-", dir=LIVE_DIR)
        try:
            wav = os.path.join(run, "frase.wav")
            prefix = os.path.join(run, "testo")
            write_wav(wav, pcm)
            cmd, env = whisper_command(options["whisper_model"], wav, prefix,
                                       options.get("language") or "auto",
                                       options.get("threads"), options.get("gpu"),
                                       options.get("gpu_device", ""), self.prompt, devices)
            try:
                self._proc = subprocess.Popen(cmd, env=env, stdin=subprocess.DEVNULL,
                                              stdout=subprocess.DEVNULL,
                                              stderr=subprocess.PIPE, start_new_session=True)
                err = self._proc.communicate()[1].decode("utf-8", "replace")
                code = self._proc.returncode
            except OSError as e:
                raise VoiceError("err_whisper_start", str(e)) from e
            finally:
                self._proc = None
            if self._cancelled:
                return ""
            done = "whisper_print_timings" in err and "total time" in err
            if code != 0 and not (done and os.path.isfile(prefix + ".json")):
                tail = "\n".join(err.strip().splitlines()[-8:])
                raise VoiceError("err_whisper", f"{whisper.exit_description(code)}\n{tail}")
            try:
                _lang, segments = whisper.load_json(prefix + ".json")
            except (OSError, ValueError) as e:
                raise VoiceError("err_whisper", str(e)) from e
            segments = whisper.collapse_repeats(segments)
            return " ".join(s.text for s in segments).strip()
        finally:
            shutil.rmtree(run, ignore_errors=True)


class SpeechCutter:
    """Taglia il parlato del microfono in frasi per Whisper: una frase va
    dalla voce a un silenzio di WHISPER_PAUSE, con WHISPER_PREROLL di audio
    prima, al massimo WHISPER_MAX. La voce si riconosce dall'energia, sopra
    una soglia tre volte il rumore di fondo. Il rumore è il livello più
    basso degli ultimi NOISE_WINDOW secondi, misurato sempre, anche mentre
    si parla: la voce ha sempre delle pause e non lo fa salire, e una ventola
    si impara anche se è più forte della soglia iniziale. Prima il rumore
    seguiva la media dei livelli fuori dalla voce, compresa la voce bassa:
    la soglia saliva da sola e dopo un po' la voce non si sentiva più."""

    NOISE_WINDOW = 5.0

    def __init__(self):
        self.pre = collections.deque(maxlen=int(WHISPER_PREROLL / 0.02))
        self.speech = bytearray()
        self.levels = collections.deque(maxlen=int(self.NOISE_WINDOW / 0.02))
        self.noise = 0.004
        self.loud = self.voiced = self.silent = 0
        self.in_speech = False

    def threshold(self):
        return max(0.012, self.noise * 3.0)

    def feed(self, data):
        """Un blocco di 20 ms; restituisce una frase finita o None."""
        level = _rms(data)
        self.levels.append(level)
        self.noise = min(self.levels)
        threshold = self.threshold()
        if not self.in_speech:
            self.loud = self.loud + 1 if level > threshold else 0
            self.pre.append(data)
            if self.loud >= 3:                                      # 60 ms di voce
                self.in_speech = True
                self.speech = bytearray(b"".join(self.pre))
                self.voiced, self.silent = self.loud, 0
            return None
        self.speech += data
        if level > threshold:
            self.voiced += 1
            self.silent = 0
        else:
            self.silent += 1
        if self.silent * 0.02 >= WHISPER_PAUSE or len(self.speech) / (RATE * 2) >= WHISPER_MAX:
            return self.flush()
        return None

    def flush(self):
        """La frase in corso, se c'è abbastanza voce (pausa, stop)."""
        segment = bytes(self.speech) if self.in_speech and \
            self.voiced * 0.02 >= WHISPER_MIN_SPEECH else None
        self.in_speech, self.speech = False, bytearray()
        self.voiced = self.silent = self.loud = 0
        self.pre.clear()
        return segment


# ── trascrizione di un file ────────────────────────────────────────────────
class FileTranscriber:
    """Un file audio o video → documento Markdown. Callback nel thread
    dell'interfaccia:
        on_progress(frazione o None, fase)   fase: "audio" | "model" | "speech"
        on_done(errore, markdown)            errore: None, "cancelled" o VoiceError
    Whisper: rusca_whisper.Transcriber. Vosk: ffmpeg decodifica in memoria
    (niente file) e il riconoscitore lavora sul flusso."""

    def __init__(self, on_progress=None, on_done=None):
        self.on_progress = on_progress or (lambda f, s: None)
        self.on_done = on_done or (lambda e, m: None)
        self._whisper = None
        self._cancel = threading.Event()
        self._proc = None
        self._thread = None

    def start(self, media, engine, options, title="", recognizer=None):
        """recognizer: un vosk.Recognizer già caricato con lo stesso modello
        (Dictation.borrow_recognizer()), che resta di chi lo presta."""
        if not whisper.find_ffmpeg():
            raise VoiceError("err_no_ffmpeg")
        self._cancel.clear()
        if engine == "whisper":
            if not whisper.find_binary():
                raise VoiceError("err_no_whisper")
            if not options.get("whisper_model"):
                raise VoiceError("err_no_whisper_model")

            def stage(name, percent=0):
                self.on_progress(None if name != "speech" else percent / 100.0, name)

            def done(error, _language, segments):
                if error is None:
                    self.on_done(None, whisper.to_markdown(segments, title))
                elif error == "cancelled":
                    self.on_done("cancelled", "")
                else:
                    self.on_done(_from_whisper(error), "")
            self._whisper = whisper.Transcriber(on_stage=stage, on_done=done)
            try:
                self._whisper.start(media, options["whisper_model"],
                                    options.get("language") or "auto",
                                    options.get("threads"), options.get("gpu"),
                                    options.get("gpu_device", ""))
            except whisper.WhisperError as e:
                raise _from_whisper(e) from e
            return
        if not vosk.find_library():
            raise VoiceError("err_no_vosk")
        if not options.get("vosk_model"):
            raise VoiceError("err_no_vosk_model")
        self._thread = threading.Thread(target=self._vosk_work,
                                        args=(media, options["vosk_model"], title, recognizer),
                                        daemon=True)
        self._thread.start()

    def cancel(self):
        self._cancel.set()
        if self._whisper is not None:
            self._whisper.cancel()
        proc = self._proc
        if proc is not None and proc.poll() is None:
            try:
                os.killpg(os.getpgid(proc.pid), signal.SIGTERM)
            except OSError:
                pass

    def _emit(self, fn, *args):
        GLib.idle_add(lambda: fn(*args) and False)

    _DURATION = re.compile(r"Duration:\s*(\d+):(\d\d):(\d\d(?:\.\d+)?)")

    def _vosk_work(self, media, model, title, borrowed=None):
        rec = borrowed
        segments = []
        try:
            if rec is None:
                self._emit(self.on_progress, None, "model")
                try:
                    rec = vosk.Recognizer(model)
                except vosk.VoskError as e:
                    raise VoiceError(e.key, e.detail) from e
            rec.reset()
            self._emit(self.on_progress, None, "audio")
            self._proc = proc = subprocess.Popen(
                [whisper.find_ffmpeg(), "-nostdin", "-hide_banner", "-nostats",
                 "-protocol_whitelist", "file", "-i", media,
                 "-vn", "-sn", "-dn", "-map", "0:a:0", "-ac", "1", "-ar", str(RATE),
                 "-f", "s16le", "-"],
                stdout=subprocess.PIPE, stderr=subprocess.PIPE, stdin=subprocess.DEVNULL,
                start_new_session=True)
            duration = [0.0]
            err_tail = collections.deque(maxlen=8)

            def read_err():
                for raw in proc.stderr:
                    line = raw.decode("utf-8", "replace").strip()
                    err_tail.append(line)
                    m = self._DURATION.search(line)
                    if m and not duration[0]:
                        h, mi, s = m.groups()
                        duration[0] = int(h) * 3600 + int(mi) * 60 + float(s)
            reader = threading.Thread(target=read_err, daemon=True)
            reader.start()
            done_bytes, last = 0, 0.0
            while not self._cancel.is_set():
                data = proc.stdout.read(FRAME * 50)               # 1 s
                if not data:
                    break
                done_bytes += len(data)
                if rec.accept(data):
                    segments += _vosk_segments(rec.result())
                now = time.monotonic()
                if duration[0] and now - last > 0.25:
                    last = now
                    self._emit(self.on_progress,
                               min(1.0, done_bytes / (duration[0] * RATE * 2)), "speech")
            code = proc.wait()
            reader.join(2)
            if self._cancel.is_set():
                self._emit(self.on_done, "cancelled", "")
                return
            segments += _vosk_segments(rec.final_result())
            if code != 0 and not done_bytes:
                raise VoiceError("err_audio", "\n".join(err_tail))
            self._emit(self.on_done, None, whisper.to_markdown(segments, title))
        except VoiceError as e:
            self._emit(self.on_done, "cancelled" if self._cancel.is_set() else e, "")
        except OSError as e:
            self._emit(self.on_done, VoiceError("err_audio", str(e)), "")
        finally:
            self._proc = None
            if rec is not None and rec is not borrowed:
                rec.close()


def _vosk_segments(result):
    """Un risultato di Vosk (con le parole e i loro tempi) → Segment di
    rusca_whisper, in ms. Vosk non scrive la punteggiatura: la frase, che
    finisce dove chi parla fa una pausa, prende la maiuscola e il punto."""
    words = result.get("result") or []
    text = " ".join((result.get("text") or "").split())
    if not text:
        return []
    text = _capitalize(text)
    if not text.endswith(_SENTENCE_END):
        text += "."
    start = int(float(words[0].get("start", 0)) * 1000) if words else 0
    end = int(float(words[-1].get("end", 0)) * 1000) if words else start
    return [whisper.Segment(start, end, text)]


# ── lettura ad alta voce ──────────────────────────────────────────────────
def reading_sentences(text, skip_code=True, skip_notes=True, lexicon=None):
    """Il documento Markdown come frasi da dire: il motore comune decide che
    cosa si legge (speech_blocks(): niente marcatori, il testo dei link, le
    formule in simboli), speech_text.Sentences lo taglia in frasi, il
    lessico delle pronunce corregge gli accenti."""
    out = []
    for kind, body in md.speech_blocks(text):
        if kind == "break" or (kind == "code" and skip_code) or (kind == "note" and skip_notes):
            continue
        body = " ".join(body.split())
        if kind in ("heading", "item", "table") and not body.endswith(_SENTENCE_END + (":", ";")):
            body += "."
        cut = st.Sentences()
        for sentence in cut.feed(body + "\n") + cut.flush():
            sentence = sentence.strip()
            if sentence:
                out.append(st.apply_lexicon(sentence, lexicon or {}))
    return out


class Reader:
    """La voce di Piper, caricata una volta (ruscapiper-stream resta aperto
    finché non cambia la voce). on_state("reading" | "idle") e
    on_error(VoiceError) arrivano nel thread dell'interfaccia."""

    def __init__(self, on_state=None, on_error=None):
        self.on_state = on_state or (lambda s: None)
        self.on_error = on_error or (lambda e: None)
        self._speaker = None
        self._voice = ""
        self._watch = 0
        self._loading = False

    @property
    def reading(self):
        return self._watch != 0 or self._loading

    def read(self, sentences, voice, speed=1.0):
        """Mette in coda le frasi; la voce si carica in un thread se serve."""
        self.stop()
        if not piper.available():
            raise VoiceError("err_no_piper", piper.STREAM)
        if not voice or not os.path.isfile(voice):
            raise VoiceError("err_no_voice")
        if not sentences:
            return
        if self._speaker is not None and self._voice == voice:
            self._speak(sentences, speed)
            return
        self._loading = True
        self.on_state("reading")

        def load():
            try:
                old, self._speaker = self._speaker, None
                if old is not None:
                    old.close()
                speaker = piper.Speaker(voice, speed)
            except piper.PiperError as e:
                GLib.idle_add(self._failed, VoiceError(e.key, str(e)))
                return
            except (OSError, RuntimeError) as e:
                GLib.idle_add(self._failed, VoiceError("err_voice_load", str(e)))
                return
            GLib.idle_add(self._loaded, speaker, voice, sentences, speed)
        threading.Thread(target=load, daemon=True).start()

    def _failed(self, error):
        self._loading = False
        self.on_state("idle")
        self.on_error(error)
        return False

    def _loaded(self, speaker, voice, sentences, speed):
        self._loading = False
        self._speaker, self._voice = speaker, voice
        speaker.on_error = lambda key: self.on_error(VoiceError(key))
        if self._cancel_pending:
            self._cancel_pending = False
            self.on_state("idle")
            return False
        self._speak(sentences, speed)
        return False

    _cancel_pending = False

    def _speak(self, sentences, speed):
        self._speaker.set_speed(speed)
        for s in sentences:
            self._speaker.say(s)
        self.on_state("reading")
        if not self._watch:
            self._watch = GLib.timeout_add(150, self._check)

    def _check(self):
        if self._speaker is not None and self._speaker.busy:
            return True
        self._watch = 0
        self.on_state("idle")
        return False

    def stop(self):
        if self._loading:
            self._cancel_pending = True
        if self._watch:
            GLib.source_remove(self._watch)
            self._watch = 0
        if self._speaker is not None:
            self._speaker.stop()
        if not self._loading:
            self.on_state("idle")

    def close(self):
        self.stop()
        if self._speaker is not None:
            self._speaker.close()
            self._speaker = None
