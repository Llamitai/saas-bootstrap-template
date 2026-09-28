import { type NextRequest, NextResponse } from "next/server";
import {
  isSessionRejected,
  rotateBackendSession,
} from "@/features/auth/server";
import { backendHeadersFrom } from "@/shared/http/bff";
import { genericServerError, invalidRefreshToken } from "@/shared/http/errors";
import {
  clearSessionCookies,
  setSessionCookies,
} from "@/shared/http/session-cookies";
import { COOKIE_REFRESH_TOKEN } from "@/src/constants";

export async function POST(request: NextRequest) {
  try {
    // Read from the request: next/headers cookies() depends on the async
    // request scope, which dev-time recompiles can lose in route handlers.
    const refreshToken = request.cookies.get(COOKIE_REFRESH_TOKEN)?.value;

    if (!refreshToken) {
      return clearSessionResponse(
        NextResponse.json(invalidRefreshToken, { status: 401 })
      );
    }

    // Client path for rotation; src/proxy.ts covers page navigations. The
    // per-module dedup in rotateBackendSession is not shared with the proxy
    // bundle: the backend grace window absorbs that race.
    const result = await rotateBackendSession(
      refreshToken,
      backendHeadersFrom(request)
    );

    if (!result.ok) {
      // Only a rejected token ends the session: answer 401 and drop the
      // cookies so the client signs out.
      if (isSessionRejected(result)) {
        return clearSessionResponse(
          NextResponse.json(result.body ?? invalidRefreshToken, {
            status: 401,
          })
        );
      }
      // 429/5xx/unreachable: keep the cookies and mirror the status so the
      // client surfaces an error instead of logging out.
      const response = NextResponse.json(result.body ?? genericServerError, {
        status: result.status,
      });
      if (result.retryAfter) {
        response.headers.set("Retry-After", result.retryAfter);
      }
      return response;
    }

    const { session, user, tenant, tenantRole } = result.body.data;

    const response = NextResponse.json({
      accessToken: session.accessToken,
      data: {
        user,
        tenant,
        tenantRole,
      },
      timestamp: result.body.timestamp,
    });

    return setSessionCookies(response, session);
  } catch (error) {
    console.error("Refresh route failed:", error);
    return NextResponse.json(genericServerError, { status: 500 });
  }
}

function clearSessionResponse(response: NextResponse): NextResponse {
  return clearSessionCookies(response);
}
