"""测试岗位搜索 —— 独立验证 MCP job_search 功能"""
import sys
from pathlib import Path

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")

sys.path.insert(0, str(Path(__file__).parent.parent))

from mcp_server.job_search import search_jobs, JobListing


def print_separator(title: str):
    print(f"\n{'='*60}")
    print(f"  {title}")
    print('='*60)


def main():
    print("=" * 60)
    print("  岗位搜索功能测试")
    print("=" * 60)
    print()
    print("  生成主流招聘平台搜索链接 + Bing 聚合搜索")
    print()

    # --- 解析参数 ---
    title = None
    keywords = None
    city = ""
    limit = 10

    args = sys.argv[1:]
    i = 0
    while i < len(args):
        if args[i] == "--title" and i + 1 < len(args):
            title = args[i + 1]
            i += 2
        elif args[i] == "--keywords" and i + 1 < len(args):
            keywords = [k.strip() for k in args[i + 1].split(",")]
            i += 2
        elif args[i] == "--city" and i + 1 < len(args):
            city = args[i + 1]
            i += 2
        elif args[i] == "--limit" and i + 1 < len(args):
            limit = int(args[i + 1])
            i += 2
        else:
            i += 1

    # --- 交互式输入 ---
    if title is None:
        title = input("请输入求职意向岗位名称: ").strip()
    if keywords is None:
        kw_input = input("请输入技术关键词（逗号分隔，如 Java,Spring Cloud,K8s）: ").strip()
        keywords = [k.strip() for k in kw_input.split(",") if k.strip()]
    if not city:
        c = input("目标城市（可选，直接回车跳过）: ").strip()
        if c:
            city = c

    print(f"\n搜索参数:")
    print(f"  岗位: {title}")
    print(f"  关键词 ({len(keywords)}个): {', '.join(keywords)}")
    print(f"  城市: {city or '不限'}")
    print(f"  数量: {limit}")
    print()

    # --- 执行搜索 ---
    try:
        print("🔍 搜索中...")
        jobs = search_jobs(
            title=title,
            keywords=keywords,
            city=city,
            limit=limit,
        )

        if not jobs:
            print("⚠️ 未生成任何搜索链接。")
            return

        print_separator(f"搜索结果（共 {len(jobs)} 个岗位）")

        score_dist = {"green": 0, "orange": 0, "red": 0}
        for j in jobs:
            if j.match_score >= 70:
                score_dist["green"] += 1
            elif j.match_score >= 50:
                score_dist["orange"] += 1
            else:
                score_dist["red"] += 1
        print(f"  高匹配(>=70%): {score_dist['green']} | 中匹配(50-69%): {score_dist['orange']} | 低匹配(<50%): {score_dist['red']}")

        for i, job in enumerate(jobs, 1):
            print(f"\n{'─'*50}")
            print(f"  [{i}] {job.title}")
            print(f"  公司: {job.company}  [{job.source}]")
            print(f"  薪资: {job.salary or '未标注'}")
            print(f"  城市: {job.city}")
            print(f"  经验: {job.experience} | 学历: {job.education}")
            print(f"  标签: {', '.join(job.tags) if job.tags else '无'}")
            print(f"  匹配度: {job.match_score:.0f}%", end="")
            if job.match_score >= 70:
                print(" ✅")
            elif job.match_score >= 50:
                print(" ⚠️")
            else:
                print(" ❌")
            if job.url:
                print(f"  链接: {job.url}")

        print(f"\n{'='*60}")
        print("  测试完成")
        print('='*60)

    except Exception as e:
        print(f"\n❌ 错误: {e}")


if __name__ == "__main__":
    main()
