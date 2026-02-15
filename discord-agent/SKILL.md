---
name: discord-agent
description: Bridge between Discord and Pi. Allows managing Discord interactions, heartbeat tasks, and research reports. Use for managing the Discord bot, sending notifications to Discord channels, or checking bot status.
---

# Discord Agent

A bridge that connects Discord to the Pi coding agent.

## Setup

Ensure environment variables are set in `/home/ubuntu/discord-agent/.env`.

```bash
cd /home/ubuntu/discord-agent
source .venv/bin/activate
# To start the bot (usually managed by systemd)
# systemctl --user restart discord-agent.service
```

## Management

- Check logs: `journalctl --user -u discord-agent -f`
- Check config: `python3 /home/ubuntu/discord-agent/check_config.py`
- Database: `/home/ubuntu/discord-agent/discord_agent.db` (SQLite)

## Capabilities

- **DM / Channel / Thread Isolation**
- **Heartbeat Framework**: Automated tasks via `!hb` command in Discord.
- **Research Mode**: Generates HTML reports.
- **Async Task Queue**: Long-running tasks.
