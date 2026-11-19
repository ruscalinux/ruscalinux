# -*- coding: utf-8 -*-
# rusca_diffusion.py — RuscaLinux OS Tools 1.99.3 — GPL-3.0-or-later
#
# Generazione delle immagini di RuscaLLama con ruscadiffusion-engine (sd-cli,
# cioe' stable-diffusion.cpp: software esterno, licenza MIT).
#
# Un'immagine (o un gruppo di immagini con lo stesso prompt) e' un processo:
# sd-cli parte, carica il modello, scrive le immagini PNG ed esce. Non resta
# acceso nessun server e non si apre nessuna porta, nemmeno su 127.0.0.1:
# per questo qui non c'e' rusca_engine.py.
#
# I modelli sono di due tipi:
#   * un file solo (.safetensors, .gguf o .ckpt) con tutto dentro, come
#     Stable Diffusion 1.5, 2.1 e SDXL: si passa con -m;
#   * una cartella con il modello di diffusione e i suoi componenti (VAE,
#     codificatori di testo CLIP e T5, modello linguistico), come FLUX,
#     Stable Diffusion 3.5, Z-Image e Qwen-Image: ogni file ha la sua
#     opzione (--diffusion-model, --vae, --clip_l, --t5xxl, --llm...).
# I file si riconoscono dal nome e, per i .safetensors, dai nomi dei tensori
# scritti nell'intestazione (si legge solo l'intestazione, mai i pesi).
#
# Privacy e sicurezza (specifiche, sezione 11):
#   * nessun modulo di rete;
#   * sd-cli e' avviato con percorso assoluto e lista di argomenti, mai
#     tramite shell; il prompt non e' un argomento (lo vedrebbe chiunque
#     con ps) ma un file (--prompt-file) nella cartella di lavoro;
#   * cartella di lavoro ~/.cache/ruscallama/images con permessi 0700:
#     prompt, anteprime e immagini generate. Si cancella a ogni avvio e alla
#     chiusura: restano solo le immagini che l'utente salva altrove.
import collections
import json
import os
import random
import re
import shutil
import signal
import struct
import subprocess
import tempfile
import threading
import time
from dataclasses import dataclass, field

from gi.repository import GLib

# RUSCADIFFUSION_ENGINE_DIR: per provare un motore compilato a mano.
ENGINE_DIRS = tuple(filter(None, (os.environ.get("RUSCADIFFUSION_ENGINE_DIR"),
                                  "/usr/lib/ruscadiffusion-engine")))
SYSTEM_MODEL_DIR = "/usr/share/ruscadiffusion/models"
USER_MODEL_DIR = os.path.join(GLib.get_user_data_dir(), "ruscadiffusion", "models")
MODEL_DIRS = (SYSTEM_MODEL_DIR, USER_MODEL_DIR)
WORK_DIR = os.path.join(GLib.get_user_cache_dir(), "ruscallama", "images")

MODEL_EXTENSIONS = (".safetensors", ".sft", ".gguf", ".ckpt")
MAX_HEADER = 64 * 1024 * 1024          # intestazione .safetensors piu' grande: file strano
MAX_COUNT = 4                          # immagini per volta
SAMPLERS = ("euler", "euler_a", "dpm++2m", "dpm++2s_a", "heun", "lcm", "ddim_trailing")
QUALITY = {"fast": 0.6, "normal": 1.0, "detailed": 1.6}     # moltiplica i passi
ASPECTS = {"square": 1.0, "landscape": 1.5, "portrait": 1 / 1.5}


class DiffusionError(Exception):
    """Errore con un messaggio pensato per l'utente (il chiamante lo traduce
    tramite la chiave `key`)."""

    def __init__(self, key, detail=""):
        super().__init__(f"{key}: {detail}" if detail else key)
        self.key = key
        self.detail = detail


# ── che cosa c'e' sul computer ──────────────────────────────────────────────
def find_binary():
    for d in ENGINE_DIRS:
        p = os.path.join(d, "sd-cli")
        if os.path.isfile(p) and os.access(p, os.X_OK):
            return p
    return None


def physical_cores():
    """Core fisici: la regola pratica per i thread di ggml."""
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


def ensure_user_model_dir():
    """Crea, se manca, la cartella in cui l'utente copia i modelli."""
    os.makedirs(USER_MODEL_DIR, exist_ok=True)
    return USER_MODEL_DIR


