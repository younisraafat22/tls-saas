# TLS SaaS Complete Operations Manual

This manual is recreated from the current project codebase and scripts.
It is intended to be the single operational reference for running, testing, deploying, updating, and troubleshooting the full system.

---

## 1. Project Overview

### 1.1 Components
- Backend API: `backend/` (FastAPI, async SQLAlchemy, WebSocket, scheduler and worker APIs)
- Frontend Web App: `frontend/` (Next.js 14, React, Tailwind)
- Desktop App: `desktop/` (Flet + Selenium/Playwright automation + license system)
- Infrastructure scripts: root scripts (`start.bat`, `stop.bat`, `install.sh`, `update.sh`, `setup-tunnel.sh`)

### 1.2 Runtime Architecture
- Local dev mode:
  - Backend runs on `http://localhost:8000`
  - Frontend runs on `http://localhost:3000`
- Production hybrid mode:
  - Fly.io backend in API mode (`WORKER_MODE=true`)
  - Laptop worker runs checks and posts results to Fly.io
  - Frontend deployed on Vercel

---

## 2. Full Repository Map (Operationally Important)

### 2.1 Root
- `start.bat`: starts backend and frontend in separate windows
- `stop.bat`: force-stops backend and frontend processes
- `docker-compose.yml`: container orchestration for backend/frontend
- `install.sh`: Linux setup script for backend service + deps
- `update.sh`: Linux update + service restart script
- `setup-tunnel.sh`: Cloudflare tunnel + Vercel env auto-update script

### 2.2 Backend
- `backend/app/main.py`: app entrypoint, migrations, seeding, router registration, health, websocket
- `backend/app/config.py`: all backend env settings/defaults
- `backend/app/models.py`: core DB schema
- `backend/app/auth.py`: JWT and auth helpers
- `backend/app/websocket.py`: realtime manager
- `backend/app/api/`: route modules (auth, subscriptions, payments, monitoring, admin, desktop, etc.)
- `backend/app/services/`: checker, scheduler, email, telegram and related services
- `backend/worker.py`: polling worker for remote checks
- `backend/tls-worker.service`: systemd unit for worker
- `backend/requirements.txt`: full backend deps
- `backend/requirements-fly.txt`: slim deps for Fly.io API deployment

### 2.3 Frontend
- `frontend/package.json`: scripts and dependencies
- `frontend/next.config.js`: runtime env pass-through (`NEXT_PUBLIC_API_URL`, `NEXT_PUBLIC_WS_URL`)
- `frontend/src/app/`: routes (landing, auth, dashboard, admin, legal pages)

### 2.4 Desktop
- `desktop/main.py`: desktop app entrypoint and UI flow
- `desktop/config.py`: desktop runtime config loading hierarchy
- `desktop/auth_service.py`, `checker_service.py`, `license_service.py`, `database.py`
- `desktop/build.ps1`: build pipeline wrapper (PyInstaller + Inno Setup)
- `desktop/TLSAppointmentChecker.spec`: PyInstaller config
- `desktop/installer_setup.iss`: Inno Setup installer definition
- `desktop/version.json`: desktop version metadata

---

## 3. Exact Start/Stop Commands

## 3.1 Windows Quick Start (Recommended)

### Start all (backend + frontend)
```bat
start.bat
```
What it does:
1. Opens backend terminal and starts Uvicorn on port 8000
2. Opens frontend terminal and starts Next dev on port 3000
3. Opens browser to frontend URL

### Stop all
```bat
stop.bat
```
What it does:
- Kills windows titled `TLS Backend*` and `TLS Frontend*`
- Kills `uvicorn.exe` and `node.exe`

## 3.2 Manual Local Start (if not using BAT files)

### Backend (Windows)
```powershell
cd backend
venv\Scripts\activate
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### Frontend (Windows)
```powershell
cd frontend
npm install
npm run dev
```

### Desktop App (dev run)
```powershell
cd desktop
python main.py
```

## 3.3 Docker Start
```bash
docker-compose up --build
```
Services:
- Backend exposed on 8000
- Frontend exposed on 3000
- Compose healthcheck currently calls `http://localhost:8000/health` in container

Important:
- API health endpoint in code is `GET /api/health`
- If compose healthcheck fails unexpectedly, align it with `/api/health`

---

## 4. Backend Control Manual

