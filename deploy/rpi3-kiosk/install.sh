#!/bin/bash
# =============================================================================
# UFS RPi3 Kiosk Installer
# VIBE 풀 대시보드를 TV에 표시하는 키오스크 모드 세팅
# 대상: Raspberry Pi 3 + Raspberry Pi OS Lite (Bookworm)
# =============================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CONFIG_FILE="${SCRIPT_DIR}/kiosk.env"
KIOSK_USER="${SUDO_USER:-pi}"
KIOSK_HOME="/home/${KIOSK_USER}"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

log()   { echo -e "${GREEN}[UFS-KIOSK]${NC} $1"; }
warn()  { echo -e "${YELLOW}[WARNING]${NC} $1"; }
error() { echo -e "${RED}[ERROR]${NC} $1" >&2; exit 1; }

# --- Pre-checks ---
[[ $EUID -ne 0 ]] && error "root 권한 필요: sudo bash install.sh"
[[ ! -f "$CONFIG_FILE" ]] && error "kiosk.env 파일이 없습니다: $CONFIG_FILE"

source "$CONFIG_FILE"
[[ -z "${KIOSK_URL:-}" ]] && error "KIOSK_URL이 설정되지 않았습니다"

log "=== UFS RPi3 Kiosk 설치 시작 ==="
log "URL: ${KIOSK_URL}"
log "User: ${KIOSK_USER}"

# --- 1. System packages ---
log "1/5 패키지 설치..."
apt-get update -qq
apt-get install -y -qq \
    xserver-xorg x11-xserver-utils xinit \
    chromium-browser \
    openbox \
    unclutter \
    lightdm \
    > /dev/null 2>&1

# --- 2. Auto-login ---
log "2/5 자동 로그인 설정..."
mkdir -p /etc/lightdm/lightdm.conf.d
cat > /etc/lightdm/lightdm.conf.d/50-autologin.conf << EOF
[Seat:*]
autologin-user=${KIOSK_USER}
autologin-session=openbox
user-session=openbox
EOF

# --- 3. Openbox autostart (kiosk mode) ---
log "3/5 키오스크 자동 시작 설정..."
OPENBOX_DIR="${KIOSK_HOME}/.config/openbox"
mkdir -p "${OPENBOX_DIR}"

cat > "${OPENBOX_DIR}/autostart" << 'AUTOSTART_EOF'
#!/bin/bash
# UFS Kiosk Autostart

# Load config
source /opt/ufs-kiosk/kiosk.env

# 화면 보호기 비활성화
xset s off
xset s noblank
xset -dpms

# 커서 숨김
if [ "${HIDE_CURSOR}" = "true" ]; then
    unclutter -idle 0.1 -root &
fi

# 이전 Chromium 크래시 팝업 방지
sed -i 's/"exited_cleanly":false/"exited_cleanly":true/' \
    "${HOME}/.config/chromium/Default/Preferences" 2>/dev/null || true
sed -i 's/"exit_type":"Crashed"/"exit_type":"Normal"/' \
    "${HOME}/.config/chromium/Default/Preferences" 2>/dev/null || true

# Chromium 키오스크 모드 (RPi3 메모리 최적화)
chromium-browser \
    --kiosk \
    --noerrdialogs \
    --disable-infobars \
    --disable-session-crashed-bubble \
    --disable-translate \
    --no-first-run \
    --start-fullscreen \
    --disable-features=TranslateUI \
    --disable-gpu \
    --disable-software-rasterizer \
    --disable-dev-shm-usage \
    --memory-pressure-off \
    --max-old-space-size=256 \
    --renderer-process-limit=1 \
    --disable-background-networking \
    --disable-extensions \
    --disable-component-update \
    --disable-default-apps \
    "${KIOSK_URL}" &
AUTOSTART_EOF

chmod +x "${OPENBOX_DIR}/autostart"
chown -R "${KIOSK_USER}:${KIOSK_USER}" "${KIOSK_HOME}/.config"

# --- 4. Install config to /opt ---
log "4/5 설정 파일 복사..."
mkdir -p /opt/ufs-kiosk
cp "${CONFIG_FILE}" /opt/ufs-kiosk/kiosk.env

# --- 5. Systemd watchdog (Chromium 크래시 시 자동 재시작) ---
log "5/5 Watchdog 서비스 등록..."
cat > /etc/systemd/system/ufs-kiosk-watchdog.service << EOF
[Unit]
Description=UFS Kiosk Watchdog - Chromium 프로세스 모니터링
After=graphical.target

[Service]
Type=simple
User=root
ExecStart=/opt/ufs-kiosk/watchdog.sh
Restart=always
RestartSec=10

[Install]
WantedBy=graphical.target
EOF

cat > /opt/ufs-kiosk/watchdog.sh << 'WATCHDOG_EOF'
#!/bin/bash
# Chromium이 죽으면 X 세션 재시작
while true; do
    sleep 30
    if ! pgrep -x chromium-browse > /dev/null 2>&1; then
        logger "UFS-Kiosk: Chromium not running, restarting display manager"
        systemctl restart lightdm
    fi
done
WATCHDOG_EOF
chmod +x /opt/ufs-kiosk/watchdog.sh

systemctl daemon-reload
systemctl enable ufs-kiosk-watchdog.service

# --- GPU memory split (RPi3: 최소 GPU 할당) ---
if [[ -f /boot/config.txt ]] || [[ -f /boot/firmware/config.txt ]]; then
    BOOT_CONFIG="/boot/config.txt"
    [[ -f /boot/firmware/config.txt ]] && BOOT_CONFIG="/boot/firmware/config.txt"

    if ! grep -q "gpu_mem=" "${BOOT_CONFIG}"; then
        log "GPU 메모리 64MB 할당 (브라우저 최소)"
        echo "gpu_mem=64" >> "${BOOT_CONFIG}"
    fi

    # 화면 꺼짐 방지
    if [ "${SCREEN_BLANK}" = "false" ]; then
        if ! grep -q "consoleblank=0" "${BOOT_CONFIG}"; then
            sed -i 's/$/ consoleblank=0/' "${BOOT_CONFIG}"
        fi
    fi
fi

log "=== 설치 완료 ==="
log ""
log "다음 단계:"
log "  1. kiosk.env에서 KIOSK_URL을 실제 서버 IP로 변경"
log "     nano /opt/ufs-kiosk/kiosk.env"
log "  2. 재부팅: sudo reboot"
log ""
log "관리 명령어:"
log "  URL 변경 후 적용:  sudo systemctl restart lightdm"
log "  키오스크 중지:     sudo systemctl stop lightdm"
log "  로그 확인:         journalctl -u ufs-kiosk-watchdog"
