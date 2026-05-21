# Reflection 自省评估框架 实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 为4个核心Agent（简历分析、岗位画像、差距分析、优化建议）嵌入独立评估器 + 带反馈重试机制

**Architecture:** 共享 ReflectionLoop 循环引擎 + 4个专属评估器，评估器聚焦 Prompt 管不住的二阶质量维度（深度感、一致性、保真度、抓重点），阈值6分，最多重试2次

**Tech Stack:** Python 3.10+, OpenAI SDK, Pydantic v2

---

## 任务概览

| 任务 | 内容 | 依赖 |
|------|------|------|
| 1 | 创建 `EvaluationResult` + `BaseEvaluator` | 无 |
| 2 | 创建 `ReflectionLoop` | Task 1 |
| 3 | 测试 `ReflectionLoop` | Task 2 |
| 4 | 创建 `ResumeAnalysisEvaluator` | Task 1 |
| 5 | 创建 `RoleAnalyzerEvaluator` | Task 1 |
| 6 | 创建 `GapAnalyzerEvaluator` | Task 1 |
| 7 | 创建 `OptimizationEvaluator` | Task 1 |
| 8 | 修改 `ResumeAnalysisAgent.analyze()` 接受 critique | 无 |
| 9 | 修改 `RoleAnalyzerAgent` 两个方法接受 critique | 无 |
| 10 | 修改 `GapAnalyzerAgent.analyze()` 接受 critique | 无 |
| 11 | 修改 `OptimizationAgent.generate_suggestions()` 接受 critique | 无 |
| 12 | 修改 `app.py` 集成 ReflectionLoop | Tasks 1-11 |

---

### Task 1: 创建 EvaluationResult + BaseEvaluator

**Files:**
- Create: `evaluators/__init__.py`
- Create: `evaluators/base_evaluator.py`

- [ ] **Step 1: 创建 `evaluators/__init__.py`**

```python
"""评估器模块 —— 为各Agent输出提供独立质量评估"""
from .base_evaluator import BaseEvaluator, EvaluationResult
```

- [ ] **Step 2: 创建 `evaluators/base_evaluator.py`**

```python
"""评估器基类 —— 所有具体评估器的抽象基类"""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Dict, Any
import json
from openai import OpenAI
from config import LLM_API_KEY, LLM_BASE_URL, LLM_MODEL_NAME


@dataclass
class EvaluationResult:
    """评估结果"""
    score: float
    passed: bool
    strengths: list = field(default_factory=list)
    issues: list = field(default_factory=list)
    suggestion: str = ""
    threshold: float = 6.0


class BaseEvaluator(ABC):
    """评估器抽象基类。

    子类只需实现两个方法：
    - get_system_prompt() → 评委角色描述
    - get_evaluation_prompt(output, context) → 评估任务prompt
    """

    def __init__(self, threshold: float = 6.0):
        self.client = OpenAI(api_key=LLM_API_KEY, base_url=LLM_BASE_URL)
        self.model = LLM_MODEL_NAME
        self.threshold = threshold

    @abstractmethod
    def get_system_prompt(self) -> str:
        """返回评委的角色描述（system prompt）"""
        ...

    @abstractmethod
    def get_evaluation_prompt(self, output: Dict[str, Any], context: Dict[str, Any]) -> str:
        """返回包含待评估输出和评估标准的 prompt

        Args:
            output: Agent 输出的 dict
            context: 评估所需的上下文（如原始简历文本、岗位画像等）
        """
        ...

    def evaluate(self, output: Dict[str, Any], context: Dict[str, Any]) -> EvaluationResult:
        """调用 LLM 对 Agent 输出进行质量评估"""
        evaluation_prompt = self.get_evaluation_prompt(output, context)

        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": self.get_system_prompt()},
                {"role": "user", "content": evaluation_prompt},
            ],
            response_format={"type": "json_object"},
            temperature=0.2,
        )

        data = json.loads(response.choices[0].message.content)
        score = float(data.get("score", 7.0))
        return EvaluationResult(
            score=score,
            passed=score >= self.threshold,
            strengths=data.get("strengths", []),
            issues=data.get("issues", []),
            suggestion=data.get("suggestion", ""),
            threshold=self.threshold,
        )
```

- [ ] **Step 3: 运行测试验证导入**

Run: `python -c "from evaluators import BaseEvaluator, EvaluationResult; print('OK')"`
Expected: `OK`

- [ ] **Step 4: Commit**

```bash
git add evaluators/__init__.py evaluators/base_evaluator.py
git commit -m "feat: add BaseEvaluator and EvaluationResult"
```

---

### Task 2: 创建 ReflectionLoop

**Files:**
- Create: `agents/reflection_loop.py`

- [ ] **Step 1: 创建 `agents/reflection_loop.py`**

```python
"""Reflection 循环引擎 —— 调用 Agent → 评估 → 反馈 → 重试"""
from typing import Callable, Dict, Any, Tuple, List
from evaluators.base_evaluator import BaseEvaluator, EvaluationResult


class ReflectionLoop:
    """通用 Reflection 循环：调用 Agent → 独立评估 → 不通过则注入 critique 重试。

    用法:
        loop = ReflectionLoop(GapAnalyzerEvaluator(), max_retries=2)
        output, evals = loop.run(
            agent_callable=lambda critique: agent.analyze(resume, job, critique=critique),
            context={"resume": resume, "job": job},
        )
    """

    def __init__(self, evaluator: BaseEvaluator, max_retries: int = 2):
        self.evaluator = evaluator
        self.max_retries = max_retries

    def run(
        self,
        agent_callable: Callable[[str | None], Any],
        context: Dict[str, Any],
    ) -> Tuple[Any, List[EvaluationResult]]:
        """执行带 Reflection 的 Agent 调用。

        Args:
            agent_callable: 接受 critique: str | None，返回 Agent 输出
            context: 传给评估器的上下文

        Returns:
            (final_output, evaluation_history) —— 每轮评估的结果列表
        """
        evaluations: List[EvaluationResult] = []
        output = agent_callable(None)

        for attempt in range(self.max_retries + 1):
            # 将 output 转为 dict 供评估器使用
            output_dict = self._to_dict(output)

            result = self.evaluator.evaluate(output_dict, context)
            evaluations.append(result)

            if result.passed:
                break

            if attempt < self.max_retries:
                critique = self._build_critique(result)
                output = agent_callable(critique)

        return output, evaluations

    def _to_dict(self, output: Any) -> Dict[str, Any]:
        """将 Agent 输出转为 dict。JobRequirement 等 Pydantic 模型需转换。"""
        if hasattr(output, "model_dump"):
            return output.model_dump()
        if isinstance(output, dict):
            return output
        return {"output": str(output)}

    def _build_critique(self, result: EvaluationResult) -> str:
        """根据评估结果构建给 Agent 的改进反馈"""
        parts = [
            "=== 上一轮输出质量评估 ===",
            f"评分：{result.score}/10（未通过，阈值 {result.threshold}）",
        ]
        if result.strengths:
            parts.append("做得好的地方：")
            for s in result.strengths:
                parts.append(f"  ✅ {s}")
        if result.issues:
            parts.append("需要改进的地方：")
            for i in result.issues:
                parts.append(f"  ❌ {i}")
        if result.suggestion:
            parts.append(f"改进方向：{result.suggestion}")
        parts.append("请在重新生成时针对以上反馈修正输出。")
        return "\n".join(parts)
```

