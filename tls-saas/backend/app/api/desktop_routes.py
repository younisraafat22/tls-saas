"""
Desktop App Routes — Version check, download info, payment submission
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from app.schemas import AppVersionResponse, DesktopPaymentSubmit
from app.config import settings
from app.database import get_db
from app.models import Payment, User, PaymentMethod, PaymentStatus

router = APIRouter(prefix="/api/app", tags=["desktop-app"])

# ── Payment plan prices (EGP) ────────────────────────────────────────
DESKTOP_PLAN_PRICES: dict[str, float] = {
    "trial": 0.0,
    "legalization_monthly": settings.PRICE_LEGALIZATION_MONTHLY,
    "legalization_quarterly": settings.PRICE_LEGALIZATION_MONTHLY * 3 * 0.85,
    "visa_monthly": settings.PRICE_VISA_MONTHLY,
    "visa_quarterly": settings.PRICE_VISA_MONTHLY * 3 * 0.85,
    "all_in_one": settings.PRICE_ALL_IN_ONE_MONTHLY,
    "all_in_one_monthly": settings.PRICE_ALL_IN_ONE_MONTHLY,
    "all_in_one_quarterly": settings.PRICE_ALL_IN_ONE_MONTHLY * 3 * 0.85,
    "premium": settings.PRICE_PREMIUM_MONTHLY,
    "premium_monthly": settings.PRICE_PREMIUM_MONTHLY,
    "premium_quarterly": settings.PRICE_PREMIUM_MONTHLY * 3 * 0.8,
    "premium_annual": settings.PRICE_PREMIUM_MONTHLY * 12 * 0.65,
}


@router.get("/version", response_model=AppVersionResponse)
async def app_version():
    """
    Returns the latest desktop app version info.
    Used by the desktop app for auto-update checks.
    Version/URL/notes are controlled via env vars:
      DESKTOP_APP_VERSION, DESKTOP_DOWNLOAD_URL, DESKTOP_RELEASE_NOTES, DESKTOP_FORCE_UPDATE
    """
    return AppVersionResponse(
        version=settings.DESKTOP_APP_VERSION,
        download_url=settings.DESKTOP_DOWNLOAD_URL,
        release_notes=settings.DESKTOP_RELEASE_NOTES,
        force_update=settings.DESKTOP_FORCE_UPDATE,
    )


@router.get("/download-info")
async def download_info():
    """
    Returns download information for the landing page frontend.
    """
    return {
        "version": settings.DESKTOP_APP_VERSION,
        "download_url": settings.DESKTOP_DOWNLOAD_URL,
        "platforms": ["windows"],
        "size_mb": "~260",
        "requirements": "Windows 10/11, Chrome browser installed",
        "features": [
            "Local TLS appointment monitoring (runs on your machine)",
            "Selenium-based browser automation with anti-detection",
            "Audio CAPTCHA solver",
            "Email and Windows notifications",
            "All Egypt branches supported",
            "Encrypted credential storage",
        ],
    }


@router.post("/license/recover")
async def recover_license(
    body: dict,
    db: AsyncSession = Depends(get_db),
):
    """
    Return the license key(s) for a given email address.
    Used by the desktop app when a user accidentally deletes their .license file.
    """
    from sqlalchemy import select, or_
    email = (body.get("email") or "").strip().lower()
    if not email or "@" not in email:
        raise HTTPException(status_code=400, detail="A valid email address is required")

    # Outer-join to User so we can match payments from both:
    #  - Desktop/guest submissions (submitter_email is set, user_id may be None)
    #  - Web-portal submissions (submitter_email is NULL, email lives in User.email)
    stmt = (
        select(Payment)
        .join(User, Payment.user_id == User.id, isouter=True)
        .where(
            or_(
                Payment.submitter_email.ilike(email),
                User.email.ilike(email),
            ),
            Payment.status == PaymentStatus.APPROVED,
            Payment.license_key.isnot(None),
            Payment.license_key != "",
        )
        .order_by(Payment.created_at.desc())
    )
    result = await db.execute(stmt)
    payments = result.scalars().all()

    if not payments:
        raise HTTPException(
            status_code=404,
            detail="No approved license found for this email address. Please contact support if you believe this is an error.",
        )

    licenses = [{"license_key": p.license_key, "plan": p.plan_key or ""} for p in payments]
    return {"licenses": licenses, "count": len(licenses)}


@router.post("/payments/submit")
async def desktop_payment_submit(
    body: DesktopPaymentSubmit,
    db: AsyncSession = Depends(get_db),
):
    """
    Accept a payment submission from the desktop app.
    No authentication required — users may not have a web account.
    Stores screenshot, hardware_id, and contact info for admin review.
    Admin can then generate a license key from the admin panel.
    """
    plan_key = body.plan_key.strip().lower()
    if plan_key not in DESKTOP_PLAN_PRICES:
        raise HTTPException(status_code=400, detail=f"Unknown plan: {plan_key}")

    amount = DESKTOP_PLAN_PRICES[plan_key]
    if amount == 0:
        raise HTTPException(status_code=400, detail="Cannot submit payment for free trial plan")

    # Map payment method string to enum
    method_map = {
        "vodafone_cash": PaymentMethod.VODAFONE_CASH,
        "instapay": PaymentMethod.INSTAPAY,
    }
    method = method_map.get(body.payment_method.lower(), PaymentMethod.OTHER)

    # Use a placeholder user_id=0 — admin will see submitter_name/email instead
    # (SQLite FK not enforced, Postgres would need a real user; use admin user as placeholder)
    from sqlalchemy import select as sa_select
    admin_result = await db.execute(
        sa_select(User).where(User.is_admin == True).limit(1)
    )
    admin_user = admin_result.scalar_one_or_none()
    placeholder_user_id = admin_user.id if admin_user else 1

    payment = Payment(
        user_id=placeholder_user_id,
        amount=amount,
        currency=settings.CURRENCY,
        method=method,
        reference=body.reference,
        status=PaymentStatus.PENDING,
        screenshot_data=body.screenshot_b64 if body.screenshot_b64 else None,
        hardware_id=body.hardware_id,
        plan_key=plan_key,
        submitter_name=body.full_name,
        submitter_email=body.email,
    )
    db.add(payment)
    await db.commit()
    await db.refresh(payment)

    return {
        "success": True,
        "payment_id": payment.id,
        "message": (
            "Payment submitted successfully! "
            "Your license key will be sent to your email within a few hours after review."
        ),
    }


@router.get("/config")
async def get_desktop_config():
    """
    Remote configuration for the desktop app.
    Provides ability to update CSS selectors or wait timings over-the-air 
    without needing to completely reinstall the executable.
    """
    return {
        "selectors": {
            "login_button": ".login-btn, button[type='submit']",
            "recaptcha_iframe": "iframe[src*='recaptcha']",
            "audio_button": "#recaptcha-audio-button, button.rc-button-audio",
            "popup_close": "button.tls-button-primary, button[data-tls-value='confirm'], .tls-popup button",
            "calendar_slots": ".tls-time-unit:not(.-unavailable)",
        },
        "timeouts": {
            "page_load": 60,
            "captcha": 30
        }
    }
