"""任务管理 — next / context / complete / sync."""

import os
import re
import json
from project_ai.state import STATE_DIR, load_state, save_state
from project_ai.utils import backup_file, now_iso
from project_ai.cli_tdd import _is_forbidden, _run_test, check_file_boundary


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

    # 6. TDD 审批门禁（v5.5.0 重构：fresh test run + git boundary + allowed_files + cheating-probe）
    tdd_config = task.get("tdd", {})
    if isinstance(tdd_config, dict) and tdd_config.get("enabled", False):
        sanitized = task_id.replace("/", "_").replace("\\", "_")
        risk_level = task.get("risk_level", "medium")

        # 6a. 审批文件
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

        # 6b. Fresh test run（v5.5.0 新增 — 最终裁判亲自跑测试）
        test_result = _run_test(cwd, task_id)
        if not test_result.get("ok", False):
            return {
                "ok": False,
                "error_code": "TDD_FRESH_TEST_FAILED",
                "message": (
                    f"测试命令执行失败: {test_result.get('message', '未知错误')}。"
                    "请检查测试配置和依赖是否正确安装。"
                ),
            }
        if not test_result.get("passed", False):
            return {
                "ok": False,
                "error_code": "TDD_TESTS_NOT_PASSING",
                "message": (
                    f"测试未全部通过（exit_code={test_result.get('exit_code', '?')}）。"
                    f"\nstdout: {test_result.get('stdout', '')[:500]}"
                    f"\nstderr: {test_result.get('stderr', '')[:500]}"
                ),
            }

        # 6c. 文件边界检查（v5.5.0 升级 — git diff + allowed_files 双重门禁）
        allowed_files = task.get("expected_files", [])
        boundary_passed, forbidden_violations, extra_files, boundary_method = \
            check_file_boundary(cwd, allowed_files, task_id=task_id)

        if forbidden_violations:
            return {
                "ok": False,
                "error_code": "TDD_FORBIDDEN_FILES_MODIFIED",
                "message": f"实现者修改了以下禁止修改的文件（检测方式: {boundary_method}）: {forbidden_violations}",
                "violations": forbidden_violations,
                "detection_method": boundary_method,
            }

        if extra_files:
            return {
                "ok": False,
                "error_code": "TDD_FILES_OUTSIDE_ALLOWED",
                "message": (
                    f"实现者修改了以下不在 allowed_files 中的生产文件: {extra_files}。"
                    "这些文件未在任务计划中列出，属于越界修改。请检查是否遗漏了 allowed_files 声明，"
                    "或回退这些越界变更。"
                ),
                "extra_files": extra_files,
                "allowed_files": allowed_files,
            }

        if not boundary_passed:
            return {
                "ok": False,
                "error_code": "TDD_BOUNDARY_CHECK_FAILED",
                "message": f"文件边界检查未通过（检测方式: {boundary_method}）。",
            }

        # 6d. Spec Compliance Review 门禁（v5.4.0）
        sc_path = os.path.join(
            cwd, STATE_DIR, "tdd", "spec-compliance", f"{sanitized}.spec-compliance.md"
        )
        if not os.path.isfile(sc_path):
            return {
                "ok": False,
                "error_code": "SPEC_COMPLIANCE_MISSING",
                "message": (
                    f"Spec Compliance Review 报告不存在: "
                    f".project_ai/tdd/spec-compliance/{sanitized}.spec-compliance.md。"
                    "请先完成 Spec Compliance Review (Phase C2) 流程。"
                ),
            }
        sc_verdict = _parse_spec_compliance_verdict(sc_path)
        if sc_verdict != "compliant":
            return {
                "ok": False,
                "error_code": "SPEC_COMPLIANCE_FAILED",
                "message": (
                    f"Spec Compliance Review 未通过（verdict: {sc_verdict}）。"
                    "请修复 spec 合规问题后重新运行 Spec Compliance Review。"
                ),
            }

        # 6e. Cheating Implementation Probe（v5.5.0 — 独立路径，Phase B 产出）
        if risk_level in ("medium", "high"):
            cp_path = os.path.join(
                cwd, STATE_DIR, "tdd", "cheating-probe-results", f"{sanitized}.cheating-probe.md"
            )
            if not os.path.isfile(cp_path):
                return {
                    "ok": False,
                    "error_code": "CHEATING_PROBE_MISSING",
                    "message": (
                        f"Cheating Implementation Probe 结果文件不存在（risk_level={risk_level}，必须提供）: "
                        f".project_ai/tdd/cheating-probe-results/{sanitized}.cheating-probe.md。"
                        "请先完成 Test Reviewer 的 Cheating Implementation Probe 步骤。"
                    ),
                }
            killed, total = _parse_cheating_probe_results(cp_path)
            # 强制最低数量：medium/high 至少 3 个 cheating probe
            MIN_PROBES = 3
            if total < MIN_PROBES:
                return {
                    "ok": False,
                    "error_code": "CHEATING_PROBE_INSUFFICIENT",
                    "message": (
                        f"Cheating Implementation Probe 数量不足: {total} 个（要求至少 {MIN_PROBES} 个）。"
                        "risk_level >= medium 必须执行至少 3 个作弊实现探测。"
                    ),
                }
            if killed < total:
                return {
                    "ok": False,
                    "error_code": "CHEATING_PROBE_SURVIVORS",
                    "message": (
                        f"Cheating Implementation Probe 未全部杀死: {killed}/{total} KILLED。"
                        "存在 SURVIVED 作弊实现说明测试有盲区，请补充测试后重新运行 Cheating Probe。"
                    ),
                }

        # 6f. Post-Green Mutation Testing（v5.5.0 新增 — Phase C 后，仅 high）
        if risk_level == "high":
            pgm_path = os.path.join(
                cwd, STATE_DIR, "tdd", "mutation-results", f"{sanitized}.mutation-results.md"
            )
            if os.path.isfile(pgm_path):
                pgm_killed, pgm_total = _parse_mutation_results(pgm_path)
                if pgm_total > 0 and pgm_killed < pgm_total:
                    return {
                        "ok": False,
                        "error_code": "POST_GREEN_MUTATION_SURVIVORS",
                        "message": (
                            f"Post-Green Mutation Testing 未全部杀死: {pgm_killed}/{pgm_total} KILLED。"
                            "正确实现被修改后测试未能发现回归，存在测试盲区。"
                        ),
                    }
            # 注意：post-green mutation 文件不存在时仅警告，不阻塞（该功能尚未在所有流程中强制）

        # 6g. E2E 验证（仅 risk_level=high 且含 e2e_scenarios）
        e2e_scenarios = tdd_config.get("e2e_scenarios", [])
        if risk_level == "high" and e2e_scenarios:
            e2e_path = os.path.join(
                cwd, STATE_DIR, "tdd", "e2e-results", f"{sanitized}.e2e-results.md"
            )
            if not os.path.isfile(e2e_path):
                return {
                    "ok": False,
                    "error_code": "E2E_RESULTS_MISSING",
                    "message": (
                        f"E2E 验证结果文件不存在（risk_level=high 且含 e2e_scenarios，必须提供）: "
                        f".project_ai/tdd/e2e-results/{sanitized}.e2e-results.md"
                    ),
                }
            e2e_passed, e2e_msg = _parse_e2e_results(e2e_path)
            if not e2e_passed:
                return {
                    "ok": False,
                    "error_code": "E2E_FAILED",
                    "message": f"E2E 验证未通过: {e2e_msg}",
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


def _parse_spec_compliance_verdict(file_path):
    """从 spec-compliance 报告中解析 verdict。返回 'compliant' / 'issues_found' / 'unknown'。"""
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()
    except OSError:
        return "unknown"

    # 查找 "## Verdict: ✅ COMPLIANT" 或 "## Verdict: ❌ ISSUES FOUND"
    m = re.search(r"##\s*Verdict:\s*(✅|❌)\s*(\w+)", content)
    if m:
        verdict = m.group(2).lower().strip()
        if verdict in ("compliant",):
            return "compliant"
        if verdict in ("issues", "issues_found", "found"):
            return "issues_found"
        return verdict

    # Fallback: 查找 "Verdict: COMPLIANT"
    if re.search(r"(?i)verdict\s*:\s*compliant", content):
        return "compliant"
    if re.search(r"(?i)verdict\s*:\s*issues?\s*found", content):
        return "issues_found"

    return "unknown"


def _parse_cheating_probe_results(file_path):
    """从 cheating-probe 报告中解析 KILLED/SURVIVED。返回 (killed, total)。

    v5.5.0: 独立于 post-green mutation，专门解析 Phase B 的 cheating probe 结果。
    如果 total 为 0 表示未执行任何 probe，视为未通过。
    """
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()
    except OSError:
        return 0, 0

    # 查找 "杀死: X/Y" 或 "Killed: X/Y"（大小写不敏感）
    m = re.search(r"(?i)(?:杀死|killed)\s*[:：]\s*(\d+)\s*/\s*(\d+)", content)
    if m:
        return int(m.group(1)), int(m.group(2))

    # Count KILLED and SURVIVED rows in table
    killed = len(re.findall(r"\|\s*\d+\s*\|.*\|\s*✅.*\|\s*KILLED", content))
    survived = len(re.findall(r"\|\s*\d+\s*\|.*\|\s*❌.*\|\s*SURVIVED", content))
    if killed + survived > 0:
        return killed, killed + survived

    # 未找到任何结果 → 0 probe 执行
    return 0, 0


def _parse_mutation_results(file_path):
    """从 post-green mutation-results 报告中解析 KILLED/SURVIVED。返回 (killed, total)。

    v5.5.0: 专门用于 Phase C 后的传统 mutation testing（post-green）。
    Phase B 的 cheating probe 使用 _parse_cheating_probe_results。
    """
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()
    except OSError:
        return 0, 0

    # 查找 "杀死: X/Y" 或 "Killed: X/Y"（大小写不敏感）
    m = re.search(r"(?i)(?:杀死|killed)\s*[:：]\s*(\d+)\s*/\s*(\d+)", content)
    if m:
        return int(m.group(1)), int(m.group(2))

    # Count KILLED and SURVIVED rows in table
    killed = len(re.findall(r"\|\s*\d+\s*\|.*\|\s*✅.*\|\s*KILLED", content))
    survived = len(re.findall(r"\|\s*\d+\s*\|.*\|\s*❌.*\|\s*SURVIVED", content))
    if killed + survived > 0:
        return killed, killed + survived

    return 0, 0


def _parse_e2e_results(file_path):
    """从 e2e-results 报告中解析是否全部 pass。返回 (passed: bool, message: str)。

    v5.5.0: fail-closed — 只有找到显式 PASS 标记才返回 True。
    空报告、格式错误、无显式标记 → 一律判失败。
    """
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()
    except OSError:
        return False, "无法读取 E2E 结果文件"

    # 先查找显式失败标记
    failures = re.findall(r"(?i)(?:FAIL|❌)\s*[:：]?\s*(.+)", content)
    if failures:
        return False, "; ".join(failures[:5])

    # 必须找到显式 PASS 标记才判通过
    explicit_pass = re.search(
        r"(?i)(?:all\s*(?:tests?\s*)?pass|✅.*pass|verdict\s*:\s*pass|passed\s*:\s*true)",
        content
    )
    if explicit_pass:
        return True, "全部 E2E 通过"

    # 无显式 PASS 标记 → fail-closed
    return False, "E2E 结果文件中未找到显式 PASS 标记（verdict: pass / ✅ pass / all tests pass）"
