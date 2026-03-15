from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
from app.models import AppRating, AppDownload, FoundAppointment
from pydantic import BaseModel
from typing import Optional
from datetime import datetime

router = APIRouter(prefix="/metrics", tags=["Metrics"])

class RatingRequest(BaseModel):
    rating: int
    comment: Optional[str] = None
    source: str = "website"
    user_email: Optional[str] = None

class DownloadRequest(BaseModel):
    version: Optional[str] = None
    platform: Optional[str] = None

class FoundAppointmentRequest(BaseModel):
    user_email: Optional[str] = None
    branch: Optional[str] = None
    service_type: Optional[str] = None

@router.post("/rate")
async def submit_rating(req: RatingRequest, db: AsyncSession = Depends(get_db)):
    record = AppRating(
        user_email=req.user_email,
        rating=req.rating,
        comment=req.comment,
        source=req.source
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
        platform=req.platform
    )
    db.add(record)
    await db.commit()
    return {"status": "success"}

@router.post("/appointment-found")
async def record_found_appointment(req: FoundAppointmentRequest, db: AsyncSession = Depends(get_db)):
    record = FoundAppointment(
        user_email=req.user_email,
        branch=req.branch,
        service_type=req.service_type
    )
    db.add(record)
    await db.commit()
    return {"status": "success"}
