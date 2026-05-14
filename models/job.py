"""岗位数据模型"""
from pydantic import BaseModel, Field
from typing import List, Optional


class JobRequirement(BaseModel):
    """岗位需求画像——统一表示JD提取结果或岗位名推测结果"""
    title: str = ""                    # 岗位名称
    company: str = ""                  # 公司名称
    salary_range: str = ""             # 薪资范围
    location: str = ""                 # 工作地点
    responsibilities: List[str] = Field(default_factory=list)   # 岗位职责
    requirements: List[str] = Field(default_factory=list)       # 硬性要求
    preferred: List[str] = Field(default_factory=list)          # 加分项
    tech_keywords: List[str] = Field(default_factory=list)      # 技术栈关键词
    soft_skills: List[str] = Field(default_factory=list)        # 软技能要求
    industry: str = ""                 # 行业领域
    level: str = ""                    # 岗位层级（初级/中级/高级/专家/管理）
    description: str = ""              # 岗位描述原文（JD模式下有值）
    source: str = ""                   # "jd" 或 "title"

    def to_text(self) -> str:
        """转为纯文本"""
        parts = [f"岗位: {self.title}"]
        if self.company:
            parts.append(f"公司: {self.company}")
        if self.salary_range:
            parts.append(f"薪资: {self.salary_range}")
        if self.location:
            parts.append(f"地点: {self.location}")
        if self.level:
            parts.append(f"层级: {self.level}")
        if self.industry:
            parts.append(f"行业: {self.industry}")

        if self.responsibilities:
            parts.append("\n【岗位职责】")
            for r in self.responsibilities:
                parts.append(f"- {r}")

        if self.requirements:
            parts.append("\n【硬性要求】")
            for r in self.requirements:
                parts.append(f"- {r}")

        if self.preferred:
            parts.append("\n【加分项】")
            for p in self.preferred:
                parts.append(f"- {p}")

        if self.tech_keywords:
            parts.append(f"\n【技术关键词】: {', '.join(self.tech_keywords)}")

        if self.soft_skills:
            parts.append(f"\n【软技能】: {', '.join(self.soft_skills)}")

        return "\n".join(parts)
