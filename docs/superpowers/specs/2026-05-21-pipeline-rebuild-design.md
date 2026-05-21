# 简历优化 Pipeline 全面改造 - 设计文档

## 目标

对简历生成(Pipeline Step 5)、匹配度分析(Step 6)、PDF渲染(Step 7)三个核心环节进行三阶段改造：

1. **Diff-based 简历生成** —— 从全文重写改为手术式微调 + 全文连贯性审查
2. **匹配度驱动优化闭环** —— 匹配度分析反哺简历生成，形成"生成→打分→改进"循环
3. **LLM 动态排版** —— 放弃固定HTML模板，让LLM按用户需的风格生成HTML

## 第一阶段：Diff-based 简历生成

### 核心思路

LLM 不再输出完整简历，只输出结构化改动清单。DiffApplier（纯Python）机械执行改动，未涉及内容100%保留原文。

### 架构

```
原始简历 + Gap分析 + 优化建议
           │
           ▼
    ┌─────────────────┐
    │   DiffAgent      │  LLM 输出 DiffResult（改动清单）
    │   分析原始→生成改动│
    └────────┬────────┘
             │ DiffResult
             ▼
    ┌─────────────────┐
    │   DiffApplier    │  纯机械操作，无 LLM
    │   逐条执行改动     │  用 target + original 精确定位
    └────────┬────────┘  未匹配的条目报 warning 跳过
             │ modified_resume : Resume
             ▼
    ┌──────────────────┐
    │ CoherenceReviewer │  LLM 审查全文连贯性
    │ 检查衔接/矛盾/对齐 │  输出修补意见或通过
    └────────┬─────────┘
             │
        ┌────┴────┐
        │ 通过？   │
        └────┬────┘
      是 ↓       ↓ 否 → 小修补 → 再审查（最多1次）
    ┌──────────────┐
    │ 最终 Resume   │
    └──────────────┘
```

### DiffChange 数据结构

```python
class DiffAction(str, Enum):
    rewrite = "rewrite"       # 重写某段文字
    append = "append"         # 补充关键词/数据点
    reorder = "reorder"       # 调整顺序
    highlight = "highlight"   # 把已有但埋没的内容提到更显眼位置
    delete = "delete"         # 删除冗余或不合适的表述

class DiffChange(BaseModel):
    target: str               # "work_experiences[0].responsibilities[2]"
    action: DiffAction
    original: str = ""        # 原文（rewrite/highlight/delete需要，用于精确匹配）
    rewritten: str = ""       # 改写后（rewrite/highlight）
    item: str = ""            # 新增内容（append）
    reason: str               # 为什么这么改，关联gap分析
    section_label: str = ""   # 人类可读的板块名（前端展示用）

class DiffResult(BaseModel):
    changes: list[DiffChange]
    unchanged_summary: str    # LLM说明为什么其他部分没改
    estimated_impact: str     # 预估改动对匹配度的提升
```

### DiffApplier 核心逻辑

纯Python，不做LLM调用。对每条 DiffChange：
1. 解析 `target` 路径（如 `work_experiences[0].responsibilities[2]`）
2. 读取原始 Resume 对象对应字段
3. 用 `original` 做模糊匹配定位（容忍 LLM 输出原文时的细微差异）
4. 执行操作
5. 定位失败 → logger.warning + 跳过

### CoherenceReviewer

输入：修改后的完整 Resume（纯文本格式，标注了哪些部分是改动过的）
输出：
```json
{
    "coherence_score": 8.5,
    "passed": true,
    "issues": [],
    "patches": []
}
```

如果不通过，`patches` 包含具体修补改动，由 DiffApplier 二次应用。

### 前端页面调整（Step 5 区域）

Tab 1（优化预览）新增改动清单展示：

```
┌─────────────────────────────────────────┐
│ ✨ 优化结果                               │
│                                          │
│ 共 8 处改动，3类修改                       │
│                                          │
│ ┌─ 🟡 改写 (5处) ──────────────────────┐ │
│ │ 工作经历-XX公司-职责2                  │ │
│ │ 原文: 负责系统日常维护...              │ │
│ │ 改后: 主导XX系统运维，保障99.9%可用性.. │ │
│ │ 原因: STAR法则量化                     │ │
│ │                                       │ │
│ │ 项目经历-XX项目-亮点1                  │ │
│ │ ...                                   │ │
│ └───────────────────────────────────────┘ │
│ ┌─ 🟢 补充 (2处) ──────────────────────┐ │
│ │ 技能-框架: + Kubernetes               │ │
│ │ 原因: 项目中实际使用但未在技能列表       │ │
│ └───────────────────────────────────────┘ │
│ ┌─ 🔵 强化 (1处) ──────────────────────┐ │
│ │ Summary 调整了侧重方向                  │ │
│ └───────────────────────────────────────┘ │
│                                          │
│ 📋 完整优化后简历（折叠）                   │
│ 🔍 连贯性审查: 8.5/10 ✅                  │
└─────────────────────────────────────────┘
```

---

## 第二阶段：匹配度驱动优化闭环

### 核心思路

匹配度不再是终点，而是反馈信号。匹配度 < 阈值时，未覆盖的Top3差距作为第二轮DiffAgent的精准输入。

### 架构

```
优化后简历
    │
    ▼
┌──────────────────┐
│ JobMatchingAgent  │ 计算 match_score + uncovered_gaps（未覆盖的Top3差距）
└────────┬─────────┘
         │
    ┌────┴────┐
    │ ≥ 70 ？  │
    └────┬────┘
  是 ↓       ↓ 否
┌───────┐  ┌───────────────────────────┐
│ 输出   │  │ 未覆盖gap → DiffAgent      │
└───────┘  │ → DiffApplier              │
           │ → CoherenceReviewer        │
           │ → 重新 JobMatchingAgent →  │
           │ 最多循环2次，取最高分结果     │
           └───────────────────────────┘
```

