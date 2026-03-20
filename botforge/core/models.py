"""
core/models.py — نموذج بيانات BotInstance
"""

from __future__ import annotations
import subprocess
from pathlib import Path
from datetime import datetime
from collections import deque
from typing import Optional

from core.config import LOGS_DIR, MAX_LOG_LINES, STATUS_EMOJI


class BotInstance:
    """يمثل بوتاً مستضافاً واحداً"""

    __slots__ = (
        "bot_id",
        "name",
        "path",
        "token",
        "main_file",
        "process",
        "pid",
        "started_at",
        "status",
        "restarts",
        "auto_restart",
        "logs",
        "log_file",
        "env_path",
        "username",
        "description",
        "about",
        "env_vars",
        "tags",
        "created_at",
        "last_updated",
    )

    def __init__(self, bot_id: str, name: str, path: Path, token: str = ""):
        self.bot_id = bot_id
        self.name = name
        self.path = path
        self.token = token
        self.main_file = ""
        self.process: Optional[subprocess.Popen] = None
        self.pid: Optional[int] = None
        self.started_at: Optional[datetime] = None
        self.status = "stopped"
        self.restarts = 0
        self.auto_restart = True
        self.logs: deque = deque(maxlen=MAX_LOG_LINES)
        self.log_file = LOGS_DIR / f"{bot_id}.log"
        self.env_path = path / ".venv"
        self.username = ""
        self.description = ""
        self.about = ""
        self.env_vars: dict[str, str] = {}  # متغيرات بيئة مخصصة
        self.tags: list[str] = []  # وسوم للتصفية
        self.created_at = datetime.now().isoformat()
        self.last_updated = self.created_at

    @property
    def status_emoji(self) -> str:
        return STATUS_EMOJI.get(self.status, "⚪")

    @property
    def uptime_seconds(self) -> int:
        if self.started_at and self.status == "running":
            return int((datetime.now() - self.started_at).total_seconds())
        return 0

    @property
    def uptime_str(self) -> str:
        sec = self.uptime_seconds
        if sec == 0:
            return ""
        h, r = divmod(sec, 3600)
        m, s = divmod(r, 60)
        return f"{h:02d}:{m:02d}:{s:02d}"

    def to_dict(self) -> dict:
        return dict(
            bot_id=self.bot_id,
            name=self.name,
            path=str(self.path),
            token=self.token,
            main_file=self.main_file,
            auto_restart=self.auto_restart,
            restarts=self.restarts,
            status="stopped",
            username=self.username,
            description=self.description,
            about=self.about,
            env_vars=self.env_vars,
            tags=self.tags,
            created_at=self.created_at,
            last_updated=self.last_updated,
        )

    @classmethod
    def from_dict(cls, d: dict) -> "BotInstance":
        b = cls(d["bot_id"], d["name"], Path(d["path"]), d.get("token", ""))
        b.main_file = d.get("main_file", "")
        b.auto_restart = d.get("auto_restart", True)
        b.restarts = d.get("restarts", 0)
        b.username = d.get("username", "")
        b.description = d.get("description", "")
        b.about = d.get("about", "")
        b.env_vars = d.get("env_vars", {})
        b.tags = d.get("tags", [])
        b.created_at = d.get("created_at", datetime.now().isoformat())
        b.last_updated = d.get("last_updated", b.created_at)
        return b

    def summary_line(
        self, show_stats: bool = False, cpu: float = 0, mem: float = 0
    ) -> str:
        e = self.status_emoji
        up = f"  ⏱`{self.uptime_str}`" if self.uptime_str else ""
        mb = f"  💾`{mem:.0f}MB`" if mem else ""
        return f"{e} *{self.name}* `[{self.bot_id}]`{up}{mb}"
