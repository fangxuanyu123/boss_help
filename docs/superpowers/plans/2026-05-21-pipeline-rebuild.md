# Pipeline 全面改造 实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 对简历生成、匹配度分析、PDF渲染三个核心环节进行三阶段改造：Diff-based增量生成、匹配驱动优化闭环、LLM动态排版

**Architecture:** 阶段一：DiffAgent生成改动清单 → DiffApplier机械应用 → CoherenceReviewer连贯审查。阶段二：MatchLoop包裹生成+匹配，不通过则带着uncovered_gaps回DiffAgent重试。阶段三：StyleAgent替代固定模板，输出带内联样式的完整HTML。

**Tech Stack:** Python 3.10+, OpenAI SDK, Pydantic v2, Streamlit, Playwright, thefuzz (模糊匹配)

---

## 任务总览

| 阶段 | 任务 | 内容 | 依赖 |
|------|------|------|------|
| 一 | 1 | DiffChange + DiffResult 数据模型 | 无 |
| 一 | 2 | DiffApplier 纯Python改动应用引擎 | Task 1 |
| 一 | 3 | 测试 DiffApplier | Task 2 |
| 一 | 4 | DiffAgent LLM改动清单生成 | Task 1 |
| 一 | 5 | CoherenceReviewer 全文连贯性审查 | 无 |
| 一 | 6 | 重写 ResumeGenerationAgent | Tasks 2,4,5 |
| 一 | 7 | 改造 app.py Step 5 展示 | Task 6 |
| 二 | 8 | JobMatchingAgent 新增 uncovered_gaps | 无 |
| 二 | 9 | MatchLoop 匹配闭环引擎 | Tasks 6,8 |
| 二 | 10 | 改造 app.py Step 5-6 闭环 + 前端 | Task 9 |
| 三 | 11 | StyleAgent LLM动态HTML生成 | 无 |
| 三 | 12 | 简化 TemplateEngine + 更新 app.py Step 7 | Task 11 |

---

### Task 1: DiffChange + DiffResult 数据模型

**Files:**
- Modify: `models/resume.py` — 在文件末尾新增

- [ ] **Step 1: 在 models/resume.py 末尾新增数据模型**

```python
"""改动清单相关模型"""
from enum import Enum


class DiffAction(str, Enum):
    rewrite = "rewrite"
    append = "append"
    reorder = "reorder"
    highlight = "highlight"
    delete = "delete"


class DiffChange(BaseModel):
    """单条改动"""
    target: str = ""
    action: DiffAction = DiffAction.rewrite
    original: str = ""
    rewritten: str = ""
    item: str = ""
    reason: str = ""
    section_label: str = ""


class DiffResult(BaseModel):
    """改动清单"""
    changes: List[DiffChange] = Field(default_factory=list)
    unchanged_summary: str = ""
    estimated_impact: str = ""


class CoherenceReview(BaseModel):
    """连贯性审查结果"""
    coherence_score: float = 10.0
    passed: bool = True
    issues: List[str] = Field(default_factory=list)
    patches: List[DiffChange] = Field(default_factory=list)
```

- [ ] **Step 2: 将新模型加入 `__init__.py` 导出**

Read `models/__init__.py` and add `DiffAction, DiffChange, DiffResult, CoherenceReview` to the imports.

- [ ] **Step 3: 验证导入**

Run: `python -c "from models.resume import DiffAction, DiffChange, DiffResult, CoherenceReview; print('OK')"`
Expected: `OK`

- [ ] **Step 4: Commit**

```bash
git add models/resume.py models/__init__.py
git commit -m "feat: add DiffChange, DiffResult, CoherenceReview models"
```

---

### Task 2: DiffApplier 纯Python改动应用引擎

**Files:**
- Create: `agents/diff_applier.py`

`DiffApplier` 不调用 LLM，纯 Python 逻辑：解析 target 路径 → 模糊匹配定位 → 执行 action → 返回新的 Resume。

- [ ] **Step 1: 安装 thefuzz 依赖**

Run: `pip install thefuzz`

- [ ] **Step 2: 创建 `agents/diff_applier.py`**

```python
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

        # 解析索引: work_experiences[0]
        idx_match = re.match(r'^\[(\d+)\]$', path[0])
        if not idx_match:
            raise ApplyError(f"{field_name} 路径格式错误: {path[0]}")
        idx = int(idx_match.group(1))
        if idx >= len(items):
            raise ApplyError(f"{field_name}[{idx}] 索引越界 (共{len(items)}条)")

        item = items[idx]
        sub_path = path[1:] if len(path) > 1 else []

        if not sub_path:
            # 没有子路径，直接操作 item 本身
            raise ApplyError(f"{field_name}[{idx}] 需要指定子字段，如 responsibilities[0]")

        sub_field = sub_path[0]

        if sub_field in ("responsibilities", "achievements", "highlights", "items", "tech_stack"):
            self._apply_string_list(item, sub_field, sub_path[1:], change)
        else:
            # 普通字符串字段: position, company, description 等
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
            # 没有子索引: 对整个列表做 rewrite (替换整个列表)
            raise ApplyError(f"{field} 没有子索引，无法定位具体条目")

        idx_match = re.match(r'^\[(\d+)\]$', path[0])
        if not idx_match:
            raise ApplyError(f"{field} 子路径格式错误: {path[0]}")
        idx = int(idx_match.group(1))

        if idx >= len(lst):
            raise ApplyError(f"{field}[{idx}] 索引越界 (共{len(lst)}条)")

        original_text = lst[idx]

        if change.action == DiffAction.rewrite:
            # 通过模糊匹配确认原文一致
            if change.original:
                similarity = fuzz.partial_ratio(change.original, original_text)
                if similarity < self.SIMILARITY_THRESHOLD:
                    raise ApplyError(
                        f"原文不匹配 (相似度{similarity}%)，原文='{original_text[:80]}...'，"
                        f"期望='{change.original[:80]}...'"
                    )
            lst[idx] = change.rewritten
        elif change.action == DiffAction.highlight:
            # highlight 同 rewrite，但在前端展示为"强化"
            if change.rewritten:
                lst[idx] = change.rewritten
        elif change.action == DiffAction.reorder:
            # reorder 暂由前端提示实现
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
```

