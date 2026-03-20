"""
TLS Appointment Checker — Server Manager
=========================================
Admin GUI that embeds the monitoring & license server.

One-click to:
  - Start / stop the monitoring + license server
  - Generate, view, and revoke license keys
  - See active monitoring jobs in real time
  - View live server logs
  - Enable ngrok for remote / public access

Run:
    python license_manager.py
"""
import flet as ft
import sqlite3
import os
import sys
import json
import base64
import threading
import time
import socket
from datetime import datetime, timedelta, timezone

# Ensure sibling imports work
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from license_service import PLANS, get_hardware_id, parse_license_key
import hmac
import hashlib
import secrets

SECRET = "TLS-CHECKER-2026-HMAC-SECRET-KEY-DONT-SHARE"

def _sign(payload: str) -> str:
    """HMAC-SHA256 signature of payload."""
    return hmac.new(SECRET.encode(), payload.encode(), hashlib.sha256).hexdigest()[:16]

def generate_license_key(plan: str, hardware_id: str) -> str:
    """
    Generate a license key bound to a specific hardware ID.
    Format: PLAN-HWID8-RANDOM8-SIG16
    """
    hw_short = hardware_id[:8].upper()
    rand = secrets.token_hex(4).upper()
    payload = f"{plan}:{hw_short}:{rand}"
    sig = _sign(payload).upper()
    return f"{plan.upper()}-{hw_short}-{rand}-{sig}"

# ────────────────────────────────────────────────────────────────────
#  Embedded server state
# ────────────────────────────────────────────────────────────────────
_server_thread = None
_server_running = False
_server_port = 5000
_admin_api_key = ""
_ngrok_url = None

# ────────────────────────────────────────────────────────────────────
#  Local license DB  (same schema the old License Manager used)
# ────────────────────────────────────────────────────────────────────
def _get_db_path():
    if getattr(sys, 'frozen', False):
        app_data = os.path.join(os.environ.get('APPDATA', os.path.expanduser('~')),
                                'TLS License Manager')
        os.makedirs(app_data, exist_ok=True)
        return os.path.join(app_data, 'license_manager.db')
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), "license_manager.db")

DB_PATH = _get_db_path()


def _conn():
    return sqlite3.connect(DB_PATH)


