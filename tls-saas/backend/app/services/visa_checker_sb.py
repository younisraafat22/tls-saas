"""
TLS Visa Checker — SeleniumBase UC (Undetected Chrome) mode.

The TLS Visa site (visas-de.tlscontact.com) uses strict Cloudflare/Turnstile
protection that causes Patchright to time out on page load. SeleniumBase with
uc=True (undetected-chrome) bypasses this natively.

Called by TLSChecker.check_branch() when service_type == "visa".
"""

import logging
import os
import random
import re
import subprocess
import sys
import time
from datetime import datetime
from typing import Optional

from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException

from app.config import settings

logger = logging.getLogger("visa_checker_sb")


def _wait(min_s: float = 0.5, max_s: float = 1.5):
    time.sleep(random.uniform(min_s, max_s))


class VisaCheckerSB:
    """
    Synchronous SeleniumBase UC driver for TLS Visa branch checks.
    Designed to be run in a thread pool from async code.
    """

    def check(
        self,
        branch_url: str,
        tls_email: str,
        tls_password: str,
        branch_name: str = "",
    ) -> dict:
        result = {
            "slots_available": False,
            "slot_details": None,
            "screenshot": None,
            "error": "",
            "duration": 0,
            "logs": [],
        }
        start = time.time()

        def log(msg: str, level: str = "info"):
            result["logs"].append({"level": level, "message": msg})
            if level == "error":
                logger.error(f"[{branch_name}] {msg}")
            elif level == "warn":
                logger.warning(f"[{branch_name}] {msg}")
            else:
                logger.info(f"[{branch_name}] {msg}")

        driver = None
        try:
            from seleniumbase import Driver

            # IMPORTANT: UC mode CANNOT bypass Cloudflare/Turnstile in headless=True.
            # Use the real desktop display (:0) if available, otherwise Xvfb.
            if sys.platform != "win32":
                # Prefer real desktop session (much better for CF bypass)
                real_display = None
                for d in [":0", ":1"]:
                    if os.path.exists(f"/tmp/.X11-unix/X{d[1:]}"):
                        real_display = d
                        break
                if real_display:
                    os.environ["DISPLAY"] = real_display
                    log(f"Using real display {real_display}")
                elif not os.environ.get("DISPLAY"):
                    try:
                        subprocess.Popen(["Xvfb", ":99", "-screen", "0", "1920x1080x24"],
                                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                        time.sleep(1)
                        os.environ["DISPLAY"] = ":99"
                        log("Started Xvfb virtual display :99")
                    except Exception as _xe:
                        log(f"Xvfb start warning: {_xe}", "warn")

            log("Opening TLS Visa website (SeleniumBase UC mode)...")
            driver = Driver(
                uc=True,
                headless=False,   # Must be False — headless is detectable by Cloudflare
                no_sandbox=True,
                disable_gpu=True,
            )
            driver.set_page_load_timeout(90)
            driver.implicitly_wait(3)
            driver.maximize_window()  # Ensures LOGIN text button is visible (not collapsed to icon)

            # Navigate — uc_open_with_reconnect disconnects devtools during CF
            # challenge so Cloudflare cannot detect automation, then reconnects.
            log("Navigating with uc_open_with_reconnect...")
            driver.uc_open_with_reconnect(branch_url, reconnect_time=6)
            _wait(2, 3)

            # If Turnstile checkbox is present, click it
            if self._has_cloudflare(driver):
                log("Cloudflare/Turnstile still present, clicking captcha checkbox...")
                try:
                    driver.uc_gui_click_captcha()
                    _wait(3, 5)
                except Exception as ce:
                    log(f"uc_gui_click_captcha failed: {ce}", "warn")

            # If STILL present, try reconnect + click again
            if self._has_cloudflare(driver):
                log("Retrying: reconnect + click captcha...")
                try:
                    driver.uc_open_with_reconnect(branch_url, reconnect_time=10)
                    _wait(2, 3)
                    driver.uc_gui_click_captcha()
                    _wait(3, 5)
                except Exception as ce:
                    log(f"Retry failed: {ce}", "warn")

            if self._has_cloudflare(driver):
                log("Cloudflare still present after all attempts — waiting up to 30s...")
                self._wait_cloudflare(driver, log, max_wait=30)

            # Accept cookies
            self._accept_cookies(driver)

            # Click Login
            if not self._click_login(driver, log):
                result["error"] = "Login button not found"
                try:
                    result["screenshot"] = driver.get_screenshot_as_png()
                except Exception:
                    pass
                return result

            _wait(2, 3)
            self._accept_cookies(driver)

            # Fill credentials
            log("Logging in...")
            if not self._fill_credentials(driver, tls_email, tls_password, log):
                result["error"] = "Login form not found"
                return result

            # Submit login
            if not self._submit_login(driver, log):
                result["error"] = "Submit button not found"
                return result

            _wait(4, 6)

            # Verify login
            if not self._verify_login(driver, tls_email, log):
                result["error"] = "Login failed — invalid credentials or CAPTCHA"
                try:
                    result["screenshot"] = driver.get_screenshot_as_png()
                except Exception:
                    pass
                return result

            log("Login successful")

            # Navigate to booking
            if not self._navigate_to_booking(driver, log, branch_url):
                result["error"] = "Could not navigate to appointment booking page"
                try:
                    result["screenshot"] = driver.get_screenshot_as_png()
                except Exception:
                    pass
                return result

            # Check slots
            slots_available, slot_details, msg = self._check_slots(driver, branch_name, log)
            result["slots_available"] = slots_available
            result["slot_details"] = slot_details

            if slots_available:
                log(f"*** APPOINTMENTS FOUND! *** {msg}")
            else:
                log(f"No appointments available ({msg})")

            try:
                result["screenshot"] = driver.get_screenshot_as_png()
            except Exception:
                pass

        except Exception as e:
            result["error"] = str(e)
            log(f"Check failed: {e}", "error")
            if driver:
                try:
                    result["screenshot"] = driver.get_screenshot_as_png()
                except Exception:
                    pass
        finally:
            if driver:
                try:
                    driver.quit()
                except Exception:
                    pass
            result["duration"] = round(time.time() - start, 2)

        return result

    # ── Cloudflare ────────────────────────────────────────────────────

    _CF_INDICATORS = [
        "just a moment",
        "checking your browser",
        "cf-browser-verification",
        "challenge-platform",
    ]

    def _has_cloudflare(self, driver) -> bool:
        """Return True only if a real CF challenge page is active (not just CF scripts on a normal page)."""
        try:
            # Title is the most reliable signal — CF challenge page is titled "Just a moment..."
            title = driver.title.lower()
            if "just a moment" in title:
                return True
            # Only check body text for actual challenge phrases, excluding script content
            body_text = driver.execute_script(
                "return document.body ? document.body.innerText.toLowerCase() : '';"
            )
            return any(ind in body_text for ind in self._CF_INDICATORS)
        except Exception:
            return False

    def _wait_cloudflare(self, driver, log, max_wait: int = 90):
        """Wait for Cloudflare challenge / Turnstile to pass."""
        start = time.time()
        while time.time() - start < max_wait:
            if self._has_cloudflare(driver):
                log("Cloudflare challenge detected, waiting...")
                time.sleep(3)
                continue
            log("Page loaded (Cloudflare passed)")
            return
        log("Cloudflare wait timed out — proceeding anyway", "warn")

    # ── Cookie Consent ────────────────────────────────────────────────

    def _accept_cookies(self, driver):
        """Dismiss Osano / generic cookie consent banners."""
        selectors = [
            "button.osano-cm-accept-all",
            ".osano-cm-accept-all",
            "button[class*='osano-cm-accept']",
            ".osano-cm-button--type_accept",
        ]
        for sel in selectors:
            try:
                els = driver.find_elements(By.CSS_SELECTOR, sel)
                for el in els:
                    if el.is_displayed():
                        el.click()
                        time.sleep(0.5)
                        return
            except Exception:
                continue
        # Generic accept buttons
        try:
            for btn in driver.find_elements(By.TAG_NAME, "button"):
                if btn.text.strip().lower() in ("accept all", "accept", "save") and btn.is_displayed():
                    btn.click()
                    time.sleep(0.5)
                    return
        except Exception:
            pass

    # ── Login Flow ────────────────────────────────────────────────────

    def _click_login(self, driver, log) -> bool:
        """Find and click the LOGIN button on the TLS home page."""
        # TLS-specific CSS selectors (text button — only visible when maximized)
        for sel in [
            "span.TlsButton_tls-button__syUS5",
            "[class*='TlsButton'][class*='--outline']",
            "a.tls-button-link",
        ]:
            try:
                els = driver.find_elements(By.CSS_SELECTOR, sel)
                for el in els:
                    if el.text.strip().upper() == "LOGIN" and el.is_displayed():
                        driver.execute_script("arguments[0].click();", el)
                        log("Clicked LOGIN button")
                        return True
            except Exception:
                continue

        # Scan by text
        for tag in ["a", "button", "span"]:
            try:
                for el in driver.find_elements(By.TAG_NAME, tag):
                    if el.text.strip().upper() in ("LOGIN", "LOG IN") and el.is_displayed():
                        driver.execute_script("arguments[0].click();", el)
                        log("Clicked LOGIN button (text scan)")
                        return True
            except Exception:
                continue

        # Small-screen fallback: SVG User icon (shown when window is narrow)
        try:
            icon_svg = driver.find_element(By.CSS_SELECTOR, "svg[aria-label='User icon']")
            login_btn = icon_svg.find_element(By.XPATH, "..")
            driver.execute_script("arguments[0].click();", login_btn)
            log("Clicked SVG User icon login button")
            return True
        except Exception:
            pass

        # div#login fallback
        try:
            login_div = driver.find_element(By.CSS_SELECTOR, "div#login, [id='login']")
            driver.execute_script("arguments[0].click();", login_div)
            log("Clicked login div")
            return True
        except Exception:
            pass

        # Wait up to 20s for delayed button, then retry all
        log("LOGIN button not found yet, waiting...")
        time.sleep(10)
        for sel in [
            "span.TlsButton_tls-button__syUS5",
            "[class*='TlsButton'][class*='--outline']",
        ]:
            try:
                els = driver.find_elements(By.CSS_SELECTOR, sel)
                for el in els:
                    if el.text.strip().upper() == "LOGIN" and el.is_displayed():
                        driver.execute_script("arguments[0].click();", el)
                        log("Clicked LOGIN button (after wait)")
                        return True
            except Exception:
                continue
        try:
            icon_svg = driver.find_element(By.CSS_SELECTOR, "svg[aria-label='User icon']")
            login_btn = icon_svg.find_element(By.XPATH, "..")
            driver.execute_script("arguments[0].click();", login_btn)
            log("Clicked SVG User icon (after wait)")
            return True
        except Exception:
            pass

        return False

    def _fill_credentials(self, driver, email: str, password: str, log) -> bool:
        """Fill the TLS login form."""
        email_field = None
        for sel in ["#email-input-field", "#username", "input[type='email']", "input[name='email']"]:
            try:
                f = driver.find_element(By.CSS_SELECTOR, sel)
                if f.is_displayed():
                    email_field = f
                    break
            except Exception:
                continue

        password_field = None
        for sel in ["#password-input-field", "#password", "input[type='password']"]:
            try:
                f = driver.find_element(By.CSS_SELECTOR, sel)
                if f.is_displayed():
                    password_field = f
                    break
            except Exception:
                continue

        if not email_field or not password_field:
            log("Login form fields not found", "error")
            return False

        email_field.clear()
        email_field.send_keys(email)
        _wait(0.5, 1)
        password_field.clear()
        password_field.send_keys(password)
        _wait(0.5, 1)
        log("Credentials entered")
        return True

    def _submit_login(self, driver, log) -> bool:
        """Submit the login form."""
        for sel in [
            "button[type='submit']",
            "button.tls-button-primary",
            "button[class*='tls-button-primary']",
        ]:
            try:
                els = driver.find_elements(By.CSS_SELECTOR, sel)
                for el in els:
                    if el.is_displayed():
                        txt = el.text.strip().upper()
                        if txt in ("LOGIN", "LOG IN", "SIGN IN", "SUBMIT", "CONTINUE", ""):
                            el.click()
                            log("Clicked submit button")
                            return True
            except Exception:
                continue

        # Last resort: submit the form via JS
        try:
            driver.execute_script(
                "var f = document.querySelector('form'); if(f) f.submit();"
            )
            log("Submitted form via JS")
            return True
        except Exception:
            pass

        return False

    def _verify_login(self, driver, email: str, log) -> bool:
        """Verify login succeeded by checking page content and URL."""
        time.sleep(2)
        body = driver.page_source.lower()

        # Explicit failure indicators
        for fail_phrase in [
            "invalid credentials", "incorrect password", "wrong password",
            "authentication failed", "invalid email", "bad credentials",
            "login failed", "incorrect email",
        ]:
            if fail_phrase in body:
                log(f"Login failed — detected: '{fail_phrase}'", "error")
                return False

        # Still on the login page?
        try:
            ef = driver.find_element(By.CSS_SELECTOR, "input[type='email'], #email-input-field")
            if ef.is_displayed():
                log("Login failed — still on login page", "error")
                return False
        except Exception:
            pass  # email field gone → logged in

        # URL no longer contains login
        url = driver.current_url.lower()
        if "login" not in url and "sign-in" not in url:
            log("Login verified (URL changed)")
            return True

        log("Login status unclear — assuming success", "warn")
        return True

    # ── Navigation to Booking ────────────────────────────────────────

    def _navigate_to_booking(self, driver, log, branch_url: str = "") -> bool:
        """Click Select → (Continue for legalization / skip for visa) → appointment calendar."""
        try:
            self._accept_cookies(driver)
            time.sleep(2)

            # Extract location keywords from URL for multi-app card matching
            location_keywords: list[str] = []
            if branch_url:
                m = re.search(r'eg([A-Z]{3})\d', branch_url)
                if m:
                    code = m.group(1).upper()
                    if code == "CAI":
                        location_keywords = ["cai", "cairo", "sheikh zayed", "egcai"]
                    elif code == "HRG":
                        location_keywords = ["hrg", "hurghada", "eghrg"]
                    elif code == "HAC":
                        location_keywords = ["hac", "new cairo", "eghac"]
                    elif code == "ALY":
                        location_keywords = ["aly", "alexandria", "egaly"]

            # ── Step 1: Find Select button ────────────────────────────
            log("Looking for Select button...")
            select_el = None

            # Wait up to 20s for the primary button selector (with class)
            for css in [
                "button[name='formGroupId'].TlsButton_tls-button__syUS5",
                "button[name='formGroupId']",
            ]:
                try:
                    found = WebDriverWait(driver, 20).until(
                        EC.presence_of_all_elements_located((By.CSS_SELECTOR, css))
                    )
                    if found:
                        if len(found) > 1 and location_keywords:
                            for btn in found:
                                try:
                                    card_text = driver.execute_script(
                                        """
                                        var el = arguments[0];
                                        for (var i = 0; i < 8; i++) {
                                            el = el.parentElement;
                                            if (!el) break;
                                            if (el.textContent.trim().length > 30)
                                                return el.textContent.toLowerCase();
                                        }
                                        return '';
                                        """,
                                        btn,
                                    )
                                    if any(kw in card_text for kw in location_keywords):
                                        select_el = btn
                                        log("Matched application card to location")
                                        break
                                except Exception:
                                    pass
                            if not select_el:
                                select_el = found[0]
                        else:
                            select_el = found[0]
                        break
                except Exception:
                    continue

            # Fallback: any button with text SELECT
            if not select_el:
                try:
                    for btn in driver.find_elements(By.TAG_NAME, "button"):
                        if btn.text.strip().upper() == "SELECT" and btn.is_displayed():
                            select_el = btn
                            break
                except Exception:
                    pass

            # If still no Select button, NOW check for "no application" indicators
            if not select_el:
                try:
                    body_text = driver.execute_script("return document.body.innerText;").lower()
                    no_app_indicators = [
                        "no application created",
                        "no application",
                    ]
                    if any(ind in body_text for ind in no_app_indicators):
                        log("No TLS application found — user must create one first", "error")
                    else:
                        log("Select button not found (page may still be loading)", "error")
                except Exception:
                    log("Select button not found", "error")
                return False

            driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", select_el)
            _wait(0.5, 1)
            driver.execute_script("arguments[0].click();", select_el)
            log("Clicked Select")
            _wait(3, 5)

            # ── Step 2: Visa goes straight to appointments — skip Continue ──
            log("Group selected – loading appointments...")
            _wait(4, 6)

            # ── Step 3: Verify appointment/booking page loaded ─────────
            for _ in range(10):
                url = driver.current_url.lower()
                if any(k in url for k in ("appointment-booking", "appointment", "booking", "workflow")):
                    log("Appointment page loaded")
                    return True
                try:
                    body_text = driver.execute_script("return document.body.innerText;").lower()
                    if any(k in body_text for k in ("calendar", "slot", "month", "don't have any", "available")):
                        log("Appointment page loaded (calendar/slot text detected)")
                        return True
                except Exception:
                    pass
                # Also check for month-link anchors
                try:
                    if driver.find_elements(By.CSS_SELECTOR, "a[href*='appointment-booking?month=']"):
                        log("Appointment page loaded (month links found)")
                        return True
                except Exception:
                    pass
                time.sleep(2)

            log("Could not confirm booking page — proceeding anyway", "warn")
            return True

        except Exception as e:
            log(f"Navigation to booking failed: {e}", "error")
            return False

    # ── Slot Checking ────────────────────────────────────────────────

    def _check_slots(self, driver, branch_name: str, log) -> tuple[bool, Optional[dict], str]:
        """Check all available months for appointment slots."""
        try:
            log("Checking for appointments...")
            time.sleep(2)

            # Immediate no-slots popup?
            try:
                popup = driver.find_element(By.CSS_SELECTOR, ".tls-popup")
                if any(p in popup.text.lower() for p in ["no appointment", "no slot", "not available"]):
                    log("━━━ NO APPOINTMENTS AVAILABLE (popup)")
                    for btn in driver.find_elements(By.CSS_SELECTOR, ".tls-popup button"):
                        try:
                            btn.click()
                            break
                        except Exception:
                            pass
                    return False, None, "No appointments (popup)"
            except Exception:
                pass

            # Gather months
            checked_months: set[str] = set()
            months_to_check = self._get_months(driver)

            # Visa fallback: build month URLs from workflow URL
            if not months_to_check and "visas-de.tlscontact.com" in driver.current_url:
                log("Building month URLs from current URL...")
                wf_match = re.search(r'(https://visas-de\.tlscontact\.com/\S+?/workflow)', driver.current_url)
                if wf_match:
                    base_wf = wf_match.group(1)
                    month_names = [
                        "January", "February", "March", "April", "May", "June",
                        "July", "August", "September", "October", "November", "December",
                    ]
                    now = datetime.now()
                    for offset in range(3):
                        m = now.month + offset
                        y = now.year
                        if m > 12:
                            m -= 12
                            y += 1
                        url = f"{base_wf}/appointment-booking?month={m:02d}-{y}"
                        months_to_check.append((f"{month_names[m-1]} {y}", url))

            if not months_to_check:
                body = driver.page_source.lower()
                if any(p in body for p in ["don't have any", "no slot", "not available"]):
                    log("━━━ NO APPOINTMENTS AVAILABLE (page content)")
                    return False, None, "No appointments"
                slots = self._find_available_dates(driver)
                if slots:
                    return True, {"available_dates": slots}, str(slots)
                return False, None, "No month selectors found"

            log(f"Starting with {len(months_to_check)} month(s)")
            found_slots: list[str] = []

            while months_to_check:
                month_name, month_url = months_to_check.pop(0)
                if month_name in checked_months:
                    continue
                checked_months.add(month_name)

                log(f"Checking {month_name}...")

                if month_url:
                    try:
                        driver.get(month_url)
                        time.sleep(3)
                    except Exception as e:
                        log(f"Failed to load {month_name}: {e}", "warn")
                        continue

                # No-slots message check
                no_slots = self._is_no_slots_page(driver)
                if no_slots:
                    log(f"{month_name}: No appointments available")
                    for nm, nl in self._get_months(driver):
                        if nm not in checked_months:
                            months_to_check.append((nm, nl))
                    continue

                # Find available dates
                slots = self._find_available_dates(driver)
                if slots:
                    log(f"{month_name}: SLOTS FOUND — {slots}")
                    found_slots.extend(slots)
                else:
                    log(f"{month_name}: No available dates")

                for nm, nl in self._get_months(driver):
                    if nm not in checked_months:
                        months_to_check.append((nm, nl))

            if found_slots:
                unique = list(dict.fromkeys(found_slots))
                return True, {"available_dates": unique, "message": f"Slots: {', '.join(unique[:5])}"}, str(unique)
            return False, None, "No appointments in any checked month"

        except Exception as e:
            log(f"Slot check error: {e}", "error")
            return False, None, f"Error: {e}"

    def _is_no_slots_page(self, driver) -> bool:
        """Return True if a DOM element clearly says no appointments available.
        Checks specific visible elements only — NOT page_source — to avoid matching
        CSS class names or script text that contain 'not available'.
        """
        no_slot_phrases = [
            "don't have any appointment",
            "no slots",
            "currently available",   # part of "not currently available"
        ]
        # First: check if there are actual available slot buttons — if yes, return False immediately
        try:
            avail = driver.find_elements(
                By.CSS_SELECTOR, "button[data-testid='btn-available-slot-default']"
            )
            if avail:
                return False
        except Exception:
            pass

        # Check specific CMS / page text elements only
        try:
            for sel in [
                "p.text-lg.font-semibold",
                ".text-center p.font-semibold",
                "p.font-semibold.text-on-surface-variant",
                ".TlsCmsContent_cms-wrapper__5pjaA p",
            ]:
                for el in driver.find_elements(By.CSS_SELECTOR, sel):
                    try:
                        if el.is_displayed():
                            txt = el.text.lower()
                            if any(p in txt for p in no_slot_phrases):
                                return True
                    except Exception:
                        continue
        except Exception:
            pass
        return False

    def _get_months(self, driver) -> list[tuple[str, str]]:
        """Extract navigable month links from the TLS appointment page.
        Ported from the original app's _get_available_months().
        Excludes already-selected and disabled months.
        """
        months: list[tuple[str, str]] = []
        seen_names: set[str] = set()
        try:
            # ── Strategy 1: TLS MonthSelector component (new layout) ──
            # Add currently selected month with None URL (already on this page)
            selected = driver.find_elements(
                By.CSS_SELECTOR,
                "a.MonthSelector_month-selector_button__An0eF.MonthSelector_--selected__5re9q",
            )
            if selected:
                name = selected[0].text.strip()
                if name and name not in seen_names:
                    months.append((name, None))
                    seen_names.add(name)

            # Navigable (non-selected, non-disabled) month links
            all_month_links = driver.find_elements(
                By.CSS_SELECTOR, "a.MonthSelector_month-selector_button__An0eF"
            )
            for link in all_month_links:
                try:
                    cls = link.get_attribute("class") or ""
                    if "--selected" in cls or "--disabled" in cls:
                        continue
                    name = link.text.strip()
                    href = link.get_attribute("href") or ""
                    if name and href and name not in seen_names:
                        months.append((name, href))
                        seen_names.add(name)
                except Exception:
                    continue

            if months:
                return months

            # ── Strategy 2: any anchor with month= in href ─────────────
            for link in driver.find_elements(
                By.CSS_SELECTOR,
                "a[href*='appointment-booking?month='], a[data-testid*='month']",
            ):
                try:
                    name = link.text.strip()
                    href = link.get_attribute("href") or ""
                    if name and href and name not in seen_names:
                        months.append((name, href))
                        seen_names.add(name)
                except Exception:
                    continue

            # ── Strategy 3: infer current month from URL if no-slots page ─
            if not months:
                try:
                    url = driver.current_url
                    m = re.search(r'month=(\d{2})-(\d{4})', url)
                    if m:
                        month_num, year = int(m.group(1)), m.group(2)
                        month_names_list = [
                            'January','February','March','April','May','June',
                            'July','August','September','October','November','December',
                        ]
                        name = f"{month_names_list[month_num-1]} {year}"
                        if name not in seen_names:
                            months.append((name, None))
                except Exception:
                    pass

        except Exception:
            pass
        return months

    def _find_available_dates(self, driver) -> list[str]:
        """Find available appointment slot buttons.
        Primary: TLS's exact data-testid attribute.
        Fallback: day groups + time buttons.
        """
        available: list[str] = []
        try:
            # ── Primary: exact TLS selector from original app ──────────
            slot_btns = driver.find_elements(
                By.CSS_SELECTOR, "button[data-testid='btn-available-slot-default']"
            )
            if slot_btns:
                # Try to pair with day labels for richer detail
                day_groups = driver.find_elements(
                    By.CSS_SELECTOR,
                    ".AppointmentDay_appointment-day__1Qnz1, .appointment-day",
                )
                if day_groups:
                    for group in day_groups:
                        try:
                            spans = group.find_elements(By.CSS_SELECTOR, "p span")
                            day_label = (
                                f"{spans[0].text.strip()} {spans[1].text.strip()}"
                                if len(spans) >= 2
                                else group.find_element(By.CSS_SELECTOR, "p").text.strip()
                            )
                            btns = group.find_elements(
                                By.CSS_SELECTOR,
                                "button[data-testid='btn-available-slot-default']",
                            )
                            times = [b.text.strip() for b in btns if b.text.strip()]
                            if times:
                                available.append(f"{day_label}: {', '.join(times)}")
                        except Exception:
                            continue
                else:
                    for btn in slot_btns:
                        txt = btn.text.strip()
                        if txt and txt not in available:
                            available.append(txt)
                return available

            # ── Fallback: generic enabled date/time buttons ────────────
            for sel in [
                "button[aria-label*='Available']:not([disabled])",
                "button.available:not([disabled])",
                "button[class*='available']:not([disabled])",
                "td[class*='available'] button:not([disabled])",
            ]:
                els = driver.find_elements(By.CSS_SELECTOR, sel)
                for el in els:
                    try:
                        if el.is_displayed() and el.is_enabled():
                            txt = (
                                el.text.strip()
                                or el.get_attribute("aria-label")
                                or el.get_attribute("title")
                                or ""
                            )
                            if txt and txt not in available:
                                available.append(txt)
                    except Exception:
                        continue
                if available:
                    break
        except Exception:
            pass
        return available


# Module-level singleton
visa_checker_sb = VisaCheckerSB()