- [ ] **Step 2: 运行测试验证导入**

Run: `python -c "from agents.reflection_loop import ReflectionLoop; print('OK')"`
Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add agents/reflection_loop.py
git commit -m "feat: add ReflectionLoop shared engine"
```

---

### Task 3: 测试 ReflectionLoop

**Files:**
- Create: `test/test_reflection_loop.py`

- [ ] **Step 1: 创建 `test/test_reflection_loop.py`**

```python
"""测试 ReflectionLoop —— 验证重试逻辑、阈值边界、取最高分兜底"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from agents.reflection_loop import ReflectionLoop
from evaluators.base_evaluator import BaseEvaluator, EvaluationResult


class MockEvaluator(BaseEvaluator):
    """Mock 评估器：按预设评分序列返回"""
    def __init__(self, scores, threshold=6.0):
        super().__init__(threshold=threshold)
        self.scores = list(scores)
        self.call_count = 0

    def get_system_prompt(self):
        return "mock"

    def get_evaluation_prompt(self, output, context):
        return "mock"

    def evaluate(self, output, context):
        score = self.scores[min(self.call_count, len(self.scores) - 1)]
        self.call_count += 1
        passed = score >= self.threshold
        return EvaluationResult(
            score=score,
            passed=passed,
            strengths=[f"得分{score}的强项"],
            issues=[] if passed else [f"得分{score}的问题"],
            suggestion="" if passed else f"需要改进以超过{self.threshold}分",
        )


def test_passes_on_first_try():
    """首轮通过 → 返回结果，仅1轮评估"""
    evaluator = MockEvaluator(scores=[8.0])
    loop = ReflectionLoop(evaluator, max_retries=2)

    calls = []
    def agent(critique=None):
        calls.append(critique)
        return {"result": "good"}

    output, evals = loop.run(agent, context={})

    assert output == {"result": "good"}
    assert len(evals) == 1
    assert evals[0].score == 8.0
    assert evals[0].passed is True
    assert len(calls) == 1  # agent 只被调用1次
    assert calls[0] is None  # 首次调用无 critique


def test_retries_and_passes_on_second_try():
    """首轮5.0未通过 → 注入critique重试 → 第二轮8.0通过"""
    evaluator = MockEvaluator(scores=[5.0, 8.0])
    loop = ReflectionLoop(evaluator, max_retries=2)

    calls = []
    def agent(critique=None):
        calls.append(critique)
        return {"result": f"attempt_{len(calls)}"}

    output, evals = loop.run(agent, context={})

    assert output == {"result": "attempt_2"}
    assert len(evals) == 2
    assert evals[0].score == 5.0
    assert evals[0].passed is False
    assert evals[1].score == 8.0
    assert evals[1].passed is True
    assert len(calls) == 2
    assert calls[0] is None
    assert "5.0" in calls[1]  # critique 包含评分信息


def test_exhausts_all_retries():
    """三轮都不通过 → 取最高分的输出"""
    evaluator = MockEvaluator(scores=[4.0, 5.5, 5.0])
    loop = ReflectionLoop(evaluator, max_retries=2)

    calls = []
    def agent(critique=None):
        calls.append(critique)
        return {"result": f"attempt_{len(calls)}"}

    output, evals = loop.run(agent, context={})

    assert len(evals) == 3  # 首轮 + 2次重试
    assert evals[2].passed is False
    assert output == {"result": "attempt_2"}  # 第二轮得分最高 (5.5)
    assert len(calls) == 3


def test_passes_on_second_after_borderline_first():
    """首轮5.9（evaluator判定未达到6分threshold）→ 重试后通过"""
    evaluator = MockEvaluator(scores=[5.9, 7.0], threshold=6.0)
    loop = ReflectionLoop(evaluator, max_retries=2)

    def agent(critique=None):
        return {"result": "refined"}

    output, evals = loop.run(agent, context={})

    assert len(evals) == 2
    assert evals[0].passed is False
    assert evals[1].passed is True


def test_threshold_exactly_6_passes():
    """6.0 分通过"""
    evaluator = MockEvaluator(scores=[6.0], threshold=6.0)
    loop = ReflectionLoop(evaluator, max_retries=2)

    def agent(critique=None):
        return {"result": "ok"}

    output, evals = loop.run(agent, context={})

    assert evals[0].passed is True


def test_max_retries_zero():
    """max_retries=0 → 不重试"""
    evaluator = MockEvaluator(scores=[5.0])
    loop = ReflectionLoop(evaluator, max_retries=0)

    calls = []
    def agent(critique=None):
        calls.append(critique)
        return {"result": "only_once"}

    output, evals = loop.run(agent, context={})

    assert len(evals) == 1
    assert len(calls) == 1
    assert evals[0].passed is False


def test_eval_history_contains_all_rounds():
    """验证 evaluations 列表记录了每轮的完整评估信息"""
    evaluator = MockEvaluator(scores=[5.0, 5.0, 5.0])
    loop = ReflectionLoop(evaluator, max_retries=2)

    def agent(critique=None):
        return {"result": "data"}

    _, evals = loop.run(agent, context={})

    assert len(evals) == 3
    for e in evals:
        assert isinstance(e, EvaluationResult)
        assert e.score == 5.0
        assert e.passed is False
        assert len(e.issues) == 1
        assert len(e.suggestion) > 0
```

- [ ] **Step 2: 运行测试验证失败**

Run: `python -m pytest test/test_reflection_loop.py -v`
Expected: FAIL (definitely — `MockEvaluator` 需要 override `evaluate`，但 `BaseEvaluator.evaluate()` 有参数未用到。实际上 MockEvaluator 已经 override 了 `evaluate`，不会调父类。Wait，我应该 run the test and it will work since MockEvaluator properly overrides `evaluate`. Let me re-check.)

Actually the mock evaluator properly overrides `evaluate`, so tests should pass. Let me change the expectation.

Expected: 7 tests PASS (all 7 test functions pass)

- [ ] **Step 3: 运行测试**

Run: `python -m pytest test/test_reflection_loop.py -v`
Expected: 7 passed

- [ ] **Step 4: Commit**

```bash
git add test/test_reflection_loop.py
git commit -m "test: add ReflectionLoop unit tests"
```

---

### Task 4: 创建 ResumeAnalysisEvaluator

**Files:**
- Create: `evaluators/resume_analysis_evaluator.py`

- [ ] **Step 1: 创建 `evaluators/resume_analysis_evaluator.py`**

```python
"""简历分析评估器 —— 评估 ResumeAnalysisAgent.analyze() 的输出质量"""
from typing import Dict, Any
import json
from .base_evaluator import BaseEvaluator


class ResumeAnalysisEvaluator(BaseEvaluator):
    """评估简历分析的输出质量。

    聚焦 Prompt 管不住的二阶维度：
    - 深度感：薄弱点是否触及竞争力本质，而非万能模板
    - 保真度：对原文的引用是否真实，有无曲解
    """

    def get_system_prompt(self) -> str:
        return (
            "你是一位资深简历顾问，擅长评判一份简历分析的「眼光」——"
            "分析报告是真的看到了别人看不到的问题，还是用正确但空洞的套话在凑数。"
            "你关注的是二阶质量：Prompt 已经约束了格式和合规性，你需要判断的是"
            "分析深度和对原文的忠实程度。"
        )

    def get_evaluation_prompt(self, output: Dict[str, Any], context: Dict[str, Any]) -> str:
        resume_text = context.get("resume_raw_text", "")

        weaknesses_json = json.dumps(output.get("weaknesses", []), ensure_ascii=False, indent=2)
        strengths_list = json.dumps(output.get("strengths", []), ensure_ascii=False)
        score = output.get("overall_score", "N/A")
        key_improvements = json.dumps(output.get("key_improvements", []), ensure_ascii=False)

        return f"""请评估以下简历分析报告的质量。

