"""
TLS Appointment Checker — Combined Monitoring & License Server
==============================================================
Run this on YOUR PC (or a dedicated server/laptop) to:
  1. License management   (replaces Railway — generate, validate, revoke)
  2. Cloud monitoring     (run Selenium checks for ALL your users)

Users install the desktop app, enter their credentials, click Start,
and THIS server does the actual checking.  The user's PC does NOT need
to stay on.

Usage
-----
    python monitoring_server.py                    # local only (port 5000)
    python monitoring_server.py --ngrok            # + public ngrok tunnel
    python monitoring_server.py --port 8080        # custom port

Requirements
------------
    pip install flask flask-cors cryptography
    pip install pyngrok          (optional, for public access)
    Google Chrome installed on this machine

Environment Variables (optional — sensible defaults built-in)
-------------------------------------------------------------
    ADMIN_API_KEY       Admin bearer token  (default: printed on startup)
    CREDENTIAL_SECRET   Passphrase for encrypting stored TLS passwords
    MAX_BROWSERS        Max concurrent Selenium sessions (default 2)
    PORT                Server port (default 5000)
"""

import argparse
import base64
import hashlib
import hmac
import json
import os
import secrets
import signal
import smtplib
import sqlite3
import sys
import threading
import time
import traceback
from datetime import datetime, timezone, timedelta
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders
from functools import wraps

from flask import Flask, jsonify, request, abort
from flask_cors import CORS
from dotenv import load_dotenv

# ── Ensure sibling imports work ────────────────────────────────────
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Load desktop .env so production secrets can live outside source code.
load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env"), override=False)

# ── Fernet for encrypting user TLS passwords at rest ──────────────
from cryptography.fernet import Fernet

def _make_fernet(passphrase: str) -> Fernet:
    key = hashlib.sha256(passphrase.encode()).digest()
    return Fernet(base64.urlsafe_b64encode(key))

_fernet = _make_fernet(os.environ.get("CREDENTIAL_SECRET", ""))

# ══════════════════════════════════════════════════════════════════════
#  FLASK APP
# ══════════════════════════════════════════════════════════════════════
app = Flask(__name__)
CORS(app, resources={r"/api/*": {"origins": "*"}})

@app.before_request
def log_request():
    """Log all incoming requests for debugging."""
    print(f"[Request] {request.method} {request.path} from {request.remote_addr}")

LICENSE_SECRET = os.environ.get("LICENSE_HMAC_SECRET", "")
ADMIN_API_KEY  = os.environ.get("ADMIN_API_KEY", secrets.token_hex(16))
MAX_BROWSERS   = int(os.environ.get("MAX_BROWSERS", "2"))

# SMTP config (for sending license keys & notifications from server)
SMTP_SERVER  = os.environ.get("SMTP_SERVER", "smtp.gmail.com")
SMTP_PORT    = int(os.environ.get("SMTP_PORT", "587"))
SMTP_USER    = os.environ.get("ADMIN_EMAIL", "")
SMTP_PASS    = os.environ.get("ADMIN_EMAIL_PASSWORD", "")


def _ensure_secure_config():
    missing = []
    if not os.environ.get("CREDENTIAL_SECRET", ""):
        missing.append("CREDENTIAL_SECRET")
    if not LICENSE_SECRET:
        missing.append("LICENSE_HMAC_SECRET")
    if missing:
        raise RuntimeError(
            "Missing required security settings for monitoring_server.py: "
            + ", ".join(missing)
        )

# ══════════════════════════════════════════════════════════════════════
#  DATABASE  (SQLite — single file for everything)
# ══════════════════════════════════════════════════════════════════════
DB_PATH = os.environ.get("MONITOR_DB_PATH",
                          os.path.join(os.path.dirname(__file__), "monitoring_server.db"))

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn

