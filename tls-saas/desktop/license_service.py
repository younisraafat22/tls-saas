"""
License Service
Handles hardware-bound licensing, license management, and trial logic.
Also supports API-based subscription checking via the backend.
"""
import hashlib
import hmac
import json
import logging
import os
import ssl
import uuid
import platform
import subprocess
import time
import urllib.request
import urllib.error
from datetime import datetime, timedelta, timezone
from config import Config, BASE_DIR

logger = logging.getLogger("license")

# ---------- constants ----------
LICENSE_FILE = os.path.join(str(BASE_DIR), ".license")
SECRET = "TLS-CHECKER-2026-HMAC-SECRET-KEY-DONT-SHARE"

# Persistent trial marker (to prevent trial bypass by uninstall/reinstall)
TRIAL_REGISTRY_KEY = r"SOFTWARE\TLSAppointmentChecker"
TRIAL_REGISTRY_VALUE = "TrialActivated"
CHECKS_TODAY_REGISTRY_VALUE = "ChecksToday"  # "YYYY-MM-DD|count"


# ---------- SSL-safe URL helper (PyInstaller compat) ----------

def _get_ssl_context():
    """Return an SSL context that works reliably in PyInstaller bundles."""
    try:
        import certifi
        return ssl.create_default_context(cafile=certifi.where())
    except Exception:
        pass
    try:
        return ssl.create_default_context()
    except Exception:
        # Last resort — unverified (only for HTTP, but keeps things working)
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        return ctx


def _safe_urlopen(req, timeout=10):
    """urlopen wrapper with SSL context that works in PyInstaller bundles."""
    url = req.full_url if hasattr(req, 'full_url') else str(req)
    if url.startswith("https"):
        ctx = _get_ssl_context()
        return urllib.request.urlopen(req, timeout=timeout, context=ctx)
    return urllib.request.urlopen(req, timeout=timeout)

PLANS = {
    "trial": {
        "name": "Free Trial",
        "checks_per_day": 3,
        "min_interval": 60,        # 1 hour
        "duration_days": 1,
        "price": 0,
        "max_emails": 1,           # Trial: 1 email only
    },
    # Base plan keys (used by backend license generation)
    "legalization": {
        "name": "Legalization",
        "checks_per_day": 24,
        "min_interval": 60,
        "duration_days": 30,
        "price": 400,
        "currency": "EGP",
        "max_emails": 1,
    },
    "visa": {
        "name": "Visa",
        "checks_per_day": 24,
        "min_interval": 60,
        "duration_days": 30,
        "price": 400,
        "currency": "EGP",
        "max_emails": 1,
    },
    "legalization_monthly": {
        "name": "Legalization",
        "checks_per_day": 24,      # 24h / 60min
        "min_interval": 60,
        "duration_days": 30,
        "price": 400,
        "currency": "EGP",
        "max_emails": 1,
    },
    "legalization_quarterly": {
        "name": "Legalization (3 months)",
        "checks_per_day": 24,
        "min_interval": 60,
        "duration_days": 90,
        "price": 1200,
        "currency": "EGP",
        "max_emails": 1,
    },
    "visa_monthly": {
        "name": "Visa",
        "checks_per_day": 24,      # 24h / 60min
        "min_interval": 60,
        "duration_days": 30,
        "price": 400,
        "currency": "EGP",
        "max_emails": 1,
    },
    "visa_quarterly": {
        "name": "Visa (3 months)",
        "checks_per_day": 24,
        "min_interval": 60,
        "duration_days": 90,
        "price": 1200,
        "currency": "EGP",
        "max_emails": 1,
    },
    "premium": {
        "name": "Premium",
        "checks_per_day": 999999,
        "min_interval": 30,        # 30 minutes
        "duration_days": 30,
        "price": 2500,
        "currency": "EGP",
        "max_emails": 1,
    },
    "premium_monthly": {
        "name": "Premium (Monthly)",
        "checks_per_day": 999999,
        "min_interval": 30,
        "duration_days": 30,
        "price": 2500,
        "currency": "EGP",
        "max_emails": 1,
    },
    "premium_quarterly": {
        "name": "Premium (3 months)",
        "checks_per_day": 999999,
        "min_interval": 30,
        "duration_days": 90,
        "price": 6000,
        "currency": "EGP",
        "max_emails": 1,
    },
    "premium_annual": {
        "name": "Premium (Annual)",
        "checks_per_day": 999999,
        "min_interval": 30,
        "duration_days": 365,
        "price": 20000,
        "currency": "EGP",
        "max_emails": 1,
    },
    # Combo plan: both legalization + visa locally
    "all_in_one": {
        "name": "Legalization + Visa",
        "checks_per_day": 24,
        "min_interval": 60,
        "duration_days": 30,
        "price": 750,
        "currency": "EGP",
        "max_emails": 1,
    },
    "all_in_one_monthly": {
        "name": "Legalization + Visa",
        "checks_per_day": 24,
        "min_interval": 60,
        "duration_days": 30,
        "price": 750,
        "currency": "EGP",
        "max_emails": 1,
    },
    "all_in_one_quarterly": {
        "name": "Legalization + Visa (3 months)",
        "checks_per_day": 24,
        "min_interval": 60,
        "duration_days": 90,
        "price": 2400,
        "currency": "EGP",
        "max_emails": 1,
    },
    # Internal test plan — 2-hour expiry for verifying expiry logic without waiting 30 days
    "test_2h": {
        "name": "Test (2 Hours)",
        "checks_per_day": 24,
        "min_interval": 30,
        "duration_days": 0,
        "duration_hours": 2,
        "price": 0,
        "currency": "EGP",
        "max_emails": 1,
    },
}


