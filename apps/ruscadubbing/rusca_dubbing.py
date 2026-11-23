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
import os
import re
import shutil
import subprocess
import tempfile
import threading

from gi.repository import GLib

import rusca_engine as engine
import rusca_tts as tts
import rusca_whisper as whisper

APP_ID = "org.ruscalinux.RuscaDubbing"
WORK_DIR = os.path.join(GLib.get_user_cache_dir(), "ruscadubbing")
# I moduli comuni lavorano in sottocartelle di quella di RuscaDubbing, non in
# quelle di RuscaTranscriber e RuscaNarrator.
whisper.WORK_DIR = os.path.join(WORK_DIR, "whisper")
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
BATCH = 12                      # battute per richiesta di traduzione
CONTEXT_LINES = 4               # battute già tradotte date come contesto
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


# ── traduzione ──────────────────────────────────────────────────────────────
def build_prompt(src, tgt):
    s, g = english_name(src), english_name(tgt)
    return (
        f"You are a professional dubbing adapter translating spoken dialogue from {s} to "
        f"{g}. You receive numbered subtitle lines in the format `N|MAX|text`, where MAX is "
        f"the maximum number of characters the {g} line may have, so that it can be spoken "
        f"in the time of the original. Translate each line into natural, idiomatic spoken "
        f"{g}, faithful to the meaning and tone. When a faithful translation would be "
        f"longer than MAX, condense it as a professional adapter would, keeping the "
        f"meaning. A sentence may continue across lines: translate it so that each line "
        f"still corresponds to its own part. Answer with exactly one line per input line, "
        f"in the format `N|translation`, same numbers, same order, nothing else: no notes, "
        f"no explanations, no blank translations.")


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
                   batch=BATCH):
    """Traduce le battute a gruppi. chat(body) -> testo è la funzione del
    motore (engine.Engine.chat). Restituisce (traduzioni, statistiche):
    statistiche = {"retried": n, "shortened": n, "kept": n}.
    Una battuta che non torna tradotta si chiede di nuovo da sola; se il
    modello non la restituisce ancora, resta l'originale ("kept")."""
    stats = {"retried": 0, "shortened": 0, "kept": 0}
    system = build_prompt(src, tgt)
    result = [None] * len(cues)

    def ask(lines, context):
        user = ""
        if context:
            user += ("Previous lines, already translated (context only, do not output):\n"
                     + "\n".join(context) + "\n\n")
        user += "Lines to translate:\n" + "\n".join(lines)
        body = dict(SAMPLING, messages=[{"role": "system", "content": system},
                                        {"role": "user", "content": user}],
                    max_tokens=MAX_TOKENS, reasoning_effort="none")
        return parse_translations(chat(body))

    for first in range(0, len(cues), batch):
        if stop_event is not None and stop_event.is_set():
            raise _Stopped()
        if on_progress:
            on_progress(first, len(cues))
        idx = list(range(first, min(first + batch, len(cues))))
        lines = [f"{i + 1}|{budget_chars(cues, i, tgt, max_speed)}|{cues[i].text}" for i in idx]
        context = [f"{cues[j].text} => {result[j]}"
                   for j in range(max(0, first - CONTEXT_LINES), first) if result[j]]
        got = ask(lines, context)
        for i in idx:
            if got.get(i + 1):
                result[i] = got[i + 1]
        missing = [i for i in idx if not result[i]]
        for i in missing:                       # una per volta
            if stop_event is not None and stop_event.is_set():
                raise _Stopped()
            stats["retried"] += 1
            got = ask([f"{i + 1}|{budget_chars(cues, i, tgt, max_speed)}|{cues[i].text}"], context)
            if got.get(i + 1):
                result[i] = got[i + 1]
            else:
                result[i] = cues[i].text
                stats["kept"] += 1
        # Battute molto più lunghe del loro tempo: si chiede una versione breve.
        long_ones = [i for i in idx
                     if len(result[i]) > budget_chars(cues, i, tgt, max_speed) * 1.25]
        if long_ones:
            if stop_event is not None and stop_event.is_set():
                raise _Stopped()
            lines = [f"{i + 1}|{budget_chars(cues, i, tgt, max_speed)}|{cues[i].text}"
                     for i in long_ones]
            got = ask(lines, [f"(too long, shorten to MAX) {result[i]}" for i in long_ones])
            for i in long_ones:
                short = got.get(i + 1)
                if short and len(short) < len(result[i]):
                    result[i] = short
                    stats["shortened"] += 1
    if on_progress:
        on_progress(len(cues), len(cues))
    return result, stats


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
                "alimiter=limit=0.95[out]",
                "-map", "[out]"]
    else:
        cmd += ["-i", dub_wav, "-af", "aresample=48000,aformat=channel_layouts=stereo"]
    return cmd + ["-c:a", "pcm_s16le", "-f", "wav", "-y", out_wav]


