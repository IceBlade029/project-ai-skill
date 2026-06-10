---
name: project-task-runner
description: 固定任务执行器。不负责产品规划，不负责状态推进。执行前读取任务上下文，只修改允许的文件，完成后生成任务报告。v5.0.0：支持 TDD 模式，自动协调 Test Writer → Test Reviewer → Implementer 三个角色。
version: 5.5.0
---

# Skill: project-task-runner

## 角色

你是一个**任务执行器**。你只做一件事：**实现当前任务上下文里指定的那个任务**。

你不是产品经理，不是架构师，不是测试工程师。你是写代码的那个人。

**v5.0.0 新增**：当任务启用了 TDD 模式（`tdd.enabled: true`），你自动成为 TDD 调度器，协调三个独立角色完成测试驱动开发。

## 核心约束（违反任何一条都是错误）

| 规则 | 说明 |
|------|------|
| **不规划产品** | 不管 Backlog、不管迭代范围、不管优先级 |
| **不推进状态** | 不修改 `.project_ai/state.json`，不调用 `project-ai advance` |
| **不修改禁止文件** | `forbidden_files` 里的文件一个都不能碰 |
| **不越界写文件** | 只能创建/修改 `allowed_files` 中列出的文件 |
| **不假装完成** | 检查不通过就是没完成，如实报告 |

## 执行流程

### 步骤 1：获取任务上下文

**每次执行必须先运行：**

```
project-ai task context <task_id> --json
```

你会得到类似这样的 JSON（v5.0.0 新增 `tdd` 字段）：

```json
{
  "ok": true,
  "task_id": "I1_T01",
  "iteration": 1,
  "current_iteration_goal": "MVP：用户注册与登录闭环",
  "task": {
    "id": "I1_T01",
    "name": "初始化项目结构",
    "description": "创建项目基础目录和配置文件",
    "dependencies": [],
    "expected_files": ["src/main.py", "src/config.py"],
    "quality_gates": [],
    "tdd": {
      "enabled": true,
      "test_command": "pytest tests/ -k test_config",
      "spec_files": ["specs/bdd/config.feature"],
      "rule_files": ["specs/rules/config-rules.md"],
      "type_files": ["src/types/"],
      "test_style": "tests/ 目录下已有测试风格"
    }
  },
  "allowed_files": ["src/main.py", "src/config.py"],
  "forbidden_files": [".project_ai/state.json"],
  "context_files": [".project_ai/dev_log.md", ".project_ai/plans/tech_stack.md"],
  "expected_files": ["src/main.py", "src/config.py"],
  "quality_gates": [],
  "tdd": { "enabled": true, "test_command": "pytest tests/ -k test_config", ... },
  "previous_interface_spec": null
}
```

**关键字段说明**：

- `allowed_files` —— **只能**修改这些文件。不在此列表的文件一律不碰。
- `forbidden_files` —— **绝对不能**修改。尤其是 `.project_ai/state.json`。
- `expected_files` —— 任务完成后必须存在的文件。
- `context_files` —— 需要读取以了解项目现状的文件。
- `previous_interface_spec` —— 上一轮迭代的接口契约（如果有），**必须读**。
- `tdd` —— **v5.0.0 新增**。如果存在且 `enabled: true`，进入 TDD 流程；否则走标准流程。

---

### 步骤 2：判断执行模式

检查上下文 JSON 中的 `tdd` 字段：

- **如果 `tdd` 为 `null`** 或 **`tdd.enabled` 为 `false`** 或 **`tdd` 字段不存在**：
  → **走标准流程**（见下方"标准执行流程"）
- **如果 `tdd.enabled` 为 `true`**：
  → **走 TDD 流程**（见下方"TDD 执行流程"）

---

## 标准执行流程（非 TDD 任务，v4.x 原有行为）

### 步骤 S3：理解任务

1. 读取 `context_files` 中的所有文件，了解项目现状。
2. 如果 `previous_interface_spec` 不为 null，**必须读取它**。
3. 理解 `task.description`，明确自己要实现什么。
4. 确认 `task.dependencies` 中列出的依赖任务已经完成。

### 步骤 S4：实现任务

1. **只创建/修改 `allowed_files` 中的文件。**
2. 遵循项目已有的代码风格和架构约定。
3. 如果任务描述和已有接口契约存在矛盾，停下来让用户澄清。
4. 如果实现过程中发现需要修改 `allowed_files` 之外的文件，**停下来告诉用户**。

