## Functional and Non-Functional Requirements (FR/NFR)

> This document presents the finalized Functional Requirements (FR) and
> Non-Functional Requirements (NFR) for all stakeholders of the
> **Workflow Management System for MNCs**.

------------------------------------------------------------------------

## 1. HR Manager

### 1.1 Functional Requirements

  -----------------------------------------------------------------------
  ID                                  Requirement
  ----------------------------------- -----------------------------------
  **FR-HR01**                         The system shall allow the HR
                                      Manager to create and maintain
                                      employee records.

  **FR-HR02**                         The system shall allow the HR
                                      Manager to assign employees to
                                      departments.

  **FR-HR03**                         The system shall allow the HR
                                      Manager to create teams and assign
                                      or change Team Leads.

  **FR-HR04**                         The system shall allow the HR
                                      Manager to view and manage the
                                      organizational hierarchy of
                                      departments, teams, employees, and
                                      their reporting managers.

  **FR-HR05**                         The system shall allow the HR
                                      Manager to view and manage employee
                                      leave requests according to the
                                      applicable leave policies.

  **FR-HR06**                         The system shall allow the HR
                                      Manager to define and manage leave
                                      policies and entitlements based on
                                      an employee's region or office.
  -----------------------------------------------------------------------

### 1.2 Non-Functional Requirements

  -----------------------------------------------------------------------
  ID                      Category                Requirement
  ----------------------- ----------------------- -----------------------
  **NFR-HR01**            Security /              The system shall ensure
                          Confidentiality         that employee and leave
                                                  information is
                                                  accessible only to
                                                  authorized users
                                                  according to their
                                                  assigned role and
                                                  organizational scope.

  **NFR-HR02**            Auditability            The system shall record
                                                  the user and timestamp
                                                  for important HR
                                                  actions, including
                                                  employee-record updates
                                                  and changes to leave
                                                  policies.

  **NFR-HR03**            Data Integrity          The system shall
                                                  validate HR-related
                                                  information before
                                                  storing it and prevent
                                                  invalid or incomplete
                                                  employee, department,
                                                  team, and leave-policy
                                                  records.
  -----------------------------------------------------------------------

------------------------------------------------------------------------

## 2. Team Lead

### 2.1 Functional Requirements

  -----------------------------------------------------------------------
  ID                                  Requirement
  ----------------------------------- -----------------------------------
  **FR-TL01**                         The system shall allow a Team Lead
                                      to view the members of their team.

  **FR-TL02**                         The system shall allow a Team Lead
                                      to view tasks assigned to members
                                      of their team.

  **FR-TL03**                         The system shall allow a Team Lead
                                      to create a task within a project
                                      and assign it to an eligible team
                                      member.

  **FR-TL04**                         The system shall allow a Team Lead
                                      to set or modify a task's deadline
                                      and priority.

  **FR-TL05**                         The system shall allow a Team Lead
                                      to reassign a task to another
                                      eligible team member.

  **FR-TL06**                         The system shall allow a Team Lead
                                      to review a submitted task.

  **FR-TL07**                         The system shall allow a Team Lead
                                      to approve a submitted task.

  **FR-TL08**                         The system shall allow a Team Lead
                                      to reject or return a submitted
                                      task with a mandatory reason.

  **FR-TL09**                         The system shall display overdue
                                      tasks belonging to the Team Lead's
                                      team.

  **FR-TL10**                         The system shall display aggregate
                                      team task progress for a selected
                                      project.

  **FR-TL11**                         The system shall notify the Team
                                      Lead when assigned team tasks
                                      become overdue or are submitted for
                                      review.

  **FR-TL12**                         The system shall display an
                                      employee's current leave balance
                                      and task deadlines together before
                                      a Team Lead approves or reassigns a
                                      leave request.

  **FR-TL13**                         The system shall allow a Team Lead
                                      to view aggregated logged hours by
                                      employee and by project for a
                                      selected period.
  -----------------------------------------------------------------------

