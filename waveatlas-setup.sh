#!/bin/bash
###############################################################################
# WaveAtlas HTPC — Comprehensive One-Shot Setup
#
# ONE SCRIPT. Everything from bare disk to fully configured HTPC.
#
#   scp waveatlas-setup.sh htpc@192.168.1.113:~/
#   ssh htpc@192.168.1.113 'sudo bash ~/waveatlas-setup.sh'
#
# Phase 1: Live USB → partition HDD/SSD, install OS, reboot
# Phase 2: HDD/SSD → configure everything, generate docs
#
# Hardware: Dell Inspiron, i3-8130U, Intel UHD 620, 931GB HDD/SSD,
#           HDMI to LG TV (surround + 4K)
###############################################################################
set -euo pipefail
umask 077

LOG="/tmp/waveatlas-setup.log"
exec > >(tee -a "$LOG") 2>&1

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'
CYAN='\033[0;36m'; BOLD='\033[1m'; NC='\033[0m'
info()  { echo -e "${CYAN}[INFO]${NC}  $*"; }
ok()    { echo -e "${GREEN}[ OK ]${NC}  $*"; }
warn()  { echo -e "${YELLOW}[WARN]${NC}  $*"; }
die()   { echo -e "${RED}[FATAL]${NC} $*"; exit 1; }
banner(){ echo -e "\n${BOLD}${CYAN}═══ $* ═══${NC}\n"; }

[ "$(id -u)" -eq 0 ] || die "Must run as root. Use: sudo $0"
export DEBIAN_FRONTEND=noninteractive

# ─── Detect internal disk ───────────────────────────────────────────────────
detect_disk() {
    if [ -b /dev/nvme0n1 ]; then
        DISK=/dev/nvme0n1; PPREFIX="${DISK}p"
    elif [ -b /dev/sda ]; then
        DISK=/dev/sda; PPREFIX="${DISK}"
    else
        die "No internal disk found (/dev/sda or /dev/nvme0n1)"
    fi
    PART_EFI="${PPREFIX}1"
    PART_ROOT="${PPREFIX}2"
    PART_SWAP="${PPREFIX}3"
    PART_MEDIA="${PPREFIX}4"

    if [ "$(cat /sys/block/"$(basename "$DISK")"/queue/rotational 2>/dev/null)" = "1" ]; then
        IS_HDD=true
    else
        IS_HDD=false
    fi
}

detect_phase() {
    local root_dev
    root_dev="$(findmnt -n -o SOURCE /)"
    if echo "$root_dev" | grep -qE '(overlay|tmpfs|aufs|squashfs|cow)'; then
        echo "phase1"
    elif [ -f /run/live/medium/casper/vmlinuz ] || [ -f /cdrom/casper/vmlinuz ]; then
        echo "phase1"
    else
        echo "phase2"
    fi
}

detect_disk
PHASE="$(detect_phase)"

###############################################################################
# PHASE 1 — Partition + Persist from Live USB
###############################################################################
phase1() {
    banner "PHASE 1: Partition & Install to $DISK"

    [ -b "$DISK" ] || die "$DISK not found"
    info "Disk: $DISK ($(lsblk -dno SIZE "$DISK" | tr -d ' '))"
    info "Type: $( $IS_HDD && echo 'HDD (rotational)' || echo 'SSD/NVMe' )"
    echo ""
    lsblk -o NAME,SIZE,FSTYPE,LABEL,MOUNTPOINT "$DISK"
    echo ""

    warn "This will REPARTITION $DISK (keeping EFI) and install WaveAtlas."
    warn "Layout: EFI(keep) + Root(60G) + Swap(4G) + Media(rest)"
    echo ""
    read -rp "Type YES to proceed: " confirm
    [ "$confirm" = "YES" ] || die "Aborted."

    # Unmount everything on the disk
    for mp in $(findmnt -rn -o TARGET -S "${PPREFIX}"* 2>/dev/null | sort -r); do
        umount "$mp" 2>/dev/null || true
    done
    swapoff "${PART_SWAP}" 2>/dev/null || true

    # Get EFI partition end in MiB
    local efi_end
    efi_end=$(parted -s "$DISK" unit MiB print | awk '/^ 1 /{gsub(/MiB/,"",$3); print $3}')
    [ -n "$efi_end" ] || die "Cannot detect EFI partition boundary"

    local root_end=$((efi_end + 61440))
    local swap_end=$((root_end + 4096))

    info "Repartitioning: EFI ends at ${efi_end}MiB, root=${efi_end}-${root_end}MiB, swap=${root_end}-${swap_end}MiB, media=${swap_end}MiB-100%"

    # Remove partitions 2+ (keep EFI)
    for pnum in $(parted -s "$DISK" print | awk '/^ [2-9]/{print $1}' | sort -rn); do
        parted -s "$DISK" rm "$pnum"
    done

    parted -s "$DISK" -- \
        mkpart WaveAtlas ext4 "${efi_end}MiB" "${root_end}MiB" \
        mkpart WaveSwap linux-swap "${root_end}MiB" "${swap_end}MiB" \
        mkpart WaveMedia ext4 "${swap_end}MiB" 100%

    partprobe "$DISK" 2>/dev/null || true
    sleep 2

    info "Formatting partitions..."
    mkfs.ext4 -F -L WaveAtlas "$PART_ROOT"
    mkswap -L WaveSwap "$PART_SWAP"
    mkfs.ext4 -F -L WaveMedia "$PART_MEDIA"
    ok "Partitions created and formatted"

    # Mount and rsync
    mount "$PART_ROOT" /mnt
    mkdir -p /mnt/srv/media
    mount "$PART_MEDIA" /mnt/srv/media

    info "Copying live filesystem to $PART_ROOT (10-20 min on HDD)..."
    rsync -aAXv --info=progress2 \
        --exclude='/proc/*' --exclude='/sys/*' --exclude='/dev/*' \
        --exclude='/run/*'  --exclude='/tmp/*' --exclude='/mnt/*' \
        --exclude='/media/*' --exclude='/cdrom/*' --exclude='/snap/*' \
        --exclude='/swapfile' --exclude='/lost+found' \
        --exclude='/cow/*' --exclude='/rofs/*' --exclude='/srv/media/*' \
        / /mnt/
    ok "Filesystem copied"

    # Chroot setup
    info "Setting up chroot..."
    mkdir -p /mnt/{proc,sys,dev,run,tmp,srv/media}
    mount --bind /dev /mnt/dev
    mount --bind /dev/pts /mnt/dev/pts
    mount -t proc proc /mnt/proc
    mount -t sysfs sys /mnt/sys
    mount --bind /sys/firmware/efi/efivars /mnt/sys/firmware/efi/efivars 2>/dev/null || true
    mount -t tmpfs tmpfs /mnt/run
    mkdir -p /mnt/boot/efi
    mount "$PART_EFI" /mnt/boot/efi

    # Generate fstab
    local uuid_root uuid_efi uuid_swap uuid_media
    uuid_root="$(blkid -s UUID -o value "$PART_ROOT")"
    uuid_efi="$(blkid -s UUID -o value "$PART_EFI")"
    uuid_swap="$(blkid -s UUID -o value "$PART_SWAP")"
    uuid_media="$(blkid -s UUID -o value "$PART_MEDIA")"

    cat > /mnt/etc/fstab <<FSTAB
# WaveAtlas HTPC — generated by waveatlas-setup.sh
UUID=$uuid_root   /           ext4  errors=remount-ro,noatime  0 1
UUID=$uuid_efi    /boot/efi   vfat  umask=0077                 0 1
UUID=$uuid_swap   none        swap  sw,pri=10                  0 0
UUID=$uuid_media  /srv/media  ext4  defaults,noatime           0 2
tmpfs             /tmp        tmpfs defaults,noatime,nosuid,nodev,size=1G 0 0
FSTAB
    ok "fstab written (root + EFI + swap + media + tmpfs)"

    cp /etc/resolv.conf /mnt/etc/resolv.conf 2>/dev/null || true

    chroot /mnt /bin/bash -e <<'CHROOT'
export DEBIAN_FRONTEND=noninteractive
apt-get update -qq
apt-get install -y grub-efi-amd64 grub-efi-amd64-signed shim-signed \
    linux-generic initramfs-tools os-prober 2>&1 | tail -10

if command -v efibootmgr &>/dev/null; then
    for bn in $(efibootmgr | grep -iE 'ubuntu|waveatlas|grub' | grep -oP 'Boot\K[0-9A-Fa-f]{4}'); do
        efibootmgr -b "$bn" -B 2>/dev/null || true
    done
fi

grub-install --target=x86_64-efi --efi-directory=/boot/efi \
    --bootloader-id=WaveAtlas --recheck
update-grub
update-initramfs -u -k all

apt-get remove -y --purge casper lupin-casper 2>/dev/null || true
apt-get autoremove -y 2>/dev/null || true

echo "waveatlas" > /etc/hostname
printf '127.0.0.1  localhost\n127.0.1.1  waveatlas\n' > /etc/hosts

id htpc &>/dev/null || useradd -m -s /bin/bash -G sudo,audio,video,input,render htpc
usermod -aG sudo,audio,video,input,render htpc 2>/dev/null || true

systemctl enable NetworkManager ssh 2>/dev/null || true

mkdir -p /srv/media/{videos,music,wallpapers,channels}
chown -R htpc:htpc /srv/media
CHROOT
    ok "GRUB + kernel + users configured"

    # Copy script for Phase 2
    cp "$(readlink -f "$0")" /mnt/home/htpc/waveatlas-setup.sh 2>/dev/null || \
        cp "$0" /mnt/home/htpc/waveatlas-setup.sh
    chmod 750 /mnt/home/htpc/waveatlas-setup.sh
    chroot /mnt chown htpc:htpc /home/htpc/waveatlas-setup.sh

    # Cleanup chroot
    for mp in /mnt/boot/efi /mnt/dev/pts /mnt/dev /mnt/proc \
              /mnt/sys/firmware/efi/efivars /mnt/sys /mnt/run /mnt/srv/media /mnt; do
        umount "$mp" 2>/dev/null || true
    done

    echo ""
    ok "PHASE 1 COMPLETE"
    info "Next: remove USB, reboot, select 'WaveAtlas' in UEFI (F12)"
    info "Then:  sudo ~/waveatlas-setup.sh"
}

