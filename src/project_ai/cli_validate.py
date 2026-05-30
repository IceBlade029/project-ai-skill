"""validate 命令 — 校验 state.json 完整性."""

import os
from project_ai.state import (
    STATE_DIR,
    STATE_FILE,
    load_state,
    VALID_PHASES,
    VALID_TASK_STATUSES,
)

REQUIRED_FIELDS = [
    "schema_version",
    "skill_version",
    "phase",
    "current_step",
    "current_iteration",
    "current_iteration_goal",
    "product_vision",
    "product_backlog",
    "iteration_tasks",
    "completed_iterations",
    "decisions",
    "task_status",
    "last_error",
    "last_modified",
]


def run(cwd):
    errors = []
    warnings = []

    # 1. 检查 .project_ai/ 目录
    target_dir = os.path.join(cwd, STATE_DIR)
    if not os.path.isdir(target_dir):
        return {
            "ok": False,
            "error_code": "PROJECT_AI_NOT_INITIALIZED",
            "message": "No .project_ai directory found. Run project-ai init first.",
            "errors": [],
            "warnings": [],
        }

    # 2. 检查 state.json 是否存在
    state_path = os.path.join(target_dir, STATE_FILE)
    if not os.path.isfile(state_path):
        return {
            "ok": False,
            "error_code": "STATE_NOT_FOUND",
            "message": f"state.json 不存在。项目可能已损坏。",
            "errors": [f"{STATE_FILE} 不存在"],
            "warnings": [],
        }

    # 3. 检查是否可解析
    state = load_state(cwd)
    if state is None:
        return {
            "ok": False,
            "error_code": "STATE_PARSE_ERROR",
            "message": "state.json 无法解析为合法 JSON。",
            "errors": ["state.json JSON 解析失败"],
            "warnings": [],
        }

    # 4. 检查必填字段
    for field in REQUIRED_FIELDS:
        if field not in state:
            errors.append(f"缺少必填字段: {field}")

    # 5. 检查 phase
    phase = state.get("phase", "")
    if phase not in VALID_PHASES:
        errors.append(f"phase 值 '{phase}' 不合法。允许值：{VALID_PHASES}")

    # 6. 检查 task_status
    task_status = state.get("task_status", {})
    if not isinstance(task_status, dict):
        errors.append("task_status 必须是对象（dict）")
    else:
        for tid, tstatus in task_status.items():
            if tstatus not in VALID_TASK_STATUSES:
                errors.append(f"task_status['{tid}'] 值 '{tstatus}' 不合法。允许值：{VALID_TASK_STATUSES}")

    # 7. 检查 current_iteration 合理性
    current_iter = state.get("current_iteration", 0)
    if not isinstance(current_iter, int) or current_iter < 0:
        errors.append(f"current_iteration 必须是非负整数，当前值：{current_iter}")

    # 8. 检查 iteration_tasks 与 task_status 一致性
    iteration_tasks = state.get("iteration_tasks", [])
    if isinstance(iteration_tasks, list) and isinstance(task_status, dict):
        task_ids_in_tasks = {t.get("id") for t in iteration_tasks if isinstance(t, dict)}
        task_ids_in_status = set(task_status.keys())

        extra_in_status = task_ids_in_status - task_ids_in_tasks
        missing_in_status = task_ids_in_tasks - task_ids_in_status

        if extra_in_status:
            warnings.append(f"task_status 中存在不在 iteration_tasks 里的任务 ID：{extra_in_status}")
        if missing_in_status:
            warnings.append(f"iteration_tasks 中的任务在 task_status 中缺少状态：{missing_in_status}")

    # 9. 检查 completed_iterations
    completed = state.get("completed_iterations", [])
    if isinstance(completed, list) and current_iter > 0:
        completed_nums = [c.get("iteration", 0) for c in completed if isinstance(c, dict)]
        if current_iter > 0 and current_iter not in completed_nums and phase == "done":
            pass  # 最终交付时可以不记录在 completed_iterations

    return {
        "ok": len(errors) == 0,
        "errors": errors,
        "warnings": warnings,
        "phase": phase,
        "current_iteration": current_iter,
        "message": "校验通过" if len(errors) == 0 else f"发现 {len(errors)} 个错误，{len(warnings)} 个警告",
    }
