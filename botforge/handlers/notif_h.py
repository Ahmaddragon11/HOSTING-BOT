"""
handlers/notif_h.py — إعدادات الإشعارات
"""

from __future__ import annotations
import logging

from telegram import Update
from telegram.ext import ContextTypes
from telegram.constants import ParseMode

from handlers.base import BaseHandler
from utils.keyboards import kb, btn

logger = logging.getLogger("BotForge.Notif")


_NOTIF_LABELS = {
    "on_start": "🟢 عند التشغيل",
    "on_stop": "🔴 عند الإيقاف",
    "on_error": "🟠 عند الخطأ",
    "on_crash": "💥 عند الانهيار",
    "on_update": "🔄 عند التحديث",
    "on_install": "📦 عند التثبيت",
}


class NotifHandler(BaseHandler):
    def __init__(self, notifier):
        super().__init__(None)  # لا يحتاج pm
        self.notifier = notifier

    async def on_cb(self, update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        if not self.is_owner(update):
            await update.callback_query.answer("⛔", show_alert=True)
            return
        q = update.callback_query
        await q.answer()
        d = q.data

        if d == "notif_menu":
            await self._show_menu(update)

        elif d.startswith("notif_toggle:"):
            key = d.split(":", 1)[1]
            new_v = self.notifier.toggle(key)
            label = _NOTIF_LABELS.get(key, key)
            status = "✅ مفعّل" if new_v else "❌ معطّل"
            await q.answer(f"{label}: {status}", show_alert=True)
            await self._show_menu(update)

    async def _show_menu(self, update: Update):
        settings = self.notifier.get_settings()
        lines = ["🔔 *إعدادات الإشعارات*\n"]
        rows = []
        for key, label in _NOTIF_LABELS.items():
            enabled = settings.get(key, False)
            icon = "✅" if enabled else "❌"
            lines.append(f"  {icon} {label}")
            rows.append(
                [
                    btn(
                        f"{'🔕 تعطيل' if enabled else '🔔 تفعيل'} {label}",
                        f"notif_toggle:{key}",
                    )
                ]
            )

        rows.append([btn("↩️ رجوع", "home")])
        await self.reply(update, "\n".join(lines), kb(*rows))
