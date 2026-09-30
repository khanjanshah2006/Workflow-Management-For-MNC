---
name: react-feature-scaffold
description: Use whenever building a new page, panel, or component in wms-frontend. Defines the required pattern (API hook, role guard, folder placement) so all 11 of us produce consistent components instead of each inventing our own data-fetching and access-control approach.
---

# Workflow Management System for MNCs React Feature Pattern

## Folder placement

New UI for Epic N goes in `src/features/<epic-folder>/`, matching the backend router of the same Epic. Never create a top-level page outside `features/` unless it's truly shared across every role (those go in `components/`).

## Standard component shape

```jsx
// features/leave/LeaveApprovalPanel.jsx
import { useAuth } from '@/hooks/useAuth';
import { useQuery, useMutation } from '@tanstack/react-query';
import { leaveApi } from '@/api/leaveApi';

export default function LeaveApprovalPanel() {
  const { user } = useAuth();
  if (user.role !== 'Team Lead') return null; // belt-and-suspenders; ProtectedRoute already blocks the route

  const { data: requests } = useQuery(['leave-requests', 'pending'], leaveApi.getPendingForTeam);
  const approve = useMutation(leaveApi.approveRequest);

  // ...render
}
```

## The three things every data-bearing feature component needs

1. **Role guard** — even though `ProtectedRoute` blocks the route itself, components that render conditionally within a shared page (e.g. a dashboard showing different widgets per role) must check `useAuth().user.role` before rendering role-specific data, not just before rendering the route.
2. **One API file per backend router** — call through `api/<domain>Api.js`, never call `fetch`/`axios` directly inside a component. If the endpoint you need doesn't have a corresponding function in the api file yet, add it there first.
3. **Loading and error states** — every query needs a visible loading state and an error state that shows what went wrong (matches NFR-U03's "clear error messages" requirement, which applies to the UI too, not just the API).

## Notifications

Any feature that triggers a backend action the user should be notified about (task submission, leave request, etc.) doesn't need to handle notification display itself — `components/layout/NotificationBell.jsx` polls/subscribes centrally. Don't build a second notification UI inside a feature folder.