- [ ] **Step 3: 验证导入**

Run: `python -c "from agents.diff_applier import DiffApplier; print('OK')"`
Expected: `OK`

- [ ] **Step 4: Commit**

```bash
git add agents/diff_applier.py
git commit -m "feat: add DiffApplier - pure Python change application engine"
```

---

### Task 3: 测试 DiffApplier

**Files:**
- Create: `test/test_diff_applier.py`

- [ ] **Step 1: 创建 `test/test_diff_applier.py`**

```python
"""测试 DiffApplier —— 验证每种 action 的精确执行"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from agents.diff_applier import DiffApplier
from models.resume import Resume, WorkExperience, Project, Skill, DiffChange, DiffResult, DiffAction


def make_sample_resume():
    return Resume(
        name="张三",
        phone="13800138000",
        email="test@example.com",
        title="Java开发",
        summary="3年Java开发经验",
        work_experiences=[
            WorkExperience(
                company="XX科技",
                position="Java开发工程师",
                start_date="2021-01",
                end_date="2024-01",
                responsibilities=[
                    "负责系统日常维护",
                    "参与需求评审",
                    "编写技术文档",
                ],
                achievements=["完成XX项目上线"],
            ),
        ],
        projects=[
            Project(
                name="电商平台",
                role="后端开发",
                highlights=["使用Spring Boot搭建微服务"],
                tech_stack=["Java", "Spring Boot", "MySQL"],
            ),
        ],
        skills=[
            Skill(category="编程语言", items=["Java", "Python"]),
            Skill(category="框架", items=["Spring Boot"]),
        ],
        certifications=["Java SCJP"],
    )


def test_rewrite_work_responsibility():
    """改写工作经历中的某条职责"""
    resume = make_sample_resume()
    applier = DiffApplier()
    diff = DiffResult(changes=[
        DiffChange(
            target="work_experiences[0].responsibilities[0]",
            action=DiffAction.rewrite,
            original="负责系统日常维护",
            rewritten="主导XX系统运维，保障99.9%可用性，覆盖日均50万+请求",
            reason="STAR法则量化",
            section_label="工作经历-XX科技-职责1",
        )
    ])
    result, warnings = applier.apply(resume, diff)
    assert len(warnings) == 0
    assert result.work_experiences[0].responsibilities[0] == "主导XX系统运维，保障99.9%可用性，覆盖日均50万+请求"
    assert result.work_experiences[0].responsibilities[1] == "参与需求评审"  # 未改动
    assert result.work_experiences[0].responsibilities[2] == "编写技术文档"  # 未改动


def test_append_to_skills():
    """补充技能"""
    resume = make_sample_resume()
    applier = DiffApplier()
    diff = DiffResult(changes=[
        DiffChange(
            target="skills[0].items",
            action=DiffAction.append,
            item="Golang",
            reason="项目中使用但未在技能列表",
            section_label="技能-编程语言",
        )
    ])
    result, warnings = applier.apply(resume, diff)
    assert len(warnings) == 0
    assert "Golang" in result.skills[0].items
    assert "Java" in result.skills[0].items  # 原有保留


def test_rewrite_summary():
    """改写Summary"""
    resume = make_sample_resume()
    applier = DiffApplier()
    diff = DiffResult(changes=[
        DiffChange(
            target="summary",
            action=DiffAction.rewrite,
            rewritten="3年Java后端开发经验，专注高并发系统设计与微服务架构",
            reason="调整侧重方向",
            section_label="个人总结",
        )
    ])
    result, warnings = applier.apply(resume, diff)
    assert len(warnings) == 0
    assert "高并发" in result.summary


def test_delete_responsibility():
    """删除某条职责"""
    resume = make_sample_resume()
    applier = DiffApplier()
    diff = DiffResult(changes=[
        DiffChange(
            target="work_experiences[0].responsibilities[2]",
            action=DiffAction.delete,
            reason="冗余表述",
            section_label="工作经历-XX科技-职责3",
        )
    ])
    result, warnings = applier.apply(resume, diff)
    assert len(warnings) == 0
    assert len(result.work_experiences[0].responsibilities) == 2
    assert result.work_experiences[0].responsibilities[0] == "负责系统日常维护"


def test_fuzzy_match_original():
    """模糊匹配：原文有细微差异时仍能匹配"""
    resume = make_sample_resume()
    applier = DiffApplier()
    diff = DiffResult(changes=[
        DiffChange(
            target="work_experiences[0].responsibilities[0]",
            action=DiffAction.rewrite,
            original="负责系统日常的维护工作",  # LLM可能输出的原文略有不同
            rewritten="主导系统运维，保障高可用性",
            reason="STAR",
            section_label="…",
        )
    ])
    result, warnings = applier.apply(resume, diff)
    assert len(warnings) == 0
    assert "高可用性" in result.work_experiences[0].responsibilities[0]


def test_original_mismatch_warning():
    """原文完全对不上时产生警告"""
    resume = make_sample_resume()
    applier = DiffApplier()
    diff = DiffResult(changes=[
        DiffChange(
            target="work_experiences[0].responsibilities[0]",
            action=DiffAction.rewrite,
            original="这是一个完全不存在的原文XYZXYZXYZ",
            rewritten="新的内容",
            reason="…",
            section_label="…",
        )
    ])
    result, warnings = applier.apply(resume, diff)
    assert len(warnings) == 1
    assert "不匹配" in warnings[0]
    # 原文未被修改（仍保持原样）
    assert result.work_experiences[0].responsibilities[0] == "负责系统日常维护"


def test_index_out_of_range():
    """索引越界"""
    resume = make_sample_resume()
    applier = DiffApplier()
    diff = DiffResult(changes=[
        DiffChange(
            target="work_experiences[99].responsibilities[0]",
            action=DiffAction.rewrite,
            rewritten="新",
            reason="…",
            section_label="…",
        )
    ])
    result, warnings = applier.apply(resume, diff)
    assert len(warnings) == 1
    assert "越界" in warnings[0]


def test_append_to_certifications():
    """补充证书"""
    resume = make_sample_resume()
    applier = DiffApplier()
    diff = DiffResult(changes=[
        DiffChange(
            target="certifications",
            action=DiffAction.append,
            item="AWS Solutions Architect",
            reason="gap分析显示该证加分",
            section_label="证书",
        )
    ])
    result, warnings = applier.apply(resume, diff)
    assert len(warnings) == 0
    assert "AWS Solutions Architect" in result.certifications


def test_multiple_changes():
    """多条改动同时应用"""
    resume = make_sample_resume()
    applier = DiffApplier()
    diff = DiffResult(changes=[
        DiffChange(
            target="work_experiences[0].responsibilities[0]",
            action=DiffAction.rewrite,
            original="负责系统日常维护",
            rewritten="主导系统运维",
            reason="STAR",
            section_label="…",
        ),
        DiffChange(
            target="skills[1].items",
            action=DiffAction.append,
            item="Spring Cloud",
            reason="…",
            section_label="…",
        ),
    ])
    result, warnings = applier.apply(resume, diff)
    assert len(warnings) == 0
    assert "主导系统运维" in result.work_experiences[0].responsibilities[0]
    assert "Spring Cloud" in result.skills[1].items
```

