# -*- coding: utf-8 -*-
# rusca_whisper.py — RuscaLinux OS Tools 1.99.3 — GPL-3.0-or-later
#
# Avvio e sorveglianza di ruscawhisper-engine (whisper-cli, cioe'
# whisper.cpp: software esterno, licenza MIT) per RuscaDubbing, e scrittura
# della trascrizione in Markdown e in SRT.
#
# Una trascrizione sono due processi, uno dopo l'altro:
#   1. ffmpeg (pacchetto Debian) estrae l'audio del video o del file audio e
#      lo porta nel formato che Whisper vuole: WAV, 16 kHz, mono;
#   2. whisper-cli legge il WAV e scrive la trascrizione in un file JSON.
# Tutti e due partono, lavorano su un file ed escono: non resta acceso
# nessun server.
#
# Privacy e sicurezza (specifiche, sezione 11):
#   * nessun modulo di rete: qui non servono nemmeno le connessioni a
#     127.0.0.1 che RuscaLLama usa per il suo motore. whisper-cli non ha
#     codice di rete (lo controlla la build di ruscawhisper-engine), e
#     ffmpeg e' avviato con -protocol_whitelist file: legge solo file
#     locali, anche se il file scelto e' una playlist che nomina indirizzi;
#   * i programmi sono avviati con percorso assoluto e lista di argomenti,
#     mai tramite shell;
#   * i file di lavoro stanno in ~/.cache/ruscadubbing (permessi 0700) e
#     sono cancellati alla fine di ogni trascrizione, a ogni avvio e alla
#     chiusura.
import collections
import ctypes
import json
import os
import re
import shutil
import signal
import subprocess
import sys
import tempfile
import threading

from gi.repository import GLib

# RUSCAWHISPER_ENGINE_DIR: per provare un motore compilato a mano.
ENGINE_DIRS = tuple(filter(None, (os.environ.get("RUSCAWHISPER_ENGINE_DIR"),
                                  "/usr/lib/ruscawhisper-engine")))
# RUSCADUBBING_FFMPEG: per provare un ffmpeg diverso da quello di Debian.
FFMPEG_PATHS = tuple(filter(None, (os.environ.get("RUSCADUBBING_FFMPEG"),
                                   "/usr/bin/ffmpeg")))
SYSTEM_MODEL_DIR = "/usr/share/ruscawhisper/models"
USER_MODEL_DIR = os.path.join(GLib.get_user_data_dir(), "ruscawhisper", "models")
MODEL_DIRS = (SYSTEM_MODEL_DIR, USER_MODEL_DIR)
WORK_DIR = os.path.join(GLib.get_user_cache_dir(), "ruscadubbing")

# Una pausa cosi' lunga nel parlato comincia un paragrafo nuovo; un
# paragrafo gia' lungo si chiude alla prima frase finita.
PARAGRAPH_PAUSE_MS = 2000
PARAGRAPH_CHARS = 600
SENTENCE_END = (".", "?", "!", "…", "。", "？", "！", ".\"", ".”", "?”", "!”")

Segment = collections.namedtuple("Segment", "start end text")   # tempi in ms


class WhisperError(Exception):
    """Errore con un messaggio pensato per l'utente (il chiamante lo traduce
    tramite la chiave `key`)."""

    def __init__(self, key, detail=""):
        super().__init__(f"{key}: {detail}" if detail else key)
        self.key = key
        self.detail = detail


# ── che cosa c'e' sul computer ──────────────────────────────────────────────
def _find_executable(dirs_or_paths, name=None):
    for p in dirs_or_paths:
        if name:
            p = os.path.join(p, name)
        if os.path.isfile(p) and os.access(p, os.X_OK):
            return p
    return None


def find_binary():
    return _find_executable(ENGINE_DIRS, "whisper-cli")


def find_ffmpeg():
    return _find_executable(FFMPEG_PATHS)


def physical_cores():
    """Core fisici: la regola pratica per i thread di whisper.cpp."""
    base = "/sys/devices/system/cpu"
    primi = set()
    try:
        for nome in os.listdir(base):
            if nome.startswith("cpu") and nome[3:].isdigit():
                try:
                    with open(os.path.join(base, nome, "topology",
                                           "thread_siblings_list")) as f:
                        primi.add(f.read().strip().split(",")[0].split("-")[0])
                except OSError:
                    continue
    except OSError:
        pass
    return len(primi) or os.cpu_count() or 4


