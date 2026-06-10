"""tdd 命令 — TDD 流程专用操作."""

import os
import hashlib
import json
import fnmatch
import subprocess
from datetime import datetime, timezone

from project_ai.state import STATE_DIR, load_state

# v5.5.0: 全面禁止修改的前缀和文件模式
#
# 原则：FORBIDDEN_PREFIXES 只放"任何 agent 在任何情况下都不能碰"的目录。
# 各 TDD 子代理的正常产出（coverage/ reviews/ approvals/ spec-compliance/
# cheating-probe-results/ mutation-results/ e2e-results/ implementation-reports/
# blockers/ 等）不在此列——它们由独立子代理通过 SKILL.md 角色分离来保护，
# 不能放在全局 forbidden list 中，否则 git-diff 检查会拦截正常流程产物。
FORBIDDEN_PREFIXES = [
    # 测试目录（任何 agent 都不能碰）
    "tests/",
    "test/",
    "e2e/",
    "__tests__/",
    # Spec / BDD（任何 agent 都不能碰，仅 bdd-spec-writer / iteration-manager 可写）
    ".project_ai/specs/",
    # 项目关键文件（仅 CLI / iteration-manager 可写，任何任务代理禁止修改）
    ".project_ai/state.json",
    ".project_ai/plans/",
    ".project_ai/requirements/",
    ".project_ai/iteration_reports/",
    ".project_ai/confirmations/",
    # 阶段封存清单（仅 CLI 可写，防止代理篡改 manifest）
    ".project_ai/tdd/manifests/",
]

FORBIDDEN_FILE_PATTERNS = [
    # 测试文件
    "*.test.ts",
    "*.test.tsx",
    "*.test.js",
    "*.test.jsx",
    "*.spec.ts",
    "*.spec.tsx",
    "*.spec.js",
    "*.spec.jsx",
    # 测试配置
    "playwright.config.*",
    "vitest.config.*",
    "jest.config.*",
    "cypress.config.*",
    # 构建配置
    "vite.config.*",
    "webpack.config.*",
    "rollup.config.*",
    "tsconfig*.json",
    "eslint.config.*",
    ".eslintrc*",
    ".prettierrc*",
    # 包管理
    "package.json",
    "package-lock.json",
    "pnpm-lock.yaml",
    "yarn.lock",
    "bun.lockb",
    # 环境变量
    ".env",
    ".env.*",
]

# v5.5.0: 阶段封存 — 每个 TDD phase 的产出文件清单
# {task_id} 会在运行时替换为 sanitized task_id
PHASE_OUTPUTS = {
    "test_writer": {
        "label": "Phase A — Test Writer",
        "required": [
            ".project_ai/tdd/coverage/{task_id}.coverage.md",
            ".project_ai/tdd/red-runs/{task_id}.red-run.md",
        ],
        "optional": [
            ".project_ai/tdd/open-questions/{task_id}.questions.md",
        ],
    },
    "test_reviewer": {
        "label": "Phase B — Test Reviewer",
        "required": [
            ".project_ai/tdd/reviews/{task_id}.test-review.md",
        ],
        "optional": [
            ".project_ai/tdd/approvals/{task_id}.approved.md",
            ".project_ai/tdd/cheating-probe-results/{task_id}.cheating-probe.md",
        ],
    },
    "implementer": {
        "label": "Phase C — Implementer",
        "required": [
            ".project_ai/tdd/implementation-reports/{task_id}.implementation.md",
        ],
        "optional": [
            ".project_ai/tdd/blockers/{task_id}.blockers.md",
        ],
    },
    "spec_compliance": {
        "label": "Phase C2 — Spec Compliance Review",
        "required": [
            ".project_ai/tdd/spec-compliance/{task_id}.spec-compliance.md",
        ],
        "optional": [],
    },
    "e2e": {
        "label": "Phase C3 — E2E Verification",
        "required": [
            ".project_ai/tdd/e2e-results/{task_id}.e2e-results.md",
        ],
        "optional": [],
    },
}

