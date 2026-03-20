"""
handlers/panel.py — لوحة التحكم الرئيسية وشاشة البداية
"""

from __future__ import annotations
from datetime import datetime

from telegram import Update
from telegram.ext import ContextTypes, ConversationHandler
from telegram.constants import ParseMode

from core.config import VERSION
from handlers.base import BaseHandler
from utils.keyboards import kb, btn


class PanelHandler(BaseHandler):

    # ══════════════════════════════════════════════════════
    #  /start
    # ══════════════════════════════════════════════════════
    async def cmd_start(self, update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        if not self.is_owner(update):
            await update.message.reply_text("⛔ هذا البوت خاص.")
            return
        bots = self.pm.bots
        run  = sum(1 for b in bots.values() if b.status == "running")
        text = (
            f"🤖 *BotForge v{VERSION}*\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"📦 البوتات: `{len(bots)}`   🟢 تعمل: `{run}`\n\n"
            "مدير البوتات الشخصي — استضف، راقب، وتحكم في بوتاتك بسهولة تامة.\n\n"
            "اختر ما تريد:"
        )
        keyboard = kb(
            [btn("🖥 لوحة التحكم",      "home"),
             btn("📋 البوتات",           "list")],
            [btn("➕ إضافة بوت",         "add"),
             btn("🔍 بحث وتصفية",        "search_menu")],
            [btn("📊 إحصائيات النظام",   "sys_stats"),
             btn("📅 الجدول الزمني",     "sched_list:all")],
            [btn("🔔 الإشعارات",         "notif_menu"),
             btn("⚙️ إعدادات BotForge", "self_ctrl")],
        )
        await update.message.reply_text(text, reply_markup=keyboard, parse_mode=ParseMode.MARKDOWN)

    # ══════════════════════════════════════════════════════
    #  /panel
    # ══════════════════════════════════════════════════════
    async def cmd_panel(self, update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        if not self.is_owner(update):
            return
        await self._show_home(update, edit=False)

    async def cmd_bots(self, update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        if not self.is_owner(update):
            return
        await self._show_list(update, edit=False)

    async def cmd_stats(self, update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        if not self.is_owner(update):
            return
        await self._show_stats(update, edit=False)

    # ══════════════════════════════════════════════════════
    #  Callback router (للـ panel فقط)
    # ══════════════════════════════════════════════════════
    async def on_cb(self, update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        if not self.is_owner(update):
            await update.callback_query.answer("⛔", show_alert=True)
            return
        q = update.callback_query
        await q.answer()
        d = q.data

        if d in ("home", "refresh_panel"):
            await self._show_home(update)
        elif d == "list":
            await self._show_list(update)
        elif d == "sys_stats":
            await self._show_stats(update)
        elif d == "start_all":
            n = 0
            for b in self.pm.bots.values():
                if b.status != "running":
                    ok, _ = self.pm.start(b.bot_id)
                    if ok:
                        n += 1
            await q.answer(f"✅ تم تشغيل {n} بوت", show_alert=True)
            await self._show_home(update)
        elif d == "stop_all":
            for b in list(self.pm.bots.values()):
                self.pm.stop(b.bot_id)
            await q.answer("⏹ تم إيقاف الكل", show_alert=True)
            await self._show_home(update)

    # ══════════════════════════════════════════════════════
    #  Home
    # ══════════════════════════════════════════════════════
    async def _show_home(self, update: Update, edit: bool = True):
        bots  = self.pm.bots
        total = len(bots)
        run   = sum(1 for b in bots.values() if b.status == "running")
        stop_ = sum(1 for b in bots.values() if b.status == "stopped")
        err   = sum(1 for b in bots.values() if b.status == "error")
        inst  = sum(1 for b in bots.values() if b.status == "installing")
        sys_s = self.pm.system_stats()
        text = (
            "╔══ 🖥 *BotForge Control Panel* ══╗\n\n"
            f"  📦 الكل: `{total}`\n"
            f"  🟢`{run}` 🔴`{stop_}` 🟠`{err}` 🔵`{inst}`\n\n"
            f"  🖥 CPU: `{sys_s['cpu']:.1f}%`\n"
            f"  🧠 RAM: `{sys_s['mem_used']}`/`{sys_s['mem_total']} GB` ({sys_s['mem_pct']}%)\n"
            f"  💿 Disk: `{sys_s['disk_used']}`/`{sys_s['disk_total']} GB`\n\n"
            f"  🕐 `{datetime.now().strftime('%Y-%m-%d  %H:%M:%S')}`\n"
            "╚══════════════════════════════╝"
        )
        keyboard = kb(
            [btn("📋 البوتات",         "list"),
             btn("➕ إضافة",           "add")],
            [btn("🔍 بحث",             "search_menu"),
             btn("📊 إحصائيات",        "sys_stats")],
            [btn("🟢 تشغيل الكل",     "start_all"),
             btn("🔴 إيقاف الكل",     "stop_all")],
            [btn("📅 الجدول",          "sched_list:all"),
             btn("🔔 الإشعارات",      "notif_menu")],
            [btn("⚙️ إعدادات BotForge","self_ctrl"),
             btn("🔄 تحديث",          "refresh_panel")],
        )
        await self.reply(update, text, keyboard, edit)

    # ══════════════════════════════════════════════════════
    #  Bot List
    # ══════════════════════════════════════════════════════
    async def _show_list(self, update: Update, edit: bool = True,
                         bots=None, title: str = "📋 *قائمة البوتات:*"):
        if bots is None:
            bots = list(self.pm.bots.values())
        if not bots:
            text = "📭 لا توجد بوتات بعد\\.\nأرسل ملفاً أو اضغط ➕"
            keyboard = kb(
                [btn("➕ إضافة بوت", "add"),
                 btn("↩️ رجوع",      "home")]
            )
            await self.reply(update, text, keyboard, edit, md=ParseMode.MARKDOWN_V2)
            return

        lines = [f"{title}\n"]
        rows  = []
        for b in bots:
            s  = self.pm.get_stats(b.bot_id)
            up = f"  ⏱`{b.uptime_str}`" if b.uptime_str else ""
            mb = f"  💾`{s.get('mem',0):.0f}MB`" if s.get("mem") else ""
            lines.append(f"{b.status_emoji} *{b.name}* `[{b.bot_id}]`{up}{mb}")
            rows.append([btn(f"{b.status_emoji} {b.name}  [{b.bot_id}]", f"info:{b.bot_id}")])

        rows.append([btn("🔍 بحث/تصفية", "search_menu"), btn("↩️ رجوع", "home")])
        await self.reply(update, "\n".join(lines), kb(*rows), edit)

    # ══════════════════════════════════════════════════════
    #  System Stats
    # ══════════════════════════════════════════════════════
    async def _show_stats(self, update: Update, edit: bool = True):
        s = self.pm.system_stats()
        text = (
            "📊 *إحصائيات النظام*\n\n"
            f"  🖥 CPU: `{s['cpu']:.1f}%`\n"
            f"  🧠 RAM: `{s['mem_used']:.2f}` / `{s['mem_total']:.2f} GB` ({s['mem_pct']}%)\n"
            f"  💿 Disk: `{s['disk_used']:.1f}` / `{s['disk_total']:.1f} GB` ({s['disk_pct']}%)\n"
            f"  ⏱ Uptime: `{s['uptime']}`\n\n"
            f"  🤖 إجمالي البوتات: `{s['bots_total']}`\n"
            f"  🟢 تعمل: `{s['bots_running']}`\n"
            f"  💾 إجمالي RAM البوتات: `{s['bots_mem']:.1f} MB`\n"
        )
        keyboard = kb(
            [btn("🔄 تحديث", "sys_stats"),
             btn("↩️ رجوع",  "home")]
        )
        await self.reply(update, text, keyboard, edit)

    # expose for other handlers
    async def show_list(self, update, edit=True, bots=None, title="📋 *قائمة البوتات:*"):
        await self._show_list(update, edit, bots, title)
