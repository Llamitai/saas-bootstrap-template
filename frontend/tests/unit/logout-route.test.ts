// @vitest-environment node
import { NextRequest } from "next/server";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { COOKIE_ACCESS_TOKEN, COOKIE_REFRESH_TOKEN } from "@/src/constants";

const backend = vi.hoisted(() => ({ post: vi.fn() }));

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
    post: async (url: string, body: unknown) => {
      backend.post(url, body);
      return {
        status: 200,
        data: { data: { status: "SUCCESS" } },
        headers: {},
      };
    },
  },
}));

const { POST } = await import("@/src/app/api/auth/logout/route");

describe("POST /api/auth/logout", () => {
  beforeEach(() => backend.post.mockReset());

  it("revokes the refresh token from the request cookie and clears the session", async () => {
    const response = await POST(
      new NextRequest("http://app.test/api/auth/logout", {
        method: "POST",
        headers: {
          cookie: `${COOKIE_REFRESH_TOKEN}=rt-1; ${COOKIE_ACCESS_TOKEN}=at-1`,
        },
      })
    );

    expect(response.status).toBe(200);
    expect(backend.post).toHaveBeenCalledWith("/auth/logout", {
      refreshToken: "rt-1",
    });
    const cleared = response.headers.getSetCookie().join("\n");
    expect(cleared).toContain(`${COOKIE_REFRESH_TOKEN}=;`);
    expect(cleared).toContain(`${COOKIE_ACCESS_TOKEN}=;`);
  });
});
