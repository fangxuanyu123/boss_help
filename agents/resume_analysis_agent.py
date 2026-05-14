"""简历分析 Agent - 分析用户简历，提取结构化信息，识别薄弱环节"""
from typing import Dict, Any
import json
from openai import OpenAI
from config import LLM_API_KEY, LLM_BASE_URL, LLM_MODEL_NAME
from models.resume import Resume, WorkExperience, Project, Skill, Education


class ResumeAnalysisAgent:
    """简历分析智能体"""

    def __init__(self):
        self.client = OpenAI(api_key=LLM_API_KEY, base_url=LLM_BASE_URL)
        self.model = LLM_MODEL_NAME

    def extract_structured_resume(self, raw_text: str, job_title: str = "") -> Resume:
        """从原始简历文本中提取完整的结构化 Resume 对象

        这是 pipeline 的关键第一步 —— 只有先从 PDF 文本中提取出结构化字段，
        后续的 gap 分析、优化建议、简历生成才有可靠的原始数据基础。
        """
        prompt = f"""你是一位资深的简历解析专家。请从以下简历原文中提取所有信息，返回完整的结构化 JSON。

=== 简历原文 ===
{raw_text}

=== 提取规则（严格遵循） ===
1. **只提取原文中存在的字段**：如果原文没有提到某项，就留空或用空数组，绝不编造
2. **经历条目完整提取**：工作经历和项目经历中的每一条 responsibilities/achievements/highlights 都要提取
3. **技能归类**：将原文中的技能按类别整理（编程语言、框架、数据库、工具、系统、其他等）
4. **日期保持原样**：不要修改或格式化日期

返回 JSON 格式：
{{
    "name": "姓名",
    "phone": "手机号（原文有则填）",
    "email": "邮箱（原文有则填）",
    "title": "求职意向（原文有则填，否则空）",
    "summary": "个人总结（原文有则填，否则空）",
    "education": [
        {{"school": "学校", "degree": "学历", "major": "专业", "start_date": "", "end_date": "", "description": ""}}
    ],
    "work_experiences": [
        {{"company": "公司名", "position": "职位", "start_date": "", "end_date": "", "responsibilities": ["职责1"], "achievements": ["成果1"]}}
    ],
    "projects": [
        {{"name": "项目名", "role": "角色", "start_date": "", "end_date": "", "description": "描述", "highlights": ["亮点"], "tech_stack": ["技术"]}}
    ],
    "skills": [
        {{"category": "类别", "items": ["技能1", "技能2"]}}
    ],
    "certifications": ["证书1", "证书2"]
}}
"""
        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": "你是一位精确的简历解析专家。只提取原文中存在的信息，绝不编造。输出JSON格式。"},
                {"role": "user", "content": prompt},
            ],
            response_format={"type": "json_object"},
            temperature=0.1,
        )

        data = json.loads(response.choices[0].message.content)

        # 构建 Resume 对象
        edu_list = []
        for e in data.get("education", []):
            edu_list.append(Education(
                school=e.get("school", ""),
                degree=e.get("degree", ""),
                major=e.get("major", ""),
                start_date=e.get("start_date", ""),
                end_date=e.get("end_date", ""),
                description=e.get("description", ""),
            ))

        work_list = []
        for w in data.get("work_experiences", []):
            work_list.append(WorkExperience(
                company=w.get("company", ""),
                position=w.get("position", ""),
                start_date=w.get("start_date", ""),
                end_date=w.get("end_date", ""),
                responsibilities=w.get("responsibilities", []),
                achievements=w.get("achievements", []),
            ))

        proj_list = []
        for p in data.get("projects", []):
            proj_list.append(Project(
                name=p.get("name", ""),
                role=p.get("role", ""),
                start_date=p.get("start_date", ""),
                end_date=p.get("end_date", ""),
                description=p.get("description", ""),
                highlights=p.get("highlights", []),
                tech_stack=p.get("tech_stack", []),
            ))

        skill_list = []
        for s in data.get("skills", []):
            skill_list.append(Skill(
                category=s.get("category", ""),
                items=s.get("items", []),
            ))

        return Resume(
            name=data.get("name", ""),
            phone=data.get("phone", ""),
            email=data.get("email", ""),
            title=data.get("title", job_title),
            summary=data.get("summary", ""),
            education=edu_list,
            work_experiences=work_list,
            projects=proj_list,
            skills=skill_list,
            certifications=data.get("certifications", []),
            raw_text=raw_text,
        )

    def analyze(self, resume: Resume) -> Dict[str, Any]:
        """分析简历并返回结构化分析与薄弱环节"""
        prompt = f"""你是一位资深的 HR 顾问和简历优化专家。请分析以下简历，完成以下任务：

1. **结构化提取**: 从原始文本中提取结构化的简历信息
2. **优势分析**: 指出该简历的亮点和优势
3. **薄弱环节**: 指出该简历的不足之处和改进空间
4. **改进建议**: 针对每个薄弱环节给出具体的改进建议

简历原始文本：
```
{resume.raw_text}
```

请以 JSON 格式返回，格式如下：
{{
    "structured": {{
        "name": "姓名",
        "title": "求职意向",
        "summary": "个人总结",
        "education": [{{"school": "", "degree": "", "major": ""}}],
        "skills": [{{"category": "", "items": []}}],
        "work_experiences": [{{"company": "", "position": "", "duration": "", "key_achievements": []}}],
        "projects": [{{"name": "", "role": "", "description": "", "tech_stack": []}}]
    }},
    "strengths": ["优势1", "优势2"],
    "weaknesses": [
        {{"aspect": "薄弱方面", "detail": "具体描述", "suggestion": "改进建议"}}
    ],
    "overall_score": 7.5,
    "key_improvements": ["最重要的3个改进点"]
}}
"""
        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": "你是一位资深的简历优化专家，擅长分析简历并提供结构化反馈。"},
                {"role": "user", "content": prompt},
            ],
            response_format={"type": "json_object"},
            temperature=0.3,
        )

        return json.loads(response.choices[0].message.content)
