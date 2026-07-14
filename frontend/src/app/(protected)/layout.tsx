import { cookies } from "next/headers";
import { redirect } from "next/navigation";
import { Fragment, type ReactNode } from "react";
import { SessionSync, StoreInitializer } from "@/features/app-shell";
import { refreshBackendSession } from "@/features/auth/server";
import { COOKIE_REFRESH_TOKEN } from "@/src/constants";

export const dynamic = "force-dynamic";

async function refreshServerSession() {
  const cookieStore = await cookies();
  const refreshToken = cookieStore.get(COOKIE_REFRESH_TOKEN)?.value;

  if (!refreshToken) {
    return null;
  }

  const result = await refreshBackendSession(refreshToken);
  if (!result.ok) {
    return null;
  }

  return result.body.data;
}

interface ProtectedLayoutProps {
  children: ReactNode;
}

export default async function ProtectedLayout({
  children,
}: ProtectedLayoutProps) {
  const session = await refreshServerSession();

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
        accessToken={session.session.accessToken}
      />
      <StoreInitializer />
      {children}
    </Fragment>
  );
}