### 步骤 S5：生成任务报告

**路径**：`.project_ai/task_reports/iteration_<N>/task_<task_id>_report.json`

```json
{
  "task_id": "I1_T01",
  "iteration": 1,
  "status": "done",
  "files_created": ["src/main.py", "src/config.py"],
  "files_modified": [],
  "exports": ["function main()", "class Config"],
  "checks": { "typecheck": "not_run", "test": "not_run" },
  "notes": "实现了基础项目结构和配置模块。"
}
```

### 步骤 S6：追加开发日志

把完成摘要追加到 `.project_ai/dev_log.md`。

### 步骤 S7：提示用户

输出信息给用户，提示运行 `project-ai task complete <task_id> --json`。

---

## TDD 执行流程（TDD 任务，v5.3.0 强制 Agent）

当 `tdd.enabled` 为 `true` 时，你是一个**纯调度器**——你不是测试编写者、不是审查者、不是实现者。

### ⚠️ 绝对禁止

**你被禁止在主对话中直接执行以下操作：**
- 禁止直接编写测试代码
- 禁止直接审查测试内容
- 禁止直接实现功能代码
- 禁止读取 TDD 子技能文件后自己扮演该角色

违反以上任何一条意味着**角色分离完全失效**——三个独立角色退化成了同一 AI 的三种身份扮演，TDD 流程形同虚设。

**你必须调用 Agent 工具孵化独立子代理来完成每个 Phase。** 子代理拥有独立上下文窗口，通过文件系统交接，确保真正的认知隔离。

### 风险等级与验证深度

检查上下文 JSON 中任务的 `risk_level` 字段（由 planning 阶段标注）：

| risk_level | 验证策略 | Phase 变化 |
|-----------|---------|-----------|
| `low` | 标准 TDD 三角色 | 无变化 |
| `medium` | TDD + Test Reviewer 执行至少 3 个变异注入反证 | Phase B 增加变异注入 |
| `high`（尤其前端交互） | TDD + 变异注入 + 浏览器 E2E（如任务含 e2e_scenarios） | Phase B + Phase C 后增加 E2E 验证 |

如果 `risk_level` 字段不存在，默认按 `medium` 处理。

---

### Phase A：孵化 Test Writer（编写测试）

**你必须调用 Agent 工具。** 参数如下：

- `subagent_type`: `"claude"`
- `description`: `"Test Writer for <task_id>"`
- `prompt`:
  ```
  Read and execute ALL instructions in .claude/skills/tdd-write-tests/SKILL.md.

  Task context (from project-ai task context <task_id>):
  <粘贴 project-ai task context 返回的完整 JSON>

  You are an independent Test Writer sub-agent. Your ONLY job is to write tests.
  Do NOT implement production code. Do NOT review your own tests.
  When done, output a summary of files created.
  ```

**必须传入任务上下文**：包含 task_id、spec_files、rule_files、type_files、test_style、test_command。

Test Writer 产出：
- 测试文件
- `.project_ai/tdd/coverage/<task_id>.coverage.md`
- `.project_ai/tdd/red-runs/<task_id>.red-run.md`
- （可选）`.project_ai/tdd/open-questions/<task_id>.questions.md`

**子代理返回后验证**：检查 coverage 和 red-run 文件是否已生成。如果 Test Writer 产生了 open-questions，**暂停并向用户报告问题**，等待澄清后再继续。如果产出文件缺失，**报告用户**，不要继续 Phase B。

**验证通过后，立即封存 Phase A 产物**：

```
project-ai tdd seal-phase <task_id> test_writer --json
```

如果返回 `ok: false`（如 manifest 已存在），报告用户，不要继续。

### Phase B：孵化 Test Reviewer（审查测试）

**你必须调用 Agent 工具。** 参数如下：

- `subagent_type`: `"claude"`
- `description`: `"Test Reviewer for <task_id>"`
- `prompt`:
  ```
  Read and execute ALL instructions in .claude/skills/tdd-review-tests/SKILL.md.

  Task ID: <task_id>
  Risk level: <risk_level>

  You are an independent Test Reviewer sub-agent. Your ONLY job is to attack the tests.
  Do NOT implement production code. Do NOT write tests.
  When done, output whether tests are approved or not.

  <如果 risk_level 为 medium 或 high，追加：>
  CRITICAL: This is a medium/high-risk task. After the standard review, you MUST
  perform the "Cheating Implementation Probe" step described in your SKILL.md — design at
  least 3 cheating implementations, inject them, and verify tests catch them.
  ```

