# Story Sizing Guide

## The Golden Rule

**Each story must be completable in ONE Ralph iteration (one context window).**

Ralph spawns a fresh AI instance per iteration with no memory of previous work. If a story is too big, the AI runs out of context before finishing and produces broken code.

---

## Rule of Thumb

> If you cannot describe the change in 2-3 sentences, it is too big.

---

## Right-Sized Stories

These fit comfortably in one iteration:

| Story | Why it works |
|-------|-------------|
| Add a database column and migration | Single schema change, one file |
| Add a UI component to an existing page | Focused UI work, clear scope |
| Update a server action with new logic | One function change |
| Add a filter dropdown to a list | Small UI + query change |
| Create a new API endpoint | One route, one handler |
| Add form validation rules | Focused validation logic |
| Write unit tests for a service | Testing one module |

---

## Too-Big Stories (Split These)

| Too Big | Split Into |
|---------|-----------|
| "Build the entire dashboard" | Schema, queries, layout, cards, filters, pagination |
| "Add authentication" | Schema, middleware, login UI, session handling, logout |
| "Refactor the API" | One story per endpoint or pattern |
| "Add user notification system" | Table, service, bell icon, dropdown, mark-read, preferences |
| "Build settings page" | Profile section, password change, preferences, billing |

---

## Splitting Strategy

### 1. Vertical Slicing (by layer)
```
Feature: User Profile
├── US-001: Add profile fields to database (schema)
├── US-002: Create profile API endpoints (backend)
├── US-003: Build profile display page (frontend)
└── US-004: Add profile edit form (frontend)
```

### 2. Horizontal Slicing (by sub-feature)
```
Feature: Search
├── US-001: Basic text search
├── US-002: Search filters
├── US-003: Search results pagination
└── US-004: Search suggestions/autocomplete
```

### 3. Incremental Enhancement
```
Feature: Data Table
├── US-001: Basic table with columns
├── US-002: Sorting by column
├── US-003: Pagination
├── US-004: Column visibility toggle
└── US-005: Export to CSV
```

---

## Dependency Ordering

Stories execute in priority order. Earlier stories must NOT depend on later ones.

### Correct Order:
1. Schema/database changes (migrations)
2. Server actions / backend logic
3. UI components that use the backend
4. Dashboard/summary views that aggregate data
5. Polish (animations, edge cases, error states)

### Wrong Order:
1. ❌ UI component (depends on schema that doesn't exist yet)
2. ❌ Schema change (should be first)

---

## Acceptance Criteria Quality

### Verifiable (Good) ✅
- "Add `status` column to tasks table with default 'pending'"
- "Filter dropdown has options: All, Active, Completed"
- "Clicking delete shows confirmation dialog"
- "API returns 404 for non-existent resources"
- "Typecheck passes"

### Vague (Bad) ❌
- "Works correctly"
- "User can do X easily"
- "Good UX"
- "Handles edge cases"
- "Performant"

### Mandatory Criteria
Every story must include:
```
"Typecheck passes"
```

UI stories must also include:
```
"Verify in browser"
```

Testable logic should include:
```
"Tests pass"
```

---

## Sizing Checklist

Before finalizing stories:

- [ ] Can each story be described in 2-3 sentences?
- [ ] Does each story touch at most 3-5 files?
- [ ] Are there no circular dependencies between stories?
- [ ] Is the dependency order correct (schema → backend → UI)?
- [ ] Are all acceptance criteria verifiable?
- [ ] Does every story include "Typecheck passes"?
- [ ] Do UI stories include "Verify in browser"?
