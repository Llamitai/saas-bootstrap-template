import { config } from "@/lib/config";

export interface AuthTokens {
  accessToken: string;
  refreshToken?: string;
}

function normalizeTokens(payload: unknown): AuthTokens {
  if (!payload || typeof payload !== "object") {
    throw new Error("La respuesta de autenticación no contiene tokens.");
  }

  const record = payload as Record<string, unknown>;
  const accessToken = record.accessToken ?? record.access_token;
  const refreshToken = record.refreshToken ?? record.refresh_token;

  if (typeof accessToken !== "string" || accessToken.length === 0) {
    throw new Error("La respuesta de autenticación no contiene access token.");
  }

  return {
    accessToken,
    refreshToken: typeof refreshToken === "string" ? refreshToken : undefined,
  };
}

async function requestAuth(path: string, init: RequestInit = {}) {
  const response = await fetch(`${config.apiHost}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...init.headers,
    },
  });

  if (!response.ok) {
    throw new Error(`Auth request failed: ${response.status}`);
  }

  if (response.status === 204) {
    return null;
  }

  return response.json() as Promise<unknown>;
}

export async function login(email: string, password: string) {
  const payload = await requestAuth("/auth/login", {
    method: "POST",
    body: JSON.stringify({ email, password }),
  });

  return normalizeTokens(payload);
}

export async function refresh(refreshToken: string) {
  const payload = await requestAuth("/auth/refresh", {
    method: "POST",
    body: JSON.stringify({ refreshToken }),
  });

  return normalizeTokens(payload);
}

export async function logout(accessToken?: string, refreshToken?: string) {
  await requestAuth("/auth/logout", {
    method: "POST",
    headers: accessToken ? { Authorization: `Bearer ${accessToken}` } : {},
    body: JSON.stringify({ refreshToken }),
  });
}