Test Reviewer 产出：
- `.project_ai/tdd/reviews/<task_id>.test-review.md`
- `.project_ai/tdd/approvals/<task_id>.approved.md`（如果测试通过审查）
- （risk_level >= medium）`.project_ai/tdd/cheating-probe-results/<task_id>.cheating-probe.md`

**子代理返回后验证**：检查 approval 文件是否已生成。如果没有 approval 文件，**向用户报告审查结果**（review 报告中的弱点），等待测试修复后重新进入 Phase A。如果 risk_level >= medium 且 cheating-probe 文件缺失，提示 Test Reviewer 补做 Cheating Implementation Probe。

**验证通过后，立即封存 Phase B 产物**：

```
project-ai tdd seal-phase <task_id> test_reviewer --json
```

如果返回 `ok: false`，报告用户，不要继续。

### Phase C：孵化 Implementer（实现功能）

**你必须调用 Agent 工具。** 参数如下：

- `subagent_type`: `"claude"`
- `description`: `"Implementer for <task_id>"`
- `prompt`:
  ```
  Read and execute ALL instructions in .claude/skills/tdd-implement-feature/SKILL.md.

  Task ID: <task_id>

  You are an independent Implementer sub-agent. Your ONLY job is to make
  approved tests pass. Do NOT modify tests. Do NOT modify specs.
  When done, output implementation summary and files changed.
  ```

**前置条件**：必须先运行 `project-ai tdd check-approval <task_id>` 确认 `approved: true`。

Implementer 产出：
- `src/` 下的实现代码
- `.project_ai/tdd/implementation-reports/<task_id>.implementation.md`

**子代理返回后验证**：运行 `project-ai tdd check-boundary <task_id>` 确认实现者没有越界修改测试或 spec 文件。如果有违规，**报告用户**，不标记任务完成。

**验证通过后，立即封存 Phase C 产物**：

```
project-ai tdd seal-phase <task_id> implementer --json
```

如果返回 `ok: false`，报告用户，不要继续。

### Phase C2：Spec Compliance Review（所有 TDD 任务强制，v5.4.0 新增）

实现完成后、E2E 之前，**你必须调用 Agent 工具孵化 Spec Compliance Reviewer 子代理**，验证实现是否真正匹配 spec——不多做、不漏做、不误解。

- `subagent_type`: `"claude"`
- `description`: `"Spec compliance review for <task_id>"`
- `prompt`:
  ```
  You are a Spec Compliance Reviewer. Your job is adversarial — you do NOT trust
  the implementer's report. You verify EVERYTHING independently by reading the
  actual code.

  Task ID: <task_id>

  ## What Was Requested

  1. Read the BDD spec files:
     <粘贴 tdd.spec_files 列表>
  2. Read the rule table files:
     <粘贴 tdd.rule_files 列表>
  3. Read the task description and acceptance criteria from the plan.

  ## What the Implementer Claims

  <从 .project_ai/tdd/implementation-reports/<task_id>.implementation.md 粘贴实现报告>

  ## Your Job

  Read the IMPLEMENTATION CODE (not the report) and verify:

  ### Missing requirements
  - Is EVERY acceptance criterion met by actual running code?
  - Are there spec requirements the implementer skipped or missed?
  - Did they claim something works but didn't really implement it?

  ### Extra/unneeded work (YAGNI violation)
  - Did they build things NOT in the spec?
  - Did they add "nice to haves" that weren't requested?
  - Did they over-engineer beyond what the spec requires?

  ### Misunderstandings
  - Did they interpret requirements differently than intended?
  - Did they solve a different problem than what the spec describes?
  - Did they implement the right feature in the wrong way?

  ### Spec-to-code traceability
  - Can you trace every spec scenario to the code that fulfills it?
  - Are there spec scenarios with NO corresponding code path?

  ## Output

  Write to .project_ai/tdd/spec-compliance/<task_id>.spec-compliance.md:

  ```
  # Spec Compliance Review — <task_id>

  ## Verdict: ✅ COMPLIANT | ❌ ISSUES FOUND

  ## Missing (spec requires, code doesn't deliver)
  - [file:line] <具体问题>
  - ...

  ## Extra (code delivers, spec doesn't require)
  - [file:line] <具体问题>
  - ...

  ## Misunderstood (code does something different from spec intent)
  - [file:line] <具体问题>
  - ...

  ## Traceability gaps (spec scenario → no matching code path)
  - Scenario "<name>": no implementation found

  ## Notes
  <any additional observations>
  ```

  **CRITICAL**: If you find MISSING or MISUNDERSTOOD issues, the verdict is ❌.
  Extra features alone may be acceptable if they're trivial, but flag them.
  ```

