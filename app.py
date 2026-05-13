"""AI 简历优化助手 - Streamlit 主界面"""
import streamlit as st
import json
from pathlib import Path

from config import LLM_API_KEY, KNOWLEDGE_BASE_PATH
from models.resume import Resume
from models.job import JobRequirement
from utils.file_utils import save_generated_resume
from utils.resume_parser import parse_resume
from agents.resume_analysis_agent import ResumeAnalysisAgent
from agents.rag_retrieval_agent import RAGRetrievalAgent
from agents.optimization_agent import OptimizationAgent
from agents.resume_generation_agent import ResumeGenerationAgent
from agents.job_matching_agent import JobMatchingAgent
from rag.retriever import retriever

# ─── 页面配置 ─────────────────────────────────────
st.set_page_config(
    page_title="AI 简历优化助手",
    page_icon="📋",
    layout="wide",
)

# ─── 初始化 Session State ────────────────────────
if "resume" not in st.session_state:
    st.session_state.resume = None
if "analysis" not in st.session_state:
    st.session_state.analysis = None
if "suggestions" not in st.session_state:
    st.session_state.suggestions = None
if "optimized_resume" not in st.session_state:
    st.session_state.optimized_resume = None
if "rag_references" not in st.session_state:
    st.session_state.rag_references = None
if "job_match" not in st.session_state:
    st.session_state.job_match = None

# ─── 侧边栏 ───────────────────────────────────────
with st.sidebar:
    st.title("⚙️ 设置")
    api_key = st.text_input("API Key", value=LLM_API_KEY, type="password")
    if not api_key:
        st.warning("请先在 .env 文件中配置 LLM_API_KEY")
    st.divider()
    st.markdown("### 📚 知识库状态")
    stats = retriever.get_knowledge_base_stats()
    st.metric("知识库片段数", stats["total_chunks"])
    st.divider()
    st.markdown("### 📌 使用流程")
    st.markdown("""
    1. 上传简历 (PDF/DOCX)
    2. 输入求职意向
    3. 进行简历分析
    4. 查看优化建议
    5. 生成优化简历
    6. （可选）岗位匹配分析
    """)

# ─── 主页面标题 ──────────────────────────────────
st.title("📋 AI 简历优化助手")
st.markdown("基于 RAG + Agent 技术的智能简历优化工具，帮你打造更出色的简历。")

# ─── Tab 布局 ────────────────────────────────────
tab1, tab2, tab3, tab4 = st.tabs([
    "📄 简历上传与分析",
    "💡 优化建议",
    "✨ 简历生成",
    "🎯 岗位匹配",
])

# ════════════════════════════════════════════════
# Tab 1: 简历上传与分析
# ════════════════════════════════════════════════
with tab1:
    col1, col2 = st.columns([1, 1])

    with col1:
        st.subheader("上传简历")
        uploaded_file = st.file_uploader(
            "选择简历文件 (PDF 或 DOCX)",
            type=["pdf", "docx"],
            key="resume_uploader",
        )

        job_intent = st.text_input(
            "求职意向（目标岗位）",
            placeholder="例如：高级 Python 后端工程师",
            key="job_intent",
        )

        col_analyze, col_clear = st.columns([1, 1])
        with col_analyze:
            analyze_btn = st.button("🔍 开始分析", type="primary", use_container_width=True)
        with col_clear:
            if st.button("🔄 重置", use_container_width=True):
                for key in ["resume", "analysis", "suggestions", "optimized_resume",
                            "rag_references", "job_match"]:
                    st.session_state[key] = None
                st.rerun()

    with col2:
        st.subheader("简历预览")
        if st.session_state.resume:
            resume: Resume = st.session_state.resume
            st.text_area("原始文本", resume.raw_text, height=400)
        elif uploaded_file is not None:
            st.info("点击「开始分析」按钮处理简历")
        else:
            st.info("请上传简历文件")

    # 分析逻辑
    if analyze_btn:
        if not uploaded_file:
            st.error("请先上传简历文件")
        elif not api_key:
            st.error("请先在侧边栏配置 API Key")
        else:
            with st.spinner("正在解析简历..."):
                # 保存上传文件到临时位置
                temp_dir = Path("_temp_uploads")
                temp_dir.mkdir(exist_ok=True)
                temp_path = temp_dir / uploaded_file.name
                temp_path.write_bytes(uploaded_file.getvalue())

                # 解析简历
                resume_obj = parse_resume(temp_path)
                if resume_obj is None or not resume_obj.raw_text.strip():
                    st.error("无法解析简历内容，请检查文件格式")
                else:
                    st.session_state.resume = resume_obj
                    st.success("简历解析完成！")

            with st.spinner("AI 正在分析简历..."):
                try:
                    # 1. 简历分析
                    analysis_agent = ResumeAnalysisAgent()
                    analysis = analysis_agent.analyze(resume_obj)
                    st.session_state.analysis = analysis

                    # 2. RAG 检索
                    rag_agent = RAGRetrievalAgent()
                    rag_results = rag_agent.retrieve_by_analysis(analysis)
                    st.session_state.rag_references = rag_agent.format_results(rag_results)

                    st.success("简历分析完成！请查看「优化建议」标签页。")
                except Exception as e:
                    st.error(f"分析过程中出错: {e}")

    # 显示分析结果摘要
    if st.session_state.analysis:
        with st.expander("📊 分析结果摘要", expanded=True):
            analysis = st.session_state.analysis
            col_score, col_strengths, col_weak = st.columns([1, 2, 2])

            with col_score:
                score = analysis.get("overall_score", "N/A")
                st.metric("综合评分", f"{score}/10")

            with col_strengths:
                st.markdown("**✅ 优势**")
                for s in analysis.get("strengths", []):
                    st.markdown(f"- {s}")

            with col_weak:
                st.markdown("**⚠️ 待改进**")
                for w in analysis.get("weaknesses", []):
                    st.markdown(f"- **{w.get('aspect', '')}**: {w.get('detail', '')}")

