#!/bin/bash
# =============================================================================
#  Permanent Cloudflare Tunnel + Auto-update Vercel
#  Run once on the Ubuntu laptop: bash setup-tunnel.sh
# =============================================================================

set -e
RED='\033[0;31m'; GREEN='\033[0;32m'; CYAN='\033[0;36m'; NC='\033[0m'
info()    { echo -e "${CYAN}[INFO]${NC}  $1"; }
success() { echo -e "${GREEN}[OK]${NC}    $1"; }

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
USERNAME="younis"
VERCEL_PROJECT="tls-saas"
WRAPPER="$SCRIPT_DIR/tunnel-wrapper.sh"

# Token passed as argument or already saved in .env.tunnel
if [ -n "$1" ]; then
    VERCEL_TOKEN="$1"
    echo "$1" > "$SCRIPT_DIR/.env.tunnel"
    chmod 600 "$SCRIPT_DIR/.env.tunnel"
elif [ -f "$SCRIPT_DIR/.env.tunnel" ]; then
    VERCEL_TOKEN=$(cat "$SCRIPT_DIR/.env.tunnel")
else
    echo "Usage: bash setup-tunnel.sh YOUR_VERCEL_TOKEN"
    exit 1
fi

# ── 1. Create the tunnel wrapper script ──────────────────────────────────────
info "Creating tunnel wrapper script..."

cat > "$WRAPPER" << 'WRAPEOF'
#!/bin/bash
# Starts cloudflared quick tunnel, extracts the public URL,
# updates Vercel NEXT_PUBLIC_API_URL, then keeps running.

VERCEL_TOKEN=$(cat "$(dirname "$0")/.env.tunnel" 2>/dev/null || echo '')
VERCEL_PROJECT="tls-saas"
LOGFILE="/tmp/cloudflared-tunnel.log"

# Kill any old cloudflared process
pkill -f "cloudflared tunnel --url" 2>/dev/null || true
sleep 1

# Start cloudflared and tee output to logfile
cloudflared tunnel --url http://localhost:8000 2>&1 | tee "$LOGFILE" &
CF_PID=$!

# Wait for the URL to appear in the log (up to 30 seconds)
echo "[tunnel] Waiting for tunnel URL..."
for i in $(seq 1 30); do
    URL=$(grep -oP 'https://[a-z0-9-]+\.trycloudflare\.com' "$LOGFILE" 2>/dev/null | head -1)
    if [ -n "$URL" ]; then
        break
    fi
    sleep 1
done

if [ -z "$URL" ]; then
    echo "[tunnel] ERROR: Could not detect tunnel URL after 30s"
    wait $CF_PID
    exit 1
fi

echo "[tunnel] Tunnel URL: $URL"

# ── Update Vercel NEXT_PUBLIC_API_URL ────────────────────────────────────────
echo "[tunnel] Updating Vercel NEXT_PUBLIC_API_URL → $URL"

# Get existing env var ID for production
ENV_LIST=$(curl -sf \
  -H "Authorization: Bearer $VERCEL_TOKEN" \
  "https://api.vercel.com/v9/projects/$VERCEL_PROJECT/env?target=production" 2>/dev/null || echo "{}")

