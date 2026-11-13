#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# RuscaCleaner — pulizia delle tracce di attività per il desktop GNOME
# Copyright (C) 2026  Nunzio Curcuruto
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.
"""
RuscaCleaner — rimuove le tracce di attività dalla home dell'utente.

Requisiti: Python 3.10+, PyGObject, GTK 4.18+, libadwaita 1.7+
(Debian: python3-gi gir1.2-gtk-4.0 gir1.2-adw-1).

    ruscacleaner             apre la finestra
    ruscacleaner --list      elenca obiettivi e dimensioni
    ruscacleaner --dry-run   simula, senza cancellare nulla

La logica che tocca il disco sta nella prima metà del file e non importa GTK:
si può verificare senza desktop. L'interfaccia è dentro run_gui().
"""
import argparse
import json
import os
import re
import shutil
import stat
import sys
import threading
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Callable, List, Optional, Tuple, Union

APP_ID = "org.ruscalinux.RuscaCleaner"
APP_VERSION = "1.99.3"
ICON_NAME = APP_ID


def _xdg(var: str, default: Path) -> Path:
    """Cartella XDG. La specifica ammette solo percorsi assoluti."""
    value = os.environ.get(var, "")
    return Path(value) if os.path.isabs(value) else default


# $HOME e le variabili XDG servono a *trovare* le cartelle, non ad autorizzare
# la cancellazione: quella la decide check_path().
HOME = Path(os.path.expanduser("~")).resolve()
CACHE = _xdg("XDG_CACHE_HOME", HOME / ".cache")
DATA = _xdg("XDG_DATA_HOME", HOME / ".local" / "share")
STATE = _xdg("XDG_STATE_HOME", HOME / ".local" / "state")
FLATPAK = HOME / ".var" / "app"
CONFIG = _xdg("XDG_CONFIG_HOME", HOME / ".config") / "ruscacleaner"
BASE_DIR = Path(__file__).resolve().parent
LANG_DIR = BASE_DIR / "lang"
ICON_SRC = BASE_DIR / "ruscacleaner.svg"
STYLE_SRC = BASE_DIR / "style.css"      # tema comune RuscaLinux
ADW_MIN = (1, 7)                         # libadwaita di Debian 13 trixie

# --------------------------------------------------------------- traduzioni ---
# lang/xx.json o lang/xx_YY.json. en.json è la base; una chiave che manca
# ovunque mostra il proprio nome invece di bloccare il programma.
_LANG_CODE = re.compile(r"[a-z]{2,3}(_[A-Z]{2})?")
# Ripieghi fra lingue vicine (specifiche, sezione 9.2): Hong Kong e Macao
# usano il cinese tradizionale, Singapore il semplificato; il portoghese
# senza variante legge il brasiliano, lo slovacco il ceco.
_LANG_ALIASES = {"zh_HK": "zh_TW", "zh_MO": "zh_TW", "zh_SG": "zh_CN", "zh": "zh_CN",
                 "pt": "pt_BR", "sk": "cs"}


def _read_lang(code: str) -> dict:
    """Solo coppie stringa->stringa: un file malformato non deve poter
    iniettare oggetti nell'interfaccia. Il codice viene convalidato prima di
    diventare un nome di file."""
    if not _LANG_CODE.fullmatch(code):
        return {}
    try:
        with (LANG_DIR / f"{code}.json").open(encoding="utf-8") as handle:
            data = json.load(handle)
    except (OSError, ValueError):
        return {}
    if not isinstance(data, dict):
        return {}
    return {k: v for k, v in data.items() if isinstance(k, str) and isinstance(v, str)}


def _language_codes() -> List[str]:
    """Lingue da provare, nell'ordine di gettext: LANGUAGE, poi la locale dei
    messaggi. Per ciascuna: variante (zh_HK), suo ripiego (zh_TW), lingua
    (zh), ripiego della lingua (zh_CN)."""
    locale = next((os.environ[v] for v in ("LC_ALL", "LC_MESSAGES", "LANG")
                   if os.environ.get(v)), "")
    locale = locale.split(".")[0].split("@")[0]
    if locale in ("", "C", "POSIX"):
        return []
    codes: List[str] = []
    for piece in os.environ.get("LANGUAGE", "").split(":") + [locale]:
        piece = piece.split(".")[0].split("@")[0].strip()
        lang = piece.split("_")[0]
        for code in (piece, _LANG_ALIASES.get(piece, ""), lang, _LANG_ALIASES.get(lang, "")):
            if code and code not in codes:
                codes.append(code)
    return codes


RTL_LANGS = ("ar",)


def _load_strings() -> Tuple[dict, str]:
    """Restituisce le stringhe e il codice della lingua usata."""
    strings = _read_lang("en")
    for code in _language_codes():
        if code.split("_")[0] == "en":
            break
        translated = _read_lang(code)
        if translated:
            strings.update(translated)
            return strings, code
    return strings, "en"


_STRINGS, _LANG = _load_strings()


def _(key: str, **fields) -> str:
    """Sostituisce solo i segnaposto attesi. Niente str.format(): con un file
    di lingua alterato, "{path.__class__}" darebbe accesso agli oggetti."""
    text = _STRINGS.get(key, key)
    for name, value in fields.items():
        text = text.replace("{" + name + "}", str(value))
    return text


def fmt(size: int) -> str:
    """Dimensione leggibile, in unità SI come il resto di GNOME."""
    if size < 1000:
        return f"{size} B"
    value = float(size)
    for unit in ("kB", "MB", "GB", "TB"):
        value /= 1000.0
        if value < 1000.0:
            return f"{value:.1f} {unit}"
    return f"{value:.1f} PB"


def tilde(path: Path) -> str:
    try:
        return "~/" + str(Path(path).relative_to(HOME))
    except ValueError:
        return str(path)


