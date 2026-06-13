"""CLI 入口 — 命令行参数解析与路由."""

import sys
import os
import json
import argparse


def main():
    # 共享父解析器，所有子命令都接受 --json（当前为保持与 SKILL 文档兼容，CLI 始终输出 JSON）
    _parent = argparse.ArgumentParser(add_help=False)
    _parent.add_argument("--json", action="store_true", default=True, help="JSON 格式输出（默认启用）")

    parser = argparse.ArgumentParser(
        prog="project-ai",
        description="产品迭代管理 CLI 工具",
    )
    subparsers = parser.add_subparsers(dest="command", help="可用命令")

    # init
    p_init = subparsers.add_parser("init", parents=[_parent], help="初始化 .project_ai/ 目录")
    p_init.add_argument("--force", action="store_true", help="强制重新初始化（备份旧目录）")

    # status
    subparsers.add_parser("status", parents=[_parent], help="读取并输出当前状态")

    # validate
    subparsers.add_parser("validate", parents=[_parent], help="校验 state.json")

    # confirm
    p_confirm = subparsers.add_parser("confirm", parents=[_parent], help="解析确认文档")
    p_confirm.add_argument("type", help="确认类型")

    # advance
    p_advance = subparsers.add_parser("advance", parents=[_parent], help="推进状态")
    p_advance.add_argument("--event", required=True, help="事件名称")

    # task
    p_task = subparsers.add_parser("task", parents=[_parent], help="任务相关操作")
    task_sub = p_task.add_subparsers(dest="task_command")
    task_sub.add_parser("next", parents=[_parent], help="获取下一个可执行任务")
    p_context = task_sub.add_parser("context", parents=[_parent], help="生成任务上下文")
    p_context.add_argument("task_id", help="任务 ID")
    p_complete = task_sub.add_parser("complete", parents=[_parent], help="标记任务完成")
    p_complete.add_argument("task_id", help="任务 ID")
    task_sub.add_parser("sync", parents=[_parent], help="从 iteration_<N>_tasks.json 同步任务到 state.json")

    # tdd
    p_tdd = subparsers.add_parser("tdd", parents=[_parent], help="TDD 流程操作")
    tdd_sub = p_tdd.add_subparsers(dest="tdd_command")
    p_run_test = tdd_sub.add_parser("run-test", parents=[_parent], help="执行测试命令")
    p_run_test.add_argument("task_id", help="任务 ID")
    p_check_approval = tdd_sub.add_parser("check-approval", parents=[_parent], help="检查审批文件")
    p_check_approval.add_argument("task_id", help="任务 ID")
    p_check_boundary = tdd_sub.add_parser("check-boundary", parents=[_parent], help="检查文件边界违规")
    p_check_boundary.add_argument("task_id", help="任务 ID")
    # v5.5.0: 阶段封存与完整性检查
    p_seal_phase = tdd_sub.add_parser("seal-phase", parents=[_parent], help="封存 TDD 阶段产物")
    p_seal_phase.add_argument("task_id", help="任务 ID")
    p_seal_phase.add_argument("phase", help="阶段名称 (test_writer/test_reviewer/implementer/spec_compliance/e2e)")
    p_check_integrity = tdd_sub.add_parser("check-integrity", parents=[_parent], help="检查阶段产物完整性")
    p_check_integrity.add_argument("task_id", help="任务 ID")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return 1

    # 路由到对应模块
    result = _dispatch(args)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result.get("ok", False) else 1


def _dispatch(args):
    """根据命令路由到对应处理函数。"""
    from project_ai import state, confirm, tasks

    if args.command == "init":
        from project_ai.cli_init import run
        return run(args, cwd=os.getcwd())

    cwd = state.find_project_root()

    if args.command == "status":
        from project_ai.cli_status import run
        return run(cwd)

    if args.command == "validate":
        from project_ai.cli_validate import run
        return run(cwd)

    if args.command == "confirm":
        return confirm.run(cwd, args.type)

    if args.command == "advance":
        from project_ai.cli_advance import run
        return run(cwd, args.event)

    if args.command == "task":
        if args.task_command == "next":
            return tasks.next_task(cwd)
        elif args.task_command == "context":
            return tasks.task_context(cwd, args.task_id)
        elif args.task_command == "complete":
            return tasks.complete_task(cwd, args.task_id)
        elif args.task_command == "sync":
            return tasks.sync_tasks(cwd)
        else:
            return {"ok": False, "error_code": "INVALID_TASK_COMMAND", "message": f"Unknown task command: {args.task_command}"}

    if args.command == "tdd":
        from project_ai.cli_tdd import run
        return run(cwd, args)

    return {"ok": False, "error_code": "UNKNOWN_COMMAND", "message": f"Unknown command: {args.command}"}
