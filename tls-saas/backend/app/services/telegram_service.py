"""
Telegram Notification Service
Sends instant alerts via Telegram Bot API.
"""

import logging
import httpx
from app.config import settings

logger = logging.getLogger("telegram_service")

TELEGRAM_API = "https://api.telegram.org/bot{token}"


class TelegramService:
    def __init__(self):
        self.token = settings.TELEGRAM_BOT_TOKEN
        self.base_url = TELEGRAM_API.format(token=self.token) if self.token else ""

    async def send_message(self, chat_id: str, text: str, parse_mode: str = "HTML") -> bool:
        """Send a message to a Telegram chat."""
        if not self.token or not chat_id:
            return False

        try:
            async with httpx.AsyncClient() as client:
                resp = await client.post(
                    f"{self.base_url}/sendMessage",
                    json={
                        "chat_id": chat_id,
                        "text": text,
                        "parse_mode": parse_mode,
                        "disable_web_page_preview": True,
                    },
                    timeout=10,
                )
                if resp.status_code == 200:
                    logger.info(f"Telegram message sent to {chat_id}")
                    return True
                else:
                    logger.error(f"Telegram API error: {resp.status_code} {resp.text}")
                    return False
        except Exception as e:
            logger.error(f"Telegram send failed: {e}")
            return False

    async def send_appointment_alert(
        self,
        chat_id: str,
        branch_name: str,
        service_type: str,
        slot_details: dict | None = None,
    ) -> bool:
        """Send a formatted appointment alert via Telegram."""
        details = ""
        if slot_details and slot_details.get("message"):
            details = f"\n📋 {slot_details['message']}"

        text = (
            f"🎉 <b>Appointment Available!</b>\n\n"
            f"📍 <b>Branch:</b> {branch_name}\n"
            f"📄 <b>Service:</b> {service_type.title()}\n"
            f"{details}\n\n"
            f"⚡ <b>Act fast — slots fill up within minutes!</b>\n\n"
            f"🔗 <a href='https://legalization-de.tlscontact.com'>Book Now</a>"
        )
        return await self.send_message(chat_id, text)

    async def send_subscription_notification(self, chat_id: str, plan_name: str, expires_at: str) -> bool:
        text = (
            f"✅ <b>Subscription Activated!</b>\n\n"
            f"📦 Plan: {plan_name}\n"
            f"📅 Expires: {expires_at}\n\n"
            f"Head to your dashboard to select branches to monitor."
        )
        return await self.send_message(chat_id, text)

    async def get_bot_info(self) -> dict | None:
        """Get bot info to verify token is valid."""
        if not self.token:
            return None
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.get(f"{self.base_url}/getMe", timeout=5)
                if resp.status_code == 200:
                    return resp.json().get("result")
        except Exception:
            pass
        return None


telegram_service = TelegramService()
