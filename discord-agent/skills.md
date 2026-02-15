---
description: Discord Agent 支持的核心技能、失败模式与冒烟测试清单说明。
---

# skills.md

## 核心技能清单

### S1. 对话与上下文
- 触发：普通消息（群里默认需 @）
- 输入：文本消息
- 输出：LLM 回复
- 依赖：`BACKEND_MODE`

### S2. DM 配对与授权
- 触发：陌生用户 DM
- 行为：返回 6 位 pairing code
- 管理：`!approve <code>`

### S3. Web 搜索
- 命令：`!search <query>`
- 输出：标题/链接/摘要列表
- 依赖：`WEB_SEARCH_BIN`

### S4. 调研综合
- 命令：`!research <query>`
- 输出：结构化研究结论 + Sources
- 流程：
  1) 检索
  2) 抓取来源片段
  3) 证据增强提示词
  4) 模型综合

### S5. 运行时调参（管理员）
- `!model <id|default>`
- `!thinking <off|minimal|low|medium|high|xhigh|default>`
- `!runtime`

### S6. 能力自描述
- `!help`
- `!capabilities`

### S7. 统一心跳框架（管理员）
- `!hb on/off/status/list`
- `!hb add ...`
- `!hb run <id|all>`
- `!hb pause/resume/remove <id>`
- 适配多类任务（research/coding/ops/personal/自定义）

### S8. 展示层（HTML 报告）
- 长调研结果自动发布为 HTML 页面
- 支持复杂 markdown（表格/代码块/图片链接）
- Discord 返回可直接点击的报告链接

### S9. 重启后主动补发
- outbox 持久化消息
- 重启后自动 flush pending
- 启动时主动向管理员汇报状态

## 失败模式

- `web-search` 缺失：`!search/!research` 失败
- 外部站点反爬：来源正文抓取可能为空
- 后端认证失效：OpenAI/PI 调用报错
- Discord token 失效：机器人离线

## 冒烟测试

1. `!capabilities`
2. `!search openclaw`
3. `!research openclaw architecture`
4. `!runtime`
5. 管理员执行 `!thinking xhigh` 后再提问
6. `!hb on` + `!hb add ...` + `!hb run <id>`
7. 发起一个长 `!research`，确认返回 HTML 报告链接可打开
8. 重启服务后确认 pending outbox 被补发