def clean_work_dir():
    """Cancella i file di lavoro (all'avvio e alla chiusura): contengono i
    prompt e le immagini non salvate dell'utente."""
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


# ── modelli ─────────────────────────────────────────────────────────────────
# Ruolo di un file dal suo nome. I nomi sono quelli con cui i componenti si
# distribuiscono di solito, come negli esempi della documentazione di
# stable-diffusion.cpp (docs/models/): ae.safetensors (o ae.sft) e' il VAE
# di FLUX.1 e Z-Image, flux2_ae quello di FLUX.2, clip_l e t5xxl i
# codificatori di FLUX.1 e SD3, qwen_3_4b quello di Z-Image e FLUX.2-klein,
# Qwen3-VL-...-mmproj la parte visiva del codificatore di Fibo...
# L'ordine conta: vince la prima regola che corrisponde.
_W = r"(^|[^a-z])"                     # inizio di parola
_E = r"([^a-z]|$)"                     # fine di parola
_ROLE_RULES = (
    ("skip", re.compile(_W + r"(taesd|taef1|taef2|tae|lora|controlnet|esrgan|upscaler?|"
                        r"embedding|pulid|photomaker|adetailer)" + _E)),
    ("uncond-diffusion-model", re.compile(_W + r"uncond")),
    ("embeddings-connectors", re.compile(r"connector")),
    ("tokenizer", re.compile(_W + r"tokenizer")),
    ("llm_vision", re.compile(_W + r"mmproj")),
    ("vae", re.compile(_W + r"(vae|ae)" + _E)),
    ("clip_l", re.compile(r"clip[_-]?(l|vit[_-]?l)" + _E)),
    ("clip_g", re.compile(r"clip[_-]?(g|vit[_-]?(g|bigg))" + _E)),
    ("t5xxl", re.compile(_W + r"(u?mt5|t5[_-]?(xxl|v1|base)?)" + _E)),
    # Codificatori con un nome che si confonderebbe con il modello.
    ("llm", re.compile(r"ling[_-]?mini|text[_-]?encoder|ovis[_-]?2|ministral|gpt[_-]?oss")),
    # Modelli di diffusione con il nome di un modello linguistico dentro
    # (qwen-image, ming-image): sono il modello principale.
    ("", re.compile(r"(qwen|z|ovis|ming|minimax[_-]?h3|p[_-]?h3)[-_ ]?image")),
    ("llm", re.compile(r"qwen|gemma|mistral|llama|llm|phi[-_]?\d")),
)
# Ruolo -> opzione di sd-cli (--<ruolo>), nell'ordine in cui si passano.
COMPONENT_ROLES = ("vae", "clip_l", "clip_g", "t5xxl", "llm", "llm_vision", "tokenizer",
                   "embeddings-connectors", "uncond-diffusion-model")
# Questi da soli non fanno di una cartella un modello in piu' file.
_ACCESSORY_ROLES = ("llm_vision", "tokenizer")


def file_role(name):
    """Uno dei COMPONENT_ROLES, "skip" (file da non usare: LoRA, ControlNet,
    anteprime...) oppure "" per un modello di diffusione o completo."""
    stem = os.path.splitext(os.path.basename(name).lower())[0]
    for role, rule in _ROLE_RULES:
        if rule.search(stem):
            return role
    return ""


def is_model_file(name):
    low = name.lower()
    if low.startswith("."):
        return False
    # Il tokenizzatore di alcuni modelli (Lens, MOSS, Ming) e' un .json.
    return low.endswith(MODEL_EXTENSIONS) or (low.startswith("tokenizer") and
                                              low.endswith(".json"))


def safetensors_keys(path):
    """Nomi dei tensori di un .safetensors, letti dall'intestazione (i primi
    8 byte dicono quanto e' lunga, poi c'e' un JSON). None se il file non
    si legge o non e' un .safetensors."""
    try:
        with open(path, "rb") as f:
            raw = f.read(8)
            if len(raw) != 8:
                return None
            (size,) = struct.unpack("<Q", raw)
            if not 2 <= size <= MAX_HEADER:
                return None
            header = json.loads(f.read(size).decode("utf-8"))
    except (OSError, ValueError, UnicodeDecodeError):
        return None
    if not isinstance(header, dict):
        return None
    return [k for k in header if k != "__metadata__"]


