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
    APP_VERSION: str = "2.0.0"
    DEBUG: bool = False
    SECRET_KEY: str = "CHANGE-THIS-TO-A-RANDOM-64-CHAR-STRING-IN-PRODUCTION"
    ALLOWED_ORIGINS: str = "http://localhost:3000,http://127.0.0.1:3000"

    # ── Database ─────────────────────────────────────────
    # For development: SQLite; for production: PostgreSQL
    DATABASE_URL: str = "sqlite+aiosqlite:///./data/tls_saas.db"
    # PostgreSQL example: "postgresql+asyncpg://user:pass@localhost:5432/tls_saas"

    # ── JWT Auth ─────────────────────────────────────────
    JWT_SECRET: str = "jwt-secret-change-in-production-make-it-long"
    JWT_ALGORITHM: str = "HS256"
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24  # 24 hours
    JWT_REFRESH_TOKEN_EXPIRE_DAYS: int = 30

    # ── Admin ────────────────────────────────────────────
    ADMIN_EMAIL: str = "admin@tlschecker.com"
    ADMIN_PASSWORD: str = "admin123"  # Changed on first login

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
    CREDENTIAL_ENCRYPTION_KEY: str = "credential-encryption-key-change-this"

    # ── Pricing (EGP) ───────────────────────────────────
    PRICE_LEGALIZATION_MONTHLY: float = 300.0
    PRICE_VISA_MONTHLY: float = 500.0
    CURRENCY: str = "EGP"

    @property
    def allowed_origins_list(self) -> list[str]:
        return [o.strip() for o in self.ALLOWED_ORIGINS.split(",")]

    class Config:
        env_file = "../.env"
        extra = "ignore"
        env_file_encoding = "utf-8"


settings = Settings()
