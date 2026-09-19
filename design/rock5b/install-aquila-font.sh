#!/usr/bin/env bash
#
# install-aquila-font.sh -- apply the Aquila design system's font stack to
# this machine: system-wide fontconfig default for GUI apps, the actual
# KDE Plasma desktop font (kdeglobals) if this is a Plasma system, plus
# an optional larger/clearer console (TTY) font.
#
# Follows the same convention as the rock5b skill's own tune/remediate
# scripts: DRY RUN by default, nothing is changed until you pass --apply.
# Every file this script touches is backed up first; --rollback restores
# the most recent backup set.
#
# Usage:
#   ./install-aquila-font.sh                # dry run, prints what it would do
#   sudo ./install-aquila-font.sh --apply   # actually applies changes
#   sudo ./install-aquila-font.sh --apply --skip-console   # fontconfig only
#   sudo ./install-aquila-font.sh --rollback
#
# What it does NOT do: it will not invent or download a font called
# "Aquila" -- that's a brand typeface with its own license, not something
# on a public CDN. If you have the licensed font file(s), drop them in
# ./fonts/ (next to this script) before running -- any *.ttf/*.otf there
# is installed as the "Aquila" family. Without it, the system falls back
# to Atkinson Hyperlegible and Lexend, which is a legitimate, permanent
# choice, not just a placeholder -- both are open-licensed and independently
# validated for low-vision/dyslexic readability. It also will not fetch
# and parse third-party network content to decide what to write to disk
# while running as root: fallback fonts install only via apt; if your
# release doesn't package one, the script tells you where to get it and
# you drop the file in ./fonts/ yourself.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
APPLY=false
SKIP_CONSOLE=false
ROLLBACK=false
BACKUP_ROOT="/var/backups/aquila-font"
FONT_DIR="/usr/local/share/fonts/aquila"
FONTCONFIG_DEST="/etc/fonts/conf.d/60-aquila.conf"
AQUILA_FONT_SPEC="Aquila,10,-1,5,50,0,0,0,0,0"

# The desktop user, if this was invoked as `sudo ./install-aquila-font.sh`
# from a normal login session -- needed because KDE's font setting lives
# in that user's ~/.config/kdeglobals, not anywhere root-writable.
KDE_USER="${SUDO_USER:-}"
KDE_HOME=""
KDEGLOBALS=""
if [[ -n "$KDE_USER" ]]; then
  KDE_HOME="$(getent passwd "$KDE_USER" | cut -d: -f6)" || KDE_HOME=""
  [[ -n "$KDE_HOME" ]] && KDEGLOBALS="$KDE_HOME/.config/kdeglobals"
fi
KWRITECONFIG=""
if command -v kwriteconfig5 >/dev/null 2>&1; then
  KWRITECONFIG="kwriteconfig5"
elif command -v kwriteconfig6 >/dev/null 2>&1; then
  KWRITECONFIG="kwriteconfig6"
fi

for arg in "$@"; do
  case "$arg" in
    --apply) APPLY=true ;;
    --skip-console) SKIP_CONSOLE=true ;;
    --rollback) ROLLBACK=true ;;
    -h|--help)
      grep '^#' "$0" | sed 's/^#//'
      exit 0
      ;;
    *)
      echo "Unknown argument: $arg" >&2
      exit 1
      ;;
  esac
done

log() { echo "[aquila-font] $*"; }
run() {
  if $APPLY; then
    "$@"
  else
    echo "  (dry run) $*"
  fi
}

if $ROLLBACK; then
  latest="$(find "$BACKUP_ROOT" -maxdepth 1 -mindepth 1 -type d 2>/dev/null | sort | tail -n1 || true)"
  if [[ -z "$latest" ]]; then
    echo "No backup found under $BACKUP_ROOT" >&2
    exit 1
  fi
  log "Restoring from $latest"
  if [[ -f "$latest/60-aquila.conf" ]]; then
    run cp "$latest/60-aquila.conf" "$FONTCONFIG_DEST"
  elif [[ -f "$latest/60-aquila.conf.absent" ]]; then
    run rm -f "$FONTCONFIG_DEST"
  fi
  if [[ -f "$latest/console-setup" ]]; then
    run cp "$latest/console-setup" /etc/default/console-setup
  fi
  if [[ -f "$latest/kdeglobals" && -n "$KDEGLOBALS" ]]; then
    run cp "$latest/kdeglobals" "$KDEGLOBALS"
    run chown "$KDE_USER" "$KDEGLOBALS"
  fi
  run fc-cache -f
  log "Rollback complete. Reboot or re-login for console font to fully apply."
  exit 0
fi

if $APPLY && [[ "$(id -u)" -ne 0 ]]; then
  echo "Re-run with sudo to actually apply changes (this run needs to write to /etc and /usr/local/share/fonts)." >&2
  exit 1
fi

timestamp="$(date +%Y%m%d-%H%M%S)"
backup_dir="$BACKUP_ROOT/$timestamp"
if $APPLY; then
  mkdir -p "$backup_dir"
  if [[ -f "$FONTCONFIG_DEST" ]]; then
    cp "$FONTCONFIG_DEST" "$backup_dir/60-aquila.conf"
  else
    : > "$backup_dir/60-aquila.conf.absent"
  fi
  [[ -f /etc/default/console-setup ]] && cp /etc/default/console-setup "$backup_dir/console-setup"
  [[ -n "$KDEGLOBALS" && -f "$KDEGLOBALS" ]] && cp "$KDEGLOBALS" "$backup_dir/kdeglobals"
  log "Backed up existing config to $backup_dir"
