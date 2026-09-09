// @vitest-environment node
import { NextRequest } from "next/server";
import { describe, expect, it, vi } from "vitest";
import { backendHeadersFrom, mirrorBackendError } from "@/shared/http/bff";

vi.mock("@/shared/config/server", () => ({
  serverConfig: {
    apiKey: "server-test-key",
    cfAccessClientId: "edge-id",
    cfAccessClientSecret: "edge-secret",
  },
}));

describe("BFF transport contract", () => {
  it("preserves authorization and tenant, and uses server infrastructure credentials", () => {
    const request = new NextRequest("http://localhost/api/v1/members", {
      headers: {
        authorization: "Bearer session",
        "x-tenant": "tenant-a",
        "x-api-key": "untrusted-browser-key",
      },
    });
    expect(backendHeadersFrom(request)).toEqual({
      Authorization: "Bearer session",
      "X-Tenant": "tenant-a",
      "X-Api-Key": "server-test-key",
      "CF-Access-Client-Id": "edge-id",
      "CF-Access-Client-Secret": "edge-secret",
    });
  });
  it("mirrors upstream status and validation envelope", async () => {
    const body = {
      errors: [{ code: "tenants.NotAllowed", message: "Denied" }],
      validation: null,
    };
    const response = mirrorBackendError({
      response: { status: 403, data: body },
    });
    expect(response.status).toBe(403);
    expect(await response.json()).toEqual(body);
  });
  it("reports unavailable upstream as a recoverable gateway error", async () => {
    const response = mirrorBackendError(new Error("connection refused"));
    expect(response.status).toBe(502);
    expect((await response.json()).errors[0].code).toBe(
      "bff.upstream_unreachable"
    );
  });
});
