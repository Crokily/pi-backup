---
name: pi-self-extension
description: Guide for extending pi coding agent following official standards. Use when creating extensions (custom tools with TypeScript), skills (reusable workflows with bundled resources), or prompt templates. Ensures compliance with pi extension API, skill specification (agentskills.io), directory structure, and progressive disclosure patterns.
---

# Pi Self-Extension Guide

This skill provides authoritative guidance for extending pi in accordance with official standards. Use this when adding new capabilities to ensure architectural consistency and proper integration.

## Core Extension Mechanisms

Pi supports three primary extension mechanisms:

1. **Extensions** (`.ts` files) - Custom tools, event handlers, commands using the Extension API
2. **Skills** (SKILL.md + resources) - Domain workflows with scripts, references, and assets
3. **Prompt Templates** (`.md` files) - Reusable prompt snippets with argument expansion

## Directory Structure Standard

Official pi directory layout:

```
~/.pi/agent/                    # Global scope
├── extensions/                 # TypeScript extensions
│   ├── web-search.ts          # Single-file extension
│   └── my-extension/          # Multi-file extension
│       ├── index.ts           # Entry point (exports default function)
│       ├── package.json       # Optional: for npm dependencies
│       └── node_modules/      # After npm install
├── skills/                     # Skill packages
│   └── research/
│       ├── SKILL.md           # Required: frontmatter + instructions
│       ├── scripts/           # Executable code
│       ├── references/        # Loaded on-demand docs
│       └── assets/            # Output templates/files
├── prompts/                    # Prompt templates
│   └── review.md              # Invoked as /review
├── bin/                        # Helper binaries (optional)
│   └── fd                     # Fast file search
└── settings.json              # Pi configuration

.pi/                            # Project-local scope
├── extensions/                 # Project extensions
├── skills/                     # Project skills
├── prompts/                    # Project prompts
└── settings.json              # Project settings
```

**Auto-discovery rules:**
- Extensions: `*.ts` in root, or `*/index.ts` in subdirectories
- Skills: Direct `.md` files or recursive `SKILL.md` under subdirectories
- Prompts: `*.md` files (non-recursive)

## Decision Tree: Which Mechanism to Use

```
Need to extend pi?
│
├─ Custom tool the LLM can invoke?
│  ├─ Yes → Extension with registerTool()
│  │         Examples: web_search, database_query, image_process
│  │
│  └─ No → Continue
│
├─ Domain-specific workflow with reusable resources?
│  ├─ Yes → Skill
│  │         Examples: pdf-processing, brand-guidelines, big-query
│  │
│  └─ No → Continue
│
└─ Reusable prompt snippet?
   └─ Yes → Prompt Template
             Examples: /review, /component, /test
```

## Extension Development (TypeScript)

### When to Use Extensions

- Register custom tools callable by LLM
- Intercept events (tool calls, session lifecycle)
- Add commands (`/mycommand`)
- Modify system prompt or context
- Custom UI components
- State management across turns

### Mandatory Extension Structure

Location: `~/.pi/agent/extensions/web-search.ts`

```typescript
import type { ExtensionAPI } from "@mariozechner/pi-coding-agent";
import { Type } from "@sinclair/typebox";

export default function (pi: ExtensionAPI) {
  // Register tools
  pi.registerTool({
    name: "web_search",
    label: "Web Search",
    description: "Search web via Bing RSS and fetch content",
    parameters: Type.Object({
      query: Type.String({ description: "Search query" }),
      limit: Type.Optional(Type.Number({ default: 5 })),
      fetchContent: Type.Optional(Type.Number()),
    }),
    async execute(toolCallId, params, signal, onUpdate, ctx) {
      // Implementation
      const result = await pi.exec("python3", [
        "/home/ubuntu/web_search.py",
        params.query,
        "-n",
        String(params.limit ?? 5)
      ], { signal });
      
      return {
        content: [{ type: "text", text: result.stdout }],
        details: { query: params.query }
      };
    }
  });

  // Register commands
  pi.registerCommand("search", {
    description: "Quick web search",
    handler: async (args, ctx) => {
      ctx.ui.notify(`Searching: ${args}`, "info");
    }
  });

  // Event handlers
  pi.on("session_start", async (_event, ctx) => {
    ctx.ui.notify("Extension loaded", "info");
  });
}
```

### Extension API Checklist

- ✅ Export default function accepting `ExtensionAPI`
- ✅ Use `pi.registerTool()` for LLM-callable tools
- ✅ Use `pi.registerCommand()` for `/slash` commands
- ✅ Use `pi.on()` for event interception
- ✅ Return proper result shapes with `content` and `details`
- ✅ Support cancellation via `signal`
- ✅ Truncate output (50KB/2000 lines max)
- ✅ Use `StringEnum` from `@mariozechner/pi-ai` for enums

### Output Truncation (Mandatory)

**All tools MUST truncate output** to avoid context overflow:

