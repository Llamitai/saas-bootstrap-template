import { type NextRequest, NextResponse } from "next/server";
import { serverConfig } from "@/shared/config/server";
import {
  COOKIE_GOOGLE_OAUTH_STATE,
  GOOGLE_OAUTH_STATE_MAX_AGE,
} from "@/src/constants";

const GOOGLE_AUTHORIZE_URL = "https://accounts.google.com/o/oauth2/v2/auth";

export async function GET(request: NextRequest) {
  // Trailing slash would desync redirect_uri from the backend's GOOGLE_REDIRECT_URI.
  const origin = (serverConfig.appUrl || request.nextUrl.origin).replace(
    /\/+$/,
    ""
  );

  if (!serverConfig.googleClientId) {
    console.error("Google login: GOOGLE_CLIENT_ID is not configured");
    return NextResponse.redirect(new URL("/?error=googleLoginFailed", origin));
  }

  const state = crypto.randomUUID();
  const authorizeUrl = new URL(GOOGLE_AUTHORIZE_URL);
  authorizeUrl.searchParams.set("client_id", serverConfig.googleClientId);
  // Must match the backend's GOOGLE_REDIRECT_URI byte-for-byte — the token
  // exchange re-sends it and Google rejects any mismatch.
  authorizeUrl.searchParams.set(
    "redirect_uri",
    `${origin}/api/auth/google/callback`
  );
  authorizeUrl.searchParams.set("response_type", "code");
  authorizeUrl.searchParams.set("scope", "openid email profile");
  authorizeUrl.searchParams.set("state", state);
  authorizeUrl.searchParams.set("prompt", "select_account");

  const response = NextResponse.redirect(authorizeUrl);
  response.cookies.set({
    name: COOKIE_GOOGLE_OAUTH_STATE,
    value: state,
    httpOnly: true,
    secure: serverConfig.isProd,
    // "lax" so the cookie travels on the top-level redirect back from Google.
    sameSite: "lax",
    path: "/",
    maxAge: GOOGLE_OAUTH_STATE_MAX_AGE,
  });
  return response;
}
