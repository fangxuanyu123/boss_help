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
