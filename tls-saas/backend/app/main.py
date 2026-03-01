"""
TLS Appointment Checker — FastAPI Application Entry Point
Main server that handles all API requests, WebSocket connections, and background checking.
"""

import asyncio
import sys
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from sqlalchemy import select, text

from app.config import settings
from app.database import create_tables, async_session
from app.models import (
    User, Plan, Branch, PlanType, ServiceType, UserCredential,
)
from app.auth import hash_password, decode_token, get_current_user
from app.websocket import ws_manager

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("main")


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
                    "One branch of your choice (El-Sheikh Zayed, Hurghada, New Cairo or Alexandria)",
                    "Individual check using your TLS credentials",
                    "Email & web push notifications",
                    "Real-time dashboard",
                    "60-minute check interval",
                    "Desktop app — PC must stay on",
                ],
                "sort_order": 2,
            },
            {
                "plan_type": PlanType.PREMIUM,
                "display_name": "Premium — Server Monitored",
                "description": "We run monitoring on our server — you don't need to leave your PC on",
                "price_monthly": settings.PRICE_PREMIUM_MONTHLY,
                "features": [
                    "Server-based monitoring — no PC needed",
                    "Legalization & visa branches covered",
                    "Email & web push notifications",
                    "Real-time dashboard",
                    "Priority support",
                    "30-minute check interval",
                ],
                "sort_order": 3,
            },
        ]
        for pd in plans_data:
            result = await db.execute(select(Plan).where(Plan.plan_type == pd["plan_type"]))
            existing_plan = result.scalar_one_or_none()
            if existing_plan:
                # Upsert: update price and features if plan already exists
                existing_plan.price_monthly = pd["price_monthly"]
                existing_plan.features = pd["features"]
                existing_plan.display_name = pd["display_name"]
            else:
                db.add(Plan(**pd))

        # Create branches — Normal + Students legalization + visa for each location
        branches_data = [
            {"name": "Sheikh Zayed - Normal Legalization", "url": "https://legalization-de.tlscontact.com/service/eg/egCAI2de/home", "service_type": ServiceType.LEGALIZATION},
            {"name": "Sheikh Zayed - Students Legalization", "url": "https://legalization-de.tlscontact.com/service/eg/egCAI2de/home", "service_type": ServiceType.LEGALIZATION},
            {"name": "Hurghada - Normal Legalization", "url": "https://legalization-de.tlscontact.com/service/eg/egHRG2de/home", "service_type": ServiceType.LEGALIZATION},
            {"name": "Hurghada - Students Legalization", "url": "https://legalization-de.tlscontact.com/service/eg/egHRG2de/home", "service_type": ServiceType.LEGALIZATION},
            {"name": "New Cairo - Visa", "url": "https://visas-de.tlscontact.com/en-us/country/eg/vac/egHAC2de", "service_type": ServiceType.VISA},
            {"name": "El-Sheikh Zayed - Visa", "url": "https://visas-de.tlscontact.com/en-us/country/eg/vac/egCAI2de", "service_type": ServiceType.VISA},
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
                    "UPDATE plans SET display_name = :n, description = :d, features = :f, price_monthly = :p "
                    "WHERE UPPER(plan_type) = 'LEGALIZATION'"
                ),
                {
                    "n": "Legalization Monitor",
                    "d": "Monitor legalization branches for appointment availability",
                    "f": new_features,
                    "p": settings.PRICE_LEGALIZATION_MONTHLY,
                },
            )
            # Remove all-in-one plan (no longer offered)
            await db.execute(text("DELETE FROM plans WHERE UPPER(plan_type) = 'ALL_IN_ONE'"))
            # Update legalization price to 300
            await db.execute(
                text("UPDATE plans SET price_monthly = :p WHERE UPPER(plan_type) = 'LEGALIZATION'"),
                {"p": settings.PRICE_LEGALIZATION_MONTHLY},
            )
            # Restore visa plan if it was deleted — seed_data will add it back; just ensure price is correct
            await db.execute(
                text("UPDATE plans SET price_monthly = :p WHERE UPPER(plan_type) = 'VISA'"),
                {"p": settings.PRICE_VISA_MONTHLY},
            )
            # Restore visa branches if deactivated
            await db.execute(
                text("UPDATE branches SET is_active = 1 WHERE UPPER(service_type) = 'VISA'")
            )
            await db.commit()
            logger.info("Migration: updated legalization plan name/features/price, restored visa plans/branches")
        except Exception as e:
            logger.warning(f"Plan price migration skipped: {e}")

    # Fix visa branch names and URLs to match original TLS application
    async with async_session() as db:
        try:
            # Rename old incorrect entry and fix its URL
            await db.execute(text(
                "UPDATE branches SET name = 'El-Sheikh Zayed - Visa', "
                "url = 'https://visas-de.tlscontact.com/en-us/country/eg/vac/egCAI2de' "
                "WHERE name = 'Sheikh Zayed - Visa' AND UPPER(service_type) = 'VISA'"
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

    await seed_data()

    # NOTE: Monitoring scheduler is NOT started automatically.
    # Start it manually from the Admin → Monitoring dashboard.
    logger.info("Server ready. Start monitoring manually from Admin → Monitoring.")

    yield

    # Shutdown
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

app.include_router(auth_router)
app.include_router(sub_router)
app.include_router(payment_router)
app.include_router(monitoring_router)
app.include_router(admin_router)
app.include_router(contact_router)
app.include_router(credential_router)
app.include_router(desktop_router)


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
