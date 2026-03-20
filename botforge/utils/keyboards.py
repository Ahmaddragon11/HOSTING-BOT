"""
utils/keyboards.py — مولّد لوحات المفاتيح المتكررة
"""

from telegram import InlineKeyboardButton, InlineKeyboardMarkup


def kb(*rows) -> InlineKeyboardMarkup:
    """ينشئ InlineKeyboardMarkup من صفوف"""
    return InlineKeyboardMarkup(list(rows))


def btn(text: str, data: str = "", url: str = "") -> InlineKeyboardButton:
    if url:
        return InlineKeyboardButton(text, url=url)
    return InlineKeyboardButton(text, callback_data=data)


def back_btn(target: str = "home", label: str = "↩️ رجوع") -> InlineKeyboardButton:
    return btn(label, target)


def home_kb() -> InlineKeyboardMarkup:
    return kb([btn("🏠 الرئيسية", "home")])


def confirm_kb(yes_data: str, no_data: str) -> InlineKeyboardMarkup:
    return kb([btn("✅ نعم", yes_data), btn("❌ لا", no_data)])


def status_filter_kb(current: str = "all") -> InlineKeyboardMarkup:
    def mk_btn(label: str, val: str):
        prefix = "✔ " if current == val else ""
        return btn(f"{prefix}{label}", f"filter_status:{val}")

    return kb(
        [mk_btn("الكل", "all"), mk_btn("🟢 تعمل", "running"),
         mk_btn("🔴 متوقفة", "stopped"), mk_btn("🟠 أخطاء", "error")],
        [btn("↩️ رجوع", "list")],
    )
