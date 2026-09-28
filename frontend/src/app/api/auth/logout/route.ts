import { type NextRequest, NextResponse } from "next/server";
import { logoutBackend } from "@/features/auth/server";
import { backendHeadersFrom } from "@/shared/http/bff";
import { clearSessionCookies } from "@/shared/http/session-cookies";
import { COOKIE_REFRESH_TOKEN } from "@/src/constants";

export async function POST(request: NextRequest) {
  try {
    // Read from the request: next/headers cookies() depends on the async
    // request scope, which dev-time recompiles can lose in route handlers.
    const refreshToken = request.cookies.get(COOKIE_REFRESH_TOKEN)?.value;
    await logoutBackend(refreshToken, backendHeadersFrom(request));

    const response = NextResponse.json({
      data: {
        status: "SUCCESS",
      },
      timestamp: new Date().toISOString(),
    });

    return clearSessionCookies(response);
  } catch (error) {
    console.error("Error en logout:", error);
    return NextResponse.json(
      {
        errors: [
          {
            code: "SERVER_ERROR",
            message: "Error al cerrar sesión",
          },
        ],
        validation: null,
      },
      { status: 500 }
    );
  }
}