# ---------- hardware fingerprint ----------

def _get_machine_id() -> str:
    """
    Build a stable fingerprint from hardware identifiers.
    Falls back gracefully on each platform.
    """
    parts = []

    # 1. MAC address (uuid.getnode)
    mac = uuid.getnode()
    parts.append(f"mac:{mac}")

    # 2. Machine name
    parts.append(f"host:{platform.node()}")

    # 3. Windows-specific: MachineGuid from registry
    if platform.system() == "Windows":
        try:
            import winreg
            reg = winreg.OpenKey(
                winreg.HKEY_LOCAL_MACHINE,
                r"SOFTWARE\Microsoft\Cryptography",
                0,
                winreg.KEY_READ | winreg.KEY_WOW64_64KEY,
            )
            val, _ = winreg.QueryValueEx(reg, "MachineGuid")
            winreg.CloseKey(reg)
            parts.append(f"wguid:{val}")
        except Exception:
            pass

    # 4. Linux: /etc/machine-id
    elif platform.system() == "Linux":
        try:
            with open("/etc/machine-id") as f:
                parts.append(f"mid:{f.read().strip()}")
        except Exception:
            pass

    raw = "|".join(parts)
    return hashlib.sha256(raw.encode()).hexdigest()[:32]


def get_hardware_id() -> str:
    """Public accessor — cached."""
    return _get_machine_id()


# ---------- persistent trial tracking (prevent reinstall bypass) ----------

def _check_trial_ever_activated() -> bool:
    """Check if trial was ever activated on this machine (via Windows Registry)."""
    if platform.system() != "Windows":
        return False
    
    try:
        import winreg
        try:
            key = winreg.OpenKey(
                winreg.HKEY_CURRENT_USER,
                TRIAL_REGISTRY_KEY,
                0,
                winreg.KEY_READ
            )
            hw_id = get_hardware_id()
            try:
                value, _ = winreg.QueryValueEx(key, TRIAL_REGISTRY_VALUE)
                winreg.CloseKey(key)
                # Value format: "hardware_id|timestamp"
                if value and hw_id in value:
                    return True
            except FileNotFoundError:
                winreg.CloseKey(key)
                return False
        except FileNotFoundError:
            return False
    except Exception:
        return False
    return False


