"""岗位搜索核心逻辑 —— Playwright 自动化搜索 Boss 直聘"""
import time
import logging
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


def _compute_match(jd: str, keywords: list[str]) -> float:
    """简单命中率匹配：统计关键词在 JD 中出现的比例"""
    if not keywords:
        return 0.0
    jd_lower = jd.lower()
    hits = sum(1 for kw in keywords if kw.lower() in jd_lower)
    return round(hits / len(keywords) * 100, 1)


def search_jobs(
    title: str,
    keywords: list[str],
    city: str = "",
    limit: int = 15,
) -> list[JobListing]:
    """搜索岗位。

    Args:
        title: 岗位名称（如 "高级Java开发工程师"）
        keywords: 技术关键词（用于匹配度计算和辅助搜索）
        city: 城市（可选，如 "深圳"）
        limit: 返回数量上限

    Returns:
        按 match_score 降序排列的岗位列表
    """
    from mcp_server.browser import get_page

    query = title
    if keywords:
        query += " " + " ".join(keywords[:3])

    if city:
        search_url = f"https://www.zhipin.com/web/geek/job?query={query}&city={city}"
    else:
        search_url = f"https://www.zhipin.com/web/geek/job?query={query}"

    logger.info("搜索岗位: %s (city=%s)", title, city or "不限")

    page = get_page()
    jobs: list[JobListing] = []

    try:
        page.goto(search_url, timeout=30000, wait_until="domcontentloaded")
        time.sleep(3)

        job_cards = page.query_selector_all("li.job-card-wrapper")
        if not job_cards:
            job_cards = page.query_selector_all("li.job-card-box")
        if not job_cards:
            job_cards = page.query_selector_all("[class*='job-card']")

        for card in job_cards[:limit * 2]:
            try:
                title_el = card.query_selector(".job-name")
                if not title_el:
                    title_el = card.query_selector("[class*='job-name']")
                job_title_text = title_el.inner_text().strip() if title_el else ""

                salary_el = card.query_selector(".salary")
                if not salary_el:
                    salary_el = card.query_selector("[class*='salary']")
                salary_text = salary_el.inner_text().strip() if salary_el else ""

                company_el = card.query_selector(".company-name")
                if not company_el:
                    company_el = card.query_selector("[class*='company-name']")
                company_text = company_el.inner_text().strip() if company_el else ""

                tag_els = card.query_selector_all(".tag-list li")
                if not tag_els:
                    tag_els = card.query_selector_all("[class*='tag']")
                tags = [t.inner_text().strip() for t in tag_els if t.inner_text().strip()]

                city_text = ""
                area_el = card.query_selector(".job-area")
                if not area_el:
                    area_el = card.query_selector("[class*='area']")
                if area_el:
                    city_text = area_el.inner_text().strip()

                link_el = card.query_selector("a")
                url = ""
                if link_el:
                    href = link_el.get_attribute("href")
                    if href:
                        url = "https://www.zhipin.com" + href if href.startswith("/") else href

                exp_text = tags[0] if len(tags) > 0 else ""
                edu_text = tags[1] if len(tags) > 1 else ""

                if not job_title_text or not company_text:
                    continue

                brief_text = job_title_text + " " + " ".join(tags)
                match = _compute_match(brief_text, keywords)

                jobs.append(JobListing(
                    title=job_title_text,
                    company=company_text,
                    salary=salary_text,
                    city=city_text,
                    experience=exp_text,
                    education=edu_text,
                    tags=tags,
                    url=url,
                    match_score=match,
                ))
            except Exception as e:
                logger.debug("解析卡片失败: %s", e)
                continue

    except Exception as e:
        logger.error("搜索失败: %s", e)
    finally:
        page.close()

    jobs.sort(key=lambda j: j.match_score, reverse=True)
    return jobs[:limit]
