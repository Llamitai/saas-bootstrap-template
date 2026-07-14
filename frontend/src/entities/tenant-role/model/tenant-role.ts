import { TenantRoleStatus } from "@/entities/tenant";

export interface Permission {
  code: string;
  label: string;
}

export interface TenantRole {
  uuid: string;
  name: string;
  slug: string;
  status: TenantRoleStatus;
  permissions: Permission[];
  iconUrl?: string | null;
  isOwner?: boolean;
}

export const emptyTenantRole: TenantRole = {
  uuid: "",
  name: "",
  slug: "",
  status: TenantRoleStatus.INACTIVE,
  permissions: [],
  iconUrl: null,
  isOwner: false,
};