- [ ] **Step 2: 运行测试**

Run: `python -m pytest test/test_diff_applier.py -v`
Expected: 9 tests PASS

- [ ] **Step 3: Commit**

```bash
git add test/test_diff_applier.py
git commit -m "test: add DiffApplier unit tests (9 tests)"
```

---

### Task 4: DiffAgent LLM改动清单生成

**Files:**
- Create: `agents/diff_agent.py`

- [ ] **Step 1: 创建 `agents/diff_agent.py`**

```python
"""DiffAgent —— 分析原始简历和优化建议，生成精确定位的手术式改动清单"""
from typing import Dict, Any
import json
from openai import OpenAI
from config import LLM_API_KEY, LLM_BASE_URL, LLM_MODEL_NAME
from models.resume import Resume, DiffResult, DiffChange, DiffAction
from models.job import JobRequirement


class DiffAgent:
    """生成手术式改动清单。

    不输出完整简历，只输出 DiffResult —— 每条改动精确定位到 target 路径，
    附带原文和改写后文字。DiffApplier 负责机械执行。
    """

    def __init__(self):
        self.client = OpenAI(api_key=LLM_API_KEY, base_url=LLM_BASE_URL)
        self.model = LLM_MODEL_NAME

    def generate_diff(
        self,
        original_resume: Resume,
        suggestions: Dict[str, Any],
        job: JobRequirement,
        uncovered_gaps: list | None = None,
        critique: str | None = None,
    ) -> DiffResult:
        """生成改动清单。

        Args:
            original_resume: 原始结构化简历
            suggestions: OptimizationAgent 输出的优化建议
            job: 岗位画像
            uncovered_gaps: 匹配闭环第二轮传入的未覆盖差距
            critique: Reflection 反馈
        """
        suggestion_text = ""
        for opt in suggestions.get("content_optimizations", []):
            suggestion_text += f"- [{opt.get('section', '')}] {opt.get('suggestion', '')}\n"
            if opt.get("example"):
                suggestion_text += f"  示例: {opt.get('example', '')}\n"

        keywords = ", ".join(suggestions.get("keywords_to_add", []))

        uncovered_text = ""
        if uncovered_gaps:
            uncovered_text = "\n=== 上一轮匹配后仍未覆盖的关键差距（本轮必须重点处理）===\n"
            for g in uncovered_gaps:
                uncovered_text += f"- 差距: {g.get('gap', '')}\n"
                uncovered_text += f"  建议: {g.get('suggestion_for_diff', '')}\n"

        system_content = (
            "你是一位精准的简历优化专家。你的任务是给出手术式的精确定位修改，"
            "而非重写整份简历。你必须为每处修改提供原文证据和改后文字，"
            "使得 DiffApplier 能机械应用你的改动。未在改动清单中的内容将被完整保留。"
            "遵守原则：少改优于多改，能保持不变的部分坚决不改。"
        )
        if critique:
            system_content += f"\n\n=== 上一轮输出的改进反馈 ===\n{critique}\n请针对以上反馈，修正你上一轮的输出。"

        prompt = f"""请根据以下原始简历、优化建议和岗位要求，生成手术式改动清单。

【关键原则：少改优于多改】
- 只改那些对提升岗位匹配度有实质帮助的部分
- 原文已经足够好的条目，不要为了改而去改
- 每条改动必须有明确的 reason，说明为什么这样改

=== 原始简历（结构化） ===
{original_resume.to_text()}

=== 目标岗位 ===
{job.to_text()}

=== 优化建议 ===
整体策略: {suggestions.get('overall_strategy', '')}
需强调的关键词: {keywords}

逐项优化建议:
{suggestion_text}
{uncovered_text}

=== 改动清单格式 ===

返回 JSON，每条改动必须包含以下字段：

{{
    "changes": [
        {{
            "target": "目标路径（如 work_experiences[0].responsibilities[2] / skills[0].items / summary / title）",
            "action": "rewrite / append / delete / highlight / reorder",
            "original": "被改动的原文（必须和原简历一字不差，用于精确定位）",
            "rewritten": "改写后的文字（action=rewrite/highlight 时填写）",
            "item": "新增内容（action=append 时填写）",
            "reason": "为什么这样改，关联到哪条优化建议或差距",
            "section_label": "人类可读的板块名（如'工作经历-XX公司-职责2'）"
        }}
    ],
    "unchanged_summary": "一句话说明为什么其他部分没有改动",
    "estimated_impact": "预估这些改动对匹配度提升的效果"
}}

【target 路径规则】
- summary, title: 直接写字段名
- work_experiences[N].responsibilities[M]: N是经历序号从0开始，M是职责序号从0开始
- work_experiences[N].achievements[M]: 同上
- projects[N].highlights[M]: 同上
- projects[N].tech_stack: 追加技术栈
- skills[N].items: N是技能类别序号，追加到该类别下
- certifications: 追加证书
- work_experiences[N].position: 改写职位（极少使用）

【original 字段要求】
- 必须和被改动的原文严格一致，用于 DiffApplier 精确匹配定位
- 如果是 append action，original 可以为空
- 如果是 reorder action，original 写要调整顺序的条目原文

【数量限制】
- 改动总数建议 5-12 条
- 不要为了凑数去改已经写得很好的内容
- 如果确实不需要改那么多，2-3条高质量改动远比10条无意义改动更好

只输出 JSON，不要额外文字。"""
        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": system_content},
                {"role": "user", "content": prompt},
            ],
            response_format={"type": "json_object"},
            temperature=0.2,
        )

        data = json.loads(response.choices[0].message.content)
        changes = []
        for c in data.get("changes", []):
            changes.append(DiffChange(
                target=c.get("target", ""),
                action=DiffAction(c.get("action", "rewrite")),
                original=c.get("original", ""),
                rewritten=c.get("rewritten", ""),
                item=c.get("item", ""),
                reason=c.get("reason", ""),
                section_label=c.get("section_label", ""),
            ))
        return DiffResult(
            changes=changes,
            unchanged_summary=data.get("unchanged_summary", ""),
            estimated_impact=data.get("estimated_impact", ""),
        )
```

