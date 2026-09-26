#!/usr/bin/env bash
set -euo pipefail

REPO_URL="https://github.com/CosmicIndustries/BIL.git"
BRANCH="claude/audio-output-config-8wupo4"
INSTALL_DIR="${BIL_DIR:-$HOME/BIL}"
OUTPUT_DIR="${ENTRAINMENT_OUT:-$HOME/entrainment_out}"

bold() { printf '\033[1m%s\033[0m\n' "$*"; }
ok()   { printf '\033[32m✓ %s\033[0m\n' "$*"; }
fail() { printf '\033[31m✗ %s\033[0m\n' "$*"; exit 1; }

bold "=== HTPC Vibroacoustic Entrainment Setup ==="
echo

# ── 1. Check prerequisites ──────────────────────────────────────────
bold "[1/6] Checking prerequisites..."

command -v python3 >/dev/null || fail "python3 not found"
command -v git     >/dev/null || fail "git not found"
command -v pactl   >/dev/null || fail "pactl not found (need pulseaudio-utils or pipewire-pulse)"

python3 -c "import wave, struct, array" 2>/dev/null || fail "python3 stdlib incomplete"
ok "python3, git, pactl all present"

# ── 2. Clone or update repo ─────────────────────────────────────────
bold "[2/6] Setting up repository..."

if [ -d "$INSTALL_DIR/.git" ]; then
    cd "$INSTALL_DIR"
    git fetch origin "$BRANCH"
    git checkout "$BRANCH"
    git pull origin "$BRANCH"
    ok "Updated existing clone at $INSTALL_DIR"
else
    git clone "$REPO_URL" "$INSTALL_DIR"
    cd "$INSTALL_DIR"
    git checkout "$BRANCH"
    ok "Cloned to $INSTALL_DIR"
fi

# ── 3. Detect system audio ──────────────────────────────────────────
bold "[3/6] Detecting system audio output..."

python3 -m vibroacoustic_entrainment.cli --show-audio-info
echo

# ── 4. Run tests ────────────────────────────────────────────────────
bold "[4/6] Running test suite..."

python3 -m unittest tests.test_vibroacoustic_entrainment -v 2>&1 | tail -5
echo

# ── 5. Render a test session matched to system audio ────────────────
bold "[5/6] Rendering test session to $OUTPUT_DIR..."

mkdir -p "$OUTPUT_DIR"
python3 -m vibroacoustic_entrainment.cli \
    --match-system \
    --protocol focus10 \
    --out-dir "$OUTPUT_DIR"
echo

# ── 6. Verify output ────────────────────────────────────────────────
bold "[6/6] Verifying output WAV..."

python3 - "$OUTPUT_DIR" <<'PYEOF'
import wave, json, os, sys
d = sys.argv[1]
with wave.open(os.path.join(d, 'audio.wav')) as w:
    rate = w.getframerate()
    depth = w.getsampwidth() * 8
    ch = w.getnchannels()
    dur = w.getnframes() / rate
    print(f'  Rate:     {rate} Hz')
    print(f'  Depth:    {depth}-bit')
    print(f'  Channels: {ch}')
    print(f'  Duration: {dur:.0f}s')

with open(os.path.join(d, 'manifest.json')) as f:
    m = json.load(f)
    print(f'  Protocol: {m["protocol"]}')
    if m.get('safety_warnings'):
        for w in m['safety_warnings']:
            print(f'  WARNING:  {w}')
PYEOF

echo
ok "Setup complete. Files are in $OUTPUT_DIR"
echo
bold "To play:"
echo "  paplay $OUTPUT_DIR/audio.wav"
echo "  # or: aplay $OUTPUT_DIR/audio.wav"
echo
bold "To render other protocols:"
echo "  cd $INSTALL_DIR"
echo "  python3 -m vibroacoustic_entrainment.cli --match-system --protocol obe_phase --out-dir $OUTPUT_DIR"
echo
echo "Available protocols: focus10, focus12, focus15, gateway, obe_phase,"
echo "  focus21_bridge, lucia_hypnagogic, vibroacoustic_relaxation"
