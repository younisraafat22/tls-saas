"""
Notification Service
Handles email and Windows toast notifications
"""
import sys
import smtplib
import json
import urllib.request
import urllib.error
from html import escape
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
from datetime import datetime
from typing import Optional
import os
from pathlib import Path
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

    def _log_relay(self, message: str) -> None:
        """Persist relay diagnostics (frozen apps have no console)."""
        try:
            log_path = Path(str(Config.BASE_DIR)) / "email_relay.log"
            log_path.parent.mkdir(parents=True, exist_ok=True)
            ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            with open(log_path, "a", encoding="utf-8") as f:
                f.write(f"[{ts}] {message}\n")
        except Exception:
            pass

    @staticmethod
    def _relay_endpoint_bases() -> list[str]:
        """Same discovery order as license checks: Vercel /api/backend-url, LICENSE_SERVER_URL, BACKEND_URL."""
        from license_service import _build_backend_urls

        urls = _build_backend_urls()
        if not urls:
            b = (getattr(Config, "BACKEND_URL", None) or "").strip().rstrip("/")
            if b:
                urls = [b]
        return urls

    @staticmethod
    def _redact_license_key(key: str) -> str:
        k = (key or "").strip()
        if len(k) <= 6:
            return "***"
        return f"{k[:4]}…{k[-2:]}"

    def _send_email_via_backend_relay(
        self, to_email: str, subject: str, html_body: str, screenshot_path: Optional[str]
    ) -> bool:
        """
        POST to FastAPI /api/monitoring/desktop-email-relay on each discovered API base URL.
        Uses the same URL list as license verification (Vercel discovery first).
        """
        frozen = getattr(sys, "frozen", False)
        if screenshot_path and os.path.exists(screenshot_path):
            self._log_relay(
                "relay: screenshot attachment skipped (relay sends HTML only; "
                "unfrozen + ALLOW_LOCAL_SMTP=1 enables local SMTP with attachments)"
            )
        try:
            from license_service import _read_license_file, _safe_urlopen, get_hardware_id

            lic = _read_license_file()
            if not lic or not lic.get("key"):
                self._log_relay("relay skipped: no license key on disk")
                return False

            hw = get_hardware_id() or ""
            payload_obj = {
                "license_key": lic["key"],
                "hardware_id": hw,
                "to_email": to_email.strip(),
                "subject": subject,
                "html_body": html_body,
            }

            ua = "TLSAppointmentChecker/1.0 (Windows; email-relay)"
            hdr_json = {
                "Content-Type": "application/json",
                "Accept": "application/json",
                "User-Agent": ua,
            }

            bases = self._relay_endpoint_bases()
            self._log_relay(
                f"relay debug: frozen={frozen} bases={bases} "
                f"license_key={self._redact_license_key(str(lic.get('key', '')))} hw_len={len(hw)}"
            )
            if not bases:
                self._log_relay(
                    "relay aborted: no backend base URL (set BACKEND_URL / LICENSE_SERVER_URL; "
                    "or ensure Vercel NEXT_PUBLIC_API_URL + /api/backend-url discovery works)"
                )
                return False

            relay_path = "/api/monitoring/desktop-email-relay"
            last_err = ""

            import requests

            try:
                import certifi

                verify = certifi.where()
            except Exception:
                verify = True

            for i, base in enumerate(bases, start=1):
                base = (base or "").strip().rstrip("/")
                if not base:
                    continue
                url = f"{base}{relay_path}"
                self._log_relay(f"relay attempt {i}/{len(bases)} POST {url}")

                try:
                    r = requests.post(
                        url,
                        json=payload_obj,
                        timeout=45,
                        headers={"User-Agent": ua, "Accept": "application/json"},
                        verify=verify,
                        allow_redirects=True,
                    )
                    final_url = getattr(r, "url", url)
                    if final_url != url:
                        self._log_relay(f"relay debug: requests final URL after redirects: {final_url}")
                    if int(r.status_code) < 400:
                        self._log_relay(f"relay OK: status={r.status_code} base={base}")
                        return True
                    body = (r.text or "")[:800]
                    self._log_relay(f"relay HTTP {r.status_code} body_snip={body[:500]!r}")
                    last_err = f"HTTP {r.status_code}"
                    if r.status_code == 404:
                        if "vercel.app" in base.lower() or "tls-saas" in base.lower():
                            self._log_relay(
                                "relay hint: 404 on website host — the FastAPI app is usually on Fly.io. "
                                "Point BACKEND_URL at the API base, or fix NEXT_PUBLIC_API_URL on Vercel."
                            )
                        try:
                            h = requests.get(
                                f"{base}/api/health",
                                timeout=10,
                                headers={"User-Agent": ua},
                                verify=verify,
                            )
                            self._log_relay(
                                f"relay probe GET {base}/api/health -> {h.status_code} "
                                f"{(h.text or '')[:200]!r}"
                            )
                        except Exception as probe_exc:
                            self._log_relay(f"relay probe /api/health failed: {type(probe_exc).__name__}: {probe_exc!r}")
                except Exception as ex_req:
                    self._log_relay(f"relay requests: {type(ex_req).__name__}: {ex_req!r}")
                    last_err = str(ex_req)

                payload = json.dumps(payload_obj, ensure_ascii=False).encode("utf-8")
                req = urllib.request.Request(
                    url,
                    data=payload,
                    headers=hdr_json,
                    method="POST",
                )
                try:
                    with _safe_urlopen(req, timeout=45) as resp:
                        code = int(getattr(resp, "status", 200))
                        if code < 400:
                            self._log_relay(f"relay OK (urllib): status={code} base={base}")
                            return True
                        body = resp.read().decode(errors="replace")[:500]
                        self._log_relay(f"relay urllib HTTP {code}: {body}")
                        last_err = f"urllib HTTP {code}"
                except urllib.error.HTTPError as e:
                    body = e.read().decode(errors="replace")[:500] if e.fp else ""
                    self._log_relay(f"relay urllib HTTPError {e.code}: {body}")
                    last_err = f"HTTPError {e.code}"
                except Exception as uex:
                    self._log_relay(f"relay urllib: {type(uex).__name__}: {uex!r}")
                    last_err = str(uex)

            self._log_relay(f"relay failed on all bases ({len(bases)}). Last error: {last_err}")
            return False
        except Exception as e:
            import traceback

            self._log_relay(f"relay failed: {e}\n{traceback.format_exc()}")
            return False

    def _try_local_smtp(
        self, to_email: str, subject: str, html_body: str, screenshot_path: Optional[str]
    ) -> bool:
        """Return True if Gmail/local SMTP succeeds."""
        msg = MIMEMultipart("mixed")
        msg["From"] = f"TLS Appointment Checker <{Config.ADMIN_EMAIL}>"
        msg["To"] = to_email
        msg["Subject"] = subject

        alt = MIMEMultipart("alternative")
        alt.attach(MIMEText(html_body, "html"))
        msg.attach(alt)

        if screenshot_path and os.path.exists(screenshot_path):
            with open(screenshot_path, "rb") as attachment:
                part = MIMEBase("application", "octet-stream")
                part.set_payload(attachment.read())
                encoders.encode_base64(part)
                filename = os.path.basename(screenshot_path)
                part.add_header("Content-Disposition", f'attachment; filename="{filename}"')
                msg.attach(part)

        server = smtplib.SMTP(Config.SMTP_SERVER, Config.SMTP_PORT)
        server.starttls()
        server.login(Config.ADMIN_EMAIL, Config.ADMIN_EMAIL_PASSWORD)
        server.sendmail(msg["From"], to_email, msg.as_string())
        server.quit()
        return True

    def send_email(self, to_email: str, subject: str, html_body: str, screenshot_path: str = None) -> bool:
        """Send an HTML email notification with optional screenshot attachment."""
        if not to_email or not to_email.strip():
            print("Email notification skipped: no recipient email configured")
            return False

        frozen = getattr(sys, "frozen", False)
        # Installed .exe: never use local SMTP (no Gmail credentials in the client). Relay only.
        # Dev: optional local SMTP if ADMIN_* set and ALLOW_LOCAL_SMTP is not 0/false/no.
        allow_smtp = not frozen
        if allow_smtp:
            allow_smtp = os.getenv("ALLOW_LOCAL_SMTP", "1").strip().lower() not in ("0", "false", "no")
        use_local_smtp = bool(Config.ADMIN_EMAIL and Config.ADMIN_EMAIL_PASSWORD) and allow_smtp

        if use_local_smtp:
            try:
                return self._try_local_smtp(to_email, subject, html_body, screenshot_path)
            except Exception as e:
                print(f"Email notification failed: {e}")
                self._log_relay(f"local SMTP failed, trying relay: {e}")
                return self._send_email_via_backend_relay(to_email, subject, html_body, screenshot_path)

        return self._send_email_via_backend_relay(to_email, subject, html_body, screenshot_path)
    
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
    
    def send_slots_available_notification(
        self,
        user_email: str,
        notification_types: list,
        screenshot_path: str = None,
        *,
        slot_details: str = "",
        tls_disabled_month_booking_tip: bool = False,
        tls_month_probe_example_url: str | None = None,
    ):
        """Send notification when slots are available"""
        title = "🎉 TLS Appointments Available!"
        windows_message = "Appointment slots are now available! Log in to the TLS website immediately to book."
        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        details_html = ""
        if slot_details:
            safe_details = escape(str(slot_details).strip()).replace("\n", "<br>")
            details_html = (
                '<div style="background:#1a1f3a;border:1px solid #00d9ff40;border-radius:10px;padding:14px 16px;margin:16px 0;">'
                '<p style="color:#00d9ff;font-weight:600;margin:0 0 8px 0;font-size:14px;">Detected slot details</p>'
                f'<p style="color:#ddd;font-size:13px;line-height:1.5;margin:0;word-break:break-word;">{safe_details}</p>'
                '</div>'
            )

        tip_html = ""
        if tls_disabled_month_booking_tip:
            ex_url = (tls_month_probe_example_url or "").strip()
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
                "To book, open your appointment booking link and edit only the <strong>month=</strong> numbers "
                "(for example <code style=\"color:#7dd3fc;\">month=05-2026</code> → <code style=\"color:#7dd3fc;\">month=06-2026</code>, "
                "or <code style=\"color:#7dd3fc;\">month=05-26</code> → <code style=\"color:#7dd3fc;\">month=06-26</code>) then press Enter."
                "</p>"
                f"{ex_block}"
                "</div>"
            )
            windows_message = (
                "Slots may be on a month that looks disabled on TLS. Edit month= in the booking URL if needed, then book."
            )

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
      {details_html}
      <div class="info-row">
        <span class="info-label">Detected At</span>
        <span class="info-value">{now}</span>
      </div>
      <div class="info-row">
        <span class="info-label">Website</span>
        <span class="info-value">{Config.TLS_URL}</span>
      </div>
      {tip_html}
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

    def send_monitoring_reminder(
        self,
        user_email: str,
        slot_details: str = "",
        *,
        tls_disabled_month_booking_tip: bool = False,
        tls_month_probe_example_url: str | None = None,
    ):
        """Send 12-hour reminder that appointments are still available."""
        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        tip_html = ""
        if tls_disabled_month_booking_tip:
            ex_url = (tls_month_probe_example_url or "").strip()
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
                "If that month still looks greyed out, edit <strong>month=</strong> in your booking URL "
                "(e.g. <code style=\"color:#7dd3fc;\">month=05-2026</code> → <code style=\"color:#7dd3fc;\">month=06-2026</code>) "
                "and press Enter."
                "</p>"
                f"{ex_block}"
                "</div>"
            )

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
      {tip_html}
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