### 2.2 Non-Functional Requirements

  -----------------------------------------------------------------------
  ID                      Category                Requirement
  ----------------------- ----------------------- -----------------------
  **NFR-P02**             Performance             The system shall
                                                  reflect a task status
                                                  update in the UI within
                                                  2 seconds of successful
                                                  processing under normal
                                                  load.

  **NFR-U02**             Usability               Task status, priority,
                                                  deadline, and required
                                                  actions shall be
                                                  clearly displayed to
                                                  the user.

  **NFR-U04**             Usability               Common operations such
                                                  as reviewing and
                                                  approving a task shall
                                                  be accessible without
                                                  unnecessary navigation
                                                  steps.

  **NFR-S04**             Security                The system shall ensure
                                                  a Team Lead can access
                                                  only the team, task,
                                                  and leave data
                                                  permitted by their role
                                                  and team scope.

  **NFR-AU01**            Auditability            Task and leave
                                                  approvals, rejections,
                                                  and reassignments shall
                                                  record the responsible
                                                  user and timestamp.

  **NFR-R04**             Reliability             Where an Employee has
                                                  selected multiple
                                                  notification channels,
                                                  the system shall
                                                  attempt delivery on a
                                                  fallback channel if the
                                                  primary channel fails.
  -----------------------------------------------------------------------

------------------------------------------------------------------------

## 3. Project Manager

### 3.1 Functional Requirements

  -----------------------------------------------------------------------
  ID                                  Requirement
  ----------------------------------- -----------------------------------
  **FR-PM01**                         The system shall allow a Project
                                      Manager to create a project with a
                                      name, description, start date, and
                                      target end date.

  **FR-PM02**                         The system shall allow a Project
                                      Manager to update project
                                      information and status.

  **FR-PM03**                         The system shall allow a Project
                                      Manager to add or remove authorized
                                      employees and Team Leads from a
                                      project.

  **FR-PM04**                         The system shall allow a Project
                                      Manager to define project
                                      milestones and target dates.

  **FR-PM05**                         The system shall allow a Project
                                      Manager to view the overall project
                                      status, including completed,
                                      in-progress, and overdue tasks.

  **FR-PM06**                         The system shall allow a Project
                                      Manager to monitor project
                                      deadlines and identify delayed or
                                      at-risk work.

  **FR-PM07**                         The system shall allow a Project
                                      Manager to view tasks that have
                                      been rejected or returned multiple
                                      times.

  **FR-PM08**                         The system shall allow a Project
                                      Manager to reassign or escalate
                                      work when project progress is at
                                      risk.

  **FR-PM09**                         The system shall allow a Project
                                      Manager to view and generate
                                      project progress reports.

  **FR-PM10**                         The system shall allow a Project
                                      Manager to view an employee's
                                      aggregate task load across all
                                      projects before assigning new work.

  **FR-PM11**                         The system shall automatically
                                      notify the relevant Project Manager
                                      and Team Lead when a team member on
                                      their project submits a leave
                                      request.

  **FR-PM12**                         The system shall allow a Project
                                      Manager to view aggregated logged
                                      hours by employee and by project
                                      for a selected period.
  -----------------------------------------------------------------------

### 3.2 Non-Functional Requirements

  -----------------------------------------------------------------------
  ID                      Category                Requirement
  ----------------------- ----------------------- -----------------------
  **NFR-P01**             Performance             The system shall load
                                                  the Project Manager's
                                                  project status view
                                                  within 3 seconds under
                                                  normal load.

  **NFR-SC01**            Scalability             The system shall
                                                  support a growing
                                                  number of projects,
                                                  tasks, and employees
                                                  without requiring a
                                                  redesign of the data
                                                  model.

  **NFR-S04**             Security                The system shall ensure
                                                  a Project Manager can
                                                  access only the
                                                  projects, tasks, and
                                                  employee data permitted
                                                  by their role and
                                                  project scope.

  **NFR-DI02**            Data Integrity          The system shall
                                                  prevent invalid
                                                  relationships, such as
                                                  assigning a task to an
                                                  inactive or
                                                  unauthorized employee.

  **NFR-U01**             Usability               The system shall
                                                  provide consistent
                                                  navigation and
                                                  interface structure
                                                  across all project
                                                  views.

  **NFR-AU02**            Auditability            The system shall
                                                  maintain the
                                                  chronological history
                                                  of important task and
                                                  workflow state changes.

  **NFR-R03**             Reliability             The system shall
                                                  display an appropriate
                                                  error message when an
                                                  operation cannot be
                                                  completed, instead of
                                                  failing silently.
  -----------------------------------------------------------------------

------------------------------------------------------------------------

## 4. IT Support