def init_db():
    conn = get_db()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS licenses (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            license_key   TEXT UNIQUE NOT NULL,
            plan          TEXT NOT NULL,
            hardware_id   TEXT NOT NULL,
            customer_email TEXT,
            customer_name  TEXT,
            payment_provider TEXT DEFAULT 'manual',
            amount_paid   REAL DEFAULT 0,
            currency      TEXT DEFAULT 'USD',
            created_at    TEXT NOT NULL,
            expires_at    TEXT,
            is_active     INTEGER DEFAULT 1,
            notes         TEXT
        );

        CREATE TABLE IF NOT EXISTS monitoring_jobs (
            id                INTEGER PRIMARY KEY AUTOINCREMENT,
            license_key       TEXT NOT NULL,
            hardware_id       TEXT NOT NULL,
            tls_email         TEXT NOT NULL,
            tls_password_enc  TEXT NOT NULL,
            service_type      TEXT DEFAULT 'legalization',
            branch            TEXT DEFAULT 'Sheikh Zayed',
            branch_url        TEXT,
            notification_email TEXT NOT NULL,
            check_interval    INTEGER DEFAULT 60,
            is_active         INTEGER DEFAULT 1,
            status            TEXT DEFAULT 'pending',
            last_check_at     TEXT,
            last_status       TEXT,
            total_checks      INTEGER DEFAULT 0,
            slots_found_total INTEGER DEFAULT 0,
            error_count       INTEGER DEFAULT 0,
            created_at        TEXT NOT NULL,
            updated_at        TEXT
        );

        CREATE TABLE IF NOT EXISTS monitoring_logs (
            id        INTEGER PRIMARY KEY AUTOINCREMENT,
            job_id    INTEGER NOT NULL,
            timestamp TEXT NOT NULL,
            message   TEXT NOT NULL,
            level     TEXT DEFAULT 'info'
        );

        CREATE INDEX IF NOT EXISTS idx_jobs_hw ON monitoring_jobs(hardware_id);
        CREATE INDEX IF NOT EXISTS idx_jobs_active ON monitoring_jobs(is_active);
        CREATE INDEX IF NOT EXISTS idx_logs_job ON monitoring_logs(job_id);
    """)
    conn.commit()
    conn.close()

# ── helpers ───────────────────────────────────────────────────────────

def _now_iso():
    return datetime.now(timezone.utc).isoformat()

def _add_log(job_id: int, message: str, level: str = "info"):
    """Append a log entry for a monitoring job."""
    try:
        conn = get_db()
        conn.execute("INSERT INTO monitoring_logs (job_id, timestamp, message, level) VALUES (?,?,?,?)",
                     (job_id, _now_iso(), message, level))
        conn.commit()
        conn.close()
        print(f"  [Job {job_id}] {message}")
    except Exception:
        pass

def _update_job(job_id: int, **fields):
    """Update monitoring job fields."""
    if not fields:
        return
    fields["updated_at"] = _now_iso()
    sets = ", ".join(f"{k}=?" for k in fields)
    vals = list(fields.values()) + [job_id]
    conn = get_db()
    conn.execute(f"UPDATE monitoring_jobs SET {sets} WHERE id=?", vals)
    conn.commit()
    conn.close()

# ══════════════════════════════════════════════════════════════════════
#  LICENSE KEY HELPERS
# ══════════════════════════════════════════════════════════════════════

def _sign(payload: str) -> str:
    return hmac.new(LICENSE_SECRET.encode(), payload.encode(), hashlib.sha256).hexdigest()[:16]

def generate_license_key(plan: str, hardware_id: str) -> str:
    plan_normalized = plan.lower()
    hw_short = hardware_id[:8].upper() if len(hardware_id) >= 8 else "PENDING0"
    rand = secrets.token_hex(4).upper()
    payload = f"{plan_normalized}:{hw_short}:{rand}"
    sig = _sign(payload).upper()
    return f"{plan_normalized.upper()}-{hw_short}-{rand}-{sig}"

# ══════════════════════════════════════════════════════════════════════
#  EMAIL HELPERS
# ══════════════════════════════════════════════════════════════════════

def _send_email(to: str, subject: str, body_html: str) -> bool:
    if not SMTP_USER or not SMTP_PASS:
        print(f"[EMAIL] SMTP not configured — skipping email to {to}")
        return False
    try:
        msg = MIMEMultipart("alternative")
        msg["From"] = f"TLS Appointment Checker <{SMTP_USER}>"
        msg["To"] = to
        msg["Subject"] = subject
        msg.attach(MIMEText(body_html, "html"))
        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT, timeout=30) as s:
            s.starttls()
            s.login(SMTP_USER, SMTP_PASS)
            s.send_message(msg)
        print(f"[EMAIL] ✅ Sent to {to}")
        return True
    except Exception as e:
        print(f"[EMAIL] ❌ Failed to {to}: {e}")
        return False

def _send_slots_email(to: str, branch: str, screenshot_path: str = None) -> bool:
    """Send appointment-found notification email with optional screenshot."""
    subject = "🎉 TLS Appointments Available!"
    html = f"""
    <div style="font-family:Arial;max-width:600px;margin:0 auto;background:#0A0E27;color:#E0E0E0;padding:30px;border-radius:16px;">
      <h1 style="color:#00D9FF;text-align:center;">Appointments Found! 🎉</h1>
      <p>Great news — appointment slots have been detected at <strong>{branch}</strong>!</p>
      <p style="font-size:18px;color:#00FF88;font-weight:bold;">
        ⚠️ Log in to the TLS website NOW and book your appointment.
      </p>
      <p>Checked at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
      <hr style="border:none;border-top:1px solid #333;margin:25px 0;">
      <p style="color:#666;font-size:12px;text-align:center;">
        TLS Appointment Checker · Automated Notification
      </p>
    </div>"""
    try:
        msg = MIMEMultipart("mixed")
        msg["From"] = f"TLS Appointment Checker <{SMTP_USER}>"
        msg["To"] = to
        msg["Subject"] = subject
        msg.attach(MIMEText(html, "html"))
        # Attach screenshot if available
        if screenshot_path and os.path.exists(screenshot_path):
            with open(screenshot_path, "rb") as f:
                part = MIMEBase("application", "octet-stream")
                part.set_payload(f.read())
                encoders.encode_base64(part)
                part.add_header("Content-Disposition",
                                f"attachment; filename={os.path.basename(screenshot_path)}")
                msg.attach(part)
        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT, timeout=30) as s:
            s.starttls()
            s.login(SMTP_USER, SMTP_PASS)
            s.send_message(msg)
        print(f"[EMAIL] ✅ Slots notification sent to {to}")
        return True
    except Exception as e:
        print(f"[EMAIL] ❌ Slots notification failed for {to}: {e}")
        return False

# ══════════════════════════════════════════════════════════════════════
#  AUTH MIDDLEWARE
# ══════════════════════════════════════════════════════════════════════

def require_admin(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        auth = request.headers.get("Authorization", "")
        if not auth.startswith("Bearer ") or auth[7:] != ADMIN_API_KEY:
            abort(401, "Unauthorized")
        return f(*args, **kwargs)
    return decorated

# ══════════════════════════════════════════════════════════════════════
#  LICENSE ROUTES  (replaces Railway server)
# ══════════════════════════════════════════════════════════════════════

@app.route("/health", methods=["GET"])
def health():
    return jsonify({
        "status": "ok",
        "service": "TLS Monitoring & License Server",
        "monitoring": True,
        "active_jobs": _count_active_jobs(),
    })

@app.route("/api/license/verify", methods=["POST"])
def verify_license():
    data = request.get_json() or {}
    hardware_id = data.get("hardware_id", "")
    license_key = data.get("license_key", "")
    if not hardware_id and not license_key:
        return jsonify({"error": "Missing hardware_id or license_key"}), 400
    conn = get_db()
    if license_key:
        row = conn.execute(
            "SELECT license_key,plan,customer_email,created_at,is_active FROM licenses WHERE license_key=? ORDER BY created_at DESC LIMIT 1",
            (license_key,)).fetchone()
    else:
        row = conn.execute(
            "SELECT license_key,plan,customer_email,created_at,is_active FROM licenses WHERE hardware_id=? AND is_active=1 ORDER BY created_at DESC LIMIT 1",
            (hardware_id,)).fetchone()
    conn.close()
    if row:
        return jsonify({"found": True, "license_key": row["license_key"], "plan": row["plan"],
                        "email": row["customer_email"], "is_active": bool(row["is_active"])})
    return jsonify({"found": False})

@app.route("/api/license/generate", methods=["POST"])
@require_admin
def admin_generate_license():
    data = request.get_json() or {}
    plan = data.get("plan"); hw = data.get("hardware_id")
    email = data.get("email", ""); name = data.get("name", "")
    if not plan or not hw:
        return jsonify({"error": "Missing plan or hardware_id"}), 400
    key = generate_license_key(plan, hw)
    conn = get_db()
    conn.execute(
        "INSERT INTO licenses (license_key,plan,hardware_id,customer_email,customer_name,created_at,is_active) VALUES (?,?,?,?,?,?,1)",
        (key, plan, hw, email, name, _now_iso()))
    conn.commit(); conn.close()
    if data.get("send_email", True) and email:
        _send_license_email(email, name, plan, key)
    return jsonify({"license_key": key, "plan": plan, "hardware_id": hw})

@app.route("/api/licenses", methods=["GET"])
@require_admin
def list_licenses():
    conn = get_db()
    rows = conn.execute("SELECT * FROM licenses ORDER BY created_at DESC").fetchall()
    conn.close()
    return jsonify([dict(r) for r in rows])

@app.route("/api/license/revoke", methods=["POST"])
@require_admin
def revoke_license():
    data = request.get_json() or {}
    lk = data.get("license_key", "").strip()
    hw = data.get("hardware_id", "").strip()
    if not lk and not hw:
        return jsonify({"error": "Provide license_key or hardware_id"}), 400
    conn = get_db()
    if lk:
        conn.execute("UPDATE licenses SET is_active=0 WHERE license_key=?", (lk,))
    else:
        conn.execute("UPDATE licenses SET is_active=0 WHERE hardware_id=?", (hw,))
    # Also stop monitoring jobs for this license/device
    if lk:
        conn.execute("UPDATE monitoring_jobs SET is_active=0, status='revoked' WHERE license_key=?", (lk,))
    if hw:
        conn.execute("UPDATE monitoring_jobs SET is_active=0, status='revoked' WHERE hardware_id=?", (hw,))
    conn.commit()
    affected = conn.total_changes
    conn.close()
    return jsonify({"success": True, "revoked": affected})

@app.route("/api/license/deactivate", methods=["POST"])
def deactivate_license():
    data = request.get_json() or {}
    lk = data.get("license_key", "").strip()
    hw = data.get("hardware_id", "").strip()
    if not lk or not hw:
        return jsonify({"error": "Both license_key and hardware_id required"}), 400
    conn = get_db()
    cur = conn.execute("UPDATE licenses SET is_active=0 WHERE license_key=? AND hardware_id=?", (lk, hw))
    conn.commit(); affected = cur.rowcount; conn.close()
    if affected:
        return jsonify({"success": True, "deactivated": affected})
    return jsonify({"success": False, "error": "Not found or already deactivated"}), 404

@app.route("/api/license/retrieve", methods=["POST"])
@require_admin
def retrieve_license():
    data = request.get_json() or {}
    email = data.get("email", "").strip().lower()
    if not email:
        return jsonify({"error": "Email required"}), 400
    conn = get_db()
    row = conn.execute(
        "SELECT license_key,plan,created_at FROM licenses WHERE LOWER(customer_email)=? AND is_active=1 ORDER BY created_at DESC LIMIT 1",
        (email,)).fetchone()
    conn.close()
    if row:
        return jsonify({"success": True, "license_key": row[0], "plan": row[1], "created_at": row[2]})
    return jsonify({"success": False, "error": "No license found"}), 404

def _send_license_email(to_email, name, plan, key):
    plan_names = {"trial": "Trial", "lifetime": "Lifetime", "basic_monthly": "Basic Monthly", "pro_monthly": "Pro Monthly"}
    plan_display = plan_names.get(plan, plan)
    html = f"""
    <div style="font-family:Arial;max-width:600px;margin:0 auto;background:#0A0E27;color:#E0E0E0;padding:30px;border-radius:16px;">
      <h1 style="color:#00D9FF;text-align:center;">Your License Key 🔑</h1>
      <p>Hi {name or 'there'},</p>
      <p>Here is your <strong>{plan_display}</strong> license key:</p>
      <div style="background:#1A1F3A;border:2px solid #00D9FF;border-radius:12px;padding:20px;text-align:center;margin:20px 0;">
        <p style="color:#00D9FF;font-size:18px;font-weight:bold;letter-spacing:1px;word-break:break-all;">{key}</p>
      </div>
      <h3 style="color:#00D9FF;">How to activate:</h3>
      <ol><li>Open the app</li><li>Go to Pricing</li><li>Click "Already have a license key?"</li><li>Paste your key and click Activate</li></ol>
      <hr style="border:none;border-top:1px solid #333;margin:25px 0;">
      <p style="color:#666;font-size:12px;text-align:center;">TLS Appointment Checker</p>
    </div>"""
    _send_email(to_email, f"🔑 Your TLS Appointment Checker License — {plan_display}", html)

# ══════════════════════════════════════════════════════════════════════
#  MONITORING ROUTES  (cloud-based checking)
# ══════════════════════════════════════════════════════════════════════

def _count_active_jobs():
    try:
        conn = get_db()
        n = conn.execute("SELECT COUNT(*) FROM monitoring_jobs WHERE is_active=1").fetchone()[0]
        conn.close()
        return n
    except Exception:
        return 0

@app.route("/api/monitoring/start", methods=["POST"])
def monitoring_start():
    """
    User submits their config to start cloud monitoring.
    Expects JSON: {
      license_key, hardware_id,
      tls_email, tls_password,
      service_type, branch, branch_url,
      notification_email, check_interval
    }
    """
    data = request.get_json() or {}
    required = ["license_key", "hardware_id", "tls_email", "tls_password", "notification_email"]
    missing = [k for k in required if not data.get(k)]
    if missing:
        return jsonify({"error": f"Missing: {', '.join(missing)}"}), 400

    hw = data["hardware_id"]
    lk = data["license_key"]

    # Validate license is active
    conn = get_db()
    lic = conn.execute("SELECT is_active FROM licenses WHERE license_key=? AND hardware_id=?", (lk, hw)).fetchone()
    if not lic or not bool(lic["is_active"]):
        conn.close()
        return jsonify({"error": "License is not registered or is inactive"}), 403

    # Encrypt TLS password
    enc_pass = _fernet.encrypt(data["tls_password"].encode()).decode()

    # Check if job already exists for this device
    existing = conn.execute("SELECT id FROM monitoring_jobs WHERE hardware_id=?", (hw,)).fetchone()
    now = _now_iso()

    if existing:
        # Update existing job
        conn.execute("""
            UPDATE monitoring_jobs SET
                license_key=?, tls_email=?, tls_password_enc=?,
                service_type=?, branch=?, branch_url=?,
                notification_email=?, check_interval=?,
                is_active=1, status='pending', updated_at=?
            WHERE hardware_id=?
        """, (lk, data["tls_email"], enc_pass,
              data.get("service_type", "legalization"),
              data.get("branch", "Sheikh Zayed"),
              data.get("branch_url", ""),
              data["notification_email"],
              data.get("check_interval", 60),
              now, hw))
        job_id = existing["id"]
        _add_log(job_id, "Monitoring re-started (config updated)")
    else:
        cur = conn.execute("""
            INSERT INTO monitoring_jobs
                (license_key, hardware_id, tls_email, tls_password_enc,
                 service_type, branch, branch_url, notification_email,
                 check_interval, is_active, status, created_at, updated_at)
            VALUES (?,?,?,?,?,?,?,?,?,1,'pending',?,?)
        """, (lk, hw, data["tls_email"], enc_pass,
              data.get("service_type", "legalization"),
              data.get("branch", "Sheikh Zayed"),
              data.get("branch_url", ""),
              data["notification_email"],
              data.get("check_interval", 60),
              now, now))
        job_id = cur.lastrowid
        _add_log(job_id, "Monitoring started")

    conn.commit()
    conn.close()

    return jsonify({"success": True, "job_id": job_id, "message": "Cloud monitoring started"})


@app.route("/api/monitoring/stop", methods=["POST"])
def monitoring_stop():
    data = request.get_json() or {}
    hw = data.get("hardware_id", "")
    if not hw:
        return jsonify({"error": "Missing hardware_id"}), 400
    conn = get_db()
    conn.execute("UPDATE monitoring_jobs SET is_active=0, status='stopped' WHERE hardware_id=?", (hw,))
    conn.commit()
    # Get job id for logging
    row = conn.execute("SELECT id FROM monitoring_jobs WHERE hardware_id=?", (hw,)).fetchone()
    conn.close()
    if row:
        _add_log(row["id"], "Monitoring stopped by user")
    return jsonify({"success": True})


@app.route("/api/monitoring/status", methods=["POST"])
def monitoring_status():
    """Get monitoring status for a device."""
    data = request.get_json() or {}
    hw = data.get("hardware_id", "")
    if not hw:
        return jsonify({"error": "Missing hardware_id"}), 400
    conn = get_db()
    job = conn.execute("SELECT * FROM monitoring_jobs WHERE hardware_id=? ORDER BY id DESC LIMIT 1", (hw,)).fetchone()
    if not job:
        conn.close()
        return jsonify({"active": False, "message": "No monitoring job found"})
    # Get recent logs
    logs = conn.execute(
        "SELECT timestamp, message, level FROM monitoring_logs WHERE job_id=? ORDER BY id DESC LIMIT 20",
        (job["id"],)).fetchall()
    conn.close()
    return jsonify({
        "active": bool(job["is_active"]),
        "status": job["status"],
        "last_check_at": job["last_check_at"],
        "last_status": job["last_status"],
        "total_checks": job["total_checks"],
        "slots_found_total": job["slots_found_total"],
        "check_interval": job["check_interval"],
        "error_count": job["error_count"],
        "logs": [{"timestamp": l["timestamp"], "message": l["message"], "level": l["level"]} for l in reversed(list(logs))],
    })


@app.route("/api/monitoring/logs", methods=["POST"])
def monitoring_logs():
    data = request.get_json() or {}
    hw = data.get("hardware_id", "")
    limit = data.get("limit", 50)
    if not hw:
        return jsonify({"error": "Missing hardware_id"}), 400
    conn = get_db()
    job = conn.execute("SELECT id FROM monitoring_jobs WHERE hardware_id=?", (hw,)).fetchone()
    if not job:
        conn.close()
        return jsonify({"logs": []})
    logs = conn.execute(
        "SELECT timestamp, message, level FROM monitoring_logs WHERE job_id=? ORDER BY id DESC LIMIT ?",
        (job["id"], limit)).fetchall()
    conn.close()
    return jsonify({
        "logs": [{"timestamp": l["timestamp"], "message": l["message"], "level": l["level"]}
                 for l in reversed(list(logs))]
    })


@app.route("/api/monitoring/jobs", methods=["GET"])
@require_admin
def list_monitoring_jobs():
    """Admin: list all monitoring jobs."""
    conn = get_db()
    rows = conn.execute("SELECT * FROM monitoring_jobs ORDER BY created_at DESC").fetchall()
    conn.close()
    # Don't expose encrypted passwords
    result = []
    for r in rows:
        d = dict(r)
        d.pop("tls_password_enc", None)
        result.append(d)
    return jsonify(result)


# Support endpoint (same as server/app.py)
@app.route("/api/support/submit", methods=["POST"])
def submit_support():
    try:
        data = request.get_json() or {}
        subject = data.get("subject", "").strip()
        message = data.get("message", "").strip()
        reply_email = data.get("email", "").strip()
        if not subject or not message:
            return jsonify({"error": "Subject and message required"}), 400
        body = f"From: {reply_email or 'N/A'}\nHW: {data.get('hardware_id','N/A')}\nPlan: {data.get('plan','N/A')}\n{'='*40}\n\n{message}"
        msg = MIMEMultipart()
        msg['From'] = SMTP_USER; msg['To'] = SMTP_USER
        msg['Subject'] = f"[Support] {subject}"
        if reply_email: msg['Reply-To'] = reply_email
        msg.attach(MIMEText(body, 'plain'))
        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT, timeout=30) as s:
            s.starttls(); s.login(SMTP_USER, SMTP_PASS); s.send_message(msg)
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ══════════════════════════════════════════════════════════════════════
#  MONITORING WORKER  (background thread — runs Selenium checks)
# ══════════════════════════════════════════════════════════════════════

class MonitoringWorker:
    """
    Background worker that cycles through active monitoring jobs and
    runs TLS appointment checks using the existing checker_service.
    """

    def __init__(self, max_browsers: int = 2):
        self.max_browsers = max_browsers
        self._running = False
        self._thread = None
        self._semaphore = threading.Semaphore(max_browsers)
        self._active_checks = 0
        self._lock = threading.Lock()

    def start(self):
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._main_loop, daemon=True, name="MonitorWorker")
        self._thread.start()
        print(f"[Worker] Started (max {self.max_browsers} concurrent browsers)")

    def stop(self):
        self._running = False
        print("[Worker] Stopping...")

    def _main_loop(self):
        """Main loop: find due jobs → run checks → sleep."""
        # Wait for server to initialize
        time.sleep(3)

        while self._running:
            try:
                due_jobs = self._get_due_jobs()
                if due_jobs:
                    print(f"[Worker] {len(due_jobs)} job(s) due for check")

                threads = []
                for job in due_jobs:
                    if not self._running:
                        break
                    # Run each check in a thread (limited by semaphore)
                    t = threading.Thread(target=self._run_job, args=(dict(job),), daemon=True)
                    t.start()
                    threads.append(t)

                # Wait for all current checks to finish
                for t in threads:
                    t.join(timeout=300)  # 5 min max per check

            except Exception as e:
                print(f"[Worker] Loop error: {e}")
                traceback.print_exc()

            # Sleep 30 seconds between cycles
            for _ in range(60):
                if not self._running:
                    return
                time.sleep(0.5)

    def _get_due_jobs(self) -> list:
        """Get monitoring jobs that are due for a check."""
        conn = get_db()
        jobs = conn.execute("""
            SELECT * FROM monitoring_jobs
            WHERE is_active = 1 AND status != 'checking'
            ORDER BY last_check_at ASC NULLS FIRST
        """).fetchall()
        conn.close()

        now = datetime.now(timezone.utc)
        due = []
        for job in jobs:
            last = job["last_check_at"]
            interval = job["check_interval"] or 60
            if last:
                try:
                    last_dt = datetime.fromisoformat(last)
                    if last_dt.tzinfo is None:
                        last_dt = last_dt.replace(tzinfo=timezone.utc)
                    if (now - last_dt).total_seconds() < interval * 60:
                        continue  # Not due yet
                except Exception:
                    pass
            due.append(job)
        return due

    def _run_job(self, job: dict):
        """Run a single monitoring check for a job."""
        job_id = job["id"]
        self._semaphore.acquire()
        with self._lock:
            self._active_checks += 1

        try:
            _update_job(job_id, status="checking")
            _add_log(job_id, f"Starting check for {job['tls_email']}...")

            # Decrypt TLS password
            try:
                tls_password = _fernet.decrypt(job["tls_password_enc"].encode()).decode()
            except Exception as e:
                _add_log(job_id, f"Failed to decrypt credentials: {e}", "error")
                _update_job(job_id, status="error", error_count=job["error_count"] + 1)
                return

            # Import the checker service (lazy import to avoid circular deps)
            from checker_service import TLSCheckerService
            from database import SessionLocal, UserSettings, CheckHistory
            from database import init_db as init_app_db
            from auth_service import auth_service
            from config import Config

            # Ensure the app DB tables exist
            init_app_db()

            # Create/update a UserSettings entry for this monitoring job
            # Use user_id = 9000 + job_id to avoid conflicts with local app users
            user_id = 9000 + job_id
            db = SessionLocal()
            try:
                settings = db.query(UserSettings).filter(UserSettings.user_id == user_id).first()
                if not settings:
                    settings = UserSettings(
                        user_id=user_id,
                        tls_email=job["tls_email"],
                        tls_password=auth_service.encrypt_password(tls_password),
                        service_type=job["service_type"] or "legalization",
                        branch=job["branch"] or "Sheikh Zayed",
                        branch_url=job["branch_url"] or "",
                        notification_email=job["notification_email"],
                        check_interval=job["check_interval"] or 60,
                        enable_email_notifications=True,
                        enable_windows_notifications=False,
                        headless_mode=True,
                        first_check_done=True,
                        is_monitoring=True,
                    )
                    db.add(settings)
                else:
                    settings.tls_email = job["tls_email"]
                    settings.tls_password = auth_service.encrypt_password(tls_password)
                    settings.service_type = job["service_type"] or "legalization"
                    settings.branch = job["branch"] or "Sheikh Zayed"
                    settings.branch_url = job["branch_url"] or ""
                    settings.notification_email = job["notification_email"]
                    settings.check_interval = job["check_interval"] or 60
                    settings.headless_mode = True
                    settings.first_check_done = True
                    settings.is_monitoring = True
                db.commit()
            except Exception as e:
                _add_log(job_id, f"DB setup error: {e}", "error")
                db.close()
                _update_job(job_id, status="error", error_count=job["error_count"] + 1)
                return
            finally:
                db.close()

            # Create a status callback that logs to our monitoring_logs table
            def on_status(msg: str):
                _add_log(job_id, msg)

            # Force headless/background mode
            Config.BROWSER_HEADLESS = True

            # Create checker and run a single check
            checker = TLSCheckerService(
                user_id=user_id,
                on_status_update=on_status,
            )
            checker.is_running = True  # Pretend monitoring is active

            try:
                success = checker.run_check(headless_override=True, is_retry=False)
            except Exception as e:
                _add_log(job_id, f"Check error: {e}", "error")
                success = False
            finally:
                checker.is_running = False
                checker._cleanup_driver()

            # Check if slots were found (read from CheckHistory)
            slots_found = False
            db = SessionLocal()
            try:
                last_history = db.query(CheckHistory).filter(
                    CheckHistory.user_id == user_id
                ).order_by(CheckHistory.id.desc()).first()
                if last_history and last_history.slots_available:
                    slots_found = True
                    # Also send notification from server directly
                    _send_slots_email(job["notification_email"], job["branch"])
            except Exception:
                pass
            finally:
                db.close()

            # Update job status
            new_total = job["total_checks"] + 1
            new_slots = job["slots_found_total"] + (1 if slots_found else 0)
            status_msg = "Appointments found!" if slots_found else "No appointments"

            if success:
                _update_job(job_id,
                            status="idle",
                            last_check_at=_now_iso(),
                            last_status=status_msg,
                            total_checks=new_total,
                            slots_found_total=new_slots,
                            error_count=0)
                _add_log(job_id, f"Check complete: {status_msg}")
            else:
                _update_job(job_id,
                            status="idle",
                            last_check_at=_now_iso(),
                            last_status="Check failed - will retry",
                            total_checks=new_total,
                            error_count=job["error_count"] + 1)
                _add_log(job_id, "Check failed — will retry next cycle", "warning")

        except Exception as e:
            _add_log(job_id, f"Unexpected error: {e}", "error")
            traceback.print_exc()
            _update_job(job_id, status="error", error_count=job["error_count"] + 1)
        finally:
            with self._lock:
                self._active_checks -= 1
            self._semaphore.release()


# ══════════════════════════════════════════════════════════════════════
#  ADMIN DASHBOARD  (simple HTML)
# ══════════════════════════════════════════════════════════════════════

@app.route("/", methods=["GET"])
@app.route("/dashboard", methods=["GET"])
def dashboard():
    conn = get_db()
    jobs = conn.execute("SELECT * FROM monitoring_jobs ORDER BY is_active DESC, created_at DESC").fetchall()
    licenses = conn.execute("SELECT COUNT(*) as cnt, SUM(is_active) as active FROM licenses").fetchone()
    conn.close()

    rows_html = ""
    for j in jobs:
        status_color = {
            "idle": "#00FF88", "checking": "#FFD700", "pending": "#00D9FF",
            "error": "#FF6B6B", "stopped": "#888", "revoked": "#FF0000"
        }.get(j["status"], "#888")
        rows_html += f"""
        <tr>
            <td>{j['id']}</td>
            <td>{j['tls_email']}</td>
            <td>{j['branch'] or '-'}</td>
            <td>{j['notification_email']}</td>
            <td style="color:{status_color};font-weight:bold;">{j['status']}</td>
            <td>{j['total_checks']}</td>
            <td>{j['slots_found_total']}</td>
            <td>{(j['last_check_at'] or '-')[:19]}</td>
            <td>{j['check_interval']}m</td>
            <td>{'✅' if j['is_active'] else '❌'}</td>
        </tr>"""

    html = f"""<!DOCTYPE html>
