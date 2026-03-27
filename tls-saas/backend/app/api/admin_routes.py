"""
Admin Dashboard API — Full control over users, payments, monitoring, settings.
"""

from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect
from sqlalchemy import select, func, and_, or_, update, text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from app.database import get_db
from app.models import (
    AppRating,
    AppDownload,
    FoundAppointment,
    User, Plan, Subscription, Branch, Payment, CheckResult,
    NotificationLog, ServiceAccount, SystemSetting, ActivityLog,
    AdminNotification, SupportInquiry,
    UserBranchMonitor,
    PlanType, SubscriptionStatus, PaymentStatus, PaymentMethod, ServiceType,
    NotificationLogStatus,
)
from app.auth import get_current_admin, decode_token
from app.config import settings
from app.schemas import (
    DashboardStats, PaymentPublic, PaymentApproveRequest,
    PaymentRejectRequest, PlanUpdate, ServiceAccountCreate,
    ServiceAccountPublic, AdminUserUpdate, SystemSettingUpdate,
    MessageResponse, AdminNotificationPublic, SupportInquiryPublic, ReplyInquiryRequest, UpdateInquiryStatusRequest,
)
from app.websocket import ws_manager

router = APIRouter(prefix="/api/admin", tags=["admin"])


# ── Dashboard Stats ──────────────────────────────────────────────────

