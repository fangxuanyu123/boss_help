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
