"""测试 GapAnalyzerAgent —— 对比简历与岗位，查看差距分析结果"""
import sys
from pathlib import Path

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")

sys.path.insert(0, str(Path(__file__).parent.parent))

from utils.resume_parser import parse_resume
from agents.resume_analysis_agent import ResumeAnalysisAgent
from agents.role_analyzer_agent import RoleAnalyzerAgent
from agents.gap_analyzer_agent import GapAnalyzerAgent


def print_separator(title: str):
    print(f"\n{'='*60}")
    print(f"  {title}")
    print('='*60)


def print_implicit_skills(skills: list):
    print("\n【推断的隐式技能】")
    for i, s in enumerate(skills, 1):
        print(f"  {i}. {s.get('skill', '')}  [{s.get('category', '')}]")
        print(f"     依据: {s.get('evidence', '')}")


def print_keyword_match(match: dict):
    print("\n【关键词匹配】")
    matched = match.get("matched", [])
    buried = match.get("present_but_buried", [])
    missing = match.get("missing", [])

    if matched:
        print(f"  ✅ 已匹配 ({len(matched)}个): {', '.join(matched)}")
    if buried:
        print(f"  ⚠️ 有但不突出 ({len(buried)}个): {', '.join(buried)}")
    if missing:
        print(f"  ❌ 缺失 ({len(missing)}个): {', '.join(missing)}")


def print_alignment_points(points: list):
    print("\n【对齐点】")
    for i, p in enumerate(points, 1):
        print(f"  {i}. 简历: {p.get('resume_item', '')}")
        print(f"     岗位要求: {p.get('job_requirement', '')}")
        print(f"     优化方向: {p.get('action', '')}")


def print_gaps(gaps: list):
    print("\n【差距分析】")
    if not gaps:
        print("  无显著差距")
        return
    for i, g in enumerate(gaps, 1):
        print(f"  {i}. {g.get('aspect', '')}")
        print(f"     当前状态: {g.get('current_state', '')}")
        print(f"     优化方向: {g.get('optimization', '')}")


def print_restructure_plan(plan: list):
    print("\n【简历重组建议】")
    for i, p in enumerate(plan, 1):
        print(f"  {i}. [{p.get('section', '')}] {p.get('suggested_change', '')}")


def main():
    print("=" * 60)
    print("  GapAnalyzerAgent 功能测试")
    print("=" * 60)

    # --- 解析命令行参数 ---
    resume_path = None
    job_title = None
    jd_text = None
    skip_analysis = False

    args = sys.argv[1:]
    i = 0
    while i < len(args):
        if args[i] == "--resume":
            resume_path = args[i + 1]
            i += 2
        elif args[i] == "--title":
            job_title = args[i + 1]
            i += 2
        elif args[i] == "--jd-file":
            jd_path = Path(args[i + 1])
            if jd_path.exists():
                jd_text = jd_path.read_text(encoding="utf-8").strip()
            i += 2
        elif args[i] == "--jd":
            jd_text = args[i + 1]
            i += 2
        elif args[i] == "--skip-analysis":
            skip_analysis = True
            i += 1
        else:
            i += 1

    # --- 交互式输入 ---
    if resume_path is None:
        resume_path = input("请输入简历文件路径（支持 PDF/DOCX）: ").strip().strip('"')
    resume_path = Path(resume_path)
    if not resume_path.exists():
        print(f"[错误] 文件不存在: {resume_path}")
        sys.exit(1)

    if job_title is None and jd_text is None:
        choice = input("岗位输入方式 (1=岗位名, 2=粘贴JD, 3=JD文件): ").strip()
        if choice == "2":
            print("请粘贴 JD 原文（Ctrl+Z 回车结束）:")
            lines = []
            while True:
                try:
                    lines.append(input())
                except EOFError:
                    break
            jd_text = "\n".join(lines)
        elif choice == "3":
            jd_path = Path(input("请输入JD文件路径: ").strip().strip('"'))
            if jd_path.exists():
                jd_text = jd_path.read_text(encoding="utf-8").strip()
            else:
                print(f"[错误] 文件不存在: {jd_path}")
                sys.exit(1)
        else:
            job_title = input("请输入岗位名称: ").strip()

    # --- Step 1: 解析简历 ---
    print(f"\n[1/5] 解析简历: {resume_path.name}")
    resume = parse_resume(resume_path)
    if resume is None or not resume.raw_text:
        print("[错误] 无法解析简历")
        sys.exit(1)
    print(f"  -> 提取到 {len(resume.raw_text)} 个字符")

    # --- Step 2: 结构化提取 ---
    print(f"\n[2/5] 简历结构化提取...")
    analysis_agent = ResumeAnalysisAgent()
    structured = analysis_agent.extract_structured_resume(resume.raw_text, job_title or "")
    print(f"  -> {len(structured.work_experiences)}段工作, {len(structured.projects)}个项目, {len(structured.skills)}类技能")

    # --- Step 3: 岗位画像 ---
    role_agent = RoleAnalyzerAgent()
    if jd_text:
        print(f"\n[3/5] 岗位画像 (从JD提取)...")
        job_profile = role_agent.analyze_from_jd(jd_text)
    else:
        print(f"\n[3/5] 岗位画像 (从岗位名推测): {job_title}")
        job_profile = role_agent.analyze_from_title(job_title)
    print(f"  -> {job_profile.title} | {job_profile.level or '层级未指定'} | {job_profile.industry or '行业未指定'}")

    # --- Step 4: 简历分析（可选） ---
    resume_analysis = None
    if not skip_analysis:
        print(f"\n[4/5] 简历深度分析...")
        resume_analysis = analysis_agent.analyze(structured)
        score = resume_analysis.get("overall_score", "N/A")
        weaknesses = resume_analysis.get("weaknesses", [])
        print(f"  -> 综合评分: {score}/10, {len(weaknesses)}个薄弱点")
    else:
        print(f"\n[4/5] 跳过简历分析 (--skip-analysis)")

    # --- Step 5: 差距分析 ---
    print(f"\n[5/5] 简历-岗位差距分析...")
    gap_agent = GapAnalyzerAgent()
    result = gap_agent.analyze(structured, job_profile, resume_analysis=resume_analysis)

    # --- 输出结果 ---
    print_separator("差距分析结果")

    verdict = result.get("verdict", "")
    if verdict:
        print(f"\n  📋 总体判断: {verdict}")

    implicit_skills = result.get("implicit_skills", [])
    if implicit_skills:
        print_implicit_skills(implicit_skills)

    keyword_match = result.get("keyword_match", {})
    print_keyword_match(keyword_match)

    alignment_points = result.get("alignment_points", [])
    if alignment_points:
        print_alignment_points(alignment_points)

    gaps = result.get("gaps", [])
    print_gaps(gaps)

    restructure_plan = result.get("restructure_plan", [])
    if restructure_plan:
        print_restructure_plan(restructure_plan)

    summary_direction = result.get("summary_rewrite_direction", "")
    if summary_direction:
        print(f"\n【个人总结改写方向】")
        print(f"  {summary_direction}")

    priority_actions = result.get("priority_actions", [])
    if priority_actions:
        print(f"\n【优先级最高动作】")
        for i, a in enumerate(priority_actions, 1):
            print(f"  {i}. {a}")

    print("\n" + "=" * 60)
    print("  测试完成")
    print("=" * 60)


if __name__ == "__main__":
    main()
