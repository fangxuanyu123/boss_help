"""优化建议 Agent - 结合分析结果和 RAG 检索生成具体优化建议"""
from typing import Dict, Any, List
from openai import OpenAI
from config import LLM_API_KEY, LLM_BASE_URL, LLM_MODEL_NAME


class OptimizationAgent:
    """简历优化建议智能体"""

    def __init__(self):
        self.client = OpenAI(api_key=LLM_API_KEY, base_url=LLM_BASE_URL)
        self.model = LLM_MODEL_NAME

    def generate_suggestions(
        self,
        analysis: Dict[str, Any],
        rag_references: str,
        job_intent: str = "",
    ) -> Dict[str, Any]:
        """生成具体优化建议"""
        weaknesses_text = ""
        for w in analysis.get("weaknesses", []):
            weaknesses_text += f"- {w.get('aspect', '')}: {w.get('detail', '')}\n  建议: {w.get('suggestion', '')}\n"

        prompt = f"""你是一位资深的简历优化专家。请根据以下信息生成详细的简历优化建议。

=== 求职意向 ===
{job_intent or "未提供"}

=== 当前简历分析（薄弱环节） ===
{weaknesses_text}

=== 优秀简历参考（RAG 检索结果） ===
{rag_references}

请从以下几个方面给出优化建议，并以 JSON 格式返回：

1. **整体策略**: 简历调整的整体方向和策略
2. **内容优化**: 逐项具体优化建议（工作经历、项目、技能等）
3. **关键词优化**: 建议添加的行业关键词和术语
4. **排版格式**: 格式和排版建议
5. **针对性调整**: 针对求职意向量身定制的建议

返回 JSON 格式：
{{
    "overall_strategy": "整体策略描述",
    "content_optimizations": [
        {{"section": "工作经历/项目/技能等", "original": "原始问题", "suggestion": "优化建议", "example": "示例写法"}}
    ],
    "keywords": ["关键词1", "关键词2"],
    "format_suggestions": ["建议1", "建议2"],
    "job_targeting": "针对性调整建议",
    "priority_actions": ["最重要的3个行动项"]
}}
"""

        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": "你是一位资深的简历优化专家，擅长提供具体、可执行的简历优化建议。"},
                {"role": "user", "content": prompt},
            ],
            response_format={"type": "json_object"},
            temperature=0.3,
        )

        import json
        result = json.loads(response.choices[0].message.content)
        return result