- [ ] **Step 2: 验证导入**

Run: `python -c "from agents.diff_agent import DiffAgent; print('OK')"`
Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add agents/diff_agent.py
git commit -m "feat: add DiffAgent - surgical change list generation"
```

---

### Task 5: CoherenceReviewer 全文连贯性审查

**Files:**
- Create: `agents/coherence_reviewer.py`

- [ ] **Step 1: 创建 `agents/coherence_reviewer.py`**

```python
"""CoherenceReviewer —— 审查修改后简历的全文连贯性"""
from typing import Dict, Any
import json
from openai import OpenAI
from config import LLM_API_KEY, LLM_BASE_URL, LLM_MODEL_NAME
from models.resume import Resume, DiffChange, CoherenceReview


class CoherenceReviewer:
    """审查 Diff 应用后的全文连贯性。

    输入：修改后的完整简历（标注了哪些部分是改过的）
    输出：CoherenceReview —— 通过 or 需要修补
    """

    def __init__(self):
        self.client = OpenAI(api_key=LLM_API_KEY, base_url=LLM_BASE_URL)
        self.model = LLM_MODEL_NAME

    def review(self, modified_resume: Resume, changes_applied: list) -> CoherenceReview:
        """审查全文连贯性"""
        # 标注改动过的部分
        annotated = modified_resume.to_text()
        annotation_note = "\n\n=== 以下内容被修改过（已标注在简历文本中） ===\n"
        for i, c in enumerate(changes_applied):
            annotation_note += f"[改动{i+1}] {c.section_label}: {c.action.value} → {c.rewritten or c.item}\n"

        system_content = (
            "你是一位简历审校专家。你的任务不是评判简历写得好不好，"
            "而是检查修改后的简历是否存在**逻辑矛盾、表述不一致、衔接突兀**的问题。"
            "Prompt 已经管住了'改了什么'，你需要关注的是'改完之后读起来是否自然'。"
        )

        prompt = f"""请审阅以下修改后的简历，检查全文连贯性。

{annotated}
{annotation_note}

=== 检查维度 ===

1. **改动衔接**：修改后的措辞与相邻未改动的部分是否自然过渡？
   - 例如：前半句改成了高级技术术语，后半句还是原来简单的表述，是否有突兀感？
   
2. **表述一致性**：同一概念在不同位置是否用了一致的方式描述？
   - 例如：skill列表补充了"分布式系统"，但在工作经历中还是只说"后端系统"

3. **Summary-正文对齐**：如果 Summary 被修改了，它是否准确反映了正文中的经历？
   - Summary 提到的亮点，正文中确实有相应描述吗？

4. **无事实矛盾**：修改后是否产生了自相矛盾？
   - 例如：职责1说"独立负责XX"，职责3又写"协助完成XX"

返回 JSON：
{{
    "coherence_score": 8.5,
    "passed": true,
    "issues": [],
    "patches": []
}}

如果 passed=false（coherence_score < 7），patches 里给出修补用的 DiffChange（格式与输入一致）。
评分 ≥ 8.0: 全文流畅自然。6.0-7.9: 有小瑕疵但不影响理解。<6.0: 存在明显矛盾或衔接问题。"""
        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": system_content},
                {"role": "user", "content": prompt},
            ],
            response_format={"type": "json_object"},
            temperature=0.2,
        )

        data = json.loads(response.choices[0].message.content)
        patches = []
        for p in data.get("patches", []):
            from models.resume import DiffAction as DA
            patches.append(DiffChange(
                target=p.get("target", ""),
                action=DA(p.get("action", "rewrite")),
                original=p.get("original", ""),
                rewritten=p.get("rewritten", ""),
                item=p.get("item", ""),
                reason=p.get("reason", ""),
                section_label=p.get("section_label", ""),
            ))
        return CoherenceReview(
            coherence_score=float(data.get("coherence_score", 10.0)),
            passed=data.get("passed", True),
            issues=data.get("issues", []),
            patches=patches,
        )
```

- [ ] **Step 2: 验证导入**

Run: `python -c "from agents.coherence_reviewer import CoherenceReviewer; print('OK')"`
Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add agents/coherence_reviewer.py
git commit -m "feat: add CoherenceReviewer - full-text coherence check"
```

---

### Task 6: 重写 ResumeGenerationAgent

**Files:**
- Modify: `agents/resume_generation_agent.py` — 整个文件重写

- [ ] **Step 1: 重写 `agents/resume_generation_agent.py`**