def _mark_trial_activated():
    """Mark that trial has been activated on this machine (persist in Registry)."""
    if platform.system() != "Windows":
        return
    
    try:
        import winreg
        hw_id = get_hardware_id()
        timestamp = datetime.now(timezone.utc).isoformat()
        value = f"{hw_id}|{timestamp}"
        
        try:
            key = winreg.CreateKeyEx(
                winreg.HKEY_CURRENT_USER,
                TRIAL_REGISTRY_KEY,
                0,
                winreg.KEY_WRITE
            )
            winreg.SetValueEx(key, TRIAL_REGISTRY_VALUE, 0, winreg.REG_SZ, value)
            winreg.CloseKey(key)
        except Exception:
            pass # Silently fail if can't write to registry
    except Exception:
        pass


def _get_registry_checks_today() -> tuple[str, int]:
    """Read ChecksToday from Registry. Returns (date_str, count) or ("", 0) on failure."""
    if platform.system() != "Windows":
        return "", 0
    try:
        import winreg
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, TRIAL_REGISTRY_KEY, 0, winreg.KEY_READ)
        try:
            value, _ = winreg.QueryValueEx(key, CHECKS_TODAY_REGISTRY_VALUE)
            winreg.CloseKey(key)
            parts = value.split("|", 1)
            if len(parts) == 2:
                return parts[0], int(parts[1])
        except (FileNotFoundError, ValueError):
            winreg.CloseKey(key)
    except Exception:
        pass
    return "", 0


def _set_registry_checks_today(date_str: str, count: int):
    """Write ChecksToday to Registry as 'YYYY-MM-DD|count'."""
    if platform.system() != "Windows":
        return
    try:
        import winreg
        key = winreg.CreateKeyEx(winreg.HKEY_CURRENT_USER, TRIAL_REGISTRY_KEY, 0, winreg.KEY_WRITE)
        winreg.SetValueEx(key, CHECKS_TODAY_REGISTRY_VALUE, 0, winreg.REG_SZ, f"{date_str}|{count}")
        winreg.CloseKey(key)
    except Exception:
        pass

def _sign(payload: str) -> str:
    """HMAC-SHA256 signature of payload."""
    return hmac.new(SECRET.encode(), payload.encode(), hashlib.sha256).hexdigest()[:16]


def generate_license_key(plan: str, hardware_id: str) -> str:
    """
    Generate a license key bound to a specific hardware ID.
    Format: PLAN-HWID8-RANDOM8-SIG16
    Run this on YOUR machine (generate_license.py) and give the key to the buyer.
    """
    import secrets
    hw_short = hardware_id[:8].upper()
    rand = secrets.token_hex(4).upper()
    payload = f"{plan}:{hw_short}:{rand}"
    sig = _sign(payload).upper()
    return f"{plan.upper()}-{hw_short}-{rand}-{sig}"


def parse_license_key(key: str) -> dict | None:
    """
    Parse and validate a license key.
    Returns dict with plan, hw_prefix, random, signature or None if invalid.
    """
    parts = key.strip().upper().split("-")
    # Handle plan names with underscores (BASIC_MONTHLY -> parts[0] + parts[1])
    # Format: PLAN_TYPE-HWID8-RANDOM8-SIG16  or  PLAN-HWID8-RANDOM8-SIG16
    # We need to reconstruct — try different splits
    
    if len(parts) == 4:
        plan_raw, hw, rand, sig = parts
    elif len(parts) == 5:
        plan_raw = f"{parts[0]}_{parts[1]}"
        hw, rand, sig = parts[2], parts[3], parts[4]
    else:
        return None

    plan = plan_raw.lower()
    if plan not in PLANS:
        return None

    # Verify signature
    payload = f"{plan}:{hw}:{rand}"
    expected_sig = _sign(payload).upper()
    if not hmac.compare_digest(sig, expected_sig):
        return None

    return {"plan": plan, "hw_prefix": hw, "random": rand, "signature": sig, "raw_key": key.strip().upper()}


