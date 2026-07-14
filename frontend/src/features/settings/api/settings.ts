import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useSessionStore } from "@/features/auth";
import type { TenantSettings } from "@/features/settings/model/types";
import { authHttp } from "@/shared/http/client";

type ApiEnvelope<T> = { data: T };

export const settingsKeys = {
  all: ["settings"] as const,
};

function activeTenantId(): string {
  const tenantId = useSessionStore.getState().tenant?.uuid;
  if (!tenantId) throw new Error("No active tenant");
  return tenantId;
}

export async function getSettings(): Promise<TenantSettings> {
  const response = await authHttp.get<ApiEnvelope<TenantSettings>>(
    `/v1/tenants/${activeTenantId()}/settings`
  );
  return response.data.data;
}

export async function updateSettings(name: string): Promise<TenantSettings> {
  const response = await authHttp.patch<ApiEnvelope<TenantSettings>>(
    `/v1/tenants/${activeTenantId()}/settings`,
    { name }
  );
  return response.data.data;
}

export async function updateAvatar(file: File): Promise<TenantSettings> {
  const form = new FormData();
  form.append("avatar", file);
  const response = await authHttp.post<ApiEnvelope<TenantSettings>>(
    `/v1/tenants/${activeTenantId()}/settings/avatar`,
    form
  );
  return response.data.data;
}

export async function deleteTenant(): Promise<{ success: boolean }> {
  await authHttp.delete(`/v1/tenants/${activeTenantId()}`);
  return { success: true };
}

export function useSettingsQuery() {
  return useQuery({
    queryKey: settingsKeys.all,
    queryFn: getSettings,
  });
}

export function useUpdateSettingsMutation() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: updateSettings,
    onSuccess: () => qc.invalidateQueries({ queryKey: settingsKeys.all }),
  });
}

export function useUpdateAvatarMutation() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: updateAvatar,
    onSuccess: () => qc.invalidateQueries({ queryKey: settingsKeys.all }),
  });
}

export function useDeleteTenantMutation() {
  return useMutation({
    mutationFn: deleteTenant,
  });
}
