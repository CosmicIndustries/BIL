#!/bin/bash
###############################################################################
# WaveAtlas HTPC — Performance Tuning + Animated Wallpaper
#
# Run on the Dell after Phase 2 is done:
#   scp waveatlas-tune.sh htpc@192.168.1.113:~/
#   ssh htpc@192.168.1.113 'sudo bash ~/waveatlas-tune.sh'
#
# Hardware: Dell Inspiron, i3-8130U, Intel UHD 620, 931GB HDD (ST1000LM035)
###############################################################################
set -euo pipefail

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; CYAN='\033[0;36m'; NC='\033[0m'
info()  { echo -e "${CYAN}[INFO]${NC}  $*"; }
ok()    { echo -e "${GREEN}[OK]${NC}    $*"; }
warn()  { echo -e "${YELLOW}[WARN]${NC}  $*"; }
die()   { echo -e "${RED}[FATAL]${NC} $*"; exit 1; }

[ "$(id -u)" -eq 0 ] || die "Must run as root. Use: sudo $0"

export DEBIAN_FRONTEND=noninteractive

HTPC_USER=""
for u in htpc waveatlas; do
    if id "$u" &>/dev/null; then
        HTPC_USER="$u"
        break
    fi
done
[ -n "$HTPC_USER" ] || die "Could not find htpc or waveatlas user"
HTPC_HOME="$(eval echo "~${HTPC_USER}")"

info "WaveAtlas Performance Tuning — $(date)"
info "User: $HTPC_USER  Home: $HTPC_HOME"
echo ""

###############################################################################
# 1. HDD I/O Tuning
###############################################################################
info "── HDD I/O Tuning ──"

# mq-deadline is best for rotational drives — low latency, fair queuing
cat > /etc/udev/rules.d/60-waveatlas-iosched.rules <<'UDEV'
# WaveAtlas: mq-deadline for rotational HDD, none for SSD/NVMe
ACTION=="add|change", KERNEL=="sd[a-z]", ATTR{queue/rotational}=="1", ATTR{queue/scheduler}="mq-deadline"
ACTION=="add|change", KERNEL=="sd[a-z]", ATTR{queue/rotational}=="0", ATTR{queue/scheduler}="none"
ACTION=="add|change", KERNEL=="nvme[0-9]*", ATTR{queue/scheduler}="none"
UDEV

# Apply now for sda
if [ -f /sys/block/sda/queue/scheduler ]; then
    echo mq-deadline > /sys/block/sda/queue/scheduler 2>/dev/null || true
fi

# Increase readahead to 2MB for HDD — helps with sequential media reads
if [ -b /dev/sda ]; then
    blockdev --setra 4096 /dev/sda 2>/dev/null || true
    cat > /etc/udev/rules.d/61-waveatlas-readahead.rules <<'RA'
ACTION=="add|change", KERNEL=="sda", ATTR{queue/read_ahead_kb}="2048"
RA
fi

ok "HDD I/O scheduler: mq-deadline, readahead: 2MB"

###############################################################################
# 2. zram Swap (avoid HDD thrashing)
###############################################################################
info "── zram Compressed Swap ──"

apt-get install -y -qq zram-tools 2>/dev/null || true

cat > /etc/default/zramswap <<'ZRAM'
# WaveAtlas: zram compressed swap — keeps swap in RAM, avoids HDD
ALGO=zstd
PERCENT=50
PRIORITY=100
ZRAM

# Reduce HDD swap priority if it exists
if grep -q '/swap' /etc/fstab 2>/dev/null; then
    sed -i 's/\(swap.*sw\)/\1,pri=10/' /etc/fstab 2>/dev/null || true
fi

systemctl enable zramswap 2>/dev/null || true
systemctl restart zramswap 2>/dev/null || true

ok "zram swap enabled (zstd, 50% of RAM, priority 100)"

###############################################################################
# 3. Kernel VM Tuning
###############################################################################
info "── Kernel VM Tuning ──"

cat > /etc/sysctl.d/99-waveatlas-perf.conf <<'SYSCTL'
# WaveAtlas — HTPC performance tuning for HDD + 8GB RAM

# Prefer RAM over swap — HDD swap is glacial
vm.swappiness = 10

# Write back dirty pages sooner — avoids I/O storms on HDD
vm.dirty_ratio = 10
vm.dirty_background_ratio = 5

# Larger VFS cache pressure — keep dentries/inodes cached (media library)
vm.vfs_cache_pressure = 50

# Inotify for Kodi media scanning
fs.inotify.max_user_watches = 524288
fs.inotify.max_user_instances = 1024
SYSCTL

sysctl -p /etc/sysctl.d/99-waveatlas-perf.conf 2>/dev/null || true

ok "VM tuning applied (swappiness=10, dirty_ratio=10, vfs_cache_pressure=50)"