# ---------- local license file ----------

def _read_license_file() -> dict | None:
    """Read the local encrypted license file."""
    if not os.path.exists(LICENSE_FILE):
        return None
    try:
        with open(LICENSE_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        # Verify integrity
        stored_sig = data.get("integrity")
        check_str = f"{data.get('key')}:{data.get('hardware_id')}:{data.get('plan')}:{data.get('activated_at')}:{data.get('expires_at')}"
        if _sign(check_str) != stored_sig:
            return None
        return data
    except Exception:
        return None


def _write_license_file(data: dict):
    """Write the local license file with integrity signature."""
    check_str = f"{data['key']}:{data['hardware_id']}:{data['plan']}:{data['activated_at']}:{data['expires_at']}"
    data["integrity"] = _sign(check_str)
    with open(LICENSE_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f)


# ---------- public API ----------

def update_license_branch(branch_name: str, branch_url: str, service_type: str = None):
    """Update the branch/service_type fields in the local license file.
    Called by the background thread in the UI after a successful server fetch,
    so the offline step is correct on the next app launch.
    """
    data = _read_license_file()
    if not data:
        return
    changed = False
    if data.get("branch_name") != branch_name:
        data["branch_name"] = branch_name
        changed = True
    if data.get("branch_url") != branch_url:
        data["branch_url"] = branch_url
        changed = True
    if service_type and data.get("service_type") != service_type:
        data["service_type"] = service_type
        changed = True
    if changed:
        _write_license_file(data)


def activate_license(key: str) -> tuple[bool, str]:
    """
    Activate a license key on this device.
    Returns (success, message).
    """
    hw_id = get_hardware_id()
    parsed = parse_license_key(key)
    if not parsed:
        return False, "Invalid license key. Please check and try again."

    # Check hardware prefix
    hw_prefix = hw_id[:8].upper()
    # Allow PENDING0 prefix (universal license purchased from website)
    if parsed["hw_prefix"] != hw_prefix and parsed["hw_prefix"] != "PENDING0":
        return False, f"This license key is for a different device.\nYour Device ID: {hw_prefix}\nKey Device ID: {parsed['hw_prefix']}"

    plan = parsed["plan"]
    plan_info = PLANS[plan]
    now = datetime.now(timezone.utc)
    if plan_info.get("duration_hours"):
        expires = now + timedelta(hours=plan_info["duration_hours"])
    else:
        expires = now + timedelta(days=plan_info["duration_days"])

    license_data = {
        "key": key.upper(),
        "hardware_id": hw_id,
        "plan": plan,
        "activated_at": now.isoformat(),
        "expires_at": expires.isoformat(),
        "checks_today": 0,
        "checks_reset_date": now.date().isoformat(),
    }

    # Fetch branch info from backend (if available)
    # Use _safe_urlopen for reliable SSL handling in PyInstaller bundles.
    server_url = (Config.LICENSE_SERVER_URL or Config.BACKEND_URL or "").rstrip("/")
    if server_url:
        for _attempt in range(3):
            try:
                _url = (f"{server_url}/api/payments/license-branch"
                        f"?license_key={key.strip().upper()}")
                _req = urllib.request.Request(_url, headers={"Accept": "application/json"}, method="GET")
                with _safe_urlopen(_req, timeout=10) as _resp:
                    branch_data = json.loads(_resp.read())
                if branch_data.get("branch_name"):
                    license_data["branch_name"] = branch_data["branch_name"]
                    license_data["branch_url"] = branch_data["branch_url"]
                    license_data["service_type"] = branch_data["service_type"]
                    logger.info(f"[LICENSE] Branch fetched: {branch_data['branch_name']}")
                break  # success
            except Exception as exc:
                logger.warning(f"[LICENSE] Branch fetch attempt {_attempt+1}/3 failed: {exc}")
                if _attempt < 2:
                    time.sleep(1)

    _write_license_file(license_data)
    return True, f"License activated! Type: {plan_info['name']}"


def activate_trial() -> tuple[bool, str]:
    """
    Activate a free 1-day trial.
    Only works if no license has ever been activated on this device.
    Uses persistent registry marker to prevent bypass by uninstall/reinstall.
    """
    # First check registry marker (prevents reinstall bypass)
    if _check_trial_ever_activated():
        return False, "Trial has already been used on this device. Please purchase a license to continue."
    
    existing = _read_license_file()
    if existing:
        # If already has a license (even expired), don't allow another trial
        if existing.get("plan") == "trial":
            expires = datetime.fromisoformat(existing["expires_at"])
            # Ensure timezone-aware for comparison (handle legacy naive datetimes)
            if expires.tzinfo is None:
                expires = expires.replace(tzinfo=timezone.utc)
            if datetime.now(timezone.utc) < expires:
                return True, "Trial is still active."
            else:
                return False, "Your free trial has expired. Please purchase a license to continue."
        else:
            # Has a paid license
            return False, "You already have a license."

    hw_id = get_hardware_id()
    now = datetime.now(timezone.utc)
    trial_info = PLANS["trial"]
    expires = now + timedelta(days=trial_info["duration_days"])

    license_data = {
        "key": "TRIAL",
        "hardware_id": hw_id,
        "plan": "trial",
        "activated_at": now.isoformat(),
        "expires_at": expires.isoformat(),
        "checks_today": 0,
        "checks_reset_date": now.date().isoformat(),
    }
    _write_license_file(license_data)
    
    # Mark trial as activated in persistent storage (Registry)
    _mark_trial_activated()
    
    return True, f"Trial activated! Expires in {trial_info['duration_days']} day(s)."


# ── Revocation check cache (in-memory, per session) ──────────────────────────
# Avoids blocking the UI on every get_license_status() call.
# Format: {"time": float | None, "not_revoked": bool}
_revoke_cache: dict = {"time": None, "not_revoked": True}
_REVOKE_CACHE_TTL = 3600  # 1 hour

# Stable URL to discover the current backend URL (survives tunnel restarts)
_VERCEL_URL = "https://tls-saas.vercel.app"
_BACKEND_URL_CACHE: dict = {"time": None, "url": None}
_BACKEND_URL_TTL = 3600  # 1 hour


def _fetch_current_backend_url() -> str | None:
    """
    Fetch the current backend URL from the stable Vercel deployment.
    The Vercel app always knows which tunnel is active via NEXT_PUBLIC_API_URL.
    Returns the URL string, or None on failure.  Results are cached for 1 hour.
    """
    now = time.time()
    if (_BACKEND_URL_CACHE["time"] is not None
            and now - _BACKEND_URL_CACHE["time"] < _BACKEND_URL_TTL
            and _BACKEND_URL_CACHE["url"]):
        return _BACKEND_URL_CACHE["url"]
    try:
        req = urllib.request.Request(
            f"{_VERCEL_URL}/api/backend-url",
            headers={"Accept": "application/json"},
            method="GET",
        )
        with _safe_urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read())
            url = (data.get("url") or "").rstrip("/")
            if url:
                _BACKEND_URL_CACHE["time"] = now
                _BACKEND_URL_CACHE["url"] = url
                return url
    except Exception as exc:
        logger.debug(f"[LICENSE] Failed to fetch backend URL from Vercel: {exc}")
    return None


