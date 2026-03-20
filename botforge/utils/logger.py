"""
utils/logger.py — إعداد نظام السجلات المركزي
"""

import logging
from core.config import LOGS_DIR


def setup_logging():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        handlers=[
            logging.FileHandler(LOGS_DIR / "botforge_main.log", encoding="utf-8"),
            logging.StreamHandler(),
        ],
    )
    for noisy in ("httpx", "telegram", "httpcore", "apscheduler"):
        logging.getLogger(noisy).setLevel(logging.WARNING)
