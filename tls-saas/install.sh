#!/bin/bash
# =============================================================================
#  TLS Appointment Checker — Auto Installer for Ubuntu Server 24.04
#  Run as your normal user (NOT root). Sudo will be used where needed.
#  Usage:  bash install.sh
# =============================================================================

set -e  # Exit on any error

# ── Colours ──────────────────────────────────────────────────────────────────
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; CYAN='\033[0;36m'; NC='\033[0m'
info()    { echo -e "${CYAN}[INFO]${NC}  $1"; }
success() { echo -e "${GREEN}[OK]${NC}    $1"; }
warn()    { echo -e "${YELLOW}[WARN]${NC}  $1"; }
error()   { echo -e "${RED}[ERROR]${NC} $1"; exit 1; }

# ── Config — edit these before running ───────────────────────────────────────
DOMAIN=""           # e.g. "mysite.com"  — leave empty to use server IP only
APP_USER=$(whoami)
APP_DIR="/home/$APP_USER/tls-saas"
BACKEND_DIR="$APP_DIR/backend"
FRONTEND_DIR="$APP_DIR/frontend"
BACKEND_PORT=8000
FRONTEND_PORT=3000

echo ""
echo "============================================================"
echo "   TLS Appointment Checker — Installer"
echo "============================================================"
echo ""

# ── 1. System packages ────────────────────────────────────────────────────────
info "Updating system and installing packages..."
sudo apt-get update -qq
sudo apt-get upgrade -y -qq
sudo apt-get install -y -qq \
    python3 python3-pip python3-venv \
    nodejs npm \
    nginx \
    curl wget git \
    ffmpeg \
    libnss3 libatk1.0-0 libatk-bridge2.0-0 libcups2 libdrm2 \
    libxcomposite1 libxdamage1 libxfixes3 libxrandr2 libgbm1 \
    libasound2 libpango-1.0-0 libpangocairo-1.0-0
success "System packages installed"

# ── 2. Python virtual environment ────────────────────────────────────────────
info "Setting up Python virtual environment..."
cd "$BACKEND_DIR"
python3 -m venv venv
source venv/bin/activate
pip install --quiet --upgrade pip
pip install --quiet -r requirements.txt
success "Python dependencies installed"

# ── 3. Patchright browser ────────────────────────────────────────────────────
info "Installing Patchright Chromium browser..."
python3 -m patchright install chromium 2>&1 | tail -5
success "Patchright Chromium installed"

deactivate

# ── 4. Frontend dependencies & build ─────────────────────────────────────────
info "Installing Node.js dependencies..."
cd "$FRONTEND_DIR"
npm install --silent
info "Building Next.js frontend (this may take 2-3 minutes)..."
npm run build
success "Frontend built"

# ── 5. Systemd service — Backend ─────────────────────────────────────────────
info "Creating backend systemd service..."
sudo tee /etc/systemd/system/tls-backend.service > /dev/null <<EOF
[Unit]
Description=TLS Appointment Checker — Backend
After=network.target

[Service]
User=$APP_USER
WorkingDirectory=$BACKEND_DIR
ExecStart=$BACKEND_DIR/venv/bin/uvicorn app.main:app --host 127.0.0.1 --port $BACKEND_PORT --workers 1
Restart=always
RestartSec=5
Environment=PYTHONUNBUFFERED=1

[Install]
WantedBy=multi-user.target
EOF
success "Backend service created"

# ── 6. Systemd service — Frontend ────────────────────────────────────────────
info "Creating frontend systemd service..."
sudo tee /etc/systemd/system/tls-frontend.service > /dev/null <<EOF
[Unit]
Description=TLS Appointment Checker — Frontend
After=network.target tls-backend.service

[Service]
User=$APP_USER
WorkingDirectory=$FRONTEND_DIR
ExecStart=/usr/bin/npm start -- --port $FRONTEND_PORT
Restart=always
RestartSec=5
Environment=NODE_ENV=production

[Install]
WantedBy=multi-user.target
EOF
success "Frontend service created"

