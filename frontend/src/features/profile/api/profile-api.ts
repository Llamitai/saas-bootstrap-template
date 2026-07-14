import { isAxiosError } from "axios";
import type {
  Profile,
  UpdatePasswordPayload,
  UpdateProfilePayload,
} from "@/features/profile/model/types";
import { authHttp } from "@/shared/http/client";

type ErrorEnvelope = {
  errors?: Array<{ message?: unknown }>;
};

export function profileErrorMessage(error: unknown, fallback: string): string {
  if (!isAxiosError(error)) return fallback;
  const data = error.response?.data as ErrorEnvelope | undefined;
  const message = data?.errors?.[0]?.message;
  return typeof message === "string" ? message : fallback;
}

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
