# reference.md — 详细参考

本文档是 `SKILL.md` 的配套参考手册。SKILL.md 是轻量执行指南，本文档是设计原理和详细规格。

---

## 1. 核心设计思想

### 1.1 文件驱动，脱离对话上下文

大模型有上下文窗口限制，对话历史可能在长会话中丢失。所有状态、决策、确认都保存在文件中，AI 每次执行从文件重新读取，不依赖对话记忆。

### 1.2 确定性 vs 非确定性分离

```
确定性 → CLI（project-ai）
  - 读/写 state.json
  - 校验数据完整性
  - 推进状态机
  - 解析确认文档
  - 计算文件哈希
  - 检测文件变更

非确定性 → AI（Skill）
  - 理解用户需求
  - 拆解功能到任务
  - 评估技术风险
  - 生成开发计划
  - 解释审计结果
  - 写复盘建议
```

### 1.3 双重权威源

| 文件类型 | 用途 | 冲突时 |
|----------|------|--------|
| JSON（state.json, tasks.json, backlog.json） | 流程、任务列表、依赖关系 | 机器权威 |
| Markdown（确认书、计划、报告） | 用户说明、验收意见、修改建议 | 用户权威 |

### 1.4 确认文件三段式

每个需要用户确认的文档都有三个状态：

- **未生成**：文件不存在 → AI 生成
- **已生成未确认**：存在但答案不完整 → AI 给反馈，不覆盖用户编辑
- **已确认有效**：答案合法 → 进入下一步

### 1.5 答案与问题分离

确认文档使用 HTML 注释标记：

```
<!-- CONFIRM_ITEM: ITEM_ID -->
### 问题标题
<!-- ANSWER_START -->
用户填写的答案
<!-- ANSWER_END -->
```

- AI 只读取 `ANSWER_START/END` 之间的内容
- AI 的反馈写入独立的 `AI_FEEDBACK_START/END` 区块
- 每次校验前先清空旧反馈区块

### 1.6 接口契约作为迭代桥梁

每轮迭代结束时，AI 从产出代码中提取所有对外接口，生成 `interface_spec.md`。

下一轮迭代的 task-runner 执行前必须读取这个文件，确保新代码与已有接口兼容。这解决了"跨会话上下文丢失"的问题。

---

## 2. 目录结构详解

### 2.1 `.project_ai/` 顶层

```
.project_ai/
├── state.json              # 全局状态机（唯一机器权威源）
├── dev_log.md               # 开发日志（每轮迭代和任务追加）
├── requirements/            # 用户放入需求文档的目录
├── confirmations/           # 确认文档（问答式，用户填写）
├── specs/                   # ★v5.3.0 BDD 规格文件
│   ├── bdd/                 # Gherkin .feature 场景文件（AI 自动生成）
│   │   └── coverage-matrix.md
│   └── rules/               # 规则表、状态机、决策表（AI 自动生成）
├── plans/                   # 开发计划
│   ├── product_vision.md
│   ├── product_backlog.json
│   ├── tech_stack.md
│   └── iteration_plans/
│       ├── iteration_1.md
│       ├── iteration_1_tasks.json
│       └── ...
├── tdd/                     # TDD 流程产出
│   ├── coverage/            # Test Writer 覆盖报告
│   ├── red-runs/            # 红跑记录
│   ├── reviews/             # Test Reviewer 审查报告
│   ├── approvals/           # 批准文件
│   ├── open-questions/      # Spec 矛盾标记
│   ├── mutation-results/    # ★v5.3.0 变异注入结果
│   ├── e2e-results/         # ★v5.3.0 浏览器 E2E 结果
│   ├── implementation-reports/  # Implementer 实现报告
│   └── blockers/            # 阻塞报告
├── task_reports/            # 每个任务的完成报告
│   ├── iteration_1/
│   │   └── task_I1_T01_report.json
│   └── ...
├── quality_gates/           # 质量门禁确认文件
├── iteration_reports/       # 每轮迭代的审计和复盘报告
│   ├── iteration_1_audit.md
│   ├── iteration_1_interface_spec.md
│   ├── iteration_1_review.md
│   └── ...
└── delivery/                # 最终交付物
    └── milestone_delivery_report.md
```

### 2.2 版本演进

