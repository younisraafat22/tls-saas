"""
Notification Service
Handles email and Windows toast notifications
"""
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
from datetime import datetime
import os
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
    
    def send_email(self, to_email: str, subject: str, html_body: str, screenshot_path: str = None) -> bool:
        """Send an HTML email notification with optional screenshot attachment."""
        if not to_email or not to_email.strip():
            print("Email notification skipped: no recipient email configured")
            return False

        if not Config.ADMIN_EMAIL or not Config.ADMIN_EMAIL_PASSWORD:
            print("Email notification skipped: admin email credentials not configured")
            return False

        try:
            msg = MIMEMultipart("mixed")
            msg['From'] = f"TLS Appointment Checker <{Config.ADMIN_EMAIL}>"
            msg['To'] = to_email
            msg['Subject'] = subject

            # HTML body
            alt = MIMEMultipart("alternative")
            alt.attach(MIMEText(html_body, 'html'))
            msg.attach(alt)

            # Attach screenshot if provided
            if screenshot_path and os.path.exists(screenshot_path):
                with open(screenshot_path, "rb") as attachment:
                    part = MIMEBase('application', 'octet-stream')
                    part.set_payload(attachment.read())
                    encoders.encode_base64(part)
                    filename = os.path.basename(screenshot_path)
                    part.add_header('Content-Disposition', f'attachment; filename="{filename}"')
                    msg.attach(part)

            server = smtplib.SMTP(Config.SMTP_SERVER, Config.SMTP_PORT)
            server.starttls()
            server.login(Config.ADMIN_EMAIL, Config.ADMIN_EMAIL_PASSWORD)
            server.sendmail(msg['From'], to_email, msg.as_string())
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
        windows_message = "Appointment slots are now available! Log in to the TLS website immediately to book."
        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        html = f"""<!DOCTYPE html>
<html>
<head>
<style>
  body {{ font-family: 'Segoe UI', Arial, sans-serif; background: #0a0e27; color: #fff; margin: 0; padding: 0; }}
  .container {{ max-width: 600px; margin: 0 auto; padding: 30px; }}
  .header {{ background: linear-gradient(135deg, #00d9ff 0%, #0066ff 100%); padding: 30px; border-radius: 16px 16px 0 0; text-align: center; }}
  .header h1 {{ margin: 0; font-size: 24px; color: #fff; }}
  .body {{ background: #141832; padding: 30px; border-radius: 0 0 16px 16px; }}
  .badge {{ display: inline-block; background: #00ff88; color: #000; padding: 8px 20px; border-radius: 20px; font-weight: bold; font-size: 18px; margin: 15px 0; }}
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
      <h1>🎉 Appointment Slots Available!</h1>
    </div>
    <div class="body">
      <p style="color: #fff;">Hi there,</p>
      <div style="text-align: center;">
        <span class="badge">SLOTS OPEN NOW</span>
      </div>
      <p style="color: #fff; font-size: 16px; margin-top: 16px;">Great news! Our monitoring detected <strong>available appointment slots</strong> on the TLS website.</p>
      <div class="info-row">
        <span class="info-label">Detected At</span>
        <span class="info-value">{now}</span>
      </div>
      <div class="info-row">
        <span class="info-label">Website</span>
        <span class="info-value">{Config.TLS_URL}</span>
      </div>
      <p style="color: #ffaa00; margin-top: 20px; font-size: 16px;">⚡ Act fast — slots fill up within minutes!</p>
      <div style="text-align: center;">
        <a href="{Config.TLS_URL}" class="cta">Book Now →</a>
      </div>
      <p style="color: #dddddd; font-size: 13px; margin-top: 24px;">This is an automated notification. Please verify availability on the website before proceeding.</p>
    </div>
    <div class="footer">
      <p>TLS Appointment Checker — Automated alert</p>
      <p>Do not reply to this email.</p>
    </div>
  </div>
</body>
</html>"""

        if "email" in notification_types:
            self.send_email(user_email, title, html, screenshot_path)

        if "windows" in notification_types:
            self.send_windows_notification(title, windows_message)

    def send_status_report(self, user_email: str, notification_types: list, total_checks: int, last_check: datetime, slots_found: bool):
        """Send 6-hour status report"""
        title = f"{Config.APP_NAME} — Status Report"
        now = datetime.now().strftime('%Y-%m-%d %H:%M')
        last_check_str = last_check.strftime('%Y-%m-%d %H:%M:%S') if last_check else 'Never'
        status_color = "#00ff88" if slots_found else "#8892b0"
        status_text = "✅ Slots were found in the last check!" if slots_found else "No slots found yet — monitoring continues."

        html = f"""<!DOCTYPE html>
<html>
<head>
<style>
  body {{ font-family: 'Segoe UI', Arial, sans-serif; background: #0a0e27; color: #fff; margin: 0; padding: 0; }}
  .container {{ max-width: 600px; margin: 0 auto; padding: 30px; }}
  .header {{ background: linear-gradient(135deg, #1e2448 0%, #141832 100%); border: 1px solid #00d9ff40; padding: 30px; border-radius: 16px 16px 0 0; text-align: center; }}
  .header h1 {{ margin: 0; font-size: 22px; color: #00d9ff; }}
  .body {{ background: #141832; padding: 30px; border-radius: 0 0 16px 16px; }}
  .info-row {{ display: flex; justify-content: space-between; padding: 12px 0; border-bottom: 1px solid #1e2448; }}
  .info-label {{ color: #dddddd; }}
  .info-value {{ color: #fff; font-weight: 600; }}
  .footer {{ text-align: center; padding: 20px; color: #dddddd; font-size: 12px; }}
</style>
</head>
<body>
  <div class="container">
    <div class="header">
      <h1>📊 Status Report</h1>
      <p style="color:#8892b0;margin:8px 0 0;">{now}</p>
    </div>
    <div class="body">
      <p style="color:{status_color}; font-size: 16px; font-weight: 600;">{status_text}</p>
      <div class="info-row">
        <span class="info-label">Total Checks</span>
        <span class="info-value">{total_checks}</span>
      </div>
      <div class="info-row">
        <span class="info-label">Last Check</span>
        <span class="info-value">{last_check_str}</span>
      </div>
      <div class="info-row">
        <span class="info-label">App Version</span>
        <span class="info-value">{Config.APP_VERSION}</span>
      </div>
      <p style="color: #dddddd; font-size: 13px; margin-top: 20px;">The system is monitoring for appointment slots at every configured interval. You will be notified immediately when slots become available.</p>
    </div>
    <div class="footer"><p>TLS Appointment Checker — Automated status report</p></div>
  </div>
</body>
</html>"""

        if "email" in notification_types:
            self.send_email(user_email, title, html)

        if "windows" in notification_types and slots_found:
            self.send_windows_notification(title, status_text)

    def send_trial_expiring_notification(self, user_email: str, days_remaining: int):
        """Send trial expiring notification"""
        title = f"{Config.APP_NAME} — Trial Expiring Soon"
        windows_msg = f"Your trial expires in {days_remaining} day(s)"

        html = f"""<!DOCTYPE html>
<html>
<head>
<style>
  body {{ font-family: 'Segoe UI', Arial, sans-serif; background: #0a0e27; color: #fff; margin: 0; padding: 0; }}
  .container {{ max-width: 600px; margin: 0 auto; padding: 30px; }}
  .header {{ background: linear-gradient(135deg, #ffaa00 0%, #ff6600 100%); padding: 30px; border-radius: 16px 16px 0 0; text-align: center; }}
  .header h1 {{ margin: 0; font-size: 24px; color: #fff; }}
  .body {{ background: #141832; padding: 30px; border-radius: 0 0 16px 16px; }}
  .cta {{ display: inline-block; background: linear-gradient(135deg, #ffaa00, #ff6600); color: #fff; padding: 14px 32px; border-radius: 8px; text-decoration: none; font-weight: 600; margin: 20px 0; }}
  .footer {{ text-align: center; padding: 20px; color: #dddddd; font-size: 12px; }}
</style>
</head>
<body>
  <div class="container">
    <div class="header">
      <h1>⏰ Trial Expiring Soon</h1>
    </div>
    <div class="body">
      <p style="color: #ffffff;">Hi there,</p>
      <p style="font-size: 18px; color: #ffaa00; font-weight: 600;">Your free trial expires in <strong>{days_remaining} day(s)</strong>.</p>
      <p>To continue using {Config.APP_NAME} after your trial expires, please purchase a license key from our website.</p>
      <div style="text-align: center;">
        <a href="{Config.WEBSITE_URL}" class="cta">Get a License →</a>
      </div>
      <p style="color: #dddddd; font-size: 13px; margin-top: 24px;">Thank you for using {Config.APP_NAME}!</p>
    </div>
    <div class="footer"><p>TLS Appointment Checker — Automated notification</p></div>
  </div>
</body>
</html>"""

        self.send_email(user_email, title, html)
        self.send_windows_notification(title, windows_msg)

    def send_registration_confirmation(self, user_email: str, full_name: str) -> bool:
        """Send registration confirmation email"""
        subject = f"Welcome to {Config.APP_NAME}!"
        html = f"""<!DOCTYPE html>
<html>
<head>
<style>
  body {{ font-family: 'Segoe UI', Arial, sans-serif; background: #0a0e27; color: #fff; margin: 0; padding: 0; }}
  .container {{ max-width: 600px; margin: 0 auto; padding: 30px; }}
  .header {{ background: linear-gradient(135deg, #00d9ff 0%, #0066ff 100%); padding: 30px; border-radius: 16px 16px 0 0; text-align: center; }}
  .header h1 {{ margin: 0; font-size: 24px; color: #fff; }}
  .body {{ background: #141832; padding: 30px; border-radius: 0 0 16px 16px; }}
  .step {{ display: flex; align-items: flex-start; margin: 12px 0; }}
  .step-num {{ background: #00d9ff; color: #000; border-radius: 50%; width: 24px; height: 24px; min-width: 24px; text-align: center; font-weight: bold; margin-right: 12px; line-height: 24px; font-size: 13px; }}
  .cta {{ display: inline-block; background: linear-gradient(135deg, #00d9ff, #0066ff); color: #fff; padding: 14px 32px; border-radius: 8px; text-decoration: none; font-weight: 600; margin: 20px 0; }}
  .footer {{ text-align: center; padding: 20px; color: #dddddd; font-size: 12px; }}
</style>
</head>
<body>
  <div class="container">
    <div class="header">
      <h1>🎉 Welcome to {Config.APP_NAME}!</h1>
    </div>
    <div class="body">
      <p>Hi {full_name},</p>
      <p>Your account has been successfully created. You now have <strong style="color:#00ff88">{Config.TRIAL_DAYS} days of free trial</strong> to explore all features.</p>
      <h3 style="color: #00d9ff;">Get started in 3 steps:</h3>
      <div class="step"><div class="step-num">1</div><span>Login to your account</span></div>
      <div class="step"><div class="step-num">2</div><span>Configure your TLS credentials in the app</span></div>
      <div class="step"><div class="step-num">3</div><span>Start monitoring and get notified instantly</span></div>
      <div style="text-align: center;">
        <a href="{Config.WEBSITE_URL}" class="cta">Open Dashboard →</a>
      </div>
    </div>
    <div class="footer"><p>TLS Appointment Checker — Thank you for signing up!</p></div>
  </div>
</body>
</html>"""
        return self.send_email(user_email, subject, html)

    def send_monitoring_reminder(self, user_email: str, slot_details: str = ""):
        """Send 12-hour reminder that appointments are still available."""
        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        html = f"""<!DOCTYPE html>
<html>
<head>
<style>
  body {{ font-family: 'Segoe UI', Arial, sans-serif; background: #0a0e27; color: #fff; margin: 0; padding: 0; }}
  .container {{ max-width: 600px; margin: 0 auto; padding: 30px; }}
  .header {{ background: linear-gradient(135deg, #ffaa00 0%, #ff6600 100%); padding: 30px; border-radius: 16px 16px 0 0; text-align: center; }}
  .header h1 {{ margin: 0; font-size: 24px; color: #fff; }}
  .body {{ background: #141832; padding: 30px; border-radius: 0 0 16px 16px; }}
  .badge {{ display: inline-block; background: #ffaa00; color: #000; padding: 8px 20px; border-radius: 20px; font-weight: bold; font-size: 16px; margin: 15px 0; }}
  .cta {{ display: inline-block; background: linear-gradient(135deg, #ffaa00, #ff6600); color: #fff; padding: 14px 32px; border-radius: 8px; text-decoration: none; font-weight: 600; margin: 20px 0; }}
  .footer {{ text-align: center; padding: 20px; color: #dddddd; font-size: 12px; }}
</style>
</head>
<body>
  <div class="container">
    <div class="header">
      <h1>⏰ 12-Hour Reminder — Slots Still Available</h1>
    </div>
    <div class="body">
      <p style="color: #ffffff;">Hi there,</p>
      <div style="text-align: center;"><span class="badge">REMINDER</span></div>
      <p style="font-size: 16px; margin-top: 16px;">This is a reminder that <strong>appointment slots are still available</strong> on the TLS website. We notified you 12 hours ago and haven't detected any changes.</p>
      <p style="color: #ffaa00; font-size: 15px;">⚡ If you haven't booked yet, now is the time!</p>
      {'<p style="color: #dddddd; font-size: 13px;">Details: ' + slot_details + '</p>' if slot_details else ''}
      <p style="color: #dddddd; font-size: 12px;">Detected at: {now}</p>
      <div style="text-align: center;">
        <a href="{Config.TLS_URL}" class="cta">Book Now &rarr;</a>
      </div>
      <p style="color: #dddddd; font-size: 12px; margin-top: 24px;">This is the final automated reminder for this availability window. Monitoring continues in the background.</p>
    </div>
    <div class="footer"><p>TLS Appointment Checker &mdash; Automated reminder</p></div>
  </div>
</body>
</html>"""
        self.send_email(user_email, "⏰ Reminder: TLS Appointment Slots Still Available", html)

    def send_error_notification(self, user_email: str, error_message: str):
        """Send an alert when a monitoring check fails with an error."""
        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        safe_error = str(error_message).replace('<', '&lt;').replace('>', '&gt;')
        html = f"""<!DOCTYPE html>
<html>
<head>
<style>
  body {{ font-family: 'Segoe UI', Arial, sans-serif; background: #0a0e27; color: #fff; margin: 0; padding: 0; }}
  .container {{ max-width: 600px; margin: 0 auto; padding: 30px; }}
  .header {{ background: linear-gradient(135deg, #ff4444 0%, #cc0000 100%); padding: 30px; border-radius: 16px 16px 0 0; text-align: center; }}
  .header h1 {{ margin: 0; font-size: 24px; color: #fff; }}
  .body {{ background: #141832; padding: 30px; border-radius: 0 0 16px 16px; }}
  .error-box {{ background: #2a1520; border: 1px solid #ff4444; border-radius: 8px; padding: 16px; margin: 16px 0; font-family: monospace; font-size: 13px; color: #ff8888; word-break: break-all; }}
  .footer {{ text-align: center; padding: 20px; color: #dddddd; font-size: 12px; }}
  .tip {{ background: #1a2040; border-left: 3px solid #00d9ff; padding: 12px 16px; margin: 16px 0; border-radius: 0 8px 8px 0; }}
</style>
</head>
<body>
  <div class="container">
    <div class="header">
      <h1>&#9888; Monitoring Check Failed</h1>
    </div>
    <div class="body">
      <p style="color: #ffffff;">Hi there,</p>
      <p style="color: #ffffff;">The TLS monitoring check encountered an error at <strong>{now}</strong> and could not complete successfully.</p>
      <div class="error-box">{safe_error}</div>
      <div class="tip">
        <p style="margin:0; color: #00d9ff; font-weight: 600;">Common fixes:</p>
        <ul style="margin: 8px 0 0 0; color: #dddddd;">
          <li>Verify your TLS email and password are correct in the app settings</li>
          <li>Check your internet connection</li>
          <li>The TLS website may be temporarily down or under maintenance</li>
          <li>If the error persists, try restarting the monitoring</li>
        </ul>
      </div>
      <p style="color: #dddddd; font-size: 13px;">Monitoring will automatically retry. You will only receive this email once per hour for repeated errors.</p>
    </div>
    <div class="footer"><p>TLS Appointment Checker &mdash; Error alert</p></div>
  </div>
</body>
</html>"""
        self.send_email(user_email, "⚠️ TLS Monitoring Error — Action May Be Required", html)


# Global notification service instance
notification_service = NotificationService()