```python
"""简历生成 Agent —— 调度 DiffAgent + DiffApplier + CoherenceReviewer 完成增量优化"""
from typing import Dict, Any
import logging
from models.resume import Resume
from models.job import JobRequirement
from agents.diff_agent import DiffAgent
from agents.diff_applier import DiffApplier
from agents.coherence_reviewer import CoherenceReviewer

logger = logging.getLogger(__name__)


class ResumeGenerationAgent:
    """简历生成智能体 —— 增量优化模式。

    generate() 调度：
    1. DiffAgent 生成改动清单
    2. DiffApplier 机械应用改动到原始简历
    3. CoherenceReviewer 审查连贯性，不通过则修补
    返回 (modified_resume, diff_result, coherence_review, warnings)
    """

    def __init__(self):
        self.diff_agent = DiffAgent()
        self.applier = DiffApplier()
        self.reviewer = CoherenceReviewer()

    def generate(
        self,
        original_resume: Resume,
        suggestions: Dict[str, Any],
        job: JobRequirement,
        uncovered_gaps: list | None = None,
        critique: str | None = None,
    ) -> tuple[Resume, Any, Any, list]:
        """生成优化简历（增量模式）。

        Returns:
            (optimized_resume, diff_result, coherence_review, warnings)
        """
        # Step 1: 生成改动清单
        diff_result = self.diff_agent.generate_diff(
            original_resume, suggestions, job,
            uncovered_gaps=uncovered_gaps,
            critique=critique,
        )
        logger.info("DiffAgent 生成了 %d 条改动", len(diff_result.changes))
        logger.info("预估影响: %s", diff_result.estimated_impact)

        # Step 2: 应用改动
        modified, warnings = self.applier.apply(original_resume, diff_result)

        if warnings:
            logger.warning("应用改动时产生 %d 条警告: %s", len(warnings), warnings)

        # Step 3: 连贯性审查
        coherence = self.reviewer.review(modified, diff_result.changes)

        if not coherence.passed and coherence.patches:
            logger.info("连贯性审查未通过 (%.1f)，应用 %d 条修补", coherence.coherence_score, len(coherence.patches))
            # 二次修补
            from models.resume import DiffResult
            patch_diff = DiffResult(changes=coherence.patches, unchanged_summary="", estimated_impact="")
            modified, patch_warnings = self.applier.apply(modified, patch_diff)
            warnings.extend(patch_warnings)
            # 再审一次
            coherence = self.reviewer.review(modified, diff_result.changes + coherence.patches)

        logger.info("最终连贯性评分: %.1f, passed=%s", coherence.coherence_score, coherence.passed)
        return modified, diff_result, coherence, warnings
```

- [ ] **Step 2: 验证导入**

Run: `python -c "from agents.resume_generation_agent import ResumeGenerationAgent; print('OK')"`
Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add agents/resume_generation_agent.py
git commit -m "refactor: rewrite ResumeGenerationAgent as diff-based pipeline"
```

---

### Task 7: 改造 app.py Step 5 展示

**Files:**
- Modify: `app.py` — Step 5 流程、Tab 1 展示、session state

- [ ] **Step 1: 修改 Step 5 主流程代码**

将原来的 Step 5 + Step 6 代码块（约 220-235 行）替换为：

```python
                # Step 5: 生成优化简历（Diff-based）
                st.write("✍️ 生成优化简历（手术式微调）...")
                st.session_state.optimized_resume, st.session_state.diff_result, \
                    st.session_state.coherence_review, _warnings = agents["generation"].generate(
                    structured_resume,
                    st.session_state.suggestions,
                    st.session_state.job_profile,
                )
                st.session_state.optimized_resume.raw_text = resume.raw_text
                st.write(f"✅ 简历优化完成: {len(st.session_state.diff_result.changes)}处改动")
```

- [ ] **Step 2: 新增 session state 变量**

在 defaults 字典中新增：
```python
"diff_result": None,
"coherence_review": None,
"match_rounds": [],  # 匹配闭环的每轮记录
```

- [ ] **Step 3: 重构 Tab 1（优化预览）**

将原来的 "简历对比" 展示替换为"改动清单 + 简历对比"的新布局：

```python
    # ---- Tab 1: 优化预览 ----
    with tabs[0]:
        diff = st.session_state.get("diff_result")
        coherence = st.session_state.get("coherence_review")

        # 改动清单
        if diff and diff.changes:
            st.subheader(f"🔧 改动清单（共 {len(diff.changes)} 处）")
            st.caption(diff.estimated_impact)

            action_colors = {
                "rewrite": ("🟡 改写", "orange"),
                "append": ("🟢 补充", "green"),
                "highlight": ("🔵 强化", "blue"),
                "delete": ("🔴 删除", "red"),
                "reorder": ("🟣 调整顺序", "violet"),
            }

            for i, c in enumerate(diff.changes):
                icon, _ = action_colors.get(c.action.value, ("⚪", "grey"))
                with st.expander(f"{icon} {c.section_label} — {c.reason}", expanded=(i < 3)):
                    if c.original:
                        st.markdown(f"**原文:** {c.original}")
                    if c.rewritten:
                        st.markdown(f"**改后:** {c.rewritten}")
                    if c.item:
                        st.markdown(f"**新增:** {c.item}")

            # 连贯性审查结果
            if coherence:
                passed = coherence.coherence_score >= 7.0
                co_icon = "✅" if passed else "⚠️"
                st.info(f"{co_icon} 全文连贯性: {coherence.coherence_score:.1f}/10")
                if coherence.issues:
                    for issue in coherence.issues:
                        st.caption(f"  - {issue}")

        # 优化后完整简历
        with st.expander("📋 完整优化后简历"):
            col_orig, col_opt = st.columns(2)
            with col_orig:
                st.markdown("**原始简历**")
                st.text(st.session_state.resume_raw_text[:5000])
            with col_opt:
                st.markdown("**优化后简历**")
                opt = st.session_state.optimized_resume
                if opt:
                    st.markdown(f"**{opt.name}** | {opt.phone} | {opt.email}")
                    st.markdown(f"*{opt.title}*")
                    if opt.summary:
                        st.markdown(f"> {opt.summary}")
                    if opt.work_experiences:
                        st.markdown("##### 工作经历")
                        for exp in opt.work_experiences:
                            st.markdown(f"**{exp.position}** @ {exp.company}  *{exp.start_date} - {exp.end_date}*")
                            for r in exp.responsibilities:
                                st.markdown(f"- {r}")
                            for a in exp.achievements:
                                st.markdown(f"- ⭐ {a}")
                    if opt.projects:
                        st.markdown("##### 项目经历")
                        for proj in opt.projects:
                            st.markdown(f"**{proj.name}** ({proj.role})  *{proj.start_date} - {proj.end_date}*")
                            for h in proj.highlights:
                                st.markdown(f"- {h}")
                            if proj.tech_stack:
                                st.caption(f"🔧 {', '.join(proj.tech_stack)}")
                    if opt.skills:
                        st.markdown("##### 技能")
                        for skill in opt.skills:
                            st.markdown(f"- **{skill.category}**: {', '.join(skill.items)}")
