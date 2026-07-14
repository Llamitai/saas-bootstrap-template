import { describe, expect, it } from "vitest";
import {
  loginFormSchema,
  tenantUserContextSchema,
} from "@/features/auth/model/types";

describe("loginFormSchema", () => {
  it("accepts a well-formed email and password", () => {
    const result = loginFormSchema.safeParse({
      email: "owner@acme.test",
      password: "s3cret!",
    });

    expect(result.success).toBe(true);
  });

  it("rejects a malformed email with the localized message", () => {
    const result = loginFormSchema.safeParse({
      email: "not-an-email",
      password: "s3cret!",
    });

    expect(result.success).toBe(false);
    if (!result.success) {
      expect(result.error.issues[0]?.message).toBe("Email invalido");
    }
  });

  it("rejects passwords shorter than six characters", () => {
    const result = loginFormSchema.safeParse({
      email: "owner@acme.test",
      password: "12345",
    });

    expect(result.success).toBe(false);
    if (!result.success) {
      expect(result.error.issues[0]?.path).toEqual(["password"]);
    }
  });
});

describe("tenantUserContextSchema", () => {
  it("parses an unassigned user payload with null tenant and role", () => {
    const result = tenantUserContextSchema.safeParse({
      user: {
        uuid: "user-1",
        username: "owner@acme.test",
      },
      tenant: null,
      tenantRole: null,
    });

    expect(result.success).toBe(true);
    if (result.success) {
      expect(result.data.user.uuid).toBe("user-1");
      expect(result.data.tenant).toBeNull();
    }
  });
});
