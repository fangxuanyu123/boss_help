"""AI 简历优化助手 —— 基于目标岗位驱动的简历优化与PDF生成"""
import streamlit as st
from pathlib import Path
import tempfile

from utils.resume_parser import parse_resume

from agents.resume_analysis_agent import ResumeAnalysisAgent
from agents.role_analyzer_agent import RoleAnalyzerAgent
from agents.gap_analyzer_agent import GapAnalyzerAgent
from agents.optimization_agent import OptimizationAgent
from agents.resume_generation_agent import ResumeGenerationAgent
from agents.job_matching_agent import JobMatchingAgent
from agents.reflection_loop import ReflectionLoop
from evaluators.role_analyzer_evaluator import RoleAnalyzerEvaluator
from evaluators.gap_analyzer_evaluator import GapAnalyzerEvaluator
from evaluators.optimization_evaluator import OptimizationEvaluator

from generators.template_engine import TemplateEngine
from generators.pdf_renderer import PDFRenderer

from mcp_server.job_search import search_jobs


# ---- 页面配置 ----
st.set_page_config(
    page_title="AI 简历优化助手",
    page_icon="📄",
    layout="wide",
)

st.title("📄 AI 简历优化助手")
st.caption("基于目标岗位驱动，上传简历即可获得专业优化和PDF输出。JD可选，仅需岗位名也可优化。")


# ---- 初始化组件 ----
@st.cache_resource
def get_agents():
    return {
        "analysis": ResumeAnalysisAgent(),
        "role": RoleAnalyzerAgent(),
        "gap": GapAnalyzerAgent(),
        "optimization": OptimizationAgent(),
        "generation": ResumeGenerationAgent(),
        "matching": JobMatchingAgent(),
    }


@st.cache_resource
def get_generators():
    return TemplateEngine(), PDFRenderer()


@st.cache_resource
def get_reflection_loops():
    return {
        "role":     ReflectionLoop(RoleAnalyzerEvaluator(), max_retries=2),
        "gap":      ReflectionLoop(GapAnalyzerEvaluator(), max_retries=2),
        "optimization": ReflectionLoop(OptimizationEvaluator(), max_retries=2),
    }


agents = get_agents()
reflection_loops = get_reflection_loops()
template_engine, pdf_renderer = get_generators()
templates = template_engine.list_templates()

# ---- Session State ----
defaults = {
    "resume": None,
    "resume_raw_text": "",
    "resume_analysis": None,
    "job_profile": None,
    "gap_analysis": None,
    "suggestions": None,
    "diff_result": None,
    "coherence_review": None,
    "match_rounds": [],
    "optimized_resume": None,
    "match_result": None,
    "pdf_bytes": None,
    "current_template": templates[0]["id"],
    "job_title_input": "",
    "reflection_logs": {},
    "job_listings": [],
}
for key, val in defaults.items():
    if key not in st.session_state:
        st.session_state[key] = val


# ---- 输入区域 ----
col1, col2 = st.columns([1, 1])

with col1:
    st.subheader("📤 上传简历")
    uploaded_file = st.file_uploader(
        "支持 PDF / DOCX 格式",
        type=["pdf", "docx"],
        help="上传你的简历文件，支持 PDF 和 Word 格式",
    )

    st.subheader("🎯 目标岗位")
    job_title = st.text_input(
        "意向岗位名称（必填）",
        placeholder="例如：高级Java开发工程师、产品经理、数据分析师",
        help="输入你期望的岗位名称，Agent会根据行业标准优化你的简历",
        key="job_title_input_widget",
    )

with col2:
    st.subheader("📋 岗位描述（可选）")
    jd_text = st.text_area(
        "粘贴目标岗位的 JD",
        placeholder="如有目标岗位的招聘JD，粘贴到这里可以让优化更精准...\n\n不填也可以，Agent会根据你输入的岗位名称自动分析该岗位的典型要求。",
        height=180,
        help="粘贴完整的岗位描述可以让简历优化更有针对性",
    )

    st.subheader("🎨 排版风格")
    template_names = [f"{t['name']} - {t['description']}" for t in templates]
    selected_tpl_idx = st.selectbox(
        "选择PDF排版模板",
        range(len(templates)),
        format_func=lambda i: template_names[i],
    )
    st.session_state.current_template = templates[selected_tpl_idx]["id"]