Spec Compliance Reviewer 产出：
- `.project_ai/tdd/spec-compliance/<task_id>.spec-compliance.md`

**子代理返回后处理**：
- 如果 verdict 是 `❌ ISSUES FOUND`：
  - 将问题报告给用户
  - **回退到 Phase C**，将 spec compliance 报告中的问题交给 Implementer 子代理修复
  - Implementer 修复后，重新运行 Spec Compliance Review
  - 循环直到 verdict 为 ✅
- 如果 verdict 是 `✅ COMPLIANT`：
  - **立即封存 Phase C2 产物**：
    ```
    project-ai tdd seal-phase <task_id> spec_compliance --json
    ```
  - 继续 Phase C3（E2E）或 Phase D（完成）

### Phase C3：浏览器 E2E 验证（仅 risk_level=high 且含 e2e_scenarios）

如果任务的 `tdd.e2e_scenarios` 字段存在且非空，**你必须额外调用一次 Agent 工具**：

- `subagent_type`: `"claude"`
- `description`: `"E2E verification for <task_id>"`
- `prompt`:
  ```
  You are an E2E verification agent. You must verify the implemented feature
  against real browser scenarios using Playwright (or equivalent).

  Task ID: <task_id>
  E2E scenarios:
  <粘贴 tdd.e2e_scenarios 内容>

  For each scenario:
  1. Start from a real user entry point (not a mounted component)
  2. Use real interactions (click, type, drag, keyboard — not direct store manipulation)
  3. Verify loading, success, error, and empty states
  4. Refresh the page and verify state persistence
  5. Verify error/failure paths

  Write results to .project_ai/tdd/e2e-results/<task_id>.e2e-results.md
  Include: scenario name, status (pass/fail), screenshots if failures, error details.
  ```

### Phase D：完成任务

所有 Phase 完成后：

1. 生成任务报告到 `.project_ai/task_reports/iteration_<N>/task_<task_id>_report.json`：
   ```json
   {
     "task_id": "<task_id>",
     "iteration": <N>,
     "risk_level": "<low|medium|high>",
     "status": "done",
     "files_created": ["src/xxx.py"],
     "files_modified": [],
     "exports": ["function xxx()", "class YYY"],
     "checks": { "test": "passed", "spec_compliance": "✅", "mutation": "<n_killed>/<n_total>", "e2e": "<pass/fail/skipped>" },
     "notes": "TDD 流程完成。"
   }
   ```
2. 追加完成摘要到 `.project_ai/dev_log.md`
3. 提示用户：
   ```
   任务 <task_id> TDD 流程已完成（风险等级: <risk_level>）。

   Test Writer       → .project_ai/tdd/coverage/<task_id>.coverage.md
   Test Reviewer     → .project_ai/tdd/reviews/<task_id>.test-review.md
   <如果 risk_level >= medium：> Cheating Probe  → .project_ai/tdd/cheating-probe-results/<task_id>.cheating-probe.md
   Implementer       → .project_ai/tdd/implementation-reports/<task_id>.implementation.md
   Spec Compliance   → .project_ai/tdd/spec-compliance/<task_id>.spec-compliance.md
   <如果 risk_level = high：> E2E Results      → .project_ai/tdd/e2e-results/<task_id>.e2e-results.md

   请运行以下命令验证并推进状态：

     project-ai task complete <task_id> --json
   ```

---

# Red Flags — STOP and Self-Correct

These thoughts mean you are rationalizing. Stop immediately.

## For the Scheduler (TDD flow)

| Thought | Reality |
|---------|---------|
| "I can write the tests myself, it's faster than spawning a sub-agent" | Role separation exists for a reason. Three roles in one context = identity play. Agent tool is mandatory. |
| "This task is simple, I'll skip the Test Reviewer" | Every TDD task goes through all three phases. Simplicity is not an exception. |
| "The sub-agent failed, I'll fix its output myself" | Fix the CONTEXT you provided, re-dispatch the sub-agent. Never patch sub-agent output manually. |
| "I'll read the TDD skill file and execute it inline" | You are FORBIDDEN from reading TDD skill files. They are for sub-agents only. |
| "One combined sub-agent can do test+review+implement" | Three phases = three independent sub-agents. Combining = destroying cognitive isolation. |
| "I'll skip checking the output files, I'm sure it worked" | Verify every output file exists after each sub-agent returns. No file = phase incomplete. |
| "This sub-agent is taking too long, let me just do it" | Wait for sub-agent completion. Rushing = quality collapse. |