def checkpoint_info(path):
    """(completo, famiglia) di un file: completo e' True se il file contiene
    anche VAE e codificatore di testo, False se e' solo il modello di
    diffusione, None se non si sa (.gguf e .ckpt). La famiglia ("sd1",
    "sdxl", "sd3", "flux", "") aiuta a scegliere dimensione e passi."""
    keys = safetensors_keys(path) if path.lower().endswith((".safetensors", ".sft")) else None
    if keys is None:
        return None, ""
    # Completo: modello di diffusione con codificatore di testo o VAE. Un
    # VAE da solo o un codificatore da solo non hanno model.diffusion_model.
    diffusion = any(k.startswith("model.diffusion_model.") for k in keys)
    full = diffusion and any(k.startswith(("first_stage_model.", "vae.", "cond_stage_model.",
                                           "conditioner.", "text_encoders.")) for k in keys)
    if any(k.startswith("conditioner.embedders.1") for k in keys):
        family = "sdxl"
    elif any(k.startswith("cond_stage_model.") for k in keys):
        family = "sd1"
    elif any("joint_blocks." in k for k in keys):
        family = "sd3"
    elif any("double_blocks." in k for k in keys):
        family = "flux"
    else:
        family = ""
    return full, family


def _size(path):
    try:
        return os.path.getsize(path)
    except OSError:
        return 0


@dataclass
class Model:
    """Un modello per immagini: un file completo o una cartella di file."""
    name: str
    main: str                          # modello completo o di diffusione
    full: bool                         # True: -m; False: --diffusion-model
    family: str = ""                   # dall'intestazione del file, se si sa
    folder: str = ""                   # cartella del modello in piu' file
    parts: dict = field(default_factory=dict)      # ruolo -> percorso

    @property
    def key(self):
        """Cio' che si salva nelle impostazioni."""
        return self.main

    def label(self):
        """Nome della cartella e del file, in minuscolo: da qui si
        riconosce il modello."""
        return (self.name + " " + os.path.basename(self.main)).lower()

    def args(self):
        args = ["-m" if self.full else "--diffusion-model", self.main]
        for role in COMPONENT_ROLES:
            if self.parts.get(role):
                args += [f"--{role}", self.parts[role]]
        return args

    def guess_family(self):
        return recommended(self)["family"]


def scan_folder(folder, recursive=True):
    """Modelli di una cartella. Se la cartella contiene componenti (VAE,
    codificatori di testo) e' UN modello in piu' file, che prende il nome
    dalla cartella; altrimenti ogni file e' un modello completo. Le
    sottocartelle si guardano allo stesso modo, una per una."""
    try:
        entries = sorted(os.scandir(folder), key=lambda e: e.name.lower())
    except OSError:
        return []
    files, subdirs = [], []
    for e in entries:
        if e.name.startswith("."):
            continue
        try:
            if e.is_dir():
                subdirs.append(e.path)
            elif e.is_file() and is_model_file(e.name):
                files.append(e.path)
        except OSError:
            continue
    models = []
    parts, mains = {}, []
    for p in files:
        role = file_role(p)
        if p.lower().endswith(".json") and role != "tokenizer":
            continue
        if role in COMPONENT_ROLES and role != "tokenizer" and checkpoint_info(p)[0]:
            role = ""                  # "...0.9vae.safetensors": e' un modello completo
        if role in COMPONENT_ROLES:
            # Due file per lo stesso ruolo: il piu' grande (di solito il
            # piu' preciso, per esempio fp16 invece di fp8).
            if role not in parts or _size(p) > _size(parts[role]):
                parts[role] = p
        elif role == "":
            mains.append(p)
    if mains and any(r not in _ACCESSORY_ROLES for r in parts):
        main = max(mains, key=lambda p: (_size(p), p))
        full, family = checkpoint_info(main)
        models.append(Model(name=os.path.basename(os.path.normpath(folder)), main=main,
                            full=bool(full), family=family, folder=folder, parts=parts))
    else:
        for p in mains:
            full, family = checkpoint_info(p)
            # .gguf e .ckpt da soli: un file che si usa da solo e' completo.
            models.append(Model(name=os.path.splitext(os.path.basename(p))[0], main=p,
                                full=full is not False, family=family))
    if recursive:
        for d in subdirs:
            models += scan_folder(d, recursive=True)
    return models


