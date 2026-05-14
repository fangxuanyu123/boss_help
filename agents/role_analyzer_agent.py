"""岗位画像分析 Agent - 输入岗位名或JD原文，输出标准化的岗位需求画像"""
from typing import Dict, Any, Optional
import json
from openai import OpenAI
from config import LLM_API_KEY, LLM_BASE_URL, LLM_MODEL_NAME
from models.job import JobRequirement


class RoleAnalyzerAgent:
    """岗位画像分析智能体——统一处理岗位名和JD两种输入"""

    def __init__(self):
        self.client = OpenAI(api_key=LLM_API_KEY, base_url=LLM_BASE_URL)
        self.model = LLM_MODEL_NAME

    def analyze_from_title(self, job_title: str) -> JobRequirement:
        """仅根据岗位名称，让LLM补全该岗位的典型要求画像"""
        prompt = f"""你是一位资深的招聘专家和行业顾问。请根据以下岗位名称，基于你对行业标准的了解，生成该岗位的典型要求画像。

目标岗位：{job_title}

请分析该岗位在行业中的标准要求，包括：
1. 典型职责（6-10条）
2. 硬性要求（学历、经验、技能等，5-8条）
3. 加分项（3-5条）
4. 核心技术关键词（8-15个）
5. 软技能要求（3-5个）
6. 行业领域
7. 岗位层级（初级/中级/高级/专家/管理）

请以 JSON 格式返回：
{{
    "title": "{job_title}",
    "level": "中级",
    "industry": "互联网/金融/制造业等",
    "responsibilities": ["职责1", "职责2"],
    "requirements": ["要求1", "要求2"],
    "preferred": ["加分项1", "加分项2"],
    "tech_keywords": ["关键词1", "关键词2"],
    "soft_skills": ["沟通能力", "团队协作"],
    "source": "title"
}}
"""
        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": "你是一位资深的招聘专家，对各行业岗位要求有深入了解。"},
                {"role": "user", "content": prompt},
            ],
            response_format={"type": "json_object"},
            temperature=0.3,
        )

        data = json.loads(response.choices[0].message.content)
        return JobRequirement(**data)

    def analyze_from_jd(self, jd_text: str) -> JobRequirement:
        """从JD原文中提取结构化的岗位需求"""
        prompt = f"""你是一位资深的招聘专家。请从以下岗位描述（JD）中提取结构化的岗位需求信息。

=== 岗位描述原文 ===
{jd_text}

请提取以下信息，以 JSON 格式返回：
1. title: 岗位名称
2. company: 公司名称（如有）
3. salary_range: 薪资范围（如有）
4. location: 工作地点（如有）
5. level: 岗位层级（初级/中级/高级/专家/管理）
6. industry: 行业领域
7. responsibilities: 岗位职责列表（6-10条）
8. requirements: 硬性要求列表（学历、经验、技能等，5-8条）
9. preferred: 加分项列表（3-5条）
10. tech_keywords: 技术栈关键词（8-15个）
11. soft_skills: 软技能要求（3-5个）
12. description: 保留JD原文
13. source: 固定为 "jd"

返回 JSON：
{{
    "title": "岗位名",
    "company": "",
    "salary_range": "",
    "location": "",
    "level": "",
    "industry": "",
    "responsibilities": [],
    "requirements": [],
    "preferred": [],
    "tech_keywords": [],
    "soft_skills": [],
    "description": "{jd_text[:200]}...",
    "source": "jd"
}}
"""
        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": "你是一位资深的招聘专家，擅长从JD中提取结构化信息。"},
                {"role": "user", "content": prompt},
            ],
            response_format={"type": "json_object"},
            temperature=0.3,
        )

        data = json.loads(response.choices[0].message.content)
        return JobRequirement(**data)
