# -*- coding: utf-8 -*-
# rusca_diffusion.py — RuscaLinux OS Apps 1.99.3 — GPL-3.0-or-later
#
# Generazione delle immagini e dei video di RuscaLLama con
# ruscadiffusion-engine (sd-cli, cioe' stable-diffusion.cpp: software
# esterno, licenza MIT).
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
# I modelli per i video (Wan 2.1 e 2.2, HunyuanVideo 1.5, LingBot-Video) sono
# cartelle come le altre, nelle stesse cartelle dei modelli: si riconoscono
# dal nome (PROFILES, "video": True) e li mostra solo la vista Video. sd-cli
# li usa con -M vid_gen e scrive un video AVI in Motion JPEG.
#
# Privacy e sicurezza (specifiche, sezione 11):
#   * nessun modulo di rete;
#   * sd-cli e' avviato con percorso assoluto e lista di argomenti, mai
#     tramite shell; il prompt non e' un argomento (lo vedrebbe chiunque
#     con ps) ma un file (--prompt-file) nella cartella di lavoro;
#   * cartella di lavoro ~/.cache/ruscallama/images con permessi 0700:
#     prompt, anteprime, immagini e video generati, immagine di partenza di
#     un video (una copia). Si cancella a ogni avvio e alla
#     chiusura: restano solo le immagini che l'utente salva altrove.
import collections
import dataclasses
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
# Durata di un video, in secondi (impostazione Durata della vista Video).
LENGTHS = {"short": 2, "normal": 3, "long": 5}
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
    ("skip", re.compile(_W + r"(taesd|taef1|taef2|taew\d(_\d)?|taehv|tae|lora|controlnet|"
                        r"esrgan|upscaler?|embedding|pulid|photomaker|adetailer)" + _E)),
    ("uncond-diffusion-model", re.compile(_W + r"uncond")),
    # Wan 2.2 A14B: due modelli, HighNoise (i primi passi) e LowNoise (il
    # modello principale, --diffusion-model).
    ("high-noise-diffusion-model", re.compile(r"high[-_ ]?noise")),
    # Wan 2.1 I2V: il codificatore dell'immagine di partenza.
    ("clip_vision", re.compile(r"clip[-_ ]?vision")),
    ("embeddings-connectors", re.compile(r"connector")),
    ("tokenizer", re.compile(_W + r"tokenizer")),
    ("llm_vision", re.compile(_W + r"mmproj")),
    ("vae", re.compile(_W + r"(vae|ae)" + _E)),
    ("clip_l", re.compile(r"clip[_-]?(l|vit[_-]?l)" + _E)),
    ("clip_g", re.compile(r"clip[_-]?(g|vit[_-]?(g|bigg))" + _E)),
    # umt5-xxl e' il codificatore di Wan, byt5 il secondo di HunyuanVideo.
    ("t5xxl", re.compile(_W + r"(u?mt5[_-]?(xxl)?|by?t5|t5[_-]?(xxl|v1|base)?)" + _E)),
    # Codificatori con un nome che si confonderebbe con il modello.
    ("llm", re.compile(r"ling[_-]?mini|text[_-]?encoder|ovis[_-]?2|ministral|gpt[_-]?oss")),
    # Modelli di diffusione con il nome di un modello linguistico dentro
    # (qwen-image, ming-image): sono il modello principale.
    ("", re.compile(r"(qwen|z|ovis|ming|minimax[_-]?h3|p[_-]?h3)[-_ ]?image")),
    ("llm", re.compile(r"qwen|gemma|mistral|llama|llm|phi[-_]?\d")),
)
# Ruolo -> opzione di sd-cli (--<ruolo>), nell'ordine in cui si passano.
COMPONENT_ROLES = ("vae", "clip_l", "clip_g", "t5xxl", "llm", "llm_vision", "tokenizer",
                   "embeddings-connectors", "uncond-diffusion-model",
                   "high-noise-diffusion-model", "clip_vision")