def is_model_name(name):
    """Modelli Whisper in formato ggml: file .bin. Esclusi i modelli che
    riconoscono solo la presenza della voce (VAD), che whisper.cpp
    distribuisce nello stesso formato, e i file di codifica per Core ML e
    OpenVINO."""
    low = name.lower()
    return (low.endswith(".bin") and not low.startswith(".")
            and "silero" not in low and "vad" not in low and "encoder" not in low)


def find_models(dirs=None):
    """Tutti i modelli nelle cartelle dei modelli, dal piu' grande (di
    solito il piu' preciso). Restituisce percorsi."""
    trovati = []
    for d in (MODEL_DIRS if dirs is None else dirs):
        if not d or not os.path.isdir(d):
            continue
        for root, _dirs, files in os.walk(d):
            for nome in files:
                p = os.path.join(root, nome)
                if is_model_name(nome) and p not in trovati:
                    trovati.append(p)

    def size(p):
        try:
            return os.path.getsize(p)
        except OSError:
            return 0
    trovati.sort(key=lambda p: (-size(p), p))
    return trovati


def ensure_user_model_dir():
    """Crea, se manca, la cartella in cui l'utente copia i modelli."""
    os.makedirs(USER_MODEL_DIR, exist_ok=True)
    return USER_MODEL_DIR


def clean_work_dir():
    """Cancella i file di lavoro rimasti (da chiamare all'avvio e alla fine):
    contengono l'audio dell'utente."""
    try:
        for nome in os.listdir(WORK_DIR):
            p = os.path.join(WORK_DIR, nome)
            if os.path.isdir(p) and not os.path.islink(p):
                shutil.rmtree(p, ignore_errors=True)
            else:
                try:
                    os.unlink(p)
                except OSError:
                    pass
    except OSError:
        pass


# ── schede grafiche ─────────────────────────────────────────────────────────
# whisper-cli non sa elencare le schede: le chiede al caricatore Vulkan
# (libvulkan1 di Debian) questo stesso modulo, tramite ctypes. La scheda
# scelta si passa al motore con GGML_VK_VISIBLE_DEVICES, che usa la stessa
# numerazione (l'ordine di vkEnumeratePhysicalDevices): il motore vede solo
# quella scheda e la usa come scheda 0. Il nome dell'opzione e' controllato
# dalla build di ruscawhisper-engine.
#
# L'elenco si legge in un processo a parte (list_devices): il driver di una
# scheda puo' bloccarsi o terminare il processo che lo carica, e non deve
# succedere a RuscaDubbing.
VK_TYPES = {1: "integrated", 2: "discrete"}        # le altre (CPU, virtuali) no
# Solo per le prove: RUSCADUBBING_VK_ALL=1 elenca anche le schede emulate
# (come llvmpipe, il driver software di Mesa), che ggml di solito ignora.
VK_ALL_TYPES = {0: "other", 1: "integrated", 2: "discrete", 3: "virtual", 4: "cpu"}


