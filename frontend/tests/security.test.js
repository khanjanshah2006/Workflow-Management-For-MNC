import { test, describe, beforeEach, afterEach } from "node:test";
import assert from "node:assert/strict";
import { ApiError, setStoredToken } from "../src/api/client.js";
import { authApi } from "../src/api/authApi.js";
import { adminApi } from "../src/api/adminApi.js";
import {
  classifyLoginResponse,
  classifyLoginError,
  submitPasswordLogin,
  getRetryAfterSeconds,
  formatThrottleMessage,
  isMfaTokenRejected,
  INVALID_CREDENTIALS_MESSAGE,
  LOCKED_SUBMIT_COOLDOWN_SECONDS,
  DEFAULT_RETRY_AFTER_SECONDS,
  MFA_CHALLENGE_ROUTE,
  MFA_SETUP_ROUTE,
} from "../src/auth/loginFlow.js";
import {
  getPendingMfa,
  setPendingMfa,
  clearPendingMfa,
  isPendingMfaExpired,
  getTokenExpiryMs,
  MFA_STEP_CHALLENGE,
  MFA_STEP_SETUP,
} from "../src/auth/pendingMfa.js";
import { buildOtpauthUri, formatOtpSecret, normalizeOtpSecret } from "../src/auth/otpauth.js";
import { isAdminMfaEnforced, isMfaRequiredForRole } from "../src/auth/mfaPolicy.js";
import {
  getLockedAccounts,
  mergeLockState,
  parseServerTimestamp,
  formatLockedUntil,
} from "../src/features/admin/lockState.js";

const originalFetch = globalThis.fetch;
const originalLocalStorage = globalThis.localStorage;
const originalSessionStorage = globalThis.sessionStorage;

function jsonResponse(body, status = 200, headers = {}) {
  return new Response(body === null ? null : JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json", ...headers },
  });
}

/** Builds an unsigned JWT-shaped token with the given payload. */
function fakeJwt(payload) {
  const encode = (obj) =>
    Buffer.from(JSON.stringify(obj)).toString("base64url");
  return `${encode({ alg: "HS256", typ: "JWT" })}.${encode(payload)}.signature`;
}

/** Storage stub that records every write. */
function recordingStorage() {
  const data = new Map();
  const writes = [];
  return {
    writes,
    getItem: (key) => (data.has(key) ? data.get(key) : null),
    setItem: (key, value) => {
      writes.push([key, String(value)]);
      data.set(key, String(value));
    },
    removeItem: (key) => data.delete(key),
    clear: () => data.clear(),
  };
}

function restoreGlobals() {
  globalThis.fetch = originalFetch;
  globalThis.localStorage = originalLocalStorage;
  globalThis.sessionStorage = originalSessionStorage;
  setStoredToken("");
  clearPendingMfa();
}

