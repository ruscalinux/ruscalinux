# RuscaWriter — User Manual

| Field | Value |
|---|---|
| Program | RuscaWriter |
| Version | 1.99.2 |
| Project | RuscaLinux OS Tools |
| Website | https://www.ruscalinux.org |
| Source | https://github.com/ruscalinux/ruscalinux (folder `tools/ruscawriter`) |
| Contact | info@ruscalinux.org |
| Author | Nunzio Curcuruto (ruscalinux-dev) |
| License | GPL-3.0 or later |

---

## 1. What it is

RuscaWriter is a writing environment for books, designed for non-fiction. The window has three columns: the chapter list on the left, your text in the middle and the chapter's notes on the right. You write in Markdown, and the same program typesets the result and exports it to PDF, EPUB, AZW3, ODT, DOCX, HTML, Markdown or TXT.

The program works entirely on your machine: it never connects to the network.

---

## 2. Installation

Requirements: RuscaLinux or Debian Stable, GNOME, GTK 4.18 and libadwaita 1.7 or later, Python 3.10 or later. RuscaLinux ships RuscaWriter preinstalled.

Check the package integrity, then install it:

```bash
sha256sum -c SHA256SUMS
sudo apt install ./ruscawriter-ruscalinux_1.99.2_all.deb
```

Alternatively, use `sudo dpkg -i` followed by `sudo apt -f install` to pull in any missing dependencies.

Optional packages, recommended by the deb:

| Package | Purpose |
|---|---|
| `gir1.2-gtksource-5` | Markdown highlighting in the editor |
| `gir1.2-spelling-1` | Spell checking |
| `hunspell-en-gb`, `hunspell-it`, … | Spelling dictionaries per language |
| `hyphen-en-gb`, `hyphen-it`, … | Hyphenation in PDF |
| `python3-pyphen` | PDF hyphenation engine |
| `python3-pil` | Cover generator |
| `calibre` | Only for AZW3 (Kindle) export |

---

## 3. Launching and the window

From the GNOME applications menu, by searching for "RuscaWriter" in Activities, by double-clicking a `.rwr` file, or from a terminal:

```bash
ruscawriter                 # start the program
ruscawriter book.rwr        # open a project directly
```

At start, if you did not open a file, RuscaWriter asks whether to create a new project or open an existing one.

The window:

- **Header bar**: on the left show/hide chapters and **+** (new chapter); in the middle the project title; on the right show/hide notes, preview, Save and the **main menu**.
- **Main menu**: at the top new project, open, import and export; then the **Chapter** submenu, editorial sections, page setup and word goal; then search, dictionaries and paragraph reflow; then the **View** and **Appearance** submenus; at the bottom the Markdown guide, keyboard shortcuts and About.
- **Three columns**: chapters (with arrows to move them), text, chapter notes.
- **Bottom bar**: chapter words, characters and estimated pages, project total, spell-check language and text size.

The interface language is the system's (Settings → System → Region & Language), among the languages the RuscaLinux OS Tools are translated into. Slovak users see Czech; anything untranslated falls back to English.

---

## 4. The project

A project is a `.rwr` file: a `tar.gz` archive holding one Markdown file per chapter, one for each chapter's notes, the metadata in JSON and any attached images. The text can be recovered with ordinary tools even without RuscaWriter.

| Action | Menu | Shortcut |
|---|---|---|
| New project | Main menu → New project | Ctrl+N |
| Open | Main menu → Open | Ctrl+O |
| Save | Save button in the header bar | Ctrl+S |
| Import chapters from .md/.txt files | Main menu → Import as chapters | Ctrl+I |
| Editorial sections (frontispiece, colophon, cover) | Main menu → Editorial sections | — |
| Quit | — | Ctrl+Q |

**Autosave.** Every 60 seconds, if there are unsaved changes, RuscaWriter writes a copy called `filename.rwr.autosave` next to the project. If the program closes unexpectedly, it offers to recover that copy the next time you open the project. A normal save deletes the copy.

**Safe saving.** The project is first written to a temporary file in the same folder and then renamed. An interruption therefore leaves either the old project or the new one, never half a file.

---