def get_license_status() -> dict | None:
    """
    Get current license status.
    Returns dict with plan info or None if no valid license.
    """
    data = _read_license_file()
    if not data:
        return None

    # Check hardware match
    hw_id = get_hardware_id()
    if data.get("hardware_id") != hw_id:
        return None

    # Check expiry
    expires = datetime.fromisoformat(data["expires_at"])
    # Ensure timezone-aware for comparison (handle legacy naive datetimes)
    if expires.tzinfo is None:
        expires = expires.replace(tzinfo=timezone.utc)
    if datetime.now(timezone.utc) > expires:
        return {
            "valid": False,
            "expired": True,
            "plan": data["plan"],
            "plan_info": PLANS.get(data["plan"], PLANS["trial"]),
            "expires_at": expires,
            "message": "License expired",
        }

    # Server-side revocation check (best-effort, cached per session)
    # Only check for non-trial licenses to reduce server load.
    if data["plan"] != "trial" and data.get("key"):
        now_ts = time.time()
        cache_valid = (
            _revoke_cache["time"] is not None
            and now_ts - _revoke_cache["time"] < _REVOKE_CACHE_TTL
        )
        if cache_valid and not _revoke_cache["not_revoked"]:
            # Cached as revoked — enforce it
            logger.info("[LICENSE] Revoked (cached) — removing local license")
            if os.path.exists(LICENSE_FILE):
                os.remove(LICENSE_FILE)
            return None

        if not cache_valid:
            # Build list of URLs to try: Vercel-discovered URL first, then hardcoded fallbacks
            urls_to_try = []
            discovered = _fetch_current_backend_url()
            if discovered:
                urls_to_try.append(discovered)
            server_url = (Config.LICENSE_SERVER_URL or "").rstrip("/")
            if server_url and server_url not in urls_to_try:
                urls_to_try.append(server_url)
            backend_url = (Config.BACKEND_URL or "").rstrip("/")
            if backend_url and backend_url not in urls_to_try:
                urls_to_try.append(backend_url)

            revoked = False
            check_done = False
            for try_url in urls_to_try:
                for _attempt in range(2):
                    try:
                        payload = json.dumps({"license_key": data["key"]}).encode()
                        req = urllib.request.Request(
                            f"{try_url}/api/monitoring/license/verify",
                            data=payload,
                            headers={"Content-Type": "application/json"},
                            method="POST",
                        )
                        with _safe_urlopen(req, timeout=5) as resp:
                            result = json.loads(resp.read())
                            if result.get("found") and not result.get("is_active", True):
                                revoked = True
                            else:
                                logger.debug(f"[LICENSE] Server verify OK: is_active={result.get('is_active')}")
                        check_done = True
                        break  # success — stop retrying this URL
                    except Exception as exc:
                        logger.warning(f"[LICENSE] Revocation check attempt {_attempt+1}/2 failed ({try_url}): {exc}")
                        if _attempt < 1:
                            time.sleep(1)
                if check_done:
                    break  # stop trying other URLs

            if check_done:
                _revoke_cache["time"] = now_ts
                _revoke_cache["not_revoked"] = not revoked

            if revoked:
                logger.info("[LICENSE] Revoked by server — removing local license")
                if os.path.exists(LICENSE_FILE):
                    os.remove(LICENSE_FILE)
                return None

    plan = data["plan"]
    plan_info = PLANS.get(plan, PLANS["trial"])

    # Daily check counter
    checks_today = data.get("checks_today", 0)
    reset_date = data.get("checks_reset_date", "")
    today = datetime.now(timezone.utc).date().isoformat()
    if reset_date != today:
        checks_today = 0

    # Harden against .license deletion: compare with Registry (use whichever is higher)
    reg_date, reg_count = _get_registry_checks_today()
    if reg_date == today and reg_count > checks_today:
        checks_today = reg_count

    return {
        "valid": True,
        "expired": False,
        "plan": plan,
        "plan_info": plan_info,
        "expires_at": expires,
        "days_remaining": (expires - datetime.now(timezone.utc)).days,
        "checks_today": checks_today,
        "checks_limit": plan_info["checks_per_day"],
        "min_interval": plan_info["min_interval"],
        "key": data.get("key", ""),
        "branch_name": data.get("branch_name"),
        "branch_url": data.get("branch_url"),
        "service_type": data.get("service_type"),
        "message": f"License: {plan_info['name']}",
    }


