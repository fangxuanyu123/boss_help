"""Playwright 浏览器管理 —— 共享浏览器实例（含 stealth 伪装）"""
from playwright.sync_api import sync_playwright, Browser, Page
from playwright_stealth import Stealth

_browser: Browser | None = None
_playwright = None


def get_page() -> Page:
    """获取或创建带 stealth 伪装的浏览器页面"""
    global _browser, _playwright
    if _browser is None:
        _playwright = sync_playwright().start()
        _browser = _playwright.chromium.launch(
            headless=True,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox",
                "--disable-dev-shm-usage",
            ],
        )
    ctx = _browser.new_context(
        viewport={"width": 1920, "height": 1080},
        user_agent=(
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/131.0.0.0 Safari/537.36"
        ),
        locale="zh-CN",
        timezone_id="Asia/Shanghai",
    )
    page = ctx.new_page()
    Stealth().apply_stealth_sync(page)
    return page


def close_browser():
    global _browser, _playwright
    if _browser:
        _browser.close()
        _browser = None
    if _playwright:
        _playwright.stop()
        _playwright = None
