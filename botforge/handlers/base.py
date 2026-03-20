"""
handlers/base.py — كلاس أساسي مشترك لجميع الـ handlers
"""

from __future__ import annotations
import logging
from typing import TYPE_CHECKING

from telegram import Update, InlineKeyboardMarkup
from telegram.constants import ParseMode
from telegram.error import BadRequest

from core.config import BOTFORGE_OWNER
from core.process_manager import ProcessManager

if TYPE_CHECKING:
    from core.notifier import Notifier

logger = logging.getLogger("BotForge.Handler")


class BaseHandler:
    def __init__(self, pm: ProcessManager, notifier: "Notifier | None" = None):
        self.pm = pm
        self.notifier = notifier
        self._sessions: dict[int, dict] = {}

    # ── Auth ──────────────────────────────────────────────
    def is_owner(self, update: Update) -> bool:
        return update.effective_user.id == BOTFORGE_OWNER

    def _deny(self, update: Update):
        if update.callback_query:
            return update.callback_query.answer("⛔ غير مصرح", show_alert=True)
        elif update.message:
            return update.message.reply_text("⛔ هذا البوت خاص.")

    # ── Session ───────────────────────────────────────────
    def sess(self, uid: int) -> dict:
        return self._sessions.setdefault(uid, {})

    def sess_clear(self, uid: int):
        self._sessions.pop(uid, None)

    # ── Reply helper ──────────────────────────────────────
    async def reply(
        self,
        update: Update,
        text: str,
        keyboard: InlineKeyboardMarkup | None = None,
        edit: bool = True,
        md: str = ParseMode.MARKDOWN,
    ):
        kw = {"parse_mode": md}
        if keyboard:
            kw["reply_markup"] = keyboard
        if edit and update.callback_query:
            try:
                await update.callback_query.edit_message_text(text, **kw)
                return
            except BadRequest:
                pass
        target = update.message or (
            update.callback_query and update.callback_query.message
        )
        if target:
            await target.reply_text(text, **kw)
