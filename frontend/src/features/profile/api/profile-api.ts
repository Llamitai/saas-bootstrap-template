import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useSessionStore } from "@/features/auth";
import type {
  Profile,
  UpdatePasswordPayload,
  UpdateProfilePayload,
} from "@/features/profile/model/types";
import { authHttp } from "@/shared/http/client";

export const profileKeys = {
  all: ["profile"] as const,
  detail: () => ["profile", "me"] as const,
};

export async function getProfile(): Promise<Profile> {
  const response = await authHttp.get<{ data: Profile }>("/v1/me/profile");
  return response.data.data;
}

export async function updateProfile(
  payload: UpdateProfilePayload
): Promise<Profile> {
  const response = await authHttp.put<{ data: Profile }>(
    "/v1/me/profile",
    payload
  );
  return response.data.data;
}

export async function updatePassword(
  payload: UpdatePasswordPayload
): Promise<void> {
  await authHttp.put("/v1/me/password", payload);
}

export function useProfileQuery() {
  return useQuery({
    queryKey: profileKeys.detail(),
    queryFn: getProfile,
  });
}

export function useUpdateProfileMutation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: updateProfile,
    onSuccess: (profile) => {
      queryClient.setQueryData(profileKeys.detail(), profile);
      // The shell reads the signed-in user from the session store.
      useSessionStore.getState().setUser(profile);
    },
  });
}

export function useUpdatePasswordMutation() {
  return useMutation({ mutationFn: updatePassword });
}
