# RuscaSpeaking 1.99.3 — Manual

**Version** 1.99.3 · **Author** Nunzio Curcuruto · **Distribution** RuscaLinux ([ruscalinux.org](https://www.ruscalinux.org/)) · **License** GNU GPL v3 or later

RuscaSpeaking reads a **Markdown document** aloud, or **SRT subtitles** following their timing, with a **speech synthesis** model that runs **on this computer**, through `llama-tts` from **ruscallama-engine** (llama.cpp, an external component under the MIT license). The audio is saved as **WAV**, **FLAC**, **Opus** or **MP3**.

---

## 1. Requirements

- RuscaLinux or Debian Stable, GNOME;
- Python ≥ 3.10, GTK ≥ 4.18, libadwaita ≥ 1.7;
- the `ruscallama-engine` (with `llama-tts`) and `ffmpeg` packages;
- a **speech synthesis model** in GGUF with its **mmproj** file: see the next section.

## 2. The model

The model is not part of the program: it is two files you copy once.

1. Open the main menu → **Open the Models Folder** (the same entry is in **Preferences**). The folder is `~/.local/share/ruscaspeaking/models/`.
2. Copy the model **and** its mmproj into it, in the same folder. For example, from [ggml-org/Qwen3-TTS-12Hz-1.7B-Base-GGUF](https://huggingface.co/ggml-org/Qwen3-TTS-12Hz-1.7B-Base-GGUF):
   - `Qwen3-TTS-12Hz-1.7B-Base-Q8_0.gguf` (1.85 GB), or the `bf16` version for the best quality, or `Q4_K_M` if memory is short;
   - `mmproj-Qwen3-TTS-12Hz-1.7B-Base-bf16.gguf` (669 MB) or `…-Q8_0.gguf` (446 MB).
3. Go back to RuscaSpeaking: the model appears on its own, without restarting.

RuscaSpeaking pairs each model with the mmproj that has the same name (apart from the word "mmproj" and the precision, such as `Q8_0` or `bf16`); if the folder has a single mmproj it uses that one. Among several suitable mmproj files it picks the most precise. **Preferences** show which mmproj is in use. With several models it proposes the largest file, that is the most precise.

Every model has its own license, to be checked before publishing the audio. RuscaSpeaking downloads nothing.

## 3. Reading a document

1. **Open** the document (Ctrl+O), drag it onto the window, or from the file manager: **Open With → RuscaSpeaking**. `.md`, `.markdown` and `.txt` files can be opened.
2. The window shows **the text as it will be read**: without asterisks, hash signs, link addresses and footnote references; formulas as symbols.
3. Choose the **voice language** and press **Generate Audio** (Ctrl+Enter). The sentence being read is bold and underlined; the bar at the bottom shows the progress and the time left, with **Stop** (Esc).
4. When the audio is ready, listen to it in the bar at the bottom and save it from the **Save** button: **WAV** (Ctrl+S), **FLAC**, **Opus** or **MP3**.

How a document is read:

| Element | Reading |
|---|---|
| Headings | Read, followed by a long pause |
| Paragraphs | Read; long ones are split at the end of sentences |
| Lists | One item at a time; numbered lists read the number |
| Tables | One row at a time, cells separated by a short pause |
| Formulas | Read as Unicode symbols (x², α, ≈) |
| Horizontal rule | A longer pause |
| Code blocks, footnotes | Skipped, unless you turn them on in **Preferences** |

## 4. Reading subtitles

Open an `.srt` file: the window shows each subtitle with its time. With **Generate Audio** every sentence starts **at the time of its subtitle**, and the audio lasts until the end of the last subtitle. You can use it as a dubbing track, for example after a transcription made with RuscaDubbing.

- Tags such as `<i>` and `{\an8}`, sound descriptions in square brackets (`[music]`) and musical notes (♪) are not read; dialogue dashes are removed.
- Each sentence has the time until the next subtitle. If the voice is longer, it is **sped up** without changing the pitch, up to the **maximum speed** chosen in Preferences (1.3 times unless you change it).
- If that is not enough, the sentence **moves later** as much as needed: two voices never overlap. At the end RuscaSpeaking tells you how many subtitles it sped up and moved, and by how much at most.

To fit the timing better: a more concise language, a slightly higher maximum speed, or less dense subtitles.

## 5. Voice quality

- **The same voice for every sentence.** "Base" models such as Qwen3-TTS, without a **reference voice**, make up a voice for each sentence: the seed is not enough, because a different text gives a different voice. With a reference voice every sentence starts from the same voice, from beginning to end. There are two ways to get one:
  - **Create a Voice** (main menu, or Preferences → Voice). RuscaSpeaking reads a trial sentence with one of the model's voices. **Another Voice** tries another one; when you find one you like, give it a name and press **Keep This Voice**: it is saved in `~/.local/share/ruscaspeaking/voices/` and becomes the reference voice. The trial sentence is in the voice language chosen in the window.
  - **A recording**: in **Preferences**, the button next to **Reference Voice** chooses an audio file (WAV or MP3) with about 10 seconds of clear speech, without music or noise. Use your own voice, or a voice you have permission to use.

  The **Reference Voice** row lists the saved voices: you can change them at any time, or choose **None**. To rename or delete a voice, open the voices folder.
- **Model voice.** Some models, such as Pocket TTS, have ready-made voices: write the name in the **Model Voice** row.
- **Seed.** The same seed always gives the same reading, and it is what keeps the voice consistent from one sentence to the next. If you do not like a reading, change it.
- **Precision.** `bf16` sounds better than `Q8_0`, which sounds better than `Q4_K_M`; more precise files are larger and slower.
- **Volume.** **Adjust the Volume** brings all the audio to an even level (EBU R128, −16 LUFS, as in podcasts).
- **Formats.** WAV and FLAC lose nothing; Opus (160 kbit/s) and MP3 (highest quality) are smaller and fine for listening.

## 6. Speed

`llama-tts` reads one sentence at a time: for each sentence it loads the model, generates the voice and exits. It is slower than an engine that stays running, but it opens no port, not even inside the computer. With the **graphics card** reading is much faster; a long document or a film still takes time. The bar at the bottom estimates the time left.

## 7. Preferences

| Option | Effect |
|---|---|
| Theme | Follows the system, light or dark |
| Text Size | Of the text to read; also with Ctrl++ and Ctrl+−, Ctrl+0 returns to the system size |
| Model | Choice among the models found; under the name, the paired mmproj |
| Open the Models Folder | Opens `~/.local/share/ruscaspeaking/models/` |
| Reference Voice | None, one of the saved voices, or an audio file chosen with the button next to it |
| Create a Voice | Try the model’s voices and save the one you like (section 5) |
| Open the Voices Folder | Opens `~/.local/share/ruscaspeaking/voices/` |
| Model Voice | Name of a ready-made voice of the model (optional) |
| Read Code Blocks / Read Footnotes | Off by default |
| Maximum Speed in Subtitles | From 1 (never speed up) to 2 |
| Adjust the Volume | On by default |
| Seed | 42 unless you change it |
| Graphics Card (Vulkan) | On by default; turn it off if the driver causes problems |
| Graphics Card to Use | With more than one graphics card: **Automatic** lets the engine choose |
| CPU Threads | As many as the physical cores is recommended |

Settings are in `~/.config/ruscaspeaking/settings.json`.

## 8. Shortcuts

| Shortcut | Action |
|---|---|
| Ctrl+O | Open |
| Ctrl+Enter | Generate audio |
| Esc | Stop |
| Ctrl+S | Save as WAV |
| Ctrl+, | Preferences |
| Ctrl++ / Ctrl+− / Ctrl+0 | Larger text / smaller text / system size |
| Ctrl+? | Keyboard shortcuts |
| F10 | Main menu |
| Ctrl+W / Ctrl+Q | Close window / Quit |

## 9. Privacy and security

- Everything happens on this computer. RuscaSpeaking does not use the network in any way: `llama-tts` reads a text and writes a file, without opening ports.
- FFmpeg is started so that it reads local files only.
- Created voices stay in `~/.local/share/ruscaspeaking/voices/` until you delete them.
- While working, the audio is kept in `~/.cache/ruscaspeaking/`, readable by the user only; it is deleted when you discard the result, at start and on closing. The source document is never modified.
- No telemetry.

## 10. Troubleshooting

| Problem | What to do |
|---|---|
| "The voice engine is not installed" | Install or update `ruscallama-engine`: the version with `llama-tts` is needed |
| "No model found" | Copy the model **and** its mmproj into the models folder (section 2) |
| "Speech synthesis stopped with an error" | Usually an incomplete file (interrupted copy), an mmproj that does not belong to that model, or too little memory. Details are in the main menu → **Engine Log** |
| "Reference voice not found" | The file was moved: choose it again in Preferences |
| The voice changes from one sentence to the next | There is no reference voice: create one with **Create a Voice**, or choose a recording (section 5) |
| Wrong language or foreign accent | Check the **voice language**. Qwen3-TTS knows Italian, English, German, French, Spanish, Portuguese, Russian, Chinese, Japanese and Korean |
| Very slow | Turn on the graphics card and choose the dedicated one in **Graphics Card to Use**; a `Q4_K_M` model is faster |
| It hangs with the graphics card | Try another card, or turn off **Graphics Card (Vulkan)** |
| The audio cannot be heard in the window | GTK's audio and video support is missing: `sudo apt install libgtk-4-media-gstreamer`. The saved file plays in any player |

To try the engine from a terminal: `/usr/lib/ruscallama-engine/llama-tts --version`.

## 11. External components

| Component | License | Where |
|---|---|---|
| llama.cpp (`llama-tts`, © The ggml authors) | MIT | Package `ruscallama-engine`, in `/usr/lib/ruscallama-engine/` |
| Highlight rule of the Markdown engine, a port of markdown-it-mark (© Vitaly Puzrin, Alex Kocharin; ExecutableBookProject) | MIT (Expat) | `/usr/share/ruscaspeaking/markdown_it_mark.py` |

FFmpeg is not included: it is Debian's `ffmpeg` package, used as an external program.

Development note: see the **About** window or `NOTA-IA.md` in the RuscaLinux repository.

Support: info@ruscalinux.org