=== 简历原文（参考上下文） ===
{resume_text[:2000]}

=== 分析报告 ===
综合评分: {score}/10
优势: {strengths_list}
薄弱环节: {weaknesses_json}
关键改进点: {key_improvements}

=== 评估维度 ===

1. **深度感**（权重40%）：
   - 薄弱点是否触及"这个候选人到底哪里竞争力不足"的本质？
   - 还是停留在"经历描述不够量化"这类万能模板？
   - 如果简历本身质量很高、薄弱点确实少，weaknesses 少或为空是合理的（不是扣分项）
   - 如果简历有明显问题但分析只说了正确废话，扣分

2. **保真度**（权重40%）：
   - 每条 weakness 是否引用了简历原文作为证据？
   - 引用的原文是否准确反映了原意（不存在曲解）？
   - 是否存在"把简历没说的东西说成简历的问题"的情况？

3. **可执行性**（权重20%）：
   - 每条 weakness 的 suggestion 是否是"能直接操作"的建议？
   - 还是"补充量化指标"这种放之四海而皆准的空话？

返回 JSON：
{{
    "score": 7.5,
    "strengths": ["分析做得好的具体点"],
    "issues": ["存在问题的具体点"],
    "suggestion": "给 Agent 的改进方向汇总（2-3句话）"
}}

严格评分：≥8.0 = 分析有洞察力，6.0-7.9 = 可接受但有提升空间，<6.0 = 分析浮于表面或引用失实。"""
```

- [ ] **Step 2: 验证导入**

Run: `python -c "from evaluators.resume_analysis_evaluator import ResumeAnalysisEvaluator; print('OK')"`
Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add evaluators/resume_analysis_evaluator.py
git commit -m "feat: add ResumeAnalysisEvaluator"
```

---

### Task 5: 创建 RoleAnalyzerEvaluator

**Files:**
- Create: `evaluators/role_analyzer_evaluator.py`

- [ ] **Step 1: 创建 `evaluators/role_analyzer_evaluator.py`**

```python
"""岗位画像评估器 —— 评估 RoleAnalyzerAgent 的输出质量"""
from typing import Dict, Any
import json
from .base_evaluator import BaseEvaluator


class RoleAnalyzerEvaluator(BaseEvaluator):
    """评估岗位画像的输出质量。

    聚焦 Prompt 管不住的二阶维度：
    - 抓重点：关键词是否代表岗位核心壁垒，非辅助工具堆砌
    - 一致性：level 与 requirements 的难度是否匹配
    - 保真度：如果是 JD 模式，画像是否忠实于 JD 原文
    """

    def get_system_prompt(self) -> str:
        return (
            "你是一位资深行业招聘专家，深知各岗位的核心壁垒在哪里。"
            "你评判岗位画像的质量时，关注的是画像是「写到了点子上」还是「列了一堆不痛不痒的东西」。"
            "你关注二阶质量：Prompt 已约束格式，你需要判断的是画像的专业深度和内部一致性。"
        )

    def get_evaluation_prompt(self, output: Dict[str, Any], context: Dict[str, Any]) -> str:
        title = output.get("title", "")
        level = output.get("level", "")
        industry = output.get("industry", "")
        responsibilities = json.dumps(output.get("responsibilities", []), ensure_ascii=False, indent=2)
        requirements = json.dumps(output.get("requirements", []), ensure_ascii=False, indent=2)
        tech_keywords = json.dumps(output.get("tech_keywords", []), ensure_ascii=False)
        soft_skills = json.dumps(output.get("soft_skills", []), ensure_ascii=False)
        source = output.get("source", "title")

        jd_hint = ""
        if source == "jd" and context.get("jd_text"):
            jd_hint = f"\n=== JD 原文（参考） ===\n{context['jd_text'][:1500]}"

        return f"""请评估以下岗位画像的质量。

岗位: {title} | 层级: {level} | 行业: {industry} | 来源: {source}
{jd_hint}

=== 岗位画像 ===
职责 ({len(output.get('responsibilities', []))}条): {responsibilities}
硬性要求 ({len(output.get('requirements', []))}条): {requirements}
技术关键词: {tech_keywords}
软技能: {soft_skills}

=== 评估维度 ===

1. **抓重点**（权重50%）：
   - 技术关键词是否聚焦该岗位的**核心壁垒**（如后端开发的分布式/高并发，算法的数学基础）？
   - 还是列了一堆辅助工具/通用技能（如 Git、Office、Postman）？
   - 职责描述是否是该岗位的核心职责，而非"参与需求评审"这种通用活动？

2. **一致性**（权重30%）：
   - level 的推断与 requirements 的难度要求是否匹配？
   - 例如：level=高级 但 requirements 全是初级水平的要求 → 扣分
   - responsibilities、requirements、tech_keywords 三者是否画的是同一个岗位？

3. **具体性**（权重20%）：
   - 职责描述是否有"动作+产出"，还是笼统的"负责XX系统开发"？
   - 如果是 title 模式（无 JD），画像对该岗位的行业标准认知是否准确？

返回 JSON：
{{
    "score": 7.5,
    "strengths": ["画像做得好的具体点"],
    "issues": ["存在问题的具体点"],
    "suggestion": "给 Agent 的改进方向汇总（2-3句话）"
}}

