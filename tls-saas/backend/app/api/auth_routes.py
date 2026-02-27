"""
Auth API Routes — Register, Login, Refresh, Profile
"""

from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import HTMLResponse
from jose import JWTError, jwt
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
from sqlalchemy.orm import selectinload
from app.models import User, Subscription, UserBranchMonitor
from app.config import settings
from app.auth import (
    hash_password, verify_password,
    create_access_token, create_refresh_token,
    decode_token, get_current_user,
    create_password_reset_token,
)
from app.schemas import (
    RegisterRequest, LoginRequest, TokenResponse,
    RefreshRequest, UserPublic, UserUpdate,
    ChangePasswordRequest, MessageResponse,
    PushSubscriptionRequest,
    ForgotPasswordRequest, ResetPasswordRequest,
)
from app.websocket import ws_manager
from app.services.email_service import EmailService
from concurrent.futures import ThreadPoolExecutor
import asyncio

_email_executor = ThreadPoolExecutor(max_workers=2)

router = APIRouter(prefix="/api/auth", tags=["auth"])


def _user_to_public(user: User) -> UserPublic:
    """Convert a User ORM object to a public schema."""
    active_plan = None
    sub_expires = None
    for sub in (user.subscriptions or []):
        if sub.status.value == "active" and sub.plan:
            active_plan = sub.plan.display_name
            sub_expires = sub.expires_at
            break
    return UserPublic(
        id=user.id,
        email=user.email,
        full_name=user.full_name or "",
        phone=user.phone or "",
        is_active=user.is_active,
        is_admin=user.is_admin,
        has_push_subscription=bool(user.push_subscription),
        created_at=user.created_at,
        active_plan=active_plan,
        subscription_expires=sub_expires,
    )


@router.post("/register", response_model=TokenResponse, status_code=201)
async def register(body: RegisterRequest, db: AsyncSession = Depends(get_db)):
    # Check if email exists
    existing = await db.execute(
        select(User)
        .options(selectinload(User.subscriptions).selectinload(Subscription.plan))
        .where(User.email == body.email.lower())
    )
    if existing.scalar_one_or_none():
        raise HTTPException(400, "Email already registered")

    user = User(
        email=body.email.lower().strip(),
        password_hash=hash_password(body.password),
        full_name=body.full_name.strip(),
        phone=body.phone.strip() if body.phone else "",
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)

    # Notify admins
    await ws_manager.broadcast_admin_event("new_user", {
        "user_id": user.id, "email": user.email, "name": user.full_name,
    })

    # Send welcome email (non-blocking)
    def _send_welcome():
        html = f"""
        <!DOCTYPE html><html><body style="font-family:'Segoe UI',Arial,sans-serif;background:#0a0e27;color:#fff;margin:0;padding:0;">
          <div style="max-width:560px;margin:40px auto;background:#111827;border-radius:16px;overflow:hidden;border:1px solid #1f2937;">
            <div style="background:linear-gradient(135deg,#0ea5e9,#6366f1);padding:32px;text-align:center;">
              <h1 style="margin:0;font-size:24px;color:#fff;">Welcome to TLS Appointment Checker</h1>
            </div>
            <div style="padding:32px;">
              <p style="font-size:16px;color:#d1d5db;">Hi <strong style="color:#fff;">{user.full_name or user.email}</strong>,</p>
              <p style="color:#9ca3af;line-height:1.6;">Your account has been created successfully. You can now log in and subscribe to start monitoring legalization appointment availability.</p>
              <div style="background:#1f2937;border-radius:12px;padding:20px;margin:24px 0;">
                <p style="margin:0;color:#9ca3af;font-size:14px;">&#x26A0;&#xFE0F; <strong style="color:#fbbf24;">Early Access:</strong> This service is in early access. Subscription is activated manually after payment confirmation via InstaPay or Vodafone Cash.</p>
              </div>
              <p style="color:#9ca3af;font-size:14px;">If you did not create this account, please ignore this email.</p>
            </div>
            <div style="padding:16px 32px;border-top:1px solid #1f2937;text-align:center;">
              <p style="margin:0;color:#6b7280;font-size:12px;">TLS Appointment Checker &mdash; Egypt</p>
            </div>
          </div>
        </body></html>
        """
        EmailService().send(user.email, "Welcome to TLS Appointment Checker", html)
    asyncio.get_event_loop().run_in_executor(_email_executor, _send_welcome)

    access = create_access_token({"sub": str(user.id)})
    refresh = create_refresh_token({"sub": str(user.id)})
    return TokenResponse(
        access_token=access,
        refresh_token=refresh,
        user=_user_to_public(user),
    )


@router.post("/login", response_model=TokenResponse)
async def login(body: LoginRequest, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(User)
        .options(selectinload(User.subscriptions).selectinload(Subscription.plan))
        .where(User.email == body.email.lower())
    )
    user = result.scalar_one_or_none()
    if not user or not verify_password(body.password, user.password_hash):
        raise HTTPException(401, "Invalid email or password")
    if not user.is_active:
        raise HTTPException(403, "Account deactivated. Contact support.")

    user.last_login = datetime.now(timezone.utc)
    await db.commit()

    access = create_access_token({"sub": str(user.id)})
    refresh = create_refresh_token({"sub": str(user.id)})
    return TokenResponse(
        access_token=access,
        refresh_token=refresh,
        user=_user_to_public(user),
    )


