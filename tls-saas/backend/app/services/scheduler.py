"""
Scheduler Service  Manages periodic branch checks using APScheduler.

Logic:
  LEGALIZATION: Every cycle, for each legalization branch, pick up to 4 random
                user credentials (active subscribers who have legalization creds).
                Run checks sequentially until one succeeds. If login fails on a
                credential, mark it and try the next. After 2 consecutive login
                failures  email admin. The first successful result is shared
                with ALL active legalization subscribers.

  VISA:         Every cycle, for each visa branch, collect all active visa
                subscribers who have visa credentials. Run individual checks one
                at a time (sequential). Each user gets their own result/notification.
"""

import asyncio
import logging
import random
from collections import deque
from datetime import datetime, timezone, timedelta
from typing import Optional
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.date import DateTrigger
from sqlalchemy import select

from app.config import settings
from app.auth import create_unsubscribe_token
from app.database import async_session
from app.models import (
    Branch, CheckResult, ServiceAccount, UserBranchMonitor, UserCredential,
    User, NotificationLog, NotificationChannel, NotificationLogStatus,
    Subscription, SubscriptionStatus, ServiceType,
)
from app.services.checker import tls_checker, decrypt_credential
from app.services.email_service import email_service
from app.websocket import ws_manager

logger = logging.getLogger("scheduler")

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
    return [e.to_dict() for e in list(_log_buffer)[-limit:]]


async def _emit_log(level: str, message: str, branch: str = ""):
    entry = LogEntry(level, message, branch)
    _log_buffer.append(entry)
    try:
        await ws_manager.send_to_admins({"type": "monitor_log", **entry.to_dict()})
    except Exception:
        pass


async def _get_active_subscribers(db, branch_id: int) -> list:
    monitors = await db.execute(
        select(UserBranchMonitor, User)
        .join(User, UserBranchMonitor.user_id == User.id)
        .where(
            UserBranchMonitor.branch_id == branch_id,
            UserBranchMonitor.is_active == True,
            User.is_active == True,
        )
    )
    users = []
    now = datetime.now(timezone.utc)
    for _m, user in monitors.all():
        sub_r = await db.execute(
            select(Subscription)
            .where(Subscription.user_id == user.id, Subscription.status == SubscriptionStatus.ACTIVE)
            .order_by(Subscription.expires_at.desc())
            .limit(1)
        )
        sub = sub_r.scalar_one_or_none()
        if sub and sub.expires_at:
            exp = sub.expires_at
            if exp.tzinfo is None:
                exp = exp.replace(tzinfo=timezone.utc)
            if exp > now:
                users.append(user)
    return users


async def _get_user_credential(db, user_id: int, service_type):
    r = await db.execute(
        select(UserCredential).where(
            UserCredential.user_id == user_id,
            UserCredential.service_type == service_type,
            UserCredential.is_active == True,
        )
    )
    return r.scalar_one_or_none()


def _is_login_failure(error: str) -> bool:
    err = (error or "").lower()
    return any(k in err for k in (
        "invalid credentials", "login failed", "incorrect password",
        "wrong password", "authentication failed", "invalid email", "bad credentials"
    ))


def _is_captcha_failure(error: str) -> bool:
    return "captcha_bypass_failed" in (error or "").lower()


async def _notify_admin_login_failure(branch_name: str, user_email: str, error: str):
    try:
        email_service.send(
            to_email=settings.ADMIN_EMAIL,
            subject=f"\u26a0\ufe0f TLS Login Failed \u2014 {branch_name}",
            html_body=f"""<div style="font-family:'Segoe UI',Arial;max-width:600px;margin:0 auto;
                background:#141832;color:#fff;padding:30px;border-radius:16px;">
                <h2 style="color:#ff4444;">\u26a0\ufe0f TLS Login Failed</h2>
                <p>Branch: <strong>{branch_name}</strong></p>
                <p>Credential used: <strong>{user_email}</strong></p>
                <p>Error: {error}</p>
                <p>Time: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}</p>
                <p style="color:#ffaa00;">This user's TLS credentials may be invalid or expired.</p>
            </div>""",
        )
    except Exception as e:
        logger.error(f"Failed to send admin login failure email: {e}")


