---
name: deep-research
description: Multi-step deep research workflow for complex topics. Use when user asks for 深度调研、全面报告、thorough analysis、multi-source synthesis, or needs citations + structured conclusions.
---

# Deep Research Skill

## When to use
在以下场景加载本 skill：
- 用户明确要“深度调研 / 全面报告 / 研究综述”
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

### Phase 1 — Plan
1. 把用户主题拆成 3-5 个子问题（Least-to-Most）。
2. 为每个子问题定义：
   - 目标事实（要回答什么）
   - 最低证据数（>=2 个来源）
   - 质量门槛（官方/论文/权威媒体优先）

### Phase 2 — Gather
优先并行，失败自动降级：
1. 先尝试 `subagent` 并行收集。
2. 若 subagent 报错、空输出或模型不可用：降级为串行 `web_search`。
3. 对每个子问题至少收集 2 个来源，记录“事实 -> 来源 URL”。

> 质量规则与降级细节见：
> - `references/source-quality.md`
> - `references/fallback-playbook.md`

### Phase 3 — Synthesize
1. 合并重复信息，标记冲突信息。
2. 每条关键结论至少绑定 1 个来源。
3. 形成“结论 + 证据 + 不确定性”三元组。

### Phase 4 — Validate
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

## Tool usage policy
- `subagent`: 并行探索（首选）
- `web_search`: 可快速扩展信息面
- `read`: 读取本地中间结果与状态文件
- `write/edit`: 生成报告与更新状态

## Troubleshooting
### Search Localization Bias
If `web_search` consistently returns results from a specific region (e.g., Zhihu/China) despite English queries:
1.  **Force English**: Use search operators like `language:en` (if supported) or append "english only" to queries.
2.  **Specific Domains**: Try stricter `site:` filters (e.g., `site:arxiv.org`, `site:acm.org`).
3.  **Fallback**: If search is unusable, acknowledge the limitation in the "Risks / Unknowns" section of the report and rely on internal knowledge or known static resources.

## Minimal execution template
1. 规划子问题（3-5）
2. 并行/串行收集证据
3. 生成结构化草稿
4. 做质量门禁检查
5. 输出终稿

## References
- 查询质量标准：`references/source-quality.md`
- 失败降级策略：`references/fallback-playbook.md`
