"""RuscaLinux OS Tools — test della generazione di immagini di RuscaLLama —
1.99.3 — GPL-3.0

rusca_diffusion.py riconosce i modelli per immagini (un file solo o una
cartella di file), sceglie i valori consigliati, prepara il comando di
sd-cli (ruscadiffusion-engine) e ne segue l'avanzamento. Qui si controlla
tutto questo e l'intero percorso di una generazione, con un sd-cli finto
che scrive barre di avanzamento, anteprime e PNG veri: i test non hanno
bisogno né del motore né di un modello. Si lanciano dalla radice del
repository:
    python3 -m unittest tests/test_ruscallama_diffusion.py

rusca_diffusion.py usa GLib (PyGObject): senza, i test si saltano.
"""

import json
import os
import stat
import struct
import sys
import tempfile
import threading
import unittest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TOOL = os.path.join(REPO, "tools", "ruscallama")
sys.path.insert(0, TOOL)

try:
    from gi.repository import GLib
    import rusca_diffusion as rd
except (ImportError, ValueError):
    rd = None

# sd-cli finto: stesse opzioni, stesse barre (stable-diffusion.cpp
# master-1106, src/core/util.cpp), stessi nomi dei file d'uscita.
FAKE_SD = r'''#!/usr/bin/env python3
import os, struct, sys, time, zlib

def png(path, w, h, rgb):
    raw = b"".join(b"\x00" + bytes(rgb) * w for _ in range(h))
    def chunk(t, d):
        c = struct.pack(">I", len(d)) + t + d
        return c + struct.pack(">I", zlib.crc32(t + d) & 0xffffffff)
    with open(path, "wb") as f:
        f.write(b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0))
                + chunk(b"IDAT", zlib.compress(raw)) + chunk(b"IEND", b""))

a = sys.argv[1:]
if a == ["--list-devices"]:
    print("CPU\tFake CPU")
    print("Vulkan0\tFake GPU")
    print("Vulkan1\tFake GPU")
    sys.exit(0)
log = os.environ.get("FAKE_SD_LOG")
if log:
    with open(log, "w") as f:
        f.write("\n".join(a))
def opt(name, default=None):
    return a[a.index(name) + 1] if name in a else default
prompt = open(opt("--prompt-file")).read()
if os.environ.get("FAKE_SD_FAIL"):
    print("[ERROR] model.cpp:123 - load model failed", file=sys.stderr)
    sys.exit(1)
w, h = int(opt("-W", 512)) // 8, int(opt("-H", 512)) // 8
steps, count = int(opt("--steps", 4)), int(opt("-b", 1))
preview, out = opt("--preview-path"), opt("-o")
print("[INFO ] stable-diffusion.cpp:200 - loading model", file=sys.stderr, flush=True)
delay = float(os.environ.get("FAKE_SD_DELAY", "0"))
for i in range(1, 4):
    sys.stdout.write("\r  |" + "#" * (i * 16) + " " * (50 - i * 16) + f"| {i}/3 - 210.00MB/s\033[K")
    sys.stdout.flush()
    time.sleep(delay)
sys.stdout.write("\n")
for b in range(count):
    for s in range(1, steps + 1):
        png(preview, w, h, (s * 40 % 256, 80, 120))
        bar = "=" * (s * 50 // steps) + ">"
        sys.stdout.write(f"\r  |{bar[:50]:<50}| {s}/{steps} - 1.52s/it\033[K")
        sys.stdout.flush()
        time.sleep(delay)
    sys.stdout.write("\n")
    print("[INFO ] image.cpp:900 - decoding 1 latents", file=sys.stderr, flush=True)
for b in range(count):
    png(out.replace("%03d", f"{b:03d}"), w, h, (200, 100, b * 50))
print(f"[INFO ] main.cpp:540 - {count}/{count} images saved", file=sys.stderr)
'''


def write_safetensors(path, keys):
    """Un .safetensors minimo: intestazione con i nomi dei tensori, niente pesi."""
    header = {k: {"dtype": "F16", "shape": [0], "data_offsets": [0, 0]} for k in keys}
    header["__metadata__"] = {"format": "pt"}
    raw = json.dumps(header).encode()
    with open(path, "wb") as f:
        f.write(struct.pack("<Q", len(raw)) + raw)


SDXL_KEYS = ["model.diffusion_model.input_blocks.0.0.weight",
             "first_stage_model.decoder.conv_in.weight",
             "conditioner.embedders.0.transformer.text_model.embeddings.weight",
             "conditioner.embedders.1.model.token_embedding.weight"]
