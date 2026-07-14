import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import type {
  CreateTenantRolePayload,
  DeleteResponse,
  TenantRole,
  UpdateTenantRolePayload,
} from "@/features/roles/model/types";
import { authHttp } from "@/shared/http/client";

type ApiEnvelope<T> = { data: T };

export const roleKeys = {
  all: ["roles"] as const,
  detail: (uuid: string) => ["roles", uuid] as const,
};

export async function getRoles(): Promise<TenantRole[]> {
  const response =
    await authHttp.get<ApiEnvelope<TenantRole[]>>("/v1/tenants/roles");
  return response.data.data;
}

export async function createRole(
  payload: CreateTenantRolePayload
): Promise<TenantRole> {
  const response = await authHttp.post<ApiEnvelope<TenantRole>>(
    "/v1/tenants/roles",
    payload
  );
  return response.data.data;
}

export async function updateRole(
  uuid: string,
  payload: UpdateTenantRolePayload
): Promise<TenantRole> {
  const response = await authHttp.put<ApiEnvelope<TenantRole>>(
    `/v1/tenants/roles/${encodeURIComponent(uuid)}`,
    payload
  );
  return response.data.data;
}

export async function deleteRole(uuid: string): Promise<DeleteResponse> {
  const response = await authHttp.delete<ApiEnvelope<DeleteResponse>>(
    `/v1/tenants/roles/${encodeURIComponent(uuid)}`
  );
  return response.data.data;
}

export function useRolesQuery() {
  return useQuery({
    queryKey: roleKeys.all,
    queryFn: getRoles,
  });
}

export function useCreateRoleMutation() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: createRole,
    onSuccess: () => qc.invalidateQueries({ queryKey: roleKeys.all }),
  });
}

export function useUpdateRoleMutation() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async ({
      uuid,
      payload,
    }: {
      uuid: string;
      payload: UpdateTenantRolePayload;
    }) => updateRole(uuid, payload),
    onSuccess: () => qc.invalidateQueries({ queryKey: roleKeys.all }),
  });
}

export function useDeleteRoleMutation() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: deleteRole,
    onSuccess: () => qc.invalidateQueries({ queryKey: roleKeys.all }),
  });
}