| 目录 | v3.0.0 | v4.0.0 | v4.1.0 | v4.2.0 | v5.0.0 | v5.1.0 | v5.3.0 |
|------|--------|--------|--------|--------|--------|--------|--------|
| `skills/` | 按迭代存放动态生成的子 Skills | **已移除**（改为固定 task-runner） | 不变 | 不变 | **新增 3 个 TDD Skill**：tdd-write-tests、tdd-review-tests、tdd-implement-feature | 不变 | **新增 bdd-spec-writer**：AI 自动生成 BDD spec |
| `state.json` | `skill_version: "3.0.0"` | `skill_version: "4.0.0"` | `skill_version: "4.1.0"` | `skill_version: "4.2.0"` | `skill_version: "5.0.0"`，`schema_version: "2.0.0"` | `skill_version: "5.1.0"` | `skill_version: "5.3.0"` |
| `phase` 值 | 含 `skill_generation` 作为主路径 | `skill_generation` 降级为兼容路径 | 新增 `iteration_polishing` | 新增 `requirements_revision` | 不变（TDD 是任务级特性） | 不变 | 不变（9 个 phase） |
| 打磨流程 | review → backlog_update（轻量选择） | 同 v3.0.0 | review → **强制 polishing** → backlog_update | **polishing 修复强制通过 task-runner**，问题文档采用增量追加+状态流转 | 不变 | **自动模式**：polishing 修复任务自动循环执行 | 不变 |
| 需求管理 | 仅在 product_discovery 阶段一次性读取 | 不变 | 不变 | **支持中继修订**：backlog_update → requirements_revision → backlog_update | 不变 | 不变 | **BDD 自动生成**：planning 孵化 bdd-spec-writer，requirements_revision 复用更新 |
| 任务执行 | 动态 Skill 文件 | 固定 task-runner 单角色 | 不变 | 不变 | **TDD 三角色调度**：task-runner 自动协调 Test Writer→Reviewer→Implementer | 不变 | **强制 Agent 子代理**：execution 孵化 task-runner，TDD 角色独立子代理 |
| 质量门禁 | 无 | quality_gates 空壳 | 不变 | 不变 | **Approval 门禁 + 文件边界检查**：task complete 新增第 6/7 层验证 | 不变 | **变异注入反证 + E2E**：按 risk_level 分级验证 |
| 执行流程 | 每任务需用户手动确认 | 不变 | 不变 | 不变 | 不变 | **自动模式**：execution→audit→review 自动推进，polishing 修复自动执行 | **BDD→TDD→变异→E2E** 完整质量链 |

---

## 3. state.json 完整规格

### 3.1 字段说明

| 字段 | 类型 | 说明 |
|------|------|------|
| `schema_version` | string | 状态结构版本，用于未来升级兼容检测 |
| `skill_version` | string | Skill 版本，自动对齐 |
| `phase` | string | 主状态机标识（见下方允许值） |
| `current_step` | int (1-99) | 便于理解的步数展示，**不作为核心判断依据** |
| `target_step` | string | 控制执行深度（保留字段） |
| `current_iteration` | int | 当前迭代编号，从1开始，0=尚未开始迭代 |
| `current_iteration_goal` | string | 迭代目标描述 |
| `product_vision` | object | 结构化产品愿景数据 |
| `product_backlog` | array | 完整功能池 |
| `iteration_tasks` | array | 当前迭代任务列表 |
| `completed_iterations` | array | 已完成迭代摘要 |
| `decisions` | object | 全局需求决策 |
| `task_status` | object | `{task_id: "pending"\|"in_progress"\|"done"\|"blocked"}` |
| `file_snapshots` | object | 产出文件哈希记录 |
| `last_error` | object\|null | 最近错误信息 |
| `last_modified` | string | ISO 时间戳 |
| `environment_fingerprint` | string | 运行环境摘要（可选） |

### 3.2 phase 允许值

```
init               → 初始状态
product_discovery  → 产品发现（分析需求，建立愿景）
backlog_planning   → Backlog 规划（迭代划分）
iteration_planning → 迭代计划（详细开发计划）
skill_generation   → [旧版兼容] 子 Skills 生成
execution          → 执行督导
iteration_audit    → 迭代审计
iteration_review   → 迭代复盘
iteration_polishing → 迭代打磨（必经阶段，用户测试→问题分类→修复→文档更新→循环）
backlog_update     → 下一步决策
requirements_revision → 需求修订（重新审视需求，更新愿景和 Backlog）
next_iteration_scope → 下一轮范围确认
milestone_delivery → 阶段性交付
done               → [保留，不再由正常流程到达]
```

