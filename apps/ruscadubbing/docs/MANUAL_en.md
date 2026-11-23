# RuscaDubbing 1.99.3 — User Guide

**Version** 1.99.3 · **Author** Nunzio Curcuruto · **Distribution** RuscaLinux ([ruscalinux.org](https://www.ruscalinux.org/)) · **License** GNU GPL v3 or later

RuscaDubbing is the RuscaLinux **dubbing room**. From a video in its own language it makes:

- **subtitles** in the original language, in the dubbing language and in both together (SRT);
- the **dubbed audio** (Opus);
- the **dubbed video** (MKV or MP4): the original picture, the original and the dubbed audio, subtitles in both languages.

Everything happens **on this computer**, with three external engines under the MIT license: **whisper.cpp** (`ruscawhisper-engine`) transcribes, **llama.cpp** (`ruscallama-engine`) translates and gives the voice, **FFmpeg** mixes and writes the video.

---

## 1. Requirements

- RuscaLinux or Debian Stable, GNOME;
- Python ≥ 3.10, GTK ≥ 4.18, libadwaita ≥ 1.7;
- the packages `ruscawhisper-engine`, `ruscallama-engine` (with `llama-tts`) and `ffmpeg`;
- three models, the same as the other apps (next section).

A Vulkan graphics card makes everything much faster. On a laptop without one, a video of a few minutes still takes some patience.

## 2. Models

RuscaDubbing **has no models of its own**: it uses those you already copied for the other apps.

| Step | Model | Folder | Also used by |
|---|---|---|---|
| Transcription | Whisper (`ggml-….bin`) | `~/.local/share/ruscawhisper/models/` | RuscaTranscriber |
| Translation | GGUF language model | `~/.local/share/ruscallama/models/` | RuscaTranslator, RuscaLLama |
| Voice | Qwen3-TTS GGUF + mmproj | `~/.local/share/ruscanarrator/models/` | RuscaNarrator |

In **Preferences** you choose which one each step uses; the folder button opens the right folder. If one is missing, a bar at the top says so.

**The voice.** Without a reference voice the model invents a voice for every line. A dubbing needs **one voice**: make one with **Create a Voice** in RuscaNarrator and choose it in Preferences → **Reference Voice**. On first start RuscaDubbing picks the first voice it finds.

## 3. Dubbing a video

1. **Open** the video (Ctrl+O), drop it on the window, or from the file manager: **Open With → RuscaDubbing**.
2. Choose the **original language** (“Automatic” detects it) and the **dubbing language**.
3. Choose **what to make**: subtitles, dubbed audio, dubbed video.
4. Press **Dub** (Ctrl+Enter).

The window shows the four steps:

| Step | What happens |
|---|---|
| **Transcription** | Whisper writes the original subtitles. Pieces of one sentence separated by a short pause become a single line, so the voice says them together. |
| **Translation** | The language model translates the lines in groups, with the previous lines as context. For each line it knows **how many characters** it may use to fit its time; if a translation is much longer, it is asked for a short version, as an adapter would do. Then the model is closed, to leave the graphics card to the voice. |
| **Dubbing** | The voice says each line **at its time**. If it is too long it is sped up without changing the pitch, up to the maximum speed; if that is not enough it moves later: two lines never overlap. |
| **Mixing** | FFmpeg lowers the original audio while the voice speaks (music and effects stay, quieter) and writes the files. The picture is **copied** without re-encoding: no quality loss and a few seconds even for a film. |

**Stop** (Esc) interrupts at any time. At the end RuscaDubbing lists the files: a click opens them, **Watch** opens the video.

## 4. The files

Next to the video, or in the folder chosen in **Output Folder**. A video `film.mp4` dubbed from English to Italian gives:

| File | Content |
|---|---|
| `film.en.srt` | original subtitles |
| `film.it.srt` | translated subtitles |
| `film.en-it.srt` | both languages together: original above, translation below |
| `film.it.opus` | the dubbed audio alone |
| `film.it.mkv` | the dubbed video |

An existing file is never overwritten: the new one is called `film.it (2).mkv`.

In the dubbed video the **dubbed track is the default**; the original audio and the subtitles are extra tracks, tagged with their language, to choose in the player (in Videos/Totem: menu → **Languages** and **Subtitles**; in VLC: **Audio** → **Audio Track**). **MKV** accepts any video and copies the original audio as it is; **MP4** is more common on phones and TVs but does not accept every kind of picture: if it fails, choose MKV.

## 5. Original subtitles from a file

If you already have the original subtitles (the film's own, or RuscaTranscriber's corrected by hand), press the folder button in the **Original Subtitles** row and choose the `.srt` file: transcription is skipped and those are used. Set the **original language**: it cannot be detected from the text. This is also how to dub a video **without audio**.

For a careful dubbing: transcribe with RuscaTranscriber, correct the text, then give it to RuscaDubbing.

## 6. Original audio under the voice

**A little**, **Quite a lot** or **A lot**: how much the original audio is lowered while the dubbed voice speaks. It is the “voice-over” dubbing of documentaries: the original voice is barely heard underneath. Removing the original voice entirely while keeping music and effects needs separating voices from the rest: it will come in a future version.

## 7. Preferences

| Group | What |
|---|---|
| Appearance | Light, dark or system theme |
| Models | The model to transcribe, translate and give the voice |
| Voice | Reference voice; model voice (for models with named voices); **maximum speed** (how much a line may be sped up, 1.3× by default); **seed** (the same seed gives the same performance) |
| Engine | Graphics card on/off and which one; CPU threads; translation context |

## 8. Privacy

- **No data leaves the machine.** The only connection is to `llama-server`, on the computer itself (`127.0.0.1`), with a random key that changes at every start.
- Programs are started without a shell; FFmpeg reads only local files.
- Working files (extracted audio, lines, voice) are kept in `~/.cache/ruscadubbing/` and **deleted** at the end of each dubbing, at start and at close.

## 9. Rights and voices

Dub only videos you have the right to use. Each model has its own license, to check before publishing. Use as reference voice only your own voice or that of someone who gave you permission.

## 10. Shortcuts

| Keys | Action |
|---|---|
| Ctrl+O | Open a video |
| Ctrl+Enter | Dub |
| Esc | Stop |
| Ctrl+, | Preferences |
| Ctrl+? | Shortcuts |
| F10 | Main menu |
| Ctrl+W / Ctrl+Q | Close / Quit |

## 11. Troubleshooting

| Problem | Solution |
|---|---|
| The bar at the top says a model is missing | Copy the model into its folder (section 2) and reopen Preferences |
| The voice changes from line to line | Choose a **reference voice** (section 2) |
| Many lines sped up or moved | Raise the maximum speed a little, or use less dense subtitles |
| Some lines stay in the original language | The language model did not translate them: try a larger one |
| The MP4 video cannot be written | Choose **MKV** |
| Something is wrong | Main menu → **Engine Log** shows what the programs wrote |
