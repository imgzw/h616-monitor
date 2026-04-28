#!/bin/bash
set -euo pipefail

GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m'

INSTALL_DIR="/opt/h616-monitor"
RECORDINGS_DIR="/opt/h616-monitor/recordings"
CURRENT_DIR="$(cd "$(dirname "$0")/.." && pwd)"

info()  { echo -e "${GREEN}[INFO]${NC} $*"; }
warn()  { echo -e "${YELLOW}[WARN]${NC} $*"; }
error() { echo -e "${RED}[ERROR]${NC} $*"; exit 1; }

check_root() {
    [ "$(id -u)" -eq 0 ] || error "This script must be run as root (sudo)"
}

install_system_deps() {
    info "Installing system dependencies..."
    apt-get update -qq
    apt-get install -y -qq \
        python3 python3-pip python3-venv \
        ffmpeg v4l-utils \
        nginx \
        curl wget rsync
    info "System dependencies installed."
}

install_nodejs() {
    if command -v node &>/dev/null && command -v npm &>/dev/null; then
        info "Node.js $(node -v) already installed, skipping."
        return 0
    fi

    info "Installing Node.js (LTS) for frontend build..."
    ARCH=$(dpkg --print-architecture)
    case "$ARCH" in
        arm64|aarch64) NODE_ARCH="arm64" ;;
        armhf)        NODE_ARCH="armv7l" ;;
        *)             NODE_ARCH="x64" ;;
    esac

    NODE_MAJOR=20
    curl -fsSL https://deb.nodesource.com/setup_${NODE_MAJOR}.x | bash -
    apt-get install -y -qq nodejs
    info "Node.js $(node -v) installed."
}

install_go2rtc() {
    info "Installing go2rtc..."
    systemctl stop go2rtc 2>/dev/null || true

    ARCH=$(dpkg --print-architecture)
    case "$ARCH" in
        armhf)   GO2RTC_ARCH="armv6" ;;
        arm64)   GO2RTC_ARCH="arm64" ;;
        aarch64) GO2RTC_ARCH="arm64" ;;
        *)       GO2RTC_ARCH="arm64" ;;
    esac

    LATEST_URL=$(curl -sL https://api.github.com/repos/AlexxIT/go2rtc/releases/latest \
        | grep "browser_download_url.*linux_${GO2RTC_ARCH}" \
        | head -1 | cut -d'"' -f4)

    if [ -z "$LATEST_URL" ]; then
        warn "Could not determine latest go2rtc release, trying direct URL..."
        LATEST_URL="https://github.com/AlexxIT/go2rtc/releases/latest/download/go2rtc_linux_${GO2RTC_ARCH}"
    fi

    wget -qO /usr/local/bin/go2rtc "$LATEST_URL"
    chmod +x /usr/local/bin/go2rtc
    info "go2rtc installed: $(go2rtc -v 2>&1 | head -1 || echo 'version check failed')"
}

setup_app() {
    info "Setting up H616 Monitor application..."

    useradd -r -s /bin/false h616-monitor 2>/dev/null || true

    mkdir -p "$INSTALL_DIR"/{backend,frontend,config,recordings}
    mkdir -p "$RECORDINGS_DIR"
    mkdir -p "$INSTALL_DIR/backend/.thumbnails"

    rsync -a --exclude='venv' --exclude='__pycache__' --exclude='.DS_Store' "$CURRENT_DIR/backend/" "$INSTALL_DIR/backend/"
    cp "$CURRENT_DIR/config/go2rtc.yaml" "$INSTALL_DIR/config/go2rtc.yaml"

    info "Creating Python virtual environment..."
    python3 -m venv "$INSTALL_DIR/backend/venv"
    "$INSTALL_DIR/backend/venv/bin/pip" install -q --upgrade pip
    "$INSTALL_DIR/backend/venv/bin/pip" install -q -r "$INSTALL_DIR/backend/requirements.txt"

    chown -R h616-monitor:h616-monitor "$INSTALL_DIR"

    info "Application setup complete."
}

setup_systemd() {
    info "Configuring systemd services..."

    cp "$CURRENT_DIR/deploy/go2rtc.service" /etc/systemd/system/
    cp "$CURRENT_DIR/deploy/h616-monitor.service" /etc/systemd/system/

    systemctl daemon-reload
    systemctl enable go2rtc h616-monitor
    info "Systemd services configured."
}

setup_nginx() {
    info "Configuring nginx..."
    cp "$CURRENT_DIR/deploy/nginx.conf" /etc/nginx/sites-available/h616-monitor
    ln -sf /etc/nginx/sites-available/h616-monitor /etc/nginx/sites-enabled/
    rm -f /etc/nginx/sites-enabled/default
    nginx -t && info "Nginx config OK" || error "Nginx config test failed"
}

build_frontend() {
    info "Building frontend on device..."
    cd "$CURRENT_DIR/frontend"
    npm ci --ignore-scripts
    npm run build
    mkdir -p "$INSTALL_DIR/frontend/dist"
    cp -r dist/* "$INSTALL_DIR/frontend/dist/"
    chown -R h616-monitor:h616-monitor "$INSTALL_DIR/frontend"
    info "Frontend built and installed."
}

start_services() {
    info "Starting services..."
    systemctl restart go2rtc
    sleep 2
    systemctl restart h616-monitor
    systemctl restart nginx

    systemctl is-active go2rtc >/dev/null && info "go2rtc: RUNNING" || error "go2rtc: FAILED"
    systemctl is-active h616-monitor >/dev/null && info "h616-monitor: RUNNING" || error "h616-monitor: FAILED"
    systemctl is-active nginx >/dev/null && info "nginx: RUNNING" || error "nginx: FAILED"

    echo ""
    info "========================================="
    info "H616 Monitor Platform is ready!"
    info "Web UI: http://$(hostname -I | awk '{print $1}')"
    info "API:   http://$(hostname -I | awk '{print $1}')/api/status"
    info "========================================="
}

main() {
    check_root
    install_system_deps
    install_nodejs
    install_go2rtc
    setup_app
    setup_systemd
    setup_nginx
    build_frontend
    start_services
}

main "$@"