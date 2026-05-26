"""面经搜索 —— Playwright 搜索 牛客网 + CSDN 面经"""
import logging
import time
from dataclasses import dataclass, field
from urllib.parse import quote

logger = logging.getLogger(__name__)


@dataclass
class MianjingItem:
    """面经条目"""
    title: str = ""
    url: str = ""
    snippet: str = ""
    source: str = ""


def search_mianjing(keywords: list[str], limit: int = 10) -> list[MianjingItem]:
    """搜索 牛客网 + CSDN 上的面经。

    Args:
        keywords: 搜索关键词列表（如 ['Java', 'Kafka', '面试']）
        limit: 最多返回条数
    """
    from playwright.sync_api import sync_playwright

    query = " ".join(keywords[:5])
    results: list[MianjingItem] = []

    pw = sync_playwright().start()
    try:
        browser = pw.chromium.launch(
            headless=True,
            args=["--no-sandbox", "--disable-dev-shm-usage", "--disable-blink-features=AutomationControlled"],
        )
        ctx = browser.new_context(
            viewport={"width": 1920, "height": 1080},
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/131.0.0.0 Safari/537.36",
            locale="zh-CN",
            timezone_id="Asia/Shanghai",
        )
        page = ctx.new_page()

        # 搜索牛客网
        try:
            page.goto(
                f"https://www.nowcoder.com/search?type=post&query={quote(query + ' 面经 面试')}",
                timeout=20000,
                wait_until="networkidle",
            )
            time.sleep(3)

            links = page.query_selector_all("a[href*='/discuss/']")
            seen = set()
            for l in links:
                href = l.get_attribute("href")
                if not href or href in seen:
                    continue
                seen.add(href)
                title = l.inner_text().strip()
                if title and len(title) > 3:
                    url = "https://www.nowcoder.com" + href if href.startswith("/") else href
                    results.append(MianjingItem(
                        title=title,
                        url=url,
                        snippet="",
                        source="牛客网",
                    ))
        except Exception as e:
            logger.debug("牛客搜索跳过: %s", e)

        # 搜索 CSDN
        try:
            page.goto(
                f"https://so.csdn.net/so/search?q={quote(query + ' 面试题')}&t=blog",
                timeout=20000,
                wait_until="domcontentloaded",
            )
            time.sleep(2)

            csdn_links = page.query_selector_all("a[href*='blog.csdn.net']")
            seen_csdn = set()
            for l in csdn_links[:limit]:
                href = l.get_attribute("href")
                if not href or href in seen_csdn:
                    continue
                seen_csdn.add(href)
                title = l.inner_text().strip()
                if title and len(title) > 5:
                    results.append(MianjingItem(
                        title=title,
                        url=href,
                        snippet="",
                        source="CSDN",
                    ))
        except Exception as e:
            logger.debug("CSDN搜索跳过: %s", e)

        browser.close()
    except Exception as e:
        logger.warning("面经搜索失败: %s", e)
    finally:
        try:
            pw.stop()
        except Exception:
            pass

    return results[:limit]
