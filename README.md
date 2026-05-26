# AI 简历优化助手

基于目标岗位驱动的智能简历优化工具。上传简历 + 输入意向岗位，自动分析差距、手术式微调简历、匹配闭环优化、动态排版 PDF、生成面试准备材料。

## 核心特性

- **手术式微调**：DiffAgent 精确定位改动位置，DiffApplier 机械执行，未改动内容 100% 保留原文
- **匹配闭环**：优化后自动打分，不达标则带着未覆盖差距重新优化（最多 2 轮，取最高分）
- **自省评估**：关键分析环节由独立评估器打分，不通过自动注入反馈重试
- **LLM 动态排版**：4 种风格（极简/商务/创意/紧凑），无需维护固定 HTML 模板
- **面试准备**：基于 gap 分析 + 牛客网/CSDN 真实面经，生成针对性面试 Q&A
- **MCP 支持**：面试准备工具可作为 MCP Server 被外部客户端调用

## 快速开始

### 1. 环境准备

```bash
git clone https://github.com/fangxuanyu123/boss_help.git
cd boss_help
pip install -r requirements.txt
playwright install chromium
```

### 2. 配置 LLM

复制 `.env.example` 或直接创建 `.env`：

```env
LLM_API_KEY=your_api_key
LLM_BASE_URL=https://api.deepseek.com
LLM_MODEL_NAME=deepseek-chat
```

### 3. 启动

```bash
streamlit run app.py
```

### 4. 使用

1. 上传简历（PDF/DOCX）
2. 填写意向岗位名称（可粘贴 JD 提高精准度）
3. 点击「开始优化」
4. 在 Tab 1-4 查看结果

## 工作流程

```
上传简历 → 解析 → 结构化提取
    → 岗位画像 → 简历分析 → 差距分析 → 优化建议
    → Diff手术微调 → 连贯性审查
    → 匹配度打分 → (不通过→回Diff再改) × 2轮
    → 动态排版PDF
    → 牛客/CSDN面经搜索 → 面试准备
```

## 项目结构

```
boss_help/
├── app.py                    # Streamlit 主入口
├── config.py                 # 配置（LLM Key/URL/Model）
├── agents/                   # 11 个 Agent
│   ├── diff_agent.py         # 手术式改动清单生成
│   ├── diff_applier.py       # 机械应用改动（无LLM）
│   ├── coherence_reviewer.py # 全文连贯性审查
│   ├── match_loop.py         # 匹配闭环引擎
│   ├── interview_prep_agent.py # 面试准备
│   └── reflection_loop.py    # 自省评估循环
├── evaluators/               # 3 个评估器
├── generators/               # PDF生成（StyleAgent + Playwright）
├── mcp_server/               # MCP Server
│   ├── server.py             # 面试准备工具
│   └── mianjing_search.py    # 牛客/CSDN面经搜索
├── models/                   # Pydantic 数据模型
├── utils/                    # 工具（简历解析）
└── test/                     # 6 个测试文件
```

## 测试

```bash
# 运行全部测试
python -m pytest test/ -v

# 单独测试面试准备
python test/test_interview_prep.py --skip-llm

# 单独测试 DiffApplier
python -m pytest test/test_diff_applier.py -v
```

## MCP 使用

在 Claude Desktop 配置中添加：

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

## License

MIT
