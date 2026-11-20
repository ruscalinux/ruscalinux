# Changelog

What changed that you can see while using RuscaWriter. Internal changes stay
in the `git log` of the RuscaLinux repository.

One line per change.

---

## [Unreleased]

- **Added** — *Format* button in the header bar (also in the main menu and,
  bold and italic first, in the right-click menu): bold, italic, normal text,
  section, subsection, quote, bulleted and numbered list, footnote, scene
  break, image and chapter title. Each command applies or removes its
  formatting, works on the word under the cursor when nothing is selected,
  formats a multi-line selection line by line, and is undone with one Ctrl+Z.
  Strikethrough and highlight are not offered: the book formats do not print
  them
- **Added** — shortcuts Ctrl+B (bold), Ctrl+I (italic), Ctrl+2 (section),
  Ctrl+3 (subsection), Ctrl+Alt+F (footnote); Ctrl+0 brings the text back to
  the default size, as in the other RuscaLinux OS Apps
- **Changed** — *Import as chapters* moves from Ctrl+I to Ctrl+Shift+O,
  because Ctrl+I is italic in every word processor
- **Changed** — chapter titles follow one rule everywhere: the title is the
  chapter's name in the list; a `# Title` at the top of the text is that title
  and is printed once; every other heading is a section (`##`) or subsection
  (`###`), and a `#` further down counts as `##`. The preview and all exports
  (PDF, typeset PDF, EPUB, ODT, DOCX, HTML, Markdown, TXT) now agree
- **Changed** — renaming a chapter whose title is written in the text
  rewrites it there, so the list and the page never disagree
- **Fixed** — EPUB: a chapter without `# Title` in the text had no title on
  its page
- **Fixed** — DOCX: chapter, section and subsection titles are Word's real
  heading styles (navigation pane, automatic table of contents); quotes have a
  real style; each chapter starts on a new page, as in ODT and PDF
- **Fixed** — HTML: chapters were `h1` or `h2` depending on whether the text
  had a title; now always `h2` in a single file and `h1` on their own page
- **Fixed** — typeset PDF: `##` was a subsection; now `##` is `\section` and
  `###` is `\subsection`
- **Fixed** — TXT: chapters without a written title had none
- **Fixed** — Markdown import cut chapters at every `#` and `##`, even inside
  code blocks; now it cuts at chapter headings only, and a file with one `#`
  and several `##` (as written by the Markdown export) comes back with the
  same chapters, sections and cover lines
- **Fixed** — a line such as `#tag` is no longer taken for a chapter title

- **Added** — Export → *Typeset PDF (LuaLaTeX)*: the book typeset by LuaLaTeX
  with whole-paragraph line breaking, microtypography, kerning and ligatures,
  every script (Arabic right to left, Devanagari, Chinese, Japanese, Korean),
  full-page cover, title page, colophon, table of contents, chapters on
  right-hand pages, running heads and no widows or orphans. Needs
  `texlive-luatex` and `texlive-latex-recommended`
- **Fixed** — PDF: on a cover without an image a long title ran past the
  frame and the rules crossed it; the title now shrinks until every word fits
  inside the frame, and the rules follow the text
- **Changed** — PDF: each line break starts an indented paragraph, so
  paragraphs can be told apart without blank lines; space before headings;
  no running head on a chapter's opening page, which always shows the
  chapter title; web and e-mail addresses are no longer hyphenated

## [1.99.2] — RuscaLinux OS Tools

RuscaWriter is now one of the RuscaLinux OS Tools: it lives in the RuscaLinux
repository (`apps/ruscawriter`) and follows its specifications.

### Look

- **Changed** — a GNOME (libadwaita) window: header bar with chapters, new
  chapter, notes, preview, Save and the main menu; the classic menu bar is gone
- **Changed** — the main menu groups everything: file and export at the top,
  then Chapter, sections and page setup, search and dictionaries, View and
  Appearance, and at the bottom the Markdown guide, keyboard shortcuts, About
- **Changed** — text size and spell-check language moved to the bottom bar
- **Changed** — bars, menus and dialogs follow the common RuscaLinux theme; the
  page themes now colour only the writing page, the preview and the notes
- **Changed** — two page themes instead of three: **Amethyst** and **Classic**.
  Classic is now the look of a professional writing studio: a crisp white
  page, near-black ink, cool greys and blue headings, code and selection; in
  dark mode a charcoal page with a muted blue. Whoever used **Simple** is
  moved to Classic
