"""模板引擎 —— 调度 StyleAgent 生成 HTML"""
from typing import List, Dict
from models.resume import Resume
from generators.style_agent import StyleAgent


class TemplateEngine:
    """简历模板引擎 —— 包装 StyleAgent"""

    def __init__(self):
        self.style_agent = StyleAgent()

    def list_templates(self) -> List[Dict[str, str]]:
        """列出所有可用风格"""
        return self.style_agent.list_styles()

    def render(self, resume: Resume, job_title: str, template_id: str) -> str:
        """渲染为 HTML 字符串（StyleAgent 动态生成）"""
        return self.style_agent.render(resume, job_title, style=template_id)
