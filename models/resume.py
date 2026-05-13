"""简历数据模型"""
from pydantic import BaseModel, Field
from typing import List, Optional


class Education(BaseModel):
    """教育经历"""
    school: str = ""
    degree: str = ""        # 本科/硕士/博士
    major: str = ""
    start_date: str = ""
    end_date: str = ""
    description: str = ""


class WorkExperience(BaseModel):
    """工作经历"""
    company: str = ""
    position: str = ""
    start_date: str = ""
    end_date: str = ""
    responsibilities: List[str] = Field(default_factory=list)
    achievements: List[str] = Field(default_factory=list)


class Project(BaseModel):
    """项目经历"""
    name: str = ""
    role: str = ""
    start_date: str = ""
    end_date: str = ""
    description: str = ""
    highlights: List[str] = Field(default_factory=list)
    tech_stack: List[str] = Field(default_factory=list)


class Skill(BaseModel):
    """技能"""
    category: str = ""       # 如：编程语言、框架、工具
    items: List[str] = Field(default_factory=list)


class Resume(BaseModel):
    """完整简历"""
    name: str = ""
    phone: str = ""
    email: str = ""
    title: str = ""           # 求职意向/目标职位
    summary: str = ""         # 个人总结
    education: List[Education] = Field(default_factory=list)
    work_experiences: List[WorkExperience] = Field(default_factory=list)
    projects: List[Project] = Field(default_factory=list)
    skills: List[Skill] = Field(default_factory=list)
    certifications: List[str] = Field(default_factory=list)
    raw_text: str = ""        # 原始解析文本

    def to_text(self) -> str:
        """转为纯文本用于 LLM 输入"""
        parts = [f"姓名: {self.name}"]
        if self.title:
            parts.append(f"求职意向: {self.title}")
        if self.summary:
            parts.append(f"个人总结: {self.summary}")

        if self.education:
            parts.append("\n【教育背景】")
            for edu in self.education:
                parts.append(f"- {edu.school} | {edu.degree} | {edu.major} ({edu.start_date}-{edu.end_date})")

        if self.work_experiences:
            parts.append("\n【工作经历】")
            for exp in self.work_experiences:
                parts.append(f"- {exp.company} | {exp.position} ({exp.start_date}-{exp.end_date})")
                for r in exp.responsibilities:
                    parts.append(f"  · {r}")
                for a in exp.achievements:
                    parts.append(f"  ★ {a}")

        if self.projects:
            parts.append("\n【项目经历】")
            for proj in self.projects:
                parts.append(f"- {proj.name} ({proj.role})")
                if proj.description:
                    parts.append(f"  {proj.description}")
                for h in proj.highlights:
                    parts.append(f"  · {h}")
                if proj.tech_stack:
                    parts.append(f"  技术栈: {', '.join(proj.tech_stack)}")

        if self.skills:
            parts.append("\n【技能】")
            for skill in self.skills:
                parts.append(f"- {skill.category}: {', '.join(skill.items)}")

        if self.certifications:
            parts.append(f"\n【证书】: {', '.join(self.certifications)}")

        return "\n".join(parts)