# ---- 操作按钮 ----
col_btn1, col_btn2 = st.columns([1, 3])
with col_btn1:
    start_btn = st.button("🚀 开始优化", type="primary", use_container_width=True)
with col_btn2:
    if st.button("🔄 重置", use_container_width=False):
        for key in defaults:
            st.session_state[key] = defaults[key]
        st.rerun()


# ---- 主流程 ----
if start_btn:
    if not uploaded_file:
        st.error("请先上传简历文件")
    elif not job_title.strip():
        st.error("请输入意向岗位名称")
    else:
        st.session_state.job_title_input = job_title.strip()
        with st.status("正在处理...", expanded=True) as status:
            try:
                # Step 1: 解析简历
                st.write("📖 解析简历文件...")
                with tempfile.TemporaryDirectory() as tmpdir:
                    filepath = Path(tmpdir) / uploaded_file.name
                    filepath.write_bytes(uploaded_file.getvalue())
                    resume = parse_resume(filepath)

                if not resume or not resume.raw_text:
                    st.error("无法解析简历文件，请检查文件格式")
                    st.stop()

                st.session_state.resume = resume
                st.session_state.resume_raw_text = resume.raw_text
                st.write("✅ 简历解析完成")

                # Step 1.5: 结构化提取（从raw_text解析出完整的structured Resume）
                st.write("📝 提取简历结构化信息...")
                structured_resume = agents["analysis"].extract_structured_resume(
                    resume.raw_text, job_title
                )
                st.session_state.resume = structured_resume  # 替换空壳Resume
                st.write(f"✅ 结构化提取完成: {len(structured_resume.work_experiences)}段工作经历, {len(structured_resume.projects)}个项目, {len(structured_resume.skills)}类技能")

                # Step 2: 岗位画像（with Reflection）
                st.write("🔍 分析目标岗位画像...")
                if jd_text.strip():
                    st.session_state.job_profile, role_evals = reflection_loops["role"].run(
                        agent_callable=lambda critique: agents["role"].analyze_from_jd(jd_text, critique=critique),
                        context={"jd_text": jd_text},
                    )
                else:
                    st.session_state.job_profile, role_evals = reflection_loops["role"].run(
                        agent_callable=lambda critique: agents["role"].analyze_from_title(job_title, critique=critique),
                        context={},
                    )
                st.session_state.reflection_logs["role"] = role_evals
                jp = st.session_state.job_profile
                st.write(f"✅ 岗位画像完成: {jp.title} ({jp.level or '层级未指定'})")

                # Step 2.5: 深度分析简历
                st.write("🔬 深度分析简历内容...")
                st.session_state.resume_analysis = agents["analysis"].analyze(structured_resume)
                st.write("✅ 简历深度分析完成")

                # Step 3: Gap 分析（with Reflection）
                st.write("📊 对比简历与岗位差距...")
                st.session_state.gap_analysis, gap_evals = reflection_loops["gap"].run(
                    agent_callable=lambda critique: agents["gap"].analyze(
                        structured_resume, st.session_state.job_profile,
                        resume_analysis=st.session_state.resume_analysis,
                        critique=critique,
                    ),
                    context={},
                )
                st.session_state.reflection_logs["gap"] = gap_evals
                st.write("✅ 差距分析完成")

                # Step 4: 优化建议（with Reflection）
                st.write("💡 生成优化建议...")
                st.session_state.suggestions, opt_evals = reflection_loops["optimization"].run(
                    agent_callable=lambda critique: agents["optimization"].generate_suggestions(
                        st.session_state.gap_analysis,
                        st.session_state.job_profile,
                        critique=critique,
                    ),
                    context={"gap_analysis": st.session_state.gap_analysis},
                )
                st.session_state.reflection_logs["optimization"] = opt_evals
                st.write("✅ 优化建议生成完成")

                # Step 5: 生成优化简历（Diff-based + 匹配度闭环）
                st.write("✍️ 生成优化简历（手术式微调）...")

                from agents.match_loop import MatchLoop
                match_loop = MatchLoop(
                    agents["generation"],
                    agents["matching"],
                    threshold=70,
                    max_rounds=2,
                )
                st.session_state.optimized_resume, match_rounds, st.session_state.match_result = \
                    match_loop.run(
                        structured_resume,
                        st.session_state.suggestions,
                        st.session_state.job_profile,
                    )
                st.session_state.optimized_resume.raw_text = resume.raw_text
                st.session_state.match_rounds = match_rounds

                last_round = match_rounds[-1] if match_rounds else {}
                st.session_state.diff_result = last_round.get("diff")
                st.session_state.coherence_review = last_round.get("coherence")

                final_score = st.session_state.match_result.get("match_score", 0)
                num_rounds = len(match_rounds)
                st.write(f"✅ 优化完成: {num_rounds}轮, 最终匹配度 {final_score}/100")

                # Step 7: 生成 PDF
                st.write("🖨️ 渲染PDF...")
                html = template_engine.render(
                    st.session_state.optimized_resume,
                    job_title,
                    st.session_state.current_template,
                )
                st.session_state.pdf_bytes = pdf_renderer.render_to_bytes(html)
                st.write("✅ PDF 生成完成")

                status.update(label="✨ 优化完成！", state="complete", expanded=False)

            except Exception as e:
                status.update(label=f"❌ 处理出错", state="error")
                st.exception(e)


