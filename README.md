# RuscaLinux

A Debian-based desktop distribution — free, complete, and ready to go.
GNOME on Debian trixie, amd64, built with `live-build`.

Website: <https://www.ruscalinux.org/> · Downloads: [SourceForge](https://sourceforge.net/projects/ruscalinux/)

---

## Build it

```sh
sudo apt install live-build python3 openssl squashfs-tools qemu-system-x86 qemu-utils ovmf
./build.sh          # produces .work/ruscalinux-<version>-amd64.hybrid.iso
./test.sh           # boots it in QEMU
```

Needs a Debian trixie amd64 machine and about 25 GB of free space. Run it as
a normal user, not root.

The version is written in `release.conf` and nowhere else. Changing that one
line propagates it to the ISO name, the volume label, `/etc/os-release`,
`/etc/issue`, the installer title and the release notes.

## Layout

| Path | What it is |
|------|------------|
| `release.conf` | Settings. **The only place the version is written.** |
| `build.sh` | Builds the ISO. |
| `make-debs.sh` | Builds the bundled `.deb` packages. Called by `build.sh`. |
| `test.sh` | Boots the built ISO in QEMU. |
| `steps/` | The three scripts that determine what goes into the ISO. |
| `branding/` | Design sources: logos, icon theme, wallpapers, fonts, generators. |
| `tools/` | First-party applications, one directory each. |
| `tests/` | Tests shared by several applications, such as the common Markdown engine. |
| `local/` | Files `live-build` consumes directly: splash images, vendor logo. |
| `dist/` | Templates for the README and INSTALL published next to the ISO. |

## Documentation

**[`COME-FUNZIONA.md`](COME-FUNZIONA.md)** — the maintainer's manual, in
Italian: what each script does, how to cut a release, how to add an
application to `tools/`.

[`docs/NAMING.md`](docs/NAMING.md) — naming convention for the Rusca family of
applications, and the identifiers that must agree for each one.

## The mark

A paper plane flying between two plum-coloured vortices. The wider vortex is
the Debian world — universal, plural, deeply free. The inner one is the Red Hat
tradition — clean, professional, deliberate. Plum is the two of them meeting:
Debian blue and Red Hat red, fused. The plane is paper, the cheapest material
there is, and the first thing most of us ever engineered.

## Licensing

Build scripts and original design sources: **GPL-3.0**, see [`LICENSE`](LICENSE).

Third-party material keeps its own licence — Debian packages, the upstream
Adwaita icon theme, and the DM Sans and Syne fonts (SIL Open Font License).

The image also includes, as an option in the boot menu, the NVIDIA driver
from NVIDIA's repository: proprietary software under the NVIDIA licence, with
open-source kernel modules (MIT/GPL-2.0). The free drivers are the default.
See [`docs/NVIDIA.md`](docs/NVIDIA.md).

**Trademarks:** the name *RuscaLinux*, its logo and its emblem are **not**
covered by the GPL. See [`TRADEMARK.md`](TRADEMARK.md) and
[`docs/TRADEMARK-branding.md`](docs/TRADEMARK-branding.md).

---

Maintained by Nunzio Curcuruto.