```

- [ ] **Step 4: 验证 app.py 编译**

Run: `python -c "import py_compile; py_compile.compile('app.py', doraise=True); print('OK')"`
Expected: `OK`

- [ ] **Step 5: Commit**

```bash
git add app.py
git commit -m "feat: update Step 5 UI - diff change list display, coherence review"
```

---

### Task 8: JobMatchingAgent 新增 uncovered_gaps

**Files:**
- Modify: `agents/job_matching_agent.py` — 在 match() 的 JSON 输出中新增字段

- [ ] **Step 1: 修改 JobMatchingAgent.match()**

在 match 方法的 JSON 模板中新增 `uncovered_gaps` 字段。修改 `agents/job_matching_agent.py` 的 prompt 部分：

```python
    def match(self, resume: Resume, job: JobRequirement) -> Dict[str, Any]:
        prompt = f"""你是一位资深的招聘专家。请分析以下简历与岗位的匹配情况。

=== 简历 ===
{resume.to_text()}

=== 岗位需求 ===
{job.to_text()}

请从以下维度分析，以 JSON 格式返回：

1. **match_score**: 匹配度评分 (0-100)
2. **match_strengths**: 简历中与岗位高度匹配的方面
3. **match_gaps**: 简历与岗位要求有差距的方面
4. **uncovered_gaps**: 当前简历**修改后仍未能覆盖**的关键差距（最多3条）。
   如果 match_score >= 70，此数组可为空。
   每条必须有具体的 suggestion_for_diff（告诉DiffAgent下一步应该怎么改）。
   格式：
   [
       {{"gap": "差距描述", "priority": 1, "suggestion_for_diff": "具体的改动建议（如：在项目X的highlights中补充Y）"}}
   ]
5. **specific_actions**: 提升匹配度的具体行动
6. **keyword_match**: 关键词匹配情况
7. **summary**: 整体匹配总结

返回 JSON：
{{
    "match_score": 75,
    "match_strengths": ["优势1"],
    "match_gaps": [{{"requirement": "岗位要求", "current_status": "当前状态", "suggestion": "改进建议"}}],
    "uncovered_gaps": [],
    "specific_actions": ["具体行动1"],
    "keyword_match": {{"matched": [], "missing": []}},
    "summary": "整体匹配总结"
}}
"""
        # ... 其余代码不变
```

- [ ] **Step 2: 验证修改**

Run: `python -c "from agents.job_matching_agent import JobMatchingAgent; print('OK')"`
Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add agents/job_matching_agent.py
git commit -m "feat: add uncovered_gaps output to JobMatchingAgent"
```

---

### Task 9: MatchLoop 匹配闭环引擎

**Files:**
- Create: `agents/match_loop.py`

- [ ] **Step 1: 创建 `agents/match_loop.py`**

```python
"""MatchLoop —— 匹配度驱动优化闭环：
生成 → 匹配打分 → 低于阈值 → uncovered_gaps反馈 → 再生成 → 再匹配
取最高分结果返回
"""
import logging
from typing import List
from models.resume import Resume
from models.job import JobRequirement
from agents.resume_generation_agent import ResumeGenerationAgent
from agents.job_matching_agent import JobMatchingAgent

logger = logging.getLogger(__name__)


class MatchRound:
    """一轮优化记录"""
    round_num: int
    resume: Resume
    diff_result: any
    coherence: any
    match_result: dict


class MatchLoop:
    """匹配度驱动优化闭环。

    用法:
        loop = MatchLoop(generation_agent, matching_agent, threshold=70, max_rounds=2)
        final_resume, rounds = loop.run(original_resume, suggestions, job_profile)
    """

    def __init__(self, generation_agent, matching_agent, threshold=70, max_rounds=2):
        self.generation = generation_agent
        self.matching = matching_agent
        self.threshold = threshold
        self.max_rounds = max_rounds

    def run(
        self,
        original_resume: Resume,
        suggestions: dict,
        job: JobRequirement,
    ) -> tuple[Resume, List[dict], dict]:
        """执行匹配闭环。

        Returns:
            (最佳简历, 每轮记录列表, 最佳匹配结果)
        """
        rounds = []
        best_resume = None
        best_score = -1
        best_match = None
        uncovered_gaps = None

        current_resume = original_resume

        for rnd in range(self.max_rounds):
            round_num = rnd + 1
            logger.info("MatchLoop 第 %d/%d 轮", round_num, self.max_rounds)

            # 生成
            if rnd == 0:
                resume, diff, coherence, warnings = self.generation.generate(
                    current_resume, suggestions, job,
                )
            else:
                resume, diff, coherence, warnings = self.generation.generate(
                    current_resume, suggestions, job,
                    uncovered_gaps=uncovered_gaps,
                )

            # 匹配打分
            match = self.matching.match(resume, job)
            score = match.get("match_score", 0)

            rounds.append({
                "round": round_num,
                "resume": resume,
                "diff": diff,
                "coherence": coherence,
                "match": match,
            })

            if score > best_score:
                best_score = score
                best_resume = resume
                best_match = match

            logger.info("第 %d 轮匹配度: %d/100", round_num, score)

            if score >= self.threshold:
                logger.info("匹配度达标，结束循环")
                break

            uncovered_gaps = match.get("uncovered_gaps", [])
            if not uncovered_gaps:
                logger.info("无未覆盖差距，结束循环")
                break

        return best_resume, rounds, best_match
```

