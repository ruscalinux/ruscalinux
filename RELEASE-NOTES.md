# RuscaLinux @VERSION@

<!--
  Template. @VERSION@, @SUITE@, @ARCH@, @KERNEL@, @DESKTOP@, @ISO@, @SHA256@,
  @SIZE@, @DATE@ and @NVIDIA@ (the NVIDIA driver version) are filled in by
  build.sh from release.conf and the image that was actually built. Edit the prose below for each release;
  never type the version, the file name or the checksum by hand.
-->

> **@VERSION@ is a stable release.** The project uses a `.99` minor to mark a
> stable milestone — it is not a beta or a pre-release.

## Highlights

<!-- Rewrite this section for each release. Everything else is automatic. -->

- **RuscaMark**, a new Markdown editor: formatting appears as you type, the
  page stays centred like a sheet of paper, spelling is checked live, and
  the preview shows real tables whose cells wrap to the page width, and
  formulas as readable symbols. Text is set in Literata, a typeface made
  for long reading that also prints well. You can dictate with Vosk (word
  by word) or Whisper (by sentence, on the processor or on the graphics
  card you choose), turn an audio or video file into a Markdown document,
  and have the document read aloud with Piper — all on your computer.
- **RuscaHub**, a new AppImage manager: import an AppImage by drag and drop,
  add it to the GNOME menu with its original icon, run it or remove it.
- **RuscaCleaner** has been rewritten. It removes activity traces from the
  home folder, lists everything it does and does not do, and has a user
  manual in English and Italian.
- **One look for the in-house tools.** RuscaCleaner, RuscaHub and RuscaMark
  are now native GNOME (libadwaita) applications in the RuscaLinux plum and
  pink colours. They follow the system light or dark style, or the one you
  choose in their preferences, share the same About window and keyboard
  shortcuts, and RuscaHub asks before deleting an
  AppImage and moves it to the trash. RuscaMark's app ID is now
  `org.ruscalinux.RuscaMark`: if you pinned it to the dash, pin it again.
- **The tools carry the RuscaLinux emblem.** Every in-house tool's icon is
  now the plum ring of the RuscaLinux emblem, with the tool's own symbol in
  place of the paper plane, so the tools are easy to tell apart and easy to
  recognise as part of RuscaLinux in the dash, the app grid and GNOME
  Software.
- **RuscaWriter joins the in-house tools.** The book-writing program
  (chapters, notes, Markdown, typesetting and export to PDF, EPUB, ODT,
  DOCX…) now has the same GNOME look as the other tools, page themes with
  verified contrast, and opens `.rwr` projects with a double click. Tables,
  formulas and pictures appear in the preview, whose button shows when it is
  on, and tables and formulas in every export; pictures next to an imported
  Markdown file come into the project with it, and the PDF prints
  Greek, Cyrillic and every other script the chosen font contains.
- **A folder for the in-house tools.** All RuscaLinux OS Apps are gathered
  in the **RuscaLinux Apps** folder of the GNOME app grid. The folder is
  created at the first login of each user; you can rename, empty or delete
  it like any other folder.
- **New applications.** darktable (raw photo development), gImageReader
  (text recognition from images and scanned PDFs, with Tesseract in all its
  languages), Sigil (EPUB book editor), MediaInfo (technical details of audio
  and video files), Asunder (audio CD ripper), Gaupol (subtitle editor) and
  GPRename (batch file renaming).
- **26 languages everywhere.** All in-house tools follow the system language
  and are translated into the same 26 languages, now including Traditional
  Chinese and European Portuguese.
- **Local AI tools.** RuscaLLama (chat) and RuscaTranslator run language
  models on your own computer. RuscaLLama formats answers while they are
  being written, with tables and formulas shown as readable symbols
  (E = mc²). RuscaTranslator translates Markdown documents
  between all 26 languages, with Italian ↔ English linguistic knowledge, and
  detects the source language on its own, telling apart close variants
  (Ukrainian and Russian, Simplified and Traditional Chinese, European and
  Brazilian Portuguese). Models are not included: copy a GGUF file into
  `~/.local/share/ruscallama/models/`.
