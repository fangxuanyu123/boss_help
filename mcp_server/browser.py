"""Playwright 浏览器管理 —— 共享浏览器实例"""
from playwright.sync_api import sync_playwright, Browser, Page


_browser: Browser | None = None
_playwright = None


def get_page() -> Page:
    """获取或创建浏览器页面"""
    global _browser, _playwright
    if _browser is None:
        _playwright = sync_playwright().start()
        _browser = _playwright.chromium.launch(headless=True)
    ctx = _browser.new_context(
        viewport={"width": 1920, "height": 1080},
        user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    )
    return ctx.new_page()


def close_browser():
    global _browser, _playwright
    if _browser:
        _browser.close()
        _browser = None
    if _playwright:
        _playwright.stop()
        _playwright = None
