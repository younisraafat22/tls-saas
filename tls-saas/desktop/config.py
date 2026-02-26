"""
Application Configuration
Centralized configuration management
"""
import os
import sys
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables from .env
# When running as frozen exe, look next to the .exe; otherwise use source dir
if getattr(sys, 'frozen', False):
    _env_path = Path(sys.executable).parent / '.env'
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
    APP_VERSION = os.getenv("APP_VERSION", "2.0.0")
    
    # Database
    DATABASE_URL = os.getenv("DATABASE_URL", f"sqlite:///{BASE_DIR}/tls_app.db")
    
    # Security
    SECRET_KEY = os.getenv("SECRET_KEY", "change-this-secret-key-in-production")
    
    # Backend API URL (for authentication, subscriptions, result reporting)
    BACKEND_URL = os.getenv("BACKEND_URL", "https://api.tlschecker.com")
    
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
    
    # Trial & License (offline fallback)
    TRIAL_DAYS = int(os.getenv("TRIAL_DAYS", "3"))
    LICENSE_SERVER_URL = os.getenv("LICENSE_SERVER_URL", os.getenv("BACKEND_URL", "http://192.168.1.108:8000"))
    
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
    DEFAULT_CHECK_INTERVAL = 60  # minutes (1 hour)
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
