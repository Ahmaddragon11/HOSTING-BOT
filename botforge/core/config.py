"""
core/config.py — إعدادات BotForge المركزية
"""

import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

# ── هوية البوت ────────────────────────────────────────────────
BOTFORGE_TOKEN: str = os.getenv("BOTFORGE_TOKEN", "8760554877:AAGGKSUL5dmtOU0uKT4vYnlpIpanTFTR1yA")
BOTFORGE_OWNER: int = int(os.getenv("BOTFORGE_OWNER", "8049455831"))

# ── المسارات ──────────────────────────────────────────────────
BASE_DIR   = Path(__file__).parent.parent
BOTS_DIR   = BASE_DIR / "hosted_bots"
LOGS_DIR   = BASE_DIR / "botforge_logs"
DATA_DIR   = BASE_DIR / "data"
TMP_DIR    = BASE_DIR / ".tmp"

STATE_FILE    = DATA_DIR / "state.json"
SCHEDULE_FILE = DATA_DIR / "schedules.json"
NOTIF_FILE    = DATA_DIR / "notifications.json"
ENV_VARS_FILE = DATA_DIR / "env_vars.json"

# إنشاء المجلدات
for _d in (BOTS_DIR, LOGS_DIR, DATA_DIR, TMP_DIR):
    _d.mkdir(parents=True, exist_ok=True)

# ── ثوابت البوت ───────────────────────────────────────────────
VERSION = "4.0"
MAX_LOG_LINES     = 500
DEFAULT_LOG_TAIL  = 40
AUTO_RESTART_DELAY = 4   # ثوانٍ
MAX_RESTARTS_TRACK = 100

# ── حالات الـ Conversation ────────────────────────────────────
(
    ST_FILE, ST_NAME, ST_TOKEN,
    ST_SC_VALUE,
    ST_BC_VALUE,
    ST_ENV_KEY, ST_ENV_VAL,
    ST_SCHEDULE_BOT, ST_SCHEDULE_ACTION, ST_SCHEDULE_TIME,
    ST_UPDATE_FILE,
    ST_SEARCH,
) = range(12)

# ── رموز الحالات ──────────────────────────────────────────────
STATUS_EMOJI = {
    "running":    "🟢",
    "stopped":    "🔴",
    "error":      "🟠",
    "installing": "🔵",
    "updating":   "🟡",
}

# ── إعدادات الإشعارات الافتراضية ─────────────────────────────
DEFAULT_NOTIF_SETTINGS = {
    "on_start":   True,
    "on_stop":    True,
    "on_error":   True,
    "on_crash":   True,
    "on_update":  True,
    "on_install": False,
}
