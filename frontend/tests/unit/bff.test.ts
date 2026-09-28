// @vitest-environment node
import { NextRequest } from "next/server";
import { beforeEach, describe, expect, it, vi } from "vitest";
import {
  backendHeadersFrom,
  mirrorBackendError,
  resolveClientIp,
} from "@/shared/http/bff";

const config = vi.hoisted(() => ({
  apiKey: "server-test-key",
  cfAccessClientId: "edge-id",
  cfAccessClientSecret: "edge-secret",
  trustedClientIpHeader: "",
}));

vi.mock("@/shared/config/server", () => ({ serverConfig: config }));

function withHeaders(headers: Record<string, string>) {
  return new NextRequest("http://localhost/api/auth/login", { headers });
}

describe("client IP for backend rate limits", () => {
  beforeEach(() => {
    config.trustedClientIpHeader = "";
  });

  it("replaces a browser-supplied X-Client-IP with the last forwarded hop", () => {
    const headers = backendHeadersFrom(
      withHeaders({
        "x-client-ip": "6.6.6.6",
        "x-forwarded-for": "6.6.6.6, 203.0.113.7",
      })
    );
    expect(headers["X-Client-IP"]).toBe("203.0.113.7");
    expect(headers["X-Api-Key"]).toBe("server-test-key");
  });

  it("honors the configured trusted edge header", () => {
    config.trustedClientIpHeader = "cf-connecting-ip";
    const request = withHeaders({
      "cf-connecting-ip": "2001:db8::1",
      "x-forwarded-for": "10.0.0.2",
    });
    expect(resolveClientIp(request)).toBe("2001:db8::1");
  });

  it("omits the header when the trusted edge header is missing", () => {
    config.trustedClientIpHeader = "cf-connecting-ip";
    const headers = backendHeadersFrom(
      withHeaders({ "x-forwarded-for": "203.0.113.7" })
    );
    expect(headers).not.toHaveProperty("X-Client-IP");
  });

  it.each(["not-an-ip", "300.1.1.1", "203.0.113.7:443", "", "1.2.3"])(
    "omits invalid values (%s)",
    (value) => {
      expect(resolveClientIp(withHeaders({ "x-forwarded-for": value }))).toBe(
        null
      );
    }
  );
});

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
