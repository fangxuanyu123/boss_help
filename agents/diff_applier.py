"""DiffApplier —— 纯机械操作，将 DiffResult 的改动应用到 Resume 对象"""
import logging
import re
from copy import deepcopy
from typing import Tuple, List
from thefuzz import fuzz
from models.resume import Resume, DiffChange, DiffResult, DiffAction

logger = logging.getLogger(__name__)


class ApplyError(Exception):
    """改动应用失败"""
    pass


class DiffApplier:
    """将 DiffResult 中的改动逐条应用到 Resume 对象。

    纯 Python 逻辑，不调用 LLM。对原始 Resume 做 deepcopy，
    然后逐条解析 target 路径、用 fuzzy matching 定位、执行操作。
    """

    SIMILARITY_THRESHOLD = 60  # 模糊匹配最低相似度

    def apply(self, original: Resume, diff: DiffResult) -> Tuple[Resume, List[str]]:
        """应用改动，返回 (修改后的Resume, 警告列表)"""
        resume = deepcopy(original)
        warnings: List[str] = []

        for i, change in enumerate(diff.changes):
            try:
                self._apply_one(resume, change)
            except ApplyError as e:
                msg = f"改动#{i} ({change.action.value} @ {change.target}) 应用失败: {e}"
                logger.warning(msg)
                warnings.append(msg)

        return resume, warnings

    def _apply_one(self, resume: Resume, change: DiffChange) -> None:
        target: str = change.target
        parts = target.split(".")
        if not parts:
            raise ApplyError("target 为空")

        root = parts[0]
        path = parts[1:] if len(parts) > 1 else []

        if root == "summary":
            self._apply_summary(resume, change)
        elif root == "title":
            self._apply_title(resume, change)
        elif root == "work_experiences":
            self._apply_to_list_field(resume.work_experiences, path, change, "work_experiences")
        elif root == "projects":
            self._apply_to_list_field(resume.projects, path, change, "projects")
        elif root == "skills":
            self._apply_to_list_field(resume.skills, path, change, "skills")
        elif root == "education":
            self._apply_to_list_field(resume.education, path, change, "education")
        elif root == "certifications":
            self._apply_certifications(resume, change)
        else:
            raise ApplyError(f"未知根字段: {root}")

    def _apply_summary(self, resume: Resume, change: DiffChange) -> None:
        if change.action == DiffAction.rewrite and change.rewritten:
            resume.summary = change.rewritten
        elif change.action == DiffAction.append and change.item:
            resume.summary = (resume.summary + " " + change.item).strip()
        else:
            raise ApplyError(f"summary 不支持 action={change.action}")

    def _apply_title(self, resume: Resume, change: DiffChange) -> None:
        if change.action == DiffAction.rewrite and change.rewritten:
            resume.title = change.rewritten
        else:
            raise ApplyError(f"title 不支持 action={change.action}")

    def _apply_to_list_field(self, items: list, path: list, change: DiffChange, field_name: str) -> None:
        """处理数组类字段：work_experiences / projects / skills / education"""
        if not path:
            raise ApplyError(f"{field_name} 缺少索引路径")

        idx_match = re.match(r'^\[(\d+)\]$', path[0])
        if not idx_match:
            raise ApplyError(f"{field_name} 路径格式错误: {path[0]}")
        idx = int(idx_match.group(1))
        if idx >= len(items):
            raise ApplyError(f"{field_name}[{idx}] 索引越界 (共{len(items)}条)")

        item = items[idx]
        sub_path = path[1:] if len(path) > 1 else []

        if not sub_path:
            raise ApplyError(f"{field_name}[{idx}] 需要指定子字段，如 responsibilities[0]")

        sub_field = sub_path[0]

        if sub_field in ("responsibilities", "achievements", "highlights", "items", "tech_stack"):
            self._apply_string_list(item, sub_field, sub_path[1:], change)
        else:
            if change.action == DiffAction.rewrite and change.rewritten and hasattr(item, sub_field):
                setattr(item, sub_field, change.rewritten)
            else:
                raise ApplyError(f"{field_name}[{idx}].{sub_field} 不支持 action={change.action}")

    def _apply_string_list(self, parent, field: str, path: list, change: DiffChange) -> None:
        """处理列表子字段：responsibilities[2] / items / tech_stack 等"""
        lst = getattr(parent, field, [])
        if not isinstance(lst, list):
            raise ApplyError(f"{field} 不是列表类型")

        if change.action == DiffAction.append:
            if change.item:
                lst.append(change.item)
            elif change.rewritten:
                lst.append(change.rewritten)
            return

        if change.action == DiffAction.delete:
            if path:
                idx = int(re.match(r'^\[(\d+)\]$', path[0]).group(1))
                if 0 <= idx < len(lst):
                    lst.pop(idx)
                return
            raise ApplyError(f"delete 需要子索引路径")

        if not path:
            raise ApplyError(f"{field} 没有子索引，无法定位具体条目")

        idx_match = re.match(r'^\[(\d+)\]$', path[0])
        if not idx_match:
            raise ApplyError(f"{field} 子路径格式错误: {path[0]}")
        idx = int(idx_match.group(1))

        if idx >= len(lst):
            raise ApplyError(f"{field}[{idx}] 索引越界 (共{len(lst)}条)")

        original_text = lst[idx]

        if change.action == DiffAction.rewrite:
            if change.original:
                similarity = fuzz.partial_ratio(change.original, original_text)
                if similarity < self.SIMILARITY_THRESHOLD:
                    raise ApplyError(
                        f"原文不匹配 (相似度{similarity}%)，原文='{original_text[:80]}...'，"
                        f"期望='{change.original[:80]}...'"
                    )
            lst[idx] = change.rewritten
        elif change.action == DiffAction.highlight:
            if change.rewritten:
                lst[idx] = change.rewritten
        elif change.action == DiffAction.reorder:
            logger.info("reorder action for %s[%d] — 仅记录，由前端提示", field, idx)
        else:
            raise ApplyError(f"{field} 不支持 action={change.action}")

    def _apply_certifications(self, resume: Resume, change: DiffChange) -> None:
        lst = resume.certifications
        if change.action == DiffAction.append and change.item:
            lst.append(change.item)
        elif change.action == DiffAction.append and change.rewritten:
            lst.append(change.rewritten)
        else:
            raise ApplyError(f"certifications 不支持 action={change.action}")
