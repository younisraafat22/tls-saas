"""
Monitoring Routes — Check results, live status for user dashboard, desktop app reporting,
and license verification / deactivation for the desktop app.
"""

import logging
import json
from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse
from jose import jwt
from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)
from pydantic import BaseModel
from sqlalchemy import select, func, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from app.database import get_db
from app.config import settings
from app.models import (
    User, Branch, CheckResult, UserBranchMonitor,
    NotificationLog, NotificationLogStatus, NotificationChannel,
    SubscriptionStatus, Subscription, Payment, PaymentStatus,
    SystemSetting, ServiceType, HardwareUsage, PlanType,
)
from app.auth import get_current_user
from app.schemas import (
    CheckResultPublic,
    NotificationLogPublic,
    DesktopCheckReport,
    DesktopEmailRelay,
    DesktopEmailRecipientCheck,
    DesktopHardwareRegister,
)

logger = logging.getLogger("monitoring")

router = APIRouter(prefix="/api/monitoring", tags=["monitoring"])


def _merge_hw_tls_extra(
    existing: dict | None,
    client_count: int | None,
    client_emails: list[str] | None,
) -> dict:
    """Merge TLS email usage onto server-side hardware_usage.extra (survives reinstall)."""
    ex = dict(existing or {})
    emails = {e.strip().lower() for e in (ex.get("tls_emails_used") or []) if isinstance(e, str) and e.strip()}
    if client_emails:
        for e in client_emails:
            if isinstance(e, str) and e.strip():
                emails.add(e.strip().lower())
    sc = int(ex.get("tls_email_change_count") or 0)
    if client_count is not None:
        sc = max(sc, int(client_count))
    ex["tls_email_change_count"] = sc
    ex["tls_emails_used"] = sorted(emails)
    return ex


def _merge_tls_usage_payload(
    existing: dict | None,
    client_count: int | None,
    client_emails: list[str] | None,
) -> dict:
    ex = dict(existing or {})
    emails = {e.strip().lower() for e in (ex.get("tls_emails_used") or []) if isinstance(e, str) and e.strip()}
    if client_emails:
        for e in client_emails:
            if isinstance(e, str) and e.strip():
                emails.add(e.strip().lower())
    sc = int(ex.get("tls_email_change_count") or 0)
    if client_count is not None:
        sc = max(sc, int(client_count))
    ex["tls_email_change_count"] = sc
    ex["tls_emails_used"] = sorted(emails)
    return ex


def _tls_usage_setting_key(user_id: int) -> str:
    return f"tls_email_usage_user_{user_id}"


async def _load_user_tls_usage(db: AsyncSession, user_id: int) -> dict:
    key = _tls_usage_setting_key(user_id)
    row_result = await db.execute(select(SystemSetting).where(SystemSetting.key == key))
    row = row_result.scalar_one_or_none()
    if not row or not (row.value or "").strip():
        return {"tls_email_change_count": 0, "tls_emails_used": []}
    try:
        data = json.loads(row.value)
        return _merge_tls_usage_payload(data, None, None)
    except Exception:
        return {"tls_email_change_count": 0, "tls_emails_used": []}


async def _save_user_tls_usage(db: AsyncSession, user_id: int, usage: dict) -> None:
    key = _tls_usage_setting_key(user_id)
    row_result = await db.execute(select(SystemSetting).where(SystemSetting.key == key))
    row = row_result.scalar_one_or_none()
    payload = json.dumps(_merge_tls_usage_payload(usage, None, None), ensure_ascii=False)
    if row:
        row.value = payload
    else:
        db.add(SystemSetting(key=key, value=payload))


# For desktop-app purchases, users can be "active" based on an approved
# Payment row, without a Subscription row.
# The website dashboard still needs an `expires_at` value, so we derive it from:
#   Payment.processed_at + desktop plan duration (based on plan_key)
#
# Note: the desktop app license file expiry is computed on local activation time,
# so this is an approximation used to fix missing dashboard expiry (shows `—`).
_DESKTOP_PLAN_DURATION_DAYS: dict[str, int] = {
    "trial": 1,
    "test_1d": 1,
    "legalization": 30,
    "visa": 30,
    "legalization_monthly": 30,
    "visa_monthly": 30,
    "all_in_one": 30,
    "all_in_one_monthly": 30,
    "premium": 30,
    "premium_monthly": 30,
    "legalization_quarterly": 90,
    "visa_quarterly": 90,
    "all_in_one_quarterly": 90,
    "premium_quarterly": 90,
    "premium_annual": 365,
}

