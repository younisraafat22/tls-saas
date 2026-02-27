"""
TLS Appointment Checker — License Manager
Admin GUI tool for generating, viewing, and managing license keys.
Run:  python license_manager.py
"""
import flet as ft
import sqlite3
import os
import sys
import base64
from datetime import datetime, timedelta, timezone

# Ensure sibling imports work
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from license_service import generate_license_key, PLANS, get_hardware_id, parse_license_key

# Server URL for syncing license status
# Point to your local monitoring server (default) or a remote URL
# If using ngrok, set the ngrok URL here or as environment variable
LICENSE_SERVER_URL = os.environ.get('LICENSE_SERVER_URL', 'http://localhost:5000')
# Admin API key — must match the key shown when monitoring_server.py starts
ADMIN_API_KEY = os.environ.get('ADMIN_API_KEY', 'changeme-admin-key-2026')

# ────────────────────────────────────────────────────────────────────
#  Database  (writable location — AppData when installed, else script dir)
# ────────────────────────────────────────────────────────────────────
def _get_db_path():
    """Return a writable path for the license database."""
    # When running as PyInstaller bundle, use AppData to avoid Program Files permission issues
    if getattr(sys, 'frozen', False):
        app_data = os.path.join(os.environ.get('APPDATA', os.path.expanduser('~')),
                                'TLS License Manager')
        os.makedirs(app_data, exist_ok=True)
        return os.path.join(app_data, 'license_manager.db')
    # Development: use script directory
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
    # Add new columns to existing DB (safe migration)
    for col, coldef in [("revoked_at", "TIMESTAMP DEFAULT NULL"), ("revoke_reason", "TEXT DEFAULT ''")]:
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
    # First, get the license key and device_id
    row = conn.execute("SELECT license_key, device_id FROM licenses WHERE id=?", (lid,)).fetchone()
    if not row:
        conn.close()
        return False, "License not found"
    
    license_key, device_id = row
    
    # Update local database
    conn.execute(
        "UPDATE licenses SET is_active=0, revoked_at=?, revoke_reason=? WHERE id=?",
        (datetime.now(timezone.utc).isoformat(), reason, lid),
    )
    conn.commit()
    conn.close()
    
    # Sync to server
    return _sync_revoke_to_server(license_key, device_id, reason)


def _sync_revoke_to_server(license_key, device_id, reason=""):
    """Sync license revocation to server so client apps get notified."""
    try:
        import urllib.request
        import urllib.error
        import json
        
        payload = json.dumps({
            "license_key": license_key,
            "hardware_id": device_id
        }).encode()
        
        req = urllib.request.Request(
            f"{LICENSE_SERVER_URL.rstrip('/')}/api/license/revoke",
            data=payload,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {ADMIN_API_KEY}"
            },
            method="POST",
        )
        
        with urllib.request.urlopen(req, timeout=10) as resp:
            result = json.loads(resp.read())
            if result.get("success"):
                return True, f"License revoked (affected {result.get('revoked', 0)} records)"
            else:
                return False, result.get("error", "Server revocation failed")
    except urllib.error.HTTPError as e:
        if e.code == 401:
            return False, "Unauthorized - Check ADMIN_API_KEY in license_manager.py"
        error_msg = e.read().decode() if e.code != 404 else "Server endpoint not found"
        return False, f"Server error ({e.code}): {error_msg[:100]}"
    except Exception as e:
        return False, f"Failed to sync to server: {str(e)[:100]}"


def db_delete_license(lid):
    conn = _conn()
    conn.execute("DELETE FROM licenses WHERE id=?", (lid,))
    conn.commit()
    conn.close()


def db_backup(filepath):
    """Export all licenses to a JSON file."""
    import json
    licenses = db_get_all_licenses()
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump({"exported_at": datetime.now(timezone.utc).isoformat(), "licenses": licenses}, f, indent=2, default=str)
    return len(licenses)


def db_restore(filepath):
    """Import licenses from a JSON backup file. Skips duplicates."""
    import json
    with open(filepath, "r", encoding="utf-8") as f:
        data = json.load(f)
    licenses = data.get("licenses", [])
    conn = _conn()
    imported = 0
    skipped = 0
    for lic in licenses:
        try:
            conn.execute(
                "INSERT INTO licenses (license_key,plan,device_id,customer_name,customer_email,created_at,expires_at,is_active,notes,revoked_at,revoke_reason) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                (lic["license_key"], lic["plan"], lic["device_id"], lic.get("customer_name",""),
                 lic.get("customer_email",""), lic.get("created_at"), lic.get("expires_at"),
                 lic.get("is_active",1), lic.get("notes",""), lic.get("revoked_at"), lic.get("revoke_reason","")),
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
#  Logo helper (optional)
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