def _is_no_application_error(error: str) -> bool:
    err = (error or "").lower()
    return "no application" in err


async def _notify_user_check_error(user, branch_name: str, error: str):
    """Send email to user when their check encounters login failure or no-application error."""
    try:
        error_type = "no_application" if _is_no_application_error(error) else "invalid_credentials"
        email_service.send_check_error_alert(
            to_email=user.email,
            user_name=user.full_name or user.email,
            branch_name=branch_name,
            error_type=error_type,
            error_message=error,
        )
        logger.info(f"Sent check error email to {user.email}: {error_type}")
    except Exception as e:
        logger.error(f"Failed to send check error email to {user.email}: {e}")


async def _save_screenshot(result: dict, branch_name: str) -> str:
    if not result.get("screenshot"):
        return ""
    try:
        import os
        screenshots_dir = os.path.join("data", "screenshots")
        os.makedirs(screenshots_dir, exist_ok=True)
        ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        safe_name = branch_name.replace(" ", "_").replace("/", "_")
        path = os.path.join(screenshots_dir, f"{safe_name}_{ts}.png")
        with open(path, "wb") as f:
            f.write(result["screenshot"])
        return path
    except Exception as e:
        logger.warning(f"Failed to save screenshot: {e}")
        return ""


async def _notify_user_email(db, scheduler, user, check_result, branch, slot_details):
    try:
        # ── Deduplication: only send once per slots-available window ──────────
        # If a successful email was sent for this user+branch within the last 13h
        # (initial alert + 12h reminder), skip — the reminder handles the follow-up.
        cutoff = datetime.now(timezone.utc) - timedelta(hours=13)
        recent_r = await db.execute(
            select(NotificationLog)
            .join(CheckResult, NotificationLog.check_result_id == CheckResult.id)
            .where(
                NotificationLog.user_id == user.id,
                CheckResult.branch_id == branch.id,
                NotificationLog.sent_at > cutoff,
                NotificationLog.status == NotificationLogStatus.SENT,
                NotificationLog.channel == NotificationChannel.EMAIL,
            )
            .limit(1)
        )
        if recent_r.scalar_one_or_none():
            logger.info(f"[{branch.name}] Skipping email for {user.email} — already notified within 13h")
            return

        unsubscribe_token = create_unsubscribe_token(user.id, branch.id)
        unsubscribe_url = f"{settings.BACKEND_URL}/api/auth/unsubscribe?token={unsubscribe_token}"

        success = email_service.send_appointment_alert(
            to_email=user.email,
            branch_name=branch.name,
            service_type=branch.service_type.value,
            slot_details=slot_details,
            user_name=user.full_name,
            unsubscribe_url=unsubscribe_url,
        )
        db.add(NotificationLog(
            user_id=user.id,
            check_result_id=check_result.id,
            channel=NotificationChannel.EMAIL,
            destination=user.email,
            status=NotificationLogStatus.SENT if success else NotificationLogStatus.FAILED,
        ))
        if success and scheduler and scheduler.running:
            try:
                scheduler.remove_job(f"reminder_{user.id}_{branch.id}", jobstore="default")
            except Exception:
                pass
            reminder_time = datetime.now(timezone.utc) + timedelta(hours=12)
            scheduler.add_job(
                _send_reminder_email,
                trigger=DateTrigger(run_date=reminder_time),
                id=f"reminder_{user.id}_{branch.id}",
                args=[user.email, user.full_name, branch.name, branch.service_type.value, unsubscribe_url],
                replace_existing=True,
            )
    except Exception as e:
        logger.error(f"Email notification failed for {user.email}: {e}")