## 5. Chapters and writing

| Action | Shortcut |
|---|---|
| New chapter | Ctrl+Shift+N |
| Rename chapter | F2 |
| Move up / down | Ctrl+Shift+↑ / ↓ |
| Find and replace | Ctrl+F |
| Insert image (PNG, JPEG, WebP) | Ctrl+Shift+I |
| Preview the chapter | Ctrl+E |
| Preview the whole book | Ctrl+Shift+E |
| Show line breaks | Ctrl+Shift+B |
| Markdown guide | Shift+F1 |
| Look up the word in the dictionary | Ctrl+D or Ctrl+click |

**Reflow paragraphs** (main menu) joins lines that were broken by hand, for example in text pasted from a PDF.

Markdown follows the CommonMark standard, as in RuscaMark and RuscaLLama: preview, highlighting and exports all read it the same way. Besides headings, bold, italic, lists, quotes, links, images and tables you can use code blocks between three backticks, task lists (`- [x]`), footnotes (`text[^1]` and, further down, `[^1]: the note`, which end up at the bottom of the chapter) and formulas (`$x^2$`, which become symbols). One rule differs from CommonMark, because it is more natural in a book: **every line break is a line break in the book too**, and lines written one under the other are not merged into a single paragraph. A blank line separates blocks of text. When exporting to Markdown, RuscaWriter adds the blank lines needed for the file to read the same in any program that follows CommonMark.

---

## 6. View and appearance

| Action | Shortcut |
|---|---|
| Show/hide the chapters column | Ctrl+L |
| Show/hide the notes column | Ctrl+R |
| Full screen | F11 |
| Larger / smaller text | Ctrl++ / Ctrl+− |
| Switch between light and dark | Ctrl+Shift+D |
| Keyboard shortcuts | Ctrl+? |

The View submenu also holds the writing font (Fonts…) and the **column width**: *Normal* (68 characters per line, the book measure, the default) or *Wide* (80). The column keeps its width when you move or hide the side columns and when you resize the window: it only re-centres. If there is less room, the text uses all the space available.

**Appearance.** The Appearance submenu offers three choices. *Automatic* follows GNOME's light or dark mode (Settings → Appearance) and changes with the system, even while you write. *Light* and *Dark* fix the choice. Ctrl+Shift+D switches between the two. Bars, menus and dialogs follow the common theme of the RuscaLinux OS Tools.

**Page themes.** The same submenu sets the colours of the writing page, the preview and the notes. There are two, each in a light and a dark version:

| Theme | Character |
|---|---|
| Ametista | The official RuscaLinux colours: a white page with a breath of pink, plum headings and code; in dark mode a plum page with pink headings. The default. |
| Classico | The style of a professional writing studio: a crisp white page, near-black ink, cool greys, and blue headings, code and selection; in dark mode a charcoal page with light-grey text and a muted blue. |

