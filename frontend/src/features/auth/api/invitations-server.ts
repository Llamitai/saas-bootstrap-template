import { cache } from "react";

import { serverConfig } from "@/shared/config/server";

export interface InvitationView {
  email: string;
  tenantName: string;
  roleName: string | null;
  expiresAt: string | null;
  requiresPassword: boolean;
}

export type InvitationLoadResult =
  | { kind: "ok"; data: InvitationView }
  | { kind: "not_found" }
  | { kind: "already_accepted" }
  | { kind: "expired" };

export const loadInvitation = cache(
  async (token: string): Promise<InvitationLoadResult> => {
    try {
      const res = await fetch(
        `${serverConfig.apiBaseUrl}/v1/invitations/${encodeURIComponent(token)}`,
        { cache: "no-store" }
      );
      if (res.ok) {
        const body = await res.json();
        const data = body?.data as InvitationView | undefined;
        if (!data) return { kind: "not_found" };
        return { kind: "ok", data };
      }
      const body = (await res.json().catch(() => ({}))) as {
        errors?: { code?: string }[];
      };
      const code = body?.errors?.[0]?.code ?? "";
      if (code === "tenants.InvitationAlreadyAccepted") {
        return { kind: "already_accepted" };
      }
      if (code === "tenants.InvitationExpired") {
        return { kind: "expired" };
      }
      return { kind: "not_found" };
    } catch {
      return { kind: "not_found" };
    }
  }
);