###############################################################################
# PHASE 2 — Full Configuration (from HDD/SSD)
###############################################################################
phase2() {
    banner "PHASE 2: Full HTPC Configuration"

    HTPC_USER=""
    for u in htpc waveatlas; do
        id "$u" &>/dev/null && { HTPC_USER="$u"; break; }
    done
    [ -n "$HTPC_USER" ] || die "No htpc or waveatlas user found"
    HTPC_HOME="$(eval echo "~${HTPC_USER}")"
    info "User: $HTPC_USER  Home: $HTPC_HOME  Disk: $DISK ($( $IS_HDD && echo HDD || echo SSD ))"

    # ─────────────────────────────────────────────────────────────────────────
    # A. PACKAGES
    # ─────────────────────────────────────────────────────────────────────────
    banner "A. System Update + Dependencies"

    apt-get update -qq
    apt-get upgrade -y 2>&1 | tail -5

    apt-get install -y \
        curl wget git python3-pip python3-venv \
        fonts-noto fonts-roboto \
        sway foot wlr-randr waybar swayidle swaylock grim slurp \
        kodi kodi-inputstream-adaptive \
        pulseaudio pulseaudio-utils alsa-utils pavucontrol \
        intel-media-va-driver intel-media-va-driver-non-free vainfo \
        libva-drm2 libva-wayland2 i965-va-driver mesa-va-drivers \
        mpv \
        xdg-utils dbus-x11 \
        wireguard wireguard-tools qrencode \
        openssh-server \
        ufw fail2ban \
        unattended-upgrades apt-listchanges \
        zram-tools cpufrequtils preload earlyoom irqbalance \
        whiptail dialog \
        2>&1 | tail -20
    ok "All packages installed"

    # ─────────────────────────────────────────────────────────────────────────
    # B. SURROUND SOUND
    # ─────────────────────────────────────────────────────────────────────────
    banner "B. Surround Sound (HDMI 5.1/7.1)"

    local hdmi_card="0" hdmi_device="3"
    while IFS= read -r line; do
        if echo "$line" | grep -qi 'hdmi'; then
            hdmi_card="$(echo "$line" | grep -oP 'card \K[0-9]+')"
            hdmi_device="$(echo "$line" | grep -oP 'device \K[0-9]+')"
            break
        fi
    done < <(aplay -l 2>/dev/null)

    install -m 644 /dev/stdin /etc/asound.conf <<ALSA
pcm.!default {
    type plug
    slave.pcm "surround51"
}
pcm.surround51 {
    type hw
    card ${hdmi_card}
    device ${hdmi_device}
    channels 6
}
pcm.surround71 {
    type hw
    card ${hdmi_card}
    device ${hdmi_device}
    channels 8
}
pcm.iec958 {
    type iec958
    slave {
        pcm "hw:${hdmi_card},${hdmi_device}"
        format IEC958_SUBFRAME_LE
    }
    status [ AES0=0x02 AES1=0x82 AES2=0x00 AES3=0x02 ]
}
ctl.!default {
    type hw
    card ${hdmi_card}
}
ALSA

    install -d -m 755 /etc/pulse
    if [ ! -f /etc/pulse/daemon.conf ] || ! grep -q 'default-sample-channels = 6' /etc/pulse/daemon.conf 2>/dev/null; then
        install -m 644 /dev/stdin /etc/pulse/daemon.conf <<'PDAEMON'
default-sample-channels = 6
default-channel-map = front-left,front-right,rear-left,rear-right,front-center,lfe
enable-remixing = yes
enable-lfe-remixing = yes
default-sample-rate = 48000
alternate-sample-rate = 44100
PDAEMON
    fi

    if [ -f /etc/pulse/default.pa ] && ! grep -q 'waveatlas-surround' /etc/pulse/default.pa; then
        cat >> /etc/pulse/default.pa <<PULSE

### waveatlas-surround
load-module module-alsa-sink device=hw:${hdmi_card},${hdmi_device} sink_name=hdmi-surround channels=6 channel_map=front-left,front-right,rear-left,rear-right,front-center,lfe sink_properties="device.description='HDMI Surround 5.1'"
set-default-sink hdmi-surround
PULSE
    fi
    ok "Surround sound: 5.1 HDMI with IEC958 passthrough"

    # ─────────────────────────────────────────────────────────────────────────
    # C. 4K DISPLAY + VA-API
    # ─────────────────────────────────────────────────────────────────────────
    banner "C. 4K Display + Hardware Acceleration"

    install -m 644 /dev/stdin /etc/modprobe.d/i915-waveatlas.conf <<'I915'
options i915 enable_fbc=1 enable_guc=2 enable_psr=0 fastboot=1
I915

    install -d -m 755 /etc/X11/xorg.conf.d
    install -m 644 /dev/stdin /etc/X11/xorg.conf.d/20-intel-4k.conf <<'XORG'
Section "Device"
    Identifier  "Intel UHD 620"
    Driver      "modesetting"
    Option      "AccelMethod"  "glamor"
    Option      "TearFree"     "true"
    Option      "DRI"          "3"
EndSection
Section "Monitor"
    Identifier  "HDMI-1"
    Option      "PreferredMode" "3840x2160"
EndSection
XORG

    install -d -m 755 /etc/environment.d
    install -m 644 /dev/stdin /etc/environment.d/90-waveatlas-gpu.conf <<'GPUENV'
LIBVA_DRIVER_NAME=iHD
VDPAU_DRIVER=va_gl
GPUENV

    install -d -o "$HTPC_USER" -g "$HTPC_USER" -m 755 "$HTPC_HOME/.config/environment.d"
    install -o "$HTPC_USER" -g "$HTPC_USER" -m 644 \
        /etc/environment.d/90-waveatlas-gpu.conf "$HTPC_HOME/.config/environment.d/"

    ok "4K display + VA-API (iHD) configured"

    # ─────────────────────────────────────────────────────────────────────────
    # D. WAYDROID + microG + APKs
    # ─────────────────────────────────────────────────────────────────────────
    banner "D. Waydroid (Android Container)"

    if [ ! -f /etc/apt/sources.list.d/waydroid.list ]; then
        local gpg_tmp
        gpg_tmp="$(mktemp /tmp/waydroid-gpg.XXXXXX)"
        curl --fail -sS --max-time 30 --proto '=https' --tlsv1.2 \
            -o "$gpg_tmp" https://repo.waydro.id/waydroid.gpg
        gpg --dearmor -o /usr/share/keyrings/waydroid.gpg < "$gpg_tmp"
        rm -f "$gpg_tmp"
        local codename
        codename="$(lsb_release -cs 2>/dev/null || echo noble)"
        echo "deb [signed-by=/usr/share/keyrings/waydroid.gpg] https://repo.waydro.id/ $codename main" \
            > /etc/apt/sources.list.d/waydroid.list
        apt-get update -qq
    fi

    apt-get install -y waydroid 2>&1 | tail -5

    if [ ! -d /var/lib/waydroid/images ]; then
        info "Initializing Waydroid (LineageOS)..."
        waydroid init -s GAPPS -f 2>&1 | tail -5 || waydroid init -f 2>&1 | tail -5 || true
    fi

    # microG + Magisk + libndk via waydroid_script
    local ws_dir
    ws_dir="$(mktemp -d /tmp/waydroid_script.XXXXXX)"
    if git clone --depth 50 https://github.com/casualsnek/waydroid_script.git "$ws_dir" 2>&1 | tail -3; then
        cd "$ws_dir"
        python3 -m pip install -r requirements.txt 2>&1 | tail -3 || true

        waydroid session start &
        local wd_pid=$!
        sleep 8

        python3 main.py install microg 2>&1 | tail -5 || true
        python3 main.py install magisk 2>&1 | tail -5 || true
        python3 main.py install libndk 2>&1 | tail -5 || true

        cd /
        kill "$wd_pid" 2>/dev/null; wait "$wd_pid" 2>/dev/null || true
        waydroid session stop 2>/dev/null || true
        rm -rf "$ws_dir"
    fi

    # APKs
    local apk_dir
    apk_dir="$(mktemp -d /tmp/waveatlas-apks.XXXXXX)"
    _install_apk() {
        local name="$1" url="$2" dest="$3"
        if wget -q --timeout=30 --max-redirect=3 --https-only -O "$dest" "$url" && \
           file "$dest" | grep -qi 'zip\|jar\|android'; then
            waydroid session start 2>/dev/null &
            sleep 5
            waydroid app install "$dest" 2>&1 | tail -2
            waydroid session stop 2>/dev/null || true
        else
            warn "$name download failed — install from F-Droid later"
        fi
    }
    _install_apk "F-Droid" "https://f-droid.org/F-Droid.apk" "$apk_dir/FDroid.apk" || true
    _install_apk "Aurora Store" "https://f-droid.org/repo/com.aurora.store_57.apk" "$apk_dir/Aurora.apk" || true
    _install_apk "Shizuku" "https://f-droid.org/repo/moe.shizuku.privileged.api_700.apk" "$apk_dir/Shizuku.apk" || true
    rm -rf "$apk_dir"

    # Waydroid auto-start
    install -m 644 /dev/stdin /etc/systemd/system/waydroid-session.service <<'WDSVC'
[Unit]
Description=Waydroid Session
After=network.target

[Service]
Type=simple
User=htpc
ExecStart=/usr/bin/waydroid session start
ExecStop=/usr/bin/waydroid session stop
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
WDSVC
    systemctl daemon-reload
    systemctl enable waydroid-session.service waydroid-container.service 2>/dev/null || true
    ok "Waydroid + microG + APKs configured"

    # ─────────────────────────────────────────────────────────────────────────
    # E. KODI
    # ─────────────────────────────────────────────────────────────────────────
    banner "E. Kodi Configuration"

    local kodi_fonts="/usr/share/kodi/addons/skin.estuary/fonts"
    if [ -d "$kodi_fonts" ]; then
        for font in NotoSans-Regular NotoSans-Bold; do
            [ -f "/usr/share/fonts/truetype/noto/${font}.ttf" ] && \
                ln -sf "/usr/share/fonts/truetype/noto/${font}.ttf" "$kodi_fonts/" 2>/dev/null || true
        done
    fi

    install -d -o "$HTPC_USER" -g "$HTPC_USER" -m 755 "$HTPC_HOME/.kodi/userdata"
    if [ ! -f "$HTPC_HOME/.kodi/userdata/guisettings.xml" ]; then
        install -o "$HTPC_USER" -g "$HTPC_USER" -m 644 /dev/stdin \
            "$HTPC_HOME/.kodi/userdata/guisettings.xml" <<'KODIGUI'
<settings version="2">
    <setting id="videoscreen.resolution">63</setting>
    <setting id="videoscreen.screenmode">3840x2160</setting>
    <setting id="videoplayer.adjustrefreshrate">2</setting>
    <setting id="audiooutput.channels">2.1</setting>
    <setting id="audiooutput.passthrough">true</setting>
    <setting id="audiooutput.ac3passthrough">true</setting>
    <setting id="audiooutput.dtspassthrough">true</setting>
</settings>
KODIGUI
    fi

    # Add media sources
    if [ ! -f "$HTPC_HOME/.kodi/userdata/sources.xml" ]; then
        install -o "$HTPC_USER" -g "$HTPC_USER" -m 644 /dev/stdin \
            "$HTPC_HOME/.kodi/userdata/sources.xml" <<'KODISRC'
<sources>
    <video>
        <default pathversion="1"></default>
        <source>
            <name>Media</name>
            <path pathversion="1">/srv/media/videos/</path>
        </source>
        <source>
            <name>Channels</name>
            <path pathversion="1">/srv/media/channels/</path>
        </source>
    </video>
    <music>
        <default pathversion="1"></default>
        <source>
            <name>Music</name>
            <path pathversion="1">/srv/media/music/</path>
        </source>
    </music>
</sources>
KODISRC
    fi
    ok "Kodi: fonts fixed, media sources added"

    # ─────────────────────────────────────────────────────────────────────────
    # F. SWAY + FLEX LAUNCHER + SETTINGS + AUTO-LOGIN
    # ─────────────────────────────────────────────────────────────────────────
    banner "F. Desktop Environment"

    # Sway config
    local sway_dir="$HTPC_HOME/.config/sway"
    install -d -o "$HTPC_USER" -g "$HTPC_USER" -m 755 "$sway_dir"
    if [ ! -f "$sway_dir/config" ] || ! grep -q 'waveatlas' "$sway_dir/config" 2>/dev/null; then
        install -o "$HTPC_USER" -g "$HTPC_USER" -m 644 /dev/stdin "$sway_dir/config" <<'SWAYCONF'
# WaveAtlas sway config
set $mod Mod4

output HDMI-A-1 mode 3840x2160@30Hz
output HDMI-A-1 scale 1
output * bg #000000 solid_color

input * {
    xkb_layout us
}

# Flex Launcher on startup
exec flex-launcher

# Animated wallpaper (mpvpaper) via systemd user service
exec systemctl --user start mpvpaper.service 2>/dev/null

bar {
    mode invisible
}

# Useful keybinds
bindsym $mod+Return exec foot
bindsym $mod+q kill
bindsym $mod+Shift+e exec swaynag -t warning -m 'Exit sway?' -B 'Yes' 'swaymsg exit'
bindsym $mod+Shift+r reload

# No window decorations for HTPC
default_border none
default_floating_border none
gaps inner 0
gaps outer 0

# Idle inhibit (no screen blanking)
exec swayidle -w
SWAYCONF
    fi

    # Settings TUI script
    install -d -o "$HTPC_USER" -g "$HTPC_USER" -m 755 "$HTPC_HOME/.local/bin"
    install -o "$HTPC_USER" -g "$HTPC_USER" -m 755 /dev/stdin \
        "$HTPC_HOME/.local/bin/waveatlas-settings.sh" <<'SETTINGS'
#!/bin/bash
while true; do
    CHOICE=$(whiptail --title "WaveAtlas Settings" \
        --menu "Choose an option:" 20 60 10 \
        "1" "Audio Settings (pavucontrol)" \
        "2" "Display Info" \
        "3" "Network Settings" \
        "4" "Bluetooth" \
        "5" "VPN Status (WireGuard)" \
        "6" "System Update" \
        "7" "Storage Info" \
        "8" "Restart Services" \
        "9" "Shutdown / Reboot" \
        "0" "Back to Launcher" \
        3>&1 1>&2 2>&3) || break

    case $CHOICE in
        1) pavucontrol 2>/dev/null || alsamixer ;;
        2) wlr-randr 2>/dev/null; echo ""; vainfo 2>&1 | head -8; echo ""; read -rp "Press Enter..." ;;
        3) nmtui ;;
        4) bluetoothctl ;;
        5) sudo wg show 2>/dev/null || echo "WireGuard not active"; echo ""; read -rp "Press Enter..." ;;
        6) sudo apt-get update && sudo apt-get upgrade -y; echo ""; read -rp "Press Enter..." ;;
        7) df -h / /srv/media /tmp 2>/dev/null; echo ""; free -h; echo ""; read -rp "Press Enter..." ;;
        8) sudo systemctl restart pulseaudio waydroid-session 2>/dev/null; echo "Services restarted"; sleep 2 ;;
        9)
            SUB=$(whiptail --title "Power" --menu "" 12 40 3 \
                "1" "Reboot" "2" "Shutdown" "3" "Cancel" 3>&1 1>&2 2>&3) || continue
            case $SUB in
                1) sudo reboot ;;
                2) sudo poweroff ;;
            esac ;;
        0) break ;;
    esac
