# AI 简历优化助手 - 项目框架

## 项目概述
基于目标岗位驱动的智能简历优化工具。用户上传简历并输入意向岗位名称（或粘贴JD），系统自动分析差距、生成手术式优化改动、形成匹配闭环，并支持LLM动态排版PDF下载。

**核心理念**：不编造经历，只做手术式微调。DiffAgent 精确定位+DiffApplier机械应用，未改动内容100%保留原文。匹配度不达标时自动循环优化。

## 技术栈

| 层级 | 技术选型 | 说明 |
|------|----------|------|
| 前端 UI | Streamlit | 单页流程式交互界面 |
| LLM | DeepSeek / OpenAI | 默认 DeepSeek（兼容 OpenAI SDK） |
| 文档解析 | PyMuPDF + python-docx | 支持 PDF 和 DOCX 格式简历 |
| PDF 生成 | Playwright + Chromium + StyleAgent | LLM动态生成HTML + 无头浏览器渲染 |
| 数据模型 | Pydantic v2 | 结构化的简历和岗位数据模型 |
| 模糊匹配 | thefuzz | DiffApplier 原文定位用 |

## 系统架构

```
用户上传简历 + 输入岗位名/JD
           │
           ▼
   ┌─ Step 1: 简历解析（PDF/DOCX → raw_text）
   │
   ├─ Step 1.5: 结构化提取（LLM 将 raw_text 解析为完整的 Resume 对象）
   │
   ├─ Step 2: 岗位画像（with Reflection）
   │
   ├─ Step 2.5: 简历深度分析（with Reflection）
   │
   ├─ Step 3: 差距分析（with Reflection）
   │
   ├─ Step 4: 优化建议（with Reflection）
   │
   ├─ Step 5-6: 简历生成 + 匹配闭环
   │   ┌──────────────────────────────────┐
   │   │ DiffAgent → DiffApplier           │
   │   │   → CoherenceReviewer             │
   │   │   → JobMatchingAgent              │
   │   │   ├─ score >= 70 → 通过           │
   │   │   └─ score < 70                   │
   │   │       → uncovered_gaps → DiffAgent │
   │   │       最多2轮，取最高分             │
   │   └──────────────────────────────────┘
   │
   └─ Step 7: PDF渲染（StyleAgent → HTML → Playwright Chromium → PDF下载）
```

## 双输入模式

| 模式 | 输入 | 处理方式 |
|------|------|----------|
| 仅岗位名 | 用户输入「高级Java开发工程师」 | LLM 根据行业经验自动补全该岗位的典型职责、技能要求、关键词 |
| 完整JD | 用户粘贴招聘JD原文 | LLM 精确提取结构化的岗位要求，匹配更精准 |

两种模式输出统一的 `JobRequirement` 对象，下游Agent无需区分。

## 模块设计

### 1. Agent 模块 (`agents/`)

| Agent | 文件 | 功能 |
|-------|------|------|
| ResumeAnalysisAgent | `resume_analysis_agent.py` | (1) `extract_structured_resume()` 提取结构化Resume；(2) `analyze()` 深度分析优势/薄弱环节 |
| RoleAnalyzerAgent | `role_analyzer_agent.py` | 岗位画像生成：`analyze_from_title()` 和 `analyze_from_jd()` |
| GapAnalyzerAgent | `gap_analyzer_agent.py` | 简历 vs 岗位差距分析：隐式技能推断、关键词匹配、对齐点识别 |
| OptimizationAgent | `optimization_agent.py` | 基于gap分析生成优化建议 |
| DiffAgent | `diff_agent.py` | 生成手术式改动清单（DiffResult），精确定位每条改动的target路径 |
| DiffApplier | `diff_applier.py` | 纯Python引擎，机械执行DiffResult到Resume对象（无LLM调用） |
| CoherenceReviewer | `coherence_reviewer.py` | 审查改动后简历的全文连贯性（衔接、一致性、对齐） |
| ResumeGenerationAgent | `resume_generation_agent.py` | 调度 DiffAgent + DiffApplier + CoherenceReviewer 完成增量优化 |
| JobMatchingAgent | `job_matching_agent.py` | 匹配度分析 + 输出未覆盖差距（uncovered_gaps）驱动再优化 |
| MatchLoop | `match_loop.py` | 匹配闭环引擎：生成→打分→不通过→反馈→再生成（最多2轮） |
| ReflectionLoop | `reflection_loop.py` | 通用自省评估循环：调用Agent→独立评估→不通过注入critique重试 |

### 2. 评估器模块 (`evaluators/`)

| 评估器 | 文件 | 评估目标 |
|--------|------|----------|
| BaseEvaluator | `base_evaluator.py` | 抽象基类，定义 evaluate() 接口和 EvaluationResult |
| ResumeAnalysisEvaluator | `resume_analysis_evaluator.py` | 简历分析的深度感+保真度 |
| RoleAnalyzerEvaluator | `role_analyzer_evaluator.py` | 岗位画像的抓重点+一致性 |
| GapAnalyzerEvaluator | `gap_analyzer_evaluator.py` | 差距分析的内部一致性+保真度+深度感 |
| OptimizationEvaluator | `optimization_evaluator.py` | 优化建议的抓重点+深度感 |

### 3. PDF生成模块 (`generators/`)

```
generators/
├── style_agent.py             # LLM动态HTML生成（4种风格：minimal/professional/creative/compact）
├── template_engine.py         # StyleAgent 包装器（提供 list_templates + render 接口）
├── pdf_renderer.py            # Playwright + Chromium → PDF渲染
├── template_config.yaml       # 已废弃（保留兼容）
└── templates/                 # 已废弃（保留兼容）
```

