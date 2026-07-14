import { type NextRequest, NextResponse } from "next/server";
import { genericServerError } from "@/shared/http/errors";
import { serverHttp } from "@/shared/http/server";
import { setSessionCookies } from "@/shared/http/session-cookies";

interface AcceptBody {
  firstName?: string | null;
  lastName?: string | null;
  password?: string;
}

export async function POST(
  request: NextRequest,
  context: { params: Promise<{ token: string }> }
) {
  const { token } = await context.params;
  try {
    const body = (await request.json()) as AcceptBody;
    const backendRes = await serverHttp.post(
      `/invitations/${encodeURIComponent(token)}/accept`,
      body,
      { validateStatus: () => true }
    );
    if (backendRes.status >= 400) {
      return NextResponse.json(backendRes.data, { status: backendRes.status });
    }

    const { session, user, tenant, tenantRole } = backendRes.data.data;
    const response = NextResponse.json({
      data: { user, tenant, tenantRole },
    });

    return setSessionCookies(response, session);
  } catch (error) {
    console.error("Error en accept-invitation:", error);
    return NextResponse.json(genericServerError, { status: 500 });
  }
}
