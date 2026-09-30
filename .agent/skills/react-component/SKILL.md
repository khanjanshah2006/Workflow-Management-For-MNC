---
name: react-component
description: Use when scaffolding a brand-new React component or page from scratch (not editing an existing one — see react-feature-scaffold for the underlying conventions). Generates boilerplate with the role guard, API call, and loading/error states pre-wired.
---

# Scaffold a New React Component

Prerequisite: know which Epic this belongs to and which feature folder it goes in (`project-structure`). Don't create a component outside `features/<epic>/` unless it's genuinely shared across every role.

## Page/panel template

```jsx
// features/<epic>/<ComponentName>.jsx
import { useAuth } from '@/hooks/useAuth';
import { useQuery } from '@tanstack/react-query';
import { <domain>Api } from '@/api/<domain>Api';

export default function <ComponentName>() {
  const { user } = useAuth();
  if (!['<AllowedRole1>', '<AllowedRole2>'].includes(user.role)) return null;

  const { data, isLoading, error } = useQuery(['<query-key>'], <domain>Api.<method>);

  if (isLoading) return <LoadingState />;
  if (error) return <ErrorState message={error.message} />;

  return (
    <div>
      {/* render data */}
    </div>
  );
}
```

## Before calling it done

- [ ] Role guard present, matching `rbac-enforcement`'s table for who should see this
- [ ] API call goes through `api/<domain>Api.js` — if the function doesn't exist there yet, add it first rather than calling `fetch` inline
- [ ] Loading state and error state both handled, not just the happy path (NFR-U03 applies to the frontend, not just API error messages)
- [ ] If this component triggers a backend action someone should be notified about, don't build a second notification UI — `NotificationBell.jsx` handles that centrally
- [ ] Add/verify the route in `routes/routeConfig.jsx` maps this component to the correct role(s)
