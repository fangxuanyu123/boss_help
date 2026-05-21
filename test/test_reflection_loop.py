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
    """首轮通过 -> 返回结果，仅1轮评估"""
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
    assert len(calls) == 1
    assert calls[0] is None


def test_retries_and_passes_on_second_try():
    """首轮5.0未通过 -> 注入critique重试 -> 第二轮8.0通过"""
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
    assert "5.0" in calls[1]


def test_exhausts_all_retries():
    """三轮都不通过 -> 取最高分的输出"""
    evaluator = MockEvaluator(scores=[4.0, 5.5, 5.0])
    loop = ReflectionLoop(evaluator, max_retries=2)

    calls = []
    def agent(critique=None):
        calls.append(critique)
        return {"result": f"attempt_{len(calls)}"}

    output, evals = loop.run(agent, context={})

    assert len(evals) == 3
    assert evals[2].passed is False
    assert output == {"result": "attempt_2"}  # 第二轮得分最高 (5.5)
    assert len(calls) == 3


def test_passes_on_second_after_borderline_first():
    """首轮5.9（未达到6分threshold）-> 重试后通过"""
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
    """max_retries=0 -> 不重试"""
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
