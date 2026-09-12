# Aquila font on the ROCK 5B

Confirmed setup: Radxa OS 26.01, KDE Plasma 5.27.5 (KDE Frameworks 5.103, Qt 5.15.8), Wayland, RK3588. This session has no network path to the physical board, so this can't be applied remotely — copy these files over and run the script on the device itself.

## What this changes

- **KDE Plasma desktop** (`kdeglobals`): sets the actual "General font", "Menu font", "Toolbar font", and window-title font Plasma tells Qt apps to use → `Aquila` (resolved via fontconfig, so it falls through to Atkinson Hyperlegible/Lexend if you haven't supplied the real Aquila font file). Fontconfig aliasing alone isn't enough here — Plasma writes a literal family name into `kdeglobals` and Qt requests exactly that name, so this step is what actually makes the desktop change, not just what's available to it.
- **GUI apps generally** (GTK apps, Electron, browsers, anything else that goes through fontconfig): system-wide `sans-serif` default → Aquila → Atkinson Hyperlegible → Lexend.
- **Console/TTY** (only matters if you plug in a monitor/keyboard directly or use the serial console — not your SSH terminal, which is a client-side setting on whichever machine you're SSHing *from*): switches to Terminus 16x32, chosen for large size and glyphs that don't get confused with each other (0/O, 1/l/I). Skip with `--skip-console` since this is a desktop system and you're likely never on the physical console.

## Steps

```bash
# from your workstation, copy the files over
scp -r design/rock5b/ user@rock5b-host:/tmp/aquila-font

# optional: if you have the actual licensed Aquila font file(s)
scp Aquila-Regular.ttf user@rock5b-host:/tmp/aquila-font/fonts/

# on the ROCK 5B itself:
ssh user@rock5b-host
cd /tmp/aquila-font

# see what it would do first -- this makes no changes
./install-aquila-font.sh

# apply it -- run via sudo from your normal login session (not a root
# shell) so $SUDO_USER is set and the KDE step knows whose kdeglobals to edit
sudo ./install-aquila-font.sh --apply --skip-console

# verify
fc-match sans-serif                                  # should print Aquila or AtkinsonHyperlegible
kreadconfig5 --file kdeglobals --group General --key font   # should print the Aquila,... spec

# log out and back in (or: plasmashell --replace &) for Plasma to pick it up

# undo if needed
sudo ./install-aquila-font.sh --rollback
```

## Notes

- The script never invents or hotlinks a font file claiming to be "Aquila" — that's a brand typeface with its own license. It only installs it if you provide the real file; otherwise it uses the Atkinson Hyperlegible / Lexend fallback permanently, not as a placeholder.
- Fallback fonts install via `apt` only (`fonts-atkinson-hyperlegible-ttf` is in Ubuntu 24.04+ universe). The script does not fetch or parse third-party network content while running as root; if your release doesn't package a font, it prints where to download it and you drop the `.ttf`/`.otf` file in `fonts/` yourself, same as for the Aquila file.
- Matches this repo's `rock5b` skill convention: dry-run by default, `--apply` to commit, every touched file backed up under `/var/backups/aquila-font/<timestamp>/`, `--rollback` restores the latest backup.
