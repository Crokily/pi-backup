---
name: deep-research
description: Multi-step deep research workflow for complex topics. Use when user asks for 深度调研、全面报告、thorough analysis、multi-source synthesis, or needs citations + structured conclusions.
---

# Deep Research Skill

## When to use
在以下场景加载本 skill：
- 用户明确要"深度调研 / 全面报告 / 研究综述"
- 需要跨多个来源做对比、归因、趋势判断
- 需要结构化输出（Executive Summary / Findings / References）

## Output contract (must follow)
最终输出必须包含：
1. Executive Summary（3-6 行）
2. Key Findings（3-7 条）
3. Detailed Analysis（按子问题分节）
4. Risks / Unknowns（信息缺口与不确定性）
5. References（可点击链接）

模板见：`assets/report_template.md`

## Workflow

### Phase 1 - Plan
1. 把用户主题拆成 3-5 个子问题（Least-to-Most）。
2. 为每个子问题定义：
   - 目标事实（要回答什么）
   - 最低证据数（>=2 个来源）
   - 质量门槛（官方/论文/权威媒体优先）

### Phase 2 — Gather
**双轨并行：直接导航 + 搜索引擎。** 不要只依赖搜索引擎。

**轨道 A：一手来源直接导航（优先）**
对于技术产品/SDK/框架类调查：
1. 构造 GitHub 仓库 URL（`github.com/{org}/{project}`），用 `fetch_content` 提取 README 全文（GitHub URL 会自动克隆仓库）。
2. 构造官方文档站 URL（`developers.{company}.com`、`docs.{product}.dev`）。
3. GitHub README 的信息密度和新鲜度通常远高于搜索引擎结果。
4. 404 时按降级链处理：变体 URL → 上级页面 → org 页面 → 搜索引擎。

**轨道 B：web_search 搜索**
1. 使用 `web_search` 工具进行搜索（pi-web-access 扩展提供，内置 Exa → Perplexity → Gemini API 多级 fallback）。
2. 搜索结果返回真实 URL 和引用来源，Pi 自行判断可信度。
3. 可批量搜索多个子问题：`web_search({ queries: ["q1", "q2", "q3"] })`。
4. 搜索引擎用来**发现未知来源**，拿到线索后可用 `fetch_content` 追溯到一手来源。

**搜索快速执行模板：**
```typescript
// 单个搜索
web_search({ query: "具体问题", numResults: 10 })

// 批量搜索多个子问题
web_search({ queries: ["子问题1", "子问题2", "子问题3"] })

// 限定域名搜索
web_search({ query: "问题", domainFilter: ["github.com", "docs.example.com"] })

// 限定时间范围
web_search({ query: "问题", recencyFilter: "month" })

// 搜索后获取完整页面内容
web_search({ query: "问题", includeContent: true })
```

**两轨共同规则：**
- 对每个子问题至少收集 2 个来源，记录"事实 -> 来源 URL"。
- 关注**跨源收敛**：多个独立来源得出相同结论时，标注为高置信度发现。
- 来源优先级：GitHub README > 官方文档 > 作者博客 > 搜索结果 > 社区内容。

> 质量规则与降级细节见：
> - `references/source-quality.md`（来源分级 + 一手来源操作手册）
> - `references/fallback-playbook.md`（降级策略 + 信息缺口处理）

### Phase 3 - Synthesize
1. 合并重复信息，标记冲突信息。
2. 每条关键结论至少绑定 1 个来源。
3. 形成"结论 + 证据 + 不确定性"三元组。

### Phase 4 - Validate
发布前执行自检：
- 是否覆盖所有子问题？
- 是否有无来源断言？
- 是否包含反例/限制条件？
- 是否明确下一步调研建议？

## Practical prompting patterns
- **CoT**: 先列推理步骤，再给结论。
- **ReAct**: Thought -> Action -> Observation。
- **Self-Consistency**: 对关键结论尝试第二条搜索路径做交叉验证。
- **Reflexion**: 搜索结果差时，先解释为何差，再改写 query 重试。

