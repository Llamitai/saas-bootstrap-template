import { create } from "zustand";
import { persist } from "zustand/middleware";

import type { Tenant } from "@/entities/tenant";
import type { TenantRole } from "@/entities/tenant-role";
import type { User } from "@/entities/user";
import { configureAuthHeaderContext } from "@/shared/http/auth-context";

interface SessionState {
  user: User | null;
  tenant: Tenant | null;
  tenantRole: TenantRole | null;
  accessToken: string | null;
  _synced: boolean;

  setSession: (
    user: User,
    tenant: Tenant | null,
    tenantRole: TenantRole | null,
    accessToken: string
  ) => void;
  setUser: (user: User) => void;
  setAccessToken: (accessToken: string) => void;
  setTenant: (tenant: Tenant) => void;
  clearTenant: () => void;
  clearSession: () => void;

  isAuthenticated: () => boolean;
}

export const useSessionStore = create<SessionState>()(
  persist(
    (set, get) => ({
      user: null,
      tenant: null,
      tenantRole: null,
      accessToken: null,
      _synced: false,

      setSession: (user, tenant, tenantRole, accessToken) => {
        set({
          user,
          tenant,
          tenantRole,
          accessToken,
          _synced: true,
        });
      },

      setUser: (user) => {
        set({ user });
      },

      setAccessToken: (accessToken) => {
        set({ accessToken });
      },

      setTenant: (tenant) => {
        set({ tenant });
      },

      clearTenant: () => {
        set({ tenant: null, tenantRole: null });
      },

      clearSession: () => {
        set({
          user: null,
          tenant: null,
          tenantRole: null,
          accessToken: null,
          _synced: false,
        });
      },

      isAuthenticated: () => {
        const state = get();
        return (
          state.user !== null &&
          state.tenant !== null &&
          state.accessToken !== null
        );
      },
    }),
    {
      name: "session-storage",
      partialize: (state) => ({
        user: state.user,
        tenant: state.tenant,
        tenantRole: state.tenantRole,
      }),
    }
  )
);

configureAuthHeaderContext(() => {
  const session = useSessionStore.getState();
  return {
    tenantSlug: session.tenant?.slug ?? null,
    accessToken: session.accessToken,
    clearSession: session.clearSession,
    setAccessToken: session.setAccessToken,
  };
});