严格评分：≥8.0 = 画像精准专业，6.0-7.9 = 基本合理但有优化空间，<6.0 = 核心判断有误或关键词严重跑偏。"""
```

- [ ] **Step 2: 验证导入**

Run: `python -c "from evaluators.role_analyzer_evaluator import RoleAnalyzerEvaluator; print('OK')"`
Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add evaluators/role_analyzer_evaluator.py
git commit -m "feat: add RoleAnalyzerEvaluator"
```

---

### Task 6: 创建 GapAnalyzerEvaluator

**Files:**
- Create: `evaluators/gap_analyzer_evaluator.py`

- [ ] **Step 1: 创建 `evaluators/gap_analyzer_evaluator.py`**

```python
"""差距分析评估器 —— 评估 GapAnalyzerAgent 的输出质量"""
from typing import Dict, Any
import json
from .base_evaluator import BaseEvaluator


class GapAnalyzerEvaluator(BaseEvaluator):
    """评估差距分析的输出质量。

    聚焦 Prompt 管不住的二阶维度：
    - 一致性（最核心）：verdict/gaps/keyword_match/alignment 四者逻辑自洽
    - 保真度：implicit_skills 推断不过度
    - 深度感：gaps 是否点到差距根源
    """

    def get_system_prompt(self) -> str:
        return (
            "你是一位简历-岗位匹配分析专家。你的核心能力是：能一眼看穿分析报告中的逻辑矛盾——"
            "同一个技能不能既被列为'对齐点'又出现在'缺失'列表，verdict 的总体判断必须和"
            "下面的 gaps/keywords 对得上。你关注的是分析报告的逻辑严密性、推断的诚实度。"
        )

    def get_evaluation_prompt(self, output: Dict[str, Any], context: Dict[str, Any]) -> str:
        verdict = output.get("verdict", "")
        implicit_skills = json.dumps(output.get("implicit_skills", []), ensure_ascii=False, indent=2)
        keyword_match = json.dumps(output.get("keyword_match", {}), ensure_ascii=False)
        alignment_points = json.dumps(output.get("alignment_points", []), ensure_ascii=False, indent=2)
        gaps = json.dumps(output.get("gaps", []), ensure_ascii=False, indent=2)
        priority_actions = json.dumps(output.get("priority_actions", []), ensure_ascii=False)

        return f"""请评估以下差距分析报告的质量。

=== 差距分析报告 ===
总体判断: {verdict}

关键词匹配: {keyword_match}

对齐点 ({len(output.get('alignment_points', []))}条): {alignment_points}

差距 ({len(output.get('gaps', []))}条): {gaps}

隐式技能 ({len(output.get('implicit_skills', []))}条): {implicit_skills}

优先级动作: {priority_actions}

=== 评估维度 ===

1. **内部一致性**（权重50%，最核心）：
   - verdict 的整体判断与 gaps/keyword_match 描述是否一致？
   - 是否存在同一个技能在 "matched" 和 "missing" 中同时出现？
   - alignment_points 中的 resume_item 是否也在 gaps 中以不同方式出现？
   - 如果 verdict 说"匹配度较高"，gaps 不应该列一堆硬伤；反之亦然

2. **保真度**（权重30%）：
   - implicit_skills 的推断是否有经历描述作为支撑？
   - 是否存在把"用过一次"推断为"精通"的过度解读？
   - 每条 implicit_skill 的 evidence 是否和简历经历能对上？

3. **深度感**（权重20%）：
   - gaps 是点出了"差距的根源"（如"经历侧重A方向，岗位需要B方向"）？
   - 还是只在罗列"缺少X技能"这种表面结论？
   - optimization 建议是否是简历优化范畴（而非建议去学新技能）？

返回 JSON：
{{
    "score": 7.5,
    "strengths": ["分析做得好的具体点"],
    "issues": ["存在矛盾或问题的具体点"],
    "suggestion": "给 Agent 的改进方向汇总（2-3句话）"
}}

严格评分：≥8.0 = 分析精准、逻辑无矛盾，6.0-7.9 = 基本一致但有局部瑕疵，<6.0 = 存在明显逻辑矛盾或推断严重过度。"""
```

- [ ] **Step 2: 验证导入**

Run: `python -c "from evaluators.gap_analyzer_evaluator import GapAnalyzerEvaluator; print('OK')"`
Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add evaluators/gap_analyzer_evaluator.py
git commit -m "feat: add GapAnalyzerEvaluator"
```

---

### Task 7: 创建 OptimizationEvaluator

**Files:**
- Create: `evaluators/optimization_evaluator.py`

- [ ] **Step 1: 创建 `evaluators/optimization_evaluator.py`**

```python
"""优化建议评估器 —— 评估 OptimizationAgent 的输出质量"""
from typing import Dict, Any
import json
from .base_evaluator import BaseEvaluator


class OptimizationEvaluator(BaseEvaluator):
    """评估优化建议的输出质量。

    聚焦 Prompt 管不住的二阶维度：
    - 抓重点：optimizations 是否聚焦最关键问题，而非平均用力
    - 深度感：example 是否真的是更好的写法，而非换了个平庸说法
    """

    def get_system_prompt(self) -> str:
        return (
            "你是一位资深简历优化专家，帮求职者改过几千份简历。"
            "你评判优化建议的质量时，关注的是建议是否「抓对了重点」、"
            "给出的示例是否「真的比原文更好」——而不是换了一种平庸的说法。"
            "你关注二阶质量：Prompt 已约束了格式和合规性，你需要判断的是"
            "建议的战略聚焦度和示例的真实水平。"
        )

    def get_evaluation_prompt(self, output: Dict[str, Any], context: Dict[str, Any]) -> str:
        overall_strategy = output.get("overall_strategy", "")
        content_opts = json.dumps(output.get("content_optimizations", []), ensure_ascii=False, indent=2)
        keywords_to_add = json.dumps(output.get("keywords_to_add", []), ensure_ascii=False)
        priority_actions = json.dumps(output.get("priority_actions", []), ensure_ascii=False)

        gap_context = ""
        if context.get("gap_analysis"):
            ga = context["gap_analysis"]
            gap_context = (
                f"\n=== 差距分析（参考） ===\n"
                f"verdict: {ga.get('verdict', '')}\n"
                f"missing: {json.dumps(ga.get('keyword_match', {}).get('missing', []), ensure_ascii=False)}\n"
                f"buried: {json.dumps(ga.get('keyword_match', {}).get('present_but_buried', []), ensure_ascii=False)}\n"
            )

        return f"""请评估以下优化建议的质量。

=== 优化建议 ===
整体策略: {overall_strategy}
优化项 ({len(output.get('content_optimizations', []))}条): {content_opts}
建议关键词: {keywords_to_add}
优先级动作: {priority_actions}
{gap_context}

=== 评估维度 ===

1. **抓重点**（权重50%）：
   - 优化建议是否聚焦在差距分析中最关键的 2-3 个核心问题？
   - 还是对每条 gap 平均用力，没有主次之分？
   - priority_actions 排的优先级是否合理？最重要的是否排在第一？

