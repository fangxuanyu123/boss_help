"""岗位搜索核心逻辑 —— Playwright 自动化搜索 51job / Boss 直聘"""
import time
import logging
from urllib.parse import quote
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class JobListing:
    """结构化岗位信息"""
    title: str = ""
    company: str = ""
    salary: str = ""
    city: str = ""
    experience: str = ""
    education: str = ""
    tags: list = field(default_factory=list)
    jd_text: str = ""
    url: str = ""
    match_score: float = 0.0
    source: str = ""


def _compute_match(jd: str, keywords: list[str]) -> float:
    if not keywords:
        return 0.0
    jd_lower = jd.lower()
    hits = sum(1 for kw in keywords if kw.lower() in jd_lower)
    return round(hits / len(keywords) * 100, 1)


def _new_browser():
    from playwright.sync_api import sync_playwright
    from playwright_stealth import Stealth

    pw = sync_playwright().start()
    browser = pw.chromium.launch(
        headless=True,
        args=["--disable-blink-features=AutomationControlled", "--no-sandbox", "--disable-dev-shm-usage"],
    )
    ctx = browser.new_context(
        viewport={"width": 1920, "height": 1080},
        user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
        locale="zh-CN",
        timezone_id="Asia/Shanghai",
    )
    page = ctx.new_page()
    Stealth().apply_stealth_sync(page)
    return pw, browser, ctx, page


def _search_51job(title: str, keywords: list[str], city: str, limit: int) -> list[JobListing]:
    """在 51job 搜索岗位（server-rendered HTML，爬取友好）"""
    search_term = title
    if keywords:
        search_term += " " + " ".join(keywords[:2])

    # 51job 城市码映射（常用）
    city_codes = {
        "北京": "010000", "上海": "020000", "广州": "030200", "深圳": "040000",
        "杭州": "080200", "成都": "090200", "南京": "070200", "武汉": "180200",
        "西安": "200200", "苏州": "070300", "重庆": "060000", "天津": "050000",
    }
    city_code = city_codes.get(city.replace("市", ""), "000000")

    search_url = (
        f"https://search.51job.com/list/"
        f"{city_code},000000,0000,00,9,99,{quote(search_term)},2,1.html"
    )

    logger.info("51job 搜索: %s (city=%s)", title, city or "不限")

    pw, browser, ctx, page = _new_browser()
    jobs: list[JobListing] = []

    try:
        page.goto(search_url, timeout=30000, wait_until="domcontentloaded")
        time.sleep(3)

        # 调试：检查实际 URL 和页面内容
        logger.info("51job 实际页面: %s", page.url[:80])
        body_text = page.inner_text("body")[:200] if page.query_selector("body") else "(空)"
        logger.info("51job 页面片段: %s", body_text.replace("\n", " "))

        # 多策略找卡片
        cards = page.query_selector_all("div.el")
        if not cards:
            cards = page.query_selector_all("div.joblist-item")
        if not cards:
            cards = page.query_selector_all("[class*='job']")
        if not cards:
            cards = page.query_selector_all("div.re, div.r1, div.r2")
        if not cards:
            cards = page.query_selector_all("script")  # 检查是否纯JS渲染

        logger.info("51job 找到 %d 个卡片（script=%d）",
                    0 if not cards else len(cards),
                    sum(1 for c in (cards or []) if c.evaluate("el => el.tagName") == "SCRIPT"))

        for card in cards[:limit * 2]:
            try:
                # 岗位名
                title_el = card.query_selector(".t1 span[title]") or card.query_selector("[class*='title'] span")
                if not title_el:
                    title_el = card.query_selector("a[class*='job']")
                job_title_text = title_el.inner_text().strip() if title_el else ""
                if not job_title_text:
                    continue

                # 公司
                company_el = card.query_selector(".t2 a") or card.query_selector("[class*='company'] a")
                company_text = company_el.inner_text().strip() if company_el else ""

                # 薪资 + 城市 + 经验/学历
                t3 = card.query_selector(".t3")
                t4 = card.query_selector(".t4")
                t5 = card.query_selector(".t5")

                salary_text = t3.inner_text().strip() if t3 else ""
                city_text = t4.inner_text().strip() if t4 else ""
                edu_exp = t5.inner_text().strip() if t5 else ""

                # 链接
                url = ""
                link_el = card.query_selector("a")
                if link_el:
                    href = link_el.get_attribute("href")
                    if href:
                        url = href if href.startswith("http") else "https://search.51job.com" + href

                brief = job_title_text + " " + edu_exp
                match = _compute_match(brief, keywords)

                jobs.append(JobListing(
                    title=job_title_text,
                    company=company_text,
                    salary=salary_text,
                    city=city_text or city,
                    experience=edu_exp,
                    education="",
                    tags=[edu_exp] if edu_exp else [],
                    url=url,
                    match_score=match,
                    source="51job",
                ))
            except Exception as e:
                logger.debug("51job 解析卡片失败: %s", e)
                continue

    except Exception as e:
        logger.warning("51job 搜索失败: %s", e)
    finally:
        try: page.close();
        except: pass
        try: ctx.close();
        except: pass
        try: browser.close();
        except: pass
        try: pw.stop();
        except: pass

    jobs.sort(key=lambda j: j.match_score, reverse=True)
    return jobs[:limit]


