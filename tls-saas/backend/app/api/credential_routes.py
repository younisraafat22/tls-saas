"""
Credential Routes — Users can view and update their stored TLS credentials.
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import User, UserCredential, ServiceType
from app.auth import get_current_user
from app.schemas import UserCredentialCreate, UserCredentialPublic, MessageResponse
from app.services.checker import encrypt_credential, decrypt_credential

router = APIRouter(prefix="/api/credentials", tags=["credentials"])


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
    existing = await db.execute(
        select(UserCredential).where(
            UserCredential.user_id == user.id,
            UserCredential.service_type == body.service_type,
        )
    )
    cred = existing.scalar_one_or_none()
    if cred:
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
