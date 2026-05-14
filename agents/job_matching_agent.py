"""岗位匹配 Agent - 分析简历与岗位的匹配度，给出针对性调整意见"""
from typing import Dict, Any
import json
from openai import OpenAI
from config import LLM_API_KEY, LLM_BASE_URL, LLM_MODEL_NAME
from models.resume import Resume
from models.job import JobRequirement


class JobMatchingAgent:
    """岗位匹配智能体"""

    def __init__(self):
        self.client = OpenAI(api_key=LLM_API_KEY, base_url=LLM_BASE_URL)
        self.model = LLM_MODEL_NAME

    def match(self, resume: Resume, job: JobRequirement) -> Dict[str, Any]:
        """分析简历与岗位的匹配度"""
        prompt = f"""你是一位资深的招聘专家。请分析以下简历与岗位的匹配情况。

=== 简历 ===
{resume.to_text()}

=== 岗位需求 ===
{job.to_text()}

请从以下维度分析，以 JSON 格式返回：

1. **match_score**: 匹配度评分 (0-100)
2. **match_strengths**: 简历中与岗位高度匹配的方面
3. **match_gaps**: 简历与岗位要求有差距的方面（带建议）
4. **specific_actions**: 提升匹配度的具体行动
5. **keyword_match**: 关键词匹配情况
6. **summary**: 整体匹配总结

返回 JSON：
{{
    "match_score": 75,
    "match_strengths": ["优势1", "优势2"],
    "match_gaps": [
        {{"requirement": "岗位要求", "current_status": "当前状态", "suggestion": "改进建议"}}
    ],
    "specific_actions": ["具体行动1", "具体行动2"],
    "keyword_match": {{
        "matched": ["匹配的关键词"],
        "missing": ["缺失的关键词"]
    }},
    "summary": "整体匹配总结"
}}
"""
        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": "你是一位资深的招聘专家，擅长分析简历与岗位的匹配度。"},
                {"role": "user", "content": prompt},
            ],
            response_format={"type": "json_object"},
            temperature=0.3,
        )

        return json.loads(response.choices[0].message.content)
