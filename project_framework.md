# AI 简历优化助手 - 项目框架

## 项目概述
基于目标岗位驱动的智能简历优化工具。用户上传简历并输入意向岗位名称（或粘贴JD），系统自动分析差距、生成优化建议、输出优化后的简历，并支持多模板PDF下载。

**核心理念**：不依赖外部简历库，优化完全基于目标岗位画像和LLM对行业标准的理解。**不编造经历，只重构和润色**。

## 技术栈

| 层级 | 技术选型 | 说明 |
|------|----------|------|
| 前端 UI | Streamlit | 单页流程式交互界面 |
| LLM | DeepSeek / OpenAI | 默认 DeepSeek（兼容 OpenAI SDK） |
| 文档解析 | PyMuPDF + python-docx | 支持 PDF 和 DOCX 格式简历 |
| PDF 生成 | Playwright + Chromium + Jinja2 | HTML模板 + 无头浏览器渲染，支持多套排版风格 |
| 数据模型 | Pydantic v2 | 结构化的简历和岗位数据模型 |

## 系统架构

```
用户上传简历 + 输入岗位名/JD
           │
           ▼
   ┌─ Step 1: 简历解析（PDF/DOCX → raw_text）
   │
   ├─ Step 1.5: 结构化提取（LLM 将 raw_text 解析为完整的 Resume 对象）
   │
   ├─ Step 2: 岗位画像（岗位名 → LLM补全 / JD → LLM提取）
   │          输出：JobRequirement（职责、要求、关键词、层级等）
   │
   ├─ Step 2.5: 简历深度分析（识别优势、薄弱环节）
   │
   ├─ Step 3: 差距分析（GapAnalyzer — 语义推断隐式技能、关键词匹配、对齐点识别）
   │
   ├─ Step 4: 优化建议（OptimizationAgent — 基于gap和岗位画像生成建议）
   │
   ├─ Step 5: 简历生成（ResumeGenerationAgent — 基于原始简历修改，禁止编造）
   │          输出：完整结构化Resume（带change_type标注）
   │
   ├─ Step 6: 匹配度分析（JobMatchingAgent — 优化后简历 vs 岗位画像）
   │
   └─ Step 7: PDF渲染（Jinja2 HTML模板 + Playwright Chromium → PDF下载）
              支持3种模板：Modern / Classic / Compact
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
| ResumeAnalysisAgent | `resume_analysis_agent.py` | 两个职责：(1) `extract_structured_resume()` 从raw_text提取完整结构化Resume；(2) `analyze()` 深度分析优势/薄弱环节 |
| RoleAnalyzerAgent | `role_analyzer_agent.py` | 岗位画像生成：`analyze_from_title()`（岗位名→推测）和 `analyze_from_jd()`（JD→提取） |
| GapAnalyzerAgent | `gap_analyzer_agent.py` | 简历 vs 岗位差距分析，核心功能：**隐式技能推断**（从项目/工作描述推断未显式列出的技能）、关键词匹配、对齐点识别、重组建议 |
| OptimizationAgent | `optimization_agent.py` | 基于gap分析和岗位画像生成具体优化建议（整体策略、逐项优化、关键词、格式、优先行动） |
| ResumeGenerationAgent | `resume_generation_agent.py` | 基于原始简历生成优化版。**三重保障防编造**：Prompt禁止编造字段 + `_validate_completeness()` 逐条校验（公司/职位/日期/项目名被篡改则自动回退原始数据） + `少改优于多改`策略 |
| JobMatchingAgent | `job_matching_agent.py` | 优化后简历与岗位画像的匹配度分析（评分、优势、gap、关键词匹配） |

### 2. PDF生成模块 (`generators/`)

```
generators/
├── template_engine.py       # Jinja2模板引擎，CSS内嵌处理
├── pdf_renderer.py           # Playwright + Chromium → PDF渲染
├── template_config.yaml      # 模板元数据（名称/描述）
└── templates/
    ├── modern/               # 现代简约：双栏布局，蓝色主色调，适合IT/互联网
    │   ├── template.html
    │   └── style.css
    ├── classic/              # 经典传统：单栏衬线字体，适合金融/法律/制造业
    │   ├── template.html
    │   └── style.css
    └── compact/              # 紧凑单页：高信息密度，适合校招/初级岗位
        ├── template.html
        └── style.css
