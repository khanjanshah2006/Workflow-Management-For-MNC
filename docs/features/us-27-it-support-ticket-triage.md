# US-27: IT Support Staff Ticket Triage, Assignment & Troubleshooting Notes

## Overview
- **Scenario:** S8 — IT Support Ticket Lifecycle
- **User Story:** US-27 (Manage Support Ticket)
- **Assignee:** `@konark-17`
- **Milestone:** Wave 1 (Days 3–5)
- **Branch:** `feature/us-27-it-ticket-management`
- **Target Branch:** `develop`

## Technical Scope
US-27 empowers IT Support personnel and System Administrators with operational tools to manage incoming technical support requests:
1. **Queue View & Triage:** Inspect incoming tickets with multi-dimensional filtering by `status`, `category`, `assigned_to`, and `priority`.
2. **Ticket Assignment:** Assign tickets to qualified IT Support staff, enforcing role validation to prevent assignment to unqualified personnel.
3. **Internal Troubleshooting Notes:** Record internal notes and diagnostics directly in `ticket_activity` without altering the public ticket description, updating `updated_at`.
4. **Status Transitions & Reporter Notification:** Update ticket lifecycle state (`open` -> `in_progress` -> `resolved` / `escalated`), automatically triggering dispatch to the reporter via the notification service upon resolution.
5. **Dashboard Queue Metrics:** Real-time summary counts for open, in-progress, resolved, escalated, and unassigned tickets.

---

## RBAC Security Matrix
| Endpoint | Allowed Roles | Forbidden (403) |
| :--- | :--- | :--- |
| `GET /api/v1/support/tickets` | `IT_SUPPORT`, `SYSTEM_ADMIN` | `EMPLOYEE`, `HR_ADMIN`, `FINANCE_ADMIN`, etc. |
| `PUT /api/v1/support/tickets/{id}/assign` | `IT_SUPPORT`, `SYSTEM_ADMIN` | `EMPLOYEE`, others |
| `POST /api/v1/support/tickets/{id}/notes` | `IT_SUPPORT`, `SYSTEM_ADMIN` | `EMPLOYEE`, others |
| `PUT /api/v1/support/tickets/{id}/status` | `IT_SUPPORT`, `SYSTEM_ADMIN` | `EMPLOYEE`, others |
| `GET /api/v1/support/tickets/queue/metrics`| `IT_SUPPORT`, `SYSTEM_ADMIN` | `EMPLOYEE`, others |

---

## API Endpoints Reference

### 1. IT Support Queue View
- **URL:** `GET /api/v1/support/tickets`
- **Query Parameters:**
  - `status` (optional): `open`, `in_progress`, `resolved`, `escalated`, `closed`
  - `category` (optional): `hardware`, `software`, `network`, `access`, `other`
  - `assigned_to` (optional): UUID of assigned IT staff member
  - `priority` (optional): `LOW`, `MEDIUM`, `HIGH`, `CRITICAL`
  - `skip` / `limit` (optional): Pagination offsets (default: 0, 50)
- **Response:** `200 OK` (Array of `TicketOut`)

### 2. Assign Ticket
- **URL:** `PUT /api/v1/support/tickets/{id}/assign`
- **Request Body:**
  ```json
  {
    "assigned_to": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
    "reassignment_reason": "Escalating hardware issue to tier-2 technician"
  }
  ```
- **Validation:** Verifies target assignee exists and holds the `IT_SUPPORT` role. Returns `422 Unprocessable Entity` if assignee is not IT Support.
- **Activity Logged:** `ASSIGNED`

### 3. Append Troubleshooting Note
- **URL:** `POST /api/v1/support/tickets/{id}/notes`
- **Request Body:**
  ```json
  {
    "note": "Replaced RAM module in slot 2. Ran diagnostic memory test suite - 100% pass."
  }
  ```
- **Activity Logged:** `NOTE_ADDED`
- **Side Effect:** Updates `updated_at` timestamp on parent ticket.

### 4. Transition Status
- **URL:** `PUT /api/v1/support/tickets/{id}/status`
- **Request Body:**
  ```json
  {
    "status": "resolved",
    "resolution_notes": "Replaced faulty hardware component and verified user access."
  }
  ```
- **Activity Logged:** `STATUS_CHANGED`
- **Notification:** Automatically triggers `notification_service.notify(...)` to `reporter_id` with type `TICKET_RESOLVED`.

### 5. Queue Metrics
- **URL:** `GET /api/v1/support/tickets/queue/metrics`
- **Response:** `200 OK`
  ```json
  {
    "open_count": 5,
    "in_progress_count": 3,
    "resolved_count": 12,
    "escalated_count": 1,
    "unassigned_count": 4,
    "total_tickets": 21
  }
  ```

---

## Verification & Testing
### Automated Pytest Suite
Run the test suites:
```bash
python -m pytest backend/tests/test_support_ticket_triage.py -v
python -m pytest backend/tests/test_support_ticket_integration.py -v
```

### Postman Testing
Import `docs/postman/wms.postman_collection.json` and environment `docs/postman/support_ticket_triage.postman_environment.json`.
Run the requests located under folder **09 Support**.
