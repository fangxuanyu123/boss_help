"""MatchLoop —— 匹配度驱动优化闭环"""
import logging
from typing import List
from models.resume import Resume
from models.job import JobRequirement

logger = logging.getLogger(__name__)


class MatchLoop:
    """匹配度驱动优化闭环。

    用法:
        loop = MatchLoop(generation_agent, matching_agent, threshold=70, max_rounds=2)
        final_resume, rounds, best_match = loop.run(original_resume, suggestions, job_profile)
    """

    def __init__(self, generation_agent, matching_agent, threshold=70, max_rounds=2):
        self.generation = generation_agent
        self.matching = matching_agent
        self.threshold = threshold
        self.max_rounds = max_rounds

    def run(
        self,
        original_resume: Resume,
        suggestions: dict,
        job: JobRequirement,
    ) -> tuple:
        """执行匹配闭环。

        Returns:
            (最佳简历, 每轮记录列表, 最佳匹配结果)
        """
        rounds = []
        best_resume = None
        best_score = -1
        best_match = None
        uncovered_gaps = None

        for rnd in range(self.max_rounds):
            round_num = rnd + 1
            logger.info("MatchLoop 第 %d/%d 轮", round_num, self.max_rounds)

            # 生成
            if rnd == 0:
                resume, diff, coherence, warnings = self.generation.generate(
                    original_resume, suggestions, job,
                )
            else:
                resume, diff, coherence, warnings = self.generation.generate(
                    original_resume, suggestions, job,
                    uncovered_gaps=uncovered_gaps,
                )

            # 匹配打分
            match = self.matching.match(resume, job)
            score = match.get("match_score", 0)

            rounds.append({
                "round": round_num,
                "resume": resume,
                "diff": diff,
                "coherence": coherence,
                "match": match,
            })

            if score > best_score:
                best_score = score
                best_resume = resume
                best_match = match

            logger.info("第 %d 轮匹配度: %d/100", round_num, score)

            if score >= self.threshold:
                logger.info("匹配度达标，结束循环")
                break

            uncovered_gaps = match.get("uncovered_gaps", [])
            if not uncovered_gaps:
                logger.info("无未覆盖差距，结束循环")
                break

        return best_resume, rounds, best_match
