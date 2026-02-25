# Fallback & Degradation Playbook

## Tool Availability Fallback Chain

```
Gemini 搜索 (首选) → agent-browser 直接导航 (已知 URL) → 内部知识 + 标注
```

**⚠️ 关键变更：Gemini 是搜索的首选工具，不是降级选项。agent-browser 仅用于已知 URL 的直接导航。**

### 每一级的触发条件

| 工具 | 正常使用 | 降级触发条件 |
|------|---------|-------------|
| **`gemini`** | **通用搜索（唯一路径）** | API 错误、超时、返回无关结果 |
| `agent-browser` | 导航到已知 URL 提取全文 | 页面 404、Cloudflare 拦截、超时 |
| 内部知识 | 补充已知事实 | 所有外部工具失败时 |

### ⚠️ 禁止操作

- **禁止用 agent-browser 访问任何搜索引擎页面**（Google、Bing、DuckDuckGo、Reddit search）
  - 原因：搜索引擎对 headless browser 几乎 100% 拦截（CAPTCHA/Cloudflare）
  - 正确做法：用 Gemini（内置 Google grounding，不会被拦截）
- **agent-browser 连续 2 次被拦截 → 立即熔断，切换到 Gemini**

## agent-browser 特有的降级策略

### URL 404 降级链

```
精确 URL 404
  → 变体 URL（改 slug 格式、加减前缀后缀）
  → 上一级页面（去掉最后一段路径）
  → 组织/公司首页导航
  → GitHub org 页面浏览仓库列表
  → 搜索引擎查询
  → 标记"未找到公开信息"
```

### 页面加载失败

```
Cloudflare/Bot 拦截（"Just a moment..."）
  → 等待 5s 重试一次
  → 换到 GitHub 仓库（通常不拦截）
  → 换到 Google Cache（site:url）
  → 放弃该来源，标注原因

超时
  → agent-browser screenshot 截图留证
  → 重试一次（可能是网络抖动）
  → 放弃该页面，尝试替代来源
```

### 内容提取失败

```
agent-browser get text "article" 返回空/脚本代码
  → 尝试 "main" 选择器
  → 尝试 "body" 选择器 + grep 过滤脚本
  → 截图后人工判断
```

## Search Quality Degradation

### 地域偏差问题

如果 `web_search` 持续返回特定地区结果（如中文结果但需要英文信息）：

1. 强制英文：查询中加 `language:en` 或 `"english only"`
2. 限定域名：`site:github.com`、`site:arxiv.org`、`site:docs.*.dev`
3. **切换到直接导航**：如果搜索不可靠，用 agent-browser 直接去已知的权威来源

### 搜索结果质量差

搜索返回的全是 T4-T5 来源（教程聚合站、AI 摘要）时：

1. 从搜索结果中提取组织/产品名称
2. 用名称构造 GitHub/官方文档 URL
3. 直接导航到一手来源
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
