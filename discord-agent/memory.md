---
description: Discord Agent 的长期目标、默认策略、安全边界与后续演进计划记录。
---

# memory.md

## 项目长期目标
- 打造一个“强调调研能力”的个人 Agent
- 兼顾：稳定性、可控性、可扩展性

## 当前默认策略
- 优先使用 `BACKEND_MODE=pi`
- 群聊默认 `REQUIRE_MENTION=true`
- DM 默认 `DM_POLICY=pairing`
- 心跳框架默认关闭，按需 `!hb on` 启用
- 调研长文优先输出 HTML 报告链接，提升阅读体验
- 变更优先小步迭代，避免一次性复杂重构

## 运维约定
- 服务由 `systemd --user` 守护
- 关键配置在 `.env`
- 运行时参数优先通过 `!model` / `!thinking` 调整

## 安全边界
- 不在聊天中回传敏感凭据
- 仅管理员可执行审批与运行时调参
- 对调研结果明确标注证据来源与不确定性

## 下一阶段演进（候选）
1. 增加 `/health` 与定时自检
2. 加入引用质量评分（source confidence）
3. 引入结构化 capabilities 文件（JSON/YAML）用于自动对外宣告能力
4. 细分多 Agent（research / coding / ops）