SD15_KEYS = ["model.diffusion_model.input_blocks.0.0.weight",
             "first_stage_model.decoder.conv_in.weight",
             "cond_stage_model.transformer.text_model.embeddings.weight"]
FLUX_KEYS = ["double_blocks.0.img_attn.proj.weight", "img_in.weight"]
VAE_KEYS = ["decoder.conv_in.weight", "encoder.conv_in.weight"]


@unittest.skipIf(rd is None, "serve PyGObject (GLib)")
class TestModels(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = self.tmp.name

    def tearDown(self):
        self.tmp.cleanup()

    def touch(self, rel, keys=None, size=0):
        path = os.path.join(self.dir, rel)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        if keys is not None:
            write_safetensors(path, keys)
        else:
            with open(path, "wb") as f:
                f.truncate(size)
        return path

    def test_roles(self):
        for name, role in (("ae.safetensors", "vae"), ("flux_vae.safetensors", "vae"),
                           ("qwen_image_vae.safetensors", "vae"),
                           ("clip_l.safetensors", "clip_l"), ("clip_g.safetensors", "clip_g"),
                           ("t5xxl_fp16.safetensors", "t5xxl"),
                           ("umt5-xxl-encoder-Q8_0.gguf", "t5xxl"),
                           ("qwen_3_4b.safetensors", "llm"),
                           ("Qwen2.5-VL-7B-Instruct-Q8_0.gguf", "llm"),
                           ("qwen-image-2512-Q4_K_M.gguf", ""),
                           ("z_image_turbo_bf16.safetensors", ""),
                           ("flux1-dev-Q8_0.gguf", ""), ("v1-5-pruned-emaonly.safetensors", ""),
                           ("taesd.safetensors", "skip"), ("my_lora.safetensors", "skip"),
                           ("Qwen3-VL-4B-Instruct-mmproj-BF16.gguf", "llm_vision"),
                           ("flux2_ae.safetensors", "vae"), ("ae.sft", "vae"),
                           ("ideogram4_uncond-Q8_0.gguf", "uncond-diffusion-model"),
                           ("animagine-xl-4.0.safetensors", "")):
            self.assertEqual(rd.file_role(name), role, name)

    def test_checkpoint_info(self):
        self.assertEqual(rd.checkpoint_info(self.touch("a.safetensors", SDXL_KEYS)), (True, "sdxl"))
        self.assertEqual(rd.checkpoint_info(self.touch("b.safetensors", SD15_KEYS)), (True, "sd1"))
        self.assertEqual(rd.checkpoint_info(self.touch("c.safetensors", FLUX_KEYS)), (False, "flux"))
        self.assertEqual(rd.checkpoint_info(self.touch("d.safetensors", VAE_KEYS)), (False, ""))
        self.assertEqual(rd.checkpoint_info(self.touch("e.gguf", size=10)), (None, ""))
        # File che non e' un .safetensors: niente eccezioni.
        bad = self.touch("f.safetensors", size=4)
        self.assertEqual(rd.checkpoint_info(bad), (None, ""))
        with open(bad, "wb") as f:
            f.write(struct.pack("<Q", 2 ** 60))
        self.assertIsNone(rd.safetensors_keys(bad))

    def test_scan_single_files_and_folders(self):
        self.touch("sd15.safetensors", SD15_KEYS)
        self.touch("taesd.safetensors", VAE_KEYS)          # anteprime: ignorato
        self.touch("notes.txt", size=3)
        flux = self.touch("FLUX.1-dev/flux1-dev-Q8_0.gguf", size=300)
        ae = self.touch("FLUX.1-dev/ae.safetensors", VAE_KEYS)
        clip = self.touch("FLUX.1-dev/clip_l.safetensors", size=10)
        self.touch("FLUX.1-dev/t5xxl_fp8.safetensors", size=10)
        t5 = self.touch("FLUX.1-dev/t5xxl_fp16.safetensors", size=20)   # il piu' grande
        # SDXL con il VAE incorporato e "vae" nel nome: e' un modello completo.
        self.touch("xl/sd_xl_base_1.0_0.9vae.safetensors", SDXL_KEYS)
        models = {m.name: m for m in rd.scan_folder(self.dir)}
        self.assertEqual(sorted(models), ["FLUX.1-dev", "sd15", "sd_xl_base_1.0_0.9vae"])
        m = models["FLUX.1-dev"]
        self.assertFalse(m.full)
        self.assertEqual(m.args(), ["--diffusion-model", flux, "--vae", ae, "--clip_l", clip,
                                    "--t5xxl", t5])
        self.assertEqual(m.guess_family(), "flux")
        self.assertEqual(models["sd15"].args()[0], "-m")
        self.assertEqual(models["sd_xl_base_1.0_0.9vae"].family, "sdxl")

    def test_full_checkpoint_with_separate_vae(self):
        main = self.touch("anime/animeXL.safetensors", SDXL_KEYS)
        vae = self.touch("anime/sdxl_vae.safetensors", VAE_KEYS)
        (m,) = rd.scan_folder(self.dir)
        self.assertEqual(m.args(), ["-m", main, "--vae", vae])

    def test_missing_parts(self):
        # ERNIE senza VAE e senza codificatore, da solo nella cartella.
        lone = self.touch("ERNIE-Image-Turbo-Q4_K_M.gguf", size=100)
        (m,) = rd.scan_folder(self.dir, recursive=False)
        self.assertEqual(m.missing(), ["vae", "llm"])
        # Con il VAE ma senza codificatore.
        os.remove(lone)
        self.touch("Z-Image-Turbo/z_image_turbo-Q4_0.gguf", size=100)
        self.touch("Z-Image-Turbo/ae.safetensors", VAE_KEYS)
        (m,) = rd.scan_folder(os.path.join(self.dir, "Z-Image-Turbo"))
        self.assertEqual(m.missing(), ["llm"])
        self.touch("Z-Image-Turbo/Qwen3-4B-Instruct-2507-Q4_K_M.gguf", size=10)
        (m,) = rd.scan_folder(os.path.join(self.dir, "Z-Image-Turbo"))
        self.assertEqual(m.missing(), [])
        # Un SD 1.5 completo non ha bisogno di niente.
        sd = rd.Model("v1-5", self.touch("v1-5.safetensors", SD15_KEYS), True, "sd1",
                      header_full=True)
        self.assertEqual(sd.missing(), [])

    def test_files_in_models_root(self):
        """I tre file messi direttamente nella cartella dei modelli: il
        modello prende il nome del file, non "models"."""
        saved = rd.MODEL_DIRS
        rd.MODEL_DIRS = (self.dir,)
        try:
            self.touch("ERNIE-Image-Turbo-Q4_K_M.gguf", size=100)
            self.touch("flux2-vae.safetensors", VAE_KEYS)
            self.touch("Ministral-3-3B-Instruct-2512-Q8_0.gguf", size=10)
            (m,) = rd.find_models()
            self.assertEqual(m.name, "ERNIE-Image-Turbo-Q4_K_M")
            self.assertEqual(m.missing(), [])
        finally:
            rd.MODEL_DIRS = saved

    def test_misplaced_files(self):
        chat = os.path.join(self.dir, "chat")
        os.makedirs(chat)
        for n in ("Qwen3-8B-Q4_K_M.gguf", "ERNIE-4.5-21B-Q4_K_M.gguf",
                  "Ministral-3-3B-Instruct-2512-Q8_0.gguf", "mmproj-F16.gguf"):
            self.touch(os.path.join("chat", n), size=10)
        self.assertEqual(rd.misplaced_files((chat,)), [])
        for n in ("ERNIE-Image-Turbo-Q4_K_M.gguf", "ae.safetensors", "z_image_turbo-Q4_0.gguf"):
            self.touch(os.path.join("chat", n), size=10)
        self.assertEqual([os.path.basename(p) for p in rd.misplaced_files((chat,))],
                         ["ERNIE-Image-Turbo-Q4_K_M.gguf", "ae.safetensors",
                          "z_image_turbo-Q4_0.gguf"])

    def test_guide_files_are_recognised(self):
        """I nomi dei file della guida «Quali file scaricare?» danno un
        modello completo."""
        for entry in rd.GUIDE:
            with self.subTest(entry["name"]):
                for role, hint, _url in entry["files"]:
                    name = "vae.safetensors" if hint.startswith("vae/") else hint
                    self.touch(os.path.join(entry["name"], name),
                               size=100 if role == "model" else 10)
                (m,) = rd.scan_folder(os.path.join(self.dir, entry["name"]))
                self.assertEqual(m.missing(), [])
                self.assertEqual(rd.recommended(m)["steps"], 8)

    def test_find_models_no_duplicates(self):
        self.touch("a.safetensors", SD15_KEYS)
        found = rd.find_models([self.dir, self.dir, "/non/esiste"])
        self.assertEqual([m.name for m in found], ["a"])

    def test_recommended_and_job(self):
        sd15 = rd.Model("v1-5", self.touch("v1-5.safetensors", SD15_KEYS), True, "sd1")
        turbo = rd.Model("sdxl-turbo", self.touch("sdxl_turbo.safetensors", SDXL_KEYS),
                         True, "sdxl")
        # SDXL completo con "flux" nel nome: valgono i tensori, non il nome.
        mania = rd.Model("fluxmania-xl", self.touch("fluxmania.safetensors", SDXL_KEYS),
                         True, "sdxl")
        rec = rd.recommended(sd15)
        self.assertEqual((rec["family"], rec["side"], rec["steps"], rec["cfg"], rec["fixed"]),
                         ("sd1", 512, 25, 7.0, False))
        self.assertEqual((rd.recommended(turbo)["steps"], rd.recommended(turbo)["fixed"]),
                         (4, True))
        self.assertEqual(rd.recommended(mania)["family"], "sdxl")
        settings = {"img_aspect": "landscape", "img_quality": "fast", "img_seed": 42,
                    "img_count": 9, "img_negative": "  sfocato ", "img_sampler": "nessuno"}
        job = rd.make_job(sd15, "  un gatto  ", settings)
        self.assertEqual((job.prompt, job.negative, job.seed), ("un gatto", "sfocato", 42))
        self.assertEqual((job.width, job.height), (640, 448))
        self.assertEqual((job.steps, job.cfg, job.count, job.sampler), (15, 7.0, 4, ""))
        # Distillato: la Qualita' non cambia i passi.
        self.assertEqual(rd.make_job(turbo, "x", settings).steps, 4)
        job = rd.make_job(sd15, "x", {"img_steps": 30, "img_cfg": 5.5, "img_side": 1024,
                                      "img_seed": -1, "img_sampler": "euler"})
        self.assertEqual((job.width, job.height, job.steps, job.cfg, job.sampler),
                         (1024, 1024, 30, 5.5, "euler"))
        self.assertGreaterEqual(job.seed, 0)

    # Cartelle come negli esempi di docs/models/ di stable-diffusion.cpp:
    # file -> opzioni attese, e (passi, cfg, campionatore, opzioni in piu').
    LAYOUTS = {
        "Z-Image-Turbo": (["z-image-turbo-Q4_K_M.gguf", "Qwen3-4B-Instruct-2507-Q4_K_M.gguf",
                           "ae.safetensors"],
                          {"--diffusion-model": "z-image-turbo-Q4_K_M.gguf",
                           "--llm": "Qwen3-4B-Instruct-2507-Q4_K_M.gguf", "--vae": "ae.safetensors"},
                          (8, 1.0, "", [])),
        "Z-Image": (["z_image_bf16.safetensors", "qwen_3_4b.safetensors", "ae.sft"],
                    {"--vae": "ae.sft", "--llm": "qwen_3_4b.safetensors"}, (20, 5.0, "", [])),
        "FLUX.2-klein-4B": (["flux-2-klein-4b.safetensors", "flux2_ae.safetensors",
                             "qwen_3_4b.safetensors"],
                            {"--diffusion-model": "flux-2-klein-4b.safetensors",
                             "--vae": "flux2_ae.safetensors"}, (4, 1.0, "", [])),
        "FLUX.2-klein-base-4B": (["flux-2-klein-base-4b.safetensors", "flux2_ae.safetensors",
                                  "qwen_3_4b.safetensors"], {}, (20, 4.0, "", [])),
        "FLUX.2-dev": (["flux2-dev-Q4_K_S.gguf", "flux2_ae.safetensors",
                        "Mistral-Small-3.2-24B-Instruct-2506-Q4_K_M.gguf"],
                       {"--llm": "Mistral-Small-3.2-24B-Instruct-2506-Q4_K_M.gguf"},
                       (20, 1.0, "euler", [])),
        "FLUX.3": (["flux-3-image-klein.safetensors", "Qwen3-VL-4B-Instruct-Q4_K_M.gguf",
                    "flux2_ae.safetensors"], {}, (16, 1.0, "euler", [])),
        "FLUX.1-schnell": (["flux1-schnell-q8_0.gguf", "ae.sft", "clip_l.safetensors",
                            "t5xxl_fp16.safetensors"],
                           {"--clip_l": "clip_l.safetensors", "--t5xxl": "t5xxl_fp16.safetensors"},
                           (4, 1.0, "euler", [])),
        "FLUX.1-dev": (["flux1-dev-q8_0.gguf", "ae.sft", "clip_l.safetensors",
                        "t5xxl_fp16.safetensors"], {}, (20, 1.0, "euler", [])),
        "Qwen-Image": (["qwen-image-Q8_0.gguf", "qwen_image_vae.safetensors",
                        "Qwen2.5-VL-7B-Instruct-Q8_0.gguf"],
                       {"--diffusion-model": "qwen-image-Q8_0.gguf",
                        "--vae": "qwen_image_vae.safetensors",
                        "--llm": "Qwen2.5-VL-7B-Instruct-Q8_0.gguf"},
                       (20, 2.5, "euler", ["--flow-shift", "3"])),
        "Qwen-Image-2.1": (["qwen_image_2.1_int8_convrot.safetensors",
                            "qwen_image_2.1_vae_bf16.safetensors",
                            "Qwen3VL-8B-Instruct-Q4_K_M.gguf"],
                           {"--vae": "qwen_image_2.1_vae_bf16.safetensors"},
                           (40, 6.0, "euler", [])),
        "Qwen-Image-2.1-Turbo": (["qwen_image_2.1_turbo-Q8_0.gguf",
                                  "qwen_image_2.1_vae_bf16.safetensors",
                                  "Qwen3VL-8B-Instruct-Q4_K_M.gguf"], {},
                                 (8, 1.0, "euler", ["--sigmas", "qwen-image-2.1-turbo"])),
        "ERNIE-Image": (["ernie-image-UD-Q4_K_M.gguf", "flux2_ae.safetensors",
                         "ministral-3-3b.safetensors"], {}, (50, 5.0, "", [])),
        "Chroma": (["chroma-unlocked-v40-q8_0.gguf", "ae.sft", "t5xxl_fp16.safetensors"],
                   {"--t5xxl": "t5xxl_fp16.safetensors"},
                   (20, 4.0, "euler", ["--model-args", "chroma_use_dit_mask=false"])),
        "SD3.5-Large": (["sd3.5_large.safetensors", "clip_l.safetensors", "clip_g.safetensors",
                         "t5xxl_fp16.safetensors"], {"--clip_g": "clip_g.safetensors"},
                        (28, 4.5, "euler", [])),
        "Fibo-2": (["fibo2_dev_int8_convrot.safetensors", "Qwen3-VL-4B-Instruct-Q4_K_M.gguf",
                    "Qwen3-VL-4B-Instruct-mmproj-BF16.gguf", "flux2_ae.safetensors"],
                   {"--llm": "Qwen3-VL-4B-Instruct-Q4_K_M.gguf",
                    "--llm_vision": "Qwen3-VL-4B-Instruct-mmproj-BF16.gguf"},
                   (20, 5.0, "euler", [])),
        "Ideogram4": (["ideogram4-Q8_0.gguf", "ideogram4_uncond-Q8_0.gguf",
                       "Qwen3VL-8B-Instruct-Q4_K_M.gguf", "flux2_ae.safetensors"],
                      {"--diffusion-model": "ideogram4-Q8_0.gguf",
                       "--uncond-diffusion-model": "ideogram4_uncond-Q8_0.gguf"},
                      (20, None, "", [])),
        "Lens-Turbo": (["lens_turbo_bf16.safetensors", "gpt-oss-20b-UD-Q8_K_XL.gguf",
                        "tokenizer_gpt_oss.json", "flux2_ae.safetensors", "LEGGIMI.json"],
                       {"--llm": "gpt-oss-20b-UD-Q8_K_XL.gguf",
                        "--tokenizer": "tokenizer_gpt_oss.json"}, (4, 1.0, "", [])),
        "Ming-Image": (["ming_image_0.1_design_bf16.safetensors",
                        "ming_image_0.1_ling_mini_2.0_bf16.safetensors",
                        "ming_image_vae_bf16.safetensors", "tokenizer.json"],
                       {"--diffusion-model": "ming_image_0.1_design_bf16.safetensors",
                        "--llm": "ming_image_0.1_ling_mini_2.0_bf16.safetensors",
                        "--vae": "ming_image_vae_bf16.safetensors"},
                       (12, 1.0, "euler", [])),
        "ERNIE-Image-Turbo": (["ernie-image-turbo.safetensors", "flux2_ae.safetensors",
                               "ministral-3-3b.safetensors"],
                              {"--llm": "ministral-3-3b.safetensors"}, (8, 1.0, "", [])),
        "Ovis-Image": (["ovis_image-Q4_0.gguf", "ae.sft", "ovis_2.5.safetensors"],
                       {"--diffusion-model": "ovis_image-Q4_0.gguf",
                        "--llm": "ovis_2.5.safetensors"}, (20, 5.0, "", [])),
        "MiniMax-H3-Image": (["minimax_h3_image_pruned_bf16.safetensors",
                              "minimax_h3_image_vae_fp16.safetensors",
                              "qwen3vl_32b_minimax_h3-Q4_K_M.gguf"],
                             {"--diffusion-model": "minimax_h3_image_pruned_bf16.safetensors",
                              "--vae": "minimax_h3_image_vae_fp16.safetensors",
                              "--llm": "qwen3vl_32b_minimax_h3-Q4_K_M.gguf"},
                             (6, 1.0, "euler", ["--sigmas", "minimax-h3-image", "--rng", "cpu"])),
        "LongCat-Image": (["LongCat-Image-Q4_K_M.gguf", "ae.sft",
                           "Qwen2.5-VL-7B-Instruct-Q8_0.gguf"], {},
                          (20, 5.0, "euler", ["--flow-shift", "3"])),
        "Krea-2": (["Krea-2-Raw-Q8_0.gguf", "Qwen3-VL-4B-Instruct-Q4_K_M.gguf",
                    "wan_2.1_vae.safetensors"], {"--vae": "wan_2.1_vae.safetensors"},
                   (20, None, "", [])),
    }

    def test_known_layouts(self):
        for folder, (names, expected, (steps, cfg, sampler, extra)) in self.LAYOUTS.items():
            with self.subTest(folder):
                for n in names:
                    self.touch(os.path.join(folder, n), size=100 if n.startswith(
                        ("z", "flux", "qwen-image", "qwen_image_2", "chroma", "sd3", "fibo2_",
                         "ideogram4-", "lens_", "ming_image_0.1_design", "ernie", "ovis_image",
                         "minimax_h3_image_pruned", "LongCat", "Krea")) else 10)
                # (i nomi "qwen_image_2.1..." di modello e VAE: conta il ruolo)
                (m,) = rd.scan_folder(os.path.join(self.dir, folder))
                args = m.args()
                flags = dict(zip(args[::2], (os.path.basename(a) for a in args[1::2])))
                self.assertEqual(args[0], "--diffusion-model")
                for flag, name in expected.items():
                    self.assertEqual(flags.get(flag), name, flag)
                job = rd.make_job(m, "x", {"img_quality": "normal"})
                self.assertEqual((job.steps, job.cfg, job.sampler, job.extra),
                                 (steps, cfg, sampler, extra))

    def test_image_size(self):
        self.assertEqual(rd.image_size(1024, "square"), (1024, 1024))
        self.assertEqual(rd.image_size(1024, "landscape"), (1280, 832))
        self.assertEqual(rd.image_size(1024, "portrait"), (832, 1280))
        for side in (512, 768, 1024, 1280):
            for aspect in rd.ASPECTS:
                w, h = rd.image_size(side, aspect)
                self.assertEqual((w % 64, h % 64), (0, 0))

    def test_devices(self):
        devices = rd.parse_devices("CPU\tAMD Ryzen\nVulkan0\tNVIDIA RTX 4060\n"
                                   "Vulkan1\tNVIDIA RTX 4060\nrumore\n")
        self.assertEqual(devices, [{"name": "Vulkan0", "label": "NVIDIA RTX 4060"},
                                   {"name": "Vulkan1", "label": "NVIDIA RTX 4060 (2)"}])
        self.assertEqual(rd.device_backend("NVIDIA RTX 4060 (2)", devices), "Vulkan1")
        self.assertIsNone(rd.device_backend("altra", devices))

    def test_backend_assignment(self):
        self.assertIsNone(rd.backend_assignment())
        self.assertEqual(rd.backend_assignment("Vulkan0"), "Vulkan0")
        self.assertEqual(rd.backend_assignment(None, "Vulkan1"), "te=Vulkan1")
        self.assertEqual(rd.backend_assignment("Vulkan0", "Vulkan1"), "all=Vulkan0,te=Vulkan1")
        self.assertEqual(rd.backend_assignment("Vulkan0", "cpu"), "all=Vulkan0,te=cpu")
        self.assertEqual(rd.backend_assignment("Vulkan0", "Vulkan0"), "Vulkan0")

    def test_progress(self):
        self.assertEqual(rd.parse_progress("\r  |=====>      | 3/20 - 1.52s/it\x1b[K"),
                         ("sample", 3, 20))
        self.assertEqual(rd.parse_progress("  |####       | 2/9 - 210.00MB/s"), ("load", 2, 9))
        self.assertEqual(rd.parse_progress("\r  |=>   | 1/4 - 2s/it\r  |===> | 3/4 - 2s/it"),
                         ("sample", 3, 4))
        self.assertIsNone(rd.parse_progress("[INFO ] loading model"))


@unittest.skipIf(rd is None, "serve PyGObject (GLib)")
class TestGenerator(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        engine_dir = os.path.join(self.tmp.name, "engine")
        os.makedirs(engine_dir)
        self.binary = os.path.join(engine_dir, "sd-cli")
        with open(self.binary, "w") as f:
            f.write(FAKE_SD)
        os.chmod(self.binary, os.stat(self.binary).st_mode | stat.S_IEXEC)
        self.saved = (rd.ENGINE_DIRS, rd.WORK_DIR)
        rd.ENGINE_DIRS = (engine_dir,)
        rd.WORK_DIR = os.path.join(self.tmp.name, "cache", "ruscallama", "images")
        self.args_log = os.path.join(self.tmp.name, "args.txt")
        os.environ["FAKE_SD_LOG"] = self.args_log
        model = os.path.join(self.tmp.name, "sd15.safetensors")
        write_safetensors(model, SD15_KEYS)
        self.model = rd.scan_folder(self.tmp.name, recursive=False)[0]

    def tearDown(self):
        rd.ENGINE_DIRS, rd.WORK_DIR = self.saved
        for k in ("FAKE_SD_LOG", "FAKE_SD_FAIL", "FAKE_SD_DELAY"):
            os.environ.pop(k, None)
        self.tmp.cleanup()

    def run_job(self, job, cancel_after_preview=False, **kw):
        loop = GLib.MainLoop()
        events = {"progress": [], "previews": 0, "log": [], "done": None}
        gen = None

        def on_preview(data):
            events["previews"] += 1
            if cancel_after_preview:
                gen.cancel()

        def done(error, images, j):
            events["done"] = (error, images, j)
            loop.quit()
        gen = rd.Generator(on_progress=lambda *a: events["progress"].append(a),
                           on_preview=on_preview, on_log=events["log"].append, on_done=done)
        gen.PREVIEW_POLL = 0.05
        gen.start(self.model, job, threads=2, **kw)
        GLib.timeout_add_seconds(30, loop.quit)
        loop.run()
        gen.wait(5)
        return events

    def test_generation(self):
        job = rd.Job(prompt="un gatto rosso su un tetto", negative="sfocato", width=512,
                     height=384, steps=4, cfg=7, seed=7, count=2)
        os.environ["FAKE_SD_DELAY"] = "0.15"
        ev = self.run_job(job, gpu=False)
        error, images, _job = ev["done"]
        self.assertIsNone(error)
        self.assertEqual([os.path.basename(p) for p in images], ["image_000.png", "image_001.png"])
        for p in images:
            with open(p, "rb") as f:
                self.assertEqual(f.read(8), b"\x89PNG\r\n\x1a\n")
        run_dir = os.path.dirname(images[0])
        # Prompt e anteprima non restano sul disco.
        self.assertEqual(sorted(os.listdir(run_dir)), ["image_000.png", "image_001.png"])
        self.assertEqual(stat.S_IMODE(os.stat(rd.WORK_DIR).st_mode), 0o700)
        self.assertIn(("sample", 4, 4), ev["progress"])
        self.assertIn(("load", 3, 3), ev["progress"])
        self.assertGreater(ev["previews"], 0)
        with open(self.args_log) as f:
            args = f.read().split("\n")
        # Il prompt non e' sulla riga di comando: e' in un file.
        self.assertNotIn("un gatto rosso su un tetto", " ".join(args))
        self.assertIn("--prompt-file", args)
        self.assertIn("--negative-prompt-file", args)
        self.assertEqual(args[args.index("--backend") + 1], "cpu")
        self.assertIn("--disable-image-metadata", args)
        for opt, val in (("-W", "512"), ("-H", "384"), ("--steps", "4"), ("-s", "7"),
                         ("-b", "2"), ("-t", "2")):
            self.assertEqual(args[args.index(opt) + 1], val)
        rd.clean_work_dir()
        self.assertEqual(os.listdir(rd.WORK_DIR), [])

    def test_gpu_device_and_options(self):
        job = rd.Job(prompt="x", steps=1, seed=1)
        ev = self.run_job(job, gpu=True, gpu_device="Fake GPU (2)", low_memory=True,
                          metadata=True)
        self.assertIsNone(ev["done"][0])
        with open(self.args_log) as f:
            args = f.read().split("\n")
        self.assertEqual(args[args.index("--backend") + 1], "Vulkan1")
        self.assertIn("--vae-tiling", args)
        self.assertIn("--offload-to-cpu", args)
        self.assertNotIn("--disable-image-metadata", args)
        self.assertNotIn("--negative-prompt-file", args)
        self.assertNotIn("--cfg-scale", args)          # cfg None: decide il motore

    def test_extra_options(self):
        job = rd.Job(prompt="x", steps=1, seed=1, cfg=2.5, sampler="euler",
                     extra=["--flow-shift", "3"])
        self.assertIsNone(self.run_job(job, gpu=False)["done"][0])
        with open(self.args_log) as f:
            args = f.read().split("\n")
        self.assertEqual(args[args.index("--cfg-scale") + 1], "2.5")
        self.assertEqual(args[args.index("--sampling-method") + 1], "euler")
        self.assertEqual(args[args.index("--flow-shift") + 1], "3")

    def test_text_encoder_on_other_card(self):
        job = rd.Job(prompt="x", steps=1, seed=1)
        for gpu_device, te_device, expected in (
                ("Fake GPU", "Fake GPU (2)", "all=Vulkan0,te=Vulkan1"),
                ("", "Fake GPU (2)", "te=Vulkan1"),
                ("Fake GPU", "cpu", "all=Vulkan0,te=cpu"),
                ("Fake GPU", "scheda tolta", "Vulkan0")):
            with self.subTest(te_device):
                self.assertIsNone(self.run_job(job, gpu=True, gpu_device=gpu_device,
                                               te_device=te_device)["done"][0])
                with open(self.args_log) as f:
                    args = f.read().split("\n")
                self.assertEqual(args[args.index("--backend") + 1], expected)
        # Senza scheda grafica tutto va sul processore.
        self.run_job(job, gpu=False, te_device="Fake GPU (2)")
        with open(self.args_log) as f:
            args = f.read().split("\n")
        self.assertEqual(args[args.index("--backend") + 1], "cpu")

    def test_engine_error(self):
        os.environ["FAKE_SD_FAIL"] = "1"
        ev = self.run_job(rd.Job(prompt="x", steps=1, seed=1), gpu=False)
        error, images, _job = ev["done"]
        self.assertIsInstance(error, rd.DiffusionError)
        self.assertEqual(error.key, "img_err_engine")
        self.assertIn("load model failed", error.detail)
        self.assertEqual(images, [])
        self.assertEqual(os.listdir(rd.WORK_DIR), [])     # niente resti

    def test_cancel(self):
        os.environ["FAKE_SD_DELAY"] = "0.5"
        ev = self.run_job(rd.Job(prompt="x", steps=50, seed=1), cancel_after_preview=True,
                          gpu=False)
        self.assertEqual(ev["done"][0], "cancelled")
        self.assertEqual(os.listdir(rd.WORK_DIR), [])

    def test_start_errors(self):
        gen = rd.Generator()
        with self.assertRaises(rd.DiffusionError) as e:
            gen.start(self.model, rd.Job(prompt="  ".strip()))
        self.assertEqual(e.exception.key, "img_err_no_prompt")
        missing = rd.Model("x", "/non/esiste.safetensors", True)
        with self.assertRaises(rd.DiffusionError) as e:
            gen.start(missing, rd.Job(prompt="x"))
        self.assertEqual(e.exception.key, "img_err_no_model")
        rd.ENGINE_DIRS = ("/non/esiste",)
        with self.assertRaises(rd.DiffusionError) as e:
            gen.start(self.model, rd.Job(prompt="x"))
        self.assertEqual(e.exception.key, "img_err_no_engine")

    def test_list_devices(self):
        self.assertEqual([d["name"] for d in rd.list_devices()], ["Vulkan0", "Vulkan1"])


@unittest.skipIf(rd is None, "serve PyGObject (GLib)")
class TestTranslations(unittest.TestCase):
    def test_keys_and_placeholders(self):
        """Ogni testo usato dalla vista Immagini c'e' in tutte le lingue, con
        gli stessi segnaposto dell'inglese (lo controlla anche make-deb.sh)."""
        import re
        lang = os.path.join(TOOL, "lang")
        def load(name):
            with open(os.path.join(lang, name), encoding="utf-8") as f:
                return json.load(f)
        en = load("en.json")
        src = ""
        for name in ("diffusion_view.py", "ruscallama.py"):
            with open(os.path.join(TOOL, name), encoding="utf-8") as f:
                src += f.read()
        used = set(re.findall(r'_\("((?:img|view)_[a-z_]+)"', src))
        used |= {f"img_aspect_{a}" for a in rd.ASPECTS} | {f"img_quality_{q}" for q in rd.QUALITY}
        self.assertFalse(used - set(en), sorted(used - set(en)))
        fields = lambda v: sorted(re.findall(r"{(\w+)}", v))
        for name in sorted(os.listdir(lang)):
            data = load(name)
            self.assertEqual(set(data), set(en), name)
            for k in en:
                self.assertEqual(fields(data[k]), fields(en[k]), f"{name}: {k}")


if __name__ == "__main__":
    unittest.main()