### MatchLoop（匹配闭环引擎）

```python
class MatchLoop:
    def __init__(self, diff_agent, matching_agent, max_rounds=2, threshold=70):
        ...

    def run(self, original_resume, gap_analysis, suggestions, job_profile) -> tuple[Resume, list[MatchResult]]:
        """
        第一轮: DiffAgent生成改动 → 打分
        如果 score < threshold:
           提取 uncovered_gaps
           第二轮: DiffAgent（带uncovered_gaps） → 重新打分
        取最高分的结果返回
        """
```

### JobMatchingAgent 新增输出

```json
{
    "match_score": 65,
    "match_strengths": [...],
    "match_gaps": [...],
    "uncovered_gaps": [
        {"gap": "...", "priority": 1, "suggestion_for_diff": "在项目X的描述中补充..."},
    ],
    "summary": "..."
}
```

关键是 `uncovered_gaps`——不是泛泛的"缺失"，而是给DiffAgent的可执行输入。

### 前端页面调整（Step 6 区域）

Tab 2（分析报告）匹配度区域改为：

```
┌─────────────────────────────────────────┐
│ 📊 匹配度: 65/100 ⚠️                     │
│ ████████████████░░░░ 65%                 │
│                                          │
│ 优化轮次: 2                              │
│ 第1轮: 52 → 第2轮: 65 (+13)             │
│                                          │
│ 未覆盖的Top3差距（已尽力）:               │
│ 1. ...                                   │
│ 2. ...                                   │
└─────────────────────────────────────────┘
```

---

## 第三阶段：LLM 动态排版

### 核心思路

不再维护固定的HTML模板文件。让LLM生成带内联样式的HTML，适配不同风格需求。

### StyleAgent

输入：结构化 Resume + 风格关键词（简洁/专业/创意/紧凑）+ 纸张尺寸
输出：完整的 HTML（含内联CSS）

```python
class StyleAgent:
    def render(self, resume: Resume, style: str, page_size: str = "A4") -> str:
        """
        style in ["minimal", "professional", "creative", "compact"]
        返回完整的独立HTML文件内容
        """
```

### 风格支持

| 风格 | 描述 | HTML特征 |
|------|------|----------|
| minimal | 极简黑白，适合投递大厂（友好ATS解析） | 单栏、无装饰、高对比度、标准字号 |
| professional | 传统商务，适合金融/法律/制造 | 双栏、蓝色或深灰辅助色、衬线字体 |
| creative | 现代活力，适合互联网/设计 | 色彩点缀、图标、非对称布局 |

### 放弃固定模板的原因

- 三套模板维护成本高，且每套都要兼顾中文排版细节
- 固定模板无法根据简历内容做适应性调整（谁的经历多谁的经历少排版都不同）
- StyleAgent 输出HTML时可以自然处理这些细节：经历少的人多留白调整视觉节奏，关键词高亮等

### 保留的部分

- TemplateEngine 简化为只生成基础HTML骨架（`<html><head><body>`）
- PDFRenderer 保持不变（Playwright + Chromium渲染）
- template_config.yaml 简化为风格选项配置

### 前端页面调整（Step 7 区域）

```
┌─────────────────────────────────────────┐
│ 📥 下载优化简历                           │
│                                          │
│ 风格: [minimal ▼] [professional] [creative] [compact]
│                                          │
│ ┌─ 预览 ───────────────────────────────┐ │
│ │  (嵌入式 HTML 预览 iframe)             │ │
│ │                                       │ │
│ └───────────────────────────────────────┘ │
│                                          │
│ [📥 下载 PDF]   [📝 下载 Markdown]       │
└─────────────────────────────────────────┘
```

---

## 全流程改造后完整数据流

```
用户上传简历 + 岗位名 [+ JD]
           │
           ▼
    简历解析 + 结构化提取
           │
           ▼
    岗位画像（with Reflection）
           │
           ▼
    简历深度分析（with Reflection）
           │
           ▼
    Gap 分析（with Reflection）
           │
           ▼
    优化建议（with Reflection）
           │
           ▼
  ┌──────────────────────────────────────┐
  │  阶段一：Diff-based 生成               │
  │  DiffAgent → DiffApplier              │
  │  → CoherenceReviewer（with Reflection）│
  │  → 优化后简历                          │
  └──────────────────┬───────────────────┘
                     │
                     ▼
  ┌──────────────────────────────────────┐
  │  阶段二：匹配闭环                      │
  │  JobMatchingAgent                    │
  │  ├─ score >= 70 → 通过               │
  │  └─ score < 70                       │
  │      → uncovered_gaps → DiffAgent    │
  │      → 最多2轮，取最高分              │
  └──────────────────┬───────────────────┘
                     │
                     ▼
  ┌──────────────────────────────────────┐
  │  阶段三：动态排版                      │
  │  StyleAgent → HTML                   │
  │  → PDFRenderer → PDF                 │
  └──────────────────────────────────────┘
```

---

## 测试策略

### 第一阶段
- `test/test_diff_applier.py` — 纯Python逻辑，测试每种action的精确执行
- `test/test_diff_agent.py` — 集成测试：给一份简历+gap分析，验证输出DiffResult结构
- `test/test_coherence_reviewer.py` — 集成测试：验证连贯性审查输出

### 第二阶段
- `test/test_match_loop.py` — 单元测试：mock DiffAgent和MatchingAgent，验证循环逻辑和取最高分

### 第三阶段
- `test/test_style_agent.py` — 验证输出HTML完整性，验证不同风格关键词产生的差异
