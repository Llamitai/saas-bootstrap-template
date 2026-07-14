import type { NextRequest } from "next/server";
import { isTokenValid } from "@/shared/helpers/jwt-token";
import { COOKIE_REFRESH_TOKEN } from "@/src/constants";

export function getRefreshTokenFromRequest(
  request: NextRequest
): string | null {
  const refreshToken = request.cookies.get(COOKIE_REFRESH_TOKEN)?.value;
  if (!refreshToken) return null;
  if (isTokenValid(refreshToken)) return refreshToken;
  return null;
}
