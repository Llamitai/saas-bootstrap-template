export type { TenantUser } from "@/entities/member";
export type { TenantRole } from "@/entities/tenant-role";

export interface InviteMemberPayload {
  email: string;
  roleSlug: string;
}

export interface PendingInvitation {
  uuid: string;
  email: string;
  tenantRoleId: string | null;
  token: string;
  status: string;
  expiresAt: string | null;
  requiresPassword: boolean;
  createdAt: string | null;
}

export interface InviteMembersResult {
  invitations: PendingInvitation[];
  skippedExistingMembers: Array<{ email: string }>;
}

export interface UpdateTenantUserPayload {
  firstName?: string;
  lastName?: string;
  status?: string;
  tenantRoleId?: string;
  isOwner?: boolean;
  isSupport?: boolean;
  email?: string;
}

export interface DeleteResponse {
  status: string;
}
