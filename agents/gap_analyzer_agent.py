"""差距分析 Agent - 对比简历与岗位画像，识别差距和对齐点"""
from typing import Dict, Any, Optional
import json
from openai import OpenAI
from config import LLM_API_KEY, LLM_BASE_URL, LLM_MODEL_NAME
from models.resume import Resume
from models.job import JobRequirement


class GapAnalyzerAgent:
    """简历-岗位差距分析智能体"""

    def __init__(self):
        self.client = OpenAI(api_key=LLM_API_KEY, base_url=LLM_BASE_URL)
        self.model = LLM_MODEL_NAME

    def analyze(
        self,
        resume: Resume,
        job: JobRequirement,
        resume_analysis: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """对比简历与岗位画像，输出差距分析"""
        # 如果提供了 resume_analysis，将其作为上下文
        analysis_context = ""
        if resume_analysis:
            strengths = resume_analysis.get("strengths", [])
            weaknesses = resume_analysis.get("weaknesses", [])
            if strengths:
                analysis_context += "\n【简历已有优势】\n" + "\n".join(f"- {s}" for s in strengths)
            if weaknesses:
                analysis_context += "\n【简历已知薄弱点】\n" + "\n".join(
                    f"- {w.get('aspect', '')}: {w.get('detail', '')}" for w in weaknesses
                )

        prompt = f"""你是一位资深的招聘和简历优化专家。请对比以下简历和岗位要求，进行深度分析。

=== 求职者简历 ===
{resume.to_text()}
{analysis_context}

=== 目标岗位画像 ===
{job.to_text()}

请从以下维度分析，以 JSON 格式返回：

1. **implicit_skills [最关键的步骤]**: 从简历中的项目经历、工作经历、实习经历的描述文字中，**深入推断**求职者实际掌握但未在技能列表中显式写出的技能。这是最重要的分析步骤！
   - 例如：项目提到"基于epoll实现高并发服务器" → 推断：C++、网络编程、多线程、Linux系统编程、TCP/IP协议、性能优化、系统调优
   - 例如：经历提到"使用Redis做缓存层" → 推断：Redis、缓存策略、NoSQL、高可用设计
   - 例如：经历提到"编写Shell脚本自动化部署" → 推断：Shell脚本、Linux、自动化运维、CI/CD意识
   - 请深入阅读每一条项目/工作描述，推断所有隐含的技术能力和知识点

2. **keyword_match**: 综合显式和隐式技能，与岗位关键词进行匹配
   - matched: 显式列出或从经历中推断出的匹配关键词
   - present_but_buried: 简历的经历描述中提到但不够突出的关键词
   - missing: 确实缺失且无法从经历中推断的关键词

3. **alignment_points**: 简历中与岗位高度匹配的经历和技能

4. **gaps**: 简历与岗位有差距的方面（不要建议编造经历）

5. **restructure_plan**: 简历内容重组的建议

6. **summary_rewrite_direction**: 个人总结的改写方向

返回 JSON：
{{
    "implicit_skills": [
        {{"skill": "技能名", "evidence": "从简历哪段经历推断出的", "category": "技能类别"}}
    ],
    "keyword_match": {{
        "matched": ["匹配的关键词（包括显性和推断的）"],
        "present_but_buried": ["有但不突出的关键词"],
        "missing": ["确实缺失的关键词"]
    }},
    "alignment_points": [
        {{"resume_item": "简历中的经历/技能", "job_requirement": "对应的岗位要求", "action": "如何突出/加强"}}
    ],
    "gaps": [
        {{"aspect": "差距方面", "current_state": "当前状态", "optimization": "如何通过重写弥补（不编造经历）"}}
    ],
    "restructure_plan": [
        {{"section": "简历板块", "suggested_change": "调整建议"}}
    ],
    "summary_rewrite_direction": "个人总结改写方向",
    "priority_actions": ["优先级最高的3个优化动作"]
}}
"""
        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": "你是一位资深的简历优化专家。你必须从项目经历和工作经历的描述中深入推断求职者的真实技能，不要仅凭技能列表做表面判断。深入阅读每一条经历描述，推断所有隐含的技术能力和知识点。"},
                {"role": "user", "content": prompt},
            ],
            response_format={"type": "json_object"},
            temperature=0.3,
        )

        return json.loads(response.choices[0].message.content)
