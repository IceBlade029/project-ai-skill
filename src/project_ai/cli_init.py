"""init 命令 — 初始化 .project_ai/ 目录."""

import os
import shutil
from project_ai.state import STATE_DIR, default_state, save_state
from project_ai.utils import backup_dir, ensure_dir, now_iso

DIRS = [
    "requirements",
    "confirmations",
    os.path.join("plans", "iteration_plans"),
    "task_reports",
    "quality_gates",
    "iteration_reports",
    "delivery",
    # ---- v5.0.0 TDD directories ----
    os.path.join("specs", "bdd"),
    os.path.join("specs", "rules"),
    os.path.join("tdd", "tasks"),
    os.path.join("tdd", "coverage"),
    os.path.join("tdd", "reviews"),
    os.path.join("tdd", "red-runs"),
    os.path.join("tdd", "approvals"),
    os.path.join("tdd", "implementation-reports"),
    os.path.join("tdd", "blockers"),
    os.path.join("tdd", "open-questions"),
    # ---- v5.3.0 变异注入与 E2E 目录 ----
    os.path.join("tdd", "mutation-results"),
    os.path.join("tdd", "e2e-results"),
    # ---- v5.4.0 Spec Compliance Review 目录 ----
    os.path.join("tdd", "spec-compliance"),
    # ---- v5.5.0 Cheating Probe 独立路径与阶段封存清单目录 ----
    os.path.join("tdd", "cheating-probe-results"),
    os.path.join("tdd", "manifests"),
]


def run(args, cwd=None):
    if cwd is None:
        cwd = os.getcwd()
    target = os.path.join(cwd, STATE_DIR)

    if os.path.exists(target):
        if args.force:
            backup = backup_dir(target)
            shutil.rmtree(target)
            return _create(cwd, f"已备份旧目录到 {backup}")
        else:
            return {
                "ok": False,
                "error_code": "ALREADY_INITIALIZED",
                "message": f".project_ai/ 已存在。使用 --force 强制重新初始化（会自动备份旧目录）。",
            }

    return _create(cwd, None)


def _create(cwd, note):
    target = os.path.join(cwd, STATE_DIR)
    ensure_dir(target)

    for d in DIRS:
        ensure_dir(os.path.join(target, d))

    # dev_log.md
    log_path = os.path.join(target, "dev_log.md")
    with open(log_path, "w", encoding="utf-8") as f:
        f.write(f"# 开发日志\n\n初始化时间：{now_iso()}\n\n")

    # state.json
    state = default_state()
    save_state(cwd, state)

    result = {
        "ok": True,
        "project_ai_path": target,
        "created_dirs": [target] + [os.path.join(target, d) for d in DIRS],
        "state": state,
    }
    if note:
        result["note"] = note
    return result
