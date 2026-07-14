import { type NextRequest, NextResponse } from "next/server";
import { genericServerError } from "@/shared/http/errors";
import { serverHttp } from "@/shared/http/server";

export async function POST(request: NextRequest) {
  try {
    const body = await request.json();
    const backendRes = await serverHttp.post(
      "/auth/reset-password/confirm",
      body,
      { validateStatus: () => true }
    );
    return NextResponse.json(backendRes.data, { status: backendRes.status });
  } catch (error) {
    console.error("reset-password/confirm error:", error);
    return NextResponse.json(genericServerError, { status: 500 });
  }
}
