"""
utils/extractor.py — استخراج ملفات البوتات المضغوطة
"""

import shutil
import zipfile
import tarfile
from pathlib import Path


class Extractor:
    ALLOWED_EXTS = (".zip", ".tar.gz", ".tgz", ".tar.bz2", ".tar", ".py")

    @staticmethod
    def is_allowed(name: str) -> bool:
        n = name.lower()
        return any(n.endswith(e) for e in Extractor.ALLOWED_EXTS)

    @staticmethod
    def extract(src: Path, dest: Path) -> tuple[bool, str]:
        dest.mkdir(parents=True, exist_ok=True)
        n = src.name.lower()
        try:
            if n.endswith(".zip"):
                with zipfile.ZipFile(src) as zf:
                    zf.extractall(dest)
            elif any(n.endswith(e) for e in (".tar.gz", ".tgz", ".tar.bz2", ".tar")):
                with tarfile.open(src) as tf:
                    tf.extractall(dest)
            elif n.endswith(".py"):
                shutil.copy(src, dest / src.name)
            else:
                return False, "نوع الملف غير مدعوم (.zip, .tar.gz, .py)"
        except (zipfile.BadZipFile, tarfile.TarError) as e:
            return False, f"الملف تالف: {e}"
        except Exception as e:
            return False, str(e)

        # رفع المستوى إذا كان مجلداً وحيداً داخل المجلد
        entries = list(dest.iterdir())
        if len(entries) == 1 and entries[0].is_dir():
            inner = entries[0]
            for item in list(inner.iterdir()):
                t = dest / item.name
                if t.exists():
                    shutil.rmtree(t) if t.is_dir() else t.unlink()
                shutil.move(str(item), str(t))
            inner.rmdir()
        return True, "تم الاستخراج"