# Questi da soli non fanno di una cartella un modello in piu' file.
_ACCESSORY_ROLES = ("llm_vision", "tokenizer", "clip_vision")


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
    header_full: object = None         # True: completo secondo i tensori del file

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

    @property
    def video(self):
        """True per un modello che genera video (vista Video)."""
        return recommended(self)["video"]

    def missing(self):
        """Componenti che mancano a un modello in piu' file (VAE,
        codificatore...), per i modelli di cui si sa che cosa serve. Un file
        completo secondo i suoi tensori non ha bisogno di niente."""
        if self.header_full:
            return []
        need = REQUIRED_PARTS.get(recommended(self)["family"], ())
        return [role for role in need if not self.parts.get(role)]


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
        # I file messi direttamente nella cartella dei modelli: il nome e'
        # quello del file, non "models".
        name = os.path.basename(os.path.normpath(folder))
        if os.path.normpath(folder) in map(os.path.normpath, MODEL_DIRS):
            name = os.path.splitext(os.path.basename(main))[0]
        models.append(Model(name=name, main=main, full=bool(full), family=family,
                            folder=folder, parts=parts, header_full=full))
    else:
        for p in mains:
            full, family = checkpoint_info(p)
            # .gguf e .ckpt da soli: un file che si usa da solo e' completo.
            models.append(Model(name=os.path.splitext(os.path.basename(p))[0], main=p,
                                full=full is not False, family=family, header_full=full))
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
# sono i valori con cui gli autori provano ogni modello; i passi, quando
# quegli esempi non li indicano, dalla scheda del modello (ERNIE-Image 50,
# Qwen-Image-2.1 40). Si riconoscono dal
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
            "sampler": sampler, "extra": list(extra), "fixed": fixed,
            "video": False, "fps": 0, "init": "", "high_steps": 0, "negative": ""}


# Il prompt negativo predefinito di Wan (dal codice di Wan, in cinese come lo
# ha addestrato Alibaba; lo usano anche gli esempi di stable-diffusion.cpp):
# colori sgargianti, sovraesposizione, immagine statica, dettagli sfocati,
# sottotitoli, peggiore qualita', artefatti JPEG, mani e volti deformi, dita
# fuse, sfondo disordinato, tre gambe, folla, camminare all'indietro.
WAN_NEGATIVE = ("色调艳丽，过曝，静态，细节模糊不清，字幕，风格，作品，画作，画面，静止，整体发灰，"
                "最差质量，低质量，JPEG压缩残留，丑陋的，残缺的，多余的手指，画得不好的手部，"
                "画得不好的脸部，畸形的，毁容的，形态畸形的肢体，手指融合，静止不动的画面，"
                "杂乱的背景，三条腿，背景人很多，倒着走")


def _v(family, steps=20, cfg=6.0, sampler="euler", extra=("--flow-shift", "3"), fps=16,
       init="", high_steps=0, negative="", side=640):
    """Profilo di un modello per i video. fps: fotogrammi al secondo con cui
    il modello e' addestrato (Wan 2.1 16, Wan 2.2 TI2V 5B 24). init:
    "required" se serve un'immagine di partenza (I2V), "optional" se si puo'
    dare (TI2V), "" se non si usa. side 640: circa 480p, la risoluzione che
    una scheda di casa regge (Wan ne fa anche 720p, con tempi molto piu'
    lunghi)."""
    return dict(_p(family, steps, cfg, sampler, extra, side=side), video=True, fps=fps,
                init=init, high_steps=high_steps, negative=negative)


# Modelli per i video che sd-cli sa usare ma che chiedono un ingresso che
# RuscaLLama non ha (audio, video da modificare, ultimo fotogramma): si
# mostrano nella vista Video con un avviso.
_UNSUPPORTED_VIDEO = re.compile(r"(^|[^a-z])(s2v|vace|flf2v|animate|fun)([^a-z]|$)")


