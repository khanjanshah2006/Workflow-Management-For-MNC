import { useCallback, useEffect, useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import { clearPendingMfa, getPendingMfa, isPendingMfaExpired } from "../../auth/pendingMfa";
import { getHomeRouteForRole } from "../../auth/session";
import { ROUTES } from "../../routes";

/**
 * Shared navigation for the public MFA screens (/login/mfa and /login/mfa-setup).
 * - Reads the in-memory pending MFA token for the given step.
 * - Sends the user back to /login when the token is missing, or with
 *   "Your sign-in timed out" once it expires.
 *
 * @param {string} step MFA_STEP_CHALLENGE or MFA_STEP_SETUP
 */
export function useMfaNavigation(step) {
  const navigate = useNavigate();
  const location = useLocation();
  // Captured once: completing the sign-in clears the store, and this screen must not
  // bounce to /login on the re-render that follows.
  const [pending] = useState(() => getPendingMfa());
  const isValid = Boolean(pending && pending.step === step);

  const backToLogin = useCallback(
    (state) => {
      const email = pending?.email;
      clearPendingMfa();
      navigate(ROUTES.LOGIN, {
        replace: true,
        state: { ...(email ? { email } : {}), ...(state || {}) },
      });
    },
    [navigate, pending]
  );

  const timedOut = useCallback(() => backToLogin({ notice: "timeout" }), [backToLogin]);
  const locked = useCallback((message) => backToLogin({ lockMessage: message }), [backToLogin]);

  const finish = useCallback(
    (user) => {
      const requestedFrom = location.state?.from?.pathname;
      const target =
        requestedFrom && !requestedFrom.startsWith(ROUTES.LOGIN)
          ? requestedFrom
          : getHomeRouteForRole(user);
      navigate(target, { replace: true });
    },
    [location.state, navigate]
  );

  // Leave the screen when the pending token expires while it is open.
  const expiresAt = isValid ? pending.expiresAt : null;
  useEffect(() => {
    if (!isValid) return undefined;
    if (isPendingMfaExpired(pending)) {
      timedOut();
      return undefined;
    }
    if (typeof expiresAt !== "number") return undefined;
    const timer = setTimeout(timedOut, Math.max(0, expiresAt - Date.now()));
    return () => clearTimeout(timer);
  }, [isValid, pending, expiresAt, timedOut]);

  return { pending: isValid ? pending : null, backToLogin, timedOut, locked, finish };
}

export default useMfaNavigation;
