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
import threading
import time
import urllib.request
import urllib.error
import urllib.parse
from datetime import datetime, timedelta, timezone
from config import Config, BASE_DIR

logger = logging.getLogger("license")

# ---------- constants ----------
LICENSE_FILE = os.path.join(str(BASE_DIR), ".license")
DEV_EXPIRY_OVERRIDE_FILE = os.path.join(str(BASE_DIR), ".dev_license_expiry_override")
DEVICE_ID_FILE = os.path.join(str(BASE_DIR), ".device_id")

# Persistent trial marker (to prevent trial bypass by uninstall/reinstall)
TRIAL_REGISTRY_KEY = r"SOFTWARE\TLSAppointmentChecker"

TRIAL_REGISTRY_VALUE = "TrialActivated"
CHECKS_TODAY_REGISTRY_VALUE = "ChecksToday"  # "YYYY-MM-DD|count"
STABLE_HWID_REGISTRY_VALUE = "StableHardwareId"

_CACHED_HARDWARE_ID: str | None = None


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
        "price": 300,
        "currency": "EGP",
        "max_emails": 2,
    },
    "visa": {
        "name": "Visa",
        "checks_per_day": 24,
        "min_interval": 60,
        "duration_days": 30,
        "price": 300,
        "currency": "EGP",
        "max_emails": 2,
    },
    "legalization_monthly": {
        "name": "Legalization",
        "checks_per_day": 24,      # 24h / 60min
        "min_interval": 60,
        "duration_days": 30,
        "price": 300,
        "currency": "EGP",
        "max_emails": 2,
    },
    "legalization_quarterly": {
        "name": "Legalization (3 months)",
        "checks_per_day": 24,
        "min_interval": 60,
        "duration_days": 90,
        "price": 900,
        "currency": "EGP",
        "max_emails": 2,
    },
    "visa_monthly": {
        "name": "Visa",
        "checks_per_day": 24,      # 24h / 60min
        "min_interval": 60,
        "duration_days": 30,
        "price": 300,
        "currency": "EGP",
        "max_emails": 2,
    },
    "visa_quarterly": {
        "name": "Visa (3 months)",
        "checks_per_day": 24,
        "min_interval": 60,
        "duration_days": 90,
        "price": 900,
        "currency": "EGP",
        "max_emails": 2,
    },
    "premium": {
        "name": "Premium",
        "checks_per_day": 999999,
        "min_interval": 30,        # 30 minutes
        "duration_days": 30,
        "price": 2500,
        "currency": "EGP",
        "max_emails": 2,
    },
    "premium_monthly": {
        "name": "Premium (Monthly)",
        "checks_per_day": 999999,
        "min_interval": 30,
        "duration_days": 30,
        "price": 2500,
        "currency": "EGP",
        "max_emails": 2,
    },
    "premium_quarterly": {
        "name": "Premium (3 months)",
        "checks_per_day": 999999,
        "min_interval": 30,
        "duration_days": 90,
        "price": 6000,
        "currency": "EGP",
        "max_emails": 2,
    },
    "premium_annual": {
        "name": "Premium (Annual)",
        "checks_per_day": 999999,
        "min_interval": 30,
        "duration_days": 365,
        "price": 20000,
        "currency": "EGP",
        "max_emails": 2,
    },
    # Combo plan: both legalization + visa locally
    "all_in_one": {
        "name": "Legalization + Visa",
        "checks_per_day": 24,
        "min_interval": 60,
        "duration_days": 30,
        "price": 500,
        "currency": "EGP",
        "max_emails": 2,
    },
    "all_in_one_monthly": {
        "name": "Legalization + Visa",
        "checks_per_day": 24,
        "min_interval": 60,
        "duration_days": 30,
        "price": 500,
        "currency": "EGP",
        "max_emails": 2,
    },
    "all_in_one_quarterly": {
        "name": "Legalization + Visa (3 months)",
        "checks_per_day": 24,
        "min_interval": 60,
        "duration_days": 90,
        "price": 1500,
        "currency": "EGP",
        "max_emails": 2,
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
        "max_emails": 2,
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


def _is_valid_hardware_id(value: str) -> bool:
    if not isinstance(value, str):
        return False
    value = value.strip().lower()
    if len(value) != 32:
        return False
    return all(ch in "0123456789abcdef" for ch in value)


def _read_license_hardware_id_raw() -> str | None:
    """Read only hardware_id from local license JSON without integrity checks."""
    if not os.path.exists(LICENSE_FILE):
        return None
    try:
        with open(LICENSE_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        hw_id = (data.get("hardware_id") or "").strip().lower()
        if _is_valid_hardware_id(hw_id):
            return hw_id
    except Exception:
        return None
    return None


def _read_persisted_hardware_id() -> str | None:
    """Read stable hardware id from registry (Windows) or local file."""
    if platform.system() == "Windows":
        try:
            import winreg
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, TRIAL_REGISTRY_KEY, 0, winreg.KEY_READ)
            try:
                value, _ = winreg.QueryValueEx(key, STABLE_HWID_REGISTRY_VALUE)
                winreg.CloseKey(key)
                value = (value or "").strip().lower()
                if _is_valid_hardware_id(value):
                    return value
            except FileNotFoundError:
                winreg.CloseKey(key)
            except Exception:
                winreg.CloseKey(key)
        except Exception:
            pass

    if os.path.exists(DEVICE_ID_FILE):
        try:
            with open(DEVICE_ID_FILE, "r", encoding="utf-8") as f:
                value = f.read().strip().lower()
            if _is_valid_hardware_id(value):
                return value
        except Exception:
            pass

    return None


def _persist_hardware_id(hw_id: str):
    """Persist stable hardware id best-effort to registry/file for future runs."""
    if not _is_valid_hardware_id(hw_id):
        return

    if platform.system() == "Windows":
        try:
            import winreg
            key = winreg.CreateKeyEx(winreg.HKEY_CURRENT_USER, TRIAL_REGISTRY_KEY, 0, winreg.KEY_WRITE)
            winreg.SetValueEx(key, STABLE_HWID_REGISTRY_VALUE, 0, winreg.REG_SZ, hw_id)
            winreg.CloseKey(key)
        except Exception:
            pass

    try:
        with open(DEVICE_ID_FILE, "w", encoding="utf-8") as f:
            f.write(hw_id)
    except Exception:
        pass


def get_hardware_id() -> str:
    """Return a stable device id that survives adapter/order changes and reboots."""
    global _CACHED_HARDWARE_ID
    if _CACHED_HARDWARE_ID:
        return _CACHED_HARDWARE_ID

    persisted = _read_persisted_hardware_id()
    if persisted:
        _CACHED_HARDWARE_ID = persisted
        return persisted

    # Backward compatibility: keep the id from an already-activated local license.
    existing = _read_license_hardware_id_raw()
    if existing:
        _persist_hardware_id(existing)
        _CACHED_HARDWARE_ID = existing
        return existing

    computed = _get_machine_id().lower()
    _persist_hardware_id(computed)
    _CACHED_HARDWARE_ID = computed
    return computed


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

def _get_local_integrity_key() -> str:
    """Generate a hardware-bound key for local file tampering prevention."""
    raw = f"local-tamper-{get_hardware_id()}"
    return hashlib.sha256(raw.encode()).hexdigest()

def _sign_local(payload: str) -> str:
    """HMAC-SHA256 signature for local file integrity only."""
    return hmac.new(_get_local_integrity_key().encode(), payload.encode(), hashlib.sha256).hexdigest()[:16]


def parse_license_key(key: str) -> dict | None:
    """
    Parse a license key for format.
    Validation against tampering is now deferred exclusively to the server.
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

    # Removed client-side HMAC secret checking. Verification is now server-enforced.
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
        if _sign_local(check_str) != stored_sig:
            return None
        return data
    except Exception:
        return None


def _write_license_file(data: dict):
    """Write the local license file with integrity signature."""
    check_str = f"{data['key']}:{data['hardware_id']}:{data['plan']}:{data['activated_at']}:{data['expires_at']}"
    data["integrity"] = _sign_local(check_str)
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

    # Resolve candidate backend URLs (stable Vercel-discovered URL first).
    urls_to_try = _build_backend_urls()
    if not urls_to_try:
        return False, "Server URL not configured. Cannot verify license."

    # First verify license isn't revoked
    verified = False
    verified_url = ""
    for try_url in urls_to_try:
        for _attempt in range(2):
            try:
                payload = json.dumps({"license_key": key.strip().upper(), "hardware_id": hw_id}).encode()
                _vreq = urllib.request.Request(
                    f"{try_url}/api/monitoring/license/verify",
                    data=payload,
                    headers={"Content-Type": "application/json"},
                    method="POST"
                )
                with _safe_urlopen(_vreq, timeout=5) as _vresp:
                    vdata = json.loads(_vresp.read())
                    if vdata.get("found"):
                        if not vdata.get("is_active", True):
                            detail = (vdata.get("error") or "").strip()
                            if detail:
                                return False, detail
                            return False, "This license has been deactivated or revoked."
                        verified = True
                        verified_url = try_url
                        break
                    else:
                        return False, "Invalid or unrecognized license key."
            except Exception as exc:
                logger.warning(f"[LICENSE] Activation verification check failed ({try_url}): {exc}")
                if _attempt < 1:
                    time.sleep(1)
        if verified:
            break
    
    if not verified:
        return False, "Could not contact server to verify license. Please check your internet connection."

    # Now fetch branch (prefer the URL that passed verification).
    branch_urls = [verified_url] if verified_url else []
    for _url in urls_to_try:
        if _url and _url not in branch_urls:
            branch_urls.append(_url)

    for try_url in branch_urls:
        try:
            _url = (f"{try_url}/api/payments/license-branch"
                    f"?license_key={key.strip().upper()}")
            _req = urllib.request.Request(_url, headers={"Accept": "application/json"}, method="GET")
            with _safe_urlopen(_req, timeout=10) as _resp:
                branch_data = json.loads(_resp.read())
            if branch_data.get("branch_name"):
                license_data["branch_name"] = branch_data["branch_name"]
                license_data["branch_url"] = branch_data["branch_url"]
                license_data["service_type"] = branch_data["service_type"]
                logger.info(f"[LICENSE] Branch fetched: {branch_data['branch_name']}")
            break
        except Exception as exc:
            logger.warning(f"[LICENSE] Branch fetch failed ({try_url}): {exc}")

    # Reset revocation cache to this key after a successful activation flow.
    _revoke_cache["time"] = time.time()
    _revoke_cache["key"] = key.strip().upper()
    _revoke_cache["not_revoked"] = True

    _write_license_file(license_data)
    register_desktop_hardware_with_backend()
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

    register_desktop_hardware_with_backend()

    return True, f"Trial activated! Expires in {trial_info['duration_days']} day(s)."


# ── Revocation check cache (in-memory, per session) ──────────────────────────
# Avoids blocking the UI on every get_license_status() call.
# Format: {"time": float | None, "not_revoked": bool, "key": str | None}
_revoke_cache: dict = {"time": None, "not_revoked": True, "key": None}
_REVOKE_CACHE_TTL = 300  # 5 minutes

# Stable URL to discover the current backend URL (survives tunnel restarts)
_VERCEL_URL = "https://tls-saas.vercel.app"
_BACKEND_URL_CACHE: dict = {"time": None, "url": None}
_BACKEND_URL_TTL = 3600  # 1 hour
_TLS_USAGE_SYNC_CACHE: dict = {"time": None}
_TLS_USAGE_SYNC_TTL = 120  # 2 minutes


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


def _build_backend_urls() -> list[str]:
    """Return unique backend base URLs in preferred order."""
    urls: list[str] = []
    discovered = _fetch_current_backend_url()
    if discovered:
        urls.append(discovered)
    for candidate in [Config.LICENSE_SERVER_URL, Config.BACKEND_URL]:
        url = (candidate or "").rstrip("/")
        if url and url not in urls:
            urls.append(url)
    return urls


def read_dev_expiry_override() -> datetime | None:
    """Optional dev-only simulated expiry (ISO datetime in .dev_license_expiry_override)."""
    try:
        if not os.path.exists(DEV_EXPIRY_OVERRIDE_FILE):
            return None
        with open(DEV_EXPIRY_OVERRIDE_FILE, "r", encoding="utf-8") as f:
            raw = f.read().strip()
        if not raw:
            return None
        dt = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except Exception:
        return None


def _set_license_revocation_state(revoked: bool, reason: str = "") -> None:
    """Persist or clear a local revoked marker without changing the core license identity."""
    data = _read_license_file()
    if not data:
        return
    if revoked:
        data["revoked_at"] = datetime.now(timezone.utc).isoformat()
        if reason:
            data["revoked_reason"] = reason
    else:
        data.pop("revoked_at", None)
        data.pop("revoked_reason", None)
    _write_license_file(data)


def write_dev_expiry_override(dt: datetime | None) -> None:
    """Set or clear simulated expiry for testing (dashboard expiry / renewal flows)."""
    try:
        if dt is None:
            if os.path.exists(DEV_EXPIRY_OVERRIDE_FILE):
                os.remove(DEV_EXPIRY_OVERRIDE_FILE)
            _set_license_revocation_state(False)
            return
        with open(DEV_EXPIRY_OVERRIDE_FILE, "w", encoding="utf-8") as f:
            f.write(dt.isoformat())
        if dt <= datetime.now(timezone.utc):
            _set_license_revocation_state(True, "simulated expiry")
        else:
            _set_license_revocation_state(False)
    except Exception as exc:
        logger.warning("[LICENSE] dev expiry override write failed: %s", exc)


def get_license_status(force_network: bool = False) -> dict | None:
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
    dev_sim = read_dev_expiry_override()
    revoked_at = data.get("revoked_at")
    if revoked_at:
        try:
            revoked_dt = datetime.fromisoformat(str(revoked_at).replace("Z", "+00:00"))
            if revoked_dt.tzinfo is None:
                revoked_dt = revoked_dt.replace(tzinfo=timezone.utc)
        except Exception:
            revoked_dt = datetime.now(timezone.utc)
    else:
        revoked_dt = None
    if dev_sim is not None:
        expires = dev_sim
    is_expired = datetime.now(timezone.utc) > expires
    if revoked_dt is not None or is_expired:
        return {
            "valid": False,
            "expired": True,
            "plan": data["plan"],
            "plan_info": PLANS.get(data["plan"], PLANS["trial"]),
            "expires_at": expires,
            "days_remaining": 0,
            "revoked_at": revoked_dt,
            "message": "License expired",
        }

    # Server-side revocation check (best-effort, cached per session)
    # Only check for non-trial licenses to reduce server load.
    if data["plan"] != "trial" and data.get("key"):
        now_ts = time.time()
        current_key = str(data.get("key") or "").upper()
        cache_valid = (
            not force_network
            and _revoke_cache["time"] is not None
            and now_ts - _revoke_cache["time"] < _REVOKE_CACHE_TTL
            and str(_revoke_cache.get("key") or "").upper() == current_key
        )
        if cache_valid and not _revoke_cache["not_revoked"]:
            # Cached as revoked — enforce it
            logger.info("[LICENSE] Revoked (cached) — removing local license")
            if os.path.exists(LICENSE_FILE):
                os.remove(LICENSE_FILE)
            return None

        if not cache_valid:
            # Build list of URLs to try: Vercel-discovered URL first, then configured fallbacks.
            urls_to_try = _build_backend_urls()

            revoked = False
            check_done = False
            # Keep this path responsive: no retries/sleeps on UI-triggered status checks.
            # If network is flaky, we fail open briefly and retry on next cache window.
            for try_url in urls_to_try:
                try:
                    payload = json.dumps({
                        "license_key": data["key"],
                        "hardware_id": hw_id,
                    }).encode()
                    req = urllib.request.Request(
                        f"{try_url}/api/monitoring/license/verify",
                        data=payload,
                        headers={"Content-Type": "application/json"},
                        method="POST",
                    )
                    with _safe_urlopen(req, timeout=3) as resp:
                        result = json.loads(resp.read())
                        if result.get("found"):
                            if not result.get("is_active", True):
                                revoked = True
                        else:
                            # Not found in database -> Revoked
                            revoked = True
                        
                        logger.debug(f"[LICENSE] Server verify OK: is_active={result.get('is_active')}")
                    check_done = True
                    break
                except Exception as exc:
                    logger.warning(f"[LICENSE] Revocation check failed ({try_url}): {exc}")

            if not check_done:
                logger.warning("[LICENSE] Could not verify license with server. Failing closed.")
                return None

            _revoke_cache["time"] = now_ts
            _revoke_cache["key"] = current_key
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

    out = {
        "valid": True,
        "expired": False,
        "plan": plan,
        "plan_info": plan_info,
        "expires_at": expires,
        "days_remaining": max(0, (expires - datetime.now(timezone.utc)).days),
        "checks_today": checks_today,
        "checks_limit": plan_info["checks_per_day"],
        "min_interval": plan_info["min_interval"],
        "key": data.get("key", ""),
        "branch_name": data.get("branch_name"),
        "branch_url": data.get("branch_url"),
        "service_type": data.get("service_type"),
        "message": f"License: {plan_info['name']}",
    }
    if dev_sim is not None:
        out["dev_expiry_override_active"] = True
    return out


def can_check() -> tuple[bool, str]:
    """Check if user can perform a check right now."""
    status = get_license_status()
    if not status:
        return False, "No license found. Please activate a license."
    if not status["valid"]:
        return False, "License expired. Please renew."
    if status["checks_today"] >= status["checks_limit"]:
        return False, f"Daily check limit reached ({status['checks_limit']})."
    return True, ""


def _tls_payload_emails_from_settings(settings) -> list[str]:
    emails: set[str] = set()
    if getattr(settings, "tls_email", None):
        emails.add(settings.tls_email.strip().lower())
    try:
        history = json.loads(settings.tls_email_history or "[]")
        if isinstance(history, list):
            for item in history:
                if not isinstance(item, dict):
                    continue
                for k in ("old_email", "new_email"):
                    v = (item.get(k) or "").strip().lower()
                    if v:
                        emails.add(v)
    except Exception:
        pass
    return sorted(emails)


def _apply_tls_usage_from_server_response(data: dict) -> None:
    """Merge server-side TLS email limits into local UserSettings (reinstall-safe)."""
    if not data:
        return
    tc = data.get("tls_email_change_count")
    tu = data.get("tls_emails_used")
    if tc is None and not tu:
        return
    from database import SessionLocal, UserSettings

    db = SessionLocal()
    try:
        settings = db.query(UserSettings).filter(UserSettings.user_id == 1).first()
        if not settings:
            return
        if tc is not None:
            settings.tls_email_change_count = max(settings.tls_email_change_count or 0, int(tc))
        if tu and isinstance(tu, list):
            try:
                history = json.loads(settings.tls_email_history or "[]")
                if not isinstance(history, list):
                    history = []
            except Exception:
                history = []
            known: set[str] = set()
            for item in history:
                if not isinstance(item, dict):
                    continue
                for k in ("old_email", "new_email"):
                    v = (item.get(k) or "").strip().lower()
                    if v:
                        known.add(v)
            if settings.tls_email:
                known.add(settings.tls_email.strip().lower())
            changed = False
            for em in tu:
                if not isinstance(em, str) or not em.strip():
                    continue
                e = em.strip().lower()
                if e not in known:
                    history.append({
                        "old_email": "",
                        "new_email": e,
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                        "source": "server_sync",
                    })
                    known.add(e)
                    changed = True
            if changed:
                settings.tls_email_history = json.dumps(history)
        db.commit()
    finally:
        db.close()


def sync_tls_email_usage_from_server(force: bool = False, require_server_for_paid: bool = False) -> bool:
    """Pull TLS email usage counts from backend and return True when sync succeeds.

    For paid licenses, caller may require a successful server sync to enforce limits
    across reinstalls/devices.
    """
    try:
        now = time.time()
        if (
            not force
            and _TLS_USAGE_SYNC_CACHE["time"] is not None
            and now - float(_TLS_USAGE_SYNC_CACHE["time"]) < _TLS_USAGE_SYNC_TTL
        ):
            return True

        lic = _read_license_file() or {}
        lic_key = str(lic.get("key") or "").strip()
        is_paid_license = bool(lic_key and lic_key.upper() != "TRIAL")

        urls_to_try = _build_backend_urls()
        if not urls_to_try:
            return False if (is_paid_license and require_server_for_paid) else True

        # Paid licenses: usage is tied to subscription user, not device.
        if is_paid_license:
            encoded = urllib.parse.quote(lic_key, safe="")
            for backend_url in urls_to_try:
                try:
                    req = urllib.request.Request(
                        f"{backend_url}/api/monitoring/license/{encoded}/tls-email-usage",
                        headers={"Accept": "application/json"},
                        method="GET",
                    )
                    with _safe_urlopen(req, timeout=3) as resp:
                        raw = resp.read().decode()
                        if raw:
                            _apply_tls_usage_from_server_response(json.loads(raw))
                            _TLS_USAGE_SYNC_CACHE["time"] = now
                            return True
                except Exception:
                    continue
            return False if require_server_for_paid else True

        # Trial fallback: still device-scoped.
        hw_id = get_hardware_id()
        if not hw_id or len(str(hw_id).strip()) < 8:
            return True
        for backend_url in urls_to_try:
            try:
                req = urllib.request.Request(
                    f"{backend_url}/api/monitoring/hardware/{hw_id}/usage",
                    headers={"Accept": "application/json"},
                    method="GET",
                )
                with _safe_urlopen(req, timeout=3) as resp:
                    raw = resp.read().decode()
                    if raw:
                        _apply_tls_usage_from_server_response(json.loads(raw))
                        _TLS_USAGE_SYNC_CACHE["time"] = now
                        return True
            except Exception:
                continue
        return True
    except Exception:
        return False


def register_desktop_hardware_with_backend() -> None:
    """Ensure backend has a hardware_usage row (trial email relay; idempotent)."""
    try:
        hw_id = get_hardware_id()
        if not hw_id or len(str(hw_id).strip()) < 8:
            return
        urls_to_try = _build_backend_urls()
        if not urls_to_try:
            return
        body: dict = {"hardware_id": str(hw_id).strip()}
        lic = _read_license_file() or {}
        lic_key = str(lic.get("key") or "").strip()
        if lic_key:
            body["license_key"] = lic_key
        try:
            from database import SessionLocal, UserSettings

            db = SessionLocal()
            s = db.query(UserSettings).filter(UserSettings.user_id == 1).first()
            if s:
                body["tls_email_change_count"] = s.tls_email_change_count or 0
                body["tls_emails_used"] = _tls_payload_emails_from_settings(s)
            db.close()
        except Exception:
            pass
        payload = json.dumps(body).encode("utf-8")
        for backend_url in urls_to_try:
            try:
                req = urllib.request.Request(
                    f"{backend_url}/api/monitoring/register-desktop-hardware",
                    data=payload,
                    headers={"Content-Type": "application/json", "Accept": "application/json"},
                    method="POST",
                )
                with _safe_urlopen(req, timeout=10) as resp:
                    raw = resp.read().decode()
                    if raw:
                        _apply_tls_usage_from_server_response(json.loads(raw))
                return
            except Exception:
                continue
    except Exception:
        pass


def increment_check_count():
    """Increment today's check counter. Syncs with backend to prevent local DB wipes."""
    data = _read_license_file()
    if not data:
        return
        
    today = datetime.now(timezone.utc).date().isoformat()
    hw_id = get_hardware_id()
    new_count = None
    
    # Send increment to backend
    try:
        backend_url = getattr(Config, "BACKEND_URL", "https://backend-cold-sound-6496.fly.dev").rstrip("/")
        req = urllib.request.Request(
            f"{backend_url}/api/monitoring/hardware/{hw_id}/increment",
            method="POST",
            headers={"Content-Length": "0", "Accept": "application/json"}
        )
        ctx = _get_ssl_context()
        with urllib.request.urlopen(req, context=ctx, timeout=5) as response:
            resp_data = json.loads(response.read().decode())
            new_count = resp_data.get("checks_today")
    except Exception as e:
        logger.error(f"Failed to sync increment to backend: {e}")

    # Fallback to local if backend fails, otherwise use backend count
    if new_count is not None:
        data["checks_today"] = new_count
        data["checks_reset_date"] = today
    else:
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

    lic_key = str(status.get("key") or "").strip()
    is_paid_license = bool(lic_key and lic_key.upper() != "TRIAL")
    sync_ok = sync_tls_email_usage_from_server(force=True, require_server_for_paid=is_paid_license)
    if is_paid_license and not sync_ok:
        return False, "Could not verify TLS email limit from server. Please check internet and try again."
    
    plan_info = status.get("plan_info", {})
    max_emails = plan_info.get("max_emails", 1)
    
    from database import SessionLocal, UserSettings
    db = SessionLocal()
    try:
        settings = db.query(UserSettings).filter(UserSettings.user_id == 1).first()
        if not settings:
            return True, "First TLS email setup allowed"
        
        target_email = (new_email or "").strip().lower()

        # Check if same email (no increment needed)
        if settings.tls_email and settings.tls_email.lower() == target_email:
            return True, "Same TLS email, no change needed"

        # Enforce max distinct TLS emails allowed for this device.
        # Example with max=2: user can use at most 2 different TLS emails total.
        used_emails: set[str] = set()
        if settings.tls_email:
            used_emails.add(settings.tls_email.strip().lower())
        try:
            history = json.loads(settings.tls_email_history or "[]")
            if isinstance(history, list):
                for item in history:
                    if not isinstance(item, dict):
                        continue
                    old_e = (item.get("old_email") or "").strip().lower()
                    new_e = (item.get("new_email") or "").strip().lower()
                    if old_e:
                        used_emails.add(old_e)
                    if new_e:
                        used_emails.add(new_e)
        except Exception:
            pass

        # If this email was already used on this device, allow switching back to it.
        if target_email and target_email in used_emails:
            return True, f"TLS email already approved ({len(used_emails)}/{max_emails} used)."

        if target_email and target_email not in used_emails and len(used_emails) >= max_emails:
            return False, f"TLS email limit reached. Maximum {max_emails} different TLS email(s) allowed for this subscription."

        next_used = len(used_emails) + (1 if target_email else 0)
        return True, f"TLS email change allowed ({min(next_used, max_emails)}/{max_emails} used)."
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
            old_norm = (old_email or "").strip().lower()
            new_norm = (new_email or "").strip().lower()

            try:
                history = json.loads(settings.tls_email_history or "[]")
            except:
                history = []

            used_emails: set[str] = set()
            if settings.tls_email:
                used_emails.add((settings.tls_email or "").strip().lower())
            for item in history:
                if not isinstance(item, dict):
                    continue
                old_e = (item.get("old_email") or "").strip().lower()
                new_e = (item.get("new_email") or "").strip().lower()
                if old_e:
                    used_emails.add(old_e)
                if new_e:
                    used_emails.add(new_e)

            # Only consume quota when introducing a brand-new TLS email on this device.
            if new_norm and new_norm not in used_emails:
                settings.tls_email_change_count = (settings.tls_email_change_count or 0) + 1
            
            history.append({
                "old_email": old_norm,
                "new_email": new_norm,
                "timestamp": datetime.now(timezone.utc).isoformat()
            })
            settings.tls_email_history = json.dumps(history)
            
            db.commit()
    finally:
        db.close()
    # Keep Save Configuration responsive: persist server sync in background.
    threading.Thread(target=register_desktop_hardware_with_backend, daemon=True).start()


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
                "max_emails": 2,
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