# ====================================================================== #
#  PROTEZIONI                                                            #
#  Rendono impossibile cancellare ciò che non è dell'utente o che sta     #
#  fuori dai confini attesi.                                              #
# ====================================================================== #
SKIP_SYMLINK = "symlink"
SKIP_OUTSIDE = "outside"
SKIP_OWNER = "owner"
SKIP_IS_HOME = "is_home"
SKIP_MISSING = "missing"   # normale, non si annuncia

_SKIP_MESSAGE = {
    SKIP_SYMLINK: "log_skip_symlink",
    SKIP_OUTSIDE: "log_skip_outside",
    SKIP_OWNER: "log_skip_owner",
    SKIP_IS_HOME: "log_skip_is_home",
}


def _is_within(path: Path, root: Path) -> bool:
    """True se path sta strettamente dentro root (non se coincide)."""
    try:
        return path.relative_to(root) != Path(".")
    except ValueError:
        return False


def volume_trash_dirs(bases: Optional[List[Path]] = None) -> List[Path]:
    """Cestini freedesktop sui dischi montati: gli unici percorsi fuori dalla
    home che il programma può toccare, e solo se
    - stanno sotto /media/<utente>, /run/media/<utente> o /media;
    - la cartella del disco è un vero punto di mount;
    - si chiamano .Trash-<uid> oppure .Trash/<uid>;
    - non sono collegamenti simbolici e appartengono all'utente.
    """
    uid = os.geteuid()
    try:
        import pwd
        user = pwd.getpwuid(uid).pw_name
    except (ImportError, KeyError):
        user = os.environ.get("USER") or ""
    if bases is None:
        bases = [Path("/media"), Path("/run/media")]
        if user:
            bases = [Path("/media") / user, Path("/run/media") / user] + bases
    found: List[Path] = []
    seen = set()
    for base in bases:
        try:
            entries = sorted(base.iterdir())
        except OSError:
            continue
        for volume in entries:
            try:
                if volume.is_symlink() or not volume.is_dir():
                    continue
                if not os.path.ismount(str(volume)):
                    continue
            except OSError:
                continue
            for candidate in (volume / f".Trash-{uid}", volume / ".Trash" / str(uid)):
                try:
                    info = os.lstat(candidate)
                except OSError:
                    continue
                if not stat.S_ISDIR(info.st_mode) or info.st_uid != uid:
                    continue
                resolved = candidate.resolve()
                if resolved not in seen:
                    seen.add(resolved)
                    found.append(candidate)
    return found


# Radici consentite (home + cestini validati), già risolte. Si calcolano una
# volta per operazione: un disco può essere montato o smontato fra due.
_roots_real: Optional[List[Path]] = None


def reset_path_cache() -> None:
    """Da chiamare all'inizio di ogni operazione (elenco, scansione, pulizia)."""
    global _roots_real
    _roots_real = None


def _real_roots() -> List[Path]:
    global _roots_real
    if _roots_real is None:
        roots = []
        for root in [HOME] + volume_trash_dirs():
            try:
                roots.append(root.resolve())
            except (OSError, RuntimeError):
                continue
        _roots_real = roots
    return _roots_real


def check_path(path: Path) -> Optional[str]:
    """None se il percorso si può toccare, altrimenti il motivo del rifiuto.
    lstat, non stat: un collegamento simbolico viene riconosciuto e rifiutato
    invece di essere seguito. Un percorso inesistente non è "consentito":
    è un caso a parte, così chi dimentica di controllarlo non riceve un via
    libera."""
    try:
        info = os.lstat(path)
    except OSError:
        return SKIP_MISSING
    if stat.S_ISLNK(info.st_mode):
        return SKIP_SYMLINK
    if info.st_uid != os.geteuid():
        return SKIP_OWNER
    try:
        real = Path(path).resolve()
    except (OSError, RuntimeError):
        return SKIP_OUTSIDE
    if real == HOME:
        return SKIP_IS_HOME
    for root in _real_roots():
        if real == root or _is_within(real, root):
            return None
    return SKIP_OUTSIDE


def home_refusal() -> Optional[str]:
    """Errore se la home non appartiene all'utente effettivo. Copre anche
    su, pkexec e le shell di root, che SUDO_USER non intercetta."""
    try:
        info = os.stat(HOME)
    except OSError:
        return _("err_home_owner", path=HOME)
    if info.st_uid != os.geteuid():
        return _("err_home_owner", path=HOME)
    return None


# ======================================================================= #
#  MISURA E CANCELLAZIONE                                                 #
# ======================================================================= #
def dir_size(path: Path) -> int:
    """Somma dei file dentro path, senza seguire collegamenti. Iterativa:
    una gerarchia molto profonda non deve far fallire il calcolo."""
    total = 0
    stack = [str(path)]
    while stack:
        current = stack.pop()
        try:
            with os.scandir(current) as entries:
                for entry in entries:
                    try:
                        if entry.is_symlink():
                            continue
                        if entry.is_dir(follow_symlinks=False):
                            stack.append(entry.path)
                        else:
                            total += entry.stat(follow_symlinks=False).st_size
                    except OSError:
                        continue
        except OSError:
            continue
    return total


def _entry_size(path: Path) -> Optional[int]:
    """Dimensione di path senza seguire collegamenti; None se non esiste.
    Un collegamento vale 0: non verrà comunque toccato."""
    try:
        info = os.lstat(path)
    except OSError:
        return None
    if stat.S_ISLNK(info.st_mode):
        return 0
    if stat.S_ISDIR(info.st_mode):
        return dir_size(path)
    return info.st_size


def _rmtree_counted(path: Path) -> Tuple[int, Optional[OSError]]:
    """Elimina un albero e restituisce i byte spariti davvero: se rmtree si
    ferma a metà si conta ciò che è sparito, non ciò che si sperava."""
    before = dir_size(path)
    try:
        shutil.rmtree(path)
    except OSError as err:
        left = dir_size(path) if os.path.lexists(path) else 0
        return before - left, err
    return before, None