- **Changed** — Amethyst uses the official RuscaLinux palette; Markdown marks,
  once almost invisible (about 1.2:1), are now at least 4.5:1, headings and
  code at least 7:1, in all six theme combinations
- **Changed** — a new icon in the family of the RuscaLinux OS Tools: a
  fountain-pen nib on the writing line, with a symbolic version
- **Changed** — dialogs are GNOME dialogs; short confirmations appear as
  notifications at the bottom
- **Added** — Keyboard Shortcuts window (Ctrl+?)

### Behaviour

- **Changed** — the interface language is the system's; the language menu is gone
- **Changed** — About shows the version only (no date), the website, support,
  licence, the bundled fonts as external components and the development note
- **Changed** — website, source and issue tracker are RuscaLinux's
- **Added** — `.rwr` projects open with a double click, or as `ruscawriter file.rwr`
- **Changed** — the package is `ruscawriter`, architecture `all`; it replaces
  `ruscawriter-ruscalinux`
- **Added** — Markdown tables in the preview and in every export: book-style
  rules in the PDF, real tables in HTML, EPUB and AZW3, native tables in ODT
  and DOCX, aligned columns in plain text
- **Added** — the preview shows the pictures, not only their captions
- **Changed** — the preview button is a toggle: the eye stays pressed while
  the preview is shown (tooltip "Back to editing"), and the subtitle says
  "Preview" too
- **Added** — importing a Markdown file copies the pictures it cites from
  next to it into the project; a picture missing from the project shows a
  box with "Choose the Image…", which adds the file and updates the text
- **Added** — formulas (`$E = mc^2$`, `$$…$$`) appear as readable symbols
  (E = mc², ≈, √, α) in the preview and in every export except Markdown,
  which keeps the LaTeX source
- **Fixed** — the PDF uses Unicode fonts: Greek, Cyrillic and every other
  character in the chosen font are printed, instead of becoming "?"
- **Added** — characters the book font lacks (emoji, symbols, Greek in
  Courier Prime) are taken from a system font that has them, in black and
  white as in printed books; flags and invisible emoji marks are left out
- **Added** — `---` is a short centred rule in the PDF and the preview, a
  line in HTML, EPUB and AZW3, and "* * *" in ODT and DOCX

---

## [1.99.2] — before the RuscaLinux OS Tools

### Look

- **Changed** — a new icon in the RuscaLinux colours: the fountain pen is plum
  and gold instead of burgundy, on a light pink-to-mauve ground that makes it
  stand out at every size, from the dock down to 16 px. The welcome window and
  About now read the same file as the desktop, so the two can no longer differ
- **Fixed** — the links in About were GTK blue; they now take the theme's colour
- **Changed** — three themes instead of six: **Amethyst** (the RuscaLinux
  colours, light pink to dark plum), **Classic** (warm
  grey, ivory page, graphite ink) and **Simple** (neutral greys only, the same
  for every kind of colour vision). Each has a light and a dark version
- **Changed** — every piece of interface text is now at 7:1 contrast or more
  (WCAG AAA), checked on both ends of every gradient; the writing text stays
  around 11:1, never the glare of pure black on white
- **Changed** — the selection is a soft tint with dark text instead of a block
  of solid colour
- **Fixed** — the main button of a dialog, check boxes and focus rings took
  GTK's blue in every theme; they now take the theme's own colour
- **Added** — View → Appearance: *Automatic* follows GNOME's light or dark
  mode and changes with it while the program is open; *Light* and *Dark* fix
  the choice. `Ctrl+Shift+D` still switches between the two
- **Fixed** — in a dark theme, menus and file choosers opened white; they now
  follow the theme
- **Removed** — themes read from `~/.config/ruscawriter/themes/`. A theme saved
  by an older version (Ruby, Sapphire, Jade, Amber, Morganite) opens as the
  nearest of the three

### Layout

- **Added** — File → Page setup (`Ctrl+Shift+P`): format, top, bottom,
  inside and outside margins, gutter, facing pages on or off, in millimetres,
  centimetres or inches, with a live preview of the spread
- **Added** — margin presets: the format's own margins, the classical canon
  (2:3:4:6), a wide outer margin for notes, and the 1-inch manuscript
