import { type NextRequest, NextResponse } from "next/server";
import { googleLoginBackend } from "@/features/auth/server";
import { serverConfig } from "@/shared/config/server";
import { clearCookie, setSessionCookies } from "@/shared/http/session-cookies";
import { COOKIE_GOOGLE_OAUTH_STATE } from "@/src/constants";

export async function GET(request: NextRequest) {
  const origin = (serverConfig.appUrl || request.nextUrl.origin).replace(
    /\/+$/,
    ""
  );
  const params = request.nextUrl.searchParams;
  const code = params.get("code");
  const state = params.get("state");
  const oauthError = params.get("error");
  const cookieState = request.cookies.get(COOKIE_GOOGLE_OAUTH_STATE)?.value;

  // The user backed out of the Google consent — back to login, no error toast.
  if (oauthError === "access_denied") {
    return clearState(NextResponse.redirect(new URL("/", origin)));
  }

  if (oauthError || !code || !state || !cookieState || state !== cookieState) {
    return clearState(
      NextResponse.redirect(new URL("/?error=googleLoginFailed", origin))
    );
  }

  try {
    const result = await googleLoginBackend(code);
    if (!result.ok) {
      return clearState(
        NextResponse.redirect(new URL("/?error=googleLoginFailed", origin))
      );
    }

    const { session, tenant } = result.body.data;
    const response = NextResponse.redirect(
      new URL(tenant ? "/members" : "/unassigned", origin)
    );

    return clearState(setSessionCookies(response, session));
  } catch (error) {
    console.error("Error en google login:", error);
    return clearState(
      NextResponse.redirect(new URL("/?error=googleLoginFailed", origin))
    );
  }
}

function clearState(response: NextResponse): NextResponse {
  return clearCookie(response, COOKIE_GOOGLE_OAUTH_STATE);
}
