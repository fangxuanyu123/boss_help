"""Playwright PDF渲染器——将HTML简历转为PDF"""
from pathlib import Path
from playwright.sync_api import sync_playwright


class PDFRenderer:
    """PDF渲染器（基于 Playwright + Chromium）"""

    def render_html(self, html_content: str, output_path: Path) -> Path:
        """将HTML字符串渲染为PDF文件"""
        with sync_playwright() as p:
            browser = p.chromium.launch()
            page = browser.new_page()
            page.set_content(html_content, wait_until="networkidle")
            page.pdf(path=str(output_path), format="A4", print_background=True)
            browser.close()
        return output_path

    def render_to_bytes(self, html_content: str) -> bytes:
        """将HTML字符串渲染为PDF字节流"""
        with sync_playwright() as p:
            browser = p.chromium.launch()
            page = browser.new_page()
            page.set_content(html_content, wait_until="networkidle")
            pdf_bytes = page.pdf(format="A4", print_background=True)
            browser.close()
        return pdf_bytes
