---
description: Discord Agent 的架构拆分与设计原则说明，用于理解组件职责与系统边界。
---

# agents.md

## 目标
构建一个“够用但可扩展”的个人 AI Agent：
- 稳定在线
- 可调研
- 可运维
- 可持续迭代

## 组件拆分

### 1) Channel Adapter（Discord）
- 文件：`discord_agent.py`（`DiscordAgent`）
- 职责：
  - 接收消息（DM / 群 / 线程）
  - 鉴权与触发控制（mention、allowlist、pairing）
  - 命令路由（`!research`、`!model` 等）

### 2) Session & Memory Store（SQLite）
- 文件：`discord_agent.py`（`Store`）
- 表：
  - `messages`：短期会话历史
  - `allowed_users`：DM 授权名单
  - `pairing_requests`：配对码
  - `runtime_settings`：运行时覆盖（model/thinking）

### 3) LLM Backend Adapter
- 文件：`discord_agent.py`（`AgentBackend`）
- 模式：
  - `pi`
  - `openai`
  - `command`
- 统一接口：`ask(session_key, history, user_text, ...)`

### 4) Research Skill（调研能力）
- 入口命令：`!search`、`!research`
- 工具依赖：`WEB_SEARCH_BIN`
- 能力：
  - Web 检索
  - 来源片段抓取
  - 证据增强后交给模型综合回答

### 5) Runtime Control
- 管理员命令：
  - `!model`
  - `!thinking`
  - `!runtime`
- 用途：
  - 在线调参，不必改 `.env` + 重启

## 设计原则
1. 默认最小权限（allowlist + pairing + mention）
2. 能力可观测（`!capabilities`）
3. 能力可运维（`!runtime` + systemd）
4. 先稳定再复杂（功能增量、小步快跑）