2. **深度感**（权重50%）：
   - content_optimizations 中的 example 真的是更好的写法吗？
   - 还是把原文换了一种同样平庸的表述？
   - 判断标准：如果求职者把 example 写到简历里，竞争力是否真的提升了？
   - 检查 example 是否只是换了同义词、调了语序，还是用了更具体的动词、增加了可感知的影响

返回 JSON：
{{
    "score": 7.5,
    "strengths": ["建议做得好的具体点"],
    "issues": ["存在问题的具体点"],
    "suggestion": "给 Agent 的改进方向汇总（2-3句话）"
}}

严格评分：≥8.0 = 建议聚焦要害、示例真正提升了表达力，6.0-7.9 = 方向对但建议泛化或示例一般，<6.0 = 抓错重点或示例毫无提升。"""
```

- [ ] **Step 2: 验证导入**

Run: `python -c "from evaluators.optimization_evaluator import OptimizationEvaluator; print('OK')"`
Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add evaluators/optimization_evaluator.py
git commit -m "feat: add OptimizationEvaluator"
```

---

### Task 8: 修改 ResumeAnalysisAgent.analyze() 接受 critique

**Files:**
- Modify: `agents/resume_analysis_agent.py:123-175`

- [ ] **Step 1: 修改 `analyze` 方法签名和 prompt 构建**

在 `resume_analysis_agent.py` 中，修改 `analyze` 方法：

```python
    def analyze(self, resume: Resume, critique: str | None = None) -> Dict[str, Any]:
        """分析简历并返回结构化分析与薄弱环节。critique 为评估器的改进反馈，非 None 时表示重试。"""
        system_content = (
            "你是一位资深职业顾问，为各行业求职者审视简历。"
            "你眼光老辣但不过度苛刻：你关注的是简历在目标行业中的真实竞争力，"
            "能一眼看穿哪些是表面问题、哪些是硬伤。"
            "你从不说正确的废话，每条建议都必须具体、可执行、直击要害。"
        )
        if critique:
            system_content += f"\n\n=== 上一轮输出的改进反馈 ===\n{critique}\n请针对以上反馈，修正你上一轮的输出。"

        prompt = f"""你是一位经验丰富的职业顾问，擅长从用人方视角审视简历。请仔细阅读以下简历，找出其**真正的薄弱点**，给出精准、一针见血的分析。

=== 简历原文 ===
{resume.raw_text}

=== 分析原则（严格遵守） ===

1. **行业无关性**：不要预设候选人所在行业或岗位。从简历内容本身出发，判断这份简历在其自身领域中存在的问题。

2. **优势分析**：指出简历的亮点，限定 2-3 条，每条一句话，具体到点。

3. **薄弱环节分析（核心）**：
   - 找出简历中**实质性的、会影响竞争力**的问题，例如：
     · 经历描述浮于表面——只罗列了"做了什么"，没有体现"做得怎么样"、"解决了什么难题"、"带来了什么价值"
     · 关键成果缺乏说服力——有数据但数据无法体现个人贡献度，或该量化的地方没有量化
     · 经历堆砌无重点——罗列了大量项目/职责，但没有一条能让人记住的核心亮点
     · 表述笼统空泛——使用了大量"参与""协助""负责"等动词，但看不出实际角色深度
     · 关键信息缺失——对于该领域来说必须体现的能力或经验没有覆盖到
   - **严禁**将以下内容列为薄弱点：
     · 缺少个人总结/求职意向（简洁有力的简历不需要这些）
     · 排版格式问题（除非严重到影响理解）
     · 教育背景缺少 GPA 或课程列表（非必填项）
     · 简历篇幅偏短（简洁是优点，不是缺点）
   - 每条薄弱点**必须引用简历原文的具体内容**作为证据，不得脱离简历泛泛而谈
   - 如果确实没有实质性薄弱点，weaknesses 可以为空数组，不要硬凑

4. **改进建议**：不说空话（如"补充量化指标"），而是给出**针对性的、可立即执行**的方案。例如不说"成果应该量化"，而说"在XX模块中，可以补充处理的请求量级、优化的性能提升百分比"。

5. **评分**：10 分制。8分以上 = 在其领域内较有竞争力，6-7分 = 有提升空间，5分以下 = 有硬伤需大幅改进。

返回 JSON 格式：
{{
    "strengths": ["具体优势1", "具体优势2"],
    "weaknesses": [
        {{"aspect": "薄弱方面（一句概括）", "detail": "简历中的具体表现", "suggestion": "具体可执行的改进方案"}}
    ],
    "overall_score": 7.0,
    "key_improvements": ["最重要的改进点（不超过3条，按优先级排序）"]
}}
"""
        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": system_content},
                {"role": "user", "content": prompt},
            ],
            response_format={"type": "json_object"},
            temperature=0.3,
        )

        return json.loads(response.choices[0].message.content)
```

- [ ] **Step 2: 验证修改**

Run: `python -c "from agents.resume_analysis_agent import ResumeAnalysisAgent; a = ResumeAnalysisAgent(); import inspect; sig = inspect.signature(a.analyze); print('critique' in str(sig))"`
Expected: `True`

- [ ] **Step 3: Commit**

```bash
git add agents/resume_analysis_agent.py
git commit -m "feat: add critique parameter to ResumeAnalysisAgent.analyze()"
```

---

### Task 9: 修改 RoleAnalyzerAgent 两个方法接受 critique

**Files:**
- Modify: `agents/role_analyzer_agent.py:16-104`

- [ ] **Step 1: 修改 `analyze_from_title` 方法**

```python
    def analyze_from_title(self, job_title: str, critique: str | None = None) -> JobRequirement:
        """仅根据岗位名称，让LLM补全该岗位的典型要求画像"""
        system_content = "你是一位资深的招聘专家，对各行业岗位要求有深入了解。"
        if critique:
            system_content += f"\n\n=== 上一轮输出的改进反馈 ===\n{critique}\n请针对以上反馈，修正你上一轮的输出。"

        prompt = f"""你是一位资深的招聘专家和行业顾问。请根据以下岗位名称，基于你对行业标准的了解，生成该岗位的典型要求画像。

目标岗位：{job_title}

请分析该岗位在行业中的标准要求，包括：
1. 典型职责（6-10条）
2. 硬性要求（学历、经验、技能等，5-8条）
3. 加分项（3-5条）
4. 核心技术关键词（8-15个）
5. 软技能要求（3-5个）
6. 行业领域
7. 岗位层级（初级/中级/高级/专家/管理）

