"""
Application Configuration
All settings loaded from environment variables with sensible defaults.
"""

from pydantic_settings import BaseSettings
from typing import Optional
import os


class Settings(BaseSettings):
    # ── App ──────────────────────────────────────────────
    APP_NAME: str = "TLS Appointment Checker"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = False
    ALLOW_INSECURE_DEFAULTS: bool = False
    SECRET_KEY: str = ""
    ALLOWED_ORIGINS: str = "http://localhost:3000,http://127.0.0.1:3000"
    BACKEND_URL: str = "http://localhost:8000"
    FRONTEND_URL: str = "https://tls-saas.vercel.app"

    # ── Database ─────────────────────────────────────────
    # For development: SQLite; for production: PostgreSQL
    DATABASE_URL: str = "sqlite+aiosqlite:///./data/tls_saas.db"
    # PostgreSQL example: "postgresql+asyncpg://user:pass@localhost:5432/tls_saas"

    # ── JWT Auth ─────────────────────────────────────────
    JWT_SECRET: str = ""
    JWT_ALGORITHM: str = "HS256"
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24  # 24 hours
    JWT_REFRESH_TOKEN_EXPIRE_DAYS: int = 30

    # ── Admin ────────────────────────────────────────────
    ADMIN_EMAIL: str = "admin@tlschecker.com"
    ADMIN_PASSWORD: str = ""
    ADMIN_ERROR_EMAILS_ENABLED: bool = False

    # ── Email (SMTP) ─────────────────────────────────────
    SMTP_SERVER: str = "smtp.gmail.com"
    SMTP_PORT: int = 587
    SMTP_USERNAME: str = ""
    SMTP_PASSWORD: str = ""
    SENDER_EMAIL: str = ""
    SENDER_NAME: str = "TLS Appointment Checker"

    # ── Web Push (VAPID) ─────────────────────────────────
    VAPID_PRIVATE_KEY: str = ""
    VAPID_PUBLIC_KEY: str = ""
    VAPID_CLAIMS_EMAIL: str = "admin@tlschecker.com"

    # ── TLS Checker ──────────────────────────────────────
    CHECK_INTERVAL_MINUTES: int = 30
    BROWSER_HEADLESS: bool = True
    PLAYWRIGHT_TIMEOUT: int = 60000  # ms
    MAX_CONCURRENT_BROWSERS: int = 6

    # ── Encryption key for stored TLS credentials ────────
    CREDENTIAL_ENCRYPTION_KEY: str = ""

    # ── Pricing (EGP) ───────────────────────────────────
    PRICE_LEGALIZATION_MONTHLY: float = 300.0
    PRICE_VISA_MONTHLY: float = 300.0
    PRICE_PREMIUM_MONTHLY: float = 2500.0
    PRICE_ALL_IN_ONE_MONTHLY: float = 500.0
    CURRENCY: str = "EGP"

    # ── License Generation ───────────────────────────────
    LICENSE_HMAC_SECRET: str = ""

    # ── Worker (laptop → Fly.io) ─────────────────────────
    # Shared secret between the laptop worker and the Fly.io API.
    # Set via environment variable on both sides.
    WORKER_SECRET: str = ""

    # ── Desktop App Release ──────────────────────────────
    DESKTOP_APP_VERSION: str = "1.0.0"
    DESKTOP_DOWNLOAD_URL: str = "https://github.com/younisraafat22/tls-saas/releases/download/v1.0.0/TLS_Appointment_Checker_v1.0.0_Setup.exe"
    DESKTOP_RELEASE_NOTES: str = "v1.0.0: First stable release with local TLS appointment monitoring."
    DESKTOP_FORCE_UPDATE: bool = False

    @property
    def allowed_origins_list(self) -> list[str]:
        return [o.strip() for o in self.ALLOWED_ORIGINS.split(",")]

    class Config:
        env_file = ".env"
        extra = "ignore"
        env_file_encoding = "utf-8"

    def validate_security(self) -> None:
        if self.ALLOW_INSECURE_DEFAULTS:
            return

        missing = []
        for key in [
            "SECRET_KEY",
            "JWT_SECRET",
            "ADMIN_PASSWORD",
            "CREDENTIAL_ENCRYPTION_KEY",
            "LICENSE_HMAC_SECRET",
            "WORKER_SECRET",
        ]:
            if not getattr(self, key, ""):
                missing.append(key)

        if missing:
            joined = ", ".join(missing)
            raise RuntimeError(
                f"Missing required secure configuration values: {joined}. "
                "Set them in environment/.env, or set ALLOW_INSECURE_DEFAULTS=true only for local development."
            )


settings = Settings()
settings.validate_security()