## 4.1 Entrypoint behavior (`backend/app/main.py`)
On startup the backend:
1. Creates DB tables (`create_tables()`)
2. Runs inline migration safety SQL (`ALTER TABLE ...`, `CREATE TABLE IF NOT EXISTS ...`)
3. Seeds data if missing:
   - Admin user from `ADMIN_EMAIL`, `ADMIN_PASSWORD`
   - Plans
   - Branches
4. Evaluates worker mode:
   - If `WORKER_MODE=true`: scheduler disabled
   - Else scheduler can auto-resume based on DB system settings

## 4.2 Routers registered
- `/api/auth`
- `/api/subscriptions`
- `/api/payments`
- `/api/monitoring`
- `/api/admin`
- `/api/contact`
- `/api/credentials`
- `/api/app` (desktop support APIs)
- `/api/metrics`

## 4.3 Health and websocket
- Health endpoint: `GET /api/health`
- User WebSocket: `/ws/user?token=...`

## 4.4 Key env variables (`backend/app/config.py`)
Critical in production:
- `SECRET_KEY`
- `JWT_SECRET`
- `DATABASE_URL`
- `ADMIN_EMAIL`, `ADMIN_PASSWORD`
- `ALLOWED_ORIGINS`
- `WORKER_SECRET`
- `CREDENTIAL_ENCRYPTION_KEY`
- SMTP settings (`SMTP_*`, `SENDER_*`)
- Desktop release settings:
  - `DESKTOP_APP_VERSION`
  - `DESKTOP_DOWNLOAD_URL`
  - `DESKTOP_RELEASE_NOTES`
  - `DESKTOP_FORCE_UPDATE`

---

## 5. Frontend Control Manual

## 5.1 Scripts (`frontend/package.json`)
```bash
npm run dev
npm run build
npm start
npm run lint
```

## 5.2 Required public env
- `NEXT_PUBLIC_API_URL`
- `NEXT_PUBLIC_WS_URL`

Defaults in `next.config.js`:
- API: `http://localhost:8000`
- WS: `ws://localhost:8000`

## 5.3 Main route areas (`frontend/src/app`)
- Public pages: landing, login, register, contact, reviews, terms, privacy
- User area: dashboard + branches/payments/notifications/settings
- Admin area: dashboard/users/payments/licenses/monitoring/logs/settings/reviews

---

## 6. Desktop App Control Manual

## 6.1 Build and package

### Build command
```powershell
cd desktop
.\build.ps1
```
This script does:
1. `python -m PyInstaller TLSAppointmentChecker.spec --clean ...`
2. Calls Inno Setup compiler (`ISCC.exe`) with `installer_setup.iss`

Output:
- Built app folder under `desktop/dist/TLSAppointmentChecker/`
- Installer EXE under `desktop/installer_output/`

## 6.2 Installer behavior (`desktop/installer_setup.iss`)
- Requires Windows 10+ and admin privileges
- Installs app under Program Files
- Creates start menu entries
- Optionally creates desktop icon
- Installs bundled Cloudflare WARP MSI silently if not installed
- Warns user if Chrome missing

## 6.3 Version metadata (`desktop/version.json`)
Current file has:
- `version`
- `download_url`
- `release_notes`

Important consistency rule:
- Keep version in sync across:
  - `desktop/version.json`
  - backend `DESKTOP_APP_VERSION`
  - installer output naming/version

## 6.4 Desktop update API
Desktop checks backend endpoint:
- `GET /api/app/version`
Response includes:
- version
- download_url
- release_notes
- force_update

Backend source of truth:
- `backend/app/config.py` desktop release vars

---

## 7. Linux/VPS Operations

## 7.1 Initial install (`install.sh`)
Main actions:
1. Installs system dependencies
2. Creates backend Python venv and installs requirements
3. Installs Chromium deps for patchright
4. Writes backend `.env`
5. Creates and starts `tls-backend` systemd service
6. Installs cloudflared helper package

Run:
```bash
bash install.sh
```

## 7.2 Update server (`update.sh`)
Run:
```bash
bash update.sh
```
What it does:
- Pulls latest git changes
- Reinstalls backend requirements
- Rebuilds frontend
- Restarts `tls-backend` and `tls-frontend`

## 7.3 Worker service (`backend/tls-worker.service`)
Worker process command:
- `python worker.py`

Reads env from:
- `backend/.env.worker`

Useful commands:
```bash
sudo systemctl status tls-worker
sudo systemctl restart tls-worker
journalctl -u tls-worker -f
```

---

## 8. Complete Pre-Release Manual QA

Run this in order before release.