done
SETTINGS

    # Flex Launcher config
    local flex_dir="$HTPC_HOME/.config/flex-launcher"
    install -d -o "$HTPC_USER" -g "$HTPC_USER" -m 755 "$flex_dir"
    local flex_conf="$flex_dir/config.ini"
    if [ ! -f "$flex_conf" ]; then
        install -o "$HTPC_USER" -g "$HTPC_USER" -m 644 /dev/stdin "$flex_conf" <<'FLEXCONF'
[General]
Background=#1a1a2e
HighlightColor=#e94560
TextColor=#ffffff
FontSize=28

[Entry1]
Title=Kodi
Command=kodi --standalone
IconPath=kodi

[Entry2]
Title=Android TV
Command=waydroid show-full-ui
IconPath=waydroid

[Entry3]
Title=FieldStation42
Command=foot -e /home/htpc/.local/bin/fieldstation42.sh
IconPath=video-television

[Entry4]
Title=Settings
Command=foot -e /home/htpc/.local/bin/waveatlas-settings.sh
IconPath=preferences-system
FLEXCONF
    else
        if ! grep -q 'waveatlas-settings' "$flex_conf"; then
            cat >> "$flex_conf" <<'FLEXADD'

[Settings]
Title=Settings
Command=foot -e /home/htpc/.local/bin/waveatlas-settings.sh
IconPath=preferences-system
FLEXADD
        fi
        chown "$HTPC_USER:$HTPC_USER" "$flex_conf"
    fi

    # Auto-login getty → sway → Flex Launcher
    install -d -m 755 /etc/systemd/system/getty@tty1.service.d
    install -m 644 /dev/stdin /etc/systemd/system/getty@tty1.service.d/autologin.conf <<'AUTOLOGIN'
