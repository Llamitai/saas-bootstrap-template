// @vitest-environment node
import { NextRequest } from "next/server";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { COOKIE_ACCESS_TOKEN, COOKIE_REFRESH_TOKEN } from "@/src/constants";

const backend = vi.hoisted(() => ({
  respond: vi.fn(),
  cookie: { value: "refresh-token" as string | undefined },
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

vi.mock("@/shared/http/server", () => ({
  serverHttp: {
    post: async () => {
      const result = await backend.respond();
      return {
        status: result.status,
        data: result.body,
        headers: result.headers ?? {},
      };
    },
  },
}));

const { POST } = await import("@/src/app/api/auth/refresh/route");
const { resetSessionRotationCache } = await import(
  "@/features/auth/api/auth-server"
);

// The handler reads cookies from the request, not from next/headers, so no
// request-scope mock is needed.
function call() {
  const headers = new Headers();
  if (backend.cookie.value) {
    headers.set("cookie", `${COOKIE_REFRESH_TOKEN}=${backend.cookie.value}`);
  }
  return POST(
    new NextRequest("http://app.test/api/auth/refresh", {
      method: "POST",
      headers,
    })
  );
}

function setCookies(response: Response) {
  return response.headers.getSetCookie();
}

describe("POST /api/auth/refresh", () => {
  beforeEach(() => {
    backend.respond.mockReset();
    backend.cookie.value = "refresh-token";
    resetSessionRotationCache();
  });

  it("rotates, sets both cookies and returns the access token", async () => {
    backend.respond.mockResolvedValue({
      status: 200,
      body: {
        data: {
          session: { accessToken: "new-at", refreshToken: "new-rt" },
          user: {},
          tenant: null,
          tenantRole: null,
        },
        timestamp: "now",
      },
    });

    const response = await call();

    expect(response.status).toBe(200);
    expect((await response.json()).accessToken).toBe("new-at");
    const cookies = setCookies(response).join("\n");
    expect(cookies).toContain(`${COOKIE_ACCESS_TOKEN}=new-at`);
    expect(cookies).toContain(`${COOKIE_REFRESH_TOKEN}=new-rt`);
  });

  it("answers 401 and clears the cookies when the token is rejected", async () => {
    backend.respond.mockResolvedValue({
      status: 401,
      body: { errors: [{ code: "auth.InvalidRefreshToken", message: "x" }] },
    });

    const response = await call();

    expect(response.status).toBe(401);
    expect(setCookies(response).join("\n")).toMatch(
      new RegExp(`${COOKIE_REFRESH_TOKEN}=;.*Max-Age=0`, "i")
    );
  });

  it("answers 401 and clears the cookies without a refresh cookie", async () => {
    backend.cookie.value = undefined;

    const response = await call();

    expect(response.status).toBe(401);
    expect(backend.respond).not.toHaveBeenCalled();
    expect(setCookies(response).length).toBeGreaterThan(0);
  });

  it("mirrors a rate limit with Retry-After and keeps the cookies", async () => {
    backend.respond.mockResolvedValue({
      status: 429,
      body: { errors: [{ code: "common.TooManyRequests", message: "x" }] },
      headers: { "retry-after": "12" },
    });

    const response = await call();

    expect(response.status).toBe(429);
    expect(response.headers.get("retry-after")).toBe("12");
    expect(setCookies(response)).toEqual([]);
  });

  it("keeps the cookies when the backend is unreachable", async () => {
    backend.respond.mockRejectedValue(new Error("connection refused"));

    const response = await call();

    expect(response.status).toBe(502);
    expect(setCookies(response)).toEqual([]);
  });
});
