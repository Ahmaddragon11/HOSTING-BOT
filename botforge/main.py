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
        ("telegram", "python-telegram-bot[job-queue]>=20.7"),
        ("psutil", "psutil"),
        ("dotenv", "python-dotenv"),
        ("httpx", "httpx"),
        ("aiofiles", "aiofiles"),
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
import os
import fcntl
import time
import psutil

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
#  SINGLE INSTANCE CHECK
# ══════════════════════════════════════════════════════════════
def check_single_instance():
    """التأكد من عدم وجود نسخة أخرى تعمل من البوت"""
    lock_file = BASE_DIR / ".botforge.lock"

    if lock_file.exists():
        try:
            # قراءة PID من ملف القفل
            with open(lock_file, "r") as f:
                old_pid = int(f.read().strip())

            # فحص إذا كان العملية لا تزال تعمل
            if psutil.pid_exists(old_pid):
                logger.error(f"يوجد نسخة أخرى من BotForge تعمل (PID: {old_pid})")
                print("❌ خطأ: يوجد نسخة أخرى من BotForge تعمل بالفعل!")
                print("تأكد من إيقاف النسخة الأخرى قبل تشغيل هذه النسخة.")
                return None
            else:
                # العملية السابقة توقفت، تنظيف ملف القفل
                logger.info(f"تنظيف ملف قفل قديم (PID: {old_pid})")
                lock_file.unlink(missing_ok=True)
        except (OSError, ValueError):
            # مشكلة في قراءة ملف القفل، تنظيفه
            lock_file.unlink(missing_ok=True)

    try:
        # محاولة إنشاء ملف القفل
        lock_fd = os.open(lock_file, os.O_CREAT | os.O_RDWR)
        fcntl.flock(lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)

        # كتابة PID الحالي
        os.write(lock_fd, str(os.getpid()).encode())
        os.fsync(lock_fd)

        logger.info(f"تم الحصول على قفل البوت (PID: {os.getpid()})")
        # حفظ file descriptor للإغلاق لاحقاً
        return lock_fd

    except (OSError, BlockingIOError):
        logger.error("يوجد نسخة أخرى من BotForge تعمل بالفعل!")
        print("❌ خطأ: يوجد نسخة أخرى من BotForge تعمل بالفعل!")
        print("تأكد من إيقاف النسخة الأخرى قبل تشغيل هذه النسخة.")
        return None


# ══════════════════════════════════════════════════════════════
#  APPLICATION
# ══════════════════════════════════════════════════════════════
def main():
    logger.info("بدء تشغيل BotForge v4.0...")

    # فحص النسخة الوحيدة
    lock_fd = check_single_instance()
    if lock_fd is None:
        return

    # فحص الإعدادات الأساسية
    if not BOTFORGE_TOKEN:
        logger.error("BOTFORGE_TOKEN غير محدد! أضف التوكن في ملف .env")
        print("❌ خطأ: BOTFORGE_TOKEN غير محدد!")
        print("أضف التوكن في ملف .env في مجلد botforge/")
        return
    if BOTFORGE_OWNER == 0:
        logger.error("BOTFORGE_OWNER غير محدد! أضف معرف المالك في ملف .env")
        print("❌ خطأ: BOTFORGE_OWNER غير محدد!")
        print("أضف معرف المالك في ملف .env في مجلد botforge/")
        return

    # إنشاء المكونات الأساسية
    pm = ProcessManager()
    scheduler = BotScheduler(pm)
    notifier = Notifier(BOTFORGE_OWNER)

    # بناء تطبيق Telegram
    try:
        app = Application.builder().token(BOTFORGE_TOKEN).build()
        logger.info("تم بناء تطبيق Telegram بنجاح")
    except Exception as e:
        logger.error(f"فشل في بناء تطبيق Telegram: {e}")
        print(f"❌ فشل في بناء تطبيق Telegram: {e}")
        return

    # ربط الـ notifier بالتطبيق
    notifier.set_app(app)
    pm.set_notifier(notifier)

    # تسجيل جميع الـ handlers
    build_handlers(app, pm, scheduler, notifier)

    # Post-init: يعمل بعد بدء التطبيق
    async def post_init(application: Application):
        from telegram import BotCommand

        me = await application.bot.get_me()

        logger.info(
            f"BotForge جاهز: @{me.username} | المالك: {BOTFORGE_OWNER} | بوتات: {len(pm.bots)}"
        )

        print("\n" + "═" * 58)
        print(f"  🚀  BotForge v4.0 يعمل!")
        print(f"  🤖  @{me.username}  (ID: {me.id})")
        print(f"  👤  المالك: {BOTFORGE_OWNER}")
        print(f"  📦  بوتات محتضنة: {len(pm.bots)}")
        print(f"  📁  مجلد العمل: {BASE_DIR}")
        print("═" * 58 + "\n")

        # تعيين قائمة الأوامر
        await application.bot.set_my_commands(
            [
                BotCommand("start", "🏠 الرئيسية"),
                BotCommand("panel", "🖥 لوحة التحكم"),
                BotCommand("bots", "📋 قائمة البوتات"),
                BotCommand("add", "➕ إضافة بوت"),
                BotCommand("search", "🔍 بحث في البوتات"),
                BotCommand("stats", "📊 إحصائيات النظام"),
                BotCommand("logs", "📋 سجلات بوت"),
                BotCommand("start_bot", "▶️ تشغيل بوت"),
                BotCommand("stop_bot", "⏹ إيقاف بوت"),
                BotCommand("restart", "🔄 إعادة تشغيل"),
                BotCommand("schedule", "📅 جدولة مهمة"),
                BotCommand("cancel", "❌ إلغاء"),
            ]
        )

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

        # تنظيف ملف القفل
        lock_file = BASE_DIR / ".botforge.lock"
        try:
            if lock_file.exists():
                os.remove(lock_file)
        except OSError:
            pass

        print("[BotForge] 👋 تم الإيقاف.")
        sys.exit(0)

    signal.signal(signal.SIGINT, _shutdown)
    signal.signal(signal.SIGTERM, _shutdown)

    try:
        # انتظار قصير للتأكد من إيقاف أي نسخة سابقة
        logger.info("انتظار 5 ثوانٍ للتأكد من إيقاف أي نسخة سابقة...")
        time.sleep(5)

        # تشغيل البوت
        logger.info("بدء الاستماع للتحديثات...")
        app.run_polling(
            drop_pending_updates=True,
            allowed_updates=Update.ALL_TYPES,
            poll_interval=1.0,  # ثانية واحدة بين كل استطلاع
            timeout=30,  # 30 ثانية timeout لكل استطلاع
        )
    except Exception as e:
        logger.error(f"خطأ في تشغيل البوت: {e}")
        print(f"❌ خطأ في تشغيل البوت: {e}")
    finally:
        # تنظيف ملف القفل عند الخروج
        lock_file = BASE_DIR / ".botforge.lock"
        try:
            if lock_file.exists():
                os.remove(lock_file)
        except OSError:
            pass


if __name__ == "__main__":
    main()
