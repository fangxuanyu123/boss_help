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