def find_models(extra_folders=()):
    """Modelli delle cartelle dei modelli e delle cartelle aggiunte
    dall'utente, senza doppioni, in ordine di nome."""
    seen, result = set(), []
    for d in tuple(MODEL_DIRS) + tuple(extra_folders):
        if not d or not os.path.isdir(d):
            continue
        for m in scan_folder(d):
            if m.main not in seen:
                seen.add(m.main)
                result.append(m)
    result.sort(key=lambda m: (m.name.lower(), m.main))
    return result


# ── valori consigliati ──────────────────────────────────────────────────────
# Dagli esempi di docs/models/ di stable-diffusion.cpp (master-1106), che
# sono i valori con cui gli autori provano ogni modello. Si riconoscono dal
# nome della cartella e del file; la prima regola che corrisponde vince.
#   steps   passi (20 e' il valore predefinito di sd-cli quando la
#           documentazione non ne indica)
#   cfg     scala CFG; None: non si passa e decide il motore
#   sampler campionatore consigliato ("" = quello del motore)
#   extra   opzioni che il modello richiede (--flow-shift, --sigmas...)
#   fixed   modello distillato: i passi sono quelli, la Qualita' non li
#           cambia (con meno passi l'immagine si rovina, con piu' non migliora)
def _p(family, steps=20, cfg=None, sampler="", extra=(), fixed=False, side=1024):
    return {"family": family, "side": side, "steps": steps, "cfg": cfg,
            "sampler": sampler, "extra": list(extra), "fixed": fixed}


PROFILES = (
    (r"flux[-_.]?3.*base", _p("flux3", 20, 3.5, "euler")),
    (r"flux[-_.]?3", _p("flux3", 16, 1.0, "euler", fixed=True)),
    (r"flux[-_.]?2.*klein.*base", _p("flux2", 20, 4.0)),
    (r"flux[-_.]?2.*klein", _p("flux2", 4, 1.0, fixed=True)),
    (r"flux[-_.]?2", _p("flux2", 20, 1.0, "euler")),
    (r"schnell", _p("flux", 4, 1.0, "euler", fixed=True)),
    (r"chroma.*radiance", _p("chroma", 20, 4.0, "euler")),
    (r"chroma", _p("chroma", 20, 4.0, "euler", ["--model-args", "chroma_use_dit_mask=false"])),
    (r"z[-_ ]?image.*turbo", _p("zimage", 8, 1.0, fixed=True)),
    (r"z[-_ ]?image", _p("zimage", 20, 5.0)),
    (r"qwen[-_ ]?image[-_ ]?2[._]?1", _p("qwen", 20, 6.0, "euler")),
    (r"qwen[-_ ]?image", _p("qwen", 20, 2.5, "euler", ["--flow-shift", "3"])),
    (r"longcat", _p("longcat", 20, 5.0, "euler", ["--flow-shift", "3"])),
    (r"ovis", _p("ovis", 20, 5.0)),
    (r"(^|[^a-z])anima([^a-z]|$)", _p("anima", 20, 6.0, "euler")),
    (r"ernie.*turbo", _p("ernie", 8, 1.0, fixed=True)),
    (r"ernie", _p("ernie", 20, 5.0)),
    (r"fibo", _p("fibo", 20, 5.0, "euler")),
    (r"(^|[^a-z])lens.*turbo", _p("lens", 4, 1.0, fixed=True)),
    (r"(^|[^a-z])lens([^a-z]|$)", _p("lens", 20, 5.0)),
    (r"mage[-_ ]?flow", _p("mageflow", 4, 1.0, fixed=True)),
    (r"ming[-_ ]?image", _p("ming", 12, 1.0, "euler", fixed=True)),
    (r"minimax[-_ ]?h3", _p("minimax", 6, 1.0, "euler",
                            ["--sigmas", "minimax-h3-image", "--rng", "cpu"], fixed=True)),
    (r"moss", _p("moss", 20, 3.0)),
    (r"sefi.*turbo", _p("sefi", 4, 1.0, fixed=True)),
    (r"sefi", _p("sefi", 50, 4.0)),
    (r"pixart", _p("pixart", 20, 4.5)),
    (r"krea", _p("krea")),
    (r"(^|[^a-z])iris[-_ ]?\d", _p("iris", 20, 3.0)),
    (r"sd[-_ ]?3|stable[-_ ]?diffusion[-_ ]?3", _p("sd3", 28, 4.5, "euler")),
    (r"flux", _p("flux", 20, 1.0, "euler")),
)
PROFILES = tuple((re.compile(rule), profile) for rule, profile in PROFILES)