ENV_ID=$(echo "$ENV_LIST" | grep -o '"id":"[^"]*"' | head -1 | \
  # Find the one next to NEXT_PUBLIC_API_URL key
  true; echo "$ENV_LIST" | python3 -c "
import sys, json
data = json.load(sys.stdin)
envs = data.get('envs', [])
for e in envs:
    if e.get('key') == 'NEXT_PUBLIC_API_URL':
        print(e.get('id',''))
        break
" 2>/dev/null)

if [ -n "$ENV_ID" ]; then
    # Update existing
    RESULT=$(curl -sf -X PATCH \
      -H "Authorization: Bearer $VERCEL_TOKEN" \
      -H "Content-Type: application/json" \
      -d "{\"value\":\"$URL\",\"target\":[\"production\"]}" \
      "https://api.vercel.com/v9/projects/$VERCEL_PROJECT/env/$ENV_ID" 2>/dev/null)
    echo "[tunnel] Updated existing env var"
else
    # Create new
    RESULT=$(curl -sf -X POST \
      -H "Authorization: Bearer $VERCEL_TOKEN" \
      -H "Content-Type: application/json" \
      -d "{\"key\":\"NEXT_PUBLIC_API_URL\",\"value\":\"$URL\",\"target\":[\"production\"],\"type\":\"plain\"}" \
      "https://api.vercel.com/v10/projects/$VERCEL_PROJECT/env" 2>/dev/null)
    echo "[tunnel] Created new env var"
fi

# ── Trigger Vercel redeploy ───────────────────────────────────────────────────
echo "[tunnel] Triggering Vercel redeploy..."
# Get latest deployment ID
LATEST_DEP=$(curl -sf \
  -H "Authorization: Bearer $VERCEL_TOKEN" \
  "https://api.vercel.com/v6/deployments?projectId=$VERCEL_PROJECT&limit=1&target=production" 2>/dev/null)

DEP_ID=$(echo "$LATEST_DEP" | python3 -c "
import sys, json
data = json.load(sys.stdin)
deps = data.get('deployments', [])
if deps: print(deps[0].get('uid',''))
" 2>/dev/null)

if [ -n "$DEP_ID" ]; then
    curl -sf -X POST \
      -H "Authorization: Bearer $VERCEL_TOKEN" \
      -H "Content-Type: application/json" \
      -d "{\"name\":\"$VERCEL_PROJECT\"}" \
      "https://api.vercel.com/v13/deployments?forceNew=1&withLatestCommit=1&deploymentId=$DEP_ID" \
      > /dev/null 2>&1 && echo "[tunnel] Redeploy triggered" || echo "[tunnel] Redeploy skipped (will use cached env on next deploy)"
fi

echo "[tunnel] All done. Tunnel is live at: $URL"
echo "[tunnel] Keeping tunnel alive..."

# Keep running with cloudflared
wait $CF_PID
WRAPEOF

chmod +x "$WRAPPER"
success "Wrapper script created at $WRAPPER"

# ── 2. Create systemd service ─────────────────────────────────────────────────
info "Creating cloudflared-tunnel systemd service..."

sudo tee /etc/systemd/system/cloudflared-tunnel.service > /dev/null << EOF
[Unit]
Description=Cloudflare Tunnel (auto-update Vercel)
After=network-online.target tls-backend.service
Wants=network-online.target

[Service]
Type=simple
User=$USERNAME
ExecStart=/bin/bash $WRAPPER
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable cloudflared-tunnel
sudo systemctl start cloudflared-tunnel
sleep 8

if sudo systemctl is-active --quiet cloudflared-tunnel; then
    success "Tunnel service is RUNNING"
    echo ""
    info "Fetching current tunnel URL..."
    sleep 5
    URL=$(grep -oP 'https://[a-z0-9-]+\.trycloudflare\.com' /tmp/cloudflared-tunnel.log 2>/dev/null | head -1)
    if [ -n "$URL" ]; then
        echo ""
        echo "  ✓ Tunnel URL: $URL"
        echo ""
        echo "  Vercel NEXT_PUBLIC_API_URL is being updated automatically."
        echo "  Vercel will redeploy in ~2 minutes."
    fi
else
    echo "  Service may still be starting. Check:"
    echo "  sudo journalctl -u cloudflared-tunnel -f"
fi

echo ""
echo "  Useful commands:"
echo "    sudo systemctl status cloudflared-tunnel"
echo "    sudo journalctl -u cloudflared-tunnel -f"
echo "    cat /tmp/cloudflared-tunnel.log | grep trycloudflare"
