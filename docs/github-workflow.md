# GitHub Workflow & Team Rules

**Project:** Workflow Management For MNC
**Stack:** Python + FastAPI + PostgreSQL (Supabase) | ReactJS + TypeScript | Postman | Antigravity IDE | Slack
**Team:** 1 Team Lead + 10 Developers
**Repository model:** One shared repo, many short-lived branches

> **These rules apply to EVERYONE, including the Team Lead.**
> If you are unsure about anything, ask in Slack **before** you act, not after.

---

## Table of Contents

1. [The Big Picture](#1-the-big-picture)
2. [Branches](#2-branches)
3. [Branch Naming](#3-branch-naming)
4. [One-Time Setup](#4-one-time-setup-every-member)
5. [The Task Lifecycle (Issue to Merge)](#5-the-task-lifecycle-issue-to-merge)
6. [Commit Rules](#6-commit-rules)
7. [Pull Request Rules](#7-pull-request-rules)
8. [Code Review Rules](#8-code-review-rules)
9. [Merge Conflicts](#9-merge-conflicts)
10. [Shared Files and Ownership](#10-shared-files-and-ownership)
11. [Database (Supabase) Rules](#11-database-supabase-rules)
12. [Secrets and Security](#12-secrets-and-security)
13. [Working With Antigravity (AI) Rules](#13-working-with-antigravity-ai-rules)
14. [Issues, Labels and Milestones](#14-issues-labels-and-milestones)
15. [Communication (Slack)](#15-communication-slack)
16. [Sprint and Release Process](#16-sprint-and-release-process)
17. [Forbidden Actions](#17-forbidden-actions)
18. [Emergency Procedures](#18-emergency-procedures)
19. [Command Cheat Sheet](#19-command-cheat-sheet)
20. [Final Checklists](#20-final-checklists)

---

## 1. The Big Picture

```
Issue  ->  Branch  ->  Code  ->  Commit  ->  Push  ->  Pull Request  ->  Review  ->  Merge  ->  Clean up
```

| Term | Meaning |
|---|---|
| **Issue** | A written task (what to build or fix) |
| **Branch** | Your private workspace for that one task |
| **Commit** | A saved snapshot of your work |
| **Pull Request (PR)** | A request to add your work to the shared code, after someone checks it |
| **Merge** | Adding the approved work into the shared branch |

**Core principle:** Nobody writes directly into shared branches. All work happens on your own branch and enters the shared code only through a reviewed Pull Request.

---

## 2. Branches

| Branch | Purpose | Direct push? | Lifetime |
|---|---|---|---|
| `main` | Stable, tested, demo/submission-ready code | **Never** (PR only) | Permanent |
| `develop` | Integration branch: all finished work meets here | **Never** (PR only) | Permanent |
| `feature/*`, `bugfix/*`, `docs/*`, ... | One task by one person | Yes, by the owner | Short (1-3 days) |

```
main       <- stable releases only (Team Lead merges from develop)
  ^
develop    <- everyone's finished, reviewed work
  ^
feature/login-api   feature/login-ui   bugfix/token-expiry   ...
```

**Rules:**
- All feature branches are created **from `develop`**, never from `main`.
- All PRs from feature branches target **`develop`**, never `main`.
- Only the Team Lead opens the `develop -> main` release PR.
- There are **no sprint branches** and **no personal branches** (no `smit-branch`). Sprints are tracked with Milestones.

---

## 3. Branch Naming

**Format:** `<type>/<short-feature-description>`

- Lowercase only, words separated by hyphens
- No spaces, no personal names, no special characters
- Name describes **what**, not **who**

| Prefix | Use for | Example |
|---|---|---|
| `feature/` | New functionality | `feature/login-api` |
| `bugfix/` | Fixing a bug found in `develop` | `bugfix/login-validation` |
| `hotfix/` | Urgent fix for `main` (rare) | `hotfix/crash-on-startup` |
| `docs/` | Documentation only | `docs/update-readme` |
| `test/` | Adding or fixing tests | `test/auth-endpoints` |
| `refactor/` | Cleanup with no behaviour change | `refactor/task-service` |
| `chore/` | Config, dependencies, tooling | `chore/add-eslint` |

**Good:** `feature/employee-crud-api`, `feature/login-ui`
**Bad:** `krish-work`, `new_branch`, `Feature/Login`, `final-version`, `test123`

---

## 4. One-Time Setup (Every Member)

Do this once on your computer.

### 4.1 Accept the invitation
You must accept the collaborator invitation (check your email or `https://github.com/<owner>/<repo>/invitations`). **Until you accept, you cannot push.**

### 4.2 Install and configure Git
```bash
git --version                                   # verify it is installed

git config --global user.name "Your Full Name"
git config --global user.email "your-github-email@example.com"
git config --global init.defaultBranch main
git config --global pull.rebase false           # use merge, not rebase
```
> Use the **same email as your GitHub account**, or your commits will not be linked to your profile. Commits are used to verify individual contributions.

### 4.3 Sign in to GitHub
Easiest options: **GitHub Desktop**, or sign in through **Antigravity/VS Code** (Source Control panel). Git Credential Manager will open a browser on your first push. Do not use your account password.

### 4.4 Clone and verify
```bash
git clone https://github.com/<owner>/Workflow-Management-For-MNC.git
cd Workflow-Management-For-MNC
git branch -a          # you should see main, develop and their origin/ versions
git switch develop
git pull origin develop
git status             # should say: nothing to commit, working tree clean
```

### 4.5 Install project dependencies
```bash
# Backend
cd backend
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env            # then fill in your values (never commit .env)

# Frontend
cd ../frontend
npm install
cp .env.example .env
```

### 4.6 Read these files before your first task
1. `README.md`: what we are building
2. `AGENTS.md`: coding and AI rules
3. This document

---

## 5. The Task Lifecycle (Issue to Merge)

Follow these steps **in order, every time**. No exceptions.

### Step 1: Pick your Issue
- Open GitHub > **Issues** and find the one assigned to you (filter by your name).
- Read the description and **acceptance criteria** fully.
- If anything is unclear, **comment on the Issue** and ask before coding.
- **No Issue = no coding.** If you find something that needs doing, tell the Team Lead so an Issue is created.
- Work on **one Issue at a time**.

### Step 2: Update `develop`
```bash
git switch develop
git pull origin develop
```
Always start from the newest code.

### Step 3: Create your branch
```bash
git switch -c feature/login-api
git branch          # confirm the * is on your new branch
```

### Step 4: Do the work
- Edit only files that belong to your task and module.
- Test locally as you go (Postman for endpoints, browser for UI).
- Commit small and often (see [Section 6](#6-commit-rules)).
- **At least once per day**, bring in the latest `develop`:
  ```bash
  git fetch origin
  git merge origin/develop
  ```

### Step 5: Check before you commit
```bash
git status      # which files changed? Only YOUR files should appear
git diff        # read every changed line
```

### Step 6: Commit and push
```bash
git add path/to/your/files
git commit -m "feat: add login endpoint"
git push -u origin feature/login-api     # first push of this branch
git push                                 # later pushes
```

### Step 7: Sync again, then open a PR
Before opening the PR:
```bash
git fetch origin
git merge origin/develop
# fix conflicts if any, run the app, make sure it still works
git push
```
Then open the Pull Request (see [Section 7](#7-pull-request-rules)).

### Step 8: Respond to the review
- Fix requested changes **on the same branch** (do not open a new PR).
- Commit and `git push`; the PR updates automatically.
- Reply to each comment, then mark it resolved once fixed.

### Step 9: Merge
After approval and all conversations resolved, click **Squash and merge**, then **Delete branch**.

### Step 10: Clean up locally
```bash
git switch develop
git pull origin develop
git branch -d feature/login-api
```
Now pick your next Issue and repeat from Step 1.

---

## 6. Commit Rules

### 6.1 Format
```
<type>: <short description in lowercase, imperative mood>
```

| Type | Use for | Example |
|---|---|---|
| `feat` | New feature | `feat: add employee registration endpoint` |
| `fix` | Bug fix | `fix: correct password length validation` |
| `docs` | Documentation only | `docs: update setup steps in README` |
| `test` | Tests | `test: add login endpoint tests` |
| `refactor` | Restructure, same behaviour | `refactor: split auth service into helpers` |
| `style` | Formatting only | `style: format login component` |
| `chore` | Config, dependencies, tooling | `chore: add axios dependency` |
| `merge` | Conflict resolution | `merge: resolve conflict with develop` |
| `wip` | Work in progress (feature branches only) | `wip: login form in progress` |

### 6.2 Requirements
- Keep the first line under ~72 characters
- Use "add", "fix", "update" (not "added", "fixed")
- No full stop at the end
- One logical change per commit
- Reference the Issue where useful: `fix: resolve token expiry bug (#12)`

| Bad | Good |
|---|---|
| `update` | `feat: add leave request form` |
| `fixed stuff` | `fix: correct salary calculation` |
| `final final v2` | `refactor: simplify notification service` |
| `asdfgh` | `docs: add API endpoints to README` |

### 6.3 What must NEVER be committed
- `.env` files, passwords, API keys, tokens, Supabase service keys
- `node_modules/`, `venv/`, `__pycache__/`, `build/`, `dist/`
- IDE settings (`.idea/`, `.vscode/`) unless the Team Lead agrees
- Large files, database dumps, videos, zip files
- Commented-out old code and random test files

---

## 7. Pull Request Rules

### 7.1 Opening a PR
1. Push your branch.
2. On GitHub click **Compare & pull request**.
3. **Check the top of the page: `base: develop` <- `compare: your-branch`.** Base must NOT be `main`.
4. Title follows commit style: `feat: add login API endpoint`.
5. **Fill in every section of the template.** Do not leave it blank.
6. Write `Closes #<issue-number>` so the Issue closes automatically.
7. Add **Reviewers** (your assigned reviewer + Team Lead), yourself as **Assignee**, and **Labels** and **Milestone**.
8. Click **Create pull request**. If you are not finished, choose **Draft pull request**.

### 7.2 PR requirements (all must be true)
- [ ] Branch created from latest `develop` and synced again before the PR
- [ ] No merge conflicts
- [ ] App runs: backend starts, frontend builds (`npm run build`)
- [ ] You tested your own work (Postman screenshots for APIs, UI screenshots for frontend)
- [ ] One PR = one task; no unrelated changes
- [ ] No secrets or junk files
- [ ] Docs updated if setup or behaviour changed
- [ ] Linked to an Issue

### 7.3 Size limit
Keep PRs small: **ideally under ~300 changed lines**. If your PR is huge, split it into smaller PRs. Large PRs are hard to review and cause conflicts.

### 7.4 Merge method

| PR type | Merge button |
|---|---|
| feature / bugfix / docs -> `develop` | **Squash and merge** |
| `develop` -> `main` (Team Lead only) | **Create a merge commit** |
| Any PR | **Never** "Rebase and merge" |

### 7.5 Approvals

| PR type | Approvals needed | Who merges |
|---|---|---|
| feature / bugfix -> `develop` | 1 (2 for big or risky changes) | PR author, after approval |
| `develop` -> `main` | 2 (Team Lead + 1 other) | Team Lead |
| Small docs-only fix | 1 | PR author |

- **You can never approve your own PR.**
- **Never merge without approval**, even if you have the ability to.

---

## 8. Code Review Rules

### 8.1 For reviewers
- Review within **24 hours** of being assigned.
- Open the PR > **Files changed** and read line by line.
- Comment on a specific line by clicking the **+** beside it.
- Then choose **Review changes**: **Comment**, **Approve**, or **Request changes**.
- **Never approve without reading.** Approving means you checked it.
- Be kind and specific: *"Could we rename `x` to `user_count`?"* not *"bad naming"*.

### 8.2 Reviewer checklist
- [ ] Does it do what the Issue and acceptance criteria say?
- [ ] Code is readable (clear names, comments where needed)?
- [ ] Input validation and error handling present?
- [ ] No secrets, `.env`, or hardcoded URLs/keys?
- [ ] No unrelated changes or files from other modules?
- [ ] Follows `AGENTS.md` naming and structure?
- [ ] No unnecessary new dependencies?
- [ ] Endpoints tested (Postman evidence) and UI checked?
- [ ] No leftover debug prints / `console.log` / commented-out code?
- [ ] Docs or types updated where needed?

### 8.3 Extra checks for AI-generated code
- [ ] Author understands the code (ask them if unsure)
- [ ] No files changed outside the author's module
- [ ] No quietly added dependencies
- [ ] No whole-file reformatting (huge diffs)
- [ ] No duplicate logic that already exists elsewhere
- [ ] No fake placeholder data or TODO stubs left behind

### 8.4 For authors
- Respond to comments within **24 hours**.
- Do not take feedback personally; review is normal for everyone.
- Fix on the same branch, push, then resolve the conversation.

### 8.5 Reviewer rotation

| Author | Primary reviewer | Backup |
|---|---|---|
| Member 2 | Member 3 | Team Lead |
| Member 3 | Member 4 | Team Lead |
| Member 4 | Member 5 | Team Lead |
| Member 5 | Member 6 | Team Lead |
| Member 6 | Member 7 | Team Lead |
| Member 7 | Member 8 | Team Lead |
| Member 8 | Member 9 | Team Lead |
| Member 9 | Member 10 | Team Lead |
| Member 10 | Member 11 | Team Lead |
| Member 11 | Member 2 | Team Lead |
| Team Lead | Member 2 | Member 3 |

*(Adjust names to match your actual team.)*

---

## 9. Merge Conflicts

A conflict happens when two people edit the **same lines** of the same file. It is normal, not a disaster.

### 9.1 Prevention (most important)
- Pull `develop` before starting and at least **once a day**.
- Keep branches **short-lived (1-3 days)** and PRs small.
- Stay inside your own module/folder.
- **Never reformat or "clean up" files you do not own.** Never auto-format the whole project.
- Announce in Slack before touching shared files ([Section 10](#10-shared-files-and-ownership)).
- Open PRs early and often instead of waiting for "perfect".

### 9.2 Resolving a conflict
```bash
git switch feature/your-branch
git fetch origin
git merge origin/develop
# Git reports: CONFLICT (content): Merge conflict in <file>

git status                 # see "both modified" files
```
Open the file. You will see:
```
<<<<<<< HEAD
your version
=======
their version (from develop)
>>>>>>> origin/develop
```
1. Decide the final code: keep yours, theirs, or combine. **Ask the other author if unsure.**
2. Delete all three marker lines (`<<<<<<<`, `=======`, `>>>>>>>`).
3. Run the app and make sure it works.
4. Finish:
   ```bash
   git add <file>
   git commit -m "merge: resolve conflict with develop in <file>"
   git push
   ```

**Bail out safely** if you get confused mid-merge:
```bash
git merge --abort
```

Never leave conflict markers in a file, and never resolve a conflict by blindly accepting your version.

---

## 10. Shared Files and Ownership

Some files are touched by many people and cause the most conflicts.

| File / Area | Owner | Rule |
|---|---|---|
| `backend/requirements.txt` | Team Lead | Request additions via Issue or Slack; do not edit directly |
| `frontend/package.json`, lock file | Team Lead | Same as above |
| `backend/app/main.py` (router registration) | Team Lead | Small PR, merged quickly |
| Frontend routing / `App.tsx` | Team Lead | Announce in Slack first |
| Database schema / migrations | Database owner | See [Section 11](#11-database-supabase-rules) |
| `.github/`, `AGENTS.md`, `.gitignore` | Team Lead | Changes via PR only, reviewed by Team Lead |
| `README.md`, `docs/` | QA/Docs owner | Anyone can propose via PR |

**Procedure for editing a shared file:**
1. Announce in Slack: *"Editing `main.py` to register the auth router, PR in 15 min."*
2. Make the **smallest possible** change on a short branch.
3. Open a tiny PR and get it reviewed and merged quickly.
4. Everyone else pulls `develop` to receive it.

**Module ownership:** each member works in their own module's folders (for example `backend/app/routes/auth.py`). Do not modify another member's module. If you find a bug in it, open an Issue or message the owner.

---

## 11. Database (Supabase) Rules

We share one Supabase project. Uncontrolled changes here can break everyone's work.

1. **No one edits tables directly in the Supabase dashboard** without telling the Team Lead and the database owner.
2. **Schema changes go through the repo.** Write the SQL in `database/migrations/` (numbered, e.g. `003_add_phone_to_users.sql`) and submit it in a PR.
3. Migrations are applied **only after the PR is merged**, by the database owner.
4. Never delete or rename existing tables/columns without team agreement.
5. Never use the Supabase **service role key** in frontend code or commit it anywhere.
6. Use test data only. Do not delete or overwrite other members' data.
7. Use the **anon key** in the frontend and keep Row Level Security policies in mind.
8. Keep `database/schema.sql` updated when the structure changes.

---

## 12. Secrets and Security

1. **Never commit** passwords, API keys, tokens, Supabase keys, or `.env` files.
2. Only `.env.example` (with dummy values) is committed.
3. Read secrets from environment variables, never hardcode them.
4. Share real credentials privately and temporarily (not in public Slack channels or PR comments).
5. **If you commit a secret by accident:**
   - Tell the Team Lead **immediately**.
   - The secret must be **revoked and replaced**. Deleting the file in a new commit does **not** remove it from Git history.
6. Use parameterized queries / the Supabase client; never build SQL by string concatenation with user input.
7. Validate all user input on the backend (Pydantic) and on the frontend.
8. Do not log passwords, tokens, or personal data.

---

## 13. Working With Antigravity (AI) Rules

AI helps you write code faster, but **you are responsible for every line you commit**.

### 13.1 Setup
- Open the **repository root folder** in Antigravity so it loads `AGENTS.md`.
- Use the same runtime versions as the team (Python, Node).
- Do not edit `AGENTS.md` yourself; propose changes through a PR or to the Team Lead.

### 13.2 How to prompt
1. **One task per prompt.** Not "build the whole module".
2. **Give context:** *"Working on Issue #5, Login API, in `backend/app/routes/auth.py`."*
3. **State the boundaries:** *"Do not modify any other module, `requirements.txt`, or shared config."*
4. **Paste the acceptance criteria** from the Issue.
5. Pull `develop` first so the AI sees existing code and reuses it instead of duplicating.
6. Ask it to follow `AGENTS.md` naming and structure.

### 13.3 Before committing AI code
- Read and understand every changed file. Run `git status` and `git diff`.
- Revert any file you did not intend to change: `git restore <file>`.
- Check that no new dependency, secret, or reformatted file slipped in.
- Run and test it yourself (Postman / browser). "The AI wrote it" is not a test.
- Delete dead code, placeholder data, and unused imports.

### 13.4 Never
- Paste secrets or real keys into AI prompts.
- Let the AI run destructive Git commands (`reset --hard`, `push --force`, `clean -fd`, `rebase`).
- Let the AI commit or push without you reviewing the diff first.
- Accept output you cannot explain during review.

---

## 14. Issues, Labels and Milestones

### 14.1 Who creates Issues
- **Team Lead** creates and assigns Issues for planned work.
- Members who find a bug or need something tell the Team Lead in Slack, and an Issue is created. (Members may create Issues themselves later, once the Team Lead says so.)

### 14.2 Good Issue format
```
Title: Build login API endpoint

Description:
What needs to be built and why.

Acceptance criteria:
- [ ] POST /api/v1/auth/login accepts email and password
- [ ] Returns a JWT on success
- [ ] Returns a clear error on invalid credentials
- [ ] Input validated; tested in Postman

Assignee: Member 2
Labels: feature, backend
Milestone: Sprint 1
```

### 14.3 Labels
`feature`, `bug`, `documentation`, `frontend`, `backend`, `database`, `testing`, `urgent`, `help wanted`, `blocked`

### 14.4 Milestones (Sprints)
Sprints are **Milestones**, not branches.

| Milestone | Goal |
|---|---|
| Sprint 1 | Repo setup, database, authentication |
| Sprint 2 | Core modules |
| Sprint 3 | Advanced features |
| Final | Testing, documentation, demo |

### 14.5 Board columns
`Backlog -> Todo -> In Progress -> In Review -> Done`
Move your card when your status changes (or let GitHub automation do it).

### 14.6 Issue size
If an Issue takes more than **2-3 days**, ask for it to be split.

---

## 15. Communication (Slack)

- **Announce** in Slack before editing shared files or merging large PRs.
- Post in the PR channel when your PR is ready: `PR #7 ready for review: feat: add login API`.
- Post a short **daily update** (every working day or every other day):
  1. What I did
  2. What I will do next
  3. What is blocking me
- **Ask early** when blocked; do not stay stuck for more than ~1 hour.
- Keep code discussion in **PR/Issue comments** so the history lives on GitHub.
- Never post secrets in Slack channels.
- Answer direct questions and review requests within **24 hours**.

---

## 16. Sprint and Release Process

**Each sprint:**
1. **Planning:** Team Lead creates Issues, assigns them to the sprint Milestone.
2. **Development:** everyone follows [Section 5](#5-the-task-lifecycle-issue-to-merge).
3. **Check-ins:** daily updates in Slack.
4. **Sprint end:** Team Lead opens PR `develop -> main`, gets 2 approvals, tests the combined build, and merges with **Create a merge commit**.
5. **Retrospective:** quick discussion on what to improve.

**Freeze period:** before major demos or submissions, only bug fixes are merged into `develop` (Team Lead announces the start and end).

**Final release checklist (Team Lead):**
- [ ] `develop` builds and runs from a fresh clone
- [ ] README setup steps verified
- [ ] No secrets or junk files in the repo
- [ ] All Issues for the milestone closed or moved
- [ ] `develop -> main` PR approved and merged
- [ ] Release tagged (e.g. `v1.0`)

---

## 17. Forbidden Actions

| Never do this | Why |
|---|---|
| Push directly to `main` or `develop` | Bypasses review; can break everyone |
| `git push --force` (or `-f`) | Overwrites teammates' history |
| `git reset --hard` without asking | Destroys uncommitted work |
| `git rebase` | Rewrites history; confusing for beginners |
| `git clean -fd` | Permanently deletes files |
| Merge your own PR without an approval | Defeats the review process |
| Approve a PR you have not read | Bugs slip through |
| Commit `.env`, keys, or passwords | Security leak |
| Commit `node_modules/`, `venv/`, build output | Bloats the repo |
| Edit another member's module without telling them | Causes conflicts and confusion |
| Create mega-branches with many unrelated tasks | Unreviewable and conflict-prone |
| Reformat files you do not own | Creates huge diffs and conflicts |
| Change Supabase tables directly without telling the team | Breaks others' work |
| Merge test/practice PRs into `develop` | Pollutes shared code (close them instead) |
| Commit with someone else's name/email | Breaks contribution tracking |

> **Rule of thumb:** if a command contains `--hard`, `--force`, `clean`, or `rebase`, **stop and ask the Team Lead first.**

---

## 18. Emergency Procedures

| Situation | What to do |
|---|---|
| **Push rejected** ("fetch first") | `git pull origin <your-branch>`, resolve conflicts, `git push`. **Do not force push.** |
| **"Repository not found" / permission denied** | Accept the invitation; check `git remote -v`; sign in via GitHub Desktop/VS Code |
| **Committed to `develop`/`main` locally (not pushed)** | `git switch -c feature/my-work` (keeps your commit), then tell the Team Lead before resetting the old branch |
| **Pushed to `develop`/`main` by mistake** | Tell the Team Lead immediately; they will `git revert` it |
| **Committed a secret** | Tell the Team Lead now; revoke and change the secret |
| **Forgot to pull before coding (no commit yet)** | `git stash push -m "my work"`, `git pull origin develop`, `git stash pop` |
| **Uncommitted changes block switching branches** | `git stash push -m "temp"`, switch, later `git stash pop` |
| **Deleted a file by mistake (uncommitted)** | `git restore path/to/file` |
| **Wrong commit message (not pushed)** | `git commit --amend -m "new message"` |
| **Need to undo last commit (not pushed)** | `git reset --soft HEAD~1` (keeps your changes) |
| **Need to undo a pushed commit** | `git revert <commit-hash>` (never reset or force push) |
| **Merge got confusing** | `git merge --abort`, then ask for help |
| **Totally stuck / panicking** | **Stop.** Do not run random commands. Copy your project folder as a backup, run `git status`, and ask the Team Lead in Slack |

---

## 19. Command Cheat Sheet

**Start a task**
```bash
git switch develop
git pull origin develop
git switch -c feature/my-task
```

**While working**
```bash
git status
git diff
git add path/to/files
git commit -m "feat: what I did"
git push -u origin feature/my-task     # first push
git push                               # later pushes
```

**Sync with the latest develop**
```bash
git fetch origin
git merge origin/develop
```

**After your PR is merged**
```bash
git switch develop
git pull origin develop
git branch -d feature/my-task
```

**Useful checks**
```bash
git branch                 # which branch am I on?
git branch -a              # all branches
git log --oneline -10      # recent commits
git remote -v              # which remote am I using?
git stash push -m "wip"    # shelve uncommitted work
git stash pop              # bring it back
```

---

## 20. Final Checklists

### Before you start a task
- [ ] I have an assigned Issue and understand the acceptance criteria
- [ ] I pulled the latest `develop`
- [ ] I created a correctly named branch from `develop`
- [ ] `git branch` shows I am on my new branch

### Before you open a PR
- [ ] I merged the latest `develop` into my branch and fixed conflicts
- [ ] Backend runs and endpoints tested in Postman; frontend builds
- [ ] `git status` shows only files related to my task
- [ ] No secrets, `.env`, `node_modules`, `venv`, or debug code
- [ ] I read and understand all AI-generated code
- [ ] PR base is `develop`, template filled, `Closes #N` added, reviewer assigned

### Before you approve a PR (reviewer)
- [ ] I read every changed file
- [ ] Checklist in [Section 8.2](#82-reviewer-checklist) is satisfied
- [ ] I am not the author

### The 10 Golden Rules
1. Never push to `main` or `develop`; always use a Pull Request.
2. No Issue, no coding. One task = one Issue = one branch = one PR.
3. Pull `develop` before you start and before you open a PR.
4. Stay inside your own module; announce before touching shared files.
5. Use clear commit messages (`feat:`, `fix:`, `docs:` ...).
6. No secrets, `.env`, or generated files in commits.
7. Test your own work before asking for a review.
8. Review within 24 hours; never approve without reading.
9. No `--force`, `--hard`, `clean`, or `rebase` without asking the Team Lead.
10. When in doubt, stop and ask in Slack.

---

*Document owner: Team Lead. To suggest improvements, open a PR with the `docs:` prefix.*
