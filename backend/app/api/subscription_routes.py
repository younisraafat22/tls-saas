"""
Subscription & Branch Monitoring Routes
"""

from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from app.database import get_db
from app.models import (
    User, Plan, Subscription, Branch, UserBranchMonitor,
    PlanType, SubscriptionStatus, ServiceType, Payment, PaymentStatus,
)
from app.auth import get_current_user
from app.schemas import (
    SubscribeRequest, SubscriptionPublic, BranchPublic,
    BranchMonitorRequest, MessageResponse, PlanPublic,
)

router = APIRouter(prefix="/api/subscriptions", tags=["subscriptions"])


# ── Plans ────────────────────────────────────────────────────────────

@router.get("/plans", response_model=list[PlanPublic])
async def list_plans(db: AsyncSession = Depends(get_db)):
    """List all active subscription plans."""
    result = await db.execute(
        select(Plan).where(Plan.is_active == True).order_by(Plan.sort_order)
    )
    return [PlanPublic.model_validate(p) for p in result.scalars().all()]


# ── User Subscription ───────────────────────────────────────────────

@router.get("/my", response_model=list[SubscriptionPublic])
async def my_subscriptions(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Subscription)
        .options(selectinload(Subscription.plan))
        .where(Subscription.user_id == user.id)
        .order_by(Subscription.created_at.desc())
    )
    return [SubscriptionPublic.model_validate(s) for s in result.scalars().all()]


@router.get("/active")
async def active_subscription(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get user's current active subscription(s)."""
    result = await db.execute(
        select(Subscription)
        .options(selectinload(Subscription.plan))
        .where(
            Subscription.user_id == user.id,
            Subscription.status == SubscriptionStatus.ACTIVE,
        )
        .order_by(Subscription.expires_at.desc())
    )
    subs = result.scalars().all()
    if not subs:
        return {"active": False, "subscription": None, "subscriptions": []}

    linked_rows = await db.execute(
        select(Payment.subscription_id, Payment.status).where(
            Payment.user_id == user.id,
            Payment.subscription_id.isnot(None),
        )
    )
    payment_statuses_by_sub: dict[int, list[PaymentStatus]] = {}
    for sub_id, status in linked_rows.all():
        if sub_id is None:
            continue
        payment_statuses_by_sub.setdefault(int(sub_id), []).append(status)

    now = datetime.now(timezone.utc)
    changed = False
    active_valid: list[Subscription] = []
    for sub in subs:
        linked_statuses = payment_statuses_by_sub.get(sub.id, [])
        if not linked_statuses or PaymentStatus.APPROVED not in linked_statuses:
            if sub.status in (SubscriptionStatus.ACTIVE, SubscriptionStatus.PENDING_PAYMENT):
                sub.status = SubscriptionStatus.CANCELLED
                changed = True
            continue
        if not sub.expires_at:
            continue
        exp = sub.expires_at
        if exp.tzinfo is None:
            exp = exp.replace(tzinfo=timezone.utc)
        if exp < now:
            sub.status = SubscriptionStatus.EXPIRED
            changed = True
        else:
            active_valid.append(sub)

    if changed:
        await db.commit()

    if not active_valid:
        return {"active": False, "subscription": None, "subscriptions": []}

    return {
        "active": True,
        "subscription": SubscriptionPublic.model_validate(active_valid[0]),
        "subscriptions": [SubscriptionPublic.model_validate(s) for s in active_valid],
    }


# ── Branches ─────────────────────────────────────────────────────────

@router.get("/branches", response_model=list[BranchPublic])
async def list_branches(db: AsyncSession = Depends(get_db)):
    """List all branches available for monitoring."""
    result = await db.execute(select(Branch).where(Branch.is_active == True))
    branches = result.scalars().all()

    out = []
    for b in branches:
        # Count active subscribers
        count_result = await db.execute(
            select(func.count(UserBranchMonitor.id))
            .where(UserBranchMonitor.branch_id == b.id, UserBranchMonitor.is_active == True)
        )
        count = count_result.scalar() or 0

        # Last check
        from app.models import CheckResult
        last_check_result = await db.execute(
            select(CheckResult)
            .where(CheckResult.branch_id == b.id)
            .order_by(CheckResult.checked_at.desc())
            .limit(1)
        )
        last = last_check_result.scalar_one_or_none()

        out.append(BranchPublic(
            id=b.id,
            name=b.name,
            url=b.url,
            service_type=b.service_type,
            is_active=b.is_active,
            subscriber_count=count,
            last_check=last.checked_at if last else None,
            last_status=last.slots_available if last else None,
        ))
    return out


@router.get("/my-branches", response_model=list[BranchPublic])
async def my_monitored_branches(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get branches the current user is monitoring."""
    result = await db.execute(
        select(Branch)
        .join(UserBranchMonitor)
        .where(
            UserBranchMonitor.user_id == user.id,
            UserBranchMonitor.is_active == True,
        )
    )
    branches = result.scalars().all()
    return [BranchPublic(
        id=b.id, name=b.name, url=b.url,
        service_type=b.service_type, is_active=b.is_active,
    ) for b in branches]


@router.post("/monitor-branches", response_model=MessageResponse)
async def set_monitored_branches(
    body: BranchMonitorRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Set which branches the user wants to monitor.
    Validates against the user's active subscription plan."""

    # Check active subscription
    sub_result = await db.execute(
        select(Subscription)
        .options(selectinload(Subscription.plan))
        .where(
            Subscription.user_id == user.id,
            Subscription.status == SubscriptionStatus.ACTIVE,
        )
    )
    sub = sub_result.scalar_one_or_none()
    if not sub:
        raise HTTPException(403, "Active subscription required to monitor branches")

    # Check expiry
    if sub.expires_at and sub.expires_at < datetime.now(timezone.utc):
        sub.status = SubscriptionStatus.EXPIRED
        await db.commit()
        raise HTTPException(403, "Subscription expired")

    # Validate branches against plan
    plan_type = sub.plan.plan_type
    requested_branches = await db.execute(
        select(Branch).where(Branch.id.in_(body.branch_ids))
    )
    branches = requested_branches.scalars().all()

    for b in branches:
        if plan_type == PlanType.LEGALIZATION and b.service_type != ServiceType.LEGALIZATION:
            raise HTTPException(400, f"Branch '{b.name}' is not a supported legalization branch.")
        if plan_type == PlanType.VISA and b.service_type != ServiceType.VISA:
            raise HTTPException(400, f"Branch '{b.name}' is not the visa monitoring entry.")

    # Deactivate all current monitors
    current = await db.execute(
        select(UserBranchMonitor).where(UserBranchMonitor.user_id == user.id)
    )
    for m in current.scalars().all():
        m.is_active = False

    # Activate requested monitors
    for branch_id in body.branch_ids:
        existing = await db.execute(
            select(UserBranchMonitor).where(
                UserBranchMonitor.user_id == user.id,
                UserBranchMonitor.branch_id == branch_id,
            )
        )
        monitor = existing.scalar_one_or_none()
        if monitor:
            monitor.is_active = True
        else:
            db.add(UserBranchMonitor(user_id=user.id, branch_id=branch_id, is_active=True))

    await db.commit()
    return MessageResponse(message=f"Now monitoring {len(body.branch_ids)} branch(es)")

