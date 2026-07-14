import type { Tenant } from "@/entities/tenant";
import type { TenantRole } from "@/entities/tenant-role";
import type { User } from "@/entities/user";
import type {
  AcceptInvitationPayload,
  LoginPayload,
} from "@/features/auth/model/types";

interface ErrorEnvelope {
  errors?: Array<{ code?: string; message?: string }>;
  validation?: unknown;
}

interface SessionContextData {
  user: User;
  tenant: Tenant | null;
  tenantRole: TenantRole | null;
}

export interface RefreshSessionResult {
  accessToken: string | null;
  data?: SessionContextData;
}

export class AuthApiError extends Error {
  readonly status: number;
  readonly code: string | null;
  readonly body: unknown;

  constructor(status: number, body: unknown, fallbackMessage: string) {
    const envelope = asErrorEnvelope(body);
    super(envelope?.errors?.[0]?.message ?? fallbackMessage);
    this.name = "AuthApiError";
    this.status = status;
    this.code = envelope?.errors?.[0]?.code ?? null;
    this.body = body;
  }
}

export function getAuthErrorMessage(error: unknown, fallback: string): string {
  if (error instanceof AuthApiError) return error.message || fallback;
  return fallback;
}

export function getAuthErrorCode(error: unknown): string | null {
  return error instanceof AuthApiError ? error.code : null;
}

export async function loginWithPassword(
  payload: LoginPayload
): Promise<SessionContextData> {
  const body = await postJson("/api/auth/login", payload, "Login failed");
  return sessionContextFromBody(body);
}

export async function logout(): Promise<void> {
  await postJson("/api/auth/logout", null, "Logout failed");
}

export async function refreshSession(): Promise<RefreshSessionResult> {
  const body = await postJson("/api/auth/refresh", null, "Refresh failed");
  return {
    accessToken:
      isRecord(body) && typeof body.accessToken === "string"
        ? body.accessToken
        : null,
    data:
      isRecord(body) && isRecord(body.data)
        ? sessionContextFromBody(body)
        : undefined,
  };
}

export async function requestPasswordReset(email: string): Promise<void> {
  await postJson(
    "/api/auth/reset-password",
    { email: email.trim() },
    "Password reset request failed"
  );
}

export async function confirmPasswordReset(
  token: string,
  password: string
): Promise<void> {
  await postJson(
    "/api/auth/reset-password/confirm",
    { token, password },
    "Password reset confirmation failed"
  );
}

export async function acceptInvitation(
  token: string,
  payload: AcceptInvitationPayload
): Promise<SessionContextData> {
  const body = await postJson(
    `/api/auth/invitations/${encodeURIComponent(token)}/accept`,
    payload,
    "Invitation accept failed"
  );
  return sessionContextFromBody(body);
}

async function postJson(
  url: string,
  payload: unknown,
  fallbackMessage: string
): Promise<unknown> {
  const response = await fetch(url, {
    method: "POST",
    headers:
      payload == null ? undefined : { "Content-Type": "application/json" },
    body: payload == null ? undefined : JSON.stringify(payload),
    credentials: "include",
  });
  const body = await response.json().catch(() => ({}));

  if (!response.ok) {
    throw new AuthApiError(response.status, body, fallbackMessage);
  }

  return body;
}

function sessionContextFromBody(body: unknown): SessionContextData {
  if (!isRecord(body) || !isRecord(body.data)) {
    throw new AuthApiError(500, body, "Invalid auth response");
  }
  const { user, tenant, tenantRole } = body.data;
  return {
    user: user as User,
    tenant: (tenant ?? null) as Tenant | null,
    tenantRole: (tenantRole ?? null) as TenantRole | null,
  };
}

function asErrorEnvelope(body: unknown): ErrorEnvelope | null {
  if (!isRecord(body)) return null;
  return body as ErrorEnvelope;
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null;
}
