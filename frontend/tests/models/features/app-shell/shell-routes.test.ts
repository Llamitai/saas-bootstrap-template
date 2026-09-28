import { describe, expect, it } from "vitest";
import { resolveShellRoute } from "@/features/app-shell/ui/sidebar-config";

describe("resolveShellRoute", () => {
  it("maps each shell page to its nav entry and breadcrumb label", () => {
    expect(resolveShellRoute("/members")).toEqual({
      activePath: "/members",
      label: { namespace: "Nav", key: "members" },
    });
    expect(resolveShellRoute("/roles")?.label.key).toBe("roles");
    expect(resolveShellRoute("/settings")?.label.key).toBe("settings");
    expect(resolveShellRoute("/profile")).toEqual({
      activePath: "/profile",
      label: { namespace: "NavUser", key: "profile" },
    });
  });

  it("keeps the parent entry active for nested pages", () => {
    expect(resolveShellRoute("/members/abc")?.activePath).toBe("/members");
  });

  it("does not match unrelated paths that share a prefix", () => {
    expect(resolveShellRoute("/membership")).toBeNull();
    expect(resolveShellRoute("/")).toBeNull();
  });
});