### 4.1 Functional Requirements

  -----------------------------------------------------------------------
  ID                                  Requirement
  ----------------------------------- -----------------------------------
  **FR-ITS-01**                       The system shall allow employees to
                                      report technical issues with
                                      required information such as
                                      description and category.

  **FR-ITS-02**                       The system shall allow IT Support
                                      to view, track, and update the
                                      status of support tickets
                                      throughout their lifecycle.

  **FR-ITS-03**                       The system shall allow IT Support
                                      to assign, reassign, and prioritize
                                      support tickets.

  **FR-ITS-04**                       The system shall allow IT Support
                                      to record troubleshooting details
                                      and mark tickets as resolved or
                                      closed.

  **FR-ITS-05**                       The system shall allow IT Support
                                      to escalate unresolved issues to
                                      the System Administrator along with
                                      relevant ticket information and
                                      troubleshooting history.

  **FR-ITS-06**                       The system shall notify employees
                                      about relevant changes in the
                                      status of their support tickets.
  -----------------------------------------------------------------------

### 4.2 Non-Functional Requirements

  -----------------------------------------------------------------------
  ID                      Category                Requirement
  ----------------------- ----------------------- -----------------------
  **NFR-ITS-01**          Security                The system shall
                                                  restrict ticket and
                                                  employee information to
                                                  authorized users
                                                  according to their
                                                  assigned role.

  **NFR-ITS-02**          Security                The system shall
                                                  provide appropriate
                                                  access controls to
                                                  prevent IT Support from
                                                  accessing information
                                                  outside their
                                                  authorized
                                                  responsibilities.

  **NFR-ITS-03**          Performance             Support-ticket
                                                  information should load
                                                  and update within an
                                                  acceptable response
                                                  time during normal
                                                  system usage.

  **NFR-ITS-04**          Reliability             The system shall
                                                  reliably preserve
                                                  ticket information when
                                                  an issue is submitted
                                                  or updated.

  **NFR-ITS-05**          Usability/Reliability   The system shall
                                                  provide clear feedback
                                                  when a ticket operation
                                                  fails because of a
                                                  system error.

  **NFR-ITS-06**          Auditability            The system shall
                                                  maintain an audit trail
                                                  of important support
                                                  activities, including
                                                  assignment, status
                                                  changes, escalation,
                                                  and resolution.
  -----------------------------------------------------------------------

### 4.3 Domain Requirements

  -----------------------------------------------------------------------
  ID                                  Requirement
  ----------------------------------- -----------------------------------
  **DR-ITS-01**                       Every technical issue shall be
                                      recorded as a support ticket
                                      containing sufficient information
                                      to identify the issue and
                                      requester.

  **DR-ITS-02**                       Support tickets shall follow a
                                      defined lifecycle from reporting
                                      through investigation, resolution,
                                      and closure.

  **DR-ITS-03**                       Technical issues shall be
                                      prioritized according to their
                                      urgency, impact, and/or number of
                                      affected users.

  **DR-ITS-04**                       Issues that cannot be resolved by
                                      IT Support shall be escalated to
                                      the appropriate technical authority
                                      with relevant troubleshooting
                                      information.

  **DR-ITS-05**                       Access to employee and
                                      technical-support information shall
                                      be restricted according to
                                      organizational roles and
                                      responsibilities.
  -----------------------------------------------------------------------

------------------------------------------------------------------------

## 5. System Administrator

### 5.1 Functional Requirements

  -----------------------------------------------------------------------
  ID                                  Requirement
  ----------------------------------- -----------------------------------
  **FR-SA01**                         The system shall allow a System
                                      Administrator to create, view,
                                      edit, activate, and deactivate user
                                      accounts.

  **FR-SA02**                         The system shall allow a System
                                      Administrator to assign, modify,
                                      and revoke user roles across all
                                      designated system roles.

  **FR-SA03**                         The system shall enforce role-based
                                      access control (RBAC) dynamically
                                      according to the roles and
                                      privileges assigned to each user.

  **FR-SA04**                         The system shall allow a System
                                      Administrator to grant time-bound
                                      temporary elevated privileges with
                                      automated revocation upon
                                      expiration.

  **FR-SA05**                         The system shall allow a System
                                      Administrator to configure approved
                                      system-wide parameters, including
                                      session timeout duration, password
                                      complexity policies, file upload
                                      limits, and maintenance mode
                                      toggles.

  **FR-SA06**                         The system shall record and
                                      maintain an immutable chronological
                                      audit trail of all administrative
                                      actions, role modifications,
                                      account state transitions, and
                                      sensitive workflow overrides.

  **FR-SA07**                         The system shall provide an
                                      administrative interface to search,
                                      filter, and export audit log
                                      records by user ID, date-time
                                      range, module, task, or project.

  **FR-SA08**                         The system shall provide an
                                      authorized administrative mechanism
                                      to initiate secure account
                                      unlocking and password
                                      reset/recovery workflows.

  **FR-SA09**                         The system shall alert the System
                                      Administrator in real time
                                      regarding anomalous security
                                      events, such as repeated failed
                                      authentication attempts,
                                      brute-force patterns, or off-hours
                                      administrative access.

  **FR-SA10**                         The system shall allow a System
                                      Administrator to initiate on-demand
                                      system data backups and view the
                                      status of automated scheduled
                                      backups.
  -----------------------------------------------------------------------