###############################################################################
# 4. CPU Governor
###############################################################################
info "── CPU Governor ──"

apt-get install -y -qq cpufrequtils 2>/dev/null || true

# schedutil is the best for interactive use — scales with load, saves power at idle
cat > /etc/default/cpufrequtils <<'CPU'
GOVERNOR="schedutil"
CPU

# Apply now
for gov in /sys/devices/system/cpu/cpu*/cpufreq/scaling_governor; do
    echo schedutil > "$gov" 2>/dev/null || true
done

# Enable turbo boost (i3-8130U boosts to 3.4GHz)
if [ -f /sys/devices/system/cpu/intel_pstate/no_turbo ]; then
    echo 0 > /sys/devices/system/cpu/intel_pstate/no_turbo 2>/dev/null || true
fi

ok "CPU governor: schedutil (turbo boost enabled)"

###############################################################################
# 5. Intel GPU Performance
###############################################################################
info "── Intel GPU Tuning ──"

# i915 kernel params — enable GuC/HuC for UHD 620, framebuffer compression
if [ -f /etc/default/grub ]; then
    GRUB_LINE='GRUB_CMDLINE_LINUX_DEFAULT'
    CURRENT=$(grep "^${GRUB_LINE}=" /etc/default/grub | head -1 | sed "s/^${GRUB_LINE}=\"//;s/\"$//")

    needs_update=false
    for param in "i915.enable_fbc=1" "i915.enable_guc=2" "i915.fastboot=1"; do
        if ! echo "$CURRENT" | grep -q "$param"; then
            CURRENT="$CURRENT $param"
            needs_update=true
        fi
    done

    if [ "$needs_update" = true ]; then
        CURRENT="$(echo "$CURRENT" | sed 's/^[[:space:]]*//')"
        sed -i "s|^${GRUB_LINE}=.*|${GRUB_LINE}=\"${CURRENT}\"|" /etc/default/grub
        update-grub 2>/dev/null || true
        ok "GRUB updated with i915 params (reboot to apply)"
    else
        ok "i915 kernel params already set"
    fi
fi

# VA-API environment for sway
cat > /etc/environment.d/90-waveatlas-gpu.conf <<'GPUENV' 2>/dev/null || \
    { mkdir -p /etc/environment.d && cat > /etc/environment.d/90-waveatlas-gpu.conf <<'GPUENV'; }
LIBVA_DRIVER_NAME=iHD
VDPAU_DRIVER=va_gl
GPUENV

ok "Intel GPU: FBC, GuC, fastboot, VA-API (iHD)"

###############################################################################
# 6. Preload (predictive app loading for HDD)
###############################################################################
info "── Preload Daemon ──"

apt-get install -y -qq preload 2>/dev/null || true
systemctl enable preload 2>/dev/null || true
systemctl start preload 2>/dev/null || true

ok "preload enabled — learns your usage patterns, prefetches from HDD"

###############################################################################
# 7. tmpfs for /tmp (keep temp I/O off the HDD)
###############################################################################
info "── tmpfs for /tmp ──"

if ! grep -q 'tmpfs.*/tmp' /etc/fstab; then
    echo "tmpfs /tmp tmpfs defaults,noatime,nosuid,nodev,size=1G 0 0" >> /etc/fstab
    ok "tmpfs for /tmp added to fstab (1GB, applied on reboot)"
else
    ok "tmpfs for /tmp already configured"
fi

###############################################################################
# 8. Disable Unnecessary Services
###############################################################################
info "── Disabling Unnecessary Services ──"

for svc in \
    bluetooth.service \
    ModemManager.service \
    cups.service \
    cups-browsed.service \
    avahi-daemon.service \
    wpa_supplicant.service; do
    if systemctl is-enabled "$svc" &>/dev/null; then
        systemctl disable "$svc" 2>/dev/null || true
        systemctl stop "$svc" 2>/dev/null || true
        info "  Disabled $svc"
    fi
done

ok "Unnecessary services disabled"
warn "If you need Wi-Fi, re-enable wpa_supplicant: sudo systemctl enable --now wpa_supplicant"

###############################################################################
# 9. Animated Wallpaper (APNG/Video via mpvpaper)
###############################################################################
info "── Animated Wallpaper (mpvpaper) ──"

# mpvpaper uses mpv to render video/animated images as sway wallpaper
apt-get install -y -qq mpv 2>/dev/null || true

# Build mpvpaper from source
if ! command -v mpvpaper &>/dev/null; then
    info "Building mpvpaper from source..."
    apt-get install -y -qq \
        meson ninja-build \
        libmpv-dev libwayland-dev wayland-protocols \
        pkg-config libwlroots-dev 2>/dev/null || true

    BUILD_DIR="$(mktemp -d)"
    git clone --depth 1 https://github.com/GhostNaN/mpvpaper.git "$BUILD_DIR/mpvpaper"
    cd "$BUILD_DIR/mpvpaper"
    meson setup build
    ninja -C build
    ninja -C build install
    cd /
    rm -rf "$BUILD_DIR"
    ok "mpvpaper installed"
