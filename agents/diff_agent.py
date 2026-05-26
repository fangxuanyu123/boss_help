"""DiffAgent —— 分析原始简历和优化建议，生成精确定位的手术式改动清单"""
from typing import Dict, Any
import json
from openai import OpenAI
from config import LLM_API_KEY, LLM_BASE_URL, LLM_MODEL_NAME
from models.resume import Resume, DiffResult, DiffChange, DiffAction
from models.job import JobRequirement


class DiffAgent:
    """生成手术式改动清单。

    不输出完整简历，只输出 DiffResult —— 每条改动精确定位到 target 路径，
    附带原文和改写后文字。DiffApplier 负责机械执行。
    """

    def __init__(self):
        self.client = OpenAI(api_key=LLM_API_KEY, base_url=LLM_BASE_URL)
        self.model = LLM_MODEL_NAME

    def generate_diff(
        self,
        original_resume: Resume,
        suggestions: Dict[str, Any],
        job: JobRequirement,
        uncovered_gaps: list | None = None,
        critique: str | None = None,
    ) -> DiffResult:
        """生成改动清单"""
        suggestion_text = ""
        for opt in suggestions.get("content_optimizations", []):
            suggestion_text += f"- [{opt.get('section', '')}] {opt.get('suggestion', '')}\n"
            if opt.get("example"):
                suggestion_text += f"  示例: {opt.get('example', '')}\n"

        keywords = ", ".join(suggestions.get("keywords_to_add", []))

        uncovered_text = ""
        if uncovered_gaps:
            uncovered_text = "\n=== 上一轮匹配后仍未覆盖的关键差距（本轮必须重点处理）===\n"
            for g in uncovered_gaps:
                uncovered_text += f"- 差距: {g.get('gap', '')}\n"
                uncovered_text += f"  建议: {g.get('suggestion_for_diff', '')}\n"

        system_content = (
            "你是一位精准的简历优化专家。你的任务是给出手术式的精确定位修改，"
            "而非重写整份简历。你必须为每处修改提供原文证据和改后文字，"
            "使得 DiffApplier 能机械应用你的改动。未在改动清单中的内容将被完整保留。"
            "遵守原则：少改优于多改，能保持不变的部分坚决不改。"
        )
        if critique:
            system_content += f"\n\n=== 上一轮输出的改进反馈 ===\n{critique}\n请针对以上反馈，修正你上一轮的输出。"

        prompt = f"""请根据以下原始简历、优化建议和岗位要求，生成手术式改动清单。

【关键原则：少改优于多改】
- 只改那些对提升岗位匹配度有实质帮助的部分
- 原文已经足够好的条目，不要为了改而去改
- 每条改动必须有明确的 reason，说明为什么这样改

=== 原始简历（结构化） ===
{original_resume.to_text()}

=== 目标岗位 ===
{job.to_text()}

=== 优化建议 ===
整体策略: {suggestions.get('overall_strategy', '')}
需强调的关键词: {keywords}

逐项优化建议:
{suggestion_text}
{uncovered_text}

=== Few-Shot 示例（高质量改动参考） ===

以下是 3 条高质量改动示例，请模仿其精确度和理由深度：

【示例 1：STAR 法则改写职责】
输入：原文 "负责系统日常维护"
输出：
{{
    "target": "work_experiences[0].responsibilities[0]",
    "action": "rewrite",
    "original": "负责系统日常维护",
    "rewritten": "主导XX业务系统运维，保障99.9%可用性，覆盖日均50万+请求，通过自动化监控将故障响应时间从30分钟降至5分钟",
    "reason": "STAR法则改写：补充了系统规模（日均50万+请求）、量化成果（99.9%可用性）、主动贡献（故障响应优化）",
    "section_label": "工作经历-XX公司-职责1"
}}

【示例 2：补充缺失关键词】
输入：gap分析显示 Kafka 缺失，但项目描述中有使用
输出：
{{
    "target": "skills[1].items",
    "action": "append",
    "item": "Kafka",
    "reason": "gap分析显示该关键词缺失，但XX项目中实际使用了Kafka进行消息处理，补充后提升匹配度",
    "section_label": "技能-中间件"
}}

【示例 3：删除冗余表述】
输入：原文 "参与需求评审会议，记录会议纪要"
输出：
{{
    "target": "work_experiences[0].responsibilities[2]",
    "action": "delete",
    "reason": "参与需求评审是团队基础协作活动，不体现个人技术能力，删除以节省空间给更有区分度的内容",
    "section_label": "工作经历-XX公司-职责3"
}}

=== 改动清单格式 ===

返回 JSON，每条改动必须包含以下字段：

{{
    "changes": [
        {{
            "target": "目标路径（如 work_experiences[0].responsibilities[2] / skills[0].items / summary / title）",
            "action": "rewrite / append / delete / highlight / reorder",
            "original": "被改动的原文（必须和原简历一字不差，用于精确定位）",
            "rewritten": "改写后的文字（action=rewrite/highlight 时填写）",
            "item": "新增内容（action=append 时填写）",
            "reason": "为什么这样改，关联到哪条优化建议或差距",
            "section_label": "人类可读的板块名（如'工作经历-XX公司-职责2'）"
        }}
    ],
    "unchanged_summary": "一句话说明为什么其他部分没有改动",
    "estimated_impact": "预估这些改动对匹配度提升的效果"
}}

【target 路径规则】
- summary, title: 直接写字段名，action 用 rewrite
- work_experiences[N].responsibilities[M]: N是经历序号从0开始，M是职责序号从0开始，action 用 rewrite
- work_experiences[N].achievements[M]: 同上
- projects[N].highlights[M]: 同上
- projects[N].tech_stack: 追加单个技术，action 必须用 append，item 填技术名
- skills[N].items: N是技能类别序号，追加单个技能，action 必须用 append，item 填技能名
- certifications: 追加单个证书，action 必须用 append，item 填证书名
- work_experiences[N].position: 改写职位（极少使用），action 用 rewrite

【action 选择规则（重要）】
- rewrite: 用于改写已有文字，必须指定到具体条目的索引（如 responsibilities[2]）
- append: 用于向列表追加新条目，target 写到列表字段即可（如 skills[0].items 或 certifications），不需要子索引
- delete: 用于删除某条，必须指定到具体索引
- highlight: 同 rewrite，用于把已有但埋没的内容改写得更突出
- reorder: 仅记录"建议调序"提示，不实际修改

【original 字段要求】
- 必须和被改动的原文严格一致，用于 DiffApplier 精确匹配定位
- 如果是 append action，original 可以为空
- 如果是 reorder action，original 写要调整顺序的条目原文

【数量限制】
- 改动总数建议 5-12 条
- 不要为了凑数去改已经写得很好的内容
- 如果确实不需要改那么多，2-3条高质量改动远比10条无意义改动更好

只输出 JSON，不要额外文字。"""
        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": system_content},
                {"role": "user", "content": prompt},
            ],
            response_format={"type": "json_object"},
            temperature=0.2,
        )

        data = json.loads(response.choices[0].message.content)
        changes = []
        for c in data.get("changes", []):
            changes.append(DiffChange(
                target=c.get("target", ""),
                action=DiffAction(c.get("action", "rewrite")),
                original=c.get("original", ""),
                rewritten=c.get("rewritten", ""),
                item=c.get("item", ""),
                reason=c.get("reason", ""),
                section_label=c.get("section_label", ""),
            ))
        return DiffResult(
            changes=changes,
            unchanged_summary=data.get("unchanged_summary", ""),
            estimated_impact=data.get("estimated_impact", ""),
        )
