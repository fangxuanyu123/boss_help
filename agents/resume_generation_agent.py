"""简历生成 Agent - 根据优化建议生成结构化简历"""
from typing import Dict, Any
import json
import logging
from openai import OpenAI
from config import LLM_API_KEY, LLM_BASE_URL, LLM_MODEL_NAME
from models.resume import Resume, WorkExperience, Project, Skill, Education
from models.job import JobRequirement

logger = logging.getLogger(__name__)


class ResumeGenerationAgent:
    """简历生成智能体——输出结构化JSON简历"""

    def __init__(self):
        self.client = OpenAI(api_key=LLM_API_KEY, base_url=LLM_BASE_URL)
        self.model = LLM_MODEL_NAME

    def generate(
        self,
        original_resume: Resume,
        suggestions: Dict[str, Any],
        job: JobRequirement,
    ) -> Resume:
        """生成优化后的结构化简历"""
        suggestion_text = ""
        for opt in suggestions.get("content_optimizations", []):
            suggestion_text += f"### {opt.get('section', '')}\n"
            suggestion_text += f"- 问题: {opt.get('original', '')}\n"
            suggestion_text += f"- 建议: {opt.get('suggestion', '')}\n"
            if opt.get("example"):
                suggestion_text += f"- 示例: {opt.get('example', '')}\n"
            suggestion_text += "\n"

        keywords = ", ".join(suggestions.get("keywords_to_add", []))

        prompt = f"""你是一位资深的简历优化专家。请严格基于原始简历的内容进行优化修改。

【CRITICAL - 严格基于原始简历，禁止编造】
- 公司名、职位名、项目名、起止日期、学校名、专业、学历 — **必须与原始简历一字不差**
- 你只能优化以下内容：responsibilities和achievements的措辞（STAR法则）、summary的侧重方向、skills的有依据补充
- 对于完全匹配的条目，保持原样（change_type=keep），不要为了改而改

=== 原始简历（结构化） ===
{original_resume.to_text()}

=== 目标岗位 ===
{job.to_text()}

=== 优化建议 ===
整体策略: {suggestions.get('overall_strategy', '')}
关键关键词: {keywords}
针对性调整: {suggestions.get('job_targeting', '')}

具体优化项:
{suggestion_text}

=== 核心原则 ===
0. **禁止编造 [CRITICAL]**: 公司名/职位名/项目名/日期/学校名/专业/学历 — 这些必须与原始简历一字不差。永远不要编造新的公司、职位、项目或日期。
1. **尊重原始数据**: 所有事实性信息（公司、职位、日期、项目名）来自原始简历，不允许修改
2. **可优化内容**: responsibilities描述用STAR法则改写、achievements量化强化、summary调整侧重、skills从经历中推断补充
3. **少改优于多改**: 如果某项已经写得好，就保持原样（change_type=keep）。不需要每项都改。
4. **输出完整简历**: 必须包含所有板块，未修改的板块也要完整输出

返回完整JSON（所有板块必须包含原始简历中的所有条目）：

{{
    "name": "{original_resume.name}",
    "phone": "{original_resume.phone}",
    "email": "{original_resume.email}",
    "title": "优化后的求职意向",
    "summary": "优化后的个人总结（200字内）",
    "education": [
        {{"school": "学校名", "degree": "学历", "major": "专业", "start_date": "", "end_date": "", "description": "", "change_type": "keep"}}
    ],
    "work_experiences": [
        {{"company": "公司名", "position": "职位", "start_date": "", "end_date": "", "responsibilities": ["优化后职责"], "achievements": ["优化后成果"], "change_type": "new_wording"}}
    ],
    "projects": [
        {{"name": "项目名", "role": "角色", "start_date": "", "end_date": "", "description": "项目描述", "highlights": ["优化后亮点"], "tech_stack": ["技术栈"], "change_type": "new_wording"}}
    ],
    "skills": [
        {{"category": "技能类别", "items": ["技能"], "change_type": "modified"}}
    ],
    "certifications": ["证书"],
    "raw_text": ""
}}

change_type 说明：keep=未修改, modified=内容有修改, restructured=结构/顺序调整, new_wording=重新表述"""
        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": "你是一位资深的简历优化专家。你必须输出一份完整的优化简历JSON，包含所有板块（education、work_experiences、projects、skills）。绝不允许只输出修改过的部分，未修改的板块也必须原样输出。"},
                {"role": "user", "content": prompt},
            ],
            response_format={"type": "json_object"},
            temperature=0.3,
        )

        data = json.loads(response.choices[0].message.content)

        # 校验：确保关键字段不丢失
        data = self._validate_completeness(data, original_resume)
        return self._build_resume(data, original_resume)

    def _validate_completeness(self, data: dict, original: Resume) -> dict:
        """校验 LLM 返回的 JSON 是否包含所有原始数据，缺失或编造则回退到原始"""
        # 1. 校验顶层身份字段（不可编造）
        for field in ["name", "phone", "email"]:
            orig_val = getattr(original, field, "")
            new_val = data.get(field, "")
            if orig_val and new_val != orig_val:
                logger.warning(f"[ResumeGenerationAgent] '{field}' 被修改 '{orig_val}' → '{new_val}'，回退到原始")
                data[field] = orig_val

        # 2. 校验数组字段的数量和关键事实字段
        array_checks = [
            ("work_experiences", original.work_experiences, ["company", "position", "start_date", "end_date"]),
            ("projects", original.projects, ["name", "start_date", "end_date"]),
            ("education", original.education, ["school", "degree", "major", "start_date", "end_date"]),
        ]

        for field, original_list, key_fields in array_checks:
            items = data.get(field)
            if items is None or (len(original_list) > 0 and len(items) == 0):
                logger.warning(f"[ResumeGenerationAgent] '{field}' 缺失，使用原始数据")
                data[field] = [item.model_dump() for item in original_list]
                continue

            # 逐条校验事实字段是否与原始一致
            validated = []
            for i, item in enumerate(items):
                if i < len(original_list):
                    orig_item = original_list[i]
                    for kf in key_fields:
                        orig_val = getattr(orig_item, kf, "")
                        new_val = item.get(kf, "")
                        if orig_val and new_val and new_val != orig_val:
                            logger.warning(f"[ResumeGenerationAgent] '{field}[{i}].{kf}' 被篡改 '{orig_val}' → '{new_val}'，回退")
                            item[kf] = orig_val
                validated.append(item)

            data[field] = validated

        # 3. 校验 skills 和 certifications 数量
        for field, original_list in [
            ("skills", original.skills),
            ("certifications", original.certifications),
        ]:
            items = data.get(field)
            if items is None:
                data[field] = [item.model_dump() for item in original_list]
            elif len(original_list) > 0 and len(items) == 0:
                data[field] = [item.model_dump() for item in original_list]

        return data

    def _build_resume(self, data: dict, original: Resume) -> Resume:
        """从LLM返回的JSON构建Resume对象"""
        edu_list = []
        for e in data.get("education", []):
            edu_list.append(Education(
                school=e.get("school", ""),
                degree=e.get("degree", ""),
                major=e.get("major", ""),
                start_date=e.get("start_date", ""),
                end_date=e.get("end_date", ""),
                description=e.get("description", ""),
                change_type=e.get("change_type", "keep"),
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
                change_type=w.get("change_type", "keep"),
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
                change_type=p.get("change_type", "keep"),
            ))

        skill_list = []
        for s in data.get("skills", []):
            skill_list.append(Skill(
                category=s.get("category", ""),
                items=s.get("items", []),
                change_type=s.get("change_type", "keep"),
            ))

        return Resume(
            name=data.get("name", original.name),
            phone=data.get("phone", original.phone),
            email=data.get("email", original.email),
            title=data.get("title", original.title),
            summary=data.get("summary", ""),
            education=edu_list or original.education,
            work_experiences=work_list or original.work_experiences,
            projects=proj_list or original.projects,
            skills=skill_list or original.skills,
            certifications=data.get("certifications", original.certifications),
            raw_text=data.get("raw_text", ""),
        )