_DESKTOP_PLAN_DURATION_HOURS: dict[str, int] = {
}


def _desktop_plan_base_type(plan_key: str | None) -> str:
    pk = (plan_key or "").strip().lower()
    if pk.startswith("premium"):
        return "premium"
    if pk.startswith("all_in_one"):
        return "all_in_one"
    if pk.startswith("visa"):
        return "visa"
    if pk.startswith("legalization"):
        return "legalization"
    return pk or "desktop"


def _calc_desktop_expires_at(plan_key: str | None, processed_at: datetime | None) -> datetime | None:
    if not plan_key or processed_at is None:
        return None

    pk = plan_key.strip().lower()
    base = processed_at
    if base.tzinfo is None:
        base = base.replace(tzinfo=timezone.utc)

    hours = _DESKTOP_PLAN_DURATION_HOURS.get(pk)
    if hours is not None:
        return base + timedelta(hours=hours)

    days = _DESKTOP_PLAN_DURATION_DAYS.get(pk)
    if days is not None:
        return base + timedelta(days=days)

    return None


async def _branch_row_for_source(
    db: AsyncSession,
    user: User,
    branch: Branch,
    source_mode: str | None,
) -> dict:
    """
    Build monitored-branch snapshot. source_mode: None = latest check any origin;
    'server' = latest server job (source server or null); 'desktop' = desktop app only.
    """
    conds = [
        CheckResult.branch_id == branch.id,
        CheckResult.user_id == user.id,
    ]
    if source_mode == "server":
        conds.append(or_(CheckResult.source == "server", CheckResult.source.is_(None)))
    elif source_mode == "desktop":
        conds.append(CheckResult.source == "desktop")

    latest = await db.execute(
        select(CheckResult)
        .where(and_(*conds))
        .order_by(CheckResult.checked_at.desc())
        .limit(1)
    )
    check = latest.scalar_one_or_none()

    today_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    today_conds = [*conds, CheckResult.checked_at >= today_start]
    checks_today_result = await db.execute(
        select(func.count(CheckResult.id)).where(and_(*today_conds))
    )
    checks_today = checks_today_result.scalar() or 0

    return {
        "branch_id": branch.id,
        "branch_name": branch.name,
        "service_type": branch.service_type.value,
        "is_active": branch.is_active,
        "last_check": check.checked_at.isoformat() if check else None,
        "last_slots_available": check.slots_available if check else None,
        "last_slot_details": check.slot_details if check else None,
        "checks_today": checks_today,
    }