- **Added** — the dialog shows the size of the text block and the characters
  per line, with a hint outside the comfortable 45–75; margins under 5 mm or
  a block too narrow or too short cannot be applied
- **Added** — margins are saved in the document, one set per format, and are
  used by the PDF, ODT and DOCX exports alike. DOCX was always A4 before
- **Changed** — the PDF export dialog is now the page setup dialog, with the
  justification and hyphenation options below the margins
- **Fixed** — running heads and page numbers were centred on the page instead
  of the text block
- **Fixed** — in the table of contents the page numbers stuck out past the
  dot leaders by the width of the binding margin
- **Fixed** — pictures in ODT and DOCX could be wider than the text block of a
  small format; they now fit inside it

---

## [0.99.1] — 2026-08-27

### Writing

- **Added** — dictionaries. Add your own MDict (`.mdx`) files under
  View → Dictionaries, then look a word up with `Ctrl+D`. A small sheet opens
  beside the word, the cursor never leaves the text, and the next key you type
  puts it away — as does `Esc`, or scrolling. Several dictionaries can be
  installed and put in order: the first one that has the word answers
- **Added** — the lookup understands elisions, so `dell'anima` finds *anima*,
  the way the spell checker already did
- **Added** — dictionaries are read by RuscaWriter itself, with the standard
  library alone: nothing new to install, and nothing goes online. The first
  opening builds an index, kept under `~/.cache/ruscawriter/` and rebuilt by
  itself if the file changes
- **Added** — gender and number are undone by rule, so a plural or a feminine
  reaches the headword a dictionary actually files: *case* → *casa*, *amiche* →
  *amica*, *fuochi* → *fuoco*, *uomini* → *uomo*, *houses* → *house*,
  *children* → *child*, *Bücher* → *Buch*, *книги* → *книга*. Rules for the
  seven interface languages, irregulars included; the language you spell-check
  in is tried first
- **Added** — when no rule fits either, the closest headword is shown instead,
  marked as such, with the other close ones offered beside it. This is what
  catches verb endings, like *scrivendo* reaching *scrivere*
- **Added** — selecting more than one word now works: the phrase is tried
  first, then its longest word
- **Added** — a folder for your dictionaries, shown and changed under
  View → Dictionaries. Adding a dictionary copies the file there, so the
  program does not depend on where you happened to download it; the default is
  `~/.local/share/ruscawriter/dictionaries`, and the copying can be switched
  off if you would rather keep the files where they are
- **Added** — taking a dictionary out of the list asks whether to delete the
  file too, when the file is one this program copied into that folder
- **Note** — two kinds of `.mdx` are refused with a message instead of being
  half-read: dictionaries encrypted with a purchase key, and the old ones
  compressed with LZO

---

## [0.99] — 2026-08-13

Everything that changed since 0.3, the last published release.

### Writing and typesetting

- **Added** — View → Fonts: the screen font and the export font are chosen
  separately, from the two built-in faces or from any TrueType family installed
  on the machine. The export font is embedded in the PDF
- **Added** — PDF bookmarks: the exported PDF now carries a navigation tree of
  the chapters, which readers show in the sidebar and open by default
- **Added** — justified text in the PDF export, with optional hyphenation
- **Fixed** — a maximised window now reopens maximised. Its size was being
  saved while maximised and restored as an ordinary window the size of the
  screen, spilling under the taskbar every time
- **Fixed** — on the first run the text sat in a narrow column between two
  huge margins. The reading margins were measured before the side panels took
  their space, and nothing recalculated them afterwards
- **Fixed** — the writing column could be squeezed into a sliver, with the
  chapter list taking most of the window. The side columns were each capped at
  40% of the width, but independently, so together they could take 80%; and
  divider positions were being saved before the window had a real size, so a
  bad layout copied itself from one session to the next. The text now keeps a
  floor whatever the side columns ask for
- **Fixed** — View → Dark theme and Show line breaks now carry a tick when
  they are on. They are switches, and the menu used to read the same either way
- **Fixed** — on a cover with only a title and an author, the author was
  printed twice: the exports worked out each line's role from its position,
  and with two lines the ranges overlapped. Roles now come from the editorial
  fields themselves, in the PDF, HTML, EPUB and the thumbnail alike