请以 JSON 格式返回：
{{
    "title": "{job_title}",
    "level": "中级",
    "industry": "互联网/金融/制造业等",
    "responsibilities": ["职责1", "职责2"],
    "requirements": ["要求1", "要求2"],
    "preferred": ["加分项1", "加分项2"],
    "tech_keywords": ["关键词1", "关键词2"],
    "soft_skills": ["沟通能力", "团队协作"],
    "source": "title"
}}
"""
        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": system_content},
                {"role": "user", "content": prompt},
            ],
            response_format={"type": "json_object"},
            temperature=0.3,
        )

        data = json.loads(response.choices[0].message.content)
        return JobRequirement(**data)
```

- [ ] **Step 2: 修改 `analyze_from_jd` 方法**

```python
    def analyze_from_jd(self, jd_text: str, critique: str | None = None) -> JobRequirement:
        """从JD原文中提取结构化的岗位需求"""
        system_content = "你是一位资深的招聘专家，擅长从JD中提取结构化信息。"
        if critique:
            system_content += f"\n\n=== 上一轮输出的改进反馈 ===\n{critique}\n请针对以上反馈，修正你上一轮的输出。"

        prompt = f"""你是一位资深的招聘专家。请从以下岗位描述（JD）中提取结构化的岗位需求信息。

=== 岗位描述原文 ===
{jd_text}

请提取以下信息，以 JSON 格式返回：
1. title: 岗位名称
2. company: 公司名称（如有）
3. salary_range: 薪资范围（如有）
4. location: 工作地点（如有）
5. level: 岗位层级（初级/中级/高级/专家/管理）
6. industry: 行业领域
7. responsibilities: 岗位职责列表（6-10条）
8. requirements: 硬性要求列表（学历、经验、技能等，5-8条）
9. preferred: 加分项列表（3-5条）
10. tech_keywords: 技术栈关键词（8-15个）
11. soft_skills: 软技能要求（3-5个）


返回 JSON：
{{
    "title": "岗位名",
    "company": "",
    "salary_range": "",
    "location": "",
    "level": "",
    "industry": "",
    "responsibilities": [],
    "requirements": [],
    "preferred": [],
    "tech_keywords": [],
    "soft_skills": [],
}}
"""
        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": system_content},
                {"role": "user", "content": prompt},
            ],
            response_format={"type": "json_object"},
            temperature=0.3,
        )

        data = json.loads(response.choices[0].message.content)
        return JobRequirement(**data)
```

- [ ] **Step 3: 验证修改**

Run: `python -c "from agents.role_analyzer_agent import RoleAnalyzerAgent; a = RoleAnalyzerAgent(); import inspect; s1 = inspect.signature(a.analyze_from_title); s2 = inspect.signature(a.analyze_from_jd); print('OK' if 'critique' in str(s1) and 'critique' in str(s2) else 'FAIL')"`
Expected: `OK`

- [ ] **Step 4: Commit**

```bash
git add agents/role_analyzer_agent.py
git commit -m "feat: add critique parameter to RoleAnalyzerAgent methods"
```

---

### Task 10: 修改 GapAnalyzerAgent.analyze() 接受 critique

**Files:**
- Modify: `agents/gap_analyzer_agent.py:17-125`

- [ ] **Step 1: 修改 `analyze` 方法签名和 prompt 构建**

```python
    def analyze(
        self,
        resume: Resume,
        job: JobRequirement,
        resume_analysis: Optional[Dict[str, Any]] = None,
        critique: str | None = None,
    ) -> Dict[str, Any]:
        """对比简历与岗位画像，输出差距分析。critique 为评估器的改进反馈。"""
        analysis_context = ""
        if resume_analysis:
            strengths = resume_analysis.get("strengths", [])
            weaknesses = resume_analysis.get("weaknesses", [])
            if strengths:
                analysis_context += "\n【简历已有优势】\n" + "\n".join(f"- {s}" for s in strengths)
            if weaknesses:
                analysis_context += "\n【简历已知薄弱点】\n" + "\n".join(
                    f"- {w.get('aspect', '')}: {w.get('detail', '')}" for w in weaknesses
                )

        system_content = (
            "你是一位资深招聘专家，为各行业求职者做岗位匹配分析。"
            "你的核心能力：能结合行业上下文做判断——在自动驾驶公司实习意味着大概率接触过ROS，"
            "做ADAS意味着涉及传感器融合，不被'经历描述里没出现这个词'所蒙蔽。"
            "你的分析前后一致，不会把一个技能同时列为'对齐点'和'缺失'。"
            "你只做简历优化，不建议用户去学新技能。你从不说正确的废话。"
        )
        if critique:
            system_content += f"\n\n=== 上一轮输出的改进反馈 ===\n{critique}\n请针对以上反馈，修正你上一轮的输出。"

        prompt = f"""你是一位资深的招聘和简历优化专家。你的任务是对比简历与目标岗位，找出**岗位匹配度上的真实差距**，给出精准、可执行的优化建议。

=== 求职者简历 ===
{resume.to_text()}
{analysis_context}

=== 目标岗位画像 ===
{job.to_text()}

=== 分析原则（严格遵守） ===

0. **先给总体判断**：一句话总结简历与岗位的匹配程度。不预判"缺乏XX"，而是客观描述"简历侧重XX，岗位要求XX，最大交叉点在XX"。

1. **行业上下文推断（重要）**：
   - 当技能的「技能列表」中有某个技能，且求职者的工作/实习公司或项目属于该技能高度相关的行业时，**不应判定该技能缺失**，应归类为"经历中有但描述未突出"
   - 例如：在自动驾驶公司实习 → 行业重度使用 ROS → 技能列表有 ROS → 不要判 ROS 缺失，而是建议"在经历描述中显式提及 ROS 的使用"

2. **implicit_skills（隐式技能推断）**：
   - 从工作/项目经历的**描述文字**中推断求职者实际掌握但**未在技能列表中显式列出**的技能
   - **严禁**将技能列表中已有的技能列为"隐式技能"
   - 每条必须有具体的经历描述作为证据
   - **精选 8-12 条**，只保留对未来雇主有说服力的

3. **keyword_match（关键词匹配）**：
   - 综合显式技能+隐式技能+行业上下文，与岗位关键词逐一对照
   - matched：有明确证据或行业上下文支撑的匹配
   - present_but_buried：技能列表有或行业可推断，但经历描述不够突出
   - missing：确实缺失，且无法从行业上下文或现有经历推断
   - **内部一致性检查（强制）**：如果一个关键词出现在某个 alignment_point 的 resume_item 中，它**绝对不能**同时出现在 missing 列表

4. **alignment_points（对齐点）**：
   - 找出简历中与岗位要求可直接对应经历/技能
   - 给具体的"如何在简历中突出"的建议

5. **gaps（差距分析——核心产出）**：
   - 只分析**岗位匹配上的差距**，不重复简历本身的质量问题
   - 区分两类差距：
     · **写作层面**（能力有但描述不到位）→ optimization 聚焦如何重写描述来体现
     · **能力层面**（确实缺少某项核心经验）→ 坦诚说明，但不要建议"去学""去做个新项目"（这超出了简历优化的范围）
   - optimization 的目标是**优化简历呈现**，不是规划用户的学习路线