### 4. 数据模型 (`models/`)

**Resume** (`resume.py`)：完整简历模型
- 基本信息：name, phone, email, title, summary
- 教育：Education（school, degree, major, dates）
- 工作：WorkExperience（company, position, dates, responsibilities, achievements）
- 项目：Project（name, role, dates, description, highlights, tech_stack）
- 技能：Skill（category, items）
- 每个子模型都有 `change_type` 字段（keep/modified/restructured/new_wording）

**Diff相关** (`resume.py`)：
- DiffAction：改动类型枚举（rewrite/append/reorder/highlight/delete）
- DiffChange：单条改动（target路径+action+原文+改后+原因）
- DiffResult：改动清单（changes[]+unchanged_summary+estimated_impact）
- CoherenceReview：连贯性审查结果（score+passed+issues+patches）

**JobRequirement** (`job.py`)：岗位需求画像
- 基本信息：title, company, salary_range, location, level, industry
- 要求：responsibilities, requirements（硬性要求）, preferred（加分项）
- 关键词：tech_keywords, soft_skills
- 来源标注：source（"jd" / "title"）

### 5. 工具层 (`utils/`)

- **resume_parser.py**: PDF/DOCX 简历解析为原始文本（PyMuPDF + python-docx）
- **file_utils.py**: 文件上传、保存、路径管理

### 6. 配置 (`config.py`)

精简配置，仅包含：
- 项目路径（PROJECT_ROOT, OUTPUT_PATH）
- LLM 配置（API Key, Base URL, Model Name）

## 数据流（完整Pipeline）

```
用户上传PDF/DOCX + 输入岗位名 [+ 粘贴JD]
           │
           ▼
    parse_resume() → raw_text
           │
           ▼
    extract_structured_resume(raw_text) → 完整Resume
           │
           ▼
    RoleAnalyzer（with Reflection）→ JobRequirement
           │
           ▼
    ResumeAnalysisAgent.analyze()（with Reflection）→ 优势/薄弱点
           │
           ▼
    GapAnalyzer（with Reflection）
        ├── implicit_skills
        ├── keyword_match
        ├── alignment_points
        └── gaps / restructure_plan
           │
           ▼
    OptimizationAgent（with Reflection）
        ├── overall_strategy
        ├── content_optimizations
        ├── keywords_to_add
        └── priority_actions
           │
           ▼
  ┌─ MatchLoop（匹配闭环，最多2轮）─┐
  │  DiffAgent → DiffApplier         │
  │    → CoherenceReviewer           │
  │    → JobMatchingAgent            │
  │  ┌─ score >= 70 → 输出          │
  │  └─ score < 70 → uncovered_gaps │
  │      → 回DiffAgent再改          │
  └──────────────────────────────────┘
           │
    optimized_resume + match_result
           │
           ▼
    StyleAgent.render(resume, style) → HTML含内联CSS
           │
           ▼
    PDFRenderer.render_to_bytes(html) → PDF下载
```

## 目录结构

```
boss_help/
├── project_framework.md          # 本框架文档
├── requirements.txt              # Python 依赖
├── config.py                     # 配置文件（精简）
├── app.py                        # Streamlit 主入口
├── agents/
│   ├── __init__.py
│   ├── resume_analysis_agent.py  # 结构化提取 + 深度分析
│   ├── role_analyzer_agent.py    # 岗位画像生成（双模式）
│   ├── gap_analyzer_agent.py     # 差距分析（隐式技能推断）
│   ├── optimization_agent.py     # 优化建议生成
│   ├── diff_agent.py             # 手术式改动清单生成
│   ├── diff_applier.py           # 纯Python改动应用引擎
│   ├── coherence_reviewer.py     # 全文连贯性审查
│   ├── resume_generation_agent.py # 简历生成（调度Diff管线）
│   ├── job_matching_agent.py     # 岗位匹配分析 + uncovered_gaps
│   ├── match_loop.py             # 匹配闭环引擎
│   └── reflection_loop.py        # 通用自省评估循环
├── evaluators/
│   ├── __init__.py
│   ├── base_evaluator.py         # 评估器基类 + EvaluationResult
│   ├── resume_analysis_evaluator.py
│   ├── role_analyzer_evaluator.py
│   ├── gap_analyzer_evaluator.py
│   └── optimization_evaluator.py
├── generators/
│   ├── __init__.py
│   ├── style_agent.py            # LLM动态HTML生成
│   ├── template_engine.py        # StyleAgent包装器
│   ├── pdf_renderer.py           # PDF渲染器
│   ├── template_config.yaml      # 已废弃
│   └── templates/                # 已废弃
├── models/
│   ├── __init__.py
│   ├── resume.py                 # Resume + Diff模型
│   └── job.py                    # JobRequirement
├── utils/
│   ├── __init__.py
│   ├── file_utils.py
│   └── resume_parser.py          # PDF/DOCX 解析
├── test/
│   ├── test_resume_analysis.py
│   ├── test_role_analyzer.py
│   ├── test_gap_analyzer.py
│   ├── test_reflection_loop.py
│   └── test_diff_applier.py
└── output/                       # 产物输出目录
    └── .gitkeep
```

## TODO（后续迭代）
- [ ] 多轮对话式简历优化（用户反馈 → Agent重新调整）
- [ ] DiffApplier 支持 reorder action
- [ ] 简历优化历史记录与版本对比
- [ ] Boss 直聘岗位自动筛选与匹配