### 3.3 状态转换图

```
product_discovery
    │ product_vision_confirmed
    ▼
backlog_planning
    │ backlog_confirmed
    ▼
iteration_planning
    │ iteration_plan_confirmed
    ▼
[skill_generation] ←── 旧版路径，兼容
    │ execution_started
    ▼
execution
    │ all_tasks_done
    ▼
iteration_audit
    │ audit_done
    ▼
iteration_review
    │ review_done
    ▼
iteration_polishing ────────────────────┐
    │ polishing_done                    │ 用户提交新问题（循环打磨）
    ▼                                   │
backlog_update ───────────────────────────────────────────┐
    │ next_iteration           │ requirements_revision     │ continue_current_iteration
    ▼                          ▼                           ▼
next_iteration_scope    requirements_revision        iteration_polishing
    │ iteration_plan_confirmed  │ requirements_revision_done  │
    ▼                          ▼                           │
iteration_planning ←─────── backlog_update ←───────────────┘
    ...
    
backlog_update ── milestone_delivery ── backlog_update (阶段性交付，继续循环)
```

### 3.4 task_status 允许值

| 值 | 含义 |
|------|------|
| `pending` | 等待执行 |
| `in_progress` | 正在执行 |
| `done` | 已完成 |
| `blocked` | 被阻塞（需要人工介入） |

---

## 4. product_backlog.json 功能项格式

```json
{
  "id": "F001",
  "name": "用户注册",
  "description": "用户可以通过邮箱和密码注册账号",
  "priority": "must_have",
  "estimated_complexity": "M",
  "assigned_iteration": 1,
  "status": "current",
  "dependencies": [],
  "acceptance_criteria": [
    "用户可以填写邮箱和密码完成注册",
    "系统发送验证邮件"
  ],
  "history": [
    {"date": "2026-05-12", "action": "added", "reason": "用户首次提出"},
    {"date": "2026-05-20", "action": "priority_changed", "from": "could_have", "to": "must_have", "reason": "打磨阶段用户反馈"}
  ]
}
```

- `priority`：`must_have` / `should_have` / `could_have` / `wont_have_now`
- `estimated_complexity`：`S` / `M` / `L` / `XL`
- `status`：`backlog` / `current` / `done` / `deferred`
- `history`（v4.2.0 新增）：功能项的变更历史，记录每次增删改的时间、动作和原因。在需求修订时增量追加，**不删除已有功能项**（标记为 `wont_have_now` 或 `deferred`），确保旧代码的功能意图可追溯。

---

## 5. 任务结构格式（iteration_tasks）

```json
{
  "id": "I1_T01",
  "name": "初始化项目结构",
  "description": "创建项目基础目录、配置文件、依赖管理",
  "dependencies": [],
  "expected_files": ["src/main.py", "package.json", "tsconfig.json"],
  "quality_gates": [],
  "tdd": {
    "enabled": false
  }
}
```

- `id`：`I<迭代编号>_T<序号>`，如 `I1_T01`, `I2_T03`
- `dependencies`：依赖的任务 ID 列表（必须在当前迭代内）
- `expected_files`：任务完成后必须存在的文件
- `tdd`（v5.0.0 新增）：TDD 配置对象。当 `enabled: true` 时，task-runner 将自动协调三个角色
  - `enabled`：是否启用 TDD 流程
  - `test_command`：测试执行命令（必须可执行，如 `pytest tests/ -k test_xxx`）
  - `spec_files`：BDD 场景文件列表（相对于 `.project_ai/` 的路径）
  - `rule_files`：规则表文件列表
  - `type_files`：类型定义/接口文件列表
  - `test_style`：测试风格描述（用于 AI 生成一致风格的测试）

---

## 6. 确认文档完整格式

```markdown
# 确认文档标题

<!-- CONFIRM_ITEM: ITEM_ID_1 -->
### 问题1
问题描述
<!-- ANSWER_START -->
用户答案
<!-- ANSWER_END -->

<!-- CONFIRM_ITEM: ITEM_ID_2 -->
### 问题2
问题描述
<!-- ANSWER_START -->
用户答案
<!-- ANSWER_END -->

<!-- AI_FEEDBACK_START -->
**反馈日期**：2026-05-12
- [CONFIRM_ITEM: ITEM_ID_1] 答案缺失，请填写。
<!-- AI_FEEDBACK_END -->
```