def can_check() -> tuple[bool, str]:
    """Check if user can perform a check right now."""
    status = get_license_status()
    if not status:
        return False, "No license found. Please activate a license."
    if not status["valid"]:
        return False, "License expired. Please renew."
    if status["checks_today"] >= status["checks_limit"]:
        return False, f"Daily check limit reached ({status['checks_limit']}). Upgrade for more."
    return True, ""


def increment_check_count():
    """Increment today's check counter."""
    data = _read_license_file()
    if not data:
        return
    today = datetime.now(timezone.utc).date().isoformat()
    if data.get("checks_reset_date") != today:
        data["checks_today"] = 1
        data["checks_reset_date"] = today
    else:
        data["checks_today"] = data.get("checks_today", 0) + 1
    _write_license_file(data)
    # Also persist to Registry so deleting .license can't reset the counter
    _set_registry_checks_today(today, data["checks_today"])


def deactivate_license():
    """Remove local license and notify server to deactivate it."""
    # Read current license data before removing
    data = _read_license_file()
    
    # Remove local file
    if os.path.exists(LICENSE_FILE):
        os.remove(LICENSE_FILE)
    
    # Also deactivate on server if we have the key and hardware_id
    if data and data.get("key"):
        server_url = (Config.LICENSE_SERVER_URL or "").rstrip("/")
        if server_url:
            try:
                hw_id = get_hardware_id()
                payload = json.dumps({
                    "license_key": data["key"],
                    "hardware_id": hw_id,
                }).encode()
                req = urllib.request.Request(
                    f"{server_url}/api/monitoring/license/deactivate",
                    data=payload,
                    headers={"Content-Type": "application/json"},
                    method="POST",
                )
                with _safe_urlopen(req, timeout=10) as resp:
                    result = json.loads(resp.read())
                    logger.info(f"[LICENSE] Server deactivation result: {result}")
            except Exception as e:
                logger.warning(f"[LICENSE] Server deactivation failed: {e}")


