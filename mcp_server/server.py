"""MCP Server —— 提供面试准备工具，支持 stdio 传输"""
import logging
import asyncio
from mcp.server import Server, NotificationOptions
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent

from agents.interview_prep_agent import InterviewPrepAgent

logger = logging.getLogger(__name__)

server = Server("boss-help-interview-prep")


@server.list_tools()
async def list_tools() -> list[Tool]:
    return [
        Tool(
            name="generate_interview_prep",
            description="基于简历分析结果生成针对性面试准备材料。输入简历与岗位的差距分析和技术关键词，输出技术问答、系统设计题、行为面试题和考前建议。",
            inputSchema={
                "type": "object",
                "properties": {
                    "job_title": {
                        "type": "string",
                        "description": "目标岗位名称"
                    },
                    "tech_keywords": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "岗位技术关键词列表"
                    },
                    "missing_keywords": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "简历缺失的技术关键词"
                    },
                    "gaps": {
                        "type": "array",
                        "items": {"type": "object"},
                        "description": "差距分析中的gaps列表"
                    },
                    "uncovered_gaps": {
                        "type": "array",
                        "items": {"type": "object"},
                        "description": "未覆盖的差距列表"
                    },
                    "overall_strategy": {
                        "type": "string",
                        "description": "整体优化策略"
                    },
                },
                "required": ["job_title", "tech_keywords"],
            },
        )
    ]


@server.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    if name == "generate_interview_prep":
        job_title = arguments.get("job_title", "")
        tech_keywords = arguments.get("tech_keywords", [])
        missing_kw = arguments.get("missing_keywords", [])
        gaps = arguments.get("gaps", [])
        uncovered = arguments.get("uncovered_gaps", [])
        strategy = arguments.get("overall_strategy", "")

        agent = InterviewPrepAgent()
        result = agent.generate(
            gap_analysis={"gaps": gaps, "weaknesses": []},
            suggestions={
                "overall_strategy": strategy,
                "content_optimizations": [],
            },
            match_result={
                "keyword_match": {"missing": missing_kw},
                "uncovered_gaps": uncovered,
            },
            tech_keywords=tech_keywords,
            job_title=job_title,
        )

        lines = [f"## {job_title} 面试准备材料\n"]

        if result.get("technical_qa"):
            lines.append("### 技术问答")
            for q in result["technical_qa"]:
                lines.append(f"**{q.get('topic', '')}**")
                lines.append(f"问: {q.get('question', '')}")
                lines.append(f"答: {q.get('answer_hint', '')}")
                lines.append("")

        if result.get("gap_qa"):
            lines.append("### 短板应对")
            for q in result["gap_qa"]:
                lines.append(f"**{q.get('gap', '')}**")
                lines.append(f"问: {q.get('question', '')}")
                lines.append(f"建议: {q.get('suggested_answer', '')}")
                lines.append("")

        if result.get("system_design"):
            lines.append("### 系统设计")
            for s in result["system_design"]:
                lines.append(f"**{s.get('scenario', '')}**")
                for p in s.get("key_points", []):
                    lines.append(f"  - {p}")
                lines.append("")

        if result.get("behavioral"):
            lines.append("### 行为面试")
            for b in result["behavioral"]:
                lines.append(f"**{b.get('situation', '')}**")
                lines.append(f"问: {b.get('question', '')}")
                lines.append(f"准备: {b.get('prep_tip', '')}")
                lines.append("")

        if result.get("last_minute_tips"):
            lines.append("### 考前提醒")
            for t in result["last_minute_tips"]:
                lines.append(f"- {t}")
            lines.append("")

        if result.get("estimated_prep_time"):
            lines.append(f"建议准备时间: {result['estimated_prep_time']}")

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
