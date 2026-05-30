"""确认文档解析 — 解析 CONFIRM_ITEM / ANSWER 标记."""

import os
import re

CONFIRM_FILES = {
    "product-vision": "product_vision_confirm.md",
    "planning": "iteration_plan_confirm.md",
    "iteration-plan": "iteration_plan_confirm.md",  # 向后兼容旧名
    "polishing-issues": "polishing_issues_confirm.md",
    "next-action": "next_action_confirm.md",
    "requirements-revision": "requirements_revision_confirm.md",
}

AMBIGUOUS_WORDS = ["随便", "都行", "看情况", "你决定", "无所谓"]

# 匹配 <!-- CONFIRM_ITEM: ITEM_ID --> ... <!-- ANSWER_START --> ... <!-- ANSWER_END -->
_CONFIRM_RE = re.compile(
    r"<!--\s*CONFIRM_ITEM:\s*(\w+)\s*-->.*?"
    r"<!--\s*ANSWER_START\s*-->(.*?)<!--\s*ANSWER_END\s*-->",
    re.DOTALL,
)


def run(cwd, confirm_type):
    """解析指定类型的确认文档。"""
    if confirm_type not in CONFIRM_FILES:
        return {
            "ok": False,
            "error_code": "UNKNOWN_CONFIRM_TYPE",
            "message": f"未知确认类型: {confirm_type}。支持: {list(CONFIRM_FILES.keys())}",
        }

    filename = CONFIRM_FILES[confirm_type]
    doc_path = os.path.join(cwd, ".project_ai", "confirmations", filename)

    if not os.path.isfile(doc_path):
        return {
            "ok": False,
            "error_code": "CONFIRM_FILE_NOT_FOUND",
            "message": f"确认文档不存在: .project_ai/confirmations/{filename}",
        }

    with open(doc_path, "r", encoding="utf-8") as f:
        content = f.read()

    # 清除旧反馈区块
    content = re.sub(
        r"<!--\s*AI_FEEDBACK_START\s*-->.*?<!--\s*AI_FEEDBACK_END\s*-->",
        "",
        content,
        flags=re.DOTALL,
    )

    # 提取所有确认项
    items = _CONFIRM_RE.findall(content)

    missing_items = []
    ambiguous_items = []
    answers = {}

    for item_id, answer in items:
        answer = answer.strip()
        answers[item_id] = answer

        if not answer or answer == "（待填写）":
            missing_items.append(item_id)
        elif any(w in answer for w in AMBIGUOUS_WORDS):
            ambiguous_items.append(item_id)

    confirmed = len(missing_items) == 0 and len(ambiguous_items) == 0

    return {
        "ok": True,
        "confirmed": confirmed,
        "confirm_type": confirm_type,
        "file": f".project_ai/confirmations/{filename}",
        "total_items": len(items),
        "missing_items": missing_items,
        "ambiguous_items": ambiguous_items,
        "answers": answers,
    }