def can_change_email(new_email: str) -> tuple[bool, str]:
    """
    Check if user can change their notification email.
    Returns (allowed, message)
    """
    status = get_license_status()
    if not status or not status.get("valid"):
        return False, "No active license"
    
    plan_info = status.get("plan_info", {})
    max_emails = plan_info.get("max_emails", 1)
    
    # Get current email change count from database
    from database import SessionLocal, UserSettings
    db = SessionLocal()
    try:
        settings = db.query(UserSettings).filter(UserSettings.user_id == 1).first()
        if not settings:
            return True, "First email setup allowed"
        
        current_count = settings.email_change_count or 0
        
        # Check if same email (no increment needed)
        if settings.notification_email and settings.notification_email.lower() == new_email.lower():
            return True, "Same email, no change needed"
        
        # Check if limit reached
        if current_count >= max_emails:
            return False, f"Email change limit reached. Maximum {max_emails} email(s) allowed per device."
        
        return True, f"Email change allowed ({current_count + 1}/{max_emails})"
    finally:
        db.close()


def record_email_change(old_email: str, new_email: str):
    """Record notification email change in database."""
    from database import SessionLocal, UserSettings
    import json
    
    db = SessionLocal()
    try:
        settings = db.query(UserSettings).filter(UserSettings.user_id == 1).first()
        if settings:
            # Update count
            settings.email_change_count = (settings.email_change_count or 0) + 1
            
            # Update history
            try:
                history = json.loads(settings.email_history or "[]")
            except:
                history = []
            
            history.append({
                "old_email": old_email,
                "new_email": new_email,
                "timestamp": datetime.now(timezone.utc).isoformat()
            })
            settings.email_history = json.dumps(history)
            
            db.commit()
    finally:
        db.close()