async def _send_reminder_email(to_email: str, user_name: str, branch_name: str, service_type: str, unsubscribe_url: str = ""):
    try:
        email_service.send_appointment_reminder(
            to_email=to_email, branch_name=branch_name,
            service_type=service_type, user_name=user_name,
            unsubscribe_url=unsubscribe_url,
        )
    except Exception as e:
        logger.error(f"12h reminder failed for {to_email}: {e}")


class SchedulerService:
    def __init__(self):
        self._scheduler: Optional[AsyncIOScheduler] = None
        self.is_running = False
        self.next_run_time: Optional[str] = None
        self.last_run_time: Optional[str] = None

    def _on_job_error(self, event):
        """APScheduler error listener — log but never let it kill the scheduler."""
        logger.error(f"Scheduler job error: {event.exception}", exc_info=event.exception)

    def start(self):
        if self.is_running:
            return
        self._scheduler = AsyncIOScheduler()
        # Listen for job errors so they're logged and the scheduler continues
        from apscheduler.events import EVENT_JOB_ERROR, EVENT_JOB_MISSED
        self._scheduler.add_listener(self._on_job_error, EVENT_JOB_ERROR)
        self._scheduler.add_listener(
            lambda e: logger.warning(f"Job missed: {e.job_id}"), EVENT_JOB_MISSED
        )
        self._scheduler.add_job(
            self._run_all_checks,
            "interval",
            minutes=settings.CHECK_INTERVAL_MINUTES,
            id="tls_checker",
            replace_existing=True,
            next_run_time=datetime.now(timezone.utc),
            misfire_grace_time=None,  # never discard missed runs
            coalesce=True,            # combine missed runs into one
            max_instances=1,
        )
        self._scheduler.start()
        self.is_running = True
        logger.info(f"Scheduler started — checking every {settings.CHECK_INTERVAL_MINUTES} min")

    def stop(self):
        if self._scheduler:
            self._scheduler.shutdown(wait=False)
            self._scheduler = None
        self.is_running = False

    async def _run_all_checks(self):
        """Main check cycle — called by APScheduler every CHECK_INTERVAL_MINUTES."""
        try:
            logger.info("=== Starting check cycle ===")
            await _emit_log("info", "=== Starting check cycle ===")
            self.last_run_time = datetime.now(timezone.utc).isoformat()

            async with async_session() as db:
                result = await db.execute(select(Branch).where(Branch.is_active == True))
                branches = result.scalars().all()

            leg_branches = [b for b in branches if b.service_type == ServiceType.LEGALIZATION]
            visa_branches = [b for b in branches if b.service_type == ServiceType.VISA]

            # Per-branch timeout to prevent a single stuck check from blocking the cycle
            BRANCH_TIMEOUT = 300  # 5 minutes per branch

            for branch in leg_branches:
                try:
                    await asyncio.wait_for(
                        self._check_legalization_branch(branch.id),
                        timeout=BRANCH_TIMEOUT,
                    )
                except asyncio.TimeoutError:
                    logger.error(f"Legalization branch {branch.name} timed out after {BRANCH_TIMEOUT}s")
                    await _emit_log("error", f"Timed out after {BRANCH_TIMEOUT}s", branch.name)
                except asyncio.CancelledError:
                    logger.info("Check cycle cancelled")
                    return
                except Exception as e:
                    logger.error(f"Legalization branch error {branch.name}: {e}", exc_info=True)
                    await _emit_log("error", str(e), branch.name)

            for branch in visa_branches:
                try:
                    await asyncio.wait_for(
                        self._check_visa_branch(branch.id),
                        timeout=BRANCH_TIMEOUT,
                    )
                except asyncio.TimeoutError:
                    logger.error(f"Visa branch {branch.name} timed out after {BRANCH_TIMEOUT}s")
                    await _emit_log("error", f"Timed out after {BRANCH_TIMEOUT}s", branch.name)
                except asyncio.CancelledError:
                    logger.info("Check cycle cancelled")
                    return
                except Exception as e:
                    logger.error(f"Visa branch error {branch.name}: {e}", exc_info=True)
                    await _emit_log("error", str(e), branch.name)

            if self._scheduler:
                job = self._scheduler.get_job("tls_checker")
                if job and job.next_run_time:
                    self.next_run_time = job.next_run_time.isoformat()
                    logger.info(f"Next scheduled run: {self.next_run_time}")

            logger.info("=== Check cycle complete ===")
            await _emit_log("info", "=== Check cycle complete ===")
        except asyncio.CancelledError:
            logger.info("Check cycle cancelled by shutdown")
        except Exception as e:
            # Catch-all: NEVER let an exception kill the scheduler
            logger.error(f"CRITICAL: Check cycle crashed: {e}", exc_info=True)
            await _emit_log("error", f"Check cycle crashed: {e}")

    async def _check_legalization_branch(self, branch_id: int):
        """Shared check: use up to 4 random user credentials, share result with all subscribers."""
        async with async_session() as db:
            branch_r = await db.execute(select(Branch).where(Branch.id == branch_id))
            branch = branch_r.scalar_one_or_none()
            if not branch or not branch.is_active:
                return

            active_users = await _get_active_subscribers(db, branch_id)
            if not active_users:
                await _emit_log("info", "No active subscribers, skipping", branch.name)
                return

            # Gather user credentials
            cred_users = []
            for user in active_users:
                cred = await _get_user_credential(db, user.id, ServiceType.LEGALIZATION)
                if cred:
                    cred_users.append((user, cred))

            if not cred_users:
                # Fall back to admin service accounts
                await self._check_with_service_account(db, branch, active_users)
                return

            random.shuffle(cred_users)
            candidates = cred_users[:4]
            await _emit_log("info",
                f"Legalization: trying {len(candidates)} credential(s) for {len(active_users)} subscriber(s)",
                branch.name)

            consecutive_failures = 0
            check_result = None

            for user, cred in candidates:
                try:
                    email = decrypt_credential(cred.email_encrypted)
                    pw = decrypt_credential(cred.password_encrypted)
                except Exception as e:
                    logger.error(f"[{branch.name}] Decrypt error for {user.email}: {e}")
                    continue

                logger.info(f"[{branch.name}] Attempting with {user.email}...")
                res = await tls_checker.check_branch(
                    branch_url=branch.url,
                    tls_email=email,
                    tls_password=pw,
                    branch_name=branch.name,
                    service_type=branch.service_type.value,
                )

                for le in res.get("logs", []):
                    await _emit_log(le.get("level", "info"), le.get("message", ""), branch.name)

                cred.last_used_at = datetime.now(timezone.utc)

                if _is_captcha_failure(res.get("error", "")):
                    cred.last_error = res["error"]
                    logger.warning(f"[{branch.name}] Captcha blocked for {user.email} — trying next credential")
                    await _emit_log("warn", f"Captcha blocked for {user.email} — trying next credential", branch.name)
                    continue

                if _is_login_failure(res.get("error", "")):
                    cred.last_error = res["error"]
                    consecutive_failures += 1
                    logger.warning(f"[{branch.name}] Login failure #{consecutive_failures} for {user.email}")
                    await _notify_user_check_error(user, branch.name, res["error"])
                    if consecutive_failures >= 2:
                        await db.commit()
                        await _notify_admin_login_failure(branch.name, user.email, res["error"])
                        await _emit_log("error", "2 consecutive login failures  admin notified", branch.name)
                        return
                    continue

                # Check for "no application" error and notify user
                if _is_no_application_error(res.get("error", "")):
                    await _notify_user_check_error(user, branch.name, res["error"])

                cred.last_error = res.get("error", "")
                consecutive_failures = 0
                check_result = res
                break  # Use first successful (non-login-failure) result

            await db.commit()

            if check_result is None:
                await _emit_log("warn", "All credential attempts failed/skipped", branch.name)
                # If all failed due to captcha, schedule a retry in 60s
                if self._scheduler:
                    self._scheduler.add_job(
                        self._check_legalization_branch,
                        trigger=DateTrigger(run_date=datetime.now(timezone.utc) + timedelta(minutes=1)),
                        id=f"captcha_retry_leg_{branch_id}",
                        args=[branch_id],
                        replace_existing=True,
                    )
                    await _emit_log("info", "Scheduled captcha retry in 60s", branch.name)
                return

            await self._persist_and_notify(db, branch, check_result, active_users)

    async def _check_visa_branch(self, branch_id: int):
        """Individual visa checks  one per user, sequential."""
        async with async_session() as db:
            branch_r = await db.execute(select(Branch).where(Branch.id == branch_id))
            branch = branch_r.scalar_one_or_none()
            if not branch or not branch.is_active:
                return

            active_users = await _get_active_subscribers(db, branch_id)
            if not active_users:
                await _emit_log("info", "No active subscribers, skipping", branch.name)
                return

            await _emit_log("info", f"Visa: {len(active_users)} user(s) queued sequentially", branch.name)

            for user in active_users:
                cred = await _get_user_credential(db, user.id, ServiceType.VISA)
                if not cred:
                    continue

                try:
                    email = decrypt_credential(cred.email_encrypted)
                    pw = decrypt_credential(cred.password_encrypted)
                except Exception as e:
                    logger.error(f"[{branch.name}] Decrypt error for {user.email}: {e}")
                    continue

                logger.info(f"[{branch.name}] Visa check for {user.email}...")
                res = await tls_checker.check_branch(
                    branch_url=branch.url,
                    tls_email=email,
                    tls_password=pw,
                    branch_name=branch.name,
                    service_type=branch.service_type.value,
                )

                for le in res.get("logs", []):
                    await _emit_log(le.get("level", "info"), le.get("message", ""), branch.name)

                cred.last_used_at = datetime.now(timezone.utc)

                if _is_captcha_failure(res.get("error", "")):
                    cred.last_error = res["error"]
                    await db.commit()
                    logger.warning(f"[{branch.name}] Captcha blocked for {user.email} — scheduling retry in 60s")
                    await _emit_log("warn", f"Captcha blocked for {user.email} — retrying in 60s", branch.name)
                    if self._scheduler:
                        self._scheduler.add_job(
                            self._check_visa_branch,
                            trigger=DateTrigger(run_date=datetime.now(timezone.utc) + timedelta(minutes=1)),
                            id=f"captcha_retry_visa_{branch_id}",
                            args=[branch_id],
                            replace_existing=True,
                        )
                    continue

                if _is_login_failure(res.get("error", "")):
                    cred.last_error = res["error"]
                    await db.commit()
                    await _notify_admin_login_failure(branch.name, user.email, res["error"])
                    await _notify_user_check_error(user, branch.name, res["error"])
                    await _emit_log("error", f"Login failed for {user.email}  admin notified", branch.name)
                    continue

                cred.last_error = res.get("error", "")
                await db.flush()

                # Check for "no application" error and notify user
                if _is_no_application_error(res.get("error", "")):
                    await _notify_user_check_error(user, branch.name, res["error"])
                await db.flush()

                screenshot_path = await _save_screenshot(res, branch.name)
                db_result = CheckResult(
                    branch_id=branch_id,
                    user_id=user.id,
                    slots_available=res["slots_available"],
                    slot_details=res["slot_details"],
                    error=res.get("error", ""),
                    duration_seconds=res["duration"],
                    screenshot_path=screenshot_path,
                )
                db.add(db_result)
                await db.flush()

                await ws_manager.broadcast_check_result(
                    branch_name=branch.name,
                    service_type=branch.service_type.value,
                    slots_available=res["slots_available"],
                    slot_details=res["slot_details"],
                    subscriber_user_ids=[user.id],
                )

                if res["slots_available"]:
                    await _notify_user_email(db, self._scheduler, user, db_result, branch, res["slot_details"])

                await db.commit()
                status = "SLOTS!" if res["slots_available"] else (res.get("error") or "No slots")
                await _emit_log(
                    "success" if res["slots_available"] else ("error" if res.get("error") else "info"),
                    f"Visa {user.email}: {status} ({res['duration']}s)",
                    branch.name,
                )

    async def _check_with_service_account(self, db, branch, active_users: list):
        """Fallback when no user credentials exist  use admin service account."""
        sa_r = await db.execute(
            select(ServiceAccount)
            .where(ServiceAccount.branch_id == branch.id, ServiceAccount.is_active == True)
            .order_by(ServiceAccount.is_primary.desc())
            .limit(1)
        )
        sa = sa_r.scalar_one_or_none()
        if not sa:
            await _emit_log("warn", "No user credentials and no service account  skipping", branch.name)
            return
        try:
            email = decrypt_credential(sa.email_encrypted)
            pw = decrypt_credential(sa.password_encrypted)
        except Exception as e:
            logger.error(f"[{branch.name}] SA decrypt error: {e}")
            return

        await _emit_log("info",
            f"Legalization fallback: using admin service account ({len(active_users)} subscribers)", branch.name)
        res = await tls_checker.check_branch(
            branch_url=branch.url,
            tls_email=email,
            tls_password=pw,
            branch_name=branch.name,
            service_type=branch.service_type.value,
        )
        for le in res.get("logs", []):
            await _emit_log(le.get("level", "info"), le.get("message", ""), branch.name)

        sa.last_used_at = datetime.now(timezone.utc)
        sa.last_error = res.get("error", "")
        if _is_login_failure(res.get("error", "")):
            await _notify_admin_login_failure(branch.name, "admin service account", res["error"])
        await db.commit()
        await self._persist_and_notify(db, branch, res, active_users)

    async def _persist_and_notify(self, db, branch, check_result: dict, active_users: list):
        """Save one CheckResult per subscriber and notify each individually."""
        screenshot_path = await _save_screenshot(check_result, branch.name)

        # Create an individual result row for each subscriber so their dashboards
        # show only their own checks, not results shared with other users.
        user_results: dict = {}  # user.id -> db_result
        for user in active_users:
            db_result = CheckResult(
                branch_id=branch.id,
                user_id=user.id,
                slots_available=check_result["slots_available"],
                slot_details=check_result["slot_details"],
                error=check_result.get("error", ""),
                duration_seconds=check_result["duration"],
                screenshot_path=screenshot_path,
            )
            db.add(db_result)
            user_results[user.id] = db_result

        await db.flush()

        await ws_manager.broadcast_check_result(
            branch_name=branch.name,
            service_type=branch.service_type.value,
            slots_available=check_result["slots_available"],
            slot_details=check_result["slot_details"],
            subscriber_user_ids=[u.id for u in active_users],
        )

        if check_result["slots_available"]:
            logger.info(f"[{branch.name}] *** SLOTS  Notifying {len(active_users)} users ***")
            for user in active_users:
                await _notify_user_email(db, self._scheduler, user, user_results[user.id], branch, check_result["slot_details"])

        await db.commit()
        msg = "SLOTS AVAILABLE!" if check_result["slots_available"] else (
            f"Error: {check_result['error']}" if check_result.get("error") else "No slots"
        )
        await _emit_log(
            "success" if check_result["slots_available"] else ("error" if check_result.get("error") else "info"),
            f"Done in {check_result['duration']}s  {msg}",
            branch.name,
        )

    async def check_branch(self, branch_id: int):
        """Trigger a single branch check from admin panel."""
        async with async_session() as db:
            r = await db.execute(select(Branch).where(Branch.id == branch_id))
            branch = r.scalar_one_or_none()
        if not branch:
            return
        if branch.service_type == ServiceType.VISA:
            await self._check_visa_branch(branch_id)
        else:
            await self._check_legalization_branch(branch_id)


# Singleton
scheduler_service = SchedulerService()