## Tool usage policy — MANDATORY DECISION TREE

**在选择任何信息收集工具之前，必须按以下决策树执行。这不是建议，是硬性规则。**

```
需要外部信息 →
  Q1: 是否有已知的、确切的 URL？（如 github.com/org/repo, docs.xxx.dev/page）
  │
  ├─ YES → fetch_content({ url: "..." }) 直接提取
  │         GitHub URL 会自动克隆仓库，返回文件内容
  │         普通 URL 自动处理 JS 渲染、反爬、PDF 等
  │         失败? → 降级到 web_search 搜索
  │
  └─ NO → Q2: 是否需要搜索/发现未知来源？
           │
           └─ YES → web_search({ query: "..." })
                    支持批量查询、域名过滤、时间过滤
                    返回真实结果 + 来源 URL，Pi 自行综合判断
```

### 工具职责边界（硬性）

| 工具 | ✅ 用于 | ❌ 禁止用于 |
|------|--------|-----------|
| **web_search** | 通用搜索、多源搜集、研究问题、查最新信息 | — |
| **code_search** | 代码示例、API 文档、库使用方式 | — |
| **fetch_content** | 已知 URL 提取全文、GitHub 仓库、YouTube 视频、PDF | — |
| **agent-browser** | 需要交互的页面（填表、点击、登录） | 访问搜索引擎页面（Google/Bing/DDG） |
| **read/write** | 本地文件操作 | — |

### 连续失败熔断规则

**fetch_content 连续 2 次提取失败（Cloudflare/空内容）→ 尝试 web_search 搜索相关信息，或用 agent-browser 交互式提取。**

### 搜索快速调用模板（复制即用）

```typescript
// 基础搜索
web_search({ query: "具体问题" })

// 深度搜索（获取完整页面内容）
web_search({ query: "具体问题", includeContent: true, numResults: 10 })

// 限定来源搜索
web_search({ query: "问题", domainFilter: ["github.com", "arxiv.org"] })

// 代码搜索
code_search({ query: "React useEffect cleanup pattern" })
```

### 批量搜索模板（多子问题）

```typescript
// 一次性搜索多个子问题
web_search({
  queries: ["子问题1", "子问题2", "子问题3"],
  numResults: 5
})
```

## Troubleshooting
### Search Quality Issues
If web_search returns low-quality or irrelevant results:
1.  **Refine query**: Add explicit constraints like domain filters, recency filters.
2.  **Switch provider**: Try `web_search({ query: "...", provider: "perplexity" })` or `provider: "exa"`.
3.  **Direct fetch**: If you know the target URL, use `fetch_content({ url: "..." })` instead.
4.  **Retry with rephrased query**: Use Reflexion pattern — analyze why results were poor, rephrase, re-search.
5.  **Fallback**: Acknowledge limitation in "Risks / Unknowns" section and rely on Pi's internal knowledge.

## Phase 5 — Publish (optional, recommended)

调研完成后，将报告转为美观的网页以便阅读和分享。

**触发条件**：当报告内容较长（>2000 字）且用户未明确拒绝网页输出时，主动提议生成网页。

**执行方式**：使用 `md-to-web-report` skill 将 Markdown 报告转为 HTML 网页。

详见 `md-to-web-report` skill（模板在 `/home/ubuntu/.pi/agent/skills/md-to-web-report/`）。

生成后向用户报告公开访问 URL：`https://docs.a2a.ing/<slug>.html`

## Minimal execution template
1. 规划子问题（3-5）
2. 并行/串行收集证据（web_search + fetch_content）
3. 生成结构化草稿
4. 做质量门禁检查
5. 输出终稿
6. （可选）生成网页报告 → 部署到 web-reports

## References
- 查询质量标准：`references/source-quality.md`
- 失败降级策略：`references/fallback-playbook.md`
- 网页报告生成：`md-to-web-report` skill（模板在 `/home/ubuntu/.pi/agent/skills/md-to-web-report/`）
