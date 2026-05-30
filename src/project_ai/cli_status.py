"""status 命令 — 读取并输出当前状态."""

import os
from project_ai.state import STATE_DIR, STATE_FILE, load_state, VALID_PHASES


def run(cwd):
    target = os.path.join(cwd, STATE_DIR)

    if not os.path.isdir(target):
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
            "message": f".project_ai/{STATE_FILE} 不存在或无法解析。请检查项目是否已初始化。",
        }

    phase = state.get("phase", "unknown")
    phase_ok = phase in VALID_PHASES

    if not phase_ok:
        return {
            "ok": False,
            "error_code": "INVALID_PHASE",
            "message": f"state.json 中的 phase 值 '{phase}' 不合法。允许值：{VALID_PHASES}",
            "phase": phase,
        }

    # 计算允许的动作和阻塞问题
    allowed_actions, blocking_issues, next_human_action = _analyze_state(state)

    # 收集相关文件
    relevant_files = _collect_relevant_files(cwd, state)

    return {
        "ok": True,
        "phase": phase,
        "current_step": state.get("current_step"),
        "current_iteration": state.get("current_iteration", 0),
        "current_iteration_goal": state.get("current_iteration_goal", ""),
        "target_step": state.get("target_step", ""),
        "allowed_actions": allowed_actions,
        "blocking_issues": blocking_issues,
        "next_human_action": next_human_action,
        "relevant_files": relevant_files,
    }


def _analyze_state(state):
    """分析当前状态，返回允许的动作、阻塞问题和下一步建议。"""
    phase = state.get("phase", "unknown")
    allowed = []
    blocking = []
    next_action = ""

    if phase == "product_discovery":
        allowed = ["product_vision_confirmed"]
        next_action = "请在 .project_ai/requirements/ 下放入需求文档，然后让 AI 分析需求并生成确认文档。"

    elif phase == "planning":
        allowed = ["planning_confirmed"]
        n = state.get("current_iteration", 0)
        if n < 1:
            next_action = "请审阅 AI 生成的 Backlog 和首轮迭代计划确认文档。"
        else:
            next_action = "请审阅 AI 生成的本轮迭代计划确认文档。"

    elif phase == "execution":
        allowed = ["all_tasks_done"]
        tasks = state.get("iteration_tasks", [])
        task_status = state.get("task_status", {})
        pending = [t for t in tasks if task_status.get(t.get("id"), "pending") != "done"]
        if pending:
            next_action = f"还有 {len(pending)} 个任务未完成。运行 project-ai task next --json 获取下一个任务。"
        else:
            next_action = "所有任务已完成。运行 project-ai advance --event all_tasks_done --json 进入复盘阶段。"

    elif phase == "iteration_review":
        allowed = ["review_done"]
        next_action = "请让 AI 基于 git diff 和任务完成情况生成复盘报告和接口契约。"

    elif phase == "iteration_polishing":
        allowed = ["polishing_done"]
        next_action = '请在对话中直接描述你测试时发现的问题，AI 会自动记录并分类。如果无更多问题请说"打磨完成"。'

    elif phase == "backlog_update":
        allowed = ["next_iteration", "continue_current_iteration", "requirements_revision", "milestone_delivery"]
        next_action = "请填写 .project_ai/confirmations/next_action_confirm.md 并运行 confirm 确认。"

    elif phase == "requirements_revision":
        allowed = ["requirements_revision_done"]
        next_action = "请审阅 .project_ai/confirmations/requirements_revision_confirm.md 中的需求修订分析，填写确认项后重新运行本 Skill。"

    elif phase == "milestone_delivery":
        allowed = ["delivery_done"]
        next_action = "请让 AI 生成阶段性交付报告。"

    elif phase == "done":
        allowed = []
        next_action = "项目已完成。感谢使用！"

    return allowed, blocking, next_action


def _collect_relevant_files(cwd, state):
    """收集当前阶段相关文件列表。"""
    base = os.path.join(cwd, STATE_DIR)
    files = []

    candidates = [
        "state.json",
        "dev_log.md",
    ]

    phase = state.get("phase", "")
    n = state.get("current_iteration", 0)

    if phase in ("product_discovery",):
        candidates.append("confirmations/product_vision_confirm.md")

    if phase in ("planning",):
        candidates.extend([
            "confirmations/product_vision_confirm.md",
            "confirmations/iteration_plan_confirm.md",
            "plans/product_vision.md",
            "plans/product_backlog.json",
            "plans/tech_stack.md",
            f"plans/iteration_plans/iteration_{n}.md",
            f"plans/iteration_plans/iteration_{n}_tasks.json",
        ])

    if phase in ("execution",):
        candidates.append(f"plans/iteration_plans/iteration_{n}_tasks.json")

    if phase in ("iteration_review",):
        if n >= 1:
            candidates.append(f"iteration_reports/iteration_{n}_review.md")
            candidates.append(f"iteration_reports/iteration_{n}_interface_spec.md")

    if phase in ("iteration_polishing",):
        candidates.append("confirmations/polishing_issues_confirm.md")
        if n >= 1:
            candidates.extend([
                f"iteration_reports/iteration_{n}_review.md",
                f"iteration_reports/iteration_{n}_interface_spec.md",
            ])

    if phase in ("backlog_update",):
        candidates.append("confirmations/next_action_confirm.md")

    if phase in ("requirements_revision",):
        candidates.append("confirmations/requirements_revision_confirm.md")
        candidates.extend([
            "plans/product_vision.md",
            "plans/product_backlog.json",
        ])
        if n >= 1:
            candidates.append(f"iteration_reports/iteration_{n}_interface_spec.md")

    if phase in ("milestone_delivery",):
        candidates.append("delivery/milestone_delivery_report.md")

    for f in candidates:
        full = os.path.join(base, f)
        if os.path.exists(full):
            files.append(f".project_ai/{f}")

    return files
