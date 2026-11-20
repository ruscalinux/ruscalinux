# Naming the Rusca applications

RuscaLinux ships a small family of first-party applications. They are named to
look like a family rather than a pile of tools that appeared one at a time.

## The pattern

**`Rusca` + an English agent noun**, in CamelCase, no space:

    RuscaCleaner   cleans

The agent noun is what makes them a set. *RuscaCleaner* and *RuscaClean* would
read as two unrelated things: one is a thing, the other is an action. Keeping
the `-er` costs a syllable and buys coherence.

When no agent noun fits — a tool that is a place or a collection rather than
something that acts — use a plain English noun instead of forcing the suffix.
`RuscaVault` is better than `RuscaBackupper`. The rule is there to make naming
easy, not to be obeyed past the point where it produces something ugly.

Keep it English even though the project is Italian-first: these names appear in
`.desktop` files, package names and app IDs, all of which are English-shaped by
convention, and the applications themselves ship English as their fallback
language.

## The identifiers that follow from it

For an application named `RuscaFoo`, all of these must agree:

| Thing | Value |
|---|---|
| Directory | `apps/ruscafoo/` |
| Version | `VER` in `make-deb.sh` and `APP_VERSION` in the program, equal to `VERSION` in `release.conf` |
| Build script | `apps/ruscafoo/make-deb.sh` |
| Package file | `apps/ruscafoo/build-deb/ruscafoo-ruscalinux_<version>_all.deb` |
| Debian package | `ruscafoo` |
| Command | `/usr/bin/ruscafoo` |
| Data | `/usr/share/ruscafoo/` |
| Desktop file | `org.ruscalinux.RuscaFoo.desktop` |
| App ID | `org.ruscalinux.RuscaFoo` |
| Metainfo | `org.ruscalinux.RuscaFoo.metainfo.xml` |
| `StartupWMClass` | `org.ruscalinux.RuscaFoo` |
| Icon | `org.ruscalinux.RuscaFoo` (plus `org.ruscalinux.RuscaFoo-symbolic`) |

The desktop file, the metainfo and the icon are all named after the app ID:
that is the GNOME convention, and portals and notifications look the desktop
file up by the app ID.

Two of these pairings are not cosmetic. `StartupWMClass` must match the app ID
the application registers with GTK, or GNOME will not connect the running
window to its icon in the dash. The metainfo `<launchable>` must name the
`.desktop` file exactly, or the software catalogue will not link the two.

## Adding a utility

Create `apps/ruscafoo/` containing a `make-deb.sh` that runs from its own
directory with no arguments and writes exactly one `.deb` into `build-deb/`.

Nothing else. `make-debs.sh` walks `apps/*/` and builds whatever it finds;
`build.sh` then requires a package named after each directory and refuses to
build the ISO if one is missing. No script names any application, so adding
the fifth utility costs exactly as much as adding the second.
