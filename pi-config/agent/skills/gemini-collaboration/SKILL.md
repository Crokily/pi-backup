---
name: gemini-collaboration
description: Guidelines for delegating information retrieval and web research tasks to Gemini CLI. Use when the main agent (pi) needs to search the web, fetch URL content, research documentation, look up error solutions, compare online sources, or gather any external information. Gemini is the research specialist — delegate all "find out", "search for", "what is the latest", "look up", and "read this URL" tasks to it. Do NOT use Gemini for coding, file editing, or engineering work (use Codex for those).
---

# Gemini Collaboration Guide (Research Specialist, Non-Interactive)

## Team Architecture

Pi (Claude Opus 4.6) is the **主脑 (master brain)** — all decisions, planning, and orchestration flow through Pi.

Three-agent division of labor:

| Agent | Role | Strengths | Delegates |
|-------|------|-----------|-----------|
| **Pi** | 主脑・统筹决策 | Strategic thinking, planning, coordination, complex reasoning | Everything that isn't pure coding or pure research |
| **Codex** | 理科生・编码执行 | Rigorous coding, refactoring, tests, debugging, architecture | All software engineering work (see codex-collaboration skill) |
| **Gemini** | 搜索官・信息获取 | Web search (Google grounding), URL fetching, real-time info | All external information retrieval |

**Cardinal rule:** Pi never surrenders decision-making authority. Codex and Gemini are specialist workers who execute and report back. Pi synthesizes, judges, and decides.

---

## When to Delegate to Gemini

- Searching for latest docs, release notes, changelogs
- Looking up error messages, Stack Overflow solutions
- Fetching and reading specific URLs
- Researching unfamiliar libraries, APIs, frameworks
- Comparing online documentation sources
- Checking real-time information (versions, status, news)
- Any question requiring knowledge beyond training cutoff

**Never delegate to Gemini:**
- Code writing, editing, or review (→ Codex)
- File system operations (→ Pi or Codex)
- Decision-making or architectural choices (→ Pi)

---

## Mandatory Rules

### 1) Always use headless mode
Use `gemini -p "<prompt>" -m gemini-3-flash-preview` for all delegated tasks. Never launch the interactive TUI.

### 2) Use `--yolo` to enable tool auto-approval
Gemini needs to use `google_web_search` and `web_fetch` tools without pausing for approval.

### 3) Never stream Gemini output into current session context
Capture output to file, read only the final result after process exits.

### 4) Keep prompts focused on information retrieval
Gemini is a search specialist. Frame prompts as research questions, not coding tasks.

### 5) Gemini is the ONLY search channel — 搜索唯一入口
- Pi 禁止使用 `web_search.py` 等脚本类搜索工具。
- Pi **禁止用 `agent-browser` 访问任何搜索引擎页面**（Google、Bing、DuckDuckGo、Reddit search 等），因为 headless browser 会被 CAPTCHA/Cloudflare 100% 拦截。
- **所有搜索需求必须且只能通过 Gemini（内置 Google grounding）。**
- `agent-browser` 仅用于导航到已知的具体 URL 提取内容，不用于搜索。
- 判断标准：如果你不知道确切 URL → 用 Gemini；如果你知道确切 URL → 可以用 agent-browser。

---

## Canonical Execution Pattern

```bash
# 1) Prepare files
PROMPT_FILE=$(mktemp /tmp/gemini-prompt.XXXXXX.md)
RESULT_FILE=$(mktemp /tmp/gemini-result.XXXXXX.txt)
LOG_FILE=$(mktemp /tmp/gemini-run.XXXXXX.log)

# 2) Write research prompt into $PROMPT_FILE

# 3) Run Gemini non-interactively, capture output
gemini -p "$(cat "$PROMPT_FILE")" \
  -m gemini-3-flash-preview \
  --yolo \
  --output-format text \
  > "$RESULT_FILE" 2> "$LOG_FILE"
GEMINI_EXIT=$?

# 4) Post-run handling
# - If GEMINI_EXIT=0: consume ONLY $RESULT_FILE
# - If GEMINI_EXIT!=0: inspect $LOG_FILE minimally and report concise failure summary
```

### Alternative: Pipe context directly

When the query needs input context (file content, error log, etc.):

```bash
cat "$CONTEXT_FILE" | gemini -p "$(cat "$PROMPT_FILE")" \
  -m gemini-3-flash-preview \
  --yolo \
  --output-format text \
  > "$RESULT_FILE" 2> "$LOG_FILE"
```

### Alternative: JSON output for structured data

When structured parsing is needed:

```bash
gemini -p "$(cat "$PROMPT_FILE")" \
  -m gemini-3-flash-preview \
  --yolo \
  --output-format json \
  > "$RESULT_FILE" 2> "$LOG_FILE"
# Parse with: python3 -c "import json,sys; print(json.load(sys.stdin)['response'])" < "$RESULT_FILE"
```

