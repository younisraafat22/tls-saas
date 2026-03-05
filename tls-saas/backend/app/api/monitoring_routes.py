"""
Monitoring Routes — Check results, live status for user dashboard, desktop app reporting,
and license verification / deactivation for the desktop app.
"""

import logging
from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, Depends, HTTPException
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
    SystemSetting, ServiceType,
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
      1. Revocation check (sends license_key) — returns is_active status
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
            # Key is valid (HMAC checks out) but not in DB — allow it.
            return {"found": True, "is_active": True, "plan": parsed["plan"]}

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
    if payment.hardware_id and payment.hardware_id != body.hardware_id:
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

    return {
        "subscription_active": is_active,
        "plan_type": sub.plan.plan_type.value if sub and sub.plan else None,
        "plan_types": plan_types,
        "payment_pending": pending_payment,
        "maintenance_mode": maintenance_mode,
        "expires_at": sub.expires_at.isoformat() if sub and sub.expires_at else None,
        "monitored_branches": branches,
        "total_branches_monitored": len(branches),
    }


@router.get("/results")
async def check_results(
    branch_id: int | None = None,
    limit: int = 20,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get recent check results belonging to this user."""
    query = (
        select(CheckResult, Branch)
        .join(Branch, CheckResult.branch_id == Branch.id)
        # Only return results for branches this user actually has a monitor entry for.
        # This prevents orphaned or incorrectly associated records from leaking to other users.
        .join(
            UserBranchMonitor,
            and_(
                UserBranchMonitor.user_id == user.id,
                UserBranchMonitor.branch_id == CheckResult.branch_id,
            ),
        )
        .where(CheckResult.user_id == user.id)
    )

    if branch_id:
        query = query.where(CheckResult.branch_id == branch_id)

    query = query.order_by(CheckResult.checked_at.desc()).limit(min(limit, 100))
    result = await db.execute(query)

    return [
        CheckResultPublic(
            id=cr.id,
            branch_name=b.name,
            branch_service_type=b.service_type,
            checked_at=cr.checked_at,
            slots_available=cr.slots_available,
            slot_details=cr.slot_details,
            duration_seconds=cr.duration_seconds,
            error=cr.error or "",
        )
        for cr, b in result.all()
    ]


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