规则：
- `CONFIRM_ITEM` 和 `ANSWER_START/END` 使用 HTML 注释标记
- AI 提取答案时使用正则：`<!-- CONFIRM_ITEM: (\w+) -->.*?<!-- ANSWER_START -->(.*?)<!-- ANSWER_END -->`（dotall 标志）
- AI 反馈写入 `AI_FEEDBACK_START/END`，**每次校验前先清除旧反馈**
- 答案判定模糊的词：随便、都行、看情况、你决定、无所谓

---

## 7. 任务报告格式

```json
{
  "task_id": "I1_T01",
  "iteration": 1,
  "status": "done",
  "files_created": ["src/main.py"],
  "files_modified": [],
  "exports": ["function login()", "interface User"],
  "checks": {
    "typecheck": "passed",
    "test": "passed"
  },
  "notes": ""
}
```

---

## 8. 旧版工作流参考（v3.0.0）

v3.0.0 的完整工作流包含以下阶段，这些阶段的设计思想保留，但执行方式已改变：

| 旧阶段 | 新版处理方式 |
|--------|-------------|
| 阶段0：初始化 | `project-ai init` CLI |
| 阶段1：产品愿景 | SKILL.md product_discovery 节 |
| 阶段2：Backlog 规划 | SKILL.md backlog_planning 节 |
| 阶段2.5：下轮范围 | SKILL.md next_iteration_scope 节 |
| 阶段3：迭代计划 | SKILL.md iteration_planning 节 |
| 阶段4：生成子 Skills | **已移除**，改为固定 task-runner |
| 阶段5：执行督导 | SKILL.md execution 节 + task-runner |
| 阶段6：审计验收 | SKILL.md iteration_audit 节 + `project-ai audit` |
| 阶段7：复盘 | SKILL.md iteration_review 节 |
| **阶段7.5：迭代打磨（新增 v4.1.0）** | SKILL.md iteration_polishing 节 — 用户测试→四分类→修复→强制文档更新→循环 |
| 阶段7.6：下一步 | SKILL.md backlog_update 节 |
| 阶段8：阶段性交付 | SKILL.md milestone_delivery 节 — 生成交付报告后回到 backlog_update，可继续迭代 |

---

## 9. 为什么放弃动态子 Skills

v3.0.0 的设计是：每个迭代为每个任务动态生成一个独立的 Skill 文件（如 `skills/iteration_1/task_I1_T01.md`），然后用户需要把它们复制到 `.claude/skills/` 目录下加载。

问题：
1. **文件爆炸**：每个迭代 5-8 个任务，3 轮迭代就 15-24 个 Skill 文件
2. **用户操作繁琐**：每轮都要复制/链接 Skill 文件
3. **上下文冗余**：每个子 Skill 都重复大量模板内容
4. **维护困难**：修改模板需要重新生成所有子 Skills

v4.0.0 方案：
- 一个固定的 `project-task-runner` Skill
- 任务上下文通过 `project-ai task context` CLI 动态获取
- 约束通过 JSON 结构化数据传递（allowed_files、forbidden_files）
- 用户无需任何额外操作

---

## 10. 运行锁机制（从 v3.0.0 保留）

- 状态变更操作前检查 `.project_ai/.lock` 文件
- 默认超时 30 分钟
- 有效锁存在时停止执行，提示用户
- 操作结束后删除锁文件

当前 v4.0.0 CLI 尚未实现运行锁（计划在后续版本加入）。

---

## 11. 错误处理参考（从 v3.0.0 保留）

| 场景 | 处理 |
|------|------|
| 需求文档为空 | 立即停止，引导放入文档 |
| state.json 损坏 | 备份旧文件，重建初始状态 |
| 答案格式错误 | 要求按规范填写 |
| 任务依赖环路 | 生成环路图，中断并要求修改 |
| 跨会话文件不一致 | 输出警告，用户决定 |
| 权限/写入失败 | 报告具体错误 |
| 审计时文件不可读 | 跳过该文件，继续审计 |
| 大量文件变更 (>20) | 提示整体审查，避免 token 耗尽 |
| 运行锁冲突 | 立即停止 |
| 为未来迭代生成任务 | 阻止并提示缩小范围 |
| 手动修改 state.json | 生成冲突报告 |

---

## 12. 从 v4.0.0 迁移到 v4.1.0

### 兼容性