[Service]
ExecStart=
ExecStart=-/sbin/agetty --autologin htpc --noclear %I $TERM
AUTOLOGIN

    local profile="$HTPC_HOME/.profile"
    if ! grep -q 'waveatlas-autostart' "$profile" 2>/dev/null; then
        cat >> "$profile" <<'AUTOSTART'

# waveatlas-autostart
if [ -z "$WAYLAND_DISPLAY" ] && [ "$(tty)" = "/dev/tty1" ]; then
    export XDG_SESSION_TYPE=wayland
    export XDG_CURRENT_DESKTOP=sway
    export MOZ_ENABLE_WAYLAND=1
    export QT_QPA_PLATFORM=wayland
    export LIBVA_DRIVER_NAME=iHD
    exec sway
fi
AUTOSTART
        chown "$HTPC_USER:$HTPC_USER" "$profile"
    fi
    ok "Sway + Flex Launcher (with Settings) + auto-login configured"

    # ─────────────────────────────────────────────────────────────────────────
    # G. PERFORMANCE TUNING
    # ─────────────────────────────────────────────────────────────────────────
    banner "G. Performance Tuning"

    # I/O scheduler
    install -m 644 /dev/stdin /etc/udev/rules.d/60-waveatlas-iosched.rules <<'UDEV'
