"""
TLS Visa Checker — SeleniumBase UC (Undetected Chrome) mode.

The TLS Visa site (visas-de.tlscontact.com) uses strict Cloudflare/Turnstile
protection that causes Patchright to time out on page load. SeleniumBase with
uc=True (undetected-chrome) bypasses this natively.

Called by TLSChecker.check_branch() when service_type == "visa".
"""

import logging
import random
import re
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

            log("Opening TLS Visa website (SeleniumBase UC mode)...")
            driver = Driver(
                uc=True,
                headless=settings.BROWSER_HEADLESS,
                no_sandbox=True,
                disable_gpu=True,
            )
            driver.set_page_load_timeout(90)
            driver.implicitly_wait(3)

            # Navigate — UC mode handles Cloudflare challenge automatically
            driver.get(branch_url)
            _wait(3, 5)

            # Wait for Cloudflare to clear
            self._wait_cloudflare(driver, log)

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

    def _wait_cloudflare(self, driver, log, max_wait: int = 90):
        """Wait for Cloudflare challenge / Turnstile to pass."""
        start = time.time()
        cf_indicators = [
            "just a moment", "checking your browser",
            "cf-browser-verification", "challenge-platform",
            "turnstile", "cloudflare",
        ]
        while time.time() - start < max_wait:
            body = driver.page_source.lower()
            if any(ind in body for ind in cf_indicators):
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
        # TLS-specific selectors
        for sel in [
            "span.TlsButton_tls-button__syUS5",
            "[class*='TlsButton'][class*='--outline']",
            "a.tls-button-link",
        ]:
            try:
                els = driver.find_elements(By.CSS_SELECTOR, sel)
                for el in els:
                    if el.text.strip().upper() == "LOGIN" and el.is_displayed():
                        el.click()
                        log("Clicked LOGIN button")
                        return True
            except Exception:
                continue

        # Scan by text
        for tag in ["a", "button", "span"]:
            try:
                for el in driver.find_elements(By.TAG_NAME, tag):
                    if el.text.strip().upper() in ("LOGIN", "LOG IN") and el.is_displayed():
                        el.click()
                        log("Clicked LOGIN button (text scan)")
                        return True
            except Exception:
                continue

        # Wait up to 20s for delayed button
        log("LOGIN button not found yet, waiting...")
        try:
            btn = WebDriverWait(driver, 20).until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, "span.TlsButton_tls-button__syUS5"))
            )
            if btn.text.strip().upper() == "LOGIN":
                btn.click()
                log("Clicked LOGIN button (after wait)")
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
        """Click Select → Continue to reach the appointment calendar."""
        try:
            self._accept_cookies(driver)
            time.sleep(2)

            body = driver.page_source.lower()
            if "click on the button to create a new application" in body:
                log("No TLS application found — user must create one first", "error")
                return False

            # Extract location keywords from URL for multi-app selection
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

            # Find Select button
            log("Looking for Select button...")
            select_el = None

            # Multiple app cards?
            try:
                all_btns = driver.find_elements(By.CSS_SELECTOR, "button[name='formGroupId']")
                if len(all_btns) > 1 and location_keywords:
                    for btn in all_btns:
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
                    if not select_el and all_btns:
                        select_el = all_btns[0]
                elif len(all_btns) == 1:
                    select_el = all_btns[0]
            except Exception:
                pass

            if not select_el:
                for css in ["button[name='formGroupId']", "button.tls-button-primary"]:
                    try:
                        el = WebDriverWait(driver, 8).until(
                            EC.element_to_be_clickable((By.CSS_SELECTOR, css))
                        )
                        if el.is_displayed():
                            select_el = el
                            break
                    except Exception:
                        continue

            if not select_el:
                for el in driver.find_elements(By.TAG_NAME, "button"):
                    if el.text.strip().upper() == "SELECT" and el.is_displayed():
                        select_el = el
                        break

            if not select_el:
                log("Select button not found", "error")
                return False

            driver.execute_script("arguments[0].scrollIntoView(true);", select_el)
            _wait(0.5, 1)
            select_el.click()
            log("Clicked Select")
            _wait(2, 3)

            # Find Continue button
            log("Looking for Continue button...")
            continue_el = None

            for _ in range(3):
                for sel in ["button[type='submit']", "button.tls-button-primary", "button[class*='tls-button-primary']"]:
                    try:
                        els = driver.find_elements(By.CSS_SELECTOR, sel)
                        for el in els:
                            if el.is_displayed() and el.text.strip().upper() in ("CONTINUE", "CONFIRM", "NEXT", "PROCEED"):
                                continue_el = el
                                break
                        if continue_el:
                            break
                    except Exception:
                        continue

                if not continue_el:
                    for el in driver.find_elements(By.TAG_NAME, "button"):
                        if el.text.strip().upper() in ("CONTINUE", "CONFIRM", "NEXT") and el.is_displayed():
                            continue_el = el
                            break

                if continue_el:
                    break
                time.sleep(2)

            if not continue_el:
                log("Continue button not found", "error")
                return False

            driver.execute_script("arguments[0].scrollIntoView(true);", continue_el)
            _wait(0.5, 1)
            continue_el.click()
            log("Clicked Continue")
            _wait(3, 5)

            # Verify we reached booking page
            for _ in range(10):
                url = driver.current_url.lower()
                body_lc = driver.page_source.lower()
                if any(k in url for k in ("appointment-booking", "appointment", "booking", "workflow")):
                    log("Appointment page loaded")
                    return True
                if "calendar" in body_lc or "month" in body_lc:
                    log("Appointment page loaded (calendar detected)")
                    return True
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
        """Return True if the page clearly says no appointments available."""
        no_slot_phrases = [
            "don't have any appointment", "no slots available",
            "no appointment slots", "not available",
        ]
        try:
            body = driver.page_source.lower()
            if any(p in body for p in no_slot_phrases):
                return True
            for sel in ["p.text-lg.font-semibold", ".text-center p.font-semibold",
                        "p.font-semibold.text-on-surface-variant"]:
                for el in driver.find_elements(By.CSS_SELECTOR, sel):
                    if el.is_displayed() and any(p in el.text.lower() for p in no_slot_phrases):
                        return True
        except Exception:
            pass
        return False

    def _get_months(self, driver) -> list[tuple[str, str]]:
        """Extract available month navigation links from the page."""
        months: list[tuple[str, str]] = []
        try:
            for sel in [
                "a[href*='appointment-booking']",
                "a[href*='month=']",
                "li[class*='month'] a",
                "nav a[href*='booking']",
            ]:
                els = driver.find_elements(By.CSS_SELECTOR, sel)
                for el in els:
                    try:
                        href = el.get_attribute("href") or ""
                        text = el.text.strip()
                        if href and text and (href, text) not in months:
                            months.append((text, href))
                    except Exception:
                        continue
                if months:
                    break
        except Exception:
            pass
        return months

    def _find_available_dates(self, driver) -> list[str]:
        """Find enabled (available) date buttons in the appointment calendar."""
        available: list[str] = []
        try:
            for sel in [
                "button.available:not([disabled])",
                "button[class*='available']:not([disabled])",
                "td[class*='available'] button:not([disabled])",
                "td.available:not(.disabled)",
                "button[aria-label*='Available']",
                ".calendar-day:not(.disabled):not(.empty) button:not([disabled])",
                "button[class*='CalendarDay']:not([disabled]):not([class*='Blocked'])",
            ]:
                els = driver.find_elements(By.CSS_SELECTOR, sel)
                for el in els:
                    try:
                        if el.is_displayed() and el.is_enabled():
                            txt = (el.text.strip() or
                                   el.get_attribute("aria-label") or
                                   el.get_attribute("title") or "")
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
