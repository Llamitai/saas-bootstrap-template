import { cookies } from "next/headers";
import { type NextRequest, NextResponse } from "next/server";
import { logoutBackend } from "@/features/auth/server";
import { clearSessionCookies } from "@/shared/http/session-cookies";
import { COOKIE_REFRESH_TOKEN } from "@/src/constants";

export async function POST(request: NextRequest) {
  try {
    const cookieStore = await cookies();
    // Obtener refresh token de las cookies

    const refreshToken = cookieStore.get(COOKIE_REFRESH_TOKEN)?.value;
    await logoutBackend(refreshToken);

    const response = NextResponse.json({
      data: {
        status: "SUCCESS",
      },
      datetime: new Date().toISOString(),
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
