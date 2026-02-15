---
name: ralph-loop
description: "Autonomous AI agent loop for iterative PRD-driven development. Generates PRDs, converts to prd.json, and executes user stories one at a time with quality gates, progress tracking, and pattern consolidation. Use when asked to: create a PRD, plan a feature, run ralph, autonomous development loop, iterative implementation, execute prd stories, or build a feature end-to-end autonomously."
---

# Ralph Loop — Autonomous Iterative Development

An autonomous coding workflow based on the [Ralph pattern](https://github.com/snarktank/ralph). Each iteration picks one user story from a `prd.json`, implements it, runs quality checks, commits, and tracks progress. Memory persists across iterations via git history, `progress.txt`, and `prd.json`.

---

## Quick Start

### Option A: Full Autonomous Loop (recommended)

```bash
# Generate PRD, convert to JSON, then run the loop
~/.pi/agent/skills/ralph-loop/scripts/ralph.sh [max_iterations]
```

### Option B: Manual Step-by-Step

1. **Create PRD**: Ask pi to "create a PRD for [feature]"
2. **Convert**: Ask pi to "convert the PRD to prd.json"
3. **Execute**: Ask pi to "run one ralph iteration"
4. **Repeat**: Keep running iterations until all stories pass

---

## Three Modes of Operation

### Mode 1: PRD Generation

**Triggers**: "create a prd", "write requirements for", "plan this feature"

When asked to generate a PRD:

1. Ask 3-5 clarifying questions with lettered options (A/B/C/D) so user can respond like "1A, 2C, 3B"
2. Generate a structured PRD with sections: Introduction, Goals, User Stories, Functional Requirements, Non-Goals, Technical Considerations, Success Metrics
3. Save to `tasks/prd-[feature-name].md`

See [references/prd-guide.md](references/prd-guide.md) for detailed format.

**Critical rules for user stories:**
- Each story must be completable in ONE iteration (one context window)
- Stories ordered by dependency (schema → backend → UI)
- Acceptance criteria must be verifiable, not vague
- UI stories must include "Verify in browser" criterion
- Always include "Typecheck/lint passes" as criterion

### Mode 2: PRD → prd.json Conversion

**Triggers**: "convert prd to json", "create prd.json", "ralph format"

Convert a markdown PRD to the structured JSON format:

```json
{
  "project": "ProjectName",
  "branchName": "ralph/feature-name",
  "description": "Feature description",
  "qualityChecks": {
    "typecheck": "npm run typecheck",
    "lint": "npm run lint",
    "test": "npm run test"
  },
  "userStories": [
    {
      "id": "US-001",
      "title": "Story title",
      "description": "As a [user], I want [feature] so that [benefit]",
      "acceptanceCriteria": ["Criterion 1", "Criterion 2", "Typecheck passes"],
      "priority": 1,
      "passes": false,
      "notes": ""
    }
  ]
}
```

See [references/story-sizing.md](references/story-sizing.md) for how to size stories.

### Mode 3: Execute One Iteration

**Triggers**: "run ralph", "next ralph iteration", "execute next story"

Follow this exact sequence:

1. **Read** `prd.json` in the project root (or specified path)
2. **Read** `progress.txt` — check the `Codebase Patterns` section first
3. **Check branch** — ensure you're on the branch from `prd.json.branchName`. Create from main if needed.
4. **Pick story** — select highest priority story where `passes: false`
5. **Implement** — make the code changes for that ONE story
6. **Quality checks** — run the commands in `prd.json.qualityChecks` (or project's standard checks)
7. **Commit** — if checks pass: `git add -A && git commit -m "feat: [Story ID] - [Story Title]"`
8. **Update PRD** — set `passes: true` for the completed story
9. **Update progress** — append to `progress.txt` (see format below)
10. **Consolidate patterns** — update `Codebase Patterns` section if reusable patterns discovered
11. **Check completion** — if ALL stories have `passes: true`, output `<promise>COMPLETE</promise>`

### Progress Report Format

APPEND to `progress.txt` (never replace):

```
## [Date/Time] - [Story ID]: [Story Title]
- What was implemented
- Files changed
- **Learnings for future iterations:**
  - Patterns discovered
  - Gotchas encountered
  - Useful context
---
```

### Codebase Patterns (top of progress.txt)

If you discover reusable patterns, add them to `## Codebase Patterns` at the TOP:

```
## Codebase Patterns
- Use `sql<number>` template for aggregations
- Always use `IF NOT EXISTS` for migrations
- Export types from actions.ts for UI components
```

---

## Running the Autonomous Loop

The shell script `scripts/ralph.sh` drives the loop by spawning fresh pi instances:

```bash
# Run with default 10 iterations
~/.pi/agent/skills/ralph-loop/scripts/ralph.sh

# Run with custom iteration count
~/.pi/agent/skills/ralph-loop/scripts/ralph.sh 20

# Specify prd.json location
~/.pi/agent/skills/ralph-loop/scripts/ralph.sh --prd ./my-feature/prd.json 10
```

Each iteration:
- Spawns a **fresh pi instance** with clean context
- Feeds it the iteration prompt from `scripts/prompt.md`
- Checks for `<promise>COMPLETE</promise>` to stop
- Archives previous runs when branch changes

---

## Key Design Principles

### Fresh Context Per Iteration
Each iteration is a new instance. No context bleed. Memory only via:
- **Git history** — commits from previous iterations
- **progress.txt** — append-only learnings
- **prd.json** — which stories are done

### One Story Per Iteration
Never attempt multiple stories. One story, one commit, one iteration.

### Small Tasks
If a story can't be described in 2-3 sentences, it's too big. Split it.

**Right-sized**: Add a database column and migration
**Too big**: Build the entire dashboard

### Quality Gates
Every commit MUST pass quality checks. Broken code compounds across iterations.

### Knowledge Accumulation
Progress.txt is the institutional memory. Future iterations read it first.

---

## File Reference

| File | Purpose |
|------|---------|
| `prd.json` | User stories with pass/fail status |
| `progress.txt` | Append-only learnings across iterations |
| `tasks/prd-*.md` | Source PRD documents |
| `scripts/ralph.sh` | Autonomous loop driver |
| `scripts/prompt.md` | Prompt template for each iteration |

---

## Advanced: Customization

### Project-Specific Quality Checks

Add a `qualityChecks` object to `prd.json`:

```json
{
  "qualityChecks": {
    "typecheck": "npx tsc --noEmit",
    "lint": "npx eslint . --fix",
    "test": "npm test",
    "build": "npm run build"
  }
}
```

### Browser Verification for UI Stories

For stories that change UI, use the `agent-browser` skill:

```bash
agent-browser open http://localhost:3000/page
agent-browser snapshot -i
# Verify UI elements match acceptance criteria
agent-browser screenshot
```

---

## References

- [PRD Writing Guide](references/prd-guide.md) — Detailed PRD format and best practices
- [Story Sizing Guide](references/story-sizing.md) — How to size stories for one-iteration completion
- [prd.json Template](assets/prd.json.template) — Example JSON structure