describe("S9-FE-2 Login response routing (US-31, US-48, US-49)", () => {
  afterEach(restoreGlobals);

  test("401 shows the unchanged invalid-credentials message", () => {
    const outcome = classifyLoginError(new ApiError("Incorrect email or password", 401));
    assert.deepEqual(outcome, { type: "invalid", message: INVALID_CREDENTIALS_MESSAGE });
    assert.equal(INVALID_CREDENTIALS_MESSAGE, "Invalid email or password");
  });

  test("423 shows the backend lock detail and a 30 s submit cool-down", () => {
    const detail = "Account locked. Try again after 14:35 UTC or contact an administrator.";
    const outcome = classifyLoginError(new ApiError(detail, 423));
    assert.equal(outcome.type, "locked");
    assert.equal(outcome.message, detail);
    assert.equal(outcome.cooldownSeconds, 30);
    assert.equal(LOCKED_SUBMIT_COOLDOWN_SECONDS, 30);
  });

  test("429 reads Retry-After from the response headers exposed on ApiError", async () => {
    globalThis.fetch = async () =>
      jsonResponse({ detail: "Too many login attempts. Try again in a minute." }, 429, {
        "Retry-After": "17",
      });

    const err = await authApi
      .login({ email: "sarah.connor@company.com", password: "wrong-password" })
      .then(() => null, (e) => e);

    assert.ok(err instanceof ApiError);
    assert.equal(err.status, 429);
    assert.ok(err.headers, "ApiError.headers should be set");
    assert.equal(err.headers.get("retry-after"), "17");

    const outcome = classifyLoginError(err);
    assert.deepEqual(outcome, { type: "throttled", retryAfterSeconds: 17 });
    assert.equal(formatThrottleMessage(17), "Too many sign-in attempts. Try again in 17 seconds.");
    assert.equal(formatThrottleMessage(1), "Too many sign-in attempts. Try again in 1 second.");
  });

  test("429 without a readable Retry-After falls back to the default wait", () => {
    const outcome = classifyLoginError(new ApiError("Too many", 429, null, new Headers()));
    assert.deepEqual(outcome, { type: "throttled", retryAfterSeconds: DEFAULT_RETRY_AFTER_SECONDS });
  });

  test("Retry-After accepts delta-seconds, HTTP-dates and plain objects", () => {
    const now = Date.parse("2026-11-23T10:00:00Z");
    assert.equal(getRetryAfterSeconds(new Headers({ "Retry-After": "42" }), 60, now), 42);
    assert.equal(
      getRetryAfterSeconds(new Headers({ "Retry-After": "Mon, 23 Nov 2026 10:00:30 GMT" }), 60, now),
      30
    );
    assert.equal(getRetryAfterSeconds({ "retry-after": "5" }, 60, now), 5);
    assert.equal(getRetryAfterSeconds({ "Retry-After": "not-a-number" }, 60, now), 60);
    assert.equal(getRetryAfterSeconds(null, 60, now), 60);
  });

  test("mfa_required routes to /login/mfa", () => {
    const outcome = classifyLoginResponse({ mfa_required: true, mfa_token: "pending-token" });
    assert.deepEqual(outcome, {
      type: MFA_STEP_CHALLENGE,
      mfaToken: "pending-token",
      route: MFA_CHALLENGE_ROUTE,
    });
    assert.equal(MFA_CHALLENGE_ROUTE, "/login/mfa");
  });

  test("mfa_setup_required routes to /login/mfa-setup", () => {
    const outcome = classifyLoginResponse({ mfa_setup_required: true, mfa_token: "setup-token" });
    assert.deepEqual(outcome, {
      type: MFA_STEP_SETUP,
      mfaToken: "setup-token",
      route: MFA_SETUP_ROUTE,
    });
    assert.equal(MFA_SETUP_ROUTE, "/login/mfa-setup");
  });

  test("a normal token response is treated as signed in", () => {
    assert.deepEqual(
      classifyLoginResponse({ access_token: "a", refresh_token: "r", mfa_required: false }),
      { type: "authenticated" }
    );
    // A flag without a token cannot start an MFA step
    assert.deepEqual(classifyLoginResponse({ mfa_required: true }), { type: "authenticated" });
  });

  test("submitPasswordLogin holds the MFA token in memory for the next screen", async () => {
    const result = await submitPasswordLogin(
      { email: "admin@company.com", password: "secret123" },
      { login: async () => ({ mfa_setup_required: true, mfa_token: "setup-token" }) }
    );
    assert.equal(result.outcome.type, MFA_STEP_SETUP);
    assert.deepEqual(
      { token: getPendingMfa().token, step: getPendingMfa().step, email: getPendingMfa().email },
      { token: "setup-token", step: MFA_STEP_SETUP, email: "admin@company.com" }
    );
  });

  test("submitPasswordLogin clears an older pending token and rethrows API errors", async () => {
    setPendingMfa({ token: "old", step: MFA_STEP_CHALLENGE });
    const locked = new ApiError("Account locked.", 423);
    await assert.rejects(
      submitPasswordLogin({ email: "a@b.co", password: "x" }, { login: async () => { throw locked; } }),
      (err) => err === locked
    );
    assert.equal(getPendingMfa(), null);
  });

  test("an expired or rejected MFA token is told apart from a wrong code", () => {
    assert.equal(isMfaTokenRejected(new ApiError("Invalid or expired MFA token", 401)), true);
    assert.equal(isMfaTokenRejected(new ApiError("Invalid token type for MFA challenge", 401)), true);
    assert.equal(isMfaTokenRejected(new ApiError("Could not validate credentials", 401)), true);
    assert.equal(isMfaTokenRejected(new ApiError("Invalid 6-digit MFA code", 401)), false);
    assert.equal(isMfaTokenRejected(new ApiError("Account locked.", 423)), false);
  });

  test("MFA login 401 is reported as-is instead of triggering a silent refresh", async () => {
    setStoredToken("stale-access-token");
    const calls = [];
    globalThis.fetch = async (url) => {
      calls.push(String(url));
      return jsonResponse({ detail: "Invalid 6-digit MFA code" }, 401);
    };
    const err = await authApi.mfaLogin("pending", "123456").then(() => null, (e) => e);
    assert.equal(err.status, 401);
    assert.equal(calls.length, 1);
    assert.ok(calls[0].endsWith("/api/v1/auth/mfa/login"));
  });
});

