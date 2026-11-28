# RuscaMark 1.99.3 Manual

RuscaMark is the Markdown editor of the RuscaLinux OS Apps. It is designed for writing articles, reports, notes and documentation: formatting appears as you type, the page stays centred like a sheet of paper and all work happens on your own computer.

| Field | Value |
|---|---|
| Version | 1.99.3 |
| Author | Nunzio Curcuruto (ruscalinux-dev) |
| Website | [ruscalinux.org](https://www.ruscalinux.org) |
| Contact | info@ruscalinux.org |
| License | GPL-3.0 — <https://www.gnu.org/licenses/gpl-3.0.html> |

---

## 1. Requirements and installation

| Requirement | Value |
|---|---|
| System | RuscaLinux or Debian Stable |
| Desktop | GNOME |
| Graphics libraries | GTK 4.18 or later and libadwaita 1.7 or later |
| Language | Python 3.10 or later |

Before installing, verify the package in the folder that contains the `SHA256SUMS` file:

```bash
sha256sum -c SHA256SUMS
```

Recommended installation:

```bash
sudo apt install ./ruscamark-ruscalinux_1.99.3_all.deb
```

Alternatively `sudo dpkg -i ruscamark-ruscalinux_1.99.3_all.deb`, followed by `sudo apt -f install` if dependencies are missing.

Recommended packages (installed automatically by `apt` when available):

| Package | Purpose |
|---|---|
| `gir1.2-gtksource-5` | Advanced editor: undo/redo, highlighted search |
| `gir1.2-spelling-1` | Live spell checking |
| `hunspell-it`, `hunspell-en-gb` | Italian and British English dictionaries |
| `ruscavosk-engine`, `ruscawhisper-engine` | Dictation and transcription of audio files (section 12) |
| `ruscapiper-engine` | Reading aloud |
| `pipewire-bin`, `ffmpeg` | Microphone and playback; reading audio and video files |

For other languages install the matching dictionary, for example `hunspell-fr` or `hunspell-de-de`.

## 2. Launching

Open RuscaMark from the GNOME applications menu or by searching for it in Activities. From a terminal:

```bash
ruscamark               # new document
ruscamark report.md     # open a file
```

On first launch RuscaMark shows a welcome document that introduces its features; from then on it opens with an empty document.

You can also drag a `.md` file into the window.

## 3. The window

- **Header bar**: New and Open on the left; the dictation microphone, preview, Save and the main menu on the right. The main menu also holds Import from Audio, export, live rendering, spell checking, full screen, formatting, search, word goal, dictation, Read Aloud, Preferences, Keyboard Shortcuts and About.
- **Typeface**: the text is set in **Literata**, a typeface designed for long reading on screen that also prints well; it is included with RuscaMark and also used in the PDF. You can choose another one in Preferences.
- **Light or dark style**: RuscaMark follows the GNOME setting; in Preferences you can also force the light or the dark style.
- **Writing page**: the text sits in a centred column whose width is set in Preferences (68 characters by default). The margins are recalculated whenever you resize, maximise or full-screen the window, and when you open the preview.
- **Status bar**: words, characters and lines, cursor position and word goal.
- **Spelling bar**: appears below the text when spell checking is on.
- **Voice bar**: appears above the status bar during dictation and reading aloud, with the **Stop** button (section 12).

## 4. Two ways to view your text

**Live rendering (Ctrl+L)** — the default mode. Headings, bold, italic, code, links, quotes and lists take on their final look immediately and the markers (`**`, `#`, `>`…) are hidden. When you move the cursor onto an element, its syntax reappears so you can edit it. Tables stay in a monospaced font, so aligned columns remain aligned. Live rendering reads Markdown exactly as the preview and the exports do, even when bold or italic text continues on the next line. `$…$` formulas appear in italics, with real superscripts and subscripts (`x^2`, `a_{i}`); the `$$` lines of multi-line formulas disappear and the formula is centred; the backslashes of escapes (`\*`) and of forced line breaks are hidden; `---` becomes a line. List dashes stay dashes: a text editor cannot show a character other than the one written in the file.

**Classic preview (Ctrl+P)** — splits the window: source with syntax colouring on the left, the laid-out document on the right. Only the preview shows real images, tables drawn as grids and footnotes collected at the end. With the light style the preview uses the colours of the PDF and HTML theme chosen in Preferences; with the dark style it stays plum.

The two modes are mutually exclusive: turning one on turns the other off.

## 5. Markdown quick guide

### Text

| You type | You get |
|---|---|
| `**bold**` or `__bold__` | **bold** |
| `*italic*` or `_italic_` | *italic* |
| `***both***` | ***both*** |
| `~~strikethrough~~` | ~~strikethrough~~ |
| `==highlight==` | highlighted text |
| `` `code` `` | `code` |
| `\*not italic\*` | \*not italic\* (the backslash cancels the marker) |

To break a line without starting a new paragraph, end the line with two spaces or with `\`. A blank line separates paragraphs.

### Headings

```markdown
# Level 1 heading
## Level 2 heading
###### Level 6 heading

Alternative level 1 heading
===========================

Alternative level 2 heading
---------------------------
```

In exported HTML every heading gets an anchor (`id`), handy for internal links such as `[see the results](#results)`.

### Lists

```markdown
- item
- another item
  - nested item (indent by two spaces)

1. first
2. second

3. a list may start at any number
```

Task lists:

```markdown
- [x] draft finished
- [ ] review
```

### Quotes

```markdown
> A quote can span several lines
> and contain **formatting**.
>
> > Nested quotes use more `>`.
```

### Links

```markdown
[link text](https://ruscalinux.org "optional title")
<https://ruscalinux.org>
https://ruscalinux.org          (bare addresses become links)

Reference links: see [Debian][deb].

[deb]: https://debian.org "Debian"
```

Reference links keep long articles readable: the definitions can live at the end of the document.

### Images

```markdown
![Image description](img/chart.png "optional title")
```

- The path can be relative to the document's folder (recommended), absolute, or `file://`.
- An image alone on its own line is shown at full page width in the preview, scaled down to the column width and never enlarged.
- Images on the internet (`https://…`) are **not downloaded** by the preview, to protect your privacy: a notice is shown instead. In exported HTML they stay as links and the browser loads them.
- The text in square brackets is the alternative description: always write it, it matters for accessibility.

### Tables

```markdown
| Item     | Q1    | Notes    |
|:---------|------:|:--------:|
| Revenue  | 1,200 | on track |
| Costs    |   800 | `ok`     |
```

Colons in the separator row set the alignment: `:---` left, `---:` right, `:---:` centre. To put a vertical bar inside a cell, write `\|`. There is no need to align columns by hand: **Ctrl+Shift+T** does it (see section 6).

### Footnotes

```markdown
The figure is an estimate[^source].

[^source]: Internal survey, September 2026.
```

Footnotes are numbered in the order they appear in the text and collected at the end of the document.

### Code

````markdown
```python
print("Hello")
```
````

Blocks fenced with `~~~` and blocks indented by four spaces are accepted too.

### Horizontal rule

A line containing `---`, `***` or `___` (preceded by a blank line).

## 6. Writing commands

They are in the main menu and have dedicated shortcuts.

| Command | Shortcut | Behaviour |
|---|---|---|
| Bold | Ctrl+B | Wraps the selection in `**…**`; if it is already bold, removes it. With no selection inserts `****` with the cursor in the middle. |
| Italic | Ctrl+I | Same as above with `*…*`. |
| Heading 1…6 | Ctrl+1 … Ctrl+6 | Turns the current line into a heading of that level. |
| Normal text | Ctrl+0 | Removes the `#` from the current line. |
| Insert link | Ctrl+K | With text selected creates `[text](https://)` and selects the address for you to replace; with a URL selected creates `[](URL)` and places the cursor on the text. |
| Insert image | Ctrl+Shift+I | Pick an image file; inserts `![name](path)`. If the document is already saved, the path is relative to its folder, otherwise absolute. |
| Insert/align table | Ctrl+Shift+T | Outside a table inserts a three-column table; with the cursor inside a table realigns all its columns, keeping the chosen alignment and handling wide characters (Chinese, Japanese, Korean). |

Tip: save the document before inserting images, so paths are relative and the document stays portable together with its folder.

## 7. All shortcuts

| Shortcut | Action |
|---|---|
| Ctrl+N | New document |
| Ctrl+O | Open/Import Markdown |
| Ctrl+S | Save |
| Ctrl+Shift+S | Save As |
| Ctrl+Shift+E | Export HTML |
| Ctrl+Shift+P | Export PDF |
| Ctrl+L | Live rendering |
| Ctrl+P | Preview |
| F11 | Full screen |
| F7 | Spell checking on/off |
| F10 | Main menu |
| Ctrl+, | Preferences |
| Ctrl+? | Keyboard shortcuts |
| Ctrl+Z / Ctrl+Shift+Z | Undo / Redo |
| Ctrl+F | Find |
| Ctrl+H | Find and replace |
| Ctrl+B / Ctrl+I | Bold / Italic |
| Ctrl+K | Link |
| Ctrl+Shift+I | Image |
| Ctrl+Shift+T | Insert or align table |
| Ctrl+1 … Ctrl+6, Ctrl+0 | Heading level / normal text |
| Ctrl+Shift+D | Dictation on/off |
| Ctrl+Shift+R | Read aloud / stop reading |
| Ctrl+Shift+O | Import from audio |
| Ctrl+W | Close the window |
| Ctrl+Q | Quit |

The full list also opens from the program with **Ctrl+?** or from the main menu → **Keyboard Shortcuts**.

## 8. Find and replace

**Ctrl+F** opens the search bar, **Ctrl+H** adds the replace field.

- **Enter** or the down arrow jumps to the next match, the up arrow to the previous one; the search wraps around at the end.
- **Aa** makes the search case-sensitive.
- **Replace** changes the current match and moves on; **All** replaces every occurrence in a single step, which Ctrl+Z can undo.
- **Esc** closes the bar.

## 9. Spell checking

Press **F7** or choose **Spell checking** from the main menu. Unknown words are underlined as you type; **right-click** a word for suggestions or to add it to your personal dictionary. The dictionary language is chosen from the drop-down in the spelling bar and is independent of the interface language: you can have Italian menus and check a British English text (`en_GB`, package `hunspell-en-gb`).

For Italian and French, RuscaMark adds the elision fragments (`dell'`, `quest'`, `qu'`, `jusqu'`…) to your personal dictionary so they are not flagged as errors. Whether spell checking is on or off is remembered across restarts.

Checking uses only the dictionaries installed on your computer: your text is never sent over the network.

## 10. Word goal

Click **🎯 Goal** in the status bar (or use the menu) and set the number of words to reach; 0 turns it off. A progress bar shows how many words are left and changes colour when the goal is reached.

## 11. Exporting to PDF and HTML

PDF and HTML share the **same style**, whatever the editor's light or dark style: that of the **theme** chosen in Preferences → Export → *PDF and HTML theme*. With the light style the preview uses the theme's colours too.

### Themes

| Theme | Look |
|---|---|
| **RuscaLinux – Guide** (default) | The style of the RuscaLinux OS Apps reference guides: level-1 heading in a **banner** with a pink-to-plum gradient, plum level-2 headings with a pink rule, code on dark plum with a pink bar, tables with a plum header, text in Literata. |
| **Neutral** | Plain greys: heading with a rule, code on light grey, blue links. Prints well in black and white too. |
| **RuscaLinux – Strip** | The RuscaLinux palette, lighter: a gradient strip at the top of the first page, plum heading without a box, code on dark plum, split footer (title on the left, pages on the right). |
| **Classic** | A serif typeface (Literata) and sepia tones, like a book. |
| **Sea** | Blues, with the gradient heading banner. |

In every theme the paragraph right after the main heading is an introduction in a larger size, inline code is a coloured "pill", tables span the full width with alternating rows, and every page ends with the footer "*title* - page *N* / *total*", where the title is the first level-1 heading (or the file name). There is no reference to the program or the website.

### Personal themes

A theme is a `.css` file with variables, like a style sheet. To make one:

1. In Preferences → Export press **Open Folder** next to *Personal themes*: `~/.local/share/ruscamark/themes/` opens.
2. Copy one of the included themes there from `/usr/share/ruscamark/themes/` (`ruscalinux.css` explains every variable) and give it a new name, for example `my-theme.css`.
3. Change the values and choose the theme in Preferences (reopen them if they were open). Exports read the file again every time, so there is no need to restart.

A theme can also change just a few things and take the rest from another theme with `--base`:

```css
:root {
  --name: "Blue neutral";
  --base: neutral;
  --title: #1A5FB4;
  --rule-h2: #99C1F1;
}
```

The main variables: text and heading colours (`--fg`, `--title`, `--h3`, `--link`…), code (`--code-bg`, `--pre-bg`, `--pre-bar-width`…), quotes, tables (`--th-bg`, `--stripe`), typefaces (`--font`, `--mono`, lists of families as in `font-family`), heading shape (`--h1-style: banner | text | rule`), top strip (`--strip: none | top`) and footer (`--footer-align: center | split`). An invalid value is ignored and the base theme's value stays. RuscaMark reads only the variables: other CSS rules in the file have no effect, and a file with the same name as an included theme replaces it.

### PDF

**Ctrl+Shift+P** (or menu → *Export PDF…*) creates the PDF file directly, without going through the print dialog.

- The paper size is the system default (A4 in Europe, Letter in the United States), with 2 cm margins; text is set at 10 points.
- Long paragraphs continue on the next page; a heading is never left alone at the bottom of a page; short code blocks are never split, long ones continue on the next page with their box.
- Long text wraps inside table cells and, when a table continues on the next page, the header row is repeated.
- Local images are inserted at their natural size, scaled down if wider than the page. Remote images are not downloaded: their alternative text is shown instead.
- Links are clickable: web and e-mail links open the browser or the mail program, internal links such as `[go to the results](#results)` jump to the heading. Links to files or relative paths stay as text, because outside the document's folder they would lead nowhere; an internal link to a heading that does not exist also stays as text.

### HTML

**Ctrl+Shift+E** creates an HTML page in the style described above, with the title taken from the first level-1 heading and the document language taken from the spelling dictionary in use. On screen the document appears as a white sheet centred on a lightly tinted background.

- **Local images**: paths are recalculated relative to the folder where you save the HTML, so they work even when exporting to a different folder.
- **Single file**: when "Embed images in HTML export" is on in Preferences, images are stored inside the file (base64). The file is larger but can be sent or moved on its own.
- **Printing from the browser**: the HTML includes an A4 print style with 2 cm margins, background colours kept, headings kept with the following text, code, quotes and images not split, and the same footer as the PDF (in browsers that support CSS page margins, such as Chromium and its derivatives).

HTML written inside the Markdown (for example `<br>` or `<div>`) is not executed but shown as text: this is a safety choice.

## 12. Voice: dictation, transcription and reading aloud

RuscaMark writes what you say, turns an audio or video file into a document and reads aloud. It uses the engines of the RuscaLinux OS Apps, which are separate packages: **ruscavosk-engine** (Vosk), **ruscawhisper-engine** (whisper.cpp) and **ruscapiper-engine** (Piper). If one is missing, RuscaMark says so when it is needed and in Preferences → Voice. Models and voices are not in the packages: copy them into the folders shown below; each one has its own licence, which must be respected.

### Dictation

Press the **microphone** in the header bar (**Ctrl+Shift+D**) and speak. The voice bar appears above the status bar, with the microphone level, the state and, with Vosk, the words being recognised. **Stop** (or Ctrl+Shift+D again) stops listening; everything you have already said is still written.

**The draft (default).** Dictated text does not go straight into the document: it collects in a **draft** below the voice bar, sentence after sentence. You can correct it with the keyboard even while you keep speaking: new sentences are added at the end and the cursor stays where you are correcting. **Insert** (or **Ctrl+Enter** in the draft) puts it into the document at the cursor, in a single step that Ctrl+Z undoes; **Discard** empties it. After **Stop** the draft stays until you insert or discard it, and if you close the window RuscaMark asks what to do with it. So you can dictate calmly: a long pause truncates nothing, at most it starts a new sentence in the draft. If you prefer each sentence to go straight into the document, turn off *Check sentences before inserting* in Preferences → Voice.

**Pause.** Closes the microphone without stopping dictation: the sentence you were saying is finished and written, the model stays loaded, and **Resume** reopens the microphone at once.

**Delay.** If recognition falls behind your speech (it happens with large models on slow processors), the bar shows by how many seconds, for example "3 s behind": no word is lost, it just arrives later. If the delay keeps growing, use a smaller model.

Choose the engine in Preferences → Voice → *Engine*:

| | Vosk | Whisper |
|---|---|---|
| How it writes | Word by word while you speak; the sentence enters the text after a one-second pause | One sentence at a time, after each pause of about 0.7 seconds |
| Punctuation and capitals | You say them (see below) | It writes them itself |
| Accuracy | Good | Very good |
| Where it runs | Always on the processor | On the processor or on the graphics card (Vulkan) |
| Models | Folders in `~/.local/share/ruscavosk/models/`, for example `vosk-model-en-us-0.22` or `vosk-model-small-en-us-0.15` | `.bin` files in `~/.local/share/ruscawhisper/models/`, for example `ggml-large-v3-turbo.bin` |

With Whisper each sentence starts the engine, which reloads the model: on the graphics card a large model answers in a couple of seconds; for dictating on the processor a small model such as `ggml-small.bin` is better. Whisper also receives the last words already written, so it keeps the same style and punctuation.

**Voice commands.** While dictating you can say commands, in English or Italian: the full list is in the main menu → **Voice Commands…**, in the **?** button of the voice bar and in Preferences → Voice. Turn them off with *Voice commands*.

| You say | It writes | When |
|---|---|---|
| comma · full stop / period · colon · semicolon | `,` `.` `:` `;` | Vosk only (Whisper writes signs itself) |
| question mark · exclamation mark / exclamation point | `?` `!` | Vosk only |
| open parenthesis · close parenthesis · open quote · close quote | `(` `)` `“` `”` | Vosk only |
| new line · new paragraph | a new line · an empty line | Always |
| heading (or heading one) · heading two (or subheading) · heading three | `#` `##` `###` | At the start of a sentence |
| bullet · numbered list · quote | `-` `1.` `>` | At the start of a sentence |
| start bold … end bold | `**…**` | Always |
| start italic … end italic | `*…*` | Always |

Examples, with a short pause between sentences:

- "heading two introduction" → `## Introduction`, then you continue in a new paragraph;
- "bullet milk" · "bullet bread" → two list items, `- Milk` and `- Bread`; with "numbered list" the numbers go on by themselves (`1.`, `2.`…);
- "it is start bold very end bold important" → `it is **very** important`.

Line Markdown commands count only at the start of a sentence (that is, after a pause) or after "new line": so "the heading of the page", said in the middle of a sentence, stays text. After a full stop, question mark, exclamation mark, new line and a Markdown marker the next word gets a capital letter. With Vosk "period" always counts as a sign, even inside a sentence: "the period of" becomes "the. Of". If that happens often, use Whisper or turn the commands off. In Italian: *virgola, punto, punto interrogativo, a capo, nuovo paragrafo, titolo uno/due/tre, sottotitolo, elenco, elenco numerato, citazione, inizio/fine grassetto, inizio/fine corsivo*; other languages have no commands.

Speech is text: if you say something Markdown would read as formatting (an asterisk, "1." at the start of a line), RuscaMark protects it with a backslash, as RuscaTranscriber does.

**Spoken language.** *Same as the document* (default) uses the language of the spelling dictionary; you can choose one of the 24 languages of the RuscaLinux OS Apps, or *Automatic* (Whisper only). With Vosk the model decides the language: RuscaMark uses the one chosen in Preferences or, with *Automatic choice*, the largest one for the spoken language.

**Processor or graphics card (Whisper).** In Preferences → Voice → Whisper, *Run on* is *Processor (CPU)* (default) or *Graphics card (Vulkan)*. With the graphics card, *Card to use* offers *Automatic* and the computer's integrated and dedicated cards, with their memory: the choice is saved by name, and if the card is gone the engine decides. If a card's driver gives trouble, go back to the processor. Vosk and Piper always run on the processor.

### Import from Audio

Main menu → **Import from Audio…** (**Ctrl+Shift+O**): choose an audio or video file, in any format FFmpeg can read. The engine is the dictation engine. The resulting document has a heading with the file name and the text in paragraphs (a new one after a pause of at least two seconds); it is not saved yet, and Save proposes the same name as the file with `.md`. The open document is replaced: if it has unsaved changes, RuscaMark asks first. **Cancel** stops the work.

- With *Same as the document* the language of a file is *Automatic*: audio in another language, transcribed as if it were English, would become invented text.
- With Vosk each sentence gets a capital letter and a final full stop. For long files Whisper is more accurate.
- If the Whisper models include the speech detection model `ggml-silero-v6.2.0.bin`, Whisper transcribes only the parts with a voice, as in RuscaTranscriber.

### Read Aloud

Main menu → **Read Aloud** (**Ctrl+Shift+R**) reads the selection, or the document from the cursor's paragraph to the end. The same command, or **Stop**, interrupts it. The text is read as in the preview: no markers, the text of links and not the address, formulas as symbols; code blocks and footnotes are skipped (code blocks can be read, from Preferences).

- Piper voices are pairs `name.onnx` and `name.onnx.json` in `~/.local/share/ruscapiper/voices/` (the same as RuscaLLisse). With *Automatic choice* RuscaMark uses the voice of the document's language. Speed goes from 0.7 to 1.3.
- Preferences show the voice licence, if its MODEL_CARD file states it. Many Piper voices derive from the English "lessac" voice, distributed for non-commercial research only: for public or commercial use choose a voice with a verified free licence.
- The stress corrections of RuscaLLisse's pronunciation lexicon (`~/.local/share/ruscallisse/pronunce.tsv`) apply here too.

While RuscaMark reads, dictation stays off (the microphone would hear the voice), and vice versa.

## 13. Preferences

Main menu → **Preferences…** (Ctrl+,). Every change applies immediately. Preferences have two pages: **General** and **Voice**.

| Group | Option | Effect |
|---|---|---|
| Appearance | Style | *Follow System* (default), *Light* or *Dark*. |
| Appearance | Text font and Size | Typeface of the editor and the preview: Literata (default, at the top of the list) or one of the installed typefaces. The typeface of the PDF and HTML is the theme's (section 11). |
| Appearance | Line spacing | *Compact*, *Normal* (default) or *Airy*: the space between lines in the editor and the preview, in proportion to the font size (1.25 – 1.5 – 1.75 times). Code blocks and tables stay compact. |
| Writing | Live rendering of formatting | Same as Ctrl+L. |
| Writing | Centred page | When on, text stays in a centred column; when off it uses the full width and a vertical guide line marks the page width. |
| Writing | Page width (characters) | From 40 to 140, measured on the average character of the chosen font. 60–75 is the most comfortable reading measure. |
| Export | PDF and HTML theme | Colours, typefaces and headings of exports and preview: see section 11. |
| Export | Personal themes | *Open Folder* opens `~/.local/share/ruscamark/themes/`, where your own `.css` themes go. |
| Export | Embed images in HTML export | See section 11. |
| Voice → Dictation | Engine, Spoken language, Voice commands, Check sentences before inserting | See section 12. |
| Voice → Vosk | Model, Models folder | *Automatic choice* uses the largest model for the spoken language. |
| Voice → Whisper | Model, Run on, Card to use, Models folder | Processor or graphics card (Vulkan) and which card: see section 12. |
| Voice → Read aloud | Voice, Voice licence, Speed, Read code blocks too, Voices folder | See section 12. |

Side margins adapt to the window: in narrow windows they are at least 4% of the width (16 to 48 pixels); in wide windows the free space is split evenly between both sides.

## 14. Interface languages

English, Simplified Chinese, Spanish, Hindi, Arabic, Brazilian Portuguese, Russian, Japanese, German, French, Italian, Korean, Indonesian, Turkish and Polish. RuscaMark always uses the system language; to change it, use GNOME Settings → System → Region & Language. With Arabic the whole interface switches to right-to-left.

Translations are JSON files in `/usr/share/ruscamark/lang/`. To fix or customise a translation, copy the file to `~/.config/ruscamark/lang/` and edit it: your copy takes precedence. Any missing phrase is shown in English.

## 15. Files and folders

| Path | Contents |
|---|---|
| `~/.config/ruscamark/config.json` | Preferences, window size, spell checking state |
| `~/.config/ruscamark/lang/` | Custom translations (optional) |
| `~/.config/ruscamark/icons/` | Copy of the program icon |
| `~/.local/share/gtksourceview-5/styles/` | Pink and plum editor colour schemes |
| `~/.config/enchant/<language>.dic` | Personal dictionary (including elision fragments) |
| `~/.config/enchant/<language>.dic.ruscamark-added` | List of the fragments added by RuscaMark, so your own words are never touched |
| `~/.local/share/ruscavosk/models/` | Vosk models (one folder per model; also `/usr/share/ruscavosk/models/`) |
| `~/.local/share/ruscawhisper/models/` | Whisper models, `.bin` files (also `/usr/share/ruscawhisper/models/`) |
| `~/.local/share/ruscapiper/voices/` | Piper voices, `.onnx` and `.onnx.json` (also `/usr/share/ruscapiper/voices/`) |
| `~/.cache/ruscamark/trascrizione/` | Working files of a Whisper transcription, deleted at the end and at every start |
| `$XDG_RUNTIME_DIR/ruscamark/` | A sentence dictated with Whisper, in memory, deleted as soon as it is read |

To restore the default settings, close RuscaMark and delete `config.json`.

## 16. Privacy and security

| Principle | How RuscaMark follows it |
|---|---|
| Processed data | Local only, on your computer |
| Sending to remote servers or over the internet | Never: the program opens no network connections |
| Telemetry and usage statistics | None |
| Personal data collection | None |
| Dangerous or harmful commands | None; no administrator rights are needed |
| Sensitive operations | Happen only at your request and are always visible |

**All processed data remains local.** No text, document or file is sent to remote servers or over the internet.

### Network

RuscaMark contains no code that connects to the network. In particular:

- the preview shows only images stored on your computer; those with an `https://…` address are not downloaded and a notice is shown instead;
- spell checking uses only the installed dictionaries (hunspell); your text never leaves your computer;
- in the About window, the "Website", "Support" and "License" rows open your browser or mail program, and only when you choose them;
- dictation, transcription and reading aloud run on your computer, with the engines of the RuscaLinux OS Apps, which open no connections or ports.

### Microphone and audio

- The microphone opens only when you turn dictation on, and the voice bar shows it for as long as it stays open.
- With Vosk the microphone audio passes through memory only and is never written to disk.
- Whisper reads a file: each dictated sentence becomes a short WAV file in a private session folder (`$XDG_RUNTIME_DIR/ruscamark/`, usually in memory), deleted as soon as it is read. Transcribing a file uses `~/.cache/ruscamark/trascrizione/`, which is emptied at the end and at every start.
- Neither the audio nor the dictated text is kept anywhere else: only what you save remains.

Exported HTML is an ordinary file: if the document contains remote images, the **browser** that opens the HTML will download them. For a fully self-contained file, use local images and turn on "Embed images in HTML export".

### Content safety

- HTML written inside the Markdown is never executed, neither in the preview nor in the export: it is shown as text.
- Dangerous links (`javascript:`, `vbscript:`, `data:text/html`) are neutralised in exported HTML.
- Opening a Markdown file runs nothing: it is just text.

### Files written to your computer

RuscaMark writes only the documents you save or export, plus the configuration files listed in section 15, all inside your home folder. It does not modify system files. In the personal dictionary it adds only the Italian and French elision fragments, keeping a separate list of them so the words you added yourself are never altered.

### Package integrity

Always verify the package before installing it:

```bash
sha256sum -c SHA256SUMS
```

### Removing every trace

```bash
sudo apt remove ruscamark
rm -rf ~/.config/ruscamark ~/.cache/ruscamark
rm -f ~/.local/share/gtksourceview-5/styles/ruscamark-*.xml
```

The personal dictionary in `~/.config/enchant/` is shared with other programs: if you wish, delete any words you no longer need by hand.

## 17. Troubleshooting

| Problem | Solution |
|---|---|
| The program does not start | Check Python 3, GTK 4 (`gir1.2-gtk-4.0`) and libadwaita (`gir1.2-adw-1`); verify the package with `sha256sum -c SHA256SUMS` and reinstall it. |
| "Spell checking unavailable" | Install `gir1.2-spelling-1` and the language dictionary (e.g. `hunspell-en-gb`). |
| Undo/redo or highlighted search do not work | Install `gir1.2-gtksource-5`. |
| PDF export reports "python3-gi-cairo" | Install the `python3-gi-cairo` package (normally installed together with RuscaMark). |
| A generic icon appears in the panel | Launch RuscaMark from the applications menu after installing the package: the icon comes from the `org.ruscalinux.RuscaMark.desktop` file. If you had pinned RuscaMark to the dash with a version before 1.99.2, unpin it and pin it again: the identifier has changed. When `ruscamark.py` is run directly from the source folder, GNOME cannot find the launcher and shows a generic icon. |
| An image does not appear in the preview | Check the path: a relative path starts from the saved document's folder. Remote images are deliberately not shown. |
| Table columns are misaligned | Put the cursor in the table and press Ctrl+Shift+T. |
| A line with `---` under it becomes a heading | Leave a blank line before `---` to get a horizontal rule. |
| Dictation does not start | Read the message: it says whether the engine (`ruscavosk-engine` or `ruscawhisper-engine`), the model or `pipewire-bin` is missing. Preferences → Voice shows what is there. |
| The voice bar stays on "Listening" but writes nothing | Check the microphone in Settings → Sound. With Vosk the sentence enters after a one-second pause; with Whisper after about 0.7 seconds. With the draft on, text goes into the draft, not the document: press **Insert**. |
| After a while dictation writes later and later | Recognition is slower than your speech: the bar shows the delay. Use a smaller model (for example `vosk-model-small-en-us-0.15`) or pause a little more. To see what happens, start RuscaMark from a terminal with `RUSCAMARK_VOICE_DEBUG=1 ruscamark`: for each sentence it prints how much audio, how much delay and how long it took (with `=2` also the recognised text). This stays on the terminal and is never saved. |
| Whisper is slow | Use a smaller model, or *Graphics card (Vulkan)* in Preferences → Voice. |
| Whisper stops with an error on the graphics card | Choose another card in *Card to use*, or *Processor (CPU)*. |
| Vosk writes "." instead of the word "period" | It is a voice command: turn off *Voice commands* or use Whisper. |
| I don't know what to say for punctuation or headings | Main menu → *Voice Commands…*, or the **?** button in the voice bar. |
| Reading aloud does not start | Install `ruscapiper-engine` and copy a voice (`.onnx` with its `.onnx.json`) into the voices folder. |

Support: info@ruscalinux.org

## 18. License and development note

RuscaMark is free software released under the GPL-3.0 license: <https://www.gnu.org/licenses/gpl-3.0.html>.

The common Markdown engine includes an external component: the highlight rule `==text==`, a port of the [markdown-it-mark](https://github.com/markdown-it/markdown-it-mark) plugin (MIT license, © Vitaly Puzrin and Alex Kocharin; Python structure from markdown-it-py, © ExecutableBookProject), in its own file `markdown_it_mark.py`. It is also listed in the About window, under “External Components”.

The text typeface is **Literata 3.103** (© The Literata Project Authors, <https://github.com/googlefonts/literata>), under the SIL Open Font License 1.1, which allows distribution together with GPL software: the font files are unmodified and the licence text is in `/usr/share/ruscamark/fonts/Literata-OFL.txt`. The licence allows embedding it in exported PDFs.

Dictation, transcription and reading aloud use three engines that are separate packages, also listed under “External Components”: Vosk (Apache 2.0 licence, © Alpha Cephei Inc.), whisper.cpp (MIT licence, © The ggml authors) and Piper (GPL-3.0 licence, © Michael Hansen and the Piper authors).

The note on the use of AI tools is in the program's About window and in the `NOTA-IA.md` file of the repository.
