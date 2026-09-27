# Workflow Management For MNC — User Stories



### US-01 — User Login

**As an** Employee, **I want to** log in using my unique credentials, **so that** I can securely access WorkSphere according to my role.

**Acceptance Criteria**

- Users can enter valid login credentials.
- The system verifies the credentials.
- Successful login creates an authenticated session.
- Invalid credentials are rejected with an appropriate error.
- Users are redirected to the dashboard according to their role.
- Passwords must not be stored in plain text.

**Traceability:** FR-E01, NFR-S04
**Priority:** High

---

### US-02 — Role-Based Access

**As a** System Administrator, **I want to** control access according to user roles, **so that** users can access only the functions and data permitted to them.

**Acceptance Criteria**

- Each user has an assigned role.
- The system identifies the user's role after authentication.
- Employees cannot access HR/Admin functions.
- Team Leads access only permitted team information.
- PMs access permitted project information.
- HR accesses HR functions.
- IT Support accesses support functions.
- System Administrator manages system-level permissions.
- Unauthorized API requests are rejected.

**Traceability:** NFR-S03, NFR-S04, FR-E01
**Priority:** High

---

### US-03 — Employee Profile

**As an** Employee, **I want to** view and update my permitted profile information, **so that** my organizational information remains accurate.

**Acceptance Criteria**

- Employees can view their profile.
- Editable fields are clearly identified.
- Employees cannot modify restricted organizational information.
- Changes are validated before being saved.
- Updated information is reflected in the system.

**Traceability:** FR-E02, NFR-DI03
**Priority:** Medium

---

### US-04 — Employee Records

**As an** HR Manager, **I want to** manage employee records, **so that** the organization has accurate employee information.

**Acceptance Criteria**

- HR can create employee records.
- HR can update employee records.
- HR can deactivate an employee when required.
- Employee records contain required organizational information.
- Unauthorized users cannot modify HR records.

**Traceability:** FR-HR01, NFR-HR01, NFR-HR03
**Priority:** High

---

### US-05 — Department & Team Management

**As an** HR Manager, **I want to** manage departments, teams and team leads, **so that** the organization's structure is correctly represented.

**Acceptance Criteria**

- HR can create/update departments.
- HR can create/update teams.
- HR can assign a team lead.
- Employees can be associated with appropriate teams.
- Invalid organizational relationships are rejected.

**Traceability:** FR-HR02, FR-HR03, FR-HR04, NFR-HR03
**Priority:** High

---

### US-06 — Create Project

**As a** Project Manager, **I want to** create a project with its basic information, **so that** the project can be managed within WorkSphere.

**Acceptance Criteria**

- PM can enter project name and description.
- PM can specify start and end dates.
- System validates the project information.
- A unique project record is created.
- Project initially receives an appropriate status.

**Traceability:** FR-PM01, NFR-DI02
**Priority:** High

---

### US-07 — Manage Project Team

**As a** Project Manager, **I want to** add or remove authorized employees and Team Leads from a project, **so that** the correct people are assigned to the project.

**Acceptance Criteria**

- PM can view eligible employees.
- PM can add authorized employees.
- PM can remove project members.
- Inactive employees cannot be assigned.
- Unauthorized users cannot modify project membership.

**Traceability:** FR-PM03, NFR-DI02, NFR-S04
**Priority:** High

---

### US-08 — Project Milestones

**As a** Project Manager, **I want to** create project milestones and target dates, **so that** project progress can be tracked against planned goals.

**Acceptance Criteria**

- PM can create milestones.
- Each milestone has a target date.
- PM can update milestone information.
- Completed and pending milestones can be distinguished.
- Milestone progress is visible in the project view.

**Traceability:** FR-PM04, FR-PM05
**Priority:** High

---

### US-09 — Create and Assign Task

**As a** Team Lead, **I want to** create and assign tasks to team members, **so that** project work is distributed among employees.

**Acceptance Criteria**

- Team Lead can create a task.
- Task contains description/details.
- Team Lead can assign it to an eligible employee.
- Team Lead can specify priority.
- Team Lead can specify a deadline.
- Assigned employee receives a notification.

**Traceability:** FR-TL03, FR-TL04, FR-E03, FR-E10
**Priority:** Critical

---

### US-10 — Update Task Progress

**As an** Employee, **I want to** update my task progress, **so that** my Team Lead and Project Manager can monitor the work.

**Acceptance Criteria**