def _search_boss(title: str, keywords: list[str], city: str, limit: int) -> list[JobListing]:
    """Boss 直聘搜索（备用）"""
    query = title
    if keywords:
        query += " " + " ".join(keywords[:3])

    if city:
        search_url = f"https://www.zhipin.com/web/geek/job?query={quote(query)}&city={quote(city)}"
    else:
        search_url = f"https://www.zhipin.com/web/geek/job?query={quote(query)}"

    logger.info("Boss 直聘搜索: %s (city=%s)", title, city or "不限")

    pw, browser, ctx, page = _new_browser()
    jobs: list[JobListing] = []

    try:
        page.goto(search_url, timeout=30000, wait_until="networkidle")
        time.sleep(5)

        current_url = page.url
        if "login" in current_url or "verify" in current_url or "captcha" in current_url:
            raise RuntimeError("Boss直聘触发了反爬验证")

        cards = page.query_selector_all("li.job-card-wrapper") or \
                page.query_selector_all("li.job-card-box") or \
                page.query_selector_all("[class*='job-card']")

        for card in (cards or [])[:limit * 2]:
            try:
                title_el = card.query_selector(".job-name") or card.query_selector("[class*='job-name']")
                t = title_el.inner_text().strip() if title_el else ""
                if not t:
                    continue
                salary_el = card.query_selector(".salary") or card.query_selector("[class*='salary']")
                company_el = card.query_selector(".company-name") or card.query_selector("[class*='company-name']")

                tag_els = card.query_selector_all(".tag-list li") or card.query_selector_all("[class*='tag']")
                tags = [tag.inner_text().strip() for tag in tag_els if tag.inner_text().strip()]

                area_el = card.query_selector(".job-area") or card.query_selector("[class*='area']")
                cty = area_el.inner_text().strip() if area_el else ""

                link_el = card.query_selector("a")
                url = ""
                if link_el:
                    href = link_el.get_attribute("href") or ""
                    url = "https://www.zhipin.com" + href if href.startswith("/") else href

                brief = t + " " + " ".join(tags)
                match = _compute_match(brief, keywords)

                jobs.append(JobListing(
                    title=t,
                    company=company_el.inner_text().strip() if company_el else "",
                    salary=salary_el.inner_text().strip() if salary_el else "",
                    city=cty,
                    experience=tags[0] if tags else "",
                    education=tags[1] if len(tags) > 1 else "",
                    tags=tags,
                    url=url,
                    match_score=match,
                    source="Boss直聘",
                ))
            except Exception as e:
                logger.debug("Boss 解析卡片失败: %s", e)
                continue

    except Exception as e:
        logger.warning("Boss 直聘搜索失败: %s", e)
    finally:
        try: page.close();
        except: pass
        try: ctx.close();
        except: pass
        try: browser.close();
        except: pass
        try: pw.stop();
        except: pass

    jobs.sort(key=lambda j: j.match_score, reverse=True)
    return jobs[:limit]


def search_jobs(
    title: str,
    keywords: list[str],
    city: str = "",
    limit: int = 15,
) -> list[JobListing]:
    """搜索岗位。优先 51job，失败时尝试 Boss 直聘。

    Args:
        title: 岗位名称
        keywords: 技术关键词
        city: 城市（可选）
        limit: 返回数量上限
    """
    # 优先 51job（反爬宽松）
    logger.info("搜索岗位: %s, city=%s, keywords=%d", title, city, len(keywords))
    jobs = _search_51job(title, keywords, city, limit)
    if jobs:
        logger.info("51job 返回 %d 个岗位", len(jobs))
        return jobs

    # 51job 失败则尝试 Boss 直聘
    logger.info("51job 无结果，尝试 Boss 直聘")
    jobs = _search_boss(title, keywords, city, limit)
    if jobs:
        logger.info("Boss 直聘返回 %d 个岗位", len(jobs))
        return jobs

    raise RuntimeError(
        "所有招聘网站均搜索失败。可能原因：网络问题、网站结构调整、或反爬验证。"
    )
