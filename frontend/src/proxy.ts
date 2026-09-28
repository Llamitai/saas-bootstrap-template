import type { NextRequest } from "next/server";
import { NextResponse } from "next/server";
import {
  type BackendAuthResult,
  isSessionRejected,
  rotateBackendSession,
} from "@/features/auth/server";
import { serverConfig } from "@/shared/config/server";
import { isTokenValid } from "@/shared/helpers/jwt-token";
import { getRefreshTokenFromRequest } from "@/shared/helpers/session";
import {
  backendHeadersFrom,
  CLIENT_IP_HEADER,
  clientIpHeaders,
} from "@/shared/http/bff";
import {
  clearSessionCookies,
  type SessionCookieTokens,
  setSessionCookies,
} from "@/shared/http/session-cookies";
import {
  COOKIE_ACCESS_TOKEN,
  COOKIE_REFRESH_ATTEMPTS,
  COOKIE_REFRESH_TOKEN,
  MAX_REFRESH_ATTEMPTS,
  REFRESH_ATTEMPTS_MAX_AGE,
} from "@/src/constants";
import { defaultLocale, isLocale, LOCALE_COOKIE } from "@/src/i18n/config";
import en from "@/src/i18n/messages/en.json";
import es from "@/src/i18n/messages/es.json";

const PUBLIC_EXACT_ROUTES = ["/", "/register", "/reset-password"];
// Token-bearing public flows. Anything under these prefixes is reachable
// without auth so links sent by email keep working when the recipient
// is signed out.
const PUBLIC_PREFIX_ROUTES = ["/invitations/", "/reset-password/"];
const LOGIN_REDIRECT_PATH = "/members";
// Rotate slightly before expiry so the access token outlives the render.
const ACCESS_TOKEN_LEEWAY_SECONDS = 30;
const DEFAULT_RETRY_AFTER_SECONDS = 5;
const MAX_RETRY_AFTER_SECONDS = 120;

function isPublicPath(pathname: string): boolean {
  if (PUBLIC_EXACT_ROUTES.includes(pathname)) return true;
  return PUBLIC_PREFIX_ROUTES.some((p) => pathname.startsWith(p));
}

export const config = {
  matcher: [
    // All routes except static assets
    "/((?!_next/|_vercel|.*\\..*|icons/|config/|images/).*)",
    // Explicitly match API v1 routes for proxying
    "/api/v1/:path*",
  ],
};

export async function proxy(req: NextRequest) {
  const url = req.nextUrl;

  // ─── PROXY: forward /api/v1/* to backend ───
  if (url.pathname.startsWith("/api/v1/")) {
    const backendPath = url.pathname.replace(/^\/api/, "");
    const backendUrl = new URL(
      backendPath + url.search,
      serverConfig.apiBaseUrl
    );

    const requestHeaders = new Headers(req.headers);
    // Never forward a browser-supplied client IP; set the resolved one.
    requestHeaders.delete(CLIENT_IP_HEADER);
    for (const [name, value] of Object.entries(clientIpHeaders(req))) {
      requestHeaders.set(name, value);
    }
    if (serverConfig.apiKey)
      requestHeaders.set("X-Api-Key", serverConfig.apiKey);

    // Browser-native requests cannot attach an Authorization header the way
    // the axios clients do. Translate the httpOnly access cookie for them;
    // explicit headers from axios still win.
    if (!requestHeaders.has("authorization")) {
      const accessToken = req.cookies.get(COOKIE_ACCESS_TOKEN)?.value;
      if (accessToken) {
        requestHeaders.set("Authorization", `Bearer ${accessToken}`);
      }
    }

    if (serverConfig.cfAccessClientId) {
      requestHeaders.set("CF-Access-Client-Id", serverConfig.cfAccessClientId);
    }
    if (serverConfig.cfAccessClientSecret) {
      requestHeaders.set(
        "CF-Access-Client-Secret",
        serverConfig.cfAccessClientSecret
      );
    }

    return NextResponse.rewrite(backendUrl, {
      request: { headers: requestHeaders },
    });
  }

  // ─── SKIP: internal API routes handle their own auth ───
  if (url.pathname.startsWith("/api/")) {
    return NextResponse.next();
  }

  // ─── AUTH REDIRECTS ───
  const refreshToken = getRefreshTokenFromRequest(req);
  const isPublic = isPublicPath(url.pathname);

  // Authenticated user on public route -> redirect to the first core app view.
  // But if the user keeps bouncing back to a public route, the RT is broken
  // (revoked / signing secret rotated). Count attempts and bail after MAX_REFRESH_ATTEMPTS.
  if (refreshToken && isPublic) {
    const attempts = readAttempts(req);

    if (attempts >= MAX_REFRESH_ATTEMPTS) {
      // Loop detected. Clear the session so the user lands on login cleanly.
      const res = NextResponse.next();
      clearSessionCookies(res);
      return res;
    }

    const res = NextResponse.redirect(new URL(LOGIN_REDIRECT_PATH, req.url));
    res.cookies.set({
      name: COOKIE_REFRESH_ATTEMPTS,
      value: String(attempts + 1),
      httpOnly: true,
      secure: serverConfig.isProd,
      sameSite: "lax",
      path: "/",
      maxAge: REFRESH_ATTEMPTS_MAX_AGE,
    });
    return res;
  }

  // Unauthenticated user on protected route -> redirect to login
  if (!refreshToken && !isPublic) {
    return NextResponse.redirect(new URL("/", req.url));
  }

  if (refreshToken && !isPublic) {
    return ensureFreshSession(req, refreshToken);
  }

  return NextResponse.next();
}

