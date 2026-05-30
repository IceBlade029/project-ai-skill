"""工具函数 — ISO 时间、备份、哈希等."""

import os
import hashlib
import shutil
from datetime import datetime, timezone


def now_iso():
    """返回当前 ISO 时间字符串。"""
    return datetime.now(timezone.utc).isoformat()


def timestamp_tag():
    """返回 YYYYMMDD_HHMMSS 格式的时间戳。"""
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def file_hash(path):
    """返回文件的 SHA-256 哈希。"""
    if not os.path.isfile(path):
        return None
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def backup_file(path):
    """备份文件，加上时间戳后缀。"""
    if not os.path.isfile(path):
        return None
    backup_path = f"{path}.backup.{timestamp_tag()}"
    shutil.copy2(path, backup_path)
    return backup_path


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