```typescript
import {
  truncateHead,
  DEFAULT_MAX_BYTES,
  DEFAULT_MAX_LINES,
  formatSize,
} from "@mariozechner/pi-coding-agent";

async execute(toolCallId, params, signal, onUpdate, ctx) {
  const output = await runCommand();
  
  const truncation = truncateHead(output, {
    maxLines: DEFAULT_MAX_LINES,  // 2000
    maxBytes: DEFAULT_MAX_BYTES,   // 50KB
  });

  let result = truncation.content;
  
  if (truncation.truncated) {
    const tempFile = "/tmp/output.txt";
    await fs.writeFile(tempFile, output);
    
    result += `\n\n[Output truncated: ${truncation.outputLines} of ${truncation.totalLines} lines`;
    result += ` (${formatSize(truncation.outputBytes)} of ${formatSize(truncation.totalBytes)}).`;
    result += ` Full output: ${tempFile}]`;
  }

  return { content: [{ type: "text", text: result }] };
}
```

### Testing Extensions

```bash
# Test without installing
pi -e ~/.pi/agent/extensions/web-search.ts

# Install and reload
pi
/reload
```

## Skill Development (SKILL.md)

### When to Use Skills

- Multi-step domain workflows
- Bundled scripts/references/assets
- Procedural knowledge not in LLM training
- Company-specific schemas/templates
- Progressive disclosure (load docs on-demand)

### Skill Creation Workflow

```bash
# 1. Initialize
cd /home/ubuntu/.agents/skills/skill-creator
python3 scripts/init_skill.py my-skill --path ~/.pi/agent/skills

# 2. Structure (delete unneeded dirs)
~/.pi/agent/skills/my-skill/
├── SKILL.md              # Required
├── scripts/              # Optional: executable code
├── references/           # Optional: loaded on-demand
└── assets/              # Optional: output templates

# 3. Edit SKILL.md (see template below)

# 4. Validate and package
python3 scripts/package_skill.py ~/.pi/agent/skills/my-skill
```

### SKILL.md Template

```markdown
---
name: my-skill
description: Complete description of what the skill does AND when to use it. Include specific triggers: file types, domains, task categories. Example: "PDF manipulation including rotation, merging, form filling. Use when working with PDF documents for editing, extraction, or analysis."
---

# My Skill

## Quick Start

[Minimal example showing the most common use case]

\`\`\`bash
./scripts/process.sh input.txt
\`\`\`

## Workflow

[Step-by-step instructions]

## Advanced Features

- **Feature A**: See [references/feature-a.md](references/feature-a.md)
- **Feature B**: See [references/feature-b.md](references/feature-b.md)

## Scripts

- `scripts/process.sh` - Main processing script
- `scripts/validate.py` - Input validation
```

### Skill Frontmatter Rules

| Field | Required | Rules |
|-------|----------|-------|
| `name` | Yes | 1-64 chars, lowercase a-z0-9-, match directory |
| `description` | Yes | Max 1024 chars, include "when to use" |
| `license` | No | License name or file reference |
| `compatibility` | No | Environment requirements |
| `metadata` | No | Arbitrary key-value |

### Progressive Disclosure Pattern

Keep SKILL.md under 500 lines. Split content:

```
pdf-skill/
├── SKILL.md                    # Quick start + navigation
└── references/
    ├── rotation.md             # Loaded when needed
    ├── forms.md                # Loaded when needed
    └── api-reference.md        # Loaded when needed
```

**In SKILL.md:**
```markdown
## PDF Rotation

Rotate pages with pdfplumber. See [rotation.md](references/rotation.md) for details.

## Form Filling

See [forms.md](references/forms.md) for complete guide.
```

### Validation

```bash
python3 scripts/quick_validate.py ~/.pi/agent/skills/my-skill
```

Common errors:
- Name doesn't match directory
- Description missing or > 1024 chars
- Name contains invalid characters
- Missing SKILL.md

## Prompt Templates

### When to Use

- Reusable prompt snippets
- Common review workflows
- Code generation patterns
- Argument-based templates

### Template Structure

Location: `~/.pi/agent/prompts/review.md`

```markdown
---
description: Review code for bugs and security
---
Review the code in $1. Focus on:
- Logic errors and edge cases
- Security vulnerabilities
- Missing error handling
- Performance issues

Context: ${@:2}
```

Usage: `/review src/app.ts "payment processing module"`

### Argument Expansion

- `$1`, `$2`, ... - Positional args
- `$@` or `$ARGUMENTS` - All args joined
- `${@:N}` - Args from Nth position
- `${@:N:L}` - L args starting at N

## Migration Guide: Current → Standard

### Migrate web-search (bash script → Extension)

Current (non-standard):
```
~/.pi/agent/bin/web-search      # Bash wrapper
~/web_search.py                 # Python script
```

