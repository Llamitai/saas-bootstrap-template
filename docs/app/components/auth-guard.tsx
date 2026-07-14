import { Navigate, useLocation } from "react-router";
import type { ReactNode } from "react";
import { config } from "@/lib/config";
import { useSession } from "@/lib/session";

export function AuthGuard({ children }: { children: ReactNode }) {
  const session = useSession();
  const location = useLocation();

  if (!config.docsRequireAuth) {
    return <>{children}</>;
  }

  if (session.isLoading) {
    return (
      <div className="flex min-h-screen items-center justify-center text-sm text-fd-muted-foreground">
        Cargando sesión...
      </div>
    );
  }

  if (!session.isAuthenticated) {
    const redirectTo = `${location.pathname}${location.search}`;
    return (
      <Navigate
        replace
        to={`/login?redirectTo=${encodeURIComponent(redirectTo)}`}
      />
    );
  }

  return <>{children}</>;
}
