"""
Payment Routes — Submit payment proof, check status
"""

from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from app.database import get_db
from app.models import (
    User, Plan, Subscription, Payment, Branch,
    SubscriptionStatus, PaymentStatus,
)
from app.auth import get_current_user
from app.schemas import (
    PaymentSubmitRequest, PaymentPublic, MessageResponse,
)
from app.websocket import ws_manager

router = APIRouter(prefix="/api/payments", tags=["payments"])


@router.post("/submit", response_model=MessageResponse)
async def submit_payment(
    body: PaymentSubmitRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """User submits payment proof after transferring via Vodafone Cash/Instapay."""
    # Get the plan
    plan_result = await db.execute(
        select(Plan).where(Plan.plan_type == body.plan_type, Plan.is_active == True)
    )
    plan = plan_result.scalar_one_or_none()
    if not plan:
        raise HTTPException(400, "Invalid plan")

    # Validate branch exists
    branch_result = await db.execute(
        select(Branch).where(Branch.id == body.branch_id, Branch.is_active == True)
    )
    branch = branch_result.scalar_one_or_none()
    if not branch:
        raise HTTPException(400, "Invalid or inactive branch")

    # Require at least a reference number or a screenshot
    if not body.reference.strip() and not body.screenshot_data:
        raise HTTPException(400, "Please provide a transaction reference number or a payment screenshot")

    # Check for duplicate reference (only if a reference was given)
    if body.reference.strip():
        dup = await db.execute(
            select(Payment).where(Payment.reference == body.reference.strip())
        )
        if dup.scalar_one_or_none():
            raise HTTPException(400, "This payment reference has already been submitted")

    # Create pending subscription
    subscription = Subscription(
        user_id=user.id,
        plan_id=plan.id,
        status=SubscriptionStatus.PENDING_PAYMENT,
    )
    db.add(subscription)
    await db.flush()

    # Create payment record
    payment = Payment(
        user_id=user.id,
        subscription_id=subscription.id,
        branch_id=body.branch_id,
        amount=body.amount,
        currency=plan.currency,
        method=body.method,
        reference=body.reference.strip(),
        screenshot_data=body.screenshot_data,
        status=PaymentStatus.PENDING,
    )
    db.add(payment)

    await db.commit()

    # Notify admins of new payment
    await ws_manager.broadcast_admin_event("new_payment", {
        "payment_id": payment.id,
        "user_email": user.email,
        "amount": body.amount,
        "method": body.method.value,
        "reference": body.reference,
        "plan": plan.display_name,
        "branch": branch.name,
    })

    return MessageResponse(
        message="Payment submitted! We'll verify and activate your subscription within a few hours."
    )


@router.get("/my", response_model=list[PaymentPublic])
async def my_payments(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Payment)
        .where(Payment.user_id == user.id)
        .order_by(Payment.created_at.desc())
    )
    payments = result.scalars().all()
    return [
        PaymentPublic(
            id=p.id,
            user_id=p.user_id,
            user_email=user.email,
            user_name=user.full_name,
            amount=p.amount,
            currency=p.currency,
            method=p.method,
            reference=p.reference,
            screenshot_data=p.screenshot_data,
            status=p.status,
            admin_notes=p.admin_notes,
            created_at=p.created_at,
            processed_at=p.processed_at,
        )
        for p in payments
    ]


@router.get("/status/{payment_id}")
async def payment_status(
    payment_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Payment).where(Payment.id == payment_id, Payment.user_id == user.id)
    )
    payment = result.scalar_one_or_none()
    if not payment:
        raise HTTPException(404, "Payment not found")
    return {
        "status": payment.status.value,
        "admin_notes": payment.admin_notes,
        "processed_at": payment.processed_at,
    }
