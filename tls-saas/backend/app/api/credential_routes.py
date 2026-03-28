"""
Credential Routes — Users can view and update their stored TLS credentials.
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import User, UserCredential, ServiceType, ActivityLog
from app.auth import get_current_user
from app.schemas import UserCredentialCreate, UserCredentialPublic, MessageResponse
from app.services.checker import encrypt_credential, decrypt_credential

router = APIRouter(prefix="/api/credentials", tags=["credentials"])
TLS_EMAIL_CHANGE_LIMIT = 2


@router.get("/", response_model=list[UserCredentialPublic])
async def get_my_credentials(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Return the user's stored credentials (email masked)."""
    result = await db.execute(
        select(UserCredential).where(UserCredential.user_id == user.id, UserCredential.is_active == True)
    )
    creds = result.scalars().all()
    out = []
    for c in creds:
        try:
            raw_email = decrypt_credential(c.email_encrypted)
            at_idx = raw_email.find("@")
            if at_idx > 3:
                masked = raw_email[:3] + "*" * (at_idx - 3) + raw_email[at_idx:]
            else:
                masked = raw_email[:2] + "***"
        except Exception:
            masked = "***"
        out.append(UserCredentialPublic(
            id=c.id,
            service_type=c.service_type,
            email_masked=masked,
            has_credential=True,
            last_used_at=c.last_used_at,
            last_error=c.last_error or "",
        ))
    return out


@router.post("/", response_model=MessageResponse)
async def save_credential(
    body: UserCredentialCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Save or update TLS credentials for a service type."""
    new_email = body.tls_email.strip().lower()
    action_name = f"tls_credential_email_changed_{body.service_type.value}"
    existing = await db.execute(
        select(UserCredential).where(
            UserCredential.user_id == user.id,
            UserCredential.service_type == body.service_type,
        )
    )
    cred = existing.scalar_one_or_none()
    if cred:
        old_email = ""
        try:
            old_email = (decrypt_credential(cred.email_encrypted) or "").strip().lower()
        except Exception:
            old_email = ""

        if old_email and old_email != new_email:
            cnt_result = await db.execute(
                select(func.count(ActivityLog.id)).where(
                    ActivityLog.actor_id == user.id,
                    ActivityLog.action == action_name,
                )
            )
            change_count = int(cnt_result.scalar() or 0)
            if change_count >= TLS_EMAIL_CHANGE_LIMIT:
                raise HTTPException(
                    status_code=400,
                    detail=f"TLS email change limit reached. Maximum {TLS_EMAIL_CHANGE_LIMIT} change(s) allowed.",
                )
            db.add(ActivityLog(
                actor_id=user.id,
                action=action_name,
                details={
                    "service_type": body.service_type.value,
                    "old_email": old_email,
                    "new_email": new_email,
                },
            ))

        cred.email_encrypted = encrypt_credential(body.tls_email)
        cred.password_encrypted = encrypt_credential(body.tls_password)
        cred.is_active = True
        cred.last_error = ""
    else:
        db.add(UserCredential(
            user_id=user.id,
            service_type=body.service_type,
            email_encrypted=encrypt_credential(body.tls_email),
            password_encrypted=encrypt_credential(body.tls_password),
        ))
    await db.commit()
    return MessageResponse(message="Credentials saved successfully.")


@router.delete("/{service_type}", response_model=MessageResponse)
async def delete_credential(
    service_type: ServiceType,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Deactivate (soft-delete) credentials for a service type."""
    existing = await db.execute(
        select(UserCredential).where(
            UserCredential.user_id == user.id,
            UserCredential.service_type == service_type,
        )
    )
    cred = existing.scalar_one_or_none()
    if not cred:
        raise HTTPException(404, "No credentials found for this service type")
    cred.is_active = False
    await db.commit()
    return MessageResponse(message="Credentials removed.")