ACTION=="add|change", KERNEL=="sd[a-z]", ATTR{queue/rotational}=="1", ATTR{queue/scheduler}="mq-deadline"
ACTION=="add|change", KERNEL=="sd[a-z]", ATTR{queue/rotational}=="0", ATTR{queue/scheduler}="none"
ACTION=="add|change", KERNEL=="nvme[0-9]*", ATTR{queue/scheduler}="none"
UDEV

    if $IS_HDD; then
        echo mq-deadline > "/sys/block/$(basename "$DISK")/queue/scheduler" 2>/dev/null || true
        blockdev --setra 4096 "$DISK" 2>/dev/null || true
        install -m 644 /dev/stdin /etc/udev/rules.d/61-waveatlas-readahead.rules <<'RA'
ACTION=="add|change", KERNEL=="sda", ATTR{queue/read_ahead_kb}="2048"
RA
        ok "HDD tuning: mq-deadline, 2MB readahead"
    else
        ok "SSD detected: noop scheduler, no readahead override"
    fi

    # zram swap (on top of swap partition)
    install -m 644 /dev/stdin /etc/default/zramswap <<'ZRAM'
ALGO=zstd
PERCENT=50
PRIORITY=100
ZRAM
    systemctl enable zramswap 2>/dev/null || true
    systemctl restart zramswap 2>/dev/null || true
    ok "zram swap: zstd, 50% RAM, priority 100 (swap partition at pri=10)"

    # Kernel VM
    install -m 644 /dev/stdin /etc/sysctl.d/99-waveatlas-perf.conf <<'SYSCTL'
vm.swappiness = 10
vm.dirty_ratio = 10
vm.dirty_background_ratio = 5
vm.vfs_cache_pressure = 50
fs.inotify.max_user_watches = 524288
fs.inotify.max_user_instances = 1024
SYSCTL
    sysctl -p /etc/sysctl.d/99-waveatlas-perf.conf 2>/dev/null || true
    ok "VM tuning: swappiness=10, dirty_ratio=10, vfs_cache_pressure=50"

    # CPU governor
    install -m 644 /dev/stdin /etc/default/cpufrequtils <<'CPU'
GOVERNOR="schedutil"
CPU
    for gov in /sys/devices/system/cpu/cpu*/cpufreq/scaling_governor; do
        echo schedutil > "$gov" 2>/dev/null || true
    done
    [ -f /sys/devices/system/cpu/intel_pstate/no_turbo ] && \
        echo 0 > /sys/devices/system/cpu/intel_pstate/no_turbo 2>/dev/null || true
    ok "CPU: schedutil governor, turbo boost enabled"

    # GPU GRUB params
    if [ -f /etc/default/grub ]; then
        local grub_key='GRUB_CMDLINE_LINUX_DEFAULT'
        local current
        current=$(grep "^${grub_key}=" /etc/default/grub | head -1 | sed "s/^${grub_key}=\"//;s/\"$//")
        local updated=false
        for param in "i915.enable_fbc=1" "i915.enable_guc=2" "i915.fastboot=1"; do
            echo "$current" | grep -q "$param" || { current="$current $param"; updated=true; }
        done
        if [ "$updated" = true ]; then
            current="$(echo "$current" | sed 's/^[[:space:]]*//')"
            sed -i "s|^${grub_key}=.*|${grub_key}=\"${current}\"|" /etc/default/grub
            update-grub 2>/dev/null || true
        fi
    fi
    ok "Intel GPU: FBC, GuC, fastboot in GRUB"

    # Memoized workers: preload, earlyoom, irqbalance
    systemctl enable preload earlyoom irqbalance 2>/dev/null || true
    systemctl start preload earlyoom irqbalance 2>/dev/null || true

    # earlyoom config — protect interactive apps
    if [ -f /etc/default/earlyoom ]; then
        sed -i 's/^EARLYOOM_ARGS=.*/EARLYOOM_ARGS="-m 5 -s 5 -r 60 --prefer '\''^(kodi|mpv|flex-launcher|waydroid)$'\'' --avoid '\''^(sshd|systemd)$'\''"/' \
            /etc/default/earlyoom 2>/dev/null || true
        systemctl restart earlyoom 2>/dev/null || true
    fi
    ok "Memoized workers: preload (prefetch), earlyoom (OOM guard), irqbalance"

    # tmpfs /tmp
    if ! grep -q 'tmpfs.*/tmp' /etc/fstab; then
        echo "tmpfs /tmp tmpfs defaults,noatime,nosuid,nodev,size=1G 0 0" >> /etc/fstab
    fi

    # Journal limit
    install -d -m 755 /etc/systemd/journald.conf.d
    install -m 644 /dev/stdin /etc/systemd/journald.conf.d/waveatlas.conf <<'JOURNAL'
[Journal]
SystemMaxUse=200M
MaxRetentionSec=7day
JOURNAL
    systemctl restart systemd-journald 2>/dev/null || true
    ok "tmpfs /tmp + journal capped at 200MB"

    # ─────────────────────────────────────────────────────────────────────────
    # H. ANIMATED WALLPAPER
    # ─────────────────────────────────────────────────────────────────────────
    banner "H. Animated Wallpaper (mpvpaper)"

    if ! command -v mpvpaper &>/dev/null; then
        apt-get install -y -qq mpvpaper 2>/dev/null || {
            apt-get install -y -qq meson ninja-build libmpv-dev libwayland-dev \
                wayland-protocols pkg-config libwlroots-dev 2>/dev/null || true
            local build_dir
            build_dir="$(mktemp -d)"
            git clone --depth 1 https://github.com/GhostNaN/mpvpaper.git "$build_dir/mpvpaper"
            cd "$build_dir/mpvpaper" && meson setup build && ninja -C build && ninja -C build install
            cd /; rm -rf "$build_dir"
        }
    fi

    local wall_dir="$HTPC_HOME/.local/share/wallpapers"
    install -d -o "$HTPC_USER" -g "$HTPC_USER" -m 755 "$wall_dir"

    # Also link /srv/media/wallpapers
    ln -sf /srv/media/wallpapers "$wall_dir/library" 2>/dev/null || true

    install -d -o "$HTPC_USER" -g "$HTPC_USER" -m 755 "$HTPC_HOME/.config"
    install -o "$HTPC_USER" -g "$HTPC_USER" -m 644 /dev/stdin "$HTPC_HOME/.config/mpvpaper.conf" <<'MPVCFG'
loop
no-audio
no-osd
panscan=1.0
video-unscaled=downscale-big
hwdec=vaapi
MPVCFG

    local mpvpaper_bin
    mpvpaper_bin="$(command -v mpvpaper || echo /usr/local/bin/mpvpaper)"
    local sdu="$HTPC_HOME/.config/systemd/user"
    install -d -o "$HTPC_USER" -g "$HTPC_USER" -m 755 "$sdu"
    install -o "$HTPC_USER" -g "$HTPC_USER" -m 644 /dev/stdin "$sdu/mpvpaper.service" <<MPVSVC
