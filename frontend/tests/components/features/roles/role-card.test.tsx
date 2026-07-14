import { beforeEach, describe, expect, it, vi } from "vitest";
import { TenantRoleStatus } from "@/entities/tenant";
import type { TenantRole } from "@/entities/tenant-role";
import { RoleCard } from "@/features/roles/ui/role-card";
import { fireEvent, render, screen } from "@/tests/render-with-intl";

const authMock = vi.hoisted(() => ({
  allowed: new Set<string>(),
}));

vi.mock("@/features/auth", () => ({
  usePermissions: () => ({
    hasPermission: (code: string) => authMock.allowed.has(code),
    hasPermissions: (codes: string[]) =>
      codes.every((code) => authMock.allowed.has(code)),
    isOwner: false,
  }),
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

describe("RoleCard", () => {
  beforeEach(() => {
    authMock.allowed = new Set(["tenant_roles.update", "tenant_roles.delete"]);
  });

  it("opens edit from the card surface when updates are allowed", () => {
    const onEdit = vi.fn();

    render(<RoleCard role={role} onEdit={onEdit} onDelete={vi.fn()} />);

    const [cardButton] = screen.getAllByRole("button", {
      name: "Edit role Compliance reviewer",
    });
    fireEvent.click(cardButton);

    expect(onEdit).toHaveBeenCalledWith("role-1");
  });

  it("keeps delete separate from the card edit action", () => {
    const onDelete = vi.fn();
    const onEdit = vi.fn();

    render(<RoleCard role={role} onEdit={onEdit} onDelete={onDelete} />);

    fireEvent.click(
      screen.getByRole("button", {
        name: "Delete role Compliance reviewer",
      })
    );

    expect(onDelete).toHaveBeenCalledWith("role-1");
    expect(onEdit).not.toHaveBeenCalled();
  });

  it("does not expose the card edit surface when updates are not allowed", () => {
    authMock.allowed = new Set(["tenant_roles.delete"]);
    const onEdit = vi.fn();

    render(<RoleCard role={role} onEdit={onEdit} onDelete={vi.fn()} />);

    expect(
      screen.getByRole("button", { name: "Edit role Compliance reviewer" })
    ).toBeDisabled();

    fireEvent.click(screen.getByText("Compliance reviewer"));

    expect(onEdit).not.toHaveBeenCalled();
  });
});
