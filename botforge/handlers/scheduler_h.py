"""
handlers/scheduler_h.py — واجهة جدولة المهام
"""

from __future__ import annotations
import logging
import re
from datetime import datetime, timedelta

from telegram import Update
from telegram.ext import ContextTypes, ConversationHandler
from telegram.constants import ParseMode

from core.config import (
    ST_SCHEDULE_BOT,
    ST_SCHEDULE_ACTION,
    ST_SCHEDULE_TIME,
)
from handlers.base import BaseHandler
from utils.keyboards import kb, btn

logger = logging.getLogger("BotForge.Scheduler")

_ACTIONS = {"start": "▶️ تشغيل", "stop": "⏹ إيقاف", "restart": "🔄 إعادة تشغيل"}


class SchedulerHandler(BaseHandler):
    def __init__(self, pm, scheduler):
        super().__init__(pm)
        self.sch = scheduler

    # ══════════════════════════════════════════════════════
    #  /schedule
    # ══════════════════════════════════════════════════════
    async def cmd_schedule(self, update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> int:
        if not self.is_owner(update):
            return ConversationHandler.END
        await self._pick_bot(update, edit=False)
        return ST_SCHEDULE_BOT

    async def start_schedule(
        self, update: Update, ctx: ContextTypes.DEFAULT_TYPE
    ) -> int:
        """يبدأ من زر sched_new:<bot_id>"""
        if not self.is_owner(update):
            return ConversationHandler.END
        q = update.callback_query
        await q.answer()
        bot_id = q.data.split(":", 1)[1]
        if bot_id == "new":
            await self._pick_bot(update)
            return ST_SCHEDULE_BOT
        # مباشرة لاختيار الإجراء
        self.sess(update.effective_user.id)["sched_bot"] = bot_id
        await self._pick_action(update, bot_id)
        return ST_SCHEDULE_ACTION

    async def pick_bot(self, update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> int:
        if not self.is_owner(update):
            return ConversationHandler.END
        q = update.callback_query
        await q.answer()
        bot_id = q.data.split(":", 1)[1]
        self.sess(update.effective_user.id)["sched_bot"] = bot_id
        await self._pick_action(update, bot_id)
        return ST_SCHEDULE_ACTION

    async def pick_action(self, update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> int:
        if not self.is_owner(update):
            return ConversationHandler.END
        q = update.callback_query
        await q.answer()
        action = q.data.split(":", 1)[1]
        self.sess(update.effective_user.id)["sched_action"] = action
        await self._pick_time(update)
        return ST_SCHEDULE_TIME

    async def get_time(self, update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> int:
        if not self.is_owner(update):
            return ConversationHandler.END
        uid = update.effective_user.id
        s = self.sess(uid)
        bot_id = s.get("sched_bot", "")
        action = s.get("sched_action", "start")
        text = (update.message.text or "").strip()
        bot = self.pm.bots.get(bot_id)

        jid, msg = self._parse_and_add(bot_id, action, text)
        self.sess_clear(uid)

        if jid:
            nxt = self.sch.next_run(jid)
            name = bot.name if bot else bot_id
            reply = (
                f"✅ *تم إنشاء المهمة المجدولة*\n\n"
                f"  🤖 البوت: *{name}*\n"
                f"  ⚡ الإجراء: `{_ACTIONS.get(action, action)}`\n"
                f"  📅 الجدول: `{text}`\n"
                f"  🕐 التشغيل القادم: `{nxt}`\n"
                f"  🆔 ID: `{jid}`"
            )
        else:
            reply = f"❌ {msg}"

        keyboard = kb(
            [btn("📅 الجدول الزمني", "sched_list:all"), btn("🏠 الرئيسية", "home")]
        )
        await update.message.reply_text(
            reply, reply_markup=keyboard, parse_mode=ParseMode.MARKDOWN
        )
        return ConversationHandler.END

    # ══════════════════════════════════════════════════════
    #  Callback router
    # ══════════════════════════════════════════════════════
    async def on_cb(self, update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        if not self.is_owner(update):
            await update.callback_query.answer("⛔", show_alert=True)
            return
        q = update.callback_query
        await q.answer()
        d = q.data

        if d.startswith("sched_list:"):
            scope = d.split(":", 1)[1]
            await self._show_list(update, scope)

        elif d.startswith("sched_menu:"):
            bot_id = d.split(":", 1)[1]
            await self._show_bot_schedule(update, bot_id)

        elif d.startswith("sched_del:"):
            jid = d.split(":", 1)[1]
            ok = self.sch.remove(jid)
            await q.answer(
                "✅ تم الحذف" if ok else "❌ المهمة غير موجودة", show_alert=True
            )
            await self._show_list(update, "all")

    # ══════════════════════════════════════════════════════
    #  Helpers
    # ══════════════════════════════════════════════════════
    async def _pick_bot(self, update: Update, edit: bool = True):
        bots = list(self.pm.bots.values())
        if not bots:
            text = "📭 لا توجد بوتات — أضف بوتاً أولاً"
            await self.reply(update, text, kb([btn("↩️ رجوع", "home")]), edit)
            return
        rows = [[btn(f"{b.status_emoji} {b.name}", f"spick:{b.bot_id}")] for b in bots]
        rows.append([btn("❌ إلغاء", "home")])
        await self.reply(
            update, "📅 *جدولة مهمة جديدة*\n\nاختر البوت:", kb(*rows), edit
        )

    async def _pick_action(self, update: Update, bot_id: str):
        bot = self.pm.bots.get(bot_id)
        name = bot.name if bot else bot_id
        keyboard = kb(
            [
                btn("▶️ تشغيل", f"sact:start"),
                btn("⏹ إيقاف", f"sact:stop"),
                btn("🔄 إعادة تشغيل", f"sact:restart"),
            ],
            [btn("❌ إلغاء", "home")],
        )
        await self.reply(
            update,
            f"📅 *جدولة — {name}*\n\nاختر الإجراء:",
            keyboard,
        )

    async def _pick_time(self, update: Update):
        text = (
            "🕐 *أدخل توقيت الجدول*\n\n"
            "الصيغ المدعومة:\n"
            "• `08:30` — يومياً الساعة 8:30 صباحاً\n"
            "• `08:30 fri` — كل جمعة 8:30 ص\n"
            "• `every 2h` — كل ساعتين\n"
            "• `every 30m` — كل 30 دقيقة\n"
            "• `once 2024-12-31 23:59` — مرة واحدة\n\n"
            "/cancel للإلغاء"
        )
        await self.reply(update, text, None)

    def _parse_and_add(self, bot_id: str, action: str, text: str) -> tuple[str, str]:
        """يحلل النص ويضيف المهمة المجدولة"""
        text = text.strip()
        try:
            # every Xh / every Xm
            m = re.match(r"every\s+(\d+)h(?:\s+(\d+)m)?", text, re.I)
            if m:
                h = int(m.group(1))
                mn = int(m.group(2) or 0)
                jid = self.sch.add_interval(bot_id, action, hours=h, minutes=mn)
                return jid, ""

            m = re.match(r"every\s+(\d+)m", text, re.I)
            if m:
                jid = self.sch.add_interval(bot_id, action, minutes=int(m.group(1)))
                return jid, ""

            # once YYYY-MM-DD HH:MM
            m = re.match(r"once\s+(\d{4}-\d{2}-\d{2})\s+(\d{2}:\d{2})", text, re.I)
            if m:
                dt = datetime.fromisoformat(f"{m.group(1)}T{m.group(2)}:00")
                if dt < datetime.now():
                    return "", "الوقت المحدد في الماضي!"
                jid = self.sch.add_once(bot_id, action, dt)
                return jid, ""

            # HH:MM [day]
            m = re.match(r"(\d{1,2}):(\d{2})(?:\s+(\w+))?", text)
            if m:
                h = m.group(1)
                mn = m.group(2)
                dow = m.group(3) or "*"
                # تحويل الأيام العربية
                day_map = {
                    "الاثنين": "mon",
                    "الثلاثاء": "tue",
                    "الأربعاء": "wed",
                    "الخميس": "thu",
                    "الجمعة": "fri",
                    "السبت": "sat",
                    "الأحد": "sun",
                }
                dow = day_map.get(dow, dow)
                jid = self.sch.add_cron(bot_id, action, h, mn, dow)
                return jid, ""

            return "", "صيغة غير معروفة — راجع الأمثلة أعلاه"
        except Exception as e:
            return "", str(e)

    async def _show_list(self, update: Update, scope: str):
        if scope == "all":
            jobs = self.sch.list_all()
            title = "📅 *جميع المهام المجدولة:*"
        else:
            jobs = self.sch.list_for_bot(scope)
            bot = self.pm.bots.get(scope)
            title = f"📅 *مهام {bot.name if bot else scope}:*"

        if not jobs:
            text = f"{title}\n\n📭 لا توجد مهام مجدولة"
            keyboard = kb(
                [btn("➕ جدولة جديدة", "sched_new:new"), btn("↩️ رجوع", "home")]
            )
            await self.reply(update, text, keyboard)
            return

        lines = [f"{title}\n"]
        rows = []
        for j in jobs:
            jid = j["jid"]
            line = self.sch.format_job(jid, j)
            lines.append(line)
            rows.append([btn(f"🗑 حذف `{jid[:6]}`", f"sched_del:{jid}")])

        rows.append([btn("➕ جدولة جديدة", "sched_new:new"), btn("↩️ رجوع", "home")])
        await self.reply(update, "\n".join(lines), kb(*rows))

    async def _show_bot_schedule(self, update: Update, bot_id: str):
        bot = self.pm.bots.get(bot_id)
        name = bot.name if bot else bot_id
        jobs = self.sch.list_for_bot(bot_id)
        lines = [f"📅 *مهام البوت: {name}*\n"]
        rows = []
        for j in jobs:
            jid = j["jid"]
            lines.append(self.sch.format_job(jid, j))
            rows.append([btn(f"🗑 {jid[:6]}", f"sched_del:{jid}")])
        rows.append(
            [
                btn("➕ إضافة مهمة", f"sched_new:{bot_id}"),
                btn("↩️ رجوع", f"info:{bot_id}"),
            ]
        )
        if not jobs:
            lines.append("📭 لا توجد مهام مجدولة لهذا البوت")
        await self.reply(update, "\n".join(lines), kb(*rows))