@router.post("/refresh", response_model=TokenResponse)
async def refresh_token(body: RefreshRequest, db: AsyncSession = Depends(get_db)):
    payload = decode_token(body.refresh_token)
    if payload.get("type") != "refresh":
        raise HTTPException(401, "Invalid refresh token")

    user_id = payload.get("sub")
    result = await db.execute(
        select(User)
        .options(selectinload(User.subscriptions).selectinload(Subscription.plan))
        .where(User.id == int(user_id))
    )
    user = result.scalar_one_or_none()
    if not user or not user.is_active:
        raise HTTPException(401, "Invalid user")

    access = create_access_token({"sub": str(user.id)})
    refresh = create_refresh_token({"sub": str(user.id)})
    return TokenResponse(
        access_token=access,
        refresh_token=refresh,
        user=_user_to_public(user),
    )


@router.get("/me", response_model=UserPublic)
async def get_me(user: User = Depends(get_current_user)):
    return _user_to_public(user)


@router.patch("/me", response_model=UserPublic)
async def update_me(
    body: UserUpdate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if body.full_name is not None:
        user.full_name = body.full_name.strip()
    if body.phone is not None:
        user.phone = body.phone.strip()
    await db.commit()
    await db.refresh(user)
    return _user_to_public(user)


@router.post("/change-password", response_model=MessageResponse)
async def change_password(
    body: ChangePasswordRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if not verify_password(body.current_password, user.password_hash):
        raise HTTPException(400, "Current password is incorrect")
    user.password_hash = hash_password(body.new_password)
    await db.commit()
    return MessageResponse(message="Password changed successfully")


@router.post("/push-subscription", response_model=MessageResponse)
async def save_push_subscription(
    body: PushSubscriptionRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    user.push_subscription = body.subscription
    await db.commit()
    return MessageResponse(message="Push subscription saved")


@router.get("/unsubscribe", response_class=HTMLResponse)
async def unsubscribe_email(token: str, db: AsyncSession = Depends(get_db)):
    """One-click unsubscribe from appointment alerts for a specific branch."""
    _error_page = """
    <!DOCTYPE html><html><head><title>Unsubscribe — Error</title>
    <style>body{font-family:Arial,sans-serif;background:#0a0e27;color:#fff;display:flex;align-items:center;justify-content:center;min-height:100vh;margin:0}
    .box{background:#141832;padding:40px;border-radius:16px;max-width:480px;text-align:center}
    h2{color:#ff4444}p{color:#8892b0}</style></head>
    <body><div class="box"><h2>❌ Invalid Link</h2>
    <p>This unsubscribe link is invalid or has expired (links are valid for 30 days).</p></div></body></html>
    """
    try:
        payload = jwt.decode(token, settings.JWT_SECRET, algorithms=[settings.JWT_ALGORITHM])
        if payload.get("type") != "unsubscribe":
            raise ValueError("wrong token type")
        user_id = int(payload["sub"])
        branch_id = int(payload["branch_id"])
    except Exception:
        return HTMLResponse(_error_page, status_code=400)

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

    return HTMLResponse("""
    <!DOCTYPE html><html><head><title>Unsubscribed</title>
    <style>body{font-family:Arial,sans-serif;background:#0a0e27;color:#fff;display:flex;align-items:center;justify-content:center;min-height:100vh;margin:0}
    .box{background:#141832;padding:40px;border-radius:16px;max-width:480px;text-align:center}
    h2{color:#00ff88}p{color:#8892b0}small{color:#555}</style></head>
    <body><div class="box"><h2>✅ Unsubscribed</h2>
    <p>You will no longer receive appointment alert emails for this branch.</p>
    <p>You can re-enable monitoring any time from your dashboard.</p>
    <small>TLS Appointment Checker</small></div></body></html>
    """)


# ── Forgot / Reset Password ─────────────────────────────────────────

@router.post("/forgot-password", response_model=MessageResponse)
async def forgot_password(body: ForgotPasswordRequest, db: AsyncSession = Depends(get_db)):
    """Request a password reset email. Always returns 200 to prevent email enumeration."""
    email = body.email.strip().lower()
    result = await db.execute(select(User).where(User.email == email))
    user = result.scalar_one_or_none()

    if user and user.is_active:
        token = create_password_reset_token(user.id)
        reset_url = f"{settings.FRONTEND_URL}/reset-password?token={token}"
        svc = EmailService()

        loop = asyncio.get_running_loop()
        await loop.run_in_executor(
            _email_executor,
            svc.send_password_reset,
            user.email,
            user.full_name or user.email,
            reset_url,
        )

    # Always return success to prevent enumeration
    return {"message": "If an account with that email exists, a password reset link has been sent."}


@router.post("/reset-password", response_model=MessageResponse)
async def reset_password(body: ResetPasswordRequest, db: AsyncSession = Depends(get_db)):
    """Reset password using a valid reset token."""
    try:
        payload = jwt.decode(body.token, settings.JWT_SECRET, algorithms=[settings.JWT_ALGORITHM])
    except JWTError:
        raise HTTPException(status_code=400, detail="Invalid or expired reset link")

    if payload.get("type") != "password_reset":
        raise HTTPException(status_code=400, detail="Invalid reset link")

    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(status_code=400, detail="Invalid reset link")

    result = await db.execute(select(User).where(User.id == int(user_id)))
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(status_code=400, detail="Invalid reset link")

    user.password_hash = hash_password(body.new_password)
    await db.commit()

    return {"message": "Your password has been reset successfully. You can now log in."}