# ---- 结果展示 ----
if st.session_state.optimized_resume:
    st.divider()

    tabs = st.tabs(["📊 优化预览", "🔬 分析报告", "📥 PDF下载", "🔗 岗位匹配"])

    # ---- Tab 1: 优化预览 ----
    with tabs[0]:
        diff = st.session_state.get("diff_result")
        coherence = st.session_state.get("coherence_review")

        # 改动清单
        if diff and diff.changes:
            st.subheader(f"🔧 改动清单（共 {len(diff.changes)} 处）")
            if diff.estimated_impact:
                st.caption(diff.estimated_impact)

            action_labels = {
                "rewrite": ("🟡 改写", "orange"),
                "append": ("🟢 补充", "green"),
                "highlight": ("🔵 强化", "blue"),
                "delete": ("🔴 删除", "red"),
                "reorder": ("🟣 调整顺序", "violet"),
            }

            for i, c in enumerate(diff.changes):
                icon, _ = action_labels.get(c.action.value, ("⚪ 改写", "grey"))
                label = f"{icon} {c.section_label}"
                if c.reason:
                    label += f" — {c.reason}"
                with st.expander(label, expanded=(i < 3)):
                    if c.original:
                        st.markdown(f"**原文:** {c.original}")
                    if c.rewritten:
                        st.markdown(f"**改后:** {c.rewritten}")
                    if c.item:
                        st.markdown(f"**新增:** `{c.item}`")

            if diff.unchanged_summary:
                st.caption(f"💡 {diff.unchanged_summary}")

            # 连贯性审查
            if coherence:
                co_passed = coherence.coherence_score >= 7.0
                co_icon = "✅" if co_passed else "⚠️"
                st.info(f"{co_icon} 全文连贯性: {coherence.coherence_score:.1f}/10")
                if coherence.issues:
                    for issue in coherence.issues:
                        st.caption(f"  - {issue}")

        # 完整优化后简历
        with st.expander("📋 完整优化后简历（展开查看）"):
            opt = st.session_state.optimized_resume
            if opt:
                st.markdown(f"**{opt.name}** | {opt.phone} | {opt.email}")
                st.markdown(f"*{opt.title}*")
                if opt.summary:
                    st.markdown(f"> {opt.summary}")

                if opt.work_experiences:
                    st.markdown("##### 工作经历")
                    for exp in opt.work_experiences:
                        st.markdown(f"**{exp.position}** @ {exp.company}  *{exp.start_date} - {exp.end_date}*")
                        for r in exp.responsibilities:
                            st.markdown(f"- {r}")
                        for a in exp.achievements:
                            st.markdown(f"- ⭐ {a}")

                if opt.projects:
                    st.markdown("##### 项目经历")
                    for proj in opt.projects:
                        st.markdown(f"**{proj.name}** ({proj.role})")
                        for h in proj.highlights:
                            st.markdown(f"- {h}")
                        if proj.tech_stack:
                            st.caption(f"🔧 {', '.join(proj.tech_stack)}")

                if opt.skills:
                    st.markdown("##### 技能")
                    for skill in opt.skills:
                        st.markdown(f"- **{skill.category}**: {', '.join(skill.items)}")

                if opt.certifications:
                    st.markdown(f"**证书:** {', '.join(opt.certifications)}")

    # ---- Tab 2: 分析报告 ----
    with tabs[1]:
        col_a, col_b = st.columns(2)

        with col_a:
            st.subheader("🎯 岗位画像")
            if st.session_state.job_profile:
                job = st.session_state.job_profile
                with st.container(border=True):
                    st.markdown(f"**岗位**: {job.title}")
                    if job.company:
                        st.markdown(f"**公司**: {job.company}")
                    st.markdown(f"**层级**: {job.level or '未指定'} | **行业**: {job.industry or '未指定'}")
                    source_label = "JD原文提取" if job.source == "jd" else "岗位名推测"
                    st.caption(f"来源: {source_label}")
                    if job.tech_keywords:
                        st.markdown(f"**技术关键词**: {' '.join([f'`{k}`' for k in job.tech_keywords])}")
                    if job.soft_skills:
                        st.markdown(f"**软技能**: {', '.join(job.soft_skills)}")
                    if job.responsibilities:
                        with st.expander(f"典型职责（{len(job.responsibilities)}条）"):
                            for r in job.responsibilities:
                                st.markdown(f"- {r}")
                    if job.requirements:
                        with st.expander(f"硬性要求（{len(job.requirements)}条）"):
                            for r in job.requirements:
                                st.markdown(f"- {r}")

            st.subheader("📊 匹配度")
            if st.session_state.match_result:
                score = st.session_state.match_result.get("match_score", 0)
                st.progress(score / 100, text=f"**{score}/100**")
                st.caption(st.session_state.match_result.get("summary", ""))
                with st.expander("匹配优势"):
                    for s in st.session_state.match_result.get("match_strengths", []):
                        st.markdown(f"- ✅ {s}")

        with col_b:
            st.subheader("🔍 关键词分析")
            if st.session_state.gap_analysis:
                kw = st.session_state.gap_analysis.get("keyword_match", {})
                col_k1, col_k2, col_k3 = st.columns(3)
                with col_k1:
                    st.markdown("**✅ 已匹配**")
                    for k in kw.get("matched", []):
                        st.markdown(f"- `{k}`")
                with col_k2:
                    st.markdown("**📌 不够突出**")
                    for k in kw.get("present_but_buried", []):
                        st.markdown(f"- `{k}`")
                with col_k3:
                    st.markdown("**❌ 缺失**")
                    for k in kw.get("missing", []):
                        st.markdown(f"- `{k}`")

            st.subheader("💡 优化建议")
            if st.session_state.suggestions:
                st.info(st.session_state.suggestions.get("overall_strategy", ""))
                with st.expander("详细优化项", expanded=True):
                    for opt in st.session_state.suggestions.get("content_optimizations", []):
                        st.markdown(f"**{opt.get('section', '')}**")
                        st.caption(f"问题: {opt.get('original', '')}")
                        st.markdown(f"建议: {opt.get('suggestion', '')}")
                        if opt.get("example"):
                            st.code(opt.get("example", ""), language=None)

            st.subheader("🔍 质量评估")
            logs = st.session_state.get("reflection_logs", {})
            for module_name, module_label in [
                ("role", "岗位画像"),
                ("gap", "差距分析"),
                ("optimization", "优化建议"),
            ]:
                evals = logs.get(module_name, [])
                if not evals:
                    continue
                final = evals[-1]
                passed = final.passed
                icon = "✅" if passed else "⚠️"
                with st.expander(f"{icon} {module_label} — {final.score:.1f}/10", expanded=not passed):
                    for i, e in enumerate(evals):
                        round_label = f"第{i+1}轮" if i > 0 else "首轮"
                        status_icon = "✅" if e.passed else "🔄"
                        st.caption(f"{status_icon} {round_label}: {e.score:.1f}/10")
                    if final.issues:
                        st.markdown("**发现问题：**")
                        for issue in final.issues:
                            st.markdown(f"- {issue}")

            st.subheader("📋 优先行动")
            if st.session_state.suggestions:
                for i, action in enumerate(st.session_state.suggestions.get("priority_actions", []), 1):
                    st.markdown(f"{i}. **{action}**")

    # ---- Tab 3: PDF下载 ----
    with tabs[2]:
        st.subheader("📥 下载优化简历")

        styles = template_engine.list_templates()
        style_names = [f"{s['name']} — {s['description']}" for s in styles]
        download_style = st.selectbox(
            "排版风格",
            style_names,
            key="download_style_select",
        )
        download_style_id = styles[style_names.index(download_style)]["id"]

        if download_style_id != st.session_state.current_template or st.button("🔄 用此风格重新渲染", key="re_render_btn"):
            st.session_state.current_template = download_style_id
            html = template_engine.render(
                st.session_state.optimized_resume,
                st.session_state.job_title_input,
                download_style_id,
            )
            st.session_state.pdf_bytes = pdf_renderer.render_to_bytes(html)

        if st.session_state.pdf_bytes:
            col_dl1, col_dl2 = st.columns(2)
            with col_dl1:
                st.download_button(
                    label="📥 下载 PDF 简历",
                    data=st.session_state.pdf_bytes,
                    file_name=f"简历_{st.session_state.optimized_resume.name}_{download_style_id}.pdf",
                    mime="application/pdf",
                    use_container_width=True,
                )
            with col_dl2:
                st.markdown(f"🎨 风格: **{download_style}**")
                st.caption(f"文件大小: {len(st.session_state.pdf_bytes) / 1024:.1f} KB")

            st.divider()
            st.caption("备选格式:")
            st.download_button(
                label="📝 下载 Markdown 版本",
                data=st.session_state.optimized_resume.to_text(),
                file_name=f"简历_{st.session_state.optimized_resume.name}.md",
                mime="text/markdown",
            )

    # ---- Tab 4: 岗位匹配 ----
    with tabs[3]:
        st.subheader("🔗 匹配岗位")

        if not st.session_state.get("optimized_resume"):
            st.info("请先完成简历优化，然后在此搜索匹配岗位。")
        else:
            opt = st.session_state.optimized_resume
            all_skills = []
            for s in opt.skills:
                all_skills.extend(s.items)
            search_title = opt.title or st.session_state.job_title_input
            search_keywords = list(set(all_skills))[:12]
            keywords_str = " / ".join(search_keywords[:8])

            st.caption(f"将搜索: **{search_title}** | 技能: {keywords_str}")

            if st.button("🔍 搜索匹配岗位", type="primary", key="search_jobs_btn"):
                with st.spinner("正在搜索 Boss 直聘..."):
                    try:
                        st.session_state.job_listings = search_jobs(
                            title=search_title,
                            keywords=search_keywords,
                            limit=15,
                        )
                    except Exception as e:
                        st.error(f"搜索失败: {e}")
                        st.session_state.job_listings = []

            listings = st.session_state.get("job_listings", [])
            if listings:
                st.success(f"找到 {len(listings)} 个岗位")
                for i, job in enumerate(listings):
                    with st.container(border=True):
                        col_l, col_r = st.columns([3, 1])
                        with col_l:
                            st.markdown(f"### {i+1}. {job.title}")
                            st.markdown(f"**{job.company}** | {job.salary} | {job.city}")
                            st.caption(f"{job.experience} | {job.education}")
                            if job.tags:
                                st.caption(" / ".join(job.tags))
                        with col_r:
                            st.metric("匹配度", f"{job.match_score:.0f}%")
                            if job.url:
                                st.link_button("查看详情", job.url)

# ---- 底部 ----
st.divider()
st.caption("💡 优化基于目标岗位需求驱动，不会编造不存在的经历。所有修改都是对现有经历的重新表述和结构优化。")
