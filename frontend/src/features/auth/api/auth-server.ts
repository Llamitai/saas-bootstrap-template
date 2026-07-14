import type { TenantUserSession } from "@/entities/session";
import type { ErrorFeedback } from "@/shared/http/errors";
import { serverHttp } from "@/shared/http/server";
import type { TaskResult } from "@/shared/types/task-result";

interface TaskResultResponse {
  data: TaskResult;
  datetime: string;
}

interface TenantUserSessionResponse {
  data: TenantUserSession;
  datetime: string;
}

export type BackendAuthResult<T> =
  | { ok: true; status: number; body: T }
  | { ok: false; status: number; body: ErrorFeedback | unknown };

async function postBackendAuth<T>(
  endpoint: string,
  payload: unknown
): Promise<BackendAuthResult<T>> {
  const response = await serverHttp.post<T>(endpoint, payload, {
    validateStatus: () => true,
  });

  if (response.status >= 400) {
    return { ok: false, status: response.status, body: response.data };
  }
  return { ok: true, status: response.status, body: response.data };
}

export function loginBackend(
  email: string,
  password: string
): Promise<BackendAuthResult<TenantUserSessionResponse>> {
  return postBackendAuth("/auth/login", { email, password });
}

export function googleLoginBackend(
  code: string
): Promise<BackendAuthResult<TenantUserSessionResponse>> {
  return postBackendAuth("/auth/google-login", { code });
}

export function refreshBackendSession(
  refreshToken: string
): Promise<BackendAuthResult<TenantUserSessionResponse>> {
  return postBackendAuth("/auth/refresh", { refreshToken });
}

export function logoutBackend(
  refreshToken?: string | null
): Promise<BackendAuthResult<TaskResultResponse>> {
  return postBackendAuth("/auth/logout", { refreshToken });
}
