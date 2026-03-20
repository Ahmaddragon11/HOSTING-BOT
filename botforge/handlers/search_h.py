"""
handlers/search_h.py — بحث البوتات وتصفيتها
"""

from __future__ import annotations
import logging

from telegram import Update
from telegram.ext import ContextTypes
from telegram.constants import ParseMode

from handlers.base import BaseHandler
from utils.keyboards import kb, btn, status_filter_kb

logger = logging.getLogger("BotForge.Search")


class SearchHandler(BaseHandler):

    async def cmd_search(self, update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        if not self.is_owner(update):
            return
        query = " ".join(ctx.args) if ctx.args else ""
        if query:
            await self._do_search(update, query, edit=False)
        else:
            await self._show_search_menu(update, edit=False)

    async def on_cb(self, update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        if not self.is_owner(update):
            await update.callback_query.answer("⛔", show_alert=True)
            return
        q = update.callback_query
        await q.answer()
        d = q.data

        if d == "search_menu":
            await self._show_search_menu(update)

        elif d.startswith("filter_status:"):
            status = d.split(":", 1)[1]
            results = self.pm.search(status=status)
            await self._show_results(update, results, f"تصفية: {status}")

        elif d.startswith("search_result:"):
            # إعادة العرض
            query = d.split(":", 1)[1]
            await self._do_search(update, query)

    async def _show_search_menu(self, update: Update, edit: bool = True):
        text = "🔍 *بحث وتصفية البوتات*\n\n" "اختر طريقة البحث:"
        keyboard = kb(
            [
                btn("🟢 تعمل", "filter_status:running"),
                btn("🔴 متوقفة", "filter_status:stopped"),
            ],
            [
                btn("🟠 أخطاء", "filter_status:error"),
                btn("📦 الكل", "filter_status:all"),
            ],
            [btn("↩️ رجوع", "home")],
        )
        await self.reply(update, text, keyboard, edit)

    async def _do_search(self, update: Update, query: str, edit: bool = True):
        results = self.pm.search(query=query)
        await self._show_results(update, results, f'بحث: "{query}"', edit)

    async def _show_results(
        self, update: Update, results: list, label: str, edit: bool = True
    ):
        if not results:
            text = f"🔍 *{label}*\n\n📭 لا توجد نتائج"
            keyboard = kb([btn("↩️ رجوع", "search_menu"), btn("🏠 الرئيسية", "home")])
            await self.reply(update, text, keyboard, edit)
            return

        lines = [f"🔍 *{label}* — {len(results)} نتيجة:\n"]
        rows = []
        for b in results:
            s = self.pm.get_stats(b.bot_id)
            up = f"  ⏱`{b.uptime_str}`" if b.uptime_str else ""
            mb = f"  💾`{s.get('mem',0):.0f}MB`" if s.get("mem") else ""
            lines.append(f"{b.status_emoji} *{b.name}* `[{b.bot_id}]`{up}{mb}")
            rows.append([btn(f"{b.status_emoji} {b.name}", f"info:{b.bot_id}")])

        rows.append([btn("🔍 بحث جديد", "search_menu"), btn("↩️ رجوع", "list")])
        await self.reply(update, "\n".join(lines), kb(*rows), edit)