# ════════════════════════════════════════════════
# Tab 2: 优化建议
# ════════════════════════════════════════════════
with tab2:
    if not st.session_state.analysis:
        st.info("请先在「简历上传与分析」标签页上传并分析简历")
    else:
        st.subheader("💡 简历优化建议")

        col_gen, _ = st.columns([1, 3])
        with col_gen:
            gen_suggestions_btn = st.button("🚀 生成优化建议", type="primary")

        if gen_suggestions_btn:
            with st.spinner("AI 正在生成优化建议..."):
                try:
                    optimization_agent = OptimizationAgent()
                    suggestions = optimization_agent.generate_suggestions(
                        analysis=st.session_state.analysis,
                        rag_references=st.session_state.rag_references or "",
                        job_intent=job_intent or "",
                    )
                    st.session_state.suggestions = suggestions
                    st.success("优化建议生成完成！")
                except Exception as e:
                    st.error(f"生成建议时出错: {e}")

        if st.session_state.suggestions:
            suggestions = st.session_state.suggestions

            # 整体策略
            st.markdown("### 📌 整体策略")
            st.info(suggestions.get("overall_strategy", ""))

            # 内容优化项
            st.markdown("### 📝 内容优化")
            optimizations = suggestions.get("content_optimizations", [])
            for i, opt in enumerate(optimizations, 1):
                with st.expander(f"{i}. {opt.get('section', '')}"):
                    st.markdown(f"**问题**: {opt.get('original', '')}")
                    st.markdown(f"**建议**: {opt.get('suggestion', '')}")
                    if opt.get("example"):
                        st.markdown(f"**示例**:")
                        st.code(opt.get("example", ""))

            # 关键词
            st.markdown("### 🔑 推荐关键词")
            keywords = suggestions.get("keywords", [])
            if keywords:
                st.markdown(" ".join([f"`{k}`" for k in keywords]))

            # 格式建议
            st.markdown("### 📐 格式建议")
            for f_sug in suggestions.get("format_suggestions", []):
                st.markdown(f"- {f_sug}")

            # 针对性调整
            st.markdown("### 🎯 针对性调整")
            st.write(suggestions.get("job_targeting", ""))

            # 优先行动
            st.markdown("### ⭐ 优先行动项")
            for action in suggestions.get("priority_actions", []):
                st.markdown(f"- **{action}**")

            # RAG 参考
            if st.session_state.rag_references:
                with st.expander("📚 优秀简历参考（RAG）"):
                    st.text(st.session_state.rag_references)

# ════════════════════════════════════════════════
# Tab 3: 简历生成
# ════════════════════════════════════════════════
with tab3:
    if not st.session_state.suggestions:
        st.info("请先在「优化建议」标签页生成优化建议")
    else:
        st.subheader("✨ 生成优化简历")

        col_gen2, _ = st.columns([1, 3])
        with col_gen2:
            gen_resume_btn = st.button("📄 生成优化简历", type="primary")

        if gen_resume_btn:
            with st.spinner("AI 正在生成优化简历..."):
                try:
                    generation_agent = ResumeGenerationAgent()
                    optimized = generation_agent.generate(
                        original_resume=st.session_state.resume,
                        suggestions=st.session_state.suggestions,
                        job_intent=job_intent or "",
                    )
                    st.session_state.optimized_resume = optimized
                    st.success("优化简历生成完成！")
                except Exception as e:
                    st.error(f"生成简历时出错: {e}")

        if st.session_state.optimized_resume:
            optimized = st.session_state.optimized_resume

            # 显示对比
            tab_original, tab_optimized = st.tabs(["原始简历", "优化简历"])

            with tab_original:
                if st.session_state.resume:
                    st.text_area("", st.session_state.resume.to_text(), height=500)

            with tab_optimized:
                st.markdown(optimized)

            # 导出
            st.divider()
            col_dl1, col_dl2 = st.columns([1, 3])

            with col_dl1:
                saved = save_generated_resume(optimized, "optimized_resume.md")
                with open(saved, "rb") as f:
                    st.download_button(
                        label="📥 下载优化简历 (Markdown)",
                        data=f,
                        file_name="optimized_resume.md",
                        mime="text/markdown",
                        use_container_width=True,
                    )
            with col_dl2:
                st.info(f"文件已保存至: {saved}")