---

## Delegation Workflow

### Step 1: Identify research needs
Detect when the task requires external/real-time information that Pi doesn't have.

### Step 2: Formulate precise research prompt
Include:
- Exact question or topic
- Desired output format (summary, list, comparison, raw content)
- Scope constraints (e.g., "official docs only", "since 2025", "GitHub issues")
- Any context Gemini needs (pipe via stdin if large)

### Step 3: Execute with result isolation
Use canonical pattern above. Always redirect stdout/stderr.

### Step 4: Read only final result
- Success: read `$RESULT_FILE`, extract relevant information
- Failure: check exit code, read minimal `$LOG_FILE` snippets

### Step 5: Synthesize and act
Pi processes the research results, makes decisions, and either:
- Uses the info directly to answer the user
- Passes relevant findings to Codex as context for coding tasks

---

## Common Research Scenarios

### Web search (Gemini's core strength)
```bash
gemini -p "Search the web for the latest React 19 server components API changes. Summarize the key breaking changes and new patterns." \
  -m gemini-3-flash-preview --yolo --output-format text > "$RESULT_FILE" 2> "$LOG_FILE"
```

### Fetch specific URL
```bash
gemini -p "Read https://docs.example.com/api/v3 and extract all endpoint definitions with their parameters and return types." \
  -m gemini-3-flash-preview --yolo --output-format text > "$RESULT_FILE" 2> "$LOG_FILE"
```

### Error troubleshooting
```bash
cat error.log | gemini -p "Search for solutions to this error. Focus on GitHub issues and Stack Overflow from the last 6 months. Provide the top 3 most relevant solutions with links." \
  -m gemini-3-flash-preview --yolo --output-format text > "$RESULT_FILE" 2> "$LOG_FILE"
```

### Documentation research
```bash
gemini -p "Search for the official migration guide from Prisma v5 to v6. Summarize the steps and list any breaking changes." \
  -m gemini-3-flash-preview --yolo --output-format text > "$RESULT_FILE" 2> "$LOG_FILE"
```

### Version/compatibility check
```bash
gemini -p "What is the latest stable version of PostgreSQL? What Node.js versions does it support with the 'pg' npm package?" \
  -m gemini-3-flash-preview --yolo --output-format text > "$RESULT_FILE" 2> "$LOG_FILE"
```

---

## Prompt Template for Gemini

Use this structure in `PROMPT_FILE`:

```text
Research Task:
[clear question or topic]

Scope:
- [time range, source preferences, depth]

Output Format:
- [summary / bullet list / comparison table / raw content]

Constraints:
- [what NOT to include, length limits]
```

---

## Communication Policy

### Before running Gemini
"这个问题需要查阅外部信息，我将委托 Gemini 进行搜索/获取，完成后仅返回最终结果。"

### After success
- Provide concise summary of research findings
- Include key facts, versions, URLs as relevant
- Note confidence level and source quality

### After failure
- Report briefly (exit code + high-level reason)
- Propose alternatives (rephrase query, try different search terms, use browser skill directly)

---

## Multi-Agent Collaboration Patterns

### Research → Code pipeline
1. Pi identifies knowledge gap
2. Pi delegates research to Gemini
3. Pi reads Gemini results, synthesizes requirements
4. Pi delegates implementation to Codex (with Gemini findings as context)

### Parallel research
When multiple independent questions exist, run Gemini instances concurrently:
```bash
gemini -p "question 1" -m gemini-3-flash-preview --yolo --output-format text > "$RESULT1" 2> "$LOG1" &
gemini -p "question 2" -m gemini-3-flash-preview --yolo --output-format text > "$RESULT2" 2> "$LOG2" &
wait
```

---

## Exit Codes Reference

| Code | Meaning |
|------|---------|
| 0 | Success |
| 1 | General error or API failure |
| 42 | Input error (invalid prompt) |
| 53 | Turn limit exceeded |

---

## Anti-Patterns (Forbidden)

- Running interactive `gemini` TUI
- Asking Gemini to write or edit code (→ Codex)
- Asking Gemini to make decisions or architectural choices (→ Pi)
- Dumping raw Gemini output into conversation without Pi's synthesis
- Using Gemini when Pi already has the knowledge (waste of resources)

---

## Quick Checklist

Before run:
- [ ] Research/information task identified (not coding)
- [ ] Prompt file prepared with clear question and scope
- [ ] Using `gemini -p -m gemini-3-flash-preview` (headless mode, latest model)
- [ ] Using `--yolo` for tool auto-approval
- [ ] Redirecting stdout to result file, stderr to log file

After run:
- [ ] Exit code checked
- [ ] Only result file consumed on success
- [ ] Pi synthesizes and contextualizes the findings
- [ ] User receives concise, actionable summary

---

**Core principle:** Gemini is Pi's eyes and ears to the outside world. Delegate research, ingest only final results, and always let Pi synthesize and decide.
