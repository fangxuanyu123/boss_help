# AI 简历优化助手 - 项目框架

## 项目概述
基于 RAG + Agent 的智能简历优化工具，帮助求职者优化简历、匹配岗位。
后续迭代扩展为 Boss 直聘自动投递 + 每日复盘系统。

## 技术栈

| 层级 | 技术选型 | 说明 |
|------|----------|------|
| 前端 UI | Streamlit | 快速构建交互式 Web 应用 |
| Agent 框架 | LangChain | 多 Agent 编排、工具调用、链式推理 |
| RAG 引擎 | LangChain + ChromaDB | 文档分块、向量化存储、语义检索 |
| LLM | DeepSeek / OpenAI | 默认 DeepSeek（国内可访问），可切换 |
| 文档解析 | PyMuPDF + python-docx | 支持 PDF 和 DOCX 格式简历 |
| 向量嵌入 | text2vec / OpenAI embeddings | 中文简历向量化 |

## 系统架构

```
┌─────────────────────────────────────────────────┐
│                  Streamlit UI                    │
│  (简历上传 / 求职意向输入 / 建议展示 / 简历生成)   │
└──────────────────────┬──────────────────────────┘
                       │
┌──────────────────────▼──────────────────────────┐
│              Orchestrator Agent                  │
│           (协调多个子 Agent 的工作流)              │
└──────┬──────────┬──────────┬────────────────┬───┘
       │          │          │                │
┌──────▼──┐ ┌─────▼─────┐ ┌─▼────────┐ ┌────▼──────┐
│ Resume  │ │   RAG     │ │Optimization│ │  Resume   │
│Analysis │ │ Retrieval │ │Suggestion │ │Generation  │
│ Agent   │ │   Agent   │ │  Agent    │ │  Agent     │
└─────────┘ └─────┬─────┘ └──────────┘ └───────────┘
                  │
         ┌───────▼────────┐
         │   ChromaDB     │
         │  (优秀简历库)   │
         └────────────────┘
```

## 模块设计

### 1. RAG 模块 (`rag/`)
- **document_processor.py**: 简历文档解析、文本提取、分块 (Chunk)
- **embedding.py**: 文本向量化嵌入
- **vector_store.py**: ChromaDB 向量库管理（增删改查）
- **retriever.py**: 语义检索，返回最匹配的优秀简历片段

### 2. Agent 模块 (`agents/`)
- **resume_analysis_agent.py**: 分析用户简历，提取技能、经历、教育等结构化信息，识别薄弱环节
- **rag_retrieval_agent.py**: 根据分析结果，从 RAG 库检索相关优秀简历片段
- **optimization_agent.py**: 结合检索结果生成具体的优化建议
- **resume_generation_agent.py**: 根据建议生成优化后的简历文本
- **job_matching_agent.py**: 分析岗位 JD，给出针对性修改意见

### 3. 数据模型 (`models/`)
- **resume.py**: Resume 数据类（个人信息、工作经历、教育背景、技能等）
- **job.py**: JobRequirement 数据类（岗位需求、职责、要求等）

### 4. 工具层 (`utils/`)
- **file_utils.py**: 文件上传、保存、路径管理等
- **resume_parser.py**: PDF/DOCX 简历解析为结构化数据

### 5. 配置 (`config.py`)
- API 密钥管理
- 模型选择
- 向量库路径
- 知识库路径

## 数据流

```
用户上传简历 + 输入求职意向
        │
        ▼
简历解析 → 结构化 Resume 对象
        │
        ▼
ResumeAnalysisAgent 分析薄弱点
        │
        ▼
RAGRetrievalAgent 检索优秀简历
        │
        ▼
OptimizationAgent 生成优化建议
        │
        ▼
ResumeGenerationAgent 生成优化简历
        │
        ▼
展示对比 → 用户确认 → 导出
```

## 目录结构

```
boss_help/
├── project_framework.md          # 本框架文档
├── requirements.txt              # Python 依赖
├── .env.example                  # 环境变量示例
├── config.py                     # 配置文件
├── app.py                        # Streamlit 主入口
├── agents/
│   ├── __init__.py
│   ├── resume_analysis_agent.py
│   ├── rag_retrieval_agent.py
│   ├── optimization_agent.py
│   ├── resume_generation_agent.py
│   └── job_matching_agent.py
├── rag/
│   ├── __init__.py
│   ├── vector_store.py
│   ├── embedding.py
│   ├── document_processor.py
│   └── retriever.py
├── models/
│   ├── __init__.py
│   ├── resume.py
│   └── job.py
├── utils/
│   ├── __init__.py
│   ├── file_utils.py
│   └── resume_parser.py
├── knowledge_base/
│   └── .gitkeep                  # 优秀简历存放目录
└── output/                       # 生成结果输出
    └── .gitkeep
```

## TODO（后续迭代）
- [ ] Boss 直聘岗位自动筛选
- [ ] 自动投递简历
- [ ] 每日投递复盘总结
- [ ] 多轮对话式简历优化
- [ ] 批量简历优化
