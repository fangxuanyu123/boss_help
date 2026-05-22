"""岗位搜索 —— 通过搜索引擎聚合 + 直接跳转链接"""
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


def _direct_links(title: str, keywords: list[str], city: str) -> list[JobListing]:
    """生成各大招聘网站的直接搜索链接，不爬取，100%可靠"""
    search_term = title
    if keywords:
        search_term += " " + " ".join(keywords[:3])
    encoded = quote(search_term)

    # Boss 直聘城市码
    boss_city_codes = {
        "北京": "100010000", "上海": "100020000", "广州": "100030000",
        "深圳": "100040000", "杭州": "100080000", "成都": "100090000",
        "南京": "100070000", "武汉": "100180000", "西安": "100200000",
    }
    boss_city = boss_city_codes.get(city.replace("市", ""), "100010000")

    links = [
        JobListing(
            title=f"在 Boss 直聘搜索「{search_term}」",
            company="Boss 直聘",
            city=city or "全国",
            url=f"https://www.zhipin.com/web/geek/job?query={encoded}&city={boss_city}",
            match_score=100.0,
            source="Boss直聘",
            tags=["点击打开官网搜索"],
        ),
        JobListing(
            title=f"在 51job 搜索「{search_term}」",
            company="51job",
            city=city or "全国",
            url=f"https://we.51job.com/pc/search?keyword={encoded}&searchType=2",
            match_score=100.0,
            source="51job",
            tags=["点击打开官网搜索"],
        ),
        JobListing(
            title=f"在 拉勾 搜索「{search_term}」",
            company="拉勾",
            city=city or "全国",
            url=f"https://www.lagou.com/wn/jobs?kd={encoded}&city={quote(city) if city else ''}",
            match_score=100.0,
            source="拉勾",
            tags=["点击打开官网搜索"],
        ),
        JobListing(
            title=f"在 猎聘 搜索「{search_term}」",
            company="猎聘",
            city=city or "全国",
            url=f"https://www.liepin.com/zhaopin/?key={encoded}",
            match_score=100.0,
            source="猎聘",
            tags=["点击打开官网搜索"],
        ),
    ]
    return links


def search_jobs(
    title: str,
    keywords: list[str],
    city: str = "",
    limit: int = 15,
) -> list[JobListing]:
    """搜索岗位。

    当前策略：生成各大招聘网站的精准搜索链接。用户点击即可在真实浏览器中查看。
    （国内招聘网站反爬极严，直接爬取不可靠。搜索引擎聚合和直接链接更实用。）

    Args:
        title: 岗位名称
        keywords: 技术关键词
        city: 城市（可选）
        limit: 返回数量上限
    """
    logger.info("生成岗位搜索链接: %s, city=%s, keywords=%d", title, city, len(keywords))
    links = _direct_links(title, keywords, city)

    # 再用搜索引擎增强（如果可用）
    try:
        extra = _bing_search(title, keywords, city, max(0, limit - len(links)))
        links.extend(extra)
    except Exception as e:
        logger.debug("搜索引擎增强跳过: %s", e)

    return links[:limit]


def _bing_search(title: str, keywords: list[str], city: str, limit: int) -> list[JobListing]:
    """用 Bing 搜索聚合岗位信息（可选增强）"""
    from playwright.sync_api import sync_playwright

    query = f"{title} {' '.join(keywords[:3])} 招聘"
    if city:
        query += f" {city}"
    search_url = f"https://www.bing.com/search?q={quote(query)}&setlang=zh-cn"

    pw = sync_playwright().start()
    try:
        browser = pw.chromium.launch(
            headless=True,
            args=["--no-sandbox", "--disable-dev-shm-usage"],
        )
        ctx = browser.new_context(
            viewport={"width": 1920, "height": 1080},
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
            locale="zh-CN",
        )
        page = ctx.new_page()
        page.goto(search_url, timeout=20000, wait_until="domcontentloaded")
        page.wait_for_timeout(2000)

        # Bing 搜索结果
        results = page.query_selector_all("li.b_algo h2 a, div.b_title h2 a")
        snippets = page.query_selector_all("li.b_algo .b_caption p, div.b_caption p")

        jobs = []
        for i, r in enumerate(results[:limit]):
            try:
                t = r.inner_text().strip()
                url = r.get_attribute("href") or ""
                snippet = snippets[i].inner_text().strip() if i < len(snippets) else ""
                if not t or "招聘" not in t and "岗位" not in t:
                    continue
                jobs.append(JobListing(
                    title=t,
                    company="",
                    salary="",
                    city="",
                    url=url,
                    match_score=50.0,
                    source="Bing",
                    tags=[snippet[:80]] if snippet else [],
                ))
            except Exception:
                continue

        return jobs
    except Exception as e:
        logger.debug("Bing 搜索跳过: %s", e)
        return []
    finally:
        try:
            browser.close()
        except Exception:
            pass
        try:
            pw.stop()
        except Exception:
            pass