CLEAR_DIR = "clear_dir"   # svuota la cartella, lasciandola esistere
DELETE = "delete"         # elimina il percorso
TRUNCATE = "truncate"     # azzera il file, lasciandolo esistere


@dataclass
class Outcome:
    freed: int = 0
    errors: int = 0
    items: int = 0

    def __iadd__(self, other: "Outcome") -> "Outcome":
        self.freed += other.freed
        self.errors += other.errors
        self.items += other.items
        return self


def _truncate_file(path: Path) -> None:
    """O_NOFOLLOW: fra il controllo e l'apertura non c'è una finestra in cui
    sostituire il file con un collegamento."""
    fd = os.open(path, os.O_WRONLY | os.O_NOFOLLOW)
    try:
        os.ftruncate(fd, 0)
    finally:
        os.close(fd)


def _log_error(log: Callable[[str], None], path: Path, err: OSError) -> None:
    log("  ✗ " + _("log_error", path=tilde(path), reason=err.strerror or err))


def _clear_directory(path: Path, log: Callable[[str], None], dry_run: bool) -> Outcome:
    """Svuota una cartella voce per voce: una voce che non si lascia
    cancellare fa fallire quella voce e nient'altro."""
    result = Outcome()
    uid = os.geteuid()
    try:
        with os.scandir(path) as iterator:
            entries = list(iterator)
    except OSError as err:
        _log_error(log, path, err)
        result.errors += 1
        return result
    for entry in entries:
        target = Path(entry.path)
        try:
            info = entry.stat(follow_symlinks=False)
            if info.st_uid != uid:
                log("  · " + _("log_skip_owner", path=tilde(target)))
                continue
            if entry.is_dir(follow_symlinks=False):
                if dry_run:
                    result.freed += dir_size(target)
                else:
                    freed, err = _rmtree_counted(target)
                    result.freed += freed
                    if err:
                        raise err
            else:
                if not dry_run:
                    os.unlink(entry.path)
                result.freed += info.st_size
            result.items += 1
        except OSError as err:
            result.errors += 1
            _log_error(log, target, err)
    return result


PathSource = Union[Path, Tuple[Path, str]]


def _paths(*sources: PathSource) -> Callable[[], List[Path]]:
    """Percorsi calcolati a ogni scansione: Path fissi oppure coppie
    (base, schema glob), così nuove app Flatpak o nuovi log si vedono."""
    def collect() -> List[Path]:
        out: List[Path] = []
        for source in sources:
            if isinstance(source, tuple):
                base, pattern = source
                out.extend(sorted(base.glob(pattern)))
            else:
                out.append(source)
        return out
    return collect


@dataclass
class Target:
    key: str
    title: str
    subtitle: str
    mode: str
    paths: Callable[[], List[Path]]
    default: bool = False
    note: str = ""
    history: bool = False          # va nella riga espansibile delle cronologie
    row: object = field(default=None, repr=False)

    def resolved_paths(self) -> List[Path]:
        try:
            return list(self.paths())
        except OSError:
            return []

    def exists(self) -> bool:
        return any(os.path.lexists(p) for p in self.resolved_paths())

    def measure(self) -> Tuple[int, bool]:
        """Dimensione totale e presenza, con un solo lstat per percorso."""
        total, exists = 0, False
        for path in self.resolved_paths():
            size = _entry_size(path)
            if size is not None:
                exists = True
                total += size
        return total, exists

    def clean(self, log: Callable[[str], None], dry_run: bool = False) -> Outcome:
        result = Outcome()
        for path in self.resolved_paths():
            refusal = check_path(path)
            if refusal == SKIP_MISSING:
                continue
            if refusal:
                log("  ✗ " + _(_SKIP_MESSAGE[refusal], path=tilde(path)))
                result.errors += 1
                continue
            try:
                if self.mode == CLEAR_DIR:
                    if not path.is_dir():
                        continue
                    step = _clear_directory(path, log, dry_run)
                    result += step
                    log("  ✓ " + _("log_emptied", path=tilde(path),
                                   size=fmt(step.freed), count=step.items))
                elif self.mode == TRUNCATE:
                    if not path.is_file():
                        continue
                    size = os.lstat(path).st_size
                    if not dry_run:
                        _truncate_file(path)
                    result.freed += size
                    result.items += 1
                    log("  ✓ " + _("log_truncated", path=tilde(path), size=fmt(size)))
                else:
                    if path.is_dir():
                        if dry_run:
                            size = dir_size(path)
                        else:
                            size, err = _rmtree_counted(path)
                            if err:
                                result.freed += size
                                raise err
                    else:
                        size = os.lstat(path).st_size
                        if not dry_run:
                            os.unlink(path)
                    result.freed += size
                    result.items += 1
                    log("  ✓ " + _("log_deleted", path=tilde(path), size=fmt(size)))
            except OSError as err:
                result.errors += 1
                _log_error(log, path, err)
        return result


