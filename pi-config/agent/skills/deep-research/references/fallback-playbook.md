# Fallback & Degradation Playbook

## Tool Availability Fallback Chain

```
web_search (首选搜索) → fetch_content (已知 URL 提取) → agent-browser (交互式) → 内部知识 + 标注
```

**搜索通过 pi-web-access 扩展（web_search / fetch_content / code_search），内置多级 fallback（Exa → Perplexity → Gemini API）。**

### 每一级的触发条件

| 工具 | 正常使用 | 降级触发条件 |
|------|---------|-------------|
| **`web_search`** | 通用搜索、发现未知来源 | 返回无关结果、provider 限流 |
| **`fetch_content`** | 已知 URL 提取全文、GitHub 克隆、YouTube 视频 | 页面 404、Cloudflare 拦截 |
| **`code_search`** | 代码示例、API 文档 | 无相关结果 |
| `agent-browser` | 需要交互的页面（填表、点击、登录） | Cloudflare 拦截、超时 |
| 内部知识 | 补充已知事实 | 所有外部工具失败时 |

### ⚠️ 注意事项

- **禁止用 agent-browser 访问搜索引擎页面**（Google、Bing、DuckDuckGo、Reddit search）
  - 原因：搜索引擎对 headless browser 几乎 100% 拦截（CAPTCHA/Cloudflare）
  - 正确做法：用 `web_search`（内置多个搜索后端，自动降级）
- **fetch_content 连续 2 次失败 → 换 agent-browser 或标记信息缺口**

## fetch_content 特有的降级策略

pi-web-access 的 `fetch_content` 内置了多层降级（Readability → Jina Reader → Gemini extraction），大多数情况下自动处理。

### URL 404 降级链

```
精确 URL 404
  → 变体 URL（改 slug 格式、加减前缀后缀）
  → 上一级页面（去掉最后一段路径）
  → 组织/公司首页导航
  → GitHub org 页面浏览仓库列表
  → web_search 搜索
  → 标记"未找到公开信息"
```

### 页面加载/提取失败

```
fetch_content 返回空或错误
  → 内置已自动尝试: Readability → RSC parser → Jina Reader → Gemini fallback
  → 如仍失败: 尝试 agent-browser 交互式提取
  → 仍然失败: 放弃该来源，标注原因
```

## web_search Quality Degradation

### 搜索结果质量差

如果 `web_search` 返回不相关或低质量结果：

1. **切换 provider**：`web_search({ query: "...", provider: "perplexity" })` 或 `provider: "exa"`
2. **添加域名过滤**：`domainFilter: ["github.com", "arxiv.org"]`
3. **添加时间过滤**：`recencyFilter: "week"` 或 `"month"`
4. **获取完整内容**：`includeContent: true` 让搜索同时提取页面全文
5. **重写查询**：用 Reflexion 模式 — 分析为何结果差，重新措辞

### 地域偏差问题

如果搜索持续返回特定地区结果（如中文结果但需要英文信息）：

1. 强制英文：查询中加 `"english only"` 或用英文措辞
2. 限定域名：`domainFilter: ["github.com", "arxiv.org", "docs.*.dev"]`
3. **切换到直接导航**：如果搜索不可靠，用 `fetch_content` 直接去已知的权威来源

### 搜索结果全是 T4-T5 来源

搜索返回的全是教程聚合站、AI 摘要时：

1. 从搜索结果中提取组织/产品名称
2. 用名称构造 GitHub/官方文档 URL
3. 用 `fetch_content` 直接导航到一手来源
4. 搜索引擎仅用来**发现线索**，不用来**获取答案**

## 信息缺口处理

当某个子问题完全找不到可靠信息时：

```markdown
### [子问题标题]

**状态：信息不足**

- 已尝试：[列出尝试过的来源和查询]
- 未找到原因：[产品太新/闭源/文档缺失/被拦截]
- 最佳猜测（低置信度）：[基于间接证据的推断]
- 建议后续：[下一步怎么获取这个信息]
```

**永远不要用猜测填充信息缺口而不标注。**
