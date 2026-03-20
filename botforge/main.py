#!/usr/bin/env python3
"""
╔══════════════════════════════════════════════════════════════╗
║        BotForge v4.0 — Personal Bot Hosting Manager          ║
║                    by AHMADDRAGON                            ║
╠══════════════════════════════════════════════════════════════╣
║  تشغيل:  python main.py                                      ║
║  لا تحتاج لأي تثبيت يدوي — كل شيء يُثبَّت تلقائياً          ║
╚══════════════════════════════════════════════════════════════╝
"""

# ══════════════════════════════════════════════════════════════
#  BOOTSTRAP — يجب أن يكون أول شيء
# ══════════════════════════════════════════════════════════════
import sys
import subprocess


def _can_import(mod: str) -> bool:
    try:
        __import__(mod)
        return True
    except ImportError:
        return False


def bootstrap():
    pkgs = [
        ("telegram",    "python-telegram-bot[job-queue]>=20.7"),
        ("psutil",      "psutil"),
        ("dotenv",      "python-dotenv"),
        ("httpx",       "httpx"),
        ("aiofiles",    "aiofiles"),
        ("apscheduler", "APScheduler>=3.10"),
    ]
    missing = [pkg for mod, pkg in pkgs if not _can_import(mod)]
    if missing:
        print(f"[BotForge] 📦 تثبيت المتطلبات: {', '.join(missing)}")
        subprocess.check_call(
            [sys.executable, "-m", "pip", "install", "--quiet", "--upgrade", *missing],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        print("[BotForge] ✅ تم التثبيت بنجاح — جاري التشغيل...\n")


bootstrap()

# ══════════════════════════════════════════════════════════════
#  MAIN IMPORTS (بعد التثبيت)
# ══════════════════════════════════════════════════════════════
import logging
import signal

from telegram import Update
from telegram.ext import Application

from core.config import BOTFORGE_TOKEN, BOTFORGE_OWNER, BASE_DIR
from core.process_manager import ProcessManager
from core.scheduler import BotScheduler
from core.notifier import Notifier
from handlers.router import build_handlers
from utils.logger import setup_logging

# ══════════════════════════════════════════════════════════════
#  LOGGING SETUP
# ══════════════════════════════════════════════════════════════
setup_logging()
logger = logging.getLogger("BotForge.Main")


# ══════════════════════════════════════════════════════════════
#  APPLICATION
# ══════════════════════════════════════════════════════════════
def main():
    logger.info("بدء تشغيل BotForge v4.0...")

    # إنشاء المكونات الأساسية
    pm        = ProcessManager()
    scheduler = BotScheduler(pm)
    notifier  = Notifier(BOTFORGE_OWNER)

    # بناء تطبيق Telegram
    app = Application.builder().token(BOTFORGE_TOKEN).build()

    # ربط الـ notifier بالتطبيق
    notifier.set_app(app)
    pm.set_notifier(notifier)

    # تسجيل جميع الـ handlers
    build_handlers(app, pm, scheduler, notifier)

    # Post-init: يعمل بعد بدء التطبيق
    async def post_init(application: Application):
        from telegram import BotCommand
        me = await application.bot.get_me()

        logger.info(f"BotForge جاهز: @{me.username} | المالك: {BOTFORGE_OWNER} | بوتات: {len(pm.bots)}")

        print("\n" + "═" * 58)
        print(f"  🚀  BotForge v4.0 يعمل!")
        print(f"  🤖  @{me.username}  (ID: {me.id})")
        print(f"  👤  المالك: {BOTFORGE_OWNER}")
        print(f"  📦  بوتات محتضنة: {len(pm.bots)}")
        print(f"  📁  مجلد العمل: {BASE_DIR}")
        print("═" * 58 + "\n")

        # تعيين قائمة الأوامر
        await application.bot.set_my_commands([
            BotCommand("start",     "🏠 الرئيسية"),
            BotCommand("panel",     "🖥 لوحة التحكم"),
            BotCommand("bots",      "📋 قائمة البوتات"),
            BotCommand("add",       "➕ إضافة بوت"),
            BotCommand("search",    "🔍 بحث في البوتات"),
            BotCommand("stats",     "📊 إحصائيات النظام"),
            BotCommand("logs",      "📋 سجلات بوت"),
            BotCommand("start_bot", "▶️ تشغيل بوت"),
            BotCommand("stop_bot",  "⏹ إيقاف بوت"),
            BotCommand("restart",   "🔄 إعادة تشغيل"),
            BotCommand("schedule",  "📅 جدولة مهمة"),
            BotCommand("cancel",    "❌ إلغاء"),
        ])

        # تشغيل المجدول
        scheduler.start()

    app.post_init = post_init

    # إيقاف نظيف
    def _shutdown(sig, _frame):
        print(f"\n[BotForge] إيقاف نظيف (signal {sig})...")
        scheduler.stop()
        for b in list(pm.bots.values()):
            if b.status == "running":
                pm.stop(b.bot_id)
        print("[BotForge] 👋 تم الإيقاف.")
        sys.exit(0)

    signal.signal(signal.SIGINT,  _shutdown)
    signal.signal(signal.SIGTERM, _shutdown)

    # تشغيل البوت
    app.run_polling(
        drop_pending_updates=True,
        allowed_updates=Update.ALL_TYPES,
    )


if __name__ == "__main__":
    main()