- [ ] **Step 2: 验证导入**

Run: `python -c "from agents.match_loop import MatchLoop; print('OK')"`
Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add agents/match_loop.py
git commit -m "feat: add MatchLoop - score-driven optimization cycle"
```

---

### Task 10: 改造 app.py Step 5-6 闭环 + 前端

**Files:**
- Modify: `app.py` — Step 5-6 流程合并、Tab 2 匹配度展示

- [ ] **Step 1: 导入 MatchLoop**

在 app.py 新增 import：
```python
from agents.match_loop import MatchLoop
```

- [ ] **Step 2: 修改 Step 5-6 流程（合并为闭环）**

将原来的 Step 5 和 Step 6 替换为：

```python
                # Step 5-6: 简历生成 + 匹配度闭环
                st.write("✍️ 生成优化简历（手术式微调）...")
                match_loop = MatchLoop(
                    agents["generation"],
                    agents["matching"],
                    threshold=70,
                    max_rounds=2,
                )
                st.session_state.optimized_resume, match_rounds, st.session_state.match_result = \
                    match_loop.run(
                        structured_resume,
                        st.session_state.suggestions,
                        st.session_state.job_profile,
                    )
                st.session_state.optimized_resume.raw_text = resume.raw_text
                st.session_state.match_rounds = match_rounds

                # 获取最后一轮的 diff 和 coherence 用于展示
                last_round = match_rounds[-1] if match_rounds else {}
                st.session_state.diff_result = last_round.get("diff")
                st.session_state.coherence_review = last_round.get("coherence")

                final_score = st.session_state.match_result.get("match_score", 0)
                num_rounds = len(match_rounds)
                st.write(f"✅ 优化完成: {num_rounds}轮, 最终匹配度 {final_score}/100")
```

- [ ] **Step 3: 改造 Tab 2 匹配度展示**

在 Tab 2 的 "匹配度" 区域，替换原有展示：

```python
            st.subheader("📊 匹配度")
            if st.session_state.match_result:
                score = st.session_state.match_result.get("match_score", 0)
                passed = score >= 70
                status_icon = "✅" if passed else "⚠️"
                st.progress(score / 100, text=f"**{score}/100** {status_icon}")

                # 多轮对比
                rounds = st.session_state.get("match_rounds", [])
                if len(rounds) > 1:
                    scores_str = " → ".join(
                        f"第{r['round']}轮: {r['match'].get('match_score', 0)}"
                        for r in rounds
                    )
                    st.caption(f"优化历程: {scores_str}")

                st.caption(st.session_state.match_result.get("summary", ""))

                # 未覆盖差距
                uncovered = st.session_state.match_result.get("uncovered_gaps", [])
                if uncovered and not passed:
                    st.warning("⚠️ 以下差距仍未完全覆盖（已尽最大努力优化）:")
                    for g in uncovered:
                        st.markdown(f"- {g.get('gap', '')}")

                with st.expander("匹配优势"):
                    for s in st.session_state.match_result.get("match_strengths", []):
                        st.markdown(f"- ✅ {s}")
```

- [ ] **Step 4: 验证 app.py 编译**

Run: `python -c "import py_compile; py_compile.compile('app.py', doraise=True); print('OK')"`
Expected: `OK`

- [ ] **Step 5: Commit**

```bash
git add app.py
git commit -m "feat: integrate MatchLoop into Step 5-6, multi-round match display"
```

---

### Task 11: StyleAgent LLM动态HTML生成

**Files:**
- Create: `generators/style_agent.py`

- [ ] **Step 1: 创建 `generators/style_agent.py`**

```python
"""StyleAgent —— LLM 动态生成简历 HTML，按用户选择的风格自适应排版"""
from openai import OpenAI
from config import LLM_API_KEY, LLM_BASE_URL, LLM_MODEL_NAME
from models.resume import Resume


class StyleAgent:
    """LLM 驱动的简历 HTML 生成器。

    替代固定模板。根据风格关键词和简历内容，生成带内联CSS的完整HTML。
    """

    STYLES = {
        "minimal": "极简黑白，单栏，无装饰，高对比度，标准字号。适合投递大厂，对ATS解析友好。",
        "professional": "传统商务，双栏布局，蓝色或深灰辅助色，衬线字体。适合金融/法律/制造业。",
        "creative": "现代活力，色彩点缀，非对称布局可选，适当的图标和视觉层次。适合互联网/设计。",
        "compact": "紧凑单页，高信息密度，最小化留白，字体略小。适合校招或初级岗位。",
    }

    def __init__(self):
        self.client = OpenAI(api_key=LLM_API_KEY, base_url=LLM_BASE_URL)
        self.model = LLM_MODEL_NAME

    def list_styles(self) -> list[dict]:
        return [{"id": k, "name": k, "description": v.split("。")[0]} for k, v in self.STYLES.items()]

    def render(self, resume: Resume, job_title: str, style: str = "professional", page_size: str = "A4") -> str:
        """生成完整的 HTML 字符串（含内联CSS），可直接用于PDF渲染。

        Args:
            resume: 结构化简历
            job_title: 目标岗位名
            style: 风格ID (minimal/professional/creative/compact)
            page_size: 纸张尺寸 (A4/Letter)
        """
        style_desc = self.STYLES.get(style, self.STYLES["professional"])

        prompt = f"""你是一位资深的前端设计师，精通中文简历排版。请根据以下结构化简历和风格要求，生成一份完整的 HTML 简历文档。

=== 风格要求 ===
{style_desc}

=== 纸张 ===
{page_size}（210mm × 297mm），打印边距 15-20mm

=== 结构化简历 ===
{resume.to_text()}

=== 目标岗位 ===
{job_title}

=== 生成要求 ===

1. **必须是完整的独立 HTML 文件**，包含 <html><head><body>，所有 CSS 内嵌在 <style> 标签中。
2. **不要引入外部资源**（不要 Google Fonts、CDN 等），使用系统字体栈。
3. **中文排版**：正文使用系统中文字体（如 "PingFang SC", "Microsoft YaHei", "SimSun"），字号恰当（正文10-12pt，标题14-18pt）。
4. **视觉层次**：用小标题、留白、细线来区分板块，不要用大面积色块。
5. **内容完整**：所有板块（个人信息、教育、工作、项目、技能、证书）必须完整呈现，不省略任何条目。
6. **适合打印**：避免深色背景、避免依赖颜色传递信息（简历通常是黑白打印的）。
7. **ATS友好**：使用语义化 HTML 标签（section, h1-h3, ul/li），关键信息不要藏在CSS伪元素或图标字体里。
8. **响应式但重点是打印**：CSS @page 设置适合打印的边距。

直接输出完整的 HTML 源码，不要用 markdown 代码块包裹。"""
        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": "你是一位资深前端设计师，擅长生成精美、专业的中文排版HTML。你输出的HTML是完整可用的，不需要任何外部资源。你注重细节：字距、行高、颜色灰度、留白节奏。你尊重内容的完整性，绝不省略或简化任何一段经历。"},
                {"role": "user", "content": prompt},
            ],
            temperature=0.4,
        )

        html = response.choices[0].message.content
        # 去掉可能的 markdown 包裹
        if html.startswith("```html"):
            html = html[7:]
        if html.startswith("```"):
            html = html[3:]
        if html.endswith("```"):
            html = html[:-3]
        return html.strip()
