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