async def _total_checks_for_source(
    db: AsyncSession,
    user: User,
    source_mode: str | None,
) -> int:
    conds = [
        CheckResult.user_id == user.id,
        CheckResult.user_id.isnot(None),
        CheckResult.checked_at >= user.created_at,
    ]
    if source_mode == "server":
        conds.append(or_(CheckResult.source == "server", CheckResult.source.is_(None)))
    elif source_mode == "desktop":
        conds.append(CheckResult.source == "desktop")

    total_checks_result = await db.execute(
        select(func.count(func.distinct(CheckResult.id)))
        .select_from(CheckResult)
        .join(
            UserBranchMonitor,
            and_(
                UserBranchMonitor.user_id == user.id,
                UserBranchMonitor.branch_id == CheckResult.branch_id,
                UserBranchMonitor.is_active == True,
            ),
        )
        .where(and_(*conds))
    )
    return total_checks_result.scalar() or 0


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
    # If this license came from a web payment flow, also cancel linked subscription
    if payment.subscription_id:
        sub_result = await db.execute(select(Subscription).where(Subscription.id == payment.subscription_id))
        sub = sub_result.scalar_one_or_none()
        if sub and sub.status in (SubscriptionStatus.ACTIVE, SubscriptionStatus.PENDING_PAYMENT):
            sub.status = SubscriptionStatus.CANCELLED
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
    # Only keep subscriptions that still have at least one approved linked payment.
    # This hides stale subscriptions after payment/license removal.
    linked_payment_rows = await db.execute(
        select(Payment.subscription_id, Payment.status).where(
            Payment.user_id == user.id,
            Payment.subscription_id.isnot(None),
        )
    )
    payment_statuses_by_sub: dict[int, list[PaymentStatus]] = {}
    for sub_id, status in linked_payment_rows.all():
        if sub_id is None:
            continue
        payment_statuses_by_sub.setdefault(int(sub_id), []).append(status)
    # Filter to truly active (not expired)
    now = datetime.now(timezone.utc)
    active_subs = []
    for s in all_subs:
        linked_statuses = payment_statuses_by_sub.get(s.id, [])
        if not linked_statuses or PaymentStatus.APPROVED not in linked_statuses:
            continue
        exp = s.expires_at
        if exp:
            if exp.tzinfo is None:
                exp = exp.replace(tzinfo=timezone.utc)
            if exp > now:
                active_subs.append(s)
    sub = active_subs[0] if active_subs else None
    is_active = len(active_subs) > 0
    desktop_expires_at: datetime | None = None

    # Desktop license entitlements can coexist with website subscriptions.
    paid = await db.execute(
        select(Payment).where(
            Payment.user_id == user.id,
            Payment.status == PaymentStatus.APPROVED,
            Payment.license_key.isnot(None),
        ).order_by(Payment.processed_at.desc())
    )
    paid_rows = paid.scalars().all()
    if paid_rows:
        is_active = True
        if desktop_expires_at is None:
            desktop_expires_at = _calc_desktop_expires_at(paid_rows[0].plan_key, paid_rows[0].processed_at)

    plan_types = [s.plan.plan_type.value for s in active_subs if s.plan]
    plan_types.extend(_desktop_plan_base_type(p.plan_key) for p in paid_rows)
    plan_types = list(dict.fromkeys(plan_types))

    primary_plan_type = None
    if "premium" in plan_types:
        primary_plan_type = "premium"
    elif plan_types:
        primary_plan_type = plan_types[0]

    has_premium_sub = any(s.plan and s.plan.plan_type == PlanType.PREMIUM for s in active_subs)
    premium_expires_at: datetime | None = None
    if has_premium_sub:
        exp_candidates = [
            s.expires_at for s in active_subs
            if s.plan and s.plan.plan_type == PlanType.PREMIUM and s.expires_at
        ]
        if exp_candidates:
            premium_expires_at = max(exp_candidates)
            if premium_expires_at.tzinfo is None:
                premium_expires_at = premium_expires_at.replace(tzinfo=timezone.utc)

    # Get monitored branches with latest results (combined + per-entitlement for dashboard split)
    monitors = await db.execute(
        select(UserBranchMonitor, Branch)
        .join(Branch, UserBranchMonitor.branch_id == Branch.id)
        .where(UserBranchMonitor.user_id == user.id, UserBranchMonitor.is_active == True)
    )

    branches = []
    branches_server = []
    branches_desktop = []
    for _monitor, branch in monitors.all():
        branches.append(await _branch_row_for_source(db, user, branch, None))
        if has_premium_sub:
            branches_server.append(await _branch_row_for_source(db, user, branch, "server"))
        if paid_rows:
            branches_desktop.append(await _branch_row_for_source(db, user, branch, "desktop"))

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

    # Total checks for this user, scoped to branches they actively monitor.
    total_checks_result = await db.execute(
        select(func.count(func.distinct(CheckResult.id)))
        .select_from(CheckResult)
        .join(
            UserBranchMonitor,
            and_(
                UserBranchMonitor.user_id == user.id,
                UserBranchMonitor.branch_id == CheckResult.branch_id,
                UserBranchMonitor.is_active == True,
            ),
        )
        .where(
            CheckResult.user_id == user.id,
            CheckResult.user_id.isnot(None),
            CheckResult.checked_at >= user.created_at,
        )
    )
    total_checks = total_checks_result.scalar() or 0

    total_checks_server = await _total_checks_for_source(db, user, "server") if has_premium_sub else 0
    total_checks_desktop = await _total_checks_for_source(db, user, "desktop") if paid_rows else 0

    exp_candidates: list[datetime] = []
    if premium_expires_at:
        exp_candidates.append(premium_expires_at)
    if sub and sub.expires_at:
        se = sub.expires_at
        if se.tzinfo is None:
            se = se.replace(tzinfo=timezone.utc)
        exp_candidates.append(se)
    if desktop_expires_at:
        exp_candidates.append(desktop_expires_at)
    expires_at_top = max(exp_candidates) if exp_candidates else None

    overview = {
        "server": {
            "active": has_premium_sub,
            "expires_at": premium_expires_at.isoformat() if premium_expires_at else None,
            "monitored_branches": branches_server,
            "total_checks": total_checks_server,
        },
        "desktop": {
            "active": bool(paid_rows),
            "expires_at": desktop_expires_at.isoformat() if desktop_expires_at else None,
            "monitored_branches": branches_desktop,
            "total_checks": total_checks_desktop,
            "licenses": [
                {"license_key": p.license_key, "plan_key": p.plan_key or ""}
                for p in paid_rows
                if p.license_key
            ],
        },
    }

    return {
        "subscription_active": is_active,
        "plan_type": primary_plan_type,
        "plan_types": plan_types,
        "payment_pending": pending_payment,
        "maintenance_mode": maintenance_mode,
        "expires_at": expires_at_top.isoformat() if expires_at_top else None,
        "monitored_branches": branches,
        "total_branches_monitored": len(branches),
        "worker_next_run": worker_next_run,
        "total_checks": total_checks,
        "overview": overview,
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


@router.get("/email-monitoring-choice", response_class=HTMLResponse)
async def email_monitoring_choice(token: str, db: AsyncSession = Depends(get_db)):
    """
    Premium appointment email: user chooses to stop server monitoring or keep monitoring.
    Signed token (type monitoring_choice, action stop|continue).
    """
    _err = """
    <!DOCTYPE html><html><head><title>TLS — Link error</title>
    <style>body{font-family:Arial,sans-serif;background:#0a0e27;color:#fff;display:flex;align-items:center;justify-content:center;min-height:100vh;margin:0}
    .box{background:#141832;padding:40px;border-radius:16px;max-width:480px;text-align:center}
    h2{color:#ff4444}p{color:#8892b0}</style></head>
    <body><div class="box"><h2>Invalid or expired link</h2>
    <p>This link may have expired (30 days) or is invalid.</p></div></body></html>
    """
    try:
        payload = jwt.decode(token, settings.JWT_SECRET, algorithms=[settings.JWT_ALGORITHM])
        if payload.get("type") != "monitoring_choice":
            raise ValueError("wrong token type")
        user_id = int(payload["sub"])
        branch_id = int(payload["branch_id"])
        action = (payload.get("action") or "").strip().lower()
    except Exception:
        return HTMLResponse(_err, status_code=400)

    if action == "stop":
        result = await db.execute(
            select(UserBranchMonitor).where(
                UserBranchMonitor.user_id == user_id,
                UserBranchMonitor.branch_id == branch_id,
            )
        )
        monitor = result.scalar_one_or_none()
        if monitor and monitor.is_active:
            monitor.is_active = False
            await db.commit()
        return HTMLResponse(
            """
    <!DOCTYPE html><html><head><title>Monitoring stopped</title>
    <style>body{font-family:Arial,sans-serif;background:#0a0e27;color:#fff;display:flex;align-items:center;justify-content:center;min-height:100vh;margin:0}
    .box{background:#141832;padding:40px;border-radius:16px;max-width:480px;text-align:center}
    h2{color:#00ff88}p{color:#8892b0}</style></head>
    <body><div class="box"><h2>Monitoring stopped</h2>
    <p>Server-side monitoring for this branch has been turned off.</p>
    <p>You can turn it back on anytime from your dashboard.</p></div></body></html>
    """
        )

    if action == "continue":
        return HTMLResponse(
            """
    <!DOCTYPE html><html><head><title>Monitoring continues</title>
    <style>body{font-family:Arial,sans-serif;background:#0a0e27;color:#fff;display:flex;align-items:center;justify-content:center;min-height:100vh;margin:0}
    .box{background:#141832;padding:40px;border-radius:16px;max-width:480px;text-align:center}
    h2{color:#00d9ff}p{color:#8892b0}</style></head>
    <body><div class="box"><h2>We'll keep monitoring</h2>
    <p>Your Premium server checks for this branch will continue as before.</p></div></body></html>
    """
        )

    return HTMLResponse(_err, status_code=400)


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

        desktop_total_checks_result = await db.execute(
            select(func.count(CheckResult.id)).where(
                CheckResult.user_id == payment.user_id,
                CheckResult.user_id.isnot(None),
                CheckResult.source == "desktop",
            )
        )
        desktop_total_checks = desktop_total_checks_result.scalar() or 0

        desktop_last_check_result = await db.execute(
            select(func.max(CheckResult.checked_at)).where(
                CheckResult.user_id == payment.user_id,
                CheckResult.user_id.isnot(None),
                CheckResult.source == "desktop",
            )
        )
        desktop_last_check_at = desktop_last_check_result.scalar()

    # Error emails are sent by the desktop app via /desktop-email-relay (or local SMTP when .env is present).
    # Avoid duplicating the same alert here.

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

    # Desktop app already sends slot notifications (relay/local SMTP).
    # Do not send another backend alert here to avoid duplicate emails.

    return {
        "status": "ok",
        "check_result_id": cr.id,
        "slots_available": body.slots_available,
        "desktop_total_checks": desktop_total_checks,
        "desktop_last_check_at": desktop_last_check_at.isoformat() if desktop_last_check_at else None,
    }


def _simple_email_ok(addr: str) -> bool:
    a = (addr or "").strip()
    if len(a) < 5 or len(a) > 254 or "@" not in a:
        return False
    local, _, domain = a.partition("@")
    return bool(local and domain and "." in domain)


@router.post("/desktop-email-relay/validate-recipient")
async def desktop_email_validate_recipient(
    body: DesktopEmailRecipientCheck,
    db: AsyncSession = Depends(get_db),
):
    """
    Validate the recipient address for desktop relay before saving desktop config.
    Does NOT send an email.
    """
    if not body.license_key or not body.to_email.strip():
        raise HTTPException(400, "license_key and to_email are required")
    if not _simple_email_ok(body.to_email):
        raise HTTPException(400, "Invalid recipient email")

    lk = body.license_key.strip()
    # Trial licenses can use any valid recipient once hardware is registered.
    if lk.upper() == "TRIAL":
        hw = (body.hardware_id or "").strip()
        if len(hw) < 8:
            raise HTTPException(400, "hardware_id is required for trial relay")
        uq = await db.execute(select(HardwareUsage).where(HardwareUsage.hardware_id == hw))
        if not uq.scalar_one_or_none():
            raise HTTPException(
                403,
                "Device not registered for relay — open the app once after install or complete a check",
            )
        return {"status": "ok", "allowed": True}

    pay_result = await db.execute(
        select(Payment).where(
            Payment.license_key.isnot(None),
            Payment.license_key != "",
            func.upper(Payment.license_key) == lk.upper(),
            Payment.status == PaymentStatus.APPROVED,
        ).limit(1)
    )
    payment = pay_result.scalar_one_or_none()
    if not payment:
        raise HTTPException(401, "Invalid or inactive license key")

    if not _hardware_matches(payment.hardware_id, body.hardware_id):
        raise HTTPException(403, "Hardware ID does not match this license")

    user_result = await db.execute(select(User).where(User.id == payment.user_id))
    user = user_result.scalar_one_or_none()
    if not user:
        raise HTTPException(404, "User not found")

    dest = body.to_email.strip().lower()
    allowed = {user.email.strip().lower()}
    if payment.submitter_email and payment.submitter_email.strip():
        allowed.add(payment.submitter_email.strip().lower())

    if dest not in allowed:
        raise HTTPException(
            400,
            "Notification email must be your account email or the email used when purchasing the desktop license",
        )
    return {"status": "ok", "allowed": True}


@router.post("/register-desktop-hardware")
async def register_desktop_hardware(
    body: DesktopHardwareRegister,
    db: AsyncSession = Depends(get_db),
):
    """
    Idempotent: ensure hardware_usage has a row for this device (trial email relay, metrics).
    Merges TLS email usage into extra so limits survive reinstall when hardware_id is unchanged.
    """
    hw = (body.hardware_id or "").strip()
    if len(hw) < 8:
        raise HTTPException(400, "hardware_id is required")

    lk = (body.license_key or "").strip()
    if lk and lk.upper() != "TRIAL":
        pay_result = await db.execute(
            select(Payment).where(
                Payment.license_key.isnot(None),
                Payment.license_key != "",
                func.upper(Payment.license_key) == lk.upper(),
                Payment.status == PaymentStatus.APPROVED,
            ).limit(1)
        )
        payment = pay_result.scalar_one_or_none()
        if payment:
            current = await _load_user_tls_usage(db, payment.user_id)
            merged = _merge_tls_usage_payload(
                current,
                body.tls_email_change_count,
                body.tls_emails_used,
            )
            await _save_user_tls_usage(db, payment.user_id, merged)
            await db.commit()
            return {
                "status": "ok",
                "registered": False,
                "scope": "subscription_user",
                "tls_email_change_count": merged.get("tls_email_change_count", 0),
                "tls_emails_used": merged.get("tls_emails_used", []),
            }

    result = await db.execute(select(HardwareUsage).where(HardwareUsage.hardware_id == hw))
    row = result.scalar_one_or_none()
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    merged = _merge_hw_tls_extra(
        row.extra if row else None,
        body.tls_email_change_count,
        body.tls_emails_used,
    )

    if row:
        row.extra = merged
        await db.commit()
        return {
            "status": "ok",
            "registered": False,
            "tls_email_change_count": merged.get("tls_email_change_count", 0),
            "tls_emails_used": merged.get("tls_emails_used", []),
        }

    db.add(
        HardwareUsage(
            hardware_id=hw,
            checks_today=0,
            last_reset_date=today,
            extra=merged,
        )
    )
    await db.commit()
    return {
        "status": "ok",
        "registered": True,
        "scope": "hardware",
        "tls_email_change_count": merged.get("tls_email_change_count", 0),
        "tls_emails_used": merged.get("tls_emails_used", []),
    }


@router.get("/license/{license_key}/tls-email-usage")
async def get_license_tls_email_usage(license_key: str, db: AsyncSession = Depends(get_db)):
    lk = (license_key or "").strip()
    if not lk:
        raise HTTPException(400, "license_key is required")

    pay_result = await db.execute(
        select(Payment).where(
            Payment.license_key.isnot(None),
            Payment.license_key != "",
            func.upper(Payment.license_key) == lk.upper(),
            Payment.status == PaymentStatus.APPROVED,
        ).limit(1)
    )
    payment = pay_result.scalar_one_or_none()
    if not payment:
        raise HTTPException(404, "License not found")

    usage = await _load_user_tls_usage(db, payment.user_id)
    return {
        "scope": "subscription_user",
        "tls_email_change_count": usage.get("tls_email_change_count", 0),
        "tls_emails_used": usage.get("tls_emails_used", []),
    }


@router.post("/desktop-email-relay")
async def desktop_email_relay(
    body: DesktopEmailRelay,
    db: AsyncSession = Depends(get_db),
):
    """
    Send an HTML email using server SMTP. Used by the installed desktop app when
    ADMIN_EMAIL / ADMIN_EMAIL_PASSWORD are not available locally (PyInstaller builds).
    Paid licenses: license key + hardware must match Payment; recipient must match user/submitter email.
    Trial: key TRIAL + hardware_id registered via /register-desktop-hardware; any valid recipient.
    """
    if not body.license_key or not body.to_email.strip():
        raise HTTPException(400, "license_key and to_email are required")

    if not _simple_email_ok(body.to_email):
        raise HTTPException(400, "Invalid recipient email")

    from app.services.email_service import email_service

    lk = body.license_key.strip()
    # ── Trial (local license file key is literally "TRIAL" — no Payment row) ──
    if lk.upper() == "TRIAL":
        hw = (body.hardware_id or "").strip()
        if len(hw) < 8:
            raise HTTPException(400, "hardware_id is required for trial relay")

        uq = await db.execute(select(HardwareUsage).where(HardwareUsage.hardware_id == hw))
        if not uq.scalar_one_or_none():
            raise HTTPException(
                403,
                "Device not registered for relay — open the app once after install or complete a check",
            )

        ok = email_service.send(
            to_email=body.to_email.strip(),
            subject=body.subject[:998] if body.subject else "TLS Appointment Checker",
            html_body=body.html_body[:500_000] if body.html_body else "<p></p>",
        )
        if not ok:
            raise HTTPException(503, "Email could not be sent (server SMTP unavailable)")
        return {"status": "ok", "sent": True}

    # ── Paid license (case-insensitive key match — Postgres/SQLite) ─────────
    pay_result = await db.execute(
        select(Payment).where(
            Payment.license_key.isnot(None),
            Payment.license_key != "",
            func.upper(Payment.license_key) == lk.upper(),
            Payment.status == PaymentStatus.APPROVED,
        ).limit(1)
    )
    payment = pay_result.scalar_one_or_none()
    if not payment:
        raise HTTPException(401, "Invalid or inactive license key")

    if not _hardware_matches(payment.hardware_id, body.hardware_id):
        raise HTTPException(403, "Hardware ID does not match this license")

    user_result = await db.execute(select(User).where(User.id == payment.user_id))
    user = user_result.scalar_one_or_none()
    if not user:
        raise HTTPException(404, "User not found")

    dest = body.to_email.strip().lower()
    allowed = {user.email.strip().lower()}
    if payment.submitter_email and payment.submitter_email.strip():
        allowed.add(payment.submitter_email.strip().lower())

    if dest not in allowed:
        raise HTTPException(
            400,
            "Notification email must be your account email or the email used when purchasing the desktop license",
        )

    ok = email_service.send(
        to_email=body.to_email.strip(),
        subject=body.subject[:998] if body.subject else "TLS Appointment Checker",
        html_body=body.html_body[:500_000] if body.html_body else "<p></p>",
    )
    if not ok:
        raise HTTPException(503, "Email could not be sent (server SMTP unavailable)")
    return {"status": "ok", "sent": True}


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
    screenshot_b64: str | None = None
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
    maint_r = await db.execute(select(SystemSetting).where(SystemSetting.key == "maintenance_mode"))
    maint = maint_r.scalar_one_or_none()
    if maint and (maint.value or "").strip().lower() == "true":
        return {"jobs": [], "paused": True, "maintenance_mode": True}

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
    """Check for worker control signals from the admin panel. Clears flags after reading."""
    force_row = (await db.execute(select(SystemSetting).where(SystemSetting.key == "worker_force_run"))).scalar_one_or_none()
    restart_row = (await db.execute(select(SystemSetting).where(SystemSetting.key == "worker_restart_laptop"))).scalar_one_or_none()

    force_run = bool(force_row and force_row.value == "true")
    restart_laptop = bool(restart_row and restart_row.value == "true")

    changed = False
    if force_run and force_row:
        force_row.value = "false"
        changed = True
    if restart_laptop and restart_row:
        restart_row.value = "false"
        changed = True
    if changed:
        await db.commit()

    return {"force_run": force_run, "restart_laptop": restart_laptop}


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
    if body.screenshot_b64:
        try:
            import base64 as _b64
            check_result["screenshot"] = _b64.b64decode(body.screenshot_b64)
        except Exception:
            check_result["screenshot"] = None
    # Re-use the scheduler's persist+notify logic so emails/WebSocket work uniformly
    await scheduler_service._persist_and_notify(db, branch, check_result, active_users)

    return {"status": "ok", "notified": len(active_users)}

@router.get("/hardware/{hardware_id}/usage")
@limiter.limit("30/minute")
async def get_hardware_usage(request: Request, hardware_id: str, db: AsyncSession = Depends(get_db)):
    "Fetch usage counts and TLS email usage for a hardware id."
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    from sqlalchemy import select
    from app.models import HardwareUsage
    result = await db.execute(select(HardwareUsage).where(HardwareUsage.hardware_id == hardware_id))
    usage = result.scalar_one_or_none()

    checks = 0
    if usage and usage.last_reset_date == today:
        checks = usage.checks_today or 0

    extra = (usage.extra or {}) if usage else {}
    tls_email_change_count = int(extra.get("tls_email_change_count") or 0)
    tls_emails_used = list(extra.get("tls_emails_used") or [])

    return {
        "checks_today": checks,
        "tls_email_change_count": tls_email_change_count,
        "tls_emails_used": tls_emails_used,
    }

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