- Employee can open assigned tasks.
- Employee can update task progress/status.
- System records the update.
- Team Lead can see the updated progress.
- Project-level progress reflects relevant task updates.

**Traceability:** FR-E03, FR-E05, FR-TL10, NFR-P02
**Priority:** Critical

---

### US-11 — Submit Completed Task

**As an** Employee, **I want to** submit completed work with comments or files, **so that** my Team Lead can review my work.

**Acceptance Criteria**

- Employee can mark work as ready for review.
- Employee can add comments.
- Employee can attach permitted files.
- Submission is recorded with user and timestamp.
- Team Lead receives a review notification.

**Traceability:** FR-E06, FR-E10, NFR-AU01
**Priority:** High

---

### US-12 — Review Task

**As a** Team Lead, **I want to** review submitted tasks, **so that** I can approve completed work or request corrections.

**Acceptance Criteria**

- Team Lead can view submitted tasks.
- Team Lead can approve a task.
- Team Lead can reject/return a task.
- Rejection requires a reason.
- Employee receives the review result.
- Review action is recorded with user and timestamp.

**Traceability:** FR-TL06, FR-TL07, FR-TL08, FR-E07, NFR-AU01
**Priority:** Critical

---

### US-13 — Revise and Resubmit Task

**As an** Employee, **I want to** view the reason for a rejected task and resubmit the corrected work, **so that** I can complete the task successfully.

**Acceptance Criteria**

- Employee can see rejection feedback.
- Employee can modify the work.
- Employee can resubmit it.
- Task returns to the review state.
- Team Lead receives a notification.

**Traceability:** FR-E07, FR-E08
**Priority:** High

---

### US-14 — Reassign Task

**As a** Team Lead, **I want to** reassign a task to another eligible team member, **so that** work can continue when the original assignee cannot complete it.

**Acceptance Criteria**

- Team Lead can select another eligible employee.
- System records the reassignment.
- Previous and new assignees are identifiable.
- New assignee receives a notification.
- Reassignment is recorded in the task history.

**Traceability:** FR-TL05, FR-PM08, NFR-AU01
**Priority:** High

---

### US-15 — Monitor Overdue Work

**As a** Team Lead, **I want to** identify overdue and at-risk tasks, **so that** I can take corrective action before project deadlines are affected.

**Acceptance Criteria**

- System identifies tasks whose deadlines have passed.
- Overdue tasks are clearly indicated.
- Team Lead can filter overdue tasks.
- Relevant notifications are generated.
- Team Lead can reassign or escalate work where appropriate.

**Traceability:** FR-TL09, FR-TL11, FR-PM06
**Priority:** High

---

### US-16 — Submit Leave Request

**As an** Employee, **I want to** submit a leave request, **so that** my leave can be formally recorded and reviewed.

**Acceptance Criteria**

- Employee can select leave dates.
- Employee can select an applicable leave type.
- System checks available leave balance.
- Request is submitted to the appropriate authority.
- Employee can view request status.

**Traceability:** FR-E12, FR-HR05
**Priority:** High

---

### US-17 — Check Leave Conflicts

**As a** Team Lead, **I want to** see relevant task deadlines and leave information before handling a leave request, **so that** project work can be considered during leave decisions.

**Acceptance Criteria**

- Team Lead can view the employee's relevant leave information.
- Relevant upcoming deadlines are displayed.
- Potential task/deadline conflicts are highlighted.
- Team Lead can review the request with this context.

**Traceability:** FR-TL12
**Priority:** High

---

### US-18 — Manage Leave Policies

**As an** HR Manager, **I want to** manage region-specific leave policies, **so that** leave requests follow the applicable organizational rules.

**Acceptance Criteria**

- HR can define leave types.
- HR can define applicable leave rules.
- Policies can be associated with the relevant region/office.
- Leave requests are evaluated against applicable policies.
- Unauthorized users cannot modify policies.

**Traceability:** FR-HR06, FR-HR05, NFR-HR01
**Priority:** High

---

### US-19 — Task and Workflow Notifications

**As an** Employee, **I want to** receive notifications about important task and workflow events, **so that** I do not miss assignments, deadlines or reviews.

**Acceptance Criteria**

- Employee receives notification when a task is assigned.
- Employee receives relevant deadline notifications.
- Employee receives approval/rejection notifications.
- Employee receives reassignment notifications.
- Notifications are associated with the relevant task/workflow.

**Traceability:** FR-E10, FR-E13, FR-E18
**Priority:** High

---

