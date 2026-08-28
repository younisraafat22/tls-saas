# TLS Appointment Monitor — SaaS

A web-based SaaS platform that monitors TLS appointment availability and notifies subscribers instantly via email, Telegram, and browser push notifications.

[Live application](https://tls-saas.vercel.app/) · [Backend status](https://backend-cold-sound-6496.fly.dev/health)

> Independent monitoring software. It does not book appointments, guarantee availability, or represent TLScontact or an embassy.

## Engineering highlights

- Two execution modes: a privacy-first Windows worker and a continuously running server worker.
- Real-time dashboard updates over WebSockets with email and browser-push fan-out.
- Encrypted external-service credentials, role-based admin tools, refresh-token authentication, and rate limiting.
- Async FastAPI/SQLAlchemy backend with PostgreSQL production support.
- Docker delivery, responsive PWA frontend, and automated CI checks.

## Architecture

```
┌─────────────┐     ┌──────────────┐     ┌──────────────────┐
│  Next.js 16  │────▶│  FastAPI      │────▶│  Browser Worker   │
│  Frontend    │◀────│  Backend      │◀────│  Browser Checker  │
│  (React/TS)  │ WS  │  (Python)     │     │  (Chromium)       │
└─────────────┘     └──────────────┘     └──────────────────┘
                          │                        │
                    ┌─────┴─────┐          ┌───────┴───────┐
                    │ SQLite/PG │          │ TLS Website   │
                    └───────────┘          └───────────────┘
```

## Features

### User Features
- **Real-time monitoring dashboard** with WebSocket live updates
- **Branch selection** — choose which TLS branches to monitor
- **Multi-channel notifications** — Email, Telegram, Browser Push
- **Subscription management** — view plan, expiry, payment history
- **Profile & settings** — manage account, Telegram setup, notification preferences

### Admin Features
- **Dashboard** — users, revenue, pending payments, system status
- **User management** — search, promote/demote admin, enable/disable
- **Payment approval** — approve/reject Vodafone Cash & InstaPay payments
- **Monitoring control** — start/stop scheduler, trigger manual checks, manage branches
- **Service accounts** — manage TLS login credentials per branch
- **System settings** — check interval, payment details, maintenance mode

### Pricing Tiers
| Plan | Price | Monitors |
|------|-------|----------|
| Legalization Monitor | 200 EGP/mo | Legalization branches |
| Visa Monitor | 200 EGP/mo | Visa branches |
| All-in-One | 300 EGP/mo | All branches |

## Tech Stack

| Layer | Technology |
|-------|------------|
| Frontend | Next.js 16, React 19, TypeScript, Tailwind CSS, Framer Motion |
| Backend | FastAPI, Python 3.11, async SQLAlchemy, Pydantic |
| Database | SQLite (dev) / PostgreSQL (prod) |
| Browser | Playwright (Chromium) |
| Scheduler | APScheduler |
| Auth | JWT (access + refresh tokens), bcrypt |
| Notifications | SMTP Email, Telegram Bot API, Web Push (VAPID) |

## Quick Start

### 1. Clone & Configure

```bash
cp .env.example .env
# Edit .env with your settings (SMTP, Telegram bot token, etc.)
```

### 2. Backend Setup

```bash
cd backend
python -m venv venv
venv\Scripts\activate        # Windows
# source venv/bin/activate   # Linux/Mac

pip install -r requirements.txt
playwright install chromium

# Run the server
uvicorn app.main:app --reload --port 8000
```

On first run, the backend automatically:
- Creates the database tables
- Seeds the admin user (from `ADMIN_EMAIL` / `ADMIN_PASSWORD` in `.env`)
- Creates the 3 subscription plans
- Creates all TLS branches

### 3. Frontend Setup

```bash
cd frontend
npm install
npm run dev
```

Open http://localhost:3000

### 4. Docker (Alternative)

```bash
docker-compose up --build
```

## Project Structure

```
tls-saas/
├── backend/
│   ├── app/
│   │   ├── main.py              # FastAPI app, lifespan, seed data
│   │   ├── config.py            # Pydantic Settings (env vars)
│   │   ├── database.py          # Async SQLAlchemy engine
│   │   ├── models.py            # 11 ORM models
│   │   ├── schemas.py           # Pydantic request/response schemas
│   │   ├── auth.py              # JWT utilities & dependencies
│   │   ├── websocket.py         # WebSocket connection manager
│   │   ├── api/
│   │   │   ├── auth_routes.py       # Register, login, profile
│   │   │   ├── subscription_routes.py  # Plans, branches, monitoring
│   │   │   ├── payment_routes.py    # Submit & track payments
│   │   │   ├── monitoring_routes.py # Status, results, notification history
│   │   │   └── admin_routes.py      # Full admin API
│   │   └── services/
│   │       ├── checker.py           # Playwright TLS checker
│   │       ├── email_service.py     # SMTP email with HTML templates
│   │       ├── telegram_service.py  # Telegram Bot API
│   │       └── scheduler.py        # APScheduler coordination
│   ├── requirements.txt
│   └── Dockerfile
├── frontend/
│   ├── src/
│   │   ├── app/
│   │   │   ├── page.tsx             # Animated landing page
│   │   │   ├── login/page.tsx       # Login
│   │   │   ├── register/page.tsx    # Registration
│   │   │   ├── dashboard/           # User dashboard (5 pages)
│   │   │   └── admin/               # Admin panel (5 pages)
│   │   ├── lib/
│   │   │   ├── api.ts               # API client with auto-refresh
│   │   │   └── auth-context.tsx     # Auth React context
│   │   └── hooks/
│   │       └── useWebSocket.ts      # WebSocket with auto-reconnect
│   ├── package.json
│   ├── tailwind.config.ts
│   └── Dockerfile
├── docker-compose.yml
├── .env.example
└── README.md
```

## How It Works

1. **Shared checking model** — One Playwright browser per branch checks TLS for ALL subscribers. With 6 branches, only 6 browser instances run regardless of user count.

2. **Scheduler** runs every N minutes (configurable), checking each active branch using service account credentials.

3. **When slots are found**, all active subscribers monitoring that branch are notified simultaneously via their configured channels (email, Telegram, push).

4. **WebSocket** delivers real-time updates to connected dashboards instantly.

5. **Payment flow**: User selects plan → sends money via Vodafone Cash/InstaPay → submits reference → admin approves → subscription activates automatically.

## API Endpoints

### Auth
- `POST /api/auth/register` — Create account
- `POST /api/auth/login` — Get JWT tokens  
- `POST /api/auth/refresh` — Refresh access token
- `GET /api/auth/me` — Current user profile
- `PATCH /api/auth/me` — Update profile

### Subscriptions
- `GET /api/subscriptions/plans` — List plans
- `GET /api/subscriptions/branches` — List branches
- `POST /api/subscriptions/branches/monitor` — Set monitored branches

### Payments
- `POST /api/payments/submit` — Submit payment proof
- `GET /api/payments/my` — My payment history

### Monitoring
- `GET /api/monitoring/status` — Current monitoring status
- `GET /api/monitoring/results` — Check results
- `GET /api/monitoring/notifications` — Notification history

### Admin
- `GET /api/admin/dashboard` — Dashboard stats
- `GET/PATCH /api/admin/users` — User management
- `GET/POST /api/admin/payments` — Payment approval
- `POST /api/admin/scheduler/start|stop` — Scheduler control  
- `POST /api/admin/check/trigger` — Manual check
- Full CRUD for branches, service accounts, settings

## Environment Variables

See [.env.example](.env.example) for all configuration options.

### Required for Production
- `SECRET_KEY` — Random string for JWT signing
- `ADMIN_EMAIL` / `ADMIN_PASSWORD` — First admin account
- `SMTP_*` — Email notification settings
- `TELEGRAM_BOT_TOKEN` — Telegram notifications
- `CREDENTIAL_ENCRYPTION_KEY` — Fernet key for encrypting TLS credentials

### Generate Fernet Key
```python
from cryptography.fernet import Fernet
print(Fernet.generate_key().decode())
```

## License

Proprietary — All rights reserved.
