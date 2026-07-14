import type { NextResponse } from "next/server";

import { serverConfig } from "@/shared/config/server";
import {
  ACCESS_TOKEN_MAX_AGE,
  COOKIE_ACCESS_TOKEN,
  COOKIE_REFRESH_ATTEMPTS,
  COOKIE_REFRESH_TOKEN,
  REFRESH_TOKEN_MAX_AGE,
} from "@/src/constants";

export type SessionCookieTokens = {
  accessToken: string;
  refreshToken: string;
};

const SESSION_COOKIE_NAMES = [
  COOKIE_REFRESH_TOKEN,
  COOKIE_ACCESS_TOKEN,
  COOKIE_REFRESH_ATTEMPTS,
] as const;

function setHttpOnlyCookie(
  response: NextResponse,
  name: string,
  value: string,
  maxAge: number
): void {
  response.cookies.set({
    name,
    value,
    httpOnly: true,
    secure: serverConfig.isProd,
    sameSite: "lax",
    path: "/",
    maxAge,
  });
}

export function setSessionCookies(
  response: NextResponse,
  tokens: SessionCookieTokens
): NextResponse {
  setHttpOnlyCookie(
    response,
    COOKIE_ACCESS_TOKEN,
    tokens.accessToken,
    ACCESS_TOKEN_MAX_AGE
  );
  setHttpOnlyCookie(
    response,
    COOKIE_REFRESH_TOKEN,
    tokens.refreshToken,
    REFRESH_TOKEN_MAX_AGE
  );
  clearCookie(response, COOKIE_REFRESH_ATTEMPTS);
  return response;
}

export function clearCookie(
  response: NextResponse,
  name: string
): NextResponse {
  setHttpOnlyCookie(response, name, "", 0);
  return response;
}

export function clearSessionCookies(response: NextResponse): NextResponse {
  for (const name of SESSION_COOKIE_NAMES) {
    clearCookie(response, name);
  }
  return response;
}