### 5.2 Non-Functional Requirements

  -----------------------------------------------------------------------
  ID                      Category                Requirement
  ----------------------- ----------------------- -----------------------
  **NFR-S01**             Security                The system shall store
                                                  user credentials using
                                                  strong salted
                                                  cryptographic hashing
                                                  algorithms and shall
                                                  never store passwords
                                                  in plain text.

  **NFR-S02**             Security                The system shall
                                                  enforce Multi-Factor
                                                  Authentication (MFA) or
                                                  strict secondary
                                                  verification for all
                                                  accounts accessing
                                                  administrative
                                                  interfaces.

  **NFR-S03**             Security                The system shall
                                                  automatically terminate
                                                  and invalidate
                                                  administrative sessions
                                                  after 15 minutes of
                                                  user inactivity.

  **NFR-AU03**            Auditability            Normal users shall not
                                                  be able to modify or
                                                  delete audit records;
                                                  audit storage shall be
                                                  write-once and
                                                  tamper-evident,
                                                  verifiable rather than
                                                  merely
                                                  access-restricted.

  **NFR-AU04**            Auditability            All administrative
                                                  actions, role
                                                  assignments, privilege
                                                  escalations, and system
                                                  configuration edits
                                                  shall automatically
                                                  capture the responsible
                                                  user ID, IP address,
                                                  action type, and exact
                                                  UTC timestamp.

  **NFR-BR01**            Backup & Recovery       The system database and
                                                  application state shall
                                                  undergo automated
                                                  scheduled backups
                                                  daily, with a Recovery
                                                  Point Objective (RPO)
                                                  of less than 24 hours.

  **NFR-BR02**            Backup & Recovery       The system shall
                                                  provide a documented
                                                  and verifiable
                                                  mechanism to restore
                                                  full operational state
                                                  from a valid backup
                                                  snapshot within a
                                                  Recovery Time Objective
                                                  (RTO) of 2 hours.

  **NFR-A01**             Availability            The system shall remain
                                                  available during its
                                                  defined operating
                                                  period except for
                                                  planned maintenance or
                                                  unexpected failures;
                                                  the administrative
                                                  subsystem specifically
                                                  shall maintain 99.9%
                                                  uptime and the client
                                                  portal 99.5%, both
                                                  outside scheduled
                                                  maintenance windows
                                                  communicated in
                                                  advance.

  **NFR-SC03**            Scalability             The user directory and
                                                  RBAC permission
                                                  evaluation engine shall
                                                  support up to 10,000
                                                  active concurrent user
                                                  accounts without
                                                  introducing latency
                                                  exceeding 100
                                                  milliseconds during
                                                  session validation.

  **NFR-DI04**            Data Integrity          The system shall
                                                  prevent referential
                                                  integrity errors by
                                                  disallowing hard
                                                  deletion of user
                                                  accounts that are tied
                                                  to active tasks,
                                                  projects, or historical
                                                  audit logs.
  -----------------------------------------------------------------------

------------------------------------------------------------------------

## 6. Client / Customer