else
    ok "mpvpaper already installed"
fi

# Create wallpaper directory
WALLPAPER_DIR="$HTPC_HOME/.local/share/wallpapers"
mkdir -p "$WALLPAPER_DIR"

# Drop a sample config — user places their .apng/.mp4/.webm in the wallpaper dir
cat > "$HTPC_HOME/.config/mpvpaper.conf" <<'MPVCFG'
# mpvpaper config — animated wallpaper for sway
# Loops the wallpaper, no audio, no OSD
loop
no-audio
no-osd
panscan=1.0
video-unscaled=downscale-big
hwdec=vaapi
MPVCFG

# Create a systemd user service for mpvpaper
SYSTEMD_USER="$HTPC_HOME/.config/systemd/user"
mkdir -p "$SYSTEMD_USER"

cat > "$SYSTEMD_USER/mpvpaper.service" <<MPVSVC
[Unit]
Description=Animated wallpaper via mpvpaper
After=graphical-session.target
Requisite=graphical-session.target

[Service]
Type=simple
# Set your wallpaper file here — APNG, GIF, MP4, WEBM all work
# Change HDMI-A-1 to your output name (check with: wlr-randr)
ExecStart=/usr/local/bin/mpvpaper -o "--config=$HTPC_HOME/.config/mpvpaper.conf" '*' $HTPC_HOME/.local/share/wallpapers/wallpaper.apng
Restart=on-failure
RestartSec=5

[Install]
WantedBy=graphical-session.target
MPVSVC

chown -R "${HTPC_USER}:${HTPC_USER}" "$WALLPAPER_DIR" "$HTPC_HOME/.config/mpvpaper.conf" "$SYSTEMD_USER/mpvpaper.service"

# Enable the service for the user
su - "$HTPC_USER" -c "systemctl --user daemon-reload" 2>/dev/null || true
su - "$HTPC_USER" -c "systemctl --user enable mpvpaper.service" 2>/dev/null || true

ok "mpvpaper configured as systemd user service"
info "  Wallpaper dir: $WALLPAPER_DIR"
info "  Drop your .apng/.mp4/.webm as: $WALLPAPER_DIR/wallpaper.apng"
info "  Or edit: $SYSTEMD_USER/mpvpaper.service (ExecStart line)"
info "  Supports: APNG, GIF, MP4, WEBM, any format mpv plays"
info "  Uses VA-API hardware decoding for efficiency"

###############################################################################
# 10. Journal Size Limit (HDD space conservation)
###############################################################################
info "── Journal Size Limit ──"

mkdir -p /etc/systemd/journald.conf.d
cat > /etc/systemd/journald.conf.d/waveatlas.conf <<'JOURNAL'
[Journal]
SystemMaxUse=200M
MaxRetentionSec=7day
JOURNAL

systemctl restart systemd-journald 2>/dev/null || true
ok "Journal limited to 200MB / 7 days"

###############################################################################
# Done
###############################################################################
echo ""
ok "══════════════════════════════════════════════════════════"
ok "  Performance tuning complete!"
ok "══════════════════════════════════════════════════════════"
echo ""
info "What's configured:"
info "  ✓ HDD I/O: mq-deadline scheduler, 2MB readahead"
info "  ✓ zram swap (compressed, in-RAM — avoids HDD thrashing)"
info "  ✓ VM tuning (swappiness=10, dirty writeback optimized)"
info "  ✓ CPU: schedutil governor, turbo boost on"
info "  ✓ Intel GPU: FBC, GuC, fastboot, VA-API"
info "  ✓ preload (predictive app prefetching)"
info "  ✓ tmpfs /tmp (temp I/O stays in RAM)"
info "  ✓ Unnecessary services disabled"
info "  ✓ mpvpaper animated wallpaper (APNG/video)"
info "  ✓ Journal capped at 200MB"
echo ""
info "Next steps:"
info "  1. Reboot to apply GRUB + tmpfs changes: sudo reboot"
info "  2. Drop wallpaper: scp cool.apng htpc@<IP>:~/.local/share/wallpapers/wallpaper.apng"
info "  3. After reboot, wallpaper service auto-starts with sway"
echo ""
info "To test animated wallpaper manually:"
info "  mpvpaper -o '--loop --no-audio --hwdec=vaapi --panscan=1.0' '*' ~/path/to/wallpaper.apng"
echo ""
warn "If you need Wi-Fi: sudo systemctl enable --now wpa_supplicant"
warn "If you need Bluetooth: sudo systemctl enable --now bluetooth"