## For the Standard flow (non-TDD tasks)

| Thought | Reality |
|---------|---------|
| "I know the codebase, I don't need to read context_files" | Context files tell you what the planner intended. Skip them = build the wrong thing. |
| "This file isn't in allowed_files but it's a small change" | allowed_files is a hard boundary. Touching anything outside = violation. Tell the user. |
| "The quality gate can be checked later" | Quality gates exist for a reason. Check them now or don't claim done. |
| "Close enough, I'll mark it done" | expected_files must all EXIST and BE CORRECT. "Close enough" = not done. |

---

## 不能完成的情况

如果遇到以下情况，**不要假装完成**：

| 情况 | 做法 |
|------|------|
| 任务描述不清晰，无法确定要做什么 | 告诉用户哪里不清楚，请求澄清 |
| 需要修改 `allowed_files` 之外的文件 | 列出需要额外修改的文件，让用户决策 |
| 依赖任务产出不存在 | 告诉用户先完成依赖任务 |
| 和已有的接口契约冲突 | 说明冲突点，让用户决定如何处理 |
| 类型检查/测试失败（标准流程） | 如实报告失败信息，`status` 不要写 `done` |
| **TDD: approval 文件未生成** | 报告审查结果，等待测试修复 |
| **TDD: open-questions 文件存在** | 暂停并向用户报告 spec 矛盾 |
| **TDD: boundary check 失败** | 报告用户，实现者违规修改了禁止文件 |
| **TDD: integrity check 失败** | 阶段封存产物被篡改——某个 agent 修改了其他 phase 的裁判文件。检查 manifest 中的 violations。 |
| **TDD: seal-phase 失败（manifest 已存在）** | 该阶段已被封存过。如果确实需要重新封存，先手动删除旧 manifest。 |
| **TDD: 测试在实现前就通过（绿灯）** | 这是无效测试，不继续实现 |
| **TDD: cheating probe 未全部杀死（risk>=medium）** | 报告用户哪些变异漏过了测试，要求 Test Writer 补测试后重新进入 Phase A |
| **TDD: e2e 失败（risk=high）** | 报告用户失败场景，要求 Implementer 修复后重新进入 Phase C |
| **调度器违规：自己写了测试/审查/实现代码** | 立即停止，删除自己写的代码，改为调用 Agent 工具孵化子代理 |
| **Spec Compliance Review 未通过（❌）** | 将问题回传给 Implementer 子代理修复，修复后重新运行 Spec Compliance Review，循环直到 ✅ |
| **Spec Compliance Review 发现 extra features** | 标记但不一定阻塞——trivial extras 可接受，significant extras 必须删除 |

---

## 快速参考

```
# 获取任务上下文（每次必做）
project-ai task context <task_id> --json

# TDD 命令
project-ai tdd run-test <task_id>
project-ai tdd check-approval <task_id>
project-ai tdd check-boundary <task_id>
project-ai tdd seal-phase <task_id> <phase>       （v5.5.0 阶段封存）
project-ai tdd check-integrity <task_id>          （v5.5.0 完整性检查）

# 任务报告路径
.project_ai/task_reports/iteration_<N>/task_<task_id>_report.json

# TDD 产出（v5.5.0）
.project_ai/tdd/coverage/<task_id>.coverage.md
.project_ai/tdd/reviews/<task_id>.test-review.md
.project_ai/tdd/approvals/<task_id>.approved.md
.project_ai/tdd/cheating-probe-results/<task_id>.cheating-probe.md  （risk_level >= medium · Phase B）
.project_ai/tdd/spec-compliance/<task_id>.spec-compliance.md        （所有 TDD 任务 · Phase C2）
.project_ai/tdd/mutation-results/<task_id>.mutation-results.md      （risk_level = high · Phase C 后）
.project_ai/tdd/e2e-results/<task_id>.e2e-results.md                （risk_level = high）

# 阶段封存清单（v5.5.0 · CLI 自动生成，禁止手动修改）
.project_ai/tdd/manifests/<task_id>.<phase>.manifest.json

# 用户验证命令（执行完提示用户运行）
project-ai task complete <task_id> --json
```
