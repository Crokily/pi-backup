#!/usr/bin/env bash
set -euo pipefail
cd /home/ubuntu/discord-agent
if [ ! -f .env ]; then
  cp .env.example .env
fi
TOKEN_LINE="$(grep -E '^DISCORD_BOT_TOKEN=' .env || true)"
TOKEN_VALUE="${TOKEN_LINE#DISCORD_BOT_TOKEN=}"
if [ -z "${TOKEN_VALUE}" ]; then
  echo "DISCORD_BOT_TOKEN is missing in /home/ubuntu/discord-agent/.env" >&2
  exit 1
fi
source .venv/bin/activate
exec python3 discord_agent.py
