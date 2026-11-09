# RuscaLLama 1.99.2 — Manual

**Version** 1.99.2 · **Author** Nunzio Curcuruto · **Distribution** RuscaLinux ([ruscalinux.org](https://www.ruscalinux.org/)) · **License** GNU GPL v3 or later

RuscaLLama is a chat with language models that run **entirely on this computer**. The model is run by **ruscallama-engine**, that is llama.cpp: an external component under the MIT license, built for RuscaLinux.

The common Markdown engine includes an external component: the highlight rule `==text==`, a port of the [markdown-it-mark](https://github.com/markdown-it/markdown-it-mark) plugin (MIT license, © Vitaly Puzrin and Alex Kocharin), in `rusca_markdown.py`.

---

## 1. Requirements

- RuscaLinux or Debian Stable, GNOME;
- Python ≥ 3.10, GTK ≥ 4.18, libadwaita ≥ 1.7, GtkSourceView 5;
- the `ruscallama-engine` package;
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

- **Header bar**: on the left **+** (new conversation); in the middle the program name and engine state; on the right the settings panel button and the main menu.
- **Conversation**: answers appear while they are generated. Code blocks are highlighted and have a copy button. Each answer has **Copy Answer** and a menu to save it as Markdown or save its code blocks.
- **Reasoning**: when on, the model's reasoning appears in a collapsible section above the answer.
- **Bottom bar**: attachments, message box, **Send** (which becomes **Stop** during an answer) and the speed in tokens per second.
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

## 7. Keyboard shortcuts

| Keys | Action |
|---|---|
| Enter | Send |
| Shift+Enter | New line |
| Esc | Stop the answer |
| Ctrl+N | New conversation |
| Ctrl+O | Attach files |
| Ctrl+S | Save the conversation as Markdown |
| F9 | Model settings |
| Ctrl++ / Ctrl+− / Ctrl+0 | Larger / smaller text / system size |
| Ctrl+? | Keyboard shortcuts |
| F10 | Main menu |
| Ctrl+W / Ctrl+Q | Close the window / Quit |

## 8. Privacy and security

- The engine listens only on **127.0.0.1**, on a free port chosen at every start.
- Every start creates a **temporary access key**, stored in `$XDG_RUNTIME_DIR/ruscallama/` with 0600 permissions: other users of the computer cannot use the model or read the conversations.
- The engine is built **without** the ability to download anything from the internet.
- Conversations are not saved automatically: they stay in memory until you save them.
- The engine has an AppArmor profile (in *complain* mode) that denies it the most sensitive folders of the home.
- Settings are in `~/.config/ruscallama/settings.json`.

Answers from a language model can be wrong: check important information.

## 9. Troubleshooting

| Problem | What to do |
|---|---|
| "ruscallama-engine is not installed" | `sudo apt install ruscallama-engine` |
| The engine stops at once | Open **Engine Log** from the menu: memory is often the cause; try a smaller model, less context or compressed context memory |
| Very slow | Turn on **Graphics Card (Vulkan)**; check the number of threads |
| The graphics driver hangs | Turn off **Graphics Card (Vulkan)** |
| The model loads without the graphics card but not with it | In **Graphics Card to Use** choose the dedicated card: on a laptop with two cards the engine may use the wrong one |
| Images are not accepted | You need an `mmproj` file next to the model and **Vision** on |

Support: info@ruscalinux.org — The note on the use of AI tools is in the About window and in the `NOTA-IA.md` file of the repository.
