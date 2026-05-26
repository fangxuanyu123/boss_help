"""评测脚本 —— 对 DiffAgent 在标注数据集上自动评分"""
import sys
import json
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from models.resume import Resume
from agents.resume_analysis_agent import ResumeAnalysisAgent
from agents.diff_agent import DiffAgent
from eval.golden_cases import CASES


def score_case(case: dict) -> dict:
    """对单个 case 评测 DiffAgent 输出"""
    resume = Resume(raw_text=case["resume_text"])
    # 简化版结构化提取
    analysis_agent = ResumeAnalysisAgent()
    structured = analysis_agent.extract_structured_resume(case["resume_text"], case["job_title"])

    diff_agent = DiffAgent()
    mock_suggestions = {
        "overall_strategy": "针对岗位要求优化简历描述",
        "content_optimizations": [],
        "keywords_to_add": case["job"].tech_keywords,
    }

    result = diff_agent.generate_diff(
        structured, mock_suggestions, case["job"]
    )

    expected = case["expected"]
    changes = result.changes
    scores = {}
    details = []

    # 1. 数量检查
    count = len(changes)
    scores["count"] = 1.0 if expected["min_changes"] <= count <= expected["max_changes"] else (
        0.5 if count > 0 else 0.0
    )
    details.append(f"改动数={count} (期望{expected['min_changes']}-{expected['max_changes']})")

    # 2. action 类型检查
    actions = set(c.action.value for c in changes)
    required_actions = set(expected["must_contain_actions"])
    matched = required_actions & actions
    scores["actions"] = len(matched) / len(required_actions) if required_actions else 1.0
    details.append(f"action类型匹配: {matched}/{required_actions}")

    # 3. 板块覆盖检查
    sections_covered = set()
    for c in changes:
        target = c.target
        for sec in expected["must_cover_sections"]:
            if sec in target:
                sections_covered.add(sec)
    scores["coverage"] = len(sections_covered) / len(expected["must_cover_sections"])
    details.append(f"板块覆盖: {sections_covered}/{set(expected['must_cover_sections'])}")

    # 4. reason 质量检查
    all_reasons = " ".join(c.reason for c in changes)
    key_hits = sum(1 for kw in expected["key_terms_in_changes"] if kw in all_reasons)
    scores["reason_quality"] = min(1.0, key_hits / len(expected["key_terms_in_changes"]))
    details.append(f"reason关键词命中: {key_hits}/{len(expected['key_terms_in_changes'])}")

    # 5. 综合得分
    weights = {"count": 0.2, "actions": 0.25, "coverage": 0.3, "reason_quality": 0.25}
    overall = sum(scores[k] * weights[k] for k in weights)
    scores["overall"] = round(overall, 2)

    return {
        "case_id": case["id"],
        "overall": scores["overall"],
        "sub_scores": {k: round(v, 2) for k, v in scores.items()},
        "details": details,
        "change_count": count,
        "changes_summary": [f"{c.action.value}: {c.section_label}" for c in changes[:5]],
    }


def main():
    print("=" * 60)
    print("  DiffAgent 评测")
    print("=" * 60)
    print(f"  共 {len(CASES)} 个测试用例\n")

    total_score = 0.0
    passed = 0

    for i, case in enumerate(CASES, 1):
        print(f"[{i}/{len(CASES)}] {case['id']} ({case['job_title']})")
        start = time.time()
        try:
            result = score_case(case)
            elapsed = time.time() - start
            status = "✅" if result["overall"] >= 0.6 else "⚠️"
            print(f"  {status} 综合: {result['overall']}/1.0 | {elapsed:.1f}s")
            for d in result["details"]:
                print(f"     {d}")
            for c in result["changes_summary"]:
                print(f"     - {c}")
            total_score += result["overall"]
            if result["overall"] >= 0.6:
                passed += 1
        except Exception as e:
            elapsed = time.time() - start
            print(f"  ❌ 失败 ({elapsed:.1f}s): {e}")
        print()

    avg = total_score / len(CASES) if CASES else 0
    print("=" * 60)
    print(f"  平均分: {avg:.2f}/1.0 | 通过率: {passed}/{len(CASES)}")
    print("=" * 60)
    return avg


if __name__ == "__main__":
    main()
