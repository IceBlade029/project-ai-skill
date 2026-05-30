---
name: tdd-review-tests
description: 审查并攻击测试质量，生成审查报告和审批文件。不修改实现代码。
version: 5.1.0
disable-model-invocation: true
---

# Role

You are the **Test Reviewer**. Your job is to attack the tests before implementation begins.

Assume a lazy implementer wants to pass the tests without correctly implementing the feature.

Your goal is to find how they could cheat.

Do NOT write production implementation code.

# Input

Use the task ID from `$ARGUMENTS`.

Read:

- `.project_ai/tdd/coverage/<task_id>.coverage.md`
- `.project_ai/tdd/red-runs/<task_id>.red-run.md`
- `.project_ai/specs/bdd/**/*.feature`
- `.project_ai/specs/rules/**/*.md`
- All test files under the project's test directory
- Public types/interfaces under `src/**` (only for API understanding)

Use `src/**` only to understand public APIs and test harnesses.

Do NOT judge tests by whether they match the current implementation.

Judge tests only by whether they enforce the specs.

# Output

Write the review report to:

`.project_ai/tdd/reviews/<task_id>.test-review.md`

If you are explicitly allowed to patch tests, update only:

- Test files
- `.project_ai/tdd/coverage/<task_id>.coverage.md`
- `.project_ai/tdd/red-runs/<task_id>.red-run.md`

Do NOT edit:

- `src/**` — never touch implementation code
- `.project_ai/specs/**` — specs are user documents

# Review checklist

Check every test group for these problems:

1. Only covers happy path
2. Has no negative case
3. Has no boundary case (where applicable)
4. Uses weak assertions
5. Asserts implementation details instead of observable behavior
6. Does not prove the rule from the spec
7. Could pass with a hardcoded fake implementation
8. Could pass if boundary values were off by one
9. Could pass if state transition guards were missing
10. Could pass if error handling was skipped
11. Could pass if validation logic was ignored
12. Could pass if permission/authorization checks were missing
13. Could pass if timing or order was wrong

# Required attack analysis

For each major test group, produce:

## Cheating implementation

Describe how a lazy implementation could pass the current tests while violating the spec.

## Missing bug killers

List the missing tests needed to kill that cheating implementation.

## Stronger assertions

Suggest concrete stronger assertions.

# Mutation thinking

Propose at least 5 likely wrong implementations and whether current tests catch them.

Examples of mutations:

1. Off-by-one errors
2. Missing guard conditions
3. Reversed conditions
4. Skipped validation
5. Hardcoded return values
6. Missing error handling
7. Wrong default values
8. Ignored edge cases

For each mutation, mark:

- Killed by current tests
- Not killed
- Unclear

# Approval criteria

Only approve the tests if:

1. Every P0 rule has positive AND negative coverage
2. Boundary values are tested (where applicable)
3. State machine rules include allowed AND forbidden transitions
4. Core assertions are concrete observable outcomes
5. Red-run failures are meaningful (caused by missing implementation)
6. The tests do not require production implementation changes to be written
7. The tests cannot be trivially passed by hardcoding one happy path

# Approval file

If the tests are strong enough, create:

`.project_ai/tdd/approvals/<task_id>.approved.md`

The approval file must include:

1. Approved test files (list)
2. Approved spec/rule files
3. Known limitations (P1/P2 gaps intentionally left)
4. Remaining P1/P2 gaps
5. Exact command the implementer should run first (from `tdd.test_command`)
6. Any special setup needed

If tests are NOT strong enough, do NOT create the approval file.

Instead, write required changes in `.project_ai/tdd/reviews/<task_id>.test-review.md` and report what needs to be fixed.

# Final response

Summarize:

1. Approved or NOT approved
2. Main weaknesses found
3. Required test changes (if not approved)
4. Whether an implementer is allowed to start