def init_manager_db():
    conn = _conn()
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS licenses (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            license_key TEXT    UNIQUE NOT NULL,
            plan        TEXT    NOT NULL,
            device_id   TEXT    NOT NULL,
            customer_name  TEXT DEFAULT '',
            customer_email TEXT DEFAULT '',
            created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            expires_at  TIMESTAMP,
            is_active   INTEGER DEFAULT 1,
            notes       TEXT DEFAULT '',
            revoked_at  TIMESTAMP DEFAULT NULL,
            revoke_reason TEXT DEFAULT ''
        )
    """)
    for col, coldef in [("revoked_at", "TIMESTAMP DEFAULT NULL"),
                        ("revoke_reason", "TEXT DEFAULT ''")]:
        try:
            c.execute(f"ALTER TABLE licenses ADD COLUMN {col} {coldef}")
        except Exception:
            pass
    conn.commit()
    conn.close()


def db_insert_license(key, plan, device_id, customer_name, customer_email, expires_at, notes=""):
    conn = _conn()
    conn.execute(
        "INSERT INTO licenses (license_key,plan,device_id,customer_name,customer_email,expires_at,notes) VALUES (?,?,?,?,?,?,?)",
        (key, plan, device_id, customer_name, customer_email, expires_at, notes),
    )
    conn.commit()
    conn.close()


def db_get_all_licenses(search=""):
    conn = _conn()
    conn.row_factory = sqlite3.Row
    if search:
        like = f"%{search}%"
        rows = conn.execute(
            "SELECT * FROM licenses WHERE license_key LIKE ? OR device_id LIKE ? OR customer_name LIKE ? OR customer_email LIKE ? ORDER BY created_at DESC",
            (like, like, like, like),
        ).fetchall()
    else:
        rows = conn.execute("SELECT * FROM licenses ORDER BY created_at DESC").fetchall()
    conn.close()
    return [dict(r) for r in rows]


def db_get_license(lid):
    conn = _conn()
    conn.row_factory = sqlite3.Row
    row = conn.execute("SELECT * FROM licenses WHERE id=?", (lid,)).fetchone()
    conn.close()
    return dict(row) if row else None


def db_toggle_active(lid, active: bool):
    conn = _conn()
    conn.execute("UPDATE licenses SET is_active=? WHERE id=?", (1 if active else 0, lid))
    conn.commit()
    conn.close()


def db_update_notes(lid, notes: str):
    conn = _conn()
    conn.execute("UPDATE licenses SET notes=? WHERE id=?", (notes, lid))
    conn.commit()
    conn.close()


def db_update_customer(lid, name, email):
    conn = _conn()
    conn.execute("UPDATE licenses SET customer_name=?, customer_email=? WHERE id=?", (name, email, lid))
    conn.commit()
    conn.close()


def db_revoke_license(lid, reason=""):
    conn = _conn()
    row = conn.execute("SELECT license_key, device_id FROM licenses WHERE id=?", (lid,)).fetchone()
    if not row:
        conn.close()
        return False, "License not found"
    license_key, device_id = row
    conn.execute(
        "UPDATE licenses SET is_active=0, revoked_at=?, revoke_reason=? WHERE id=?",
        (datetime.now(timezone.utc).isoformat(), reason, lid),
    )
    conn.commit()
    conn.close()
    return _sync_revoke_to_server(license_key, device_id, reason)


def _sync_revoke_to_server(license_key, device_id, reason=""):
    """Sync license revocation to the embedded monitoring server."""
    global _server_running, _server_port, _admin_api_key
    if not _server_running:
        return True, "Revoked locally (server not running)"
    try:
        import urllib.request
        import urllib.error
        payload = json.dumps({"license_key": license_key, "hardware_id": device_id}).encode()
        req = urllib.request.Request(
            f"http://localhost:{_server_port}/api/license/revoke",
            data=payload,
            headers={"Content-Type": "application/json",
                     "Authorization": f"Bearer {_admin_api_key}"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            result = json.loads(resp.read())
            if result.get("success"):
                return True, f"Revoked on server ({result.get('revoked', 0)} records)"
            return False, result.get("error", "Server revocation failed")
    except Exception as e:
        return False, f"Server sync failed: {str(e)[:100]}"


def db_delete_license(lid):
    conn = _conn()
    conn.execute("DELETE FROM licenses WHERE id=?", (lid,))
    conn.commit()
    conn.close()


def db_backup(filepath):
    licenses = db_get_all_licenses()
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump({"exported_at": datetime.now(timezone.utc).isoformat(), "licenses": licenses}, f, indent=2, default=str)
    return len(licenses)


def db_restore(filepath):
    with open(filepath, "r", encoding="utf-8") as f:
        data = json.load(f)
    licenses = data.get("licenses", [])
    conn = _conn()
    imported = skipped = 0
    for lic in licenses:
        try:
            conn.execute(
                "INSERT INTO licenses (license_key,plan,device_id,customer_name,customer_email,created_at,expires_at,is_active,notes,revoked_at,revoke_reason) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                (lic["license_key"], lic["plan"], lic["device_id"], lic.get("customer_name", ""),
                 lic.get("customer_email", ""), lic.get("created_at"), lic.get("expires_at"),
                 lic.get("is_active", 1), lic.get("notes", ""), lic.get("revoked_at"), lic.get("revoke_reason", "")),
            )
            imported += 1
        except sqlite3.IntegrityError:
            skipped += 1
    conn.commit()
    conn.close()
    return imported, skipped


def db_stats():
    conn = _conn()
    total = conn.execute("SELECT COUNT(*) FROM licenses").fetchone()[0]
    active = conn.execute("SELECT COUNT(*) FROM licenses WHERE is_active=1").fetchone()[0]
    expired = conn.execute(
        "SELECT COUNT(*) FROM licenses WHERE is_active=1 AND expires_at < ?",
        (datetime.now(timezone.utc).isoformat(),),
    ).fetchone()[0]
    revenue = 0.0
    for plan_key, info in PLANS.items():
        cnt = conn.execute(
            "SELECT COUNT(*) FROM licenses WHERE plan=? AND is_active=1",
            (plan_key,),
        ).fetchone()[0]
        revenue += cnt * info["price"]
    conn.close()
    return {"total": total, "active": active, "expired": expired, "revenue": revenue}


# ────────────────────────────────────────────────────────────────────
#  Monitoring-server DB helpers (reads monitoring_server.db)
# ────────────────────────────────────────────────────────────────────
def _monitor_db_path():
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), "monitoring_server.db")


def _monitor_conn():
    path = _monitor_db_path()
    if not os.path.exists(path):
        return None
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    return conn


def get_monitoring_jobs():
    conn = _monitor_conn()
    if not conn:
        return []
    try:
        rows = conn.execute("SELECT * FROM monitoring_jobs ORDER BY is_active DESC, created_at DESC").fetchall()
        return [dict(r) for r in rows]
    except Exception:
        return []
    finally:
        conn.close()


def get_monitoring_stats():
    conn = _monitor_conn()
    if not conn:
        return {"active_jobs": 0, "total_checks": 0, "slots_found": 0}
    try:
        jobs = conn.execute("SELECT * FROM monitoring_jobs").fetchall()
        return {
            "active_jobs": sum(1 for j in jobs if j["is_active"]),
            "total_checks": sum(j["total_checks"] for j in jobs),
            "slots_found": sum(j["slots_found_total"] for j in jobs),
        }
    except Exception:
        return {"active_jobs": 0, "total_checks": 0, "slots_found": 0}
    finally:
        conn.close()


def get_monitoring_logs(job_id=None, limit=100):
    conn = _monitor_conn()
    if not conn:
        return []
    try:
        if job_id:
            rows = conn.execute(
                "SELECT ml.*, mj.tls_email FROM monitoring_logs ml LEFT JOIN monitoring_jobs mj ON ml.job_id=mj.id WHERE ml.job_id=? ORDER BY ml.id DESC LIMIT ?",
                (job_id, limit)).fetchall()
        else:
            rows = conn.execute(
                "SELECT ml.*, mj.tls_email FROM monitoring_logs ml LEFT JOIN monitoring_jobs mj ON ml.job_id=mj.id ORDER BY ml.id DESC LIMIT ?",
                (limit,)).fetchall()
        return [dict(r) for r in rows]
    except Exception:
        return []
    finally:
        conn.close()


def stop_monitoring_job(job_id):
    conn = _monitor_conn()
    if not conn:
        return False
    try:
        conn.execute("UPDATE monitoring_jobs SET is_active=0, status='stopped' WHERE id=?", (job_id,))
        conn.commit()
        return True
    except Exception:
        return False
    finally:
        conn.close()


# ────────────────────────────────────────────────────────────────────
#  Server start / stop / ngrok helpers
# ────────────────────────────────────────────────────────────────────
def _sync_license_to_server(key, plan, device_id, email="", name=""):
    """After generating a license locally, also push it to the monitoring server."""
    global _server_running, _server_port, _admin_api_key
    if not _server_running:
        return
    try:
        import urllib.request
        payload = json.dumps({
            "plan": plan, "hardware_id": device_id,
            "email": email, "name": name, "send_email": bool(email),
        }).encode()
        req = urllib.request.Request(
            f"http://localhost:{_server_port}/api/license/generate",
            data=payload,
            headers={"Content-Type": "application/json",
                     "Authorization": f"Bearer {_admin_api_key}"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            json.loads(resp.read())
    except Exception:
        pass


def start_server(port=5000, log_callback=None):
    """Start the monitoring server in a background thread."""
    global _server_thread, _server_running, _server_port, _admin_api_key

    if _server_running:
        if log_callback:
            log_callback("Server is already running")
        return True

    _server_port = port

    def _run():
        global _server_running, _admin_api_key
        try:
            import monitoring_server as ms
            ms.init_db()
            _admin_api_key = ms.ADMIN_API_KEY
            if log_callback:
                log_callback(f"Server starting on port {port}...")
                log_callback(f"Admin API Key: {_admin_api_key}")
            ms.worker.start()
            _server_running = True
            ms.app.run(host="0.0.0.0", port=port, debug=False, use_reloader=False)
        except Exception as e:
            _server_running = False
            if log_callback:
                log_callback(f"Server error: {e}")

    _server_thread = threading.Thread(target=_run, daemon=True, name="MonitoringServer")
    _server_thread.start()

    # Wait for server to start and test it's responding
    for attempt in range(50):
        time.sleep(0.2)
        if _server_running:
            # Test the server is actually responding
            try:
                import urllib.request
                urllib.request.urlopen(f"http://localhost:{port}/health", timeout=2).read()
                if log_callback:
                    log_callback(f"✓ Server ready on port {port}")
                    log_callback(f"Dashboard: http://localhost:{port}/dashboard")
                return True
            except Exception:
                continue
    if log_callback:
        log_callback("Server failed to become ready in time")
    return False


def stop_server(log_callback=None):
    """Mark server as stopped (daemon thread dies with app)."""
    global _server_running
    if not _server_running:
        if log_callback:
            log_callback("Server is not running")
        return
    _server_running = False
    if log_callback:
        log_callback("Server stopped (will fully close when app exits)")


def start_ngrok(port, token="", log_callback=None):
    """Start an ngrok tunnel for public access."""
    global _ngrok_url
    try:
        from pyngrok import ngrok, conf
        if token:
            conf.get_default().auth_token = token
        tunnel = ngrok.connect(port, "http")
        _ngrok_url = tunnel.public_url
        if log_callback:
            log_callback(f"ngrok tunnel active: {_ngrok_url}")
        return _ngrok_url
    except ImportError:
        if log_callback:
            log_callback("pyngrok not installed. Run: pip install pyngrok")
        return None
    except Exception as e:
        if log_callback:
            log_callback(f"ngrok error: {e}")
        return None


# ────────────────────────────────────────────────────────────────────
#  Logo helper
# ────────────────────────────────────────────────────────────────────
def _load_logo():
    try:
        app_dir = os.path.dirname(os.path.abspath(__file__))
        path = os.path.join(app_dir, "Logos", "LOGO_H_W.png")
        with open(path, "rb") as f:
            b64 = base64.b64encode(f.read()).decode()
        return f"data:image/png;base64,{b64}"
    except Exception:
        return None


# ════════════════════════════════════════════════════════════════════
#  SERVER MANAGER APP  (Flet GUI)
# ════════════════════════════════════════════════════════════════════
class ServerManagerApp:
    ACCENT = "#00D9FF"
    BG = "#0A0E27"
    CARD_BG = "#1A1F3A"

    def __init__(self, page: ft.Page):
        self.page = page
        self.page.title = "TLS Server Manager"
        self.page.bgcolor = self.BG
        self.page.theme_mode = ft.ThemeMode.DARK
        self.page.window.width = 1200
        self.page.window.height = 850
        self.page.window.min_width = 1000
        self.page.window.min_height = 700
        self.page.padding = 0
        self.page.fonts = {
            "Montserrat": "https://fonts.googleapis.com/css2?family=Montserrat:wght@300;400;500;600;700;800&display=swap"
        }
        self.page.theme = ft.Theme(color_scheme_seed=self.ACCENT, font_family="Montserrat")
        self._logo_src = _load_logo()
        self._server_logs = []
        self._refresh_active = True

        # Centre window
        try:
            import tkinter as tk
            root = tk.Tk(); root.withdraw()
            sw, sh = root.winfo_screenwidth(), root.winfo_screenheight()
            root.destroy()
            self.page.window.left = (sw - 1200) // 2
            self.page.window.top = (sh - 850) // 2
        except Exception:
            pass

        init_manager_db()
        self._nav_index = 0
        self._build_shell()
        self._start_auto_refresh()

    # ── cleanup ─────────────────────────────────────────────────────
    def _on_close(self, e):
        if e.data == "close":
            self._refresh_active = False

    # ── auto-refresh thread ─────────────────────────────────────────
    def _start_auto_refresh(self):
        self.page.window.on_event = self._on_close

        def _tick():
            while self._refresh_active:
                try:
                    if self._nav_index in (0, 3, 4):
                        self._route(self._nav_index)
                except Exception:
                    pass
                for _ in range(30):
                    if not self._refresh_active:
                        return
                    time.sleep(0.5)
        threading.Thread(target=_tick, daemon=True).start()

    # ── shared helpers ──────────────────────────────────────────────
    def _glass(self, content, width=None, height=None, padding=20):
        return ft.Container(
            content=content, width=width, height=height, padding=padding,
            border_radius=18,
            gradient=ft.LinearGradient(
                begin=ft.alignment.Alignment(-1, -1),
                end=ft.alignment.Alignment(1, 1),
                colors=[self.CARD_BG, "#0F1525"],
            ),
            border=ft.Border.all(1, ft.Colors.with_opacity(0.3, self.ACCENT)),
            shadow=ft.BoxShadow(
                spread_radius=0, blur_radius=15,
                color=ft.Colors.with_opacity(0.15, self.ACCENT),
                offset=ft.Offset(0, 3),
            ),
        )

    def _stat_card(self, icon, value, label, color=None):
        color = color or self.ACCENT
        return self._glass(
            ft.Column(
                [
                    ft.Icon(icon, size=28, color=color),
                    ft.Container(height=4),
                    ft.Text(str(value), size=28, weight=ft.FontWeight.BOLD, color=color),
                    ft.Text(label, size=11, color=ft.Colors.GREY_400),
                ],
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                spacing=2,
            ),
            width=180, padding=16,
        )

    def _server_log(self, msg):
        ts = datetime.now().strftime("%H:%M:%S")
        self._server_logs.append((ts, msg))
        if len(self._server_logs) > 500:
            self._server_logs = self._server_logs[-300:]

    # ── shell ───────────────────────────────────────────────────────
    def _build_shell(self):
        self.page.controls.clear()
        self._content_area = ft.Column(expand=True, scroll=ft.ScrollMode.AUTO, spacing=0)

        def on_nav(e):
            idx = e.control.selected_index
            self._nav_index = idx
            self._route(idx)

        nav = ft.NavigationRail(
            selected_index=self._nav_index,
            label_type=ft.NavigationRailLabelType.ALL,
            min_width=80,
            min_extended_width=200,
            bgcolor="#0D1130",
            indicator_color=ft.Colors.with_opacity(0.15, self.ACCENT),
            on_change=on_nav,
            destinations=[
                ft.NavigationRailDestination(icon=ft.Icons.DNS, label="Server"),
                ft.NavigationRailDestination(icon=ft.Icons.ADD_CIRCLE, label="Generate"),
                ft.NavigationRailDestination(icon=ft.Icons.LIST_ALT, label="Licenses"),
                ft.NavigationRailDestination(icon=ft.Icons.MONITOR_HEART, label="Monitoring"),
                ft.NavigationRailDestination(icon=ft.Icons.TERMINAL, label="Logs"),
            ],
        )

        shell = ft.Row(
            [
                nav,
                ft.VerticalDivider(width=1, color=ft.Colors.with_opacity(0.15, self.ACCENT)),
                ft.Container(content=self._content_area, expand=True, padding=25),
            ],
            expand=True, spacing=0,
        )
        self.page.add(shell)
        self._route(self._nav_index)

    def _route(self, idx):
        self._content_area.controls.clear()
        if idx == 0:
            self._page_server()
        elif idx == 1:
            self._page_generate()
        elif idx == 2:
            self._page_licenses()
        elif idx == 3:
            self._page_monitoring()
        elif idx == 4:
            self._page_logs()
        try:
            self.page.update()
        except Exception:
            pass

    # ══════════════════════════════════════════════════════════════════
    #  PAGE: Server Control
    # ══════════════════════════════════════════════════════════════════
    def _page_server(self):
        global _server_running, _server_port, _admin_api_key, _ngrok_url

        lic_stats = db_stats()
        mon_stats = get_monitoring_stats()

        port_field = ft.TextField(
            label="Port", value=str(_server_port), width=120, border_radius=12,
            text_align=ft.TextAlign.CENTER,
        )

        status_color = ft.Colors.GREEN_400 if _server_running else ft.Colors.RED_400
        status_text = "RUNNING" if _server_running else "STOPPED"
        status_icon = ft.Icons.CHECK_CIRCLE if _server_running else ft.Icons.CANCEL

        server_status = ft.Row([
            ft.Icon(status_icon, color=status_color, size=32),
            ft.Text(status_text, size=22, weight=ft.FontWeight.BOLD, color=status_color),
        ], spacing=10)

        api_key_text = ft.Text(
            _admin_api_key if _admin_api_key else "Will be generated on start",
            size=13, color=ft.Colors.GREY_300, selectable=True, font_family="Courier New",
        )

        ngrok_status = ft.Text(
            _ngrok_url or "Not active",
            size=13, color=ft.Colors.GREEN_400 if _ngrok_url else ft.Colors.GREY_500,
            selectable=True,
        )

        feedback_text = ft.Text("", size=13)

        def do_start(e):
            try:
                p = int(port_field.value)
            except ValueError:
                feedback_text.value = "Invalid port number"
                feedback_text.color = ft.Colors.RED_400
                self.page.update()
                return

            feedback_text.value = "Starting server..."
            feedback_text.color = ft.Colors.GREY_400
            self.page.update()

            ok = start_server(port=p, log_callback=self._server_log)
            if ok:
                self._server_log(f"Server started on port {p}")
                feedback_text.value = f"Server running on port {p}"
                feedback_text.color = ft.Colors.GREEN_400
            else:
                feedback_text.value = "Failed to start server"
                feedback_text.color = ft.Colors.RED_400
            self._route(0)

        def do_stop(e):
            stop_server(log_callback=self._server_log)
            self._server_log("Server stop requested")
            self._route(0)

        def do_ngrok(e):
            token = ngrok_token_field.value.strip() if ngrok_token_field.value else ""
            try:
                p = int(port_field.value)
            except ValueError:
                p = _server_port

            feedback_text.value = "Starting ngrok tunnel..."
            feedback_text.color = ft.Colors.GREY_400
            self.page.update()

            url = start_ngrok(p, token=token, log_callback=self._server_log)
            if url:
                feedback_text.value = f"ngrok active: {url}"
                feedback_text.color = ft.Colors.GREEN_400
            else:
                feedback_text.value = "Failed to start ngrok (install pyngrok?)"
                feedback_text.color = ft.Colors.RED_400
            self._route(0)

        def copy_api_key(e):
            if _admin_api_key:
                try:
                    import pyperclip
                    pyperclip.copy(_admin_api_key)
                    feedback_text.value = "API key copied!"
                    feedback_text.color = ft.Colors.GREEN_400
                    self.page.update()
                except Exception:
                    pass

        def copy_ngrok_url(e):
            if _ngrok_url:
                try:
                    import pyperclip
                    pyperclip.copy(_ngrok_url)
                    feedback_text.value = "ngrok URL copied!"
                    feedback_text.color = ft.Colors.GREEN_400
                    self.page.update()
                except Exception:
                    pass

        ngrok_token_field = ft.TextField(
            label="ngrok Token (optional)", width=400, border_radius=12,
            password=True, can_reveal_password=True,
            hint_text="From dashboard.ngrok.com",
        )

        start_btn = ft.FilledButton(
            "Start Server", icon=ft.Icons.PLAY_ARROW,
            on_click=do_start, width=200, height=48,
            disabled=_server_running,
            style=ft.ButtonStyle(bgcolor=ft.Colors.GREEN_700, color=ft.Colors.WHITE),
        )
        stop_btn = ft.OutlinedButton(
            "Stop Server", icon=ft.Icons.STOP,
            on_click=do_stop, width=200, height=48,
            disabled=not _server_running,
            style=ft.ButtonStyle(color=ft.Colors.RED_400,
                                 side=ft.BorderSide(1, ft.Colors.RED_400)),
        )

        self._content_area.controls.extend([
            ft.Container(height=10),
            ft.Row([
                ft.Image(src=self._logo_src or "", width=180, height=45) if self._logo_src else ft.Container(),
                ft.Text("Server Manager", size=22, weight=ft.FontWeight.BOLD),
            ], spacing=15, vertical_alignment=ft.CrossAxisAlignment.CENTER),
            ft.Container(height=20),

            # Server status card
            self._glass(ft.Column([
                ft.Text("Server Status", size=16, weight=ft.FontWeight.W_600, color=self.ACCENT),
                ft.Divider(height=1, color=ft.Colors.with_opacity(0.15, self.ACCENT)),
                ft.Container(height=8),
                server_status,
                ft.Container(height=12),
                ft.Row([
                    ft.Text("Port:", size=13, color=ft.Colors.GREY_400, width=100),
                    port_field,
                    ft.Container(width=20),
                    start_btn, stop_btn,
                ], spacing=10, vertical_alignment=ft.CrossAxisAlignment.CENTER),
                ft.Container(height=12),
                ft.Row([
                    ft.Text("Admin API Key:", size=13, color=ft.Colors.GREY_400, width=100),
                    api_key_text,
                    ft.IconButton(icon=ft.Icons.COPY, icon_size=16, on_click=copy_api_key,
                                  icon_color=self.ACCENT, tooltip="Copy"),
                ], spacing=8),
                ft.Container(height=8),
                ft.Row([
                    ft.Text("Public URL:", size=13, color=ft.Colors.GREY_400, width=100),
                    ngrok_status,
                    ft.IconButton(icon=ft.Icons.COPY, icon_size=16, on_click=copy_ngrok_url,
                                  icon_color=self.ACCENT, tooltip="Copy") if _ngrok_url else ft.Container(),
                ], spacing=8),
                ft.Container(height=10),
                ft.Row([
                    ngrok_token_field,
                    ft.FilledButton("Start ngrok", icon=ft.Icons.PUBLIC, on_click=do_ngrok,
                                    height=42, style=ft.ButtonStyle(bgcolor=self.ACCENT, color=self.BG)),
                ], spacing=10),
                ft.Container(height=8),
                feedback_text,
            ], spacing=6), padding=20),

            ft.Container(height=20),

            # Stats row
            ft.Row([
                self._stat_card(ft.Icons.CONFIRMATION_NUMBER, lic_stats["total"], "Total Licenses"),
                self._stat_card(ft.Icons.CHECK_CIRCLE, lic_stats["active"], "Active Licenses", ft.Colors.GREEN_400),
                self._stat_card(ft.Icons.MONITOR_HEART, mon_stats["active_jobs"], "Active Jobs", ft.Colors.AMBER_400),
                self._stat_card(ft.Icons.SEARCH, mon_stats["total_checks"], "Total Checks"),
                self._stat_card(ft.Icons.EVENT_AVAILABLE, mon_stats["slots_found"], "Slots Found", ft.Colors.GREEN_400),
            ], spacing=10, wrap=True),

            ft.Container(height=20),

            # Quick instructions
            self._glass(ft.Column([
                ft.Text("Quick Start Guide", size=16, weight=ft.FontWeight.W_600, color=self.ACCENT),
                ft.Divider(height=1, color=ft.Colors.with_opacity(0.15, self.ACCENT)),
                ft.Container(height=6),
                ft.Text("1. Click 'Start Server' to launch the monitoring & license server", size=13, color=ft.Colors.GREY_300),
                ft.Text("2. Generate license keys in the 'Generate' tab and share with users", size=13, color=ft.Colors.GREY_300),
                ft.Text("3. Users install the app, activate their license, and click Start", size=13, color=ft.Colors.GREY_300),
                ft.Text("4. The server checks appointments for all users automatically", size=13, color=ft.Colors.GREY_300),
                ft.Text("5. Users get email notifications when appointments are found", size=13, color=ft.Colors.GREY_300),
                ft.Container(height=6),
                ft.Text("For remote access: Enter your ngrok token and click 'Start ngrok'", size=12, color=ft.Colors.GREY_500),
                ft.Text("Then update LICENSE_SERVER_URL in config.py to the ngrok URL", size=12, color=ft.Colors.GREY_500),
            ], spacing=4), padding=18),
        ])

    # ══════════════════════════════════════════════════════════════════
    #  PAGE: Generate License
    # ══════════════════════════════════════════════════════════════════
    def _page_generate(self):
        plan_dd = ft.Dropdown(
            label="License Type", width=350, border_radius=12,
            options=[
                ft.dropdown.Option(k, f"{v['name']}  —  {v.get('price', 0):,} EGP")
                for k, v in PLANS.items() if k != "trial"
            ],
            value="lifetime",
        )
        device_field = ft.TextField(
            label="Customer Device ID (full 32-char hash)",
            width=500, border_radius=12, prefix_icon=ft.Icons.DEVICES,
            hint_text="e.g. 26d19c80d368f666a08ee4b9f1c67b6b",
        )
        name_field = ft.TextField(label="Customer Name (optional)", width=350, border_radius=12, prefix_icon=ft.Icons.PERSON)
        email_field = ft.TextField(label="Customer Email (optional)", width=350, border_radius=12, prefix_icon=ft.Icons.EMAIL)
        notes_field = ft.TextField(label="Notes (optional)", width=500, border_radius=12, multiline=True, min_lines=2, max_lines=4)

        result_key = ft.Text("", size=16, weight=ft.FontWeight.BOLD, color=self.ACCENT, selectable=True)
        status_msg = ft.Text("", size=14)

        def generate(e):
            plan = plan_dd.value
            device_id = (device_field.value or "").strip()
            if not plan or not device_id:
                status_msg.value = "Please select a plan and enter a device ID"
                status_msg.color = ft.Colors.RED_400
                self.page.update()
                return
            if len(device_id) < 8:
                status_msg.value = "Device ID must be at least 8 characters"
                status_msg.color = ft.Colors.RED_400
                self.page.update()
                return

            key = generate_license_key(plan, device_id)
            plan_info = PLANS[plan]
            expires_at = (datetime.now(timezone.utc) + timedelta(days=plan_info["duration_days"])).isoformat()
            customer = (name_field.value or "").strip()
            c_email = (email_field.value or "").strip()
            notes = (notes_field.value or "").strip()

            try:
                db_insert_license(key, plan, device_id, customer, c_email, expires_at, notes)
                _sync_license_to_server(key, plan, device_id, c_email, customer)
            except sqlite3.IntegrityError:
                status_msg.value = "License already exists for this configuration"
                status_msg.color = ft.Colors.AMBER_400
                self.page.update()
                return

            result_key.value = key
            status_msg.value = f"License generated!  Plan: {plan_info['name']},  Expires: {expires_at[:10]}"
            status_msg.color = ft.Colors.GREEN_400
            self.page.update()

        def copy_key(e):
            if result_key.value:
                try:
                    import pyperclip
                    pyperclip.copy(result_key.value)
                except Exception:
                    pass

        self._content_area.controls.extend([
            ft.Container(height=10),
            ft.Text("Generate License Key", size=22, weight=ft.FontWeight.BOLD),
            ft.Container(height=20),
            self._glass(
                ft.Column([
                    ft.Row([plan_dd, ft.Container(width=20), name_field], wrap=True, spacing=10),
                    ft.Container(height=10),
                    device_field,
                    ft.Container(height=10),
                    ft.Row([email_field], spacing=10),
                    ft.Container(height=10),
                    notes_field,
                    ft.Container(height=20),
                    ft.FilledButton(
                        "Generate Key", icon=ft.Icons.VPN_KEY, width=250, height=48,
                        on_click=generate,
                        style=ft.ButtonStyle(bgcolor=self.ACCENT, color=self.BG),
                    ),
                    ft.Container(height=15),
                    ft.Divider(height=1, color=ft.Colors.with_opacity(0.15, self.ACCENT)),
                    ft.Container(height=10),
                    ft.Text("Generated Key:", size=12, color=ft.Colors.GREY_400),
                    ft.Row([result_key,
                            ft.IconButton(icon=ft.Icons.COPY, on_click=copy_key, icon_color=self.ACCENT, tooltip="Copy")],
                           spacing=10),
                    ft.Container(height=5),
                    status_msg,
                ], spacing=4),
                width=700, padding=25,
            ),
        ])

    # ══════════════════════════════════════════════════════════════════
    #  PAGE: Licenses
    # ══════════════════════════════════════════════════════════════════
    def _page_licenses(self):
        search_field = ft.TextField(
            label="Search (key, device, name, email)",
            width=400, border_radius=12, prefix_icon=ft.Icons.SEARCH,
            on_submit=lambda e: refresh_table(),
        )
        table_container = ft.Column(scroll=ft.ScrollMode.AUTO)

        def refresh_table():
            table_container.controls.clear()
            licenses = db_get_all_licenses(search_field.value or "")
            if not licenses:
                table_container.controls.append(ft.Text("No licenses found.", color=ft.Colors.GREY_500))
                self.page.update()
                return

            rows = []
            for lic in licenses:
                exp = lic["expires_at"] or ""
                exp_short = exp[:10] if exp else "—"
                active_icon = ft.Icon(ft.Icons.CHECK_CIRCLE, size=16, color=ft.Colors.GREEN_400) if lic["is_active"] else ft.Icon(ft.Icons.CANCEL, size=16, color=ft.Colors.RED_400)
                rows.append(ft.DataRow(
                    cells=[
                        ft.DataCell(ft.Text(lic["plan"], size=12)),
                        ft.DataCell(ft.Text(lic["license_key"][:20] + "...", size=11, font_family="Courier New", selectable=True)),
                        ft.DataCell(ft.Text(lic["device_id"][:12] + "...", size=11, selectable=True)),
                        ft.DataCell(ft.Text(lic.get("customer_name", "") or "-", size=12)),
                        ft.DataCell(ft.Text(exp_short, size=12)),
                        ft.DataCell(active_icon),
                    ],
                    on_select_change=lambda e, lid=lic["id"]: show_detail_dialog(lid),
                ))

            table = ft.DataTable(
                columns=[
                    ft.DataColumn(ft.Text("Plan", size=11, weight=ft.FontWeight.BOLD)),
                    ft.DataColumn(ft.Text("License Key", size=11, weight=ft.FontWeight.BOLD)),
                    ft.DataColumn(ft.Text("Device", size=11, weight=ft.FontWeight.BOLD)),
                    ft.DataColumn(ft.Text("Customer", size=11, weight=ft.FontWeight.BOLD)),
                    ft.DataColumn(ft.Text("Expires", size=11, weight=ft.FontWeight.BOLD)),
                    ft.DataColumn(ft.Text("Status", size=11, weight=ft.FontWeight.BOLD)),
                ],
                rows=rows,
                border_radius=12,
                border=ft.Border.all(1, ft.Colors.with_opacity(0.15, self.ACCENT)),
                heading_row_color=ft.Colors.with_opacity(0.06, self.ACCENT),
                data_row_max_height=50,
                column_spacing=18,
            )
            table_container.controls.append(table)
            self.page.update()

        def show_detail_dialog(lid):
            lic = db_get_license(lid)
            if not lic:
                return

            name_f = ft.TextField(value=lic["customer_name"], label="Customer Name", width=350, border_radius=10)
            email_f = ft.TextField(value=lic["customer_email"], label="Customer Email", width=350, border_radius=10)
            notes_f = ft.TextField(value=lic["notes"], label="Notes", width=500, border_radius=10, multiline=True, min_lines=2, max_lines=4)
            dlg_status = ft.Text("", size=13)

            def save(e):
                db_update_customer(lid, name_f.value.strip(), email_f.value.strip())
                db_update_notes(lid, notes_f.value.strip())
                dlg_status.value = "Saved!"
                dlg_status.color = ft.Colors.GREEN_400
                self.page.update()

            def revoke_lic(e):
                reason_field = ft.TextField(label="Reason (optional)", width=400, border_radius=10)
                rvk_status = ft.Text("", size=12)

                def confirm_revoke(ev):
                    success, message = db_revoke_license(lid, reason_field.value.strip())
                    if success:
                        rvk_status.value = f"OK: {message}"
                        rvk_status.color = ft.Colors.GREEN_400
                    else:
                        rvk_status.value = f"Warning: {message}"
                        rvk_status.color = ft.Colors.AMBER_400
                    self.page.update()
                    time.sleep(1.5)
                    confirm_dlg.open = False
                    detail_dlg.open = False
                    self.page.update()
                    refresh_table()

                def cancel_revoke(ev):
                    confirm_dlg.open = False
                    self.page.update()

                confirm_dlg = ft.AlertDialog(
                    modal=True,
                    title=ft.Text("Revoke License", color=ft.Colors.RED_400),
                    content=ft.Column([
                        ft.Text("This will permanently deactivate the license.\nThe customer will lose access immediately.", size=13),
                        ft.Container(height=5),
                        reason_field,
                        ft.Container(height=5),
                        rvk_status,
                    ], tight=True, spacing=8),
                    actions=[
                        ft.TextButton("Cancel", on_click=cancel_revoke),
                        ft.FilledButton("Confirm Revoke", on_click=confirm_revoke,
                                        style=ft.ButtonStyle(bgcolor=ft.Colors.RED_400, color=ft.Colors.WHITE)),
                    ],
                    actions_alignment=ft.MainAxisAlignment.END,
                    bgcolor=self.CARD_BG,
                )
                self.page.overlay.append(confirm_dlg)
                confirm_dlg.open = True
                self.page.update()

            def delete_lic(e):
                db_delete_license(lid)
                detail_dlg.open = False
                self.page.update()
                refresh_table()

            def copy_key(e):
                try:
                    import pyperclip
                    pyperclip.copy(lic["license_key"])
                except Exception:
                    pass

            def close_dlg(e):
                detail_dlg.open = False
                self.page.update()

            revoked_info = []
            if lic.get("revoked_at"):
                revoked_info.append(ft.Text(f"Revoked: {(lic['revoked_at'] or '')[:19]}", size=12, color=ft.Colors.RED_400))
                if lic.get("revoke_reason"):
                    revoked_info.append(ft.Text(f"Reason: {lic['revoke_reason']}", size=12, color=ft.Colors.RED_300))

            detail_dlg = ft.AlertDialog(
                modal=True,
                title=ft.Text("License Details", size=20, weight=ft.FontWeight.BOLD, color=self.ACCENT),
                content=ft.Container(
                    content=ft.Column([
                        ft.Text("License Key", size=11, color=ft.Colors.GREY_400),
                        ft.Row([
                            ft.Text(lic["license_key"], size=13, weight=ft.FontWeight.BOLD, selectable=True, font_family="Courier New"),
                            ft.IconButton(icon=ft.Icons.COPY, icon_size=16, on_click=copy_key, icon_color=self.ACCENT),
                        ]),
                        ft.Divider(height=1, color=ft.Colors.with_opacity(0.1, self.ACCENT)),
                        ft.Column([
                            ft.Text(f"Plan: {lic['plan']}", size=13),
                            ft.Text(f"Device: {lic['device_id']}", size=12, color=ft.Colors.GREY_400, selectable=True),
                            ft.Text(f"Created: {(lic['created_at'] or '')[:19]}", size=12, color=ft.Colors.GREY_400),
                            ft.Text(f"Expires: {(lic['expires_at'] or '')[:10]}", size=12, color=ft.Colors.GREY_400),
                            *revoked_info,
                        ], spacing=4),
                        ft.Container(height=10),
                        name_f, email_f, notes_f,
                        ft.Container(height=5),
                        dlg_status,
                    ], spacing=8, tight=True),
                    width=550, padding=10,
                ),
                actions=[
                    ft.TextButton("Delete", on_click=delete_lic,
                                  style=ft.ButtonStyle(color=ft.Colors.with_opacity(0.5, ft.Colors.RED_400))),
                    ft.FilledButton("Revoke", on_click=revoke_lic,
                                    style=ft.ButtonStyle(bgcolor=ft.Colors.RED_400, color=ft.Colors.WHITE)) if lic["is_active"] else ft.Container(),
                    ft.FilledButton("Save", on_click=save, style=ft.ButtonStyle(bgcolor=self.ACCENT, color=self.BG)),
                    ft.TextButton("Close", on_click=close_dlg),
                ],
                actions_alignment=ft.MainAxisAlignment.END,
                bgcolor=self.CARD_BG,
            )
            self.page.overlay.append(detail_dlg)
            detail_dlg.open = True
            self.page.update()

        # Backup / Restore
        backup_status = ft.Text("", size=12)

        async def do_backup(e):
            picker = ft.FilePicker()
            self.page.overlay.append(picker)
            self.page.update()

            def on_save(ev: ft.FilePickerResultEvent):
                if ev.path:
                    cnt = db_backup(ev.path)
                    backup_status.value = f"Exported {cnt} licenses"
                    backup_status.color = ft.Colors.GREEN_400
                    self.page.update()

            picker.on_result = on_save
            picker.save_file(
                dialog_title="Save License Backup",
                file_name=f"license_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
                allowed_extensions=["json"],
            )

        async def do_restore(e):
            picker = ft.FilePicker()
            self.page.overlay.append(picker)
            self.page.update()

            def on_pick(ev: ft.FilePickerResultEvent):
                if ev.files:
                    imported, skipped = db_restore(ev.files[0].path)
                    backup_status.value = f"Imported {imported}, skipped {skipped} duplicates"
                    backup_status.color = ft.Colors.GREEN_400
                    self.page.update()
                    refresh_table()

            picker.on_result = on_pick
            picker.pick_files(
                dialog_title="Select License Backup",
                allowed_extensions=["json"],
                allow_multiple=False,
            )

        self._content_area.controls.extend([
            ft.Container(height=10),
            ft.Text("All Licenses", size=22, weight=ft.FontWeight.BOLD),
            ft.Container(height=15),
            ft.Row([
                search_field,
                ft.FilledButton("Search", icon=ft.Icons.SEARCH, on_click=lambda e: refresh_table(),
                                style=ft.ButtonStyle(bgcolor=self.ACCENT, color=self.BG), height=42),
                ft.TextButton("Refresh", icon=ft.Icons.REFRESH, on_click=lambda e: refresh_table()),
            ], spacing=10),
            ft.Container(height=15),
            table_container,
            ft.Container(height=20),
            ft.Divider(height=1, color=ft.Colors.with_opacity(0.1, self.ACCENT)),
            ft.Container(height=10),
            ft.Row([
                ft.FilledButton("Backup", icon=ft.Icons.BACKUP, on_click=do_backup,
                                style=ft.ButtonStyle(bgcolor=self.ACCENT, color=self.BG)),
                ft.OutlinedButton("Restore", icon=ft.Icons.RESTORE, on_click=do_restore,
                                  style=ft.ButtonStyle(color=self.ACCENT)),
                backup_status,
            ], spacing=15),
        ])
        refresh_table()

    # ══════════════════════════════════════════════════════════════════
    #  PAGE: Monitoring Jobs
    # ══════════════════════════════════════════════════════════════════
    def _page_monitoring(self):
        jobs = get_monitoring_jobs()
        mon_stats = get_monitoring_stats()

        self._content_area.controls.extend([
            ft.Container(height=10),
            ft.Text("Monitoring Jobs", size=22, weight=ft.FontWeight.BOLD),
            ft.Container(height=15),
            ft.Row([
                self._stat_card(ft.Icons.PLAY_CIRCLE, mon_stats["active_jobs"], "Active Jobs", ft.Colors.GREEN_400),
                self._stat_card(ft.Icons.SEARCH, mon_stats["total_checks"], "Total Checks"),
                self._stat_card(ft.Icons.EVENT_AVAILABLE, mon_stats["slots_found"], "Slots Found", ft.Colors.AMBER_400),
            ], spacing=10),
            ft.Container(height=20),
        ])

        if not jobs:
            self._content_area.controls.append(
                self._glass(ft.Column([
                    ft.Icon(ft.Icons.HOURGLASS_EMPTY, size=48, color=ft.Colors.GREY_500),
                    ft.Container(height=10),
                    ft.Text("No monitoring jobs yet", size=16, color=ft.Colors.GREY_400, text_align=ft.TextAlign.CENTER),
                    ft.Text("Users will appear here when they start monitoring from the app",
                            size=13, color=ft.Colors.GREY_600, text_align=ft.TextAlign.CENTER),
                ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=4), padding=30)
            )
            return

        rows = []
        for job in jobs:
            status_color = {
                "idle": ft.Colors.GREEN_400, "checking": ft.Colors.AMBER_400,
                "pending": self.ACCENT, "error": ft.Colors.RED_400,
                "stopped": ft.Colors.GREY_500, "revoked": ft.Colors.RED_400,
            }.get(job.get("status", ""), ft.Colors.GREY_500)

            def _stop_job(e, jid=job["id"]):
                stop_monitoring_job(jid)
                self._server_log(f"Job {jid} stopped manually")
                self._route(3)

            def _view_logs(e, jid=job["id"]):
                self._nav_index = 4
                self._route(4)

            rows.append(ft.DataRow(cells=[
                ft.DataCell(ft.Text(str(job["id"]), size=12)),
                ft.DataCell(ft.Text(job.get("tls_email", ""), size=11, selectable=True)),
                ft.DataCell(ft.Text(job.get("branch", "-"), size=11)),
                ft.DataCell(ft.Text(job.get("notification_email", ""), size=11)),
                ft.DataCell(ft.Text(job.get("status", ""), size=12, color=status_color, weight=ft.FontWeight.BOLD)),
                ft.DataCell(ft.Text(str(job.get("total_checks", 0)), size=12)),
                ft.DataCell(ft.Text(str(job.get("slots_found_total", 0)), size=12)),
                ft.DataCell(ft.Text((job.get("last_check_at") or "-")[:16], size=11)),
                ft.DataCell(ft.Text(f"{job.get('check_interval', 60)}m", size=12)),
                ft.DataCell(ft.Row([
                    ft.IconButton(icon=ft.Icons.STOP, icon_size=18, icon_color=ft.Colors.RED_400,
                                  on_click=_stop_job, tooltip="Stop") if job.get("is_active") else ft.Container(),
                    ft.IconButton(icon=ft.Icons.ARTICLE, icon_size=18, icon_color=self.ACCENT,
                                  on_click=_view_logs, tooltip="Logs"),
                ], spacing=0)),
            ]))

        table = ft.DataTable(
            columns=[
                ft.DataColumn(ft.Text("ID", size=11, weight=ft.FontWeight.BOLD)),
                ft.DataColumn(ft.Text("TLS Email", size=11, weight=ft.FontWeight.BOLD)),
                ft.DataColumn(ft.Text("Branch", size=11, weight=ft.FontWeight.BOLD)),
                ft.DataColumn(ft.Text("Notify", size=11, weight=ft.FontWeight.BOLD)),
                ft.DataColumn(ft.Text("Status", size=11, weight=ft.FontWeight.BOLD)),
                ft.DataColumn(ft.Text("Checks", size=11, weight=ft.FontWeight.BOLD)),
                ft.DataColumn(ft.Text("Found", size=11, weight=ft.FontWeight.BOLD)),
                ft.DataColumn(ft.Text("Last Check", size=11, weight=ft.FontWeight.BOLD)),
                ft.DataColumn(ft.Text("Interval", size=11, weight=ft.FontWeight.BOLD)),
                ft.DataColumn(ft.Text("Actions", size=11, weight=ft.FontWeight.BOLD)),
            ],
            rows=rows,
            border_radius=12,
            border=ft.Border.all(1, ft.Colors.with_opacity(0.15, self.ACCENT)),
            heading_row_color=ft.Colors.with_opacity(0.06, self.ACCENT),
            data_row_max_height=50,
            column_spacing=14,
        )
        self._content_area.controls.append(table)

    # ══════════════════════════════════════════════════════════════════
    #  PAGE: Logs
    # ══════════════════════════════════════════════════════════════════
    def _page_logs(self):
        # Server logs
        server_log_list = ft.ListView(spacing=4, padding=10, auto_scroll=True, height=250)
        for ts, msg in self._server_logs[-100:]:
            color = ft.Colors.GREEN_400 if ("started" in msg.lower() or "ok" in msg.lower()) else \
                    ft.Colors.RED_400 if ("error" in msg.lower() or "fail" in msg.lower()) else \
                    ft.Colors.GREY_300
            server_log_list.controls.append(
                ft.Text(f"[{ts}] {msg}", size=11, color=color, selectable=True)
            )
        if not self._server_logs:
            server_log_list.controls.append(
                ft.Text("No server logs yet. Start the server to see logs here.", size=12, color=ft.Colors.GREY_500)
            )

        # Monitoring logs from DB
        monitor_logs = get_monitoring_logs(limit=200)
        monitor_log_list = ft.ListView(spacing=4, padding=10, auto_scroll=True, height=350)
        for log in reversed(monitor_logs):
            level = log.get("level", "info")
            color = ft.Colors.RED_400 if level == "error" else \
                    ft.Colors.AMBER_400 if level == "warning" else \
                    ft.Colors.GREY_300
            email = log.get("tls_email", "")
            ts = (log.get("timestamp") or "")[:19]
            msg = log.get("message", "")
            monitor_log_list.controls.append(
                ft.Text(f"[{ts}] [{email}] {msg}", size=11, color=color, selectable=True)
            )
        if not monitor_logs:
            monitor_log_list.controls.append(
                ft.Text("No monitoring logs. Logs appear here when the server runs checks.", size=12, color=ft.Colors.GREY_500)
            )

        def clear_server_logs(e):
            self._server_logs.clear()
            self._route(4)

        self._content_area.controls.extend([
            ft.Container(height=10),
            ft.Text("Server & Monitoring Logs", size=22, weight=ft.FontWeight.BOLD),
            ft.Container(height=15),
            ft.Row([
                ft.Icon(ft.Icons.DNS, size=20, color=self.ACCENT),
                ft.Text("Server Logs", size=16, weight=ft.FontWeight.W_600),
                ft.Container(expand=True),
                ft.TextButton("Clear", icon=ft.Icons.DELETE_SWEEP, on_click=clear_server_logs,
                              style=ft.ButtonStyle(color=ft.Colors.GREY_400)),
            ], spacing=8),
            self._glass(server_log_list, padding=10),
            ft.Container(height=20),
            ft.Row([
                ft.Icon(ft.Icons.MONITOR_HEART, size=20, color=self.ACCENT),
                ft.Text("Monitoring Activity", size=16, weight=ft.FontWeight.W_600),
            ], spacing=8),
            self._glass(monitor_log_list, padding=10),
        ])


# ════════════════════════════════════════════════════════════════════
#  Entry
# ════════════════════════════════════════════════════════════════════
def main(page: ft.Page):
    ServerManagerApp(page)


if __name__ == "__main__":
    app_dir = os.path.dirname(os.path.abspath(__file__))

    def _port_free(port):
        for fam, host in ((socket.AF_INET6, "::"), (socket.AF_INET, "0.0.0.0")):
            try:
                with socket.socket(fam, socket.SOCK_STREAM) as s:
                    if fam == socket.AF_INET6:
                        try:
                            s.setsockopt(socket.IPPROTO_IPV6, socket.IPV6_V6ONLY, 1)
                        except OSError:
                            pass
                    s.bind((host, port))
            except OSError:
                return False
        return True

    pref = int(os.environ.get("FLET_PORT", "8090"))
    port = pref
    if not _port_free(pref):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind(("0.0.0.0", 0))
            port = s.getsockname()[1]
        print(f"Port {pref} busy; using {port}")

    ft.run(main, assets_dir=app_dir, view=ft.AppView.FLET_APP)
