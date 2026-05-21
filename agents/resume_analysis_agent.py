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

    def analyze(self, resume: Resume, critique: str | None = None) -> Dict[str, Any]:
        """分析简历并返回结构化分析与薄弱环节。critique 为评估器的改进反馈，非 None 时表示重试。"""
        prompt = f"""你是一位经验丰富的职业顾问，擅长从用人方视角审视简历。请仔细阅读以下简历，找出其**真正的薄弱点**，给出精准、一针见血的分析。

=== 简历原文 ===
{resume.raw_text}

=== 分析原则（严格遵守） ===

1. **行业无关性**：不要预设候选人所在行业或岗位。从简历内容本身出发，判断这份简历在其自身领域中存在的问题。

2. **优势分析**：指出简历的亮点，限定 2-3 条，每条一句话，具体到点。

3. **薄弱环节分析（核心）**：
   - 找出简历中**实质性的、会影响竞争力**的问题，例如：
     · 经历描述浮于表面——只罗列了"做了什么"，没有体现"做得怎么样"、"解决了什么难题"、"带来了什么价值"
     · 关键成果缺乏说服力——有数据但数据无法体现个人贡献度，或该量化的地方没有量化
     · 经历堆砌无重点——罗列了大量项目/职责，但没有一条能让人记住的核心亮点
     · 表述笼统空泛——使用了大量"参与""协助""负责"等动词，但看不出实际角色深度
     · 关键信息缺失——对于该领域来说必须体现的能力或经验没有覆盖到
   - **严禁**将以下内容列为薄弱点：
     · 缺少个人总结/求职意向（简洁有力的简历不需要这些）
     · 排版格式问题（除非严重到影响理解）
     · 教育背景缺少 GPA 或课程列表（非必填项）
     · 简历篇幅偏短（简洁是优点，不是缺点）
   - 每条薄弱点**必须引用简历原文的具体内容**作为证据，不得脱离简历泛泛而谈
   - 如果确实没有实质性薄弱点，weaknesses 可以为空数组，不要硬凑

4. **改进建议**：不说空话（如"补充量化指标"），而是给出**针对性的、可立即执行**的方案。例如不说"成果应该量化"，而说"在XX模块中，可以补充处理的请求量级、优化的性能提升百分比"。

5. **评分**：10 分制。8分以上 = 在其领域内较有竞争力，6-7分 = 有提升空间，5分以下 = 有硬伤需大幅改进。

返回 JSON 格式：
{{
    "strengths": ["具体优势1", "具体优势2"],
    "weaknesses": [
        {{"aspect": "薄弱方面（一句概括）", "detail": "简历中的具体表现", "suggestion": "具体可执行的改进方案"}}
    ],
    "overall_score": 7.0,
    "key_improvements": ["最重要的改进点（不超过3条，按优先级排序）"]
}}
"""
        system_content = (
            "你是一位资深职业顾问，为各行业求职者审视简历。"
            "你眼光老辣但不过度苛刻：你关注的是简历在目标行业中的真实竞争力，"
            "能一眼看穿哪些是表面问题、哪些是硬伤。"
            "你从不说正确的废话，每条建议都必须具体、可执行、直击要害。"
        )
        if critique:
            system_content += f"\n\n=== 上一轮输出的改进反馈 ===\n{critique}\n请针对以上反馈，修正你上一轮的输出。"

        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": system_content},
                {"role": "user", "content": prompt},
            ],
            response_format={"type": "json_object"},
            temperature=0.3,
        )

        return json.loads(response.choices[0].message.content)
