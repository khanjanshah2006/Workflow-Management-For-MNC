---
name: commit-and-story-tracing
description: Use whenever generating a git commit message or opening a pull request in the Workflow Management System for MNCs repo. Ties every commit back to a User Story ID so progress across all 11 group members stays traceable to the backlog and sprint plan.
---

# Workflow Management System for MNCs Commit & PR Conventions

## Commit message format

```
US-<id>: <short imperative summary>

<optional body: what changed and why, not a restatement of the diff>
```

Examples:
- `US-09: add task creation and assignment endpoint`
- `US-17: surface leave balance + deadlines in TL approval panel`

If a commit touches setup/tooling with no single story (e.g. initial FastAPI scaffold), use `SETUP:` instead of a US-ID — don't force-fit one.

## Branch naming

`feature/us-<id>-<short-slug>` (e.g. `feature/us-12-review-task`). One branch per story where practical; a branch spanning multiple stories should name the range (`feature/us-43-44-account-role-admin`).

## PR description template

```markdown
## Story
US-<id> — <title, copied from the backlog>

## What this implements
<1-3 lines>

## Checklist
- [ ] RBAC check present (see rbac-enforcement skill)
- [ ] Audit log call present, if state-changing (see api-endpoint-pattern skill)
- [ ] Matches file structure (see project-structure skill)
- [ ] Acceptance criteria from the backlog are all met
```

## Why this matters for an 11-person group specifically

With this many contributors, `git log --grep "US-"` becomes the fastest way to answer "who implemented this, and does it match what the backlog says it should do" — treat the US-ID as mandatory, not a nice-to-have, since the alternative is manually cross-referencing commits to the 50-story backlog by hand.
