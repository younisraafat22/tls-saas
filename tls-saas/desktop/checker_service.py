"""
TLS Checker Service
Background service for checking appointment availability
"""
import threading
import time
import os
import sys
import tempfile
import requests as http_requests
from datetime import datetime, timedelta, timezone
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from selenium.common.exceptions import TimeoutException
from config import Config
from database import SessionLocal, UserSettings, CheckHistory, User
from notification_service import notification_service
from auth_service import auth_service
from license_service import can_check, increment_check_count
import random

# ── Audio CAPTCHA solving engines ──────────────────────────────────
# Audio transcription
# Engine: Google Web Speech API (online, free, reliable)

# Engine 2: Google Speech Recognition via SpeechRecognition lib (online, free)
try:
    import speech_recognition as sr
    SR_AVAILABLE = True
except ImportError:
    SR_AVAILABLE = False

# Audio conversion (pydub)
try:
    from pydub import AudioSegment
    from pydub.effects import normalize as pydub_normalize
    PYDUB_AVAILABLE = True
except ImportError:
    PYDUB_AVAILABLE = False

# Point pydub at the bundled ffmpeg from imageio-ffmpeg if system ffmpeg is absent
try:
    import imageio_ffmpeg
    _ffmpeg_path = imageio_ffmpeg.get_ffmpeg_exe()
    if _ffmpeg_path and PYDUB_AVAILABLE:
        AudioSegment.converter = _ffmpeg_path
        # Use ffmpeg as prober (ffprobe not bundled with imageio-ffmpeg)
        import pydub.utils
        pydub.utils.PROBER = _ffmpeg_path
except Exception:
    pass

# ── Anti-bot browsers ──────────────────────────────────────────────
try:
    from seleniumbase import Driver
    SELENIUMBASE_AVAILABLE = True
except ImportError:
    SELENIUMBASE_AVAILABLE = False

try:
    import undetected_chromedriver as uc
    UNDETECTED_CHROME_AVAILABLE = True
except ImportError:
    UNDETECTED_CHROME_AVAILABLE = False

# Window transparency helper for "invisible" mode
try:
    from window_hider import ChromeWindowHider, get_chrome_hwnds, find_new_chrome_hwnd
    WINDOW_HIDER_AVAILABLE = True
except ImportError:
    WINDOW_HIDER_AVAILABLE = False


def _get_chrome_major_version() -> int | None:
    """Detect the installed Chrome/Chromium major version number.
    Returns e.g. 145 or None if undetectable.
    Uses registry first to avoid briefly launching Chrome as a subprocess."""
    import re
    # 1) Registry (fast, no Chrome launch)
    try:
        import winreg
        for reg_path in [
            r'Software\Google\Chrome\BLBeacon',
            r'Software\Wow6432Node\Google\Chrome\BLBeacon',
        ]:
            for hive in [winreg.HKEY_CURRENT_USER, winreg.HKEY_LOCAL_MACHINE]:
                try:
                    key = winreg.OpenKey(hive, reg_path)
                    version, _ = winreg.QueryValueEx(key, 'version')
                    winreg.CloseKey(key)
                    m = re.search(r'(\d+)\.', str(version))
                    if m:
                        return int(m.group(1))
                except Exception:
                    pass
    except Exception:
        pass
    # 2) Fallback: read from chrome.exe file version (no subprocess launch)
    try:
        import win32api
        candidates = [
            os.path.join(os.environ.get('PROGRAMFILES', ''), 'Google', 'Chrome', 'Application', 'chrome.exe'),
            os.path.join(os.environ.get('PROGRAMFILES(X86)', ''), 'Google', 'Chrome', 'Application', 'chrome.exe'),
            os.path.join(os.environ.get('LOCALAPPDATA', ''), 'Google', 'Chrome', 'Application', 'chrome.exe'),
        ]
        for path in candidates:
            if os.path.exists(path):
                info = win32api.GetFileVersionInfo(path, '\\')
                ms = info['FileVersionMS']
                major = ms >> 16
                if major:
                    return int(major)
    except Exception:
        pass
    return None

# Audio transcription imports