MANIFESTS_DIR = os.path.join(STATE_DIR, "tdd", "manifests")


def _is_forbidden(file_path):
    """检查文件路径是否命中任何禁止规则。"""
    for prefix in FORBIDDEN_PREFIXES:
        if file_path.startswith(prefix):
            return True
    for pattern in FORBIDDEN_FILE_PATTERNS:
        if fnmatch.fnmatch(file_path, pattern):
            return True
    # 也匹配路径中任意一层目录命中模式
    parts = file_path.replace("\\", "/").split("/")
    for part in parts:
        for pattern in FORBIDDEN_FILE_PATTERNS:
            if fnmatch.fnmatch(part, pattern):
                return True
    return False


def run(cwd, args):
    """路由 tdd 子命令。"""
    if args.tdd_command == "run-test":
        return _run_test(cwd, args.task_id)
    elif args.tdd_command == "check-approval":
        return _check_approval(cwd, args.task_id)
    elif args.tdd_command == "check-boundary":
        return _check_boundary(cwd, args.task_id)
    elif args.tdd_command == "seal-phase":
        return _seal_phase(cwd, args.task_id, getattr(args, "phase", ""))
    elif args.tdd_command == "check-integrity":
        return _check_integrity(cwd, args.task_id)
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
    """检查实现者是否越界修改了测试/spec/tdd/build 等禁止文件。"""

    # 策略 1: git diff（最可靠）
    violations = _git_diff_check(cwd)
    if violations is not None:
        return {
            "ok": True,
            "passed": len(violations) == 0,
            "method": "git_diff",
            "violations": violations,
        }

    # 策略 2: 任务报告交叉检查（fallback）
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
    violations = [f for f in all_files if _is_forbidden(f)]

    return {
        "ok": True,
        "passed": len(violations) == 0,
        "method": "report_check",
        "violations": violations,
    }


def _get_all_changed_files(cwd):
    """收集所有文件变更（unstaged + staged + untracked + deleted）。
    返回 list 表示成功，返回 None 表示 git 不可用。"""
    all_files = set()

    commands = [
        ["git", "diff", "--name-only"],                          # unstaged modify/delete
        ["git", "diff", "--cached", "--name-only"],              # staged changes
        ["git", "ls-files", "--others", "--exclude-standard"],   # untracked
        ["git", "diff", "--name-only", "--diff-filter=D"],       # deleted (unstaged)
        ["git", "diff", "--cached", "--name-only", "--diff-filter=D"],  # deleted (staged)
    ]

    any_success = False
    for cmd in commands:
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=10,
                cwd=cwd,
            )
        except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
            return None

        if result.returncode != 0:
            continue

        any_success = True
        for line in result.stdout.split("\n"):
            stripped = line.strip()
            if stripped:
                all_files.add(stripped)

    if not any_success:
        return None

    return sorted(all_files)


def _git_diff_check(cwd):
    """用 git 检查文件变更中的 forbidden 文件。返回 list 或 None（git 不可用）。"""
    all_files = _get_all_changed_files(cwd)
    if all_files is None:
        return None
    return [f for f in all_files if _is_forbidden(f)]


def _is_path_allowed(path, allowed_patterns):
    """检查 path 是否匹配 allowed_patterns 中的任一模式。

    支持三种匹配方式（按优先级）：
    1. 精确匹配：path == pattern
    2. 目录前缀：pattern 以 / 结尾时，path 以 pattern 开头即匹配
       （如 "src/features/inventory/" 匹配 "src/features/inventory/sort.ts"）
    3. Glob 模式：fnmatch（支持 * 和 ? 通配符）
       （如 "src/features/inventory/*.ts" 匹配 "src/features/inventory/sort.ts"）
    """
    for pattern in allowed_patterns:
        if path == pattern:
            return True
        if pattern.endswith("/") and path.startswith(pattern):
            return True
        if fnmatch.fnmatch(path, pattern):
            return True
    return False


