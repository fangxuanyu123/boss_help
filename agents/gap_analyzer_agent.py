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

        prompt = f"""你是一位资深的招聘和简历优化专家。你的任务是对比简历与目标岗位，找出**岗位匹配度上的真实差距**，给出精准、可执行的优化建议。

=== 求职者简历 ===
{resume.to_text()}
{analysis_context}

=== 目标岗位画像 ===
{job.to_text()}

=== 分析原则（严格遵守） ===

0. **先给总体判断**：一句话总结简历与岗位的匹配程度。不预判"缺乏XX"，而是客观描述"简历侧重XX，岗位要求XX，最大交叉点在XX"。

1. **行业上下文推断（重要）**：
   - 当技能的「技能列表」中有某个技能，且求职者的工作/实习公司或项目属于该技能高度相关的行业时，**不应判定该技能缺失**，应归类为"经历中有但描述未突出"
   - 例如：在自动驾驶公司实习 → 行业重度使用 ROS → 技能列表有 ROS → 不要判 ROS 缺失，而是建议"在经历描述中显式提及 ROS 的使用"

2. **implicit_skills（隐式技能推断）**：
   - 从工作/项目经历的**描述文字**中推断求职者实际掌握但**未在技能列表中显式列出**的技能
   - **严禁**将技能列表中已有的技能列为"隐式技能"
   - 每条必须有具体的经历描述作为证据
   - **精选 8-12 条**，只保留对未来雇主有说服力的

3. **keyword_match（关键词匹配）**：
   - 综合显式技能+隐式技能+行业上下文，与岗位关键词逐一对照
   - matched：有明确证据或行业上下文支撑的匹配
   - present_but_buried：技能列表有或行业可推断，但经历描述不够突出
   - missing：确实缺失，且无法从行业上下文或现有经历推断
   - **内部一致性检查（强制）**：如果一个关键词出现在某个 alignment_point 的 resume_item 中，它**绝对不能**同时出现在 missing 列表

4. **alignment_points（对齐点）**：
   - 找出简历中与岗位要求可直接对应经历/技能
   - 给具体的"如何在简历中突出"的建议

5. **gaps（差距分析——核心产出）**：
   - 只分析**岗位匹配上的差距**，不重复简历本身的质量问题
   - 区分两类差距：
     · **写作层面**（能力有但描述不到位）→ optimization 聚焦如何重写描述来体现
     · **能力层面**（确实缺少某项核心经验）→ 坦诚说明，但不要建议"去学""去做个新项目"（这超出了简历优化的范围）
   - optimization 的目标是**优化简历呈现**，不是规划用户的学习路线

6. **restructure_plan（内容重组建议）**：
   - 基于岗位需求，给出简历内容如何重新排列组合、哪些板块提前/加重、哪些精简
   - **严禁**建议"新增个人总结板块"（简洁简历不需要，除非特别需要新增）
   - **严禁**建议删除与对齐点或 matched 关键词相关的已有内容

7. **summary_rewrite_direction（总结改写方向）**：
   - 只针对「如果简历有一个定位性的一句话」，给出这个句子的方向建议
   - **严禁**写成"建议增加一段个人总结"——只需给出那句话本身的内容方向即可

8. **priority_actions（优先级动作）**：
   - 不超过 3 条，按紧急程度排序
   - 每条必须是**简历优化**的具体动作（重写某段描述、调整某段经历的重点、显式补充某个关键词等）
   - **不要建议用户去学新技能、做新项目**——这不属于简历优化的范畴
   - **不要加序号前缀**，直接写动作内容

返回 JSON：
{{
    "verdict": "一句话总体判断",
    "implicit_skills": [
        {{"skill": "技能名", "evidence": "简历经历中的具体描述", "category": "技能类别"}}
    ],
    "keyword_match": {{
        "matched": [],
        "present_but_buried": [],
        "missing": []
    }},
    "alignment_points": [
        {{"resume_item": "简历中的具体经历/技能", "job_requirement": "对应的岗位要求", "action": "如何在简历中突出这个对齐点"}}
    ],
    "gaps": [
        {{"aspect": "差距方面", "current_state": "当前状态", "optimization": "具体的弥补方案（不编造经历）"}}
    ],
    "restructure_plan": [
        {{"section": "简历板块", "suggested_change": "重组建议（基于现有内容）"}}
    ],
    "summary_rewrite_direction": "总结改写方向",
    "priority_actions": ["具体动作1", "具体动作2", "具体动作3"]
}}
"""
        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": "你是一位资深招聘专家，为各行业求职者做岗位匹配分析。你的核心能力：能结合行业上下文做判断——在自动驾驶公司实习意味着大概率接触过ROS，做ADAS意味着涉及传感器融合，不被'经历描述里没出现这个词'所蒙蔽。你的分析前后一致，不会把一个技能同时列为'对齐点'和'缺失'。你只做简历优化，不建议用户去学新技能。你从不说正确的废话。"},
                {"role": "user", "content": prompt},
            ],
            response_format={"type": "json_object"},
            temperature=0.3,
        )

        return json.loads(response.choices[0].message.content)
