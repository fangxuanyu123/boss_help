"""优化建议 Agent - 结合岗位画像和差距分析生成具体优化建议"""
from typing import Dict, Any
import json
from openai import OpenAI
from config import LLM_API_KEY, LLM_BASE_URL, LLM_MODEL_NAME
from models.job import JobRequirement


class OptimizationAgent:
    """简历优化建议智能体——基于岗位画像和差距分析驱动"""

    def __init__(self):
        self.client = OpenAI(api_key=LLM_API_KEY, base_url=LLM_BASE_URL)
        self.model = LLM_MODEL_NAME

    def generate_suggestions(
        self,
        gap_analysis: Dict[str, Any],
        job: JobRequirement,
    ) -> Dict[str, Any]:
        """基于差距分析生成具体优化建议"""
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
                {"role": "system", "content": "你是一位资深的简历优化专家，擅长提供具体、可执行的简历优化建议。强调不编造经历，只重组和润色。"},
                {"role": "user", "content": prompt},
            ],
            response_format={"type": "json_object"},
            temperature=0.3,
        )

        return json.loads(response.choices[0].message.content)
