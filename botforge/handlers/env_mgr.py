"""
handlers/env_mgr.py — إدارة متغيرات البيئة لكل بوت
"""

from __future__ import annotations
import logging

from telegram import Update
from telegram.ext import ContextTypes, ConversationHandler
from telegram.constants import ParseMode

from core.config import ST_ENV_KEY, ST_ENV_VAL
from handlers.base import BaseHandler
from utils.keyboards import kb, btn

logger = logging.getLogger("BotForge.EnvMgr")


class EnvManager(BaseHandler):

    # ══════════════════════════════════════════════════════
    #  Callback router
    # ══════════════════════════════════════════════════════
    async def on_cb(self, update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        if not self.is_owner(update):
            await update.callback_query.answer("⛔", show_alert=True)
            return
        q  = update.callback_query
        await q.answer()
        d  = q.data

        if d.startswith("env_menu:"):
            bot_id = d.split(":", 1)[1]
            await self._show_env_menu(update, bot_id)

        elif d.startswith("env_list:"):
            bot_id = d.split(":", 1)[1]
            await self._show_env_list(update, bot_id)

        elif d.startswith("env_del:"):
            _, bot_id, key = d.split(":", 2)
            bot = self.pm.bots.get(bot_id)
            if bot:
                deleted = self.pm.delete_env_var(bot, key)
                await q.answer(
                    f"✅ تم حذف {key}" if deleted else "❌ المتغير غير موجود",
                    show_alert=True
                )
            await self._show_env_menu(update, bot_id)

    # ══════════════════════════════════════════════════════
    #  Conversation — إضافة متغير
    # ══════════════════════════════════════════════════════
    async def start_add_env(self, update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> int:
        if not self.is_owner(update):
            return ConversationHandler.END
        q      = update.callback_query
        await q.answer()
        bot_id = q.data.split(":", 1)[1]
        bot    = self.pm.bots.get(bot_id)
        if not bot:
            await q.answer("البوت غير موجود", show_alert=True)
            return ConversationHandler.END

        self.sess(update.effective_user.id)["env_target"] = bot_id
        await q.edit_message_text(
            f"🔑 *إضافة متغير بيئة — {bot.name}*\n\n"
            "أدخل اسم المتغير (مثال: `API_KEY`):\n\n"
            "/cancel للإلغاء",
            parse_mode=ParseMode.MARKDOWN,
        )
        return ST_ENV_KEY

    async def get_key(self, update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> int:
        if not self.is_owner(update):
            return ConversationHandler.END
        key = (update.message.text or "").strip().upper()
        if not key or not key.replace("_", "").isalnum():
            await update.message.reply_text(
                "⚠️ اسم المتغير يجب أن يحتوي على حروف وأرقام وشرطة سفلية فقط"
            )
            return ST_ENV_KEY
        self.sess(update.effective_user.id)["env_key"] = key
        await update.message.reply_text(
            f"✅ المفتاح: `{key}`\n\n🔒 أدخل القيمة:\n_سيتم حذف رسالتك تلقائياً_",
            parse_mode=ParseMode.MARKDOWN,
        )
        return ST_ENV_VAL

    async def get_val(self, update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> int:
        if not self.is_owner(update):
            return ConversationHandler.END
        uid    = update.effective_user.id
        s      = self.sess(uid)
        bot_id = s.get("env_target", "")
        key    = s.get("env_key", "")
        val    = (update.message.text or "").strip()
        bot    = self.pm.bots.get(bot_id)

        # حذف الرسالة التي تحتوي القيمة (أمان)
        try:
            await update.message.delete()
        except Exception:
            pass

        if not bot:
            await update.message.reply_text("❌ البوت غير موجود")
            self.sess_clear(uid)
            return ConversationHandler.END

        self.pm.set_env_var(bot, key, val)
        self.sess_clear(uid)

        keyboard = kb(
            [btn("🔑 إدارة المتغيرات", f"env_menu:{bot_id}"),
             btn("📋 معلومات البوت",  f"info:{bot_id}")]
        )
        await update.message.reply_text(
            f"✅ تم حفظ المتغير:\n`{key}` = `{'*' * min(len(val), 8)}...`",
            reply_markup=keyboard,
            parse_mode=ParseMode.MARKDOWN,
        )
        return ConversationHandler.END

    # ══════════════════════════════════════════════════════
    #  Menus
    # ══════════════════════════════════════════════════════
    async def _show_env_menu(self, update: Update, bot_id: str):
        bot = self.pm.bots.get(bot_id)
        if not bot:
            if update.callback_query:
                await update.callback_query.answer("غير موجود", show_alert=True)
            return
        count = len(bot.env_vars)
        text = (
            f"🔑 *متغيرات البيئة — {bot.name}*\n\n"
            f"  عدد المتغيرات: `{count}`\n\n"
            "هذه المتغيرات تُمرَّر للبوت عند التشغيل وتتفوق على أي قيم في `.env`"
        )
        keyboard = kb(
            [btn("➕ إضافة متغير",    f"env_add:{bot_id}"),
             btn("📋 عرض المتغيرات",  f"env_list:{bot_id}")],
            [btn("↩️ رجوع",          f"info:{bot_id}")],
        )
        await self.reply(update, text, keyboard)

    async def _show_env_list(self, update: Update, bot_id: str):
        bot = self.pm.bots.get(bot_id)
        if not bot:
            return
        if not bot.env_vars:
            await update.callback_query.answer("لا توجد متغيرات بعد", show_alert=True)
            await self._show_env_menu(update, bot_id)
            return

        lines = [f"📋 *متغيرات البيئة — {bot.name}:*\n"]
        rows  = []
        for k, v in bot.env_vars.items():
            # إخفاء القيم الحساسة
            masked = v[:3] + "****" if len(v) > 3 else "****"
            lines.append(f"  `{k}` = `{masked}`")
            rows.append([
                btn(f"🗑 حذف {k}", f"env_del:{bot_id}:{k}")
            ])
        rows.append([btn("➕ إضافة", f"env_add:{bot_id}"), btn("↩️ رجوع", f"env_menu:{bot_id}")])
        await self.reply(update, "\n".join(lines), kb(*rows))