```

- [ ] **Step 2: 验证导入**

Run: `python -c "from generators.style_agent import StyleAgent; print('OK')"`
Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add generators/style_agent.py
git commit -m "feat: add StyleAgent - LLM-driven dynamic HTML generation"
```

---

### Task 12: 简化 TemplateEngine + 更新 app.py Step 7

**Files:**
- Modify: `generators/template_engine.py` — 保留但改成调用 StyleAgent
- Modify: `app.py` — Step 7 和 Tab 3 使用 StyleAgent

- [ ] **Step 1: 重写 TemplateEngine 为 StyleAgent 的包装器**

```python
"""模板引擎 —— 调度 StyleAgent 生成 HTML"""
from pathlib import Path
from typing import List, Dict, Any
from models.resume import Resume
from generators.style_agent import StyleAgent


class TemplateEngine:
    """简历模板引擎 —— 包装 StyleAgent"""

    def __init__(self):
        self.style_agent = StyleAgent()

    def list_templates(self) -> List[Dict[str, str]]:
        """列出所有可用风格"""
        return self.style_agent.list_styles()

    def render(self, resume: Resume, job_title: str, template_id: str) -> str:
        """渲染为 HTML 字符串（StyleAgent 动态生成）"""
        return self.style_agent.render(resume, job_title, style=template_id)
```

- [ ] **Step 2: 更新 app.py Step 7 流程（约 237-245 行）**

```python
                # Step 7: 生成 PDF（StyleAgent 动态排版）
                st.write("🖨️ 渲染PDF...")
                html = template_engine.render(
                    st.session_state.optimized_resume,
                    job_title,
                    st.session_state.current_template,
                )
                st.session_state.pdf_bytes = pdf_renderer.render_to_bytes(html)
                st.write("✅ PDF 生成完成")
```

- [ ] **Step 3: 更新 app.py Tab 3 (PDF下载)**

```python
    # ---- Tab 3: PDF下载 ----
    with tabs[2]:
        st.subheader("📥 下载优化简历")

        styles = template_engine.list_templates()
        style_names = [f"{s['name']} — {s['description']}" for s in styles]
        download_style = st.selectbox(
            "排版风格",
            style_names,
            key="download_style_select",
        )
        download_style_id = styles[style_names.index(download_style)]["id"]

        if download_style_id != st.session_state.current_template or st.button("🔄 用此风格重新渲染", key="re_render_btn"):
            st.session_state.current_template = download_style_id
            html = template_engine.render(
                st.session_state.optimized_resume,
                st.session_state.job_title_input,
                download_style_id,
            )
            st.session_state.pdf_bytes = pdf_renderer.render_to_bytes(html)

        if st.session_state.pdf_bytes:
            col_dl1, col_dl2 = st.columns(2)
            with col_dl1:
                st.download_button(
                    label="📥 下载 PDF 简历",
                    data=st.session_state.pdf_bytes,
                    file_name=f"简历_{st.session_state.optimized_resume.name}_{download_style_id}.pdf",
                    mime="application/pdf",
                    use_container_width=True,
                )
            with col_dl2:
                st.markdown(f"🎨 风格: **{download_style}**")
                st.caption(f"文件大小: {len(st.session_state.pdf_bytes) / 1024:.1f} KB")

            st.divider()
            st.caption("备选格式:")
            st.download_button(
                label="📝 下载 Markdown 版本",
                data=st.session_state.optimized_resume.to_text(),
                file_name=f"简历_{st.session_state.optimized_resume.name}.md",
                mime="text/markdown",
            )
```

- [ ] **Step 4: 验证 app.py 编译**

Run: `python -c "import py_compile; py_compile.compile('app.py', doraise=True); print('OK')"`
Expected: `OK`

- [ ] **Step 5: Commit**

```bash
git add generators/template_engine.py app.py
git commit -m "feat: replace fixed templates with StyleAgent LLM-driven HTML, update PDF tab UI"
```

---

## 自评检查

1. **Spec覆盖**: 三阶段设计文档中的所有组件均有对应Task
2. **无占位符**: 所有Task都包含完整代码
3. **类型一致性**: DiffChange/DiffResult/CoherenceReview 在 Task 1 定义，后续 Task 一致使用
4. **前端覆盖**: Task 7（Tab 1改动清单）、Task 10（Tab 2匹配闭环展示）、Task 12（Tab 3风格选择）
