"""Jinja2模板引擎——加载和渲染简历HTML模板"""
from pathlib import Path
from typing import Dict, Any, List
import re
import yaml
from jinja2 import Environment, FileSystemLoader
from models.resume import Resume


class TemplateEngine:
    """简历模板引擎"""

    def __init__(self):
        self.templates_dir = Path(__file__).parent / "templates"
        self.config_path = Path(__file__).parent / "template_config.yaml"
        self._env = Environment(
            loader=FileSystemLoader(str(self.templates_dir)),
            autoescape=True,
        )
        self._config = None

    @property
    def config(self) -> List[Dict[str, Any]]:
        if self._config is None:
            with open(self.config_path, "r", encoding="utf-8") as f:
                self._config = yaml.safe_load(f)
        return self._config

    def list_templates(self) -> List[Dict[str, str]]:
        """列出所有可用模板"""
        return [
            {"id": t["id"], "name": t["name"], "description": t["description"]}
            for t in self.config
        ]

    def _read_css(self, template_id: str) -> str:
        """读取模板的CSS文件内容"""
        css_path = self.templates_dir / template_id / "style.css"
        if css_path.exists():
            return css_path.read_text(encoding="utf-8")
        return ""

    def render(self, resume: Resume, job_title: str, template_id: str) -> str:
        """将简历渲染为HTML字符串（CSS内嵌，可直接用于PDF渲染）"""
        cfg = next((t for t in self.config if t["id"] == template_id), None)
        if cfg is None:
            cfg = self.config[0]
            template_id = cfg["id"]

        template = self._env.get_template(f"{template_id}/template.html")
        css_content = self._read_css(template_id)

        context = {
            "resume": resume,
            "job_title": job_title,
            "has_education": bool(resume.education),
            "has_work": bool(resume.work_experiences),
            "has_projects": bool(resume.projects),
            "has_skills": bool(resume.skills),
            "has_certifications": bool(resume.certifications),
        }

        html = template.render(**context)

        # 将 <link rel="stylesheet" href="style.css"> 替换为内嵌 <style>
        html = re.sub(
            r'<link\s+rel="stylesheet"\s+href="style\.css"\s*/?>',
            f"<style>\n{css_content}\n</style>",
            html,
        )

        return html
