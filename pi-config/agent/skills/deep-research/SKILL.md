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
1. 构造 GitHub 仓库 URL（`github.com/{org}/{project}`），用 `agent-browser get text "article"` 提取 README 全文。
2. 构造官方文档站 URL（`developers.{company}.com`、`docs.{product}.dev`）。
3. GitHub README 的信息密度和新鲜度通常远高于搜索引擎结果。
4. 404 时按降级链处理：变体 URL → 上级页面 → org 页面 → 搜索引擎。

**轨道 B：Gemini 搜索（搜索的唯一通道）**
1. **所有搜索必须通过 Gemini**（内置 Google grounding，不被 CAPTCHA 拦截）。
2. 禁止用 agent-browser 访问搜索引擎页面。
3. 可并行运行多个 Gemini 实例收集不同子问题。
4. 搜索引擎用来**发现未知来源**，但拿到线索后可用 agent-browser 追溯到一手来源。

**Gemini 搜索快速执行模板（每次搜索复制此模板）：**
```bash
RESULT_FILE=$(mktemp /tmp/gemini-result.XXXXXX.txt)
gemini -p "Research Task: [问题]
Scope: [范围]
Output: bullet list with source URLs" \
  -m gemini-3-pro-preview --yolo --output-format text \
  > "$RESULT_FILE" 2>/dev/null
# 读取结果
cat "$RESULT_FILE"
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
  ├─ YES → agent-browser 直接导航提取
  │         失败(Cloudflare/404)? → 降级到 Gemini 搜索（不要换另一个 agent-browser URL 反复重试）
  │
  └─ NO → Q2: 是否需要搜索/发现未知来源？
           │
           └─ YES → **Gemini（唯一路径）**
                    使用: gemini -p "..." -m gemini-3-pro-preview --yolo --output-format text
                    ⚠️ 禁止用 agent-browser 访问 Google/Bing/DuckDuckGo/Reddit 等搜索引擎页面
                    ⚠️ 禁止用 web_search.py 等脚本类搜索工具
```

### 工具职责边界（硬性）

| 工具 | ✅ 用于 | ❌ 禁止用于 |
|------|--------|-----------|
| **Gemini** | 通用搜索、多源搜集、研究问题、查最新信息 | 写代码、做决策 |
| **agent-browser** | 导航到已知 URL 提取全文、填表、交互 | 访问搜索引擎页面（Google/Bing/DDG/Reddit search） |
| **read/write** | 本地文件操作 | — |

### 连续失败熔断规则

**agent-browser 连续 2 次被拦截（Cloudflare/CAPTCHA/空内容）→ 立即切换到 Gemini，不要继续尝试 agent-browser。**

### Gemini 快速调用模板（复制即用）

```bash
RESULT_FILE=$(mktemp /tmp/gemini-result.XXXXXX.txt)
LOG_FILE=$(mktemp /tmp/gemini-run.XXXXXX.log)

gemini -p "Research Task: [具体问题]
Scope: [时间范围、来源偏好]
Output: [格式要求]" \
  -m gemini-3-pro-preview \
  --yolo \
  --output-format text \
  > "$RESULT_FILE" 2> "$LOG_FILE"

# 成功后读取结果
cat "$RESULT_FILE"
```

### 并行 Gemini 搜索模板（多子问题）

```bash
gemini -p "question 1" -m gemini-3-pro-preview --yolo --output-format text > "$R1" 2> "$L1" &
gemini -p "question 2" -m gemini-3-pro-preview --yolo --output-format text > "$R2" 2> "$L2" &
gemini -p "question 3" -m gemini-3-pro-preview --yolo --output-format text > "$R3" 2> "$L3" &
wait
```

## Troubleshooting
### Search Quality Issues
If Gemini returns low-quality or regionally biased results:
1.  **Refine prompt**: Add explicit constraints like "English sources only", "official documentation", "peer-reviewed".
2.  **Specific URL fetch**: If you know the target URL, ask Gemini to fetch it directly instead of searching.
3.  **Retry with rephrased query**: Use Reflexion pattern — analyze why results were poor, rephrase, re-delegate.
4.  **Fallback**: Acknowledge limitation in "Risks / Unknowns" section and rely on Pi's internal knowledge.

## Phase 5 — Publish (optional, recommended)

调研完成后，将报告转为美观的网页以便阅读和分享。

**触发条件**：当报告内容较长（>2000 字）且用户未明确拒绝网页输出时，主动提议生成网页。

**执行方式**：委托 Gemini CLI 生成 HTML 页面。Gemini 擅长前端设计，能生成更有创意的视觉效果。

```bash
# 1. 先将报告 markdown 保存到临时文件
REPORT_MD=$(mktemp /tmp/report-XXXXXX.md)
# write report markdown to $REPORT_MD

# 2. 委托 Gemini 生成网页
gemini -p "你是一个前端设计专家。请将以下 markdown 报告转为美观的单文件 HTML 网页。

要求：
1. 读取 skill 模板：$(cat /home/ubuntu/.pi/agent/skills/md-to-web-report/SKILL.md)
2. 读取 HTML 模板：/home/ubuntu/.pi/agent/skills/md-to-web-report/assets/report-template.html
3. 按 skill 指示填充所有 {{placeholders}}，特别注意为该主题选择独特的配色方案和装饰符号
4. Markdown 内容嵌入时注意转义反引号和 \${ 序列
5. 将最终 HTML 写入 /home/ubuntu/discord-agent/web-reports/<slug>.html
6. 用 curl 验证 http://localhost:18080/<slug>.html 返回 200

报告内容：
$(cat $REPORT_MD)" \
  -m gemini-3-pro-preview --yolo --output-format text \
  > /tmp/web-report-gen.log 2>&1
```

生成后向用户报告公开访问 URL：`https://docs.a2a.ing/<slug>.html`

## Minimal execution template
1. 规划子问题（3-5）
2. 并行/串行收集证据
3. 生成结构化草稿
4. 做质量门禁检查
5. 输出终稿
6. （可选）委托 Gemini 生成网页报告 → 部署到 web-reports

## References
- 查询质量标准：`references/source-quality.md`
- 失败降级策略：`references/fallback-playbook.md`
- 网页报告生成：`md-to-web-report` skill（模板在 `/home/ubuntu/.pi/agent/skills/md-to-web-report/`）
