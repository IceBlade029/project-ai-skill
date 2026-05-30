"""任务管理 — next / context / complete / sync."""

import os
import json
from project_ai.state import STATE_DIR, load_state, save_state
from project_ai.utils import backup_file, now_iso


def sync_tasks(cwd):
    """把 iteration_<N>_tasks.json 同步到 state.json 的 iteration_tasks。

    来源文件：.project_ai/plans/iteration_plans/iteration_<N>_tasks.json
    写入字段：state.json → iteration_tasks, task_status
    """
    state = load_state(cwd)
    if state is None:
        return {
            "ok": False,
            "error_code": "STATE_NOT_FOUND",
            "message": "state.json 不存在或无法解析。",
        }

    n = state.get("current_iteration", 0)
    if n < 1:
        return {
            "ok": False,
            "error_code": "NO_CURRENT_ITERATION",
            "message": "current_iteration 为 0，尚无迭代。请先完成 Backlog 规划并确认迭代计划。",
        }

    tasks_path = os.path.join(
        cwd, STATE_DIR, "plans", "iteration_plans", f"iteration_{n}_tasks.json"
    )

    if not os.path.isfile(tasks_path):
        return {
            "ok": False,
            "error_code": "TASKS_FILE_NOT_FOUND",
            "message": f"任务文件不存在: .project_ai/plans/iteration_plans/iteration_{n}_tasks.json",
        }

    try:
        with open(tasks_path, "r", encoding="utf-8") as f:
            tasks = json.load(f)
    except (json.JSONDecodeError, OSError) as e:
        return {
            "ok": False,
            "error_code": "TASKS_FILE_PARSE_ERROR",
            "message": f"任务文件无法解析: {e}",
        }

    if not isinstance(tasks, list):
        return {
            "ok": False,
            "error_code": "TASKS_FORMAT_ERROR",
            "message": "任务文件内容必须是 JSON 数组。",
        }

    # 校验每个任务的基本结构
    for i, t in enumerate(tasks):
        if not isinstance(t, dict):
            return {
                "ok": False,
                "error_code": "TASKS_FORMAT_ERROR",
                "message": f"第 {i} 个任务不是有效的 JSON 对象。",
            }
        if "id" not in t:
            return {
                "ok": False,
                "error_code": "TASKS_FORMAT_ERROR",
                "message": f"第 {i} 个任务缺少 id 字段。",
            }

    # 备份 state.json
    backup_file(os.path.join(cwd, STATE_DIR, "state.json"))

    # 同步
    state["iteration_tasks"] = tasks
    state["task_status"] = {t["id"]: "pending" for t in tasks}
    state["last_modified"] = now_iso()
    save_state(cwd, state)

    return {
        "ok": True,
        "iteration": n,
        "synced_count": len(tasks),
        "task_ids": [t["id"] for t in tasks],
        "message": f"已将迭代 {n} 的 {len(tasks)} 个任务同步到 state.json。",
    }


