# Skill Structure Examples

## Example 1: PDF Processing Skill

**Directory Structure:**
```
pdf-processing/
├── SKILL.md                    # Main workflow
├── scripts/
│   ├── rotate.py              # Rotate pages
│   ├── merge.py               # Merge PDFs
│   ├── split.py               # Split pages
│   └── extract_text.py        # Text extraction
├── references/
│   ├── forms.md               # Form filling guide
│   └── api-reference.md       # pdfplumber API docs
└── assets/
    └── form-template.pdf      # Example form
```

**SKILL.md (condensed):**
```markdown
---
name: pdf-processing
description: PDF manipulation including rotation, merging, splitting, form filling, and text extraction. Use when working with PDF documents for editing, analysis, or automation.
---

# PDF Processing

## Quick Start

Rotate a PDF:
\`\`\`bash
./scripts/rotate.py input.pdf --angle 90 --output rotated.pdf
\`\`\`

## Operations

### Merge PDFs
\`\`\`bash
./scripts/merge.py file1.pdf file2.pdf --output merged.pdf
\`\`\`

### Split Pages
\`\`\`bash
./scripts/split.py document.pdf --pages 1-5 --output section.pdf
\`\`\`

### Extract Text
\`\`\`bash
./scripts/extract_text.py document.pdf --output text.txt
\`\`\`

### Form Filling
See [references/forms.md](references/forms.md) for complete guide.

## API Reference
For advanced usage, see [references/api-reference.md](references/api-reference.md).
```

---

## Example 2: Brand Guidelines Skill

**Directory Structure:**
```
brand-guidelines/
├── SKILL.md                    # Brand usage guide
├── references/
│   ├── colors.md              # Color palette specs
│   ├── typography.md          # Font specifications
│   └── voice.md               # Brand voice guidelines
└── assets/
    ├── logo.svg               # Logo files
    ├── powerpoint-template.pptx
    └── fonts/
        ├── brand-regular.ttf
        └── brand-bold.ttf
```

**SKILL.md:**
```markdown
---
name: brand-guidelines
description: Company brand guidelines including colors, typography, logo usage, and voice. Use when creating marketing materials, presentations, or any branded content.
---

# Brand Guidelines

## Quick Reference

**Primary Colors:**
- Brand Blue: #0066CC
- Brand Red: #CC0000

See [references/colors.md](references/colors.md) for complete palette.

## Logo Usage

Use logo from `assets/logo.svg`:
- Minimum size: 40px height
- Clear space: Logo height × 0.5
- Do not distort or recolor

## Typography

Primary font: Brand Sans (see `assets/fonts/`)
See [references/typography.md](references/typography.md) for hierarchy.

## Brand Voice

See [references/voice.md](references/voice.md) for tone guidelines.

## Templates

- PowerPoint: `assets/powerpoint-template.pptx`
```

---

## Example 3: BigQuery Skill

**Directory Structure:**
```
bigquery/
├── SKILL.md                    # Overview and workflow
└── references/
    ├── finance.md              # Revenue, billing schemas
    ├── sales.md                # Pipeline, opportunities
    ├── product.md              # API usage, features
    └── marketing.md            # Campaigns, attribution
```

**SKILL.md:**
```markdown
---
name: bigquery
description: Query company BigQuery datasets for analytics across finance, sales, product, and marketing domains. Use when answering data questions about revenue, users, campaigns, or business metrics.
---

# BigQuery Analytics

## Domain References

Load the relevant domain reference when working with specific datasets:

- **Finance metrics**: See [references/finance.md](references/finance.md)
  - Revenue, billing, invoices
  - Tables: `revenue`, `invoices`, `subscriptions`

- **Sales data**: See [references/sales.md](references/sales.md)
  - Pipeline, opportunities, deals
  - Tables: `opportunities`, `accounts`, `contacts`

- **Product analytics**: See [references/product.md](references/product.md)
  - API usage, features, adoption
  - Tables: `api_logs`, `feature_flags`, `user_sessions`

- **Marketing campaigns**: See [references/marketing.md](references/marketing.md)
  - Campaigns, attribution, conversions
  - Tables: `campaigns`, `conversions`, `ad_spend`

## Query Pattern

\`\`\`python
from google.cloud import bigquery

client = bigquery.Client(project="company-prod")
query = """
  SELECT DATE(created_at) as date, COUNT(*) as count
  FROM \`company-prod.analytics.events\`
  WHERE DATE(created_at) >= DATE_SUB(CURRENT_DATE(), INTERVAL 7 DAY)
  GROUP BY date
  ORDER BY date
"""
results = client.query(query).to_dataframe()
\`\`\`
```