- **Images from a description.** RuscaLLama has a second view, Images:
  describe what you want to see, choose square, landscape or portrait and
  press Generate; a preview shows the image taking shape. Its engine,
  **ruscadiffusion-engine**, is stable-diffusion.cpp built from source with
  Vulkan and without any network code, started once per image: no server,
  no port. It runs single-file models (Stable Diffusion 1.5, SDXL, Turbo
  models) and models made of several files (FLUX, SD 3.5, Z-Image,
  Qwen-Image), recognised on their own. Models are not included: copy them
  into `~/.local/share/ruscadiffusion/models/`, or add the folder where they
  already are. An image can be attached to the conversation, and an answer
  can become the description of a new image.
- **Short videos.** A third view, Videos, creates clips of a few seconds
  from a description or from a starting image, with the same engine and
  video models such as Wan 2.2 TI2V 5B (Apache 2.0), which runs even on a
  6 GB graphics card. The result is an AVI video that RuscaLLama plays by
  itself; the time left is shown while it works. Any image of the Images
  view can be animated with "Animate in a Video".
- **Speech to text.** RuscaTranscriber transcribes a video or audio file with a
  Whisper model that runs on your own computer and saves the text as
  Markdown and the subtitles as SRT. Its engine, **ruscawhisper-engine**, is
  whisper.cpp built from source with Vulkan and without any network code.
  Models are not included: copy a ggml file (for example
  `ggml-large-v3-turbo.bin`) into `~/.local/share/ruscawhisper/models/`.
  On computers with more than one graphics card you choose which one to use.
- **Text to speech.** RuscaNarrator reads a Markdown document aloud, or SRT
  subtitles following their timing, with a speech synthesis model that runs
  on your own computer, and saves the audio as WAV, FLAC, Opus or MP3. It
  uses llama-tts from ruscallama-engine and opens no network port. Create a
  Voice lets you try the model's voices and keep one, so every sentence is
  read with the same voice. Models
  are not included: copy a GGUF model with its mmproj (for example
  Qwen3-TTS) into `~/.local/share/ruscanarrator/models/`.
- **A voice conversation.** RuscaLLisse lets you talk aloud with
  Ellittica, a digital woman with glasses and short hair who explains things
  simply and step by step. Only her animated face is on screen: nothing is
  written and nothing is saved, as in a real conversation. She listens with
  **ruscavosk-engine** (Vosk, with Kaldi and OpenFst), thinks with
  ruscallama-engine and speaks with **ruscapiper-engine** (Piper with
  espeak-ng), all three built from source, without network code. Her
  personality is a text file you can edit. Models and voices are not
  included: copy a Vosk model, a GGUF model and a Piper voice (for example
  `vosk-model-it-0.22`, a Ministral model and `it_IT-paola-medium`) and import
  them from the app.
- **A dubbing room.** RuscaDubbing takes a video in its own language and
  makes subtitles in both languages, the dubbed audio and a video with both
  audio tracks and both subtitle tracks. Whisper transcribes the speech, a
  language model translates each line so that it fits its time, and the
  voice of RuscaNarrator says it at the right moment over the lowered
  original sound. The picture is copied, not re-encoded. It uses the models
  of RuscaTranscriber, RuscaTranslator and RuscaNarrator: nothing new to
  download, and nothing leaves the computer. “Find a Similar Voice” measures
  the original speaker and suggests invented voices in the dubbing language
  with a similar register, so the dubbing keeps a natural accent. It
  translates whole sentences with notes on the whole talk, checks that each
  spoken sentence fits its time, splits subtitles by professional rules,
  remembers the work done on each video and can try just the first minute.
- **A pinball game.** RuscaPinball brings the “Amethyst” table, seen in
  perspective like the 1980s home computer pinball games: mushroom
  bumpers, a centre target that lights double bumpers, a dome kicker, the
  bonus trap, a ring of bonus lamps that counts down at the
  end of each ball, the SPECIAL for an extra ball and the R-U-S-C-A
  letters. Original table, graphics and sounds; keyboard or gamepad. It is
  in the RuscaLinux Apps folder and in the Games category.
- **NVIDIA graphics, optional.** The image includes the NVIDIA driver
  @NVIDIA@, with open kernel modules, for GTX 16, RTX 20 and later cards,
  RTX 50 included. RuscaLinux still starts and installs with the free
  drivers: the NVIDIA driver is chosen with the “… with NVIDIA driver”
  entries of the boot menu, once, at installation. With Secure Boot on,
  the RuscaLinux certificate must be enrolled once: see `INSTALL.md`. Older cards (GTX 900, GTX 1000) use the free drivers.
  Laptops with two graphics cards run the desktop on the integrated
  graphics and use the NVIDIA card for the programs that ask for it.
