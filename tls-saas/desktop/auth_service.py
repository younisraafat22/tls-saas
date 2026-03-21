"""
Auth Service (Minimal)
Kept only for TLS credential encryption/decryption.
All login/registration logic has been replaced by the license system.
"""
from cryptography.fernet import Fernet
from config import Config
import base64
import hashlib
import platform
import uuid


class AuthService:
    """Minimal auth service — only encrypts/decrypts TLS passwords."""

    def __init__(self):
        self._cipher = self._get_cipher()

    def _derive_local_secret(self) -> str:
        configured = (Config.SECRET_KEY or "").strip()
        if configured:
            return configured

        parts = [f"mac:{uuid.getnode()}", f"host:{platform.node()}"]
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
        return "|".join(parts)

    def _get_cipher(self):
        key = hashlib.sha256(self._derive_local_secret().encode()).digest()
        key_b64 = base64.urlsafe_b64encode(key)
        return Fernet(key_b64)

    def encrypt_password(self, password: str) -> str:
        """Encrypt a TLS password for storage."""
        return self._cipher.encrypt(password.encode()).decode()

    def decrypt_password(self, encrypted: str) -> str:
        """Decrypt a stored TLS password."""
        return self._cipher.decrypt(encrypted.encode()).decode()


# Global instance (imported by main.py and checker_service.py)
auth_service = AuthService()
