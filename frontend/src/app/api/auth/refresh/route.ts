import { cookies } from "next/headers";
import { type NextRequest, NextResponse } from "next/server";
import { refreshBackendSession } from "@/features/auth/server";
import { genericServerError, invalidRefreshToken } from "@/shared/http/errors";
import {
  clearSessionCookies,
  setSessionCookies,
} from "@/shared/http/session-cookies";
import { COOKIE_REFRESH_TOKEN } from "@/src/constants";

export async function POST(request: NextRequest) {
  try {
    const cookieStore = await cookies();

    // Obtener refresh token de las cookies
    const refreshToken = cookieStore.get(COOKIE_REFRESH_TOKEN)?.value;

    if (!refreshToken) {
      return clearSessionResponse(
        NextResponse.json(invalidRefreshToken, { status: 401 })
      );
    }

    // Llamar al repositorio para refrescar el token
    const result = await refreshBackendSession(refreshToken);

    // Si hay error, retornar error y limpiar la sesión: si el backend rechaza
    // el RT no tiene sentido seguir guardándolo en el navegador.
    if (!result.ok) {
      return clearSessionResponse(
        NextResponse.json(result.body, { status: result.status })
      );
    }

    // Si es exitoso, establecer nuevas cookies y retornar access token
    const { session, user, tenant, tenantRole } = result.body.data;

    const response = NextResponse.json({
      accessToken: session.accessToken,
      data: {
        user,
        tenant,
        tenantRole,
      },
      datetime: result.body.datetime,
    });

    return setSessionCookies(response, session);
  } catch (error) {
    console.error("Error en refresh:", error);
    return NextResponse.json(genericServerError, { status: 500 });
  }
}

function clearSessionResponse(response: NextResponse): NextResponse {
  return clearSessionCookies(response);
}