Standard migration:
```typescript
// ~/.pi/agent/extensions/web-search.ts
import type { ExtensionAPI } from "@mariozechner/pi-coding-agent";
import { Type } from "@sinclair/typebox";

export default function (pi: ExtensionAPI) {
  pi.registerTool({
    name: "web_search",
    label: "Web Search",
    description: "Search web and fetch content via Bing RSS",
    parameters: Type.Object({
      query: Type.String({ description: "Search query" }),
      limit: Type.Optional(Type.Number({ default: 5 })),
      fetchContent: Type.Optional(Type.Number()),
    }),
    async execute(toolCallId, params, signal, onUpdate, ctx) {
      const args = [params.query, "-n", String(params.limit ?? 5)];
      if (params.fetchContent) {
        args.push("--open", String(params.fetchContent));
      }
      
      const result = await pi.exec(
        "python3",
        ["/home/ubuntu/web_search.py", ...args],
        { signal, timeout: 30000 }
      );
      
      return {
        content: [{ type: "text", text: result.stdout }],
        details: { exitCode: result.code }
      };
    }
  });
}
```

**Benefits:**
- LLM auto-discovers tool (appears in system prompt)
- Type-safe parameters
- Proper error handling
- Hot-reloadable via `/reload`

### Migrate fd (binary → Extension or keep as-is)

**Option 1: Keep as-is** (acceptable for simple binaries)
- Already in PATH via `~/.pi/agent/bin/`
- Document in skill or system prompt

**Option 2: Wrap as extension** (better discoverability)
```typescript
pi.registerTool({
  name: "find_fast",
  label: "Fast Find",
  description: "Fast file search using fd",
  parameters: Type.Object({
    pattern: Type.String(),
    path: Type.Optional(Type.String({ default: "." })),
  }),
  async execute(toolCallId, params, signal, onUpdate, ctx) {
    const result = await pi.exec(
      "~/.pi/agent/bin/fd",
      [params.pattern, params.path],
      { signal }
    );
    return { content: [{ type: "text", text: result.stdout }] };
  }
});
```

## Common Patterns

### Research Workflow Skill

Create `~/.pi/agent/skills/research/SKILL.md`:

```markdown
---
name: research
description: Multi-source research workflow with web search, content extraction, and synthesis. Use for fact-finding, documentation lookup, or gathering information from web sources.
---

# Research Workflow

## Quick Research

1. Use `web_search` tool with query
2. Review top 5 results
3. Use `--open N` to fetch content
4. Synthesize findings

## Deep Research

1. Initial broad search
2. Identify key sources
3. Fetch full content
4. Cross-reference information
5. Generate summary with citations

## Examples

User: "Research the latest features of Next.js 15"
1. web_search("Next.js 15 features", limit=5)
2. Open official docs and release notes
3. Summarize new features
```

### Permission Gate Extension

```typescript
// ~/.pi/agent/extensions/safety.ts
import type { ExtensionAPI } from "@mariozechner/pi-coding-agent";

export default function (pi: ExtensionAPI) {
  pi.on("tool_call", async (event, ctx) => {
    if (event.toolName === "bash") {
      const cmd = event.input.command;
      
      if (cmd.includes("rm -rf") || cmd.includes("sudo")) {
        const ok = await ctx.ui.confirm(
          "Dangerous Command",
          `Allow: ${cmd}?`
        );
        if (!ok) {
          return { block: true, reason: "User rejected" };
        }
      }
    }
  });
}
```

## Validation Checklist

Before considering an extension complete:

**Extensions:**
- [ ] File in `~/.pi/agent/extensions/` or `.pi/extensions/`
- [ ] Exports default function with ExtensionAPI
- [ ] Tools use `pi.registerTool()` with proper schema
- [ ] Output truncation implemented
- [ ] Cancellation support via `signal`
- [ ] Tested with `pi -e ./extension.ts`

**Skills:**
- [ ] Directory in `~/.pi/agent/skills/`
- [ ] SKILL.md with valid frontmatter
- [ ] Name matches directory (lowercase a-z0-9-)
- [ ] Description includes "when to use"
- [ ] Scripts tested and executable
- [ ] References organized by domain
- [ ] SKILL.md under 500 lines
- [ ] Validated with `quick_validate.py`

**Prompt Templates:**
- [ ] File in `~/.pi/agent/prompts/`
- [ ] Frontmatter with description
- [ ] Filename = command name
- [ ] Arguments tested

## References

**Official Documentation:**
- Extensions: See [extensions.md](https://github.com/badlogic/pi-mono/blob/main/packages/coding-agent/docs/extensions.md)
- Skills: See [skills.md](https://github.com/badlogic/pi-mono/blob/main/packages/coding-agent/docs/skills.md)
- Prompt Templates: See [prompt-templates.md](https://github.com/badlogic/pi-mono/blob/main/packages/coding-agent/docs/prompt-templates.md)
- Agent Skills Standard: https://agentskills.io/specification

**Example Collections:**
- Extensions: `/usr/local/lib/node_modules/@mariozechner/pi-coding-agent/examples/extensions/`
- Skills: Available via `pi install` (see pi.dev packages)

## Quick Commands

```bash
# Create new skill
cd ~/.agents/skills/skill-creator
python3 scripts/init_skill.py my-skill --path ~/.pi/agent/skills

# Validate skill
python3 scripts/quick_validate.py ~/.pi/agent/skills/my-skill

# Package skill
python3 scripts/package_skill.py ~/.pi/agent/skills/my-skill

# Test extension
pi -e ~/.pi/agent/extensions/my-ext.ts

# Reload extensions/skills
pi
/reload
```