class TLSCheckerService:
    """Background service for checking TLS appointments"""
    
    def __init__(self, user_id: int, on_status_update=None, on_countdown_update=None):
        self.user_id = user_id
        self.driver = None
        self._is_seleniumbase = False
        self.is_running = False
        self._window_hidden = False  # Track if window has been hidden in background mode
        self._chrome_hider = ChromeWindowHider() if WINDOW_HIDER_AVAILABLE else None
        self.check_thread = None
        self.on_status_update = on_status_update  # Callback for UI updates
        self.on_countdown_update = on_countdown_update  # Callback for countdown timer
        self.last_status_report = None
        self.developer_mode = False  # When True, ALL log messages are forwarded to the UI
        # Email notification throttling: send at most 2 emails per slot-available cycle
        # (1 immediate + 1 reminder after 12 hours). Reset when no slots found.
        self._slots_notif_count = 0          # 0=not sent, 1=first sent, 2=reminder sent
        self._slots_first_notif_time = None  # datetime of first notification
        self._last_error_email_time = None   # throttle error emails (max 1/hr)
    
    def _report_to_backend(self, branch_name: str, service_type: str,
                           slots_available: bool, slot_details: str = "",
                           error: str = ""):
        """Fire-and-forget: report check result to backend so the web dashboard can show it."""
        def _do_report():
            try:
                from license_service import get_license_status
                import json as _json
                import urllib.request
                import urllib.error

                lic = get_license_status()
                if not lic or not lic.get("key"):
                    return  # No license key — skip

                payload = _json.dumps({
                    "license_key": lic["key"],
                    "branch_name": branch_name,
                    "service_type": service_type,
                    "slots_available": slots_available,
                    "slot_details": slot_details,
                    "error": error,
                }).encode("utf-8")

                url = f"{Config.BACKEND_URL.rstrip('/')}/api/monitoring/report-desktop-license"
                req = urllib.request.Request(url, data=payload,
                                            headers={"Content-Type": "application/json"},
                                            method="POST")
                with urllib.request.urlopen(req, timeout=10) as resp:
                    pass  # 200 OK is enough
            except Exception as e:
                print(f"[Checker] Backend report failed (non-fatal): {e}")

        threading.Thread(target=_do_report, daemon=True).start()

    # Messages allowed in the UI activity log (prefix match).
    # Everything else is printed to terminal only.
    # Messages shown in the "Recent Checks" UI panel (prefix match).
    # Only check outcomes and start/stop events — everything else goes
    # to the debug log file only.  Developer mode does NOT override this;
    # verbose step-by-step logs are always debug-file-only.
    _UI_ALLOWED_PREFIXES = (
        "\u23f9\ufe0f Monitoring stopped",
        "\U0001F50D Check at ",
        "\u274c TLS credentials",
        "[ERROR]",
        "\u274c License no longer valid",  # Triggers license-invalid dialog
    )

    def _log(self, message: str):
        """Log message — only show user-facing messages in UI, rest goes to terminal and log file."""
        print(f"[Checker] {message}")
        
        # Also write to log file for debugging built apps
        try:
            import os
            from datetime import datetime
            from pathlib import Path
            
            # Try to use AppData first, fallback to temp
            try:
                from config import BASE_DIR
                log_dir = Path(str(BASE_DIR))
            except Exception:
                log_dir = Path(os.getenv('APPDATA', os.path.expanduser('~'))) / 'TLSAppointmentChecker'
            
            # Ensure directory exists
            log_dir.mkdir(parents=True, exist_ok=True)
            
            log_file = log_dir / "checker_debug.log"
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            with open(str(log_file), "a", encoding="utf-8") as f:
                f.write(f"[{timestamp}] {message}\n")
        except Exception as e:
            # If all else fails, silently continue - don't break the app
            print(f"[Checker] Warning: Could not write to debug log: {e}")
        
        # Forward ONLY result messages to the UI — always filtered regardless
        # of developer mode.  Verbose step-by-step logs stay in the debug file.
        if self.on_status_update:
            for prefix in self._UI_ALLOWED_PREFIXES:
                if message.startswith(prefix):
                    self.on_status_update(message)
                    return
    
    def _hide_chrome_window(self):
        """Make Chrome practically invisible in background mode.

        Uses Win32 layered-window transparency (alpha ≈ 0%) so the window
        is still rendered on-screen at normal coordinates.  Anti-bot systems
        see a fully visible, non-minimized window and pass all checks.
        The window is also removed from the taskbar and placed behind all
        other windows so it doesn't interfere with the user.

        Falls back to CDP viewport lock + minimize if the transparency
        helper is unavailable.
        """
        if self._window_hidden or not Config.BROWSER_HEADLESS or not self.driver:
            return

        # Strategy 1: Win32 transparency (preferred — anti-bot friendly)
        if self._chrome_hider and self._chrome_hider.hwnd:
            try:
                self._chrome_hider.hide()
                self._window_hidden = True
                self._log("Chrome window hidden (transparent mode)")
                return
            except Exception as e:
                print(f"[Checker] Transparency hide failed: {e}")

        # Strategy 2: Fallback — CDP viewport lock + minimize
        try:
            self.driver.execute_cdp_cmd(
                "Emulation.setDeviceMetricsOverride",
                {"width": 1920, "height": 1080,
                 "deviceScaleFactor": 1, "mobile": False},
            )
        except Exception:
            pass
        try:
            self.driver.minimize_window()
            self._window_hidden = True
        except Exception:
            pass
    def _inject_visibility_override(self):
        """Inject a CDP script that makes every page always report
        document.visibilityState = 'visible' and document.hidden = false.

        This persists across all page navigations for the lifetime of the
        browser session, ensuring that anti-bot / login pages never see a
        'hidden' visibility state even when the OS window is pushed to the
        bottom of the Z-order by the transparent-window hider.
        """
        if not self.driver:
            return
        try:
            self.driver.execute_cdp_cmd(
                "Page.addScriptToEvaluateOnNewDocument",
                {
                    "source": (
                        "Object.defineProperty(document, 'hidden', "
                        "  { get: () => false, configurable: true });"
                        "Object.defineProperty(document, 'visibilityState', "
                        "  { get: () => 'visible', configurable: true });"
                        "window.addEventListener('visibilitychange', "
                        "  function(e) { e.stopImmediatePropagation(); }, true);"
                    )
                },
            )
            print("[Checker] Visibility override injected via CDP")
        except Exception as e:
            print(f"[Checker] Could not inject visibility override: {e}")

    def log(self, message: str):
        """Public log method (alias for _log)"""
        self._log(message)
    
    def _redirect_driver_paths_for_frozen(self):
        """For installed (frozen) app: redirect SeleniumBase driver paths
        from the read-only Program Files bundle to a writable AppData location.
        Without this, UC mode fails because it can't write patched chromedriver."""
        if not getattr(sys, 'frozen', False):
            return
        from config import BASE_DIR

        writable_drivers = os.path.join(str(BASE_DIR), "drivers")
        os.makedirs(writable_drivers, exist_ok=True)

        # Redirect SeleniumBase paths to writable directory.
        # Do NOT pre-seed with a bundled chromedriver — the bundled version
        # will almost certainly mismatch the user's installed Chrome.
        # Instead let SeleniumBase download the matching chromedriver at
        # runtime (requires internet, which the app needs anyway).
        try:
            from seleniumbase.core import browser_launcher
            browser_launcher.DRIVER_DIR = writable_drivers
            browser_launcher.LOCAL_CHROMEDRIVER = os.path.join(
                writable_drivers, "chromedriver.exe"
            )
            browser_launcher.LOCAL_UC_DRIVER = os.path.join(
                writable_drivers, "uc_driver.exe"
            )

            # Only seed from bundle if NO driver exists yet AND the bundled
            # version matches the installed Chrome major version.  Otherwise
            # let SeleniumBase download the correct version automatically.
            chrome_major = _get_chrome_major_version()
            local_cd = browser_launcher.LOCAL_CHROMEDRIVER
            if not os.path.exists(local_cd):
                import shutil as _shutil
                bundled_cd = None
                for _search in [
                    os.path.join(getattr(sys, "_MEIPASS", ""), "seleniumbase", "drivers", "chromedriver.exe"),
                    os.path.join(os.path.dirname(sys.executable), "_internal", "seleniumbase", "drivers", "chromedriver.exe"),
                ]:
                    if os.path.exists(_search):
                        bundled_cd = _search
                        break
                if bundled_cd:
                    # Try to read the bundled driver's version to check compatibility
                    _version_ok = True
                    if chrome_major:
                        try:
                            import subprocess as _sp
                            _out = _sp.check_output(
                                [bundled_cd, "--version"],
                                timeout=5,
                                creationflags=_sp.CREATE_NO_WINDOW if os.name == "nt" else 0,
                            ).decode()
                            import re as _re
                            _m = _re.search(r"(\d+)\.", _out)
                            if _m and int(_m.group(1)) != chrome_major:
                                _version_ok = False
                                print(f"[Checker] Bundled chromedriver is v{_m.group(1)} but Chrome is v{chrome_major} — skipping seed, will download correct version")
                        except Exception:
                            pass  # Can't check version — try seeding anyway
                    if _version_ok:
                        for _dest in [browser_launcher.LOCAL_CHROMEDRIVER, browser_launcher.LOCAL_UC_DRIVER]:
                            try:
                                _shutil.copy2(bundled_cd, _dest)
                                print(f"[Checker] Seeded driver from bundle: {_dest}")
                            except Exception as _ce:
                                print(f"[Checker] Could not seed driver to {_dest}: {_ce}")
                else:
                    print("[Checker] No bundled chromedriver found — SeleniumBase will download one")
            else:
                print(f"[Checker] Using existing driver at {local_cd}")
        except Exception as e:
            print(f"[Checker] Warning: driver path redirect failed: {e}")

        # Update PATH so SeleniumBase and Selenium find drivers in writable dir
        if writable_drivers not in os.environ.get("PATH", ""):
            os.environ["PATH"] = (
                writable_drivers + os.pathsep + os.environ["PATH"]
            )

        # Redirect UC Patcher's data_path (where it writes patched binaries)
        try:
            from seleniumbase.undetected.patcher import Patcher
            writable_downloads = os.path.join(str(BASE_DIR), "downloaded_files")
            os.makedirs(writable_downloads, exist_ok=True)
            Patcher.data_path = writable_downloads
        except Exception:
            pass

    def _setup_driver(self):
        """Setup Selenium driver"""
        try:

            # Record existing Chrome windows BEFORE launch so we can
            # identify the new one afterwards (for the window hider).
            _pre_chrome_hwnds = get_chrome_hwnds() if WINDOW_HIDER_AVAILABLE else set()

            # Use AppData for browser downloads to avoid permission issues
            from config import BASE_DIR
            downloads_dir = os.path.join(str(BASE_DIR), "downloads")
            os.makedirs(downloads_dir, exist_ok=True)
            download_prefs = {
                "download.default_directory": downloads_dir,
                "download.prompt_for_download": False,
                "download.directory_upgrade": True,
            }

            # Ensure SeleniumBase creates ./downloaded_files inside AppData
            if SELENIUMBASE_AVAILABLE:
                original_cwd = os.getcwd()
                os.chdir(str(BASE_DIR))
                try:
                    # Patcher.data_path was already redirected by _redirect_driver_paths_for_frozen()
                    # above. Clear the stale UC binary from whatever path Patcher actually uses
                    # (frozen app: AppData/TLSAppointmentChecker/downloaded_files;
                    #  dev:         ./downloaded_files)
                    # Also clear the legacy %APPDATA%\undetected_chromedriver location.
                    try:
                        from seleniumbase.undetected.patcher import Patcher as _Patcher
                        import shutil as _shutil_sb
                        # Clean Patcher data_path (AppData or ./downloaded_files)
                        for _uc_file in ["undetected_chromedriver.exe", "chromedriver.exe"]:
                            _p = os.path.join(_Patcher.data_path, _uc_file)
                            if os.path.exists(_p):
                                try: os.remove(_p)
                                except Exception: pass
                        # Clean the chromedriver-win32 subfolder the patcher downloads into
                        _cdw32 = os.path.join(_Patcher.data_path, "chromedriver-win32")
                        if os.path.isdir(_cdw32):
                            _shutil_sb.rmtree(_cdw32, ignore_errors=True)
                        # Clean legacy %APPDATA%\undetected_chromedriver entirely
                        _legacy_dir = os.path.join(
                            os.environ.get("APPDATA", ""),
                            "undetected_chromedriver",
                        )
                        if os.path.isdir(_legacy_dir):
                            _shutil_sb.rmtree(_legacy_dir, ignore_errors=True)
                    except Exception:
                        pass

                    # Detect Chrome version and pass it as a numeric version_main.
                    # Passing "keep" or None causes the patcher to fetch the latest
                    # chromedriver version from the internet (ignoring installed Chrome).
                    chrome_ver = _get_chrome_major_version()
                    driver_ver = str(chrome_ver) if chrome_ver else "keep"

                    # Standard UC driver — no extra chromium flags.
                    # Anti-throttle flags like --disable-renderer-backgrounding
                    # change Chrome's JS fingerprint and cause Google reCAPTCHA
                    # to block audio challenges.  In "invisible" mode, the window
                    # is made nearly-transparent via Win32 layered-window API
                    # (see window_hider.py) so Chrome stays at normal screen
                    # coordinates and passes all anti-bot visibility checks.
                    driver_kwargs = {
                        "uc": True,
                        "headless": False,
                        "headless2": False,
                        "driver_version": driver_ver,
                    }
                    
                    # If running as frozen app, explicitly set binary location
                    if getattr(sys, 'frozen', False):
                        chrome_paths = [
                            os.path.join(os.environ.get('PROGRAMFILES', ''), 'Google', 'Chrome', 'Application', 'chrome.exe'),
                            os.path.join(os.environ.get('PROGRAMFILES(X86)', ''), 'Google', 'Chrome', 'Application', 'chrome.exe'),
                            os.path.join(os.environ.get('LOCALAPPDATA', ''), 'Google', 'Chrome', 'Application', 'chrome.exe'),
                        ]
                        for cp in chrome_paths:
                            if os.path.exists(cp):
                                driver_kwargs["binary_location"] = cp
                                break

                    self.driver = Driver(**driver_kwargs)

                    # Maximize the window — the OS preserves maximized state
                    # even across SeleniumBase UC reconnects.  For background
                    # mode the window is made transparent AFTER navigation.
                    try:
                        self.driver.maximize_window()
                    except Exception:
                        pass

                    # Attach the window hider to the NEW Chrome window and
                    # hide it immediately so it never appears to the user.
                    if WINDOW_HIDER_AVAILABLE and self._chrome_hider and Config.BROWSER_HEADLESS:
                        new_hwnd = find_new_chrome_hwnd(_pre_chrome_hwnds, timeout=8)
                        if new_hwnd:
                            self._chrome_hider.attach(new_hwnd)
                            self._chrome_hider.hide()
                            self._window_hidden = True
                            print(f"[Checker] Chrome hidden immediately (hwnd {new_hwnd})")
                        else:
                            print("[Checker] Warning: could not find new Chrome window for hider")

                    self._is_seleniumbase = True
                    return True
                except Exception as e:
                    self._log(f"SeleniumBase driver failed: {e}")
                    # Don't set self.driver if initialization failed
                    self.driver = None
                    # Continue to try other driver options below
                finally:
                    os.chdir(original_cwd)
            
            if UNDETECTED_CHROME_AVAILABLE:
                options = uc.ChromeOptions()
                options.add_argument('--log-level=3')
                options.add_argument('--disable-logging')
                options.add_argument('--disable-blink-features=AutomationControlled')
                options.add_argument('--disable-dev-shm-usage')
                options.add_argument('--no-sandbox')
                options.add_experimental_option("prefs", download_prefs)
                # Only use real headless if window hider is unavailable;
                # otherwise Chrome starts visible and is made transparent.
                if Config.BROWSER_HEADLESS and not WINDOW_HIDER_AVAILABLE:
                    options.add_argument('--headless=new')
                    options.add_argument('--window-size=1920,1080')
                options.add_argument('--start-maximized')
                
                # Clean up stale undetected_chromedriver files to prevent
                # [WinError 183] "Cannot create a file when that file already exists"
                try:
                    import shutil
                    uc_appdata = os.path.join(
                        os.environ.get("APPDATA", ""),
                        "undetected_chromedriver",
                    )
                    if os.path.isdir(uc_appdata):
                        for item in os.listdir(uc_appdata):
                            item_path = os.path.join(uc_appdata, item)
                            try:
                                if os.path.isdir(item_path):
                                    shutil.rmtree(item_path, ignore_errors=True)
                                else:
                                    os.remove(item_path)
                            except Exception:
                                pass
                except Exception:
                    pass

                chrome_ver_uc = _get_chrome_major_version()
                # Clear any stale uc binary that may be wrong version
                try:
                    from seleniumbase.undetected.patcher import Patcher as _P2
                    _stale = os.path.join(_P2.data_path, "undetected_chromedriver.exe")
                    if os.path.exists(_stale):
                        os.remove(_stale)
                except Exception:
                    pass
                self.driver = uc.Chrome(options=options, version_main=chrome_ver_uc)
                self.driver.maximize_window()
                if WINDOW_HIDER_AVAILABLE and self._chrome_hider and Config.BROWSER_HEADLESS:
                    new_hwnd = find_new_chrome_hwnd(_pre_chrome_hwnds, timeout=8)
                    if new_hwnd:
                        self._chrome_hider.attach(new_hwnd)
                        self._chrome_hider.hide()
                        self._window_hidden = True
                return True
            
            # Fallback to regular Selenium
            options = Options()
            options.add_argument('--disable-blink-features=AutomationControlled')
            options.add_argument('--disable-dev-shm-usage')
            options.add_argument('--no-sandbox')
            options.add_argument('--disable-gpu')
            options.add_argument('--log-level=3')
            options.add_argument('--disable-logging')
            options.add_experimental_option("prefs", download_prefs)
            # Only use real headless if window hider is unavailable;
            # otherwise Chrome starts visible and is made transparent.
            if Config.BROWSER_HEADLESS and not WINDOW_HIDER_AVAILABLE:
                options.add_argument('--headless=new')
                options.add_argument('--window-size=1920,1080')
            options.add_argument('--start-maximized')
            
            self.driver = webdriver.Chrome(options=options)
            self.driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
            self.driver.maximize_window()
            if WINDOW_HIDER_AVAILABLE and self._chrome_hider and Config.BROWSER_HEADLESS:
                new_hwnd = find_new_chrome_hwnd(_pre_chrome_hwnds, timeout=8)
                if new_hwnd:
                    self._chrome_hider.attach(new_hwnd)
                    self._chrome_hider.hide()
                    self._window_hidden = True
            return True
            
        except Exception as e:
            self._log(f"Error setting up browser: {e}")
            return False
    
    def _cleanup_driver(self):
        """Close browser"""
        # Detach window hider before closing
        if self._chrome_hider:
            self._chrome_hider.detach()
        if self.driver:
            try:
                self.driver.quit()
            except:
                pass
            self.driver = None
        # Always reset so the next cycle can re-hide/resize the new window
        self._window_hidden = False
    
    def _dismiss_alert(self):
        """Dismiss any unexpected browser alert (e.g. reCAPTCHA network errors)."""
        try:
            alert = self.driver.switch_to.alert
            print(f"[Checker] Dismissing browser alert: {alert.text}")
            alert.accept()
            time.sleep(0.5)
            return True
        except Exception:
            return False

    def _handle_cookie_consent(self):
        """Handle Osano cookie consent banner that may block page elements"""
        try:
            # Check if cookie consent banner is present
            osano_selectors = [
                "button.osano-cm-accept-all",
                ".osano-cm-accept-all",
                "button[class*='osano-cm-accept']",
                ".osano-cm-button--type_accept"
            ]
            
            for selector in osano_selectors:
                try:
                    elements = self.driver.find_elements(By.CSS_SELECTOR, selector)
                    if elements and elements[0].is_displayed():
                        self._log("🍪 Dismissing cookie consent banner...")
                        self.driver.execute_script("arguments[0].click();", elements[0])
                        time.sleep(1)
                        return True
                except Exception:
                    continue
            return False
        except Exception:
            return False

    def _wait_random(self, min_sec=1, max_sec=3):
        """Random wait to mimic human behavior"""
        time.sleep(random.uniform(min_sec, max_sec))
    
    # ── reCAPTCHA / Cloudflare / anti-bot helpers ───────────────────

    def _is_cloudflare_challenge_page(self) -> bool:
        """Return True only if the current page is an active Cloudflare challenge.
        Uses page title (most reliable signal) rather than broad keywords that
        also appear on normal pages (e.g. 'cloudflare', 'ray id' in footers)."""
        try:
            title = self.driver.title.lower()
            # These titles are ONLY shown on actual Cloudflare challenge pages
            if any(t in title for t in ["just a moment", "attention required", "one more step", "checking your browser"]):
                return True
            # Also check for the specific challenge-only DOM element
            try:
                self.driver.find_element(By.ID, "cf-challenge-running")
                return True
            except Exception:
                pass
        except Exception:
            pass
        return False

    def _detect_cloudflare(self, max_attempts: int = 2) -> bool:
        """Detect Cloudflare challenge / Turnstile and wait for it to pass.
        Retries with page refresh if challenge doesn't clear.
        """
        for attempt in range(1, max_attempts + 1):
            try:
                if self._is_cloudflare_challenge_page():
                    self._log(f"🛡️ Cloudflare challenge detected (attempt {attempt}/{max_attempts})...")
                    for _ in range(30):  # wait up to 30 seconds
                        time.sleep(1)
                        if not self.is_running:
                            return False
                        if not self._is_cloudflare_challenge_page():
                            self._log("✅ Cloudflare challenge passed")
                            return True
                    
                    # Challenge didn't pass
                    if attempt < max_attempts:
                        self._log("🔄 Cloudflare didn't clear – refreshing page...")
                        self.driver.refresh()
                        self._wait_random(3, 5)
                    else:
                        self._log("❌ Cloudflare challenge did not clear after retries")
                        return False
                else:
                    return True  # No active Cloudflare challenge
            except Exception:
                pass
        return True  # no Cloudflare detected

    def _is_captcha_solved(self) -> bool:
        """Check if the g-recaptcha-response textarea already has a token."""
        try:
            token = self.driver.execute_script(
                "var el = document.getElementById('g-recaptcha-response'); "
                "return el ? el.value : '';"
            )
            return bool(token and len(token) > 20)
        except Exception:
            return False

    def _wait_for_captcha_token(self, timeout: int = 15) -> bool:
        """Poll until the g-recaptcha-response token appears."""
        for _ in range(timeout * 2):
            if self._is_captcha_solved():
                return True
            time.sleep(0.5)
        return False

    def _handle_recaptcha(self, attempt: int = 1) -> bool:
        """
        Full reCAPTCHA v2 solver:
        1. Detect CAPTCHA; bail early if not present.
        2. Click the checkbox in the anchor iframe.
        3. If checkbox alone solves it -> done.
        4. Try AI image solver (Gemini Vision) if API key configured.
        4. Audio challenge solved with Google Speech API.
        Retries up to 3 times with increasing delays.
        """
        MAX_ATTEMPTS = 3
        try:
            # Bail out immediately if monitoring was stopped
            if not self.is_running:
                return False

            # ── 0. Cloudflare / Turnstile pre-check ─────────────────
            self._detect_cloudflare()

            # ── 1. Is there even a CAPTCHA? ─────────────────────────
            recaptcha_present = self.driver.find_elements(
                By.CSS_SELECTOR,
                "iframe[src*='recaptcha'], iframe[title='reCAPTCHA'], "
                ".g-recaptcha, #it-recaptcha-here"
            )
            if not recaptcha_present:
                return True  # nothing to solve

            if self._is_captcha_solved():
                return True

            self._log(f"🔓 reCAPTCHA detected – solving (attempt {attempt}/{MAX_ATTEMPTS})...")

            # ── 2. Click the checkbox ───────────────────────────────
            anchor_frame = None
            for frame in self.driver.find_elements(By.CSS_SELECTOR, "iframe[src*='recaptcha']"):
                src = frame.get_attribute("src") or ""
                if "anchor" in src:
                    anchor_frame = frame
                    break

            if anchor_frame:
                self.driver.switch_to.frame(anchor_frame)
                self._wait_random(0.5, 1.0)
                try:
                    cb = WebDriverWait(self.driver, 8).until(
                        EC.element_to_be_clickable((By.CSS_SELECTOR, "#recaptcha-anchor"))
                    )
                    self.driver.execute_script("arguments[0].click();", cb)
                    self._wait_random(2, 4)

                    # Check if checkbox alone solved it
                    try:
                        self.driver.find_element(
                            By.CSS_SELECTOR,
                            ".recaptcha-checkbox-checked, [aria-checked='true']"
                        )
                        self.driver.switch_to.default_content()
                        if self._wait_for_captcha_token(5):
                            self._log("✅ reCAPTCHA auto-passed (no challenge)!")
                            return True
                    except Exception:
                        pass
                except Exception:
                    pass

                # Always return to default before looking for bframe
                self.driver.switch_to.default_content()
            else:
                self._log("⚠️ Anchor iframe not found – trying challenge directly")

            self._wait_random(1, 2)

            # ── 3. Find the challenge (bframe) iframe ───────────────
            challenge_frame = None
            for frame in self.driver.find_elements(By.CSS_SELECTOR, "iframe[src*='recaptcha']"):
                src = frame.get_attribute("src") or ""
                if "bframe" in src:
                    challenge_frame = frame
                    break

            if not challenge_frame:
                self._log("❌ Challenge iframe not found")
                return False

            self.driver.switch_to.frame(challenge_frame)
            self._wait_random(0.5, 1)

            # ── 4. Check for Google "automated queries" block BEFORE trying audio ──
            try:
                page_body = self.driver.find_element(By.TAG_NAME, "body").text.lower()
                if "automated queries" in page_body or "unusual traffic" in page_body:
                    self._log("❌ Google detected automation — blocked by rate-limit")
                    self.driver.switch_to.default_content()
                    if attempt < MAX_ATTEMPTS:
                        wait_time = 10 * attempt
                        self._log(f"🔄 Waiting {wait_time}s before retry (cooldown)...")
                        time.sleep(wait_time)
                        return self._handle_recaptcha(attempt + 1)
                    return False
            except Exception:
                pass

            # ── 5. Switch to audio challenge ────────────────────────
            try:
                # First check if audio button exists at all
                audio_btns = self.driver.find_elements(By.CSS_SELECTOR, "#recaptcha-audio-button, button.rc-button-audio")
                self._log(f"🔍 Found {len(audio_btns)} audio button(s)")
                
                audio_btn = WebDriverWait(self.driver, 10).until(
                    EC.element_to_be_clickable(
                        (By.CSS_SELECTOR, "#recaptcha-audio-button, button.rc-button-audio")
                    )
                )
                self._log("🔊 Clicking audio challenge button...")
                self.driver.execute_script("arguments[0].click();", audio_btn)
                
                # Check for and dismiss any alerts (e.g., "Cannot contact reCAPTCHA")
                try:
                    from selenium.webdriver.support.ui import WebDriverWait as WDW
                    from selenium.webdriver.support import expected_conditions as EC_Alert
                    alert = WDW(self.driver, 2).until(EC_Alert.alert_is_present())
                    alert_text = alert.text
                    print(f"[Checker] reCAPTCHA alert dismissed: {alert_text}")
                    alert.accept()
                    # Wait a bit after dismissing alert
                    time.sleep(2)
                except Exception:
                    pass  # No alert, continue normally
                
                self._wait_random(3, 5)  # Wait for audio to load
            except Exception as e:
                print(f"[Checker] Audio button not found or not clickable: {e}")

            # After clicking audio, the bframe content may reload.
            # Switch back to default and re-enter the bframe to get fresh DOM.
            self.driver.switch_to.default_content()
            self._wait_random(1, 2)

            challenge_frame = None
            for frame in self.driver.find_elements(By.CSS_SELECTOR, "iframe[src*='recaptcha']"):
                src = frame.get_attribute("src") or ""
                if "bframe" in src:
                    challenge_frame = frame
                    break

            if not challenge_frame:
                self._log("❌ Challenge iframe lost after audio click")
                if attempt < MAX_ATTEMPTS:
                    self._log("🔄 Retrying in 3s...")
                    time.sleep(3)
                    return self._handle_recaptcha(attempt + 1)
                return False

            self.driver.switch_to.frame(challenge_frame)
            self._wait_random(1, 2)  # Increased wait for audio UI to fully load

            # Check for "automated queries" block
            try:
                err_el = self.driver.find_element(By.CSS_SELECTOR, ".rc-audiochallenge-error-message")
                if err_el and err_el.is_displayed():
                    self._log("❌ Google blocked audio challenges (rate-limited)")
                    self.driver.switch_to.default_content()
                    if attempt < MAX_ATTEMPTS:
                        self._log("🔄 Waiting 5s before retry...")
                        time.sleep(5)
                        return self._handle_recaptcha(attempt + 1)
                    return False
            except Exception:
                pass

            # ── 6. Get the audio URL ────────────────────────────────
            audio_url = None

            # Wait for audio challenge to fully load (audio src takes a moment)
            for _poll in range(30):  # up to 15 seconds
                # Strategy 1: <audio id="audio-source"> with src attribute
                try:
                    audio_el = self.driver.find_element(By.CSS_SELECTOR, "#audio-source")
                    audio_url = audio_el.get_attribute("src")
                    if audio_url and audio_url.startswith("http"):
                        break
                    audio_url = None
                except Exception:
                    pass

                # Strategy 2: <source> element inside the <audio> tag
                try:
                    source_el = self.driver.find_element(By.CSS_SELECTOR, "#audio-source source, audio source")
                    src = source_el.get_attribute("src")
                    if src and src.startswith("http"):
                        audio_url = src
                        break
                except Exception:
                    pass

                # Strategy 3: download link
                try:
                    dl_link = self.driver.find_element(By.CSS_SELECTOR, ".rc-audiochallenge-tdownload-link")
                    href = dl_link.get_attribute("href")
                    if href and href.startswith("http"):
                        audio_url = href
                        break
                except Exception:
                    pass

                time.sleep(0.5)

            if not audio_url:
                # Show any specific reCAPTCHA error to user
                try:
                    err_msgs = self.driver.find_elements(By.CSS_SELECTOR, ".rc-audiochallenge-error-message, .rc-doscaptcha-header")
                    for em in err_msgs:
                        if em.text:
                            self._log(f"❌ reCAPTCHA: {em.text[:120]}")
                except Exception:
                    pass

                self.driver.switch_to.default_content()
                self._log("❌ Audio source element not found")
                if attempt < MAX_ATTEMPTS:
                    self._log("🔄 Retrying in 3s...")
                    time.sleep(3)
                    return self._handle_recaptcha(attempt + 1)
                return False

            self._log("✅ Audio challenge URL found, downloading...")

            # ── 7. Download, enhance, transcribe ────────────────────
            transcript = self._transcribe_audio(audio_url)
            if not transcript:
                self.driver.switch_to.default_content()
                if attempt < MAX_ATTEMPTS:
                    self._log("🔄 Transcription failed – retrying in 3s...")
                    time.sleep(3)
                    return self._handle_recaptcha(attempt + 1)
                self._log("❌ Transcription failed after all attempts")
                return False

            # ── 8. Type answer & verify ─────────────────────────────
            # Re-enter bframe (transcribe_audio may have switched to default)
            try:
                self.driver.switch_to.default_content()
                for frame in self.driver.find_elements(By.CSS_SELECTOR, "iframe[src*='recaptcha']"):
                    src = frame.get_attribute("src") or ""
                    if "bframe" in src:
                        self.driver.switch_to.frame(frame)
                        break
            except Exception:
                pass

            try:
                answer_input = WebDriverWait(self.driver, 5).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, "#audio-response"))
                )
                # Inject via JS — immune to user keyboard interference in
                # the background/transparent window mode.
                self.driver.execute_script(
                    "arguments[0].focus(); arguments[0].value = arguments[1];"
                    "arguments[0].dispatchEvent(new Event('input', {bubbles:true}));"
                    "arguments[0].dispatchEvent(new Event('change', {bubbles:true}));",
                    answer_input, transcript
                )
                self._wait_random(0.5, 1)
            except Exception as e:
                self._log(f"❌ Could not type answer: {e}")
                self.driver.switch_to.default_content()
                return False

            try:
                verify_btn = self.driver.find_element(By.CSS_SELECTOR, "#recaptcha-verify-button")
                self.driver.execute_script("arguments[0].click();", verify_btn)
                self._wait_random(2, 4)
            except Exception as e:
                self._log(f"❌ Could not click verify: {e}")
                self.driver.switch_to.default_content()
                return False

            self.driver.switch_to.default_content()

            # ── 8. Confirm success ──────────────────────────────────
            if self._wait_for_captcha_token(10):
                self._log("✅ reCAPTCHA solved via audio!")
                return True

            # Token not set – might have gotten a new challenge
            if attempt < MAX_ATTEMPTS:
                self._log("🔄 Answer not accepted – retrying in 3s...")
                time.sleep(3)
                return self._handle_recaptcha(attempt + 1)

            self._log("❌ Could not solve CAPTCHA after multiple attempts. Please check your internet connection.")
            return False

        except Exception as e:
            if not self.is_running:
                return False  # monitoring stopped, suppress error
            
            # User-friendly error messages
            error_str = str(e).lower()
            if "session deleted" in error_str or "disconnected" in error_str or "devtools" in error_str:
                self._log("❌ Connection interrupted. Please check your internet connection and try again.")
            elif "timeout" in error_str or "timed out" in error_str:
                self._log("❌ Network is too slow. Please connect to a better network or try again later.")
            else:
                self._log(f"❌ CAPTCHA solving failed. Please check your connection and try again.")
            
            try:
                self.driver.switch_to.default_content()
            except Exception:
                pass
            return False

    # ── Audio transcription with Google Speech API ────────────

    def _transcribe_with_google(self, wav_path: str) -> str | None:
        """Transcribe audio using Google Web Speech API (online, free)."""
        if not SR_AVAILABLE:
            return None
        
        # Verify file exists before attempting transcription
        if not os.path.exists(wav_path):
            self._log(f"⚠️ Google: WAV file not found at {wav_path}")
            return None
        
        try:
            import speech_recognition as _sr
            recognizer = _sr.Recognizer()
            # Adjust for noise
            with _sr.AudioFile(wav_path) as source:
                recognizer.adjust_for_ambient_noise(source, duration=0.5)
            with _sr.AudioFile(wav_path) as source:
                audio_data = recognizer.record(source)
            text = recognizer.recognize_google(audio_data).strip()
            if text:
                self._log(f"🔊 Google raw: \"{text}\"")
                text = self._clean_transcript(text)
                self._log(f"🔊 Google cleaned: \"{text}\"")
            return text if text else None
        except Exception as e:
            self._log(f"⚠️ Google transcription error: {e}")
            return None

    @staticmethod
    def _clean_transcript(text: str) -> str:
        """
        Clean transcription output for reCAPTCHA audio answer.
        Removes punctuation and normalizes.
        """
        import re
        cleaned = text.lower().strip()
        
        # Remove all punctuation except spaces
        cleaned = re.sub(r'[^\w\s]', '', cleaned)
        # Collapse multiple spaces
        cleaned = re.sub(r'\s+', ' ', cleaned).strip()
        
        # Convert spoken digits to numbers if the whole thing is digit words
        word_to_digit = {
            'zero': '0', 'one': '1', 'two': '2', 'three': '3',
            'four': '4', 'five': '5', 'six': '6', 'seven': '7',
            'eight': '8', 'nine': '9',
        }
        words = cleaned.split()
        if all(w in word_to_digit for w in words):
            cleaned = ''.join(word_to_digit[w] for w in words)
        
        return cleaned

    def _enhance_audio(self, mp3_path: str) -> str:
        """
        Convert MP3 to WAV with audio enhancement.
        Uses ffmpeg directly via subprocess (bypasses pydub's broken path resolution).
        - Convert to mono 16kHz WAV (optimal for speech recognition)
        - Normalize volume
        Returns path to the WAV file.
        """
        wav_path = os.path.splitext(mp3_path)[0] + ".wav"
        
        try:
            import imageio_ffmpeg
            import subprocess
            
            ffmpeg_exe = imageio_ffmpeg.get_ffmpeg_exe()
            self._log(f"🎵 Using ffmpeg from: {ffmpeg_exe}")
            self._log(f"🎵 Converting {os.path.basename(mp3_path)} to WAV...")
            
            # Call ffmpeg directly: convert to mono 16kHz WAV with volume normalization
            cmd = [
                ffmpeg_exe,
                "-y",              # overwrite output
                "-i", mp3_path,    # input file
                "-ac", "1",        # mono
                "-ar", "16000",    # 16kHz sample rate
                "-af", "loudnorm", # normalize volume
                wav_path           # output file
            ]
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=30,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
            )
            
            if result.returncode == 0 and os.path.exists(wav_path):
                self._log(f"✅ Audio converted successfully")
            else:
                self._log(f"⚠️ ffmpeg returned code {result.returncode}")
                self._log(f"⚠️ ffmpeg stderr: {result.stderr[:200]}")
                # Try basic conversion without filters
                cmd_basic = [
                    ffmpeg_exe, "-y", "-i", mp3_path, wav_path
                ]
                result2 = subprocess.run(
                    cmd_basic,
                    capture_output=True,
                    text=True,
                    timeout=30,
                    creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
                )
                if result2.returncode == 0 and os.path.exists(wav_path):
                    self._log(f"✅ Basic audio conversion successful")
                else:
                    self._log(f"⚠️ Basic conversion also failed: {result2.stderr[:200]}")
                    return ""
        except Exception as e:
            self._log(f"⚠️ Audio conversion failed: {e}")
            import traceback
            self._log(f"⚠️ Traceback: {traceback.format_exc()[:200]}")
            return ""
        return wav_path

    def _transcribe_audio(self, audio_url: str) -> str | None:
        """Download reCAPTCHA audio and transcribe using Google Web Speech API."""
        tmp_mp3 = tmp_wav = None
        try:
            # Download audio — prefer Selenium XHR inside the bframe
            # (same origin as recaptcha.net, avoids CORS & DNS issues),
            # then fall back to requests.
            audio_bytes = None

            # ─ Attempt 1: XHR inside the reCAPTCHA bframe (same origin) ─
            try:
                # Make sure we are inside the bframe iframe (same-origin with recaptcha.net)
                self.driver.switch_to.default_content()
                for frame in self.driver.find_elements(By.CSS_SELECTOR, "iframe[src*='recaptcha']"):
                    src = frame.get_attribute("src") or ""
                    if "bframe" in src:
                        self.driver.switch_to.frame(frame)
                        break

                js = (
                    "var cb = arguments[arguments.length - 1];"
                    "var xhr = new XMLHttpRequest();"
                    "xhr.open('GET', arguments[0], true);"
                    "xhr.responseType = 'arraybuffer';"
                    "xhr.onload = function() {"
                    "  if (xhr.status === 200) {"
                    "    var b = new Uint8Array(xhr.response);"
                    "    var s = '';"
                    "    for (var i = 0; i < b.length; i++) s += String.fromCharCode(b[i]);"
                    "    cb(btoa(s));"
                    "  } else { cb(null); }"
                    "};"
                    "xhr.onerror = function() { cb(null); };"
                    "xhr.send();"
                )
                b64 = self.driver.execute_async_script(js, audio_url)
                if b64:
                    import base64
                    audio_bytes = base64.b64decode(b64)
                    self._log("✅ Audio downloaded via browser XHR")
            except Exception as xhr_err:
                self._log(f"⚠️ Browser XHR download failed: {xhr_err}")

            # ─ Attempt 2: XHR from default_content (may work if same session) ─
            if not audio_bytes:
                try:
                    self.driver.switch_to.default_content()
                    js = (
                        "return fetch(arguments[0]).then(r=>r.arrayBuffer())"
                        ".then(buf=>{var b=new Uint8Array(buf),s='';"
                        "for(var i=0;i<b.length;i++)s+=String.fromCharCode(b[i]);"
                        "return btoa(s);});"
                    )
                    b64 = self.driver.execute_async_script(
                        "var cb=arguments[arguments.length-1];"
                        + js.replace("return ", "").replace(";}", ";}").rstrip(";") +
                        ".then(r=>cb(r)).catch(e=>cb(null));",
                        audio_url
                    )
                    if b64:
                        import base64
                        audio_bytes = base64.b64decode(b64)
                        self._log("✅ Audio downloaded via fetch fallback")
                except Exception:
                    pass

            # ─ Attempt 3: plain requests download (last resort) ─
            if not audio_bytes:
                try:
                    # Use browser cookies for the request
                    cookies = {c['name']: c['value'] for c in self.driver.get_cookies()}
                    resp = http_requests.get(
                        audio_url, timeout=30, cookies=cookies,
                        headers={'User-Agent': self.driver.execute_script('return navigator.userAgent')}
                    )
                    resp.raise_for_status()
                    audio_bytes = resp.content
                    self._log("✅ Audio downloaded via requests")
                except Exception as e:
                    self._log(f"⚠️ Audio download failed: {e}")
                    return None

            with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as f:
                f.write(audio_bytes)
                tmp_mp3 = f.name

            # Convert & enhance - try runtime import if module flag is False
            pydub_ok = PYDUB_AVAILABLE
            if not pydub_ok:
                try:
                    from pydub import AudioSegment as _test
                    pydub_ok = True
                except ImportError:
                    pass
            
            if not pydub_ok:
                self._log("❌ pydub/ffmpeg not available – install: pip install pydub")
                return None

            tmp_wav = self._enhance_audio(tmp_mp3)
            if not tmp_wav or not os.path.exists(tmp_wav):
                self._log("❌ Audio conversion failed")
                return None

            # Transcribe with Google Speech API
            try:
                text = self._transcribe_with_google(tmp_wav)
                if text:
                    return text
            except Exception as google_err:
                self._log(f"⚠️ Google transcription error: {google_err}")

            self._log("❌ Transcription failed. Please check your internet connection.")
            return None

        except Exception as e:
            self._log(f"⚠️ Audio download/transcription error: {e}")
            return None
        finally:
            for p in (tmp_mp3, tmp_wav):
                if p:
                    try:
                        os.unlink(p)
                    except Exception:
                        pass


    def _handle_application_error(self, max_retries: int = 3) -> bool:
        """
        Detect the TLS "Application error: a client-side exception has occurred"
        and attempt recovery by reloading immediately.
        Returns True if page is OK (no error or recovered), False if error persists.
        """
        try:
            page_text = self.driver.page_source.lower()
        except Exception:
            return True  # Assume OK if can't read page

        if "application error" not in page_text and "client-side exception" not in page_text:
            return True  # No error detected - page is OK

        self._log("⚠️ Application error detected – reloading immediately...")

        for attempt in range(max_retries):
            # Immediate reload - no delays
            try:
                self.driver.refresh()
                self._wait_random(2, 3)  # Minimal wait for page load
                new_source = self.driver.page_source.lower()
                if "application error" not in new_source and "client-side exception" not in new_source:
                    self._log("✅ Recovered from application error")
                    return True
            except Exception:
                pass

            # If reload didn't work, try back then forward
            if attempt >= 1:
                try:
                    self.driver.back()
                    self._wait_random(1, 2)
                    self.driver.forward()
                    self._wait_random(2, 3)
                    new_source = self.driver.page_source.lower()
                    if "application error" not in new_source and "client-side exception" not in new_source:
                        self._log("✅ Recovered from application error (back+forward)")
                        return True
                except Exception:
                    pass

        self._log("❌ Could not recover from application error")
        return False  # Error persists

    def _login(self, email: str, password: str, branch_url: str = None, service_type: str = "legalization", is_retry: bool = False) -> tuple[bool, str]:
        """Login to TLS website. Returns (success, error_message)"""
        try:
            # Safety check: ensure driver is initialized
            if not self.driver:
                self._log("❌ Browser driver not initialized!")
                return False, "DRIVER_ERROR: Browser failed to start. Please restart the application."
            
            # Check if monitoring was stopped before starting login
            if not self.is_running:
                return False, "STOPPED: Monitoring was stopped"

            target_url = branch_url or Config.TLS_URL
            label = "Visa" if service_type == "visa" else "Legalization"
            if not is_retry:
                self._log(f"Opening TLS {label} website...")

            # Use SeleniumBase's UC-specific open method when available.
            # uc_open_with_reconnect disconnects CDP during page load so
            # Cloudflare Turnstile cannot detect automation, then reconnects.
            if self._is_seleniumbase:
                try:
                    self.driver.uc_open_with_reconnect(target_url, reconnect_time=4)
                    self._wait_random(2, 3)
                    # UC mode handles Cloudflare Turnstile automatically via
                    # uc_open_with_reconnect. No manual click needed.
                except Exception:
                    # Fallback to regular get if UC method not available
                    self.driver.get(target_url)
                    self._wait_random(4, 6)
            else:
                self.driver.get(target_url)
                self._wait_random(4, 6)

            # Check again after page load
            if not self.is_running:
                return False, "STOPPED: Monitoring was stopped"

            # Dismiss any unexpected alerts before proceeding
            self._dismiss_alert()

            # Check for Cloudflare / Turnstile challenge.
            # When UC mode opened the URL, uc_open_with_reconnect already bypassed
            # Cloudflare. We still verify the title just in case it wasn't fully solved.
            if self._is_cloudflare_challenge_page():
                self._log("🛡️ Cloudflare still active after UC open – waiting...")
                if not self._detect_cloudflare(max_attempts=2):
                    return False, "CLOUDFLARE_TIMEOUT: Cloudflare challenge did not pass. Will retry after interval."
            
            # Handle cookie consent banner (may block Login button)
            self._handle_cookie_consent()

            # ── Restore window state after uc_open_with_reconnect ───────────
            # uc_open_with_reconnect disconnects/reconnects CDP which resets
            # window size to 800x600. We must fix this AFTER navigation.
            # Chrome stays FULLY VISIBLE (though transparent in invisible mode)
            # so that reCAPTCHA and Cloudflare see a real browser.
            # Chrome is made transparent AFTER login succeeds.
            try:
                self.driver.execute_cdp_cmd(
                    "Emulation.setDeviceMetricsOverride",
                    {"width": 1920, "height": 1080,
                     "deviceScaleFactor": 1, "mobile": False},
                )
            except Exception:
                pass
            try:
                self.driver.set_window_size(1920, 1080)
                self.driver.maximize_window()
            except Exception:
                pass

            # Handle "Application error: a client-side exception has occurred"
            if not self._handle_application_error():
                return False, "APPLICATION_ERROR: Page failed to load properly. Will retry immediately."

            # Check for maintenance page
            try:
                maintenance_div = self.driver.find_element(By.CSS_SELECTOR, ".maintenance_center")
                if maintenance_div:
                    self._log("⚠️ TLS website is under maintenance")
                    return False, "MAINTENANCE: TLS website is temporarily unavailable for maintenance. Will retry after interval."
            except:
                pass  # No maintenance page, continue normally
            
            # Find and click Login button
            try:
                # Handle cookie consent again before looking for button
                self._handle_cookie_consent()
                
                wait = WebDriverWait(self.driver, 10)
                try:
                    wait.until(lambda d: d.execute_script("return document.readyState") in ["interactive", "complete"])
                except Exception:
                    pass

                # Try new TlsButton selector first, then fall back to legacy
                login_selectors = [
                    "span.TlsButton_tls-button__syUS5",
                    "[class*='TlsButton'][class*='--outline']",
                    "a.tls-button-link",
                ]
                login_found = False

                for selector in login_selectors:
                    login_links = self.driver.find_elements(By.CSS_SELECTOR, selector)
                    for link in login_links:
                        if link.text.strip().upper() == 'LOGIN':
                            self.driver.execute_script("arguments[0].click();", link)
                            login_found = True
                            break
                    if login_found:
                        break

                if not login_found:
                    self._log("⏳ Page still loading... waiting for Login button")
                    # Handle cookie consent one more time
                    self._handle_cookie_consent()
                    
                    wait = WebDriverWait(self.driver, 40)
                    # Wait for any of the possible selectors
                    wait.until(lambda d: d.find_elements(By.CSS_SELECTOR, ", ".join(login_selectors)))
                    for selector in login_selectors:
                        login_links = self.driver.find_elements(By.CSS_SELECTOR, selector)
                        for link in login_links:
                            if link.text.strip().upper() == 'LOGIN':
                                self.driver.execute_script("arguments[0].click();", link)
                                login_found = True
                                break
                        if login_found:
                            break

                if not login_found:
                    # Try fallback: SVG user icon (shown on smaller viewports).
                    # Clicking it opens a dropdown — we then find and click the
                    # Login link inside that dropdown.
                    try:
                        icon_svg = self.driver.find_element(By.CSS_SELECTOR, "svg[aria-label='User icon']")
                        login_button = icon_svg.find_element(By.XPATH, "..")
                        self.driver.execute_script("arguments[0].click();", login_button)
                        self._log("✓ Clicked SVG icon login button")
                        time.sleep(1.5)  # wait for dropdown to open
                        # Look for Login link inside the opened dropdown
                        try:
                            login_link = self.driver.find_element(
                                By.XPATH,
                                "//*[normalize-space(text())='LOGIN' or "
                                "normalize-space(text())='Login' or "
                                "normalize-space(text())='Log in']"
                            )
                            self.driver.execute_script("arguments[0].click();", login_link)
                            login_found = True
                            self._log("✓ Clicked Login link in dropdown")
                        except Exception:
                            # Dropdown didn't have a direct Login link;
                            # the icon click may have navigated directly
                            login_found = True
                    except Exception:
                        pass

                if not login_found:
                    # Try another fallback: div with id="login"
                    try:
                        login_div = self.driver.find_element(By.CSS_SELECTOR, "div[id='login']")
                        self.driver.execute_script("arguments[0].click();", login_div)
                        login_found = True
                        self._log("✓ Clicked login div")
                    except Exception:
                        pass

                if not login_found:
                    # Dump diagnostic info for debugging
                    try:
                        page_title = self.driver.title
                        current_url = self.driver.current_url
                        body_text = self.driver.find_element(By.TAG_NAME, "body").text[:500]
                        self._log(f"❌ Login button not found. Page title: '{page_title}'")
                        self._log(f"   URL: {current_url}")
                        self._log(f"   Body preview: {body_text[:200]}")
                    except Exception:
                        self._log("❌ Login button still not found after extended wait")
                    # Take screenshot for debugging
                    try:
                        self.driver.save_screenshot(f"login_button_not_found_{int(time.time())}.png")
                    except Exception:
                        pass
                    return False, "PAGE_NOT_LOADED: Login button not found. The TLS website may be slow or down."
            except Exception as e:
                # Dismiss any alert that might be blocking (e.g. reCAPTCHA network error)
                self._dismiss_alert()
                return False, f"PAGE_NOT_LOADED: Could not find login button. Website may be loading slowly. ({str(e)[:80]})"
            
            self._wait_random(3, 5)
            
            # Handle cookie consent on login page
            self._handle_cookie_consent()
            
            # Fill credentials
            self._log("Logging in...")
            try:
                # Try new selectors first, fall back to legacy
                email_field = None
                password_field = None
                for eid in ["#email-input-field", "#username"]:
                    try:
                        email_field = self.driver.find_element(By.CSS_SELECTOR, eid)
                        break
                    except:
                        pass
                for pid in ["#password-input-field", "#password"]:
                    try:
                        password_field = self.driver.find_element(By.CSS_SELECTOR, pid)
                        break
                    except:
                        pass
                if not email_field or not password_field:
                    raise Exception("fields not found")
            except Exception as e:
                return False, "PAGE_NOT_LOADED: Login form not found. Website may be loading slowly. Will retry immediately."
            
            # Use JavaScript to set values directly — avoids any risk of the
            # user's keyboard input interfering with the hidden browser window.
            self.driver.execute_script(
                "arguments[0].focus(); arguments[0].value = arguments[1];"
                "arguments[0].dispatchEvent(new Event('input', {bubbles:true}));"
                "arguments[0].dispatchEvent(new Event('change', {bubbles:true}));",
                email_field, email
            )
            self._wait_random(0.5, 1)

            self.driver.execute_script(
                "arguments[0].focus(); arguments[0].value = arguments[1];"
                "arguments[0].dispatchEvent(new Event('input', {bubbles:true}));"
                "arguments[0].dispatchEvent(new Event('change', {bubbles:true}));",
                password_field, password
            )
            self._wait_random(0.5, 1)
            
            # Handle reCAPTCHA if present
            captcha_solved = self._handle_recaptcha()
            if not captcha_solved:
                if not self.is_running:
                    return False, "STOPPED: Monitoring was stopped by user."
                return False, "CAPTCHA_TIMEOUT: Unable to solve CAPTCHA. This could be due to slow internet or high website traffic. Please ensure you have a stable connection and try again later."
            
            # Click login button (new or legacy selector)
            login_button = None
            for btn_sel in ["#btn-login", "#kc-login"]:
                try:
                    login_button = self.driver.find_element(By.CSS_SELECTOR, btn_sel)
                    break
                except:
                    pass
            if not login_button:
                return False, "PAGE_NOT_LOADED: Login button not found on form."

            # Use JS click — avoids "element click intercepted" errors caused by
            # overlays or the transparent-window layer covering the button.
            self.driver.execute_script("arguments[0].click();", login_button)
            self._wait_random(4, 6)

            # Wait for redirect to complete (visa site can be slower)
            try:
                WebDriverWait(self.driver, 10).until(
                    lambda d: not any(x in d.current_url.lower() for x in [
                        "openid-connect/auth", "kc-login", "/auth/realms/"
                    ])
                )
            except TimeoutException:
                pass  # Continue checks below
            
            # Check for error message (try specific selectors first)
            try:
                for err_sel in ["#kc-feedback-text", ".kc-feedback-text", ".alert-error", ".error-message",
                                "#input-error", ".kc-error-message"]:
                    try:
                        error_element = self.driver.find_element(By.CSS_SELECTOR, err_sel)
                        error_text = error_element.text.strip()
                        if error_text and ("invalid" in error_text.lower() or "incorrect" in error_text.lower() 
                                          or "wrong" in error_text.lower() or "failed" in error_text.lower()
                                          or "account" in error_text.lower()):
                            return False, "INVALID_CREDENTIALS: Your TLS email or password is incorrect. Please update your credentials."
                    except:
                        pass
            except:
                pass
            
            # Verify login actually succeeded by checking if we left the login page
            try:
                current_url = self.driver.current_url.lower()
                page_source = self.driver.page_source.lower()
                
                # Still on login/auth page = login failed
                still_on_login = (
                    "/login" in current_url or 
                    "/auth/" in current_url or
                    "kc-login" in current_url or
                    "openid-connect" in current_url
                )
                
                # Check for login form still present
                login_form_present = False
                try:
                    for field_sel in ["#email-input-field", "#username", "#password-input-field", "#password"]:
                        try:
                            el = self.driver.find_element(By.CSS_SELECTOR, field_sel)
                            if el.is_displayed():
                                login_form_present = True
                                break
                        except:
                            pass
                except:
                    pass
                
                # Check page text for error indicators
                error_in_page = any(indicator in page_source for indicator in [
                    "invalid username or password",
                    "invalid credentials",
                    "incorrect password",
                    "authentication failed",
                    "login failed",
                    "account is not fully set up",
                    "invalid email or password",
                ])
                
                if error_in_page:
                    return False, "INVALID_CREDENTIALS: Your TLS email or password is incorrect. Please update your credentials."
                
                if still_on_login and login_form_present:
                    return False, "INVALID_CREDENTIALS: Login failed. The TLS website did not accept your credentials. Please check your email and password."
                
            except Exception:
                pass  # If URL check fails, continue optimistically
            
            self._log("✅ Login successful")
            return True, ""
            
        except Exception as e:
            error_msg = str(e)
            if "no such element" in error_msg.lower():
                return False, "PAGE_NOT_LOADED: Website elements not found. TLS website may be slow. Will retry immediately."
            return False, f"LOGIN_ERROR: {error_msg[:100]}"
    
    def _navigate_to_booking(self, service_type: str = "legalization") -> bool:
        """Navigate to appointment booking page via group select + continue"""
        try:
            wait = WebDriverWait(self.driver, 20)

            # Handle Application error on the page
            self._handle_application_error()

            # Dismiss cookie banner if present
            try:
                cookie_buttons = self.driver.find_elements(By.CSS_SELECTOR, "button")
                for btn in cookie_buttons:
                    text = btn.text.strip().lower()
                    if text in {"accept all", "accept", "save"}:
                        self.driver.execute_script("arguments[0].click();", btn)
                        self._wait_random(0.5, 1)
                        break
            except Exception:
                pass

            # --- Step 1: Click "Select" on the group table ---
            self._log("Selecting group...")
            
            # Check for "No application created" message — user needs to create one on TLS website
            # Use very specific strings that only appear on the actual empty-application page,
            # not on normal pages. Also verify no select button exists to avoid false positives.
            try:
                page_text = self.driver.page_source.lower()
                # Only the most specific phrases that uniquely identify the "no application" page
                no_app_indicators = [
                    "no application created",
                    "click on the button to create a new application",
                    "you don't have any application",
                    "vous n'avez pas de dossier",   # French version
                ]
                indicator_found = any(ind in page_text for ind in no_app_indicators)
                if indicator_found:
                    # Double-check: if a select/enter button IS present, the application exists
                    # and the indicator was a false positive in some other page text
                    has_select_btn = bool(
                        self.driver.find_elements(By.CSS_SELECTOR,
                            "button[name='formGroupId'], button.tls-button-primary")
                    )
                    if not has_select_btn:
                        self._log("❌ No application found on TLS website")
                        if self.on_status_update:
                            self.on_status_update("SHOW_NO_APPLICATION_ERROR")
                        self.is_running = False
                        return False
            except Exception:
                pass

            select_btn = None
            try:
                # New TLS layout: button with name="formGroupId" and TlsButton class
                select_btn = wait.until(EC.element_to_be_clickable(
                    (By.CSS_SELECTOR, "button[name='formGroupId'].TlsButton_tls-button__syUS5")
                ))
            except Exception:
                # Fallback: any button containing "Select" text
                try:
                    buttons = self.driver.find_elements(By.CSS_SELECTOR, "button")
                    for btn in buttons:
                        if btn.text.strip().lower() == "select":
                            select_btn = btn
                            break
                except Exception:
                    pass

            if not select_btn:
                # Legacy fallback: old Enter button
                try:
                    select_btn = self.driver.find_element(By.CSS_SELECTOR, "button.tls-button-primary.button-neo-inside")
                except Exception:
                    self._log("❌ Select / Enter button not found.")
                    return False

            self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", select_btn)
            self._wait_random(0.5, 1)
            self.driver.execute_script("arguments[0].click();", select_btn)
            self._wait_random(3, 5)

            # Handle Application error after selecting group - critical checkpoint
            if not self._handle_application_error():
                self._log("⚠️ Application error after group selection - will retry")
                return False

            # --- Step 2: Click "Continue" (book appointment) ---
            # Visa flow goes straight to appointment page after group select; skip Continue.
            if service_type == "visa":
                self._log("📋 Group selected – loading appointments...")
                # Visa site needs extra time after group selection
                self._wait_random(4, 6)
            else:
                self._log("Clicking Continue...")
                continue_btn = None
                try:
                    continue_btn = wait.until(EC.element_to_be_clickable(
                        (By.CSS_SELECTOR, "a#book-appointment-btn")
                    ))
                except Exception:
                    # Fallback: any <a> or button with "Continue" or "Book" text
                    try:
                        for el in self.driver.find_elements(By.CSS_SELECTOR, "a, button"):
                            txt = el.text.strip().lower()
                            if txt in ("continue", "book appointment"):
                                continue_btn = el
                                break
                    except Exception:
                        pass

                if not continue_btn:
                    # Legacy fallback
                    try:
                        continue_btn = self.driver.find_element(By.CSS_SELECTOR, "button.button-neo-inside.-primary")
                    except Exception:
                        self._log("❌ Continue / Book appointment button not found.")
                        return False

                self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", continue_btn)
                self._wait_random(0.5, 1)
                self.driver.execute_script("arguments[0].click();", continue_btn)
                self._wait_random(3, 5)

            # Handle Application error after Continue / group select
            if not self._handle_application_error():
                self._log("⚠️ Application error persists - will retry navigation")
                return False

            # Verify we landed on the appointment calendar page
            # Try multiple times with longer waits for visa site
            calendar_loaded = False
            for attempt in range(3):
                try:
                    # Look for ANY calendar/appointment indicator
                    calendar_elements = self.driver.find_elements(By.CSS_SELECTOR,
                        "[data-testid*='month'], .MonthSelector_month-selector_button__An0eF, "
                        ".tls-appointment-time-picker, .tls-time-picker, "
                        "p.text-lg.font-semibold, p.font-semibold.text-on-surface-variant, "
                        ".TlsCmsContent_cms-wrapper__5pjaA, "
                        "a[href*='appointment-booking?month='], "
                        ".bg-surface-container, "
                        "button[data-testid='btn-available-slot-default']"
                    )
                    if calendar_elements:
                        calendar_loaded = True
                        break
                    # Also check page text for appointment-related content
                    page_text = self.driver.page_source.lower()
                    if ("appointment" in page_text and ("slot" in page_text or "month" in page_text)) or \
                       "don't have any" in page_text or "currently available" in page_text:
                        calendar_loaded = True
                        break
                    # Wait a bit more and check for application error
                    self._wait_random(2, 3)
                    if not self._handle_application_error():
                        break
                except Exception:
                    self._wait_random(1, 2)
            
            if not calendar_loaded:
                # Calendar didn't load - check for application error and retry
                self._log("❌ Appointment calendar not loaded - checking for errors...")
                page_source = self.driver.page_source.lower()
                if "application error" in page_source or "client-side exception" in page_source:
                    self._log("⚠️ Application error detected - retrying from group selection...")
                    # Go back to group page and retry
                    try:
                        self.driver.back()
                        self._wait_random(2, 3)
                    except Exception:
                        pass
                return False
            
            return True

        except Exception as e:
            self._log(f"❌ Navigation failed: {e}")
            return False
    
    def _check_slots(self) -> tuple[bool, str]:
        """
        Check for available appointment slots across all available months.
        Returns: (slots_available: bool, message: str)
        """
        try:
            self._log("Checking for appointments...")
            wait = WebDriverWait(self.driver, 10)
            any_slots_found = False
            all_results = []

            # Wait for the page to fully load (visa site can be slow)
            try:
                wait.until(lambda d: d.execute_script("return document.readyState") == "complete")
            except Exception:
                pass
            self._wait_random(1, 2)

            # Handle application error first
            if not self._handle_application_error():
                return False, "Application error on appointment page"

            # Check for immediate popup indicating no slots anywhere
            # Use a short timeout and very specific selectors to avoid false positives
            try:
                short_wait = WebDriverWait(self.driver, 3)
                popup = short_wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, ".tls-popup")))
                # Verify the popup text actually mentions no appointments
                popup_text = popup.text.lower()
                if "no appointment" in popup_text or "no slot" in popup_text or "not available" in popup_text or "unavailable" in popup_text:
                    self._log("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
                    self._log("❌ NO APPOINTMENTS AVAILABLE")
                    self._log("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
                    
                    # Try to close the popup
                    try:
                        time.sleep(1)
                        close_btns = self.driver.find_elements(By.CSS_SELECTOR, 
                            "button.tls-button-primary, button[data-tls-value='confirm'], .tls-popup button")
                        for btn in close_btns:
                            try:
                                self.driver.execute_script("arguments[0].click();", btn)
                                self._wait_random(1, 2)
                                break
                            except Exception:
                                continue
                    except Exception:
                        pass
                    
                    check_time = datetime.now().strftime("%I:%M %p").lstrip("0")
                    self._log(f"🔍 Check at {check_time} — No appointments found")
                    return False, "No appointments available (popup)"
                else:
                    print(f"[Checker] Popup found but text doesn't indicate no slots: {popup_text[:100]}")
            except TimeoutException:
                # No popup - continue with normal month checking
                print("[Checker] No popup detected, proceeding to check months...")
                pass

            # Dynamic month discovery: months appear as we navigate through them
            checked_months = set()  # Track which months we've already checked
            months_to_check = []  # Queue of (name, link) to check
            
            # Wait for month selectors to render (visa SPA may take time)
            for _attempt in range(5):
                initial_months = self._get_available_months()
                if initial_months:
                    break
                self._wait_random(1, 2)
            if not initial_months:
                # Before falling to legacy, check if we're already on a no-slots page
                try:
                    no_slot_el = self.driver.find_element(By.CSS_SELECTOR,
                        "p.text-lg.font-semibold, p.font-semibold.text-on-surface-variant, "
                        ".TlsCmsContent_cms-wrapper__5pjaA p")
                    txt = no_slot_el.text.lower()
                    if "don't have" in txt or "no slot" in txt or "not available" in txt or "currently available" in txt or "check this page" in txt:
                        self._log("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
                        self._log("❌ NO APPOINTMENTS AVAILABLE (current month)")
                        self._log("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
                        # Still try to discover month links on this page
                        month_links = self.driver.find_elements(By.CSS_SELECTOR,
                            "a[href*='appointment-booking?month='], "
                            "a[data-testid*='month']")
                        if month_links:
                            for link in month_links:
                                name = link.text.strip()
                                href = link.get_attribute("href")
                                cls = link.get_attribute("class") or ""
                                if "--selected" in cls or "--disabled" in cls:
                                    continue
                                if href and name:
                                    initial_months.append((name, href))
                except Exception:
                    pass

            if not initial_months:
                # Debug: dump page info to help diagnose
                try:
                    url = self.driver.current_url
                    title = self.driver.title
                    body_text = self.driver.find_element(By.CSS_SELECTOR, "body").text[:500]
                    print(f"[Checker DEBUG] URL: {url}")
                    print(f"[Checker DEBUG] Title: {title}")
                    print(f"[Checker DEBUG] Body: {body_text[:300]}")
                except Exception:
                    pass

                # Strategy 4 (backup): Build direct appointment-booking URLs for
                # current month + next 2 months using visa URL pattern
                current_url = self.driver.current_url
                if "visas-de.tlscontact.com" in current_url:
                    print("[Checker] Using backup month URLs for visa site")
                    now = datetime.now()
                    month_names_list = ['January','February','March','April','May','June',
                                        'July','August','September','October','November','December']
                    # Extract base from current URL:
                    # e.g. https://visas-de.tlscontact.com/en-us/4055204/workflow/...
                    import re as _re
                    wf_match = _re.search(r'(https://visas-de\.tlscontact\.com/[^/]+/[^/]+/workflow)', current_url)
                    if not wf_match:
                        # Try to build from the page we're on
                        wf_match = _re.search(r'(https://visas-de\.tlscontact\.com/\S+?/workflow)', current_url)
                    if wf_match:
                        base_wf = wf_match.group(1)
                    else:
                        # Fallback: use known pattern
                        base_wf = "https://visas-de.tlscontact.com/en-us/4055204/workflow"

                    for offset in range(3):
                        m = now.month + offset
                        y = now.year
                        if m > 12:
                            m -= 12
                            y += 1
                        month_str = f"{m:02d}-{y}"
                        name = f"{month_names_list[m-1]} {y}"
                        url = f"{base_wf}/appointment-booking?month={month_str}"
                        initial_months.append((name, url))
                    print(f"[Checker] Generated backup month URLs: {[m[0] for m in initial_months]}")

                if not initial_months:
                    self._log("⚠️ No month selectors found, trying legacy layout...")
                    return self._check_slots_legacy()

            months_to_check.extend(initial_months)
            self._log(f"📆 Starting with {len(months_to_check)} visible month(s)")

            # Process months until no new ones discovered
            while months_to_check:
                month_name, month_link = months_to_check.pop(0)
                
                # Skip if already checked
                if month_name in checked_months:
                    continue
                
                checked_months.add(month_name)
                self._log(f"🔍 Checking {month_name}...")
                
                # Navigate to the month
                if month_link:
                    month_ok = False
                    for recovery_attempt in range(4):
                        try:
                            self.driver.get(month_link)
                            self._wait_random(1.5, 2.5)
                            if self._handle_application_error():
                                month_ok = True
                                break
                            # Strategy alternation: even=refresh/back, odd=go to group
                            if recovery_attempt % 2 == 0:
                                # Refresh then go back
                                print(f"[Checker] Month recovery {recovery_attempt}: refresh + back")
                                try:
                                    self.driver.refresh()
                                    self._wait_random(2, 3)
                                    if self._handle_application_error():
                                        month_ok = True
                                        break
                                    self.driver.back()
                                    self._wait_random(2, 3)
                                except Exception:
                                    pass
                            else:
                                # Go back and re-select group
                                print(f"[Checker] Month recovery {recovery_attempt}: back to group")
                                try:
                                    self.driver.back()
                                    self._wait_random(1, 2)
                                    self.driver.back()
                                    self._wait_random(2, 3)
                                    # Re-click group select
                                    btns = self.driver.find_elements(By.CSS_SELECTOR,
                                        "button[name='formGroupId'], button.tls-button-primary")
                                    for btn in btns:
                                        txt = btn.text.strip().lower()
                                        if txt == "select" or "formgroupid" in (btn.get_attribute("name") or ""):
                                            self.driver.execute_script("arguments[0].click();", btn)
                                            self._wait_random(3, 5)
                                            break
                                    if not self._handle_application_error():
                                        continue
                                except Exception:
                                    pass
                        except Exception:
                            self._wait_random(1, 2)
                    if not month_ok:
                        print(f"[Checker] Could not recover {month_name} after 4 attempts, skipping")
                        continue

                # Check for "no slots" message
                no_slots = False
                try:
                    no_slots_el = self.driver.find_element(By.CSS_SELECTOR,
                        "p.text-lg.font-semibold, .text-center p.font-semibold")
                    if "don't have any appointment" in no_slots_el.text.lower() or \
                       "no slots" in no_slots_el.text.lower() or \
                       "not available" in no_slots_el.text.lower() or \
                       "currently available" in no_slots_el.text.lower():
                        no_slots = True
                except Exception:
                    pass

                if no_slots:
                    self._log(f"📅 {month_name}: No appointments available")
                    all_results.append(f"{month_name}: No slots")
                    # Discover new months that may have appeared
                    newly_available = self._get_available_months()
                    for new_month, new_link in newly_available:
                        if new_month not in checked_months and (new_month, new_link) not in months_to_check:
                            months_to_check.append((new_month, new_link))
                            print(f"[Checker] Discovered new month: {new_month}")
                    continue

                # Look for available slot buttons
                available_buttons = self.driver.find_elements(By.CSS_SELECTOR,
                    "button[data-testid='btn-available-slot-default']")

                if not available_buttons:
                    self._log(f"📅 {month_name}: No appointments available")
                    all_results.append(f"{month_name}: No slots")
                    # Discover new months that may have appeared
                    newly_available = self._get_available_months()
                    for new_month, new_link in newly_available:
                        if new_month not in checked_months and (new_month, new_link) not in months_to_check:
                            months_to_check.append((new_month, new_link))
                            print(f"[Checker] Discovered new month: {new_month}")
                    continue

                # — Appointments found! Collect details —
                any_slots_found = True
                # Parse day groups
                day_groups = self.driver.find_elements(By.CSS_SELECTOR,
                    ".AppointmentDay_appointment-day__1Qnz1, .appointment-day")

                slot_details = []
                for day_group in day_groups:
                    try:
                        day_label_parts = day_group.find_elements(By.CSS_SELECTOR, "p span")
                        if len(day_label_parts) >= 2:
                            day_name = day_label_parts[0].text.strip()
                            day_num = day_label_parts[1].text.strip()
                            day_label = f"{day_name} {day_num}"
                        else:
                            day_label = day_group.find_element(By.CSS_SELECTOR, "p").text.strip()

                        avail_btns = day_group.find_elements(By.CSS_SELECTOR,
                            "button[data-testid='btn-available-slot-default']")
                        if avail_btns:
                            times = [btn.text.strip() for btn in avail_btns if btn.text.strip()]
                            slot_details.append(f"  {day_label}: {', '.join(times)}")
                    except Exception:
                        continue

                self._log("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
                self._log(f"🎉 {month_name}: APPOINTMENTS FOUND!")
                for detail in slot_details:
                    self._log(detail)
                self._log("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
                all_results.append(f"{month_name}: {len(available_buttons)} slots found")

                # Take screenshot (save into AppData so gallery works in installed app)
                screenshot_path = os.path.join(str(Config.BASE_DIR), f"slots_found_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png")
                self.driver.save_screenshot(screenshot_path)
                self._log(f"📸 Screenshot saved: {screenshot_path}")

                # Send first-alert notification (at most once per slot-available cycle)
                if self._slots_notif_count == 0:
                    db = SessionLocal()
                    try:
                        settings = db.query(UserSettings).filter(UserSettings.user_id == self.user_id).first()
                        if settings:
                            notification_service.send_slots_available_notification(
                                settings.notification_email,
                                settings.get_notification_types(),
                                screenshot_path
                            )
                            self._slots_notif_count = 1
                            self._slots_first_notif_time = datetime.now()
                            self._log("📧 Notification sent!")
                    finally:
                        db.close()
                else:
                    self._log("📧 Notification already sent — skipping duplicate")

                # Discover new months that may have appeared after navigating to this month
                newly_available = self._get_available_months()
                for new_month, new_link in newly_available:
                    if new_month not in checked_months and (new_month, new_link) not in months_to_check:
                        months_to_check.append((new_month, new_link))
                        print(f"[Checker] Discovered new month: {new_month}")

            if not any_slots_found:
                self._log("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
                self._log(f"❌ NO APPOINTMENTS in any month (checked {len(checked_months)} months)")
                self._log("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
                # Emit a single UI-friendly summary for Recent Checks
                check_time = datetime.now().strftime("%I:%M %p").lstrip("0")
                self._log(f"🔍 Check at {check_time} — No appointments found")
                return False, "No appointments available"

            # Emit a single UI-friendly summary for Recent Checks
            check_time = datetime.now().strftime("%I:%M %p").lstrip("0")
            # Build a formatted multi-line summary
            slot_lines = []
            no_slot_lines = []
            for r in all_results:
                if "slots found" in r.lower():
                    slot_lines.append(f"  🎉 {r}")
                else:
                    no_slot_lines.append(f"  ⬚ {r}")
            summary_parts = [f"🔍 Check at {check_time} — Slots available!"]
            summary_parts.extend(slot_lines)
            if no_slot_lines:
                summary_parts.extend(no_slot_lines)
            summary_msg = "\n".join(summary_parts)
            self._log(summary_msg)
            return True, "; ".join(all_results)

        except Exception as e:
            self._log(f"Error checking slots: {e}")
            return False, f"Error: {str(e)}"

    def _get_available_months(self) -> list[tuple[str, str | None]]:
        """Return list of (month_name, full_url_or_None) for months on the calendar page."""
        months = []
        try:
            # Strategy 1: New TLS layout - MonthSelector links
            selected = self.driver.find_elements(By.CSS_SELECTOR,
                "a.MonthSelector_month-selector_button__An0eF.MonthSelector_--selected__5re9q")

            if selected:
                name = selected[0].text.strip()
                if name:  # Guard against empty text (page not fully rendered)
                    months.append((name, None))  # None = already on this page

            # Collect all navigable month links
            month_links = self.driver.find_elements(By.CSS_SELECTOR,
                "a.MonthSelector_month-selector_button__An0eF")
            for link in month_links:
                name = link.text.strip()
                href = link.get_attribute("href")
                cls = link.get_attribute("class") or ""
                # Skip the already selected month
                if "--selected" in cls:
                    continue
                if href and name:
                    months.append((name, href))

            # Strategy 2: Broader selector - any link with month in href or data-testid
            if not months:
                all_month_links = self.driver.find_elements(By.CSS_SELECTOR,
                    "a[href*='appointment-booking?month='], "
                    "a[data-testid*='month']")
                for link in all_month_links:
                    name = link.text.strip()
                    href = link.get_attribute("href")
                    if name and href:
                        months.append((name, href))

            # Strategy 3: Detect "no slots" message on current page (visa layout)
            # If we see the no-slot message, the current month IS present — add it
            if not months:
                no_slot_els = self.driver.find_elements(By.CSS_SELECTOR,
                    "p.text-lg.font-semibold, p.font-semibold.text-on-surface-variant")
                for el in no_slot_els:
                    txt = el.text.lower()
                    if "don't have" in txt or "no slot" in txt or "not available" in txt or "currently available" in txt:
                        # We're on an appointment page but couldn't find month selectors
                        # Use the URL to infer current month
                        current_url = self.driver.current_url
                        if "month=" in current_url:
                            import re
                            m = re.search(r'month=(\d{2})-(\d{4})', current_url)
                            if m:
                                month_num, year = int(m.group(1)), m.group(2)
                                month_names = ['January','February','March','April','May','June',
                                               'July','August','September','October','November','December']
                                name = f"{month_names[month_num-1]} {year}"
                                months.append((name, None))
                        else:
                            months.append(("Current Month", None))
                        break

        except Exception as e:
            print(f"[Checker] Error getting months: {e}")
        return months

    def _check_slots_legacy(self) -> tuple[bool, str]:
        """Legacy slot check for older TLS layout (popup-based)."""
        try:
            wait = WebDriverWait(self.driver, 10)
            try:
                popup = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, ".tls-popup")))
                self._log("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
                self._log("❌ NO APPOINTMENTS AVAILABLE")
                self._log("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
                try:
                    confirm_btn = self.driver.find_element(By.CSS_SELECTOR,
                        "button.tls-button-primary.-uppercase[data-tls-value='confirm']")
                    self.driver.execute_script("arguments[0].click();", confirm_btn)
                    self._wait_random(1, 2)
                except Exception:
                    pass
                return False, "No appointments available"
            except TimeoutException:
                available_slots = self.driver.find_elements(By.CSS_SELECTOR, ".tls-time-unit:not(.-unavailable)")
                if not available_slots:
                    self._log("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
                    self._log("❌ NO APPOINTMENTS AVAILABLE")
                    self._log("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
                    return False, "No appointments available"

                self._log("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
                self._log("🎉 APPOINTMENTS AVAILABLE!")
                self._log("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
                screenshot_path = os.path.join(str(Config.BASE_DIR), f"slots_found_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png")
                self.driver.save_screenshot(screenshot_path)
                self._log(f"📸 Screenshot saved: {screenshot_path}")
                if self._slots_notif_count == 0:
                    db = SessionLocal()
                    try:
                        settings = db.query(UserSettings).filter(UserSettings.user_id == self.user_id).first()
                        if settings:
                            notification_service.send_slots_available_notification(
                                settings.notification_email, settings.get_notification_types(), screenshot_path)
                            self._slots_notif_count = 1
                            self._slots_first_notif_time = datetime.now()
                            self._log("📧 Notification sent!")
                    finally:
                        db.close()
                else:
                    self._log("📧 Notification already sent — skipping duplicate")
                return True, "Appointments available!"
        except Exception as e:
            self._log(f"Error checking slots (legacy): {e}")
            return False, f"Error: {str(e)}"
    
    def run_check(self, headless_override=None, is_retry: bool = False) -> bool:
        """Run TLS check. Returns True if check was successful, False if needs immediate retry."""
        db = SessionLocal()
        try:
            # Get user settings
            settings = db.query(UserSettings).filter(UserSettings.user_id == self.user_id).first()
            if not settings or not settings.tls_email or not settings.tls_password:
                self._log("❌ TLS credentials not configured")
                return True  # Don't retry immediately
            
            # Determine headless mode - always use settings value
            if headless_override is not None:
                use_headless = headless_override
            else:
                use_headless = settings.headless_mode if settings.headless_mode is not None else True
                if not settings.first_check_done:
                    settings.first_check_done = True
                    db.commit()
            
            # Store headless setting for _setup_driver
            Config.BROWSER_HEADLESS = use_headless
            
            # Get TLS credentials
            tls_email = settings.tls_email
            if not settings.tls_password or settings.tls_password == "__USE_ACCOUNT_PASSWORD__":
                self._log("[ERROR] TLS password not configured. Please save your TLS credentials.")
                db.close()
                return True  # Don't retry immediately
            
            tls_password = auth_service.decrypt_password(settings.tls_password)

            # Read service type and branch URL
            service_type = getattr(settings, 'service_type', 'legalization') or 'legalization'
            branch_url = settings.branch_url or Config.TLS_URL
            
            # Setup browser
            if not self._setup_driver():
                return False  # Retry immediately

            # Override document.visibilityState/hidden on every future page so
            # the TLS site always sees a "visible" window, even after the OS
            # window is sent to the bottom of the Z-order by the window hider.
            self._inject_visibility_override()

            # Login
            login_success, login_error = self._login(
                settings.tls_email, tls_password,
                branch_url=branch_url, service_type=service_type,
                is_retry=is_retry,
            )

            # Make Chrome transparent AFTER login (including CAPTCHA solving).
            # Chrome was visible (though transparent alpha=1 is imperceptible)
            # during the entire login flow so anti-bot systems see a real
            # browser.  Now it's safe to fully hide it.
            if login_success:
                self._hide_chrome_window()

            if not login_success:
                self._cleanup_driver()
                
                # Silently exit if monitoring was stopped during login
                if "STOPPED" in login_error:
                    return True
                
                self._log(f"❌ {login_error}")
                
                # Show popup for invalid credentials
                if "INVALID_CREDENTIALS" in login_error:
                    if self.on_status_update:
                        self.on_status_update("SHOW_CREDENTIALS_ERROR")
                    return True  # Don't retry immediately for wrong credentials
                
                # Wait for interval if maintenance
                if "MAINTENANCE" in login_error:
                    return True  # Wait for full interval, don't retry immediately
                
                # Retry immediately for application error or page loading issues
                if "APPLICATION_ERROR" in login_error or "PAGE_NOT_LOADED" in login_error:
                    self._log("➡️ Retrying immediately...")
                    return False  # Signal to retry immediately
                
                return False  # Retry immediately for other errors
            
            # Navigate to booking
            if not self._navigate_to_booking(service_type=service_type):
                self._cleanup_driver()
                return False  # Retry immediately
            
            # Check slots
            slots_available, message = self._check_slots()
            
            # Save to history
            history = CheckHistory(
                user_id=self.user_id,
                checked_at=datetime.now(timezone.utc),
                slots_available=slots_available,
                message=message
            )
            db.add(history)
            
            # Update settings
            settings.last_check_at = datetime.now(timezone.utc)
            settings.total_checks += 1
            settings.last_slots_found = slots_available
            
            # Increment daily check counter in license
            increment_check_count()
            
            db.commit()

            # --- Notification throttle logic ---
            if slots_available:
                # 12h reminder: if first email was sent >12 hours ago and reminder not yet sent
                if self._slots_notif_count == 1 and self._slots_first_notif_time:
                    elapsed = (datetime.now() - self._slots_first_notif_time).total_seconds()
                    if elapsed >= 12 * 3600:
                        db_n = SessionLocal()
                        try:
                            s = db_n.query(UserSettings).filter(UserSettings.user_id == self.user_id).first()
                            if s and s.notification_email:
                                notification_service.send_monitoring_reminder(
                                    s.notification_email, message)
                                self._slots_notif_count = 2
                                self._log("📧 12h reminder sent!")
                        finally:
                            db_n.close()
            else:
                # Reset cycle so re-notification happens if slots appear again later
                if self._slots_notif_count > 0:
                    self._slots_notif_count = 0
                    self._slots_first_notif_time = None

            # Report result to backend so dashboard shows recent checks
            self._report_to_backend(
                branch_name=getattr(settings, 'branch', '') or '',
                service_type=service_type,
                slots_available=slots_available,
                slot_details=message,
            )
            
            self._cleanup_driver()
            return True  # Check completed successfully
            
        except Exception as e:
            import traceback
            from datetime import timedelta
            error_msg = f"{type(e).__name__}: {str(e)}"
            trace = traceback.format_exc()
            self._log(f"[ERROR] Check cycle error: {error_msg}")
            print(f"Full traceback:\n{trace}")

            # Send error email — throttled to at most 1 per hour
            now = datetime.now()
            should_send = (
                self._last_error_email_time is None or
                (now - self._last_error_email_time).total_seconds() >= 3600
            )
            if should_send:
                try:
                    db_e = SessionLocal()
                    try:
                        s_e = db_e.query(UserSettings).filter(UserSettings.user_id == self.user_id).first()
                        if s_e and s_e.notification_email:
                            notification_service.send_error_notification(
                                s_e.notification_email, error_msg)
                            self._last_error_email_time = now
                    finally:
                        db_e.close()
                except Exception:
                    pass

            # Report error to backend so dashboard shows it
            try:
                self._report_to_backend(
                    branch_name=getattr(settings, 'branch', '') if 'settings' in dir() else '',
                    service_type=service_type if 'service_type' in dir() else 'visa',
                    slots_available=False,
                    error=error_msg,
                )
            except Exception:
                pass

            self._cleanup_driver()
            return False  # Retry immediately
        finally:
            db.close()
    
    def _monitoring_loop(self):
        """Background monitoring loop"""
        db = SessionLocal()
        try:
            settings = db.query(UserSettings).filter(UserSettings.user_id == self.user_id).first()
            check_interval = settings.check_interval if settings else Config.DEFAULT_CHECK_INTERVAL
        finally:
            db.close()
        
        is_retry = False
        while self.is_running:
            try:
                # Validate license before each check cycle
                from license_service import get_license_status
                license_status = get_license_status()
                if not license_status or not license_status.get('valid'):
                    self._log("❌ License no longer valid. Monitoring stopped.")
                    self.is_running = False
                    break
                
                # Run check and wait for it to complete
                check_successful = self.run_check(headless_override=None, is_retry=is_retry)
                
                # Exit loop if monitoring was stopped during check
                if not self.is_running:
                    break
                
                # If check failed (page not loaded, etc.), retry immediately
                if not check_successful:
                    is_retry = True
                    self._log("⏱️ Waiting 10 seconds before retry...")
                    for _ in range(20):  # 20 x 0.5s = 10s
                        if not self.is_running:
                            break
                        time.sleep(0.5)
                    continue  # Skip countdown, retry immediately
                
                # Reset retry flag after successful check
                is_retry = False
                
                # Only start countdown if check was successful
                if self.is_running:
                    wait_seconds = check_interval * 60
                    start_time = time.time()
                    
                    while time.time() - start_time < wait_seconds:
                        if not self.is_running:
                            break
                        
                        remaining = int(wait_seconds - (time.time() - start_time))
                        minutes = remaining // 60
                        seconds = remaining % 60
                        
                        # Update countdown display
                        if self.on_countdown_update:
                            self.on_countdown_update(minutes, seconds)
                        
                        time.sleep(1)
                    
                    # Reset countdown display
                    if self.on_countdown_update:
                        self.on_countdown_update(0, 0)
                    
            except Exception as e:
                self._log(f"Monitoring error: {e}")
                time.sleep(60)  # Wait 1 minute on error
    
    def start_monitoring(self):
        """Start background monitoring"""
        if self.is_running:
            self._log("Monitoring already running")
            return
        
        self.is_running = True
        self.check_thread = threading.Thread(target=self._monitoring_loop, daemon=True)
        self.check_thread.start()
        self._log("✅ Monitoring started")
    
    def stop_monitoring(self):
        """Stop background monitoring"""
        if not self.is_running:
            return
        
        self.is_running = False
        self._cleanup_driver()
        self._log("⏹️ Monitoring stopped")
    
    def run_single_check(self):
        """Run a single manual check"""
        threading.Thread(target=self.run_check, kwargs={'headless_override': None, 'is_retry': False}, daemon=True).start()


# Global checker instance (will be initialized per user)
checker_service = None