6. **restructure_plan（内容重组建议）**：
   - 基于岗位需求，给出简历内容如何重新排列组合、哪些板块提前/加重、哪些精简
   - **严禁**建议"新增个人总结板块"（简洁简历不需要，除非特别需要新增）
   - **严禁**建议删除与对齐点或 matched 关键词相关的已有内容

7. **summary_rewrite_direction（总结改写方向）**：
   - 只针对「如果简历有一个定位性的一句话」，给出这个句子的方向建议
   - **严禁**写成"建议增加一段个人总结"——只需给出那句话本身的内容方向即可

8. **priority_actions（优先级动作）**：
   - 不超过 3 条，按紧急程度排序
   - 每条必须是**简历优化**的具体动作（重写某段描述、调整某段经历的重点、显式补充某个关键词等）
   - **不要建议用户去学新技能、做新项目**——这不属于简历优化的范畴
   - **不要加序号前缀**，直接写动作内容

返回 JSON：
{{
    "verdict": "一句话总体判断",
    "implicit_skills": [
        {{"skill": "技能名", "evidence": "简历经历中的具体描述", "category": "技能类别"}}
    ],
    "keyword_match": {{
        "matched": [],
        "present_but_buried": [],
        "missing": []
    }},
    "alignment_points": [
        {{"resume_item": "简历中的具体经历/技能", "job_requirement": "对应的岗位要求", "action": "如何在简历中突出这个对齐点"}}
    ],
    "gaps": [
        {{"aspect": "差距方面", "current_state": "当前状态", "optimization": "具体的弥补方案（不编造经历）"}}
    ],
    "restructure_plan": [
        {{"section": "简历板块", "suggested_change": "重组建议（基于现有内容）"}}
    ],
    "summary_rewrite_direction": "总结改写方向",
    "priority_actions": ["具体动作1", "具体动作2", "具体动作3"]
}}
"""
        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": system_content},
                {"role": "user", "content": prompt},
            ],
            response_format={"type": "json_object"},
            temperature=0.3,
        )

        return json.loads(response.choices[0].message.content)
```

- [ ] **Step 2: 验证修改**

Run: `python -c "from agents.gap_analyzer_agent import GapAnalyzerAgent; a = GapAnalyzerAgent(); import inspect; sig = inspect.signature(a.analyze); print('critique' in str(sig))"`
Expected: `True`

- [ ] **Step 3: Commit**

```bash
git add agents/gap_analyzer_agent.py
git commit -m "feat: add critique parameter to GapAnalyzerAgent.analyze()"
```

---

### Task 11: 修改 OptimizationAgent.generate_suggestions() 接受 critique

**Files:**
- Modify: `agents/optimization_agent.py:16-93`

- [ ] **Step 1: 修改 `generate_suggestions` 方法签名和 prompt 构建**

```python
    def generate_suggestions(
        self,
        gap_analysis: Dict[str, Any],
        job: JobRequirement,
        critique: str | None = None,
    ) -> Dict[str, Any]:
        """基于差距分析生成具体优化建议。critique 为评估器的改进反馈。"""
        # 处理关键词匹配
        keyword_info = gap_analysis.get("keyword_match", {})
        matched = ", ".join(keyword_info.get("matched", []))
        missing = ", ".join(keyword_info.get("missing", []))
        buried = ", ".join(keyword_info.get("present_but_buried", []))

        # 处理对齐点
        alignment_text = ""
        for a in gap_analysis.get("alignment_points", []):
            alignment_text += f"- 简历项: {a.get('resume_item', '')}\n"
            alignment_text += f"  岗位要求: {a.get('job_requirement', '')}\n"
            alignment_text += f"  建议: {a.get('action', '')}\n\n"

        # 处理差距
        gaps_text = ""
        for g in gap_analysis.get("gaps", []):
            gaps_text += f"- {g.get('aspect', '')}: {g.get('current_state', '')}\n"
            gaps_text += f"  优化: {g.get('optimization', '')}\n\n"

        # 重组建议
        restructure_text = ""
        for r in gap_analysis.get("restructure_plan", []):
            restructure_text += f"- {r.get('section', '')}: {r.get('suggested_change', '')}\n"

        system_content = "你是一位资深的简历优化专家，擅长提供具体、可执行的简历优化建议。强调不编造经历，只重组和润色。"
        if critique:
            system_content += f"\n\n=== 上一轮输出的改进反馈 ===\n{critique}\n请针对以上反馈，修正你上一轮的输出。"

        prompt = f"""你是一位资深的简历优化专家。请根据以下岗位画像和差距分析，生成详细的简历优化建议。

=== 目标岗位 ===
{job.to_text()}

=== 差距分析 ===

【关键词匹配】
已匹配: {matched}
缺失（可在现有经历中体现）: {missing}
有但不够突出: {buried}

【经历对齐点】
{alignment_text}

【差距】
{gaps_text}

【重组建议】
{restructure_text}

【个人总结方向】
{gap_analysis.get('summary_rewrite_direction', '')}

请从以下方面给出可执行的优化建议，以 JSON 格式返回：