describe("S9-FE-2 MFA token never reaches persistent storage", () => {
  let local;
  let session;

  beforeEach(() => {
    local = recordingStorage();
    session = recordingStorage();
    globalThis.localStorage = local;
    globalThis.sessionStorage = session;
  });

  afterEach(restoreGlobals);

  const MFA_TOKEN = fakeJwt({ sub: "acc-1", type: "mfa_pending", exp: 4102444800 });

  for (const [flag, step] of [
    ["mfa_required", MFA_STEP_CHALLENGE],
    ["mfa_setup_required", MFA_STEP_SETUP],
  ]) {
    test(`${flag}: token is kept in memory only`, async () => {
      globalThis.fetch = async (url) => {
        assert.ok(String(url).endsWith("/api/v1/auth/login"));
        return jsonResponse({ [flag]: true, mfa_token: MFA_TOKEN, access_token: null });
      };

      await submitPasswordLogin({ email: "admin@company.com", password: "Admin@123" });

      assert.equal(getPendingMfa()?.token, MFA_TOKEN);
      assert.equal(getPendingMfa()?.step, step);

      for (const [name, store] of [["localStorage", local], ["sessionStorage", session]]) {
        const leaked = store.writes.filter(([, value]) => value.includes(MFA_TOKEN));
        assert.deepEqual(leaked, [], `${name} must not receive the MFA token`);
      }
      assert.equal(local.getItem("wms_access_token"), null);
    });
  }

  test("forced setup calls use the MFA token as bearer without storing it", async () => {
    const seen = [];
    globalThis.fetch = async (url, options) => {
      seen.push({ url: String(url), auth: options.headers.Authorization, body: options.body });
      if (String(url).endsWith("/mfa/setup")) {
        return jsonResponse({ secret: "JBSWY3DPEHPK3PXP", provisioning_uri: "otpauth://x" });
      }
      return jsonResponse({ message: "ok", access_token: "access", refresh_token: "refresh" });
    };

    await authApi.mfaSetup(MFA_TOKEN);
    await authApi.mfaVerify("123456", MFA_TOKEN);

    assert.deepEqual(
      seen.map((s) => [s.url.replace(/^https?:\/\/[^/]+/, ""), s.auth]),
      [
        ["/api/v1/auth/mfa/setup", `Bearer ${MFA_TOKEN}`],
        ["/api/v1/auth/mfa/verify", `Bearer ${MFA_TOKEN}`],
      ]
    );
    assert.equal(seen[1].body, JSON.stringify({ code: "123456" }));
    assert.deepEqual(local.writes, []);
    assert.deepEqual(session.writes, []);
  });

  test("pending token expiry comes from its exp claim", () => {
    const exp = Math.floor(Date.parse("2026-11-23T10:05:00Z") / 1000);
    const token = fakeJwt({ sub: "acc-1", type: "mfa_pending", exp });
    assert.equal(getTokenExpiryMs(token), exp * 1000);

    setPendingMfa({ token, step: MFA_STEP_CHALLENGE });
    const pending = getPendingMfa();
    assert.equal(isPendingMfaExpired(pending, Date.parse("2026-11-23T10:04:59Z")), false);
    assert.equal(isPendingMfaExpired(pending, Date.parse("2026-11-23T10:05:00Z")), true);
    assert.equal(isPendingMfaExpired(null), true);
    assert.equal(getTokenExpiryMs("not-a-jwt"), null);
  });
});

