"""
Monitoring Routes — Check results, live status for user dashboard, desktop app reporting,
and license verification / deactivation for the desktop app.
"""

import logging
from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, Depends, HTTPException, Request
from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)
from pydantic import BaseModel
from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from app.database import get_db
from app.config import settings
from app.models import (
    User, Branch, CheckResult, UserBranchMonitor,
    NotificationLog, NotificationLogStatus, NotificationChannel,
    SubscriptionStatus, Subscription, Payment, PaymentStatus,
    SystemSetting, ServiceType, HardwareUsage,
)
from app.auth import get_current_user
from app.schemas import CheckResultPublic, NotificationLogPublic, DesktopCheckReport

logger = logging.getLogger("monitoring")

router = APIRouter(prefix="/api/monitoring", tags=["monitoring"])


# ── License verification / deactivation (public, no auth) ────────────

class LicenseVerifyRequest(BaseModel):
    license_key: str = ""
    hardware_id: str = ""

class LicenseDeactivateRequest(BaseModel):
    license_key: str
    hardware_id: str


def _hardware_matches(stored_hardware_id: str | None, provided_hardware_id: str | None) -> bool:
    """
    Require a provided hardware ID whenever a stored one exists.
    Allow exact matches for full IDs and prefix matches for legacy imported licenses.
    """
    stored = (stored_hardware_id or "").strip()
    provided = (provided_hardware_id or "").strip()
    if not stored:
        return True
    if not provided:
        return False
    if len(stored) == 8:
        return provided.upper().startswith(stored.upper())
    return stored.lower() == provided.lower()


def _validate_license_signature(plan: str, hw_short: str, rand: str, sig: str) -> bool:
    """Verify HMAC-SHA256 signature of a license key."""
    import hashlib, hmac as _hmac
    secret = settings.LICENSE_HMAC_SECRET
    payload = f"{plan}:{hw_short}:{rand}"
    expected = _hmac.new(secret.encode(), payload.encode(), hashlib.sha256).hexdigest()[:16].upper()
    return sig.upper() == expected


def _parse_license_key(key: str) -> dict | None:
    """Parse a license key into its components. Returns dict or None."""
    key = key.strip().upper()
    parts = key.split("-")
    if len(parts) == 4:
        plan_raw, hw, rand, sig = parts
    elif len(parts) == 5:
        plan_raw = f"{parts[0]}_{parts[1]}"
        hw, rand, sig = parts[2], parts[3], parts[4]
    else:
        return None
    plan = plan_raw.lower()
    if not _validate_license_signature(plan, hw, rand, sig):
        return None
    return {"plan": plan, "hw_prefix": hw, "random": rand, "signature": sig, "raw_key": key}


