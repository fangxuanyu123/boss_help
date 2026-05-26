# AI 简历优化助手 - 项目框架

## 项目概述
基于目标岗位驱动的智能简历优化工具。上传简历+输入意向岗位，系统自动分析差距、生成手术式优化改动、匹配闭环迭代、LLM动态排版PDF、生成面试准备材料。

**核心理念**：不编造经历，只做手术式微调。DiffAgent 精确定位+DiffApplier机械应用，未改动内容100%保留原文。匹配度不达标时自动循环优化。

## 技术栈

| 层级 | 技术选型 | 说明 |
|------|----------|------|
| 前端 UI | Streamlit | 4个Tab + 侧边栏历史记录 |
| LLM | DeepSeek / OpenAI | 分层模型：FAST(解析/评估) / 默认 / STRONG(面试准备) |
| 文档解析 | PyMuPDF + python-docx | PDF 和 DOCX 格式简历 |
| PDF 生成 | Playwright + StyleAgent | LLM动态生成HTML → 无头浏览器渲染 |
| 浏览器自动化 | Playwright | 牛客网/CSDN 面经搜索（带质量过滤） |
| 数据模型 | Pydantic v2 | 结构化简历、岗位、Diff模型 |
| 持久化 | SQLite | 优化历史自动保存，侧边栏可查 |
| MCP | mcp SDK | 面试准备工具可被外部MCP客户端调用 |
| 评测 | 自研 scorer | 3组金标准用例，5维度自动评分 |

## 系统架构

```
用户上传简历 + 输入岗位名/JD
           │
           ▼
   ┌─ Step 1:    简历解析（PDF/DOCX → raw_text）
   │
   ├─ Step 1.5 + 2:  ┌ 结构化提取（FAST模型）         ┐ 并行
   │                 └ 岗位画像（RoleAnalyzer + Reflection）┘
   │
   ├─ Step 2.5:  简历深度分析（ResumeAnalysisAgent）
   ├─ Step 3:    差距分析（GapAnalyzer + Reflection）
   ├─ Step 4:    优化建议（OptimizationAgent + Reflection）
   │
   ├─ Step 5-6:  简历生成 + 匹配闭环
   │   ┌──────────────────────────────────┐
   │   │ DiffAgent（Few-Shot示例）          │
   │   │   → DiffApplier（机械应用）        │
   │   │   → CoherenceReviewer             │
   │   │   → JobMatchingAgent              │
   │   │   ├─ score >= 70 → 通过           │
   │   │   └─ score < 70                   │
   │   │       → uncovered_gaps → 回Diff   │
   │   │       最多2轮，取最高分             │
   │   └──────────────────────────────────┘
   │
   └─ Step 7 + 8:  ┌ PDF渲染（StyleAgent）      ┐ 并行
                   └ 面试准备（InterviewPrepAgent │
                     + 牛客/CSDN面经搜索）        ┘
```

## 模块设计

### 1. Agent 模块 (`agents/`)

| Agent | 文件 | 功能 |
|-------|------|------|
| ResumeAnalysisAgent | `resume_analysis_agent.py` | 结构化提取 + 深度分析（优势/薄弱环节） |
| RoleAnalyzerAgent | `role_analyzer_agent.py` | 岗位画像：`analyze_from_title()` / `analyze_from_jd()` |
| GapAnalyzerAgent | `gap_analyzer_agent.py` | 差距分析：隐式技能推断、关键词匹配、对齐点识别 |
| OptimizationAgent | `optimization_agent.py` | 基于gap分析生成优化建议 |
| DiffAgent | `diff_agent.py` | 生成手术式改动清单（DiffResult），精确定位target路径 |
| DiffApplier | `diff_applier.py` | 纯Python引擎，机械执行DiffResult到Resume（无LLM） |
| CoherenceReviewer | `coherence_reviewer.py` | 全文连贯性审查（衔接、一致性、对齐） |
| ResumeGenerationAgent | `resume_generation_agent.py` | 调度 DiffAgent + DiffApplier + CoherenceReviewer |
| JobMatchingAgent | `job_matching_agent.py` | 匹配度分析 + uncovered_gaps驱动再优化 |
| MatchLoop | `match_loop.py` | 匹配闭环引擎（最多2轮，取最高分） |
| InterviewPrepAgent | `interview_prep_agent.py` | 面试准备：gap分析 + 真实面经 → 技术问答/短板应对/系统设计/行为面试 |
| ReflectionLoop | `reflection_loop.py` | 通用自省评估循环：调用→评估→不通过→注入critique重试 |

