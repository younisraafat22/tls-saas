"""
Application Configuration
Centralized configuration management
"""
import os
import sys
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables from .env
# When running as frozen exe, load the bundled .env first, then allow overrides
# from the exe directory and AppData (so the user can update BACKEND_URL without
# rebuilding the exe).
if getattr(sys, 'frozen', False):
    _meipass = getattr(sys, '_MEIPASS', None)
    # 1) Bundled .env (lowest priority — baked in at build time)
    _bundled_env = Path(_meipass) / '.env' if _meipass else None
    if _bundled_env and _bundled_env.exists():
        load_dotenv(_bundled_env)
    # 2) .env next to the exe (medium priority)
    _exe_env = Path(sys.executable).parent / '.env'
    if _exe_env.exists():
        load_dotenv(_exe_env, override=True)
    # 3) .env in AppData (highest priority — survives reinstalls)
    _appdata_env = Path(os.getenv('APPDATA', '')) / 'TLSAppointmentChecker' / '.env'
    if _appdata_env.exists():
        load_dotenv(_appdata_env, override=True)
else:
    _env_path = Path(__file__).resolve().parent / '.env'
    load_dotenv(_env_path, override=True)

# Base directory - use AppData for installed apps, current dir for development
if getattr(sys, 'frozen', False):
    # Running as .exe
    BASE_DIR = Path(os.getenv('APPDATA')) / 'TLSAppointmentChecker'
    BASE_DIR.mkdir(parents=True, exist_ok=True)
elif 'Program Files' in str(Path(__file__).resolve()):
    # Running from Program Files installation
    BASE_DIR = Path(os.getenv('APPDATA')) / 'TLSAppointmentChecker'
    BASE_DIR.mkdir(parents=True, exist_ok=True)
else:
    # Running from source
    BASE_DIR = Path(__file__).resolve().parent

class Config:
    """Application configuration"""
    
    # Base directory (also available as class attribute)
    BASE_DIR = BASE_DIR
    
    # App Info
    APP_NAME = os.getenv("APP_NAME", "TLS Appointment Checker")
    APP_VERSION = os.getenv("APP_VERSION", "1.0.0")
    
    # Database
    DATABASE_URL = os.getenv("DATABASE_URL", f"sqlite:///{BASE_DIR}/tls_app.db")
    
    # Security
    SECRET_KEY = os.getenv("SECRET_KEY", "change-this-secret-key-in-production")
    
    # Backend API URL (for authentication, subscriptions, result reporting)
    BACKEND_URL = os.getenv("BACKEND_URL", "https://stephanie-centres-chart-whole.trycloudflare.com")
    
    # Website URL (for links in the app)
    WEBSITE_URL = os.getenv("WEBSITE_URL", "https://tls-saas.vercel.app")
    
    # GitHub Releases URL (for auto-update)
    GITHUB_RELEASES_URL = os.getenv(
        "GITHUB_RELEASES_URL",
        "https://api.github.com/repos/YOUR_USERNAME/tls-appointment-checker/releases/latest"
    )
    
    # Admin Email (Hidden from users - used for local email sending fallback)
    ADMIN_EMAIL = os.getenv("ADMIN_EMAIL")
    ADMIN_EMAIL_PASSWORD = os.getenv("ADMIN_EMAIL_PASSWORD")
    SMTP_SERVER = os.getenv("SMTP_SERVER", "smtp.gmail.com")
    SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
    
    # Trial & License
    TRIAL_DAYS = int(os.getenv("TRIAL_DAYS", "3"))
    # License server URL — defaults to BACKEND_URL (unified server)
    LICENSE_SERVER_URL = os.getenv("LICENSE_SERVER_URL", BACKEND_URL)
    
    # AI Vision CAPTCHA Solver (Google Gemini)
    GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
    
    # TLS Website – Legalization
    TLS_URL = "https://legalization-de.tlscontact.com/service/eg/egCAI2de/home"
    LOGIN_URL = "https://legalization-de.tlscontact.com/login"

    LEGALIZATION_BRANCHES = {
        "Sheikh Zayed": "https://legalization-de.tlscontact.com/service/eg/egCAI2de/home",
        "Hurghada": "https://legalization-de.tlscontact.com/service/eg/egHRG2de/home",
    }

    # TLS Website – Visa Process
    VISA_BRANCHES = {
        "New Cairo": "https://visas-de.tlscontact.com/en-us/country/eg/vac/egHAC2de",
        "El-Sheikh Zayed": "https://visas-de.tlscontact.com/en-us/country/eg/vac/egCAI2de",
        "Alexandria": "https://visas-de.tlscontact.com/en-us/country/eg/vac/egALY2de",
        "Hurghada": "https://visas-de.tlscontact.com/en-us/country/eg/vac/egHRG2de",
    }

    # Default Settings
    DEFAULT_CHECK_INTERVAL = 30  # minutes (every 30 minutes)
    DEFAULT_NOTIFICATION_TYPES = ["email", "windows"]
    
    # Browser Settings
    BROWSER_HEADLESS = True
    BROWSER_PAGE_LOAD_TIMEOUT = 60
    CLOUDFLARE_MAX_WAIT = 180
    
    # Notification Settings
    STATUS_REPORT_INTERVAL = 6  # hours
    
    @classmethod
    def validate(cls):
        """Validate required configuration"""
        if not cls.ADMIN_EMAIL or not cls.ADMIN_EMAIL_PASSWORD:
            raise ValueError("Admin email credentials not configured in .env file")
        return True