def next_task(cwd):
    """返回下一个可执行任务。"""
    target_dir = os.path.join(cwd, STATE_DIR)
    if not os.path.isdir(target_dir):
        return {
            "ok": False,
            "error_code": "PROJECT_AI_NOT_INITIALIZED",
            "message": "No .project_ai directory found.",
        }

    state = load_state(cwd)
    if state is None:
        return {
            "ok": False,
            "error_code": "STATE_NOT_FOUND",
            "message": "state.json 不存在或无法解析。",
        }

    iteration_tasks = state.get("iteration_tasks", [])
    task_status = state.get("task_status", {})

    if not iteration_tasks:
        return {
            "ok": True,
            "has_next": False,
            "task": None,
            "instruction": "当前没有迭代任务。请先完成迭代规划。",
        }

    # 找到阻塞任务
    blocked = []
    for t in iteration_tasks:
        tid = t.get("id", "")
        if task_status.get(tid) == "blocked":
            blocked.append(t)

    if blocked:
        return {
            "ok": True,
            "has_next": True,
            "task": blocked[0],
            "blocked_tasks": [t.get("id") for t in blocked],
            "instruction": f"任务 {blocked[0].get('id')} 处于 blocked 状态，需要先解决阻塞原因。",
        }

    # 找到下一个可执行任务（依赖已满足且为 pending）
    done_ids = {tid for tid, s in task_status.items() if s == "done"}
    done_ids.add(None)  # 空依赖视为已满足

    for t in iteration_tasks:
        tid = t.get("id", "")
        if task_status.get(tid, "pending") != "pending":
            continue
        deps = set(t.get("dependencies", []))
        if deps.issubset(done_ids):
            return {
                "ok": True,
                "has_next": True,
                "task": t,
                "instruction": f"Run project-task-runner for task {tid}.",
            }

    # 所有任务 done
    all_done = all(task_status.get(t.get("id"), "pending") == "done" for t in iteration_tasks)
    if all_done:
        return {
            "ok": True,
            "has_next": False,
            "task": None,
            "instruction": "所有任务已完成。运行 project-ai advance --event all_tasks_done --json 进入审计阶段。",
        }

    # 有任务但依赖未满足（理论上不应该到这里，但防御性处理）
    return {
        "ok": True,
        "has_next": False,
        "task": None,
        "instruction": "存在未完成任务，但它们的依赖尚未满足。请检查任务依赖关系。",
    }


def task_context(cwd, task_id):
    """生成指定任务的上下文。"""
    state = load_state(cwd)
    if state is None:
        return {
            "ok": False,
            "error_code": "STATE_NOT_FOUND",
            "message": "state.json 不存在或无法解析。",
        }

    iteration_tasks = state.get("iteration_tasks", [])
    task = None
    for t in iteration_tasks:
        if t.get("id") == task_id:
            task = t
            break

    if task is None:
        return {
            "ok": False,
            "error_code": "TASK_NOT_FOUND",
            "message": f"任务 {task_id} 不在当前迭代的任务列表中。",
        }

    n = state.get("current_iteration", 0)

    # 上一轮接口契约
    prev_spec = None
    if n > 1:
        spec_path = os.path.join(
            cwd, STATE_DIR, "iteration_reports", f"iteration_{n - 1}_interface_spec.md"
        )
        if os.path.isfile(spec_path):
            prev_spec = f".project_ai/iteration_reports/iteration_{n - 1}_interface_spec.md"

    # 收集已完成任务的预期文件
    task_status = state.get("task_status", {})
    done_ids = {tid for tid, s in task_status.items() if s == "done"}
    context_files = []

    # 检查是否有 dev_log
    if os.path.isfile(os.path.join(cwd, STATE_DIR, "dev_log.md")):
        context_files.append(".project_ai/dev_log.md")

    # 检查是否有技术栈文档
    if os.path.isfile(os.path.join(cwd, STATE_DIR, "plans", "tech_stack.md")):
        context_files.append(".project_ai/plans/tech_stack.md")

    # 如果有上一轮接口契约
    if prev_spec:
        context_files.append(prev_spec)

    return {
        "ok": True,
        "task_id": task_id,
        "iteration": n,
        "current_iteration_goal": state.get("current_iteration_goal", ""),
        "task": task,
        "allowed_files": task.get("expected_files", []),
        "forbidden_files": [
            ".project_ai/state.json",
        ],
        "context_files": context_files,
        "expected_files": task.get("expected_files", []),
        "quality_gates": task.get("quality_gates", []),
        "tdd": task.get("tdd", None),
        "previous_interface_spec": prev_spec,
    }


