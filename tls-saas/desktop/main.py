"""
TLS Appointment Checker - Main Application
License-based desktop app - enter license key to activate monitoring
"""
import flet as ft
import sys
from auth_service import auth_service  # kept for encrypt/decrypt only
from checker_service import TLSCheckerService
from database import init_db, SessionLocal, UserSettings, CheckHistory
from license_service import (
    get_license_status, activate_license, activate_trial,
    get_hardware_id, PLANS, can_check, increment_check_count,
    deactivate_license,
)
from config import Config
from datetime import datetime, timedelta, timezone
import os
import glob
import base64
import socket
import asyncio
import queue
import json
import urllib.request
import urllib.error
import threading
import webbrowser
import pyperclip

# Single instance check
if sys.platform == "win32":
    try:
        import win32event
        import win32api
        import winerror
    except ImportError:
        pass  # pywin32 not installed

# App version
VERSION = "2.0.0"

# Update check URL — fetched from backend /api/app/version
UPDATE_CHECK_URL = f"{Config.BACKEND_URL}/api/app/version"

# Fixed single-user ID for all DB operations (desktop app, no auth)
USER_ID = 1


def _load_image_data_url(relative_path: str) -> str | None:
    """Load a local image and return a data-URL for ft.Image(src=...)."""
    try:
        if getattr(sys, 'frozen', False):
            app_dir = sys._MEIPASS
        else:
            app_dir = os.path.dirname(os.path.abspath(__file__))
        file_path = os.path.join(app_dir, relative_path)
        with open(file_path, "rb") as f:
            b64 = base64.b64encode(f.read()).decode("utf-8")
        return f"data:image/png;base64,{b64}"
    except Exception:
        return None


def check_for_updates(callback):
    """
    Check for app updates in background thread.
    Fetches version.json from remote URL and compares with current VERSION.
    Calls callback(new_version, download_url) if update available.
    """
    def _check():
        try:
            req = urllib.request.Request(
                UPDATE_CHECK_URL,
                headers={'User-Agent': 'TLSAppointmentChecker'}
            )
            with urllib.request.urlopen(req, timeout=5) as response:
                data = json.loads(response.read().decode('utf-8'))
                remote_version = data.get('version', '0.0.0')
                download_url = data.get('download_url', '')
                
                # Simple version comparison (assumes X.Y.Z format)
                def version_tuple(v):
                    return tuple(map(int, v.split('.')))
                
                if version_tuple(remote_version) > version_tuple(VERSION):
                    callback(remote_version, download_url)
        except (urllib.error.URLError, json.JSONDecodeError, ValueError, KeyError,
                TimeoutError, OSError, ConnectionError):
            # Silently fail - don't block app startup
            pass
    
    thread = threading.Thread(target=_check, daemon=True)
    thread.start()