## 8.1 Auth & account flows
1. Register new account from frontend
2. Login and refresh token path
3. Forgot/reset password flow
4. Verify protected route denial when unauthenticated

## 8.2 Subscription and payment flow
1. View plans API and pricing render on UI
2. Submit payment from web flow
3. Submit payment from desktop flow (`/api/app/payments/submit`)
4. Approve in admin panel
5. Confirm active subscription and/or generated license

## 8.3 Monitoring flow
1. Select branches in dashboard
2. Trigger checks (scheduler or worker)
3. Confirm results appear in monitoring endpoints
4. Confirm websocket updates in user dashboard and admin pages

## 8.4 License flow
1. Verify valid key accepted (`/api/monitoring/license/verify`)
2. Verify invalid or tampered key rejected
3. Verify deactivation endpoint behavior (`/api/monitoring/license/deactivate`)
4. Verify license recovery (`/api/app/license/recover`)

## 8.5 Desktop runtime
1. Launch clean install (first-run flow)
2. Confirm check interval behavior
3. Confirm notifications (Windows + email path)
4. Confirm update check against `/api/app/version`

## 8.6 Admin operations
1. Review users list and role controls
2. Review pending payments queue and actions
3. Start/stop scheduler controls
4. Check admin monitoring logs
5. Confirm settings updates persist

## 8.7 Reliability checks
1. Restart backend and ensure startup migrations do not break
2. Restart worker and ensure it resumes polling jobs
3. Validate health endpoint: `GET /api/health`
4. Validate no CORS mismatch between frontend and backend origin settings

---

## 9. Release Procedure (Step-by-Step)

## 9.1 Backend release
1. Update code and env values
2. If Fly.io deployment:
```bash
cd backend
flyctl deploy --app backend-cold-sound-6496
```
3. Verify:
- `GET /api/health`
- auth endpoint login
- monitoring endpoint response

## 9.2 Frontend release
```bash
cd frontend
npm install
npm run build
```
Deploy via Vercel (prod).
Confirm env:
- `NEXT_PUBLIC_API_URL`
- `NEXT_PUBLIC_WS_URL`

## 9.3 Desktop release
1. Update app version metadata
2. Build with `desktop/build.ps1`
3. Upload installer to release location
4. Update backend desktop env values:
- `DESKTOP_APP_VERSION`
- `DESKTOP_DOWNLOAD_URL`
- `DESKTOP_RELEASE_NOTES`
- optional `DESKTOP_FORCE_UPDATE=true`
5. Restart backend service
6. Open app and confirm update prompt from `/api/app/version`

---

## 10. Post-Release Monitoring Checklist

1. Confirm backend health endpoint success every minute
2. Confirm websocket clients connect without error
3. Confirm payment submission and admin approval path works
4. Confirm at least one successful check result write in DB
5. Confirm desktop download link serves expected installer version

---

## 11. Known Risks and Inconsistencies to Track

1. Docker healthcheck in `docker-compose.yml` points to `/health` while API defines `/api/health`
2. Backend `requirements.txt` currently includes duplicate `slowapi==0.1.9`
3. Desktop build/version values can drift across `.iss`, `version.json`, and backend desktop env
4. Worker/API secret mismatch (`WORKER_SECRET`) will silently break remote job polling
5. Hard-coded defaults in config files must be overridden in production env

---

## 12. Command Reference (Quick Copy)

## Local
```powershell
start.bat
stop.bat
cd backend; venv\Scripts\activate; python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
cd frontend; npm install; npm run dev
cd desktop; python main.py
```

## Docker
```bash
docker-compose up --build
docker-compose down
```

## Desktop build
```powershell
cd desktop
.\build.ps1
```

## Fly/Vercel (if configured)
```bash
cd backend
flyctl deploy --app backend-cold-sound-6496

cd ../frontend
vercel deploy --prod
```

## Linux services
```bash
sudo systemctl status tls-backend
sudo systemctl restart tls-backend
sudo journalctl -u tls-backend -f

sudo systemctl status tls-worker
sudo systemctl restart tls-worker
sudo journalctl -u tls-worker -f
```

---

## 13. What This Manual Covers

This recreated manual includes:
- Start/stop for each subsystem
- Test and validation flow before release
- Backend/frontend/desktop update procedure
- Deployment flow and service controls
- Operational risks and consistency checks

If you want, the next step is to split this into:
1. A short operator runbook (daily use)
2. A release engineer checklist
3. A full technical architecture book with screenshots
