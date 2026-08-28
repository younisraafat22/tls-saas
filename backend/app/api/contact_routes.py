"""
Contact Form API - Receives messages from website/desktop users, sends email,
and stores inquiries for admin inbox handling.
"""

import logging
from typing import Optional
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.services.email_service import email_service
from app.database import get_db
from app.models import SupportInquiry, AdminNotification
from app.websocket import ws_manager

logger = logging.getLogger("contact")

router = APIRouter(tags=["contact"])


class ContactRequest(BaseModel):
    name: str
    email: str
    subject: str
    message: str
    source: Optional[str] = None   # website | desktop
    locale: Optional[str] = None


@router.post("/api/contact")
async def submit_contact(
    body: ContactRequest,
    db: AsyncSession = Depends(get_db),
):
    """Receive a contact form submission, email admin, and save inquiry."""
    if not body.name or not body.email or not body.message:
        raise HTTPException(400, "Name, email, and message are required")

    source = (body.source or "").strip().lower()
    if source not in {"website", "desktop"}:
        # Backward compatibility with old desktop builds that don't send `source`
        if (body.subject or "").strip().lower().startswith("[desktop support]") or "hardware id:" in (body.message or "").lower():
            source = "desktop"
        else:
            source = "website"
    locale = (body.locale or "en").strip().lower()[:10] or "en"
    subject = (body.subject or "").strip() or "No subject"

    # Send to admin using branded styling (consistent with license/registration mails)
    admin_html = f"""
    <div style="font-family:'Segoe UI',Arial,sans-serif;max-width:640px;margin:0 auto;background:#0a0e27;color:#fff;">
      <div style="background:linear-gradient(135deg,#00d9ff 0%,#0066ff 100%);padding:26px;border-radius:16px 16px 0 0;text-align:center;">
        <h2 style="margin:0;color:#fff;">New Support Inquiry</h2>
      </div>
      <div style="background:#141832;padding:24px;border-radius:0 0 16px 16px;">
        <div style="display:grid;grid-template-columns:120px 1fr;gap:10px 14px;font-size:14px;">
          <div style="color:#9ca3af;">From</div><div style="color:#fff;font-weight:600;">{body.name}</div>
          <div style="color:#9ca3af;">Email</div><div style="color:#fff;">{body.email}</div>
          <div style="color:#9ca3af;">Source</div><div style="color:#fff;">{source}</div>
          <div style="color:#9ca3af;">Language</div><div style="color:#fff;">{locale}</div>
          <div style="color:#9ca3af;">Subject</div><div style="color:#fff;">{subject}</div>
        </div>
        <div style="margin-top:16px;padding:14px;background:#0a0e27;border:1px solid #22305f;border-radius:10px;white-space:pre-wrap;color:#e5e7eb;">{body.message}</div>
      </div>
      <div style="text-align:center;padding:14px;color:#94a3b8;font-size:12px;">TLS Appointment Checker - Support Inbox</div>
    </div>
    """
    admin_email = settings.ADMIN_EMAIL
    sent = email_service.send(admin_email, f"[Support] {subject} - {body.name}", admin_html)

    # Confirmation to sender with same brand styling
    confirm_html = f"""
    <div style="font-family:'Segoe UI',Arial,sans-serif;max-width:640px;margin:0 auto;background:#0a0e27;color:#fff;">
      <div style="background:linear-gradient(135deg,#00d9ff 0%,#0066ff 100%);padding:26px;border-radius:16px 16px 0 0;text-align:center;">
        <h2 style="margin:0;color:#fff;">We Received Your Message</h2>
      </div>
      <div style="background:#141832;padding:24px;border-radius:0 0 16px 16px;">
        <p style="margin:0 0 10px 0;color:#fff;">Hi {body.name},</p>
        <p style="margin:0 0 14px 0;color:#d1d5db;">Thanks for contacting us. Our team will reply as soon as possible.</p>
        <div style="color:#9ca3af;font-size:13px;margin-bottom:6px;">Subject</div>
        <div style="color:#fff;margin-bottom:12px;">{subject}</div>
        <div style="color:#9ca3af;font-size:13px;margin-bottom:6px;">Your message</div>
        <div style="padding:14px;background:#0a0e27;border:1px solid #22305f;border-radius:10px;white-space:pre-wrap;color:#e5e7eb;">{body.message}</div>
      </div>
      <div style="text-align:center;padding:14px;color:#94a3b8;font-size:12px;">TLS Appointment Checker Support</div>
    </div>
    """
    email_service.send(body.email, "We received your message - TLS Appointment Checker", confirm_html)

    inquiry = SupportInquiry(
        name=body.name.strip(),
        email=body.email.strip(),
        subject=(body.subject or "").strip() or "No subject",
        message=body.message.strip(),
        source=source,
        locale=locale,
        status="new",
    )
    db.add(inquiry)
    await db.flush()

    db.add(AdminNotification(
        category="inquiry",
        event_type="new_inquiry",
        title="New support inquiry",
        message=f"{inquiry.name} sent a support request",
        payload={
            "inquiry_id": inquiry.id,
            "email": inquiry.email,
            "subject": inquiry.subject,
            "source": inquiry.source,
            "locale": inquiry.locale,
        },
    ))
    await db.commit()

    await ws_manager.broadcast_admin_event("new_inquiry", {
        "inquiry_id": inquiry.id,
        "email": inquiry.email,
        "subject": inquiry.subject,
        "source": inquiry.source,
        "locale": inquiry.locale,
    })

    if not sent:
        logger.warning(f"Contact form from {body.email} - email delivery failed (SMTP may not be configured)")

    return {"message": "Thank you! Your message has been sent. We'll get back to you shortly."}
