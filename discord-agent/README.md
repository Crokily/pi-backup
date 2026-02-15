---
description: Discord Agent 项目总览与部署使用说明，包含配置、安全策略、命令与运维指南。
---

# Discord Agent Bridge (OpenClaw-style, lightweight)

这是一个面向个人自托管的轻量 Discord Agent 网关：
- Discord 作为消息入口（DM / 群 / 线程）
- 会话键按 DM/Channel/Thread 隔离
- DM 安全策略（pairing / allowlist / open / disabled）
- 多后端（原生 `pi` / OpenAI-compatible / 本地命令）
- 内置调研模式（`!search` / `!research`）
- 运行时控制（`!model` / `!thinking` / `!runtime`）
- 统一心跳框架（`!hb ...`）
- 异步任务队列（长任务可追踪：`!tasks` / `!task <id>`）
- 重启后主动补发（outbox）

---

## 1) 安装

```bash
cd /home/ubuntu/discord-agent
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

## 2) 配置 `.env`

至少要填：
- `DISCORD_BOT_TOKEN`
- `BACKEND_MODE`

### A. 使用原生 pi 后端（推荐）

```env
BACKEND_MODE=pi
PI_BIN=pi
PI_MODEL=openai-codex/gpt-5.3-codex
PI_THINKING=medium
```

`PI_THINKING` 可选：`off|minimal|low|medium|high|xhigh`。

### B. 使用 OpenAI-compatible 后端

```env
BACKEND_MODE=openai
OPENAI_BASE_URL=https://api.openai.com/v1
OPENAI_API_KEY=...
OPENAI_MODEL=gpt-4.1-mini
```

### C. 使用本地命令后端

```env
BACKEND_MODE=command
AGENT_COMMAND=python3 -c "import sys;print('Echo:',sys.stdin.read().strip())"
```

### D. 报告展示层（长文 HTML）

```env
REPORT_SERVER_ENABLED=true
REPORT_BIND=0.0.0.0
REPORT_PORT=18080
REPORT_BASE_URL=
REPORT_PUBLIC_HOST=
REPORT_DIR=/home/ubuntu/discord-agent/web-reports
REPORT_AUTO_FOR_RESEARCH=true
REPORT_AUTO_MIN_CHARS=1800
```

说明：
- `!research` 结果较长或 markdown 复杂时，会自动生成 HTML 报告并返回链接。
- 推荐设置 `REPORT_BASE_URL` 为可公网访问地址（后续可切域名）。

### E. 心跳框架配置

```env
HEARTBEAT_DEFAULT_ENABLED=false
HEARTBEAT_POLL_SECONDS=45
HEARTBEAT_TASK_TIMEOUT_SEC=240
HEARTBEAT_MAX_TASKS_PER_TICK=3
HEARTBEAT_DEFAULT_MAX_ALERTS_PER_DAY=2
HEARTBEAT_DEFAULT_DEDUPE_WINDOW=6h
STARTUP_REPORT_ENABLED=true

# Async task queue
ASYNC_TASKS_ENABLED=true
ASYNC_TASK_WORKERS=2
ASYNC_TASK_POLL_SECONDS=2
ASYNC_TASK_TIMEOUT_SEC=1800
ASYNC_TASK_MAX_ATTEMPTS=2
```

---

## 3) 运行

```bash
source .venv/bin/activate
python3 discord_agent.py
```

或使用 user-systemd：
- service 文件：`~/.config/systemd/user/discord-agent.service`
- 启动：`systemctl --user restart discord-agent.service`

---

## 4) 安全与触发建议

- `DM_POLICY=pairing`（默认）
- `ADMIN_USER_IDS=你的Discord用户ID`
- `REQUIRE_MENTION=true`（普通聊天在群里需 @ 触发）
- 可选 `ALLOWED_GUILD_IDS` / `ALLOWED_CHANNEL_IDS`

Pairing 模式下，陌生人 DM 会拿到 6 位码。
管理员发送：

```text
!approve 123456
```

批准后该用户进入 allowlist。

---

## 5) Discord 命令

### 通用命令

- `!help`：查看命令列表
- `!capabilities`：查看当前能力清单
- `!search <query>`：只返回搜索结果
- `!ask [model=...] [thinking=...] <prompt>`：发起异步对话任务
- `!research [model=...] [thinking=...] <query>`：调研模式（默认异步排队执行）
- `!tasks`：查看我的异步任务队列
- `!task <id>`：查看指定异步任务状态
- `!runtime`：查看当前后端/模型/thinking

示例：
- `!ask model=gpt-5.3-codex thinking=high 帮我写一个部署脚本并解释风险点`
- `!research model=claude-opus-4.5 thinking=minimal OpenAI Frontier 发布后生态影响`

### 管理员命令（模型）

- `!model <model-id>` / `!model default`
- `!thinking <off|minimal|low|medium|high|xhigh>` / `!thinking default`
- `!think ...`：`!thinking` 别名
- `!tasks all`：查看全局异步任务（admin）

### 管理员命令（心跳框架）

- `!hb help`
- `!hb on` / `!hb off`
- `!hb status`
- `!hb list`
- `!hb add name=... tag=... every=... mode=... prompt=... [hours=09:00-23:00] [tz=Asia/Shanghai] [max=2] [dedupe=6h] [target=here|admin|dm:<uid>|channel:<cid>]`
- `!hb run <id|all>`
- `!hb pause <id>` / `!hb resume <id>`
- `!hb remove <id>`

示例：

```text
!hb add name="AI行业雷达" tag=research every=6h mode=digest hours=09:00-23:00 tz=Asia/Shanghai max=2 dedupe=6h prompt="跟踪AI Agent框架与模型生态变化，输出结论+证据+建议动作" target=here
```

---

## 6) 调研模式配置

```env
RESEARCH_ENABLED=true
WEB_SEARCH_BIN=/home/ubuntu/.pi/agent/bin/web-search
RESEARCH_MAX_RESULTS=5
RESEARCH_READABLE_SOURCES=2
RESEARCH_PAGE_CHAR_LIMIT=3500
```

---

## 7) 展示层访问

生成的 HTML 报告会保存在：
- `REPORT_DIR`（默认 `/home/ubuntu/discord-agent/web-reports`）

访问链接由 `REPORT_BASE_URL` 或 `REPORT_PUBLIC_HOST` + `REPORT_PORT` 生成。
例如设置：

```env
REPORT_BASE_URL=https://report.example.com
```

则机器人返回的报告链接就是该域名下的静态页面。

---

## 8) 重启中断后的主动触达

已实现 outbox：
- 发送前先落库
- 发送失败保留 pending
- 进程重启后自动补发 pending
- 启动后可向管理员 DM 发送“已重启 + pending 状态”报告

适用于：异步任务结果、心跳任务结果、异常报告等需要“最终一定送达”的消息场景。
