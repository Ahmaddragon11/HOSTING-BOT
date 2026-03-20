"""
core/process_manager.py — إدارة دورة حياة البوتات المستضافة
"""

from __future__ import annotations
import os
import re
import sys
import json
import time
import shutil
import venv
import logging
import threading
import subprocess
from pathlib import Path
from datetime import datetime
from typing import TYPE_CHECKING

import psutil

from core.config import (
    BOTS_DIR, LOGS_DIR, STATE_FILE, TMP_DIR,
    AUTO_RESTART_DELAY,
)
from core.models import BotInstance

if TYPE_CHECKING:
    from core.notifier import Notifier

logger = logging.getLogger("BotForge.PM")


class ProcessManager:
    """يدير جميع البوتات المستضافة: تسجيل، تشغيل، إيقاف، إحصائيات"""

    def __init__(self):
        self.bots: dict[str, BotInstance] = {}
        self._lock = threading.Lock()
        self._notifier: "Notifier | None" = None
        self._load()

    def set_notifier(self, notifier: "Notifier"):
        self._notifier = notifier

    # ══════════════════════════════════════════════════════
    #  Persistence
    # ══════════════════════════════════════════════════════
    def _load(self):
        if not STATE_FILE.exists():
            return
        try:
            rows = json.loads(STATE_FILE.read_text("utf-8"))
            for d in rows:
                b = BotInstance.from_dict(d)
                self.bots[b.bot_id] = b
            logger.info(f"تم تحميل {len(self.bots)} بوت")
        except Exception as e:
            logger.error(f"خطأ تحميل الحالة: {e}")

    def save(self):
        try:
            STATE_FILE.write_text(
                json.dumps(
                    [b.to_dict() for b in self.bots.values()],
                    indent=2, ensure_ascii=False,
                ),
                encoding="utf-8",
            )
        except Exception as e:
            logger.error(f"خطأ حفظ الحالة: {e}")

    # ══════════════════════════════════════════════════════
    #  Registration
    # ══════════════════════════════════════════════════════
    def add(self, bot: BotInstance):
        with self._lock:
            self.bots[bot.bot_id] = bot
            self.save()

    def remove(self, bot_id: str) -> bool:
        with self._lock:
            if bot_id not in self.bots:
                return False
            self._kill(bot_id)
            bot = self.bots.pop(bot_id)
            shutil.rmtree(bot.path, ignore_errors=True)
            bot.log_file.unlink(missing_ok=True)
            self.save()
            logger.info(f"تم حذف البوت {bot.name} [{bot_id}]")
            return True

    # ══════════════════════════════════════════════════════
    #  Environment Setup
    # ══════════════════════════════════════════════════════
    def _python_exe(self, bot: BotInstance) -> str:
        s = "Scripts" if sys.platform == "win32" else "bin"
        e = "python.exe" if sys.platform == "win32" else "python"
        return str(bot.env_path / s / e)

    # مكتبة stdlib شاملة لتجنب التثبيت غير الضروري
    _STDLIB = {
        "os","sys","re","json","time","math","random","logging","threading",
        "subprocess","pathlib","datetime","collections","functools","itertools",
        "io","abc","copy","enum","typing","dataclasses","asyncio","concurrent",
        "contextlib","inspect","hashlib","hmac","base64","urllib","http",
        "socket","ssl","email","html","xml","csv","sqlite3","pickle","struct",
        "traceback","warnings","gc","weakref","signal","shutil","tempfile",
        "glob","fnmatch","stat","uuid","decimal","fractions","operator",
        "string","textwrap","pprint","numbers","cmath","venv","argparse",
        "configparser","platform","queue","array","heapq","bisect","calendar",
        "locale","gettext","codecs","unicodedata","struct","binascii","zlib",
        "gzip","bz2","lzma","zipfile","tarfile","csv","configparser",
        "netrc","ftplib","imaplib","smtplib","poplib","xmlrpc","http",
        "multiprocessing","concurrent","selectors","asynchat","asyncore",
        "unittest","doctest","pdb","profile","timeit","trace","dis",
        "ast","token","tokenize","keyword","symtable","compileall",
        "builtins","__future__","_thread","atexit","abc","contextlib",
    }

    _PKG_MAP = {
        "telegram":    "python-telegram-bot[job-queue]>=20.7",
        "telebot":     "pyTelegramBotAPI",
        "aiogram":     "aiogram",
        "flask":       "flask",
        "fastapi":     "fastapi uvicorn",
        "aiohttp":     "aiohttp",
        "requests":    "requests",
        "httpx":       "httpx",
        "pydantic":    "pydantic",
        "sqlalchemy":  "sqlalchemy",
        "pymongo":     "pymongo",
        "redis":       "redis",
        "celery":      "celery",
        "PIL":         "Pillow",
        "cv2":         "opencv-python",
        "numpy":       "numpy",
        "pandas":      "pandas",
        "dotenv":      "python-dotenv",
        "yaml":        "PyYAML",
        "bs4":         "beautifulsoup4",
        "lxml":        "lxml",
        "openai":      "openai",
        "anthropic":   "anthropic",
        "google":      "google-generativeai",
        "aiosqlite":   "aiosqlite",
        "motor":       "motor",
        "apscheduler": "APScheduler",
        "psutil":      "psutil",
        "pytz":        "pytz",
        "babel":       "Babel",
        "cryptography":"cryptography",
        "jwt":         "PyJWT",
        "paramiko":    "paramiko",
        "boto3":       "boto3",
        "stripe":      "stripe",
        "qrcode":      "qrcode[pil]",
        "barcode":     "python-barcode",
        "fpdf":        "fpdf2",
        "docx":        "python-docx",
        "openpyxl":    "openpyxl",
        "matplotlib":  "matplotlib",
        "seaborn":     "seaborn",
        "sklearn":     "scikit-learn",
        "torch":       "torch",
        "tf":          "tensorflow",
        "transformers":"transformers",
    }

    def detect_imports(self, bot: BotInstance) -> list[str]:
        """يكتشف المكتبات المستخدمة من ملفات .py"""
        found: set[str] = set()
        for py in bot.path.rglob("*.py"):
            if ".venv" in py.parts:
                continue
            try:
                txt = py.read_text(encoding="utf-8", errors="ignore")
                for m in re.findall(
                    r"^(?:import|from)\s+([a-zA-Z_][a-zA-Z0-9_]*)", txt, re.M
                ):
                    if m not in self._STDLIB and m in self._PKG_MAP:
                        found.add(self._PKG_MAP[m])
            except Exception:
                pass
        return list(found)

    def setup_env(self, bot: BotInstance) -> tuple[bool, str]:
        """ينشئ venv ويثبت المتطلبات"""
        bot.status = "installing"
        try:
            if not bot.env_path.exists():
                bot.logs.append("🔧 إنشاء بيئة Python الافتراضية...")
                venv.create(str(bot.env_path), with_pip=True)
                subprocess.run(
                    [self._python_exe(bot), "-m", "pip", "install",
                     "--quiet", "--upgrade", "pip"],
                    capture_output=True, timeout=120,
                )

            req = bot.path / "requirements.txt"
            if req.exists():
                bot.logs.append("📦 تثبيت requirements.txt...")
                r = subprocess.run(
                    [self._python_exe(bot), "-m", "pip", "install",
                     "--quiet", "-r", str(req)],
                    capture_output=True, text=True, timeout=480,
                )
                if r.returncode != 0:
                    bot.logs.append(f"⚠️ pip stderr:\n{r.stderr[-600:]}")
                else:
                    bot.logs.append("✅ requirements.txt مثبَّت")
            else:
                detected = self.detect_imports(bot)
                if detected:
                    bot.logs.append(f"🔍 مكتبات مكتشفة: {', '.join(detected)}")
                    r = subprocess.run(
                        [self._python_exe(bot), "-m", "pip", "install",
                         "--quiet", *detected],
                        capture_output=True, text=True, timeout=480,
                    )
                    if r.returncode == 0:
                        bot.logs.append("✅ مكتبات مثبَّتة")
                    else:
                        bot.logs.append(f"⚠️ {r.stderr[-500:]}")
                else:
                    bot.logs.append("ℹ️ لا مكتبات إضافية مطلوبة")

            if self._notifier:
                self._notifier.queue("install", bot, "✅ تم تثبيت البيئة")
            bot.status = "stopped"
            return True, "✅ البيئة جاهزة"
        except Exception as e:
            bot.status = "error"
            msg = f"❌ {e}"
            bot.logs.append(msg)
            return False, msg

    def reinstall_env(self, bot: BotInstance) -> tuple[bool, str]:
        """يعيد تثبيت البيئة من الصفر"""
        if bot.env_path.exists():
            shutil.rmtree(bot.env_path, ignore_errors=True)
            bot.logs.append("🗑 تم حذف البيئة القديمة")
        return self.setup_env(bot)

    # ══════════════════════════════════════════════════════
    #  Main file detection
    # ══════════════════════════════════════════════════════
    def find_main(self, bot: BotInstance) -> str:
        for n in ("main.py","bot.py","app.py","run.py","start.py","index.py"):
            if (bot.path / n).exists():
                return n
        for f in sorted(bot.path.glob("*.py")):
            return f.name
        return ""

    def list_py_files(self, bot: BotInstance) -> list[str]:
        return [str(f.relative_to(bot.path)) for f in sorted(bot.path.rglob("*.py"))
                if ".venv" not in f.parts]

    # ══════════════════════════════════════════════════════
    #  Process Start / Stop
    # ══════════════════════════════════════════════════════
    def start(self, bot_id: str) -> tuple[bool, str]:
        bot = self.bots.get(bot_id)
        if not bot:
            return False, "البوت غير موجود"
        if bot.status == "running":
            return False, "البوت يعمل بالفعل"
        if not bot.main_file:
            bot.main_file = self.find_main(bot)
        if not bot.main_file:
            return False, "❌ لا يوجد ملف Python رئيسي"
        main_path = bot.path / bot.main_file
        if not main_path.exists():
            return False, f"❌ الملف {bot.main_file} غير موجود"
        if not bot.env_path.exists():
            ok, m = self.setup_env(bot)
            if not ok:
                return False, m

        # بناء متغيرات البيئة
        env = os.environ.copy()
        if bot.token:
            env["BOT_TOKEN"] = bot.token
            env["TELEGRAM_BOT_TOKEN"] = bot.token
        # .env من مجلد البوت
        _ef = bot.path / ".env"
        if _ef.exists():
            for line in _ef.read_text("utf-8", errors="ignore").splitlines():
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, _, v = line.partition("=")
                    env[k.strip()] = v.strip()
        # متغيرات البيئة المخصصة (تأتي في الأولوية)
        for k, v in bot.env_vars.items():
            env[k] = v

        try:
            lf = open(bot.log_file, "a", encoding="utf-8", buffering=1)
            sep = f"\n{'─'*60}\n[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] ▶ START\n{'─'*60}\n"
            lf.write(sep)
            bot.process = subprocess.Popen(
                [self._python_exe(bot), str(main_path)],
                cwd=str(bot.path),
                env=env,
                stdout=lf,
                stderr=lf,
                text=True,
            )
            bot.pid        = bot.process.pid
            bot.status     = "running"
            bot.started_at = datetime.now()
            bot.logs.append(f"🚀 PID {bot.pid} | {bot.started_at.strftime('%H:%M:%S')}")
            self.save()
            threading.Thread(target=self._watch, args=(bot_id,), daemon=True).start()
            if self._notifier:
                self._notifier.queue("start", bot)
            logger.info(f"بدء تشغيل {bot.name} [{bot_id}] PID={bot.pid}")
            return True, f"✅ يعمل | PID: {bot.pid}"
        except Exception as e:
            bot.status = "error"
            logger.error(f"فشل تشغيل {bot.name}: {e}")
            return False, f"❌ {e}"

    def _kill(self, bot_id: str):
        bot = self.bots.get(bot_id)
        if not bot or not bot.process:
            return
        try:
            parent = psutil.Process(bot.pid)
            for c in parent.children(recursive=True):
                c.terminate()
            parent.terminate()
            try:
                bot.process.wait(timeout=6)
            except subprocess.TimeoutExpired:
                bot.process.kill()
                bot.process.wait(timeout=3)
        except Exception:
            pass
        bot.process = None
        bot.pid     = None

    def stop(self, bot_id: str) -> tuple[bool, str]:
        bot = self.bots.get(bot_id)
        if not bot:
            return False, "البوت غير موجود"
        if bot.status != "running":
            bot.status = "stopped"
            return True, "البوت متوقف بالفعل"
        self._kill(bot_id)
        bot.status = "stopped"
        bot.logs.append(f"⏹ أُوقف | {datetime.now().strftime('%H:%M:%S')}")
        self.save()
        if self._notifier:
            self._notifier.queue("stop", bot)
        logger.info(f"إيقاف {bot.name} [{bot_id}]")
        return True, "⏹ تم الإيقاف"

    def restart(self, bot_id: str) -> tuple[bool, str]:
        self.stop(bot_id)
        time.sleep(1.5)
        bot = self.bots.get(bot_id)
        if bot:
            bot.restarts += 1
        return self.start(bot_id)

    def _watch(self, bot_id: str):
        """يراقب العملية ويتحكم في إعادة التشغيل التلقائي"""
        bot = self.bots.get(bot_id)
        if not bot or not bot.process:
            return
        bot.process.wait()
        if bot.status != "running":
            return
        code = bot.process.returncode
        bot.logs.append(f"⚠️ العملية انتهت برمز {code}")
        logger.warning(f"{bot.name} [{bot_id}] انتهى برمز {code}")
        if bot.auto_restart and code != 0:
            bot.logs.append(f"🔄 إعادة تشغيل تلقائية خلال {AUTO_RESTART_DELAY}s...")
            if self._notifier:
                self._notifier.queue("crash", bot, f"رمز الخروج: {code}")
            time.sleep(AUTO_RESTART_DELAY)
            bot.status  = "stopped"
            bot.restarts += 1
            self.start(bot_id)
        else:
            bot.status = "stopped"
            self.save()
            if self._notifier:
                self._notifier.queue("stop", bot, f"توقف عادي (رمز {code})")

    # ══════════════════════════════════════════════════════
    #  Update (استبدال الكود)
    # ══════════════════════════════════════════════════════
    def update_code(self, bot: BotInstance, new_archive: Path) -> tuple[bool, str]:
        """يستبدل كود البوت بكود جديد مع الحفاظ على .env و .venv"""
        was_running = bot.status == "running"
        if was_running:
            self.stop(bot.bot_id)
            time.sleep(1)

        bot.status = "updating"
        bot.logs.append(f"🔄 تحديث الكود من {new_archive.name}")

        try:
            # حفظ نسخة احتياطية من .env
            env_backup = None
            ef = bot.path / ".env"
            if ef.exists():
                env_backup = ef.read_text("utf-8", errors="ignore")

            # حذف الملفات القديمة (مع الإبقاء على .venv)
            for item in list(bot.path.iterdir()):
                if item.name in (".venv", ".env"):
                    continue
                if item.is_dir():
                    shutil.rmtree(item)
                else:
                    item.unlink()

            # استخراج الجديد
            from utils.extractor import Extractor
            ok, err = Extractor.extract(new_archive, bot.path)
            if not ok:
                raise RuntimeError(err)

            # استعادة .env
            if env_backup:
                ef.write_text(env_backup, encoding="utf-8")

            # تحديث الملف الرئيسي
            bot.main_file = self.find_main(bot)
            bot.last_updated = datetime.now().isoformat()
            self.save()

            bot.logs.append("✅ تم تحديث الكود بنجاح")
            if self._notifier:
                self._notifier.queue("update", bot)

            if was_running:
                time.sleep(0.5)
                self.start(bot.bot_id)

            return True, "✅ تم التحديث بنجاح"
        except Exception as e:
            bot.status = "error"
            msg = f"❌ فشل التحديث: {e}"
            bot.logs.append(msg)
            return False, msg

    # ══════════════════════════════════════════════════════
    #  Stats
    # ══════════════════════════════════════════════════════
    def get_stats(self, bot_id: str) -> dict:
        bot = self.bots.get(bot_id)
        if not bot:
            return {}
        d = dict(
            status=bot.status, pid=bot.pid,
            restarts=bot.restarts, cpu=0.0, mem=0.0,
            uptime=bot.uptime_str,
        )
        if bot.pid and bot.status == "running":
            try:
                p = psutil.Process(bot.pid)
                d["cpu"] = round(p.cpu_percent(interval=0.1), 1)
                d["mem"] = round(p.memory_info().rss / 1024 / 1024, 1)
            except Exception:
                pass
        return d

    def system_stats(self) -> dict:
        mem  = psutil.virtual_memory()
        disk = psutil.disk_usage("/")
        cpu  = psutil.cpu_percent(interval=0.4)
        up   = datetime.now() - datetime.fromtimestamp(psutil.boot_time())
        h, r = divmod(int(up.total_seconds()), 3600)
        m, _ = divmod(r, 60)
        bots    = list(self.bots.values())
        running = [b for b in bots if b.status == "running"]
        total_mem = sum(self.get_stats(b.bot_id).get("mem", 0) for b in running)
        return dict(
            cpu=cpu,
            mem_used=round(mem.used / 1024**3, 2),
            mem_total=round(mem.total / 1024**3, 2),
            mem_pct=mem.percent,
            disk_used=round(disk.used / 1024**3, 1),
            disk_total=round(disk.total / 1024**3, 1),
            disk_pct=disk.percent,
            uptime=f"{h}h {m}m",
            bots_total=len(bots),
            bots_running=len(running),
            bots_mem=round(total_mem, 1),
        )

    # ══════════════════════════════════════════════════════
    #  Logs
    # ══════════════════════════════════════════════════════
    def get_logs(self, bot_id: str, n: int = 40, search: str = "") -> str:
        bot = self.bots.get(bot_id)
        if not bot:
            return "لا يوجد بوت بهذا الـ ID"
        lines: list[str] = []
        if bot.log_file.exists():
            try:
                lines = bot.log_file.read_text("utf-8", errors="ignore").splitlines()
            except Exception:
                pass
        if not lines:
            lines = list(bot.logs)
        if search:
            lines = [l for l in lines if search.lower() in l.lower()]
        return "\n".join(lines[-n:])

    def clear_logs(self, bot_id: str):
        bot = self.bots.get(bot_id)
        if not bot:
            return
        bot.logs.clear()
        try:
            bot.log_file.write_text("", encoding="utf-8")
        except Exception:
            pass

    # ══════════════════════════════════════════════════════
    #  Search & Filter
    # ══════════════════════════════════════════════════════
    def search(self, query: str = "", status: str = "") -> list[BotInstance]:
        result = list(self.bots.values())
        if query:
            q = query.lower()
            result = [
                b for b in result
                if q in b.name.lower()
                or q in b.bot_id.lower()
                or q in b.username.lower()
                or any(q in t.lower() for t in b.tags)
            ]
        if status and status != "all":
            result = [b for b in result if b.status == status]
        return result

    # ══════════════════════════════════════════════════════
    #  Env Vars
    # ══════════════════════════════════════════════════════
    def set_env_var(self, bot: BotInstance, key: str, value: str):
        bot.env_vars[key.upper()] = value
        self.save()

    def delete_env_var(self, bot: BotInstance, key: str) -> bool:
        if key.upper() in bot.env_vars:
            del bot.env_vars[key.upper()]
            self.save()
            return True
        return False
