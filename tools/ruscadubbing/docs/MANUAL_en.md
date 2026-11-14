# RuscaDubbing 1.99.3 — Manual

**Version** 1.99.3 · **Author** Nunzio Curcuruto · **Distribution** RuscaLinux ([ruscalinux.org](https://www.ruscalinux.org/)) · **License** GNU GPL v3 or later

RuscaDubbing turns the speech of a **video** or **audio file** into text, with a **Whisper** speech recognition model that runs **on this computer**, through **ruscawhisper-engine** (whisper.cpp, an external component under the MIT license). The result is saved as a **Markdown** document and as **SRT subtitles**.

---

## 1. Requirements

- RuscaLinux or Debian Stable, GNOME;
- Python ≥ 3.10, GTK ≥ 4.18, libadwaita ≥ 1.7;
- the `ruscawhisper-engine` and `ffmpeg` packages;
- a **Whisper model** in ggml format (a `.bin` file): see the next section.

## 2. The model

The model is not part of the program: it is a file you copy once.

1. Open the main menu → **Open the Models Folder** (the same entry is in **Preferences**). The folder is `~/.local/share/ruscawhisper/models/`.
2. Copy the model you prefer into it, for example `ggml-large-v3-turbo.bin`.
3. Go back to RuscaDubbing: the model appears on its own, without restarting.

Whisper models for whisper.cpp have names such as `ggml-tiny.bin`, `ggml-base.bin`, `ggml-small.bin`, `ggml-medium.bin`, `ggml-large-v3.bin` and `ggml-large-v3-turbo.bin`. Larger models are more accurate, slower and need more memory; those with `.en` in the name understand English only. RuscaDubbing downloads nothing: you get the file from another computer or with the browser, and every model has its own license, which you must respect.

With several models in the folder, RuscaDubbing proposes the largest; change it in **Preferences** (Ctrl+,). The administrator can put models for all users in `/usr/share/ruscawhisper/models/`.

## 3. Transcribing

1. **Open** the video or audio file (Ctrl+O), or drag it onto the window, or from the file manager: **Open With → RuscaDubbing**.
2. Choose the **spoken language**. **Detect language** lets the model decide by listening to the first seconds: convenient, but it can be wrong when the file starts with music or silence.
3. Press **Transcribe** (Ctrl+Enter). The text appears as it is recognized; the bar at the bottom shows the progress, with **Stop** (Esc).
4. Save from the **Save** button in the title bar: **Save as Markdown…** (Ctrl+S) or **Save Subtitles (SRT)…** (Ctrl+E). You can save both.

The proposed name is that of the source file, in the same folder: `lesson.mp4` → `lesson.md` and `lesson.srt`. An `.srt` file with the same name as the video, next to the video, is loaded automatically by most players.

How long it takes depends on the model and on the computer: with a large model and no graphics card, one hour of speech can take more than one hour.

## 4. What you get

| Format | Content |
|---|---|
| Markdown (`.md`) | A heading with the file name and the text in paragraphs. A new paragraph starts after a pause of at least two seconds, or at the end of a sentence when the paragraph is already long. Open it with RuscaMark or RuscaWriter |
| SRT (`.srt`) | One numbered subtitle for each recognized segment, with its start and end time. UTF-8 |

In the Markdown file speech stays text: asterisks, hash signs, addresses and other characters that Markdown would read as formatting are protected with a backslash.

**Automatic transcription must be reviewed.** A model can get names, numbers and rare words wrong, and during silence or music it can write sentences nobody said. To correct the text, open the saved file with RuscaMark; for subtitles, use a text or subtitle editor.

## 5. Input formats

Video and audio that **FFmpeg** can read: MP4, MKV, WebM, MOV, AVI, MPEG, MP3, WAV, FLAC, Ogg, Opus, M4A and others. For a video, the first audio track is used. The source file is never modified.

## 6. Preferences

| Option | Effect |
|---|---|
| Theme | Follows the system, light or dark |
| Text Size | Size of the transcript text; also with Ctrl++ and Ctrl+−, Ctrl+0 returns to the system size |
| Model | Choice among the models found in the models folders |
| Open the Models Folder | Opens `~/.local/share/ruscawhisper/models/` in the file manager |
| Graphics Card (Vulkan) | Much faster; off by default because some drivers hang |
| CPU Threads | As many as the physical cores is recommended |

Settings are in `~/.config/ruscadubbing/settings.json`.

## 7. Shortcuts

| Shortcut | Action |
|---|---|
| Ctrl+O | Open |
| Ctrl+Enter | Transcribe |
| Esc | Stop |
| Ctrl+S | Save as Markdown |
| Ctrl+E | Save subtitles (SRT) |
| Ctrl+, | Preferences |
| Ctrl++ / Ctrl+− / Ctrl+0 | Larger text / smaller text / system size |
| Ctrl+? | Keyboard shortcuts |
| F10 | Main menu |
| Ctrl+W / Ctrl+Q | Close window / Quit |

## 8. Privacy and security

- Everything happens on this computer. RuscaDubbing does not use the network in any way: not even the local connections other tools use to talk to their engine.
- The engine (`whisper-cli`) contains no network code: the package build checks it. It starts, transcribes one file and exits.
- FFmpeg is started so that it reads local files only.
- While working, the extracted audio is kept in `~/.cache/ruscadubbing/`, readable by the user only; it is deleted at the end of every transcription, at start and on closing.
- No telemetry.

## 9. Troubleshooting

| Problem | What to do |
|---|---|
| "ruscawhisper-engine is not installed" | `sudo apt install ruscawhisper-engine` (RuscaLinux already has it) |
| "No model found" | Copy a model into the models folder (section 2) |
| "Could not read the audio of the file" | The file has no audio track, is damaged or is not a video or audio file. The message shows the FFmpeg error |
| "Speech recognition stopped with an error" | Usually the model is incomplete (interrupted copy) or there is not enough memory: try a smaller model. Details are in the main menu → **Engine Log** |
| "No speech recognized" | The file contains no voice, or the chosen language is not the spoken one |
| Text in the wrong language | Choose the language by hand instead of **Detect language** |
| Very slow | Use a smaller model, or turn on **Graphics Card (Vulkan)** in Preferences |
| It hangs with the graphics card | Turn off **Graphics Card (Vulkan)** |

To try the engine from a terminal: `/usr/lib/ruscawhisper-engine/whisper-cli --version`.

## 10. External components

| Component | License | Where |
|---|---|---|
| whisper.cpp (© The ggml authors) | MIT | Package `ruscawhisper-engine`, in `/usr/lib/ruscawhisper-engine/` |

FFmpeg is not included: it is Debian's `ffmpeg` package, used as an external program.

Development note: see the **About** window or `NOTA-IA.md` in the RuscaLinux repository.

Support: info@ruscalinux.org