@router.post("/license/verify")
async def license_verify(
    body: LicenseVerifyRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Verify a license key and/or check if a hardware_id has a license.
    Used by the desktop app for:
      1. Revocation check (sends license_key + hardware_id) — returns is_active status
      2. Payment polling (sends hardware_id) — returns found + license_key
    """
    # ── Case 1: Verify a specific license key ───────────────────────
    if body.license_key:
        parsed = _parse_license_key(body.license_key)
        if not parsed:
            return {"found": False, "error": "Invalid license key format"}

        # Look up in the payments table
        result = await db.execute(
            select(Payment).where(Payment.license_key == parsed["raw_key"]).limit(1)
        )
        payment = result.scalar_one_or_none()

        if not payment:
            # Check the revoked-keys blacklist (populated when payments are deleted)
            revoked_result = await db.execute(
                select(SystemSetting).where(SystemSetting.key == "revoked_license_keys")
            )
            revoked_setting = revoked_result.scalar_one_or_none()
            if revoked_setting:
                try:
                    import json as _json
                    revoked_keys: list = _json.loads(revoked_setting.value)
                    if parsed["raw_key"] in revoked_keys:
                        return {"found": True, "is_active": False, "plan": parsed["plan"]}
                except Exception:
                    pass
            # A valid signature alone is not enough — the key must exist in the database.
            return {"found": False, "error": "License key is not registered"}

        # Backward compatibility: some already-installed desktop builds did not send
        # hardware_id during periodic status/revocation checks. Keep them functional
        # while newer clients enforce full hardware-bound verification.
        if payment.hardware_id and not (body.hardware_id or "").strip():
            is_active = payment.status == PaymentStatus.APPROVED
            return {
                "found": True,
                "is_active": is_active,
                "plan": payment.plan_key or parsed["plan"],
                "license_key": payment.license_key,
                "legacy_client": True,
            }

        if not _hardware_matches(payment.hardware_id, body.hardware_id):
            return {
                "found": True,
                "is_active": False,
                "plan": payment.plan_key or parsed["plan"],
                "error": "Hardware ID mismatch",
            }

        is_active = payment.status == PaymentStatus.APPROVED
        return {
            "found": True,
            "is_active": is_active,
            "plan": payment.plan_key or parsed["plan"],
            "license_key": payment.license_key,
        }

    # ── Case 2: Look up by hardware_id (payment polling) ───────────
    if body.hardware_id:
        hw_id = body.hardware_id.strip()
        result = await db.execute(
            select(Payment)
            .where(
                Payment.hardware_id == hw_id,
                Payment.license_key.isnot(None),
                Payment.license_key != "",
                Payment.status == PaymentStatus.APPROVED,
            )
            .order_by(Payment.processed_at.desc())
            .limit(1)
        )
        payment = result.scalar_one_or_none()
        if payment:
            return {
                "found": True,
                "is_active": True,
                "license_key": payment.license_key,
                "plan": payment.plan_key or "",
            }
        return {"found": False}

    return {"found": False, "error": "Provide license_key or hardware_id"}


@router.post("/license/deactivate")
async def license_deactivate(
    body: LicenseDeactivateRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Deactivate a license key (called when user uninstalls / changes device).
    Marks the payment record's license_key as revoked.
    """
    parsed = _parse_license_key(body.license_key)
    if not parsed:
        return {"success": False, "error": "Invalid license key"}

    result = await db.execute(
        select(Payment).where(Payment.license_key == parsed["raw_key"]).limit(1)
    )
    payment = result.scalar_one_or_none()

    if not payment:
        return {"success": True, "message": "License not found in database (already inactive)"}

    # Verify hardware_id matches
    if not _hardware_matches(payment.hardware_id, body.hardware_id):
        return {"success": False, "error": "Hardware ID mismatch"}

    payment.status = PaymentStatus.REJECTED
    payment.admin_notes = (payment.admin_notes or "") + f"\nDeactivated by user at {datetime.now(timezone.utc).isoformat()}"
    await db.commit()

    logger.info(f"License deactivated: {parsed['raw_key']} by hardware {body.hardware_id}")
    return {"success": True, "message": "License deactivated"}


@router.get("/status")
async def monitoring_status(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get user's monitoring overview — is monitoring active, what branches, latest results."""
    # Check subscription
    subs_result = await db.execute(
        select(Subscription)
        .options(selectinload(Subscription.plan))
        .where(
            Subscription.user_id == user.id,
            Subscription.status == SubscriptionStatus.ACTIVE,
        )
        .order_by(Subscription.expires_at.desc())
    )
    all_subs = subs_result.scalars().all()
    # Filter to truly active (not expired)
    now = datetime.now(timezone.utc)
    active_subs = []
    for s in all_subs:
        exp = s.expires_at
        if exp:
            if exp.tzinfo is None:
                exp = exp.replace(tzinfo=timezone.utc)
            if exp > now:
                active_subs.append(s)
    sub = active_subs[0] if active_subs else None
    is_active = len(active_subs) > 0

    # Desktop license users don't have Subscription rows — treat approved payment as active
    if not is_active:
        paid = await db.execute(
            select(Payment).where(
                Payment.user_id == user.id,
                Payment.status == PaymentStatus.APPROVED,
                Payment.license_key.isnot(None),
            ).limit(1)
        )
        if paid.scalar_one_or_none():
            is_active = True

    plan_types = list(dict.fromkeys(
        s.plan.plan_type.value for s in active_subs if s.plan
    ))

    # Get monitored branches with latest results
    monitors = await db.execute(
        select(UserBranchMonitor, Branch)
        .join(Branch, UserBranchMonitor.branch_id == Branch.id)
        .where(UserBranchMonitor.user_id == user.id, UserBranchMonitor.is_active == True)
    )

    branches = []
    for monitor, branch in monitors.all():
        # Latest check for this user on this branch
        latest = await db.execute(
            select(CheckResult)
            .where(
                CheckResult.branch_id == branch.id,
                CheckResult.user_id == user.id,
            )
            .order_by(CheckResult.checked_at.desc())
            .limit(1)
        )
        check = latest.scalar_one_or_none()

        # Checks today
        today_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
        checks_today_result = await db.execute(
            select(func.count(CheckResult.id))
            .where(
                CheckResult.branch_id == branch.id,
                CheckResult.user_id == user.id,
                CheckResult.checked_at >= today_start,
            )
        )
        checks_today = checks_today_result.scalar() or 0

        branches.append({
            "branch_id": branch.id,
            "branch_name": branch.name,
            "service_type": branch.service_type.value,
            "is_active": branch.is_active,
            "last_check": check.checked_at.isoformat() if check else None,
            "last_slots_available": check.slots_available if check else None,
            "last_slot_details": check.slot_details if check else None,
            "checks_today": checks_today,
        })

    # Check for pending payment (user submitted but admin hasn't approved yet)
    pending_payment_result = await db.execute(
        select(Payment, Branch)
        .outerjoin(Branch, Payment.branch_id == Branch.id)
        .where(Payment.user_id == user.id, Payment.status == PaymentStatus.PENDING)
        .order_by(Payment.created_at.desc())
        .limit(1)
    )
    pending_row = pending_payment_result.first()
    pending_payment = None
    if pending_row:
        pmt, br = pending_row
        pending_payment = {
            "payment_id": pmt.id,
            "branch_name": br.name if br else None,
            "amount": pmt.amount,
            "submitted_at": pmt.created_at.isoformat(),
        }

    # Check maintenance mode
    maint_result = await db.execute(
        select(SystemSetting).where(SystemSetting.key == "maintenance_mode")
    )
    maint_setting = maint_result.scalar_one_or_none()
    maintenance_mode = maint_setting and maint_setting.value == "true"

    # Worker next run time
    next_run_result = await db.execute(
        select(SystemSetting).where(SystemSetting.key == "worker_next_run")
    )
    next_run_setting = next_run_result.scalar_one_or_none()
    worker_next_run = next_run_setting.value if next_run_setting else None

    # Total checks for this user
    total_checks_result = await db.execute(
        select(func.count(CheckResult.id)).where(CheckResult.user_id == user.id)
    )
    total_checks = total_checks_result.scalar() or 0

    return {
        "subscription_active": is_active,
        "plan_type": sub.plan.plan_type.value if sub and sub.plan else None,
        "plan_types": plan_types,
        "payment_pending": pending_payment,
        "maintenance_mode": maintenance_mode,
        "expires_at": sub.expires_at.isoformat() if sub and sub.expires_at else None,
        "monitored_branches": branches,
        "total_branches_monitored": len(branches),
        "worker_next_run": worker_next_run,
        "total_checks": total_checks,
    }


@router.get("/results")
async def check_results(
    branch_id: int | None = None,
    limit: int = 20,
    offset: int = 0,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get recent check results belonging to this user."""
    base_query = (
        select(CheckResult, Branch)
        .join(Branch, CheckResult.branch_id == Branch.id)
        # Only return results for branches this user actually has an active monitor entry for.
        # This prevents orphaned records from leaking to other users.
        .join(
            UserBranchMonitor,
            and_(
                UserBranchMonitor.user_id == user.id,
                UserBranchMonitor.branch_id == CheckResult.branch_id,
                UserBranchMonitor.is_active == True,
                CheckResult.checked_at >= UserBranchMonitor.created_at,
            ),
        )
        .where(
            CheckResult.user_id == user.id,
            CheckResult.user_id.isnot(None),
        )
        .distinct(CheckResult.id)
    )

    if branch_id:
        base_query = base_query.where(CheckResult.branch_id == branch_id)

    # Total count for pagination
    count_result = await db.execute(
        select(func.count()).select_from(base_query.subquery())
    )
    total = count_result.scalar() or 0

    page_limit = min(limit, 100)
    query = base_query.order_by(CheckResult.checked_at.desc()).limit(page_limit).offset(offset)
    result = await db.execute(query)

    import base64 as _b64, os as _os
    rows = []
    for cr, b in result.all():
        screenshot_b64 = None
        if cr.slots_available and cr.screenshot_path:
            try:
                with open(cr.screenshot_path, "rb") as f:
                    screenshot_b64 = _b64.b64encode(f.read()).decode()
            except Exception:
                pass
        rows.append(CheckResultPublic(
            id=cr.id,
            branch_name=b.name,
            branch_service_type=b.service_type,
            checked_at=cr.checked_at,
            slots_available=cr.slots_available,
            slot_details=cr.slot_details,
            duration_seconds=cr.duration_seconds,
            error=cr.error or "",
            screenshot_b64=screenshot_b64,
        ))

    return {"total": total, "results": rows}


@router.get("/notifications")
async def my_notifications(
    limit: int = 30,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get recent notifications sent to the user."""
    result = await db.execute(
        select(NotificationLog, CheckResult, Branch)
        .join(CheckResult, NotificationLog.check_result_id == CheckResult.id)
        .join(Branch, CheckResult.branch_id == Branch.id)
        .where(NotificationLog.user_id == user.id)
        .order_by(NotificationLog.sent_at.desc())
        .limit(min(limit, 100))
    )

    return [
        NotificationLogPublic(
            id=nl.id,
            channel=nl.channel,
            destination=nl.destination,
            sent_at=nl.sent_at,
            status=nl.status.value,
            branch_name=b.name,
        )
        for nl, cr, b in result.all()
    ]


@router.post("/report-desktop")
async def report_desktop_check(
    body: DesktopCheckReport,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Receive a check result from the desktop app.
    Creates a CheckResult entry linked to the correct branch.
    """
    # Find the branch
    svc_type = ServiceType.VISA if body.service_type.lower() == "visa" else ServiceType.LEGALIZATION
    branch_result = await db.execute(
        select(Branch).where(
            Branch.name.ilike(f"%{body.branch_name}%"),
            Branch.service_type == svc_type,
        ).limit(1)
    )
    branch = branch_result.scalar_one_or_none()

    if not branch:
        # Try broader match
        branch_result = await db.execute(
            select(Branch).where(Branch.service_type == svc_type).limit(1)
        )
        branch = branch_result.scalar_one_or_none()

    if not branch:
        raise HTTPException(404, f"Branch not found: {body.branch_name}")

    # Save screenshot if provided
    screenshot_path = ""
    if body.screenshot_b64:
        import base64, os
        screenshots_dir = os.path.join("data", "screenshots")
        os.makedirs(screenshots_dir, exist_ok=True)
        ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        screenshot_path = os.path.join(screenshots_dir, f"desktop_{user.id}_{ts}.png")
        try:
            with open(screenshot_path, "wb") as f:
                f.write(base64.b64decode(body.screenshot_b64))
        except Exception:
            screenshot_path = ""

    # Create check result
    cr = CheckResult(
        branch_id=branch.id,
        user_id=user.id,
        checked_at=datetime.now(timezone.utc),
        slots_available=body.slots_available,
        slot_details=body.slot_details or "",
        screenshot_path=screenshot_path,
        duration_seconds=body.duration_seconds,
        error=body.error or "",
        source="desktop",
    )
    db.add(cr)
    await db.commit()

    # If slots found, notify via backend email too
    if body.slots_available:
        try:
            from app.services.email_service import EmailService
            email_svc = EmailService()
            email_svc.send_appointment_alert(
                to_email=user.email,
                user_name=user.full_name or user.email,
                branch_name=branch.name,
                service_type=branch.service_type.value,
                slot_details=body.slot_details or "Slots detected by desktop app",
            )
        except Exception as e:
            import logging
            logging.getLogger("monitoring").warning(f"Failed to send desktop alert email: {e}")

    return {"status": "ok", "check_result_id": cr.id, "slots_available": body.slots_available}


@router.post("/report-desktop-license")
async def report_desktop_check_by_license(
    body: DesktopCheckReport,
    db: AsyncSession = Depends(get_db),
):
    """
    Receive a check result from the desktop app, authenticated by license key.
    No JWT required — the desktop app sends its license key instead.
    """
    if not body.license_key:
        raise HTTPException(400, "license_key is required")

    # Look up payment by license key to find the user
    pay_result = await db.execute(
        select(Payment).where(
            Payment.license_key == body.license_key,
            Payment.status == PaymentStatus.APPROVED,
        ).limit(1)
    )
    payment = pay_result.scalar_one_or_none()
    if not payment:
        raise HTTPException(401, "Invalid or inactive license key")

    # Get the user
    user_result = await db.execute(select(User).where(User.id == payment.user_id))
    user = user_result.scalar_one_or_none()

    # Find the branch
    svc_type = ServiceType.VISA if body.service_type.lower() == "visa" else ServiceType.LEGALIZATION
    branch_result = await db.execute(
        select(Branch).where(
            Branch.name.ilike(f"%{body.branch_name}%"),
            Branch.service_type == svc_type,
        ).limit(1)
    )
    branch = branch_result.scalar_one_or_none()

    if not branch:
        branch_result = await db.execute(
            select(Branch).where(Branch.service_type == svc_type).limit(1)
        )
        branch = branch_result.scalar_one_or_none()

    if not branch:
        raise HTTPException(404, f"Branch not found: {body.branch_name}")

    # Ensure UserBranchMonitor exists so dashboard results endpoint can find it
    from app.models import UserBranchMonitor
    mon_result = await db.execute(
        select(UserBranchMonitor).where(
            UserBranchMonitor.user_id == payment.user_id,
            UserBranchMonitor.branch_id == branch.id,
        )
    )
    monitor = mon_result.scalar_one_or_none()
    if not monitor:
        db.add(UserBranchMonitor(
            user_id=payment.user_id,
            branch_id=branch.id,
            is_active=True,
            created_at=datetime.now(timezone.utc) - timedelta(seconds=5),
        ))

    # Save screenshot if provided
    screenshot_path = ""
    if body.screenshot_b64:
        import base64, os
        screenshots_dir = os.path.join("data", "screenshots")
        os.makedirs(screenshots_dir, exist_ok=True)
        ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        screenshot_path = os.path.join(screenshots_dir, f"desktop_{payment.user_id}_{ts}.png")
        try:
            with open(screenshot_path, "wb") as f:
                f.write(base64.b64decode(body.screenshot_b64))
        except Exception:
            screenshot_path = ""

    # Create check result — tagged with user_id so their dashboard shows only their checks
    cr = CheckResult(
        branch_id=branch.id,
        user_id=payment.user_id,
        checked_at=datetime.now(timezone.utc),
        slots_available=body.slots_available,
        slot_details=body.slot_details or "",
        screenshot_path=screenshot_path,
        duration_seconds=body.duration_seconds,
        error=body.error or "",
        source="desktop",
    )
    db.add(cr)
    await db.commit()
    await db.refresh(cr)

    # Log the desktop notification so the user's Notifications page shows it
    if body.slots_available and user:
        nl = NotificationLog(
            user_id=payment.user_id,
            check_result_id=cr.id,
            channel=NotificationChannel.EMAIL,
            destination=user.email,
            status=NotificationLogStatus.SENT,
        )
        db.add(nl)
        await db.commit()

    # Check if desktop app experienced a critical error (no application, bad credentials) and alert user
    if user and body.error:
        error_lower = body.error.lower()
        if('no application' in error_lower or 'invalid' in error_lower or 'incorrect' in error_lower or 'wrong' in error_lower):
            try:
                from app.services.scheduler import _notify_user_check_error
                await _notify_user_check_error(user, branch.name if branch else "unknown", body.error)
            except Exception as e:
                logging.getLogger("monitoring").warning(f"Failed to send desktop error alert: {e}")

    # Broadcast to user's dashboard via WebSocket so it auto-refreshes
    try:
        from app.websocket import ws_manager
        await ws_manager.broadcast_check_result(
            branch_name=branch.name,
            service_type=branch.service_type.value,
            slots_available=body.slots_available,
            slot_details=None,
            subscriber_user_ids=[payment.user_id],
        )
    except Exception as e:
        logger.warning(f"WebSocket broadcast failed (non-fatal): {e}")

    # If slots found, notify via backend email too
    if body.slots_available and user:
        try:
            from app.services.email_service import EmailService
            email_svc = EmailService()
            email_svc.send_appointment_alert(
                to_email=user.email,
                user_name=user.full_name or user.email,
                branch_name=branch.name,
                service_type=branch.service_type.value,
                slot_details=body.slot_details or "Slots detected by desktop app",
            )
        except Exception as e:
            logger.warning(f"Failed to send desktop alert email: {e}")

    return {"status": "ok", "check_result_id": cr.id, "slots_available": body.slots_available}


# ── Laptop Worker API (WORKER_MODE architecture) ───────────────────────────────
# The laptop runs worker.py which polls these endpoints to get check jobs,
# runs Selenium locally, and posts results back.  All endpoints require the
# shared WORKER_SECRET header so random callers cannot abuse them.

from fastapi import Header

def _verify_worker(x_worker_secret: str = Header(default="")):
    if x_worker_secret != settings.WORKER_SECRET:
        raise HTTPException(status_code=403, detail="Invalid worker secret")


class WorkerLogBody(BaseModel):
    level: str = "info"
    message: str = ""
    branch: str = ""


class WorkerResultBody(BaseModel):
    branch_id: int
    slots_available: bool
    slot_details: str | None = None
    error: str = ""
    duration_seconds: float = 0
    source: str = "worker"
    logs: list = []  # Step-by-step logs from the checker to forward to the admin panel
    skip_log_replay: bool = False  # True when logs were already streamed in real-time


@router.get("/worker/jobs", dependencies=[Depends(_verify_worker)])
async def worker_get_jobs(db: AsyncSession = Depends(get_db)):
    """
    Return the list of active branches + their active subscribers so the
    laptop worker knows what to check next.
    Only called when WORKER_MODE=true is configured on Fly.io.
    """
    from app.models import Branch, UserBranchMonitor, User, Subscription, UserCredential, Plan
    from app.models import PlanType as _PlanType
    # Respect the admin start/stop toggle
    state_r = await db.execute(select(SystemSetting).where(SystemSetting.key == "scheduler_running"))
    state = state_r.scalar_one_or_none()
    if not state or state.value != "true":
        return {"jobs": [], "paused": True}

    result = await db.execute(select(Branch).where(Branch.is_active == True))
    branches = result.scalars().all()

    if branches:
        from app.services.scheduler import _emit_log
        await _emit_log("info", f"=== Worker starting check cycle ({len(branches)} branch(es)) ===")

    jobs = []
    now = datetime.now(timezone.utc)
    for branch in branches:
        # Collect active subscribers with valid subscriptions
        monitors = await db.execute(
            select(UserBranchMonitor, User)
            .join(User, UserBranchMonitor.user_id == User.id)
            .where(
                UserBranchMonitor.branch_id == branch.id,
                UserBranchMonitor.is_active == True,
                User.is_active == True,
            )
        )
        users = []
        for _m, user in monitors.all():
            sub_r = await db.execute(
                select(Subscription)
                .join(Plan, Subscription.plan_id == Plan.id)
                .where(
                    Subscription.user_id == user.id,
                    Subscription.status == SubscriptionStatus.ACTIVE,
                    Plan.plan_type == _PlanType.PREMIUM,  # cloud worker only handles premium
                )
                .order_by(Subscription.expires_at.desc())
                .limit(1)
            )
            sub = sub_r.scalar_one_or_none()
            if sub and sub.expires_at:
                exp = sub.expires_at
                if exp.tzinfo is None:
                    exp = exp.replace(tzinfo=timezone.utc)
                if exp > now:
                    # Fetch encrypted credentials
                    svc = branch.service_type
                    cred_r = await db.execute(
                        select(UserCredential).where(
                            UserCredential.user_id == user.id,
                            UserCredential.service_type == svc,
                            UserCredential.is_active == True,
                        )
                    )
                    cred = cred_r.scalar_one_or_none()
                    # Only include users who have credentials — no point sending jobs
                    # the worker can't use (avoids instant "All attempts failed" errors)
                    if cred and cred.email_encrypted and cred.password_encrypted:
                        users.append({
                            "user_id": user.id,
                            "user_email": user.email,
                            "email_encrypted": cred.email_encrypted,
                            "password_encrypted": cred.password_encrypted,
                        })
        if users:
            jobs.append({
                "branch_id": branch.id,
                "branch_name": branch.name,
                "branch_url": branch.url,
                "service_type": branch.service_type.value,
                "users": users,
            })
    # Include the configured interval so the worker uses the DB value, not just its env var
    interval_r = await db.execute(select(SystemSetting).where(SystemSetting.key == "check_interval_minutes"))
    interval_setting = interval_r.scalar_one_or_none()
    interval_minutes = int(interval_setting.value) if interval_setting and interval_setting.value.isdigit() else 30
    return {"jobs": jobs, "interval_minutes": interval_minutes}


class WorkerHeartbeatBody(BaseModel):
    last_run_at: str  # ISO timestamp
    next_run_at: str  # ISO timestamp
    interval_minutes: int = 30


@router.post("/worker/heartbeat", dependencies=[Depends(_verify_worker)])
async def worker_heartbeat(body: WorkerHeartbeatBody, db: AsyncSession = Depends(get_db)):
    """Called by the laptop worker at the start of each cycle to report timing info."""
    for key, val in [
        ("worker_last_run", body.last_run_at),
        ("worker_next_run", body.next_run_at),
        ("worker_interval_minutes", str(body.interval_minutes)),
    ]:
        row = (await db.execute(select(SystemSetting).where(SystemSetting.key == key))).scalar_one_or_none()
        if row:
            row.value = val
        else:
            db.add(SystemSetting(key=key, value=val))
    await db.commit()
    return {"ok": True}


@router.post("/worker/log", dependencies=[Depends(_verify_worker)])
async def worker_stream_log(body: WorkerLogBody):
    """Receives a single log entry from the laptop worker and broadcasts it immediately via WebSocket."""
    from app.services.scheduler import _emit_log
    await _emit_log(body.level, body.message, body.branch)
    return {"ok": True}


@router.get("/worker/signal", dependencies=[Depends(_verify_worker)])
async def worker_signal(db: AsyncSession = Depends(get_db)):
    """Check for a force-run signal from the admin panel. Clears the flag after reading."""
    row = (await db.execute(select(SystemSetting).where(SystemSetting.key == "worker_force_run"))).scalar_one_or_none()
    force_run = bool(row and row.value == "true")
    if force_run and row:
        row.value = "false"
        await db.commit()
    return {"force_run": force_run}


@router.post("/worker/result", dependencies=[Depends(_verify_worker)])
async def worker_post_result(
    body: WorkerResultBody,
    db: AsyncSession = Depends(get_db),
):
    """
    Receive a check result from the laptop worker and persist it exactly
    like the scheduler would, including user notifications.
    """
    from app.models import Branch, UserBranchMonitor, User, CheckResult as CR
    from app.services.scheduler import _get_active_subscribers, scheduler_service

    branch_r = await db.execute(select(Branch).where(Branch.id == body.branch_id))
    branch = branch_r.scalar_one_or_none()
    if not branch:
        raise HTTPException(status_code=404, detail="Branch not found")

    active_users = await _get_active_subscribers(db, body.branch_id)
    if not active_users:
        return {"status": "ok", "notified": 0}

    from app.services.scheduler import _emit_log
    # Forward step-by-step logs from the laptop checker (only if not already streamed in real-time)
    if not body.skip_log_replay:
        for log_entry in body.logs:
            level = log_entry.get("level", "info") if isinstance(log_entry, dict) else "info"
            message = log_entry.get("message", str(log_entry)) if isinstance(log_entry, dict) else str(log_entry)
            await _emit_log(level, message, branch.name)

    check_result = {
        "slots_available": body.slots_available,
        "slot_details": body.slot_details,
        "error": body.error,
        "duration": body.duration_seconds,
        "screenshot": None,
        "logs": body.logs,
    }
    # Re-use the scheduler's persist+notify logic so emails/WebSocket work uniformly
    await scheduler_service._persist_and_notify(db, branch, check_result, active_users)

    return {"status": "ok", "notified": len(active_users)}

@router.get("/hardware/{hardware_id}/usage")
@limiter.limit("30/minute")
async def get_hardware_usage(request: Request, hardware_id: str, db: AsyncSession = Depends(get_db)):
    "Fetch usage counts for a hardware id."
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    from sqlalchemy import select
    from app.models import HardwareUsage
    result = await db.execute(select(HardwareUsage).where(HardwareUsage.hardware_id == hardware_id))
    usage = result.scalar_one_or_none()
    
    if usage and usage.last_reset_date == today:
        return {"checks_today": usage.checks_today}
    else:
        return {"checks_today": 0}

@router.post("/hardware/{hardware_id}/increment")
@limiter.limit("10/minute")
async def increment_hardware_usage(request: Request, hardware_id: str, db: AsyncSession = Depends(get_db)):
    "Increment usage count for a hardware id."
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    from sqlalchemy import select
    from app.models import HardwareUsage
    result = await db.execute(select(HardwareUsage).where(HardwareUsage.hardware_id == hardware_id))
    usage = result.scalar_one_or_none()
    
    if usage:
        if usage.last_reset_date != today:
            usage.checks_today = 1
            usage.last_reset_date = today
        else:
            usage.checks_today += 1
    else:
        usage = HardwareUsage(hardware_id=hardware_id, checks_today=1, last_reset_date=today)
        db.add(usage)
        
    await db.commit()
    return {"status": "ok", "checks_today": usage.checks_today}