<html><head><title>TLS Monitoring Server</title>
<meta http-equiv="refresh" content="30">
<style>
  body {{ background:#0A0E27; color:#E0E0E0; font-family:Arial; padding:20px; }}
  h1 {{ color:#00D9FF; }}
  table {{ border-collapse:collapse; width:100%; margin-top:20px; }}
  th, td {{ border:1px solid #333; padding:8px 12px; text-align:left; }}
  th {{ background:#1A1F3A; color:#00D9FF; }}
  tr:hover {{ background:#1A1F3A; }}
  .stat {{ display:inline-block; background:#1A1F3A; padding:15px 25px; border-radius:12px;
           margin:5px; border:1px solid #00D9FF33; }}
  .stat h3 {{ color:#00D9FF; margin:0 0 5px 0; font-size:14px; }}
  .stat .value {{ font-size:28px; font-weight:bold; }}
</style></head><body>
  <h1>🖥️ TLS Monitoring Server Dashboard</h1>
  <div>
    <div class="stat"><h3>Active Jobs</h3><div class="value">{sum(1 for j in jobs if j['is_active'])}</div></div>
    <div class="stat"><h3>Total Checks</h3><div class="value">{sum(j['total_checks'] for j in jobs)}</div></div>
    <div class="stat"><h3>Slots Found</h3><div class="value">{sum(j['slots_found_total'] for j in jobs)}</div></div>
    <div class="stat"><h3>Licenses</h3><div class="value">{licenses['cnt'] or 0} ({licenses['active'] or 0} active)</div></div>
  </div>
  <h2>Monitoring Jobs</h2>
  <table>
    <tr><th>ID</th><th>TLS Email</th><th>Branch</th><th>Notify</th><th>Status</th>
        <th>Checks</th><th>Found</th><th>Last Check</th><th>Interval</th><th>Active</th></tr>
    {rows_html or '<tr><td colspan="10" style="text-align:center;color:#888;">No monitoring jobs yet. Users can start monitoring from the app.</td></tr>'}
  </table>
  <p style="color:#666;margin-top:20px;">Auto-refreshes every 30 seconds.
     Admin API Key: <code>{ADMIN_API_KEY[:8]}...</code></p>
</body></html>"""
    return html


# ══════════════════════════════════════════════════════════════════════
#  MAIN
# ══════════════════════════════════════════════════════════════════════

worker = MonitoringWorker(max_browsers=MAX_BROWSERS)

def main():
    parser = argparse.ArgumentParser(description="TLS Monitoring & License Server")
    parser.add_argument("--port", type=int, default=int(os.environ.get("PORT", "5000")))
    parser.add_argument("--ngrok", action="store_true", help="Create public ngrok tunnel")
    parser.add_argument("--ngrok-token", type=str, default=os.environ.get("NGROK_TOKEN", ""),
                        help="ngrok auth token")
    args = parser.parse_args()

    _ensure_secure_config()
    init_db()

    print("=" * 60)
    print("  TLS Appointment Checker — Monitoring Server")
    print("=" * 60)
    print(f"  Port:           {args.port}")
    print(f"  Admin API Key:  {ADMIN_API_KEY}")
    print(f"  Max Browsers:   {MAX_BROWSERS}")
    print(f"  Database:       {DB_PATH}")
    print(f"  Dashboard:      http://localhost:{args.port}/dashboard")
    print()

    public_url = None
    if args.ngrok:
        try:
            from pyngrok import ngrok, conf
            if args.ngrok_token:
                conf.get_default().auth_token = args.ngrok_token
            tunnel = ngrok.connect(args.port, "http")
            public_url = tunnel.public_url
            print(f"  🌐 Public URL:  {public_url}")
            print(f"     Use this URL in your app's LICENSE_SERVER_URL setting")
            print(f"     and in license_manager.py LICENSE_SERVER_URL")
        except ImportError:
            print("  ⚠️  pyngrok not installed. Run: pip install pyngrok")
            print("     Falling back to local-only mode.")
        except Exception as e:
            print(f"  ⚠️  ngrok failed: {e}")

    print()
    print("  📋 Quick Start:")
    print("  1. Set LICENSE_SERVER_URL in your .env or config to this server's URL")
    print("  2. In license_manager.py, set LICENSE_SERVER_URL and ADMIN_API_KEY")
    print("  3. Users start monitoring from the app → server handles everything")
    print("=" * 60)
    print()

    # Start the monitoring worker
    worker.start()

    # Register clean shutdown
    def _shutdown(sig, frame):
        print("\n[Server] Shutting down...")
        worker.stop()
        sys.exit(0)

    signal.signal(signal.SIGINT, _shutdown)
    signal.signal(signal.SIGTERM, _shutdown)

    # Run Flask
    app.run(host="0.0.0.0", port=args.port, debug=False, use_reloader=False)


if __name__ == "__main__":
    main()
