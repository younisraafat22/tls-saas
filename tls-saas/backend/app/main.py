"""
TLS Appointment Checker — FastAPI Application Entry Point
Main server that handles all API requests, WebSocket connections, and background checking.
"""

import asyncio
import sys
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Depends, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

limiter = Limiter(key_func=get_remote_address)
from sqlalchemy import select, text

from app.config import settings
from app.database import create_tables, async_session
from app.models import (
    AppRating, AppDownload, FoundAppointment,
    User, Plan, Branch, PlanType, ServiceType, UserCredential, SystemSetting,
)
from app.auth import hash_password, decode_token, get_current_user
from app.websocket import ws_manager

from collections import deque as _deque

# In-memory system log buffer — captures all Python log output.
# Used as fallback for the admin system-logs panel when journalctl is unavailable (e.g. Fly.io).
_system_log_buffer: _deque = _deque(maxlen=500)

class _MemoryLogHandler(logging.Handler):
    def emit(self, record):
        try:
            _system_log_buffer.append(self.format(record))
        except Exception:
            pass

def get_system_log_lines(n: int = 200) -> list:
    lines = list(_system_log_buffer)
    return lines[-n:] if len(lines) > n else lines

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("main")

# Attach memory handler to root logger so all app logs are captured
_mem_handler = _MemoryLogHandler()
_mem_handler.setFormatter(logging.Formatter(
    "%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%S",
))
logging.getLogger().addHandler(_mem_handler)


