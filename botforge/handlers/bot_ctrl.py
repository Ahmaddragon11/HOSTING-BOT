"""
handlers/bot_ctrl.py — التحكم في هوية البوتات (اسم، وصف، نبذة، صورة)
"""

from __future__ import annotations
import logging

from telegram import Update
from telegram.ext import ContextTypes, ConversationHandler
from telegram.constants import ParseMode

from core.config import ST_SC_VALUE, ST_BC_VALUE
from handlers.base import BaseHandler
from utils.keyboards import kb, btn
from utils.bot_controller import BotController, SelfController

logger = logging.getLogger("BotForge.BotCtrl")


class BotCtrlHandler(BaseHandler):

    # ══════════════════════════════════════════════════════
    #  Self Control (BotForge نفسه)
    # ══════════════════════════════════════════════════════
    async def sc_start(self, update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> int:
        """يبدأ محادثة تغيير هوية BotForge"""
        if not self.is_owner(update):
            return ConversationHandler.END
        q = update.callback_query
        await q.answer()
        field = q.data.split(":", 1)[1]  # name | desc | about | photo

        prompts = {
            "name": "✏️ أدخل الاسم الجديد لـ BotForge:",
            "desc": "📝 أدخل الوصف الجديد (حتى 512 حرف):",
            "about": "💬 أدخل النبذة القصيرة (حتى 120 حرف):",
            "photo": "🖼 أرسل صورة جديدة لـ BotForge:",
        }
        self.sess(update.effective_user.id)["sc_field"] = field
        await q.edit_message_text(
            prompts.get(field, "أدخل القيمة:") + "\n\n/cancel للإلغاء"
        )
        return ST_SC_VALUE

    async def sc_text(self, update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> int:
        if not self.is_owner(update):
            return ConversationHandler.END
        uid = update.effective_user.id
        field = self.sess(uid).get("sc_field", "")
        text = (update.message.text or "").strip()

        if field == "photo":
            await update.message.reply_text("⚠️ أرسل صورة وليس نصاً.")
            return ST_SC_VALUE

        bot = ctx.application.bot
        if field == "name":
            ok, msg = await SelfController.set_name(bot, text)
        elif field == "desc":
            ok, msg = await SelfController.set_description(bot, text)
        elif field == "about":
            ok, msg = await SelfController.set_short_description(bot, text)
        else:
            return ConversationHandler.END

        self.sess_clear(uid)
        keyboard = kb(
            [
                btn("⚙️ إعدادات BotForge", "self_ctrl"),
                btn("🏠 الرئيسية", "home"),
            ]
        )
        await update.message.reply_text(
            msg, reply_markup=keyboard, parse_mode=ParseMode.MARKDOWN
        )
        return ConversationHandler.END

    # ══════════════════════════════════════════════════════
    #  Bot Control (بوت محتضن)
    # ══════════════════════════════════════════════════════
    async def bc_start(self, update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> int:
        """يبدأ محادثة تغيير هوية بوت محتضن"""
        if not self.is_owner(update):
            return ConversationHandler.END
        q = update.callback_query
        await q.answer()
        parts = q.data.split(":", 2)  # bc : field : bot_id
        field = parts[1]
        bot_id = parts[2]
        bot = self.pm.bots.get(bot_id)
        if not bot:
            await q.answer("البوت غير موجود", show_alert=True)
            return ConversationHandler.END
        if not bot.token:
            await q.answer(
                "❌ لا يوجد توكن — لا يمكن التحكم في هوية البوت",
                show_alert=True,
            )
            return ConversationHandler.END

        prompts = {
            "name": f"✏️ أدخل الاسم الجديد لـ {bot.name}:",
            "desc": "📝 أدخل الوصف الجديد:",
            "about": "💬 أدخل النبذة الجديدة:",
            "photo": "🖼 أرسل الصورة الجديدة:",
        }
        s = self.sess(update.effective_user.id)
        s["bc_field"] = field
        s["bc_target"] = bot_id
        await q.edit_message_text(
            prompts.get(field, "أدخل القيمة:") + "\n\n/cancel للإلغاء"
        )
        return ST_BC_VALUE

    async def bc_text(self, update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> int:
        if not self.is_owner(update):
            return ConversationHandler.END
        uid = update.effective_user.id
        s = self.sess(uid)
        field = s.get("bc_field", "")
        bot_id = s.get("bc_target", "")
        bot = self.pm.bots.get(bot_id)
        text = (update.message.text or "").strip()

        if not bot or not bot.token:
            await update.message.reply_text("❌ البوت أو التوكن غير متوفر")
            self.sess_clear(uid)
            return ConversationHandler.END

        if field == "photo":
            await update.message.reply_text("⚠️ أرسل صورة وليس نصاً.")
            return ST_BC_VALUE

        if field == "name":
            ok, msg = await BotController.set_name(bot.token, text)
            if ok:
                bot.name = text
                self.pm.save()
        elif field == "desc":
            ok, msg = await BotController.set_description(bot.token, text)
            if ok:
                bot.description = text
                self.pm.save()
        elif field == "about":
            ok, msg = await BotController.set_short_description(bot.token, text)
            if ok:
                bot.about = text
                self.pm.save()
        else:
            self.sess_clear(uid)
            return ConversationHandler.END

        self.sess_clear(uid)
        keyboard = kb(
            [
                btn("↩️ إعدادات البوت", f"bot_ctrl:{bot_id}"),
                btn("🏠 الرئيسية", "home"),
            ]
        )
        await update.message.reply_text(
            msg, reply_markup=keyboard, parse_mode=ParseMode.MARKDOWN
        )
        return ConversationHandler.END

    # ══════════════════════════════════════════════════════
    #  Callback router (غير المحادثة)
    # ══════════════════════════════════════════════════════
    async def on_cb(self, update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        if not self.is_owner(update):
            await update.callback_query.answer("⛔", show_alert=True)
            return
        q = update.callback_query
        await q.answer()
        d = q.data

        if d == "self_ctrl":
            await self._show_self_ctrl(update)

        elif d.startswith("bot_ctrl:"):
            bot_id = d.split(":", 1)[1]
            await self._show_bot_ctrl(update, bot_id)

        elif d.startswith("bc_fetch:"):
            bot_id = d.split(":", 1)[1]
            bot = self.pm.bots.get(bot_id)
            if bot and bot.token:
                info = await BotController.get_info(bot.token)
                if "error" in info:
                    await q.answer(f"❌ {info['error']}", show_alert=True)
                else:
                    bot.username = info.get("username", "")
                    self.pm.save()
                    text = (
                        "ℹ️ *معلومات البوت من Telegram*\n\n"
                        f"  🆔 ID: `{info.get('id')}`\n"
                        f"  👤 Username: `@{info.get('username')}`\n"
                        f"  📛 الاسم: `{info.get('first_name')}`\n"
                        f"  👥 يمكنه الانضمام: `{info.get('can_join')}`\n"
                        f"  🔍 Inline: `{info.get('is_inline')}`\n"
                    )
                    keyboard = kb([btn("↩️ رجوع", f"bot_ctrl:{bot_id}")])
                    await q.edit_message_text(
                        text,
                        reply_markup=keyboard,
                        parse_mode=ParseMode.MARKDOWN,
                    )

        elif d.startswith("bc_del_photo:"):
            bot_id = d.split(":", 1)[1]
            bot = self.pm.bots.get(bot_id)
            if bot and bot.token:
                ok, msg = await BotController.delete_photo(bot.token)
                await q.answer(msg, show_alert=True)
            await self._show_bot_ctrl(update, bot_id)

    # ══════════════════════════════════════════════════════
    #  Menus
    # ══════════════════════════════════════════════════════
    async def _show_self_ctrl(self, update: Update):
        text = "⚙️ *إعدادات BotForge*\n\nتحكم في هوية هذا البوت نفسه:"
        keyboard = kb(
            [btn("✏️ الاسم", "sc:name"), btn("📝 الوصف", "sc:desc")],
            [btn("💬 النبذة", "sc:about"), btn("🖼 الصورة", "sc:photo")],
            [btn("↩️ رجوع", "home")],
        )
        await self.reply(update, text, keyboard)

    async def _show_bot_ctrl(self, update: Update, bot_id: str):
        bot = self.pm.bots.get(bot_id)
        if not bot:
            if update.callback_query:
                await update.callback_query.answer("غير موجود", show_alert=True)
            return
        if not bot.token:
            if update.callback_query:
                await update.callback_query.answer(
                    "❌ لا يوجد توكن — لا يمكن التحكم في هوية البوت",
                    show_alert=True,
                )
            return
        text = (
            f"🛠 *إعدادات البوت: {bot.name}*\n\n"
            f"  🤖 `@{bot.username or '?'}`\n"
            f"  📝 {bot.description[:50] or '—'}\n"
            f"  💬 {bot.about[:50] or '—'}\n\n"
            "اختر ما تريد تعديله:"
        )
        keyboard = kb(
            [
                btn("✏️ الاسم", f"bc:name:{bot_id}"),
                btn("📝 الوصف", f"bc:desc:{bot_id}"),
            ],
            [
                btn("💬 النبذة", f"bc:about:{bot_id}"),
                btn("🖼 الصورة", f"bc:photo:{bot_id}"),
            ],
            [
                btn("🗑 حذف الصورة", f"bc_del_photo:{bot_id}"),
                btn("ℹ️ جلب المعلومات", f"bc_fetch:{bot_id}"),
            ],
            [btn("↩️ رجوع", f"info:{bot_id}")],
        )
        await self.reply(update, text, keyboard)