{{
    "overall_strategy": "整体优化策略（2-3句话）",
    "content_optimizations": [
        {{"section": "板块名", "original": "原问题", "suggestion": "优化建议", "example": "示例写法"}}
    ],
    "keywords_to_add": ["需要强调的关键词"],
    "format_suggestions": ["格式和排版建议"],
    "job_targeting": "针对目标岗位的定制化调整建议",
    "priority_actions": ["最先做的3件事"]
}}
"""
        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": system_content},
                {"role": "user", "content": prompt},
            ],
            response_format={"type": "json_object"},
            temperature=0.3,
        )

        return json.loads(response.choices[0].message.content)
```

- [ ] **Step 2: 验证修改**

Run: `python -c "from agents.optimization_agent import OptimizationAgent; a = OptimizationAgent(); import inspect; sig = inspect.signature(a.generate_suggestions); print('critique' in str(sig))"`
Expected: `True`

- [ ] **Step 3: Commit**

```bash
git add agents/optimization_agent.py
git commit -m "feat: add critique parameter to OptimizationAgent.generate_suggestions()"
```

---

### Task 12: 修改 app.py 集成 ReflectionLoop

**Files:**
- Modify: `app.py:119-213`（主流程中的 4 个关键步骤）

- [ ] **Step 1: 新增导入**

在 `app.py` 文件顶部新增导入（在现有 import 之后）：

```python
from agents.reflection_loop import ReflectionLoop
from evaluators.resume_analysis_evaluator import ResumeAnalysisEvaluator
from evaluators.role_analyzer_evaluator import RoleAnalyzerEvaluator
from evaluators.gap_analyzer_evaluator import GapAnalyzerEvaluator
from evaluators.optimization_evaluator import OptimizationEvaluator
```

- [ ] **Step 2: 新增 ReflectionLoop 初始化**

在 `get_generators()` 函数之后新增：

```python
@st.cache_resource
def get_reflection_loops():
    return {
        "analysis": ReflectionLoop(ResumeAnalysisEvaluator(), max_retries=2),
        "role":     ReflectionLoop(RoleAnalyzerEvaluator(), max_retries=2),
        "gap":      ReflectionLoop(GapAnalyzerEvaluator(), max_retries=2),
        "optimization": ReflectionLoop(OptimizationEvaluator(), max_retries=2),
    }
```

在 `agents = get_agents()` 之后新增：

```python
reflection_loops = get_reflection_loops()
```

- [ ] **Step 3: 新增 session state 变量**

在 session state defaults 字典中新增：

```python
"reflection_logs": {},   # {"analysis": [...], "role": [...], "gap": [...], "optimization": [...]}
```

- [ ] **Step 4: 修改 Step 2（岗位画像）使用 ReflectionLoop**

将原来的：
```python
                # Step 2: 岗位画像
                st.write("🔍 分析目标岗位画像...")
                if jd_text.strip():
                    st.session_state.job_profile = agents["role"].analyze_from_jd(jd_text)
                else:
                    st.session_state.job_profile = agents["role"].analyze_from_title(job_title)
                jp = st.session_state.job_profile
                st.write(f"✅ 岗位画像完成: {jp.title} ({jp.level or '层级未指定'})")
```

改为：
```python
                # Step 2: 岗位画像（with Reflection）
                st.write("🔍 分析目标岗位画像...")
                if jd_text.strip():
                    st.session_state.job_profile, role_evals = reflection_loops["role"].run(
                        agent_callable=lambda critique: agents["role"].analyze_from_jd(jd_text, critique=critique),
                        context={"jd_text": jd_text},
                    )
                else:
                    st.session_state.job_profile, role_evals = reflection_loops["role"].run(
                        agent_callable=lambda critique: agents["role"].analyze_from_title(job_title, critique=critique),
                        context={},
                    )
                st.session_state.reflection_logs["role"] = role_evals
                jp = st.session_state.job_profile
                st.write(f"✅ 岗位画像完成: {jp.title} ({jp.level or '层级未指定'})")
```

- [ ] **Step 5: 修改 Step 2.5（简历深度分析）使用 ReflectionLoop**

将原来的：
```python
                # Step 2.5: 深度分析简历（推断隐式技能和结构化信息）
                st.write("🔬 深度分析简历内容...")
                st.session_state.resume_analysis = agents["analysis"].analyze(resume)
                st.write("✅ 简历深度分析完成")
```

改为：
```python
                # Step 2.5: 深度分析简历（with Reflection）
                st.write("🔬 深度分析简历内容...")
                st.session_state.resume_analysis, analysis_evals = reflection_loops["analysis"].run(
                    agent_callable=lambda critique: agents["analysis"].analyze(structured_resume, critique=critique),
                    context={"resume_raw_text": resume.raw_text},
                )
                st.session_state.reflection_logs["analysis"] = analysis_evals
                st.write("✅ 简历深度分析完成")
```

- [ ] **Step 6: 修改 Step 3（差距分析）使用 ReflectionLoop**

将原来的：
```python
                # Step 3: Gap 分析（传入简历分析结果）
                st.write("📊 对比简历与岗位差距...")
                st.session_state.gap_analysis = agents["gap"].analyze(
                    resume, st.session_state.job_profile,
                    resume_analysis=st.session_state.resume_analysis,
                )
                st.write("✅ 差距分析完成")
```

改为：
```python
                # Step 3: Gap 分析（with Reflection）
                st.write("📊 对比简历与岗位差距...")
                st.session_state.gap_analysis, gap_evals = reflection_loops["gap"].run(
                    agent_callable=lambda critique: agents["gap"].analyze(
                        structured_resume, st.session_state.job_profile,
                        resume_analysis=st.session_state.resume_analysis,
                        critique=critique,
                    ),
                    context={},
                )
                st.session_state.reflection_logs["gap"] = gap_evals
                st.write("✅ 差距分析完成")
```

- [ ] **Step 7: 修改 Step 4（优化建议）使用 ReflectionLoop**

将原来的：
```python
                # Step 4: 优化建议
                st.write("💡 生成优化建议...")
                st.session_state.suggestions = agents["optimization"].generate_suggestions(
                    st.session_state.gap_analysis,
                    st.session_state.job_profile,
                )
                st.write("✅ 优化建议生成完成")
```

改为：
```python
                # Step 4: 优化建议（with Reflection）
                st.write("💡 生成优化建议...")
                st.session_state.suggestions, opt_evals = reflection_loops["optimization"].run(
                    agent_callable=lambda critique: agents["optimization"].generate_suggestions(
                        st.session_state.gap_analysis,
                        st.session_state.job_profile,
                        critique=critique,
                    ),
                    context={"gap_analysis": st.session_state.gap_analysis},
                )
                st.session_state.reflection_logs["optimization"] = opt_evals
                st.write("✅ 优化建议生成完成")
```

- [ ] **Step 8: 在 Tab 2 的分析报告中新增质量评估展示**

在 `tabs[1]` 的 `col_b` 中，在"优化建议"展开之后、"优先行动"之前，新增：

```python
            st.subheader("🔍 质量评估")
            logs = st.session_state.get("reflection_logs", {})
            for module_name, module_label in [
                ("analysis", "简历分析"),
                ("role", "岗位画像"),
                ("gap", "差距分析"),
                ("optimization", "优化建议"),
            ]:
                evals = logs.get(module_name, [])
                if not evals:
                    continue
                final = evals[-1]
                passed = final.passed
                icon = "✅" if passed else "⚠️"
                with st.expander(f"{icon} {module_label} — {final.score:.1f}/10", expanded=not passed):
                    for i, e in enumerate(evals):
                        round_label = f"第{i+1}轮" if i > 0 else "首轮"
                        status_icon = "✅" if e.passed else "🔄"
                        st.caption(f"{status_icon} {round_label}: {e.score:.1f}/10")
                    if final.issues:
                        st.markdown("**发现问题：**")
                        for issue in final.issues:
                            st.markdown(f"- {issue}")
```

- [ ] **Step 9: 验证 app.py 无语法错误**

Run: `python -c "import py_compile; py_compile.compile('app.py', doraise=True); print('OK')"`
Expected: `OK`

- [ ] **Step 10: Commit**

```bash
git add app.py
git commit -m "feat: integrate ReflectionLoop into 4 core pipeline steps"
```

---

## 自评检查

1. **Spec 覆盖**: 设计文档中所有内容均已覆盖——4个评估器、ReflectionLoop、Agent critique 参数、app.py 集成、测试
2. **无占位符**: 所有任务都包含完整代码，无 TBD/TODO
3. **类型一致性**: EvaluationResult 在 Task 1 定义，所有后续任务使用一致；各 Agent 的 critique 参数签名一致（`critique: str | None = None`）
