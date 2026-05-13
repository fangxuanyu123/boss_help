"""简历生成 Agent - 根据优化建议生成优化后的简历"""
from typing import Dict, Any
from openai import OpenAI
from config import LLM_API_KEY, LLM_BASE_URL, LLM_MODEL_NAME
from models.resume import Resume


class ResumeGenerationAgent:
    """简历生成智能体"""

    def __init__(self):
        self.client = OpenAI(api_key=LLM_API_KEY, base_url=LLM_BASE_URL)
        self.model = LLM_MODEL_NAME

    def generate(
        self,
        original_resume: Resume,
        suggestions: Dict[str, Any],
        job_intent: str = "",
    ) -> str:
        """生成优化后的简历文本"""
        suggestion_text = ""
        for opt in suggestions.get("content_optimizations", []):
            suggestion_text += f"### {opt.get('section', '')}\n"
            suggestion_text += f"- 问题: {opt.get('original', '')}\n"
            suggestion_text += f"- 建议: {opt.get('suggestion', '')}\n"
            if opt.get("example"):
                suggestion_text += f"- 示例: {opt.get('example', '')}\n"
            suggestion_text += "\n"

        prompt = f"""你是一位资深的简历优化专家。请根据以下原始简历和优化建议，生成一份完整的优化版简历。

=== 原始简历 ===
{original_resume.to_text()}

=== 优化建议 ===
整体策略: {suggestions.get('overall_strategy', '')}

{suggestion_text}

关键优化关键词: {', '.join(suggestions.get('keywords', []))}

求职意向针对性调整: {suggestions.get('job_targeting', '')}

=== 要求 ===
请生成一份完整的、优化后的简历文本，要求：
1. 使用中文，语言简洁有力，突出成果和数据
2. 工作经历和项目经历使用 STAR 法则（情景-任务-行动-结果）
3. 针对求职意向进行优化，突出相关经验和技能
4. 使用行业关键词和专业术语
5. 格式清晰，层次分明

直接输出优化后的完整简历内容（markdown格式）。
"""

        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": "你是一位资深的简历优化专家，擅长生成高质量的优化简历。"},
                {"role": "user", "content": prompt},
            ],
            temperature=0.3,
        )

        return response.choices[0].message.content

    def generate_by_template(
        self,
        original_resume: Resume,
        job_description: str,
    ) -> str:
        """根据具体岗位 JD 生成针对性简历"""
        prompt = f"""你是一位资深的简历优化专家。请根据以下原始简历和岗位描述，生成一份针对该岗位优化后的简历。

=== 原始简历 ===
{original_resume.to_text()}

=== 岗位描述 ===
{job_description}

=== 要求 ===
1. 突出与岗位最相关的经验和技能
2. 使用岗位 JD 中的关键词
3. 量化成果，使用 STAR 法则
4. 调整个人总结以匹配岗位要求
5. 保持真实，不捏造经历

直接输出优化后的完整简历（markdown格式）。
"""

        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": "你是一位资深的简历优化专家。"},
                {"role": "user", "content": prompt},
            ],
            temperature=0.3,
        )

        return response.choices[0].message.content
