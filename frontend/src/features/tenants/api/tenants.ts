import { useMutation, useQuery } from "@tanstack/react-query";
import type { Tenant } from "@/entities/tenant";
import { useSessionStore } from "@/features/auth";
import { authHttp } from "@/shared/http/client";

export interface TenantFilters {
  status?: string;
  search?: string;
}

type ApiEnvelope<T> = { data: T };

export const tenantQueryKeys = {
  all: ["tenants"] as const,
  list: (filters?: TenantFilters) =>
    filters === undefined
      ? (["tenants", "list"] as const)
      : (["tenants", "list", filters] as const),
};

export async function listTenants(filters?: TenantFilters): Promise<Tenant[]> {
  const params = new URLSearchParams();
  if (filters?.status) params.set("status", filters.status);
  if (filters?.search) params.set("search", filters.search);
  const query = params.toString();
  const endpoint = `/v1/me/tenants${query ? `?${query}` : ""}`;
  const response = await authHttp.get<ApiEnvelope<Tenant[]>>(endpoint);
  return response.data.data;
}

export async function setCurrentTenant(tenantUuid: string): Promise<void> {
  await authHttp.put(`/v1/me/tenants/${encodeURIComponent(tenantUuid)}`);
}

export function useTenantsQuery(filters?: TenantFilters) {
  return useQuery({
    queryKey: tenantQueryKeys.list(filters),
    queryFn: () => listTenants(filters),
  });
}

export function useSelectTenantMutation() {
  return useMutation({
    mutationFn: async (tenant: Tenant) => {
      const session = useSessionStore.getState();
      const previous = session.tenant;
      session.setTenant(tenant);
      try {
        await setCurrentTenant(tenant.uuid);
      } catch (error) {
        if (previous) session.setTenant(previous);
        throw error;
      }
    },
  });
}