def build_targets() -> List[Target]:
    """Accese per difetto solo le voci rigenerabili senza perdita (miniature,
    file recenti); tutto ciò che non si ricostruisce parte spento.
    Non si toccano: dati dei browser, journal di sistema, impostazioni delle
    singole applicazioni, ~/.ssh/known_hosts e ~/.wget-hsts (proteggono le
    connessioni)."""
    def volume_trash_paths() -> List[Path]:
        return [root / sub for root in volume_trash_dirs()
                for sub in ("files", "info", "expunged") if (root / sub).is_dir()]

    return [
        Target("thumbs", _("t_thumbs"), _("t_thumbs_sub"), CLEAR_DIR,
               _paths(CACHE / "thumbnails", HOME / ".thumbnails",
                      (FLATPAK, "*/cache/thumbnails")),
               default=True),
        Target("recent", _("t_recent"), _("t_recent_sub"), DELETE,
               _paths(DATA / "recently-used.xbel", DATA / "recently-used.xbel.bak",
                      HOME / ".recently-used.xbel",
                      (FLATPAK, "*/data/recently-used.xbel")),
               default=True, note=_("note_recent")),
        Target("clipboard", _("t_clipboard"), _("t_clipboard_sub"), DELETE,
               _paths(DATA / "gpaste" / "history.xml",
                      CACHE / "clipboard-indicator@tudmotu.com" / "registry.txt"),
               note=_("note_clipboard")),
        Target("search", _("t_search"), _("t_search_sub"), CLEAR_DIR,
               _paths(CACHE / "tracker3" / "files"),
               note=_("note_search")),
        Target("gvfs", _("t_gvfs"), _("t_gvfs_sub"), CLEAR_DIR,
               _paths(DATA / "gvfs-metadata"),
               note=_("note_gvfs")),
        Target("logs", _("t_logs"), _("t_logs_sub"), DELETE,
               _paths(HOME / ".xsession-errors", HOME / ".xsession-errors.old",
                      (DATA / "xorg", "Xorg.*.log*"))),
        Target("trash", _("t_trash"), _("t_trash_sub"), CLEAR_DIR,
               _paths(DATA / "Trash" / "files", DATA / "Trash" / "info",
                      DATA / "Trash" / "expunged")),
        Target("volume_trash", _("t_volume_trash"), _("t_volume_trash_sub"),
               CLEAR_DIR, volume_trash_paths, note=_("note_volume_trash")),
        # --- cronologie ---------------------------------------------------
        Target("bash", _("t_bash"), "~/.bash_history", TRUNCATE,
               _paths(HOME / ".bash_history"),
               note=_("note_shell"), history=True),
        Target("zsh", _("t_zsh"), "~/.zsh_history · ~/.zhistory · ~/.histfile",
               TRUNCATE,
               _paths(HOME / ".zsh_history", HOME / ".zhistory",
                      HOME / ".histfile", DATA / "zsh" / "history"),
               note=_("note_shell"), history=True),
        Target("fish", _("t_fish"), "~/.local/share/fish/fish_history", TRUNCATE,
               _paths(DATA / "fish" / "fish_history"),
               note=_("note_shell"), history=True),
        Target("tools", _("t_tools"), _("t_tools_sub"), DELETE,
               _paths(HOME / ".python_history", HOME / ".lesshst", STATE / "lesshst",
                      HOME / ".sqlite_history", HOME / ".psql_history",
                      HOME / ".mysql_history", HOME / ".node_repl_history",
                      HOME / ".irb_history", HOME / ".rediscli_history",
                      HOME / ".Rhistory", HOME / ".octave_hist",
                      HOME / ".gnuplot_history",
                      HOME / ".julia" / "logs" / "repl_history.jl"),
               note=_("note_tools"), history=True),
        Target("editors", _("t_editors"), _("t_editors_sub"), DELETE,
               _paths(HOME / ".viminfo", STATE / "nvim" / "shada" / "main.shada",
                      DATA / "nano" / "search_history",
                      DATA / "nano" / "filepos_history",
                      HOME / ".nano" / "search_history",
                      HOME / ".nano" / "filepos_history",
                      HOME / ".emacs.d" / "recentf", HOME / ".emacs.d" / "history"),
               note=_("note_tools"), history=True),
    ]


def measure_all(targets: List[Target]) -> dict:
    """Misura in parallelo: la scansione è limitata dall'I/O."""
    if not targets:
        return {}
    with ThreadPoolExecutor(max_workers=min(8, len(targets))) as pool:
        return dict(zip((t.key for t in targets), pool.map(Target.measure, targets)))


# ======================================================================= #
#  RIGA DI COMANDO                                                        #
# ======================================================================= #
def run_list() -> int:
    """Elenca obiettivi e dimensioni. Non tocca nulla."""
    reset_path_cache()
    targets = build_targets()
    sizes = measure_all(targets)
    total = 0
    for target in targets:
        size, exists = sizes[target.key]
        total += size
        state = fmt(size) if exists else _("no_data")
        print(f"{target.key:<14} {target.title:<40} {state}")
    print("-" * 70)
    print(_("scan_done", size=fmt(total)))
    return 0


def run_simulation() -> int:
    """Simula le voci accese per difetto. La riga di comando non cancella
    mai: una cancellazione senza la finestra di conferma è proprio il modo
    in cui questi programmi fanno danni."""
    reset_path_cache()
    print(_("confirm_dry"))
    print(_("confirm_caveat"))
    print()
    outcome = Outcome()
    for target in build_targets():
        if not target.default or not target.exists():
            continue
        print(f"{target.title}:")
        outcome += target.clean(print, dry_run=True)
        print()
    print(_("done_dry", size=fmt(outcome.freed)))
    return 0


# ======================================================================= #
#  INTERFACCIA                                                            #
# ======================================================================= #
WINDOW_STATE = CONFIG / "window.json"
DEFAULT_SIZE = (600, 700)


def load_window_state() -> Tuple[int, int, bool]:
    """Dimensione e stato massimizzato dell'ultima chiusura. Valori assurdi o
    file illeggibile: si torna ai predefiniti, senza errori."""
    try:
        with WINDOW_STATE.open(encoding="utf-8") as handle:
            data = json.load(handle)
        width, height = int(data["width"]), int(data["height"])
        if 360 <= width <= 10000 and 294 <= height <= 10000:
            return width, height, bool(data.get("maximized", False))
    except (OSError, ValueError, KeyError, TypeError):
        pass
    return DEFAULT_SIZE[0], DEFAULT_SIZE[1], False


def save_window_state(width: int, height: int, maximized: bool) -> None:
    try:
        CONFIG.mkdir(parents=True, exist_ok=True)
        tmp = WINDOW_STATE.with_suffix(".tmp")
        with tmp.open("w", encoding="utf-8") as handle:
            json.dump({"width": width, "height": height, "maximized": maximized}, handle)
        os.replace(tmp, WINDOW_STATE)
    except OSError:
        pass                    # non ricordare la dimensione non è un errore


