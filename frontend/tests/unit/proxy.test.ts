// @vitest-environment node
import { NextRequest } from "next/server";
import { beforeEach, describe, expect, it, vi } from "vitest";
import {
  COOKIE_ACCESS_TOKEN,
  COOKIE_REFRESH_ATTEMPTS,
  COOKIE_REFRESH_TOKEN,
  MAX_REFRESH_ATTEMPTS,
} from "@/src/constants";

const refreshBackendSession = vi.fn();
const backendCalls = vi.hoisted(() => ({
  headers: [] as Array<Record<string, string> | undefined>,
}));

vi.mock("@/shared/config/server", () => ({
  serverConfig: {
    apiBaseUrl: "http://backend.test",
    apiKey: "server-test-key",
    cfAccessClientId: "",
    cfAccessClientSecret: "",
    isProd: false,
    trustedClientIpHeader: "",
  },
}));

// Transport double: the backend refresh endpoint receives the refresh token.
vi.mock("@/shared/http/server", () => ({
  serverHttp: {
    post: async (
      endpoint: string,
      payload: { refreshToken: string },
      config?: { headers?: Record<string, string> }
    ) => {
      if (endpoint !== "/auth/refresh") throw new Error(endpoint);
      backendCalls.headers.push(config?.headers);
      const result = await refreshBackendSession(payload.refreshToken);
      return {
        status: result.status,
        data: result.body,
        headers: result.headers ?? {},
      };
    },
  },
}));

const { proxy } = await import("@/src/proxy");
const { resetSessionRotationCache } = await import(
  "@/features/auth/api/auth-server"
);

function jwt(expiresInSeconds: number, id = "t"): string {
  const encode = (value: object) =>
    Buffer.from(JSON.stringify(value)).toString("base64url");
  const exp = Math.floor(Date.now() / 1000) + expiresInSeconds;
  return `${encode({ alg: "HS256" })}.${encode({ exp, jti: id })}.sig`;
}

function request(
  path: string,
  cookies: Record<string, string>,
  extraHeaders: Record<string, string> = {}
) {
  const cookie = Object.entries(cookies)
    .map(([name, value]) => `${name}=${value}`)
    .join("; ");
  return new NextRequest(`http://app.test${path}`, {
    headers: { ...(cookie ? { cookie } : {}), ...extraHeaders },
  });
}

function rotated(accessToken: string, refreshToken: string) {
  return {
    ok: true,
    status: 200,
    body: {
      data: {
        session: { accessToken, refreshToken },
        user: {},
        tenant: null,
        tenantRole: null,
      },
      timestamp: "now",
    },
  };
}

function setCookie(response: Response, name: string) {
  return response.headers
    .getSetCookie()
    .find((value) => value.startsWith(`${name}=`));
}

function forwardedCookies(response: Response): string {
  return response.headers.get("x-middleware-request-cookie") ?? "";
}