/**
 * Protected navigation: Server Components cannot write cookies, so the
 * refresh-token rotation happens here. The new cookies go to the browser on
 * the response and to the render through the forwarded Cookie header, so the
 * protected layout reads the session with the new access token.
 */
async function ensureFreshSession(
  req: NextRequest,
  refreshToken: string
): Promise<NextResponse> {
  const accessToken = req.cookies.get(COOKIE_ACCESS_TOKEN)?.value;
  if (accessToken && isTokenValid(accessToken, ACCESS_TOKEN_LEEWAY_SECONDS)) {
    return NextResponse.next();
  }

  const result = await rotateBackendSession(
    refreshToken,
    backendHeadersFrom(req)
  );
  if (!result.ok) {
    if (isSessionRejected(result)) {
      const res = NextResponse.redirect(new URL("/", req.url));
      clearSessionCookies(res);
      return res;
    }
    // Rate limit, 5xx or unreachable backend: the session is still valid.
    // Keep the cookies and answer 503 instead of bouncing through login.
    return serviceUnavailable(req, result);
  }

  const tokens = result.body.data.session;
  const res = NextResponse.next({
    request: { headers: withSessionCookies(req, tokens) },
  });
  return setSessionCookies(res, tokens);
}

function withSessionCookies(
  req: NextRequest,
  tokens: SessionCookieTokens
): Headers {
  const cookies = new Map(
    req.cookies.getAll().map((cookie) => [cookie.name, cookie.value])
  );
  cookies.set(COOKIE_ACCESS_TOKEN, tokens.accessToken);
  cookies.set(COOKIE_REFRESH_TOKEN, tokens.refreshToken);
  cookies.delete(COOKIE_REFRESH_ATTEMPTS);

  const headers = new Headers(req.headers);
  headers.set(
    "cookie",
    [...cookies]
      .map(([name, value]) => `${name}=${encodeURIComponent(value)}`)
      .join("; ")
  );
  return headers;
}

function readAttempts(req: NextRequest): number {
  const raw = req.cookies.get(COOKIE_REFRESH_ATTEMPTS)?.value;
  if (!raw) return 0;
  const n = Number.parseInt(raw, 10);
  return Number.isFinite(n) && n > 0 ? n : 0;
}

function retryAfterSeconds(result: BackendAuthResult<unknown>): number {
  const raw = result.ok ? undefined : result.retryAfter;
  const seconds = raw ? Number.parseInt(raw, 10) : Number.NaN;
  if (!Number.isFinite(seconds) || seconds < 1) {
    return DEFAULT_RETRY_AFTER_SECONDS;
  }
  return Math.min(seconds, MAX_RETRY_AFTER_SECONDS);
}

function escapeHtml(value: string): string {
  return value
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;");
}

/** Minimal self-refreshing page; the session cookies stay untouched. */
function serviceUnavailable(
  req: NextRequest,
  result: BackendAuthResult<unknown>
): NextResponse {
  const cookieLocale = req.cookies.get(LOCALE_COOKIE)?.value;
  const locale = isLocale(cookieLocale) ? cookieLocale : defaultLocale;
  const t = (locale === "en" ? en : es).ServiceUnavailable;
  const retryAfter = retryAfterSeconds(result);
  const body = `<!doctype html><html lang="${locale}"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><meta http-equiv="refresh" content="${retryAfter}"><title>${escapeHtml(t.title)}</title></head><body><main><h1>${escapeHtml(t.title)}</h1><p>${escapeHtml(t.description)}</p><p><a href="${escapeHtml(req.nextUrl.pathname + req.nextUrl.search)}">${escapeHtml(t.retry)}</a></p></main></body></html>`;
  return new NextResponse(body, {
    status: 503,
    headers: {
      "Content-Type": "text/html; charset=utf-8",
      "Cache-Control": "no-store",
      "Retry-After": String(retryAfter),
    },
  });
}
