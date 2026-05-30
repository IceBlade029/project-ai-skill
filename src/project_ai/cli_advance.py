"""advance 命令 — 状态推进引擎."""

import os
from project_ai.state import STATE_DIR, load_state, save_state
from project_ai.utils import backup_file, now_iso

# 合法状态转换表（v5.2.0 精简版：10 条转换）
TRANSITIONS = {
    ("product_discovery", "product_vision_confirmed"): "planning",
    ("planning", "planning_confirmed"): "execution",
    ("execution", "all_tasks_done"): "iteration_review",
    ("iteration_review", "review_done"): "iteration_polishing",
    ("iteration_polishing", "polishing_done"): "backlog_update",
    ("backlog_update", "next_iteration"): "planning",
    ("backlog_update", "continue_current_iteration"): "iteration_polishing",
    ("backlog_update", "requirements_revision"): "requirements_revision",
    ("requirements_revision", "requirements_revision_done"): "backlog_update",
    ("backlog_update", "milestone_delivery"): "milestone_delivery",
    ("milestone_delivery", "delivery_done"): "backlog_update",
}

# v5.2.0 向后兼容：旧 phase 名 → 新 phase 名
_COMPAT_PHASE_MAP = {
    "backlog_planning": "planning",
    "iteration_planning": "planning",
    "next_iteration_scope": "planning",
    "iteration_audit": "iteration_review",
    "skill_generation": "planning",
    "init": "product_discovery",
}

# 向后兼容：旧 event 名 → 新 event 名
_COMPAT_EVENT_MAP = {
    "backlog_confirmed": "planning_confirmed",
    "iteration_plan_confirmed": "planning_confirmed",
    "execution_started": "planning_confirmed",
    "audit_done": "review_done",
}


def run(cwd, event):
    target_dir = os.path.join(cwd, STATE_DIR)
    if not os.path.isdir(target_dir):
        return {
            "ok": False,
            "error_code": "PROJECT_AI_NOT_INITIALIZED",
            "message": "No .project_ai directory found. Run project-ai init first.",
        }

    state = load_state(cwd)
    if state is None:
        return {
            "ok": False,
            "error_code": "STATE_NOT_FOUND",
            "message": "state.json 不存在或无法解析。",
        }

    current_phase = state.get("phase", "unknown")

    # 向后兼容：自动迁移旧 phase 名
    if current_phase in _COMPAT_PHASE_MAP:
        current_phase = _COMPAT_PHASE_MAP[current_phase]

    # 向后兼容：自动迁移旧 event 名
    if event in _COMPAT_EVENT_MAP:
        event = _COMPAT_EVENT_MAP[event]

    key = (current_phase, event)

    if key not in TRANSITIONS:
        possible_events = [e for (p, e) in TRANSITIONS if p == current_phase]
        return {
            "ok": False,
            "error_code": "INVALID_PHASE_TRANSITION",
            "message": f"Cannot apply event '{event}' when phase is '{current_phase}'.",
            "current_phase": current_phase,
            "event": event,
            "allowed_events": possible_events,
        }

    new_phase = TRANSITIONS[key]

    # 备份 state.json
    state_path = os.path.join(target_dir, "state.json")
    backup_file(state_path)

    # 特殊处理各事件
    if event == "product_vision_confirmed":
        state["current_step"] = 2

    elif event == "planning_confirmed":
        state["current_step"] = 3
        if state.get("current_iteration", 0) == 0:
            state["current_iteration"] = 1

    elif event == "all_tasks_done":
        state["current_step"] = 4
        state["current_iteration_goal"] = (
            f"{state.get('current_iteration_goal', '')} (已完成)"
        )

    elif event == "review_done":
        state["current_step"] = 5

    elif event == "polishing_done":
        state["current_step"] = 6
        completed = state.get("completed_iterations", [])
        current_iter = state.get("current_iteration", 0)
        # 避免重复记录同一轮
        already_recorded = any(
            isinstance(c, dict) and c.get("iteration") == current_iter
            for c in completed
        )
        if not already_recorded:
            completed.append({
                "iteration": current_iter,
                "goal": state.get("current_iteration_goal", ""),
                "completed_at": now_iso(),
            })
            state["completed_iterations"] = completed

    elif event == "next_iteration":
        state["current_iteration"] += 1
        state["iteration_tasks"] = []
        state["task_status"] = {}
        state["current_step"] = 2

    elif event == "continue_current_iteration":
        state["current_step"] = 5

    elif event == "requirements_revision":
        state["current_step"] = 7

    elif event == "requirements_revision_done":
        state["current_step"] = 6

    elif event == "milestone_delivery":
        state["current_step"] = 8

    elif event == "delivery_done":
        state["current_step"] = 6

    # 更新 phase 和时间
    state["phase"] = new_phase
    state["last_modified"] = now_iso()

    # 保存
    save_state(cwd, state)

    return {
        "ok": True,
        "previous_phase": current_phase,
        "new_phase": new_phase,
        "event": event,
        "message": f"状态已从 '{current_phase}' 推进到 '{new_phase}'（事件：{event}）",
    }
