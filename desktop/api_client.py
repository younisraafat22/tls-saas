"""
API Client for TLS Appointment Checker Desktop App
Communicates with the FastAPI backend for auth, subscriptions, and result reporting.
"""
import json
import urllib.request
import urllib.error
import urllib.parse
import os
import threading
from datetime import datetime, timezone
from config import Config, BASE_DIR

# Token storage file
TOKEN_FILE = os.path.join(str(BASE_DIR), ".auth_tokens")


class APIClient:
    """HTTP client for the backend API."""

    def __init__(self, base_url: str = None):
        self.base_url = (base_url or Config.BACKEND_URL).rstrip("/")
        self._access_token = None
        self._refresh_token = None
        self._user = None
        self._load_tokens()

    # ── Token Management ─────────────────────────────────

    def _load_tokens(self):
        """Load saved tokens from disk."""
        try:
            if os.path.exists(TOKEN_FILE):
                with open(TOKEN_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                self._access_token = data.get("access_token")
                self._refresh_token = data.get("refresh_token")
                self._user = data.get("user")
        except Exception:
            pass

    def _save_tokens(self):
        """Persist tokens to disk."""
        try:
            data = {
                "access_token": self._access_token,
                "refresh_token": self._refresh_token,
                "user": self._user,
            }
            with open(TOKEN_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f)
        except Exception:
            pass

    def _clear_tokens(self):
        """Remove all stored tokens."""
        self._access_token = None
        self._refresh_token = None
        self._user = None
        try:
            if os.path.exists(TOKEN_FILE):
                os.remove(TOKEN_FILE)
        except Exception:
            pass

    @property
    def is_logged_in(self) -> bool:
        return self._access_token is not None

    @property
    def user(self) -> dict | None:
        return self._user

    @property
    def access_token(self) -> str | None:
        return self._access_token

    # ── HTTP Helpers ────────────────────────────────────

    def _request(self, method: str, path: str, body: dict = None,
                 auth: bool = True, timeout: int = 15) -> dict:
        """
        Make an HTTP request to the backend.
        Automatically retries with token refresh on 401.
        """
        url = f"{self.base_url}{path}"
        headers = {"Content-Type": "application/json"}

        if auth and self._access_token:
            headers["Authorization"] = f"Bearer {self._access_token}"

        data = json.dumps(body).encode("utf-8") if body else None
        req = urllib.request.Request(url, data=data, headers=headers, method=method)

        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            if e.code == 401 and auth and self._refresh_token:
                # Try refresh
                if self._do_refresh():
                    headers["Authorization"] = f"Bearer {self._access_token}"
                    req2 = urllib.request.Request(url, data=data, headers=headers, method=method)
                    with urllib.request.urlopen(req2, timeout=timeout) as resp2:
                        return json.loads(resp2.read().decode("utf-8"))
                else:
                    self._clear_tokens()
                    raise
            # Parse error body
            try:
                err_body = json.loads(e.read().decode("utf-8"))
                detail = err_body.get("detail", str(e))
            except Exception:
                detail = str(e)
            raise APIError(e.code, detail) from e
        except (urllib.error.URLError, TimeoutError, OSError, ConnectionError) as e:
            raise APIError(0, f"Cannot reach server: {e}") from e

    def _do_refresh(self) -> bool:
        """Attempt to refresh the access token."""
        try:
            url = f"{self.base_url}/api/auth/refresh"
            data = json.dumps({"refresh_token": self._refresh_token}).encode("utf-8")
            req = urllib.request.Request(url, data=data,
                                        headers={"Content-Type": "application/json"},
                                        method="POST")
            with urllib.request.urlopen(req, timeout=10) as resp:
                result = json.loads(resp.read().decode("utf-8"))
            self._access_token = result["access_token"]
            self._refresh_token = result["refresh_token"]
            self._user = result.get("user", self._user)
            self._save_tokens()
            return True
        except Exception:
            return False

    # ── Auth Endpoints ──────────────────────────────────

    def login(self, email: str, password: str) -> dict:
        """Login and store tokens. Returns user dict."""
        result = self._request("POST", "/api/auth/login",
                               {"email": email, "password": password}, auth=False)
        self._access_token = result["access_token"]
        self._refresh_token = result["refresh_token"]
        self._user = result.get("user")
        self._save_tokens()
        return self._user

    def register(self, email: str, password: str, full_name: str, phone: str = "") -> dict:
        """Register a new account and store tokens. Returns user dict."""
        result = self._request("POST", "/api/auth/register", {
            "email": email,
            "password": password,
            "full_name": full_name,
            "phone": phone,
        }, auth=False)
        self._access_token = result["access_token"]
        self._refresh_token = result["refresh_token"]
        self._user = result.get("user")
        self._save_tokens()
        return self._user

    def logout(self):
        """Clear local auth state."""
        self._clear_tokens()

    def get_me(self) -> dict:
        """Fetch current user profile (also refreshes cached user)."""
        user = self._request("GET", "/api/auth/me")
        self._user = user
        self._save_tokens()
        return user

    # ── Subscription Endpoints ──────────────────────────

    def get_subscription(self) -> dict | None:
        """Get active subscription info. Returns None if no active sub."""
        try:
            return self._request("GET", "/api/subscriptions/active")
        except APIError as e:
            if e.status == 404:
                return None
            raise

    def get_plans(self) -> list:
        """Get available plans."""
        return self._request("GET", "/api/subscriptions/plans")

    def get_branches(self) -> list:
        """Get all branches."""
        return self._request("GET", "/api/subscriptions/branches")

    def get_my_branches(self) -> list:
        """Get user's monitored branches."""
        return self._request("GET", "/api/subscriptions/my-branches")

    # ── Monitoring / Result Reporting ───────────────────

    def report_check_result(self, branch_name: str, service_type: str,
                            slots_available: bool, slot_details: str = "",
                            screenshot_b64: str = "", duration_seconds: float = 0,
                            error: str = "") -> dict:
        """
        Report a local check result to the backend.
        This allows the dashboard to show results from the desktop app.
        """
        try:
            return self._request("POST", "/api/monitoring/report-desktop", {
                "branch_name": branch_name,
                "service_type": service_type,
                "slots_available": slots_available,
                "slot_details": slot_details,
                "screenshot_b64": screenshot_b64,
                "duration_seconds": duration_seconds,
                "error": error,
            })
        except Exception as e:
            print(f"[API] Failed to report result: {e}")
            return {}

    def report_check_result_async(self, **kwargs):
        """Fire-and-forget result reporting in background thread."""
        thread = threading.Thread(target=self.report_check_result, kwargs=kwargs, daemon=True)
        thread.start()

    def get_monitoring_status(self) -> dict:
        """Get monitoring status from backend."""
        return self._request("GET", "/api/monitoring/status")

    def get_check_results(self, limit: int = 20) -> list:
        """Get recent check results."""
        return self._request("GET", f"/api/monitoring/results?limit={limit}")

    # ── App Version Check ───────────────────────────────

    def check_app_version(self) -> dict | None:
        """Check if a new app version is available. Returns version info or None."""
        try:
            return self._request("GET", "/api/app/version", auth=False, timeout=5)
        except Exception:
            return None

    # ── Credentials ─────────────────────────────────────

    def get_credentials(self) -> list:
        """Get stored TLS credentials."""
        return self._request("GET", "/api/credentials/")

    def save_credentials(self, service_type: str, email: str, password: str) -> dict:
        """Save TLS credentials to backend."""
        return self._request("POST", "/api/credentials/", {
            "service_type": service_type,
            "tls_email": email,
            "tls_password": password,
        })

    def delete_credentials(self, service_type: str) -> dict:
        """Delete TLS credentials from backend."""
        return self._request("DELETE", f"/api/credentials/{service_type}")


class APIError(Exception):
    """API request error with status code."""
    def __init__(self, status: int, detail: str):
        self.status = status
        self.detail = detail
        super().__init__(f"HTTP {status}: {detail}")


# Global API client instance
api_client = APIClient()
