import { type JwtPayload, jwtDecode } from "jwt-decode";

/**
 * Checks the unverified `exp` claim. Good enough for routing decisions; the
 * backend verifies signatures. `leewaySeconds` treats a token that expires
 * within that window as already expired.
 */
export function isTokenValid(token: string, leewaySeconds = 0): boolean {
  try {
    const decoded = jwtDecode<JwtPayload>(token);
    if (!decoded.exp) return false;
    const currentTime = Math.floor(Date.now() / 1000);
    return decoded.exp >= currentTime + leewaySeconds;
  } catch {
    return false;
  }
}
