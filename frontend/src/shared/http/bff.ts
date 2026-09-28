import type { AxiosError } from "axios";
import { NextResponse } from "next/server";

import { serverConfig } from "@/shared/config/server";

/**
 * Helpers compartidos por las BFF routes (`src/app/api/.../route.ts`).
 *
 * El cliente llama a la BFF con sus headers de sesión (Authorization +
 * X-Tenant, adjuntados por `attachAuthHeaders`); aquí los reenviamos al
 * backend junto con la X-Api-Key server-only — el mismo contrato que aplica
 * el proxy de `/api/v1/*` (src/proxy.ts).
 */
type IncomingRequest = { headers: Pick<Headers, "get"> };

/** Header the backend trusts for rate limits, only next to a valid X-Api-Key. */
export const CLIENT_IP_HEADER = "X-Client-IP";

const IPV4 =
  /^(25[0-5]|2[0-4]\d|1\d\d|[1-9]?\d)(\.(25[0-5]|2[0-4]\d|1\d\d|[1-9]?\d)){3}$/;

export function isIpAddress(value: string): boolean {
  if (IPV4.test(value)) return true;
  if (!value.includes(":") || !/^[0-9a-fA-F:.]+$/.test(value)) return false;
  try {
    // The WHATWG URL parser validates IPv6 literals.
    new URL(`http://[${value}]/`);
    return true;
  } catch {
    return false;
  }
}

/**
 * Client IP as seen by this frontend: the configured trusted edge header
 * (TRUSTED_CLIENT_IP_HEADER) or, without one, the last X-Forwarded-For hop,
 * which Next's server fills with the socket address. Invalid values yield
 * null. Without a trusted edge, a client that talks to Next directly can
 * still choose that last hop.
 */
export function resolveClientIp(request: IncomingRequest): string | null {
  const trusted = serverConfig.trustedClientIpHeader;
  const raw = trusted
    ? request.headers.get(trusted)
    : request.headers.get("x-forwarded-for")?.split(",").at(-1);
  const ip = raw?.trim() ?? "";
  return ip && isIpAddress(ip) ? ip : null;
}

/** `X-Client-IP` for backend calls; never the browser-supplied value. */
export function clientIpHeaders(
  request: IncomingRequest
): Record<string, string> {
  const ip = resolveClientIp(request);
  return ip ? { [CLIENT_IP_HEADER]: ip } : {};
}

export function backendHeadersFrom(
  request: IncomingRequest
): Record<string, string> {
  const headers: Record<string, string> = clientIpHeaders(request);

  const auth = request.headers.get("authorization");
  if (auth) headers.Authorization = auth;

  const tenant = request.headers.get("x-tenant");
  if (tenant) headers["X-Tenant"] = tenant;

  if (serverConfig.apiKey) headers["X-Api-Key"] = serverConfig.apiKey;

  if (serverConfig.cfAccessClientId) {
    headers["CF-Access-Client-Id"] = serverConfig.cfAccessClientId;
  }
  if (serverConfig.cfAccessClientSecret) {
    headers["CF-Access-Client-Secret"] = serverConfig.cfAccessClientSecret;
  }

  return headers;
}

/**
 * Refleja la respuesta de error del backend tal cual (status + payload),
 * para que el cliente vea exactamente el envelope de errores del API
 * (p. ej. 409 `tenant_user.invitation_pending` con detalles accionables).
 */
export function mirrorBackendError(error: unknown): NextResponse {
  const axiosError = error as AxiosError;
  if (axiosError?.response) {
    const data = axiosError.response.data ?? {
      errors: [
        { code: "bff.upstream_error", message: "Backend service error" },
      ],
      validation: null,
    };
    return NextResponse.json(data, { status: axiosError.response.status });
  }
  return NextResponse.json(
    {
      errors: [
        {
          code: "bff.upstream_unreachable",
          message: "Backend unreachable",
        },
      ],
      validation: null,
    },
    { status: 502 }
  );
}
