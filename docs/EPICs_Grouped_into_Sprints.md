# EPICs Grouped into Sprints

User stories are organized into 10 EPICs by theme; EPIC membership then determines how stories are sequenced into Sprints — foundational EPICs first, dependent EPICs after.

## EPICs

| Epic | Name | Goal | Stories |
|---|---|---|---|
| 1 | Authentication, Users & Role Management | Provide secure login and role-based access to WorkSphere. | US-01, US-02, US-31 |
| 2 | Employee & Organization Management | Give employees accurate self-service profile control, and give HR reliable tools to manage employee and organizational-structure records. | US-03, US-04, US-05, US-32, US-33, US-34, US-35 |
| 3 | Project Management | Give Project Managers full control over defining, resourcing, and tracking projects from creation through completion. | US-06, US-07, US-08, US-36, US-38, US-39 |
| 4 | Task & Work Management | Support the complete task lifecycle — assignment, progress tracking, submission, review, and reassignment — between Team Leads and Employees. | US-37, US-09, US-10, US-11, US-12, US-13, US-14, US-15 |
| 5 | Leave Management | Let employees request leave, and give Team Leads and HR the context and policy controls to approve it without disrupting project work. | US-16, US-17, US-18, US-40 |
| 6 | Notifications & Communication | Keep employees informed of every task and workflow event that affects them, without relying on manual check-ins. | US-19 |
| 7 | Client Portal & Deliverables | Give clients secure, self-service visibility into their own projects and deliverables without exposing internal information. | US-20, US-21, US-22, US-41, US-42 |
| 8 | Management & Executive Reporting | Give Project Managers and Executives the dashboards and reports needed to monitor performance at their respective scales. | US-23, US-24, US-25 |
| 9 | IT Support & System Issues | Let employees report technical issues, and give IT Support a full ticket lifecycle including escalation to the System Administrator. | US-26, US-27, US-28 |
| 10 | System Administration & Audit | Give the System Administrator complete control over accounts, roles, security, and system-wide auditability. | US-29, US-30, US-43, US-44, US-45, US-46, US-47, US-48, US-49, US-50 |

## Sprints (Generated from EPICs)

### Sprint 1 — Foundation & Security
*Goal: Build the basic system foundation and authentication.*

| Story | Title | Epic |
|---|---|---|
| US-01 | User Login | Epic 1 |
| US-02 | Role-Based Access | Epic 1 |
| US-31 | Multi-Factor Authentication for Admin Access | Epic 1 |
| US-03 | Employee Profile | Epic 2 |
| US-04 | Employee Records | Epic 2 |
| US-05 | Department & Team Management | Epic 2 |
| US-37 | View Team Members & Team Tasks | Epic 4 |
| US-29 | User and Role Administration | Epic 10 |
| US-30 | Audit System Activities | Epic 10 |
| US-43 | Manage User Accounts | Epic 10 |
| US-44 | Assign & Revoke Roles | Epic 10 |
| US-48 | Account Unlock & Password Recovery | Epic 10 |
| US-50 | Backup & Recovery Management | Epic 10 |

### Sprint 2 — Project & Task Management
*Goal: Establish the core WorkSphere workflow.*

| Story | Title | Epic |
|---|---|---|
| US-06 | Create Project | Epic 3 |
| US-36 | Update Project Status | Epic 3 |
| US-07 | Manage Project Team | Epic 3 |
| US-08 | Project Milestones | Epic 3 |
| US-09 | Create and Assign Task | Epic 4 |
| US-32 | View Task Details | Epic 2 |
| US-10 | Update Task Progress | Epic 4 |
| US-33 | Comment on Task | Epic 2 |
| US-11 | Submit Completed Task | Epic 4 |

### Sprint 3 — Task Review & Workflows
*Goal: Complete the task lifecycle.*

| Story | Title | Epic |
|---|---|---|
| US-12 | Review Task | Epic 4 |
| US-13 | Revise and Resubmit Task | Epic 4 |
| US-14 | Reassign Task | Epic 4 |
| US-15 | Monitor Overdue Work | Epic 4 |
| US-38 | Repeated Rejection Risk View | Epic 3 |
| US-19 | Task and Workflow Notifications | Epic 6 |
| US-23 | Project Management Dashboard | Epic 8 |

### Sprint 4 — Leave Management
*Goal: Implement employee leave and its effect on project work.*

| Story | Title | Epic |
|---|---|---|
| US-16 | Submit Leave Request | Epic 5 |
| US-17 | Check Leave Conflicts | Epic 5 |
| US-40 | Auto-Notify PM/TL on Leave Request | Epic 5 |
| US-18 | Manage Leave Policies | Epic 5 |

### Sprint 5 — Client & Management Visibility
*Goal: Provide controlled external and executive visibility.*

| Story | Title | Epic |
|---|---|---|
| US-20 | Secure Client Portal | Epic 7 |
| US-21 | View Project Progress | Epic 7 |
| US-22 | Review Deliverables | Epic 7 |
| US-41 | Export Client Reports | Epic 7 |
| US-42 | Toggle Client-Visible Team Role Info | Epic 7 |
| US-39 | Cross-Project Workload View | Epic 3 |
| US-24 | Executive Dashboard | Epic 8 |
| US-25 | Management Reports | Epic 8 |

### Sprint 6 — IT Support & System Operations
*Goal: Add technical support and operational workflows.*

| Story | Title | Epic |
|---|---|---|
| US-26 | Report Technical Issue | Epic 9 |
| US-27 | Manage Support Ticket | Epic 9 |
| US-28 | Escalate Technical Issue | Epic 9 |

### Sprint 7 — Admin Depth & Employee Polish
*Goal: Round out lower-urgency System Administrator capabilities and employee-side polish items that don't block earlier sprints.*

| Story | Title | Epic |
|---|---|---|
| US-34 | Propose Skill Profile Change | Epic 2 |
| US-35 | Restrict Workload/Utilization Visibility | Epic 2 |
| US-45 | Time-Bound Elevated Access | Epic 10 |
| US-46 | Configure System-Wide Parameters | Epic 10 |
| US-47 | Search & Export Audit Logs | Epic 10 |
| US-49 | Real-Time Anomaly Alerts | Epic 10 |