def check_file_boundary(cwd, allowed_files, task_id=None):
    """综合性文件边界检查（v5.5.0）。

    检查两个维度：
    1. forbidden: 变更文件不能命中 FORBIDDEN_PREFIXES / FORBIDDEN_FILE_PATTERNS
    2. allowed: 生产代码变更（非 .project_ai/ 目录）必须匹配 allowed_files 中的模式
       （支持精确匹配、目录前缀、glob 通配符）

    allowed_files: 任务允许修改的文件列表（支持 glob/目录前缀）
    task_id: 可选，用于 fallback 报告检查

    Returns: (passed: bool, forbidden_violations: list, extra_files: list, method: str)
    """
    all_changed = _get_all_changed_files(cwd)

    if all_changed is None:
        # git 不可用，fallback 到报告检查
        if task_id is not None:
            return _check_boundary_from_report(cwd, task_id, allowed_files)
        return True, [], [], "none"

    # 1. forbidden 检查
    forbidden_violations = [f for f in all_changed if _is_forbidden(f)]

    # 2. allowed 检查：生产代码（非 .project_ai/ 目录）必须在 allowed_files 内
    # 以下是已知的流程文件前缀，不受 allowed_files 限制
    PROCESS_PREFIXES = (
        ".project_ai/",
    )
    prod_files = [f for f in all_changed if not f.startswith(PROCESS_PREFIXES)]
    extra_files = [f for f in prod_files if not _is_path_allowed(f, allowed_files)]

    passed = len(forbidden_violations) == 0 and len(extra_files) == 0
    return passed, forbidden_violations, extra_files, "git_diff"


def _check_boundary_from_report(cwd, task_id, allowed_files):
    """从任务报告检查边界（git 不可用时的 fallback）。"""
    state = load_state(cwd)
    if state is None:
        return True, [], [], "none"

    n = state.get("current_iteration", 0)
    report_path = os.path.join(
        cwd, STATE_DIR, "task_reports", f"iteration_{n}", f"task_{task_id}_report.json"
    )

    if not os.path.isfile(report_path):
        return True, [], [], "none"

    try:
        with open(report_path, "r", encoding="utf-8") as f:
            report = json.load(f)
    except (json.JSONDecodeError, OSError):
        return True, [], [], "none"

    all_files = report.get("files_created", []) + report.get("files_modified", [])
    forbidden_violations = [f for f in all_files if _is_forbidden(f)]

    extra_files = [f for f in all_files
                   if not f.startswith(".project_ai/")
                   and not _is_path_allowed(f, allowed_files)]

    passed = len(forbidden_violations) == 0 and len(extra_files) == 0
    return passed, forbidden_violations, extra_files, "report_check"


def _seal_phase(cwd, task_id, phase):
    """封存一个 TDD 阶段的产物文件（v5.5.0 阶段封存机制）。

    对当前 phase 的所有必需+可选文件做 SHA256 哈希，
    写入 .project_ai/tdd/manifests/<task_id>.<phase>.manifest.json。
    如果该 phase 的 manifest 已存在，拒绝覆盖（防止后续 agent 重新封存）。
    """
    sanitized = task_id.replace("/", "_").replace("\\", "_")

    if phase not in PHASE_OUTPUTS:
        return {
            "ok": False,
            "error_code": "UNKNOWN_PHASE",
            "message": f"未知阶段: {phase}。有效阶段: {list(PHASE_OUTPUTS.keys())}",
        }

    outputs = PHASE_OUTPUTS[phase]

    # 检查 manifest 是否已存在（防止后续 agent 重新封存覆盖正确 hash）
    manifest_dir = os.path.join(cwd, MANIFESTS_DIR)
    manifest_path = os.path.join(manifest_dir, f"{sanitized}.{phase}.manifest.json")
    if os.path.isfile(manifest_path):
        return {
            "ok": False,
            "error_code": "MANIFEST_ALREADY_EXISTS",
            "message": (
                f"阶段 {phase} 的 manifest 已存在: "
                f".project_ai/tdd/manifests/{sanitized}.{phase}.manifest.json。"
                "如需重新封存，请先手动删除旧 manifest。"
            ),
        }

    # 收集并哈希所有存在的文件
    files = {}
    for template in outputs["required"] + outputs["optional"]:
        file_path = template.format(task_id=sanitized)
        full_path = os.path.join(cwd, file_path)
        if os.path.isfile(full_path):
            with open(full_path, "rb") as f:
                content = f.read()
            files[file_path] = "sha256:" + hashlib.sha256(content).hexdigest()

    # 检查必需文件
    missing = []
    for template in outputs["required"]:
        file_path = template.format(task_id=sanitized)
        if file_path not in files:
            missing.append(file_path)

    manifest = {
        "task_id": task_id,
        "phase": phase,
        "phase_label": outputs["label"],
        "created_at": datetime.now(timezone.utc).isoformat(),
        "files": files,
        "missing_required": missing,
    }

    os.makedirs(manifest_dir, exist_ok=True)
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2, ensure_ascii=False)

    return {
        "ok": True,
        "phase": phase,
        "phase_label": outputs["label"],
        "task_id": task_id,
        "files_sealed": len(files),
        "missing_required": missing,
        "manifest_path": os.path.join(
            ".project_ai", "tdd", "manifests", f"{sanitized}.{phase}.manifest.json"
        ),
    }


