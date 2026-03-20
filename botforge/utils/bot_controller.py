"""
utils/bot_controller.py — التحكم في بوتات Telegram الأخرى عبر توكناتها
"""

from __future__ import annotations
import io
import logging

import httpx
from telegram import Bot, InputFile
from telegram.error import TelegramError

logger = logging.getLogger("BotForge.BotCtrl")


class BotController:
    """يستخدم Bot API للتحكم في بوت آخر (اسم، وصف، نبذة، صورة)"""

    @staticmethod
    async def get_info(token: str) -> dict:
        try:
            b  = Bot(token=token)
            me = await b.get_me()
            await b.close()
            return {
                "id":         me.id,
                "username":   me.username or "",
                "first_name": me.first_name or "",
                "can_join":   me.can_join_groups,
                "is_inline":  me.supports_inline_queries,
            }
        except Exception as e:
            return {"error": str(e)}

    @staticmethod
    async def _api_post(token: str, method: str, **payload) -> tuple[bool, str]:
        try:
            async with httpx.AsyncClient(timeout=20) as c:
                r = await c.post(
                    f"https://api.telegram.org/bot{token}/{method}",
                    json=payload,
                )
            d = r.json()
            ok = d.get("ok", False)
            return ok, "✅ تم" if ok else d.get("description", "فشل غير معروف")
        except Exception as e:
            return False, str(e)

    @staticmethod
    async def set_name(token: str, name: str) -> tuple[bool, str]:
        ok, msg = await BotController._api_post(token, "setMyName", name=name)
        return ok, f"✅ تم تغيير الاسم إلى: *{name}*" if ok else f"❌ {msg}"

    @staticmethod
    async def set_description(token: str, desc: str) -> tuple[bool, str]:
        ok, msg = await BotController._api_post(token, "setMyDescription", description=desc)
        return ok, "✅ تم تغيير الوصف" if ok else f"❌ {msg}"

    @staticmethod
    async def set_short_description(token: str, about: str) -> tuple[bool, str]:
        ok, msg = await BotController._api_post(token, "setMyShortDescription", short_description=about)
        return ok, "✅ تم تغيير النبذة" if ok else f"❌ {msg}"

    @staticmethod
    async def set_photo(token: str, photo_bytes: bytes) -> tuple[bool, str]:
        try:
            async with httpx.AsyncClient(timeout=30) as c:
                r = await c.post(
                    f"https://api.telegram.org/bot{token}/setMyProfilePhoto",
                    files={"photo": ("photo.jpg", photo_bytes, "image/jpeg")},
                )
            d = r.json()
            ok = d.get("ok", False)
            return ok, "✅ تم تغيير الصورة" if ok else f"❌ {d.get('description','فشل')}"
        except Exception as e:
            return False, f"❌ {e}"

    @staticmethod
    async def delete_photo(token: str) -> tuple[bool, str]:
        ok, msg = await BotController._api_post(token, "deleteMyProfilePhoto")
        return ok, "✅ تم حذف الصورة" if ok else f"❌ {msg}"


class SelfController:
    """يتحكم في بوت BotForge نفسه"""

    @staticmethod
    async def set_name(bot: Bot, name: str) -> tuple[bool, str]:
        try:
            await bot.set_my_name(name=name)
            return True, f"✅ اسم BotForge → *{name}*"
        except TelegramError as e:
            return False, f"❌ {e}"

    @staticmethod
    async def set_description(bot: Bot, desc: str) -> tuple[bool, str]:
        try:
            await bot.set_my_description(description=desc)
            return True, "✅ تم تغيير الوصف"
        except TelegramError as e:
            return False, f"❌ {e}"

    @staticmethod
    async def set_short_description(bot: Bot, about: str) -> tuple[bool, str]:
        try:
            await bot.set_my_short_description(short_description=about)
            return True, "✅ تم تغيير النبذة"
        except TelegramError as e:
            return False, f"❌ {e}"

    @staticmethod
    async def set_photo(bot: Bot, photo_bytes: bytes) -> tuple[bool, str]:
        try:
            await bot.set_my_profile_photo(
                photo=InputFile(io.BytesIO(photo_bytes), filename="photo.jpg")
            )
            return True, "✅ تم تغيير الصورة"
        except TelegramError as e:
            return False, f"❌ {e}"