fi

# --- 1. Install the brand font itself, if the licensed file was supplied ---
if compgen -G "$SCRIPT_DIR/fonts/*.ttf" > /dev/null || compgen -G "$SCRIPT_DIR/fonts/*.otf" > /dev/null; then
  log "Found local font file(s) in $SCRIPT_DIR/fonts -- installing as 'Aquila'"
  run mkdir -p "$FONT_DIR"
  run cp "$SCRIPT_DIR"/fonts/*.ttf "$SCRIPT_DIR"/fonts/*.otf "$FONT_DIR"/ 2>/dev/null || true
else
  log "No licensed Aquila font file found in $SCRIPT_DIR/fonts -- skipping brand font, using fallback stack only"
fi

# --- 2. Install fallback fonts (Atkinson Hyperlegible, Lexend) ---
# Deliberately apt-only: this script runs as root, and does not fetch or
# parse third-party network content to decide what to write to disk. If
# your release doesn't package a font, install it yourself (e.g. from
# https://fonts.google.com/specimen/Lexend) and drop the .ttf/.otf files
# in $SCRIPT_DIR/fonts/ alongside a licensed Aquila file, then re-run --
# they'll be picked up by step 1 above.
install_via_apt() {
  local apt_pkg="$1" manual_url="$2"
  if command -v apt-get >/dev/null 2>&1 && apt-cache show "$apt_pkg" >/dev/null 2>&1; then
    log "Installing $apt_pkg via apt"
    run apt-get install -y "$apt_pkg"
  else
    log "$apt_pkg not packaged on this release. Download it yourself from $manual_url and drop the .ttf files in $SCRIPT_DIR/fonts/, then re-run."
  fi
}

install_via_apt "fonts-atkinson-hyperlegible-ttf" "https://fonts.google.com/specimen/Atkinson+Hyperlegible"
install_via_apt "fonts-lexend" "https://fonts.google.com/specimen/Lexend"

# --- 3. System-wide fontconfig default for GUI apps ---
log "Installing fontconfig default -> $FONTCONFIG_DEST"
run mkdir -p "$(dirname "$FONTCONFIG_DEST")"
run cp "$SCRIPT_DIR/60-aquila.conf" "$FONTCONFIG_DEST"
run fc-cache -f

# --- 4. Console (TTY) font: no bitmap "Aquila" exists, so use the closest
#        legible-console equivalent -- Terminus, large size, minimizes
#        ambiguous glyphs (0/O, 1/l/I) which matters as much as spacing
#        does for dyslexic readers. Skippable if this box is headless-only
#        and nobody ever looks at the physical console. ---
if ! $SKIP_CONSOLE; then
  if command -v setupcon >/dev/null 2>&1 || [[ -f /etc/default/console-setup ]]; then
    log "Setting console font to Terminus 16x32 (large, unambiguous glyphs)"
    if $APPLY; then
      if command -v apt-get >/dev/null 2>&1; then
        apt-get install -y console-setup xfonts-terminus >/dev/null 2>&1 || true
      fi
      sed -i \
        -e 's/^FONTFACE=.*/FONTFACE="Terminus"/' \
        -e 's/^FONTSIZE=.*/FONTSIZE="16x32"/' \
        /etc/default/console-setup
      setupcon || true
    else
      echo "  (dry run) apt-get install console-setup xfonts-terminus; set FONTFACE=Terminus FONTSIZE=16x32 in /etc/default/console-setup; setupcon"
    fi
  else
    log "console-setup not present on this system -- skipping console font (likely headless/serial-only, which is fine)"
  fi
else
  log "Skipping console font (--skip-console)"
fi

# --- 5. KDE Plasma: fontconfig only affects font *matching*, but Plasma
#        writes a literal family name into kdeglobals and Qt apps request
#        exactly that name -- so the desktop won't actually switch unless
#        we set this too. ---
if [[ -n "$KDE_USER" && -n "$KWRITECONFIG" ]]; then
  log "Setting KDE Plasma fonts -> Aquila via $KWRITECONFIG (user: $KDE_USER)"
  for key in font menuFont toolBarFont; do
    run sudo -u "$KDE_USER" "$KWRITECONFIG" --file kdeglobals --group General --key "$key" "$AQUILA_FONT_SPEC"
  done
  run sudo -u "$KDE_USER" "$KWRITECONFIG" --file kdeglobals --group WM --key activeFont "$AQUILA_FONT_SPEC"
  log "Log out and back in (or run 'plasmashell --replace &' as $KDE_USER) for Plasma to pick this up."
elif [[ -n "$KWRITECONFIG" ]]; then
  log "$KWRITECONFIG found but no desktop user detected (\$SUDO_USER unset) -- invoke as 'sudo ./install-aquila-font.sh --apply' from your normal login session, not from a root shell, so \$SUDO_USER is set."
else
  log "No kwriteconfig5/6 found -- not a KDE Plasma system (or unknown Frameworks version), skipping desktop font step"
fi

log "Done. Verify with: fc-match sans-serif   (should resolve to Aquila or Atkinson Hyperlegible)"
if ! $APPLY; then
  log "This was a DRY RUN. Re-run with sudo and --apply to actually make these changes."
fi
