import { test, describe, beforeEach, afterEach } from "node:test";
import assert from "node:assert/strict";
import {
  apiClient,
  getStoredToken,
  setStoredToken,
  setSessionClearHandler,
  setTokenRefreshHandler,
  clearSession,
} from "../src/api/client.js";

describe("apiClient Silent Refresh (US-Auth / Client Integration)", () => {
  const originalFetch = globalThis.fetch;

  beforeEach(() => {
    clearSession();
    setStoredToken("");
    setSessionClearHandler(null);
    setTokenRefreshHandler(null);
  });

  afterEach(() => {
    globalThis.fetch = originalFetch;
    clearSession();
    setStoredToken("");
    setSessionClearHandler(null);
    setTokenRefreshHandler(null);
  });

  test("1. A 401 triggers exactly one refresh and a retry with the new access token", async () => {
    setStoredToken("old-access-token");

    let refreshCalls = 0;
    let taskCalls = 0;
    let tokenRefreshedCallbackCalled = false;

    setTokenRefreshHandler((newToken) => {
      tokenRefreshedCallbackCalled = true;
      assert.equal(newToken, "fresh-token-abc");
    });

    globalThis.fetch = async (url, options) => {
      const urlStr = String(url);

      if (urlStr.includes("/api/v1/auth/refresh")) {
        refreshCalls++;
        assert.equal(options.method, "POST");
        assert.equal(options.credentials, "include");
        return new Response(
          JSON.stringify({ access_token: "fresh-token-abc", token_type: "bearer" }),
          {
            status: 200,
            headers: { "Content-Type": "application/json" },
          }
        );
      }

      if (urlStr.includes("/api/v1/tasks/101")) {
        taskCalls++;
        const authHeader = options.headers?.Authorization;
        if (taskCalls === 1) {
          assert.equal(authHeader, "Bearer old-access-token");
          return new Response(JSON.stringify({ detail: "Token expired" }), {
            status: 401,
            headers: { "Content-Type": "application/json" },
          });
        }
        if (taskCalls === 2) {
          assert.equal(authHeader, "Bearer fresh-token-abc");
          return new Response(
            JSON.stringify({ task_id: 101, title: "Refreshed Task" }),
            {
              status: 200,
              headers: { "Content-Type": "application/json" },
            }
          );
        }
      }

      return new Response("Not found", { status: 404 });
    };

    const result = await apiClient.get("/api/v1/tasks/101");

    assert.deepEqual(result, { task_id: 101, title: "Refreshed Task" });
    assert.equal(refreshCalls, 1, "Expected exactly 1 refresh call");
    assert.equal(taskCalls, 2, "Expected 2 task calls (initial + retry)");
    assert.equal(getStoredToken(), "fresh-token-abc");
    assert.equal(tokenRefreshedCallbackCalled, true);
  });

  test("2. Two parallel 401s share a single in-flight refresh promise and both retry", async () => {
    setStoredToken("expiring-token-xyz");

    let refreshCalls = 0;
    const taskCallCounts = { task1: 0, task2: 0 };

    globalThis.fetch = async (url, options) => {
      const urlStr = String(url);

      if (urlStr.includes("/api/v1/auth/refresh")) {
        refreshCalls++;
        // Small artificial delay to ensure concurrent requests overlap
        await new Promise((resolve) => setTimeout(resolve, 20));
        return new Response(
          JSON.stringify({ access_token: "shared-refreshed-token", token_type: "bearer" }),
          {
            status: 200,
            headers: { "Content-Type": "application/json" },
          }
        );
      }

      if (urlStr.includes("/api/v1/tasks/1")) {
        taskCallCounts.task1++;
        const authHeader = options.headers?.Authorization;
        if (taskCallCounts.task1 === 1) {
          assert.equal(authHeader, "Bearer expiring-token-xyz");
          return new Response(JSON.stringify({ detail: "Token expired" }), {
            status: 401,
            headers: { "Content-Type": "application/json" },
          });
        }
        return new Response(JSON.stringify({ task_id: 1, title: "Task 1" }), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        });
      }

      if (urlStr.includes("/api/v1/tasks/2")) {
        taskCallCounts.task2++;
        const authHeader = options.headers?.Authorization;
        if (taskCallCounts.task2 === 1) {
          assert.equal(authHeader, "Bearer expiring-token-xyz");
          return new Response(JSON.stringify({ detail: "Token expired" }), {
            status: 401,
            headers: { "Content-Type": "application/json" },
          });
        }
        return new Response(JSON.stringify({ task_id: 2, title: "Task 2" }), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        });
      }

      return new Response("Not found", { status: 404 });
    };

    const [res1, res2] = await Promise.all([
      apiClient.get("/api/v1/tasks/1"),
      apiClient.get("/api/v1/tasks/2"),
    ]);

    assert.deepEqual(res1, { task_id: 1, title: "Task 1" });
    assert.deepEqual(res2, { task_id: 2, title: "Task 2" });
    assert.equal(refreshCalls, 1, "Concurrent requests must share exactly 1 refresh call");
    assert.equal(taskCallCounts.task1, 2);
    assert.equal(taskCallCounts.task2, 2);
    assert.equal(getStoredToken(), "shared-refreshed-token");
  });

  test("3. A failed refresh (401 or 423) clears the session and stored token", async () => {
    setStoredToken("dead-token-123");

    let sessionCleared = false;
    setSessionClearHandler(() => {
      sessionCleared = true;
    });

    let refreshCalled = false;

    globalThis.fetch = async (url) => {
      const urlStr = String(url);

      if (urlStr.includes("/api/v1/auth/refresh")) {
        refreshCalled = true;
        return new Response(
          JSON.stringify({ detail: "Invalid or expired refresh token" }),
          {
            status: 401,
            headers: { "Content-Type": "application/json" },
          }
        );
      }

      // Initial request returns 401
      return new Response(JSON.stringify({ detail: "Signature has expired" }), {
        status: 401,
        headers: { "Content-Type": "application/json" },
      });
    };

    await assert.rejects(
      async () => {
        await apiClient.get("/api/v1/tasks/secure");
      },
      (err) => {
        assert.ok(err);
        return true;
      }
    );

    assert.equal(refreshCalled, true);
    assert.equal(getStoredToken(), "", "Stored token must be cleared on failed refresh");
    assert.equal(sessionCleared, true, "Session clear handler must be called");
  });
});
