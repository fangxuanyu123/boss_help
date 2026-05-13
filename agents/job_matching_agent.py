"""岗位匹配 Agent - 分析岗位 JD 与简历匹配度，给出针对性调整意见"""
from typing import Dict, Any
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

请从以下维度分析，并以 JSON 格式返回：
1. **匹配度评分** (0-100)
2. **匹配优势**: 简历中与岗位高度匹配的方面
3. **匹配 gap**: 简历中与岗位要求有差距的方面
4. **针对性建议**: 为提升匹配度应如何调整简历
5. **关键词匹配**: 岗位 JD 中的关键词在简历中出现/缺失的情况

返回 JSON:
{{
    "match_score": 75,
    "match_strengths": ["优势1", "优势2"],
    "match_gaps": [
        {{"requirement": "具体需求", "current_status": "当前情况", "suggestion": "改进建议"}}
    ],
    "specific_actions": ["具体行动1", "具体行动2"],
    "keyword_match": {{
        "matched": ["关键词1"],
        "missing": ["关键词2"]
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

        import json
        result = json.loads(response.choices[0].message.content)
        return result
