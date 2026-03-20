"""
core/notifier.py — نظام الإشعارات المخصصة
"""

from __future__ import annotations
import json
import asyncio
import logging
from datetime import datetime
from typing import TYPE_CHECKING

from core.config import NOTIF_FILE, DEFAULT_NOTIF_SETTINGS, BOTFORGE_OWNER
from core.models import BotInstance

if TYPE_CHECKING:
    from telegram.ext import Application

logger = logging.getLogger("BotForge.Notifier")


class Notifier:
    """يرسل إشعارات للمالك عن أحداث البوتات"""

    def __init__(self, owner_id: int):
        self.owner_id = owner_id
        self._app: "Application | None" = None
        self._settings = self._load_settings()
        self._queue: list[tuple[str, BotInstance, str]] = []

    def set_app(self, app: "Application"):
        self._app = app

    # ══════════════════════════════════════════════════════
    #  Settings
    # ══════════════════════════════════════════════════════
    def _load_settings(self) -> dict:
        if NOTIF_FILE.exists():
            try:
                return json.loads(NOTIF_FILE.read_text("utf-8"))
            except Exception:
                pass
        return dict(DEFAULT_NOTIF_SETTINGS)

    def save_settings(self):
        try:
            NOTIF_FILE.write_text(
                json.dumps(self._settings, indent=2, ensure_ascii=False),
                encoding="utf-8",
            )
        except Exception as e:
            logger.error(f"خطأ حفظ إعدادات الإشعارات: {e}")

    def toggle(self, key: str) -> bool:
        if key in self._settings:
            self._settings[key] = not self._settings[key]
            self.save_settings()
            return self._settings[key]
        return False

    def is_enabled(self, event: str) -> bool:
        return self._settings.get(f"on_{event}", False)

    def get_settings(self) -> dict:
        return dict(self._settings)

    # ══════════════════════════════════════════════════════
    #  Send
    # ══════════════════════════════════════════════════════
    _ICONS = {
        "start":   "🟢",
        "stop":    "🔴",
        "error":   "🟠",
        "crash":   "💥",
        "update":  "🔄",
        "install": "📦",
    }

    _LABELS = {
        "start":   "بدأ التشغيل",
        "stop":    "أُوقف",
        "error":   "خطأ",
        "crash":   "انهار فجأة",
        "update":  "تم التحديث",
        "install": "تم التثبيت",
    }

    def queue(self, event: str, bot: BotInstance, extra: str = ""):
        """يضيف إشعاراً للإرسال (thread-safe)"""
        if not self.is_enabled(event):
            return
        self._queue.append((event, bot, extra))
        if self._app:
            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    loop.create_task(self._flush())
            except Exception:
                pass

    async def _flush(self):
        if not self._app or not self._queue:
            return
        items = list(self._queue)
        self._queue.clear()
        for event, bot, extra in items:
            await self._send(event, bot, extra)

    async def _send(self, event: str, bot: BotInstance, extra: str = ""):
        if not self._app:
            return
        icon  = self._ICONS.get(event, "ℹ️")
        label = self._LABELS.get(event, event)
        text  = (
            f"{icon} *إشعار BotForge*\n\n"
            f"  🤖 البوت: *{bot.name}* `[{bot.bot_id}]`\n"
            f"  📌 الحدث: `{label}`\n"
            f"  🕐 الوقت: `{datetime.now().strftime('%H:%M:%S')}`\n"
        )
        if extra:
            text += f"  ℹ️ تفاصيل: `{extra}`\n"
        try:
            await self._app.bot.send_message(
                chat_id=self.owner_id,
                text=text,
                parse_mode="Markdown",
            )
        except Exception as e:
            logger.debug(f"فشل إرسال الإشعار: {e}")

    async def send_custom(self, text: str):
        if not self._app:
            return
        try:
            await self._app.bot.send_message(
                chat_id=self.owner_id,
                text=text,
                parse_mode="Markdown",
            )
        except Exception as e:
            logger.debug(f"فشل إرسال رسالة مخصصة: {e}")