def complete_task(cwd, task_id):
    """验证并完成指定任务。"""
    state = load_state(cwd)
    if state is None:
        return {
            "ok": False,
            "error_code": "STATE_NOT_FOUND",
            "message": "state.json 不存在或无法解析。",
        }

    # 1. 检查任务是否存在
    iteration_tasks = state.get("iteration_tasks", [])
    task = None
    for t in iteration_tasks:
        if t.get("id") == task_id:
            task = t
            break

    if task is None:
        return {
            "ok": False,
            "error_code": "TASK_NOT_FOUND",
            "message": f"任务 {task_id} 不在当前迭代的任务列表中。",
        }

    n = state.get("current_iteration", 0)

    # 2. 检查任务报告是否存在
    report_dir = os.path.join(cwd, STATE_DIR, "task_reports", f"iteration_{n}")
    report_path = os.path.join(report_dir, f"task_{task_id}_report.json")

    if not os.path.isfile(report_path):
        return {
            "ok": False,
            "error_code": "TASK_REPORT_MISSING",
            "message": f"任务报告不存在: .project_ai/task_reports/iteration_{n}/task_{task_id}_report.json",
        }

    # 3. 检查报告 JSON 是否可解析
    try:
        with open(report_path, "r", encoding="utf-8") as f:
            report = json.load(f)
    except (json.JSONDecodeError, OSError) as e:
        return {
            "ok": False,
            "error_code": "TASK_REPORT_PARSE_ERROR",
            "message": f"任务报告无法解析: {e}",
        }

    # 4. 检查报告 status
    if report.get("status") != "done":
        return {
            "ok": False,
            "error_code": "TASK_NOT_DONE_IN_REPORT",
            "message": f"任务报告中的状态不是 done，当前为: {report.get('status')}",
        }

    # 5. 检查 expected_files 是否存在
    expected_files = task.get("expected_files", [])
    missing_files = []
    for f in expected_files:
        full_path = os.path.join(cwd, f)
        if not os.path.exists(full_path):
            missing_files.append(f)

    if missing_files:
        return {
            "ok": False,
            "error_code": "EXPECTED_FILES_MISSING",
            "message": f"以下预期产出文件不存在: {missing_files}",
            "missing_files": missing_files,
        }

    # 6. TDD 审批门禁
    tdd_config = task.get("tdd", {})
    if isinstance(tdd_config, dict) and tdd_config.get("enabled", False):
        sanitized = task_id.replace("/", "_").replace("\\", "_")
        approval_path = os.path.join(
            cwd, STATE_DIR, "tdd", "approvals", f"{sanitized}.approved.md"
        )
        if not os.path.isfile(approval_path):
            return {
                "ok": False,
                "error_code": "TDD_APPROVAL_MISSING",
                "message": (
                    f"TDD 审批文件不存在: .project_ai/tdd/approvals/{sanitized}.approved.md。"
                    "请先完成 Test Writer 和 Test Reviewer 流程，生成审批文件后再标记任务完成。"
                ),
            }

        # 7. TDD 文件边界检查
        forbidden_prefixes = ["tests/", "docs/specs/"]
        violations = _check_report_forbidden_files(
            cwd, n, task_id, forbidden_prefixes
        )
        if violations:
            return {
                "ok": False,
                "error_code": "TDD_FORBIDDEN_FILES_MODIFIED",
                "message": f"实现者修改了以下禁止修改的文件: {violations}",
                "violations": violations,
            }

    # 全部通过，更新状态
    backup_file(os.path.join(cwd, STATE_DIR, "state.json"))

    task_status = state.get("task_status", {})
    task_status[task_id] = "done"
    state["task_status"] = task_status
    state["last_modified"] = now_iso()
    save_state(cwd, state)

    return {
        "ok": True,
        "task_id": task_id,
        "message": f"任务 {task_id} 已标记为完成。",
    }


def _check_report_forbidden_files(cwd, iteration_n, task_id, forbidden_prefixes):
    """检查任务报告中的 files_created/modified 是否包含禁止文件。"""
    report_path = os.path.join(
        cwd, STATE_DIR, "task_reports", f"iteration_{iteration_n}",
        f"task_{task_id}_report.json"
    )

    if not os.path.isfile(report_path):
        return []

    try:
        with open(report_path, "r", encoding="utf-8") as f:
            report = json.load(f)
    except (json.JSONDecodeError, OSError):
        return []

    all_files = report.get("files_created", []) + report.get("files_modified", [])
    violations = []
    for f in all_files:
        for prefix in forbidden_prefixes:
            if f.startswith(prefix):
                violations.append(f)
                break
    return violations