describe("proxy session rotation", () => {
  beforeEach(() => {
    refreshBackendSession.mockReset();
    backendCalls.headers = [];
    resetSessionRotationCache();
  });

  it("passes a protected navigation through when the access cookie is fresh", async () => {
    const response = await proxy(
      request("/members", {
        [COOKIE_ACCESS_TOKEN]: jwt(600),
        [COOKIE_REFRESH_TOKEN]: jwt(3600),
      })
    );

    expect(refreshBackendSession).not.toHaveBeenCalled();
    expect(response.headers.get("location")).toBeNull();
    expect(response.headers.getSetCookie()).toEqual([]);
  });

  it("rotates a missing access cookie, sets both cookies and forwards them to the render", async () => {
    const refreshToken = jwt(3600, "old");
    const nextAccess = jwt(900, "new-at");
    const nextRefresh = jwt(3600, "new-rt");
    refreshBackendSession.mockResolvedValue(rotated(nextAccess, nextRefresh));

    const response = await proxy(
      request("/members", { [COOKIE_REFRESH_TOKEN]: refreshToken })
    );

    expect(refreshBackendSession).toHaveBeenCalledWith(refreshToken);
    expect(response.headers.get("location")).toBeNull();
    expect(setCookie(response, COOKIE_ACCESS_TOKEN)).toContain(nextAccess);
    expect(setCookie(response, COOKIE_REFRESH_TOKEN)).toContain(nextRefresh);
    expect(setCookie(response, COOKIE_REFRESH_TOKEN)).toMatch(/HttpOnly/i);
    expect(forwardedCookies(response)).toContain(
      `${COOKIE_ACCESS_TOKEN}=${nextAccess}`
    );
    expect(forwardedCookies(response)).toContain(
      `${COOKIE_REFRESH_TOKEN}=${nextRefresh}`
    );
  });

  it("rotates an expired access cookie", async () => {
    refreshBackendSession.mockResolvedValue(rotated(jwt(900), jwt(3600)));

    await proxy(
      request("/roles", {
        [COOKIE_ACCESS_TOKEN]: jwt(-5),
        [COOKIE_REFRESH_TOKEN]: jwt(3600),
      })
    );

    expect(refreshBackendSession).toHaveBeenCalledTimes(1);
  });

  it("shares one rotation between concurrent requests with the same refresh token", async () => {
    const refreshToken = jwt(3600, "shared");
    const nextAccess = jwt(900, "a1");
    const nextRefresh = jwt(3600, "r1");
    let resolve: (value: unknown) => void = () => {};
    refreshBackendSession.mockReturnValue(
      new Promise((done) => {
        resolve = done;
      })
    );

    const pending = [
      proxy(request("/members", { [COOKIE_REFRESH_TOKEN]: refreshToken })),
      proxy(request("/roles", { [COOKIE_REFRESH_TOKEN]: refreshToken })),
    ];
    resolve(rotated(nextAccess, nextRefresh));
    const responses = await Promise.all(pending);
    // A request sent before the browser stored the new cookies still reuses it.
    responses.push(
      await proxy(
        request("/settings", { [COOKIE_REFRESH_TOKEN]: refreshToken })
      )
    );

    expect(refreshBackendSession).toHaveBeenCalledTimes(1);
    for (const response of responses) {
      expect(response.headers.get("location")).toBeNull();
      expect(setCookie(response, COOKIE_REFRESH_TOKEN)).toContain(nextRefresh);
    }
  });

  it("clears the session and redirects to login when rotation is rejected", async () => {
    refreshBackendSession.mockResolvedValue({
      ok: false,
      status: 401,
      body: { errors: [{ code: "auth.InvalidOrExpiredRefreshToken" }] },
    });

    const response = await proxy(
      request("/members", { [COOKIE_REFRESH_TOKEN]: jwt(3600) })
    );

    expect(new URL(response.headers.get("location") ?? "").pathname).toBe("/");
    expect(setCookie(response, COOKIE_REFRESH_TOKEN)).toMatch(/Max-Age=0/i);
    expect(setCookie(response, COOKIE_ACCESS_TOKEN)).toMatch(/Max-Age=0/i);
  });

  it("clears the session when the backend no longer knows the user", async () => {
    refreshBackendSession.mockResolvedValue({
      ok: false,
      status: 404,
      body: { errors: [{ code: "users.UserNotFound", message: "x" }] },
    });

    const response = await proxy(
      request("/members", { [COOKIE_REFRESH_TOKEN]: jwt(3600) })
    );

    expect(new URL(response.headers.get("location") ?? "").pathname).toBe("/");
    expect(setCookie(response, COOKIE_REFRESH_TOKEN)).toMatch(/Max-Age=0/i);
  });

  it.each([
    ["rate limited", 429, "30", "30"],
    ["a server error", 500, undefined, "5"],
    ["a gateway error", 503, "600", "120"],
  ])(
    "keeps the session and answers 503 when rotation is %s",
    async (_label, status, upstreamRetryAfter, retryAfter) => {
      refreshBackendSession.mockResolvedValue({
        ok: false,
        status,
        body: { errors: [{ code: "common.TooManyRequests", message: "x" }] },
        headers: upstreamRetryAfter
          ? { "retry-after": upstreamRetryAfter }
          : {},
      });

      const response = await proxy(
        request("/members", { [COOKIE_REFRESH_TOKEN]: jwt(3600) })
      );

      expect(response.status).toBe(503);
      expect(response.headers.get("location")).toBeNull();
      expect(response.headers.get("retry-after")).toBe(retryAfter);
      expect(response.headers.getSetCookie()).toEqual([]);
      expect(await response.text()).toContain("Servicio no disponible");
    }
  );

  it("keeps the session when the backend is unreachable", async () => {
    refreshBackendSession.mockRejectedValue(new Error("connection refused"));

    const response = await proxy(
      request(
        "/members",
        { [COOKIE_REFRESH_TOKEN]: jwt(3600), NEXT_LOCALE: "en" },
        {}
      )
    );

    expect(response.status).toBe(503);
    expect(response.headers.getSetCookie()).toEqual([]);
    expect(await response.text()).toContain("Service briefly unavailable");
  });

  it("forwards the client IP and infrastructure key to the rotation", async () => {
    refreshBackendSession.mockResolvedValue(rotated(jwt(900), jwt(3600)));

    await proxy(
      request(
        "/members",
        { [COOKIE_REFRESH_TOKEN]: jwt(3600) },
        {
          "x-forwarded-for": "198.51.100.9, 203.0.113.7",
          "x-client-ip": "6.6.6.6",
        }
      )
    );

    expect(backendCalls.headers[0]).toMatchObject({
      "X-Client-IP": "203.0.113.7",
      "X-Api-Key": "server-test-key",
    });
  });

  it("replaces a browser-supplied X-Client-IP on the /api/v1 rewrite", async () => {
    const response = await proxy(
      request(
        "/api/v1/members",
        {},
        { "x-client-ip": "6.6.6.6", "x-forwarded-for": "203.0.113.7" }
      )
    );

    expect(response.headers.get("x-middleware-rewrite")).toBe(
      "http://backend.test/v1/members"
    );
    expect(response.headers.get("x-middleware-request-x-client-ip")).toBe(
      "203.0.113.7"
    );
    expect(response.headers.get("x-middleware-request-x-api-key")).toBe(
      "server-test-key"
    );
  });

  it("drops a browser-supplied X-Client-IP when no valid IP resolves", async () => {
    const response = await proxy(
      request("/api/v1/members", {}, { "x-client-ip": "6.6.6.6" })
    );

    expect(response.headers.get("x-middleware-request-x-client-ip")).toBeNull();
  });

  it("redirects a protected navigation without a valid refresh cookie", async () => {
    const response = await proxy(
      request("/members", { [COOKIE_REFRESH_TOKEN]: jwt(-10) })
    );

    expect(refreshBackendSession).not.toHaveBeenCalled();
    expect(new URL(response.headers.get("location") ?? "").pathname).toBe("/");
  });

  it("never rotates on public routes and keeps the redirect-loop guard", async () => {
    const bounced = await proxy(
      request("/", { [COOKIE_REFRESH_TOKEN]: jwt(3600) })
    );
    expect(new URL(bounced.headers.get("location") ?? "").pathname).toBe(
      "/members"
    );
    expect(setCookie(bounced, COOKIE_REFRESH_ATTEMPTS)).toContain(
      `${COOKIE_REFRESH_ATTEMPTS}=1`
    );

    const exhausted = await proxy(
      request("/", {
        [COOKIE_REFRESH_TOKEN]: jwt(3600),
        [COOKIE_REFRESH_ATTEMPTS]: String(MAX_REFRESH_ATTEMPTS),
      })
    );
    expect(exhausted.headers.get("location")).toBeNull();
    expect(setCookie(exhausted, COOKIE_REFRESH_TOKEN)).toMatch(/Max-Age=0/i);
    expect(refreshBackendSession).not.toHaveBeenCalled();
  });

  it("leaves internal API routes to their own handlers", async () => {
    const response = await proxy(
      request("/api/auth/refresh", { [COOKIE_REFRESH_TOKEN]: jwt(3600) })
    );

    expect(refreshBackendSession).not.toHaveBeenCalled();
    expect(response.headers.getSetCookie()).toEqual([]);
  });
});
