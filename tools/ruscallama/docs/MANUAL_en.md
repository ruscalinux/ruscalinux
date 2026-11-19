# RuscaLLama 1.99.3 — Manual

**Version** 1.99.3 · **Author** Nunzio Curcuruto · **Distribution** RuscaLinux ([ruscalinux.org](https://www.ruscalinux.org/)) · **License** GNU GPL v3 or later

RuscaLLama is a chat with language models that run **entirely on this computer**. The model is run by **ruscallama-engine**, that is llama.cpp: an external component under the MIT license, built for RuscaLinux. The **Images** view creates pictures from a description with **ruscadiffusion-engine**, that is stable-diffusion.cpp, also under the MIT license (section 7).

The common Markdown engine includes an external component: the highlight rule `==text==`, a port of the [markdown-it-mark](https://github.com/markdown-it/markdown-it-mark) plugin (MIT license, © Vitaly Puzrin and Alex Kocharin; Python structure from markdown-it-py, © ExecutableBookProject), in its own file `markdown_it_mark.py`.

---

## 1. Requirements

- RuscaLinux or Debian Stable, GNOME;
- Python ≥ 3.10, GTK ≥ 4.18, libadwaita ≥ 1.7, GtkSourceView 5;
- the `ruscallama-engine` package, and `ruscadiffusion-engine` for images;
- at least one model in **GGUF** format.

Memory needs depend on the model: as a rule of thumb, a little more than the size of the GGUF file, plus the context memory.

## 2. Where to put models

RuscaLLama looks for `.gguf` files in:

- `~/.local/share/ruscallama/models/` — your models (from the settings: **Open the Models Folder**);
- `/usr/share/ruscallama/models/` — models installed for all users.

You can also pick a file in any folder with **Choose a File…**. Next to the model there can be:

- an `mmproj-….gguf` file: enables **Vision** (reading images);
- a small `…mtp….gguf` draft: enables **Speculative Decoding**.

## 3. The window

- **Header bar**: on the left **+** (new conversation); in the middle the two views, **Chat** and **Images** (in narrow windows they move to the bottom); on the right the settings panel button and the main menu.
- **Conversation**: answers appear while they are generated. Code blocks are highlighted and have a copy button. Each answer has **Copy Answer** and a menu to save it as Markdown or save its code blocks.
- **Reasoning**: when on, the model's reasoning appears in a collapsible section above the answer.
- **Bottom bar**: attachments, message box, **Send** (which becomes **Stop** during an answer); below, the loaded model or the engine state and the speed in tokens per second.
- **Notices at the top**: missing engine, no model, loading, settings to apply with a restart.

The engine starts on its own with the first message and stops when the window closes.

## 4. Model settings

The side panel (F9) has four groups.

| Group | Option | Effect |
|---|---|---|
| Text | Text Size | Size of the conversation and the message; also with Ctrl++ and Ctrl+−, Ctrl+0 returns to the system size |
| Model | Model | Choice among the GGUF files found |
| Answers | Style | *Precise*, *Balanced*, *For reasoning*, *Creative* or *Custom* |
| Answers | Reasoning | The model thinks before answering; applies at once, no restart |
| Answers | Reasoning Depth | Low, medium, high |
| Answers | Instructions for the model | The system message |
| Answers | Sampling Parameters | Temperature, top-p, top-k, min-p, penalties, seed; changing one sets the style to *Custom* |
| Engine | Graphics Card (Vulkan) | Much faster; turn off if the driver gives problems |
| Engine | Graphics Card to Use | Automatic, or one of the computer’s graphics cards. On laptops with two graphics cards choose the dedicated one (for example NVIDIA) |
| Engine | CPU Threads | As many as the physical cores is recommended |
| Engine | Context | Tokens the model keeps in mind |
| Engine | Context Memory | Full precision or compressed (recommended) |
| Engine | Flash Attention | Automatic, on or off |
| Engine | Vision, Speculative Decoding | Available only with the right files next to the model |

**Engine** options apply when the engine restarts: when you change one, a notice at the top offers **Restart Engine**.

## 5. Attachments

With the paper clip (Ctrl+O) you can attach text and code files (up to 512 KB) and images (up to 8 MB, only with Vision on). The text of attachments is added to the message.

## 6. Saving

From the main menu: **Save Conversation as Markdown…** (Ctrl+S) or **as HTML…**. From each answer's menu: **Save Answer as Markdown…** and **Save Code Blocks…**, which writes one file per block in the chosen folder and never overwrites existing files.

## 7. Images

The **Images** view (at the top, next to **Chat**; Alt+2) creates pictures from a description, with an image model that runs on this computer. The engine is **ruscadiffusion-engine**, that is stable-diffusion.cpp: an external component under the MIT license, built for RuscaLinux. It starts for every image and closes as soon as it is done: it opens no port and does not use the network.

### The model

The first time, the Images view shows what is needed: a model is made of **three files** (the model, the text encoder and the VAE) to put together in a folder. **Which Files to Download?** lists the files of the recommended models with the pages to download them from, and **Create the Folder and Open It** prepares the folder with the right name: copy the three files there and the model appears on its own. If a file is missing, or you copied a file into the chat models folder, a notice at the top says so.

Copy it into `~/.local/share/ruscadiffusion/models/` (side panel → **Open the Models Folder**), or leave it where it is and choose **Add a Folder…**: RuscaLLama remembers the folder without copying the files. A model can be:

- **a single** `.safetensors`, `.gguf` or `.ckpt` **file** with everything inside: Stable Diffusion 1.5, SDXL, SD-Turbo, SDXL-Turbo;
- **a folder** with the model and its parts: for FLUX the model, `ae.safetensors`, `clip_l` and `t5xxl`; for Z-Image the model, `ae.safetensors` and the Qwen language model; for Stable Diffusion 3.5 also `clip_g`.

RuscaLLama recognises the files on its own and picks the steps, CFG and sampler recommended for that model: FLUX.2, Qwen-Image, Chroma and the other recent models that stable-diffusion.cpp supports work too. For an easy start: **Z-Image-Turbo** (Apache 2.0 license), which makes good images in 8 steps and, as Q3_K, works even with 4 GB of graphics memory. Every model has its own license.

### Creating an image

1. Write what you want to see in the box at the bottom. The more details you give (subject, place, light, style), the closer the image will be.
2. Choose **Square**, **Landscape** or **Portrait**.
3. Press **Generate** (Enter). While it works you see a preview taking shape and the current step; **Stop** (Esc) interrupts it.

Click an image to see it large. From its menu: **Save Image…**, **Copy Image**, **Attach to Conversation** (to have a model with Vision describe it), **Reuse the Seed** (start again from the same image with a slightly different description), **Remove**.

A chat answer can become a description too: the answer's menu → **Create an Image from This Answer**. For example, ask the model to write a detailed prompt, then use it.

Images stay in the program until you close it: **save the ones you want to keep**. When closing, RuscaLLama asks for confirmation if some are not saved.

### Image settings

With the Images view open, the side panel (F9) shows these settings.

| Group | Option | Effect |
|---|---|---|
| Image Model | Model | Choice among the models found; below the name, whether it is a single file or a folder |
| Image Model | Add a Folder…, Remove the Folder from the List | Use or forget a folder of models; the files are not moved |
| Image | Quality | Fast, Normal, Detailed: more steps, more detail, more time. It does not apply to distilled models (Turbo, schnell, klein…), which have a fixed number of steps |
| Image | Images per Run | From 1 to 4, with the same description |
| Image | Things to avoid | What you do not want in the image (negative prompt); FLUX and Turbo models pay little attention to it |
| Image | Write the Prompt in the File | Off: the saved PNG does not contain the description and the settings |
| Image | Advanced Settings | Steps, prompt guidance (CFG), base size, sampler, seed. 0, "Automatic" and −1 use the values recommended for the model (shown under each row) or a random seed |
| Image Engine | Graphics card, Graphics card to use, Threads | As for the chat. With "Automatic" the engine picks the dedicated card; what does not fit stays in RAM and moves to the card piece by piece |
| Image Engine | Text Encoder | On the same card, on the processor or on another card. With two cards (for example an NVIDIA with little memory and an integrated Radeon) put it on the second one: the first stays free for the model, which works at every step |
| Image Engine | Save Memory | Keeps all weights in RAM. Slower: leave it off, and try it only if the engine stops for lack of graphics memory |

## 8. Keyboard shortcuts

| Keys | Action |
|---|---|
| Alt+1 / Alt+2 | Chat view / Images view |
| Enter | Send (in the Images view: Generate) |
| Shift+Enter | New line |
| Esc | Stop the answer or the image |
| Ctrl+N | New conversation |
| Ctrl+O | Attach files |
| Ctrl+S | Save the conversation as Markdown |
| F9 | Model settings |
| Ctrl++ / Ctrl+− / Ctrl+0 | Larger / smaller text / system size |
| Ctrl+? | Keyboard shortcuts |
| F10 | Main menu |
| Ctrl+W / Ctrl+Q | Close the window / Quit |

## 9. Privacy and security

- The engine listens only on **127.0.0.1**, on a free port chosen at every start.
- Every start creates a **temporary access key**, stored in `$XDG_RUNTIME_DIR/ruscallama/` with 0600 permissions: other users of the computer cannot use the model or read the conversations.
- The engine is built **without** the ability to download anything from the internet.
- Conversations are not saved automatically: they stay in memory until you save them.
- The engine has an AppArmor profile (in *complain* mode) that denies it the most sensitive folders of the home.
- Settings are in `~/.config/ruscallama/settings.json`.

For images:

- the image engine has no network code (no server): it starts, creates the images and exits;
- the description reaches it in a file, not on the command line, where other users of the computer could see it;
- unsaved images are kept in `~/.cache/ruscallama/images/` (0700 permissions) and deleted when the program closes;
- the saved PNG does not contain the description unless you turn on **Write the Prompt in the File**.

Answers from a language model can be wrong: check important information.

## 10. Troubleshooting

| Problem | What to do |
|---|---|
| "ruscallama-engine is not installed" | `sudo apt install ruscallama-engine` |
| The engine stops at once | Open **Engine Log** from the menu: memory is often the cause; try a smaller model, less context or compressed context memory |
| Very slow | Turn on **Graphics Card (Vulkan)**; check the number of threads |
| The graphics driver hangs | Turn off **Graphics Card (Vulkan)** |
| The model loads without the graphics card but not with it | In **Graphics Card to Use** choose the dedicated card: on a laptop with two cards the engine may use the wrong one |
| Images are not accepted | You need an `mmproj` file next to the model and **Vision** on |
| "ruscadiffusion-engine is not installed" | `sudo apt install ruscadiffusion-engine` |
| The image model does not appear | It must be `.safetensors`, `.gguf` or `.ckpt`; a model made of several files goes in its own folder, with its parts |
| The image is not created | Main menu → **Image Engine Log**: memory is often the cause; turn on **Save Memory**, choose **Fast** or a smaller format |
| Blurry or strange images | Use the recommended values (advanced settings at 0 and "Automatic"); SD 1.5 models work at 512 px, SDXL and FLUX at 1024 |

Support: info@ruscalinux.org — The note on the use of AI tools is in the About window and in the `NOTA-IA.md` file of the repository.
