"""Reflection 循环引擎 —— 调用 Agent → 评估 → 反馈 → 重试"""
import logging
from typing import Callable, Dict, Any, Tuple, List
from evaluators.base_evaluator import BaseEvaluator, EvaluationResult

logger = logging.getLogger(__name__)


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
            (final_output, evaluation_history) —— 返回通过轮次的输出，
            若全部未通过则返回最高分轮次的输出。
        """
        evaluations: List[EvaluationResult] = []
        output = agent_callable(None)
        best_output = output
        best_score = -1.0

        for attempt in range(self.max_retries + 1):
            output_dict = self._to_dict(output)

            result = self.evaluator.evaluate(output_dict, context)
            evaluations.append(result)

            if result.score > best_score:
                best_score = result.score
                best_output = output

            if result.passed:
                logger.debug("Reflection passed on attempt %d (score: %.1f)", attempt + 1, result.score)
                return output, evaluations

            if attempt < self.max_retries:
                logger.debug("Reflection retry %d/%d (score: %.1f, threshold: %.1f)", attempt + 1, self.max_retries, result.score, result.threshold)
                critique = self._build_critique(result)
                output = agent_callable(critique)

        logger.debug("Reflection exhausted all retries, returning best score (%.1f)", best_score)
        return best_output, evaluations

    def _to_dict(self, output: Any) -> Dict[str, Any]:
        """将 Agent 输出转为 dict。JobRequirement 等 Pydantic 模型需转换。"""
        if hasattr(output, "model_dump"):
            return output.model_dump()
        if isinstance(output, dict):
            return output
        logger.warning("ReflectionLoop: unexpected output type %s, wrapping as string", type(output).__name__)
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
                parts.append(f"  [PASS] {s}")
        if result.issues:
            parts.append("需要改进的地方：")
            for i in result.issues:
                parts.append(f"  [ISSUE] {i}")
        if result.suggestion:
            parts.append(f"改进方向：{result.suggestion}")
        parts.append("请在重新生成时针对以上反馈修正输出。")
        return "\n".join(parts)