def _check_integrity(cwd, task_id):
    """检查所有已封存阶段的产物完整性（v5.5.0 阶段封存机制）。

    读取 .project_ai/tdd/manifests/<task_id>.*.manifest.json，
    逐一验证每个文件的当前 SHA256 是否与封存时一致。
    任何不匹配（文件缺失、内容被修改）均视为完整性违规。
    """
    sanitized = task_id.replace("/", "_").replace("\\", "_")
    manifest_dir = os.path.join(cwd, MANIFESTS_DIR)

    if not os.path.isdir(manifest_dir):
        return {
            "ok": True,
            "task_id": task_id,
            "phases_checked": 0,
            "phases_found": [],
            "violations": [],
            "intact": True,
        }

    # 收集当前任务的所有 manifest
    manifests = []
    try:
        for entry in sorted(os.listdir(manifest_dir)):
            if not entry.startswith(sanitized + ".") or not entry.endswith(".manifest.json"):
                continue
            manifest_path = os.path.join(manifest_dir, entry)
            with open(manifest_path, "r", encoding="utf-8") as f:
                manifests.append(json.load(f))
    except OSError:
        return {
            "ok": False,
            "error_code": "INTEGRITY_CHECK_ERROR",
            "message": "无法读取 manifests 目录。",
        }

    # 验证每个 manifest 中的每个文件
    violations = []
    for manifest in manifests:
        phase = manifest.get("phase", "unknown")
        for file_path, expected_hash in manifest.get("files", {}).items():
            full_path = os.path.join(cwd, file_path)
            if not os.path.isfile(full_path):
                violations.append({
                    "phase": phase,
                    "file": file_path,
                    "issue": "missing",
                    "detail": f"封存的文件已不存在",
                })
                continue

            try:
                with open(full_path, "rb") as f:
                    current_hash = "sha256:" + hashlib.sha256(f.read()).hexdigest()
            except OSError:
                violations.append({
                    "phase": phase,
                    "file": file_path,
                    "issue": "unreadable",
                    "detail": "无法读取文件",
                })
                continue

            if current_hash != expected_hash:
                violations.append({
                    "phase": phase,
                    "file": file_path,
                    "issue": "tampered",
                    "detail": f"文件内容已被修改（封存 hash: {expected_hash[:16]}..., 当前 hash: {current_hash[:16]}...）",
                })

    # 检查哪些 phase 已有封存记录
    phases_found = [m.get("phase", "?") for m in manifests]

    return {
        "ok": True,
        "task_id": task_id,
        "phases_checked": len(manifests),
        "phases_found": phases_found,
        "violations": violations,
        "intact": len(violations) == 0,
    }


def _find_task(state, task_id):
    """在 iteration_tasks 中查找任务。"""
    for t in state.get("iteration_tasks", []):
        if t.get("id") == task_id:
            return t
    return None