# Famiglie riconosciute dall'intestazione o dai componenti, quando il nome
# non dice niente.
FAMILY_PROFILES = {
    "sd1": _p("sd1", 25, 7.0, side=512),
    "sdxl": _p("sdxl", 25, 6.0),
    "sd3": _p("sd3", 28, 4.5, "euler"),
    "flux": _p("flux", 20, 1.0, "euler"),
    "dit": _p("dit"),                  # modello recente con codificatore LLM
}
# SD 1.x e SDXL distillati (SD-Turbo, SDXL-Lightning, LCM...).
_FAST_RE = re.compile(r"turbo|lightning|hyper|lcm|flash|distill|dmd|(^|[^a-z])tcd")


def recommended(model):
    """Valori consigliati per un modello: {"family", "side", "steps", "cfg",
    "sampler", "extra", "fixed"}."""
    low = model.label()
    # Un SD 1.x o SDXL completo si riconosce con certezza dai tensori: il
    # nome conta solo per i modelli che il file non dice (fluxmania-xl...).
    if not (model.full and model.family in ("sd1", "sdxl")):
        for rule, profile in PROFILES:
            if rule.search(low):
                return dict(profile, extra=list(profile["extra"]))
    family = model.family
    if not family:
        if model.parts.get("llm"):
            family = "dit"
        elif model.parts.get("clip_g") and model.parts.get("t5xxl"):
            family = "sd3"
        elif model.parts.get("t5xxl"):
            family = "flux"
        elif re.search(r"xl|pony|illustrious|noob", low):
            family = "sdxl"
        elif re.search(r"(^|[^0-9])(1[._]?5|v1|sd15|2[._]?1)([^0-9]|$)", low):
            family = "sd1"
        else:
            family = "sdxl" if _size(model.main) > 4 * 1024 ** 3 else "sd1"
    profile = dict(FAMILY_PROFILES[family])
    profile["extra"] = []
    if family in ("sd1", "sdxl") and _FAST_RE.search(low):
        profile.update(steps=4, cfg=1.0, fixed=True)
    return profile


def image_size(side, aspect):
    """Larghezza e altezza a multipli di 64, con circa side × side pixel."""
    ratio = ASPECTS.get(aspect, 1.0)
    w = side * ratio ** 0.5
    h = side / ratio ** 0.5
    return max(64, int(round(w / 64)) * 64), max(64, int(round(h / 64)) * 64)


def recommended_steps(rec, quality):
    """Passi consigliati con la Qualita' scelta."""
    if rec["fixed"]:
        return rec["steps"]
    return max(1, round(rec["steps"] * QUALITY.get(quality, 1.0)))


@dataclass
class Job:
    prompt: str
    negative: str = ""
    width: int = 512
    height: int = 512
    steps: int = 20
    cfg: float = None                  # None: decide il motore
    seed: int = -1
    count: int = 1
    sampler: str = ""
    extra: list = field(default_factory=list)


def make_job(model, prompt, settings):
    """Il lavoro da fare, dalle impostazioni di RuscaLLama (chiavi img_*):
    0 o "" vuol dire «consigliato per il modello»."""
    rec = recommended(model)
    side = int(settings.get("img_side") or rec["side"])
    width, height = image_size(side, settings.get("img_aspect", "square"))
    steps = int(settings.get("img_steps") or 0)
    if steps <= 0:
        steps = recommended_steps(rec, settings.get("img_quality"))
    cfg = float(settings.get("img_cfg") or 0) or rec["cfg"]
    seed = int(settings.get("img_seed", -1))
    if seed < 0:
        seed = random.randint(0, 2 ** 31 - 1)
    sampler = settings.get("img_sampler") or ""
    if sampler not in SAMPLERS:
        sampler = rec["sampler"]
    return Job(prompt=prompt.strip(), negative=(settings.get("img_negative") or "").strip(),
               width=width, height=height, steps=steps, cfg=cfg, seed=seed,
               count=max(1, min(MAX_COUNT, int(settings.get("img_count") or 1))),
               sampler=sampler, extra=rec["extra"])