---

## Example 4: Web Development Skill

**Directory Structure:**
```
web-dev/
├── SKILL.md                    # Workflow and navigation
├── scripts/
│   ├── init-project.sh        # Project scaffolding
│   └── validate-html.py       # HTML validation
├── references/
│   ├── react-patterns.md      # React best practices
│   ├── css-guide.md           # CSS organization
│   └── accessibility.md       # A11y checklist
└── assets/
    └── frontend-template/
        ├── index.html
        ├── style.css
        └── app.js
```

**SKILL.md:**
```markdown
---
name: web-dev
description: Modern web development workflows for React, HTML, and CSS including scaffolding, patterns, and accessibility. Use when creating web applications, components, or responsive layouts.
---

# Web Development

## Quick Start

Initialize project:
\`\`\`bash
./scripts/init-project.sh my-app
cd my-app
\`\`\`

## Framework Selection

**React:** See [references/react-patterns.md](references/react-patterns.md)
- Component composition
- State management
- Hooks patterns

**Vanilla HTML/CSS/JS:** Use template from `assets/frontend-template/`

## Styling

See [references/css-guide.md](references/css-guide.md) for:
- CSS organization
- Responsive patterns
- Design tokens

## Accessibility

See [references/accessibility.md](references/accessibility.md) for A11y checklist.
```

---

## Example 5: Research Workflow Skill

**Directory Structure:**
```
research/
├── SKILL.md                    # Research workflow
└── references/
    └── sources.md              # Trusted sources catalog
```

**SKILL.md:**
```markdown
---
name: research
description: Multi-source research workflow with search, extraction, and synthesis. Use for fact-finding, documentation lookup, or gathering information from web, academic, or company sources.
---

# Research Workflow

## Quick Research (Single Source)

1. Search: Use `web_search` tool
2. Review: Check top 5 results
3. Extract: Fetch relevant content
4. Summarize: Synthesize key points

Example:
\`\`\`
User: "What are the main features of Rust async?"
1. web_search("Rust async features 2024")
2. Open official Rust docs
3. Extract async/await, Tokio info
4. Summarize with code examples
\`\`\`

## Deep Research (Multi-Source)

1. **Broad search**: General query, identify domains
2. **Source evaluation**: Check authority, recency
3. **Deep dive**: Fetch full content from 3-5 sources
4. **Cross-reference**: Verify facts across sources
5. **Synthesis**: Create comprehensive summary with citations

Example:
\`\`\`
User: "Research state of LLM reasoning in 2024"
1. web_search("LLM reasoning capabilities 2024")
2. Identify: Academic papers, company blogs, benchmarks
3. Fetch: OpenAI, Anthropic, Google research
4. Cross-check: Claims across sources
5. Synthesize: Timeline, capabilities, limitations
\`\`\`

## Company Research

For internal docs, use:
- Confluence: [internal wiki URL]
- GitHub: Company repos
- Slack: Engineering channels

## Source Evaluation

See [references/sources.md](references/sources.md) for trusted source catalog.

Criteria:
- Authority: Official docs, peer-reviewed, reputable orgs
- Recency: Publication date, last updated
- Relevance: Directly answers question
- Consensus: Corroborated by multiple sources
```

---

## Key Patterns

### Pattern 1: Tool-Based (scripts heavy)
- PDF processing, image manipulation
- Scripts do the work, SKILL.md guides usage
- Keep SKILL.md minimal, script docs in references

### Pattern 2: Knowledge-Based (references heavy)
- Brand guidelines, company schemas, BigQuery
- SKILL.md is navigation hub
- Split by domain/category into references

### Pattern 3: Workflow-Based (procedural)
- Research, code review, deployment
- SKILL.md contains step-by-step process
- References for deep dives

### Pattern 4: Template-Based (assets heavy)
- Web dev, presentations, documents
- SKILL.md explains when to use which template
- Assets are boilerplate/starting points

## Progressive Disclosure Checklist

- [ ] SKILL.md under 500 lines
- [ ] Core workflow in SKILL.md
- [ ] Details in references (linked clearly)
- [ ] Scripts documented but not duplicated
- [ ] Assets referenced, not embedded
- [ ] No more than 1 level of references
- [ ] Table of contents in long references
- [ ] Clear "when to read" guidance
