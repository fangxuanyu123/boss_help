"""面试准备 Agent —— 基于 Pipeline 差距分析 + 真实面经生成针对性面试Q&A"""
import json
import logging
from openai import OpenAI
from config import LLM_API_KEY, LLM_BASE_URL, LLM_MODEL_NAME

logger = logging.getLogger(__name__)


class InterviewPrepAgent:
    """基于简历优化过程的差距分析 + 牛客/CSDN真实面经，生成面试准备材料。"""

    def __init__(self):
        self.client = OpenAI(api_key=LLM_API_KEY, base_url=LLM_BASE_URL)
        self.model = LLM_MODEL_NAME

    def _fetch_mianjing(self, tech_keywords: list[str]) -> list[dict]:
        """从牛客网和CSDN搜索真实面经"""
        try:
            from mcp_server.mianjing_search import search_mianjing
            items = search_mianjing(tech_keywords + ["面经", "面试"], limit=10)
            result = []
            for item in items:
                result.append({
                    "title": item.title,
                    "url": item.url,
                    "source": item.source,
                })
            logger.info("获取到 %d 条真实面经参考", len(result))
            return result
        except Exception as e:
            logger.warning("面经搜索失败，使用纯LLM生成: %s", e)
            return []

    def generate(
        self,
        gap_analysis: dict,
        suggestions: dict,
        match_result: dict,
        tech_keywords: list[str],
        job_title: str,
    ) -> dict:
        """生成面试准备材料。

        Args:
            gap_analysis: GapAnalyzerAgent 的输出
            suggestions: OptimizationAgent 的输出
            match_result: JobMatchingAgent 的输出
            tech_keywords: 岗位技术关键词
            job_title: 目标岗位名

        Returns:
            {
                "technical_qa": [{"topic":"", "question":"", "answer_hint":""}],
                "gap_qa": [{"gap":"", "question":"", "suggested_answer":""}],
                "system_design": [{"scenario":"", "key_points":[]}],
                "behavioral": [{"situation":"", "question":"", "prep_tip":""}],
                "last_minute_tips": [""],
                "estimated_prep_time": ""
            }
        """
        # 提取关键信息
        missing_kw = match_result.get("keyword_match", {}).get("missing", [])
        uncovered = match_result.get("uncovered_gaps", [])
        gaps = gap_analysis.get("gaps", [])
        weaknesses = gap_analysis.get("weaknesses", [])

        # 搜索真实面经
        real_mianjing = self._fetch_mianjing(tech_keywords)
        mianjing_ref = ""
        if real_mianjing:
            mianjing_ref = "\n=== 牛客网/CSDN 真实面经参考（请结合这些真实面经生成更精准的问题） ===\n"
            for m in real_mianjing:
                mianjing_ref += f"- [{m['source']}] {m['title']}\n"

        prompt = f"""你是一位资深的技术面试官和面试导师。一位求职者正在准备「{job_title}」的面试，请根据以下简历分析结果和真实面经参考，生成针对性的面试准备材料。

=== 目标岗位 ===
{job_title}

=== 技术关键词（需要准备的方向） ===
{', '.join(tech_keywords)}

=== 技能差距（面试中可能被追问的弱项） ===
{json.dumps([
    {"aspect": g.get("aspect", ""), "current": g.get("current_state", "")}
    for g in gaps
], ensure_ascii=False, indent=2)}

=== 岗位要求中未覆盖的关键词 ===
{json.dumps(missing_kw, ensure_ascii=False)}

=== 简历优化后仍未完全覆盖的差距 ===
{json.dumps([
    {"gap": u.get("gap", ""), "suggestion": u.get("suggestion_for_diff", "")}
    for u in uncovered
], ensure_ascii=False, indent=2)}

=== 优化策略 ===
{suggestions.get('overall_strategy', '')}
{mianjing_ref}
=== 生成要求 ===

请生成面试准备材料，内容要「精准、有深度、针对这个候选人的具体情况」。
如果上面提供了真实面经参考，请综合这些面经中常见的考察方向来生成问题——真实面经比凭空想象的问题更有价值。

返回 JSON：

{{
    "technical_qa": [
        {{
            "topic": "技术主题（如 Kafka 消息队列）",
            "question": "面试官可能这样问...",
            "answer_hint": "你应该这样回答的方向..."
        }}
    ],
    "gap_qa": [
        {{
            "gap": "从简历差距分析中发现的问题",
            "question": "面试官会这样追问...",
            "suggested_answer": "建议的回答思路（基于候选人已有经验，如何扬长避短）"
        }}
    ],
    "system_design": [
        {{
            "scenario": "系统设计场景",
            "key_points": ["关键设计要点1", "要点2"]
        }}
    ],
    "behavioral": [
        {{
            "situation": "行为面试场景",
            "question": "具体的问题",
            "prep_tip": "准备的要点"
        }}
    ],
    "last_minute_tips": ["面试前最后的建议"],
    "estimated_prep_time": "建议准备时间"
}}

【原则】
- technical_qa: 聚焦 tech_keywords 和 missing_kw，生成 5-8 个高频技术问题
- gap_qa: 聚焦候选人简历中暴露的短板（gaps），生成 3-5 个针对性问题，帮助候选人准备如何应对追问
- system_design: 如果岗位是高级/架构级别，生成 2-3 个系统设计场景
- behavioral: 基于 gaps 中可能暴露的经验短板，生成 2-3 个行为面试问题
- 每个问题要有深度，不要问"Java是什么"这种初级问题
- answer_hint/suggested_answer 要有实际指导价值，不是空话"""

        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": "你是一位资深技术面试官，为求职者提供精准的面试准备指导。你了解面试官的真实关注点，给出的建议具体、可操作、有洞察力。"},
                {"role": "user", "content": prompt},
            ],
            response_format={"type": "json_object"},
            temperature=0.4,
        )

        result = json.loads(response.choices[0].message.content)
        result["_real_mianjing"] = real_mianjing  # 附加面经链接供前端展示
        return result