async def seed_data():
    """Seed initial data: admin user, plans, branches."""
    async with async_session() as db:
        # Create admin user if not exists
        result = await db.execute(select(User).where(User.email == settings.ADMIN_EMAIL))
        if not result.scalar_one_or_none():
            admin = User(
                email=settings.ADMIN_EMAIL,
                password_hash=hash_password(settings.ADMIN_PASSWORD),
                full_name="Admin",
                is_admin=True,
                is_active=True,
            )
            db.add(admin)
            logger.info(f"Admin user created: {settings.ADMIN_EMAIL}")

        # Create / upsert plans — legalization + visa + premium
        plans_data = [
            {
                "plan_type": PlanType.LEGALIZATION,
                "display_name": "Legalization Monitor",
                "description": "Monitor all legalization branches for appointment availability",
                "price_monthly": settings.PRICE_LEGALIZATION_MONTHLY,
                "features": [
                    "One branch of your choice (Sheikh Zayed or Hurghada)",
                    "Email & web push notifications",
                    "Real-time dashboard",
                    "60-minute check interval",
                    "No TLS credentials needed",
                    "Desktop app — PC must stay on",
                ],
                "sort_order": 1,
            },
            {
                "plan_type": PlanType.VISA,
                "display_name": "Visa Monitor",
                "description": "Monitor your personal TLS visa appointment — individual per-user check",
                "price_monthly": settings.PRICE_VISA_MONTHLY,
                "features": [
                    "One branch of your choice (Sheikh Zayed, Hurghada, New Cairo or Alexandria)",
                    "Individual check using your TLS credentials",
                    "Email & web push notifications",
                    "Real-time dashboard",
                    "60-minute check interval",
                    "Desktop app — PC must stay on",
                ],
                "sort_order": 2,
            },
            {
                "plan_type": PlanType.ALL_IN_ONE,
                "display_name": "Legalization + Visa",
                "description": "Monitor both legalization and visa branches — switch anytime in the desktop app",
                "price_monthly": settings.PRICE_ALL_IN_ONE_MONTHLY,
                "features": [
                    "Both legalization & visa monitoring",
                    "Switch service type anytime",
                    "All branches available",
                    "Email & web push notifications",
                    "Real-time dashboard",
                    "60-minute check interval",
                    "Desktop app — PC must stay on",
                ],
                "sort_order": 3,
            },
            {
                "plan_type": PlanType.PREMIUM,
                "display_name": "Premium — Server Monitored",
                "description": "We run monitoring on our server — you don't need to leave your PC on",
                "price_monthly": settings.PRICE_PREMIUM_MONTHLY,
                "features": [
                    "Server-based monitoring — no PC needed",
                    "1 service: legalization or visa (your choice)",
                    "Email & web push notifications",
                    "Real-time dashboard",
                    "Priority support",
                    "30-minute check interval",
                ],
                "sort_order": 4,
            },
        ]
        for pd in plans_data:
            result = await db.execute(select(Plan).where(Plan.plan_type == pd["plan_type"]))
            existing_plan = result.scalar_one_or_none()
            if not existing_plan:
                db.add(Plan(**pd))

        # Create branches — 2 legalization + 4 visa branches (Cairo uses "Sheikh Zayed" for both services; suffix disambiguates in DB)
        branches_data = [
            {"name": "Sheikh Zayed - Legalization", "url": "https://legalization-de.tlscontact.com/service/eg/egCAI2de/home", "service_type": ServiceType.LEGALIZATION},
            {"name": "Hurghada - Legalization", "url": "https://legalization-de.tlscontact.com/service/eg/egHRG2de/home", "service_type": ServiceType.LEGALIZATION},
            {"name": "New Cairo - Visa", "url": "https://visas-de.tlscontact.com/en-us/country/eg/vac/egHAC2de", "service_type": ServiceType.VISA},
            {"name": "Sheikh Zayed - Visa", "url": "https://visas-de.tlscontact.com/en-us/country/eg/vac/egCAI2de", "service_type": ServiceType.VISA},
            {"name": "Alexandria - Visa", "url": "https://visas-de.tlscontact.com/en-us/country/eg/vac/egALY2de", "service_type": ServiceType.VISA},
            {"name": "Hurghada - Visa", "url": "https://visas-de.tlscontact.com/en-us/country/eg/vac/egHRG2de", "service_type": ServiceType.VISA},
        ]
        for bd in branches_data:
            exists = await db.execute(
                select(Branch).where(Branch.name == bd["name"], Branch.service_type == bd["service_type"])
            )
            if not exists.scalar_one_or_none():
                db.add(Branch(**bd))

        await db.commit()
        logger.info("Seed data applied")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown events."""
    logger.info(f"Starting {settings.APP_NAME} v{settings.APP_VERSION}")

    # Create tables and seed data
    await create_tables()

    # Run lightweight migrations for new columns
    async with async_session() as db:
        try:
            await db.execute(text("ALTER TABLE check_results ADD COLUMN user_id INTEGER REFERENCES users(id)"))
            await db.commit()
            logger.info("Migration: added user_id to check_results table")
        except Exception:
            pass  # Column already exists

    async with async_session() as db:
        try:
            await db.execute(text("ALTER TABLE payments ADD COLUMN branch_id INTEGER REFERENCES branches(id)"))
            await db.commit()
            logger.info("Migration: added branch_id to payments table")
        except Exception:
            pass  # Column already exists

    async with async_session() as db:
        try:
            await db.execute(text("ALTER TABLE payments ADD COLUMN screenshot_data TEXT"))
            await db.commit()
            logger.info("Migration: added screenshot_data to payments table")
        except Exception:
            pass  # Column already exists

    # New desktop-app payment columns
    desktop_migrations = [
        ("hardware_id", "VARCHAR(100)"),
        ("plan_key", "VARCHAR(50)"),
        ("submitter_name", "VARCHAR(255)"),
        ("submitter_email", "VARCHAR(255)"),
        ("license_key", "VARCHAR(255)"),
    ]
    async with async_session() as db:
        for col, col_type in desktop_migrations:
            try:
                await db.execute(text(f"ALTER TABLE payments ADD COLUMN {col} {col_type}"))
                await db.commit()
                logger.info(f"Migration: added {col} to payments table")
            except Exception:
                pass  # Column already exists

    # Add source column to check_results (desktop vs server)
    async with async_session() as db:
        try:
            await db.execute(text("ALTER TABLE check_results ADD COLUMN source VARCHAR(20) DEFAULT 'server'"))
            await db.commit()
            logger.info("Migration: added source column to check_results")
        except Exception:
            pass  # Column already exists

    # Add user_name to app_ratings for named review attribution
    async with async_session() as db:
        try:
            await db.execute(text("ALTER TABLE app_ratings ADD COLUMN user_name VARCHAR(255)"))
            await db.commit()
            logger.info("Migration: added user_name to app_ratings")
        except Exception:
            pass  # Column already exists

    # Create user_credentials table if not exists (handled by create_tables, but add migration safety)
    async with async_session() as db:
        try:
            await db.execute(text("""
                CREATE TABLE IF NOT EXISTS user_credentials (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                    service_type VARCHAR NOT NULL,
                    email_encrypted TEXT NOT NULL,
                    password_encrypted TEXT NOT NULL,
                    is_active BOOLEAN DEFAULT 1,
                    created_at DATETIME,
                    last_used_at DATETIME,
                    last_error TEXT DEFAULT '',
                    UNIQUE(user_id, service_type)
                )
            """))
            await db.commit()
            logger.info("Migration: ensured user_credentials table exists")
        except Exception:
            pass

    # Create admin notifications table
    async with async_session() as db:
        try:
            await db.execute(text("""
                CREATE TABLE IF NOT EXISTS admin_notifications (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    category VARCHAR(50) NOT NULL DEFAULT 'general',
                    event_type VARCHAR(100) NOT NULL DEFAULT 'event',
                    title VARCHAR(255) NOT NULL DEFAULT '',
                    message TEXT NOT NULL DEFAULT '',
                    payload JSON,
                    is_read BOOLEAN NOT NULL DEFAULT 0,
                    created_at DATETIME,
                    read_at DATETIME
                )
            """))
            await db.commit()
            logger.info("Migration: ensured admin_notifications table exists")
        except Exception:
            pass

    # Create support inquiries table
    async with async_session() as db:
        try:
            await db.execute(text("""
                CREATE TABLE IF NOT EXISTS support_inquiries (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name VARCHAR(255) NOT NULL DEFAULT '',
                    email VARCHAR(255) NOT NULL DEFAULT '',
                    subject VARCHAR(255) NOT NULL DEFAULT '',
                    message TEXT NOT NULL DEFAULT '',
                    source VARCHAR(20) NOT NULL DEFAULT 'website',
                    locale VARCHAR(10) NOT NULL DEFAULT 'en',
                    status VARCHAR(20) NOT NULL DEFAULT 'new',
                    admin_reply TEXT,
                    replied_at DATETIME,
                    replied_by INTEGER REFERENCES users(id),
                    created_at DATETIME
                )
            """))
            await db.commit()
            logger.info("Migration: ensured support_inquiries table exists")
        except Exception:
            pass

    # Rename legalization branches to include service label
    async with async_session() as db:
        try:
            await db.execute(text(
                "UPDATE branches SET name = 'Sheikh Zayed (Legalization)' "
                "WHERE name = 'Sheikh Zayed' AND service_type = 'legalization'"
            ))
            await db.execute(text(
                "UPDATE branches SET name = 'Hurghada (Legalization)' "
                "WHERE name = 'Hurghada' AND service_type = 'legalization'"
            ))
            await db.commit()
            logger.info("Migration: updated legalization branch display names")
        except Exception:
            pass

    # Remove any duplicate bare-name legalization branches left over from old seeds
    async with async_session() as db:
        try:
            await db.execute(text(
                "DELETE FROM branches WHERE name IN ('Sheikh Zayed', 'Hurghada')"
            ))
            await db.commit()
            logger.info("Migration: removed duplicate legalization branch entries")
        except Exception:
            pass

    # Deactivate old generic branch names now replaced by Normal/Students variants
    async with async_session() as db:
        try:
            await db.execute(text(
                "UPDATE branches SET is_active = 0 "
                "WHERE name IN ('Sheikh Zayed (Legalization)', 'Hurghada (Legalization)')"
            ))
            await db.commit()
            logger.info("Migration: deactivated old generic legalization branches")
        except Exception:
            pass

    # Update plan prices and remove visa plan/branches
    async with async_session() as db:
        try:
            from app.models import PlanType as _PT
            import json as _json
            # Update legalization plan name, description, features and price
            new_features = _json.dumps([
                "Sheikh Zayed & Hurghada branches",
                "Individual appointment monitoring",
                "Email notifications",
                "Web push notifications",
                "Real-time dashboard",
            ])
            await db.execute(
                text(
                    "UPDATE plans SET display_name = :n, description = :d, features = :f "
                    "WHERE UPPER(plan_type) = 'LEGALIZATION'"
                ),
                {
                    "n": "Legalization Monitor",
                    "d": "Monitor legalization branches for appointment availability",
                    "f": new_features,
                },
            )
            # Ensure all-in-one plan price is up to date (Removed to prevent overwriting admin custom prices)
            # Update legalization price to 300 (Removed to prevent overwriting admin custom prices)
            # Restore visa plan if it was deleted — seed_data will add it back; just ensure price is correct (Removed)
            # Restore visa branches if deactivated
            await db.execute(
                text("UPDATE branches SET is_active = 1 WHERE UPPER(service_type) = 'VISA'")
            )
            await db.commit()
            logger.info("Migration: updated legalization plan name, restored visa branches")
        except Exception as e:
            logger.warning(f"Plan price migration skipped: {e}")

    # Fix visa branch names and URLs to match original TLS application
    async with async_session() as db:
        try:
            # Cairo visa: same "Sheikh Zayed" naming as legalization; fix URL if needed
            await db.execute(text(
                "UPDATE branches SET name = 'Sheikh Zayed - Visa', "
                "url = 'https://visas-de.tlscontact.com/en-us/country/eg/vac/egCAI2de' "
                "WHERE UPPER(service_type) = 'VISA' AND url LIKE '%visas-de.tlscontact.com%' AND url LIKE '%egCAI2de%' "
                "AND (name IN ('El-Sheikh Zayed - Visa', 'El-Sheikh Zayed', 'Sheikh Zayed') OR name = 'Sheikh Zayed - Visa')"
            ))
            # Fix Hurghada visa URL
            await db.execute(text(
                "UPDATE branches SET "
                "url = 'https://visas-de.tlscontact.com/en-us/country/eg/vac/egHRG2de' "
                "WHERE name = 'Hurghada - Visa' AND UPPER(service_type) = 'VISA'"
            ))
            # Fix any rows incorrectly inserted with lowercase service_type (delete duplicates — seed re-inserts correct ones)
            await db.execute(text(
                "DELETE FROM branches WHERE UPPER(service_type) = 'VISA' AND service_type != 'VISA'"
            ))
            # Insert New Cairo visa branch if missing
            existing_nc = await db.execute(text(
                "SELECT id FROM branches WHERE name = 'New Cairo - Visa'"
            ))
            if not existing_nc.scalar_one_or_none():
                await db.execute(text(
                    "INSERT INTO branches (name, url, service_type, is_active) VALUES "
                    "('New Cairo - Visa', 'https://visas-de.tlscontact.com/en-us/country/eg/vac/egHAC2de', 'VISA', 1)"
                ))
            # Insert Alexandria visa branch if missing
            existing_alx = await db.execute(text(
                "SELECT id FROM branches WHERE name = 'Alexandria - Visa'"
            ))
            if not existing_alx.scalar_one_or_none():
                await db.execute(text(
                    "INSERT INTO branches (name, url, service_type, is_active) VALUES "
                    "('Alexandria - Visa', 'https://visas-de.tlscontact.com/en-us/country/eg/vac/egALY2de', 'VISA', 1)"
                ))
            # Insert Hurghada visa branch if missing
            existing_hrg = await db.execute(text(
                "SELECT id FROM branches WHERE name = 'Hurghada - Visa'"
            ))
            if not existing_hrg.scalar_one_or_none():
                await db.execute(text(
                    "INSERT INTO branches (name, url, service_type, is_active) VALUES "
                    "('Hurghada - Visa', 'https://visas-de.tlscontact.com/en-us/country/eg/vac/egHRG2de', 'VISA', 1)"
                ))
            await db.commit()
            logger.info("Migration: fixed visa branch names/URLs, added New Cairo & Alexandria")
        except Exception as e:
            logger.warning(f"Visa branch fix migration skipped: {e}")

    # Update existing admin user email/password to match current ADMIN_EMAIL setting
    async with async_session() as db:
        try:
            from app.auth import hash_password as _hp
            result = await db.execute(select(User).where(User.is_admin == True))
            admin_rows = result.scalars().all()
            for u in admin_rows:
                if u.email != settings.ADMIN_EMAIL:
                    # Keep only the canonical admin row; delete stale duplicates
                    old_email = u.email
                    u.email = settings.ADMIN_EMAIL
                    u.password_hash = _hp(settings.ADMIN_PASSWORD)
                    await db.commit()
                    logger.info(f"Migration: updated admin email {old_email} → {settings.ADMIN_EMAIL}")
                    break  # Only update the first admin found
        except Exception as e:
            logger.warning(f"Admin email migration skipped: {e}")

    # Rename 'Normal Legalization' branches — drop the 'Normal' qualifier (skip if already done)
    async with async_session() as db:
        try:
            result = await db.execute(text(
                "SELECT COUNT(*) FROM branches WHERE name LIKE '% - Normal Legalization'"
            ))
            count = result.scalar()
            if count and count > 0:
                # If the renamed target already exists, just delete the old duplicate rows
                await db.execute(text(
                    "DELETE FROM branches WHERE name LIKE '% - Normal Legalization' "
                    "AND EXISTS ("
                    "  SELECT 1 FROM branches b2 WHERE b2.name = REPLACE(branches.name, ' - Normal Legalization', ' - Legalization')"
                    "  AND b2.service_type = branches.service_type"
                    ")"
                ))
                # Rename any remaining rows where target doesn't exist yet
                await db.execute(text(
                    "UPDATE branches SET name = REPLACE(name, ' - Normal Legalization', ' - Legalization') "
                    "WHERE name LIKE '% - Normal Legalization' AND UPPER(service_type) = 'LEGALIZATION'"
                ))
                await db.commit()
                logger.info("Migration: cleaned up 'Normal Legalization' branch duplicates")
        except Exception as e:
            logger.warning(f"Branch rename migration skipped: {e}")

    # Deactivate sub-type legalization branches (Students / Normal) — only 2 plain legalization branches should be active
    async with async_session() as db:
        try:
            await db.execute(text(
                "UPDATE branches SET is_active = 0 "
                "WHERE UPPER(service_type) = 'LEGALIZATION' "
                "AND (name LIKE '% - Students Legalization' OR name LIKE '% - Normal Legalization')"
            ))
            await db.commit()
            logger.info("Migration: deactivated sub-type legalization branches (Students/Normal)")
        except Exception as e:
            logger.warning(f"Legalization sub-type deactivation migration skipped: {e}")

    # Unify Cairo visa naming with legalization (Sheikh Zayed); restore suffixed names if a prior migration shortened them
    async with async_session() as db:
        try:
            await db.execute(text(
                "UPDATE branches SET name = 'Sheikh Zayed - Visa' "
                "WHERE UPPER(service_type) = 'VISA' AND url LIKE '%visas-de.tlscontact.com%' AND url LIKE '%egCAI2de%' "
                "AND name IN ('El-Sheikh Zayed - Visa', 'El-Sheikh Zayed', 'Sheikh Zayed')"
            ))
            await db.execute(text(
                "UPDATE branches SET name = 'Sheikh Zayed - Legalization' "
                "WHERE UPPER(service_type) = 'LEGALIZATION' AND url LIKE '%legalization-de.tlscontact.com%' AND url LIKE '%egCAI2de%' "
                "AND name IN ('Sheikh Zayed', 'Sheikh Zayed (Legalization)')"
            ))
            await db.execute(text(
                "UPDATE branches SET name = 'Hurghada - Legalization' "
                "WHERE name = 'Hurghada' AND UPPER(service_type) = 'LEGALIZATION'"
            ))
            await db.execute(text(
                "UPDATE branches SET name = 'Hurghada - Visa' "
                "WHERE name = 'Hurghada' AND UPPER(service_type) = 'VISA'"
            ))
            await db.execute(text(
                "UPDATE branches SET name = 'New Cairo - Visa' "
                "WHERE name = 'New Cairo' AND UPPER(service_type) = 'VISA'"
            ))
            await db.execute(text(
                "UPDATE branches SET name = 'Alexandria - Visa' "
                "WHERE name = 'Alexandria' AND UPPER(service_type) = 'VISA'"
            ))
            await db.commit()
            logger.info("Migration: Sheikh Zayed naming for Cairo visa+legalization; restored suffixed branch names where needed")
        except Exception as e:
            logger.warning(f"Branch naming migration skipped: {e}")

    await seed_data()

    # Deactivate sub-type legalization branches (Students / Normal) — only 2 plain legalization branches should be active
    # NOTE: runs AFTER seed_data so seed cannot re-activate them
    async with async_session() as db:
        try:
            await db.execute(text(
                "UPDATE branches SET is_active = 0 "
                "WHERE UPPER(service_type) = 'LEGALIZATION' "
                "AND name NOT IN ('Sheikh Zayed - Legalization', 'Hurghada - Legalization')"
            ))
            await db.commit()
            logger.info("Migration: ensured only 2 active legalization branches")
        except Exception as e:
            logger.warning(f"Legalization branch cleanup migration skipped: {e}")

    # In WORKER_MODE (Fly.io cloud deployment) the scheduler is disabled.
    # Monitoring is handled by the laptop worker polling /api/worker/jobs.
    import os as _os
    _worker_mode = _os.environ.get("WORKER_MODE", "false").lower() == "true"

    if _worker_mode:
        logger.info("WORKER_MODE=true — scheduler disabled. Laptop worker handles monitoring.")
    else:
        # Resume scheduler if it was running before restart (persisted in system settings)
        from app.services.scheduler import scheduler_service
        async with async_session() as db:
            interval_r = await db.execute(
                select(SystemSetting).where(SystemSetting.key == "check_interval_minutes")
            )
            interval_setting = interval_r.scalar_one_or_none()
            if interval_setting:
                try:
                    settings.CHECK_INTERVAL_MINUTES = max(5, int(interval_setting.value))
                    logger.info(f"Custom check interval: {settings.CHECK_INTERVAL_MINUTES} min")
                except (ValueError, TypeError):
                    pass

            resume_r = await db.execute(
                select(SystemSetting).where(SystemSetting.key == "scheduler_running")
            )
            resume_setting = resume_r.scalar_one_or_none()
            if resume_setting and resume_setting.value == "true":
                scheduler_service.start()
                logger.info(f"Server ready. Monitoring scheduler auto-resumed (interval: {settings.CHECK_INTERVAL_MINUTES} min).")
            else:
                logger.info("Server ready. Start monitoring manually from Admin → Monitoring.")

    yield

    # Shutdown
    if not _worker_mode:
        from app.services.scheduler import scheduler_service
        scheduler_service.stop()
        from app.services.checker import tls_checker
        await tls_checker.close()
    logger.info("Shutdown complete")


# ── FastAPI App ──────────────────────────────────────────────────────

app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    lifespan=lifespan,
)

# CORS
_origins = settings.allowed_origins_list
app.add_middleware(
    CORSMiddleware,
    allow_origins=_origins if _origins != ["*"] else [],
    allow_origin_regex=".*" if _origins == ["*"] else None,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API routers
from app.api.auth_routes import router as auth_router
from app.api.subscription_routes import router as sub_router
from app.api.payment_routes import router as payment_router
from app.api.monitoring_routes import router as monitoring_router
from app.api.admin_routes import router as admin_router
from app.api.contact_routes import router as contact_router
from app.api.credential_routes import router as credential_router
from app.api.desktop_routes import router as desktop_router
from app.api.metrics_routes import router as metrics_router

app.include_router(auth_router)
app.include_router(sub_router)
app.include_router(payment_router)
app.include_router(monitoring_router)
app.include_router(admin_router)
app.include_router(contact_router)
app.include_router(credential_router)
app.include_router(desktop_router)
app.include_router(metrics_router)


# ── Health Check ─────────────────────────────────────────────────────

@app.get("/api/health")
async def health():
    return {
        "status": "ok",
        "version": settings.APP_VERSION,
        "app": settings.APP_NAME,
    }


# ── User WebSocket ──────────────────────────────────────────────────

@app.websocket("/ws/user")
async def user_websocket(websocket: WebSocket):
    """WebSocket for user dashboard — real-time check results & notifications."""
    token = websocket.query_params.get("token", "")
    try:
        payload = decode_token(token)
        user_id = int(payload.get("sub", 0))
    except Exception:
        await websocket.close(code=4001)
        return

    await ws_manager.connect_user(websocket, user_id)
    try:
        while True:
            # Keep connection alive, handle pings
            data = await websocket.receive_text()
            if data == "ping":
                await websocket.send_text("pong")
    except WebSocketDisconnect:
        await ws_manager.disconnect_user(websocket, user_id)


# ── Run ──────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