In both the writing text is around 11:1, headings, code and notes at least 7:1, and Markdown marks (`**`, `#`, `` ` ``) at least 4.5:1: subdued, but always readable.

---

## 7. Spell checking

Spell checking works when `gir1.2-spelling-1` and a Hunspell dictionary are installed. The language is chosen per document and saved in the project. Elided apostrophes (for example Italian *dell'anima*) are handled correctly. For British English, install `hunspell-en-gb` and `hyphen-en-gb`.

---

## 8. MDict dictionaries

RuscaWriter reads dictionaries in MDict format, with no extra software needed.

**Adding a dictionary.** Open main menu → Dictionaries. There are two ways.

- **Add folder…** is the recommended one: choose the dictionary's folder just as you downloaded it. RuscaWriter copies the whole folder into the library and adds every `.mdx` inside it, with its `.mdd` files, icon and style sheets.
- **Add** picks a single file. You may point at the `.mdx`, the `.mdd` or the `.png`: the program always takes the `.mdx` with the same name and brings along the files that belong to it.

An MDict dictionary is often a family of files sharing the same name:

| File | Contents | Use in RuscaWriter |
|---|---|---|
| `name.mdx` | Headwords and definitions | The dictionary itself |
| `name.mdd`, `name.1.mdd`, … | Pictures, sounds, style sheets | The entry's pictures, in "Show all" |
| `name.png` | Icon | Beside the name, in the list and on the sheet |
| `name.css` | Style | Copied along with the dictionary |

Sounds and style sheets are not used: the sheet shows text with bold and italics, not a web page. Pictures are taken only from the `.mdd` archives, never from the internet.

**Supported formats:** MDict engine 1.x, 2.x and 3.0; uncompressed, zlib or LZO; UTF-8, UTF-16, GB18030 and Big5 encodings; protected key index. Registered dictionaries, which need a purchase code, are not supported and are refused with a clear message.

**First opening.** The first time, the dictionary is indexed in the background with a progress bar. The index is kept in `~/.cache/ruscawriter/mdict/`, so from then on the dictionary is ready at once. If you delete that folder, the index is simply rebuilt.

**Looking up a word.** There are three ways:

| How | What to do |
|---|---|
| Keyboard | Cursor on the word (or the word selected) and **Ctrl+D** |
| Mouse | **Ctrl+click** on the word |
| Menu | Right-click on the word → **Look up** |

A small sheet with the definition appears beside the word. **Show all** opens the full entry with its pictures; a long entry scrolls inside the sheet.

To close the sheet, click its **✕**, click anywhere in the text, press **Esc**, or just carry on typing.

If the exact word is not in the dictionary, RuscaWriter tries its dictionary forms (*houses* → *house*, *case* → *casa*). Failing that, it shows the closest headword and says plainly that it is not the word you asked for.

**Dictionary folder.** By default, added files are copied into `~/.local/share/ruscawriter/dictionaries/`, and added folders become subfolders there. When you remove a dictionary you can delete its files too: the `.mdx` with its companions or, for a copied folder, exactly the files that were copied. Nothing outside the library is ever deleted. The same window lets you change the folder or turn copying off. The order of the list is the order in which dictionaries are searched; change it with the arrows.

**If a dictionary does not work.** The list shows "⚠" followed by the reason, and the other dictionaries keep working. If none of them works, the message appears in a window.

---

## 9. Export

Main menu → Export:

| Format | Notes |
|---|---|
| PDF | Book page sizes, binding margins, justified text, embedded fonts. Hyphenation needs `python3-pyphen` and `hyphen-<lang>`. |
| EPUB | With cover, frontispiece, colophon and table of contents |
| AZW3 | Needs Calibre (`ebook-convert`), run locally |
| ODT, DOCX | For LibreOffice or Word |
| HTML, Markdown, TXT | Simple, open formats |

### Page setup

Main menu → Page setup (Ctrl+Shift+P) sets the book's format and margins. The same dialog opens before every PDF export, together with the justification and hyphenation options.

| Field | Meaning |
|---|---|
| Format | A5, 17 × 24 cm, A4, 5 × 8 inches… |
| Preset | *Format margins* (the ones designed for each format), *Classical canon* (inside, top, outside and bottom in the proportion 2:3:4:6, as in traditional books), *Wide outer margin for notes*, *Manuscript* (1 inch on every side). Changing a value turns the preset into *Custom*. |
| Facing pages | Mirrored margins: the inside margin is on the left of odd pages and on the right of even ones. Without this option the margins are simply left and right. |
| Top, bottom, inside, outside | The four margins, in millimetres, centimetres or inches. |
| Gutter | Space added to the inside edge for the fold or glue of the binding. |

The preview shows the spread with the text block. Below it you read the size of the block and the characters per line: between 45 and 75 is comfortable, and outside that range a hint appears. A margin under 5 mm, or a text block that is too narrow or too short, turns the button off and says why.

Margins are saved **in the document**, one set per format, so a book reopened later prints as before. They apply to the PDF and also to ODT and DOCX, which open in LibreOffice or Word already laid out. Running heads and page numbers are centred on the text block.

---

## 10. Files used by the program

| Path | Contents |
|---|---|
| `~/.config/ruscawriter/settings.json` | Settings |
| `~/.local/share/ruscawriter/dictionaries/` | Added dictionaries |
| `~/.cache/ruscawriter/mdict/` | Dictionary indexes (safe to delete) |
| `<project>.rwr.autosave` | Automatic copy, next to the project |
| `/usr/share/ruscawriter/` | Installed program |
| `/usr/share/doc/ruscawriter/` | This manual and the Italian edition |

---

## 11. Troubleshooting

| Problem | What to do |
|---|---|
| The program does not start | Check that `python3`, `python3-gi` and `gir1.2-gtk-4.0` are installed; run `ruscawriter` from a terminal to read the error |
| No spell checking | Install `gir1.2-spelling-1` and `hunspell-<lang>` |
| PDF without hyphenation | Install `python3-pyphen` and `hyphen-<lang>` |
| AZW3 export not possible | Install Calibre, or export to EPUB instead |
| Dictionary marked "⚠" | Read the reason in the list; make sure you chose the `.mdx`, not the `.mdd` |
| Odd settings | Close the program and rename `~/.config/ruscawriter/settings.json` |
| Suspicious package | Run `sha256sum -c SHA256SUMS`, then reinstall |

---

## 12. Privacy and security

### Principles

| Principle | Rule |
|---|---|
| Processed data | Local only |
| Sending to remote servers | No |
| Sending over the internet | No |
| Telemetry | No |
| Dangerous or harmful commands | No |
| Personal data collection | No |
| Sensitive operations | Clear and user-controlled |

All data processed by RuscaWriter remains local. No data or files are sent to remote servers or over the internet. The program contains no dangerous or harmful commands for the operating system.

### How this is achieved

- **No network.** The code opens no connections. The two links in the About window (website and source) open in your browser only if you click them.
- **`.rwr` projects.** The archive is read into memory and never extracted to disk, so a malicious path inside it (such as `../../.bashrc`) cannot write anywhere. Limits of 20,000 entries and 1 GB uncompressed stop archives built to exhaust memory. Text with a broken encoding still opens, without crashing.
- **`.mdx` and `.mdd` dictionaries.** They are treated as untrusted files. Every size read from the file is checked against a ceiling before any memory is allocated, decompression is capped per block, and every read and back-reference of the LZO decompressor is bounds-checked. Definitions are cleaned before display: no scripts, no styles, no external links. Pictures come only from the dictionary's own `.mdd` archives (never from the internet or other files on disk); only PNG, JPEG, GIF and WebP are decoded, up to 8 MB each. When a folder is copied, symbolic links are not followed. The reader has been tested against hundreds of deliberately corrupted files, and it always answers with an error message, never a crash.
- **Ciphers.** RIPEMD-128, Salsa20/8 and XXH64 are there only to *read* dictionaries that use them, never to protect user data.
- **Atomic writes.** Projects and settings are written to a temporary file and then renamed.
- **External programs.** The only one is Calibre (`ebook-convert`). It runs only when you export to AZW3, without a shell, with arguments passed as a list, and with a 5-minute limit.
- **Permissions.** Project files are created readable by their owner only (0600). The program neither needs nor uses administrator privileges; only installing the package requires `sudo`.
- **Dependencies.** Only the Python standard library and GTK 4. Optional components come from the Debian repositories.
- **Integrity.** Every package ships with `SHA256SUMS`: always check it before installing.

### Reporting a security issue

Write to **info@ruscalinux.org**. Include the version (main menu → About), the steps to reproduce the problem and, if you can, a sample file. Please do not publish the details of a vulnerability before it is fixed. Only the latest released version is supported.

---

## 13. Licenses

The code is released under GPL-3.0 or later: https://www.gnu.org/licenses/gpl-3.0.html

| Component | License | Path |
|---|---|---|
| EB Garamond (font) | SIL OFL 1.1 | `assets/EBGaramond-*.ttf`, `assets/EBGaramond-OFL.txt` |
| Courier Prime (font) | SIL OFL 1.1 | `assets/CourierPrime-*.ttf`, `assets/CourierPrime-OFL.txt` |

The MDict reader, the decompressors and the ciphers were written from scratch for this project and are covered by GPL-3.0.

---

## 14. AI note

The note on the use of AI tools is in the program's About window and in the `NOTA-IA.md` file of the RuscaLinux repository.
