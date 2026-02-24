"""
Contact Form API — Receives messages from the website contact form
and forwards them via email to the admin.
"""

import logging
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, EmailStr
from app.config import settings
from app.services.email_service import email_service

logger = logging.getLogger("contact")

router = APIRouter(tags=["contact"])


class ContactRequest(BaseModel):
    name: str
    email: str
    subject: str
    message: str


@router.post("/api/contact")
async def submit_contact(body: ContactRequest):
    """Receive a contact form submission and email it to the admin."""
    if not body.name or not body.email or not body.message:
        raise HTTPException(400, "Name, email, and message are required")

    # Send to admin
    html = f"""
    <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
        <h2 style="color: #00d9ff;">New Contact Form Submission</h2>
        <table style="width: 100%; border-collapse: collapse;">
            <tr><td style="padding: 8px; color: #888; width: 100px;">From</td><td style="padding: 8px;"><strong>{body.name}</strong></td></tr>
            <tr><td style="padding: 8px; color: #888;">Email</td><td style="padding: 8px;">{body.email}</td></tr>
            <tr><td style="padding: 8px; color: #888;">Subject</td><td style="padding: 8px;">{body.subject or 'No subject'}</td></tr>
        </table>
        <div style="margin-top: 16px; padding: 16px; background: #f5f5f5; border-radius: 8px;">
            <p style="white-space: pre-wrap;">{body.message}</p>
        </div>
        <p style="margin-top: 16px; color: #888; font-size: 12px;">Reply directly to: {body.email}</p>
    </div>
    """

    admin_email = settings.ADMIN_EMAIL
    sent = email_service.send(admin_email, f"[Contact] {body.subject or 'New message'} — from {body.name}", html)

    # Also send a confirmation to the sender
    confirmation_html = f"""
    <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
        <h2 style="color: #00d9ff;">Thank you for contacting us!</h2>
        <p>Hi {body.name},</p>
        <p>We've received your message and will get back to you as soon as possible.</p>
        <p style="margin-top: 16px; padding: 16px; background: #f5f5f5; border-radius: 8px; white-space: pre-wrap;">{body.message}</p>
        <p style="margin-top: 16px; color: #888; font-size: 12px;">— TLS Appointment Checker Team</p>
    </div>
    """
    email_service.send(body.email, "We received your message — TLS Appointment Checker", confirmation_html)

    if not sent:
        logger.warning(f"Contact form from {body.email} — email delivery failed (SMTP may not be configured)")

    return {"message": "Thank you! Your message has been sent. We'll get back to you shortly."}
