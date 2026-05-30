"""tdd 命令 — TDD 流程专用操作."""

import os
import json
import subprocess

from project_ai.state import STATE_DIR, load_state


def run(cwd, args):
    """路由 tdd 子命令。"""
    if args.tdd_command == "run-test":
        return _run_test(cwd, args.task_id)
    elif args.tdd_command == "check-approval":
        return _check_approval(cwd, args.task_id)
    elif args.tdd_command == "check-boundary":
        return _check_boundary(cwd, args.task_id)
    else:
        return {
            "ok": False,
            "error_code": "INVALID_TDD_COMMAND",
            "message": f"Unknown tdd command: {args.tdd_command}",
        }


def _run_test(cwd, task_id):
    """执行任务的 tdd.test_command，返回 exit_code 和输出。"""
    state = load_state(cwd)
    if state is None:
        return {
            "ok": False,
            "error_code": "STATE_NOT_FOUND",
            "message": "state.json 不存在或无法解析。",
        }

    task = _find_task(state, task_id)
    if task is None:
        return {
            "ok": False,
            "error_code": "TASK_NOT_FOUND",
            "message": f"任务 {task_id} 不在当前迭代的任务列表中。",
        }

    tdd = task.get("tdd", {})
    if not tdd.get("enabled", False):
        return {
            "ok": False,
            "error_code": "TDD_NOT_ENABLED",
            "message": f"任务 {task_id} 未启用 TDD。设置 tdd.enabled: true 以使用此命令。",
        }

    test_command = tdd.get("test_command", "")
    if not test_command:
        return {
            "ok": False,
            "error_code": "TDD_NO_TEST_COMMAND",
            "message": f"任务 {task_id} 的 tdd.test_command 为空。",
        }

    try:
        result = subprocess.run(
            test_command,
            shell=True,
            capture_output=True,
            text=True,
            timeout=120,
            cwd=cwd,
        )
    except subprocess.TimeoutExpired:
        return {
            "ok": False,
            "error_code": "TEST_COMMAND_TIMEOUT",
            "message": "测试命令执行超时（120 秒）。",
        }
    except Exception as e:
        return {
            "ok": False,
            "error_code": "TEST_COMMAND_ERROR",
            "message": f"无法执行测试命令: {e}",
        }

    stdout = result.stdout[:5000] if result.stdout else ""
    stderr = result.stderr[:2000] if result.stderr else ""

    return {
        "ok": True,
        "exit_code": result.returncode,
        "passed": result.returncode == 0,
        "stdout": stdout,
        "stderr": stderr,
        "command": test_command,
    }


def _check_approval(cwd, task_id):
    """检查 TDD approval 文件是否存在。"""
    sanitized = task_id.replace("/", "_").replace("\\", "_")
    approval_path = os.path.join(
        cwd, STATE_DIR, "tdd", "approvals", f"{sanitized}.approved.md"
    )

    exists = os.path.isfile(approval_path)
    return {
        "ok": True,
        "approved": exists,
        "approval_file": os.path.join(
            ".project_ai", "tdd", "approvals", f"{sanitized}.approved.md"
        ),
        "exists": exists,
    }


def _check_boundary(cwd, task_id):
    """检查实现者是否越界修改了 tests/ 或 docs/specs/ 等禁止文件。"""
    forbidden_prefixes = ["tests/", "docs/specs/"]

    # 策略 1: git diff
    violations = _git_diff_check(cwd, forbidden_prefixes)
    if violations is not None:
        return {
            "ok": True,
            "passed": len(violations) == 0,
            "method": "git_diff",
            "violations": violations,
        }

    # 策略 2: 任务报告交叉检查
    state = load_state(cwd)
    if state is None:
        return {"ok": True, "passed": True, "method": "none", "violations": []}

    n = state.get("current_iteration", 0)
    report_path = os.path.join(
        cwd, STATE_DIR, "task_reports", f"iteration_{n}", f"task_{task_id}_report.json"
    )

    if not os.path.isfile(report_path):
        return {"ok": True, "passed": True, "method": "none", "violations": []}

    try:
        with open(report_path, "r", encoding="utf-8") as f:
            report = json.load(f)
    except (json.JSONDecodeError, OSError):
        return {"ok": True, "passed": True, "method": "none", "violations": []}

    all_files = report.get("files_created", []) + report.get("files_modified", [])
    violations = []
    for f in all_files:
        for prefix in forbidden_prefixes:
            if f.startswith(prefix):
                violations.append(f)
                break

    return {
        "ok": True,
        "passed": len(violations) == 0,
        "method": "report_check",
        "violations": violations,
    }


def _git_diff_check(cwd, forbidden_prefixes):
    """用 git diff 检查文件变更。返回 None 表示 git 不可用。"""
    try:
        result = subprocess.run(
            ["git", "diff", "--name-only", "--diff-filter=MCA"],
            capture_output=True,
            text=True,
            timeout=10,
            cwd=cwd,
        )
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        return None

    if result.returncode != 0:
        return None

    files = [f.strip() for f in result.stdout.split("\n") if f.strip()]
    violations = []
    for f in files:
        for prefix in forbidden_prefixes:
            if f.startswith(prefix):
                violations.append(f)
                break

    return violations


def _find_task(state, task_id):
    """在 iteration_tasks 中查找任务。"""
    for t in state.get("iteration_tasks", []):
        if t.get("id") == task_id:
            return t
    return None
