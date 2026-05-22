# MCP 岗位搜索 实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 新增 MCP Server 提供岗位搜索工具，Pipeline 完成后自动基于优化简历搜索匹配岗位

**Architecture:** MCP Server 独立运行（stdio transport，可被任何 MCP 客户端调用），核心搜索逻辑在共享模块 `job_search.py` 中，Streamlit 直接 import 使用，同时 MCP Server 暴露相同能力

**Tech Stack:** Python 3.10+, mcp SDK, Playwright, Streamlit

---

### Task 1: MCP Server + 核心搜索逻辑

**Files:**
- Create: `mcp_server/__init__.py`
- Create: `mcp_server/browser.py`
- Create: `mcp_server/job_search.py`
- Create: `mcp_server/server.py`

- [ ] **Step 1: 创建 `mcp_server/__init__.py`**

```python
"""MCP Server —— 岗位搜索 + 面试准备工具"""
```

- [ ] **Step 2: 创建 `mcp_server/browser.py`**

```python
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
```

- [ ] **Step 3: 创建 `mcp_server/job_search.py`**

```python
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

    # 构建搜索 URL
    query = title
    if keywords:
        query += " " + " ".join(keywords[:3])  # Top 3 关键词辅助搜索

    if city:
        search_url = f"https://www.zhipin.com/web/geek/job?query={query}&city={city}"
    else:
        search_url = f"https://www.zhipin.com/web/geek/job?query={query}"

    logger.info("搜索岗位: %s (city=%s)", title, city or "不限")

    page = get_page()
    jobs: list[JobListing] = []

    try:
        page.goto(search_url, timeout=30000, wait_until="domcontentloaded")
        time.sleep(3)  # 等待动态内容加载

        # 解析职位列表
        job_cards = page.query_selector_all("li.job-card-wrapper")
        if not job_cards:
            job_cards = page.query_selector_all("li.job-card-box")
        if not job_cards:
            job_cards = page.query_selector_all("[class*='job-card']")

        for card in job_cards[:limit * 2]:  # 多抓一些，后面筛选
            try:
                # 岗位名
                title_el = card.query_selector(".job-name")
                if not title_el:
                    title_el = card.query_selector("[class*='job-name']")
                job_title_text = title_el.inner_text().strip() if title_el else ""

                # 薪资
                salary_el = card.query_selector(".salary")
                if not salary_el:
                    salary_el = card.query_selector("[class*='salary']")
                salary_text = salary_el.inner_text().strip() if salary_el else ""

                # 公司
                company_el = card.query_selector(".company-name")
                if not company_el:
                    company_el = card.query_selector("[class*='company-name']")
                company_text = company_el.inner_text().strip() if company_el else ""

                # 标签（经验/学历等）
                tag_els = card.query_selector_all(".tag-list li")
                if not tag_els:
                    tag_els = card.query_selector_all("[class*='tag']")
                tags = [t.inner_text().strip() for t in tag_els if t.inner_text().strip()]

                # 城市
                city_text = ""
                area_el = card.query_selector(".job-area")
                if not area_el:
                    area_el = card.query_selector("[class*='area']")
                if area_el:
                    city_text = area_el.inner_text().strip()

                # 链接
                link_el = card.query_selector("a")
                url = ""
                if link_el:
                    href = link_el.get_attribute("href")
                    if href:
                        url = "https://www.zhipin.com" + href if href.startswith("/") else href

                # 经验/学历从 tags 提取
                exp_text = tags[0] if len(tags) > 0 else ""
                edu_text = tags[1] if len(tags) > 1 else ""

                if not job_title_text or not company_text:
                    continue

                # 匹配度预计算（用标题+标签，因为还没点进详情）
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

    # 按匹配度降序，Top N
    jobs.sort(key=lambda j: j.match_score, reverse=True)
    return jobs[:limit]
```

- [ ] **Step 4: 创建 `mcp_server/server.py`**

```python
"""MCP Server —— 提供岗位搜索工具，支持 stdio 传输"""
import logging
import asyncio
from mcp.server import Server, NotificationOptions
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent

from mcp_server.job_search import search_jobs, JobListing

logger = logging.getLogger(__name__)

server = Server("boss-help-job-search")


@server.list_tools()
async def list_tools() -> list[Tool]:
    return [
        Tool(
            name="search_jobs",
            description="基于简历信息搜索匹配的招聘岗位。输入求职意向和技术关键词，返回匹配的岗位列表。",
            inputSchema={
                "type": "object",
                "properties": {
                    "title": {
                        "type": "string",
                        "description": "求职意向岗位名称，如 高级Java开发工程师"
                    },
                    "keywords": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "技术关键词列表，如 ['Java', 'Spring Cloud', 'K8s']"
                    },
                    "city": {
                        "type": "string",
                        "description": "目标城市，如 深圳、北京。留空表示不限"
                    },
                    "limit": {
                        "type": "integer",
                        "description": "返回数量上限，默认15",
                        "default": 15
                    },
                },
                "required": ["title", "keywords"],
            },
        )
    ]


@server.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    if name == "search_jobs":
        title = arguments.get("title", "")
        keywords = arguments.get("keywords", [])
        city = arguments.get("city", "")
        limit = arguments.get("limit", 15)

        jobs = search_jobs(title=title, keywords=keywords, city=city, limit=limit)

        # 格式化输出
        lines = [f"## 岗位搜索结果: {title}", f"关键词: {', '.join(keywords)}", f"共找到 {len(jobs)} 个岗位\n"]
        for i, j in enumerate(jobs, 1):
            lines.append(f"### {i}. {j.title}")
            lines.append(f"- 公司: {j.company}")
            lines.append(f"- 薪资: {j.salary}")
            lines.append(f"- 城市: {j.city}")
            lines.append(f"- 经验/学历: {j.experience} | {j.education}")
            lines.append(f"- 匹配度: {j.match_score}%")
            if j.url:
                lines.append(f"- 链接: {j.url}")
            lines.append("")

        return [TextContent(type="text", text="\n".join(lines))]

    raise ValueError(f"未知工具: {name}")


async def main():
    async with stdio_server() as (read, write):
        await server.run(
            read,
            write,
            server.create_initialization_options(
                notification_options=NotificationOptions(),
            ),
        )


def run():
    asyncio.run(main())


if __name__ == "__main__":
    run()
```

