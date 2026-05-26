"""评估器基类 —— 所有具体评估器的抽象基类"""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Dict, Any
import json
from openai import OpenAI
from config import LLM_API_KEY, LLM_BASE_URL, LLM_MODEL_FAST


@dataclass
class EvaluationResult:
    """评估结果"""
    score: float
    passed: bool
    strengths: list = field(default_factory=list)
    issues: list = field(default_factory=list)
    suggestion: str = ""
    threshold: float = 6.0


class BaseEvaluator(ABC):
    """评估器抽象基类。

    子类只需实现两个方法：
    - get_system_prompt() → 评委角色描述
    - get_evaluation_prompt(output, context) → 评估任务prompt
    """

    def __init__(self, threshold: float = 6.0):
        self.client = OpenAI(api_key=LLM_API_KEY, base_url=LLM_BASE_URL)
        self.model = LLM_MODEL_FAST
        self.threshold = threshold

    @abstractmethod
    def get_system_prompt(self) -> str:
        """返回评委的角色描述（system prompt）"""
        ...

    @abstractmethod
    def get_evaluation_prompt(self, output: Dict[str, Any], context: Dict[str, Any]) -> str:
        """返回包含待评估输出和评估标准的 prompt

        Args:
            output: Agent 输出的 dict
            context: 评估所需的上下文（如原始简历文本、岗位画像等）
        """
        ...

    def evaluate(self, output: Dict[str, Any], context: Dict[str, Any]) -> EvaluationResult:
        """调用 LLM 对 Agent 输出进行质量评估"""
        evaluation_prompt = self.get_evaluation_prompt(output, context)

        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": self.get_system_prompt()},
                {"role": "user", "content": evaluation_prompt},
            ],
            response_format={"type": "json_object"},
            temperature=0.2,
        )

        try:
            data = json.loads(response.choices[0].message.content)
            score = float(data.get("score", 0.0))
            return EvaluationResult(
                score=score,
                passed=score >= self.threshold,
                strengths=data.get("strengths", []),
                issues=data.get("issues", []),
                suggestion=data.get("suggestion", ""),
                threshold=self.threshold,
            )
        except (json.JSONDecodeError, TypeError, AttributeError) as e:
            return EvaluationResult(
                score=0.0,
                passed=False,
                issues=[f"评估调用失败：{e}"],
            )
