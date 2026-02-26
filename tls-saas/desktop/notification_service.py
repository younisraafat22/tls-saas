"""
Notification Service
Handles email, Windows toast notifications, and backend result reporting
"""
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
from datetime import datetime
import os
import threading
from config import Config

# Cross-platform notifications
try:
    from plyer import notification as plyer_notification
    PLYER_AVAILABLE = True
except ImportError:
    PLYER_AVAILABLE = False


class NotificationService:
    """Handles all notifications"""
    
    def __init__(self):
        pass
    
    def send_registration_confirmation(self, user_email: str, full_name: str) -> bool:
        """Send registration confirmation email"""
        subject = f"Welcome to {Config.APP_NAME}!"
        body = f"""
Hello {full_name},

Welcome to {Config.APP_NAME}!

Your account has been successfully created. You now have {Config.TRIAL_DAYS} days of free trial to explore all features.

What you can do:
- Monitor TLS visa appointment slots automatically
- Get instant notifications when appointments become available
- Customize check intervals and notification preferences

To get started:
1. Login to your account
2. Configure your TLS credentials
3. Start monitoring!

Thank you for choosing {Config.APP_NAME}.

Best regards,
The {Config.APP_NAME} Team
"""
        return self.send_email(user_email, subject, body)
    
    def send_verification_email(self, user_email: str, full_name: str, token: str) -> bool:
        """Send email verification email"""
        subject = f"Verify your {Config.APP_NAME} account"
        verification_link = f"{Config.BACKEND_URL}/verify?token={token}"
        
        body = f"""
Hello {full_name},

Thank you for registering with {Config.APP_NAME}!

Please verify your email address by using this verification code:

Verification Token: {token}

(In production, this would be a clickable link)

This link will expire in 24 hours.

If you didn't create this account, please ignore this email.

Best regards,
The {Config.APP_NAME} Team
"""
        return self.send_email(user_email, subject, body)
    
    def send_password_reset_email(self, user_email: str, full_name: str, token: str) -> bool:
        """Send password reset email"""
        subject = f"Reset your {Config.APP_NAME} password"
        reset_link = f"{Config.BACKEND_URL}/reset?token={token}"
        
        body = f"""
Hello {full_name},

We received a request to reset your password for {Config.APP_NAME}.

Use this reset code:

Reset Token: {token}

(In production, this would be a clickable link)

This link will expire in 1 hour.

If you didn't request a password reset, please ignore this email and your password will remain unchanged.

Best regards,
The {Config.APP_NAME} Team
"""
        return self.send_email(user_email, subject, body)
    
    def send_email(self, to_email: str, subject: str, body: str, screenshot_path: str = None) -> bool:
        """Send email notification"""
        if not to_email or not to_email.strip():
            print("Email notification skipped: no recipient email configured")
            return False
        
        if not Config.ADMIN_EMAIL or not Config.ADMIN_EMAIL_PASSWORD:
            print("Email notification skipped: admin email credentials not configured")
            return False
        
        try:
            # Create message
            msg = MIMEMultipart()
            msg['From'] = Config.ADMIN_EMAIL
            msg['To'] = to_email
            msg['Subject'] = subject
            
            # Add body
            msg.attach(MIMEText(body, 'plain'))
            
            # Attach screenshot if provided
            if screenshot_path and os.path.exists(screenshot_path):
                with open(screenshot_path, "rb") as attachment:
                    part = MIMEBase('application', 'octet-stream')
                    part.set_payload(attachment.read())
                    encoders.encode_base64(part)
                    filename = os.path.basename(screenshot_path)
                    part.add_header('Content-Disposition', f'attachment; filename= {filename}')
                    msg.attach(part)
            
            # Send email
            server = smtplib.SMTP(Config.SMTP_SERVER, Config.SMTP_PORT)
            server.starttls()
            server.login(Config.ADMIN_EMAIL, Config.ADMIN_EMAIL_PASSWORD)
            server.sendmail(Config.ADMIN_EMAIL, to_email, msg.as_string())
            server.quit()
            
            return True
            
        except Exception as e:
            print(f"Email notification failed: {e}")
            return False
    
    def send_windows_notification(self, title: str, message: str) -> bool:
        """Send Windows toast notification"""
        try:
            if PLYER_AVAILABLE:
                plyer_notification.notify(
                    title=title,
                    message=message,
                    app_name=Config.APP_NAME,
                    timeout=10
                )
                return True
            return False
        except Exception as e:
            print(f"Windows notification failed: {e}")
            return False
    
    def send_slots_available_notification(self, user_email: str, notification_types: list, screenshot_path: str = None):
        """Send notification when slots are available"""
        title = "🎉 TLS Appointments Available!"
        message = "Appointment slots are now available! Log in to the website immediately to book."
        
        email_body = f"""
{title}

Great news! Appointment slots have been detected on the TLS website!

⚠️ ACTION REQUIRED:
Please log in to the TLS website immediately to verify and book your appointment.

Website: {Config.TLS_URL}

Check Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

This is an automated notification from {Config.APP_NAME}.
Do not reply to this email.
"""
        
        # Send notifications based on user preferences
        if "email" in notification_types:
            self.send_email(user_email, title, email_body, screenshot_path)
        
        if "windows" in notification_types:
            self.send_windows_notification(title, message)
    
    def send_status_report(self, user_email: str, notification_types: list, total_checks: int, last_check: datetime, slots_found: bool):
        """Send 6-hour status report"""
        title = f"{Config.APP_NAME} - Status Report"
        
        if slots_found:
            status = "✅ SLOTS FOUND in last check!"
            message = f"Slots were detected! Total checks: {total_checks}"
        else:
            status = "No slots available"
            message = f"No slots found yet. Total checks: {total_checks}"
        
        email_body = f"""
{title}

Status Report - {datetime.now().strftime('%Y-%m-%d %H:%M')}

Status: {status}
Total Checks Performed: {total_checks}
Last Check: {last_check.strftime('%Y-%m-%d %H:%M:%S') if last_check else 'Never'}

The system is monitoring for appointment slots every configured interval.
You will be notified immediately when slots become available.

---
{Config.APP_NAME} v{Config.APP_VERSION}
"""
        
        # Send email status report
        if "email" in notification_types:
            self.send_email(user_email, title, email_body)
        
        # Optional Windows notification for status reports
        if "windows" in notification_types and slots_found:
            self.send_windows_notification(title, message)
    
    def send_trial_expiring_notification(self, user_email: str, days_remaining: int):
        """Send trial expiring notification"""
        title = f"{Config.APP_NAME} - Trial Expiring Soon"
        message = f"Your trial expires in {days_remaining} day(s)"
        
        email_body = f"""
{title}

Your free trial will expire in {days_remaining} day(s).

To continue using {Config.APP_NAME} after your trial expires, please purchase a license key.

Thank you for using {Config.APP_NAME}!
"""
        
        self.send_email(user_email, title, email_body)
        self.send_windows_notification(title, message)

    def report_to_backend(self, branch_name: str, service_type: str,
                          slots_available: bool, slot_details: str = "",
                          screenshot_path: str = None, duration_seconds: float = 0,
                          error: str = ""):
        """
        Report check result to the backend API (fire-and-forget).
        Only reports if the user is logged in via API.
        """
        def _report():
            try:
                from api_client import api_client
                if not api_client.is_logged_in:
                    return

                screenshot_b64 = ""
                if screenshot_path and os.path.exists(screenshot_path):
                    try:
                        import base64
                        with open(screenshot_path, "rb") as f:
                            screenshot_b64 = base64.b64encode(f.read()).decode("utf-8")
                    except Exception:
                        pass

                api_client.report_check_result(
                    branch_name=branch_name,
                    service_type=service_type,
                    slots_available=slots_available,
                    slot_details=slot_details,
                    screenshot_b64=screenshot_b64,
                    duration_seconds=duration_seconds,
                    error=error,
                )
            except Exception as e:
                print(f"[NOTIFY] Backend report failed: {e}")

        threading.Thread(target=_report, daemon=True).start()


# Global notification service instance
notification_service = NotificationService()