[Unit]
Description=Animated wallpaper via mpvpaper
After=graphical-session.target
Requisite=graphical-session.target

[Service]
Type=simple
ExecStart=${mpvpaper_bin} -o "--config=${HTPC_HOME}/.config/mpvpaper.conf" '*' ${wall_dir}/wallpaper.apng
Restart=on-failure
RestartSec=5

[Install]
WantedBy=graphical-session.target
MPVSVC
    su - "$HTPC_USER" -c "systemctl --user daemon-reload; systemctl --user enable mpvpaper.service" 2>/dev/null || true
    ok "mpvpaper: drop wallpaper at $wall_dir/wallpaper.apng"

    # ─────────────────────────────────────────────────────────────────────────
    # I. WIREGUARD VPN
    # ─────────────────────────────────────────────────────────────────────────
    banner "I. WireGuard VPN"

    local wg_dir="/etc/wireguard"
    install -d -m 700 "$wg_dir"

    if [ ! -f "$wg_dir/server_private.key" ]; then
        wg genkey | tee "$wg_dir/server_private.key" | wg pubkey > "$wg_dir/server_public.key"
        chmod 600 "$wg_dir/server_private.key" "$wg_dir/server_public.key"
    fi
    if [ ! -f "$wg_dir/client_private.key" ]; then
        wg genkey | tee "$wg_dir/client_private.key" | wg pubkey > "$wg_dir/client_public.key"
        wg genpsk > "$wg_dir/preshared.key"
        chmod 600 "$wg_dir/client_private.key" "$wg_dir/client_public.key" "$wg_dir/preshared.key"
    fi

    local srv_priv srv_pub cli_priv cli_pub psk lan_ip
    srv_priv="$(cat "$wg_dir/server_private.key")"
    srv_pub="$(cat "$wg_dir/server_public.key")"
    cli_priv="$(cat "$wg_dir/client_private.key")"
    cli_pub="$(cat "$wg_dir/client_public.key")"
    psk="$(cat "$wg_dir/preshared.key")"

    # Detect LAN IP
    lan_ip="$(ip -4 route get 1.1.1.1 2>/dev/null | awk '/src/{print $7; exit}')"
    [ -n "$lan_ip" ] || lan_ip="192.168.1.113"

    # Server config
    install -m 600 /dev/stdin "$wg_dir/wg0.conf" <<WGSERVER
[Interface]
Address = 10.66.0.1/24
ListenPort = 51820
PrivateKey = ${srv_priv}
PostUp = iptables -A FORWARD -i wg0 -j ACCEPT; iptables -t nat -A POSTROUTING -o $(ip route show default | awk '{print $5; exit}') -j MASQUERADE
PostDown = iptables -D FORWARD -i wg0 -j ACCEPT; iptables -t nat -D POSTROUTING -o $(ip route show default | awk '{print $5; exit}') -j MASQUERADE

[Peer]
PublicKey = ${cli_pub}
PresharedKey = ${psk}
AllowedIPs = 10.66.0.2/32
WGSERVER

    # Client config
    local client_conf="$HTPC_HOME/wireguard-client.conf"
    install -o "$HTPC_USER" -g "$HTPC_USER" -m 600 /dev/stdin "$client_conf" <<WGCLIENT
[Interface]
PrivateKey = ${cli_priv}
Address = 10.66.0.2/32
DNS = 1.1.1.1, 9.9.9.9

[Peer]
PublicKey = ${srv_pub}
PresharedKey = ${psk}
AllowedIPs = 10.66.0.0/24
Endpoint = ${lan_ip}:51820
PersistentKeepalive = 25
WGCLIENT

    # Generate QR code
    local qr_png="$HTPC_HOME/wireguard-client-qr.png"
    qrencode -t PNG -o "$qr_png" < "$client_conf" 2>/dev/null || true
    chown "$HTPC_USER:$HTPC_USER" "$qr_png" 2>/dev/null || true

    # Enable IP forwarding for VPN routing
    install -m 644 /dev/stdin /etc/sysctl.d/99-waveatlas-wg.conf <<'WGSYS'
net.ipv4.ip_forward = 1
WGSYS
    sysctl -p /etc/sysctl.d/99-waveatlas-wg.conf 2>/dev/null || true

    systemctl enable wg-quick@wg0 2>/dev/null || true
    systemctl start wg-quick@wg0 2>/dev/null || true

    ok "WireGuard: server=10.66.0.1, client=10.66.0.2, port=51820"
    info "Client config: $client_conf"
    info "QR code: $qr_png"
    info "Terminal QR (scan with WireGuard mobile app):"
    qrencode -t ANSIUTF8 < "$client_conf" 2>/dev/null || true

    # ─────────────────────────────────────────────────────────────────────────
    # J. AUTO-HARDENING
    # ─────────────────────────────────────────────────────────────────────────
    banner "J. Auto-Hardening (Firewall + SSH + Updates)"

    # UFW firewall
    ufw --force reset 2>/dev/null || true
    ufw default deny incoming
    ufw default allow outgoing
    ufw allow 22/tcp comment 'SSH'
    ufw allow 51820/udp comment 'WireGuard'
    ufw allow 5353/udp comment 'Avahi/mDNS'
    ufw allow from 192.168.0.0/16 to any port 631 proto tcp comment 'CUPS LAN'
    ufw allow from 10.66.0.0/24 comment 'WireGuard subnet'
    ufw --force enable
    ok "UFW firewall: SSH, WireGuard, Avahi, CUPS(LAN) allowed"

    # fail2ban
    install -m 644 /dev/stdin /etc/fail2ban/jail.local <<'F2B'
[DEFAULT]
bantime = 1h
findtime = 10m
maxretry = 5

[sshd]
enabled = true
port = ssh
filter = sshd
logpath = /var/log/auth.log
F2B
    systemctl enable fail2ban 2>/dev/null || true
    systemctl restart fail2ban 2>/dev/null || true
    ok "fail2ban: SSH brute-force protection"

    # SSH hardening
    install -m 644 /dev/stdin /etc/ssh/sshd_config.d/waveatlas.conf <<'SSHD'
PermitRootLogin no
MaxAuthTries 4
X11Forwarding no
AllowAgentForwarding no
ClientAliveInterval 300
ClientAliveCountMax 2
SSHD
    systemctl restart ssh 2>/dev/null || true
    ok "SSH hardened: no root login, rate-limited"

    # Unattended upgrades (security only, no auto-reboot)
    install -m 644 /dev/stdin /etc/apt/apt.conf.d/50waveatlas-updates <<'UNATTENDED'