- **NVIDIA driver 620.** The optional NVIDIA driver moves from the 595
  branch to the new 620 branch.
- **ruscallama-engine** is llama.cpp 1.0.0, the latest stable release, built
  from source with Vulkan for NVIDIA, AMD and Intel graphics. It is built
  without HTTPS support and without its web interface, so it cannot download
  anything: nothing is sent over the internet. It now includes **llama-tts**
  for speech synthesis, used by RuscaNarrator and from the terminal.
- **SMPlayer** replaces VLC as the video player.
- **Foliate** reads EPUB and other e-books, with a clean reading view.
- **Magic wallpaper** redrawn for contrast: a rose-mauve background halfway
  between the plum paper planes and the cream stardust, without grain.
- **Archive Manager** (File Roller) opens, creates and extracts ZIP, 7z, TAR
  and other archives.
- **Traditional Chinese input**: the Zhuyin (Bopomofo) method used in Taiwan
  (Chewing), in Settings → Keyboard → Input Sources. Mozc Setup, needed only
  for Japanese input, no longer appears in the app grid: it opens from the
  Japanese input source's preferences.
- **Disk repair tools**, also in the live session: `fsck` for ext4, FAT,
  exFAT, NTFS, XFS and Btrfs, `smartctl` for disk health, `ddrescue` to copy
  a failing disk, and `testdisk`/`photorec` to recover partitions and files.
- **Python virtual environments** work out of the box: `python3 -m venv`.
- **Larger text in the graphical installer.** Text now scales with the
  screen, so the installer is just as readable on a 4K monitor as on a
  Full HD one. To choose the size yourself, add `ruscalinux.dpi=150` (or any
  value from 72 to 384) to the installer's boot line.
- **New default wallpaper, and a new one to choose.** The colourful plum and
  pink wallpaper is now the default with the light style; the dark one stays
  the default with the dark style. The light wallpaper becomes **Magic**:
  the same sky with stardust trails behind the paper planes, sparkles, and a
  ring of light shaped like the emblem. Choose it in Settings → Appearance.
- New boot splash.
- **Only RuscaLinux artwork.** The Debian desktop themes that nothing used
  (wallpapers, lock screens, boot splash and GRUB backgrounds) are no longer
  on the disk, and the Debian logo left in a few icons is now the RuscaLinux
  one. The Debian Reference guide is no longer installed.
- The **Extensions** app no longer appears in the app grid. It is still
  installed, and extensions work as before.
- **Shorter image name**: `@ISO@`, without `.hybrid`. The image is still a
  hybrid ISO and is written to a USB stick in the same way.
- Removed: the uBlock Origin extension for Firefox.

## The image

| | |
|---|---|
| **File** | `@ISO@` |
| **Size** | @SIZE@ |
| **SHA256** | `@SHA256@` |
| **Base** | Debian @SUITE@, @ARCH@ |
| **Desktop** | @DESKTOP@ |
| **Kernel** | Linux @KERNEL@ |
| **NVIDIA driver** | @NVIDIA@ (optional, from the boot menu) |
| **Released** | @DATE@ |

Hybrid ISO: a full live system plus its own installer, including a
speech-synthesis option for accessibility. Write it byte-for-byte to a USB
stick of 8 GB or larger.

Download: <https://sourceforge.net/projects/ruscalinux/files/@VERSION@/>

Verify before writing:

```sh
sha256sum @ISO@
sha256sum -c SHA256SUMS
```

## Build it yourself

```sh
sudo apt install live-build python3-pil openssl squashfs-tools
./build.sh
```

The build also needs the key of the NVIDIA repository in `local/nvidia/`,
downloaded once: see `docs/NVIDIA.md`.

The version of the image lives in `release.conf`. Each utility in `apps/`
carries the same version in its own `make-deb.sh`; `make-debs.sh` warns if
they differ.

## Licensing

Build scripts and original design sources: GPL-3.0. Third-party material keeps
its own licence. The name *RuscaLinux*, its logo and its emblem are not covered
by the GPL — see `TRADEMARK.md`.

RuscaLinux is built almost entirely from free software. Like Debian, it
includes the non-free firmware some hardware needs. It also includes, as an
option in the boot menu, the NVIDIA driver: proprietary software distributed
under the NVIDIA licence, with open-source kernel modules (MIT/GPL-2.0). The
free drivers are the default. Security fixes for the NVIDIA driver, like all
others, arrive with each new release.