def can_change_tls_email(new_email: str) -> tuple[bool, str]:
    """
    Check if user can change their TLS credential email.
    Trial: 1 email allowed, Lifetime: 2 emails allowed.
    Returns (allowed, message)
    """
    status = get_license_status()
    if not status or not status.get("valid"):
        return False, "No active license"
    
    plan_info = status.get("plan_info", {})
    max_emails = plan_info.get("max_emails", 1)
    
    from database import SessionLocal, UserSettings
    db = SessionLocal()
    try:
        settings = db.query(UserSettings).filter(UserSettings.user_id == 1).first()
        if not settings:
            return True, "First TLS email setup allowed"
        
        current_count = settings.tls_email_change_count or 0
        
        # Check if same email (no increment needed)
        if settings.tls_email and settings.tls_email.lower() == new_email.lower():
            return True, "Same TLS email, no change needed"
        
        # Check if limit reached
        if current_count >= max_emails:
            return False, f"TLS email change limit reached. Maximum {max_emails} TLS credential email(s) allowed per device."
        
        return True, f"TLS email change allowed ({current_count + 1}/{max_emails})"
    finally:
        db.close()


def record_tls_email_change(old_email: str, new_email: str):
    """Record TLS credential email change in database."""
    from database import SessionLocal, UserSettings
    import json
    
    db = SessionLocal()
    try:
        settings = db.query(UserSettings).filter(UserSettings.user_id == 1).first()
        if settings:
            settings.tls_email_change_count = (settings.tls_email_change_count or 0) + 1
            
            try:
                history = json.loads(settings.tls_email_history or "[]")
            except:
                history = []
            
            history.append({
                "old_email": old_email,
                "new_email": new_email,
                "timestamp": datetime.now(timezone.utc).isoformat()
            })
            settings.tls_email_history = json.dumps(history)
            
            db.commit()
    finally:
        db.close()


# =====================================================================
#  API-BASED SUBSCRIPTION CHECK (primary auth — uses backend server)
# =====================================================================

def check_api_subscription() -> dict | None:
    """
    Check subscription status via the backend API.
    Returns a dict compatible with get_license_status() format, or None if not logged in / no sub.
    """
    try:
        from api_client import api_client
        if not api_client.is_logged_in:
            return None

        # Refresh user info from server
        user = api_client.get_me()
        if not user:
            return None

        active_plan = user.get("active_plan")
        sub_expires = user.get("subscription_expires")

        if not active_plan:
            return {
                "valid": False,
                "expired": False,
                "plan": None,
                "plan_info": {"name": "No subscription", "checks_per_day": 0, "min_interval": 60},
                "expires_at": None,
                "message": "No active subscription. Subscribe at the website.",
                "source": "api",
                "user": user,
            }

        # Parse expiry
        expires_at = None
        days_remaining = 0
        if sub_expires:
            if isinstance(sub_expires, str):
                expires_at = datetime.fromisoformat(sub_expires.replace("Z", "+00:00"))
            else:
                expires_at = sub_expires
            if expires_at.tzinfo is None:
                expires_at = expires_at.replace(tzinfo=timezone.utc)
            days_remaining = (expires_at - datetime.now(timezone.utc)).days

        # Map plan name to plan type
        plan_type = "legalization"
        if active_plan and "visa" in active_plan.lower():
            plan_type = "visa"

        return {
            "valid": True,
            "expired": False,
            "plan": plan_type,
            "plan_info": {
                "name": active_plan,
                "checks_per_day": 999999,
                "min_interval": 30,
                "max_emails": 1,
            },
            "expires_at": expires_at,
            "days_remaining": days_remaining,
            "checks_today": 0,
            "checks_limit": 999999,
            "min_interval": 30,
            "key": "API_SUBSCRIPTION",
            "message": f"Subscription: {active_plan}",
            "source": "api",
            "user": user,
        }
    except Exception as e:
        print(f"[LICENSE] API subscription check failed: {e}")
        return None


def get_combined_license_status() -> dict | None:
    """
    Check both API subscription and offline license.
    API takes priority; falls back to offline license if API is unavailable.
    """
    # Try API first
    api_status = check_api_subscription()
    if api_status and api_status.get("valid"):
        return api_status

    # Fall back to offline license
    offline_status = get_license_status()
    if offline_status:
        offline_status["source"] = "offline"
        return offline_status

    # If API returned an expired/no-sub result, return that
    if api_status:
        return api_status

    return None