APT::Periodic::Update-Package-Lists "1";
APT::Periodic::Unattended-Upgrade "1";
APT::Periodic::AutocleanInterval "7";
Unattended-Upgrade::Automatic-Reboot "false";
UNATTENDED
    systemctl enable unattended-upgrades 2>/dev/null || true
    ok "Auto-updates: daily security patches, no auto-reboot"

    # ─────────────────────────────────────────────────────────────────────────
    # K. AUTO CONTENT (Internet Archive + FieldStation42)
    # ─────────────────────────────────────────────────────────────────────────
    banner "K. Auto Content (Internet Archive + FieldStation42)"

    # Install IA CLI
    su - "$HTPC_USER" -c "python3 -m pip install --user internetarchive" 2>&1 | tail -3 || true

    # Content directories
    install -d -o "$HTPC_USER" -g "$HTPC_USER" -m 755 \
        /srv/media/channels/prelinger \
        /srv/media/channels/classic_tv \
        /srv/media/channels/feature_films

    # Content config
    install -d -o "$HTPC_USER" -g "$HTPC_USER" -m 755 "$HTPC_HOME/.config/waveatlas"
    install -o "$HTPC_USER" -g "$HTPC_USER" -m 644 /dev/stdin \
        "$HTPC_HOME/.config/waveatlas/content.conf" <<'IACFG'
# WaveAtlas content sources — Internet Archive collections
# One collection per line. Lines starting with # are ignored.
# Format: collection_name|max_items_per_sync|media_type_filter
prelinger|20|movies
classic_tv_shows|10|movies
feature_films|5|movies
IACFG

    # Content download script
    install -o "$HTPC_USER" -g "$HTPC_USER" -m 755 /dev/stdin \
        "$HTPC_HOME/.local/bin/waveatlas-content.sh" <<'DLSCRIPT'
#!/bin/bash
# Auto-download content from Internet Archive
CONF="$HOME/.config/waveatlas/content.conf"
MEDIA_DIR="/srv/media/channels"
IA="$HOME/.local/bin/ia"
[ -x "$IA" ] || IA="$(command -v ia 2>/dev/null)" || exit 0

