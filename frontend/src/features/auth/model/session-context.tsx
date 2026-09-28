"use client";

import { useQueryClient } from "@tanstack/react-query";
import { createContext, type ReactNode, useCallback, useContext } from "react";

import type { Tenant } from "@/entities/tenant";
import type { TenantRole } from "@/entities/tenant-role";
import type { User } from "@/entities/user";
import { useSessionStore } from "@/features/auth/model/session-store";

interface SessionContextType {
  user: User | null;
  tenant: Tenant | null;
  tenantRole: TenantRole | null;
  isAuthenticated: boolean;
  isLoading: boolean;
}

const SessionContext = createContext<SessionContextType | undefined>(undefined);

export function SessionProvider({ children }: { children: ReactNode }) {
  const user = useSessionStore((state) => state.user);
  const tenant = useSessionStore((state) => state.tenant);
  const tenantRole = useSessionStore((state) => state.tenantRole);
  const isAuthenticated = useSessionStore((state) => state.isAuthenticated());
  const synced = useSessionStore((state) => state._synced);

  return (
    <SessionContext.Provider
      value={{
        user,
        tenant,
        tenantRole,
        isAuthenticated,
        isLoading: !synced,
      }}
    >
      {children}
    </SessionContext.Provider>
  );
}

export function useSession() {
  const context = useContext(SessionContext);
  if (context === undefined) {
    throw new Error("useSession must be used within a SessionProvider");
  }
  return context;
}

export function useSessionActions() {
  const queryClient = useQueryClient();
  const clearStoredSession = useSessionStore((state) => state.clearSession);
  // Query keys are not scoped by user or tenant, so ending a session must
  // drop every cached response (cache-scope rule).
  const clearSession = useCallback(() => {
    clearStoredSession();
    queryClient.clear();
  }, [clearStoredSession, queryClient]);

  return {
    setSession: useSessionStore((state) => state.setSession),
    setAccessToken: useSessionStore((state) => state.setAccessToken),
    clearSession,
  };
}
