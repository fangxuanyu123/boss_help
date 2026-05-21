"""StyleAgent —— LLM 动态生成简历 HTML，按用户选择的风格自适应排版"""
from openai import OpenAI
from config import LLM_API_KEY, LLM_BASE_URL, LLM_MODEL_NAME
from models.resume import Resume


class StyleAgent:
    """LLM 驱动的简历 HTML 生成器。

    替代固定模板。根据风格关键词和简历内容，生成带内联CSS的完整HTML。
    """

    STYLES = {
        "minimal": "极简黑白，单栏，无装饰，高对比度，标准字号。适合投递大厂，对ATS解析友好。",
        "professional": "传统商务，双栏布局，蓝色或深灰辅助色，衬线字体。适合金融/法律/制造业。",
        "creative": "现代活力，色彩点缀，非对称布局可选，适当的图标和视觉层次。适合互联网/设计。",
        "compact": "紧凑单页，高信息密度，最小化留白，字体略小。适合校招或初级岗位。",
    }

    def __init__(self):
        self.client = OpenAI(api_key=LLM_API_KEY, base_url=LLM_BASE_URL)
        self.model = LLM_MODEL_NAME

    def list_styles(self) -> list:
        return [{"id": k, "name": k, "description": v.split("。")[0]} for k, v in self.STYLES.items()]

    def render(self, resume: Resume, job_title: str, style: str = "professional", page_size: str = "A4") -> str:
        """生成完整的 HTML 字符串（含内联CSS），可直接用于PDF渲染。"""
        style_desc = self.STYLES.get(style, self.STYLES["professional"])

        prompt = f"""你是一位资深的前端设计师，精通中文简历排版。请根据以下结构化简历和风格要求，生成一份完整的 HTML 简历文档。

=== 风格要求 ===
{style_desc}

=== 纸张 ===
{page_size}（210mm × 297mm），打印边距 15-20mm

=== 结构化简历 ===
{resume.to_text()}

=== 目标岗位 ===
{job_title}

=== 生成要求 ===

1. **必须是完整的独立 HTML 文件**，包含 <html><head><body>，所有 CSS 内嵌在 <style> 标签中。
2. **不要引入外部资源**（不要 Google Fonts、CDN 等），使用系统字体栈。
3. **中文排版**：正文使用系统中文字体（如 "PingFang SC", "Microsoft YaHei", "SimSun"），字号恰当（正文10-12pt，标题14-18pt）。
4. **视觉层次**：用小标题、留白、细线来区分板块，不要用大面积色块。
5. **内容完整**：所有板块（个人信息、教育、工作、项目、技能、证书）必须完整呈现，不省略任何条目。
6. **适合打印**：避免深色背景、避免依赖颜色传递信息（简历通常是黑白打印的）。
7. **ATS友好**：使用语义化 HTML 标签（section, h1-h3, ul/li），关键信息不要藏在CSS伪元素或图标字体里。
8. **响应式但重点是打印**：CSS @page 设置适合打印的边距。

直接输出完整的 HTML 源码，不要用 markdown 代码块包裹。"""
        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": "你是一位资深前端设计师，擅长生成精美、专业的中文排版HTML。你输出的HTML是完整可用的，不需要任何外部资源。你注重细节：字距、行高、颜色灰度、留白节奏。你尊重内容的完整性，绝不省略或简化任何一段经历。"},
                {"role": "user", "content": prompt},
            ],
            temperature=0.4,
        )

        html = response.choices[0].message.content
        if html.startswith("```html"):
            html = html[7:]
        if html.startswith("```"):
            html = html[3:]
        if html.endswith("```"):
            html = html[:-3]
        return html.strip()