while IFS='|' read -r collection max_items media_type; do
    [[ "$collection" =~ ^#.*$ || -z "$collection" ]] && continue
    max_items="${max_items:-10}"
    media_type="${media_type:-movies}"
    dest="$MEDIA_DIR/$collection"
    mkdir -p "$dest"

    existing=$(find "$dest" -name '*.mp4' -o -name '*.mkv' -o -name '*.avi' 2>/dev/null | wc -l)
    [ "$existing" -ge "$max_items" ] && continue

    need=$((max_items - existing))
    "$IA" search "collection:${collection} mediatype:${media_type}" \
        --itemlist -n "$need" 2>/dev/null | head -"$need" | while read -r item; do
        [ -d "$dest/$item" ] && continue
        "$IA" download "$item" --destdir="$dest" --glob='*.mp4' --no-directories \
            --retries=3 -C 2>/dev/null || true
    done
done < "$CONF"
DLSCRIPT

    # Weekly content sync timer
    install -o "$HTPC_USER" -g "$HTPC_USER" -m 644 /dev/stdin "$sdu/waveatlas-content.service" <<'DLSVC'
[Unit]
Description=WaveAtlas content sync from Internet Archive

[Service]
Type=oneshot
ExecStart=%h/.local/bin/waveatlas-content.sh
Nice=19
IOSchedulingClass=idle
DLSVC

    install -o "$HTPC_USER" -g "$HTPC_USER" -m 644 /dev/stdin "$sdu/waveatlas-content.timer" <<'DLTMR'
[Unit]
Description=Weekly content sync

[Timer]
OnCalendar=weekly
RandomizedDelaySec=3600
Persistent=true

[Install]
WantedBy=timers.target
DLTMR
    su - "$HTPC_USER" -c "systemctl --user daemon-reload; systemctl --user enable waveatlas-content.timer" 2>/dev/null || true

    # FieldStation42
    if [ ! -d "$HTPC_HOME/FieldStation42" ]; then
        su - "$HTPC_USER" -c "git clone --depth 1 https://github.com/FieldStation42/FieldStation42.git ~/FieldStation42" 2>&1 | tail -3 || true
    fi
    if [ -d "$HTPC_HOME/FieldStation42" ]; then
        su - "$HTPC_USER" -c "cd ~/FieldStation42 && python3 -m venv env && source env/bin/activate && pip install -r requirements.txt" 2>&1 | tail -5 || true
    fi

    # FieldStation42 launcher wrapper
    install -o "$HTPC_USER" -g "$HTPC_USER" -m 755 /dev/stdin \
        "$HTPC_HOME/.local/bin/fieldstation42.sh" <<'FS42'
#!/bin/bash
cd "$HOME/FieldStation42" 2>/dev/null || { echo "FieldStation42 not installed"; sleep 3; exit 1; }
source env/bin/activate 2>/dev/null || true
python3 main.py --media-dir /srv/media/channels "$@"
FS42

    ok "IA content sync (weekly) + FieldStation42 configured"

    # ─────────────────────────────────────────────────────────────────────────
    # L. SYSTEM TWEAKS
    # ─────────────────────────────────────────────────────────────────────────
    banner "L. System Tweaks"

    # Lid close = ignore (HTPC)
    install -d -m 755 /etc/systemd/logind.conf.d
    install -m 644 /dev/stdin /etc/systemd/logind.conf.d/waveatlas.conf <<'LOGIND'
[Login]
HandleLidSwitch=ignore
HandleLidSwitchExternalPower=ignore
HandleLidSwitchDocked=ignore
IdleAction=ignore
LOGIND

    # Disable DPMS
    install -m 644 /dev/stdin /etc/systemd/system/disable-dpms.service <<'DPMS'
[Unit]
Description=Disable DPMS screen blanking
After=multi-user.target

[Service]
Type=oneshot
ExecStart=/bin/sh -c 'setterm --blank 0 --powerdown 0 2>/dev/null; echo 0 > /sys/module/kernel/parameters/consoleblank'
RemainAfterExit=yes

[Install]
WantedBy=multi-user.target
DPMS
    systemctl daemon-reload
    systemctl enable disable-dpms.service 2>/dev/null || true

    # Disable only ModemManager (keep bluetooth, cups, Wi-Fi, avahi, SSH)
    for svc in ModemManager.service; do
        systemctl disable "$svc" 2>/dev/null || true
        systemctl stop "$svc" 2>/dev/null || true
    done

    # Ensure needed services stay enabled
    systemctl enable ssh NetworkManager bluetooth cups avahi-daemon 2>/dev/null || true

    ok "Lid ignore, DPMS off, ModemManager disabled, essential services kept"

    # ─────────────────────────────────────────────────────────────────────────
    # M. GENERATE SETUP DOCUMENTATION
    # ─────────────────────────────────────────────────────────────────────────
    banner "M. Generating Setup Documentation"

    local doc="$HTPC_HOME/WAVEATLAS-SETUP.md"
    cat > "$doc" <<SETUPDOC
# WaveAtlas HTPC Setup Guide

Generated: $(date -u '+%Y-%m-%d %H:%M UTC')
Hostname: waveatlas
LAN IP: ${lan_ip}

---

## Quick Access

| Service       | Address                          |
|---------------|----------------------------------|
| SSH           | \`ssh ${HTPC_USER}@${lan_ip}\`   |
| WireGuard     | \`10.66.0.1:51820\`              |
| Kodi Web      | \`http://${lan_ip}:8080\`        |
| CUPS Printing | \`http://${lan_ip}:631\`         |

---

## WireGuard VPN Connection

### Mobile App (QR Code)

1. Install **WireGuard** from your app store
2. Tap **+** → **Create from QR code**
3. Scan the QR code at: \`${qr_png}\`
   - Or display it in terminal: \`sudo cat ${client_conf} | qrencode -t ANSIUTF8\`

### Desktop Client (Manual Config)

1. Install WireGuard on your device
2. Import this config file (or copy-paste):

\`\`\`ini
$(cat "$client_conf")
\`\`\`

### Remote Access (Outside Home Network)

To access WaveAtlas from outside your LAN:

1. Log into your router admin panel
2. Forward **UDP port 51820** to **${lan_ip}**
3. Find your public IP: \`curl -s ifconfig.me\`
4. Update the client config's \`Endpoint\` to: \`YOUR_PUBLIC_IP:51820\`

### WireGuard Commands

\`\`\`bash
sudo wg show               # Status
sudo wg-quick up wg0       # Start
sudo wg-quick down wg0     # Stop
sudo systemctl status wg-quick@wg0
\`\`\`

---

## Partition Layout

| Partition  | Mount        | Size   | Purpose               |
|------------|--------------|--------|-----------------------|
| ${PART_EFI}  | /boot/efi  | ~512MB | EFI boot              |
| ${PART_ROOT} | /          | 60GB   | Operating system      |
| ${PART_SWAP} | swap       | 4GB    | Swap (+ zram in RAM)  |
| ${PART_MEDIA}| /srv/media | ~867GB | Videos, music, content|

---

## Media Directories

\`\`\`
/srv/media/
├── videos/        ← Your video files
├── music/         ← Your music files
├── wallpapers/    ← Animated wallpapers (APNG/MP4/WEBM)
└── channels/      ← Auto-downloaded IA content
    ├── prelinger/
    ├── classic_tv_shows/
    └── feature_films/
\`\`\`

---

## Key Configuration

### Animated Wallpaper

\`\`\`bash
# Drop a wallpaper file:
scp cool.apng ${HTPC_USER}@${lan_ip}:~/.local/share/wallpapers/wallpaper.apng
# Restart wallpaper service:
systemctl --user restart mpvpaper.service
\`\`\`

Supported formats: APNG, GIF, MP4, WEBM (hardware-decoded via VA-API)

### Adding Content

\`\`\`bash
# Manual: copy files to media partition
scp movie.mp4 ${HTPC_USER}@${lan_ip}:/srv/media/videos/

# Auto: edit IA collections config
nano ~/.config/waveatlas/content.conf

# Force sync now
~/.local/bin/waveatlas-content.sh
\`\`\`

### Flex Launcher Tiles

Config: \`~/.config/flex-launcher/config.ini\`

| Tile           | Action                       |
|----------------|------------------------------|
| Kodi           | Media center                 |
| Android TV     | Waydroid (microG)            |
| FieldStation42 | Retro TV station simulator   |
| Settings       | Audio, display, network, VPN |

### Performance Tuning Active

- **I/O**: $( $IS_HDD && echo 'mq-deadline + 2MB readahead (HDD)' || echo 'noop scheduler (SSD)' )
- **Swap**: zram (zstd, 50% RAM, pri=100) + partition (4GB, pri=10)
- **CPU**: schedutil governor, turbo boost to 3.4GHz
- **GPU**: Intel UHD 620, VA-API (iHD), FBC, GuC
- **Memory**: preload (prefetch), earlyoom (OOM guard), irqbalance
- **tmpfs**: /tmp in RAM (1GB)
- **Journal**: capped at 200MB / 7 days

### Security

- **Firewall**: UFW (SSH, WireGuard, Avahi, CUPS-LAN only)
- **fail2ban**: SSH brute-force protection (5 attempts → 1h ban)
- **SSH**: No root login, max 4 auth tries
- **Updates**: Daily automatic security patches (no auto-reboot)

---

## Troubleshooting

### No display after boot
\`\`\`bash
# SSH in and check sway
ssh ${HTPC_USER}@${lan_ip}
journalctl --user -u sway -n 50
# Force restart
sudo systemctl restart getty@tty1
\`\`\`

### No sound
\`\`\`bash
speaker-test -c 6 -t wav     # Test surround
aplay -l                      # List audio devices
pavucontrol                   # Volume control
\`\`\`

### WireGuard not connecting
\`\`\`bash
sudo wg show                  # Check interface
sudo ufw status               # Check firewall
sudo journalctl -u wg-quick@wg0
\`\`\`

### Check display resolution
\`\`\`bash
wlr-randr                    # Current output info
vainfo                        # VA-API status
\`\`\`
SETUPDOC
    chown "$HTPC_USER:$HTPC_USER" "$doc"
    ok "Setup docs: $doc"

    # ─────────────────────────────────────────────────────────────────────────
    # DONE
    # ─────────────────────────────────────────────────────────────────────────
    echo ""
    echo -e "${BOLD}${GREEN}"
    echo "═══════════════════════════════════════════════════════════════"
    echo "  WAVEATLAS HTPC — FULLY CONFIGURED"
    echo "═══════════════════════════════════════════════════════════════"
    echo -e "${NC}"
    info "Reboot to apply all changes:  sudo reboot"
    echo ""
    info "What's configured:"
    info "  [disk]     Root(60G) + Swap(4G) + Media($(lsblk -dno SIZE "${PART_MEDIA}" 2>/dev/null || echo '~867G'))"
    info "  [audio]    Surround 5.1 over HDMI + IEC958 passthrough"
    info "  [display]  4K@30Hz, Intel UHD 620, VA-API hardware decode"
    info "  [apps]     Kodi, Waydroid+microG, FieldStation42"
    info "  [desktop]  Sway → Flex Launcher (Kodi/Android/FS42/Settings)"
    info "  [login]    Auto-login → sway → Flex Launcher on tty1"
    info "  [perf]     $( $IS_HDD && echo 'mq-deadline' || echo 'noop' ), zram, schedutil, preload, earlyoom"
    info "  [gpu]      i915 FBC+GuC+fastboot, VA-API iHD"
    info "  [wallpaper] mpvpaper (APNG/video, VA-API accelerated)"
    info "  [vpn]      WireGuard (10.66.0.0/24, port 51820)"
    info "  [security] UFW + fail2ban + SSH hardening + auto-updates"
    info "  [content]  Internet Archive weekly sync + FieldStation42"
    info "  [docs]     ~/WAVEATLAS-SETUP.md (WireGuard QR, connection info)"
    echo ""
    info "WireGuard client QR: ~/wireguard-client-qr.png"
    info "Setup guide: ~/WAVEATLAS-SETUP.md"
    info "Log: $LOG"
    echo ""
}

###############################################################################
# Main
###############################################################################
echo ""
info "WaveAtlas HTPC Setup — $(date)"
info "Phase: $PHASE | Disk: $DISK | $( $IS_HDD && echo HDD || echo SSD )"
echo ""

case "$PHASE" in
    phase1) phase1 ;;
    phase2) phase2 ;;
    *)      die "Could not detect phase" ;;
esac
