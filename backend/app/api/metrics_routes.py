from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc
from pydantic import BaseModel
from typing import Optional

from app.database import get_db
from app.models import AppRating, AppDownload, FoundAppointment, Payment, User, PaymentStatus

router = APIRouter(prefix="/metrics", tags=["Metrics"])


class RatingRequest(BaseModel):
    rating: int
    comment: Optional[str] = None
    source: str = "website"
    user_name: Optional[str] = None
    user_email: Optional[str] = None
    license_key: Optional[str] = None
    hardware_id: Optional[str] = None


class DownloadRequest(BaseModel):
    version: Optional[str] = None
    platform: Optional[str] = None


class FoundAppointmentRequest(BaseModel):
    user_email: Optional[str] = None
    branch: Optional[str] = None
    service_type: Optional[str] = None


@router.post("/rate")
async def submit_rating(req: RatingRequest, db: AsyncSession = Depends(get_db)):
    resolved_name = (req.user_name or "").strip() or None
    resolved_email = (req.user_email or "").strip().lower() or None

    if req.source == "desktop":
        # Prefer exact license lookup so desktop feedback is linked to buyer account data.
        license_key = (req.license_key or "").strip()
        if license_key:
            owner_result = await db.execute(
                select(Payment, User)
                .join(User, Payment.user_id == User.id, isouter=True)
                .where(
                    Payment.license_key == license_key,
                    Payment.status == PaymentStatus.APPROVED,
                )
                .order_by(desc(Payment.id))
                .limit(1)
            )
            owner_row = owner_result.first()
            if owner_row:
                payment, user = owner_row
                resolved_name = (
                    (payment.submitter_name or "").strip()
                    or (user.full_name.strip() if user and user.full_name else "")
                    or resolved_name
                ) or None
                resolved_email = (
                    (payment.submitter_email or "").strip().lower()
                    or (user.email.strip().lower() if user and user.email else "")
                    or resolved_email
                ) or None

        # Fallback: if desktop sent an email, map to account full name.
        if resolved_email and not resolved_name:
            user_result = await db.execute(
                select(User).where(User.email.ilike(resolved_email)).limit(1)
            )
            user = user_result.scalar_one_or_none()
            if user and user.full_name:
                resolved_name = user.full_name.strip() or None

    record = AppRating(
        user_name=resolved_name,
        user_email=resolved_email,
        rating=req.rating,
        comment=req.comment,
        source=req.source,
    )
    db.add(record)
    await db.commit()
    return {"status": "success"}


@router.post("/download")
async def record_download(req: DownloadRequest, request: Request, db: AsyncSession = Depends(get_db)):
    ip_addr = request.client.host if request.client else "unknown"
    record = AppDownload(
        ip_address=ip_addr,
        version=req.version,
        platform=req.platform,
    )
    db.add(record)
    await db.commit()
    return {"status": "success"}


@router.post("/appointment-found")
async def record_found_appointment(req: FoundAppointmentRequest, db: AsyncSession = Depends(get_db)):
    record = FoundAppointment(
        user_email=req.user_email,
        branch=req.branch,
        service_type=req.service_type,
    )
    db.add(record)
    await db.commit()
    return {"status": "success"}


@router.get("/ratings")
async def get_ratings(limit: Optional[int] = None, db: AsyncSession = Depends(get_db)):
    query = (
        select(AppRating)
        .where(AppRating.comment.is_not(None), AppRating.comment != "")
        .order_by(desc(AppRating.created_at))
    )
    if limit:
        query = query.limit(limit)
    result = await db.execute(query)
    ratings = result.scalars().all()
    return [
        {
            "id": r.id,
            "rating": r.rating,
            "comment": r.comment,
            "source": r.source,
            "created_at": r.created_at.isoformat() if r.created_at else None,
            "user_name": r.user_name,
            "user_email": r.user_email,
        }
        for r in ratings
    ]