- **Added** — cover generator: builds a typographic cover, with a live preview
- **Fixed** — on the generated cover, a long title no longer runs off the
  edges, and words are never split across lines: the type size is measured
  against the real text width, letter spacing included, and shrinks until every
  word fits whole
- **Added** — Markdown guide under Help (Shift+F1)
- **Added** — View → Show line breaks (`Ctrl+Shift+B`) tints the paragraphs that
  are broken at a fixed column, and Chapter → Rejoin paragraphs repairs them.
  Both follow the same rule, so what you see highlighted is what gets joined
- **Changed** — importing a hard-wrapped `.txt` no longer rejoins the
  paragraphs on its own: it is your text, so the choice is yours. Turn on
  Chapter → Rejoin imported text automatically and RuscaWriter will do it from
  then on
- **Fixed** — importing a Project Gutenberg `.txt` no longer drags the header
  and the licence into the manuscript: about a tenth of the words in a typical
  file. The cut is made between Gutenberg's own two marker lines, so a file
  that is not from Gutenberg comes through untouched
- **Added** — Chapter → Rejoin paragraphs repairs text that is hard-wrapped at
  a fixed column, the usual shape of literary plain text, so it justifies in the
  PDF and reflows in the EPUB. Verse, lists, quotes and explicit Markdown line
  breaks are left alone
- **Fixed** — a Markdown link lost its address on export: only the label came
  through, so a cited source became unreachable. The address is now printed in
  full beside the label, and never as a clickable link — a book gets printed,
  and on paper nobody can click
- **Fixed** — Markdown is now read the same way everywhere. A heading needs a
  space after the `#`, as the Markdown guide has always shown: `#Title` is body
  text in every format, where before it was a heading in the PDF only
- **Fixed** — `_italic_` and `__bold__` are highlighted while you type, not
  only formatted on export
- **Fixed** — a lone `*`, as in `3 * 4`, no longer turns the rest of the line
  italic in the PDF
- **Fixed** — nested formatting (`**bold with *italic* inside**`) now comes out
  right in HTML and EPUB too

### Look

- **Added** — custom themes: drop a small text file with a name and seven
  colours into `~/.config/ruscawriter/themes/` and it joins the theme menu,
  light and dark version included. The folder ships a commented example
- **Added** — a second interface theme beside the plum of RuscaLinux:
  **Quiet**, designed for comfort over long sessions — off-white paper,
  graphite ink, a sage accent kept to the selection and the rules, in a light
  and a dark version
- **Changed** — five themes, named after five gems: **Ametista**, **Rubino**,
  **Zaffiro**, **Giada**, **Ambra**. Each has its own paper, ink and night
  ground, and each keeps body text between 12:1 and 14:1 rather than at the
  21:1 of pure black on pure white. The names are translated, and each entry in
  the theme menu carries a dot in its own colour
- **Changed** — the RuscaLinux plum theme was reworked for the eyes. Its bars
  keep the full plum, but the page no longer is black on white at 21:1: paper
  with a whisper of plum, graphite ink, 13.8:1
- **Added** — themes can now set the interface bars separately from the accent,
  and choose their own paper, panels and ink. Custom themes in the folder can
  do the same
- **Changed** — the theme is now picked in two independent steps: the colour
  family under View → Theme, light or dark with `Ctrl+Shift+D`
- **Fixed** — the hint on the empty page named a menu command that did not
  exist ("New chapter" instead of "Add chapter")

### Under the hood

- **Changed** — the version and the date are now written in one place only

---

## [0.3] — 2026-07-04

- **Added** — images inside chapters (Ctrl+Shift+I). They travel inside the
  `.rwr` file and come out as real figures with captions in every export
- **Added** — WebP, alongside PNG and JPEG, for chapter images and covers
- **Removed** — the "update date" button, made redundant by editorial sections

---

## [0.2] — 2026-06-14

- **Added** — five page sizes for the PDF export: A5, 6×9″, 17×24 cm, A4, 5×8″
- **Added** — binding margins, so text does not disappear into the spine
- **Added** — cover, frontispiece and colophon, set from editorial sections
- **Changed** — the default PDF page size is now A5 instead of A4
- **Changed** — application icons redrawn at every size, up to 512 px

---

## [0.1] — 2026-06-11

- **Added** — first release. Three columns (chapters, text, notes), writing in
  Markdown, and export to TXT, Markdown, PDF, EPUB, ODT, DOCX and HTML
