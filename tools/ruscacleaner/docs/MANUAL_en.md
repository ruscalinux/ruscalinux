# RuscaCleaner — User Manual

**Version** 1.99.3 · **Author** Nunzio Curcuruto · **Distribution** RuscaLinux ([ruscalinux.org](https://www.ruscalinux.org/)) · **License** GNU GPL v3 or later

---

## 1. What it is

RuscaCleaner is a GNOME desktop program that **removes activity traces from your home folder**: thumbnails, recent files, histories, clipboard, search index and trash. It does a limited set of things, lists all of them in the window, and also states the ones it does **not** do.

---

## 2. Installation

Requirements: RuscaLinux or Debian Stable, GNOME, Python 3.10+, GTK 4.18+, libadwaita 1.7+.

```bash
sha256sum -c SHA256SUMS                                   # check integrity first
sudo apt install ./ruscacleaner-ruscalinux_1.99.3_all.deb # installs dependencies too
```

To build the package from source: `./make-deb.sh`. The package and `SHA256SUMS` are created in `build-deb/`.

---

## 3. What it cleans

| Entry | What is removed | On by default |
|---|---|---|
| **Thumbnails** | Image and video previews: `~/.cache/thumbnails`, `~/.thumbnails` and the caches of Flatpak apps. They regenerate on their own. | ✅ |
| **Recent files** | The list of recently opened documents (`recently-used.xbel`), Flatpak apps included. | ✅ |
| **Clipboard history** | The history saved by GPaste and by the Clipboard Indicator extension. | ❌ |
| **Search index** | `~/.cache/tracker3/files`: the text and details that GNOME search extracted from your files. It is rebuilt automatically. | ❌ |
| **File manager metadata** | `~/.local/share/gvfs-metadata`: notes about files you opened. | ❌ |
| **Session logs** | `~/.xsession-errors` and the Xorg logs, which may contain file names. | ❌ |
| **Trash** | Files, metadata and interrupted deletions in the trash. | ❌ |
| **Trash on other drives** | The `.Trash-<uid>` folders on USB sticks and secondary drives that are mounted. | ❌ |

In the expandable **Shell, tool and editor histories** row (all off by default):

| Entry | Files |
|---|---|
| **Bash** | `~/.bash_history` |
| **Zsh** | `~/.zsh_history`, `~/.zhistory`, `~/.histfile`, `~/.local/share/zsh/history` |
| **Fish** | `~/.local/share/fish/fish_history` |
| **Command-line tools** | Python, less, SQLite, PostgreSQL, MySQL, Node.js, Ruby (irb), Redis, R, Octave, gnuplot, Julia |
| **Editors** | Vim (`~/.viminfo`), Neovim (ShaDa), nano, Emacs (`recentf`, `history`): opened files and searches |

Shell histories are **emptied**, not deleted, so the file keeps its permissions.

**Why these defaults?** Only what regenerates with no loss starts switched on. Everything that cannot be rebuilt starts off and must be chosen by you, knowingly.

---

## 4. Using the window

1. **Open the program.** A scan starts automatically. The list shows only the entries that really have something to remove, each with its size; if there is nothing, the window says "Nothing to clean".
2. **Choose** what to clean with the switches. Shell, tool and editor histories are in a separate group. The total, in the bar at the bottom, updates with every change.
3. **Press "Clean now"** in the bottom bar. The confirmation window lists **the real paths of the files** and the relevant warnings, and has **"Cancel"** as the default button.
4. **Read the result** in the notification at the bottom. The **"Details"** button opens the log: every deleted item, every skipped item with its reason, and the total freed. After cleaning, the list refreshes on its own.

The **⟳** button at the top left recalculates sizes. The menu at the top right contains:

- **Simulate only:** try without deleting anything. While it is on, a strip at the top says so (with a "Turn Off" button) and the bottom button becomes "Simulate".
- **What this does not do:** the declared limits (§6.3).
- **Keyboard Shortcuts** and **About** (version, links to website, support and license, development note).

The window refuses to close while a deletion is in progress.

The window follows GNOME's light or dark style, remembers its size and can be used from the keyboard:

| Keys | Action |
|---|---|
| F5 or Ctrl+R | Recalculate sizes |
| Ctrl+? | Keyboard shortcuts |
| F10 | Main menu |
| Ctrl+W | Close the window |
| Ctrl+Q | Quit |

---

## 5. Command line

```
ruscacleaner              opens the window
ruscacleaner --list       lists entries and sizes, touches nothing
ruscacleaner --dry-run    simulates the default entries, deletes nothing
ruscacleaner --version    shows the version
```

From the command line the program **never deletes**: real deletion happens only in the window, after confirmation. `--allow-root` disables a protection (§7) and is not meant for normal use.

---

## 6. Privacy

### 6.1 Everything stays on your computer
RuscaCleaner has no network functionality: no servers, no statistics, no account, no downloads. The GPL source code lets anyone verify this.

### 6.2 Deleting is not erasing forever
This is an ordinary delete, **not a secure wipe**. A forensic tool, a btrfs snapshot or a backup may still hold the old data. If a file must no longer exist in any form, you need disk encryption and careful management of snapshots and backups.

### 6.3 What is NOT cleaned
- **Browser data** (history, cookies, caches): browsers have their own, more complete tools.
- **The system journal**: it requires administrator rights.
- **GNOME Shell app usage statistics**: the Shell keeps them in memory and writes them back.
- **The settings of individual applications** (for example recent-file lists inside their configuration files).
- **`~/.ssh/known_hosts` and `~/.wget-hsts`**, kept on purpose: they protect your connections from impersonation and downgrade attacks.

### 6.4 Tips for an effective clean
Many programs rewrite their traces when they quit, so cleaning them while open achieves little. The confirmation window reminds you of this:
- close **applications** before cleaning *recent files*;
- close **terminals** (or run `history -c` in each) before cleaning shell histories, and close **editors and tools** before cleaning theirs;
- clear the **clipboard manager** from its own menu too, or restart it;
- after cleaning the **search index**, log out and back in;
- after cleaning **file manager metadata**, restart the file manager;
- *trash on other drives* is visible only for drives **mounted at that moment**.

---

## 7. Security: built-in protections

1. **Refuses to run as root** (sudo, su, pkexec, root shells).
2. **Checks that the home folder belongs to you**, which also covers cases that `SUDO_USER` alone does not see.
3. **Stays within its boundaries**: only your home and validated trash folders on mounted drives (under `/media/<user>`, `/run/media/<user>` or `/media`, on a real mount point, named `.Trash-<uid>` or `.Trash/<uid>`, owned by you, not a link).
4. **Never follows symbolic links**: `lstat` to recognise them, `O_NOFOLLOW` when emptying a file. A link is skipped and reported.
5. **Checks the owner of every item**: other users' files are skipped.
6. **Always asks for confirmation** with the real paths; the default button is "Cancel".
7. **Simulation**: `--dry-run` and "Simulate only" show everything and delete nothing.
8. **No half-done jobs**: the window does not close during a deletion, a failing item affects only itself, and the reported space is only what really disappeared.
9. **Safe translations**: language files are accepted only as text→text pairs, file names are validated, and placeholders are replaced without `str.format()`.
10. **Robust calculations**: sizes are computed iteratively, so very deep folders do not crash the program.

---

## 8. Languages

The interface is translated into the languages of the RuscaLinux OS Tools: they are the files in the `lang/` folder. Translations other than Italian and English are made with the assistance of AI tools: corrections from native speakers are welcome (info@ruscalinux.org).

The language follows the system settings (`LANGUAGE`, then `LC_ALL`, `LC_MESSAGES`, `LANG`). A regional variant falls back to its language (`de_AT` → `de`). Hong Kong and Macao use Traditional Chinese (`zh_TW`), other Chinese locales Simplified Chinese (`zh_CN`); Slovak uses Czech. Anything missing falls back to English. To try a language: `LANGUAGE=it ruscacleaner`.

---

## 9. Frequently asked questions

**How much space will I free?** Thumbnails, the search index and the trash can take up many GB; histories only a few kB. For many people the real value is removing traces, not freeing space.

**Can I undo a clean?** No. The program keeps no copies.

**Does it need an internet connection?** No, never.

**How do I check what it would do, without risk?** `ruscacleaner --dry-run`, or the "Simulate only" switch.

---

## 10. Short glossary

- **Home**: your personal folder (`/home/your-name`, written `~`).
- **Symbolic link**: a file that only points to another one; following it blindly is the classic way to delete the wrong thing.
- **Mount point**: where a disk or USB stick is attached to the folder tree.
- **UID**: the user's identification number, used to tell who owns a file.
- **Snapshot**: a picture of the filesystem that keeps earlier versions of files.

---

## 11. License, contacts and AI note

- **License:** GNU GPL v3 or later, without any warranty.
- **Support:** info@ruscalinux.org
- **AI note:** in the program's About window and in the `NOTA-IA.md` file of the repository.
