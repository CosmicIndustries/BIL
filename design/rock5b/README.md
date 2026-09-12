# Aquila font on the ROCK 5B

This session has no network path to the physical board, so this can't be applied remotely — copy these three files over and run the script on the device itself.

## What this changes

- **GUI apps** (GTK/Qt/Electron/browser, if this box runs a desktop or a kiosk display): system-wide `sans-serif` default via fontconfig → Aquila (if you supply it) → Atkinson Hyperlegible → Lexend.
- **Console/TTY** (if you ever look at the physical display or serial console directly): switches to Terminus 16x32 — the closest console-world equivalent, chosen for large size and glyphs that don't get confused with each other (0/O, 1/l/I), which is the console-font analogue of what Aquila does for GUI text.

If this board is headless-only (SSH/serial, no physical display ever used), the console-font part is a no-op you can skip with `--skip-console` — your terminal emulator's font is a client-side setting on whatever machine you SSH *from*, not something this script can reach.

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

# apply it
sudo ./install-aquila-font.sh --apply

# verify
fc-match sans-serif      # should print Aquila or AtkinsonHyperlegible
showconsolefont          # if console font was changed

# undo if needed
sudo ./install-aquila-font.sh --rollback
```

## Notes

- The script never invents or hotlinks a font file claiming to be "Aquila" — that's a brand typeface with its own license. It only installs it if you provide the real file; otherwise it uses the Atkinson Hyperlegible / Lexend fallback permanently, not as a placeholder.
- Fallback fonts are installed via `apt` where the release ships them (`fonts-atkinson-hyperlegible-ttf` is in Ubuntu 24.04+ universe); otherwise the script downloads the TTFs directly from Google Fonts' CSS API at run time.
- Matches this repo's `rock5b` skill convention: dry-run by default, `--apply` to commit, every touched file backed up under `/var/backups/aquila-font/<timestamp>/`, `--rollback` restores the latest backup.
