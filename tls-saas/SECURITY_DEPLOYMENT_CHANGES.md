# Security & Deployment Changes

## What was changed

### 1. License security hardening
- Backend license verification now requires the license key to exist in the database.
- A valid HMAC signature alone is no longer enough to activate a license.
- Hardware mismatch checks were tightened for both verify and deactivate flows.
- Public license recovery was restricted to admin-only access.

### 2. Secret handling cleanup
- Removed hardcoded secrets/passwords from Python source files.
- Moved runtime secrets to environment files.
- Added secure config validation so production startup fails fast when required secrets are missing.
- Added generated values for:
  - `SECRET_KEY`
  - `JWT_SECRET`
  - `ADMIN_PASSWORD`
  - `CREDENTIAL_ENCRYPTION_KEY`
  - `LICENSE_HMAC_SECRET`
  - `WORKER_SECRET`
  - `CREDENTIAL_SECRET`
  - VAPID keys

### 3. Desktop support flow
- Removed direct SMTP sending from the desktop client.
- Desktop support requests now go through the backend contact API.
- Removed the hardcoded developer password from source and made it environment-controlled.

### 4. Environment/deployment readiness
- Updated `.env.example`, `desktop/.env.example`, and `frontend/.env.example`.
- Created/updated local deployment files:
  - `.env`
  - `desktop/.env`
  - `backend/.env.worker`
  - `frontend/.env.local`
- Cleaned `.env.local` to remove the exposed `VERCEL_OIDC_TOKEN`.
- Updated the desktop client default backend URL to the Fly.io production API.
- Removed bundled `.env` from the end-user desktop build so local/admin secrets are not shipped inside the installer.

### 5. Repo hygiene
- Added ignores for worker env files and desktop runtime artifacts.
- Renamed the admin frontend helper to better reflect that license recovery is now admin-only.

---

## Rebuild / redeploy requirements

### Backend
**Rebuild artifact locally:** not required.

**Redeploy required:** yes.

Reason: backend Python source and env handling changed.

### Frontend
**Rebuild required:** yes.

Reason: frontend API helper usage changed and environment values changed.

Suggested command:
```bash
cd frontend
npm run build
```

### Desktop app + installer
**Rebuild required:** yes.

Reason: desktop source changed (`main.py`, `config.py`, `auth_service.py`, env loading, monitoring server, license manager), and the build packaging was updated to stop bundling sensitive `.env` data into the client.

Suggested command:
```powershell
cd desktop
.\build.ps1
```

---

## Important secrets to rotate externally

These values were already present in local env files before cleanup and should be rotated outside the repo/code:

- Gmail SMTP app password
- OpenRouter API key
- Gemini API key
- Any Vercel/Fly secret that was ever exposed locally

---

## Files touched

- `backend/app/api/monitoring_routes.py`
- `backend/app/api/desktop_routes.py`
- `backend/app/config.py`
- `desktop/config.py`
- `desktop/auth_service.py`
- `desktop/main.py`
- `desktop/TLSAppointmentChecker.spec`
- `desktop/monitoring_server.py`
- `desktop/license_manager.py`
- `frontend/src/lib/api.ts`
- `frontend/src/app/admin/licenses/page.tsx`
- `.gitignore`
- `.env.example`
- `desktop/.env.example`
- `frontend/.env.example`
- `SECURITY_DEPLOYMENT_CHANGES.md`

---

## Verification performed

- Python files compile with `py_compile`
- Backend config imports with the new secure env flow
- Desktop monitoring server and license manager import with env loading

---

## Remaining manual deployment steps

1. Rotate exposed third-party credentials.
2. Rebuild the frontend.
3. Rebuild the desktop app and installer.
4. Redeploy backend to Fly.io.
5. Deploy frontend to Vercel.
6. Distribute the newly built desktop installer.