"""
Email Notification Service
Sends appointment availability alerts via SMTP.
"""

import logging
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from datetime import datetime, timezone
from app.config import settings

logger = logging.getLogger("email_service")


class EmailService:
    def send(self, to_email: str, subject: str, html_body: str) -> bool:
        """Send an HTML email. Returns True on success."""
        if not settings.SMTP_USERNAME or not settings.SMTP_PASSWORD:
            logger.warning("SMTP not configured, skipping email")
            return False

        try:
            msg = MIMEMultipart("alternative")
            msg["From"] = f"{settings.SENDER_NAME} <{settings.SENDER_EMAIL or settings.SMTP_USERNAME}>"
            msg["To"] = to_email
            msg["Subject"] = subject
            msg.attach(MIMEText(html_body, "html"))

            with smtplib.SMTP(settings.SMTP_SERVER, settings.SMTP_PORT) as server:
                server.starttls()
                server.login(settings.SMTP_USERNAME, settings.SMTP_PASSWORD)
                server.sendmail(msg["From"], to_email, msg.as_string())

            logger.info(f"Email sent to {to_email}: {subject}")
            return True
        except Exception as e:
            logger.error(f"Email failed to {to_email}: {e}")
            return False

    def send_appointment_alert(
        self,
        to_email: str,
        branch_name: str,
        service_type: str,
        slot_details: dict | None = None,
        user_name: str = "",
    ) -> bool:
        """Send a formatted appointment availability alert."""
        now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
        details_html = ""
        if slot_details:
            details_html = f'<p style="color: #00d9ff; font-size: 16px;">{slot_details.get("message", "")}</p>'

        html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <style>
                body {{ font-family: 'Segoe UI', Arial, sans-serif; background: #0a0e27; color: #fff; margin: 0; padding: 0; }}
                .container {{ max-width: 600px; margin: 0 auto; padding: 30px; }}
                .header {{ background: linear-gradient(135deg, #00d9ff 0%, #0066ff 100%); padding: 30px; border-radius: 16px 16px 0 0; text-align: center; }}
                .header h1 {{ margin: 0; font-size: 24px; color: #fff; }}
                .body {{ background: #141832; padding: 30px; border-radius: 0 0 16px 16px; }}
                .alert-badge {{ display: inline-block; background: #00ff88; color: #000; padding: 8px 20px; border-radius: 20px; font-weight: bold; font-size: 18px; margin: 15px 0; }}
                .info-row {{ display: flex; justify-content: space-between; padding: 12px 0; border-bottom: 1px solid #1e2448; }}
                .info-label {{ color: #8892b0; }}
                .info-value {{ color: #fff; font-weight: 600; }}
                .cta {{ display: inline-block; background: linear-gradient(135deg, #00d9ff, #0066ff); color: #fff; padding: 14px 32px; border-radius: 8px; text-decoration: none; font-weight: 600; margin: 20px 0; }}
                .footer {{ text-align: center; padding: 20px; color: #8892b0; font-size: 12px; }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1>🎉 Appointment Available!</h1>
                </div>
                <div class="body">
                    <p>Hi {user_name or 'there'},</p>
                    <div style="text-align: center;">
                        <span class="alert-badge">SLOTS OPEN</span>
                    </div>
                    {details_html}
                    <div class="info-row">
                        <span class="info-label">Branch</span>
                        <span class="info-value">{branch_name}</span>
                    </div>
                    <div class="info-row">
                        <span class="info-label">Service</span>
                        <span class="info-value">{service_type.title()}</span>
                    </div>
                    <div class="info-row">
                        <span class="info-label">Detected At</span>
                        <span class="info-value">{now}</span>
                    </div>
                    <p style="margin-top: 20px; color: #ffaa00;">⚡ Act fast — slots fill up within minutes!</p>
                    <div style="text-align: center;">
                        <a href="https://legalization-de.tlscontact.com" class="cta">Book Now →</a>
                    </div>
                </div>
                <div class="footer">
                    <p>TLS Appointment Checker — You received this because you subscribed to monitoring alerts.</p>
                    <p>This is a time-sensitive notification. Do not share — slots may already be taken.</p>
                </div>
            </div>
        </body>
        </html>
        """

        return self.send(
            to_email=to_email,
            subject=f"🎉 TLS Appointment Available — {branch_name} ({service_type.title()})",
            html_body=html,
        )

    def send_appointment_reminder(
        self,
        to_email: str,
        branch_name: str,
        service_type: str,
        user_name: str = "",
    ) -> bool:
        """Send a 12-hour follow-up reminder to book the appointment."""
        now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

        html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <style>
                body {{ font-family: 'Segoe UI', Arial, sans-serif; background: #0a0e27; color: #fff; margin: 0; padding: 0; }}
                .container {{ max-width: 600px; margin: 0 auto; padding: 30px; }}
                .header {{ background: linear-gradient(135deg, #ffaa00 0%, #ff6600 100%); padding: 30px; border-radius: 16px 16px 0 0; text-align: center; }}
                .header h1 {{ margin: 0; font-size: 24px; color: #fff; }}
                .body {{ background: #141832; padding: 30px; border-radius: 0 0 16px 16px; }}
                .alert-badge {{ display: inline-block; background: #ffaa00; color: #000; padding: 8px 20px; border-radius: 20px; font-weight: bold; font-size: 18px; margin: 15px 0; }}
                .cta {{ display: inline-block; background: linear-gradient(135deg, #ffaa00, #ff6600); color: #fff; padding: 14px 32px; border-radius: 8px; text-decoration: none; font-weight: 600; margin: 20px 0; }}
                .footer {{ text-align: center; padding: 20px; color: #8892b0; font-size: 12px; }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1>⏰ Reminder: Book Your Appointment!</h1>
                </div>
                <div class="body">
                    <p>Hi {user_name or 'there'},</p>
                    <div style="text-align: center;">
                        <span class="alert-badge">DON'T MISS OUT</span>
                    </div>
                    <p>We detected <strong>available appointment slots</strong> at <strong>{branch_name}</strong> ({service_type.title()}) earlier today.</p>
                    <p style="color: #ffaa00; font-size: 16px;">⚠️ Have you booked yet? Slots can disappear at any time!</p>
                    <p>If you haven't already, head to the TLS website now and secure your appointment before it's too late.</p>
                    <div style="text-align: center;">
                        <a href="https://legalization-de.tlscontact.com" class="cta">Book Now →</a>
                    </div>
                    <p style="color: #8892b0; font-size: 13px; margin-top: 20px;">This is your final reminder for this alert. No further emails will be sent for this detection.</p>
                </div>
                <div class="footer">
                    <p>TLS Appointment Checker — Automated reminder.</p>
                </div>
            </div>
        </body>
        </html>
        """

        return self.send(
            to_email=to_email,
            subject=f"⏰ Reminder: Book Your TLS Appointment — {branch_name}",
            html_body=html,
        )

    def send_subscription_activated(self, to_email: str, user_name: str, plan_name: str, expires_at: str) -> bool:
        """Send subscription activation confirmation."""
        html = f"""
        <div style="font-family: 'Segoe UI', Arial; max-width: 600px; margin: 0 auto; background: #141832; color: #fff; padding: 30px; border-radius: 16px;">
            <h2 style="color: #00d9ff;">✅ Subscription Activated!</h2>
            <p>Hi {user_name},</p>
            <p>Your <strong>{plan_name}</strong> subscription is now active.</p>
            <p><strong>Expires:</strong> {expires_at}</p>
            <p>Head to your dashboard to select which branches to monitor. You'll receive instant notifications when appointments become available.</p>
            <p style="color: #8892b0; font-size: 12px; margin-top: 30px;">TLS Appointment Checker</p>
        </div>
        """
        return self.send(to_email, f"✅ {plan_name} Subscription Activated", html)


email_service = EmailService()
