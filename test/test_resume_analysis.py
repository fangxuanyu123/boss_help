"""测试 ResumeAnalysisAgent —— 上传简历文件并查看分析结果"""
import sys
from pathlib import Path

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")

# 确保项目根目录在 sys.path 中，使得 test/ 目录下的脚本也能正常 import
sys.path.insert(0, str(Path(__file__).parent.parent))

from utils.resume_parser import parse_resume
from agents.resume_analysis_agent import ResumeAnalysisAgent


def print_separator(title: str):
    print(f"\n{'='*60}")
    print(f"  {title}")
    print('='*60)


def print_structured_resume(resume):
    """打印结构化简历"""
    print(f"姓名: {resume.name}")
    print(f"电话: {resume.phone}")
    print(f"邮箱: {resume.email}")
    print(f"求职意向: {resume.title}")
    print(f"个人总结: {resume.summary}")

    if resume.education:
        print("\n【教育背景】")
        for edu in resume.education:
            print(f"  - {edu.school} | {edu.degree} | {edu.major} ({edu.start_date} ~ {edu.end_date})")
            if edu.description:
                print(f"    {edu.description}")

    if resume.work_experiences:
        print("\n【工作经历】")
        for exp in resume.work_experiences:
            print(f"  - {exp.company} | {exp.position} ({exp.start_date} ~ {exp.end_date})")
            for r in exp.responsibilities:
                print(f"    · {r}")
            for a in exp.achievements:
                print(f"    ★ {a}")

    if resume.projects:
        print("\n【项目经历】")
        for proj in resume.projects:
            print(f"  - {proj.name} ({proj.role})")
            if proj.description:
                print(f"    {proj.description}")
            for h in proj.highlights:
                print(f"    · {h}")
            if proj.tech_stack:
                print(f"    技术栈: {', '.join(proj.tech_stack)}")

    if resume.skills:
        print("\n【技能】")
        for skill in resume.skills:
            print(f"  - {skill.category}: {', '.join(skill.items)}")

    if resume.certifications:
        print(f"\n【证书】: {', '.join(resume.certifications)}")


def print_analysis(analysis: dict):
    """打印分析结果"""
    print(f"\n综合评分: {analysis.get('overall_score', 'N/A')} / 10")

    strengths = analysis.get("strengths", [])
    if strengths:
        print("\n【优势/亮点】")
        for i, s in enumerate(strengths, 1):
            print(f"  {i}. {s}")

    weaknesses = analysis.get("weaknesses", [])
    if weaknesses:
        print("\n【薄弱环节】")
        for i, w in enumerate(weaknesses, 1):
            print(f"  {i}. {w.get('aspect', '')}")
            print(f"     描述: {w.get('detail', '')}")
            print(f"     建议: {w.get('suggestion', '')}")

    key_improvements = analysis.get("key_improvements", [])
    if key_improvements:
        print("\n【最重要的改进点】")
        for i, imp in enumerate(key_improvements, 1):
            print(f"  {i}. {imp}")


def main():
    print("=" * 60)
    print("  ResumeAnalysisAgent 功能测试")
    print("=" * 60)

    # 获取文件路径
    if len(sys.argv) > 1:
        filepath = Path(sys.argv[1])
    else:
        filepath = Path(input("请输入简历文件路径（支持 PDF/DOCX）: ").strip().strip('"'))

    if not filepath.exists():
        print(f"[错误] 文件不存在: {filepath}")
        sys.exit(1)

    print(f"\n[1/3] 解析文件: {filepath.name}")
    resume = parse_resume(filepath)
    if resume is None or not resume.raw_text:
        print("[错误] 无法解析文件内容，文件可能为空")
        sys.exit(1)

    print(f"  -> 提取到 {len(resume.raw_text)} 个字符的原始文本")

    agent = ResumeAnalysisAgent()

    # Step 1: 结构化提取
    print(f"\n[2/3] LLM 结构化提取中...")
    structured = agent.extract_structured_resume(resume.raw_text)
    print_separator("结构化简历")
    print_structured_resume(structured)

    # Step 2: 简历分析
    print(f"\n[3/3] LLM 简历分析中...")
    analysis = agent.analyze(structured)
    print_separator("简历分析结果")
    print_analysis(analysis)

    print("\n" + "=" * 60)
    print("  测试完成")
    print("=" * 60)


if __name__ == "__main__":
    main()
