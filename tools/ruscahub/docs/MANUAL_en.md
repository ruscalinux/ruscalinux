# RuscaHub — User Manual

**Version 1.99.3 · RuscaTools Suite · RuscaLinux**
Author: Nunzio Curcuruto — © 2026 — GPL-3.0 License — <https://www.ruscalinux.org/>

## 1. Overview
RuscaHub is the official AppImage manager of RuscaLinux. It allows you to:
- import `.AppImage` files via button or drag & drop;
- archive them in a hidden folder of the Home (`~/.ruscahub/apps/`);
- **install** them (creates a GNOME menu entry with the program's original icon);
- **uninstall** them (removes only the menu entry);
- **run** them directly from the list;
- **delete** them (entry and icon are removed, the AppImage file goes to the trash).

## 2. Requirements
- RuscaLinux or Debian Stable (or derivative) with a GNOME environment;
- Python ≥ 3.10 with `python3-gi`, `gir1.2-gtk-4.0` (GTK ≥ 4.18) and `gir1.2-adw-1` (libadwaita ≥ 1.7);
- `squashfs-tools` recommended: it lets RuscaHub read the AppImage name and icon
  **without running it**, and is the most reliable way to get the right icon;
- FUSE 2 recommended (`libfuse2t64` on Debian 13, `libfuse2` on Debian 12) to
  run AppImages; without it RuscaHub automatically falls back to
  `--appimage-extract-and-run`;
- Chinese, Japanese, Korean, Hindi and Arabic need the matching fonts
  (`fonts-noto-core`, `fonts-noto-cjk`), usually already present in GNOME.

The `.deb` package installs the dependencies and recommended packages automatically.

## 3. Installation
### 3.1 .deb package
Check integrity, then install:

    cd build-deb && sha256sum -c SHA256SUMS
    sudo apt install ./ruscahub-ruscalinux_1.99.3_all.deb

The installed package name is still `ruscahub`, so the new version upgrades the
previous one without conflicts.

### 3.2 From source

    python3 ruscahub.py

The `lang/` folder must sit next to `ruscahub.py`.

## 4. Launch
From the GNOME menu: **RuscaHub** (Utility category), or from a terminal: `ruscahub`.

## 5. Main window
- **Header bar:** on the left the **+** button ("Add AppImage"); on the right the
  activity indicator and the main menu with "Keyboard Shortcuts" and
  "About RuscaHub".
- **"Your AppImages" list:** for each AppImage it shows icon, name, state
  ("Installed" / "Archived") and file name (hover the row to see the full path),
  with the Run, menu switch and Delete controls.
- **Empty page:** when there are no AppImages, it invites you to drag one in or
  press "Add AppImage".
- **Notifications:** a short notification at the bottom confirms imports,
  installations and deletions, or reports an error.

The window follows GNOME's light or dark style, remembers its size and can be
used from the keyboard:

| Keys | Action |
|---|---|
| Ctrl+O | Add AppImage |
| Ctrl+? | Keyboard shortcuts |
| F10 | Main menu |
| Ctrl+W | Close the window |
| Ctrl+Q | Quit |

## 6. Importing an AppImage
1. Drag the `.AppImage` file onto the window, or press "Add AppImage" and pick it
   (multiple selection is allowed).
2. RuscaHub copies the file to `~/.ruscahub/apps/`, sets execute permissions,
   reads the original name, description and icon, and adds it to the list.

### 6.1 How the icon is found
Many AppImages do not keep the icon in their root folder, only a symbolic link
to an inner folder. RuscaHub:
1. reads the inner `.desktop` file (even when it is a symbolic link) and takes
   `Name`, `Comment`, `Icon` and `StartupWMClass` from it;
2. follows the `.DirIcon` link to the real file;
3. looks for the icon named by `Icon=` in the root, in `usr/share/icons/` and in
   `usr/share/pixmaps/`;
4. picks the best icon: SVG (compressed `.svgz` too) when available, otherwise
   the largest PNG;
5. saves it in `~/.ruscahub/icons/`.

Reading is done with `unsquashfs`, without running the AppImage; when it is not
available, RuscaHub uses the AppImage's own `--appimage-extract` command.
The AppImage content is never modified.

The `StartupWMClass` key links the running program window to its menu entry, so
the GNOME dash shows the correct icon too.

## 7. Available operations
| Control | Effect |
|---|---|
| ▶ Run | Launches the AppImage immediately |
| Switch on | Creates the GNOME menu entry (`~/.local/share/applications/`) |
| Switch off | Removes the menu entry, keeps the file |
| 🗑 Delete | After confirmation, removes entry, icon and `.desktop` file and moves the AppImage file to the trash |

An AppImage deleted by mistake can be recovered from the GNOME Trash and
imported again.

## 8. Automatic icon repair
AppImages imported with earlier RuscaHub versions and left without an icon are
scanned again **once only**, the first time the new version starts; the activity
spinner turns while this happens. If the AppImage was installed, its menu entry
is rewritten with the icon found.

## 9. Files and paths
| Path | Content |
|---|---|
| `~/.ruscahub/apps/` | Archived AppImages |
| `~/.ruscahub/icons/` | Extracted icons |
| `~/.ruscahub/ruscahub.json` | Persistent list |
| `~/.local/share/applications/ruscahub-*.desktop` | GNOME menu entries |
| `/usr/share/ruscahub/lang/*.json` | Interface translations |

## 10. Supported languages
RuscaHub is translated into the languages of the RuscaLinux OS Tools: they are the
files in the `lang/` folder. Translations other than Italian and English are made
with the assistance of AI tools: corrections from native speakers are welcome
(info@ruscalinux.org).

- The language follows the system locale; manual override: `RUSCAHUB_LANG=de ruscahub`.
- Hong Kong and Macao use Traditional Chinese (`zh_TW`), other Chinese locales
  Simplified Chinese (`zh_CN`); Slovak uses Czech.
- With Arabic the interface is laid out right to left.
- A missing translation falls back to `en.json`; if the text is missing there too,
  the program does not crash and shows the key name.
- Translations are UTF-8 JSON files in the `lang/` folder: to fix one, just edit
  that language's file.

## 11. About window
Opens from the main menu: icon, name, version, description and links to website,
support and license. The “Development Note” row opens the note on a second page,
with the back button at the top.

## 12. Building the .deb package
From the project root:

    ./make-deb.sh

Output in the `build-deb/` folder:
`ruscahub-ruscalinux_1.99.3_all.deb` + `SHA256SUMS`.
The architecture is `all` because RuscaHub is written entirely in Python.

## 13. Troubleshooting
- **The menu shows a generic icon (blue diamond with a gear):**
  install `squashfs-tools` (`sudo apt install squashfs-tools`), then press
  "Uninstall" and "Install" again. AppImages without an icon are also rescanned
  automatically the first time version 1.99.2 starts.
  To check the entry: `grep Icon ~/.local/share/applications/ruscahub-*.desktop`.
- **Correct icon in the menu but generic in the dash while the program is open:**
  the AppImage does not declare `StartupWMClass`; this is a limit of the AppImage,
  not of RuscaHub.
- **AppImage does not start:** install `libfuse2t64` (Debian 13) or `libfuse2`
  (Debian 12); otherwise RuscaHub uses the automatic fallback.
- **Menu entry missing:** log out and back in, or run
  `update-desktop-database ~/.local/share/applications`.
- **Entry disappeared from the list:** the file was moved manually; at startup
  RuscaHub automatically prunes orphaned entries.
- **Square boxes instead of Chinese, Japanese, Korean, Hindi or Arabic text:**
  install `fonts-noto-core` and `fonts-noto-cjk`.

## 14. Privacy and security
All data processed by RuscaHub remains local. No data or files are sent to
remote servers or over the internet; there is no telemetry. RuscaHub contains no
dangerous or harmful commands for the operating system: the only destructive
operation (Remove) acts only on files created by RuscaHub itself and is started
explicitly by the user.

## 15. Development note
The note on the use of AI tools is in the About window (§11) and in the
`NOTA-IA.md` file of the repository.

## 16. License and contacts
GPL-3.0 — Nunzio Curcuruto (ruscalinux-dev) — <info@ruscalinux.org>