### 2. 评估器模块 (`evaluators/`)

| 评估器 | 文件 | 评估维度 |
|--------|------|----------|
| BaseEvaluator | `base_evaluator.py` | 抽象基类 + EvaluationResult |
| RoleAnalyzerEvaluator | `role_analyzer_evaluator.py` | 抓重点 + 一致性 |
| GapAnalyzerEvaluator | `gap_analyzer_evaluator.py` | 内部一致性 + 保真度 + 深度感 |
| OptimizationEvaluator | `optimization_evaluator.py` | 抓重点 + 深度感 |

### 3. 数据模型 (`models/`)

- **Resume**: 完整简历（name/phone/email/title/summary/education/work_experiences/projects/skills/certifications）
- **JobRequirement**: 岗位需求画像（title/responsibilities/requirements/tech_keywords/level/industry）
- **DiffChange**: 单条改动（target + action + original + rewritten + reason）
- **DiffResult**: 改动清单（changes[] + unchanged_summary + estimated_impact）
- **CoherenceReview**: 连贯性审查（score + passed + issues + patches）

### 4. PDF生成 (`generators/`)

| 组件 | 文件 | 功能 |
|------|------|------|
| StyleAgent | `style_agent.py` | LLM动态生成HTML（4种风格：minimal/professional/creative/compact） |
| TemplateEngine | `template_engine.py` | StyleAgent包装器 |
| PDFRenderer | `pdf_renderer.py` | Playwright → PDF |

### 5. MCP Server (`mcp_server/`)

| 组件 | 文件 | 功能 |
|------|------|------|
| MCP Server | `server.py` | `generate_interview_prep` 工具，stdio transport |
| 面经搜索 | `mianjing_search.py` | Playwright 搜索牛客网 + CSDN 真实面经 |

### 6. 工具层 (`utils/`)

- `resume_parser.py`: PDF/DOCX 简历解析为原始文本
- `file_utils.py`: 文件管理
- `db.py`: SQLite 持久化，保存优化历史记录

### 7. 评测模块 (`eval/`)

- `golden_cases.py`: 3组标注金标准测试用例（Java/Python/嵌入式）
- `scorer.py`: 自动评分脚本，从5个维度评估DiffAgent输出质量

## 完整数据流

```
用户上传简历 + 岗位名 [+ JD]
           │
    简历解析 → 结构化提取 ∥ 岗位画像（并行）
           │
    简历分析 → Gap分析 → 优化建议（Reflection评估）
           │
  ┌─ MatchLoop（最多2轮）──────────────┐
  │   DiffAgent(Few-Shot示例) → DiffApplier │
  │   → CoherenceReviewer                 │
  │   → JobMatchingAgent                  │
  │   通过 → 输出 | 不通过 → uncovered_gaps │
  └───────────────────────────────────────┘
           │
    StyleAgent PDF ∥ 面试准备（并行）
           │
    SQLite 自动保存 → 历史记录侧边栏
```

## 目录结构

```
boss_help/
├── project_framework.md
├── requirements.txt
├── config.py
├── app.py                          # Streamlit 主入口
├── agents/
│   ├── resume_analysis_agent.py
│   ├── role_analyzer_agent.py
│   ├── gap_analyzer_agent.py
│   ├── optimization_agent.py
│   ├── diff_agent.py
│   ├── diff_applier.py
│   ├── coherence_reviewer.py
│   ├── resume_generation_agent.py
│   ├── job_matching_agent.py
│   ├── match_loop.py
│   ├── interview_prep_agent.py
│   └── reflection_loop.py
├── evaluators/
│   ├── base_evaluator.py
│   ├── role_analyzer_evaluator.py
│   ├── gap_analyzer_evaluator.py
│   └── optimization_evaluator.py
├── generators/
│   ├── style_agent.py
│   ├── template_engine.py
│   └── pdf_renderer.py
├── mcp_server/
│   ├── server.py
│   └── mianjing_search.py
├── models/
│   ├── resume.py
│   └── job.py
├── eval/
│   ├── golden_cases.py
│   └── scorer.py
├── utils/
│   ├── resume_parser.py
│   ├── file_utils.py
│   └── db.py
└── test/
    ├── test_diff_applier.py
    ├── test_reflection_loop.py
    ├── test_interview_prep.py
    ├── test_resume_analysis.py
    ├── test_role_analyzer.py
    └── test_gap_analyzer.py
```
