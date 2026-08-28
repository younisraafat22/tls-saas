#!/bin/bash
# Run this any time you push changes to update the server
set -e

# Resolve repo location from this script's path.
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
APP_DIR="$SCRIPT_DIR"

# Backward-compat fallback for older layout where repo lived one level deeper.
if [[ -d "$APP_DIR/tls-saas/backend" && -f "$APP_DIR/tls-saas/update.sh" ]]; then
	APP_DIR="$APP_DIR/tls-saas"
fi

echo "Pulling latest changes..."
cd "$APP_DIR" && git pull origin main

echo "Updating backend dependencies..."
cd "$APP_DIR/backend"
source venv/bin/activate
pip install --quiet -r requirements.txt
deactivate

# Worker-first deployment: laptop runs monitoring worker, Fly.io is main backend.
echo "Restarting worker service..."
if systemctl list-unit-files | grep -q '^tls-worker\.service'; then
	sudo systemctl restart tls-worker
else
	echo "tls-worker service not found; skipped"
fi

# Optional full-stack local restart for legacy/local setups.
if [[ "${UPDATE_FULL_STACK:-0}" == "1" ]]; then
	if [[ -d "$APP_DIR/frontend" ]]; then
		if command -v npm >/dev/null 2>&1; then
			echo "Rebuilding frontend..."
			cd "$APP_DIR/frontend"
			npm install --silent
			npm run build
		else
			echo "npm not found; skipping frontend build"
		fi
	fi

	if systemctl list-unit-files | grep -q '^tls-backend\.service'; then
		sudo systemctl restart tls-backend
	fi
	if systemctl list-unit-files | grep -q '^tls-frontend\.service'; then
		sudo systemctl restart tls-frontend
	fi
fi

echo "Done! Worker update complete."
