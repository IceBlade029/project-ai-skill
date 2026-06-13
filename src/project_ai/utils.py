"""工具函数 — ISO 时间、备份目录等."""

import os
import shutil
from datetime import datetime, timezone


def now_iso():
    """返回当前 ISO 时间字符串。"""
    return datetime.now(timezone.utc).isoformat()


def timestamp_tag():
    """返回 YYYYMMDD_HHMMSS 格式的时间戳。"""
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def backup_dir(dir_path):
    """备份整个目录。"""
    if not os.path.isdir(dir_path):
        return None
    backup_path = f"{dir_path}_backup_{timestamp_tag()}"
    shutil.copytree(dir_path, backup_path)
    return backup_path


def ensure_dir(path):
    """确保目录存在。"""
    os.makedirs(path, exist_ok=True)
    return path
