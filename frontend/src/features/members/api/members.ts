import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import type {
  DeleteResponse,
  InviteMemberPayload,
  InviteMembersResult,
  PendingInvitation,
  TenantUser,
  UpdateTenantUserPayload,
} from "@/features/members/model/types";
import { authHttp } from "@/shared/http/client";

type ApiEnvelope<T> = { data: T };

export const memberKeys = {
  all: ["members"] as const,
};

export const invitationKeys = {
  pending: ["invitations", "pending"] as const,
};

export async function getMembers(): Promise<TenantUser[]> {
  const response =
    await authHttp.get<ApiEnvelope<TenantUser[]>>("/v1/tenants/users");
  return response.data.data;
}

export async function inviteMember(
  payload: InviteMemberPayload
): Promise<InviteMembersResult> {
  const response = await authHttp.post<ApiEnvelope<InviteMembersResult>>(
    "/v1/tenants/invitations",
    { members: [{ email: payload.email, roleSlug: payload.roleSlug }] }
  );
  return response.data.data;
}

export async function listPendingInvitations(): Promise<PendingInvitation[]> {
  const response = await authHttp.get<ApiEnvelope<PendingInvitation[]>>(
    "/v1/tenants/invitations"
  );
  return response.data.data;
}

export async function cancelInvitation(
  invitationId: string
): Promise<PendingInvitation> {
  const response = await authHttp.delete<ApiEnvelope<PendingInvitation>>(
    `/v1/tenants/invitations/${encodeURIComponent(invitationId)}`
  );
  return response.data.data;
}

export async function sendPasswordReset(
  tenantUserId: string
): Promise<{ email: string }> {
  const response = await authHttp.post<ApiEnvelope<{ email: string }>>(
    `/v1/tenants/users/${encodeURIComponent(tenantUserId)}/send-password-reset`
  );
  return response.data.data;
}

export async function updateMember(
  uuid: string,
  payload: UpdateTenantUserPayload
): Promise<TenantUser> {
  const response = await authHttp.put<ApiEnvelope<TenantUser>>(
    `/v1/tenants/users/${encodeURIComponent(uuid)}`,
    payload
  );
  return response.data.data;
}

export async function uploadMemberPhoto(
  uuid: string,
  file: File
): Promise<TenantUser> {
  const form = new FormData();
  form.append("photo", file);
  const response = await authHttp.post<ApiEnvelope<TenantUser>>(
    `/v1/tenants/users/${encodeURIComponent(uuid)}/photo`,
    form,
    { headers: { "Content-Type": "multipart/form-data" } }
  );
  return response.data.data;
}

export async function deleteMember(uuid: string): Promise<DeleteResponse> {
  const response = await authHttp.delete<ApiEnvelope<DeleteResponse>>(
    `/v1/tenants/users/${encodeURIComponent(uuid)}`
  );
  return response.data.data;
}

export function useMembersQuery() {
  return useQuery({
    queryKey: memberKeys.all,
    queryFn: getMembers,
  });
}

export function useInviteMemberMutation() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: inviteMember,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: memberKeys.all });
      qc.invalidateQueries({ queryKey: invitationKeys.pending });
    },
  });
}

export function usePendingInvitationsQuery() {
  return useQuery({
    queryKey: invitationKeys.pending,
    queryFn: listPendingInvitations,
  });
}

export function useSendPasswordResetMutation() {
  return useMutation({
    mutationFn: async (tenantUserId: string) => {
      // Admin path: hits the tenant-scoped endpoint that operates on a
      // known TenantUser, so we get a real 404 if the member is missing
      // (the public /v1/auth/reset-password endpoint is anti-enumeration
      // and silently no-ops for unknown emails, which is misleading for
      // an admin acting on a member they can see).
      return sendPasswordReset(tenantUserId);
    },
  });
}

export function useCancelInvitationMutation() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: cancelInvitation,
    onSuccess: () => qc.invalidateQueries({ queryKey: invitationKeys.pending }),
  });
}

export function useUpdateMemberMutation() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async ({
      uuid,
      payload,
    }: {
      uuid: string;
      payload: UpdateTenantUserPayload;
    }) => updateMember(uuid, payload),
    onSuccess: () => qc.invalidateQueries({ queryKey: memberKeys.all }),
  });
}

export function useUploadMemberPhotoMutation() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ uuid, file }: { uuid: string; file: File }) =>
      uploadMemberPhoto(uuid, file),
    onSuccess: () => qc.invalidateQueries({ queryKey: memberKeys.all }),
  });
}

export function useDeleteMemberMutation() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: deleteMember,
    onSuccess: () => qc.invalidateQueries({ queryKey: memberKeys.all }),
  });
}
