# pi-backup

Backup of a self-extending pi coding agent's accumulated capabilities,
including custom extensions, skills, prompt templates, agent definitions,
a Discord gateway bot, and service configurations.

This repository contains no secrets or credentials.
Everything here is the result of pi (https://github.com/mariozechner/pi)
progressively building out its own tooling over time on a live server.

If you find anything useful, take what you need.

---

## What is in here

### pi-config/

The `.pi/` configuration directory that pi uses at runtime.
This is normally located at `~/.pi` (or symlinked there).

```
pi-config/
  settings.json              -- top-level defaults (provider, model)
  agent/
    settings.json            -- agent-mode defaults (provider, model, thinking level)
    extensions/              -- custom tool extensions (TypeScript)
      fast-find.ts           -- parallel fd + rg search tool
      model-quota-fallback.ts -- auto-fallback when a model hits rate limits
      token-usage.ts         -- token usage status bar widget
    skills/                  -- reusable workflow skills
      codex-collaboration/   -- delegate tasks to OpenAI Codex CLI
      deep-research/         -- multi-step web research with structured reports
        references/          -- source quality rules + fallback playbook
      gemini-collaboration/  -- delegate search/research tasks to Gemini CLI
      md-to-web-report/     -- convert markdown to styled HTML web pages
        assets/              -- HTML report template
      pi-agent-app-dev/     -- guide for building agent-powered apps with pi-mono SDK
        references/          -- integration patterns, security, production, tool design
      pi-self-extension/     -- guide for creating new extensions and skills
      ralph-loop/            -- autonomous PRD-driven development loop
    prompts/
      codex.md               -- prompt template for Codex delegation
    agents/
      researcher.md          -- sub-agent definition for web research
```

### discord-agent/

A standalone Discord bot that bridges Discord messages to pi (or any
OpenAI-compatible backend). Features include session management, async
task queues, a web report server for long outputs (served via
`https://docs.a2a.ing/`), and heartbeat scheduled tasks.

See `discord-agent/README.md` for full documentation.

To run it: copy `.env.example` to `.env`, fill in the values, then
`pip install -r requirements.txt && python3 discord_agent.py`.

### external-skills/

Third-party skills installed from the community. These were placed in
`~/.agents/skills/` (or similar) and symlinked into pi's skill
discovery path. Included:

- agent-browser -- browser automation for AI agents
- find-skills -- skill discovery helper
- frontend-design -- frontend design guidelines
- next-best-practices -- Next.js patterns and conventions
- skill-creator -- scaffolding tool for new skills
- vercel-composition-patterns -- React component composition rules
- vercel-react-best-practices -- React performance rules
- web-design-guidelines -- general web design guidance

### systemd/

Systemd unit files used to keep services running:

- `discord-agent.service` -- user-level service for the Discord bot
- `self-improvement.service` / `self-improvement.timer` -- periodic
  self-improvement loop (runs a research iteration every 5 hours)

---

## Restoring on a new machine

This section is written for pi itself. If you are an AI agent restoring
from this backup, read this carefully and follow the steps in order.

### 1. Install pi

```
npm install -g @mariozechner/pi-coding-agent
```

Verify with `pi --version`.

### 2. Restore pi-config

Copy the `pi-config/` tree into `~/.pi/`:

```
mkdir -p ~/.pi
cp -r pi-config/* ~/.pi/
```

The `settings.json` files define default provider and model preferences.
After copying, run `pi` once and authenticate with your providers when
prompted. The `auth.json` files will be regenerated automatically.

Note: the original setup used a symlink (`~/.pi -> ~/pi-agents/main-agent/.pi`).
You can replicate that or just use `~/.pi` directly.

### 3. Restore external skills

```
mkdir -p ~/.agents/skills
cp -r external-skills/* ~/.agents/skills/
```

Then symlink the ones you want pi to discover into the skills directory:

```
cd ~/.pi/agent/skills
ln -s ~/.agents/skills/agent-browser .
ln -s ~/.agents/skills/skill-creator .
ln -s ~/.agents/skills/web-design-guidelines .
```

(Add or remove symlinks depending on which skills you actually use.)

### 4. Set up Discord Agent

```
cp -r discord-agent/ ~/discord-agent/
cd ~/discord-agent
cp .env.example .env
# Edit .env -- fill in DISCORD_BOT_TOKEN, ADMIN_USER_IDS, etc.
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Test with `python3 discord_agent.py`. Once working, install the
systemd service:

```
mkdir -p ~/.config/systemd/user
cp systemd/discord-agent.service ~/.config/systemd/user/
systemctl --user daemon-reload
systemctl --user enable --now discord-agent
```

Then symlink it as a pi skill so the agent knows about the bot:

```
ln -s ~/discord-agent ~/.pi/agent/skills/discord-agent
```

### 5. Systemd services (optional)

The other service files in `systemd/` are for the self-improvement loop.
Install them the same way if you want that functionality:

```
cp systemd/self-improvement.* ~/.config/systemd/user/
systemctl --user daemon-reload
systemctl --user enable --now self-improvement.timer
```

### 6. Global npm packages (optional)

The original server also had these installed globally:

```
npm install -g agent-browser neonctl vercel
```

Install them if your workflows depend on them.

---

## Original server context

- OS: Ubuntu 22.04 on a cloud VPS
- Node: v24.x, npm 11.x
- Pi version at time of backup: 0.55.0
- Default agent model: claude-opus-4-6-thinking with high thinking
- Web report domain: https://docs.a2a.ing/
- Other projects (clawdeploy, rlm-doc-explorer) have their own
  repositories and are not included here