# ── schede grafiche ─────────────────────────────────────────────────────────
# sd-cli --list-devices scrive una scheda per riga, "nome<TAB>descrizione";
# il nome (Vulkan0, Vulkan1...) e' quello che vuole --backend. Si salva la
# descrizione, non il nome, che puo' cambiare se cambiano schede o driver.
def parse_devices(text):
    devices, seen = [], collections.Counter()
    for line in text.splitlines():
        name, sep, desc = line.partition("\t")
        name, desc = name.strip(), desc.strip()
        if not sep or not name or name.lower().startswith("cpu"):
            continue
        desc = desc or name
        seen[desc] += 1
        label = desc if seen[desc] == 1 else f"{desc} ({seen[desc]})"
        devices.append({"name": name, "label": label})
    return devices


def list_devices(timeout=30):
    """Schede grafiche viste dal motore. Puo' servire qualche secondo (Vulkan
    si inizializza): va chiamata fuori dal thread dell'interfaccia."""
    binary = find_binary()
    if not binary:
        return []
    try:
        r = subprocess.run([binary, "--list-devices"], stdin=subprocess.DEVNULL,
                           capture_output=True, text=True, timeout=timeout)
    except (OSError, subprocess.SubprocessError):
        return []
    return parse_devices(r.stdout or "")


def device_backend(label, devices):
    for d in devices:
        if label and d["label"] == label:
            return d["name"]
    return None


# ── comando ─────────────────────────────────────────────────────────────────
def backend_assignment(device=None, te_device=None):
    """Valore di --backend (o None per la scelta del motore).

    device: scheda di tutto il lavoro (Vulkan0...), None per la scelta del
    motore (la scheda dedicata con piu' memoria libera). te_device: dove va
    il codificatore di testo, se non sulla stessa scheda: un'altra scheda o
    "cpu". Il codificatore lavora una volta per immagine ma pesa molto
    (Qwen3-4B, T5...): spostandolo, la scheda principale resta tutta per il
    modello di diffusione, che lavora a ogni passo. Gli altri moduli (VAE,
    diffusione) restano a device o alla scelta del motore, che rispetta le
    assegnazioni esplicite (docs/guides/backend.md di stable-diffusion.cpp)."""
    if te_device and te_device != device:
        return f"all={device},te={te_device}" if device else f"te={te_device}"
    return device or None


def build_command(binary, model, job, run_dir, threads=None, gpu=True, device=None,
                  low_memory=False, metadata=False, te_device=None):
    """Comando e ambiente per sd-cli. Scrive il prompt nei file di run_dir.
    device: nome --backend (Vulkan0...) o None per la scelta del motore;
    te_device: scheda o "cpu" per il codificatore di testo, None per la
    stessa di device."""
    prompt_file = os.path.join(run_dir, "prompt.txt")
    with open(prompt_file, "w", encoding="utf-8") as f:
        f.write(job.prompt)
    cmd = [binary] + model.args() + [
        "--prompt-file", prompt_file,
        "-W", str(job.width), "-H", str(job.height),
        "--steps", str(job.steps),
        "-s", str(job.seed), "-b", str(job.count),
        "-t", str(max(1, int(threads or physical_cores()))),
        "-o", os.path.join(run_dir, "image_%03d.png"),
        "--preview", "proj", "--preview-path", os.path.join(run_dir, "preview.png"),
        "--preview-interval", "1"]
    if job.negative:
        negative_file = os.path.join(run_dir, "negative.txt")
        with open(negative_file, "w", encoding="utf-8") as f:
            f.write(job.negative)
        cmd += ["--negative-prompt-file", negative_file]
    if job.cfg is not None:
        cmd += ["--cfg-scale", f"{job.cfg:g}"]
    if job.sampler:
        cmd += ["--sampling-method", job.sampler]
    cmd += list(job.extra)
    if low_memory:
        cmd += ["--vae-tiling", "--offload-to-cpu"]
    if not metadata:
        cmd.append("--disable-image-metadata")
    env = os.environ.copy()
    if not gpu:
        # Senza scheda grafica i driver Vulkan vengono nascosti: alcuni
        # driver si bloccano anche quando non si usano.
        cmd += ["--backend", "cpu"]
        env["VK_DRIVER_FILES"] = "/dev/null"
        env["VK_ICD_FILENAMES"] = "/dev/null"
    else:
        backend = backend_assignment(device, te_device)
        if backend:
            cmd += ["--backend", backend]
    return cmd, env


