"""面经搜索 —— Playwright 搜索 牛客网 + CSDN 面经（带质量过滤）"""
import logging
import re
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


# ---- 质量过滤规则 ----

# 标题中必须包含面经相关词（至少一个）
MIANJING_TERMS = [
    "面经", "面试题", "面试经验", "面试总结", "面试准备",
    "面试", "笔试", "考题", "真题", "问答", "参考答案",
    "八股", "知识点", "常考", "必问", "核心面试",
]

# 标题中出现这些词且不包含面经词 → 过滤（招聘/广告/无关）
NOISE_TERMS = [
    "招聘", "秋招", "校招", "社招", "提前批", "开启",
    "内推", "急招", "HC", "人才", "大厂解析",
]

# 标题长度太短 → 可能是用户名/无意义页面
MIN_TITLE_LEN = 8


def _is_quality_mianjing(title: str) -> bool:
    """判断标题是否为高质量面经"""
    if len(title) < MIN_TITLE_LEN:
        return False

    # 不含任何面经相关词 → 不行
    has_mianjing = any(t in title for t in MIANJING_TERMS)
    if not has_mianjing:
        return False

    # 包含噪声词且不包含面经核心词 → 过滤
    is_noise = any(t in title for t in NOISE_TERMS)
    core_mianjing = any(t in title for t in ["面经", "面试题", "面试经验", "面试总结", "参考答案", "笔试"])
    if is_noise and not core_mianjing:
        return False

    return True


def _score_title(title: str) -> int:
    """给标题打分，越高越相关"""
    score = 0
    for t in MIANJING_TERMS:
        if t in title:
            score += 2
    # 标题包含关键词中的技术名词加分（如 Java/Kafka/ROS）
    # 由调用方处理，这里只做基本打分
    title_lower = title.lower()
    for kw in ["面经", "面试经验", "面试总结"]:
        if kw in title_lower:
            score += 3
    return score


# ---- 搜索函数 ----

def search_mianjing(keywords: list[str], limit: int = 10) -> list[MianjingItem]:
    """搜索 牛客网 + CSDN 上的面经，自动过滤低质量结果。

    Args:
        keywords: 搜索关键词列表（如 ['Java', 'Kafka', '面试']）
        limit: 最多返回条数
    """
    from playwright.sync_api import sync_playwright

    # 构建精准搜索词：核心关键词 + 面经限定词
    core_kw = keywords[:4]
    nowcoder_query = " ".join(core_kw) + " 面经"
    csdn_query = " ".join(core_kw) + " 面试题 面试经验"

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

        # === 牛客网：type=post, 搜索 "关键词 面经" ===
        try:
            page.goto(
                f"https://www.nowcoder.com/search?type=post&query={quote(nowcoder_query)}",
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
                title = l.inner_text().strip()
                if not title or len(title) < MIN_TITLE_LEN:
                    continue
                seen.add(href)

                if _is_quality_mianjing(title):
                    url = "https://www.nowcoder.com" + href if href.startswith("/") else href
                    results.append(MianjingItem(
                        title=title, url=url, snippet="", source="牛客网",
                    ))
        except Exception as e:
            logger.debug("牛客搜索跳过: %s", e)

        # === CSDN：blog 搜索 "关键词 面试题 面试经验" ===
        try:
            page.goto(
                f"https://so.csdn.net/so/search?q={quote(csdn_query)}&t=blog",
                timeout=20000,
                wait_until="domcontentloaded",
            )
            time.sleep(2)

            csdn_links = page.query_selector_all("a[href*='blog.csdn.net']")
            seen_csdn = set()
            for l in csdn_links:
                href = l.get_attribute("href")
                if not href or href in seen_csdn:
                    continue
                title = l.inner_text().strip()
                if not title or len(title) < MIN_TITLE_LEN:
                    continue
                seen_csdn.add(href)

                if _is_quality_mianjing(title):
                    results.append(MianjingItem(
                        title=title, url=href, snippet="", source="CSDN",
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

    # 按标题质量排序，去重
    unique = {}
    for r in results:
        key = r.title.strip().lower()
        if key not in unique or _score_title(r.title) > _score_title(unique[key].title):
            unique[key] = r

    sorted_results = sorted(unique.values(), key=lambda r: _score_title(r.title), reverse=True)
    return sorted_results[:limit]