PROFILES = (
    # ── video (docs/models/wan.md, hunyuan_video.md, lingbot_video.md) ──
    # Wan 2.2 A14B: 10 passi del modello LowNoise e 8 del HighNoise, CFG 3.5.
    (r"(^|[^a-z])wan.*2[._]?2.*(a14b|14b).*(i2v)", _v("wan22_14b", 10, 3.5, init="required",
                                                       high_steps=8, negative=WAN_NEGATIVE)),
    (r"(^|[^a-z])wan.*2[._]?2.*(a14b|14b)", _v("wan22_14b", 10, 3.5, high_steps=8,
                                                negative=WAN_NEGATIVE)),
    (r"(^|[^a-z])wan.*2[._]?2.*(5b|ti2v)|ti2v", _v("wan22_5b", fps=24, init="optional",
                                                   negative=WAN_NEGATIVE)),
    (r"(^|[^a-z])wan.*i2v", _v("wan21_i2v", init="required", negative=WAN_NEGATIVE)),
    (r"(^|[^a-z])wan[-_ .]?\d|(^|[^a-z])wan([^a-z]|$)", _v("wan21", negative=WAN_NEGATIVE)),
    (r"hunyuan[-_ ]?video.*i2v", _v("hunyuanvideo", 20, 6.0, extra=["--vae-tiling"], fps=24,
                                    init="required")),
    (r"hunyuan[-_ ]?video", _v("hunyuanvideo", 20, 6.0, extra=["--vae-tiling"], fps=24)),
    (r"lingbot", _v("lingbot", 20, 3.0, sampler="", extra=())),
    # ── immagini ──
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
    (r"qwen[-_ ]?image[-_ ]?2[._]?1.*turbo", _p("qwen", 8, 1.0, "euler",
                                                ["--sigmas", "qwen-image-2.1-turbo"],
                                                fixed=True)),
    # 40 passi: il valore predefinito della scheda del modello (Qwen).
    (r"qwen[-_ ]?image[-_ ]?2[._]?1", _p("qwen", 40, 6.0, "euler")),
    (r"qwen[-_ ]?image", _p("qwen", 20, 2.5, "euler", ["--flow-shift", "3"])),
    (r"longcat", _p("longcat", 20, 5.0, "euler", ["--flow-shift", "3"])),
    (r"ovis", _p("ovis", 20, 5.0)),
    (r"(^|[^a-z])anima([^a-z]|$)", _p("anima", 20, 6.0, "euler")),
    (r"ernie.*turbo", _p("ernie", 8, 1.0, fixed=True)),
    # 50 passi: il valore indicato da Baidu per ERNIE-Image (non Turbo).
    (r"ernie", _p("ernie", 50, 5.0)),
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
                profile = dict(profile, extra=list(profile["extra"]))
                if profile["video"] and _UNSUPPORTED_VIDEO.search(low):
                    profile["family"] = "unsupported"
                # Wan 2.2 A14B riconosciuto dal secondo modello, non dal nome.
                if profile["family"] in ("wan21", "wan21_i2v") and model.parts.get(
                        "high-noise-diffusion-model"):
                    return recommended_for("wan22_14b", profile["init"])
                return profile
    if model.parts.get("high-noise-diffusion-model"):
        return recommended_for("wan22_14b")
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


def recommended_for(family, init=""):
    """Il profilo di una famiglia di PROFILES (per Wan 2.2 A14B riconosciuto
    dal file HighNoise)."""
    found = [p for _, p in PROFILES if p["family"] == family]
    profile = next((p for p in found if p["init"] == init), found[0])
    return dict(profile, extra=list(profile["extra"]))


# Che cosa serve, oltre al modello di diffusione, ai modelli che si
# distribuiscono in piu' file (docs/models/ di stable-diffusion.cpp).
REQUIRED_PARTS = {
    "wan21": ("vae", "t5xxl"), "wan21_i2v": ("vae", "t5xxl", "clip_vision"),
    "wan22_5b": ("vae", "t5xxl"),
    "wan22_14b": ("vae", "t5xxl", "high-noise-diffusion-model"),
    "hunyuanvideo": ("vae", "llm", "t5xxl"), "lingbot": ("vae", "llm"),
    "zimage": ("vae", "llm"), "ernie": ("vae", "llm"), "flux2": ("vae", "llm"),
    "flux3": ("vae", "llm"), "qwen": ("vae", "llm"), "chroma": ("vae", "t5xxl"),
    "flux": ("vae", "clip_l", "t5xxl"),
}

# Modelli consigliati, con i file da scaricare (pagine della documentazione di
# stable-diffusion.cpp): li mostra la guida «Quali file scaricare?».
GUIDE = (
    {"name": "ERNIE-Image-Turbo", "desc": "img_guide_ernie", "files": (
        ("model", "ERNIE-Image-Turbo-Q4_K_M.gguf",
         "https://huggingface.co/unsloth/ERNIE-Image-Turbo-GGUF/tree/main"),
        ("llm", "Ministral-3-3B-Instruct-2512-Q8_0.gguf",
         "https://huggingface.co/unsloth/Ministral-3-3B-Instruct-2512-GGUF/tree/main"),
        ("vae", "vae/*.safetensors",
         "https://huggingface.co/Comfy-Org/ERNIE-Image/tree/main/vae"))},
    {"name": "Z-Image-Turbo", "desc": "img_guide_zimage", "files": (
        ("model", "z_image_turbo-Q4_0.gguf",
         "https://huggingface.co/leejet/Z-Image-Turbo-GGUF/tree/main"),
        ("llm", "Qwen3-4B-Instruct-2507-Q4_K_M.gguf",
         "https://huggingface.co/unsloth/Qwen3-4B-Instruct-2507-GGUF/tree/main"),
        # Lo stesso autoencoder di FLUX.1, ma senza registrazione: il
        # repository di black-forest-labs chiede di accedere e accettare la licenza.
        ("vae", "ae.safetensors",
         "https://huggingface.co/Comfy-Org/z_image_turbo/tree/main/split_files/vae"))},
)

# Modelli per i video consigliati (vista Video, «Quali file scaricare?»).
VIDEO_GUIDE = (
    {"name": "Wan2.2-TI2V-5B", "desc": "vid_guide_wan22", "files": (
        ("model", "Wan2.2-TI2V-5B-Q5_K_M.gguf",
         "https://huggingface.co/QuantStack/Wan2.2-TI2V-5B-GGUF/tree/main"),
        ("t5xxl", "umt5-xxl-encoder-Q8_0.gguf",
         "https://huggingface.co/city96/umt5-xxl-encoder-gguf/tree/main"),
        ("vae", "wan2.2_vae.safetensors",
         "https://huggingface.co/Comfy-Org/Wan_2.2_ComfyUI_Repackaged/tree/main/split_files/vae"))},
    {"name": "Wan2.1-T2V-1.3B", "desc": "vid_guide_wan21", "files": (
        ("model", "wan2.1_t2v_1.3B_fp16.safetensors",
         "https://huggingface.co/Comfy-Org/Wan_2.1_ComfyUI_repackaged/tree/main/"
         "split_files/diffusion_models"),
        ("t5xxl", "umt5-xxl-encoder-Q8_0.gguf",
         "https://huggingface.co/city96/umt5-xxl-encoder-gguf/tree/main"),
        ("vae", "wan_2.1_vae.safetensors",
         "https://huggingface.co/Comfy-Org/Wan_2.1_ComfyUI_repackaged/tree/main/split_files/vae"))},
)

# Cartelle dei modelli della chat: chi copia li' un modello per immagini non
# lo trova nella vista Immagini.
CHAT_MODEL_DIRS = ("/usr/share/ruscallama/models",
                   os.path.join(GLib.get_user_data_dir(), "ruscallama", "models"))
_DIFFUSION_HINT = re.compile(r"(z|qwen|ernie|ovis|ming)[-_ ]?image|flux|chroma|sd[-_]?xl|"
                             r"(^|[^a-z])wan[-_ .]?\d|hunyuan[-_ ]?video|lingbot|umt5|"
                             r"stable[-_ ]?diffusion|(^|[^a-z])sd[-_ ]?(1[._]?5|3)")


def misplaced_files(dirs=CHAT_MODEL_DIRS):
    """File che sembrano di un modello per immagini nelle cartelle dei
    modelli della chat (la chat usa solo .gguf linguistici)."""
    found = []
    for d in dirs:
        try:
            names = sorted(os.listdir(d))
        except OSError:
            continue
        for n in names:
            low = n.lower()
            if not is_model_file(n):
                continue
            stem = os.path.splitext(low)[0]
            if (low.endswith((".safetensors", ".sft", ".ckpt"))
                    or file_role(n) in ("vae", "clip_l", "clip_g", "t5xxl")
                    or _DIFFUSION_HINT.search(stem)):
                found.append(os.path.join(d, n))
    return found


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
    # Solo per i video:
    video: bool = False
    frames: int = 0                    # fotogrammi (4n+1, come vuole Wan)
    fps: int = 0
    init_image: str = ""               # immagine di partenza (I2V), o ""
    high_steps: int = 0                # passi del modello HighNoise (Wan 2.2 A14B)


def video_frames(seconds, fps):
    """Fotogrammi per una durata: 4n+1, il numero che vogliono i VAE video
    (Wan comprime 4 fotogrammi in uno, piu' il primo): 2 s a 16 fps = 33."""
    return 4 * max(1, round(seconds * fps / 4)) + 1


def make_job(model, prompt, settings, prefix="img_", init_image=""):
    """Il lavoro da fare, dalle impostazioni di RuscaLLama (chiavi img_* per
    le immagini, vid_* per i video): 0 o "" vuol dire «consigliato per il
    modello». init_image: immagine di partenza di un video."""
    def get(key, default=None):
        return settings.get(prefix + key, default)

    rec = recommended(model)
    side = int(get("side") or rec["side"])
    width, height = image_size(side, get("aspect", "square"))
    steps = int(get("steps") or 0)
    if steps <= 0:
        steps = recommended_steps(rec, get("quality"))
    cfg = float(get("cfg") or 0) or rec["cfg"]
    seed = int(get("seed", -1))
    if seed < 0:
        seed = random.randint(0, 2 ** 31 - 1)
    sampler = get("sampler") or ""
    if sampler not in SAMPLERS:
        sampler = rec["sampler"]
    negative = (get("negative") or "").strip()
    job = Job(prompt=prompt.strip(), negative=negative, width=width, height=height,
              steps=steps, cfg=cfg, seed=seed,
              count=max(1, min(MAX_COUNT, int(get("count") or 1))),
              sampler=sampler, extra=rec["extra"])
    if rec["video"]:
        job.video, job.count = True, 1
        job.fps = rec["fps"] or 16
        job.frames = video_frames(LENGTHS.get(get("length"), LENGTHS["short"]), job.fps)
        job.negative = negative or rec["negative"]
        job.init_image = init_image if rec["init"] else ""
        if rec["high_steps"]:
            job.high_steps = (rec["high_steps"] if steps == rec["steps"] else
                              max(1, round(rec["high_steps"] * steps / rec["steps"])))
    return job


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
    cmd = [binary]
    if job.video:
        cmd += ["-M", "vid_gen"]
    cmd += model.args() + [
        "--prompt-file", prompt_file,
        "-W", str(job.width), "-H", str(job.height),
        "--steps", str(job.steps),
        "-s", str(job.seed),
        "-t", str(max(1, int(threads or physical_cores())))]
    if job.video:
        # Il video e' un AVI in Motion JPEG (sd-cli e' compilato senza
        # WebM); l'anteprima di un video e' anch'essa un AVI, dei
        # fotogrammi ancora rumorosi.
        cmd += ["--video-frames", str(job.frames), "--fps", str(job.fps),
                "-o", os.path.join(run_dir, "video.avi"),
                "--preview", "proj", "--preview-path", os.path.join(run_dir, "preview.avi"),
                "--preview-interval", "1"]
        if job.init_image:
            # Il motore ritaglia l'immagine al formato del video e la
            # ridimensiona; lanczos invece del predefinito "nearest", che
            # su una foto grande lascia scalini (docs/guides/image_preprocessing.md).
            cmd += ["-i", job.init_image, "--image-preprocess",
                    "target=init,mode=crop-resize,filter=lanczos,antialias=true"]
        if job.high_steps and model.parts.get("high-noise-diffusion-model"):
            cmd += ["--high-noise-steps", str(job.high_steps)]
            if job.cfg is not None:
                cmd += ["--high-noise-cfg-scale", f"{job.cfg:g}"]
            if job.sampler:
                cmd += ["--high-noise-sampling-method", job.sampler]
    else:
        cmd += ["-b", str(job.count), "-o", os.path.join(run_dir, "image_%03d.png"),
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
        cmd += [o for o in ("--vae-tiling", "--offload-to-cpu") if o not in cmd]
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


def collect_images(run_dir, video=False):
    """Immagini (o il video) scritte da sd-cli, nell'ordine."""
    prefix, ext = ("video", ".avi") if video else ("image_", ".png")
    try:
        names = sorted(n for n in os.listdir(run_dir)
                       if n.startswith(prefix) and n.endswith(ext))
    except OSError:
        return []
    return [os.path.join(run_dir, n) for n in names
            if os.path.getsize(os.path.join(run_dir, n)) > 0]


# ── video AVI ───────────────────────────────────────────────────────────────
# sd-cli scrive i video come AVI in Motion JPEG (examples/common/media_io.cpp):
# un'intestazione, poi la lista "movi" con un pezzo "00dc" per fotogramma,
# ognuno un'immagine JPEG intera. Per le miniature e per l'anteprima basta
# prenderne uno: non serve un decodificatore video.
def avi_frames(data):
    """I fotogrammi JPEG (byte) di un AVI Motion JPEG, nell'ordine."""
    start = data.find(b"movi")
    if start < 0 or data[:4] != b"RIFF":
        return []
    frames, pos = [], start + 4
    while pos + 8 <= len(data):
        fourcc = data[pos:pos + 4]
        (size,) = struct.unpack("<I", data[pos + 4:pos + 8])
        if fourcc in (b"idx1", b"LIST") or pos + 8 + size > len(data):
            break
        chunk = data[pos + 8:pos + 8 + size]
        if fourcc[2:] == b"dc" and chunk[:2] == b"\xff\xd8":
            frames.append(chunk)
        pos += 8 + size + (size & 1)
    return frames


def video_frame(source, where=0.5):
    """Un fotogramma JPEG di un video (percorso o byte): where 0 il primo,
    0.5 quello a meta', 1 l'ultimo. None se non si legge."""
    if isinstance(source, str):
        try:
            with open(source, "rb") as f:
                source = f.read()
        except OSError:
            return None
    frames = avi_frames(source)
    if not frames:
        return None
    return frames[min(len(frames) - 1, int(where * (len(frames) - 1) + 0.5))]


# ── generazione ─────────────────────────────────────────────────────────────
class Generator:
    """Una generazione per volta. Le callback arrivano sempre nel thread
    dell'interfaccia (GLib.idle_add):
        on_progress(stage, step, steps)   "load" | "sample" | "decode"
        on_preview(data)                  byte PNG (JPEG per un video)
                                          dell'anteprima
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
        if job.video and recommended(model)["family"] == "unsupported":
            raise DiffusionError("vid_err_unsupported")
        if job.video and recommended(model)["init"] == "required" and not job.init_image:
            raise DiffusionError("vid_err_need_image")
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
            if job.init_image:
                # Una copia nella cartella di lavoro: il motore legge solo li'
                # (e nelle cartelle dei modelli), non in tutta la home.
                ext = os.path.splitext(job.init_image)[1].lower()
                start = os.path.join(run_dir, "start" + (ext if ext in (
                    ".png", ".jpg", ".jpeg", ".webp", ".bmp") else ".png"))
                shutil.copyfile(job.init_image, start)
                job = dataclasses.replace(job, init_image=start)
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
            preview = os.path.join(run_dir, "preview.avi" if job.video else "preview.png")
            code, tail = self._run(cmd, env, preview, job)
            images = collect_images(run_dir, job.video)
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
                for name in ("prompt.txt", "negative.txt", "preview.png", "preview.avi"):
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
                if len(data) != st.st_size:
                    continue
                if preview_path.endswith(".avi"):
                    # Anteprima di un video: il fotogramma a meta'.
                    data = video_frame(data) if data[:4] == b"RIFF" else None
                    if data:
                        last = stamp
                        self._emit(self.on_preview, data)
                elif data[:8] == b"\x89PNG\r\n\x1a\n":
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