# ── avanzamento ─────────────────────────────────────────────────────────────
# sd-cli disegna una barra sullo standard output e la riscrive con "\r":
#   "  |=========>          | 4/20 - 1.52s/it"   passi della generazione
#   "  |#########           | 3/9 - 210.00MB/s"  caricamento dei pesi
_PROGRESS_RE = re.compile(r"\|([=#> ]{3,})\|\s*(\d+)/(\d+)")


def parse_progress(chunk):
    """("load" | "sample", passo, passi) dall'ultima barra di un pezzo di
    standard output, o None."""
    found = None
    for m in _PROGRESS_RE.finditer(chunk):
        stage = "load" if "#" in m.group(1) else "sample"
        found = (stage, int(m.group(2)), int(m.group(3)))
    return found


def collect_images(run_dir):
    """Immagini scritte da sd-cli, nell'ordine."""
    try:
        names = sorted(n for n in os.listdir(run_dir)
                       if n.startswith("image_") and n.endswith(".png"))
    except OSError:
        return []
    return [os.path.join(run_dir, n) for n in names
            if os.path.getsize(os.path.join(run_dir, n)) > 0]


# ── generazione ─────────────────────────────────────────────────────────────
class Generator:
    """Una generazione per volta. Le callback arrivano sempre nel thread
    dell'interfaccia (GLib.idle_add):
        on_progress(stage, step, steps)   "load" | "sample" | "decode"
        on_preview(data)                  byte PNG dell'anteprima
        on_log(line)                      righe scritte dal motore
        on_done(error, images, job)       error: None, "cancelled" o
                                          DiffusionError; images: percorsi
    """

    PREVIEW_POLL = 0.4                 # s

    def __init__(self, on_progress=None, on_preview=None, on_log=None, on_done=None):
        self.on_progress = on_progress or (lambda stage, step, steps: None)
        self.on_preview = on_preview or (lambda data: None)
        self.on_log = on_log or (lambda line: None)
        self.on_done = on_done or (lambda error, images, job: None)
        self._proc = None
        self._lock = threading.Lock()
        self._cancel = threading.Event()
        self._thread = None

    @property
    def running(self):
        return self._thread is not None and self._thread.is_alive()

    def start(self, model, job, threads=None, gpu=True, gpu_device="", low_memory=False,
              metadata=False, devices=None, te_device=""):
        """Avvia la generazione in background e ritorna subito. gpu_device:
        "label" di una scheda di list_devices(), o "" per la scelta del
        motore. te_device: dove va il codificatore di testo: "" sulla stessa
        scheda, "cpu" sul processore, o il "label" di un'altra scheda."""
        if self.running:
            return
        binary = find_binary()
        if not binary:
            raise DiffusionError("img_err_no_engine")
        missing = [p for p in [model.main] + list(model.parts.values()) if not os.path.isfile(p)]
        if missing:
            raise DiffusionError("img_err_no_model", missing[0])
        if not job.prompt:
            raise DiffusionError("img_err_no_prompt")
        self._cancel.clear()
        self._thread = threading.Thread(
            target=self._work, args=(binary, model, job, threads, gpu, gpu_device,
                                     low_memory, metadata, devices, te_device),
            daemon=True)
        self._thread.start()

    def cancel(self):
        """Ferma il motore; on_done arriva con "cancelled"."""
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

    def _work(self, binary, model, job, threads, gpu, gpu_device, low_memory, metadata,
              devices, te_device=""):
        error, images = None, []
        run_dir = None
        try:
            os.makedirs(WORK_DIR, mode=0o700, exist_ok=True)
            os.chmod(WORK_DIR, 0o700)
            os.chmod(os.path.dirname(WORK_DIR), 0o700)
            # Una cartella per generazione: le immagini restano li' finche'
            # la finestra le mostra.
            run_dir = tempfile.mkdtemp(prefix="run-", dir=WORK_DIR)
            device = te = None
            if gpu and (gpu_device or (te_device and te_device != "cpu")):
                if devices is None:
                    devices = list_devices()
            if gpu and gpu_device:
                device = device_backend(gpu_device, devices)
                self._emit(self.on_log, f"ruscallama: scheda «{gpu_device}» → "
                                        f"{device or 'non trovata, scelta automatica'}")
            if gpu and te_device:
                te = "cpu" if te_device == "cpu" else device_backend(te_device, devices)
                self._emit(self.on_log, f"ruscallama: codificatore di testo «{te_device}» → "
                                        f"{te or 'scheda non trovata, sulla stessa'}")
            cmd, env = build_command(binary, model, job, run_dir, threads, gpu, device,
                                     low_memory, metadata, te)
            code, tail = self._run(cmd, env, os.path.join(run_dir, "preview.png"), job)
            images = collect_images(run_dir)
            if code != 0 or not images:
                raise DiffusionError("img_err_engine", tail)
        except _Cancelled:
            error = "cancelled"
        except DiffusionError as e:
            error = "cancelled" if self._cancel.is_set() else e
        except OSError as e:
            error = DiffusionError("img_err_engine", str(e))
        finally:
            if run_dir:
                for name in ("prompt.txt", "negative.txt", "preview.png"):
                    try:
                        os.unlink(os.path.join(run_dir, name))
                    except OSError:
                        pass
                if error is not None:
                    shutil.rmtree(run_dir, ignore_errors=True)
                    images = []
        self._emit(self.on_done, error, images, job)

    def _run(self, cmd, env, preview_path, job):
        """Avvia sd-cli, segue avanzamento e anteprima e ne restituisce il
        codice di uscita e le ultime righe di errore."""
        shown = [a if not a.endswith((".txt",)) else os.path.basename(a) for a in cmd]
        self._emit(self.on_log, "$ " + " ".join(shown))
        try:
            proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                    stdin=subprocess.DEVNULL, env=env,
                                    start_new_session=True)
        except OSError as e:
            raise DiffusionError("img_err_start", str(e)) from e
        with self._lock:
            self._proc = proc
        tail = collections.deque(maxlen=12)
        done = threading.Event()
        state = {"sampled": False}

        def read_stderr():
            for raw in iter(proc.stderr.readline, b""):
                line = raw.decode("utf-8", "replace").rstrip("\r\n")
                if line.strip():
                    tail.append(line)
                    self._emit(self.on_log, line)
                low = line.lower()
                if state["sampled"] and ("decod" in low or "vae" in low):
                    self._emit(self.on_progress, "decode", 0, 0)

        def watch_preview():
            last = None
            while not done.wait(self.PREVIEW_POLL):
                try:
                    st = os.stat(preview_path)
                except OSError:
                    continue
                stamp = (st.st_mtime_ns, st.st_size)
                if stamp == last or st.st_size == 0:
                    continue
                # Il motore riscrive il file a ogni passo: si legge solo
                # quando ha smesso di crescere, e si passano i byte (il file
                # puo' cambiare subito dopo).
                time.sleep(0.05)
                try:
                    with open(preview_path, "rb") as f:
                        data = f.read()
                except OSError:
                    continue
                if len(data) == st.st_size and data[:8] == b"\x89PNG\r\n\x1a\n":
                    last = stamp
                    self._emit(self.on_preview, data)

        readers = [threading.Thread(target=read_stderr, daemon=True),
                   threading.Thread(target=watch_preview, daemon=True)]
        for t in readers:
            t.start()
        try:
            buf = ""
            while True:
                chunk = proc.stdout.read1(4096) if hasattr(proc.stdout, "read1") \
                    else proc.stdout.read(256)
                if not chunk:
                    break
                buf = (buf + chunk.decode("utf-8", "replace"))[-4096:]
                found = parse_progress(buf)
                if found:
                    stage, step, steps = found
                    if stage == "sample":
                        state["sampled"] = True
                    self._emit(self.on_progress, stage, step, steps)
                # Le righe complete (non le barre) vanno nel registro.
                *lines, buf = re.split(r"[\r\n]", buf)
                for line in lines:
                    line = re.sub(r"\x1b\[[0-9;]*[A-Za-z]", "", line).strip()
                    if line and not _PROGRESS_RE.search(line):
                        self._emit(self.on_log, line)
            code = proc.wait()
        finally:
            if proc.poll() is None:            # eccezione: non lasciarlo acceso
                try:
                    os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
                except OSError:
                    pass
                proc.wait()
            done.set()
            for t in readers:
                t.join(5)
            proc.stdout.close()
            proc.stderr.close()
            with self._lock:
                self._proc = None
        if self._cancel.is_set():
            raise _Cancelled()
        return code, "\n".join(tail)


class _Cancelled(Exception):
    pass
