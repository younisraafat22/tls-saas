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
        slot_details: dict | str | None = None,
        user_name: str = "",
        unsubscribe_url: str = "",
    ) -> bool:
        """Send a formatted appointment availability alert."""
        now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
        booking_url = (
            "https://visas-de.tlscontact.com"
            if service_type.lower() == "visa"
            else "https://legalization-de.tlscontact.com"
        )
        details_html = ""
        if slot_details:
            # slot_details may arrive as a JSON string (from worker) or a dict (from scheduler)
            if isinstance(slot_details, str):
                import json as _json
                try:
                    slot_details = _json.loads(slot_details)
                except Exception:
                    slot_details = {"message": slot_details}
            slots = slot_details.get("slots", [])
            message = slot_details.get("message", "")
            if slots:
                grid_items = "".join(
                    f'<div style="background:#00ff8820;border:1px solid #00ff8840;border-radius:8px;padding:8px 10px;margin:4px;">'
                    f'<div style="color:#00ff88;font-weight:600;font-size:13px;">{s["day"]}</div>'
                    f'<div style="color:#ccc;font-size:11px;">{" · ".join(s["times"][:6])}{" ..." if len(s["times"]) > 6 else ""}</div>'
                    f'</div>'
                    for s in slots[:12]
                )
                more = f'<p style="color:#888;font-size:12px;margin-top:4px;">+{len(slots)-12} more days</p>' if len(slots) > 12 else ""
                details_html = (
                    f'<p style="color:#00d9ff;font-size:15px;margin-bottom:8px;">'
                    f'{len(slots)} day(s) with available slots:</p>'
                    f'<div style="display:flex;flex-wrap:wrap;margin-bottom:4px;">{grid_items}</div>{more}'
                )
            elif message:
                details_html = f'<p style="color: #00d9ff; font-size: 16px;">{message}</p>'

        tip_html = ""
        if isinstance(slot_details, dict) and slot_details.get("tls_disabled_month_booking_tip"):
            ex_url = (slot_details.get("tls_month_probe_example_url") or "").strip()
            ex_block = (
                f'<p style="color:#8892b0;font-size:12px;margin:10px 0 0 0;word-break:break-all;">Example URL we used: {ex_url}</p>'
                if ex_url
                else ""
            )
            tip_html = (
                '<div style="background:#1e2448;border:1px solid #ffaa0040;border-radius:10px;padding:14px 16px;margin:16px 0;">'
                '<p style="color:#ffcc66;font-weight:600;margin:0 0 8px 0;font-size:14px;">'
                "Important: TLS calendar may show some months as disabled</p>"
                '<p style="color:#ccc;font-size:13px;line-height:1.5;margin:0;">'
                "Slots were detected on a month that can appear greyed out in the website navigation. "
                "To book, open your appointment booking link and edit only the <strong>month=</strong> numbers in the address bar "
                "(for example <code style=\"color:#7dd3fc;\">month=05-2026</code> → <code style=\"color:#7dd3fc;\">month=06-2026</code>, "
                "or <code style=\"color:#7dd3fc;\">month=05-26</code> → <code style=\"color:#7dd3fc;\">month=06-26</code>) then press Enter."
                "</p>"
                f"{ex_block}"
                "</div>"
            )

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
                .info-label {{ color: #dddddd; }}
                .info-value {{ color: #fff; font-weight: 600; }}
                .cta {{ display: inline-block; background: linear-gradient(135deg, #00d9ff, #0066ff); color: #fff; padding: 14px 32px; border-radius: 8px; text-decoration: none; font-weight: 600; margin: 20px 0; }}
                .footer {{ text-align: center; padding: 20px; color: #dddddd; font-size: 12px; }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1>🎉 Appointment Available!</h1>
                </div>
                <div class="body">
                    <p style="color:#fff;">Hi {user_name or 'there'},</p>
                    <div style="text-align: center;">
                        <span class="alert-badge">SLOTS OPEN</span>
                    </div>
                    {details_html}
                    {tip_html}
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
                        <a href="{booking_url}" class="cta">Book Now →</a>
                    </div>
                </div>
                <div class="footer">
                    <p style="color:#8892b0;">TLS Appointment Checker — You received this because you subscribed to monitoring alerts.</p>
                    <p style="color:#8892b0;">This is a time-sensitive notification. Do not share — slots may already be taken.</p>
                    {f'<p style="margin-top:12px;"><a href="{unsubscribe_url}" style="color:#555;font-size:11px;text-decoration:underline;">Stop receiving alerts for this branch</a></p>' if unsubscribe_url else ''}
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
        unsubscribe_url: str = "",
    ) -> bool:
        """Send a 12-hour follow-up reminder to book the appointment."""
        now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
        booking_url = (
            "https://visas-de.tlscontact.com"
            if service_type.lower() == "visa"
            else "https://legalization-de.tlscontact.com"
        )

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
                .footer {{ text-align: center; padding: 20px; color: #dddddd; font-size: 12px; }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1>⏰ Reminder: Book Your Appointment!</h1>
                </div>
                <div class="body">
                    <p style="color:#fff;">Hi {user_name or 'there'},</p>
                    <div style="text-align: center;">
                        <span class="alert-badge">DON'T MISS OUT</span>
                    </div>
                    <p style="color:#fff;">We detected <strong>available appointment slots</strong> at <strong>{branch_name}</strong> ({service_type.title()}) earlier today.</p>
                    <p style="color: #ffaa00; font-size: 16px;">⚠️ Have you booked yet? Slots can disappear at any time!</p>
                    <p style="color:#fff;">If you haven't already, head to the TLS website now and secure your appointment before it's too late.</p>
                    <div style="text-align: center;">
                        <a href="{booking_url}" class="cta">Book Now →</a>
                    </div>
                    <p style="color: #dddddd; font-size: 13px; margin-top: 20px;">This is your final reminder for this alert. No further emails will be sent for this detection.</p>
                </div>
                <div class="footer">
                    <p style="color:#8892b0;">TLS Appointment Checker — Automated reminder.</p>
                    {f'<p style="margin-top:12px;"><a href="{unsubscribe_url}" style="color:#555;font-size:11px;text-decoration:underline;">Stop receiving alerts for this branch</a></p>' if unsubscribe_url else ''}
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

    def send_check_error_alert(
        self,
        to_email: str,
        user_name: str,
        branch_name: str,
        error_type: str,
        error_message: str,
    ) -> bool:
        """Send an alert when a monitoring check finds invalid credentials or no application."""
        now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

        if "no application" in error_type.lower():
            icon = "📋"
            title = "No Application Found"
            color = "#ffaa00"
            explanation = (
                "Our monitoring check could not find a TLS application under your account. "
                "You need to <strong>create an application on the TLS website first</strong> "
                "before we can monitor for available appointment slots."
            )
            action_text = "Create Application on TLS"
            action_url = "https://visas-de.tlscontact.com"
        else:
            icon = "🔐"
            title = "Invalid Credentials"
            color = "#ff4444"
            explanation = (
                "Our monitoring check could not log in with the TLS credentials you provided. "
                "Your email or password may be <strong>incorrect or expired</strong>. "
                "Please update your credentials in your dashboard."
            )
            action_text = "Update Credentials"
            action_url = f"{settings.FRONTEND_URL}/dashboard"

        html = f"""
        <div style="font-family:'Segoe UI',Arial;max-width:600px;margin:0 auto;background:#0a0e27;color:#fff;padding:0;">
            <div style="background:linear-gradient(135deg,{color} 0%,#ff6600 100%);padding:30px;border-radius:16px 16px 0 0;text-align:center;">
                <h1 style="margin:0;font-size:24px;color:#fff;">{icon} {title}</h1>
            </div>
            <div style="background:#141832;padding:30px;border-radius:0 0 16px 16px;">
                <p style="color:#fff;">Hi {user_name or 'there'},</p>
                <p style="color:#fff;">{explanation}</p>
                <div style="background:#0a0e27;border:1px solid {color}40;border-radius:12px;padding:16px;margin:20px 0;">
                    <div style="color:#8892b0;font-size:13px;">Branch</div>
                    <div style="color:#fff;font-weight:600;margin-top:4px;">{branch_name}</div>
                    <div style="color:#8892b0;font-size:13px;margin-top:12px;">Error</div>
                    <div style="color:{color};margin-top:4px;font-size:13px;">{error_message}</div>
                    <div style="color:#8892b0;font-size:13px;margin-top:12px;">Time</div>
                    <div style="color:#fff;margin-top:4px;font-size:13px;">{now}</div>
                </div>
                <div style="text-align:center;">
                    <a href="{action_url}" style="display:inline-block;background:linear-gradient(135deg,#00d9ff,#0066ff);color:#fff;padding:14px 32px;border-radius:8px;text-decoration:none;font-weight:600;margin:20px 0;">{action_text} →</a>
                </div>
            </div>
            <div style="text-align:center;padding:20px;color:#8892b0;font-size:12px;">
                <p style="color:#8892b0;">TLS Appointment Checker — Automated monitoring alert.</p>
            </div>
        </div>
        """

        return self.send(
            to_email=to_email,
            subject=f"{icon} {title} — {branch_name}",
            html_body=html,
        )

    def send_license_key(self, to_email: str, customer_name: str, license_key: str, plan_name: str) -> bool:
        """Send a license key to the customer after admin approval."""
        html = f"""
        <div style="font-family: 'Segoe UI', Arial; max-width: 600px; margin: 0 auto; background: #0a0e27; color: #fff; padding: 0;">
            <div style="background: linear-gradient(135deg, #00d9ff 0%, #0066ff 100%); padding: 30px; border-radius: 16px 16px 0 0; text-align: center;">
                <h1 style="margin: 0; font-size: 24px; color: #fff;">🔑 Your License Key</h1>
            </div>
            <div style="background: #141832; padding: 30px; border-radius: 0 0 16px 16px;">
                <p style="color:#fff;">Hi {customer_name or 'there'},</p>
                <p style="color:#fff;">Your payment has been approved! Here is your license key for <strong>{plan_name}</strong>:</p>
                <div style="background: #0a0e27; border: 2px solid #00d9ff; border-radius: 12px; padding: 20px; text-align: center; margin: 20px 0;">
                    <code style="font-size: 18px; color: #00ff88; letter-spacing: 2px; word-break: break-all;">{license_key}</code>
                </div>
                <h3 style="color: #00d9ff;">How to activate:</h3>
                <ol style="color: #ccc; line-height: 1.8;">
                    <li>Open the TLS Appointment Checker app</li>
                    <li>Go to the Pricing / Activation page</li>
                    <li>Paste the license key above</li>
                    <li>Click <strong>Activate</strong></li>
                </ol>
                <p style="color: #ffaa00; margin-top: 20px;">⚠️ This key is bound to your device. Do not share it.</p>
            </div>
            <div style="text-align: center; padding: 20px; color: #dddddd; font-size: 12px;">
                <p style="color:#8892b0;">TLS Appointment Checker — Thank you for your purchase!</p>
                <p style="color:#8892b0;">Need help? Reply to this email or contact support.</p>
            </div>
        </div>
        """
        return self.send(to_email, f"🔑 Your TLS Checker License Key — {plan_name}", html)

    def send_subscription_activated(self, to_email: str, user_name: str, plan_name: str, expires_at: str) -> bool:
        """Send subscription activation confirmation."""
        html = f"""
        <div style="font-family: 'Segoe UI', Arial; max-width: 600px; margin: 0 auto; background: #141832; color: #fff; padding: 30px; border-radius: 16px;">
            <h2 style="color: #00d9ff;">✅ Subscription Activated!</h2>
            <p style="color:#fff;">Hi {user_name},</p>
            <p style="color:#fff;">Your <strong>{plan_name}</strong> subscription is now active.</p>
            <p style="color:#fff;"><strong>Expires:</strong> {expires_at}</p>
            <p style="color:#fff;">Head to your dashboard to select which branches to monitor. You'll receive instant notifications when appointments become available.</p>
            <p style="color: #dddddd; font-size: 12px; margin-top: 30px;">TLS Appointment Checker</p>
        </div>
        """
        return self.send(to_email, f"✅ {plan_name} Subscription Activated", html)

    def send_password_reset(self, to_email: str, user_name: str, reset_url: str) -> bool:
        """Send a password reset link email."""
        display_name = user_name or to_email
        html = f"""
        <div style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; max-width: 600px; margin: 0 auto; background: #0a192f; color: #ccd6f6; padding: 30px; border-radius: 12px;">
            <h2 style="color: #00D9FF; margin-bottom: 20px;">🔑 Password Reset</h2>
            <p style="color:#ccd6f6;">Hi {display_name},</p>
            <p style="color:#ccd6f6;">We received a request to reset your password. Click the button below to set a new password:</p>
            <div style="text-align: center; margin: 30px 0;">
                <a href="{reset_url}" style="background: #00D9FF; color: #0a192f; padding: 14px 40px; border-radius: 8px; text-decoration: none; font-weight: bold; display: inline-block;">Reset Password</a>
            </div>
            <p style="color: #dddddd; font-size: 13px;">This link expires in 15 minutes. If you didn't request this reset, you can safely ignore this email.</p>
            <p style="color: #dddddd; font-size: 13px;">Or copy and paste this URL into your browser:</p>
            <p style="color: #64ffda; font-size: 12px; word-break: break-all;">{reset_url}</p>
            <p style="color: #dddddd; font-size: 12px; margin-top: 30px;">TLS Appointment Checker</p>
        </div>
        """
        return self.send(to_email, "🔑 Reset Your Password - TLS Appointment Checker", html)


email_service = EmailService()
