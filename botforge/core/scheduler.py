"""
core/scheduler.py — جدولة المهام (تشغيل/إيقاف/إعادة تشغيل في أوقات محددة)
"""

from __future__ import annotations
import json
import logging
import threading
from datetime import datetime
from typing import TYPE_CHECKING

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger
from apscheduler.triggers.date import DateTrigger

from core.config import SCHEDULE_FILE

if TYPE_CHECKING:
    from core.process_manager import ProcessManager

logger = logging.getLogger("BotForge.Scheduler")


class BotScheduler:
    """يدير جدولة المهام المرتبطة بالبوتات"""

    def __init__(self, pm: "ProcessManager"):
        self.pm = pm
        self._sch = BackgroundScheduler(timezone="Asia/Riyadh")
        self._jobs: dict[str, dict] = {}  # job_id -> info
        self._lock = threading.Lock()
        self._load()

    def start(self):
        self._sch.start()
        logger.info(f"المجدول بدأ | مهام محملة: {len(self._jobs)}")

    def stop(self):
        try:
            self._sch.shutdown(wait=False)
        except Exception:
            pass

    # ══════════════════════════════════════════════════════
    #  Persistence
    # ══════════════════════════════════════════════════════
    def _load(self):
        if not SCHEDULE_FILE.exists():
            return
        try:
            data = json.loads(SCHEDULE_FILE.read_text("utf-8"))
            for jid, info in data.items():
                self._jobs[jid] = info
                self._register(jid, info)
            logger.info(f"تم تحميل {len(self._jobs)} مهمة مجدولة")
        except Exception as e:
            logger.error(f"خطأ تحميل الجدول: {e}")

    def _save(self):
        try:
            SCHEDULE_FILE.write_text(
                json.dumps(self._jobs, indent=2, ensure_ascii=False),
                encoding="utf-8",
            )
        except Exception as e:
            logger.error(f"خطأ حفظ الجدول: {e}")

    # ══════════════════════════════════════════════════════
    #  Job Registration
    # ══════════════════════════════════════════════════════
    def _execute(self, bot_id: str, action: str):
        bot = self.pm.bots.get(bot_id)
        if not bot:
            logger.warning(f"مهمة مجدولة: البوت {bot_id} غير موجود")
            return
        logger.info(f"تنفيذ مهمة مجدولة: {action} → {bot.name}")
        if action == "start":
            self.pm.start(bot_id)
        elif action == "stop":
            self.pm.stop(bot_id)
        elif action == "restart":
            self.pm.restart(bot_id)

    def _register(self, jid: str, info: dict):
        """يسجل المهمة في APScheduler"""
        try:
            ttype = info.get("trigger_type", "cron")
            bot_id = info["bot_id"]
            action = info["action"]

            if ttype == "cron":
                trigger = CronTrigger(
                    hour=info.get("hour", "*"),
                    minute=info.get("minute", "0"),
                    day_of_week=info.get("day_of_week", "*"),
                )
            elif ttype == "interval":
                trigger = IntervalTrigger(
                    hours=info.get("hours", 0),
                    minutes=info.get("minutes", 0),
                )
            elif ttype == "once":
                run_at = datetime.fromisoformat(info["run_at"])
                trigger = DateTrigger(run_date=run_at)
            else:
                return

            self._sch.add_job(
                self._execute,
                trigger=trigger,
                args=[bot_id, action],
                id=jid,
                replace_existing=True,
                misfire_grace_time=60,
            )
        except Exception as e:
            logger.error(f"خطأ تسجيل المهمة {jid}: {e}")

    # ══════════════════════════════════════════════════════
    #  Public API
    # ══════════════════════════════════════════════════════
    def add_cron(
        self, bot_id: str, action: str, hour: str, minute: str, day_of_week: str = "*"
    ) -> str:
        import hashlib
        import time

        jid = hashlib.md5(
            f"{bot_id}{action}{hour}{minute}{time.time()}".encode()
        ).hexdigest()[:10]
        info = dict(
            bot_id=bot_id,
            action=action,
            trigger_type="cron",
            hour=hour,
            minute=minute,
            day_of_week=day_of_week,
            created=datetime.now().isoformat(),
        )
        with self._lock:
            self._jobs[jid] = info
            self._register(jid, info)
            self._save()
        return jid

    def add_interval(
        self, bot_id: str, action: str, hours: int = 0, minutes: int = 0
    ) -> str:
        import hashlib
        import time

        jid = hashlib.md5(
            f"{bot_id}{action}{hours}{minutes}{time.time()}".encode()
        ).hexdigest()[:10]
        info = dict(
            bot_id=bot_id,
            action=action,
            trigger_type="interval",
            hours=hours,
            minutes=minutes,
            created=datetime.now().isoformat(),
        )
        with self._lock:
            self._jobs[jid] = info
            self._register(jid, info)
            self._save()
        return jid

    def add_once(self, bot_id: str, action: str, run_at: datetime) -> str:
        import hashlib
        import time as t

        jid = hashlib.md5(f"{bot_id}{action}{t.time()}".encode()).hexdigest()[:10]
        info = dict(
            bot_id=bot_id,
            action=action,
            trigger_type="once",
            run_at=run_at.isoformat(),
            created=datetime.now().isoformat(),
        )
        with self._lock:
            self._jobs[jid] = info
            self._register(jid, info)
            self._save()
        return jid

    def remove(self, jid: str) -> bool:
        with self._lock:
            if jid not in self._jobs:
                return False
            try:
                self._sch.remove_job(jid)
            except Exception:
                pass
            del self._jobs[jid]
            self._save()
            return True

    def list_for_bot(self, bot_id: str) -> list[dict]:
        return [
            {"jid": jid, **info}
            for jid, info in self._jobs.items()
            if info.get("bot_id") == bot_id
        ]

    def list_all(self) -> list[dict]:
        return [{"jid": jid, **info} for jid, info in self._jobs.items()]

    def next_run(self, jid: str) -> str:
        try:
            job = self._sch.get_job(jid)
            if job and job.next_run_time:
                return job.next_run_time.strftime("%Y-%m-%d %H:%M")
        except Exception:
            pass
        return "—"

    def format_job(self, jid: str, info: dict) -> str:
        actions = {"start": "▶️ تشغيل", "stop": "⏹ إيقاف", "restart": "🔄 إعادة"}
        ttype = info.get("trigger_type", "cron")
        action = actions.get(info.get("action", ""), info.get("action", ""))
        bot = self.pm.bots.get(info.get("bot_id", ""))
        name = bot.name if bot else info.get("bot_id", "؟")
        nxt = self.next_run(jid)

        if ttype == "cron":
            dow = info.get("day_of_week", "*")
            dow_ar = {
                "*": "يومياً",
                "mon": "الاثنين",
                "tue": "الثلاثاء",
                "wed": "الأربعاء",
                "thu": "الخميس",
                "fri": "الجمعة",
                "sat": "السبت",
                "sun": "الأحد",
            }.get(dow, dow)
            when = f"{info.get('hour','*')}:{info.get('minute','00')} — {dow_ar}"
        elif ttype == "interval":
            h = info.get("hours", 0)
            m = info.get("minutes", 0)
            when = f"كل {h}h {m}m" if h else f"كل {m} دقيقة"
        elif ttype == "once":
            when = info.get("run_at", "")[:16]
        else:
            when = "—"

        return f"📅 `{jid[:6]}` | {action} *{name}* | {when} | التالي: `{nxt}`"
