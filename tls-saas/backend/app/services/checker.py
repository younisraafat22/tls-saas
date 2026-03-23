"""
TLS Checker Service — Playwright-based branch availability checker.
Ported from the battle-tested desktop Selenium checker for server-side shared checking.

Flow per branch: Navigate → Cloudflare → Cookie → Login → Group Select → Continue → Month-by-Month Slot Check

One browser instance per branch — checks once, notifies all subscribers.
"""

import asyncio
import base64
import hashlib
import logging
import os
import random
import re
import subprocess
import sys
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from typing import Optional

# Optional audio-transcription dependencies (install: pip install speechrecognition imageio-ffmpeg pydub)
try:
    import speech_recognition as _sr  # noqa: F401
    SR_AVAILABLE = True
except ImportError:
    SR_AVAILABLE = False

try:
    import imageio_ffmpeg  # noqa: F401
    FFMPEG_AVAILABLE = True
except ImportError:
    FFMPEG_AVAILABLE = False

from cryptography.fernet import Fernet
from app.config import settings

# Lazy import — visa_checker_sb pulls in selenium which isn't available in WORKER_MODE (Fly.io)
visa_checker_sb = None

logger = logging.getLogger("checker")

# Thread pool for running Playwright in its own ProactorEventLoop on Windows
_pw_executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="playwright")

# Separate thread pool for SeleniumBase (visa branches — sync, UC mode)
_sb_executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="sb_visa")

# ── Credential Encryption ────────────────────────────────────────────

def _derive_key(secret: str) -> bytes:
    """Derive a Fernet key from the config secret."""
    h = hashlib.sha256(secret.encode()).digest()
    return base64.urlsafe_b64encode(h)


_fernet = Fernet(_derive_key(settings.CREDENTIAL_ENCRYPTION_KEY))


def encrypt_credential(plain: str) -> str:
    return _fernet.encrypt(plain.encode()).decode()


def decrypt_credential(encrypted: str) -> str:
    return _fernet.decrypt(encrypted.encode()).decode()


# ── TLS Checker ──────────────────────────────────────────────────────