# ════════════════════════════════════════════════
# Tab 4: 岗位匹配
# ════════════════════════════════════════════════
with tab4:
    if not st.session_state.resume:
        st.info("请先在「简历上传与分析」标签页上传简历")
    else:
        st.subheader("🎯 岗位匹配分析")

        job_desc = st.text_area(
            "粘贴岗位描述 (JD)",
            placeholder="请粘贴 Boss 直聘或其他平台的岗位描述...",
            height=200,
        )

        col_match, _ = st.columns([1, 3])
        with col_match:
            match_btn = st.button("🎯 分析匹配度", type="primary")

        if match_btn:
            if not job_desc.strip():
                st.error("请先输入岗位描述")
            else:
                with st.spinner("AI 正在分析匹配度..."):
                    try:
                        job = JobRequirement(description=job_desc)
                        # 尝试从 JD 中提取结构化信息
                        try:
                            extract_prompt = f"""从以下岗位描述中提取结构化信息并以JSON格式返回：
{job_desc}

{{"title": "岗位名称", "company": "公司名称", "salary_range": "薪资范围", "responsibilities": ["职责1"], "requirements": ["要求1"]}}
"""
                            from openai import OpenAI
                            client = OpenAI(api_key=api_key, base_url=LLM_BASE_URL)
                            from config import LLM_BASE_URL, LLM_MODEL_NAME
                            resp = client.chat.completions.create(
                                model=LLM_MODEL_NAME,
                                messages=[{"role": "user", "content": extract_prompt}],
                                response_format={"type": "json_object"},
                                temperature=0.1,
                            )
                            job_data = json.loads(resp.choices[0].message.content)
                            job = JobRequirement(**{k: v for k, v in job_data.items()
                                                     if k in JobRequirement.model_fields})
                        except Exception:
                            job = JobRequirement(description=job_desc)

                        matching_agent = JobMatchingAgent()
                        match_result = matching_agent.match(
                            resume=st.session_state.resume,
                            job=job,
                        )
                        st.session_state.job_match = match_result
                        st.success("匹配分析完成！")
                    except Exception as e:
                        st.error(f"匹配分析时出错: {e}")

        if st.session_state.job_match:
            match = st.session_state.job_match

            # 匹配度评分
            score = match.get("match_score", 0)
            col_m1, col_m2, col_m3 = st.columns(3)

            with col_m1:
                st.metric("匹配度", f"{score}/100")
                st.progress(score / 100)

            with col_m2:
                st.markdown("**✅ 匹配优势**")
                for s in match.get("match_strengths", []):
                    st.markdown(f"- {s}")

            with col_m3:
                st.markdown("**❌ 差距分析**")
                for g in match.get("match_gaps", []):
                    st.markdown(f"- **{g.get('requirement', '')}**: {g.get('current_status', '')}")

            # 关键词匹配
            st.markdown("### 🔑 关键词匹配")
            kw_match = match.get("keyword_match", {})
            col_kw1, col_kw2 = st.columns(2)

            with col_kw1:
                st.markdown("**已匹配关键词**")
                for kw in kw_match.get("matched", []):
                    st.markdown(f"✅ `{kw}`")

            with col_kw2:
                st.markdown("**缺失关键词**")
                for kw in kw_match.get("missing", []):
                    st.markdown(f"❌ `{kw}`")

            # 具体建议
            st.markdown("### 📋 具体改进建议")
            for action in match.get("specific_actions", []):
                st.markdown(f"- {action}")

            # 生成针对性简历
            st.divider()
            st.markdown("### 📄 生成针对性简历")
            if st.button("生成针对该岗位的优化简历", type="primary"):
                with st.spinner("正在生成针对性简历..."):
                    try:
                        gen_agent = ResumeGenerationAgent()
                        targeted_resume = gen_agent.generate_by_template(
                            original_resume=st.session_state.resume,
                            job_description=job_desc,
                        )
                        st.session_state.optimized_resume = targeted_resume
                        st.success("针对性简历生成完成！请到「简历生成」标签页查看。")
                    except Exception as e:
                        st.error(f"生成时出错: {e}")

# ─── 页脚 ───────────────────────────────────────
st.divider()
st.caption("AI 简历优化助手 | 基于 RAG + Agent 技术构建 | 数据仅保存在本地")
