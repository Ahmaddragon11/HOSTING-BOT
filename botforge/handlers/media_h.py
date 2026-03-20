"""
handlers/media_h.py — معالجة الصور والملفات خارج المحادثات الرسمية
"""

from __future__ import annotations
import io
import logging

from telegram import Update
from telegram.ext import ContextTypes, ConversationHandler
from telegram.constants import ParseMode

from core.config import TMP_DIR, ST_SC_VALUE, ST_BC_VALUE
from handlers.base import BaseHandler
from utils.keyboards import kb, btn
from utils.extractor import Extractor

logger = logging.getLogger("BotForge.Media")


class MediaHandler(BaseHandler):
    def __init__(self, pm, bot_ctrl_handler):
        super().__init__(pm)
        self._bctrl = bot_ctrl_handler   # BotCtrlHandler

    # ══════════════════════════════════════════════════════
    #  صور ضمن محادثة self_ctrl
    # ══════════════════════════════════════════════════════
    async def sc_photo(self, update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> int:
        if not self.is_owner(update):
            return ConversationHandler.END
        uid   = update.effective_user.id
        field = self._bctrl.sess(uid).get("sc_field", "")
        if field != "photo":
            return ST_SC_VALUE

        data = await self._download_photo(update, ctx)
        from utils.bot_controller import SelfController
        ok, msg = await SelfController.set_photo(ctx.application.bot, data)
        self._bctrl.sess_clear(uid)
        keyboard = kb(
            [btn("⚙️ إعدادات BotForge", "self_ctrl"),
             btn("🏠 الرئيسية",          "home")]
        )
        await update.message.reply_text(msg, reply_markup=keyboard, parse_mode=ParseMode.MARKDOWN)
        return ConversationHandler.END

    # ══════════════════════════════════════════════════════
    #  صور ضمن محادثة bot_ctrl
    # ══════════════════════════════════════════════════════
    async def bc_photo(self, update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> int:
        if not self.is_owner(update):
            return ConversationHandler.END
        uid    = update.effective_user.id
        s      = self._bctrl.sess(uid)
        field  = s.get("bc_field", "")
        bot_id = s.get("bc_target", "")

        if field != "photo":
            return ST_BC_VALUE

        bot = self.pm.bots.get(bot_id)
        if not bot or not bot.token:
            await update.message.reply_text("❌ التوكن غير متوفر")
            self._bctrl.sess_clear(uid)
            return ConversationHandler.END

        data = await self._download_photo(update, ctx)
        from utils.bot_controller import BotController
        ok, msg = await BotController.set_photo(bot.token, data)
        self._bctrl.sess_clear(uid)
        keyboard = kb(
            [btn("↩️ إعدادات البوت", f"bot_ctrl:{bot_id}"),
             btn("🏠 الرئيسية",       "home")]
        )
        await update.message.reply_text(msg, reply_markup=keyboard, parse_mode=ParseMode.MARKDOWN)
        return ConversationHandler.END

    # ══════════════════════════════════════════════════════
    #  ملف يُرسَل مباشرة (drag & drop)
    # ══════════════════════════════════════════════════════
    async def on_doc_free(self, update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        if not self.is_owner(update):
            return
        doc = update.message.document
        if not doc or not Extractor.is_allowed(doc.file_name):
            return

        uid = update.effective_user.id
        msg = await update.message.reply_text(
            "📥 *تم استلام ملف*\n\n"
            "⏳ جاري التحميل… سأبدأ عملية الإضافة تلقائياً.",
            parse_mode=ParseMode.MARKDOWN,
        )
        tmp  = TMP_DIR / f"{uid}_{doc.file_name}"
        tgf  = await ctx.bot.get_file(doc.file_id)
        await tgf.download_to_drive(tmp)

        # نحتاج اسم — نطلبه
        self.sess(uid)["file"] = tmp
        self.sess(uid)["orig"] = doc.file_name
        ctx.user_data["awaiting_name_free"] = True

        await msg.edit_text(
            f"✅ تم تحميل `{doc.file_name}`\n\n"
            "📝 *أدخل اسماً للبوت:*\n_(أو /cancel للإلغاء)_",
            parse_mode=ParseMode.MARKDOWN,
        )

    async def on_free_name(self, update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        """يستقبل اسم البوت بعد رفع الملف مباشرة"""
        if not self.is_owner(update):
            return
        if not ctx.user_data.get("awaiting_name_free"):
            return
        uid  = update.effective_user.id
        name = (update.message.text or "").strip()
        if not 1 <= len(name) <= 64:
            await update.message.reply_text("⚠️ الاسم 1–64 حرف — حاول مجدداً:")
            return
        self.sess(uid)["name"] = name
        ctx.user_data["awaiting_name_free"] = False
        ctx.user_data["awaiting_token_free"] = True

        keyboard = kb([btn("⏭ تخطي (بدون توكن)", "skip_token_free")])
        await update.message.reply_text(
            "🔑 *أدخل توكن البوت* أو اضغط تخطي:",
            reply_markup=keyboard,
            parse_mode=ParseMode.MARKDOWN,
        )

    # ══════════════════════════════════════════════════════
    #  Helper
    # ══════════════════════════════════════════════════════
    async def _download_photo(self, update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> bytes:
        photo = update.message.photo[-1]
        f     = await ctx.bot.get_file(photo.file_id)
        buf   = io.BytesIO()
        await f.download_to_memory(buf)
        return buf.getvalue()
