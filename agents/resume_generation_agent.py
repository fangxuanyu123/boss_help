"""简历生成 Agent —— 调度 DiffAgent + DiffApplier + CoherenceReviewer 完成增量优化"""
from typing import Dict, Any
import logging
from models.resume import Resume, DiffResult
from models.job import JobRequirement
from agents.diff_agent import DiffAgent
from agents.diff_applier import DiffApplier
from agents.coherence_reviewer import CoherenceReviewer

logger = logging.getLogger(__name__)


class ResumeGenerationAgent:
    """简历生成智能体 —— 增量优化模式"""

    def __init__(self):
        self.diff_agent = DiffAgent()
        self.applier = DiffApplier()
        self.reviewer = CoherenceReviewer()

    def generate(
        self,
        original_resume: Resume,
        suggestions: Dict[str, Any],
        job: JobRequirement,
        uncovered_gaps: list | None = None,
        critique: str | None = None,
    ) -> tuple:
        """生成优化简历（增量模式）。

        Returns:
            (optimized_resume, diff_result, coherence_review, warnings)
        """
        # Step 1: 生成改动清单
        diff_result = self.diff_agent.generate_diff(
            original_resume, suggestions, job,
            uncovered_gaps=uncovered_gaps,
            critique=critique,
        )
        logger.info("DiffAgent 生成了 %d 条改动", len(diff_result.changes))
        logger.info("预估影响: %s", diff_result.estimated_impact)

        # Step 2: 应用改动
        modified, warnings = self.applier.apply(original_resume, diff_result)

        if warnings:
            logger.warning("应用改动时产生 %d 条警告: %s", len(warnings), warnings)

        # Step 3: 连贯性审查
        coherence = self.reviewer.review(modified, diff_result.changes)

        if not coherence.passed and coherence.patches:
            logger.info("连贯性审查未通过 (%.1f)，应用 %d 条修补", coherence.coherence_score, len(coherence.patches))
            patch_diff = DiffResult(changes=coherence.patches, unchanged_summary="", estimated_impact="")
            modified, patch_warnings = self.applier.apply(modified, patch_diff)
            warnings.extend(patch_warnings)
            coherence = self.reviewer.review(modified, diff_result.changes + coherence.patches)

        logger.info("最终连贯性评分: %.1f, passed=%s", coherence.coherence_score, coherence.passed)
        return modified, diff_result, coherence, warnings