### 6.1 Functional Requirements

  -----------------------------------------------------------------------
  ID                                  Requirement
  ----------------------------------- -----------------------------------
  **FR-CL01**                         The system shall allow authorized
                                      clients to authenticate securely
                                      into a dedicated, restricted client
                                      portal.

  **FR-CL02**                         The system shall display only
                                      projects, schedules, and
                                      deliverables associated with the
                                      logged-in client account.

  **FR-CL03**                         The system shall display authorized
                                      milestone status, percentage
                                      complete, delivery projections, and
                                      high-level risk indicators.

  **FR-CL04**                         The system shall allow clients to
                                      view and download deliverables
                                      explicitly marked as client-visible
                                      by project management.

  **FR-CL05**                         The system shall allow clients to
                                      submit formal approvals,
                                      rejections, and structured review
                                      feedback directly on authorized
                                      project deliverables.

  **FR-CL06**                         The system shall allow clients to
                                      generate and export authorized
                                      progress summaries in standardized
                                      PDF and spreadsheet formats.

  **FR-CL07**                         The system shall permit project
                                      managers to toggle visibility of
                                      high-level team roles and lead
                                      contacts on client project views.

  **FR-CL08**                         The system shall strictly prevent
                                      clients from accessing internal
                                      task assignments, employee
                                      profiles, internal discussion
                                      comments, or unshared project
                                      notes.
  -----------------------------------------------------------------------

### 6.2 Non-Functional Requirements

  -----------------------------------------------------------------------
  ID                      Category                Requirement
  ----------------------- ----------------------- -----------------------
  **NFR-S-CL01**          Security                The system shall
                                                  enforce rigorous data
                                                  segregation and
                                                  role-based access
                                                  control, ensuring no
                                                  client user can view
                                                  data, deliverables, or
                                                  projects belonging to
                                                  other accounts.

  **NFR-S-CL02**          Security                The system shall
                                                  automatically sanitize
                                                  and strip internal
                                                  comments, drafts, and
                                                  employee metrics from
                                                  all client-facing
                                                  interfaces and API
                                                  payloads.

  **NFR-P-CL01**          Performance             The client portal
                                                  overview and milestone
                                                  tracking screens shall
                                                  load within 3 seconds
                                                  under normal expected
                                                  operating load.

  **NFR-P-CL02**          Performance             Downloadable
                                                  client-facing PDF
                                                  summary reports shall
                                                  compile and render
                                                  within 4 seconds of
                                                  request initiation.

  **NFR-U-CL01**          Usability               The client portal shall
                                                  provide an intuitive,
                                                  self-service layout
                                                  requiring zero formal
                                                  system training for
                                                  clients to review work
                                                  and submit feedback.

  **NFR-AU-CL01**         Auditability            The system shall record
                                                  an immutable,
                                                  time-stamped audit
                                                  entry whenever a client
                                                  accesses deliverables,
                                                  logs reviews, or issues
                                                  an approval.

  **NFR-A-CL01**          Availability            The client portal
                                                  interface shall remain
                                                  available 24/7 with a
                                                  minimum uptime of
                                                  99.5%, excluding
                                                  scheduled maintenance
                                                  windows announced in
                                                  advance.
  -----------------------------------------------------------------------

------------------------------------------------------------------------

## 7. MNC Executive

### 7.1 Functional Requirements --- Confirmed

  -----------------------------------------------------------------------
  ID                                  Requirement
  ----------------------------------- -----------------------------------
  **FR-EX01**                         The system shall provide an MNC
                                      Executive with a dashboard
                                      summarizing active projects across
                                      the organization.

  **FR-EX02**                         The system shall allow an MNC
                                      Executive to view
                                      organization-level project and task
                                      KPIs.

  **FR-EX03**                         The system shall allow an MNC
                                      Executive to view projects that are
                                      delayed, at risk, or escalated.

  **FR-EX04**                         The system shall allow an MNC
                                      Executive to view summarized
                                      performance information by
                                      department or team.

  **FR-EX05**                         The system shall allow an MNC
                                      Executive to generate
                                      management-level reports for a
                                      selected period.
  -----------------------------------------------------------------------

### 7.2 Functional Requirements --- Suggested, Not Yet Validated

  -----------------------------------------------------------------------
  ID                                  Requirement
  ----------------------------------- -----------------------------------
  **FR-EX06**                         The system shall allow an MNC
                                      Executive to view summarized
                                      resource utilization across
                                      projects, departments, or teams.

  **FR-EX07**                         The system shall allow an MNC
                                      Executive to compare project and
                                      organizational performance across
                                      different time periods.

  **FR-EX08**                         The system shall allow an MNC
                                      Executive to drill down from
                                      organization-level information to
                                      department, team, and project-level
                                      information.

  **FR-EX09**                         The system shall allow an MNC
                                      Executive to view important project
                                      dependencies that may affect
                                      organizational progress.
  -----------------------------------------------------------------------