v4.1.0 完全兼容 v4.0.0 的 `state.json`。旧项目的 `phase: "backlog_update"` 等状态会被新 CLI 和 Skill 正确识别。

### 迁移路径

| 旧项目当前状态 | 迁移后的行为 |
|---------------|-------------|
| 正处于 `backlog_update`（已完成 review，未选下一步） | 正常使用。若选"回到打磨阶段"，manager 会自动生成 `polishing_issues_confirm.md`，进入打磨流程 |
| 正处于 `execution` | 正常执行完成 → audit → review → 强制进入 polishing |
| 正处于 `iteration_audit` / `iteration_review` | 正常流转，`review_done` 后进入 polishing |
| `completed_iterations` 中已有记录（旧 CLI 在 `review_done` 写入） | `polishing_done` 会自动去重，不会重复记录 |

### 确认文档变化

- `next_action_confirm.md`：选项从 4 项减为 3 项（移除"暂停开发"，"最终交付"改为"阶段性交付"）
- 新增 `polishing_issues_confirm.md`：老项目首次进入 polishing 时由 manager 自动生成
- `next_action_confirm.md`：选项从 4 项减为 3 项（移除"暂停开发"，"最终交付"改为"阶段性交付"）

### 从 v4.1.0 迁移到 v4.2.0

#### 兼容性

v4.2.0 完全兼容 v4.1.0 的 `state.json`。旧项目的所有 phase 值、transition 和 confirm type 均保持不变。唯一的增量是新增 `requirements_revision` 阶段。

#### 迁移路径

| 旧项目当前状态 | 迁移后的行为 |
|---------------|-------------|
| 正处于 `backlog_update` | 正常使用。`next_action_confirm.md` 中新增"修订产品需求与愿景"选项 |
| 正处于其他任何 phase | 正常流转，在到达 `backlog_update` 时可选择需求修订 |
| `product_backlog.json` 中旧功能项无 `history` 字段 | 兼容。manager 首次读取时自动补充空 `history` |

#### 确认文档变化

- `next_action_confirm.md`：选项从 3 项增为 4 项（新增"修订产品需求与愿景"）
- 新增 `requirements_revision_confirm.md`：由 manager 在进入 requirements_revision 时自动生成

#### 不需要的操作

- 不需要运行 `init --force`
- 不需要手动修改 `state.json`
- 不需要删除任何旧文件

---

## 13. 从 v4.2.0 迁移到 v5.0.0

### 兼容性

v5.0.0 完全向后兼容 v4.2.0 的 `state.json`。`schema_version` 从 `1.0.0` 升级到 `2.0.0`，`skill_version` 从 `4.2.0` 升级到 `5.0.0`，但 CLI 能正确读取所有已有字段。

任务执行模式由 `tdd.enabled` 字段控制：
- 旧任务无 `tdd` 字段 → 使用原有单角色执行流程
- 新任务 `tdd.enabled: true` → 自动触发 TDD 三角色流程
- 新任务 `tdd.enabled: false` → 使用原有流程

### 迁移路径

| 旧项目当前状态 | 迁移后的行为 |
|---------------|-------------|
| 任何状态 | 已有任务继续按原流程执行（无 tdd 字段 = 无行为变化） |
| `iteration_planning` 准备新迭代 | Manager 可自动为适合 TDD 的任务添加 `tdd.enabled: true` |
| 旧 `project-ai init` 创建的项目 | 运行 `init --force` 重新初始化，会新增 10 个 TDD 目录 |

### 目录变化

新增目录（`project-ai init` 自动创建）：

```
.project_ai/
  specs/
    bdd/           ← BDD 场景文件（★v5.3.0 AI 自动生成，不再需要用户手动编写 .feature）
    rules/         ← 规则表文件（★v5.3.0 AI 自动生成）
  tdd/
    tasks/         ← TDD 任务详细说明
    coverage/      ← 测试覆盖报告
    reviews/       ← 测试审查报告
    red-runs/      ← 红灯运行报告
    approvals/     ← 审批文件（关键门禁）
    mutation-results/  ← ★v5.3.0 变异注入结果
    e2e-results/       ← ★v5.3.0 浏览器 E2E 结果
    implementation-reports/  ← 实现报告
    blockers/      ← 阻塞报告
    open-questions/  ← 待澄清问题
```

### 新增 CLI 命令

```
project-ai tdd run-test <task_id>        # 执行 tdd.test_command
project-ai tdd check-approval <task_id>  # 检查审批文件
project-ai tdd check-boundary <task_id>  # 检查实现者文件边界
```

