# Source Quality Standards & Primary Source Strategy

## Source Tier System

| Tier | Source Type | Examples | Trust Level |
|------|-----------|----------|-------------|
| **T1** | 官方一手来源 | GitHub README, 官方文档站, RFC/Spec | ★★★★★ |
| **T2** | 创作者原文 | 作者/团队的工程博客, 论文 | ★★★★ |
| **T3** | 权威媒体 | ArXiv, ACM, IEEE, HN top post | ★★★ |
| **T4** | 社区内容 | 博客文章, StackOverflow, Reddit | ★★ |
| **T5** | 聚合/转述 | 教程聚合站, AI 生成的摘要 | ★ |

**原则：永远优先 T1-T2。** 搜索引擎返回的往往是 T3-T5，需要主动向上追溯到一手来源。

## 一手来源优先策略（Primary Source First）

当调查技术产品、SDK、框架、工具时，**先直接导航到一手来源，再用搜索引擎补充**。这比搜索引擎优先的方法产出更准确、更新鲜的信息。

### 为什么 GitHub README > 博客 > 搜索结果

| 来源 | 信息新鲜度 | 信息密度 | 准确性 |
|------|-----------|---------|--------|
| **GitHub README** | 实时（维护者持续更新） | 极高（架构图+代码+对比表） | 一手 |
| **官方文档** | 实时（和产品同步） | 高 | 一手 |
| 工程博客 | 发布时是新的，之后不更新 | 中等 | 一手但可能过时 |
| 搜索引擎结果 | 索引有延迟 | 低（摘要片段） | 可能是转述 |
| 教程/聚合文章 | 写作时是新的 | 中等 | 二手，可能有误解 |

### 直接导航操作手册

**Step 1：构造 GitHub 仓库 URL**

大多数技术产品的仓库 URL 可以直接猜测：

```
github.com/{org}/{project}
github.com/{org}/{project}-sdk
github.com/{org}/{project}-js
```

常见模式：
```
Cloudflare Agents → github.com/cloudflare/agents
PydanticAI       → github.com/pydantic/pydantic-ai
Pydantic Monty   → github.com/pydantic/monty
E2B              → github.com/e2b-dev/e2b
Daytona          → github.com/daytonaio/daytona
```

**Step 2：用 agent-browser 提取全文**

```bash
agent-browser open "https://github.com/{org}/{project}"
agent-browser get text "article"   # GitHub README 内容在 <article> 标签里
```

一次提取可以获得几千字的完整文档，比搜索摘要信息完整得多。

**Step 3：构造官方文档 URL**

常见文档站模式：
```
developers.{company}.com/{product}/
docs.{product}.dev/
{product}.dev/docs/
ai.{company}.dev/
```

**Step 4：404 时的降级策略**

```
直觉构造的 URL 404 → 尝试变体
   ↓ 仍然 404
去 GitHub org 页面浏览仓库列表
   ↓ 找不到
去官方文档站的首页/索引页导航
   ↓ 仍然找不到
降级到搜索引擎查询
   ↓ 搜索也无结果
在报告中标记为"未找到公开信息"
```

### 跨源收敛检测

当多个独立一手来源（不同公司/团队）对同一问题得出相同结论时，这通常是最有价值的发现。主动寻找这种收敛：

```
示例：
  Cloudflare CodeMode: "LLMs are better at writing code than calling tools"
  Pydantic Monty:      "LLMs can work faster if they write code"
  HuggingFace SmolAgents: "Code is a better way to express actions"
  Anthropic:           "Code is a more natural format for tool calling"

  → 收敛发现：四家独立团队达成同一结论，这是行业共识，不是单一观点
```

在报告中明确标注这种收敛："N个独立来源收敛于同一结论"比"某公司说了X"有更高的置信度。

## Quality Gates

每条关键事实必须满足：

1. **可追溯**: 绑定到具体 URL，读者可以点击验证
2. **有时效标注**: 标注信息的发布/更新日期（GitHub README 标注 last commit date）
3. **区分事实与观点**: 
   - 事实："Monty 启动时间 <1μs"（README 中有基准测试数据）
   - 观点："Monty 是最有趣的新技术"（作者判断，需标注）
4. **标注不确定性**: 如果只有单一来源，标注"单源，未交叉验证"

## Anti-patterns

- ❌ 把搜索引擎摘要当作信息来源（去读原文）
- ❌ 引用博客文章但不检查是否有更新的官方文档
- ❌ 多个来源说同一件事就认为是独立验证（检查它们是否互相引用）
- ❌ 404 后放弃（先试变体 URL、上一级页面、org 页面）
- ❌ 只用搜索引擎（可能漏掉搜索引擎未索引的新内容）
