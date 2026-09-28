import axios, { type AxiosError, type InternalAxiosRequestConfig } from "axios";
import { getAuthHeaderContext } from "@/shared/http/auth-context";
import { getCommonHeaders } from "@/shared/http/headers";

type ErrorEnvelope = {
  errors?: Array<{ code?: unknown }>;
};

// Browser-side clients always go through the Next.js BFF/proxy.
export const localHttp = axios.create({
  baseURL: "/api",
  timeout: 10000,
});

export const authHttp = axios.create({
  baseURL: "/api",
});

function attachAuthHeaders(config: InternalAxiosRequestConfig) {
  const { tenantSlug, accessToken } = getAuthHeaderContext();
  const common = getCommonHeaders(tenantSlug, accessToken);

  config.headers = config.headers || {};

  if (typeof config.headers.set === "function") {
    for (const [key, value] of Object.entries(common)) {
      if (value == null) continue;
      config.headers.set(key, value);
    }
  } else {
    Object.assign(config.headers, common);
  }
  return config;
}

/**
 * `token` on success; `rejected` when /api/auth/refresh answered 401 (the
 * session is gone); `transient` for rate limits, 5xx or network errors, where
 * the cookies are kept and the original request simply fails.
 */
type RefreshOutcome =
  | { kind: "token"; token: string }
  | { kind: "rejected" }
  | { kind: "transient" };

let refreshPromise: Promise<RefreshOutcome> | null = null;
let isRedirecting = false;

function deduplicatedRefresh(): Promise<RefreshOutcome> {
  if (!refreshPromise) {
    refreshPromise = refreshAccess().finally(() => {
      refreshPromise = null;
    });
  }
  return refreshPromise;
}

async function refreshAccess(): Promise<RefreshOutcome> {
  try {
    const res = await axios.post("/api/auth/refresh", null, {
      withCredentials: true,
    });
    const token = res.data?.accessToken;
    return typeof token === "string" && token
      ? { kind: "token", token }
      : { kind: "rejected" };
  } catch (error) {
    const status = axios.isAxiosError(error) ? error.response?.status : null;
    return status === 401 ? { kind: "rejected" } : { kind: "transient" };
  }
}

function handleRefreshFailure(): void {
  if (isRedirecting) return;
  isRedirecting = true;
  getAuthHeaderContext().clearSession();
  if (typeof window !== "undefined") {
    window.location.href = "/";
  }
}

function createRefreshInterceptor(httpClient: ReturnType<typeof axios.create>) {
  return async (error: AxiosError) => {
    const original = error.config as InternalAxiosRequestConfig & {
      _retry?: boolean;
    };

    const status = error.response?.status;
    const errorData = error.response?.data as ErrorEnvelope | undefined;
    const rawErrorCode = errorData?.errors?.[0]?.code;
    const errorCode = typeof rawErrorCode === "string" ? rawErrorCode : null;
    const isAuthError =
      status === 401 ||
      (status === 403 && errorCode === "auth.NotAuthenticated");
    if (isAuthError && !original?._retry && !isRedirecting) {
      original._retry = true;

      const outcome = await deduplicatedRefresh();

      if (outcome.kind === "token") {
        getAuthHeaderContext().setAccessToken(outcome.token);
        original.headers = original.headers ?? {};
        original.headers.Authorization = `Bearer ${outcome.token}`;
        return httpClient(original);
      }

      if (outcome.kind === "rejected") handleRefreshFailure();
    }

    return Promise.reject(error);
  };
}

localHttp.interceptors.request.use(attachAuthHeaders);
localHttp.interceptors.response.use(
  (response) => response,
  createRefreshInterceptor(localHttp)
);

authHttp.interceptors.request.use(attachAuthHeaders);
authHttp.interceptors.response.use(
  (response) => response,
  createRefreshInterceptor(authHttp)
);