> **Status:** FR-EX01--FR-EX05 are candidate requirements to validate
> through interview. FR-EX06--FR-EX09 require validation before being
> added to the finalized master set.

### 7.3 Relevant Existing NFRs

  -----------------------------------------------------------------------
  ID                                  Requirement
  ----------------------------------- -----------------------------------
  **NFR-S03**                         Role-based access control.

  **NFR-S04**                         Access restricted according to role
                                      and organizational scope.

  **NFR-SC01**                        System supports growth in
                                      employees, projects, tasks, and
                                      workflow records.

  **NFR-SC02**                        Historical project, task, workflow,
                                      and audit records are retained.

  **NFR-AU01**                        Important actions record the
                                      responsible user and timestamp.

  **NFR-AU02**                        Chronological history of important
                                      workflow/state changes.

  **NFR-P01--P03**                    Performance and expected
                                      concurrent-user support.
  -----------------------------------------------------------------------

------------------------------------------------------------------------

## 8. Employee

### 8.1 Functional Requirements

  -----------------------------------------------------------------------
  ID                                  Requirement
  ----------------------------------- -----------------------------------
  **FR-E01**                          The system shall allow an employee
                                      to log in using a unique employee
                                      ID/username and password.

  **FR-E02**                          The system shall allow an employee
                                      to view and update their basic
                                      profile information permitted by
                                      the organization.

  **FR-E03**                          The system shall display all tasks
                                      currently assigned to the logged-in
                                      employee.

  **FR-E04**                          The system shall allow an employee
                                      to view task details including
                                      description, deadline, priority,
                                      project, and attached files.

  **FR-E05**                          The system shall allow an employee
                                      to update the progress status of an
                                      assigned task.

  **FR-E06**                          The system shall allow an employee
                                      to submit a completed task for
                                      review with comments and optional
                                      file attachments.

  **FR-E07**                          The system shall allow an employee
                                      to view feedback and rejection
                                      reasons provided by the reviewer.

  **FR-E08**                          The system shall allow an employee
                                      to revise and resubmit a rejected
                                      task.

  **FR-E09**                          The system shall allow an employee
                                      to add comments to an assigned
                                      task.

  **FR-E10**                          The system shall notify an employee
                                      when a task is assigned,
                                      approaching its deadline, approved,
                                      rejected, or returned for
                                      correction.

  **FR-E12**                          The system shall allow an Employee
                                      to submit a leave request
                                      specifying dates, type, and reason.

  **FR-E13**                          The system shall notify an Employee
                                      immediately when they are added to
                                      or removed from a project.

  **FR-E14**                          The system shall allow an Employee
                                      to select their preferred
                                      notification channel(s) for
                                      assignment, leave, and approval
                                      notifications.

  **FR-E15**                          The system shall allow an Employee
                                      to propose changes to their skill
                                      profile, routed for approval
                                      according to configured
                                      organizational policy.

  **FR-E16**                          The system shall allow an Employee
                                      to log time spent against an
                                      assigned task or project, if
                                      time-tracking functionality is
                                      included in the finalized project
                                      scope.

  **FR-E17**                          The system shall restrict
                                      visibility of an Employee's
                                      workload/utilization percentage to
                                      roles authorized under configured
                                      visibility settings.

  **FR-E18**                          The system shall notify affected
                                      employees when a project's scope,
                                      milestones, or their task's
                                      requirements change.
  -----------------------------------------------------------------------

### 8.2 Non-Functional Requirements

  -----------------------------------------------------------------------
  ID                      Category                Requirement
  ----------------------- ----------------------- -----------------------
  **NFR-U05**             Usability               The system shall
                                                  provide a
                                                  mobile-responsive
                                                  interface with full
                                                  parity to desktop for
                                                  core functions: task
                                                  view, leave request,
                                                  and notifications.

  **NFR-R04**             Reliability             Where an Employee has
                                                  selected multiple
                                                  notification channels,
                                                  the system shall
                                                  attempt delivery on a
                                                  fallback channel if the
                                                  primary channel fails.
  -----------------------------------------------------------------------

------------------------------------------------------------------------

## Requirement Status Notes

-   Requirements marked **Confirmed** are part of the current confirmed
    set.
-   Requirements marked **Suggested, Not Yet Validated** must be
    validated before being added to the finalized master set.
-   Requirement IDs are retained as provided by the project requirements
    document.