- [ ] **Step 5: 验证 MCP Server 可以启动**

Run: `python -c "from mcp_server.job_search import search_jobs; print('job_search OK')" && python -c "from mcp_server.server import server; print('server OK')"`
Expected: `job_search OK` + `server OK`

- [ ] **Step 6: Commit**

```bash
git add mcp_server/ requirements.txt
git commit -m "feat: add MCP server with job search tool (Boss直聘)"
```

---

### Task 2: Streamlit 集成 —— Step 8 + Tab 4

**Files:**
- Modify: `app.py`

- [ ] **Step 1: 新增 import 和 session state**

在 app.py 顶部新增 import：
```python
from mcp_server.job_search import search_jobs, JobListing
```

在 defaults 字典中新增：
```python
"job_listings": [],
```

- [ ] **Step 2: 在 Step 7 之后新增 Step 8**

在 `st.write("✅ PDF 生成完成")` 之后、`status.update(...)` 之前插入：

```python
                # Step 8: 岗位搜索
                st.write("🔗 搜索匹配岗位...")
                opt = st.session_state.optimized_resume
                all_skills = []
                for s in opt.skills:
                    all_skills.extend(s.items)
                search_title = opt.title or job_title
                search_keywords = list(set(all_skills))[:12]  # 去重，最多12个
                try:
                    st.session_state.job_listings = search_jobs(
                        title=search_title,
                        keywords=search_keywords,
                        limit=15,
                    )
                    st.write(f"✅ 找到 {len(st.session_state.job_listings)} 个匹配岗位")
                except Exception as e:
                    st.warning(f"岗位搜索暂不可用: {e}")
                    st.session_state.job_listings = []
```

- [ ] **Step 3: 在结果展示区域新增 Tab 4**

在 `tabs[2]`（Tab 3 PDF 下载）的 `with tabs[2]:` 块之后新增：

```python
    # ---- Tab 4: 岗位匹配 ----
    with tabs[3]:
        st.subheader("🔗 匹配岗位")
        listings = st.session_state.get("job_listings", [])
        if not listings:
            st.info("完成简历优化后，将自动搜索匹配岗位。")
        else:
            opt = st.session_state.optimized_resume
            all_skills = []
            for s in opt.skills:
                all_skills.extend(s.items)
            keywords_str = " / ".join(all_skills[:8])
            st.caption(f"搜索词: **{opt.title or job_title}** | 技能: {keywords_str}")

            for i, job in enumerate(listings):
                score_color = "green" if job.match_score >= 70 else "orange" if job.match_score >= 50 else "red"
                with st.container(border=True):
                    col_l, col_r = st.columns([3, 1])
                    with col_l:
                        st.markdown(f"### {i+1}. {job.title}")
                        st.markdown(f"**{job.company}** | {job.salary} | {job.city}")
                        st.caption(f"{job.experience} | {job.education}")
                        if job.tags:
                            st.caption(" / ".join(job.tags))
                    with col_r:
                        st.metric("匹配度", f"{job.match_score:.0f}%")
                        if job.url:
                            st.link_button("查看详情", job.url)
```

- [ ] **Step 4: 修改 tabs 定义（从3个tab改为4个）**

找到 `tabs = st.tabs(["📊 优化预览", "🔬 分析报告", "📥 PDF下载"])`，改为：

```python
    tabs = st.tabs(["📊 优化预览", "🔬 分析报告", "📥 PDF下载", "🔗 岗位匹配"])
```

- [ ] **Step 5: 验证**

Run: `python -c "import py_compile; py_compile.compile('app.py', doraise=True); print('OK')"`
Expected: `OK`

- [ ] **Step 6: Commit**

```bash
git add app.py
git commit -m "feat: add Step 8 job search + Tab 4 job listings display"
```

---

## 自评

1. MCP Server 可独立运行：`python -m mcp_server.server`（stdio transport），任何 MCP 客户端可连接
2. Streamlit 直接 import `search_jobs`，同一进程内调用，零延迟
3. 搜索参数100%来自优化后简历，Pipeline 不重跑
4. 匹配度是纯文本命中率，不需要 LLM，速度快
