"""
Scheduler Service — Manages periodic branch checks using APScheduler.
Coordinates checker, notifications, and WebSocket broadcasts.
"""

import asyncio
import logging
from collections import deque
from datetime import datetime, timezone
from typing import Optional
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.config import settings
from app.database import async_session
from app.models import (
    Branch, CheckResult, ServiceAccount, UserBranchMonitor,
    User, NotificationLog, NotificationChannel, NotificationLogStatus,
    Subscription, SubscriptionStatus,
)
from app.services.checker import tls_checker, decrypt_credential
from app.services.email_service import email_service
from app.websocket import ws_manager

logger = logging.getLogger("scheduler")

# ── In-memory log buffer for admin monitoring ─────────────────────
MAX_LOG_ENTRIES = 200

class LogEntry:
    __slots__ = ("ts", "level", "branch", "message")
    def __init__(self, level: str, message: str, branch: str = ""):
        self.ts = datetime.now(timezone.utc).isoformat()
        self.level = level
        self.branch = branch
        self.message = message
    def to_dict(self):
        return {"ts": self.ts, "level": self.level, "branch": self.branch, "message": self.message}

_log_buffer: deque[LogEntry] = deque(maxlen=MAX_LOG_ENTRIES)

def get_recent_logs(limit: int = 100) -> list[dict]:
    """Return the last N monitoring log entries."""
    return [e.to_dict() for e in list(_log_buffer)[-limit:]]

async def _emit_log(level: str, message: str, branch: str = ""):
    """Add to buffer + push to admin WebSocket."""
    entry = LogEntry(level, message, branch)
    _log_buffer.append(entry)
    try:
        await ws_manager.send_to_admins({"type": "monitor_log", **entry.to_dict()})
    except Exception:
        pass