def ensure_icon() -> None:
    """Se il tema non conosce l'icona (programma avviato dai sorgenti), la
    copia nel tema hicolor dell'utente. Se fallisce, niente icona invece del
    segnaposto "immagine mancante"."""
    dest = DATA / "icons" / "hicolor" / "scalable" / "apps" / f"{ICON_NAME}.svg"
    if dest.exists() or not ICON_SRC.exists():
        return
    try:
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ICON_SRC, dest)
    except OSError:
        return


@lru_cache(maxsize=1)
def have_gtk() -> bool:
    try:
        import gi
        gi.require_version("Gtk", "4.0")
        gi.require_version("Adw", "1")
        from gi.repository import Adw, Gtk  # noqa: F401
        return (Adw.get_major_version(), Adw.get_minor_version()) >= ADW_MIN
    except (ImportError, ValueError):
        return False


def _theme_has_icon() -> bool:
    try:
        import gi
        gi.require_version("Gtk", "4.0")
        from gi.repository import Gdk, Gtk
        display = Gdk.Display.get_default()
        return display is not None and \
            Gtk.IconTheme.get_for_display(display).has_icon(ICON_NAME)
    except (ImportError, ValueError):
        return False


def run_gui(dry_run: bool) -> int:
    import gi
    gi.require_version("Gtk", "4.0")
    gi.require_version("Adw", "1")
    from gi.repository import Adw, Gdk, Gio, GLib, Gtk, Pango

    def show_about_dialog(parent, tr, app_id, app_name, version, description, has_icon,
                          components=()):
        """Finestra «Informazioni» comune ai RuscaLinux OS Tools.

        Pagina principale: icona, nome, versione, descrizione (sempre visibile:
        in Adw.AboutDialog finirebbe in una sottopagina) e collegamenti. La nota
        di sviluppo e' una riga dell'elenco, come la licenza: con un clic apre la
        sua pagina nella stessa finestra (specifiche, sezioni 3.10 e 12).
        `tr` restituisce il testo tradotto di una chiave di lang/.
        `components`: componenti esterni (nome, licenza, indirizzo), mostrati in
        un gruppo «Componenti esterni» (specifiche, sezioni 3.10 e 6)."""
        def open_uri(_row, uri):
            def done(launcher, result):
                try:
                    launcher.launch_finish(result)
                except GLib.Error:
                    pass
            Gtk.UriLauncher.new(uri).launch(parent, None, done)

        nav = Adw.NavigationView()

        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6,
                      margin_top=12, margin_bottom=24, margin_start=24, margin_end=24)
        icon = Gtk.Image(icon_name=app_id if has_icon else "application-x-executable",
                         pixel_size=128, margin_bottom=12)
        icon.add_css_class("icon-dropshadow")
        box.append(icon)
        for text, css in ((app_name, "title-1"), (version, "dim-label"),
                          (description, "body")):
            label = Gtk.Label(label=text, wrap=True, justify=Gtk.Justification.CENTER)
            label.add_css_class(css)
            box.append(label)

        links = Adw.PreferencesGroup(margin_top=18)
        for title, subtitle, uri in (
                (tr("about_website"), "www.ruscalinux.org", "https://www.ruscalinux.org/"),
                (tr("about_support"), "info@ruscalinux.org", "mailto:info@ruscalinux.org"),
                (tr("about_license"), "GNU GPL 3.0", "https://www.gnu.org/licenses/gpl-3.0.html")):
            row = Adw.ActionRow(title=title, subtitle=subtitle, activatable=True)
            row.add_suffix(Gtk.Image(icon_name="adw-external-link-symbolic"))
            row.connect("activated", open_uri, uri)
            links.add(row)
        # Nota di sviluppo: una riga come le altre, che apre la sua pagina.
        note_row = Adw.ActionRow(title=tr("dev_note_title"), activatable=True)
        note_row.add_suffix(Gtk.Image(icon_name="go-next-symbolic"))
        links.add(note_row)
        box.append(links)

        if components:
            ext = Adw.PreferencesGroup(title=tr("about_components"), margin_top=12)
            for name, licence, uri in components:
                row = Adw.ActionRow(title=name, subtitle=licence, activatable=True)
                row.add_suffix(Gtk.Image(icon_name="adw-external-link-symbolic"))
                row.connect("activated", open_uri, uri)
                ext.add(row)
            box.append(ext)

        copyright_label = Gtk.Label(label="© 2026 Nunzio Curcuruto", margin_top=12)
        copyright_label.add_css_class("caption")
        copyright_label.add_css_class("dim-label")
        box.append(copyright_label)

        scroller = Gtk.ScrolledWindow(hscrollbar_policy=Gtk.PolicyType.NEVER,
                                      propagate_natural_height=True, child=box)
        view = Adw.ToolbarView(content=scroller)
        view.add_top_bar(Adw.HeaderBar(show_title=False))
        nav.add(Adw.NavigationPage(title=app_name, child=view))

        # Pagina della nota: testo a colore pieno (contrasto >= 4,5:1), pulsante
        # indietro nella barra in alto, tradotto da libadwaita.
        note_label = Gtk.Label(label=tr("ai_note"), wrap=True, xalign=0, valign=Gtk.Align.START,
                               margin_top=12, margin_bottom=24, margin_start=24, margin_end=24)
        note_label.add_css_class("body")
        note_view = Adw.ToolbarView(content=note_label)
        note_view.add_top_bar(Adw.HeaderBar())
        note_page = Adw.NavigationPage(title=tr("dev_note_title"), child=note_view)
        note_row.connect("activated", lambda _row: nav.push(note_page))

        Adw.Dialog(title=app_name, content_width=420, child=nav).present(parent)

    class RuscaWindow(Adw.ApplicationWindow):
        """Una pagina sola: elenco di cosa si può pulire (solo le voci con
        dati), totale e pulsante sempre visibili nella barra in basso.
        Simulazione, limiti, scorciatoie e informazioni stanno nel menu."""

        def __init__(self, app, dry_run: bool):
            super().__init__(application=app, title="RuscaCleaner")
            width, height, maximized = load_window_state()
            self.set_default_size(width, height)
            self.set_size_request(360, 294)
            if maximized:
                self.maximize()
            if _theme_has_icon():
                self.set_icon_name(ICON_NAME)
            self.targets = build_targets()
            self.sizes = {}
            self.busy = False
            self.dry_run = dry_run
            self.log_lines: List[str] = []

            # --- azioni -------------------------------------------------
            for name, callback in (("rescan", lambda *_a: self.scan()),
                                   ("log", self.show_log),
                                   ("limits", self.show_limits),
                                   ("shortcuts", self.show_shortcuts),
                                   ("about", self.show_about)):
                action = Gio.SimpleAction.new(name, None)
                action.connect("activate", callback)
                self.add_action(action)
            dry_action = Gio.SimpleAction.new_stateful(
                "dry", None, GLib.Variant.new_boolean(dry_run))
            dry_action.connect("change-state", self.on_dry_changed)
            self.add_action(dry_action)

            # --- barra del titolo -----------------------------------------
            header = Adw.HeaderBar()
            scan_button = Gtk.Button(icon_name="view-refresh-symbolic",
                                     tooltip_text=_("rescan_tooltip"),
                                     action_name="win.rescan")
            scan_button.update_property([Gtk.AccessibleProperty.LABEL],
                                        [_("rescan_tooltip")])
            header.pack_start(scan_button)
            menu = Gio.Menu()
            options = Gio.Menu()
            options.append(_("dry_title"), "win.dry")
            options.append(_("group_limits"), "win.limits")
            menu.append_section(None, options)
            app_menu = Gio.Menu()
            app_menu.append(_("shortcuts"), "win.shortcuts")
            app_menu.append(_("about"), "win.about")
            menu.append_section(None, app_menu)
            header.pack_end(Gtk.MenuButton(icon_name="open-menu-symbolic",
                                           menu_model=menu, primary=True,
                                           tooltip_text=_("main_menu")))

            # Avviso di simulazione: sempre visibile finché è attiva.
            self.banner = Adw.Banner(title=_("dry_banner"),
                                     button_label=_("dry_off"),
                                     action_name="win.dry", revealed=dry_run)

            # --- contenuto ----------------------------------------------
            self.stack = Gtk.Stack(transition_type=Gtk.StackTransitionType.CROSSFADE)
            loading = Adw.StatusPage(title=_("scanning"))
            loading.set_paintable(Adw.SpinnerPaintable(widget=loading))
            self.stack.add_named(loading, "loading")
            self.stack.add_named(Adw.StatusPage(icon_name="emblem-ok-symbolic",
                                                title=_("all_clean_title"),
                                                description=_("all_clean_desc")),
                                 "clean")

            page = Adw.PreferencesPage()
            self.main_group = Adw.PreferencesGroup(title=_("group_what"))
            self.hist_group = Adw.PreferencesGroup(title=_("group_hist"))
            page.add(self.main_group)
            page.add(self.hist_group)
            self.size_labels = {}
            self.rows = {}
            for target in self.targets:
                row = Adw.ActionRow(title=target.title, subtitle=target.subtitle,
                                    subtitle_lines=2)
                size = Gtk.Label(valign=Gtk.Align.CENTER)
                size.add_css_class("dim-label")
                size.add_css_class("numeric")
                row.add_suffix(size)
                switch = Gtk.Switch(active=target.default, valign=Gtk.Align.CENTER)
                switch.update_property([Gtk.AccessibleProperty.LABEL], [target.title])
                switch.connect("notify::active", lambda *_a: self.update_total())
                row.add_suffix(switch)
                row.set_activatable_widget(switch)
                target.row = switch
                self.rows[target.key] = row
                self.size_labels[target.key] = size
                (self.hist_group if target.history else self.main_group).add(row)
            self.stack.add_named(page, "list")

            # --- barra in basso: totale e azione, sempre a portata --------
            # A capo invece dei puntini: la cifra deve restare leggibile.
            self.total_label = Gtk.Label(label=_("total_pending"), xalign=0,
                                         wrap=True, hexpand=True)
            self.total_label.add_css_class("heading")
            self.clean_button = Gtk.Button(valign=Gtk.Align.CENTER)
            self.clean_button.connect("clicked", self.on_clean_clicked)
            self.total_label.set_margin_start(6)
            self.clean_button.set_margin_end(6)
            self.action_bar = Gtk.ActionBar()
            self.action_bar.pack_start(self.total_label)
            self.action_bar.pack_end(self.clean_button)
            self.update_clean_button()

            # Le notifiche compaiono sopra la barra in basso, non su di essa.
            self.toasts = Adw.ToastOverlay(child=self.stack)
            toolbar = Adw.ToolbarView(content=self.toasts)
            toolbar.add_top_bar(header)
            toolbar.add_top_bar(self.banner)
            toolbar.add_bottom_bar(self.action_bar)
            self.set_content(toolbar)

            # La finestra non si chiude a metà cancellazione.
            self.connect("close-request", self.on_close_request)
            self.scan()

        # -- dialoghi -------------------------------------------------------
        def show_about(self, *_a):
            show_about_dialog(self, _, APP_ID, "RuscaCleaner", APP_VERSION,
                              _("app_subtitle"), _theme_has_icon())

        def show_shortcuts(self, *_a):
            """Adw.ShortcutsDialog arriva solo con libadwaita 1.8: su trixie si
            usa un Adw.Dialog con righe normali."""
            group = Adw.PreferencesGroup()
            for title, accel in ((_("rescan_tooltip"), "F5"),
                                 (_("shortcuts"), "<Control>question"),
                                 (_("main_menu"), "F10"),
                                 (_("sc_close"), "<Control>w"),
                                 (_("sc_quit"), "<Control>q")):
                row = Adw.ActionRow(title=title)
                ok, key, mods = Gtk.accelerator_parse(accel)
                keys = Gtk.Label(label=Gtk.accelerator_get_label(key, mods) if ok else accel)
                keys.add_css_class("dim-label")
                row.add_suffix(keys)
                group.add(row)
            page = Adw.PreferencesPage()
            page.add(group)
            view = Adw.ToolbarView(content=page)
            view.add_top_bar(Adw.HeaderBar())
            Adw.Dialog(title=_("shortcuts"), content_width=420, child=view).present(self)

        def show_limits(self, *_a):
            dialog = Adw.AlertDialog(heading=_("group_limits"), body=_("limits_body"))
            dialog.add_response("close", _("close"))
            dialog.set_default_response("close")
            dialog.set_close_response("close")
            dialog.present(self)

        def show_log(self, *_a):
            view = Gtk.TextView(editable=False, cursor_visible=False,
                                wrap_mode=Gtk.WrapMode.WORD_CHAR,
                                top_margin=12, bottom_margin=12,
                                left_margin=12, right_margin=12)
            view.add_css_class("monospace")
            view.get_buffer().set_text("\n".join(self.log_lines))
            scroller = Gtk.ScrolledWindow(child=view, vexpand=True)
            toolbar = Adw.ToolbarView(content=scroller)
            toolbar.add_top_bar(Adw.HeaderBar())
            Adw.Dialog(title=_("group_log"), content_width=560, content_height=420,
                       child=toolbar).present(self)

        # -- utilità ------------------------------------------------------
        def log(self, text: str):
            self.log_lines.append(text)
            del self.log_lines[:-self._LOG_MAX_LINES]
            return False

        _LOG_MAX_LINES = 400   # il registro non deve crescere senza limite

        def on_close_request(self, *_a):
            if self.busy:
                self.toasts.add_toast(Adw.Toast(title=_("toast_busy")))
                return True
            width, height = self.get_default_size()
            save_window_state(width, height, self.is_maximized())
            return False

        def on_dry_changed(self, action, value):
            action.set_state(value)
            self.dry_run = value.get_boolean()
            self.banner.set_revealed(self.dry_run)
            self.update_clean_button()

        def update_clean_button(self):
            # In simulazione nulla viene cancellato: niente rosso.
            self.clean_button.set_label(_("btn_simulate") if self.dry_run
                                        else _("btn_clean"))
            self.clean_button.remove_css_class("destructive-action")
            self.clean_button.remove_css_class("suggested-action")
            self.clean_button.add_css_class("suggested-action" if self.dry_run
                                            else "destructive-action")

        def set_busy(self, busy: bool):
            self.busy = busy
            self.clean_button.set_sensitive(not busy)
            for name in ("rescan", "dry"):
                self.lookup_action(name).set_enabled(not busy)

        def selected(self) -> List[Target]:
            return [t for t in self.targets
                    if self.rows[t.key].get_visible() and t.row.get_active()]

        # -- analisi -------------------------------------------------------
        def scan(self):
            if self.busy:
                return
            self.set_busy(True)
            self.stack.set_visible_child_name("loading")
            self.action_bar.set_revealed(False)
            threading.Thread(target=self._scan_worker, daemon=True).start()

        def _scan_worker(self):
            reset_path_cache()
            GLib.idle_add(self._scan_done, measure_all(self.targets))

        def _scan_done(self, sizes):
            self.sizes = sizes
            # Si mostrano solo le voci che hanno davvero qualcosa da rimuovere:
            # una cartella vuota non è una traccia.
            for target in self.targets:
                size, exists = sizes[target.key]
                present = exists and size > 0
                self.rows[target.key].set_visible(present)
                self.size_labels[target.key].set_label(fmt(size))
                if not present:
                    target.row.set_active(False)
            for group, history in ((self.main_group, False), (self.hist_group, True)):
                group.set_visible(any(self.rows[t.key].get_visible()
                                      for t in self.targets if t.history == history))
            anything = any(self.rows[t.key].get_visible() for t in self.targets)
            self.stack.set_visible_child_name("list" if anything else "clean")
            self.action_bar.set_revealed(anything)
            self.update_total()
            self.log(_("scan_done", size=fmt(self._total_bytes())))
            self.set_busy(False)
            return False

        def _total_bytes(self) -> int:
            return sum(self.sizes.get(t.key, (0, False))[0] for t in self.selected())

        def update_total(self):
            self.total_label.set_label(_("total", size=fmt(self._total_bytes())))

        # -- pulizia -------------------------------------------------------
        def on_clean_clicked(self, _button):
            chosen = self.selected()
            if not chosen:
                self.toasts.add_toast(Adw.Toast(title=_("none_selected")))
                return
            # La conferma elenca i percorsi veri: chi autorizza una
            # cancellazione ha diritto di sapere su quali file.
            notes: List[str] = []
            listing: List[str] = []
            for target in chosen:
                listing.append(f"<b>{GLib.markup_escape_text(target.title)}</b>")
                listing += [GLib.markup_escape_text(tilde(p))
                            for p in target.resolved_paths() if os.path.lexists(p)]
                if target.note and target.note not in notes:
                    notes.append(target.note)
            # In simulazione contano solo i percorsi: avvisi e limiti no.
            body = [_("confirm_dry")] if self.dry_run else [_("confirm_caveat")] + notes
            dialog = Adw.AlertDialog(heading=_("confirm_heading"),
                                     body="\n\n".join(body))
            paths = Gtk.Label(label="\n".join(listing), use_markup=True, xalign=0,
                              wrap=True, wrap_mode=Pango.WrapMode.WORD_CHAR,
                              margin_top=8, margin_bottom=8,
                              margin_start=12, margin_end=12)
            paths.add_css_class("caption")
            scroller = Gtk.ScrolledWindow(child=paths, max_content_height=180,
                                          propagate_natural_height=True,
                                          hscrollbar_policy=Gtk.PolicyType.NEVER)
            scroller.add_css_class("card")
            dialog.set_extra_child(scroller)
            dialog.add_response("cancel", _("cancel"))
            dialog.add_response("clean", _("btn_simulate") if self.dry_run else _("clean"))
            dialog.set_response_appearance(
                "clean", Adw.ResponseAppearance.SUGGESTED if self.dry_run
                else Adw.ResponseAppearance.DESTRUCTIVE)
            dialog.set_default_response("cancel")
            dialog.set_close_response("cancel")
            dialog.connect("response", self.on_dialog_response, chosen)
            dialog.present(self)

        def on_dialog_response(self, _dialog, response, chosen):
            if response != "clean":
                return
            self.set_busy(True)
            self.clean_button.set_label(_("cleaning"))
            self.log("")
            self.log(_("cleaning"))
            if self.dry_run:
                self.log(_("log_dry"))
            # Thread non-daemon: una cancellazione iniziata arriva in fondo.
            threading.Thread(target=self._clean_worker, args=(chosen, self.dry_run),
                             daemon=False).start()

        def _clean_worker(self, chosen: List[Target], dry: bool):
            reset_path_cache()
            outcome = Outcome()
            for target in chosen:
                GLib.idle_add(self.log, f"{target.title}:")
                outcome += target.clean(lambda msg: GLib.idle_add(self.log, msg),
                                        dry_run=dry)
            GLib.idle_add(self._clean_done, outcome, dry)

        def _clean_done(self, outcome: Outcome, dry: bool):
            size = fmt(outcome.freed)
            if dry:
                message = _("done_dry", size=size)
            elif outcome.errors:
                message = _("done_errors", size=size, count=outcome.errors)
            else:
                message = _("done", size=size)
            self.log(message)
            toast = Adw.Toast(title=GLib.markup_escape_text(message), timeout=8,
                              button_label=_("details"), action_name="win.log")
            self.toasts.add_toast(toast)
            self.set_busy(False)
            self.update_clean_button()
            if not dry:            # in simulazione nulla è cambiato
                self.scan()
            return False

    class RuscaCleaner(Adw.Application):
        def __init__(self, dry_run: bool):
            super().__init__(application_id=APP_ID)
            self.dry_run = dry_run

        def do_startup(self):
            Adw.Application.do_startup(self)
            # GTK sceglie la direzione dalla propria lingua; se le traduzioni
            # del programma sono in arabo il layout va comunque da destra.
            if _LANG.split("_")[0] in RTL_LANGS:
                Gtk.Widget.set_default_direction(Gtk.TextDirection.RTL)
            if not _theme_has_icon():
                ensure_icon()
            if _theme_has_icon():
                Gtk.Window.set_default_icon_name(ICON_NAME)
            # Tema comune RuscaLinux. Se manca, l'app resta usabile con i
            # colori standard di GNOME.
            if STYLE_SRC.is_file():
                provider = Gtk.CssProvider()
                provider.load_from_path(str(STYLE_SRC))
                Gtk.StyleContext.add_provider_for_display(
                    Gdk.Display.get_default(), provider,
                    Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)
            # Le classi rusca-light/rusca-dark scelgono la palette (style.css)
            # e seguono la modalità chiara/scura del sistema.
            style = Adw.StyleManager.get_default()
            style.connect("notify::dark", lambda *_a: self.update_theme())
            self.connect("window-added", lambda *_a: self.update_theme())
            quit_action = Gio.SimpleAction.new("quit", None)
            quit_action.connect("activate", self.on_quit)
            self.add_action(quit_action)
            for action, accels in (("app.quit", ["<Control>q"]),
                                   ("window.close", ["<Control>w"]),
                                   ("win.rescan", ["F5", "<Control>r"]),
                                   ("win.shortcuts", ["<Control>question"])):
                self.set_accels_for_action(action, accels)

        def update_theme(self):
            dark = Adw.StyleManager.get_default().get_dark()
            for window in self.get_windows():
                window.remove_css_class("rusca-light" if dark else "rusca-dark")
                window.add_css_class("rusca-dark" if dark else "rusca-light")

        def on_quit(self, *_a):
            # Passa da close-request: una pulizia in corso blocca l'uscita.
            for window in list(self.get_windows()):
                window.close()

        def do_activate(self):
            window = self.props.active_window or RuscaWindow(self, self.dry_run)
            window.present()

    return RuscaCleaner(dry_run).run(None)


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        prog="ruscacleaner",
        description="Remove activity traces from your home folder.")
    parser.add_argument("--dry-run", action="store_true",
                        help="report what would be removed, remove nothing")
    parser.add_argument("--list", action="store_true", dest="only_list",
                        help="list targets and sizes, then exit")
    parser.add_argument("--allow-root", action="store_true",
                        help="permit running with an effective uid of 0")
    parser.add_argument("--version", action="version",
                        version=f"RuscaCleaner {APP_VERSION}")
    args = parser.parse_args(argv)
    # Non basta SUDO_USER: "su" senza trattino lascia la HOME dell'utente con
    # euid 0 e pkexec non lo imposta. Conta a chi appartiene la home.
    if os.geteuid() == 0 and not args.allow_root:
        print(_("err_root"), file=sys.stderr)
        return 1
    refusal = home_refusal()
    if refusal:
        print(refusal, file=sys.stderr)
        return 1
    if args.only_list:
        return run_list()
    if not have_gtk():
        # Senza desktop la simulazione resta utile; la cancellazione no.
        print(_("err_no_gtk"), file=sys.stderr)
        return run_simulation() if args.dry_run else 1
    return run_gui(dry_run=args.dry_run)


if __name__ == "__main__":
    sys.exit(main())
