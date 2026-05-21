# Reflection 自省评估框架 - 设计文档

> 为简历优化助手的核心分析环节引入独立评估器 + 带反馈重试机制，提升输出质量可靠性。

## 目标

在现有 Pipeline 中嵌入 Reflection（自省）机制：每个关键 Agent 输出后，由独立评估器评判质量。质量通过则返回给用户，不通过则注入具体反馈（critique）让 Agent 修正，最多重试 2 次。

## 覆盖范围

| 环节 | Agent | 评估器 |
|------|-------|--------|
| 简历深度分析 | ResumeAnalysisAgent.analyze() | ResumeAnalysisEvaluator |
| 岗位画像 | RoleAnalyzerAgent | RoleAnalyzerEvaluator |
| 差距分析 | GapAnalyzerAgent | GapAnalyzerEvaluator |
| 优化建议 | OptimizationAgent | OptimizationEvaluator |

## 架构方案：独立评估器 + 共享循环引擎（方案 B）

```
ReflectionLoop（共享循环逻辑）
  ├── ResumeAnalysisEvaluator
  ├── RoleAnalyzerEvaluator
  ├── GapAnalyzerEvaluator
  └── OptimizationEvaluator
```

每个 Agent 有专属评估器，评估标准针对其输出特点定制。循环逻辑（调用→评估→反馈→重试）在 ReflectionLoop 中统一处理。

## 文件结构

新增文件：
- `agents/reflection_loop.py` — 共享循环引擎
- `evaluators/__init__.py`
- `evaluators/base_evaluator.py` — 评估器基类 + EvaluationResult
- `evaluators/resume_analysis_evaluator.py`
- `evaluators/role_analyzer_evaluator.py`
- `evaluators/gap_analyzer_evaluator.py`
- `evaluators/optimization_evaluator.py`

## 核心流程

```
agent_call() → evaluator.evaluate()
  ├── score >= 6 → 通过，返回结果
  └── score < 6 → retry_count < 2 ?
        ├── 是 → 组装 critique 注入 agent_call()，重新执行
        └── 否 → 取最高分轮次结果返回
```

- 阈值：6/10（有瑕疵但方向对即可通过，避免无限重试）
- 最大重试：2 次
- 兜底：取所有轮次中最高分的结果返回

## Agent 改动（统一、轻量）

每个 Agent 的目标方法新增可选参数 `critique: str | None = None`：
- 为 None → 首次调用，正常 Prompt
- 有值 → system prompt 末尾追加改进反馈

不修改现有 Prompt 结构，仅条件拼接。

## 评估维度设计（聚焦 Prompt 管不住的二阶质量）

评估器不重复 Agent Prompt 已约束的合规检查，只关注 Prompt 无法保证的质量维度：

### 共性维度

| 维度 | 含义 |
|------|------|
| 深度感 | 是否一针见血，还是正确但空洞的套话 |
| 一致性 | 输出各部分之间是否自洽 |
| 保真度 | 对输入数据的引用/推断是否准确，无曲解 |
| 抓重点能力 | 是否抓住最关键的问题，而非被次要信息带偏 |

### 各评估器特有维度

**ResumeAnalysisEvaluator**：深度感（薄弱点是否触及竞争力本质）、保真度（对原文的引用是否真实）

**RoleAnalyzerEvaluator**：抓重点（关键词是否代表了岗位核心壁垒）、一致性（level 与 requirements 难度是否匹配）

**GapAnalyzerEvaluator**：一致性（verdict/gaps/keyword_match/alignment 四者逻辑自洽）、保真度（implicit_skills 推断不过度）、深度感（gaps 是否点到差距根源）

**OptimizationEvaluator**：抓重点（optimizations 是否聚焦最关键问题而非平均用力）、深度感（example 是否真的是好写法）

## app.py 集成

4 个步骤的 Agent 调用用 `reflection_loop.run()` 包裹。初始化 4 个 ReflectionLoop 实例，存储在 session 旁。

评估日志在 Tab 2（分析报告）中展示，每个模块显示质量评分和轮次信息。

## 测试策略

- `test/test_reflection_loop.py`：用 mock evaluator 验证循环逻辑（0/1/2 次重试、阈值边界、取最高分逻辑）
- 现有 3 个测试文件不变