describe("S9-FE-2 otpauth URI builder (US-31)", () => {
  test("builds the WorkSphere provisioning URI", () => {
    assert.equal(
      buildOtpauthUri({ email: "admin@company.com", secret: "JBSWY3DPEHPK3PXP" }),
      "otpauth://totp/WorkSphere:admin%40company.com?secret=JBSWY3DPEHPK3PXP&issuer=WorkSphere"
    );
  });

  test("normalizes the secret and encodes the label", () => {
    assert.equal(normalizeOtpSecret("jbsw y3dp-ehpk 3pxp"), "JBSWY3DPEHPK3PXP");
    assert.equal(
      buildOtpauthUri({ email: " first last@company.com ", secret: "jbsw y3dp" }),
      "otpauth://totp/WorkSphere:first%20last%40company.com?secret=JBSWY3DP&issuer=WorkSphere"
    );
    assert.equal(buildOtpauthUri({ email: "a@b.co", secret: "" }), "");
  });

  test("formats the secret in groups of four for manual entry", () => {
    assert.equal(formatOtpSecret("JBSWY3DPEHPK3PXP"), "JBSW Y3DP EHPK 3PXP");
    assert.equal(formatOtpSecret("ABCDEF"), "ABCD EF");
  });
});

describe("S9-FE-2 Admin MFA policy label", () => {
  test("is off unless VITE_ENFORCE_ADMIN_MFA is true", () => {
    assert.equal(isAdminMfaEnforced({}), false);
    assert.equal(isAdminMfaEnforced({ VITE_ENFORCE_ADMIN_MFA: "false" }), false);
    assert.equal(isAdminMfaEnforced({ VITE_ENFORCE_ADMIN_MFA: "TRUE" }), true);
  });

  test("applies only to ADMIN and SYSTEM_ADMIN", () => {
    assert.equal(isMfaRequiredForRole("ADMIN", true), true);
    assert.equal(isMfaRequiredForRole("system_admin", true), true);
    assert.equal(isMfaRequiredForRole("EMPLOYEE", true), false);
    assert.equal(isMfaRequiredForRole("ADMIN", false), false);
  });
});

