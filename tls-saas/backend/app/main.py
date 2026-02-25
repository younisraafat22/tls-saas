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
    User, Plan, Branch, PlanType, ServiceType,
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

        # Create plans if not exist — legalization only
        plans_data = [
            {
                "plan_type": PlanType.LEGALIZATION,
                "display_name": "Legalization Monitor",
                "description": "Monitor all legalization branches for appointment availability",
                "price_monthly": settings.PRICE_LEGALIZATION_MONTHLY,
                "features": [
                    "Sheikh Zayed & Hurghada branches",
                    "Email notifications",
                    "Web push notifications",
                    "Real-time dashboard",
                    "30-minute check interval",
                ],
                "sort_order": 1,
            },
        ]
        for pd in plans_data:
            exists = await db.execute(select(Plan).where(Plan.plan_type == pd["plan_type"]))
            if not exists.scalar_one_or_none():
                db.add(Plan(**pd))

        # Create branches — Normal + Students legalization for each location
        branches_data = [
            {"name": "Sheikh Zayed - Normal Legalization", "url": "https://legalization-de.tlscontact.com/service/eg/egCAI2de/home", "service_type": ServiceType.LEGALIZATION},
            {"name": "Sheikh Zayed - Students Legalization", "url": "https://legalization-de.tlscontact.com/service/eg/egCAI2de/home", "service_type": ServiceType.LEGALIZATION},
            {"name": "Hurghada - Normal Legalization", "url": "https://legalization-de.tlscontact.com/service/eg/egHRG2de/home", "service_type": ServiceType.LEGALIZATION},
            {"name": "Hurghada - Students Legalization", "url": "https://legalization-de.tlscontact.com/service/eg/egHRG2de/home", "service_type": ServiceType.LEGALIZATION},
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
            # Remove visa plan and branches (no longer offered)
            await db.execute(text("DELETE FROM plans WHERE UPPER(plan_type) = 'VISA'"))
            await db.execute(text("DELETE FROM branches WHERE UPPER(service_type) = 'VISA'"))
            # Remove all-in-one plan (no longer offered)
            await db.execute(text("DELETE FROM plans WHERE UPPER(plan_type) = 'ALL_IN_ONE'"))
            await db.commit()
            logger.info("Migration: updated legalization plan name/features/price, removed visa plans/branches")
        except Exception as e:
            logger.warning(f"Plan price migration skipped: {e}")

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
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins_list,
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

app.include_router(auth_router)
app.include_router(sub_router)
app.include_router(payment_router)
app.include_router(monitoring_router)
app.include_router(admin_router)
app.include_router(contact_router)


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