class TLSChecker:
    """
    Checks a single TLS branch for appointment availability using Playwright.
    Designed to be called per-branch by the scheduler.
    """

    # Path to warp-cli — works on both Windows (worker laptop) and Linux (Fly.io)
    WARP_CLI_WINDOWS = r"C:\Program Files\Cloudflare\Cloudflare WARP\warp-cli.exe"
    WARP_CLI_LINUX = "/usr/bin/warp-cli"

    def __init__(self):
        self._browser = None
        self._playwright = None
        self._loop = None  # Dedicated event loop for Playwright thread
        self._warp_enabled = False  # True when WARP is active for this session

    # ── Cloudflare WARP helpers ─────────────────────────────────────────

    def _warp_cli_path(self) -> str:
        """Return the platform-appropriate warp-cli path."""
        if sys.platform == "win32":
            return self.WARP_CLI_WINDOWS
        return self.WARP_CLI_LINUX

    def _warp_cmd(self, *args) -> list:
        """Build a warp-cli command list, adding --accept-tos on Linux (required for non-TTY use)."""
        cli = self._warp_cli_path()
        if sys.platform != "win32":
            return [cli, "--accept-tos"] + list(args)
        return [cli] + list(args)

    def _warp_available(self) -> bool:
        """Check that warp-cli binary exists AND is registered (not in 'Registration Missing' state)."""
        cli = self._warp_cli_path()
        if not os.path.isfile(cli):
            return False
        no_win = subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
        try:
            r = subprocess.run(
                self._warp_cmd("status"),
                capture_output=True, text=True, timeout=5,
                creationflags=no_win,
            )
            output = r.stdout + r.stderr
            # Skip WARP if registration is missing or it's in an error state
            if "Registration Missing" in output or "Unable" in output or "Terms of Service" in output:
                return False
        except Exception:
            return False
        return True

    def _warp_connect(self, log=None) -> bool:
        """Connect WARP and wait up to 30 s for the tunnel to be up."""
        _log = log or (lambda m, *a: None)
        no_win = subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
        try:
            subprocess.run(
                self._warp_cmd("connect"),
                capture_output=True, timeout=15,
                creationflags=no_win,
            )
        except Exception as exc:
            _log(f"WARP connect failed: {exc}", "warn")
            return False
        # Poll until status shows 'Connected' (not 'Connecting')
        deadline = time.time() + 30
        while time.time() < deadline:
            try:
                r = subprocess.run(
                    self._warp_cmd("status"),
                    capture_output=True, text=True, timeout=5,
                    creationflags=no_win,
                )
                status = r.stdout
                if "Connected" in status and "Connecting" not in status:
                    self._warp_enabled = True
                    _log("✅ WARP connected — IP rotated")
                    return True
            except Exception:
                pass
            time.sleep(1)
        _log("WARP did not reach Connected state within 30 s", "warn")
        return False

    def _warp_disconnect(self, log=None) -> None:
        """Disconnect WARP if active."""
        if not self._warp_enabled:
            return
        no_win = subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
        try:
            subprocess.run(
                self._warp_cmd("disconnect"),
                capture_output=True, timeout=10,
                creationflags=no_win,
            )
        except Exception:
            pass
        self._warp_enabled = False

    def _get_dedicated_loop(self):
        """Get or create a ProactorEventLoop for Playwright (Windows-safe)."""
        if self._loop is None or self._loop.is_closed():
            if sys.platform == "win32":
                self._loop = asyncio.ProactorEventLoop()
            else:
                self._loop = asyncio.new_event_loop()
        return self._loop

    async def _ensure_browser(self):
        """Lazy-init Patchright browser (binary-level stealth, bypasses Cloudflare/Turnstile)."""
        if self._browser and self._browser.is_connected():
            return

        from patchright.async_api import async_playwright
        self._playwright = await async_playwright().start()
        self._browser = await self._playwright.chromium.launch(
            headless=settings.BROWSER_HEADLESS,
            args=[
                "--no-sandbox",
                "--disable-dev-shm-usage",
            ],
        )
        logger.info("Patchright browser launched")

    async def close(self):
        """Shut down browser and disconnect WARP if active."""
        if self._browser:
            await self._browser.close()
            self._browser = None
        if self._playwright:
            await self._playwright.stop()
            self._playwright = None
        self._warp_disconnect()

    # ── Public entry point ───────────────────────────────────────────

    async def check_branch(
        self,
        branch_url: str,
        tls_email: str,
        tls_password: str,
        branch_name: str = "",
        service_type: str = "legalization",
    ) -> dict:
        """
        Check a branch for appointment availability.
        - Visa branches → SeleniumBase UC (bypasses Cloudflare on visas-de.tlscontact.com)
        - Legalization branches → Patchright async
        """
        try:
            # Visa: use SeleniumBase UC (synchronous) in a thread pool on all platforms
            if service_type == "visa":
                global visa_checker_sb
                if visa_checker_sb is None:
                    from app.services.visa_checker_sb import visa_checker_sb as _vcb
                    visa_checker_sb = _vcb
                return await asyncio.get_event_loop().run_in_executor(
                    _sb_executor,
                    visa_checker_sb.check,
                    branch_url, tls_email, tls_password, branch_name,
                )

            # Legalization: use Patchright (async)
            if sys.platform == "win32":
                return await asyncio.shield(
                    asyncio.get_event_loop().run_in_executor(
                        _pw_executor,
                        self._check_branch_sync,
                        branch_url, tls_email, tls_password, branch_name, service_type,
                    )
                )
            else:
                return await self._check_branch_async(
                    branch_url, tls_email, tls_password, branch_name, service_type,
                )
        except asyncio.CancelledError:
            logger.info(f"[{branch_name}] Check cancelled (monitoring stopped)")
            return {
                "slots_available": False,
                "slot_details": None,
                "screenshot": None,
                "error": "cancelled",
                "duration": 0,
                "logs": [{"level": "info", "message": "Check cancelled (monitoring stopped)"}],
            }

    def _check_branch_sync(self, branch_url, tls_email, tls_password, branch_name, service_type) -> dict:
        """Run the async check in a dedicated ProactorEventLoop (Windows)."""
        loop = self._get_dedicated_loop()
        asyncio.set_event_loop(loop)
        return loop.run_until_complete(
            self._check_branch_async(branch_url, tls_email, tls_password, branch_name, service_type)
        )

    # ── Core async check ─────────────────────────────────────────────

    async def _check_branch_async(
        self,
        branch_url: str,
        tls_email: str,
        tls_password: str,
        branch_name: str = "",
        service_type: str = "legalization",
    ) -> dict:
        """
        Full TLS check flow matching the desktop app:
        1. Navigate to branch URL
        2. Handle Cloudflare / cookie consent
        3. Click Login, fill credentials, handle reCAPTCHA
        4. Select group, click Continue
        5. Check months for available slots
        """
        start = time.time()
        result = {
            "slots_available": False,
            "slot_details": None,
            "screenshot": None,
            "error": "",
            "duration": 0,
            "logs": [],  # Step-by-step logs
        }

        def log(msg: str, level: str = "info"):
            """Log to both Python logger and result log buffer."""
            result["logs"].append({"level": level, "message": msg})
            if level == "error":
                logger.error(f"[{branch_name}] {msg}")
            elif level == "warn":
                logger.warning(f"[{branch_name}] {msg}")
            else:
                logger.info(f"[{branch_name}] {msg}")

        page = None
        context = None
        try:
            await self._ensure_browser()
            context = await self._browser.new_context(
                viewport={"width": 1920, "height": 1080},
                user_agent=(
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/121.0.0.0 Safari/537.36"
                ),
            )
            page = await context.new_page()
            page.set_default_timeout(settings.PLAYWRIGHT_TIMEOUT)

            # ── Step 1: Navigate ──────────────────────────────────
            label = "Visa" if service_type == "visa" else "Legalization"
            log(f"Opening TLS {label} website...")
            await page.goto(branch_url, wait_until="networkidle", timeout=60000)
            await asyncio.sleep(2)

            # ── Step 2: Cloudflare / Turnstile ────────────────────
            cf_passed = await self._handle_cloudflare(page, branch_name, log)
            if not cf_passed:
                result["error"] = "Cloudflare challenge did not pass"
                log("Cloudflare challenge did not pass", "error")
                await context.close()
                result["duration"] = round(time.time() - start, 2)
                return result

            # ── Step 3: Cookie consent ────────────────────────────
            await self._handle_cookie_consent(page, log)

            # ── Step 4: Check for maintenance ─────────────────────
            content = await page.content()
            if "maintenance" in content.lower():
                try:
                    maint = await page.query_selector(".maintenance_center")
                    if maint:
                        result["error"] = "TLS website under maintenance"
                        log("TLS website is under maintenance", "warn")
                        await context.close()
                        result["duration"] = round(time.time() - start, 2)
                        return result
                except Exception:
                    pass

            # ── Step 5: Handle Application Error ──────────────────
            app_ok = await self._handle_application_error(page, log)
            if not app_ok:
                result["error"] = "TLS Application error persists"
                await context.close()
                result["duration"] = round(time.time() - start, 2)
                return result

            # ── Step 6: Click Login button ────────────────────────
            login_clicked = await self._click_login_button(page, log)
            if not login_clicked:
                result["error"] = "Login button not found on TLS website"
                log("Login button not found", "error")
                try:
                    result["screenshot"] = await page.screenshot(type="png")
                except Exception:
                    pass
                await context.close()
                result["duration"] = round(time.time() - start, 2)
                return result

            await asyncio.sleep(3)
            await self._handle_cookie_consent(page, log)

            # ── Step 7: Fill credentials ──────────────────────────
            log("Logging in...")
            cred_ok = await self._fill_credentials(page, tls_email, tls_password, log)
            if not cred_ok:
                result["error"] = "Login form not found"
                log("Login form fields not found", "error")
                await context.close()
                result["duration"] = round(time.time() - start, 2)
                return result

            # ── Step 8: Handle reCAPTCHA (if present) ─────────────
            # Returns False if browser was closed for WARP IP rotate — must abort session
            captcha_ok = await self._check_recaptcha(page, log)
            if captcha_ok is False:
                result["error"] = "Session reset for IP rotation — will retry"
                result["duration"] = round(time.time() - start, 2)
                return result

            # ── Step 9: Click submit login ────────────────────────
            submit_ok = await self._submit_login(page, log)
            if not submit_ok:
                result["error"] = "Login submit button not found"
                await context.close()
                result["duration"] = round(time.time() - start, 2)
                return result

            await asyncio.sleep(3)

            # ── Step 10: Verify login succeeded ───────────────────
            login_ok = await self._verify_login(page, log)
            if not login_ok:
                result["error"] = "Login failed — invalid credentials or CAPTCHA"
                try:
                    result["screenshot"] = await page.screenshot(type="png")
                except Exception:
                    pass
                await context.close()
                result["duration"] = round(time.time() - start, 2)
                return result

            log("Login successful")

            # ── Step 11: Handle Application Error (post-login) ────
            await self._handle_application_error(page, log)

            # ── Step 12: Navigate to booking ──────────────────────
            nav_ok = await self._navigate_to_booking(page, service_type, log, branch_url=branch_url)
            if not nav_ok:
                # Check logs for specific "no application" error
                no_app_logs = [l for l in result["logs"] if "no application" in l.get("message", "").lower()]
                if no_app_logs:
                    result["error"] = "No application found on TLS website"
                else:
                    result["error"] = "Could not navigate to appointment booking page"
                try:
                    result["screenshot"] = await page.screenshot(type="png")
                except Exception:
                    pass
                await context.close()
                result["duration"] = round(time.time() - start, 2)
                return result

            # ── Step 13: Check slots across all months ────────────
            slots_available, slot_details, slot_msg = await self._check_slots(
                page, service_type, branch_name, log
            )
            result["slots_available"] = slots_available
            result["slot_details"] = slot_details

            if slots_available:
                log(f"*** APPOINTMENTS FOUND! *** {slot_msg}", "success")
            else:
                log(f"No appointments available ({slot_msg})")

            # Take final screenshot
            try:
                result["screenshot"] = await page.screenshot(type="png")
            except Exception:
                pass

            await context.close()

        except Exception as e:
            result["error"] = str(e)
            log(f"Check failed: {e}", "error")
            if page:
                try:
                    result["screenshot"] = await page.screenshot(type="png")
                except Exception:
                    pass
            if context:
                try:
                    await context.close()
                except Exception:
                    pass

        result["duration"] = round(time.time() - start, 2)
        return result

    # ── Cloudflare / Turnstile ────────────────────────────────────────

    async def _handle_cloudflare(self, page, branch_name: str, log) -> bool:
        """Detect Cloudflare challenge and wait for it to pass."""
        max_wait = 180  # seconds
        start = time.time()

        cf_indicators = [
            "just a moment", "checking your browser",
            "cf-browser-verification", "challenge-platform",
            "turnstile", "cloudflare",
        ]

        while time.time() - start < max_wait:
            content = (await page.content()).lower()
            if any(ind in content for ind in cf_indicators):
                log("Cloudflare challenge detected, waiting...")
                await asyncio.sleep(3)
                continue
            log("Page loaded (Cloudflare passed)")
            return True

        return False

    # ── Cookie Consent ────────────────────────────────────────────────

    async def _handle_cookie_consent(self, page, log):
        """Dismiss Osano / generic cookie consent banners."""
        selectors = [
            "button.osano-cm-accept-all",
            ".osano-cm-accept-all",
            "button[class*='osano-cm-accept']",
            ".osano-cm-button--type_accept",
        ]
        for sel in selectors:
            try:
                el = await page.query_selector(sel)
                if el and await el.is_visible():
                    log("Dismissing cookie consent banner...")
                    await el.click()
                    await asyncio.sleep(1)
                    return
            except Exception:
                continue

        # Also try generic "Accept" / "Accept All" buttons
        try:
            buttons = await page.query_selector_all("button")
            for btn in buttons:
                txt = (await btn.inner_text()).strip().lower()
                if txt in ("accept all", "accept", "save"):
                    await btn.click()
                    await asyncio.sleep(0.5)
                    return
        except Exception:
            pass

    # ── Application Error Recovery ────────────────────────────────────

    async def _handle_application_error(self, page, log, max_retries: int = 3) -> bool:
        """Detect TLS 'Application error: a client-side exception' and recover."""
        for attempt in range(max_retries):
            content = (await page.content()).lower()
            if "application error" not in content and "client-side exception" not in content:
                return True
            log(f"Application error detected — reloading (attempt {attempt + 1})...", "warn")
            await page.reload(wait_until="networkidle", timeout=30000)
            await asyncio.sleep(2)
        return False

    # ── Login Flow ────────────────────────────────────────────────────

    async def _click_login_button(self, page, log) -> bool:
        """Find and click the LOGIN button on the TLS home page."""
        # TLS-specific selectors (from desktop app)
        login_selectors = [
            "span.TlsButton_tls-button__syUS5",
            "[class*='TlsButton'][class*='--outline']",
            "a.tls-button-link",
        ]

        for sel in login_selectors:
            try:
                elements = await page.query_selector_all(sel)
                for el in elements:
                    txt = (await el.inner_text()).strip().upper()
                    if txt == "LOGIN":
                        await el.click()
                        log("Clicked LOGIN button")
                        return True
            except Exception:
                continue

        # Fallback: any link/button with text "Login" or "Log in"
        try:
            for sel in ["a", "button", "span"]:
                elements = await page.query_selector_all(sel)
                for el in elements:
                    try:
                        txt = (await el.inner_text()).strip().upper()
                        if txt in ("LOGIN", "LOG IN"):
                            await el.click()
                            log("Clicked LOGIN button (fallback)")
                            return True
                    except Exception:
                        continue
        except Exception:
            pass

        # SVG icon fallback — click the person icon, then find Login in the dropdown
        try:
            icon = await page.query_selector("svg[aria-label='User icon']")
            if icon:
                parent = await icon.evaluate_handle("el => el.parentElement")
                await parent.as_element().click()
                log("Clicked SVG user icon — waiting for dropdown...")
                await asyncio.sleep(1.5)
                # Find the Login link inside the opened dropdown
                for xpath_text in ["LOGIN", "Login", "Log in"]:
                    try:
                        login_link = await page.query_selector(
                            f"xpath=//*[normalize-space(text())='{xpath_text}']"
                        )
                        if login_link and await login_link.is_visible():
                            await login_link.click()
                            log("Clicked Login link in dropdown")
                            return True
                    except Exception:
                        continue
                # Dropdown may have navigated directly — treat as success
                log("Clicked login icon button (direct navigation)")
                return True
        except Exception:
            pass

        # div#login fallback
        try:
            div = await page.query_selector("div[id='login']")
            if div:
                await div.click()
                log("Clicked login div")
                return True
        except Exception:
            pass

        # Last resort: wait for it
        log("Login button not found yet, waiting...")
        await self._handle_cookie_consent(page, log)
        try:
            await page.wait_for_selector(
                ", ".join(login_selectors), timeout=40000
            )
            for sel in login_selectors:
                elements = await page.query_selector_all(sel)
                for el in elements:
                    txt = (await el.inner_text()).strip().upper()
                    if txt == "LOGIN":
                        await el.click()
                        log("Clicked LOGIN button (after wait)")
                        return True
        except Exception:
            pass

        # Debug info
        try:
            title = await page.title()
            url = page.url
            log(f"Login button not found. Page: '{title}', URL: {url}", "error")
        except Exception:
            pass
        return False

    async def _fill_credentials(self, page, email: str, password: str, log) -> bool:
        """Fill in the TLS login form."""
        email_field = None
        password_field = None

        # TLS-specific selectors
        for eid in ["#email-input-field", "#username", "input[type='email']", "input[name='email']"]:
            try:
                f = await page.query_selector(eid)
                if f:
                    email_field = f
                    break
            except Exception:
                continue

        for pid in ["#password-input-field", "#password", "input[type='password']"]:
            try:
                f = await page.query_selector(pid)
                if f:
                    password_field = f
                    break
            except Exception:
                continue

        if not email_field or not password_field:
            log("Login form fields not found", "error")
            return False

        await email_field.fill("")
        await email_field.fill(email)
        await asyncio.sleep(1)
        await password_field.fill("")
        await password_field.fill(password)
        await asyncio.sleep(1)
        log("Credentials entered")
        return True

    # ── reCAPTCHA helpers ──────────────────────────────────────────────────

    async def _is_captcha_solved(self, page) -> bool:
        """Check if the g-recaptcha-response textarea already has a token."""
        try:
            token = await page.evaluate(
                "() => { var el = document.getElementById('g-recaptcha-response'); return el ? el.value : ''; }"
            )
            return bool(token and len(token) > 20)
        except Exception:
            return False

    async def _wait_for_captcha_token(self, page, timeout: int = 15) -> bool:
        """Poll until the g-recaptcha-response token appears (max `timeout` seconds)."""
        for _ in range(timeout * 2):
            if await self._is_captcha_solved(page):
                return True
            await asyncio.sleep(0.5)
        return False

    @staticmethod
    def _clean_transcript(text: str) -> str:
        """Clean transcription output for use as a reCAPTCHA audio answer."""
        cleaned = text.lower().strip()
        cleaned = re.sub(r'[^\w\s]', '', cleaned)
        cleaned = re.sub(r'\s+', ' ', cleaned).strip()
        word_to_digit = {
            'zero': '0', 'one': '1', 'two': '2', 'three': '3',
            'four': '4', 'five': '5', 'six': '6', 'seven': '7',
            'eight': '8', 'nine': '9',
        }
        words = cleaned.split()
        if words and all(w in word_to_digit for w in words):
            cleaned = ''.join(word_to_digit[w] for w in words)
        return cleaned

    def _enhance_audio(self, mp3_path: str, log) -> str:
        """Convert MP3 → mono 16 kHz WAV with loudnorm via imageio_ffmpeg."""
        wav_path = os.path.splitext(mp3_path)[0] + ".wav"
        try:
            if not FFMPEG_AVAILABLE:
                log("imageio_ffmpeg not available — install: pip install imageio-ffmpeg", "warn")
                return ""
            ffmpeg_exe = imageio_ffmpeg.get_ffmpeg_exe()
            flags = subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
            # Primary: mono 16 kHz + loudnorm
            cmd = [ffmpeg_exe, "-y", "-i", mp3_path, "-ac", "1", "-ar", "16000", "-af", "loudnorm", wav_path]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30, creationflags=flags)
            if result.returncode != 0 or not os.path.exists(wav_path):
                log(f"ffmpeg primary failed (code {result.returncode}), trying basic conversion", "warn")
                cmd2 = [ffmpeg_exe, "-y", "-i", mp3_path, wav_path]
                result2 = subprocess.run(cmd2, capture_output=True, text=True, timeout=30, creationflags=flags)
                if result2.returncode != 0 or not os.path.exists(wav_path):
                    log(f"Basic audio conversion also failed: {result2.stderr[:200]}", "warn")
                    return ""
        except Exception as e:
            log(f"Audio conversion error: {e}", "warn")
            return ""
        return wav_path

    def _transcribe_with_google(self, wav_path: str, log) -> Optional[str]:
        """Transcribe a WAV file using Google Web Speech API (online, free)."""
        if not SR_AVAILABLE:
            log("speech_recognition not available — install: pip install SpeechRecognition", "warn")
            return None
        if not os.path.exists(wav_path):
            log(f"WAV file not found: {wav_path}", "warn")
            return None
        try:
            import speech_recognition as _sr  # noqa: WPS433
            recognizer = _sr.Recognizer()
            with _sr.AudioFile(wav_path) as source:
                recognizer.adjust_for_ambient_noise(source, duration=0.5)
            with _sr.AudioFile(wav_path) as source:
                audio_data = recognizer.record(source)
            text = recognizer.recognize_google(audio_data).strip()
            if text:
                log(f"Google raw: \"{text}\"")
                text = self._clean_transcript(text)
                log(f"Google cleaned: \"{text}\"")
            return text if text else None
        except Exception as e:
            log(f"Google transcription error: {e}", "warn")
            return None

    async def _transcribe_audio(self, page, audio_url: str, log) -> Optional[str]:
        """Download reCAPTCHA audio (3 strategies), convert to WAV, transcribe."""
        tmp_mp3 = tmp_wav = None
        try:
            audio_bytes = None

            # ── Strategy 1: fetch inside the bframe (same-origin with recaptcha.net) ──
            bframe = next((f for f in page.frames if "recaptcha" in f.url and "bframe" in f.url), None)
            if bframe:
                try:
                    b64 = await bframe.evaluate("""
                        async (url) => {
                            try {
                                const resp = await fetch(url);
                                if (!resp.ok) return null;
                                const buf = await resp.arrayBuffer();
                                const bytes = new Uint8Array(buf);
                                let s = '';
                                for (let i = 0; i < bytes.length; i++) s += String.fromCharCode(bytes[i]);
                                return btoa(s);
                            } catch(e) { return null; }
                        }
                    """, audio_url)
                    if b64:
                        audio_bytes = base64.b64decode(b64)
                        log("Audio downloaded via bframe fetch")
                except Exception as e:
                    log(f"bframe fetch failed: {e}", "warn")

            # ── Strategy 2: fetch from page default context ──
            if not audio_bytes:
                try:
                    b64 = await page.evaluate("""
                        async (url) => {
                            try {
                                const resp = await fetch(url);
                                if (!resp.ok) return null;
                                const buf = await resp.arrayBuffer();
                                const bytes = new Uint8Array(buf);
                                let s = '';
                                for (let i = 0; i < bytes.length; i++) s += String.fromCharCode(bytes[i]);
                                return btoa(s);
                            } catch(e) { return null; }
                        }
                    """, audio_url)
                    if b64:
                        audio_bytes = base64.b64decode(b64)
                        log("Audio downloaded via page fetch fallback")
                except Exception as e:
                    log(f"Page fetch fallback failed: {e}", "warn")

            # ── Strategy 3: requests with page cookies (last resort) ──
            if not audio_bytes:
                try:
                    import requests as _req
                    cookies_list = await page.context.cookies()
                    cookies = {c['name']: c['value'] for c in cookies_list}
                    ua = await page.evaluate("() => navigator.userAgent")
                    resp = _req.get(audio_url, timeout=30, cookies=cookies,
                                    headers={'User-Agent': ua})
                    resp.raise_for_status()
                    audio_bytes = resp.content
                    log("Audio downloaded via requests fallback")
                except Exception as e:
                    log(f"requests download failed: {e}", "warn")
                    return None

            # Save to temp MP3
            with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as f:
                f.write(audio_bytes)
                tmp_mp3 = f.name

            # Convert to WAV
            tmp_wav = self._enhance_audio(tmp_mp3, log)
            if not tmp_wav or not os.path.exists(tmp_wav):
                log("Audio conversion failed", "warn")
                return None

            # Transcribe
            return self._transcribe_with_google(tmp_wav, log)

        except Exception as e:
            log(f"Audio transcription error: {e}", "warn")
            return None
        finally:
            for p in (tmp_mp3, tmp_wav):
                if p:
                    try:
                        os.unlink(p)
                    except Exception:
                        pass

    # ── Full reCAPTCHA v2 audio solver ─────────────────────────────────────

    async def _check_recaptcha(self, page, log):
        """
        Full reCAPTCHA v2 audio solver — ported from original desktop Selenium app.
        Flow: detect → click checkbox → (auto-solved?) → audio challenge → download →
              ffmpeg convert → Google Speech API → type answer → verify (up to 3 retries).
        """
        MAX_ATTEMPTS = 3

        for attempt in range(1, MAX_ATTEMPTS + 1):
            try:
                # ── 1. Is there even a CAPTCHA? ──────────────────────────
                recaptcha = await page.query_selector(
                    "iframe[src*='recaptcha'], iframe[title='reCAPTCHA'], "
                    ".g-recaptcha, #it-recaptcha-here"
                )
                if not recaptcha:
                    log("No reCAPTCHA detected")
                    return

                if await self._is_captcha_solved(page):
                    log("reCAPTCHA already solved (token present)")
                    return

                log(f"reCAPTCHA detected — solving (attempt {attempt}/{MAX_ATTEMPTS})...", "warn")

                # ── 2. Click the checkbox in the anchor iframe ────────────
                anchor_frame = next(
                    (f for f in page.frames if "recaptcha" in f.url and "anchor" in f.url), None
                )
                if anchor_frame:
                    await asyncio.sleep(random.uniform(0.5, 1.0))
                    try:
                        cb = await anchor_frame.wait_for_selector("#recaptcha-anchor", timeout=8000)
                        if cb:
                            await cb.click()
                            await asyncio.sleep(random.uniform(2, 4))
                            # Check if checkbox alone solved it (no challenge appeared)
                            try:
                                checked = await anchor_frame.query_selector(
                                    ".recaptcha-checkbox-checked, [aria-checked='true']"
                                )
                                if checked and await self._wait_for_captcha_token(page, 5):
                                    log("reCAPTCHA auto-passed (no challenge needed)")
                                    return
                            except Exception:
                                pass
                    except Exception:
                        pass
                else:
                    log("Anchor iframe not found — trying challenge directly", "warn")

                await asyncio.sleep(random.uniform(1, 2))

                # ── 3. Find the bframe (challenge iframe) ────────────────
                bframe = next(
                    (f for f in page.frames if "recaptcha" in f.url and "bframe" in f.url), None
                )
                if not bframe:
                    log("Challenge iframe not found", "warn")
                    if attempt < MAX_ATTEMPTS:
                        await asyncio.sleep(3)
                        continue
                    log("reCAPTCHA could not be solved — proceeding anyway", "warn")
                    return

                # ── 4. Check for "automated queries" block ───────────────
                try:
                    body_text = await bframe.evaluate(
                        "() => document.body ? document.body.innerText.toLowerCase() : ''"
                    )
                    if "automated queries" in body_text or "unusual traffic" in body_text:
                        log("Google detected automation — rate-limited", "warn")
                        if self._warp_available() and not self._warp_enabled:
                            log("Connecting WARP to rotate IP...", "warn")
                            connected = await asyncio.get_event_loop().run_in_executor(
                                None, lambda: self._warp_connect(log)
                            )
                            if connected:
                                log("WARP connected — closing browser for fresh session", "warn")
                                try:
                                    await self._browser.close()
                                except Exception:
                                    pass
                                self._browser = None
                                return False  # signal caller: browser closed, session aborted
                        if attempt < MAX_ATTEMPTS:
                            wait_time = 10 * attempt
                            log(f"Waiting {wait_time}s before retry (cooldown)...", "warn")
                            await asyncio.sleep(wait_time)
                            continue
                        log("reCAPTCHA rate-limited — proceeding anyway", "warn")
                        return
                except Exception:
                    pass

                # ── 5. Click the audio challenge button ──────────────────
                try:
                    audio_btn = await bframe.wait_for_selector(
                        "#recaptcha-audio-button, button.rc-button-audio",
                        timeout=10000, state="visible"
                    )
                    if audio_btn:
                        log("Clicking audio challenge button...")
                        await audio_btn.click()
                        await asyncio.sleep(random.uniform(3, 5))
                except Exception as e:
                    log(f"Audio button not found or not clickable: {e}", "warn")

                # ── 6. Re-find bframe after audio click (DOM may reload) ──
                await asyncio.sleep(random.uniform(1, 2))
                bframe = next(
                    (f for f in page.frames if "recaptcha" in f.url and "bframe" in f.url), None
                )
                if not bframe:
                    log("Challenge iframe lost after audio click", "warn")
                    if attempt < MAX_ATTEMPTS:
                        await asyncio.sleep(3)
                        continue
                    log("reCAPTCHA could not be solved — proceeding anyway", "warn")
                    return

                await asyncio.sleep(random.uniform(1, 2))

                # Check for rate-limit error message
                try:
                    err_el = await bframe.query_selector(".rc-audiochallenge-error-message")
                    if err_el and await err_el.is_visible():
                        log("Google blocked audio challenges (rate-limited)", "warn")
                        if self._warp_available() and not self._warp_enabled:
                            log("Connecting WARP to rotate IP...", "warn")
                            connected = await asyncio.get_event_loop().run_in_executor(
                                None, lambda: self._warp_connect(log)
                            )
                            if connected:
                                log("WARP connected — closing browser for fresh session", "warn")
                                try:
                                    await self._browser.close()
                                except Exception:
                                    pass
                                self._browser = None
                                return False  # signal caller: browser closed, session aborted
                        if attempt < MAX_ATTEMPTS:
                            await asyncio.sleep(5)
                            continue
                        log("reCAPTCHA blocked — proceeding anyway", "warn")
                        return
                except Exception:
                    pass

                # ── 7. Get the audio URL (poll up to 15 s) ───────────────
                audio_url = None
                for _poll in range(30):
                    # Strategy A: <audio id="audio-source" src="...">
                    try:
                        el = await bframe.query_selector("#audio-source")
                        if el:
                            src = await el.get_attribute("src")
                            if src and src.startswith("http"):
                                audio_url = src
                                break
                    except Exception:
                        pass
                    # Strategy B: <source> inside <audio>
                    try:
                        el = await bframe.query_selector("#audio-source source, audio source")
                        if el:
                            src = await el.get_attribute("src")
                            if src and src.startswith("http"):
                                audio_url = src
                                break
                    except Exception:
                        pass
                    # Strategy C: download link
                    try:
                        el = await bframe.query_selector(".rc-audiochallenge-tdownload-link")
                        if el:
                            href = await el.get_attribute("href")
                            if href and href.startswith("http"):
                                audio_url = href
                                break
                    except Exception:
                        pass
                    await asyncio.sleep(0.5)

                if not audio_url:
                    log("Audio source URL not found", "warn")
                    if attempt < MAX_ATTEMPTS:
                        await asyncio.sleep(3)
                        continue
                    log("reCAPTCHA could not be solved — proceeding anyway", "warn")
                    return

                log("Audio challenge URL found, downloading...")

                # ── 8. Download, convert, transcribe ────────────────────
                transcript = await self._transcribe_audio(page, audio_url, log)
                if not transcript:
                    if attempt < MAX_ATTEMPTS:
                        log("Transcription failed — retrying in 3s...", "warn")
                        await asyncio.sleep(3)
                        continue
                    log("Transcription failed after all attempts — proceeding anyway", "warn")
                    return

                # ── 9. Type the answer ───────────────────────────────────
                # Re-fetch bframe in case it reloaded during transcription
                bframe = next(
                    (f for f in page.frames if "recaptcha" in f.url and "bframe" in f.url), None
                )
                if not bframe:
                    log("bframe gone after transcription — proceeding anyway", "warn")
                    return

                try:
                    answer_input = await bframe.wait_for_selector("#audio-response", timeout=5000)
                    if answer_input:
                        await answer_input.fill("")
                        for ch in transcript:
                            await answer_input.type(ch)
                            await asyncio.sleep(random.uniform(0.04, 0.09))
                        await asyncio.sleep(random.uniform(0.5, 1.0))
                except Exception as e:
                    log(f"Could not type CAPTCHA answer: {e}", "warn")
                    if attempt < MAX_ATTEMPTS:
                        await asyncio.sleep(3)
                        continue
                    return

                # ── 10. Click verify ─────────────────────────────────────
                try:
                    verify_btn = await bframe.query_selector("#recaptcha-verify-button")
                    if verify_btn:
                        await verify_btn.click()
                        await asyncio.sleep(random.uniform(2, 4))
                except Exception as e:
                    log(f"Could not click verify: {e}", "warn")
                    if attempt < MAX_ATTEMPTS:
                        await asyncio.sleep(3)
                        continue
                    return

                # ── 11. Confirm token ────────────────────────────────────
                if await self._wait_for_captcha_token(page, 10):
                    log("reCAPTCHA solved via audio!")
                    return

                # Token not set — probably got a new challenge, retry
                if attempt < MAX_ATTEMPTS:
                    log("Answer not accepted — retrying in 3s...", "warn")
                    await asyncio.sleep(3)
                    continue

                log("Could not solve reCAPTCHA after multiple attempts — proceeding anyway", "warn")
                return

            except Exception as e:
                log(f"CAPTCHA solving error (attempt {attempt}): {e}", "warn")
                if attempt < MAX_ATTEMPTS:
                    await asyncio.sleep(3)
                    continue
                return

    async def _submit_login(self, page, log) -> bool:
        """Click the login submit button."""
        submit_selectors = ["#btn-login", "#kc-login", "button[type='submit']", "input[type='submit']"]
        # Wait for submit button to appear — generous timeout in case reCAPTCHA delayed things
        try:
            await page.wait_for_selector(
                ", ".join(submit_selectors), timeout=30000
            )
        except Exception:
            pass

        for sel in submit_selectors:
            try:
                btn = await page.query_selector(sel)
                if btn:
                    # Scroll into view and click
                    await btn.scroll_into_view_if_needed()
                    await asyncio.sleep(0.5)
                    await btn.click()
                    log("Login submitted")
                    return True
            except Exception:
                continue

        # Last resort: try JavaScript click on any submit-like element
        try:
            clicked = await page.evaluate("""
                () => {
                    const selectors = ['#btn-login', '#kc-login', 'button[type="submit"]', 'input[type="submit"]'];
                    for (const sel of selectors) {
                        const el = document.querySelector(sel);
                        if (el) { el.click(); return true; }
                    }
                    return false;
                }
            """)
            if clicked:
                log("Login submitted (JS click)")
                return True
        except Exception:
            pass

        # Log debug info
        try:
            title = await page.title()
            url = page.url
            log(f"Submit button not found. Page: '{title}', URL: {url}", "error")
        except Exception:
            pass
        log("Login submit button not found", "error")
        return False

    async def _verify_login(self, page, log) -> bool:
        """Verify that login actually succeeded."""
        await asyncio.sleep(2)
        url = page.url.lower()
        content = (await page.content()).lower()

        # Check for error indicators
        error_phrases = [
            "invalid username or password",
            "invalid credentials",
            "incorrect password",
            "authentication failed",
            "login failed",
            "invalid email or password",
            "account is not fully set up",
        ]
        for phrase in error_phrases:
            if phrase in content:
                log(f"Login failed: '{phrase}' detected", "error")
                return False

        # Still on login/auth page?
        still_on_login = any(p in url for p in ["/login", "/auth/", "kc-login", "openid-connect"])
        if still_on_login:
            for sel in ["#email-input-field", "#username", "#password-input-field", "#password"]:
                try:
                    el = await page.query_selector(sel)
                    if el and await el.is_visible():
                        log("Still on login page — credentials may be wrong", "error")
                        return False
                except Exception:
                    pass

        return True

    # ── Navigation to Booking Page ────────────────────────────────────

    async def _find_element_by_text(self, page, target_texts: list[str]) -> Optional[object]:
        """
        Scan ALL visible elements on the page for any whose text/label/value
        matches one of the target texts (case-insensitive, exact match).
        Checks every tag type: button, a, span, div, li, td, input, p, etc.
        """
        target_lower = [t.lower() for t in target_texts]
        try:
            handle = await page.evaluate_handle("""
                (targets) => {
                    const tags = ['button','a','span','div','li','td','input','p','h1','h2','h3','h4','th','label','i','em','strong'];
                    for (const tag of tags) {
                        for (const el of document.querySelectorAll(tag)) {
                            const rect = el.getBoundingClientRect();
                            if (rect.width === 0 && rect.height === 0) continue; // skip invisible
                            const text = (el.innerText || el.textContent || '').trim().toLowerCase();
                            const aria  = (el.getAttribute('aria-label') || '').trim().toLowerCase();
                            const val   = (el.value || '').trim().toLowerCase();
                            const title = (el.getAttribute('title') || '').trim().toLowerCase();
                            if (targets.includes(text) || targets.includes(aria) || targets.includes(val) || targets.includes(title)) {
                                return el;
                            }
                        }
                    }
                    return null;
                }
            """, target_lower)
            el = handle.as_element()
            return el if el else None
        except Exception:
            return None

    async def _navigate_to_booking(self, page, service_type: str, log, branch_url: str = "") -> bool:
        """Navigate to the appointment calendar page: Group Select → Continue."""
        try:
            await self._handle_application_error(page, log)
            await self._handle_cookie_consent(page, log)

            # Wait for the page to settle before making any checks
            try:
                await page.wait_for_load_state("networkidle", timeout=10000)
            except Exception:
                pass
            await asyncio.sleep(2)

            # ── Check for "No application created" ───────────────────
            # Only bail if the VERY-SPECIFIC TLS phrase is VISIBLE as rendered text —
            # NOT just anywhere in the raw HTML (avoids false positives from loading states).
            try:
                no_app_phrase = "click on the button to create a new application"
                rendered_text = await page.evaluate("() => document.body ? document.body.innerText.toLowerCase() : ''")
                if no_app_phrase in rendered_text:
                    log("No application found on TLS website — user must create one first", "error")
                    return False
            except Exception:
                pass

            # ── Extract location keywords from branch URL for multi-app selection ──
            # e.g. egCAI2de → keywords for Cairo/Sheikh Zayed
            #      egHRG2de → keywords for Hurghada
            location_keywords: list[str] = []
            location_label = ""
            if branch_url:
                _m = re.search(r'eg([A-Z]{3})\d', branch_url)
                if _m:
                    _code = _m.group(1).upper()
                    if _code == "CAI":
                        location_keywords = [
                            "cai", "cairo", "sheikh zayed", "el-sheikh zayed",
                            "sheik zayed", "egcai",
                        ]
                        location_label = "Cairo / Sheikh Zayed"
                    elif _code == "HRG":
                        location_keywords = ["hrg", "hurghada", "eghrg"]
                        location_label = "Hurghada"

            # ── Step 0: Multi-application card detection ──────────────────
            # When 2+ applications exist under the same TLS account (e.g. Sheikh Zayed
            # + Hurghada legalization), TLS shows one card per application each with its
            # own Select button.  Pick the card whose text matches the target branch.
            select_el = None
            try:
                all_app_btns = await page.query_selector_all("button[name='formGroupId']")
                if len(all_app_btns) > 1 and location_keywords:
                    log(f"Multiple application cards found — looking for {location_label}...")
                    for _btn in all_app_btns:
                        try:
                            card_text = await page.evaluate(
                                """
                                (el) => {
                                    let node = el;
                                    for (let i = 0; i < 8; i++) {
                                        node = node.parentElement;
                                        if (!node) break;
                                        const t = (node.textContent || '').trim();
                                        if (t.length > 30) return t.toLowerCase();
                                    }
                                    return '';
                                }
                                """,
                                _btn,
                            )
                            if any(kw in card_text for kw in location_keywords):
                                select_el = _btn
                                log(f"Application card matched: {location_label}")
                                break
                        except Exception:
                            pass
                    if not select_el:
                        log(f"Could not match application to {location_label}, using first card", "warn")
                        select_el = all_app_btns[0]
                elif len(all_app_btns) == 1:
                    select_el = all_app_btns[0]
                    log("Single application found")
            except Exception:
                pass

            # ── Step 1: Find & click the "Select" group element ───────
            log("Looking for Select button...")
            if not select_el:
                select_el = None  # will be resolved by CSS fallbacks below

            # Try 1: known TLS CSS selector (class name may change with each deploy)
            for css in [
                "button[name='formGroupId']",
                "button[name='formGroupId'].TlsButton_tls-button__syUS5",
                "button.tls-button-primary.button-neo-inside",
            ]:
                try:
                    el = await page.wait_for_selector(css, timeout=8000, state="visible")
                    if el:
                        select_el = el
                        log(f"Select button found via CSS: {css}")
                        break
                except Exception:
                    pass

            # Try 2: find ANY visible element whose text/label/value is exactly "select"
            if not select_el:
                select_el = await self._find_element_by_text(page, ["select", "sélectionner", "seleccionar", "enter"])
                if select_el:
                    log("Select button found via text scan")

            # Try 3: Playwright locator — first visible "Select" text match
            if not select_el:
                try:
                    loc = page.get_by_text("Select", exact=True)
                    cnt = await loc.count()
                    for i in range(cnt):
                        candidate = loc.nth(i)
                        if await candidate.is_visible():
                            select_el = candidate
                            log(f"Select button found via locator (index {i})")
                            break
                except Exception:
                    pass

            # Try 4: JS scan for any clickable with "select" in aria/name/id attributes
            if not select_el:
                try:
                    handle = await page.evaluate_handle("""
                        () => {
                            for (const el of document.querySelectorAll('[aria-label],[name],[id],[data-testid]')) {
                                const attrs = ['aria-label','name','id','data-testid'];
                                const rect = el.getBoundingClientRect();
                                if (rect.width === 0) continue;
                                for (const a of attrs) {
                                    const v = (el.getAttribute(a) || '').toLowerCase();
                                    if (v.includes('select') || v.includes('group')) return el;
                                }
                            }
                            return null;
                        }
                    """)
                    el = handle.as_element()
                    if el:
                        select_el = el
                        log("Select button found via attribute scan")
                except Exception:
                    pass

            if not select_el:
                # Log visible page text for diagnosis
                try:
                    body = await page.evaluate("() => document.body ? document.body.innerText.slice(0, 500) : ''")
                    log(f"Could not find Select button. Page text preview: {body!r}", "error")
                except Exception:
                    log("Select / Enter button not found on page", "error")
                return False

            # Click it — try normal click first, JS click as fallback
            try:
                await select_el.scroll_into_view_if_needed()
                await asyncio.sleep(random.uniform(0.4, 0.8))
                await select_el.click()
            except Exception:
                try:
                    await page.evaluate("el => el.click()", select_el)
                except Exception as e:
                    log(f"Failed to click Select button: {e}", "error")
                    return False

            log("Group selected")
            await asyncio.sleep(4)

            # Handle application error after select
            await self._handle_application_error(page, log)

            # ── Step 2: Click "Continue" / "Book Appointment" ─────────
            if service_type == "visa":
                log("Group selected — loading appointments...")
                await asyncio.sleep(5)
            else:
                log("Looking for Continue button...")
                continue_el = None

                # Try 1: known ID
                try:
                    continue_el = await page.wait_for_selector("a#book-appointment-btn", timeout=12000, state="visible")
                    if continue_el:
                        log("Continue button found via #book-appointment-btn")
                except Exception:
                    pass

                # Try 2: text scan across all element types
                if not continue_el:
                    continue_el = await self._find_element_by_text(
                        page, ["continue", "book appointment", "book an appointment", "next", "continuer"]
                    )
                    if continue_el:
                        log("Continue button found via text scan")

                # Try 3: Playwright locator
                if not continue_el:
                    for label in ["Continue", "Book Appointment", "Book an Appointment", "Next"]:
                        try:
                            loc = page.get_by_text(label, exact=True)
                            if await loc.count() > 0 and await loc.first.is_visible():
                                continue_el = loc.first
                                log(f"Continue button found via locator: {label!r}")
                                break
                        except Exception:
                            pass

                # Try 4: CSS legacy
                if not continue_el:
                    try:
                        continue_el = await page.query_selector("button.button-neo-inside.-primary")
                    except Exception:
                        pass

                if not continue_el:
                    log("Continue / Book Appointment button not found", "error")
                    return False

                try:
                    await continue_el.scroll_into_view_if_needed()
                    await asyncio.sleep(random.uniform(0.4, 0.8))
                    await continue_el.click()
                except Exception:
                    try:
                        await page.evaluate("el => el.click()", continue_el)
                    except Exception as e:
                        log(f"Failed to click Continue button: {e}", "error")
                        return False

                log("Continue clicked")
                await asyncio.sleep(4)

            # Handle application error after continue
            await self._handle_application_error(page, log)

            # ── Verify calendar / appointment page loaded ─────────────
            calendar_selectors = [
                "[data-testid*='month']",
                ".MonthSelector_month-selector_button__An0eF",
                ".tls-appointment-time-picker", ".tls-time-picker",
                "p.text-lg.font-semibold", "p.font-semibold.text-on-surface-variant",
                ".TlsCmsContent_cms-wrapper__5pjaA",
                "a[href*='appointment-booking?month=']",
                ".bg-surface-container",
                "button[data-testid='btn-available-slot-default']",
                ".tls-popup",
            ]
            for attempt in range(3):
                for sel in calendar_selectors:
                    try:
                        el = await page.query_selector(sel)
                        if el:
                            log("Appointment calendar loaded")
                            return True
                    except Exception:
                        pass

                rendered = await page.evaluate("() => document.body ? document.body.innerText.toLowerCase() : ''")
                if ("appointment" in rendered and ("slot" in rendered or "month" in rendered)) or \
                   "don't have any" in rendered or "currently available" in rendered or \
                   "no appointment" in rendered:
                    log("Appointment page loaded")
                    return True

                await asyncio.sleep(2)
                await self._handle_application_error(page, log)

            log("Could not navigate to appointment booking page", "error")
            return False

        except Exception as e:
            log(f"Navigation failed: {e}", "error")
            return False

    # ── Slot Checking ─────────────────────────────────────────────────

    async def _check_slots(self, page, service_type: str, branch_name: str, log) -> tuple[bool, dict | None, str]:
        """
        Check for available appointment slots across all available months.
        Returns: (slots_available, slot_details_dict, message_str)
        """
        try:
            log("Checking for appointments...")
            any_slots_found = False
            all_results = []
            full_slot_details = []

            # Wait for page ready
            try:
                await page.wait_for_load_state("networkidle", timeout=10000)
            except Exception:
                pass
            await asyncio.sleep(1)

            await self._handle_application_error(page, log)

            # ── Check for immediate "no slots" popup ──────────────
            try:
                popup = await page.wait_for_selector(".tls-popup", timeout=3000)
                if popup:
                    popup_text = (await popup.inner_text()).lower()
                    if any(p in popup_text for p in [
                        "no appointment", "no slot", "not available", "unavailable"
                    ]):
                        log("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
                        log("NO APPOINTMENTS AVAILABLE (popup)")
                        log("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
                        # Close popup
                        try:
                            close_btns = await page.query_selector_all(
                                "button.tls-button-primary, button[data-tls-value='confirm'], .tls-popup button"
                            )
                            for btn in close_btns:
                                try:
                                    await btn.click()
                                    await asyncio.sleep(1)
                                    break
                                except Exception:
                                    continue
                        except Exception:
                            pass
                        return False, None, "No appointments (popup)"
            except Exception:
                pass  # No popup — continue

            # ── Discover months ───────────────────────────────────
            checked_months = set()
            months_to_check = []

            for _attempt in range(5):
                initial_months = await self._get_available_months(page)
                if initial_months:
                    break
                await asyncio.sleep(1)

            # If no month selectors, check current page for no-slots message
            if not initial_months:
                content = (await page.content()).lower()
                no_slot_phrases = [
                    "don't have any", "no slot", "not available",
                    "currently available", "check this page",
                ]
                if any(p in content for p in no_slot_phrases):
                    log("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
                    log("NO APPOINTMENTS AVAILABLE (current month)")
                    log("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
                    initial_months = await self._get_available_months(page)

            # Visa fallback: generate month URLs from current URL
            if not initial_months and "visas-de.tlscontact.com" in page.url:
                log("Using backup month URLs for visa site...")
                now = datetime.now()
                month_names = ['January', 'February', 'March', 'April', 'May', 'June',
                               'July', 'August', 'September', 'October', 'November', 'December']
                wf_match = re.search(r'(https://visas-de\.tlscontact\.com/\S+?/workflow)', page.url)
                if wf_match:
                    base_wf = wf_match.group(1)
                    for offset in range(3):
                        m = now.month + offset
                        y = now.year
                        if m > 12:
                            m -= 12
                            y += 1
                        month_str = f"{m:02d}-{y}"
                        name = f"{month_names[m - 1]} {y}"
                        url = f"{base_wf}/appointment-booking?month={month_str}"
                        initial_months.append((name, url))

            if not initial_months:
                # Try legacy slot check
                log("No month selectors found, trying legacy layout...")
                legacy_result = await self._check_slots_legacy(page, log)
                return legacy_result

            months_to_check.extend(initial_months)
            log(f"Starting with {len(months_to_check)} visible month(s)")

            # ── Process each month ────────────────────────────────
            while months_to_check:
                month_name, month_link = months_to_check.pop(0)
                if month_name in checked_months:
                    continue
                checked_months.add(month_name)

                log(f"Checking {month_name}...")

                # Navigate to the month
                if month_link:
                    month_ok = False
                    for recovery in range(3):
                        try:
                            await page.goto(month_link, wait_until="networkidle", timeout=30000)
                            await asyncio.sleep(2)
                            if await self._handle_application_error(page, log):
                                month_ok = True
                                break
                        except Exception:
                            await asyncio.sleep(2)
                    if not month_ok:
                        # Attempt direct URL construction as fallback
                        try:
                            from urllib.parse import urlparse, parse_qs, urljoin
                            _month_names = ['January', 'February', 'March', 'April', 'May', 'June',
                                            'July', 'August', 'September', 'October', 'November', 'December']
                            _parts = month_name.split()
                            if len(_parts) >= 2 and _parts[0] in _month_names:
                                _m = _month_names.index(_parts[0]) + 1
                                _y = _parts[1]
                                _month_str = f"{_m:02d}-{_y}"
                                # Resolve month_link to absolute URL using current page URL as base
                                _src = month_link or page.url
                                _abs = urljoin(page.url, _src)
                                _p = urlparse(_abs)
                                _qs = parse_qs(_p.query)
                                _loc = _qs.get('location', [''])[0]
                                _base = re.sub(r'/appointment-booking.*', '', _p.path)
                                _new_q = f"location={_loc}&month={_month_str}" if _loc else f"month={_month_str}"
                                direct_url = f"{_p.scheme}://{_p.netloc}{_base}/appointment-booking?{_new_q}"
                                log(f"Retrying {month_name} via direct URL fallback...")
                                await page.goto(direct_url, wait_until="networkidle", timeout=30000)
                                await asyncio.sleep(2)
                                await self._handle_application_error(page, log)
                            else:
                                log(f"Could not build fallback URL for {month_name}, skipping", "warn")
                                continue
                        except Exception as e:
                            log(f"Direct URL fallback failed for {month_name}: {e}, skipping", "warn")
                            continue

                # Check for "no slots" on this month
                no_slots = False
                try:
                    no_els = await page.query_selector_all(
                        "p.text-lg.font-semibold, .text-center p.font-semibold, "
                        "p.font-semibold.text-on-surface-variant, .TlsCmsContent_cms-wrapper__5pjaA p"
                    )
                    for el in no_els:
                        txt = (await el.inner_text()).lower()
                        if any(p in txt for p in [
                            "don't have any appointment", "no slots",
                            "not available", "currently available",
                        ]):
                            no_slots = True
                            break
                except Exception:
                    pass

                if no_slots:
                    log(f"{month_name}: No appointments available")
                    all_results.append(f"{month_name}: No slots")
                    newly = await self._get_available_months(page)
                    for nm, nl in newly:
                        if nm not in checked_months:
                            months_to_check.append((nm, nl))
                    continue

                # Check for popup on this month
                try:
                    popup = await page.wait_for_selector(".tls-popup", timeout=2000)
                    if popup:
                        popup_text = (await popup.inner_text()).lower()
                        if any(p in popup_text for p in ["no appointment", "no slot", "not available"]):
                            log(f"{month_name}: No appointments available (popup)")
                            all_results.append(f"{month_name}: No slots")
                            try:
                                close_btn = await page.query_selector(
                                    "button.tls-button-primary, button[data-tls-value='confirm']"
                                )
                                if close_btn:
                                    await close_btn.click()
                                    await asyncio.sleep(1)
                            except Exception:
                                pass
                            newly = await self._get_available_months(page)
                            for nm, nl in newly:
                                if nm not in checked_months:
                                    months_to_check.append((nm, nl))
                            continue
                except Exception:
                    pass

                # Look for available slot buttons
                available_buttons = await page.query_selector_all(
                    "button[data-testid='btn-available-slot-default']"
                )

                if not available_buttons:
                    log(f"{month_name}: No appointments available")
                    all_results.append(f"{month_name}: No slots")
                    newly = await self._get_available_months(page)
                    for nm, nl in newly:
                        if nm not in checked_months:
                            months_to_check.append((nm, nl))
                    continue

                # ── SLOTS FOUND! ──────────────────────────────────
                any_slots_found = True
                slot_count = len(available_buttons)

                # Parse day groups for details
                day_groups = await page.query_selector_all(
                    ".AppointmentDay_appointment-day__1Qnz1, .appointment-day"
                )
                slot_day_details = []
                for dg in day_groups:
                    try:
                        label_parts = await dg.query_selector_all("p span")
                        if len(label_parts) >= 2:
                            day_name = (await label_parts[0].inner_text()).strip()
                            day_num = (await label_parts[1].inner_text()).strip()
                            day_label = f"{day_name} {day_num}"
                        else:
                            p = await dg.query_selector("p")
                            day_label = (await p.inner_text()).strip() if p else "Unknown"

                        avail_btns = await dg.query_selector_all(
                            "button[data-testid='btn-available-slot-default']"
                        )
                        if avail_btns:
                            times = []
                            for ab in avail_btns:
                                t = (await ab.inner_text()).strip()
                                if t:
                                    times.append(t)
                            slot_day_details.append({
                                "day": day_label,
                                "times": times,
                            })
                    except Exception:
                        continue

                log("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
                log(f"APPOINTMENTS FOUND! {month_name} ({slot_count} slots)")
                for sd in slot_day_details:
                    log(f"  {sd['day']}: {', '.join(sd['times'])}")
                log("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")

                full_slot_details.extend(slot_day_details)
                all_results.append(f"{month_name}: {slot_count} slots found")

                # Discover new months
                newly = await self._get_available_months(page)
                for nm, nl in newly:
                    if nm not in checked_months:
                        months_to_check.append((nm, nl))

            # ── Summary ───────────────────────────────────────────
            if not any_slots_found:
                log("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
                log(f"NO APPOINTMENTS in any month (checked {len(checked_months)} months)")
                log("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
                return False, None, f"Checked {len(checked_months)} months — no slots"

            details = {
                "message": "Appointment slots detected!",
                "branch": branch_name,
                "slots": full_slot_details,
                "months_checked": len(checked_months),
            }
            return True, details, "; ".join(all_results)

        except Exception as e:
            log(f"Error checking slots: {e}", "error")
            return False, None, f"Error: {str(e)}"

    async def _get_available_months(self, page) -> list[tuple[str, str | None]]:
        """Return list of (month_name, full_url_or_None) for months on the calendar page."""
        from urllib.parse import urljoin
        months = []
        base_url = page.url
        try:
            # Strategy 1: New TLS layout - MonthSelector links
            selected = await page.query_selector_all(
                "a.MonthSelector_month-selector_button__An0eF.MonthSelector_--selected__5re9q"
            )
            if selected:
                name = (await selected[0].inner_text()).strip()
                months.append((name, None))

            month_links = await page.query_selector_all(
                "a.MonthSelector_month-selector_button__An0eF"
            )
            for link in month_links:
                name = (await link.inner_text()).strip()
                href = await link.get_attribute("href")
                cls = await link.get_attribute("class") or ""
                if "--selected" in cls:
                    continue
                if href and name:
                    months.append((name, urljoin(base_url, href)))

            # Strategy 2: Broader selector
            if not months:
                all_links = await page.query_selector_all(
                    "a[href*='appointment-booking?month='], a[data-testid*='month']"
                )
                for link in all_links:
                    name = (await link.inner_text()).strip()
                    href = await link.get_attribute("href")
                    if name and href:
                        months.append((name, urljoin(base_url, href)))

            # Strategy 3: Infer from URL
            if not months:
                content = (await page.content()).lower()
                no_slot_phrases = ["don't have", "no slot", "not available", "currently available"]
                if any(p in content for p in no_slot_phrases):
                    current_url = page.url
                    if "month=" in current_url:
                        m = re.search(r'month=(\d{2})-(\d{4})', current_url)
                        if m:
                            month_num, year = int(m.group(1)), m.group(2)
                            month_names = ['January', 'February', 'March', 'April', 'May', 'June',
                                           'July', 'August', 'September', 'October', 'November', 'December']
                            name = f"{month_names[month_num - 1]} {year}"
                            months.append((name, None))
                    else:
                        months.append(("Current Month", None))

        except Exception as e:
            logger.warning(f"Error getting months: {e}")
        return months

    async def _check_slots_legacy(self, page, log) -> tuple[bool, dict | None, str]:
        """Legacy slot check for older TLS layout (popup-based / time-unit based)."""
        try:
            # Check for popup
            try:
                popup = await page.wait_for_selector(".tls-popup", timeout=10000)
                if popup:
                    log("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
                    log("NO APPOINTMENTS AVAILABLE (legacy popup)")
                    log("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
                    try:
                        btn = await page.query_selector(
                            "button.tls-button-primary.-uppercase[data-tls-value='confirm']"
                        )
                        if btn:
                            await btn.click()
                            await asyncio.sleep(1)
                    except Exception:
                        pass
                    return False, None, "No appointments (legacy popup)"
            except Exception:
                pass

            # Check for available time slots
            available_slots = await page.query_selector_all(
                ".tls-time-unit:not(.-unavailable)"
            )
            if not available_slots:
                log("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
                log("NO APPOINTMENTS AVAILABLE (legacy)")
                log("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
                return False, None, "No appointments (legacy)"

            slot_count = len(available_slots)
            log("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
            log(f"APPOINTMENTS AVAILABLE! ({slot_count} slots)")
            log("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
            details = {"message": "Appointment slots detected!", "count": slot_count}
            return True, details, f"{slot_count} slots found (legacy)"

        except Exception as e:
            log(f"Error in legacy check: {e}", "error")
            return False, None, f"Legacy error: {str(e)}"


# Singleton
tls_checker = TLSChecker()
