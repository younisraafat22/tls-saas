#!/bin/bash
# =============================================================================
#  TLS Appointment Checker — Auto Installer
#  Username: younis | Frontend: https://tls-saas.vercel.app
#  Run: bash install.sh
# =============================================================================

set -e  # Exit on any error

# ── Colours ──────────────────────────────────────────────────────────────────
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; CYAN='\033[0;36m'; NC='\033[0m'
info()    { echo -e "${CYAN}[INFO]${NC}  $1"; }
success() { echo -e "${GREEN}[OK]${NC}    $1"; }
warn()    { echo -e "${YELLOW}[WARN]${NC}  $1"; }
error()   { echo -e "${RED}[ERROR]${NC} $1"; exit 1; }

# ── Config ────────────────────────────────────────────────────────────────────
USERNAME="younis"
# Auto-detect repo root from where this script lives
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_DIR="$SCRIPT_DIR/backend"
VENV="$BACKEND_DIR/venv"
VERCEL_URL="https://tls-saas.vercel.app"
echo "  Repo root: $SCRIPT_DIR"

echo ""
echo "============================================================"
echo "   TLS Appointment Checker — Auto Installer"
echo "============================================================"
echo ""

# ── 1. System packages ────────────────────────────────────────────────────────
info "Installing system dependencies..."
sudo apt-get update -y
sudo apt-get install -y \
    python3.12 python3.12-venv python3-pip git curl openssh-server \
    wget gnupg2 libnss3 libxss1 libasound2t64 libatk-bridge2.0-0t64 \
    libdrm2 libxcomposite1 libxdamage1 libxrandr2 libgbm1 \
    libpango-1.0-0 libcairo2 libatspi2.0-0t64 \
    fonts-liberation fonts-noto-color-emoji
sudo systemctl enable ssh && sudo systemctl start ssh
success "System packages installed | SSH enabled"

# ── 2. Clone / update repo ────────────────────────────────────────────────────
info "Pulling latest changes..."
cd "$SCRIPT_DIR" && git pull origin main
success "Repository up to date"

# ── 3. Python virtual environment ─────────────────────────────────────────────
info "Setting up Python 3.11 virtual environment..."
cd "$BACKEND_DIR"
python3.12 -m venv venv
source "$VENV/bin/activate"
pip install --upgrade pip -q
pip install -r requirements.txt -q
success "Python dependencies installed"

# ── 4. Playwright Chromium ────────────────────────────────────────────────────
info "Installing Playwright Chromium (this takes 2-3 mins)..."
python -m patchright install chromium
python -m patchright install-deps chromium
success "Chromium installed"

# ── 5. .env file & data directory ────────────────────────────────────────────
info "Creating .env file and data directory..."
mkdir -p "$BACKEND_DIR/data"

cat > "$BACKEND_DIR/.env" << ENVEOF
DATABASE_URL=sqlite+aiosqlite:////$BACKEND_DIR/data/tls_saas.db
SECRET_KEY=qZGlsKFtbLxl3EBBPYv9UvYIzLR6uydmI0Fcur2LObeR030TnYe3hKoDbqwKqfKo
JWT_SECRET=qZGlsKFtbLxl3EBBPYv9UvYIzLR6uydmI0Fcur2LObeR030TnYe3hKoDbqwKqfKo
ADMIN_EMAIL=younis.raafat2@gmail.com
ADMIN_PASSWORD=Yois@Ra753
SMTP_SERVER=smtp.gmail.com
SMTP_PORT=587
SMTP_USERNAME=tlsappointmentchecker@gmail.com
SMTP_PASSWORD=zylc etmv kuic uluq
SENDER_EMAIL=tlsappointmentchecker@gmail.com
SENDER_NAME=TLS Appointment Checker
CREDENTIAL_ENCRYPTION_KEY=vcgcr_5TAdK4qnuvpgRn858y-K1vMDcRzU5zNKpa6IM=
CHECK_INTERVAL_MINUTES=5
BROWSER_HEADLESS=true
ALLOWED_ORIGINS=$VERCEL_URL
APP_ENV=production
ENVEOF

success ".env file written"

# ── 6. Systemd service (auto-start on boot) ───────────────────────────────────
info "Creating systemd auto-start service..."
sudo tee /etc/systemd/system/tls-backend.service > /dev/null << SVCEOF
[Unit]
Description=TLS Appointment Checker Backend
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=$USERNAME
WorkingDirectory=$BACKEND_DIR
EnvironmentFile=$BACKEND_DIR/.env
ExecStart=$VENV/bin/python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
Restart=always
RestartSec=5
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
SVCEOF

sudo systemctl daemon-reload
sudo systemctl enable tls-backend
sudo systemctl start tls-backend
sleep 4

if sudo systemctl is-active --quiet tls-backend; then
    success "Backend service is RUNNING on port 8000"
else
    warn "Backend didn't start — check: sudo journalctl -u tls-backend -n 40"
fi

# ── 7. Cloudflare Tunnel ──────────────────────────────────────────────────────
info "Installing cloudflared..."
curl -sL https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64.deb -o /tmp/cloudflared.deb
sudo dpkg -i /tmp/cloudflared.deb
rm /tmp/cloudflared.deb
success "cloudflared installed"

# ── Done ──────────────────────────────────────────────────────────────────────
LOCAL_IP=$(hostname -I | awk '{print $1}')
echo ""
echo "============================================================"
echo -e "${GREEN}  Setup Complete!${NC}"
echo "============================================================"
echo ""
echo "  Local health check:"
echo "    curl http://localhost:8000/api/health"
echo ""
echo "  Backend logs:   sudo journalctl -u tls-backend -f"
echo "  Restart:        sudo systemctl restart tls-backend"
echo ""
echo "  ── NEXT STEP: Get a public HTTPS URL ───────────────────"
echo ""
echo "  Run this command and leave it open:"
echo "    cloudflared tunnel --url http://localhost:8000"
echo ""
echo "  It will print a URL like: https://xxxx-xxxx.trycloudflare.com"
echo ""
echo "  Then in Vercel dashboard → tls-saas project →"
echo "  Settings → Environment Variables → add:"
echo "    NEXT_PUBLIC_API_URL = https://xxxx-xxxx.trycloudflare.com"
echo "  Then click Redeploy."
echo "============================================================"
