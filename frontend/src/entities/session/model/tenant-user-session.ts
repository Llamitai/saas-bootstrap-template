import type { JwtSession } from "@/entities/session/model/jwt-session";
import { emptyJwtSession } from "@/entities/session/model/jwt-session";
import type { Tenant } from "@/entities/tenant";
import { emptyTenant } from "@/entities/tenant";
import type { TenantRole } from "@/entities/tenant-role";
import { emptyTenantRole } from "@/entities/tenant-role";
import type { User } from "@/entities/user";
import { emptyUser } from "@/entities/user";

export interface TenantUserProfile {
  user: User;
  tenant: Tenant | null;
}

export const emptyTenantUserProfile: TenantUserProfile = {
  user: emptyUser,
  tenant: emptyTenant,
};

export interface TenantUserSession {
  session: JwtSession;
  user: User;
  tenant: Tenant | null;
  tenantRole: TenantRole | null;
}

export const emptyTenantUserSession: TenantUserSession = {
  session: emptyJwtSession,
  user: emptyUser,
  tenant: emptyTenant,
  tenantRole: emptyTenantRole,
};

export type TenantUserContext = Omit<TenantUserSession, "session">;

export const emptyTenantUserContext: TenantUserContext = {
  user: emptyUser,
  tenant: emptyTenant,
  tenantRole: emptyTenantRole,
};