# ────────────────────────────────────────────────────────────────────
#  App
# ────────────────────────────────────────────────────────────────────
class LicenseManagerApp:
    ACCENT = "#00D9FF"
    BG = "#0A0E27"
    CARD_BG = "#1A1F3A"

    def __init__(self, page: ft.Page):
        self.page = page
        self.page.title = "TLS License Manager"
        self.page.bgcolor = self.BG
        self.page.theme_mode = ft.ThemeMode.DARK
        self.page.window.width = 1100
        self.page.window.height = 780
        self.page.window.min_width = 900
        self.page.window.min_height = 700
        self.page.padding = 0
        self.page.fonts = {
            "Montserrat": "https://fonts.googleapis.com/css2?family=Montserrat:wght@300;400;500;600;700;800&display=swap"
        }
        self.page.theme = ft.Theme(color_scheme_seed=self.ACCENT, font_family="Montserrat")
        self._logo_src = _load_logo()

        # Centre window
        try:
            import tkinter as tk
            root = tk.Tk(); root.withdraw()
            sw, sh = root.winfo_screenwidth(), root.winfo_screenheight()
            root.destroy()
            self.page.window.left = (sw - 1100) // 2
            self.page.window.top = (sh - 780) // 2
        except Exception:
            pass

        init_manager_db()

        # Navigation state
        self._nav_index = 0
        self._build_shell()

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
                    ft.Text(str(value), size=32, weight=ft.FontWeight.BOLD, color=color),
                    ft.Text(label, size=11, color=ft.Colors.GREY_400),
                ],
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                spacing=2,
            ),
            width=200, padding=18,
        )

    # ── shell: nav bar + content area ──────────────────────────────
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
                ft.NavigationRailDestination(icon=ft.Icons.DASHBOARD, label="Dashboard"),
                ft.NavigationRailDestination(icon=ft.Icons.ADD_CIRCLE, label="Generate"),
                ft.NavigationRailDestination(icon=ft.Icons.LIST_ALT, label="Licenses"),
                ft.NavigationRailDestination(icon=ft.Icons.PEOPLE, label="Customers"),
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
            self._page_dashboard()
        elif idx == 1:
            self._page_generate()
        elif idx == 2:
            self._page_licenses()
        elif idx == 3:
            self._page_customers()
        self.page.update()

    # ── page: Dashboard ────────────────────────────────────────────
    def _page_dashboard(self):
        stats = db_stats()
        self._content_area.controls.extend([
            ft.Container(height=10),
            ft.Row(
                [
                    ft.Image(src=self._logo_src or "", width=180, height=45) if self._logo_src else ft.Container(),
                    ft.Text("License Manager", size=22, weight=ft.FontWeight.BOLD),
                ],
                spacing=15,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            ),
            ft.Container(height=25),
            ft.Row(
                [
                    self._stat_card(ft.Icons.CONFIRMATION_NUMBER, stats["total"], "Total Licenses"),
                    self._stat_card(ft.Icons.CHECK_CIRCLE, stats["active"], "Active", ft.Colors.GREEN_400),
                    self._stat_card(ft.Icons.TIMER_OFF, stats["expired"], "Expired", ft.Colors.RED_400),
                    self._stat_card(ft.Icons.ATTACH_MONEY, f"{stats['revenue']:,.0f} EGP", "Revenue", ft.Colors.AMBER_400),
                ],
                spacing=15, wrap=True,
            ),
            ft.Container(height=30),
            ft.Text("Recent licenses", size=16, weight=ft.FontWeight.W_600),
            ft.Container(height=10),
        ])

        recent = db_get_all_licenses()[:8]
        if not recent:
            self._content_area.controls.append(
                ft.Text("No licenses yet. Go to Generate to create one.", color=ft.Colors.GREY_500)
            )
        else:
            rows = []
            for lic in recent:
                exp = lic["expires_at"] or ""
                exp_short = exp[:10] if exp else "—"
                active_icon = ft.Icon(ft.Icons.CHECK_CIRCLE, size=16, color=ft.Colors.GREEN_400) if lic["is_active"] else ft.Icon(ft.Icons.CANCEL, size=16, color=ft.Colors.RED_400)
                rows.append(
                    ft.DataRow(cells=[
                        ft.DataCell(ft.Text(lic["plan"], size=12)),
                        ft.DataCell(ft.Text(lic["device_id"][:12] + "…", size=12)),
                        ft.DataCell(ft.Text(lic["customer_name"] or "—", size=12)),
                        ft.DataCell(ft.Text(exp_short, size=12)),
                        ft.DataCell(active_icon),
                    ])
                )
            table = ft.DataTable(
                columns=[
                    ft.DataColumn(ft.Text("Plan", size=12, weight=ft.FontWeight.BOLD)),
                    ft.DataColumn(ft.Text("Device ID", size=12, weight=ft.FontWeight.BOLD)),
                    ft.DataColumn(ft.Text("Customer", size=12, weight=ft.FontWeight.BOLD)),
                    ft.DataColumn(ft.Text("Expires", size=12, weight=ft.FontWeight.BOLD)),
                    ft.DataColumn(ft.Text("Active", size=12, weight=ft.FontWeight.BOLD)),
                ],
                rows=rows,
                border_radius=12,
                border=ft.border.all(1, ft.Colors.with_opacity(0.15, self.ACCENT)),
                heading_row_color=ft.Colors.with_opacity(0.06, self.ACCENT),
                data_row_max_height=48,
            )
            self._content_area.controls.append(table)

        # ── Backup / Restore buttons ──
        backup_status = ft.Text("", size=12)

        async def do_backup(e):
            picker = ft.FilePicker()
            self.page.overlay.append(picker)
            self.page.update()
            def on_save(ev: ft.FilePickerResultEvent):
                if ev.path:
                    try:
                        count = db_backup(ev.path)
                        backup_status.value = f"✓ Backed up {count} licenses to {os.path.basename(ev.path)}"
                        backup_status.color = ft.Colors.GREEN_400
                    except Exception as ex:
                        backup_status.value = f"✗ Backup failed: {ex}"
                        backup_status.color = ft.Colors.RED_400
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
                    try:
                        imported, skipped = db_restore(ev.files[0].path)
                        backup_status.value = f"✓ Imported {imported} licenses ({skipped} duplicates skipped)"
                        backup_status.color = ft.Colors.GREEN_400
                        self._route(0)  # refresh dashboard
                    except Exception as ex:
                        backup_status.value = f"✗ Restore failed: {ex}"
                        backup_status.color = ft.Colors.RED_400
                    self.page.update()
            picker.on_result = on_pick
            picker.pick_files(
                dialog_title="Select License Backup",
                allowed_extensions=["json"],
                allow_multiple=False,
            )

        self._content_area.controls.extend([
            ft.Container(height=25),
            ft.Divider(height=1, color=ft.Colors.with_opacity(0.1, self.ACCENT)),
            ft.Container(height=15),
            ft.Text("Database Management", size=16, weight=ft.FontWeight.W_600),
            ft.Container(height=10),
            ft.Row([
                ft.FilledButton("Backup Licenses", icon=ft.Icons.BACKUP, on_click=do_backup,
                    style=ft.ButtonStyle(bgcolor=self.ACCENT, color=self.BG)),
                ft.OutlinedButton("Restore from Backup", icon=ft.Icons.RESTORE, on_click=do_restore,
                    style=ft.ButtonStyle(color=self.ACCENT)),
                backup_status,
            ], spacing=15),
        ])

    # ── page: Generate license ─────────────────────────────────────
    def _page_generate(self):
        plan_dd = ft.Dropdown(
            label="License Type",
            width=350, border_radius=12,
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
        name_field = ft.TextField(
            label="Customer Name (optional)",
            width=350, border_radius=12, prefix_icon=ft.Icons.PERSON,
        )
        email_field = ft.TextField(
            label="Customer Email (optional)",
            width=350, border_radius=12, prefix_icon=ft.Icons.EMAIL,
        )
        notes_field = ft.TextField(
            label="Notes (optional)",
            width=500, border_radius=12, multiline=True, min_lines=2, max_lines=4,
        )

        result_key = ft.Text("", size=16, weight=ft.FontWeight.BOLD, color=self.ACCENT, selectable=True)
        status_msg = ft.Text("", size=14)

        def generate(e):
            plan = plan_dd.value
            device_id = (device_field.value or "").strip()
            if not plan or not device_id:
                status_msg.value = "Plan and Device ID are required."
                status_msg.color = ft.Colors.RED_400
                self.page.update()
                return
            if len(device_id) < 8:
                status_msg.value = "Device ID must be at least 8 characters."
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
            except sqlite3.IntegrityError:
                status_msg.value = "Duplicate key (extremely rare). Try again."
                status_msg.color = ft.Colors.RED_400
                self.page.update()
                return

            result_key.value = key
            status_msg.value = f"License generated!  Type: {plan_info['name']},  Expires: {expires_at[:10]}"
            status_msg.color = ft.Colors.GREEN_400
            self.page.update()

        def copy_key(e):
            if result_key.value:
                try:
                    import pyperclip
                    pyperclip.copy(result_key.value)
                    status_msg.value = "Key copied to clipboard!"
                    status_msg.color = ft.Colors.GREEN_400
                except ImportError:
                    try:
                        self.page.set_clipboard(result_key.value)
                        status_msg.value = "Key copied to clipboard!"
                        status_msg.color = ft.Colors.GREEN_400
                    except Exception:
                        status_msg.value = "Select the key text above and copy manually (Ctrl+C)."
                        status_msg.color = ft.Colors.ORANGE_400
                except Exception:
                    status_msg.value = "Select the key text above and copy manually (Ctrl+C)."
                    status_msg.color = ft.Colors.ORANGE_400
                self.page.update()

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
                        "Generate Key",
                        icon=ft.Icons.VPN_KEY,
                        width=250, height=48,
                        on_click=generate,
                        style=ft.ButtonStyle(bgcolor=self.ACCENT, color=self.BG),
                    ),
                    ft.Container(height=15),
                    ft.Divider(height=1, color=ft.Colors.with_opacity(0.15, self.ACCENT)),
                    ft.Container(height=10),
                    ft.Text("Generated Key:", size=12, color=ft.Colors.GREY_400),
                    ft.Row([
                        result_key,
                        ft.IconButton(icon=ft.Icons.COPY, on_click=copy_key, icon_color=self.ACCENT, tooltip="Copy"),
                    ], spacing=10),
                    ft.Container(height=5),
                    status_msg,
                ], spacing=4),
                width=700, padding=25,
            ),
        ])

    # ── page: All licenses ─────────────────────────────────────────
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
                table_container.controls.append(
                    ft.Text("No licenses found.", color=ft.Colors.GREY_500)
                )
                self.page.update()
                return

            rows = []
            for lic in licenses:
                lid = lic["id"]
                exp = (lic["expires_at"] or "")[:10]
                is_expired = False
                if lic["expires_at"]:
                    try:
                        exp_dt = datetime.fromisoformat(lic["expires_at"])
                        # Ensure timezone-aware for comparison
                        if exp_dt.tzinfo is None:
                            exp_dt = exp_dt.replace(tzinfo=timezone.utc)
                        is_expired = exp_dt < datetime.now(timezone.utc)
                    except Exception:
                        pass

                if not lic["is_active"]:
                    active_chip = ft.Container(
                        content=ft.Text("Revoked", size=10, color=ft.Colors.RED_400),
                        bgcolor=ft.Colors.with_opacity(0.15, ft.Colors.RED),
                        padding=ft.Padding(8, 3, 8, 3), border_radius=6,
                    )
                elif is_expired:
                    active_chip = ft.Container(
                        content=ft.Text("Expired", size=10, color=ft.Colors.ORANGE_400),
                        bgcolor=ft.Colors.with_opacity(0.15, ft.Colors.ORANGE),
                        padding=ft.Padding(8, 3, 8, 3), border_radius=6,
                    )
                else:
                    active_chip = ft.Container(
                        content=ft.Text("Active", size=10, color=ft.Colors.GREEN_400),
                        bgcolor=ft.Colors.with_opacity(0.15, ft.Colors.GREEN),
                        padding=ft.Padding(8, 3, 8, 3), border_radius=6,
                    )

                def make_detail_handler(license_id):
                    return lambda e: show_detail_dialog(license_id)

                rows.append(
                    ft.DataRow(
                        cells=[
                            ft.DataCell(ft.Text(lic["plan"], size=12)),
                            ft.DataCell(ft.Text(lic["license_key"][:24] + "…", size=11, font_family="Courier New")),
                            ft.DataCell(ft.Text(lic["device_id"][:12] + "…", size=12)),
                            ft.DataCell(ft.Text(lic["customer_name"] or "—", size=12)),
                            ft.DataCell(ft.Text(exp or "—", size=12)),
                            ft.DataCell(active_chip),
                            ft.DataCell(
                                ft.IconButton(
                                    icon=ft.Icons.OPEN_IN_NEW, icon_size=18,
                                    icon_color=self.ACCENT,
                                    on_click=make_detail_handler(lid),
                                    tooltip="Details",
                                ),
                            ),
                        ],
                    )
                )

            table = ft.DataTable(
                columns=[
                    ft.DataColumn(ft.Text("Plan", size=11, weight=ft.FontWeight.BOLD)),
                    ft.DataColumn(ft.Text("License Key", size=11, weight=ft.FontWeight.BOLD)),
                    ft.DataColumn(ft.Text("Device", size=11, weight=ft.FontWeight.BOLD)),
                    ft.DataColumn(ft.Text("Customer", size=11, weight=ft.FontWeight.BOLD)),
                    ft.DataColumn(ft.Text("Expires", size=11, weight=ft.FontWeight.BOLD)),
                    ft.DataColumn(ft.Text("Status", size=11, weight=ft.FontWeight.BOLD)),
                    ft.DataColumn(ft.Text("", size=11)),
                ],
                rows=rows,
                border_radius=12,
                border=ft.border.all(1, ft.Colors.with_opacity(0.15, self.ACCENT)),
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

            def toggle_active(e):
                new_state = not bool(lic["is_active"])
                db_toggle_active(lid, new_state)
                lic["is_active"] = 1 if new_state else 0
                toggle_btn.text = "Revoke" if new_state else "Reactivate"
                toggle_btn.style = ft.ButtonStyle(
                    color=ft.Colors.RED_400 if new_state else ft.Colors.GREEN_400,
                )
                dlg_status.value = "Active" if new_state else "Revoked"
                dlg_status.color = ft.Colors.GREEN_400 if new_state else ft.Colors.RED_400
                self.page.update()

            def revoke_lic(e):
                reason_field = ft.TextField(label="Reason (optional)", width=400, border_radius=10)
                status_text = ft.Text("", size=12)
                
                def confirm_revoke(ev):
                    success, message = db_revoke_license(lid, reason_field.value.strip())
                    if success:
                        status_text.value = f"✓ {message}"
                        status_text.color = ft.Colors.GREEN_400
                    else:
                        status_text.value = f"⚠ Local DB updated, but server sync failed: {message}"
                        status_text.color = ft.Colors.AMBER_400
                    self.page.update()
                    
                    # Close dialogs after a short delay
                    import time
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
                        ft.Text("This will permanently deactivate the license.\nThe customer will lose access immediately on their next check.", size=13),
                        ft.Container(height=5),
                        reason_field,
                        ft.Container(height=5),
                        status_text,
                    ], tight=True, spacing=8),
                    actions=[
                        ft.TextButton("Cancel", on_click=cancel_revoke),
                        ft.FilledButton("Revoke", on_click=confirm_revoke, style=ft.ButtonStyle(bgcolor=ft.Colors.RED_400, color=ft.Colors.WHITE)),
                    ],
                    bgcolor=self.CARD_BG,
                )
                self.page.overlay.append(confirm_dlg)
                confirm_dlg.open = True
                self.page.update()

            def delete_lic(e):
                def confirm_delete(ev):
                    db_delete_license(lid)
                    del_dlg.open = False
                    detail_dlg.open = False
                    self.page.update()
                    refresh_table()
                def cancel_delete(ev):
                    del_dlg.open = False
                    self.page.update()
                del_dlg = ft.AlertDialog(
                    modal=True,
                    title=ft.Text("Delete License Record", color=ft.Colors.RED_400),
                    content=ft.Text("This permanently removes the license record from your database.\n\nNote: If the customer already activated it, their app will still work\nuntil the license expires. Use 'Revoke' instead to deactivate it.", size=13),
                    actions=[
                        ft.TextButton("Cancel", on_click=cancel_delete),
                        ft.FilledButton("Delete", on_click=confirm_delete, style=ft.ButtonStyle(bgcolor=ft.Colors.RED_400, color=ft.Colors.WHITE)),
                    ],
                    bgcolor=self.CARD_BG,
                )
                self.page.overlay.append(del_dlg)
                del_dlg.open = True
                self.page.update()

            def copy_key(e):
                try:
                    import pyperclip
                    pyperclip.copy(lic["license_key"])
                    dlg_status.value = "Key copied!"
                    dlg_status.color = self.ACCENT
                except ImportError:
                    try:
                        self.page.set_clipboard(lic["license_key"])
                        dlg_status.value = "Key copied!"
                        dlg_status.color = self.ACCENT
                    except Exception:
                        dlg_status.value = "Press Ctrl+C to copy from above"
                        dlg_status.color = ft.Colors.ORANGE_400
                except Exception:
                    dlg_status.value = "Press Ctrl+C to copy from above"
                    dlg_status.color = ft.Colors.ORANGE_400
                self.page.update()

            def close_dlg(e):
                detail_dlg.open = False
                self.page.update()
                refresh_table()

            toggle_btn = ft.TextButton(
                "Revoke" if lic["is_active"] else "Reactivate",
                on_click=toggle_active,
                style=ft.ButtonStyle(color=ft.Colors.RED_400 if lic["is_active"] else ft.Colors.GREEN_400),
            )

            revoked_info = []
            if lic.get("revoked_at"):
                revoked_info.append(ft.Text(f"Revoked: {(lic['revoked_at'] or '')[:19]}", size=12, color=ft.Colors.RED_400))
                if lic.get("revoke_reason"):
                    revoked_info.append(ft.Text(f"Reason: {lic['revoke_reason']}", size=12, color=ft.Colors.RED_300, italic=True))

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
                        ft.Row([
                            ft.Column([
                                ft.Text(f"Plan: {lic['plan']}", size=13),
                                ft.Text(f"Device: {lic['device_id']}", size=12, color=ft.Colors.GREY_400, selectable=True),
                                ft.Text(f"Created: {(lic['created_at'] or '')[:19]}", size=12, color=ft.Colors.GREY_400),
                                ft.Text(f"Expires: {(lic['expires_at'] or '')[:10]}", size=12, color=ft.Colors.GREY_400),
                                *revoked_info,
                            ], spacing=4),
                        ]),
                        ft.Container(height=10),
                        name_f,
                        email_f,
                        notes_f,
                        ft.Container(height=5),
                        dlg_status,
                    ], spacing=8, tight=True),
                    width=550, padding=10,
                ),
                actions=[
                    ft.TextButton("Delete", on_click=delete_lic, style=ft.ButtonStyle(color=ft.Colors.with_opacity(0.5, ft.Colors.RED_400))),
                    ft.FilledButton("Revoke", on_click=revoke_lic, style=ft.ButtonStyle(bgcolor=ft.Colors.RED_400, color=ft.Colors.WHITE)) if lic["is_active"] else toggle_btn,
                    ft.FilledButton("Save", on_click=save, style=ft.ButtonStyle(bgcolor=self.ACCENT, color=self.BG)),
                    ft.TextButton("Close", on_click=close_dlg),
                ],
                actions_alignment=ft.MainAxisAlignment.END,
                bgcolor=self.CARD_BG,
            )
            self.page.overlay.append(detail_dlg)
            detail_dlg.open = True
            self.page.update()

        self._content_area.controls.extend([
            ft.Container(height=10),
            ft.Text("All Licenses", size=22, weight=ft.FontWeight.BOLD),
            ft.Container(height=15),
            ft.Row([
                search_field,
                ft.FilledButton(
                    "Search", icon=ft.Icons.SEARCH,
                    on_click=lambda e: refresh_table(),
                    style=ft.ButtonStyle(bgcolor=self.ACCENT, color=self.BG),
                    height=42,
                ),
                ft.TextButton(
                    "Refresh", icon=ft.Icons.REFRESH,
                    on_click=lambda e: refresh_table(),
                ),
            ], spacing=10),
            ft.Container(height=15),
            table_container,
        ])

        refresh_table()

    # ── page: Customers ────────────────────────────────────────────
    def _page_customers(self):
        """Customer management page - grouped by email."""
        search_field = ft.TextField(
            label="Search by name or email",
            width=400, border_radius=12, prefix_icon=ft.Icons.SEARCH,
            on_submit=lambda e: refresh_customers(),
        )

        customers_container = ft.Column(scroll=ft.ScrollMode.AUTO)

        def refresh_customers():
            customers_container.controls.clear()
            all_licenses = db_get_all_licenses(search_field.value or "")

            # Group by customer email
            customers = {}
            for lic in all_licenses:
                email = lic.get("customer_email", "").strip() or "No Email"
                if email not in customers:
                    customers[email] = {
                        "name": lic.get("customer_name", ""),
                        "email": email,
                        "licenses": [],
                        "devices": set(),
                    }
                customers[email]["licenses"].append(lic)
                customers[email]["devices"].add(lic["device_id"])
                if lic.get("customer_name") and not customers[email]["name"]:
                    customers[email]["name"] = lic["customer_name"]

            if not customers:
                customers_container.controls.append(
                    ft.Text("No customers found.", color=ft.Colors.GREY_500)
                )
                self.page.update()
                return

            for email, data in customers.items():
                active_count = sum(1 for l in data["licenses"] if l["is_active"])
                total_count = len(data["licenses"])
                device_count = len(data["devices"])

                license_chips = []
                for lic in data["licenses"][:5]:
                    color = ft.Colors.GREEN_400 if lic["is_active"] else ft.Colors.RED_400
                    license_chips.append(
                        ft.Container(
                            content=ft.Text(
                                f"{lic['plan']} - {lic['license_key'][:16]}...",
                                size=11, color=color,
                            ),
                            bgcolor=ft.Colors.with_opacity(0.1, color),
                            padding=ft.Padding(8, 4, 8, 4),
                            border_radius=6,
                        )
                    )

                device_chips = []
                for dev in list(data["devices"])[:3]:
                    device_chips.append(
                        ft.Container(
                            content=ft.Text(f"Device: {dev[:16]}...", size=10, color=ft.Colors.GREY_300),
                            bgcolor=ft.Colors.with_opacity(0.08, ft.Colors.WHITE),
                            padding=ft.Padding(6, 3, 6, 3),
                            border_radius=6,
                        )
                    )

                customer_card = self._glass(
                    ft.Column([
                        ft.Row([
                            ft.Icon(ft.Icons.PERSON, size=24, color=self.ACCENT),
                            ft.Column([
                                ft.Text(data["name"] or "Unknown", size=15, weight=ft.FontWeight.BOLD),
                                ft.Text(email, size=12, color=ft.Colors.GREY_400),
                            ], spacing=2, expand=True),
                            ft.Column([
                                ft.Text(f"{active_count}/{total_count} active", size=12,
                                        color=ft.Colors.GREEN_400 if active_count > 0 else ft.Colors.RED_400),
                                ft.Text(f"{device_count} device(s)", size=11, color=ft.Colors.GREY_500),
                            ], spacing=2, horizontal_alignment=ft.CrossAxisAlignment.END),
                        ], spacing=12),
                        ft.Container(height=8),
                        ft.Row(license_chips, spacing=6, wrap=True),
                        ft.Container(height=4),
                        ft.Row(device_chips, spacing=6, wrap=True),
                    ], spacing=4),
                    width=750, padding=16,
                )
                customers_container.controls.append(customer_card)
                customers_container.controls.append(ft.Container(height=8))

            self.page.update()

        self._content_area.controls.extend([
            ft.Container(height=10),
            ft.Text("Customers", size=22, weight=ft.FontWeight.BOLD),
            ft.Container(height=15),
            ft.Row([
                search_field,
                ft.FilledButton(
                    "Search", icon=ft.Icons.SEARCH,
                    on_click=lambda e: refresh_customers(),
                    style=ft.ButtonStyle(bgcolor=self.ACCENT, color=self.BG),
                    height=42,
                ),
                ft.TextButton(
                    "Refresh", icon=ft.Icons.REFRESH,
                    on_click=lambda e: refresh_customers(),
                ),
            ], spacing=10),
            ft.Container(height=15),
            customers_container,
        ])

        refresh_customers()


# ────────────────────────────────────────────────────────────────────
#  Entry
# ────────────────────────────────────────────────────────────────────
def main(page: ft.Page):
    LicenseManagerApp(page)


if __name__ == "__main__":
    import socket

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
