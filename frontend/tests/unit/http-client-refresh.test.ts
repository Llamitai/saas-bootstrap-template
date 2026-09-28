import axios, { AxiosError, type InternalAxiosRequestConfig } from "axios";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { configureAuthHeaderContext } from "@/shared/http/auth-context";
import { authHttp } from "@/shared/http/client";

const session = {
  clearSession: vi.fn(),
  setAccessToken: vi.fn(),
};

function reply(config: InternalAxiosRequestConfig, status: number) {
  const response = {
    status,
    statusText: "",
    headers: {},
    config,
    data: status === 200 ? { accessToken: "new-at" } : { errors: [] },
  };
  if (status >= 400) {
    return Promise.reject(
      new AxiosError("failed", "ERR", config, null, response)
    );
  }
  return Promise.resolve(response);
}

function routeRefreshTo(refreshStatus: number) {
  let apiCalls = 0;
  const adapter = (config: InternalAxiosRequestConfig) => {
    if (config.url === "/api/auth/refresh") return reply(config, refreshStatus);
    apiCalls += 1;
    return reply(config, apiCalls === 1 ? 401 : 200);
  };
  axios.defaults.adapter = adapter;
  authHttp.defaults.adapter = adapter;
}

describe("authHttp refresh interceptor", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    configureAuthHeaderContext(() => ({
      tenantSlug: null,
      accessToken: "old-at",
      ...session,
    }));
    vi.stubGlobal("location", { href: "/members" });
  });

  it("retries the request with the rotated token", async () => {
    routeRefreshTo(200);

    const response = await authHttp.get("/v1/members");

    expect(response.status).toBe(200);
    expect(session.setAccessToken).toHaveBeenCalledWith("new-at");
    expect(session.clearSession).not.toHaveBeenCalled();
  });

  it.each([429, 502, 503])(
    "surfaces the error without signing out when refresh answers %s",
    async (status) => {
      routeRefreshTo(status);

      await expect(authHttp.get("/v1/members")).rejects.toMatchObject({
        response: { status: 401 },
      });
      expect(session.clearSession).not.toHaveBeenCalled();
      expect(window.location.href).toBe("/members");
    }
  );

  it("signs out when refresh rejects the session", async () => {
    routeRefreshTo(401);

    await expect(authHttp.get("/v1/members")).rejects.toBeInstanceOf(Error);
    expect(session.clearSession).toHaveBeenCalledTimes(1);
    expect(window.location.href).toBe("/");
  });
});
