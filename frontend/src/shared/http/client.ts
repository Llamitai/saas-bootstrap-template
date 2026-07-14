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

let refreshPromise: Promise<string | null> | null = null;
let isRedirecting = false;

function deduplicatedRefresh(): Promise<string | null> {
  if (!refreshPromise) {
    refreshPromise = refreshAccess().finally(() => {
      refreshPromise = null;
    });
  }
  return refreshPromise;
}

async function refreshAccess(): Promise<string | null> {
  try {
    const res = await axios.post("/api/auth/refresh", null, {
      withCredentials: true,
    });
    return res.data?.accessToken ?? null;
  } catch {
    return null;
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

      const newToken = await deduplicatedRefresh();

      if (newToken) {
        getAuthHeaderContext().setAccessToken(newToken);
        original.headers = original.headers ?? {};
        original.headers.Authorization = `Bearer ${newToken}`;
        return httpClient(original);
      }

      handleRefreshFailure();
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
