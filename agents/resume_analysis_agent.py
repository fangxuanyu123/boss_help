"""简历分析 Agent - 分析用户简历，提取结构化信息，识别薄弱环节"""
from typing import Dict, Any
from openai import OpenAI
from config import LLM_API_KEY, LLM_BASE_URL, LLM_MODEL_NAME
from models.resume import Resume


class ResumeAnalysisAgent:
    """简历分析智能体"""

    def __init__(self):
        self.client = OpenAI(api_key=LLM_API_KEY, base_url=LLM_BASE_URL)
        self.model = LLM_MODEL_NAME

    def analyze(self, resume: Resume) -> Dict[str, Any]:
        """分析简历并返回结构化分析与薄弱环节"""
        prompt = f"""你是一位资深的 HR 顾问和简历优化专家。请分析以下简历，完成以下任务：

1. **结构化提取**: 从原始文本中提取结构化的简历信息
2. **优势分析**: 指出该简历的亮点和优势
3. **薄弱环节**: 指出该简历的不足之处和改进空间
4. **改进建议**: 针对每个薄弱环节给出具体的改进建议

简历原始文本：
```
{resume.raw_text}
```

请以 JSON 格式返回，格式如下：
{{
    "structured": {{
        "name": "姓名",
        "title": "求职意向",
        "summary": "个人总结",
        "education": [{{"school": "", "degree": "", "major": ""}}],
        "skills": [{{"category": "", "items": []}}],
        "work_experiences": [{{"company": "", "position": "", "duration": "", "key_achievements": []}}],
        "projects": [{{"name": "", "role": "", "description": "", "tech_stack": []}}]
    }},
    "strengths": ["优势1", "优势2"],
    "weaknesses": [
        {{"aspect": "薄弱方面", "detail": "具体描述", "suggestion": "改进建议"}}
    ],
    "overall_score": 7.5,
    "key_improvements": ["最重要的3个改进点"]
}}
"""

        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": "你是一位资深的简历优化专家，擅长分析简历并提供结构化反馈。"},
                {"role": "user", "content": prompt},
            ],
            response_format={"type": "json_object"},
            temperature=0.3,
        )

        import json
        result = json.loads(response.choices[0].message.content)
        return result
