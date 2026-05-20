"""测试 RoleAnalyzerAgent —— 输入岗位名或JD，查看岗位画像输出"""
import sys
from pathlib import Path

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")

sys.path.insert(0, str(Path(__file__).parent.parent))

from agents.role_analyzer_agent import RoleAnalyzerAgent


def print_separator(title: str):
    print(f"\n{'='*60}")
    print(f"  {title}")
    print('='*60)


def print_job_profile(job):
    """打印岗位画像"""
    print(f"岗位: {job.title}")
    print(f"来源: {'JD提取' if job.source == 'jd' else '岗位名推测'}")
    if job.company:
        print(f"公司: {job.company}")
    if job.location:
        print(f"地点: {job.location}")
    if job.salary_range:
        print(f"薪资: {job.salary_range}")
    if job.level:
        print(f"层级: {job.level}")
    if job.industry:
        print(f"行业: {job.industry}")

    if job.responsibilities:
        print("\n【岗位职责】")
        for i, r in enumerate(job.responsibilities, 1):
            print(f"  {i}. {r}")

    if job.requirements:
        print("\n【硬性要求】")
        for i, r in enumerate(job.requirements, 1):
            print(f"  {i}. {r}")

    if job.preferred:
        print("\n【加分项】")
        for i, p in enumerate(job.preferred, 1):
            print(f"  {i}. {p}")

    if job.tech_keywords:
        print(f"\n【技术关键词】({len(job.tech_keywords)}个)")
        print(f"  {', '.join(job.tech_keywords)}")

    if job.soft_skills:
        print(f"\n【软技能】")
        print(f"  {', '.join(job.soft_skills)}")

    if job.description:
        print(f"\n【JD原文】(截取前200字)")
        print(f"  {job.description[:200]}...")


def main():
    print("=" * 60)
    print("  RoleAnalyzerAgent 功能测试")
    print("=" * 60)
    print()
    print("  模式 1: 仅输入岗位名（LLM 根据行业经验补全画像）")
    print("  模式 2: 粘贴 JD 原文（LLM 从 JD 中提取画像）")
    print()

    agent = RoleAnalyzerAgent()

    # 解析命令行参数
    mode = None
    input_value = None

    args = sys.argv[1:]
    i = 0
    while i < len(args):
        if args[i] == "--title":
            mode = "title"
            input_value = args[i + 1]
            i += 2
        elif args[i] == "--jd-file":
            mode = "jd_file"
            input_value = args[i + 1]
            i += 2
        elif args[i] == "--jd":
            mode = "jd"
            input_value = args[i + 1]
            i += 2
        else:
            i += 1

    if mode is None:
        choice = input("请选择测试模式 (1=岗位名, 2=JD原文): ").strip()
        if choice == "1":
            mode = "title"
            input_value = input("请输入岗位名称: ").strip()
        elif choice == "2":
            sub = input("JD来源 (1=粘贴文本, 2=从文件读取): ").strip()
            if sub == "2":
                mode = "jd_file"
                input_value = input("请输入JD文件路径: ").strip().strip('"')
            else:
                mode = "jd"
                print("请粘贴 JD 原文（输入完成后按 Enter，然后按 Ctrl+Z 再回车结束）:")
                lines = []
                while True:
                    try:
                        line = input()
                        lines.append(line)
                    except EOFError:
                        break
                input_value = "\n".join(lines)

    # 执行分析
    if mode == "title":
        print(f"\n[分析中] 岗位名: {input_value}")
        print(f"  -> LLM 根据行业经验补全岗位画像...")
        job_profile = agent.analyze_from_title(input_value)
    elif mode == "jd":
        print(f"\n[分析中] JD 原文 ({len(input_value)} 字)")
        print(f"  -> LLM 从 JD 中提取结构化画像...")
        job_profile = agent.analyze_from_jd(input_value)
    elif mode == "jd_file":
        jd_path = Path(input_value)
        if not jd_path.exists():
            print(f"[错误] 文件不存在: {jd_path}")
            sys.exit(1)
        jd_text = jd_path.read_text(encoding="utf-8").strip()
        print(f"\n[分析中] JD 文件: {jd_path.name} ({len(jd_text)} 字)")
        print(f"  -> LLM 从 JD 中提取结构化画像...")
        job_profile = agent.analyze_from_jd(jd_text)

    print_separator("岗位画像结果")
    print_job_profile(job_profile)

    print("\n" + "=" * 60)
    print("  测试完成")
    print("=" * 60)


if __name__ == "__main__":
    main()