### 新增错误码

| 错误码 | 含义 |
|--------|------|
| `TDD_APPROVAL_MISSING` | 审批文件不存在，实现者不能开始 |
| `TDD_FORBIDDEN_FILES_MODIFIED` | 实现者修改了禁止文件 |
| `TDD_NOT_ENABLED` | 任务未启用 TDD 模式 |
| `TDD_NO_TEST_COMMAND` | test_command 为空 |
| `TEST_COMMAND_TIMEOUT` | 测试命令执行超时 |
| `TEST_COMMAND_ERROR` | 测试命令执行异常 |

### 不需要的操作

- 不需要运行 `init --force`（除非需要新目录）
- 不需要手动修改 `state.json`
- 不需要删除任何旧文件
- 不需要修改已有任务的 `tdd` 字段

---

## 14. 需求修订机制（v4.2.0 新增）

### 14.1 设计动机

v4.1.0 及之前版本中，需求文档（`requirements/`）仅在 `product_discovery` 阶段被读取一次，之后变成"死文档"。用户只能在打磨阶段通过四分类间接注入新需求，但战略层面的方向调整（用户画像变化、竞品应对、MVP 范围重新划分）无正式入口。

### 14.2 分层处理策略

需求修订时，不同文件采用不同的更新策略：

| 文件 | 策略 | 原因 |
|------|------|------|
| `product_backlog.json` | **增量追加**（标记不删除） | 旧功能对应已有代码，删除会导致代码意图无法追溯 |
| `product_vision.md` | **完全替代**（带变更摘要） | 愿景应反映最新方向，旧版本通过变更摘要保留关键决策 |
| `requirements/` 目录 | **追加新文件**（带时间戳命名） | 完整保留需求演进历史，AI 以最新文件为准 |
| `interface_spec.md` | **不变**（事实锚点） | 代码的真实面貌不随需求变更而改变 |

### 14.3 冲突检测流程

当用户修订需求时，AI 必须执行以下冲突检测：

1. 读取最新 `interface_spec.md`（当前代码暴露了什么）
2. 读取当前 `product_backlog.json`（当前规划了什么）
3. 比对用户的变更请求：
   - **代码中已有但新需求不再需要** → 标记为待处理，用户确认后决定移除/保留/标记技术债务
   - **新需求与已有接口冲突** → 明确告知用户"改 X 会破坏 Y"
   - **新需求可在现有接口上扩展** → 最安全，直接进入 Backlog
4. 生成冲突报告给用户确认，**AI 不允许自行决定删除代码**

### 14.4 进入和退出

- **进入**：用户在 `backlog_update` 阶段选择"修订产品需求与愿景"
- **退出**：用户确认修订后，更新愿景和 Backlog，回到 `backlog_update`
- 可在任意轮迭代完成后触发，不限次数

### 14.5 `history` 字段格式

Backlog 中每个功能项可携带 `history` 数组，记录变更轨迹：

```json
{
  "id": "F005",
  "history": [
    {"date": "2026-05-12", "action": "added", "reason": "用户首次提出"},
    {"date": "2026-05-20", "action": "priority_changed", "from": "could_have", "to": "must_have", "reason": "需求修订：用户反馈核心价值变化"},
    {"date": "2026-05-28", "action": "deferred", "reason": "需求修订：方向调整，暂时搁置"}
  ]
}
```

`action` 允许值：`added` / `priority_changed` / `deferred` / `scope_changed` / `removed`

---

## 13. 新手术语表

| 术语 | 通俗解释 |
|------|----------|
| Backlog | 功能待办清单，列出所有想做的功能 |
| 迭代 (Iteration) | 一轮开发周期，通常完成一个用户可感知的功能切片 |
| MVP | 最小可行产品，第一个能跑起来的版本 |
| Phase | 阶段，状态机里的当前位置 |
| 接口契约 | 代码对外暴露的函数和数据结构清单 |
| 审计 (Audit) | 检查代码实际改了哪些文件，是否和计划一致 |
| 复盘 (Review) | 回顾这轮迭代做得好不好，有什么经验教训 |
| 质量门禁 | 任务完成前必须通过的检查项 |
| 文件快照 | 给文件算一个指纹（哈希），用于检测是否被修改过 |
| 状态转换 | 从一个阶段推进到下一个阶段 |
