"""状态管理 — 读取与写入 state.json."""

import os

VALID_PHASES = [
    "product_discovery",
    "planning",
    "execution",
    "iteration_review",
    "iteration_polishing",
    "backlog_update",
    "requirements_revision",
    "milestone_delivery",
    "done",
]

VALID_TASK_STATUSES = ["pending", "in_progress", "done", "blocked"]

STATE_DIR = ".project_ai"
STATE_FILE = "state.json"


def find_project_root():
    """从当前目录向上查找 .project_ai/ 目录。"""
    cwd = os.getcwd()
    # 从当前目录出发，逐级向上查找 .project_ai/
    search = os.path.abspath(cwd)
    while True:
        if os.path.isdir(os.path.join(search, STATE_DIR)):
            return search
        parent = os.path.dirname(search)
        if parent == search:
            # 到达文件系统根目录，回退到当前工作目录
            break
        search = parent
    return cwd


def state_path(cwd):
    return os.path.join(cwd, STATE_DIR, STATE_FILE)


def load_state(cwd):
    """加载并返回 state.json 内容。"""
    path = state_path(cwd)
    if not os.path.isfile(path):
        return None
    import json
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_state(cwd, data):
    """保存 state.json。"""
    path = state_path(cwd)
    import json
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def default_state():
    """返回初始 state.json 内容。"""
    from datetime import datetime, timezone
    return {
        "schema_version": "2.0.0",
        "skill_version": "5.5.1",
        "phase": "product_discovery",
        "current_step": 1,
        "target_step": "iteration_complete",
        "current_iteration": 0,
        "current_iteration_goal": "",
        "product_vision": {},
        "product_backlog": [],
        "iteration_tasks": [],
        "completed_iterations": [],
        "decisions": {},
        "task_status": {},
        "last_error": None,
        "last_modified": datetime.now(timezone.utc).isoformat(),
        "environment_fingerprint": "",
    }