### US-20 — Secure Client Portal

**As a** Client, **I want to** securely log into a client portal, **so that** I can access information related only to my projects.

**Acceptance Criteria**

- Client authentication is required.
- Client can access only associated projects.
- Client cannot access other clients' projects.
- Internal employee/HR information is not exposed.
- Unauthorized access attempts are blocked.

**Traceability:** FR-CL01, FR-CL02, FR-CL08, NFR-S-CL01, NFR-S-CL02
**Priority:** High

---

### US-21 — View Project Progress

**As a** Client, **I want to** view project milestones and high-level progress, **so that** I can monitor the progress of my project.

**Acceptance Criteria**

- Client can view associated projects.
- Client can view project milestones.
- Client can view high-level progress.
- Client cannot view internal task discussions or restricted detail.

**Traceability:** FR-CL03, FR-CL08
**Priority:** High

---

### US-22 — Review Deliverables

**As a** Client, **I want to** access and review project deliverables, **so that** I can provide feedback or sign off on submitted work.

**Acceptance Criteria**

- Client can view permitted deliverables.
- Client can download permitted files.
- Client can provide feedback.
- Client can provide sign-off where applicable.
- Client actions are recorded.

**Traceability:** FR-CL04, FR-CL05, NFR-AU-CL01
**Priority:** High

---

### US-23 — Project Management Dashboard

**As a** Project Manager, **I want to** view project progress, deadlines and at-risk work, **so that** I can take appropriate project-management action.

**Acceptance Criteria**

- PM can view active projects.
- Project status is displayed.
- Upcoming deadlines are visible.
- Delayed/at-risk work is identifiable.
- PM can access relevant progress detail.

**Traceability:** FR-PM05, FR-PM06, FR-PM09, NFR-P01
**Priority:** High

---

### US-24 — Executive Dashboard

**As an** MNC Executive, **I want to** view organization-level project and task information, **so that** I can monitor overall organizational performance.

**Acceptance Criteria**

- Executive can view active projects.
- Executive can view high-level project/task KPIs.
- Delayed or at-risk projects are identifiable.
- Information can be summarized by department/team.
- Executive cannot modify operational task information unless separately authorized.

**Traceability:** FR-EX01–FR-EX05, NFR-S03, NFR-S04
**Priority:** Medium

---

### US-25 — Management Reports

**As an** MNC Executive, **I want to** generate management reports, **so that** performance can be tracked and reported.

**Acceptance Criteria**

- Executive can select a reporting period.
- System generates the requested report.
- Report contains relevant project/team information.
- Only authorized management data is included.
- Historical information is preserved where required.

**Traceability:** FR-EX05, NFR-SC02, NFR-AU02
**Priority:** Medium

---

### US-26 — Report Technical Issue

**As an** Employee, **I want to** report a technical issue, **so that** the problem can be tracked and resolved.

**Acceptance Criteria**

- Employee can create a support ticket.
- Employee can provide an issue description.
- Employee can select an issue category.
- System generates a unique ticket number.
- Ticket records reporter and creation time.
- IT Support can access the submitted ticket.

**Traceability:** FR-ITS-01
**Priority:** Medium

---

### US-27 — Manage Support Ticket

**As** IT Support, **I want to** update and manage support tickets, **so that** technical issues can be tracked from reporting to resolution.

**Acceptance Criteria**

- IT Support can view tickets.
- IT Support can assign/reassign tickets.
- IT Support can update ticket status.
- IT Support can add troubleshooting notes.
- IT Support can mark resolved tickets.
- Ticket history is maintained.

**Traceability:** FR-ITS-02, FR-ITS-03, FR-ITS-04, NFR-ITS-06
**Priority:** Medium

---

### US-28 — Escalate Technical Issue

**As** IT Support, **I want to** escalate unresolved technical issues to the System Administrator, **so that** issues requiring higher-level access or intervention can be resolved.

**Acceptance Criteria**

- IT Support can identify an unresolved issue.
- IT Support can escalate the ticket.
- Relevant ticket information is transferred with the escalation.
- System Administrator receives the escalation.
- Escalation is recorded in ticket history.

**Traceability:** FR-ITS-05
**Priority:** Medium

---

### US-29 — User and Role Administration

**As a** System Administrator, **I want to** manage users, roles and permissions, **so that** system access remains controlled.

**Acceptance Criteria**

- Admin can create/manage user accounts.
- Admin can assign appropriate roles.
- Admin can modify permissions where authorized.
- Deactivated users cannot access the system.
- Changes to access control are audited.