def _vulkan_devices():
    """[{"index", "name", "type", "mib"}] dal caricatore Vulkan, nell'ordine
    di vkEnumeratePhysicalDevices. Solo schede vere, integrate o dedicate:
    sono quelle che ggml usa. Lista vuota se manca Vulkan."""
    try:
        vk = ctypes.CDLL("libvulkan.so.1")
    except OSError:
        return []
    p = ctypes.c_void_p

    class AppInfo(ctypes.Structure):
        _fields_ = [("sType", ctypes.c_int), ("pNext", p), ("pApplicationName", ctypes.c_char_p),
                    ("applicationVersion", ctypes.c_uint32), ("pEngineName", ctypes.c_char_p),
                    ("engineVersion", ctypes.c_uint32), ("apiVersion", ctypes.c_uint32)]

    class CreateInfo(ctypes.Structure):
        _fields_ = [("sType", ctypes.c_int), ("pNext", p), ("flags", ctypes.c_uint32),
                    ("pApplicationInfo", ctypes.POINTER(AppInfo)),
                    ("enabledLayerCount", ctypes.c_uint32), ("ppEnabledLayerNames", p),
                    ("enabledExtensionCount", ctypes.c_uint32), ("ppEnabledExtensionNames", p)]

    app = AppInfo(0, None, b"RuscaDubbing", 1, None, 0, 1 << 22)      # Vulkan 1.0
    info = CreateInfo(1, None, 0, ctypes.pointer(app), 0, None, 0, None)
    instance = p()
    vk.vkCreateInstance.restype = ctypes.c_int
    if vk.vkCreateInstance(ctypes.byref(info), None, ctypes.byref(instance)) != 0:
        return []
    devices = []
    try:
        count = ctypes.c_uint32(0)
        vk.vkEnumeratePhysicalDevices.restype = ctypes.c_int
        if vk.vkEnumeratePhysicalDevices(instance, ctypes.byref(count), None) != 0:
            return []
        handles = (p * count.value)()
        if vk.vkEnumeratePhysicalDevices(instance, ctypes.byref(count), handles) not in (0, 5):
            return []
        for i in range(count.value):
            # VkPhysicalDeviceProperties: 5 interi a 32 bit (deviceType e'
            # il quinto), poi deviceName[256]. Il buffer e' piu' grande
            # della struttura intera.
            props = ctypes.create_string_buffer(4096)
            vk.vkGetPhysicalDeviceProperties(p(handles[i]), props)
            kind = int.from_bytes(props.raw[16:20], "little")
            name = props.raw[20:276].split(b"\0", 1)[0].decode("utf-8", "replace").strip()
            # VkPhysicalDeviceMemoryProperties: memoryTypeCount (4 byte),
            # 32 VkMemoryType da 8 byte, memoryHeapCount (offset 260), poi
            # 16 VkMemoryHeap da 16 byte {size 64 bit, flags} da offset 264.
            mem = ctypes.create_string_buffer(1024)
            vk.vkGetPhysicalDeviceMemoryProperties(p(handles[i]), mem)
            heaps = min(16, int.from_bytes(mem.raw[260:264], "little"))
            local = 0
            for h in range(heaps):
                off = 264 + 16 * h
                size = int.from_bytes(mem.raw[off:off + 8], "little")
                flags = int.from_bytes(mem.raw[off + 8:off + 12], "little")
                if flags & 1:                                # DEVICE_LOCAL
                    local = max(local, size)
            types = VK_ALL_TYPES if os.environ.get("RUSCADUBBING_VK_ALL") else VK_TYPES
            if kind in types and name:
                devices.append({"index": i, "name": name, "type": types[kind],
                                "mib": local // (1024 * 1024)})
    finally:
        vk.vkDestroyInstance(instance, None)
    return devices


def list_devices(timeout=20):
    """Schede grafiche utilizzabili, lette in un processo a parte (vedi
    sopra). Ogni scheda ha anche "label", unica anche quando due schede hanno
    lo stesso nome: e' cio' che si salva nelle impostazioni. Puo' servire un
    secondo: va chiamata fuori dal thread dell'interfaccia."""
    try:
        # -I: senza le variabili PYTHON* e i moduli della cartella corrente.
        # RUSCADUBBING_VK_ALL e le variabili di Vulkan passano comunque.
        r = subprocess.run([sys.executable, "-I", os.path.abspath(__file__), "--list-devices"],
                           stdin=subprocess.DEVNULL, capture_output=True, text=True,
                           timeout=timeout)
        devices = json.loads(r.stdout or "[]")
    except (OSError, subprocess.SubprocessError, ValueError):
        return []
    seen = collections.Counter()
    for d in devices:
        seen[d["name"]] += 1
        d["label"] = d["name"] if seen[d["name"]] == 1 else f"{d['name']} ({seen[d['name']]})"
    return devices


def device_index(label, devices):
    """Numero Vulkan della scheda salvata, o None se la scelta e'
    automatica o la scheda non c'e' piu'. Si salva il nome e non il numero,
    perche' il numero puo' cambiare se cambiano schede o driver."""
    for d in devices:
        if label and d["label"] == label:
            return d["index"]
    return None


# ── risultato di whisper-cli ────────────────────────────────────────────────
# Una riga scritta da whisper-cli mentre trascrive:
#   "[00:00:07.960 --> 00:00:10.760]   ask what you can do for your country."
_LINE_RE = re.compile(r"^\[(\d+):(\d\d):(\d\d)[.,](\d{3}) --> "
                      r"(\d+):(\d\d):(\d\d)[.,](\d{3})\]\s?(.*)$")
_PROGRESS_RE = re.compile(r"progress\s*=\s*(\d+)\s*%")
_LANGUAGE_RE = re.compile(r"auto-detected language:\s*([a-z]{2,3})\b")


def _ms(h, m, s, ms):
    return ((int(h) * 60 + int(m)) * 60 + int(s)) * 1000 + int(ms)


def parse_line(line):
    """Segmento da una riga dello standard output, o None."""
    m = _LINE_RE.match(line.strip())
    if not m:
        return None
    g = m.groups()
    return Segment(_ms(*g[0:4]), _ms(*g[4:8]), g[8].strip())


def parse_progress(line):
    """Percentuale (0–100) da una riga di avanzamento, o None."""
    m = _PROGRESS_RE.search(line)
    return min(100, int(m.group(1))) if m else None


def parse_language(line):
    m = _LANGUAGE_RE.search(line)
    return m.group(1) if m else None


def load_json(path):
    """Legge il JSON scritto da whisper-cli (-oj): (lingua, [Segment]).
    whisper-cli protegge solo virgolette e barre rovesciate, quindi nel
    testo possono restare caratteri di controllo e sequenze UTF-8 spezzate:
    si legge senza pretendere un JSON rigoroso."""
    with open(path, "rb") as f:
        data = json.loads(f.read().decode("utf-8", "replace"), strict=False)
    language = (data.get("result") or {}).get("language") or ""
    segments = []
    for item in data.get("transcription") or ():
        off = item.get("offsets") or {}
        text = " ".join((item.get("text") or "").split())
        try:
            start, end = int(off.get("from", 0)), int(off.get("to", 0))
        except (TypeError, ValueError):
            continue
        if text:
            segments.append(Segment(max(0, start), max(0, end), text))
    return language, segments


# ── formati di uscita ───────────────────────────────────────────────────────
def srt_time(ms):
    ms = max(0, int(ms))
    h, rest = divmod(ms, 3600000)
    m, rest = divmod(rest, 60000)
    s, ms = divmod(rest, 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def to_srt(segments):
    """Sottotitoli SubRip: un blocco numerato per segmento. Un segmento che
    finisce prima di cominciare (capita ai margini dell'audio) dura almeno
    un millisecondo, altrimenti alcuni lettori scartano il blocco."""
    blocks = []
    for seg in segments:
        text = " ".join(seg.text.split())
        if not text:
            continue
        end = max(seg.end, seg.start + 1)
        blocks.append(f"{len(blocks) + 1}\n{srt_time(seg.start)} --> {srt_time(end)}\n{text}\n")
    return "\n".join(blocks)


def paragraphs(segments):
    """Raggruppa i segmenti in paragrafi: uno nuovo dopo una pausa lunga, o
    alla fine di una frase quando il paragrafo e' gia' lungo."""
    result, current, last_end = [], [], None
    for seg in segments:
        text = " ".join(seg.text.split())
        if not text:
            continue
        if current:
            length = sum(len(t) + 1 for t in current)
            pause = last_end is not None and seg.start - last_end >= PARAGRAPH_PAUSE_MS
            full = length >= PARAGRAPH_CHARS and current[-1].endswith(SENTENCE_END)
            if pause or full:
                result.append(" ".join(current))
                current = []
        current.append(text)
        last_end = seg.end
    if current:
        result.append(" ".join(current))
    return result


_MD_INLINE = re.compile(r"([\\`*_<$]|\](?=[(:\[])|~(?=~)|=(?==)|&(?=#?\w+;)|@(?=\w))")
_MD_AUTOLINK = re.compile(r"(?i)\b(https?:|www\.)")
_MD_START = re.compile(r"^(?:[#>]|[-+](?=\s|$)|-(?=[- ]*$)|\d{1,9}(?=[.)](?:\s|$)))")


def escape_markdown(text):
    """Il parlato trascritto e' testo, non Markdown: i caratteri che
    CommonMark (con le estensioni dei RuscaLinux OS Tools) leggerebbe come
    formattazione vengono protetti con la barra rovesciata. Anche gli
    indirizzi restano testo: niente link automatici verso siti o caselle
    nominati a voce (o inventati dal modello). Le parentesi quadre restano
    come sono ("[Musica]" e' frequente nelle trascrizioni): si protegge solo
    la chiusa che formerebbe un link, e mai l'aperta, perche' "\\[" apre una
    formula nelle estensioni dei RuscaLinux OS Tools."""
    text = _MD_INLINE.sub(r"\\\1", text.strip())
    text = _MD_AUTOLINK.sub(lambda m: m.group(1)[:-1] + "\\" + m.group(1)[-1], text)
    m = _MD_START.match(text)
    if m:
        # "12. parole" -> "12\. parole"; "# parole" -> "\# parole"
        i = m.end() if text[0].isdigit() else 0
        text = text[:i] + "\\" + text[i:]
    return text


def to_markdown(segments, title=""):
    """Documento Markdown: titolo (di solito il nome del file) e il testo a
    paragrafi."""
    parts = []
    if title.strip():
        parts.append("# " + escape_markdown(" ".join(title.split())))
    parts += [escape_markdown(p) for p in paragraphs(segments)]
    return "\n\n".join(parts) + "\n"


def plain_text(segments):
    """Il testo a paragrafi, come lo mostra la finestra."""
    return "\n\n".join(paragraphs(segments))


# ── trascrizione ────────────────────────────────────────────────────────────
class Transcriber:
    """Una trascrizione per volta. Le callback arrivano sempre nel thread
    dell'interfaccia (GLib.idle_add):
        on_stage(stage, percent)   "audio" | "model" | "speech" (0–100)
        on_segment(Segment)        ogni segmento, appena riconosciuto
        on_log(line)               righe scritte dai due programmi
        on_done(error, language, segments)
                                   error: None, "cancelled" o WhisperError
    """

    def __init__(self, on_stage=None, on_segment=None, on_log=None, on_done=None):
        self.on_stage = on_stage or (lambda stage, percent=0: None)
        self.on_segment = on_segment or (lambda segment: None)
        self.on_log = on_log or (lambda line: None)
        self.on_done = on_done or (lambda error, language, segments: None)
        self._proc = None
        self._lock = threading.Lock()
        self._cancel = threading.Event()
        self._thread = None

    @property
    def running(self):
        return self._thread is not None and self._thread.is_alive()

    def start(self, media, model, language="auto", threads=None, gpu=False, gpu_device=""):
        """Avvia la trascrizione in background e ritorna subito. gpu_device:
        "label" di una scheda di list_devices(), o "" per la scelta del
        motore."""
        if self.running:
            return
        if not find_binary():
            raise WhisperError("err_no_engine")
        if not find_ffmpeg():
            raise WhisperError("err_no_ffmpeg")
        if not model or not os.path.isfile(model):
            raise WhisperError("err_no_model")
        if not media or not os.path.isfile(media):
            raise WhisperError("open_error", media or "")
        self._cancel.clear()
        self._thread = threading.Thread(
            target=self._work, args=(media, model, language or "auto",
                                     int(threads or physical_cores()), bool(gpu),
                                     gpu_device or ""),
            daemon=True)
        self._thread.start()

    def cancel(self):
        """Ferma il programma in corso; on_done arriva con "cancelled"."""
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

    # ── lavoro (thread proprio) ───────────────────────────────────────────
    def _emit(self, callback, *args):
        GLib.idle_add(lambda: callback(*args) and False)

    def _run(self, cmd, env=None, on_stdout=None, on_stderr=None):
        """Avvia un programma, passa le sue righe alle due funzioni e ne
        restituisce il codice di uscita e le ultime righe di errore."""
        self._emit(self.on_log, "$ " + " ".join(cmd))
        try:
            proc = subprocess.Popen(
                cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                stdin=subprocess.DEVNULL, env=env, start_new_session=True)
        except OSError as e:
            raise WhisperError("err_start", str(e)) from e
        with self._lock:
            self._proc = proc
        tail = collections.deque(maxlen=12)

        def read_stderr():
            for raw in iter(proc.stderr.readline, b""):
                line = raw.decode("utf-8", "replace").rstrip("\r\n")
                tail.append(line)
                self._emit(self.on_log, line)
                if on_stderr:
                    on_stderr(line)
        reader = threading.Thread(target=read_stderr, daemon=True)
        reader.start()
        try:
            for raw in iter(proc.stdout.readline, b""):
                line = raw.decode("utf-8", "replace").rstrip("\r\n")
                if on_stdout:
                    on_stdout(line)
            code = proc.wait()
        finally:
            if proc.poll() is None:            # eccezione: non lasciarlo acceso
                try:
                    os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
                except OSError:
                    pass
                proc.wait()
            reader.join(5)
            proc.stdout.close()
            proc.stderr.close()
            with self._lock:
                self._proc = None
        if self._cancel.is_set():
            raise _Cancelled()
        return code, "\n".join(t for t in tail if t.strip())

    def _work(self, media, model, language, threads, gpu, gpu_device=""):
        error, detected, segments = None, "", []
        run_dir = None
        try:
            os.makedirs(WORK_DIR, mode=0o700, exist_ok=True)
            os.chmod(WORK_DIR, 0o700)
            # Una cartella per trascrizione: una corsa appena fermata non
            # tocca i file di quella nuova.
            run_dir = tempfile.mkdtemp(prefix="run-", dir=WORK_DIR)
            wav = os.path.join(run_dir, "audio.wav")
            prefix = os.path.join(run_dir, "testo")

            # 1. Audio: prima traccia audio, mono, 16 kHz, 16 bit.
            self._emit(self.on_stage, "audio", 0)
            code, tail = self._run([
                find_ffmpeg(), "-nostdin", "-hide_banner", "-loglevel", "error",
                "-protocol_whitelist", "file", "-i", media,
                "-vn", "-sn", "-dn", "-map", "0:a:0", "-ac", "1", "-ar", "16000",
                "-c:a", "pcm_s16le", "-f", "wav", "-y", wav])
            if code != 0 or not os.path.isfile(wav) or os.path.getsize(wav) <= 44:
                raise WhisperError("err_audio", tail)

            # 2. Riconoscimento.
            self._emit(self.on_stage, "model", 0)
            cmd = [find_binary(), "-m", model, "-f", wav, "-l", language,
                   "-t", str(max(1, threads)), "-oj", "-of", prefix, "-pp"]
            env = os.environ.copy()
            if not gpu:
                # Senza scheda grafica i driver Vulkan vengono nascosti:
                # alcuni driver si bloccano anche con -ng.
                cmd.append("-ng")
                env["VK_DRIVER_FILES"] = "/dev/null"
                env["VK_ICD_FILENAMES"] = "/dev/null"
            elif gpu_device:
                index = device_index(gpu_device, list_devices())
                if index is None:
                    self._emit(self.on_log, f"ruscadubbing: scheda «{gpu_device}» non trovata, "
                                            "scelta automatica")
                else:
                    env["GGML_VK_VISIBLE_DEVICES"] = str(index)
                    self._emit(self.on_log, f"ruscadubbing: scheda «{gpu_device}», "
                                            f"GGML_VK_VISIBLE_DEVICES={index}")
            found = []

            def on_stdout(line):
                seg = parse_line(line)
                if seg and seg.text:
                    self._emit(self.on_segment, seg)

            def on_stderr(line):
                percent = parse_progress(line)
                if percent is not None:
                    self._emit(self.on_stage, "speech", percent)
                elif "processing '" in line:
                    self._emit(self.on_stage, "speech", 0)
                lang = parse_language(line)
                if lang:
                    found.append(lang)
            code, tail = self._run(cmd, env, on_stdout, on_stderr)
            if code != 0:
                raise WhisperError("err_engine", tail)
            try:
                detected, segments = load_json(prefix + ".json")
            except (OSError, ValueError) as e:
                raise WhisperError("err_engine", tail or str(e)) from e
            if language != "auto":
                detected = language
            elif found:
                detected = detected or found[-1]
        except _Cancelled:
            error = "cancelled"
        except WhisperError as e:
            error = "cancelled" if self._cancel.is_set() else e
        except OSError as e:
            error = WhisperError("err_engine", str(e))
        finally:
            if run_dir:
                shutil.rmtree(run_dir, ignore_errors=True)
        self._emit(self.on_done, error, detected, segments)


class _Cancelled(Exception):
    pass


if __name__ == "__main__" and sys.argv[1:] == ["--list-devices"]:
    # Usato da list_devices(), in un processo a parte.
    print(json.dumps(_vulkan_devices()))