describe("S9-FE-2 Lock state merged from alerts into user rows (US-48, US-49)", () => {
  const now = Date.parse("2026-11-23T14:20:00Z");
  const alerts = [
    {
      id: "ALT-LOCK-1",
      alert_type: "ACCOUNT_LOCKED",
      account_id: "acc-sarah",
      attempted_email: "sarah.connor@company.com",
      first_timestamp: "2026-11-23T14:20:00",
      last_timestamp: "2026-11-23T14:35:00",
    },
    {
      id: "ALT-LOCK-OLD",
      alert_type: "ACCOUNT_LOCKED",
      account_id: "acc-expired",
      last_timestamp: "2026-11-23T14:00:00Z",
    },
    {
      id: "ALT-ACC-1",
      alert_type: "FAILED_LOGIN_BURST",
      account_id: "acc-john",
      last_timestamp: "2026-11-23T14:30:00Z",
    },
  ];

  test("only unexpired ACCOUNT_LOCKED alerts produce locks", () => {
    const locked = getLockedAccounts(alerts, now);
    assert.deepEqual([...locked.keys()], ["acc-sarah"]);
    assert.equal(locked.get("acc-sarah").lockedUntil, Date.parse("2026-11-23T14:35:00Z"));
    assert.equal(locked.get("acc-sarah").email, "sarah.connor@company.com");
  });

  test("merges is_locked and locked_until into the matching rows", () => {
    const users = [
      { account_id: "acc-sarah", email: "sarah.connor@company.com", is_active: true },
      { account_id: "acc-john", email: "john@company.com", is_active: true },
    ];
    const merged = mergeLockState(users, getLockedAccounts(alerts, now));
    assert.equal(merged[0].is_locked, true);
    assert.equal(merged[0].locked_until, "2026-11-23T14:35:00.000Z");
    assert.equal(merged[1].is_locked, false);
    assert.equal(merged[1].locked_until, null);
    // Original rows are untouched
    assert.equal("is_locked" in users[0], false);
  });

  test("handles missing data safely", () => {
    assert.equal(getLockedAccounts(null, now).size, 0);
    assert.deepEqual(mergeLockState(null, new Map()), []);
    assert.equal(parseServerTimestamp(""), null);
    assert.equal(parseServerTimestamp("2026-11-23T14:35:00+00:00"), Date.parse("2026-11-23T14:35:00Z"));
    assert.equal(formatLockedUntil(null), "");
  });

  test("formats the lock expiry as HH:MM", () => {
    const local = new Date(2026, 10, 23, 9, 5);
    assert.equal(formatLockedUntil(local.getTime()), "09:05");
  });
});

describe("S9-FE-2 Unlock and revoke API calls (US-45, US-48)", () => {
  beforeEach(() => {
    setStoredToken("admin-access-token");
  });

  afterEach(restoreGlobals);

  test("unlockAccount POSTs to /admin/users/{id}/unlock", async () => {
    let captured;
    globalThis.fetch = async (url, options) => {
      captured = { url: String(url), method: options.method, auth: options.headers.Authorization };
      return jsonResponse({ account_id: "acc-sarah", email: "sarah.connor@company.com" });
    };

    const result = await adminApi.unlockAccount("acc-sarah");

    assert.ok(captured.url.endsWith("/api/v1/admin/users/acc-sarah/unlock"));
    assert.equal(captured.method, "POST");
    assert.equal(captured.auth, "Bearer admin-access-token");
    assert.equal(result.email, "sarah.connor@company.com");
  });

  test("unlockAccount keeps the 409 status when the account is not locked", async () => {
    globalThis.fetch = async () => jsonResponse({ detail: "Account is not locked" }, 409);
    await assert.rejects(adminApi.unlockAccount("acc-john"), (err) => {
      assert.ok(err instanceof ApiError);
      assert.equal(err.status, 409);
      assert.equal(err.message, "Account is not locked");
      return true;
    });
  });

  test("revokeElevatedGrant DELETEs /admin/elevated-access/{grant_id}", async () => {
    let captured;
    globalThis.fetch = async (url, options) => {
      captured = { url: String(url), method: options.method };
      return jsonResponse({ id: 7, revoked_at: "2026-11-23T14:00:00Z" });
    };

    const result = await adminApi.revokeElevatedGrant(7);

    assert.ok(captured.url.endsWith("/api/v1/admin/elevated-access/7"));
    assert.equal(captured.method, "DELETE");
    assert.equal(result.id, 7);
  });

  test("revokeElevatedGrant keeps the 409 status for an already revoked or expired grant", async () => {
    globalThis.fetch = async () =>
      jsonResponse({ detail: "Grant is already revoked or expired" }, 409);
    await assert.rejects(adminApi.revokeElevatedGrant(7), (err) => {
      assert.ok(err instanceof ApiError);
      assert.equal(err.status, 409);
      assert.equal(err.message, "Grant is already revoked or expired");
      return true;
    });
  });
});