@router.get("/dashboard", response_model=DashboardStats)
async def dashboard_stats(
    admin=Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    today = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    now = datetime.now(timezone.utc)

    total_users = (await db.execute(
        select(func.count(User.id))
        .where(User.is_admin == False, User.email.not_like(r"deleted\_%@deleted.invalid"))
    )).scalar() or 0
    active_subs = (await db.execute(
        select(func.count(func.distinct(Subscription.user_id)))
        .join(User, Subscription.user_id == User.id)
        .where(
            Subscription.status == SubscriptionStatus.ACTIVE,
            User.is_admin == False,
            User.email.not_like(r"deleted\_%@deleted.invalid"),
            or_(Subscription.expires_at.is_(None), Subscription.expires_at > now),
        )
    )).scalar() or 0
    # Defensive clamp: dashboard should never show more active subscribers than total users.
    active_subs = min(active_subs, total_users)
    pending_payments = (await db.execute(
        select(func.count(Payment.id))
        .where(Payment.status == PaymentStatus.PENDING)
    )).scalar() or 0
    total_revenue = (await db.execute(
        select(func.coalesce(func.sum(Payment.amount), 0))
        .where(Payment.status == PaymentStatus.APPROVED)
    )).scalar() or 0
    checks_today = (await db.execute(
        select(func.count(CheckResult.id))
        .where(CheckResult.checked_at >= today)
    )).scalar() or 0
    slots_found = (await db.execute(
        select(func.count(CheckResult.id))
        .where(CheckResult.checked_at >= today, CheckResult.slots_available == True)
    )).scalar() or 0
    notifs_today = (await db.execute(
        select(func.count(NotificationLog.id))
        .where(NotificationLog.sent_at >= today)
    )).scalar() or 0

    total_licenses = (await db.execute(
        select(func.count(Payment.id))
        .where(Payment.hardware_id != None)
    )).scalar() or 0
    active_licenses = (await db.execute(
        select(func.count(Payment.id))
        .where(Payment.hardware_id != None, Payment.status == PaymentStatus.APPROVED)
    )).scalar() or 0
    pending_licenses = (await db.execute(
        select(func.count(Payment.id))
        .where(Payment.hardware_id != None, Payment.status == PaymentStatus.PENDING)
    )).scalar() or 0

    total_downloads = (await db.execute(
        select(func.count(AppDownload.id))
    )).scalar() or 0

    rating_filter = and_(AppRating.comment.is_not(None), AppRating.comment != "")
    avg_rating = (await db.execute(
        select(func.avg(AppRating.rating)).where(rating_filter)
    )).scalar()

    total_appointments_found = (await db.execute(
        select(func.count(FoundAppointment.id))
    )).scalar() or 0

    service_accounts_count = (await db.execute(
        select(func.count(ServiceAccount.id))
    )).scalar() or 0

    # Recent pending payments (all types, for dashboard quick view)
    recent_pending_result = await db.execute(
        select(Payment, User)
        .join(User, Payment.user_id == User.id)
        .where(Payment.status == PaymentStatus.PENDING)
        .order_by(Payment.created_at.desc())
        .limit(5)
    )
    recent_pending = [
        {
            "id": p.id,
            "user_email": p.submitter_email or u.email,
            "method": str(p.method.value if hasattr(p.method, 'value') else p.method).replace('_', ' '),
            "reference": p.reference or "",
            "amount": p.amount,
            "created_at": p.created_at.isoformat() if p.created_at else None,
        }
        for p, u in recent_pending_result.all()
    ]

    # Recent activity log
    activity_result = await db.execute(
        select(ActivityLog, User)
        .join(User, ActivityLog.actor_id == User.id, isouter=True)
        .order_by(ActivityLog.id.desc())
        .limit(8)
    )
    recent_activity = [
        {
            "action": a.action,
            "user_email": u.email if u else "system",
            "created_at": a.created_at.isoformat() if a.created_at else None,
        }
        for a, u in activity_result.all()
    ]

    return DashboardStats(
        total_users=total_users,
        active_subscriptions=active_subs,
        pending_payments=pending_payments,
        total_revenue=total_revenue,
        checks_today=checks_today,
        slots_found_today=slots_found,
        notifications_sent_today=notifs_today,
        total_licenses=total_licenses,
        active_licenses=active_licenses,
        pending_licenses=pending_licenses,
        total_downloads=total_downloads,
        average_rating=float(avg_rating) if avg_rating is not None else 0.0,
        total_appointments_found=total_appointments_found,
        service_accounts=service_accounts_count,
        scheduler_running=True,
        recent_pending_payments=recent_pending,
        recent_activity=recent_activity,
    )


# ── User Management ─────────────────────────────────────────────────

@router.get("/users")
async def list_users(
    page: int = 1,
    per_page: int = 20,
    search: str = "",
    admin=Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    query = (
        select(User)
        .options(
            selectinload(User.subscriptions).selectinload(Subscription.plan),
        )
        .where(
            User.is_admin == False,
            User.email.not_like(r"deleted\_%@deleted.invalid"),
        )
        .order_by(User.created_at.desc())
    )
    if search:
        query = query.where(
            User.email.ilike(f"%{search}%") | User.full_name.ilike(f"%{search}%")
        )

    # Count total
    count_query = (
        select(func.count(User.id))
        .where(
            User.is_admin == False,
            User.email.not_like(r"deleted\_%@deleted.invalid"),
        )
    )
    if search:
        count_query = count_query.where(
            User.email.ilike(f"%{search}%") | User.full_name.ilike(f"%{search}%")
        )
    total = (await db.execute(count_query)).scalar() or 0

    # Paginate
    result = await db.execute(
        query.offset((page - 1) * per_page).limit(per_page)
    )
    users = result.scalars().all()

    items = []
    for u in users:
        # Find best subscription: prefer ACTIVE, then PENDING_PAYMENT
        active_sub = None
        pending_sub = None
        for s in (u.subscriptions or []):
            if s.status == SubscriptionStatus.ACTIVE:
                active_sub = s
            elif s.status == SubscriptionStatus.PENDING_PAYMENT:
                pending_sub = s

        sub = active_sub or pending_sub
        if active_sub:
            sub_status = "active"
        elif pending_sub:
            sub_status = "pending_payment"
        else:
            sub_status = "none"

        items.append({
            "id": u.id,
            "email": u.email,
            "full_name": u.full_name,
            "phone": u.phone,
            "is_active": u.is_active,
            "is_admin": u.is_admin,
            "created_at": u.created_at.isoformat() if u.created_at else None,
            "last_login": u.last_login.isoformat() if u.last_login else None,
            "subscription_status": sub_status,
            "plan_name": sub.plan.display_name if sub and sub.plan else None,
            "subscription_expires": active_sub.expires_at.isoformat() if active_sub and active_sub.expires_at else None,
        })

    return {
        "items": items,
        "total": total,
        "page": page,
        "per_page": per_page,
        "pages": (total + per_page - 1) // per_page,
    }


@router.patch("/users/{user_id}", response_model=MessageResponse)
async def update_user(
    user_id: int,
    body: AdminUserUpdate,
    admin=Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(404, "User not found")

    if body.is_active is not None:
        user.is_active = body.is_active
        # When deactivating, cancel all active subscriptions and disable branch monitors
        if not body.is_active:
            await db.execute(
                text(
                    "UPDATE subscriptions SET status = 'cancelled' "
                    "WHERE user_id = :uid AND status IN ('active', 'pending_payment')"
                ),
                {"uid": user_id},
            )
            await db.execute(
                text("UPDATE user_branch_monitors SET is_active = 0 WHERE user_id = :uid"),
                {"uid": user_id},
            )
    if body.is_admin is not None:
        user.is_admin = body.is_admin

    db.add(ActivityLog(
        actor_id=admin.id,
        action="user_updated",
        details={"user_id": user_id, "changes": body.model_dump(exclude_none=True)},
    ))
    await db.commit()
    return MessageResponse(message=f"User {user.email} updated")


@router.delete("/users/{user_id}", response_model=MessageResponse)
async def delete_user(
    user_id: int,
    admin=Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(404, "User not found")
    if user.is_admin:
        raise HTTPException(400, "Cannot delete an admin account")
    email = user.email
    # Collect all license keys belonging to this user and add them to the
    # revoked blacklist BEFORE deleting, so the desktop verify endpoint
    # will correctly block them even after the payment rows are gone.
    import json as _json
    keys_result = await db.execute(
        select(Payment.license_key).where(
            Payment.user_id == user_id,
            Payment.license_key.isnot(None),
            Payment.license_key != "",
        )
    )
    user_license_keys = [row[0] for row in keys_result.fetchall()]
    if user_license_keys:
        revoked_result = await db.execute(
            select(SystemSetting).where(SystemSetting.key == "revoked_license_keys")
        )
        revoked_setting = revoked_result.scalar_one_or_none()
        if revoked_setting:
            try:
                keys_list = _json.loads(revoked_setting.value)
            except Exception:
                keys_list = []
            for k in user_license_keys:
                if k not in keys_list:
                    keys_list.append(k)
            revoked_setting.value = _json.dumps(keys_list)
        else:
            db.add(SystemSetting(key="revoked_license_keys", value=_json.dumps(user_license_keys)))

    # Delete all child records explicitly before deleting the user
    # to avoid FK / NOT NULL constraint errors from ORM nullification
    await db.execute(text("DELETE FROM notification_logs WHERE user_id = :uid"), {"uid": user_id})
    await db.execute(text("DELETE FROM user_branch_monitors WHERE user_id = :uid"), {"uid": user_id})
    await db.execute(text("DELETE FROM payments WHERE user_id = :uid"), {"uid": user_id})
    await db.execute(text("DELETE FROM subscriptions WHERE user_id = :uid"), {"uid": user_id})
    await db.execute(text("DELETE FROM users WHERE id = :uid"), {"uid": user_id})
    db.add(ActivityLog(
        actor_id=admin.id,
        action="user_deleted",
        details={"user_id": user_id, "email": email},
    ))
    await db.commit()
    return MessageResponse(message=f"User {email} deleted")


# ── Payment Management ───────────────────────────────────────────────

@router.get("/payments")
async def list_payments(
    page: int = 1,
    per_page: int = 20,
    status: str = "",
    admin=Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    query = (
        select(Payment, User)
        .join(User, Payment.user_id == User.id)
        .order_by(Payment.created_at.desc())
    )
    if status:
        query = query.where(Payment.status == status)

    count_q = select(func.count(Payment.id))
    if status:
        count_q = count_q.where(Payment.status == status)
    total = (await db.execute(count_q)).scalar() or 0

    result = await db.execute(query.offset((page - 1) * per_page).limit(per_page))

    # Load branch names
    branch_ids = [p.branch_id for p, u in result.all() if p.branch_id]
    result = await db.execute(query.offset((page - 1) * per_page).limit(per_page))
    branch_map: dict = {}
    if branch_ids:
        branches_result = await db.execute(select(Branch).where(Branch.id.in_(branch_ids)))
        branch_map = {b.id: b.name for b in branches_result.scalars().all()}

    result = await db.execute(query.offset((page - 1) * per_page).limit(per_page))
    items = [
        PaymentPublic(
            id=p.id,
            user_id=p.user_id,
            user_email=u.email,
            user_name=u.full_name,
            amount=p.amount,
            currency=p.currency,
            method=p.method,
            reference=p.reference,
            screenshot_data=p.screenshot_data,
            status=p.status,
            admin_notes=p.admin_notes,
            branch_id=p.branch_id,
            branch_name=branch_map.get(p.branch_id, "") if p.branch_id else "",
            hardware_id=p.hardware_id,
            plan_key=p.plan_key,
            submitter_name=p.submitter_name,
            submitter_email=p.submitter_email,
            license_key=p.license_key,
            created_at=p.created_at,
            processed_at=p.processed_at,
        )
        for p, u in result.all()
    ]

    return {
        "items": [i.model_dump() for i in items],
        "total": total,
        "page": page,
        "per_page": per_page,
        "pages": (total + per_page - 1) // per_page,
    }


@router.post("/payments/{payment_id}/approve", response_model=MessageResponse)
async def approve_payment(
    payment_id: int,
    body: PaymentApproveRequest,
    admin=Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Payment)
        .options(selectinload(Payment.subscription))
        .where(Payment.id == payment_id)
    )
    payment = result.scalar_one_or_none()
    if not payment:
        raise HTTPException(404, "Payment not found")
    if payment.status != PaymentStatus.PENDING:
        raise HTTPException(400, "Payment already processed")

    now = datetime.now(timezone.utc)
    payment.status = PaymentStatus.APPROVED
    payment.admin_notes = body.admin_notes
    payment.processed_at = now

    # Activate or extend subscription
    sub = payment.subscription
    if sub:
        # Handle timezone-naive datetimes from SQLite
        sub_expires = sub.expires_at
        if sub_expires and sub_expires.tzinfo is None:
            sub_expires = sub_expires.replace(tzinfo=timezone.utc)
        if sub.status == SubscriptionStatus.ACTIVE and sub_expires and sub_expires > now:
            # Extend existing
            sub.expires_at = sub_expires + timedelta(days=30 * body.months)
        else:
            sub.status = SubscriptionStatus.ACTIVE
            sub.starts_at = now
            sub.expires_at = now + timedelta(days=30 * body.months)

    # Auto-assign branch monitoring based on what user selected during payment
    if payment.branch_id:
        existing = await db.execute(
            select(UserBranchMonitor).where(
                UserBranchMonitor.user_id == payment.user_id,
                UserBranchMonitor.branch_id == payment.branch_id,
            )
        )
        monitor = existing.scalar_one_or_none()
        if monitor:
            monitor.is_active = True
            # Reset created_at so the check_results filter (checked_at >= created_at)
            # doesn't show results from the previous subscription period.
            monitor.created_at = datetime.now(timezone.utc) - timedelta(seconds=5)
        else:
            db.add(UserBranchMonitor(
                user_id=payment.user_id,
                branch_id=payment.branch_id,
                is_active=True,
            ))

    db.add(ActivityLog(
        actor_id=admin.id,
        action="payment_approved",
        details={"payment_id": payment_id, "months": body.months, "branch_id": payment.branch_id},
    ))

    # Reuse existing key on renewals; only generate on first issue.
    license_key = None
    if payment.hardware_id and payment.plan_key:
        license_key = await _find_existing_license_key_for_renewal(db, payment)
        if not license_key:
            license_key = _generate_license_key(payment.plan_key, payment.hardware_id)
        payment.license_key = license_key
    elif payment.hardware_id and not payment.plan_key:
        # Fallback: use plan_type from subscription
        plan_key = "premium"
        if sub and sub.plan_id:
            plan_result = await db.execute(select(Plan).where(Plan.id == sub.plan_id))
            plan_obj = plan_result.scalar_one_or_none()
            if plan_obj:
                plan_key = plan_obj.plan_type.value
        payment.plan_key = plan_key
        license_key = await _find_existing_license_key_for_renewal(db, payment)
        if not license_key:
            license_key = _generate_license_key(plan_key, payment.hardware_id)
        payment.license_key = license_key

    await db.commit()

    # Send subscription activation email (+ license key if generated)
    try:
        from app.services.email_service import email_service
        user_result = await db.execute(select(User).where(User.id == payment.user_id))
        email_user = user_result.scalar_one_or_none()
        if email_user and sub:
            plan_name = (payment.plan_key or "subscription").replace("_", " ").title()
            expires_str = sub.expires_at.strftime("%B %d, %Y") if sub.expires_at else "N/A"
            email_service.send_subscription_activated(
                to_email=email_user.email,
                user_name=email_user.full_name or email_user.email,
                plan_name=plan_name,
                expires_at=expires_str,
            )
            # Also send license key email if one was generated
            if license_key:
                email_service.send_license_key(
                    to_email=email_user.email,
                    customer_name=email_user.full_name or email_user.email,
                    license_key=license_key,
                    plan_name=plan_name,
                )
    except Exception:
        pass  # Never fail payment approval due to email error

    # Notify user via WebSocket
    await ws_manager.send_to_user(payment.user_id, {
        "type": "subscription_activated",
        "message": f"Your subscription has been activated for {body.months} month(s)!" + (f" License key: {license_key}" if license_key else ""),
        "expires_at": sub.expires_at.isoformat() if sub else None,
        "license_key": license_key,
    })

    msg = f"Payment approved. Subscription activated for {body.months} month(s)."
    if license_key:
        msg += f" License key generated: {license_key}"
    return MessageResponse(message=msg)


@router.post("/payments/{payment_id}/reject", response_model=MessageResponse)
async def reject_payment(
    payment_id: int,
    body: PaymentRejectRequest,
    admin=Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Payment).where(Payment.id == payment_id))
    payment = result.scalar_one_or_none()
    if not payment:
        raise HTTPException(404, "Payment not found")
    if payment.status != PaymentStatus.PENDING:
        raise HTTPException(400, "Payment already processed")

    payment.status = PaymentStatus.REJECTED
    payment.admin_notes = body.admin_notes
    payment.processed_at = datetime.now(timezone.utc)

    if payment.subscription_id:
        sub_result = await db.execute(
            select(Subscription).where(Subscription.id == payment.subscription_id)
        )
        sub = sub_result.scalar_one_or_none()
        if sub:
            sub.status = SubscriptionStatus.CANCELLED

    db.add(ActivityLog(
        actor_id=admin.id,
        action="payment_rejected",
        details={"payment_id": payment_id, "notes": body.admin_notes},
    ))
    await db.commit()

    await ws_manager.send_to_user(payment.user_id, {
        "type": "payment_rejected",
        "message": f"Payment rejected. {body.admin_notes}",
    })
    return MessageResponse(message="Payment rejected")


# ── Desktop License Management ───────────────────────────────────────

def _generate_license_key(plan: str, hardware_id: str) -> str:
    """
    Generate a hardware-bound license key using HMAC-SHA256.
    Format: PLAN-HWID8-RANDOM8-SIG16  (matches desktop license_service.py)
    """
    import hashlib, hmac as _hmac, secrets
    secret = settings.LICENSE_HMAC_SECRET
    hw_short = hardware_id[:8].upper()
    rand = secrets.token_hex(4).upper()
    payload = f"{plan}:{hw_short}:{rand}"
    sig = _hmac.new(secret.encode(), payload.encode(), hashlib.sha256).hexdigest()[:16].upper()
    return f"{plan.upper()}-{hw_short}-{rand}-{sig}"


async def _find_existing_license_key_for_renewal(db: AsyncSession, payment: Payment) -> str | None:
    """Return an existing approved key for the same user/device/plan when renewing."""
    if payment.license_key:
        return payment.license_key

    if not payment.hardware_id:
        return None

    filters = [
        Payment.id != payment.id,
        Payment.user_id == payment.user_id,
        Payment.hardware_id == payment.hardware_id,
        Payment.license_key.isnot(None),
        Payment.license_key != "",
        Payment.status == PaymentStatus.APPROVED,
    ]
    if payment.plan_key:
        filters.append(Payment.plan_key == payment.plan_key)

    existing_result = await db.execute(
        select(Payment.license_key)
        .where(*filters)
        .order_by(Payment.processed_at.desc(), Payment.created_at.desc())
        .limit(1)
    )
    row = existing_result.first()
    return row[0] if row and row[0] else None


@router.post("/generate-test-license")
async def generate_test_license(
    body: dict,
    admin=Depends(get_current_admin),
):
    """
    Generate a 2-hour test license for a specific hardware_id.
    Admin-only. Use this to verify that license expiry logic works
    without waiting the full plan duration.
    """
    hardware_id = (body.get("hardware_id") or "").strip()
    if not hardware_id:
        raise HTTPException(status_code=400, detail="hardware_id is required")

    license_key = _generate_license_key("test_2h", hardware_id)
    return {
        "license_key": license_key,
        "plan": "test_2h",
        "duration": "2 hours",
        "note": "Activate this key in the desktop app. The license will expire 2 hours after activation.",
    }


@router.get("/desktop-payments")
async def list_desktop_payments(
    page: int = 1,
    per_page: int = 20,
    status: str = "",
    admin=Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    """List payments submitted from the desktop app (have hardware_id)."""
    from sqlalchemy import and_
    query = (
        select(Payment)
        .where(Payment.hardware_id != None)
        .order_by(Payment.created_at.desc())
    )
    if status:
        query = query.where(Payment.status == status)

    total = (await db.execute(
        select(func.count(Payment.id)).where(Payment.hardware_id != None)
    )).scalar() or 0

    result = await db.execute(query.offset((page - 1) * per_page).limit(per_page))
    payments = result.scalars().all()

    items = [
        {
            "id": p.id,
            "submitter_name": p.submitter_name or "",
            "submitter_email": p.submitter_email or "",
            "hardware_id": p.hardware_id or "",
            "plan_key": p.plan_key or "",
            "amount": p.amount,
            "currency": p.currency,
            "method": p.method,
            "reference": p.reference,
            "has_screenshot": bool(p.screenshot_data),
            "screenshot_data": p.screenshot_data,
            "status": p.status,
            "admin_notes": p.admin_notes,
            "license_key": p.license_key or "",
            "created_at": p.created_at.isoformat() if p.created_at else None,
            "processed_at": p.processed_at.isoformat() if p.processed_at else None,
        }
        for p in payments
    ]

    return {
        "items": items,
        "total": total,
        "page": page,
        "per_page": per_page,
        "pages": (total + per_page - 1) // per_page,
    }


@router.post("/desktop-payments/{payment_id}/generate-license")
async def generate_license(
    payment_id: int,
    admin=Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    """
    Generate a hardware-bound license key for a desktop payment and mark it approved.
    The generated key can then be sent to the buyer.
    """
    result = await db.execute(
        select(Payment)
        .options(selectinload(Payment.subscription))
        .where(Payment.id == payment_id)
    )
    payment = result.scalar_one_or_none()
    if not payment:
        raise HTTPException(404, "Payment not found")
    if not payment.hardware_id:
        raise HTTPException(400, "This payment has no hardware_id — cannot generate license")
    if not payment.plan_key:
        raise HTTPException(400, "This payment has no plan_key — cannot generate license")

    # Renewal behavior: keep the same key if one already exists for this device.
    license_key = await _find_existing_license_key_for_renewal(db, payment)
    if not license_key:
        license_key = _generate_license_key(payment.plan_key, payment.hardware_id)

    # Save the key and mark as approved
    payment.license_key = license_key
    payment.status = PaymentStatus.APPROVED
    payment.processed_at = datetime.now(timezone.utc)
    payment.admin_notes = f"License generated by admin"

    # Activate the linked subscription (if any) so the user management page
    # shows the correct status instead of staying on "Pending Payment".
    now = datetime.now(timezone.utc)
    sub = payment.subscription
    if sub:
        sub_expires = sub.expires_at
        if sub_expires and sub_expires.tzinfo is None:
            sub_expires = sub_expires.replace(tzinfo=timezone.utc)
        if sub.status == SubscriptionStatus.ACTIVE and sub_expires and sub_expires > now:
            sub.expires_at = sub_expires + timedelta(days=30)
        else:
            sub.status = SubscriptionStatus.ACTIVE
            sub.starts_at = now
            sub.expires_at = now + timedelta(days=30)

    db.add(ActivityLog(
        actor_id=admin.id,
        action="license_generated",
        details={"payment_id": payment_id, "plan_key": payment.plan_key, "hardware_id": payment.hardware_id},
    ))
    await db.commit()

    # Auto-email the license key to the customer
    email_sent = False
    if payment.submitter_email:
        try:
            from app.services.email_service import email_service
            email_sent = email_service.send_license_key(
                to_email=payment.submitter_email,
                customer_name=payment.submitter_name or "",
                license_key=license_key,
                plan_name=payment.plan_key or "Premium",
            )
        except Exception as exc:
            import logging
            logging.getLogger("admin").warning(f"Failed to email license to {payment.submitter_email}: {exc}")

    return {
        "success": True,
        "license_key": license_key,
        "plan_key": payment.plan_key,
        "hardware_id": payment.hardware_id,
        "submitter_email": payment.submitter_email or "",
        "email_sent": email_sent,
        "message": f"License key generated and payment approved.{' Email sent to ' + payment.submitter_email + '.' if email_sent else ' Could not email — please send manually.'}",
    }


@router.post("/licenses/create")
async def create_license_directly(
    body: dict,
    admin=Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    """
    Create a license key directly without needing a desktop payment submission.
    Admin provides hardware_id, plan_key, and optional customer info.
    Optionally assign the license to a specific user by providing user_id.
    """
    hardware_id = (body.get("hardware_id") or "").strip()
    plan_key = (body.get("plan_key") or "").strip()
    customer_name = (body.get("customer_name") or "").strip()
    customer_email = (body.get("customer_email") or "").strip()
    notes = (body.get("notes") or "").strip()
    branch_id: int | None = body.get("branch_id") or None
    assigned_user_id: int | None = body.get("user_id") or None

    if not hardware_id:
        raise HTTPException(400, "hardware_id is required")
    if not plan_key:
        raise HTTPException(400, "plan_key is required")

    # Validate branch if provided
    if branch_id:
        branch_result = await db.execute(select(Branch).where(Branch.id == branch_id))
        if not branch_result.scalar_one_or_none():
            raise HTTPException(400, "Branch not found")

    # Validate assigned user if provided
    assigned_user = None
    if assigned_user_id:
        user_result = await db.execute(select(User).where(User.id == assigned_user_id))
        assigned_user = user_result.scalar_one_or_none()
        if not assigned_user:
            raise HTTPException(400, "User not found")

    license_key = _generate_license_key(plan_key, hardware_id)
    now = datetime.now(timezone.utc)

    # Use assigned user if provided, otherwise use admin's user
    license_user_id = assigned_user_id if assigned_user else admin.id
    # If assigning to a user, update customer info from that user if not provided
    if assigned_user and not customer_email:
        customer_email = assigned_user.email
    if assigned_user and not customer_name:
        customer_name = assigned_user.full_name or assigned_user.email

    payment = Payment(
        user_id=license_user_id,
        amount=0,
        currency="EGP",
        method=PaymentMethod.OTHER,
        reference="admin-direct",
        status=PaymentStatus.APPROVED,
        admin_notes=(f"Manually created by admin.{' Assigned to user ' + assigned_user.email + '.' if assigned_user else ''} {notes}".strip()),
        processed_at=now,
        hardware_id=hardware_id,
        plan_key=plan_key,
        submitter_name=customer_name or "Direct Issue",
        submitter_email=customer_email or "",
        license_key=license_key,
        branch_id=branch_id,
    )
    db.add(payment)
    db.add(ActivityLog(
        actor_id=admin.id,
        action="license_created_direct",
        details={
            "plan_key": plan_key,
            "hardware_id": hardware_id,
            "customer_email": customer_email,
            "assigned_to_user_id": assigned_user_id,
        },
    ))
    await db.commit()
    await db.refresh(payment)

    # Auto-email the license key to the customer
    email_sent = False
    if customer_email:
        try:
            from app.services.email_service import email_service
            email_sent = email_service.send_license_key(
                to_email=customer_email,
                customer_name=customer_name or "",
                license_key=license_key,
                plan_name=plan_key,
            )
        except Exception as exc:
            import logging
            logging.getLogger("admin").warning(f"Failed to email license to {customer_email}: {exc}")

    return {
        "success": True,
        "license_key": license_key,
        "payment_id": payment.id,
        "plan_key": plan_key,
        "hardware_id": hardware_id,
        "customer_email": customer_email,
        "email_sent": email_sent,
        "message": f"License created successfully.{' Email sent to ' + customer_email + '.' if email_sent else ''}",
    }


@router.post("/licenses/import")
async def import_existing_license(
    body: dict,
    admin=Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    """
    Import an externally-generated license key into the management system.
    Use this for any key that exists on a device but has no Payment record
    (e.g. keys issued before the database, or via the desktop license_manager).
    The key's HMAC signature is validated before importing.
    """
    import hashlib, hmac as _hmac
    license_key = (body.get("license_key") or "").strip().upper()
    customer_name = (body.get("customer_name") or "").strip()
    customer_email = (body.get("customer_email") or "").strip()
    notes = (body.get("notes") or "").strip()

    if not license_key:
        raise HTTPException(400, "license_key is required")

    # Check it isn't already registered
    existing = (await db.execute(
        select(Payment).where(Payment.license_key == license_key).limit(1)
    )).scalar_one_or_none()
    if existing:
        raise HTTPException(400, f"License key is already registered (payment #{existing.id})")

    # Parse and validate HMAC signature
    parts = license_key.split("-")
    if len(parts) == 4:
        plan_raw, hw, rand, sig = parts
    elif len(parts) == 5:
        plan_raw = f"{parts[0]}_{parts[1]}"
        hw, rand, sig = parts[2], parts[3], parts[4]
    else:
        raise HTTPException(400, "Invalid license key format (expected PLAN-HW-RAND-SIG)")

    plan = plan_raw.lower()
    payload = f"{plan}:{hw}:{rand}"
    expected = _hmac.new(
        settings.LICENSE_HMAC_SECRET.encode(), payload.encode(), hashlib.sha256
    ).hexdigest()[:16].upper()
    if not _hmac.compare_digest(sig, expected):
        raise HTTPException(400, "License key has an invalid signature — cannot import")

    now = datetime.now(timezone.utc)
    payment = Payment(
        user_id=admin.id,
        amount=0,
        currency="EGP",
        method=PaymentMethod.OTHER,
        reference="admin-import",
        status=PaymentStatus.APPROVED,
        admin_notes=(f"Imported by admin. {notes}".strip()),
        processed_at=now,
        hardware_id=hw,  # store the 8-char prefix; full ID is not known
        plan_key=plan,
        submitter_name=customer_name or "Imported",
        submitter_email=customer_email or "",
        license_key=license_key,
    )
    db.add(payment)
    db.add(ActivityLog(
        actor_id=admin.id,
        action="license_imported",
        details={"license_key": license_key, "plan": plan},
    ))
    await db.commit()
    await db.refresh(payment)

    return {
        "success": True,
        "license_key": license_key,
        "payment_id": payment.id,
        "plan_key": plan,
        "message": "License imported successfully. It is now visible and manageable in the admin panel.",
    }


@router.get("/licenses")
async def list_all_licenses(
    page: int = 1,
    per_page: int = 30,
    status: str = "",
    search: str = "",
    admin=Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    """List all license records (payments with hardware_id, ordered newest first)."""
    query = (
        select(Payment)
        .where(Payment.hardware_id != None)
        .order_by(Payment.created_at.desc())
    )
    if status:
        query = query.where(Payment.status == status)
    if search:
        search_lower = f"%{search.lower()}%"
        from sqlalchemy import or_
        query = query.where(
            or_(
                Payment.submitter_email.ilike(search_lower),
                Payment.submitter_name.ilike(search_lower),
                Payment.hardware_id.ilike(search_lower),
                Payment.plan_key.ilike(search_lower),
                Payment.license_key.ilike(search_lower),
            )
        )

    count_q = select(func.count(Payment.id)).where(Payment.hardware_id != None)
    if status:
        count_q = count_q.where(Payment.status == status)
    total = (await db.execute(count_q)).scalar() or 0

    result = await db.execute(query.offset((page - 1) * per_page).limit(per_page))
    payments = result.scalars().all()

    items = [
        {
            "id": p.id,
            "submitter_name": p.submitter_name or "",
            "submitter_email": p.submitter_email or "",
            "hardware_id": p.hardware_id or "",
            "plan_key": p.plan_key or "",
            "amount": p.amount,
            "currency": p.currency,
            "method": p.method,
            "reference": p.reference or "",
            "has_screenshot": bool(p.screenshot_data),
            "screenshot_data": p.screenshot_data,
            "status": p.status,
            "admin_notes": p.admin_notes or "",
            "license_key": p.license_key or "",
            "created_at": p.created_at.isoformat() if p.created_at else None,
            "processed_at": p.processed_at.isoformat() if p.processed_at else None,
            "direct_issue": p.reference == "admin-direct",
        }
        for p in payments
    ]

    return {
        "items": items,
        "total": total,
        "page": page,
        "per_page": per_page,
        "pages": (total + per_page - 1) // per_page,
    }


@router.post("/licenses/{payment_id}/revoke", response_model=MessageResponse)
async def revoke_license(
    payment_id: int,
    admin=Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    """Revoke a license — marks the record as rejected and clears the license key."""
    result = await db.execute(
        select(Payment).where(Payment.id == payment_id).options(selectinload(Payment.subscription))
    )
    payment = result.scalar_one_or_none()
    if not payment:
        raise HTTPException(404, "License record not found")
    if not payment.license_key and payment.status not in (PaymentStatus.APPROVED, PaymentStatus.PENDING):
        raise HTTPException(400, "No active license to revoke")

    payment.status = PaymentStatus.REJECTED
    # Do NOT clear license_key — verify endpoint needs it to return is_active=False
    payment.admin_notes = ((payment.admin_notes or "") + " [REVOKED]").strip()
    payment.processed_at = datetime.now(timezone.utc)

    # Also cancel the linked subscription so it disappears from user management
    if payment.subscription and payment.subscription.status == SubscriptionStatus.ACTIVE:
        payment.subscription.status = SubscriptionStatus.CANCELLED

    db.add(ActivityLog(
        actor_id=admin.id,
        action="license_revoked",
        details={"payment_id": payment_id},
    ))
    await db.commit()
    return MessageResponse(message=f"License #{payment_id} revoked successfully")


@router.post("/licenses/{payment_id}/regenerate")
async def regenerate_license(
    payment_id: int,
    admin=Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    """Re-generate a fresh license key for an existing record (e.g. after hardware change)."""
    result = await db.execute(select(Payment).where(Payment.id == payment_id))
    payment = result.scalar_one_or_none()
    if not payment:
        raise HTTPException(404, "License record not found")
    if not payment.hardware_id:
        raise HTTPException(400, "No hardware_id on this record")
    if not payment.plan_key:
        raise HTTPException(400, "No plan_key on this record")

    new_key = _generate_license_key(payment.plan_key, payment.hardware_id)
    payment.license_key = new_key
    payment.status = PaymentStatus.APPROVED
    payment.processed_at = datetime.now(timezone.utc)
    payment.admin_notes = ((payment.admin_notes or "").replace(" [REVOKED]", "") + " [REGENERATED]").strip()

    db.add(ActivityLog(
        actor_id=admin.id,
        action="license_regenerated",
        details={"payment_id": payment_id, "new_key": new_key},
    ))
    await db.commit()

    return {
        "success": True,
        "license_key": new_key,
        "payment_id": payment_id,
        "message": "License key regenerated successfully.",
    }


@router.delete("/payments/{payment_id}", response_model=MessageResponse)
async def delete_payment(
    payment_id: int,
    admin=Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    """Permanently delete a payment record (for removing test/fake payments)."""
    result = await db.execute(select(Payment).where(Payment.id == payment_id))
    payment = result.scalar_one_or_none()
    if not payment:
        raise HTTPException(404, "Payment not found")

    # If payment has a license key, save it to the revoked blacklist before deleting
    # so the desktop verify endpoint can still block it
    if payment.license_key:
        import json as _json
        revoked_result = await db.execute(
            select(SystemSetting).where(SystemSetting.key == "revoked_license_keys")
        )
        revoked_setting = revoked_result.scalar_one_or_none()
        if revoked_setting:
            try:
                keys_list = _json.loads(revoked_setting.value)
            except Exception:
                keys_list = []
            if payment.license_key not in keys_list:
                keys_list.append(payment.license_key)
            revoked_setting.value = _json.dumps(keys_list)
        else:
            db.add(SystemSetting(key="revoked_license_keys", value=_json.dumps([payment.license_key])))

    # Cancel the linked subscription if it is still pending
    if payment.subscription_id and payment.status == PaymentStatus.PENDING:
        sub_result = await db.execute(
            select(Subscription).where(Subscription.id == payment.subscription_id)
        )
        sub = sub_result.scalar_one_or_none()
        if sub and sub.status == SubscriptionStatus.PENDING_PAYMENT:
            sub.status = SubscriptionStatus.CANCELLED

    await db.delete(payment)
    db.add(ActivityLog(
        actor_id=admin.id,
        action="payment_deleted",
        details={"payment_id": payment_id},
    ))
    await db.commit()
    return MessageResponse(message=f"Payment #{payment_id} deleted")


# ── Plan Management ──────────────────────────────────────────────────

@router.get("/plans")
async def list_all_plans(admin=Depends(get_current_admin), db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Plan).order_by(Plan.sort_order))
    return [
        {
            "id": p.id,
            "plan_type": p.plan_type.value,
            "display_name": p.display_name,
            "description": p.description,
            "price_monthly": p.price_monthly,
            "currency": p.currency,
            "features": p.features,
            "is_active": p.is_active,
            "sort_order": p.sort_order,
        }
        for p in result.scalars().all()
    ]


@router.patch("/plans/{plan_id}", response_model=MessageResponse)
async def update_plan(
    plan_id: int,
    body: PlanUpdate,
    admin=Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Plan).where(Plan.id == plan_id))
    plan = result.scalar_one_or_none()
    if not plan:
        raise HTTPException(404, "Plan not found")

    for field, val in body.model_dump(exclude_none=True).items():
        setattr(plan, field, val)

    await db.commit()
    return MessageResponse(message=f"Plan '{plan.display_name}' updated")


# ── Service Account Management ───────────────────────────────────────

@router.get("/service-accounts")
async def list_service_accounts(
    admin=Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(ServiceAccount, Branch)
        .join(Branch, ServiceAccount.branch_id == Branch.id)
    )
    return [
        ServiceAccountPublic(
            id=sa.id,
            branch_id=sa.branch_id,
            branch_name=b.name,
            email_masked=sa.email_encrypted[:3] + "***" if len(sa.email_encrypted) > 3 else "***",
            is_primary=sa.is_primary,
            is_active=sa.is_active,
            last_used_at=sa.last_used_at,
            last_error=sa.last_error or "",
        ).model_dump()
        for sa, b in result.all()
    ]


@router.post("/service-accounts", response_model=MessageResponse)
async def create_service_account(
    body: ServiceAccountCreate,
    admin=Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    from app.services.checker import encrypt_credential
    sa = ServiceAccount(
        branch_id=body.branch_id,
        email_encrypted=encrypt_credential(body.email),
        password_encrypted=encrypt_credential(body.password),
        is_primary=body.is_primary,
        is_active=True,
    )
    db.add(sa)
    await db.commit()
    return MessageResponse(message="Service account created")


@router.delete("/service-accounts/{account_id}", response_model=MessageResponse)
async def delete_service_account(
    account_id: int,
    admin=Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(ServiceAccount).where(ServiceAccount.id == account_id))
    sa = result.scalar_one_or_none()
    if not sa:
        raise HTTPException(404, "Service account not found")
    await db.delete(sa)
    await db.commit()
    return MessageResponse(message="Service account deleted")


# ── Check Results (Admin view) ───────────────────────────────────────

@router.get("/check-results")
async def admin_check_results(
    branch_id: int | None = None,
    limit: int = 50,
    admin=Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    query = (
        select(CheckResult, Branch)
        .join(Branch, CheckResult.branch_id == Branch.id)
    )
    if branch_id:
        query = query.where(CheckResult.branch_id == branch_id)
    query = query.order_by(CheckResult.checked_at.desc()).limit(limit)

    result = await db.execute(query)
    return [
        {
            "id": cr.id,
            "branch_name": b.name,
            "service_type": b.service_type.value,
            "checked_at": cr.checked_at.isoformat(),
            "slots_available": cr.slots_available,
            "slot_details": cr.slot_details,
            "error": cr.error,
            "duration_seconds": cr.duration_seconds,
        }
        for cr, b in result.all()
    ]


@router.delete("/check-results", response_model=MessageResponse)
async def delete_all_check_results(
    branch_id: int | None = None,
    admin=Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    """Delete all check results, or only those for a specific branch."""
    from sqlalchemy import delete as sa_delete
    stmt = sa_delete(CheckResult)
    if branch_id:
        stmt = stmt.where(CheckResult.branch_id == branch_id)
    result = await db.execute(stmt)
    await db.commit()
    label = f"branch #{branch_id}" if branch_id else "all branches"
    return MessageResponse(message=f"Deleted {result.rowcount} check result(s) for {label}")


@router.delete("/check-results/{result_id}", response_model=MessageResponse)
async def delete_check_result(
    result_id: int,
    admin=Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    """Delete a single check result by ID."""
    res = await db.execute(select(CheckResult).where(CheckResult.id == result_id))
    cr = res.scalar_one_or_none()
    if not cr:
        raise HTTPException(404, "Check result not found")
    await db.delete(cr)
    await db.commit()
    return MessageResponse(message=f"Check result #{result_id} deleted")


# ── System Settings ──────────────────────────────────────────────────

@router.get("/settings")
async def get_settings(admin=Depends(get_current_admin), db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(SystemSetting))
    return {s.key: s.value for s in result.scalars().all()}


@router.post("/settings", response_model=MessageResponse)
async def update_setting(
    body: SystemSettingUpdate,
    admin=Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(SystemSetting).where(SystemSetting.key == body.key))
    setting = result.scalar_one_or_none()
    if setting:
        setting.value = body.value
    else:
        db.add(SystemSetting(key=body.key, value=body.value))
    await db.commit()
    return MessageResponse(message=f"Setting '{body.key}' updated")


@router.post("/settings/bulk", response_model=MessageResponse)
async def update_settings_bulk(
    body: dict[str, str],
    admin=Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    for key, value in body.items():
        result = await db.execute(select(SystemSetting).where(SystemSetting.key == key))
        setting = result.scalar_one_or_none()
        if setting:
            setting.value = str(value)
        else:
            db.add(SystemSetting(key=key, value=str(value)))

    # If the check interval changed, recalculate worker_next_run so the UI shows the
    # correct countdown immediately (without waiting for the worker's next heartbeat).
    if "check_interval_minutes" in body:
        try:
            new_interval_sec = int(body["check_interval_minutes"]) * 60
            last_run_r = await db.execute(
                select(SystemSetting).where(SystemSetting.key == "worker_last_run")
            )
            last_run_row = last_run_r.scalar_one_or_none()
            if last_run_row and last_run_row.value:
                from datetime import datetime, timezone, timedelta
                last_run_dt = datetime.fromisoformat(last_run_row.value)
                if last_run_dt.tzinfo is None:
                    last_run_dt = last_run_dt.replace(tzinfo=timezone.utc)
                new_next_run = (last_run_dt + timedelta(seconds=new_interval_sec)).isoformat()
                next_run_r = await db.execute(
                    select(SystemSetting).where(SystemSetting.key == "worker_next_run")
                )
                next_run_row = next_run_r.scalar_one_or_none()
                if next_run_row:
                    next_run_row.value = new_next_run
                else:
                    db.add(SystemSetting(key="worker_next_run", value=new_next_run))
        except Exception:
            pass  # Non-fatal — worker will correct it on next heartbeat

    await db.commit()
    return MessageResponse(message=f"{len(body)} settings updated")


# ── Activity Log ─────────────────────────────────────────────────────

@router.get("/activity-log")
async def activity_log(
    limit: int = 50,
    admin=Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(ActivityLog).order_by(ActivityLog.created_at.desc()).limit(limit)
    )
    return [
        {
            "id": a.id,
            "actor_id": a.actor_id,
            "action": a.action,
            "details": a.details,
            "created_at": a.created_at.isoformat(),
        }
        for a in result.scalars().all()
    ]


# ── Scheduler Control ───────────────────────────────────────────────

@router.post("/checker/start", response_model=MessageResponse)
async def start_checker(admin=Depends(get_current_admin), db: AsyncSession = Depends(get_db)):
    import os as _os
    if _os.environ.get("WORKER_MODE", "false").lower() == "true":
        setting = (await db.execute(select(SystemSetting).where(SystemSetting.key == "scheduler_running"))).scalar_one_or_none()
        if setting:
            setting.value = "true"
        else:
            db.add(SystemSetting(key="scheduler_running", value="true"))
        await db.commit()
        return MessageResponse(message="Monitoring enabled — laptop worker will pick up jobs on its next cycle.")
    from app.services.scheduler import scheduler_service
    # Read custom interval from system settings (if admin changed it)
    interval_setting = (await db.execute(
        select(SystemSetting).where(SystemSetting.key == "check_interval_minutes")
    )).scalar_one_or_none()
    if interval_setting:
        try:
            settings.CHECK_INTERVAL_MINUTES = max(5, int(interval_setting.value))
        except (ValueError, TypeError):
            pass
    scheduler_service.start()
    # Persist state so backend auto-resumes after restart
    setting = (await db.execute(select(SystemSetting).where(SystemSetting.key == "scheduler_running"))).scalar_one_or_none()
    if setting:
        setting.value = "true"
    else:
        db.add(SystemSetting(key="scheduler_running", value="true"))
    await db.commit()
    return MessageResponse(message=f"Checker scheduler started (interval: {settings.CHECK_INTERVAL_MINUTES} min)")


@router.post("/checker/stop", response_model=MessageResponse)
async def stop_checker(admin=Depends(get_current_admin), db: AsyncSession = Depends(get_db)):
    import os as _os
    if _os.environ.get("WORKER_MODE", "false").lower() == "true":
        setting = (await db.execute(select(SystemSetting).where(SystemSetting.key == "scheduler_running"))).scalar_one_or_none()
        if setting:
            setting.value = "false"
        else:
            db.add(SystemSetting(key="scheduler_running", value="false"))
        await db.commit()
        return MessageResponse(message="Monitoring paused — laptop worker will stop processing jobs on its next cycle.")
    from app.services.scheduler import scheduler_service
    scheduler_service.stop()
    # Persist state so backend does NOT auto-resume after restart
    setting = (await db.execute(select(SystemSetting).where(SystemSetting.key == "scheduler_running"))).scalar_one_or_none()
    if setting:
        setting.value = "false"
    else:
        db.add(SystemSetting(key="scheduler_running", value="false"))
    await db.commit()
    return MessageResponse(message="Checker scheduler stopped")


@router.get("/checker/status")
async def checker_status(admin=Depends(get_current_admin), db: AsyncSession = Depends(get_db)):
    import os as _os
    worker_mode = _os.environ.get("WORKER_MODE", "false").lower() == "true"
    if worker_mode:
        rows = {r.key: r.value for r in (await db.execute(
            select(SystemSetting).where(SystemSetting.key.in_([
                "scheduler_running", "worker_last_run", "worker_next_run",
                "worker_interval_minutes", "check_interval_minutes",
            ]))
        )).scalars().all()}
        worker_running = rows.get("scheduler_running") == "true"
        # Prefer the user-saved check_interval_minutes; fall back to last worker heartbeat value
        interval = int(rows["check_interval_minutes"]) if rows.get("check_interval_minutes", "").isdigit() else \
                   int(rows["worker_interval_minutes"]) if rows.get("worker_interval_minutes", "").isdigit() else \
                   settings.CHECK_INTERVAL_MINUTES
        return {
            "running": worker_running,
            "worker_mode": True,
            "next_run": rows.get("worker_next_run"),
            "last_run": rows.get("worker_last_run"),
            "interval_minutes": interval,
            "connected_users_ws": ws_manager.connected_users_count,
            "connected_admins_ws": ws_manager.connected_admins_count,
        }
    from app.services.scheduler import scheduler_service
    # Sync is_running with APScheduler's actual state (handles auto-resume after restart)
    apscheduler_running = (
        scheduler_service._scheduler is not None
        and scheduler_service._scheduler.running
    )
    if apscheduler_running and not scheduler_service.is_running:
        scheduler_service.is_running = True

    running = scheduler_service.is_running or apscheduler_running

    # Also check DB-persisted state as fallback (survives worker restarts)
    if not running:
        db_state = (await db.execute(
            select(SystemSetting).where(SystemSetting.key == "scheduler_running")
        )).scalar_one_or_none()
        if db_state and db_state.value == "true":
            # DB says it should be running — auto-restart it
            try:
                # Read custom interval if set
                interval_r = (await db.execute(
                    select(SystemSetting).where(SystemSetting.key == "check_interval_minutes")
                )).scalar_one_or_none()
                if interval_r:
                    try:
                        settings.CHECK_INTERVAL_MINUTES = max(5, int(interval_r.value))
                    except (ValueError, TypeError):
                        pass
                scheduler_service.start()
                running = True
            except Exception:
                pass

    return {
        "running": running,
        "next_run": scheduler_service.next_run_time,
        "last_run": scheduler_service.last_run_time,
        "interval_minutes": settings.CHECK_INTERVAL_MINUTES,
        "connected_users_ws": ws_manager.connected_users_count,
        "connected_admins_ws": ws_manager.connected_admins_count,
    }


# ── Manual Check Trigger ────────────────────────────────────────────

@router.post("/checker/run-now/{branch_id}", response_model=MessageResponse)
async def run_check_now(
    branch_id: int,
    admin=Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    import os as _os
    if _os.environ.get("WORKER_MODE", "false").lower() == "true":
        raise HTTPException(400, "WORKER_MODE=true — manual checks must be run from the laptop worker, not this server.")
    result = await db.execute(select(Branch).where(Branch.id == branch_id))
    branch = result.scalar_one_or_none()
    if not branch:
        raise HTTPException(404, "Branch not found")

    from app.services.scheduler import scheduler_service
    import asyncio
    asyncio.create_task(scheduler_service.check_branch(branch_id))
    return MessageResponse(message=f"Check triggered for '{branch.name}'")


@router.post("/checker/run-all-now", response_model=MessageResponse)
async def run_all_checks_now(
    admin=Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    """Trigger a full check cycle immediately (all active branches)."""
    import os as _os
    if _os.environ.get("WORKER_MODE", "false").lower() == "true":
        # Signal the laptop worker to start a new cycle ASAP (picked up within 30s)
        row = (await db.execute(select(SystemSetting).where(SystemSetting.key == "worker_force_run"))).scalar_one_or_none()
        if row:
            row.value = "true"
        else:
            db.add(SystemSetting(key="worker_force_run", value="true"))
        await db.commit()
        return MessageResponse(message="Force-run signal sent — worker will start a new cycle within 30 seconds")
    from app.services.scheduler import scheduler_service
    import asyncio
    asyncio.create_task(scheduler_service._run_all_checks())
    return MessageResponse(message="Full check cycle started immediately")


@router.post("/checker/restart-worker-laptop", response_model=MessageResponse)
async def restart_worker_laptop(
    admin=Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    """Signal the laptop worker process to restart the host machine."""
    import os as _os
    if _os.environ.get("WORKER_MODE", "false").lower() != "true":
        raise HTTPException(400, "This action is only available when WORKER_MODE=true.")

    row = (await db.execute(select(SystemSetting).where(SystemSetting.key == "worker_restart_laptop"))).scalar_one_or_none()
    if row:
        row.value = "true"
    else:
        db.add(SystemSetting(key="worker_restart_laptop", value="true"))
    await db.commit()
    return MessageResponse(message="Restart signal sent — worker laptop will restart on next signal poll.")


# ── Headless Mode Toggle ─────────────────────────────────────────────

@router.get("/checker/headless")
async def get_headless_mode(admin=Depends(get_current_admin)):
    """Get the current headless mode setting."""
    return {"headless": settings.BROWSER_HEADLESS}


@router.post("/checker/headless", response_model=MessageResponse)
async def toggle_headless_mode(
    body: dict,
    admin=Depends(get_current_admin),
):
    """Toggle headless mode. When False, browser window will be visible for debugging."""
    headless = body.get("headless", True)
    settings.BROWSER_HEADLESS = headless

    # Close existing browser so it relaunches with the new setting
    from app.services.checker import tls_checker
    try:
        # The checker runs in a thread, so just flag it — next check will pick up the setting
        if tls_checker._browser:
            import asyncio
            try:
                await tls_checker.close()
            except Exception:
                tls_checker._browser = None
                tls_checker._playwright = None
    except Exception:
        pass

    mode = "headless" if headless else "visible (non-headless)"
    return MessageResponse(message=f"Browser mode set to {mode}. Takes effect on next check.")


# ── Test Notifications ───────────────────────────────────────────────

@router.post("/test-notification", response_model=MessageResponse)
async def test_notification(
    admin=Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    """Send a test notification via all configured channels to the admin user."""
    from app.services.email_service import email_service

    admin_user = admin
    results = []

    # Test email
    if settings.SMTP_USERNAME and settings.SMTP_PASSWORD:
        ok = email_service.send(
            admin_user.email,
            "Test Notification — TLS Appointment Checker",
            "<h2>✅ Test Notification</h2><p>If you're reading this, email notifications are working!</p>"
        )
        results.append(f"Email: {'✅ sent' if ok else '❌ failed'}")
    else:
        results.append("Email: ⚠️ SMTP not configured")

    # Test Web Push
    if settings.VAPID_PRIVATE_KEY and admin_user.push_subscription:
        try:
            from pywebpush import webpush
            import json
            webpush(
                subscription_info=admin_user.push_subscription,
                data=json.dumps({"title": "Test Notification", "body": "Push notifications are working!"}),
                vapid_private_key=settings.VAPID_PRIVATE_KEY,
                vapid_claims={"sub": f"mailto:{settings.VAPID_CLAIMS_EMAIL}"},
            )
            results.append("Web Push: ✅ sent")
        except Exception as e:
            results.append(f"Web Push: ❌ {str(e)[:80]}")
    elif not settings.VAPID_PRIVATE_KEY:
        results.append("Web Push: ⚠️ VAPID keys not configured")
    else:
        results.append("Web Push: ⚠️ No push subscription for admin")

    return MessageResponse(message=" | ".join(results))


@router.post("/test-appointment-email", response_model=MessageResponse)
async def test_appointment_email(
    admin=Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    """Send a fake appointment-found email to the admin so you can preview the template."""
    from app.services.email_service import email_service
    test_email = "omarraafat6@gmail.com"
    ok = email_service.send_appointment_alert(
        to_email=test_email,
        branch_name="El-Sheikh Zayed",
        service_type="legalization",
        slot_details={"message": "Appointment slots are available — book now before they're gone!"},
        user_name=admin.full_name or "Admin",
    )
    if ok:
        return MessageResponse(message=f"Test appointment alert sent to {test_email} ✅")
    raise HTTPException(500, "Failed to send — check SMTP settings")


# ── Resend License Email ─────────────────────────────────────────────

@router.post("/payments/{payment_id}/resend-email", response_model=MessageResponse)
async def resend_license_email(
    payment_id: int,
    admin=Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    """Resend the license key email for an approved desktop payment."""
    result = await db.execute(select(Payment).where(Payment.id == payment_id))
    payment = result.scalar_one_or_none()
    if not payment:
        raise HTTPException(404, "Payment not found")
    if not payment.license_key:
        raise HTTPException(400, "No license key on this payment — generate one first")
    to_email = payment.submitter_email or ""
    # Fall back to the web user's email if no submitter email
    if not to_email:
        user_result = await db.execute(select(User).where(User.id == payment.user_id))
        u = user_result.scalar_one_or_none()
        if u:
            to_email = u.email
    if not to_email:
        raise HTTPException(400, "No email address on this record")
    from app.services.email_service import email_service
    ok = email_service.send_license_key(
        to_email=to_email,
        customer_name=payment.submitter_name or to_email,
        license_key=payment.license_key,
        plan_name=payment.plan_key or "subscription",
    )
    if ok:
        return MessageResponse(message=f"License key re-sent to {to_email} ✅")
    raise HTTPException(500, "Email delivery failed — check SMTP settings")


# ── User Payment History ─────────────────────────────────────────────

@router.get("/users/{user_id}/payments")
async def user_payment_history(
    user_id: int,
    admin=Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    """Return all payments and subscriptions for a specific user."""
    user_result = await db.execute(select(User).where(User.id == user_id))
    user = user_result.scalar_one_or_none()
    if not user:
        raise HTTPException(404, "User not found")

    payments_result = await db.execute(
        select(Payment)
        .where(Payment.user_id == user_id)
        .order_by(Payment.created_at.desc())
    )
    payments = payments_result.scalars().all()

    return {
        "user_id": user_id,
        "email": user.email,
        "payments": [
            {
                "id": p.id,
                "amount": p.amount,
                "currency": p.currency,
                "method": p.method,
                "reference": p.reference or "",
                "status": p.status,
                "plan_key": p.plan_key or "",
                "license_key": p.license_key or "",
                "hardware_id": p.hardware_id or "",
                "admin_notes": p.admin_notes or "",
                "created_at": p.created_at.isoformat() if p.created_at else None,
                "processed_at": p.processed_at.isoformat() if p.processed_at else None,
            }
            for p in payments
        ],
    }


# ── Admin Password Reset for User ───────────────────────────────────

@router.post("/users/{user_id}/send-password-reset", response_model=MessageResponse)
async def admin_send_password_reset(
    user_id: int,
    admin=Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    """Send a password reset email to a user on behalf of the admin."""
    from app.auth import create_password_reset_token
    from app.services.email_service import email_service
    from app.config import settings as cfg

    # Check SMTP is configured
    if not cfg.SMTP_USERNAME or not cfg.SMTP_PASSWORD:
        raise HTTPException(500, "SMTP email is not configured. Contact server administrator to set SMTP_USERNAME and SMTP_PASSWORD environment variables.")

    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(404, "User not found")

    token = create_password_reset_token(user.id)
    frontend_url = (cfg.FRONTEND_URL or "").rstrip("/")
    reset_url = f"{frontend_url}/reset-password?token={token}"

    ok = email_service.send_password_reset(
        to_email=user.email,
        user_name=user.full_name or user.email,
        reset_url=reset_url,
    )
    if ok:
        db.add(ActivityLog(
            actor_id=admin.id,
            action="admin_password_reset_sent",
            details={"target_user_id": user_id, "email": user.email},
        ))
        await db.commit()
        return MessageResponse(message=f"Password reset email sent to {user.email} ✅")
    raise HTTPException(500, "Failed to send password reset email. Check server logs for details.")


@router.get("/checker/logs")
async def checker_logs(limit: int = 100, admin=Depends(get_current_admin)):
    """Return recent monitoring log entries from the in-memory buffer."""
    from app.services.scheduler import get_recent_logs
    return get_recent_logs(min(limit, 200))


@router.get("/system-logs")
async def system_logs(lines: int = 200, admin=Depends(get_current_admin)):
    """Return recent backend process logs (journalctl on Linux, in-memory buffer elsewhere)."""
    import subprocess
    n = min(lines, 500)
    try:
        result = subprocess.run(
            ["journalctl", "-u", "tls-backend", "--no-pager",
             "-n", str(n), "--output=short-iso"],
            capture_output=True, text=True, timeout=10
        )
        raw = result.stdout.strip() or result.stderr.strip()
        log_lines = raw.split("\n") if raw else []
        if log_lines:
            return {"lines": log_lines, "total": len(log_lines), "source": "journalctl"}
        # journalctl returned empty — fall through to memory buffer
    except (FileNotFoundError, subprocess.TimeoutExpired, Exception):
        pass
    # Fallback: in-memory Python log buffer (always available)
    from app.main import get_system_log_lines
    log_lines = get_system_log_lines(n)
    return {"lines": log_lines, "total": len(log_lines), "source": "memory"}


# ── Admin WebSocket ──────────────────────────────────────────────────

@router.get("/notifications")
async def list_admin_notifications(
    page: int = 1,
    per_page: int = 30,
    unread_only: bool = False,
    category: str = "",
    admin=Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    query = select(AdminNotification).order_by(AdminNotification.created_at.desc())
    if unread_only:
        query = query.where(AdminNotification.is_read == False)
    if category:
        query = query.where(AdminNotification.category == category.strip().lower())

    count_q = select(func.count(AdminNotification.id))
    if unread_only:
        count_q = count_q.where(AdminNotification.is_read == False)
    if category:
        count_q = count_q.where(AdminNotification.category == category.strip().lower())
    total = (await db.execute(count_q)).scalar() or 0

    rows = (await db.execute(query.offset((page - 1) * per_page).limit(per_page))).scalars().all()
    items = [
        AdminNotificationPublic(
            id=n.id,
            category=n.category,
            event_type=n.event_type,
            title=n.title,
            message=n.message,
            payload=n.payload,
            is_read=n.is_read,
            created_at=n.created_at,
            read_at=n.read_at,
        ).model_dump()
        for n in rows
    ]
    return {
        "items": items,
        "total": total,
        "page": page,
        "per_page": per_page,
        "pages": (total + per_page - 1) // per_page,
    }


@router.get("/notifications/counts")
async def admin_notification_counts(
    admin=Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    unread_total = (await db.execute(
        select(func.count(AdminNotification.id)).where(AdminNotification.is_read == False)
    )).scalar() or 0
    unread_payments = (await db.execute(
        select(func.count(AdminNotification.id)).where(
            AdminNotification.is_read == False,
            AdminNotification.category == "payment",
        )
    )).scalar() or 0
    unread_inquiries = (await db.execute(
        select(func.count(AdminNotification.id)).where(
            AdminNotification.is_read == False,
            AdminNotification.category == "inquiry",
        )
    )).scalar() or 0
    return {
        "unread_total": unread_total,
        "unread_payments": unread_payments,
        "unread_inquiries": unread_inquiries,
    }


@router.post("/notifications/{notification_id}/read", response_model=MessageResponse)
async def mark_admin_notification_read(
    notification_id: int,
    admin=Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    row = (await db.execute(
        select(AdminNotification).where(AdminNotification.id == notification_id)
    )).scalar_one_or_none()
    if not row:
        raise HTTPException(404, "Notification not found")
    row.is_read = True
    row.read_at = datetime.now(timezone.utc)
    await db.commit()
    return MessageResponse(message="Notification marked as read")


@router.post("/notifications/read-all", response_model=MessageResponse)
async def mark_all_admin_notifications_read(
    category: str = "",
    admin=Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    q = (
        update(AdminNotification)
        .where(AdminNotification.is_read == False)
        .values(is_read=True, read_at=datetime.now(timezone.utc))
    )
    if category:
        q = q.where(AdminNotification.category == category.strip().lower())
    await db.execute(q)
    await db.commit()
    return MessageResponse(message="Notifications marked as read")


@router.delete("/notifications/{notification_id}", response_model=MessageResponse)
async def delete_admin_notification(
    notification_id: int,
    admin=Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    row = (await db.execute(
        select(AdminNotification).where(AdminNotification.id == notification_id)
    )).scalar_one_or_none()
    if not row:
        raise HTTPException(404, "Notification not found")
    await db.delete(row)
    await db.commit()
    return MessageResponse(message="Notification deleted")


@router.delete("/notifications", response_model=MessageResponse)
async def delete_admin_notifications(
    category: str = "",
    only_read: bool = False,
    admin=Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    q = text("DELETE FROM admin_notifications WHERE 1=1")
    params: dict = {}
    if category:
        q = text("DELETE FROM admin_notifications WHERE category = :category" + (" AND is_read = 1" if only_read else ""))
        params["category"] = category.strip().lower()
    elif only_read:
        q = text("DELETE FROM admin_notifications WHERE is_read = 1")
    await db.execute(q, params)
    await db.commit()
    return MessageResponse(message="Notifications deleted")


@router.get("/inquiries")
async def list_support_inquiries(
    page: int = 1,
    per_page: int = 30,
    status: str = "",
    search: str = "",
    admin=Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    query = select(SupportInquiry).order_by(SupportInquiry.created_at.desc())
    if status:
        query = query.where(SupportInquiry.status == status.strip().lower())
    if search:
        s = f"%{search.strip()}%"
        query = query.where(or_(
            SupportInquiry.name.ilike(s),
            SupportInquiry.email.ilike(s),
            SupportInquiry.subject.ilike(s),
            SupportInquiry.message.ilike(s),
        ))

    count_q = select(func.count(SupportInquiry.id))
    if status:
        count_q = count_q.where(SupportInquiry.status == status.strip().lower())
    if search:
        s = f"%{search.strip()}%"
        count_q = count_q.where(or_(
            SupportInquiry.name.ilike(s),
            SupportInquiry.email.ilike(s),
            SupportInquiry.subject.ilike(s),
            SupportInquiry.message.ilike(s),
        ))
    total = (await db.execute(count_q)).scalar() or 0

    rows = (await db.execute(query.offset((page - 1) * per_page).limit(per_page))).scalars().all()
    return {
        "items": [
            SupportInquiryPublic(
                id=i.id,
                name=i.name,
                email=i.email,
                subject=i.subject,
                message=i.message,
                source=i.source,
                locale=i.locale,
                status=i.status,
                admin_reply=i.admin_reply,
                replied_at=i.replied_at,
                replied_by=i.replied_by,
                created_at=i.created_at,
            ).model_dump()
            for i in rows
        ],
        "total": total,
        "page": page,
        "per_page": per_page,
        "pages": (total + per_page - 1) // per_page,
    }


@router.post("/inquiries/{inquiry_id}/reply", response_model=MessageResponse)
async def reply_to_inquiry(
    inquiry_id: int,
    body: ReplyInquiryRequest,
    admin=Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    row = (await db.execute(
        select(SupportInquiry).where(SupportInquiry.id == inquiry_id)
    )).scalar_one_or_none()
    if not row:
        raise HTTPException(404, "Inquiry not found")

    from app.services.email_service import email_service
    html = f"""
    <div style='font-family:Arial,sans-serif;max-width:700px;margin:0 auto;color:#111827;'>
      <h2 style='color:#0ea5e9;margin-bottom:12px;'>TLS Appointment Checker Support</h2>
      <p style='margin:0 0 12px 0;'>Hello {row.name or "there"},</p>
      <p style='margin:0 0 12px 0;'>We received your inquiry and here is our reply:</p>
      <div style='white-space:pre-wrap;background:#f3f4f6;border-radius:8px;padding:14px;margin:8px 0 16px 0;'>{body.message}</div>
      <p style='margin:0 0 8px 0;color:#6b7280;font-size:12px;'>Original subject: {row.subject or 'No subject'}</p>
      <p style='margin:0;color:#6b7280;font-size:12px;'>Sent from admin panel on {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}</p>
    </div>
    """
    ok = email_service.send(row.email, body.subject.strip(), html)
    if not ok:
        raise HTTPException(500, "Reply email failed to send. Check SMTP configuration.")

    row.admin_reply = body.message.strip()
    row.replied_at = datetime.now(timezone.utc)
    row.replied_by = admin.id
    row.status = "closed" if body.close_after_reply else "replied"

    db.add(ActivityLog(
        actor_id=admin.id,
        action="inquiry_replied",
        details={"inquiry_id": row.id, "email": row.email, "status": row.status},
    ))
    await db.commit()
    return MessageResponse(message=f"Reply sent to {row.email}")


@router.post("/inquiries/{inquiry_id}/mark-closed", response_model=MessageResponse)
async def close_inquiry(
    inquiry_id: int,
    admin=Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    row = (await db.execute(
        select(SupportInquiry).where(SupportInquiry.id == inquiry_id)
    )).scalar_one_or_none()
    if not row:
        raise HTTPException(404, "Inquiry not found")
    row.status = "closed"
    await db.commit()
    return MessageResponse(message="Inquiry closed")


@router.patch("/inquiries/{inquiry_id}/status", response_model=MessageResponse)
async def update_inquiry_status(
    inquiry_id: int,
    body: UpdateInquiryStatusRequest,
    admin=Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    status = (body.status or "").strip().lower()
    if status not in {"new", "replied", "closed"}:
        raise HTTPException(400, "Invalid status")
    row = (await db.execute(
        select(SupportInquiry).where(SupportInquiry.id == inquiry_id)
    )).scalar_one_or_none()
    if not row:
        raise HTTPException(404, "Inquiry not found")
    row.status = status
    await db.commit()
    return MessageResponse(message=f"Inquiry status updated to {status}")


@router.delete("/inquiries/{inquiry_id}", response_model=MessageResponse)
async def delete_inquiry(
    inquiry_id: int,
    admin=Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    row = (await db.execute(
        select(SupportInquiry).where(SupportInquiry.id == inquiry_id)
    )).scalar_one_or_none()
    if not row:
        raise HTTPException(404, "Inquiry not found")
    await db.delete(row)
    await db.commit()
    return MessageResponse(message="Inquiry deleted")


@router.websocket("/ws")
async def admin_websocket(websocket: WebSocket):
    from app.database import async_session
    # Validate admin token from query params
    token = websocket.query_params.get("token", "")
    try:
        payload = decode_token(token)
        user_id = int(payload.get("sub", 0))
    except Exception:
        await websocket.close(code=4001)
        return

    async with async_session() as db:
        result = await db.execute(select(User).where(User.id == user_id))
        user = result.scalar_one_or_none()
        if not user or not user.is_admin:
            await websocket.close(code=4003)
            return

    await ws_manager.connect_admin(websocket)
    try:
        while True:
            data = await websocket.receive_text()
            # Admin can send commands via WS if needed
    except WebSocketDisconnect:
        await ws_manager.disconnect_admin(websocket)

@router.delete("/ratings/{rating_id}", response_model=MessageResponse)
async def delete_rating(
    rating_id: int,
    admin=Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    from app.models import AppRating
    res = await db.execute(select(AppRating).where(AppRating.id == rating_id))
    rating = res.scalar_one_or_none()
    if not rating:
        raise HTTPException(404, "Rating not found")
    await db.delete(rating)
    db.add(ActivityLog(
        actor_id=admin.id,
        action="rating_deleted",
        details={"rating_id": rating_id},
    ))
    await db.commit()
    return MessageResponse(message=f"Rating #{rating_id} deleted")