def mux_command(ffmpeg, media, mix_wav, srt_src, srt_tgt, out, fmt, src, tgt, has_audio,
                titles=("", "")):
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
    cmd += ["-map", "1:a:0", "-map", "2:s:0", "-map", "3:s:0", "-c:v", "copy"]
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
            "-f", "mp4" if fmt == "mp4" else "matroska", "-y", out]
    return cmd


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


def output_paths(media, folder, src, tgt, fmt):
    """Nomi dei file in uscita, accanto al video o nella cartella scelta."""
    stem = os.path.splitext(os.path.basename(media))[0]
    base = os.path.join(folder or os.path.dirname(os.path.abspath(media)), stem)
    return {
        "srt_src": unique_path(f"{base}.{src}.srt"),
        "srt_tgt": unique_path(f"{base}.{tgt}.srt"),
        "srt_both": unique_path(f"{base}.{src}-{tgt}.srt"),
        "audio": unique_path(f"{base}.{tgt}.opus"),
        "video": unique_path(f"{base}.{tgt}.{fmt}"),
    }


# ── la catena ───────────────────────────────────────────────────────────────
STAGES = ("transcribe", "translate", "dub", "mix")
Options = collections.namedtuple("Options", [
    "media", "folder", "src", "tgt", "whisper_model", "llm_model", "voice", "speaker_file",
    "voice_name", "gpu", "gpu_device", "threads", "context", "max_speed", "seed", "ducking",
    "outputs", "fmt", "titles", "source_srt"])