**Traceability:** FR-SA01, FR-SA02, FR-SA03, NFR-S03, NFR-S04
**Priority:** High

---

### US-30 — Audit System Activities

**As a** System Administrator, **I want to** important system actions to be recorded, **so that** changes and workflow activities can be traced.

**Acceptance Criteria**

- Important actions record the responsible user.
- Timestamp is recorded.
- Important task/workflow changes are traceable.
- Audit records cannot be casually modified by ordinary users.
- Authorized administrators can review audit logs.

**Traceability:** NFR-AU01, NFR-AU02, NFR-HR02
**Priority:** High

---

### US-31 — Multi-Factor Authentication for Admin Access

**As a** System Administrator, **I want to** MFA required for admin-level logins, **so that** a stolen password alone can't compromise administrative control.

**Acceptance Criteria**

- MFA is required, not optional, for every admin-role login.
- No documented flow bypasses it.
- MFA failure is itself logged as a security event.

**Traceability:** NFR-S02
**Priority:** High

---


### US-32 — View Task Details

**As an** Employee, **I want to** view full task details (description, deadline, priority, project, attachments), **so that** I understand exactly what's expected of me.

**Acceptance Criteria**

- Opening a task shows all listed fields.
- Attachments are downloadable directly from the detail view.
- Missing fields display as empty, not as errors.

**Traceability:** FR-E04
**Priority:** High

---

### US-33 — Comment on Task

**As an** Employee, **I want to** comment on an assigned task, **so that** I can communicate context or questions to my Team Lead.

**Acceptance Criteria**

- Comments are timestamped and attributed to the author.
- Visible to the Team Lead and Project Manager.
- No hard limit on comment length within reasonable bounds.

**Traceability:** FR-E09
**Priority:** Medium

---

### US-34 — Propose Skill Profile Change

**As an** Employee, **I want to** propose changes to my skill profile, **so that** my record reflects my actual capabilities.

**Acceptance Criteria**

- Proposal is routed to the correct approver per configured policy.
- I can see the status of a pending proposal.
- Approved changes update my profile; rejected ones show a reason.

**Traceability:** FR-E15
**Priority:** Medium

---

### US-35 — Restrict Workload/Utilization Visibility

**As an** Employee, **I want to** my workload/utilization percentage visible only to authorized roles, **so that** my data isn't exposed to people who don't need it.

**Acceptance Criteria**

- Visibility settings support self, Team Lead, PM, HR, Senior Management as distinct toggles.
- Unauthorized roles can't see it even via direct link/API.
- Setting changes take effect immediately.

**Traceability:** FR-E17
**Priority:** Medium

---

### US-36 — Update Project Status

**As a** Project Manager, **I want to** update a project's information and status after creation, **so that** the record stays current as things change.

**Acceptance Criteria**

- Status options reflect the defined project lifecycle.
- Changes are timestamped.
- Relevant stakeholders are notified of significant status changes where configured.

**Traceability:** FR-PM02
**Priority:** High

---

### US-37 — View Team Members & Team Tasks

**As a** Team Lead, **I want to** view my team's members and their assigned tasks, **so that** I know who I'm managing and what everyone's working on.

**Acceptance Criteria**

- List shows every active member on my team.
- Task view is filterable by member and by project.
- Updates in real time as tasks change.

**Traceability:** FR-TL01, FR-TL02
**Priority:** High

---


### US-38 — Repeated Rejection Risk View

**As a** Project Manager, **I want to** see tasks that have been rejected or returned multiple times, **so that** I can treat repeated rejection as an early risk indicator.

**Acceptance Criteria**

- Threshold for "multiple times" is configurable or clearly defined.
- Filterable by project and by employee.
- Each entry links to the task's rejection history.

**Traceability:** FR-PM07
**Priority:** Medium

---

### US-39 — Cross-Project Workload View

**As a** Project Manager, **I want to** see an employee's aggregate task load across all projects before assigning new work, **so that** I don't accidentally overload someone who's already busy.

**Acceptance Criteria**

- Shows total open tasks/load across every project, not just mine.
- I see aggregate figures only, not other PMs' project-internal detail.
- Surfaces before I confirm the assignment.

**Traceability:** FR-PM10
**Priority:** High

---

### US-40 — Auto-Notify PM/TL on Leave Request

**As a** Project Manager, **I want to** be automatically notified when a team member on my project submits a leave request, **so that** I can plan around it instead of finding out too late.