```

### 3. 数据模型 (`models/`)

**Resume** (`resume.py`)：完整简历模型
- 基本信息：name, phone, email, title, summary
- 教育：Education（school, degree, major, dates）
- 工作：WorkExperience（company, position, dates, responsibilities, achievements）
- 项目：Project（name, role, dates, description, highlights, tech_stack）
- 技能：Skill（category, items）
- 每个子模型都有 `change_type` 字段（keep/modified/restructured/new_wording），用于标注优化修改类型

**JobRequirement** (`job.py`)：岗位需求画像
- 基本信息：title, company, salary_range, location, level, industry
- 要求：responsibilities, requirements（硬性要求）, preferred（加分项）
- 关键词：tech_keywords, soft_skills
- 来源标注：source（"jd" / "title"）

### 4. 工具层 (`utils/`)

- **resume_parser.py**: PDF/DOCX 简历解析为原始文本（PyMuPDF + python-docx）
- **file_utils.py**: 文件上传、保存、路径管理

### 5. 配置 (`config.py`)

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
    extract_structured_resume(raw_text) → 完整Resume（所有字段已填充）
           │
           ▼
    RoleAnalyzer → JobRequirement（岗位画像）
           │
           ▼
    ResumeAnalysisAgent.analyze() → 优势/薄弱点
           │
           ▼
    GapAnalyzer.analyze(resume=Resume, job=JobRequirement, resume_analysis)
        ├── implicit_skills: 从经历推断隐式技能
        ├── keyword_match: 匹配/缺失/不够突出
        ├── alignment_points: 经历-岗位对齐点
        └── gaps / restructure_plan: 差距和重组建议
           │
           ▼
    OptimizationAgent.generate_suggestions(gap_analysis, job)
        ├── overall_strategy: 整体策略
        ├── content_optimizations: 逐项优化建议
        ├── keywords_to_add: 建议强调的关键词
        └── priority_actions: 优先行动项
           │
           ▼
    ResumeGenerationAgent.generate(original_resume, suggestions, job)
        ├── Prompt约束: 禁止编造公司/职位/日期/项目名
        ├── LLM生成优化后JSON
        ├── _validate_completeness(): 校验+回退虚假字段
        └── 输出: 完整Resume（带change_type标注）
           │
           ▼
    JobMatchingAgent.match(optimized_resume, job) → 匹配度报告
           │
           ▼
    TemplateEngine.render(resume, job_title, template_id) → HTML
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
├── app.py                        # Streamlit 主入口（单页3Tab）
├── agents/
│   ├── __init__.py
│   ├── resume_analysis_agent.py  # 结构化提取 + 深度分析
│   ├── role_analyzer_agent.py    # 岗位画像生成（双模式）
│   ├── gap_analyzer_agent.py     # 差距分析（隐式技能推断）
│   ├── optimization_agent.py     # 优化建议生成
│   ├── resume_generation_agent.py # 简历生成（防编造三重保障）
│   └── job_matching_agent.py     # 岗位匹配分析
├── generators/
│   ├── __init__.py
│   ├── template_engine.py        # Jinja2 模板引擎
│   ├── pdf_renderer.py           # PDF 渲染器
│   ├── template_config.yaml      # 模板配置
│   └── templates/                # 3套HTML/CSS简历模板
├── models/
│   ├── __init__.py
│   ├── resume.py                 # Resume + 子模型（含change_type）
│   └── job.py                    # JobRequirement
├── utils/
│   ├── __init__.py
│   ├── file_utils.py
│   └── resume_parser.py          # PDF/DOCX 解析
└── output/                       # 产物输出目录
    └── .gitkeep
```

## TODO（后续迭代）
- [ ] 多轮对话式简历优化（用户反馈 → Agent重新调整）
- [ ] 批量简历优化
- [ ] 更多PDF模板（中英文双语、创意行业风格）
- [ ] 简历优化历史记录与版本对比
- [ ] Boss 直聘岗位自动筛选与匹配
