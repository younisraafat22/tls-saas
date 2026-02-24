#!/bin/bash
# Run this any time you push changes to update the server
set -e
APP_DIR="/home/$(whoami)/tls-saas"

echo "Pulling latest changes..."
cd "$APP_DIR" && git pull

echo "Updating backend dependencies..."
cd "$APP_DIR/backend"
source venv/bin/activate
pip install --quiet -r requirements.txt
deactivate

echo "Rebuilding frontend..."
cd "$APP_DIR/frontend"
npm install --silent
npm run build

echo "Restarting services..."
sudo systemctl restart tls-backend tls-frontend

echo "Done! Services restarted."