**Acceptance Criteria**

- Fires immediately on submission, not on approval.
- Identifies the employee, dates, and affected project.
- Both the relevant PM and Team Lead receive the notification.

**Traceability:** FR-PM11
**Priority:** High

---

### US-41 — Export Client Reports

**As a** Client, **I want to** export authorized progress summaries as PDF or spreadsheet, **so that** I can share updates internally on my end.

**Acceptance Criteria**

- Produces correctly formatted PDF and spreadsheet options.
- Includes only data I'm authorized to see.
- Completes within the defined latency window.

**Traceability:** FR-CL06, NFR-P-CL02
**Priority:** Medium

---

### US-42 — Toggle Client-Visible Team Role Info

**As a** Project Manager, **I want to** toggle visibility of high-level team roles and lead contacts on the client view, **so that** I control exactly how much team detail the client sees.

**Acceptance Criteria**

- Toggle is per-project, not global.
- Default state is explicitly defined.
- Client sees the change immediately once toggled.

**Traceability:** FR-CL07
**Priority:** Low

---


### US-43 — Manage User Accounts

**As a** System Administrator, **I want to** create, edit, activate, and deactivate user accounts, **so that** I control who has system access at any time.

**Acceptance Criteria**

- All four actions available from one interface.
- Deactivating an account immediately revokes access.
- Deactivated accounts retain historical data, not active access.

**Traceability:** FR-SA01
**Priority:** High

---

### US-44 — Assign & Revoke Roles

**As a** System Administrator, **I want to** assign, modify, and revoke user roles, **so that** permissions match each person's actual responsibilities.

**Acceptance Criteria**

- Role changes take effect immediately.
- Revoking a role immediately removes associated permissions.
- Role changes are audited.

**Traceability:** FR-SA02, FR-SA03
**Priority:** High

---

### US-45 — Time-Bound Elevated Access

**As a** System Administrator, **I want to** grant time-bound temporary elevated privileges with automatic revocation, **so that** emergency access never lingers past when it's needed.

**Acceptance Criteria**

- Grant requires an explicit expiry; no indefinite option.
- Privilege reverts automatically at expiry with no manual step.
- Every grant and its expiry is logged.

**Traceability:** FR-SA04
**Priority:** Medium

---

### US-46 — Configure System-Wide Parameters

**As a** System Administrator, **I want to** configure system-wide parameters (session timeout, password policy, upload limits, maintenance mode), **so that** I can tune platform behavior without a code change.

**Acceptance Criteria**

- Each parameter has a defined valid range/format.
- Changes take effect without a restart, or clearly state if one is needed.
- Parameter changes are logged.

**Traceability:** FR-SA05
**Priority:** Medium

---

### US-47 — Search & Export Audit Logs

**As a** System Administrator, **I want to** search, filter, and export audit logs by user, date range, module, task, or project, **so that** I can investigate incidents efficiently.

**Acceptance Criteria**

- All filter dimensions work independently and combined.
- Export produces a usable file format.
- Search performance stays acceptable as log volume grows.

**Traceability:** FR-SA06, FR-SA07
**Priority:** Medium

---

### US-48 — Account Unlock & Password Recovery

**As a** System Administrator, **I want to** a secure mechanism to unlock accounts and reset/recover passwords, **so that** locked-out users can regain access safely.

**Acceptance Criteria**

- Reset requires identity verification before completing.
- Reset action is logged with who performed it.
- Temporary credentials expire quickly and force a change on first use.

**Traceability:** FR-SA08
**Priority:** High

---

### US-49 — Real-Time Anomaly Alerts

**As a** System Administrator, **I want to** real-time alerts on anomalous security events (repeated failed logins, brute-force patterns, off-hours admin access), **so that** I can respond to threats as they happen.

**Acceptance Criteria**

- Alert fires in real time, not on a delayed batch job.
- Includes enough context to act.
- Alert thresholds are configurable.

**Traceability:** FR-SA09
**Priority:** Medium

---

### US-50 — Backup & Recovery Management

**As a** System Administrator, **I want to** trigger on-demand backups and view scheduled backup status, **so that** I can confirm data protection is actually working.

**Acceptance Criteria**

- On-demand backup can be triggered without waiting for the schedule.
- Status view shows last successful backup time and any failures.
- Failed scheduled backups trigger their own alert.

**Traceability:** FR-SA10, NFR-BR01, NFR-BR02
**Priority:** High

---
