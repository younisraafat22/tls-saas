"""
Desktop App Routes — Version check, download info
"""

from fastapi import APIRouter
from app.schemas import AppVersionResponse
from app.config import settings

router = APIRouter(prefix="/api/app", tags=["desktop-app"])


@router.get("/version", response_model=AppVersionResponse)
async def app_version():
    """
    Returns the latest desktop app version info.
    Used by the desktop app for auto-update checks.
    Version/URL/notes are controlled via env vars:
      DESKTOP_APP_VERSION, DESKTOP_DOWNLOAD_URL, DESKTOP_RELEASE_NOTES, DESKTOP_FORCE_UPDATE
    """
    return AppVersionResponse(
        version=settings.DESKTOP_APP_VERSION,
        download_url=settings.DESKTOP_DOWNLOAD_URL,
        release_notes=settings.DESKTOP_RELEASE_NOTES,
        force_update=settings.DESKTOP_FORCE_UPDATE,
    )


@router.get("/download-info")
async def download_info():
    """
    Returns download information for the landing page frontend.
    """
    return {
        "version": settings.DESKTOP_APP_VERSION,
        "download_url": settings.DESKTOP_DOWNLOAD_URL,
        "platforms": ["windows"],
        "size_mb": "~80",
        "requirements": "Windows 10/11, Chrome browser installed",
        "features": [
            "Local TLS appointment monitoring (runs on your machine)",
            "Selenium-based browser automation with anti-detection",
            "Audio CAPTCHA solver",
            "Email and Windows notifications",
            "All Egypt branches supported",
            "Encrypted credential storage",
        ],
    }