# ── 7. Enable & start services ────────────────────────────────────────────────
info "Enabling and starting backend & frontend services..."
sudo systemctl daemon-reload
sudo systemctl enable tls-backend tls-frontend
sudo systemctl start tls-backend tls-frontend
sleep 3
sudo systemctl is-active --quiet tls-backend && success "Backend is running" || warn "Backend may not have started — check: sudo journalctl -u tls-backend -n 30"
sudo systemctl is-active --quiet tls-frontend && success "Frontend is running" || warn "Frontend may not have started — check: sudo journalctl -u tls-frontend -n 30"

# ── 8. Nginx config ───────────────────────────────────────────────────────────
info "Configuring Nginx reverse proxy..."

# Determine server_name line
if [ -n "$DOMAIN" ]; then
    SERVER_NAME="$DOMAIN www.$DOMAIN"
else
    SERVER_NAME="_"
fi

sudo tee /etc/nginx/sites-available/tls > /dev/null <<EOF
server {
    listen 80;
    server_name $SERVER_NAME;

    client_max_body_size 20M;

    # Backend API
    location /api/ {
        proxy_pass http://127.0.0.1:$BACKEND_PORT;
        proxy_http_version 1.1;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_read_timeout 120s;
    }

    # WebSocket
    location /ws {
        proxy_pass http://127.0.0.1:$BACKEND_PORT;
        proxy_http_version 1.1;
        proxy_set_header Upgrade \$http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host \$host;
        proxy_read_timeout 3600s;
    }

    # Frontend
    location / {
        proxy_pass http://127.0.0.1:$FRONTEND_PORT;
        proxy_http_version 1.1;
        proxy_set_header Upgrade \$http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
    }
}
EOF

# Remove default site if present
sudo rm -f /etc/nginx/sites-enabled/default
sudo ln -sf /etc/nginx/sites-available/tls /etc/nginx/sites-enabled/tls

sudo nginx -t && sudo systemctl reload nginx
success "Nginx configured and reloaded"

# ── 9. Cloudflare Tunnel (optional) ──────────────────────────────────────────
info "Installing Cloudflare Tunnel (cloudflared)..."
ARCH=$(dpkg --print-architecture)
CF_URL="https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-$ARCH"
sudo curl -fsSL "$CF_URL" -o /usr/local/bin/cloudflared
sudo chmod +x /usr/local/bin/cloudflared
success "cloudflared installed at /usr/local/bin/cloudflared"

# ── 10. Firewall ──────────────────────────────────────────────────────────────
info "Configuring firewall (ufw)..."
sudo ufw allow OpenSSH
sudo ufw allow 'Nginx Full'
sudo ufw --force enable
success "Firewall configured"

# ── Done ──────────────────────────────────────────────────────────────────────
SERVER_IP=$(hostname -I | awk '{print $1}')
echo ""
echo "============================================================"
echo -e "${GREEN}  Installation complete!${NC}"
echo "============================================================"
echo ""
echo "  Local access:   http://$SERVER_IP"
if [ -n "$DOMAIN" ]; then
echo "  Domain:         http://$DOMAIN"
fi
echo ""
echo "  Useful commands:"
echo "    sudo systemctl status tls-backend"
echo "    sudo systemctl status tls-frontend"
echo "    sudo journalctl -u tls-backend -f      # live backend logs"
echo "    sudo journalctl -u tls-frontend -f     # live frontend logs"
echo ""
echo "  To set up Cloudflare Tunnel (free HTTPS, no port forwarding):"
echo "    cloudflared tunnel login"
echo "    cloudflared tunnel create tls-app"
echo "    cloudflared tunnel route dns tls-app $DOMAIN"
echo "    cloudflared tunnel run tls-app"
echo ""
echo "  To enable HTTPS with Let's Encrypt (if you have a domain):"
echo "    sudo apt install certbot python3-certbot-nginx -y"
echo "    sudo certbot --nginx -d $DOMAIN"
echo ""
