"""
handlers/bot_mgr.py — إدارة دورة حياة البوتات (إضافة، تشغيل، إيقاف، تحديث، حذف)
"""

from __future__ import annotations
import asyncio
import hashlib
import time
import logging
from datetime import datetime

from telegram import Update
from telegram.ext import ContextTypes, ConversationHandler
from telegram.constants import ParseMode
from telegram.error import BadRequest

from core.config import (
    ST_FILE, ST_NAME, ST_TOKEN, ST_UPDATE_FILE,
    TMP_DIR,
)
from core.models import BotInstance
from handlers.base import BaseHandler
from utils.keyboards import kb, btn
from utils.extractor import Extractor
from utils.bot_controller import BotController

logger = logging.getLogger("BotForge.BotMgr")


def _gen_id(name: str) -> str:
    return hashlib.md5(f"{name}{time.time()}".encode()).hexdigest()[:8]


class BotManager(BaseHandler):

    # ══════════════════════════════════════════════════════
    #  /add conversation
    # ══════════════════════════════════════════════════════
    async def cmd_add(self, update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> int:
        if not self.is_owner(update):
            return ConversationHandler.END
        self.sess_clear(update.effective_user.id)
        await update.message.reply_text(
            "➕ *إضافة بوت جديد*\n\n"
            "أرسل ملف البوت:\n"
            "• `.zip` / `.tar.gz` — مجلد مضغوط\n"
            "• `.py` — ملف Python مفرد\n\n"
            "/cancel للإلغاء",
            parse_mode=ParseMode.MARKDOWN,
        )
        return ST_FILE

    async def conv_file(self, update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> int:
        if not self.is_owner(update):
            return ConversationHandler.END
        doc = update.message.document
        if not doc or not Extractor.is_allowed(doc.file_name):
            await update.message.reply_text("⚠️ أرسل .zip أو .tar.gz أو .py فقط")
            return ST_FILE
        msg  = await update.message.reply_text("⏳ جاري تحميل الملف...")
        uid  = update.effective_user.id
        tmp  = TMP_DIR / f"{uid}_{doc.file_name}"
        tgf  = await ctx.bot.get_file(doc.file_id)
        await tgf.download_to_drive(tmp)
        s = self.sess(uid)
        s["file"] = tmp
        s["orig"] = doc.file_name
        await msg.edit_text(
            "✅ تم التحميل!\n\n📝 *أدخل اسماً للبوت:*",
            parse_mode=ParseMode.MARKDOWN,
        )
        return ST_NAME

    async def conv_name(self, update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> int:
        if not self.is_owner(update):
            return ConversationHandler.END
        name = (update.message.text or "").strip()
        if not 1 <= len(name) <= 64:
            await update.message.reply_text("⚠️ الاسم يجب أن يكون 1–64 حرف")
            return ST_NAME
        self.sess(update.effective_user.id)["name"] = name
        keyboard = kb([btn("⏭ تخطي (بدون توكن)", "skip_token")])
        await update.message.reply_text(
            "🔑 *أدخل توكن البوت* (BOT\\_TOKEN):\n"
            "_سيُمرَّر تلقائياً عند التشغيل_\n\n"
            "أو اضغط **تخطي** إذا كان التوكن في ملف `.env`",
            reply_markup=keyboard,
            parse_mode=ParseMode.MARKDOWN,
        )
        return ST_TOKEN

    async def conv_token(self, update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> int:
        if not self.is_owner(update):
            return ConversationHandler.END
        self.sess(update.effective_user.id)["token"] = (update.message.text or "").strip()
        try:
            await update.message.delete()
        except Exception:
            pass
        return await self._finalize_add(update, ctx)

    async def conv_skip_token(self, update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> int:
        await update.callback_query.answer()
        self.sess(update.effective_user.id)["token"] = ""
        return await self._finalize_add(update, ctx, from_cb=True)

    async def _finalize_add(
        self, update: Update, ctx: ContextTypes.DEFAULT_TYPE, from_cb: bool = False
    ) -> int:
        uid   = update.effective_user.id
        s     = self.sess(uid)
        name  = s.get("name", "MyBot")
        token = s.get("token", "")
        fp    = s.get("file")

        target = update.message or (update.callback_query and update.callback_query.message)
        msg = await target.reply_text(
            "⚙️ *جاري الإعداد…*\n\n📦 استخراج الملفات…",
            parse_mode=ParseMode.MARKDOWN,
        )

        from core.config import BOTS_DIR
        bot_id = _gen_id(name)
        dest   = BOTS_DIR / bot_id
        ok, err = Extractor.extract(fp, dest)
        if not ok:
            await msg.edit_text(f"❌ فشل الاستخراج: {err}")
            self.sess_clear(uid)
            return ConversationHandler.END

        b           = BotInstance(bot_id, name, dest, token)
        b.main_file = self.pm.find_main(b)

        if token:
            info = await BotController.get_info(token)
            b.username = info.get("username", "")

        self.pm.add(b)

        await msg.edit_text(
            "⚙️ *جاري الإعداد…*\n\n"
            "📦 استخراج ✅\n"
            "🔧 إعداد البيئة الافتراضية وتثبيت المتطلبات…\n"
            "_قد يستغرق هذا دقيقة…_",
            parse_mode=ParseMode.MARKDOWN,
        )

        loop = asyncio.get_event_loop()
        setup_ok, setup_msg = await loop.run_in_executor(None, self.pm.setup_env, b)

        if fp and fp.exists():
            fp.unlink(missing_ok=True)
        self.sess_clear(uid)

        result = (
            f"{'✅' if setup_ok else '⚠️'} *تمت إضافة البوت!*\n\n"
            f"  📛 الاسم: `{name}`\n"
            f"  🆔 ID: `{bot_id}`\n"
        )
        if b.username:
            result += f"  🤖 يوزر: `@{b.username}`\n"
        result += (
            f"  📄 الملف: `{b.main_file or 'غير محدد'}`\n"
            f"  🔧 الإعداد: {setup_msg}\n"
        )

        rows = [
            [btn("▶️ تشغيل الآن", f"start:{bot_id}"),
             btn("📋 معلومات",    f"info:{bot_id}")],
        ]
        if b.username:
            rows.append([btn(f"↗️ فتح @{b.username}", url=f"https://t.me/{b.username}")])

        await msg.edit_text(result, reply_markup=kb(*rows), parse_mode=ParseMode.MARKDOWN)
        return ConversationHandler.END

    # ══════════════════════════════════════════════════════
    #  Update bot code
    # ══════════════════════════════════════════════════════
    async def start_update(self, update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> int:
        if not self.is_owner(update):
            return ConversationHandler.END
        bot_id = update.callback_query.data.split(":", 1)[1]
        bot    = self.pm.bots.get(bot_id)
        if not bot:
            await update.callback_query.answer("البوت غير موجود", show_alert=True)
            return ConversationHandler.END
        await update.callback_query.answer()
        self.sess(update.effective_user.id)["update_target"] = bot_id
        await update.callback_query.edit_message_text(
            f"🔄 *تحديث كود البوت: {bot.name}*\n\n"
            "أرسل الملف الجديد (.zip / .tar.gz / .py)\n"
            "_ملاحظة: سيتم الحفاظ على ملف `.env` والبيئة الافتراضية_\n\n"
            "/cancel للإلغاء",
            parse_mode=ParseMode.MARKDOWN,
        )
        return ST_UPDATE_FILE

    async def recv_update_file(self, update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> int:
        if not self.is_owner(update):
            return ConversationHandler.END
        doc = update.message.document
        if not doc or not Extractor.is_allowed(doc.file_name):
            await update.message.reply_text("⚠️ أرسل .zip أو .tar.gz أو .py")
            return ST_UPDATE_FILE

        uid    = update.effective_user.id
        bot_id = self.sess(uid).get("update_target")
        bot    = self.pm.bots.get(bot_id) if bot_id else None
        if not bot:
            await update.message.reply_text("❌ لم يُعثر على البوت")
            self.sess_clear(uid)
            return ConversationHandler.END

        msg = await update.message.reply_text("⏳ جاري تحميل الملف الجديد...")
        tmp = TMP_DIR / f"{uid}_update_{doc.file_name}"
        tgf = await ctx.bot.get_file(doc.file_id)
        await tgf.download_to_drive(tmp)

        await msg.edit_text("🔄 جاري تطبيق التحديث…")
        loop = asyncio.get_event_loop()
        ok, result_msg = await loop.run_in_executor(
            None, self.pm.update_code, bot, tmp
        )
        tmp.unlink(missing_ok=True)
        self.sess_clear(uid)

        keyboard = kb([btn("📋 معلومات البوت", f"info:{bot_id}"), btn("🏠 الرئيسية", "home")])
        await msg.edit_text(result_msg, reply_markup=keyboard, parse_mode=ParseMode.MARKDOWN)
        return ConversationHandler.END

    # ══════════════════════════════════════════════════════
    #  Cancel
    # ══════════════════════════════════════════════════════
    async def cmd_cancel(self, update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> int:
        self.sess_clear(update.effective_user.id)
        await update.message.reply_text(
            "❌ تم الإلغاء.",
            reply_markup=kb([btn("🏠 الرئيسية", "home")]),
        )
        return ConversationHandler.END

    # ══════════════════════════════════════════════════════
    #  Callback router
    # ══════════════════════════════════════════════════════
    async def on_cb(self, update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        if not self.is_owner(update):
            await update.callback_query.answer("⛔", show_alert=True)
            return
        q  = update.callback_query
        d  = q.data
        await q.answer()

        if d == "add":
            self.sess_clear(update.effective_user.id)
            await q.edit_message_text(
                "📤 *إضافة بوت جديد*\n\nأرسل الملف:\n• `.zip` / `.tar.gz`\n• `.py`\n\n/cancel للإلغاء",
                parse_mode=ParseMode.MARKDOWN,
            )
            return

        action, bot_id = d.split(":", 1)

        if action == "info":
            await self._show_info(update, bot_id)
        elif action == "start":
            ok, msg = self.pm.start(bot_id)
            await q.answer(msg, show_alert=not ok)
            await self._show_info(update, bot_id)
        elif action == "stop":
            ok, msg = self.pm.stop(bot_id)
            await q.answer(msg, show_alert=not ok)
            await self._show_info(update, bot_id)
        elif action == "restart":
            await q.edit_message_text("🔄 جاري إعادة التشغيل…")
            ok, msg = self.pm.restart(bot_id)
            await q.answer(msg, show_alert=not ok)
            await self._show_info(update, bot_id)
        elif action == "logs":
            await self._show_logs(update, bot_id)
        elif action == "clear_logs":
            self.pm.clear_logs(bot_id)
            await q.answer("✅ تم مسح السجلات", show_alert=True)
            await self._show_info(update, bot_id)
        elif action == "bstats":
            await self._show_bstats(update, bot_id)
        elif action == "toggle_ar":
            bot = self.pm.bots.get(bot_id)
            if bot:
                bot.auto_restart = not bot.auto_restart
                self.pm.save()
                lbl = "✅ مفعّل" if bot.auto_restart else "❌ معطّل"
                await q.answer(f"إعادة تشغيل تلقائي: {lbl}", show_alert=True)
            await self._show_info(update, bot_id)
        elif action == "del_confirm":
            bot  = self.pm.bots.get(bot_id)
            name = bot.name if bot else bot_id
            keyboard = kb([
                btn("✅ نعم، احذف!", f"del_do:{bot_id}"),
                btn("❌ إلغاء",      f"info:{bot_id}"),
            ])
            await q.edit_message_text(
                f"⚠️ *تأكيد الحذف*\n\n"
                f"هل أنت متأكد من حذف *{name}*؟\n"
                "_سيتم حذف جميع الملفات نهائياً!_",
                reply_markup=keyboard,
                parse_mode=ParseMode.MARKDOWN,
            )
        elif action == "del_do":
            bot  = self.pm.bots.get(bot_id)
            name = bot.name if bot else bot_id
            self.pm.remove(bot_id)
            await q.answer(f"✅ تم حذف {name}", show_alert=True)
            await self._show_list_cb(update)
        elif action == "reinstall":
            bot = self.pm.bots.get(bot_id)
            if not bot:
                await q.answer("غير موجود", show_alert=True); return
            await q.edit_message_text("🔧 جاري إعادة تثبيت البيئة…")
            loop = asyncio.get_event_loop()
            ok, msg = await loop.run_in_executor(None, self.pm.reinstall_env, bot)
            await q.answer(msg, show_alert=True)
            await self._show_info(update, bot_id)

    # ══════════════════════════════════════════════════════
    #  Info card
    # ══════════════════════════════════════════════════════
    async def _show_info(self, update: Update, bot_id: str):
        bot = self.pm.bots.get(bot_id)
        if not bot:
            if update.callback_query:
                await update.callback_query.answer("البوت غير موجود!", show_alert=True)
            return
        s   = self.pm.get_stats(bot_id)
        e   = bot.status_emoji
        ar  = "✅" if bot.auto_restart else "❌"
        un  = f"@{bot.username}" if bot.username else "—"
        cr  = bot.created_at[:10]
        lu  = bot.last_updated[:10]
        text = (
            f"╔══ {e} *{bot.name}* ══╗\n\n"
            f"  🆔 ID: `{bot.bot_id}`\n"
            f"  🤖 يوزر: `{un}`\n"
            f"  📄 ملف: `{bot.main_file or 'غير محدد'}`\n"
            f"  ⚡ الحالة: `{bot.status}`\n"
            f"  🔄 تلقائي: {ar}   🔁 إعادات: `{bot.restarts}`\n"
            f"  📅 أُضيف: `{cr}`   🔧 آخر تحديث: `{lu}`\n"
        )
        if s.get("uptime"):  text += f"  ⏱ وقت التشغيل: `{s['uptime']}`\n"
        if s.get("pid"):     text += f"  🔧 PID: `{s['pid']}`\n"
        if s.get("mem"):     text += f"  💾 RAM: `{s['mem']:.1f} MB`\n"
        if s.get("cpu"):     text += f"  🖥 CPU: `{s['cpu']:.1f}%`\n"
        if bot.env_vars:     text += f"  🔑 متغيرات البيئة: `{len(bot.env_vars)}`\n"
        if bot.description:  text += f"  📝 الوصف: `{bot.description[:40]}`\n"
        text += "╚═══════════════════════╝"

        is_run = bot.status == "running"
        rows = [
            [btn("⏹ إيقاف" if is_run else "▶️ تشغيل",
                 f"{'stop' if is_run else 'start'}:{bot_id}"),
             btn("🔄 إعادة تشغيل", f"restart:{bot_id}")],
            [btn("📋 السجلات",     f"logs:{bot_id}"),
             btn("📊 إحصائيات",   f"bstats:{bot_id}")],
            [btn("🛠 إعدادات البوت", f"bot_ctrl:{bot_id}"),
             btn("🔑 متغيرات البيئة", f"env_menu:{bot_id}")],
            [btn("🔄 تحديث الكود", f"update:{bot_id}"),
             btn("📅 الجدولة",    f"sched_menu:{bot_id}")],
            [btn(f"{'❌' if bot.auto_restart else '✅'} تلقائي",
                 f"toggle_ar:{bot_id}"),
             btn("🔧 إعادة تثبيت", f"reinstall:{bot_id}")],
        ]
        if bot.username:
            rows.append([btn(f"↗️ فتح @{bot.username}", url=f"https://t.me/{bot.username}")])
        rows.append([btn("🗑 حذف", f"del_confirm:{bot_id}"), btn("↩️ القائمة", "list")])

        if update.callback_query:
            try:
                await update.callback_query.edit_message_text(
                    text, reply_markup=kb(*rows), parse_mode=ParseMode.MARKDOWN
                )
            except BadRequest:
                await update.callback_query.message.reply_text(
                    text, reply_markup=kb(*rows), parse_mode=ParseMode.MARKDOWN
                )
        else:
            await update.message.reply_text(
                text, reply_markup=kb(*rows), parse_mode=ParseMode.MARKDOWN
            )

    async def _show_list_cb(self, update: Update):
        """إعادة عرض قائمة البوتات"""
        bots = list(self.pm.bots.values())
        if not bots:
            await update.callback_query.edit_message_text(
                "📭 لا توجد بوتات.",
                reply_markup=kb([btn("➕ إضافة", "add"), btn("↩️ رجوع", "home")]),
            )
            return
        lines = ["📋 *قائمة البوتات:*\n"]
        rows  = []
        for b in bots:
            s  = self.pm.get_stats(b.bot_id)
            up = f"  ⏱`{b.uptime_str}`" if b.uptime_str else ""
            mb = f"  💾`{s.get('mem',0):.0f}MB`" if s.get("mem") else ""
            lines.append(f"{b.status_emoji} *{b.name}* `[{b.bot_id}]`{up}{mb}")
            rows.append([btn(f"{b.status_emoji} {b.name}  [{b.bot_id}]", f"info:{b.bot_id}")])
        rows.append([btn("↩️ رجوع", "home")])
        await update.callback_query.edit_message_text(
            "\n".join(lines), reply_markup=kb(*rows), parse_mode=ParseMode.MARKDOWN
        )

    # ══════════════════════════════════════════════════════
    #  Logs viewer
    # ══════════════════════════════════════════════════════
    async def _show_logs(self, update: Update, bot_id: str,
                          search: str = "", lines: int = 40):
        bot  = self.pm.bots.get(bot_id)
        name = bot.name if bot else bot_id
        raw  = self.pm.get_logs(bot_id, n=lines, search=search)
        safe = (raw[-3500:] or "لا توجد سجلات").replace("`", "'")
        lbl  = f" (بحث: {search})" if search else ""
        text = f"📋 *سجلات {name}*{lbl}:\n\n```\n{safe}\n```"
        keyboard = kb(
            [btn("🔄 تحديث",   f"logs:{bot_id}"),
             btn("🗑 مسح",      f"clear_logs:{bot_id}"),
             btn("📥 تحميل",   f"dl_log:{bot_id}")],
            [btn("↩️ رجوع",   f"info:{bot_id}")],
        )
        try:
            await update.callback_query.edit_message_text(
                text, reply_markup=keyboard, parse_mode=ParseMode.MARKDOWN
            )
        except BadRequest:
            await update.callback_query.edit_message_text(
                f"📋 سجلات {name}:\n{raw[-3000:] or 'لا توجد'}",
                reply_markup=keyboard,
            )

    # ══════════════════════════════════════════════════════
    #  Bot stats
    # ══════════════════════════════════════════════════════
    async def _show_bstats(self, update: Update, bot_id: str):
        bot = self.pm.bots.get(bot_id)
        s   = self.pm.get_stats(bot_id)
        e   = bot.status_emoji if bot else "⚪"
        text = (
            f"📊 *إحصائيات {bot.name if bot else bot_id}*\n\n"
            f"  {e} الحالة: `{s.get('status','—')}`\n"
            f"  🔧 PID: `{s.get('pid') or 'N/A'}`\n"
            f"  ⏱ وقت التشغيل: `{s.get('uptime') or 'N/A'}`\n"
            f"  🖥 CPU: `{s.get('cpu',0):.1f}%`\n"
            f"  💾 RAM: `{s.get('mem',0):.1f} MB`\n"
            f"  🔁 إعادات التشغيل: `{s.get('restarts',0)}`\n"
        )
        keyboard = kb(
            [btn("🔄 تحديث", f"bstats:{bot_id}"),
             btn("↩️ رجوع",  f"info:{bot_id}")]
        )
        await update.callback_query.edit_message_text(
            text, reply_markup=keyboard, parse_mode=ParseMode.MARKDOWN
        )

    # ══════════════════════════════════════════════════════
    #  Direct commands
    # ══════════════════════════════════════════════════════
    async def cmd_logs(self, update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        if not self.is_owner(update) or not ctx.args:
            await update.message.reply_text("الاستخدام: /logs <bot_id> [بحث]")
            return
        bot_id = ctx.args[0]
        search = " ".join(ctx.args[1:]) if len(ctx.args) > 1 else ""
        raw    = self.pm.get_logs(bot_id, 50, search)
        bot    = self.pm.bots.get(bot_id)
        name   = bot.name if bot else bot_id
        safe   = (raw[-4000:] or "لا توجد").replace("`", "'")
        try:
            await update.message.reply_text(
                f"📋 *سجلات {name}*:\n\n```\n{safe}\n```",
                parse_mode=ParseMode.MARKDOWN,
            )
        except Exception:
            await update.message.reply_text(f"سجلات {name}:\n{raw[-3000:] or 'لا توجد'}")

    async def cmd_start_bot(self, update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        if not self.is_owner(update) or not ctx.args:
            await update.message.reply_text("الاستخدام: /start_bot <id>")
            return
        ok, msg = self.pm.start(ctx.args[0])
        await update.message.reply_text(f"{'✅' if ok else '❌'} {msg}")

    async def cmd_stop_bot(self, update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        if not self.is_owner(update) or not ctx.args:
            await update.message.reply_text("الاستخدام: /stop_bot <id>")
            return
        ok, msg = self.pm.stop(ctx.args[0])
        await update.message.reply_text(f"{'⏹' if ok else '❌'} {msg}")

    async def cmd_restart_bot(self, update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        if not self.is_owner(update) or not ctx.args:
            await update.message.reply_text("الاستخدام: /restart <id>")
            return
        ok, msg = self.pm.restart(ctx.args[0])
        await update.message.reply_text(f"{'✅' if ok else '❌'} {msg}")

    async def cmd_delete(self, update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        if not self.is_owner(update) or not ctx.args:
            await update.message.reply_text("الاستخدام: /delete <id>")
            return
        bot_id = ctx.args[0]
        bot    = self.pm.bots.get(bot_id)
        if not bot:
            await update.message.reply_text("❌ البوت غير موجود")
            return
        keyboard = kb([
            btn("✅ نعم احذف!", f"del_do:{bot_id}"),
            btn("❌ إلغاء",     f"info:{bot_id}"),
        ])
        await update.message.reply_text(
            f"⚠️ تأكيد حذف *{bot.name}*؟",
            reply_markup=keyboard,
            parse_mode=ParseMode.MARKDOWN,
        )
