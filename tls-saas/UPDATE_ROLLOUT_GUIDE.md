# Update Rollout Guide (Installed Desktop Users + Website)

This guide explains how to ship updates safely for:
- Small updates (login flow, validation, backend/frontend fixes)
- Large updates (desktop UI/logic changes, security/protocol changes)

It is written for this repo and current deployment setup:
- Backend: Fly.io (`backend-cold-sound-6496`)
- Frontend: Vercel (`tls-saas.vercel.app`)
- Desktop installer: GitHub Releases

---

## 1) How updates currently work

### Website users
- Frontend and backend are live-deployed.
- Users get updates instantly on next page load/refresh.

### Installed desktop users
- Desktop app checks backend endpoint:
  - `GET /api/app/version`
- Backend returns:
  - `DESKTOP_APP_VERSION`
  - `DESKTOP_DOWNLOAD_URL`
  - `DESKTOP_RELEASE_NOTES`
  - `DESKTOP_FORCE_UPDATE`
- If remote version is newer, desktop prompts user to update and downloads installer URL.

Important: Desktop updates are installer-based. If code changes are inside desktop app binaries, users need a new installer release (or in-app updater flow) to receive them.

---

## 2) Decide update type first

## Type A: Server-only (small)
Examples:
- Login/API fixes
- Payment/admin logic fixes
- Frontend wording/layout tweaks
- Security fixes that do not break old desktop request format

User impact:
- Website users: instant after deploy
- Desktop users: usually instant if behavior depends on backend only
- No installer required

## Type B: Desktop code change (medium/large)
Examples:
- Desktop UI redesign
- Local checker flow changes
- Local storage/config behavior changes

User impact:
- Existing installed users do not get new code until they update installer
- Requires new desktop build + release asset

## Type C: Breaking protocol/security change (high risk)
Examples:
- Changing required request fields in license/auth endpoints
- Tightening validation that old desktop builds do not send

User impact:
- Can lock out installed users if backend is updated first without compatibility

Rule:
- Always add compatibility window first, then migrate users, then enforce strict mode.

---

## 3) Versioning policy (recommended)

Use SemVer:
- Patch (`1.0.x`): bugfix, safe small behavior change
- Minor (`1.x.0`): new features, non-breaking changes
- Major (`x.0.0`): breaking changes

For every desktop release, keep these in sync:
- `desktop/main.py` (`VERSION`)
- `desktop/installer_setup.iss` (`MyAppVersion`, output filename)
- `desktop/version.json` (`version`, notes)
- Backend env: `DESKTOP_APP_VERSION`, `DESKTOP_DOWNLOAD_URL`, `DESKTOP_RELEASE_NOTES`

---

## 4) Small update runbook (Type A)

Use this for login flow fixes, backend/frontend bugs, non-breaking API changes.

1. Implement and test locally.
2. Deploy backend:
   - `cd backend`
   - `flyctl deploy --app backend-cold-sound-6496`
3. Deploy frontend:
   - `vercel redeploy tls-saas.vercel.app`
   - or `vercel deploy --prod` from the correct linked root
4. Smoke test production:
   - `https://backend-cold-sound-6496.fly.dev/api/health`
   - `https://tls-saas.vercel.app/login`
   - `https://tls-saas.vercel.app/api/backend-url`
5. Do not bump desktop version unless desktop binary changed.

---

## 5) Desktop update runbook (Type B)

Use this when desktop code changed (UI/logic/local features).

1. Bump version across desktop files.
2. Clean rebuild desktop:
   - `cd desktop`
   - `.\build.ps1`
3. Verify installer exists in:
   - `desktop/installer_output/`
4. Create/update GitHub Release:
   - Tag example: `v1.0.1`
   - Upload installer EXE
5. Update backend desktop release env values:
   - `DESKTOP_APP_VERSION=1.0.1`
   - `DESKTOP_DOWNLOAD_URL=<new release asset url>`
   - `DESKTOP_RELEASE_NOTES=<short notes>`
   - `DESKTOP_FORCE_UPDATE=false` (default recommended)
6. Redeploy backend (`flyctl deploy ...`).
7. Verify update prompt in installed old app:
   - App start should detect newer version from `/api/app/version`
   - Download URL should point to new installer

---

## 6) Breaking/security update runbook (Type C)

Use this when backend and desktop protocol changes together.

### Phase 1: Compatibility release
1. Backend accepts both old and new request formats.
2. Release new desktop installer with new format.
3. Set backend desktop version to new installer URL.
4. Keep `DESKTOP_FORCE_UPDATE=false`.
5. Monitor adoption.

### Phase 2: Enforcement
1. When adoption is high, enable strict checks in backend.
2. Optionally set:
   - `DESKTOP_FORCE_UPDATE=true`
3. Keep rollback plan ready.

### Phase 3: Cleanup
1. Remove legacy compatibility logic after stable period.

---

## 7) Rollback plan (must-have)

If a release breaks users:

1. Backend rollback (fastest):
   - Redeploy previous backend commit.
2. Desktop rollback:
   - Set backend env to previous known-good installer:
     - `DESKTOP_APP_VERSION`
     - `DESKTOP_DOWNLOAD_URL`
     - `DESKTOP_RELEASE_NOTES`
     - `DESKTOP_FORCE_UPDATE=false`
3. Frontend rollback:
   - Redeploy previous good Vercel deployment.
4. Communicate to users:
   - "Issue identified, rollback completed, restart app."

---

## 8) Communication templates

## Small update
"We deployed service improvements. Please refresh website or restart app."

## Optional desktop update
"A new desktop version is available with improvements. Update from in-app prompt."

## Mandatory security update
"A security update is required. Please install the latest version to continue."

---

## 9) Pre-release checklist

- Backend health endpoint returns OK.
- Frontend points to correct backend URL.
- Desktop installer built from clean `build/dist`.
- GitHub release URL works and downloads installer.
- `/api/app/version` returns expected version + URL.
- Existing installed app can still activate/verify license.
- Login flow tested on website and desktop.

---

## 10) Operational guardrails

- Never ship backend strict validation changes without compatibility when old desktop clients are active.
- Keep at least one previous installer URL ready for rollback.
- Avoid version drift across desktop files and backend env.
- Deploy backend first when frontend depends on new API behavior.
- For risky changes, rollout in stages and monitor logs before enforcing.

