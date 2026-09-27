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
