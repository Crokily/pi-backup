---
name: codex-collaboration
description: Guidelines for delegating all software engineering work to Codex CLI. Use non-interactive execution and ingest only final results to keep the main agent context clean.
---

# Codex Collaboration Guide (Result-Only, Non-Interactive)

## Mission

Codex is the primary executor for coding tasks. The main agent should:
1. Detect coding work early
2. Package context clearly
3. Delegate with `codex exec` (non-interactive)
4. Read only final outputs after Codex exits

---

## Mandatory Rules

### 1) Always use non-interactive mode
Use `codex exec` (or `codex e`) for all delegated coding tasks.

### 2) Default to `--yolo` in hardened environments
Use `--dangerously-bypass-approvals-and-sandbox` (`--yolo`) to avoid approval pauses.

> Safety note (from Codex CLI reference): `--yolo` bypasses approvals and sandboxing. Use only in externally hardened/isolated runners.

### 3) Never stream Codex run output into current session context
**Critical:** Do not let Codex progress logs/tool chatter pollute this agent context.

Enforce all of the following:
- Use `--output-last-message <file>` to capture Codex final answer
- Redirect stdout/stderr to a log file (`>log 2>&1`)
- Only read the final message file after process exits
- Only inspect log file on failure, and summarize briefly

### 4) Avoid interactive `codex` TUI in normal delegation
Default to non-interactive `codex exec`.

Exception: if an explicit slash-command workflow is requested (for example `/review`), run it in an isolated Codex session and only return the final summary.

---

## Canonical Execution Pattern

```bash
# 1) Prepare files
PROMPT_FILE=$(mktemp /tmp/codex-prompt.XXXXXX.md)
RESULT_FILE=$(mktemp /tmp/codex-result.XXXXXX.txt)
LOG_FILE=$(mktemp /tmp/codex-run.XXXXXX.log)

# 2) Write prompt content into $PROMPT_FILE (requirements, files, constraints)

# 3) Run Codex non-interactively, no streaming into current context
codex exec \
  --model gpt-5.3-codex-xhigh \
  --yolo \
  --output-last-message "$RESULT_FILE" \
  - < "$PROMPT_FILE" > "$LOG_FILE" 2>&1
CODEX_EXIT=$?

# 4) Post-run handling
# - If CODEX_EXIT=0: consume ONLY $RESULT_FILE
# - If CODEX_EXIT!=0: inspect $LOG_FILE minimally and report concise failure summary
```

Optional for automation/CI logging:
```bash
codex exec --model gpt-5.3-codex-xhigh --yolo --json --output-last-message "$RESULT_FILE" - \
  < "$PROMPT_FILE" > "$LOG_FILE" 2>&1
```
`--json` emits JSONL events, but they must stay in log files, not in chat context.

---

## Delegation Workflow

### Step 1: Identify coding tasks (delegate immediately)
Delegate tasks like implementation, refactor, debugging, tests, architecture, performance tuning, migrations, config/code review.

### Step 2: Prepare complete prompt context
Include:
- Task objective
- Relevant files/paths
- Constraints and non-goals
- Expected output format
- Validation/test expectations

### Step 3: Execute with result isolation
Use the canonical pattern above (`codex exec + --yolo + -o + stdout/stderr redirection`).

### Step 4: Read only final result
- Success: read and use `RESULT_FILE` only
- Failure: read minimal log snippets and summarize; do not dump full logs

### Step 5: Integrate and verify
Run tests/checks, verify changed files, then present concise summary to user.

---

## Review Tasks (Working Tree Review)

When the user asks for a code review, treat it as a first-class Codex delegation scenario.

### Preferred path (still non-interactive, result-only)
Use `codex exec` with a review-focused prompt and keep output isolated:

```bash
PROMPT_FILE=$(mktemp /tmp/codex-review-prompt.XXXXXX.md)
RESULT_FILE=$(mktemp /tmp/codex-review-result.XXXXXX.txt)
LOG_FILE=$(mktemp /tmp/codex-review-run.XXXXXX.log)

cat > "$PROMPT_FILE" <<'EOF'
Review the current Git working tree.
Focus on:
1) behavior changes and regressions
2) correctness and edge cases
3) missing/insufficient tests
4) security/performance risks

Output format:
- Findings (severity: high/medium/low)
- Evidence (file + rationale)
- Recommended fixes
- Test gaps
EOF

codex exec --model gpt-5.3-codex-xhigh --yolo --output-last-message "$RESULT_FILE" - \
  < "$PROMPT_FILE" > "$LOG_FILE" 2>&1
```

### CLI slash command reference (`/review`)
From Codex CLI slash-commands docs:
- `/review`: ask Codex to review the current working tree
- `/diff`: optionally inspect exact file changes after review
- Expected behavior: emphasizes behavior changes and missing tests
- Model behavior: uses current session model, unless `review_model` is set in `config.toml`

### Policy for using `/review` with this skill
`/review` is an interactive slash command. If you use it:
- run it in an isolated Codex session
- do **not** stream or paste in-flight transcript into this chat
- only bring back the final review summary

---

## Prompt Template for Codex

Use this structure in `PROMPT_FILE`:

```text
Task:
[clear description]

Repository context:
- Working directory: [path]
- Relevant files:
  - [file1]
  - [file2]

Requirements:
1. ...
2. ...

Constraints:
- ...

Validation:
- Run: [test/lint/build commands]
- Expect: [expected outcomes]

Deliverables:
- Modified files list
- What changed and why
- Any tradeoffs / follow-ups
```

---

## Communication Policy

### Before running Codex
"这是编码任务，我将委托 Codex 以非交互模式执行，并在结束后仅返回最终结果。"

### After success
- Provide concise summary based on final result file
- List modified files and validation status
- Offer follow-up edits

### After failure
- Report failure briefly (exit status + high-level reason)
- Include minimal diagnostic summary from log
- Propose retry plan (adjust prompt/constraints/env)

---

## Anti-Patterns (Forbidden)

- Running interactive `codex` TUI by default (or without isolation/final-result-only handling)
- Posting Codex streaming output directly into current conversation
- Parsing partial in-flight output as final result
- Mixing `--full-auto` and `--yolo` casually (follow CLI safety guidance)
- Using stale invocation style (e.g., old prompt flags)

---

## Operational Notes from CLI Reference

- Put flags after subcommand for subcommand runs (e.g., `codex exec --model ...`)
- `codex exec` is the supported path for non-interactive/CI-style work
- `--output-last-message` is the key primitive for clean, post-run ingestion
- Pair `--json` with `--output-last-message` when machine-readable logs are needed

---

## Quick Checklist

Before run:
- [ ] Coding task identified
- [ ] Prompt file prepared with full context
- [ ] Using `codex exec`
- [ ] Using `--yolo` (only in hardened environment)
- [ ] Using `--output-last-message`
- [ ] Redirecting stdout/stderr to log file

After run:
- [ ] Exit code checked
- [ ] Only final message file consumed on success
- [ ] Logs consulted only if needed
- [ ] User receives concise final summary

---

**Core principle:** Delegate coding to Codex, but ingest only post-run final output. Keep process noise out of the main agent context.
