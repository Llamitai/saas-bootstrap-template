import { type NextRequest, NextResponse } from "next/server";
import { loginBackend } from "@/features/auth/server";
import { genericServerError, invalidCredentials } from "@/shared/http/errors";
import { setSessionCookies } from "@/shared/http/session-cookies";

export async function POST(request: NextRequest) {
  try {
    const body = await request.json();
    const { email, password } = body;

    if (!email || !password) {
      return NextResponse.json(invalidCredentials, { status: 400 });
    }

    const result = await loginBackend(email, password);
    if (!result.ok) {
      return NextResponse.json(result.body, { status: result.status });
    }

    const { session, user, tenant, tenantRole } = result.body.data;
    const response = NextResponse.json({
      data: {
        user,
        tenant,
        tenantRole,
      },
      datetime: result.body.datetime,
    });

    return setSessionCookies(response, session);
  } catch (error) {
    console.error("Error en login:", error);
    return NextResponse.json(genericServerError, { status: 500 });
  }
}
