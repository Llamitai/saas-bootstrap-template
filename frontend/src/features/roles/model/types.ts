import type { TenantRoleStatus } from "@/entities/tenant";

export type { TenantRole } from "@/entities/tenant-role";

export interface CreateTenantRolePayload {
  name: string;
  status: TenantRoleStatus;
  permissions: string[];
  iconUrl?: string | null;
}

export interface UpdateTenantRolePayload {
  name?: string;
  status?: TenantRoleStatus;
  permissions?: string[];
  iconUrl?: string | null;
}

export interface DeleteResponse {
  status: string;
}