class TLSApp:
    def __init__(self, page: ft.Page):
        # Check for single instance
        self.mutex = None
        self.lock_file = None
        if not self.ensure_single_instance(page):
            return
            
        self.page = page
        self.checker = None
        self.status_text = None
        self.countdown_text = None
        self._ui_queue = queue.Queue()
        self._log_history = []  # Persist log messages across page rebuilds
        self._developer_mode = False  # Hidden developer mode (Ctrl+Shift+D)
        self._cloud_monitoring = False   # True when using cloud/server-based monitoring
        self._cloud_poll_active = False  # Polling flag for cloud status

        # Config data used when saving settings
        self.flow_data = {
            'tls_email': '',
            'tls_password': '',
            'branch': '',
            'branch_url': '',
            'check_interval': 60,
            'notification_email': '',
            'service_type': 'legalization',
        }

        # ---- Page chrome ----
        self.page.title = Config.APP_NAME
        self.page.window.width = 1400
        self.page.window.height = 1150
        self.page.window.min_width = 990
        self.page.window.min_height = 750
        self.page.window.resizable = True
        self.page.window.maximizable = True
        self.page.window.maximized = False
        self.page.window.full_screen = False
        self.page.padding = 0
        self.page.window.always_on_top = False
        self.page.window.prevent_close = False
        self.page.bgcolor = "#0A0E27"
        self.page.theme_mode = ft.ThemeMode.DARK
        self.page.vertical_alignment = ft.MainAxisAlignment.START
        
        # Keep title bar and controls visible - no custom window background
        self.page.window.title_bar_hidden = False
        self.page.window.title_bar_buttons_hidden = False

        # Set custom window icon (taskbar / title bar)
        try:
            if getattr(sys, 'frozen', False):
                _icon_dir = sys._MEIPASS
            else:
                _icon_dir = os.path.dirname(os.path.abspath(__file__))
            # Try white icon first, fallback to black
            _icon_path = os.path.join(_icon_dir, "Logos", "icon_WHITE.ico")
            if not os.path.exists(_icon_path):
                _icon_path = os.path.join(_icon_dir, "Logos", "icon_BLACK.ico")
            if os.path.exists(_icon_path):
                self.page.window.icon = _icon_path
        except Exception:
            pass

        self._logo_src = _load_image_data_url(os.path.join("Logos", "LOGO_H_W.png"))

        self.page.fonts = {
            "Montserrat": "https://fonts.googleapis.com/css2?family=Montserrat:wght@300;400;500;600;700;800&display=swap"
        }
        self.page.theme = ft.Theme(
            color_scheme_seed="#00D9FF",
            font_family="Montserrat",
        )

        self.page.window.maximized = False
        self.page.window.full_screen = False
        try:
            import ctypes
            user32 = ctypes.windll.user32
            user32.SetProcessDPIAware()
            screen_width = user32.GetSystemMetrics(0)
            screen_height = user32.GetSystemMetrics(1)
            self.page.window.left = (screen_width - 1400) // 2
            self.page.window.top = max(0, (screen_height - 1050) // 2)
        except Exception:
            try:
                import tkinter as tk
                root = tk.Tk()
                root.withdraw()
                screen_width = root.winfo_screenwidth()
                screen_height = root.winfo_screenheight()
                root.destroy()
                self.page.window.left = (screen_width - 1400) // 2
                self.page.window.top = max(0, (screen_height - 1050) // 2)
            except Exception:
                self.page.window.left = 100
                self.page.window.top = 50
        self.page.update()

        # Register window event handler for cleanup
        self.page.window.on_event = self.on_window_event

        # Register keyboard event handler for developer mode (Ctrl+Shift+D)
        self.page.on_keyboard_event = self.on_keyboard_event

        # ---- Init ----
        init_db()
        self._ensure_default_settings()

        # Start UI-update loop (thread-safe queue → main thread)
        self.page.run_task(self._ui_update_loop)

        # Check for updates in background
        check_for_updates(self._on_update_available)

        # Route based on license status
        self.check_license_and_route()

    # ------------------------------------------------------------------
    # helpers
    # ------------------------------------------------------------------
    def create_website_icon_button(self):
        """Create a reusable website icon button"""
        def open_website(e):
            webbrowser.open("https://tls-saas.vercel.app")
        
        return ft.IconButton(
            icon=ft.Icons.LANGUAGE,
            icon_color="#00D9FF",
            icon_size=24,
            tooltip="Visit Website",
            on_click=open_website,
        )
    
    def ensure_single_instance(self, page: ft.Page):
        """
        Ensures only one instance of the application can run at a time.
        Returns True if this is the only instance, False if another instance exists.
        Uses Windows mutex or Unix file lock depending on platform.
        """
        if sys.platform == "win32":
            # Windows: Use named mutex
            try:
                self.mutex = win32event.CreateMutex(None, True, "Global\\TLSAppointmentChecker_Mutex")
                last_error = win32api.GetLastError()
                if last_error == winerror.ERROR_ALREADY_EXISTS:
                    # Another instance is running - show dialog and keep window open
                    print("[INFO] Another instance is already running")
                    
                    # Configure page minimally for the error dialog
                    page.title = "TLS Appointment Checker"
                    page.bgcolor = "#0A0E27"
                    page.theme_mode = ft.ThemeMode.DARK
                    page.window.width = 500
                    page.window.height = 320
                    page.window.resizable = False
                    page.vertical_alignment = ft.MainAxisAlignment.CENTER
                    page.horizontal_alignment = ft.CrossAxisAlignment.CENTER
                    
                    # Center the small error window on screen
                    try:
                        import ctypes
                        user32 = ctypes.windll.user32
                        user32.SetProcessDPIAware()
                        sw = user32.GetSystemMetrics(0)
                        sh = user32.GetSystemMetrics(1)
                        page.window.left = (sw - 500) // 2
                        page.window.top = (sh - 320) // 2
                    except Exception:
                        pass
                    
                    def close_app(e):
                        page.window.destroy()
                    
                    page.add(
                        ft.Container(
                            content=ft.Column(
                                [
                                    ft.Icon(ft.Icons.ERROR_OUTLINE, color="#FF6B6B", size=48),
                                    ft.Container(height=10),
                                    ft.Text("App Already Running", size=24, weight=ft.FontWeight.BOLD),
                                    ft.Container(height=12),
                                    ft.Text(
                                        "TLS Appointment Checker is already running.",
                                        size=15,
                                        color="#CCCCCC",
                                        text_align=ft.TextAlign.CENTER,
                                    ),
                                    ft.Text(
                                        "Only one instance can run at a time.",
                                        size=13,
                                        color=ft.Colors.GREY_500,
                                        text_align=ft.TextAlign.CENTER,
                                    ),
                                    ft.Container(height=20),
                                    ft.FilledButton("OK", on_click=close_app, width=160, height=42,
                                                    style=ft.ButtonStyle(bgcolor="#00D9FF", color="#0A0E27",
                                                                         shape=ft.RoundedRectangleBorder(radius=10))),
                                ],
                                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                                alignment=ft.MainAxisAlignment.CENTER,
                                spacing=4,
                            ),
                            padding=30,
                        )
                    )
                    page.update()
                    return False
            except Exception as e:
                print(f"Error creating mutex: {e}")
                return True  # Allow app to continue if mutex creation fails
        else:
            # Unix/Linux/Mac: Use file lock
            try:
                import fcntl
                self.lock_file = open("/tmp/tls_checker.lock", "w")
                fcntl.flock(self.lock_file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            except (IOError, BlockingIOError):
                # Lock file is already locked by another instance
                print("[INFO] Another instance is already running")
                
                page.title = "TLS Appointment Checker"
                page.bgcolor = "#0A0E27"
                page.theme_mode = ft.ThemeMode.DARK
                page.window.width = 500
                page.window.height = 320
                page.window.resizable = False
                page.vertical_alignment = ft.MainAxisAlignment.CENTER
                page.horizontal_alignment = ft.CrossAxisAlignment.CENTER
                
                def close_app(e):
                    page.window.destroy()
                
                page.add(
                    ft.Container(
                        content=ft.Column(
                            [
                                ft.Icon(ft.Icons.ERROR_OUTLINE, color="#FF6B6B", size=48),
                                ft.Container(height=10),
                                ft.Text("App Already Running", size=24, weight=ft.FontWeight.BOLD),
                                ft.Container(height=12),
                                ft.Text(
                                    "TLS Appointment Checker is already running.",
                                    size=15,
                                    color="#CCCCCC",
                                    text_align=ft.TextAlign.CENTER,
                                ),
                                ft.Text(
                                    "Only one instance can run at a time.",
                                    size=13,
                                    color=ft.Colors.GREY_500,
                                    text_align=ft.TextAlign.CENTER,
                                ),
                                ft.Container(height=20),
                                ft.FilledButton("OK", on_click=close_app, width=160, height=42,
                                                style=ft.ButtonStyle(bgcolor="#00D9FF", color="#0A0E27",
                                                                     shape=ft.RoundedRectangleBorder(radius=10))),
                            ],
                            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                            alignment=ft.MainAxisAlignment.CENTER,
                            spacing=4,
                        ),
                        padding=30,
                    )
                )
                page.update()
                return False
            except Exception as e:
                print(f"Error creating file lock: {e}")
                return True  # Allow app to continue if lock creation fails
        
        return True

    def on_window_event(self, e):
        """Handle window events - cleanup mutex/lock on close."""
        if e.data == "close":
            # Clean up single instance lock
            if sys.platform == "win32":
                if self.mutex:
                    try:
                        win32api.CloseHandle(self.mutex)
                    except Exception:
                        pass
            else:
                if hasattr(self, 'lock_file'):
                    try:
                        import fcntl
                        fcntl.flock(self.lock_file.fileno(), fcntl.LOCK_UN)
                        self.lock_file.close()
                    except Exception:
                        pass

    def on_keyboard_event(self, e: ft.KeyboardEvent):
        """Handle keyboard events - Ctrl+Shift+D toggles developer mode."""
        if e.key == "D" and e.ctrl and e.shift:
            self._developer_mode = not self._developer_mode
            status = "enabled" if self._developer_mode else "disabled"
            if self.page:
                self.page.snack_bar = ft.SnackBar(ft.Text(f"Developer mode {status}"), open=True)
                self.page.update()
                # Rebuild monitoring page to show/hide developer controls
                self.show_monitoring_page()

    def _ensure_default_settings(self):
        """Make sure a UserSettings row exists for USER_ID."""
        db = SessionLocal()
        try:
            settings = db.query(UserSettings).filter(UserSettings.user_id == USER_ID).first()
            if not settings:
                settings = UserSettings(
                    user_id=USER_ID,
                    enable_email_notifications=True,
                    enable_windows_notifications=True,
                    headless_mode=True,
                    branch="Sheikh Zayed",
                    branch_url="https://legalization-de.tlscontact.com/service/eg/egCAI2de/home",
                    service_type="legalization",
                )
                db.add(settings)
                db.commit()
        finally:
            db.close()

    def _on_update_available(self, new_version: str, download_url: str):
        """Called when a new version is available. Shows update dialog."""
        def show_dialog():
            def close_dlg(e):
                update_dlg.open = False
                self.page.update()

            def open_download(e):
                self.page.launch_url(download_url)
                close_dlg(e)

            update_dlg = ft.AlertDialog(
                modal=True,
                title=ft.Row([
                    ft.Icon(ft.Icons.SYSTEM_UPDATE, color="#00D9FF", size=28),
                    ft.Text("Update Available", size=20, weight=ft.FontWeight.BOLD)
                ]),
                content=ft.Column([
                    ft.Text(
                        f"A new version ({new_version}) is available!",
                        size=16,
                        color="#FFFFFF"
                    ),
                    ft.Text(
                        f"Current version: {VERSION}",
                        size=14,
                        color="#888888"
                    ),
                    ft.Divider(height=20, color="transparent"),
                    ft.Text(
                        "Download the latest version to get new features and fixes.",
                        size=14,
                        color="#CCCCCC"
                    ),
                ], tight=True, spacing=8),
                actions=[
                    ft.TextButton("Later", on_click=close_dlg),
                    ft.ElevatedButton(
                        "Download",
                        icon=ft.Icons.DOWNLOAD,
                        on_click=open_download,
                        bgcolor="#00D9FF",
                        color="#0A0E27"
                    ),
                ],
                actions_alignment=ft.MainAxisAlignment.END,
            )
            self.page.overlay.append(update_dlg)
            update_dlg.open = True
            self.page.update()

        # Run on main thread
        try:
            self.page.run_task(lambda: show_dialog())
        except Exception:
            pass

    async def _enforce_window_size(self):
        """Ensure the window opens at configured size."""
        await asyncio.sleep(0.05)
        self.page.window.maximized = False
        self.page.window.full_screen = False
        self.page.window.width = 1400
        self.page.window.height = 1150
        self.page.window.min_width = 1000
        self.page.window.min_height = 750
        self.page.window.maximizable = True
        try:
            import ctypes
            user32 = ctypes.windll.user32
            user32.SetProcessDPIAware()
            sw = user32.GetSystemMetrics(0)
            sh = user32.GetSystemMetrics(1)
            self.page.window.left = (sw - 1400) // 2
            self.page.window.top = max(0, (sh - 1050) // 2)
        except Exception:
            try:
                import tkinter as tk
                root = tk.Tk()
                root.withdraw()
                sw = root.winfo_screenwidth()
                sh = root.winfo_screenheight()
                root.destroy()
                self.page.window.left = (sw - 1400) // 2
                self.page.window.top = max(0, (sh - 1050) // 2)
            except Exception:
                self.page.window.left = 100
                self.page.window.top = 50
        try:
            self.page.update()
        except Exception:
            pass

    def check_license_and_route(self):
        """Decide which page to show based on offline license."""
        status = get_license_status()
        if status and status.get('valid'):
            # Block premium plans from using the desktop app
            if status.get('plan', '').startswith('premium'):
                from license_service import deactivate_license
                deactivate_license()
                self.show_activation_page(
                    message="Premium plans are managed via the web dashboard.\n"
                            "Please visit the website to use your Premium subscription."
                )
            else:
                self.show_monitoring_page()
        else:
            self.show_activation_page()

    def _save_service_type_to_db(self):
        """Persist the selected service_type from flow_data into the DB."""
        svc = self.flow_data.get('service_type', 'legalization') or 'legalization'
        db = SessionLocal()
        try:
            settings = db.query(UserSettings).filter(UserSettings.user_id == USER_ID).first()
            if settings:
                settings.service_type = svc
                # Also set appropriate default branch/URL for the chosen service
                if svc == 'visa':
                    if not settings.branch or settings.branch not in Config.VISA_BRANCHES:
                        settings.branch = "El-Sheikh Zayed"
                        settings.branch_url = Config.VISA_BRANCHES["El-Sheikh Zayed"]
                else:
                    if not settings.branch or settings.branch not in Config.LEGALIZATION_BRANCHES:
                        settings.branch = "Sheikh Zayed"
                        settings.branch_url = Config.LEGALIZATION_BRANCHES["Sheikh Zayed"]
                db.commit()
        finally:
            db.close()

    def create_glass_container(self, content, width=None, height=None, padding=30, gradient=True):
        """Reusable glassy card component."""
        if gradient:
            return ft.Container(
                content=content,
                width=width,
                height=height,
                padding=padding,
                border_radius=24,
                gradient=ft.LinearGradient(
                    begin=ft.alignment.Alignment(-1, -1),
                    end=ft.alignment.Alignment(1, 1),
                    colors=["#1A1F3A", "#0F1525"],
                ),
                border=ft.Border.all(1, ft.Colors.with_opacity(0.3, "#00D9FF")),
                shadow=ft.BoxShadow(
                    spread_radius=0,
                    blur_radius=20,
                    color=ft.Colors.with_opacity(0.2, "#00D9FF"),
                    offset=ft.Offset(0, 4),
                ),
            )
        else:
            return ft.Container(
                content=content,
                width=width,
                height=height,
                padding=padding,
                border_radius=24,
                bgcolor="#1A1F3A",
                border=ft.Border.all(1, ft.Colors.with_opacity(0.3, "#00D9FF")),
                shadow=ft.BoxShadow(
                    spread_radius=0,
                    blur_radius=20,
                    color=ft.Colors.with_opacity(0.2, "#00D9FF"),
                    offset=ft.Offset(0, 4),
                ),
            )

    def _create_log_entry(self, message: str, timestamp: str) -> ft.Container:
        """Create a styled log entry widget."""
        if "\u2705" in message or "SUCCESS" in message.upper() or "AVAILABLE" in message.upper():
            icon = ft.Icons.CHECK_CIRCLE
            icon_color = ft.Colors.GREEN_400
            bg_color = ft.Colors.with_opacity(0.1, ft.Colors.GREEN)
        elif "\u274c" in message or "ERROR" in message.upper() or "FAILED" in message.upper():
            icon = ft.Icons.ERROR
            icon_color = ft.Colors.RED_400
            bg_color = ft.Colors.with_opacity(0.1, ft.Colors.RED)
        elif "\u26a0\ufe0f" in message or "WARNING" in message.upper():
            icon = ft.Icons.WARNING
            icon_color = ft.Colors.ORANGE_400
            bg_color = ft.Colors.with_opacity(0.1, ft.Colors.ORANGE)
        elif "\u2139\ufe0f" in message or message.startswith("Checking"):
            icon = ft.Icons.INFO
            icon_color = "#00D9FF"
            bg_color = ft.Colors.with_opacity(0.05, ft.Colors.BLUE)
        else:
            icon = ft.Icons.CIRCLE
            icon_color = ft.Colors.GREY_400
            bg_color = ft.Colors.with_opacity(0.03, ft.Colors.WHITE)

        return ft.Container(
            content=ft.Row(
                [
                    ft.Icon(icon, size=14, color=icon_color),
                    ft.Column(
                        [
                            ft.Text(message, size=11, color=ft.Colors.WHITE),
                            ft.Text(timestamp, size=9, color=ft.Colors.GREY_500),
                        ],
                        spacing=2, expand=True,
                    ),
                ],
                spacing=8,
            ),
            padding=8, border_radius=8,
            bgcolor=bg_color,
            border=ft.Border.all(1, ft.Colors.with_opacity(0.1, icon_color)),
        )

    # ==================================================================
    #  CLOUD MONITORING HELPERS
    # ==================================================================
    def _is_premium_plan(self) -> bool:
        """Check if the current license is a premium plan (server monitoring eligible)."""
        try:
            status = get_license_status()
            if status and status.get('valid'):
                plan = status.get('plan', '')
                return plan.startswith('premium')
        except Exception:
            pass
        return False

    def _try_cloud_start(self, settings) -> bool:
        """Try to start cloud monitoring on the server.
        Returns True if cloud monitoring was started, False to fall back to local.
        Only premium plans are eligible for server-side monitoring."""

        # Gate: only premium plans get server monitoring
        if not self._is_premium_plan():
            self.update_status_log("ℹ️ Local monitoring active — keep your PC on while checking.")
            return False

        server_url = Config.LICENSE_SERVER_URL
        if not server_url:
            self.update_status_log("ℹ️ Server URL not configured — starting local monitoring. Keep your PC on.")
            return False
        try:
            license_status = get_license_status()
            license_key = license_status.get('key', '') if license_status else ''
            hw_id = get_hardware_id()
            tls_password = auth_service.decrypt_password(settings.tls_password)

            payload = json.dumps({
                "license_key": license_key,
                "hardware_id": hw_id,
                "tls_email": settings.tls_email,
                "tls_password": tls_password,
                "service_type": settings.service_type or 'legalization',
                "branch": settings.branch or 'Sheikh Zayed',
                "branch_url": settings.branch_url or '',
                "notification_email": settings.notification_email,
                "check_interval": settings.check_interval or 60,
            }).encode()

            req = urllib.request.Request(
                f"{server_url.rstrip('/')}/api/monitoring/start",
                data=payload,
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=10) as resp:
                result = json.loads(resp.read())
                if result.get("success"):
                    self._cloud_monitoring = True
                    self.update_status_log("☁️ Cloud monitoring started!")
                    self.update_status_log("ℹ️ Your PC does NOT need to stay on — the server handles checking.")
                    self.update_status_log("ℹ️ You'll receive an email notification when appointments are found.")
                    # Start polling for status
                    self._start_cloud_polling()
                    return True
                else:
                    self.update_status_log(f"⚠️ Server: {result.get('error', 'Unknown error')}")
                    self.update_status_log("ℹ️ Starting local monitoring instead. Keep your PC on.")
                    return False
        except urllib.error.HTTPError as e:
            body = e.read().decode(errors='ignore')[:200]
            self.update_status_log(f"⚠️ Server HTTP {e.code} — could not start cloud monitoring")
            self.update_status_log("ℹ️ Starting local monitoring instead. Keep your PC on.")
            return False
        except urllib.error.URLError as e:
            self.update_status_log("ℹ️ Server unavailable — starting local monitoring. Keep your PC on.")
            return False
        except Exception as e:
            self.update_status_log(f"ℹ️ Server unavailable ({type(e).__name__}) — starting local monitoring. Keep your PC on.")
            return False

    def _try_cloud_stop(self) -> bool:
        """Try to stop cloud monitoring on the server."""
        server_url = Config.LICENSE_SERVER_URL
        if not server_url:
            return False
        try:
            hw_id = get_hardware_id()
            payload = json.dumps({"hardware_id": hw_id}).encode()
            req = urllib.request.Request(
                f"{server_url.rstrip('/')}/api/monitoring/stop",
                data=payload,
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=10) as resp:
                result = json.loads(resp.read())
                if result.get("success"):
                    self._cloud_monitoring = False
                    self._stop_cloud_polling()
                    self.update_status_log("☁️ Cloud monitoring stopped")
                    return True
        except Exception:
            pass
        return False

    def _start_cloud_polling(self):
        """Poll the server for cloud monitoring status/logs."""
        self._cloud_poll_active = True
        def _poll():
            while getattr(self, '_cloud_poll_active', False):
                try:
                    server_url = Config.LICENSE_SERVER_URL
                    if not server_url:
                        break
                    hw_id = get_hardware_id()
                    payload = json.dumps({"hardware_id": hw_id}).encode()
                    req = urllib.request.Request(
                        f"{server_url.rstrip('/')}/api/monitoring/status",
                        data=payload,
                        headers={"Content-Type": "application/json"},
                        method="POST",
                    )
                    with urllib.request.urlopen(req, timeout=10) as resp:
                        result = json.loads(resp.read())
                        if not result.get("active"):
                            self.update_status_log("☁️ Cloud monitoring has stopped")
                            self._cloud_poll_active = False
                            break
                        # Show recent logs
                        logs = result.get("logs", [])
                        for log_entry in logs[-5:]:
                            msg = log_entry.get("message", "")
                            if msg and not any(msg == h[0] for h in self._log_history[-10:]):
                                self.update_status_log(f"☁️ {msg}")
                except Exception:
                    pass
                # Poll every 30 seconds
                for _ in range(60):
                    if not getattr(self, '_cloud_poll_active', False):
                        return
                    import time; time.sleep(0.5)
        threading.Thread(target=_poll, daemon=True).start()

    def _stop_cloud_polling(self):
        self._cloud_poll_active = False

    # ==================================================================
    #  LICENSE ACTIVATION PAGE
    # ==================================================================
    def _start_trial_from_activation(self, status_msg):
        """Start free trial from the activation page."""
        success, message = activate_trial()
        if success:
            self._save_service_type_to_db()
            self.show_monitoring_page()
        else:
            status_msg.value = message
            status_msg.color = ft.Colors.RED_400
            self.page.update()

    def show_activation_page(self, message: str = None):
        self.page.controls.clear()
        self.page.scroll = None

        hw_id = get_hardware_id()

        key_field = ft.TextField(
            label="License Key",
            width=500,
            border_radius=12,
            prefix_icon=ft.Icons.VPN_KEY,
            bgcolor=ft.Colors.with_opacity(0.05, ft.Colors.WHITE),
            border_color=ft.Colors.with_opacity(0.3, ft.Colors.WHITE),
            hint_text="e.g. LEGALIZATION_MONTHLY-1A2B3C4D-ABCD1234-SIG12345",
            capitalization=ft.TextCapitalization.CHARACTERS,
        )

        _initial_msg = message or ""
        _initial_color = ft.Colors.ORANGE_400 if message else ft.Colors.WHITE
        status_msg = ft.Text(_initial_msg, size=14, text_align=ft.TextAlign.CENTER, color=_initial_color)

        def do_activate(e):
            if not key_field.value or not key_field.value.strip():
                status_msg.value = "Please enter a license key"
                status_msg.color = ft.Colors.RED_400
                self.page.update()
                return

            entered_key = key_field.value.strip().upper()

            # Reject premium licenses — premium users should use the website dashboard
            if entered_key.startswith("PREMIUM"):
                status_msg.value = (
                    "Premium plans are managed via the web dashboard.\n"
                    "Please visit the website to use your Premium subscription."
                )
                status_msg.color = ft.Colors.ORANGE_400
                self.page.update()
                return

            success, message = activate_license(entered_key)
            if success:
                # Double-check plan in case key was parsed as premium
                lic = get_license_status()
                if lic and lic.get('plan', '').startswith('premium'):
                    # Deactivate it and tell the user
                    from license_service import deactivate_license
                    deactivate_license()
                    status_msg.value = (
                        "Premium plans are managed via the web dashboard.\n"
                        "Please visit the website to use your Premium subscription."
                    )
                    status_msg.color = ft.Colors.ORANGE_400
                    self.page.update()
                    return
                # Save the selected service type to DB
                self._save_service_type_to_db()
                self.show_monitoring_page()
            else:
                status_msg.value = message
                status_msg.color = ft.Colors.RED_400
                self.page.update()

        def open_website(e):
            webbrowser.open(Config.WEBSITE_URL)

        # Add website icon button at top
        top_bar = ft.Container(
            content=ft.Row([
                ft.TextButton(
                    "🌐 Get a License on Website",
                    on_click=open_website,
                    style=ft.ButtonStyle(color="#00D9FF"),
                ),
                ft.Container(expand=True),
                self.create_website_icon_button(),
            ]),
            padding=ft.Padding(left=20, right=20, top=15, bottom=0),
        )

        def copy_device_id(e):
            try:
                import pyperclip
                pyperclip.copy(hw_id)
                copy_btn.text = "Copied!"
                copy_btn.style = ft.ButtonStyle(color=ft.Colors.GREEN_400)
            except ImportError:
                # Fallback to Flet's clipboard if pyperclip not available
                try:
                    self.page.set_clipboard(hw_id)
                    copy_btn.text = "Copied!"
                    copy_btn.style = ft.ButtonStyle(color=ft.Colors.GREEN_400)
                except Exception as ex:
                    copy_btn.text = "Ctrl+C to copy"
                    copy_btn.style = ft.ButtonStyle(color=ft.Colors.ORANGE_400)
            except Exception as ex:
                copy_btn.text = "Ctrl+C to copy"
                copy_btn.style = ft.ButtonStyle(color=ft.Colors.ORANGE_400)
            self.page.update()

        copy_btn = ft.TextButton(
            "Copy",
            on_click=copy_device_id,
            style=ft.ButtonStyle(color="#00D9FF"),
        )

        activation_card = self.create_glass_container(
            ft.Column(
                [
                    ft.Icon(ft.Icons.VPN_KEY, size=60, color="#00D9FF"),
                    ft.Container(height=20),
                    ft.Text("Activate License", size=24, weight=ft.FontWeight.BOLD, text_align=ft.TextAlign.CENTER),
                    ft.Container(height=25),

                    # Device ID box
                    ft.Container(
                        content=ft.Column(
                            [
                                ft.Text("Your Device ID", size=12, color=ft.Colors.GREY_400),
                                ft.Container(height=5),
                                ft.Row(
                                    [
                                        ft.Text(
                                            hw_id,
                                            size=14, weight=ft.FontWeight.BOLD,
                                            color="#00D9FF", selectable=True,
                                            font_family="Courier New",
                                        ),
                                        copy_btn,
                                    ],
                                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                                ),
                            ],
                        ),
                        padding=15,
                        border_radius=12,
                        bgcolor=ft.Colors.with_opacity(0.05, ft.Colors.WHITE),
                        border=ft.Border.all(1, ft.Colors.with_opacity(0.2, "#00D9FF")),
                        width=500,
                    ),
                    ft.Container(height=20),

                    # Instructions
                    ft.Container(
                        content=ft.Column(
                            [
                                ft.Text("How to get a license:", size=13, weight=ft.FontWeight.BOLD, color=ft.Colors.GREY_300),
                                ft.Container(height=5),
                                ft.Text("1. Visit our website and create an account", size=12, color=ft.Colors.GREY_400),
                                ft.Text("2. Choose a plan and complete payment", size=12, color=ft.Colors.GREY_400),
                                ft.Text("3. Copy your Device ID above and enter it during checkout", size=12, color=ft.Colors.GREY_400),
                                ft.Text("4. Your license key will be emailed to you", size=12, color=ft.Colors.GREY_400),
                            ],
                        ),
                        padding=15,
                        border_radius=12,
                        bgcolor=ft.Colors.with_opacity(0.03, ft.Colors.WHITE),
                        width=500,
                    ),
                    ft.Container(height=25),

                    # Key input
                    key_field,
                    ft.Container(height=20),

                    ft.FilledButton(
                        "Activate License",
                        width=500,
                        height=50,
                        on_click=do_activate,
                        style=ft.ButtonStyle(
                            bgcolor="#00D9FF",
                            color="#0A0E27",
                            shape=ft.RoundedRectangleBorder(radius=12),
                        ),
                    ),
                    ft.Container(height=10),
                    # Free trial button
                    ft.OutlinedButton(
                        content=ft.Row([
                            ft.Icon(ft.Icons.ROCKET_LAUNCH, size=18),
                            ft.Text("Start Free Trial", size=14),
                        ], alignment=ft.MainAxisAlignment.CENTER, spacing=8),
                        width=500,
                        height=45,
                        on_click=lambda e: self._start_trial_from_activation(status_msg),
                        style=ft.ButtonStyle(
                            color=ft.Colors.GREEN_400,
                            side=ft.BorderSide(1, ft.Colors.GREEN_600),
                            shape=ft.RoundedRectangleBorder(radius=12),
                        ),
                    ),
                    ft.Container(height=15),
                    status_msg,
                    ft.Container(height=10),
                    ft.TextButton(
                        "🌐 Visit Website",
                        on_click=open_website,
                        style=ft.ButtonStyle(color="#00D9FF"),
                    ),
                    ft.Container(height=8),
                    ft.Text(
                        f"Version {VERSION}",
                        size=11, color=ft.Colors.GREY_600,
                        text_align=ft.TextAlign.CENTER,
                    ),
                ],
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                spacing=0,
            ),
            width=600,
        )

        self.page.add(
            ft.Container(
                content=ft.Column(
                    [
                        top_bar,
                        ft.Container(height=10),
                        activation_card,
                    ],
                    horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                    alignment=ft.MainAxisAlignment.CENTER,
                    scroll=ft.ScrollMode.AUTO,
                    expand=True,
                ),
                expand=True,
            )
        )
        self.page.update()

    # ==================================================================
    #  SAVE SETTINGS
    # ==================================================================
    def save_settings(self):
        """Save settings to database using fixed USER_ID."""
        db = SessionLocal()
        try:
            settings = db.query(UserSettings).filter(UserSettings.user_id == USER_ID).first()

            tls_email = (self.flow_data.get('tls_email') or "").strip()
            raw_password = (self.flow_data.get('tls_password') or "").strip()
            encrypted_password = auth_service.encrypt_password(raw_password) if raw_password else None
            service_type_value = self.flow_data.get('service_type') or (getattr(settings, 'service_type', 'legalization') if settings else 'legalization') or 'legalization'
            branch_value = self.flow_data.get('branch') or (settings.branch if settings else ("El-Sheikh Zayed" if service_type_value == 'visa' else "Sheikh Zayed"))
            # Resolve branch_url from config maps
            if service_type_value == 'visa':
                default_url = Config.VISA_BRANCHES.get(branch_value, list(Config.VISA_BRANCHES.values())[0])
            else:
                default_url = Config.LEGALIZATION_BRANCHES.get(branch_value, list(Config.LEGALIZATION_BRANCHES.values())[0])
            branch_url_value = self.flow_data.get('branch_url') or (settings.branch_url if settings else default_url)
            check_interval_value = self.flow_data.get('check_interval', 120)
            notification_email_value = self.flow_data.get('notification_email') or (settings.notification_email if settings else "")

            if not settings:
                settings = UserSettings(
                    user_id=USER_ID,
                    tls_email=tls_email,
                    tls_password=encrypted_password or "",
                    check_interval=check_interval_value,
                    notification_email=notification_email_value,
                    enable_email_notifications=True,
                    enable_windows_notifications=True,
                    headless_mode=True,
                    branch=branch_value,
                    branch_url=branch_url_value,
                    service_type=service_type_value,
                )
                db.add(settings)
            else:
                if tls_email:
                    settings.tls_email = tls_email
                if encrypted_password:
                    settings.tls_password = encrypted_password
                settings.check_interval = check_interval_value
                settings.notification_email = notification_email_value
                settings.branch = branch_value
                settings.branch_url = branch_url_value
                settings.service_type = service_type_value

            db.commit()
        finally:
            db.close()

    # ==================================================================
    #  MONITORING PAGE
    # ==================================================================
    def show_monitoring_page(self, auto_start=False):
        self.page.controls.clear()
        self.page.scroll = None

        # Current license info (API first, then offline)
        license_status = get_license_status()

        # Init checker
        if not self.checker:
            self.checker = TLSCheckerService(
                user_id=USER_ID,
                on_status_update=self.update_status_log,
                on_countdown_update=self.update_countdown,
            )

        # Detect if checker is actually still running (survives page rebuilds)
        is_monitoring = self.checker.is_running if self.checker else False

        db = SessionLocal()
        settings = db.query(UserSettings).filter(UserSettings.user_id == USER_ID).first()

        # Only reset DB flag when checker truly isn't running
        if settings and not auto_start and not is_monitoring:
            settings.is_monitoring = False
            db.commit()

        total_checks = settings.total_checks if settings else 0
        if settings and settings.last_check_at:
            last_check_time = settings.last_check_at.strftime('%H:%M')
            last_check_date = settings.last_check_at.strftime('%m/%d')
            last_check = f"{last_check_date}\n{last_check_time}"
        else:
            last_check = "Never"

        db.close()

        # ---- Status log ----
        self.status_list = ft.ListView(
            spacing=8, padding=10, auto_scroll=True, expand=True,
            scroll=ft.ScrollMode.AUTO,
        )

        initial_msg = ft.Container(
            content=ft.Row(
                [
                    ft.Icon(ft.Icons.INFO_OUTLINE, size=16, color="#00D9FF"),
                    ft.Column(
                        [
                            ft.Text("Ready to start monitoring...", size=12, color=ft.Colors.GREY_400),
                            ft.Text(datetime.now().strftime("%H:%M:%S"), size=10, color=ft.Colors.GREY_600),
                        ],
                        spacing=2, expand=True,
                    ),
                ],
                spacing=8,
            ),
            padding=10, border_radius=8,
            bgcolor=ft.Colors.with_opacity(0.05, ft.Colors.WHITE),
            border=ft.Border.all(1, ft.Colors.with_opacity(0.1, "#00D9FF")),
        )
        # Restore log history if page was rebuilt while monitoring
        if self._log_history:
            for msg, ts in self._log_history[-20:]:
                self.status_list.controls.append(self._create_log_entry(msg, ts))
        else:
            self.status_list.controls.append(initial_msg)

        self.status_text = ft.Text(
            "Ready to start monitoring...", size=12, color=ft.Colors.GREY_400,
            selectable=True, text_align=ft.TextAlign.LEFT,
        )

        status_container = ft.Container(
            content=ft.Column(
                [self.status_text],
                scroll=ft.ScrollMode.AUTO,
                spacing=5,
            ),
            padding=10,
            expand=True,
        )

        # ---- Countdown timer ----
        self.countdown_text = ft.Text("--:--", size=28, weight=ft.FontWeight.BOLD, color="#00D9FF")

        _STAT_W = 155
        _STAT_H = 140
        _STAT_PAD = 15

        countdown_card = self.create_glass_container(
            ft.Column(
                [
                    ft.Icon(ft.Icons.TIMER, size=24, color="#00D9FF"),
                    ft.Container(height=6),
                    self.countdown_text,
                    ft.Text("Next Check", size=10, color=ft.Colors.GREY_500),
                ],
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                alignment=ft.MainAxisAlignment.CENTER,
                spacing=5,
            ),
            width=_STAT_W, height=_STAT_H, padding=_STAT_PAD,
        )

        # ---- Stats cards ----
        self.checks_count_text = ft.Text(str(total_checks), size=28, weight=ft.FontWeight.BOLD)
        checks_card = self.create_glass_container(
            ft.Column(
                [
                    ft.Icon(ft.Icons.NUMBERS, size=24, color="#00D9FF"),
                    ft.Container(height=6),
                    self.checks_count_text,
                    ft.Text("Total Checks", size=10, color=ft.Colors.GREY_500),
                ],
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                alignment=ft.MainAxisAlignment.CENTER,
                spacing=5,
            ),
            width=_STAT_W, height=_STAT_H, padding=_STAT_PAD,
        )

        # ---- Checks per day card ----
        checks_today = license_status.get('checks_today', 0) if license_status and license_status.get('valid') else 0
        checks_limit = license_status.get('checks_limit', 0) if license_status and license_status.get('valid') else 0
        # Format checks today - abbreviate large limits
        if checks_limit >= 99999:
            checks_limit_str = "\u221e"  # infinity symbol
        elif checks_limit >= 10000:
            checks_limit_str = f"{checks_limit // 1000}k"
        else:
            checks_limit_str = str(checks_limit)
        self.checks_today_text = ft.Text(f"{checks_today}/{checks_limit_str}", size=28, weight=ft.FontWeight.BOLD)
        checks_day_card = self.create_glass_container(
            ft.Column(
                [
                    ft.Icon(ft.Icons.TODAY, size=24, color="#00D9FF"),
                    ft.Container(height=6),
                    self.checks_today_text,
                    ft.Text("Checks Today", size=10, color=ft.Colors.GREY_500),
                ],
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                alignment=ft.MainAxisAlignment.CENTER,
                spacing=5,
            ),
            width=_STAT_W, height=_STAT_H, padding=_STAT_PAD,
        )

        last_check_card = self.create_glass_container(
            ft.Column(
                [
                    ft.Icon(ft.Icons.ACCESS_TIME, size=24, color="#00D9FF"),
                    ft.Container(height=6),
                    ft.Text(last_check, size=20, weight=ft.FontWeight.BOLD, text_align=ft.TextAlign.CENTER),
                    ft.Text("Last Check", size=10, color=ft.Colors.GREY_500),
                ],
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                alignment=ft.MainAxisAlignment.CENTER,
                spacing=5,
            ),
            width=_STAT_W, height=_STAT_H, padding=_STAT_PAD,
        )

        # ---- Control callbacks ----
        def start_monitoring(e):
            # Check license first
            allowed, reason = can_check()
            if not allowed:
                self.update_status_log(f"⚠️ {reason}")
                return

            db = SessionLocal()
            settings = db.query(UserSettings).filter(UserSettings.user_id == USER_ID).first()

            if not settings or not settings.tls_email or not settings.tls_password:
                db.close()
                self.update_status_log("[ERROR] Please configure TLS credentials first")
                return

            if not settings.notification_email or not settings.notification_email.strip():
                db.close()
                self.update_status_log("[ERROR] Notification email is required. Please enter your email in the configuration and save.")
                return

            # Check for unsaved configuration changes
            unsaved_changes = []
            try:
                if config_service_dropdown.value and config_service_dropdown.value != (settings.service_type or 'legalization'):
                    unsaved_changes.append("Service Type")
                if config_branch_dropdown.value and config_branch_dropdown.value != (settings.branch or ''):
                    unsaved_changes.append("Branch")
                if config_interval_dropdown.value and str(config_interval_dropdown.value) != str(settings.check_interval or 60):
                    unsaved_changes.append("Check Interval")
                if config_notification_field.value is not None and config_notification_field.value.strip() != (settings.notification_email or ''):
                    unsaved_changes.append("Notification Email")
                if config_email_field.value is not None and config_email_field.value.strip() != (settings.tls_email or ''):
                    unsaved_changes.append("TLS Email")
            except Exception:
                pass  # If dropdowns haven't been created yet, skip check

            if unsaved_changes:
                db.close()
                self.update_status_log(f"⚠️ You have unsaved changes in: {', '.join(unsaved_changes)}")
                self.update_status_log("⚠️ Please click 'Save Configuration' first before starting monitoring")
                return

            first_check_done = settings.first_check_done
            settings.is_monitoring = True
            db.commit()

            # Try cloud monitoring first (server handles everything)
            if self._try_cloud_start(settings):
                db.close()
                return

            db.close()
            self.checker.start_monitoring()

        def stop_monitoring(e):
            db = SessionLocal()
            settings = db.query(UserSettings).filter(UserSettings.user_id == USER_ID).first()
            settings.is_monitoring = False
            db.commit()
            db.close()

            # Stop cloud monitoring if active
            if getattr(self, '_cloud_monitoring', False):
                self._try_cloud_stop()

            self.checker.stop_monitoring()
            if self.countdown_text:
                self.countdown_text.value = "--:--"

        def change_plan(e):
            if self.checker:
                self.checker.stop_monitoring()
            self.checker = None
            self.show_activation_page()

        def view_screenshots(e):
            self.show_screenshots_gallery()

        def toggle_headless(e):
            db = SessionLocal()
            settings = db.query(UserSettings).filter(UserSettings.user_id == USER_ID).first()
            if not settings:
                settings = UserSettings(
                    user_id=USER_ID,
                    enable_email_notifications=True,
                    enable_windows_notifications=True,
                )
                db.add(settings)
            settings.headless_mode = headless_switch.value
            db.commit()
            db.close()
            status = "background" if headless_switch.value else "visible"
            self.update_status_log(f"“ Browser will run in {status} mode")

        # Headless switch
        db = SessionLocal()
        settings = db.query(UserSettings).filter(UserSettings.user_id == USER_ID).first()
        headless_mode = settings.headless_mode if settings else True
        db.close()

        headless_switch = ft.Switch(
            value=headless_mode,
            active_color="#00D9FF",
            on_change=toggle_headless,
        )

        # ---- Inline configuration card ----
        # Determine service type from license plan (locked for paid licenses)
        license_plan = license_status.get('plan', 'trial') if license_status else 'trial'
        service_locked = False  # Whether the user can change service type
        if license_plan.startswith('visa'):
            current_service_type = 'visa'
            service_locked = True
        elif license_plan.startswith('legalization'):
            current_service_type = 'legalization'
            service_locked = True
        elif license_plan.startswith('all_in_one'):
            # Combo plan — user can switch between legalization and visa
            current_service_type = getattr(settings, 'service_type', 'legalization') if settings else 'legalization'
            service_locked = False
        else:
            # Trial — use whatever is saved in DB, allow changing
            current_service_type = getattr(settings, 'service_type', 'legalization') if settings else 'legalization'
        if not current_service_type:
            current_service_type = 'legalization'

        # Resolve branch defaults per service type
        if current_service_type == 'visa':
            default_branch = "El-Sheikh Zayed"
            branch_options_list = list(Config.VISA_BRANCHES.keys())
        else:
            default_branch = "Sheikh Zayed"
            branch_options_list = list(Config.LEGALIZATION_BRANCHES.keys())

        branch_value = settings.branch if settings and settings.branch else default_branch
        # If branch not in options (service type changed), reset to default
        if branch_value not in branch_options_list:
            branch_value = default_branch
        interval_value = str(settings.check_interval if settings else 120)
        notification_value = settings.notification_email if settings and settings.notification_email else ""

        config_email_field = ft.TextField(
            label="TLS Email",
            value=settings.tls_email if settings and settings.tls_email else "",
            width=620, border_radius=12, prefix_icon=ft.Icons.EMAIL,
        )

        config_password_field = ft.TextField(
            label="TLS Password",
            password=True, can_reveal_password=True,
            width=620, border_radius=12, prefix_icon=ft.Icons.LOCK,
            hint_text="Leave blank to keep current password",
        )

        config_branch_dropdown = ft.Dropdown(
            label="TLS Branch",
            value=branch_value,
            width=620, border_radius=12,
            options=[ft.dropdown.Option(b, b) for b in branch_options_list],
        )

        def _on_service_type_change(e):
            """Update branch dropdown when service type changes."""
            new_type = e.control.value
            if new_type == 'visa':
                new_branches = list(Config.VISA_BRANCHES.keys())
                new_default = "El-Sheikh Zayed"
            else:
                new_branches = list(Config.LEGALIZATION_BRANCHES.keys())
                new_default = "Sheikh Zayed"
            config_branch_dropdown.options = [ft.dropdown.Option(b, b) for b in new_branches]
            config_branch_dropdown.value = new_default
            self.page.update()

        config_service_dropdown = ft.Dropdown(
            label="Service Type" + (" (locked by license)" if service_locked else ""),
            value=current_service_type,
            width=620, border_radius=12,
            disabled=service_locked,
            options=[
                ft.dropdown.Option("legalization", "Document Legalization"),
                ft.dropdown.Option("visa", "Visa Process"),
            ],
        )
        if not service_locked:
            config_service_dropdown.on_change = _on_service_type_change

        # Interval options restricted by plan
        min_interval = license_status['min_interval'] if license_status and license_status.get('valid') else 120
        all_intervals = [
            ("30", "30 min"), ("45", "45 min"),
            ("60", "1 hour"), ("120", "2 hours"), ("180", "3 hours"), ("240", "4 hours"),
        ]
        interval_options = [ft.dropdown.Option(k, v) for k, v in all_intervals if int(k) >= min_interval]

        # Make sure current value is still valid
        effective_interval = interval_value if int(interval_value) >= min_interval else str(min_interval)

        config_interval_dropdown = ft.Dropdown(
            label="Check Interval",
            value=effective_interval,
            width=620, border_radius=12,
            options=interval_options,
            visible=False,  # Hidden by default, shown in developer mode
        )

        config_notification_field = ft.TextField(
            label="Notification Email",
            value=notification_value,
            width=620, border_radius=12, prefix_icon=ft.Icons.NOTIFICATIONS,
        )

        def save_configuration(e):
            db = SessionLocal()
            settings_obj = db.query(UserSettings).filter(UserSettings.user_id == USER_ID).first()
            if not settings_obj:
                settings_obj = UserSettings(
                    user_id=USER_ID,
                    enable_email_notifications=True,
                    enable_windows_notifications=True,
                    headless_mode=headless_switch.value,
                )
                db.add(settings_obj)
            
            # Get old email for comparison
            old_email = settings_obj.notification_email or ""
            new_email = config_notification_field.value.strip()

            # Check if TLS credential email change is allowed
            old_tls_email = settings_obj.tls_email or ""
            new_tls_email = config_email_field.value.strip()
            if old_tls_email and new_tls_email and old_tls_email.lower() != new_tls_email.lower():
                from license_service import can_change_tls_email, record_tls_email_change
                can_change, message = can_change_tls_email(new_tls_email)
                
                if not can_change:
                    self.update_status_log(f"— {message}")
                    db.close()
                    return
                
                # Record the TLS email change
                record_tls_email_change(old_tls_email, new_tls_email)
                self.update_status_log(f"“ {message}")

            settings_obj.tls_email = new_tls_email
            if config_password_field.value:
                settings_obj.tls_password = auth_service.encrypt_password(config_password_field.value.strip())
            settings_obj.notification_email = new_email
            settings_obj.check_interval = int(config_interval_dropdown.value) if config_interval_dropdown.value else settings_obj.check_interval

            # Save service type
            svc_type = config_service_dropdown.value or 'legalization'
            settings_obj.service_type = svc_type

            # Set branch and resolve branch URL from config maps
            branch_name = config_branch_dropdown.value
            settings_obj.branch = branch_name
            if svc_type == 'visa':
                settings_obj.branch_url = Config.VISA_BRANCHES.get(
                    branch_name, list(Config.VISA_BRANCHES.values())[0]
                )
            else:
                settings_obj.branch_url = Config.LEGALIZATION_BRANCHES.get(
                    branch_name, list(Config.LEGALIZATION_BRANCHES.values())[0]
                )

            settings_obj.headless_mode = headless_switch.value

            db.commit()
            db.close()
            self.update_status_log("“ Configuration saved")

        # Build config card children dynamically
        config_children = [
            ft.Row(
                [
                    ft.Icon(ft.Icons.SETTINGS, size=22, color="#00D9FF"),
                    ft.Text("Configuration", size=16, weight=ft.FontWeight.BOLD),
                ],
                alignment=ft.MainAxisAlignment.START, spacing=8,
            ),
            ft.Divider(height=1, color=ft.Colors.with_opacity(0.2, "#00D9FF")),
            config_email_field,
            config_password_field,
            config_service_dropdown,
            config_branch_dropdown,
            config_notification_field,
        ]
        
        # Developer mode only: Show headless toggle and interval dropdown
        if self._developer_mode:
            config_children.append(config_interval_dropdown)
            config_interval_dropdown.visible = True
            config_children.append(
                ft.Row(
                    [
                        ft.Icon(ft.Icons.VISIBILITY_OFF, size=24, color="#00D9FF"),
                        ft.Text("Run browser in background (Dev)", size=13),
                        headless_switch,
                    ],
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN, spacing=10,
                )
            )
        
        # Save button
        config_children.append(
            ft.Row(
                [
                    ft.FilledButton(
                        "Save Configuration",
                        icon=ft.Icons.SAVE,
                        width=620, height=45,
                        on_click=save_configuration,
                        style=ft.ButtonStyle(bgcolor="#00D9FF", color="#0A0E27"),
                    ),
                ],
                alignment=ft.MainAxisAlignment.CENTER,
            )
        )

        config_card = self.create_glass_container(
            ft.Column(
                config_children,
                spacing=12,
            ),
            padding=16, width=660,
        )

        # ---- Toggle monitoring button ----
        def toggle_monitoring(e):
            db = SessionLocal()
            settings = db.query(UserSettings).filter(UserSettings.user_id == USER_ID).first()
            current_state = settings.is_monitoring if settings else False
            db.close()

            if current_state:
                stop_monitoring(e)
            else:
                start_monitoring(e)
            update_toggle_button()

        def update_toggle_button():
            db = SessionLocal()
            settings = db.query(UserSettings).filter(UserSettings.user_id == USER_ID).first()
            is_active = settings.is_monitoring if settings else False
            db.close()

            if is_active:
                toggle_btn.text = "Stop Monitoring"
                toggle_btn.icon = ft.Icons.STOP
                toggle_btn.style = ft.ButtonStyle(
                    bgcolor=ft.Colors.with_opacity(0.3, ft.Colors.RED),
                    color="#FF6B6B",
                )
            else:
                toggle_btn.text = "Start Monitoring"
                toggle_btn.icon = ft.Icons.PLAY_ARROW
                toggle_btn.style = ft.ButtonStyle(
                    bgcolor="#00D9FF",
                    color="#0A0E27",
                )
            self.page.update()

        toggle_btn = ft.FilledButton(
            "Start Monitoring" if not is_monitoring else "Stop Monitoring",
            icon=ft.Icons.PLAY_ARROW if not is_monitoring else ft.Icons.STOP,
            on_click=toggle_monitoring,
            height=50, width=660,
            style=ft.ButtonStyle(
                bgcolor="#00D9FF" if not is_monitoring else ft.Colors.with_opacity(0.3, ft.Colors.RED),
                color="#0A0E27" if not is_monitoring else "#FF6B6B",
            ),
        )

        # ---- Plan badge ----
        if license_status and license_status['valid']:
            plan_info = license_status['plan_info']
            plan_key_curr = license_status['plan']
            if plan_key_curr == 'premium':
                badge_text = "Premium ☁"
                badge_border = ft.Colors.AMBER_600
                badge_bg = ft.Colors.with_opacity(0.15, ft.Colors.AMBER)
                badge_color = ft.Colors.AMBER_400
                badge_icon_color = ft.Colors.AMBER_400
            elif plan_key_curr in ('legalization_monthly', 'visa_monthly', 'lifetime'):
                days = license_status.get('days_remaining', 0)
                pname = plan_info.get('name', plan_key_curr.replace('_', ' ').title())
                badge_text = f"{pname} · {days}d left"
                badge_border = ft.Colors.AMBER_600
                badge_bg = ft.Colors.with_opacity(0.15, ft.Colors.AMBER)
                badge_color = ft.Colors.AMBER_400
                badge_icon_color = ft.Colors.AMBER_400
            elif plan_key_curr == 'trial':
                secs_left = (license_status['expires_at'] - datetime.now(timezone.utc)).total_seconds()
                hrs = max(0, int(secs_left / 3600))
                badge_text = f"Trial · {hrs}h left"
                badge_border = ft.Colors.GREEN_600
                badge_bg = ft.Colors.with_opacity(0.15, ft.Colors.GREEN)
                badge_color = ft.Colors.GREEN_400
                badge_icon_color = ft.Colors.GREEN_400
            else:
                days = license_status.get('days_remaining', 0)
                badge_text = f"{plan_info['name']} · {days}d left"
                badge_border = "#00D9FF"
                badge_bg = ft.Colors.with_opacity(0.15, "#00D9FF")
                badge_color = "#00D9FF"
                badge_icon_color = "#00D9FF"

            plan_badge = ft.Container(
                content=ft.Row(
                    [
                        ft.Icon(ft.Icons.WORKSPACE_PREMIUM, color=badge_icon_color, size=20),
                        ft.Text(badge_text, color=badge_color, weight=ft.FontWeight.BOLD, size=13),
                    ],
                    spacing=6,
                ),
                padding=10, border_radius=10,
                bgcolor=badge_bg,
                border=ft.Border.all(1, badge_border),
            )
        else:
            plan_badge = ft.Container(visible=False)

        # ---- Support dialog ----
        def show_support_dialog(e):
            support_subject = ft.TextField(
                label="Subject", width=400, border_radius=10,
                prefix_icon=ft.Icons.SUBJECT,
            )
            support_message = ft.TextField(
                label="Message", width=400, border_radius=10,
                multiline=True, min_lines=4, max_lines=8,
                prefix_icon=ft.Icons.MESSAGE,
            )
            support_email_field = ft.TextField(
                label="Your Email (for reply)", width=400, border_radius=10,
                prefix_icon=ft.Icons.EMAIL,
                value=settings.notification_email if settings and settings.notification_email else "",
            )
            support_status = ft.Text("", size=13)

            def send_support(e):
                subj = (support_subject.value or "").strip()
                msg = (support_message.value or "").strip()
                reply_email = (support_email_field.value or "").strip()
                if not subj or not msg:
                    support_status.value = "Please fill in subject and message."
                    support_status.color = ft.Colors.RED_400
                    self.page.update()
                    return
                # Send email in background
                support_status.value = "Sending..."
                support_status.color = ft.Colors.GREY_400
                self.page.update()

                def _send():
                    try:
                        import smtplib
                        from email.mime.text import MIMEText
                        from email.mime.multipart import MIMEMultipart
                        hw_id = get_hardware_id()
                        plan_name = license_status.get('plan', 'unknown') if license_status else 'none'
                        body = (
                            f"From: {reply_email or 'N/A'}\n"
                            f"Hardware ID: {hw_id}\n"
                            f"Plan: {plan_name}\n"
                            f"App Version: {VERSION}\n"
                            f"{'='*40}\n\n"
                            f"{msg}"
                        )
                        email_msg = MIMEMultipart()
                        email_msg['From'] = "tlsappointmentchecker@gmail.com"
                        email_msg['To'] = "tlsappointmentchecker@gmail.com"
                        email_msg['Subject'] = f"[Support] {subj}"
                        if reply_email:
                            email_msg['Reply-To'] = reply_email
                        email_msg.attach(MIMEText(body, 'plain'))

                        with smtplib.SMTP("smtp.gmail.com", 587) as server:
                            server.starttls()
                            server.login("tlsappointmentchecker@gmail.com", "zylc etmv kuic uluq")
                            server.send_message(email_msg)

                        support_status.value = "… Message sent! We'll get back to you soon."
                        support_status.color = ft.Colors.GREEN_400
                    except Exception as ex:
                        support_status.value = f"Failed to send: {str(ex)[:60]}"
                        support_status.color = ft.Colors.RED_400
                    try:
                        self.page.update()
                    except Exception:
                        pass

                threading.Thread(target=_send, daemon=True).start()

            def close_support(e):
                support_dlg.open = False
                self.page.update()

            support_dlg = ft.AlertDialog(
                modal=True,
                title=ft.Row([
                    ft.Icon(ft.Icons.SUPPORT_AGENT, color="#00D9FF", size=28),
                    ft.Text("Contact Support", size=20, weight=ft.FontWeight.BOLD),
                ]),
                content=ft.Column([
                    ft.Text("Have a question or issue? Send us a message.", size=13, color=ft.Colors.GREY_400),
                    ft.Container(height=10),
                    support_email_field,
                    support_subject,
                    support_message,
                    ft.Container(height=5),
                    support_status,
                ], tight=True, spacing=10),
                actions=[
                    ft.TextButton("Cancel", on_click=close_support),
                    ft.FilledButton("Send", icon=ft.Icons.SEND, on_click=send_support,
                                    style=ft.ButtonStyle(bgcolor="#00D9FF", color="#0A0E27")),
                ],
                actions_alignment=ft.MainAxisAlignment.END,
                bgcolor="#1A1F3A",
            )
            self.page.overlay.append(support_dlg)
            support_dlg.open = True
            self.page.update()

        # ---- Header ----
        header_actions = ft.Row(
            [
                plan_badge,
                self.create_website_icon_button(),
                ft.IconButton(
                    icon=ft.Icons.SUPPORT_AGENT,
                    tooltip="Contact Support",
                    on_click=show_support_dialog,
                    icon_color="#00D9FF",
                ),
                ft.IconButton(
                    icon=ft.Icons.PHOTO_LIBRARY,
                    tooltip="View Screenshots",
                    on_click=view_screenshots,
                    icon_color="#00D9FF",
                ),
                ft.IconButton(
                    icon=ft.Icons.SWAP_HORIZ,
                    tooltip="Change License",
                    on_click=change_plan,
                    icon_color="#00D9FF",
                ),
            ],
            spacing=10,
            alignment=ft.MainAxisAlignment.END,
        )

        header = ft.Container(
            content=ft.Row(
                [
                    ft.Image(
                        src=self._logo_src or "Logos/LOGO_H_W.png",
                        width=220, height=50,
                    ),
                    header_actions,
                ],
                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            ),
            padding=ft.Padding(left=0, right=0, top=15, bottom=10),
        )

        # ---- Help & Support card ----
        def open_whatsapp_support(e):
            webbrowser.open("https://wa.me/201060263887")

        def open_faq(e):
            webbrowser.open("https://tls-saas.vercel.app/#faq")

        help_card = self.create_glass_container(
            ft.Column([
                ft.Row([
                    ft.Icon(ft.Icons.HELP_CENTER, size=22, color="#00D9FF"),
                    ft.Text("Help & Support", size=16, weight=ft.FontWeight.BOLD),
                ], alignment=ft.MainAxisAlignment.START, spacing=8),
                ft.Divider(height=1, color=ft.Colors.with_opacity(0.2, "#00D9FF")),
                ft.Container(height=4),
                ft.Row([
                    ft.Container(
                        content=ft.Column([
                            ft.Icon(ft.Icons.CHAT, size=28, color=ft.Colors.GREEN_400),
                            ft.Text("WhatsApp", size=12, weight=ft.FontWeight.BOLD),
                            ft.Text("Quick support", size=10, color=ft.Colors.GREY_500),
                        ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=4),
                        padding=12, border_radius=12,
                        bgcolor=ft.Colors.with_opacity(0.05, ft.Colors.GREEN),
                        border=ft.Border.all(1, ft.Colors.with_opacity(0.2, ft.Colors.GREEN)),
                        ink=True, on_click=open_whatsapp_support, expand=True,
                    ),
                    ft.Container(
                        content=ft.Column([
                            ft.Icon(ft.Icons.MENU_BOOK, size=28, color="#00D9FF"),
                            ft.Text("User Guide", size=12, weight=ft.FontWeight.BOLD),
                            ft.Text("How to use", size=10, color=ft.Colors.GREY_500),
                        ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=4),
                        padding=12, border_radius=12,
                        bgcolor=ft.Colors.with_opacity(0.05, "#00D9FF"),
                        border=ft.Border.all(1, ft.Colors.with_opacity(0.2, "#00D9FF")),
                        ink=True, on_click=open_faq, expand=True,
                    ),
                    ft.Container(
                        content=ft.Column([
                            ft.Icon(ft.Icons.SUPPORT_AGENT, size=28, color=ft.Colors.AMBER_400),
                            ft.Text("Support", size=12, weight=ft.FontWeight.BOLD),
                            ft.Text("Send a ticket", size=10, color=ft.Colors.GREY_500),
                        ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=4),
                        padding=12, border_radius=12,
                        bgcolor=ft.Colors.with_opacity(0.05, ft.Colors.AMBER),
                        border=ft.Border.all(1, ft.Colors.with_opacity(0.2, ft.Colors.AMBER)),
                        ink=True, on_click=show_support_dialog, expand=True,
                    ),
                    ft.Container(
                        content=ft.Column([
                            ft.Icon(ft.Icons.LANGUAGE, size=28, color="#FF6B9D"),
                            ft.Text("Website", size=12, weight=ft.FontWeight.BOLD),
                            ft.Text("Learn more", size=10, color=ft.Colors.GREY_500),
                        ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=4),
                        padding=12, border_radius=12,
                        bgcolor=ft.Colors.with_opacity(0.05, "#FF6B9D"),
                        border=ft.Border.all(1, ft.Colors.with_opacity(0.2, "#FF6B9D")),
                        ink=True, on_click=lambda e: webbrowser.open("https://tls-saas.vercel.app"), expand=True,
                    ),
                ], alignment=ft.MainAxisAlignment.CENTER, spacing=10),
            ], spacing=8),
            padding=16, width=660,
        )

        # ---- Main layout ----
        content = ft.Container(
            content=ft.Column(
                [
                    header,
                    ft.Divider(height=1, color=ft.Colors.with_opacity(0.2, ft.Colors.WHITE)),
                    ft.Container(height=15),

                    # Two-column: left controls + right activity log
                    ft.Row(
                        [
                            # Left column
                            ft.Column(
                                [
                                    ft.Row(
                                        [checks_card, checks_day_card, last_check_card, countdown_card],
                                        alignment=ft.MainAxisAlignment.START, spacing=10,
                                        wrap=True,
                                    ),
                                    ft.Container(height=15),
                                    ft.Row(
                                        [toggle_btn],
                                        alignment=ft.MainAxisAlignment.START, spacing=20,
                                    ),
                                    ft.Container(height=12),
                                    config_card,
                                    ft.Container(height=12),
                                    help_card,
                                ],
                            ),

                            # Right column — activity log (expands to fill)
                            ft.Container(
                                content=self.create_glass_container(
                                    ft.Column(
                                        [
                                            ft.Row(
                                                [
                                                    ft.Icon(ft.Icons.HISTORY, size=20, color="#00D9FF"),
                                                    ft.Text("Activity Log", size=16, weight=ft.FontWeight.BOLD),
                                                ],
                                                alignment=ft.MainAxisAlignment.CENTER, spacing=8,
                                            ),
                                            ft.Divider(height=1, color=ft.Colors.with_opacity(0.2, "#00D9FF")),
                                            ft.Container(content=self.status_list, expand=True),
                                        ],
                                        spacing=8,
                                    ),
                                    padding=10, height=890,
                                ),
                                expand=True,
                            ),
                        ],
                        alignment=ft.MainAxisAlignment.START,
                        spacing=15,
                        vertical_alignment=ft.CrossAxisAlignment.START,
                    ),
                ],
                spacing=15,
                scroll=ft.ScrollMode.AUTO,
            ),
            padding=ft.Padding(left=20, right=20, top=0, bottom=0),
            expand=True,
        )

        self.page.add(content)

        # Force window size
        self.page.window.width = 1400
        self.page.window.height = 1150
        self.page.window.maximizable = True
        self.page.window.maximized = False
        self.page.window.full_screen = False
        try:
            import ctypes
            user32 = ctypes.windll.user32
            user32.SetProcessDPIAware()
            screen_width = user32.GetSystemMetrics(0)
            screen_height = user32.GetSystemMetrics(1)
            self.page.window.left = (screen_width - 1400) // 2
            self.page.window.top = max(0, (screen_height - 1050) // 2)
        except Exception:
            pass

        self.page.update()

        # Auto-start if coming from trial activation
        if auto_start:
            db = SessionLocal()
            settings = db.query(UserSettings).filter(UserSettings.user_id == USER_ID).first()

            if settings and settings.tls_email and settings.tls_password:
                first_check_done = settings.first_check_done
                settings.is_monitoring = True
                db.commit()
                db.close()

                if not first_check_done:
                    self.update_status_log("ℹ️ You'll watch the first check to verify everything works correctly")
                    self.update_status_log("ℹ️ After that, checks will run in the background")

                self.checker.start_monitoring()
                update_toggle_button()
            else:
                db.close()

    # ==================================================================
    #  SCREENSHOTS GALLERY
    # ==================================================================
    def show_screenshots_gallery(self):
        """Show gallery of captured screenshots"""
        self.page.controls.clear()

        screenshots = glob.glob("slots_found_*.png")
        screenshots.sort(reverse=True)

        def back_to_monitor(e):
            self.show_monitoring_page()

        if not screenshots:
            gallery_content = ft.Column(
                [
                    ft.Icon(ft.Icons.PHOTO_LIBRARY_OUTLINED, size=100, color=ft.Colors.GREY_600),
                    ft.Container(height=20),
                    ft.Text("No screenshots yet", size=24, color=ft.Colors.GREY_500),
                    ft.Text("Screenshots will appear here when appointments are found", size=14, color=ft.Colors.GREY_600),
                ],
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                spacing=10,
            )
        else:
            screenshot_cards = []
            for screenshot in screenshots[:20]:
                try:
                    timestamp = screenshot.replace("slots_found_", "").replace(".png", "")
                    formatted_time = datetime.strptime(timestamp, "%Y%m%d_%H%M%S").strftime("%Y-%m-%d %H:%M:%S")

                    def open_screenshot(e, img_path=screenshot):
                        import subprocess
                        import platform
                        abs_path = os.path.abspath(img_path)
                        if platform.system() == 'Windows':
                            os.startfile(abs_path)
                        elif platform.system() == 'Darwin':
                            subprocess.run(['open', abs_path])
                        else:
                            subprocess.run(['xdg-open', abs_path])

                    card = ft.Container(
                        content=ft.Column(
                            [
                                ft.Image(
                                    src=os.path.abspath(screenshot),
                                    width=300, height=200,
                                    border_radius=10,
                                ),
                                ft.Text(formatted_time, size=12, color=ft.Colors.GREY_400),
                            ],
                            spacing=5,
                        ),
                        padding=10,
                        border_radius=15,
                        bgcolor=ft.Colors.with_opacity(0.05, ft.Colors.WHITE),
                        border=ft.Border.all(1, ft.Colors.with_opacity(0.2, ft.Colors.WHITE)),
                        on_click=open_screenshot,
                        ink=True,
                    )
                    screenshot_cards.append(card)
                except Exception:
                    pass

            gallery_content = ft.Column(
                [
                    ft.Row(
                        screenshot_cards,
                        wrap=True, spacing=15, run_spacing=15,
                    ),
                ],
                scroll=ft.ScrollMode.AUTO,
            )

        header = ft.Container(
            content=ft.Row(
                [
                    ft.IconButton(icon=ft.Icons.ARROW_BACK, on_click=back_to_monitor),
                    ft.Text("Screenshots Gallery", size=28, weight=ft.FontWeight.BOLD),
                ],
                spacing=10,
            ),
            padding=20,
        )

        content = ft.Container(
            content=ft.Column(
                [
                    header,
                    ft.Divider(height=1, color=ft.Colors.with_opacity(0.2, ft.Colors.WHITE)),
                    ft.Container(height=20),
                    gallery_content,
                ],
                scroll=ft.ScrollMode.AUTO,
            ),
            padding=10, expand=True,
        )

        self.page.add(content)
        self.page.update()

    # ==================================================================
    #  UI UPDATE LOOP  (thread-safe queue → main thread)
    # ==================================================================
    async def _ui_update_loop(self):
        while True:
            try:
                item = self._ui_queue.get_nowait()
            except queue.Empty:
                await asyncio.sleep(0.1)
                continue

            # Handle plain callables (used by login/register callbacks)
            if callable(item):
                try:
                    item()
                    self.page.update()
                except Exception:
                    pass
                continue

            try:
                kind = item[0]
                if kind == "log":
                    message = item[1]
                    if self.status_list:
                        timestamp = datetime.now().strftime("%H:%M:%S")

                        # Persist for page rebuild recovery
                        self._log_history.append((message, timestamp))
                        if len(self._log_history) > 50:
                            self._log_history = self._log_history[-50:]

                        log_entry = self._create_log_entry(message, timestamp)

                        self.status_list.controls.append(log_entry)
                        if len(self.status_list.controls) > 20:
                            self.status_list.controls.pop(0)

                        if self.status_text:
                            current_text = self.status_text.value if self.status_text.value != "Ready to start monitoring..." else ""
                            new_line = f"[{timestamp}] {message}"
                            new_text = (current_text + "\n" + new_line) if current_text else new_line
                            lines = new_text.split('\n')
                            self.status_text.value = '\n'.join(lines[-20:])

                    # Refresh stats in real-time after each log
                    try:
                        db = SessionLocal()
                        _s = db.query(UserSettings).filter(UserSettings.user_id == USER_ID).first()
                        if _s and hasattr(self, 'checks_count_text') and self.checks_count_text:
                            self.checks_count_text.value = str(_s.total_checks)
                        db.close()
                        _ls = get_license_status()
                        if _ls and hasattr(self, 'checks_today_text') and self.checks_today_text:
                            _ct = _ls.get('checks_today', 0)
                            _cl = _ls.get('checks_limit', 0)
                            if _cl >= 99999:
                                _cl_str = "\u221e"
                            elif _cl >= 10000:
                                _cl_str = f"{_cl // 1000}k"
                            else:
                                _cl_str = str(_cl)
                            self.checks_today_text.value = f"{_ct}/{_cl_str}"
                    except Exception:
                        pass

                elif kind == "countdown":
                    minutes, seconds = item[1], item[2]
                    if self.countdown_text:
                        if minutes == 0 and seconds == 0:
                            self.countdown_text.value = "--:--"
                        else:
                            self.countdown_text.value = f"{minutes}:{seconds:02d}"

                elif kind == "credentials_error":
                    self.show_credentials_error_dialog()
                elif kind == "no_application_error":
                    self.show_no_application_dialog()
                elif kind == "license_invalid":
                    self.show_license_invalid_dialog()
            finally:
                try:
                    self.page.update()
                except Exception:
                    pass

    def update_status_log(self, message: str):
        try:
            if message == "SHOW_CREDENTIALS_ERROR":
                self._ui_queue.put(("credentials_error",))
                return
            if message == "SHOW_NO_APPLICATION_ERROR":
                self._ui_queue.put(("no_application_error",))
                return
            if "License no longer valid" in message or "License revoked" in message:
                self._ui_queue.put(("license_invalid",))
                return
            self._ui_queue.put(("log", message))
        except Exception as e:
            print(f"Error updating log: {e}")

    def show_credentials_error_dialog(self):
        def close_dialog(e):
            error_dialog.open = False
            self.page.update()

        def open_configuration(e):
            error_dialog.open = False
            self.page.update()
            self.show_monitoring_page()
            self.update_status_log("Update TLS email and password in the configuration card below.")

        error_dialog = ft.AlertDialog(
            modal=True,
            title=ft.Text("❌ Invalid TLS Credentials", size=24, weight=ft.FontWeight.BOLD, color=ft.Colors.RED_400),
            content=ft.Column([
                ft.Text("Your TLS email or password is incorrect.", size=16),
                ft.Container(height=10),
                ft.Text("The TLS website rejected your login credentials.", size=14, color=ft.Colors.GREY_400),
                ft.Container(height=10),
                ft.Text("Please update your TLS email and password in the configuration card.", size=14, weight=ft.FontWeight.BOLD),
            ], tight=True),
            actions=[
                ft.TextButton("Close", on_click=close_dialog),
                ft.FilledButton(
                    "Open Configuration",
                    on_click=open_configuration,
                    style=ft.ButtonStyle(
                        bgcolor={"": "#00D9FF", "hovered": "#00B8D4"},
                        color=ft.Colors.BLACK,
                    ),
                ),
            ],
            actions_alignment=ft.MainAxisAlignment.END,
            bgcolor="#1A1F3A",
        )

        self.page.overlay.append(error_dialog)
        error_dialog.open = True
        self.page.update()

    def update_countdown(self, minutes: int, seconds: int):
        try:
            self._ui_queue.put(("countdown", minutes, seconds))
        except Exception as e:
            print(f"Error updating countdown: {e}")

    def show_no_application_dialog(self):
        """Show popup when no application is found on TLS website."""
        # Stop monitoring
        if self.checker:
            self.checker.stop_monitoring()
        
        # Update DB
        db = SessionLocal()
        settings = db.query(UserSettings).filter(UserSettings.user_id == USER_ID).first()
        if settings:
            settings.is_monitoring = False
            db.commit()
        db.close()

        def close_dialog(e):
            no_app_dlg.open = False
            self.page.update()
            self.show_monitoring_page()

        no_app_dlg = ft.AlertDialog(
            modal=True,
            title=ft.Row([
                ft.Icon(ft.Icons.ERROR_OUTLINE, color=ft.Colors.AMBER_400, size=28),
                ft.Text("No Application Found", size=20, weight=ft.FontWeight.BOLD),
            ]),
            content=ft.Column([
                ft.Text(
                    "You don't have an application created on the TLS website.",
                    size=16, color="#FFFFFF",
                ),
                ft.Container(height=10),
                ft.Text(
                    "To use this app, you must first:",
                    size=14, color=ft.Colors.GREY_400,
                ),
                ft.Container(height=5),
                ft.Text("1. Go to the TLS website", size=13, color=ft.Colors.GREY_300),
                ft.Text("2. Log in with your account", size=13, color=ft.Colors.GREY_300),
                ft.Text("3. Click 'Create a new application'", size=13, color=ft.Colors.GREY_300),
                ft.Text("4. Fill in all required details", size=13, color=ft.Colors.GREY_300),
                ft.Text("5. Come back here and start monitoring", size=13, color=ft.Colors.GREY_300),
                ft.Container(height=10),
                ft.Text(
                    "Monitoring has been stopped.",
                    size=14, weight=ft.FontWeight.BOLD, color=ft.Colors.AMBER_400,
                ),
            ], tight=True, spacing=4),
            actions=[
                ft.FilledButton(
                    "OK",
                    on_click=close_dialog,
                    style=ft.ButtonStyle(bgcolor="#00D9FF", color="#0A0E27"),
                ),
            ],
            actions_alignment=ft.MainAxisAlignment.END,
            bgcolor="#1A1F3A",
        )

        self.page.overlay.append(no_app_dlg)
        no_app_dlg.open = True
        self.page.update()

    def show_license_invalid_dialog(self):
        """Show popup when license is revoked or becomes invalid during monitoring."""
        # Stop monitoring
        if self.checker:
            self.checker.stop_monitoring()
        
        # Update DB
        db = SessionLocal()
        settings = db.query(UserSettings).filter(UserSettings.user_id == USER_ID).first()
        if settings:
            settings.is_monitoring = False
            db.commit()
        db.close()

        def go_to_activation(e):
            license_dlg.open = False
            self.page.update()
            self.show_activation_page()

        license_dlg = ft.AlertDialog(
            modal=True,
            title=ft.Row([
                ft.Icon(ft.Icons.BLOCK, color=ft.Colors.RED_400, size=28),
                ft.Text("License No Longer Valid", size=20, weight=ft.FontWeight.BOLD),
            ]),
            content=ft.Column([
                ft.Text(
                    "Your license has been deactivated or is no longer valid.",
                    size=16, color="#FFFFFF",
                ),
                ft.Container(height=10),
                ft.Text(
                    "Possible reasons:",
                    size=14, color=ft.Colors.GREY_400,
                ),
                ft.Container(height=5),
                ft.Text("• License was manually revoked", size=13, color=ft.Colors.GREY_300),
                ft.Text("• License expired", size=13, color=ft.Colors.GREY_300),
                ft.Text("• License is being used on another device", size=13, color=ft.Colors.GREY_300),
                ft.Container(height=10),
                ft.Text(
                    "Monitoring has been stopped.",
                    size=14, weight=ft.FontWeight.BOLD, color=ft.Colors.RED_400,
                ),
                ft.Container(height=5),
                ft.Text(
                    "Please purchase a new license or contact support.",
                    size=14, color=ft.Colors.GREY_400,
                ),
            ], tight=True, spacing=4),
            actions=[
                ft.FilledButton(
                    "Get New License",
                    on_click=go_to_activation,
                    style=ft.ButtonStyle(bgcolor="#00D9FF", color="#0A0E27"),
                ),
            ],
            actions_alignment=ft.MainAxisAlignment.END,
            bgcolor="#1A1F3A",
        )

        self.page.overlay.append(license_dlg)
        license_dlg.open = True
        self.page.update()


# ==================================================================
#  Entry point
# ==================================================================
def main(page: ft.Page):
    TLSApp(page)


if __name__ == "__main__":
    # Determine base directory — handles both source and frozen (.exe) mode
    if getattr(sys, 'frozen', False):
        # PyInstaller unpacks data to sys._MEIPASS
        app_dir = sys._MEIPASS
    else:
        app_dir = os.path.dirname(os.path.abspath(__file__))

    def _port_is_free(port: int) -> bool:
        for family, host in ((socket.AF_INET6, "::"), (socket.AF_INET, "0.0.0.0")):
            try:
                with socket.socket(family, socket.SOCK_STREAM) as s:
                    if family == socket.AF_INET6:
                        try:
                            s.setsockopt(socket.IPPROTO_IPV6, socket.IPV6_V6ONLY, 1)
                        except OSError:
                            pass
                    s.bind((host, port))
            except OSError:
                return False
        return True

    def _pick_free_port() -> int:
        try:
            with socket.socket(socket.AF_INET6, socket.SOCK_STREAM) as s6:
                try:
                    s6.setsockopt(socket.IPPROTO_IPV6, socket.IPV6_V6ONLY, 1)
                except OSError:
                    pass
                s6.bind(("::", 0))
                candidate = int(s6.getsockname()[1])
            if _port_is_free(candidate):
                return candidate
        except OSError:
            pass
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s4:
            s4.bind(("0.0.0.0", 0))
            return int(s4.getsockname()[1])

    preferred_port = int(os.environ.get("FLET_PORT", "8080"))
    port = preferred_port if _port_is_free(preferred_port) else _pick_free_port()
    if port != preferred_port:
        print(f"Port {preferred_port} is busy; using {port} instead")

    ft.run(main, assets_dir=app_dir, view=ft.AppView.FLET_APP)
