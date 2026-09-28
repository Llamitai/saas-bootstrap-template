import type { TenantUserContext, TenantUserSession } from "@/entities/session";
import type { ErrorFeedback } from "@/shared/http/errors";
import { serverHttp } from "@/shared/http/server";
import type { TaskResult } from "@/shared/types/task-result";

interface TaskResultResponse {
  data: TaskResult;
  timestamp: string;
}

export interface TenantUserSessionResponse {
  data: TenantUserSession;
  timestamp: string;
}

interface TenantUserContextResponse {
  data: TenantUserContext;
  timestamp: string;
}

export type BackendAuthResult<T> =
  | { ok: true; status: number; body: T }
  | {
      ok: false;
      status: number;
      body: ErrorFeedback | unknown;
      /** Upstream Retry-After, when the backend sent one (429/503). */
      retryAfter?: string;
    };

/** Headers for backend calls: infrastructure credentials and client IP. */
export type BackendHeaders = Record<string, string>;

function toResult<T>(response: {
  status: number;
  data: T;
  headers?: unknown;
}): BackendAuthResult<T> {
  if (response.status >= 400) {
    // AxiosHeaders keeps normalized lowercase names as own properties.
    const raw = (response.headers as Record<string, unknown> | undefined)?.[
      "retry-after"
    ];
    return {
      ok: false,
      status: response.status,
      body: response.data,
      ...(typeof raw === "string" ? { retryAfter: raw } : {}),
    };
  }
  return { ok: true, status: response.status, body: response.data };
}

async function postBackendAuth<T>(
  endpoint: string,
  payload: unknown,
  headers?: BackendHeaders
): Promise<BackendAuthResult<T>> {
  const response = await serverHttp.post<T>(endpoint, payload, {
    headers,
    validateStatus: () => true,
  });
  return toResult(response);
}

export function loginBackend(
  email: string,
  password: string,
  headers?: BackendHeaders
): Promise<BackendAuthResult<TenantUserSessionResponse>> {
  return postBackendAuth("/auth/login", { email, password }, headers);
}

export function googleLoginBackend(
  code: string,
  headers?: BackendHeaders
): Promise<BackendAuthResult<TenantUserSessionResponse>> {
  return postBackendAuth("/auth/google-login", { code }, headers);
}

export function refreshBackendSession(
  refreshToken: string,
  headers?: BackendHeaders
): Promise<BackendAuthResult<TenantUserSessionResponse>> {
  return postBackendAuth("/auth/refresh", { refreshToken }, headers);
}

// Backend codes that mean the refresh token (or its user) is gone for good.
const REJECTED_SESSION_CODES = new Set([
  "auth.InvalidRefreshToken",
  "common.InvalidRefreshToken",
  "common.InvalidOrExpiredToken",
  "users.UserNotFound",
]);

function firstErrorCode(body: unknown): string | null {
  if (typeof body !== "object" || body === null) return null;
  const errors = (body as { errors?: Array<{ code?: unknown }> }).errors;
  const code = Array.isArray(errors) ? errors[0]?.code : undefined;
  return typeof code === "string" ? code : null;
}

/**
 * True only when the backend rejected the session itself (401/403 or a
 * known invalid-token code). Rate limits (429), 5xx, timeouts and an
 * unreachable backend are transient: callers keep the cookies.
 */
export function isSessionRejected(result: BackendAuthResult<unknown>): boolean {
  if (result.ok) return false;
  if (result.status === 401 || result.status === 403) return true;
  const code = firstErrorCode(result.body);
  return code !== null && REJECTED_SESSION_CODES.has(code);
}

// The backend rotates refresh tokens and revokes the presented one, so two
// rotations with the same token cannot both succeed. Parallel requests from
// one browser (hard reload plus RSC prefetches, or several tabs) reach this
// process with the same old cookie; they share one rotation and its result
// for a short window instead of revoking each other. The cache is per module
// instance: the Proxy and the route handlers are separate bundles, and several
// frontend instances do not share it either; the backend's grace window for a
// just-rotated token covers those races.
const ROTATION_REUSE_MS = 15_000;

type RotationEntry = {
  expiresAt: number;
  result: Promise<BackendAuthResult<TenantUserSessionResponse>>;
};

const rotations = new Map<string, RotationEntry>();

function pruneRotations(now: number): void {
  for (const [token, entry] of rotations) {
    if (entry.expiresAt <= now) rotations.delete(token);
  }
}

/**
 * Rotates a refresh token once per process and reuses the outcome for
 * concurrent callers. Only callers that can write cookies (Proxy, route
 * handlers) may use it; Server Components read the session with
 * `getBackendSession` instead.
 */
export function rotateBackendSession(
  refreshToken: string,
  headers?: BackendHeaders
): Promise<BackendAuthResult<TenantUserSessionResponse>> {
  const now = Date.now();
  pruneRotations(now);
  const cached = rotations.get(refreshToken);
  if (cached) return cached.result;

  const result = refreshBackendSession(refreshToken, headers).catch(
    (): BackendAuthResult<TenantUserSessionResponse> => ({
      ok: false,
      status: 502,
      body: null,
    })
  );
  rotations.set(refreshToken, { expiresAt: now + ROTATION_REUSE_MS, result });
  // A failed attempt is shared only by the callers already waiting on it;
  // network failures surface as a transient 502.
  result.then((outcome) => {
    if (!outcome.ok) rotations.delete(refreshToken);
  });
  return result;
}

/** Test seam: forget shared rotations between cases. */
export function resetSessionRotationCache(): void {
  rotations.clear();
}

/** Reads the active session without rotating any token. */
export async function getBackendSession(
  accessToken: string,
  headers?: BackendHeaders
): Promise<BackendAuthResult<TenantUserContextResponse>> {
  const response = await serverHttp.get<TenantUserContextResponse>(
    "/auth/session",
    {
      headers: { ...headers, Authorization: `Bearer ${accessToken}` },
      validateStatus: () => true,
    }
  );
  return toResult(response);
}

export function logoutBackend(
  refreshToken?: string | null,
  headers?: BackendHeaders
): Promise<BackendAuthResult<TaskResultResponse>> {
  return postBackendAuth("/auth/logout", { refreshToken }, headers);
}
