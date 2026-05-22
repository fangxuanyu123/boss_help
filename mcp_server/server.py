"""MCP Server —— 提供岗位搜索工具，支持 stdio 传输"""
import logging
import asyncio
from mcp.server import Server, NotificationOptions
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent

from mcp_server.job_search import search_jobs

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

        lines = [f"## 岗位搜索结果: {title}", f"关键词: {', '.join(keywords)}", f"共找到 {len(jobs)} 个岗位\n"]
        for i, j in enumerate(jobs, 1):
            lines.append(f"### {i}. {j.title}")
            lines.append(f"- 公司: {j.company}  [{j.source}]")
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