# outputs: insieme di "srt", "audio", "video". source_srt: file SRT della
# lingua originale da usare al posto della trascrizione ("" = trascrivere).


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
        os.makedirs(WORK_DIR, mode=0o700, exist_ok=True)
        os.chmod(WORK_DIR, 0o700)
        self.run_dir = tempfile.mkdtemp(prefix="run-", dir=WORK_DIR)
        try:
            self.info = probe(o.media)
        except DubbingError as e:
            self._finish(e)
            return
        if o.source_srt:
            self._use_source_srt()
        else:
            self._transcribe()

    def cancel(self):
        if not self.running:
            return
        self.stop_event.set()
        if self.transcriber is not None:
            self.transcriber.cancel()
        if self.speaker is not None:
            self.speaker.cancel()
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
            self.transcriber.start(self.o.media, self.o.whisper_model, self.o.src,
                                   self.o.threads, self.o.gpu, self.o.gpu_device)
        except whisper.WhisperError as e:
            self._finish(DubbingError(e.key, e.detail))

    def _transcribed(self, error, language, segments):
        self.transcriber = None
        if error:
            self._finish(error if error == "cancelled" else DubbingError(error.key, error.detail))
            return
        self.cues = cues_from_segments(segments)
        if not self.cues:
            self._finish(DubbingError("err_no_speech"))
            return
        self.src = language or (self.o.src if self.o.src != "auto" else "en")
        self.on_stage("transcribe", 1.0, self.src)
        self._translate()

    def _translate(self):
        o = self.o
        self.on_stage("translate", 0.0, "")
        if self.src == o.tgt:
            # Stessa lingua: niente traduzione, il doppiaggio rilegge il testo.
            self.translated = [c.text for c in self.cues]
            self._after_translation()
            return
        threading.Thread(target=self._translate_work, daemon=True).start()

    def _translate_work(self):
        o = self.o
        error = None
        try:
            args = ["-t", o.threads, "-c", o.context, "-b", 2048, "-ub", 1024, "--parallel", 1,
                    "--flash-attn", "on", "--reasoning", "off"]
            if o.gpu and o.gpu_device:
                # list_devices apre un processo: qui, fuori dall'interfaccia.
                device = engine.device_name(o.gpu_device, engine.list_devices())
                if device:
                    args += ["--device", device]
            self.engine.start(o.llm_model, args, o.gpu)
            if not self.engine.wait_ready(self.stop_event):
                if self.stop_event.is_set():
                    raise _Stopped()
                raise engine.EngineError("engine_not_ready")
            self.translated, tstats = translate_cues(
                self.engine.chat, self.cues, self.src, self.o.tgt, self.stop_event,
                lambda i, n: self._emit(self.on_stage, "translate", i / max(1, n), f"{i}/{n}"),
                self.o.max_speed)
            self.stats.update(tstats)
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
        self._dub()

    def _write_subtitles(self):
        o = self.o
        self.paths = output_paths(o.media, o.folder, self.src, o.tgt, o.fmt)
        self.work_srt_src = os.path.join(self.run_dir, "originale.srt")
        self.work_srt_tgt = os.path.join(self.run_dir, "tradotto.srt")
        for path, text in ((self.work_srt_src, to_srt(self.cues)),
                           (self.work_srt_tgt, to_srt(self.cues, self.translated))):
            with open(path, "w", encoding="utf-8") as f:
                f.write(text)
        if "srt" in o.outputs:
            for key, src_path in (("srt_src", self.work_srt_src), ("srt_tgt", self.work_srt_tgt)):
                shutil.copyfile(src_path, self.paths[key])
                self.files[key] = self.paths[key]
            with open(self.paths["srt_both"], "w", encoding="utf-8") as f:
                f.write(bilingual_srt(self.cues, self.translated))
            self.files["srt_both"] = self.paths["srt_both"]

    def _dub(self):
        o = self.o
        self.on_stage("dub", 0.0, "")
        pieces = [tts.Piece(t, 0, c.start, c.end) for c, t in zip(self.cues, self.translated)
                  if t.strip()]
        self.speaker = tts.Speaker(
            on_progress=lambda i, n: self.on_stage("dub", i / max(1, n), f"{i + 1}/{n}"),
            on_stage=lambda stage: self.on_stage("dub", 1.0, stage),
            on_log=self.on_log, on_done=self._dubbed)
        try:
            self.speaker.start(pieces, o.voice, srt=True, language=o.tgt,
                               speaker_file=o.speaker_file, voice_name=o.voice_name,
                               gpu=o.gpu, gpu_device=o.gpu_device, threads=o.threads,
                               seed=o.seed, max_speed=o.max_speed, normalize=True)
        except tts.TTSError as e:
            self._finish(DubbingError(e.key, e.detail))

    def _dubbed(self, error, path, stats):
        speaker, self.speaker = self.speaker, None
        if error:
            if speaker is not None:
                speaker.discard()
            self._finish(error if error == "cancelled" else DubbingError(error.key, error.detail))
            return
        self.stats.update(stats)
        self.on_stage("dub", 1.0, "")
        self.on_stage("mix", 0.0, "")
        threading.Thread(target=self._mix_work, args=(path, speaker), daemon=True).start()

    def _run(self, cmd):
        self._emit(self.on_log, "$ " + " ".join(cmd))
        proc = subprocess.Popen(cmd, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                                stderr=subprocess.STDOUT, start_new_session=True)
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
            code, tail = self._run(mix_command(ffmpeg, o.media, voice_wav, mix, has_audio, o.ducking))
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
                code, tail = self._run(mux_command(
                    ffmpeg, o.media, mix, self.work_srt_src, self.work_srt_tgt, tmp, o.fmt,
                    self.src, o.tgt, has_audio, o.titles))
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
