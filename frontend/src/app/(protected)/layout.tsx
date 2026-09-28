import { cookies, headers } from "next/headers";
import { redirect } from "next/navigation";
import { Fragment, type ReactNode } from "react";
import { SessionSync, StoreInitializer } from "@/features/app-shell";
import { getBackendSession, isSessionRejected } from "@/features/auth/server";
import { backendHeadersFrom } from "@/shared/http/bff";
import { COOKIE_ACCESS_TOKEN } from "@/src/constants";

export const dynamic = "force-dynamic";

// Server Components cannot write cookies, so this layout never rotates the
// refresh token: src/proxy.ts rotates it when the access cookie is missing or
// expired and forwards the new cookies to this render.
async function readServerSession() {
  const cookieStore = await cookies();
  const accessToken = cookieStore.get(COOKIE_ACCESS_TOKEN)?.value;

  if (!accessToken) {
    return null;
  }

  const result = await getBackendSession(
    accessToken,
    backendHeadersFrom({ headers: await headers() })
  );
  if (!result.ok) {
    if (isSessionRejected(result)) return null;
    // Transient backend failure: fail this render (error page, cookies kept)
    // instead of redirecting to login, which would count as a session loss.
    throw new Error(`Session read failed with status ${result.status}`);
  }

  return { ...result.body.data, accessToken };
}

interface ProtectedLayoutProps {
  children: ReactNode;
}

export default async function ProtectedLayout({
  children,
}: ProtectedLayoutProps) {
  const session = await readServerSession();

  if (!session) {
    redirect("/");
  }

  if (!session.tenant) {
    redirect("/unassigned");
  }

  // Keying the subtree by tenant slug forces a full remount of every page
  // (and its client stores' useEffect hooks) whenever the active tenant
  // changes server-side. Without this, router.refresh() would only re-run
  // Server Components, leaving client-side data fetched from the old tenant.
  return (
    <Fragment key={session.tenant.slug}>
      <SessionSync
        session={{
          user: session.user,
          tenant: session.tenant,
          tenantRole: session.tenantRole,
        }}
        accessToken={session.accessToken}
      />
      <StoreInitializer />
      {children}
    </Fragment>
  );
}
