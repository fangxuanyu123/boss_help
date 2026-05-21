"""CoherenceReviewer —— 审查修改后简历的全文连贯性"""
from typing import Dict, Any
import json
from openai import OpenAI
from config import LLM_API_KEY, LLM_BASE_URL, LLM_MODEL_NAME
from models.resume import Resume, DiffChange, CoherenceReview


class CoherenceReviewer:
    """审查 Diff 应用后的全文连贯性"""

    def __init__(self):
        self.client = OpenAI(api_key=LLM_API_KEY, base_url=LLM_BASE_URL)
        self.model = LLM_MODEL_NAME

    def review(self, modified_resume: Resume, changes_applied: list) -> CoherenceReview:
        """审查全文连贯性"""
        annotated = modified_resume.to_text()
        annotation_note = "\n\n=== 以下内容被修改过（已标注在简历文本中） ===\n"
        for i, c in enumerate(changes_applied):
            annotation_note += f"[改动{i+1}] {c.section_label}: {c.action.value} → {c.rewritten or c.item}\n"

        system_content = (
            "你是一位简历审校专家。你的任务不是评判简历写得好不好，"
            "而是检查修改后的简历是否存在**逻辑矛盾、表述不一致、衔接突兀**的问题。"
            "Prompt 已经管住了'改了什么'，你需要关注的是'改完之后读起来是否自然'。"
        )

        prompt = f"""请审阅以下修改后的简历，检查全文连贯性。

{annotated}
{annotation_note}

=== 检查维度 ===

1. **改动衔接**：修改后的措辞与相邻未改动的部分是否自然过渡？
   - 例如：前半句改成了高级技术术语，后半句还是原来简单的表述，是否有突兀感？

2. **表述一致性**：同一概念在不同位置是否用了一致的方式描述？
   - 例如：skill列表补充了"分布式系统"，但在工作经历中还是只说"后端系统"

3. **Summary-正文对齐**：如果 Summary 被修改了，它是否准确反映了正文中的经历？

4. **无事实矛盾**：修改后是否产生了自相矛盾？

返回 JSON：
{{
    "coherence_score": 8.5,
    "passed": true,
    "issues": [],
    "patches": []
}}

如果 passed=false（coherence_score < 7），patches 里给出修补用的 DiffChange（格式与输入一致）。
评分 >= 8.0: 全文流畅自然。6.0-7.9: 有小瑕疵但不影响理解。<6.0: 存在明显矛盾或衔接问题。"""
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
        patches = []
        for p in data.get("patches", []):
            from models.resume import DiffAction as DA
            patches.append(DiffChange(
                target=p.get("target", ""),
                action=DA(p.get("action", "rewrite")),
                original=p.get("original", ""),
                rewritten=p.get("rewritten", ""),
                item=p.get("item", ""),
                reason=p.get("reason", ""),
                section_label=p.get("section_label", ""),
            ))
        return CoherenceReview(
            coherence_score=float(data.get("coherence_score", 10.0)),
            passed=data.get("passed", True),
            issues=data.get("issues", []),
            patches=patches,
        )
