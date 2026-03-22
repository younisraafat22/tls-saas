"""
Contact Form API - Receives messages from website/desktop users, sends email,
and stores inquiries for admin inbox handling.
"""

import logging
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
    source: str = "website"   # website | desktop
    locale: str = "en"


@router.post("/api/contact")
async def submit_contact(
    body: ContactRequest,
    db: AsyncSession = Depends(get_db),
):
    """Receive a contact form submission, email admin, and save inquiry."""
    if not body.name or not body.email or not body.message:
        raise HTTPException(400, "Name, email, and message are required")

    # Send to admin
    html = f"""
    <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
        <h2 style="color: #00d9ff;">New Contact Form Submission</h2>
        <table style="width: 100%; border-collapse: collapse;">
            <tr><td style="padding: 8px; color: #888; width: 100px;">From</td><td style="padding: 8px;"><strong>{body.name}</strong></td></tr>
            <tr><td style="padding: 8px; color: #888;">Email</td><td style="padding: 8px;">{body.email}</td></tr>
            <tr><td style="padding: 8px; color: #888;">Source</td><td style="padding: 8px;">{body.source}</td></tr>
            <tr><td style="padding: 8px; color: #888;">Language</td><td style="padding: 8px;">{body.locale}</td></tr>
            <tr><td style="padding: 8px; color: #888;">Subject</td><td style="padding: 8px;">{body.subject or 'No subject'}</td></tr>
        </table>
        <div style="margin-top: 16px; padding: 16px; background: #f5f5f5; border-radius: 8px;">
            <p style="white-space: pre-wrap;">{body.message}</p>
        </div>
        <p style="margin-top: 16px; color: #888; font-size: 12px;">Reply directly to: {body.email}</p>
    </div>
    """

    admin_email = settings.ADMIN_EMAIL
    sent = email_service.send(admin_email, f"[Contact] {body.subject or 'New message'} - from {body.name}", html)

    # Also send a confirmation to the sender
    confirmation_html = f"""
    <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
        <h2 style="color: #00d9ff;">Thank you for contacting us!</h2>
        <p>Hi {body.name},</p>
        <p>We've received your message and will get back to you as soon as possible.</p>
        <p style="margin-top: 16px; padding: 16px; background: #f5f5f5; border-radius: 8px; white-space: pre-wrap;">{body.message}</p>
        <p style="margin-top: 16px; color: #888; font-size: 12px;">- TLS Appointment Checker Team</p>
    </div>
    """
    email_service.send(body.email, "We received your message - TLS Appointment Checker", confirmation_html)

    inquiry = SupportInquiry(
        name=body.name.strip(),
        email=body.email.strip(),
        subject=(body.subject or "").strip() or "No subject",
        message=body.message.strip(),
        source=(body.source or "website").strip().lower(),
        locale=(body.locale or "en").strip().lower(),
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