class SchedulerService:
    def __init__(self):
        self._scheduler: Optional[AsyncIOScheduler] = None
        self.is_running = False
        self.next_run_time: Optional[str] = None
        self.last_run_time: Optional[str] = None

    def start(self):
        """Start the periodic checker scheduler."""
        if self.is_running:
            logger.info("Scheduler already running")
            return

        self._scheduler = AsyncIOScheduler()
        self._scheduler.add_job(
            self._run_all_checks,
            "interval",
            minutes=settings.CHECK_INTERVAL_MINUTES,
            id="tls_checker",
            replace_existing=True,
            next_run_time=datetime.now(timezone.utc),  # Run immediately on start
        )
        self._scheduler.start()
        self.is_running = True
        logger.info(f"Scheduler started — checking every {settings.CHECK_INTERVAL_MINUTES} min")

    def stop(self):
        """Stop the scheduler."""
        if self._scheduler:
            self._scheduler.shutdown(wait=False)
            self._scheduler = None
        self.is_running = False
        logger.info("Scheduler stopped")

    async def _run_all_checks(self):
        """Run checks for all active branches that have subscribers."""
        logger.info("=== Starting check cycle ===")
        await _emit_log("info", "=== Starting check cycle ===")
        self.last_run_time = datetime.now(timezone.utc).isoformat()

        async with async_session() as db:
            # Get all active branches
            result = await db.execute(
                select(Branch).where(Branch.is_active == True)
            )
            branches = result.scalars().all()

            for branch in branches:
                try:
                    await self.check_branch(branch.id)
                except asyncio.CancelledError:
                    logger.info("Check cycle cancelled — monitoring stopped")
                    return
                except Exception as e:
                    logger.error(f"Error checking branch {branch.name}: {e}")
                    await _emit_log("error", str(e), branch.name)

        # Update next run time
        if self._scheduler:
            job = self._scheduler.get_job("tls_checker")
            if job and job.next_run_time:
                self.next_run_time = job.next_run_time.isoformat()

        logger.info("=== Check cycle complete ===")
        await _emit_log("info", "=== Check cycle complete ===")

    async def check_branch(self, branch_id: int):
        """Check a specific branch and notify subscribers if slots found."""
        async with async_session() as db:
            # Get branch
            branch_result = await db.execute(select(Branch).where(Branch.id == branch_id))
            branch = branch_result.scalar_one_or_none()
            if not branch or not branch.is_active:
                return

            # Get active subscribers for this branch
            monitors = await db.execute(
                select(UserBranchMonitor, User)
                .join(User, UserBranchMonitor.user_id == User.id)
                .where(
                    UserBranchMonitor.branch_id == branch_id,
                    UserBranchMonitor.is_active == True,
                    User.is_active == True,
                )
            )
            subscribers = [(m, u) for m, u in monitors.all()]

            # Filter to users with active subscriptions
            active_subscribers = []
            for monitor, user in subscribers:
                sub_result = await db.execute(
                    select(Subscription)
                    .where(
                        Subscription.user_id == user.id,
                        Subscription.status == SubscriptionStatus.ACTIVE,
                    )
                    .order_by(Subscription.expires_at.desc())
                    .limit(1)
                )
                sub = sub_result.scalar_one_or_none()
                now = datetime.now(timezone.utc)
                if sub and sub.expires_at:
                    exp = sub.expires_at
                    # Handle timezone-naive datetimes from SQLite
                    if exp.tzinfo is None:
                        from datetime import timezone as tz
                        exp = exp.replace(tzinfo=tz.utc)
                    if exp > now:
                        active_subscribers.append((monitor, user))

            if not active_subscribers:
                logger.info(f"[{branch.name}] No active subscribers, skipping")
                await _emit_log("info", "No active subscribers, skipping", branch.name)
                return

            # Get service account for this branch
            sa_result = await db.execute(
                select(ServiceAccount)
                .where(ServiceAccount.branch_id == branch_id, ServiceAccount.is_active == True)
                .order_by(ServiceAccount.is_primary.desc())
                .limit(1)
            )
            service_account = sa_result.scalar_one_or_none()
            if not service_account:
                logger.warning(f"[{branch.name}] No service account configured, skipping")
                await _emit_log("warn", "No service account configured, skipping", branch.name)
                return

            # Decrypt credentials
            try:
                tls_email = decrypt_credential(service_account.email_encrypted)
                tls_password = decrypt_credential(service_account.password_encrypted)
            except Exception as e:
                logger.error(f"[{branch.name}] Credential decryption failed: {e}")
                return

            # Run the check
            logger.info(f"[{branch.name}] Checking ({len(active_subscribers)} subscribers)...")
            await _emit_log("info", f"Checking ({len(active_subscribers)} subscribers)...", branch.name)
            check_result = await tls_checker.check_branch(
                branch_url=branch.url,
                tls_email=tls_email,
                tls_password=tls_password,
                branch_name=branch.name,
                service_type=branch.service_type.value,
            )

            # Emit all step-by-step logs from the checker to admin panel
            for entry in check_result.get("logs", []):
                await _emit_log(
                    entry.get("level", "info"),
                    entry.get("message", ""),
                    branch.name,
                )

            # Update service account last used
            service_account.last_used_at = datetime.now(timezone.utc)
            if check_result["error"]:
                service_account.last_error = check_result["error"]

            # Save screenshot to disk if present
            screenshot_path = ""
            if check_result.get("screenshot"):
                try:
                    import os
                    screenshots_dir = os.path.join("data", "screenshots")
                    os.makedirs(screenshots_dir, exist_ok=True)
                    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
                    safe_name = branch.name.replace(" ", "_").replace("/", "_")
                    screenshot_path = os.path.join(screenshots_dir, f"{safe_name}_{ts}.png")
                    with open(screenshot_path, "wb") as f:
                        f.write(check_result["screenshot"])
                except Exception as e:
                    logger.warning(f"Failed to save screenshot: {e}")

            # Save check result to DB
            db_result = CheckResult(
                branch_id=branch_id,
                slots_available=check_result["slots_available"],
                slot_details=check_result["slot_details"],
                error=check_result["error"],
                duration_seconds=check_result["duration"],
                screenshot_path=screenshot_path,
            )
            db.add(db_result)
            await db.flush()

            # Broadcast via WebSocket to all subscribers
            subscriber_ids = [u.id for _, u in active_subscribers]
            await ws_manager.broadcast_check_result(
                branch_name=branch.name,
                service_type=branch.service_type.value,
                slots_available=check_result["slots_available"],
                slot_details=check_result["slot_details"],
                subscriber_user_ids=subscriber_ids,
            )

            # If slots found, send notifications
            if check_result["slots_available"]:
                logger.info(f"[{branch.name}] *** SLOTS FOUND — Notifying {len(active_subscribers)} users ***")

                for monitor, user in active_subscribers:
                    await self._notify_user(
                        db, user, db_result, branch, check_result["slot_details"]
                    )

            await db.commit()
            logger.info(f"[{branch.name}] Check complete in {check_result['duration']}s")
            result_msg = "SLOTS AVAILABLE!" if check_result["slots_available"] else (f"Error: {check_result['error']}" if check_result["error"] else "No slots")
            await _emit_log(
                "success" if check_result["slots_available"] else ("error" if check_result["error"] else "info"),
                f"Check complete in {check_result['duration']}s — {result_msg}",
                branch.name,
            )

    async def _notify_user(self, db, user: User, check_result: CheckResult,
                           branch: Branch, slot_details: dict | None):
        """Send notifications to a user across all their enabled channels."""

        # Email notification
        try:
            success = email_service.send_appointment_alert(
                to_email=user.email,
                branch_name=branch.name,
                service_type=branch.service_type.value,
                slot_details=slot_details,
                user_name=user.full_name,
            )
            db.add(NotificationLog(
                user_id=user.id,
                check_result_id=check_result.id,
                channel=NotificationChannel.EMAIL,
                destination=user.email,
                status=NotificationLogStatus.SENT if success else NotificationLogStatus.FAILED,
            ))
        except Exception as e:
            logger.error(f"Email notification failed for {user.email}: {e}")

        # Web Push notification
        if user.push_subscription:
            try:
                from pywebpush import webpush
                import json
                webpush(
                    subscription_info=user.push_subscription,
                    data=json.dumps({
                        "title": f"🎉 Appointment Available — {branch.name}",
                        "body": f"{branch.service_type.value.title()} slots detected! Book now.",
                        "url": "/dashboard",
                    }),
                    vapid_private_key=settings.VAPID_PRIVATE_KEY,
                    vapid_claims={"sub": f"mailto:{settings.VAPID_CLAIMS_EMAIL}"},
                )
                db.add(NotificationLog(
                    user_id=user.id,
                    check_result_id=check_result.id,
                    channel=NotificationChannel.WEB_PUSH,
                    destination="browser",
                    status=NotificationLogStatus.SENT,
                ))
            except Exception as e:
                logger.error(f"Web push failed for {user.email}: {e}")
                db.add(NotificationLog(
                    user_id=user.id,
                    check_result_id=check_result.id,
                    channel=NotificationChannel.WEB_PUSH,
                    destination="browser",
                    status=NotificationLogStatus.FAILED,
                    error=str(e),
                ))


# Singleton
scheduler_service = SchedulerService()
