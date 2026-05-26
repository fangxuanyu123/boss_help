# AI Resume Optimizer — 智能简历优化助手

> 基于目标岗位驱动的简历优化工具。上传简历 + 输入岗位名，自动完成「解析 → 分析 → 手术式微调 → 匹配闭环 → PDF 排版 → 面试准备」全流程。

[![Python](https://img.shields.io/badge/Python-3.10+-blue.svg)](https://www.python.org/)
[![Streamlit](https://img.shields.io/badge/Streamlit-1.28+-red.svg)](https://streamlit.io/)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Tests](https://img.shields.io/badge/Tests-16%20passed-brightgreen.svg)](./test/)

---

## 为什么你需要这个工具？

投简历最大的痛点不是「简历写得不好」，而是**你不知道针对某个具体岗位应该怎么改**。大多数人的简历是自己凭感觉写的，投出去石沉大海。

这个工具做三件事：

1. **告诉你差在哪** — 对比简历和目标岗位，找出具体的差距（不是泛泛的「缺乏量化」，而是「在 XX 项目的描述中缺少对系统吞吐量的体现，而这个岗位明确要求高并发系统经验」）
2. **精准地帮你改** — 不是全书重写，而是手术式微调：只改必要的句子，保留你的原文风格，每条改动都可追溯到优化建议
3. **帮你准备面试** — 从你的技能短板和岗位要求出发，结合牛客网 / CSDN 上的真实面经，生成针对性的面试 Q&A

## 核心特性

### 手术式微调，而非全文重写

传统的 LLM 简历优化是「把简历扔给 AI，还你一份全新的」。问题是——AI 写的不是你，读起来像模板。

这个项目采用的是 **Diff-based 增量修改**：

```
原始简历中「负责系统日常维护」
    → DiffAgent 识别：这条应该用 STAR 法则改写
    → 输出改动：写为「主导 XX 系统运维，保障 99.9% 可用性，覆盖日均 50 万+ 请求」
    → DiffApplier 机械应用：只有这条职责被修改，其他 100% 保留原文
```

每处改动都有明确的原因标注和原文引用，你可以逐条审查、逐条接受。

### 匹配闭环：不达标就再改

简历优化不是一次性的。匹配度低于 70 分时，系统会自动提取未覆盖的差距，回传给 DiffAgent 进行第二轮优化，**最多迭代 2 轮，取最高分的结果**。

```
DiffAgent → DiffApplier → CoherenceReviewer → JobMatchingAgent
                                                    │
                                               score < 70 ?
                                                    │
                                           ┌────────┴────────┐
                                           │ 是               │ 否
                                           ▼                  ▼
                                    提取 uncovered_gaps    输出结果
                                    回传 DiffAgent 再改
```

### Reflection 自省评估

Pipeline 中的关键 LLM 调用（岗位画像、差距分析、优化建议）都由**独立评估器**打分。评估器不检查合规性（Prompt 已经管住了），而是评判二阶质量：

- **深度感** — 输出是一针见血还是正确的废话？
- **一致性** — 各部分之间的结论是否自洽？
- **保真度** — 对原始数据的引用是否准确？
- **抓重点** — 是否抓住了最关键的问题？

评分低于 6 分 → 注入具体反馈 → Agent 重新生成，最多重试 2 次。
评分采用 **FAST 模型**（评估不需要强推理），减少 60% 评估成本。

### 性能优化策略

- **并行执行**：Step 1.5 ∥ Step 2、Step 7 ∥ Step 8，省 2 次 LLM 时延
- **分层模型**：结构化提取/评估器 → FAST 模型 | 面试准备 → STRONG 模型 | 其余 → 默认模型
- **Prompt Caching**：固定 system prompt 自动缓存，评估器 100% 可缓存
- **Few-Shot 示例**：DiffAgent Prompt 包含 3 组高质量改动示例，提升输出稳定性

### LLM 动态排版 PDF

放弃固定 HTML 模板，改为 **StyleAgent 按风格动态生成**：

| 风格 | 描述 | 适用场景 |
|------|------|----------|
| Minimal | 极简黑白，单栏，高对比度 | 投递大厂，ATS 友好 |
| Professional | 传统商务，双栏，衬线字体 | 金融 / 法律 / 制造业 |
| Creative | 现代活力，色彩点缀 | 互联网 / 设计 |
| Compact | 紧凑单页，高信息密度 | 校招 / 初级岗位 |

### 面试准备 + 真实面经

Pipeline 完成后，自动生成面试准备材料：

- **技术问答** — 基于岗位关键词 + 技能差距，生成针对性技术面试题
- **短板应对** — 针对简历暴露的短板，准备面试追问的应对策略
- **系统设计** — 高级 / 架构岗位生成系统设计场景
- **行为面试** — 针对经验短板准备行为面试问题

同时通过 Playwright 搜索**牛客网和 CSDN 上的真实面经**标题和链接，作为 LLM 生成的参考，让问题更有实战感。

### 历史记录 + 评测体系

- **SQLite 持久化**：每次优化自动保存到数据库，侧边栏展示历史记录
- **金标准评测**：3 组标注数据（Java/Python/嵌入式），自动评分覆盖改动数量、action类型、板块覆盖、reason质量等维度
- 运行 `python eval/scorer.py` 即可自动评测 DiffAgent 输出质量

### MCP 支持

面试准备工具封装为 MCP Server（`stdio` transport），可被 Claude Desktop 等外部客户端调用：

```json
{
  "mcpServers": {
    "boss-help-interview-prep": {
      "command": "python",
      "args": ["-m", "mcp_server.server"]
    }
  }
}
```

---

## 快速开始

### 1. 克隆 + 安装

```bash
git clone https://github.com/fangxuanyu123/boss_help.git
cd boss_help
pip install -r requirements.txt
playwright install chromium
```

### 2. 配置 LLM

创建 `.env` 文件：

```env
LLM_API_KEY=sk-your-api-key
LLM_BASE_URL=https://api.deepseek.com
LLM_MODEL_NAME=deepseek-chat

# 可选：分层模型（不设置则回退到 LLM_MODEL_NAME）
LLM_MODEL_FAST=deepseek-chat      # 解析/评估用，可換 gpt-4o-mini 降成本
LLM_MODEL_STRONG=deepseek-chat    # 面试准备用，可換 gpt-4o 提质量
```

默认使用 DeepSeek，也支持 OpenAI (`https://api.openai.com/v1`) 或其他兼容接口。

### 3. 启动

```bash
streamlit run app.py
```

浏览器打开 `http://localhost:8501`。

### 4. 使用

1. **上传简历** — 支持 PDF / DOCX 格式
2. **输入目标岗位** — 如「高级Java开发工程师」，可粘贴完整 JD 获得更精准的分析
3. **点击「开始优化」** — Pipeline 自动运行，进度一目了然
4. **查看结果** — 4 个 Tab：
   - 📊 **优化预览** — 每条改动清晰展示原文 / 改后 / 原因
   - 🔬 **分析报告** — 岗位画像、关键词匹配、质量评估
   - 📥 **PDF下载** — 4 种排版风格随心切换
   - 🎯 **面试准备** — 技术问答、短板应对、系统设计、行为面试 + 真实面经链接

---

## 项目架构

### Pipeline 全景

```
上传简历 + 岗位名 / JD
        │
Step 1   ── PDF/DOCX 解析 → raw_text
Step 1.5 ── LLM 结构化提取 → Resume 对象
Step 2   ── 岗位画像生成（RoleAnalyzer，Reflection 评估）
Step 2.5 ── 简历深度分析（ResumeAnalysisAgent）
Step 3   ── 差距分析（GapAnalyzer，Reflection 评估）
Step 4   ── 优化建议（OptimizationAgent，Reflection 评估）
Step 5-6 ── Diff 手术微调 → 连贯性审查 → 匹配打分
            └─ 不达标 → 回传 uncovered_gaps 再改（≤ 2 轮）
Step 7   ── StyleAgent 动态排版 → PDF 下载
Step 8   ── 牛客 / CSDN 面经搜索 → 面试准备 Q&A
```

### 12 个 Agent

| Agent | 职责 |
|-------|------|
| `ResumeAnalysisAgent` | 简历结构化提取 + 优势/薄弱点深度分析 |
| `RoleAnalyzerAgent` | 从岗位名或 JD 生成标准化岗位画像 |
| `GapAnalyzerAgent` | 简历 vs 岗位差距：隐式技能推断、关键词匹配、对齐点 |
| `OptimizationAgent` | 基于差距生成优化建议 |
| **`DiffAgent`** | 生成手术式改动清单（每条精确到 target 路径） |
| **`DiffApplier`** | 纯 Python 机械应用改动（无 LLM，100% 保留未改动内容） |
| **`CoherenceReviewer`** | 全文连贯性审查（衔接、一致性、无矛盾） |
| `ResumeGenerationAgent` | 调度 DiffAgent + DiffApplier + CoherenceReviewer |
| `JobMatchingAgent` | 匹配度打分 + 输出 uncovered_gaps |
| **`MatchLoop`** | 匹配闭环引擎 |
| **`InterviewPrepAgent`** | 基于 gap 分析 + 真实面经生成面试 Q&A |
| **`ReflectionLoop`** | 通用自省评估循环（调用→独立评估→反馈→重试） |

### 3 个独立评估器

| 评估器 | 维度 |
|--------|------|
| `RoleAnalyzerEvaluator` | 抓重点（核心壁垒 vs 辅助工具）、一致性（level 与要求匹配） |
| `GapAnalyzerEvaluator` | 内部一致性（verdict/gaps/keywords 不自相矛盾）、保真度、深度感 |
| `OptimizationEvaluator` | 抓重点（聚焦最关键 2-3 个问题）、深度感（example 是否真的更好） |

### 数据模型（Pydantic v2）

- **Resume** — 完整简历（基本信息、教育、工作、项目、技能、证书）
- **JobRequirement** — 岗位画像（职责、要求、关键词、层级、行业）
- **DiffChange** — 单条改动（`target` 路径 + `action` 类型 + 原文 + 改后 + 原因）
- **DiffResult** — 改动清单（`changes[]` + `unchanged_summary` + `estimated_impact`）
- **CoherenceReview** — 连贯性审查（`score` + `passed` + `issues` + `patches`）

---

## 项目结构

```
boss_help/
├── app.py                              # Streamlit 入口
├── config.py                           # LLM 配置
├── agents/                             # 12 个 Agent
│   ├── resume_analysis_agent.py
│   ├── role_analyzer_agent.py
│   ├── gap_analyzer_agent.py
│   ├── optimization_agent.py
│   ├── diff_agent.py                   # ★ 手术式改动生成
│   ├── diff_applier.py                 # ★ 机械应用改动
│   ├── coherence_reviewer.py           # ★ 连贯性审查
│   ├── resume_generation_agent.py      # Diff 调度器
│   ├── job_matching_agent.py
│   ├── match_loop.py                   # ★ 匹配闭环
│   ├── interview_prep_agent.py         # ★ 面试准备
│   └── reflection_loop.py             # ★ 自省循环
├── evaluators/                         # 3 个评估器
│   ├── base_evaluator.py               # 基类 + EvaluationResult
│   ├── role_analyzer_evaluator.py
│   ├── gap_analyzer_evaluator.py
│   └── optimization_evaluator.py
├── generators/                         # PDF 生成
│   ├── style_agent.py                  # LLM 动态生成 HTML
│   ├── template_engine.py              # StyleAgent 包装器
│   └── pdf_renderer.py                 # Playwright → PDF
├── mcp_server/                         # MCP Server
│   ├── server.py                       # 面试准备工具
│   └── mianjing_search.py             # 牛客/CSDN 面经搜索
├── models/                             # Pydantic 数据模型
│   ├── resume.py                       # Resume + Diff 模型
│   └── job.py                          # JobRequirement
├── eval/                               # 评测模块 ★
│   ├── golden_cases.py                 # 金标准标注数据
│   └── scorer.py                       # 自动评分脚本
├── utils/                              # 工具层
│   ├── resume_parser.py                # PDF/DOCX 解析
│   ├── file_utils.py
│   └── db.py                           # SQLite 持久化
├── test/                               # 6 个测试文件 / 18 个测试函数
│   ├── test_diff_applier.py            # 9 tests
│   ├── test_reflection_loop.py         # 7 tests
│   ├── test_interview_prep.py          # 2 tests (面经搜索 + LLM 生成)
│   ├── test_resume_analysis.py         # 集成测试
│   ├── test_role_analyzer.py           # 集成测试
│   └── test_gap_analyzer.py            # 集成测试
├── docs/superpowers/                   # 设计文档 + 实现计划
├── project_framework.md                # 项目框架文档
├── requirements.txt
└── README.md
```

**代码量**：约 4500 行 Python / 42 个文件

---

## 运行测试

```bash
# 全部测试（LLM 调用较慢）
python -m pytest test/ -v

# 仅快速单元测试（秒级完成）
python -m pytest test/test_diff_applier.py test/test_reflection_loop.py -v

# 独立测试面试准备（仅搜索面经，不调 LLM）
python test/test_interview_prep.py --skip-llm

# 自定义关键词测试面经搜索
python test/test_interview_prep.py --keywords "Go,微服务,K8s,面试" --skip-llm

# 评测 DiffAgent 在金标准数据上的表现
python eval/scorer.py
```

---

## 技术栈

| 层级 | 选型 | 说明 |
|------|------|------|
| UI | Streamlit 1.28+ | 单页多 Tab 流程式交互 |
| LLM | DeepSeek / OpenAI | 兼容 OpenAI SDK，默认 DeepSeek |
| 文档解析 | PyMuPDF + python-docx | PDF / DOCX → 结构化文本 |
| 数据模型 | Pydantic v2 | 完整的类型安全 + 序列化 |
| PDF 渲染 | Playwright + Chromium | StyleAgent 动态生成 HTML → 无头浏览器 |
| 浏览器自动化 | Playwright | 牛客 / CSDN 面经搜索 |
| MCP | `mcp` SDK | 面试准备工具支持外部 MCP 客户端调用 |
| 持久化 | SQLite | 优化历史自动保存，侧边栏查阅 |
| 评测 | 自研 scorer | 3 组金标准标注数据，5 维度自动评分 |

---

## 设计理念

### 不编造经历

这是最核心的原则。所有公司名、职位名、项目名、起止日期与原始简历一字不差。LLM 只能改写职责描述和成果的措辞，不能凭空添加你从未做过的事情。

### 少改优于多改

如果一段职位描述已经写得很好了，就保持原样。改动清单通常只有 5-12 条，而不是全文重写。每条改动都有明确的 `reason` 字段说明为什么改。

### Prompt 管合规，评估器管质量

Agent 的 Prompt 负责约束「不要做什么」（不编造、不报排版问题、不建议去学新技能）。评估器负责评判 Prompt 管不住的二阶质量（深度、一致性、保真度）。两者分工明确，不重复。

---

## License

MIT License
