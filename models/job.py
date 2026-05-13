"""岗位数据模型"""
from pydantic import BaseModel, Field
from typing import List, Optional


class JobRequirement(BaseModel):
    """岗位需求"""
    title: str = ""                    # 岗位名称
    company: str = ""                  # 公司名称
    salary_range: str = ""             # 薪资范围
    location: str = ""                 # 工作地点
    responsibilities: List[str] = Field(default_factory=list)   # 岗位职责
    requirements: List[str] = Field(default_factory=list)       # 任职要求
    preferred: List[str] = Field(default_factory=list)          # 优先条件
    description: str = ""              # 岗位描述原文

    def to_text(self) -> str:
        """转为纯文本"""
        parts = [f"岗位: {self.title}", f"公司: {self.company}"]
        if self.salary_range:
            parts.append(f"薪资: {self.salary_range}")
        if self.location:
            parts.append(f"地点: {self.location}")

        if self.responsibilities:
            parts.append("\n【岗位职责】")
            for r in self.responsibilities:
                parts.append(f"- {r}")

        if self.requirements:
            parts.append("\n【任职要求】")
            for r in self.requirements:
                parts.append(f"- {r}")

        if self.preferred:
            parts.append("\n【优先条件】")
            for p in self.preferred:
                parts.append(f"- {p}")

        return "\n".join(parts)
