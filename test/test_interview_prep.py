"""测试 MCP 面试准备功能 —— 独立验证面经搜索 + 面试Q&A生成"""
import sys
from pathlib import Path

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")

sys.path.insert(0, str(Path(__file__).parent.parent))

from mcp_server.mianjing_search import search_mianjing
from agents.interview_prep_agent import InterviewPrepAgent


def print_separator(title: str):
    print(f"\n{'='*60}")
    print(f"  {title}")
    print('='*60)


def test_mianjing_search(keywords: list[str]):
    """步骤1：测试真实面经搜索"""
    print_separator("步骤1: 搜索真实面经（牛客网 + CSDN）")
    print(f"  搜索关键词: {', '.join(keywords)}\n")
    print("  搜索中...")

    results = search_mianjing(keywords, limit=10)

    if not results:
        print("  ⚠️ 未搜到任何面经")
        return []

    by_source = {}
    for r in results:
        by_source.setdefault(r.source, []).append(r)
    for src, items in by_source.items():
        print(f"  [{src}] {len(items)} 条")
    print(f"  共 {len(results)} 条\n")

    for i, r in enumerate(results, 1):
        print(f"  [{i}] [{r.source}] {r.title}")
        print(f"      {r.url}")
        print()

    return results


def test_interview_prep_generation(mianjing_count: int):
    """步骤2：测试 LLM 生成面试准备（含真实面经参考）"""
    print_separator("步骤2: 生成面试准备材料（LLM + 真实面经）")

    # 模拟 Pipeline 产出的数据
    mock_gap_analysis = {
        "gaps": [
            {"aspect": "分布式系统实战经验不足", "current_state": "简历中未体现分布式架构设计经验"},
            {"aspect": "消息队列深度使用缺失", "current_state": "Kafka仅在项目中简单使用，未涉及性能调优"},
            {"aspect": "系统设计能力不明确", "current_state": "缺少独立设计大型系统的经历"},
        ],
        "weaknesses": [
            {"aspect": "经历描述不够量化", "detail": "XX项目只写了负责开发，没写QPS/数据量"},
        ],
    }

    mock_suggestions = {
        "overall_strategy": "强化分布式和消息队列相关经历描述，量化项目成果",
        "content_optimizations": [],
    }

    mock_match_result = {
        "match_score": 68,
        "keyword_match": {"missing": ["Kubernetes", "Redis Cluster", "微服务治理"]},
        "uncovered_gaps": [
            {"gap": "容器化部署经验缺失", "suggestion_for_diff": "在项目描述中补充Docker/K8s相关经验"},
        ],
    }

    tech_keywords = ["Java", "Spring Cloud", "Kafka", "MySQL", "Redis", "微服务", "分布式"]
    job_title = "高级Java开发工程师"

    print(f"  目标岗位: {job_title}")
    print(f"  技术方向: {', '.join(tech_keywords)}")
    print(f"  技能差距: {len(mock_gap_analysis['gaps'])} 项")
    print(f"  缺失关键词: {len(mock_match_result['keyword_match']['missing'])} 个")
    print(f"  参考面经: {mianjing_count} 条")
    print(f"\n  LLM 生成中...")

    agent = InterviewPrepAgent()
    result = agent.generate(
        gap_analysis=mock_gap_analysis,
        suggestions=mock_suggestions,
        match_result=mock_match_result,
        tech_keywords=tech_keywords,
        job_title=job_title,
    )

    # 展示真实面经
    real_mj = result.get("_real_mianjing", [])
    if real_mj:
        print(f"\n  📚 搜索到的真实面经（{len(real_mj)}条）：")
        for mj in real_mj[:5]:
            print(f"    - [{mj.get('source','')}] {mj.get('title','')}")

    # 展示生成结果
    ta = result.get("technical_qa", [])
    print(f"\n  🔧 技术问答（{len(ta)}题）：")
    for i, q in enumerate(ta, 1):
        print(f"    [{i}] {q.get('topic', '')}")
        print(f"        Q: {q.get('question', '')}")
        hint = q.get('answer_hint', '')
        print(f"        A: {hint[:120]}{'...' if len(hint) > 120 else ''}")

    ga = result.get("gap_qa", [])
    print(f"\n  🎯 短板应对（{len(ga)}题）：")
    for i, q in enumerate(ga, 1):
        print(f"    [{i}] {q.get('gap', '')}")
        print(f"        Q: {q.get('question', '')}")

    sd = result.get("system_design", [])
    print(f"\n  🏗 系统设计（{len(sd)}题）：")
    for i, s in enumerate(sd, 1):
        print(f"    [{i}] {s.get('scenario', '')}")
        for p in s.get("key_points", []):
            print(f"        - {p}")

    bh = result.get("behavioral", [])
    print(f"\n  💬 行为面试（{len(bh)}题）：")
    for i, b in enumerate(bh, 1):
        print(f"    [{i}] {b.get('situation', '')}")
        print(f"        Q: {b.get('question', '')}")

    tips = result.get("last_minute_tips", [])
    if tips:
        print(f"\n  📋 考前建议：")
        for t in tips:
            print(f"    - {t}")

    if result.get("estimated_prep_time"):
        print(f"\n  ⏱ {result['estimated_prep_time']}")

    return result


def main():
    print("=" * 60)
    print("  MCP 面试准备功能测试")
    print("=" * 60)

    # 解析参数
    keywords = ["Java", "Spring", "Kafka", "Redis", "面试"]
    skip_mianjing = False
    skip_llm = False

    args = sys.argv[1:]
    i = 0
    while i < len(args):
        if args[i] == "--keywords" and i + 1 < len(args):
            keywords = [k.strip() for k in args[i + 1].split(",")]
            i += 2
        elif args[i] == "--skip-search":
            skip_mianjing = True
            i += 1
        elif args[i] == "--skip-llm":
            skip_llm = True
            i += 1
        else:
            i += 1

    # 步骤1：面经搜索
    mianjing_count = 0
    if not skip_mianjing:
        try:
            results = test_mianjing_search(keywords)
            mianjing_count = len(results)
        except Exception as e:
            print(f"  ❌ 面经搜索失败: {e}")
            print("  （可加 --skip-search 跳过此步骤）")
    else:
        print("  ⏭ 跳过面经搜索（--skip-search）")

    # 步骤2：LLM 生成
    if not skip_llm:
        try:
            test_interview_prep_generation(mianjing_count)
        except Exception as e:
            print(f"\n  ❌ LLM 生成失败: {e}")
            print("  （可加 --skip-llm 跳过此步骤）")
    else:
        print("  ⏭ 跳过 LLM 生成（--skip-llm）")

    print_separator("测试完成")


if __name__ == "__main__":
    main()
