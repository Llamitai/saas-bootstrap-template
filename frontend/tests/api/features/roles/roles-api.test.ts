import { beforeEach, describe, expect, it, vi } from "vitest";
import { TenantRoleStatus } from "@/entities/tenant";
import type { TenantRole } from "@/entities/tenant-role";
import { getRoles, updateRole } from "@/features/roles/api/roles";

// Request functions go through the shared axios instances, so tests replace
// the transport at the module boundary instead of spinning up a network.
const httpMock = vi.hoisted(() => ({
  get: vi.fn(),
  post: vi.fn(),
  put: vi.fn(),
  delete: vi.fn(),
}));

vi.mock("@/shared/http/client", () => ({
  authHttp: httpMock,
  localHttp: httpMock,
}));

const role: TenantRole = {
  uuid: "role-1",
  name: "Compliance reviewer",
  slug: "compliance-reviewer",
  status: TenantRoleStatus.ACTIVE,
  permissions: [
    { code: "tenant_settings.view", label: "View tenant settings" },
  ],
};

describe("roles api", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("getRoles unwraps the data envelope from the roles endpoint", async () => {
    httpMock.get.mockResolvedValue({ data: { data: [role] } });

    const roles = await getRoles();

    expect(httpMock.get).toHaveBeenCalledWith("/v1/tenants/roles");
    expect(roles).toEqual([role]);
  });

  it("updateRole encodes the uuid into the resource path", async () => {
    httpMock.put.mockResolvedValue({ data: { data: role } });

    const updated = await updateRole("role/1", { name: "Auditor" });

    expect(httpMock.put).toHaveBeenCalledWith("/v1/tenants/roles/role%2F1", {
      name: "Auditor",
    });
    expect(updated).toEqual(role);
  });

  it("propagates transport errors to the caller", async () => {
    httpMock.get.mockRejectedValue(new Error("network down"));

    await expect(getRoles()).rejects.toThrow("network down");
  });
});
