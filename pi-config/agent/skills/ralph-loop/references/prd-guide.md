# PRD Writing Guide

## Overview

A Product Requirements Document (PRD) defines what to build, why, and how to verify it's done. This guide produces PRDs optimized for autonomous AI execution via the Ralph loop.

---

## Step 1: Clarifying Questions

Ask 3-5 essential questions with lettered options so the user can respond quickly (e.g., "1A, 2C, 3B"):

```
1. What is the primary goal?
   A. Improve user onboarding
   B. Increase retention
   C. Reduce support burden
   D. Other: [specify]

2. Who is the target user?
   A. New users only
   B. Existing users
   C. All users
   D. Admin users

3. What is the scope?
   A. Minimal viable version
   B. Full-featured
   C. Backend/API only
   D. UI only
```

Focus on:
- **Problem/Goal**: What problem does this solve?
- **Core Functionality**: What are the key actions?
- **Scope/Boundaries**: What should it NOT do?
- **Success Criteria**: How do we know it's done?

---

## Step 2: PRD Structure

### 1. Introduction/Overview
Brief description of the feature and problem it solves.

### 2. Goals
Specific, measurable objectives (bullet list).

### 3. User Stories
Each story needs:
- **Title**: Short descriptive name
- **Description**: "As a [user], I want [feature] so that [benefit]"
- **Acceptance Criteria**: Verifiable checklist

**Format:**
```markdown
### US-001: [Title]
**Description:** As a [user], I want [feature] so that [benefit].

**Acceptance Criteria:**
- [ ] Specific verifiable criterion
- [ ] Another criterion
- [ ] Typecheck/lint passes
- [ ] **[UI stories only]** Verify in browser
```

**Rules:**
- Each story must be completable in one context window
- Acceptance criteria must be verifiable ("Button shows dialog" not "Works correctly")
- UI stories always include browser verification

### 4. Functional Requirements
Numbered list: "FR-1: The system must allow users to..."

### 5. Non-Goals (Out of Scope)
What this feature will NOT include. Critical for scope management.

### 6. Technical Considerations (Optional)
Known constraints, dependencies, integration points, performance requirements.

### 7. Success Metrics
Measurable outcomes: "Reduce time to complete X by 50%"

### 8. Open Questions
Remaining areas needing clarification.

---

## Writing for AI Agents

The PRD reader may be an AI agent with no context. Therefore:
- Be explicit and unambiguous
- Avoid jargon or explain it
- Provide enough detail for core logic
- Number requirements for easy reference
- Use concrete examples

---

## Output

- **Format**: Markdown (`.md`)
- **Location**: `tasks/`
- **Filename**: `prd-[feature-name].md` (kebab-case)

---

## Example

```markdown
# PRD: Task Priority System

## Introduction
Add priority levels to tasks so users can focus on what matters most.

## Goals
- Allow assigning priority (high/medium/low) to any task
- Provide clear visual differentiation
- Enable filtering by priority
- Default new tasks to medium priority

## User Stories

### US-001: Add priority field to database
**Description:** As a developer, I need to store task priority in the database.
**Acceptance Criteria:**
- [ ] Add priority column: 'high' | 'medium' | 'low' (default 'medium')
- [ ] Migration runs successfully
- [ ] Typecheck passes

### US-002: Display priority badge on task cards
**Description:** As a user, I want to see priority at a glance.
**Acceptance Criteria:**
- [ ] Colored badge (red=high, yellow=medium, gray=low)
- [ ] Visible without interaction
- [ ] Typecheck passes
- [ ] Verify in browser

### US-003: Add priority selector to edit modal
**Description:** As a user, I want to change priority when editing.
**Acceptance Criteria:**
- [ ] Priority dropdown in edit modal
- [ ] Shows current priority selected
- [ ] Saves immediately
- [ ] Typecheck passes
- [ ] Verify in browser

### US-004: Filter tasks by priority
**Description:** As a user, I want to filter by priority.
**Acceptance Criteria:**
- [ ] Filter dropdown: All | High | Medium | Low
- [ ] Filter persists in URL params
- [ ] Empty state message
- [ ] Typecheck passes
- [ ] Verify in browser

## Functional Requirements
- FR-1: Add `priority` field ('high' | 'medium' | 'low', default 'medium')
- FR-2: Display colored priority badge on task cards
- FR-3: Priority selector in edit modal
- FR-4: Priority filter dropdown in list header

## Non-Goals
- No priority-based notifications
- No automatic priority assignment
- No priority inheritance for subtasks

## Success Metrics
- Priority changeable in under 2 clicks
- High-priority tasks immediately visible
- No performance regression
```

---

## Checklist

- [ ] Asked clarifying questions with lettered options
- [ ] Incorporated user's answers
- [ ] Stories are small and specific (one iteration each)
- [ ] Stories ordered by dependency
- [ ] Functional requirements numbered and unambiguous
- [ ] Non-goals section defines boundaries
- [ ] Saved to `tasks/prd-[feature-name].md`
