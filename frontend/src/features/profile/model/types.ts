import type { User } from "@/entities/user";

export type Profile = User;

export interface UpdateProfilePayload {
  firstName?: string | null;
  lastName?: string | null;
}

export interface UpdatePasswordPayload {
  currentPassword: string;
  newPassword: string;
}
