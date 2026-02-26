"""
Desktop App Routes — Version check, download info
"""

from fastapi import APIRouter
from app.schemas import AppVersionResponse

router = APIRouter(prefix="/api/app", tags=["desktop-app"])

# Desktop app version — update these when publishing new releases
DESKTOP_APP_VERSION = "2.0.0"
DESKTOP_DOWNLOAD_URL = ""  # Set to GitHub Releases URL when published
DESKTOP_RELEASE_NOTES = "Initial release with API-based authentication and local monitoring."


@router.get("/version", response_model=AppVersionResponse)
async def app_version():
    """
    Returns the latest desktop app version info.
    Used by the desktop app for auto-update checks.
    """
    return AppVersionResponse(
        version=DESKTOP_APP_VERSION,
        download_url=DESKTOP_DOWNLOAD_URL,
        release_notes=DESKTOP_RELEASE_NOTES,
        force_update=False,
    )


@router.get("/download-info")
async def download_info():
    """
    Returns download information for the landing page.
    """
    return {
        "version": DESKTOP_APP_VERSION,
        "download_url": DESKTOP_DOWNLOAD_URL,
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
