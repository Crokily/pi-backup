---
name: md-to-web-report
description: Convert Markdown documents into beautiful, readable single-file HTML web pages and deploy them to the standalone web report site. Use when the user asks to "turn this markdown into a web page", "make this report into a web page", "deploy this as a web page", "render this markdown nicely", "把这个 md 转成网页", "生成网页报告", or any request to convert markdown/report content into a hosted, styled HTML page for easy reading and sharing.
---

# Markdown → Web Report

Convert Markdown into a polished single-file HTML page and deploy to the standalone web report directory at `/var/www/docs.a2a.ing/`.

## Workflow

### 1. Read the source markdown
Load the `.md` file or accept inline markdown content from context.

### 2. Build the HTML page

Use the template at `assets/report-template.html` as the structural foundation. Read it, then customize:

#### Required customizations (fill all `{{placeholders}}`):

| Placeholder | What to fill |
|---|---|
| `{{TITLE}}` | Page `<title>` |
| `{{HERO_BADGE}}` | Small badge text in hero (e.g. "2025-2026 · 深度调研") |
| `{{HERO_TITLE}}` | Main hero heading — can include `<span>` for accent color |
| `{{HERO_SUBTITLE}}` | Italic subtitle below heading |
| `{{HERO_META}}` | HTML for meta pills (date, author, tags). Use `<span>` with SVG icons and dot separators |
| `{{DECORATIVE_SYMBOLS}}` | 6-8 `<span>` elements with themed symbols positioned absolutely. Pick symbols matching the topic (e.g. math: ∇∑∂θ, code: {}</>λ, business: $%↗△) |
| `{{MARKDOWN_CONTENT}}` | The full markdown content (escaped for JS template literal — see escaping rules below) |
| `{{FOOTER_LEFT}}` | Footer left text |
| `{{FOOTER_RIGHT}}` | Footer right text (usually generation date) |

#### Optional customizations for visual distinctiveness:

- **`{{EXTRA_FONTS}}`**: Additional Google Fonts `<link>` tags if changing typography
- **`{{EXTRA_STYLES}}`**: Additional CSS rules injected inside the `<style>` block
- **Override CSS variables** in `:root` to change the color palette. Examples:
  - Academic: `--accent-primary: #2d4a7a; --accent-secondary: #c9a54e;`
  - Tech: `--accent-primary: #0ea5e9; --accent-secondary: #a855f7;`
  - Nature: `--accent-primary: #3d5a3d; --accent-secondary: #8c6b5d;`
- **Hero gradient**: Modify `.hero` background gradient to match the palette

### 3. Escape markdown for JS embedding

The markdown goes inside a JS template literal. Escape:
- All backticks: `` ` `` → `` \` ``
- All `${` sequences: `${` → `\${`
- All backslashes that precede the above: double them

### 4. Deploy

Write the final HTML to:
```
/var/www/docs.a2a.ing/<slug>.html
```

The slug should be a kebab-case name derived from the content topic (e.g. `math-to-ai-pathway-guide.html`).

Verify deployment:
```bash
curl -s -o /dev/null -w '%{http_code}' https://docs.a2a.ing/<slug>.html
```

Report the public URL to the user:
```
https://docs.a2a.ing/<slug>.html
```

## Design guidelines

The template provides a solid default, but **each page should feel unique**. Vary:

1. **Color palette** — change CSS variables per topic
2. **Hero decorative symbols** — pick 6-8 Unicode symbols relevant to the topic
3. **Hero gradient** — shift the gradient hues to match the palette
4. **Typography** — optionally swap display/body fonts via `{{EXTRA_FONTS}}` and CSS overrides

**Do NOT**:
- Use generic fonts (Inter, Roboto, Arial)
- Use the same color scheme for every report
- Strip tables or code blocks from the markdown — the template renders them beautifully
- Add external JS dependencies beyond the three CDN scripts already in the template (tailwind, marked, dompurify)

## Built-in features (no action needed)

The template automatically provides:
- Scroll progress bar at top
- Sticky sidebar TOC with active-section highlighting (auto-generated from h2/h3)
- Blockquote auto-styling (⚠️→warning amber, 💡→tip green, else→blue)
- Checkbox list rendering
- Responsive layout (sidebar hidden on mobile)
- Print-friendly styles
