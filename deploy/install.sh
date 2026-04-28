#!/bin/bash
set -euo pipefail

GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m'

INSTALL_DIR="/opt/h616-monitor"
RECORDINGS_DIR="/opt/h616-monitor/recordings"
CURRENT_DIR="$(cd "$(dirname "$0")/.." && pwd)"

FORCE="${1:-}"
[ "$FORCE" = "--force" ] && FORCE_FLAG=1 || FORCE_FLAG=0

info()  { echo -e "${GREEN}[INFO]${NC} $*"; }
warn()  { echo -e "${YELLOW}[WARN]${NC} $*"; }
error() { echo -e "${RED}[ERROR]${NC} $*"; exit 1; }

check_root() {
    [ "$(id -u)" -eq 0 ] || error "This script must be run as root (sudo)"
}

step() {
    local name="$1"
    echo ""
    info "=== $name ==="
}

# --- System deps (skip if already installed) ---
install_system_deps() {
    if [ "$FORCE_FLAG" -eq 0 ] && dpkg -s python3-venv nginx ffmpeg &>/dev/null; then
        info "System dependencies already installed, skipping. Use --force to reinstall."
        return 0
    fi
    step "Installing system dependencies"
    apt-get update -qq
    apt-get install -y -qq \
        python3 python3-pip python3-venv \
        ffmpeg v4l-utils \
        nginx \
        curl wget rsync
    info "System dependencies installed."
}

# --- Node.js (skip if present) ---
install_nodejs() {
    if [ "$FORCE_FLAG" -eq 0 ] && command -v node &>/dev/null; then
        info "Node.js $(node -v) already installed, skipping."
        return 0
    fi
    step "Installing Node.js"
    NODE_MAJOR=20
    curl -fsSL https://deb.nodesource.com/setup_${NODE_MAJOR}.x | bash -
    apt-get install -y -qq nodejs
    info "Node.js $(node -v) installed."
}

# --- go2rtc (skip if same version) ---
install_go2rtc() {
    local latest_url wanted_version current_version

    ARCH=$(dpkg --print-architecture)
    case "$ARCH" in
        armhf)   GO2RTC_ARCH="armv6" ;;
        arm64)   GO2RTC_ARCH="arm64" ;;
        aarch64) GO2RTC_ARCH="arm64" ;;
        *)       GO2RTC_ARCH="arm64" ;;
    esac

    latest_url=$(curl -sL https://api.github.com/repos/AlexxIT/go2rtc/releases/latest \
        | grep "browser_download_url.*linux_${GO2RTC_ARCH}" \
        | head -1 | cut -d'"' -f4)

    if [ -z "$latest_url" ]; then
        warn "Could not determine latest go2rtc release, trying direct URL..."
        latest_url="https://github.com/AlexxIT/go2rtc/releases/latest/download/go2rtc_linux_${GO2RTC_ARCH}"
    fi

    wanted_version=$(basename "$latest_url" | sed 's/go2rtc_//; s/_linux.*//')

    if [ "$FORCE_FLAG" -eq 0 ] && [ -x /usr/local/bin/go2rtc ]; then
        current_version=$(go2rtc -v 2>&1 | head -1 || echo "unknown")
        if echo "$current_version" | grep -q "$wanted_version"; then
            info "go2rtc ${current_version} already installed, skipping. Use --force to reinstall."
            return 0
        fi
        info "Updating go2rtc: ${current_version} -> ${wanted_version}"
    else
        step "Installing go2rtc"
    fi

    systemctl stop go2rtc 2>/dev/null || true
    wget -qO /usr/local/bin/go2rtc "$latest_url"
    chmod +x /usr/local/bin/go2rtc
    info "go2rtc installed: $(go2rtc -v 2>&1 | head -1 || echo 'version check failed')"
}

# --- Backend app ---
setup_app() {
    step "Setting up backend"

    useradd -r -s /bin/false h616-monitor 2>/dev/null || true
    usermod -aG video h616-monitor 2>/dev/null || true

    mkdir -p "$INSTALL_DIR"/{backend,frontend,config,recordings}
    mkdir -p "$RECORDINGS_DIR"
    mkdir -p "$INSTALL_DIR/backend/.thumbnails"

    rsync -a --exclude='venv' --exclude='__pycache__' --exclude='.DS_Store' "$CURRENT_DIR/backend/" "$INSTALL_DIR/backend/"
    cp "$CURRENT_DIR/config/go2rtc.yaml" "$INSTALL_DIR/config/go2rtc.yaml"

    if [ ! -d "$INSTALL_DIR/backend/venv" ]; then
        info "Creating Python virtual environment..."
        python3 -m venv "$INSTALL_DIR/backend/venv"
    else
        info "Virtual environment exists, reusing."
    fi
    "$INSTALL_DIR/backend/venv/bin/pip" install -q --upgrade pip
    "$INSTALL_DIR/backend/venv/bin/pip" install -q -r "$INSTALL_DIR/backend/requirements.txt"

    chown -R h616-monitor:h616-monitor "$INSTALL_DIR"

    info "Backend setup complete."
}

# --- Systemd ---
setup_systemd() {
    step "Configuring systemd services"
    cp "$CURRENT_DIR/deploy/go2rtc.service" /etc/systemd/system/
    cp "$CURRENT_DIR/deploy/h616-monitor.service" /etc/systemd/system/
    systemctl daemon-reload
    systemctl enable go2rtc h616-monitor
    info "Systemd services configured."
}

# --- Nginx ---
setup_nginx() {
    step "Configuring nginx"
    cp "$CURRENT_DIR/deploy/nginx.conf" /etc/nginx/sites-available/h616-monitor
    ln -sf /etc/nginx/sites-available/h616-monitor /etc/nginx/sites-enabled/
    rm -f /etc/nginx/sites-enabled/default
    nginx -t && info "Nginx config OK" || error "Nginx config test failed"
}

# --- Frontend (skip if dist up-to-date) ---
build_frontend() {
    local src_hash="$CURRENT_DIR/frontend/package.json"
    local dist_hash="$INSTALL_DIR/frontend/.build-hash"

    if [ "$FORCE_FLAG" -eq 0 ] && [ -f "$dist_hash" ]; then
        local old_hash
        old_hash=$(cat "$dist_hash" 2>/dev/null || echo "")
        local new_hash
        new_hash=$(md5sum "$src_hash" "$CURRENT_DIR/frontend/src/App.vue" 2>/dev/null | md5sum | cut -d' ' -f1 || echo "")
        if [ "$old_hash" = "$new_hash" ] && [ -d "$INSTALL_DIR/frontend/dist" ]; then
            info "Frontend unchanged, skipping build. Use --force to rebuild."
            return 0
        fi
    fi

    step "Building frontend"
    cd "$CURRENT_DIR/frontend"
    npm ci --ignore-scripts
    npm run build
    mkdir -p "$INSTALL_DIR/frontend/dist"
    cp -rf dist/* "$INSTALL_DIR/frontend/dist/"
    md5sum "$src_hash" "$CURRENT_DIR/frontend/src/App.vue" 2>/dev/null | md5sum | cut -d' ' -f1 > "$dist_hash"
    chown -R h616-monitor:h616-monitor "$INSTALL_DIR/frontend"
    info "Frontend built and installed."
}

# --- Start ---
start_services() {
    step "Starting services"
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